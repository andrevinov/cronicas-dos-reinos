#!/usr/bin/env python3
"""Porta de cena com presença, sidequests canônicas e condições persistentes."""
from __future__ import annotations

import cena_mundo_v4 as _v4
import condicoes_mundo_cena as _conditions
import presenca_incidental_cena as _incidental
import sidequest_gate_v2 as _gate_v2
import sidequests_canonicas_cena as _canonical_quests

# Task31 mantém o procedural morto. Task32 recebe apenas refs opacas do encontro
# explícito; presença incidental é instalada antes e nunca fornece refs de quest.
# Task34 envolve a porta por último: só cenas com contexto espacial leem o estado
# compacto de condições e ele entra no fingerprint da preparação.
_v4._core.interacoes_mundo.encounter_event = _gate_v2.encounter_event
_incidental.install()
_canonical_quests.install()
_conditions.install()

for _name in dir(_v4):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_v4, _name)

prepare_scene = _v4.prepare_scene
confirm_scene = _v4.confirm_scene
open_scene = _v4.open_scene
build_parser = _v4.build_parser
main = _v4.main

if __name__ == "__main__":
    raise SystemExit(main())
