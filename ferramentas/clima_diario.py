#!/usr/bin/env python3
"""NV-21 — clima diário determinístico por alvorada e região.

O clima é sorteado no máximo uma vez por data/região por um deck sazonal explícito
ordenado por SHA-256. Cenas nunca sorteiam: apenas leem ``estado/clima-diario.yaml``.
Resultados extremos ficam congelados como candidatos até confirmação explícita.
Quando um estado climático se torna ativo, ele é espelhado como condição persistente
Task 34; o estado climático permanece a autoridade para retry e reparo idempotente.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

import condicoes_mundo
import mundo

CONFIG = Path("narrador/mundo/clima-diario.yaml")
STATE = Path("estado/clima-diario.yaml")
SCHEMA = 1
DEFAULT_REGION = "ravens_bluff"
MAX_HISTORY = 12
MAX_STATE_BYTES = 20 * 1024
MAX_DECK_SLOTS = 64
MAX_SENSORY = 3
MAX_EFFECT_MARKERS = 6
EXTREME_FAMILIES = {"tempestade", "vendaval"}
REGION_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
STATE_ID_RE = re.compile(r"^clima-[0-9a-f]{16}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
VALID_SPACE = {"normal", "desconfortavel", "cautela", "restrito", "indisponivel"}
VALID_INTENSITY = {"leve", "moderada", "forte"}


class ClimateError(ValueError):
    pass


def configured(repo: Path) -> bool:
    root = Path(repo)
    return (root / CONFIG).is_file() and (root / STATE).is_file()


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise ClimateError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ClimateError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ClimateError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str, maximum: int = 240) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ClimateError(f"{label} deve ser texto não vazio")
    result = " ".join(value.strip().split())
    if len(result) > maximum:
        raise ClimateError(f"{label} excede {maximum} caracteres")
    return result


def _region(value: Any) -> str:
    if not isinstance(value, str) or not REGION_RE.fullmatch(value):
        raise ClimateError("região precisa ser slug ASCII minúsculo")
    return value


def _markers(value: Any, label: str, maximum: int = MAX_EFFECT_MARKERS) -> list[str]:
    raw = _list(value, label)
    if len(raw) > maximum:
        raise ClimateError(f"{label} excede {maximum} itens")
    result = [_text(item, label + ".item", 64) for item in raw]
    if result != sorted(set(result)):
        raise ClimateError(f"{label} deve ser ordenado e sem duplicatas")
    if any(not re.fullmatch(r"[a-z0-9][a-z0-9_:-]{0,63}", item) for item in result):
        raise ClimateError(f"{label} contém marcador inválido")
    return result


def atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
        handle.flush()
        os.fsync(handle.fileno())
        temp = Path(handle.name)
    os.replace(temp, path)


def _definition(raw: Any, key: str) -> dict[str, Any]:
    value = _map(raw, f"estados.{key}")
    required = {
        "familia", "extremo", "duracao_horas", "intensidade", "descricao",
        "sensorial", "deslocamento", "espacos", "incidentes", "condicao",
    }
    if set(value) != required:
        raise ClimateError(f"estados.{key} possui campos divergentes")
    family = _text(value["familia"], f"estados.{key}.familia", 40)
    extreme = value["extremo"]
    if not isinstance(extreme, bool) or extreme != (family in EXTREME_FAMILIES):
        raise ClimateError(f"estados.{key}: extremo precisa corresponder à família")
    duration = value["duracao_horas"]
    if isinstance(duration, bool) or not isinstance(duration, int) or not 1 <= duration <= 23:
        raise ClimateError(f"estados.{key}.duracao_horas deve ficar em 1..23")
    if value["intensidade"] not in VALID_INTENSITY:
        raise ClimateError(f"estados.{key}.intensidade inválida")
    description = _text(value["descricao"], f"estados.{key}.descricao", 260)
    sensory = [_text(item, f"estados.{key}.sensorial", 140) for item in _list(value["sensorial"], "sensorial")]
    if not sensory or len(sensory) > MAX_SENSORY:
        raise ClimateError(f"estados.{key}.sensorial deve ter 1..{MAX_SENSORY} itens")
    travel = _map(value["deslocamento"], f"estados.{key}.deslocamento")
    if set(travel) != {"tempo_percentual", "marcadores"}:
        raise ClimateError("deslocamento exige tempo_percentual e marcadores")
    percent = travel["tempo_percentual"]
    if isinstance(percent, bool) or not isinstance(percent, int) or not 100 <= percent <= 200:
        raise ClimateError("tempo_percentual climático deve ficar em 100..200")
    travel_markers = _markers(sorted(travel["marcadores"]), "deslocamento.marcadores")
    spaces = _map(value["espacos"], f"estados.{key}.espacos")
    if set(spaces) != {"exteriores", "expostos", "marcadores"}:
        raise ClimateError("espacos exige exteriores, expostos e marcadores")
    if spaces["exteriores"] not in VALID_SPACE or spaces["expostos"] not in VALID_SPACE:
        raise ClimateError("disponibilidade climática de espaço inválida")
    space_markers = _markers(sorted(spaces["marcadores"]), "espacos.marcadores")
    incidents = _markers(sorted(value["incidentes"]), f"estados.{key}.incidentes")
    condition = _map(value["condicao"], f"estados.{key}.condicao")
    if set(condition) != {"sinais", "marcadores"}:
        raise ClimateError("condicao exige sinais e marcadores")
    signals = [_text(item, f"estados.{key}.condicao.sinais", 140) for item in _list(condition["sinais"], "condicao.sinais")]
    if not 1 <= len(signals) <= 4:
        raise ClimateError("condicao.sinais deve ter 1..4 itens")
    condition_markers = _markers(sorted(condition["marcadores"]), "condicao.marcadores")
    return {
        "familia": family,
        "extremo": extreme,
        "duracao_horas": duration,
        "intensidade": value["intensidade"],
        "descricao": description,
        "sensorial": sensory,
        "deslocamento": {"tempo_percentual": percent, "marcadores": travel_markers},
        "espacos": {
            "exteriores": spaces["exteriores"], "expostos": spaces["expostos"],
            "marcadores": space_markers,
        },
        "incidentes": incidents,
        "condicao": {"sinais": signals, "marcadores": condition_markers},
    }


def load_config(repo: Path) -> dict[str, Any]:
    data = _map(_load(Path(repo) / CONFIG), CONFIG.as_posix())
    if data.get("schema_clima_diario") != SCHEMA or data.get("natureza") != "configuracao_deterministica_reservada":
        raise ClimateError("configuração de clima diário inválida")
    if set(data) != {"schema_clima_diario", "natureza", "semente", "regioes", "estados", "regras"}:
        raise ClimateError("configuração de clima diário possui campos divergentes")
    seed = _text(data["semente"], "semente", 100)
    states_raw = _map(data["estados"], "estados")
    states = {str(key): _definition(raw, str(key)) for key, raw in states_raw.items()}
    if not states:
        raise ClimateError("catálogo climático não pode ser vazio")
    regions_raw = _map(data["regioes"], "regioes")
    regions: dict[str, Any] = {}
    for rid, raw in regions_raw.items():
        rid = _region(rid)
        region = _map(raw, f"regioes.{rid}")
        if set(region) != {"nome", "meses", "festivais", "decks"}:
            raise ClimateError(f"regioes.{rid} possui campos divergentes")
        _text(region["nome"], f"regioes.{rid}.nome", 100)
        months = _map(region["meses"], f"regioes.{rid}.meses")
        if set(months) != set(mundo.MONTHS):
            raise ClimateError(f"regioes.{rid}.meses precisa cobrir os 12 meses de Harptos")
        festivals = _map(region["festivais"], f"regioes.{rid}.festivais")
        if set(festivals) != set(mundo.FESTIVALS):
            raise ClimateError(f"regioes.{rid}.festivais precisa cobrir festivais de Harptos")
        decks_raw = _map(region["decks"], f"regioes.{rid}.decks")
        seasons = set(months.values()) | set(festivals.values())
        if set(decks_raw) != seasons:
            raise ClimateError(f"regioes.{rid}.decks diverge das estações declaradas")
        decks: dict[str, list[str]] = {}
        for season, slots_raw in decks_raw.items():
            slots = _list(slots_raw, f"decks.{season}")
            if not 8 <= len(slots) <= MAX_DECK_SLOTS or any(item not in states for item in slots):
                raise ClimateError(f"deck {season} inválido")
            extreme = sum(states[item]["extremo"] for item in slots)
            ordinary_weather = sum(states[item]["familia"] in {"chuva", "vento"} and not states[item]["extremo"] for item in slots)
            if extreme < 1 or extreme * 10 > len(slots) or ordinary_weather * 4 < len(slots):
                raise ClimateError(f"deck {season} precisa manter extremos raros e chuva/vento comuns plausíveis")
            decks[season] = list(slots)
        regions[rid] = {"nome": region["nome"], "meses": dict(months), "festivais": dict(festivals), "decks": decks}
    rules = _map(data["regras"], "regras")
    if rules.get("avaliacao_por_dia_regiao") != 1 or any(rules.get(k) is not True for k in ("zero_ia", "zero_scheduler_novo", "cena_nao_sorteia", "extremo_exige_confirmacao", "retry_preserva_resultado")):
        raise ClimateError("guardrails do clima diário foram relaxados")
    return {"schema_clima_diario": SCHEMA, "natureza": data["natureza"], "semente": seed, "regioes": regions, "estados": states, "regras": dict(rules)}


def _date_day(date: str) -> int:
    try:
        return mundo.parse_instant(date, "00:00").minute // 1440
    except mundo.WorldEngineError as exc:
        raise ClimateError(str(exc)) from exc


def _date_from_day(day: int) -> str:
    try:
        return mundo.instant_parts(mundo.WorldInstant(day * 1440))["data"]
    except mundo.WorldEngineError as exc:
        raise ClimateError(str(exc)) from exc


def _season(region: dict[str, Any], date: str) -> str:
    month = re.fullmatch(r"\d{1,2}\s+([A-Za-zÀ-ÿ'-]+),\s*\d+\s*DR", date)
    if month:
        name = month.group(1)
        if name not in region["meses"]:
            raise ClimateError(f"mês sem estação climática: {name}")
        return str(region["meses"][name])
    festival = re.fullmatch(r"([A-Za-zÀ-ÿ' -]+),\s*\d+\s*DR", date)
    if festival and festival.group(1).strip() in region["festivais"]:
        return str(region["festivais"][festival.group(1).strip()])
    raise ClimateError(f"data sem estação climática: {date}")


def _dawn_clock(repo: Path) -> str:
    try:
        agenda = _map(_load(Path(repo) / mundo.AGENDA_PATH), mundo.AGENDA_PATH.as_posix())
        value = _text(agenda.get("hora_amanhecer"), "hora_amanhecer", 16)
        mundo.parse_instant("1 Hammer, 1372 DR", value)
        return value
    except (ClimateError, mundo.WorldEngineError) as exc:
        raise ClimateError(str(exc)) from exc


def _sha_payload(value: Any) -> str:
    raw = yaml.safe_dump(value, allow_unicode=True, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _record_without_fingerprint(record: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(record)
    value.pop("fingerprint", None)
    return value


def _make_record(repo: Path, config: dict[str, Any], date: str, region_id: str) -> dict[str, Any]:
    region = config["regioes"][region_id]
    season = _season(region, date)
    deck = region["decks"][season]
    digest = hashlib.sha256(f"{config['semente']}\x1f{region_id}\x1f{date}\x1f{season}".encode("utf-8")).hexdigest()
    slot = int(digest, 16) % len(deck)
    state_id = deck[slot]
    definition = copy.deepcopy(config["estados"][state_id])
    dawn = _dawn_clock(repo)
    start = mundo.parse_instant(date, dawn)
    end = mundo.WorldInstant(start.minute + definition["duracao_horas"] * 60)
    fact = f"Clima NV-21 {date} em {region_id}: {state_id}."
    scope = {"cidade": condicoes_mundo.CITY, "locais": []}
    condition_id = condicoes_mundo.condition_id(
        kind="clima", subject=f"Clima diário — {region_id}", scope=scope,
        start=start, source=STATE.as_posix(), evidence=fact,
    )
    record = {
        "id": "clima-" + hashlib.sha256(f"{region_id}\x1f{date}".encode()).hexdigest()[:16],
        "data": date,
        "regiao": region_id,
        "estacao": season,
        "estado": state_id,
        "extremo": bool(definition["extremo"]),
        "inicio": mundo.instant_parts(start),
        "fim_previsto": mundo.instant_parts(end),
        "duracao_horas": definition["duracao_horas"],
        "intensidade": definition["intensidade"],
        "descricao": definition["descricao"],
        "efeitos": {
            "sensorial": definition["sensorial"],
            "deslocamento": definition["deslocamento"],
            "espacos": definition["espacos"],
            "incidentes": definition["incidentes"],
            "condicao": definition["condicao"],
        },
        "fato_canonico": fact,
        "seed_sha256": digest,
        "slot_indice": slot,
        "condicao_id": condition_id,
    }
    record["fingerprint"] = _sha_payload(record)
    return record


def draw_for_date(repo: Path, *, date: str, region: str = DEFAULT_REGION) -> dict[str, Any]:
    """Sorteio puro/auditável; não lê nem altera o estado climático."""
    config = load_config(Path(repo))
    region = _region(region)
    if region not in config["regioes"]:
        raise ClimateError(f"região climática desconhecida: {region}")
    _date_day(date)
    return _make_record(Path(repo), config, date, region)


def _validate_record(raw: Any, region_id: str, config: dict[str, Any]) -> dict[str, Any]:
    record = _map(raw, "registro climático")
    required = {
        "id", "data", "regiao", "estacao", "estado", "extremo", "inicio", "fim_previsto",
        "duracao_horas", "intensidade", "descricao", "efeitos", "fato_canonico", "seed_sha256",
        "slot_indice", "condicao_id", "fingerprint",
    }
    if set(record) != required or record.get("regiao") != region_id:
        raise ClimateError("registro climático possui campos/região divergentes")
    if not isinstance(record["id"], str) or not STATE_ID_RE.fullmatch(record["id"]):
        raise ClimateError("id climático inválido")
    if record["estado"] not in config["estados"]:
        raise ClimateError("registro climático aponta estado inexistente")
    expected = _make_record(Path(_validation_repo), config, record["data"], region_id) if False else None
    if record["extremo"] != config["estados"][record["estado"]]["extremo"]:
        raise ClimateError("flag extrema diverge do catálogo")
    if not isinstance(record["seed_sha256"], str) or not SHA_RE.fullmatch(record["seed_sha256"]):
        raise ClimateError("seed_sha256 inválido")
    if record["fingerprint"] != _sha_payload(_record_without_fingerprint(record)):
        raise ClimateError("fingerprint climático divergente")
    try:
        start = mundo.parse_instant(record["inicio"]["data"], record["inicio"]["hora"])
        end = mundo.parse_instant(record["fim_previsto"]["data"], record["fim_previsto"]["hora"])
    except (KeyError, TypeError, mundo.WorldEngineError) as exc:
        raise ClimateError("instante climático inválido") from exc
    if end.minute - start.minute != record["duracao_horas"] * 60:
        raise ClimateError("duração climática diverge dos instantes congelados")
    if record["intensidade"] not in VALID_INTENSITY:
        raise ClimateError("intensidade climática inválida")
    _text(record["descricao"], "descrição climática", 260)
    _text(record["fato_canonico"], "fato climático", 160)
    effects = _map(record["efeitos"], "efeitos")
    if set(effects) != {"sensorial", "deslocamento", "espacos", "incidentes", "condicao"}:
        raise ClimateError("efeitos climáticos divergentes")
    definition = config["estados"][record["estado"]]
    expected_effects = {
        "sensorial": definition["sensorial"], "deslocamento": definition["deslocamento"],
        "espacos": definition["espacos"], "incidentes": definition["incidentes"],
        "condicao": definition["condicao"],
    }
    if effects != expected_effects or record["descricao"] != definition["descricao"]:
        raise ClimateError("efeitos climáticos deixaram de corresponder ao resultado congelado")
    return copy.deepcopy(record)


def load_state(repo: Path, config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_config(Path(repo))
    data = _map(_load(Path(repo) / STATE), STATE.as_posix())
    if data.get("schema_clima_diario") != SCHEMA or data.get("natureza") != "estado_climatico_deterministico" or set(data) != {"schema_clima_diario", "natureza", "regioes"}:
        raise ClimateError("estado climático inválido")
    regions_raw = _map(data["regioes"], "regioes")
    if set(regions_raw) != set(config["regioes"]):
        raise ClimateError("estado climático diverge das regiões configuradas")
    regions: dict[str, Any] = {}
    for rid, raw in regions_raw.items():
        region = _map(raw, f"regioes.{rid}")
        if set(region) != {"avaliado_ate", "ativo", "candidato_extremo", "historico_recente"}:
            raise ClimateError(f"estado de {rid} possui campos divergentes")
        evaluated = region["avaliado_ate"]
        if evaluated is not None:
            _date_day(_text(evaluated, f"{rid}.avaliado_ate", 80))
        active = _validate_record(region["ativo"], rid, config) if region["ativo"] is not None else None
        candidate = _validate_record(region["candidato_extremo"], rid, config) if region["candidato_extremo"] is not None else None
        if candidate is not None and candidate["extremo"] is not True:
            raise ClimateError("candidato_extremo precisa ser extremo")
        history_raw = _list(region["historico_recente"], f"{rid}.historico_recente")
        if len(history_raw) > MAX_HISTORY:
            raise ClimateError(f"histórico climático de {rid} excede {MAX_HISTORY}")
        history = [_validate_record(item, rid, config) for item in history_raw]
        regions[rid] = {"avaliado_ate": evaluated, "ativo": active, "candidato_extremo": candidate, "historico_recente": history}
    result = {"schema_clima_diario": SCHEMA, "natureza": "estado_climatico_deterministico", "regioes": regions}
    if len(yaml.safe_dump(result, allow_unicode=True, sort_keys=False).encode("utf-8")) > MAX_STATE_BYTES:
        raise ClimateError(f"estado climático excede {MAX_STATE_BYTES} bytes")
    return result


def _archive(region_state: dict[str, Any], record: dict[str, Any] | None) -> None:
    if record is None:
        return
    if not any(item["id"] == record["id"] for item in region_state["historico_recente"]):
        region_state["historico_recente"].append(copy.deepcopy(record))
        region_state["historico_recente"] = region_state["historico_recente"][-MAX_HISTORY:]


def _record_end(record: dict[str, Any]) -> mundo.WorldInstant:
    return mundo.parse_instant(record["fim_previsto"]["data"], record["fim_previsto"]["hora"])


def _ensure_condition(repo: Path, record: dict[str, Any]) -> dict[str, Any]:
    effects = record["efeitos"]["condicao"]
    try:
        result = condicoes_mundo.register(
            Path(repo), kind="clima", subject=f"Clima diário — {record['regiao']}",
            intensity=record["intensidade"], description=record["descricao"],
            signals=list(effects["sinais"]), markers=list(effects["marcadores"]),
            locals_=[], duration_hours=record["duracao_horas"], source=STATE.as_posix(),
            evidence=record["fato_canonico"],
            now=mundo.parse_instant(record["inicio"]["data"], record["inicio"]["hora"]),
        )
    except condicoes_mundo.WorldConditionError as exc:
        raise ClimateError(str(exc)) from exc
    if result["condicao"]["id"] != record["condicao_id"]:
        raise ClimateError("condição persistente divergiu do id climático congelado")
    return result


def _latest_due_day(now: mundo.WorldInstant, dawn_clock: str) -> int:
    current_day = now.minute // 1440
    dawn_minute = mundo.parse_instant(_date_from_day(current_day), dawn_clock).minute
    return current_day if now.minute >= dawn_minute else current_day - 1


def sync_dawn(repo: Path) -> dict[str, Any]:
    """Avalia cada alvorada ainda não processada, no máximo uma vez por região."""
    repo = Path(repo)
    if not configured(repo) or not (repo / mundo.TIME_PATH).is_file() or not (repo / mundo.AGENDA_PATH).is_file():
        return {"configurado": False, "alterou": False, "avaliacoes": [], "candidatos_extremos": []}
    config = load_config(repo)
    state = load_state(repo, config)
    try:
        now, _ = mundo.load_canonical_time(repo)
    except mundo.WorldEngineError as exc:
        raise ClimateError(str(exc)) from exc
    dawn = _dawn_clock(repo)
    latest = _latest_due_day(now, dawn)
    changed = False
    evaluations: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    for rid in sorted(config["regioes"]):
        rs = state["regioes"][rid]
        active = rs["ativo"]
        if active is not None and now.minute > _record_end(active).minute:
            _archive(rs, active)
            rs["ativo"] = None
            active = None
            changed = True
        if rs["candidato_extremo"] is not None:
            candidates.append(copy.deepcopy(rs["candidato_extremo"]))
            continue
        last = _date_day(rs["avaliado_ate"]) if rs["avaliado_ate"] is not None else latest
        for day in range(last + 1, latest + 1):
            date = _date_from_day(day)
            if rs["ativo"] is not None:
                _archive(rs, rs["ativo"])
                rs["ativo"] = None
            record = _make_record(repo, config, date, rid)
            rs["avaliado_ate"] = date
            changed = True
            evaluations.append({"regiao": rid, "data": date, "estado": record["estado"], "extremo": record["extremo"], "fingerprint": record["fingerprint"]})
            if record["extremo"]:
                rs["candidato_extremo"] = record
                candidates.append(copy.deepcopy(record))
                break
            if day == latest and now.minute <= _record_end(record).minute:
                rs["ativo"] = record
            else:
                _archive(rs, record)

    if changed:
        atomic(repo / STATE, state)
    conditions: list[str] = []
    for rid, rs in state["regioes"].items():
        active = rs["ativo"]
        if active is not None and now.minute <= _record_end(active).minute:
            result = _ensure_condition(repo, active)
            conditions.append(result["condicao"]["id"])
    return {
        "configurado": True,
        "alterou": changed,
        "avaliacoes": evaluations,
        "candidatos_extremos": [
            {"id": item["id"], "regiao": item["regiao"], "data": item["data"], "estado": item["estado"], "fingerprint": item["fingerprint"], "efeitos": copy.deepcopy(item["efeitos"])}
            for item in candidates
        ],
        "condicoes_ativas": conditions,
        "fontes_lidas": [CONFIG.as_posix(), STATE.as_posix(), mundo.TIME_PATH.as_posix(), mundo.AGENDA_PATH.as_posix()],
    }


def confirm_extreme(repo: Path, *, candidate_id: str, expected_fingerprint: str, region: str = DEFAULT_REGION) -> dict[str, Any]:
    repo = Path(repo)
    config = load_config(repo)
    state = load_state(repo, config)
    region = _region(region)
    if region not in state["regioes"]:
        raise ClimateError(f"região climática desconhecida: {region}")
    rs = state["regioes"][region]
    active = rs["ativo"]
    if active is not None and active["id"] == candidate_id:
        if active["fingerprint"] != expected_fingerprint:
            raise ClimateError("fingerprint extremo diverge do resultado já confirmado")
        return {"ok": True, "resultado": "ja_confirmado", "clima": _public(active), "reutilizado": True}
    candidate = rs["candidato_extremo"]
    if candidate is None or candidate["id"] != candidate_id:
        raise ClimateError("candidato extremo inexistente ou substituído")
    if candidate["fingerprint"] != expected_fingerprint:
        raise ClimateError("candidato extremo ficou obsoleto; não é permitido reroll")
    rs["candidato_extremo"] = None
    rs["ativo"] = copy.deepcopy(candidate)
    atomic(repo / STATE, state)
    _ensure_condition(repo, candidate)
    return {"ok": True, "resultado": "confirmado", "clima": _public(candidate), "reutilizado": False}


def _public(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"], "data": record["data"], "regiao": record["regiao"],
        "estado": record["estado"], "intensidade": record["intensidade"],
        "descricao": record["descricao"], "inicio": copy.deepcopy(record["inicio"]),
        "fim_previsto": copy.deepcopy(record["fim_previsto"]),
        "sensorial": list(record["efeitos"]["sensorial"]),
        "deslocamento": copy.deepcopy(record["efeitos"]["deslocamento"]),
        "espacos": copy.deepcopy(record["efeitos"]["espacos"]),
        "incidentes": list(record["efeitos"]["incidentes"]),
        "fingerprint": record["fingerprint"],
    }


def view(repo: Path, *, region: str = DEFAULT_REGION, now: mundo.WorldInstant | None = None) -> dict[str, Any]:
    """Leitura de cena: estado ativo somente; nunca abre deck nem sorteia."""
    repo = Path(repo)
    if not configured(repo):
        return {"configurado": False, "ativo": None, "fontes_lidas": []}
    state_data = _map(_load(repo / STATE), STATE.as_posix())
    regions = _map(state_data.get("regioes"), "regioes")
    region = _region(region)
    raw_region = _map(regions.get(region), f"regioes.{region}")
    active = raw_region.get("ativo")
    sources = [STATE.as_posix()]
    if active is None:
        return {"configurado": True, "regiao": region, "ativo": None, "fontes_lidas": sources}
    if now is None:
        try:
            now, _ = mundo.load_canonical_time(repo)
        except mundo.WorldEngineError as exc:
            raise ClimateError(str(exc)) from exc
        sources.append(mundo.TIME_PATH.as_posix())
    end = mundo.parse_instant(active["fim_previsto"]["data"], active["fim_previsto"]["hora"])
    start = mundo.parse_instant(active["inicio"]["data"], active["inicio"]["hora"])
    if not start.minute <= now.minute <= end.minute:
        return {"configurado": True, "regiao": region, "ativo": None, "fontes_lidas": sources}
    return {"configurado": True, "regiao": region, "ativo": _public(active), "fontes_lidas": sources}


def for_scene(repo: Path, local_id: str, *, now: mundo.WorldInstant | None = None, region: str = DEFAULT_REGION) -> dict[str, Any]:
    result = view(Path(repo), region=region, now=now)
    result["local_id"] = local_id
    result["regra"] = "a cena apenas lê o clima ativo; sorteio ocorre exclusivamente na alvorada"
    return result


def for_travel(repo: Path, *, region: str = DEFAULT_REGION, now: mundo.WorldInstant | None = None) -> dict[str, Any]:
    result = view(Path(repo), region=region, now=now)
    active = result.get("ativo")
    public = None if active is None else {
        "id": active["id"], "estado": active["estado"], "intensidade": active["intensidade"],
        "deslocamento": copy.deepcopy(active["deslocamento"]), "fingerprint": active["fingerprint"],
    }
    return {"configurado": result["configurado"], "regiao": region, "ativo": public, "fontes_lidas": result["fontes_lidas"]}


def status_view(repo: Path, *, region: str = DEFAULT_REGION) -> dict[str, Any]:
    repo = Path(repo)
    if not configured(repo):
        return {"configurado": False}
    config = load_config(repo)
    state = load_state(repo, config)
    rs = state["regioes"][_region(region)]
    return {
        "configurado": True, "regiao": region, "avaliado_ate": rs["avaliado_ate"],
        "ativo": _public(rs["ativo"]) if rs["ativo"] is not None else None,
        "candidato_extremo": (
            {"id": rs["candidato_extremo"]["id"], "data": rs["candidato_extremo"]["data"], "estado": rs["candidato_extremo"]["estado"], "fingerprint": rs["candidato_extremo"]["fingerprint"], "efeitos": copy.deepcopy(rs["candidato_extremo"]["efeitos"])}
            if rs["candidato_extremo"] is not None else None
        ),
    }


def check(repo: Path) -> dict[str, Any]:
    repo = Path(repo)
    errors: list[str] = []
    regions = 0
    try:
        config = load_config(repo)
        state = load_state(repo, config)
        regions = len(config["regioes"])
        if (repo / condicoes_mundo.STATE).is_file():
            conditions = condicoes_mundo.load_state(repo)
            for rs in state["regioes"].values():
                active = rs["ativo"]
                if active is not None and active["condicao_id"] not in conditions["condicoes"]:
                    errors.append(f"condição climática ativa ausente: {active['condicao_id']}")
                candidate = rs["candidato_extremo"]
                if candidate is not None and candidate["condicao_id"] in conditions["condicoes"]:
                    errors.append("candidato extremo não confirmado já materializou condição")
    except (ClimateError, condicoes_mundo.WorldConditionError) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors, "regioes": regions, "erros": list(dict.fromkeys(errors)),
        "avaliacoes_por_dia_regiao": 1, "ia": False, "scheduler_novo": False,
        "rng": "sha256", "fontes_lidas": [CONFIG.as_posix(), STATE.as_posix()],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    sub.add_parser("status")
    sub.add_parser("sincronizar")
    confirm = sub.add_parser("confirmar-extremo")
    confirm.add_argument("--regiao", default=DEFAULT_REGION)
    confirm.add_argument("--id", required=True)
    confirm.add_argument("--fingerprint", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "check":
            result = check(repo)
        elif args.cmd == "status":
            result = status_view(repo)
        elif args.cmd == "sincronizar":
            result = sync_dawn(repo)
        else:
            result = confirm_extreme(repo, region=args.regiao, candidate_id=args.id, expected_fingerprint=args.fingerprint)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0 if result.get("ok", True) else 1
    except ClimateError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
