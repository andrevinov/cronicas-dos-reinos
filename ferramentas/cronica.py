#!/usr/bin/env python3
"""Porta unificada da crônica, composta até a NV-19.

A composição preserva uma única identidade de módulo para compatibilidade com
monkeypatches, reparos e integrações legadas. NV-15 instala permanência espacial;
NV-16 acrescenta iniciativa do elenco; NV-17 roteia side quests vivas por causa;
NV-19 expõe entradas causais vencidas sem escolher personagens do catálogo.
"""
from __future__ import annotations

import sys

# Imports de composição não fazem I/O de campanha.
import permanencia_espacial_idempotencia as _stay_idempotency  # noqa: F401
import cronica_entradas_causais as _impl

if __name__ == "__main__":
    raise SystemExit(_impl.main())

_base = _impl._base
for _name in dir(_impl):
    if not _name.startswith("__") and not hasattr(_base, _name):
        setattr(_base, _name, getattr(_impl, _name))

sys.modules[__name__] = _base
