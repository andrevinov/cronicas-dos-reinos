#!/usr/bin/env python3
"""Ergonomia do hot path da CLI ``cronica`` observada em rollout real.

A camada não cria um segundo motor. Tickets reativos continuam delegando byte-logicamente
à Task 21. A única extensão é o ticket **neutro**: um turno sem entrada/exploração de
local, novo encontro de NPC ou tag contextual não precisa inventar um gatilho apenas
para obter o ticket de duas fases.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

import yaml

import _cronica_turn_core as core
import endpoints
import qualidade_abordagem
import rodape_turno
import turno

NEUTRAL_PREPARATION_PREFIX = "turn-neutral-"


def _local_flags(place: str | None, action: str | None, tier: int | None, danger: str | None) -> tuple[bool, bool]:
    supplied = (place is not None, action is not None, tier is not None, danger is not None)
    return any(supplied), all(supplied)


def _validate_local_contract(
    place: str | None,
    action: str | None,
    tier: int | None,
    danger: str | None,
) -> None:
    any_local, all_local = _local_flags(place, action, tier, danger)
    if any_local and not all_local:
        raise core.CronicaError(
            "gatilho local incompleto. Use --local, --acao, --tier e --periculosidade juntos "
            "somente ao entrar/explorar um local. Em turno comum sem gatilho local, omita os quatro "
            "e use apenas --cena-id (mais NPC/tag somente se já forem fatos pertinentes)."
        )


def _has_reactive_request(request: dict[str, Any]) -> bool:
    return bool(
        request.get("npcs")
        or request.get("context_tags")
        or any(request.get(key) is not None for key in ("place", "action", "tier", "danger"))
    )


def _neutral_preparation_id(request: dict[str, Any]) -> str:
    raw = core._json_bytes({"tipo": "turno_neutro", "cena": request})
    return NEUTRAL_PREPARATION_PREFIX + hashlib.sha256(raw).hexdigest()[:20]


def _is_neutral_payload(payload: dict[str, Any]) -> bool:
    preparation_id = str(payload.get("preparacao_id") or "")
    if not preparation_id.startswith(NEUTRAL_PREPARATION_PREFIX):
        return False
    request = payload.get("cena")
    if not isinstance(request, dict) or _has_reactive_request(request):
        raise core.CronicaError("ticket neutro contém gatilho reativo e foi corrompido")
    expected = _neutral_preparation_id(request)
    if preparation_id != expected:
        raise core.CronicaError("ticket neutro possui preparação divergente")
    return True


def _quality_modifier(request: dict[str, Any]) -> tuple[list[str], list[dict[str, Any]]]:
    approach = request.get("approach") or {}
    try:
        quality = endpoints._quality(
            preparacao=approach.get("preparacao"),
            informacao=approach.get("informacao"),
            adequacao=approach.get("adequacao"),
        )
    except qualidade_abordagem.ApproachQualityError as exc:
        raise core.CronicaError(str(exc)) from exc
    if int(quality["bonus"]) <= 0:
        return [], []
    return (
        ["qualidade_abordagem_pre_rolagem"],
        [qualidade_abordagem.compact_modifier(quality)],
    )


def _transaction_contract() -> dict[str, Any]:
    return {
        "comando": "cronica concluir --ticket <ticket> <<'JSON'",
        "campos": {
            "jogador": "<ON resolvido do jogador>",
            "narracao": "<prosa diegética; mecânica explícita somente em linha MECÂNICA — ...>",
            "resumo": "<resumo curto do que mudou>",
            "modo": "<interação|exploração|combate|descanso|descoberta ou modo coerente>",
            "deltas": [],
        },
        "mecanica": "Se houver número/CD/CA/rolagem explícita na narração, usar linha própria iniciada por `MECÂNICA — `.",
        "disciplina": "Não chamar --help nem ler implementação para descobrir este contrato; esta saída é autoritativa.",
    }


def _decorate(result: dict[str, Any], *, reactive: bool) -> dict[str, Any]:
    result = dict(result)
    result["reativa"] = reactive
    result["contrato_conclusao"] = _transaction_contract()
    next_step = dict(result.get("proximo_passo") or {})
    next_step.update(
        {
            "acao": "narrar_e_concluir",
            "comando": "cronica concluir --ticket <ticket>",
            "entrada": "usar contrato_conclusao; stdin JSON, sem arquivo temporário",
        }
    )
    result["proximo_passo"] = next_step
    size = len(yaml.safe_dump(result, allow_unicode=True, sort_keys=False).encode("utf-8"))
    if size > core.MAX_PREP_OUTPUT_BYTES:
        raise core.CronicaError(
            f"preparação cronica excede orçamento: {size} > {core.MAX_PREP_OUTPUT_BYTES} bytes"
        )
    return result


def prepare(
    repo: Path,
    *,
    scene_id: str,
    npcs: list[str] | None = None,
    place: str | None = None,
    action: str | None = None,
    tier: int | None = None,
    danger: str | None = None,
    context_tags: list[str] | None = None,
    now=None,
    approach_preparacao: str | None = None,
    approach_informacao: str | None = None,
    approach_adequacao: str | None = None,
) -> dict[str, Any]:
    _validate_local_contract(place, action, tier, danger)
    request = core._request(
        scene_id=scene_id,
        npcs=npcs,
        place=place,
        action=action,
        tier=tier,
        danger=danger,
        context_tags=context_tags,
        now=now,
        approach_preparacao=approach_preparacao,
        approach_informacao=approach_informacao,
        approach_adequacao=approach_adequacao,
    )
    if _has_reactive_request(request):
        result = core.prepare(
            repo,
            scene_id=scene_id,
            npcs=npcs,
            place=place,
            action=action,
            tier=tier,
            danger=danger,
            context_tags=context_tags,
            now=now,
            approach_preparacao=approach_preparacao,
            approach_informacao=approach_informacao,
            approach_adequacao=approach_adequacao,
        )
        return _decorate(result, reactive=True)

    preparation_id = _neutral_preparation_id(request)
    token, digest = core.encode_ticket(
        {
            "schema_cronica_ticket": core.SCHEMA,
            "preparacao_id": preparation_id,
            "cena": request,
        }
    )
    filters, modifiers = _quality_modifier(request)
    result = {
        "schema_cronica_turno": core.SCHEMA,
        "fase": "preparacao",
        "ticket_id": digest,
        "ticket": token,
        "ids": {
            "cena": scene_id,
            "preparacao": preparation_id,
            "local": None,
            "npcs": [],
            "encontros": [],
            "sidequests_potenciais": [],
            "presencas_contextuais": [],
            "entradas_contextuais": [],
            "operacoes_contextuais": [],
            "direcoes_contextuais": [],
            "candidatos_contextuais": [],
        },
        "filtros": ["turno_neutro_sem_gatilho_reativo", *filters],
        "disponibilidade": {
            "conclusao": True,
            "confirmacao_reativa": False,
        },
        "gates": [],
        "modificadores": modifiers,
        "fontes_lidas": [],
        "proximo_passo": {},
    }
    return _decorate(result, reactive=False)


def revalidate(repo: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if _is_neutral_payload(payload):
        return {"preparacao_id": payload["preparacao_id"], "reativa": False}
    return core._revalidate_ticket(repo, payload)


def confirm(repo: Path, token: str) -> dict[str, Any]:
    payload = core.decode_ticket(token)
    if not _is_neutral_payload(payload):
        return core.confirm(repo, token)
    return {
        "schema_cronica_turno": core.SCHEMA,
        "fase": "confirmacao",
        "ticket_id": core.ticket_id(token),
        "cena_id": payload["cena"]["scene_id"],
        "preparacao_id": payload["preparacao_id"],
        "mutacoes_aplicadas": False,
        "reativa": False,
        "resumo": {},
        "fontes_lidas": [],
        "proximo_passo": {
            "acao": "registrar_turno",
            "comando": "cronica registrar --ticket <ticket>",
        },
    }


def _registered_result(repo: Path, token: str, payload: dict[str, Any], registered: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_cronica_turno": core.SCHEMA,
        "fase": "registro",
        "ticket_id": core.ticket_id(token),
        "preparacao_id": payload["preparacao_id"],
        "reativa": False,
        "transacao": {
            "id": registered["id"],
            "sessao": registered["sessao"],
            "deltas": registered["deltas"],
            "transcricao_escrita": registered["transcricao_escrita"],
            "evento_escrito": registered["evento_escrito"],
            "reparo_parcial": registered["reparo_parcial"],
            "ja_registrada": registered["ja_registrada"],
            "consolidada": registered["consolidada"],
        },
        "checkpoint_mundo": registered.get("checkpoint_mundo"),
        "avisos": registered.get("avisos") or [],
        "confirmacao_pendente": False,
        "rodape_canonico": rodape_turno.build_safe(repo),
        "proximo_passo": {"acao": "continuar_narracao_ou_checkpoint_quando_necessario"},
    }


def register(
    repo: Path,
    token: str,
    transaction: dict[str, Any],
    *,
    revalidate_ticket: bool = True,
) -> dict[str, Any]:
    payload = core.decode_ticket(token)
    if not _is_neutral_payload(payload):
        return core.register(repo, token, transaction, revalidate=revalidate_ticket)
    if revalidate_ticket:
        revalidate(repo, payload)
    registered = turno.register_transaction(repo, transaction)
    return _registered_result(repo, token, payload, registered)


def conclude(
    repo: Path,
    token: str,
    transaction: dict[str, Any],
    *,
    preflight: Callable[[Path, dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload = core.decode_ticket(token)
    if not _is_neutral_payload(payload):
        return core.conclude(repo, token, transaction)

    preview = (preflight or core._preflight_registration)(repo, transaction)
    registered = turno.register_transaction(repo, transaction)
    return {
        "schema_cronica_turno": core.SCHEMA,
        "fase": "concluida",
        "ticket_id": core.ticket_id(token),
        "reativa": False,
        "cena": {
            "id": payload["cena"]["scene_id"],
            "preparacao_id": payload["preparacao_id"],
            "confirmada": False,
            "resumo": {},
        },
        "transacao": {
            "id": registered["id"],
            "sessao": registered["sessao"],
            "deltas": registered["deltas"],
            "transcricao_escrita": registered["transcricao_escrita"],
            "evento_escrito": registered["evento_escrito"],
            "reparo_parcial": registered["reparo_parcial"],
            "ja_registrada": registered["ja_registrada"],
            "consolidada": registered["consolidada"],
        },
        "checkpoint_previsto_no_preflight": preview.get("checkpoint_previsto"),
        "checkpoint_mundo": registered.get("checkpoint_mundo"),
        "avisos": registered.get("avisos") or [],
        "rodape_canonico": rodape_turno.build_safe(repo),
        "proximo_passo": {"acao": "continuar_narracao_ou_checkpoint_quando_necessario"},
    }
