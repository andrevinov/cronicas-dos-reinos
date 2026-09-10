#!/usr/bin/env python3
"""NV-14 — fronteira global de vivacidade e recibo de calma.

A camada agrega somente causas já estruturadas pelos subsistemas existentes. Ela
não é scheduler, não sorteia ocorrências, não cria presença, não oferece sidequest
e não escolhe ação para Ren. Em transições temporais relevantes, consulta fontes
dirigidas, distribui no máximo uma pressão primária por janela operacional e
produz recibo estruturado de calma quando todas as fontes autorizadas foram
consultadas e nenhuma pressão elegível existe.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

import mundo

SCHEMA = 1
CALM_SCHEMA = 1
MAX_OUTPUT_BYTES = 4 * 1024
MAX_CANDIDATES = 12
MAX_SOURCES_PER_DOMAIN = 8
MIN_LONG_COMPRESSION_MINUTES = 180

WINDOW_TRIGGERS = {"inicio_dia", "mudanca_periodo", "compressao_longa"}
CHECK_STATES = {"consultado", "nao_configurado"}
DECISIONS = {"entregue", "adiada", "bloqueada"}

# Os períodos são janelas operacionais, não fatos meteorológicos nem relógios de
# cena. Eles permanecem relativos ao amanhecer configurado na agenda: 06:00 gera
# 06:00 / 10:00 / 18:00 / 22:00. Alterar hora_amanhecer desloca as quatro janelas
# sem criar outro scheduler.
PERIOD_OFFSETS = (
    ("amanhecer", 0),
    ("dia", 4 * 60),
    ("anoitecer", 12 * 60),
    ("noite", 16 * 60),
)

REQUIRED_DOMAINS = (
    "entregas_contatos",
    "planos_compromissos",
    "operacoes_reacoes",
    "sidequests_vivas",
    "iniciativas_elenco",
    "ecologia_local",
    "ambiente_publico",
)


class LivenessBoundaryError(ValueError):
    """Contrato inválido ou consulta de vivacidade incapaz de fechar cobertura."""


def _text(value: Any, label: str, maximum: int = 260) -> str:
    if not isinstance(value, str):
        raise LivenessBoundaryError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if not result or len(result) > maximum:
        raise LivenessBoundaryError(
            f"{label} deve ser texto não vazio de até {maximum} caracteres"
        )
    return result


def _canonical(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()[:24]


def _size(value: Any) -> int:
    return len(yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8"))


def _instant(value: Any, label: str) -> tuple[dict[str, str], mundo.WorldInstant]:
    if not isinstance(value, dict) or set(value) != {"data", "hora"}:
        raise LivenessBoundaryError(f"{label} exige exatamente data e hora")
    data = _text(value.get("data"), f"{label}.data", 80)
    hora = _text(value.get("hora"), f"{label}.hora", 5)
    if not re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", hora):
        raise LivenessBoundaryError(f"{label}.hora exige HH:MM válido")
    try:
        instant = mundo.parse_instant(data, hora)
    except (ValueError, mundo.WorldEngineError) as exc:
        raise LivenessBoundaryError(str(exc)) from exc
    return {"data": data, "hora": hora}, instant


def _window(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"gatilho", "inicio", "fim"}:
        raise LivenessBoundaryError("janela exige exatamente gatilho, inicio e fim")
    trigger = _text(value.get("gatilho"), "janela.gatilho", 32)
    if trigger not in WINDOW_TRIGGERS:
        raise LivenessBoundaryError(f"gatilho de janela desconhecido: {trigger}")
    start, start_instant = _instant(value.get("inicio"), "janela.inicio")
    end, end_instant = _instant(value.get("fim"), "janela.fim")
    if end_instant < start_instant:
        raise LivenessBoundaryError("fim da janela não pode preceder o início")
    return {"gatilho": trigger, "inicio": start, "fim": end}


def _sources(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or len(value) > MAX_SOURCES_PER_DOMAIN:
        raise LivenessBoundaryError(
            f"{label} deve ser lista de até {MAX_SOURCES_PER_DOMAIN} fontes"
        )
    result: list[str] = []
    for index, raw in enumerate(value):
        source = _text(raw, f"{label}[{index}]", 180)
        if source not in result:
            result.append(source)
    return result


def _checks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise LivenessBoundaryError("consultas deve ser lista")
    found: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(value):
        if not isinstance(raw, dict):
            raise LivenessBoundaryError(f"consultas[{index}] deve ser mapa")
        allowed = {"dominio", "estado", "fontes", "motivo"}
        if set(raw) - allowed:
            raise LivenessBoundaryError(f"consultas[{index}] possui campos desconhecidos")
        domain = _text(raw.get("dominio"), f"consultas[{index}].dominio", 48)
        if domain not in REQUIRED_DOMAINS:
            raise LivenessBoundaryError(f"domínio de vivacidade desconhecido: {domain}")
        if domain in found:
            raise LivenessBoundaryError(f"domínio consultado duas vezes: {domain}")
        state = _text(raw.get("estado"), f"consultas[{index}].estado", 32)
        if state not in CHECK_STATES:
            raise LivenessBoundaryError(f"estado de consulta inválido: {state}")
        sources = _sources(raw.get("fontes"), f"consultas[{index}].fontes")
        if state == "consultado" and not sources:
            raise LivenessBoundaryError(
                f"domínio {domain} marcado consultado precisa declarar fonte"
            )
        item: dict[str, Any] = {"dominio": domain, "estado": state, "fontes": sources}
        reason = raw.get("motivo")
        if state == "nao_configurado":
            item["motivo"] = _text(reason, f"consultas[{index}].motivo", 180)
        elif reason is not None:
            item["motivo"] = _text(reason, f"consultas[{index}].motivo", 180)
        found[domain] = item
    missing = [domain for domain in REQUIRED_DOMAINS if domain not in found]
    if missing:
        raise LivenessBoundaryError(
            "cobertura incompleta da fronteira de vivacidade: " + ", ".join(missing)
        )
    return [found[domain] for domain in REQUIRED_DOMAINS]


def _candidate(value: Any, index: int) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LivenessBoundaryError(f"candidatas[{index}] deve ser mapa")
    required = {
        "id", "dominio", "tipo", "prioridade", "elegivel", "fundamento", "origem"
    }
    if set(value) != required:
        raise LivenessBoundaryError(
            f"candidatas[{index}] exige exatamente {', '.join(sorted(required))}"
        )
    candidate_id = _text(value.get("id"), f"candidatas[{index}].id", 96)
    domain = _text(value.get("dominio"), f"candidatas[{index}].dominio", 48)
    if domain not in REQUIRED_DOMAINS:
        raise LivenessBoundaryError(f"domínio de candidata desconhecido: {domain}")
    priority = value.get("prioridade")
    if not isinstance(priority, int) or isinstance(priority, bool) or not 0 <= priority <= 99:
        raise LivenessBoundaryError("prioridade deve ser inteiro entre 0 e 99")
    eligible = value.get("elegivel")
    if type(eligible) is not bool:
        raise LivenessBoundaryError("elegivel deve ser booleano")
    normalized = {
        "id": candidate_id,
        "dominio": domain,
        "tipo": _text(value.get("tipo"), f"candidatas[{index}].tipo", 64),
        "prioridade": priority,
        "elegivel": eligible,
        "fundamento": _text(value.get("fundamento"), f"candidatas[{index}].fundamento", 260),
        "origem": _text(value.get("origem"), f"candidatas[{index}].origem", 180),
    }
    normalized["fingerprint"] = _digest(normalized)
    return normalized


def _calm_receipt(window: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    base = {
        "schema_recibo_calma": CALM_SCHEMA,
        "estado": "calma_justificada",
        "motivo": "nenhuma_pressao_elegivel",
        "janela_digest": _digest(window),
        "cobertura_digest": _digest(checks),
    }
    return {**base, "digest": _digest(base)}


def project(
    window: dict[str, Any],
    candidates: list[dict[str, Any]],
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Projeta uma janela sem I/O, RNG, scheduler ou decisão narrativa automática."""
    normalized_window = _window(window)
    normalized_checks = _checks(checks)
    if not isinstance(candidates, list) or len(candidates) > MAX_CANDIDATES:
        raise LivenessBoundaryError(
            f"candidatas deve ser lista de até {MAX_CANDIDATES} itens"
        )
    normalized_candidates = [_candidate(raw, index) for index, raw in enumerate(candidates)]
    ids = [item["id"] for item in normalized_candidates]
    if len(ids) != len(set(ids)):
        raise LivenessBoundaryError("IDs de candidatas devem ser únicos na janela")
    coverage = {item["dominio"]: item for item in normalized_checks}
    for item in normalized_candidates:
        if coverage[item["dominio"]]["estado"] != "consultado":
            raise LivenessBoundaryError(
                f"candidata {item['id']} pertence a domínio não configurado"
            )
    ordered = sorted(normalized_candidates, key=lambda item: (item["prioridade"], item["id"]))
    primary = next((item for item in ordered if item["elegivel"]), None)
    decisions: list[dict[str, Any]] = []
    for item in ordered:
        if not item["elegivel"]:
            decision = "bloqueada"
            reason = item["fundamento"]
        elif primary is not None and item["id"] == primary["id"]:
            decision = "entregue"
            reason = "selecionada para o único slot primário desta janela"
        else:
            decision = "adiada"
            reason = (
                f"{primary['id']} ocupa o único slot primário desta janela"
                if primary is not None
                else "nenhuma pressão primária disponível"
            )
        decisions.append(
            {
                key: item[key]
                for key in ("id", "dominio", "tipo", "origem", "prioridade", "fingerprint")
            }
            | {"decisao": decision, "motivo": reason}
        )
    eligible_count = sum(item["elegivel"] for item in ordered)
    result = {
        "schema_fronteira_vivacidade": SCHEMA,
        "mutante": False,
        "janela": normalized_window,
        "pressao_primaria": primary["id"] if primary is not None else None,
        "decisoes": decisions,
        "cobertura": normalized_checks,
        "recibo_calma": _calm_receipt(normalized_window, normalized_checks) if primary is None else None,
        "semantica_entrega": "entregue significa selecionada para atenção; transporte até Ren continua sujeito ao contrato causal da fonte",
        "metricas": {
            "candidatas": len(ordered),
            "elegiveis": eligible_count,
            "primarias": 1 if primary is not None else 0,
            "max_primarias_por_janela": 1,
            "rng_novo": 0,
            "scheduler_novo": 0,
            "scan_global": 0,
            "chamadas_ia": 0,
        },
    }
    if _size(result) > MAX_OUTPUT_BYTES:
        raise LivenessBoundaryError(
            f"projeção de vivacidade excede {MAX_OUTPUT_BYTES} bytes; reduza as projeções dirigidas, não aumente o teto"
        )
    return result


