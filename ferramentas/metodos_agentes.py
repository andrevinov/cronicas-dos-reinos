#!/usr/bin/env python3
"""Contrato compacto para traduções operacionais por agente.

As linhas operacionais pertencem ao Contrato de Arco e descrevem problemas
estratégicos. Este módulo valida a tradução dessas linhas no fragmento do agente:
**como aquele agente tende a abordar o problema**, sem escolher alvo, momento ou
resultado concreto.

Não executa ações e não cria cânone. Tags são apenas metadados determinísticos
para a futura descoberta contextual dirigida.
"""
from __future__ import annotations

import re
from typing import Any

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,95}$")
VALID_MODALITIES = {"fisica", "indireta", "mista"}
MAX_LINES_PER_AGENT = 12
MAX_METHODS_PER_LINE = 4
MAX_TAGS_PER_METHOD = 8
MAX_APPROACH_CHARS = 360


class AgentMethodError(ValueError):
    pass


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AgentMethodError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise AgentMethodError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentMethodError(f"{label} deve ser texto não vazio")
    return value.strip()


def _id(value: Any, label: str) -> str:
    value = _text(value, label)
    if not ID_RE.fullmatch(value):
        raise AgentMethodError(f"{label} possui ID inválido: {value}")
    return value


def _strict(data: dict[str, Any], allowed: set[str], label: str) -> None:
    extra = set(data) - allowed
    if extra:
        raise AgentMethodError(
            f"{label} contém campos não permitidos: {', '.join(sorted(extra))}"
        )


def normalize(value: Any, *, agent_id: str = "agente") -> dict[str, list[dict[str, Any]]]:
    """Valida e normaliza ``metodos_operacionais`` de um fragmento de agente."""
    if value is None:
        return {}
    lines = _map(value, f"{agent_id}.metodos_operacionais")
    if len(lines) > MAX_LINES_PER_AGENT:
        raise AgentMethodError(
            f"{agent_id}.metodos_operacionais excede {MAX_LINES_PER_AGENT} linhas"
        )

    result: dict[str, list[dict[str, Any]]] = {}
    seen_method_ids: set[str] = set()
    for raw_line_id, raw_methods in lines.items():
        line_id = _id(raw_line_id, f"{agent_id}.metodos_operacionais.linha")
        methods = _list(raw_methods, f"{agent_id}.metodos_operacionais.{line_id}")
        if not methods or len(methods) > MAX_METHODS_PER_LINE:
            raise AgentMethodError(
                f"{agent_id}.metodos_operacionais.{line_id} deve ter entre 1 e "
                f"{MAX_METHODS_PER_LINE} métodos"
            )
        normalized_methods: list[dict[str, Any]] = []
        for index, raw in enumerate(methods):
            label = f"{agent_id}.metodos_operacionais.{line_id}[{index}]"
            method = _map(raw, label)
            _strict(method, {"id", "abordagem", "modalidade", "tags"}, label)
            method_id = _id(method.get("id"), f"{label}.id")
            if method_id in seen_method_ids:
                raise AgentMethodError(
                    f"{agent_id}: id de método duplicado: {method_id}"
                )
            seen_method_ids.add(method_id)
            approach = _text(method.get("abordagem"), f"{label}.abordagem")
            if len(approach) > MAX_APPROACH_CHARS:
                raise AgentMethodError(
                    f"{label}.abordagem excede {MAX_APPROACH_CHARS} caracteres"
                )
            modality = _text(method.get("modalidade"), f"{label}.modalidade")
            if modality not in VALID_MODALITIES:
                raise AgentMethodError(
                    f"{label}.modalidade inválida: {modality}"
                )
            tags = [_id(tag, f"{label}.tags") for tag in _list(method.get("tags"), f"{label}.tags")]
            if not tags or len(tags) > MAX_TAGS_PER_METHOD:
                raise AgentMethodError(
                    f"{label}.tags deve ter entre 1 e {MAX_TAGS_PER_METHOD} tags"
                )
            if len(tags) != len(set(tags)):
                raise AgentMethodError(f"{label}.tags não pode conter duplicatas")
            normalized_methods.append(
                {
                    "id": method_id,
                    "abordagem": approach,
                    "modalidade": modality,
                    "tags": tags,
                }
            )
        result[line_id] = normalized_methods
    return result


def from_agent(agent: Any, *, expected_agent_id: str | None = None) -> dict[str, list[dict[str, Any]]]:
    data = _map(agent, "fragmento de agente")
    agent_id = _id(data.get("id"), "agente.id")
    if expected_agent_id is not None and agent_id != expected_agent_id:
        raise AgentMethodError(
            f"fragmento de agente diverge do executor esperado: {agent_id} != {expected_agent_id}"
        )
    return normalize(data.get("metodos_operacionais"), agent_id=agent_id)


def for_line(
    agent: Any,
    line_id: str,
    *,
    expected_agent_id: str | None = None,
) -> list[dict[str, Any]]:
    line_id = _id(line_id, "linha operacional")
    return list(from_agent(agent, expected_agent_id=expected_agent_id).get(line_id, []))
