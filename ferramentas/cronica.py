#!/usr/bin/env python3
"""CLI operacional unificada de turno, sessão e progressão.

A Task 21 permanece preservada em ``_cronica_turn_core.py`` e a Task 22 em
``ciclo_cronica.py``. A camada pública acrescenta ergonomia observada em rollout
real: turno neutro sem gatilho inventado, trânsito urbano no mesmo hot path,
retomada compacta limpa, transporte de ticket tolerante a whitespace acidental,
gate read-only de pendências, contratos operacionais tolerantes a aliases
inequívocos, sidequests emergentes Task46, a decisão explícita Task47 e a
reavaliação read-only de sidequests aceitas Task48 antes de todo
``cronica preparar``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

import _cronica_turn_core as _core
import checkpoint
import ciclo_cronica
import ciclo_sessoes
import consolidar
import contratos_operacionais as _contracts
import cronica_hotpath as _hot
import cronica_pending_gate as _pending_gate
import mecanica_cronica as _mechanics
import progressao_juppongatana
import retomada_cronica
import sessoes
import sidequests_ativas as _sidequests48
import sidequests_integracao_runtime as _sidequests46
import transacoes

for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

_ORIGINAL_BUILD_PARSER = _core.build_parser
_ORIGINAL_MAIN = _core.main
_ORIGINAL_B64_DECODE = _core._b64_decode
_ORIGINAL_DECODE_TICKET = _core.decode_ticket
_ORIGINAL_INSTANT_ARG = _core._instant_arg
_ORIGINAL_TRANSACTION_CONTRACT = _hot._transaction_contract
_SIDEQUEST_DECISION_UNSET = object()


def _b64_decode(value: str) -> bytes:
    compact = "".join(value.split())
    return _ORIGINAL_B64_DECODE(compact)


def _ticket_argument(value: str) -> str:
    try:
        return _contracts.explain_ticket_argument(value)
    except _contracts.OperationalContractError as exc:
        raise _core.CronicaError(str(exc)) from exc


def decode_ticket(value: str) -> dict:
    return _ORIGINAL_DECODE_TICKET(_ticket_argument(value))


def _instant_arg(date: str | None, hour: str | None):
    if date is None and hour is None:
        return None
    if not date or not hour:
        raise _core.CronicaError("--data e --hora devem ser usados juntos")
    try:
        normalized = _contracts.normalize_date(date)
    except _contracts.OperationalContractError as exc:
        raise _core.CronicaError(str(exc)) from exc
    return _ORIGINAL_INSTANT_ARG(normalized, hour)


def _transaction_contract() -> dict:
    contract = _ORIGINAL_TRANSACTION_CONTRACT()
    contract["disciplina"] = (
        "Em --ticket use exatamente o campo `ticket:` completo, nunca `ticket_id`. "
        "Não chamar --help nem ler implementação para redescobrir este contrato."
    )
    contract["sidequest_emergente_task46"] = (
        "Somente em ticket preparado com --oportunidade-sidequest, a transação pode "
        "conter sidequest_emergente com oferta+quest+contratos Task43/44/45. "
        "Sem oferta literal narrada, omita o bloco inteiro."
    )
    return contract


_core._b64_decode = _b64_decode
_core.decode_ticket = decode_ticket
_hot._transaction_contract = _transaction_contract


def prepare(*args, **kwargs):
    repo = args[0] if args else kwargs.get("repo")
    if repo is None:
        raise _core.CronicaError("cronica preparar exige raiz do repositório")
    signal = kwargs.pop("sidequest_signal", _SIDEQUEST_DECISION_UNSET)
    mechanical_spec = kwargs.pop("mechanical_spec", None)
    if signal is _SIDEQUEST_DECISION_UNSET:
        raise _core.CronicaError(
            "Task47: cronica preparar exige decisão explícita de oportunidade de sidequest; "
            "use sidequest_signal=None para descartar ou forneça a âncora causal"
        )
    gate = _pending_gate.prepare_gate(Path(repo))
    if gate is not None:
        return gate
    base = _hot.prepare(*args, **kwargs)
    if signal is None:
        prepared = base
    else:
        try:
            prepared = _sidequests46.integrate_prepare(
                Path(repo),
                base,
                signal_raw=signal,
                decode_ticket=decode_ticket,
                encode_ticket=_core.encode_ticket,
                now=kwargs.get("now"),
            )
        except _sidequests46.EmergentSidequestIntegrationError as exc:
            raise _core.CronicaError(str(exc)) from exc
    try:
        prepared = _sidequests48.integrate_prepare(
            Path(repo),
            prepared,
            decode_ticket=decode_ticket,
            encode_ticket=_core.encode_ticket,
        )
    except _sidequests48.ActiveSidequestError as exc:
        raise _core.CronicaError(f"Task48: {exc}") from exc
    try:
        output_budget = (
            _sidequests46.MAX_COMBINED_PREP_BYTES
            if "sidequest_emergente" in prepared or "sidequests_ativas" in prepared
            else _core.MAX_PREP_OUTPUT_BYTES
        )
        return _mechanics.attach_to_prepare(
            Path(repo),
            prepared,
            mechanical_spec,
            decode_ticket=decode_ticket,
            encode_ticket=_core.encode_ticket,
            max_ticket_chars=_core.MAX_TICKET_CHARS,
            max_output_bytes=output_budget,
        )
    except _mechanics.MechanicalContractError as exc:
        raise _core.CronicaError(str(exc)) from exc


def _task46_meta(token: str) -> tuple[dict, dict | None]:
    payload = decode_ticket(token)
    try:
        _sidequests48.ticket_meta(payload)
        return payload, _sidequests46.ticket_meta(payload)
    except (
        _sidequests46.EmergentSidequestIntegrationError,
        _sidequests48.ActiveSidequestError,
    ) as exc:
        raise _core.CronicaError(str(exc)) from exc


def _base_token(payload: dict) -> str:
    token, _ = _core.encode_ticket(_sidequests46.strip_ticket_payload(payload))
    return token


def confirm(repo: Path, token: str):
    _, meta = _task46_meta(token)
    if meta is not None:
        raise _core.CronicaError(
            "ticket Task46 usa a porta transacional cronica concluir; não separe confirmar/registrar"
        )
    return _hot.confirm(repo, token)


def _conclude_base(repo: Path, token: str, transaction: dict):
    original = _core._preflight_registration
    _core._preflight_registration = globals()["_preflight_registration"]
    try:
        return _hot.conclude(
            repo,
            token,
            transaction,
            preflight=globals()["_preflight_registration"],
        )
    finally:
        _core._preflight_registration = original


def conclude(repo: Path, token: str, transaction: dict):
    payload, meta = _task46_meta(token)
    try:
        mechanical_writer_tx = _mechanics.validate_transaction(repo, payload, transaction)
    except _mechanics.MechanicalContractError as exc:
        raise _core.CronicaError(str(exc)) from exc
    if meta is None:
        return _conclude_base(repo, token, mechanical_writer_tx)

    ticket_id_original = _core.ticket_id(token)
    base_token = _base_token(payload)
    writer_tx = _sidequests46.writer_transaction(mechanical_writer_tx)
    try:
        journal = _sidequests46.recover_matching_journal(
            repo, ticket_id=ticket_id_original, transaction=transaction
        )
        if journal is None:
            package = _sidequests46._plan_from_ticket(repo, meta)
            block, offer = _sidequests46._normalize_offer(transaction)
            if block is None:
                result = _conclude_base(repo, base_token, writer_tx)
                result["ticket_id"] = ticket_id_original
                result["sidequest_emergente"] = {
                    "resultado": "oferta_nao_materializada",
                    "mutacoes_sidequest": 0,
                    "regra": "oportunidade avaliada, mas nenhuma oferta foi narrada neste turno",
                }
                result.setdefault("sistemas_narrativos", []).append(
                    "emergent_sidequest_opportunity"
                )
                return result
            scene_id = str((_sidequests46._map(payload.get("cena"), "ticket.cena")).get("scene_id"))
            plan = _sidequests46.prepare_installation(
                repo,
                package=package,
                block=block,
                offer_scene_id=scene_id,
                offer_summary=offer["resumo"],
            )
            journal = _sidequests46.begin_conclusion(
                repo,
                ticket_id=ticket_id_original,
                transaction=transaction,
                plan=plan,
            )
        result = _conclude_base(repo, base_token, writer_tx)
        installed = _sidequests46.install(repo, journal)
    except _sidequests46.EmergentSidequestIntegrationError as exc:
        raise _core.CronicaError(
            f"Task46: {exc}. Se o turno já tiver sido registrado, repita o mesmo cronica concluir; "
            "o journal recupera a instalação sem duplicar a narração ou a quest."
        ) from exc

    result["ticket_id"] = ticket_id_original
    result["sidequest_emergente"] = installed
    result.setdefault("sistemas_narrativos", []).extend(
        [
            "emergent_sidequest_opportunity",
            "emergent_sidequest_authoring",
            "quest_rewards",
            "adversarial_integrity",
            "sidequest_progression",
        ]
    )
    return result


def register(
    repo: Path,
    token: str,
    transaction: dict,
    *,
    revalidate: bool = True,
):
    payload, meta = _task46_meta(token)
    if meta is not None:
        raise _core.CronicaError(
            "reparo Task46 repete cronica concluir com a mesma transação; registrar isolado não instala a sidequest"
        )
    try:
        writer_tx = _mechanics.validate_transaction(repo, payload, transaction)
    except _mechanics.MechanicalContractError as exc:
        raise _core.CronicaError(str(exc)) from exc
    original = _core._revalidate_ticket
    _core._revalidate_ticket = globals()["_revalidate_ticket"]
    try:
        return _hot.register(
            repo,
            token,
            writer_tx,
            revalidate_ticket=revalidate,
        )
    finally:
        _core._revalidate_ticket = original


def _subparsers(parser: argparse.ArgumentParser) -> argparse._SubParsersAction:
    return next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )


def build_parser() -> argparse.ArgumentParser:
    parser = _ORIGINAL_BUILD_PARSER()
    root = _subparsers(parser)
    prepare_parser = root.choices["preparar"]
    prepare_parser.add_argument(
        "--tag",
        dest="contexto_tag",
        action="append",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    prepare_parser.add_argument(
        "--transito-urbano",
        choices=[_hot.URBAN_TRANSIT_SCOPE],
        help=(
            "deslocamento material pela malha urbana; usa o mesmo preparar/concluir, "
            "sem criar local canônico nem chamada adicional"
        ),
    )
    prepare_parser.add_argument(
        "--mecanica-json",
        help=(
            "JSON com regras e obrigações mecânicas; fica congelado no mesmo ticket "
            "de preparar e não cria endpoint nem chamada de orquestração adicional"
        ),
    )
    sidequest_decision = prepare_parser.add_mutually_exclusive_group(required=True)
    sidequest_decision.add_argument(
        "--oportunidade-sidequest",
        action="store_true",
        help="acorda Task40 somente quando a cena produziu âncora causal concreta",
    )
    sidequest_decision.add_argument(
        "--sem-oportunidade-sidequest",
        action="store_true",
        help=(
            "declara que a cena não contém âncora para nova sidequest; missões já "
            "aceitas continuam projetadas read-only pela Task48"
        ),
    )
    prepare_parser.add_argument("--sidequest-origem-tipo")
    prepare_parser.add_argument("--sidequest-origem-id")
    prepare_parser.add_argument("--sidequest-ancora-tipo")
    prepare_parser.add_argument("--sidequest-ancora")
    prepare_parser.add_argument("--sidequest-npc")

    session = root.add_parser(
        "sessao",
        help="lifecycle de alto nível: checkpoint, encerrar, iniciar, recuperar e status",
    )
    session_sub = session.add_subparsers(dest="sessao_cmd", required=True)
    session_sub.add_parser("status", help="resume lifecycle e devolve retomada quente sem transcrição")
    session_sub.add_parser("checkpoint", help="checkpoint de cena + regeneração derivada")
    session_sub.add_parser("encerrar", help="fecha sessão com consolidação, mundo e handoff")
    session_sub.add_parser("iniciar", help="abre N+1, devolve recap compacto e não copia transcrição")
    session_sub.add_parser("recuperar", help="retoma journal interrompido e regenera memória")

    progression = root.add_parser(
        "progressao",
        help="level-up mecânico atômico, protegido pelo milestone registrado",
    )
    progression_sub = progression.add_subparsers(dest="progressao_cmd", required=True)
    progression_sub.add_parser("status", help="mostra nível da ficha e nível desbloqueado")
    apply = progression_sub.add_parser(
        "aplicar",
        help="aplica um plano mecânico em um único journal multi-arquivo",
    )
    apply.add_argument(
        "--arquivo",
        type=Path,
        help="plano YAML/JSON; sem esta opção, lê stdin",
    )
    return parser


def _sidequest_signal_from_args(args: argparse.Namespace) -> dict | None:
    fields = {
        "origem_tipo": getattr(args, "sidequest_origem_tipo", None),
        "origem_id": getattr(args, "sidequest_origem_id", None),
        "ancora_tipo": getattr(args, "sidequest_ancora_tipo", None),
        "ancora": getattr(args, "sidequest_ancora", None),
        "npc_id": getattr(args, "sidequest_npc", None),
    }
    enabled = bool(getattr(args, "oportunidade_sidequest", False))
    declined = bool(getattr(args, "sem_oportunidade_sidequest", False))
    if enabled == declined:
        raise _core.CronicaError(
            "Task47: escolha exatamente uma decisão: --oportunidade-sidequest ou "
            "--sem-oportunidade-sidequest"
        )
    if declined:
        if any(value is not None for value in fields.values()):
            raise _core.CronicaError(
                "flags --sidequest-* não podem acompanhar --sem-oportunidade-sidequest"
            )
        return None
    if fields["origem_id"] is None:
        fields["origem_id"] = args.cena_id
    if fields["npc_id"] is None and len(args.npc or []) == 1:
        fields["npc_id"] = args.npc[0]
    missing = [
        label
        for key, label in (
            ("origem_tipo", "--sidequest-origem-tipo"),
            ("ancora_tipo", "--sidequest-ancora-tipo"),
            ("ancora", "--sidequest-ancora"),
        )
        if fields[key] is None
    ]
    if fields["origem_tipo"] in {"conversa_npc", "consequencia_npc"} and fields["npc_id"] is None:
        missing.append("--sidequest-npc ou exatamente um --npc")
    if missing:
        raise _core.CronicaError(
            "Task47: --oportunidade-sidequest exige âncora causal completa; faltando: "
            + ", ".join(missing)
        )
    fields["local_id"] = args.local
    fields["periculosidade"] = args.periculosidade or "media"
    fields["tier"] = args.tier
    return fields


def _mechanical_spec_from_args(args: argparse.Namespace) -> dict | None:
    raw = getattr(args, "mecanica_json", None)
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise _core.CronicaError(f"--mecanica-json inválido: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise _core.CronicaError("--mecanica-json precisa representar um objeto JSON")
    return data


def _run_session(repo: Path, command: str):
    if command == "status":
        return retomada_cronica.decorate_status(repo, ciclo_cronica.session_status(repo))
    if command == "checkpoint":
        return ciclo_cronica.session_checkpoint(repo)
    if command == "encerrar":
        return ciclo_cronica.session_close(repo)
    if command == "iniciar":
        return retomada_cronica.decorate_start(repo, ciclo_cronica.session_start(repo))
    if command == "recuperar":
        return ciclo_cronica.session_recover(repo)
    raise ciclo_cronica.UnifiedSessionError(f"subcomando de sessão desconhecido: {command}")


def _run_progression(repo: Path, command: str, file: Path | None):
    if command == "status":
        return ciclo_cronica.progression_status(repo)
    if command == "aplicar":
        plan = ciclo_cronica.read_progression_plan(file)
        return ciclo_cronica.apply_progression(repo, plan)
    raise ciclo_cronica.UnifiedSessionError(f"subcomando de progressão desconhecido: {command}")


def _run_turn(repo: Path, args: argparse.Namespace):
    if args.cmd == "preparar":
        return prepare(
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
            urban_transit=getattr(args, "transito_urbano", None),
            mechanical_spec=_mechanical_spec_from_args(args),
            sidequest_signal=_sidequest_signal_from_args(args),
        )
    token = _ticket_argument(args.ticket)
    if args.cmd == "concluir":
        return conclude(repo, token, turno.read_transaction(args.arquivo))
    if args.cmd == "registrar":
        return register(
            repo,
            token,
            turno.read_transaction(args.arquivo),
            revalidate=not args.reparo_pos_confirmacao,
        )
    return confirm(repo, token)


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    args = build_parser().parse_args(raw)
    repo = args.repo.resolve()
    try:
        if args.cmd in {"preparar", "concluir", "registrar", "confirmar"}:
            result = _run_turn(repo, args)
        elif args.cmd == "sessao":
            result = _run_session(repo, args.sessao_cmd)
        elif args.cmd == "progressao":
            result = _run_progression(
                repo,
                args.progressao_cmd,
                getattr(args, "arquivo", None),
            )
        else:
            raise ciclo_cronica.UnifiedSessionError(f"comando desconhecido: {args.cmd}")
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
        ciclo_cronica.UnifiedSessionError,
        ciclo_sessoes.SessionLifecycleError,
        consolidar.ConsolidationError,
        checkpoint.mundo.WorldEngineError,
        checkpoint.direcoes.DirectionError,
        checkpoint.interacoes_mundo.IntegrationError,
        checkpoint.barreira_mundo.WorldPendingBarrierError,
        progressao_juppongatana.JuppongatanaProgressionError,
        sessoes.SessionMemoryError,
        transacoes.TransactionError,
        OSError,
        ValueError,
        yaml.YAMLError,
    ) as exc:
        print(f"FALHA CRONICA — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
