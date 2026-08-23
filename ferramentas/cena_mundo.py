#!/usr/bin/env python3
"""Porta de cena transacional com Side Quest Gate v2 no encontro dirigido."""
from __future__ import annotations

import cena_mundo_v4 as _v4
import sidequest_gate_v2 as _gate_v2

for _name in dir(_v4):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_v4, _name)

# A cena permanece na v4: apenas a porta de encontro usada por ela é adaptada.
_v4._core.interacoes_mundo.encounter_event = _gate_v2.encounter_event

prepare_scene = _v4.prepare_scene
confirm_scene = _v4.confirm_scene
open_scene = _v4.open_scene
build_parser = _v4.build_parser
main = _v4.main

if __name__ == "__main__":
    raise SystemExit(main())
