#!/usr/bin/env python3
"""NV-15 — permanência espacial reativa com frescor por local/data/período.

A camada só é acionada por permanência explícita na porta ``cronica``. Ela não
agenda tempo, não cria presença, não transforma candidato em fato e não decide
uma ação de Ren. A primeira consulta de uma janela local/data/período congela a
avaliação não-canônica dos produtores espaciais já existentes; retries e novos
``scene_id`` reutilizam o mesmo recibo em vez de rerrolar o mundo.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

import condicoes_mundo
import ecologia_local
import fronteira_vivacidade
import incidentes_mundo
import locais
import microeventos_locais
import mundo
import presenca_incidental

SCHEMA = 1
STATE = Path("narrador/permanencia-espacial/estado.yaml")
STATE_NATURE = "controle_reservado"
MAX_EVALUATIONS = 64
MAX_STATE_BYTES = 256 * 1024
MAX_PUBLIC_BYTES = 12 * 1024
MAX_SOURCES = 24
RESULTS = {"resolvida", "adiada", "invalidada"}
TERMINAL_STATES = {"calma_espacial", "resolvida", "adiada", "invalidada"}


class SpatialPermanenceError(ValueError):
    """A permanência não possui local/tempo válidos ou perdeu sua reserva."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _compact_text(value: Any, label: str, *, minimum: int = 1, maximum: int = 320) -> str:
    if not isinstance(value, str):
        raise SpatialPermanenceError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if not minimum <= len(result) <= maximum:
        raise SpatialPermanenceError(f"{label} deve ter {minimum}..{maximum} caracteres")
    return result


