#!/usr/bin/env python3
"""Gate read-only de pendências do Mundo Vivo para ``cronica preparar``.

O caminho livre lê somente ``runtime/mundo-pendencias.yaml``. Quando o marcador
aponta bloqueio, a fila autoritativa é confirmada sem escrita antes de recusar a
preparação do turno. Isso evita narrar uma ação de Ren que o writer rejeitaria
mais tarde e remove a leitura manual do marcador do protocolo do agente.

A camada não resolve pendências, não chama o endpoint de cena e não emite ticket.
A resolução continua pertencendo à Task 23 (``resolver_fronteira.py``), enquanto
o writer preserva sua própria barreira como defesa contra corridas posteriores à
preparação.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

import _cronica_turn_core as core
import barreira_mundo
import mundo

MAX_BLOCKED_OUTPUT_BYTES = 2048


def _actual_payload(status: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_barreira_mundo": barreira_mundo.SCHEMA,
        "natureza": barreira_mundo.NATURE,
        "bloqueado": bool(status["bloqueado"]),
        "quantidade": int(status["quantidade"]),
        "disparo_mais_antigo": status["disparo_mais_antigo"],
    }


def inspect_read_only(repo: Path) -> dict[str, Any]:
    """Observa a barreira sem reparar arquivos.

    Marcador livre é confiado no hot path barato. Marcador bloqueado é conferido
    contra ``narrador/mundo/estado.yaml`` para que um marcador stale não crie um
    deadlock em ``cronica preparar``. A correção persistente continua a cargo da
    barreira mutante já existente no writer/checkpoint.
    """
    try:
        status = barreira_mundo.load_status(repo)
    except barreira_mundo.WorldPendingBarrierError as exc:
        raise core.CronicaError(str(exc)) from exc

    if not status.get("configurado") or not status.get("bloqueado"):
        return {**status, "marcador_stale": False, "autoritativo_confirmado": False}

    try:
        state = mundo.load_world_state(repo)
        expected = barreira_mundo.payload_from_state(state)
    except mundo.WorldEngineError as exc:
        raise core.CronicaError(str(exc)) from exc

    stale = _actual_payload(status) != expected
    return {
        "configurado": True,
        **expected,
        "marcador_stale": stale,
        "autoritativo_confirmado": True,
        "fontes_lidas": [
            barreira_mundo.BARRIER_PATH.as_posix(),
            mundo.WORLD_STATE_PATH.as_posix(),
        ],
    }


def prepare_gate(repo: Path) -> dict[str, Any] | None:
    """Retorna ``None`` no caminho livre ou uma resposta bloqueante compacta."""
    status = inspect_read_only(repo)
    if not status.get("bloqueado"):
        return None

    result = {
        "schema_cronica_turno": core.SCHEMA,
        "fase": "bloqueada_pendencias_mundo",
        "reativa": False,
        "ticket_emitido": False,
        "barreira": {
            "bloqueado": True,
            "quantidade": status["quantidade"],
            "disparo_mais_antigo": status["disparo_mais_antigo"],
            "marcador_stale": status["marcador_stale"],
        },
        "disponibilidade": {
            "preparacao_turno": False,
            "narracao": False,
            "conclusao": False,
        },
        "fontes_lidas": list(status.get("fontes_lidas") or []),
        "proximo_passo": {
            "acao": "resolver_pendencias_mundo",
            "comando": "poetry run python ferramentas/resolver_fronteira.py preparar",
            "regra": (
                "Resolva a fila pela Task 23 antes de narrar. Depois de aplicar os no-ops e "
                "materializar os itens restantes, repita o mesmo `cronica preparar`; esta "
                "resposta não contém ticket de turno."
            ),
        },
    }
    size = len(yaml.safe_dump(result, allow_unicode=True, sort_keys=False).encode("utf-8"))
    if size > MAX_BLOCKED_OUTPUT_BYTES:
        raise core.CronicaError(
            f"gate de pendências excede orçamento: {size} > {MAX_BLOCKED_OUTPUT_BYTES} bytes"
        )
    return result
