#!/usr/bin/env python3
"""Condições persistentes e multi-dia do mundo, sem scheduler.

A Task 34 representa fatos ambientais/sociais que duram mais de uma cena — clima,
escassez, greve, festival, toque de recolher e problemas portuários — como estado
canônico compacto. Nada avança sozinho: início/fim são comparados ao relógio
canônico somente em leitura, e uma condição expirada simplesmente deixa de ser
projetada. Escritas futuras podem compactá-la para histórico.

Registrar/encerrar exige evidência literal em fonte canônica não reservada. O
estado reservado guarda causalidade; a projeção pública omite fonte/evidência.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

import yaml

import locais
import mundo

STATE = Path("narrador/mundo/condicoes-persistentes.yaml")
CITY = "ravens_bluff"
SCHEMA = 1
VALID_TYPES = {
    "clima",
    "escassez",
    "greve",
    "festival",
    "toque_de_recolher",
    "porto",
}
VALID_INTENSITIES = {"leve", "moderada", "forte"}
MAX_CONDITIONS = 8
MAX_HISTORY = 16
MAX_LOCALS = 8
MAX_SIGNALS = 4
MAX_MARKERS = 6
MAX_DESCRIPTION = 260
MAX_SIGNAL = 140
MAX_SUBJECT = 80
MAX_EVIDENCE = 220
MAX_SOURCE = 120
MAX_DURATION_HOURS = 24 * 30
MAX_STATE_BYTES = 12 * 1024
ID_RE = re.compile(r"^cnd-[0-9a-f]{16}$")
MARKER_RE = re.compile(r"^[a-z0-9][a-z0-9_:-]{0,63}$")
CANONICAL_SOURCE_ROOTS = {"sessoes", "historico", "estado"}


class WorldConditionError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise WorldConditionError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorldConditionError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise WorldConditionError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str, *, maximum: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorldConditionError(f"{label} deve ser texto não vazio")
    result = " ".join(value.strip().split())
    if maximum is not None and len(result) > maximum:
        raise WorldConditionError(f"{label} excede {maximum} caracteres")
    return result


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return " ".join(ascii_text.lower().split())


def _instant(value: Any, label: str) -> mundo.WorldInstant:
    raw = _map(value, label)
    if set(raw) != {"data", "hora"}:
        raise WorldConditionError(f"{label} deve conter exatamente data e hora")
    try:
        return mundo.parse_instant(
            _text(raw["data"], label + ".data"),
            _text(raw["hora"], label + ".hora"),
        )
    except mundo.WorldEngineError as exc:
        raise WorldConditionError(str(exc)) from exc


def _source_rel(value: Any) -> Path:
    text = _text(value, "fonte", maximum=MAX_SOURCE)
    rel = Path(text)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise WorldConditionError("fonte deve ser caminho relativo canônico")
    if rel.parts[0] not in CANONICAL_SOURCE_ROOTS:
        raise WorldConditionError(
            "fonte de condição precisa vir de sessoes/, historico/ ou estado/; narrador/runtime não canonizam fato"
        )
    return rel


def _validate_evidence(repo: Path, source: Any, evidence: Any) -> tuple[str, str]:
    rel = _source_rel(source)
    literal = _text(evidence, "evidencia", maximum=MAX_EVIDENCE)
    if len(literal) < 12:
        raise WorldConditionError("evidencia precisa ter pelo menos 12 caracteres")
    path = repo / rel
    if not path.is_file():
        raise WorldConditionError(f"fonte canônica inexistente: {rel.as_posix()}")
    try:
        body = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise WorldConditionError(f"fonte não é UTF-8: {rel.as_posix()}") from exc
    if literal not in body:
        raise WorldConditionError("evidencia precisa ocorrer literalmente na fonte canônica")
    return rel.as_posix(), literal


def atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
        handle.flush()
        os.fsync(handle.fileno())
        temp = Path(handle.name)
    os.replace(temp, path)


def _scope(raw: Any, label: str = "escopo") -> dict[str, Any]:
    value = _map(raw, label)
    if set(value) != {"cidade", "locais"}:
        raise WorldConditionError(f"{label} deve conter somente cidade e locais")
    if value.get("cidade") != CITY:
        raise WorldConditionError(f"{label}.cidade deve ser {CITY}")
    local_ids = _list(value.get("locais"), label + ".locais")
    if len(local_ids) > MAX_LOCALS:
        raise WorldConditionError(f"{label}.locais excede {MAX_LOCALS}")
    if any(not isinstance(item, str) or not item.strip() for item in local_ids):
        raise WorldConditionError(f"{label}.locais deve conter ids não vazios")
    if local_ids != sorted(set(local_ids)):
        raise WorldConditionError(f"{label}.locais deve ser ordenado e sem duplicatas")
    return {"cidade": CITY, "locais": list(local_ids)}


def _record(raw: Any, expected_id: str | None = None) -> dict[str, Any]:
    item = _map(raw, "condicao")
    allowed = {
        "id", "tipo", "assunto", "intensidade", "escopo", "inicio",
        "fim_previsto", "descricao", "sinais", "marcadores", "fonte", "evidencia",
    }
    if set(item) != allowed:
        extra = set(item) - allowed
        missing = allowed - set(item)
        raise WorldConditionError(
            "condição possui campos divergentes: "
            + ("extras=" + ",".join(sorted(extra)) if extra else "")
            + (" ausentes=" + ",".join(sorted(missing)) if missing else "")
        )
    cid = _text(item.get("id"), "condicao.id")
    if not ID_RE.fullmatch(cid) or (expected_id is not None and cid != expected_id):
        raise WorldConditionError(f"id de condição inválido: {cid!r}")
    kind = _text(item.get("tipo"), f"{cid}.tipo")
    if kind not in VALID_TYPES:
        raise WorldConditionError(f"{cid}: tipo inválido: {kind}")
    subject = _text(item.get("assunto"), f"{cid}.assunto", maximum=MAX_SUBJECT)
    intensity = _text(item.get("intensidade"), f"{cid}.intensidade")
    if intensity not in VALID_INTENSITIES:
        raise WorldConditionError(f"{cid}: intensidade inválida: {intensity}")
    scope = _scope(item.get("escopo"), f"{cid}.escopo")
    start = _instant(item.get("inicio"), f"{cid}.inicio")
    end_raw = item.get("fim_previsto")
    end = _instant(end_raw, f"{cid}.fim_previsto") if end_raw is not None else None
    if end is not None and end.minute <= start.minute:
        raise WorldConditionError(f"{cid}: fim_previsto precisa ser posterior ao início")
    description = _text(item.get("descricao"), f"{cid}.descricao", maximum=MAX_DESCRIPTION)
    signals = _list(item.get("sinais"), f"{cid}.sinais")
    if len(signals) > MAX_SIGNALS:
        raise WorldConditionError(f"{cid}: sinais excedem {MAX_SIGNALS}")
    signals = [_text(value, f"{cid}.sinal", maximum=MAX_SIGNAL) for value in signals]
    markers = _list(item.get("marcadores"), f"{cid}.marcadores")
    if len(markers) > MAX_MARKERS:
        raise WorldConditionError(f"{cid}: marcadores excedem {MAX_MARKERS}")
    if any(not isinstance(value, str) or not MARKER_RE.fullmatch(value) for value in markers):
        raise WorldConditionError(f"{cid}: marcador inválido")
    if markers != sorted(set(markers)):
        raise WorldConditionError(f"{cid}: marcadores devem ser ordenados e únicos")
    source = _source_rel(item.get("fonte")).as_posix()
    evidence = _text(item.get("evidencia"), f"{cid}.evidencia", maximum=MAX_EVIDENCE)
    return {
        "id": cid,
        "tipo": kind,
        "assunto": subject,
        "intensidade": intensity,
        "escopo": scope,
        "inicio": mundo.instant_parts(start),
        "fim_previsto": mundo.instant_parts(end) if end is not None else None,
        "descricao": description,
        "sinais": signals,
        "marcadores": markers,
        "fonte": source,
        "evidencia": evidence,
    }


def _history_item(raw: Any) -> dict[str, Any]:
    item = _map(raw, "historico_recente")
    allowed = {"id", "tipo", "assunto", "encerrada_em", "motivo", "fonte"}
    if set(item) != allowed:
        raise WorldConditionError("histórico de condição possui campos inesperados")
    cid = _text(item.get("id"), "historico.id")
    if not ID_RE.fullmatch(cid):
        raise WorldConditionError("histórico possui id inválido")
    kind = _text(item.get("tipo"), f"historico.{cid}.tipo")
    if kind not in VALID_TYPES:
        raise WorldConditionError("histórico possui tipo inválido")
    subject = _text(item.get("assunto"), f"historico.{cid}.assunto", maximum=MAX_SUBJECT)
    ended = _instant(item.get("encerrada_em"), f"historico.{cid}.encerrada_em")
    reason = _text(item.get("motivo"), f"historico.{cid}.motivo", maximum=160)
    source = _source_rel(item.get("fonte")).as_posix()
    return {
        "id": cid,
        "tipo": kind,
        "assunto": subject,
        "encerrada_em": mundo.instant_parts(ended),
        "motivo": reason,
        "fonte": source,
    }


def load_state(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / STATE), STATE.as_posix())
    if (
        data.get("schema_condicoes_mundo") != SCHEMA
        or data.get("natureza") != "controle_reservado"
        or data.get("cidade") != CITY
        or set(data) != {"schema_condicoes_mundo", "natureza", "cidade", "condicoes", "historico_recente"}
    ):
        raise WorldConditionError("estado de condições persistentes inválido")
    conditions = _map(data.get("condicoes"), "condicoes")
    if len(conditions) > MAX_CONDITIONS:
        raise WorldConditionError(f"estado excede {MAX_CONDITIONS} condições")
    clean_conditions: dict[str, Any] = {}
    semantic: set[tuple[str, str, tuple[str, ...]]] = set()
    for cid, raw in conditions.items():
        rec = _record(raw, str(cid))
        key = (rec["tipo"], _slug(rec["assunto"]), tuple(rec["escopo"]["locais"]))
        if key in semantic:
            raise WorldConditionError("duas condições abertas duplicam tipo/assunto/escopo")
        semantic.add(key)
        clean_conditions[cid] = rec
    history = _list(data.get("historico_recente"), "historico_recente")
    if len(history) > MAX_HISTORY:
        raise WorldConditionError(f"histórico excede {MAX_HISTORY} entradas")
    clean_history = [_history_item(item) for item in history]
    result = {
        "schema_condicoes_mundo": SCHEMA,
        "natureza": "controle_reservado",
        "cidade": CITY,
        "condicoes": clean_conditions,
        "historico_recente": clean_history,
    }
    size = len(yaml.safe_dump(result, allow_unicode=True, sort_keys=False).encode("utf-8"))
    if size > MAX_STATE_BYTES:
        raise WorldConditionError(f"estado excede orçamento: {size} > {MAX_STATE_BYTES} bytes")
    return result


def _canonical_now(repo: Path, now: mundo.WorldInstant | None) -> tuple[mundo.WorldInstant, list[str]]:
    if now is not None:
        return now, []
    try:
        current, _ = mundo.load_canonical_time(repo)
    except mundo.WorldEngineError as exc:
        raise WorldConditionError(str(exc)) from exc
    return current, [mundo.TIME_PATH.as_posix()]


def _is_active(record: dict[str, Any], now: mundo.WorldInstant) -> bool:
    start = _instant(record["inicio"], "inicio")
    end = _instant(record["fim_previsto"], "fim_previsto") if record.get("fim_previsto") else None
    return start.minute <= now.minute and (end is None or now.minute <= end.minute)


def _is_expired(record: dict[str, Any], now: mundo.WorldInstant) -> bool:
    end = _instant(record["fim_previsto"], "fim_previsto") if record.get("fim_previsto") else None
    return end is not None and now.minute > end.minute


def _applies(record: dict[str, Any], local_id: str | None) -> bool:
    local_ids = record["escopo"]["locais"]
    if not local_ids:
        return True
    return local_id is not None and local_id in local_ids


def _public(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "tipo": record["tipo"],
        "assunto": record["assunto"],
        "intensidade": record["intensidade"],
        "descricao": record["descricao"],
        "sinais": list(record["sinais"]),
        "marcadores": list(record["marcadores"]),
        "fim_previsto": record["fim_previsto"],
    }


def project(
    repo: Path,
    *,
    local_id: str | None = None,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    state = load_state(repo)
    sources = [STATE.as_posix()]
    if not state["condicoes"]:
        return {
            "schema_condicoes_mundo": SCHEMA,
            "cidade": CITY,
            "local_id": local_id,
            "ativas": [],
            "fontes_lidas": sources,
            "regra": "condições persistentes são contexto; não criam teste, penalidade, evento ou NPC automaticamente",
        }
    current, time_sources = _canonical_now(repo, now)
    sources.extend(time_sources)
    active = [
        _public(record)
        for record in state["condicoes"].values()
        if _is_active(record, current) and _applies(record, local_id)
    ]
    active.sort(key=lambda item: (item["tipo"], item["id"]))
    return {
        "schema_condicoes_mundo": SCHEMA,
        "cidade": CITY,
        "local_id": local_id,
        "ativas": active,
        "fontes_lidas": list(dict.fromkeys(sources)),
        "regra": "condições persistentes são contexto; não criam teste, penalidade, evento ou NPC automaticamente",
    }


def for_scene(repo: Path, local_id: str, *, now: mundo.WorldInstant | None = None) -> dict[str, Any]:
    if not isinstance(local_id, str) or not local_id.strip():
        raise WorldConditionError("cena precisa de local_id canônico não vazio")
    return project(repo, local_id=local_id.strip(), now=now)


def show(repo: Path, *, local: str | None = None, now: mundo.WorldInstant | None = None) -> dict[str, Any]:
    local_id = None
    sources: list[str] = []
    if local is not None:
        try:
            resolved = locais.resolve(repo, local)
        except locais.LocationError as exc:
            raise WorldConditionError(str(exc)) from exc
        local_id = resolved["local_id"]
        sources.extend(resolved.get("fontes_lidas") or [])
    result = project(repo, local_id=local_id, now=now)
    result["fontes_lidas"] = list(dict.fromkeys([*sources, *result["fontes_lidas"]]))
    return result


def _history_from(record: dict[str, Any], ended: mundo.WorldInstant, reason: str, source: str) -> dict[str, Any]:
    return {
        "id": record["id"],
        "tipo": record["tipo"],
        "assunto": record["assunto"],
        "encerrada_em": mundo.instant_parts(ended),
        "motivo": reason,
        "fonte": source,
    }


def _append_history(state: dict[str, Any], item: dict[str, Any]) -> None:
    state["historico_recente"].append(item)
    state["historico_recente"] = state["historico_recente"][-MAX_HISTORY:]


def _compact_expired(state: dict[str, Any], now: mundo.WorldInstant) -> int:
    expired = [cid for cid, record in state["condicoes"].items() if _is_expired(record, now)]
    for cid in sorted(expired):
        record = state["condicoes"].pop(cid)
        ended = _instant(record["fim_previsto"], f"{cid}.fim_previsto")
        _append_history(
            state,
            _history_from(record, ended, "fim_previsto_alcancado", record["fonte"]),
        )
    return len(expired)


def _resolve_scope(repo: Path, local_terms: list[str]) -> tuple[dict[str, Any], list[str]]:
    ids: set[str] = set()
    sources: list[str] = []
    for term in local_terms:
        try:
            resolved = locais.resolve(repo, term)
        except locais.LocationError as exc:
            raise WorldConditionError(str(exc)) from exc
        ids.add(resolved["local_id"])
        sources.extend(resolved.get("fontes_lidas") or [])
    if len(ids) > MAX_LOCALS:
        raise WorldConditionError(f"escopo excede {MAX_LOCALS} locais")
    return {"cidade": CITY, "locais": sorted(ids)}, list(dict.fromkeys(sources))


def condition_id(
    *, kind: str, subject: str, scope: dict[str, Any], start: mundo.WorldInstant,
    source: str, evidence: str,
) -> str:
    raw = "\x1f".join(
        [kind, _slug(subject), ",".join(scope["locais"]), str(start.minute), source, evidence]
    )
    return "cnd-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def register(
    repo: Path,
    *,
    kind: str,
    subject: str,
    intensity: str,
    description: str,
    signals: list[str] | None,
    markers: list[str] | None,
    locals_: list[str] | None,
    duration_hours: int | None,
    source: str,
    evidence: str,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    if kind not in VALID_TYPES:
        raise WorldConditionError("tipo deve ser: " + ", ".join(sorted(VALID_TYPES)))
    subject = _text(subject, "assunto", maximum=MAX_SUBJECT)
    if intensity not in VALID_INTENSITIES:
        raise WorldConditionError("intensidade deve ser leve, moderada ou forte")
    description = _text(description, "descricao", maximum=MAX_DESCRIPTION)
    signals = [_text(item, "sinal", maximum=MAX_SIGNAL) for item in list(signals or [])]
    if len(signals) > MAX_SIGNALS:
        raise WorldConditionError(f"sinais excedem {MAX_SIGNALS}")
    markers = sorted(set(_text(item, "marcador") for item in list(markers or [])))
    if len(markers) > MAX_MARKERS or any(not MARKER_RE.fullmatch(item) for item in markers):
        raise WorldConditionError("marcadores inválidos ou acima do teto")
    if duration_hours is not None and (
        isinstance(duration_hours, bool)
        or not isinstance(duration_hours, int)
        or not 1 <= duration_hours <= MAX_DURATION_HOURS
    ):
        raise WorldConditionError(f"duracao_horas deve ficar entre 1 e {MAX_DURATION_HOURS}")

    start, time_sources = _canonical_now(repo, now)
    scope, scope_sources = _resolve_scope(repo, list(locals_ or []))
    source_path, evidence_literal = _validate_evidence(repo, source, evidence)
    end = (
        mundo.WorldInstant(start.minute + duration_hours * 60)
        if duration_hours is not None
        else None
    )
    cid = condition_id(
        kind=kind,
        subject=subject,
        scope=scope,
        start=start,
        source=source_path,
        evidence=evidence_literal,
    )
    record = _record(
        {
            "id": cid,
            "tipo": kind,
            "assunto": subject,
            "intensidade": intensity,
            "escopo": scope,
            "inicio": mundo.instant_parts(start),
            "fim_previsto": mundo.instant_parts(end) if end is not None else None,
            "descricao": description,
            "sinais": signals,
            "marcadores": markers,
            "fonte": source_path,
            "evidencia": evidence_literal,
        },
        cid,
    )
    state = load_state(repo)
    compacted = _compact_expired(state, start)
    existing = state["condicoes"].get(cid)
    if existing is not None:
        if existing != record:
            raise WorldConditionError(f"colisão de id de condição: {cid}")
        return {
            "ok": True,
            "resultado": "ja_registrada",
            "condicao": _public(existing),
            "compactadas": compacted,
            "fontes_lidas": list(dict.fromkeys([STATE.as_posix(), *time_sources, *scope_sources, source_path])),
        }
    semantic_key = (kind, _slug(subject), tuple(scope["locais"]))
    for current in state["condicoes"].values():
        key = (current["tipo"], _slug(current["assunto"]), tuple(current["escopo"]["locais"]))
        if key == semantic_key:
            raise WorldConditionError(
                "já existe condição aberta com mesmo tipo, assunto e escopo; encerre-a antes de registrar outra"
            )
    if len(state["condicoes"]) >= MAX_CONDITIONS:
        raise WorldConditionError(f"estado já possui {MAX_CONDITIONS} condições abertas")
    state["condicoes"][cid] = record
    state = load_state_from_value(state)
    atomic(repo / STATE, state)
    return {
        "ok": True,
        "resultado": "registrada",
        "condicao": _public(record),
        "compactadas": compacted,
        "fontes_lidas": list(dict.fromkeys([STATE.as_posix(), *time_sources, *scope_sources, source_path])),
    }


def load_state_from_value(data: dict[str, Any]) -> dict[str, Any]:
    """Valida uma sombra em memória com o mesmo contrato de ``load_state``."""
    rendered = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    parsed = yaml.safe_load(rendered)
    # Reaplica a validação sem depender de arquivo temporário.
    if not isinstance(parsed, dict):
        raise WorldConditionError("estado em memória inválido")
    if (
        parsed.get("schema_condicoes_mundo") != SCHEMA
        or parsed.get("natureza") != "controle_reservado"
        or parsed.get("cidade") != CITY
    ):
        raise WorldConditionError("estado em memória divergente")
    conditions = _map(parsed.get("condicoes"), "condicoes")
    history = _list(parsed.get("historico_recente"), "historico_recente")
    clean = {
        "schema_condicoes_mundo": SCHEMA,
        "natureza": "controle_reservado",
        "cidade": CITY,
        "condicoes": {cid: _record(raw, str(cid)) for cid, raw in conditions.items()},
        "historico_recente": [_history_item(item) for item in history],
    }
    if len(clean["condicoes"]) > MAX_CONDITIONS or len(clean["historico_recente"]) > MAX_HISTORY:
        raise WorldConditionError("estado em memória excede tetos")
    size = len(yaml.safe_dump(clean, allow_unicode=True, sort_keys=False).encode("utf-8"))
    if size > MAX_STATE_BYTES:
        raise WorldConditionError(f"estado excede orçamento: {size} > {MAX_STATE_BYTES} bytes")
    return clean


def close(
    repo: Path,
    condition_id_value: str,
    *,
    source: str,
    evidence: str,
    reason: str,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    cid = _text(condition_id_value, "id")
    if not ID_RE.fullmatch(cid):
        raise WorldConditionError("id deve usar cnd- + 16 hexadecimais")
    ended, time_sources = _canonical_now(repo, now)
    source_path, _ = _validate_evidence(repo, source, evidence)
    reason = _text(reason, "motivo", maximum=160)
    state = load_state(repo)
    record = state["condicoes"].get(cid)
    if record is None:
        previous = next((item for item in reversed(state["historico_recente"]) if item["id"] == cid), None)
        if previous is not None:
            return {
                "ok": True,
                "resultado": "ja_encerrada",
                "historico": previous,
                "fontes_lidas": list(dict.fromkeys([STATE.as_posix(), *time_sources, source_path])),
            }
        raise WorldConditionError(f"condição inexistente: {cid}")
    start = _instant(record["inicio"], f"{cid}.inicio")
    if ended.minute < start.minute:
        raise WorldConditionError("condição não pode encerrar antes de começar")
    state["condicoes"].pop(cid)
    history = _history_from(record, ended, reason, source_path)
    _append_history(state, history)
    state = load_state_from_value(state)
    atomic(repo / STATE, state)
    return {
        "ok": True,
        "resultado": "encerrada",
        "historico": history,
        "fontes_lidas": list(dict.fromkeys([STATE.as_posix(), *time_sources, source_path])),
    }


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        state = load_state(repo)
        for record in state["condicoes"].values():
            source = repo / record["fonte"]
            if not source.is_file():
                errors.append(f"fonte ausente: {record['fonte']}")
                continue
            try:
                body = source.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                errors.append(f"fonte não UTF-8: {record['fonte']}")
                continue
            if record["evidencia"] not in body:
                errors.append(f"evidencia não encontrada: {record['id']}")
            for local_id in record["escopo"]["locais"]:
                try:
                    resolved = locais.resolve(repo, local_id)
                    if resolved["local_id"] != local_id:
                        errors.append(f"escopo não usa id canônico: {local_id}")
                except locais.LocationError as exc:
                    errors.append(str(exc))
        active = project(repo)
    except (WorldConditionError, mundo.WorldEngineError) as exc:
        errors.append(str(exc))
        active = {"ativas": []}
    return {
        "ok": not errors,
        "erros": errors,
        "condicoes_abertas": len(state["condicoes"]) if "state" in locals() else 0,
        "ativas_agora": len(active.get("ativas") or []),
        "historico_recente": len(state["historico_recente"]) if "state" in locals() else 0,
        "scheduler": False,
        "rng": False,
        "fontes_lidas": [STATE.as_posix()],
    }


def _now_args(date: str | None, hour: str | None) -> mundo.WorldInstant | None:
    if date is None and hour is None:
        return None
    if not date or not hour:
        raise WorldConditionError("--data e --hora devem ser usados juntos")
    try:
        return mundo.parse_instant(date, hour)
    except mundo.WorldEngineError as exc:
        raise WorldConditionError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)

    show_parser = sub.add_parser("mostrar", help="projeta somente condições ativas")
    show_parser.add_argument("--local")
    show_parser.add_argument("--data")
    show_parser.add_argument("--hora")

    add = sub.add_parser("registrar", help="registra condição após fato canônico")
    add.add_argument("--tipo", choices=sorted(VALID_TYPES), required=True)
    add.add_argument("--assunto", required=True)
    add.add_argument("--intensidade", choices=sorted(VALID_INTENSITIES), required=True)
    add.add_argument("--descricao", required=True)
    add.add_argument("--sinal", action="append", default=[])
    add.add_argument("--marcador", action="append", default=[])
    add.add_argument("--local", action="append", default=[])
    add.add_argument("--duracao-horas", type=int)
    add.add_argument("--fonte", required=True)
    add.add_argument("--evidencia", required=True)
    add.add_argument("--data")
    add.add_argument("--hora")

    end = sub.add_parser("encerrar", help="encerra condição por fato canônico")
    end.add_argument("id")
    end.add_argument("--motivo", required=True)
    end.add_argument("--fonte", required=True)
    end.add_argument("--evidencia", required=True)
    end.add_argument("--data")
    end.add_argument("--hora")

    sub.add_parser("check", help="valida estado, fontes e orçamento")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "mostrar":
            result = show(repo, local=args.local, now=_now_args(args.data, args.hora))
        elif args.cmd == "registrar":
            result = register(
                repo,
                kind=args.tipo,
                subject=args.assunto,
                intensity=args.intensidade,
                description=args.descricao,
                signals=args.sinal,
                markers=args.marcador,
                locals_=args.local,
                duration_hours=args.duracao_horas,
                source=args.fonte,
                evidence=args.evidencia,
                now=_now_args(args.data, args.hora),
            )
        elif args.cmd == "encerrar":
            result = close(
                repo,
                args.id,
                source=args.fonte,
                evidence=args.evidencia,
                reason=args.motivo,
                now=_now_args(args.data, args.hora),
            )
        else:
            result = check(repo)
            print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
            return 0 if result["ok"] else 1
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0
    except (WorldConditionError, mundo.WorldEngineError, OSError, yaml.YAMLError) as exc:
        print(f"ERRO CONDICAO MUNDO — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
