#!/usr/bin/env python3
"""Composição NV-17 da porta ``cronica``.

A decisão Task47 continua obrigatória, mas sua negativa significa apenas "não há
âncora nova nesta cena". Antes da Task46, causas NV-11 vencidas e alcançáveis são
projetadas por índice dirigido e não podem ser escondidas por essa negativa.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path

import yaml

import cronica_iniciativa as _prev
import cronica_pending_gate as _pending_gate
import sidequests_vivas as _live

_base = _prev._base
_core = _base._core
_BASE_PREPARE = _base.prepare
_BASE_BUILD_PARSER = _base.build_parser
_UNSET = object()


def _repo(args, kwargs) -> Path | None:
    raw = args[0] if args else kwargs.get("repo")
    return Path(raw) if raw is not None else None


def _installed(repo: Path) -> bool:
    """Ativa NV-17 somente depois do recibo one-shot de instalação/migração.

    Fixtures anteriores à NV-17 não carregam esse recibo e devem continuar a
    exercer exatamente o contrato que estão testando, sem ganhar dependência de
    tempo/agenda/estado novos. No repositório instalado o recibo é obrigatório e
    o check da própria NV-17 valida seu conteúdo.
    """
    return (Path(repo) / _live.MIGRATION).is_file()


def _require_recovery_first(repo: Path) -> None:
    """Preserva a precedência do journal Task49 antes de qualquer reserva NV-17."""
    progress = _base._sidequests49
    try:
        progress.require_no_open_journal(Path(repo))
    except progress.TransactionalSidequestProgressError as exc:
        raise _core.CronicaError(f"Task49: {exc}") from exc


def _public(route: dict) -> dict:
    selected = route.get("causa_viva")
    need = None
    if isinstance(selected, dict):
        need = {
            key: copy.deepcopy(selected.get(key))
            for key in (
                "id",
                "plano_id",
                "causa",
                "dono",
                "bloqueio",
                "conhecimento",
                "alcance",
                "reavaliacao",
                "stakes",
                "protecoes",
                "motivo_envolver_ren",
                "prioridade_elevada_por_zero_ativas",
            )
        }
    projection = route.get("projecao") or {}
    return {
        "schema_sidequests_vivas": _live.SCHEMA,
        "janela": copy.deepcopy(route.get("janela")),
        "resultado": route.get("resultado"),
        "origem": route.get("origem"),
        "reutilizada": bool(route.get("reutilizada")),
        "causa_viva": need,
        "ancora_manual_adiada": bool(route.get("ancora_manual_adiada")),
        "orcamento": copy.deepcopy(projection.get("orcamento")),
        "regra": (
            "a negativa Task47 só nega âncora nova; causa NV-11 vencida e alcançável "
            "permanece elegível; somente oferta narrada pode ser materializada pela Task46"
        ),
    }


def _encoded_size(value: dict) -> int:
    return len(yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8"))


def _output_limit(prepared: dict) -> int:
    limit = int(getattr(_core, "MAX_PREP_OUTPUT_BYTES", 12 * 1024))
    if "pressao_narrativa" in prepared:
        pressure = getattr(_base, "_pressure52", None)
        limit = int(getattr(pressure, "MAX_OUTPUT_BYTES", limit))
    elif "sidequest_emergente" in prepared or "sidequests_ativas" in prepared:
        integration = getattr(_base, "_sidequests46", None)
        limit = int(getattr(integration, "MAX_COMBINED_PREP_BYTES", limit))
    return limit


def _decorate(prepared: dict, routed: dict) -> dict:
    projection = routed.get("projecao") or {}
    should_expose = (
        routed.get("resultado") != "sem_nova_oportunidade"
        or bool(projection.get("causas"))
    )
    if not should_expose or prepared.get("fase") == "bloqueada_pendencias_mundo":
        return prepared

    candidate = copy.deepcopy(prepared)
    candidate["sidequests_vivas"] = _public(routed)
    systems = candidate.setdefault("sistemas_narrativos", [])
    if "live_sidequests_by_cause" not in systems:
        systems.append("live_sidequests_by_cause")

    # O bloco é observabilidade; nunca pode fazer um preparo funcional estourar o
    # envelope herdado. Task46 já transporta a causa autoritativa no ticket.
    if _encoded_size(candidate) <= _output_limit(prepared):
        return candidate
    return prepared


def prepare(*args, **kwargs):
    signal = kwargs.get("sidequest_signal", _UNSET)
    if signal is _UNSET:
        # Preserva o erro explícito da Task47 em chamadas programáticas antigas.
        return _BASE_PREPARE(*args, **kwargs)
    repo = _repo(args, kwargs)
    if repo is None:
        return _BASE_PREPARE(*args, **kwargs)

    # Compatibilidade estrutural: sandboxes/fixtures anteriores à NV-17 não têm
    # o recibo de migração e não devem precisar fabricar tempo/agenda novos.
    if not _installed(repo):
        return _BASE_PREPARE(*args, **kwargs)

    # A Task49 já bloqueava qualquer turno novo durante recovery. A NV-17 não
    # pode ler tempo/agenda nem reservar uma oportunidade antes desse gate.
    _require_recovery_first(repo)

    # Pendência bloqueante tem precedência. Não reservar oportunidade enquanto o
    # turno talvez nem atravesse a barreira. A base ainda revalida sua própria
    # exceção operacional para contatos/operações já comprometidos.
    gate = _pending_gate.prepare_gate(repo)
    if gate is not None:
        return _BASE_PREPARE(*args, **kwargs)

    try:
        routed = _live.route_prepare(
            repo,
            manual_signal=signal,
            participants=kwargs.get("npcs"),
            local_id=kwargs.get("place"),
            danger=kwargs.get("danger") or "media",
            tier=kwargs.get("tier"),
            now=kwargs.get("now"),
        )
    except _live.LiveSidequestError as exc:
        raise _core.CronicaError(f"NV17: {exc}") from exc

    forwarded = dict(kwargs)
    forwarded["sidequest_signal"] = routed["sinal_efetivo"]
    prepared = _BASE_PREPARE(*args, **forwarded)
    if not isinstance(prepared, dict):
        return prepared
    return _decorate(prepared, routed)


def build_parser() -> argparse.ArgumentParser:
    parser = _BASE_BUILD_PARSER()
    root = _base._subparsers(parser)
    prepare_parser = root.choices["preparar"]
    for action in prepare_parser._actions:
        if "--sem-oportunidade-sidequest" in action.option_strings:
            action.help = (
                "declara que a cena não trouxe âncora NOVA; não suprime causa NV-11 "
                "vencida/alcançável da NV-17"
            )
        elif "--oportunidade-sidequest" in action.option_strings:
            action.help = (
                "declara âncora causal NOVA surgida na própria cena; causas NV-11 de "
                "planos são projetadas automaticamente"
            )
        elif "--sidequest-plano" in action.option_strings:
            action.help = (
                "referência explícita de compatibilidade a plano NV-11; NV-17 ainda "
                "exige causa vencida e alcance até Ren"
            )
    return parser


_base.prepare = prepare
_base.build_parser = build_parser
_base._sidequests17 = _live

for _name in dir(_prev):
    if not _name.startswith("__") and not hasattr(_base, _name):
        setattr(_base, _name, getattr(_prev, _name))

main = _base.main

if __name__ == "__main__":
    raise SystemExit(main())
