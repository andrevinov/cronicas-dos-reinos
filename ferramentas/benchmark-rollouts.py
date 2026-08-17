#!/usr/bin/env python3
"""Gate final de eficiência sobre rollouts reais pós-refatoração.

Diferente de ``comparar-rollouts.py``, que é diagnóstico, este comando possui
critério de aceitação: exige amostra mínima e retorna exit 1 quando uma meta final
não é atingida. Rollouts brutos continuam fora do repositório; o comando só os lê.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
from typing import Any


TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
COMPARER_PATH = TOOLS / "comparar-rollouts.py"
DEFAULT_BASELINE = ROOT / "baseline/rollout-2026-08-15.json"
DEFAULT_TARGETS = ROOT / "baseline/metas-benchmark-final.json"

spec = importlib.util.spec_from_file_location("comparar_rollouts_benchmark", COMPARER_PATH)
comparer = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(comparer)


class BenchmarkError(ValueError):
    pass


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkError(f"não foi possível ler {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise BenchmarkError(f"{path} não contém objeto JSON")
    return value


def _per_turn_items(reports: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        item
        for report in reports
        for item in (report.get("per_narration_turn") or [])
        if isinstance(item, dict)
    ]


def collect_metrics(
    reports: list[dict[str, Any]],
    *,
    baseline: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not reports:
        raise BenchmarkError("nenhum rollout informado")
    comparison = comparer.compare(baseline, reports, targets=None)
    aggregate = comparer._aggregate_after(reports)
    normalized = comparer._normalized(aggregate)
    per_turn = _per_turn_items(reports)

    temporary = sum(
        int(((report.get("narration_turns") or {}).get("violations") or {}).get("temporary_turn_file_calls") or 0)
        for report in reports
    )
    attempted_transcripts = sum(
        int((report.get("narration_turns") or {}).get("attempted_transcript_read_calls") or 0)
        for report in reports
    )
    unknown_writes = sum(
        int((report.get("narration_turns") or {}).get("unknown_write_calls") or 0)
        for report in reports
    )

    metrics = {
        **normalized,
        "raw_input_reduction": comparison["interpretation"].get("raw_input_reduction"),
        "uncached_input_reduction": comparison["interpretation"].get("uncached_input_reduction"),
        "canonical_write_target_touches": int(aggregate.get("canonical_write_target_touches") or 0),
        "transcript_read_calls": int(aggregate.get("transcript_read_calls") or 0),
        "attempted_transcript_read_calls": attempted_transcripts,
        "temporary_turn_file_calls": temporary,
        "schema_discovery_calls": int(aggregate.get("schema_discovery_calls") or 0),
        "failed_write_calls": int(aggregate.get("failed_write_calls") or 0),
        "unknown_write_calls": unknown_writes,
        "max_successful_write_calls_per_turn": max(
            (int(item.get("successful_write_calls") or 0) for item in per_turn), default=0
        ),
        "max_write_target_touches_per_turn": max(
            (int(item.get("write_target_touches") or 0) for item in per_turn), default=0
        ),
        "max_raw_read_calls_per_turn": max(
            (int(item.get("raw_read_calls") or 0) for item in per_turn), default=0
        ),
    }
    return metrics, comparison


def _compare(actual: Any, operator: str, expected: Any) -> bool | None:
    if actual is None:
        return None
    if operator == "<=":
        return actual <= expected
    if operator == ">=":
        return actual >= expected
    if operator == "==":
        return actual == expected
    raise BenchmarkError(f"operador de meta desconhecido: {operator}")


def evaluate(metrics: dict[str, Any], targets: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for rule in targets.get("regras") or []:
        if not isinstance(rule, dict):
            continue
        metric = str(rule.get("metrica") or "")
        operator = str(rule.get("operador") or "")
        expected = rule.get("valor")
        actual = metrics.get(metric)
        passed = _compare(actual, operator, expected)
        result.append(
            {
                "id": rule.get("id"),
                "rotulo": rule.get("rotulo") or metric,
                "metrica": metric,
                "operador": operator,
                "esperado": expected,
                "obtido": actual,
                "ok": passed,
            }
        )
    return result


def benchmark(
    rollout_paths: list[Path],
    *,
    baseline_path: Path = DEFAULT_BASELINE,
    targets_path: Path = DEFAULT_TARGETS,
    narration_regex: str | None = None,
    min_turns_override: int | None = None,
) -> dict[str, Any]:
    baseline = load_json(baseline_path)
    targets = load_json(targets_path)
    reports = [comparer.analyzer.analyze(path, narration_regex) for path in rollout_paths]
    metrics, comparison = collect_metrics(reports, baseline=baseline)

    configured_min = int(targets.get("amostra_minima_turnos_narrativos") or 5)
    minimum = min_turns_override if min_turns_override is not None else configured_min
    turns = int(metrics.get("turns") or 0)
    enough = turns >= minimum
    rules = evaluate(metrics, targets) if enough else []
    all_green = enough and bool(rules) and all(item.get("ok") is True for item in rules)
    status = "APROVADO" if all_green else ("AMOSTRA INSUFICIENTE" if not enough else "REPROVADO")

    return {
        "schema_benchmark": 1,
        "status": status,
        "aprovado": all_green,
        "amostra": {
            "rollouts": [str(path) for path in rollout_paths],
            "turnos_narrativos": turns,
            "minimo_exigido": minimum,
            "suficiente": enough,
        },
        "metricas": metrics,
        "regras": rules,
        "comparacao_baseline": {
            "reducao_input_bruto": comparison["interpretation"].get("raw_input_reduction"),
            "reducao_input_nao_cache": comparison["interpretation"].get("uncached_input_reduction"),
        },
        "nota": (
            "Benchmark para avanços narrativos comuns. Fronteiras de sessão e manutenção devem ser "
            "inspecionadas separadamente, não usadas para maquiar ou punir a média do hot path."
        ),
    }


def _fmt(value: Any, *, percent: bool = False) -> str:
    if value is None:
        return "n/d"
    if percent:
        return f"{float(value):.1%}"
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def human(report: dict[str, Any]) -> str:
    sample = report["amostra"]
    metrics = report["metricas"]
    lines = [
        f"BENCHMARK FINAL — {report['status']}",
        f"Rollouts: {len(sample['rollouts'])} | turnos narrativos: {sample['turnos_narrativos']} | mínimo: {sample['minimo_exigido']}",
        "",
        f"Input bruto: redução {_fmt(metrics.get('raw_input_reduction'), percent=True)}",
        f"Input não-cache: redução {_fmt(metrics.get('uncached_input_reduction'), percent=True)}",
        f"Inferências/turno: {_fmt(metrics.get('inference_events_per_turn'))}",
        f"Tool calls/turno: {_fmt(metrics.get('tool_calls_per_turn'))}",
        f"Writer bem-sucedido máximo/turno: {_fmt(metrics.get('max_successful_write_calls_per_turn'))}",
        f"Alvos escritos máximo/turno: {_fmt(metrics.get('max_write_target_touches_per_turn'))}",
        f"L0–L2 limpo: {_fmt(metrics.get('fraction_turns_l0_l2'), percent=True)}",
        f"RAW/turno (máximo): {_fmt(metrics.get('max_raw_read_calls_per_turn'))}",
        "",
    ]
    if not sample["suficiente"]:
        lines.append("Amostra ainda pequena: jogue mais avanços comuns antes de tirar um veredito final.")
        return "\n".join(lines) + "\n"
    lines.append("METAS")
    for item in report.get("regras") or []:
        state = "OK" if item.get("ok") is True else ("FALHA" if item.get("ok") is False else "N/D")
        actual = item.get("obtido")
        percent = item.get("metrica") in {"raw_input_reduction", "fraction_turns_l0_l2"}
        lines.append(f"[{state}] {item['rotulo']}: {_fmt(actual, percent=percent)}")
    return "\n".join(lines) + "\n"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rollouts", nargs="+", type=Path)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--metas", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--min-turnos", type=int, help="sobrescreve apenas o tamanho mínimo da amostra")
    parser.add_argument("--narration-regex")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        report = benchmark(
            args.rollouts,
            baseline_path=args.baseline,
            targets_path=args.metas,
            narration_regex=args.narration_regex,
            min_turns_override=args.min_turnos,
        )
    except (BenchmarkError, comparer.ComparisonError, comparer.analyzer.RolloutError, OSError, ValueError) as exc:
        print(f"FALHA DE BENCHMARK — {exc}")
        return 1
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(human(report), end="")
    if report["aprovado"]:
        return 0
    return 2 if report["status"] == "AMOSTRA INSUFICIENTE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
