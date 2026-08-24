#!/usr/bin/env python3
"""Integra Task 35 à cena reativa depois das condições persistentes.

Reutiliza local canônico, ecologia e condições já projetadas. Preparação sombreia
a escrita do baralho; confirmação revalida a cena inteira e só então consome o
estado. Cena sem contexto espacial continua sem ler a camada.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

import cena_mundo_v4 as _v4
import condicoes_mundo_cena
import ecologia_local
import incidentes_mundo

_core = _v4._core
_BASE_OPEN_SCENE: Callable[..., dict[str, Any]] | None = None
_BASE_PREVIEW: Callable[[Path], Any] | None = None
_INSTALLED = False


@contextmanager
def _preview_effects(repo: Path) -> Iterator[None]:
    if _BASE_PREVIEW is None:
        raise _core.SceneGateError("preview de incidentes não instalado")
    original = incidentes_mundo.atomic
    incidentes_mundo.atomic = lambda _path, _data: None
    try:
        with _BASE_PREVIEW(repo):
            yield
    finally:
        incidentes_mundo.atomic = original


def _profile(repo: Path, result: dict[str, Any], local_id: str) -> tuple[dict[str, Any], list[str]]:
    local = result.get("local")
    if isinstance(local, dict) and isinstance(local.get("ecologia"), dict):
        return local["ecologia"], []
    try:
        lookup = ecologia_local.lookup_canonical(repo, local_id)
    except ecologia_local.LocalEcologyError as exc:
        raise _core.SceneGateError(str(exc)) from exc
    return lookup["perfil"], lookup["fontes_lidas"]


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
        raise _core.SceneGateError("integração de incidentes não instalada")
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
    layer_dir = repo / incidentes_mundo.INDEX.parent
    if not layer_dir.exists():
        return result
    if not incidentes_mundo.configured(repo):
        raise _core.SceneGateError("camada de incidentes declarada parcialmente")

    local_id = condicoes_mundo_cena._local_id(repo, result)
    if local_id is None:
        return result
    profile, extra_sources = _profile(repo, result, local_id)
    conditions = result.get("condicoes_mundo")
    if not isinstance(conditions, list):
        conditions = []
    try:
        planned = incidentes_mundo.plan(
            repo,
            scene_id=scene_id,
            local_id=local_id,
            profile=profile,
            conditions=conditions,
        )
    except incidentes_mundo.IncidentError as exc:
        raise _core.SceneGateError(str(exc)) from exc

    public = planned["publico"]
    result["fontes_lidas"] = list(
        dict.fromkeys(
            [
                *(result.get("fontes_lidas") or []),
                *extra_sources,
                *(public.get("fontes_lidas") or []),
            ]
        )
    )
    summary = dict(result.get("resumo") or {})
    summary["incidentes_para_avaliar"] = 1 if public.get("resultado") == "avaliar_incidente" else 0
    result["resumo"] = summary
    if public.get("resultado") == "avaliar_incidente":
        result["incidente_mundo"] = public
        result["regra"] = (
            str(result.get("regra") or "").rstrip()
            + " Incidente sério é candidato, não fato: apresente situação e saídas observáveis; "
            "não converta automaticamente em side quest, recompensa, segredo ou ação de Ren."
        )
    try:
        incidentes_mundo.commit_plan(repo, planned)
    except incidentes_mundo.IncidentError as exc:
        raise _core.SceneGateError(str(exc)) from exc
    return result


def install() -> None:
    global _INSTALLED, _BASE_OPEN_SCENE, _BASE_PREVIEW
    if _INSTALLED:
        return
    _BASE_OPEN_SCENE = _v4.open_scene
    _BASE_PREVIEW = _core._preview_effects
    _core._preview_effects = _preview_effects
    _v4._preview_effects = _preview_effects
    _core.open_scene = open_scene
    _v4.open_scene = open_scene
    _INSTALLED = True
