#!/usr/bin/env python3
"""Compatibilidade estreita para contratos operacionais observados em rollout.

Esta camada normaliza somente representações de borda que são inequivocamente
sinônimas. Ela não altera o calendário canônico, não inventa datas e não tenta
adivinhar entradas ambíguas. O formato persistido continua sendo o formato de
Harptos usado pelo repositório.
"""
from __future__ import annotations

import re
from typing import Any

MONTHS = (
    "Hammer",
    "Alturiak",
    "Ches",
    "Tarsakh",
    "Mirtul",
    "Kythorn",
    "Flamerule",
    "Eleasis",
    "Eleint",
    "Marpenoth",
    "Uktar",
    "Nightal",
)
_MONTH_BY_CASEFOLD = {month.casefold(): month for month in MONTHS}
_DATE_EXAMPLES = "'17 Eleasis, 1372 DR', '1372-08-17' ou '17/08/1372'"
_TICKET_ID_RE = re.compile(r"^[0-9a-f]{20}$")


class OperationalContractError(ValueError):
    """Entrada operacional reconhecível, mas incompatível com o contrato público."""


def _month_number(value: str) -> str:
    number = int(value)
    if not 1 <= number <= len(MONTHS):
        raise OperationalContractError(
            f"mês numérico de Harptos deve estar entre 1 e 12; use {_DATE_EXAMPLES}"
        )
    return MONTHS[number - 1]


def _validate_day(day: int, month: str) -> None:
    if not 1 <= day <= 30:
        raise OperationalContractError(
            f"dia inválido para {month}: {day}; meses de Harptos aceitos aqui usam dias 1–30"
        )


def normalize_date(value: Any) -> str:
    """Converte aliases operacionais inequívocos para a grafia canônica de mês.

    Formatos aceitos:
    - ``17 Eleasis, 1372 DR`` (canônico);
    - ``17 eleasis 1372`` / ``17 Eleasis 1372 DR``;
    - ``1372-08-17`` (ano-mês-dia; 08 = Eleasis);
    - ``17/08/1372`` ou ``17-08-1372`` (dia-mês-ano).

    Datas intercalárias/festivais continuam usando sua forma canônica e são
    deixadas para o parser do calendário existente.
    """
    if not isinstance(value, str) or not value.strip():
        raise OperationalContractError(f"data deve ser texto não vazio; use {_DATE_EXAMPLES}")
    text = " ".join(value.strip().split())

    named = re.fullmatch(
        r"(\d{1,2})\s+([A-Za-zÀ-ÿ'-]+),?\s+(\d+)\s*(?:DR)?",
        text,
        flags=re.IGNORECASE,
    )
    if named:
        day = int(named.group(1))
        raw_month = named.group(2)
        month = _MONTH_BY_CASEFOLD.get(raw_month.casefold())
        if month is None:
            raise OperationalContractError(
                f"mês de Harptos não reconhecido: {raw_month!r}; use {_DATE_EXAMPLES}"
            )
        _validate_day(day, month)
        return f"{day} {month}, {int(named.group(3))} DR"

    iso = re.fullmatch(r"(\d{1,4})-(\d{1,2})-(\d{1,2})", text)
    if iso:
        year = int(iso.group(1))
        month = _month_number(iso.group(2))
        day = int(iso.group(3))
        _validate_day(day, month)
        return f"{day} {month}, {year} DR"

    day_first = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{1,4})", text)
    if day_first:
        day = int(day_first.group(1))
        month = _month_number(day_first.group(2))
        year = int(day_first.group(3))
        _validate_day(day, month)
        return f"{day} {month}, {year} DR"

    # Festivais como ``Midsummer, 1372 DR`` não são aliases numéricos; o parser
    # canônico existente deve continuar decidindo sua validade.
    return text


def explain_ticket_argument(value: Any) -> str:
    """Valida o transporte público de ``--ticket`` antes do decoder binário.

    O checksum curto exposto como ``ticket_id`` é diagnóstico e não contém bytes
    suficientes para reconstruir o ticket. Detectá-lo aqui evita cascata de
    ``--help``/leitura de código depois de um erro genérico de prefixo.
    """
    if not isinstance(value, str) or not value.strip():
        raise OperationalContractError(
            "--ticket exige o valor completo do campo `ticket:` devolvido por `cronica preparar`"
        )
    text = value.strip()
    if text.startswith("ticket:"):
        token = text[len("ticket:") :].strip()
        if token.startswith("crn1."):
            return token
        raise OperationalContractError(
            "a linha `ticket:` não contém um token `crn1.` completo; copie a linha inteira da saída de `cronica preparar`"
        )
    if _TICKET_ID_RE.fullmatch(text):
        raise OperationalContractError(
            "foi fornecido apenas `ticket_id` (checksum de 20 caracteres). "
            "`--ticket` exige o campo `ticket:` completo, iniciado por `crn1.`; "
            "reuse exatamente esse campo da saída de `cronica preparar` e não chame `--help` nem leia código"
        )
    if text.startswith("ticket_id:"):
        raise OperationalContractError(
            "`--ticket` recebeu a linha `ticket_id:`. Use o valor da linha `ticket:` completa "
            "da mesma saída de `cronica preparar`"
        )
    return text
