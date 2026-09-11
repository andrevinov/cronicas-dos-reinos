#!/usr/bin/env python3
"""NV-22 — política cívica e avisos públicos.

O módulo mantém um ledger compacto dentro de ``estado/estado-atual.yaml`` e
reutiliza o writer transacional existente. Ele não possui scheduler próprio,
não escolhe leis aleatoriamente e não sonda instituições no hot path. A agenda
é consultada apenas de forma dirigida; a permanência espacial enxerga somente
publicações já produzidas.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

import entregas_causais as _delivery
import mundo

SCHEMA = 1
STATE_FILE = Path("estado/estado-atual.yaml")
STATE_ROOT = "politica_civica"
REGISTRY_FILE = Path("cenario/regioes/ravens-bluff/instituicoes-civicas.yaml")
CATALOG_FILE = Path("cenario/regioes/ravens-bluff/catalogo-medidas-civicas.yaml")

MAX_MEASURES = 32
MAX_PLANS = 48
MAX_PUBLICATIONS = 64
MAX_DELIVERIES = 96
MAX_HISTORY = 16
MAX_STATE_BYTES = 64 * 1024
MAX_PERMANENCE_NOTICES = 6

MEASURE_TYPES = {"lei", "decreto", "edital", "aviso"}
PHASES = {
    "proposta",
    "em_avaliacao",
    "aprovada",
    "vigente",
    "publicada",
    "expirada",
    "revogada",
    "substituida",
}
TERMINAL_PHASES = {"expirada", "revogada", "substituida"}
TRANSITIONS = {
    "proposta": {"em_avaliacao", "aprovada"},
    "em_avaliacao": {"aprovada"},
    "aprovada": {"vigente"},
    "vigente": {"publicada"},
    "publicada": set(TERMINAL_PHASES),
    "expirada": set(),
    "revogada": set(),
    "substituida": set(),
}
ACTIONS = {
    "avaliar": "em_avaliacao",
    "aprovar": "aprovada",
    "iniciar_vigencia": "vigente",
    "publicar": "publicada",
    "expirar": "expirada",
    "revogar": "revogada",
    "substituir": "substituida",
}
PLAN_STATES = {"pendente", "concluido", "cancelado"}
CHANNELS = {
    "arauto",
    "quadro_avisos",
    "guarda",
    "templo",
    "mensageiro",
    "edital_publico",
}
PERSISTENT_CHANNELS = {"quadro_avisos", "edital_publico"}
ACTIVE_CHANNELS = CHANNELS - PERSISTENT_CHANNELS
PERSISTENT_PERIOD = "persistente"
_ID_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,95}$")


class CivicPolicyError(ValueError):
    """Contrato da NV-22 inválido."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, label: str, maximum: int = 480) -> str:
    if not isinstance(value, str):
        raise CivicPolicyError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if not result or len(result) > maximum:
        raise CivicPolicyError(f"{label} deve ter 1..{maximum} caracteres")
    return result


def _identifier(value: Any, label: str) -> str:
    result = _text(value, label, 96).lower().replace(" ", "_")
    if not _ID_RE.fullmatch(result):
        raise CivicPolicyError(f"{label} possui identificador inválido: {result!r}")
    return result


def _moment(value: Any, label: str = "instante") -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"data", "hora"}:
        raise CivicPolicyError(f"{label} exige data e hora")
    data = _text(value.get("data"), f"{label}.data", 80)
    hora = _text(value.get("hora"), f"{label}.hora", 5)
    try:
        mundo.parse_instant(data, hora)
    except mundo.WorldEngineError as exc:
        raise CivicPolicyError(str(exc)) from exc
    return {"data": data, "hora": hora}


def _minute(value: dict[str, str]) -> int:
    return mundo.parse_instant(value["data"], value["hora"]).minute


def _read_yaml(path: Path, label: str) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise CivicPolicyError(f"arquivo inexistente: {label}") from exc
    except (OSError, yaml.YAMLError) as exc:
        raise CivicPolicyError(f"não foi possível ler {label}: {exc}") from exc
    if not isinstance(data, dict):
        raise CivicPolicyError(f"{label} deve ser mapa")
    return data


def load_registry(repo: Path) -> dict[str, Any]:
    data = _read_yaml(Path(repo) / REGISTRY_FILE, REGISTRY_FILE.as_posix())
    if data.get("schema_instituicoes_civicas") != SCHEMA:
        raise CivicPolicyError("registro de instituições cívicas deve usar schema 1")
    if data.get("jurisdicao") != "ravens_bluff":
        raise CivicPolicyError("NV-22 está configurada para a jurisdição ravens_bluff")
    channels = data.get("canais_publicos")
    institutions = data.get("instituicoes")
    if not isinstance(channels, dict) or set(channels) != CHANNELS:
        raise CivicPolicyError("registro cívico deve declarar exatamente os canais públicos NV-22")
    for channel_id, raw in channels.items():
        if not isinstance(raw, dict) or raw.get("modo") not in {"ativo", "persistente"}:
            raise CivicPolicyError(f"canal cívico inválido: {channel_id}")
        expected = "persistente" if channel_id in PERSISTENT_CHANNELS else "ativo"
        if raw.get("modo") != expected:
            raise CivicPolicyError(f"modo incompatível para canal {channel_id}")
        _text(raw.get("nome"), f"canais_publicos.{channel_id}.nome", 120)
    if not isinstance(institutions, dict) or not institutions:
        raise CivicPolicyError("registro cívico precisa de instituições")
    for institution_id, raw in institutions.items():
        _identifier(institution_id, "instituicao")
        if not isinstance(raw, dict):
            raise CivicPolicyError(f"instituição inválida: {institution_id}")
        _text(raw.get("nome"), f"instituicoes.{institution_id}.nome", 160)
        if not isinstance(raw.get("autorizada"), bool):
            raise CivicPolicyError(f"instituicoes.{institution_id}.autorizada deve ser booleano")
        types = raw.get("tipos") or []
        institution_channels = raw.get("canais") or []
        if not isinstance(types, list) or len(types) != len(set(types)) or set(types) - MEASURE_TYPES:
            raise CivicPolicyError(f"tipos inválidos para instituição {institution_id}")
        if (
            not isinstance(institution_channels, list)
            or len(institution_channels) != len(set(institution_channels))
            or set(institution_channels) - CHANNELS
        ):
            raise CivicPolicyError(f"canais inválidos para instituição {institution_id}")
        if raw["autorizada"] and (not types or not institution_channels):
            raise CivicPolicyError(f"instituição autorizada sem tipos/canais: {institution_id}")
    return data


