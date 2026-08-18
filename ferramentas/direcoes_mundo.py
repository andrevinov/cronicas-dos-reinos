#!/usr/bin/env python3
"""Integra direções canônicas à fila determinística do Mundo Vivo.

Este módulo é chamado em checkpoints, antes de `mundo.py` mover seu cursor até o
novo tempo canônico. Ele cria pendências de avaliação/ativação sem abrir os
fragmentos das direções e sem avançar qualquer marco automaticamente.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import direcoes
import mundo


def _direction_pending_id(kind: str, direction_id: str, when: mundo.WorldInstant) -> str:
    raw = f"{kind}|direcao:{direction_id}|{when.minute}".encode("utf-8")
    return "mundo-" + hashlib.sha256(raw).hexdigest()[:16]


def _pending_direction_ids(world_state: dict[str, Any]) -> set[str]:
    return {
        str(item.get("direcao"))
        for item in world_state.get("pendencias") or []
        if isinstance(item, dict) and item.get("direcao")
    }


def _activation_records(
    index: dict[str, Any],
    direction_state: dict[str, Any],
    world_state: dict[str, Any],
    when: mundo.WorldInstant,
) -> list[dict[str, Any]]:
    pending = _pending_direction_ids(world_state)
    result: list[dict[str, Any]] = []
    for direction_id, meta in index["direcoes"].items():
        current = direction_state["direcoes"][direction_id]
        if current["estado"] != "latente" or direction_id in pending:
            continue
        if not direcoes.dependency_satisfied(index, direction_state, direction_id):
            continue
        activation = meta.get("ativacao")
        if activation is None:
            continue
        dep = activation["depende_de"]
        result.append(
            {
                "id": _direction_pending_id("ativar_direcao", direction_id, when),
                "tipo": "ativar_direcao",
                "direcao": direction_id,
                "agentes_afetados": [],
                "disparado_em": mundo.instant_parts(when),
                "motivo": (
                    f"A dependência canônica {dep['direcao']}.{dep['marco']} foi satisfeita; "
                    "avaliar a ativação da direção sem escolher cena automaticamente."
                ),
                "origem": f"direcoes:{direction_id}.ativacao",
            }
        )
    return result


def _evaluation_records(
    index: dict[str, Any],
    direction_state: dict[str, Any],
    world_state: dict[str, Any],
    agenda: dict[str, Any],
    start: mundo.WorldInstant,
    end: mundo.WorldInstant,
) -> list[dict[str, Any]]:
    if end <= start:
        return []
    pending = _pending_direction_ids(world_state)
    dawn = mundo._dawn_minute(agenda)
    result: list[dict[str, Any]] = []
    for direction_id, meta in index["direcoes"].items():
        current = direction_state["direcoes"][direction_id]
        if current["estado"] != "ativa" or direction_id in pending:
            continue
        evaluation = meta["avaliacao"]
        start_day = mundo._date_to_day_index(evaluation["inicio"])
        interval = int(evaluation["intervalo_dias"])
        due: list[mundo.WorldInstant] = []
        for day_index in mundo._iter_day_indices(start, end):
            if day_index < start_day or (day_index - start_day) % interval:
                continue
            when = mundo.WorldInstant(day_index * 1440 + dawn)
            if start < when <= end:
                due.append(when)
        if not due:
            continue
        when = due[-1]
        result.append(
            {
                "id": _direction_pending_id("avaliar_direcao", direction_id, when),
                "tipo": "avaliar_direcao",
                "direcao": direction_id,
                "agentes_afetados": [],
                "disparado_em": mundo.instant_parts(when),
                "motivo": (
                    f"Reavaliar o marco {current.get('marco_atual')} da direção {meta['nome']} "
                    "contra os fatos canônicos já ocorridos; cadência não implica avanço."
                ),
                "origem": f"direcoes:{direction_id}.avaliacao",
            }
        )
    return result


def process_checkpoint(repo: Path) -> dict[str, Any]:
    """Acrescenta pendências de direção sem mover o cursor do mundo."""
    index = direcoes.load_index(repo)
    direction_state = direcoes.load_state(repo, index)
    world_state = mundo.load_world_state(repo)
    agenda = mundo.load_agenda(repo)
    canonical, _ = mundo.load_canonical_time(repo)
    cursor = mundo._state_cursor(world_state)
    if cursor > canonical:
        raise direcoes.DirectionError("cursor do Mundo Vivo está à frente do tempo canônico")

    emitted = _activation_records(index, direction_state, world_state, canonical)
    emitted.extend(
        _evaluation_records(index, direction_state, world_state, agenda, cursor, canonical)
    )
    emitted.sort(key=lambda item: (mundo.parse_instant(item["disparado_em"]["data"], item["disparado_em"]["hora"]).minute, item["id"]))
    added = mundo._merge_pending(world_state, emitted)
    if added:
        mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, world_state)
    return {
        "ok": True,
        "novas_pendencias": added,
        "direcoes_reconsiderar": sorted({item["direcao"] for item in added}),
        "fontes_lidas": [
            direcoes.INDEX_PATH.as_posix(),
            direcoes.STATE_PATH.as_posix(),
            mundo.WORLD_STATE_PATH.as_posix(),
            mundo.AGENDA_PATH.as_posix(),
            mundo.TIME_PATH.as_posix(),
        ],
    }


def check_repo(repo: Path) -> dict[str, Any]:
    result = direcoes.validate_repo(repo)
    errors = list(result.get("erros") or [])
    try:
        index = direcoes.load_index(repo)
        known = set(index["direcoes"])
        world_state = mundo.load_world_state(repo)
        for item in world_state.get("pendencias") or []:
            if item.get("tipo") in {"avaliar_direcao", "ativar_direcao"}:
                direction_id = item.get("direcao")
                if direction_id not in known:
                    errors.append(f"pendência do mundo referencia direção inexistente: {direction_id}")
    except (direcoes.DirectionError, mundo.WorldEngineError) as exc:
        errors.append(str(exc))
    return {"ok": not errors, "erros": list(dict.fromkeys(errors))}
