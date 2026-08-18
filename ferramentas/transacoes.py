#!/usr/bin/env python3
"""Extensão transacional para descobertas de rastros do Mundo Vivo.

O núcleo legado permanece em ``_transacoes_core.py``. Este wrapper acrescenta um
invariante pequeno e barato: toda descoberta de rastro precisa transportar, na
mesma transação, o conhecimento observável e a mudança reservada do rastro para
``descoberto``. Assim o caminho normal recusa pares incompletos antes das duas
escritas de ``turno.py``.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

import _transacoes_core as _base

for _name in dir(_base):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_base, _name)

TRACE_PREFIX = "rastro:"
TRACE_KNOWLEDGE_TYPE = "rastro_descoberto"
TRACE_DISCOVERED_STATE = "descoberto"


def _trace_discovery_pairs(deltas: list[dict[str, Any]]) -> tuple[Counter[str], Counter[str]]:
    knowledge: Counter[str] = Counter()
    state: Counter[str] = Counter()

    for delta in deltas:
        target = str(delta.get("alvo") or "")
        op = delta.get("op")

        if target == "conhecimento" and op == "registrar":
            value = delta.get("valor")
            if isinstance(value, dict) and value.get("tipo") == TRACE_KNOWLEDGE_TYPE:
                trace_id = value.get("rastro")
                if not isinstance(trace_id, str) or not trace_id:
                    raise TransactionError("conhecimento de rastro precisa de rastro válido")
                text = value.get("texto")
                if not isinstance(text, str) or not text.strip():
                    raise TransactionError(f"descoberta {trace_id} precisa de texto observável")
                if value.get("fonte") != f"{TRACE_PREFIX}{trace_id}":
                    raise TransactionError(
                        f"descoberta {trace_id} precisa usar fonte {TRACE_PREFIX}{trace_id}"
                    )
                knowledge[trace_id] += 1
            continue

        if target.startswith(TRACE_PREFIX):
            trace_id = target.split(":", 1)[1]
            if not trace_id:
                raise TransactionError("alvo de rastro sem id")
            if (
                op != "set"
                or delta.get("caminho") != "estado"
                or delta.get("valor") != TRACE_DISCOVERED_STATE
                or delta.get("visibilidade", "operacional") != "narrador"
            ):
                raise TransactionError(
                    f"{target} só aceita set estado=descoberto com visibilidade narrador"
                )
            state[trace_id] += 1

    return knowledge, state


def validate_trace_discovery_pairs(deltas: list[dict[str, Any]]) -> None:
    knowledge, state = _trace_discovery_pairs(deltas)
    ids = set(knowledge) | set(state)
    for trace_id in sorted(ids):
        if knowledge[trace_id] != 1 or state[trace_id] != 1:
            raise TransactionError(
                f"descoberta de rastro {trace_id} exige exatamente um delta de conhecimento "
                "e um delta reservado rastro:<id> na mesma transação"
            )


def validate_pending_record(record: Any) -> dict[str, Any]:
    validated = _base.validate_pending_record(record)
    validate_trace_discovery_pairs(validated.get("deltas") or [])
    return validated


def build_pending_record(transaction: dict[str, Any], session: int) -> dict[str, Any]:
    record = _base.build_pending_record(transaction, session)
    validate_trace_discovery_pairs(record.get("deltas") or [])
    return record


def load_pending(repo):
    records = _base.load_pending(repo)
    for record in records:
        validate_trace_discovery_pairs(record.get("deltas") or [])
    return records