def load_catalog(repo: Path, registry: dict[str, Any] | None = None) -> dict[str, Any]:
    registry = registry or load_registry(repo)
    data = _read_yaml(Path(repo) / CATALOG_FILE, CATALOG_FILE.as_posix())
    if data.get("schema_catalogo_medidas_civicas") != SCHEMA:
        raise CivicPolicyError("catálogo cívico deve usar schema 1")
    entries = data.get("medidas_menores")
    if not isinstance(entries, dict) or not entries or len(entries) > 12:
        raise CivicPolicyError("catálogo de medidas menores deve ser mapa limitado a 12 entradas")
    known = registry["instituicoes"]
    for slug, raw in entries.items():
        _identifier(slug, "entrada de catálogo")
        if not isinstance(raw, dict) or raw.get("tipo") not in MEASURE_TYPES:
            raise CivicPolicyError(f"entrada de catálogo inválida: {slug}")
        _text(raw.get("descricao"), f"catalogo.{slug}.descricao", 320)
        institutions = raw.get("instituicoes") or []
        channels = raw.get("canais_sugeridos") or []
        if (
            not isinstance(institutions, list)
            or not institutions
            or len(institutions) != len(set(institutions))
            or any(item not in known or not known[item].get("autorizada") for item in institutions)
        ):
            raise CivicPolicyError(f"instituições inválidas no catálogo {slug}")
        if (
            not isinstance(channels, list)
            or not channels
            or len(channels) != len(set(channels))
            or set(channels) - CHANNELS
        ):
            raise CivicPolicyError(f"canais sugeridos inválidos no catálogo {slug}")
    return data


def configured(repo: Path) -> bool:
    root = Path(repo)
    return (root / REGISTRY_FILE).is_file() and (root / CATALOG_FILE).is_file()


def empty_state() -> dict[str, Any]:
    return {
        "schema_politica_civica": SCHEMA,
        "medidas": {},
        "planos": {},
        "publicacoes": {},
        "entregas": {},
    }


def _scope(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"localidades", "descricao"}:
        raise CivicPolicyError("escopo exige localidades e descricao")
    locations = value.get("localidades")
    if (
        not isinstance(locations, list)
        or not 1 <= len(locations) <= 8
        or len(locations) != len(set(locations))
    ):
        raise CivicPolicyError("escopo.localidades exige 1..8 localidades únicas")
    normalized = [_identifier(item, "escopo.localidade") for item in locations]
    if len(normalized) != len(set(normalized)):
        raise CivicPolicyError("escopo.localidades colide após normalização")
    return {"localidades": normalized, "descricao": _text(value.get("descricao"), "escopo.descricao", 480)}


def _scope_allows(scope: dict[str, Any], locality: str) -> bool:
    locations = scope["localidades"]
    return locality in locations or "ravens_bluff" in locations


def _publication_id(measure_id: str, locality: str, period: str) -> str:
    return "pub-" + _digest({"medida": measure_id, "localidade": locality, "periodo": period})[:20]


def _delivery_id(publication_id: str) -> str:
    return "ent-" + _digest({"publicacao": publication_id, "destinatario": "ren"})[:20]


def _plan_id(measure_id: str, action: str, due: dict[str, str]) -> str:
    return "plc-" + _digest({"medida": measure_id, "acao": action, "devido_em": due})[:20]


def _validate_measure(measure_id: str, raw: Any, registry: dict[str, Any], catalog: dict[str, Any]) -> None:
    required = {
        "id", "instituicao", "tipo", "titulo", "motivo", "causa_institucional",
        "escopo", "fase", "criada_em", "historico",
    }
    allowed = required | {"catalogo", "substituida_por"}
    if not isinstance(raw, dict) or not required <= set(raw) or set(raw) - allowed:
        raise CivicPolicyError(f"medida {measure_id} possui campos inválidos")
    if raw.get("id") != measure_id or _identifier(measure_id, "medida.id") != measure_id:
        raise CivicPolicyError(f"id inconsistente para medida {measure_id}")
    institution_id = _identifier(raw.get("instituicao"), f"medidas.{measure_id}.instituicao")
    institution = registry["instituicoes"].get(institution_id)
    if not isinstance(institution, dict) or not institution.get("autorizada"):
        raise CivicPolicyError(f"instituição não autorizada para criar medida: {institution_id}")
    measure_type = raw.get("tipo")
    if measure_type not in MEASURE_TYPES or measure_type not in institution.get("tipos", []):
        raise CivicPolicyError(f"tipo {measure_type!r} não autorizado para {institution_id}")
    _text(raw.get("titulo"), f"medidas.{measure_id}.titulo", 200)
    _text(raw.get("motivo"), f"medidas.{measure_id}.motivo", 640)
    _text(raw.get("causa_institucional"), f"medidas.{measure_id}.causa_institucional", 640)
    _scope(raw.get("escopo"))
    created = _moment(raw.get("criada_em"), f"medidas.{measure_id}.criada_em")
    phase = raw.get("fase")
    if phase not in PHASES:
        raise CivicPolicyError(f"fase inválida para medida {measure_id}: {phase}")
    catalog_slug = raw.get("catalogo")
    if catalog_slug is not None:
        catalog_slug = _identifier(catalog_slug, f"medidas.{measure_id}.catalogo")
        entry = catalog["medidas_menores"].get(catalog_slug)
        if not isinstance(entry, dict):
            raise CivicPolicyError(f"catálogo inexistente: {catalog_slug}")
        if entry["tipo"] != measure_type or institution_id not in entry["instituicoes"]:
            raise CivicPolicyError(f"catálogo {catalog_slug} incompatível com medida/instituição")
    history = raw.get("historico")
    if not isinstance(history, list) or not 1 <= len(history) <= MAX_HISTORY:
        raise CivicPolicyError(f"histórico inválido para medida {measure_id}")
    previous_phase = None
    previous_minute = _minute(created)
    for index, item in enumerate(history):
        if not isinstance(item, dict) or set(item) != {"estado", "em", "ator", "motivo"}:
            raise CivicPolicyError(f"histórico inválido em {measure_id}[{index}]")
        state = item.get("estado")
        if state not in PHASES:
            raise CivicPolicyError(f"estado inválido no histórico de {measure_id}")
        actor = _identifier(item.get("ator"), f"historico.{measure_id}.ator")
        if actor != institution_id:
            raise CivicPolicyError("NV-22 não permite outra instituição avançar medida sem contrato explícito")
        _text(item.get("motivo"), f"historico.{measure_id}.motivo", 640)
        when = _moment(item.get("em"), f"historico.{measure_id}.em")
        if _minute(when) < previous_minute:
            raise CivicPolicyError(f"histórico temporalmente regressivo: {measure_id}")
        previous_minute = _minute(when)
        if index == 0:
            if state != "proposta":
                raise CivicPolicyError(f"histórico de {measure_id} deve começar em proposta")
        elif state not in TRANSITIONS[previous_phase]:
            raise CivicPolicyError(f"transição cívica inválida: {previous_phase} -> {state}")
        previous_phase = state
    if previous_phase != phase:
        raise CivicPolicyError(f"fase atual diverge do histórico: {measure_id}")
    if phase == "substituida":
        replacement = _identifier(raw.get("substituida_por"), f"medidas.{measure_id}.substituida_por")
        if replacement == measure_id:
            raise CivicPolicyError("medida não pode substituir a si mesma")
    elif "substituida_por" in raw:
        raise CivicPolicyError("substituida_por só existe na fase substituida")


