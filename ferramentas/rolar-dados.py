#!/usr/bin/env python3
"""Porta pública de dados com modificadores contextuais pré-rolagem.

O motor anterior foi preservado em ``_rolar_dados_core.py``. Esta camada interpreta
qualidade da abordagem e o gatilho de impersonação do talento Actor antes do RNG,
então delega exatamente uma vez ao motor existente.
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
ACTOR_FLAG = "--actor-impersonacao"
ACTOR_SKILLS = {"enganacao", "atuacao"}


class FeatContextError(ValueError):
    """Uso incoerente de um talento contextual antes da rolagem."""


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


def _apply_actor(argv: list[str]) -> tuple[list[str], str | None]:
    """Converte Actor em vantagem somente quando o chamador declara impersonação."""
    count = argv.count(ACTOR_FLAG)
    if count > 1:
        raise FeatContextError(f"{ACTOR_FLAG} não pode ser repetido")
    if count == 0:
        return list(argv), None

    clean = [token for token in argv if token != ACTOR_FLAG]
    if len(clean) < 3 or clean[0] != "ren" or clean[1] not in {"pericia", "skill"}:
        raise FeatContextError(
            "Actor só se aplica a `ren pericia enganacao|atuacao` quando Ren tenta se passar por outra pessoa"
        )
    skill = _core.normalize_key(clean[2])
    if skill not in ACTOR_SKILLS:
        raise FeatContextError(
            "Actor só concede vantagem a Enganação ou Atuação em contexto de impersonação"
        )

    has_advantage = "--vantagem" in clean
    has_disadvantage = "--desvantagem" in clean
    if has_advantage and has_disadvantage:
        raise FeatContextError("vantagem e desvantagem não podem ser declaradas juntas")
    if has_disadvantage:
        clean.remove("--desvantagem")
        return clean, "Actor: vantagem de impersonação cancelou a desvantagem; rolagem normal"
    if has_advantage:
        return clean, "Actor: vantagem de impersonação já estava representada"
    clean.append("--vantagem")
    return clean, "Actor: vantagem de impersonação aplicada"


def _prepare_argv_context(argv: list[str]) -> tuple[list[str], dict[str, Any], str | None]:
    clean, actor_note = _apply_actor(list(argv))
    clean, quality = _extract_approach(clean)
    bonus = int(quality["bonus"])
    if bonus:
        clean = _bump_integer_flag(clean, _approach_bonus_flag(clean), bonus)
    return clean, quality, actor_note


def prepare_argv(argv: list[str]) -> tuple[list[str], dict[str, Any]]:
    """Compatibilidade: devolve argv final + qualidade, já incluindo Actor quando declarado."""
    clean, quality, _ = _prepare_argv_context(argv)
    return clean, quality


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    try:
        adjusted, quality, actor_note = _prepare_argv_context(raw)
    except (qualidade_abordagem.ApproachQualityError, FeatContextError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2

    if int(quality["bonus"]) == 0 and actor_note is None:
        return _core.main(adjusted)

    # Captura somente stdout para anexar a auditoria contextual na mesma linha.
    # stderr e o código de saída do motor permanecem intactos.
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        status = _core.main(adjusted)
    output = buffer.getvalue().rstrip("\n")
    if status != 0:
        if output:
            print(output)
        return status

    notes: list[str] = []
    if int(quality["bonus"]) != 0:
        notes.append(qualidade_abordagem.annotation(quality))
    if actor_note:
        notes.append(f"[{actor_note}]")
    suffix = " ".join(notes)
    if output and suffix:
        print(f"{output} {suffix}.")
    elif output:
        print(output)
    elif suffix:
        print(suffix + ".")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
