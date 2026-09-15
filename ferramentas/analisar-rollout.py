#!/usr/bin/env python3
"""Telemetria pós-hoc de rollout com atribuição de sistemas narrativos.

O analisador schema 3 permanece congelado em ``_analisar_rollout_core.py``. Esta
camada preserva a visão ``legacy-v1`` e acrescenta o ledger hierárquico
``modules-v2``. A atribuição continua observacional, pós-hoc e somente leitura:
nada aqui roda durante o jogo ou escreve no repo.
"""
from __future__ import annotations

import argparse
import ast
import copy
import importlib.util
import json
import re
import shlex
import sys
from collections import Counter
from datetime import datetime
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
MODULAR_DETECTOR_VERSION = "4.2.0"
OPPORTUNITY_DECISION_SCHEMA = 2
CANONICAL_INTEGRATION_ASSESSMENT_SCHEMA = 1
LIVENESS_BOUNDARY_SCHEMA = 1
MODULE_COVERAGE_SCHEMA = 1

FAIL_CLOSED_MODULE_IDS = (
    "context_and_memory",
    "turn_and_session_orchestration",
    "narrative_delivery",
    "rules_and_character_state",
    "sidequest_authoring",
    "sidequest_lifecycle",
    "npc_continuity_and_social_behavior",
    "scene_world_projection",
    "world_boundary_resolution",
    "causal_narrative_routing",
    "adversarial_operations",
)

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
        "incidente_confirmado",
        "microevento_confirmado",
        "sem_incidente",
        "sem_microevento",
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
        "condicao_registrada",
        "condicao_encerrada",
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


_SHELL_OPERATORS = {"&", "&&", ";", "|", "||"}
_PYTHON_PROGRAM_RE = re.compile(r"^(?:python|python3)(?:\.\d+)*$")


def _javascript_string_literal(source: str) -> str | None:
    source = source.lstrip()
    if not source or source[0] not in {'"', "'", "`"}:
        return None
    quote = source[0]
    escaped = False
    end = None
    for index, character in enumerate(source[1:], 1):
        if escaped:
            escaped = False
            continue
        if character == "\\":
            escaped = True
            continue
        if character == quote:
            end = index
            break
    if end is None:
        return None
    literal = source[: end + 1]
    try:
        if quote == '"':
            value = json.loads(literal)
        elif quote == "'":
            value = ast.literal_eval(literal)
        else:
            value = literal[1:-1]
    except (json.JSONDecodeError, SyntaxError, ValueError):
        return None
    return value if isinstance(value, str) else None


def _javascript_variable_string(source: str, name: str, before: int) -> str | None:
    assignments = list(
        re.finditer(
            rf"\b(?:const|let|var)\s+{re.escape(name)}\s*=\s*",
            source[:before],
        )
    )
    if not assignments:
        return None
    return _javascript_string_literal(source[assignments[-1].end() :])


def _nested_exec_commands(text: str) -> list[str]:
    """Extrai comandos de chamadas ``tools.exec_command({...})`` do tool unificado."""

    decoder = json.JSONDecoder()
    commands: list[str] = []
    for match in re.finditer(r"\btools\.exec_command\s*\(\s*", text):
        try:
            payload, _ = decoder.raw_decode(text[match.end() :])
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            command = payload.get("cmd") or payload.get("command")
            if isinstance(command, str):
                commands.append(command)
                continue

        # O código do tool unificado também aceita objetos JavaScript com
        # chaves não citadas. Decodificamos somente o literal de `cmd`, sem
        # avaliar o restante do programa.
        remainder = text[match.end() :]
        key = re.search(r"(?:\bcmd\b|[\"']cmd[\"'])\s*:\s*", remainder)
        command = None
        if key is not None and key.end() < len(remainder):
            value_source = remainder[key.end() :].lstrip()
            command = _javascript_string_literal(value_source)
            if command is None:
                identifier = re.match(r"([A-Za-z_$][A-Za-z0-9_$]*)", value_source)
                if identifier:
                    command = _javascript_variable_string(
                        text, identifier.group(1), match.start()
                    )
        elif re.match(r"\s*\{\s*cmd\s*[,}]", remainder):
            command = _javascript_variable_string(text, "cmd", match.start())
        if isinstance(command, str):
            commands.append(command)
    return commands


def _command_invocations(command: str) -> list[tuple[str, list[str]]]:
    """Retorna programa e argumentos por segmento, sem interpretar texto citado."""

    nested_commands = _nested_exec_commands(command)
    if nested_commands:
        return [
            invocation
            for nested_command in nested_commands
            for invocation in _command_invocations(nested_command)
        ]

    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except ValueError:
        # Comando montado por concatenação pode expor apenas um prefixo com
        # aspas ainda abertas. O prefixo programa/subcomando continua sendo
        # evidência suficiente; o fallback jamais examina outputs ou prosa.
        tokens = command.split()

    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in _SHELL_OPERATORS:
            if segments[-1]:
                segments.append([])
            continue
        segments[-1].append(token)

    result: list[tuple[str, list[str]]] = []
    for segment in segments:
        if not segment:
            continue
        index = 0
        while index < len(segment) and re.match(
            r"^[A-Za-z_][A-Za-z0-9_]*=", segment[index]
        ):
            index += 1
        if index >= len(segment):
            continue
        if Path(segment[index]).name.casefold() == "env":
            index += 1
            while index < len(segment) and (
                segment[index].startswith("-")
                or re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", segment[index])
            ):
                index += 1
        if index + 1 < len(segment) and (
            Path(segment[index]).name.casefold() == "poetry"
            and segment[index + 1].casefold() == "run"
        ):
            index += 2
        if index >= len(segment):
            continue

        program = Path(segment[index]).name.casefold()
        index += 1
        if _PYTHON_PROGRAM_RE.fullmatch(program):
            while index < len(segment) and segment[index].startswith("-"):
                option = segment[index]
                index += 1
                if option in {"-c", "-m"}:
                    index = len(segment)
                    break
            if index >= len(segment):
                continue
            program = Path(segment[index]).name.casefold()
            index += 1
        result.append((program, [item.casefold() for item in segment[index:]]))
    return result


def _invocation(
    command: str, programs: set[str]
) -> tuple[str, list[str]] | None:
    normalized = {item.casefold() for item in programs}
    return next(
        (item for item in _command_invocations(command) if item[0] in normalized),
        None,
    )


def _is_routed_context_command(command: str) -> bool:
    return _invocation(command, {"contexto.py", "contexto-buscar-muitos.py"}) is not None


def _is_dice_command(command: str) -> bool:
    return _invocation(
        command,
        {"dados", "dados-lote", "rolar-dados.py", "rolar-lote.py"},
    ) is not None


def _is_rule_query(command: str) -> bool:
    context = _invocation(command, {"contexto.py"})
    catalog = _invocation(command, {"catalogo_regras.py"})
    return bool(
        context and "regra" in context[1]
        or catalog and {"consultar", "receita", "check"}.intersection(catalog[1])
    )


def _is_mechanical_schema_discovery(command: str, raw_input: str) -> bool:
    """Restringe a redescoberta genérica do core às portas da RM-10."""

    lower = command.casefold()
    relevant = any(
        marker in lower
        for marker in (
            "poetry run dados",
            "cronica preparar",
            "cronica concluir",
            "rolar-dados.py",
            "rolar-lote.py",
            "mecanica_cronica.py",
            "catalogo_regras.py",
            "ficha_ren.py",
            "tempo_transacional.py",
        )
    )
    return relevant and _core._is_schema_discovery(command, _core._paths(raw_input))


def _dice_observation(call: dict[str, Any]) -> dict[str, Any] | None:
    if call.get("command_executed") is False:
        return None
    command = str(call.get("command") or "")
    if not _is_dice_command(command) or _core._is_help_command(command):
        return None
    lower = " ".join(command.casefold().split())
    batch = bool(re.search(r"(?:^|\s)(?:poetry\s+run\s+)?dados-lote(?:\s|$)", lower))
    target = None
    target_flag = None
    if re.search(r"\bataque\b", lower):
        target, target_flag = "ca", "--ca"
    elif re.search(r"\b(?:d20|pericia|skill|salvaguarda|save)\b", lower):
        target, target_flag = "cd", "--cd"
    return {
        "batch": batch,
        "target": target,
        "target_applicable": target is not None,
        "target_predefined": target_flag in lower if target_flag else None,
        "success": call.get("output_success") is True,
        "output_seen": bool(call.get("output_seen")),
    }


def _character_state_categories(text: str) -> set[str]:
    """Reconhece somente estado de Ren/tempo; estado genérico pertence a outros módulos."""

    lower = text.casefold()
    categories: set[str] = set()
    if re.search(r'["\']?alvo["\']?\s*:\s*["\']?tempo\b', lower):
        categories.add("tempo_atomico")
    if re.search(r'["\']?alvo["\']?\s*:\s*["\']?ficha\b', lower):
        categories.add("ficha")
    state_target = bool(
        re.search(r'["\']?alvo["\']?\s*:\s*["\']?estado\b', lower)
    )
    if state_target:
        if "recursos." in lower or "recursos/" in lower:
            categories.add("recursos")
        if "personagem." in lower or "personagem/" in lower:
            categories.add("personagem")
        if "equipamento_em_posse" in lower:
            categories.add("equipamento")
        if "efeitos_temporarios" in lower:
            categories.add("condicoes_ou_efeitos")
    return categories


_MECHANICAL_CORRECTION_RE = re.compile(
    r"\b(?:(?:resultado d[oa] dado|resultado da rolagem).{0,80}"
    r"(?:errad[oa]|alterad[oa]|mudou|corrigid[oa]|corrigir)|(?:mudou|alterou).{0,40}"
    r"(?:resultado d[oa] dado|resultado da rolagem)|(?:cd|ca) (?:era|deveria)|"
    r"focus (?:não deveria|nao deveria)|(?:gastou|não gastou|nao gastou) focus|"
    r"regra (?:foi|está|esta) aplicada errad[ao]|corrig(?:ir|indo) a mecânica|"
    r"corrig(?:ir|indo) a mecanica)\b",
    re.IGNORECASE | re.DOTALL,
)


def _mechanical_correction_signals(turns: list[dict[str, Any]]) -> int:
    return sum(
        bool(_MECHANICAL_CORRECTION_RE.search("\n".join(turn.get("user_messages") or [])))
        for turn in turns[1:]
    )


def _rules_state_summary(turns: list[dict[str, Any]]) -> dict[str, Any]:
    calls = [
        call
        for turn in turns
        for call in turn.get("calls") or []
        if call.get("command_executed") is not False
    ]
    rule_calls = [call for call in calls if _is_rule_query(str(call.get("command") or ""))]
    normalized_rule_queries = [
        " ".join(str(call.get("command") or "").casefold().split())
        for call in rule_calls
    ]
    rolls = [observed for call in calls if (observed := _dice_observation(call))]
    target_rolls = [item for item in rolls if item["target_applicable"]]
    predefined = [item for item in target_rolls if item["target_predefined"] is True]
    receipts = [
        call["rules_state_receipt"]
        for call in calls
        if isinstance(call.get("rules_state_receipt"), dict)
    ]
    resource_obligations = sum(int(item.get("resource_obligations") or 0) for item in receipts)
    resources_applied = sum(int(item.get("resources_applied") or 0) for item in receipts)
    relevant_deltas = sum(int(item.get("relevant_deltas") or 0) for item in receipts)
    validated_receipts = sum(item.get("prewriter_validated") is True for item in receipts)
    d20_receipts = [item for item in receipts if int(item.get("d20_obligations") or 0)]
    delta_receipts = [item for item in receipts if int(item.get("relevant_deltas") or 0)]
    atomic_receipts = [item for item in receipts if item.get("atomic_time") is True]
    valid_delta_count = sum(
        int(item.get("relevant_deltas") or 0)
        for item in delta_receipts
        if item.get("prewriter_validated") is True
        and item.get("canonical_consistency") == "ok"
    )
    state_categories: Counter[str] = Counter()
    for receipt in receipts:
        state_categories.update(str(item) for item in receipt.get("categories") or [])
    for call in calls:
        for category in _character_state_categories(
            str(call.get("command") or "")
        ):
            state_categories[category] += 1
    guardrail_blocks = sum(
        any(
            marker in str(call.get("output_text") or "").casefold()
            for marker in (
                "diverge da primitiva",
                "exige obrigação",
                "exige obrigacao",
                "ticket mecânico obsoleto",
                "ticket mecanico obsoleto",
                "resultado mecânico diverge",
                "resultado mecanico diverge",
            )
        )
        for call in calls
    )
    return {
        "schema": 1,
        "consultas_regra": {
            "total": len(rule_calls),
            "unicas": len(set(normalized_rule_queries)),
            "redundantes": len(normalized_rule_queries) - len(set(normalized_rule_queries)),
            "por_oportunidade": None,
        },
        "redescobertas_schema_cli": sum(bool(call.get("schema_discovery")) for call in calls),
        "rolagens": {
            "chamadas": len(rolls),
            "lotes": sum(item["batch"] for item in rolls),
            "sucesso_ferramenta": sum(item["success"] for item in rolls),
            "falha_ou_indeterminada": sum(not item["success"] for item in rolls),
            "alvo_aplicavel": len(target_rolls),
            "alvo_predefinido": len(predefined),
            "proporcao_alvo_predefinido": round(len(predefined) / len(target_rolls), 6)
            if target_rolls
            else None,
        },
        "contratos": {
            "recibos_observados": len(receipts),
            "regras": sum(int(item.get("rules") or 0) for item in receipts),
            "obrigacoes": sum(int(item.get("obligations") or 0) for item in receipts),
            "obrigacoes_d20": sum(int(item.get("d20_obligations") or 0) for item in receipts),
            "obrigacoes_recurso": resource_obligations,
            "resolucoes": sum(int(item.get("resolutions") or 0) for item in receipts),
            "recursos_aplicados": resources_applied,
            "proporcao_recursos_aplicados": round(resources_applied / resource_obligations, 6)
            if resource_obligations
            else None,
            "validados_antes_do_writer": validated_receipts,
            "exactly_once": sum(item.get("exactly_once") is True for item in receipts),
            "replays_sem_novo_efeito": sum(item.get("new_effect") is False for item in receipts),
            "integridade_resultado_consequencia": round(
                sum(item.get("roll_integrity") == "ok" for item in d20_receipts)
                / len(d20_receipts),
                6,
            )
            if d20_receipts
            else None,
        },
        "estado_personagem_tempo": {
            "deltas_relevantes": relevant_deltas,
            "deltas_persistentes_validos": valid_delta_count,
            "proporcao_deltas_persistentes_validos": round(
                valid_delta_count / relevant_deltas, 6
            )
            if relevant_deltas
            else None,
            "categorias_observadas": dict(sorted(state_categories.items())),
            "instantes_atomicos": sum(item.get("atomic_time") is True for item in receipts),
            "proporcao_instantes_canonicos_coerentes": round(
                sum(item.get("canonical_consistency") == "ok" for item in atomic_receipts)
                / len(atomic_receipts),
                6,
            )
            if atomic_receipts
            else None,
            "divergencias_ficha_estado_runtime": None,
        },
        "guardrails": {
            "bloqueios_observados": guardrail_blocks,
            "nao_compensaveis": True,
        },
        "correcoes_mecanicas_jogador": _mechanical_correction_signals(turns),
    }


