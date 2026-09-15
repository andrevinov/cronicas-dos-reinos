#!/usr/bin/env python3
"""Fachada pública v2 da fronteira bidirecional entre sidequest e cânone."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from _sidequest_facade import combine_checks
import canon_bridge_runtime as _bridge
import mundo
import sidequests_canonicas as _canonical

FACADE_SCHEMA = 2
MODULE_ID = "canonical_quest_integration"
IMPLEMENTATION_VERSION = "2.0.0"
EVALUATION_VERSION = "4.0.0"
ASSESSMENT_SCHEMA = 1
CAPABILITIES = ("sidequest_to_canon_bridge", "canon_to_quest_opportunity")
LEGACY_ALIASES = ("canon_bridge", "canonical_secret_quests")
LEGACY_COMPONENTS = ("canon_bridge_runtime", "sidequests_canonicas")

CanonBridgeRuntimeError = _bridge.CanonBridgeRuntimeError
CanonicalSidequestError = _canonical.CanonicalSidequestError
select_from_refs = _canonical.select_from_refs


def _assessment_id(value: dict[str, Any]) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "cqi-" + hashlib.sha256(raw).hexdigest()[:20]


def _mission_ref(mission_id: str) -> str:
    return "sqm-" + hashlib.sha256(mission_id.encode("utf-8")).hexdigest()[:16]


def assess_mission(
    repo: Path,
    mission_id: str,
    *,
    trigger: str,
) -> dict[str, Any]:
    """Emite um recibo seguro e objetivo da fronteira sidequest→cânone.

    O recibo não publica intenção, evento ou segredo canônico. Ele prova apenas
    se a missão exigia uma operação da ponte e se o ledger Task42 contém o
    resultado estrutural esperado. Ausência do recibo é tratada pelo avaliador
    como falha de instrumentação, nunca como N/D.
    """

    if trigger not in {"oferta", "resposta", "progresso", "terminal"}:
        raise CanonBridgeRuntimeError(f"gatilho avaliativo inválido: {trigger}")
    _, _, mission = _bridge._mission(repo, mission_id)
    canonical_origin = mission.get("origem") == "sidequest_canonica"
    legacy_unclassified = False
    if canonical_origin:
        relation_mode = "origem_canonica"
        candidate = False
        bridge_state = {"reservas": {}, "resolucoes": {}, "historico_recente": []}
    else:
        try:
            document, _ = _bridge.canon_bridge._quest_document(repo, mission)
            relation = document.get("relacao_canone") or {}
            relation_mode = str(relation.get("modo") or "")
            if not relation_mode:
                # Migrações históricas podem preservar uma missão anterior ao
                # contrato Task41 sem inventar retroativamente sua relação.
                relation_mode = "legado_sem_contrato"
                legacy_unclassified = True
            elif relation_mode not in {
                "lateral",
                *set(_bridge.canon_bridge.RELATION_TO_MODE),
            }:
                raise _bridge.canon_bridge.CanonBridgeError(
                    f"relação canônica desconhecida: {relation_mode or 'ausente'}"
                )
            candidate = relation_mode != "lateral"
            bridge_state = (
                _bridge.canon_bridge.load_state(repo)
                if _bridge.canon_bridge.configured(repo)
                else {"reservas": {}, "resolucoes": {}, "historico_recente": []}
            )
        except _bridge.canon_bridge.CanonBridgeError as exc:
            raise CanonBridgeRuntimeError(str(exc)) from exc

    reserved = any(
        isinstance(item, dict) and item.get("mission_id") == mission_id
        for item in bridge_state.get("reservas", {}).values()
    )
    resolved = any(
        isinstance(item, dict) and item.get("mission_id") == mission_id
        for item in bridge_state.get("resolucoes", {}).values()
    )
    history_types = [
        str(item.get("tipo"))
        for item in bridge_state.get("historico_recente") or []
        if isinstance(item, dict) and item.get("mission_id") == mission_id
    ]
    latest_history = history_types[-1] if history_types else None
    state = str(mission.get("estado") or "")

    if canonical_origin or legacy_unclassified:
        eligibility = "nao_elegivel"
        expected_operation = "nenhuma"
        scoreable = False
    elif trigger == "oferta":
        eligibility = "nao_elegivel"
        expected_operation = "nenhuma_antes_do_aceite"
        scoreable = False
    elif trigger == "resposta" and state == "aceita" and candidate:
        eligibility = "elegivel"
        expected_operation = "reserva_canonica"
        scoreable = True
    elif trigger == "progresso" and state == "aceita" and candidate:
        eligibility = "elegivel"
        expected_operation = "preservar_reserva"
        scoreable = False
    elif trigger == "terminal" and candidate:
        eligibility = "elegivel"
        expected_operation = "resolver_reserva"
        scoreable = True
    else:
        eligibility = "nao_elegivel"
        expected_operation = "nenhuma"
        scoreable = trigger in {"resposta", "terminal"}

    if reserved:
        observed_operation = "reserva_ativa"
    elif resolved:
        observed_operation = "resolucao_canonica"
    elif latest_history in {
        "reserva_liberada",
        "reserva_aguarda_evidencia",
        "reserva_revertida",
    }:
        observed_operation = latest_history
    elif latest_history == "reserva_criada":
        observed_operation = "reserva_criada"
    else:
        observed_operation = "nenhuma"

    acceptable = {
        "nenhuma_antes_do_aceite": {"nenhuma"},
        "nenhuma": {"nenhuma"},
        "reserva_canonica": {
            "reserva_ativa",
            "reserva_criada",
            "reserva_aguarda_evidencia",
            "resolucao_canonica",
        },
        "preservar_reserva": {
            "reserva_ativa",
            "reserva_aguarda_evidencia",
            "resolucao_canonica",
        },
        "resolver_reserva": {
            "reserva_liberada",
            "reserva_aguarda_evidencia",
            "resolucao_canonica",
        },
    }
    matched = observed_operation in acceptable[expected_operation]
    if eligibility == "elegivel":
        classification = "verdadeiro_positivo" if matched else "falso_negativo"
    else:
        classification = (
            "verdadeiro_negativo" if matched else "falso_positivo"
        )
    # Reavaliações intermediárias provam cobertura, mas não multiplicam acertos.
    # Uma reserva perdida durante o progresso, porém, é uma falha real e pontua.
    if trigger == "progresso" and classification == "falso_negativo":
        scoreable = True
    reported_classification = classification if scoreable else "indeterminado"
    reasons = [
        "contrato_classificado_em_dominio_reservado",
        "ledger_task42_consultado",
    ]
    if not matched:
        reasons.append("operacao_esperada_nao_comprovada")

    identity = {
        "mission_id": mission_id,
        "quest_id": mission.get("quest_id"),
        "trigger": trigger,
        "mission_state": state,
        "relation_mode": relation_mode,
        "expected_operation": expected_operation,
        "observed_operation": observed_operation,
    }
    return {
        "schema_avaliacao_integracao_canonica": ASSESSMENT_SCHEMA,
        "assessment_id": _assessment_id(identity),
        "module_id": MODULE_ID,
        "capability_id": (
            "canon_to_quest_opportunity"
            if canonical_origin
            else "sidequest_to_canon_bridge"
        ),
        "versao_implementacao": IMPLEMENTATION_VERSION,
        "versao_avaliacao": EVALUATION_VERSION,
        "mission_ref": _mission_ref(mission_id),
        "gatilho": trigger,
        "classificacao": reported_classification,
        "incluida_na_pontuacao": scoreable,
        "recibo_completo": True,
        "motivos": reasons,
    }


def _assess_canonical_offer(quest_id: str, result: dict[str, Any]) -> dict[str, Any]:
    mission = result.get("missao") or {}
    mission_id = str(mission.get("id") or _canonical.mission_id(quest_id))
    outcome = str(result.get("resultado") or "")
    scoreable = outcome == "oferecida"
    identity = {
        "mission_id": mission_id,
        "quest_id": quest_id,
        "trigger": "oferta_canonica",
        "outcome": outcome,
        "reopening": result.get("reabertura") is True,
    }
    return {
        "schema_avaliacao_integracao_canonica": ASSESSMENT_SCHEMA,
        "assessment_id": _assessment_id(identity),
        "module_id": MODULE_ID,
        "capability_id": "canon_to_quest_opportunity",
        "versao_implementacao": IMPLEMENTATION_VERSION,
        "versao_avaliacao": EVALUATION_VERSION,
        "mission_ref": _mission_ref(mission_id),
        "gatilho": "oferta",
        "classificacao": "verdadeiro_positivo" if scoreable else "indeterminado",
        "incluida_na_pontuacao": scoreable,
        "recibo_completo": True,
        "motivos": [
            "gate_canonico_revalidado",
            "oferta_materializada_sem_expor_fonte_reservada",
        ]
        if scoreable
        else ["replay_de_oferta_ja_avaliada"],
    }


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

    result = _canonical.offer(repo, quest_id, npc_id=npc_id, local=local, now=now)
    result["avaliacoes_integracao_canonica"] = [
        _assess_canonical_offer(quest_id, result)
    ]
    mission = result.get("missao") or {}
    mission_id = mission.get("id")
    if mission_id:
        result["proximo_passo"] = (
            "canonical_quest_integration.py responder "
            f"{mission_id} aceitar|adiar|recusar"
        )
    return result


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
    result = _bridge.respond(repo, mission_id, response, now=now)
    result["avaliacoes_integracao_canonica"] = [
        assess_mission(repo, mission_id, trigger="resposta")
    ]
    return result


def finish(
    repo: Path,
    mission_id: str,
    outcome: str,
    *,
    reason: str,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    result = _bridge.finish(repo, mission_id, outcome, reason=reason, now=now)
    result["avaliacoes_integracao_canonica"] = [
        assess_mission(repo, mission_id, trigger="terminal")
    ]
    return result


def abandon(
    repo: Path,
    mission_id: str,
    *,
    reason: str,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    result = _bridge.abandon(repo, mission_id, reason=reason, now=now)
    result["avaliacoes_integracao_canonica"] = [
        assess_mission(repo, mission_id, trigger="terminal")
    ]
    return result


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
            "implementation_version": IMPLEMENTATION_VERSION,
            "evaluation_version": EVALUATION_VERSION,
            "assessment_receipt_required_per_quest_activity": True,
            "missing_receipt_can_be_nd": False,
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
