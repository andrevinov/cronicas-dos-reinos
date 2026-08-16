#!/usr/bin/env python3
"""Classifica a linguagem de mesa ON/OFF/RECALL sem interpretar a ficção.

Convenção:

- texto normal: ON — ação/fala/intenção do jogador dentro da ficção;
- bloco inteiro `[ ... ]`: OFF — conversa meta com o narrador;
- `{ ... }` dentro de ON: RECALL — lacuna factual que Ren conhece e o narrador
  deve resolver antes de executar/registrar a ação.

O parser é deliberadamente sintático. Ele NÃO decide se um pedido de RECALL é
permitido pela agência de Ren nem pesquisa a resposta. Essas decisões continuam
sob o contrato narrativo. O objetivo desta ferramenta é separar os canais de
forma determinística e impedir que OFF/RECALL cru cheguem à transcrição.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML não encontrado. Instale com: poetry install"
    ) from exc

SCHEMA_ENTRADA = 1


class InputProtocolError(ValueError):
    """A mensagem viola a sintaxe explícita ON/OFF/RECALL."""


def _split_blocks(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return []
    return [
        block.strip()
        for block in re.split(r"\n[ \t]*\n+", normalized)
        if block.strip()
    ]


def _find_recalls(text: str, block_number: int) -> list[dict[str, Any]]:
    recalls: list[dict[str, Any]] = []
    start: int | None = None
    i = 0
    while i < len(text):
        char = text[i]
        # Permite chaves literais escapadas como \{ e \} sem ativar RECALL.
        if char == "\\" and i + 1 < len(text) and text[i + 1] in "{}":
            i += 2
            continue
        if char == "{":
            if start is not None:
                raise InputProtocolError(
                    f"bloco {block_number}: RECALL aninhado não é permitido"
                )
            start = i
        elif char == "}":
            if start is None:
                raise InputProtocolError(
                    f"bloco {block_number}: chave '}}' sem abertura '{{'"
                )
            request = text[start + 1 : i].strip()
            if not request:
                raise InputProtocolError(
                    f"bloco {block_number}: RECALL vazio não é permitido"
                )
            recalls.append(
                {
                    "pedido": request,
                    "bloco": block_number,
                    "inicio": start,
                    "fim": i + 1,
                }
            )
            start = None
        i += 1
    if start is not None:
        raise InputProtocolError(
            f"bloco {block_number}: RECALL aberto com '{{' e não fechado"
        )
    return recalls


def parse_message(text: str) -> dict[str, Any]:
    """Separa a mensagem em ON/OFF e extrai lacunas RECALL de blocos ON."""
    report: dict[str, Any] = {
        "schema_entrada": SCHEMA_ENTRADA,
        "valido": True,
        "tipo": "vazio",
        "tem_on": False,
        "tem_off": False,
        "tem_recall": False,
        "pode_registrar": False,
        "blocos": [],
        "on": None,
        "off": [],
        "recalls": [],
        "erros": [],
    }
    blocks = _split_blocks(text)
    if not blocks:
        report["valido"] = False
        report["erros"] = ["entrada vazia"]
        return report

    on_blocks: list[str] = []
    off_blocks: list[str] = []
    recalls: list[dict[str, Any]] = []

    try:
        for number, block in enumerate(blocks, start=1):
            stripped = block.strip()
            if stripped.startswith("["):
                if not stripped.endswith("]"):
                    raise InputProtocolError(
                        f"bloco {number}: OFF iniciado com '[' precisa terminar com ']' no mesmo bloco"
                    )
                body = stripped[1:-1].strip()
                if not body:
                    raise InputProtocolError(
                        f"bloco {number}: OFF vazio não é permitido"
                    )
                off_blocks.append(body)
                report["blocos"].append(
                    {"ordem": number, "tipo": "off", "texto": body}
                )
                continue

            block_recalls = _find_recalls(block, number)
            on_blocks.append(block)
            recalls.extend(block_recalls)
            item: dict[str, Any] = {
                "ordem": number,
                "tipo": "on",
                "texto": block,
            }
            if block_recalls:
                item["recalls"] = block_recalls
            report["blocos"].append(item)
    except InputProtocolError as exc:
        report["valido"] = False
        report["tipo"] = "invalido"
        report["erros"] = [str(exc)]
        return report

    report["tem_on"] = bool(on_blocks)
    report["tem_off"] = bool(off_blocks)
    report["tem_recall"] = bool(recalls)
    report["on"] = "\n\n".join(on_blocks) if on_blocks else None
    report["off"] = off_blocks
    report["recalls"] = recalls

    if on_blocks and off_blocks:
        report["tipo"] = "misto"
    elif on_blocks:
        report["tipo"] = "somente_on"
    else:
        report["tipo"] = "somente_off"

    # O campo `jogador` de turno.py só pode receber ON já resolvido.
    report["pode_registrar"] = bool(
        report["valido"]
        and report["tipo"] == "somente_on"
        and not report["tem_recall"]
    )
    return report


def assert_registerable(text: str) -> str:
    """Retorna ON limpo ou recusa OFF/RECALL antes de uma transação."""
    report = parse_message(text)
    if not report["valido"]:
        raise InputProtocolError("; ".join(report["erros"]))
    if report["tem_off"]:
        raise InputProtocolError(
            "campo jogador contém OFF; responda ao bloco meta fora da transação e registre somente ON"
        )
    if report["tem_recall"]:
        requests = ", ".join(item["pedido"] for item in report["recalls"])
        raise InputProtocolError(
            "campo jogador contém RECALL não resolvido: "
            f"{requests}; resolva/substitua antes de registrar"
        )
    if not report["tem_on"]:
        raise InputProtocolError("campo jogador não contém conteúdo ON registrável")
    return str(report["on"] or "").strip()


def _read_input(args: argparse.Namespace) -> str:
    if args.texto is not None:
        return args.texto
    if args.arquivo is not None:
        return args.arquivo.read_text(encoding="utf-8")
    return sys.stdin.read()


def _emit(value: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=110), end="")


def _add_input_args(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--arquivo", type=Path, help="lê a mensagem de um arquivo UTF-8")
    group.add_argument("--texto", help="classifica o texto informado na própria linha de comando")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emite JSON em vez de YAML")
    sub = parser.add_subparsers(dest="comando", required=True)

    classify = sub.add_parser("classificar", help="separa ON/OFF e extrai RECALL")
    _add_input_args(classify)

    validate = sub.add_parser(
        "validar-registro",
        help="só retorna sucesso para ON puro, sem OFF nem RECALL pendente",
    )
    _add_input_args(validate)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        text = _read_input(args)
    except OSError as exc:
        print(f"FALHA DE ENTRADA — {exc}", file=sys.stderr)
        return 2

    report = parse_message(text)
    if args.comando == "classificar":
        _emit(report, args.json)
        return 0 if report["valido"] else 2

    try:
        on = assert_registerable(text)
        result = dict(report)
        result["on_registravel"] = on
        _emit(result, args.json)
        return 0
    except InputProtocolError as exc:
        result = dict(report)
        result["pode_registrar"] = False
        result["erro_registro"] = str(exc)
        _emit(result, args.json)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
