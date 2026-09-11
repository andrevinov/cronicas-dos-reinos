#!/usr/bin/env python3
"""NV-20 — fama/reconhecibilidade dirigida por persona e marco público.

O ledger é compacto e vive em ``estado/estado-atual.yaml`` para participar do
mesmo journal transacional que confirma o marco público. Ele não é projetado no
runtime comum nem consultado todo turno: leituras são sempre dirigidas por
persona + público + localidade.

Uma apresentação pública confirmada é representada por dois deltas no mesmo
writer: um ``consequencia/registrar`` com o marco público e um ``estado/set`` do
ledger acrescentando somente os eventos de fama desse marco. O contrato
transacional exige o par; passagem do tempo ou prosa não cria fama.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import re
from pathlib import Path
from typing import Any, Iterable

import yaml

import identidades
import reputacao_publica

STATE_FILE = Path("estado/estado-atual.yaml")
STATE_ROOT = "reconhecibilidade_personas"
SCHEMA = 1
PERFORMANCE_TYPE = "apresentacao_publica_confirmada"
MAX_EVENTS = 48
MAX_STATE_BYTES = 28 * 1024
MAX_AUDIENCES_PER_MILESTONE = 3
MAX_QUERY_EVENTS = 8
MAX_FACT_CHARS = 520
MAX_SOURCE_CHARS = 160
ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,95}$")
LOCAL_RE = re.compile(r"^[a-z][a-z0-9_.:-]{0,95}$")
ATTRIBUTIONS = {"rumor": 1, "provavel": 2, "direta": 3}
CONFIDENCES = {"baixa": 1, "media": 2, "alta": 3, "testemunhada": 4}
LEVELS = (
    (0, "desconhecida"),
    (2, "ouvida"),
    (7, "reconhecivel"),
    (13, "conhecida"),
    (10**9, "notoria_local"),
)


class RecognizabilityError(ValueError):
    """Ledger, marco público ou consulta de reconhecibilidade inválidos."""


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RecognizabilityError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise RecognizabilityError(f"YAML inválido em {path}: {exc}") from exc


def _text(value: Any, label: str, maximum: int = 240, minimum: int = 1) -> str:
    if not isinstance(value, str):
        raise RecognizabilityError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if not minimum <= len(result) <= maximum:
        raise RecognizabilityError(f"{label} deve ter {minimum}..{maximum} caracteres")
    return result


def _source(value: Any) -> str:
    result = _text(value, "fonte canônica", MAX_SOURCE_CHARS)
    if "\n" in result or "\r" in result:
        raise RecognizabilityError("fonte canônica precisa ser referência compacta")
    return result


def _id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise RecognizabilityError(f"{label} precisa ser ID canônico compacto")
    return value


def _locality(value: Any) -> str:
    if not isinstance(value, str) or not LOCAL_RE.fullmatch(value):
        raise RecognizabilityError("localidade precisa ser ID canônico compacto")
    return value


def load_audiences(repo: Path) -> dict[str, Any]:
    return reputacao_publica.load_audiences(repo)


def load_identities(repo: Path) -> dict[str, Any]:
    return identidades.load_registry(repo)


def empty_state() -> dict[str, Any]:
    return {"schema_reconhecibilidade_personas": SCHEMA, "eventos": {}}


def event_id(persona: str, audience: str, locality: str, milestone: str) -> str:
    raw = "\x1f".join([persona, audience, locality, milestone])
    return "fam-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _resolve_persona(registry: dict[str, Any], value: str) -> str:
    try:
        return identidades.resolve_identity(registry, value)
    except identidades.IdentitySuspicionError as exc:
        raise RecognizabilityError(str(exc)) from exc


def _resolve_audience(registry: dict[str, Any], value: str) -> str:
    try:
        return reputacao_publica.resolve_public(registry, value)
    except reputacao_publica.PublicReputationError as exc:
        raise RecognizabilityError(str(exc)) from exc


def validate_event(
    value: Any,
    audiences: dict[str, Any],
    identities_registry: dict[str, Any],
) -> dict[str, Any]:
    fields = {
        "id", "persona", "audiencia", "localidade", "marco_publico", "tipo_marco",
        "atribuicao", "confianca", "fato", "fonte",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise RecognizabilityError("evento de fama possui campos divergentes")
    persona = _id(value["persona"], "persona")
    audience = _id(value["audiencia"], "audiência")
    locality = _locality(value["localidade"])
    milestone = _id(value["marco_publico"], "marco público")
    if persona not in identities_registry.get("identidades", {}):
        raise RecognizabilityError(f"persona desconhecida: {persona}")
    if audience not in audiences.get("publicos", {}):
        raise RecognizabilityError(f"audiência desconhecida: {audience}")
    if value["tipo_marco"] != PERFORMANCE_TYPE:
        raise RecognizabilityError("NV-20 v1 aceita fama automática somente de apresentação pública confirmada")
    if value["atribuicao"] not in ATTRIBUTIONS:
        raise RecognizabilityError("atribuição de fama inválida")
    if value["confianca"] not in CONFIDENCES:
        raise RecognizabilityError("confiança de fama inválida")
    _text(value["fato"], "fato público", MAX_FACT_CHARS, 20)
    _source(value["fonte"])
    expected = event_id(persona, audience, locality, milestone)
    if value["id"] != expected:
        raise RecognizabilityError("ID do evento de fama diverge de persona+audiência+localidade+marco")
    return copy.deepcopy(value)


def validate_state(
    value: Any,
    audiences: dict[str, Any],
    identities_registry: dict[str, Any],
) -> dict[str, Any]:
    if value is None:
        return empty_state()
    if not isinstance(value, dict) or set(value) != {"schema_reconhecibilidade_personas", "eventos"}:
        raise RecognizabilityError("reconhecibilidade_personas exige schema e eventos")
    if value.get("schema_reconhecibilidade_personas") != SCHEMA:
        raise RecognizabilityError("schema_reconhecibilidade_personas deve ser 1")
    events = value.get("eventos")
    if not isinstance(events, dict):
        raise RecognizabilityError("eventos de reconhecibilidade precisam ser mapa")
    if len(events) > MAX_EVENTS:
        raise RecognizabilityError(f"ledger excede {MAX_EVENTS} eventos; consolidar política antes de ampliar")
    clean: dict[str, Any] = {}
    seen_keys: set[tuple[str, str, str, str]] = set()
    for key, raw in events.items():
        event = validate_event(raw, audiences, identities_registry)
        if key != event["id"]:
            raise RecognizabilityError("chave do ledger diverge do ID do evento")
        dedup = (event["persona"], event["audiencia"], event["localidade"], event["marco_publico"])
        if dedup in seen_keys:
            raise RecognizabilityError("marco público duplicado para a mesma persona/audiência/localidade")
        seen_keys.add(dedup)
        clean[key] = event
    result = {"schema_reconhecibilidade_personas": SCHEMA, "eventos": clean}
    size = len(yaml.safe_dump(result, allow_unicode=True, sort_keys=False).encode("utf-8"))
    if size > MAX_STATE_BYTES:
        raise RecognizabilityError(f"ledger excede orçamento: {size} > {MAX_STATE_BYTES} bytes")
    return result


def touches(delta: Any) -> bool:
    return (
        isinstance(delta, dict)
        and delta.get("alvo") == "estado"
        and isinstance(delta.get("caminho"), str)
        and (delta["caminho"] == STATE_ROOT or delta["caminho"].startswith(STATE_ROOT + "."))
    )


def is_fame_delta(delta: Any) -> bool:
    return touches(delta) and delta.get("caminho") == STATE_ROOT and delta.get("op") == "set"


def _metadata(delta: dict[str, Any]) -> tuple[str, list[str], str, str, str, str, str, str]:
    persona = _id(delta.get("persona"), "persona")
    locality = _locality(delta.get("localidade"))
    milestone = _id(delta.get("marco_publico"), "marco público")
    audiences_raw = delta.get("audiencias")
    if (
        not isinstance(audiences_raw, list)
        or not 1 <= len(audiences_raw) <= MAX_AUDIENCES_PER_MILESTONE
        or any(not isinstance(item, str) for item in audiences_raw)
    ):
        raise RecognizabilityError(
            f"marco público exige 1..{MAX_AUDIENCES_PER_MILESTONE} audiências explícitas"
        )
    audience_ids = [_id(item, "audiência") for item in audiences_raw]
    if audience_ids != sorted(set(audience_ids)):
        raise RecognizabilityError("audiências do marco devem ser únicas e ordenadas")
    attribution = delta.get("atribuicao")
    confidence = delta.get("confianca")
    if attribution not in ATTRIBUTIONS:
        raise RecognizabilityError("atribuição de fama inválida")
    if confidence not in CONFIDENCES:
        raise RecognizabilityError("confiança de fama inválida")
    fact = _text(delta.get("fato_canonico"), "fato público", MAX_FACT_CHARS, 20)
    source = _source(delta.get("fonte"))
    if delta.get("tipo_marco") != PERFORMANCE_TYPE or delta.get("motivo_reconhecibilidade") != "marco_publico":
        raise RecognizabilityError("delta de fama precisa declarar apresentação pública e motivo marco_publico")
    return persona, audience_ids, locality, milestone, attribution, confidence, fact, source


def validate_delta(
    delta: Any,
    audiences: dict[str, Any],
    identities_registry: dict[str, Any],
) -> dict[str, Any]:
    required = {
        "alvo", "op", "caminho", "valor", "visibilidade", "motivo_reconhecibilidade",
        "tipo_marco", "persona", "localidade", "marco_publico", "audiencias",
        "atribuicao", "confianca", "fato_canonico", "fonte",
    }
    if not isinstance(delta, dict) or set(delta) != required:
        raise RecognizabilityError("delta de reconhecibilidade possui campos divergentes")
    if not is_fame_delta(delta):
        raise RecognizabilityError("reconhecibilidade aceita somente set do ledger compacto inteiro")
    if delta.get("visibilidade") != "operacional":
        raise RecognizabilityError("ledger de fama usa visibilidade operacional")
    persona, audience_ids, locality, milestone, attribution, confidence, fact, source = _metadata(delta)
    if persona not in identities_registry.get("identidades", {}):
        raise RecognizabilityError(f"persona desconhecida: {persona}")
    if any(item not in audiences.get("publicos", {}) for item in audience_ids):
        raise RecognizabilityError("marco usa audiência social desconhecida")
    state = validate_state(delta.get("valor"), audiences, identities_registry)
    for audience in audience_ids:
        eid = event_id(persona, audience, locality, milestone)
        event = state["eventos"].get(eid)
        if event is None:
            raise RecognizabilityError(f"delta não contém evento esperado para audiência {audience}")
        expected = {
            "id": eid,
            "persona": persona,
            "audiencia": audience,
            "localidade": locality,
            "marco_publico": milestone,
            "tipo_marco": PERFORMANCE_TYPE,
            "atribuicao": attribution,
            "confianca": confidence,
            "fato": fact,
            "fonte": source,
        }
        if event != expected:
            raise RecognizabilityError("evento de fama diverge dos metadados do marco público")
    return delta


def validate_transition(
    before: Any,
    delta: dict[str, Any],
    audiences: dict[str, Any],
    identities_registry: dict[str, Any],
) -> dict[str, Any]:
    old = validate_state(before, audiences, identities_registry)
    validate_delta(delta, audiences, identities_registry)
    new = validate_state(delta["valor"], audiences, identities_registry)
    persona, audience_ids, locality, milestone, *_ = _metadata(delta)
    expected_added = {event_id(persona, audience, locality, milestone) for audience in audience_ids}
    old_events, new_events = old["eventos"], new["eventos"]
    if not set(old_events) <= set(new_events):
        raise RecognizabilityError("evento de fama anterior não pode ser removido")
    if any(new_events[key] != old_events[key] for key in old_events):
        raise RecognizabilityError("evento de fama anterior é imutável")
    added = set(new_events) - set(old_events)
    if added != expected_added:
        if expected_added & set(old_events):
            raise RecognizabilityError("marco já registrado para esta persona/audiência/localidade")
        raise RecognizabilityError("um writer de fama só pode acrescentar os eventos do marco declarado")
    return new


def _validate_marker(
    value: Any,
    audiences: dict[str, Any],
    identities_registry: dict[str, Any],
) -> dict[str, Any]:
    fields = {
        "tipo", "marco_publico", "persona", "audiencias", "localidade",
        "atribuicao", "confianca", "fato_canonico", "fonte",
    }
    if not isinstance(value, dict) or set(value) != fields or value.get("tipo") != PERFORMANCE_TYPE:
        raise RecognizabilityError("marco de apresentação pública possui schema inválido")
    synthetic = {
        "persona": value["persona"], "audiencias": value["audiencias"],
        "localidade": value["localidade"], "marco_publico": value["marco_publico"],
        "atribuicao": value["atribuicao"], "confianca": value["confianca"],
        "fato_canonico": value["fato_canonico"], "fonte": value["fonte"],
        "tipo_marco": PERFORMANCE_TYPE, "motivo_reconhecibilidade": "marco_publico",
    }
    persona, audience_ids, *_ = _metadata(synthetic)
    if persona not in identities_registry.get("identidades", {}):
        raise RecognizabilityError(f"persona desconhecida: {persona}")
    if any(item not in audiences.get("publicos", {}) for item in audience_ids):
        raise RecognizabilityError("marco usa audiência social desconhecida")
    return copy.deepcopy(value)


def _signature(value: dict[str, Any]) -> tuple[Any, ...]:
    return (
        value["marco_publico"], value["persona"], tuple(value["audiencias"]), value["localidade"],
        value["atribuicao"], value["confianca"], value["fato_canonico"], value["fonte"],
    )


def validate_transaction_contract(
    deltas: list[dict[str, Any]],
    audiences: dict[str, Any],
    identities_registry: dict[str, Any],
) -> None:
    markers: list[dict[str, Any]] = []
    fame: list[dict[str, Any]] = []
    for delta in deltas:
        value = delta.get("valor") if isinstance(delta, dict) else None
        if (
            isinstance(delta, dict)
            and delta.get("alvo") == "consequencia"
            and delta.get("op") == "registrar"
            and isinstance(value, dict)
            and value.get("tipo") == PERFORMANCE_TYPE
        ):
            markers.append(_validate_marker(value, audiences, identities_registry))
        if touches(delta):
            fame.append(validate_delta(delta, audiences, identities_registry))
    marker_counts: dict[tuple[Any, ...], int] = {}
    fame_counts: dict[tuple[Any, ...], int] = {}
    for marker in markers:
        marker_counts[_signature(marker)] = marker_counts.get(_signature(marker), 0) + 1
    for delta in fame:
        value = {
            "marco_publico": delta["marco_publico"], "persona": delta["persona"],
            "audiencias": delta["audiencias"], "localidade": delta["localidade"],
            "atribuicao": delta["atribuicao"], "confianca": delta["confianca"],
            "fato_canonico": delta["fato_canonico"], "fonte": delta["fonte"],
        }
        fame_counts[_signature(value)] = fame_counts.get(_signature(value), 0) + 1
    if marker_counts != fame_counts:
        raise RecognizabilityError(
            "apresentação pública confirmada e evento de fama precisam aparecer exatamente pareados no mesmo writer"
        )
    if any(count != 1 for count in marker_counts.values()):
        raise RecognizabilityError("o mesmo marco público não pode ser duplicado na mesma transação")


def validate_batch(repo: Path, records: Iterable[dict[str, Any]]) -> int:
    fame = [
        delta
        for record in records
        for delta in (record.get("deltas") or [])
        if touches(delta)
    ]
    if not fame:
        return 0
    audiences = load_audiences(repo)
    identities_registry = load_identities(repo)
    state_doc = _load(Path(repo) / STATE_FILE)
    if not isinstance(state_doc, dict):
        raise RecognizabilityError("estado atual inválido")
    working = validate_state(state_doc.get(STATE_ROOT), audiences, identities_registry)
    for delta in fame:
        if not is_fame_delta(delta):
            raise RecognizabilityError("mutação direta parcial do ledger de fama é proibida")
        working = validate_transition(working, delta, audiences, identities_registry)
    return len(fame)


def _effective_state(
    repo: Path,
    audiences: dict[str, Any],
    identities_registry: dict[str, Any],
    records: list[dict[str, Any]] | None,
) -> tuple[dict[str, Any], int]:
    state_doc = _load(Path(repo) / STATE_FILE)
    if not isinstance(state_doc, dict):
        raise RecognizabilityError("estado atual inválido")
    working = validate_state(state_doc.get(STATE_ROOT), audiences, identities_registry)
    session = ((state_doc.get("campanha") or {}).get("sessao_atual"))
    if records is None:
        try:
            import transacoes
            records = transacoes.load_pending(Path(repo))
            if isinstance(session, int):
                records = transacoes.pending_for_session(records, session)
        except (OSError, ValueError) as exc:
            raise RecognizabilityError(str(exc)) from exc
    applied = 0
    for record in records or []:
        for delta in record.get("deltas") or []:
            if touches(delta):
                working = validate_transition(working, delta, audiences, identities_registry)
                applied += 1
    return working, applied


def _level(index: int) -> str:
    if index <= 0:
        return "desconhecida"
    for ceiling, label in LEVELS[1:]:
        if index <= ceiling:
            return label
    return "notoria_local"


def query(
    repo: Path,
    *,
    persona: str,
    audience: str,
    locality: str,
    records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Consulta dirigida; não existe leitura global de placar no hot path."""
    repo = Path(repo).resolve()
    audiences = load_audiences(repo)
    identities_registry = load_identities(repo)
    persona_id = _resolve_persona(identities_registry, persona)
    audience_id = _resolve_audience(audiences, audience)
    locality_id = _locality(locality)
    state, applied = _effective_state(repo, audiences, identities_registry, records)
    matches = [
        event for event in state["eventos"].values()
        if event["persona"] == persona_id
        and event["audiencia"] == audience_id
        and event["localidade"] == locality_id
    ]
    matches.sort(key=lambda item: (item["marco_publico"], item["id"]))
    index = sum(CONFIDENCES[item["confianca"]] + ATTRIBUTIONS[item["atribuicao"]] for item in matches)
    visible = matches[-MAX_QUERY_EVENTS:]
    return {
        "schema_reconhecibilidade_personas": SCHEMA,
        "persona": persona_id,
        "audiencia": audience_id,
        "localidade": locality_id,
        "nivel": _level(index),
        "indice_dirigido": index,
        "marcos_distintos": len(matches),
        "eventos": [
            {
                "id": item["id"], "marco_publico": item["marco_publico"],
                "atribuicao": item["atribuicao"], "confianca": item["confianca"],
                "fonte": item["fonte"],
            }
            for item in visible
        ],
        "eventos_omitidos": max(0, len(matches) - len(visible)),
        "deltas_pendentes_aplicados": applied,
        "fontes_lidas": [
            STATE_FILE.as_posix(),
            reputacao_publica.AUDIENCE_REGISTRY.as_posix(),
            identidades.REGISTRY.as_posix(),
        ],
        "regra": "reconhecibilidade é da persona; não confirma identidade civil nem funde Ren, Shinta e Kage",
    }


