#!/usr/bin/env python3
"""Gera o pacote pós-hoc de avaliação de desempenho de uma sessão.

O rollout bruto é somente leitura e nunca é copiado para o repositório. A
ferramenta combina a telemetria schema 3, o catálogo versionado de módulos, uma
auditoria semântica opcional e o feedback opcional do jogador. Campos sem
evidência permanecem vazios/N/D.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import sys
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from statistics import mean, median
from typing import Any, Iterable

from ferramentas.catalogo_avaliacao import comparability_key, evaluation_series


ROOT = Path(__file__).resolve().parents[1]
ANALYZER_PATH = Path(__file__).with_name("analisar-rollout.py")
DEFAULT_CATALOG = ROOT / "evaluation" / "catalogo-modulos.json"
DEFAULT_TARGETS = ROOT / "evaluation" / "metas-avaliacao.json"
DEFAULT_BASELINE = ROOT / "baseline" / "rollout-2026-08-15.json"
PACKAGE_SCHEMA = 1

AUDIT_COLUMNS = (
    "modulo",
    "avaliacao_ativacao",
    "impacto_experiencia_1a5",
    "impacto_custo_1a5",
    "prioridade_rank",
    "prioridade_faixa",
    "pontuacao_prioridade_0a10",
    "principais_problemas_de_ativacao",
    "justificativa_prioridade",
    "confianca_da_inferencia",
    "evidencias",
)

FEEDBACK_COLUMNS = (
    "tipo",
    "item",
    "rotulo",
    "observado",
    "nota_1a5",
    "ativacao_menos2a2",
    "impacto_menos2a2",
    "comentario",
)

GLOBAL_FEEDBACK = (
    ("ritmo", "Ritmo da sessão"),
    ("continuidade", "Continuidade e coerência"),
    ("mundo_vivo", "Sensação de mundo vivo"),
    ("agencia_justica", "Agência e justiça"),
    ("profundidade", "Profundidade dos desafios"),
    ("naturalidade", "Naturalidade dos acontecimentos"),
    ("confianca", "Confiança no estado do mundo"),
)


class EvaluationError(ValueError):
    pass


def _load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise EvaluationError(f"não foi possível carregar {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"não foi possível ler {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvaluationError(f"{path} não contém um objeto JSON")
    return value


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, columns: Iterable[str], rows: Iterable[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_value(row.get(key)) for key in writer.fieldnames})


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "sim" if value else "nao"
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _read_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            return [dict(row) for row in csv.DictReader(stream)]
    except OSError as exc:
        raise EvaluationError(f"não foi possível ler {path}: {exc}") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _message_text(payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for item in payload.get("content") or []:
        if isinstance(item, dict):
            parts.append(str(item.get("text") or item.get("output_text") or ""))
        elif isinstance(item, str):
            parts.append(item)
    return "".join(parts)


def _tool_input(payload: dict[str, Any]) -> str:
    for key in ("arguments", "input", "params"):
        if key not in payload:
            continue
        value = payload.get(key)
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        except TypeError:
            return str(value)
    return ""


def _record_turn_id(payload: dict[str, Any]) -> str | None:
    metadata = payload.get("internal_chat_message_metadata_passthrough") or {}
    item = payload.get("item") or {}
    value = payload.get("turn_id") or metadata.get("turn_id")
    if not value and isinstance(item, dict):
        value = item.get("turn_id")
    return str(value) if value else None


def _raw_turns(path: Path, analyzer: Any) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    turns: OrderedDict[str, dict[str, Any]] = OrderedDict()
    current_turn: str | None = None
    source_first: datetime | None = None
    source_last: datetime | None = None

    def ensure(turn_id: str) -> dict[str, Any]:
        if turn_id not in turns:
            turns[turn_id] = {
                "turn_id": turn_id,
                "first": None,
                "last": None,
                "user_at": None,
                "assistant_at": None,
                "user_messages": [],
                "commands": [],
            }
        return turns[turn_id]

    try:
        stream = path.open(encoding="utf-8")
    except OSError as exc:
        raise EvaluationError(f"não foi possível ler {path}: {exc}") from exc

    with stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EvaluationError(f"JSON inválido em {path}:{line_number}: {exc}") from exc
            payload = record.get("payload") or {}
            timestamp = _parse_timestamp(record.get("timestamp"))
            if timestamp is not None:
                source_first = timestamp if source_first is None else min(source_first, timestamp)
                source_last = timestamp if source_last is None else max(source_last, timestamp)

            turn_id = _record_turn_id(payload)
            if record.get("type") == "event_msg" and payload.get("type") == "task_started":
                turn_id = str(payload.get("turn_id") or turn_id or "") or None
            if record.get("type") == "turn_context":
                turn_id = str(payload.get("turn_id") or turn_id or "") or None
            if turn_id:
                current_turn = turn_id
            if not current_turn:
                continue
            turn = ensure(current_turn)
            if timestamp is not None:
                turn["first"] = timestamp if turn["first"] is None else min(turn["first"], timestamp)
                turn["last"] = timestamp if turn["last"] is None else max(turn["last"], timestamp)

            if record.get("type") != "response_item":
                continue
            item_type = payload.get("type")
            if item_type == "message":
                role = payload.get("role")
                text = _message_text(payload)
                if role == "user":
                    turn["user_messages"].append(text)
                    if timestamp is not None:
                        turn["user_at"] = (
                            timestamp if turn["user_at"] is None else min(turn["user_at"], timestamp)
                        )
                elif role == "assistant" and timestamp is not None:
                    turn["assistant_at"] = (
                        timestamp
                        if turn["assistant_at"] is None
                        else max(turn["assistant_at"], timestamp)
                    )
            elif item_type in {"function_call", "custom_tool_call"}:
                turn["commands"].append(_tool_input(payload))

    narration_re = analyzer.DEFAULT_NARRATION_RE
    result: list[dict[str, Any]] = []
    for turn in turns.values():
        user_signal = any(
            message.strip() == analyzer.LEGACY_NARRATION_PROMPT or narration_re.search(message.strip())
            for message in turn["user_messages"]
        )
        tool_signal = any(analyzer._is_turn_register(command) for command in turn["commands"])
        if not (user_signal or tool_signal):
            continue
        start = turn["user_at"] or turn["first"]
        # A experiência termina no último texto entregue pelo assistente. Eventos
        # técnicos sem turn_id podem aparecer depois dele e não pertencem à
        # latência percebida pelo jogador.
        end = turn["assistant_at"] or turn["last"]
        latency = (end - start).total_seconds() if start and end and end >= start else None
        result.append(
            {
                **turn,
                "inicio": start.isoformat() if start else None,
                "fim": end.isoformat() if end else None,
                "latencia_segundos": round(latency, 3) if latency is not None else None,
            }
        )
    return result, {
        "inicio": source_first.isoformat() if source_first else None,
        "fim": source_last.isoformat() if source_last else None,
    }


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, round((len(ordered) - 1) * fraction)))
    return round(float(ordered[index]), 3)


def _allocate_integer(value: int, modules: list[str]) -> dict[str, int]:
    if not modules:
        return {}
    quotient, remainder = divmod(max(0, int(value)), len(modules))
    return {
        module: quotient + (1 if index < remainder else 0)
        for index, module in enumerate(sorted(modules))
    }


def _turn_class(item: dict[str, Any], active_modules: list[str]) -> str:
    active = set(active_modules)
    if active & {"emergent_sidequest_authoring", "sidequest_success_reactions"}:
        return "autoria_ou_terminal"
    if active & {"batch_world_boundary", "liveness_boundary"}:
        return "fronteira_temporal"
    if int((item.get("tool_categories") or {}).get("dice", 0)):
        return "mecanica"
    return "avanco_comum"


def _turn_rows(
    report: dict[str, Any], raw_narration: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    items = list(report.get("per_narration_turn") or [])
    if len(items) != len(raw_narration):
        warnings.append(
            "A correlação de IDs/latência não cobriu todos os turnos: "
            f"analisador={len(items)}, parser_temporal={len(raw_narration)}."
        )
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        raw = raw_narration[index] if index < len(raw_narration) else {}
        calls = item.get("narrative_system_calls") or {}
        active = sorted(module for module, count in calls.items() if int(count or 0) > 0)
        phases = item.get("orchestration_phases") or {}
        decisions = item.get("sidequest_opportunity_decisions") or {}
        categories = item.get("tool_categories") or {}
        rows.append(
            {
                "ordinal": int(item.get("ordinal") or index + 1),
                "turn_id": raw.get("turn_id"),
                "classe_turno": _turn_class(item, active),
                "inicio": raw.get("inicio"),
                "fim": raw.get("fim"),
                "latencia_segundos": raw.get("latencia_segundos"),
                "trecho_usuario": item.get("user_excerpt"),
                "nivel_acesso": item.get("access_level"),
                "input_tokens": int(item.get("input_tokens") or 0),
                "cached_input_tokens": int(item.get("cached_input_tokens") or 0),
                "uncached_input_tokens_aprox": int(item.get("approx_uncached_input_tokens") or 0),
                "output_tokens": int(item.get("output_tokens") or 0),
                "reasoning_output_tokens": int(item.get("reasoning_output_tokens") or 0),
                "tokens_totais": int(item.get("input_tokens") or 0)
                + int(item.get("output_tokens") or 0),
                "inference_events": int(item.get("inference_events") or 0),
                "tool_calls": int(item.get("tool_calls") or 0),
                "tool_output_bytes": int(item.get("tool_output_bytes") or 0),
                "read_search_calls": int(categories.get("read_search") or 0),
                "write_calls": int(categories.get("write") or 0),
                "dice_calls": int(categories.get("dice") or 0),
                "other_calls": int(categories.get("other") or 0),
                "routed_context_calls": int(item.get("routed_context_calls") or 0),
                "raw_read_calls": int(item.get("raw_read_calls") or 0),
                "schema_discovery_calls": int(item.get("schema_discovery_calls") or 0),
                "orchestration_calls": int(item.get("orchestration_calls") or 0),
                "prepare_calls": int(phases.get("preparar") or 0),
                "conclude_calls": int(phases.get("concluir") or 0),
                "par_preparar_concluir_exato": bool(item.get("cronica_pair_turns")),
                "decisao_oportunidade": int(decisions.get("oportunidade") or 0),
                "decisao_sem_oportunidade": int(decisions.get("sem_oportunidade") or 0),
                "decisao_ausente": int(decisions.get("ausente") or 0),
                "modulos_observados": active,
                "quantidade_modulos_observados": len(active),
            }
        )
    return rows, warnings


def _module_event_rows(
    turn_rows: list[dict[str, Any]],
    report: dict[str, Any],
    module_ids: list[str],
) -> tuple[list[dict[str, Any]], int]:
    report_turns = list(report.get("per_narration_turn") or [])
    rows: list[dict[str, Any]] = []
    unattributed = 0
    for turn, item in zip(turn_rows, report_turns):
        calls = item.get("narrative_system_calls") or {}
        active = sorted(module for module in module_ids if int(calls.get(module) or 0) > 0)
        total = int(turn["tokens_totais"])
        uncached = int(turn["uncached_input_tokens_aprox"])
        latency_ms = round(float(turn["latencia_segundos"]) * 1000) if turn["latencia_segundos"] else 0
        total_alloc = _allocate_integer(total, active)
        uncached_alloc = _allocate_integer(uncached, active)
        latency_alloc = _allocate_integer(latency_ms, active)
        if not active:
            unattributed += total
        for module in module_ids:
            observed = module in active
            rows.append(
                {
                    "turno_ordinal": turn["ordinal"],
                    "turn_id": turn["turn_id"],
                    "classe_turno": turn["classe_turno"],
                    "modulo": module,
                    "elegibilidade": "indeterminada",
                    "consulta_esperada": None,
                    "consulta_observada": observed,
                    "efeito_esperado": None,
                    "efeito_observado": None,
                    "estado_ativacao": "observada" if observed else "nao_observada",
                    "chamadas_detectadas": int(calls.get(module) or 0),
                    "confianca_observacao": "media" if observed else "nao_aplicavel",
                    "input_tokens_expostos_nao_aditivos": int(turn["input_tokens"]) if observed else 0,
                    "tokens_totais_expostos_nao_aditivos": total if observed else 0,
                    "tokens_totais_atribuidos_fracionados": total_alloc.get(module, 0),
                    "tokens_uncached_atribuidos_fracionados_aprox": uncached_alloc.get(module, 0),
                    "latencia_exposta_segundos_nao_aditiva": turn["latencia_segundos"] if observed else None,
                    "latencia_atribuida_fracionada_ms": latency_alloc.get(module, 0),
                    "par_preparar_concluir_exato": turn["par_preparar_concluir_exato"] if observed else None,
                }
            )
    return rows, unattributed


def _normalize_audit_rows(
    source: list[dict[str, str]], catalog: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_module: dict[str, dict[str, str]] = {}
    for row in source:
        module = row.get("modulo") or row.get("module") or ""
        if module:
            by_module[module] = row
    result: list[dict[str, Any]] = []
    for module in catalog:
        source_row = by_module.get(module["id"], {})
        result.append({column: source_row.get(column, "") for column in AUDIT_COLUMNS} | {"modulo": module["id"]})
    return result


def _feedback_template(catalog: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = [
        {
            "tipo": "global",
            "item": item,
            "rotulo": label,
            "observado": "",
            "nota_1a5": "",
            "ativacao_menos2a2": "",
            "impacto_menos2a2": "",
            "comentario": "",
        }
        for item, label in GLOBAL_FEEDBACK
    ]
    for module in catalog:
        if module.get("visibilidade_jogador") not in {"direta", "indireta"}:
            continue
        rows.append(
            {
                "tipo": "modulo",
                "item": module["id"],
                "rotulo": module.get("rotulo_jogador") or module["id"],
                "observado": "",
                "nota_1a5": "",
                "ativacao_menos2a2": "",
                "impacto_menos2a2": "",
                "comentario": "",
            }
        )
    return rows


def _number(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(str(value).replace(",", "."))
    except ValueError:
        return None


def _score_average(items: Iterable[float | None]) -> float | None:
    values = [float(item) for item in items if item is not None]
    return round(mean(values), 2) if values else None


def _weighted_score(scores: dict[str, float | None], weights: dict[str, float]) -> float | None:
    valid = [(float(score), float(weights[key])) for key, score in scores.items() if score is not None]
    weight_total = sum(weight for _, weight in valid)
    if not valid or weight_total <= 0:
        return None
    return round(sum(score * weight for score, weight in valid) / weight_total, 2)


def _latency_score(median_seconds: float | None, p90_seconds: float | None, targets: dict[str, Any]) -> float | None:
    if median_seconds is None and p90_seconds is None:
        return None
    limits = targets.get("latencia_segundos") or {}
    parts: list[float] = []
    if median_seconds is not None:
        target = float(limits.get("mediana") or 60)
        parts.append(100.0 if median_seconds <= target else max(0.0, target / median_seconds * 100.0))
    if p90_seconds is not None:
        target = float(limits.get("p90") or 120)
        parts.append(100.0 if p90_seconds <= target else max(0.0, target / p90_seconds * 100.0))
    return round(mean(parts), 2) if parts else None


def _higher_is_better(actual: float | None, target: float) -> float | None:
    if actual is None:
        return None
    if target <= 0:
        return 100.0 if actual >= target else 0.0
    return round(min(100.0, max(0.0, actual / target * 100.0)), 2)


def _lower_is_better(actual: float | None, target: float) -> float | None:
    if actual is None:
        return None
    if actual <= target:
        return 100.0
    if actual <= 0:
        return 100.0
    return round(max(0.0, target / actual * 100.0), 2)


def _status(score: float | None, targets: dict[str, Any]) -> str:
    if score is None:
        return "N/D"
    bands = targets.get("faixas_desempenho") or []
    for band in sorted(bands, key=lambda item: float(item.get("minimo") or 0), reverse=True):
        if score >= float(band.get("minimo") or 0):
            return str(band.get("id") or "N/D")
    return "critico"


def _feedback_scores(rows: list[dict[str, str]]) -> tuple[float | None, dict[str, float]]:
    global_scores: list[float] = []
    module_scores: dict[str, float] = {}
    for row in rows:
        score = _number(row.get("nota_1a5"))
        if score is None or not 1 <= score <= 5:
            continue
        normalized = (score - 1) * 25
        if row.get("tipo") == "global":
            global_scores.append(normalized)
        elif row.get("tipo") == "modulo" and row.get("item"):
            module_scores[row["item"]] = round(normalized, 2)
    return _score_average(global_scores), module_scores


def _module_summary(
    catalog: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
    feedback_rows: list[dict[str, str]],
    event_rows: list[dict[str, Any]],
    total_tokens: int,
    targets: dict[str, Any],
) -> list[dict[str, Any]]:
    audit = {row["modulo"]: row for row in audit_rows}
    _, player_scores = _feedback_scores(feedback_rows)
    activation_scores = targets.get("notas_avaliacao_ativacao") or {}
    harm_scores = targets.get("notas_impacto_1a5") or {}
    weights = targets.get("pesos_modulo") or {}
    result: list[dict[str, Any]] = []
    for module in catalog:
        module_id = module["id"]
        observed = [row for row in event_rows if row["modulo"] == module_id and row["consulta_observada"]]
        manual = audit.get(module_id, {})
        latencies = [
            float(row["latencia_exposta_segundos_nao_aditiva"])
            for row in observed
            if row.get("latencia_exposta_segundos_nao_aditiva") is not None
        ]
        median_latency = round(median(latencies), 3) if latencies else None
        p90_latency = _percentile(latencies, 0.90)
        pair_rate = (
            sum(bool(row.get("par_preparar_concluir_exato")) for row in observed) / len(observed)
            if observed
            else None
        )
        activation = str(manual.get("avaliacao_ativacao") or "").strip()
        experience_harm = _number(manual.get("impacto_experiencia_1a5"))
        cost_harm = _number(manual.get("impacto_custo_1a5"))
        priority_rank_number = _number(manual.get("prioridade_rank"))
        priority_rank = (
            int(priority_rank_number)
            if priority_rank_number is not None and priority_rank_number.is_integer()
            else priority_rank_number
        )
        scores = {
            "calibracao": _number(activation_scores.get(activation)),
            "eficacia_integridade": _number(harm_scores.get(str(int(experience_harm))))
            if experience_harm is not None
            else None,
            "confiabilidade": round(pair_rate * 100, 2) if pair_rate is not None else None,
            "economia": _number(harm_scores.get(str(int(cost_harm)))) if cost_harm is not None else None,
            "fluidez": _latency_score(median_latency, p90_latency, targets),
            "jogador": player_scores.get(module_id),
        }
        performance = _weighted_score(scores, weights)
        turns = len(observed)
        sample_confidence = "N/D" if turns == 0 else ("baixa" if turns <= 2 else "provisoria")
        attributed = sum(int(row["tokens_totais_atribuidos_fracionados"]) for row in observed)
        result.append(
            {
                "modulo": module_id,
                "responsabilidade": module.get("responsabilidade"),
                "visibilidade_jogador": module.get("visibilidade_jogador"),
                "rotulo_jogador": module.get("rotulo_jogador"),
                "indicadores_especializados": module.get("indicadores_especializados") or [],
                "avaliacao_ativacao": activation or "N/D",
                "chamadas_detectadas": sum(int(row["chamadas_detectadas"]) for row in observed),
                "turnos_detectados": turns,
                "oportunidades_elegiveis": None,
                "precisao_consulta": None,
                "cobertura_consulta": None,
                "precisao_efeito": None,
                "recall_efeito": None,
                "input_tokens_expostos_nao_aditivos": sum(
                    int(row["input_tokens_expostos_nao_aditivos"]) for row in observed
                ),
                "tokens_totais_atribuidos_fracionados": attributed,
                "tokens_uncached_atribuidos_fracionados_aprox": sum(
                    int(row["tokens_uncached_atribuidos_fracionados_aprox"]) for row in observed
                ),
                "participacao_tokens_fracionados_pct": round(attributed / total_tokens * 100, 4)
                if total_tokens
                else 0,
                "latencia_exposta_mediana_segundos": median_latency,
                "latencia_exposta_p90_segundos": p90_latency,
                "taxa_proxy_par_cronica_exato": round(pair_rate, 6) if pair_rate is not None else None,
                "nota_calibracao_0a100": scores["calibracao"],
                "nota_eficacia_integridade_0a100": scores["eficacia_integridade"],
                "nota_confiabilidade_proxy_0a100": scores["confiabilidade"],
                "nota_economia_0a100": scores["economia"],
                "nota_fluidez_exposta_0a100": scores["fluidez"],
                "nota_jogador_0a100": scores["jogador"],
                "nota_desempenho_provisoria_0a100": performance,
                "faixa_desempenho": _status(performance, targets),
                "prioridade_rank": priority_rank,
                "prioridade_faixa": manual.get("prioridade_faixa") or "N/D",
                "pontuacao_prioridade_0a10": _number(manual.get("pontuacao_prioridade_0a10")),
                "principais_problemas_de_ativacao": manual.get("principais_problemas_de_ativacao") or "",
                "justificativa_prioridade": manual.get("justificativa_prioridade") or "",
                "confianca_inferencia_semantica": manual.get("confianca_da_inferencia") or "N/D",
                "confianca_amostra_sessao": sample_confidence,
                "evidencias": manual.get("evidencias") or "",
            }
        )
    return sorted(
        result,
        key=lambda row: (
            row["prioridade_rank"] is None,
            row["prioridade_rank"] if row["prioridade_rank"] is not None else 10_000,
            row["modulo"],
        ),
    )


def _baseline_input_reduction(report: dict[str, Any], baseline: dict[str, Any]) -> float | None:
    after = report.get("narration_turns") or {}
    before = baseline.get("narration_turns") or {}
    after_turns = int(after.get("turns") or 0)
    before_turns = int(before.get("turns") or 0)
    if not after_turns or not before_turns:
        return None
    after_value = float(after.get("input_tokens") or 0) / after_turns
    before_value = float(before.get("input_tokens") or 0) / before_turns
    if not before_value:
        return None
    return round((before_value - after_value) / before_value, 6)


def _adjudicated(validity: dict[str, Any], key: str, default: Any = None) -> Any:
    return (validity.get("metricas_adjudicadas") or {}).get(key, default)


def _scorecard(
    session_id: str,
    report: dict[str, Any],
    module_rows: list[dict[str, Any]],
    feedback_rows: list[dict[str, str]],
    validity: dict[str, Any],
    baseline: dict[str, Any],
    targets: dict[str, Any],
    latencies: list[float],
    unattributed_tokens: int,
) -> dict[str, Any]:
    narr = report.get("narration_turns") or {}
    turns = int(narr.get("turns") or 0)
    latency_median = round(median(latencies), 3) if latencies else None
    latency_p90 = _percentile(latencies, 0.90)
    latency_max = round(max(latencies), 3) if latencies else None
    reduction = _baseline_input_reduction(report, baseline)
    global_targets = targets.get("metas_globais") or {}
    economy_components = {
        "reducao_input_bruto": _higher_is_better(
            reduction, float(global_targets.get("reducao_input_bruto_minima") or 0.70)
        ),
        "inferencias_por_turno": _lower_is_better(
            _number(narr.get("avg_inference_events_per_turn")),
            float(global_targets.get("inferencias_por_turno") or 5),
        ),
        "tools_por_turno": _lower_is_better(
            _number(narr.get("avg_tool_calls_per_turn")),
            float(global_targets.get("tools_por_turno") or 5),
        ),
        "l0_l2_limpo": _higher_is_better(
            _number(narr.get("fraction_turns_l0_l2")),
            float(global_targets.get("fracao_l0_l2_limpo") or 0.80),
        ),
    }
    pair_score = _higher_is_better(_number(narr.get("fraction_turns_with_cronica_pair")), 1.0)
    failure_turns = _number(_adjudicated(validity, "turnos_narrativos_com_falha_operacional"))
    completed_turns = _number(_adjudicated(validity, "turnos_narrativos_com_conclusao_bem_sucedida"))
    first_pass = (
        round(max(0.0, (turns - failure_turns) / turns * 100), 2)
        if turns and failure_turns is not None
        else None
    )
    recovery = (
        round(min(100.0, completed_turns / turns * 100), 2)
        if turns and completed_turns is not None
        else None
    )
    player_score, _ = _feedback_scores(feedback_rows)
    axes = {
        "calibracao": _score_average(row.get("nota_calibracao_0a100") for row in module_rows),
        "eficacia_integridade": _score_average(
            row.get("nota_eficacia_integridade_0a100") for row in module_rows
        ),
        "confiabilidade": _score_average((pair_score, first_pass, recovery)),
        "economia": _score_average(economy_components.values()),
        "fluidez": _latency_score(latency_median, latency_p90, targets),
        "jogador": player_score,
    }
    overall = _weighted_score(axes, targets.get("pesos_sessao") or {})
    return {
        "schema_scorecard_sessao": PACKAGE_SCHEMA,
        "sessao_id": session_id,
        "status_avaliacao": "provisoria" if player_score is None else "avaliada_com_feedback",
        "nota_geral_0a100": overall,
        "faixa_geral": _status(overall, targets),
        "eixos": {
            key: {"nota_0a100": value, "peso": (targets.get("pesos_sessao") or {}).get(key)}
            for key, value in axes.items()
        },
        "componentes": {
            "economia": economy_components,
            "confiabilidade": {
                "par_cronica_exato": pair_score,
                "sucesso_na_primeira_tentativa_adjudicado": first_pass,
                "recuperacao_no_mesmo_turno_adjudicada": recovery,
            },
        },
        "indicadores_globais": {
            "turnos_narrativos": turns,
            "input_tokens": int(narr.get("input_tokens") or 0),
            "cached_input_tokens": int(narr.get("cached_input_tokens") or 0),
            "uncached_input_tokens_aprox": int(narr.get("approx_uncached_input_tokens") or 0),
            "output_tokens": int(narr.get("output_tokens") or 0),
            "reasoning_output_tokens": int(narr.get("reasoning_output_tokens") or 0),
            "reducao_input_bruto_baseline": reduction,
            "inferencias_por_turno": narr.get("avg_inference_events_per_turn"),
            "tools_por_turno": narr.get("avg_tool_calls_per_turn"),
            "orquestracao_por_turno": narr.get("avg_orchestration_calls_per_turn"),
            "fracao_par_cronica_exato": narr.get("fraction_turns_with_cronica_pair"),
            "fracao_l0_l2_limpo": narr.get("fraction_turns_l0_l2"),
            "fracao_turnos_com_raw": narr.get("fraction_turns_with_raw_read"),
            "raw_read_calls": narr.get("raw_read_calls"),
            "schema_discovery_calls": narr.get("schema_discovery_calls"),
            "compactacoes": report.get("compactions"),
            "latencia_mediana_segundos": latency_median,
            "latencia_p90_segundos": latency_p90,
            "latencia_maxima_segundos": latency_max,
            "turnos_acima_60_segundos": sum(value > 60 for value in latencies),
            "turnos_acima_120_segundos": sum(value > 120 for value in latencies),
            "turnos_acima_300_segundos": sum(value > 300 for value in latencies),
            "tokens_sem_atribuicao_modular": unattributed_tokens,
        },
        "metricas_adjudicadas": validity.get("metricas_adjudicadas") or {},
        "correcoes_medicao": validity.get("correcoes") or [],
        "violacoes_criticas": validity.get("violacoes_criticas") or [],
        "confianca": {
            "sessao": "provisoria",
            "motivo": "uma única sessão; estabilidade exige pelo menos três sessões e dez oportunidades por módulo",
        },
        "observacoes": [
            "Notas N/D são excluídas e os pesos restantes são renormalizados.",
            "Confiabilidade modular usa o par preparar+concluir como proxy nesta primeira versão.",
            "Fluidez modular usa latência exposta, não latência causal.",
            "Custo fracionado é aditivo; custo exposto não é aditivo.",
        ],
    }


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        values = [str(value if value not in (None, "") else "N/D").replace("|", "\\|") for value in row]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _report_markdown(
    manifest: dict[str, Any], scorecard: dict[str, Any], module_rows: list[dict[str, Any]]
) -> str:
    indicators = scorecard["indicadores_globais"]
    axes = scorecard["eixos"]
    lines = [
        f"# Avaliação de desempenho — sessão {manifest['sessao_id']}",
        "",
        "> Artefato pós-hoc de engenharia. Pode conter nomes de módulos reservados e não deve ser usado como memória de jogo.",
        "",
        f"**Nota geral provisória:** {scorecard.get('nota_geral_0a100', 'N/D')} / 100 "
        f"({scorecard.get('faixa_geral', 'N/D')}).",
        "",
        "## Saúde da sessão",
        "",
        _markdown_table(
            ["Indicador", "Valor"],
            [
                ["Turnos narrativos", indicators.get("turnos_narrativos")],
                ["Input bruto", indicators.get("input_tokens")],
                ["Redução contra baseline", _fmt_percent(indicators.get("reducao_input_bruto_baseline"))],
                ["Inferências/turno", indicators.get("inferencias_por_turno")],
                ["Tools/turno", indicators.get("tools_por_turno")],
                ["L0–L2 limpo", _fmt_percent(indicators.get("fracao_l0_l2_limpo"))],
                ["Turnos com RAW", _fmt_percent(indicators.get("fracao_turnos_com_raw"))],
                ["Latência mediana", _fmt_seconds(indicators.get("latencia_mediana_segundos"))],
                ["Latência p90", _fmt_seconds(indicators.get("latencia_p90_segundos"))],
                ["Latência máxima", _fmt_seconds(indicators.get("latencia_maxima_segundos"))],
            ],
        ),
        "",
        "## Notas por eixo",
        "",
        _markdown_table(
            ["Eixo", "Nota", "Peso"],
            [
                [key, data.get("nota_0a100"), data.get("peso")]
                for key, data in axes.items()
            ],
        ),
        "",
        "A nota do jogador está pendente quando aparece como N/D; ela não é substituída por uma nota neutra.",
        "",
        "## Módulos",
        "",
        _markdown_table(
            ["Prioridade", "Módulo", "Ativação", "Desempenho", "Tokens atribuídos", "Confiança"],
            [
                [
                    row.get("prioridade_rank"),
                    row["modulo"],
                    row["avaliacao_ativacao"],
                    row.get("nota_desempenho_provisoria_0a100"),
                    row["tokens_totais_atribuidos_fracionados"],
                    row["confianca_amostra_sessao"],
                ]
                for row in module_rows
            ],
        ),
        "",
        "## Principais problemas observados",
        "",
    ]
    for row in module_rows[:10]:
        problem = row.get("principais_problemas_de_ativacao")
        if problem:
            lines.append(f"- **{row['modulo']}** — {problem}")
    lines.extend(
        [
            "",
            "## Validade da medição",
            "",
        ]
    )
    corrections = scorecard.get("correcoes_medicao") or []
    if corrections:
        for correction in corrections:
            lines.append(
                f"- `{correction.get('metrica')}`: observado={correction.get('observado')}; "
                f"adjudicado={correction.get('adjudicado')}. {correction.get('motivo', '')}"
            )
    else:
        lines.append("- Nenhuma correção manual de medição registrada.")
    lines.extend(
        [
            "",
            "## Limitações desta primeira sessão",
            "",
            "- Elegibilidade e efeito esperado por turno ainda aparecem como indeterminados quando o rollout não oferece prova suficiente.",
            "- O custo fracionado é uma atribuição aditiva, não uma estimativa causal.",
            "- A estabilidade longitudinal só poderá ser calculada após novas sessões comparáveis.",
            "- Módulos com uma ou duas ocorrências permanecem com confiança baixa.",
            "",
        ]
    )
    return "\n".join(lines)


def _rebuild_session_index(sessions_dir: Path) -> None:
    entries: list[dict[str, Any]] = []
    for directory in sorted(path for path in sessions_dir.iterdir() if path.is_dir()):
        manifest_path = directory / "manifest.json"
        scorecard_path = directory / "scorecard.json"
        if not manifest_path.is_file() or not scorecard_path.is_file():
            continue
        try:
            manifest = _load_json(manifest_path)
            scorecard = _load_json(scorecard_path)
        except EvaluationError:
            continue
        session_id = str(manifest.get("sessao_id") or directory.name)
        entries.append(
            {
                "sessao_id": session_id,
                "serie_avaliacao": evaluation_series(manifest),
                "chave_comparabilidade": list(comparability_key(manifest)),
                "status_avaliacao": scorecard.get("status_avaliacao"),
                "nota_geral_0a100": scorecard.get("nota_geral_0a100"),
                "faixa_geral": scorecard.get("faixa_geral"),
                "eixos": scorecard.get("eixos") or {},
                "indicadores_globais": scorecard.get("indicadores_globais") or {},
                "confianca": scorecard.get("confianca") or {},
                "caminho": directory.name,
            }
        )
    entries.sort(key=lambda item: (str(item["sessao_id"]).zfill(12), str(item["sessao_id"])))
    _write_json(
        sessions_dir / "index.json",
        {
            "schema_indice_avaliacoes": 1,
            "natureza": "índice derivado para visualização longitudinal",
            "sessoes": entries,
        },
    )


def _fmt_percent(value: Any) -> str:
    number = _number(value)
    return "N/D" if number is None else f"{number:.1%}"


def _fmt_seconds(value: Any) -> str:
    number = _number(value)
    return "N/D" if number is None else f"{number:.1f} s"


def generate_session_evaluation(
    rollout: Path,
    *,
    session_id: str,
    output_dir: Path,
    catalog_path: Path = DEFAULT_CATALOG,
    targets_path: Path = DEFAULT_TARGETS,
    baseline_path: Path = DEFAULT_BASELINE,
    audit_path: Path | None = None,
    validity_path: Path | None = None,
) -> dict[str, Any]:
    if not rollout.is_file():
        raise EvaluationError(f"rollout inexistente: {rollout}")
    catalog_data = _load_json(catalog_path)
    catalog = catalog_data.get("modulos") or []
    if not isinstance(catalog, list) or not catalog:
        raise EvaluationError("catálogo de módulos vazio ou inválido")
    module_ids = [str(module.get("id") or "") for module in catalog]
    if any(not module_id for module_id in module_ids) or len(module_ids) != len(set(module_ids)):
        raise EvaluationError("IDs de módulos vazios ou duplicados")
    targets = _load_json(targets_path)
    baseline = _load_json(baseline_path)
    analyzer = _load_module(ANALYZER_PATH, "avaliacao_sessao_analisar_rollout")
    report = analyzer.analyze(rollout)
    raw_narration, source_times = _raw_turns(rollout, analyzer)
    turn_rows, correlation_warnings = _turn_rows(report, raw_narration)
    event_rows, unattributed = _module_event_rows(turn_rows, report, module_ids)

    output_dir.mkdir(parents=True, exist_ok=True)
    packaged_audit = output_dir / "auditoria-modulos.csv"
    selected_audit = audit_path if audit_path and audit_path.is_file() else packaged_audit
    source_audit = _read_csv(selected_audit) if selected_audit.is_file() else []
    audit_rows = _normalize_audit_rows(source_audit, catalog)
    _write_csv(packaged_audit, AUDIT_COLUMNS, audit_rows)

    feedback_path = output_dir / "feedback-jogador.csv"
    feedback_rows = _read_csv(feedback_path) if feedback_path.is_file() else _feedback_template(catalog)
    _write_csv(feedback_path, FEEDBACK_COLUMNS, feedback_rows)

    packaged_validity = output_dir / "validade-medicao.json"
    selected_validity = validity_path if validity_path and validity_path.is_file() else packaged_validity
    validity = _load_json(selected_validity) if selected_validity.is_file() else {
        "schema_validade_medicao": 1,
        "sessao_id": session_id,
        "metricas_adjudicadas": {},
        "correcoes": [],
        "violacoes_criticas": [],
    }
    _write_json(packaged_validity, validity)

    total_tokens = int((report.get("narration_turns") or {}).get("input_tokens") or 0) + int(
        (report.get("narration_turns") or {}).get("output_tokens") or 0
    )
    module_rows = _module_summary(
        catalog, audit_rows, feedback_rows, event_rows, total_tokens, targets
    )
    latencies = [
        float(row["latencia_segundos"])
        for row in turn_rows
        if row.get("latencia_segundos") is not None
    ]
    scorecard = _scorecard(
        session_id,
        report,
        module_rows,
        feedback_rows,
        validity,
        baseline,
        targets,
        latencies,
        unattributed,
    )

    telemetry_path = output_dir / "telemetria.json"
    turns_path = output_dir / "turnos.csv"
    events_path = output_dir / "eventos-modulares.csv"
    summary_path = output_dir / "resumo-modulos.csv"
    summary_json_path = output_dir / "resumo-modulos.json"
    scorecard_path = output_dir / "scorecard.json"
    report_path = output_dir / "relatorio.md"
    _write_json(telemetry_path, report)
    turn_columns = list(turn_rows[0]) if turn_rows else ["ordinal"]
    _write_csv(turns_path, turn_columns, turn_rows)
    event_columns = list(event_rows[0]) if event_rows else ["turno_ordinal", "modulo"]
    _write_csv(events_path, event_columns, event_rows)
    summary_columns = list(module_rows[0]) if module_rows else ["modulo"]
    _write_csv(summary_path, summary_columns, module_rows)
    _write_json(summary_json_path, {"schema_resumo_modulos": 1, "modulos": module_rows})
    _write_json(scorecard_path, scorecard)

    manifest = {
        "schema_pacote_avaliacao": PACKAGE_SCHEMA,
        "sessao_id": session_id,
        "serie_avaliacao": "legacy-v1",
        "natureza": "avaliacao_pos_hoc_derivada; não altera cânone",
        "fonte": {
            "arquivo": rollout.name,
            "sha256": _sha256(rollout),
            "bytes": rollout.stat().st_size,
            "codex_session_id": (report.get("source") or {}).get("session_id"),
            "inicio_rollout": source_times.get("inicio"),
            "fim_rollout": source_times.get("fim"),
            "bruto_copiado_para_repo": False,
        },
        "versoes": {
            "gerador": PACKAGE_SCHEMA,
            "telemetria": report.get("schema_version"),
            "sistemas_narrativos": report.get("narrative_systems_schema"),
            "catalogo_modulos": catalog_data.get("schema_catalogo_modulos"),
            "metas": targets.get("schema_metas_avaliacao"),
        },
        "amostra": {
            "turnos_narrativos": len(turn_rows),
            "modulos_catalogados": len(module_ids),
            "eventos_modulo_turno": len(event_rows),
            "tokens_narrativos": total_tokens,
            "tokens_atribuidos_fracionados": sum(
                int(row["tokens_totais_atribuidos_fracionados"]) for row in event_rows
            ),
            "tokens_sem_atribuicao": unattributed,
        },
        "avisos_medicao": correlation_warnings,
        "artefatos": {
            "telemetria": "telemetria.json",
            "turnos": "turnos.csv",
            "eventos_modulares": "eventos-modulares.csv",
            "auditoria_modulos": "auditoria-modulos.csv",
            "resumo_modulos": "resumo-modulos.csv",
            "resumo_modulos_json": "resumo-modulos.json",
            "feedback_jogador": "feedback-jogador.csv",
            "validade_medicao": "validade-medicao.json",
            "scorecard": "scorecard.json",
            "relatorio": "relatorio.md",
        },
    }
    _write_json(output_dir / "manifest.json", manifest)
    report_path.write_text(_report_markdown(manifest, scorecard, module_rows), encoding="utf-8")
    if output_dir.parent.name == "sessions":
        _rebuild_session_index(output_dir.parent)
    return {"manifest": manifest, "scorecard": scorecard, "output_dir": str(output_dir)}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("rollout", type=Path)
    parser.add_argument("--sessao-id", required=True, help="ID canônico da sessão, por exemplo 021")
    parser.add_argument("--saida", type=Path, help="diretório do pacote; padrão evaluation/sessions/<id>")
    parser.add_argument("--catalogo", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--metas", type=Path, default=DEFAULT_TARGETS)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--auditoria", type=Path, help="CSV semântico usado para semear/atualizar o pacote")
    parser.add_argument("--validade", type=Path, help="JSON de adjudicação da qualidade da medição")
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    output = args.saida or ROOT / "evaluation" / "sessions" / str(args.sessao_id)
    try:
        result = generate_session_evaluation(
            args.rollout,
            session_id=str(args.sessao_id),
            output_dir=output,
            catalog_path=args.catalogo,
            targets_path=args.metas,
            baseline_path=args.baseline,
            audit_path=args.auditoria,
            validity_path=args.validade,
        )
    except (EvaluationError, OSError, ValueError) as exc:
        print(f"FALHA DE AVALIAÇÃO — {exc}")
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        score = result["scorecard"].get("nota_geral_0a100")
        print(f"AVALIAÇÃO GERADA — sessão {args.sessao_id} — nota provisória {score}")
        print(result["output_dir"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
