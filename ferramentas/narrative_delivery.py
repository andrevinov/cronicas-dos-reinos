#!/usr/bin/env python3
"""Fachada pública v2 da entrega narrativa.

O módulo observa a prosa que já passou pelo writer e publica um recibo pequeno
para correlação pós-hoc. Ele não escreve cânone, não reescreve a narração e não
tenta atribuir qualidade literária a partir de palavras-chave ou comprimento.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

from _module_facade import combine_checks
import diegetico

FACADE_SCHEMA = 2
RECEIPT_SCHEMA = 1
MODULE_ID = "narrative_delivery"
CAPABILITIES = (
    "narrative_density",
    "diegetic_mechanics",
    "visible_closure",
)
LEGACY_COMPONENTS = (
    "densidade_narrativa",
    "diegetico",
    "rodape_turno",
)
RECEIPT_KEY = "entrega_narrativa"
MAX_RECEIPT_BYTES = 1024
MAX_TURN_CLASS_CHARS = 64

SEMANTIC_DIMENSIONS = (
    "progressao_jogavel",
    "densidade_proporcional",
    "voz_e_dialogo",
    "camadas_de_conhecimento",
    "conclusao_aberta",
)
PLAYER_DIMENSIONS = (
    "ritmo",
    "naturalidade",
    "profundidade",
    "agencia_percebida",
)
GUARDRAILS = (
    "player_agency",
    "knowledge_secrecy",
    "roll_integrity",
)
SEMANTIC_STATES = {"adequado", "inadequado", "indeterminado", "nao_aplicavel"}
GUARDRAIL_STATES = {"ok", "violado", "indeterminado", "nao_aplicavel"}


class NarrativeDeliveryError(ValueError):
    """Contrato inválido de entrega ou adjudicação narrativa."""


def _size(value: Any) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


def _word_count(text: str) -> int:
    return len(re.findall(r"[^\W_]+(?:[-'][^\W_]+)*", text, flags=re.UNICODE))


def structural_metrics(narration: str) -> dict[str, int]:
    """Mede somente forma observável; tamanho não é nota de qualidade."""

    if not isinstance(narration, str) or not narration.strip():
        raise NarrativeDeliveryError("narração precisa ser texto não vazio")
    lines = narration.splitlines()
    paragraphs = [part for part in re.split(r"\n\s*\n", narration.strip()) if part.strip()]
    return {
        "caracteres": len(narration),
        "palavras": _word_count(narration),
        "paragrafos": len(paragraphs),
        "linhas_mecanica": sum(diegetico.is_mechanics_line(line) for line in lines),
    }


def validate_transaction(transaction: dict[str, Any]) -> dict[str, int]:
    """Valida a camada pública antes do writer e devolve só métricas estruturais."""

    if not isinstance(transaction, dict):
        raise NarrativeDeliveryError("transação precisa ser mapa")
    narration = transaction.get("narracao")
    try:
        diegetico.validate_narration(narration)
    except diegetico.DiegeticMechanicsError as exc:
        raise NarrativeDeliveryError(str(exc)) from exc
    return structural_metrics(narration)


def _turn_class(transaction: dict[str, Any]) -> str:
    value = transaction.get("modo")
    if not isinstance(value, str):
        return "nao_declarada"
    normalized = value.strip()
    if not normalized or len(normalized) > MAX_TURN_CLASS_CHARS:
        return "nao_declarada"
    return normalized


def _delivery_id(result: dict[str, Any], transaction: dict[str, Any], narration: str) -> str:
    persisted = result.get("transacao") if isinstance(result.get("transacao"), dict) else {}
    seed = {
        "ticket_id": result.get("ticket_id"),
        "transacao_id": persisted.get("id") or transaction.get("id"),
        "narracao_sha256": hashlib.sha256(narration.encode("utf-8")).hexdigest(),
    }
    digest = hashlib.sha256(
        json.dumps(seed, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:20]
    return f"delivery-{digest}"


def publish_conclusion(
    result: dict[str, Any], transaction: dict[str, Any]
) -> dict[str, Any]:
    """Anexa recibo pós-writer sem realizar qualquer escrita canônica."""

    if not isinstance(result, dict) or not isinstance(transaction, dict):
        raise NarrativeDeliveryError("resultado e transação precisam ser mapas")
    narration = transaction.get("narracao")
    metrics = validate_transaction(transaction)

    persisted = result.get("transacao") if isinstance(result.get("transacao"), dict) else {}
    retry = persisted.get("ja_registrada") is True
    footer = result.get("rodape_canonico")
    receipt = {
        "schema_narrative_delivery": RECEIPT_SCHEMA,
        "module_id": MODULE_ID,
        "entrega_id": _delivery_id(result, transaction, narration),
        "estado": "replay_sem_nova_persistencia" if retry else "prosa_registrada",
        "correlacao": {
            "ticket_id": result.get("ticket_id"),
            "transacao_id": persisted.get("id") or transaction.get("id"),
            "sessao": persisted.get("sessao"),
        },
        "classe_turno": _turn_class(transaction),
        "estrutura": metrics,
        "rodape": {
            "emitido": isinstance(footer, str) and bool(footer.strip()),
            "deve_ser_ultima_linha_visivel": True,
        },
        "avaliacao_semantica": "nao_realizada",
        "nota_jogador": None,
        "guardrails": {guardrail: "indeterminado" for guardrail in GUARDRAILS},
        "guardrails_participam_media": False,
        "escrita_canonica_pelo_modulo": False,
    }
    if _size(receipt) > MAX_RECEIPT_BYTES:
        raise NarrativeDeliveryError(
            f"recibo de entrega excede {MAX_RECEIPT_BYTES} bytes"
        )

    out = copy.deepcopy(result)
    out[RECEIPT_KEY] = receipt
    systems = out.setdefault("sistemas_narrativos", [])
    if MODULE_ID not in systems:
        systems.append(MODULE_ID)
    return out


def _exact_dimensions(value: Any, expected: tuple[str, ...], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(expected):
        raise NarrativeDeliveryError(
            f"{label} deve conter exatamente: {', '.join(expected)}"
        )
    return value


def validate_semantic_audit(value: dict[str, Any]) -> dict[str, Any]:
    """Valida julgamento humano/semântico sem fabricar uma nota automática."""

    if not isinstance(value, dict):
        raise NarrativeDeliveryError("auditoria semântica precisa ser mapa")
    dimensions = _exact_dimensions(
        value.get("dimensoes"), SEMANTIC_DIMENSIONS, "dimensoes"
    )
    guardrails = _exact_dimensions(value.get("guardrails"), GUARDRAILS, "guardrails")
    invalid_dimensions = {
        name: state for name, state in dimensions.items() if state not in SEMANTIC_STATES
    }
    invalid_guardrails = {
        name: state for name, state in guardrails.items() if state not in GUARDRAIL_STATES
    }
    if invalid_dimensions:
        raise NarrativeDeliveryError(f"estados semânticos inválidos: {invalid_dimensions}")
    if invalid_guardrails:
        raise NarrativeDeliveryError(f"estados de guardrail inválidos: {invalid_guardrails}")
    evidence = value.get("evidencias")
    if not isinstance(evidence, list) or any(not isinstance(item, str) for item in evidence):
        raise NarrativeDeliveryError("evidencias precisa ser lista, inclusive quando vazia")
    return {
        "dimensoes": copy.deepcopy(dimensions),
        "guardrails": copy.deepcopy(guardrails),
        "evidencias": copy.deepcopy(evidence),
        "nota_literaria_automatica": None,
        "guardrails_compensaveis": False,
    }


def validate_player_feedback(value: dict[str, Any]) -> dict[str, Any]:
    """Aceita percepção parcial do jogador; ausência permanece N/D."""

    if not isinstance(value, dict):
        raise NarrativeDeliveryError("feedback do jogador precisa ser mapa")
    ratings = _exact_dimensions(value.get("notas"), PLAYER_DIMENSIONS, "notas")
    invalid = {
        name: score
        for name, score in ratings.items()
        if score is not None and (isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 5)
    }
    if invalid:
        raise NarrativeDeliveryError(f"notas do jogador inválidas: {invalid}")
    if not any(score is not None for score in ratings.values()):
        raise NarrativeDeliveryError("feedback sem nota deve ser omitido, preservando N/D")
    comment = value.get("comentario")
    if comment is not None and (not isinstance(comment, str) or not comment.strip()):
        raise NarrativeDeliveryError("comentario, quando presente, precisa ser texto não vazio")
    return {
        "notas": copy.deepcopy(ratings),
        "comentario": comment.strip() if isinstance(comment, str) else None,
        "papel_na_agregacao": "percepcao_com_peso_limitado",
        "altera_guardrails": False,
    }


def _contract_check(_repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    fixture = "A porta se abre.\n\nMECÂNICA — Teste resolvido: 18."
    result = {
        "ticket_id": "ticket-rm09",
        "transacao": {"id": "tx-rm09", "sessao": 1, "ja_registrada": False},
        "rodape_canonico": "RODAPE_CANONICO — fixture",
    }
    try:
        published = publish_conclusion(result, {"narracao": fixture, "modo": "mecanico"})
        receipt = published.get(RECEIPT_KEY) or {}
        if receipt.get("avaliacao_semantica") != "nao_realizada":
            errors.append("recibo atribuiu avaliação semântica automática")
        if receipt.get("guardrails_participam_media") is not False:
            errors.append("guardrails críticos tornaram-se compensáveis")
        if receipt.get("escrita_canonica_pelo_modulo") is not False:
            errors.append("fachada declarou escrita canônica")
    except NarrativeDeliveryError as exc:
        errors.append(str(exc))
    return {"ok": not errors, "erros": errors, "recibo_max_bytes": MAX_RECEIPT_BYTES}


def check(repo: Path) -> dict[str, Any]:
    return combine_checks(
        repo,
        module_id=MODULE_ID,
        capabilities=CAPABILITIES,
        legacy_components=LEGACY_COMPONENTS,
        checks=(("delivery_contract", _contract_check),),
        contract={
            "automatic_literary_judge": False,
            "short_turn_is_quality_failure": False,
            "semantic_dimensions": list(SEMANTIC_DIMENSIONS),
            "player_dimensions": list(PLAYER_DIMENSIONS),
            "critical_guardrails": list(GUARDRAILS),
            "guardrails_are_compensable": False,
            "rewrites_narration": False,
            "exposes_narration_in_receipt": False,
            "decides_for_player": False,
            "publishes_reserved_content": False,
            "canonical_writes": 0,
            "additional_orchestration_calls": 0,
            "telemetry_in_hot_path": False,
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
