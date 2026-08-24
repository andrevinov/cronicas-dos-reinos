#!/usr/bin/env python3
"""Catálogo fragmentado e projeção dos eventos canônicos datados da Parte 1.

Task 36 mantém a agenda determinística existente, mas deixa o futuro frio: o
índice reservado contém somente identidade/agendamento; detalhes narrativos ficam
em um fragmento por evento e só são abertos quando aquele evento está devido.
Catálogos schema 1 continuam aceitos para fixtures/compatibilidade.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

import mundo

CATALOG = Path("narrador/arcos/parte_1/eventos-canonicos.yaml")
EVENT_DIR = Path("narrador/arcos/parte_1/eventos")
SCHEMA = 2
LEGACY_SCHEMA = 1
EVENT_SCHEMA = 2
SECRET_CANON_VERSION = 1
ARC = "parte_1_uma_ponte_para_kozakura"
SCHEDULE_ORIGIN_PREFIX = "agenda:agendamentos."
INDEX_MAX_BYTES = 12 * 1024
FRAGMENT_MAX_BYTES = 6 * 1024
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_FORBIDDEN_FUTURE_KEYS = {
    "resultado_obrigatorio",
    "acao_de_ren_obrigatoria",
    "recompensa_automatica",
    "neutralizacao_automatica",
    "conhecimento_automatico_de_ren",
}


class CanonicalEventError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise CanonicalEventError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CanonicalEventError(f"{label} deve ser mapa")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CanonicalEventError(f"{label} deve ser texto não vazio")
    return value.strip()


def _strings(value: Any, label: str, *, required: bool = False) -> list[str]:
    if value is None and not required:
        return []
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise CanonicalEventError(f"{label} deve ser lista de textos não vazios")
    if required and not value:
        raise CanonicalEventError(f"{label} não pode ser vazio")
    return [item.strip() for item in value]


def _schema(data: dict[str, Any]) -> int:
    value = data.get("schema_eventos_canonicos_parte_1")
    if value not in {LEGACY_SCHEMA, SCHEMA}:
        raise CanonicalEventError(
            f"catálogo canônico deve usar schema {LEGACY_SCHEMA} ou {SCHEMA}"
        )
    return int(value)


def _activation(raw: dict[str, Any], label: str) -> mundo.WorldInstant:
    activation = _map(raw.get("ativacao"), f"{label}.ativacao")
    return mundo.parse_instant(
        _text(activation.get("data"), f"{label}.ativacao.data"),
        _text(activation.get("hora"), f"{label}.ativacao.hora"),
    )


def _fragment_path(value: Any, label: str) -> Path:
    text = _text(value, label)
    path = Path(text)
    if (
        path.is_absolute()
        or ".." in path.parts
        or path.suffix != ".yaml"
        or not str(path).startswith(EVENT_DIR.as_posix() + "/")
    ):
        raise CanonicalEventError(f"{label} deve apontar para fragmento reservado em {EVENT_DIR}")
    return path


def load_catalog(repo: Path) -> dict[str, Any]:
    path = repo / CATALOG
    try:
        size = path.stat().st_size
    except FileNotFoundError as exc:
        raise CanonicalEventError(str(exc)) from exc
    if size > INDEX_MAX_BYTES:
        raise CanonicalEventError(
            f"índice canônico excede {INDEX_MAX_BYTES} bytes: {size}"
        )

    data = _map(_load(path), CATALOG.as_posix())
    schema = _schema(data)
    if data.get("natureza") != "reservado":
        raise CanonicalEventError("catálogo canônico deve ser reservado")
    if data.get("arco") != ARC:
        raise CanonicalEventError("catálogo canônico pertence a arco diferente")
    events = _map(data.get("eventos"), "eventos")
    if not events:
        raise CanonicalEventError("catálogo canônico precisa de eventos")

    fragments: set[str] = set()
    for event_id, raw in events.items():
        _text(event_id, "id de evento")
        event = _map(raw, f"eventos.{event_id}")
        _text(event.get("agendamento_id"), f"eventos.{event_id}.agendamento_id")
        _activation(event, f"eventos.{event_id}")
        if schema == LEGACY_SCHEMA:
            _text(event.get("titulo"), f"eventos.{event_id}.titulo")
            _strings(
                event.get("nucleo_obrigatorio"),
                f"eventos.{event_id}.nucleo_obrigatorio",
                required=True,
            )
            _strings(
                event.get("guardrails"),
                f"eventos.{event_id}.guardrails",
                required=True,
            )
            _strings(event.get("forma_preferencial"), f"eventos.{event_id}.forma_preferencial")
            continue
        fragment = _fragment_path(event.get("fragmento"), f"eventos.{event_id}.fragmento")
        key = fragment.as_posix()
        if key in fragments:
            raise CanonicalEventError(f"fragmento reutilizado por mais de um evento: {key}")
        fragments.add(key)

    if schema == SCHEMA:
        _validate_v2_header(data)
    return data


def _validate_v2_header(catalog: dict[str, Any]) -> dict[str, Any]:
    secret = _map(catalog.get("secret_canon_v2"), "secret_canon_v2")
    if secret.get("versao") != SECRET_CANON_VERSION:
        raise CanonicalEventError(
            f"secret_canon_v2 deve usar versão {SECRET_CANON_VERSION}"
        )
    frontier = _map(secret.get("fronteira_autoral"), "secret_canon_v2.fronteira_autoral")
    mundo.parse_instant(
        _text(frontier.get("data"), "secret_canon_v2.fronteira_autoral.data"),
        _text(frontier.get("hora"), "secret_canon_v2.fronteira_autoral.hora"),
    )
    frozen = _map(secret.get("passado_congelado"), "secret_canon_v2.passado_congelado")
    if not frozen:
        raise CanonicalEventError("secret_canon_v2 precisa congelar o passado já materializado")
    for event_id, digest in frozen.items():
        if event_id not in catalog["eventos"]:
            raise CanonicalEventError(f"evento congelado ausente: {event_id}")
        if not isinstance(digest, str) or not _DIGEST_RE.fullmatch(digest):
            raise CanonicalEventError(f"digest inválido para evento congelado {event_id}")
    controlled = set(
        _strings(
            secret.get("categorias_controladas"),
            "secret_canon_v2.categorias_controladas",
            required=True,
        )
    )
    required = set(
        _strings(
            secret.get("cobertura_obrigatoria"),
            "secret_canon_v2.cobertura_obrigatoria",
            required=True,
        )
    )
    if not required <= controlled:
        raise CanonicalEventError("cobertura obrigatória usa categoria não controlada")
    return {
        "frontier": mundo.parse_instant(frontier["data"], frontier["hora"]),
        "frozen": frozen,
        "controlled": controlled,
        "required": required,
    }


def _load_v2_fragment(repo: Path, event_id: str, index_event: dict[str, Any]) -> dict[str, Any]:
    rel = _fragment_path(index_event.get("fragmento"), f"eventos.{event_id}.fragmento")
    path = repo / rel
    try:
        size = path.stat().st_size
    except FileNotFoundError as exc:
        raise CanonicalEventError(str(exc)) from exc
    if size > FRAGMENT_MAX_BYTES:
        raise CanonicalEventError(
            f"fragmento {event_id} excede {FRAGMENT_MAX_BYTES} bytes: {size}"
        )
    raw = _map(_load(path), rel.as_posix())
    if raw.get("schema_evento_canonico_parte_1") != EVENT_SCHEMA:
        raise CanonicalEventError(f"fragmento {event_id} deve usar schema {EVENT_SCHEMA}")
    if raw.get("natureza") != "reservado" or raw.get("arco") != ARC:
        raise CanonicalEventError(f"fragmento {event_id} possui autoridade divergente")
    if raw.get("id") != event_id:
        raise CanonicalEventError(f"fragmento {event_id} possui id divergente")
    for forbidden in ("agendamento_id", "ativacao", "fragmento"):
        if forbidden in raw:
            raise CanonicalEventError(
                f"fragmento {event_id} duplica campo autoritativo do índice: {forbidden}"
            )
    _text(raw.get("titulo"), f"{event_id}.titulo")
    _text(raw.get("janela"), f"{event_id}.janela")
    _strings(raw.get("nucleo_obrigatorio"), f"{event_id}.nucleo_obrigatorio", required=True)
    _strings(raw.get("guardrails"), f"{event_id}.guardrails", required=True)
    _strings(raw.get("forma_preferencial"), f"{event_id}.forma_preferencial")
    return raw


def load_event(
    repo: Path,
    event_id: str,
    *,
    catalog: dict[str, Any] | None = None,
) -> dict[str, Any]:
    catalog = catalog or load_catalog(repo)
    events = catalog["eventos"]
    if event_id not in events:
        raise CanonicalEventError(f"evento canônico inexistente: {event_id}")
    index_event = _map(events[event_id], f"eventos.{event_id}")
    if _schema(catalog) == LEGACY_SCHEMA:
        return {"id": event_id, **index_event}
    fragment = _load_v2_fragment(repo, event_id, index_event)
    return {
        "id": event_id,
        **{key: value for key, value in index_event.items() if key != "fragmento"},
        **{
            key: value
            for key, value in fragment.items()
            if key not in {"schema_evento_canonico_parte_1", "natureza", "arco", "id"}
        },
    }


def _semantic_event(event: dict[str, Any]) -> dict[str, Any]:
    allowed = (
        "titulo",
        "agendamento_id",
        "ativacao",
        "janela",
        "categorias",
        "nucleo_obrigatorio",
        "forma_preferencial",
        "guardrails",
        "adaptacao",
    )
    return {key: event[key] for key in allowed if key in event}


def event_digest(event: dict[str, Any]) -> str:
    payload = json.dumps(
        _semantic_event(event),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_v2_events(repo: Path, catalog: dict[str, Any]) -> None:
    contract = _validate_v2_header(catalog)
    frontier: mundo.WorldInstant = contract["frontier"]
    frozen: dict[str, str] = contract["frozen"]
    controlled: set[str] = contract["controlled"]
    required: set[str] = contract["required"]
    coverage: set[str] = set()
    future_instants: list[tuple[int, str]] = []

    for event_id in catalog["eventos"]:
        event = load_event(repo, event_id, catalog=catalog)
        activation = mundo.parse_instant(event["ativacao"]["data"], event["ativacao"]["hora"])
        if event_id in frozen:
            if activation.minute > frontier.minute:
                raise CanonicalEventError(f"evento congelado está após fronteira autoral: {event_id}")
            digest = event_digest(event)
            if digest != frozen[event_id]:
                raise CanonicalEventError(f"passado materializado foi alterado: {event_id}")
            if "categorias" in event or "adaptacao" in event:
                raise CanonicalEventError(f"evento congelado recebeu metadado futuro: {event_id}")
            continue

        if activation.minute <= frontier.minute:
            raise CanonicalEventError(
                f"evento futuro não pode ficar no passado da fronteira autoral: {event_id}"
            )
        categories = set(_strings(event.get("categorias"), f"{event_id}.categorias", required=True))
        if not categories <= controlled:
            unknown = sorted(categories - controlled)
            raise CanonicalEventError(
                f"evento {event_id} usa categorias não controladas: {', '.join(unknown)}"
            )
        _strings(event.get("adaptacao"), f"{event_id}.adaptacao", required=True)
        forbidden = _FORBIDDEN_FUTURE_KEYS & set(event)
        if forbidden:
            raise CanonicalEventError(
                f"evento {event_id} usa resultado automático proibido: {', '.join(sorted(forbidden))}"
            )
        coverage.update(categories)
        future_instants.append((activation.minute, event_id))

    missing = required - coverage
    if missing:
        raise CanonicalEventError(
            "cobertura dramática futura incompleta: " + ", ".join(sorted(missing))
        )

    future_instants.sort()
    for (left, left_id), (right, right_id) in zip(future_instants, future_instants[1:]):
        if right == left:
            raise CanonicalEventError(
                f"dois eventos futuros compartilham o mesmo instante: {left_id}, {right_id}"
            )
        if right - left < 24 * 60:
            raise CanonicalEventError(
                f"eventos futuros densos demais (<24h): {left_id}, {right_id}"
            )


def _schedule_id_from_pending(pending: dict[str, Any]) -> str | None:
    origin = pending.get("origem")
    if not isinstance(origin, str) or not origin.startswith(SCHEDULE_ORIGIN_PREFIX):
        return None
    schedule_id = origin[len(SCHEDULE_ORIGIN_PREFIX):].strip()
    return schedule_id or None


def event_for_pending(repo: Path, pending: dict[str, Any]) -> dict[str, Any] | None:
    schedule_id = _schedule_id_from_pending(pending)
    if schedule_id is None:
        return None
    catalog = load_catalog(repo)
    for event_id, event in catalog["eventos"].items():
        if event.get("agendamento_id") == schedule_id:
            return load_event(repo, event_id, catalog=catalog)
    return None


def pending_projection(repo: Path, pendings: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = [
        pending
        for pending in pendings
        if isinstance(pending, dict) and _schedule_id_from_pending(pending) is not None
    ]
    if not candidates:
        return {"eventos": [], "fontes_lidas": []}

    catalog = load_catalog(repo)
    by_schedule = {
        str(event.get("agendamento_id")): event_id
        for event_id, event in catalog["eventos"].items()
    }
    resolved: list[tuple[dict[str, Any], dict[str, Any]]] = []
    sources = [CATALOG.as_posix()]
    for pending in candidates:
        schedule_id = _schedule_id_from_pending(pending)
        event_id = by_schedule.get(str(schedule_id))
        if event_id is None:
            continue
        event = load_event(repo, event_id, catalog=catalog)
        resolved.append((pending, event))
        if _schema(catalog) == SCHEMA:
            sources.append(catalog["eventos"][event_id]["fragmento"])

    if not resolved:
        return {"eventos": [], "fontes_lidas": []}

    now, _ = mundo.load_canonical_time(repo)
    projected: list[dict[str, Any]] = []
    for pending, event in resolved:
        activation = mundo.parse_instant(event["ativacao"]["data"], event["ativacao"]["hora"])
        overdue_minutes = max(0, now.minute - activation.minute)
        projected.append(
            {
                "pendencia": pending.get("id"),
                "evento": event["id"],
                "titulo": event.get("titulo"),
                "data": event["ativacao"]["data"],
                "janela": event.get("janela", "ao_longo_do_dia"),
                "atraso_dias": overdue_minutes // (24 * 60),
                "categorias": list(event.get("categorias") or []),
                "nucleo_obrigatorio": list(event.get("nucleo_obrigatorio") or []),
                "guardrails": list(event.get("guardrails") or []),
                "adaptacao": list(event.get("adaptacao") or []),
            }
        )
    return {
        "eventos": projected,
        "regra": (
            "materializar situação/núcleo; preservar agência, identidade, progressão e "
            "resultados; usar adaptação se detalhe futuro ficou impossível"
        ),
        "fontes_lidas": list(dict.fromkeys([*sources, mundo.TIME_PATH.as_posix()])),
    }


def validate(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    sources = [CATALOG.as_posix(), mundo.AGENDA_PATH.as_posix()]
    count = 0
    fragments = 0
    try:
        catalog = load_catalog(repo)
        count = len(catalog["eventos"])
        if _schema(catalog) == SCHEMA:
            _validate_v2_events(repo, catalog)
            fragments = count

        agenda = mundo.load_agenda(repo)
        schedules = {
            str(item.get("id")): item
            for item in agenda.get("agendamentos") or []
            if isinstance(item, dict) and item.get("id")
        }
        event_ids = set(catalog["eventos"])
        used_schedule_ids: set[str] = set()
        for event_id, event in catalog["eventos"].items():
            schedule_id = str(event["agendamento_id"])
            if schedule_id in used_schedule_ids:
                raise CanonicalEventError(f"agendamento reutilizado por mais de um evento: {schedule_id}")
            used_schedule_ids.add(schedule_id)
            schedule = schedules.get(schedule_id)
            if schedule is None:
                raise CanonicalEventError(
                    f"agendamento ausente para evento canônico {event_id}: {schedule_id}"
                )
            if schedule.get("evento_canonico") != event_id:
                raise CanonicalEventError(f"agendamento {schedule_id} não aponta para {event_id}")
            if schedule.get("em") != event.get("ativacao"):
                raise CanonicalEventError(f"data do agendamento {schedule_id} diverge do catálogo")
            if event_id == "chegada_golden_lily":
                if schedule.get("tipo") != "movimento" or schedule.get("agente") != "pan_chu":
                    raise CanonicalEventError("Golden Lily deve reutilizar o movimento físico de Pan Chu")
            elif schedule.get("tipo") != "expiracao":
                raise CanonicalEventError(
                    f"evento canônico {event_id} deve usar agendamento genérico expiracao"
                )

        dangling = [
            str(item.get("evento_canonico"))
            for item in agenda.get("agendamentos") or []
            if isinstance(item, dict)
            and item.get("evento_canonico")
            and item.get("evento_canonico") not in event_ids
        ]
        if dangling:
            raise CanonicalEventError(
                "agenda referencia eventos canônicos inexistentes: " + ", ".join(dangling)
            )
    except (CanonicalEventError, mundo.WorldEngineError) as exc:
        errors.append(str(exc))

    return {
        "ok": not errors,
        "schema": SCHEMA if not errors else None,
        "eventos": count,
        "fragmentos": fragments,
        "erros": errors,
        "fontes_lidas": sources,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("cmd", choices=["validar"])
    args = parser.parse_args(argv)
    result = validate(args.repo.resolve())
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
