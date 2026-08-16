#!/usr/bin/env python3
"""Executa várias chamadas de rolar-dados.py em uma única rodada de ferramenta.

Entrada JSON via stdin ou --arquivo. Formatos aceitos:

[
  ["ren", "pericia", "furtividade", "--cd", "14"],
  ["npc", "d20", "--nome", "Guarda", "--bonus", "3", "--cd", "12"]
]

ou

{"rolagens": [[...], [...]]}

O objetivo é reduzir ciclos modelo -> ferramenta -> modelo. Cada rolagem continua
usando exatamente o mesmo motor e as mesmas regras de `rolar-dados.py`.
"""
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

MAX_ROLLS = 24


class BatchError(ValueError):
    pass


def read_payload(path: Path | None) -> list[list[str]]:
    raw = path.read_text(encoding="utf-8") if path else sys.stdin.read()
    if not raw.strip():
        raise BatchError("entrada JSON vazia")
    try:
        payload: Any = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BatchError(f"JSON inválido: {exc}") from exc
    if isinstance(payload, dict):
        payload = payload.get("rolagens")
    if not isinstance(payload, list):
        raise BatchError("entrada precisa ser lista ou objeto com chave 'rolagens'")
    if not payload:
        raise BatchError("lote precisa conter pelo menos uma rolagem")
    if len(payload) > MAX_ROLLS:
        raise BatchError(f"lote excede {MAX_ROLLS} rolagens")

    commands: list[list[str]] = []
    for item in payload:
        if isinstance(item, str):
            argv = shlex.split(item)
        elif isinstance(item, list) and all(isinstance(part, str) for part in item):
            argv = list(item)
        else:
            raise BatchError("cada rolagem precisa ser string de comando ou lista de strings")
        if not argv:
            raise BatchError("rolagem vazia no lote")
        commands.append(argv)
    return commands


def run_batch(script: Path, commands: list[list[str]]) -> list[str]:
    outputs: list[str] = []
    for index, argv in enumerate(commands, start=1):
        process = subprocess.run(
            [sys.executable, str(script), *argv],
            text=True,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            detail = (process.stderr or process.stdout).strip()
            raise BatchError(f"rolagem {index} falhou: {detail}")
        text = process.stdout.strip()
        outputs.append(text)
    return outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arquivo", type=Path, help="arquivo JSON; sem opção, lê stdin")
    parser.add_argument(
        "--rolador",
        type=Path,
        default=Path(__file__).with_name("rolar-dados.py"),
        help="caminho do rolador base",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        commands = read_payload(args.arquivo)
        outputs = run_batch(args.rolador.resolve(), commands)
    except (OSError, BatchError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2
    for index, output in enumerate(outputs, start=1):
        print(f"{index}. {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
