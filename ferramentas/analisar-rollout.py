#!/usr/bin/env python3
"""Analisa rollout JSONL nativo do Codex sem alterar o repositório.

A ferramenta é deliberadamente pós-hoc: ela lê o rollout depois da sessão e
escreve apenas em stdout. Métricas de tokens/turnos vêm dos registros nativos;
classificações de ferramentas/caminhos são inferências observacionais e ficam
marcadas como tal no relatório.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 2
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
ACCESS_LEVEL_RE = re.compile(r"(?:^|[\s\"'])nivel(?:\"|')?\s*[:=]\s*[\"']?(L4T|L[1-4])", re.I | re.M)
LEVEL_ORDER = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4, "L4T": 5, "UNCLASSIFIED": 6}

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
READ_MARKERS = (
    "contexto.py",
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
    "apply_patch",
    "turno.py registrar",
    "checkpoint.py cena",
    "checkpoint.py sessao",
    "checkpoint.py recuperar",
    "consolidar.py cena",
    "consolidar.py sessao",
    "consolidar.py recuperar",
    "gerar-runtime.py",
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
        "write_paths": [],
        "canonical_write_paths": [],
        "transcript_read_calls": 0,
        "access_levels": [],
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


def _classify_tool(name: str, raw_input: str) -> str:
    lower = f" {name} {_extract_command(raw_input)} ".lower()
    if name == "apply_patch" or "*** begin patch" in lower:
        return "write"
    if any(marker in lower for marker in DICE_MARKERS):
        return "dice"
    if any(marker in lower for marker in VALIDATION_MARKERS):
        return "validation"
    if any(marker in lower for marker in WRITE_MARKERS):
        # gerar-runtime --check já foi capturado por validation acima.
        return "write"
    if re.search(r"(?:^|\s)(?:cat|printf|echo)\s+.*(?:>|>>)", lower):
        return "write"
    if any(marker in lower for marker in READ_MARKERS):
        return "read_search"
    if re.search(r"(?:^|[;&|\s])cat\s+[^>|]+", lower):
        return "read_search"
    return "other"


def _access_level_from_command(command: str) -> str | None:
    lower = command.lower()
    if "contexto.py" not in lower:
        return None
    if " --transcricoes" in lower:
        return "L4T"
    if " --historico" in lower:
        return "L4"
    if re.search(r"\bcontexto\.py\b.*\bbuscar\b", lower):
        return "L3"
    if re.search(r"\bcontexto\.py\b.*\bsessao\s+(?!atual\b|current\b)\d+", lower):
        return "L4"
    if re.search(r"\bcontexto\.py\b.*\bstatus\b", lower):
        return "L1"
    if re.search(r"\bcontexto\.py\b.*\b(?:retomada|cena|sessao|npc|relacao|conhecimento|regra)\b", lower):
        return "L2"
    return None


def _access_levels_from_output(text: str) -> list[str]:
    return [level.upper() for level in ACCESS_LEVEL_RE.findall(text)]


def _infer_write_paths(name: str, raw_input: str) -> list[str]:
    command = _extract_command(raw_input)
    lower = command.lower()
    paths = [
        path for path in _paths(raw_input)
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


def _turn_access_level(turn: dict[str, Any]) -> str:
    levels = [str(level).upper() for level in turn.get("access_levels") or [] if str(level).upper() in LEVEL_ORDER]
    if levels:
        return max(levels, key=lambda level: LEVEL_ORDER[level])
    if int((turn.get("tool_categories") or {}).get("read_search", 0)):
        return "UNCLASSIFIED"
    return "L0"


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
    write_paths: list[str] = []
    canonical_paths: list[str] = []
    patch_files: list[str] = []
    for turn in selected:
        tool_counts.update(turn["tool_calls"])
        categories.update(turn["tool_categories"])
        read_paths.extend(turn["read_paths"])
        write_paths.extend(turn["write_paths"])
        canonical_paths.extend(turn["canonical_write_paths"])
        patch_files.extend(turn["patch_files"])

    input_values = [int(u.get("input_tokens") or 0) for u in token_events]
    input_tokens = sum(input_values)
    cached = sum(int(u.get("cached_input_tokens") or 0) for u in token_events)
    output = sum(int(u.get("output_tokens") or 0) for u in token_events)
    reasoning = sum(int(u.get("reasoning_output_tokens") or 0) for u in token_events)
    n = len(selected)
    calls = sum(tool_counts.values())
    write_touches = len(write_paths)
    canonical_touches = len(canonical_paths)
    transcript_reads = sum(int(turn.get("transcript_read_calls") or 0) for turn in selected)
    access = Counter(_turn_access_level(turn) for turn in selected)
    no_read_turns = sum(1 for turn in selected if not int(turn["tool_categories"].get("read_search", 0)))

    return {
        "turns": n,
        "inference_events": len(token_events),
        "avg_inference_events_per_turn": round(len(token_events) / n, 3) if n else 0,
        "tool_calls": calls,
        "avg_tool_calls_per_turn": round(calls / n, 3) if n else 0,
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
        "write_target_touches": write_touches,
        "avg_write_target_touches_per_turn": round(write_touches / n, 3) if n else 0,
        "unique_write_targets": len(set(write_paths)),
        "canonical_write_target_touches": canonical_touches,
        "avg_canonical_write_target_touches_per_turn": round(canonical_touches / n, 3) if n else 0,
        "transcript_read_calls": transcript_reads,
        "turns_without_read_search": no_read_turns,
        "fraction_turns_without_read_search": round(no_read_turns / n, 6) if n else 0,
        "max_access_level_by_turn": dict(sorted(access.items(), key=lambda kv: LEVEL_ORDER.get(kv[0], 99))),
        "fraction_turns_l0_l2": round(
            sum(count for level, count in access.items() if level in {"L0", "L1", "L2"}) / n,
            6,
        ) if n else 0,
    }


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
                    turn["tool_calls"][name] += 1
                    turn["tool_categories"][category] += 1
                    turn["patch_payload_bytes"] += _patch_payload_size(name, raw_input)

                    patch_files = PATCH_FILE_RE.findall(raw_input)
                    turn["patch_files"].extend(patch_files)
                    mentioned = [
                        path for path in _paths(raw_input)
                        if not (path.startswith("ferramentas/") and path.endswith(".py"))
                    ]
                    if category == "read_search":
                        turn["read_paths"].extend(mentioned)
                        if "--transcricoes" in command.lower() or any("transcricao.md" in p for p in mentioned):
                            turn["transcript_read_calls"] += 1
                    if category == "write":
                        write_paths = _infer_write_paths(name, raw_input)
                        turn["write_paths"].extend(write_paths)
                        turn["canonical_write_paths"].extend(p for p in write_paths if _is_canonical_write(p))
                    level = _access_level_from_command(command)
                    if level:
                        turn["access_levels"].append(level)
                    if "turno.py registrar" in command.lower():
                        turn["narration_signal_tool"] = True

                if turn is not None and item_type in {"function_call_output", "custom_tool_call_output"}:
                    output_text = _tool_output(payload)
                    turn["tool_output_bytes"] += len(output_text.encode("utf-8"))
                    turn["access_levels"].extend(_access_levels_from_output(output_text))

            if record_type == "event_msg" and payload.get("type") == "token_count":
                if current_turn:
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
                "path mentions",
                "write targets inferred from known repo tools",
                "access-level classification when not present in tool output",
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
            "also_detected_by": "tool call containing ferramentas/turno.py registrar",
        },
    }


def _human(report: dict[str, Any]) -> str:
    all_ = report["all_turns"]
    narr = report["narration_turns"]
    cats = narr.get("tool_categories") or {}
    access = narr.get("max_access_level_by_turn") or {}
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
        f"Categorias: read/search={cats.get('read_search', 0)}, write={cats.get('write', 0)}, dice={cats.get('dice', 0)}, validation={cats.get('validation', 0)}, other={cats.get('other', 0)}",
        f"Escritas observadas/inferidas: {narr['write_target_touches']} alvos | {narr['avg_write_target_touches_per_turn']} alvos/turno | canônicas={narr['canonical_write_target_touches']}",
        f"Leituras de transcrição: {narr['transcript_read_calls']}",
        f"Turnos sem read/search: {narr['fraction_turns_without_read_search']:.1%}",
        f"Nível máximo por turno: {access}",
        f"Turnos L0–L2: {narr['fraction_turns_l0_l2']:.1%}",
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
