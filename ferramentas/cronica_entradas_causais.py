#!/usr/bin/env python3
"""Composição NV-19 da porta ``cronica`` para entradas causais locais.

A chegada continua pertencendo ao plano/Mundo Vivo. Esta borda apenas expõe, em
uma permanência local, a única entrada vencida já selecionada pela NV-19. Não há
escolha de personagem no catálogo e nenhum efeito é aplicado na preparação.
"""
from __future__ import annotations

import copy

import cronica_sidequests_vivas as _prev

_base = _prev._base
_BASE_PREPARE = _base.prepare


def prepare(*args, **kwargs):
    prepared = _BASE_PREPARE(*args, **kwargs)
    stay = prepared.get("permanencia_espacial")
    if not isinstance(stay, dict):
        return prepared
    entry = stay.get("entrada_causal")
    if not isinstance(entry, dict):
        return prepared
    result = copy.deepcopy(prepared)
    actor = (entry.get("agente") or {}).get("id")
    ids = result.setdefault("ids", {})
    ids["entradas_contextuais"] = [actor] if isinstance(actor, str) and actor else []
    result["entrada_local"] = copy.deepcopy(entry)
    gates = result.setdefault("gates", [])
    gates.append({
        "tipo": "entrada_local",
        "resultado": entry.get("fase"),
        "plano_id": entry.get("plano_id"),
        "pendencia_id": entry.get("pendencia_id"),
        "bloqueios": list(entry.get("bloqueios") or []),
    })
    systems = result.setdefault("sistemas_narrativos", [])
    if "causal_character_entry" not in systems:
        systems.append("causal_character_entry")
    next_step = result.setdefault("proximo_passo", {})
    next_step["entrada_local"] = (
        "A entrada é apenas uma obrigação causal projetada. Resolva a pendência pelo lote do Mundo Vivo; "
        "cadastro, ticket ou passagem do tempo não materializam presença por si sós."
    )
    return result


_base.prepare = prepare

for _name in dir(_prev):
    if not _name.startswith("__") and not hasattr(_base, _name):
        setattr(_base, _name, getattr(_prev, _name))

main = _base.main

if __name__ == "__main__":
    raise SystemExit(main())
