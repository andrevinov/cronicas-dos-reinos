#!/usr/bin/env python3
"""Fachada pública v2 das operações adversariais.

Integridade de contrato e concorrência continuam sendo motores internos com os
mesmos arquivos, receipts e journals. Esta fachada publica uma única identidade
modular para proposta, compromisso, reserva, execução e consequência, sem criar
estado, scheduler, RNG ou writer paralelo.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

from _module_facade import combine_checks
import integridade_adversarial as _integrity
import operacoes_concorrentes as _operations

FACADE_SCHEMA = 2
MODULE_ID = "adversarial_operations"
CAPABILITIES = ("adversarial_contract_integrity", "concurrent_operations")
LEGACY_ALIASES = ("adversarial_integrity", "concurrent_adversarial_operations")
LEGACY_COMPONENTS = ("integridade_adversarial", "operacoes_concorrentes")

# A fachada referencia os donos existentes. Nenhum destes dados é copiado para
# um novo arquivo e nenhum contrato histórico precisa ser migrado.
SOURCE_OWNERSHIP = {
    "integrity_policy": _integrity.POLICY.as_posix(),
    "adversarial_contracts": _integrity.CONTRACTS_DIR.as_posix(),
    "operation_index": _operations.INDEX.as_posix(),
    "operation_control": _operations.STATE.as_posix(),
    "operation_contracts": _operations.GROUPS.as_posix(),
    "frozen_encounters": _operations.ENCOUNTERS.as_posix(),
    "recovery_journal": _operations.JOURNAL.as_posix(),
}

INTEGRITY_SCHEMA = _integrity.SCHEMA
OPERATIONS_SCHEMA = _operations.SCHEMA
POLICY = _integrity.POLICY
CONTRACTS_DIR = _integrity.CONTRACTS_DIR
ROOT = _operations.ROOT
INDEX = _operations.INDEX
STATE = _operations.STATE
GROUPS = _operations.GROUPS
ENCOUNTERS = _operations.ENCOUNTERS
JOURNAL = _operations.JOURNAL
MAX_GROUPS = _operations.MAX_GROUPS
MAX_OPERATIONS = _operations.MAX_OPERATIONS
MAX_CHANNELS = _operations.MAX_CHANNELS
MAX_GROUP_BYTES = _operations.MAX_GROUP_BYTES
MAX_ENCOUNTER_BYTES = _operations.MAX_ENCOUNTER_BYTES
MAX_PREP_BYTES = _operations.MAX_PREP_BYTES

AdversarialIntegrityError = _integrity.AdversarialIntegrityError
ConcurrentOperationError = _operations.ConcurrentOperationError
ADVERSARIAL_OPERATION_ERRORS = (AdversarialIntegrityError, ConcurrentOperationError)


def _front_count(result: dict[str, Any], proposal: Any = None) -> int | None:
    if isinstance(proposal, dict) and isinstance(proposal.get("operacoes"), list):
        return len(proposal["operacoes"])
    for key in ("operacoes", "operacoes_comprometidas"):
        rows = result.get(key)
        if isinstance(rows, list):
            blocked = result.get("operacoes_bloqueadas") or []
            return len(rows) + (len(blocked) if key == "operacoes_comprometidas" else 0)
    return None


def _event(
    result: dict[str, Any],
    *,
    kind: str,
    outcome: str,
    effect: bool,
    proposal: Any = None,
) -> dict[str, Any]:
    """Anexa telemetria observável sem alterar o envelope persistido."""

    count = _front_count(result, proposal)
    event = {
        **result,
        "schema_adversarial_operations": FACADE_SCHEMA,
        "module_id": MODULE_ID,
        "evento_modular": kind,
        "resultado_modular": outcome,
        "efeito_materializado": effect,
    }
    if count is not None:
        event["quantidade_frentes"] = count
        event["operacoes_simultaneas"] = count > 1
    return event


# Contrato de integridade Task44: API pública mantida sob o módulo pai.
agent_option = _integrity.agent_option
agent_conditional_escalation = _integrity.agent_conditional_escalation
normalize_contract = _integrity.normalize_contract
load_contract = _integrity.load_contract
sidequest_authority = _integrity.sidequest_authority
authorize_sidequest_consequence = _integrity.authorize_sidequest_consequence
authorize_external_consequence = _integrity.authorize_external_consequence
resolve_escalation_choice = _integrity.resolve_escalation_choice


def prepare_contract(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Congela capacidade, conhecimento, risco e limites antes da escolha."""

    result = _integrity.prepare(*args, **kwargs)
    return _event(
        result,
        kind="consulta",
        outcome="contrato_adversarial_validado",
        effect=False,
    )


