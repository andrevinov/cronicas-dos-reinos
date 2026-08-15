#!/usr/bin/env python3
"""Analisa um rollout JSONL do Codex sem alterar o repositório."""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

NARRATION_PROMPT = "Escrevi minhas ações na sessão 3. Pode avançar na história?"
PATCH_FILE_RE = re.compile(r"^\*\*\* (?:Update|Add|Delete) File: (.+)$", re.MULTILINE)


def _new_turn() -> dict[str, Any]:
    return {"user_messages": [], "token_events": [], "tool_calls": Counter(), "patch_files": []}


def _message_text(payload: dict[str, Any]) -> str:
    parts = []
    for item in payload.get("content") or []:
        if isinstance(item, dict):
            parts.append(item.get("text") or "")
    return "".join(parts)


def analyze(path: Path) -> dict[str, Any]:
    turns: dict[str, dict[str, Any]] = {}
    current_turn: str | None = None
    compactions = 0
    record_types: Counter[str] = Counter()
    agents_chars: list[int] = []
    session_meta: dict[str, Any] = {}

    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SystemExit(f"JSON inválido na linha {line_no}: {exc}") from exc

            record_type = record.get("type", "<sem-tipo>")
            payload = record.get("payload") or {}
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
                current_turn = payload.get("turn_id")
                if current_turn:
                    turns.setdefault(current_turn, _new_turn())

            if record_type == "turn_context":
                current_turn = payload.get("turn_id") or current_turn
                if current_turn:
                    turns.setdefault(current_turn, _new_turn())

            if record_type == "world_state":
                state = payload.get("state") or {}
                text = ((state.get("agents_md") or {}).get("text"))
                if isinstance(text, str):
                    agents_chars.append(len(text))

            if record_type == "compacted":
                compactions += 1

            if record_type == "response_item":
                metadata = payload.get("internal_chat_message_metadata_passthrough") or {}
                turn_id = metadata.get("turn_id") or current_turn
                if turn_id:
                    turns.setdefault(turn_id, _new_turn())

                if turn_id and payload.get("type") == "message" and payload.get("role") == "user":
                    text = _message_text(payload)
                    if text and not text.startswith("# AGENTS.md instructions"):
                        turns[turn_id]["user_messages"].append(text)

                if turn_id and payload.get("type") in {"function_call", "custom_tool_call"}:
                    name = payload.get("name") or "<sem-nome>"
                    turns[turn_id]["tool_calls"][name] += 1
                    if name == "apply_patch":
                        patch = payload.get("input") or payload.get("arguments") or ""
                        turns[turn_id]["patch_files"].extend(PATCH_FILE_RE.findall(str(patch)))

            if record_type == "event_msg" and payload.get("type") == "token_count":
                if current_turn:
                    turns.setdefault(current_turn, _new_turn())
                    usage = ((payload.get("info") or {}).get("last_token_usage") or {})
                    turns[current_turn]["token_events"].append(usage)

    def summarize(selected: list[dict[str, Any]]) -> dict[str, Any]:
        token_events = [u for turn in selected for u in turn["token_events"]]
        tool_counts: Counter[str] = Counter()
        for turn in selected:
            tool_counts.update(turn["tool_calls"])
        input_tokens = sum(int(u.get("input_tokens") or 0) for u in token_events)
        cached = sum(int(u.get("cached_input_tokens") or 0) for u in token_events)
        output = sum(int(u.get("output_tokens") or 0) for u in token_events)
        reasoning = sum(int(u.get("reasoning_output_tokens") or 0) for u in token_events)
        patch_ops = [p for turn in selected for p in turn["patch_files"]]
        n = len(selected)
        return {
            "turns": n,
            "inference_events": len(token_events),
            "avg_inference_events_per_turn": round(len(token_events) / n, 3) if n else 0,
            "tool_calls": sum(tool_counts.values()),
            "avg_tool_calls_per_turn": round(sum(tool_counts.values()) / n, 3) if n else 0,
            "tool_calls_by_name": dict(sorted(tool_counts.items())),
            "input_tokens": input_tokens,
            "cached_input_tokens": cached,
            "approx_uncached_input_tokens": max(0, input_tokens - cached),
            "cached_fraction": round(cached / input_tokens, 6) if input_tokens else 0,
            "output_tokens": output,
            "reasoning_output_tokens": reasoning,
            "apply_patch_file_operations": len(patch_ops),
            "unique_files_touched_by_apply_patch": len(set(patch_ops)),
        }

    all_turns = list(turns.values())
    narration_turns = [
        turn
        for turn in all_turns
        if any(msg.strip() == NARRATION_PROMPT for msg in turn["user_messages"])
    ]

    per_narration = []
    for idx, turn in enumerate(narration_turns, 1):
        summary = summarize([turn])
        summary["ordinal"] = idx
        per_narration.append(summary)

    return {
        "source": {
            "filename": path.name,
            "size_bytes": path.stat().st_size,
            **session_meta,
        },
        "records": dict(sorted(record_types.items())),
        "compactions": compactions,
        "agents_md": {
            "world_state_occurrences": len(agents_chars),
            "chars_first": agents_chars[0] if agents_chars else None,
            "chars_max": max(agents_chars) if agents_chars else None,
        },
        "all_turns": summarize(all_turns),
        "narration_turns": summarize(narration_turns),
        "per_narration_turn": per_narration,
        "narration_prompt": NARRATION_PROMPT,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rollout", type=Path, help="arquivo rollout-*.jsonl")
    parser.add_argument("--json", action="store_true", help="imprime JSON completo")
    args = parser.parse_args()
    report = analyze(args.rollout)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        all_ = report["all_turns"]
        narr = report["narration_turns"]
        print(f"Sessão: {report['source'].get('session_id')}")
        print(f"Turnos: {all_['turns']} | inferências: {all_['inference_events']} | ferramentas: {all_['tool_calls']}")
        print(f"Compactações: {report['compactions']}")
        print(
            "Narração: "
            f"{narr['turns']} turnos | {narr['avg_inference_events_per_turn']} inferências/turno | "
            f"{narr['avg_tool_calls_per_turn']} ferramentas/turno"
        )
        print(
            f"Input narração: {narr['input_tokens']} tokens; cache: {narr['cached_fraction']:.1%}; "
            f"não-cache aprox.: {narr['approx_uncached_input_tokens']}"
        )
        print(
            f"apply_patch na narração: {narr['apply_patch_file_operations']} operações em "
            f"{narr['unique_files_touched_by_apply_patch']} arquivos únicos"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
