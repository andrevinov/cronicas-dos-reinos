#!/usr/bin/env python3
"""Fachada pública v2 da projeção espacial causal de uma cena.

A fachada compõe as portas existentes de cena e permanência. Incidentes,
microeventos e condições continuam produtores separados, com seus próprios
estados determinísticos; a RM-04 apenas lhes dá uma identidade modular única.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from _module_facade import attach_coverage, combine_checks
import cena_mundo as _scene
import condicoes_mundo as _conditions
import ecologia_local as _ecology
import incidentes_mundo as _incidents
import microeventos_locais as _microevents
import permanencia_espacial as spatial_permanence

FACADE_SCHEMA = 2
MODULE_ID = "scene_world_projection"
CAPABILITIES = ("local_incidents", "persistent_conditions", "spatial_continuity")
LEGACY_ALIASES = ("world_local_incidents", "persistent_world_conditions")
LEGACY_COMPONENTS = (
    "cena_mundo",
    "ecologia_local",
    "microeventos_locais",
    "incidentes_mundo",
    "condicoes_mundo",
    "permanencia_espacial",
)

SceneGateError = _scene.SceneGateError
SpatialPermanenceError = spatial_permanence.SpatialPermanenceError


def prepare_scene(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Projeta uma cena pelo compositor transacional existente, sem nova escrita."""

    result = _scene.prepare_scene(*args, **kwargs)
    return attach_coverage(
        result, module_id=MODULE_ID, phase="preparar", applicability="aplicavel"
    )


def confirm_scene(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Confirma exatamente a projeção revalidada pelo compositor existente."""

    result = _scene.confirm_scene(*args, **kwargs)
    return attach_coverage(
        result, module_id=MODULE_ID, phase="confirmar", applicability="aplicavel"
    )


def open_scene(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Mantém o alias legado de abertura sobre a mesma projeção."""

    result = _scene.open_scene(*args, **kwargs)
    return attach_coverage(
        result, module_id=MODULE_ID, phase="abrir", applicability="aplicavel"
    )


def prepare_permanence(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Reserva uma única identidade espacial por local, data e período."""

    result = spatial_permanence.prepare(*args, **kwargs)
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="permanencia",
        applicability="aplicavel",
    )


def check(repo: Path) -> dict[str, Any]:
    return combine_checks(
        repo,
        module_id=MODULE_ID,
        capabilities=CAPABILITIES,
        legacy_components=LEGACY_COMPONENTS,
        checks=(
            ("local_ecology", _ecology.check),
            ("local_microevents", _microevents.validate_repo),
            ("local_incidents", _incidents.check),
            ("persistent_conditions", _conditions.check),
        ),
        contract={
            "projection_modules_per_spatial_trigger": 1,
            "deterministic_reservation": True,
            "reroll_on_retry": False,
            "persistent_condition_implies_mechanical_effect": False,
            "additional_orchestration_calls": 0,
            "new_scheduler": False,
            "parallel_state": False,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("cmd", choices=["check"])
    args = parser.parse_args(argv)
    result = check(args.repo.resolve())
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