def _atomic(path: Path, value: dict[str, Any]) -> None:
    rendered = yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
    raw = rendered.encode("utf-8")
    if len(raw) > MAX_STATE_BYTES:
        raise SpatialPermanenceError(
            f"estado de permanência excede {MAX_STATE_BYTES} bytes; conclua janelas antigas"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
        temp = Path(handle.name)
    os.replace(temp, path)


def _empty_state() -> dict[str, Any]:
    return {
        "schema_estado_permanencia_espacial": SCHEMA,
        "natureza": STATE_NATURE,
        "avaliacoes": {},
        "ordem_recente": [],
    }


def load_state(repo: Path) -> dict[str, Any]:
    path = repo / STATE
    if not path.is_file():
        return _empty_state()
    if path.stat().st_size > MAX_STATE_BYTES:
        raise SpatialPermanenceError(f"{STATE} excede orçamento")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise SpatialPermanenceError(str(exc)) from exc
    if not isinstance(data, dict):
        raise SpatialPermanenceError("estado de permanência deve ser mapa")
    if (
        data.get("schema_estado_permanencia_espacial") != SCHEMA
        or data.get("natureza") != STATE_NATURE
        or set(data) != {
            "schema_estado_permanencia_espacial",
            "natureza",
            "avaliacoes",
            "ordem_recente",
        }
    ):
        raise SpatialPermanenceError("estado de permanência espacial inválido")
    evaluations = data.get("avaliacoes")
    order = data.get("ordem_recente")
    if not isinstance(evaluations, dict) or not isinstance(order, list):
        raise SpatialPermanenceError("estado de permanência possui coleções inválidas")
    if len(order) != len(set(order)) or any(item not in evaluations for item in order):
        raise SpatialPermanenceError("ordem de permanência possui IDs inválidos/duplicados")
    if len(evaluations) > MAX_EVALUATIONS:
        raise SpatialPermanenceError("estado de permanência excede teto de avaliações")
    for evaluation_id, raw in evaluations.items():
        if not isinstance(raw, dict) or raw.get("id") != evaluation_id:
            raise SpatialPermanenceError(f"avaliação espacial inválida: {evaluation_id}")
        if raw.get("estado") not in {"ativa", *TERMINAL_STATES}:
            raise SpatialPermanenceError(f"estado espacial inválido: {evaluation_id}")
        if not isinstance(raw.get("digest"), str) or len(raw["digest"]) != 64:
            raise SpatialPermanenceError(f"digest espacial inválido: {evaluation_id}")
    return data


def _state_without_digest(record: dict[str, Any]) -> dict[str, Any]:
    value = copy.deepcopy(record)
    value.pop("digest", None)
    return value


def _record_digest(record: dict[str, Any]) -> str:
    return _digest(_state_without_digest(record))


def _prune(state: dict[str, Any]) -> None:
    order = state["ordem_recente"]
    evaluations = state["avaliacoes"]
    while len(order) > MAX_EVALUATIONS:
        victim = next(
            (
                evaluation_id
                for evaluation_id in order
                if evaluations[evaluation_id].get("estado") in TERMINAL_STATES
            ),
            None,
        )
        if victim is None:
            raise SpatialPermanenceError(
                "muitas permanências espaciais ainda ativas; resolva/adie/invalide antes de abrir outra"
            )
        order.remove(victim)
        evaluations.pop(victim, None)


def _current_location(repo: Path) -> tuple[str, list[str]]:
    path = repo / "estado/estado-atual.yaml"
    try:
        state = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise SpatialPermanenceError(f"não foi possível ler local consolidado: {exc}") from exc
    location = state.get("localizacao") if isinstance(state, dict) else None
    if not isinstance(location, dict):
        raise SpatialPermanenceError(
            "--permanencia-local exige local consolidado em estado/estado-atual.yaml"
        )
    raw = location.get("local_id") or location.get("area")
    if not isinstance(raw, str) or not raw.strip():
        raise SpatialPermanenceError(
            "--permanencia-local exige local atual consolidado; não inventar local a partir da cena"
        )
    try:
        resolved = locais.resolve(repo, raw)
    except locais.LocationError as exc:
        raise SpatialPermanenceError(str(exc)) from exc
    return resolved["local_id"], ["estado/estado-atual.yaml", *resolved.get("fontes_lidas", [])]


def resolve_location(repo: Path, supplied: str | None = None) -> tuple[str, list[str]]:
    """Herda somente o local consolidado; ``--local`` opcional precisa coincidir."""
    current_id, sources = _current_location(repo)
    if supplied is None:
        return current_id, list(dict.fromkeys(sources))
    try:
        explicit = locais.resolve(repo, supplied)
    except locais.LocationError as exc:
        raise SpatialPermanenceError(str(exc)) from exc
    if explicit["local_id"] != current_id:
        raise SpatialPermanenceError(
            "permanência não move Ren: --local deve coincidir com o local atual consolidado"
        )
    return current_id, list(dict.fromkeys([*sources, *explicit.get("fontes_lidas", [])]))


def _instant(repo: Path, supplied: mundo.WorldInstant | None) -> tuple[mundo.WorldInstant, list[str]]:
    if supplied is not None:
        return supplied, []
    try:
        current, _ = mundo.load_canonical_time(repo)
    except mundo.WorldEngineError as exc:
        raise SpatialPermanenceError(str(exc)) from exc
    return current, [mundo.TIME_PATH.as_posix()]


def _window(repo: Path, local_id: str, current: mundo.WorldInstant) -> dict[str, str]:
    try:
        agenda = mundo.load_agenda(repo)
        dawn = mundo._dawn_minute(agenda)
    except mundo.WorldEngineError as exc:
        raise SpatialPermanenceError(str(exc)) from exc
    parts = mundo.instant_parts(current)
    period = fronteira_vivacidade.period_at(current, dawn)
    identity = {"local_id": local_id, "data": parts["data"], "periodo": period}
    return {
        **identity,
        "chave": f"{local_id}|{parts['data']}|{period}",
        "id": "perm-" + _digest(identity)[:20],
    }


def _active_for_local(state: dict[str, Any], local_id: str, except_id: str) -> dict[str, Any] | None:
    for evaluation_id in reversed(state["ordem_recente"]):
        if evaluation_id == except_id:
            continue
        record = state["avaliacoes"][evaluation_id]
        if record.get("local_id") == local_id and record.get("estado") == "ativa":
            return record
    return None


def _invalidate_other_locations(
    state: dict[str, Any], local_id: str, current_parts: dict[str, str]
) -> bool:
    changed = False
    for record in state["avaliacoes"].values():
        if record.get("estado") != "ativa" or record.get("local_id") == local_id:
            continue
        record["estado"] = "invalidada"
        record["decisao"] = {
            "resultado": "invalidada",
            "motivo": "local atual consolidado mudou; candidato da permanência anterior perdeu sua âncora espacial",
            "em": copy.deepcopy(current_parts),
        }
        record["digest"] = _record_digest(record)
        changed = True
    return changed


def _compact_conditions(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for raw in items[:4]:
        if not isinstance(raw, dict):
            continue
        result.append(
            {
                key: copy.deepcopy(raw[key])
                for key in ("id", "tipo", "assunto", "intensidade", "sinais", "marcadores")
                if key in raw
            }
        )
    return result


def _compact_presence(public: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for raw in public.get("candidatos") or []:
        if not isinstance(raw, dict):
            continue
        rows.append(
            {
                key: raw[key]
                for key in ("id", "nome", "motivo", "janela_id", "consulta_dirigida")
                if key in raw
            }
        )
    return {
        "resultado": "avaliar_presenca" if rows else "nenhuma_presenca_incidental",
        "candidatos": rows,
    }


def _compact_micro(public: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: copy.deepcopy(public[key])
        for key in ("resultado", "ficha_ocorrencia", "resultado_base", "pressao_aventura")
        if key in public
    }
    card = public.get("carta")
    if isinstance(card, dict):
        result["carta"] = {
            key: copy.deepcopy(card[key])
            for key in ("id", "nome", "categoria", "premissa", "atores_comuns", "guardrails")
            if key in card
        }
    return result


def _compact_incident(public: dict[str, Any]) -> dict[str, Any]:
    result = {
        key: copy.deepcopy(public[key])
        for key in ("resultado", "origem", "ficha_global", "ficha_local")
        if key in public
    }
    incident = public.get("incidente")
    if isinstance(incident, dict):
        result["incidente"] = copy.deepcopy(incident)
    return result


def _candidate_rows(
    presence: dict[str, Any], micro: dict[str, Any], incident: dict[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if incident.get("resultado") == "avaliar_incidente" and isinstance(incident.get("incidente"), dict):
        card = incident["incidente"]
        rows.append(
            {
                "id": "incidente:" + str(card.get("id")),
                "tipo": "incidente_local",
                "prioridade": 2,
                "origem": "incidentes_mundo",
            }
        )
    for item in presence.get("candidatos") or []:
        rows.append(
            {
                "id": "presenca:" + str(item.get("id")),
                "tipo": "presenca_incidental",
                "prioridade": 7,
                "origem": "presenca_incidental",
            }
        )
    if micro.get("resultado") == "avaliar_microevento" and isinstance(micro.get("carta"), dict):
        card = micro["carta"]
        rows.append(
            {
                "id": "microevento:" + str(card.get("id")),
                "tipo": "rotina_local",
                "prioridade": 7,
                "origem": "microeventos_locais",
            }
        )
    rows.sort(key=lambda item: (item["prioridade"], item["id"]))
    if rows:
        rows[0]["decisao"] = "primaria"
        for row in rows[1:]:
            row["decisao"] = "adiada_pelo_orcamento_da_janela"
    return rows


def _public(record: dict[str, Any], *, reused: bool, carried: bool = False) -> dict[str, Any]:
    payload = {
        "schema_permanencia_espacial": SCHEMA,
        "avaliacao_id": record["id"],
        "local_id": record["local_id"],
        "data": record["data"],
        "periodo": record["periodo"],
        "estado": record["estado"],
        "reutilizado": reused,
        "carregada_de_janela_anterior": carried,
        "pressao_primaria": record.get("pressao_primaria"),
        "candidatos": copy.deepcopy(record.get("candidatos") or []),
        "ecologia": copy.deepcopy(record["ecologia"]),
        "presenca_incidental": copy.deepcopy(record["presenca_incidental"]),
        "microevento_local": copy.deepcopy(record["microevento_local"]),
        "incidente_local": copy.deepcopy(record["incidente_local"]),
        "condicoes_ambientais": copy.deepcopy(record["condicoes_ambientais"]),
        "exige_decisao_conclusao": record["estado"] == "ativa",
        "digest": record["digest"],
        "regra": (
            "avaliação congelada por local+data+período; candidato não é fato. "
            "Novo preparo não rerrola e ausência de incidente é resultado explícito."
        ),
        "fontes_lidas": list(record.get("fontes_lidas") or []),
    }
    raw = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False).encode("utf-8")
    if len(raw) > MAX_PUBLIC_BYTES:
        raise SpatialPermanenceError(
            f"projeção de permanência excede {MAX_PUBLIC_BYTES} bytes"
        )
    return payload


def _reservation_scene_id(window: dict[str, str]) -> str:
    # Os produtores antigos usam cena_id só como chave de frescor/histórico.
    # Esta identidade substitui o scene_id efêmero sem alterar seus decks.
    return f"permanencia:{window['local_id']}:{window['data']}:{window['periodo']}"


def prepare(
    repo: Path,
    *,
    scene_id: str,
    place: str | None = None,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    """Reserva/reutiliza uma avaliação espacial para a janela consolidada atual."""
    repo = Path(repo).resolve()
    local_id, local_sources = resolve_location(repo, place)
    current, time_sources = _instant(repo, now)
    current_parts = mundo.instant_parts(current)
    window = _window(repo, local_id, current)
    state = load_state(repo)

    changed = _invalidate_other_locations(state, local_id, current_parts)
    existing = state["avaliacoes"].get(window["id"])
    if isinstance(existing, dict):
        if existing.get("digest") != _record_digest(existing):
            raise SpatialPermanenceError("recibo espacial persistido possui digest divergente")
        if changed:
            _atomic(repo / STATE, state)
        return {
            "publico": _public(existing, reused=True),
            "ticket": {
                "schema": SCHEMA,
                "avaliacao_id": existing["id"],
                "digest": existing["digest"],
                "local_id": existing["local_id"],
                "data": existing["data"],
                "periodo": existing["periodo"],
            },
        }

    carried = _active_for_local(state, local_id, window["id"])
    if carried is not None:
        if carried.get("digest") != _record_digest(carried):
            raise SpatialPermanenceError("pressão espacial carregada possui digest divergente")
        if changed:
            _atomic(repo / STATE, state)
        return {
            "publico": _public(carried, reused=True, carried=True),
            "ticket": {
                "schema": SCHEMA,
                "avaliacao_id": carried["id"],
                "digest": carried["digest"],
                "local_id": carried["local_id"],
                "data": carried["data"],
                "periodo": carried["periodo"],
            },
        }

    try:
        ecology = ecologia_local.lookup_canonical(repo, local_id)
        activity = ecologia_local.activity(ecology["perfil"], window["periodo"])
    except ecologia_local.LocalEcologyError as exc:
        raise SpatialPermanenceError(str(exc)) from exc

    condition_sources: list[str] = []
    conditions: list[dict[str, Any]] = []
    if (repo / condicoes_mundo.STATE).is_file():
        try:
            projection = condicoes_mundo.for_scene(repo, local_id, now=current)
        except condicoes_mundo.WorldConditionError as exc:
            raise SpatialPermanenceError(str(exc)) from exc
        conditions = list(projection.get("ativas") or [])
        condition_sources = list(projection.get("fontes_lidas") or [])

    presence_sources: list[str] = []
    presence_public = {
        "local_id": local_id,
        "periodo": window["periodo"],
        "candidatos": [],
        "fontes_lidas": [],
    }
    if presenca_incidental.configured(repo):
        try:
            presence_public = presenca_incidental.select(
                repo,
                scene_id=_reservation_scene_id(window),
                local_id=local_id,
                ecology=ecology["perfil"],
                now=current,
            )
        except presenca_incidental.IncidentalPresenceError as exc:
            raise SpatialPermanenceError(str(exc)) from exc
        presence_sources = list(presence_public.get("fontes_lidas") or [])

    if not microeventos_locais.configured(repo):
        raise SpatialPermanenceError("permanência exige camada de microeventos locais configurada")
    if not incidentes_mundo.configured(repo):
        raise SpatialPermanenceError("permanência exige camada de incidentes locais configurada")

    key_scene = _reservation_scene_id(window)
    try:
        micro_plan = microeventos_locais.plan(
            repo,
            local_id=local_id,
            scene_id=key_scene,
            profile=ecology["perfil"],
        )
        incident_plan = incidentes_mundo.plan(
            repo,
            scene_id=key_scene,
            local_id=local_id,
            profile=ecology["perfil"],
            conditions=conditions,
        )
    except (microeventos_locais.LocalMicroeventError, incidentes_mundo.IncidentError) as exc:
        raise SpatialPermanenceError(str(exc)) from exc

    micro = _compact_micro(micro_plan["publico"])
    incident = _compact_incident(incident_plan["publico"])
    presence = _compact_presence(presence_public)
    candidates = _candidate_rows(presence, micro, incident)
    primary = candidates[0]["id"] if candidates else None
    sources = list(
        dict.fromkeys(
            [
                STATE.as_posix(),
                mundo.AGENDA_PATH.as_posix(),
                *local_sources,
                *time_sources,
                *ecology.get("fontes_lidas", []),
                *condition_sources,
                *presence_sources,
                *micro_plan["publico"].get("fontes_lidas", []),
                *incident_plan["publico"].get("fontes_lidas", []),
            ]
        )
    )[:MAX_SOURCES]
    record: dict[str, Any] = {
        "id": window["id"],
        "chave": window["chave"],
        "local_id": local_id,
        "data": window["data"],
        "periodo": window["periodo"],
        "estado": "ativa" if primary is not None else "calma_espacial",
        "pressao_primaria": primary,
        "candidatos": candidates,
        "ecologia": {
            "ritmo": activity["ritmo"],
            "tags": list(activity.get("tags") or [])[:6],
            "canais_microevento": list(activity.get("canais_microevento") or [])[:6],
        },
        "presenca_incidental": presence,
        "microevento_local": micro,
        "incidente_local": incident,
        "condicoes_ambientais": _compact_conditions(conditions),
        "decisao": None,
        "fontes_lidas": sources,
    }
    record["digest"] = _record_digest(record)

    # Reserva primeiro os decks produtores. Se houver interrupção entre as duas
    # escritas e o recibo final, repetir a mesma chave encontra o histórico já
    # consumido e reconstrói exatamente os mesmos resultados.
    try:
        microeventos_locais.commit_plan(repo, micro_plan)
        incidentes_mundo.commit_plan(repo, incident_plan)
    except (microeventos_locais.LocalMicroeventError, incidentes_mundo.IncidentError) as exc:
        raise SpatialPermanenceError(str(exc)) from exc

    state["avaliacoes"][record["id"]] = record
    if record["id"] not in state["ordem_recente"]:
        state["ordem_recente"].append(record["id"])
    _prune(state)
    _atomic(repo / STATE, state)
    return {
        "publico": _public(record, reused=False),
        "ticket": {
            "schema": SCHEMA,
            "avaliacao_id": record["id"],
            "digest": record["digest"],
            "local_id": local_id,
            "data": record["data"],
            "periodo": record["periodo"],
        },
    }


def validate_ticket(meta: Any) -> dict[str, str]:
    if not isinstance(meta, dict):
        raise SpatialPermanenceError("ticket de permanência deve ser mapa")
    expected = {"schema", "avaliacao_id", "digest", "local_id", "data", "periodo"}
    if set(meta) != expected or meta.get("schema") != SCHEMA:
        raise SpatialPermanenceError("ticket de permanência possui campos divergentes")
    result = {
        "avaliacao_id": _compact_text(meta.get("avaliacao_id"), "avaliacao_id", maximum=64),
        "digest": _compact_text(meta.get("digest"), "digest", maximum=64),
        "local_id": _compact_text(meta.get("local_id"), "local_id", maximum=96),
        "data": _compact_text(meta.get("data"), "data", maximum=80),
        "periodo": _compact_text(meta.get("periodo"), "periodo", maximum=24),
    }
    if len(result["digest"]) != 64 or any(ch not in "0123456789abcdef" for ch in result["digest"]):
        raise SpatialPermanenceError("digest do ticket de permanência inválido")
    return result


def revalidate(repo: Path, meta: Any) -> dict[str, Any]:
    normalized = validate_ticket(meta)
    state = load_state(repo)
    record = state["avaliacoes"].get(normalized["avaliacao_id"])
    if not isinstance(record, dict):
        raise SpatialPermanenceError("avaliação espacial do ticket não existe mais")
    for key in ("local_id", "data", "periodo"):
        if record.get(key) != normalized[key]:
            raise SpatialPermanenceError("avaliação espacial divergiu do ticket")
    if record.get("digest") != normalized["digest"] or record.get("digest") != _record_digest(record):
        raise SpatialPermanenceError("avaliação espacial mudou; prepare novamente")
    return _public(record, reused=True)


def prepare_conclusion(repo: Path, meta: Any, transaction: dict[str, Any]) -> dict[str, Any] | None:
    public = revalidate(repo, meta)
    block = transaction.get("permanencia_espacial")
    if public["estado"] != "ativa":
        if block not in (None, {}):
            raise SpatialPermanenceError(
                "permanência sem pressão ativa não aceita decisão fabricada na transação"
            )
        return None
    if not isinstance(block, dict):
        raise SpatialPermanenceError(
            "pressão espacial ativa exige permanencia_espacial na conclusão"
        )
    outcome = _compact_text(block.get("resultado"), "permanencia_espacial.resultado", maximum=24)
    if outcome not in RESULTS:
        raise SpatialPermanenceError("resultado deve ser resolvida, adiada ou invalidada")
    if block.get("avaliacao_id") != public["avaliacao_id"]:
        raise SpatialPermanenceError("conclusão referencia outra avaliação espacial")
    expected = {"avaliacao_id", "resultado"}
    decision: dict[str, Any] = {
        "avaliacao_id": public["avaliacao_id"],
        "resultado": outcome,
    }
    if outcome == "resolvida":
        expected.add("evidencia_literal")
        evidence = _compact_text(
            block.get("evidencia_literal"),
            "permanencia_espacial.evidencia_literal",
            minimum=8,
            maximum=320,
        )
        haystack = "\n".join(str(transaction.get(key) or "") for key in ("narracao", "resumo"))
        if evidence not in haystack:
            raise SpatialPermanenceError(
                "evidencia_literal da pressão espacial deve aparecer na narração ou resumo"
            )
        decision["evidencia_literal"] = evidence
    else:
        expected.add("motivo")
        decision["motivo"] = _compact_text(
            block.get("motivo"), "permanencia_espacial.motivo", minimum=8, maximum=320
        )
    if set(block) != expected:
        raise SpatialPermanenceError(
            "bloco permanencia_espacial possui campos divergentes"
        )
    return decision


def install_conclusion(
    repo: Path,
    meta: Any,
    decision: dict[str, Any] | None,
    *,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any] | None:
    public = revalidate(repo, meta)
    if decision is None:
        return None
    state = load_state(repo)
    record = state["avaliacoes"][public["avaliacao_id"]]
    if record["estado"] in RESULTS:
        existing = record.get("decisao") or {}
        comparable = {key: existing.get(key) for key in decision}
        if comparable != decision:
            raise SpatialPermanenceError("retry de permanência diverge da decisão já instalada")
        return {"resultado": "ja_aplicada", "avaliacao_id": record["id"], "estado": record["estado"]}
    if record["estado"] != "ativa":
        raise SpatialPermanenceError("avaliação espacial já não possui pressão ativa")
    current, _ = _instant(repo, now)
    record["estado"] = decision["resultado"]
    record["decisao"] = {**copy.deepcopy(decision), "em": mundo.instant_parts(current)}
    record["digest"] = _record_digest(record)
    _atomic(repo / STATE, state)
    return {
        "resultado": "aplicada",
        "avaliacao_id": record["id"],
        "estado": record["estado"],
    }
