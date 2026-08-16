#!/usr/bin/env python3
"""Compara um ou mais rollouts pós-refatoração com a baseline pré-refatoração.

A comparação é normalizada por avanço narrativo para que sessões com quantidades
diferentes de turnos possam ser comparadas. Não tenta converter tokens em custo,
faturamento ou quota semanal: mostra tráfego bruto, cache e indicadores operacionais.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter
from pathlib import Path
from typing import Any

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
ANALYZER_PATH = TOOLS / "analisar-rollout.py"
DEFAULT_BASELINE = REPO / "baseline/rollout-2026-08-15.json"
DEFAULT_TARGETS = REPO / "baseline/metas-rollout-pos-refatoracao.json"

spec = importlib.util.spec_from_file_location("analisar_rollout", ANALYZER_PATH)
analyzer = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(analyzer)


class ComparisonError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ComparisonError(f"não foi possível ler {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ComparisonError(f"{path} não contém objeto JSON")
    return data


def _per_turn(total: float | int | None, turns: int) -> float | None:
    if total is None or not turns:
        return None
    return float(total) / turns


def _baseline_narration(data: dict[str, Any]) -> dict[str, Any]:
    narr = data.get("narration_turns") or {}
    if not isinstance(narr, dict):
        raise ComparisonError("baseline não possui narration_turns válido")
    turns = int(narr.get("turns") or 0)
    if turns <= 0:
        raise ComparisonError("baseline não possui turnos narrativos")
    manual = narr.get("manual_audit") or {}
    categories = manual.get("tool_categories") or narr.get("tool_categories") or {}
    write_touches = manual.get("write_target_touches", narr.get("write_target_touches"))
    canonical_touches = manual.get(
        "canonical_write_target_touches", narr.get("canonical_write_target_touches")
    )
    transcript_reads = manual.get("transcript_read_calls", narr.get("transcript_read_calls"))
    return {
        "turns": turns,
        "inference_events": int(narr.get("inference_events") or 0),
        "tool_calls": int(narr.get("tool_calls") or 0),
        "input_tokens": int(narr.get("input_tokens") or 0),
        "cached_input_tokens": int(narr.get("cached_input_tokens") or 0),
        "approx_uncached_input_tokens": int(narr.get("approx_uncached_input_tokens") or 0),
        "output_tokens": int(narr.get("output_tokens") or 0),
        "reasoning_output_tokens": int(narr.get("reasoning_output_tokens") or 0),
        "tool_output_bytes": narr.get("tool_output_bytes"),
        "tool_categories": dict(categories) if isinstance(categories, dict) else {},
        "write_target_touches": write_touches,
        "canonical_write_target_touches": canonical_touches,
        "transcript_read_calls": transcript_reads,
        "fraction_turns_without_read_search": narr.get("fraction_turns_without_read_search"),
        "fraction_turns_l0_l2": narr.get("fraction_turns_l0_l2"),
        "peak_input_tokens": narr.get("peak_input_tokens"),
    }


def _aggregate_after(reports: list[dict[str, Any]]) -> dict[str, Any]:
    if not reports:
        raise ComparisonError("nenhum rollout pós-refatoração informado")
    total: dict[str, Any] = {
        "turns": 0,
        "inference_events": 0,
        "tool_calls": 0,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "approx_uncached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "tool_output_bytes": 0,
        "write_target_touches": 0,
        "canonical_write_target_touches": 0,
        "transcript_read_calls": 0,
        "turns_without_read_search": 0,
        "l0_l2_turns": 0,
        "peak_input_tokens": 0,
        "tool_categories": Counter(),
        "access_distribution": Counter(),
    }
    for report in reports:
        narr = report.get("narration_turns") or {}
        turns = int(narr.get("turns") or 0)
        total["turns"] += turns
        for key in (
            "inference_events",
            "tool_calls",
            "input_tokens",
            "cached_input_tokens",
            "approx_uncached_input_tokens",
            "output_tokens",
            "reasoning_output_tokens",
            "tool_output_bytes",
            "write_target_touches",
            "canonical_write_target_touches",
            "transcript_read_calls",
            "turns_without_read_search",
        ):
            total[key] += int(narr.get(key) or 0)
        total["peak_input_tokens"] = max(total["peak_input_tokens"], int(narr.get("peak_input_tokens") or 0))
        total["tool_categories"].update(narr.get("tool_categories") or {})
        distribution = narr.get("max_access_level_by_turn") or {}
        total["access_distribution"].update(distribution)
        total["l0_l2_turns"] += sum(
            int(count) for level, count in distribution.items() if level in {"L0", "L1", "L2"}
        )
    if total["turns"] <= 0:
        raise ComparisonError(
            "nenhum avanço narrativo foi reconhecido; use --narration-regex se a frase/fluxo mudou"
        )
    total["tool_categories"] = dict(sorted(total["tool_categories"].items()))
    total["access_distribution"] = dict(total["access_distribution"])
    total["fraction_turns_without_read_search"] = total["turns_without_read_search"] / total["turns"]
    total["fraction_turns_l0_l2"] = total["l0_l2_turns"] / total["turns"]
    total["cached_fraction"] = (
        total["cached_input_tokens"] / total["input_tokens"] if total["input_tokens"] else 0
    )
    return total


def _normalized(data: dict[str, Any]) -> dict[str, float | int | None]:
    turns = int(data.get("turns") or 0)
    categories = data.get("tool_categories") or {}
    return {
        "turns": turns,
        "input_tokens_per_turn": _per_turn(data.get("input_tokens"), turns),
        "uncached_input_tokens_per_turn": _per_turn(data.get("approx_uncached_input_tokens"), turns),
        "inference_events_per_turn": _per_turn(data.get("inference_events"), turns),
        "tool_calls_per_turn": _per_turn(data.get("tool_calls"), turns),
        "tool_output_bytes_per_turn": _per_turn(data.get("tool_output_bytes"), turns),
        "read_search_calls_per_turn": _per_turn(categories.get("read_search"), turns),
        "write_calls_per_turn": _per_turn(categories.get("write"), turns),
        "dice_calls_per_turn": _per_turn(categories.get("dice"), turns),
        "validation_calls_per_turn": _per_turn(categories.get("validation"), turns),
        "write_target_touches_per_turn": _per_turn(data.get("write_target_touches"), turns),
        "canonical_write_target_touches_per_turn": _per_turn(
            data.get("canonical_write_target_touches"), turns
        ),
        "transcript_read_calls_per_turn": _per_turn(data.get("transcript_read_calls"), turns),
        "fraction_turns_without_read_search": data.get("fraction_turns_without_read_search"),
        "fraction_turns_l0_l2": data.get("fraction_turns_l0_l2"),
        "peak_input_tokens": data.get("peak_input_tokens"),
    }


def _reduction(before: float | int | None, after: float | int | None) -> float | None:
    if before is None or after is None or float(before) == 0:
        return None
    return (float(before) - float(after)) / float(before)


def _deltas(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in before:
        if key == "turns":
            continue
        b = before.get(key)
        a = after.get(key)
        result[key] = {
            "before": b,
            "after": a,
            "reduction_fraction": _reduction(b, a),
        }
    return result


def _evaluate_targets(
    after: dict[str, Any], deltas: dict[str, Any], targets: dict[str, Any] | None
) -> list[dict[str, Any]]:
    if not targets:
        return []
    rules = ((targets.get("narration") or {}).get("rules") or [])
    evaluations: list[dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        metric = rule.get("metric")
        operator = rule.get("operator")
        threshold = rule.get("value")
        source = rule.get("source", "after")
        if source == "reduction":
            actual = ((deltas.get(metric) or {}).get("reduction_fraction"))
        else:
            actual = after.get(metric)
        passed = None
        if actual is not None and threshold is not None:
            if operator == "<=":
                passed = actual <= threshold
            elif operator == ">=":
                passed = actual >= threshold
            elif operator == "==":
                passed = actual == threshold
        evaluations.append(
            {
                "id": rule.get("id"),
                "metric": metric,
                "source": source,
                "operator": operator,
                "threshold": threshold,
                "actual": actual,
                "passed": passed,
                "label": rule.get("label"),
            }
        )
    return evaluations


def compare(
    baseline: dict[str, Any],
    reports: list[dict[str, Any]],
    targets: dict[str, Any] | None = None,
) -> dict[str, Any]:
    before_raw = _baseline_narration(baseline)
    after_raw = _aggregate_after(reports)
    before = _normalized(before_raw)
    after = _normalized(after_raw)
    deltas = _deltas(before, after)
    return {
        "schema_version": 1,
        "kind": "rollout_before_after",
        "baseline": {
            "source": baseline.get("source"),
            "narration": before,
        },
        "after": {
            "rollouts": [report.get("source") for report in reports],
            "narration": after,
            "access_distribution": after_raw.get("access_distribution"),
            "cached_fraction": after_raw.get("cached_fraction"),
        },
        "delta": deltas,
        "targets": _evaluate_targets(after, deltas, targets),
        "interpretation": {
            "raw_input_reduction": (deltas.get("input_tokens_per_turn") or {}).get("reduction_fraction"),
            "uncached_input_reduction": (
                deltas.get("uncached_input_tokens_per_turn") or {}
            ).get("reduction_fraction"),
            "quota_warning": (
                "Redução de input bruto/uncached não equivale 1:1 a cobrança ou limite semanal; "
                "a fórmula de quota não é inferida por esta ferramenta."
            ),
        },
    }


def _fmt_number(value: Any) -> str:
    if value is None:
        return "n/d"
    if isinstance(value, float):
        return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{value:,}".replace(",", ".")


def _fmt_pct(value: Any) -> str:
    return "n/d" if value is None else f"{float(value):.1%}"


def _human(report: dict[str, Any]) -> str:
    delta = report["delta"]
    after = report["after"]["narration"]
    rows = [
        ("Input bruto / turno", "input_tokens_per_turn"),
        ("Input não-cache aprox. / turno", "uncached_input_tokens_per_turn"),
        ("Inferências / turno", "inference_events_per_turn"),
        ("Tool calls / turno", "tool_calls_per_turn"),
        ("Read/search / turno", "read_search_calls_per_turn"),
        ("Writes / turno", "write_calls_per_turn"),
        ("Alvos escritos / turno", "write_target_touches_per_turn"),
        ("Escritas canônicas / turno", "canonical_write_target_touches_per_turn"),
        ("Leituras de transcript / turno", "transcript_read_calls_per_turn"),
    ]
    lines = [
        "COMPARAÇÃO PRÉ × PÓS-REFATORAÇÃO",
        f"Rollouts pós: {len(report['after']['rollouts'])} | turnos narrativos: {after['turns']}",
        "",
    ]
    for label, key in rows:
        item = delta.get(key) or {}
        lines.append(
            f"{label}: {_fmt_number(item.get('before'))} → {_fmt_number(item.get('after'))} "
            f"| redução {_fmt_pct(item.get('reduction_fraction'))}"
        )
    lines.extend(
        [
            "",
            f"Turnos sem read/search: {_fmt_pct(after.get('fraction_turns_without_read_search'))}",
            f"Turnos com acesso máximo L0–L2: {_fmt_pct(after.get('fraction_turns_l0_l2'))}",
            f"Distribuição de acesso: {report['after'].get('access_distribution')}",
            "",
            "METAS",
        ]
    )
    evaluations = report.get("targets") or []
    if not evaluations:
        lines.append("Nenhum arquivo de metas fornecido.")
    else:
        for item in evaluations:
            state = "OK" if item.get("passed") is True else ("FALHA" if item.get("passed") is False else "N/D")
            actual = item.get("actual")
            if item.get("source") == "reduction" or "fraction" in str(item.get("metric")):
                actual_text = _fmt_pct(actual)
            else:
                actual_text = _fmt_number(actual)
            lines.append(f"[{state}] {item.get('label') or item.get('id')}: {actual_text}")
    lines.extend(
        [
            "",
            f"Redução de tráfego bruto/turno: {_fmt_pct(report['interpretation'].get('raw_input_reduction'))}",
            f"Redução de input não-cache/turno: {_fmt_pct(report['interpretation'].get('uncached_input_reduction'))}",
            "Nota: estas porcentagens não são estimativa automática de cobrança/quota semanal.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rollouts", nargs="+", type=Path, help="um ou mais rollout-*.jsonl pós-refatoração")
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--targets", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--sem-metas", action="store_true", help="não carrega o arquivo de metas")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--narration-regex")
    args = parser.parse_args()
    try:
        baseline = _load_json(args.baseline)
        targets = None if args.sem_metas else _load_json(args.targets)
        reports = [analyzer.analyze(path, args.narration_regex) for path in args.rollouts]
        result = compare(baseline, reports, targets)
    except (ComparisonError, analyzer.RolloutError, OSError, ValueError) as exc:
        print(f"FALHA DE COMPARAÇÃO — {exc}")
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(_human(result), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
