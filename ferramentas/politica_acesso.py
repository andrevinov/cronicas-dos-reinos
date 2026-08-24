#!/usr/bin/env python3
"""Política executável da escada de acesso de Crônicas dos Reinos.

A escada existe para reduzir contexto e, principalmente, evitar ciclos desnecessários
modelo → ferramenta → modelo. Ela não obriga o agente a atravessar cada degrau:
consultas dirigidas podem saltar níveis intermediários quando o alvo já é conhecido.
Buscas amplas e material frio, porém, exigem uma escalada explícita e justificada.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

LEVEL_ORDER = {
    "L0": 0,
    "L1": 1,
    "L2": 2,
    "L3": 3,
    "L4": 4,
    "L4T": 5,
    "L5": 6,
}

# Teto de bytes devolvidos ao modelo. O usuário pode pedir menos, nunca mais.
LEVEL_BUDGETS = {
    "L1": 4 * 1024,
    "L2": 8 * 1024,
    "L3": 8 * 1024,
    "L4": 12 * 1024,
    "L4T": 16 * 1024,
}

NEXT_LEVEL = {
    "L0": "L1",
    "L1": "L2",
    "L2": "L3",
    "L3": "L4",
    "L4": "L4T",
    "L4T": "L5",
    "L5": None,
}

STOP_CONDITION = {
    "L1": "Pare se o estado quente responder à lacuna concreta.",
    "L2": "Pare se a consulta dirigida responder à lacuna concreta.",
    "L3": "Pare se a descoberta limitada localizar a informação necessária.",
    "L4": "Pare se o histórico estruturado responder; não abra transcrição por precaução.",
    "L4T": "Use somente o trecho bruto necessário e pare assim que a evidência aparecer.",
}

GENERIC_REASONS = {
    "so conferir",
    "só conferir",
    "por precaucao",
    "por precaução",
    "para garantir",
    "ver se tem algo",
    "ver se ha algo",
    "ver se há algo",
    "conferir contexto",
    "buscar contexto",
}


class AccessPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class AccessDecision:
    level: str
    required_after: str | None
    direct_jump: bool = False


def _normalize_reason(value: str | None) -> str:
    return " ".join((value or "").strip().lower().split())


def _validate_reason(reason: str | None) -> str:
    normalized = _normalize_reason(reason)
    if len(normalized) < 16:
        raise AccessPolicyError(
            "escalada exige --motivo com a lacuna concreta ainda não respondida (mínimo 16 caracteres)"
        )
    if normalized in GENERIC_REASONS:
        raise AccessPolicyError(
            "--motivo genérico não basta; descreva qual informação faltou no nível anterior"
        )
    return reason.strip() if reason else ""


def _truncate(value: Any, limit: int = 140) -> Any:
    if not isinstance(value, str):
        return value
    text = " ".join(value.split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def _compact_small(value: Any, *, depth: int = 3) -> Any:
    """Compactação estrutural pequena usada só pela projeção L1."""
    if depth <= 0:
        if isinstance(value, (dict, list)):
            return "[… omitido …]"
        return _truncate(value, 100)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 8:
                out["_omitidos"] = len(value) - index
                break
            out[str(key)] = _compact_small(item, depth=depth - 1)
        return out
    if isinstance(value, list):
        result = [_compact_small(item, depth=depth - 1) for item in value[:4]]
        if len(value) > 4:
            result.append(f"… {len(value) - 4} item(ns) omitido(s)")
        return result
    return _truncate(value, 120)


def _compact_l1_result(value: Any) -> Any:
    """Mantém o estado quente útil sem deixar um pending apagar o contrato L1.

    Runtime completo continua disponível internamente; a política só projeta a
    resposta pública. Prosa temporal livre e ponteiros são omitidos do L1 porque
    não são necessários para decidir se uma consulta L2 deve acontecer.
    """
    if not isinstance(value, dict):
        return value
    out: dict[str, Any] = {}
    for key in ("sessao", "personagem", "recursos", "capacidades_contextuais"):
        if key in value:
            out[key] = value[key]

    time = value.get("tempo")
    if isinstance(time, dict):
        out["tempo"] = {
            key: time.get(key)
            for key in ("data", "hora_aproximada")
            if key in time
        }

    location = value.get("localizacao")
    if isinstance(location, dict):
        out["localizacao"] = {
            key: location.get(key)
            for key in ("area", "ponto_exato")
            if key in location
        }

    effects = value.get("efeitos_temporarios")
    if isinstance(effects, dict) and effects:
        compact_effects: dict[str, Any] = {}
        ordered = sorted(effects.items(), key=lambda item: str(item[0]))
        for effect_id, raw in ordered[:8]:
            compact_effects[str(effect_id)] = _compact_small(raw, depth=2)
        if len(ordered) > 8:
            compact_effects["_omitidos"] = len(ordered) - 8
        out["efeitos_temporarios"] = compact_effects

    if "compromissos" in value:
        out["compromissos"] = _compact_small(value["compromissos"], depth=4)
    if "sobreposicao_transacional" in value:
        out["sobreposicao_transacional"] = value["sobreposicao_transacional"]
    return out


def classify(
    command: str,
    *,
    current_session: int | None = None,
    session_term: str | None = None,
    historical: bool = False,
    transcripts: bool = False,
) -> AccessDecision:
    """Classifica uma consulta e informa a declaração de escalada exigida."""
    if command == "status":
        return AccessDecision("L1", None)
    if command in {
        "cena",
        "retomada",
        "npc",
        "local",
        "relacao",
        "recurso",
        "conhecimento",
        "regra",
        "reputacao",
    }:
        return AccessDecision("L2", None)
    if command == "sessao":
        term = (session_term or "").strip().lower()
        is_current = term in {"atual", "current"}
        if not is_current:
            try:
                is_current = current_session is not None and int(term) == current_session
            except ValueError:
                is_current = False
        if is_current:
            return AccessDecision("L2", None)
        # Alvo histórico conhecido: saltar a busca ampla L3 é MAIS econômico.
        return AccessDecision("L4", "L2", direct_jump=True)
    if command == "buscar":
        if transcripts:
            return AccessDecision("L4T", "L4")
        if historical:
            return AccessDecision("L4", "L3")
        return AccessDecision("L3", "L2")
    raise AccessPolicyError(f"comando sem política de acesso: {command}")


def validate_escalation(
    decision: AccessDecision,
    *,
    after: str | None,
    reason: str | None,
    reserved: bool = False,
) -> str | None:
    """Valida escaladas caras sem forçar degraus inúteis em consultas dirigidas."""
    if decision.required_after is None:
        if reserved:
            return _validate_reason(reason)
        return None

    if after != decision.required_after:
        extra = " (salto dirigido permitido)" if decision.direct_jump else ""
        raise AccessPolicyError(
            f"{decision.level} exige --apos {decision.required_after}{extra}; "
            "não escale apenas para conferir"
        )
    return _validate_reason(reason)


def effective_budget(level: str, requested: int) -> int:
    if level not in LEVEL_BUDGETS:
        raise AccessPolicyError(f"nível sem orçamento local: {level}")
    requested = max(1024, int(requested))
    return min(requested, LEVEL_BUDGETS[level])


def decorate(
    data: dict[str, Any],
    decision: AccessDecision,
    *,
    requested_budget: int,
    after: str | None,
    reason: str | None,
) -> tuple[dict[str, Any], int]:
    budget = effective_budget(decision.level, requested_budget)
    out = dict(data)
    if decision.level == "L1" and out.get("consulta", {}).get("comando") == "status":
        out["resultado"] = _compact_l1_result(out.get("resultado"))
    out["nivel"] = decision.level
    out["controle_acesso"] = {
        "teto_bytes": budget,
        "pare_se_suficiente": True,
        "condicao_de_parada": STOP_CONDITION.get(decision.level),
        "proximo_nivel": NEXT_LEVEL.get(decision.level),
        "depois_de": after,
        "salto_dirigido": decision.direct_jump,
    }
    if reason:
        out["controle_acesso"]["motivo_escalada"] = reason
    return out, budget


def explain() -> dict[str, Any]:
    """Representação pequena para testes/documentação, não para narração comum."""
    return {
        "ordem": ["L0", "L1", "L2", "L3", "L4", "L4T", "L5"],
        "orcamentos": dict(LEVEL_BUDGETS),
        "principios": [
            "L0 sempre vem primeiro e não chama ferramenta.",
            "consulta dirigida pode saltar nível intermediário quando o alvo já é conhecido.",
            "busca ampla L3+, histórico e transcrição exigem motivo explícito.",
            "transcrição é evidência bruta, não memória operacional.",
            "pare assim que a lacuna concreta estiver respondida.",
        ],
    }
