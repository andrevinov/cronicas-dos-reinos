#!/usr/bin/env python3
"""Endpoints determinísticos com Approach Quality Modifier opcional.

O contrato original da Task 10 está preservado em ``_endpoints_core.py``. Esta
camada acrescenta a qualidade da abordagem somente ao campo ``modificadores`` já
reservado, sem novo endpoint, nova leitura ou mudança de schema.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

import _endpoints_core as _base
import qualidade_abordagem

_ORIGINAL_PROJECT_SCENE = _base.project_scene
_ORIGINAL_BUILD_PARSER = _base.build_parser

for _name in dir(_base):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_base, _name)


def _quality(
    *,
    preparacao: str | None = None,
    informacao: str | None = None,
    adequacao: str | None = None,
) -> dict[str, Any]:
    return qualidade_abordagem.evaluate(
        preparacao=preparacao,
        informacao=informacao,
        adequacao=adequacao,
    )


def project_scene(
    preview: dict[str, Any],
    *,
    approach_preparacao: str | None = None,
    approach_informacao: str | None = None,
    approach_adequacao: str | None = None,
) -> dict[str, Any]:
    result = _ORIGINAL_PROJECT_SCENE(preview)
    quality = _quality(
        preparacao=approach_preparacao,
        informacao=approach_informacao,
        adequacao=approach_adequacao,
    )
    if int(quality["bonus"]) > 0:
        result["modificadores"].append(qualidade_abordagem.compact_modifier(quality))
        if "qualidade_abordagem_pre_rolagem" not in result["filtros"]:
            result["filtros"].append("qualidade_abordagem_pre_rolagem")
    _base.validate_endpoint(result)
    return result


def scene(
    repo: Path,
    *,
    scene_id: str,
    npcs: list[str] | None = None,
    place: str | None = None,
    action: str | None = None,
    tier: int | None = None,
    danger: str | None = None,
    context_tags: list[str] | None = None,
    now: _base.mundo.WorldInstant | None = None,
    approach_preparacao: str | None = None,
    approach_informacao: str | None = None,
    approach_adequacao: str | None = None,
) -> dict[str, Any]:
    # Continua exatamente uma chamada subjacente. A rubrica é pura e trabalha
    # apenas sobre evidência fornecida pelo narrador antes da rolagem.
    preview = _base.cena_mundo.prepare_scene(
        repo,
        scene_id=scene_id,
        npcs=npcs,
        place=place,
        action=action,
        tier=tier,
        danger=danger,
        context_tags=context_tags,
        now=now,
    )
    return project_scene(
        preview,
        approach_preparacao=approach_preparacao,
        approach_informacao=approach_informacao,
        approach_adequacao=approach_adequacao,
    )


def _add_approach_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--abordagem-preparacao",
        help="evidência de preparação concreta que favorece o teste",
    )
    parser.add_argument(
        "--abordagem-informacao",
        help="evidência de informação relevante usada pelo plano",
    )
    parser.add_argument(
        "--abordagem-adequacao",
        help="evidência de que o método se ajusta especialmente bem ao obstáculo",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = _ORIGINAL_BUILD_PARSER()
    sub = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    _add_approach_flags(sub.choices["cena"])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "cena":
            result = scene(
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
            )
        elif args.cmd == "fronteira":
            result = _base.boundary(repo, date=args.data, hour=args.hora)
        elif args.cmd == "pendencias":
            result = _base.pending(repo)
        elif args.cmd == "direcao":
            result = _base.direction(repo, args.direcao)
        else:
            result = _base.sidequest(repo, args.id, _base._stdin())
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0
    except (
        qualidade_abordagem.ApproachQualityError,
        _base.EndpointError,
        _base.cena_mundo.SceneGateError,
        _base.direcoes_destino.DestinationDirectionError,
        _base.fronteira_mundo.BoundaryError,
        _base.interacoes_mundo.IntegrationError,
        _base.mundo.WorldEngineError,
        OSError,
        yaml.YAMLError,
    ) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
