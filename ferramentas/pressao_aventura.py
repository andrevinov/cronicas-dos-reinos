#!/usr/bin/env python3
"""Pressão determinística contra seca de incidentes locais.

A pressão é uma heurística operacional, não cânone. Ela mede quantas cenas locais
confirmadas consecutivas terminaram sem sequer produzir um candidato de
microevento. Não usa relógio, sessão, transcrição ou inferência semântica.

O efeito primário existe quando outra cena local já está sendo preparada: níveis
mais altos podem promover algumas fichas `rotina_*` do baralho de ocorrência para
`microevento`. O Side Quest Gate v2 também pode consultar a mesma pressão como
modificador de raridade, sem criar encontro, oferta ou missão por conta própria.
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
MICROEVENT_STATE = Path("narrador/microeventos-locais/estado.yaml")


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
            "Só modifica um gate reativo que já tenha sido legitimamente acionado."
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


def _gate_history(repo: Path) -> tuple[list[Any], list[str], bool]:
    """Lê só o estado já existente; não abre catálogo/ecologia para o gate v2."""
    path = repo / MICROEVENT_STATE
    layer_dir = path.parent
    if not layer_dir.exists():
        return [], [], False
    if not path.is_file():
        raise AdventurePressureError(
            "camada de microeventos locais declarada parcialmente: estado ausente"
        )
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise AdventurePressureError(str(exc)) from exc
    if not isinstance(data, dict):
        raise AdventurePressureError("estado de microeventos locais deve ser mapa")
    if (
        data.get("schema_estado_microeventos_locais") != 1
        or data.get("natureza") != "controle_reservado"
    ):
        raise AdventurePressureError("estado de microeventos locais inválido")
    history = data.get("historico_recente")
    if not isinstance(history, list) or len(history) > MAX_DRY_STREAK_REPORTED:
        raise AdventurePressureError("historico_recente de microeventos inválido")
    for i, raw in enumerate(history):
        if not isinstance(raw, dict):
            raise AdventurePressureError(f"historico_recente[{i}] deve ser mapa")
        if raw.get("resultado") not in {"rotina", "microevento"}:
            raise AdventurePressureError(
                f"historico_recente[{i}].resultado inválido para pressão"
            )
    return history, [MICROEVENT_STATE.as_posix()], True


def status_for_gate(repo: Path) -> dict[str, Any]:
    """Consulta mínima para gates reativos; camada ausente equivale a nível zero."""
    history, sources, configured = _gate_history(repo)
    return {
        "ok": True,
        "configurado": configured,
        "pressao_aventura": status_from_history(history),
        "fontes_lidas": sources,
    }


def status(repo: Path) -> dict[str, Any]:
    # A consulta de manutenção valida o subsistema completo; o gate usa status_for_gate.
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
