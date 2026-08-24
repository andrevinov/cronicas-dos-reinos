#!/usr/bin/env python3
"""Reputacao publica de Ren em Ravens Bluff, separada de fama e opiniao individual.

A Task 29 registra somente consequencias sociais explicitamente publicas e atribuidas a
uma persona. O estado canonico continua em ``estado/estado-atual.yaml``; nao existe
scheduler, score global, RNG ou arquivo paralelo de estado.

Uma reputacao pertence ao par ``publico x identidade percebida``. Portanto um feito de
Kage nao altera Ren ou Shinta automaticamente, e confirmacao privada de identidade da
Task 28 tambem nao funde reputacoes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

import yaml

import contexto_core
import identidades

STATE_FILE = Path("estado/estado-atual.yaml")
STATE_ROOT = "reputacao_publica_ren"
AUDIENCE_REGISTRY = Path("cenario/regioes/ravens-bluff/publicos-reputacao.yaml")
IDENTITY_REGISTRY = identidades.REGISTRY
SCHEMA = 1
MAX_PUBLICS_PER_EVENT = 3
MAX_ACTIVE_RECORDS = 8
MAX_SOURCE_CHARS = 60
MAX_STATE_BYTES = 7 * 1024

POSITIVE_MARKS = (
    "resgate_publico",
    "derrota_criminosos",
    "colaboracao_institucional",
    "consequencia_positiva_visivel",
)
NEGATIVE_MARK = "consequencia_negativa_visivel"
CLARIFICATION = "esclarecimento_publico"
MARK_ORDER = (*POSITIVE_MARKS, NEGATIVE_MARK)
EVENT_TYPES = set(MARK_ORDER) | {CLARIFICATION}
LABELS = {
    "estrangeiro_desconhecido",
    "pessoa_perigosa",
    "vigilante",
    "pessoa_util",
    "protetor",
    "heroi_local",
    "figura_controversa",
}
FAVORABLE_LABELS = {"pessoa_util", "protetor", "heroi_local"}


class PublicReputationError(ValueError):
    """Estado ou transicao de reputacao publica incoerente."""


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PublicReputationError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise PublicReputationError(f"YAML invalido em {path}: {exc}") from exc


def _norm(value: Any) -> str:
    return contexto_core.normalize(value)


def _validate_source(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublicReputationError("reputacao exige fonte canonica rastreavel")
    source = value.strip()
    if len(source) > MAX_SOURCE_CHARS:
        raise PublicReputationError(
            f"fonte de reputacao excede {MAX_SOURCE_CHARS} caracteres; use referencia compacta"
        )
    return source


def load_audiences(repo: Path) -> dict[str, Any]:
    data = _load(repo / AUDIENCE_REGISTRY)
    if not isinstance(data, dict) or data.get("schema_publicos_reputacao") != 1:
        raise PublicReputationError("registro de publicos de reputacao invalido")
    if data.get("cidade") != "ravens_bluff":
        raise PublicReputationError("Task 29 v1 cobre somente Ravens Bluff")
    audiences = data.get("publicos")
    if not isinstance(audiences, dict) or not audiences:
        raise PublicReputationError("registro de publicos sem publicos validos")
    for audience_id, entry in audiences.items():
        if not isinstance(audience_id, str) or not re.fullmatch(r"[a-z0-9_]+", audience_id):
            raise PublicReputationError(f"id de publico invalido: {audience_id!r}")
        if not isinstance(entry, dict) or not isinstance(entry.get("nome"), str):
            raise PublicReputationError(f"publico invalido: {audience_id}")
        aliases = entry.get("aliases") or []
        if not isinstance(aliases, list) or any(not isinstance(item, str) for item in aliases):
            raise PublicReputationError(f"aliases invalidos em {audience_id}")
    source = data.get("fonte_estrutura_social")
    if not isinstance(source, str) or not (repo / source).is_file():
        raise PublicReputationError("registro de publicos precisa apontar fonte social existente")
    return data


def load_identities(repo: Path) -> dict[str, Any]:
    return identidades.load_registry(repo)


def resolve_public(audiences: dict[str, Any], term: str) -> str:
    query = _norm(term)
    matches: list[str] = []
    for audience_id, entry in audiences["publicos"].items():
        candidates = [audience_id, entry.get("nome"), *(entry.get("aliases") or [])]
        if any(_norm(candidate) == query for candidate in candidates if candidate):
            matches.append(audience_id)
    if len(matches) != 1:
        raise PublicReputationError(
            f"publico ambiguo/desconhecido {term!r}; use: " + ", ".join(sorted(audiences["publicos"]))
        )
    return matches[0]


def resolve_identity(identity_registry: dict[str, Any], term: str) -> str:
    try:
        return identidades.resolve_identity(identity_registry, term)
    except identidades.IdentitySuspicionError as exc:
        raise PublicReputationError(str(exc)) from exc


def empty_state() -> dict[str, Any]:
    return {
        "schema_reputacao_publica_ren": SCHEMA,
        "cidade": "ravens_bluff",
        "registros": {},
    }


def default_record() -> dict[str, Any]:
    return {"estado": "estrangeiro_desconhecido", "marcos": [], "evidencias": {}}


def _ordered_marks(values: Iterable[str]) -> list[str]:
    present = set(values)
    return [item for item in MARK_ORDER if item in present]


def derive_label(marks: Iterable[str]) -> str:
    current = set(marks)
    positive = current.intersection(POSITIVE_MARKS)
    negative = NEGATIVE_MARK in current
    if negative and positive:
        return "figura_controversa"
    if negative:
        return "pessoa_perigosa"
    if positive == set(POSITIVE_MARKS):
        return "heroi_local"
    if "resgate_publico" in positive:
        return "protetor"
    if "colaboracao_institucional" in positive or "consequencia_positiva_visivel" in positive:
        return "pessoa_util"
    if "derrota_criminosos" in positive:
        return "vigilante"
    return "estrangeiro_desconhecido"


def validate_record(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"estado", "marcos", "evidencias"}:
        raise PublicReputationError("registro de reputacao deve conter estado, marcos e evidencias")
    marks = value.get("marcos")
    evidence = value.get("evidencias")
    if not isinstance(marks, list) or any(item not in MARK_ORDER for item in marks):
        raise PublicReputationError("marcos de reputacao invalidos")
    if len(marks) != len(set(marks)) or marks != _ordered_marks(marks):
        raise PublicReputationError("marcos precisam ser unicos e usar ordem canonica")
    if not isinstance(evidence, dict):
        raise PublicReputationError("evidencias de reputacao precisam ser mapa")
    if any(kind not in EVENT_TYPES for kind in evidence):
        raise PublicReputationError("evidencia possui tipo de reputacao desconhecido")
    for kind, item in evidence.items():
        if not isinstance(item, dict) or set(item) != {"id", "fonte"}:
            raise PublicReputationError(f"evidencia {kind} deve conter somente id e fonte")
        if not isinstance(item.get("id"), str) or not re.fullmatch(r"rep-[0-9a-f]{16}", item["id"]):
            raise PublicReputationError(f"id de evidencia de reputacao invalido: {item.get('id')!r}")
        _validate_source(item.get("fonte"))
    missing = set(marks) - set(evidence)
    if missing:
        raise PublicReputationError("todo marco ativo precisa de evidencia rastreavel")
    inactive = set(evidence) - set(marks) - {CLARIFICATION}
    if inactive:
        if inactive != {NEGATIVE_MARK} or CLARIFICATION not in evidence:
            raise PublicReputationError("evidencia inativa so e preservada apos esclarecimento publico")
    if CLARIFICATION in evidence and NEGATIVE_MARK not in evidence:
        raise PublicReputationError("esclarecimento publico precisa preservar a evidencia negativa esclarecida")
    label = value.get("estado")
    if label not in LABELS or label != derive_label(marks):
        raise PublicReputationError("estado de reputacao deve ser derivado exclusivamente dos marcos ativos")
    return copy.deepcopy(value)


def validate_state(value: Any, audiences: dict[str, Any], identities_registry: dict[str, Any]) -> dict[str, Any]:
    if value is None:
        return empty_state()
    if not isinstance(value, dict) or value.get("schema_reputacao_publica_ren") != SCHEMA:
        raise PublicReputationError("reputacao_publica_ren precisa usar schema 1")
    if set(value) != {"schema_reputacao_publica_ren", "cidade", "registros"}:
        raise PublicReputationError("reputacao_publica_ren possui campos desconhecidos")
    if value.get("cidade") != "ravens_bluff":
        raise PublicReputationError("reputacao publica v1 deve permanecer em Ravens Bluff")
    records = value.get("registros")
    if not isinstance(records, dict):
        raise PublicReputationError("registros de reputacao precisam ser mapa")
    audience_ids = set(audiences["publicos"])
    identity_ids = set(identities_registry["identidades"])
    total = 0
    clean: dict[str, Any] = {}
    for audience_id, by_identity in records.items():
        if audience_id not in audience_ids:
            raise PublicReputationError(f"publico de reputacao desconhecido: {audience_id}")
        if not isinstance(by_identity, dict) or not by_identity:
            raise PublicReputationError(f"{audience_id}: mapa de identidades vazio/invalido")
        clean[audience_id] = {}
        for identity_id, record in by_identity.items():
            if identity_id not in identity_ids:
                raise PublicReputationError(f"identidade publica desconhecida: {identity_id}")
            clean[audience_id][identity_id] = validate_record(record)
            total += 1
    if total > MAX_ACTIVE_RECORDS:
        raise PublicReputationError(
            f"reputacao publica aceita no maximo {MAX_ACTIVE_RECORDS} pares publico x persona"
        )
    result = {
        "schema_reputacao_publica_ren": SCHEMA,
        "cidade": "ravens_bluff",
        "registros": clean,
    }
    size = len(yaml.safe_dump(result, allow_unicode=True, sort_keys=False).encode("utf-8"))
    if size > MAX_STATE_BYTES:
        raise PublicReputationError(
            f"reputacao publica excede orcamento: {size} > {MAX_STATE_BYTES} bytes"
        )
    return result


def event_id(public_id: str, identity_id: str, event_type: str, source: str, fact: str) -> str:
    raw = "\x1f".join([public_id, identity_id, event_type, source.strip(), fact.strip()])
    return "rep-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def touches_reputation(delta: Any) -> bool:
    return (
        isinstance(delta, dict)
        and delta.get("alvo") == "estado"
        and isinstance(delta.get("caminho"), str)
        and (
            delta["caminho"] == STATE_ROOT
            or str(delta["caminho"]).startswith(STATE_ROOT + ".")
        )
    )


def parse_delta_path(delta: dict[str, Any]) -> tuple[str, str]:
    path = str(delta.get("caminho") or "")
    parts = path.split(".")
    if len(parts) != 4 or parts[0] != STATE_ROOT or parts[1] != "registros":
        raise PublicReputationError(
            "reputacao publica so aceita set de um par registros.<publico>.<identidade>"
        )
    return parts[2], parts[3]


def is_reputation_delta(delta: Any) -> bool:
    if not touches_reputation(delta):
        return False
    try:
        parse_delta_path(delta)
    except PublicReputationError:
        return False
    return True


def validate_reputation_delta(
    delta: Any,
    audiences: dict[str, Any],
    identities_registry: dict[str, Any],
) -> dict[str, Any]:
    if not is_reputation_delta(delta):
        raise PublicReputationError("delta nao aponta um par valido de reputacao publica")
    if delta.get("op") != "set":
        raise PublicReputationError("reputacao publica aceita somente set do registro compacto inteiro")
    if delta.get("visibilidade", "operacional") != "operacional":
        raise PublicReputationError("reputacao publica usa visibilidade operacional")
    public_id, identity_id = parse_delta_path(delta)
    if public_id not in audiences["publicos"]:
        raise PublicReputationError(f"publico de reputacao desconhecido: {public_id}")
    if identity_id not in identities_registry["identidades"]:
        raise PublicReputationError(f"identidade publica desconhecida: {identity_id}")
    if delta.get("publico_reputacao") != public_id or delta.get("identidade_publica") != identity_id:
        raise PublicReputationError("metadados de publico/persona precisam coincidir com o caminho do delta")
    if delta.get("atribuicao_publica") is not True or delta.get("origem_reputacao") != "fato_publico":
        raise PublicReputationError("reputacao exige fato publico explicitamente atribuido a essa persona")
    event_type = delta.get("tipo_reputacao")
    if event_type not in EVENT_TYPES:
        raise PublicReputationError("tipo_reputacao invalido")
    motive = delta.get("motivo_reputacao")
    expected_motive = "esclarecimento_publico" if event_type == CLARIFICATION else "evento_publico"
    if motive != expected_motive:
        raise PublicReputationError(f"motivo_reputacao deve ser {expected_motive}")
    fact = delta.get("fato_canonico")
    if not isinstance(fact, str) or len(fact.strip()) < 20:
        raise PublicReputationError("mudanca de reputacao exige fato_canonico publico concreto")
    _validate_source(delta.get("fonte"))
    validate_record(delta.get("valor"))
    return delta


def _get_record(state: dict[str, Any], public_id: str, identity_id: str) -> dict[str, Any]:
    value = ((state.get("registros") or {}).get(public_id) or {}).get(identity_id)
    return validate_record(value) if value is not None else default_record()


def _set_record(state: dict[str, Any], public_id: str, identity_id: str, record: dict[str, Any]) -> None:
    state.setdefault("registros", {}).setdefault(public_id, {})[identity_id] = copy.deepcopy(record)


def validate_transition(
    before: Any,
    delta: dict[str, Any],
    audiences: dict[str, Any],
    identities_registry: dict[str, Any],
) -> dict[str, Any]:
    old_state = validate_state(before, audiences, identities_registry)
    validate_reputation_delta(delta, audiences, identities_registry)
    public_id, identity_id = parse_delta_path(delta)
    old = _get_record(old_state, public_id, identity_id)
    new = validate_record(delta["valor"])
    event_type = str(delta["tipo_reputacao"])
    source = str(delta["fonte"]).strip()
    fact = str(delta["fato_canonico"]).strip()
    expected_id = event_id(public_id, identity_id, event_type, source, fact)

    old_marks = set(old["marcos"])
    old_evidence = copy.deepcopy(old["evidencias"])
    if event_type == CLARIFICATION:
        if NEGATIVE_MARK not in old_marks:
            raise PublicReputationError("esclarecimento exige consequencia negativa publica ainda ativa")
        expected_marks = _ordered_marks(old_marks - {NEGATIVE_MARK})
        expected_evidence = copy.deepcopy(old_evidence)
        expected_evidence[CLARIFICATION] = {"id": expected_id, "fonte": source}
    else:
        if event_type in old_marks:
            raise PublicReputationError("o mesmo tipo de marco ja esta ativo; reputacao nao e farmavel")
        expected_marks = _ordered_marks(old_marks | {event_type})
        expected_evidence = copy.deepcopy(old_evidence)
        expected_evidence[event_type] = {"id": expected_id, "fonte": source}

    if new["marcos"] != expected_marks:
        raise PublicReputationError("um fato publico pode alterar exatamente um marco de reputacao")
    if new["evidencias"] != expected_evidence:
        raise PublicReputationError("um fato publico nao pode reescrever evidencias de outros marcos")
    if new["estado"] != derive_label(expected_marks):
        raise PublicReputationError("estado derivado de reputacao nao corresponde aos marcos")

    result = copy.deepcopy(old_state)
    _set_record(result, public_id, identity_id, new)
    return validate_state(result, audiences, identities_registry)


def validate_batch(repo: Path, records: Iterable[dict[str, Any]]) -> int:
    deltas = [
        delta
        for record in records
        for delta in (record.get("deltas") or [])
        if touches_reputation(delta)
    ]
    if not deltas:
        return 0
    audiences = load_audiences(repo)
    identities_registry = load_identities(repo)
    state_doc = _load(repo / STATE_FILE)
    if not isinstance(state_doc, dict):
        raise PublicReputationError("estado atual invalido")
    working = validate_state(state_doc.get(STATE_ROOT), audiences, identities_registry)
    for delta in deltas:
        if not is_reputation_delta(delta):
            raise PublicReputationError("mutacao direta do dominio de reputacao e proibida")
        working = validate_transition(working, delta, audiences, identities_registry)
    return len(deltas)


def _effective_state(
    repo: Path,
    audiences: dict[str, Any],
    identities_registry: dict[str, Any],
) -> tuple[dict[str, Any], int]:
    state_doc = _load(repo / STATE_FILE)
    if not isinstance(state_doc, dict):
        raise PublicReputationError("estado atual invalido")
    state = validate_state(state_doc.get(STATE_ROOT), audiences, identities_registry)
    session = ((state_doc.get("campanha") or {}).get("sessao_atual"))
    try:
        import transacoes  # lazy: transacoes importa este modulo para validar deltas

        records = transacoes.load_pending(repo)
        if isinstance(session, int):
            records = transacoes.pending_for_session(records, session)
    except (OSError, ValueError) as exc:
        raise PublicReputationError(str(exc)) from exc
    applied = 0
    for record in records:
        for delta in record.get("deltas") or []:
            if touches_reputation(delta):
                if not is_reputation_delta(delta):
                    raise PublicReputationError("buffer contem mutacao invalida do dominio de reputacao")
                state = validate_transition(state, delta, audiences, identities_registry)
                applied += 1
    return state, applied


def _city_reading(labels: list[str]) -> str:
    nondefault = [label for label in labels if label != "estrangeiro_desconhecido"]
    if not nondefault:
        return "sem_posicao_publica"
    favorable = sum(label in FAVORABLE_LABELS for label in labels)
    dangerous = any(label == "pessoa_perigosa" for label in labels)
    controversial = any(label == "figura_controversa" for label in labels)
    if controversial or (dangerous and favorable):
        return "cidade_dividida"
    if dangerous:
        return "reputacao_adversa"
    if favorable >= 4:
        return "apoio_amplo"
    if favorable >= 2:
        return "apoio_crescente"
    return "reputacao_fragmentada"


def project(
    state: Any,
    identity_id: str,
    audiences: dict[str, Any],
    identities_registry: dict[str, Any],
    *,
    only_public: str | None = None,
) -> dict[str, Any]:
    current = validate_state(state, audiences, identities_registry)
    if identity_id not in identities_registry["identidades"]:
        raise PublicReputationError(f"identidade publica desconhecida: {identity_id}")
    public_ids = [only_public] if only_public else list(audiences["publicos"])
    if any(public_id not in audiences["publicos"] for public_id in public_ids):
        raise PublicReputationError("filtro de publico invalido")
    result: dict[str, Any] = {}
    labels: list[str] = []
    for public_id in public_ids:
        record = _get_record(current, public_id, identity_id)
        labels.append(record["estado"])
        result[public_id] = {
            "nome": audiences["publicos"][public_id]["nome"],
            "estado": record["estado"],
            "marcos": list(record["marcos"]),
        }
    projection = {
        "schema_reputacao_publica_ren": SCHEMA,
        "cidade": "ravens_bluff",
        "identidade_publica": identity_id,
        "publicos": result,
        "regras": {
            "reputacao_nao_e_fama": True,
            "opiniao_individual_nao_e_reputacao_publica": True,
            "personas_nao_se_fundem_automaticamente": True,
        },
    }
    if not only_public:
        projection["leitura_da_cidade"] = _city_reading(labels)
    return projection


def show(repo: Path, identity: str, public: str | None = None) -> dict[str, Any]:
    audiences = load_audiences(repo)
    identities_registry = load_identities(repo)
    identity_id = resolve_identity(identities_registry, identity)
    public_id = resolve_public(audiences, public) if public else None
    state, applied = _effective_state(repo, audiences, identities_registry)
    result = project(state, identity_id, audiences, identities_registry, only_public=public_id)
    result["deltas_pendentes_aplicados"] = applied
    return result


def propose_event(
    repo: Path,
    *,
    identity: str,
    publics: list[str],
    event_type: str,
    fact: str,
    source: str,
) -> dict[str, Any]:
    audiences = load_audiences(repo)
    identities_registry = load_identities(repo)
    identity_id = resolve_identity(identities_registry, identity)
    if event_type not in EVENT_TYPES:
        raise PublicReputationError("tipo de evento de reputacao invalido")
    if not isinstance(fact, str) or len(fact.strip()) < 20:
        raise PublicReputationError("evento de reputacao exige fato publico concreto")
    source = _validate_source(source)
    if not publics or len(publics) > MAX_PUBLICS_PER_EVENT:
        raise PublicReputationError(
            f"evento deve atingir entre 1 e {MAX_PUBLICS_PER_EVENT} publicos explicitamente observadores"
        )
    public_ids = [resolve_public(audiences, item) for item in publics]
    if len(public_ids) != len(set(public_ids)):
        raise PublicReputationError("o mesmo publico nao pode ser repetido no evento")

    state, pending_applied = _effective_state(repo, audiences, identities_registry)
    before_projection = project(state, identity_id, audiences, identities_registry)
    deltas: list[dict[str, Any]] = []
    ignored: list[dict[str, str]] = []
    for public_id in public_ids:
        old = _get_record(state, public_id, identity_id)
        old_marks = set(old["marcos"])
        if event_type == CLARIFICATION and NEGATIVE_MARK not in old_marks:
            ignored.append({"publico": public_id, "motivo": "nenhuma consequencia negativa ativa para esclarecer"})
            continue
        if event_type != CLARIFICATION and event_type in old_marks:
            ignored.append({"publico": public_id, "motivo": "marco desse tipo ja ativo; repeticao nao aumenta reputacao"})
            continue

        new = copy.deepcopy(old)
        eid = event_id(public_id, identity_id, event_type, source, fact)
        if event_type == CLARIFICATION:
            new["marcos"] = _ordered_marks(old_marks - {NEGATIVE_MARK})
            new["evidencias"][CLARIFICATION] = {"id": eid, "fonte": source}
            motive = "esclarecimento_publico"
        else:
            new["marcos"] = _ordered_marks(old_marks | {event_type})
            new["evidencias"][event_type] = {"id": eid, "fonte": source}
            motive = "evento_publico"
        new["estado"] = derive_label(new["marcos"])
        delta = {
            "alvo": "estado",
            "op": "set",
            "caminho": f"{STATE_ROOT}.registros.{public_id}.{identity_id}",
            "valor": new,
            "visibilidade": "operacional",
            "motivo_reputacao": motive,
            "tipo_reputacao": event_type,
            "publico_reputacao": public_id,
            "identidade_publica": identity_id,
            "atribuicao_publica": True,
            "origem_reputacao": "fato_publico",
            "fato_canonico": fact.strip(),
            "fonte": source,
        }
        state = validate_transition(state, delta, audiences, identities_registry)
        deltas.append(delta)

    after_projection = project(state, identity_id, audiences, identities_registry)
    if not deltas:
        return {
            "schema_reputacao_publica_ren": SCHEMA,
            "resultado": "sem_delta",
            "identidade_publica": identity_id,
            "ignorados": ignored,
            "deltas_pendentes_preexistentes": pending_applied,
            "projecao": after_projection,
        }
    return {
        "schema_reputacao_publica_ren": SCHEMA,
        "resultado": "registrar_delta" if len(deltas) == 1 else "registrar_deltas",
        "identidade_publica": identity_id,
        "deltas": deltas,
        "ignorados": ignored,
        "deltas_pendentes_preexistentes": pending_applied,
        "projecao_antes": before_projection,
        "projecao_depois": after_projection,
    }


def check(repo: Path) -> list[str]:
    errors: list[str] = []
    try:
        audiences = load_audiences(repo)
        identities_registry = load_identities(repo)
        state_doc = _load(repo / STATE_FILE)
        if not isinstance(state_doc, dict):
            raise PublicReputationError("estado atual invalido")
        validate_state(state_doc.get(STATE_ROOT), audiences, identities_registry)
        if len(audiences["publicos"]) != 6:
            raise PublicReputationError("Task 29 v1 deve manter exatamente seis publicos sociais compactos")
    except (PublicReputationError, identidades.IdentitySuspicionError) as exc:
        errors.append(str(exc))
    return errors


def _dump(value: Any, as_json: bool) -> str:
    if as_json:
        return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=110)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    show_cmd = sub.add_parser("mostrar", help="consulta dirigida da reputacao de uma persona")
    show_cmd.add_argument("identidade")
    show_cmd.add_argument("--publico")

    event = sub.add_parser("evento", help="prepara delta read-only para um fato publico")
    event.add_argument("identidade")
    event.add_argument("--publico", action="append", required=True)
    event.add_argument("--tipo", choices=sorted(EVENT_TYPES), required=True)
    event.add_argument("--fato", required=True)
    event.add_argument("--fonte", required=True)

    sub.add_parser("check", help="valida registro, estado e orcamento da Task 29")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo = args.repo.resolve()
    try:
        if args.command == "mostrar":
            result = show(repo, args.identidade, args.publico)
        elif args.command == "evento":
            result = propose_event(
                repo,
                identity=args.identidade,
                publics=args.publico,
                event_type=args.tipo,
                fact=args.fato,
                source=args.fonte,
            )
        elif args.command == "check":
            errors = check(repo)
            result = {"ok": not errors, "erros": errors}
        else:
            raise PublicReputationError(f"comando desconhecido: {args.command}")
    except (OSError, PublicReputationError, identidades.IdentitySuspicionError) as exc:
        print(f"FALHA DE REPUTACAO PUBLICA — {exc}")
        return 1
    print(_dump(result, args.json), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
