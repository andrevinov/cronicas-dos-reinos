#!/usr/bin/env python3
"""Presença incidental determinística para NPCs recorrentes.

A camada responde somente a esta pergunta: dado um local canônico, sua ecologia e
um instante já conhecido, algum NPC recorrente com rotina canonicamente ancorada
ali merece ser *avaliado* como coincidência incidental?

O resultado nunca estabelece presença. Não cria ação, diálogo, conhecimento,
encontro, sidequest, scheduler ou estado próprio. A janela é derivada somente de
seed + dia + período + local + NPC; ``scene_id`` serve apenas para identificar a
avaliação, portanto trocar o ID da cena não permite pescar outro resultado.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml

import agentes_leves
import ecologia_local
import locais
import mundo

INDEX = Path("narrador/presencas-incidentais.yaml")
RELATIONS_ROOT = Path("estado/relacoes")
SCHEMA = 1
MAX_PROFILES = 8
MAX_CANDIDATES = 1
MAX_LOCALS_PER_PROFILE = 2
MAX_PERIODS_PER_LOCAL = 4
MAX_MOTIVES_PER_LOCAL = 4
MAX_DIVISOR = 16
PERIODS = tuple(ecologia_local.PERIODS)
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")
PROFILE_FIELDS = {"nome", "fonte_canonica", "locais"}
LOCAL_FIELDS = {"periodos", "motivos", "evidencia_local"}
REQUIRED_RULES = {
    "exige_agente_leve_ativo",
    "exige_local_canonico",
    "exige_periodo_compativel",
    "exige_motivo_compativel_com_ecologia",
    "candidato_nao_e_presenca",
    "candidato_nao_cria_acao",
    "candidato_nao_cria_dialogo",
    "candidato_nao_cria_conhecimento",
    "candidato_nao_cria_encontro_sidequest",
    "sem_scheduler",
    "sem_estado_proprio",
    "janela_independe_de_scene_id",
    "canon_forte_prevalece",
}


class IncidentalPresenceError(ValueError):
    """Erro de contrato da camada de presença incidental."""


def configured(repo: Path) -> bool:
    return (repo / INDEX).is_file()


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise IncidentalPresenceError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IncidentalPresenceError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise IncidentalPresenceError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IncidentalPresenceError(f"{label} deve ser texto não vazio")
    return value.strip()


def _slug(value: Any, label: str) -> str:
    text = _text(value, label)
    if not SLUG_RE.fullmatch(text):
        raise IncidentalPresenceError(f"{label} deve ser slug ASCII minúsculo")
    return text


def _strict(data: dict[str, Any], allowed: set[str], label: str) -> None:
    missing = sorted(allowed - set(data))
    extra = sorted(set(data) - allowed)
    if missing or extra:
        raise IncidentalPresenceError(
            f"{label}: campos inválidos; ausentes={missing}, extras={extra}"
        )


def _repo_source(raw: Any, label: str) -> str:
    source = _text(raw, label)
    path = Path(source)
    if path.is_absolute() or ".." in path.parts:
        raise IncidentalPresenceError(f"{label} deve permanecer no repositório")
    try:
        path.relative_to(RELATIONS_ROOT)
    except ValueError as exc:
        raise IncidentalPresenceError(
            f"{label} deve permanecer sob {RELATIONS_ROOT.as_posix()}"
        ) from exc
    return path.as_posix()


def _slugs(value: Any, label: str, *, maximum: int) -> list[str]:
    raw = _list(value, label)
    if not 1 <= len(raw) <= maximum:
        raise IncidentalPresenceError(f"{label} deve ter entre 1 e {maximum} itens")
    result = [_slug(item, f"{label}[{i}]") for i, item in enumerate(raw)]
    if len(result) != len(set(result)):
        raise IncidentalPresenceError(f"{label} não pode conter duplicatas")
    return result


def load_index(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / INDEX), INDEX.as_posix())
    if data.get("schema_presenca_incidental") != SCHEMA:
        raise IncidentalPresenceError(f"índice deve usar schema_presenca_incidental: {SCHEMA}")
    if data.get("natureza") != "roteador_operacional_nao_canonico":
        raise IncidentalPresenceError("natureza da presença incidental inválida")
    if data.get("estatuto") != "candidato_de_coincidencia":
        raise IncidentalPresenceError("estatuto da presença incidental inválido")
    _text(data.get("seed"), "seed")

    budget = _map(data.get("orcamento"), "orcamento")
    expected_budget = {
        "max_perfis",
        "max_candidatos_por_cena",
        "divisor_janela",
        "slots_ativos",
        "max_locais_por_perfil",
        "max_periodos_por_local",
        "max_motivos_por_local",
    }
    _strict(budget, expected_budget, "orcamento")
    if budget["max_perfis"] != MAX_PROFILES:
        raise IncidentalPresenceError(f"orcamento.max_perfis deve ser {MAX_PROFILES}")
    if budget["max_candidatos_por_cena"] != MAX_CANDIDATES:
        raise IncidentalPresenceError(
            f"orcamento.max_candidatos_por_cena deve ser {MAX_CANDIDATES}"
        )
    divisor = budget["divisor_janela"]
    if not isinstance(divisor, int) or isinstance(divisor, bool) or not 2 <= divisor <= MAX_DIVISOR:
        raise IncidentalPresenceError(f"orcamento.divisor_janela deve ficar entre 2 e {MAX_DIVISOR}")
    slots = _list(budget["slots_ativos"], "orcamento.slots_ativos")
    if not slots or any(
        not isinstance(slot, int) or isinstance(slot, bool) or not 0 <= slot < divisor
        for slot in slots
    ):
        raise IncidentalPresenceError("orcamento.slots_ativos contém slot inválido")
    if len(slots) != len(set(slots)) or len(slots) >= divisor:
        raise IncidentalPresenceError("orcamento.slots_ativos deve ser conjunto próprio da janela")
    if budget["max_locais_por_perfil"] != MAX_LOCALS_PER_PROFILE:
        raise IncidentalPresenceError(
            f"orcamento.max_locais_por_perfil deve ser {MAX_LOCALS_PER_PROFILE}"
        )
    if budget["max_periodos_por_local"] != MAX_PERIODS_PER_LOCAL:
        raise IncidentalPresenceError(
            f"orcamento.max_periodos_por_local deve ser {MAX_PERIODS_PER_LOCAL}"
        )
    if budget["max_motivos_por_local"] != MAX_MOTIVES_PER_LOCAL:
        raise IncidentalPresenceError(
            f"orcamento.max_motivos_por_local deve ser {MAX_MOTIVES_PER_LOCAL}"
        )

    rules = _map(data.get("regras"), "regras")
    if set(rules) != REQUIRED_RULES or not all(value is True for value in rules.values()):
        raise IncidentalPresenceError("regras da presença incidental devem permanecer integralmente verdadeiras")

    profiles = _map(data.get("perfis"), "perfis")
    if not 1 <= len(profiles) <= MAX_PROFILES:
        raise IncidentalPresenceError(f"presença incidental deve ter entre 1 e {MAX_PROFILES} perfis")
    for agent_id, raw_profile in profiles.items():
        agent_id = _slug(agent_id, "id de perfil")
        profile = _map(raw_profile, f"perfis.{agent_id}")
        _strict(profile, PROFILE_FIELDS, f"perfis.{agent_id}")
        _text(profile["nome"], f"perfis.{agent_id}.nome")
        _repo_source(profile["fonte_canonica"], f"perfis.{agent_id}.fonte_canonica")
        profile_locals = _map(profile["locais"], f"perfis.{agent_id}.locais")
        if not 1 <= len(profile_locals) <= MAX_LOCALS_PER_PROFILE:
            raise IncidentalPresenceError(
                f"perfis.{agent_id}.locais deve ter entre 1 e {MAX_LOCALS_PER_PROFILE} locais"
            )
        for local_id, raw_local in profile_locals.items():
            _slug(local_id, f"perfis.{agent_id}.local_id")
            local = _map(raw_local, f"perfis.{agent_id}.locais.{local_id}")
            _strict(local, LOCAL_FIELDS, f"perfis.{agent_id}.locais.{local_id}")
            periods = _slugs(
                local["periodos"],
                f"perfis.{agent_id}.locais.{local_id}.periodos",
                maximum=MAX_PERIODS_PER_LOCAL,
            )
            invalid_periods = sorted(set(periods) - set(PERIODS))
            if invalid_periods:
                raise IncidentalPresenceError(
                    f"perfis.{agent_id}.{local_id}: períodos inválidos: {', '.join(invalid_periods)}"
                )
            _slugs(
                local["motivos"],
                f"perfis.{agent_id}.locais.{local_id}.motivos",
                maximum=MAX_MOTIVES_PER_LOCAL,
            )
            _text(local["evidencia_local"], f"perfis.{agent_id}.{local_id}.evidencia_local")
    return data


def period_from_instant(instant: mundo.WorldInstant) -> str:
    """Mapeia relógio para os quatro períodos ecológicos sem ler arquivo algum."""
    minute = instant.minute % 1440
    if 5 * 60 <= minute < 8 * 60:
        return "amanhecer"
    if 8 * 60 <= minute < 17 * 60:
        return "dia"
    if 17 * 60 <= minute < 21 * 60:
        return "anoitecer"
    return "noite"


def _window(seed: str, instant: mundo.WorldInstant, period: str, local_id: str, agent_id: str, divisor: int) -> tuple[str, int, int]:
    day_index = instant.minute // 1440
    token = f"{seed}|{day_index}|{period}|{local_id}|{agent_id}".encode("utf-8")
    digest = hashlib.sha256(token).digest()
    hexdigest = digest.hex()
    slot = int.from_bytes(digest[:8], "big") % divisor
    rank = int.from_bytes(digest[8:16], "big")
    return f"incidental-{hexdigest[:16]}", slot, rank


def _motive(digest_seed: str, compatible: list[str]) -> str:
    digest = hashlib.sha256(digest_seed.encode("utf-8")).digest()
    return compatible[int.from_bytes(digest[:8], "big") % len(compatible)]


def _local_profiles(index: dict[str, Any], local_id: str, excluded: set[str]) -> list[tuple[str, dict[str, Any], dict[str, Any]]]:
    result: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
    for agent_id, profile in index["perfis"].items():
        if agent_id in excluded:
            continue
        local = profile["locais"].get(local_id)
        if isinstance(local, dict):
            result.append((agent_id, profile, local))
    return result


def select(
    repo: Path,
    *,
    scene_id: str,
    local_id: str,
    ecology: dict[str, Any],
    now: mundo.WorldInstant | None = None,
    exclude_ids: Iterable[str] | None = None,
    limit: int = MAX_CANDIDATES,
) -> dict[str, Any]:
    """Seleciona no máximo um candidato incidental sem abrir fragmentos narrativos."""
    if not isinstance(limit, int) or isinstance(limit, bool) or not 0 <= limit <= MAX_CANDIDATES:
        raise IncidentalPresenceError(f"limit deve ficar entre 0 e {MAX_CANDIDATES}")
    local_id = _slug(local_id, "local_id")
    scene_id = _text(scene_id, "scene_id")
    index = load_index(repo)
    sources = [INDEX.as_posix()]
    if limit == 0:
        return {
            "local_id": local_id,
            "periodo": None,
            "candidatos": [],
            "fontes_lidas": sources,
            "regra": "orçamento contextual sem vaga para presença incidental",
        }

    local_profiles = _local_profiles(index, local_id, set(exclude_ids or []))
    if not local_profiles:
        return {
            "local_id": local_id,
            "periodo": None,
            "candidatos": [],
            "fontes_lidas": sources,
            "regra": "nenhum perfil incidental opt-in está ancorado neste local",
        }

    current = now
    if current is None:
        try:
            current, _ = mundo.load_canonical_time(repo)
        except mundo.WorldEngineError as exc:
            raise IncidentalPresenceError(str(exc)) from exc
        sources.append(mundo.TIME_PATH.as_posix())
    period = period_from_instant(current)
    try:
        activity = ecologia_local.activity(ecology, period)
    except ecologia_local.LocalEcologyError as exc:
        raise IncidentalPresenceError(str(exc)) from exc
    ecology_terms = set(activity["tags"]) | set(activity["canais_microevento"])

    divisor = int(index["orcamento"]["divisor_janela"])
    active_slots = set(index["orcamento"]["slots_ativos"])
    rows: list[tuple[int, str, dict[str, Any]]] = []
    for agent_id, profile, local in local_profiles:
        if period not in local["periodos"]:
            continue
        compatible = sorted(set(local["motivos"]) & ecology_terms)
        if not compatible:
            continue
        window_id, slot, rank = _window(index["seed"], current, period, local_id, agent_id, divisor)
        if slot not in active_slots:
            continue
        motive = _motive(window_id + "|motivo", compatible)
        item = {
            "id": agent_id,
            "binding_id": f"incidental_{agent_id}",
            "tipo": "presenca",
            "subtipo": "incidental",
            "origem": "presenca_incidental",
            "nome": profile["nome"],
            "grupo_arco": "livre",
            "local_id": local_id,
            "periodo": period,
            "motivo": motive,
            "janela_id": window_id,
            "coincidencias": [f"local:{local_id}"],
            "prioridade": 0,
            "modo_avaliacao": "avaliar_presenca_incidental",
            "avaliacao_id": f"scene:{scene_id}:contexto:presenca_incidental:{agent_id}",
            "consulta_dirigida": f"python3 ferramentas/agentes_leves.py mostrar {agent_id}",
            "regra": (
                "coincidência determinística de rotina: avaliar contra o cânone forte antes de narrar; "
                "não estabelece presença, ação, diálogo, conhecimento, encontro ou sidequest"
            ),
        }
        rows.append((rank, agent_id, item))

    rows.sort(key=lambda row: (row[0], row[1]))
    candidates = [row[2] for row in rows[:limit]]
    return {
        "local_id": local_id,
        "periodo": period,
        "candidatos": candidates,
        "fontes_lidas": list(dict.fromkeys(sources)),
        "regra": (
            "janela derivada de seed+dia+período+local+NPC, independente de scene_id; "
            "resultado é somente candidato de avaliação"
        ),
    }


def _normalize_space(value: str) -> str:
    return " ".join(value.split())


def validate(repo: Path) -> dict[str, Any]:
    """Validação fria cruza os perfis com fontes canônicas sem expandir o hot path."""
    errors: list[str] = []
    try:
        index = load_index(repo)
        location_index = locais.load_index(repo)
        ecology = ecologia_local.load_index(repo)
        light = agentes_leves.load_index(repo)
        canonical_locations = set(location_index["locais"])
        light_agents = light["agentes"]

        for agent_id, profile in index["perfis"].items():
            meta = light_agents.get(agent_id)
            if not isinstance(meta, dict):
                errors.append(f"perfil incidental referencia agente leve inexistente: {agent_id}")
                continue
            if meta.get("estado") != "ativo":
                errors.append(f"perfil incidental exige agente leve ativo: {agent_id}")
            if meta.get("nome") != profile.get("nome"):
                errors.append(f"nome incidental diverge do agente leve: {agent_id}")
            source = profile["fonte_canonica"]
            if source not in set(meta.get("fontes_causais") or []):
                errors.append(f"fonte incidental não pertence às fontes causais de {agent_id}: {source}")
            source_path = repo / source
            if not source_path.is_file():
                errors.append(f"fonte canônica incidental inexistente: {source}")
                continue
            relation = _map(_load(source_path), source)
            relation_id = relation.get("id")
            relation_body = relation.get("relacao") if isinstance(relation.get("relacao"), dict) else {}
            if relation_id != agent_id:
                errors.append(f"fonte canônica incidental possui id divergente: {agent_id}")
            if relation_body.get("nome") != profile.get("nome"):
                errors.append(f"nome da relação diverge do perfil incidental: {agent_id}")
            haystack = _normalize_space(source_path.read_text(encoding="utf-8"))
            for local_id, local in profile["locais"].items():
                if local_id not in canonical_locations:
                    errors.append(f"perfil incidental usa local não canônico: {agent_id}/{local_id}")
                    continue
                eco = ecology["perfis"].get(local_id)
                if not isinstance(eco, dict):
                    errors.append(f"perfil incidental usa local sem ecologia: {agent_id}/{local_id}")
                    continue
                ecology_terms = set(eco["tags"]) | set(eco["canais_microevento"])
                if not set(local["motivos"]) & ecology_terms:
                    errors.append(f"motivos incidentais incompatíveis com ecologia: {agent_id}/{local_id}")
                evidence = _normalize_space(local["evidencia_local"])
                if evidence not in haystack:
                    errors.append(f"evidência local não encontrada em {source}: {evidence}")
    except (IncidentalPresenceError, locais.LocationError, ecologia_local.LocalEcologyError, agentes_leves.LightAgentError) as exc:
        errors.append(str(exc))
        index = {"perfis": {}}

    return {
        "ok": not errors,
        "perfis": len(index.get("perfis") or {}),
        "erros": list(dict.fromkeys(errors)),
        "fontes_lidas": [
            INDEX.as_posix(),
            locais.INDEX.as_posix(),
            ecologia_local.INDEX.as_posix(),
            agentes_leves.INDEX.as_posix(),
        ],
    }


def check(repo: Path) -> dict[str, Any]:
    return validate(repo)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="valida perfis, âncoras canônicas e ecologia")
    evaluate = sub.add_parser("avaliar", help="simula seleção incidental read-only para um local")
    evaluate.add_argument("local")
    evaluate.add_argument("--cena-id", default="cli-presenca-incidental")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "check":
            result = check(repo)
            status = 0 if result["ok"] else 1
        else:
            resolved = locais.resolve(repo, args.local)
            ecology = ecologia_local.lookup_canonical(repo, resolved["local_id"])
            result = select(
                repo,
                scene_id=args.cena_id,
                local_id=resolved["local_id"],
                ecology=ecology["perfil"],
            )
            result["fontes_lidas"] = list(
                dict.fromkeys([*resolved["fontes_lidas"], *ecology["fontes_lidas"], *result["fontes_lidas"]])
            )
            status = 0
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return status
    except (IncidentalPresenceError, locais.LocationError, ecologia_local.LocalEcologyError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