def materialize_contract(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Persiste o contrato validado no writer histórico já existente."""

    result = _integrity.materialize(*args, **kwargs)
    retry = result.get("resultado") == "ja_materializado"
    return _event(
        result,
        kind="consulta" if retry else "compromisso",
        outcome="retry_sem_duplicacao" if retry else "contrato_adversarial_materializado",
        effect=False,
    )


def contract_preparation_id(
    quest_id: str,
    contract: dict[str, Any],
    sources: list[str],
    repo: Path,
) -> str:
    return _integrity._prep_id(quest_id, contract, sources, repo)


def contract_path(quest_id: str) -> Path:
    return _integrity._contract_path(quest_id)


def contract_digest(contract: dict[str, Any]) -> str:
    return _integrity._digest(contract)


# Lifecycle Task51: uma operação simples e várias frentes atravessam esta mesma
# porta; ``operacoes_simultaneas`` apenas identifica a subcapacidade exercida.
def configured(repo: Path) -> bool:
    return _operations.configured(repo)


def prepare(repo: Path, proposal: Any) -> dict[str, Any]:
    result = _operations.prepare(repo, proposal)
    return _event(
        result,
        kind="consulta",
        outcome="proposta_adversarial_validada",
        effect=False,
        proposal=proposal,
    )


def materialize(
    repo: Path,
    proposal: Any,
    preparation_id: str,
    *,
    fail_after: int | None = None,
) -> dict[str, Any]:
    result = _operations.materialize(
        repo,
        proposal,
        preparation_id,
        fail_after=fail_after,
    )
    retry = result.get("resultado") == "ja_materializado"
    return _event(
        result,
        kind="consulta",
        outcome="retry_sem_duplicacao" if retry else "proposta_adversarial_materializada",
        effect=False,
        proposal=proposal,
    )


def reconcile(repo: Path, now: Any = None) -> dict[str, Any]:
    result = _operations.reconcile(repo, now=now)
    return _event(
        result,
        kind="consulta",
        outcome="janela_adversarial_reavaliada",
        effect=False,
    )


def project_group_pending(repo: Path, pending: dict[str, Any]) -> dict[str, Any]:
    result = _operations.project_group_pending(repo, pending)
    return _event(
        result,
        kind="consulta",
        outcome="grupo_adversarial_projetado",
        effect=False,
    )


def commit_group(
    repo: Path,
    group_id: str,
    blockers: Any = None,
    *,
    fail_after: int | None = None,
    validate_only: bool = False,
) -> dict[str, Any]:
    result = _operations.commit_group(
        repo,
        group_id,
        blockers,
        fail_after=fail_after,
        validate_only=validate_only,
    )
    retry = result.get("resultado") == "ja_comprometido"
    validation = validate_only or result.get("mutante") is False
    return _event(
        result,
        kind="consulta" if retry or validation else "compromisso",
        outcome=(
            "compromisso_validado_sem_mutacao"
            if validation
            else "retry_sem_duplicacao"
            if retry
            else "operacao_adversarial_comprometida"
        ),
        effect=False,
    )


def project_operation_pending(repo: Path, pending: dict[str, Any]) -> dict[str, Any]:
    result = _operations.project_operation_pending(repo, pending)
    return _event(
        result,
        kind="consulta",
        outcome="operacao_adversarial_projetada",
        effect=False,
    )


def reconstruct_operation_pending(
    contract: dict[str, Any], operation: dict[str, Any]
) -> dict[str, Any]:
    """Reconstrói a identidade determinística da pendência já comprometida."""

    return _operations._operation_pending(contract, operation)


def normalize_blockers(
    repo: Path,
    raw: Any,
    operation_ids: set[str],
) -> dict[str, dict[str, Any]]:
    return _operations._normalized_blockers(repo, raw, operation_ids)


def project_operation_snapshot(
    repo: Path,
    operation_id: str,
    *,
    allow_resolved: bool = False,
) -> dict[str, Any]:
    """Revalida contrato e encontro congelados para retry dirigido.

    A projeção é reservada. Chamadores nunca devem anexá-la diretamente à visão
    do jogador; para isso existe :func:`project_for_ren`.
    """

    contract, operation, row, source = operation_context(repo, operation_id)
    allowed = {"comprometida", "resolvida"} if allow_resolved else {"comprometida"}
    if row.get("estado") not in allowed:
        raise ConcurrentOperationError("operação não possui snapshot comprometido")
    encounter_rel = _operations._encounter_rel(operation_id)
    encounter_source = encounter_rel.as_posix()
    encounter = _operations._load(repo / encounter_rel, encounter_source)
    if (
        encounter.get("schema_encontro_operacao") != OPERATIONS_SCHEMA
        or encounter.get("natureza") != "reservado"
        or encounter.get("operacao_id") != operation_id
        or encounter.get("encontro_digest")
        != _operations._digest(encounter.get("encontro"))
    ):
        raise ConcurrentOperationError("encontro congelado divergente")
    pending = reconstruct_operation_pending(contract, operation)
    return {
        "grupo_operacoes_id": contract["grupo_operacoes_id"],
        "operacao_id": operation_id,
        "estado": row["estado"],
        "local": operation["local"],
        "alvo": operation["alvo"],
        "objetivo": operation["objetivo"],
        "bloqueios_causais": operation["bloqueios_causais"],
        "sinais_perceptiveis": operation["sinais_perceptiveis"],
        "encontro": encounter["encontro"],
        "pendencia": pending,
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), source, encounter_source],
    }


def register_roll(repo: Path, operation_id: str, roll_id: str) -> dict[str, Any]:
    result = _operations.register_roll(repo, operation_id, roll_id)
    retry = result.get("resultado") == "ja_registrada"
    return _event(
        result,
        kind="consulta" if retry else "compromisso",
        outcome="retry_sem_duplicacao" if retry else "mecanica_adversarial_congelada",
        effect=False,
    )


def resolve_operation(
    repo: Path,
    operation_id: str,
    proof: Any,
    result: str,
    *,
    desfecho: str | None = None,
    fail_after: int | None = None,
) -> dict[str, Any]:
    resolved = _operations.resolve_operation(
        repo,
        operation_id,
        proof,
        result,
        desfecho=desfecho,
        fail_after=fail_after,
    )
    retry = resolved.get("resultado") == "ja_resolvida"
    return _event(
        resolved,
        kind="consulta" if retry else "efeito_material",
        outcome="retry_sem_duplicacao" if retry else "operacao_adversarial_resolvida",
        effect=not retry,
    )


def deliver_information(
    repo: Path,
    operation_id: str,
    channel_id: str,
    facts: list[str],
    proof: Any,
    now: Any = None,
) -> dict[str, Any]:
    result = _operations.deliver_information(
        repo,
        operation_id,
        channel_id,
        facts,
        proof,
        now=now,
    )
    retry = result.get("resultado") == "ja_entregue"
    return _event(
        result,
        kind="consulta" if retry else "efeito_material",
        outcome="retry_sem_duplicacao" if retry else "consequencia_informacional_entregue",
        effect=not retry,
    )


def project_for_ren(
    repo: Path,
    group_id: str,
    *,
    local: str | None,
    now: Any = None,
) -> dict[str, Any]:
    result = _operations.project_for_ren(repo, group_id, local=local, now=now)
    return _event(
        result,
        kind="consulta",
        outcome="percepcao_limitada_projetada",
        effect=False,
    )


def operation_context(
    repo: Path,
    operation_id: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    """Consulta interna dirigida, sem expor o estado reservado ao jogador."""

    return _operations._operation_context(repo, operation_id)


def operation_control_state(repo: Path) -> dict[str, Any]:
    return _operations._load_state(repo)


def validate_causal_proof(repo: Path, raw: Any, label: str) -> dict[str, str]:
    return _operations._proof(repo, raw, label)


def reservation_is_active(repo: Path, key: str) -> bool:
    return key in operation_control_state(repo)["reservas_exclusivas"]


def check(repo: Path) -> dict[str, Any]:
    report = combine_checks(
        repo,
        module_id=MODULE_ID,
        capabilities=CAPABILITIES,
        legacy_components=LEGACY_COMPONENTS,
        checks=(
            ("adversarial_contract_integrity", _integrity.validate_repo),
            ("concurrent_operations", _operations.check),
        ),
        contract={
            "capability_knowledge_risk_frozen_before_player_choice": True,
            "difficulty_or_result_changes_after_roll": False,
            "canonical_direction_authorizes_execution": False,
            "blocked_alternative_becomes_fact_from_prepare": False,
            "exclusive_actor_or_resource_can_be_duplicated": False,
            "reserved_assessment_exposed_to_player": False,
            "resolution_order_changes_committed_results": False,
            "additional_orchestration_calls": 0,
            "new_scheduler": False,
            "parallel_state": False,
            "historical_contract_rewrite": False,
        },
    )
    diagnostics = list(report["erros"])
    integrity_ok = report["componentes"]["adversarial_contract_integrity"].get("ok") is True
    operations_ok = report["componentes"]["concurrent_operations"].get("ok") is True
    report["avaliacao_guardrail"] = {
        "schema_avaliacao_guardrail": 1,
        "contrato": "adversarial_contract_integrity",
        "estado": "ok" if not diagnostics else "violado",
        "participa_media_modular": False,
        "guardrails_catalogo": {
            "player_agency": "indeterminado",
            "knowledge_secrecy": "ok" if integrity_ok else "violado",
            "roll_integrity": "ok" if operations_ok else "violado",
            "canonical_consistency": (
                "ok" if integrity_ok and operations_ok else "violado"
            ),
        },
        "violacoes": diagnostics,
    }
    return report


def _stdin(*, optional: bool = False) -> Any:
    raw = sys.stdin.read()
    if not raw.strip():
        if optional:
            return None
        raise ConcurrentOperationError("comando exige YAML/JSON em stdin")
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ConcurrentOperationError(str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("preparar")
    material = sub.add_parser("materializar")
    material.add_argument("--preparacao-id", required=True)
    commit = sub.add_parser("comprometer")
    commit.add_argument("grupo_operacoes_id")
    roll = sub.add_parser("registrar-rolagem")
    roll.add_argument("operacao_id")
    roll.add_argument("roll_id")
    resolve = sub.add_parser("resolver")
    resolve.add_argument("operacao_id")
    resolve.add_argument("--resultado", required=True)
    resolve.add_argument("--desfecho", choices=("sucesso", "falha", "parcial"))
    deliver = sub.add_parser("entregar-informacao")
    deliver.add_argument("operacao_id")
    deliver.add_argument("canal_id")
    deliver.add_argument("fatos", nargs="+")
    show = sub.add_parser("percepcao-ren")
    show.add_argument("grupo_operacoes_id")
    show.add_argument("--local")
    agent = sub.add_parser("agente")
    agent.add_argument("actor_id")
    agent.add_argument("capability_id")
    sub.add_parser("reconciliar")
    sub.add_parser("check")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "preparar":
            result = prepare(repo, _stdin())
        elif args.cmd == "materializar":
            result = materialize(repo, _stdin(), args.preparacao_id)
        elif args.cmd == "comprometer":
            result = commit_group(repo, args.grupo_operacoes_id, _stdin(optional=True))
        elif args.cmd == "registrar-rolagem":
            result = register_roll(repo, args.operacao_id, args.roll_id)
        elif args.cmd == "resolver":
            result = resolve_operation(
                repo,
                args.operacao_id,
                _stdin(),
                args.resultado,
                desfecho=args.desfecho,
            )
        elif args.cmd == "entregar-informacao":
            result = deliver_information(
                repo,
                args.operacao_id,
                args.canal_id,
                args.fatos,
                _stdin(),
            )
        elif args.cmd == "percepcao-ren":
            result = project_for_ren(
                repo,
                args.grupo_operacoes_id,
                local=args.local,
            )
        elif args.cmd == "agente":
            raw = agent_option(repo, args.actor_id, args.capability_id)
            result = _event(
                raw,
                kind="consulta",
                outcome="capacidade_adversarial_consultada",
                effect=False,
            )
        elif args.cmd == "reconciliar":
            result = reconcile(repo)
        else:
            result = check(repo)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result.get("ok", result.get("permitida", True)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
