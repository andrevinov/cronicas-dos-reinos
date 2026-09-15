#!/usr/bin/env python3
"""Fachada pública v2 do lifecycle transacional de sidequests aceitas."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Callable

import yaml

from _module_facade import attach_coverage
from _sidequest_facade import combine_checks
import progresso_sidequests_transacional as _transactional
import progressao_sidequests as _progression
import reacoes_sidequest as _reactions
import recompensas_sidequest as _rewards
import sidequests_ativas as _active

FACADE_SCHEMA = 2
MODULE_ID = "sidequest_lifecycle"
CAPABILITIES = (
    "active_reassessment",
    "transactional_progress",
    "phase_and_terminal_progression",
    "terminal_rewards",
    "success_reactions",
)
LEGACY_ALIASES = (
    "active_sidequest_reassessment",
    "transactional_sidequest_progress",
    "sidequest_progression",
    "quest_rewards",
    "sidequest_success_reactions",
)
LEGACY_COMPONENTS = (
    "sidequests_ativas",
    "progresso_sidequests_transacional",
    "progressao_sidequests",
    "recompensas_sidequest",
    "reacoes_sidequest",
)

# Compatibilidade dos envelopes já persistidos e dos testes de recovery.
SCHEMA = _active.SCHEMA
TICKET_KEY = _active.TICKET_KEY
TRANSACTION_KEY = _transactional.TRANSACTION_KEY
JOURNAL = _transactional.JOURNAL
RECEIPTS = _transactional.RECEIPTS
MAX_ACTIVE = _active.MAX_ACTIVE
MAX_PROJECTION_BYTES = _active.MAX_PROJECTION_BYTES
MAX_COMBINED_PREP_BYTES = _active.MAX_COMBINED_PREP_BYTES
ActiveSidequestError = _active.ActiveSidequestError
TransactionalSidequestProgressError = _transactional.TransactionalSidequestProgressError
SIDEQUEST_LIFECYCLE_ERRORS = (
    ActiveSidequestError,
    TransactionalSidequestProgressError,
)
SIDEQUEST_LIFECYCLE_CLI_ERRORS = SIDEQUEST_LIFECYCLE_ERRORS + (
    OSError,
    yaml.YAMLError,
)

ticket_meta = _active.ticket_meta
integrate_prepare = _active.integrate_prepare
require_no_open_journal = _transactional.require_no_open_journal
writer_transaction = _transactional.writer_transaction
prepare_conclusion = _transactional.prepare_conclusion
install = _transactional.install


def project(repo: Path) -> dict[str, Any]:
    result = _active.project(repo)
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="projetar",
        applicability=(
            "aplicavel" if int(result.get("quantidade") or 0) > 0
            else "nao_aplicavel"
        ),
    )


def query(repo: Path, reference: str) -> dict[str, Any]:
    result = _active.query(repo, reference)
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="status",
        applicability=(
            "aplicavel" if result.get("encontrada") is True
            else "nao_aplicavel"
        ),
    )


def prepare(
    repo: Path,
    base_result: dict[str, Any],
    *,
    decode_ticket: Callable[[str], dict[str, Any]],
    encode_ticket: Callable[[dict[str, Any]], tuple[str, str]],
) -> dict[str, Any]:
    """Projeta todas as missões aceitas sem escrever ou abrir autoria."""

    result = integrate_prepare(
        repo,
        base_result,
        decode_ticket=decode_ticket,
        encode_ticket=encode_ticket,
    )
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="preparar",
        applicability=(
            "aplicavel" if result.get("sidequests_ativas") is not None
            else "nao_aplicavel"
        ),
    )


def install_conclusion(
    repo: Path,
    prepared: dict[str, Any],
    *,
    transaction: dict[str, Any],
) -> dict[str, Any]:
    """Instala fatos, terminais e efeitos exactly-once pelo journal existente."""

    result = install(repo, prepared, transaction=transaction)
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="concluir",
        applicability="aplicavel",
    )


def check(repo: Path) -> dict[str, Any]:
    return combine_checks(
        repo,
        module_id=MODULE_ID,
        capabilities=CAPABILITIES,
        legacy_components=LEGACY_COMPONENTS,
        checks=(
            ("active_reassessment", _active.check),
            ("transactional_progress", _transactional.check),
            ("phase_and_terminal_progression", _progression.check),
            ("terminal_rewards", _rewards.check),
            ("success_reactions", _reactions.check),
        ),
        contract={
            "active_missions_forgotten": False,
            "progress_requires_literal_evidence": True,
            "terminal_effects_exactly_once": True,
            "reaction_reopens_mission": False,
            "writers_per_turn": 1,
            "additional_orchestration_calls": 0,
            "destructive_state_migration": False,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("projetar")
    status = sub.add_parser("status")
    status.add_argument("referencia")
    sub.add_parser("check")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "projetar":
            result = project(args.repo.resolve())
        elif args.cmd == "status":
            result = query(args.repo.resolve(), args.referencia)
        else:
            result = check(args.repo.resolve())
    except SIDEQUEST_LIFECYCLE_CLI_ERRORS as exc:
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
