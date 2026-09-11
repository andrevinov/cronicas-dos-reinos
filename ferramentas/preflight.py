#!/usr/bin/env python3
"""Preflight até NV-19 + gate de reconhecibilidade NV-20."""
from __future__ import annotations

from pathlib import Path

_LEGACY_SOURCE = Path(__file__).with_name("_preflight_nv19.py")
_saved_name = globals().get("__name__", "preflight")
globals()["__name__"] = "_preflight_nv19_exec"
exec(compile(_LEGACY_SOURCE.read_text(encoding="utf-8"), str(_LEGACY_SOURCE), "exec"), globals(), globals())
globals()["__name__"] = _saved_name

_BASE_CHECKS_NV19 = checks


def checks(*, incluir_testes: bool = True):
    result = _BASE_CHECKS_NV19(incluir_testes=incluir_testes)
    python = sys.executable
    gate = Check(
        "reconhecibilidade de personas",
        (python, "ferramentas/reconhecibilidade_persona.py", "check"),
        "mundo vivo",
    )
    # Mantém a ordem histórica e acrescenta apenas um gate dirigido antes das
    # verificações estruturais finais.
    insert_at = next(
        (i for i, item in enumerate(result) if item.nome == "estado atual separado do histórico"),
        len(result),
    )
    result.insert(insert_at, gate)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
