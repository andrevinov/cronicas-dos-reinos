#!/usr/bin/env python3
"""Contrato transacional para data+hora como um único fato atômico.

Transações novas devem representar avanço temporal assim::

    {"alvo": "tempo", "op": "instante", "valor": {
        "data": "11 Eleasis, 1372 DR", "hora": "05:10"
    }}

A representação persistida continua sendo um único delta. Para compatibilidade
com o overlay e consolidator legados, a expansão para os espelhos físicos é feita
somente em memória. Assim uma transação nunca pode instalar a nova hora sem a
nova data (ou vice-versa).

Compatibilidade de entrada: a porta de turno pode fornecer a data corrente como
fallback para um legado **somente de hora** quando o valor é HH:MM puro. Isso é
normalizado antes da persistência. Hora com data/prosa embutida nunca é aceita.
"""
from __future__ import annotations

import copy
import re
from typing import Any, Iterable

import mundo

ATOMIC_TARGET = "tempo"
ATOMIC_OP = "instante"
CLOCK_RE = re.compile(r"(?:[01]\d|2[0-3]):[0-5]\d")

DATE_LOCATIONS = {
    ("tempo", "data_atual"),
    ("tempo", "data"),
    ("estado", "tempo.data_exata"),
}
HOUR_LOCATIONS = {
    ("tempo", "hora_aproximada"),
    ("estado", "tempo.hora_aproximada"),
}
INSTANT_LOCATIONS = DATE_LOCATIONS | HOUR_LOCATIONS


