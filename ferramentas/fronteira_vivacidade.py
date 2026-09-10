"""Projeção determinística da fronteira global de vivacidade (NV-14).

Primeira fatia da NV-14: este módulo não consulta o repositório, não agenda nada e
não escolhe ações para Ren. Ele recebe candidatas já produzidas por fontes
explicitamente consultadas, escolhe no máximo uma pressão primária por janela e
mantém destino explícito para todas as demais. Quando não há candidata elegível,
emite um recibo compacto de calma que só existe se todos os domínios obrigatórios
tiverem cobertura declarada.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import yaml

import mundo

SCHEMA = 1
CALM_SCHEMA = 1
MAX_OUTPUT_BYTES = 4 * 1024
MAX_CANDIDATES = 12
MAX_SOURCES_PER_DOMAIN = 8

WINDOW_TRIGGERS = {"inicio_dia", "mudanca_periodo", "compressao_longa"}
CHECK_STATES = {"consultado", "nao_configurado"}
DECISIONS = {"entregue", "adiada", "bloqueada"}

# Cobertura mínima da NV-14. Cada domínio será ligado aos produtores existentes
# em fatias posteriores; a projeção pura já impede um falso "dia calmo" quando
# qualquer classe obrigatória simplesmente deixou de ser consultada.
REQUIRED_DOMAINS = (
    "entregas_contatos",
    "planos_compromissos",
    "operacoes_reacoes",
    "sidequests_vivas",
    "iniciativas_elenco",
    "ecologia_local",
    "ambiente_publico",
)


class LivenessBoundaryError(ValueError):
    """Contrato inválido da fronteira de vivacidade."""


def _text(value: Any, label: str, maximum: int = 260) -> str:
    if not isinstance(value, str):
        raise LivenessBoundaryError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if not result or len(result) > maximum:
        raise LivenessBoundaryError(
            f"{label} deve ser texto não vazio de até {maximum} caracteres"
        )
    return result


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()[:24]


def _size(value: Any) -> int:
    return len(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8")
    )


def _instant(value: Any, label: str) -> tuple[dict[str, str], mundo.WorldInstant]:
    if not isinstance(value, dict) or set(value) != {"data", "hora"}:
        raise LivenessBoundaryError(f"{label} exige exatamente data e hora")
    data = _text(value.get("data"), f"{label}.data", 80)
    hora = _text(value.get("hora"), f"{label}.hora", 5)
    if not re.fullmatch(r"[0-2][0-9]:[0-5][0-9]", hora):
        raise LivenessBoundaryError(f"{label}.hora exige HH:MM")
    try:
        instant = mundo.parse_instant(data, hora)
    except (ValueError, mundo.WorldEngineError) as exc:
        raise LivenessBoundaryError(str(exc)) from exc
    return {"data": data, "hora": hora}, instant


def _window(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"gatilho", "inicio", "fim"}:
        raise LivenessBoundaryError(
            "janela exige exatamente gatilho, inicio e fim"
        )
    trigger = _text(value.get("gatilho"), "janela.gatilho", 32)
    if trigger not in WINDOW_TRIGGERS:
        raise LivenessBoundaryError(f"gatilho de janela desconhecido: {trigger}")
    start, start_instant = _instant(value.get("inicio"), "janela.inicio")
    end, end_instant = _instant(value.get("fim"), "janela.fim")
    if end_instant < start_instant:
        raise LivenessBoundaryError("fim da janela não pode preceder o início")
    return {"gatilho": trigger, "inicio": start, "fim": end}


def _sources(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_SOURCES_PER_DOMAIN:
        raise LivenessBoundaryError(
            f"{label} deve ser lista de até {MAX_SOURCES_PER_DOMAIN} fontes"
        )
    result: list[str] = []
    for index, raw in enumerate(value):
        source = _text(raw, f"{label}[{index}]", 180)
        if source not in result:
            result.append(source)
    return result


def _checks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise LivenessBoundaryError("consultas deve ser lista")
    found: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise LivenessBoundaryError(f"consultas[{index}] deve ser mapa")
        allowed = {"dominio", "estado", "fontes", "motivo"}
        if set(raw) - allowed:
            raise LivenessBoundaryError(
                f"consultas[{index}] possui campos desconhecidos"
            )
        domain = _text(raw.get("dominio"), f"consultas[{index}].dominio", 48)
        if domain not in REQUIRED_DOMAINS:
            raise LivenessBoundaryError(f"domínio de vivacidade desconhecido: {domain}")
        if domain in found:
            raise LivenessBoundaryError(f"domínio consultado duas vezes: {domain}")
        state = _text(raw.get("estado"), f"consultas[{index}].estado", 32)
        if state not in CHECK_STATES:
            raise LivenessBoundaryError(f"estado de consulta inválido: {state}")
        sources = _sources(raw.get("fontes"), f"consultas[{index}].fontes")
        if state == "consultado" and not sources:
            raise LivenessBoundaryError(
                f"domínio {domain} marcado consultado precisa declarar fonte"
            )
        item: dict[str, Any] = {
            "dominio": domain,
            "estado": state,
            "fontes": sources,
        }
        reason = raw.get("motivo")
        if state == "nao_configurado":
            item["motivo"] = _text(reason, f"consultas[{index}].motivo", 180)
        elif reason is not None:
            item["motivo"] = _text(reason, f"consultas[{index}].motivo", 180)
        found[domain] = item

    missing = [domain for domain in REQUIRED_DOMAINS if domain not in found]
    if missing:
        raise LivenessBoundaryError(
            "cobertura incompleta da fronteira de vivacidade: " + ", ".join(missing)
        )
    return [found[domain] for domain in REQUIRED_DOMAINS]


def _candidate(value: Any, index: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LivenessBoundaryError(f"candidatas[{index}] deve ser mapa")
    required = {
        "id",
        "dominio",
        "tipo",
        "prioridade",
        "elegivel",
        "fundamento",
        "origem",
    }
    if set(value) != required:
        raise LivenessBoundaryError(
            f"candidatas[{index}] exige exatamente {', '.join(sorted(required))}"
        )
    candidate_id = _text(value.get("id"), f"candidatas[{index}].id", 96)
    domain = _text(value.get("dominio"), f"candidatas[{index}].dominio", 48)
    if domain not in REQUIRED_DOMAINS:
        raise LivenessBoundaryError(f"domínio de candidata desconhecido: {domain}")
    priority = value.get("prioridade")
    if not isinstance(priority, int) or isinstance(priority, bool) or not 0 <= priority <= 99:
        raise LivenessBoundaryError("prioridade deve ser inteiro entre 0 e 99")
    eligible = value.get("elegivel")
    if type(eligible) is not bool:
        raise LivenessBoundaryError("elegivel deve ser booleano")
    normalized = {
        "id": candidate_id,
        "dominio": domain,
        "tipo": _text(value.get("tipo"), f"candidatas[{index}].tipo", 64),
        "prioridade": priority,
        "elegivel": eligible,
        "fundamento": _text(
            value.get("fundamento"), f"candidatas[{index}].fundamento", 260
        ),
        "origem": _text(value.get("origem"), f"candidatas[{index}].origem", 180),
    }
    normalized["fingerprint"] = _digest(normalized)
    return normalized


def _calm_receipt(window: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    base = {
        "schema_recibo_calma": CALM_SCHEMA,
        "estado": "calma_justificada",
        "motivo": "nenhuma_pressao_elegivel",
        "janela_digest": _digest(window),
        "cobertura_digest": _digest(checks),
    }
    return {**base, "digest": _digest(base)}


def project(
    window: dict[str, Any],
    candidates: list[dict[str, Any]],
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Projeta uma janela sem I/O, RNG, scheduler ou decisão narrativa automática."""
    normalized_window = _window(window)
    normalized_checks = _checks(checks)
    if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
        raise LivenessBoundaryError(
            f"candidatas deve ser lista de até {MAX_CANDIDATES} itens"
        )
    normalized_candidates = [_candidate(raw, index) for index, raw in enumerate(candidates)]
    ids = [item["id"] for item in normalized_candidates]
    if len(ids) != len(set(ids)):
        raise LivenessBoundaryError("IDs de candidatas devem ser únicos na janela")

    coverage = {item["dominio"]: item for item in normalized_checks}
    for item in normalized_candidates:
        if coverage[item["dominio"]]["estado"] != "consultado":
            raise LivenessBoundaryError(
                f"candidata {item['id']} pertence a domínio não configurado"
            )

    ordered = sorted(
        normalized_candidates,
        key=lambda item: (item["prioridade"], item["id"]),
    )
    primary = next((item for item in ordered if item["elegivel"]), None)
    decisions: list[dict[str, Any]] = []
    for item in ordered:
        if not item["elegivel"]:
            decision = "bloqueada"
            reason = item["fundamento"]
        elif primary is not None and item["id"] == primary["id"]:
            decision = "entregue"
            reason = "primeira pressão elegível pela ordem prioridade,id"
        else:
            decision = "adiada"
            reason = (
                f"{primary['id']} ocupa o único slot primário desta janela"
                if primary is not None
                else "nenhuma pressão primária disponível"
            )
        decisions.append(
            {
                key: item[key]
                for key in (
                    "id",
                    "dominio",
                    "tipo",
                    "origem",
                    "prioridade",
                    "fingerprint",
                )
            }
            | {"decisao": decision, "motivo": reason}
        )

    eligible_count = sum(item["elegivel"] for item in ordered)
    result = {
        "schema_fronteira_vivacidade": SCHEMA,
        "mutante": False,
        "janela": normalized_window,
        "pressao_primaria": primary["id"] if primary is not None else None,
        "decisoes": decisions,
        "cobertura": normalized_checks,
        "recibo_calma": (
            _calm_receipt(normalized_window, normalized_checks)
            if primary is None
            else None
        ),
        "metricas": {
            "candidatas": len(ordered),
            "elegiveis": eligible_count,
            "primarias": 1 if primary is not None else 0,
            "max_primarias_por_janela": 1,
            "rng_novo": 0,
            "scheduler_novo": 0,
            "scan_global": 0,
            "chamadas_ia": 0,
        },
    }
    if _size(result) > MAX_OUTPUT_BYTES:
        raise LivenessBoundaryError(
            f"projeção de vivacidade excede {MAX_OUTPUT_BYTES} bytes; "
            "reduza as projeções dirigidas, não aumente o teto"
        )
    return result
