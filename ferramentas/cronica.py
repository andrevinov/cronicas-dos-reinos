#!/usr/bin/env python3
"""Porta unificada da crônica, composta até a NV-15.

A implementação acumulada até a NV-14 foi preservada em ``_cronica_nv14.py``;
``cronica_permanencia`` instala somente a extensão de permanência espacial e
reexporta a mesma superfície pública e interna para compatibilidade.
"""
from __future__ import annotations

import cronica_permanencia as _impl

for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)

main = _impl.main

if __name__ == "__main__":
    raise SystemExit(main())
