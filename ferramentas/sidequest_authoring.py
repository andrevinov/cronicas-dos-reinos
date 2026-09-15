#!/usr/bin/env python3
"""Fachada pública v2 de autoria e materialização de sidequests.

Os motores das Tasks 40, 41 e 46 permanecem internos e compatíveis. Esta porta
é a dona pública do gate positivo/negativo, da âncora causal, do pacote autoral
e da instalação condicionada à oferta literalmente narrada.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any, Callable

import yaml

from _module_facade import attach_coverage
from _sidequest_facade import combine_checks
import canonical_quest_integration as _canonical_integration
import oportunidade_sidequest as _opportunity
import oportunidades as _registry
import sidequests_emergentes as _authoring
import sidequests_integracao_runtime as _integration
import sidequests_vivas as _live_causes

FACADE_SCHEMA = 2
MODULE_ID = "sidequest_authoring"
IMPLEMENTATION_VERSION = "2.0.1"
EVALUATION_VERSION = "4.0.0"
OPPORTUNITY_ASSESSMENT_SCHEMA = 1
CAPABILITIES = ("opportunity_gate", "quest_authoring", "fictional_materialization")
LEGACY_ALIASES = ("emergent_sidequest_opportunity", "emergent_sidequest_authoring")
LEGACY_COMPONENTS = (
    "oportunidade_sidequest",
    "oportunidades",
    "sidequests_emergentes",
    "sidequests_integracao_runtime",
    "sidequests_vivas",
)

# Compatibilidade de ticket/import durante a migração. O schema 2 é o da
# fachada; estes nomes continuam descrevendo o envelope Task46 já persistido.
SCHEMA = _integration.SCHEMA
TICKET_KEY = _integration.TICKET_KEY
TRANSACTION_KEY = _integration.TRANSACTION_KEY
JOURNAL = _integration.JOURNAL
MAX_AUTHOR_PACKET_BYTES = _integration.MAX_AUTHOR_PACKET_BYTES
MAX_COMBINED_PREP_BYTES = _integration.MAX_COMBINED_PREP_BYTES
MAX_CANON_INTENTS = _integration.MAX_CANON_INTENTS
EmergentSidequestIntegrationError = _integration.EmergentSidequestIntegrationError
SidequestAuthoringError = EmergentSidequestIntegrationError

# Pontos legados permanecem patcháveis por testes/recovery enquanto o cronica
# deixa de conhecer funções privadas do motor.
integrate_prepare = _integration.integrate_prepare
ticket_meta = _integration.ticket_meta
strip_ticket_payload = _integration.strip_ticket_payload
writer_transaction = _integration.writer_transaction
recover_matching_journal = _integration.recover_matching_journal
_plan_from_ticket = _integration._plan_from_ticket
_normalize_offer = _integration._normalize_offer
_map = _integration._map
prepare_installation = _integration.prepare_installation
begin_conclusion = _integration.begin_conclusion
install = _integration.install


def assess_opportunity(
    *,
    declared_signal: dict[str, Any] | None,
    routed: dict[str, Any],
    prepared: dict[str, Any],
) -> dict[str, Any]:
    """Produz verdade avaliativa sem tomar a declaração como prova de ausência.

    A fachada só decide automaticamente quando uma fonte estruturada consegue
    provar os predicados duros. Ausência de candidato dirigido não prova que a
    prosa da cena deixou de produzir uma âncora nova; esse caso permanece
    indeterminado para adjudicação posterior.
    """

    declaration = "oportunidade" if declared_signal is not None else "sem_oportunidade"
    effective_signal = routed.get("sinal_efetivo")
    effective_decision = "oportunidade" if isinstance(effective_signal, dict) else "sem_oportunidade"
    projection = routed.get("projecao") if isinstance(routed.get("projecao"), dict) else {}
    candidates = [item for item in projection.get("causas") or [] if isinstance(item, dict)]
    selected = routed.get("causa_viva")
    authored = isinstance(prepared.get("sidequest_emergente"), dict)
    projection_result = str(projection.get("resultado") or "")
    reasons: list[str]

    structured_live_cause = bool(
        isinstance(selected, dict)
        and (selected.get("alcance") or {}).get("alcança_ren") is True
        and isinstance(effective_signal, dict)
    )
    if authored or structured_live_cause:
        expected = "elegivel"
        reasons = ["ancora_causal_validada", "alcance_e_capacidade_validados"]
        if authored:
            reasons.append("contrato_autoral_preparado")
    elif projection_result == "limite_ativas":
        expected = "nao_elegivel"
        reasons = ["limite_de_missoes_ativas"]
    elif candidates and not isinstance(selected, dict):
        expected = "nao_elegivel"
        reasons = ["causa_estruturada_sem_alcance_atual"]
    else:
        expected = "indeterminado"
        reasons = ["ausencia_de_candidato_dirigido_nao_prova_ausencia_de_ancora_na_cena"]

    if expected == "elegivel":
        classification = (
            "verdadeiro_positivo"
            if effective_decision == "oportunidade"
            else "falso_negativo"
        )
    elif expected == "nao_elegivel":
        classification = (
            "falso_positivo"
            if effective_decision == "oportunidade"
            else "verdadeiro_negativo"
        )
    else:
        classification = "indeterminado"

    origin = str(routed.get("origem") or "") or None
    source_ref = None
    if isinstance(selected, dict):
        source_ref = str(selected.get("id") or selected.get("plano_id") or "") or None
    elif isinstance(effective_signal, dict):
        source_ref = str(
            effective_signal.get("origem_id") or effective_signal.get("plano_id") or ""
        ) or None

    return {
        "schema_avaliacao_oportunidade_sidequest": OPPORTUNITY_ASSESSMENT_SCHEMA,
        "module_id": MODULE_ID,
        "versao_implementacao": IMPLEMENTATION_VERSION,
        "versao_avaliacao": EVALUATION_VERSION,
        "declaracao": declaration,
        "decisao_efetiva": effective_decision,
        "resultado_esperado": expected,
        "classificacao": classification,
        "incluida_na_pontuacao": classification != "indeterminado",
        "candidatos_estruturados": len(candidates),
        "origem_estruturada": origin,
        "referencia_fonte": source_ref,
        "motivos": reasons,
    }


def prepare(
    repo: Path,
    base_result: dict[str, Any],
    *,
    signal: Any,
    decode_ticket: Callable[[str], dict[str, Any]],
    encode_ticket: Callable[[dict[str, Any]], tuple[str, str]],
    now: Any | None = None,
) -> dict[str, Any]:
    """Valida a oportunidade e anexa o pacote autoral na mesma preparação."""

    result = integrate_prepare(
        repo,
        base_result,
        signal_raw=signal,
        decode_ticket=decode_ticket,
        encode_ticket=encode_ticket,
        now=now,
    )
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="preparar_autoria",
        applicability=(
            "aplicavel" if result.get("sidequest_emergente") is not None
            else "nao_aplicavel"
        ),
    )


def prepare_conclusion(
    repo: Path,
    *,
    ticket_id: str,
    ticket_payload: dict[str, Any],
    ticket_meta_value: dict[str, Any],
    transaction: dict[str, Any],
) -> dict[str, Any]:
    """Congela a instalação antes do writer ou decide que não houve oferta."""

    journal = recover_matching_journal(
        repo,
        ticket_id=ticket_id,
        transaction=transaction,
    )
    if journal is None:
        package = _plan_from_ticket(repo, ticket_meta_value)
        block, offer = _normalize_offer(transaction)
        if block is None:
            result = {
                "schema_sidequest_authoring": FACADE_SCHEMA,
                "module_id": MODULE_ID,
                "resultado": "oferta_nao_materializada",
                "journal": None,
            }
            return attach_coverage(
                result,
                module_id=MODULE_ID,
                phase="concluir",
                applicability="nao_aplicavel",
            )
        scene = _map(ticket_payload.get("cena"), "ticket.cena")
        plan = prepare_installation(
            repo,
            package=package,
            block=block,
            offer_scene_id=str(scene.get("scene_id")),
            offer_summary=str(offer["resumo"]),
        )
        journal = begin_conclusion(
            repo,
            ticket_id=ticket_id,
            transaction=transaction,
            plan=plan,
        )
    result = {
        "schema_sidequest_authoring": FACADE_SCHEMA,
        "module_id": MODULE_ID,
        "resultado": "instalacao_preparada",
        "journal": copy.deepcopy(journal),
    }
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="concluir",
        applicability="aplicavel",
    )


def install_conclusion(repo: Path, prepared: dict[str, Any]) -> dict[str, Any]:
    """Instala exatamente uma oferta preparada ou devolve o gate neutro."""

    if prepared.get("schema_sidequest_authoring") != FACADE_SCHEMA:
        raise SidequestAuthoringError("plano da fachada sidequest_authoring inválido")
    if prepared.get("resultado") == "oferta_nao_materializada":
        result = {
            "resultado": "oferta_nao_materializada",
            "mutacoes_sidequest": 0,
            "regra": "oportunidade avaliada, mas nenhuma oferta foi narrada neste turno",
        }
        return attach_coverage(
            result,
            module_id=MODULE_ID,
            phase="instalar",
            applicability="nao_aplicavel",
        )
    journal = prepared.get("journal")
    if not isinstance(journal, dict):
        raise SidequestAuthoringError("instalação autoral sem journal congelado")
    result = install(repo, journal)
    mission_id = result.get("mission_id")
    if isinstance(mission_id, str) and mission_id:
        result["avaliacoes_integracao_canonica"] = [
            _canonical_integration.assess_mission(
                repo,
                mission_id,
                trigger="oferta",
            )
        ]
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="instalar",
        applicability="aplicavel",
    )


def check(repo: Path) -> dict[str, Any]:
    return combine_checks(
        repo,
        module_id=MODULE_ID,
        capabilities=CAPABILITIES,
        legacy_components=LEGACY_COMPONENTS,
        checks=(
            ("opportunity_gate", _opportunity.check),
            ("opportunity_registry", _registry.validate_repo),
            ("quest_authoring", _authoring.check),
            ("fictional_materialization", _integration.check),
            ("live_cause_routing", _live_causes.check),
        ),
        contract={
            "implementation_version": IMPLEMENTATION_VERSION,
            "evaluation_version": EVALUATION_VERSION,
            "objective_opportunity_assessment": True,
            "declaration_is_ground_truth": False,
            "indeterminate_is_scored": False,
            "negative_gate_opens_authoring": False,
            "unoffered_quest_materializes": False,
            "additional_orchestration_calls": 0,
            "new_scheduler": False,
            "new_rng": False,
            "destructive_state_migration": False,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("cmd", choices=["check"])
    args = parser.parse_args(argv)
    result = check(args.repo.resolve())
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
