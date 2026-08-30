#!/usr/bin/env python3
"""Task 42 — Canon Bridge & Rewriter.

Sidequests emergentes aceitas podem reservar uma intenção canônica futura sem
editar o cânone-base. O ledger desta camada é um overlay causal:

- ponte/convergente preservam o agendamento-base e fornecem uma âncora causal;
- adiamento desloca somente o disparo efetivo dentro da elasticidade Task39;
- transformação preserva a intenção e só elimina a realização padrão depois de
  evidência canônica suficiente;
- uma intenção satisfeita suprime o disparo padrão sem apagar Task36/Task39.

Nenhuma reserva move Ren, decide sua ação ou transforma planejamento em fato.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

import eventos_canonicos
import intencoes_canonicas
import mundo
import oportunidades

STATE = Path("narrador/arcos/parte_1/rewrites-causais.yaml")
SCHEMA = 1
MAX_STATE_BYTES = 12 * 1024
MAX_HISTORY = 48
MAX_EVIDENCE_CHARS = 320
MAX_CONVERGENCE_GAP_HOURS = 48

RELATION_TO_MODE = {
    "candidata_ponte": "ponte",
    "candidata_convergente": "convergente",
    "candidata_adiamento": "adiamento",
    "candidata_transformacao": "transformacao",
}
RESERVATION_STATES = {"ativa", "aguarda_evidencia"}
TERMINAL_RELEASE = {"recusada", "falhada", "expirada"}
FORBIDDEN_EVIDENCE_PREFIXES = (
    "narrador/sidequests-emergentes/",
    "narrador/arcos/parte_1/intencoes/",
    "narrador/arcos/parte_1/eventos/",
)


class CanonBridgeError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise CanonBridgeError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CanonBridgeError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise CanonBridgeError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str, *, minimum: int = 1, maximum: int = 520) -> str:
    if not isinstance(value, str):
        raise CanonBridgeError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if len(result) < minimum:
        raise CanonBridgeError(f"{label} deve ter ao menos {minimum} caracteres")
    if len(result) > maximum:
        raise CanonBridgeError(f"{label} excede {maximum} caracteres")
    return result


def _safe_repo_path(repo: Path, raw: Any, label: str) -> tuple[Path, str]:
    text = _text(raw, label, maximum=240)
    rel = Path(text)
    if rel.is_absolute() or ".." in rel.parts:
        raise CanonBridgeError(f"{label} deve ficar dentro do repo")
    posix = rel.as_posix()
    if any(posix.startswith(prefix) for prefix in FORBIDDEN_EVIDENCE_PREFIXES):
        raise CanonBridgeError(f"{label} não pode usar planejamento reservado como prova")
    path = repo / rel
    if not path.is_file():
        raise CanonBridgeError(f"fonte de evidência inexistente: {posix}")
    return path, posix


def _yaml_bytes(value: Any) -> bytes:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8")


def _atomic(path: Path, data: dict[str, Any]) -> None:
    rendered = _yaml_bytes(data)
    if len(rendered) > MAX_STATE_BYTES:
        raise CanonBridgeError(
            f"ledger Task42 excede {MAX_STATE_BYTES} bytes: {len(rendered)}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "wb", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
        tmp = Path(handle.name)
    os.replace(tmp, path)


def configured(repo: Path) -> bool:
    return (repo / STATE).is_file()


def load_state(repo: Path) -> dict[str, Any]:
    path = repo / STATE
    try:
        size = path.stat().st_size
    except FileNotFoundError as exc:
        raise CanonBridgeError(str(exc)) from exc
    if size > MAX_STATE_BYTES:
        raise CanonBridgeError(f"ledger Task42 excede {MAX_STATE_BYTES} bytes: {size}")
    data = _map(_load(path), STATE.as_posix())
    if set(data) != {
        "schema_canon_bridge", "natureza", "reservas", "resolucoes", "historico_recente"
    }:
        raise CanonBridgeError("ledger Task42 possui estrutura inesperada")
    if data["schema_canon_bridge"] != SCHEMA or data["natureza"] != "controle_reservado":
        raise CanonBridgeError("ledger Task42 inválido")
    _map(data["reservas"], "reservas")
    _map(data["resolucoes"], "resolucoes")
    history = _list(data["historico_recente"], "historico_recente")
    if len(history) > MAX_HISTORY:
        raise CanonBridgeError("historico_recente Task42 excede orçamento")
    return data


def _history(state: dict[str, Any], item: dict[str, Any]) -> None:
    state["historico_recente"].append(item)
    state["historico_recente"] = state["historico_recente"][-MAX_HISTORY:]


def _quest_document(repo: Path, mission: dict[str, Any]) -> tuple[dict[str, Any], str]:
    if mission.get("origem") != "sidequest_emergente":
        raise CanonBridgeError("Task42 aceita somente sidequest emergente Task41")
    raw = mission.get("arquivo")
    if not isinstance(raw, str):
        raise CanonBridgeError("missão emergente sem arquivo reservado")
    rel = Path(raw)
    if (
        rel.is_absolute() or ".." in rel.parts
        or not rel.as_posix().startswith("narrador/sidequests-emergentes/quests/")
    ):
        raise CanonBridgeError("arquivo de sidequest emergente inválido")
    doc = _map(_load(repo / rel), rel.as_posix())
    if (
        doc.get("schema_sidequest_emergente") != 2
        or doc.get("natureza") != "reservado"
        or doc.get("id") != mission.get("quest_id")
    ):
        raise CanonBridgeError("fragmento Task41 divergente da missão")
    return doc, rel.as_posix()


def _deadline(doc: dict[str, Any]) -> mundo.WorldInstant | None:
    raw = doc.get("prazo")
    if not isinstance(raw, dict) or raw.get("tipo") != "temporal":
        return None
    end = _map(raw.get("expira_em"), "prazo.expira_em")
    return mundo.parse_instant(
        _text(end.get("data"), "prazo.data"),
        _text(end.get("hora"), "prazo.hora"),
    )


def _final_locations(doc: dict[str, Any]) -> list[str]:
    phases = _list(doc.get("fases"), "quest.fases")
    if not phases:
        return []
    final = _map(phases[-1], "quest.fases[-1]")
    values = _list(final.get("locais"), "quest.fases[-1].locais")
    return [str(item) for item in values if isinstance(item, str) and item]


def _event_context(
    repo: Path, event_id: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[str]]:
    try:
        index = intencoes_canonicas.load_index(repo)
        catalog = eventos_canonicos.load_catalog(repo)
        intent = intencoes_canonicas.load_intent(
            repo, event_id, index=index, catalog=catalog
        )
    except (
        intencoes_canonicas.CanonicalIntentError,
        eventos_canonicos.CanonicalEventError,
        mundo.WorldEngineError,
    ) as exc:
        raise CanonBridgeError(str(exc)) from exc
    return index, catalog, intent, [
        intencoes_canonicas.INDEX.as_posix(),
        eventos_canonicos.CATALOG.as_posix(),
        intent["_fonte"],
    ]


def _base_activation(catalog: dict[str, Any], event_id: str) -> mundo.WorldInstant:
    meta = _map(catalog["eventos"].get(event_id), f"eventos.{event_id}")
    return mundo.parse_instant(meta["ativacao"]["data"], meta["ativacao"]["hora"])


def _schedule_id(catalog: dict[str, Any], event_id: str) -> str:
    return _text(
        catalog["eventos"][event_id].get("agendamento_id"), "agendamento_id"
    )


def _schedule(
    repo: Path, catalog: dict[str, Any], event_id: str
) -> dict[str, Any]:
    schedule_id = _schedule_id(catalog, event_id)
    schedule = next(
        (
            item
            for item in mundo.load_agenda(repo).get("agendamentos") or []
            if item.get("id") == schedule_id
        ),
        None,
    )
    if not isinstance(schedule, dict):
        raise CanonBridgeError(
            f"agendamento canônico inexistente para {event_id}: {schedule_id}"
        )
    return schedule


def _reservation_for_mission(
    state: dict[str, Any], mission_id: str
) -> tuple[str, dict[str, Any]] | None:
    for event_id, raw in state["reservas"].items():
        if isinstance(raw, dict) and raw.get("mission_id") == mission_id:
            return str(event_id), raw
    return None


def _validate_relation(
    repo: Path,
    mission: dict[str, Any],
    doc: dict[str, Any],
    now: mundo.WorldInstant,
) -> dict[str, Any] | None:
    relation = _map(doc.get("relacao_canone"), "relacao_canone")
    raw_mode = _text(relation.get("modo"), "relacao_canone.modo", maximum=48)
    if raw_mode == "lateral":
        return None
    mode = RELATION_TO_MODE.get(raw_mode)
    if mode is None:
        raise CanonBridgeError(
            f"relação Task41 não reconhecida pela Task42: {raw_mode}"
        )
    candidates = _list(
        relation.get("intencoes_candidatas"), "relacao_canone.intencoes_candidatas"
    )
    if len(candidates) != 1 or not isinstance(candidates[0], str):
        raise CanonBridgeError(
            "Task42 exige exatamente uma intenção/evento alvo na candidatura não lateral"
        )
    event_id = candidates[0]
    _, catalog, intent, sources = _event_context(repo, event_id)
    base = _base_activation(catalog, event_id)
    if base.minute <= now.minute:
        raise CanonBridgeError("Task42 não cria ponte retroativa para evento já devido")
    contract = intent["contrato_rewrite"]
    if not contract["integracao_sidequest"]:
        raise CanonBridgeError(
            f"{event_id}: intenção não aceita integração com sidequest"
        )
    allowed = set(contract["modos_permitidos"])
    end = _deadline(doc)
    effective = base
    if mode in {"ponte", "convergente"}:
        if end is None:
            raise CanonBridgeError(
                f"{mode} exige prazo temporal para criar âncora causal"
            )
        gap = abs(end.minute - base.minute)
        if gap > MAX_CONVERGENCE_GAP_HOURS * 60:
            raise CanonBridgeError(
                f"{mode} deve terminar a no máximo "
                f"{MAX_CONVERGENCE_GAP_HOURS}h do evento canônico"
            )
        if mode == "convergente" and "satisfazer" not in allowed:
            raise CanonBridgeError(
                f"{event_id}: convergência exige modo satisfazer na Task39"
            )
    elif mode == "adiamento":
        if "adiar" not in allowed:
            raise CanonBridgeError(
                f"{event_id}: contrato Task39 não permite adiar"
            )
        if end is None or end.minute <= base.minute:
            raise CanonBridgeError(
                "adiamento exige prazo temporal posterior à ativação padrão"
            )
        delay_minutes = end.minute - base.minute
        if delay_minutes > int(contract["atraso_maximo_horas"]) * 60:
            raise CanonBridgeError(
                "adiamento excede elasticidade temporal da intenção"
            )
        effective = end
    else:  # transformacao
        if "transformar" not in allowed or "satisfazer" not in allowed:
            raise CanonBridgeError(
                f"{event_id}: transformação por sidequest exige transformar+satisfazer"
            )
    state = load_state(repo)
    resolved = state["resolucoes"].get(event_id)
    if isinstance(resolved, dict) and resolved.get("estado") == "satisfeita":
        raise CanonBridgeError(f"{event_id}: intenção já foi satisfeita")
    existing = state["reservas"].get(event_id)
    if (
        isinstance(existing, dict)
        and existing.get("mission_id") != mission.get("id")
    ):
        raise CanonBridgeError(
            f"{event_id}: intenção já reservada por {existing.get('mission_id')}"
        )
    return {
        "acao": "reservar",
        "evento_id": event_id,
        "intencao_id": intent["intencao_canonica"]["id"],
        "mission_id": mission["id"],
        "quest_id": mission.get("quest_id"),
        "modo": mode,
        "estado": "ativa",
        "criada_em": mundo.instant_parts(now),
        "ativacao_padrao": mundo.instant_parts(base),
        "ativacao_efetiva": mundo.instant_parts(effective),
        "ancora_quest": {
            "prazo": copy.deepcopy(doc.get("prazo")),
            "locais_fase_final": _final_locations(doc),
        },
        "justificativa": _text(
            relation.get("justificativa"), "relacao_canone.justificativa"
        ),
        "regra_agencia": "ancora_causal_nao_move_nem_decide_ren",
        "fontes_lidas": sources,
    }


def prepare_lifecycle_transition(
    repo: Path,
    mission: dict[str, Any],
    target_state: str,
    now: mundo.WorldInstant,
) -> dict[str, Any] | None:
    """Valida a reserva antes da escrita do lifecycle; não escreve."""
    if target_state != "aceita" or mission.get("origem") != "sidequest_emergente":
        return None
    doc, source = _quest_document(repo, mission)
    plan = _validate_relation(repo, mission, doc, now)
    if plan is None:
        return {
            "acao": "lateral",
            "mission_id": mission["id"],
            "fontes_lidas": [source],
        }
    plan["fontes_lidas"] = [source, *plan["fontes_lidas"], STATE.as_posix()]
    return plan


def apply_lifecycle_transition(
    repo: Path, plan: dict[str, Any] | None
) -> dict[str, Any]:
    if plan is None or plan.get("acao") == "lateral":
        return {
            "ok": True,
            "alterou": False,
            "resultado": "sem_reserva_canonica",
        }
    if plan.get("acao") != "reservar":
        raise CanonBridgeError("plano de transição Task42 inválido")
    state = load_state(repo)
    event_id = plan["evento_id"]
    existing = state["reservas"].get(event_id)
    if isinstance(existing, dict):
        comparable = {
            key: value
            for key, value in plan.items()
            if key not in {"acao", "fontes_lidas"}
        }
        if existing == comparable:
            return {
                "ok": True,
                "alterou": False,
                "resultado": "reserva_ja_existia",
            }
        raise CanonBridgeError(f"{event_id}: reserva concorrente/divergente")
    record = {
        key: copy.deepcopy(value)
        for key, value in plan.items()
        if key not in {"acao", "fontes_lidas"}
    }
    state["reservas"][event_id] = record
    _history(
        state,
        {
            "tipo": "reserva_criada",
            "evento_id": event_id,
            "mission_id": record["mission_id"],
            "modo": record["modo"],
            "em": copy.deepcopy(record["criada_em"]),
        },
    )
    _atomic(repo / STATE, state)
    return {
        "ok": True,
        "alterou": True,
        "resultado": "reserva_criada",
        "evento_id": event_id,
    }


def _world_event_status(
    repo: Path,
    catalog: dict[str, Any],
    event_id: str,
    effective: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    schedule_id = _schedule_id(catalog, event_id)
    schedule = _schedule(repo, catalog, event_id)
    origin = f"agenda:agendamentos.{schedule_id}"
    world = mundo.load_world_state(repo)
    pending = [
        item for item in world["pendencias"] if item.get("origem") == origin
    ]
    base = _base_activation(catalog, event_id)
    ids = {
        mundo._pending_id(
            schedule["tipo"], f"agendamentos.{schedule_id}", base
        )
    }
    if effective is not None:
        ids.add(
            mundo._pending_id(
                schedule["tipo"], f"agendamentos.{schedule_id}", effective
            )
        )
    completed = [
        item for item in world["concluidas_recentes"] if item.get("id") in ids
    ]
    return {
        "origin": origin,
        "pending": pending,
        "completed": completed,
        "world": world,
    }


def _sync_barrier(repo: Path, world: dict[str, Any] | None = None) -> None:
    try:
        import barreira_mundo
    except ImportError:
        return
    try:
        barreira_mundo.sync(repo, world)
    except barreira_mundo.WorldPendingBarrierError as exc:
        raise CanonBridgeError(str(exc)) from exc


def _ensure_fallback_pending(
    repo: Path, event_id: str, now: mundo.WorldInstant
) -> bool:
    _, catalog, _, _ = _event_context(repo, event_id)
    state = load_state(repo)
    if isinstance(state["resolucoes"].get(event_id), dict):
        return False
    base = _base_activation(catalog, event_id)
    world = mundo.load_world_state(repo)
    cursor = mundo._state_cursor(world)
    if base.minute > now.minute or cursor.minute < base.minute:
        return False
    schedule_id = _schedule_id(catalog, event_id)
    origin = f"agenda:agendamentos.{schedule_id}"
    if any(item.get("origem") == origin for item in world["pendencias"]):
        return False
    agenda = mundo.load_agenda(repo)
    trigger = next(
        (
            item
            for item in mundo._scheduled_triggers(
                agenda, mundo.WorldInstant(base.minute - 1), base
            )
            if item.get("origem") == origin
        ),
        None,
    )
    if trigger is None:
        raise CanonBridgeError(
            f"não foi possível reconstruir fallback canônico de {event_id}"
        )
    if any(
        item.get("id") == trigger["id"]
        for item in world["concluidas_recentes"]
    ):
        return False
    world["pendencias"].append(trigger)
    mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, world)
    _sync_barrier(repo, world)
    return True


def _release(
    repo: Path,
    state: dict[str, Any],
    event_id: str,
    *,
    reason: str,
    now: mundo.WorldInstant,
) -> bool:
    reservation = state["reservas"].get(event_id)
    if not isinstance(reservation, dict):
        return False
    _ensure_fallback_pending(repo, event_id, now)
    del state["reservas"][event_id]
    _history(
        state,
        {
            "tipo": "reserva_liberada",
            "evento_id": event_id,
            "mission_id": reservation.get("mission_id"),
            "motivo": reason,
            "em": mundo.instant_parts(now),
        },
    )
    return True


def apply_terminal_transition(
    repo: Path,
    mission: dict[str, Any],
    outcome: str,
    now: mundo.WorldInstant,
) -> dict[str, Any]:
    if (
        mission.get("origem") != "sidequest_emergente"
        or not configured(repo)
    ):
        return {"ok": True, "alterou": False}
    state = load_state(repo)
    found = _reservation_for_mission(state, mission["id"])
    if found is None:
        return {"ok": True, "alterou": False}
    event_id, reservation = found
    changed = False
    if (
        outcome == "concluida"
        and reservation.get("modo") in {"convergente", "transformacao"}
    ):
        if reservation.get("estado") != "aguarda_evidencia":
            reservation["estado"] = "aguarda_evidencia"
            reservation["quest_concluida_em"] = mundo.instant_parts(now)
            _history(
                state,
                {
                    "tipo": "reserva_aguarda_evidencia",
                    "evento_id": event_id,
                    "mission_id": mission["id"],
                    "em": mundo.instant_parts(now),
                },
            )
            changed = True
    else:
        changed = _release(
            repo, state, event_id, reason=f"quest_{outcome}", now=now
        )
    if changed:
        _atomic(repo / STATE, state)
    return {"ok": True, "alterou": changed, "evento_id": event_id}


def reconcile_lifecycle(
    repo: Path,
    opportunity_state: dict[str, Any],
    now: mundo.WorldInstant,
) -> dict[str, Any]:
    if not configured(repo):
        return {"ok": True, "alterou": False, "liberadas": []}
    state = load_state(repo)
    changed = False
    released: list[str] = []
    for event_id, reservation in list(state["reservas"].items()):
        if not isinstance(reservation, dict):
            continue
        mission = opportunity_state.get("missoes", {}).get(
            reservation.get("mission_id")
        )
        mission_state = mission.get("estado") if isinstance(mission, dict) else None
        if mission_state in TERMINAL_RELEASE or mission_state is None:
            if _release(
                repo,
                state,
                event_id,
                reason=f"lifecycle_{mission_state or 'ausente'}",
                now=now,
            ):
                changed = True
                released.append(event_id)
        elif mission_state == "concluida":
            if reservation.get("modo") in {"convergente", "transformacao"}:
                if reservation.get("estado") != "aguarda_evidencia":
                    reservation["estado"] = "aguarda_evidencia"
                    changed = True
            elif _release(
                repo,
                state,
                event_id,
                reason="lifecycle_concluida",
                now=now,
            ):
                changed = True
                released.append(event_id)
    if changed:
        _atomic(repo / STATE, state)
    return {"ok": True, "alterou": changed, "liberadas": released}


def effective_scheduled_triggers(
    repo: Path,
    agenda: dict[str, Any],
    start: mundo.WorldInstant,
    end: mundo.WorldInstant,
) -> list[dict[str, Any]]:
    """Aplica overlay sem criar scheduler ou editar agenda."""
    if not configured(repo):
        return mundo._scheduled_triggers(agenda, start, end)
    state = load_state(repo)
    if not state["reservas"] and not state["resolucoes"]:
        return mundo._scheduled_triggers(agenda, start, end)
    adjusted = copy.deepcopy(agenda)
    schedules = []
    try:
        index = oportunidades.load_index(repo)
        opp_state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise CanonBridgeError(str(exc)) from exc
    for item in adjusted.get("agendamentos") or []:
        event_id = item.get("evento_canonico")
        if not isinstance(event_id, str):
            schedules.append(item)
            continue
        resolution = state["resolucoes"].get(event_id)
        if (
            isinstance(resolution, dict)
            and resolution.get("estado") == "satisfeita"
        ):
            continue
        reservation = state["reservas"].get(event_id)
        if (
            isinstance(reservation, dict)
            and reservation.get("modo") == "adiamento"
        ):
            mission = opp_state["missoes"].get(reservation.get("mission_id"))
            if isinstance(mission, dict) and mission.get("estado") == "aceita":
                item["em"] = copy.deepcopy(reservation["ativacao_efetiva"])
        schedules.append(item)
    adjusted["agendamentos"] = schedules
    return mundo._scheduled_triggers(adjusted, start, end)


def event_overlay(repo: Path, event_id: str) -> dict[str, Any] | None:
    if not configured(repo):
        return None
    state = load_state(repo)
    resolution = state["resolucoes"].get(event_id)
    if isinstance(resolution, dict):
        return {
            "estado": "satisfeita",
            "mission_id": resolution.get("mission_id"),
            "modo": resolution.get("modo"),
            "realizacao_padrao": "suprimida_por_intencao_satisfeita",
        }
    reservation = state["reservas"].get(event_id)
    if not isinstance(reservation, dict):
        return None
    return {
        "estado": reservation.get("estado"),
        "mission_id": reservation.get("mission_id"),
        "modo": reservation.get("modo"),
        "ativacao_efetiva": copy.deepcopy(reservation.get("ativacao_efetiva")),
        "ancora_quest": copy.deepcopy(reservation.get("ancora_quest")),
        "regra": (
            "ponte causal orienta forma; nunca obriga Ren a estar ou agir na âncora"
        ),
    }


def _cleanup_satisfied_pending(
    repo: Path, event_id: str, catalog: dict[str, Any]
) -> bool:
    schedule_id = _schedule_id(catalog, event_id)
    origin = f"agenda:agendamentos.{schedule_id}"
    world = mundo.load_world_state(repo)
    matches = [
        item for item in world["pendencias"] if item.get("origem") == origin
    ]
    changed = False
    for item in matches:
        mundo.conclude(
            repo,
            item["id"],
            f"intenção canônica satisfeita via sidequest: {event_id}",
        )
        changed = True
    if changed:
        _sync_barrier(repo)
    return changed


def satisfy(
    repo: Path,
    mission_id: str,
    evidences_raw: Any,
    *,
    note: str,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    current = now or mundo.load_canonical_time(repo)[0]
    note = _text(note, "nota", minimum=12, maximum=520)
    try:
        index = oportunidades.load_index(repo)
        opp = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise CanonBridgeError(str(exc)) from exc
    mission = opp["missoes"].get(mission_id)
    if (
        not isinstance(mission, dict)
        or mission.get("origem") != "sidequest_emergente"
    ):
        raise CanonBridgeError(
            "missão emergente inexistente para satisfação canônica"
        )
    if mission.get("estado") != "concluida":
        raise CanonBridgeError(
            "somente sidequest concluída pode satisfazer intenção canônica"
        )
    state = load_state(repo)
    found = _reservation_for_mission(state, mission_id)
    if found is None:
        existing = next(
            (
                (eid, raw)
                for eid, raw in state["resolucoes"].items()
                if isinstance(raw, dict) and raw.get("mission_id") == mission_id
            ),
            None,
        )
        if existing is not None:
            event_id, resolution = existing
            _, catalog, _, _ = _event_context(repo, event_id)
            cleaned = _cleanup_satisfied_pending(repo, event_id, catalog)
            return {
                "ok": True,
                "resultado": "ja_satisfeita",
                "evento_id": event_id,
                "intencao_id": resolution.get("intencao_id"),
                "pendencia_limpa": cleaned,
            }
        raise CanonBridgeError(
            "missão concluída não possui reserva canônica ativa"
        )
    event_id, reservation = found
    if reservation.get("modo") not in {"convergente", "transformacao"}:
        raise CanonBridgeError(
            "somente convergência/transformação pode satisfazer intenção pela Task42"
        )
    _, catalog, intent, sources = _event_context(repo, event_id)
    contract = intent["contrato_rewrite"]
    if "satisfazer" not in set(contract["modos_permitidos"]):
        raise CanonBridgeError(
            f"{event_id}: Task39 não permite satisfação alternativa"
        )
    criteria = list(intent["intencao_canonica"]["criterios_satisfacao"])
    raw = _list(evidences_raw, "evidencias")
    if len(raw) != len(criteria):
        raise CanonBridgeError(
            "satisfação exige uma evidência para cada critério canônico"
        )
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pos, item in enumerate(raw):
        data = _map(item, f"evidencias[{pos}]")
        if set(data) != {"criterio", "fonte", "evidencia"}:
            raise CanonBridgeError(
                "evidência exige criterio, fonte e evidencia"
            )
        criterion = _text(data["criterio"], f"evidencias[{pos}].criterio")
        if criterion not in criteria or criterion in seen:
            raise CanonBridgeError(
                "critério de satisfação desconhecido ou duplicado"
            )
        seen.add(criterion)
        path, source = _safe_repo_path(
            repo, data["fonte"], f"evidencias[{pos}].fonte"
        )
        literal = _text(
            data["evidencia"],
            f"evidencias[{pos}].evidencia",
            minimum=8,
            maximum=MAX_EVIDENCE_CHARS,
        )
        content = path.read_text(encoding="utf-8")
        if literal not in content:
            raise CanonBridgeError(
                f"evidência literal não encontrada em {source}"
            )
        normalized.append(
            {
                "criterio": criterion,
                "fonte": source,
                "evidencia": literal,
                "sha256_fonte": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    if seen != set(criteria):
        raise CanonBridgeError(
            "nem todos os critérios da intenção foram provados"
        )

    runtime = _world_event_status(
        repo,
        catalog,
        event_id,
        mundo.parse_instant(
            reservation["ativacao_efetiva"]["data"],
            reservation["ativacao_efetiva"]["hora"],
        ),
    )
    if runtime["completed"]:
        raise CanonBridgeError(
            "realização padrão já foi materializada; Task42 não reescreve o passado"
        )
    resolution = {
        "estado": "satisfeita",
        "evento_id": event_id,
        "intencao_id": intent["intencao_canonica"]["id"],
        "mission_id": mission_id,
        "quest_id": mission.get("quest_id"),
        "modo": reservation["modo"],
        "resolvida_em": mundo.instant_parts(current),
        "nota": note,
        "evidencias": normalized,
        "realizacao_padrao": "suprimida_somente_por_intencao_satisfeita",
    }
    state["resolucoes"][event_id] = resolution
    del state["reservas"][event_id]
    _history(
        state,
        {
            "tipo": "intencao_satisfeita",
            "evento_id": event_id,
            "mission_id": mission_id,
            "modo": reservation["modo"],
            "em": mundo.instant_parts(current),
        },
    )
    _atomic(repo / STATE, state)
    cleaned = _cleanup_satisfied_pending(repo, event_id, catalog)
    return {
        "ok": True,
        "resultado": "intencao_satisfeita",
        "evento_id": event_id,
        "intencao_id": resolution["intencao_id"],
        "realizacao_padrao": "suprimida",
        "pendencia_limpa": cleaned,
        "fontes_lidas": list(
            dict.fromkeys(
                [
                    STATE.as_posix(),
                    oportunidades.INDEX.as_posix(),
                    oportunidades.STATE.as_posix(),
                    *sources,
                    *[item["fonte"] for item in normalized],
                ]
            )
        ),
    }


def status(repo: Path) -> dict[str, Any]:
    state = load_state(repo)
    return {
        "ok": True,
        "reservas": [
            {
                "evento_id": event_id,
                "mission_id": raw.get("mission_id"),
                "modo": raw.get("modo"),
                "estado": raw.get("estado"),
                "ativacao_efetiva": copy.deepcopy(raw.get("ativacao_efetiva")),
            }
            for event_id, raw in sorted(state["reservas"].items())
            if isinstance(raw, dict)
        ],
        "satisfeitas": [
            {
                "evento_id": event_id,
                "mission_id": raw.get("mission_id"),
                "modo": raw.get("modo"),
                "resolvida_em": copy.deepcopy(raw.get("resolvida_em")),
            }
            for event_id, raw in sorted(state["resolucoes"].items())
            if isinstance(raw, dict)
        ],
        "fontes_lidas": [STATE.as_posix()],
    }


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    reservations = resolutions = 0
    try:
        state = load_state(repo)
        index = intencoes_canonicas.load_index(repo)
        catalog = eventos_canonicos.load_catalog(repo)
        opp_index = oportunidades.load_index(repo)
        opp = oportunidades.load_state(repo, opp_index)
        for event_id, raw in state["reservas"].items():
            reservations += 1
            reservation = _map(raw, f"reservas.{event_id}")
            if event_id in index["passado_congelado"]:
                raise CanonBridgeError(
                    f"{event_id}: passado congelado recebeu reserva"
                )
            intent = intencoes_canonicas.load_intent(
                repo, event_id, index=index, catalog=catalog
            )
            if (
                reservation.get("intencao_id")
                != intent["intencao_canonica"]["id"]
            ):
                raise CanonBridgeError(
                    f"{event_id}: intenção da reserva diverge da Task39"
                )
            if reservation.get("modo") not in set(RELATION_TO_MODE.values()):
                raise CanonBridgeError(
                    f"{event_id}: modo de reserva inválido"
                )
            if reservation.get("estado") not in RESERVATION_STATES:
                raise CanonBridgeError(
                    f"{event_id}: estado de reserva inválido"
                )
            mission = opp["missoes"].get(reservation.get("mission_id"))
            if (
                not isinstance(mission, dict)
                or mission.get("origem") != "sidequest_emergente"
            ):
                raise CanonBridgeError(
                    f"{event_id}: reserva aponta missão emergente inexistente"
                )
            if (
                mission.get("estado") == "aceita"
                and reservation["estado"] != "ativa"
            ):
                raise CanonBridgeError(
                    f"{event_id}: missão aceita deveria ter reserva ativa"
                )
            if (
                mission.get("estado") == "concluida"
                and reservation["modo"] in {"convergente", "transformacao"}
                and reservation["estado"] != "aguarda_evidencia"
            ):
                raise CanonBridgeError(
                    f"{event_id}: conclusão convergente aguarda evidência"
                )
            if mission.get("estado") in TERMINAL_RELEASE:
                raise CanonBridgeError(
                    f"{event_id}: reserva presa a missão terminal"
                )
        for event_id, raw in state["resolucoes"].items():
            resolutions += 1
            resolution = _map(raw, f"resolucoes.{event_id}")
            if event_id in state["reservas"]:
                raise CanonBridgeError(
                    f"{event_id}: intenção simultaneamente reservada e satisfeita"
                )
            if event_id in index["passado_congelado"]:
                raise CanonBridgeError(
                    f"{event_id}: passado congelado recebeu resolução Task42"
                )
            intent = intencoes_canonicas.load_intent(
                repo, event_id, index=index, catalog=catalog
            )
            if (
                resolution.get("estado") != "satisfeita"
                or resolution.get("realizacao_padrao")
                != "suprimida_somente_por_intencao_satisfeita"
            ):
                raise CanonBridgeError(
                    f"{event_id}: realização padrão só pode ser suprimida por intenção satisfeita"
                )
            expected = set(
                intent["intencao_canonica"]["criterios_satisfacao"]
            )
            evidence = _list(
                resolution.get("evidencias"),
                f"resolucoes.{event_id}.evidencias",
            )
            got = {
                item.get("criterio")
                for item in evidence
                if isinstance(item, dict)
            }
            if got != expected:
                raise CanonBridgeError(
                    f"{event_id}: resolução não cobre todos os critérios"
                )
    except (
        CanonBridgeError,
        intencoes_canonicas.CanonicalIntentError,
        eventos_canonicos.CanonicalEventError,
        oportunidades.OpportunityError,
        mundo.WorldEngineError,
    ) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "erros": errors,
        "reservas": reservations,
        "resolucoes": resolutions,
        "max_state_bytes": MAX_STATE_BYTES,
        "schedulers_novos": 0,
        "rng_novo": 0,
        "scans_globais": 0,
    }


def _stdin() -> dict[str, Any]:
    import sys

    try:
        return _map(yaml.safe_load(sys.stdin.read()), "stdin")
    except yaml.YAMLError as exc:
        raise CanonBridgeError(str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("check")
    sub.add_parser("reconciliar")
    sat = sub.add_parser("satisfazer")
    sat.add_argument("mission_id")
    sat.add_argument("--nota", required=True)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "status":
            result = status(repo)
        elif args.cmd == "check":
            result = check(repo)
        elif args.cmd == "reconciliar":
            idx = oportunidades.load_index(repo)
            opp = oportunidades.load_state(repo, idx)
            now = mundo.load_canonical_time(repo)[0]
            result = reconcile_lifecycle(repo, opp, now)
        else:
            payload = _stdin()
            result = satisfy(
                repo,
                args.mission_id,
                payload.get("evidencias"),
                note=args.nota,
            )
        print(
            yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end=""
        )
        return 0 if result.get("ok") else 1
    except (
        CanonBridgeError,
        oportunidades.OpportunityError,
        mundo.WorldEngineError,
    ) as exc:
        print(
            yaml.safe_dump(
                {"ok": False, "erro": str(exc)},
                allow_unicode=True,
                sort_keys=False,
            ),
            end="",
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
