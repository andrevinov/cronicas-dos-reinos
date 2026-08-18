#!/usr/bin/env python3
"""Classifica o cânone já existente antes de criar novos atores do Mundo Vivo.

Esta ferramenta é de manutenção/CI, não pertence ao hot path. Ela garante que
cada relação atual tenha uma decisão explícita: agente leve, coberta por um
agente-pai ou persistente sem agenda. Importância narrativa não implica scheduler.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

POPULATION = Path("narrador/populacao-canonica.yaml")
RELATIONS = Path("estado/relacoes/index.yaml")
STRATEGIC = Path("narrador/agentes/index.yaml")
LIGHT = Path("narrador/agentes-leves/index.yaml")


class PopulationError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PopulationError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise PopulationError(f"YAML inválido em {path}: {exc}") from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PopulationError(f"{label} deve ser mapa")
    return value


def _ids(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise PopulationError(f"{label} deve ser lista")
    result: list[str] = []
    for i, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise PopulationError(f"{label}[{i}] deve ser ID não vazio")
        result.append(item.strip())
    if len(result) != len(set(result)):
        raise PopulationError(f"{label} não pode conter duplicatas")
    return result


def load_population(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / POPULATION), POPULATION.as_posix())
    if data.get("schema_populacao_canonica") != 1:
        raise PopulationError("inventário deve usar schema_populacao_canonica: 1")
    if data.get("natureza") != "inventario_reservado":
        raise PopulationError("inventário deve ter natureza: inventario_reservado")
    if data.get("origem") != RELATIONS.as_posix():
        raise PopulationError("inventário deve declarar estado/relacoes/index.yaml como origem")
    classes = _map(data.get("classificacoes"), "classificacoes")
    _ids(classes.get("promovidos_agentes_leves"), "promovidos_agentes_leves")
    _ids(classes.get("persistentes_sem_agenda"), "persistentes_sem_agenda")
    represented = _map(classes.get("representados_por_agente"), "representados_por_agente")
    for child, parent in represented.items():
        if not isinstance(child, str) or not child.strip():
            raise PopulationError("representados_por_agente contém filho inválido")
        if not isinstance(parent, str) or not parent.strip():
            raise PopulationError(f"{child}: agente-pai inválido")
    return data


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    counts = {"relacoes": 0, "promovidos": 0, "representados": 0, "persistentes": 0}
    try:
        population = load_population(repo)
        relation_doc = _map(_load(repo / RELATIONS), RELATIONS.as_posix())
        if relation_doc.get("schema_relacoes") != 2:
            raise PopulationError("índice de relações deve usar schema_relacoes: 2")
        relations = _map(relation_doc.get("relacoes"), "relacoes")
        if relation_doc.get("quantidade") != len(relations):
            raise PopulationError("estado/relacoes/index.yaml possui quantidade divergente")

        strategic_doc = _map(_load(repo / STRATEGIC), STRATEGIC.as_posix())
        light_doc = _map(_load(repo / LIGHT), LIGHT.as_posix())
        strategic = set(_map(strategic_doc.get("agentes"), "agentes estratégicos"))
        light = set(_map(light_doc.get("agentes"), "agentes leves"))

        classes = population["classificacoes"]
        promoted = set(_ids(classes["promovidos_agentes_leves"], "promovidos_agentes_leves"))
        persistent = set(_ids(classes["persistentes_sem_agenda"], "persistentes_sem_agenda"))
        represented = dict(classes["representados_por_agente"])
        represented_ids = set(represented)

        overlaps = (promoted & persistent) | (promoted & represented_ids) | (persistent & represented_ids)
        if overlaps:
            raise PopulationError("classificações sobrepostas: " + ", ".join(sorted(overlaps)))

        classified = promoted | persistent | represented_ids
        relation_ids = set(relations)
        missing = sorted(relation_ids - classified)
        extra = sorted(classified - relation_ids)
        if missing or extra:
            raise PopulationError(f"cobertura incompleta; ausentes={missing}, extras={extra}")

        if not promoted <= light:
            raise PopulationError("promovidos ausentes do índice leve: " + ", ".join(sorted(promoted - light)))
        relation_light = relation_ids & light
        if relation_light != promoted:
            raise PopulationError(
                "relações agendadas como leves divergem do inventário; "
                f"somente_indice={sorted(relation_light-promoted)}, somente_inventario={sorted(promoted-relation_light)}"
            )

        scheduled = strategic | light
        invalid_persistent = sorted(persistent & scheduled)
        if invalid_persistent:
            raise PopulationError(
                "persistentes sem agenda aparecem em scheduler: " + ", ".join(invalid_persistent)
            )

        known_parents = strategic | light
        for child, parent in represented.items():
            if child == parent:
                raise PopulationError(f"{child}: não pode representar a si mesmo")
            if child in scheduled:
                raise PopulationError(f"{child}: representado por agente não deve possuir scheduler próprio")
            if parent not in known_parents:
                raise PopulationError(f"{child}: agente-pai inexistente: {parent}")

        counts = {
            "relacoes": len(relation_ids),
            "promovidos": len(promoted),
            "representados": len(represented_ids),
            "persistentes": len(persistent),
        }
    except PopulationError as exc:
        errors.append(str(exc))
    return {"ok": not errors, **counts, "erros": errors}


def status(repo: Path) -> dict[str, Any]:
    result = validate_repo(repo)
    return {
        **result,
        "fontes_lidas": [
            POPULATION.as_posix(),
            RELATIONS.as_posix(),
            STRATEGIC.as_posix(),
            LIGHT.as_posix(),
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("comando", choices=["status", "validar"])
    args = parser.parse_args(argv)
    result = status(args.repo.resolve()) if args.comando == "status" else validate_repo(args.repo.resolve())
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
