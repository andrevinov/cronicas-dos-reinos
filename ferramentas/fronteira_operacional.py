#!/usr/bin/env python3
"""Porta operacional compacta para fronteira temporal com aliases de data.

Reutiliza exatamente o endpoint determinístico existente; a única responsabilidade
nova é normalizar representações inequívocas da data antes da consulta.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

import contratos_operacionais
import endpoints


def query(repo: Path, date: str, hour: str):
    try:
        normalized = contratos_operacionais.normalize_date(date)
    except contratos_operacionais.OperationalContractError as exc:
        raise endpoints.EndpointError(str(exc)) from exc
    return endpoints.boundary(repo, date=normalized, hour=hour)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--data",
        required=True,
        help="data-alvo: '17 Eleasis, 1372 DR', '1372-08-17' ou '17/08/1372'",
    )
    parser.add_argument("--hora", required=True, help="hora-alvo HH:MM")
    args = parser.parse_args(argv)
    try:
        result = query(args.repo.resolve(), args.data, args.hora)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0
    except (
        endpoints.EndpointError,
        endpoints.fronteira_mundo.BoundaryError,
        endpoints.mundo.WorldEngineError,
        OSError,
        yaml.YAMLError,
    ) as exc:
        print(
            "ERRO FRONTEIRA — "
            + str(exc)
            + "; use `poetry run python ferramentas/fronteira_operacional.py --data <data> --hora HH:MM`",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
