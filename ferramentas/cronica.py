#!/usr/bin/env python3
"""Porta unificada da crônica, composta até a NV-15.

A implementação acumulada até a NV-14 foi preservada em ``_cronica_nv14.py``;
``cronica_permanencia`` instala somente a extensão de permanência espacial e
reexporta a mesma API pública.
"""
from cronica_permanencia import *  # noqa: F401,F403

if __name__ == "__main__":
    raise SystemExit(main())
