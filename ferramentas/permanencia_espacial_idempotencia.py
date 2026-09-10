"""Ajustes de idempotência do recibo NV-15 aplicados antes da composição da CLI.

Separado da lógica do produtor para manter o digest do ticket imutável mesmo
quando somente o estado de resolução muda. Não cria estado nem mecanismo novo.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import permanencia_espacial as _stay

_BASE_PREPARE_CONCLUSION = _stay.prepare_conclusion


def _record_digest(record: dict[str, Any]) -> str:
    value = copy.deepcopy(record)
    value.pop("digest", None)
    value.pop("estado", None)
    value.pop("decisao", None)
    return _stay._digest(value)


def prepare_conclusion(
    repo: Path,
    meta: Any,
    transaction: dict[str, Any],
) -> dict[str, Any] | None:
    public = _stay.revalidate(repo, meta)
    if public["estado"] not in _stay.RESULTS:
        return _BASE_PREPARE_CONCLUSION(repo, meta, transaction)

    block = transaction.get("permanencia_espacial")
    if not isinstance(block, dict):
        raise _stay.SpatialPermanenceError(
            "retry de pressão espacial concluída exige repetir o mesmo bloco permanencia_espacial"
        )
    state = _stay.load_state(repo)
    record = state["avaliacoes"].get(public["avaliacao_id"])
    if not isinstance(record, dict):
        raise _stay.SpatialPermanenceError("retry não encontra avaliação espacial instalada")
    existing = copy.deepcopy(record.get("decisao") or {})
    existing.pop("em", None)
    if block != existing:
        raise _stay.SpatialPermanenceError(
            "retry de permanência diverge da decisão espacial já instalada"
        )
    return existing


_stay._record_digest = _record_digest
_stay.prepare_conclusion = prepare_conclusion
