#!/usr/bin/env python3
"""Extensões transacionais: rastros, tempo atômico e compromissos estruturados.

O núcleo legado permanece em ``_transacoes_core.py``. Este wrapper acrescenta
invariantes baratos sem aumentar o número normal de escritas:

- descoberta de rastro transporta conhecimento + mudança reservada no mesmo lote;
- data+hora de mundo são persistidas como **um único delta** `tempo/instante`;
- compromissos futuros entram como `estado/compromissos.<id>` inteiro e são
  projetados em memória antes da consolidação.

Deltas antigos de data+hora, quando chegam juntos e consistentes a uma escrita
nova, são normalizados antes de tocar o JSONL. Um delta isolado de data ou hora é
recusado. Overlays antigos recebem expansão somente em memória.
"""
from __future__ import annotations

from collections import Counter
import copy
import json
import re
from typing import Any, Iterable

import _transacoes_core as _base
import compromissos
import tempo_transacional

for _name in dir(_base):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_base, _name)

TRACE_PREFIX = "rastro:"
TRACE_KNOWLEDGE_TYPE = "rastro_descoberto"
TRACE_DISCOVERED_STATE = "descoberto"
TRACE_TARGET_RE = re.compile(r"^rastro:rastro-[0-9a-f]{16}$")
HOT_COMMITMENTS = 4


def validate_delta(delta: Any) -> dict[str, Any]:
    if not isinstance(delta, dict):
        raise TransactionError("cada delta precisa ser objeto JSON")
    if tempo_transacional.is_atomic_delta(delta):
        try:
            return tempo_transacional.validate_atomic_delta(delta)
        except tempo_transacional.AtomicTimeError as exc:
            raise TransactionError(str(exc)) from exc
    if compromissos.is_commitment_delta(delta):
        try:
            return compromissos.validate_delta(delta)
        except compromissos.CommitmentError as exc:
            raise TransactionError(str(exc)) from exc

    target = delta.get("alvo")
    if not isinstance(target, str):
        raise TransactionError(f"alvo de delta inválido: {target!r}")
    if not target.startswith(TRACE_PREFIX):
        return _base.validate_delta(delta)
    if not TRACE_TARGET_RE.fullmatch(target):
        raise TransactionError(f"alvo de rastro inválido: {target!r}")
    if (
        delta.get("op") != "set"
        or delta.get("caminho") != "estado"
        or delta.get("valor") != TRACE_DISCOVERED_STATE
        or delta.get("visibilidade", "operacional") != "narrador"
    ):
        raise TransactionError(
            f"{target} só aceita set estado=descoberto com visibilidade narrador"
        )
    return delta


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
                if not isinstance(trace_id, str) or not re.fullmatch(r"rastro-[0-9a-f]{16}", trace_id):
                    raise TransactionError("conhecimento de rastro precisa de id determinístico válido")
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
            validate_delta(delta)
            trace_id = target.split(":", 1)[1]
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
    if not isinstance(record, dict):
        raise TransactionError("registro pendente precisa ser objeto JSON")
    if record.get("versao") != SCHEMA_VERSION:
        raise TransactionError(f"versão transacional inesperada: {record.get('versao')!r}")
    transaction_id = record.get("id")
    if not isinstance(transaction_id, str) or not transaction_id.strip():
        raise TransactionError("registro pendente sem id válido")
    session = record.get("sessao")
    if not isinstance(session, int) or session < 1:
        raise TransactionError("registro pendente sem sessao inteira positiva")
    summary = record.get("resumo", "")
    if not isinstance(summary, str):
        raise TransactionError("resumo pendente precisa ser string")
    if len(summary) > MAX_ACCEPTED_SUMMARY_CHARS:
        raise TransactionError(
            f"resumo pendente excede {MAX_ACCEPTED_SUMMARY_CHARS} caracteres: {len(summary)}"
        )

    deltas = record.get("deltas", [])
    if not isinstance(deltas, list):
        raise TransactionError("deltas precisa ser lista")
    if len(deltas) > MAX_DELTAS:
        raise TransactionError(f"transação excede {MAX_DELTAS} deltas")
    for delta in deltas:
        validate_delta(delta)
    try:
        tempo_transacional.validate_record_contract(deltas)
    except tempo_transacional.AtomicTimeError as exc:
        raise TransactionError(str(exc)) from exc
    validate_trace_discovery_pairs(deltas)

    hidden = record.get("rolagens_ocultas", [])
    if not isinstance(hidden, list) or any(not isinstance(item, str) for item in hidden):
        raise TransactionError("rolagens_ocultas precisa ser lista de strings")
    if len(hidden) > MAX_HIDDEN_ROLLS:
        raise TransactionError(f"transação excede {MAX_HIDDEN_ROLLS} rolagens ocultas")

    mode = record.get("modo")
    if mode is not None and not isinstance(mode, str):
        raise TransactionError("modo precisa ser string quando presente")
    return record


