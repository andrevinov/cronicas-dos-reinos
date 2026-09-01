#!/usr/bin/env python3
"""Porta pública/recovery da integração Task46.

O estado de oportunidades é o commit point da instalação: os quatro fragmentos
reservados podem ser reparados idempotentemente, mas a missão só passa a existir
depois que todos eles estão presentes e íntegros.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

import sidequests_integracao as _base

for _name in dir(_base):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_base, _name)


def writer_transaction(transaction: dict[str, Any]) -> dict[str, Any]:
    """Remove o envelope reservado Task46 antes do writer canônico do turno."""
    clean = copy.deepcopy(transaction)
    clean.pop(_base.TRANSACTION_KEY, None)
    return clean


def prepare_installation(
    repo: Path,
    *,
    package: dict[str, Any],
    block: dict[str, Any],
    offer_scene_id: str,
    offer_summary: str,
) -> dict[str, Any]:
    """Reusa Task41–45 e mantém ponteiros compactos na missão."""
    plan = _base.prepare_installation(
        repo,
        package=package,
        block=block,
        offer_scene_id=offer_scene_id,
        offer_summary=offer_summary,
    )
    plan = copy.deepcopy(plan)
    plan["mission"]["contrato_adversarial"] = plan["adversarial_path"]
    return plan


def install(repo: Path, journal: dict) -> dict:
    """Instala uma sidequest em uma única transação Task46 recuperável."""
    journal = _base._freeze_targets(repo, journal)
    changed: list[str] = []

    # Fragmentos reservados primeiro. Retry aceita somente bytes idênticos.
    for target in journal["targets"][:-1]:
        rel = Path(str(target["path"]))
        path = repo / rel
        content = str(target["content"])
        if path.is_file():
            if path.read_text(encoding="utf-8") != content:
                raise _base.EmergentSidequestIntegrationError(
                    f"alvo Task46 divergiu durante instalação: {rel.as_posix()}"
                )
            continue
        _base._atomic_text(path, content)
        changed.append(rel.as_posix())

    # O estado compacto é o commit point e entra por último.
    state_target = journal["targets"][-1]
    state_path = repo / Path(str(state_target["path"]))
    desired_state = str(state_target["content"])
    current_text = state_path.read_text(encoding="utf-8") if state_path.is_file() else ""
    if current_text != desired_state:
        try:
            current = _base.oportunidades.load_state(
                repo, _base.oportunidades.load_index(repo)
            )
        except _base.oportunidades.OpportunityError as exc:
            raise _base.EmergentSidequestIntegrationError(str(exc)) from exc
        mid = journal["plan"]["mission_id"]
        existing = current["missoes"].get(mid)
        if isinstance(existing, dict):
            if existing != journal["plan"]["mission"]:
                raise _base.EmergentSidequestIntegrationError(
                    "missão Task46 já existe com conteúdo divergente"
                )
        else:
            frozen = yaml.safe_load(desired_state)
            without = copy.deepcopy(frozen)
            without["missoes"].pop(mid, None)
            without["historico_recente"] = [
                item
                for item in without.get("historico_recente") or []
                if not (
                    isinstance(item, dict)
                    and item.get("id") == mid
                    and item.get("tipo") == "sidequest_emergente_materializada_task46"
                )
            ]
            if current != without:
                raise _base.EmergentSidequestIntegrationError(
                    "estado de oportunidades mudou durante instalação Task46; repita após reconciliar"
                )
            _base._atomic_text(state_path, desired_state)
            changed.append(_base.oportunidades.STATE.as_posix())

    (repo / _base.JOURNAL).unlink(missing_ok=True)
    return {
        "ok": True,
        "resultado": "sidequest_materializada",
        "mission_id": journal["plan"]["mission_id"],
        "quest_id": journal["plan"]["quest_id"],
        "transacao_instalacao": journal["id"],
        "arquivos_alterados": changed,
        "instalacoes_logicas": 1,
        "idempotente": True,
    }


def check(repo: Path) -> dict[str, Any]:
    """Congela os mesmos tetos da Task40 sem abrir conteúdo secreto novo."""
    errors: list[str] = []
    try:
        if _base.MAX_AUTHOR_PACKET_BYTES != _base.opportunity.MAX_PAYLOAD_BYTES:
            errors.append("teto Task46 do pacote autoral diverge da Task40")
        if _base.MAX_CANON_INTENTS != _base.opportunity.MAX_INTENT_FRAGMENTS:
            errors.append("teto Task46 de intenções diverge da Task40")
        index = _base.oportunidades.load_index(repo)
        if index.get("nova_origem_sidequests") not in {
            "emergente_causal_task40",
            "canonica_explicita",
        }:
            errors.append("origem operacional de sidequests desconhecida")
        journal = _base._load_journal(repo)
        if journal is not None and journal.get("schema_task46_journal") != _base.SCHEMA:
            errors.append("journal Task46 possui schema inesperado")
    except (
        _base.EmergentSidequestIntegrationError,
        _base.oportunidades.OpportunityError,
        OSError,
        yaml.YAMLError,
    ) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "erros": errors,
        "contrato": {
            "turno_neutro_leituras_task40_45": 0,
            "turno_sem_sidequest_ativa_leituras_task40_45": 0,
            "turno_com_sidequest_ativa_fragmentos_task45_max": 2,
            "decisao_negativa_autoria_task40_46": 0,
            "turno_neutro_fragmentos_emergentes": 0,
            "turno_neutro_horizonte_canonico": 0,
            "chamadas_orquestracao": 2,
            "pacote_autoral_max_bytes": _base.MAX_AUTHOR_PACKET_BYTES,
            "intencoes_max": _base.MAX_CANON_INTENTS,
            "instalacoes_por_oferta": 1,
            "schedulers_novos": 0,
            "relogios_novos": 0,
        },
    }


# A porta pública usa os wrappers corrigidos sem duplicar os motores 40–45.
globals()["prepare_installation"] = prepare_installation
globals()["install"] = install
globals()["check"] = check
