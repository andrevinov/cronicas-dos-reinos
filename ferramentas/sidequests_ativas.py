#!/usr/bin/env python3
"""Task 48 — projeção read-only de sidequests aceitas.

Esta porta não cria oportunidade, não registra fato e não reconcilia prazo. Ela
localiza as missões já aceitas no estado compacto de oportunidades e projeta, no
máximo, os dois fragmentos Task45 permitidos pelo orçamento canônico.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Callable

import yaml

import oportunidades

SCHEMA = 1
TICKET_KEY = "sidequests_ativas_task48"
PROGRESS_PREFIX = Path("narrador/sidequests-emergentes/progresso")
MAX_ACTIVE = 2
MAX_PROJECTION_BYTES = 6 * 1024
MAX_COMBINED_PREP_BYTES = 16 * 1024
VALID_PHASE_STATES = {"indeterminada", "possivel", "impossivel", "resolvida"}
VALID_CONDITION_STATES = {"pendente", "satisfeita", "inviavel"}


class ActiveSidequestError(ValueError):
    pass


def configured(repo: Path) -> bool:
    return (repo / oportunidades.INDEX).is_file() and (repo / oportunidades.STATE).is_file()


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ActiveSidequestError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ActiveSidequestError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str, *, maximum: int = 240) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ActiveSidequestError(f"{label} deve ser texto não vazio")
    result = " ".join(value.split())
    if len(result) > maximum:
        raise ActiveSidequestError(f"{label} excede {maximum} caracteres")
    return result


def _yaml_size(value: Any) -> int:
    return len(yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8"))


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file(repo: Path, raw: Any, label: str) -> tuple[dict[str, Any], Path, str]:
    rel = Path(_text(raw, label))
    if rel.is_absolute() or ".." in rel.parts:
        raise ActiveSidequestError(f"{label} aponta para fora do repositório")
    try:
        rel.relative_to(PROGRESS_PREFIX)
    except ValueError as exc:
        raise ActiveSidequestError(
            f"{label} deve ficar sob {PROGRESS_PREFIX.as_posix()}"
        ) from exc
    path = repo / rel
    try:
        raw_bytes = path.read_bytes()
        value = yaml.safe_load(raw_bytes.decode("utf-8"))
    except (FileNotFoundError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise ActiveSidequestError(str(exc)) from exc
    return _map(value, rel.as_posix()), rel, hashlib.sha256(raw_bytes).hexdigest()


def _states(raw: Any, label: str, allowed: set[str]) -> dict[str, str]:
    data = _map(raw, label)
    result: dict[str, str] = {}
    for item_id, item_raw in sorted(data.items()):
        item = _map(item_raw, f"{label}.{item_id}")
        state = _text(item.get("estado"), f"{label}.{item_id}.estado", maximum=40)
        if state not in allowed:
            raise ActiveSidequestError(f"{label}.{item_id}.estado inválido: {state}")
        result[_text(item_id, f"{label}.id", maximum=128)] = state
    return result


def _dependencies(raw: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for pos, row_raw in enumerate(_list(raw, "contrato.dependencias_fases")):
        row = _map(row_raw, f"contrato.dependencias_fases[{pos}]")
        actors = [
            _text(value, f"dependencias[{pos}].atores_necessarios", maximum=128)
            for value in _list(row.get("atores_necessarios"), "atores_necessarios")
        ]
        substitution = row.get("substituicao_permitida")
        if not isinstance(substitution, bool):
            raise ActiveSidequestError("substituicao_permitida deve ser booleano")
        result.append(
            {
                "fase_id": _text(row.get("fase_id"), f"dependencias[{pos}].fase_id", maximum=128),
                "atores_necessarios": actors,
                "substituicao_permitida": substitution,
            }
        )
    return result


def _pressures(raw: Any) -> list[str]:
    result: list[str] = []
    for pos, row_raw in enumerate(_list(raw, "contrato.efeitos_escaladas")):
        row = _map(row_raw, f"contrato.efeitos_escaladas[{pos}]")
        escalation = _text(
            row.get("escalada_id"),
            f"contrato.efeitos_escaladas[{pos}].escalada_id",
            maximum=128,
        )
        if escalation in result:
            raise ActiveSidequestError(f"escalada Task45 duplicada: {escalation}")
        result.append(escalation)
    return result


def _actor_counts(raw: Any) -> dict[str, int]:
    actors = _map(raw, "estado.atores")
    counts: dict[str, int] = {}
    for actor_id, actor_raw in actors.items():
        actor = _map(actor_raw, f"estado.atores.{actor_id}")
        state = _text(actor.get("estado"), f"estado.atores.{actor_id}.estado", maximum=64)
        counts[state] = counts.get(state, 0) + 1
    return dict(sorted(counts.items()))


def _base_mission(mid: str, mission: dict[str, Any]) -> dict[str, Any]:
    return {
        "mission_id": mid,
        "quest_id": mission.get("quest_id"),
        "origem": mission.get("origem"),
        "titulo": mission.get("titulo"),
        "estado": mission.get("estado"),
        "prazo": copy.deepcopy(mission.get("janela")),
    }


def _project_mission(repo: Path, mid: str, mission: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    projected = _base_mission(mid, mission)
    if mission.get("origem") != "sidequest_emergente":
        projected.update(
            {
                "progresso": "legado_sem_task45",
                "digest_missao": _digest(mission),
            }
        )
        return projected, []

    doc, rel, progress_digest = _file(
        repo,
        mission.get("progresso_sidequest"),
        f"missoes.{mid}.progresso_sidequest",
    )
    if (
        doc.get("schema_progressao_sidequest") != 1
        or doc.get("mission_id") != mid
        or doc.get("quest_id") != mission.get("quest_id")
    ):
        raise ActiveSidequestError(f"fragmento Task45 divergente para {mid}")
    state = _map(doc.get("estado"), "estado")
    contract = _map(doc.get("contrato"), "contrato")
    terminal = state.get("terminal")
    if terminal is not None and not isinstance(terminal, dict):
        raise ActiveSidequestError("estado.terminal deve ser mapa ou null")
    projected.update(
        {
            "progresso": "task45",
            "fases": _states(state.get("fases"), "estado.fases", VALID_PHASE_STATES),
            "condicoes_sucesso": _states(
                state.get("condicoes_sucesso"),
                "estado.condicoes_sucesso",
                VALID_CONDITION_STATES,
            ),
            "condicoes_falha": _states(
                state.get("condicoes_falha"),
                "estado.condicoes_falha",
                VALID_CONDITION_STATES,
            ),
            "dependencias_fases": _dependencies(contract.get("dependencias_fases")),
            "atores_por_estado": _actor_counts(state.get("atores")),
            "pressoes_adversariais_contratadas": _pressures(
                contract.get("efeitos_escaladas")
            ),
            "terminal": copy.deepcopy(terminal),
            "digests": {
                "missao": _digest(mission),
                "task45": progress_digest,
            },
        }
    )
    return projected, [rel.as_posix()]


def _load_registry(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise ActiveSidequestError(str(exc)) from exc
    return index, state


def project(repo: Path) -> dict[str, Any]:
    if not configured(repo):
        return {
            "schema_sidequests_ativas": SCHEMA,
            "ok": True,
            "configurado": False,
            "resultado": "sem_sistema_configurado",
            "quantidade": 0,
            "missoes": [],
            "metricas": {
                "fragmentos_task45_lidos": 0,
                "escritas": 0,
                "rng_novo": 0,
                "scheduler_novo": 0,
                "scan_global": 0,
            },
            "fontes_lidas": [],
        }
    index, state = _load_registry(repo)
    active = sorted(
        (
            (mid, _map(mission, f"missoes.{mid}"))
            for mid, mission in state.get("missoes", {}).items()
            if isinstance(mission, dict) and mission.get("estado") == "aceita"
        ),
        key=lambda item: item[0],
    )
    limit = int(index["orcamento"]["max_ativas"])
    if limit != MAX_ACTIVE or len(active) > limit:
        raise ActiveSidequestError(
            f"projeção Task48 exige teto {MAX_ACTIVE}; configurado={limit}, ativas={len(active)}"
        )
    missions: list[dict[str, Any]] = []
    sources = [oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix()]
    progress_reads = 0
    for mid, mission in active:
        item, extra_sources = _project_mission(repo, mid, mission)
        missions.append(item)
        sources.extend(extra_sources)
        progress_reads += len(extra_sources)
    result = {
        "schema_sidequests_ativas": SCHEMA,
        "ok": True,
        "configurado": True,
        "resultado": "ativas_projetadas" if missions else "sem_ativas",
        "quantidade": len(missions),
        "missoes": missions,
        "metricas": {
            "fragmentos_task45_lidos": progress_reads,
            "escritas": 0,
            "rng_novo": 0,
            "scheduler_novo": 0,
            "scan_global": 0,
        },
        "fontes_lidas": list(dict.fromkeys(sources)),
    }
    size = _yaml_size(result)
    if size > MAX_PROJECTION_BYTES:
        raise ActiveSidequestError(
            f"projeção Task48 excede {MAX_PROJECTION_BYTES} bytes: {size}"
        )
    return result


def query(repo: Path, reference: str) -> dict[str, Any]:
    reference = _text(reference, "referencia", maximum=128)
    if not configured(repo):
        return {
            "schema_sidequests_ativas": SCHEMA,
            "ok": True,
            "configurado": False,
            "encontrada": False,
            "resultado": "sem_sistema_configurado",
            "fontes_lidas": [],
        }
    _, state = _load_registry(repo)
    matches = [
        (mid, _map(mission, f"missoes.{mid}"))
        for mid, mission in state.get("missoes", {}).items()
        if isinstance(mission, dict)
        and reference in {mid, mission.get("id"), mission.get("quest_id")}
    ]
    if not matches:
        return {
            "schema_sidequests_ativas": SCHEMA,
            "ok": True,
            "configurado": True,
            "encontrada": False,
            "resultado": "inexistente",
            "referencia": reference,
            "fontes_lidas": [
                oportunidades.INDEX.as_posix(),
                oportunidades.STATE.as_posix(),
            ],
        }
    if len(matches) != 1:
        raise ActiveSidequestError(f"sidequest ambígua: {reference}")
    mid, mission = matches[0]
    item, extra_sources = _project_mission(repo, mid, mission)
    return {
        "schema_sidequests_ativas": SCHEMA,
        "ok": True,
        "configurado": True,
        "encontrada": True,
        "resultado": "encontrada",
        "missao": item,
        "fontes_lidas": [
            oportunidades.INDEX.as_posix(),
            oportunidades.STATE.as_posix(),
            *extra_sources,
        ],
    }


def _ticket_rows(projection: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for item in projection.get("missoes") or []:
        digests = item.get("digests") or {}
        rows.append(
            {
                "mission_id": str(item.get("mission_id")),
                "quest_id": str(item.get("quest_id")),
                "estado": str(item.get("estado")),
                "digest_missao": str(digests.get("missao") or item.get("digest_missao")),
                "digest_task45": str(digests.get("task45") or "legado_sem_task45"),
            }
        )
    return rows


def ticket_meta(payload: dict[str, Any]) -> dict[str, Any] | None:
    raw = payload.get(TICKET_KEY)
    if raw is None:
        return None
    meta = _map(raw, TICKET_KEY)
    if set(meta) != {"schema", "missoes"} or meta.get("schema") != SCHEMA:
        raise ActiveSidequestError("metadados Task48 do ticket são inválidos")
    rows = _list(meta.get("missoes"), f"{TICKET_KEY}.missoes")
    if not 1 <= len(rows) <= MAX_ACTIVE:
        raise ActiveSidequestError("ticket Task48 exige uma ou duas missões")
    seen: set[str] = set()
    for pos, row_raw in enumerate(rows):
        row = _map(row_raw, f"{TICKET_KEY}.missoes[{pos}]")
        expected = {
            "mission_id",
            "quest_id",
            "estado",
            "digest_missao",
            "digest_task45",
        }
        if set(row) != expected or row.get("estado") != "aceita":
            raise ActiveSidequestError("linha Task48 do ticket inválida")
        mid = _text(row.get("mission_id"), "ticket.mission_id", maximum=128)
        if mid in seen:
            raise ActiveSidequestError("ticket Task48 contém missão duplicada")
        seen.add(mid)
        for key in ("digest_missao", "digest_task45"):
            digest = _text(row.get(key), f"ticket.{key}", maximum=64)
            if digest != "legado_sem_task45" and (
                len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest)
            ):
                raise ActiveSidequestError(f"ticket.{key} inválido")
    return copy.deepcopy(meta)


def integrate_prepare(
    repo: Path,
    base_result: dict[str, Any],
    *,
    decode_ticket: Callable[[str], dict[str, Any]],
    encode_ticket: Callable[[dict[str, Any]], tuple[str, str]],
) -> dict[str, Any]:
    projection = project(repo)
    if projection["quantidade"] == 0:
        return base_result
    token = base_result.get("ticket")
    if not isinstance(token, str):
        raise ActiveSidequestError("preparação cronica não retornou ticket")
    payload = copy.deepcopy(decode_ticket(token))
    payload[TICKET_KEY] = {"schema": SCHEMA, "missoes": _ticket_rows(projection)}
    new_token, new_id = encode_ticket(payload)
    result = copy.deepcopy(base_result)
    result["ticket"] = new_token
    result["ticket_id"] = new_id
    result["sidequests_ativas"] = projection
    result.setdefault("sistemas_narrativos", []).append("active_sidequest_reassessment")
    result.setdefault("filtros", []).append("sidequests_aceitas_projetadas_task48")
    result.setdefault("disponibilidade", {})["sidequests_ativas"] = projection["quantidade"]
    result["fontes_lidas"] = list(
        dict.fromkeys(
            [*(result.get("fontes_lidas") or []), *projection.get("fontes_lidas", [])]
        )
    )
    contract = result.get("contrato_conclusao")
    if isinstance(contract, dict):
        contract["sidequests_ativas_task48"] = (
            "Projeção read-only: reavalie os fatos narrados, mas ainda não envie progresso; "
            "a escrita transacional pertence à Task49."
        )
    total = _yaml_size(result)
    if total > MAX_COMBINED_PREP_BYTES:
        raise ActiveSidequestError(
            f"preparação com Task48 excede {MAX_COMBINED_PREP_BYTES} bytes: {total}"
        )
    return result


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    projection: dict[str, Any] | None = None
    try:
        projection = project(repo)
        if projection.get("quantidade", 0) > MAX_ACTIVE:
            errors.append("Task48 projetou mais de duas sidequests aceitas")
        if projection.get("metricas", {}).get("escritas") != 0:
            errors.append("Task48 declarou escrita no caminho read-only")
    except (ActiveSidequestError, OSError, yaml.YAMLError) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "erros": errors,
        "configurado": configured(repo),
        "ativas": int((projection or {}).get("quantidade") or 0),
        "contrato": {
            "max_ativas": MAX_ACTIVE,
            "projecao_max_bytes": MAX_PROJECTION_BYTES,
            "preparacao_combinada_max_bytes": MAX_COMBINED_PREP_BYTES,
            "novas_oportunidades_no_caminho_negativo": 0,
            "schedulers_novos": 0,
            "relogios_novos": 0,
            "rng_novo": 0,
            "scans_globais": 0,
            "escritas": 0,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("projetar")
    status = sub.add_parser("status")
    status.add_argument("referencia")
    sub.add_parser("check")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "projetar":
            result = project(repo)
        elif args.cmd == "status":
            result = query(repo, args.referencia)
        else:
            result = check(repo)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0 if result.get("ok") else 1
    except (ActiveSidequestError, OSError, yaml.YAMLError) as exc:
        print(
            yaml.safe_dump(
                {"schema_sidequests_ativas": SCHEMA, "ok": False, "erro": str(exc)},
                allow_unicode=True,
                sort_keys=False,
            ),
            end="",
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
