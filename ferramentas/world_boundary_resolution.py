#!/usr/bin/env python3
"""Fachada pública v2 das fronteiras temporais e pendências do mundo.

Vivacidade permanece uma consulta read-only sobre compressão temporal. O lote
continua sendo o único materializador de pendências e conserva seus recibos de
idempotência. A fachada não cria causa, scheduler, fila ou writer.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from _module_facade import attach_coverage, combine_checks
import fronteira_torneio as _temporal_extensions
import fronteira_vivacidade as _liveness
import resolver_fronteira as _batch

FACADE_SCHEMA = 2
MODULE_ID = "world_boundary_resolution"
CAPABILITIES = ("temporal_liveness", "pending_batch_resolution")
LEGACY_ALIASES = ("liveness_boundary", "batch_world_boundary")
LEGACY_COMPONENTS = (
    "fronteira_mundo",
    "fronteira_vivacidade",
    "fronteira_torneio",
    "cronica_pending_gate",
    "barreira_mundo",
    "resolver_fronteira",
)

LivenessBoundaryError = _liveness.LivenessBoundaryError
BatchBoundaryError = _batch.BatchBoundaryError


def augment_endpoint(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Compõe a fronteira existente na mesma consulta operacional."""

    result = _temporal_extensions.augment_endpoint(*args, **kwargs)
    return attach_coverage(
        result, module_id=MODULE_ID, phase="fronteira", applicability="aplicavel"
    )


def evaluate(*args: Any, **kwargs: Any) -> dict[str, Any]:
    result = _liveness.evaluate(*args, **kwargs)
    return attach_coverage(
        result, module_id=MODULE_ID, phase="fronteira", applicability="aplicavel"
    )


def query(*args: Any, **kwargs: Any) -> dict[str, Any]:
    result = _liveness.query(*args, **kwargs)
    return attach_coverage(
        result, module_id=MODULE_ID, phase="fronteira", applicability="aplicavel"
    )


def prepare_batch(repo: Path) -> dict[str, Any]:
    result = _batch.prepare_batch(repo)
    result = {
        **result,
        "schema_world_boundary_resolution": FACADE_SCHEMA,
        "module_id": MODULE_ID,
        "resultado_modular": (
            "pendencias_projetadas" if result.get("quantidade") else "sem_pendencias"
        ),
        "efeito_materializado": False,
    }
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="preparar_lote",
        applicability=("aplicavel" if result.get("quantidade") else "nao_aplicavel"),
    )


def apply_batch(repo: Path, payload: Any) -> dict[str, Any]:
    result = _batch.apply_batch(repo, payload)
    neutral_closures = list(result.get("aplicadas") or [])
    materialized = bool(result.get("grupos_comprometidos")) or (
        result.get("planos_aplicados") is not None
    )
    if materialized:
        outcome = "lote_aplicado"
    elif neutral_closures:
        outcome = "gate_neutro_aplicado"
    else:
        outcome = "retry_sem_duplicacao"
    result = {
        **result,
        "schema_world_boundary_resolution": FACADE_SCHEMA,
        "module_id": MODULE_ID,
        "resultado_modular": outcome,
        "efeito_materializado": materialized,
    }
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="aplicar_lote",
        applicability="aplicavel" if materialized or neutral_closures else "nao_aplicavel",
    )


def _check_liveness(_: Path) -> dict[str, Any]:
    window = {
        "gatilho": "compressao_longa",
        "inicio": {"data": "1 Eleasis, 1372 DR", "hora": "06:00"},
        "fim": {"data": "1 Eleasis, 1372 DR", "hora": "10:00"},
    }
    checks = [
        {
            "dominio": domain,
            "estado": "consultado",
            "fontes": [f"fixture/{domain}.yaml"],
        }
        for domain in _liveness.REQUIRED_DOMAINS
    ]
    result = _liveness.project(window, [], checks)
    metrics = result.get("metricas") or {}
    errors: list[str] = []
    if result.get("recibo_calma", {}).get("estado") != "calma_justificada":
        errors.append("ausência de causa não produziu calma justificada")
    if any(metrics.get(key) for key in ("rng_novo", "scheduler_novo", "scan_global")):
        errors.append("fronteira neutra introduziu trabalho proibido")
    return {"ok": not errors, "erros": errors, "projecao": result}


def check(repo: Path) -> dict[str, Any]:
    return combine_checks(
        repo,
        module_id=MODULE_ID,
        capabilities=CAPABILITIES,
        legacy_components=LEGACY_COMPONENTS,
        checks=(
            ("temporal_liveness", _check_liveness),
            ("pending_batch_resolution", _batch.check),
        ),
        contract={
            "short_turn_queries_temporal_boundary": False,
            "calm_requires_complete_coverage": True,
            "canonical_due_event_allows_noop": False,
            "retry_redraws_or_duplicates": False,
            "additional_orchestration_calls": 0,
            "new_scheduler": False,
            "parallel_state": False,
        },
    )


def _read_stdin() -> Any:
    raw = sys.stdin.read()
    if not raw.strip():
        raise BatchBoundaryError("aplicar exige JSON/YAML por stdin")
    return yaml.safe_load(raw)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    frontier = sub.add_parser("fronteira")
    frontier.add_argument("--data", required=True)
    frontier.add_argument("--hora", required=True)
    sub.add_parser("preparar")
    sub.add_parser("aplicar")
    sub.add_parser("check")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "fronteira":
            result = query(repo, args.data, args.hora)
        elif args.cmd == "preparar":
            result = prepare_batch(repo)
        elif args.cmd == "aplicar":
            result = apply_batch(repo, _read_stdin())
        else:
            result = check(repo)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