def build_pending_record(transaction: dict[str, Any], session: int) -> dict[str, Any]:
    transaction_id = stable_transaction_id(transaction, session)
    summary = transaction.get("resumo") or ""
    if not isinstance(summary, str):
        raise TransactionError("resumo da transação precisa ser string")
    if not summary.strip():
        summary = str(transaction.get("narracao") or "").strip()
    summary = compact_summary(summary)
    try:
        normalized_deltas = tempo_transacional.normalize_new_deltas(transaction.get("deltas") or [])
    except tempo_transacional.AtomicTimeError as exc:
        raise TransactionError(str(exc)) from exc

    record: dict[str, Any] = {
        "versao": SCHEMA_VERSION,
        "id": transaction_id,
        "sessao": session,
        "resumo": summary,
        "deltas": normalized_deltas,
    }
    for key in ("modo", "tempo_mundo", "rolagens_ocultas", "tags"):
        value = transaction.get(key)
        if value not in (None, [], ""):
            record[key] = value
    validate_pending_record(record)
    return record


def load_pending(repo):
    if (repo / CONSOLIDATION_JOURNAL).exists():
        raise TransactionError(
            "consolidação em andamento; execute ferramentas/consolidar.py recuperar antes de ler ou registrar novos turnos"
        )
    path = repo / PENDING_PATH
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    ids: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TransactionError(f"JSONL inválido em {PENDING_PATH}:{number}: {exc}") from exc
        try:
            validate_pending_record(record)
        except TransactionError as exc:
            raise TransactionError(f"{PENDING_PATH}:{number}: {exc}") from exc
        transaction_id = record["id"]
        if transaction_id in ids:
            raise TransactionError(f"id transacional duplicado em {PENDING_PATH}: {transaction_id}")
        ids.add(transaction_id)
        records.append(record)
    return records


def overlay_target(
    payload: dict[str, Any],
    records: Iterable[dict[str, Any]],
    target: str,
) -> tuple[dict[str, Any], int]:
    return _base.overlay_target(payload, tempo_transacional.expand_records(records), target)


def _compact_commitments(bundle: Any) -> Any:
    if not isinstance(bundle, dict):
        return bundle
    items = bundle.get("itens")
    if not isinstance(items, dict) or len(items) <= HOT_COMMITMENTS:
        return bundle
    keys = list(items)
    keep = keys[:HOT_COMMITMENTS]
    dropped = keys[HOT_COMMITMENTS:]
    result = copy.deepcopy(bundle)
    result["itens"] = {key: copy.deepcopy(items[key]) for key in keep}
    result["omitidos"] = list(dict.fromkeys([*(result.get("omitidos") or []), *dropped]))
    return result


def overlay_runtime(
    context: dict[str, Any],
    scene: dict[str, Any] | None,
    records: Iterable[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any] | None, int]:
    expanded = tempo_transacional.expand_records(records)
    context_out, scene_out, applied = _base.overlay_runtime(context, scene, expanded)

    session = ((context_out.get("sessao") or {}).get("numero"))
    current = _base.pending_for_session(expanded, session if isinstance(session, int) else None)
    for record in current:
        for delta in record.get("deltas") or []:
            if delta.get("visibilidade", "operacional") == "narrador":
                continue
            if delta.get("op") == "registrar":
                continue
            target = delta.get("alvo")
            path = delta.get("caminho")
            if (
                target == "estado"
                and isinstance(path, str)
                and path.startswith("recursos.disponibilidades.")
            ):
                _base._apply_mapped(context_out, path, delta)
                applied += 1

    applied += compromissos.apply_pending_to_runtime(context_out, None, current)
    if "compromissos" in context_out:
        context_out["compromissos"] = _compact_commitments(context_out["compromissos"])
    return context_out, scene_out, applied
