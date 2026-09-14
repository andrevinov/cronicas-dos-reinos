#!/usr/bin/env python3
"""Preflight até NV-22 + gate read-only da aceitação integrada de vivacidade."""
from __future__ import annotations

from pathlib import Path
import sys

_NV23_LEGACY_SOURCE = Path(__file__).with_name("_preflight_nv22.py")
_nv23_saved_name = globals().get("__name__", "preflight")
if _nv23_saved_name == "__main__":
    _nv23_exec_name = "_preflight_nv22_exec"
    sys.modules[_nv23_exec_name] = sys.modules[_nv23_saved_name]
    globals()["__name__"] = _nv23_exec_name
    try:
        exec(
            compile(
                _NV23_LEGACY_SOURCE.read_text(encoding="utf-8"),
                str(_NV23_LEGACY_SOURCE),
                "exec",
            ),
            globals(),
            globals(),
        )
    finally:
        globals()["__name__"] = _nv23_saved_name
else:
    exec(
        compile(
            _NV23_LEGACY_SOURCE.read_text(encoding="utf-8"),
            str(_NV23_LEGACY_SOURCE),
            "exec",
        ),
        globals(),
        globals(),
    )

_BASE_CHECKS_NV22 = checks

_SIDEQUEST_INTERNAL_CHECKS = {
    ("ferramentas/recompensas_sidequest.py", "check"),
    ("ferramentas/progressao_sidequests.py", "check"),
    ("ferramentas/sidequests_integracao_check.py",),
    ("ferramentas/sidequests_vivas.py", "check"),
    ("ferramentas/sidequests_ativas.py", "check"),
    ("ferramentas/progresso_sidequests_transacional.py", "check"),
    ("ferramentas/reacoes_sidequest.py", "check"),
    ("ferramentas/oportunidades.py", "check"),
    ("ferramentas/canon_bridge_runtime.py", "check"),
}

_WORLD_CAUSAL_INTERNAL_CHECKS = {
    ("ferramentas/pressao_narrativa.py", "check"),
}

_ADVERSARIAL_INTERNAL_CHECKS = {
    ("ferramentas/integridade_adversarial.py", "check"),
    ("ferramentas/operacoes_concorrentes.py", "check"),
}


def _consolidate_sidequest_checks(items):
    positions = [
        index
        for index, item in enumerate(items)
        if tuple(item.comando[1:]) in _SIDEQUEST_INTERNAL_CHECKS
    ]
    insert_at = min(positions) if positions else len(items)
    result = [
        item
        for item in items
        if tuple(item.comando[1:]) not in _SIDEQUEST_INTERNAL_CHECKS
    ]
    facades = [
        Check(
            "autoria modular de sidequests",
            (sys.executable, "ferramentas/sidequest_authoring.py", "check"),
            "mundo vivo",
        ),
        Check(
            "lifecycle modular de sidequests",
            (sys.executable, "ferramentas/sidequest_lifecycle.py", "check"),
            "mundo vivo",
        ),
        Check(
            "integração canônica modular de sidequests",
            (sys.executable, "ferramentas/canonical_quest_integration.py", "check"),
            "mundo vivo",
        ),
    ]
    result[insert_at:insert_at] = facades
    return result


def _consolidate_world_causal_checks(items):
    positions = [
        index
        for index, item in enumerate(items)
        if tuple(item.comando[1:]) in _WORLD_CAUSAL_INTERNAL_CHECKS
    ]
    insert_at = min(positions) if positions else len(items)
    result = [
        item
        for item in items
        if tuple(item.comando[1:]) not in _WORLD_CAUSAL_INTERNAL_CHECKS
    ]
    facades = [
        Check(
            "projeção espacial modular",
            (sys.executable, "ferramentas/scene_world_projection.py", "check"),
            "mundo vivo",
        ),
        Check(
            "fronteira modular do mundo",
            (sys.executable, "ferramentas/world_boundary_resolution.py", "check"),
            "mundo vivo",
        ),
        Check(
            "roteamento narrativo causal",
            (sys.executable, "ferramentas/causal_narrative_routing.py", "check"),
            "mundo vivo",
        ),
    ]
    result[insert_at:insert_at] = facades
    return result


def _consolidate_adversarial_checks(items):
    positions = [
        index
        for index, item in enumerate(items)
        if tuple(item.comando[1:]) in _ADVERSARIAL_INTERNAL_CHECKS
    ]
    insert_at = min(positions) if positions else len(items)
    result = [
        item
        for item in items
        if tuple(item.comando[1:]) not in _ADVERSARIAL_INTERNAL_CHECKS
    ]
    result.insert(
        insert_at,
        Check(
            "operações adversariais modulares",
            (sys.executable, "ferramentas/adversarial_operations.py", "check"),
            "mundo vivo",
        ),
    )
    return result


def _add_npc_continuity_check(items):
    if any(
        tuple(item.comando[1:])
        == ("ferramentas/npc_continuity_and_social_behavior.py", "check")
        for item in items
    ):
        return items
    result = list(items)
    gate = Check(
        "continuidade e comportamento social de NPCs",
        (
            sys.executable,
            "ferramentas/npc_continuity_and_social_behavior.py",
            "check",
        ),
        "mundo vivo",
    )
    insert_at = next(
        (i for i, item in enumerate(result) if item.nome == "experiência narrativa integrada"),
        len(result),
    )
    result.insert(insert_at, gate)
    return result


def checks(*, incluir_testes: bool = True):
    result = _add_npc_continuity_check(
        _consolidate_adversarial_checks(
            _consolidate_world_causal_checks(
                _consolidate_sidequest_checks(
                    _BASE_CHECKS_NV22(incluir_testes=incluir_testes)
                )
            )
        )
    )
    gate = Check(
        "aceitação integrada de vivacidade",
        (sys.executable, "ferramentas/aceitacao_vivacidade.py", "check"),
        "mundo vivo",
    )
    insert_at = next(
        (i for i, item in enumerate(result) if item.nome == "estado atual separado do histórico"),
        len(result),
    )
    result.insert(insert_at, gate)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
