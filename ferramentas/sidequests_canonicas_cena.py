#!/usr/bin/env python3
"""Integra Side Quest Engine canônico à mesma cena transacional.

A camada só roda quando um encontro explícito já trouxe referências opacas do
roteador da Task 32. Presença incidental nunca fornece essas referências e,
portanto, nunca cria sidequest por coincidência espacial.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import cena_mundo_v4 as _v4
import sidequests_canonicas

_core = _v4._core
_BASE_OPEN_SCENE: Callable[..., dict[str, Any]] | None = None
_INSTALLED = False


def _collect_refs(result: dict[str, Any]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    for encounter in list(result.get("encontros") or []):
        if not isinstance(encounter, dict):
            continue
        raw = encounter.pop("_sidequest_canonica_refs", None)
        if not isinstance(raw, list):
            continue
        refs.extend(item for item in raw if isinstance(item, dict))
    return refs


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
        raise _core.SceneGateError("integração de sidequest canônica não instalada")
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
    refs = _collect_refs(result)
    if not refs:
        return result

    local_id = None
    local = result.get("local")
    if isinstance(local, dict) and isinstance(local.get("local_id"), str):
        local_id = local["local_id"]
    try:
        selection = sidequests_canonicas.select_from_refs(
            repo,
            refs,
            local_id=local_id,
            now=now,
        )
    except sidequests_canonicas.CanonicalSidequestError as exc:
        raise _core.SceneGateError(str(exc)) from exc

    # Tudo que foi realmente lido entra no fingerprint transacional, mesmo quando
    # nenhum gate passa. O detalhe só aparece nesta lista quando foi aberto.
    result["fontes_lidas"] = list(
        dict.fromkeys(
            [
                *(result.get("fontes_lidas") or []),
                *(selection.get("fontes_lidas") or []),
            ]
        )
    )
    if selection.get("resultado") != "sidequest_canonica_disponivel":
        return result

    result["sidequest_canonica"] = selection["sidequest"]
    summary = dict(result.get("resumo") or {})
    summary["sidequests_canonicas_disponiveis"] = 1
    result["resumo"] = summary
    result["regra"] = (
        str(result.get("regra") or "").rstrip()
        + " Sidequest canônica disponível não é oferta automática nem aceite: "
        "o NPC pode formular o pedido organicamente, e Ren controla aceitar, adiar ou recusar."
    )
    return result


def install() -> None:
    """Envolve a porta que já estiver instalada, inclusive presença incidental."""
    global _INSTALLED, _BASE_OPEN_SCENE
    if _INSTALLED:
        return
    _BASE_OPEN_SCENE = _v4.open_scene
    _core.open_scene = open_scene
    _v4.open_scene = open_scene
    _INSTALLED = True
