#!/usr/bin/env python3
"""Transações até NV-19 + pareamento atômico de reconhecibilidade da NV-20.

A implementação anterior fica congelada em ``_transacoes_nv19.py`` e é executada
no mesmo namespace. A NV-20 só intercepta o domínio
``estado.reconhecibilidade_personas`` e exige que cada apresentação pública
confirmada carregue seu evento de fama no mesmo registro transacional.
"""
from __future__ import annotations

from pathlib import Path

_LEGACY_SOURCE = Path(__file__).with_name("_transacoes_nv19.py")
_saved_name = globals().get("__name__", "transacoes")
globals()["__name__"] = "_transacoes_nv19_exec"
exec(compile(_LEGACY_SOURCE.read_text(encoding="utf-8"), str(_LEGACY_SOURCE), "exec"), globals(), globals())
globals()["__name__"] = _saved_name

import reconhecibilidade_persona as _recognition

_BASE_VALIDATE_DELTA_NV19 = validate_delta
_BASE_VALIDATE_PENDING_NV19 = validate_pending_record


def _recognition_registries():
    repo = Path(__file__).resolve().parents[1]
    return _recognition.load_audiences(repo), _recognition.load_identities(repo)


def validate_delta(delta):
    if not _recognition.touches(delta):
        return _BASE_VALIDATE_DELTA_NV19(delta)
    try:
        # Preserva as garantias estruturais do delta genérico antes do contrato NV-20.
        _base.validate_delta(delta)
        audiences, identities_registry = _recognition_registries()
        return _recognition.validate_delta(delta, audiences, identities_registry)
    except _recognition.RecognizabilityError as exc:
        raise TransactionError(str(exc)) from exc


def validate_pending_record(record):
    result = _BASE_VALIDATE_PENDING_NV19(record)
    try:
        audiences, identities_registry = _recognition_registries()
        _recognition.validate_transaction_contract(
            list(record.get("deltas") or []), audiences, identities_registry
        )
    except _recognition.RecognizabilityError as exc:
        raise TransactionError(str(exc)) from exc
    return result
