#!/usr/bin/env python3
"""Catálogo e projeção compacta dos eventos canônicos datados da Parte 1.

A data torna o núcleo do evento devido; não determina a decisão de Ren, o
resultado do encontro nem uma coreografia única. A pendência do Mundo Vivo só
pode ser concluída depois que o núcleo entrou canonicamente em jogo por uma
transação de ``modo: mundo``. Enquanto isso, a barreira normal impede que o
calendário simplesmente passe por cima do acontecimento.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

import mundo

CATALOG = Path("narrador/arcos/parte_1/eventos-canonicos.yaml")
SCHEMA = 1
ARC = "parte_1_uma_ponte_para_kozakura"


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
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise CanonicalEventError(f"{label} deve ser lista de textos não vazios")
    if required and not value:
        raise CanonicalEventError(f"{label} não pode ser vazio")
    return [item.strip() for item in value]


def load_catalog(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / CATALOG), CATALOG.as_posix())
    if data.get("schema_eventos_canonicos_parte_1") != SCHEMA:
        raise CanonicalEventError(f"catálogo canônico deve usar schema {SCHEMA}")
    if data.get("natureza") != "reservado":
        raise CanonicalEventError("catálogo canônico deve ser reservado")
    if data.get("arco") != ARC:
        raise CanonicalEventError("catálogo canônico pertence a arco diferente")
    events = _map(data.get("eventos"), "eventos")
    if not events:
        raise CanonicalEventError("catálogo canônico precisa de eventos")
    for event_id, raw in events.items():
        _text(event_id, "id de evento")
        event = _map(raw, f"eventos.{event_id}")
        _text(event.get("titulo"), f"eventos.{event_id}.titulo")
        _text(event.get("agendamento_id"), f"eventos.{event_id}.agendamento_id")
        activation = _map(event.get("ativacao"), f"eventos.{event_id}.ativacao")
        mundo.parse_instant(
            _text(activation.get("data"), f"eventos.{event_id}.ativacao.data"),
            _text(activation.get("hora"), f"eventos.{event_id}.ativacao.hora"),
        )
        _strings(event.get("nucleo_obrigatorio"), f"eventos.{event_id}.nucleo_obrigatorio", required=True)
        _strings(event.get("guardrails"), f"eventos.{event_id}.guardrails", required=True)
        _strings(event.get("forma_preferencial"), f"eventos.{event_id}.forma_preferencial")
    return data


def event_for_pending(repo: Path, pending: dict[str, Any]) -> dict[str, Any] | None:
    event_id = pending.get("evento_canonico")
    if not isinstance(event_id, str) or not event_id.strip():
        return None
    catalog = load_catalog(repo)
    event = catalog["eventos"].get(event_id)
    if not isinstance(event, dict):
        raise CanonicalEventError(f"pendência referencia evento canônico inexistente: {event_id}")
    return {"id": event_id, **event}


def pending_projection(repo: Path, pendings: list[dict[str, Any]]) -> dict[str, Any]:
    relevant = [item for item in pendings if isinstance(item, dict) and item.get("evento_canonico")]
    if not relevant:
        return {"eventos": [], "fontes_lidas": []}
    catalog = load_catalog(repo)
    now, _ = mundo.load_canonical_time(repo)
    projected: list[dict[str, Any]] = []
    for pending in relevant:
        event_id = str(pending["evento_canonico"])
        event = _map(catalog["eventos"].get(event_id), f"evento {event_id}")
        activation = mundo.parse_instant(event["ativacao"]["data"], event["ativacao"]["hora"])
        overdue_minutes = max(0, now.minute - activation.minute)
        projected.append(
            {
                "pendencia": pending.get("id"),
                "evento": event_id,
                "titulo": event.get("titulo"),
                "data": event["ativacao"]["data"],
                "janela": event.get("janela", "ao_longo_do_dia"),
                "atraso_dias": overdue_minutes // (24 * 60),
                "nucleo_obrigatorio": list(event.get("nucleo_obrigatorio") or []),
                "guardrails": list(event.get("guardrails") or []),
            }
        )
    return {
        "eventos": projected,
        "regra": "materializar o núcleo; preservar agência de Ren; forma e resultado permanecem flexíveis",
        "fontes_lidas": [CATALOG.as_posix(), mundo.TIME_PATH.as_posix()],
    }


def validate(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    sources = [CATALOG.as_posix(), mundo.AGENDA_PATH.as_posix()]
    try:
        catalog = load_catalog(repo)
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
                raise CanonicalEventError(f"agendamento ausente para evento canônico {event_id}: {schedule_id}")
            if schedule.get("evento_canonico") != event_id:
                raise CanonicalEventError(f"agendamento {schedule_id} não aponta para {event_id}")
            if schedule.get("em") != event.get("ativacao"):
                raise CanonicalEventError(f"data do agendamento {schedule_id} diverge do catálogo")
            if schedule.get("tipo") not in {"evento_canonico", "movimento"}:
                raise CanonicalEventError(f"tipo inválido para evento canônico {event_id}")
            if schedule.get("tipo") == "movimento" and event_id != "chegada_golden_lily":
                raise CanonicalEventError("somente a chegada física do Golden Lily reutiliza tipo movimento")
        dangling = [
            str(item.get("evento_canonico"))
            for item in agenda.get("agendamentos") or []
            if isinstance(item, dict)
            and item.get("evento_canonico")
            and item.get("evento_canonico") not in event_ids
        ]
        if dangling:
            raise CanonicalEventError("agenda referencia eventos canônicos inexistentes: " + ", ".join(dangling))
    except (CanonicalEventError, mundo.WorldEngineError) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "eventos": 0 if errors else len(load_catalog(repo)["eventos"]),
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
