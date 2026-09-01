#!/usr/bin/env python3
"""Projecao pura de iniciativa social de NPC baseada no estado relacional.

A camada decide somente se um NPC ja legitimamente presente/contatavel pode abrir
a troca sem esperar Ren. Nao cria presenca, canal, encontro, conhecimento, side
quest, compromisso, scheduler, RNG ou estado.
"""
from __future__ import annotations

from typing import Any

SCHEMA = 1
MAX_OPENINGS = 3
HIGH_RISK_MIN = 8
MAX_CAUSAL_ID = 128

POLICIES: dict[str, dict[str, Any]] = {
    "alta_afinidade_alta_confianca": {
        "modo": "espontanea",
        "pode_iniciar": True,
        "exige_motivo": False,
        "escopo": ["saudacao ou check-in cotidiano", "convite, oferta ou pedido leve", "necessidade propria ja canonica"],
    },
    "alta_afinidade_baixa_confianca": {
        "modo": "afetiva_cautelosa",
        "pode_iniciar": True,
        "exige_motivo": False,
        "escopo": ["saudacao ou tentativa de proximidade", "pedido pessoal pequeno", "reparar tensao ja canonica"],
    },
    "baixa_afinidade_alta_confianca": {
        "modo": "funcional",
        "pode_iniciar": True,
        "exige_motivo": True,
        "escopo": ["abordagem profissional", "pedido ou oferta de cooperacao", "atualizacao concreta do proprio dominio"],
    },
    "baixa_afinidade_baixa_confianca": {
        "modo": "somente_motivo_concreto",
        "pode_iniciar": False,
        "exige_motivo": True,
        "escopo": ["necessidade, transacao, dever ou conflito", "limite pratico exigido pelo papel"],
    },
    "intermediaria_ou_desconhecida": {
        "modo": "situacional",
        "pode_iniciar": False,
        "exige_motivo": True,
        "escopo": ["assunto cotidiano sustentado pela cena", "motivo funcional ligado ao papel"],
    },
}

LIMIT = (
    "So com presenca/canal ja legitimo; nao cria encontro, segredo, conhecimento, side quest, compromisso ou acao de Ren. "
    "Conselho continua gated pela Task 27."
)


def project(npc_payload: Any, *, relationship_mode: str) -> dict[str, Any] | None:
    if not isinstance(npc_payload, dict) or not isinstance(npc_payload.get("medidores"), dict):
        return None
    policy = POLICIES.get(relationship_mode)
    if policy is None:
        raise ValueError(f"modo relacional sem politica de iniciativa: {relationship_mode!r}")
    identity = npc_payload.get("identidade_relacional", "ren")
    if not isinstance(identity, str) or not identity.strip():
        raise ValueError("identidade_relacional precisa ser string nao vazia")
    risk = npc_payload["medidores"].get("risco_percebido")
    result = {
        "schema_iniciativa_social": SCHEMA,
        "modo": policy["modo"],
        "identidade_relacional": identity.strip(),
        "pode_iniciar": policy["pode_iniciar"],
        "exige_motivo": policy["exige_motivo"],
        "escopo": list(policy["escopo"]),
        "risco_alto": isinstance(risk, int) and risk >= HIGH_RISK_MIN,
        "limite": LIMIT,
    }
    return validate_projection(result)


def validate_projection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_iniciativa_social") != SCHEMA:
        raise ValueError("projecao de iniciativa social invalida")
    if value.get("modo") not in {item["modo"] for item in POLICIES.values()}:
        raise ValueError("modo de iniciativa social invalido")
    if not isinstance(value.get("identidade_relacional"), str) or not value["identidade_relacional"].strip():
        raise ValueError("iniciativa social sem identidade relacional")
    for key in ("pode_iniciar", "exige_motivo", "risco_alto"):
        if not isinstance(value.get(key), bool):
            raise ValueError(f"{key} precisa ser booleano")
    scope = value.get("escopo")
    if not isinstance(scope, list) or not 1 <= len(scope) <= MAX_OPENINGS:
        raise ValueError("escopo de iniciativa social invalido")
    if any(not isinstance(item, str) or not item.strip() or len(item) > 120 for item in scope):
        raise ValueError("escopo de iniciativa social precisa ser compacto")
    limit = value.get("limite")
    if not isinstance(limit, str) or not limit.strip() or len(limit) > 220:
        raise ValueError("limite de iniciativa social invalido")
    return value


def authorize_censorship_topic(
    *,
    npc_id: str,
    topic_id: str,
    fact_id: str,
    fact_digest: str,
    previous: dict[str, str] | None,
) -> dict[str, str] | None:
    """Autoriza objeção por identidade causal, nunca por análise da prosa.

    A mesma combinação NPC+tópico+digest é silêncio estrutural. Um digest novo,
    vindo de fato canônico novo ou materialmente alterado, reabre a possibilidade
    de resposta. A função não cria presença, conhecimento ou o próprio fato.
    """
    values = {
        "npc_id": npc_id,
        "topico_censura": topic_id,
        "fato_id": fact_id,
        "fato_digest": fact_digest,
    }
    for key, value in values.items():
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > MAX_CAUSAL_ID:
            raise ValueError(f"{key} precisa ser ID causal compacto")
        values[key] = value.strip()
    if previous is not None:
        if not isinstance(previous, dict):
            raise ValueError("histórico de tópico precisa ser mapa")
        if (
            previous.get("npc_id") == values["npc_id"]
            and previous.get("topico_censura") == values["topico_censura"]
            and previous.get("fato_digest") == values["fato_digest"]
        ):
            return None
    return values
