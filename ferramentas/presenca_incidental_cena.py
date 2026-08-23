#!/usr/bin/env python3
"""Adaptador read-only de presença incidental sobre ``cena_mundo_v4``.

A Task 16 não cria nova versão da cena. Este módulo envolve apenas ``open_scene``
e reinstala essa porta nos dois namespaces que a preparação/confirmação v4 já
usam, preservando as primitivas transacionais existentes.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import cena_mundo_v4 as _v4
import presenca_incidental

_core = _v4._core
_BASE_OPEN_SCENE = _v4.open_scene
_INSTALLED = False


def _ids(items: list[Any]) -> set[str]:
    result: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            value = item.get("id")
            if isinstance(value, str) and value:
                result.add(value)
    return result


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

    if not presenca_incidental.configured(repo):
        return result
    local = result.get("local")
    if not isinstance(local, dict) or not isinstance(local.get("ecologia"), dict):
        return result

    existing_presence = list(result.get("presencas_contextuais") or [])
    existing_candidates = list(result.get("candidatos_contextuais") or [])
    remaining_presence = max(
        0,
        _core.contexto_cena.MAX_PRESENCE_CANDIDATES - len(existing_presence),
    )
    remaining_total = max(
        0,
        _core.contexto_cena.MAX_CONTEXT_CANDIDATES - len(existing_candidates),
    )
    limit = min(
        presenca_incidental.MAX_CANDIDATES,
        remaining_presence,
        remaining_total,
    )

    # Incidental é sempre subordinado ao roteador contextual já existente.
    if limit <= 0:
        return result

    excluded = set(result.get("npcs_canonicos") or []) | _ids(existing_presence)
    try:
        selection = presenca_incidental.select(
            repo,
            scene_id=scene_id,
            local_id=str(local["local_id"]),
            ecology=local["ecologia"],
            now=now,
            exclude_ids=excluded,
            limit=limit,
        )
    except presenca_incidental.IncidentalPresenceError as exc:
        raise _core.SceneGateError(str(exc)) from exc

    # Fonte/configuração e relógio consultados participam do fingerprint mesmo
    # quando a janela produz zero candidatos.
    result["fontes_lidas"] = list(
        dict.fromkeys(
            [
                *(result.get("fontes_lidas") or []),
                *(selection.get("fontes_lidas") or []),
            ]
        )
    )
    selected = list(selection.get("candidatos") or [])
    if not selected:
        return result

    result["presencas_incidentais"] = selected
    result["presencas_contextuais"] = [*existing_presence, *selected]
    result["candidatos_contextuais"] = [*existing_candidates, *selected]

    summary = dict(result.get("resumo") or {})
    summary["presencas_incidentais_para_avaliar"] = len(selected)
    summary["presencas_contextuais"] = len(result["presencas_contextuais"])
    summary["candidatos_contextuais"] = len(result["candidatos_contextuais"])
    result["resumo"] = summary
    result["regra"] = (
        str(result.get("regra") or "").rstrip()
        + " Presença incidental é coincidência determinística de rotina e entra depois dos candidatos "
        "contextuais anteriores; exige avaliação contra cânone forte e nunca estabelece presença, ação, "
        "diálogo, conhecimento, encontro ou sidequest."
    )
    return result


def install() -> None:
    """Instala o adaptador sem alterar ``prepare_scene`` ou ``confirm_scene``."""
    global _INSTALLED
    if _INSTALLED:
        return
    _core.open_scene = open_scene
    _v4.open_scene = open_scene
    _INSTALLED = True
