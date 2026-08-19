#!/usr/bin/env python3
"""Consolidação legado + rastros + instante temporal atômico.

``_consolidar_core.py`` preserva o consolidator já testado. Este wrapper intercepta
somente lotes que exigem extensão:

- `rastro:<id>` é validado e instalado no mesmo journal do conhecimento;
- `tempo/instante` permanece um único delta persistido e é expandido **somente em
  memória** para os espelhos físicos (`tempo.data_atual`, `tempo.data`,
  `tempo.hora_aproximada`). O núcleo então sincroniza `estado.tempo` no mesmo plano
  multi-arquivo antes de qualquer instalação.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import _consolidar_core as _base
import rastros
import _rastros_core as _rastros_base
import tempo_transacional
import transacoes

for _name in dir(_base):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_base, _name)

_original_build_plan = _base.build_plan
_original_load_pending = transacoes.load_pending


def _records_for_batch(repo: Path) -> tuple[int, list[dict[str, Any]], list[dict[str, Any]], set[str]]:
    session = _base.current_session(repo)
    pending_all = _original_load_pending(repo)
    pending_session = transacoes.pending_for_session(pending_all, session)
    ledger = _base.load_ledger(repo, session)
    done = _base.consolidated_ids(ledger)
    records = [record for record in pending_session if record["id"] not in done]
    return session, pending_all, records, done


def _trace_delta_ids(record: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for delta in record.get("deltas") or []:
        target = str(delta.get("alvo") or "")
        if target.startswith(transacoes.TRACE_PREFIX):
            result.append(target.split(":", 1)[1])
    return result


def _knowledge_value(record: dict[str, Any], trace_id: str) -> dict[str, Any]:
    matches = []
    for delta in record.get("deltas") or []:
        if delta.get("alvo") != "conhecimento" or delta.get("op") != "registrar":
            continue
        value = delta.get("valor")
        if (
            isinstance(value, dict)
            and value.get("tipo") == transacoes.TRACE_KNOWLEDGE_TYPE
            and value.get("rastro") == trace_id
        ):
            matches.append(value)
    if len(matches) != 1:
        raise ConsolidationError(
            f"transação {record['id']}: descoberta {trace_id} precisa de um único conhecimento pareado"
        )
    return matches[0]


def _prepare_trace_index(
    repo: Path, records: list[dict[str, Any]]
) -> tuple[dict[str, Any], list[str]]:
    index = rastros.load_index(repo)
    discovered: list[str] = []
    for record in records:
        for trace_id in _trace_delta_ids(record):
            meta = index["rastros"].get(trace_id)
            if not isinstance(meta, dict):
                raise ConsolidationError(f"transação {record['id']}: rastro inexistente: {trace_id}")
            if meta.get("estado", "ativo") != "ativo":
                raise ConsolidationError(
                    f"transação {record['id']}: rastro {trace_id} já não está ativo para descoberta"
                )
            try:
                doc = _rastros_base.validate_trace(repo, trace_id, meta)
            except rastros.TraceError as exc:
                raise ConsolidationError(str(exc)) from exc
            value = _knowledge_value(record, trace_id)
            if value.get("texto") != doc["fato_observavel"]:
                raise ConsolidationError(
                    f"transação {record['id']}: conhecimento de {trace_id} excede/diverge do fato observável"
                )
            if value.get("fonte") != f"rastro:{trace_id}":
                raise ConsolidationError(
                    f"transação {record['id']}: fonte pública de {trace_id} precisa apontar apenas para o rastro"
                )
            meta["estado"] = "descoberto"
            discovered.append(trace_id)
    return index, discovered


def _prepared_pending(
    pending_all: list[dict[str, Any]],
    session: int,
    process_ids: set[str],
    *,
    strip_traces: bool,
) -> list[dict[str, Any]]:
    """Transforma somente o lote atual; pendências de outras sessões ficam byte-lógicas iguais."""
    result = copy.deepcopy(pending_all)
    for record in result:
        if record.get("sessao") != session or record.get("id") not in process_ids:
            continue
        deltas = list(record.get("deltas") or [])
        if strip_traces:
            deltas = [
                delta
                for delta in deltas
                if not str(delta.get("alvo") or "").startswith(transacoes.TRACE_PREFIX)
            ]
        try:
            record["deltas"] = tempo_transacional.expand_atomic_deltas(deltas)
        except tempo_transacional.AtomicTimeError as exc:
            raise ConsolidationError(str(exc)) from exc
    return result


def _patch_ledger_and_artifacts(
    repo: Path,
    plan: dict[str, Any],
    kind: str,
    records: list[dict[str, Any]],
    discovered: list[str],
    atomic_instants: int,
) -> None:
    if not plan.get("batch"):
        return
    session = plan["sessao"]
    ledger_rel = Path("sessoes") / f"{session:03d}" / _base.LEDGER_NAME
    raw = plan["outputs"].get(ledger_rel.as_posix())
    if raw is None:
        raise ConsolidationError("plano transacional não contém ledger esperado")
    ledger: list[dict[str, Any]] = []
    for line in raw.decode("utf-8").splitlines():
        if line.strip():
            ledger.append(json.loads(line))
    batch = next((item for item in ledger if item.get("id") == plan["batch"]), None)
    if batch is None:
        raise ConsolidationError("batch recém-criado não encontrado no ledger staged")

    # O ledger descreve a transação persistida, não a expansão interna usada pelo
    # consolidator legado.
    batch["deltas"] = sum(len(record.get("deltas") or []) for record in records)
    if atomic_instants:
        batch["instantes_atomicos"] = atomic_instants
    if discovered:
        batch["rastros_descobertos"] = list(dict.fromkeys(discovered))
        affected = set(batch.get("arquivos_afetados") or [])
        affected.add(rastros.INDEX.as_posix())
        batch["arquivos_afetados"] = sorted(affected)

    plan["outputs"][ledger_rel.as_posix()] = _base.jsonl_text(ledger)
    _base._session_artifacts(
        repo,
        session,
        ledger,
        plan["checkpoint_antes"],
        plan["checkpoint_depois"],
        kind,
        plan["outputs"],
    )


def build_plan(repo: Path, kind: str) -> dict[str, Any] | None:
    session, pending_all, records, _done = _records_for_batch(repo)
    trace_records = [record for record in records if _trace_delta_ids(record)]
    atomic_instants = tempo_transacional.atomic_count(records)
    if not trace_records and not atomic_instants:
        return _original_build_plan(repo, kind)

    trace_index: dict[str, Any] | None = None
    discovered: list[str] = []
    if trace_records:
        trace_index, discovered = _prepare_trace_index(repo, trace_records)

    process_ids = {record["id"] for record in records}
    prepared = _prepared_pending(
        pending_all,
        session,
        process_ids,
        strip_traces=bool(trace_records),
    )

    old_loader = transacoes.load_pending
    transacoes.load_pending = lambda _repo: copy.deepcopy(prepared)
    try:
        plan = _original_build_plan(repo, kind)
    finally:
        transacoes.load_pending = old_loader

    if plan is None:
        raise ConsolidationError("lote estendido ficou sem plano de consolidação")

    if trace_index is not None:
        trace_bytes = _base.dump_yaml(trace_index)
        if len(trace_bytes) > rastros.MAX_INDEX_BYTES:
            raise ConsolidationError("índice de rastros excederia o teto operacional durante descoberta")
        plan["outputs"][rastros.INDEX.as_posix()] = trace_bytes

    _patch_ledger_and_artifacts(
        repo,
        plan,
        kind,
        records,
        discovered,
        atomic_instants,
    )
    if discovered:
        plan["rastros_descobertos"] = list(dict.fromkeys(discovered))
    if atomic_instants:
        plan["instantes_atomicos"] = atomic_instants
    return plan


# O consolidator legado resolve `build_plan` no próprio módulo. Redirecioná-lo aqui
# mantém stage/install/recovery byte a byte iguais e troca apenas o planejamento.
_base.build_plan = build_plan


def main() -> int:
    return _base.main()


if __name__ == "__main__":
    raise SystemExit(main())
