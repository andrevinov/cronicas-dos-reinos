#!/usr/bin/env python3
"""Fachada pública v2 do roteamento de matérias narrativas causais.

O módulo recebe somente matérias que outro domínio já autorizou. Ele ordena
evento canônico datado, pressão comprometida e matéria incidental sem abrir
fonte reservada, produzir evento ou executar o efeito selecionado.
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from typing import Any

import yaml

from _module_facade import attach_coverage, combine_checks
import eventos_canonicos as _canonical
import pressao_narrativa as _pressure

FACADE_SCHEMA = 2
MODULE_ID = "causal_narrative_routing"
CAPABILITIES = ("reactive_pressure_arbitration", "dated_secret_canon")
LEGACY_ALIASES = ("reactive_pressure_routing", "secret_canon")
LEGACY_COMPONENTS = ("pressao_narrativa", "eventos_canonicos")
MAX_AUTHORIZED_MATTERS = _pressure.MAX_ITEMS
DATED_CANON_KIND = "evento_canonico_datado"

# Compatibilidade do ticket já persistido da pressão narrativa. A fachada não
# cria outro envelope ou writer.
SCHEMA = _pressure.SCHEMA
TICKET_KEY = _pressure.TICKET_KEY
TRANSACTION_KEY = _pressure.TRANSACTION_KEY
OPERATION_PENDING_TYPE = _pressure.OPERATION_PENDING_TYPE
RESULTS = _pressure.RESULTS
MAX_ITEMS = _pressure.MAX_ITEMS
MAX_OUTPUT_BYTES = _pressure.MAX_OUTPUT_BYTES
MAX_TICKET_ITEMS = _pressure.MAX_TICKET_ITEMS
PRIORITIES = _pressure.PRIORITIES
NarrativePressureError = _pressure.NarrativePressureError
CanonicalEventError = _canonical.CanonicalEventError

routable_operation_pendings = _pressure.routable_operation_pendings
ticket_meta = _pressure.ticket_meta
strip_ticket_payload = _pressure.strip_ticket_payload
prepare_conclusion = _pressure.prepare_conclusion
writer_transaction = _pressure.writer_transaction
authorize_registration = _pressure.authorize_registration
project_social_pressure = _pressure.project_social_pressure
authorize_censorship_topic = _pressure.authorize_censorship_topic
sort_items = _pressure.sort_items

event_for_pending = _canonical.event_for_pending
pending_projection = _canonical.pending_projection
load_catalog = _canonical.load_catalog
load_event = _canonical.load_event


def integrate_prepare(*args: Any, **kwargs: Any) -> dict[str, Any]:
    result = _pressure.integrate_prepare(*args, **kwargs)
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="preparar",
        applicability=(
            "aplicavel" if result.get("pressao_narrativa") is not None
            else "nao_aplicavel"
        ),
    )


def install_conclusion(*args: Any, **kwargs: Any) -> dict[str, Any] | None:
    result = _pressure.install_conclusion(*args, **kwargs)
    if result is None:
        return None
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="concluir",
        applicability="aplicavel",
    )


class CausalNarrativeRoutingError(ValueError):
    """Matéria não autorizada ou contrato agregado inválido."""


def _text(value: Any, label: str, maximum: int = 180) -> str:
    if not isinstance(value, str):
        raise CausalNarrativeRoutingError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if not result or len(result) > maximum:
        raise CausalNarrativeRoutingError(
            f"{label} deve ser texto não vazio de até {maximum} caracteres"
        )
    return result


def route_authorized(matters: list[dict[str, Any]]) -> dict[str, Any]:
    """Ordena matérias autorizadas sem consultar produtor ou executar domínio."""

    if not isinstance(matters, list) or len(matters) > MAX_AUTHORIZED_MATTERS:
        raise CausalNarrativeRoutingError(
            f"materias deve ser lista de até {MAX_AUTHORIZED_MATTERS} itens"
        )
    ordered: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(matters):
        if not isinstance(raw, dict):
            raise CausalNarrativeRoutingError(f"materias[{index}] deve ser mapa")
        if raw.get("autorizada") is not True:
            raise CausalNarrativeRoutingError(
                f"materias[{index}] não possui autorização causal explícita"
            )
        matter = copy.deepcopy(raw)
        matter_id = _text(matter.get("id"), f"materias[{index}].id", 96)
        if matter_id in seen:
            raise CausalNarrativeRoutingError(f"matéria duplicada: {matter_id}")
        seen.add(matter_id)
        kind = _text(matter.get("tipo"), f"materias[{index}].tipo", 64)
        source = _text(
            matter.get("fonte_causal"), f"materias[{index}].fonte_causal", 180
        )
        if kind == DATED_CANON_KIND:
            priority = 0
        elif kind in PRIORITIES:
            priority = int(PRIORITIES[kind])
        else:
            raise CausalNarrativeRoutingError(
                f"tipo de matéria causal desconhecido: {kind}"
            )
        matter["id"] = matter_id
        matter["tipo"] = kind
        matter["fonte_causal"] = source
        matter["prioridade"] = priority
        ordered.append(matter)

    ordered.sort(key=lambda item: (item["prioridade"], item["id"]))
    primary = ordered[0] if ordered else None
    if primary is None:
        result = "sem_materia"
    elif primary["tipo"] == DATED_CANON_KIND:
        result = "evento_canonico_datado"
    else:
        result = "materia_selecionada"
    result = {
        "schema_causal_narrative_routing": FACADE_SCHEMA,
        "module_id": MODULE_ID,
        "resultado_modular": result,
        "efeito_materializado": False,
        "materia_primaria": primary,
        "materias_adiadas": ordered[1:],
        "metricas": {
            "candidatas_autorizadas": len(ordered),
            "fontes_abertas_pelo_roteador": 0,
            "scheduler_novo": 0,
            "produtor_novo": 0,
        },
    }
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="rotear",
        applicability="aplicavel" if ordered else "nao_aplicavel",
    )


def check(repo: Path) -> dict[str, Any]:
    return combine_checks(
        repo,
        module_id=MODULE_ID,
        capabilities=CAPABILITIES,
        legacy_components=LEGACY_COMPONENTS,
        checks=(
            ("reactive_pressure_arbitration", _pressure.check),
            ("dated_secret_canon", _canonical.validate),
        ),
        contract={
            "accepts_only_authorized_matters": True,
            "dated_canonical_event_allows_noop": False,
            "committed_pressure_precedes_incidental_matter": True,
            "opens_reserved_sources_while_routing": False,
            "new_scheduler": False,
            "universal_producer": False,
        },
    )


def _read_matters() -> list[dict[str, Any]]:
    raw = sys.stdin.read()
    if not raw.strip():
        raise CausalNarrativeRoutingError("rotear exige lista JSON/YAML por stdin")
    value = yaml.safe_load(raw)
    if not isinstance(value, list):
        raise CausalNarrativeRoutingError("rotear exige lista JSON/YAML")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("cmd", choices=["rotear", "check"])
    args = parser.parse_args(argv)
    try:
        result = (
            route_authorized(_read_matters())
            if args.cmd == "rotear"
            else check(args.repo.resolve())
        )
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    raise SystemExit(main())
