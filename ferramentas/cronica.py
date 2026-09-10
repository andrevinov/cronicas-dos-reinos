#!/usr/bin/env python3
"""Porta unificada da crônica, composta até a NV-15.

A implementação acumulada até a NV-14 permanece em ``_cronica_nv14.py`` e a
NV-15 é instalada por ``cronica_permanencia``. Quando importada, esta porta
expõe o próprio módulo acumulado em vez de copiar seus símbolos: isso preserva
a identidade de módulo exigida por monkeypatches, reparos e integrações legadas.
"""
from __future__ import annotations

import sys

# Instala primeiro a política de digest/retry do recibo espacial. Os imports têm
# somente efeito de composição de funções; nenhum I/O de campanha ocorre aqui.
import permanencia_espacial_idempotencia as _stay_idempotency  # noqa: F401
import cronica_permanencia as _impl

if __name__ == "__main__":
    raise SystemExit(_impl.main())

# ``cronica_permanencia`` já instalou build_parser/_run_turn e os adaptadores
# NV-15 no módulo acumulado. Reexportar por cópia quebraria patch.object em
# auxiliares privados porque as funções continuariam resolvendo globals em
# ``_cronica_nv14``. O alias mantém uma única identidade operacional.
_base = _impl._base
for _name in dir(_impl):
    if not _name.startswith("__") and not hasattr(_base, _name):
        setattr(_base, _name, getattr(_impl, _name))

sys.modules[__name__] = _base
