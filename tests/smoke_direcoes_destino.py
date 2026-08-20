#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
TESTS = ROOT / "tests"
for path in (TOOLS, TESTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import direcoes_destino
from test_direcoes_destino import DestinosTest

case = DestinosTest(methodName="runTest")
case.setUp()
try:
    projection = direcoes_destino.project(case.repo, "ponte")
    assert projection["papel"] == "restricao_destino"
    assert projection["executavel"] is False
    assert projection["marco_atual"]["id"] == "pistas"
    prepared = direcoes_destino.prepare_advance(
        case.repo,
        "ponte",
        source="sessoes/010/consequencias.md",
        evidence="manifestos incompatíveis",
        note="fato-base sustenta o marco",
    )
    assert prepared["mutou_estado"] is False
    print("SMOKE DIRECOES DESTINO: OK")
finally:
    case.tearDown()
