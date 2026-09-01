#!/usr/bin/env python3
"""Telemetria pós-hoc de rollout com atribuição de sistemas narrativos.

O analisador schema 3 permanece congelado em ``_analisar_rollout_core.py``. Esta
camada preserva o schema público anterior e acrescenta extensões independentes
para orquestração/sistemas narrativos e, na Task47, cobertura da decisão explícita
de oportunidade de sidequest. Nada aqui roda durante o jogo ou escreve no repo.
"""
from __future__ import annotations

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
NARRATIVE_SYSTEMS_SCHEMA = 1
OPPORTUNITY_DECISION_SCHEMA = 1

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
    "canon_bridge": ("canon_bridge_runtime.py", "canon-bridge-runtime.py"),
}

_SYSTEM_OUTPUT_MARKERS: dict[str, tuple[str, ...]] = {
    "npc_social_initiative": ("iniciativa_social",),
    "world_local_incidents": (
        "incidente_mundo",
        "incidentes_mundo_v2",
        "incidentes_para_avaliar",
        "narrador/incidentes-v2/",
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
        "narrador/arcos/parte_1/eventos/",
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


def _observation_turn() -> dict[str, Any]:
    return {"user_messages": [], "narration_signal_tool": False, "calls": [], "calls_by_id": {}}


def _scan_observations(path: Path, narration_regex: str | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    narration_re = re.compile(narration_regex, re.I | re.S) if narration_regex else DEFAULT_NARRATION_RE
    turns: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    current_turn: str | None = None

    def ensure(turn_id: str) -> dict[str, Any]:
        if turn_id not in turns:
            turns[turn_id] = _observation_turn()
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
            if item_type == "message" and payload.get("role") == "user":
                text = _core._message_text(payload)
                if text and not text.startswith("# AGENTS.md instructions"):
                    turn["user_messages"].append(text)
                continue
            if item_type in {"function_call", "custom_tool_call"}:
                command = _core._extract_command(_core._tool_input(payload))
                cid = _core._call_id(payload)
                call = {
                    "call_id": cid,
                    "command": command,
                    "orchestration_phase": _orchestration_phase(command),
                    "sidequest_decision": _sidequest_decision_from_command(command),
                    "narrative_systems": _narrative_systems_from_command(command),
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
            output_text = _core._tool_output(payload)
            cid = _core._call_id(payload)
            matched = None
            if cid and cid in turn["calls_by_id"]:
                candidate = turn["calls"][turn["calls_by_id"][cid]]
                if not candidate["output_seen"]:
                    matched = candidate
            if matched is None:
                matched = next((item for item in turn["calls"] if not item["output_seen"]), None)
            if matched is not None:
                matched["narrative_systems"].update(_narrative_systems_from_output(output_text))
                matched["output_seen"] = True

    ordered = [turns[turn_id] for turn_id in order]
    narration = [turn for turn in ordered if _core._is_narration_turn(turn, narration_re)]
    return ordered, narration


def _observation_summary(turns: list[dict[str, Any]]) -> dict[str, Any]:
    phases: Counter[str] = Counter()
    decisions: Counter[str] = Counter()
    system_calls: Counter[str] = Counter()
    system_turns: Counter[str] = Counter()
    pair_turns = 0
    for turn in turns:
        per_turn_phases: list[str] = []
        per_turn_systems: set[str] = set()
        for call in turn["calls"]:
            phase = call.get("orchestration_phase")
            if isinstance(phase, str):
                phases[phase] += 1
                per_turn_phases.append(phase)
            decision = call.get("sidequest_decision")
            if isinstance(decision, str):
                decisions[decision] += 1
            for system in call.get("narrative_systems") or set():
                if system in NARRATIVE_SYSTEM_KEYS:
                    system_calls[system] += 1
                    per_turn_systems.add(system)
        if Counter(per_turn_phases) == Counter({"preparar": 1, "concluir": 1}):
            pair_turns += 1
        system_turns.update(per_turn_systems)
    n = len(turns)
    observed = [system for system in NARRATIVE_SYSTEM_KEYS if system_turns[system]]
    orchestration_calls = sum(phases.values())
    prepare_calls = sum(decisions.values())
    valid_decisions = decisions["oportunidade"] + decisions["sem_oportunidade"]
    violations = decisions["ausente"] + decisions["conflito"]
    inactive = sum(1 for turn in turns if not any(call.get("narrative_systems") for call in turn["calls"]))
    return {
        "orchestration_calls": orchestration_calls,
        "avg_orchestration_calls_per_turn": round(orchestration_calls / n, 3) if n else 0,
        "orchestration_phases": dict(sorted(phases.items())),
        "cronica_pair_turns": pair_turns,
        "fraction_turns_with_cronica_pair": round(pair_turns / n, 6) if n else 0,
        "sidequest_opportunity_decisions": {
            key: int(decisions[key])
            for key in ("oportunidade", "sem_oportunidade", "ausente", "conflito")
        },
        "sidequest_decision_prepare_calls": prepare_calls,
        "sidequest_decision_valid": int(valid_decisions),
        "sidequest_decision_violations": int(violations),
        "sidequest_decision_coverage": round(valid_decisions / prepare_calls, 6) if prepare_calls else 1.0,
        "task47_decision_gate_ok": violations == 0,
        "narrative_system_calls": {system: int(system_calls[system]) for system in NARRATIVE_SYSTEM_KEYS},
        "narrative_system_turns": {system: int(system_turns[system]) for system in NARRATIVE_SYSTEM_KEYS},
        "narrative_systems_observed": observed,
        "turns_without_narrative_system_activity": inactive,
        "fraction_turns_without_narrative_system_activity": round(inactive / n, 6) if n else 0,
    }


def analyze(path: Path, narration_regex: str | None = None) -> dict[str, Any]:
    report = _BASE_ANALYZE(path, narration_regex)
    ordered, narration = _scan_observations(path, narration_regex)
    all_summary = _observation_summary(ordered)
    narration_summary = _observation_summary(narration)
    report["narrative_systems_schema"] = NARRATIVE_SYSTEMS_SCHEMA
    report["opportunity_decision_schema"] = OPPORTUNITY_DECISION_SCHEMA
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
    for item, turn in zip(report.get("per_narration_turn") or [], narration):
        item.update(_observation_summary([turn]))
    inferred = report.get("measurement", {}).get("observational_inference")
    if isinstance(inferred, list):
        for label in (
            "preferred cronica orchestration phases inferred from command lines",
            "narrative-system attribution inferred from command and tool-output markers",
            "Task47 sidequest-opportunity decision inferred from cronica preparar flags",
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
    systems = narr.get("narrative_system_turns") or {}
    active = ", ".join(
        f"{name}={systems.get(name, 0)}" for name in NARRATIVE_SYSTEM_KEYS if systems.get(name, 0)
    ) or "nenhum"
    extra = [
        "",
        "SISTEMAS NARRATIVOS (inferência observacional)",
        (
            "Orquestração: "
            f"{narr.get('avg_orchestration_calls_per_turn', 0)} chamada(s)/turno | "
            "dupla cronica preparar+concluir em "
            f"{narr.get('fraction_turns_with_cronica_pair', 0):.1%} dos turnos"
        ),
        (
            "Task47: decisão de oportunidade em "
            f"{all_turns.get('sidequest_decision_coverage', 1.0):.1%} dos preparar | "
            f"violações={all_turns.get('sidequest_decision_violations', 0)}"
        ),
        f"Sistemas observados por turno: {active}",
    ]
    return base + "\n" + "\n".join(extra) + "\n"


_core._classify_tool = _classify_tool
_core._access_level_from_command = _access_level_from_command
_core._is_turn_register = _is_turn_register
_core.analyze = analyze
_core._human = _human


def main() -> int:
    return _core.main()


if __name__ == "__main__":
    raise SystemExit(main())
