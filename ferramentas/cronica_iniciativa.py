#!/usr/bin/env python3
"""Composição NV-16 da porta ``cronica``.

Tickets sem interlocutores delegam ao fluxo pós-NV-15. A extensão usa a mesma
memória de cena, congela a decisão no ticket e persiste somente um recibo
reservado depois do writer base concluir com sucesso.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cronica_permanencia as _prev
import npc_continuity_and_social_behavior as _npc_continuity

_base = _prev._base
_core = _base._core

_BASE_PREPARE = _base.prepare
_BASE_CONCLUDE = _base.conclude
_BASE_CONFIRM = _base.confirm
_BASE_REGISTER = _base.register
_BASE_BUILD_PARSER = _base.build_parser
_BASE_RUN_TURN = _base._run_turn
_UNSET = object()


def prepare(*args, **kwargs):
    requested = kwargs.pop("initiative_interlocutors", _UNSET)
    if requested is _UNSET:
        return _BASE_PREPARE(*args, **kwargs)
    with _npc_continuity.interlocutors(requested):
        return _BASE_PREPARE(*args, **kwargs)


def _meta(token: str):
    payload = _base.decode_ticket(token)
    try:
        return payload, _npc_continuity.initiative_ticket_meta(payload)
    except _npc_continuity.CastInitiativeError as exc:
        raise _core.CronicaError(f"NV16: {exc}") from exc


def conclude(repo: Path, token: str, transaction: dict):
    payload, meta = _meta(token)
    if meta is None:
        if _npc_continuity.INITIATIVE_TRANSACTION_KEY in transaction:
            raise _core.CronicaError("NV16: iniciativa_elenco exige autorização no ticket")
        return _BASE_CONCLUDE(repo, token, transaction)
    try:
        plan = _npc_continuity.prepare_initiative_conclusion(
            Path(repo), meta, transaction
        )
    except _npc_continuity.CastInitiativeError as exc:
        raise _core.CronicaError(f"NV16: {exc}") from exc
    clean_payload = _npc_continuity.strip_initiative_ticket_payload(payload)
    base_token, _ = _core.encode_ticket(clean_payload)
    _, outer_ticket_id = _core.encode_ticket(payload)
    writer_tx = _npc_continuity.initiative_writer_transaction(transaction)
    result = _BASE_CONCLUDE(repo, base_token, writer_tx)
    transaction_id = str((result.get("transacao") or {}).get("id") or "")
    if not transaction_id:
        raise _core.PartialConclusionError(
            "NV16: turno base concluiu sem ID de transação; repita o mesmo cronica concluir",
            ticket_id=outer_ticket_id,
            transaction_id="desconhecida",
        )
    try:
        installed = _npc_continuity.install_initiative_conclusion(
            Path(repo), meta, plan, ticket_id=outer_ticket_id, transaction_id=transaction_id
        )
    except _npc_continuity.CastInitiativeError as exc:
        raise _core.PartialConclusionError(
            "NV16: turno foi registrado, mas o recibo de iniciativa não foi instalado; "
            "repita o mesmo cronica concluir para reparo idempotente",
            ticket_id=outer_ticket_id,
            transaction_id=transaction_id,
        ) from exc
    result["ticket_id"] = outer_ticket_id
    result[_npc_continuity.INITIATIVE_PUBLIC_KEY] = installed
    systems = result.setdefault("sistemas_narrativos", [])
    if "npc_social_initiative" not in systems:
        systems.append("npc_social_initiative")
    if _npc_continuity.MODULE_ID not in systems:
        systems.append(_npc_continuity.MODULE_ID)
    return result


def confirm(repo: Path, token: str):
    _, meta = _meta(token)
    if meta is not None:
        raise _core.CronicaError(
            "NV16: ticket com interlocutores usa cronica concluir; não separar confirmação e registro"
        )
    return _BASE_CONFIRM(repo, token)


def register(repo: Path, token: str, transaction: dict, *, revalidate: bool = True):
    _, meta = _meta(token)
    if meta is not None or _npc_continuity.INITIATIVE_TRANSACTION_KEY in transaction:
        raise _core.CronicaError(
            "NV16: decisão de iniciativa usa cronica concluir; registrar isolado perderia o recibo"
        )
    return _BASE_REGISTER(repo, token, transaction, revalidate=revalidate)


def build_parser() -> argparse.ArgumentParser:
    parser = _BASE_BUILD_PARSER()
    root = _base._subparsers(parser)
    prepare_parser = root.choices["preparar"]
    prepare_parser.add_argument(
        "--interlocutor",
        action="append",
        help=(
            "ID canônico de NPC que deve receber decisão explícita de iniciativa; repetir para subconjunto do elenco/contactáveis"
        ),
    )
    return parser


def _run_turn(repo: Path, args: argparse.Namespace):
    if args.cmd != "preparar":
        return _BASE_RUN_TURN(repo, args)
    with _npc_continuity.interlocutors(getattr(args, "interlocutor", None)):
        return _BASE_RUN_TURN(repo, args)


_base.prepare = prepare
_base.conclude = conclude
_base.confirm = confirm
_base.register = register
_base.build_parser = build_parser
_base._run_turn = _run_turn
_base._npc_continuity = _npc_continuity
_base._initiative16 = _npc_continuity
_base._initiative16_conclusion = _npc_continuity
_base._memory16 = _npc_continuity

for _name in dir(_prev):
    if not _name.startswith("__") and not hasattr(_base, _name):
        setattr(_base, _name, getattr(_prev, _name))

main = _base.main

if __name__ == "__main__":
    raise SystemExit(main())
