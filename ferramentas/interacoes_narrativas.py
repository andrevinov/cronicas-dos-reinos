#!/usr/bin/env python3
"""Identidade durável e feedback por unidade de interação narrativa.

O ledger é metadado operacional append-only. Ele não é cânone do mundo, não
mede desempenho no hot path e não guarda a prosa ON/OFF: somente hashes ligam a
entrada e a resposta às fontes autorizadas. ``cronica preparar/concluir`` usa as
funções públicas para ON; ``interacao registrar`` cobre OFF/RECALL/operacional.
"""
from __future__ import annotations

import argparse
import copy
import fcntl
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import yaml


EVENT_SCHEMA = 1
RECEIPT_SCHEMA = 1
LEDGER_NAME = "interacoes.jsonl"
PREPARE_RECEIPT_RESERVE_BYTES = 256
REFERENCE_RE = re.compile(r"^S(?P<session>\d{3,})-I(?P<ordinal>\d{4,})$")
CLASSES = {"ON", "OFF", "RECALL", "operacional"}
PERCEIVED_TYPES = {
    "boa_ativacao",
    "oportunidade_percebida",
    "sobreativacao_percebida",
    "ativacao_inadequada",
    "efeito_incorreto",
    "timing",
    "continuidade",
    "possivel_guardrail",
}
IMPACTS = {"baixo", "moderado", "alto", "critico"}
ADJUDICATIONS = {"pendente", "confirmada", "parcial", "nao_confirmada", "indeterminada"}


