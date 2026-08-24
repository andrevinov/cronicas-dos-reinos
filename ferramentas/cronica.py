#!/usr/bin/env python3
"""CLI operacional unificada de turno, sessão e progressão.

A Task 21 permanece preservada em ``_cronica_turn_core.py`` e a Task 22 em
``ciclo_cronica.py``. A camada pública acrescenta ergonomia observada em rollout
real: turno neutro sem gatilho inventado, trânsito urbano no mesmo hot path,
retomada compacta limpa, transporte de ticket tolerante a whitespace acidental,
gate read-only de pendências e contratos operacionais tolerantes a aliases
inequívocos sem relaxar checksum, cânone ou semântica transacional.
"""
from __future__ import annotations

import argparse
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
import progressao_juppongatana
import retomada_cronica
import sessoes
import transacoes

# Compatibilidade integral da Task 21.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

_ORIGINAL_BUILD_PARSER = _core.build_parser
_ORIGINAL_MAIN = _core.main
_ORIGINAL_B64_DECODE = _core._b64_decode
_ORIGINAL_DECODE_TICKET = _core.decode_ticket
_ORIGINAL_INSTANT_ARG = _core._instant_arg
_ORIGINAL_TRANSACTION_CONTRACT = _hot._transaction_contract


def _b64_decode(value: str) -> bytes:
    """Torna o corpo base64 robusto a wrap/cópia com whitespace acidental."""
    compact = "".join(value.split())
    return _ORIGINAL_B64_DECODE(compact)


def _ticket_argument(value: str) -> str:
    try:
        return _contracts.explain_ticket_argument(value)
    except _contracts.OperationalContractError as exc:
        raise _core.CronicaError(str(exc)) from exc


def decode_ticket(value: str) -> dict:
    """Falha com instrução operacional quando ``ticket_id`` é usado como ticket."""
    return _ORIGINAL_DECODE_TICKET(_ticket_argument(value))


def _instant_arg(date: str | None, hour: str | None):
    """Aceita aliases inequívocos de data na borda e preserva o instante canônico."""
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
    return contract


# ``cronica_hotpath`` e a Task 21 compartilham o mesmo módulo core. Patchar as
# portas de borda mantém um único decoder/parser sem criar motor paralelo.
_core._b64_decode = _b64_decode
_core.decode_ticket = decode_ticket
_hot._transaction_contract = _transaction_contract


def prepare(*args, **kwargs):
    """Aplica a barreira barata antes de delegar à preparação de turno existente."""
    repo = args[0] if args else kwargs.get("repo")
    if repo is None:
        raise _core.CronicaError("cronica preparar exige raiz do repositório")
    gate = _pending_gate.prepare_gate(Path(repo))
    if gate is not None:
        return gate
    return _hot.prepare(*args, **kwargs)


def confirm(*args, **kwargs):
    return _hot.confirm(*args, **kwargs)


def conclude(*args, **kwargs):
    """Preserva o hook público de preflight da Task 21 também no hot path."""
    original = _core._preflight_registration
    _core._preflight_registration = globals()["_preflight_registration"]
    try:
        return _hot.conclude(
            *args,
            **kwargs,
            preflight=globals()["_preflight_registration"],
        )
    finally:
        _core._preflight_registration = original


def register(*args, revalidate: bool = True, **kwargs):
    """Preserva o hook público de revalidação da Task 21."""
    original = _core._revalidate_ticket
    _core._revalidate_ticket = globals()["_revalidate_ticket"]
    try:
        return _hot.register(
            *args,
            **kwargs,
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
    # Alias de compatibilidade observado em rollout. ``--contexto-tag`` continua
    # sendo o nome canônico e a validação tipada permanece na mesma camada.
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
