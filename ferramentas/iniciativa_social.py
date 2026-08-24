#!/usr/bin/env python3
"""Projecao pura de iniciativa social de NPC baseada nas Tasks 26 e 27.

Iniciativa social responde a uma pergunta estreita: quando um NPC ja esta
legitimamente presente ou existe um canal de contato canonico, ele pode abrir a
interacao por conta propria ou deve esperar um motivo concreto?

A camada nao cria presenca, encontro, mensagem, conhecimento, side quest,
compromisso, scheduler ou estado. Ela tambem nao autoriza conselho: o gate
anti-sermao da Task 27 continua valendo integralmente.
"""
from __future__ import annotations

from typing import Any

import dialogo_relacional

SCHEMA = 1
MAX_TEXT = 230
MAX_OPENINGS = 3
HIGH_RISK_MIN = dialogo_relacional.HIGH_RISK_MIN

MODE_POLICY: dict[str, dict[str, Any]] = {
    "alta_afinidade_alta_confianca": {
        "modo": "espontanea",
        "pode_iniciar_sem_solicitacao": True,
        "gatilho_externo_obrigatorio": False,
        "aberturas": [
            "saudacao, check-in ou assunto cotidiano breve",
            "convite, oferta ou pedido leve compativel com a relacao",
            "compartilhar necessidade propria ja sustentada pelo canone",
        ],
        "limite": "proximidade permite abrir a troca; nao permite decidir por Ren, fabricar intimidade nova ou despejar trama",
    },
    "alta_afinidade_baixa_confianca": {
        "modo": "afetiva_cautelosa",
        "pode_iniciar_sem_solicitacao": True,
        "gatilho_externo_obrigatorio": False,
        "aberturas": [
            "saudacao, check-in ou tentativa de proximidade",
            "pedido pessoal pequeno que nao dependa de confiança ainda inexistente",
            "tentar reparar ou esclarecer tensao ja canonica",
        ],
        "limite": "afeto pode puxar contato, mas nao autoriza confiar segredo, plano ou responsabilidade sensivel",
    },
    "baixa_afinidade_alta_confianca": {
        "modo": "funcional",
        "pode_iniciar_sem_solicitacao": True,
        "gatilho_externo_obrigatorio": True,
        "aberturas": [
            "abordagem profissional ligada ao papel do NPC",
            "pedido ou oferta de cooperacao no dominio em que ha confianca",
            "atualizacao concreta que o NPC legitimamente sabe e precisa compartilhar",
        ],
        "limite": "confianca funcional permite iniciativa profissional, nao intimidade pessoal ou vulnerabilidade inventada",
    },
    "baixa_afinidade_baixa_confianca": {
        "modo": "somente_motivo_concreto",
        "pode_iniciar_sem_solicitacao": False,
        "gatilho_externo_obrigatorio": True,
        "aberturas": [
            "necessidade, transacao, dever ou conflito ja presente na cena",
            "limite pratico que o papel do NPC exige comunicar",
        ],
        "limite": "nao fabricar conversa casual, confianca, carinho ou procura espontanea apenas para movimentar a cena",
    },
    "intermediaria_ou_desconhecida": {
        "modo": "situacional",
        "pode_iniciar_sem_solicitacao": False,
        "gatilho_externo_obrigatorio": True,
        "aberturas": [
            "assunto cotidiano ou funcional somente quando a cena e a relacao canonica o sustentarem",
            "motivo concreto ligado ao papel, necessidade ou contexto compartilhado",
        ],
        "limite": "valor neutro, cinco ou desconhecido nao vira espontaneidade, hostilidade ou intimidade por inferencia",
    },
}

GLOBAL_GUARDRAIL = (
    "So vale com presenca ou canal de contato ja legitimo. Nao cria encontro, deslocamento, conhecimento, segredo, "
    "side quest, compromisso ou evento; uma abertura devolve imediatamente agencia para Ren responder."
)

ADVICE_GUARDRAIL = (
    "Iniciativa social nao e iniciativa de conselho: censura ou aconselhamento continuam exigindo os gatilhos da Task 27."
)


def _identity(payload: dict[str, Any]) -> str:
    value = payload.get("identidade_relacional", "ren")
    if not isinstance(value, str) or not value.strip():
        raise ValueError("identidade_relacional precisa ser string nao vazia")
    return value.strip()


def project(
    npc_payload: Any,
    *,
    dialogue: dict[str, Any] | None = None,
    role: str | None = None,
) -> dict[str, Any] | None:
    """Projeta permissao/forma de iniciativa sem leitura ou estado adicional."""
    if not isinstance(npc_payload, dict) or not isinstance(npc_payload.get("medidores"), dict):
        return None

    if dialogue is None:
        dialogue = dialogo_relacional.project(npc_payload, role=role)
    if dialogue is None:
        return None
    dialogo_relacional.validate_projection(dialogue)

    relationship_mode = dialogue["modo"]
    if relationship_mode not in MODE_POLICY:
        raise ValueError(f"modo relacional sem politica de iniciativa: {relationship_mode!r}")
    policy = MODE_POLICY[relationship_mode]
    openings = list(policy["aberturas"])
    if not 1 <= len(openings) <= MAX_OPENINGS:
        raise ValueError("politica de iniciativa excede teto de aberturas")

    result: dict[str, Any] = {
        "schema_iniciativa_social": SCHEMA,
        "modo": policy["modo"],
        "identidade_relacional": _identity(npc_payload),
        "pode_iniciar_sem_solicitacao": policy["pode_iniciar_sem_solicitacao"],
        "gatilho_externo_obrigatorio": policy["gatilho_externo_obrigatorio"],
        "aberturas_permitidas": openings,
        "limite": policy["limite"],
        "guardrail": GLOBAL_GUARDRAIL,
        "conselho": ADVICE_GUARDRAIL,
    }
    if role:
        result["papel_base"] = role

    risk = dialogue.get("risco_percebido")
    if isinstance(risk, int) and risk >= HIGH_RISK_MIN:
        result["modulador_de_risco"] = (
            "Risco alto pode tornar a abertura mais cautelosa ou urgente quando houver motivo real; "
            "nao cria contato, sermão ou vigilancia por si so."
        )
    return result


def validate_projection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_iniciativa_social") != SCHEMA:
        raise ValueError("projecao de iniciativa social invalida")
    modes = {policy["modo"] for policy in MODE_POLICY.values()}
    if value.get("modo") not in modes:
        raise ValueError("modo de iniciativa social invalido")
    if not isinstance(value.get("identidade_relacional"), str) or not value["identidade_relacional"].strip():
        raise ValueError("iniciativa social sem identidade relacional")
    for key in ("pode_iniciar_sem_solicitacao", "gatilho_externo_obrigatorio"):
        if not isinstance(value.get(key), bool):
            raise ValueError(f"{key} precisa ser booleano")
    openings = value.get("aberturas_permitidas")
    if not isinstance(openings, list) or not 1 <= len(openings) <= MAX_OPENINGS:
        raise ValueError("aberturas_permitidas invalidas")
    if any(not isinstance(item, str) or not item.strip() or len(item) > MAX_TEXT for item in openings):
        raise ValueError("abertura social precisa ser texto compacto")
    for key in ("limite", "guardrail", "conselho"):
        text = value.get(key)
        if not isinstance(text, str) or not text.strip() or len(text) > 360:
            raise ValueError(f"{key} de iniciativa social invalido")
    if "modulador_de_risco" in value:
        text = value["modulador_de_risco"]
        if not isinstance(text, str) or not text.strip() or len(text) > 260:
            raise ValueError("modulador_de_risco invalido")
    return value
