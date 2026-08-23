#!/usr/bin/env python3
"""Ergonomia do hot path da CLI ``cronica`` observada em rollout real.

A camada não cria um segundo motor. Tickets reativos continuam delegando byte-logicamente
à Task 21. Há duas extensões read-only de preparação:

- ticket **neutro** para turno sem gatilho reativo;
- ticket de **trânsito urbano** para deslocamento material por Ravens Bluff, reutilizando
  o Local Microevent Deck sem fabricar uma rua como ``local_id``.

Trânsito urbano é deliberadamente exclusivo de gatilhos locais/NPC/tags no mesmo ticket:
o deck local e o escopo de trânsito compartilham o mesmo arquivo transacional de estado,
e separar os dois evita confirmação parcial/fingerprint cruzado sem criar nova tool call.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Callable

import yaml

import _cronica_turn_core as core
import endpoints
import microeventos_transito
import qualidade_abordagem
import rodape_turno
import turno

NEUTRAL_PREPARATION_PREFIX = "turn-neutral-"
TRANSIT_PREPARATION_PREFIX = "turn-transit-"
URBAN_TRANSIT_SCOPE = microeventos_transito.TRANSIT_SCOPE


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


def _transit_preparation_id(request: dict[str, Any], transit: dict[str, str]) -> str:
    raw = core._json_bytes(
        {"tipo": "transito_urbano", "cena": request, "transito_urbano": transit}
    )
    return TRANSIT_PREPARATION_PREFIX + hashlib.sha256(raw).hexdigest()[:20]


def _is_neutral_payload(payload: dict[str, Any]) -> bool:
    preparation_id = str(payload.get("preparacao_id") or "")
    if not preparation_id.startswith(NEUTRAL_PREPARATION_PREFIX):
        return False
    request = payload.get("cena")
    if not isinstance(request, dict) or _has_reactive_request(request):
        raise core.CronicaError("ticket neutro contém gatilho reativo e foi corrompido")
    if payload.get("transito_urbano") is not None:
        raise core.CronicaError("ticket neutro contém trânsito urbano e foi corrompido")
    expected = _neutral_preparation_id(request)
    if preparation_id != expected:
        raise core.CronicaError("ticket neutro possui preparação divergente")
    return True


def _transit_meta(payload: dict[str, Any]) -> dict[str, str] | None:
    raw = payload.get("transito_urbano")
    if raw is None:
        return None
    if not isinstance(raw, dict) or set(raw) != {"escopo", "fingerprint"}:
        raise core.CronicaError("ticket de trânsito possui metadados inválidos")
    scope = raw.get("escopo")
    fingerprint = raw.get("fingerprint")
    if scope != URBAN_TRANSIT_SCOPE:
        raise core.CronicaError("ticket de trânsito possui escopo inválido")
    if (
        not isinstance(fingerprint, str)
        or len(fingerprint) != 64
        or any(ch not in "0123456789abcdef" for ch in fingerprint)
    ):
        raise core.CronicaError("ticket de trânsito possui fingerprint inválido")
    return {"escopo": scope, "fingerprint": fingerprint}


def _is_transit_payload(payload: dict[str, Any]) -> bool:
    preparation_id = str(payload.get("preparacao_id") or "")
    meta = _transit_meta(payload)
    if not preparation_id.startswith(TRANSIT_PREPARATION_PREFIX):
        if meta is not None:
            raise core.CronicaError(
                "trânsito urbano não pode ser combinado com gatilho reativo no mesmo ticket"
            )
        return False
    request = payload.get("cena")
    if not isinstance(request, dict) or _has_reactive_request(request):
        raise core.CronicaError(
            "ticket de trânsito contém local/NPC/tag; separe deslocamento da cena reativa"
        )
    if meta is None:
        raise core.CronicaError("ticket de trânsito perdeu seus metadados")
    expected = _transit_preparation_id(request, meta)
    if preparation_id != expected:
        raise core.CronicaError("ticket de trânsito possui preparação divergente")
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


def _plan_transit(repo: Path, scene_id: str) -> dict[str, Any]:
    try:
        return microeventos_transito.plan(repo, scene_id=scene_id)
    except microeventos_transito.TransitMicroeventError as exc:
        raise core.CronicaError(str(exc)) from exc


def _revalidate_transit(repo: Path, payload: dict[str, Any]) -> dict[str, Any]:
    meta = _transit_meta(payload)
    if meta is None:
        raise core.CronicaError("ticket não contém trânsito urbano")
    try:
        return microeventos_transito.revalidate(
            repo,
            scene_id=payload["cena"]["scene_id"],
            expected_fingerprint=meta["fingerprint"],
            scope=meta["escopo"],
        )
    except microeventos_transito.TransitMicroeventError as exc:
        raise core.CronicaError(str(exc)) from exc


def _confirm_transit(repo: Path, payload: dict[str, Any]) -> dict[str, Any]:
    meta = _transit_meta(payload)
    if meta is None:
        raise core.CronicaError("ticket não contém trânsito urbano")
    try:
        return microeventos_transito.confirm(
            repo,
            scene_id=payload["cena"]["scene_id"],
            expected_fingerprint=meta["fingerprint"],
            scope=meta["escopo"],
        )
    except microeventos_transito.TransitMicroeventError as exc:
        raise core.CronicaError(str(exc)) from exc


def _transit_gate(public: dict[str, Any]) -> dict[str, Any]:
    gate = {
        "tipo": "transito_urbano",
        "escopo": public["escopo"],
        "resultado": public["resultado"],
    }
    card = public.get("carta")
    if isinstance(card, dict):
        gate["carta_id"] = card.get("id")
    return gate


def _transit_modifier(public: dict[str, Any]) -> dict[str, Any] | None:
    pressure = public.get("pressao_ravens_bluff") or {}
    active = int(pressure.get("frentes_ativas") or 0)
    if active <= 0:
        return None
    return {
        "tipo": "pressao_urbana_contextual",
        "frentes_ativas": active,
        "max_nivel": int(pressure.get("max_nivel") or 0),
        "efeito": "colore textura elegível; não altera frequência nem avança pressão",
    }


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
    urban_transit: str | None = None,
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

    if urban_transit is not None:
        if urban_transit != URBAN_TRANSIT_SCOPE:
            raise core.CronicaError(
                f"--transito-urbano aceita somente {URBAN_TRANSIT_SCOPE}"
            )
        if _has_reactive_request(request):
            raise core.CronicaError(
                "trânsito urbano não combina com --local/--npc/--contexto-tag no mesmo ticket. "
                "Use o deslocamento como turno de trânsito; a interação/entrada reativa fica no turno seguinte."
            )
        planned = _plan_transit(repo, scene_id)
        public = planned["publico"]
        meta = {
            "escopo": URBAN_TRANSIT_SCOPE,
            "fingerprint": planned["fingerprint"],
        }
        preparation_id = _transit_preparation_id(request, meta)
        token, digest = core.encode_ticket(
            {
                "schema_cronica_ticket": core.SCHEMA,
                "preparacao_id": preparation_id,
                "cena": request,
                "transito_urbano": meta,
            }
        )
        filters, modifiers = _quality_modifier(request)
        pressure_modifier = _transit_modifier(public)
        if pressure_modifier is not None:
            modifiers.append(pressure_modifier)
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
                "transito_urbano": URBAN_TRANSIT_SCOPE,
            },
            "filtros": ["turno_de_transito_urbano_sem_local_canonico", *filters],
            "disponibilidade": {
                "conclusao": True,
                "confirmacao_reativa": False,
                "transito_urbano": True,
            },
            "gates": [_transit_gate(public)],
            "modificadores": modifiers,
            "transito_urbano": public,
            "fontes_lidas": list(public.get("fontes_lidas") or []),
            "proximo_passo": {},
        }
        return _decorate(result, reactive=False)

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
    if _is_transit_payload(payload):
        result = _revalidate_transit(repo, payload)
        return {
            "preparacao_id": payload["preparacao_id"],
            "reativa": False,
            "transito_urbano": result["publico"],
        }
    if _is_neutral_payload(payload):
        return {"preparacao_id": payload["preparacao_id"], "reativa": False}
    return core._revalidate_ticket(repo, payload)


def confirm(repo: Path, token: str) -> dict[str, Any]:
    payload = core.decode_ticket(token)
    if _is_transit_payload(payload):
        transit = _confirm_transit(repo, payload)
        return {
            "schema_cronica_turno": core.SCHEMA,
            "fase": "confirmacao",
            "ticket_id": core.ticket_id(token),
            "cena_id": payload["cena"]["scene_id"],
            "preparacao_id": payload["preparacao_id"],
            "mutacoes_aplicadas": bool(transit.get("mutacoes_aplicadas")),
            "reativa": False,
            "transito_urbano": transit,
            "resumo": {
                "microeventos_para_avaliar": int(
                    transit.get("resultado") == "avaliar_microevento"
                )
            },
            "fontes_lidas": transit.get("fontes_lidas") or [],
            "proximo_passo": {
                "acao": "registrar_turno",
                "comando": "cronica registrar --ticket <ticket>",
            },
        }
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
    if _is_transit_payload(payload):
        if revalidate_ticket:
            _revalidate_transit(repo, payload)
        registered = turno.register_transaction(repo, transaction)
        return _registered_result(repo, token, payload, registered)
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
    if _is_transit_payload(payload):
        preview = (preflight or core._preflight_registration)(repo, transaction)
        transit = _confirm_transit(repo, payload)
        try:
            registered = turno.register_transaction(repo, transaction)
        except Exception as exc:
            raise core.PartialConclusionError(
                "trânsito urbano confirmado, mas o registrador transacional falhou; repare com "
                "`cronica registrar --ticket <ticket> --reparo-pos-confirmacao` usando a mesma transação",
                ticket_id=core.ticket_id(token),
                transaction_id=preview["id"],
            ) from exc
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
            "transito_urbano": transit,
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