def _classify_tool(name: str, raw_input: str) -> str:
    command = _core._extract_command(raw_input)
    if _is_dice_command(command):
        return "dice"
    return _BASE_CLASSIFY_TOOL(name, raw_input)


def _access_level_from_command(command: str) -> str | None:
    if not _is_routed_context_command(command):
        return None
    result = _BASE_ACCESS_LEVEL(command)
    if result is not None:
        return result
    lower = command.casefold()
    if re.search(r"\bcontexto\.py\b.*\breputacao\b", lower):
        return "L2"
    return None


def _is_turn_register(command: str) -> bool:
    if _core._is_help_command(command):
        return False
    turno = _invocation(command, {"turno.py"})
    return bool(
        turno and turno[1][:1] == ["registrar"]
        or {"concluir", "registrar"}.intersection(_orchestration_phases(command))
    )


def _orchestration_phases(command: str) -> list[str]:
    phases: list[str] = []
    for program, args in _command_invocations(command):
        if (
            program in {"cronica", "cronica.py"}
            and args[:1]
            and args[0] in {"preparar", "concluir", "registrar", "confirmar"}
        ):
            phases.append(args[0])
    return phases


def _orchestration_phase(command: str) -> str | None:
    phases = _orchestration_phases(command)
    return phases[0] if phases else None


def _call_orchestration_phases(call: dict[str, Any]) -> list[str]:
    phases = call.get("orchestration_phases")
    if isinstance(phases, list):
        return [str(item) for item in phases if isinstance(item, str)]
    phase = call.get("orchestration_phase")
    return [phase] if isinstance(phase, str) else []


def _call_has_phase(call: dict[str, Any], phase: str) -> bool:
    return phase in _call_orchestration_phases(call)


def _expanded_orchestration_calls(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for call in calls:
        for phase in _call_orchestration_phases(call):
            result.append({**call, "orchestration_phase": phase})
    return result


def _session_lifecycle_operations(command: str) -> list[str]:
    allowed = {"status", "iniciar", "checkpoint", "encerrar", "recuperar"}
    return [
        args[1]
        for program, args in _command_invocations(command)
        if program in {"cronica", "cronica.py"}
        and len(args) >= 2
        and args[0] == "sessao"
        and args[1] in allowed
    ]


def _session_lifecycle_operation(command: str) -> str | None:
    operations = _session_lifecycle_operations(command)
    return operations[0] if operations else None


def _call_session_lifecycle_operations(call: dict[str, Any]) -> list[str]:
    operations = call.get("session_lifecycle_operations")
    if isinstance(operations, list):
        return [str(item) for item in operations if isinstance(item, str)]
    operation = call.get("session_lifecycle_operation")
    return [operation] if isinstance(operation, str) else []


def _expanded_session_lifecycle_calls(
    calls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for call in calls:
        for operation in _call_session_lifecycle_operations(call):
            result.append({**call, "session_lifecycle_operation": operation})
    return result


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


def _output_int(output_text: str, key: str) -> int | None:
    value = _output_scalar(output_text, key)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _output_string_list(output_text: str, key: str) -> list[str]:
    json_match = re.search(
        rf'"{re.escape(key)}"\s*:\s*(\[[^\]]*\])', output_text, re.I
    )
    if json_match:
        try:
            value = json.loads(json_match.group(1))
        except json.JSONDecodeError:
            value = None
        if isinstance(value, list):
            return [str(item) for item in value if isinstance(item, str)]

    lines = output_text.splitlines()
    for index, line in enumerate(lines):
        match = re.match(rf'^(\s*){re.escape(key)}\s*:\s*$', line, re.I)
        if not match:
            continue
        base_indent = len(match.group(1))
        result: list[str] = []
        for candidate in lines[index + 1 :]:
            if not candidate.strip():
                continue
            indent = len(candidate) - len(candidate.lstrip())
            item = re.match(r"^\s*-\s+(.+?)\s*$", candidate)
            if item and indent >= base_indent:
                result.append(item.group(1).strip("'\""))
                continue
            if indent <= base_indent:
                break
        return result
    return []


def _record_timestamp(record: dict[str, Any], payload: dict[str, Any]) -> float | None:
    """Normaliza somente relógios explícitos do rollout; ausência fica N/D."""

    candidates = (record.get("timestamp"), payload.get("timestamp"))
    for value in candidates:
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
        if not isinstance(value, str) or not value.strip():
            continue
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(normalized).timestamp()
        except ValueError:
            continue
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


def _successful_turn_conclusion(call: dict[str, Any]) -> bool:
    """Return whether a conclude invocation visibly completed the transaction."""
    if call.get("output_success") is not True or call.get("orchestration_failure"):
        return False
    receipt = call.get("orchestration_receipt") or {}
    state = str(receipt.get("state") or "").casefold()
    if state in {"concluido", "concluida", "commitado", "completo", "complete", "completed"}:
        return True
    if receipt.get("commit_result") or receipt.get("new_effect") is True:
        return True
    interaction = call.get("interaction_receipt") or {}
    if str(interaction.get("state") or "").casefold() in {
        "concluido",
        "concluida",
        "completo",
        "complete",
        "completed",
    }:
        return True
    return bool(
        re.search(
            r"(?im)^\s*fase\s*:\s*(?:conclu[ií]d[ao]|complet[ao])\s*$",
            str(call.get("output_text") or ""),
        )
    )


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


def _delivery_receipt(output_text: str) -> dict[str, Any] | None:
    marker = "schema_narrative_delivery"
    start = output_text.casefold().rfind(marker)
    if start < 0:
        return None
    receipt_text = output_text[start:]
    return {
        "delivery_id": _output_scalar(receipt_text, "entrega_id"),
        "state": _output_scalar(receipt_text, "estado"),
        "ticket_id": _output_scalar(receipt_text, "ticket_id"),
        "transaction_id": _output_scalar(receipt_text, "transacao_id"),
        "session": _output_scalar(receipt_text, "sessao"),
        "turn_class": _output_scalar(receipt_text, "classe_turno"),
        "characters": _output_int(receipt_text, "caracteres"),
        "words": _output_int(receipt_text, "palavras"),
        "paragraphs": _output_int(receipt_text, "paragrafos"),
        "mechanics_lines": _output_int(receipt_text, "linhas_mecanica"),
        "footer_emitted": _output_bool(receipt_text, "emitido"),
        "semantic_assessment": _output_scalar(receipt_text, "avaliacao_semantica"),
    }


def _rules_state_receipt(output_text: str) -> dict[str, Any] | None:
    marker = "schema_rules_and_character_state"
    start = output_text.casefold().rfind(marker)
    if start < 0:
        return None
    receipt_text = output_text[start:]
    return {
        "event_id": _output_scalar(receipt_text, "evento_id"),
        "state": _output_scalar(receipt_text, "estado"),
        "ticket_id": _output_scalar(receipt_text, "ticket_id"),
        "transaction_id": _output_scalar(receipt_text, "transacao_id"),
        "session": _output_scalar(receipt_text, "sessao"),
        "rules": _output_int(receipt_text, "regras"),
        "obligations": _output_int(receipt_text, "obrigacoes"),
        "d20_obligations": _output_int(receipt_text, "obrigacoes_d20"),
        "resource_obligations": _output_int(receipt_text, "obrigacoes_recurso"),
        "resolutions": _output_int(receipt_text, "resolucoes"),
        "resources_applied": _output_int(receipt_text, "recursos_aplicados"),
        "relevant_deltas": _output_int(receipt_text, "deltas_relevantes"),
        "categories": _output_string_list(receipt_text, "categorias"),
        "atomic_time": _output_bool(receipt_text, "tempo_atomico"),
        "prewriter_validated": _output_bool(receipt_text, "validado_antes_do_writer"),
        "exactly_once": _output_bool(receipt_text, "exactly_once"),
        "new_effect": _output_bool(receipt_text, "efeito_novo"),
        "roll_integrity": _output_scalar(receipt_text, "roll_integrity"),
        "canonical_consistency": _output_scalar(receipt_text, "canonical_consistency"),
    }


def _interaction_receipt(output_text: str) -> dict[str, Any] | None:
    marker = "schema_narrative_interaction"
    start = output_text.casefold().rfind(marker)
    if start < 0:
        return None
    receipt_text = output_text[start:]
    return {
        "interaction_id": _output_scalar(receipt_text, "interaction_id"),
        "interaction_ref": _output_scalar(receipt_text, "interaction_ref"),
        "session": _output_int(receipt_text, "session"),
        "ordinal": _output_int(receipt_text, "ordinal"),
        "class": _output_scalar(receipt_text, "class"),
        "state": _output_scalar(receipt_text, "state"),
        "replay": _output_bool(receipt_text, "replay"),
    }


def _opportunity_assessment_receipt(output_text: str) -> dict[str, Any] | None:
    marker = "schema_avaliacao_oportunidade_sidequest"
    start = output_text.casefold().rfind(marker)
    if start < 0:
        return None
    receipt_text = output_text[start:]
    return {
        "schema": _output_int(receipt_text, marker),
        "module_id": _output_scalar(receipt_text, "module_id"),
        "implementation_version": _output_scalar(
            receipt_text, "versao_implementacao"
        ),
        "evaluation_version": _output_scalar(receipt_text, "versao_avaliacao"),
        "declaration": _output_scalar(receipt_text, "declaracao"),
        "effective_decision": _output_scalar(receipt_text, "decisao_efetiva"),
        "expected_result": _output_scalar(receipt_text, "resultado_esperado"),
        "classification": _output_scalar(receipt_text, "classificacao"),
        "included_in_score": _output_bool(receipt_text, "incluida_na_pontuacao"),
        "structured_candidates": _output_int(
            receipt_text, "candidatos_estruturados"
        ),
        "reasons": _output_string_list(receipt_text, "motivos"),
    }


def _canonical_integration_assessment_receipts(
    output_text: str,
) -> list[dict[str, Any]]:
    marker = "schema_avaliacao_integracao_canonica"
    starts = [match.start() for match in re.finditer(marker, output_text.casefold())]
    result: list[dict[str, Any]] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else len(output_text)
        receipt_text = output_text[start:end]
        result.append(
            {
                "schema": _output_int(receipt_text, marker),
                "assessment_id": _output_scalar(receipt_text, "assessment_id"),
                "module_id": _output_scalar(receipt_text, "module_id"),
                "capability_id": _output_scalar(receipt_text, "capability_id"),
                "implementation_version": _output_scalar(
                    receipt_text, "versao_implementacao"
                ),
                "evaluation_version": _output_scalar(
                    receipt_text, "versao_avaliacao"
                ),
                "mission_ref": _output_scalar(receipt_text, "mission_ref"),
                "trigger": _output_scalar(receipt_text, "gatilho"),
                "classification": _output_scalar(receipt_text, "classificacao"),
                "included_in_score": _output_bool(
                    receipt_text, "incluida_na_pontuacao"
                ),
                "complete": _output_bool(receipt_text, "recibo_completo"),
                "reasons": _output_string_list(receipt_text, "motivos"),
            }
        )
    return result


def _canonical_integration_receipt_complete(receipt: dict[str, Any]) -> bool:
    return bool(
        receipt.get("schema") == CANONICAL_INTEGRATION_ASSESSMENT_SCHEMA
        and receipt.get("complete") is True
        and receipt.get("module_id") == "canonical_quest_integration"
        and receipt.get("mission_ref")
        and receipt.get("assessment_id")
    )


def _canonical_integration_expected_receipts(call: dict[str, Any]) -> int:
    if call.get("command_executed") is False or call.get("output_success") is False:
        return 0
    output_text = str(call.get("output_text") or "")
    output_lower = output_text.casefold()
    expected = 0
    if "resultado: sidequest_materializada" in output_lower or (
        '"resultado": "sidequest_materializada"' in output_lower
    ):
        expected += 1
    if any(
        marker in output_lower
        for marker in (
            "resultado: progresso_sidequests_registrado",
            "resultado: sem_fatos_sidequest",
            '"resultado": "progresso_sidequests_registrado"',
            '"resultado": "sem_fatos_sidequest"',
        )
    ):
        expected += int(_output_int(output_text, "missoes_reavaliadas") or 0)

    invocations = _command_invocations(str(call.get("command") or ""))
    lifecycle_programs = {
        "canonical_quest_integration.py",
        "canon_bridge_runtime.py",
        "oportunidades.py",
    }
    if any(
        program in lifecycle_programs
        and args[:1]
        and args[0] in {"oferecer", "responder", "finalizar", "abandonar"}
        for program, args in invocations
    ):
        expected = max(expected, 1)
    return expected


def _sidequest_decision_from_command(command: str) -> str | None:
    if "preparar" not in _orchestration_phases(command):
        return None
    cronica = next(
        (
            item
            for item in _command_invocations(command)
            if item[0] in {"cronica", "cronica.py"}
            and item[1][:1] == ["preparar"]
        ),
        None,
    )
    if cronica is None:
        return None
    opportunity = "--oportunidade-sidequest" in cronica[1]
    declined = "--sem-oportunidade-sidequest" in cronica[1]
    if opportunity and declined:
        return "conflito"
    if opportunity:
        return "oportunidade"
    if declined:
        return "sem_oportunidade"
    return "ausente"


def _spatial_prepare_kinds(command: str) -> list[str]:
    """Return typed spatial triggers routed through ``cronica preparar``."""

    kinds: list[str] = []
    for program, args in _command_invocations(command):
        if program not in {"cronica", "cronica.py"} or args[:1] != ["preparar"]:
            continue
        if "--permanencia-local" in args:
            kinds.append("permanencia_local")
        elif "--transito-urbano" in args:
            kinds.append("transito_urbano")
        elif "--local" in args and any(
            args[index + 1] in {"entrar", "explorar"}
            for index, item in enumerate(args[:-1])
            if item == "--acao"
        ):
            kinds.append("gatilho_local")
    return kinds


def _top_level_output_section(output_text: str, name: str) -> str:
    lines = output_text.splitlines()
    start = next(
        (
            index
            for index, line in enumerate(lines)
            if re.fullmatch(rf"{re.escape(name)}\s*:\s*", line, re.I)
        ),
        None,
    )
    if start is None:
        return ""
    section: list[str] = []
    for line in lines[start + 1 :]:
        if line and not line[0].isspace():
            break
        section.append(line)
    return "\n".join(section)


def _module_coverage_receipts(output_text: str) -> dict[str, Any]:
    """Lê somente o recibo compacto; schema ou linha divergente ficam incompletos."""

    marker = "cobertura_avaliacao_modular"
    lower = output_text.casefold()
    block_present = marker in lower
    schema_present = bool(
        block_present
        and re.search(
            r'["\']?schema_avaliacao_cobertura_modular["\']?\s*:\s*1\b',
            output_text,
            re.I,
        )
    )
    encoded = re.findall(
        r'([a-z][a-z0-9_]*\|[a-z][a-z0-9_]*\|(?:aplicavel|nao_aplicavel|indeterminado)\|\d+)',
        output_text,
        re.I,
    )
    receipts: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, int]] = set()
    for raw in encoded:
        module_id, phase, applicability, raw_units = raw.casefold().split("|", 3)
        units = int(raw_units)
        key = (module_id, phase, applicability, units)
        if key in seen:
            continue
        seen.add(key)
        receipts.append(
            {
                "module_id": module_id,
                "phase": phase,
                "applicability": applicability,
                "units": units,
                "complete": bool(
                    schema_present
                    and module_id in FAIL_CLOSED_MODULE_IDS
                    and units > 0
                ),
            }
        )
    return {
        "block_present": block_present,
        "schema_present": schema_present,
        "receipts": receipts,
    }


