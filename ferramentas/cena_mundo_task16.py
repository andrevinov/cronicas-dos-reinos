#!/usr/bin/env python3
"""Compatibilidade temporária da Task 16; a porta pública aponta para cena_mundo_v5."""
from __future__ import annotations

import cena_mundo_v5 as _v5
import sidequest_gate_v2 as _gate_v2

for _name in dir(_v5):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_v5, _name)

_v5._core.interacoes_mundo.encounter_event = _gate_v2.encounter_event

prepare_scene = _v5.prepare_scene
confirm_scene = _v5.confirm_scene
open_scene = _v5.open_scene
build_parser = _v5.build_parser
main = _v5.main
