#!/usr/bin/env python3
"""Task 34 — condições persistentes com proveniência idempotente.

O core de schema/projeção/escrita permanece em ``_condicoes_mundo_task34.py``.
Esta borda endurece uma propriedade causal: uma mesma evidência canônica literal
pode materializar uma condição uma única vez. Retry enquanto ela está aberta é
idempotente; depois de expirar/encerrar, a evidência é considerada consumida e
não pode ressuscitar a condição. Recorrência legítima exige novo fato canônico.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import _condicoes_mundo_task34 as _core

for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

_BASE_REGISTER = _core.register


def condition_id(
    *,
    source: str,
    evidence: str,
    **_: Any,
) -> str:
    """Identidade causal estável: fonte + evidência, independente do retry."""
    raw = "\x1f".join([source.strip(), evidence.strip()])
    return "cnd-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _duration_hours(record: dict[str, Any]) -> int | None:
    if record.get("fim_previsto") is None:
        return None
    start = _core._instant(record["inicio"], "inicio")
    end = _core._instant(record["fim_previsto"], "fim_previsto")
    return (end.minute - start.minute) // 60


def _same_definition(
    record: dict[str, Any],
    *,
    kind: str,
    subject: str,
    intensity: str,
    description: str,
    signals: list[str],
    markers: list[str],
    scope: dict[str, Any],
    duration_hours: int | None,
) -> bool:
    return (
        record["tipo"] == kind
        and _core._slug(record["assunto"]) == _core._slug(subject)
        and record["intensidade"] == intensity
        and record["descricao"] == description
        and record["sinais"] == signals
        and record["marcadores"] == markers
        and record["escopo"] == scope
        and _duration_hours(record) == duration_hours
    )


def _history_public(item: dict[str, Any]) -> dict[str, Any]:
    return {
        key: item[key]
        for key in ("id", "tipo", "assunto", "encerrada_em", "motivo")
        if key in item
    }


def register(
    repo: Path,
    *,
    kind: str,
    subject: str,
    intensity: str,
    description: str,
    signals: list[str] | None,
    markers: list[str] | None,
    locals_: list[str] | None,
    duration_hours: int | None,
    source: str,
    evidence: str,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    """Pré-checa proveniência consumida e delega a escrita nova ao core."""
    if kind not in VALID_TYPES:
        raise WorldConditionError("tipo deve ser: " + ", ".join(sorted(VALID_TYPES)))
    subject_n = _core._text(subject, "assunto", maximum=MAX_SUBJECT)
    if intensity not in VALID_INTENSITIES:
        raise WorldConditionError("intensidade deve ser leve, moderada ou forte")
    description_n = _core._text(description, "descricao", maximum=MAX_DESCRIPTION)
    signals_n = [
        _core._text(item, "sinal", maximum=MAX_SIGNAL)
        for item in list(signals or [])
    ]
    if len(signals_n) > MAX_SIGNALS:
        raise WorldConditionError(f"sinais excedem {MAX_SIGNALS}")
    markers_n = sorted(set(_core._text(item, "marcador") for item in list(markers or [])))
    if len(markers_n) > MAX_MARKERS or any(not MARKER_RE.fullmatch(item) for item in markers_n):
        raise WorldConditionError("marcadores inválidos ou acima do teto")
    if duration_hours is not None and (
        isinstance(duration_hours, bool)
        or not isinstance(duration_hours, int)
        or not 1 <= duration_hours <= MAX_DURATION_HOURS
    ):
        raise WorldConditionError(
            f"duracao_horas deve ficar entre 1 e {MAX_DURATION_HOURS}"
        )

    current, time_sources = _core._canonical_now(repo, now)
    scope, scope_sources = _core._resolve_scope(repo, list(locals_ or []))
    source_path, evidence_literal = _core._validate_evidence(repo, source, evidence)
    cid = condition_id(source=source_path, evidence=evidence_literal)
    sources = list(
        dict.fromkeys(
            [STATE.as_posix(), *time_sources, *scope_sources, source_path]
        )
    )
    state = _core.load_state(repo)

    existing = state["condicoes"].get(cid)
    if existing is not None:
        if not _same_definition(
            existing,
            kind=kind,
            subject=subject_n,
            intensity=intensity,
            description=description_n,
            signals=signals_n,
            markers=markers_n,
            scope=scope,
            duration_hours=duration_hours,
        ):
            raise WorldConditionError(
                "a mesma evidência canônica já foi consumida por outra definição de condição"
            )
        if _core._is_expired(existing, current):
            return {
                "ok": True,
                "resultado": "evidencia_ja_consumida",
                "condicao": _core._public(existing),
                "fontes_lidas": sources,
            }
        return {
            "ok": True,
            "resultado": "ja_registrada",
            "condicao": _core._public(existing),
            "compactadas": 0,
            "fontes_lidas": sources,
        }

    previous = next(
        (item for item in reversed(state["historico_recente"]) if item["id"] == cid),
        None,
    )
    if previous is not None:
        return {
            "ok": True,
            "resultado": "evidencia_ja_consumida",
            "historico": _history_public(previous),
            "fontes_lidas": sources,
        }

    return _BASE_REGISTER(
        repo,
        kind=kind,
        subject=subject_n,
        intensity=intensity,
        description=description_n,
        signals=signals_n,
        markers=markers_n,
        locals_=list(locals_ or []),
        duration_hours=duration_hours,
        source=source_path,
        evidence=evidence_literal,
        now=current,
    )


# O core resolve esses nomes em runtime; patch preserva CLI e toda a API antiga.
_core.condition_id = condition_id
_core.register = register
main = _core.main

if __name__ == "__main__":
    raise SystemExit(main())
