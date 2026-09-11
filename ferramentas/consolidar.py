#!/usr/bin/env python3
"""Consolidação até NV-19 + validação staged do ledger NV-20.

O ledger de reconhecibilidade é um campo do estado canônico, portanto o writer
multi-arquivo existente continua sendo a única transação. Esta borda apenas
valida a transição append-only antes do stage e revalida o estado produzido.
"""
from __future__ import annotations

from pathlib import Path

_LEGACY_SOURCE = Path(__file__).with_name("_consolidar_nv19.py")
_saved_name = globals().get("__name__", "consolidar")
globals()["__name__"] = "_consolidar_nv19_exec"
exec(compile(_LEGACY_SOURCE.read_text(encoding="utf-8"), str(_LEGACY_SOURCE), "exec"), globals(), globals())
globals()["__name__"] = _saved_name

import reconhecibilidade_persona as _recognition

_BASE_BUILD_PLAN_NV19 = build_plan


def _has_recognition(records):
    return any(
        _recognition.touches(delta)
        for record in records
        for delta in (record.get("deltas") or [])
    )


def _validate_recognition_output(repo: Path, plan):
    if plan is None:
        return
    raw = (plan.get("outputs") or {}).get(_recognition.STATE_FILE.as_posix())
    if raw is None:
        raise ConsolidationError("lote de fama não produziu estado/estado-atual.yaml staged")
    try:
        doc = _base.yaml.safe_load(raw.decode("utf-8"))
        if not isinstance(doc, dict):
            raise _recognition.RecognizabilityError("estado staged inválido")
        _recognition.validate_state(
            doc.get(_recognition.STATE_ROOT),
            _recognition.load_audiences(Path(repo)),
            _recognition.load_identities(Path(repo)),
        )
    except (UnicodeDecodeError, _base.yaml.YAMLError, _recognition.RecognizabilityError) as exc:
        raise ConsolidationError(f"reconhecibilidade staged inválida: {exc}") from exc


def build_plan(repo: Path, kind: str):
    _session, _pending_all, records, _done = _records_for_batch(Path(repo))
    has_recognition = _has_recognition(records)
    if has_recognition:
        try:
            _recognition.validate_batch(Path(repo), records)
        except _recognition.RecognizabilityError as exc:
            raise ConsolidationError(str(exc)) from exc
    plan = _BASE_BUILD_PLAN_NV19(Path(repo), kind)
    if has_recognition:
        _validate_recognition_output(Path(repo), plan)
    return plan


_base.build_plan = build_plan


def main() -> int:
    return _base.main()


if __name__ == "__main__":
    raise SystemExit(main())
