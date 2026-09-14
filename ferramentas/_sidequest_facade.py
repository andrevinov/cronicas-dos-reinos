#!/usr/bin/env python3
"""Primitivas compartilhadas pelas fachadas modulares de sidequest."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml


CheckCall = tuple[str, Callable[[Path], dict[str, Any]]]


def combine_checks(
    repo: Path,
    *,
    module_id: str,
    capabilities: Iterable[str],
    legacy_components: Iterable[str],
    checks: Iterable[CheckCall],
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Executa validadores read-only e mantém a autoria de cada diagnóstico."""

    components: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for component_id, check in checks:
        try:
            raw = check(Path(repo))
            result = copy.deepcopy(raw) if isinstance(raw, dict) else {
                "ok": False,
                "erros": ["check não retornou mapa"],
            }
        except (OSError, ValueError, yaml.YAMLError) as exc:
            result = {"ok": False, "erros": [str(exc)]}
        components[component_id] = result
        if result.get("ok") is not True:
            component_errors = result.get("erros") or ["check retornou falha sem detalhe"]
            errors.extend(f"{component_id}: {error}" for error in component_errors)

    return {
        "schema_fachada_modular": 2,
        "module_id": module_id,
        "ok": not errors,
        "erros": errors,
        "subcapacidades": list(capabilities),
        "componentes_legados_internos": list(legacy_components),
        "componentes": components,
        "contrato": copy.deepcopy(contract),
    }