def _period_boundaries(
    start: mundo.WorldInstant,
    target: mundo.WorldInstant,
    dawn_minute: int,
) -> dict[int, tuple[str, str]]:
    if type(dawn_minute) is not int or not 0 <= dawn_minute < 1440:
        raise LivenessBoundaryError("amanhecer operacional deve ser minuto do dia válido")
    first_day = start.minute // 1440 - 1
    last_day = target.minute // 1440 + 1
    result: dict[int, tuple[str, str]] = {}
    for day in range(first_day, last_day + 1):
        base = day * 1440 + dawn_minute
        for period, offset in PERIOD_OFFSETS:
            when = base + offset
            trigger = "inicio_dia" if period == "amanhecer" else "mudanca_periodo"
            result[when] = (trigger, period)
    return result


def period_at(instant: mundo.WorldInstant, dawn_minute: int) -> str:
    relative = (instant.minute - dawn_minute) % 1440
    if relative < PERIOD_OFFSETS[1][1]:
        return "amanhecer"
    if relative < PERIOD_OFFSETS[2][1]:
        return "dia"
    if relative < PERIOD_OFFSETS[3][1]:
        return "anoitecer"
    return "noite"


def consultation_windows(
    start: mundo.WorldInstant,
    target: mundo.WorldInstant,
    dawn_minute: int,
) -> list[dict[str, Any]]:
    """Divide uma compressão em poucas janelas relevantes; turno curto custa zero."""
    if target < start:
        raise LivenessBoundaryError("alvo de vivacidade não pode preceder o início")
    boundaries = _period_boundaries(start, target, dawn_minute)
    crossed = sorted(minute for minute in boundaries if start.minute < minute <= target.minute)
    start_boundary = boundaries.get(start.minute)
    long_span = target.minute - start.minute >= MIN_LONG_COMPRESSION_MINUTES
    if not long_span and start_boundary is None and not crossed:
        return []
    windows: list[dict[str, Any]] = []
    if start_boundary is not None:
        windows.append(
            {
                "gatilho": start_boundary[0],
                "inicio": mundo.instant_parts(start),
                "fim": mundo.instant_parts(start),
                "periodo": start_boundary[1],
            }
        )
    cursor = start
    for minute in crossed:
        end = mundo.WorldInstant(minute)
        trigger, period = boundaries[minute]
        windows.append(
            {
                "gatilho": trigger,
                "inicio": mundo.instant_parts(cursor),
                "fim": mundo.instant_parts(end),
                "periodo": period,
            }
        )
        cursor = end
    if cursor < target:
        windows.append(
            {
                "gatilho": "compressao_longa",
                "inicio": mundo.instant_parts(cursor),
                "fim": mundo.instant_parts(target),
                "periodo": period_at(target, dawn_minute),
            }
        )
    if not windows:
        windows.append(
            {
                "gatilho": "compressao_longa",
                "inicio": mundo.instant_parts(start),
                "fim": mundo.instant_parts(target),
                "periodo": period_at(target, dawn_minute),
            }
        )
    return windows


