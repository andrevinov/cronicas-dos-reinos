#!/usr/bin/env python3
"""API pública da NV-15 — permanência espacial reativa.

O núcleo fica congelado em ``_permanencia_espacial_core.py`` e esta borda aplica
as garantias finais de digest/retry/período antes de reexportar a API completa.
"""
from __future__ import annotations

import permanencia_espacial_idempotencia as _impl

for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)