def _validate_plan(plan_id: str, raw: Any, measures: dict[str, Any]) -> None:
    required = {"id", "medida", "instituicao", "acao", "devido_em", "estado", "motivo"}
    if not isinstance(raw, dict) or set(raw) != required or raw.get("id") != plan_id:
        raise CivicPolicyError(f"plano cívico inválido: {plan_id}")
    measure_id = _identifier(raw.get("medida"), f"planos.{plan_id}.medida")
    measure = measures.get(measure_id)
    if not isinstance(measure, dict):
        raise CivicPolicyError(f"plano {plan_id} aponta medida inexistente")
    if raw.get("instituicao") != measure.get("instituicao"):
        raise CivicPolicyError(f"plano {plan_id} pertence à instituição errada")
    action = raw.get("acao")
    if action not in ACTIONS:
        raise CivicPolicyError(f"ação cívica inválida: {action}")
    due = _moment(raw.get("devido_em"), f"planos.{plan_id}.devido_em")
    if plan_id != _plan_id(measure_id, action, due):
        raise CivicPolicyError(f"id determinístico inválido para plano {plan_id}")
    state = raw.get("estado")
    if state not in PLAN_STATES:
        raise CivicPolicyError(f"estado inválido para plano {plan_id}")
    _text(raw.get("motivo"), f"planos.{plan_id}.motivo", 480)
    if state == "pendente" and ACTIONS[action] not in TRANSITIONS[measure["fase"]]:
        raise CivicPolicyError(f"plano pendente {plan_id} não é sucessor da fase atual")


def _validate_publication(pub_id: str, raw: Any, measures: dict[str, Any], registry: dict[str, Any]) -> None:
    required = {
        "id", "medida", "instituicao", "localidade", "periodo", "canal",
        "conteudo", "produzida_em",
    }
    if not isinstance(raw, dict) or set(raw) != required or raw.get("id") != pub_id:
        raise CivicPolicyError(f"publicação cívica inválida: {pub_id}")
    measure_id = _identifier(raw.get("medida"), f"publicacoes.{pub_id}.medida")
    measure = measures.get(measure_id)
    if not isinstance(measure, dict):
        raise CivicPolicyError(f"publicação {pub_id} aponta medida inexistente")
    institution_id = measure["instituicao"]
    if raw.get("instituicao") != institution_id:
        raise CivicPolicyError(f"publicação {pub_id} possui autoria incompatível")
    locality = _identifier(raw.get("localidade"), f"publicacoes.{pub_id}.localidade")
    if not _scope_allows(measure["escopo"], locality):
        raise CivicPolicyError(f"publicação {pub_id} está fora do escopo da medida")
    period = _text(raw.get("periodo"), f"publicacoes.{pub_id}.periodo", 120)
    channel = raw.get("canal")
    if channel not in CHANNELS or channel not in registry["instituicoes"][institution_id]["canais"]:
        raise CivicPolicyError(f"canal {channel!r} não autorizado para {institution_id}")
    if channel in ACTIVE_CHANNELS and period == PERSISTENT_PERIOD:
        raise CivicPolicyError(f"canal ativo {channel} não pode fingir permanência espacial")
    _text(raw.get("conteudo"), f"publicacoes.{pub_id}.conteudo", 1200)
    _moment(raw.get("produzida_em"), f"publicacoes.{pub_id}.produzida_em")
    if pub_id != _publication_id(measure_id, locality, period):
        raise CivicPolicyError(f"id determinístico inválido para publicação {pub_id}")
    if not any(item.get("estado") == "publicada" for item in measure["historico"]):
        raise CivicPolicyError(f"publicação {pub_id} não possui marco de publicação na medida")


