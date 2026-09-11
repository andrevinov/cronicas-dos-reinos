#!/usr/bin/env python3
"""Composição NV-20 da porta ``cronica``: contrato de marco público/fama.

Não consulta o ledger e não escolhe desafiante. A única responsabilidade desta
borda é tornar explícito no contrato do writer que uma apresentação pública
confirmada deve registrar o marco e a reconhecibilidade no mesmo turno.
"""
from __future__ import annotations

import cronica_entradas_causais as _prev

_base = _prev._base
_BASE_TRANSACTION_CONTRACT = _base._transaction_contract


def _transaction_contract():
    contract = _BASE_TRANSACTION_CONTRACT()
    contract["reconhecibilidade_persona_nv20"] = (
        "Ao confirmar uma apresentação pública atribuída a uma persona, gere os deltas pareados "
        "de reconhecibilidade_persona.propose_public_performance e registre ambos no mesmo writer. "
        "Fama pertence à persona percebida e não confirma identidade real. Desafios dependem de "
        "plano causal explícito; nunca escolha desafiante aleatoriamente."
    )
    return contract


# O hot path histórico consulta _hot._transaction_contract; a porta pública também
# reexporta _transaction_contract. Ambos precisam apontar para a mesma composição.
_base._transaction_contract = _transaction_contract
if hasattr(_base, "_hot"):
    _base._hot._transaction_contract = _transaction_contract

for _name in dir(_prev):
    if not _name.startswith("__") and not hasattr(_base, _name):
        setattr(_base, _name, getattr(_prev, _name))

main = _base.main

if __name__ == "__main__":
    raise SystemExit(main())
