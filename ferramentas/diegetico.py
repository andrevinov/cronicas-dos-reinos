#!/usr/bin/env python3
"""Guardrail puro para separar prosa diegética de mecânica explícita.

A camada não interpreta regras nem reescreve texto. Ela apenas impede que termos
mecânicos de personagem/sistema entrem em fala de NPC ou prosa de cena. Quando a
informação mecânica precisa ser exibida, use uma linha própria iniciada por
``MECÂNICA —``; essa linha é uma camada OOC explícita, não voz do mundo.
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from typing import Iterable

MECHANICS_PREFIX = "MECÂNICA —"
ASCII_MECHANICS_PREFIX = "MECANICA —"
MAX_VIOLATIONS = 8


class DiegeticMechanicsError(ValueError):
    pass


@dataclass(frozen=True)
class Rule:
    category: str
    pattern: re.Pattern[str]
    hint: str


RULES: tuple[Rule, ...] = (
    Rule(
        "pv_hp",
        re.compile(r"(?<![\w])(?:PV|HP)(?![\w])|\bpontos?\s+de\s+vida\b|\bhit\s+points?\b", re.IGNORECASE),
        "PV/HP e pontos de vida",
    ),
    Rule(
        "ca_ac",
        re.compile(r"(?<![\w])(?:CA|AC)(?![\w])|\bclasse\s+de\s+armadura\b|\barmor\s+class\b"),
        "CA/AC e classe de armadura",
    ),
    Rule(
        "cd_dc",
        re.compile(r"(?<![\w])(?:CD|DC)(?![\w])|\bclasse\s+de\s+dificuldade\b|\bdifficulty\s+class\b"),
        "CD/DC e classe de dificuldade",
    ),
    Rule(
        "nivel",
        re.compile(
            r"\b(?:n[ií]vel|level)\s+(?:\d+|de\s+(?:personagem|classe)|do\s+personagem|da\s+classe)\b"
            r"|\b\d+\s*(?:º|o)?\s*n[ií]vel\b",
            re.IGNORECASE,
        ),
        "nível mecânico",
    ),
    Rule(
        "ki_pontos",
        re.compile(
            r"\bpontos?\s+de\s+ki\b|\bki\s+points?\b|\bki\s*[:=/]\s*\d+\b"
            r"|\b\d+\s+(?:pontos?\s+de\s+)?ki\b",
            re.IGNORECASE,
        ),
        "contagem de pontos de Ki",
    ),
    Rule(
        "slots",
        re.compile(
            r"\bspell\s+slots?\b|\bslots?\s+de\s+(?:magia|feiti[cç]o)\b"
            r"|\bespa[cç]os?\s+de\s+(?:magia|feiti[cç]o)\b",
            re.IGNORECASE,
        ),
        "slots/espaços de magia",
    ),
    Rule(
        "bonus",
        re.compile(
            r"\bb[oô]nus\s+(?:de\s+)?[+-]\s*\d+\b|\b[+-]\s*\d+\s+de\s+b[oô]nus\b"
            r"|\bb[oô]nus\s+(?:de\s+)?(?:profici[eê]ncia|ataque|teste|jogada|salvaguarda|per[ií]cia)\b"
            r"|\b(?:proficiency|attack)\s+bonus\b"
            r"|\b(?:ataque|teste|jogada|salvaguarda|per[ií]cia)\s*[+-]\s*\d+\b",
            re.IGNORECASE,
        ),
        "bônus/modificador numérico de regra",
    ),
)


def is_mechanics_line(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith(MECHANICS_PREFIX) or stripped.startswith(ASCII_MECHANICS_PREFIX)


def mechanics_payload(line: str) -> str | None:
    stripped = line.lstrip()
    for prefix in (MECHANICS_PREFIX, ASCII_MECHANICS_PREFIX):
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return None


def violations(text: str) -> list[dict[str, object]]:
    """Retorna violações somente em linhas diegéticas.

    Uma linha mecânica precisa ser explicitamente marcada e não pode estar vazia.
    O restante do texto — inclusive diálogo citado dentro da narração — é tratado
    como prosa do mundo.
    """
    result: list[dict[str, object]] = []
    for number, line in enumerate(text.splitlines() or [text], start=1):
        payload = mechanics_payload(line)
        if payload is not None:
            if not payload:
                result.append(
                    {
                        "linha": number,
                        "categoria": "camada_mecanica_vazia",
                        "trecho": MECHANICS_PREFIX,
                        "dica": "linha MECÂNICA precisa conter a informação OOC",
                    }
                )
            continue
        for rule in RULES:
            match = rule.pattern.search(line)
            if not match:
                continue
            result.append(
                {
                    "linha": number,
                    "categoria": rule.category,
                    "trecho": match.group(0),
                    "dica": rule.hint,
                }
            )
            if len(result) >= MAX_VIOLATIONS:
                return result
    return result


def validate_narration(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise DiegeticMechanicsError("narração diegética precisa ser texto não vazio")
    found = violations(text)
    if not found:
        return text
    first = found[0]
    raise DiegeticMechanicsError(
        "mecânica explícita dentro da prosa diegética: "
        f"linha {first['linha']} contém {first['trecho']!r} ({first['dica']}). "
        f"Reescreva de forma diegética ou mova a informação para linha própria `MECÂNICA — ...`."
    )


def validate_many(texts: Iterable[str]) -> None:
    for text in texts:
        validate_narration(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comando", choices=["validar"])
    args = parser.parse_args(argv)
    if args.comando != "validar":
        return 2
    text = sys.stdin.read()
    try:
        validate_narration(text)
    except DiegeticMechanicsError as exc:
        print(f"ERRO: {exc}")
        return 2
    print("OK — prosa diegética não contém mecânica explícita fora da camada MECÂNICA.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
