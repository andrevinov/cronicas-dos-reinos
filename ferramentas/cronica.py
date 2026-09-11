#!/usr/bin/env python3
"""Porta unificada da crônica, composta até a NV-22.

Preserva uma única identidade de módulo. NV-22 acrescenta política cívica e
avisos públicos sem consultar agenda institucional no hot path normal.
"""
from __future__ import annotations

import sys

# Imports de composição não fazem I/O de campanha.
import permanencia_espacial_idempotencia as _stay_idempotency  # noqa: F401
import cronica_politica_civica as _impl

if __name__ == "__main__":
    raise SystemExit(_impl.main())

_base = _impl._base
for _name in dir(_impl):
    if not _name.startswith("__") and not hasattr(_base, _name):
        setattr(_base, _name, getattr(_impl, _name))

sys.modules[__name__] = _base
