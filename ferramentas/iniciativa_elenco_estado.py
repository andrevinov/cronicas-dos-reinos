#!/usr/bin/env python3
"""Recibos reservados de decisão de iniciativa social da NV-16."""
from __future__ import annotations

import copy
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

SCHEMA = 1
STATE = Path("narrador/iniciativas-elenco/estado.yaml")
STATE_NATURE = "controle_reservado"
MAX_STATE_BYTES = 128 * 1024
MAX_RECORDS = 256
MAX_HISTORY = 4
RESULTS = {
    "apresentada",
    "adiada_por_pressao_superior",
    "silencio_justificado",
    "nao_elegivel",
}
TERMINAL_RESULTS = {"apresentada", "silencio_justificado", "nao_elegivel"}


class InitiativeStateError(ValueError):
    pass


def empty_state() -> dict[str, Any]:
    return {
        "schema_estado_iniciativa_elenco": SCHEMA,
        "natureza": STATE_NATURE,
        "decisoes": {},
        "ordem_recente": [],
    }


def _record(record_id: str, raw: Any) -> dict[str, Any]:
    expected = {
        "id", "janela_id", "janela_tipo", "cena_id", "npc_id", "presenca",
        "proposta_digest", "resultado", "motivo_codigo", "motivo",
        "evidencia_literal", "pressao_superior", "ticket_id", "transacao_id", "historico",
    }
    if not isinstance(raw, dict) or raw.get("id") != record_id or set(raw) != expected:
        raise InitiativeStateError(f"decisão de iniciativa inválida: {record_id}")
    if raw.get("resultado") not in RESULTS:
        raise InitiativeStateError(f"resultado inválido: {record_id}")
    for key in ("janela_id", "janela_tipo", "cena_id", "npc_id", "presenca", "proposta_digest"):
        if not isinstance(raw.get(key), str) or not raw[key]:
            raise InitiativeStateError(f"{record_id}.{key} inválido")
    if len(raw["proposta_digest"]) != 64:
        raise InitiativeStateError(f"{record_id}.proposta_digest inválido")
    for key in ("motivo_codigo", "motivo", "evidencia_literal", "pressao_superior", "ticket_id", "transacao_id"):
        if raw.get(key) is not None and not isinstance(raw[key], str):
            raise InitiativeStateError(f"{record_id}.{key} deve ser texto ou null")
    history = raw.get("historico")
    if not isinstance(history, list) or len(history) > MAX_HISTORY or any(not isinstance(item, dict) for item in history):
        raise InitiativeStateError(f"{record_id}.historico inválido")
    return raw


def load(repo: Path) -> dict[str, Any]:
    path = Path(repo) / STATE
    if not path.is_file():
        return empty_state()
    if path.stat().st_size > MAX_STATE_BYTES:
        raise InitiativeStateError(f"{STATE} excede orçamento")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise InitiativeStateError(str(exc)) from exc
    if (
        not isinstance(data, dict)
        or data.get("schema_estado_iniciativa_elenco") != SCHEMA
        or data.get("natureza") != STATE_NATURE
        or set(data) != {"schema_estado_iniciativa_elenco", "natureza", "decisoes", "ordem_recente"}
    ):
        raise InitiativeStateError("estado de iniciativa do elenco inválido")
    decisions, order = data.get("decisoes"), data.get("ordem_recente")
    if not isinstance(decisions, dict) or not isinstance(order, list):
        raise InitiativeStateError("coleções do estado de iniciativa são inválidas")
    if len(decisions) > MAX_RECORDS or len(order) != len(set(order)) or set(order) != set(decisions):
        raise InitiativeStateError("índice do estado de iniciativa é inválido ou excedido")
    for record_id, raw in decisions.items():
        _record(str(record_id), raw)
    return data


def _write(path: Path, value: dict[str, Any]) -> None:
    rendered = yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
    if len(rendered.encode("utf-8")) > MAX_STATE_BYTES:
        raise InitiativeStateError(f"estado de iniciativa excede {MAX_STATE_BYTES} bytes")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
        temp = Path(handle.name)
    os.replace(temp, path)


def _history(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: copy.deepcopy(record.get(key))
        for key in ("resultado", "motivo_codigo", "motivo", "evidencia_literal", "pressao_superior", "ticket_id", "transacao_id")
    }


def install(
    repo: Path,
    rows: list[dict[str, Any]],
    *,
    ticket_id: str,
    transaction_id: str,
) -> dict[str, Any]:
    state = load(repo)
    ids = {str(row.get("id")) for row in rows}
    if any(row.get("resultado") == "apresentada" for row in rows):
        conflict = next(
            (
                raw for raw in state["decisoes"].values()
                if raw.get("janela_id") == rows[0].get("janela_id")
                and raw.get("resultado") == "apresentada" and raw.get("id") not in ids
            ),
            None,
        ) if rows else None
        if conflict is not None:
            raise InitiativeStateError("janela já possui iniciativa apresentada")
    changed = False
    result = []
    for raw in rows:
        record_id = str(raw.get("id") or "")
        existing = state["decisoes"].get(record_id)
        record = {
            **copy.deepcopy(raw),
            "ticket_id": ticket_id,
            "transacao_id": transaction_id,
            "historico": [],
        }
        if isinstance(existing, dict):
            comparable = (
                "id", "janela_id", "janela_tipo", "cena_id", "npc_id", "presenca",
                "proposta_digest", "resultado", "motivo_codigo", "motivo",
                "evidencia_literal", "pressao_superior",
            )
            if all(existing.get(key) == record.get(key) for key in comparable):
                result.append({"decisao_id": record_id, "resultado": existing["resultado"], "reutilizado": True})
                continue
            if existing.get("resultado") != "adiada_por_pressao_superior":
                raise InitiativeStateError("retry de iniciativa diverge de decisão já registrada")
            record["historico"] = [*existing.get("historico", []), _history(existing)][-MAX_HISTORY:]
        _record(record_id, record)
        state["decisoes"][record_id] = record
        if record_id not in state["ordem_recente"]:
            state["ordem_recente"].append(record_id)
        changed = True
        result.append({"decisao_id": record_id, "resultado": record["resultado"], "reutilizado": False})
    while len(state["ordem_recente"]) > MAX_RECORDS:
        victim = next((item for item in state["ordem_recente"] if state["decisoes"][item]["resultado"] in TERMINAL_RESULTS), None)
        if victim is None:
            raise InitiativeStateError("muitas iniciativas adiadas; resolver janelas antes de criar novas")
        state["ordem_recente"].remove(victim)
        state["decisoes"].pop(victim, None)
    if changed:
        _write(Path(repo) / STATE, state)
    return {"resultados": result, "alterou_estado": changed}