def _spatial_prepare_result(
    kind: str, output_text: str, output_success: bool | None
) -> tuple[str, str, str | None, bool]:
    """Classify a read-only spatial preparation without inventing an effect."""

    lower = output_text.casefold()
    candidate = bool(
        re.search(
            r"(?i)\bresultado\s*:\s*avaliar_(?:microevento|incidente)\b",
            output_text,
        )
        or re.search(r"(?im)^\s+carta\s*:\s*$", output_text)
    )
    neutral = any(
        marker in lower
        for marker in (
            "resultado: rotina",
            "resultado: calma_espacial",
            "sem_incidente",
            "sem_microevento",
        )
    )
    visible_projection = bool(
        _top_level_output_section(output_text, "transito_urbano")
        or _top_level_output_section(output_text, "permanencia_espacial")
        or re.search(
            r"(?im)^(?:incidente_mundo|incidentes_para_avaliar|"
            r"condicoes_persistentes_ativas)\s*:",
            output_text,
        )
    )
    if output_success is False:
        return "consulta", "preparo_espacial_falhou", None, visible_projection
    if candidate:
        return "decisao", "projecao_espacial_reservada", None, True
    if visible_projection and neutral:
        return "gate_neutro", "projecao_espacial_neutra", None, True
    if visible_projection or output_success is True:
        return "consulta", f"{kind}_processado", None, visible_projection
    return "consulta", f"{kind}_encaminhado", None, False


def _narrative_systems_from_command(command: str) -> set[str]:
    result: set[str] = set()
    invocations = _command_invocations(command)
    marker_programs = {
        system: {Path(marker).name.casefold() for marker in markers}
        for system, markers in _SYSTEM_COMMAND_MARKERS.items()
    }
    for program, args in invocations:
        arg_set = set(args)
        if program == "contexto.py" and "npc" in arg_set:
            result.add("npc_social_initiative")
        if (
            program in {"cronica", "cronica.py"}
            and args[:1] == ["preparar"]
            and "--oportunidade-sidequest" in arg_set
        ):
            result.add("emergent_sidequest_opportunity")
        if program == "sidequest_authoring.py":
            result.add("emergent_sidequest_authoring")
        if program == "sidequest_lifecycle.py":
            result.add("active_sidequest_reassessment")
        if program == "canonical_quest_integration.py":
            if {"avaliar", "oferecer", "efeitos", "check"}.intersection(arg_set):
                result.add("canonical_secret_quests")
            if {"responder", "finalizar", "abandonar", "reconciliar", "check"}.intersection(
                arg_set
            ):
                result.add("canon_bridge")
        if program == "scene_world_projection.py":
            result.update({"world_local_incidents", "persistent_world_conditions"})
        if program == "world_boundary_resolution.py":
            if {"fronteira", "check"}.intersection(arg_set):
                result.add("liveness_boundary")
            if {"preparar", "aplicar", "check"}.intersection(arg_set):
                result.add("batch_world_boundary")
        if program == "causal_narrative_routing.py":
            result.add("reactive_pressure_routing")
            if "check" in arg_set:
                result.add("secret_canon")
        if program == "adversarial_operations.py":
            if {"agente", "check"}.intersection(arg_set):
                result.add("adversarial_integrity")
            if {
                "preparar",
                "materializar",
                "comprometer",
                "registrar-rolagem",
                "resolver",
                "entregar-informacao",
                "percepcao-ren",
                "reconciliar",
                "check",
            }.intersection(arg_set):
                result.add("concurrent_adversarial_operations")
        for system, programs in marker_programs.items():
            if program in programs:
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
        "user_timestamps": [],
        "assistant_messages": [],
        "assistant_records": [],
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
                timestamp = _record_timestamp(record, payload)
                if payload.get("role") == "user":
                    if text and not text.startswith("# AGENTS.md instructions"):
                        turn["user_messages"].append(text)
                        if timestamp is not None:
                            turn["user_timestamps"].append(timestamp)
                elif payload.get("role") == "assistant" and text:
                    turn["assistant_messages"].append(text)
                    turn["assistant_records"].append(
                        {
                            "text": text,
                            "channel": payload.get("channel"),
                            "timestamp": timestamp,
                        }
                    )
                continue
            if item_type in {"function_call", "custom_tool_call"}:
                name = str(payload.get("name") or "<sem-nome>")
                raw_input = _core._tool_input(payload)
                command = _core._extract_command(_core._tool_input(payload))
                cid = _core._call_id(payload)
                command_systems = _narrative_systems_from_command(command)
                command_markers = _matching_markers(command, _SYSTEM_COMMAND_MARKERS)
                orchestration_phases = _orchestration_phases(command)
                lifecycle_operations = _session_lifecycle_operations(command)
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
                    "orchestration_phase": (
                        orchestration_phases[0] if orchestration_phases else None
                    ),
                    "orchestration_phases": orchestration_phases,
                    "session_lifecycle_operation": (
                        lifecycle_operations[0] if lifecycle_operations else None
                    ),
                    "session_lifecycle_operations": lifecycle_operations,
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
                    "schema_discovery": _is_mechanical_schema_discovery(command, raw_input),
                    "orchestration_receipt": None,
                    "delivery_receipt": None,
                    "rules_state_receipt": None,
                    "interaction_receipt": None,
                    "opportunity_assessment": None,
                    "canonical_integration_assessments": [],
                    "module_coverage": {
                        "block_present": False,
                        "schema_present": False,
                        "receipts": [],
                    },
                    "orchestration_failure": None,
                    "liveness": None,
                    "output_seen": False,
                    "command_executed": True,
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
                output_lower = output_text.casefold()
                nested_commands = _nested_exec_commands(
                    str(matched.get("command") or "")
                )
                execution_prevented = bool(
                    len(nested_commands) == 1
                    and (
                        "erro: ticket armazenado não encontrado" in output_lower
                        or (
                            "script error:" in output_lower
                            and "referenceerror:" in output_lower
                        )
                    )
                )
                matched["command_executed"] = not execution_prevented
                if execution_prevented:
                    matched["orchestration_phase"] = None
                    matched["orchestration_phases"] = []
                    matched["session_lifecycle_operation"] = None
                    matched["session_lifecycle_operations"] = []
                    matched["sidequest_decision"] = None
                    matched["narrative_systems"] = set()
                    matched["command_systems"] = set()
                    matched["command_markers"] = {}
                output_is_observation = bool(
                    not execution_prevented
                    and matched.get("category") not in {"read_search", "validation"}
                )
                output_systems = (
                    set()
                    if not output_is_observation
                    else _narrative_systems_from_output(output_text)
                )
                orchestration_failure = (
                    _orchestration_failure_kind(output_text)
                    if output_is_observation
                    else None
                )
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
                    explicit_failure = orchestration_failure is not None or any(
                        marker in output_lower
                        for marker in ("falha cronica", "script failed", "traceback (most recent call last)")
                    )
                    success = not explicit_failure
                matched["output_success"] = success
                matched["duration_seconds"] = _duration_seconds(output_text)
                matched["orchestration_receipt"] = (
                    _orchestration_receipt(output_text) if output_is_observation else None
                )
                matched["delivery_receipt"] = (
                    _delivery_receipt(output_text) if output_is_observation else None
                )
                matched["rules_state_receipt"] = (
                    _rules_state_receipt(output_text) if output_is_observation else None
                )
                matched["interaction_receipt"] = (
                    _interaction_receipt(output_text) if output_is_observation else None
                )
                matched["opportunity_assessment"] = (
                    _opportunity_assessment_receipt(output_text)
                    if output_is_observation
                    else None
                )
                matched["canonical_integration_assessments"] = (
                    _canonical_integration_assessment_receipts(output_text)
                    if output_is_observation
                    else []
                )
                matched["module_coverage"] = (
                    _module_coverage_receipts(output_text)
                    if output_is_observation
                    else {
                        "block_present": False,
                        "schema_present": False,
                        "receipts": [],
                    }
                )
                matched["orchestration_failure"] = orchestration_failure
                matched["liveness"] = (
                    _liveness_observation(output_text) if output_is_observation else None
                )
                matched["output_seen"] = True

    ordered = [turns[turn_id] for turn_id in order]
    for turn in ordered:
        turn["narration_signal_tool"] = any(
            call.get("command_executed") is not False
            and _is_turn_register(str(call.get("command") or ""))
            for call in turn.get("calls") or []
        )
    narration = [turn for turn in ordered if _core._is_narration_turn(turn, narration_re)]
    return ordered, narration


