#!/usr/bin/env python3
"""Porta operacional da Task 42 para lifecycle e fronteira do mundo.

A integração automática com `cronica` fica para a Task 46. Esta porta já torna o
bridge completo: responde/finaliza sidequests pela autoridade de oportunidades e
reconcilia adiamentos com a fila existente do Mundo Vivo, sem novo scheduler.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any

import yaml

import canon_bridge
import mundo
import oportunidades


class CanonBridgeRuntimeError(ValueError):
    pass


def _now(repo: Path, supplied: mundo.WorldInstant | None) -> mundo.WorldInstant:
    return supplied or mundo.load_canonical_time(repo)[0]


def _mission(repo: Path, mission_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise CanonBridgeRuntimeError(str(exc)) from exc
    mission = state["missoes"].get(mission_id)
    if not isinstance(mission, dict):
        raise CanonBridgeRuntimeError(f"missão inexistente: {mission_id}")
    return index, state, mission


def _rollback_reservation(repo: Path, mission_id: str, current: mundo.WorldInstant) -> None:
    if not canon_bridge.configured(repo):
        return
    state = canon_bridge.load_state(repo)
    found = canon_bridge._reservation_for_mission(state, mission_id)
    if found is None:
        return
    event_id, reservation = found
    # A transição do lifecycle falhou antes do aceite; o evento ainda é futuro.
    del state["reservas"][event_id]
    canon_bridge._history(state, {
        "tipo": "reserva_revertida", "evento_id": event_id,
        "mission_id": mission_id, "motivo": "lifecycle_nao_confirmou_aceite",
        "em": mundo.instant_parts(current),
    })
    canon_bridge._atomic(repo / canon_bridge.STATE, state)


def respond(
    repo: Path,
    mission_id: str,
    response: str,
    *,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    current = _now(repo, now)
    index, state, mission = _mission(repo, mission_id)
    if mission.get("origem") != "sidequest_emergente":
        raise CanonBridgeRuntimeError("porta Task42 responde somente sidequest emergente")
    if response not in {"aceitar", "adiar", "recusar"}:
        raise CanonBridgeRuntimeError("resposta deve ser aceitar, adiar ou recusar")

    bridge_plan = None
    if response == "aceitar":
        active, _ = oportunidades._mission_counts(state)
        if active >= index["orcamento"]["max_ativas"]:
            raise CanonBridgeRuntimeError("limite de sidequests ativas atingido")
        try:
            bridge_plan = canon_bridge.prepare_lifecycle_transition(
                repo, mission, "aceita", current
            )
            bridge_result = canon_bridge.apply_lifecycle_transition(repo, bridge_plan)
        except canon_bridge.CanonBridgeError as exc:
            raise CanonBridgeRuntimeError(str(exc)) from exc
    else:
        bridge_result = {"ok": True, "alterou": False, "resultado": "sem_reserva"}

    try:
        lifecycle = oportunidades.respond(repo, mission_id, response, now=current)
    except oportunidades.OpportunityError as exc:
        if response == "aceitar" and bridge_plan is not None:
            _rollback_reservation(repo, mission_id, current)
        raise CanonBridgeRuntimeError(str(exc)) from exc

    return {
        "ok": True,
        "resultado": lifecycle["resultado"],
        "missao": lifecycle["missao"],
        "canon_bridge": bridge_result,
        "regra": (
            "aceite não move Ren; reserva canônica apenas condiciona a forma futura. "
            "Recusa/adiamento de oferta não criam reserva."
        ),
        "fontes_lidas": list(dict.fromkeys([
            *(lifecycle.get("fontes_lidas") or []),
            *((bridge_plan or {}).get("fontes_lidas") or []),
        ])),
    }


def finish(
    repo: Path,
    mission_id: str,
    outcome: str,
    *,
    reason: str,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    current = _now(repo, now)
    _, _, mission = _mission(repo, mission_id)
    if mission.get("origem") != "sidequest_emergente":
        raise CanonBridgeRuntimeError("porta Task42 finaliza somente sidequest emergente")
    try:
        lifecycle = oportunidades.finish(
            repo, mission_id, outcome, reason=reason, now=current
        )
        bridge = canon_bridge.apply_terminal_transition(
            repo, lifecycle["missao"], outcome, current
        )
    except (oportunidades.OpportunityError, canon_bridge.CanonBridgeError) as exc:
        raise CanonBridgeRuntimeError(str(exc)) from exc
    return {
        "ok": True,
        "resultado": lifecycle["resultado"],
        "missao": lifecycle["missao"],
        "canon_bridge": bridge,
        "regra": (
            "ponte/adiamento liberam a reserva ao terminar; convergência/transformação "
            "concluídas aguardam evidência antes de suprimir realização padrão"
        ),
    }


def _pending_origin(catalog: dict[str, Any], event_id: str) -> str:
    return f"agenda:agendamentos.{canon_bridge._schedule_id(catalog, event_id)}"


def _consume_original_delay_pending(
    repo: Path,
    event_id: str,
    reservation: dict[str, Any],
    catalog: dict[str, Any],
) -> bool:
    world = mundo.load_world_state(repo)
    origin = _pending_origin(catalog, event_id)
    base = mundo.parse_instant(
        reservation["ativacao_padrao"]["data"], reservation["ativacao_padrao"]["hora"]
    )
    effective = mundo.parse_instant(
        reservation["ativacao_efetiva"]["data"], reservation["ativacao_efetiva"]["hora"]
    )
    matches = []
    for item in world["pendencias"]:
        if item.get("origem") != origin:
            continue
        fired = item.get("disparado_em") or {}
        instant = mundo.parse_instant(str(fired.get("data")), str(fired.get("hora")))
        if instant.minute < effective.minute and instant.minute >= base.minute:
            matches.append(item)
    if not matches:
        return False
    remove_ids = {item["id"] for item in matches}
    world["pendencias"] = [item for item in world["pendencias"] if item["id"] not in remove_ids]
    mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, world)
    try:
        import barreira_mundo
        barreira_mundo.sync(repo, world)
    except ImportError:
        pass
    return True


def _emit_delayed_pending(
    repo: Path,
    event_id: str,
    reservation: dict[str, Any],
    catalog: dict[str, Any],
    current: mundo.WorldInstant,
) -> bool:
    effective = mundo.parse_instant(
        reservation["ativacao_efetiva"]["data"], reservation["ativacao_efetiva"]["hora"]
    )
    if current.minute < effective.minute:
        return False
    world = mundo.load_world_state(repo)
    cursor = mundo._state_cursor(world)
    if cursor.minute < effective.minute:
        return False
    origin = _pending_origin(catalog, event_id)
    if any(item.get("origem") == origin for item in world["pendencias"]):
        return False
    schedule_id = canon_bridge._schedule_id(catalog, event_id)
    agenda = mundo.load_agenda(repo)
    adjusted = copy.deepcopy(agenda)
    for item in adjusted.get("agendamentos") or []:
        if item.get("id") == schedule_id:
            item["em"] = mundo.instant_parts(effective)
            break
    trigger = next(
        (
            item for item in mundo._scheduled_triggers(
                adjusted, mundo.WorldInstant(effective.minute - 1), effective
            )
            if item.get("origem") == origin
        ),
        None,
    )
    if trigger is None:
        raise CanonBridgeRuntimeError(f"não foi possível emitir disparo adiado de {event_id}")
    if any(item.get("id") == trigger["id"] for item in world["concluidas_recentes"]):
        return False
    world["pendencias"].append(trigger)
    mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, world)
    try:
        import barreira_mundo
        barreira_mundo.sync(repo, world)
    except ImportError:
        pass
    return True


def reconcile_world(repo: Path, *, now: mundo.WorldInstant | None = None) -> dict[str, Any]:
    current = _now(repo, now)
    if not canon_bridge.configured(repo):
        return {"ok": True, "alterou": False, "adiamentos": []}
    bridge = canon_bridge.load_state(repo)
    try:
        catalog = __import__("eventos_canonicos").load_catalog(repo)
        opp_index = oportunidades.load_index(repo)
        opp = oportunidades.load_state(repo, opp_index)
    except Exception as exc:
        if isinstance(exc, (oportunidades.OpportunityError, mundo.WorldEngineError)):
            raise CanonBridgeRuntimeError(str(exc)) from exc
        raise
    results = []
    for event_id, reservation in bridge["reservas"].items():
        if not isinstance(reservation, dict) or reservation.get("modo") != "adiamento":
            continue
        mission = opp["missoes"].get(reservation.get("mission_id"))
        if not isinstance(mission, dict) or mission.get("estado") != "aceita":
            continue
        consumed = _consume_original_delay_pending(repo, event_id, reservation, catalog)
        emitted = _emit_delayed_pending(repo, event_id, reservation, catalog, current)
        results.append({
            "evento_id": event_id,
            "disparo_original_retido": consumed,
            "disparo_adiado_emitido": emitted,
        })
    return {
        "ok": True,
        "alterou": any(
            item["disparo_original_retido"] or item["disparo_adiado_emitido"]
            for item in results
        ),
        "adiamentos": results,
        "regra": "usa a fila/scheduler existentes; Task42 não cria relógio paralelo",
    }


def reconcile(
    repo: Path, *, now: mundo.WorldInstant | None = None
) -> dict[str, Any]:
    current = _now(repo, now)
    # status é a porta existente que faz prune reativo do lifecycle.
    try:
        opportunities_status = oportunidades.status(repo, now=current)
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
        lifecycle = canon_bridge.reconcile_lifecycle(repo, state, current)
        world = reconcile_world(repo, now=current)
    except (oportunidades.OpportunityError, canon_bridge.CanonBridgeError) as exc:
        raise CanonBridgeRuntimeError(str(exc)) from exc
    return {
        "ok": True,
        "oportunidades": {
            "ativas": opportunities_status["ativas"],
            "em_aberto": opportunities_status["em_aberto"],
        },
        "lifecycle": lifecycle,
        "mundo": world,
    }


def check(repo: Path) -> dict[str, Any]:
    base = canon_bridge.check(repo)
    errors = list(base.get("erros") or [])
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
        bridge = canon_bridge.load_state(repo)
        reserved_by_mission = {
            raw.get("mission_id"): event_id
            for event_id, raw in bridge["reservas"].items()
            if isinstance(raw, dict)
        }
        resolved_by_mission = {
            raw.get("mission_id"): event_id
            for event_id, raw in bridge["resolucoes"].items()
            if isinstance(raw, dict)
        }
        for mission_id, mission in state["missoes"].items():
            if not isinstance(mission, dict) or mission.get("origem") != "sidequest_emergente":
                continue
            doc, _ = canon_bridge._quest_document(repo, mission)
            relation = doc.get("relacao_canone") or {}
            mode = relation.get("modo")
            if mission.get("estado") == "aceita" and mode != "lateral":
                if mission_id not in reserved_by_mission and mission_id not in resolved_by_mission:
                    errors.append(
                        f"{mission_id}: quest não lateral aceita sem reserva Task42"
                    )
    except (oportunidades.OpportunityError, canon_bridge.CanonBridgeError) as exc:
        errors.append(str(exc))
    return {
        **base,
        "ok": not errors,
        "erros": errors,
        "scheduler_paralelo": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    response = sub.add_parser("responder")
    response.add_argument("mission_id")
    response.add_argument("resposta", choices=["aceitar", "adiar", "recusar"])
    end = sub.add_parser("finalizar")
    end.add_argument("mission_id")
    end.add_argument("resultado", choices=["concluida", "falhada", "expirada"])
    end.add_argument("--motivo", required=True)
    sub.add_parser("reconciliar")
    sub.add_parser("check")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "responder":
            result = respond(repo, args.mission_id, args.resposta)
        elif args.cmd == "finalizar":
            result = finish(
                repo, args.mission_id, args.resultado, reason=args.motivo
            )
        elif args.cmd == "reconciliar":
            result = reconcile(repo)
        else:
            result = check(repo)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0 if result.get("ok") else 1
    except (CanonBridgeRuntimeError, mundo.WorldEngineError) as exc:
        print(yaml.safe_dump({"ok": False, "erro": str(exc)}, allow_unicode=True, sort_keys=False), end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
