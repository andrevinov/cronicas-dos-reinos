#!/usr/bin/env python3
"""Extensão da cena v4 com candidatos determinísticos de presença incidental."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import cena_mundo_v4 as _v4
import presenca_incidental

# Reexporta integralmente a v4; esta camada só acrescenta uma avaliação read-only
# depois que local, ecologia e candidatos contextuais anteriores já foram resolvidos.
for _name in dir(_v4):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_v4, _name)

_core = _v4._core
_base_open_scene = _v4.open_scene


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
    result = _base_open_scene(
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

    # Fixtures legados e cenas sem local continuam byte-logicamente na v4: a
    # camada só existe quando sua configuração está presente e a cena já possui
    # local canônico com ecologia validada pela Task 11.
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

    # Presença incidental jamais desloca candidato estratégico/contextual. Se os
    # tetos anteriores já foram consumidos, nem sequer lê o roteador incidental.
    if limit <= 0:
        return result

    excluded = set(result.get("npcs_canonicos") or []) | _ids(existing_presence)
    try:
        incidental = presenca_incidental.select(
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

    # Mesmo um resultado vazio participa do fingerprint: mudar o roteador ou o
    # relógio entre preparar/confirmar pode tornar uma coincidência elegível.
    result["fontes_lidas"] = list(
        dict.fromkeys(
            [
                *(result.get("fontes_lidas") or []),
                *(incidental.get("fontes_lidas") or []),
            ]
        )
    )
    selected = list(incidental.get("candidatos") or [])
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


# prepare_scene vive no core e resolve open_scene no namespace do core. Já o
# confirm_scene da v4 resolve open_scene no namespace da própria v4. Redirecionar
# os dois preserva a transação existente sem duplicar preparação/confirmação.
_core.open_scene = open_scene
_v4.open_scene = open_scene

prepare_scene = _core.prepare_scene
confirm_scene = _v4.confirm_scene
build_parser = _v4.build_parser
main = _v4.main

if __name__ == "__main__":
    raise SystemExit(main())