def _expected_module_activities(call: dict[str, Any]) -> list[tuple[str, str | None]]:
    """Deriva a obrigação de cobertura da porta pública realmente concluída."""

    if call.get("command_executed") is False or call.get("output_success") is not True:
        return []
    command = str(call.get("command") or "")
    expected: list[tuple[str, str | None]] = []
    receipt = call.get("orchestration_receipt") or {}
    blocked = str(receipt.get("state") or "").casefold().startswith("bloquead")
    direct = {
        "context_and_memory.py": "context_and_memory",
        "sidequest_authoring.py": "sidequest_authoring",
        "sidequest_lifecycle.py": "sidequest_lifecycle",
        "npc_continuity_and_social_behavior.py": "npc_continuity_and_social_behavior",
        "scene_world_projection.py": "scene_world_projection",
        "world_boundary_resolution.py": "world_boundary_resolution",
        "causal_narrative_routing.py": "causal_narrative_routing",
        "adversarial_operations.py": "adversarial_operations",
        "rules_and_character_state.py": "rules_and_character_state",
        "narrative_delivery.py": "narrative_delivery",
        "turn_and_session_orchestration.py": "turn_and_session_orchestration",
    }
    for program, args in _command_invocations(command):
        if program in {"cronica", "cronica.py"} and args[:1] == ["preparar"]:
            expected.append(("turn_and_session_orchestration", "preparar"))
            if not blocked:
                expected.extend(
                    (
                        ("scene_world_projection", "preparar"),
                        ("sidequest_authoring", "preparar"),
                        ("sidequest_lifecycle", "preparar"),
                        ("causal_narrative_routing", "preparar"),
                        ("npc_continuity_and_social_behavior", "preparar"),
                        ("context_and_memory", "preparar"),
                    )
                )
        elif program in {"cronica", "cronica.py"} and args[:1] == ["concluir"]:
            expected.extend(
                (
                    ("turn_and_session_orchestration", "concluir"),
                    ("context_and_memory", "concluir"),
                    ("npc_continuity_and_social_behavior", "concluir"),
                    ("rules_and_character_state", "concluir"),
                    ("narrative_delivery", "concluir"),
                )
            )
        elif program in {"cronica", "cronica.py"} and args[:1] == ["sessao"]:
            operation = args[1] if len(args) > 1 else None
            if operation:
                expected.append(
                    ("turn_and_session_orchestration", f"sessao_{operation}")
                )
        elif program == "contexto.py" and args[:1] != ["check"]:
            expected.append(("context_and_memory", "consulta"))
        elif program in {"dados", "dados-lote", "dados.py", "dados-lote.py"}:
            # As primitivas de dado já têm saída estruturada própria e não
            # atravessam um envelope YAML ao qual anexar o recibo compacto.
            expected.append(("rules_and_character_state", None))
        elif program == "endpoints.py" and args[:1] == ["fronteira"]:
            expected.append(("world_boundary_resolution", "fronteira"))
        elif program in direct and args[:1] != ["check"]:
            expected.append((direct[program], None))
    return list(dict.fromkeys(expected))


def _native_coverage_complete(
    call: dict[str, Any], module_id: str, applicability: str
) -> bool:
    if module_id == "turn_and_session_orchestration":
        return isinstance(call.get("orchestration_receipt"), dict)
    if module_id == "narrative_delivery":
        return isinstance(call.get("delivery_receipt"), dict)
    if module_id == "rules_and_character_state" and applicability == "aplicavel":
        return isinstance(call.get("rules_state_receipt"), dict) or (
            _dice_observation(call) is not None
            and call.get("output_success") is True
        )
    if module_id == "sidequest_authoring":
        return isinstance(call.get("opportunity_assessment"), dict)
    return True


