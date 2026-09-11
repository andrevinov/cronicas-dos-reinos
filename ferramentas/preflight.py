#!/usr/bin/env python3
"""Preflight até NV-22 + gate read-only da aceitação integrada de vivacidade."""
from __future__ import annotations

from pathlib import Path
import sys

_NV23_LEGACY_SOURCE = Path(__file__).with_name("_preflight_nv22.py")
_nv23_saved_name = globals().get("__name__", "preflight")
if _nv23_saved_name == "__main__":
    _nv23_exec_name = "_preflight_nv22_exec"
    sys.modules[_nv23_exec_name] = sys.modules[_nv23_saved_name]
    globals()["__name__"] = _nv23_exec_name
    try:
        exec(
            compile(
                _NV23_LEGACY_SOURCE.read_text(encoding="utf-8"),
                str(_NV23_LEGACY_SOURCE),
                "exec",
            ),
            globals(),
            globals(),
        )
    finally:
        globals()["__name__"] = _nv23_saved_name
else:
    exec(
        compile(
            _NV23_LEGACY_SOURCE.read_text(encoding="utf-8"),
            str(_NV23_LEGACY_SOURCE),
            "exec",
        ),
        globals(),
        globals(),
    )

_BASE_CHECKS_NV22 = checks


def checks(*, incluir_testes: bool = True):
    result = _BASE_CHECKS_NV22(incluir_testes=incluir_testes)
    gate = Check(
        "aceitação integrada de vivacidade",
        (sys.executable, "ferramentas/aceitacao_vivacidade.py", "check"),
        "mundo vivo",
    )
    insert_at = next(
        (i for i, item in enumerate(result) if item.nome == "estado atual separado do histórico"),
        len(result),
    )
    result.insert(insert_at, gate)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
