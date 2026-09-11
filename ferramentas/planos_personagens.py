#!/usr/bin/env python3
"""API pública NV-20 de planos: desafios causais sobre a implementação composta."""
from __future__ import annotations

from pathlib import Path

_IMPL_SOURCE = Path(__file__).with_name("_planos_personagens_nv20.py")
_saved_name = globals().get("__name__", "planos_personagens")
globals()["__name__"] = "_planos_personagens_nv20_exec"
exec(compile(_IMPL_SOURCE.read_text(encoding="utf-8"), str(_IMPL_SOURCE), "exec"), globals(), globals())
globals()["__name__"] = _saved_name

_BASE_STEP_PUBLIC_NV20 = _step
_BASE_CHALLENGE_REQUIREMENTS_NV20 = _challenge_requirements


def _step(value):
    # A composição NV-20 precisa rejeitar a fusão antes de delegar o restante do
    # passo à NV-19; caso contrário um ``entrada_local`` malformado intercepta o
    # erro e mascara o invariante mais forte de separação entre chegada e desafio.
    if isinstance(value, dict) and CHALLENGE_KEY in value and ENTRY_KEY in value:
        raise PlanError("desafio_persona e entrada_local são passos distintos; não fundir chegada e desafio")
    return _BASE_STEP_PUBLIC_NV20(value)


def _challenge_requirements(view, plan):
    blockers, projection = _BASE_CHALLENGE_REQUIREMENTS_NV20(view, plan)
    meta = _challenge_meta(plan.get("passo") or {}) if isinstance(plan, dict) else None
    if meta is None:
        return blockers, projection
    motivation_path = str((meta.get("motivacao") or {}).get("caminho") or "")
    interest_path = str(((meta.get("interesse") or {}).get("referencia") or {}).get("caminho") or "")
    labeled = []
    for blocker in blockers:
        text = str(blocker)
        if "condição mudou" in text and motivation_path and motivation_path in text:
            text = "motivação do desafio mudou: " + text
        elif "condição mudou" in text and interest_path and interest_path in text:
            text = "interesse do desafio mudou: " + text
        labeled.append(text)
    return list(dict.fromkeys(labeled)), projection