def _module_coverage_gates(turns: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    counters = {
        module_id: Counter(
            {
                "activity_units": 0,
                "receipts": 0,
                "complete_receipts": 0,
                "applicable_units": 0,
                "not_applicable_units": 0,
                "indeterminate_units": 0,
                "missing_receipts": 0,
                "incomplete_receipts": 0,
                "duplicate_receipts": 0,
            }
        )
        for module_id in FAIL_CLOSED_MODULE_IDS
    }
    assessments: dict[str, list[dict[str, Any]]] = {
        module_id: [] for module_id in FAIL_CLOSED_MODULE_IDS
    }
    for turn in turns:
        turn_id = str(turn.get("turn_id") or "")
        for call in turn.get("calls") or []:
            for module_id, expected_phase in _expected_module_activities(call):
                if module_id not in counters:
                    continue
                counter = counters[module_id]
                counter["activity_units"] += 1
                coverage = call.get("module_coverage") or {}
                module_receipts = [
                    item
                    for item in coverage.get("receipts") or []
                    if item.get("module_id") == module_id
                ]
                matching = [
                    item
                    for item in module_receipts
                    if expected_phase is None or item.get("phase") == expected_phase
                ]
                if (
                    not matching
                    and module_id == "rules_and_character_state"
                    and expected_phase is None
                    and _dice_observation(call) is not None
                ):
                    matching = [
                        {
                            "module_id": module_id,
                            "phase": "rolagem",
                            "applicability": "aplicavel",
                            "units": 1,
                            "complete": True,
                        }
                    ]
                status = "completo"
                applicability = None
                if not matching:
                    key = (
                        "incomplete_receipts"
                        if module_receipts
                        or (
                            coverage.get("block_present")
                            and not coverage.get("schema_present")
                        )
                        else "missing_receipts"
                    )
                    counter[key] += 1
                    status = "incompleto" if key == "incomplete_receipts" else "ausente"
                else:
                    counter["receipts"] += len(matching)
                    if len(matching) > 1:
                        counter["duplicate_receipts"] += len(matching) - 1
                        counter["incomplete_receipts"] += 1
                        status = "duplicado"
                    receipt = matching[0]
                    applicability = str(receipt.get("applicability") or "")
                    native_complete = _native_coverage_complete(
                        call, module_id, applicability
                    )
                    if receipt.get("complete") is not True or not native_complete:
                        counter["incomplete_receipts"] += 1
                        status = "incompleto"
                    elif len(matching) == 1:
                        counter["complete_receipts"] += 1
                        field = {
                            "aplicavel": "applicable_units",
                            "nao_aplicavel": "not_applicable_units",
                            "indeterminado": "indeterminate_units",
                        }[applicability]
                        counter[field] += 1
                assessments[module_id].append(
                    {
                        "turn_id": turn_id,
                        "call_id": str(call.get("call_id") or "") or None,
                        "phase": expected_phase,
                        "applicability": applicability,
                        "receipt_status": status,
                    }
                )

    result: dict[str, dict[str, Any]] = {}
    for module_id, counter in counters.items():
        activity = int(counter["activity_units"])
        complete = int(counter["complete_receipts"])
        result[module_id] = {
            "schema": MODULE_COVERAGE_SCHEMA,
            "module_id": module_id,
            **dict(counter),
            "coverage_complete": bool(
                counter["missing_receipts"] == 0
                and counter["incomplete_receipts"] == 0
                and counter["duplicate_receipts"] == 0
                and complete == activity
            ),
            "assessments": assessments[module_id],
            "regra": (
                "atividade esperada exige recibo completo; ausência ou incompletude "
                "é falha de instrumentação e N/D exige zero atividade"
            ),
        }
    return result


def _visible_response(turn: dict[str, Any]) -> dict[str, Any] | None:
    records = [item for item in turn.get("assistant_records") or [] if item.get("text")]
    finals = [item for item in records if item.get("channel") == "final"]
    if finals:
        return finals[-1]
    # Rollouts antigos não registravam canal. Em rollouts modernos, comentário
    # sem `final` é atualização operacional, não entrega ao jogador.
    if records:
        if not any(item.get("channel") is not None for item in records):
            return records[-1]
        return None
    messages = [text for text in turn.get("assistant_messages") or [] if text]
    return {"text": messages[-1], "channel": None, "timestamp": None} if messages else None


_INTERACTION_REFERENCE_RE = re.compile(r"\bS\d{3,}-I\d{4,}\b")


def _interaction_observation(turn: dict[str, Any], ordinal: int) -> dict[str, Any]:
    receipts = [
        call["interaction_receipt"]
        for call in turn.get("calls") or []
        if isinstance(call.get("interaction_receipt"), dict)
    ]
    receipt = receipts[-1] if receipts else None
    response = _visible_response(turn)
    response_text = str((response or {}).get("text") or "")
    visible_refs = _INTERACTION_REFERENCE_RE.findall(response_text)
    reference = str((receipt or {}).get("interaction_ref") or "") or (
        visible_refs[-1] if visible_refs else None
    )
    interaction_id = str((receipt or {}).get("interaction_id") or "") or None
    visible_once = bool(reference and visible_refs.count(reference) == 1)
    return {
        "interaction_id": interaction_id,
        "interaction_ref": reference,
        "session": (receipt or {}).get("session"),
        "ordinal": (receipt or {}).get("ordinal") or ordinal,
        "class": (receipt or {}).get("class") or "ON",
        "state": (receipt or {}).get("state") or ("complete" if response else "incomplete"),
        "turn_id": str(turn.get("turn_id") or f"ordinal-{ordinal}"),
        "visible_reference_count": visible_refs.count(reference) if reference else 0,
        "visible_exactly_once": visible_once,
        "receipt_present": receipt is not None,
        "response_present": response is not None,
    }


def _delivery_observation(turn: dict[str, Any]) -> dict[str, Any]:
    """Observa estrutura da saída; adequação narrativa exige adjudicação."""

    response = _visible_response(turn)
    receipts = [
        call["delivery_receipt"]
        for call in turn.get("calls") or []
        if isinstance(call.get("delivery_receipt"), dict)
    ]
    receipt = receipts[-1] if receipts else None
    text = str((response or {}).get("text") or "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    footer_lines = [line for line in lines if line.startswith("RODAPE_CANONICO")]
    footer_correct = bool(lines and footer_lines and lines[-1] == footer_lines[-1])
    body_lines = [line for line in lines if not line.startswith("RODAPE_CANONICO")]
    mechanics_lines = [
        line
        for line in body_lines
        if line.startswith("MECÂNICA —") or line.startswith("MECANICA —")
    ]
    prose_lines = [line for line in body_lines if line not in mechanics_lines]
    paragraphs = [part for part in re.split(r"\n\s*\n", text.strip()) if part.strip()]
    user_times = [value for value in turn.get("user_timestamps") or [] if isinstance(value, (int, float))]
    response_time = (response or {}).get("timestamp")
    latency = None
    if user_times and isinstance(response_time, (int, float)) and response_time >= min(user_times):
        latency = round(response_time - min(user_times), 3)
    turn_class = str((receipt or {}).get("turn_class") or "").strip()
    if not turn_class:
        turn_class = "mecanico" if mechanics_lines else "nao_declarada"
    return {
        "response_present": response is not None,
        "receipt_present": receipt is not None,
        "correlated_delivery": (
            response is not None
            and receipt is not None
            and bool(receipt.get("delivery_id"))
        ),
        "delivery_id": (receipt or {}).get("delivery_id"),
        "turn_class": turn_class,
        "characters": len(text),
        "words": len(re.findall(r"[^\W_]+(?:[-'][^\W_]+)*", text, flags=re.UNICODE)),
        "paragraphs": len(paragraphs),
        "mechanics_lines": len(mechanics_lines),
        "footer_lines": len(footer_lines),
        "footer_correct": footer_correct,
        "procedural_only": bool(mechanics_lines and not prose_lines),
        "latency_seconds": latency,
        "semantic_assessment": "nao_avaliada",
        "automatic_literary_score": None,
    }


_NEXT_TURN_REWORK_RE = re.compile(
    r"\b(?:corrigindo|correção|correcao|retcon|isso não aconteceu|isso nao aconteceu|"
    r"você decidiu por ren|voce decidiu por ren|não foi isso que eu disse|nao foi isso que eu disse|"
    r"você avançou o tempo demais|voce avancou o tempo demais|não queria avançar tanto|"
    r"nao queria avancar tanto)\b",
    re.IGNORECASE,
)


def _next_turn_rework_signals(turns: list[dict[str, Any]]) -> int:
    """Conta pedidos explícitos; é indício conservador, nunca veredito de qualidade."""

    return sum(
        bool(_NEXT_TURN_REWORK_RE.search("\n".join(turn.get("user_messages") or [])))
        for turn in turns[1:]
    )


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
    opportunity_assessment_counts: Counter[str] = Counter()
    opportunity_assessments: list[dict[str, Any]] = []
    canonical_assessment_counts: Counter[str] = Counter()
    canonical_assessments: list[dict[str, Any]] = []
    canonical_assessment_ids: set[str] = set()
    canonical_complete_receipts = 0
    canonical_duplicate_receipts = 0
    canonical_expected_receipts = 0
    canonical_missing_receipts = 0
    canonical_incomplete_receipts = 0
    pair_turns = 0
    successful_pair_turns = 0
    correlated_pair_turns = 0
    mismatched_pair_turns = 0
    indeterminate_pair_turns = 0
    blocked_turns = 0
    receipt_calls = 0
    lifecycle_receipt_calls = 0
    deliveries = [_delivery_observation(turn) for turn in turns]
    for turn in turns:
        per_turn_phases: list[str] = []
        per_turn_systems: set[str] = set()
        primary_calls: dict[str, dict[str, Any]] = {}
        blocked = False
        for call in turn["calls"]:
            if call.get("command_executed") is False:
                continue
            call_phases = _call_orchestration_phases(call)
            for phase in call_phases:
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
            receipt = call.get("orchestration_receipt")
            call_lifecycle_operations = _call_session_lifecycle_operations(call)
            receipt_operation = (
                str(receipt.get("operation") or "")
                if isinstance(receipt, dict)
                else ""
            )
            for lifecycle in call_lifecycle_operations:
                lifecycle_operations[lifecycle] += 1
                call_classes["lifecycle_sessao"] += 1
                outcome_attributable = (
                    len(call_lifecycle_operations) == 1
                    or receipt_operation == lifecycle
                )
                if outcome_attributable and call.get("output_success") is True:
                    lifecycle_success[lifecycle] += 1
                duration = call.get("duration_seconds")
                if outcome_attributable and isinstance(duration, (int, float)):
                    phase_durations.setdefault(f"sessao:{lifecycle}", []).append(float(duration))

            if isinstance(receipt, dict):
                receipt_calls += 1
                if call_lifecycle_operations:
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
            assessment = call.get("opportunity_assessment")
            if isinstance(assessment, dict):
                classification = str(assessment.get("classification") or "indeterminado")
                if classification not in {
                    "verdadeiro_positivo",
                    "verdadeiro_negativo",
                    "falso_positivo",
                    "falso_negativo",
                    "indeterminado",
                }:
                    classification = "indeterminado"
                opportunity_assessment_counts[classification] += 1
                opportunity_assessments.append(
                    {
                        "turn_id": str(turn.get("turn_id") or ""),
                        "call_id": str(call.get("call_id") or "") or None,
                        **copy.deepcopy(assessment),
                        "classification": classification,
                    }
                )
            canonical_receipts = [
                item
                for item in call.get("canonical_integration_assessments") or []
                if isinstance(item, dict)
            ]
            complete_canonical_receipts = [
                item
                for item in canonical_receipts
                if _canonical_integration_receipt_complete(item)
            ]
            expected_canonical = _canonical_integration_expected_receipts(call)
            canonical_expected_receipts += expected_canonical
            canonical_missing_receipts += max(
                0,
                expected_canonical - len(canonical_receipts),
            )
            canonical_incomplete_receipts += (
                len(canonical_receipts) - len(complete_canonical_receipts)
            )
            canonical_complete_receipts += len(complete_canonical_receipts)
            for canonical_assessment in complete_canonical_receipts:
                assessment_id = str(
                    canonical_assessment.get("assessment_id") or ""
                )
                if assessment_id in canonical_assessment_ids:
                    canonical_duplicate_receipts += 1
                    continue
                canonical_assessment_ids.add(assessment_id)
                classification = str(
                    canonical_assessment.get("classification") or "indeterminado"
                )
                included = canonical_assessment.get("included_in_score") is True
                if classification not in {
                    "verdadeiro_positivo",
                    "verdadeiro_negativo",
                    "falso_positivo",
                    "falso_negativo",
                    "indeterminado",
                }:
                    classification = "indeterminado"
                if included:
                    canonical_assessment_counts[classification] += 1
                else:
                    canonical_assessment_counts["nao_pontuavel"] += 1
                canonical_assessments.append(
                    {
                        "turn_id": str(turn.get("turn_id") or ""),
                        "call_id": str(call.get("call_id") or "") or None,
                        **copy.deepcopy(canonical_assessment),
                        "classification": classification,
                    }
                )
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
    latency_values = [
        item["latency_seconds"]
        for item in deliveries
        if isinstance(item.get("latency_seconds"), (int, float))
    ]
    size_by_class: dict[str, dict[str, int | float]] = {}
    for turn_class in sorted({str(item["turn_class"]) for item in deliveries}):
        items = [item for item in deliveries if item["turn_class"] == turn_class]
        size_by_class[turn_class] = {
            "turnos": len(items),
            "palavras_total": sum(int(item["words"]) for item in items),
            "palavras_media": round(
                sum(int(item["words"]) for item in items) / len(items), 3
            ),
            "caracteres_total": sum(int(item["characters"]) for item in items),
        }
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
        "narrative_delivery": {
            "schema": 1,
            "turnos_esperados": n,
            "respostas_observadas": sum(item["response_present"] for item in deliveries),
            "recibos_observados": sum(item["receipt_present"] for item in deliveries),
            "entregas_correlacionadas": sum(item["correlated_delivery"] for item in deliveries),
            "rodapes_em_ultima_linha": sum(item["footer_correct"] for item in deliveries),
            "rodapes_ausentes_ou_fora_de_posicao": sum(
                item["response_present"] and not item["footer_correct"] for item in deliveries
            ),
            "turnos_com_mecanica_explicita": sum(item["mechanics_lines"] > 0 for item in deliveries),
            "linhas_mecanica": sum(int(item["mechanics_lines"]) for item in deliveries),
            "exposicao_procedimental_sem_ficcao": sum(item["procedural_only"] for item in deliveries),
            "tamanho_por_classe": size_by_class,
            "latencia": {
                "turnos_observaveis": len(latency_values),
                "media_segundos": round(sum(latency_values) / len(latency_values), 3)
                if latency_values
                else None,
                "max_segundos": round(max(latency_values), 3) if latency_values else None,
            },
            "retrabalho_explicito_no_turno_seguinte": _next_turn_rework_signals(turns),
            "auditoria_semantica": {
                "estado": "nao_realizada",
                "dimensoes": {
                    key: None
                    for key in (
                        "progressao_jogavel",
                        "densidade_proporcional",
                        "voz_e_dialogo",
                        "camadas_de_conhecimento",
                        "conclusao_aberta",
                    )
                },
            },
            "feedback_jogador": "nao_fornecido",
            "nota_literaria_automatica": None,
        },
        "rules_and_character_state": _rules_state_summary(turns),
        "sidequest_opportunity_decisions": {
            key: int(decisions[key])
            for key in ("oportunidade", "sem_oportunidade", "ausente", "conflito")
        },
        "sidequest_decision_prepare_calls": prepare_calls,
        "sidequest_decision_valid": int(valid_decisions),
        "sidequest_decision_violations": int(violations),
        "sidequest_decision_coverage": round(valid_decisions / prepare_calls, 6) if prepare_calls else 1.0,
        "task47_decision_gate_ok": violations == 0,
        "sidequest_opportunity_assessment": {
            "schema": OPPORTUNITY_DECISION_SCHEMA,
            "receipts": len(opportunity_assessments),
            "scoreable": sum(
                opportunity_assessment_counts[key]
                for key in (
                    "verdadeiro_positivo",
                    "verdadeiro_negativo",
                    "falso_positivo",
                    "falso_negativo",
                )
            ),
            "indeterminate": opportunity_assessment_counts["indeterminado"],
            "confusion_matrix": {
                key: int(opportunity_assessment_counts[key])
                for key in (
                    "verdadeiro_positivo",
                    "verdadeiro_negativo",
                    "falso_positivo",
                    "falso_negativo",
                )
            },
            "assessments": opportunity_assessments,
        },
        "canonical_quest_integration_assessment": {
            "schema": CANONICAL_INTEGRATION_ASSESSMENT_SCHEMA,
            "activity_units": int(canonical_expected_receipts),
            "receipts": int(canonical_complete_receipts),
            "unique_assessments": len(canonical_assessments),
            "duplicate_receipts": int(canonical_duplicate_receipts),
            "scoreable": sum(
                canonical_assessment_counts[key]
                for key in (
                    "verdadeiro_positivo",
                    "verdadeiro_negativo",
                    "falso_positivo",
                    "falso_negativo",
                )
            ),
            "non_scoreable": int(canonical_assessment_counts["nao_pontuavel"]),
            "indeterminate": int(canonical_assessment_counts["indeterminado"]),
            "missing_receipts": int(canonical_missing_receipts),
            "incomplete_receipts": int(canonical_incomplete_receipts),
            "coverage_complete": (
                canonical_missing_receipts == 0
                and canonical_incomplete_receipts == 0
            ),
            "confusion_matrix": {
                key: int(canonical_assessment_counts[key])
                for key in (
                    "verdadeiro_positivo",
                    "verdadeiro_negativo",
                    "falso_positivo",
                    "falso_negativo",
                )
            },
            "assessments": canonical_assessments,
        },
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
    "concurrent_adversarial_operations": ("operacao_resolvida",),
}

_PASSIVE_LEGACY_OUTPUT_MARKERS: dict[str, set[str]] = {
    # Referências em `fontes_lidas` e instruções do contrato não provam que a
    # subcapacidade foi consultada ou executada naquele turno.
    "world_local_incidents": {"narrador/mundo/incidentes/"},
    "persistent_world_conditions": {"condicoes-persistentes.yaml"},
    "concurrent_adversarial_operations": {"resolver_operacao_adversarial"},
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
        "call_ids_observed": [],
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
    call_id: str | None = None,
    call_ids: list[str] | None = None,
) -> None:
    signal = signals.setdefault((module_id, capability_id), _empty_signal())
    previous_effect = signal["effect_observed"]
    for observed_call_id in [call_id, *(call_ids or [])]:
        if observed_call_id and observed_call_id not in signal["call_ids_observed"]:
            signal["call_ids_observed"].append(observed_call_id)
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
    # Uma falha observável não pode ser apagada por outro sinal bem-sucedido da
    # mesma subcapacidade no turno. Estados intermediários devem usar None.
    if effect_observed is False:
        if previous_effect is not False and observed_result is not None:
            signal["observed_result"] = observed_result
        signal["effect_observed"] = False
    elif signal["effect_observed"] is None:
        signal["effect_observed"] = effect_observed
    if confidence == "alta" or signal["inference_confidence"] == "baixa":
        signal["inference_confidence"] = confidence


def _legacy_activation(alias: str, output_text: str, source: str) -> tuple[str, str | None, str | None, bool | None]:
    lower = output_text.casefold()
    if any(marker in lower for marker in _LEGACY_NEUTRAL_MARKERS.get(alias, ())):
        return "gate_neutro", "resultado_neutro", None, None
    if any(marker in lower for marker in _LEGACY_EFFECT_MARKERS.get(alias, ())):
        return "efeito", "efeito_observado", "efeito_materializado", True
    # O nome de um módulo em output pode ser projeção, contrato ou diagnóstico.
    # Sem marcador de efeito/neutralidade, ele prova somente consulta.
    return "consulta", "marcador_observado", None, None


def _legacy_signals(
    signals: dict[tuple[str, str], dict[str, Any]],
    calls: list[dict[str, Any]],
    aliases: dict[str, tuple[str, str]],
) -> list[dict[str, Any]]:
    non_modules: dict[str, dict[str, Any]] = {}
    typed_sidequest_decisions = {
        call.get("sidequest_decision")
        for call in calls
        if call.get("sidequest_decision")
        in {"oportunidade", "sem_oportunidade", "ausente", "conflito"}
    }
    sidequest_gate_is_negative = typed_sidequest_decisions == {"sem_oportunidade"}
    for call in calls:
        if call.get("command_executed") is False:
            continue
        output_text = str(call.get("output_text") or "")
        command_lower = str(call.get("command") or "").casefold()
        output_lower = output_text.casefold()
        facade_adversarial = _invocation(
            str(call.get("command") or ""), {"adversarial_operations.py"}
        ) is not None
        actual_npc_initiative = (
            _call_has_phase(call, "preparar")
            and (
                "--interlocutor" in command_lower
                or "iniciativa_elenco" in output_lower
            )
        )
        for source, key, marker_key in (
            ("comando", "command_systems", "command_markers"),
            ("output", "output_systems", "output_markers"),
        ):
            if source == "output" and call.get("orchestration_failure") is not None:
                continue
            for alias in sorted(call.get(key) or set()):
                sidequest_decision = call.get("sidequest_decision")
                # A decisão tipada do cronica é autoritativa. Marcadores v1 no
                # mesmo output apenas identificam a infraestrutura carregada e
                # não podem promover um gate negativo a ativação/autoria.
                if (
                    alias == "emergent_sidequest_opportunity"
                    and (
                        sidequest_decision
                        in {"oportunidade", "sem_oportunidade", "ausente", "conflito"}
                        or typed_sidequest_decisions
                    )
                ):
                    continue
                if (
                    alias == "emergent_sidequest_authoring"
                    and (
                        sidequest_decision == "sem_oportunidade"
                        or sidequest_gate_is_negative
                    )
                ):
                    continue
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
                if source == "output":
                    passive = _PASSIVE_LEGACY_OUTPUT_MARKERS.get(alias, set())
                    evidence_markers = [
                        marker for marker in evidence_markers if marker not in passive
                    ]
                    if not evidence_markers:
                        continue
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
                        call_id=str(call.get("call_id") or "") or None,
                    )
    return list(non_modules.values())


