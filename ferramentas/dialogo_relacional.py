#!/usr/bin/env python3
"""Modulador puro de diálogo baseado no estado relacional da Task 26.

Não lê arquivos, não escolhe fala e não cria conhecimento. Recebe o fragmento de
NPC já carregado por ``contexto npc`` e projeta como afinidade, confiança e risco
modulam o papel conversacional existente.

A regra central é negativa: relação não autoriza sermão automático. Conselho,
censura ou moralização só entram quando há gatilho contextual concreto e o tema
cabe no limite de autoridade do NPC.
"""
from __future__ import annotations

from typing import Any

import estado_relacional

SCHEMA = 1
LOW_MAX = 4
HIGH_MIN = 6
HIGH_RISK_MIN = 8
MAX_TEXT = 220
MAX_ADVICE_TRIGGERS = 3

MODES: dict[str, dict[str, str]] = {
    "baixa_afinidade_baixa_confianca": {
        "tom": "formal, contido ou desconfiado; pouca intimidade presumida",
        "abertura": "responde ao necessário e preserva vulnerabilidade, favores e informação pessoal",
        "discordancia": "contesta fato, limite ou risco concreto; não transforma antipatia em lição moral",
    },
    "alta_afinidade_baixa_confianca": {
        "tom": "calor humano ou afeto visível, mas com reserva sobre palavra, plano ou julgamento de Ren",
        "abertura": "pode buscar proximidade pessoal, porém hesita antes de depender de Ren ou seguir seu plano",
        "discordancia": "fala como alguém que se importa e está frustrado ou preocupado, sem usar afeto como licença para sermão",
    },
    "baixa_afinidade_alta_confianca": {
        "tom": "respeito profissional e direto, sem intimidade que a relação ainda não sustenta",
        "abertura": "coopera no domínio em que Ren já provou competência, preservando distância pessoal",
        "discordancia": "questiona método, custo ou risco; evita julgar caráter ou ensinar Ren a viver",
    },
    "alta_afinidade_alta_confianca": {
        "tom": "espontâneo e caloroso; humor, familiaridade ou vulnerabilidade podem aparecer quando combinam com a personalidade",
        "abertura": "pode compartilhar opinião, preocupação ou necessidade sem ritual formal e aceitar apoio com menos defesa",
        "discordancia": "franqueza de alguém próximo: uma objeção concreta basta; não repetir reprimenda já compreendida",
    },
    "intermediaria_ou_desconhecida": {
        "tom": "seguir personalidade e papel atual sem presumir intimidade, hostilidade ou certeza ausentes do estado",
        "abertura": "calibrar pela cena e pela prosa canônica da relação; valor desconhecido não deve ser inventado",
        "discordancia": "apontar o problema concreto da cena sem usar a incerteza como pretexto para moralização genérica",
    },
}

ADVICE_TRIGGERS = (
    "Ren pediu opinião, conselho ou avaliação",
    "o tema cai diretamente no papel/responsabilidade do NPC",
    "há risco imediato que torna silêncio artificial ou irresponsável",
)

ANTI_SERMON = (
    "Não converter conversa casual, saudação, discordância ou cuidado em sermão. "
    "Quando conselho couber, preferir uma observação concreta e devolver espaço para Ren responder."
)


def _axis(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 10:
        raise ValueError(f"medidor relacional inválido: {value!r}")
    return value


def relationship_mode(affinity: int | None, trust: int | None) -> str:
    affinity = _axis(affinity)
    trust = _axis(trust)
    if affinity is None or trust is None or affinity == 5 or trust == 5:
        return "intermediaria_ou_desconhecida"
    affinity_high = affinity >= HIGH_MIN
    trust_high = trust >= HIGH_MIN
    if affinity_high and trust_high:
        return "alta_afinidade_alta_confianca"
    if affinity_high and trust <= LOW_MAX:
        return "alta_afinidade_baixa_confianca"
    if affinity <= LOW_MAX and trust_high:
        return "baixa_afinidade_alta_confianca"
    return "baixa_afinidade_baixa_confianca"


def project(npc_payload: Any, *, role: str | None = None) -> dict[str, Any] | None:
    """Projeta orientação compacta usando somente dados já carregados.

    Retorna ``None`` quando não há medidores. Isso preserva compatibilidade com
    stubs puramente técnicos e NPCs que ainda não possuam relação operacional.
    """
    if not isinstance(npc_payload, dict):
        return None
    meters = npc_payload.get("medidores")
    if not isinstance(meters, dict):
        return None
    normalized = estado_relacional.validate_meters(
        meters,
        entity_id=str(npc_payload.get("nome") or "npc"),
    )
    affinity = normalized["vinculo"]
    trust = normalized["confianca"]
    risk = normalized["risco_percebido"]
    mode = relationship_mode(affinity, trust)
    template = MODES[mode]
    result: dict[str, Any] = {
        "schema_dialogo_relacional": SCHEMA,
        "modo": mode,
        "afinidade": affinity,
        "confianca": trust,
        "risco_percebido": risk,
        "tom": template["tom"],
        "abertura": template["abertura"],
        "discordancia": template["discordancia"],
        "conselho": {
            "iniciativa": "somente_com_gatilho",
            "gatilhos": list(ADVICE_TRIGGERS),
            "guardrail": ANTI_SERMON,
        },
    }
    if role:
        result["papel_base"] = role
    if risk is not None and risk >= HIGH_RISK_MIN:
        result["modulador_de_risco"] = (
            "Risco alto pode endurecer limite, urgência ou cautela, mas não apaga afeto/confiança "
            "nem autoriza censura repetitiva."
        )
    return result


def validate_projection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema_dialogo_relacional") != SCHEMA:
        raise ValueError("projeção de diálogo relacional inválida")
    mode = value.get("modo")
    if mode not in MODES:
        raise ValueError(f"modo relacional inválido: {mode!r}")
    for key in ("tom", "abertura", "discordancia"):
        text = value.get(key)
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
            raise ValueError(f"{key} precisa ser texto compacto <= {MAX_TEXT} caracteres")
    advice = value.get("conselho")
    if not isinstance(advice, dict) or advice.get("iniciativa") != "somente_com_gatilho":
        raise ValueError("conselho precisa ser explicitamente gated")
    triggers = advice.get("gatilhos")
    if not isinstance(triggers, list) or not 1 <= len(triggers) <= MAX_ADVICE_TRIGGERS:
        raise ValueError("gatilhos de conselho inválidos")
    guardrail = advice.get("guardrail")
    if not isinstance(guardrail, str) or not guardrail.strip() or len(guardrail) > 320:
        raise ValueError("guardrail anti-sermão inválido")
    return value
