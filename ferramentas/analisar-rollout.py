#!/usr/bin/env python3
"""Telemetria pós-hoc de rollout com atribuição de sistemas narrativos.

O analisador schema 3 permanece congelado em ``_analisar_rollout_core.py``. Esta
camada preserva a visão ``legacy-v1`` e acrescenta o ledger hierárquico
``modules-v2``. A atribuição continua observacional, pós-hoc e somente leitura:
nada aqui roda durante o jogo ou escreve no repo.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_CORE_PATH = Path(__file__).with_name("_analisar_rollout_core.py")
_spec = importlib.util.spec_from_file_location("_analisar_rollout_core", _CORE_PATH)
if _spec is None or _spec.loader is None:
    raise ImportError(f"não foi possível carregar {_CORE_PATH}")
_core = importlib.util.module_from_spec(_spec)
sys.modules.setdefault("_analisar_rollout_core", _core)
_spec.loader.exec_module(_core)

for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

SCHEMA_VERSION = _core.SCHEMA_VERSION
NARRATIVE_SYSTEMS_SCHEMA = 2
LEGACY_NARRATIVE_SYSTEMS_SCHEMA = 1
MODULAR_LEDGER_SCHEMA = 2
MODULAR_DETECTOR_VERSION = "2.5.0"
OPPORTUNITY_DECISION_SCHEMA = 1
LIVENESS_BOUNDARY_SCHEMA = 1

_CATALOG_V2_PATH = Path(__file__).resolve().parents[1] / "evaluation" / "catalogo-modulos-v2.json"

_BASE_CLASSIFY_TOOL = _core._classify_tool
_BASE_ACCESS_LEVEL = _core._access_level_from_command
_BASE_ANALYZE = _core.analyze
_BASE_HUMAN = _core._human

NARRATIVE_SYSTEM_KEYS = (
    "npc_social_initiative",
    "world_local_incidents",
    "canonical_secret_quests",
    "secret_canon",
    "batch_world_boundary",
    "persistent_world_conditions",
    "underground_tournament",
    "emergent_sidequest_opportunity",
    "emergent_sidequest_authoring",
    "quest_rewards",
    "adversarial_integrity",
    "sidequest_progression",
    "active_sidequest_reassessment",
    "transactional_sidequest_progress",
    "sidequest_success_reactions",
    "concurrent_adversarial_operations",
    "reactive_pressure_routing",
    "liveness_boundary",
    "seven_names_migration_regression",
    "canon_bridge",
)

_SYSTEM_COMMAND_MARKERS: dict[str, tuple[str, ...]] = {
    "canonical_secret_quests": ("sidequests_canonicas.py", "sidequests-canonicas.py"),
    "world_local_incidents": ("incidentes_mundo.py", "incidentes-mundo.py"),
    "secret_canon": ("eventos_canonicos.py", "eventos-canonicos.py"),
    "batch_world_boundary": ("resolver_fronteira.py", "resolver-fronteira.py"),
    "persistent_world_conditions": ("condicoes_mundo.py", "condicoes-mundo.py"),
    "underground_tournament": ("torneio_clandestino.py", "torneio-clandestino.py"),
    "emergent_sidequest_opportunity": ("oportunidade_sidequest.py", "oportunidade-sidequest.py"),
    "emergent_sidequest_authoring": ("sidequests_emergentes.py", "sidequests-emergentes.py"),
    "quest_rewards": ("recompensas_sidequest.py", "recompensas-sidequest.py"),
    "adversarial_integrity": ("integridade_adversarial.py", "integridade-adversarial.py"),
    "sidequest_progression": ("progressao_sidequests.py", "progressao-sidequests.py"),
    "active_sidequest_reassessment": ("sidequests_ativas.py", "sidequests-ativas.py"),
    "transactional_sidequest_progress": (
        "progresso_sidequests_transacional.py",
        "progresso-sidequests-transacional.py",
    ),
    "sidequest_success_reactions": (
        "reacoes_sidequest.py",
        "reacoes-sidequest.py",
    ),
    "concurrent_adversarial_operations": (
        "operacoes_concorrentes.py",
        "operacoes-concorrentes.py",
    ),
    "reactive_pressure_routing": (
        "pressao_narrativa.py",
        "pressao-narrativa.py",
    ),
    "liveness_boundary": ("fronteira_vivacidade.py", "fronteira-vivacidade.py"),
    "seven_names_migration_regression": (
        "migracao_sete_nomes.py",
        "migracao-sete-nomes.py",
    ),
    "canon_bridge": ("canon_bridge_runtime.py", "canon-bridge-runtime.py"),
}

_SYSTEM_OUTPUT_MARKERS: dict[str, tuple[str, ...]] = {
    "npc_social_initiative": ("iniciativa_social",),
    "world_local_incidents": (
        "incidente_mundo",
        "incidentes_mundo_v2",
        "incidentes_para_avaliar",
        "narrador/mundo/incidentes/",
    ),
    "canonical_secret_quests": (
        "sidequest_canonica",
        "sidequest_canonica_task32",
        "sidequests-canonicas/",
    ),
    "secret_canon": (
        "evento_canonico_datado",
        "eventos_canonicos",
        "requer_fato_canonico",
        "narrador/tramas/arcos/parte_1/eventos/",
    ),
    "batch_world_boundary": ("lote_id", "frn1."),
    "persistent_world_conditions": (
        "condicoes_mundo",
        "condicoes_persistentes_ativas",
        "condicoes-persistentes.yaml",
    ),
    "underground_tournament": (
        "torneio_clandestino",
        "circuito_subterraneo_parte1",
        "torneio-clandestino/",
    ),
    "emergent_sidequest_opportunity": (
        "emergent_sidequest_opportunity",
        "sidequest_emergente_task46",
        "material_para_planejamento",
    ),
    "emergent_sidequest_authoring": (
        "emergent_sidequest_authoring",
        "sidequest_materializada",
        "sidequest_emergente_materializada_task46",
    ),
    "quest_rewards": ("quest_rewards", "contrato_recompensa"),
    "adversarial_integrity": ("adversarial_integrity", "contrato_adversarial"),
    "sidequest_progression": ("sidequest_progression", "contrato_progressao"),
    "active_sidequest_reassessment": (
        "active_sidequest_reassessment",
        "sidequests_ativas_task48",
        "sidequests_ativas:",
    ),
    "transactional_sidequest_progress": (
        "transactional_sidequest_progress",
        "progresso_sidequests_registrado",
        "progresso_sidequests:",
    ),
    "sidequest_success_reactions": (
        "sidequest_success_reactions",
        "schema_reacao_sidequest",
        "reaction_id:",
        "reacao_mundo",
        "oportunidade_sucessora",
    ),
    "concurrent_adversarial_operations": (
        "schema_grupo_operacoes",
        "grupo_operacoes_id",
        "comprometer_grupo_operacoes",
        "resolver_operacao_adversarial",
    ),
    "reactive_pressure_routing": (
        "reactive_pressure_routing",
        "schema_pressao_narrativa",
        "contrato_pressao",
        "pressao_narrativa:",
    ),
    "liveness_boundary": (
        "schema_fronteira_vivacidade",
        "fronteira_vivacidade_nv14",
        "calma_justificada",
    ),
    "seven_names_migration_regression": (
        "schema_migracao_sete_nomes",
        "seven-names-session-017-v1",
        "necessita_reavaliacao_reacao",
    ),
    "canon_bridge": ("canon_bridge", "reserva_causal", "aguarda_evidencia"),
}


def _is_dice_command(command: str) -> bool:
    lower = command.casefold()
    if any(marker in lower for marker in DICE_MARKERS):
        return True
    return bool(re.search(r"(?:^|\s)(?:poetry\s+run\s+)?dados(?:-lote)?(?:\s|$)", lower))


def _classify_tool(name: str, raw_input: str) -> str:
    command = _core._extract_command(raw_input)
    if _is_dice_command(command):
        return "dice"
    return _BASE_CLASSIFY_TOOL(name, raw_input)


def _access_level_from_command(command: str) -> str | None:
    result = _BASE_ACCESS_LEVEL(command)
    if result is not None:
        return result
    lower = command.casefold()
    if _core._is_routed_context(command) and re.search(r"\bcontexto\.py\b.*\breputacao\b", lower):
        return "L2"
    return None


def _is_turn_register(command: str) -> bool:
    if _core._is_help_command(command):
        return False
    lower = " ".join(command.casefold().split())
    return (
        "turno.py registrar" in lower
        or "cronica.py concluir" in lower
        or "cronica concluir" in lower
        or "cronica.py registrar" in lower
        or "cronica registrar" in lower
    )


def _orchestration_phase(command: str) -> str | None:
    lower = " ".join(command.casefold().split())
    for phase in ("preparar", "concluir", "registrar", "confirmar"):
        if f"cronica {phase}" in lower or f"cronica.py {phase}" in lower:
            return phase
    return None


def _session_lifecycle_operation(command: str) -> str | None:
    lower = " ".join(command.casefold().split())
    match = re.search(
        r"\bcronica(?:\.py)?\s+sessao\s+(status|iniciar|checkpoint|encerrar|recuperar)\b",
        lower,
    )
    return match.group(1) if match else None


def _duration_seconds(output_text: str) -> float | None:
    match = re.search(r"\bWall time\s+([0-9]+(?:\.[0-9]+)?)\s+seconds\b", output_text, re.I)
    if match:
        return float(match.group(1))
    match = re.search(
        r'["\']?wall_time_seconds["\']?\s*:\s*([0-9]+(?:\.[0-9]+)?)',
        output_text,
        re.I,
    )
    return float(match.group(1)) if match else None


def _normalized_tool_output(payload: dict[str, Any]) -> str:
    """Desembrulha outputs modernos sem alterar o analisador legado congelado."""

    raw = payload.get("output")
    if not isinstance(raw, list):
        return _core._tool_output(payload)
    parts: list[str] = []
    for block in raw:
        if not isinstance(block, dict):
            parts.append(str(block))
            continue
        text = block.get("text")
        if not isinstance(text, str):
            text = block.get("content")
        if not isinstance(text, str):
            continue
        try:
            nested = json.loads(text)
        except json.JSONDecodeError:
            parts.append(text)
            continue
        if not isinstance(nested, dict) or not any(
            key in nested for key in ("output", "exit_code", "returncode", "wall_time_seconds")
        ):
            parts.append(text)
            continue
        for key in ("exit_code", "returncode", "wall_time_seconds"):
            if key in nested:
                parts.append(f"{key}: {nested[key]}")
        if isinstance(nested.get("output"), str):
            parts.append(nested["output"])
    return "\n".join(parts)


def _output_scalar(output_text: str, key: str) -> str | None:
    patterns = (
        rf'(?:^|\r?\n)\s*"?{re.escape(key)}"?\s*:\s*"?([^"\r\n,}}]+)',
        rf'\\"{re.escape(key)}\\"\s*:\s*\\"([^\\"]+)',
    )
    for pattern in patterns:
        match = re.search(pattern, output_text, re.I)
        if match:
            return match.group(1).strip().strip("'\"")
    return None


def _output_bool(output_text: str, key: str) -> bool | None:
    value = _output_scalar(output_text, key)
    if value is None:
        return None
    normalized = value.casefold()
    if normalized in {"true", "sim"}:
        return True
    if normalized in {"false", "nao", "não"}:
        return False
    return None


def _orchestration_failure_kind(output_text: str) -> str | None:
    lower = output_text.casefold()
    if "falha_parcial" in lower or "falha parcial" in lower or "commit_incompleto" in lower:
        return "commit_incompleto"
    if "obsolet" in lower and ("ticket" in lower or "prepara" in lower):
        return "ticket_obsoleto"
    if "ticket" in lower and any(
        marker in lower
        for marker in (
            "incompat",
            "checksum inválido",
            "checksum invalido",
            "corrompido",
            "prefixo/formato inválido",
            "prefixo/formato invalido",
        )
    ):
        return "ticket_incompativel"
    if any(
        marker in lower
        for marker in (
            "duplicado: true",
            '"duplicado": true',
            "marcador transacional duplicado",
            "commit duplicado",
            "transação duplicada",
            "transacao duplicada",
        )
    ):
        return "commit_duplicado"
    return None


def _orchestration_receipt(output_text: str) -> dict[str, Any] | None:
    marker = "schema_turn_and_session_orchestration"
    start = output_text.casefold().rfind(marker)
    if start < 0:
        return None
    receipt_text = output_text[start:]
    return {
        "state": _output_scalar(receipt_text, "estado"),
        "operation": _output_scalar(receipt_text, "operacao"),
        "ticket_id": _output_scalar(receipt_text, "ticket_id"),
        "transaction_id": _output_scalar(receipt_text, "transacao_id"),
        "session": _output_scalar(receipt_text, "sessao"),
        "commit_result": _output_scalar(receipt_text, "resultado"),
        "exactly_once": _output_bool(receipt_text, "exactly_once"),
        "new_effect": _output_bool(receipt_text, "efeito_novo"),
        "duplicate": _output_bool(receipt_text, "duplicado"),
        "incomplete": _output_bool(receipt_text, "incompleto"),
        "canonical_order": _output_bool(receipt_text, "ordem_canonica_preservada"),
    }


def _sidequest_decision_from_command(command: str) -> str | None:
    if _orchestration_phase(command) != "preparar":
        return None
    lower = " ".join(command.casefold().split())
    opportunity = "--oportunidade-sidequest" in lower
    declined = "--sem-oportunidade-sidequest" in lower
    if opportunity and declined:
        return "conflito"
    if opportunity:
        return "oportunidade"
    if declined:
        return "sem_oportunidade"
    return "ausente"


def _narrative_systems_from_command(command: str) -> set[str]:
    lower = command.casefold()
    result: set[str] = set()
    if "contexto.py" in lower and re.search(r"\bnpc\b", lower):
        result.add("npc_social_initiative")
    if "cronica preparar" in lower and "--oportunidade-sidequest" in lower:
        result.add("emergent_sidequest_opportunity")
    if "sidequest_authoring.py" in lower:
        result.add("emergent_sidequest_authoring")
    if "sidequest_lifecycle.py" in lower:
        result.add("active_sidequest_reassessment")
    if "canonical_quest_integration.py" in lower:
        if re.search(r"\b(avaliar|oferecer|efeitos|check)\b", lower):
            result.add("canonical_secret_quests")
        if re.search(r"\b(responder|finalizar|abandonar|reconciliar|check)\b", lower):
            result.add("canon_bridge")
    if "scene_world_projection.py" in lower:
        result.update({"world_local_incidents", "persistent_world_conditions"})
    if "world_boundary_resolution.py" in lower:
        if re.search(r"\b(fronteira|check)\b", lower):
            result.add("liveness_boundary")
        if re.search(r"\b(preparar|aplicar|check)\b", lower):
            result.add("batch_world_boundary")
    if "causal_narrative_routing.py" in lower:
        result.add("reactive_pressure_routing")
        if re.search(r"\bcheck\b", lower):
            result.add("secret_canon")
    if "adversarial_operations.py" in lower:
        if re.search(r"\b(agente|check)\b", lower):
            result.add("adversarial_integrity")
        if re.search(
            r"\b(preparar|materializar|comprometer|registrar-rolagem|resolver|"
            r"entregar-informacao|percepcao-ren|reconciliar|check)\b",
            lower,
        ):
            result.add("concurrent_adversarial_operations")
    for system, markers in _SYSTEM_COMMAND_MARKERS.items():
        if any(marker in lower for marker in markers):
            result.add(system)
    return result


def _narrative_systems_from_output(output_text: str) -> set[str]:
    lower = output_text.casefold()
    return {
        system
        for system, markers in _SYSTEM_OUTPUT_MARKERS.items()
        if any(marker in lower for marker in markers)
    }


def _matching_markers(
    text: str, markers_by_system: dict[str, tuple[str, ...]]
) -> dict[str, list[str]]:
    lower = text.casefold()
    return {
        system: [marker for marker in markers if marker in lower]
        for system, markers in markers_by_system.items()
        if any(marker in lower for marker in markers)
    }


def _liveness_observation(output_text: str) -> dict[str, int] | None:
    """Extrai somente sinais estruturais; não interpreta a prosa da narração."""
    lower = output_text.casefold()
    missing = int(
        "cobertura incompleta da fronteira de vivacidade" in lower
        or "modulos_nao_consultados" in lower
        or "módulos não consultados" in lower
    )
    marker = "schema_fronteira_vivacidade" in lower or "fronteira_vivacidade_nv14" in lower
    if not marker and not missing:
        return None
    calm = len(re.findall(r"estado\s*:\s*calma_justificada", lower))
    calm += len(re.findall(r'"estado"\s*:\s*"calma_justificada"', lower))
    yaml_primaries = re.findall(r"pressao_primaria\s*:\s*([^\s,}\]]+)", lower)
    json_primaries = re.findall(r'"pressao_primaria"\s*:\s*"([^\"]+)"', lower)
    values = [*yaml_primaries, *json_primaries]
    nulls = {"null", "none", "~", "\"\""}
    pressure = sum(value.strip('"\'') not in nulls for value in values)
    evaluations = max(len(yaml_primaries), len(json_primaries))
    return {
        "avaliacoes": evaluations,
        "calma_justificada": calm,
        "pressao": pressure,
        "modulos_nao_consultados": missing,
    }


def _observation_turn(turn_id: str) -> dict[str, Any]:
    return {
        "turn_id": turn_id,
        "user_messages": [],
        "assistant_messages": [],
        "narration_signal_tool": False,
        "calls": [],
        "calls_by_id": {},
    }


def _scan_observations(path: Path, narration_regex: str | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    narration_re = re.compile(narration_regex, re.I | re.S) if narration_regex else DEFAULT_NARRATION_RE
    turns: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    current_turn: str | None = None

    def ensure(turn_id: str) -> dict[str, Any]:
        if turn_id not in turns:
            turns[turn_id] = _observation_turn(turn_id)
            order.append(turn_id)
        return turns[turn_id]

    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise RolloutError(f"JSON inválido na linha {line_no}: {exc}") from exc
            if not isinstance(record, dict):
                continue
            record_type = str(record.get("type") or "")
            payload = record.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            if record_type == "event_msg" and payload.get("type") == "task_started":
                current_turn = str(payload.get("turn_id") or "") or current_turn
                if current_turn:
                    ensure(current_turn)
            elif record_type == "turn_context":
                current_turn = str(payload.get("turn_id") or "") or current_turn
                if current_turn:
                    ensure(current_turn)
            if record_type != "response_item":
                continue
            metadata = payload.get("internal_chat_message_metadata_passthrough") or {}
            turn_id = str(metadata.get("turn_id") or "") if isinstance(metadata, dict) else ""
            turn_id = turn_id or current_turn
            if not turn_id:
                continue
            turn = ensure(turn_id)
            item_type = payload.get("type")
            if item_type == "message":
                text = _core._message_text(payload)
                if payload.get("role") == "user":
                    if text and not text.startswith("# AGENTS.md instructions"):
                        turn["user_messages"].append(text)
                elif payload.get("role") == "assistant" and text:
                    turn["assistant_messages"].append(text)
                continue
            if item_type in {"function_call", "custom_tool_call"}:
                name = str(payload.get("name") or "<sem-nome>")
                raw_input = _core._tool_input(payload)
                command = _core._extract_command(_core._tool_input(payload))
                cid = _core._call_id(payload)
                command_systems = _narrative_systems_from_command(command)
                command_markers = _matching_markers(command, _SYSTEM_COMMAND_MARKERS)
                if "npc_social_initiative" in command_systems:
                    command_markers.setdefault("npc_social_initiative", []).append("contexto.py npc")
                if "emergent_sidequest_opportunity" in command_systems:
                    command_markers.setdefault("emergent_sidequest_opportunity", []).append(
                        "--oportunidade-sidequest"
                    )
                call = {
                    "call_id": cid,
                    "name": name,
                    "raw_input": raw_input,
                    "command": command,
                    "orchestration_phase": _orchestration_phase(command),
                    "session_lifecycle_operation": _session_lifecycle_operation(command),
                    "sidequest_decision": _sidequest_decision_from_command(command),
                    "narrative_systems": set(command_systems),
                    "command_systems": set(command_systems),
                    "output_systems": set(),
                    "command_markers": command_markers,
                    "output_markers": {},
                    "category": _classify_tool(name, raw_input),
                    "output_text": "",
                    "output_success": None,
                    "duration_seconds": None,
                    "orchestration_receipt": None,
                    "orchestration_failure": None,
                    "liveness": None,
                    "output_seen": False,
                }
                index = len(turn["calls"])
                turn["calls"].append(call)
                if cid:
                    turn["calls_by_id"][cid] = index
                if _is_turn_register(command):
                    turn["narration_signal_tool"] = True
                continue
            if item_type not in {"function_call_output", "custom_tool_call_output"}:
                continue
            output_text = _normalized_tool_output(payload)
            cid = _core._call_id(payload)
            matched = None
            if cid and cid in turn["calls_by_id"]:
                candidate = turn["calls"][turn["calls_by_id"][cid]]
                if not candidate["output_seen"]:
                    matched = candidate
            if matched is None:
                matched = next((item for item in turn["calls"] if not item["output_seen"]), None)
            if matched is not None:
                output_systems = _narrative_systems_from_output(output_text)
                orchestration_failure = _orchestration_failure_kind(output_text)
                # Falha de ticket/commit pertence ao control plane. Marcadores
                # incidentais do erro não provam ativação de sidequest ou NPC.
                if orchestration_failure is not None:
                    output_systems = set()
                matched["narrative_systems"].update(output_systems)
                matched["output_systems"] = output_systems
                matched["output_markers"] = _matching_markers(output_text, _SYSTEM_OUTPUT_MARKERS)
                matched["output_text"] = output_text
                success = _core._tool_success(payload, output_text)
                if success is None and "script completed" in output_text.casefold():
                    lower_output = output_text.casefold()
                    explicit_failure = orchestration_failure is not None or any(
                        marker in lower_output
                        for marker in ("falha cronica", "script failed", "traceback (most recent call last)")
                    )
                    success = not explicit_failure
                matched["output_success"] = success
                matched["duration_seconds"] = _duration_seconds(output_text)
                matched["orchestration_receipt"] = _orchestration_receipt(output_text)
                matched["orchestration_failure"] = orchestration_failure
                matched["liveness"] = _liveness_observation(output_text)
                matched["output_seen"] = True

    ordered = [turns[turn_id] for turn_id in order]
    narration = [turn for turn in ordered if _core._is_narration_turn(turn, narration_re)]
    return ordered, narration


def _observation_summary(turns: list[dict[str, Any]]) -> dict[str, Any]:
    phases: Counter[str] = Counter()
    call_classes: Counter[str] = Counter()
    lifecycle_operations: Counter[str] = Counter()
    lifecycle_success: Counter[str] = Counter()
    decisions: Counter[str] = Counter()
    system_calls: Counter[str] = Counter()
    system_turns: Counter[str] = Counter()
    liveness: Counter[str] = Counter()
    phase_durations: dict[str, list[float]] = {}
    retry_metrics: Counter[str] = Counter()
    failure_metrics: Counter[str] = Counter()
    pair_turns = 0
    successful_pair_turns = 0
    correlated_pair_turns = 0
    mismatched_pair_turns = 0
    indeterminate_pair_turns = 0
    blocked_turns = 0
    receipt_calls = 0
    lifecycle_receipt_calls = 0
    for turn in turns:
        per_turn_phases: list[str] = []
        per_turn_systems: set[str] = set()
        primary_calls: dict[str, dict[str, Any]] = {}
        blocked = False
        for call in turn["calls"]:
            phase = call.get("orchestration_phase")
            if isinstance(phase, str):
                phases[phase] += 1
                per_turn_phases.append(phase)
                call_classes[
                    "turno_primario" if phase in {"preparar", "concluir"} else "turno_reparo"
                ] += 1
                if phase in {"preparar", "concluir"} and phase not in primary_calls:
                    primary_calls[phase] = call
                duration = call.get("duration_seconds")
                if isinstance(duration, (int, float)):
                    phase_durations.setdefault(phase, []).append(float(duration))
            lifecycle = call.get("session_lifecycle_operation")
            if isinstance(lifecycle, str):
                lifecycle_operations[lifecycle] += 1
                call_classes["lifecycle_sessao"] += 1
                if call.get("output_success") is True:
                    lifecycle_success[lifecycle] += 1
                duration = call.get("duration_seconds")
                if isinstance(duration, (int, float)):
                    phase_durations.setdefault(f"sessao:{lifecycle}", []).append(float(duration))

            receipt = call.get("orchestration_receipt")
            if isinstance(receipt, dict):
                receipt_calls += 1
                if lifecycle:
                    lifecycle_receipt_calls += 1
                state = str(receipt.get("state") or "")
                if state.startswith("bloqueado_"):
                    blocked = True
                commit_result = str(receipt.get("commit_result") or "")
                if commit_result == "reparo_recuperado_sem_duplicacao":
                    retry_metrics["validos"] += 1
                    retry_metrics["recuperados"] += 1
                elif commit_result == "replay_sem_duplicacao":
                    retry_metrics["desnecessarios"] += 1
                if receipt.get("duplicate") is True:
                    failure_metrics["commits_duplicados"] += 1
                if receipt.get("incomplete") is True:
                    failure_metrics["commits_incompletos"] += 1

            output_lower = str(call.get("output_text") or "").casefold()
            if "bloqueada_pendencias_mundo" in output_lower or "bloqueada_recuperacao_sessao" in output_lower:
                blocked = True
            failure = call.get("orchestration_failure")
            if failure == "ticket_obsoleto":
                failure_metrics["tickets_obsoletos"] += 1
            elif failure == "ticket_incompativel":
                failure_metrics["tickets_incompativeis"] += 1
            elif failure == "commit_duplicado":
                failure_metrics["commits_duplicados"] += 1
            elif failure == "commit_incompleto" and not (
                isinstance(receipt, dict) and receipt.get("incomplete") is True
            ):
                failure_metrics["commits_incompletos"] += 1
            decision = call.get("sidequest_decision")
            if isinstance(decision, str):
                decisions[decision] += 1
            for system in call.get("narrative_systems") or set():
                if system in NARRATIVE_SYSTEM_KEYS:
                    system_calls[system] += 1
                    per_turn_systems.add(system)
            observed_liveness = call.get("liveness")
            if isinstance(observed_liveness, dict):
                for key in ("avaliacoes", "calma_justificada", "pressao", "modulos_nao_consultados"):
                    liveness[key] += int(observed_liveness.get(key, 0))
        exact_pair = Counter(per_turn_phases) == Counter({"preparar": 1, "concluir": 1})
        if exact_pair:
            pair_turns += 1
            prepare_call = primary_calls["preparar"]
            conclude_call = primary_calls["concluir"]
            if all(call.get("output_success") is True for call in (prepare_call, conclude_call)):
                successful_pair_turns += 1
            prepare_receipt = prepare_call.get("orchestration_receipt") or {}
            conclude_receipt = conclude_call.get("orchestration_receipt") or {}
            prepare_ticket = prepare_receipt.get("ticket_id") or _output_scalar(
                str(prepare_call.get("output_text") or ""), "ticket_id"
            )
            conclude_ticket = conclude_receipt.get("ticket_id") or _output_scalar(
                str(conclude_call.get("output_text") or ""), "ticket_id"
            )
            if prepare_ticket is None or conclude_ticket is None:
                indeterminate_pair_turns += 1
            elif prepare_ticket == conclude_ticket:
                correlated_pair_turns += 1
            else:
                mismatched_pair_turns += 1
        if blocked:
            blocked_turns += 1
        system_turns.update(per_turn_systems)
    n = len(turns)
    observed = [system for system in NARRATIVE_SYSTEM_KEYS if system_turns[system]]
    orchestration_calls = sum(phases.values())
    lifecycle_calls = sum(lifecycle_operations.values())
    prepare_calls = sum(decisions.values())
    valid_decisions = decisions["oportunidade"] + decisions["sem_oportunidade"]
    violations = decisions["ausente"] + decisions["conflito"]
    inactive = sum(1 for turn in turns if not any(call.get("narrative_systems") for call in turn["calls"]))
    duration_summary = {
        phase: {
            "chamadas_observadas": len(values),
            "total_segundos": round(sum(values), 3),
            "media_segundos": round(sum(values) / len(values), 3),
            "max_segundos": round(max(values), 3),
        }
        for phase, values in sorted(phase_durations.items())
        if values
    }
    lifecycle_total = sum(lifecycle_operations.values())
    lifecycle_successful = sum(lifecycle_success.values())
    return {
        "orchestration_calls": orchestration_calls,
        "avg_orchestration_calls_per_turn": round(orchestration_calls / n, 3) if n else 0,
        "orchestration_phases": dict(sorted(phases.items())),
        "cronica_pair_turns": pair_turns,
        "fraction_turns_with_cronica_pair": round(pair_turns / n, 6) if n else 0,
        "turn_and_session_orchestration": {
            "schema": 1,
            "calls_total_including_lifecycle": orchestration_calls + lifecycle_calls,
            "calls_by_class": dict(sorted(call_classes.items())),
            "exact_prepare_conclude_pairs": pair_turns,
            "successful_exact_pairs": successful_pair_turns,
            "fraction_exact_pairs": round(pair_turns / n, 6) if n else 0,
            "correlated_pairs": correlated_pair_turns,
            "mismatched_pairs": mismatched_pair_turns,
            "correlation_indeterminate_pairs": indeterminate_pair_turns,
            "fraction_correlated_among_observable": round(
                correlated_pair_turns / (correlated_pair_turns + mismatched_pair_turns), 6
            ) if correlated_pair_turns + mismatched_pair_turns else None,
            "blocked_turns": blocked_turns,
            "receipts_observed": receipt_calls,
            "retry": {
                "validos": int(retry_metrics["validos"]),
                "desnecessarios": int(retry_metrics["desnecessarios"]),
                "recuperados": int(retry_metrics["recuperados"]),
            },
            "tickets": {
                "obsoletos": int(failure_metrics["tickets_obsoletos"]),
                "incompativeis": int(failure_metrics["tickets_incompativeis"]),
            },
            "commits": {
                "duplicados": int(failure_metrics["commits_duplicados"]),
                "incompletos": int(failure_metrics["commits_incompletos"]),
            },
            "duration_by_phase": duration_summary,
            "session_lifecycle": {
                "operations": dict(sorted(lifecycle_operations.items())),
                "successful": dict(sorted(lifecycle_success.items())),
                "fraction_successful": round(lifecycle_successful / lifecycle_total, 6)
                if lifecycle_total
                else None,
                "receipts_observed": lifecycle_receipt_calls,
            },
        },
        "sidequest_opportunity_decisions": {
            key: int(decisions[key])
            for key in ("oportunidade", "sem_oportunidade", "ausente", "conflito")
        },
        "sidequest_decision_prepare_calls": prepare_calls,
        "sidequest_decision_valid": int(valid_decisions),
        "sidequest_decision_violations": int(violations),
        "sidequest_decision_coverage": round(valid_decisions / prepare_calls, 6) if prepare_calls else 1.0,
        "task47_decision_gate_ok": violations == 0,
        "liveness_boundary": {
            "avaliacoes": int(liveness["avaliacoes"]),
            "janelas_com_pressao": int(liveness["pressao"]),
            "calma_justificada": int(liveness["calma_justificada"]),
            "modulos_nao_consultados": int(liveness["modulos_nao_consultados"]),
            "cobertura_ok": liveness["modulos_nao_consultados"] == 0,
        },
        "narrative_system_calls": {system: int(system_calls[system]) for system in NARRATIVE_SYSTEM_KEYS},
        "narrative_system_turns": {system: int(system_turns[system]) for system in NARRATIVE_SYSTEM_KEYS},
        "narrative_systems_observed": observed,
        "turns_without_narrative_system_activity": inactive,
        "fraction_turns_without_narrative_system_activity": round(inactive / n, 6) if n else 0,
    }


_ACTIVATION_PRIORITY = {
    "ausente": 0,
    "consulta": 1,
    "gate_neutro": 2,
    "decisao": 3,
    "efeito": 4,
}
_SOURCE_ORDER = {"comando": 0, "output": 1, "ticket": 2, "resposta": 3, "adjudicacao": 4}

_LEGACY_EFFECT_MARKERS: dict[str, tuple[str, ...]] = {
    "emergent_sidequest_authoring": ("sidequest_materializada", "sidequest_emergente_materializada"),
    "transactional_sidequest_progress": ("progresso_sidequests_registrado",),
    "quest_rewards": ("recompensa_aplicada", "recompensa_materializada"),
    "sidequest_success_reactions": ("reaction_id:", "reacao_materializada"),
    "canon_bridge": ("ponte_materializada",),
    "world_local_incidents": ("incidente_confirmado", "microevento_confirmado"),
    "persistent_world_conditions": ("condicao_registrada", "condicao_encerrada"),
    "batch_world_boundary": ("lote_aplicado", "fronteira_aplicada"),
    "secret_canon": ("materializado_em_jogo",),
    "concurrent_adversarial_operations": ("operacao_resolvida", "resolver_operacao_adversarial"),
}

_LEGACY_NEUTRAL_MARKERS: dict[str, tuple[str, ...]] = {
    "npc_social_initiative": ("resultado: silencio", '"resultado": "silencio"'),
    "world_local_incidents": ("sem_incidente", "sem_microevento"),
    "liveness_boundary": ("calma_justificada",),
    "reactive_pressure_routing": (
        "sem_pressao",
        "sem pressão",
        "resultado_modular: sem_materia",
        '"resultado_modular": "sem_materia"',
    ),
    "batch_world_boundary": (
        "resultado_modular: sem_pendencias",
        "resultado_modular: gate_neutro_aplicado",
        "resultado_modular: retry_sem_duplicacao",
        '"resultado_modular": "sem_pendencias"',
        '"resultado_modular": "gate_neutro_aplicado"',
        '"resultado_modular": "retry_sem_duplicacao"',
    ),
}


def _load_modular_catalog() -> dict[str, Any]:
    try:
        catalog = json.loads(_CATALOG_V2_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RolloutError(f"catálogo modular v2 inválido: {exc}") from exc
    if not isinstance(catalog, dict) or catalog.get("schema_catalogo_modulos") != 2:
        raise RolloutError("catálogo modular v2 precisa usar schema_catalogo_modulos=2")
    modules = catalog.get("modulos") or []
    ids = [str(item.get("id") or "") for item in modules if isinstance(item, dict)]
    if len(ids) != 12 or len(ids) != len(set(ids)):
        raise RolloutError("catálogo modular v2 precisa conter doze módulos únicos")
    return catalog


def _catalog_indexes(catalog: dict[str, Any]) -> tuple[
    dict[str, dict[str, Any]],
    dict[str, tuple[str, str]],
    dict[str, int],
    dict[tuple[str, str], int],
]:
    modules = list(catalog.get("modulos") or [])
    module_by_id = {str(module["id"]): module for module in modules}
    aliases: dict[str, tuple[str, str]] = {}
    module_order = {str(module["id"]): index for index, module in enumerate(modules)}
    capability_order: dict[tuple[str, str], int] = {}
    for module in modules:
        module_id = str(module["id"])
        for index, capability in enumerate(module.get("subcapacidades") or []):
            capability_id = str(capability["id"])
            capability_order[(module_id, capability_id)] = index
            for alias in capability.get("aliases_v1") or []:
                if alias in aliases:
                    raise RolloutError(f"alias v1 duplicado no catálogo modular: {alias}")
                aliases[str(alias)] = (module_id, capability_id)
    return module_by_id, aliases, module_order, capability_order


def _empty_signal() -> dict[str, Any]:
    return {
        "signal_sources": [],
        "eligibility_observed": "indeterminada",
        "activation_observed": "ausente",
        "observed_result": None,
        "materialized_result_observed": None,
        "effect_observed": None,
        "observable_evidence": [],
        "inference_confidence": "media",
    }


def _add_signal(
    signals: dict[tuple[str, str], dict[str, Any]],
    module_id: str,
    capability_id: str,
    *,
    source: str,
    evidence: str,
    eligibility: str = "indeterminada",
    activation: str = "consulta",
    observed_result: str | None = None,
    materialized_result: str | None = None,
    effect_observed: bool | None = None,
    confidence: str = "media",
) -> None:
    signal = signals.setdefault((module_id, capability_id), _empty_signal())
    if source not in signal["signal_sources"]:
        signal["signal_sources"].append(source)
    if evidence and evidence not in signal["observable_evidence"]:
        signal["observable_evidence"].append(evidence)
    if eligibility in {"sim", "nao"}:
        current = signal["eligibility_observed"]
        signal["eligibility_observed"] = eligibility if current == "indeterminada" else current
    if _ACTIVATION_PRIORITY[activation] > _ACTIVATION_PRIORITY[signal["activation_observed"]]:
        signal["activation_observed"] = activation
        if observed_result is not None:
            signal["observed_result"] = observed_result
    elif signal["observed_result"] is None and observed_result is not None:
        signal["observed_result"] = observed_result
    if materialized_result is not None:
        signal["materialized_result_observed"] = materialized_result
    if effect_observed is True or signal["effect_observed"] is None:
        signal["effect_observed"] = effect_observed
    if confidence == "alta" or signal["inference_confidence"] == "baixa":
        signal["inference_confidence"] = confidence


def _legacy_activation(alias: str, output_text: str, source: str) -> tuple[str, str | None, str | None, bool | None]:
    lower = output_text.casefold()
    if any(marker in lower for marker in _LEGACY_NEUTRAL_MARKERS.get(alias, ())):
        return "gate_neutro", "resultado_neutro", None, False
    if any(marker in lower for marker in _LEGACY_EFFECT_MARKERS.get(alias, ())):
        return "efeito", "efeito_observado", "efeito_materializado", True
    if alias in {
        "emergent_sidequest_opportunity",
        "canonical_secret_quests",
        "adversarial_integrity",
        "concurrent_adversarial_operations",
        "reactive_pressure_routing",
        "secret_canon",
    } and source == "output":
        return "decisao", "decisao_observada", None, False
    return "consulta", "marcador_observado", None, None


def _legacy_signals(
    signals: dict[tuple[str, str], dict[str, Any]],
    calls: list[dict[str, Any]],
    aliases: dict[str, tuple[str, str]],
) -> list[dict[str, Any]]:
    non_modules: dict[str, dict[str, Any]] = {}
    for call in calls:
        output_text = str(call.get("output_text") or "")
        command_lower = str(call.get("command") or "").casefold()
        output_lower = output_text.casefold()
        facade_adversarial = "adversarial_operations.py" in command_lower
        actual_npc_initiative = (
            "--interlocutor" in command_lower
            or "iniciativa_elenco" in output_lower
        )
        for source, key, marker_key in (
            ("comando", "command_systems", "command_markers"),
            ("output", "output_systems", "output_markers"),
        ):
            if source == "output" and call.get("orchestration_failure") is not None:
                continue
            for alias in sorted(call.get(key) or set()):
                # O v1 tratava toda consulta dirigida de NPC como iniciativa.
                # No ledger v2, carregar relação/voz é continuidade, enquanto
                # iniciativa exige interlocutor ou decisão explícita no output.
                if alias == "npc_social_initiative" and not actual_npc_initiative:
                    continue
                if (
                    alias == "concurrent_adversarial_operations"
                    and facade_adversarial
                ):
                    continue
                evidence_markers = list((call.get(marker_key) or {}).get(alias) or [alias])
                if alias not in aliases:
                    if alias in {"seven_names_migration_regression", "underground_tournament"}:
                        item = non_modules.setdefault(
                            alias,
                            {"item_id": alias, "signal_sources": [], "observable_evidence": []},
                        )
                        if source not in item["signal_sources"]:
                            item["signal_sources"].append(source)
                        for marker in evidence_markers:
                            evidence = f"{source}:{marker}"
                            if evidence not in item["observable_evidence"]:
                                item["observable_evidence"].append(evidence)
                    continue
                module_id, capability_id = aliases[alias]
                activation, result, materialized, effect = _legacy_activation(
                    alias, output_text, source
                )
                for marker in evidence_markers:
                    _add_signal(
                        signals,
                        module_id,
                        capability_id,
                        source=source,
                        evidence=f"{source}:{marker}",
                        activation=activation,
                        observed_result=result,
                        materialized_result=materialized,
                        effect_observed=effect,
                    )
    return list(non_modules.values())


def _new_module_signals(
    signals: dict[tuple[str, str], dict[str, Any]], turn: dict[str, Any]
) -> None:
    calls = list(turn.get("calls") or [])
    assistant_messages = list(turn.get("assistant_messages") or [])

    # RM-06: proposta, compromisso e efeito são eventos diferentes do mesmo
    # módulo pai. Integridade é o contrato verificável; concorrência só é
    # promovida quando duas ou mais frentes são observáveis no recibo novo.
    for call in calls:
        command = str(call.get("command") or "")
        lower = " ".join(command.casefold().split())
        output_lower = str(call.get("output_text") or "").casefold()
        facade = "adversarial_operations.py" in lower
        legacy_integrity = "integridade_adversarial.py" in lower
        legacy_operations = "operacoes_concorrentes.py" in lower
        structured = any(
            marker in output_lower
            for marker in (
                "schema_adversarial_operations",
                "schema_integridade_adversarial",
                "schema_preparacao_grupo_operacoes",
                "schema_grupo_operacoes",
                "grupo_operacoes_id",
                "resolver_operacao_adversarial",
            )
        )
        if not (facade or legacy_integrity or legacy_operations or structured):
            continue

        retry = "resultado_modular: retry_sem_duplicacao" in output_lower or bool(
            re.search(r'"resultado_modular"\s*:\s*"retry_sem_duplicacao"', output_lower)
        )
        material_effect = (
            "evento_modular: efeito_material" in output_lower
            or bool(
                re.search(r'"evento_modular"\s*:\s*"efeito_material"', output_lower)
            )
            or any(
                marker in output_lower
                for marker in (
                    "resultado_modular: operacao_adversarial_resolvida",
                    "resultado_modular: consequencia_informacional_entregue",
                    '"resultado_modular": "operacao_adversarial_resolvida"',
                    '"resultado_modular": "consequencia_informacional_entregue"',
                )
            )
        )
        commitment = (
            "evento_modular: compromisso" in output_lower
            or bool(re.search(r'"evento_modular"\s*:\s*"compromisso"', output_lower))
            or any(
                marker in output_lower
                for marker in (
                    "resultado: comprometido_em_lote",
                    "resultado_modular: operacao_adversarial_comprometida",
                    "resultado_modular: mecanica_adversarial_congelada",
                    "resultado_modular: contrato_adversarial_materializado",
                )
            )
        )
        if retry:
            activation = "gate_neutro"
            result = "retry_sem_duplicacao"
            materialized = None
            effect = False
        elif material_effect:
            activation = "efeito"
            result = "efeito_adversarial_observado"
            materialized = "efeito_adversarial_materializado"
            effect = True
        elif commitment:
            activation = "decisao"
            result = "operacao_adversarial_comprometida"
            materialized = None
            effect = False
        else:
            activation = "consulta"
            result = "contrato_adversarial_consultado"
            materialized = None
            effect = False if call.get("output_seen") else None

        source = "output" if structured or "evento_modular" in output_lower else "comando"
        _add_signal(
            signals,
            "adversarial_operations",
            "adversarial_contract_integrity",
            source=source,
            evidence=f"{source}:adversarial_{activation}",
            eligibility=(
                "sim"
                if call.get("output_success") is True and (commitment or material_effect)
                else "indeterminada"
            ),
            activation=activation,
            observed_result=result,
            materialized_result=materialized,
            effect_observed=effect,
            confidence="alta" if structured or facade else "media",
        )

        simultaneous = bool(
            re.search(r"operacoes_simultaneas\s*:\s*true", output_lower)
            or re.search(r'"operacoes_simultaneas"\s*:\s*true', output_lower)
            or re.search(r"quantidade_frentes\s*:\s*[2-9]", output_lower)
            or re.search(r'"quantidade_frentes"\s*:\s*[2-9]', output_lower)
        )
        if simultaneous or (legacy_operations and not facade):
            _add_signal(
                signals,
                "adversarial_operations",
                "concurrent_operations",
                source=source,
                evidence=f"{source}:concurrent_fronts",
                eligibility="sim" if simultaneous else "indeterminada",
                activation=activation,
                observed_result=(
                    "frentes_concorrentes_observadas" if simultaneous else result
                ),
                materialized_result=materialized,
                effect_observed=effect,
                confidence="alta" if simultaneous else "media",
            )

    # RM-05: continuidade dirigida é distinta de iniciativa incidental. Os
    # sinais vêm do mesmo comando/output já observado; nunca interpretam prosa
    # como conhecimento, presença ou identidade confirmada.
    for call in calls:
        command = str(call.get("command") or "")
        lower = " ".join(command.casefold().split())
        output_lower = str(call.get("output_text") or "").casefold()
        directed_npc = "contexto.py" in lower and re.search(r"\bnpc\b", lower)
        facade = "npc_continuity_and_social_behavior.py" in lower
        participant = call.get("orchestration_phase") == "preparar" and "--participante" in lower
        interlocutor = call.get("orchestration_phase") == "preparar" and "--interlocutor" in lower
        identity_operation = "identidades.py" in lower
        reputation_operation = "reputacao_publica.py" in lower or (
            "contexto.py" in lower and re.search(r"\breputacao\b", lower)
        )

        if directed_npc or participant or interlocutor or identity_operation or facade:
            _add_signal(
                signals,
                "npc_continuity_and_social_behavior",
                "presence_and_identity",
                source="comando",
                evidence=(
                    "command:npc_continuity_facade"
                    if facade
                    else "command:directed_npc_context"
                    if directed_npc
                    else "command:identity_operation"
                    if identity_operation
                    else "command:scene_cast_or_interlocutor"
                ),
                activation="consulta" if directed_npc or facade else "decisao",
                observed_result="contexto_npc_observado",
                confidence="alta",
            )

        if directed_npc or participant or reputation_operation or facade:
            _add_signal(
                signals,
                "npc_continuity_and_social_behavior",
                "relationship_memory_reputation",
                source="comando",
                evidence=(
                    "command:reputation_operation"
                    if reputation_operation
                    else "command:npc_memory_projection"
                ),
                activation="consulta",
                observed_result="continuidade_social_consultada",
                confidence="alta",
            )

        has_initiative = "iniciativa_elenco" in output_lower
        eligible_presence = any(
            marker in output_lower
            for marker in (
                "presenca: elenco_cena",
                "presenca: canal_contato",
                '"presenca": "elenco_cena"',
                '"presenca": "canal_contato"',
                "contexto_npc: presente",
                "contexto_npc: contactavel",
            )
        )
        presented = bool(
            re.search(r"resultado\s*:\s*apresentada", output_lower)
            or re.search(r'"resultado"\s*:\s*"apresentada"', output_lower)
            or re.search(r"aberturas_apresentadas\s*:\s*[1-9]", output_lower)
        )
        neutral = has_initiative and any(
            marker in output_lower
            for marker in (
                "silencio_justificado",
                "nao_elegivel",
                "selecionada: null",
                '"selecionada": null',
            )
        )
        if interlocutor or has_initiative:
            activation = "efeito" if presented else "gate_neutro" if neutral else "decisao"
            result = (
                "abertura_apresentada"
                if presented
                else "silencio_ou_inelegibilidade_explicita"
                if neutral
                else "iniciativa_avaliada"
            )
            _add_signal(
                signals,
                "npc_continuity_and_social_behavior",
                "social_initiative",
                source="output" if has_initiative else "comando",
                evidence=(
                    "output:initiative_receipt"
                    if has_initiative
                    else "command:initiative_interlocutor"
                ),
                eligibility="sim" if eligible_presence else "indeterminada",
                activation=activation,
                observed_result=result,
                materialized_result="abertura_apresentada" if presented else None,
                effect_observed=presented,
                confidence="alta" if has_initiative else "media",
            )

        if has_initiative or any(
            marker in output_lower
            for marker in (
                "dialogo_relacional",
                "personalidade_decisoria",
                "reconhecimento_identidade",
            )
        ):
            _add_signal(
                signals,
                "npc_continuity_and_social_behavior",
                "presence_and_identity",
                source="output",
                evidence="output:structured_npc_continuity",
                eligibility="sim" if eligible_presence else "indeterminada",
                activation="decisao" if has_initiative else "consulta",
                observed_result="continuidade_estruturada",
                confidence="alta",
            )

        persistence_observed = bool(
            re.search(r"fatos_sociais_persistidos\s*:\s*[1-9]", output_lower)
            or re.search(r'"fatos_sociais_persistidos"\s*:\s*[1-9]', output_lower)
        )
        if any(
            marker in output_lower
            for marker in (
                "informacoes_recebidas",
                "memorias_importantes",
                "reputacao_publica_ren",
                "fatos_sociais_persistidos",
            )
        ):
            _add_signal(
                signals,
                "npc_continuity_and_social_behavior",
                "relationship_memory_reputation",
                source="output",
                evidence="output:relationship_memory_or_reputation",
                activation="efeito" if persistence_observed else "consulta",
                observed_result=(
                    "fato_social_persistido"
                    if persistence_observed
                    else "fato_social_observado"
                ),
                materialized_result=(
                    "memoria_social_persistida" if persistence_observed else None
                ),
                effect_observed=True if persistence_observed else None,
                confidence="alta",
            )

    # RM-07: toda demanda narrativa usa contexto, inclusive quando L0 basta e
    # não há chamada. Leitura, memória e separação de conhecimento continuam
    # sinais distintos e só o recibo pós-writer prova persistência.
    access_calls = []
    normalized_access = Counter(
        " ".join(str(call.get("command") or "").casefold().split())
        for call in calls
        if _core._is_routed_context(str(call.get("command") or ""))
        and not _core._is_help_command(str(call.get("command") or ""))
    )
    for call in calls:
        command = str(call.get("command") or "")
        lower = " ".join(command.casefold().split())
        output_lower = str(call.get("output_text") or "").casefold()
        name = str(call.get("name") or "")
        category = str(call.get("category") or "")
        routed = _core._is_routed_context(command) and not _core._is_help_command(command)
        raw = _core._is_raw_read(name, command, category)
        if routed or raw:
            access_calls.append(call)
            level = _access_level_from_command(command) if routed else "RAW"
            duplicate = routed and normalized_access[lower] > 1
            gap = bool(
                "lacuna_preservada: true" in output_lower
                or '"lacuna_preservada": true' in output_lower
                or "encontrado: false" in output_lower
                or '"encontrado": false' in output_lower
            )
            justified = bool("--motivo" in lower and "--apos" in lower)
            stale = "obsolet" in output_lower
            if stale:
                observed = "contexto_obsoleto"
            elif raw:
                observed = "acesso_cru_sem_justificativa"
            elif duplicate:
                observed = "leitura_redundante"
            elif gap:
                observed = "lacuna_preservada"
            elif level in {"L3", "L4", "L4T"}:
                observed = (
                    "aprofundamento_justificado"
                    if justified
                    else "aprofundamento_sem_justificativa_observavel"
                )
            else:
                observed = "contexto_suficiente"
            evidence = (
                "command:raw_read"
                if raw
                else f"command:routed_context_{str(level).casefold()}"
            )
            _add_signal(
                signals,
                "context_and_memory",
                "routed_context_access",
                source="output" if "schema_context_and_memory" in output_lower else "comando",
                evidence=evidence,
                eligibility="sim",
                activation="consulta",
                observed_result=observed,
                effect_observed=False,
                confidence="alta",
            )

        memory_context = any(
            marker in lower
            for marker in (
                "contexto.py retomada",
                "contexto.py cena",
                "memoria_cena",
                "sessoes.py retomada",
                "cronica sessao status",
                "cronica sessao iniciar",
            )
        ) or "memoria_cena" in output_lower
        if memory_context:
            cold = "retomada" in lower or "cronica sessao" in lower
            stale_memory = "obsolet" in output_lower
            no_transcript = bool(
                "transcricao_lida: false" in output_lower
                or '"transcricao_lida": false' in output_lower
            )
            _add_signal(
                signals,
                "context_and_memory",
                "scene_and_durable_memory",
                source="output" if "memoria_cena" in output_lower else "comando",
                evidence=(
                    "output:cold_resume_without_transcript"
                    if cold and no_transcript
                    else "command:scene_or_memory_context"
                ),
                eligibility="sim",
                activation="consulta",
                observed_result=(
                    "memoria_de_cena_obsoleta"
                    if stale_memory
                    else "retomada_fria_sem_transcricao"
                    if cold and no_transcript
                    else "memoria_consultada"
                ),
                effect_observed=False,
                confidence="alta" if no_transcript or "memoria_cena" in output_lower else "media",
            )

        memory_declared = call.get("orchestration_phase") == "concluir" and bool(
            re.search(r'(?:^|[\s{,"])mem[oó]ria["\s]*:', command, re.I)
            or re.search(r'"memoria"\s*:', command, re.I)
        )
        memory_receipt = "schema_context_and_memory" in output_lower and bool(
            "memoria_contexto" in output_lower
            or "memoria_duravel_persistida" in output_lower
            or "retry_sem_duplicacao" in output_lower
        )
        if memory_declared or memory_receipt:
            retry = memory_receipt and "retry_sem_duplicacao" in output_lower
            persisted = memory_receipt and not retry and call.get("output_success") is True
            _add_signal(
                signals,
                "context_and_memory",
                "scene_and_durable_memory",
                source="output" if memory_receipt else "comando",
                evidence=(
                    "output:durable_memory_receipt"
                    if memory_receipt
                    else "command:durable_memory_declared"
                ),
                eligibility="sim",
                activation="efeito" if persisted else "consulta" if retry else "decisao",
                observed_result=(
                    "memoria_persistida"
                    if persisted
                    else "retry_sem_duplicacao"
                    if retry
                    else "memoria_declarada_aguardando_commit"
                ),
                materialized_result="memoria_persistida" if persisted else None,
                effect_observed=True if persisted else False,
                confidence="alta",
            )

        knowledge_query = any(
            marker in f" {lower} "
            for marker in (
                " conhecimento ",
                " reputacao ",
                " reputação ",
                " continuidade ",
                " identidades.py ",
            )
        )
        separated_receipt = "camadas_destino" in output_lower
        if knowledge_query or separated_receipt:
            _add_signal(
                signals,
                "context_and_memory",
                "knowledge_layer_separation",
                source="output" if separated_receipt else "comando",
                evidence=(
                    "output:knowledge_destinations"
                    if separated_receipt
                    else "command:knowledge_layer_query"
                ),
                eligibility="sim",
                activation="consulta",
                observed_result="camadas_preservadas" if separated_receipt else "camada_consultada",
                effect_observed=False,
                confidence="alta",
            )

    if not access_calls:
        _add_signal(
            signals,
            "context_and_memory",
            "routed_context_access",
            source="resposta",
            evidence="turn:l0_context_sufficient",
            eligibility="sim",
            activation="consulta",
            observed_result="contexto_l0_suficiente",
            effect_observed=False,
            confidence="media",
        )

    # RM-08: a correlação é inferida do par e do recibo emitido pelas chamadas
    # existentes. Falha transacional não é aproximada a nenhum domínio narrativo.
    turn_calls = [call for call in calls if call.get("orchestration_phase")]
    lifecycle_calls = [
        call for call in calls if call.get("session_lifecycle_operation")
    ]
    if turn_calls:
        phase_counts = Counter(call["orchestration_phase"] for call in turn_calls)
        failures = [
            str(call.get("orchestration_failure"))
            for call in turn_calls
            if call.get("orchestration_failure")
        ]
        blocked = any(
            str((call.get("orchestration_receipt") or {}).get("state") or "").startswith(
                "bloqueado_"
            )
            or "bloqueada_pendencias_mundo" in str(call.get("output_text") or "").casefold()
            or "bloqueada_recuperacao_sessao" in str(call.get("output_text") or "").casefold()
            for call in turn_calls
        )
        exact_pair = phase_counts == Counter({"preparar": 1, "concluir": 1})
        successful_pair = exact_pair and all(
            call.get("output_success") is True for call in turn_calls
        )
        repair_only = set(phase_counts) <= {"registrar", "confirmar"} and all(
            call.get("output_success") is True for call in turn_calls
        )
        mismatched = False
        if exact_pair:
            by_phase = {call["orchestration_phase"]: call for call in turn_calls}
            ticket_ids = []
            for phase in ("preparar", "concluir"):
                call = by_phase[phase]
                receipt = call.get("orchestration_receipt") or {}
                value = receipt.get("ticket_id") or _output_scalar(
                    str(call.get("output_text") or ""), "ticket_id"
                )
                ticket_ids.append(value)
            mismatched = all(ticket_ids) and ticket_ids[0] != ticket_ids[1]

        if failures:
            result = failures[0]
            activation = "decisao"
            effect = False
        elif blocked:
            recovery = any(
                "recuperacao" in str((call.get("orchestration_receipt") or {}).get("state") or "")
                for call in turn_calls
            )
            result = "bloqueado_por_recovery" if recovery else "bloqueado_por_pendencia"
            activation = "gate_neutro"
            effect = False
        elif mismatched:
            result = "correlacao_de_ticket_divergente"
            activation = "decisao"
            effect = False
        elif successful_pair:
            result = "ciclo_concluido"
            activation = "efeito"
            effect = True
        elif repair_only:
            result = "reparo_explicito_concluido"
            activation = "efeito"
            effect = True
        else:
            result = "ciclo_incompleto"
            activation = "decisao"
            effect = False

        for call in turn_calls:
            _add_signal(
                signals,
                "turn_and_session_orchestration",
                "transactional_turn",
                source="comando",
                evidence=f"command:cronica_{call['orchestration_phase']}",
                eligibility="sim",
                activation=activation,
                observed_result=result,
                materialized_result="turno_commitado" if effect else None,
                effect_observed=effect,
                confidence="alta",
            )
        if any("--ticket" in str(call.get("command") or "").casefold() for call in turn_calls):
            _add_signal(
                signals,
                "turn_and_session_orchestration",
                "transactional_turn",
                source="ticket",
                evidence="ticket:correlation_present",
                eligibility="sim",
                activation=activation,
                observed_result=result,
                materialized_result="turno_commitado" if effect else None,
                effect_observed=effect,
                confidence="alta",
            )
        receipts = [
            call.get("orchestration_receipt")
            for call in turn_calls
            if call.get("orchestration_receipt")
        ]
        if receipts:
            _add_signal(
                signals,
                "turn_and_session_orchestration",
                "transactional_turn",
                source="output",
                evidence="output:versioned_orchestration_receipt",
                eligibility="sim",
                activation=activation,
                observed_result=result,
                materialized_result="turno_commitado" if effect else None,
                effect_observed=effect,
                confidence="alta",
            )

        commit_receipts = [
            receipt
            for receipt in receipts
            if receipt.get("commit_result") or receipt.get("incomplete") is True
        ]
        if commit_receipts:
            recovered = any(
                receipt.get("commit_result") == "reparo_recuperado_sem_duplicacao"
                for receipt in commit_receipts
            )
            replay = any(
                receipt.get("commit_result") == "replay_sem_duplicacao"
                for receipt in commit_receipts
            )
            incomplete = any(receipt.get("incomplete") is True for receipt in commit_receipts)
            idempotent = all(
                receipt.get("exactly_once") is True and receipt.get("duplicate") is not True
                for receipt in commit_receipts
            )
            outcome = (
                "commit_incompleto"
                if incomplete
                else "retry_recuperado"
                if recovered
                else "retry_desnecessario_sem_duplicacao"
                if replay
                else "commit_exatamente_uma_vez"
            )
            _add_signal(
                signals,
                "turn_and_session_orchestration",
                "idempotent_commit",
                source="output",
                evidence="output:exactly_once_receipt",
                eligibility="sim",
                activation="decisao" if incomplete else "gate_neutro" if replay else "efeito",
                observed_result=outcome,
                materialized_result="idempotencia_preservada" if idempotent else None,
                effect_observed=idempotent and not replay,
                confidence="alta",
            )

    for call in lifecycle_calls:
        operation = str(call["session_lifecycle_operation"])
        effect = operation != "status" and call.get("output_success") is True
        receipt = call.get("orchestration_receipt")
        for source, evidence in (
            ("comando", f"command:session_{operation}"),
            ("output", "output:versioned_session_receipt"),
        ):
            if source == "output" and not receipt:
                continue
            _add_signal(
                signals,
                "turn_and_session_orchestration",
                "session_lifecycle",
                source=source,
                evidence=evidence,
                eligibility="sim",
                activation="efeito" if effect else "consulta" if operation == "status" else "decisao",
                observed_result=f"session_{operation}",
                materialized_result=f"session_{operation}" if effect else None,
                effect_observed=effect,
                confidence="alta",
            )

    if not turn_calls and not lifecycle_calls:
        _add_signal(
            signals,
            "turn_and_session_orchestration",
            "transactional_turn",
            source="resposta" if assistant_messages else "comando",
            evidence="turn:narrativo_sem_orquestracao",
            eligibility="sim",
            activation="ausente",
            observed_result="orquestracao_ausente",
            effect_observed=False,
            confidence="alta",
        )

    # RM-09: a existência da entrega é estrutural; qualidade literária permanece N/D.
    if assistant_messages:
        response_text = "\n".join(assistant_messages)
        _add_signal(
            signals,
            "narrative_delivery",
            "visible_closure",
            source="resposta",
            evidence="response:present",
            eligibility="sim",
            activation="efeito",
            observed_result="resposta_entregue",
            materialized_result="resposta_entregue",
            effect_observed=True,
            confidence="alta",
        )
        if "rodape_canonico" in response_text.casefold() or "RODAPE_CANONICO" in response_text:
            _add_signal(
                signals,
                "narrative_delivery",
                "visible_closure",
                source="resposta",
                evidence="response:canonical_footer",
                eligibility="sim",
                activation="efeito",
                observed_result="resposta_com_rodape",
                materialized_result="resposta_entregue",
                effect_observed=True,
                confidence="alta",
            )
        if "mecânica —" in response_text.casefold() or "mecanica —" in response_text.casefold():
            _add_signal(
                signals,
                "narrative_delivery",
                "diegetic_mechanics",
                source="resposta",
                evidence="response:diegetic_mechanics",
                eligibility="sim",
                activation="efeito",
                observed_result="mecanica_exposta",
                materialized_result="mecanica_exposta",
                effect_observed=True,
                confidence="alta",
            )
    else:
        _add_signal(
            signals,
            "narrative_delivery",
            "visible_closure",
            source="comando",
            evidence="turn:narrativo_sem_resposta",
            eligibility="sim",
            activation="ausente",
            observed_result="resposta_ausente",
            effect_observed=False,
            confidence="alta",
        )

    # RM-10: regra, rolagem e estado são sinais distintos.
    for call in calls:
        command = str(call.get("command") or "")
        lower = command.casefold()
        if re.search(r"\bcontexto\.py\b.*\bregra\b", lower) or "catalogo_regras.py" in lower:
            _add_signal(
                signals,
                "rules_and_character_state",
                "rules_resolution",
                source="comando",
                evidence="command:rule_query",
                activation="consulta",
                observed_result="regra_consultada",
                confidence="alta",
            )
        if _is_dice_command(command):
            succeeded = call.get("output_success") is True
            _add_signal(
                signals,
                "rules_and_character_state",
                "roll_execution",
                source="comando",
                evidence="command:dice",
                eligibility="sim" if "--cd" in lower else "indeterminada",
                activation="efeito" if succeeded else "decisao",
                observed_result="rolagem_executada" if succeeded else "rolagem_solicitada",
                materialized_result="rolagem_executada" if succeeded else None,
                effect_observed=succeeded,
                confidence="alta",
            )
            if call.get("output_seen"):
                _add_signal(
                    signals,
                    "rules_and_character_state",
                    "roll_execution",
                    source="output",
                    evidence="output:dice_result",
                    eligibility="sim" if "--cd" in lower else "indeterminada",
                    activation="efeito" if succeeded else "decisao",
                    observed_result="rolagem_executada" if succeeded else "rolagem_solicitada",
                    materialized_result="rolagem_executada" if succeeded else None,
                    effect_observed=succeeded,
                    confidence="alta",
                )
        output_lower = str(call.get("output_text") or "").casefold()
        state_signal = any(
            marker in lower or marker in output_lower
            for marker in (
                "--gasto-focus",
                "--mecanica-json",
                '"alvo":"estado"',
                '"alvo": "estado"',
                '"alvo":"tempo"',
                '"alvo": "tempo"',
                "recursos.focus",
            )
        )
        if state_signal:
            committed = call.get("orchestration_phase") in {"concluir", "registrar"} and call.get("output_success") is True
            _add_signal(
                signals,
                "rules_and_character_state",
                "character_time_state",
                source="output" if output_lower else "ticket",
                evidence="output:character_or_time_state" if output_lower else "ticket:character_or_time_state",
                eligibility="sim",
                activation="efeito" if committed else "decisao",
                observed_result="estado_commitado" if committed else "estado_pre_comprometido",
                materialized_result="estado_commitado" if committed else None,
                effect_observed=committed,
                confidence="alta",
            )

    # Gate negativo é atividade real, mas jamais efeito material.
    for call in calls:
        decision = call.get("sidequest_decision")
        if decision not in {"oportunidade", "sem_oportunidade", "ausente", "conflito"}:
            continue
        eligibility = (
            "sim" if decision == "oportunidade" else "nao" if decision == "sem_oportunidade" else "indeterminada"
        )
        activation = (
            "decisao"
            if decision == "oportunidade"
            else "gate_neutro"
            if decision == "sem_oportunidade"
            else "ausente"
        )
        _add_signal(
            signals,
            "sidequest_authoring",
            "opportunity_gate",
            source="comando",
            evidence=f"command:sidequest_gate_{decision}",
            eligibility=eligibility,
            activation=activation,
            observed_result=decision,
            effect_observed=False,
            confidence="alta",
        )


def _allocate_integer(value: int, owners: list[str]) -> dict[str, int]:
    if not owners:
        return {}
    quotient, remainder = divmod(max(0, int(value)), len(owners))
    return {
        owner: quotient + (1 if index < remainder else 0)
        for index, owner in enumerate(sorted(owners))
    }


def _turn_cost(item: dict[str, Any]) -> dict[str, int]:
    input_tokens = int(item.get("input_tokens") or 0)
    output_tokens = int(item.get("output_tokens") or 0)
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": int(item.get("cached_input_tokens") or 0),
        "uncached_input_tokens_approx": int(item.get("approx_uncached_input_tokens") or 0),
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def _build_modular_ledger(
    report: dict[str, Any], narration: list[dict[str, Any]], catalog: dict[str, Any]
) -> dict[str, Any]:
    module_by_id, aliases, module_order, capability_order = _catalog_indexes(catalog)
    events: list[dict[str, Any]] = []
    non_module_observations: list[dict[str, Any]] = []
    module_totals: dict[str, dict[str, int]] = {}
    total_narrative_cost = {key: 0 for key in _turn_cost({})}

    for item, turn in zip(report.get("per_narration_turn") or [], narration):
        signals: dict[tuple[str, str], dict[str, Any]] = {}
        non_modules = _legacy_signals(signals, list(turn.get("calls") or []), aliases)
        _new_module_signals(signals, turn)
        ordinal = int(item.get("ordinal") or len(events) + 1)
        turn_id = str(turn.get("turn_id") or f"ordinal-{ordinal}")
        for observation in non_modules:
            non_module_observations.append(
                {
                    "session_id": (report.get("source") or {}).get("session_id"),
                    "turn_id": turn_id,
                    "turn_ordinal": ordinal,
                    "classification": (
                        "regressao_historica"
                        if observation["item_id"] == "seven_names_migration_regression"
                        else "extensao_campanha"
                    ),
                    **observation,
                    "receives_modular_score": False,
                    "receives_parent_cost": False,
                }
            )

        ordered_keys = sorted(
            signals,
            key=lambda key: (
                module_order.get(key[0], 10_000),
                capability_order.get(key, 10_000),
                key,
            ),
        )
        parent_ids = sorted({module_id for module_id, _ in ordered_keys})
        turn_cost = _turn_cost(item)
        for key, value in turn_cost.items():
            total_narrative_cost[key] += value
        allocations: dict[str, dict[str, int]] = {module_id: {} for module_id in parent_ids}
        for cost_key, value in turn_cost.items():
            allocated = _allocate_integer(value, parent_ids)
            for module_id in parent_ids:
                allocations[module_id][cost_key] = allocated.get(module_id, 0)

        primary_capability: dict[str, str] = {}
        for module_id, capability_id in ordered_keys:
            primary_capability.setdefault(module_id, capability_id)

        for module_id, capability_id in ordered_keys:
            module = module_by_id[module_id]
            signal = signals[(module_id, capability_id)]
            signal["signal_sources"].sort(key=lambda value: _SOURCE_ORDER.get(value, 99))
            primary = primary_capability[module_id] == capability_id
            additive = allocations[module_id] if primary else {key: 0 for key in turn_cost}
            totals = module_totals.setdefault(module_id, {key: 0 for key in turn_cost})
            if primary:
                for key, value in additive.items():
                    totals[key] += value
            event_id = f"ml2:{ordinal}:{module_id}:{capability_id}"
            events.append(
                {
                    "event_id": event_id,
                    "session_id": (report.get("source") or {}).get("session_id"),
                    "turn_id": turn_id,
                    "turn_ordinal": ordinal,
                    "analysis_unit": module.get("unidade_analise"),
                    "module_id": module_id,
                    "capability_id": capability_id,
                    **signal,
                    "adjudication": None,
                    "cost": {
                        "attribution_class": (
                            "controle"
                            if module_id == "turn_and_session_orchestration"
                            else "dominio"
                        ),
                        "exposed_non_additive": dict(turn_cost),
                        "parent_attributed_additive": additive,
                        "parent_allocation_role": "primario" if primary else "exposicao_apenas",
                        "capability_cost_mode": "exposicao_apenas",
                        "marginal_cost": None,
                        "marginal_cost_status": "indeterminado",
                    },
                    "detector_version": MODULAR_DETECTOR_VERSION,
                    "module_implementation_version": module.get("versao_implementacao"),
                    "module_evaluation_version": module.get("versao_avaliacao"),
                }
            )

    attributed = {
        key: sum(values[key] for values in module_totals.values())
        for key in total_narrative_cost
    }
    closure = {
        key: {
            "narrative_total": total_narrative_cost[key],
            "parent_attributed_total": attributed[key],
            "difference": total_narrative_cost[key] - attributed[key],
        }
        for key in total_narrative_cost
    }
    class_totals: dict[str, dict[str, int]] = {
        "controle": {key: 0 for key in total_narrative_cost},
        "dominio": {key: 0 for key in total_narrative_cost},
    }
    for module_id, values in module_totals.items():
        cost_class = (
            "controle" if module_id == "turn_and_session_orchestration" else "dominio"
        )
        for key, value in values.items():
            class_totals[cost_class][key] += value

    return {
        "schema_modular_ledger": MODULAR_LEDGER_SCHEMA,
        "evaluation_series": "modules-v2",
        "detector_version": MODULAR_DETECTOR_VERSION,
        "catalog_schema": catalog.get("schema_catalogo_modulos"),
        "catalog_version": catalog.get("versao_catalogo"),
        "measurement_mode": "post_hoc_read_only",
        "observed_is_not_eligibility": True,
        "capability_cost_mode": "exposicao_apenas",
        "parent_cost_method": "divisao_inteira_igual_entre_modulos_pais_observados_no_turno_com_classe_controle_separada",
        "events": events,
        "non_module_observations": non_module_observations,
        "module_parent_costs": [
            {
                "module_id": module_id,
                "cost_class": (
                    "controle"
                    if module_id == "turn_and_session_orchestration"
                    else "dominio"
                ),
                **module_totals[module_id],
            }
            for module_id in sorted(module_totals, key=lambda value: module_order.get(value, 10_000))
        ],
        "cost_class_totals": [
            {"cost_class": cost_class, **class_totals[cost_class]}
            for cost_class in ("controle", "dominio")
        ],
        "cost_closure": closure,
        "corrections": [],
    }


def apply_modular_adjudications(
    ledger: dict[str, Any], adjudications: dict[str, Any] | list[dict[str, Any]]
) -> dict[str, Any]:
    """Aplica correções sem apagar nenhuma observação do detector."""

    result = copy.deepcopy(ledger)
    corrections = adjudications.get("corrections") if isinstance(adjudications, dict) else adjudications
    if not isinstance(corrections, list):
        raise RolloutError("adjudicações modulares precisam conter uma lista corrections")
    by_id = {event.get("event_id"): event for event in result.get("events") or []}
    for index, correction in enumerate(corrections, 1):
        if not isinstance(correction, dict):
            raise RolloutError(f"adjudicação modular {index} não é objeto")
        event_id = str(correction.get("event_id") or "")
        event = by_id.get(event_id)
        if event is None:
            raise RolloutError(f"adjudicação modular aponta para evento inexistente: {event_id}")
        reason = str(correction.get("reason") or "").strip()
        if not reason:
            raise RolloutError(f"adjudicação modular {event_id} exige reason")
        eligibility = correction.get("eligibility")
        activation = correction.get("activation")
        effect = correction.get("effect_observed")
        evidence = correction.get("evidence") or []
        if eligibility not in {None, "sim", "nao", "indeterminada"}:
            raise RolloutError(f"adjudicação modular {event_id}: eligibility inválida")
        if activation not in {None, *set(_ACTIVATION_PRIORITY)}:
            raise RolloutError(f"adjudicação modular {event_id}: activation inválida")
        if effect is not None and not isinstance(effect, bool):
            raise RolloutError(f"adjudicação modular {event_id}: effect_observed precisa ser booleano")
        if not isinstance(evidence, list):
            raise RolloutError(f"adjudicação modular {event_id}: evidence precisa ser lista")
        adjudication = {
            "signal_source": "adjudicacao",
            "eligibility": eligibility,
            "activation": activation,
            "materialized_result": correction.get("materialized_result"),
            "effect_observed": effect,
            "reason": reason,
            "evidence": list(evidence),
        }
        event["adjudication"] = adjudication
        result["corrections"].append(
            {
                "event_id": event_id,
                "observed_preserved": {
                    "eligibility": event.get("eligibility_observed"),
                    "activation": event.get("activation_observed"),
                    "materialized_result": event.get("materialized_result_observed"),
                    "effect_observed": event.get("effect_observed"),
                },
                "adjudicated": adjudication,
            }
        )
    return result


def telemetry_view(report: dict[str, Any], evaluation_series: str) -> dict[str, Any]:
    """Retorna uma visão compatível sem reinterpretar o rollout bruto."""

    result = copy.deepcopy(report)
    if evaluation_series == "legacy-v1":
        result.pop("modular_ledger_v2", None)
        result.pop("modular_ledger_schema", None)
        result["narrative_systems_schema"] = LEGACY_NARRATIVE_SYSTEMS_SCHEMA
        return result
    if evaluation_series == "modules-v2":
        return result
    raise RolloutError(f"visão de telemetria desconhecida: {evaluation_series}")


def analyze(
    path: Path,
    narration_regex: str | None = None,
    modular_adjudications: dict[str, Any] | list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    report = _BASE_ANALYZE(path, narration_regex)
    ordered, narration = _scan_observations(path, narration_regex)
    catalog = _load_modular_catalog()
    all_summary = _observation_summary(ordered)
    narration_summary = _observation_summary(narration)
    report["narrative_systems_schema"] = NARRATIVE_SYSTEMS_SCHEMA
    report["modular_ledger_schema"] = MODULAR_LEDGER_SCHEMA
    report["opportunity_decision_schema"] = OPPORTUNITY_DECISION_SCHEMA
    report["liveness_boundary_schema"] = LIVENESS_BOUNDARY_SCHEMA
    report["all_turns"].update(all_summary)
    report["narration_turns"].update(narration_summary)
    report["task47_opportunity_decision_gate"] = {
        "schema": OPPORTUNITY_DECISION_SCHEMA,
        "ok": all_summary["task47_decision_gate_ok"],
        "prepare_calls": all_summary["sidequest_decision_prepare_calls"],
        "valid_decisions": all_summary["sidequest_decision_valid"],
        "violations": all_summary["sidequest_decision_violations"],
        "coverage": all_summary["sidequest_decision_coverage"],
        "decisions": all_summary["sidequest_opportunity_decisions"],
        "regra": (
            "todo cronica preparar deve declarar exatamente se existe nova oportunidade; "
            "sidequests aceitas são reavaliadas independentemente pela Task48"
        ),
    }
    report["nv14_liveness_boundary"] = {
        "schema": LIVENESS_BOUNDARY_SCHEMA,
        **all_summary["liveness_boundary"],
        "regra": (
            "calma só é justificada quando a saída NV-14 existe com cobertura; "
            "ausência de consulta é medida separadamente e nunca conta como dia calmo"
        ),
    }
    for item, turn in zip(report.get("per_narration_turn") or [], narration):
        item.update(_observation_summary([turn]))
    ledger = _build_modular_ledger(report, narration, catalog)
    if modular_adjudications is not None:
        ledger = apply_modular_adjudications(ledger, modular_adjudications)
    report["modular_ledger_v2"] = ledger
    inferred = report.get("measurement", {}).get("observational_inference")
    if isinstance(inferred, list):
        for label in (
            "preferred cronica orchestration phases inferred from command lines",
            "narrative-system attribution inferred from command and tool-output markers",
            "Task47 sidequest-opportunity decision inferred from cronica preparar flags",
            "NV-14 justified calm and missing-module coverage inferred from structured liveness output",
            "modules-v2 capability ledger inferred from command, output, ticket and response signals",
            "modules-v2 parent cost allocated once per module; capability cost is exposure only",
            "RM-08 orchestration receipt, retry, correlation and phase duration inferred from existing call outputs",
            "RM-08 control cost separated from domain cost without claiming marginal causality",
        ):
            if label not in inferred:
                inferred.append(label)
    detection = report.get("narration_detection")
    if isinstance(detection, dict):
        detection["also_detected_by"] = "turno.py registrar or cronica concluir/registrar command (excluding --help)"
    return report


def _human(report: dict[str, Any]) -> str:
    base = _BASE_HUMAN(report).rstrip("\n")
    narr = report.get("narration_turns") or {}
    all_turns = report.get("all_turns") or {}
    orchestration = narr.get("turn_and_session_orchestration") or {}
    systems = narr.get("narrative_system_turns") or {}
    live = all_turns.get("liveness_boundary") or {}
    active = ", ".join(
        f"{name}={systems.get(name, 0)}" for name in NARRATIVE_SYSTEM_KEYS if systems.get(name, 0)
    ) or "nenhum"
    ledger = report.get("modular_ledger_v2") or {}
    closure = (ledger.get("cost_closure") or {}).get("total_tokens") or {}
    extra = [
        "",
        "SISTEMAS NARRATIVOS (inferência observacional)",
        (
            "Orquestração: "
            f"{narr.get('avg_orchestration_calls_per_turn', 0)} chamada(s)/turno | "
            "dupla cronica preparar+concluir em "
            f"{narr.get('fraction_turns_with_cronica_pair', 0):.1%} dos turnos | "
            f"correlacionados={orchestration.get('correlated_pairs', 0)} | "
            f"bloqueados={orchestration.get('blocked_turns', 0)}"
        ),
        (
            "Task47: decisão de oportunidade em "
            f"{all_turns.get('sidequest_decision_coverage', 1.0):.1%} dos preparar | "
            f"violações={all_turns.get('sidequest_decision_violations', 0)}"
        ),
        (
            "NV-14: "
            f"avaliações={live.get('avaliacoes', 0)} | "
            f"pressão={live.get('janelas_com_pressao', 0)} | "
            f"calma justificada={live.get('calma_justificada', 0)} | "
            f"módulos não consultados={live.get('modulos_nao_consultados', 0)}"
        ),
        f"Sistemas observados por turno: {active}",
    ]
    if ledger:
        extra.extend(
            [
                "",
                "LEDGER MODULAR V2 (inferência observacional)",
                (
                    f"Eventos={len(ledger.get('events') or [])} | "
                    f"módulos com custo={len(ledger.get('module_parent_costs') or [])} | "
                    f"fechamento de tokens={closure.get('difference', 0)}"
                ),
                "Subcapacidades exibem exposição; o custo aditivo fecha somente no módulo pai.",
            ]
        )
    return base + "\n" + "\n".join(extra) + "\n"


_core._classify_tool = _classify_tool
_core._access_level_from_command = _access_level_from_command
_core._is_turn_register = _is_turn_register
_core.analyze = analyze
_core._human = _human


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rollout", type=Path, help="arquivo rollout-*.jsonl")
    parser.add_argument("--json", action="store_true", help="imprime JSON completo")
    parser.add_argument(
        "--narration-regex",
        help="regex adicional/substitutiva para reconhecer turnos narrativos pela mensagem do usuário",
    )
    parser.add_argument(
        "--visao",
        choices=("legacy-v1", "modules-v2"),
        default="modules-v2",
        help="seleciona a extensão de telemetria; padrão modules-v2",
    )
    parser.add_argument(
        "--adjudicacoes-modulares",
        type=Path,
        help="JSON opcional de correções do ledger; observações originais são preservadas",
    )
    args = parser.parse_args()
    try:
        adjudications = None
        if args.adjudicacoes_modulares:
            adjudications = json.loads(args.adjudicacoes_modulares.read_text(encoding="utf-8"))
        report = analyze(args.rollout, args.narration_regex, adjudications)
        selected = telemetry_view(report, args.visao)
    except (OSError, json.JSONDecodeError, RolloutError, re.error) as exc:
        print(f"FALHA DE TELEMETRIA — {exc}")
        return 1
    if args.json:
        print(json.dumps(selected, ensure_ascii=False, indent=2))
    else:
        print(_human(selected), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