def _new_module_signals(
    signals: dict[tuple[str, str], dict[str, Any]], turn: dict[str, Any]
) -> None:
    calls = [
        call
        for call in turn.get("calls") or []
        if call.get("command_executed") is not False
    ]
    assistant_messages = list(turn.get("assistant_messages") or [])

    # RM-04: o hot path importa a fachada como ``cena_mundo``; por isso o
    # rollout observa ``cronica preparar`` em vez de uma CLI adicional. Os
    # gatilhos tipados provam a consulta. A preparação continua read-only e só
    # marcadores explícitos do concluir provam efeito material.
    for call in calls:
        command = str(call.get("command") or "")
        kinds = _spatial_prepare_kinds(command)
        if not kinds:
            continue
        output_text = str(call.get("output_text") or "")
        output_success = call.get("output_success")
        call_id = str(call.get("call_id") or "") or None
        for kind in kinds:
            activation, result, materialized, visible_projection = _spatial_prepare_result(
                kind, output_text, output_success
            )
            _add_signal(
                signals,
                "scene_world_projection",
                "local_incidents",
                source="comando",
                evidence=f"command:spatial_trigger_{kind}",
                eligibility="sim",
                activation=activation,
                observed_result=result,
                materialized_result=materialized,
                effect_observed=None,
                confidence="alta",
                call_id=call_id,
            )
            if visible_projection:
                _add_signal(
                    signals,
                    "scene_world_projection",
                    "local_incidents",
                    source="output",
                    evidence="output:spatial_projection_gate",
                    eligibility="sim",
                    activation=activation,
                    observed_result=result,
                    effect_observed=None,
                    confidence="alta",
                    call_id=call_id,
                )

            if kind == "permanencia_local":
                permanence = _top_level_output_section(
                    output_text, "permanencia_espacial"
                )
                reused = _output_bool(permanence, "reutilizado") if permanence else None
                continuity_activation = (
                    "efeito"
                    if reused is True
                    else "decisao"
                    if permanence
                    else "consulta"
                )
                _add_signal(
                    signals,
                    "scene_world_projection",
                    "spatial_continuity",
                    source="output" if permanence else "comando",
                    evidence=(
                        "output:spatial_reservation_reused"
                        if reused is True
                        else "output:spatial_reservation_created"
                        if permanence
                        else "command:spatial_continuity_requested"
                    ),
                    eligibility="sim",
                    activation=continuity_activation,
                    observed_result=(
                        "reserva_espacial_reutilizada"
                        if reused is True
                        else "reserva_espacial_criada"
                        if permanence
                        else "continuidade_espacial_encaminhada"
                    ),
                    materialized_result=(
                        "janela_espacial_preservada" if reused is True else None
                    ),
                    effect_observed=True if reused is True else None,
                    confidence="alta",
                    call_id=call_id,
                )

        active_conditions = re.search(
            r"(?im)^condicoes_persistentes_ativas\s*:\s*(\d+)?\s*$",
            output_text,
        )
        condition_gate = bool(
            re.search(
                r"(?im)^\s*-\s*tipo\s*:\s*condicoes_ambientais\s*$",
                output_text,
            )
        )
        if active_conditions or condition_gate:
            count = (
                int(active_conditions.group(1))
                if active_conditions and active_conditions.group(1) is not None
                else None
            )
            active = count is None or count > 0
            _add_signal(
                signals,
                "scene_world_projection",
                "persistent_conditions",
                source="output",
                evidence=(
                    "output:persistent_conditions_projected"
                    if active_conditions and active
                    else "output:persistent_conditions_gate"
                ),
                eligibility=(
                    "sim"
                    if active_conditions and active
                    else "nao"
                    if active_conditions
                    else "indeterminada"
                ),
                activation=(
                    "decisao"
                    if active_conditions and active
                    else "gate_neutro"
                    if active_conditions
                    else "consulta"
                ),
                observed_result=(
                    "condicoes_ativas_projetadas"
                    if active_conditions and active
                    else "sem_condicao_ativa"
                    if active_conditions
                    else "condicoes_persistentes_consultadas"
                ),
                effect_observed=None,
                confidence="alta",
                call_id=call_id,
            )

    # RM-06: proposta, compromisso e efeito são eventos diferentes do mesmo
    # módulo pai. Integridade é o contrato verificável; concorrência só é
    # promovida quando duas ou mais frentes são observáveis no recibo novo.
    for call in calls:
        command = str(call.get("command") or "")
        lower = " ".join(command.casefold().split())
        output_lower = str(call.get("output_text") or "").casefold()
        facade = _invocation(command, {"adversarial_operations.py"}) is not None
        legacy_integrity = _invocation(command, {"integridade_adversarial.py"}) is not None
        legacy_operations = _invocation(command, {"operacoes_concorrentes.py"}) is not None
        output_is_observation = call.get("category") not in {
            "read_search",
            "validation",
        }
        structured = output_is_observation and any(
            marker in output_lower
            for marker in (
                "schema_adversarial_operations",
                "schema_integridade_adversarial",
                "schema_preparacao_grupo_operacoes",
                "schema_grupo_operacoes",
                "grupo_operacoes_id",
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
            effect = None
        elif material_effect:
            activation = "efeito"
            result = "efeito_adversarial_observado"
            materialized = "efeito_adversarial_materializado"
            effect = True
        elif commitment:
            activation = "decisao"
            result = "operacao_adversarial_comprometida"
            materialized = None
            effect = True
        else:
            activation = "consulta"
            result = "contrato_adversarial_consultado"
            materialized = None
            effect = None

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
            call_id=str(call.get("call_id") or "") or None,
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
                call_id=str(call.get("call_id") or "") or None,
            )

    # RM-05: continuidade dirigida é distinta de iniciativa incidental. Os
    # sinais vêm do mesmo comando/output já observado; nunca interpretam prosa
    # como conhecimento, presença ou identidade confirmada.
    for call in calls:
        command = str(call.get("command") or "")
        lower = " ".join(command.casefold().split())
        output_lower = str(call.get("output_text") or "").casefold()
        context_invocation = _invocation(command, {"contexto.py"})
        directed_npc = bool(context_invocation and "npc" in context_invocation[1])
        facade = _invocation(
            command, {"npc_continuity_and_social_behavior.py"}
        ) is not None
        participant = _call_has_phase(call, "preparar") and "--participante" in lower
        interlocutor = _call_has_phase(call, "preparar") and "--interlocutor" in lower
        identity_operation = _invocation(command, {"identidades.py"}) is not None
        reputation_operation = _invocation(
            command, {"reputacao_publica.py"}
        ) is not None or (
            context_invocation is not None and "reputacao" in context_invocation[1]
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
                call_id=str(call.get("call_id") or "") or None,
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
                call_id=str(call.get("call_id") or "") or None,
            )

        output_is_observation = call.get("category") not in {
            "read_search",
            "validation",
        }
        has_initiative = bool(
            output_is_observation
            and
            "iniciativa_elenco" in output_lower
            and (_call_has_phase(call, "preparar") or facade)
        )
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
                effect_observed=True if presented else None,
                confidence="alta" if has_initiative else "media",
                call_id=str(call.get("call_id") or "") or None,
            )

        if has_initiative or (
            output_is_observation
            and any(
                marker in output_lower
                for marker in (
                    "dialogo_relacional",
                    "personalidade_decisoria",
                    "reconhecimento_identidade",
                )
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
                call_id=str(call.get("call_id") or "") or None,
            )

        persistence_observed = bool(
            output_is_observation
            and (
                re.search(r"fatos_sociais_persistidos\s*:\s*[1-9]", output_lower)
                or re.search(r'"fatos_sociais_persistidos"\s*:\s*[1-9]', output_lower)
            )
        )
        if output_is_observation and any(
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
                call_id=str(call.get("call_id") or "") or None,
            )

    # RM-07: toda demanda narrativa usa contexto, inclusive quando L0 basta e
    # não há chamada. Leitura, memória e separação de conhecimento continuam
    # sinais distintos e só o recibo pós-writer prova persistência.
    access_calls = []
    normalized_access = Counter(
        " ".join(str(call.get("command") or "").casefold().split())
        for call in calls
        if _is_routed_context_command(str(call.get("command") or ""))
        and not _core._is_help_command(str(call.get("command") or ""))
    )
    for call in calls:
        command = str(call.get("command") or "")
        lower = " ".join(command.casefold().split())
        output_lower = str(call.get("output_text") or "").casefold()
        context_invocation = _invocation(command, {"contexto.py"})
        name = str(call.get("name") or "")
        category = str(call.get("category") or "")
        routed = _is_routed_context_command(command) and not _core._is_help_command(command)
        raw = bool(
            category == "read_search"
            and not routed
            and not _core._is_help_command(command)
            and _core._looks_like_raw_read(f"{name} {command}")
        )
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
                effect_observed=observed not in {
                    "contexto_obsoleto",
                    "acesso_cru_sem_justificativa",
                    "leitura_redundante",
                    "aprofundamento_sem_justificativa_observavel",
                },
                confidence="alta",
                call_id=str(call.get("call_id") or "") or None,
            )

        context_operation = context_invocation[1] if context_invocation else []
        memory_command = bool(
            context_invocation
            and {"retomada", "cena"}.intersection(context_operation)
            or _invocation(command, {"memoria_cena.py", "sessoes.py"}) is not None
            or {"status", "iniciar"}.intersection(
                _session_lifecycle_operations(command)
            )
        )
        memory_context = memory_command or bool(
            routed and "memoria_cena" in output_lower
        )
        if memory_context:
            cold = bool(
                "retomada" in context_operation
                or _invocation(command, {"sessoes.py"}) is not None
                or {"status", "iniciar"}.intersection(
                    _session_lifecycle_operations(command)
                )
            )
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
                effect_observed=(
                    False
                    if stale_memory
                    else True
                    if no_transcript
                    else None
                ),
                confidence="alta" if no_transcript or "memoria_cena" in output_lower else "media",
                call_id=str(call.get("call_id") or "") or None,
            )

        memory_declared = _call_has_phase(call, "concluir") and bool(
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
                effect_observed=True if persisted else None,
                confidence="alta",
                call_id=str(call.get("call_id") or "") or None,
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
                effect_observed=True if separated_receipt else None,
                confidence="alta",
                call_id=str(call.get("call_id") or "") or None,
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
            effect_observed=True,
            confidence="media",
        )

    # RM-08: a correlação é inferida do par e do recibo emitido pelas chamadas
    # existentes. Falha transacional não é aproximada a nenhum domínio narrativo.
    turn_calls = _expanded_orchestration_calls(calls)
    lifecycle_calls = _expanded_session_lifecycle_calls(calls)
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
        successful_conclusions = [
            index
            for index, call in enumerate(turn_calls)
            if call["orchestration_phase"] == "concluir"
            and _successful_turn_conclusion(call)
        ]
        problem_indices = [
            index
            for index, call in enumerate(turn_calls)
            if call.get("orchestration_failure")
            or str((call.get("orchestration_receipt") or {}).get("state") or "").startswith(
                "bloqueado_"
            )
            or "bloqueada_pendencias_mundo"
            in str(call.get("output_text") or "").casefold()
            or "bloqueada_recuperacao_sessao"
            in str(call.get("output_text") or "").casefold()
        ]
        completed_cycle = bool(
            phase_counts["preparar"]
            and successful_conclusions
            and (
                not problem_indices
                or successful_conclusions[-1] > problem_indices[-1]
            )
        )
        successful_pair = exact_pair and completed_cycle
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

        if mismatched:
            result = "correlacao_de_ticket_divergente"
            activation = "decisao"
            effect = False
        elif completed_cycle:
            result = "ciclo_concluido" if successful_pair else "ciclo_concluido_apos_retry"
            activation = "efeito"
            effect = True
        elif failures:
            result = failures[-1]
            activation = "decisao"
            effect = False
        elif blocked:
            recovery = any(
                "recuperacao" in str((call.get("orchestration_receipt") or {}).get("state") or "")
                for call in turn_calls
            )
            result = "bloqueado_por_recovery" if recovery else "bloqueado_por_pendencia"
            activation = "gate_neutro"
            effect = None
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
                call_id=str(call.get("call_id") or "") or None,
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
            idempotence_failed = incomplete or any(
                receipt.get("exactly_once") is False
                or receipt.get("duplicate") is True
                for receipt in commit_receipts
            )
            outcome = (
                "commit_incompleto"
                if incomplete
                else "commit_duplicado_ou_sem_exatamente_uma_vez"
                if idempotence_failed
                else "retry_recuperado"
                if recovered and idempotent
                else "retry_desnecessario_sem_duplicacao"
                if replay
                else "commit_exatamente_uma_vez"
                if idempotent
                else "commit_sem_prova_exatamente_uma_vez"
            )
            _add_signal(
                signals,
                "turn_and_session_orchestration",
                "idempotent_commit",
                source="output",
                evidence="output:exactly_once_receipt",
                eligibility="sim",
                activation=(
                    "decisao"
                    if idempotence_failed
                    else "gate_neutro"
                    if replay
                    else "efeito"
                    if idempotent
                    else "consulta"
                ),
                observed_result=outcome,
                materialized_result="idempotencia_preservada" if idempotent else None,
                effect_observed=(
                    False
                    if idempotence_failed
                    else True
                    if idempotent and not replay
                    else None
                ),
                confidence="alta",
                call_ids=[
                    str(call.get("call_id") or "")
                    for call in turn_calls
                    if (call.get("orchestration_receipt") or {}).get("commit_result")
                    or (call.get("orchestration_receipt") or {}).get("incomplete") is True
                ],
            )

    for call in lifecycle_calls:
        operation = str(call["session_lifecycle_operation"])
        receipt = call.get("orchestration_receipt")
        operations = _call_session_lifecycle_operations(call)
        receipt_operation = (
            str(receipt.get("operation") or "")
            if isinstance(receipt, dict)
            else ""
        )
        outcome_attributable = len(operations) == 1 or receipt_operation == operation
        effect = None
        if operation != "status" and outcome_attributable:
            if call.get("output_success") is True:
                effect = True
            elif call.get("output_success") is False:
                effect = False
        for source, evidence in (
            ("comando", f"command:session_{operation}"),
            ("output", "output:versioned_session_receipt"),
        ):
            if source == "output" and (not receipt or receipt_operation != operation):
                continue
            _add_signal(
                signals,
                "turn_and_session_orchestration",
                "session_lifecycle",
                source=source,
                evidence=evidence,
                eligibility="sim",
                activation=(
                    "efeito"
                    if effect is True
                    else "decisao"
                    if effect is False
                    else "consulta"
                ),
                observed_result=f"session_{operation}",
                materialized_result=f"session_{operation}" if effect else None,
                effect_observed=effect,
                confidence="alta",
                call_id=str(call.get("call_id") or "") or None,
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

    # RM-09: estrutura é objetiva; adequação da prosa permanece N/D até
    # auditoria semântica e percepção humana explícitas.
    delivery = _delivery_observation(turn)
    if delivery["response_present"]:
        _add_signal(
            signals,
            "narrative_delivery",
            "narrative_density",
            source="resposta",
            evidence="response:size_observed_without_quality_judgment",
            eligibility="sim",
            activation="consulta",
            observed_result="densidade_nao_avaliada",
            effect_observed=None,
            confidence="alta",
        )
        closure_result = (
            "entrega_correlacionada"
            if delivery["correlated_delivery"] and delivery["footer_correct"]
            else "rodape_ausente_ou_fora_de_posicao"
            if not delivery["footer_correct"]
            else "entrega_legada_observada"
        )
        _add_signal(
            signals,
            "narrative_delivery",
            "visible_closure",
            source="resposta",
            evidence=(
                "response:canonical_footer_is_last_line"
                if delivery["footer_correct"]
                else "response:canonical_footer_missing_or_misplaced"
            ),
            eligibility="sim",
            activation="efeito",
            observed_result=closure_result,
            materialized_result="entrega_visivel" if delivery["footer_correct"] else None,
            effect_observed=bool(delivery["footer_correct"]),
            confidence="alta",
        )
        if delivery["receipt_present"]:
            _add_signal(
                signals,
                "narrative_delivery",
                "visible_closure",
                source="output",
                evidence="output:narrative_delivery_receipt",
                eligibility="sim",
                activation="efeito",
                observed_result=closure_result,
                materialized_result="entrega_visivel" if delivery["footer_correct"] else None,
                effect_observed=bool(delivery["footer_correct"]),
                confidence="alta",
            )
        if delivery["mechanics_lines"]:
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

    # RM-10: consulta, alvo prévio, rolagem e commit são evidências separadas.
    # Estado genérico (local, relações, mundo) não ativa este módulo.
    for call in calls:
        command = str(call.get("command") or "")
        lower = command.casefold()
        output_text = str(call.get("output_text") or "")
        output_lower = output_text.casefold()
        receipt = call.get("rules_state_receipt")

        if call.get("schema_discovery"):
            _add_signal(
                signals,
                "rules_and_character_state",
                "rules_resolution",
                source="comando",
                evidence="command:mechanical_schema_rediscovery",
                activation="consulta",
                observed_result="redescoberta_assinatura",
                effect_observed=False,
                confidence="alta",
                call_id=str(call.get("call_id") or "") or None,
            )
        elif _is_rule_query(command):
            _add_signal(
                signals,
                "rules_and_character_state",
                "rules_resolution",
                source="comando",
                evidence="command:rule_query",
                activation="consulta",
                observed_result="regra_consultada",
                effect_observed=None,
                confidence="alta",
                call_id=str(call.get("call_id") or "") or None,
            )

        roll = _dice_observation(call)
        if roll is not None:
            if roll["target_applicable"]:
                predefined = roll["target_predefined"] is True
                _add_signal(
                    signals,
                    "rules_and_character_state",
                    "rules_resolution",
                    source="comando",
                    evidence=(
                        f"command:{roll['target']}_predefined"
                        if predefined
                        else f"command:{roll['target']}_missing"
                    ),
                    eligibility="sim",
                    activation="decisao",
                    observed_result=(
                        "parametros_predefinidos"
                        if predefined
                        else "rolagem_sem_alvo_predefinido"
                    ),
                    effect_observed=predefined,
                    confidence="alta",
                    call_id=str(call.get("call_id") or "") or None,
                )
            succeeded = bool(roll["success"])
            _add_signal(
                signals,
                "rules_and_character_state",
                "roll_execution",
                source="comando",
                evidence="command:dice_batch" if roll["batch"] else "command:dice",
                eligibility="sim" if roll["target_applicable"] else "indeterminada",
                activation="efeito" if succeeded else "decisao",
                observed_result="rolagem_resolvida" if succeeded else "indeterminado",
                materialized_result="rolagem_resolvida" if succeeded else None,
                effect_observed=succeeded,
                confidence="alta",
                call_id=str(call.get("call_id") or "") or None,
            )
            if roll["output_seen"]:
                _add_signal(
                    signals,
                    "rules_and_character_state",
                    "roll_execution",
                    source="output",
                    evidence="output:dice_result",
                    eligibility="sim" if roll["target_applicable"] else "indeterminada",
                    activation="efeito" if succeeded else "decisao",
                    observed_result="rolagem_resolvida" if succeeded else "indeterminado",
                    materialized_result="rolagem_resolvida" if succeeded else None,
                    effect_observed=succeeded,
                    confidence="alta",
                    call_id=str(call.get("call_id") or "") or None,
                )

        precommitted = "--gasto-focus" in lower or (
            "--mecanica-json" in lower
            and any(
                marker in lower
                for marker in ("gasto_recurso", "recursos.focus", '"recurso":"focus"', '"recurso": "focus"')
            )
        )
        categories = _character_state_categories(command)
        if precommitted and not isinstance(receipt, dict):
            _add_signal(
                signals,
                "rules_and_character_state",
                "character_time_state",
                source="ticket",
                evidence="ticket:mechanical_obligation_precommitted",
                eligibility="sim",
                activation="decisao",
                observed_result="indeterminado",
                effect_observed=None,
                confidence="alta",
                call_id=str(call.get("call_id") or "") or None,
            )

        if isinstance(receipt, dict):
            replay = receipt.get("new_effect") is False
            effect = True if receipt.get("new_effect") is True else None
            if int(receipt.get("rules") or 0) or int(receipt.get("obligations") or 0):
                _add_signal(
                    signals,
                    "rules_and_character_state",
                    "rules_resolution",
                    source="output",
                    evidence="output:rules_state_contract_receipt",
                    eligibility="sim",
                    activation=(
                        "gate_neutro"
                        if replay
                        else "efeito"
                        if effect is True
                        else "consulta"
                    ),
                    observed_result=(
                        "replay_sem_duplicacao"
                        if replay
                        else "parametros_predefinidos"
                        if effect is True
                        else "contrato_sem_prova_de_efeito"
                    ),
                    materialized_result=(
                        "contrato_mecanico_validado" if effect is True else None
                    ),
                    effect_observed=None if replay else effect,
                    confidence="alta",
                    call_id=str(call.get("call_id") or "") or None,
                )
            if int(receipt.get("d20_obligations") or 0):
                resolved = (
                    int(receipt.get("resolutions") or 0)
                    >= int(receipt.get("d20_obligations") or 0)
                )
                _add_signal(
                    signals,
                    "rules_and_character_state",
                    "roll_execution",
                    source="output",
                    evidence="output:roll_integrity_receipt",
                    eligibility="sim",
                    activation="gate_neutro" if replay else "efeito" if resolved else "decisao",
                    observed_result="replay_sem_duplicacao" if replay else "rolagem_resolvida" if resolved else "indeterminado",
                    materialized_result="rolagem_resolvida" if resolved and not replay else None,
                    effect_observed=None if replay else resolved,
                    confidence="alta",
                    call_id=str(call.get("call_id") or "") or None,
                )
            if int(receipt.get("relevant_deltas") or 0) or int(
                receipt.get("resource_obligations") or 0
            ):
                _add_signal(
                    signals,
                    "rules_and_character_state",
                    "character_time_state",
                    source="output",
                    evidence="output:rules_state_commit_receipt",
                    eligibility="sim",
                    activation=(
                        "gate_neutro"
                        if replay
                        else "efeito"
                        if effect is True
                        else "consulta"
                    ),
                    observed_result=(
                        "replay_sem_duplicacao"
                        if replay
                        else "estado_commitado"
                        if effect is True
                        else "estado_sem_prova_de_efeito"
                    ),
                    materialized_result="estado_commitado" if effect is True else None,
                    effect_observed=None if replay else effect,
                    confidence="alta",
                    call_id=str(call.get("call_id") or "") or None,
                )
        elif categories:
            committed = (
                bool(
                    {"concluir", "registrar"}.intersection(
                        _call_orchestration_phases(call)
                    )
                )
                and call.get("output_success") is True
            )
            _add_signal(
                signals,
                "rules_and_character_state",
                "character_time_state",
                source="ticket",
                evidence="ticket:legacy_character_or_time_delta",
                eligibility="sim",
                activation="efeito" if committed else "decisao",
                observed_result="estado_commitado" if committed else "indeterminado",
                materialized_result="estado_commitado" if committed else None,
                # A menção de um delta antes do writer é uma intenção, não uma
                # falha. Só o concluir/registrar bem-sucedido prova o efeito.
                effect_observed=True if committed else None,
                confidence="media",
                call_id=str(call.get("call_id") or "") or None,
            )

        if any(
            marker in output_lower
            for marker in (
                "diverge da primitiva",
                "exige obrigação",
                "exige obrigacao",
                "ticket mecânico obsoleto",
                "ticket mecanico obsoleto",
                "resultado mecânico diverge",
                "resultado mecanico diverge",
            )
        ):
            _add_signal(
                signals,
                "rules_and_character_state",
                "rules_resolution",
                source="output",
                evidence="output:mechanical_guardrail_block",
                eligibility="sim",
                activation="decisao",
                observed_result="guardrail_bloqueou",
                effect_observed=False,
                confidence="alta",
                call_id=str(call.get("call_id") or "") or None,
            )

    # A flag é uma declaração obrigatória, não a verdade de elegibilidade. O
    # recibo 2.0.0/4.0.0 é independente da classificação escolhida no comando e
    # prevalece quando consegue provar os predicados duros.
    for call in calls:
        decision = call.get("sidequest_decision")
        if decision not in {"oportunidade", "sem_oportunidade", "ausente", "conflito"}:
            continue
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
            eligibility="indeterminada",
            activation=activation,
            observed_result=f"declaracao_{decision}",
            # Decidir o gate não é, por si, efeito autoral. Um efeito só existe
            # quando autoria ou oferta materializa resultado observável.
            effect_observed=None,
            confidence="alta",
            call_id=str(call.get("call_id") or "") or None,
        )
        assessment = call.get("opportunity_assessment")
        if not isinstance(assessment, dict):
            continue
        expected = assessment.get("expected_result")
        effective = assessment.get("effective_decision")
        eligibility = (
            "sim"
            if expected == "elegivel"
            else "nao"
            if expected == "nao_elegivel"
            else "indeterminada"
        )
        _add_signal(
            signals,
            "sidequest_authoring",
            "opportunity_gate",
            source="output",
            evidence="output:objective_sidequest_opportunity_assessment",
            eligibility=eligibility,
            activation="decisao" if effective == "oportunidade" else "gate_neutro",
            observed_result=str(assessment.get("classification") or "indeterminado"),
            effect_observed=None,
            confidence="alta",
            call_id=str(call.get("call_id") or "") or None,
        )
        gate_signal = signals[("sidequest_authoring", "opportunity_gate")]
        gate_signal["observed_result"] = str(
            assessment.get("classification") or "indeterminado"
        )

    # A integração canônica 2.0 é observada pelo recibo por missão, inclusive
    # quando a operação ocorre dentro do lifecycle unificado. Heurística de
    # comando permanece apenas como conferência de completude.
    for call in calls:
        canonical_receipts = [
            item
            for item in call.get("canonical_integration_assessments") or []
            if isinstance(item, dict)
        ]
        complete_canonical_receipts = [
            item
            for item in canonical_receipts
            if _canonical_integration_receipt_complete(item)
        ]
        expected_receipts = _canonical_integration_expected_receipts(call)
        missing_receipts = max(0, expected_receipts - len(canonical_receipts))
        incomplete_receipts = len(canonical_receipts) - len(complete_canonical_receipts)
        for capability_id in {
            str(item.get("capability_id") or "sidequest_to_canon_bridge")
            for item in complete_canonical_receipts
        }:
            capability_receipts = [
                item
                for item in complete_canonical_receipts
                if str(item.get("capability_id") or "sidequest_to_canon_bridge")
                == capability_id
            ]
            scoreable = [
                item
                for item in capability_receipts
                if item.get("included_in_score") is True
            ]
            classifications = {
                str(item.get("classification") or "indeterminado")
                for item in scoreable
            }
            eligible = any(
                item.get("classification")
                in {"verdadeiro_positivo", "falso_negativo"}
                for item in scoreable
            )
            active = bool(
                classifications.intersection(
                    {"verdadeiro_positivo", "falso_positivo"}
                )
            )
            incorrect = bool(
                classifications.intersection(
                    {"falso_positivo", "falso_negativo"}
                )
            )
            _add_signal(
                signals,
                "canonical_quest_integration",
                capability_id,
                source="output",
                evidence="output:canonical_integration_assessment_receipt",
                eligibility="sim" if eligible else "nao",
                activation=(
                    "efeito"
                    if active
                    else "ausente"
                    if scoreable
                    else "consulta"
                ),
                observed_result=(
                    "integracao_incorreta"
                    if incorrect
                    else "integracao_avaliada"
                ),
                effect_observed=(False if incorrect else True if scoreable else None),
                confidence="alta",
                call_id=str(call.get("call_id") or "") or None,
            )
        if missing_receipts or incomplete_receipts:
            invocations = _command_invocations(str(call.get("command") or ""))
            missing_capability = (
                "canon_to_quest_opportunity"
                if any(
                    program == "canonical_quest_integration.py"
                    and args[:1] == ["oferecer"]
                    for program, args in invocations
                )
                else "sidequest_to_canon_bridge"
            )
            _add_signal(
                signals,
                "canonical_quest_integration",
                missing_capability,
                source="output",
                evidence="output:canonical_integration_receipt_missing",
                eligibility="indeterminada",
                activation="ausente",
                observed_result="falha_instrumentacao",
                effect_observed=False,
                confidence="alta",
                call_id=str(call.get("call_id") or "") or None,
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
    report: dict[str, Any], narration: list[dict[str, Any]], catalog: dict[str, Any],
    all_turns: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    module_by_id, aliases, module_order, capability_order = _catalog_indexes(catalog)
    events: list[dict[str, Any]] = []
    non_module_observations: list[dict[str, Any]] = []
    module_totals: dict[str, dict[str, int]] = {}
    total_narrative_cost = {key: 0 for key in _turn_cost({})}

    interaction_candidates = all_turns if all_turns is not None else narration
    interactions = [
        observation
        for index, turn in enumerate(interaction_candidates, 1)
        for observation in [_interaction_observation(turn, index)]
        if observation["receipt_present"] or observation["response_present"]
    ]
    interaction_by_turn = {item["turn_id"]: item for item in interactions}
    for item, turn in zip(report.get("per_narration_turn") or [], narration):
        signals: dict[tuple[str, str], dict[str, Any]] = {}
        non_modules = _legacy_signals(signals, list(turn.get("calls") or []), aliases)
        _new_module_signals(signals, turn)
        ordinal = int(item.get("ordinal") or len(events) + 1)
        turn_id = str(turn.get("turn_id") or f"ordinal-{ordinal}")
        interaction = interaction_by_turn.get(turn_id) or _interaction_observation(turn, ordinal)
        for observation in non_modules:
            non_module_observations.append(
                {
                    "session_id": (report.get("source") or {}).get("session_id"),
                    "turn_id": turn_id,
                    "turn_ordinal": ordinal,
                    "interaction_id": interaction.get("interaction_id"),
                    "interaction_ref": interaction.get("interaction_ref"),
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
                    "interaction_id": interaction.get("interaction_id"),
                    "interaction_ref": interaction.get("interaction_ref"),
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
        "interactions": interactions,
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
        "semantic_audits": [],
        "player_feedback": [],
    }


def apply_modular_adjudications(
    ledger: dict[str, Any], adjudications: dict[str, Any] | list[dict[str, Any]]
) -> dict[str, Any]:
    """Aplica correções sem apagar nenhuma observação do detector."""

    result = copy.deepcopy(ledger)
    result.setdefault("corrections", [])
    result.setdefault("semantic_audits", [])
    result.setdefault("player_feedback", [])
    corrections = adjudications.get("corrections", []) if isinstance(adjudications, dict) else adjudications
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

    if not isinstance(adjudications, dict):
        return result

    semantic_dimensions = {
        "progressao_jogavel",
        "densidade_proporcional",
        "voz_e_dialogo",
        "camadas_de_conhecimento",
        "conclusao_aberta",
    }
    semantic_states = {"adequado", "inadequado", "indeterminado", "nao_aplicavel"}
    guardrail_ids = {"player_agency", "knowledge_secrecy", "roll_integrity"}
    guardrail_states = {"ok", "violado", "indeterminado", "nao_aplicavel"}
    audits = adjudications.get("semantic_audits", [])
    if not isinstance(audits, list):
        raise RolloutError("adjudicações modulares: semantic_audits precisa ser lista")
    for index, audit in enumerate(audits, 1):
        if not isinstance(audit, dict):
            raise RolloutError(f"auditoria semântica {index} não é objeto")
        event_id = str(audit.get("event_id") or "")
        event = by_id.get(event_id)
        if event is None or event.get("module_id") != "narrative_delivery":
            raise RolloutError(
                f"auditoria semântica aponta para entrega narrativa inexistente: {event_id}"
            )
        evaluator = str(audit.get("evaluator") or "").strip()
        if not evaluator:
            raise RolloutError(f"auditoria semântica {event_id} exige evaluator")
        dimensions = audit.get("dimensions")
        guardrails = audit.get("guardrails")
        evidence = audit.get("evidence")
        if not isinstance(dimensions, dict) or set(dimensions) != semantic_dimensions:
            raise RolloutError(f"auditoria semântica {event_id}: dimensions incompletas")
        if any(state not in semantic_states for state in dimensions.values()):
            raise RolloutError(f"auditoria semântica {event_id}: estado semântico inválido")
        if not isinstance(guardrails, dict) or set(guardrails) != guardrail_ids:
            raise RolloutError(f"auditoria semântica {event_id}: guardrails incompletos")
        if any(state not in guardrail_states for state in guardrails.values()):
            raise RolloutError(f"auditoria semântica {event_id}: estado de guardrail inválido")
        if not isinstance(evidence, list) or any(not isinstance(item, str) for item in evidence):
            raise RolloutError(f"auditoria semântica {event_id}: evidence precisa ser lista")
        result["semantic_audits"].append(
            {
                "event_id": event_id,
                "evaluator": evaluator,
                "dimensions": copy.deepcopy(dimensions),
                "guardrails": copy.deepcopy(guardrails),
                "evidence": list(evidence),
                "automatic_literary_score": None,
                "guardrails_compensable": False,
            }
        )

    feedback_items = adjudications.get("player_feedback", [])
    if not isinstance(feedback_items, list):
        raise RolloutError("adjudicações modulares: player_feedback precisa ser lista")
    for index, feedback in enumerate(feedback_items, 1):
        if not isinstance(feedback, dict):
            raise RolloutError(f"feedback do jogador {index} não é objeto")
        interaction_ref = str(feedback.get("interaction_ref") or "")
        known_refs = {
            str(item.get("interaction_ref"))
            for item in result.get("interactions") or []
            if item.get("interaction_ref")
        }
        if interaction_ref not in known_refs:
            raise RolloutError(f"feedback aponta para interação inexistente: {interaction_ref}")
        original_text = str(feedback.get("original_text") or "").strip()
        if not original_text:
            raise RolloutError(f"feedback {interaction_ref}: original_text é obrigatório")
        perceived_type = feedback.get("perceived_type")
        allowed_types = {
            "boa_ativacao", "oportunidade_percebida", "sobreativacao_percebida",
            "ativacao_inadequada", "efeito_incorreto", "timing", "continuidade",
            "possivel_guardrail",
        }
        if perceived_type not in allowed_types:
            raise RolloutError(f"feedback {interaction_ref}: perceived_type inválido")
        adjudication = feedback.get("adjudication") or {"state": "pendente", "reason": None}
        if adjudication.get("state") not in {
            "pendente", "confirmada", "parcial", "nao_confirmada", "indeterminada"
        }:
            raise RolloutError(f"feedback {interaction_ref}: adjudication inválida")
        result["player_feedback"].append(
            {
                **copy.deepcopy(feedback),
                "feedback_id": str(feedback.get("feedback_id") or f"feedback-importado-{index}"),
                "recorded_at": str(feedback.get("recorded_at") or "desconhecido"),
                "expectation": feedback.get("expectation"),
                "observation": feedback.get("observation"),
                "perceived_impact": feedback.get("perceived_impact"),
                "player_module_id": feedback.get("player_module_id"),
                "player_capability_id": feedback.get("player_capability_id"),
                "system_suggestion": feedback.get("system_suggestion"),
                "adjudication": copy.deepcopy(adjudication),
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
        "objective_assessment": all_summary["sidequest_opportunity_assessment"],
        "regra": (
            "todo cronica preparar declara se percebeu âncora nova, mas a declaração "
            "não prova elegibilidade; somente recibo objetivo ou adjudicação entra na "
            "matriz de confusão, e casos indeterminados ficam fora da nota"
        ),
    }
    report["canonical_quest_integration_gate"] = {
        **all_summary["canonical_quest_integration_assessment"],
        "ok": all_summary["canonical_quest_integration_assessment"][
            "coverage_complete"
        ],
        "regra": (
            "toda atividade observável de sidequest exige recibo canônico por missão; "
            "ausência de recibo é falha de instrumentação e nunca produz N/D"
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
    coverage_gates = _module_coverage_gates(ordered)
    report["module_coverage_gates"] = coverage_gates
    for item, turn in zip(report.get("per_narration_turn") or [], narration):
        item.update(_observation_summary([turn]))
    ledger = _build_modular_ledger(report, narration, catalog, ordered)
    ledger["module_coverage_gates"] = copy.deepcopy(coverage_gates)
    if modular_adjudications is not None:
        ledger = apply_modular_adjudications(ledger, modular_adjudications)
    report["modular_ledger_v2"] = ledger
    inferred = report.get("measurement", {}).get("observational_inference")
    if isinstance(inferred, list):
        for label in (
            "preferred cronica orchestration phases inferred from command lines",
            "narrative-system attribution inferred from command and tool-output markers",
            "Task47 declaration inferred from cronica preparar flags; objective sidequest eligibility comes from a versioned receipt or adjudication",
            "canonical quest integration comes from per-mission receipts; sidequest activity without coverage is an instrumentation failure, never N/D",
            "eleven module facades use schema-1 fail-closed coverage receipts; expected activity without a complete receipt is an instrumentation failure and N/D requires zero activity",
            "NV-14 justified calm and missing-module coverage inferred from structured liveness output",
            "modules-v2 capability ledger inferred from command, output, ticket and response signals",
            "modules-v2 parent cost allocated once per module; capability cost is exposure only",
            "RM-08 orchestration receipt, retry, correlation and phase duration inferred from existing call outputs",
            "RM-08 control cost separated from domain cost without claiming marginal causality",
            "RM-09 delivery receipt correlated with the final visible response and canonical footer position",
            "RM-09 response size and latency measured structurally without an automatic literary score",
            "RM-09 semantic audit, player perception and critical guardrails stored as separate evidence layers",
            "RM-10 rule queries, predefined targets, rolls and character/time commits inferred as separate evidence",
            "RM-10 versioned receipt correlates prewriter validation and exactly-once state effects without generic state attribution",
            "RM-10 mechanical corrections and CLI rediscovery remain observations rather than automatic quality judgments",
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
    delivery = narr.get("narrative_delivery") or {}
    rules_state = narr.get("rules_and_character_state") or {}
    rolls = rules_state.get("rolagens") or {}
    contracts = rules_state.get("contratos") or {}
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
        (
            "RM-09 entrega: "
            f"respostas={delivery.get('respostas_observadas', 0)} | "
            f"recibos={delivery.get('recibos_observados', 0)} | "
            f"correlacionadas={delivery.get('entregas_correlacionadas', 0)} | "
            f"rodapés irregulares={delivery.get('rodapes_ausentes_ou_fora_de_posicao', 0)} | "
            "qualidade semântica=N/D sem adjudicação"
        ),
        (
            "RM-10 regras/estado: "
            f"consultas={((rules_state.get('consultas_regra') or {}).get('total', 0))} | "
            f"rolagens={rolls.get('chamadas', 0)} | "
            f"alvo prévio={rolls.get('alvo_predefinido', 0)}/{rolls.get('alvo_aplicavel', 0)} | "
            f"recibos={contracts.get('recibos_observados', 0)} | "
            f"redescobertas={rules_state.get('redescobertas_schema_cli', 0)} | "
            f"correções do jogador={rules_state.get('correcoes_mecanicas_jogador', 0)}"
        ),
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
