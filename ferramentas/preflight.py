#!/usr/bin/env python3
"""Preflight até NV-19 + gate de reconhecibilidade NV-20."""
from __future__ import annotations

from pathlib import Path
import sys

_LEGACY_SOURCE = Path(__file__).with_name("_preflight_nv19.py")
_saved_name = globals().get("__name__", "preflight")
if _saved_name == "__main__":
    # O snapshot contém dataclasses. Durante execução via ``exec``, dataclasses
    # precisa encontrar ``cls.__module__`` em ``sys.modules``; ao mesmo tempo não
    # podemos deixar o ``if __name__ == '__main__'`` legado executar antes da
    # composição NV-20. O alias registra o próprio módulo público só no caminho CLI.
    _exec_name = "_preflight_nv19_exec"
    sys.modules[_exec_name] = sys.modules[_saved_name]
    globals()["__name__"] = _exec_name
    try:
        exec(compile(_LEGACY_SOURCE.read_text(encoding="utf-8"), str(_LEGACY_SOURCE), "exec"), globals(), globals())
    finally:
        globals()["__name__"] = _saved_name
else:
    # Em import normal, preserve o nome real do módulo. Isso mantém dataclasses,
    # monkeypatches e introspecção associados ao módulo público.
    exec(compile(_LEGACY_SOURCE.read_text(encoding="utf-8"), str(_LEGACY_SOURCE), "exec"), globals(), globals())

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
