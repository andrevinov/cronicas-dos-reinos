#!/usr/bin/env python3
"""Consulta não mutante da próxima fronteira temporal do Mundo Vivo.

Use somente antes de uma ação que comprime um intervalo relevante de tempo
(dormir, esperar, viajar, trabalhar por horas etc.). A consulta responde se o
alvo pretendido atravessa um instante em que alguma camada determinística pode
precisar ser processada. Ela não processa o mundo, não abre fragmentos e não
cria pendências.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

import agentes_leves
import direcoes
import entradas
import eventos_mundo
import mundo

LAYER_ORDER = (
    "agendamentos",
    "agentes_estrategicos",
    "direcoes",
    "entradas",
    "agentes_leves",
    "eventos_mundo",
)


class BoundaryError(ValueError):
    """Erro de contrato da consulta de fronteira temporal."""


def _configured(repo: Path, *paths: Path) -> bool:
    return all((repo / path).is_file() for path in paths)


def _compact(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _first_due_dawn(
    start: mundo.WorldInstant,
    target: mundo.WorldInstant,
    *,
    start_day: int,
    interval_days: int,
    dawn: int,
) -> mundo.WorldInstant | None:
    for day in mundo._iter_day_indices(start, target):
        if day < start_day or (day - start_day) % interval_days:
            continue
        when = mundo.WorldInstant(day * 1440 + dawn)
        if start < when <= target:
            return when
    return None


def _add(
    candidates: list[tuple[int, str, str]],
    start: mundo.WorldInstant,
    target: mundo.WorldInstant,
    when: mundo.WorldInstant | None,
    layer: str,
    item_id: str,
) -> None:
    if when is None or not (start < when <= target):
        return
    candidates.append((when.minute, layer, item_id))


def _agenda_candidates(
    agenda: dict[str, Any],
    start: mundo.WorldInstant,
    target: mundo.WorldInstant,
    candidates: list[tuple[int, str, str]],
) -> None:
    dawn = mundo._dawn_minute(agenda)
    for agent_id, rule in (agenda.get("reavaliacoes") or {}).items():
        when = _first_due_dawn(
            start,
            target,
            start_day=mundo._date_to_day_index(rule["inicio"]),
            interval_days=int(rule.get("intervalo_dias", 1)),
            dawn=dawn,
        )
        _add(candidates, start, target, when, "agentes_estrategicos", agent_id)

    for item in agenda.get("agendamentos") or []:
        when = mundo.parse_instant(item["em"]["data"], item["em"]["hora"])
        _add(candidates, start, target, when, "agendamentos", str(item["id"]))


def _direction_candidates(
    repo: Path,
    agenda: dict[str, Any],
    world_state: dict[str, Any],
    start: mundo.WorldInstant,
    target: mundo.WorldInstant,
    candidates: list[tuple[int, str, str]],
    sources: list[str],
) -> None:
    if not _configured(repo, direcoes.INDEX_PATH, direcoes.STATE_PATH):
        return
    index = direcoes.load_index(repo)
    state = direcoes.load_state(repo, index)
    sources.extend([direcoes.INDEX_PATH.as_posix(), direcoes.STATE_PATH.as_posix()])
    pending = {
        str(item.get("direcao"))
        for item in world_state.get("pendencias") or []
        if isinstance(item, dict) and item.get("direcao")
    }
    dawn = mundo._dawn_minute(agenda)
    for direction_id, meta in index["direcoes"].items():
        current = state["direcoes"][direction_id]
        if current.get("estado") != "ativa" or direction_id in pending:
            continue
        evaluation = meta["avaliacao"]
        when = _first_due_dawn(
            start,
            target,
            start_day=mundo._date_to_day_index(evaluation["inicio"]),
            interval_days=int(evaluation["intervalo_dias"]),
            dawn=dawn,
        )
        _add(candidates, start, target, when, "direcoes", direction_id)


def _entry_candidates(
    repo: Path,
    world_state: dict[str, Any],
    start: mundo.WorldInstant,
    target: mundo.WorldInstant,
    candidates: list[tuple[int, str, str]],
    sources: list[str],
) -> None:
    if not _configured(repo, entradas.INDEX, entradas.STATE):
        return
    index = entradas.load_index(repo)
    state = entradas.load_state(repo, index)
    sources.extend([entradas.INDEX.as_posix(), entradas.STATE.as_posix()])
    candidate_id = entradas.focus(index, state)
    if not candidate_id:
        return
    already_open = {
        str(item.get("entrada"))
        for item in world_state.get("pendencias") or []
        if isinstance(item, dict) and item.get("tipo") == "avaliar_entrada"
    }
    if candidate_id in already_open:
        return
    raw = state["candidatos"][candidate_id].get("proxima_avaliacao")
    due = entradas.parse_due(raw, candidate_id + ".proxima_avaliacao")
    _add(candidates, start, target, due, "entradas", candidate_id)


def _light_candidates(
    repo: Path,
    world_state: dict[str, Any],
    start: mundo.WorldInstant,
    target: mundo.WorldInstant,
    candidates: list[tuple[int, str, str]],
    sources: list[str],
) -> None:
    if not _configured(repo, agentes_leves.INDEX, agentes_leves.STATE):
        return
    index = agentes_leves.load_index(repo)
    state = agentes_leves.load_state(repo, index)
    sources.extend([agentes_leves.INDEX.as_posix(), agentes_leves.STATE.as_posix()])
    opened = [
        item
        for item in world_state.get("pendencias") or []
        if isinstance(item, dict) and item.get("tipo") == "reavaliar_agente_leve"
    ]
    budget = index["orcamento"]
    if len(opened) >= int(budget["max_pendencias_abertas"]):
        return
    open_agents = {
        str(item.get("agente_leve")) for item in opened if item.get("agente_leve")
    }
    for agent_id, meta in index["agentes"].items():
        if meta.get("estado") != "ativo" or agent_id in open_agents:
            continue
        raw = state["agentes"][agent_id]["proxima_avaliacao"]
        due = mundo.parse_instant(raw["data"], raw["hora"])
        _add(candidates, start, target, due, "agentes_leves", agent_id)


def _event_candidates(
    repo: Path,
    agenda: dict[str, Any],
    start: mundo.WorldInstant,
    target: mundo.WorldInstant,
    candidates: list[tuple[int, str, str]],
    sources: list[str],
) -> None:
    if not eventos_mundo.configured(repo):
        return
    index = eventos_mundo.load_index(repo)
    state = eventos_mundo.load_state(repo, index)
    sources.extend([eventos_mundo.INDEX.as_posix(), eventos_mundo.STATE.as_posix()])
    done = eventos_mundo.instant(state["processado_ate"], "processado_ate")
    minimum = eventos_mundo.instant(index["inicio"], "inicio")
    dawn = mundo._dawn_minute(agenda)
    due = eventos_mundo.dawns(done, target, dawn, minimum)
    when = next((item for item in due if start < item <= target), None)
    _add(candidates, start, target, when, "eventos_mundo", "baralho_mundial")


def next_boundary(repo: Path, target: mundo.WorldInstant) -> dict[str, Any]:
    """Retorna a primeira fronteira em (tempo_canônico, alvo], sem mutar o repo."""
    start, _ = mundo.load_canonical_time(repo)
    if target < start:
        raise BoundaryError("o alvo da fronteira não pode ser anterior ao tempo canônico")

    agenda = mundo.load_agenda(repo)
    world_state = mundo.load_world_state(repo)
    sources = [
        mundo.TIME_PATH.as_posix(),
        mundo.AGENDA_PATH.as_posix(),
        mundo.WORLD_STATE_PATH.as_posix(),
    ]
    candidates: list[tuple[int, str, str]] = []

    if target > start:
        _agenda_candidates(agenda, start, target, candidates)
        _direction_candidates(repo, agenda, world_state, start, target, candidates, sources)
        _entry_candidates(repo, world_state, start, target, candidates, sources)
        _light_candidates(repo, world_state, start, target, candidates, sources)
        _event_candidates(repo, agenda, start, target, candidates, sources)

    base = {
        "ok": True,
        "inicio": mundo.instant_parts(start),
        "alvo": mundo.instant_parts(target),
        "fontes_lidas": _compact(sources),
    }
    if not candidates:
        return {**base, "interromper": False, "fronteira": None}

    earliest = min(item[0] for item in candidates)
    grouped: dict[str, set[str]] = {}
    for minute, layer, item_id in candidates:
        if minute == earliest:
            grouped.setdefault(layer, set()).add(item_id)
    reasons = [
        {"camada": layer, "ids": sorted(grouped[layer])}
        for layer in LAYER_ORDER
        if layer in grouped
    ]
    instant = mundo.WorldInstant(earliest)
    return {
        **base,
        "interromper": True,
        "fronteira": {
            **mundo.instant_parts(instant),
            "minutos_ate_fronteira": earliest - start.minute,
            "motivos": reasons,
        },
    }


def query(repo: Path, date: str, hour: str) -> dict[str, Any]:
    return next_boundary(repo, mundo.parse_instant(date, hour))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--data", required=True, help="data-alvo, ex.: '11 Eleasis, 1372 DR'")
    parser.add_argument("--hora", required=True, help="hora-alvo HH:MM")
    args = parser.parse_args(argv)
    try:
        result = query(args.repo.resolve(), args.data, args.hora)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0
    except (BoundaryError, ValueError, OSError, yaml.YAMLError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
