#!/usr/bin/env python3
"""Fachada pública v2 da fronteira bidirecional entre sidequest e cânone."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

from _sidequest_facade import combine_checks
import canon_bridge_runtime as _bridge
import mundo
import sidequests_canonicas as _canonical

FACADE_SCHEMA = 2
MODULE_ID = "canonical_quest_integration"
CAPABILITIES = ("sidequest_to_canon_bridge", "canon_to_quest_opportunity")
LEGACY_ALIASES = ("canon_bridge", "canonical_secret_quests")
LEGACY_COMPONENTS = ("canon_bridge_runtime", "sidequests_canonicas")

CanonBridgeRuntimeError = _bridge.CanonBridgeRuntimeError
CanonicalSidequestError = _canonical.CanonicalSidequestError
select_from_refs = _canonical.select_from_refs


def project_canonical_opportunity(
    repo: Path,
    npc_id: str,
    *,
    local: str | None = None,
    now: mundo.WorldInstant | None = None,
    diagnostics: bool = False,
) -> dict[str, Any]:
    """Projeta uma oportunidade autorizada sem oferecer ou revelar seus detalhes."""

    return _canonical.evaluate_for_npc(
        repo,
        npc_id,
        local=local,
        now=now,
        diagnostics=diagnostics,
    )


def materialize_canonical_offer(
    repo: Path,
    quest_id: str,
    *,
    npc_id: str,
    local: str | None = None,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    """Registra somente uma oferta canônica já narrada; nunca a aceita por Ren."""

    return _canonical.offer(repo, quest_id, npc_id=npc_id, local=local, now=now)


def select_canonical_from_refs(
    repo: Path,
    refs: list[dict[str, Any]],
    *,
    local_id: str | None = None,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    """Resolve somente referências opacas já entregues por encontro elegível."""

    return select_from_refs(repo, refs, local_id=local_id, now=now)


def effects_for_mission(repo: Path, mission_id: str) -> dict[str, Any]:
    return _canonical.effects_for_mission(repo, mission_id)


def respond(
    repo: Path,
    mission_id: str,
    response: str,
    *,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    return _bridge.respond(repo, mission_id, response, now=now)


def finish(
    repo: Path,
    mission_id: str,
    outcome: str,
    *,
    reason: str,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    return _bridge.finish(repo, mission_id, outcome, reason=reason, now=now)


def abandon(
    repo: Path,
    mission_id: str,
    *,
    reason: str,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    return _bridge.abandon(repo, mission_id, reason=reason, now=now)


reconcile = _bridge.reconcile
reconcile_world = _bridge.reconcile_world


def check(repo: Path) -> dict[str, Any]:
    return combine_checks(
        repo,
        module_id=MODULE_ID,
        capabilities=CAPABILITIES,
        legacy_components=LEGACY_COMPONENTS,
        checks=(
            ("sidequest_to_canon_bridge", _bridge.check),
            ("canon_to_quest_opportunity", _canonical.check),
        ),
        contract={
            "canonical_source_required": True,
            "literal_evidence_required": True,
            "secret_discovery_required": True,
            "controls_ren": False,
            "edits_base_canon": False,
            "additional_scheduler": False,
            "destructive_state_migration": False,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    project = sub.add_parser("avaliar")
    project.add_argument("npc_id")
    project.add_argument("--local")
    offer = sub.add_parser("oferecer")
    offer.add_argument("quest_id")
    offer.add_argument("--npc", required=True)
    offer.add_argument("--local")
    effects = sub.add_parser("efeitos")
    effects.add_argument("mission_id")
    response = sub.add_parser("responder")
    response.add_argument("mission_id")
    response.add_argument("resposta", choices=["aceitar", "adiar", "recusar"])
    finish_parser = sub.add_parser("finalizar")
    finish_parser.add_argument("mission_id")
    finish_parser.add_argument("resultado", choices=["concluida", "falhada", "expirada"])
    finish_parser.add_argument("--motivo", required=True)
    abandoned = sub.add_parser("abandonar")
    abandoned.add_argument("mission_id")
    abandoned.add_argument("--motivo", required=True)
    sub.add_parser("reconciliar")
    sub.add_parser("check")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "avaliar":
            result = project_canonical_opportunity(repo, args.npc_id, local=args.local)
        elif args.cmd == "oferecer":
            result = materialize_canonical_offer(
                repo,
                args.quest_id,
                npc_id=args.npc,
                local=args.local,
            )
        elif args.cmd == "efeitos":
            result = effects_for_mission(repo, args.mission_id)
        elif args.cmd == "responder":
            result = respond(repo, args.mission_id, args.resposta)
        elif args.cmd == "finalizar":
            result = finish(repo, args.mission_id, args.resultado, reason=args.motivo)
        elif args.cmd == "abandonar":
            result = abandon(repo, args.mission_id, reason=args.motivo)
        elif args.cmd == "reconciliar":
            result = reconcile(repo)
        else:
            result = check(repo)
    except (
        CanonBridgeRuntimeError,
        CanonicalSidequestError,
        mundo.WorldEngineError,
        OSError,
        yaml.YAMLError,
    ) as exc:
        result = {
            "schema_fachada_modular": FACADE_SCHEMA,
            "module_id": MODULE_ID,
            "ok": False,
            "erro": str(exc),
        }
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 2
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
