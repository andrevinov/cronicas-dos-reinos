#!/usr/bin/env python3
"""Rubrica determinística de qualidade da abordagem antes de testes de habilidade.

A Task 20 é uma house rule pequena: um plano que realmente melhora as condições
do teste pode receber de +0 a +3 sem substituir bônus da ficha, vantagem,
desvantagem ou a CD. Cada ponto vem de um critério independente e precisa ser
justificado antes de qualquer RNG.

A camada é pura: não lê nem escreve o repositório e não rola dados.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

SCHEMA = 1
CRITERIA = ("preparacao", "informacao", "adequacao")
MAX_BONUS = 3
MIN_EVIDENCE_CHARS = 8
MAX_EVIDENCE_CHARS = 180
LEVELS = {
    0: "direta",
    1: "preparada",
    2: "forte",
    3: "excepcional",
}
LABELS = {
    "preparacao": "preparação",
    "informacao": "uso de informação",
    "adequacao": "adequação ao problema",
}
RULE = (
    "avaliar antes do dado; cada critério precisa favorecer este teste específico; "
    "não altera CD, não substitui bônus da ficha e não torna ação impossível possível"
)


class ApproachQualityError(ValueError):
    """Erro de contrato da rubrica de qualidade da abordagem."""


def _clean(value: Any, criterion: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ApproachQualityError(f"{criterion}: evidência deve ser texto")
    text = " ".join(value.split())
    if not text:
        raise ApproachQualityError(f"{criterion}: evidência vazia")
    if len(text) < MIN_EVIDENCE_CHARS:
        raise ApproachQualityError(
            f"{criterion}: evidência precisa ter ao menos {MIN_EVIDENCE_CHARS} caracteres"
        )
    if len(text) > MAX_EVIDENCE_CHARS:
        raise ApproachQualityError(
            f"{criterion}: evidência excede {MAX_EVIDENCE_CHARS} caracteres"
        )
    return text


def _fingerprint(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(re.findall(r"[a-z0-9]+", normalized))


def evaluate(
    *,
    preparacao: str | None = None,
    informacao: str | None = None,
    adequacao: str | None = None,
) -> dict[str, Any]:
    """Calcula +0/+1/+2/+3 a partir de três evidências independentes.

    A função não decide se a ação é possível nem se uma alegação é verdadeira;
    isso continua sendo responsabilidade do gate/narrador. Ela garante que o
    bônus seja explícito, limitado, audível e não conte a mesma justificativa em
    dois critérios.
    """
    supplied = {
        "preparacao": _clean(preparacao, "preparacao"),
        "informacao": _clean(informacao, "informacao"),
        "adequacao": _clean(adequacao, "adequacao"),
    }
    criteria: list[dict[str, str]] = []
    seen: dict[str, str] = {}
    for criterion in CRITERIA:
        evidence = supplied[criterion]
        if evidence is None:
            continue
        fingerprint = _fingerprint(evidence)
        previous = seen.get(fingerprint)
        if previous is not None:
            raise ApproachQualityError(
                f"mesma evidência não pode pontuar {previous} e {criterion}"
            )
        seen[fingerprint] = criterion
        criteria.append(
            {
                "id": criterion,
                "nome": LABELS[criterion],
                "evidencia": evidence,
            }
        )

    bonus = len(criteria)
    if not 0 <= bonus <= MAX_BONUS:
        raise ApproachQualityError("bônus de abordagem fora do contrato 0..3")
    return {
        "schema_qualidade_abordagem": SCHEMA,
        "tipo": "qualidade_abordagem",
        "aplicacao": "pre_rolagem",
        "bonus": bonus,
        "nivel": LEVELS[bonus],
        "criterios": criteria,
        "regra": RULE,
    }


def compact_modifier(result: dict[str, Any]) -> dict[str, Any]:
    """Projeção compacta para `endpoints.modificadores`, sem perder auditoria."""
    bonus = result.get("bonus")
    if not isinstance(bonus, int) or isinstance(bonus, bool) or not 0 <= bonus <= MAX_BONUS:
        raise ApproachQualityError("resultado de qualidade inválido")
    criteria = result.get("criterios")
    if not isinstance(criteria, list):
        raise ApproachQualityError("resultado sem critérios")
    return {
        "tipo": "qualidade_abordagem",
        "aplicacao": "pre_rolagem",
        "bonus": bonus,
        "nivel": LEVELS[bonus],
        "criterios": [
            {"id": item["id"], "evidencia": item["evidencia"]}
            for item in criteria
            if isinstance(item, dict)
        ],
    }


def annotation(result: dict[str, Any]) -> str:
    """Texto curto anexado à saída do rolador quando há bônus positivo."""
    bonus = int(result.get("bonus") or 0)
    if bonus <= 0:
        return ""
    ids = ", ".join(
        str(item.get("id")) for item in result.get("criterios") or [] if isinstance(item, dict)
    )
    return f"Abordagem +{bonus} ({LEVELS[bonus]}: {ids})"
