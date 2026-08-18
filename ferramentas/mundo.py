#!/usr/bin/env python3
"""Motor determinístico e reservado do Mundo Vivo.

Responsabilidades desta etapa:

- ler o tempo canônico atual sem alterá-lo;
- manter um cursor reservado de processamento do mundo;
- materializar pendências determinísticas quando cadências ou horários vencem;
- apontar apenas os IDs dos agentes que precisam ser reconsiderados;
- impedir duplicação quando o mesmo instante é processado novamente.

O motor NÃO decide criativamente o que um agente faz e NÃO altera presença,
plano, relações, relógios ou conhecimento. A resolução narrativa de uma
pendência continua sendo trabalho do narrador/Codex, com consulta dirigida ao
agente necessário.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import agentes

TIME_PATH = Path("estado/tempo.yaml")
AGENDA_PATH = Path("narrador/mundo/agenda.yaml")
WORLD_STATE_PATH = Path("narrador/mundo/estado.yaml")
VALID_SCHEDULE_TYPES = {"reavaliar_agente", "movimento", "expiracao"}
VALID_RECURRENCES = {"amanhecer"}
MAX_RECENT_COMPLETED = 64

MONTHS = (
    "Hammer", "Alturiak", "Ches", "Tarsakh", "Mirtul", "Kythorn",
    "Flamerule", "Eleasis", "Eleint", "Marpenoth", "Uktar", "Nightal",
)
FESTIVAL_AFTER_MONTH = {
    "Hammer": "Midwinter",
    "Tarsakh": "Greengrass",
    "Flamerule": "Midsummer",
    "Eleint": "Highharvestide",
    "Uktar": "Feast of the Moon",
}
FESTIVALS = {
    "Midwinter", "Greengrass", "Midsummer", "Shieldmeet",
    "Highharvestide", "Feast of the Moon",
}


class WorldEngineError(ValueError):
    """Erro de contrato ou de processamento do motor do mundo."""


@dataclass(frozen=True, order=True)
class WorldInstant:
    minute: int


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorldEngineError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise WorldEngineError(f"YAML inválido em {path}: {exc}") from exc


def _require_map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorldEngineError(f"{label} deve ser mapa")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise WorldEngineError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorldEngineError(f"{label} deve ser texto não vazio")
    return value.strip()


def _is_shieldmeet_year(year: int) -> bool:
    return year % 4 == 0


def _days_before_year(year: int) -> int:
    if year < 1:
        raise WorldEngineError("ano DR deve ser positivo")
    return (year - 1) * 365 + (year - 1) // 4


def _year_layout(year: int) -> list[tuple[str, str, int]]:
    layout: list[tuple[str, str, int]] = []
    for month in MONTHS:
        layout.append(("month", month, 30))
        festival = FESTIVAL_AFTER_MONTH.get(month)
        if festival:
            layout.append(("festival", festival, 1))
            if festival == "Midsummer" and _is_shieldmeet_year(year):
                layout.append(("festival", "Shieldmeet", 1))
    return layout


def _date_to_day_index(date_text: str) -> int:
    value = _text(date_text, "data")
    month_match = re.fullmatch(r"(\d{1,2})\s+([A-Za-zÀ-ÿ'-]+),\s*(\d+)\s*DR", value)
    if month_match:
        day = int(month_match.group(1))
        month = month_match.group(2)
        year = int(month_match.group(3))
        if month not in MONTHS:
            raise WorldEngineError(f"mês de Harptos não suportado: {month}")
        if not 1 <= day <= 30:
            raise WorldEngineError(f"dia inválido para {month}: {day}")
        offset = 0
        for kind, name, length in _year_layout(year):
            if kind == "month" and name == month:
                return _days_before_year(year) + offset + day - 1
            offset += length
        raise WorldEngineError(f"não foi possível localizar mês: {month}")

    festival_match = re.fullmatch(r"([A-Za-zÀ-ÿ' -]+),\s*(\d+)\s*DR", value)
    if festival_match:
        festival = festival_match.group(1).strip()
        year = int(festival_match.group(2))
        if festival not in FESTIVALS:
            raise WorldEngineError(f"data de Harptos não suportada: {value}")
        if festival == "Shieldmeet" and not _is_shieldmeet_year(year):
            raise WorldEngineError(f"Shieldmeet não existe em {year} DR")
        offset = 0
        for kind, name, length in _year_layout(year):
            if kind == "festival" and name == festival:
                return _days_before_year(year) + offset
            offset += length
        raise WorldEngineError(f"festival não existe em {year} DR: {festival}")
    raise WorldEngineError(f"formato de data não reconhecido: {value}")


def _day_index_to_date(day_index: int) -> str:
    if day_index < 0:
        raise WorldEngineError("data anterior a 1 DR não suportada")
    year = max(1, day_index // 365 + 1)
    while _days_before_year(year + 1) <= day_index:
        year += 1
    while _days_before_year(year) > day_index:
        year -= 1
    offset = day_index - _days_before_year(year)
    for kind, name, length in _year_layout(year):
        if offset < length:
            if kind == "month":
                return f"{offset + 1} {name}, {year} DR"
            return f"{name}, {year} DR"
        offset -= length
    raise WorldEngineError(f"índice de data fora do calendário: {day_index}")


def _parse_clock(value: str, label: str = "hora") -> int:
    text = _text(value, label)
    match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
    if not match:
        raise WorldEngineError(f"{label} não contém HH:MM válido: {text}")
    return int(match.group(1)) * 60 + int(match.group(2))


def _format_clock(minute_of_day: int) -> str:
    hour, minute = divmod(minute_of_day, 60)
    return f"{hour:02d}:{minute:02d}"


def parse_instant(data: str, hora: str) -> WorldInstant:
    return WorldInstant(_date_to_day_index(data) * 1440 + _parse_clock(hora))


def instant_parts(instant: WorldInstant) -> dict[str, str]:
    day_index, clock = divmod(instant.minute, 1440)
    return {"data": _day_index_to_date(day_index), "hora": _format_clock(clock)}


def _embedded_day_month(hour_text: str) -> tuple[int, str] | None:
    match = re.search(r"\bde\s+(\d{1,2})\s+([A-Za-zÀ-ÿ'-]+)\b", hour_text)
    if not match:
        return None
    return int(match.group(1)), match.group(2)


def load_canonical_time(repo: Path) -> tuple[WorldInstant, dict[str, Any]]:
    data = _require_map(_load_yaml(repo / TIME_PATH), TIME_PATH.as_posix())
    if data.get("schema_tempo") != 1:
        raise WorldEngineError("estado/tempo.yaml deve usar schema_tempo: 1")
    date_text = _text(data.get("data_atual") or data.get("data"), "tempo.data_atual")
    hour_text = _text(data.get("hora_aproximada"), "tempo.hora_aproximada")
    embedded = _embedded_day_month(hour_text)
    if embedded:
        match = re.fullmatch(r"(\d{1,2})\s+([A-Za-zÀ-ÿ'-]+),\s*(\d+)\s*DR", date_text)
        if match and (int(match.group(1)), match.group(2)) != embedded:
            raise WorldEngineError(
                "tempo inconsistente: data_atual diverge do dia/mês em hora_aproximada"
            )
    return parse_instant(date_text, hour_text), data


def load_agenda(repo: Path) -> dict[str, Any]:
    data = _require_map(_load_yaml(repo / AGENDA_PATH), AGENDA_PATH.as_posix())
    if data.get("schema_agenda_mundo") != 1:
        raise WorldEngineError("agenda do mundo deve usar schema_agenda_mundo: 1")
    if data.get("natureza") != "reservado":
        raise WorldEngineError("agenda do mundo deve ter natureza: reservado")
    _parse_clock(_text(data.get("hora_amanhecer"), "agenda.hora_amanhecer"))

    recurrences = data.get("reavaliacoes") or {}
    if not isinstance(recurrences, dict):
        raise WorldEngineError("agenda.reavaliacoes deve ser mapa")
    for agent_id, rule in recurrences.items():
        _text(agent_id, "id de agente em reavaliacoes")
        rule = _require_map(rule, f"reavaliacoes.{agent_id}")
        recurrence = _text(rule.get("cadencia"), f"reavaliacoes.{agent_id}.cadencia")
        if recurrence not in VALID_RECURRENCES:
            raise WorldEngineError(f"cadência inválida para {agent_id}: {recurrence}")
        interval = rule.get("intervalo_dias", 1)
        if not isinstance(interval, int) or interval < 1:
            raise WorldEngineError(
                f"reavaliacoes.{agent_id}.intervalo_dias deve ser inteiro >= 1"
            )
        _date_to_day_index(_text(rule.get("inicio"), f"reavaliacoes.{agent_id}.inicio"))
        _text(rule.get("motivo"), f"reavaliacoes.{agent_id}.motivo")

    schedules = data.get("agendamentos") or []
    if not isinstance(schedules, list):
        raise WorldEngineError("agenda.agendamentos deve ser lista")
    seen: set[str] = set()
    for i, item in enumerate(schedules):
        item = _require_map(item, f"agendamentos[{i}]")
        sid = _text(item.get("id"), f"agendamentos[{i}].id")
        if sid in seen:
            raise WorldEngineError(f"agendamento duplicado: {sid}")
        seen.add(sid)
        stype = _text(item.get("tipo"), f"agendamentos[{i}].tipo")
        if stype not in VALID_SCHEDULE_TYPES:
            raise WorldEngineError(f"tipo de agendamento inválido: {stype}")
        when = _require_map(item.get("em"), f"agendamentos[{i}].em")
        parse_instant(
            _text(when.get("data"), f"agendamentos[{i}].em.data"),
            _text(when.get("hora"), f"agendamentos[{i}].em.hora"),
        )
        agent = item.get("agente")
        if stype in {"reavaliar_agente", "movimento"}:
            _text(agent, f"agendamentos[{i}].agente")
        elif agent is not None:
            _text(agent, f"agendamentos[{i}].agente")
        affected = item.get("agentes_afetados") or []
        if not isinstance(affected, list) or not all(
            isinstance(value, str) and value.strip() for value in affected
        ):
            raise WorldEngineError(
                f"agendamentos[{i}].agentes_afetados deve ser lista de IDs"
            )
        _text(item.get("motivo"), f"agendamentos[{i}].motivo")
    return data


def load_world_state(repo: Path) -> dict[str, Any]:
    data = _require_map(_load_yaml(repo / WORLD_STATE_PATH), WORLD_STATE_PATH.as_posix())
    if data.get("schema_estado_mundo") != 1:
        raise WorldEngineError("estado do mundo deve usar schema_estado_mundo: 1")
    if data.get("natureza") != "controle_reservado":
        raise WorldEngineError("estado do mundo deve ter natureza: controle_reservado")
    cursor = _require_map(data.get("processado_ate"), "estado_mundo.processado_ate")
    parse_instant(
        _text(cursor.get("data"), "estado_mundo.processado_ate.data"),
        _text(cursor.get("hora"), "estado_mundo.processado_ate.hora"),
    )
    pending = _require_list(data.get("pendencias"), "estado_mundo.pendencias")
    completed = _require_list(data.get("concluidas_recentes"), "estado_mundo.concluidas_recentes")
    ids: set[str] = set()
    for i, item in enumerate(pending):
        item = _require_map(item, f"pendencias[{i}]")
        pid = _text(item.get("id"), f"pendencias[{i}].id")
        if pid in ids:
            raise WorldEngineError(f"pendência duplicada: {pid}")
        ids.add(pid)
        _text(item.get("tipo"), f"pendencias[{i}].tipo")
        when = _require_map(item.get("disparado_em"), f"pendencias[{i}].disparado_em")
        parse_instant(
            _text(when.get("data"), f"pendencias[{i}].disparado_em.data"),
            _text(when.get("hora"), f"pendencias[{i}].disparado_em.hora"),
        )
    completed_ids: set[str] = set()
    for i, item in enumerate(completed):
        item = _require_map(item, f"concluidas_recentes[{i}]")
        cid = _text(item.get("id"), f"concluidas_recentes[{i}].id")
        if cid in completed_ids:
            raise WorldEngineError(f"conclusão recente duplicada: {cid}")
        completed_ids.add(cid)
    return data


def _state_cursor(state: dict[str, Any]) -> WorldInstant:
    cursor = state["processado_ate"]
    return parse_instant(cursor["data"], cursor["hora"])


def _pending_id(kind: str, source: str, when: WorldInstant) -> str:
    raw = f"{kind}|{source}|{when.minute}".encode("utf-8")
    return "mundo-" + hashlib.sha256(raw).hexdigest()[:16]


def _dawn_minute(agenda: dict[str, Any]) -> int:
    return _parse_clock(agenda["hora_amanhecer"])


def _iter_day_indices(start: WorldInstant, end: WorldInstant) -> Iterable[int]:
    if end <= start:
        return ()
    return range(start.minute // 1440, end.minute // 1440 + 1)


def _recurrence_triggers(
    agenda: dict[str, Any], start: WorldInstant, end: WorldInstant
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    dawn = _dawn_minute(agenda)
    for agent_id, rule in (agenda.get("reavaliacoes") or {}).items():
        start_day = _date_to_day_index(rule["inicio"])
        interval = int(rule.get("intervalo_dias", 1))
        for day_index in _iter_day_indices(start, end):
            if day_index < start_day or (day_index - start_day) % interval:
                continue
            when = WorldInstant(day_index * 1440 + dawn)
            if not (start < when <= end):
                continue
            source = f"reavaliacoes.{agent_id}"
            result.append(
                {
                    "id": _pending_id("reavaliar_agente", source, when),
                    "tipo": "reavaliar_agente",
                    "agente": agent_id,
                    "agentes_afetados": [agent_id],
                    "disparado_em": instant_parts(when),
                    "motivo": rule["motivo"],
                    "origem": f"agenda:{source}",
                }
            )
    return result


def _scheduled_triggers(
    agenda: dict[str, Any], start: WorldInstant, end: WorldInstant
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in agenda.get("agendamentos") or []:
        when = parse_instant(item["em"]["data"], item["em"]["hora"])
        if not (start < when <= end):
            continue
        affected = list(item.get("agentes_afetados") or [])
        agent = item.get("agente")
        if agent and agent not in affected:
            affected.insert(0, agent)
        source = f"agendamentos.{item['id']}"
        record = {
            "id": _pending_id(item["tipo"], source, when),
            "tipo": item["tipo"],
            "agentes_afetados": affected,
            "disparado_em": instant_parts(when),
            "motivo": item["motivo"],
            "origem": f"agenda:{source}",
        }
        if agent:
            record["agente"] = agent
        result.append(record)
    return result


def collect_triggers(
    agenda: dict[str, Any], start: WorldInstant, end: WorldInstant
) -> list[dict[str, Any]]:
    triggers = _recurrence_triggers(agenda, start, end)
    triggers.extend(_scheduled_triggers(agenda, start, end))
    triggers.sort(
        key=lambda item: (
            parse_instant(item["disparado_em"]["data"], item["disparado_em"]["hora"]).minute,
            item["id"],
        )
    )
    return triggers


def _referenced_agents(records: Iterable[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for record in records:
        agent = record.get("agente")
        if isinstance(agent, str) and agent:
            result.add(agent)
        for item in record.get("agentes_afetados") or []:
            if isinstance(item, str) and item:
                result.add(item)
    return result


def _validate_agent_ids_if_needed(repo: Path, records: list[dict[str, Any]]) -> list[str]:
    ids = _referenced_agents(records)
    if not ids:
        return []
    index = agentes.load_index(repo)
    known = set(index["agentes"])
    missing = sorted(ids - known)
    if missing:
        raise WorldEngineError(
            "agenda produziu referência para agente inexistente: " + ", ".join(missing)
        )
    return [agentes.INDEX_PATH.as_posix()]


def _atomic_write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _merge_pending(state: dict[str, Any], emitted: list[dict[str, Any]]) -> list[dict[str, Any]]:
    existing = {item["id"] for item in state["pendencias"]}
    completed = {item["id"] for item in state["concluidas_recentes"]}
    added: list[dict[str, Any]] = []
    for item in emitted:
        if item["id"] in existing or item["id"] in completed:
            continue
        state["pendencias"].append(item)
        existing.add(item["id"])
        added.append(item)
    return added


def process_until(repo: Path, target: WorldInstant) -> dict[str, Any]:
    canonical, _ = load_canonical_time(repo)
    agenda = load_agenda(repo)
    state = load_world_state(repo)
    cursor = _state_cursor(state)
    if cursor > canonical:
        raise WorldEngineError(
            "cursor do mundo está à frente do tempo canônico; recupere o estado antes de processar"
        )
    if target > canonical:
        raise WorldEngineError("mundo.py não pode processar além do tempo canônico")
    if target < cursor:
        raise WorldEngineError("mundo.py não pode retroceder o cursor de processamento")

    base_sources = [TIME_PATH.as_posix(), AGENDA_PATH.as_posix(), WORLD_STATE_PATH.as_posix()]
    if target == cursor:
        return {
            "ok": True,
            "alterou": False,
            "processado_de": instant_parts(cursor),
            "processado_ate": instant_parts(target),
            "novas_pendencias": [],
            "agentes_reconsiderar": [],
            "fontes_lidas": base_sources,
        }

    emitted = collect_triggers(agenda, cursor, target)
    extra_sources = _validate_agent_ids_if_needed(repo, emitted)
    added = _merge_pending(state, emitted)
    state["processado_ate"] = instant_parts(target)
    _atomic_write_yaml(repo / WORLD_STATE_PATH, state)
    return {
        "ok": True,
        "alterou": True,
        "processado_de": instant_parts(cursor),
        "processado_ate": instant_parts(target),
        "novas_pendencias": added,
        "agentes_reconsiderar": sorted(_referenced_agents(added)),
        "fontes_lidas": [*base_sources, *extra_sources],
    }


def process_to_canonical(repo: Path) -> dict[str, Any]:
    canonical, _ = load_canonical_time(repo)
    return process_until(repo, canonical)


def _latest_dawn_at_or_before(current: WorldInstant, dawn: int) -> WorldInstant:
    day, clock = divmod(current.minute, 1440)
    if clock >= dawn:
        return WorldInstant(day * 1440 + dawn)
    return WorldInstant((day - 1) * 1440 + dawn)


def process_dawn(repo: Path) -> dict[str, Any]:
    canonical, _ = load_canonical_time(repo)
    agenda = load_agenda(repo)
    state = load_world_state(repo)
    cursor = _state_cursor(state)
    if cursor > canonical:
        raise WorldEngineError("cursor do mundo está à frente do tempo canônico")
    target = _latest_dawn_at_or_before(canonical, _dawn_minute(agenda))
    if target < cursor:
        return {
            "ok": True,
            "alterou": False,
            "motivo": "nenhum amanhecer novo alcançado desde o último processamento",
            "processado_ate": instant_parts(cursor),
            "novas_pendencias": [],
            "agentes_reconsiderar": [],
            "fontes_lidas": [TIME_PATH.as_posix(), AGENDA_PATH.as_posix(), WORLD_STATE_PATH.as_posix()],
        }
    return process_until(repo, target)


def pending_view(repo: Path) -> dict[str, Any]:
    state = load_world_state(repo)
    pending = list(state["pendencias"])
    return {
        "quantidade": len(pending),
        "agentes_reconsiderar": sorted(_referenced_agents(pending)),
        "pendencias": pending,
        "fontes_lidas": [WORLD_STATE_PATH.as_posix()],
    }


def _next_trigger(agenda: dict[str, Any], after: WorldInstant) -> dict[str, Any] | None:
    horizon = WorldInstant(after.minute + 367 * 1440)
    candidates = _recurrence_triggers(agenda, after, horizon)
    candidates.extend(_scheduled_triggers(agenda, after, horizon))
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: parse_instant(
            item["disparado_em"]["data"], item["disparado_em"]["hora"]
        ).minute
    )
    return candidates[0]


def status_view(repo: Path) -> dict[str, Any]:
    canonical, _ = load_canonical_time(repo)
    agenda = load_agenda(repo)
    state = load_world_state(repo)
    cursor = _state_cursor(state)
    return {
        "tempo_canonico": instant_parts(canonical),
        "processado_ate": instant_parts(cursor),
        "atraso_minutos": max(0, canonical.minute - cursor.minute),
        "pendencias": len(state["pendencias"]),
        "agentes_reconsiderar": sorted(_referenced_agents(state["pendencias"])),
        "proximo_disparo": _next_trigger(agenda, cursor),
        "fontes_lidas": [TIME_PATH.as_posix(), AGENDA_PATH.as_posix(), WORLD_STATE_PATH.as_posix()],
    }


def conclude(repo: Path, pending_id: str, note: str | None = None) -> dict[str, Any]:
    state = load_world_state(repo)
    matches = [item for item in state["pendencias"] if item["id"] == pending_id]
    if not matches:
        raise WorldEngineError(f"pendência não encontrada: {pending_id}")
    item = matches[0]
    state["pendencias"] = [record for record in state["pendencias"] if record["id"] != pending_id]
    completed = {
        "id": pending_id,
        "tipo": item["tipo"],
        "disparado_em": item["disparado_em"],
    }
    if item.get("agente"):
        completed["agente"] = item["agente"]
    if note:
        completed["nota"] = note
    state["concluidas_recentes"].append(completed)
    state["concluidas_recentes"] = state["concluidas_recentes"][-MAX_RECENT_COMPLETED:]
    _atomic_write_yaml(repo / WORLD_STATE_PATH, state)
    return {
        "ok": True,
        "concluida": completed,
        "pendencias_restantes": len(state["pendencias"]),
        "fontes_lidas": [WORLD_STATE_PATH.as_posix()],
    }


def check_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        canonical, _ = load_canonical_time(repo)
        agenda = load_agenda(repo)
        state = load_world_state(repo)
        cursor = _state_cursor(state)
        if cursor > canonical:
            errors.append("estado do mundo está processado além do tempo canônico")

        index = agentes.load_index(repo)
        known = set(index["agentes"])
        referenced: set[str] = set((agenda.get("reavaliacoes") or {}).keys())
        for item in agenda.get("agendamentos") or []:
            if item.get("agente"):
                referenced.add(item["agente"])
            referenced.update(item.get("agentes_afetados") or [])
        referenced.update(_referenced_agents(state["pendencias"]))
        missing = sorted(referenced - known)
        if missing:
            errors.append("agentes inexistentes referenciados: " + ", ".join(missing))

        pending_ids = {item["id"] for item in state["pendencias"]}
        completed_ids = {item["id"] for item in state["concluidas_recentes"]}
        overlap = sorted(pending_ids & completed_ids)
        if overlap:
            errors.append("IDs simultaneamente pendentes e concluídos: " + ", ".join(overlap))
    except (WorldEngineError, agentes.AgentValidationError) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "erros": errors,
        "fontes_lidas": [
            TIME_PATH.as_posix(), AGENDA_PATH.as_posix(), WORLD_STATE_PATH.as_posix(),
            agentes.INDEX_PATH.as_posix(),
        ],
    }


def _dump(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="raiz do repositório")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="mostra cursor, tempo canônico e próximo disparo")
    sub.add_parser("pendentes", help="lista decisões de mundo ainda não resolvidas")
    sub.add_parser("amanhecer", help="processa somente até o último amanhecer alcançado")
    sub.add_parser("avancar", help="processa do cursor até o tempo canônico atual")
    sub.add_parser("check", help="valida agenda, cursor, fila e referências")
    done = sub.add_parser("concluir", help="marca uma pendência como avaliada")
    done.add_argument("id")
    done.add_argument("--nota")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.command == "status":
            result = status_view(repo)
        elif args.command == "pendentes":
            result = pending_view(repo)
        elif args.command == "amanhecer":
            result = process_dawn(repo)
        elif args.command == "avancar":
            result = process_to_canonical(repo)
        elif args.command == "concluir":
            result = conclude(repo, args.id, args.nota)
        else:
            result = check_repo(repo)
        print(_dump(result), end="")
        if args.command == "check":
            return 0 if result["ok"] else 1
        return 0
    except (WorldEngineError, agentes.AgentValidationError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
