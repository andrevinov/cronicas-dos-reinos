#!/usr/bin/env python3
"""Consolidação até NV-20 + validação staged da política cívica NV-22."""
from __future__ import annotations

from pathlib import Path

_LEGACY_SOURCE = Path(__file__).with_name("_consolidar_nv20.py")
_saved_name = globals().get("__name__", "consolidar")
globals()["__name__"] = "_consolidar_nv20_exec"
exec(compile(_LEGACY_SOURCE.read_text(encoding="utf-8"), str(_LEGACY_SOURCE), "exec"), globals(), globals())
globals()["__name__"] = _saved_name

import politica_civica as _civic

_BASE_BUILD_PLAN_NV20 = build_plan


def _has_civic(records):
    return any(
        _civic.touches(delta) or _civic.is_civic_receipt(delta)
        for record in records
        for delta in (record.get("deltas") or [])
    )


def _validate_civic_output(repo: Path, plan):
    if plan is None:
        return
    raw = (plan.get("outputs") or {}).get(_civic.STATE_FILE.as_posix())
    if raw is None:
        raise ConsolidationError("lote cívico não produziu estado/estado-atual.yaml staged")
    try:
        doc = _base.yaml.safe_load(raw.decode("utf-8"))
        if not isinstance(doc, dict) or _civic.STATE_ROOT not in doc:
            raise _civic.CivicPolicyError("estado staged perdeu a raiz politica_civica")
        registry = _civic.load_registry(Path(repo))
        catalog = _civic.load_catalog(Path(repo), registry)
        _civic.validate_state(doc[_civic.STATE_ROOT], registry, catalog)
    except (UnicodeDecodeError, _base.yaml.YAMLError, _civic.CivicPolicyError) as exc:
        raise ConsolidationError(f"política cívica staged inválida: {exc}") from exc


def build_plan(repo: Path, kind: str):
    _session, _pending_all, records, _done = _records_for_batch(Path(repo))
    has_civic = _has_civic(records)
    if has_civic:
        try:
            _civic.validate_batch(Path(repo), records)
        except _civic.CivicPolicyError as exc:
            raise ConsolidationError(str(exc)) from exc
    plan = _BASE_BUILD_PLAN_NV20(Path(repo), kind)
    if has_civic:
        _validate_civic_output(Path(repo), plan)
    return plan


_base.build_plan = build_plan


def main() -> int:
    return _base.main()


if __name__ == "__main__":
    raise SystemExit(main())
