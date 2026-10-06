"""Contratos de finalidade do catálogo; não pontua nem altera a campanha."""
from __future__ import annotations

from typing import Any


DIMENSIONS = {"operacao", "oportunidade", "efeito_persistente", "experiencia"}
REQUIRED_FIELDS = {
    "criterio_id", "responsavel", "unidade", "objetivo_jogo", "gatilho_legitimo",
    "fontes_necessarias", "resultado_verificavel", "negativa_valida",
    "falha_observavel", "dimensoes", "guardrails", "sem_evidencia",
}


def validate_objectives(catalog: dict[str, Any]) -> None:
    """Catálogos históricos sem o contrato continuam legíveis.

    A revisão pós-hoc consome os objetivos; presença de contrato não prova
    qualidade nem instrumentação retroativa de uma sessão antiga.
    """
    policy = catalog.get("contrato_objetivos_avaliacao")
    if policy is None:
        return
    if not isinstance(policy, dict) or policy.get("schema") != 1:
        raise ValueError("contrato de objetivos exige schema 1")
    if policy.get("estado") not in {"especificado_aguardando_consumo", "consumido_em_revisao_poshoc"}:
        raise ValueError("estado do consumo de objetivos desconhecido")
    if set(policy.get("dimensoes", [])) != DIMENSIONS:
        raise ValueError("contrato deve separar as quatro dimensões de avaliação")
    for key in (
        "sucesso_operacional_nao_confirma_experiencia",
        "oportunidade_independe_de_recibo",
        "guardrail_fora_da_media",
        "ausencia_de_fonte_nao_e_negativa",
    ):
        if policy.get(key) is not True:
            raise ValueError(f"contrato exige {key}=true")
    if policy.get("sem_evidencia") != "indeterminado_fora_do_denominador":
        raise ValueError("ausência de evidência deve permanecer indeterminada")
    sampling = policy.get("amostragem", {})
    if sampling != {
        "provisoria": "uma_unidade_confirmada_sem_afirmacao_longitudinal",
        "sessoes_comparaveis_minimas": 3,
        "oportunidades_por_modulo_minimas": 10,
        "criterio_raro": "episodio_controlado_nao_substitui_ocorrencia_real",
        "natureza": "limite_de_processo_nao_garantia_estatistica",
    }:
        raise ValueError("política de amostragem diverge do contrato congelado")
    criteria: set[str] = set()
    count = 0
    for module in catalog.get("modulos", []):
        owner = module["id"]
        for capability in module["subcapacidades"]:
            label = f"{owner}.{capability['id']}"
            objective = capability.get("contrato_objetivo")
            if not isinstance(objective, dict) or set(objective) != REQUIRED_FIELDS:
                raise ValueError(f"{label}: contrato de objetivo ausente ou incompleto")
            for key in REQUIRED_FIELDS - {"fontes_necessarias", "dimensoes", "guardrails"}:
                if not isinstance(objective[key], str) or not objective[key].strip():
                    raise ValueError(f"{label}: {key} exige texto não vazio")
            if objective["criterio_id"] != label or label in criteria:
                raise ValueError(f"{label}: identidade do critério divergente ou duplicada")
            criteria.add(label)
            if objective["responsavel"] != owner:
                raise ValueError(f"{label}: responsável deve ser o módulo proprietário")
            if objective["unidade"] != module["unidade_analise"]:
                raise ValueError(f"{label}: unidade diverge do módulo")
            for key in ("fontes_necessarias", "dimensoes", "guardrails"):
                values = objective[key]
                if not isinstance(values, list) or not values or any(
                    not isinstance(value, str) or not value.strip() for value in values
                ) or len(values) != len(set(values)):
                    raise ValueError(f"{label}: {key} exige valores únicos e não vazios")
            if not set(objective["dimensoes"]) <= DIMENSIONS:
                raise ValueError(f"{label}: dimensão desconhecida")
            if "oportunidade" not in objective["dimensoes"]:
                raise ValueError(f"{label}: ausência de ativação precisa ser avaliável")
            if set(objective["guardrails"]) != set(module["guardrails_aplicaveis"]):
                raise ValueError(f"{label}: guardrails do módulo devem ser preservados")
            if objective["sem_evidencia"] != policy["sem_evidencia"]:
                raise ValueError(f"{label}: ausência de evidência não pode virar aprovação")
            count += 1
    if not count:
        raise ValueError("catálogo de objetivos vazio")
