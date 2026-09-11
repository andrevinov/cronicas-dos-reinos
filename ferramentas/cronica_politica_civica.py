#!/usr/bin/env python3
"""Composição NV-22 da porta ``cronica``: política cívica e avisos públicos.

A borda não sonda governo nem agenda. Ela só torna explícitos no contrato do
writer a autoria institucional, a publicação causal e o pareamento da entrega
NV-22 com o recibo NV-13.
"""
from __future__ import annotations

import cronica_reconhecibilidade as _prev

_base = _prev._base
_BASE_TRANSACTION_CONTRACT = _base._transaction_contract


def _transaction_contract():
    contract = _BASE_TRANSACTION_CONTRACT()
    contract["politica_civica_nv22"] = (
        "Medida cívica exige instituição autorizada, motivo, causa institucional e escopo; "
        "avance proposta -> avaliação/aprovação -> vigência -> publicação -> encerramento. "
        "Consulte apenas politica_civica.due_plans quando houver razão para processar agenda; "
        "ausência de plano vencido é ausência normal de nova lei. Catálogo menor é limitado, "
        "explícito e nunca aleatório. Publicação deduplica por medida+local+período. "
        "Permanência NV-15 só projeta quadro/edital já produzidos. Ren só toma ciência pelo par "
        "atômico de politica_civica.propose_delivery: estado NV-22 + recibo NV-13 no mesmo writer."
    )
    return contract


_base._transaction_contract = _transaction_contract
if hasattr(_base, "_hot"):
    _base._hot._transaction_contract = _transaction_contract

for _name in dir(_prev):
    if not _name.startswith("__") and not hasattr(_base, _name):
        setattr(_base, _name, getattr(_prev, _name))

main = _base.main

if __name__ == "__main__":
    raise SystemExit(main())
