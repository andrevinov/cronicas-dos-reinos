#!/usr/bin/env python3
"""Integra o convite da Task 37 à cena já existente, sem presença automática.

Somente um encontro explicitamente resolvido como ``luath`` consulta o gate do
mini-arco. NPC incidental, tag, local ou turno neutro nunca abrem o torneio.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import cena_mundo_v4 as _v4
import torneio_clandestino

_core = _v4._core
_BASE_OPEN_SCENE: Callable[..., dict[str, Any]] | None = None
_INSTALLED = False


def open_scene(
    repo: Path,
    *,
    scene_id: str,
    npcs: list[str] | None = None,
    place: str | None = None,
    action: str | None = None,
    tier: int | None = None,
    danger: str | None = None,
    context_tags: list[str] | None = None,
    now: _core.mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    if _BASE_OPEN_SCENE is None:
        raise _core.SceneGateError("integracao do torneio clandestino nao instalada")
    result = _BASE_OPEN_SCENE(
        repo,
        scene_id=scene_id,
        npcs=npcs,
        place=place,
        action=action,
        tier=tier,
        danger=danger,
        context_tags=context_tags,
        now=now,
    )
    if not (repo / torneio_clandestino.INDEX).is_file() or not (repo / torneio_clandestino.STATE).is_file():
        return result
    if "luath" not in set(result.get("npcs_canonicos") or []):
        return result
    try:
        candidate = torneio_clandestino.invitation_candidate(repo, now=now)
    except torneio_clandestino.TournamentError as exc:
        raise _core.SceneGateError(str(exc)) from exc
    result["fontes_lidas"] = list(
        dict.fromkeys([*(result.get("fontes_lidas") or []), *(candidate.get("fontes_lidas") or [])])
    )
    if not candidate.get("disponivel"):
        return result
    result["torneio_clandestino"] = candidate
    summary = dict(result.get("resumo") or {})
    summary["convites_miniarco_para_avaliar"] = 1
    result["resumo"] = summary
    result["regra"] = (
        str(result.get("regra") or "").rstrip()
        + " Convite do torneio e apenas possibilidade de fala de Luath: Ren pode recusar, escolher identidade e nunca recebe resultado de luta por decreto."
    )
    return result


def install() -> None:
    global _INSTALLED, _BASE_OPEN_SCENE
    if _INSTALLED:
        return
    _BASE_OPEN_SCENE = _v4.open_scene
    _core.open_scene = open_scene
    _v4.open_scene = open_scene
    _INSTALLED = True
