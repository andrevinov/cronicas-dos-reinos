#!/usr/bin/env python3
"""Transações até NV-20 + contrato atômico de política cívica NV-22.

A implementação pública anterior fica congelada em ``_transacoes_nv20.py``.
A NV-22 só intercepta ``estado.politica_civica`` e recibos públicos que apontam
para suas publicações, preservando todo o writer e os contratos anteriores.
"""
from __future__ import annotations

from pathlib import Path

_LEGACY_SOURCE = Path(__file__).with_name("_transacoes_nv20.py")
_saved_name = globals().get("__name__", "transacoes")
globals()["__name__"] = "_transacoes_nv20_exec"
exec(compile(_LEGACY_SOURCE.read_text(encoding="utf-8"), str(_LEGACY_SOURCE), "exec"), globals(), globals())
globals()["__name__"] = _saved_name

import politica_civica as _civic

_BASE_VALIDATE_DELTA_NV20 = validate_delta
_BASE_VALIDATE_PENDING_NV20 = validate_pending_record


def _civic_config():
    repo = Path(__file__).resolve().parents[1]
    registry = _civic.load_registry(repo)
    return registry, _civic.load_catalog(repo, registry)


def _civic_relevant(deltas):
    return any(_civic.touches(delta) or _civic.is_civic_receipt(delta) for delta in deltas)


def validate_delta(delta):
    result = _BASE_VALIDATE_DELTA_NV20(delta)
    if not _civic.touches(delta):
        return result
    try:
        registry, catalog = _civic_config()
        _civic.validate_delta_shape(delta, registry, catalog)
    except _civic.CivicPolicyError as exc:
        raise TransactionError(str(exc)) from exc
    return result


def validate_pending_record(record):
    result = _BASE_VALIDATE_PENDING_NV20(record)
    deltas = list(record.get("deltas") or [])
    if not _civic_relevant(deltas):
        return result
    try:
        registry, catalog = _civic_config()
        _civic.validate_transaction_contract(deltas, registry, catalog)
    except _civic.CivicPolicyError as exc:
        raise TransactionError(str(exc)) from exc
    return result
