#!/usr/bin/env python3
"""CLI unificada do ciclo de turno: preparar -> narrar -> concluir.

A Task 21 não move semântica das portas existentes. ``cronica preparar`` chama o
endpoint determinístico de cena e devolve um ticket autocontido, assinado por
checksum, sem escrever no repositório. Depois que a narração estiver pronta,
``cronica concluir`` usa o mesmo ticket para:

1. validar a transação de turno sem escrever;
2. revalidar e confirmar a preparação de cena;
3. registrar transcrição + deltas pelo registrador transacional existente.

A confirmação ocorre antes do registro para que um checkpoint temporal disparado
pelo turno nunca envelheça a preparação que acabou de ser narrada. A transação é
pré-validada antes da primeira mutação; se uma falha rara de I/O acontecer depois
da confirmação, a CLI retorna erro parcial explícito e ``cronica registrar`` pode
reparar o registro usando a mesma transação.

``registrar`` e ``confirmar`` continuam disponíveis como portas explícitas de
reparo/uso avançado. As CLIs legadas permanecem válidas.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
import zlib
from pathlib import Path
from typing import Any

import yaml

import cena_mundo
import endpoints
import interacoes_mundo
import mundo
import recompensas
import rodape_turno
import turno

SCHEMA = 1
TICKET_PREFIX = "crn1"
MAX_TICKET_CHARS = 4096
MAX_PREP_OUTPUT_BYTES = 8192


class CronicaError(ValueError):
    """Erro de contrato/orquestração da CLI cronica."""


class PartialConclusionError(CronicaError):
    """A cena foi confirmada, mas o registro transacional falhou depois."""

    def __init__(self, message: str, *, ticket_id: str, transaction_id: str):
        super().__init__(message)
        self.ticket_id = ticket_id
        self.transaction_id = transaction_id


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CronicaError(f"{label} deve ser texto não vazio")
    return value.strip()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _b64_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64_decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        return base64.urlsafe_b64decode(value + padding)
    except Exception as exc:
        raise CronicaError("ticket cronica possui base64 inválido") from exc


def encode_ticket(payload: dict[str, Any]) -> tuple[str, str]:
    raw = _json_bytes(payload)
    digest = hashlib.sha256(raw).hexdigest()[:20]
    token = f"{TICKET_PREFIX}.{digest}.{_b64_encode(zlib.compress(raw, 9))}"
    if len(token) > MAX_TICKET_CHARS:
        raise CronicaError(
            f"ticket excede orçamento: {len(token)} > {MAX_TICKET_CHARS} caracteres"
        )
    return token, digest


def decode_ticket(token: str) -> dict[str, Any]:
    token = _text(token, "ticket")
    if len(token) > MAX_TICKET_CHARS:
        raise CronicaError("ticket cronica excede limite operacional")
    parts = token.split(".", 2)
    if len(parts) != 3 or parts[0] != TICKET_PREFIX:
        raise CronicaError("ticket cronica possui prefixo/formato inválido")
    digest = parts[1]
    if not digest or len(digest) != 20:
        raise CronicaError("ticket cronica possui checksum inválido")
    try:
        raw = zlib.decompress(_b64_decode(parts[2]))
        payload = json.loads(raw.decode("utf-8"))
    except (zlib.error, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CronicaError("ticket cronica não pôde ser decodificado") from exc
    if not isinstance(payload, dict):
        raise CronicaError("ticket cronica não contém objeto")
    if hashlib.sha256(_json_bytes(payload)).hexdigest()[:20] != digest:
        raise CronicaError("ticket cronica foi alterado ou corrompido")
    if payload.get("schema_cronica_ticket") != SCHEMA:
        raise CronicaError(f"ticket deve usar schema_cronica_ticket: {SCHEMA}")
    _text(payload.get("preparacao_id"), "ticket.preparacao_id")
    request = payload.get("cena")
    if not isinstance(request, dict):
        raise CronicaError("ticket.cena deve ser mapa")
    _text(request.get("scene_id"), "ticket.cena.scene_id")
    if not isinstance(request.get("npcs"), list) or any(
        not isinstance(item, str) for item in request["npcs"]
    ):
        raise CronicaError("ticket.cena.npcs deve ser lista de strings")
    if not isinstance(request.get("context_tags"), list) or any(
        not isinstance(item, str) for item in request["context_tags"]
    ):
        raise CronicaError("ticket.cena.context_tags deve ser lista de strings")
    now_minute = request.get("now_minute")
    if now_minute is not None and (
        not isinstance(now_minute, int) or isinstance(now_minute, bool)
    ):
        raise CronicaError("ticket.cena.now_minute deve ser inteiro ou null")
    approach = request.get("approach")
    if not isinstance(approach, dict):
        raise CronicaError("ticket.cena.approach deve ser mapa")
    expected_approach = {"preparacao", "informacao", "adequacao"}
    if set(approach) != expected_approach:
        raise CronicaError("ticket.cena.approach possui campos divergentes")
    for key, value in approach.items():
        if value is not None and not isinstance(value, str):
            raise CronicaError(f"ticket.cena.approach.{key} deve ser texto ou null")
    return payload


def ticket_id(token: str) -> str:
    parts = _text(token, "ticket").split(".", 2)
    if len(parts) != 3 or parts[0] != TICKET_PREFIX:
        raise CronicaError("ticket cronica inválido")
    return parts[1]


def _instant_arg(date: str | None, hour: str | None) -> mundo.WorldInstant | None:
    if date is None and hour is None:
        return None
    if not date or not hour:
        raise CronicaError("--data e --hora devem ser usados juntos")
    try:
        return mundo.parse_instant(date, hour)
    except mundo.WorldEngineError as exc:
        raise CronicaError(str(exc)) from exc


def _request(
    *,
    scene_id: str,
    npcs: list[str] | None,
    place: str | None,
    action: str | None,
    tier: int | None,
    danger: str | None,
    context_tags: list[str] | None,
    now: mundo.WorldInstant | None,
    approach_preparacao: str | None,
    approach_informacao: str | None,
    approach_adequacao: str | None,
) -> dict[str, Any]:
    return {
        "scene_id": scene_id,
        "npcs": list(npcs or []),
        "place": place,
        "action": action,
        "tier": tier,
        "danger": danger,
        "context_tags": list(context_tags or []),
        "now_minute": now.minute if now is not None else None,
        "approach": {
            "preparacao": approach_preparacao,
            "informacao": approach_informacao,
            "adequacao": approach_adequacao,
        },
    }


def _scene_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    request = payload["cena"]
    now_minute = request.get("now_minute")
    return {
        "scene_id": request["scene_id"],
        "npcs": list(request["npcs"]),
        "place": request.get("place"),
        "action": request.get("action"),
        "tier": request.get("tier"),
        "danger": request.get("danger"),
        "context_tags": list(request["context_tags"]),
        "now": mundo.WorldInstant(now_minute) if now_minute is not None else None,
    }


def _approach_kwargs(payload: dict[str, Any]) -> dict[str, Any]:
    approach = payload["cena"]["approach"]
    return {
        "approach_preparacao": approach.get("preparacao"),
        "approach_informacao": approach.get("informacao"),
        "approach_adequacao": approach.get("adequacao"),
    }


def prepare(
    repo: Path,
    *,
    scene_id: str,
    npcs: list[str] | None = None,
    place: str | None = None,
    action: str | None = None,
    tier: int | None = None,
    danger: str | None = None,
    context_tags: list[str] | None = None,
    now: mundo.WorldInstant | None = None,
    approach_preparacao: str | None = None,
    approach_informacao: str | None = None,
    approach_adequacao: str | None = None,
) -> dict[str, Any]:
    request = _request(
        scene_id=scene_id,
        npcs=npcs,
        place=place,
        action=action,
        tier=tier,
        danger=danger,
        context_tags=context_tags,
        now=now,
        approach_preparacao=approach_preparacao,
        approach_informacao=approach_informacao,
        approach_adequacao=approach_adequacao,
    )
    endpoint = endpoints.scene(
        repo,
        scene_id=scene_id,
        npcs=npcs,
        place=place,
        action=action,
        tier=tier,
        danger=danger,
        context_tags=context_tags,
        now=now,
        approach_preparacao=approach_preparacao,
        approach_informacao=approach_informacao,
        approach_adequacao=approach_adequacao,
    )
    preparation_id = endpoint.get("ids", {}).get("preparacao")
    preparation_id = _text(preparation_id, "endpoint.ids.preparacao")
    token, digest = encode_ticket(
        {
            "schema_cronica_ticket": SCHEMA,
            "preparacao_id": preparation_id,
            "cena": request,
        }
    )
    result = {
        "schema_cronica_turno": SCHEMA,
        "fase": "preparacao",
        "ticket_id": digest,
        "ticket": token,
        "ids": endpoint["ids"],
        "filtros": endpoint["filtros"],
        "disponibilidade": endpoint["disponibilidade"],
        "gates": endpoint["gates"],
        "modificadores": endpoint["modificadores"],
        "proximo_passo": {
            "acao": "narrar_e_concluir",
            "comando": "cronica concluir --ticket <ticket>",
            "entrada": "JSON da transação via stdin ou --arquivo",
        },
        "fontes_lidas": endpoint["fontes_lidas"],
    }
    size = len(yaml.safe_dump(result, allow_unicode=True, sort_keys=False).encode("utf-8"))
    if size > MAX_PREP_OUTPUT_BYTES:
        raise CronicaError(
            f"preparação cronica excede orçamento: {size} > {MAX_PREP_OUTPUT_BYTES} bytes"
        )
    return result


def _preflight_registration(repo: Path, transaction: dict[str, Any]) -> dict[str, Any]:
    """Executa as validações mutantes do turno até imediatamente antes das escritas."""
    normalized, session = turno.normalize_transaction(repo, transaction)
    record = turno.build_pending_record(normalized, session)
    transaction_id = record["id"]
    transcript_path = repo / "sessoes" / f"{session:03d}" / "transcricao.md"
    pending_path = repo / turno.PENDING_PATH
    if not transcript_path.is_file():
        raise turno.TransactionError(
            f"transcrição da sessão não existe: {transcript_path.relative_to(repo)}"
        )
    if not pending_path.exists():
        raise turno.TransactionError(f"arquivo pendente não existe: {turno.PENDING_PATH}")

    transcript = transcript_path.read_text(encoding="utf-8")
    pending_text = pending_path.read_text(encoding="utf-8")
    marker = turno.transaction_marker(transaction_id)
    marker_count = transcript.count(marker)
    if marker_count > 1:
        raise turno.TransactionError(
            f"marcador transacional duplicado na transcrição: {transaction_id}"
        )

    existing_records = turno.load_pending(repo)
    by_id = {item["id"]: item for item in existing_records}
    existing_record = by_id.get(transaction_id)
    if (
        existing_record is not None
        and turno.record_fingerprint(existing_record) != turno.record_fingerprint(record)
    ):
        raise turno.TransactionError(
            f"id {transaction_id} já existe com conteúdo diferente; não sobrescrever silenciosamente"
        )

    consolidated = False
    if marker_count == 1 and existing_record is None:
        consolidated = turno._transaction_in_ledger(repo, session, transaction_id)
    need_transcript = marker_count == 0
    need_pending = existing_record is None and not consolidated
    retry = not (need_transcript and need_pending)
    authorization = turno.barreira_mundo.authorize_registration(
        repo,
        normalized,
        retry=retry,
    )

    prior_records = [item for item in existing_records if item.get("id") != transaction_id]
    temporal_trigger = None if consolidated else turno.detect_world_checkpoint(
        repo,
        prior_records,
        record,
    )
    if need_pending:
        candidate = turno._append_jsonl(pending_text, record)
        if len(candidate.encode("utf-8")) > turno.MAX_PENDING_BYTES:
            raise turno.TransactionError(
                f"{turno.PENDING_PATH} excederia {turno.MAX_PENDING_BYTES} bytes; consolidar antes de continuar"
            )

    return {
        "id": transaction_id,
        "sessao": session,
        "normalizada": normalized,
        "registro_novo": need_transcript or need_pending,
        "retry": retry,
        "consolidada": consolidated,
        "pendencia_mundo": authorization.get("pendencia_resolvida"),
        "checkpoint_previsto": (
            temporal_trigger.get("motivo") if isinstance(temporal_trigger, dict) else None
        ),
    }


def _revalidate_ticket(repo: Path, payload: dict[str, Any]) -> dict[str, Any]:
    fresh = cena_mundo.prepare_scene(repo, **_scene_kwargs(payload))
    expected = payload["preparacao_id"]
    if fresh.get("preparacao_id") != expected:
        raise CronicaError(
            "preparação do ticket ficou obsoleta; execute `cronica preparar` novamente"
        )
    return fresh


def confirm(repo: Path, token: str) -> dict[str, Any]:
    payload = decode_ticket(token)
    committed = cena_mundo.confirm_scene(
        repo,
        preparation_id=payload["preparacao_id"],
        **_scene_kwargs(payload),
    )
    return {
        "schema_cronica_turno": SCHEMA,
        "fase": "confirmacao",
        "ticket_id": ticket_id(token),
        "cena_id": committed.get("cena_id"),
        "preparacao_id": committed.get("preparacao_id"),
        "mutacoes_aplicadas": bool(committed.get("mutacoes_aplicadas")),
        "resumo": committed.get("resumo") or {},
        "fontes_lidas": committed.get("fontes_lidas") or [],
        "proximo_passo": {
            "acao": "registrar_turno",
            "comando": "cronica registrar --ticket <ticket>",
        },
    }


def register(repo: Path, token: str, transaction: dict[str, Any], *, revalidate: bool = True) -> dict[str, Any]:
    payload = decode_ticket(token)
    if revalidate:
        _revalidate_ticket(repo, payload)
    result = turno.register_transaction(repo, transaction)
    return {
        "schema_cronica_turno": SCHEMA,
        "fase": "registro",
        "ticket_id": ticket_id(token),
        "preparacao_id": payload["preparacao_id"],
        "transacao": {
            "id": result["id"],
            "sessao": result["sessao"],
            "deltas": result["deltas"],
            "transcricao_escrita": result["transcricao_escrita"],
            "evento_escrito": result["evento_escrito"],
            "reparo_parcial": result["reparo_parcial"],
            "ja_registrada": result["ja_registrada"],
            "consolidada": result["consolidada"],
        },
        "checkpoint_mundo": result.get("checkpoint_mundo"),
        "avisos": result.get("avisos") or [],
        "confirmacao_pendente": True,
        "rodape_canonico": rodape_turno.build_safe(repo),
        "proximo_passo": {
            "acao": "confirmar_preparacao",
            "comando": "cronica confirmar --ticket <ticket>",
        },
    }


def conclude(repo: Path, token: str, transaction: dict[str, Any]) -> dict[str, Any]:
    payload = decode_ticket(token)
    preview = _preflight_registration(repo, transaction)

    # confirm_scene revalida o fingerprint e só então aplica a cena. Como o
    # registro ainda não ocorreu, checkpoint temporal nenhum pode envelhecer o ticket.
    committed = cena_mundo.confirm_scene(
        repo,
        preparation_id=payload["preparacao_id"],
        **_scene_kwargs(payload),
    )
    try:
        registered = turno.register_transaction(repo, transaction)
    except Exception as exc:
        raise PartialConclusionError(
            "cena confirmada, mas o registrador transacional falhou; repare com "
            "`cronica registrar --ticket <ticket> --reparo-pos-confirmacao` usando a mesma transação",
            ticket_id=ticket_id(token),
            transaction_id=preview["id"],
        ) from exc

    return {
        "schema_cronica_turno": SCHEMA,
        "fase": "concluida",
        "ticket_id": ticket_id(token),
        "cena": {
            "id": committed.get("cena_id"),
            "preparacao_id": committed.get("preparacao_id"),
            "confirmada": bool(committed.get("mutacoes_aplicadas")),
            "resumo": committed.get("resumo") or {},
        },
        "transacao": {
            "id": registered["id"],
            "sessao": registered["sessao"],
            "deltas": registered["deltas"],
            "transcricao_escrita": registered["transcricao_escrita"],
            "evento_escrito": registered["evento_escrito"],
            "reparo_parcial": registered["reparo_parcial"],
            "ja_registrada": registered["ja_registrada"],
            "consolidada": registered["consolidada"],
        },
        "checkpoint_previsto_no_preflight": preview.get("checkpoint_previsto"),
        "checkpoint_mundo": registered.get("checkpoint_mundo"),
        "avisos": registered.get("avisos") or [],
        "rodape_canonico": rodape_turno.build_safe(repo),
        "proximo_passo": {"acao": "continuar_narracao_ou_checkpoint_quando_necessario"},
    }


def _add_scene_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cena-id", required=True)
    parser.add_argument("--npc", action="append", default=[])
    parser.add_argument("--contexto-tag", action="append", default=[])
    parser.add_argument("--local")
    parser.add_argument("--acao", choices=sorted(interacoes_mundo.VALID_LOCAL_ACTIONS))
    parser.add_argument("--tier", type=int)
    parser.add_argument("--periculosidade", choices=sorted(recompensas.VALID_DANGER))
    parser.add_argument("--data")
    parser.add_argument("--hora")
    parser.add_argument("--abordagem-preparacao")
    parser.add_argument("--abordagem-informacao")
    parser.add_argument("--abordagem-adequacao")


def _add_transaction_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--ticket", required=True)
    parser.add_argument("--arquivo", type=Path, help="JSON da transação; sem opção, lê stdin")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)

    prepare_parser = sub.add_parser("preparar", help="prepara cena e emite ticket read-only")
    _add_scene_args(prepare_parser)

    conclude_parser = sub.add_parser(
        "concluir",
        help="confirma cena + registra turno em uma única chamada pós-narração",
    )
    _add_transaction_args(conclude_parser)

    register_parser = sub.add_parser(
        "registrar",
        help="porta explícita de registro; normalmente use concluir",
    )
    _add_transaction_args(register_parser)
    register_parser.add_argument(
        "--reparo-pos-confirmacao",
        action="store_true",
        help="não revalida a cena; use somente se concluir informou falha parcial após confirmação",
    )

    confirm_parser = sub.add_parser(
        "confirmar",
        help="porta explícita de confirmação; normalmente use concluir",
    )
    confirm_parser.add_argument("--ticket", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "preparar":
            result = prepare(
                repo,
                scene_id=args.cena_id,
                npcs=args.npc,
                place=args.local,
                action=args.acao,
                tier=args.tier,
                danger=args.periculosidade,
                context_tags=args.contexto_tag,
                now=_instant_arg(args.data, args.hora),
                approach_preparacao=args.abordagem_preparacao,
                approach_informacao=args.abordagem_informacao,
                approach_adequacao=args.abordagem_adequacao,
            )
        elif args.cmd == "concluir":
            result = conclude(repo, args.ticket, turno.read_transaction(args.arquivo))
        elif args.cmd == "registrar":
            result = register(
                repo,
                args.ticket,
                turno.read_transaction(args.arquivo),
                revalidate=not args.reparo_pos_confirmacao,
            )
        else:
            result = confirm(repo, args.ticket)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0
    except PartialConclusionError as exc:
        print(
            yaml.safe_dump(
                {
                    "schema_cronica_turno": SCHEMA,
                    "fase": "falha_parcial",
                    "ticket_id": exc.ticket_id,
                    "transacao_id": exc.transaction_id,
                    "cena_confirmada": True,
                    "turno_registrado": False,
                    "erro": str(exc),
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            file=sys.stderr,
            end="",
        )
        return 3
    except (
        CronicaError,
        cena_mundo.SceneGateError,
        endpoints.EndpointError,
        interacoes_mundo.IntegrationError,
        mundo.WorldEngineError,
        recompensas.RewardMapError,
        turno.TransactionError,
        turno.barreira_mundo.WorldPendingBarrierError,
        OSError,
        yaml.YAMLError,
    ) as exc:
        print(f"FALHA CRONICA — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
