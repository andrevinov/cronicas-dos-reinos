#!/usr/bin/env python3
"""Integra camadas canônicas de baixa frequência à fila do Mundo Vivo.

Lifecycle de NPCs roda primeiro: uma morte já consolidada desliga agenda e
pendências antes que outras camadas reconsiderem o NPC. Em seguida, relógios
sincronizam pressão→consequência e recompõem seu roteador derivado. Direções,
entradas e agentes recorrentes leves observam o mesmo checkpoint antes de
``mundo.py`` mover o cursor. Nenhuma camada faz acontecimentos ocorrerem sozinha.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import agentes_leves
import ciclo_npcs
import direcoes
import entradas
import mundo
import relogios


def _direction_pending_id(kind: str, direction_id: str, when: mundo.WorldInstant) -> str:
    raw = f"{kind}|direcao:{direction_id}|{when.minute}".encode("utf-8")
    return "mundo-" + hashlib.sha256(raw).hexdigest()[:16]


def _pending_direction_ids(world_state: dict[str, Any]) -> set[str]:
    return {
        str(item.get("direcao"))
        for item in world_state.get("pendencias") or []
        if isinstance(item, dict) and item.get("direcao")
    }


def _entries_configured(repo: Path) -> bool:
    return (repo / entradas.INDEX).is_file() and (repo / entradas.STATE).is_file()


def _light_agents_configured(repo: Path) -> bool:
    return (repo / agentes_leves.INDEX).is_file() and (repo / agentes_leves.STATE).is_file()


def _crossed_dawn(
    agenda: dict[str, Any], start: mundo.WorldInstant, end: mundo.WorldInstant
) -> bool:
    if end <= start:
        return False
    dawn = mundo._dawn_minute(agenda)
    for day_index in mundo._iter_day_indices(start, end):
        when = mundo.WorldInstant(day_index * 1440 + dawn)
        if start < when <= end:
            return True
    return False


def _activation_records(index, direction_state, world_state, when):
    pending = _pending_direction_ids(world_state)
    result = []
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
                    "avaliar a ativação sem escolher cena automaticamente."
                ),
                "origem": f"direcoes:{direction_id}.ativacao",
            }
        )
    return result


def _evaluation_records(index, direction_state, world_state, agenda, start, end):
    if end <= start:
        return []
    pending = _pending_direction_ids(world_state)
    dawn = mundo._dawn_minute(agenda)
    result = []
    for direction_id, meta in index["direcoes"].items():
        current = direction_state["direcoes"][direction_id]
        if current["estado"] != "ativa" or direction_id in pending:
            continue
        evaluation = meta["avaliacao"]
        start_day = mundo._date_to_day_index(evaluation["inicio"])
        interval = int(evaluation["intervalo_dias"])
        due = []
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
    lifecycle_result = {
        "ok": True,
        "configurado": False,
        "mortos": [],
        "novos_mortos": [],
        "pendencias_canceladas": [],
    }
    if ciclo_npcs.configured(repo):
        lifecycle_result = {"configurado": True, **ciclo_npcs.sync(repo)}

    clocks_result = {
        "ok": True,
        "configurado": False,
        "pressoes_ativas": 0,
        "consequencias_resolvidas": 0,
        "resolvidos_agora": [],
        "roteador_alterado": False,
    }
    if relogios.configured(repo):
        clocks_result = {"configurado": True, **relogios.sync(repo)}

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
    emitted.sort(
        key=lambda item: (
            mundo.parse_instant(
                item["disparado_em"]["data"], item["disparado_em"]["hora"]
            ).minute,
            item["id"],
        )
    )
    added = mundo._merge_pending(world_state, emitted)
    if added:
        mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, world_state)

    entry_result = {"novas_pendencias": [], "entradas_reconsiderar": [], "fontes_lidas": []}
    if _entries_configured(repo):
        entry_result = entradas.process_checkpoint(repo)

    light_result = {
        "novas_pendencias": [],
        "agentes_leves_reconsiderar": [],
        "adiados_por_orcamento": [],
        "fontes_lidas": [],
    }
    if _light_agents_configured(repo) and _crossed_dawn(agenda, cursor, canonical):
        light_result = agentes_leves.process_checkpoint(repo)

    return {
        "ok": True,
        "ciclo_npcs": lifecycle_result,
        "relogios": clocks_result,
        "novas_pendencias": [
            *added,
            *(entry_result.get("novas_pendencias") or []),
            *(light_result.get("novas_pendencias") or []),
        ],
        "direcoes_reconsiderar": sorted({item["direcao"] for item in added}),
        "entradas_reconsiderar": entry_result.get("entradas_reconsiderar") or [],
        "agentes_leves_reconsiderar": light_result.get("agentes_leves_reconsiderar") or [],
        "agentes_leves_adiados": light_result.get("adiados_por_orcamento") or [],
        "fontes_lidas": [
            *(lifecycle_result.get("fontes_lidas") or []),
            *(clocks_result.get("fontes_expostas") or []),
            direcoes.INDEX_PATH.as_posix(),
            direcoes.STATE_PATH.as_posix(),
            mundo.WORLD_STATE_PATH.as_posix(),
            mundo.AGENDA_PATH.as_posix(),
            mundo.TIME_PATH.as_posix(),
            *(entry_result.get("fontes_lidas") or []),
            *(light_result.get("fontes_lidas") or []),
        ],
    }


def check_repo(repo: Path) -> dict[str, Any]:
    result = direcoes.validate_repo(repo)
    errors = list(result.get("erros") or [])
    try:
        if ciclo_npcs.configured(repo):
            lifecycle_check = ciclo_npcs.validate_repo(repo)
            errors.extend(
                f"ciclo de NPCs: {error}"
                for error in lifecycle_check.get("erros") or []
            )
        if relogios.configured(repo):
            clocks_check = relogios.validate_repo(repo)
            errors.extend(
                f"relógios: {error}"
                for error in clocks_check.get("erros") or []
            )

        index = direcoes.load_index(repo)
        known = set(index["direcoes"])
        world_state = mundo.load_world_state(repo)
        for item in world_state.get("pendencias") or []:
            if item.get("tipo") in {"avaliar_direcao", "ativar_direcao"}:
                direction_id = item.get("direcao")
                if direction_id not in known:
                    errors.append(
                        f"pendência do mundo referencia direção inexistente: {direction_id}"
                    )
        if _entries_configured(repo):
            entry_check = entradas.check_world(repo)
            errors.extend(
                f"entradas: {error}" for error in entry_check.get("erros") or []
            )
        if _light_agents_configured(repo):
            light_check = agentes_leves.check_world(repo)
            errors.extend(
                f"agentes leves: {error}"
                for error in light_check.get("erros") or []
            )
    except (
        agentes_leves.LightAgentError,
        ciclo_npcs.LifecycleError,
        direcoes.DirectionError,
        entradas.EntryError,
        mundo.WorldEngineError,
        relogios.ClockError,
    ) as exc:
        errors.append(str(exc))
    return {"ok": not errors, "erros": list(dict.fromkeys(errors))}
