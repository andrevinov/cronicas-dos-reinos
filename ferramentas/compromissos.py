#!/usr/bin/env python3
"""Compatibilidade de compromissos + contrato NV-18 de obrigação temporal.

A implementação NV-17 permanece byte-a-byte em `_compromissos_nv17.py` e é
executada neste mesmo namespace para preservar identidade de módulo e monkeypatches.
A NV-18 acrescenta metadados causais opcionais a compromissos já existentes; o
registro legado continua válido quando não representa uma obrigação temporal.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

_LEGACY_SOURCE = Path(__file__).with_name("_compromissos_nv17.py")
_saved_name = globals().get("__name__", "compromissos")
globals()["__name__"] = "_compromissos_nv17_exec"
exec(compile(_LEGACY_SOURCE.read_text(encoding="utf-8"), str(_LEGACY_SOURCE), "exec"), globals(), globals())
globals()["__name__"] = _saved_name

_BASE_VALIDATE_RECORD = validate_record
_BASE_MAIN = main
TEMPORAL_SCHEMA = 1
TEMPORAL_STATES = {"ativa", "reconciliar"}
MAX_TEMPORAL_TEXT = 320
MAX_TEMPORAL_EVIDENCE = 720
MAX_TEMPORAL_SUPPORT = 3
MAX_TEMPORAL_PROTECTIONS = 4


def _temporal_text(value: Any, label: str, limit: int = MAX_TEMPORAL_TEXT) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CommitmentError(f"{label} deve ser texto não vazio")
    text = " ".join(value.split())
    if len(text) > limit:
        raise CommitmentError(f"{label} excede {limit} caracteres")
    return text


def _temporal_entity(value: Any, label: str) -> str:
    return _entity(value, label)


def _temporal_source(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"arquivo", "evidencia_literal"}:
        raise CommitmentError(f"{label} deve conter somente arquivo + evidencia_literal")
    raw_path = _temporal_text(value.get("arquivo"), f"{label}.arquivo", 180)
    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        raise CommitmentError(f"{label}.arquivo deve permanecer dentro do repositório")
    evidence = _temporal_text(
        value.get("evidencia_literal"), f"{label}.evidencia_literal", MAX_TEMPORAL_EVIDENCE
    )
    return {"arquivo": path.as_posix(), "evidencia_literal": evidence}


def _temporal_trigger(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CommitmentError(f"{label} deve ser objeto")
    allowed = {"instante", "data", "condicao"}
    extra = sorted(set(value) - allowed)
    if extra:
        raise CommitmentError(f"{label} possui campos desconhecidos: " + ", ".join(extra))
    present = [key for key in allowed if value.get(key) is not None]
    if len(present) != 1:
        raise CommitmentError(f"{label} exige exatamente um de instante, data ou condicao")
    key = present[0]
    if key == "instante":
        normalized, _ = _instant(value[key], f"{label}.instante")
        return {"instante": normalized}
    if key == "data":
        data = _temporal_text(value[key], f"{label}.data", 48)
        try:
            mundo.parse_instant(data, "00:00")
        except mundo.WorldEngineError as exc:
            raise CommitmentError(str(exc)) from exc
        return {"data": data}
    return {"condicao": _temporal_text(value[key], f"{label}.condicao", 240)}


def validate_temporal_obligation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CommitmentError("obrigacao_temporal deve ser objeto")
    allowed = {
        "schema",
        "estado",
        "responsavel",
        "destinatario",
        "local_ou_canal",
        "prazo_ou_condicao",
        "resultado_esperado",
        "modo_retorno",
        "fonte_canonica",
        "fontes_suporte",
        "protecoes",
    }
    extra = sorted(set(value) - allowed)
    if extra:
        raise CommitmentError(
            "campos desconhecidos em obrigacao_temporal: " + ", ".join(extra)
        )
    if value.get("schema") != TEMPORAL_SCHEMA:
        raise CommitmentError("obrigacao_temporal.schema deve ser 1")
    state = _temporal_text(value.get("estado"), "obrigacao_temporal.estado", 24)
    if state not in TEMPORAL_STATES:
        raise CommitmentError("obrigacao_temporal.estado deve ser ativa ou reconciliar")
    result: dict[str, Any] = {
        "schema": TEMPORAL_SCHEMA,
        "estado": state,
        "responsavel": _temporal_entity(
            value.get("responsavel"), "obrigacao_temporal.responsavel"
        ),
        "destinatario": _temporal_entity(
            value.get("destinatario"), "obrigacao_temporal.destinatario"
        ),
        "local_ou_canal": _temporal_text(
            value.get("local_ou_canal"), "obrigacao_temporal.local_ou_canal", 180
        ),
        "prazo_ou_condicao": _temporal_trigger(
            value.get("prazo_ou_condicao"), "obrigacao_temporal.prazo_ou_condicao"
        ),
        "resultado_esperado": _temporal_text(
            value.get("resultado_esperado"), "obrigacao_temporal.resultado_esperado"
        ),
        "modo_retorno": _temporal_text(
            value.get("modo_retorno"), "obrigacao_temporal.modo_retorno", 180
        ),
        "fonte_canonica": _temporal_source(
            value.get("fonte_canonica"), "obrigacao_temporal.fonte_canonica"
        ),
    }
    supports = value.get("fontes_suporte") or []
    if not isinstance(supports, list) or len(supports) > MAX_TEMPORAL_SUPPORT:
        raise CommitmentError(
            f"obrigacao_temporal.fontes_suporte deve ter no máximo {MAX_TEMPORAL_SUPPORT} itens"
        )
    if supports:
        result["fontes_suporte"] = [
            _temporal_source(item, f"obrigacao_temporal.fontes_suporte[{index}]")
            for index, item in enumerate(supports)
        ]
    protections = value.get("protecoes") or []
    if not isinstance(protections, list) or len(protections) > MAX_TEMPORAL_PROTECTIONS:
        raise CommitmentError(
            f"obrigacao_temporal.protecoes deve ter no máximo {MAX_TEMPORAL_PROTECTIONS} itens"
        )
    if protections:
        result["protecoes"] = [
            _temporal_text(item, f"obrigacao_temporal.protecoes[{index}]", 200)
            for index, item in enumerate(protections)
        ]
    return result


def validate_record(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or "obrigacao_temporal" not in value:
        return _BASE_VALIDATE_RECORD(value)
    legacy = deepcopy(value)
    temporal = legacy.pop("obrigacao_temporal")
    normalized = _BASE_VALIDATE_RECORD(legacy)
    normalized["obrigacao_temporal"] = validate_temporal_obligation(temporal)
    return normalized


def is_temporal(record: Any) -> bool:
    return isinstance(record, dict) and isinstance(record.get("obrigacao_temporal"), dict)


def create_temporal_delta(commitment_id: str, record: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_record(record)
    if not is_temporal(normalized):
        raise CommitmentError("create_temporal_delta exige obrigacao_temporal")
    return {
        "alvo": "estado",
        "op": "set",
        "caminho": commitment_path(commitment_id),
        "valor": normalized,
    }


if __name__ == "__main__":
    raise SystemExit(_BASE_MAIN())
