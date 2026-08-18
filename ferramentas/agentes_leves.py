#!/usr/bin/env python3
"""Agentes recorrentes leves do Mundo Vivo.

A camada existe para NPCs que continuam vivendo fora de cena, mas cuja rotina é
o padrão. Checkpoints de amanhecer fazem apenas uma pré-seleção determinística;
fragmentos só são abertos quando uma pendência concreta precisa ser resolvida.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
import unicodedata
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import mundo

INDEX = Path("narrador/agentes-leves/index.yaml")
STATE = Path("narrador/agentes-leves/estado.yaml")
DIR = Path("narrador/agentes-leves")
VALID_STATES = {"ativo", "inativo"}
PROFILE = "recorrente_leve"


class LightAgentError(ValueError):
    """Erro de contrato da camada de agentes leves."""


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LightAgentError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise LightAgentError(f"YAML inválido em {path}: {exc}") from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LightAgentError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise LightAgentError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LightAgentError(f"{label} deve ser texto não vazio")
    return value.strip()


def _normalize(value: str) -> str:
    raw = unicodedata.normalize("NFKD", str(value))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return " ".join(raw.split()).lower()


def _repo_path(repo: Path, raw: str, *, prefix: Path | None = None) -> Path:
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        raise LightAgentError(f"caminho fora do repositório: {raw}")
    if prefix is not None:
        try:
            rel.relative_to(prefix)
        except ValueError as exc:
            raise LightAgentError(
                f"caminho {raw} deve permanecer sob {prefix.as_posix()}"
            ) from exc
    return repo / rel


def load_index(repo: Path) -> dict[str, Any]:
    data = _map(_load_yaml(repo / INDEX), INDEX.as_posix())
    if data.get("schema_agentes_leves") != 1:
        raise LightAgentError("índice deve usar schema_agentes_leves: 1")
    if data.get("natureza") != "reservado":
        raise LightAgentError("índice de agentes leves deve ter natureza: reservado")

    budget = _map(data.get("orcamento"), "orcamento")
    max_new = budget.get("max_novas_por_checkpoint")
    max_open = budget.get("max_pendencias_abertas")
    if not isinstance(max_new, int) or max_new < 1:
        raise LightAgentError("orcamento.max_novas_por_checkpoint deve ser inteiro >= 1")
    if not isinstance(max_open, int) or max_open < 1:
        raise LightAgentError("orcamento.max_pendencias_abertas deve ser inteiro >= 1")
    if max_new > max_open:
        raise LightAgentError("max_novas_por_checkpoint não pode exceder max_pendencias_abertas")
    if budget.get("ordenacao") != "mais_atrasado_prioridade_id":
        raise LightAgentError("orcamento.ordenacao deve ser mais_atrasado_prioridade_id")

    agents = _map(data.get("agentes"), "agentes")
    if not agents:
        raise LightAgentError("índice de agentes leves não pode ser vazio")
    files: set[str] = set()
    for agent_id, raw in agents.items():
        agent_id = _text(agent_id, "id de agente leve")
        meta = _map(raw, f"agentes.{agent_id}")
        _text(meta.get("nome"), f"agentes.{agent_id}.nome")
        if meta.get("perfil_operacional") != PROFILE:
            raise LightAgentError(f"{agent_id}.perfil_operacional deve ser {PROFILE}")
        state = _text(meta.get("estado"), f"agentes.{agent_id}.estado")
        if state not in VALID_STATES:
            raise LightAgentError(f"estado inválido para {agent_id}: {state}")
        priority = meta.get("prioridade")
        if not isinstance(priority, int) or not 0 <= priority <= 9:
            raise LightAgentError(f"{agent_id}.prioridade deve ser inteiro entre 0 e 9")
        interval = meta.get("intervalo_dias")
        if not isinstance(interval, int) or interval < 1:
            raise LightAgentError(f"{agent_id}.intervalo_dias deve ser inteiro >= 1")
        start = _map(meta.get("inicio"), f"agentes.{agent_id}.inicio")
        mundo.parse_instant(
            _text(start.get("data"), f"agentes.{agent_id}.inicio.data"),
            _text(start.get("hora"), f"agentes.{agent_id}.inicio.hora"),
        )
        raw_path = _text(meta.get("arquivo"), f"agentes.{agent_id}.arquivo")
        _repo_path(repo, raw_path, prefix=DIR)
        if raw_path in files:
            raise LightAgentError(f"arquivo de agente leve duplicado: {raw_path}")
        files.add(raw_path)
    return data


def load_state(repo: Path, index: dict[str, Any] | None = None) -> dict[str, Any]:
    index = index or load_index(repo)
    data = _map(_load_yaml(repo / STATE), STATE.as_posix())
    if data.get("schema_estado_agentes_leves") != 1:
        raise LightAgentError("estado deve usar schema_estado_agentes_leves: 1")
    if data.get("natureza") != "controle_reservado":
        raise LightAgentError("estado de agentes leves deve ter natureza: controle_reservado")
    states = _map(data.get("agentes"), "estado.agentes")
    expected = set(index["agentes"])
    actual = set(states)
    if expected != actual:
        raise LightAgentError(
            f"estado/índice divergem; ausentes={sorted(expected-actual)}, extras={sorted(actual-expected)}"
        )
    for agent_id, raw in states.items():
        item = _map(raw, f"estado.agentes.{agent_id}")
        if item.get("estado") != index["agentes"][agent_id]["estado"]:
            raise LightAgentError(f"{agent_id}: estado diverge do índice")
        next_eval = _map(item.get("proxima_avaliacao"), f"{agent_id}.proxima_avaliacao")
        mundo.parse_instant(
            _text(next_eval.get("data"), f"{agent_id}.proxima_avaliacao.data"),
            _text(next_eval.get("hora"), f"{agent_id}.proxima_avaliacao.hora"),
        )
    return data


def _validate_evidence(
    repo: Path, source: str, evidence: str, label: str, *, check_sources: bool
) -> None:
    if not check_sources:
        return
    path = _repo_path(repo, source)
    if not path.is_file():
        raise LightAgentError(f"{label}: fonte canônica inexistente: {source}")
    haystack = " ".join(path.read_text(encoding="utf-8").split())
    needle = " ".join(evidence.split())
    if needle not in haystack:
        raise LightAgentError(f"{label}: evidência não localizada em {source}")


def load_fragment(
    repo: Path,
    agent_id: str,
    meta: dict[str, Any],
    *,
    check_sources: bool = False,
) -> dict[str, Any]:
    raw_path = _text(meta.get("arquivo"), f"agentes.{agent_id}.arquivo")
    path = _repo_path(repo, raw_path, prefix=DIR)
    data = _map(_load_yaml(path), raw_path)
    if data.get("schema_agente_leve") != 1:
        raise LightAgentError(f"{agent_id}: schema_agente_leve deve ser 1")
    if data.get("natureza") != "reservado":
        raise LightAgentError(f"{agent_id}: natureza deve ser reservado")
    if data.get("id") != agent_id or data.get("nome") != meta.get("nome"):
        raise LightAgentError(f"{agent_id}: id/nome divergem do índice")
    if data.get("perfil_operacional") != PROFILE:
        raise LightAgentError(f"{agent_id}: perfil_operacional deve ser {PROFILE}")

    sources = _list(data.get("fontes_canonicas"), f"{agent_id}.fontes_canonicas")
    source_set: set[str] = set()
    for i, source in enumerate(sources):
        source_set.add(_text(source, f"{agent_id}.fontes_canonicas[{i}]"))

    for field in ("rotina_padrao", "objetivo_atual"):
        item = _map(data.get(field), f"{agent_id}.{field}")
        _text(item.get("descricao"), f"{agent_id}.{field}.descricao")
        source = _text(item.get("fonte"), f"{agent_id}.{field}.fonte")
        evidence = _text(item.get("evidencia"), f"{agent_id}.{field}.evidencia")
        if source not in source_set:
            raise LightAgentError(f"{agent_id}.{field}: fonte não declarada: {source}")
        _validate_evidence(repo, source, evidence, f"{agent_id}.{field}", check_sources=check_sources)

    initiatives = _list(data.get("iniciativas_possiveis"), f"{agent_id}.iniciativas_possiveis")
    for i, raw in enumerate(initiatives):
        item = _map(raw, f"{agent_id}.iniciativas_possiveis[{i}]")
        _text(item.get("descricao"), f"{agent_id}.iniciativas_possiveis[{i}].descricao")
        source = _text(item.get("fonte"), f"{agent_id}.iniciativas_possiveis[{i}].fonte")
        evidence = _text(item.get("evidencia"), f"{agent_id}.iniciativas_possiveis[{i}].evidencia")
        if source not in source_set:
            raise LightAgentError(
                f"{agent_id}.iniciativas_possiveis[{i}]: fonte não declarada: {source}"
            )
        _validate_evidence(
            repo,
            source,
            evidence,
            f"{agent_id}.iniciativas_possiveis[{i}]",
            check_sources=check_sources,
        )
    _text(data.get("regra_de_reavaliacao"), f"{agent_id}.regra_de_reavaliacao")
    return data


def resolve_agent(index: dict[str, Any], query: str) -> tuple[str, dict[str, Any]]:
    if query in index["agentes"]:
        return query, index["agentes"][query]
    wanted = _normalize(query)
    matches = []
    for agent_id, meta in index["agentes"].items():
        candidates = {_normalize(agent_id), _normalize(meta["nome"])}
        if wanted in candidates or any(wanted and wanted in value for value in candidates):
            matches.append((agent_id, meta))
    if not matches:
        raise LightAgentError(f"agente leve não encontrado: {query}")
    if len(matches) > 1:
        raise LightAgentError(
            f"consulta ambígua para {query!r}: {', '.join(item[0] for item in matches)}"
        )
    return matches[0]


def load_agent(repo: Path, query: str) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    agent_id, meta = resolve_agent(index, query)
    fragment = load_fragment(repo, agent_id, meta, check_sources=False)
    return {
        "agente_leve_id": agent_id,
        "proxima_avaliacao": state["agentes"][agent_id]["proxima_avaliacao"],
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), meta["arquivo"]],
        "resultado": fragment,
    }


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        index = load_index(repo)
        load_state(repo, index)
        for agent_id, meta in index["agentes"].items():
            load_fragment(repo, agent_id, meta, check_sources=True)
    except LightAgentError as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "quantidade": len(index["agentes"]) if "index" in locals() else 0,
        "erros": errors,
    }


def _pending_id(agent_id: str, due: mundo.WorldInstant) -> str:
    raw = f"reavaliar_agente_leve|{agent_id}|{due.minute}".encode("utf-8")
    return "mundo-" + hashlib.sha256(raw).hexdigest()[:16]


def _light_pending(world_state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in world_state.get("pendencias") or []
        if isinstance(item, dict) and item.get("tipo") == "reavaliar_agente_leve"
    ]


def _next_future(
    due: mundo.WorldInstant, interval_days: int, canonical: mundo.WorldInstant
) -> mundo.WorldInstant:
    step = interval_days * 1440
    value = mundo.WorldInstant(due.minute + step)
    while value <= canonical:
        value = mundo.WorldInstant(value.minute + step)
    return value


def _set_next(state: dict[str, Any], agent_id: str, instant: mundo.WorldInstant) -> None:
    state["agentes"][agent_id]["proxima_avaliacao"] = mundo.instant_parts(instant)


def process_checkpoint(repo: Path) -> dict[str, Any]:
    """Seleciona poucos NPCs leves vencidos; não abre nenhum fragmento."""
    index = load_index(repo)
    state = load_state(repo, index)
    canonical, _ = mundo.load_canonical_time(repo)
    world_state = mundo.load_world_state(repo)

    open_pending = _light_pending(world_state)
    open_agents = {
        str(item.get("agente_leve")) for item in open_pending if item.get("agente_leve")
    }
    open_ids = {str(item.get("id")) for item in open_pending if item.get("id")}
    completed_ids = {
        str(item.get("id"))
        for item in world_state.get("concluidas_recentes") or []
        if isinstance(item, dict) and item.get("id")
    }

    state_changed = False
    candidates: list[tuple[mundo.WorldInstant, int, str, dict[str, Any]]] = []
    for agent_id, meta in index["agentes"].items():
        if meta["estado"] != "ativo":
            continue
        raw_due = state["agentes"][agent_id]["proxima_avaliacao"]
        due = mundo.parse_instant(raw_due["data"], raw_due["hora"])
        pid = _pending_id(agent_id, due)

        if pid in open_ids or pid in completed_ids:
            next_due = _next_future(due, int(meta["intervalo_dias"]), canonical)
            _set_next(state, agent_id, next_due)
            state_changed = True
            continue

        if agent_id in open_agents or due > canonical:
            continue
        candidates.append((due, -int(meta["prioridade"]), agent_id, meta))

    candidates.sort(key=lambda item: (item[0].minute, item[1], item[2]))
    budget = index["orcamento"]
    available_open = max(0, int(budget["max_pendencias_abertas"]) - len(open_pending))
    limit = min(int(budget["max_novas_por_checkpoint"]), available_open)
    selected = candidates[:limit]

    emitted: list[dict[str, Any]] = []
    for due, _neg_priority, agent_id, meta in selected:
        emitted.append(
            {
                "id": _pending_id(agent_id, due),
                "tipo": "reavaliar_agente_leve",
                "agente_leve": agent_id,
                "agentes_afetados": [],
                "disparado_em": mundo.instant_parts(due),
                "motivo": (
                    f"Reavaliar {meta['nome']} fora de cena. Rotina é o padrão; "
                    "só registrar iniciativa se o estado atual oferecer causa concreta."
                ),
                "origem": f"agentes-leves:{agent_id}.cadencia",
            }
        )

    added = mundo._merge_pending(world_state, emitted)
    if added:
        mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, world_state)
        added_ids = {item["id"] for item in added}
        for due, _neg_priority, agent_id, meta in selected:
            if _pending_id(agent_id, due) in added_ids:
                _set_next(
                    state,
                    agent_id,
                    _next_future(due, int(meta["intervalo_dias"]), canonical),
                )
                state_changed = True

    if state_changed:
        mundo._atomic_write_yaml(repo / STATE, state)

    deferred = [agent_id for _due, _priority, agent_id, _meta in candidates[limit:]]
    return {
        "ok": True,
        "novas_pendencias": added,
        "agentes_leves_reconsiderar": [item["agente_leve"] for item in added],
        "adiados_por_orcamento": deferred,
        "orcamento": {
            "max_novas_por_checkpoint": budget["max_novas_por_checkpoint"],
            "max_pendencias_abertas": budget["max_pendencias_abertas"],
            "pendencias_abertas_antes": len(open_pending),
        },
        "fontes_lidas": [
            INDEX.as_posix(),
            STATE.as_posix(),
            mundo.TIME_PATH.as_posix(),
            mundo.WORLD_STATE_PATH.as_posix(),
        ],
    }


def status_view(repo: Path) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    canonical, _ = mundo.load_canonical_time(repo)
    due = []
    for agent_id, meta in index["agentes"].items():
        raw = state["agentes"][agent_id]["proxima_avaliacao"]
        instant = mundo.parse_instant(raw["data"], raw["hora"])
        if meta["estado"] == "ativo" and instant <= canonical:
            due.append(agent_id)
    return {
        "orcamento": index["orcamento"],
        "vencidos": sorted(due),
        "proximas_avaliacoes": {
            agent_id: state["agentes"][agent_id]["proxima_avaliacao"]
            for agent_id in sorted(index["agentes"])
        },
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), mundo.TIME_PATH.as_posix()],
    }


def check_world(repo: Path) -> dict[str, Any]:
    errors = list(validate_repo(repo).get("erros") or [])
    try:
        index = load_index(repo)
        known = set(index["agentes"])
        world_state = mundo.load_world_state(repo)
        pending = _light_pending(world_state)
        for item in pending:
            agent_id = item.get("agente_leve")
            if agent_id not in known:
                errors.append(f"pendência referencia agente leve inexistente: {agent_id}")
        if len(pending) > int(index["orcamento"]["max_pendencias_abertas"]):
            errors.append("pendências leves abertas excedem o orçamento configurado")
    except (LightAgentError, mundo.WorldEngineError) as exc:
        errors.append(str(exc))
    return {"ok": not errors, "erros": list(dict.fromkeys(errors))}


def _dump(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("validar")
    show = sub.add_parser("mostrar")
    show.add_argument("agente")
    sub.add_parser("processar")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.command == "status":
            result = status_view(repo)
        elif args.command == "validar":
            result = validate_repo(repo)
        elif args.command == "mostrar":
            result = load_agent(repo, args.agente)
        else:
            result = process_checkpoint(repo)
        print(_dump(result), end="")
        if args.command == "validar":
            return 0 if result["ok"] else 1
        return 0
    except (LightAgentError, mundo.WorldEngineError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
