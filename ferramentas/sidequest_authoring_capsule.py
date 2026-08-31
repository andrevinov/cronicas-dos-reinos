#!/usr/bin/env python3
"""Task 49 — Single Authoring Capsule & Safe Transport.

A cápsula é uma interface autoral única sobre Tasks 41/43/44/45. Ela não ganha
nenhuma autoridade nova: ``compile_block`` apenas projeta o payload para o
contrato Task46 legado e os validadores existentes continuam sendo a fonte de
verdade para autoria, recompensa, integridade adversarial e progressão.
"""
from __future__ import annotations

import copy
from typing import Any

import yaml

import _progressao_sidequests_task45_base as progress
import integridade_adversarial as adversarial
import oportunidades
import recompensas_sidequest as rewards
import sidequests_emergentes as emergent

SCHEMA = 1
CAPSULE_KEY = "capsula_autoral"
MAX_CONTRACT_BYTES = 3 * 1024
MAX_CAPSULE_BYTES = 64 * 1024

CAPSULE_KEYS = {"schema", "aventura", "recompensas", "adversidade", "progressao"}
LEGACY_BLOCK_KEYS = {
    "oferta",
    "quest",
    "contrato_recompensa",
    "contrato_adversarial",
    "contrato_progressao",
}
TASK49_BLOCK_KEYS = {"oferta", CAPSULE_KEY}

QUEST_FIELDS = [
    "titulo", "tipo", "origem_causal", "quest_giver", "oferta", "premissa",
    "prazo", "objetivo", "fases", "locais", "npcs_existentes", "npcs_novos",
    "antagonistas", "juppongatana", "condicoes_sucesso", "condicoes_falha",
    "stakes", "recompensas", "relacao_canone", "segredos", "bifurcacoes",
]
REWARD_FIELDS = [
    "recompensa_principal", "recompensas_opcionais", "recompensas_descobríveis",
    "recompensas_condicionais", "perdas_possiveis",
]
ADVERSITY_FIELDS = [
    "objetivos_antagonistas", "capacidades_disponiveis", "conhecimentos_disponiveis",
    "estado_se_ren_nao_intervier", "escaladas_possiveis", "consequencias_de_falha",
    "consequencias_de_inacao", "alvos_em_risco", "gravidade_maxima_causal",
]
PROGRESSION_FIELDS = [
    "regra_sucesso", "regra_falha", "dependencias_fases", "efeitos_escaladas",
]


class SidequestAuthoringCapsuleError(ValueError):
    pass


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SidequestAuthoringCapsuleError(f"{label} deve ser mapa")
    return value


