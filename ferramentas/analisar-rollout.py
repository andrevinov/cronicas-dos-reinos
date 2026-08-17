#!/usr/bin/env python3
"""Analisa rollout JSONL nativo do Codex sem alterar o repositório.

A ferramenta é deliberadamente pós-hoc: ela lê o rollout depois da sessão e
escreve apenas em stdout. Contadores nativos vêm do próprio rollout; categorias,
caminhos e sucesso operacional de ferramentas são inferências observacionais.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 3
LEGACY_NARRATION_PROMPT = "Escrevi minhas ações na sessão 3. Pode avançar na história?"
DEFAULT_NARRATION_RE = re.compile(
    r"(?is)(escrevi.{0,80}aç(?:ão|ões).{0,80}sess[aã]o.{0,100}avanç|"
    r"pode\s+avançar\s+na\s+hist[oó]ria|avance.{0,60}hist[oó]ria|"
    r"continu(?:e|ar).{0,80}(?:hist[oó]ria|campanha))"
)
PATCH_FILE_RE = re.compile(r"^\*\*\* (?:Update|Add|Delete) File: (.+)$", re.MULTILINE)
PATH_RE = re.compile(
    r"(?<![\w./-])((?:runtime|estado|sessoes|personagens|narrador|regras|cenario|narracao|"
    r"ferramentas|docs|baseline)/[^\s'\"`,;|()<>]+)"
)
ACCESS_LEVEL_RE = re.compile(
    r"(?:^|[\s\"'])nivel(?:\"|')?\s*[:=]\s*[\"']?(L4T|L[1-4])", re.I | re.M
)
EXIT_CODE_RES = (
    re.compile(r"process exited with code\s+(-?\d+)", re.I),
    re.compile(r"exit(?:_|\s+)code[\"']?\s*[:=]\s*[\"']?(-?\d+)", re.I),
    re.compile(r"returncode[\"']?\s*[:=]\s*[\"']?(-?\d+)", re.I),
)
BASE_LEVEL_ORDER = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4, "L4T": 5}
TEMP_TURN_FILE = ".turno-temporario.json"

CANONICAL_WRITE_PREFIXES = (
    "estado/",
    "personagens/jogador/ficha.yaml",
    "personagens/jogador/conhecimento/",
    "narrador/",
)
DICE_MARKERS = ("rolar-dados.py", "rolar-lote.py")
VALIDATION_MARKERS = (
    "pytest",
    "unittest",
    "verificar-integridade.py",
    "migrar-estado-atual.py --check",
    "migrar-memorias-fragmentadas.py --check",
    "reindexar-conhecimento.py --check",
    "gerar-runtime.py --check",
    "turno.py check",
    "checkpoint.py check",
    "consolidar.py check",
    "git status",
    "git diff",
)
RAW_READ_MARKERS = (
    " rg ",
    "rg -",
    "grep ",
    "sed -n",
    "tail ",
    "head ",
    "find ",
    "ls ",
    "git show",
    "git log",
)
WRITE_MARKERS = (
    "turno.py registrar",
    "checkpoint.py cena",
    "checkpoint.py sessao",
    "checkpoint.py recuperar",
    "consolidar.py cena",
    "consolidar.py sessao",
    "consolidar.py recuperar",
    "gerar-runtime.py",
    "sessoes.py iniciar",
    "sessoes.py bootstrap",
    "sessoes.py reindexar",
    "git commit",
    "git add",
)


class RolloutError(ValueError):
    pass


def _new_turn() -> dict[str, Any]:
    return {
        "user_messages": [],
        "token_events": [],
        "tool_calls": Counter(),
        "tool_categories": Counter(),
        "tool_output_bytes": 0,
        "patch_payload_bytes": 0,
        "patch_files": [],
        "read_paths": [],
        "temporary_turn_file_calls": 0,
        "access_levels": [],
        "call_records": [],
        "calls_by_id": {},
        "narration_signal_tool": False,
    }


def _message_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in payload.get("content") or []:
        if isinstance(item, dict):
            parts.append(str(item.get("text") or item.get("output_text") or ""))
        elif isinstance(item, str):
            parts.append(item)
    return "".join(parts)


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)


def _tool_input(payload: dict[str, Any]) -> str:
    for key in ("arguments", "input", "params"):
        if key in payload:
            return _stringify(payload.get(key))
    return ""


def _tool_output(payload: dict[str, Any]) -> str:
    for key in ("output", "content", "result"):
        if key in payload:
            return _stringify(payload.get(key))
    return ""


def _call_id(payload: dict[str, Any]) -> str | None:
    value = payload.get("call_id") or payload.get("tool_call_id")
    return str(value) if value not in (None, "") else None


def _extract_command(raw: str) -> str:
    """Tenta obter o comando real sem depender de um formato específico de tool."""
    text = raw.strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(parsed, dict):
        for key in ("cmd", "command", "script", "input"):
            value = parsed.get(key)
            if isinstance(value, str):
                return value
            if isinstance(value, list):
                return " ".join(str(part) for part in value)
    return text


def _paths(text: str) -> list[str]:
    cleaned: list[str] = []
    for match in PATH_RE.findall(text):
        path = match.rstrip(".:)]}")
        if path and path not in cleaned:
            cleaned.append(path)
    return cleaned


def _is_canonical_write(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix) for prefix in CANONICAL_WRITE_PREFIXES)


def _uses_temporary_turn_file(raw_input: str) -> bool:
    return TEMP_TURN_FILE in raw_input.lower()


def _is_help_command(command: str) -> bool:
    return bool(re.search(r"(?:^|\s)(?:--help|-h)(?:\s|$)", command))


def _is_routed_context(command: str) -> bool:
    lower = command.lower()
    return "ferramentas/contexto.py" in lower or "ferramentas/contexto-buscar-muitos.py" in lower


def _is_raw_read(name: str, command: str, category: str) -> bool:
    if category != "read_search" or _is_routed_context(command) or _is_help_command(command):
        return False
    lower = f" {name} {command} ".lower()
    if any(marker in lower for marker in RAW_READ_MARKERS):
        return True
    return bool(re.search(r"(?:^|[;&|\s])cat\s+[^>|]+", lower))


def _is_schema_discovery(command: str, mentioned_paths: list[str]) -> bool:
    if _is_help_command(command):
        return True
    return any(path.startswith("ferramentas/") and path.endswith(".py") for path in mentioned_paths)


def _classify_tool(name: str, raw_input: str) -> str:
    command = _extract_command(raw_input)
    lower = f" {name} {command} ".lower()
    if name == "apply_patch" or "*** begin patch" in lower:
        return "write"
    if any(marker in lower for marker in DICE_MARKERS):
        return "dice"
    if any(marker in lower for marker in VALIDATION_MARKERS):
        return "validation"
    if _is_help_command(command):
        return "read_search"
    if any(marker in lower for marker in WRITE_MARKERS):
        return "write"
    if re.search(r"(?:^|\s)(?:cat|printf|echo)\s+.*(?:>|>>)", lower):
        return "write"
    if _is_routed_context(command) or any(marker in lower for marker in RAW_READ_MARKERS):
        return "read_search"
    if re.search(r"(?:^|[;&|\s])cat\s+[^>|]+", lower):
        return "read_search"
    return "other"


def _access_level_from_command(command: str) -> str | None:
    lower = command.lower()
    if not _is_routed_context(command) or _is_help_command(command):
        return None
    if " --transcricoes" in lower:
        return "L4T"
    if " --historico" in lower:
        return "L4"
    if "contexto-buscar-muitos.py" in lower:
        return "L3"
    if re.search(r"\bcontexto\.py\b.*\bbuscar\b", lower):
        return "L3"
    if re.search(r"\bcontexto\.py\b.*\bsessao\s+(?!atual\b|current\b)\d+", lower):
        return "L4"
    if re.search(r"\bcontexto\.py\b.*\bstatus\b", lower):
        return "L1"
    if re.search(
        r"\bcontexto\.py\b.*\b(?:retomada|cena|sessao|npc|local|relacao|recurso|conhecimento|regra)\b",
        lower,
    ):
        return "L2"
    return None


def _access_levels_from_output(text: str) -> list[str]:
    return [level.upper() for level in ACCESS_LEVEL_RE.findall(text)]


def _infer_write_paths(name: str, raw_input: str) -> list[str]:
    command = _extract_command(raw_input)
    lower = command.lower()
    if _is_help_command(command):
        return []
    paths = [
        path
        for path in _paths(raw_input)
        if not (path.startswith("ferramentas/") and path.endswith(".py"))
    ]
    if name == "apply_patch" or "*** begin patch" in raw_input.lower():
        patch_paths = PATCH_FILE_RE.findall(raw_input)
        if patch_paths:
            paths = list(dict.fromkeys(patch_paths))
    if "turno.py registrar" in lower:
        paths.extend(["sessoes/NNN/transcricao.md", "runtime/eventos-pendentes.jsonl"])
    if "gerar-runtime.py" in lower and "--check" not in lower:
        paths.extend(["runtime/contexto.yaml", "runtime/cena.yaml"])
    return list(dict.fromkeys(paths))


def _patch_payload_size(name: str, raw_input: str) -> int:
    if name == "apply_patch" or "*** begin patch" in raw_input.lower():
        return len(raw_input.encode("utf-8"))
    return 0


def _tool_success(payload: dict[str, Any], output_text: str) -> bool | None:
    for key in ("exit_code", "returncode"):
        value = payload.get(key)
        if isinstance(value, int):
            return value == 0
    success = payload.get("success")
    if isinstance(success, bool):
        return success
    status = str(payload.get("status") or "").lower()
    if status in {"success", "succeeded", "completed", "ok"}:
        return True
    if status in {"failure", "failed", "error", "cancelled", "canceled"}:
        return False

    for pattern in EXIT_CODE_RES:
        match = pattern.search(output_text)
        if match:
            return int(match.group(1)) == 0

    stripped = output_text.strip()
    lower = stripped.lower()
    if not stripped:
        return None
    if re.search(r"(?:^|[,{\s])[\"']?is_error[\"']?\s*:\s*true", lower):
        return False
    if lower.startswith(("falha", "failed", "error", "invalid patch")):
        return False
    if stripped.startswith(("OK", "Done!", "Success", "SUCCESS")):
        return True
    return None


def _attempts_transcript_read(command: str, mentioned_paths: list[str]) -> bool:
    lower = command.lower()
    return "--transcricoes" in lower or any("transcricao.md" in path for path in mentioned_paths)


def _is_turn_register(command: str) -> bool:
    return "turno.py registrar" in command.lower() and not _is_help_command(command)


def _access_sort_key(label: str) -> tuple[int, int, str]:
    if label == "RAW":
        return (6, 1, label)
    if label == "UNCLASSIFIED":
        return (7, 0, label)
    raw = label.endswith("+RAW")
    base = label[:-4] if raw else label
    return (BASE_LEVEL_ORDER.get(base, 8), 1 if raw else 0, label)


def _turn_access_level(turn: dict[str, Any]) -> str:
    levels = [
        str(level).upper()
        for level in turn.get("access_levels") or []
        if str(level).upper() in BASE_LEVEL_ORDER
    ]
    base = max(levels, key=lambda level: BASE_LEVEL_ORDER[level]) if levels else None
    calls = turn.get("call_records") or []
    raw = any(bool(call.get("raw_read")) for call in calls)
    any_read = bool(int((turn.get("tool_categories") or {}).get("read_search", 0)))
    if raw:
        return f"{base}+RAW" if base else "RAW"
    if base:
        return base
    return "UNCLASSIFIED" if any_read else "L0"


def _is_narration_turn(turn: dict[str, Any], narration_re: re.Pattern[str]) -> bool:
    if turn.get("narration_signal_tool"):
        return True
    for message in turn.get("user_messages") or []:
        stripped = str(message).strip()
        if stripped == LEGACY_NARRATION_PROMPT or narration_re.search(stripped):
            return True
    return False


def _percentile(values: list[int], p: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * p)))
    return ordered[index]


def _summarize(selected: list[dict[str, Any]]) -> dict[str, Any]:
    token_events = [usage for turn in selected for usage in turn["token_events"]]
    tool_counts: Counter[str] = Counter()
    categories: Counter[str] = Counter()
    read_paths: list[str] = []
    patch_files: list[str] = []
    calls: list[dict[str, Any]] = []
    for turn in selected:
        tool_counts.update(turn["tool_calls"])
        categories.update(turn["tool_categories"])
        read_paths.extend(turn["read_paths"])
        patch_files.extend(turn["patch_files"])
        calls.extend(turn.get("call_records") or [])

    write_calls = [call for call in calls if call.get("category") == "write"]
    successful_writes = [call for call in write_calls if call.get("success") is True]
    failed_writes = [call for call in write_calls if call.get("success") is False]
    unknown_writes = [call for call in write_calls if call.get("success") is None]
    attempted_write_paths = [path for call in write_calls for path in call.get("write_paths", [])]
    write_paths = [path for call in successful_writes for path in call.get("write_paths", [])]
    canonical_paths = [path for path in write_paths if _is_canonical_write(path)]

    input_values = [int(u.get("input_tokens") or 0) for u in token_events]
    input_tokens = sum(input_values)
    cached = sum(int(u.get("cached_input_tokens") or 0) for u in token_events)
    output = sum(int(u.get("output_tokens") or 0) for u in token_events)
    reasoning = sum(int(u.get("reasoning_output_tokens") or 0) for u in token_events)
    n = len(selected)
    total_calls = sum(tool_counts.values())
    transcript_attempts = sum(bool(call.get("transcript_read")) for call in calls)
    transcript_reads = sum(
        bool(call.get("transcript_read")) and call.get("success") is True for call in calls
    )
    routed_calls = sum(bool(call.get("routed_context")) for call in calls)
    raw_calls = sum(bool(call.get("raw_read")) for call in calls)
    schema_calls = sum(bool(call.get("schema_discovery")) for call in calls)
    raw_turns = sum(1 for turn in selected if any(call.get("raw_read") for call in turn.get("call_records", [])))
    temporary_calls = sum(int(turn.get("temporary_turn_file_calls") or 0) for turn in selected)
    temporary_turns = sum(1 for turn in selected if int(turn.get("temporary_turn_file_calls") or 0))
    access = Counter(_turn_access_level(turn) for turn in selected)
    no_read_turns = sum(1 for turn in selected if not int(turn["tool_categories"].get("read_search", 0)))
    clean_l0_l2 = sum(count for level, count in access.items() if level in {"L0", "L1", "L2"})

    return {
        "turns": n,
        "inference_events": len(token_events),
        "avg_inference_events_per_turn": round(len(token_events) / n, 3) if n else 0,
        "tool_calls": total_calls,
        "avg_tool_calls_per_turn": round(total_calls / n, 3) if n else 0,
        "tool_calls_by_name": dict(sorted(tool_counts.items())),
        "tool_categories": dict(sorted(categories.items())),
        "input_tokens": input_tokens,
        "cached_input_tokens": cached,
        "approx_uncached_input_tokens": max(0, input_tokens - cached),
        "cached_fraction": round(cached / input_tokens, 6) if input_tokens else 0,
        "output_tokens": output,
        "reasoning_output_tokens": reasoning,
        "avg_input_tokens_per_inference": round(input_tokens / len(token_events), 3) if token_events else 0,
        "peak_input_tokens": max(input_values) if input_values else 0,
        "p95_input_tokens": _percentile(input_values, 0.95) or 0,
        "tool_output_bytes": sum(int(turn.get("tool_output_bytes") or 0) for turn in selected),
        "avg_tool_output_bytes_per_turn": round(
            sum(int(turn.get("tool_output_bytes") or 0) for turn in selected) / n, 3
        ) if n else 0,
        "patch_payload_bytes": sum(int(turn.get("patch_payload_bytes") or 0) for turn in selected),
        "apply_patch_file_operations": len(patch_files),
        "unique_files_touched_by_apply_patch": len(set(patch_files)),
        "read_path_mentions": len(read_paths),
        "unique_read_paths": len(set(read_paths)),
        "routed_context_calls": routed_calls,
        "avg_routed_context_calls_per_turn": round(routed_calls / n, 3) if n else 0,
        "raw_read_calls": raw_calls,
        "avg_raw_read_calls_per_turn": round(raw_calls / n, 3) if n else 0,
        "schema_discovery_calls": schema_calls,
        "avg_schema_discovery_calls_per_turn": round(schema_calls / n, 3) if n else 0,
        "turns_with_raw_read": raw_turns,
        "fraction_turns_with_raw_read": round(raw_turns / n, 6) if n else 0,
        "attempted_write_calls": len(write_calls),
        "successful_write_calls": len(successful_writes),
        "failed_write_calls": len(failed_writes),
        "unknown_write_calls": len(unknown_writes),
        "attempted_write_target_touches": len(attempted_write_paths),
        "avg_attempted_write_target_touches_per_turn": round(len(attempted_write_paths) / n, 3) if n else 0,
        "write_target_touches": len(write_paths),
        "avg_write_target_touches_per_turn": round(len(write_paths) / n, 3) if n else 0,
        "unique_write_targets": len(set(write_paths)),
        "canonical_write_target_touches": len(canonical_paths),
        "avg_canonical_write_target_touches_per_turn": round(len(canonical_paths) / n, 3) if n else 0,
        "attempted_transcript_read_calls": transcript_attempts,
        "transcript_read_calls": transcript_reads,
        "violations": {
            "temporary_turn_file_calls": temporary_calls,
            "turns_with_temporary_turn_file": temporary_turns,
        },
        "fraction_turns_without_temporary_turn_file": round((n - temporary_turns) / n, 6) if n else 0,
        "turns_without_read_search": no_read_turns,
        "fraction_turns_without_read_search": round(no_read_turns / n, 6) if n else 0,
        "max_access_level_by_turn": dict(sorted(access.items(), key=lambda kv: _access_sort_key(kv[0]))),
        "fraction_turns_l0_l2": round(clean_l0_l2 / n, 6) if n else 0,
    }


def _match_output_call(turn: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any] | None:
    cid = _call_id(payload)
    if cid and cid in turn["calls_by_id"]:
        call = turn["call_records"][turn["calls_by_id"][cid]]
        if call.get("success") is None and not call.get("output_seen"):
            return call
    for call in turn["call_records"]:
        if not call.get("output_seen"):
            return call
    return None


def analyze(path: Path, narration_regex: str | None = None) -> dict[str, Any]:
    if not path.is_file():
        raise RolloutError(f"rollout não encontrado: {path}")
    narration_re = re.compile(narration_regex, re.I | re.S) if narration_regex else DEFAULT_NARRATION_RE
    turns: dict[str, dict[str, Any]] = {}
    turn_order: list[str] = []
    current_turn: str | None = None
    compactions = 0
    record_types: Counter[str] = Counter()
    agents_chars: list[int] = []
    session_meta: dict[str, Any] = {}
    models: Counter[str] = Counter()

    def ensure_turn(turn_id: str) -> dict[str, Any]:
        if turn_id not in turns:
            turns[turn_id] = _new_turn()
            turn_order.append(turn_id)
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
                raise RolloutError(f"registro {line_no} não é objeto JSON")

            record_type = str(record.get("type") or "<sem-tipo>")
            payload = record.get("payload") or {}
            if not isinstance(payload, dict):
                payload = {}
            record_types[record_type] += 1

            if record_type == "session_meta":
                session_meta = {
                    "session_id": payload.get("session_id") or payload.get("id"),
                    "cli_version": payload.get("cli_version"),
                    "cwd": payload.get("cwd"),
                    "model_provider": payload.get("model_provider"),
                    "context_window": payload.get("context_window"),
                }
            if record_type == "event_msg" and payload.get("type") == "task_started":
                current_turn = str(payload.get("turn_id") or "") or current_turn
                if current_turn:
                    ensure_turn(current_turn)
            if record_type == "turn_context":
                current_turn = str(payload.get("turn_id") or "") or current_turn
                if current_turn:
                    ensure_turn(current_turn)
                model = payload.get("model") or payload.get("model_name")
                if model:
                    models[str(model)] += 1
            if record_type == "world_state":
                state = payload.get("state") or {}
                text = ((state.get("agents_md") or {}).get("text")) if isinstance(state, dict) else None
                if isinstance(text, str):
                    agents_chars.append(len(text))
            if record_type == "compacted":
                compactions += 1

            if record_type == "response_item":
                metadata = payload.get("internal_chat_message_metadata_passthrough") or {}
                turn_id = str(metadata.get("turn_id") or "") if isinstance(metadata, dict) else ""
                turn_id = turn_id or current_turn
                turn = ensure_turn(turn_id) if turn_id else None
                item_type = payload.get("type")

                if turn is not None and item_type == "message" and payload.get("role") == "user":
                    text = _message_text(payload)
                    if text and not text.startswith("# AGENTS.md instructions"):
                        turn["user_messages"].append(text)

                if turn is not None and item_type in {"function_call", "custom_tool_call"}:
                    name = str(payload.get("name") or "<sem-nome>")
                    raw_input = _tool_input(payload)
                    command = _extract_command(raw_input)
                    category = _classify_tool(name, raw_input)
                    mentioned = [
                        path
                        for path in _paths(raw_input)
                        if not (path.startswith("ferramentas/") and path.endswith(".py"))
                    ]
                    mentioned_all = _paths(raw_input)
                    cid = _call_id(payload)
                    call = {
                        "call_id": cid,
                        "name": name,
                        "command": command,
                        "category": category,
                        "routed_context": _is_routed_context(command) and not _is_help_command(command),
                        "raw_read": _is_raw_read(name, command, category),
                        "schema_discovery": _is_schema_discovery(command, mentioned_all),
                        "transcript_read": _attempts_transcript_read(command, mentioned),
                        "write_paths": _infer_write_paths(name, raw_input) if category == "write" else [],
                        "success": None,
                        "output_seen": False,
                    }
                    index = len(turn["call_records"])
                    turn["call_records"].append(call)
                    if cid:
                        turn["calls_by_id"][cid] = index

                    turn["tool_calls"][name] += 1
                    turn["tool_categories"][category] += 1
                    turn["patch_payload_bytes"] += _patch_payload_size(name, raw_input)
                    if _uses_temporary_turn_file(raw_input):
                        turn["temporary_turn_file_calls"] += 1
                    turn["patch_files"].extend(PATCH_FILE_RE.findall(raw_input))
                    if category == "read_search":
                        turn["read_paths"].extend(mentioned)
                    level = _access_level_from_command(command)
                    if level:
                        turn["access_levels"].append(level)
                    if _is_turn_register(command):
                        turn["narration_signal_tool"] = True

                if turn is not None and item_type in {"function_call_output", "custom_tool_call_output"}:
                    output_text = _tool_output(payload)
                    turn["tool_output_bytes"] += len(output_text.encode("utf-8"))
                    matched = _match_output_call(turn, payload)
                    if matched is not None:
                        matched["success"] = _tool_success(payload, output_text)
                        matched["output_seen"] = True
                        if matched.get("routed_context"):
                            turn["access_levels"].extend(_access_levels_from_output(output_text))
                    else:
                        turn["access_levels"].extend(_access_levels_from_output(output_text))

            if record_type == "event_msg" and payload.get("type") == "token_count" and current_turn:
                turn = ensure_turn(current_turn)
                usage = ((payload.get("info") or {}).get("last_token_usage") or {})
                if isinstance(usage, dict):
                    turn["token_events"].append(usage)

    ordered_turns = [turns[turn_id] for turn_id in turn_order]
    narration_turns = [turn for turn in ordered_turns if _is_narration_turn(turn, narration_re)]
    per_narration: list[dict[str, Any]] = []
    for ordinal, turn in enumerate(narration_turns, 1):
        item = _summarize([turn])
        item["ordinal"] = ordinal
        item["access_level"] = _turn_access_level(turn)
        item["user_excerpt"] = (turn.get("user_messages") or [""])[-1][:240]
        per_narration.append(item)

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": "codex_rollout_telemetry",
        "measurement": {
            "mode": "post_hoc",
            "writes_during_analysis": False,
            "native_exact": [
                "token usage fields",
                "inference event count",
                "tool call count",
                "compaction count",
            ],
            "observational_inference": [
                "tool categories",
                "routed context vs raw reads",
                "schema/help discovery",
                "path mentions and inferred write targets",
                "tool success correlated by call_id when available, FIFO fallback otherwise",
                "temporary turn-file use inferred from tool input",
                "access-level classification and +RAW contamination marker",
            ],
            "billing_warning": "Token counters describe rollout traffic; they are not a billing/quota formula.",
        },
        "source": {
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            **session_meta,
            "models_observed": dict(sorted(models.items())),
        },
        "records": dict(sorted(record_types.items())),
        "compactions": compactions,
        "agents_md": {
            "world_state_occurrences": len(agents_chars),
            "chars_first": agents_chars[0] if agents_chars else None,
            "chars_max": max(agents_chars) if agents_chars else None,
        },
        "all_turns": _summarize(ordered_turns),
        "narration_turns": _summarize(narration_turns),
        "per_narration_turn": per_narration,
        "narration_detection": {
            "legacy_prompt": LEGACY_NARRATION_PROMPT,
            "custom_regex": narration_regex,
            "also_detected_by": "successful or attempted turno.py registrar command (excluding --help)",
        },
    }


def _human(report: dict[str, Any]) -> str:
    all_ = report["all_turns"]
    narr = report["narration_turns"]
    cats = narr.get("tool_categories") or {}
    access = narr.get("max_access_level_by_turn") or {}
    violations = narr.get("violations") or {}
    temporary_calls = int(violations.get("temporary_turn_file_calls") or 0)
    temporary_turns = int(violations.get("turns_with_temporary_turn_file") or 0)
    temp_status = "OK" if temporary_calls == 0 else "VIOLAÇÃO"
    lines = [
        f"Rollout: {report['source'].get('filename')}",
        f"Sessão Codex: {report['source'].get('session_id')}",
        f"Turnos: {all_['turns']} | inferências: {all_['inference_events']} | ferramentas: {all_['tool_calls']}",
        f"Compactações: {report['compactions']}",
        "",
        "NARRAÇÃO",
        f"Turnos: {narr['turns']}",
        f"Inferências/turno: {narr['avg_inference_events_per_turn']}",
        f"Ferramentas/turno: {narr['avg_tool_calls_per_turn']}",
        f"Input total: {narr['input_tokens']} | por inferência: {narr['avg_input_tokens_per_inference']} | pico: {narr['peak_input_tokens']}",
        f"Cache: {narr['cached_fraction']:.1%} | não-cache aprox.: {narr['approx_uncached_input_tokens']}",
        f"Tool output: {narr['tool_output_bytes']} bytes | {narr['avg_tool_output_bytes_per_turn']} bytes/turno",
        f"Categorias (tentativas): read/search={cats.get('read_search', 0)}, write={cats.get('write', 0)}, dice={cats.get('dice', 0)}, validation={cats.get('validation', 0)}, other={cats.get('other', 0)}",
        f"Leitura: contexto roteado={narr['routed_context_calls']} | crua={narr['raw_read_calls']} | schema/help={narr['schema_discovery_calls']}",
        f"Escritas: tentadas={narr['attempted_write_calls']} | concluídas={narr['successful_write_calls']} | falhas={narr['failed_write_calls']} | desconhecidas={narr['unknown_write_calls']}",
        f"Alvos escritos concluídos: {narr['write_target_touches']} | {narr['avg_write_target_touches_per_turn']} alvos/turno | tentados={narr['attempted_write_target_touches']} | canônicos concluídos={narr['canonical_write_target_touches']}",
        f"Leituras de transcrição concluídas: {narr['transcript_read_calls']} | tentadas={narr['attempted_transcript_read_calls']}",
        f"Arquivo temporário de turno: {temp_status} | {TEMP_TURN_FILE} em {temporary_calls} chamada(s), {temporary_turns} turno(s)",
        f"Turnos com leitura crua: {narr['fraction_turns_with_raw_read']:.1%}",
        f"Turnos sem read/search: {narr['fraction_turns_without_read_search']:.1%}",
        f"Nível máximo por turno: {access}",
        f"Turnos L0–L2 limpos: {narr['fraction_turns_l0_l2']:.1%}",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rollout", type=Path, help="arquivo rollout-*.jsonl")
    parser.add_argument("--json", action="store_true", help="imprime JSON completo")
    parser.add_argument(
        "--narration-regex",
        help="regex adicional/substitutiva para reconhecer turnos narrativos pela mensagem do usuário",
    )
    args = parser.parse_args()
    try:
        report = analyze(args.rollout, args.narration_regex)
    except (OSError, RolloutError, re.error) as exc:
        print(f"FALHA DE TELEMETRIA — {exc}")
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(_human(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