def _validate_delivery(delivery_id: str, raw: Any, publications: dict[str, Any]) -> None:
    required = {
        "id", "publicacao", "medida", "destinatario", "localidade", "periodo",
        "canal", "evidencia_canal", "entregue_em",
    }
    if not isinstance(raw, dict) or set(raw) != required or raw.get("id") != delivery_id:
        raise CivicPolicyError(f"entrega cívica inválida: {delivery_id}")
    publication_id = _text(raw.get("publicacao"), f"entregas.{delivery_id}.publicacao", 96)
    publication = publications.get(publication_id)
    if not isinstance(publication, dict):
        raise CivicPolicyError(f"entrega {delivery_id} aponta publicação inexistente")
    if raw.get("destinatario") != "ren":
        raise CivicPolicyError("NV-22 registra conhecimento público somente para Ren")
    for key in ("medida", "localidade", "periodo", "canal"):
        if raw.get(key) != publication.get(key):
            raise CivicPolicyError(f"entrega {delivery_id} diverge da publicação em {key}")
    _text(raw.get("evidencia_canal"), f"entregas.{delivery_id}.evidencia_canal", 480)
    delivered = _moment(raw.get("entregue_em"), f"entregas.{delivery_id}.entregue_em")
    if _minute(delivered) < _minute(publication["produzida_em"]):
        raise CivicPolicyError(f"entrega {delivery_id} antecede a publicação")
    if delivery_id != _delivery_id(publication_id):
        raise CivicPolicyError(f"id determinístico inválido para entrega {delivery_id}")


