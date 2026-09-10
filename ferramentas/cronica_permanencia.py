#!/usr/bin/env python3
"""Composição NV-15 da porta ``cronica`` sem duplicar o orquestrador existente.

O arquivo ``_cronica_nv14.py`` conserva integralmente o orquestrador anterior.
Esta borda acrescenta somente ``--permanencia-local`` ao preparar e um ticket
espacial especializado. Fora desse modo, todas as chamadas são delegadas byte a
byte às funções anteriores.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
from pathlib import Path
from typing import Any

import _cronica_nv14 as _base
import permanencia_espacial as _stay

_core = _base._core
_hot = _base._hot

STAY_PREFIX = "turn-stay-"
STAY_KEY = "permanencia_espacial"

_BASE_BUILD_PARSER = _base.build_parser
_BASE_RUN_TURN = _base._run_turn
_HOT_PREPARE = _hot.prepare
_HOT_REVALIDATE = _hot.revalidate
_HOT_CONFIRM = _hot.confirm
_HOT_REGISTER = _hot.register
_HOT_CONCLUDE = _hot.conclude
_HOT_TRANSACTION_CONTRACT = _hot._transaction_contract


# O digest do ticket congela a avaliação (local/data/período + produtores), não
# seu status posterior. Assim uma repetição do mesmo concluir continua válida
# depois que a decisão idempotente já foi instalada.
def _stable_record_digest(record: dict[str, Any]) -> str:
    value = copy.deepcopy(record)
    value.pop("digest", None)
    value.pop("estado", None)
    value.pop("decisao", None)
    return _stay._digest(value)


_stay._record_digest = _stable_record_digest


def _stay_preparation_id(request: dict[str, Any], meta: dict[str, Any]) -> str:
    raw = _core._json_bytes({"tipo": "permanencia_espacial", "cena": request, STAY_KEY: meta})
    return STAY_PREFIX + hashlib.sha256(raw).hexdigest()[:20]


def _stay_meta(payload: dict[str, Any]) -> dict[str, Any] | None:
    raw = payload.get(STAY_KEY)
    if raw is None:
        return None
    try:
        normalized = _stay.validate_ticket(raw)
    except _stay.SpatialPermanenceError as exc:
        raise _core.CronicaError(f"NV15: {exc}") from exc
    return {"schema": _stay.SCHEMA, **normalized}


def _is_stay_payload(payload: dict[str, Any]) -> bool:
    preparation_id = str(payload.get("preparacao_id") or "")
    meta = _stay_meta(payload)
    if not preparation_id.startswith(STAY_PREFIX):
        if meta is not None:
            raise _core.CronicaError("ticket de permanência possui prefixo divergente")
        return False
    if meta is None:
        raise _core.CronicaError("ticket de permanência perdeu seus metadados")
    request = payload.get("cena")
    if not isinstance(request, dict):
        raise _core.CronicaError("ticket de permanência perdeu a cena")
    if request.get("place") != meta["local_id"]:
        raise _core.CronicaError("ticket de permanência perdeu o local canônico congelado")
    if request.get("npcs") or request.get("context_tags"):
        raise _core.CronicaError(
            "permanência espacial não pode fabricar elenco/tag de cena; use --participante para memória do elenco"
        )
    if any(request.get(key) is not None for key in ("action", "tier", "danger")):
        raise _core.CronicaError("ticket de permanência contém gatilho local de entrada/exploração")
    expected = _stay_preparation_id(request, payload[STAY_KEY])
    if expected != preparation_id:
        raise _core.CronicaError("ticket de permanência possui preparação divergente")
    return True


def _transaction_contract() -> dict[str, Any]:
    contract = _HOT_TRANSACTION_CONTRACT()
    contract["permanencia_espacial_nv15"] = (
        "Se permanencia_espacial.exige_decisao_conclusao=true, incluir na transação "
        "permanencia_espacial={avaliacao_id,resultado,evidencia_literal|motivo}. "
        "resultado é resolvida, adiada ou invalidada. Calma espacial não aceita bloco fabricado."
    )
    return contract


def _stay_gate(public: dict[str, Any]) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = [
        {
            "tipo": "permanencia_espacial",
            "resultado": "pressao_espacial" if public.get("pressao_primaria") else "calma_espacial",
            "avaliacao_id": public["avaliacao_id"],
            "local_id": public["local_id"],
            "data": public["data"],
            "periodo": public["periodo"],
            "reutilizado": bool(public.get("reutilizado")),
        }
    ]
    micro = public.get("microevento_local") or {}
    gates.append({"tipo": "microevento_local", "resultado": micro.get("resultado", "rotina")})
    incident = public.get("incidente_local") or {}
    gates.append({"tipo": "incidente_local", "resultado": incident.get("resultado", "rotina")})
    presence = public.get("presenca_incidental") or {}
    gates.append({"tipo": "presenca_incidental", "resultado": presence.get("resultado", "nenhuma_presenca_incidental")})
    gates.append(
        {
            "tipo": "condicoes_ambientais",
            "resultado": "consultadas",
            "ativas": len(public.get("condicoes_ambientais") or []),
        }
    )
    return gates


def _hot_prepare(
    repo: Path,
    *,
    scene_id: str,
    npcs: list[str] | None = None,
    place: str | None = None,
    action: str | None = None,
    tier: int | None = None,
    danger: str | None = None,
    context_tags: list[str] | None = None,
    now=None,
    approach_preparacao: str | None = None,
    approach_informacao: str | None = None,
    approach_adequacao: str | None = None,
    urban_transit: str | None = None,
    permanence_local: bool = False,
) -> dict[str, Any]:
    if not permanence_local:
        return _HOT_PREPARE(
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
            urban_transit=urban_transit,
        )
    if urban_transit is not None:
        raise _core.CronicaError("--permanencia-local e --transito-urbano são mutuamente exclusivos")
    if npcs or context_tags or action is not None or tier is not None or danger is not None:
        raise _core.CronicaError(
            "--permanencia-local aceita apenas --local opcional; não combine com --npc, --contexto-tag, "
            "--acao, --tier ou --periculosidade. Elenco conhecido usa --participante."
        )
    try:
        planned = _stay.prepare(Path(repo), scene_id=scene_id, place=place, now=now)
    except _stay.SpatialPermanenceError as exc:
        raise _core.CronicaError(f"NV15: {exc}") from exc
    public = planned["publico"]
    meta = planned["ticket"]
    request = _core._request(
        scene_id=scene_id,
        npcs=[],
        place=public["local_id"],
        action=None,
        tier=None,
        danger=None,
        context_tags=[],
        now=now,
        approach_preparacao=approach_preparacao,
        approach_informacao=approach_informacao,
        approach_adequacao=approach_adequacao,
    )
    preparation_id = _stay_preparation_id(request, meta)
    token, digest = _core.encode_ticket(
        {
            "schema_cronica_ticket": _core.SCHEMA,
            "preparacao_id": preparation_id,
            "cena": request,
            STAY_KEY: meta,
        }
    )
    filters, modifiers = _hot._quality_modifier(request)
    if "permanencia_espacial_nv15" not in filters:
        filters.insert(0, "permanencia_espacial_nv15")
    result = {
        "schema_cronica_turno": _core.SCHEMA,
        "fase": "preparacao",
        "ticket_id": digest,
        "ticket": token,
        "ids": {
            "cena": scene_id,
            "preparacao": preparation_id,
            "local": public["local_id"],
            "npcs": [],
            "encontros": [],
            "sidequests_potenciais": [],
            "presencas_contextuais": [item.get("id") for item in (public.get("presenca_incidental") or {}).get("candidatos", [])],
            "entradas_contextuais": [],
            "operacoes_contextuais": [],
            "direcoes_contextuais": [],
            "candidatos_contextuais": [item["id"] for item in public.get("candidatos") or []],
            "permanencia_espacial": public["avaliacao_id"],
        },
        "filtros": filters,
        "disponibilidade": {
            "conclusao": True,
            "confirmacao_reativa": False,
            "permanencia_espacial": True,
        },
        "gates": _stay_gate(public),
        "modificadores": modifiers,
        STAY_KEY: public,
        "fontes_lidas": list(public.get("fontes_lidas") or []),
        "proximo_passo": {},
    }
    decorated = _hot._decorate(result, reactive=False)
    decorated["reativa_espacial"] = True
    return decorated


def _hot_revalidate(repo: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if not _is_stay_payload(payload):
        return _HOT_REVALIDATE(repo, payload)
    try:
        public = _stay.revalidate(Path(repo), payload[STAY_KEY])
    except _stay.SpatialPermanenceError as exc:
        raise _core.CronicaError(f"NV15: {exc}") from exc
    return {
        "preparacao_id": payload["preparacao_id"],
        "reativa": False,
        "reativa_espacial": True,
        STAY_KEY: public,
    }


def _hot_confirm(repo: Path, token: str) -> dict[str, Any]:
    payload = _core.decode_ticket(token)
    if not _is_stay_payload(payload):
        return _HOT_CONFIRM(repo, token)
    validated = _hot_revalidate(repo, payload)
    return {
        "schema_cronica_turno": _core.SCHEMA,
        "fase": "confirmacao",
        "ticket_id": _core.ticket_id(token),
        "cena_id": payload["cena"]["scene_id"],
        "preparacao_id": payload["preparacao_id"],
        "mutacoes_aplicadas": False,
        "reativa": False,
        "reativa_espacial": True,
        STAY_KEY: validated[STAY_KEY],
        "proximo_passo": {"acao": "registrar_turno"},
    }


def _stay_decision(repo: Path, payload: dict[str, Any], transaction: dict[str, Any]):
    try:
        return _stay.prepare_conclusion(Path(repo), payload[STAY_KEY], transaction)
    except _stay.SpatialPermanenceError as exc:
        raise _core.CronicaError(f"NV15: {exc}") from exc


def _install_stay(repo: Path, payload: dict[str, Any], decision):
    try:
        return _stay.install_conclusion(Path(repo), payload[STAY_KEY], decision)
    except _stay.SpatialPermanenceError as exc:
        raise _core.CronicaError(f"NV15: {exc}") from exc


def _hot_register(
    repo: Path,
    token: str,
    transaction: dict[str, Any],
    *,
    revalidate_ticket: bool = True,
) -> dict[str, Any]:
    payload = _core.decode_ticket(token)
    if not _is_stay_payload(payload):
        return _HOT_REGISTER(repo, token, transaction, revalidate_ticket=revalidate_ticket)
    if revalidate_ticket:
        _hot_revalidate(repo, payload)
    decision = _stay_decision(repo, payload, transaction)
    registered = _hot.turno.register_transaction(repo, transaction)
    installed = _install_stay(repo, payload, decision)
    result = _hot._registered_result(repo, token, payload, registered)
    result["reativa_espacial"] = True
    result[STAY_KEY] = installed or _stay.revalidate(Path(repo), payload[STAY_KEY])
    return result


def _hot_conclude(
    repo: Path,
    token: str,
    transaction: dict[str, Any],
    *,
    preflight=None,
) -> dict[str, Any]:
    payload = _core.decode_ticket(token)
    if not _is_stay_payload(payload):
        return _HOT_CONCLUDE(repo, token, transaction, preflight=preflight)
    preview = (preflight or _core._preflight_registration)(repo, transaction)
    decision = _stay_decision(repo, payload, transaction)
    registered = _hot.turno.register_transaction(repo, transaction)
    try:
        installed = _install_stay(repo, payload, decision)
    except Exception as exc:
        raise _core.PartialConclusionError(
            "turno de permanência foi registrado, mas o recibo espacial não foi concluído; "
            "repita o mesmo cronica concluir para reparo idempotente",
            ticket_id=_core.ticket_id(token),
            transaction_id=preview["id"],
        ) from exc
    return {
        "schema_cronica_turno": _core.SCHEMA,
        "fase": "concluida",
        "ticket_id": _core.ticket_id(token),
        "reativa": False,
        "reativa_espacial": True,
        "cena": {
            "id": payload["cena"]["scene_id"],
            "preparacao_id": payload["preparacao_id"],
            "local_id": payload[STAY_KEY]["local_id"],
            "confirmada": False,
            "resumo": {},
        },
        STAY_KEY: installed or _stay.revalidate(Path(repo), payload[STAY_KEY]),
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
        "rodape_canonico": _hot.rodape_turno.build_safe(repo),
        "proximo_passo": {"acao": "continuar_narracao_ou_checkpoint_quando_necessario"},
    }


def build_parser() -> argparse.ArgumentParser:
    parser = _BASE_BUILD_PARSER()
    root = _base._subparsers(parser)
    prepare = root.choices["preparar"]
    prepare.add_argument(
        "--permanencia-local",
        action="store_true",
        help=(
            "avalia permanência longa no local atual consolidado; --local é opcional e, "
            "quando fornecido, precisa coincidir com o local atual"
        ),
    )
    return parser


def _run_turn(repo: Path, args: argparse.Namespace):
    if args.cmd != "preparar":
        return _BASE_RUN_TURN(repo, args)
    return _base.prepare(
        repo,
        scene_id=args.cena_id,
        npcs=args.npc,
        place=args.local,
        action=args.acao,
        tier=args.tier,
        danger=args.periculosidade,
        context_tags=args.contexto_tag,
        now=_base._instant_arg(args.data, args.hora),
        approach_preparacao=args.abordagem_preparacao,
        approach_informacao=args.abordagem_informacao,
        approach_adequacao=args.abordagem_adequacao,
        urban_transit=getattr(args, "transito_urbano", None),
        permanence_local=bool(getattr(args, "permanencia_local", False)),
        memory_participants=([] if args.sem_participantes else args.participante),
        memory_base_in_context=args.memoria_base_em_contexto,
        mechanical_spec=_base._mechanical_spec_from_args(args),
        sidequest_signal=_base._sidequest_signal_from_args(args),
    )


_hot._transaction_contract = _transaction_contract
_hot.prepare = _hot_prepare
_hot.revalidate = _hot_revalidate
_hot.confirm = _hot_confirm
_hot.register = _hot_register
_hot.conclude = _hot_conclude
_base.build_parser = build_parser
_base._run_turn = _run_turn

for _name in dir(_base):
    if not _name.startswith("__") and _name not in globals():
        globals()[_name] = getattr(_base, _name)

main = _base.main

if __name__ == "__main__":
    raise SystemExit(main())
