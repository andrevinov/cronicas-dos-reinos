#!/usr/bin/env python3
"""Fachada pública v2 da orquestração de turno e sessão.

O módulo é um control plane fino sobre as autoridades existentes. Ele não cria
writer, journal, estado persistente, scheduler ou chamada adicional: publica
recibos compactos nas respostas de ``cronica`` e reúne os checks históricos de
turno, consolidação, memória e lifecycle sob uma única identidade avaliável.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any, Callable

import yaml

from _module_facade import attach_coverage, combine_checks
import checkpoint as _checkpoint
import ciclo_sessoes as _sessions
import consolidar as _consolidation
import sessoes as _session_memory
import turno as _turn

FACADE_SCHEMA = 2
RECEIPT_SCHEMA = 1
MODULE_ID = "turn_and_session_orchestration"
CAPABILITIES = ("transactional_turn", "session_lifecycle", "idempotent_commit")
LEGACY_ALIASES: tuple[str, ...] = ()
LEGACY_COMPONENTS = (
    "cronica",
    "turno",
    "consolidar",
    "checkpoint",
    "ciclo_sessoes",
    "sessoes",
)

RECEIPT_KEY = "orquestracao"
RECEIPT_RESERVE_BYTES = 896
MAX_RECEIPT_BYTES = 768
MAX_RECOVERY_GATE_BYTES = 2048

SOURCE_OWNERSHIP = {
    "turn_buffer": _turn.PENDING_PATH.as_posix(),
    "consolidation_journal": _consolidation.JOURNAL_PATH.as_posix(),
    "consolidation_stage": _consolidation.STAGE_DIR.as_posix(),
    "session_ledger": "sessoes/<NNN>/consolidacoes.jsonl",
    "session_handoff": "sessoes/<NNN>/handoff.yaml",
    "session_index": _session_memory.INDEX_PATH.as_posix(),
}

TURN_STATE_MACHINE = {
    "preparar": {
        "sucesso": "preparado",
        "bloqueios": ("bloqueado_pendencias", "bloqueado_recuperacao"),
        "proximos": ("narracao", "resolucao_mecanica", "concluir"),
    },
    "concluir": {"sucesso": "concluido", "proximos": ()},
    "confirmar": {"sucesso": "confirmado_para_reparo", "proximos": ("registrar",)},
    "registrar": {"sucesso": "registrado_por_reparo", "proximos": ()},
}

SESSION_STATE_MACHINE = {
    "status": "observado",
    "checkpoint": "checkpoint_concluido",
    "encerrar": "encerrado",
    "iniciar": "iniciado",
    "recuperar": "recuperado",
}

CHECKPOINT_ORDER = ("canonico", "ciclo", "mundo", "memoria")


class TurnAndSessionOrchestrationError(ValueError):
    """Falha do contrato observável do control plane."""


def _size(value: Any) -> int:
    return len(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    )


def _first(*values: Any) -> Any:
    return next((value for value in values if value is not None), None)


def _correlation(result: dict[str, Any]) -> dict[str, Any]:
    ids = result.get("ids") if isinstance(result.get("ids"), dict) else {}
    scene = result.get("cena") if isinstance(result.get("cena"), dict) else {}
    transaction = (
        result.get("transacao") if isinstance(result.get("transacao"), dict) else {}
    )
    values = {
        "cena_id": _first(ids.get("cena"), scene.get("id"), result.get("cena_id")),
        "preparacao_id": _first(
            ids.get("preparacao"), scene.get("preparacao_id"), result.get("preparacao_id")
        ),
        "ticket_id": result.get("ticket_id"),
        "transacao_id": _first(transaction.get("id"), result.get("transacao_id")),
        "sessao": _first(transaction.get("sessao"), result.get("sessao")),
    }
    return {key: value for key, value in values.items() if value is not None}


def _blocked_state(phase: str) -> str | None:
    if "pendenc" in phase:
        return "bloqueado_pendencias"
    if "recuper" in phase:
        return "bloqueado_recuperacao"
    return None


def _turn_receipt(result: dict[str, Any], operation: str) -> dict[str, Any]:
    if operation not in TURN_STATE_MACHINE:
        raise TurnAndSessionOrchestrationError(
            f"operação de turno desconhecida: {operation!r}"
        )
    phase = str(result.get("fase") or "")
    blocked = _blocked_state(phase)
    state = blocked or TURN_STATE_MACHINE[operation]["sucesso"]
    primary = operation in {"preparar", "concluir"}
    receipt: dict[str, Any] = {
        "schema_turn_and_session_orchestration": RECEIPT_SCHEMA,
        "module_id": MODULE_ID,
        "unidade": "turno",
        "operacao": operation,
        "estado": state,
        "correlacao": _correlation(result),
        "fluxo": {
            "primario": primary,
            "posicao": 1 if operation == "preparar" else 2 if operation == "concluir" else None,
            "chamadas_primarias_esperadas": 2,
        },
        "classe_custo": "controle",
        "custo_dominio_separado": True,
    }
    if blocked:
        receipt["efeito_materializado"] = False
        receipt["proximo_estado"] = "recuperar" if blocked == "bloqueado_recuperacao" else "resolver_pendencias"
    elif operation == "preparar":
        receipt["efeito_materializado"] = False
        receipt["proximo_estado"] = "narracao_ou_resolucao_mecanica"
    elif operation in {"concluir", "registrar"}:
        transaction = result.get("transacao") or {}
        retry = bool(transaction.get("ja_registrada"))
        repaired = bool(transaction.get("reparo_parcial"))
        consolidated = bool(transaction.get("consolidada"))
        outcome = (
            "reparo_recuperado_sem_duplicacao"
            if repaired
            else "replay_sem_duplicacao"
            if retry or consolidated
            else "commit_exatamente_uma_vez"
        )
        new_effect = not (retry or repaired or consolidated)
        receipt["commit"] = {
            "resultado": outcome,
            "exactly_once": True,
            "efeito_novo": new_effect,
            "duplicado": False,
            "incompleto": False,
        }
        receipt["efeito_materializado"] = new_effect
    else:
        receipt["efeito_materializado"] = bool(result.get("mutacoes_aplicadas"))
        receipt["proximo_estado"] = "registrar"
    if _size(receipt) > MAX_RECEIPT_BYTES:
        raise TurnAndSessionOrchestrationError(
            f"recibo de turno excede {MAX_RECEIPT_BYTES} bytes"
        )
    return receipt


def publish_turn(
    result: dict[str, Any],
    operation: str,
    *,
    max_output_bytes: int | None = None,
) -> dict[str, Any]:
    """Anexa estado correlacionável sem tocar no ticket ou nos writers."""

    out = copy.deepcopy(result)
    out[RECEIPT_KEY] = _turn_receipt(out, operation)
    attach_coverage(
        out,
        module_id=MODULE_ID,
        phase=operation,
        applicability="aplicavel",
    )
    if max_output_bytes is not None:
        size = len(
            yaml.safe_dump(out, allow_unicode=True, sort_keys=False).encode("utf-8")
        )
        if size > max_output_bytes:
            raise TurnAndSessionOrchestrationError(
                f"output de {operation} excede orçamento: {size} > {max_output_bytes} bytes"
            )
    return out


def publish_partial_failure(
    result: dict[str, Any], operation: str = "concluir"
) -> dict[str, Any]:
    out = copy.deepcopy(result)
    receipt = _turn_receipt(out, operation)
    receipt["estado"] = "falha_parcial_recuperavel"
    receipt["efeito_materializado"] = bool(out.get("cena_confirmada"))
    receipt["commit"] = {
        "resultado": "commit_incompleto",
        "exactly_once": False,
        "efeito_novo": False,
        "duplicado": False,
        "incompleto": True,
    }
    receipt["proximo_estado"] = "reparo"
    out[RECEIPT_KEY] = receipt
    return attach_coverage(
        out,
        module_id=MODULE_ID,
        phase=operation,
        applicability="aplicavel",
    )


def _session_number(result: dict[str, Any]) -> Any:
    lifecycle = result.get("lifecycle") if isinstance(result.get("lifecycle"), dict) else {}
    cycle = lifecycle.get("ciclo_sessao") if isinstance(lifecycle.get("ciclo_sessao"), dict) else {}
    memory = result.get("memoria") if isinstance(result.get("memoria"), dict) else {}
    return _first(
        result.get("sessao"),
        result.get("sessao_iniciada"),
        memory.get("sessao"),
        cycle.get("sessao"),
    )


def publish_session(result: dict[str, Any], operation: str) -> dict[str, Any]:
    """Publica lifecycle no output da chamada existente de ``cronica sessao``."""

    if operation not in SESSION_STATE_MACHINE:
        raise TurnAndSessionOrchestrationError(
            f"operação de sessão desconhecida: {operation!r}"
        )
    out = copy.deepcopy(result)
    recovered = operation == "recuperar" or bool(result.get("recuperada"))
    receipt = {
        "schema_turn_and_session_orchestration": RECEIPT_SCHEMA,
        "module_id": MODULE_ID,
        "unidade": "sessao",
        "operacao": operation,
        "estado": SESSION_STATE_MACHINE[operation],
        "sessao": _session_number(result),
        "recuperada": recovered,
        "ordem_canonica_preservada": operation in {"checkpoint", "encerrar", "recuperar"},
        "checkpoint_por_turno": False,
        "classe_custo": "controle",
        "custo_dominio_separado": True,
    }
    if _size(receipt) > MAX_RECEIPT_BYTES:
        raise TurnAndSessionOrchestrationError(
            f"recibo de sessão excede {MAX_RECEIPT_BYTES} bytes"
        )
    out[RECEIPT_KEY] = receipt
    return attach_coverage(
        out,
        module_id=MODULE_ID,
        phase=f"sessao_{operation}",
        applicability="aplicavel",
    )


def prepare_recovery_gate(repo: Path) -> dict[str, Any] | None:
    """Bloqueia preparo read-only enquanto o journal exige recovery explícito."""

    path = Path(repo) / _consolidation.JOURNAL_PATH
    if not path.is_file():
        return None
    operation = None
    readable = False
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            operation = raw.get("tipo")
            readable = True
    except (OSError, json.JSONDecodeError):
        pass
    result = {
        "schema_cronica_turno": 1,
        "fase": "bloqueada_recuperacao_sessao",
        "reativa": False,
        "ticket_emitido": False,
        "journal": {
            "arquivo": _consolidation.JOURNAL_PATH.as_posix(),
            "tipo": operation,
            "legivel": readable,
        },
        "disponibilidade": {
            "preparacao_turno": False,
            "narracao": False,
            "conclusao": False,
        },
        "proximo_passo": {
            "acao": "recuperar_lifecycle",
            "comando": "poetry run cronica sessao recuperar",
            "regra": "Recupere o journal antes de narrar e repita cronica preparar.",
        },
    }
    out = publish_turn(result, "preparar", max_output_bytes=MAX_RECOVERY_GATE_BYTES)
    return out


def _list_check(check: Callable[[Path], list[str]]) -> Callable[[Path], dict[str, Any]]:
    def run(repo: Path) -> dict[str, Any]:
        errors = list(check(repo))
        return {"ok": not errors, "erros": errors}

    return run


def _receipt_check(_repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    prepared = publish_turn(
        {
            "fase": "preparacao",
            "ticket_id": "ticket-fixture",
            "ids": {"cena": "cena-fixture", "preparacao": "prep-fixture"},
        },
        "preparar",
    )[RECEIPT_KEY]
    concluded = publish_turn(
        {
            "fase": "concluida",
            "ticket_id": "ticket-fixture",
            "cena": {"id": "cena-fixture", "preparacao_id": "prep-fixture"},
            "transacao": {
                "id": "tx-fixture",
                "sessao": 1,
                "ja_registrada": False,
                "reparo_parcial": False,
                "consolidada": False,
            },
        },
        "concluir",
    )[RECEIPT_KEY]
    if prepared["correlacao"].get("ticket_id") != concluded["correlacao"].get("ticket_id"):
        errors.append("preparo e conclusão perderam correlação pelo ticket")
    if concluded.get("commit", {}).get("exactly_once") is not True:
        errors.append("conclusão não publicou garantia exactly-once")
    if prepared["fluxo"].get("chamadas_primarias_esperadas") != 2:
        errors.append("fluxo primário deixou de ser preparar + concluir")
    return {"ok": not errors, "erros": errors}


def check(repo: Path) -> dict[str, Any]:
    return combine_checks(
        repo,
        module_id=MODULE_ID,
        capabilities=CAPABILITIES,
        legacy_components=LEGACY_COMPONENTS,
        checks=(
            ("transactional_turn", _list_check(_turn.check_transactions)),
            ("idempotent_commit", _list_check(_consolidation.check)),
            ("session_lifecycle", _list_check(_checkpoint.check)),
            ("observable_receipts", _receipt_check),
        ),
        contract={
            "source_ownership": SOURCE_OWNERSHIP,
            "turn_state_machine": TURN_STATE_MACHINE,
            "session_state_machine": SESSION_STATE_MACHINE,
            "checkpoint_order": list(CHECKPOINT_ORDER),
            "primary_turn_calls": ["preparar", "concluir"],
            "additional_orchestration_calls": 0,
            "checkpoint_required_each_turn": False,
            "stale_ticket_can_write": False,
            "retry_can_duplicate_effect": False,
            "prepare_can_recover_mutably": False,
            "telemetry_in_hot_path": False,
            "parallel_state": False,
            "parallel_writer": False,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("cmd", choices=["check"])
    args = parser.parse_args(argv)
    result = check(args.repo.resolve())
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
