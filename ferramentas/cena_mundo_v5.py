#!/usr/bin/env python3
"""Extensão da cena transacional com Side Quest Gate v2.

A v5 não duplica abertura, ecologia, microeventos ou stubs. Ela apenas troca a
porta dirigida de encontro pelo gate v2; todo o restante continua na v4/core.
"""
from __future__ import annotations

import cena_mundo_v4 as _v4
import sidequest_gate_v2

for _name in dir(_v4):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_v4, _name)

# v4.open_scene resolve o símbolo no módulo compartilhado interacoes_mundo em
# tempo de execução. Atribuir uma vez aqui mantém uma única implementação do
# hot path sem copiar a cena inteira.
_v4._core.interacoes_mundo.encounter_event = sidequest_gate_v2.encounter_event

prepare_scene = _v4.prepare_scene
confirm_scene = _v4.confirm_scene
open_scene = _v4.open_scene
build_parser = _v4.build_parser
main = _v4.main


if __name__ == "__main__":
    raise SystemExit(main())
