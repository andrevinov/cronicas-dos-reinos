#!/usr/bin/env python3
"""Compõe a fronteira já projetada com extensões determinísticas raras.

A Task 37 compara a próxima noite aceita do torneio com a fronteira base. A NV-14
é aplicada depois, sobre a faixa que realmente pode ser comprimida, para que a
mesma chamada ``endpoints.py fronteira`` consulte vivacidade sem criar um segundo
ritual. Nenhuma das extensões cria pendência de Mundo Vivo.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import fronteira_vivacidade
import mundo
import torneio_clandestino

LAYER = "torneio_clandestino"


def _instant(parts: Any) -> mundo.WorldInstant | None:
    if not isinstance(parts, dict):
        return None
    date = parts.get("data")
    hour = parts.get("hora")
    if not isinstance(date, str) or not isinstance(hour, str):
        return None
    return mundo.parse_instant(date, hour)


def _tournament_gate(round_id: str, delayed: bool) -> dict[str, Any]:
    return {
        "tipo": LAYER,
        "resultado": "rodada_devida",
        "ids": [round_id],
        "atrasada": delayed,
        "regra": "compromisso aceito por Ren; parar o tempo não decide comparecimento nem resultado",
    }


def _augment_tournament(
    repo: Path,
    projected: dict[str, Any],
    *,
    target_date: str,
    target_hour: str,
) -> dict[str, Any]:
    if not isinstance(projected, dict):
        return projected
    original_availability = projected.get("disponibilidade")
    if not isinstance(original_availability, dict):
        return projected
    start = _instant(original_availability.get("inicio"))
    if start is None:
        return projected
    target = mundo.parse_instant(target_date, target_hour)
    try:
        extra = torneio_clandestino.next_boundary(repo, start, target)
    except torneio_clandestino.TournamentError as exc:
        raise ValueError(str(exc)) from exc
    when = extra.get("quando")
    if not isinstance(when, mundo.WorldInstant):
        return projected

    result = copy.deepcopy(projected)
    availability = result["disponibilidade"]
    result["fontes_lidas"] = list(
        dict.fromkeys([*(result.get("fontes_lidas") or []), *(extra.get("fontes_lidas") or [])])
    )
    round_id = str(extra.get("rodada"))
    delayed = bool(extra.get("atrasada"))
    next_step = result.get("proximo_passo")
    if not isinstance(next_step, dict):
        next_step = {}
        result["proximo_passo"] = next_step
    existing = _instant(next_step.get("fronteira"))
    if existing is not None and existing.minute < when.minute:
        return result

    ids = result.setdefault("ids", {})
    grouped = ids.get("motivos_por_camada")
    if not isinstance(grouped, dict):
        grouped = {}
    if existing is None or when.minute < existing.minute:
        grouped = {LAYER: [round_id]}
        result["gates"] = [
            {
                "tipo": "fronteira_temporal",
                "resultado": "interromper",
                "minutos_ate_fronteira": max(0, when.minute - start.minute),
            },
            _tournament_gate(round_id, delayed),
        ]
    else:
        grouped[LAYER] = [round_id]
        gates = list(result.get("gates") or [])
        if not any(isinstance(item, dict) and item.get("tipo") == LAYER for item in gates):
            gates.append(_tournament_gate(round_id, delayed))
        result["gates"] = gates
    ids["motivos_por_camada"] = grouped
    ids[LAYER] = [round_id]
    filters = list(result.get("filtros") or [])
    if "compromisso_torneio_clandestino_task37" not in filters:
        filters.append("compromisso_torneio_clandestino_task37")
    result["filtros"] = filters
    availability["alvo_inteiro_sem_checkpoint"] = False
    next_step["acao"] = "resolver_ate_fronteira_e_checkpoint_antes_de_continuar"
    next_step["fronteira"] = mundo.instant_parts(when)
    next_step[LAYER] = (
        "pare no instante indicado; depois do checkpoint consulte `poetry run python ferramentas/torneio_clandestino.py rodada` "
        "para abrir somente o fragmento devido. Ren ainda pode comparecer, faltar ou abandonar."
    )
    return result


def augment_endpoint(
    repo: Path,
    projected: dict[str, Any],
    *,
    target_date: str,
    target_hour: str,
) -> dict[str, Any]:
    """Aplica torneio e depois NV-14 na mesma fronteira operacional."""
    tournament = _augment_tournament(
        repo,
        projected,
        target_date=target_date,
        target_hour=target_hour,
    )
    try:
        return fronteira_vivacidade.augment_endpoint(
            repo,
            tournament,
            target_date=target_date,
            target_hour=target_hour,
        )
    except fronteira_vivacidade.LivenessBoundaryError as exc:
        raise ValueError(str(exc)) from exc
