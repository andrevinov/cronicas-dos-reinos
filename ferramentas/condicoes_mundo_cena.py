#!/usr/bin/env python3
"""Projeta condições persistentes na mesma cena reativa, sem novo motor.

A camada só lê o estado compacto da Task 34 quando a cena já possui um local
canônico explícito (gatilho local ou tag `local:`) **e** o repo declara a camada.
Fixtures/instalações legadas sem o arquivo preservam o fluxo anterior. Cenas
somente-NPC continuam com zero leitura Task34. Condição é contexto observável;
nunca cria evento, rolagem, penalidade ou presença automaticamente.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import cena_mundo_v4 as _v4
import condicoes_mundo

_core = _v4._core
_BASE_OPEN_SCENE: Callable[..., dict[str, Any]] | None = None
_INSTALLED = False


def _local_id(result: dict[str, Any]) -> str | None:
    local = result.get("local")
    if isinstance(local, dict) and isinstance(local.get("local_id"), str):
        return local["local_id"]
    found: list[str] = []
    for tag in result.get("contexto_tags") or []:
        if not isinstance(tag, str) or not tag.startswith("local:"):
            continue
        value = tag.split(":", 1)[1].strip()
        if value:
            found.append(value)
    unique = list(dict.fromkeys(found))
    return unique[0] if len(unique) == 1 else None


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
        raise _core.SceneGateError("integração de condições persistentes não instalada")
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
    local_id = _local_id(result)
    if local_id is None or not (repo / condicoes_mundo.STATE).is_file():
        return result
    try:
        projection = condicoes_mundo.for_scene(repo, local_id, now=now)
    except condicoes_mundo.WorldConditionError as exc:
        raise _core.SceneGateError(str(exc)) from exc
    result["fontes_lidas"] = list(
        dict.fromkeys([*(result.get("fontes_lidas") or []), *(projection.get("fontes_lidas") or [])])
    )
    active = projection.get("ativas") or []
    if not active:
        return result
    result["condicoes_mundo"] = active
    summary = dict(result.get("resumo") or {})
    summary["condicoes_persistentes_ativas"] = len(active)
    result["resumo"] = summary
    result["regra"] = (
        str(result.get("regra") or "").rstrip()
        + " Condições persistentes descrevem o ambiente social/físico atual; "
        "não impõem teste, penalidade, evento ou ação sem regra/cânone específico."
    )
    return result


def install() -> None:
    """Envolve a porta já instalada, inclusive presença e sidequests canônicas."""
    global _INSTALLED, _BASE_OPEN_SCENE
    if _INSTALLED:
        return
    _BASE_OPEN_SCENE = _v4.open_scene
    _core.open_scene = open_scene
    _v4.open_scene = open_scene
    _INSTALLED = True
