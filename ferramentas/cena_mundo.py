#!/usr/bin/env python3
"""Porta de cena com presença, quests, condições e incidentes sérios."""
from __future__ import annotations

import cena_mundo_v4 as _v4
import condicoes_mundo_cena as _conditions
import incidentes_mundo_cena as _incidents
import presenca_incidental_cena as _incidental
import sidequest_gate_v2 as _gate_v2
import sidequests_canonicas_cena as _canonical_quests

# Task31 mantém o procedural de sidequest morto. Presença e quests canônicas vêm
# antes; Task34 projeta condições; Task35 é a última camada e reutiliza local,
# ecologia e condições já resolvidos para avaliar no máximo um incidente sério.
_v4._core.interacoes_mundo.encounter_event = _gate_v2.encounter_event
_incidental.install()
_canonical_quests.install()
_conditions.install()
_incidents.install()

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
