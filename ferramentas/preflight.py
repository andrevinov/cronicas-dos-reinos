#!/usr/bin/env python3
"""Preflight até NV-20 + gate de clima diário NV-21."""
from __future__ import annotations

from pathlib import Path
import sys

_LEGACY_SOURCE = Path(__file__).with_name("_preflight_nv19.py")
_saved_name = globals().get("__name__", "preflight")
if _saved_name == "__main__":
    _exec_name = "_preflight_nv19_exec"
    sys.modules[_exec_name] = sys.modules[_saved_name]
    globals()["__name__"] = _exec_name
    try:
        exec(compile(_LEGACY_SOURCE.read_text(encoding="utf-8"), str(_LEGACY_SOURCE), "exec"), globals(), globals())
    finally:
        globals()["__name__"] = _saved_name
else:
    exec(compile(_LEGACY_SOURCE.read_text(encoding="utf-8"), str(_LEGACY_SOURCE), "exec"), globals(), globals())

_BASE_CHECKS_NV19 = checks


def checks(*, incluir_testes: bool = True):
    result = _BASE_CHECKS_NV19(incluir_testes=incluir_testes)
    python = sys.executable
    gates = [
        Check(
            "reconhecibilidade de personas",
            (python, "ferramentas/reconhecibilidade_persona.py", "check"),
            "mundo vivo",
        ),
        Check(
            "clima diário determinístico",
            (python, "ferramentas/clima_diario.py", "check"),
            "mundo vivo",
        ),
    ]
    insert_at = next(
        (i for i, item in enumerate(result) if item.nome == "estado atual separado do histórico"),
        len(result),
    )
    for offset, gate in enumerate(gates):
        result.insert(insert_at + offset, gate)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
