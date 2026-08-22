#!/usr/bin/env python3
"""Compromissos e encontros futuros como estado estruturado e compacto.

Compromisso não é scheduler. A camada apenas preserva obrigações já estabelecidas
na ficção e as projeta em L1/L2. Novos fatos entram no mesmo delta transacional do
turno; cumprir/cancelar remove o compromisso do estado corrente e o histórico
permanece na transação/transcrição.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any, Iterable

import yaml

import mundo

PREFIX = "compromissos."
ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
ENTITY_RE = re.compile(r"^[a-z][a-z0-9_]{0,79}$")
VALID_TYPES = {"compromisso", "encontro"}
MAX_SUMMARY = 220
MAX_DESCRIPTION = 160
MAX_INVOLVED = 6
HOT_LIMIT = 12


class CommitmentError(ValueError):
    pass


def _text(value: Any, label: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CommitmentError(f"{label} deve ser texto não vazio")
    result = " ".join(value.split())
    if len(result) > limit:
        raise CommitmentError(f"{label} excede {limit} caracteres")
    return result


def _entity(value: Any, label: str) -> str:
    value = _text(value, label, 80)
    if not ENTITY_RE.fullmatch(value):
        raise CommitmentError(f"{label} deve usar ID estável snake_case")
    return value


def _instant(value: Any, label: str) -> tuple[dict[str, str], mundo.WorldInstant]:
    if not isinstance(value, dict) or set(value) != {"data", "hora"}:
        raise CommitmentError(f"{label} deve conter somente data + hora")
    data = _text(value.get("data"), f"{label}.data", 48)
    hora = _text(value.get("hora"), f"{label}.hora", 5)
    try:
        instant = mundo.parse_instant(data, hora)
    except mundo.WorldEngineError as exc:
        raise CommitmentError(str(exc)) from exc
    return {"data": data, "hora": hora}, instant


def validate_record(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CommitmentError("compromisso deve ser objeto")
    allowed = {"tipo", "resumo", "envolvidos", "janela", "local_id"}
    extra = sorted(set(value) - allowed)
    if extra:
        raise CommitmentError("campos desconhecidos no compromisso: " + ", ".join(extra))

    kind = value.get("tipo")
    if kind not in VALID_TYPES:
        raise CommitmentError("tipo deve ser compromisso ou encontro")
    result: dict[str, Any] = {
        "tipo": kind,
        "resumo": _text(value.get("resumo"), "resumo", MAX_SUMMARY),
    }

    involved = value.get("envolvidos") or []
    if not isinstance(involved, list) or len(involved) > MAX_INVOLVED:
        raise CommitmentError(f"envolvidos deve ser lista com no máximo {MAX_INVOLVED} IDs")
    normalized = [_entity(item, f"envolvidos[{index}]") for index, item in enumerate(involved)]
    if len(normalized) != len(set(normalized)):
        raise CommitmentError("envolvidos não pode conter duplicatas")
    if normalized:
        result["envolvidos"] = normalized

    local_id = value.get("local_id")
    if local_id is not None:
        result["local_id"] = _entity(local_id, "local_id")

    raw_window = value.get("janela")
    if raw_window is not None:
        if not isinstance(raw_window, dict):
            raise CommitmentError("janela deve ser objeto")
        allowed_window = {"inicio", "fim", "descricao"}
        extra_window = sorted(set(raw_window) - allowed_window)
        if extra_window:
            raise CommitmentError("campos desconhecidos em janela: " + ", ".join(extra_window))
        window: dict[str, Any] = {}
        start_i: mundo.WorldInstant | None = None
        end_i: mundo.WorldInstant | None = None
        if raw_window.get("inicio") is not None:
            window["inicio"], start_i = _instant(raw_window["inicio"], "janela.inicio")
        if raw_window.get("fim") is not None:
            window["fim"], end_i = _instant(raw_window["fim"], "janela.fim")
        if raw_window.get("descricao") is not None:
            window["descricao"] = _text(raw_window["descricao"], "janela.descricao", MAX_DESCRIPTION)
        if not window:
            raise CommitmentError("janela precisa de início, fim ou descrição")
        if start_i is not None and end_i is not None and end_i.minute < start_i.minute:
            raise CommitmentError("janela.fim não pode anteceder janela.inicio")
        result["janela"] = window
    elif kind == "encontro":
        raise CommitmentError("encontro exige janela temporal")

    return result


def commitment_path(commitment_id: str) -> str:
    if not isinstance(commitment_id, str) or not ID_RE.fullmatch(commitment_id):
        raise CommitmentError("id de compromisso deve usar snake_case e até 64 caracteres")
    return PREFIX + commitment_id


def is_commitment_delta(delta: Any) -> bool:
    return (
        isinstance(delta, dict)
        and delta.get("alvo") == "estado"
        and isinstance(delta.get("caminho"), str)
        and str(delta["caminho"]).startswith(PREFIX)
    )


def validate_delta(delta: Any) -> dict[str, Any]:
    if not is_commitment_delta(delta):
        raise CommitmentError("delta não pertence à camada de compromissos")
    path = str(delta["caminho"])
    commitment_id = path[len(PREFIX):]
    if not ID_RE.fullmatch(commitment_id) or "." in commitment_id:
        raise CommitmentError(
            "compromissos são substituídos/removidos atomicamente; não escreva subcampos"
        )
    if delta.get("visibilidade", "operacional") != "operacional":
        raise CommitmentError("compromisso de Ren não pode usar visibilidade reservada")
    op = delta.get("op")
    if op == "set":
        validate_record(delta.get("valor"))
    elif op == "remove":
        if "valor" in delta:
            raise CommitmentError("remoção de compromisso não aceita valor")
    else:
        raise CommitmentError("compromisso aceita somente set do registro inteiro ou remove")
    return delta


def create_delta(commitment_id: str, record: dict[str, Any]) -> dict[str, Any]:
    normalized = validate_record(record)
    return {
        "alvo": "estado",
        "op": "set",
        "caminho": commitment_path(commitment_id),
        "valor": normalized,
    }


def close_delta(commitment_id: str) -> dict[str, Any]:
    return {"alvo": "estado", "op": "remove", "caminho": commitment_path(commitment_id)}


def _parse_optional(value: Any) -> mundo.WorldInstant | None:
    if not isinstance(value, dict):
        return None
    try:
        _, instant = _instant(value, "janela")
        return instant
    except CommitmentError:
        return None


def _situation(record: dict[str, Any], now: mundo.WorldInstant | None) -> tuple[str, int]:
    window = record.get("janela")
    if not isinstance(window, dict):
        return "sem_data", 10**18
    start = _parse_optional(window.get("inicio"))
    end = _parse_optional(window.get("fim"))
    if now is None:
        if start is not None:
            return "agendado", start.minute
        if end is not None:
            return "agendado", end.minute
        return "sem_instante_exato", 10**18
    if start is not None and now.minute < start.minute:
        return "futuro", start.minute
    if end is not None and now.minute > end.minute:
        return "janela_encerrada", end.minute
    if start is not None and end is not None:
        return "em_janela", start.minute
    if start is not None:
        return "devido", start.minute
    if end is not None:
        return "ate_limite", end.minute
    return "sem_instante_exato", 10**18


def _now(data: Any, hora: Any) -> mundo.WorldInstant | None:
    if not isinstance(data, str) or not isinstance(hora, str):
        return None
    try:
        return mundo.parse_instant(data, hora)
    except mundo.WorldEngineError:
        return None


def runtime_bundle(
    commitments: Any,
    data: Any,
    hora: Any,
    *,
    limit: int = HOT_LIMIT,
) -> dict[str, Any] | None:
    if commitments in (None, {}):
        return None
    if not isinstance(commitments, dict):
        raise CommitmentError("estado.compromissos deve ser mapa")
    now = _now(data, hora)
    ranked: list[tuple[int, int, str, dict[str, Any]]] = []
    rank = {
        "janela_encerrada": 0,
        "em_janela": 1,
        "devido": 2,
        "ate_limite": 3,
        "futuro": 4,
        "agendado": 4,
        "sem_instante_exato": 5,
        "sem_data": 6,
    }
    for commitment_id, raw in commitments.items():
        if not isinstance(commitment_id, str) or not ID_RE.fullmatch(commitment_id):
            raise CommitmentError(f"id inválido em estado.compromissos: {commitment_id!r}")
        record = validate_record(raw)
        situation, minute = _situation(record, now)
        item = copy.deepcopy(record)
        item["situacao_temporal"] = situation
        ranked.append((rank[situation], minute, commitment_id, item))
    ranked.sort(key=lambda item: (item[0], item[1], item[2]))
    visible = ranked[: max(1, limit)]
    result: dict[str, Any] = {
        "quantidade": len(ranked),
        "itens": {commitment_id: item for _, _, commitment_id, item in visible},
    }
    if len(ranked) > len(visible):
        result["omitidos"] = [commitment_id for _, _, commitment_id, _ in ranked[len(visible):]]
    return result


def _bundle_records(bundle: Any) -> tuple[dict[str, dict[str, Any]], list[str]]:
    if not isinstance(bundle, dict):
        return {}, []
    records: dict[str, dict[str, Any]] = {}
    for commitment_id, raw in (bundle.get("itens") or {}).items():
        if not isinstance(raw, dict):
            continue
        record = {key: copy.deepcopy(value) for key, value in raw.items() if key != "situacao_temporal"}
        try:
            records[str(commitment_id)] = validate_record(record)
        except CommitmentError:
            continue
    omitted = [str(item) for item in (bundle.get("omitidos") or []) if isinstance(item, str)]
    return records, omitted


def _apply_bundle(bundle: Any, deltas: list[dict[str, Any]], data: Any, hora: Any) -> dict[str, Any] | None:
    records, omitted = _bundle_records(bundle)
    omitted_set = set(omitted)
    for delta in deltas:
        validate_delta(delta)
        commitment_id = str(delta["caminho"])[len(PREFIX):]
        if delta["op"] == "remove":
            records.pop(commitment_id, None)
            omitted_set.discard(commitment_id)
            continue
        omitted_set.discard(commitment_id)
        records[commitment_id] = validate_record(delta["valor"])

    visible = runtime_bundle(records, data, hora, limit=HOT_LIMIT)
    if visible is None and not omitted_set:
        return None
    if visible is None:
        return {"quantidade": len(omitted_set), "itens": {}, "omitidos": sorted(omitted_set)}
    new_omitted = set(visible.get("omitidos") or []) | omitted_set
    visible["quantidade"] = len(visible.get("itens") or {}) + len(new_omitted)
    if new_omitted:
        visible["omitidos"] = sorted(new_omitted)
    else:
        visible.pop("omitidos", None)
    return visible


def apply_pending_to_runtime(
    context: dict[str, Any],
    scene: dict[str, Any] | None,
    records: Iterable[dict[str, Any]],
) -> int:
    session = ((context.get("sessao") or {}).get("numero"))
    deltas: list[dict[str, Any]] = []
    for record in records:
        if isinstance(session, int) and record.get("sessao") != session:
            continue
        for delta in record.get("deltas") or []:
            if is_commitment_delta(delta):
                deltas.append(delta)
    if not deltas:
        return 0

    time_context = context.get("tempo") or {}
    bundle = _apply_bundle(
        context.get("compromissos"),
        deltas,
        time_context.get("data"),
        time_context.get("hora_aproximada"),
    )
    if bundle is None:
        context.pop("compromissos", None)
    else:
        context["compromissos"] = bundle

    if isinstance(scene, dict):
        time_scene = scene.get("tempo") or {}
        scene_bundle = _apply_bundle(
            scene.get("compromissos"),
            deltas,
            time_scene.get("data"),
            time_scene.get("hora_aproximada"),
        )
        if scene_bundle is None:
            scene.pop("compromissos", None)
        else:
            scene["compromissos"] = scene_bundle
    return len(deltas)


def validate_state(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise CommitmentError("estado atual deve ser mapa")
    commitments = state.get("compromissos") or {}
    bundle = runtime_bundle(
        commitments,
        ((state.get("tempo") or {}).get("data_exata")),
        ((state.get("tempo") or {}).get("hora_aproximada")),
    )
    return {"ok": True, "quantidade": len(commitments), "runtime": bundle}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    close = sub.add_parser("encerrar-delta")
    close.add_argument("id")
    args = parser.parse_args(argv)
    try:
        if args.command == "encerrar-delta":
            print(json.dumps(close_delta(args.id), ensure_ascii=False, indent=2))
            return 0
        state = yaml.safe_load((args.repo.resolve() / "estado/estado-atual.yaml").read_text(encoding="utf-8"))
        print(yaml.safe_dump(validate_state(state), allow_unicode=True, sort_keys=False), end="")
        return 0
    except (OSError, yaml.YAMLError, CommitmentError) as exc:
        print(f"ERRO: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