def meets_requirement(
    projection: dict[str, Any],
    *,
    milestone: str,
    min_confidence: str,
    min_attribution: str,
) -> bool:
    _id(milestone, "marco público")
    if min_confidence not in CONFIDENCES or min_attribution not in ATTRIBUTIONS:
        raise RecognizabilityError("limiar de reconhecimento inválido")
    return any(
        item.get("marco_publico") == milestone
        and CONFIDENCES.get(str(item.get("confianca")), 0) >= CONFIDENCES[min_confidence]
        and ATTRIBUTIONS.get(str(item.get("atribuicao")), 0) >= ATTRIBUTIONS[min_attribution]
        for item in projection.get("eventos") or []
    )


def event_reference(event: dict[str, Any]) -> dict[str, Any]:
    eid = event.get("id") if isinstance(event, dict) else None
    if not isinstance(eid, str) or not re.fullmatch(r"fam-[0-9a-f]{16}", eid):
        raise RecognizabilityError("evento de fama inválido para referência causal")
    return {
        "arquivo": STATE_FILE.as_posix(),
        "caminho": f"{STATE_ROOT}.eventos.{eid}",
        "valor": copy.deepcopy(event),
    }


def propose_public_performance(
    repo: Path,
    *,
    persona: str,
    audiences: list[str],
    locality: str,
    milestone: str,
    fact: str,
    source: str,
    attribution: str = "direta",
    confidence: str = "alta",
    records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    repo = Path(repo).resolve()
    audience_registry = load_audiences(repo)
    identities_registry = load_identities(repo)
    persona_id = _resolve_persona(identities_registry, persona)
    locality_id = _locality(locality)
    milestone_id = _id(milestone, "marco público")
    fact_text = _text(fact, "fato público", MAX_FACT_CHARS, 20)
    source_text = _source(source)
    if attribution not in ATTRIBUTIONS or confidence not in CONFIDENCES:
        raise RecognizabilityError("atribuição/confiança inválidas")
    if not isinstance(audiences, list) or not 1 <= len(audiences) <= MAX_AUDIENCES_PER_MILESTONE:
        raise RecognizabilityError(
            f"apresentação exige 1..{MAX_AUDIENCES_PER_MILESTONE} audiências observadoras"
        )
    audience_ids = sorted(_resolve_audience(audience_registry, item) for item in audiences)
    if len(audience_ids) != len(set(audience_ids)):
        raise RecognizabilityError("a mesma audiência não pode ser repetida")
    state, applied = _effective_state(repo, audience_registry, identities_registry, records)
    missing = [
        audience for audience in audience_ids
        if event_id(persona_id, audience, locality_id, milestone_id) not in state["eventos"]
    ]
    if not missing:
        return {
            "schema_reconhecibilidade_personas": SCHEMA,
            "resultado": "ja_registrado",
            "persona": persona_id,
            "marco_publico": milestone_id,
            "audiencias": audience_ids,
            "deltas": [],
            "deltas_pendentes_preexistentes": applied,
        }
    new_state = copy.deepcopy(state)
    added: list[dict[str, Any]] = []
    for audience in missing:
        eid = event_id(persona_id, audience, locality_id, milestone_id)
        event = {
            "id": eid,
            "persona": persona_id,
            "audiencia": audience,
            "localidade": locality_id,
            "marco_publico": milestone_id,
            "tipo_marco": PERFORMANCE_TYPE,
            "atribuicao": attribution,
            "confianca": confidence,
            "fato": fact_text,
            "fonte": source_text,
        }
        validate_event(event, audience_registry, identities_registry)
        new_state["eventos"][eid] = event
        added.append(event)
    new_state = validate_state(new_state, audience_registry, identities_registry)
    common = {
        "marco_publico": milestone_id,
        "persona": persona_id,
        "audiencias": missing,
        "localidade": locality_id,
        "atribuicao": attribution,
        "confianca": confidence,
        "fato_canonico": fact_text,
        "fonte": source_text,
    }
    marker = {"tipo": PERFORMANCE_TYPE, **common}
    marker_delta = {"alvo": "consequencia", "op": "registrar", "valor": marker}
    fame_delta = {
        "alvo": "estado", "op": "set", "caminho": STATE_ROOT, "valor": new_state,
        "visibilidade": "operacional", "motivo_reconhecibilidade": "marco_publico",
        "tipo_marco": PERFORMANCE_TYPE, **common,
    }
    validate_delta(fame_delta, audience_registry, identities_registry)
    validate_transaction_contract([marker_delta, fame_delta], audience_registry, identities_registry)
    return {
        "schema_reconhecibilidade_personas": SCHEMA,
        "resultado": "registrar_no_mesmo_writer",
        "persona": persona_id,
        "marco_publico": milestone_id,
        "audiencias": missing,
        "eventos": added,
        "deltas": [marker_delta, fame_delta],
        "deltas_pendentes_preexistentes": applied,
        "regra": "registre ambos os deltas na mesma transação que confirma a apresentação",
    }


def check(repo: Path) -> list[str]:
    try:
        audiences = load_audiences(repo)
        identities_registry = load_identities(repo)
        state = _load(Path(repo) / STATE_FILE)
        if not isinstance(state, dict):
            raise RecognizabilityError("estado atual inválido")
        validate_state(state.get(STATE_ROOT), audiences, identities_registry)
        return []
    except (RecognizabilityError, reputacao_publica.PublicReputationError, identidades.IdentitySuspicionError) as exc:
        return [str(exc)]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    show = sub.add_parser("mostrar")
    show.add_argument("--persona", required=True)
    show.add_argument("--publico", required=True)
    show.add_argument("--localidade", required=True)
    propose = sub.add_parser("propor-apresentacao")
    propose.add_argument("--persona", required=True)
    propose.add_argument("--publico", action="append", required=True)
    propose.add_argument("--localidade", required=True)
    propose.add_argument("--marco", required=True)
    propose.add_argument("--fato", required=True)
    propose.add_argument("--fonte", required=True)
    propose.add_argument("--atribuicao", choices=sorted(ATTRIBUTIONS), default="direta")
    propose.add_argument("--confianca", choices=sorted(CONFIDENCES), default="alta")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo = args.repo.resolve()
    try:
        if args.cmd == "check":
            errors = check(repo)
            if errors:
                print("FALHA RECONHECIBILIDADE")
                for error in errors:
                    print(f"- {error}")
                return 1
            print("OK — ledger de reconhecibilidade de personas consistente.")
            return 0
        if args.cmd == "mostrar":
            print(yaml.safe_dump(query(repo, persona=args.persona, audience=args.publico,
                                      locality=args.localidade), allow_unicode=True, sort_keys=False))
            return 0
        if args.cmd == "propor-apresentacao":
            result = propose_public_performance(
                repo, persona=args.persona, audiences=args.publico, locality=args.localidade,
                milestone=args.marco, fact=args.fato, source=args.fonte,
                attribution=args.atribuicao, confidence=args.confianca,
            )
            print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False))
            return 0
        raise RecognizabilityError("comando desconhecido")
    except (RecognizabilityError, reputacao_publica.PublicReputationError, identidades.IdentitySuspicionError) as exc:
        print(f"FALHA RECONHECIBILIDADE — {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
