#!/usr/bin/env python3
"""Projeção quente de retomada para a CLI ``cronica``.

O rollout real mostrou que campos legados de prosa temporal/local podem envelhecer
sem que data/hora/deltas estejam errados. Esta projeção usa apenas estado/runtime
estruturado + overlay pendente + resumos explícitos de transações/handoffs. Nunca
abre transcrição e nunca escreve.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

import recursos
import sessoes
import transacoes

MAX_RECAP_EVENTS = 4


def _load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def _handoff(repo: Path, session: int) -> dict[str, Any]:
    path = repo / sessoes.handoff_rel(session)
    return _load_yaml(path) if path.is_file() else {}


def _events_from_handoff(repo: Path, session: int, *, limit: int = MAX_RECAP_EVENTS) -> list[dict[str, Any]]:
    handoff = _handoff(repo, session)
    events = []
    for raw in list(handoff.get("eventos_recentes") or [])[-limit:]:
        if not isinstance(raw, dict):
            continue
        summary = str(raw.get("resumo") or "").strip()
        if not summary:
            continue
        events.append(
            {
                "transacao": raw.get("transacao"),
                "resumo": summary,
            }
        )
    return events


def previous_recap(repo: Path, session: int | None) -> dict[str, Any] | None:
    if not isinstance(session, int) or session < 1:
        return None
    events = _events_from_handoff(repo, session)
    if not events:
        return None
    return {
        "sessao": session,
        "eventos_recentes": events,
        "fonte": sessoes.handoff_rel(session).as_posix(),
        "transcricao_lida": False,
    }


def current_snapshot(repo: Path) -> dict[str, Any]:
    context_path = repo / "runtime/contexto.yaml"
    scene_path = repo / "runtime/cena.yaml"
    context = _load_yaml(context_path)
    scene = _load_yaml(scene_path)
    records = transacoes.load_pending(repo)
    effective_context, effective_scene, _ = transacoes.overlay_runtime(context, scene, records)
    recursos.apply_pending_effects(effective_context, effective_scene, records)

    session_data = effective_context.get("sessao") or {}
    session = session_data.get("numero")
    current_pending = (
        transacoes.pending_for_session(records, session)
        if isinstance(session, int)
        else []
    )
    latest_summary = None
    summary_source = None
    if current_pending:
        latest_summary = str(current_pending[-1].get("resumo") or "").strip() or None
        summary_source = transacoes.PENDING_PATH.as_posix()
    elif isinstance(session, int):
        events = _events_from_handoff(repo, session, limit=1)
        if events:
            latest_summary = events[-1]["resumo"]
            summary_source = sessoes.handoff_rel(session).as_posix()

    time = effective_context.get("tempo") or {}
    location = effective_context.get("localizacao") or {}
    result: dict[str, Any] = {
        "sessao": session,
        "status": session_data.get("status"),
        "modo": session_data.get("modo_de_cena") or (effective_scene or {}).get("modo"),
        "personagem": effective_context.get("personagem") or {},
        "recursos": effective_context.get("recursos") or {},
        "agora": {
            "data": time.get("data"),
            "hora": time.get("hora_aproximada"),
            "local": {
                "area": location.get("area"),
                "ponto_exato": location.get("ponto_exato"),
            },
        },
        "resumo_imediato": latest_summary,
        "fontes_lidas": ["runtime/contexto.yaml", "runtime/cena.yaml"],
        "transcricao_lida": False,
    }
    if current_pending:
        result["fontes_lidas"].append(transacoes.PENDING_PATH.as_posix())
    elif summary_source:
        result["fontes_lidas"].append(summary_source)
    commitments = effective_context.get("compromissos")
    if commitments:
        result["compromissos"] = commitments
    capabilities = effective_context.get("capacidades_contextuais")
    if capabilities:
        result["capacidades_contextuais"] = capabilities
    return result


def decorate_status(repo: Path, result: dict[str, Any]) -> dict[str, Any]:
    out = dict(result)
    out["retomada"] = current_snapshot(repo)
    out["politica_retomada"] = (
        "Use esta projeção para retomar. Não abra handoff/transcrição nem use busca ampla "
        "se data/hora/local/resumo acima responderem à lacuna."
    )
    return out


def decorate_start(repo: Path, result: dict[str, Any]) -> dict[str, Any]:
    out = dict(result)
    previous = out.get("sessao_anterior")
    out["recap_sessao_anterior"] = previous_recap(repo, previous)
    out["retomada"] = current_snapshot(repo)
    out["politica_retomada"] = (
        "O recap acima vem do handoff compacto da sessão anterior; a abertura atual vem do runtime. "
        "Não abrir transcrição por rotina."
    )
    out["proximo_passo"] = {
        "acao": "recapitular_e_abrir_cena",
        "depois": "cronica preparar --cena-id <id-estavel> (sem outras flags se não houver gatilho reativo real)",
    }
    return out