def _envelope(
    candidate: dict[str, Any],
    activate: mundo.WorldInstant,
    expire: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    return {
        "candidata": candidate,
        "ativar_em": mundo.instant_parts(activate),
        "expirar_em": mundo.instant_parts(expire) if expire is not None else None,
    }


def _normalize_envelopes(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > MAX_CANDIDATES:
        raise LivenessBoundaryError(f"envelopes deve conter até {MAX_CANDIDATES} candidatas")
    result = []
    ids: set[str] = set()
    for pos, raw in enumerate(value):
        if not isinstance(raw, dict) or set(raw) != {"candidata", "ativar_em", "expirar_em"}:
            raise LivenessBoundaryError(f"envelopes[{pos}] possui campos divergentes")
        candidate = _candidate(raw["candidata"], pos)
        if candidate["id"] in ids:
            raise LivenessBoundaryError("IDs de candidatas devem ser únicos na faixa")
        ids.add(candidate["id"])
        activate_parts, activate = _instant(raw["ativar_em"], f"envelopes[{pos}].ativar_em")
        expire_parts = None
        expire = None
        if raw["expirar_em"] is not None:
            expire_parts, expire = _instant(raw["expirar_em"], f"envelopes[{pos}].expirar_em")
            if expire < activate:
                raise LivenessBoundaryError("candidata não pode expirar antes de ativar")
        result.append(
            {
                "candidata": candidate,
                "ativar_em": activate_parts,
                "ativar_minuto": activate.minute,
                "expirar_em": expire_parts,
                "expirar_minuto": expire.minute if expire is not None else None,
            }
        )
    return result


def project_span(
    windows: list[dict[str, Any]],
    envelopes: list[dict[str, Any]],
    checks: list[dict[str, Any]],
) -> dict[str, Any]:
    """Distribui pressões por janelas sem repetir bloqueios nem descartar adiadas."""
    normalized_checks = _checks(checks)
    normalized = _normalize_envelopes(envelopes)
    selected: set[str] = set()
    blocked_seen: set[str] = set()
    evaluations: list[dict[str, Any]] = []
    first_pressure: dict[str, str] | None = None
    for pos, raw_window in enumerate(windows):
        period = _text(raw_window.get("periodo"), f"janelas[{pos}].periodo", 24)
        base_window = {key: raw_window[key] for key in ("gatilho", "inicio", "fim")}
        checked_window = _window(base_window)
        _, begin = _instant(checked_window["inicio"], "janela.inicio")
        _, end = _instant(checked_window["fim"], "janela.fim")
        active = []
        for item in normalized:
            cid = item["candidata"]["id"]
            if cid in selected or cid in blocked_seen or item["ativar_minuto"] > end.minute:
                continue
            expiry = item["expirar_minuto"]
            if expiry is not None and expiry < begin.minute:
                continue
            active.append(
                {
                    key: item["candidata"][key]
                    for key in ("id", "dominio", "tipo", "prioridade", "elegivel", "fundamento", "origem")
                }
            )
        projected = project(checked_window, active, normalized_checks)
        primary = projected["pressao_primaria"]
        if primary is not None:
            selected.add(primary)
            if first_pressure is None:
                first_pressure = {"id": primary, **checked_window["fim"]}
        compact_decisions = []
        for decision in projected["decisoes"]:
            if decision["decisao"] == "bloqueada":
                blocked_seen.add(decision["id"])
            compact_decisions.append(
                {key: decision[key] for key in ("id", "decisao", "motivo")}
            )
        receipt = projected["recibo_calma"]
        evaluations.append(
            {
                "gatilho": checked_window["gatilho"],
                "periodo": period,
                "inicio": checked_window["inicio"],
                "fim": checked_window["fim"],
                "pressao_primaria": primary,
                "decisoes": compact_decisions,
                "recibo_calma": (
                    {"estado": receipt["estado"], "digest": receipt["digest"]}
                    if receipt is not None
                    else None
                ),
            }
        )
    pending = [
        item["candidata"]["id"]
        for item in normalized
        if item["candidata"]["elegivel"]
        and item["candidata"]["id"] not in selected
        and item["candidata"]["id"] not in blocked_seen
    ]
    catalog = [
        {
            key: item["candidata"][key]
            for key in ("id", "dominio", "tipo", "origem", "prioridade")
        }
        for item in sorted(normalized, key=lambda row: (row["candidata"]["prioridade"], row["candidata"]["id"]))
    ]
    result = {
        "schema_fronteira_vivacidade": SCHEMA,
        "modo": "faixa_temporal",
        "mutante": False,
        "avaliacoes": evaluations,
        "catalogo": catalog,
        "cobertura": normalized_checks,
        "cobertura_digest": _digest(normalized_checks),
        "primeira_pressao_em": first_pressure,
        "pendentes_apos_alvo": pending,
        "metricas": {
            "janelas": len(evaluations),
            "calmas": sum(item["recibo_calma"] is not None for item in evaluations),
            "candidatas": len(normalized),
            "primarias": len(selected),
            "max_primarias_por_janela": 1,
            "rng_novo": 0,
            "scheduler_novo": 0,
            "scan_global": 0,
            "chamadas_ia": 0,
        },
    }
    if _size(result) > MAX_OUTPUT_BYTES:
        raise LivenessBoundaryError(
            f"faixa de vivacidade excede {MAX_OUTPUT_BYTES} bytes; resolva/estreite causas em vez de elevar o teto"
        )
    return result


def _priority(kind: str) -> int:
    import pressao_narrativa

    if kind not in pressao_narrativa.PRIORITIES:
        raise LivenessBoundaryError(f"tipo de pressão sem prioridade existente: {kind}")
    return int(pressao_narrativa.PRIORITIES[kind])


def _candidate_input(
    candidate_id: str,
    domain: str,
    kind: str,
    *,
    eligible: bool,
    reason: str,
    origin: str,
) -> dict[str, Any]:
    return {
        "id": candidate_id,
        "dominio": domain,
        "tipo": kind,
        "prioridade": _priority(kind),
        "elegivel": eligible,
        "fundamento": " ".join(reason.split())[:260],
        "origem": origin,
    }


def _check(domain: str, sources: list[str], reason: str | None = None) -> dict[str, Any]:
    compact = list(dict.fromkeys(str(value) for value in sources if value))[:MAX_SOURCES_PER_DOMAIN]
    if compact:
        result: dict[str, Any] = {"dominio": domain, "estado": "consultado", "fontes": compact}
        if reason:
            result["motivo"] = reason[:180]
        return result
    return {
        "dominio": domain,
        "estado": "nao_configurado",
        "fontes": [],
        "motivo": (reason or "produtor não configurado neste repositório")[:180],
    }


def _pending_instant(pending: dict[str, Any]) -> mundo.WorldInstant:
    raw = pending.get("disparado_em")
    if not isinstance(raw, dict):
        raise LivenessBoundaryError(f"pendência {pending.get('id')} sem disparado_em")
    try:
        return mundo.parse_instant(str(raw.get("data")), str(raw.get("hora")))
    except mundo.WorldEngineError as exc:
        raise LivenessBoundaryError(str(exc)) from exc


def _plan_instant(raw: Any) -> mundo.WorldInstant | None:
    if not isinstance(raw, dict) or set(raw) != {"data", "hora"}:
        return None
    try:
        return mundo.parse_instant(str(raw["data"]), str(raw["hora"]))
    except mundo.WorldEngineError:
        return None


def _effective_state(repo: Path):
    import memoria_cena

    try:
        reader, state, records, saved = memoria_cena.load_scene(repo)
    except (ValueError, OSError, yaml.YAMLError) as exc:
        raise LivenessBoundaryError(f"estado efetivo indisponível: {exc}") from exc
    if not isinstance(state, dict):
        raise LivenessBoundaryError("estado efetivo deve ser mapa")
    return reader, state, records, saved


def _plans(world: dict[str, Any]) -> dict[str, dict[str, Any]]:
    import planos_personagens as plans

    try:
        return plans._control(copy.deepcopy(world))
    except plans.PlanError as exc:
        raise LivenessBoundaryError(str(exc)) from exc


def _collect_contacts(
    repo: Path,
    world: dict[str, Any],
    control: dict[str, dict[str, Any]],
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import contatos_sociais
    import entregas_causais
    import planos_personagens as plans

    envelopes: list[dict[str, Any]] = []
    by_pending = {plan.get("pendencia_id"): plan for plan in control.values() if plan.get("pendencia_id")}
    for pending in sorted(world.get("pendencias") or [], key=lambda row: str(row.get("id"))):
        pid = str(pending.get("id") or "")
        if pending.get("tipo") == entregas_causais.PENDING_TYPE:
            try:
                receipt = entregas_causais.blocked_receipt(repo, pending)
            except entregas_causais.DeliveryError as exc:
                raise LivenessBoundaryError(str(exc)) from exc
            detail = "entrega causal ainda não possui canal válido"
            if receipt is not None:
                detail = str(receipt["valor"]["destino"].get("detalhe") or detail)
            envelopes.append(
                _envelope(
                    _candidate_input(
                        f"entrega:{pid}",
                        "entregas_contatos",
                        "acao_social_solicitada",
                        eligible=False,
                        reason=detail,
                        origin=f"mundo:{pid}",
                    ),
                    _pending_instant(pending),
                )
            )
            continue
        plan = by_pending.get(pid)
        if not isinstance(plan, dict) or not contatos_sociais.is_contact(plan):
            continue
        eligible = False
        reason = "contato devido ainda não possui chegada causal revalidada"
        if plan.get("estado") == "tentou":
            try:
                contatos_sociais.delivery(plans.View(repo, records), plan)
                eligible = True
                reason = "contato já devido possui canal, destino e presença revalidados"
            except plans.PlanError as exc:
                reason = f"contato bloqueado: {exc}"
        envelopes.append(
            _envelope(
                _candidate_input(
                    f"contato:{plan['id']}",
                    "entregas_contatos",
                    "acao_social_solicitada",
                    eligible=eligible,
                    reason=reason,
                    origin=f"plano:{plan['id']}",
                ),
                _pending_instant(pending),
            )
        )
    return envelopes, _check("entregas_contatos", [mundo.WORLD_STATE_PATH.as_posix()])


def _collect_plans_commitments(
    world: dict[str, Any],
    control: dict[str, dict[str, Any]],
    state: dict[str, Any],
    start: mundo.WorldInstant,
    target: mundo.WorldInstant,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import compromissos
    import contatos_sociais
    import planos_personagens as plans

    envelopes: list[dict[str, Any]] = []
    by_pending = {plan.get("pendencia_id"): plan for plan in control.values() if plan.get("pendencia_id")}
    for pending in sorted(world.get("pendencias") or [], key=lambda row: str(row.get("id"))):
        if pending.get("tipo") != plans.PENDING_TYPE:
            continue
        plan = by_pending.get(pending.get("id"))
        if not isinstance(plan, dict):
            continue
        step = plan.get("passo") or {}
        resolution = step.get("resolucao") or {}
        if contatos_sociais.is_contact(plan) or step.get("oportunidade_sidequest") is not None or resolution.get("tipo") == "operacao":
            continue
        envelopes.append(
            _envelope(
                _candidate_input(
                    f"plano:{plan['id']}",
                    "planos_compromissos",
                    "pendencia_bloqueante",
                    eligible=True,
                    reason="plano autônomo já devido precisa de destino antes de comprimir tempo",
                    origin=f"mundo:{pending['id']}",
                ),
                _pending_instant(pending),
            )
        )
    commitments = state.get("compromissos") or {}
    if not isinstance(commitments, dict):
        raise LivenessBoundaryError("estado.compromissos deve ser mapa")
    for cid, raw in sorted(commitments.items()):
        try:
            record = compromissos.validate_record(raw)
        except compromissos.CommitmentError as exc:
            raise LivenessBoundaryError(str(exc)) from exc
        window = record.get("janela") or {}
        begin = _plan_instant(window.get("inicio"))
        end = _plan_instant(window.get("fim"))
        activate = begin
        reason = "compromisso entrou em sua janela temporal"
        if begin is None and end is not None:
            activate = end
            reason = "compromisso alcançou seu limite temporal"
        if end is not None and end < start:
            activate = start
            reason = "compromisso permaneceu aberto depois do fim de sua janela"
        if activate is None or activate > target:
            continue
        envelopes.append(
            _envelope(
                _candidate_input(
                    f"compromisso:{cid}",
                    "planos_compromissos",
                    "fronteira_temporal",
                    eligible=True,
                    reason=reason,
                    origin=f"estado:compromissos.{cid}",
                ),
                activate,
            )
        )
    return envelopes, _check(
        "planos_compromissos",
        [mundo.WORLD_STATE_PATH.as_posix(), "estado/estado-atual.yaml"],
    )


def _collect_operations(
    world: dict[str, Any],
    control: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import planos_personagens as plans

    envelopes: list[dict[str, Any]] = []
    operation_types = {
        "resolver_operacao_adversarial": "operacao_comprometida",
        "resolver_grupo_operacoes": "operacao_comprometida",
        "resolver_reacao_sidequest": "reacao_elegivel",
    }
    by_pending = {plan.get("pendencia_id"): plan for plan in control.values() if plan.get("pendencia_id")}
    for pending in sorted(world.get("pendencias") or [], key=lambda row: str(row.get("id"))):
        kind = operation_types.get(str(pending.get("tipo") or ""))
        if kind is not None:
            envelopes.append(
                _envelope(
                    _candidate_input(
                        f"operacao:{pending['id']}",
                        "operacoes_reacoes",
                        kind,
                        eligible=True,
                        reason="operação/reação já comprometida ou elegível está pendente",
                        origin=f"mundo:{pending['id']}",
                    ),
                    _pending_instant(pending),
                )
            )
            continue
        if pending.get("tipo") != plans.PENDING_TYPE:
            continue
        plan = by_pending.get(pending.get("id"))
        resolution = (plan or {}).get("passo", {}).get("resolucao", {}) if isinstance(plan, dict) else {}
        if resolution.get("tipo") != "operacao":
            continue
        envelopes.append(
            _envelope(
                _candidate_input(
                    f"operacao-plano:{plan['id']}",
                    "operacoes_reacoes",
                    "pendencia_bloqueante",
                    eligible=True,
                    reason="passo de operação do personagem já está devido no Mundo Vivo",
                    origin=f"plano:{plan['id']}",
                ),
                _pending_instant(pending),
            )
        )
    return envelopes, _check("operacoes_reacoes", [mundo.WORLD_STATE_PATH.as_posix()])


def _mission_deadline(window: Any) -> mundo.WorldInstant | None:
    if not isinstance(window, dict):
        return None
    if window.get("tipo") == "temporal":
        return _plan_instant(window.get("expira_em"))
    return _plan_instant(window.get("fim"))


def _collect_sidequests(
    repo: Path,
    world: dict[str, Any],
    control: dict[str, dict[str, Any]],
    records: list[dict[str, Any]],
    target: mundo.WorldInstant,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    import planos_personagens as plans
    import sidequests_ativas
    import sidequests_personagens

    if not sidequests_ativas.configured(repo):
        return [], _check("sidequests_vivas", [], "lifecycle de sidequests não configurado")
    try:
        active = sidequests_ativas.project(repo)
    except sidequests_ativas.ActiveSidequestError as exc:
        raise LivenessBoundaryError(str(exc)) from exc
    sources = list(active.get("fontes_lidas") or [])
    envelopes: list[dict[str, Any]] = []
    for mission in active.get("missoes") or []:
        due = _mission_deadline(mission.get("prazo"))
        if due is None or due > target:
            continue
        mid = str(mission.get("mission_id"))
        envelopes.append(
            _envelope(
                _candidate_input(
                    f"sidequest:{mid}",
                    "sidequests_vivas",
                    "prazo_sidequest",
                    eligible=True,
                    reason="prazo de missão aceita é alcançado pela compressão",
                    origin=f"sidequest:{mid}",
                ),
                due,
            )
        )
    for pending in sorted(world.get("pendencias") or [], key=lambda row: str(row.get("id"))):
        if pending.get("tipo") == "resolver_sidequest":
            envelopes.append(
                _envelope(
                    _candidate_input(
                        f"sidequest-pendente:{pending['id']}",
                        "sidequests_vivas",
                        "prazo_sidequest",
                        eligible=True,
                        reason="progressão/terminal de sidequest já possui pendência factual",
                        origin=f"mundo:{pending['id']}",
                    ),
                    _pending_instant(pending),
                )
            )
    pending_ids = {str(item.get("id")) for item in world.get("pendencias") or []}
    opportunity_state = None
    try:
        import oportunidades

        opportunity_index = oportunidades.load_index(repo)
        opportunity_state = oportunidades.load_state(repo, opportunity_index)
        sources.extend([oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix()])
    except oportunidades.OpportunityError as exc:
        raise LivenessBoundaryError(str(exc)) from exc
    for plan in sorted(control.values(), key=lambda row: str(row.get("id"))):
        step = plan.get("passo") or {}
        if step.get("oportunidade_sidequest") is None or plan.get("estado") in plans.TERMINAL:
            continue
        try:
            view = plans.View(repo, records)
            contract = sidequests_personagens.validate_definition(view, plan)
        except (plans.PlanError, sidequests_personagens.CharacterSidequestError) as exc:
            raise LivenessBoundaryError(str(exc)) from exc
        if contract is None:
            continue
        cause = sidequests_personagens._cause_projection(plan, contract)
        existing = sidequests_personagens._existing_for_cause(opportunity_state, cause["id"])
        if existing is not None:
            continue
        due = _plan_instant(step.get("em"))
        if due is None or due > target:
            continue
        # A negativa manual de nova oportunidade não participa desta decisão: a
        # causa NV-11 já está no plano e permanece visível até ganhar destino.
        is_due = plan.get("pendencia_id") in pending_ids or due <= target
        if not is_due:
            continue
        envelopes.append(
            _envelope(
                _candidate_input(
                    f"causa-nv11:{cause['id']}",
                    "sidequests_vivas",
                    "nova_oportunidade",
                    eligible=True,
                    reason="causa NV-11 declarada no plano tornou-se devida; avaliar não significa oferecer ou aceitar missão",
                    origin=f"plano:{plan['id']}",
                ),
                due,
            )
        )
        sources.extend(sorted(view.signatures))
    return envelopes, _check("sidequests_vivas", sources or [mundo.WORLD_STATE_PATH.as_posix()])


def _collect_initiatives(
    repo: Path,
    reader: Any,
    state: dict[str, Any],
    records: list[dict[str, Any]],
    saved: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    import dialogo_relacional
    import iniciativa_social
    import memoria_cena

    participants = list(saved.get("participantes") or []) if isinstance(saved, dict) else []
    potential: list[str] = []
    requires_reason: list[str] = []
    if participants:
        docs = memoria_cena.documents(reader, state, records, participants)
        for npc_id in participants:
            result = (docs.get(npc_id) or {}).get("resultado") or {}
            npc_payload = ((result.get("medidores") or {}).get("dados"))
            if not isinstance(npc_payload, dict):
                continue
            meters = npc_payload.get("medidores") or {}
            mode = dialogo_relacional.relationship_mode(meters.get("vinculo"), meters.get("confianca"))
            projection = iniciativa_social.project(npc_payload, relationship_mode=mode)
            if projection is None:
                continue
            if projection["pode_iniciar"]:
                potential.append(npc_id)
            if projection["exige_motivo"]:
                requires_reason.append(npc_id)
    sources = list(reader.sources) or ["estado/estado-atual.yaml"]
    context = {
        "elenco_presente": participants,
        "podem_iniciar_sem_criar_causa": potential,
        "exigem_motivo_concreto": requires_reason,
        "regra": "capacidade social não vira pressão por si; NV-14 não fabrica assunto nem presença",
    }
    return context, _check("iniciativas_elenco", sources)


def _current_local(repo: Path, state: dict[str, Any]) -> tuple[str | None, list[str]]:
    import locais

    location = state.get("localizacao") or {}
    supplied = location.get("local_id") or location.get("area")
    if not isinstance(supplied, str) or not supplied.strip():
        return None, ["estado/estado-atual.yaml"]
    try:
        resolved = locais.resolve(repo, supplied)
    except locais.LocationError as exc:
        raise LivenessBoundaryError(f"local atual não resolvido para ecologia: {exc}") from exc
    return resolved["local_id"], list(resolved.get("fontes_lidas") or [])


def _collect_ecology(
    repo: Path,
    state: dict[str, Any],
    windows: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    import ecologia_local

    local_id, location_sources = _current_local(repo, state)
    if not ecologia_local.configured(repo):
        return {}, _check("ecologia_local", [], "ecologia local não configurada"), local_id
    if local_id is None:
        return {}, _check("ecologia_local", location_sources, "estado atual não declara local canônico"), None
    try:
        lookup = ecologia_local.lookup_canonical(repo, local_id)
        periods = list(dict.fromkeys(str(row.get("periodo")) for row in windows))
        rhythms = {
            period: ecologia_local.activity(lookup["perfil"], period)["ritmo"]
            for period in periods
        }
    except ecologia_local.LocalEcologyError as exc:
        raise LivenessBoundaryError(str(exc)) from exc
    slot = {
        "local_id": local_id,
        "ritmo_por_periodo": rhythms,
        "regra": "um slot ecológico consultado; nenhum sorteio ou microevento é criado pela NV-14",
    }
    return slot, _check("ecologia_local", [*location_sources, *lookup["fontes_lidas"]]), local_id


def _collect_environment(
    repo: Path,
    local_id: str | None,
    start: mundo.WorldInstant,
    target: mundo.WorldInstant,
) -> tuple[dict[str, Any], dict[str, Any]]:
    import condicoes_mundo

    state_path = getattr(condicoes_mundo, "STATE", Path("narrador/mundo/condicoes-persistentes.yaml"))
    if not (repo / state_path).is_file():
        return {
            "condicoes_ativas_na_faixa": [],
            "avisos_publicos_estruturados": "nao_configurado",
        }, _check("ambiente_publico", [], "condições persistentes não configuradas")
    try:
        state = condicoes_mundo.load_state(repo)
    except condicoes_mundo.WorldConditionError as exc:
        raise LivenessBoundaryError(str(exc)) from exc
    active: list[str] = []
    for cid, record in sorted(state.get("condicoes", {}).items()):
        begin = condicoes_mundo._instant(record["inicio"], f"{cid}.inicio")
        end = condicoes_mundo._instant(record["fim_previsto"], f"{cid}.fim_previsto") if record.get("fim_previsto") else None
        applies = not record["escopo"]["locais"] or (local_id is not None and local_id in record["escopo"]["locais"])
        overlaps = begin <= target and (end is None or end >= start)
        if applies and overlaps:
            active.append(cid)
    context = {
        "condicoes_ativas_na_faixa": active,
        # NV-22 poderá instalar o produtor de avisos. Ausência aqui não autoriza
        # inventar edital, patrulha, decreto ou notícia pública.
        "avisos_publicos_estruturados": "nao_configurado",
    }
    return context, _check("ambiente_publico", [state_path.as_posix()])


def collect_repo(
    repo: Path,
    start: mundo.WorldInstant,
    target: mundo.WorldInstant,
    windows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    """Consulta apenas filas/índices compactos já autorizados pelos produtores."""
    try:
        world = mundo.load_world_state(repo)
    except mundo.WorldEngineError as exc:
        raise LivenessBoundaryError(str(exc)) from exc
    reader, state, records, saved = _effective_state(repo)
    control = _plans(world)
    envelopes: list[dict[str, Any]] = []
    checks: dict[str, dict[str, Any]] = {}

    rows, check = _collect_contacts(repo, world, control, records)
    envelopes.extend(rows); checks[check["dominio"]] = check
    rows, check = _collect_plans_commitments(world, control, state, start, target)
    envelopes.extend(rows); checks[check["dominio"]] = check
    rows, check = _collect_operations(world, control)
    envelopes.extend(rows); checks[check["dominio"]] = check
    rows, check = _collect_sidequests(repo, world, control, records, target)
    envelopes.extend(rows); checks[check["dominio"]] = check
    initiative_context, check = _collect_initiatives(repo, reader, state, records, saved)
    checks[check["dominio"]] = check
    ecology_context, check, local_id = _collect_ecology(repo, state, windows)
    checks[check["dominio"]] = check
    environment_context, check = _collect_environment(repo, local_id, start, target)
    checks[check["dominio"]] = check

    if len(envelopes) > MAX_CANDIDATES:
        raise LivenessBoundaryError(
            f"há {len(envelopes)} causas vivas para teto {MAX_CANDIDATES}; resolver a fila antes de comprimir, sem descarte silencioso"
        )
    context = {
        "iniciativas_elenco": initiative_context,
        "ecologia_slot": ecology_context,
        "ambiente_publico": environment_context,
    }
    return envelopes, [checks[domain] for domain in REQUIRED_DOMAINS], context


def evaluate(
    repo: Path,
    target: mundo.WorldInstant,
    *,
    start: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    """Executa a consulta global read-only apenas quando a janela é relevante."""
    repo = Path(repo).resolve()
    if start is None:
        try:
            start, _ = mundo.load_canonical_time(repo)
        except mundo.WorldEngineError as exc:
            raise LivenessBoundaryError(str(exc)) from exc
    if target < start:
        raise LivenessBoundaryError("alvo de vivacidade não pode preceder tempo canônico")
    try:
        agenda = mundo.load_agenda(repo)
        dawn = mundo._dawn_minute(agenda)
    except mundo.WorldEngineError as exc:
        raise LivenessBoundaryError(str(exc)) from exc
    windows = consultation_windows(start, target, dawn)
    if not windows:
        return {
            "schema_fronteira_vivacidade": SCHEMA,
            "modo": "faixa_temporal",
            "mutante": False,
            "aplicavel": False,
            "motivo": "turno_curto_sem_mudanca_de_periodo",
            "metricas": {"janelas": 0, "rng_novo": 0, "scheduler_novo": 0, "scan_global": 0, "chamadas_ia": 0},
            "fontes_lidas": [mundo.AGENDA_PATH.as_posix()],
        }
    envelopes, checks, context = collect_repo(repo, start, target, windows)
    result = project_span(windows, envelopes, checks)
    result["aplicavel"] = True
    result["contexto_consultado"] = context
    result["fontes_lidas"] = list(
        dict.fromkeys(
            [mundo.AGENDA_PATH.as_posix(), *(source for check in checks for source in check["fontes"])]
        )
    )[:16]
    if _size(result) > MAX_OUTPUT_BYTES:
        # O contexto auxiliar é diagnóstico; a decisão/cobertura jamais é cortada.
        compact_context = copy.deepcopy(context)
        initiatives = compact_context.get("iniciativas_elenco") or {}
        if isinstance(initiatives, dict):
            initiatives.pop("regra", None)
        ecology = compact_context.get("ecologia_slot") or {}
        if isinstance(ecology, dict):
            ecology.pop("regra", None)
        result["contexto_consultado"] = compact_context
    if _size(result) > MAX_OUTPUT_BYTES:
        raise LivenessBoundaryError(
            f"projeção integrada excede {MAX_OUTPUT_BYTES} bytes sem poder cortar decisão/cobertura"
        )
    return result


def _parts_in_endpoint(value: Any) -> mundo.WorldInstant | None:
    if not isinstance(value, dict):
        return None
    try:
        return mundo.parse_instant(str(value.get("data")), str(value.get("hora")))
    except mundo.WorldEngineError:
        return None


def augment_endpoint(
    repo: Path,
    projected: dict[str, Any],
    *,
    target_date: str,
    target_hour: str,
) -> dict[str, Any]:
    """Acopla NV-14 à mesma consulta de fronteira; nunca exige segundo ritual."""
    if not isinstance(projected, dict):
        return projected
    availability = projected.get("disponibilidade")
    if not isinstance(availability, dict):
        return projected
    start = _parts_in_endpoint(availability.get("inicio"))
    if start is None:
        return projected
    try:
        requested_target = mundo.parse_instant(target_date, target_hour)
    except mundo.WorldEngineError as exc:
        raise LivenessBoundaryError(str(exc)) from exc
    next_step = projected.get("proximo_passo") if isinstance(projected.get("proximo_passo"), dict) else {}
    existing_frontier = _parts_in_endpoint(next_step.get("fronteira"))
    target = requested_target
    if existing_frontier is not None and existing_frontier < target:
        target = existing_frontier
    live = evaluate(repo, target, start=start)
    if live.get("aplicavel") is not True:
        return projected

    result = copy.deepcopy(projected)
    result["fronteira_vivacidade"] = live
    result["fontes_lidas"] = list(
        dict.fromkeys([*(result.get("fontes_lidas") or []), *(live.get("fontes_lidas") or [])])
    )
    filters = list(result.get("filtros") or [])
    if "fronteira_vivacidade_nv14" not in filters:
        filters.append("fronteira_vivacidade_nv14")
    result["filtros"] = filters
    gates = list(result.get("gates") or [])
    first = live.get("primeira_pressao_em")
    if not isinstance(first, dict):
        gates.append(
            {
                "tipo": "fronteira_vivacidade",
                "resultado": "calma_justificada",
                "janelas": live["metricas"]["janelas"],
                "recibos": live["metricas"]["calmas"],
            }
        )
        result["gates"] = gates
        return result

    when = _parts_in_endpoint({"data": first.get("data"), "hora": first.get("hora")})
    if when is None:
        raise LivenessBoundaryError("primeira pressão de vivacidade sem instante válido")
    pressure_id = str(first.get("id"))
    gates.append(
        {
            "tipo": "fronteira_vivacidade",
            "resultado": "pressao_disponivel",
            "id": pressure_id,
        }
    )
    result["gates"] = gates
    ids = result.setdefault("ids", {})
    grouped = ids.get("motivos_por_camada")
    if not isinstance(grouped, dict):
        grouped = {}
    grouped["vivacidade"] = [pressure_id]
    ids["motivos_por_camada"] = grouped
    ids["vivacidade"] = [pressure_id]
    result_next = result.setdefault("proximo_passo", {})
    current = _parts_in_endpoint(result_next.get("fronteira"))
    if current is None or when < current:
        result["disponibilidade"]["alvo_inteiro_sem_checkpoint"] = False
        result_next["acao"] = "atender_pressao_de_vivacidade_antes_de_continuar_compressao"
        result_next["fronteira"] = mundo.instant_parts(when)
        for gate in result["gates"]:
            if isinstance(gate, dict) and gate.get("tipo") == "fronteira_temporal":
                gate["resultado"] = "interromper"
                gate["minutos_ate_fronteira"] = max(0, when.minute - start.minute)
                break
    result_next["vivacidade"] = (
        "use a pressão primária indicada; causas adiadas permanecem no recibo e serão reconsideradas na próxima janela. "
        "Não transformar seleção em ação ou fala de Ren."
    )
    return result


def query(repo: Path, date: str, hour: str) -> dict[str, Any]:
    """Diagnóstico combinado: respeita a primeira fronteira temporal já existente."""
    import fronteira_mundo

    target = mundo.parse_instant(date, hour)
    temporal = fronteira_mundo.next_boundary(repo, target)
    start = mundo.parse_instant(temporal["inicio"]["data"], temporal["inicio"]["hora"])
    effective = target
    if temporal.get("interromper") and isinstance(temporal.get("fronteira"), dict):
        effective = mundo.parse_instant(temporal["fronteira"]["data"], temporal["fronteira"]["hora"])
    return {
        "schema_fronteira_vivacidade_cli": SCHEMA,
        "fronteira_temporal": temporal,
        "vivacidade": evaluate(repo, effective, start=start),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--data", required=True)
    parser.add_argument("--hora", required=True)
    args = parser.parse_args(argv)
    try:
        result = query(args.repo.resolve(), args.data, args.hora)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0
    except (LivenessBoundaryError, ValueError, OSError, yaml.YAMLError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
