#!/usr/bin/env python3
"""Compoe a fronteira temporal existente com compromissos do torneio ativo.

Nao cria pendencia de Mundo Vivo: uma luta aceita envolve acao potencial de Ren e
nao pertence a barreira de resolucao autonoma. A fronteira apenas impede que uma
compressao de tempo atravesse a noite marcada silenciosamente.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import fronteira_mundo
import mundo
import torneio_clandestino

LAYER = "torneio_clandestino"


def _instant(parts: dict[str, Any]) -> mundo.WorldInstant:
    return mundo.parse_instant(str(parts["data"]), str(parts["hora"]))


def next_boundary(repo: Path, target: mundo.WorldInstant) -> dict[str, Any]:
    base = fronteira_mundo.next_boundary(repo, target)
    start = _instant(base["inicio"])
    try:
        extra = torneio_clandestino.next_boundary(repo, start, target)
    except torneio_clandestino.TournamentError as exc:
        raise fronteira_mundo.BoundaryError(str(exc)) from exc
    sources = list(dict.fromkeys([*(base.get("fontes_lidas") or []), *(extra.get("fontes_lidas") or [])]))
    when = extra.get("quando")
    if not isinstance(when, mundo.WorldInstant):
        base["fontes_lidas"] = sources
        return base

    reason = {"camada": LAYER, "ids": [str(extra["rodada"])]}
    if extra.get("atrasada"):
        reason["atrasada"] = True

    current = base.get("fronteira")
    if not base.get("interromper") or not isinstance(current, dict):
        return {
            **base,
            "interromper": True,
            "fronteira": {
                **mundo.instant_parts(when),
                "minutos_ate_fronteira": max(0, when.minute - start.minute),
                "motivos": [reason],
            },
            "fontes_lidas": sources,
        }

    existing = _instant(current)
    if when < existing:
        return {
            **base,
            "interromper": True,
            "fronteira": {
                **mundo.instant_parts(when),
                "minutos_ate_fronteira": max(0, when.minute - start.minute),
                "motivos": [reason],
            },
            "fontes_lidas": sources,
        }
    if when == existing:
        merged = [*(current.get("motivos") or []), reason]
        current = {**current, "motivos": merged}
        return {**base, "fronteira": current, "fontes_lidas": sources}
    base["fontes_lidas"] = sources
    return base


def query(repo: Path, date: str, hour: str) -> dict[str, Any]:
    return next_boundary(repo, mundo.parse_instant(date, hour))
