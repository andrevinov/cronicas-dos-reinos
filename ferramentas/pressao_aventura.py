#!/usr/bin/env python3
"""Pressão determinística contra seca de incidentes locais.

A pressão é uma heurística operacional, não cânone. Ela mede quantas cenas locais
confirmadas consecutivas terminaram sem sequer produzir um candidato de
microevento. Não usa relógio, sessão, transcrição ou inferência semântica.

O efeito só existe quando outra cena local já está sendo preparada: níveis mais
altos podem promover algumas fichas `rotina_*` do baralho de ocorrência para
`microevento`. Nada é criado fora da abertura de cena e o resultado continua
sendo apenas candidato sujeito aos guardrails do baralho local.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

THRESHOLDS = ((0, 0), (4, 1), (6, 2), (8, 3))
LEVEL_NAMES = {0: "normal", 1: "leve", 2: "alta", 3: "critica"}
PROMOTED_ROUTINE_TOKENS = {
    0: set(),
    1: {"rotina_03"},
    2: {"rotina_02", "rotina_03"},
    3: {"rotina_01", "rotina_02", "rotina_03"},
}
MAX_DRY_STREAK_REPORTED = 64


class AdventurePressureError(ValueError):
    """Erro de contrato da pressão de seca."""


def dry_streak(history: list[Any]) -> int:
    streak = 0
    for raw in reversed(history):
        if not isinstance(raw, dict):
            continue
        result = raw.get("resultado")
        if result == "rotina":
            streak += 1
            continue
        if result == "microevento":
            break
    return min(streak, MAX_DRY_STREAK_REPORTED)


def level_for(streak: int) -> int:
    if not isinstance(streak, int) or isinstance(streak, bool) or streak < 0:
        raise AdventurePressureError("seca deve ser inteiro >= 0")
    level = 0
    for minimum, candidate in THRESHOLDS:
        if streak >= minimum:
            level = candidate
    return level


def status_from_history(history: list[Any]) -> dict[str, Any]:
    streak = dry_streak(history)
    level = level_for(streak)
    return {
        "nivel": level,
        "nome": LEVEL_NAMES[level],
        "cenas_secas_consecutivas": streak,
        "fichas_rotina_promoviveis": sorted(PROMOTED_ROUTINE_TOKENS[level]),
        "critica": level == 3,
        "regra": (
            "Mede ausência de candidatos locais, não ausência de fatos canônicos. "
            "Só modifica o próximo sorteio quando uma cena local já existe."
        ),
    }


def apply(
    history: list[Any],
    *,
    token_id: str,
    base_result: str,
) -> dict[str, Any]:
    if base_result not in {"rotina", "microevento"}:
        raise AdventurePressureError(f"resultado-base inválido: {base_result}")
    pressure = status_from_history(history)
    promoted = (
        base_result == "rotina"
        and token_id in PROMOTED_ROUTINE_TOKENS[pressure["nivel"]]
    )
    return {
        **pressure,
        "ficha": token_id,
        "resultado_base": base_result,
        "promovido": promoted,
        "resultado": "microevento" if promoted else base_result,
    }


def status(repo: Path) -> dict[str, Any]:
    # Import local evita ciclo de importação: microeventos_locais usa este módulo.
    import microeventos_locais

    index = microeventos_locais.load_index(repo)
    state = microeventos_locais.load_state(repo, index)
    result = status_from_history(list(state.get("historico_recente") or []))
    return {
        "ok": True,
        "pressao_aventura": result,
        "fontes_lidas": [
            microeventos_locais.INDEX.as_posix(),
            microeventos_locais.STATE.as_posix(),
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("cmd", choices=["status"])
    args = parser.parse_args(argv)
    try:
        print(yaml.safe_dump(status(args.repo.resolve()), allow_unicode=True, sort_keys=False), end="")
        return 0
    except AdventurePressureError as exc:
        print(f"ERRO: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