def validate_state(value: Any, registry: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    if value is None:
        return empty_state()
    required = {"schema_politica_civica", "medidas", "planos", "publicacoes", "entregas"}
    if not isinstance(value, dict) or set(value) != required or value.get("schema_politica_civica") != SCHEMA:
        raise CivicPolicyError("estado de política cívica inválido")
    measures = value.get("medidas")
    plans = value.get("planos")
    publications = value.get("publicacoes")
    deliveries = value.get("entregas")
    if not isinstance(measures, dict) or len(measures) > MAX_MEASURES:
        raise CivicPolicyError("medidas cívicas excedem orçamento")
    if not isinstance(plans, dict) or len(plans) > MAX_PLANS:
        raise CivicPolicyError("agenda cívica excede orçamento")
    if not isinstance(publications, dict) or len(publications) > MAX_PUBLICATIONS:
        raise CivicPolicyError("publicações cívicas excedem orçamento")
    if not isinstance(deliveries, dict) or len(deliveries) > MAX_DELIVERIES:
        raise CivicPolicyError("entregas cívicas excedem orçamento")
    for measure_id, raw in measures.items():
        _validate_measure(measure_id, raw, registry, catalog)
    pending_by_measure: dict[str, int] = {}
    for plan_id, raw in plans.items():
        _validate_plan(plan_id, raw, measures)
        if raw["estado"] == "pendente":
            pending_by_measure[raw["medida"]] = pending_by_measure.get(raw["medida"], 0) + 1
    if any(count > 1 for count in pending_by_measure.values()):
        raise CivicPolicyError("cada medida aceita no máximo um plano institucional pendente")
    signatures: set[tuple[str, str, str]] = set()
    for pub_id, raw in publications.items():
        _validate_publication(pub_id, raw, measures, registry)
        signature = (raw["medida"], raw["localidade"], raw["periodo"])
        if signature in signatures:
            raise CivicPolicyError("proclamação duplicada para medida/local/período")
        signatures.add(signature)
    for delivery_id, raw in deliveries.items():
        _validate_delivery(delivery_id, raw, publications)
    rendered = yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8")
    if len(rendered) > MAX_STATE_BYTES:
        raise CivicPolicyError(f"estado cívico excede {MAX_STATE_BYTES} bytes")
    return value


def load_state(repo: Path, registry: dict[str, Any] | None = None, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    root = Path(repo)
    registry = registry or load_registry(root)
    catalog = catalog or load_catalog(root, registry)
    data = _read_yaml(root / STATE_FILE, STATE_FILE.as_posix())
    state = data.get(STATE_ROOT)
    if state is None:
        return empty_state()
    validate_state(state, registry, catalog)
    return deepcopy(state)


def state_delta(
    state: dict[str, Any],
    reason: str,
    *,
    new_publications: list[str] | None = None,
    new_deliveries: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "alvo": "estado",
        "op": "set",
        "caminho": STATE_ROOT,
        "valor": deepcopy(state),
        "visibilidade": "operacional",
        "metadata": {
            "motivo_politica_civica": _text(reason, "motivo do delta cívico", 200),
            "novas_publicacoes": sorted(new_publications or []),
            "novas_entregas": sorted(new_deliveries or []),
        },
    }


def touches(delta: Any) -> bool:
    if not isinstance(delta, dict) or delta.get("alvo") != "estado":
        return False
    path = delta.get("caminho")
    return isinstance(path, str) and (path == STATE_ROOT or path.startswith(STATE_ROOT + "."))


def _metadata(delta: dict[str, Any]) -> dict[str, Any]:
    metadata = delta.get("metadata")
    if not isinstance(metadata, dict):
        raise CivicPolicyError("delta cívico exige metadata")
    required = {"motivo_politica_civica", "novas_publicacoes", "novas_entregas"}
    if set(metadata) != required:
        raise CivicPolicyError("metadata cívica possui campos inválidos")
    _text(metadata.get("motivo_politica_civica"), "metadata.motivo_politica_civica", 200)
    for key in ("novas_publicacoes", "novas_entregas"):
        value = metadata.get(key)
        if not isinstance(value, list) or len(value) != len(set(value)) or value != sorted(value):
            raise CivicPolicyError(f"metadata.{key} deve ser lista única e ordenada")
        for item in value:
            _text(item, f"metadata.{key}", 96)
    return metadata


def validate_delta_shape(delta: Any, registry: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    if not touches(delta):
        return delta
    if (
        delta.get("alvo") != "estado"
        or delta.get("op") != "set"
        or delta.get("caminho") != STATE_ROOT
        or delta.get("visibilidade", "operacional") != "operacional"
    ):
        raise CivicPolicyError("NV-22 só aceita set atômico da raiz politica_civica")
    _metadata(delta)
    validate_state(delta.get("valor"), registry, catalog)
    return delta


def _stable_fields(measure: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(measure.get(key))
        for key in (
            "id", "instituicao", "tipo", "titulo", "motivo", "causa_institucional",
            "escopo", "criada_em", "catalogo",
        )
        if key in measure
    }


def validate_transition(
    old: dict[str, Any],
    new: dict[str, Any],
    delta: dict[str, Any],
    registry: dict[str, Any],
    catalog: dict[str, Any],
) -> dict[str, Any]:
    validate_state(old, registry, catalog)
    validate_delta_shape(delta, registry, catalog)
    if delta.get("valor") != new:
        raise CivicPolicyError("transição cívica diverge do valor do delta")
    validate_state(new, registry, catalog)

    for collection in ("medidas", "planos", "publicacoes", "entregas"):
        if not set(old[collection]) <= set(new[collection]):
            raise CivicPolicyError(f"NV-22 não apaga registros de {collection}")

    for measure_id, before in old["medidas"].items():
        after = new["medidas"][measure_id]
        if _stable_fields(before) != _stable_fields(after):
            raise CivicPolicyError(f"núcleo imutável da medida foi alterado: {measure_id}")
        old_history = before["historico"]
        new_history = after["historico"]
        if new_history[: len(old_history)] != old_history or len(new_history) - len(old_history) not in {0, 1}:
            raise CivicPolicyError(f"histórico da medida não é append-only: {measure_id}")
        if len(new_history) == len(old_history):
            if before["fase"] != after["fase"] or before.get("substituida_por") != after.get("substituida_por"):
                raise CivicPolicyError(f"fase mudou sem histórico: {measure_id}")
        else:
            target = after["fase"]
            if target not in TRANSITIONS[before["fase"]]:
                raise CivicPolicyError(f"transição inválida: {before['fase']} -> {target}")
            if target == "substituida":
                replacement = after.get("substituida_por")
                if replacement not in new["medidas"]:
                    raise CivicPolicyError("substituição exige medida substituta já registrada")
    for measure_id in set(new["medidas"]) - set(old["medidas"]):
        measure = new["medidas"][measure_id]
        if measure["fase"] != "proposta" or len(measure["historico"]) != 1:
            raise CivicPolicyError("medida nova só pode nascer como proposta")

    for plan_id, before in old["planos"].items():
        after = new["planos"][plan_id]
        stable = {key: before[key] for key in before if key != "estado"}
        if stable != {key: after[key] for key in after if key != "estado"}:
            raise CivicPolicyError(f"plano institucional foi reescrito: {plan_id}")
        if before["estado"] != after["estado"]:
            if before["estado"] != "pendente" or after["estado"] not in {"concluido", "cancelado"}:
                raise CivicPolicyError(f"transição inválida de plano: {plan_id}")
    for plan_id in set(new["planos"]) - set(old["planos"]):
        if new["planos"][plan_id]["estado"] != "pendente":
            raise CivicPolicyError("plano institucional novo deve nascer pendente")

    new_publications = sorted(set(new["publicacoes"]) - set(old["publicacoes"]))
    for pub_id, before in old["publicacoes"].items():
        if new["publicacoes"][pub_id] != before:
            raise CivicPolicyError(f"publicação cívica é append-only: {pub_id}")
    for pub_id in new_publications:
        measure = new["medidas"][new["publicacoes"][pub_id]["medida"]]
        if measure["fase"] != "publicada":
            raise CivicPolicyError("nova publicação só pode ser produzida por medida publicada")

    new_deliveries = sorted(set(new["entregas"]) - set(old["entregas"]))
    for delivery_id, before in old["entregas"].items():
        if new["entregas"][delivery_id] != before:
            raise CivicPolicyError(f"entrega cívica é append-only: {delivery_id}")
    for delivery_id in new_deliveries:
        measure = new["medidas"][new["entregas"][delivery_id]["medida"]]
        if measure["fase"] != "publicada":
            raise CivicPolicyError("nova entrega exige medida ainda publicada")

    metadata = _metadata(delta)
    if metadata["novas_publicacoes"] != new_publications:
        raise CivicPolicyError("metadata de novas publicações diverge da transição")
    if metadata["novas_entregas"] != new_deliveries:
        raise CivicPolicyError("metadata de novas entregas diverge da transição")
    return new


def receipt_pending_id(delivery_id: str) -> str:
    return "mundo-" + hashlib.sha256(f"politica-civica|{delivery_id}".encode("utf-8")).hexdigest()[:16]


def receipt_cause(publication_id: str) -> str:
    return f"politica_civica.publicacoes.{publication_id}"


def receipt_delta(delivery: dict[str, Any], publication: dict[str, Any]) -> dict[str, Any]:
    pending_id = receipt_pending_id(delivery["id"])
    return {
        "alvo": _delivery.target_for(pending_id),
        "op": "registrar",
        "valor": {
            "versao": _delivery.SCHEMA,
            "tipo": "entrega_causal",
            "pendencia": pending_id,
            "comunicavel": True,
            "destinatario": "ren",
            "causa": receipt_cause(publication["id"]),
            "conteudo": publication["conteudo"],
            "destino": {"estado": "entregue", "canal": publication["canal"]},
        },
        "visibilidade": "narrador",
    }


def is_civic_receipt(delta: Any) -> bool:
    if not isinstance(delta, dict) or not isinstance(delta.get("valor"), dict):
        return False
    value = delta["valor"]
    return (
        value.get("tipo") == "entrega_causal"
        and isinstance(value.get("causa"), str)
        and value["causa"].startswith("politica_civica.publicacoes.")
    )


def validate_transaction_contract(
    deltas: list[dict[str, Any]], registry: dict[str, Any], catalog: dict[str, Any]
) -> None:
    roots = [delta for delta in deltas if touches(delta)]
    receipts = [delta for delta in deltas if is_civic_receipt(delta)]
    if len(roots) > 1:
        raise CivicPolicyError("uma transação NV-22 aceita no máximo um set da raiz cívica")
    if not roots:
        if receipts:
            raise CivicPolicyError("recibo cívico NV-13 exige a entrega NV-22 no mesmo writer")
        return
    root = validate_delta_shape(roots[0], registry, catalog)
    state = root["valor"]
    declared = _metadata(root)["novas_entregas"]
    expected: list[dict[str, Any]] = []
    for delivery_id in declared:
        delivery = state["entregas"].get(delivery_id)
        if not isinstance(delivery, dict):
            raise CivicPolicyError(f"entrega declarada ausente do estado: {delivery_id}")
        publication = state["publicacoes"][delivery["publicacao"]]
        expected.append(receipt_delta(delivery, publication))
    if sorted((_canonical(item) for item in receipts)) != sorted((_canonical(item) for item in expected)):
        raise CivicPolicyError("entrega cívica e recibo NV-13 precisam ser pareados exatamente no mesmo writer")
    for item in expected:
        pending_id = item["valor"]["pendencia"]
        try:
            _delivery.validate_event(item["valor"], pending_id)
        except _delivery.DeliveryError as exc:
            raise CivicPolicyError(str(exc)) from exc


def validate_batch(repo: Path, records: list[dict[str, Any]]) -> dict[str, Any]:
    registry = load_registry(repo)
    catalog = load_catalog(repo, registry)
    state = load_state(repo, registry, catalog)
    for record in records:
        deltas = list(record.get("deltas") or [])
        if any(touches(delta) for delta in deltas) or any(is_civic_receipt(delta) for delta in deltas):
            validate_transaction_contract(deltas, registry, catalog)
        roots = [delta for delta in deltas if touches(delta)]
        if roots:
            validate_transition(state, roots[0]["valor"], roots[0], registry, catalog)
            state = deepcopy(roots[0]["valor"])
    return state


def _configs(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = load_registry(repo)
    return registry, load_catalog(repo, registry)


def _new_measure_id(institution: str, title: str, when: dict[str, str]) -> str:
    return "med-" + _digest({"instituicao": institution, "titulo": title, "criada_em": when})[:20]


def _ensure_authorized(registry: dict[str, Any], institution_id: str, measure_type: str) -> dict[str, Any]:
    institution = registry["instituicoes"].get(institution_id)
    if not isinstance(institution, dict) or not institution.get("autorizada"):
        raise CivicPolicyError(f"instituição não autorizada: {institution_id}")
    if measure_type not in institution.get("tipos", []):
        raise CivicPolicyError(f"{institution_id} não pode criar medida do tipo {measure_type}")
    return institution


def _append_plan(
    state: dict[str, Any], measure_id: str, action: str, due_at: dict[str, str], reason: str
) -> str:
    measure = state["medidas"][measure_id]
    if action not in ACTIONS or ACTIONS[action] not in TRANSITIONS[measure["fase"]]:
        raise CivicPolicyError(f"ação {action!r} não é sucessora de {measure['fase']}")
    if any(
        plan["estado"] == "pendente" and plan["medida"] == measure_id
        for plan in state["planos"].values()
    ):
        raise CivicPolicyError("medida já possui plano institucional pendente")
    due = _moment(due_at, "devido_em")
    plan_id = _plan_id(measure_id, action, due)
    plan = {
        "id": plan_id,
        "medida": measure_id,
        "instituicao": measure["instituicao"],
        "acao": action,
        "devido_em": due,
        "estado": "pendente",
        "motivo": _text(reason, "motivo do plano", 480),
    }
    existing = state["planos"].get(plan_id)
    if existing is not None and existing != plan:
        raise CivicPolicyError(f"colisão no plano {plan_id}")
    state["planos"][plan_id] = plan
    return plan_id


def propose_measure(
    repo: Path,
    *,
    institution: str,
    measure_type: str,
    title: str,
    motive: str,
    institutional_cause: str,
    scope: dict[str, Any],
    when: dict[str, str],
    measure_id: str | None = None,
    catalog_slug: str | None = None,
    next_action: str | None = None,
    due_at: dict[str, str] | None = None,
    plan_reason: str | None = None,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry, catalog = _configs(Path(repo))
    current = deepcopy(state) if state is not None else load_state(Path(repo), registry, catalog)
    validate_state(current, registry, catalog)
    institution_id = _identifier(institution, "instituicao")
    if measure_type not in MEASURE_TYPES:
        raise CivicPolicyError(f"tipo de medida inválido: {measure_type}")
    _ensure_authorized(registry, institution_id, measure_type)
    title = _text(title, "titulo", 200)
    when = _moment(when, "criada_em")
    scope = _scope(scope)
    if catalog_slug is not None:
        catalog_slug = _identifier(catalog_slug, "catalogo")
        entry = catalog["medidas_menores"].get(catalog_slug)
        if not isinstance(entry, dict):
            raise CivicPolicyError(f"catálogo inexistente: {catalog_slug}")
        if entry["tipo"] != measure_type or institution_id not in entry["instituicoes"]:
            raise CivicPolicyError("catálogo menor exige causa institucional e competência compatíveis")
    measure_id = _identifier(measure_id, "medida") if measure_id else _new_measure_id(institution_id, title, when)
    measure = {
        "id": measure_id,
        "instituicao": institution_id,
        "tipo": measure_type,
        "titulo": title,
        "motivo": _text(motive, "motivo", 640),
        "causa_institucional": _text(institutional_cause, "causa_institucional", 640),
        "escopo": scope,
        "fase": "proposta",
        "criada_em": when,
        "historico": [{
            "estado": "proposta",
            "em": deepcopy(when),
            "ator": institution_id,
            "motivo": _text(motive, "motivo", 640),
        }],
    }
    if catalog_slug is not None:
        measure["catalogo"] = catalog_slug
    existing = current["medidas"].get(measure_id)
    if existing is not None:
        if existing == measure:
            return {"resultado": "ja_registrada", "medida": measure_id, "plano": None, "deltas": []}
        raise CivicPolicyError(f"medida {measure_id} já existe com conteúdo diferente")
    current["medidas"][measure_id] = measure
    plan_id = None
    if any(value is not None for value in (next_action, due_at, plan_reason)):
        if next_action is None or due_at is None or plan_reason is None:
            raise CivicPolicyError("agenda inicial exige next_action, due_at e plan_reason juntos")
        plan_id = _append_plan(current, measure_id, next_action, due_at, plan_reason)
    delta = state_delta(current, "proposta_institucional")
    validate_transition(load_state(Path(repo), registry, catalog) if state is None else state, current, delta, registry, catalog)
    return {"resultado": "proposta", "medida": measure_id, "plano": plan_id, "deltas": [delta]}


def propose_plan(
    repo: Path,
    *,
    measure_id: str,
    action: str,
    due_at: dict[str, str],
    reason: str,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry, catalog = _configs(Path(repo))
    old = deepcopy(state) if state is not None else load_state(Path(repo), registry, catalog)
    current = deepcopy(old)
    measure_id = _identifier(measure_id, "medida")
    if measure_id not in current["medidas"]:
        raise CivicPolicyError(f"medida inexistente: {measure_id}")
    plan_id = _plan_id(measure_id, action, _moment(due_at, "devido_em")) if action in ACTIONS else ""
    if plan_id and plan_id in current["planos"]:
        return {"resultado": "ja_agendado", "plano": plan_id, "deltas": []}
    plan_id = _append_plan(current, measure_id, action, due_at, reason)
    delta = state_delta(current, "agenda_institucional")
    validate_transition(old, current, delta, registry, catalog)
    return {"resultado": "agendado", "plano": plan_id, "deltas": [delta]}


def due_plans(repo: Path, *, now: dict[str, str], state: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    registry, catalog = _configs(Path(repo))
    current = deepcopy(state) if state is not None else load_state(Path(repo), registry, catalog)
    validate_state(current, registry, catalog)
    instant = _minute(_moment(now, "agora"))
    result = [
        deepcopy(plan)
        for plan in current["planos"].values()
        if plan["estado"] == "pendente" and _minute(plan["devido_em"]) <= instant
    ]
    result.sort(key=lambda item: (_minute(item["devido_em"]), item["id"]))
    return result[:16]


def _close_plan(state: dict[str, Any], plan_id: str | None, measure_id: str, target_phase: str) -> None:
    if plan_id is None:
        return
    plan_id = _text(plan_id, "plano", 96)
    plan = state["planos"].get(plan_id)
    if not isinstance(plan, dict) or plan["estado"] != "pendente":
        raise CivicPolicyError(f"plano institucional pendente inexistente: {plan_id}")
    if plan["medida"] != measure_id or ACTIONS[plan["acao"]] != target_phase:
        raise CivicPolicyError("plano institucional não autoriza esta transição")
    plan["estado"] = "concluido"


def propose_transition(
    repo: Path,
    *,
    measure_id: str,
    target_phase: str,
    when: dict[str, str],
    reason: str,
    plan_id: str | None = None,
    replacement_id: str | None = None,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if target_phase == "publicada":
        raise CivicPolicyError("a fase publicada só pode nascer junto de propose_publication")
    registry, catalog = _configs(Path(repo))
    old = deepcopy(state) if state is not None else load_state(Path(repo), registry, catalog)
    current = deepcopy(old)
    measure_id = _identifier(measure_id, "medida")
    measure = current["medidas"].get(measure_id)
    if not isinstance(measure, dict):
        raise CivicPolicyError(f"medida inexistente: {measure_id}")
    if target_phase not in TRANSITIONS[measure["fase"]]:
        raise CivicPolicyError(f"transição inválida: {measure['fase']} -> {target_phase}")
    when = _moment(when, "transicao.em")
    if _minute(when) < _minute(measure["historico"][-1]["em"]):
        raise CivicPolicyError("transição não pode anteceder o histórico da medida")
    _close_plan(current, plan_id, measure_id, target_phase)
    if target_phase == "substituida":
        replacement_id = _identifier(replacement_id, "substituida_por")
        if replacement_id == measure_id or replacement_id not in current["medidas"]:
            raise CivicPolicyError("substituição exige outra medida já registrada")
        measure["substituida_por"] = replacement_id
    elif replacement_id is not None:
        raise CivicPolicyError("replacement_id só é válido para substituição")
    measure["fase"] = target_phase
    measure["historico"].append({
        "estado": target_phase,
        "em": when,
        "ator": measure["instituicao"],
        "motivo": _text(reason, "motivo da transição", 640),
    })
    delta = state_delta(current, "transicao_institucional")
    validate_transition(old, current, delta, registry, catalog)
    return {"resultado": target_phase, "medida": measure_id, "deltas": [delta]}


def propose_publication(
    repo: Path,
    *,
    measure_id: str,
    locality: str,
    period: str,
    channel: str,
    content: str,
    when: dict[str, str],
    plan_id: str | None = None,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry, catalog = _configs(Path(repo))
    old = deepcopy(state) if state is not None else load_state(Path(repo), registry, catalog)
    current = deepcopy(old)
    measure_id = _identifier(measure_id, "medida")
    measure = current["medidas"].get(measure_id)
    if not isinstance(measure, dict):
        raise CivicPolicyError(f"medida inexistente: {measure_id}")
    if measure["fase"] not in {"vigente", "publicada"}:
        raise CivicPolicyError("publicação exige medida vigente ou já publicada")
    locality = _identifier(locality, "localidade")
    if not _scope_allows(measure["escopo"], locality):
        raise CivicPolicyError("localidade de publicação está fora do escopo")
    period = _text(period, "periodo", 120)
    institution = registry["instituicoes"][measure["instituicao"]]
    if channel not in CHANNELS or channel not in institution["canais"]:
        raise CivicPolicyError(f"canal {channel!r} incompatível com a instituição")
    if channel in ACTIVE_CHANNELS and period == PERSISTENT_PERIOD:
        raise CivicPolicyError("arauto/guarda/templo/mensageiro exigem janela causal, não persistência fictícia")
    pub_id = _publication_id(measure_id, locality, period)
    if pub_id in current["publicacoes"]:
        existing = current["publicacoes"][pub_id]
        if existing["canal"] == channel and existing["conteudo"] == _text(content, "conteudo", 1200):
            return {"resultado": "ja_publicada", "publicacao": pub_id, "deltas": []}
        raise CivicPolicyError("mesma medida/local/período já possui proclamação diferente")
    when = _moment(when, "publicada_em")
    if _minute(when) < _minute(measure["historico"][-1]["em"]):
        raise CivicPolicyError("publicação não pode anteceder a fase atual")
    if measure["fase"] == "vigente":
        _close_plan(current, plan_id, measure_id, "publicada")
        measure["fase"] = "publicada"
        measure["historico"].append({
            "estado": "publicada",
            "em": deepcopy(when),
            "ator": measure["instituicao"],
            "motivo": "proclamação produzida por canal público compatível",
        })
    elif plan_id is not None:
        raise CivicPolicyError("plan_id de publicação só fecha a primeira passagem para publicada")
    current["publicacoes"][pub_id] = {
        "id": pub_id,
        "medida": measure_id,
        "instituicao": measure["instituicao"],
        "localidade": locality,
        "periodo": period,
        "canal": channel,
        "conteudo": _text(content, "conteudo", 1200),
        "produzida_em": when,
    }
    delta = state_delta(current, "publicacao_civica", new_publications=[pub_id])
    validate_transition(old, current, delta, registry, catalog)
    return {"resultado": "publicada", "publicacao": pub_id, "deltas": [delta]}


def propose_delivery(
    repo: Path,
    *,
    publication_id: str,
    evidence: str,
    when: dict[str, str],
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry, catalog = _configs(Path(repo))
    old = deepcopy(state) if state is not None else load_state(Path(repo), registry, catalog)
    current = deepcopy(old)
    publication_id = _text(publication_id, "publicacao", 96)
    publication = current["publicacoes"].get(publication_id)
    if not isinstance(publication, dict):
        raise CivicPolicyError(f"publicação inexistente: {publication_id}")
    measure = current["medidas"][publication["medida"]]
    if measure["fase"] != "publicada":
        raise CivicPolicyError("Ren não recebe como vigente proclamação de medida encerrada")
    delivery_id = _delivery_id(publication_id)
    if delivery_id in current["entregas"]:
        return {"resultado": "ja_entregue", "entrega": delivery_id, "deltas": []}
    delivered = _moment(when, "entregue_em")
    record = {
        "id": delivery_id,
        "publicacao": publication_id,
        "medida": publication["medida"],
        "destinatario": "ren",
        "localidade": publication["localidade"],
        "periodo": publication["periodo"],
        "canal": publication["canal"],
        "evidencia_canal": _text(evidence, "evidencia_canal", 480),
        "entregue_em": delivered,
    }
    current["entregas"][delivery_id] = record
    delta = state_delta(current, "entrega_publica_ren", new_deliveries=[delivery_id])
    validate_transition(old, current, delta, registry, catalog)
    receipt = receipt_delta(record, publication)
    validate_transaction_contract([delta, receipt], registry, catalog)
    return {"resultado": "entregue", "entrega": delivery_id, "deltas": [delta, receipt]}


def project_for_permanence(
    repo: Path,
    *,
    locality: str,
    date: str,
    period: str,
    evaluation_id: str | None = None,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry, catalog = _configs(Path(repo))
    current = deepcopy(state) if state is not None else load_state(Path(repo), registry, catalog)
    validate_state(current, registry, catalog)
    locality = _identifier(locality, "localidade")
    date = _text(date, "data", 80)
    period = _text(period, "periodo", 80)
    window = f"{date}|{period}"
    delivered_publications = {item["publicacao"] for item in current["entregas"].values()}
    rows: list[dict[str, Any]] = []
    for publication in current["publicacoes"].values():
        if publication["id"] in delivered_publications:
            continue
        if publication["localidade"] != locality or publication["canal"] not in PERSISTENT_CHANNELS:
            continue
        if publication["periodo"] not in {PERSISTENT_PERIOD, window}:
            continue
        measure = current["medidas"][publication["medida"]]
        if measure["fase"] != "publicada":
            continue
        rows.append({
            "publicacao": publication["id"],
            "medida": measure["id"],
            "titulo": measure["titulo"],
            "canal": publication["canal"],
            "conteudo": publication["conteudo"],
            "localidade": locality,
            "periodo_publicacao": publication["periodo"],
            "evidencia_entrega": (
                f"permanencia:{evaluation_id}" if evaluation_id
                else f"permanencia:{locality}|{window}"
            ),
        })
    rows.sort(key=lambda item: (item["medida"], item["publicacao"]))
    rows = rows[:MAX_PERMANENCE_NOTICES]
    return {
        "schema_avisos_publicos_nv22": SCHEMA,
        "resultado": "avisos_disponiveis" if rows else "nenhum_aviso_publico_produzido",
        "localidade": locality,
        "janela": window,
        "avisos": rows,
        "fontes_lidas": [STATE_FILE.as_posix(), REGISTRY_FILE.as_posix(), CATALOG_FILE.as_posix()],
        "regra": (
            "somente publicações persistentes já produzidas; presença no local não cria lei nem conhecimento. "
            "A ciência de Ren exige entrega NV-13 pareada no writer."
        ),
    }


def known_to_ren(repo: Path, measure_id: str, *, state: dict[str, Any] | None = None) -> bool:
    registry, catalog = _configs(Path(repo))
    current = deepcopy(state) if state is not None else load_state(Path(repo), registry, catalog)
    measure_id = _identifier(measure_id, "medida")
    return any(item["medida"] == measure_id for item in current["entregas"].values())


def check(repo: Path) -> dict[str, Any]:
    registry, catalog = _configs(Path(repo))
    state = load_state(Path(repo), registry, catalog)
    validate_state(state, registry, catalog)
    return {
        "ok": True,
        "schema": SCHEMA,
        "medidas": len(state["medidas"]),
        "planos": len(state["planos"]),
        "publicacoes": len(state["publicacoes"]),
        "entregas": len(state["entregas"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Política cívica e avisos públicos NV-22")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    due = sub.add_parser("vencidas", help="consulta dirigida de planos institucionais vencidos")
    due.add_argument("--data", required=True)
    due.add_argument("--hora", required=True)
    show = sub.add_parser("mostrar", help="mostra uma medida sem sondar instituições")
    show.add_argument("--medida", required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    try:
        if args.command == "check":
            payload = check(repo)
        elif args.command == "vencidas":
            payload = {"planos_vencidos": due_plans(repo, now={"data": args.data, "hora": args.hora})}
        else:
            state = load_state(repo)
            payload = state["medidas"].get(args.medida)
            if payload is None:
                raise CivicPolicyError(f"medida inexistente: {args.medida}")
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    except CivicPolicyError as exc:
        parser.error(str(exc))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
