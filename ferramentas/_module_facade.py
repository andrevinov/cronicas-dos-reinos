#!/usr/bin/env python3
"""Agregação read-only compartilhada pelas fachadas modulares v2."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable, Iterable

import yaml


CheckCall = tuple[str, Callable[[Path], dict[str, Any]]]

COVERAGE_SCHEMA = 1
COVERAGE_KEY = "cobertura_avaliacao_modular"
COVERAGE_SCHEMA_KEY = "schema_avaliacao_cobertura_modular"
COVERAGE_APPLICABILITY = frozenset(
    {"aplicavel", "nao_aplicavel", "indeterminado"}
)


def attach_coverage(
    result: dict[str, Any],
    *,
    module_id: str,
    phase: str,
    applicability: str,
    units: int = 1,
) -> dict[str, Any]:
    """Anexa um recibo compacto, explícito e avaliável sem abrir outra fonte.

    O recibo prova que a fronteira do módulo foi de fato atravessada. Ele não
    substitui recibos semânticos específicos: ``aplicavel`` ainda precisa ser
    corroborado pelo evento do próprio módulo para produzir pontuação.
    """

    if not isinstance(result, dict):
        raise ValueError("resultado modular precisa ser mapa")
    if not module_id or "|" in module_id:
        raise ValueError("module_id de cobertura inválido")
    if not phase or "|" in phase:
        raise ValueError("fase de cobertura inválida")
    if applicability not in COVERAGE_APPLICABILITY:
        raise ValueError("aplicabilidade de cobertura inválida")
    if not isinstance(units, int) or isinstance(units, bool) or units < 1:
        raise ValueError("unidades de cobertura devem ser inteiro positivo")

    block = result.setdefault(
        COVERAGE_KEY,
        {COVERAGE_SCHEMA_KEY: COVERAGE_SCHEMA, "recibos": []},
    )
    if not isinstance(block, dict):
        raise ValueError("bloco de cobertura modular inválido")
    if block.get(COVERAGE_SCHEMA_KEY) != COVERAGE_SCHEMA:
        raise ValueError("schema de cobertura modular incompatível")
    receipts = block.setdefault("recibos", [])
    if not isinstance(receipts, list):
        raise ValueError("recibos de cobertura modular precisam ser lista")
    prefix = f"{module_id}|{phase}|"
    receipts[:] = [
        item for item in receipts
        if not (isinstance(item, str) and item.startswith(prefix))
    ]
    receipts.append(f"{module_id}|{phase}|{applicability}|{units}")
    return result


def combine_checks(
    repo: Path,
    *,
    module_id: str,
    capabilities: Iterable[str],
    legacy_components: Iterable[str],
    checks: Iterable[CheckCall],
    contract: dict[str, Any],
) -> dict[str, Any]:
    """Executa validadores internos sem apagar a autoria de seus diagnósticos."""

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
            component_errors = result.get("erros") or [
                "check retornou falha sem detalhe"
            ]
            errors.extend(
                f"{component_id}: {error}" for error in component_errors
            )

    published_contract = copy.deepcopy(contract)
    published_contract["cobertura_avaliativa"] = {
        "schema": COVERAGE_SCHEMA,
        "recibo_ausente": "falha_instrumentacao",
        "recibo_incompleto": "falha_instrumentacao",
        "nd_somente_sem_atividade_esperada": True,
        "pontuacao_exige_aplicabilidade_e_evidencia": True,
    }
    return {
        "schema_fachada_modular": 2,
        "module_id": module_id,
        "ok": not errors,
        "erros": errors,
        "subcapacidades": list(capabilities),
        "componentes_legados_internos": list(legacy_components),
        "componentes": components,
        "contrato": published_contract,
    }
