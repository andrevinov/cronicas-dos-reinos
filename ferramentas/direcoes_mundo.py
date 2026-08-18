#!/usr/bin/env python3
"""Integra camadas canônicas de baixa frequência à fila do Mundo Vivo.

Lifecycle de NPCs roda primeiro: uma morte já consolidada desliga agenda e
pendências antes que outras camadas reconsiderem o NPC. Em seguida, candidatos
mortos são removidos de eventos ainda pendentes; relógios sincronizam
pressão→consequência; direções, entradas, agentes recorrentes leves e o baralho
mundial observam o mesmo checkpoint antes de ``mundo.py`` mover o cursor.
Nenhuma camada faz acontecimentos ocorrerem sozinha.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import agentes_leves
import ciclo_npcs
import direcoes
import entradas
import eventos_mundo
import mundo
import relogios


def _direction_pending_id(kind, direction_id, when):
    return "mundo-" + hashlib.sha256(
        f"{kind}|direcao:{direction_id}|{when.minute}".encode()
    ).hexdigest()[:16]


def _pending_direction_ids(world_state):
    return {
        str(item.get("direcao"))
        for item in world_state.get("pendencias") or []
        if isinstance(item, dict) and item.get("direcao")
    }


def _entries_configured(repo):
    return (repo / entradas.INDEX).is_file() and (repo / entradas.STATE).is_file()


def _light_agents_configured(repo):
    return (repo / agentes_leves.INDEX).is_file() and (
        repo / agentes_leves.STATE
    ).is_file()


def _crossed_dawn(agenda, start, end):
    if end <= start:
        return False
    dawn = mundo._dawn_minute(agenda)
    return any(
        start < mundo.WorldInstant(day * 1440 + dawn) <= end
        for day in mundo._iter_day_indices(start, end)
    )


def _activation_records(index, state, world_state, when):
    pending = _pending_direction_ids(world_state)
    result = []
    for direction_id, meta in index["direcoes"].items():
        current = state["direcoes"][direction_id]
        if (
            current["estado"] != "latente"
            or direction_id in pending
            or not direcoes.dependency_satisfied(index, state, direction_id)
        ):
            continue
        activation = meta.get("ativacao")
        if activation is None:
            continue
        dependency = activation["depende_de"]
        result.append(
            {
                "id": _direction_pending_id("ativar_direcao", direction_id, when),
                "tipo": "ativar_direcao",
                "direcao": direction_id,
                "agentes_afetados": [],
                "disparado_em": mundo.instant_parts(when),
                "motivo": (
                    f"A dependência canônica {dependency['direcao']}."
                    f"{dependency['marco']} foi satisfeita; avaliar a ativação "
                    "sem escolher cena automaticamente."
                ),
                "origem": f"direcoes:{direction_id}.ativacao",
            }
        )
    return result


def _evaluation_records(index, state, world_state, agenda, start, end):
    if end <= start:
        return []
    pending = _pending_direction_ids(world_state)
    dawn = mundo._dawn_minute(agenda)
    result = []
    for direction_id, meta in index["direcoes"].items():
        current = state["direcoes"][direction_id]
        if current["estado"] != "ativa" or direction_id in pending:
            continue
        evaluation = meta["avaliacao"]
        start_day = mundo._date_to_day_index(evaluation["inicio"])
        interval = int(evaluation["intervalo_dias"])
        due = []
        for day in mundo._iter_day_indices(start, end):
            if day < start_day or (day - start_day) % interval:
                continue
            when = mundo.WorldInstant(day * 1440 + dawn)
            if start < when <= end:
                due.append(when)
        if due:
            when = due[-1]
            result.append(
                {
                    "id": _direction_pending_id(
                        "avaliar_direcao", direction_id, when
                    ),
                    "tipo": "avaliar_direcao",
                    "direcao": direction_id,
                    "agentes_afetados": [],
                    "disparado_em": mundo.instant_parts(when),
                    "motivo": (
                        f"Reavaliar o marco {current.get('marco_atual')} da "
                        f"direção {meta['nome']} contra os fatos canônicos já "
                        "ocorridos; cadência não implica avanço."
                    ),
                    "origem": f"direcoes:{direction_id}.avaliacao",
                }
            )
    return result


def process_checkpoint(repo: Path) -> dict[str, Any]:
    lifecycle = {
        "ok": True,
        "configurado": False,
        "mortos": [],
        "novos_mortos": [],
        "pendencias_canceladas": [],
    }
    if ciclo_npcs.configured(repo):
        lifecycle = {"configurado": True, **ciclo_npcs.sync(repo)}

    event_cleanup = {
        "ok": True,
        "alterou": False,
        "pendencias_atualizadas": [],
    }
    if eventos_mundo.configured(repo) and lifecycle.get("mortos"):
        event_cleanup = eventos_mundo.prune_dead_candidates(
            repo, set(lifecycle["mortos"])
        )

    clocks = {
        "ok": True,
        "configurado": False,
        "pressoes_ativas": 0,
        "consequencias_resolvidas": 0,
        "resolvidos_agora": [],
        "roteador_alterado": False,
    }
    if relogios.configured(repo):
        clocks = {"configurado": True, **relogios.sync(repo)}

    index = direcoes.load_index(repo)
    direction_state = direcoes.load_state(repo, index)
    world_state = mundo.load_world_state(repo)
    agenda = mundo.load_agenda(repo)
    canonical, _ = mundo.load_canonical_time(repo)
    cursor = mundo._state_cursor(world_state)
    if cursor > canonical:
        raise direcoes.DirectionError(
            "cursor do Mundo Vivo está à frente do tempo canônico"
        )

    emitted = _activation_records(index, direction_state, world_state, canonical)
    emitted.extend(
        _evaluation_records(
            index, direction_state, world_state, agenda, cursor, canonical
        )
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

    entry = {
        "novas_pendencias": [],
        "entradas_reconsiderar": [],
        "fontes_lidas": [],
    }
    if _entries_configured(repo):
        entry = entradas.process_checkpoint(repo)

    light = {
        "novas_pendencias": [],
        "agentes_leves_reconsiderar": [],
        "adiados_por_orcamento": [],
        "fontes_lidas": [],
    }
    if _light_agents_configured(repo) and _crossed_dawn(
        agenda, cursor, canonical
    ):
        light = agentes_leves.process_checkpoint(repo)

    events = {
        "ok": True,
        "configurado": False,
        "dias_processados": 0,
        "dias_rotina": 0,
        "eventos_sorteados": [],
        "novas_pendencias": [],
        "eventos_reconsiderar": [],
        "agentes_evento_reconsiderar": [],
        "agentes_leves_evento_reconsiderar": [],
        "fontes_lidas": [],
    }
    if eventos_mundo.configured(repo):
        events = {
            "configurado": True,
            **eventos_mundo.process_checkpoint(repo),
        }

    return {
        "ok": True,
        "ciclo_npcs": lifecycle,
        "eventos_limpeza_mortos": event_cleanup,
        "relogios": clocks,
        "eventos_mundo": events,
        "novas_pendencias": [
            *added,
            *(entry.get("novas_pendencias") or []),
            *(light.get("novas_pendencias") or []),
            *(events.get("novas_pendencias") or []),
        ],
        "direcoes_reconsiderar": sorted(
            {item["direcao"] for item in added}
        ),
        "entradas_reconsiderar": entry.get("entradas_reconsiderar") or [],
        "agentes_leves_reconsiderar": (
            light.get("agentes_leves_reconsiderar") or []
        ),
        "agentes_leves_adiados": light.get("adiados_por_orcamento") or [],
        "eventos_reconsiderar": events.get("eventos_reconsiderar") or [],
        "agentes_evento_reconsiderar": (
            events.get("agentes_evento_reconsiderar") or []
        ),
        "agentes_leves_evento_reconsiderar": (
            events.get("agentes_leves_evento_reconsiderar") or []
        ),
        "fontes_lidas": [
            *(lifecycle.get("fontes_lidas") or []),
            *(clocks.get("fontes_expostas") or []),
            direcoes.INDEX_PATH.as_posix(),
            direcoes.STATE_PATH.as_posix(),
            mundo.WORLD_STATE_PATH.as_posix(),
            mundo.AGENDA_PATH.as_posix(),
            mundo.TIME_PATH.as_posix(),
            *(entry.get("fontes_lidas") or []),
            *(light.get("fontes_lidas") or []),
            *(events.get("fontes_lidas") or []),
        ],
    }


def check_repo(repo: Path) -> dict[str, Any]:
    result = direcoes.validate_repo(repo)
    errors = list(result.get("erros") or [])
    try:
        if ciclo_npcs.configured(repo):
            errors.extend(
                f"ciclo de NPCs: {error}"
                for error in ciclo_npcs.validate_repo(repo).get("erros") or []
            )
        if relogios.configured(repo):
            errors.extend(
                f"relógios: {error}"
                for error in relogios.validate_repo(repo).get("erros") or []
            )
        if eventos_mundo.configured(repo):
            errors.extend(
                f"eventos: {error}"
                for error in eventos_mundo.validate_repo(repo).get("erros") or []
            )

        index = direcoes.load_index(repo)
        known = set(index["direcoes"])
        world_state = mundo.load_world_state(repo)
        for item in world_state.get("pendencias") or []:
            if (
                item.get("tipo") in {"avaliar_direcao", "ativar_direcao"}
                and item.get("direcao") not in known
            ):
                errors.append(
                    "pendência do mundo referencia direção inexistente: "
                    f"{item.get('direcao')}"
                )
        if _entries_configured(repo):
            errors.extend(
                f"entradas: {error}"
                for error in entradas.check_world(repo).get("erros") or []
            )
        if _light_agents_configured(repo):
            errors.extend(
                f"agentes leves: {error}"
                for error in agentes_leves.check_world(repo).get("erros") or []
            )
    except (
        agentes_leves.LightAgentError,
        ciclo_npcs.LifecycleError,
        direcoes.DirectionError,
        entradas.EntryError,
        eventos_mundo.WorldEventError,
        mundo.WorldEngineError,
        relogios.ClockError,
    ) as exc:
        errors.append(str(exc))
    return {"ok": not errors, "erros": list(dict.fromkeys(errors))}
