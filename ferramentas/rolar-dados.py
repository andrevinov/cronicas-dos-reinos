#!/usr/bin/env python3
"""Porta pública de dados com Approach Quality Modifier pré-rolagem.

O motor anterior foi preservado em ``_rolar_dados_core.py``. Esta camada só
interpreta três evidências estruturadas antes do RNG, soma o bônus resultante ao
modificador circunstancial apropriado e então delega exatamente uma vez ao motor
existente.
"""
from __future__ import annotations

import contextlib
import io
import sys
from typing import Any

import _rolar_dados_core as _core
import qualidade_abordagem

# Compatibilidade: quem importava funções/classes do rolador público continua
# encontrando o mesmo motor. Somente ``main`` e a preparação de argv são novos.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

APPROACH_FLAGS = {
    "--abordagem-preparacao": "preparacao",
    "--abordagem-informacao": "informacao",
    "--abordagem-adequacao": "adequacao",
}


def _extract_approach(argv: list[str]) -> tuple[list[str], dict[str, Any]]:
    clean: list[str] = []
    values: dict[str, str | None] = {key: None for key in qualidade_abordagem.CRITERIA}
    seen: set[str] = set()
    index = 0
    while index < len(argv):
        token = argv[index]
        matched_flag: str | None = None
        inline_value: str | None = None
        for flag in APPROACH_FLAGS:
            if token == flag:
                matched_flag = flag
                break
            if token.startswith(flag + "="):
                matched_flag = flag
                inline_value = token.split("=", 1)[1]
                break
        if matched_flag is None:
            clean.append(token)
            index += 1
            continue
        if matched_flag in seen:
            raise qualidade_abordagem.ApproachQualityError(
                f"flag de abordagem repetida: {matched_flag}"
            )
        seen.add(matched_flag)
        if inline_value is None:
            if index + 1 >= len(argv):
                raise qualidade_abordagem.ApproachQualityError(
                    f"{matched_flag} exige evidência textual"
                )
            inline_value = argv[index + 1]
            index += 2
        else:
            index += 1
        values[APPROACH_FLAGS[matched_flag]] = inline_value

    result = qualidade_abordagem.evaluate(
        preparacao=values["preparacao"],
        informacao=values["informacao"],
        adequacao=values["adequacao"],
    )
    return clean, result


def _approach_bonus_flag(argv: list[str]) -> str:
    if argv and argv[0] == "d20":
        return "--bonus"
    if len(argv) >= 2 and argv[0] == "ren" and argv[1] in {"pericia", "skill"}:
        return "--bonus-extra"
    raise qualidade_abordagem.ApproachQualityError(
        "qualidade da abordagem só se aplica a d20 genérico do jogador ou perícia de Ren; "
        "não se aplica a ataque, salvaguarda, iniciativa, dano ou NPC"
    )


def _bump_integer_flag(argv: list[str], flag: str, amount: int) -> list[str]:
    if amount == 0:
        return list(argv)
    result = list(argv)
    matches: list[tuple[int, str]] = []
    for index, token in enumerate(result):
        if token == flag:
            matches.append((index, "separate"))
        elif token.startswith(flag + "="):
            matches.append((index, "inline"))
    if len(matches) > 1:
        raise qualidade_abordagem.ApproachQualityError(f"{flag} não pode ser repetido")
    if not matches:
        return [*result, flag, str(amount)]

    index, mode = matches[0]
    if mode == "inline":
        raw = result[index].split("=", 1)[1]
        try:
            current = int(raw)
        except ValueError as exc:
            raise qualidade_abordagem.ApproachQualityError(
                f"{flag} precisa ser inteiro antes de somar qualidade da abordagem"
            ) from exc
        result[index] = f"{flag}={current + amount}"
        return result

    if index + 1 >= len(result):
        raise qualidade_abordagem.ApproachQualityError(f"{flag} exige valor inteiro")
    try:
        current = int(result[index + 1])
    except ValueError as exc:
        raise qualidade_abordagem.ApproachQualityError(
            f"{flag} precisa ser inteiro antes de somar qualidade da abordagem"
        ) from exc
    result[index + 1] = str(current + amount)
    return result


def prepare_argv(argv: list[str]) -> tuple[list[str], dict[str, Any]]:
    """Valida abordagem e calcula argv final antes de qualquer chamada ao RNG."""
    clean, quality = _extract_approach(list(argv))
    bonus = int(quality["bonus"])
    if bonus:
        clean = _bump_integer_flag(clean, _approach_bonus_flag(clean), bonus)
    return clean, quality


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    try:
        adjusted, quality = prepare_argv(raw)
    except qualidade_abordagem.ApproachQualityError as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2

    if int(quality["bonus"]) == 0:
        return _core.main(adjusted)

    # Com abordagem, capturamos somente stdout para anexar a auditoria na mesma
    # linha. stderr e o código de saída do motor permanecem intactos.
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        status = _core.main(adjusted)
    output = buffer.getvalue().rstrip("\n")
    if status != 0:
        if output:
            print(output)
        return status
    note = qualidade_abordagem.annotation(quality)
    if output:
        print(f"{output} {note}.")
    elif note:
        print(note + ".")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