class AtomicTimeError(ValueError):
    """Contrato temporal inválido."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AtomicTimeError(f"{label} deve ser texto não vazio")
    return value.strip()


def is_atomic_delta(delta: Any) -> bool:
    return (
        isinstance(delta, dict)
        and delta.get("alvo") == ATOMIC_TARGET
        and delta.get("op") == ATOMIC_OP
    )


def _canonical_parts(data: Any, hora: Any) -> dict[str, str]:
    data_text = _text(data, "instante.data")
    hour_text = _text(hora, "instante.hora")
    if not CLOCK_RE.fullmatch(hour_text):
        raise AtomicTimeError(
            "instante.hora deve ser apenas HH:MM; não embuta data ou prosa no campo de hora"
        )
    try:
        instant = mundo.parse_instant(data_text, hour_text)
        canonical = mundo.instant_parts(instant)
    except mundo.WorldEngineError as exc:
        raise AtomicTimeError(str(exc)) from exc
    if canonical["data"] != data_text:
        raise AtomicTimeError(
            f"instante.data deve usar forma canônica {canonical['data']!r}; recebido {data_text!r}"
        )
    if canonical["hora"] != hour_text:
        raise AtomicTimeError(
            f"instante.hora deve usar forma canônica {canonical['hora']!r}; recebido {hour_text!r}"
        )
    return canonical


def validate_atomic_delta(delta: Any) -> dict[str, Any]:
    if not is_atomic_delta(delta):
        raise AtomicTimeError("delta não é instante temporal atômico")
    if delta.get("visibilidade", "operacional") != "operacional":
        raise AtomicTimeError("instante temporal é estado operacional e não aceita visibilidade narrador")
    if delta.get("caminho") not in (None, ""):
        raise AtomicTimeError("operação tempo/instante não usa caminho")
    value = delta.get("valor")
    if not isinstance(value, dict):
        raise AtomicTimeError("tempo/instante exige valor {data, hora}")
    if set(value) != {"data", "hora"}:
        raise AtomicTimeError("tempo/instante exige exatamente as chaves data e hora")
    canonical = _canonical_parts(value.get("data"), value.get("hora"))
    if value != canonical:
        raise AtomicTimeError("valor de tempo/instante precisa estar em forma canônica")
    return delta


def _legacy_kind(delta: Any) -> str | None:
    if not isinstance(delta, dict):
        return None
    key = (delta.get("alvo"), delta.get("caminho"))
    if key in DATE_LOCATIONS:
        return "data"
    if key in HOUR_LOCATIONS:
        return "hora"
    return None


def _legacy_values(deltas: Iterable[dict[str, Any]]) -> tuple[list[str], list[str], bool]:
    dates: list[str] = []
    hours: list[str] = []
    seen = False
    for delta in deltas:
        kind = _legacy_kind(delta)
        if kind is None:
            continue
        seen = True
        if delta.get("op") != "set":
            raise AtomicTimeError(
                "data/hora canônicas só aceitam set legado ou a operação tempo/instante"
            )
        if delta.get("visibilidade", "operacional") != "operacional":
            raise AtomicTimeError("data/hora canônicas não aceitam visibilidade narrador")
        value = _text(delta.get("valor"), f"tempo legado {kind}")
        (dates if kind == "data" else hours).append(value)
    return dates, hours, seen


def _legacy_parts(
    deltas: Iterable[dict[str, Any]],
    *,
    fallback_date: str | None = None,
    allow_hour_only: bool = False,
) -> dict[str, str] | None:
    dates, hours, seen = _legacy_values(deltas)
    if not seen:
        return None
    if len(set(dates)) > 1 or len(set(hours)) > 1:
        raise AtomicTimeError("deltas temporais legados divergem entre si")
    if not hours:
        raise AtomicTimeError(
            "mudança temporal com data isolada é inválida; use tempo/instante com {data, hora}"
        )
    if not dates:
        hour = hours[0]
        if not CLOCK_RE.fullmatch(hour):
            raise AtomicTimeError(
                "hora legada isolada só pode ser HH:MM puro; data/prosa embutida é proibida"
            )
        if fallback_date is not None:
            return _canonical_parts(fallback_date, hour)
        if allow_hour_only:
            return None
        raise AtomicTimeError(
            "mudança de hora sem data explícita precisa ser normalizada pela porta de turno"
        )
    return _canonical_parts(dates[0], hours[0])


def validate_record_contract(
    deltas: Iterable[dict[str, Any]],
    *,
    allow_legacy_hour_only: bool = False,
) -> None:
    values = list(deltas)
    atomic = [delta for delta in values if is_atomic_delta(delta)]
    legacy = [delta for delta in values if _legacy_kind(delta) is not None]
    if len(atomic) > 1:
        raise AtomicTimeError("uma transação pode conter no máximo um instante temporal")
    if atomic and legacy:
        raise AtomicTimeError("não misture tempo/instante com deltas legados de data/hora")
    if atomic:
        validate_atomic_delta(atomic[0])
    elif legacy:
        _legacy_parts(values, allow_hour_only=allow_legacy_hour_only)


def normalize_new_deltas(
    deltas: Iterable[dict[str, Any]],
    *,
    fallback_date: str | None = None,
) -> list[dict[str, Any]]:
    """Normaliza escrita nova para exatamente um delta atômico quando há tempo."""
    values = [copy.deepcopy(delta) for delta in deltas]
    atomic = [delta for delta in values if is_atomic_delta(delta)]
    legacy_positions = [i for i, delta in enumerate(values) if _legacy_kind(delta) is not None]
    if len(atomic) > 1:
        raise AtomicTimeError("uma transação pode conter no máximo um instante temporal")
    if atomic and legacy_positions:
        raise AtomicTimeError("não misture tempo/instante com deltas legados de data/hora")
    if atomic:
        validate_atomic_delta(atomic[0])
        return values
    if not legacy_positions:
        return values

    canonical = _legacy_parts(values, fallback_date=fallback_date)
    assert canonical is not None
    first = min(legacy_positions)
    positions = set(legacy_positions)
    filtered = [delta for i, delta in enumerate(values) if i not in positions]
    atomic_delta = {"alvo": ATOMIC_TARGET, "op": ATOMIC_OP, "valor": canonical}
    before_count = sum(i < first and i not in positions for i in range(len(values)))
    filtered.insert(before_count, atomic_delta)
    return filtered


def expand_atomic_deltas(deltas: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expande apenas em memória para os espelhos físicos legados."""
    result: list[dict[str, Any]] = []
    for raw in deltas:
        delta = copy.deepcopy(raw)
        if not is_atomic_delta(delta):
            result.append(delta)
            continue
        validate_atomic_delta(delta)
        value = delta["valor"]
        result.extend(
            [
                {"alvo": "tempo", "op": "set", "caminho": "data_atual", "valor": value["data"]},
                {"alvo": "tempo", "op": "set", "caminho": "data", "valor": value["data"]},
                {"alvo": "tempo", "op": "set", "caminho": "hora_aproximada", "valor": value["hora"]},
            ]
        )
    return result


def expand_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in records:
        record = copy.deepcopy(raw)
        record["deltas"] = expand_atomic_deltas(record.get("deltas") or [])
        result.append(record)
    return result


def has_instant_change(deltas: Iterable[dict[str, Any]]) -> bool:
    return any(is_atomic_delta(delta) or _legacy_kind(delta) is not None for delta in deltas)


def atomic_count(records: Iterable[dict[str, Any]]) -> int:
    return sum(
        is_atomic_delta(delta)
        for record in records
        for delta in (record.get("deltas") or [])
    )