def _bytes(value: Any) -> int:
    return len(yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8"))


def authoring_contract(package: dict[str, Any]) -> dict[str, Any]:
    """Contrato compacto que acompanha somente a preparação rara Task40."""
    horizon = _map(package.get("horizonte_intencoes_canonicas"), "pacote.horizonte")
    contract = {
        "schema_capsula_autoral": SCHEMA,
        "chave_transacao": "sidequest_emergente",
        "forma": {
            "sidequest_emergente": ["oferta", CAPSULE_KEY],
            "oferta": ["materializar=true", "evidencia", "resumo"],
            CAPSULE_KEY: ["schema=1", "aventura", "recompensas", "adversidade", "progressao"],
        },
        "campos": {
            "aventura": QUEST_FIELDS,
            "recompensas": REWARD_FIELDS,
            "adversidade": ADVERSITY_FIELDS,
            "progressao": PROGRESSION_FIELDS,
        },
        "enums": {
            "aventura.tipo": sorted(oportunidades.VALID_TYPES),
            "quest_giver.tipo": sorted(emergent.QUEST_GIVER_TYPES),
            "prazo.tipo": ["temporal", "enquanto_condicao", "a_qualquer_momento"],
            "local.tipo": sorted(emergent.LOCATION_TYPES),
            "antagonista.tipo": sorted(emergent.ANTAGONIST_TYPES),
            "juppongatana.estatuto": sorted(emergent.JUPPONGATANA_ROLES),
            "recompensa.tipo": sorted(emergent.REWARD_TYPES),
            "recompensa.modo": sorted(emergent.REWARD_MODES),
            "recompensa.valor": sorted(emergent.REWARD_VALUES),
            "relacao_canone.modo": sorted(emergent.CANON_RELATIONS),
            "autoridade_recompensa.tipo": sorted(rewards.AUTHORITY_TYPES),
            "descoberta.falha": sorted(rewards.DISCOVERY_FAILURES),
            "descoberta.entrega": sorted(rewards.DISCOVERY_DELIVERY),
            "adversidade.gravidade": list(adversarial.SEVERITIES),
            "adversidade.prioridade": sorted(adversarial.PRIORITIES),
            "adversidade.fonte_capacidade": sorted(adversarial.CAPABILITY_SOURCES),
            "adversidade.fonte_conhecimento": sorted(adversarial.KNOWLEDGE_SOURCES),
            "progressao.regra": sorted(progress.SUCCESS_RULES | progress.FAILURE_RULES),
        },
        "contexto": {
            "intencoes_canonicas_disponiveis": [
                item.get("evento_id")
                for item in (horizon.get("compativeis") or [])
                if isinstance(item, dict) and item.get("evento_id") is not None
            ],
            "juppongatana_disponiveis": [
                item.get("id")
                for item in (package.get("juppongatana_possiveis") or [])
                if isinstance(item, dict) and item.get("id") is not None
            ],
            "tier_recompensa": (package.get("envelope_recompensa") or {}).get("tier"),
            "teto_recompensa": (package.get("envelope_recompensa") or {}).get("teto_valor"),
        },
        "regras": [
            "preencha uma única cápsula; não consulte schemas internos Tasks41/43/44/45",
            "não escreva escolha, fala, intenção ou emoção futura de Ren",
            "a oferta só materializa se evidencia aparecer literalmente na narracao",
            "envie um único JSON completo por stdin no mesmo cronica concluir; não use write_stdin interativo nem arquivo temporário",
            "os validadores existentes continuam autoritativos e falham antes do writer",
        ],
    }
    size = _bytes(contract)
    if size > MAX_CONTRACT_BYTES:
        raise SidequestAuthoringCapsuleError(
            f"contrato autoral Task49 excede {MAX_CONTRACT_BYTES} bytes: {size}"
        )
    return contract


def compile_capsule(raw: Any) -> dict[str, Any]:
    """Projeta cápsula Task49 para as quatro entradas internas da Task46."""
    capsule = copy.deepcopy(_map(raw, CAPSULE_KEY))
    if set(capsule) != CAPSULE_KEYS:
        raise SidequestAuthoringCapsuleError(
            "capsula_autoral divergente; exige schema, aventura, recompensas, adversidade e progressao"
        )
    if capsule.get("schema") != SCHEMA:
        raise SidequestAuthoringCapsuleError(f"capsula_autoral.schema deve ser {SCHEMA}")
    if _bytes(capsule) > MAX_CAPSULE_BYTES:
        raise SidequestAuthoringCapsuleError(
            f"capsula_autoral excede {MAX_CAPSULE_BYTES} bytes"
        )
    for key in ("aventura", "recompensas", "adversidade", "progressao"):
        _map(capsule.get(key), f"capsula_autoral.{key}")
    return {
        "quest": copy.deepcopy(capsule["aventura"]),
        "contrato_recompensa": copy.deepcopy(capsule["recompensas"]),
        "contrato_adversarial": copy.deepcopy(capsule["adversidade"]),
        "contrato_progressao": copy.deepcopy(capsule["progressao"]),
    }


def compile_block(raw: Any) -> tuple[dict[str, Any], str]:
    """Aceita cápsula nova e preserva payload Task46 antigo para recovery."""
    block = copy.deepcopy(_map(raw, "sidequest_emergente"))
    keys = set(block)
    if keys == LEGACY_BLOCK_KEYS:
        return block, "legado_task46"
    if keys != TASK49_BLOCK_KEYS:
        raise SidequestAuthoringCapsuleError(
            "sidequest_emergente Task49 exige exatamente oferta + capsula_autoral"
        )
    compiled = compile_capsule(block[CAPSULE_KEY])
    return {"oferta": copy.deepcopy(block["oferta"]), **compiled}, "capsula_task49_v1"
