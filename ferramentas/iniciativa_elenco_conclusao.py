#!/usr/bin/env python3
"""Validação e instalação idempotente das decisões NV-16."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import iniciativa_elenco as initiative
import iniciativa_elenco_estado as receipts

MANUAL_SILENCE_REASONS = {"risco", "indisponibilidade"}
MANUAL_INELIGIBLE_REASONS = {"falta_conhecimento", "risco", "indisponibilidade"}
AUTOMATIC_MOTIVES = {
    "ausencia": "O interlocutor não possui presença física consolidada nem canal de contato validado nesta janela.",
    "indisponibilidade": "O estado relacional carregado não autoriza uma iniciativa dirigida a Ren nesta janela.",
    "falta_conhecimento": "O interlocutor não dispõe do conhecimento necessário para sustentar a abertura nesta janela.",
    "risco": "O risco corrente impede a abertura social sem transformar cautela em ação automática.",
    "sem_motivo_concreto": "A política social exige causa concreta e nenhuma causa já estabelecida foi encontrada na memória carregada.",
    "pressao_superior": "Uma pressão de prioridade superior ocupa a janela social; a iniciativa permanece reavaliável.",
    "janela_ocupada": "Outra abertura social já ocupa o único slot incidental permitido nesta janela.",
    "repeticao_sem_causa_nova": "A mesma abertura já foi apresentada nesta janela e não existe causa material nova para repeti-la.",
}


def validate_ticket(raw: Any) -> dict[str, Any]:
    expected_top = {"schema", "janela_id", "janela_tipo", "cena_id", "selecionada", "itens"}
    if not isinstance(raw, dict) or set(raw) != expected_top or raw.get("schema") != initiative.SCHEMA:
        raise initiative.CastInitiativeError("ticket de iniciativa possui campos divergentes")
    if raw.get("janela_tipo") not in {"cena", "permanencia"}:
        raise initiative.CastInitiativeError("tipo de janela de iniciativa inválido")
    window_id = initiative._text(raw.get("janela_id"), "janela_id", maximum=64)
    initiative._text(raw.get("cena_id"), "cena_id", maximum=160)
    rows = raw.get("itens")
    if not isinstance(rows, list) or not 1 <= len(rows) <= initiative.MAX_INTERLOCUTORS:
        raise initiative.CastInitiativeError("ticket de iniciativa exige 1..6 decisões")
    expected_row = {
        "decisao_id", "npc_id", "presenca", "proposta_digest", "requer_decisao",
        "resultado_automatico", "motivo_automatico", "pressao_superior", "exige_motivo", "reutilizado",
    }
    seen, required = set(), []
    for pos, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != expected_row:
            raise initiative.CastInitiativeError(f"ticket.itens[{pos}] possui campos divergentes")
        did = initiative._text(row.get("decisao_id"), "decisao_id", maximum=64)
        npc_id = initiative._npc(row.get("npc_id"), "npc_id")
        if row.get("presenca") not in {"elenco_cena", "canal_contato", "ausente"}:
            raise initiative.CastInitiativeError("fonte de presença inválida")
        digest = initiative._text(row.get("proposta_digest"), "proposta_digest", maximum=64)
        if len(digest) != 64 or did != initiative._decision(window_id, npc_id, digest):
            raise initiative.CastInitiativeError("identidade/digest da decisão de iniciativa inválidos")
        for key in ("requer_decisao", "exige_motivo", "reutilizado"):
            if not isinstance(row.get(key), bool):
                raise initiative.CastInitiativeError(f"{key} precisa ser booleano")
        automatic = row.get("resultado_automatico")
        if automatic is not None and automatic not in receipts.RESULTS:
            raise initiative.CastInitiativeError("resultado automático inválido")
        if row["requer_decisao"] and automatic is not None:
            raise initiative.CastInitiativeError("decisão obrigatória não pode ter resultado automático")
        if not row["requer_decisao"] and automatic is None:
            raise initiative.CastInitiativeError("decisão automática precisa declarar resultado")
        if row["motivo_automatico"] is not None and row["motivo_automatico"] not in AUTOMATIC_MOTIVES:
            raise initiative.CastInitiativeError("motivo automático inválido")
        if automatic == "adiada_por_pressao_superior" and not row["pressao_superior"]:
            raise initiative.CastInitiativeError("adiamento automático exige pressão superior")
        if did in seen:
            raise initiative.CastInitiativeError("decisão duplicada no ticket")
        seen.add(did)
        if row["requer_decisao"]:
            if row["presenca"] == "ausente":
                raise initiative.CastInitiativeError("interlocutor ausente não pode ser iniciativa selecionada")
            required.append(did)
    selected = raw.get("selecionada")
    if selected is not None:
        selected = initiative._text(selected, "selecionada", maximum=64)
    if required != ([selected] if selected is not None else []):
        raise initiative.CastInitiativeError("ticket deve ter exatamente a iniciativa selecionada como obrigatória")
    if initiative._size(raw) > initiative.MAX_TICKET_BYTES:
        raise initiative.CastInitiativeError("ticket de iniciativa excede orçamento")
    return copy.deepcopy(raw)


def ticket_meta(payload: dict[str, Any]) -> dict[str, Any] | None:
    raw = payload.get(initiative.TICKET_KEY)
    return None if raw is None else validate_ticket(raw)


def strip_ticket_payload(payload: dict[str, Any]) -> dict[str, Any]:
    clean = copy.deepcopy(payload)
    clean.pop(initiative.TICKET_KEY, None)
    return clean


def writer_transaction(transaction: dict[str, Any]) -> dict[str, Any]:
    clean = copy.deepcopy(transaction)
    clean.pop(initiative.TRANSACTION_KEY, None)
    return clean


def _literal(transaction: dict[str, Any], value: Any) -> str:
    evidence = initiative._text(value, "evidencia_literal", minimum=8, maximum=320)
    haystack = "\n".join(str(transaction.get(key) or "") for key in ("narracao", "resumo"))
    if evidence not in haystack:
        raise initiative.CastInitiativeError("evidencia_literal da iniciativa deve aparecer em narracao ou resumo")
    return evidence


def _plan_row(meta: dict[str, Any], row: dict[str, Any], result: str,
              reason: str | None = None, motive: str | None = None,
              evidence: str | None = None) -> dict[str, Any]:
    return {
        "id": row["decisao_id"], "janela_id": meta["janela_id"],
        "janela_tipo": meta["janela_tipo"], "cena_id": meta["cena_id"],
        "npc_id": row["npc_id"], "presenca": row["presenca"],
        "proposta_digest": row["proposta_digest"], "resultado": result,
        "motivo_codigo": reason, "motivo": motive, "evidencia_literal": evidence,
        "pressao_superior": row["pressao_superior"],
    }


def prepare(repo: Path, raw_meta: Any, transaction: dict[str, Any]) -> dict[str, Any]:
    meta = validate_ticket(raw_meta)
    has_block = initiative.TRANSACTION_KEY in transaction
    block = transaction.get(initiative.TRANSACTION_KEY)
    if meta["selecionada"] is None:
        if has_block:
            raise initiative.CastInitiativeError("transação traz iniciativa sem abertura selecionada")
    elif not isinstance(block, dict):
        raise initiative.CastInitiativeError("abertura selecionada exige decisão explícita no concluir")
    try:
        state = receipts.load(Path(repo))
    except receipts.InitiativeStateError as exc:
        raise initiative.CastInitiativeError(str(exc)) from exc
    plan = []
    for row in meta["itens"]:
        existing = state["decisoes"].get(row["decisao_id"])
        if row["reutilizado"] and isinstance(existing, dict) and existing.get("resultado") in receipts.TERMINAL_RESULTS:
            continue
        if not row["requer_decisao"]:
            result = row["resultado_automatico"]
            if result is None:
                raise initiative.CastInitiativeError("decisão automática sem resultado")
            if isinstance(existing, dict) and existing.get("resultado") == result and existing.get("pressao_superior") == row.get("pressao_superior"):
                continue
            code = row["motivo_automatico"]
            plan.append(_plan_row(meta, row, result, reason=code, motive=AUTOMATIC_MOTIVES.get(code)))
            continue
        assert isinstance(block, dict)
        if block.get("decisao_id") != row["decisao_id"]:
            raise initiative.CastInitiativeError("conclusão referencia outra iniciativa")
        result = initiative._text(block.get("resultado"), "resultado", maximum=40)
        base = {"decisao_id", "resultado"}
        if result == "apresentada":
            expected = base | {"evidencia_literal"}
            plan.append(_plan_row(meta, row, result, evidence=_literal(transaction, block.get("evidencia_literal"))))
        elif result == "silencio_justificado":
            expected = base | {"motivo_codigo", "motivo"}
            code = initiative._text(block.get("motivo_codigo"), "motivo_codigo", maximum=48)
            if code not in MANUAL_SILENCE_REASONS:
                raise initiative.CastInitiativeError("silêncio manual aceita somente risco ou indisponibilidade; motivos automáticos vêm do preparo")
            plan.append(_plan_row(meta, row, result, code, initiative._text(block.get("motivo"), "motivo", 8, 240)))
        elif result == "nao_elegivel":
            expected = base | {"motivo_codigo", "motivo"}
            code = initiative._text(block.get("motivo_codigo"), "motivo_codigo", maximum=48)
            if code not in MANUAL_INELIGIBLE_REASONS:
                raise initiative.CastInitiativeError("inelegibilidade manual aceita falta_conhecimento, risco ou indisponibilidade; ausência vem do preparo")
            plan.append(_plan_row(meta, row, result, code, initiative._text(block.get("motivo"), "motivo", 8, 240)))
        elif result == "adiada_por_pressao_superior":
            raise initiative.CastInitiativeError("adiamento por pressão superior é decisão automática do preparo")
        else:
            raise initiative.CastInitiativeError(f"resultado de iniciativa inválido: {result}")
        if set(block) != expected:
            raise initiative.CastInitiativeError("bloco iniciativa_elenco possui campos divergentes")
    if any(item["resultado"] == "apresentada" for item in plan):
        conflict = next((raw for raw in state["decisoes"].values()
                         if raw.get("janela_id") == meta["janela_id"]
                         and raw.get("resultado") == "apresentada"
                         and raw.get("id") != meta["selecionada"]), None)
        if conflict is not None:
            raise initiative.CastInitiativeError("outra iniciativa já foi apresentada nesta janela")
    return {"schema": initiative.SCHEMA, "janela_id": meta["janela_id"], "itens": plan}


def install(repo: Path, raw_meta: Any, plan: dict[str, Any], *, ticket_id: str,
            transaction_id: str) -> dict[str, Any]:
    meta = validate_ticket(raw_meta)
    if not isinstance(plan, dict) or plan.get("schema") != initiative.SCHEMA or plan.get("janela_id") != meta["janela_id"]:
        raise initiative.CastInitiativeError("plano de conclusão da iniciativa inválido")
    rows = plan.get("itens")
    if not isinstance(rows, list) or len(rows) > initiative.MAX_INTERLOCUTORS:
        raise initiative.CastInitiativeError("plano de conclusão excede interlocutores")
    permitted = {row["decisao_id"] for row in meta["itens"]}
    if any(not isinstance(row, dict) or row.get("id") not in permitted for row in rows):
        raise initiative.CastInitiativeError("plano tenta instalar decisão fora do ticket")
    try:
        result = receipts.install(Path(repo), rows, ticket_id=ticket_id, transaction_id=transaction_id)
    except receipts.InitiativeStateError as exc:
        raise initiative.CastInitiativeError(str(exc)) from exc
    return {"schema_iniciativa_elenco": initiative.SCHEMA, "janela_id": meta["janela_id"],
            **result, "regra": "recibo reservado não cria presença, sidequest nem ação de Ren"}