class InteractionError(ValueError):
    """Contrato ou ledger de interação inválido."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _current_release_snapshot(repo: Path) -> dict[str, Any] | None:
    path = Path(repo) / "evaluation/catalogo-modulos-v2.json"
    if not path.is_file():
        return None
    try:
        catalog = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    versions = {
        str(item["id"]): {
            "implementation_version": str(item["versao_implementacao"]),
            "evaluation_version": str(item["versao_avaliacao"]),
        }
        for item in catalog.get("modulos") or []
        if item.get("id") and item.get("versao_implementacao") and item.get("versao_avaliacao")
    }
    if not versions:
        return None
    canonical = json.dumps(versions, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {
        "release_set_id": "release-set-" + _digest(canonical)[:16],
        "catalog_version": catalog.get("versao_catalogo"),
        "module_versions": versions,
    }


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise InteractionError(f"{label} precisa ser texto não vazio")
    return value.strip()


def _session_from_runtime(repo: Path) -> tuple[int, bool]:
    path = Path(repo) / "runtime/contexto.yaml"
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError as exc:
        raise InteractionError(f"runtime de sessão ausente: {path}") from exc
    except yaml.YAMLError as exc:
        raise InteractionError(f"runtime de sessão inválido: {exc}") from exc
    session = ((data.get("sessao") or {}).get("numero")) if isinstance(data, dict) else None
    status = ((data.get("sessao") or {}).get("status")) if isinstance(data, dict) else None
    if not isinstance(session, int) or session < 1:
        raise InteractionError("runtime não define sessão atual válida")
    return session, status == "em_sessao"


def active_session(repo: Path) -> int | None:
    """Retorna a sessão ativa; repositório sem runtime não ativa a integração."""

    try:
        session, active = _session_from_runtime(Path(repo))
    except InteractionError:
        return None
    return session if active else None


def integration_enabled(repo: Path) -> bool:
    """Indica que a sessão ativa também possui o contrato modular RM-11."""

    return active_session(repo) is not None and _current_release_snapshot(Path(repo)) is not None


def ledger_path(repo: Path, session: int) -> Path:
    return Path(repo) / "sessoes" / f"{session:03d}" / LEDGER_NAME


def parse_reference(reference: str) -> tuple[int, int]:
    match = REFERENCE_RE.fullmatch(_text(reference, "interaction_ref"))
    if not match:
        raise InteractionError("interaction_ref deve usar S<sessão>-I<ordinal>, por exemplo S022-I0049")
    return int(match.group("session")), int(match.group("ordinal"))


def _read_lines(stream: Any, label: str) -> list[dict[str, Any]]:
    stream.seek(0)
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(stream, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise InteractionError(f"{label}:{line_number}: JSON inválido: {exc}") from exc
        if not isinstance(value, dict) or value.get("schema_interaction_event") != EVENT_SCHEMA:
            raise InteractionError(f"{label}:{line_number}: evento de interação inválido")
        records.append(value)
    return records


def load_events(repo: Path, session: int) -> list[dict[str, Any]]:
    path = ledger_path(repo, session)
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8") as stream:
        return _read_lines(stream, str(path))


def _locked(
    repo: Path,
    session: int,
    operation: Callable[[list[dict[str, Any]]], tuple[Any, list[dict[str, Any]]]],
) -> Any:
    path = ledger_path(repo, session)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as stream:
        fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
        records = _read_lines(stream, str(path))
        result, additions = operation(records)
        for event in additions:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
        if additions:
            stream.flush()
        fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
    return result


def _completion_by_ref(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(event.get("interaction_ref")): event
        for event in records
        if event.get("event_type") == "completed"
    }


def _reservation_receipt(event: dict[str, Any], *, replay: bool) -> dict[str, Any]:
    return {
        "schema_narrative_interaction": RECEIPT_SCHEMA,
        "interaction_id": event["interaction_id"],
        "interaction_ref": event["interaction_ref"],
        "session": event["session"],
        "ordinal": event["ordinal"],
        "class": event["interaction_class"],
        "state": "reserved",
        "replay": replay,
        "release_set_id": event.get("release_set_id"),
    }


def reserve(
    repo: Path,
    *,
    interaction_class: str,
    correlation_key: str,
    input_text: str | None = None,
) -> dict[str, Any]:
    session, active = _session_from_runtime(Path(repo))
    if not active:
        raise InteractionError("unidades de interação só podem ser reservadas em sessão ativa")
    if interaction_class not in CLASSES:
        raise InteractionError(f"classe de interação inválida: {interaction_class!r}")
    correlation = _text(correlation_key, "correlation_key")
    input_hash = _digest(input_text) if isinstance(input_text, str) else None
    release_snapshot = _current_release_snapshot(Path(repo))

    def operation(records: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        candidates = [
            event
            for event in records
            if event.get("event_type") == "reserved"
            and event.get("correlation_key") == correlation
        ]
        if candidates:
            return _reservation_receipt(candidates[-1], replay=True), []
        ordinal = max((int(event.get("ordinal") or 0) for event in records), default=0) + 1
        reference = f"S{session:03d}-I{ordinal:04d}"
        interaction_id = "interaction-" + _digest(f"{session}:{ordinal}:{correlation}")[:20]
        event = {
            "schema_interaction_event": EVENT_SCHEMA,
            "event_type": "reserved",
            "recorded_at": _now(),
            "interaction_id": interaction_id,
            "interaction_ref": reference,
            "session": session,
            "ordinal": ordinal,
            "interaction_class": interaction_class,
            "correlation_key": correlation,
            "input_sha256": input_hash,
            "release_set_id": (release_snapshot or {}).get("release_set_id"),
        }
        additions: list[dict[str, Any]] = []
        if release_snapshot is not None and not any(
            item.get("event_type") == "module_release_snapshot"
            and item.get("release_set_id") == release_snapshot["release_set_id"]
            for item in records
        ):
            additions.append(
                {
                    "schema_interaction_event": EVENT_SCHEMA,
                    "event_type": "module_release_snapshot",
                    "recorded_at": _now(),
                    **release_snapshot,
                }
            )
        additions.append(event)
        return _reservation_receipt(event, replay=False), additions

    return _locked(Path(repo), session, operation)


def _completion_receipt(reservation: dict[str, Any], *, replay: bool) -> dict[str, Any]:
    return {
        "schema_narrative_interaction": RECEIPT_SCHEMA,
        "interaction_id": reservation["interaction_id"],
        "interaction_ref": reservation["interaction_ref"],
        "session": reservation["session"],
        "ordinal": reservation["ordinal"],
        "class": reservation["interaction_class"],
        "state": "complete",
        "replay": replay,
        "visible_marker": f"INTERAÇÃO — {reservation['interaction_ref']}",
        "release_set_id": reservation.get("release_set_id"),
    }


def complete(
    repo: Path,
    *,
    reference: str,
    input_text: str,
    response_text: str,
    transaction_id: str | None = None,
    ticket_id: str | None = None,
) -> dict[str, Any]:
    session, _ = parse_reference(reference)
    player_hash = _digest(_text(input_text, "entrada"))
    response_hash = _digest(_text(response_text, "resposta"))

    def operation(records: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        reservations = [
            event
            for event in records
            if event.get("event_type") == "reserved" and event.get("interaction_ref") == reference
        ]
        if not reservations:
            raise InteractionError(f"reserva inexistente: {reference}")
        reservation = reservations[-1]
        existing = _completion_by_ref(records).get(reference)
        if existing is not None:
            if existing.get("input_sha256") != player_hash or existing.get("response_sha256") != response_hash:
                raise InteractionError(f"retry de {reference} diverge do par já concluído")
            return _completion_receipt(reservation, replay=True), []
        event = {
            "schema_interaction_event": EVENT_SCHEMA,
            "event_type": "completed",
            "recorded_at": _now(),
            "interaction_id": reservation["interaction_id"],
            "interaction_ref": reference,
            "session": reservation["session"],
            "ordinal": reservation["ordinal"],
            "interaction_class": reservation["interaction_class"],
            "input_sha256": player_hash,
            "response_sha256": response_hash,
            "transaction_id": transaction_id,
            "ticket_id": ticket_id,
        }
        return _completion_receipt(reservation, replay=False), [event]

    return _locked(Path(repo), session, operation)


def _reservation_for_key(repo: Path, correlation_key: str) -> dict[str, Any] | None:
    session = active_session(repo)
    if session is None:
        return None
    records = load_events(repo, session)
    candidates = [
        event
        for event in records
        if event.get("event_type") == "reserved"
        and event.get("correlation_key") == correlation_key
    ]
    return candidates[-1] if candidates else None


def attach_prepare(repo: Path, result: dict[str, Any]) -> dict[str, Any]:
    """Reserva a identidade ON na saída do preparar sem mudar o ticket."""

    if not integration_enabled(repo) or not isinstance(result.get("ticket_id"), str):
        return result
    receipt = reserve(
        repo,
        interaction_class="ON",
        correlation_key=f"ticket:{result['ticket_id']}",
    )
    out = copy.deepcopy(result)
    # O preparo precisa expor a referência, mas versões e metadados extensos
    # já estão preservados no ledger append-only. O recibo público permanece
    # curto para não retirar espaço de memória de cena e iniciativa.
    out["interacao"] = {
        "schema_narrative_interaction": receipt["schema_narrative_interaction"],
        "interaction_id": receipt["interaction_id"],
        "interaction_ref": receipt["interaction_ref"],
        "state": receipt["state"],
    }
    return out


def append_footer(footer: str, reference: str) -> str:
    _text(footer, "rodape_canonico")
    parse_reference(reference)
    marker = f"Interação {reference}"
    if marker in footer:
        return footer
    return f"{footer} · {marker}"


def attach_conclusion(
    repo: Path,
    result: dict[str, Any],
    transaction: dict[str, Any],
    *,
    ticket_id: str,
) -> dict[str, Any]:
    """Completa a reserva ON depois do writer e inclui a referência no rodapé."""

    correlation = f"ticket:{ticket_id}"
    reservation = _reservation_for_key(Path(repo), correlation)
    if reservation is None:
        return result
    persisted = result.get("transacao") if isinstance(result.get("transacao"), dict) else {}
    footer = result.get("rodape_canonico")
    final_footer = (
        append_footer(footer, reservation["interaction_ref"])
        if isinstance(footer, str) and footer.strip()
        else None
    )
    narration = _text(transaction.get("narracao"), "transacao.narracao")
    visible_response = f"{narration.rstrip()}\n{final_footer}" if final_footer else narration
    receipt = complete(
        repo,
        reference=reservation["interaction_ref"],
        input_text=_text(transaction.get("jogador"), "transacao.jogador"),
        response_text=visible_response,
        transaction_id=str(persisted.get("id") or transaction.get("id") or "") or None,
        ticket_id=ticket_id,
    )
    out = copy.deepcopy(result)
    out["interacao"] = receipt
    if final_footer is not None:
        out["rodape_canonico"] = final_footer
    return out


def record_exchange(
    repo: Path,
    *,
    interaction_class: str,
    input_text: str,
    response_text: str,
    client_key: str | None = None,
) -> dict[str, Any]:
    player = _text(input_text, "entrada")
    response = _text(response_text, "resposta")
    correlation = client_key or "pair:" + _digest(f"{interaction_class}\0{player}\0{response}")
    session = active_session(repo)
    if session is None:
        raise InteractionError("não há sessão ativa para registrar a interação")
    records = load_events(repo, session)
    for event in reversed(records):
        if event.get("event_type") != "reserved" or event.get("correlation_key") != correlation:
            continue
        reference = str(event["interaction_ref"])
        completed = _completion_by_ref(records).get(reference)
        if completed is not None:
            return complete(
                repo,
                reference=reference,
                input_text=player,
                response_text=f"{response.rstrip()}\nINTERAÇÃO — {reference}",
            )
        break
    reserved = reserve(
        repo,
        interaction_class=interaction_class,
        correlation_key=correlation,
        input_text=player,
    )
    visible_response = f"{response.rstrip()}\nINTERAÇÃO — {reserved['interaction_ref']}"
    return complete(
        repo,
        reference=reserved["interaction_ref"],
        input_text=player,
        response_text=visible_response,
    )


def record_player_feedback(
    repo: Path,
    *,
    interaction_ref: str,
    original_text: str,
    perceived_type: str,
    expectation: str | None = None,
    observation: str | None = None,
    impact: str | None = None,
    module_id: str | None = None,
    capability_id: str | None = None,
) -> dict[str, Any]:
    session, _ = parse_reference(interaction_ref)
    text = _text(original_text, "texto_original")
    if perceived_type not in PERCEIVED_TYPES:
        raise InteractionError(f"tipo percebido inválido: {perceived_type!r}")
    if impact is not None and impact not in IMPACTS:
        raise InteractionError(f"impacto percebido inválido: {impact!r}")
    feedback_id = "feedback-" + _digest(f"{interaction_ref}\0{text}")[:20]

    def operation(records: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if not any(event.get("interaction_ref") == interaction_ref for event in records):
            raise InteractionError(f"interação alvo inexistente: {interaction_ref}")
        existing = next(
            (event for event in records if event.get("event_type") == "player_feedback" and event.get("feedback_id") == feedback_id),
            None,
        )
        if existing is not None:
            return copy.deepcopy(existing), []
        event = {
            "schema_interaction_event": EVENT_SCHEMA,
            "event_type": "player_feedback",
            "recorded_at": _now(),
            "feedback_id": feedback_id,
            "interaction_ref": interaction_ref,
            "original_text": text,
            "perceived_type": perceived_type,
            "expectation": expectation.strip() if isinstance(expectation, str) and expectation.strip() else None,
            "observation": observation.strip() if isinstance(observation, str) and observation.strip() else None,
            "perceived_impact": impact,
            "player_module_id": module_id,
            "player_capability_id": capability_id,
            "system_suggestion": None,
            "adjudication": {"state": "pendente", "reason": None},
        }
        return copy.deepcopy(event), [event]

    return _locked(Path(repo), session, operation)


def adjudicate_feedback(
    repo: Path,
    *,
    feedback_id: str,
    state: str,
    reason: str,
    module_id: str | None = None,
    capability_id: str | None = None,
    confidence: str | None = None,
    evidence: list[str] | None = None,
) -> dict[str, Any]:
    if state not in ADJUDICATIONS - {"pendente"}:
        raise InteractionError(f"estado de adjudicação inválido: {state!r}")
    justification = _text(reason, "reason")
    sessions_root = Path(repo) / "sessoes"
    candidates = sorted(sessions_root.glob("[0-9][0-9][0-9]/interacoes.jsonl"))
    for path in candidates:
        session = int(path.parent.name)
        records = load_events(repo, session)
        if not any(event.get("event_type") == "player_feedback" and event.get("feedback_id") == feedback_id for event in records):
            continue

        def operation(current: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
            event = {
                "schema_interaction_event": EVENT_SCHEMA,
                "event_type": "feedback_adjudicated",
                "recorded_at": _now(),
                "feedback_id": feedback_id,
                "state": state,
                "reason": justification,
                "system_module_id": module_id,
                "system_capability_id": capability_id,
                "confidence": confidence,
                "evidence": list(evidence or []),
            }
            previous = [item for item in current if item.get("event_type") == "feedback_adjudicated" and item.get("feedback_id") == feedback_id]
            if previous and {key: previous[-1].get(key) for key in event if key != "recorded_at"} == {key: event.get(key) for key in event if key != "recorded_at"}:
                return copy.deepcopy(previous[-1]), []
            return copy.deepcopy(event), [event]

        return _locked(Path(repo), session, operation)
    raise InteractionError(f"feedback inexistente: {feedback_id}")


def materialize(repo: Path, session: int) -> dict[str, Any]:
    records = load_events(repo, session)
    release_sets = {
        str(event["release_set_id"]): event
        for event in records
        if event.get("event_type") == "module_release_snapshot"
    }
    reservations = {
        str(event["interaction_ref"]): copy.deepcopy(event)
        for event in records
        if event.get("event_type") == "reserved"
    }
    completions = _completion_by_ref(records)
    interactions: list[dict[str, Any]] = []
    for reference, reserved in sorted(reservations.items(), key=lambda item: int(item[1]["ordinal"])):
        completed = completions.get(reference)
        release_set = release_sets.get(str(reserved.get("release_set_id"))) or {}
        interactions.append(
            {
                "interaction_id": reserved["interaction_id"],
                "interaction_ref": reference,
                "session": reserved["session"],
                "ordinal": reserved["ordinal"],
                "class": reserved["interaction_class"],
                "state": "complete" if completed else "incomplete",
                "input_sha256": (completed or reserved).get("input_sha256"),
                "response_sha256": (completed or {}).get("response_sha256"),
                "turn_id": None,
                "transaction_id": (completed or {}).get("transaction_id"),
                "ticket_id": (completed or {}).get("ticket_id"),
                "release_set_id": reserved.get("release_set_id"),
                "catalog_version": release_set.get("catalog_version"),
                "module_versions": copy.deepcopy(release_set.get("module_versions") or {}),
            }
        )
    adjudications = {
        str(event["feedback_id"]): event
        for event in records
        if event.get("event_type") == "feedback_adjudicated"
    }
    feedback: list[dict[str, Any]] = []
    for event in records:
        if event.get("event_type") != "player_feedback":
            continue
        item = copy.deepcopy(event)
        adjudicated = adjudications.get(str(event["feedback_id"]))
        if adjudicated:
            item["system_suggestion"] = {
                "module_id": adjudicated.get("system_module_id"),
                "capability_id": adjudicated.get("system_capability_id"),
                "confidence": adjudicated.get("confidence"),
                "evidence": adjudicated.get("evidence") or [],
            }
            item["adjudication"] = {
                "state": adjudicated["state"],
                "reason": adjudicated["reason"],
            }
        feedback.append(item)
    return {
        "schema_narrative_interactions": 1,
        "session": session,
        "interactions": interactions,
        "player_feedback": feedback,
    }


def _read_payload(path: Path | None) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8") if path else sys.stdin.read()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InteractionError(f"JSON de entrada inválido: {exc}") from exc
    if not isinstance(value, dict):
        raise InteractionError("entrada precisa ser objeto JSON")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("registrar", "avaliar", "adjudicar"):
        child = sub.add_parser(name)
        child.add_argument("--arquivo", type=Path)
    list_parser = sub.add_parser("listar")
    list_parser.add_argument("--sessao", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "listar":
            session = args.sessao or active_session(repo)
            if session is None:
                raise InteractionError("informe --sessao ou inicie uma sessão")
            result = materialize(repo, session)
        else:
            value = _read_payload(args.arquivo)
            if args.cmd == "registrar":
                result = record_exchange(
                    repo,
                    interaction_class=value.get("classe"),
                    input_text=value.get("entrada"),
                    response_text=value.get("resposta"),
                    client_key=value.get("chave_cliente"),
                )
            elif args.cmd == "avaliar":
                feedback = record_player_feedback(
                    repo,
                    interaction_ref=value.get("interaction_ref"),
                    original_text=value.get("texto_original"),
                    perceived_type=value.get("tipo_percebido"),
                    expectation=value.get("expectativa"),
                    observation=value.get("observacao"),
                    impact=value.get("impacto_percebido"),
                    module_id=value.get("module_id"),
                    capability_id=value.get("capability_id"),
                )
                result = {"feedback": feedback}
                if value.get("entrada") is not None or value.get("resposta") is not None:
                    if value.get("entrada") is None or value.get("resposta") is None:
                        raise InteractionError("entrada e resposta precisam ser fornecidas juntas")
                    result["interacao"] = record_exchange(
                        repo,
                        interaction_class=value.get("classe") or "OFF",
                        input_text=value.get("entrada"),
                        response_text=value.get("resposta"),
                        client_key=value.get("chave_cliente"),
                    )
            else:
                result = adjudicate_feedback(
                    repo,
                    feedback_id=value.get("feedback_id"),
                    state=value.get("estado"),
                    reason=value.get("motivo"),
                    module_id=value.get("module_id"),
                    capability_id=value.get("capability_id"),
                    confidence=value.get("confianca"),
                    evidence=value.get("evidencias"),
                )
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0
    except (InteractionError, OSError, yaml.YAMLError) as exc:
        print(f"FALHA INTERAÇÃO — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
