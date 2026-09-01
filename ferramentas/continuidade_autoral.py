#!/usr/bin/env python3
"""Valida o registro frio de compromissos de continuidade autoral.

O registro não descobre personagens em prosa e não automatiza julgamento
narrativo. Ele torna verificáveis as decisões já identificadas: cada compromisso
aponta para sua âncora canônica, declara um estado deliberado e possui um destino
operacional ou uma justificativa explícita para não tê-lo.

Esta ferramenta pertence a manutenção/CI. Ela é read-only e não integra o hot
path de turno, checkpoint ou lifecycle de sessão.
"""
from __future__ import annotations

import argparse
import copy
import difflib
import re
import unicodedata
from pathlib import Path
from typing import Any

import yaml

REGISTRY = Path("narrador/continuidade-autoral.yaml")
SCHEMA = 1
NATURE = "indice_reservado_de_compromissos"
OPEN_STATES = {
    "aberto_em_jogo",
    "dormente_deliberado",
    "reservado_nao_materializado",
}
CLOSED_STATE = "encerrado"
ALLOWED_STATES = OPEN_STATES | {CLOSED_STATE}
STABLE_ID = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")


class ContinuityError(ValueError):
    """Contrato estrutural inválido no registro de continuidade."""


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContinuityError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise ContinuityError(f"YAML inválido em {path}: {exc}") from exc


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContinuityError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContinuityError(f"{label} deve ser lista")
    return value


def _nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContinuityError(f"{label} deve ser texto não vazio")
    return value.strip()


def _normalize_lookup(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return "_".join(re.findall(r"[a-z0-9]+", ascii_value.casefold()))


def _safe_relative_path(value: Any, label: str) -> Path:
    text = _nonempty(value, label)
    path = Path(text)
    if path.is_absolute() or ".." in path.parts:
        raise ContinuityError(f"{label} deve ser caminho relativo interno ao repo")
    return path


def _resolve_dotted(data: Any, dotted: str, label: str) -> Any:
    current = data
    for part in dotted.split("."):
        if not part or not isinstance(current, dict) or part not in current:
            raise ContinuityError(f"{label} aponta para chave inexistente: {dotted}")
        current = current[part]
    return current


def _validate_pointer(
    repo: Path,
    pointer: Any,
    label: str,
    cache: dict[Path, Any],
) -> tuple[Path, str]:
    item = _mapping(pointer, label)
    rel = _safe_relative_path(item.get("arquivo"), f"{label}.arquivo")
    dotted = _nonempty(item.get("chave"), f"{label}.chave")
    path = repo / rel
    if rel not in cache:
        cache[rel] = _load(path)
    _resolve_dotted(cache[rel], dotted, label)
    return rel, dotted


def load_registry(repo: Path) -> dict[str, Any]:
    data = _mapping(_load(repo / REGISTRY), REGISTRY.as_posix())
    if data.get("schema_continuidade_autoral") != SCHEMA:
        raise ContinuityError(
            f"registro deve usar schema_continuidade_autoral: {SCHEMA}"
        )
    if data.get("natureza") != NATURE:
        raise ContinuityError(f"registro deve ter natureza: {NATURE}")
    _mapping(data.get("cobertura"), "cobertura")
    _mapping(data.get("compromissos"), "compromissos")
    return data


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    counts = {
        "compromissos": 0,
        "abertos": 0,
        "dormentes": 0,
        "reservados": 0,
        "encerrados": 0,
        "fontes_cobertas": 0,
    }
    try:
        registry = load_registry(repo)
        coverage = registry["cobertura"]
        source_rel = _safe_relative_path(
            coverage.get("fonte_canonica"), "cobertura.fonte_canonica"
        )
        source = _mapping(_load(repo / source_rel), source_rel.as_posix())
        ignored = {
            _nonempty(item, "cobertura.chaves_nao_narrativas[]")
            for item in _list(
                coverage.get("chaves_nao_narrativas"),
                "cobertura.chaves_nao_narrativas",
            )
        }
        unknown_ignored = sorted(ignored - set(source))
        if unknown_ignored:
            raise ContinuityError(
                "cobertura ignora chaves inexistentes: " + ", ".join(unknown_ignored)
            )
        narrative_keys = set(source) - ignored
        if not narrative_keys:
            raise ContinuityError("cobertura não encontrou chaves narrativas")

        commitments = registry["compromissos"]
        cache: dict[Path, Any] = {source_rel: source}
        covered_keys: set[str] = set()
        pointer_signatures: set[tuple[str, str, str]] = set()
        state_counts = {state: 0 for state in ALLOWED_STATES}

        for commitment_id, raw in commitments.items():
            if not isinstance(commitment_id, str) or not STABLE_ID.fullmatch(commitment_id):
                raise ContinuityError(
                    f"ID de compromisso instável: {commitment_id!r}"
                )
            item = _mapping(raw, f"compromissos.{commitment_id}")
            _nonempty(item.get("tipo"), f"{commitment_id}.tipo")
            queries = [
                _normalize_lookup(_nonempty(value, f"{commitment_id}.consultas[]"))
                for value in _list(item.get("consultas"), f"{commitment_id}.consultas")
            ]
            if not queries or any(not query for query in queries):
                raise ContinuityError(f"{commitment_id} deve possuir consulta dirigida")
            if len(queries) != len(set(queries)):
                raise ContinuityError(f"{commitment_id} possui consultas duplicadas")
            state = _nonempty(item.get("estado"), f"{commitment_id}.estado")
            if state not in ALLOWED_STATES:
                raise ContinuityError(
                    f"{commitment_id}.estado inválido: {state!r}"
                )
            state_counts[state] += 1

            anchors = _list(item.get("ancoras"), f"{commitment_id}.ancoras")
            if not anchors:
                raise ContinuityError(f"{commitment_id} deve possuir ao menos uma âncora")
            for index, pointer in enumerate(anchors):
                rel, dotted = _validate_pointer(
                    repo,
                    pointer,
                    f"{commitment_id}.ancoras[{index}]",
                    cache,
                )
                signature = (commitment_id, rel.as_posix(), dotted)
                if signature in pointer_signatures:
                    raise ContinuityError(f"{commitment_id} possui âncora duplicada")
                pointer_signatures.add(signature)
                if rel == source_rel:
                    top_key = dotted.split(".", 1)[0]
                    if top_key in narrative_keys:
                        covered_keys.add(top_key)

            destinations = _list(
                item.get("destinos_operacionais", []),
                f"{commitment_id}.destinos_operacionais",
            )
            for index, pointer in enumerate(destinations):
                _validate_pointer(
                    repo,
                    pointer,
                    f"{commitment_id}.destinos_operacionais[{index}]",
                    cache,
                )
            no_destination = item.get("sem_destino_operacional")
            if bool(destinations) == bool(no_destination):
                raise ContinuityError(
                    f"{commitment_id} deve declarar destinos_operacionais ou "
                    "sem_destino_operacional, exclusivamente"
                )
            if no_destination is not None:
                _nonempty(no_destination, f"{commitment_id}.sem_destino_operacional")

            resume = _mapping(item.get("retomada"), f"{commitment_id}.retomada")
            mode = _nonempty(resume.get("modo"), f"{commitment_id}.retomada.modo")
            if state in OPEN_STATES:
                if mode != "gatilho_causal":
                    raise ContinuityError(
                        f"{commitment_id} está {state} e exige retomada por gatilho_causal"
                    )
                _nonempty(resume.get("gatilho"), f"{commitment_id}.retomada.gatilho")
                if "motivo" in resume:
                    raise ContinuityError(
                        f"{commitment_id} aberto não deve usar motivo de encerramento"
                    )
            else:
                if mode != "nenhuma":
                    raise ContinuityError(
                        f"{commitment_id} encerrado exige retomada.modo: nenhuma"
                    )
                _nonempty(resume.get("motivo"), f"{commitment_id}.retomada.motivo")
                if "gatilho" in resume:
                    raise ContinuityError(
                        f"{commitment_id} encerrado não deve declarar gatilho"
                    )

        missing = sorted(narrative_keys - covered_keys)
        if missing:
            raise ContinuityError(
                "chaves canônicas sem compromisso de continuidade: " + ", ".join(missing)
            )

        counts = {
            "compromissos": len(commitments),
            "abertos": state_counts["aberto_em_jogo"],
            "dormentes": state_counts["dormente_deliberado"],
            "reservados": state_counts["reservado_nao_materializado"],
            "encerrados": state_counts["encerrado"],
            "fontes_cobertas": len(narrative_keys),
        }
    except ContinuityError as exc:
        errors.append(str(exc))
    return {"ok": not errors, **counts, "erros": errors}


def lookup(repo: Path, term: str, *, limit: int = 3) -> tuple[dict[str, Any], list[str]]:
    """Resolve um compromisso exato e abre somente suas âncoras canônicas.

    O roteamento é deliberadamente explícito: não há fuzzy matching para escolher
    uma verdade. Aproximação serve apenas para sugerir consultas possíveis.
    """
    registry = load_registry(repo)
    commitments = registry["compromissos"]
    routes: dict[str, list[str]] = {}
    display: dict[str, str] = {}
    for commitment_id, raw in commitments.items():
        item = _mapping(raw, f"compromissos.{commitment_id}")
        raw_queries = _list(item.get("consultas"), f"{commitment_id}.consultas")
        for raw_query in raw_queries:
            label = _nonempty(raw_query, f"{commitment_id}.consultas[]")
            key = _normalize_lookup(label)
            if not key:
                raise ContinuityError(f"{commitment_id} possui consulta inválida")
            routes.setdefault(key, []).append(commitment_id)
            display.setdefault(key, label)
        routes.setdefault(_normalize_lookup(commitment_id), []).append(commitment_id)
        display.setdefault(_normalize_lookup(commitment_id), commitment_id)

    query = _normalize_lookup(term)
    selected_ids = list(dict.fromkeys(routes.get(query, [])))
    if len(selected_ids) > limit:
        raise ContinuityError(
            f"consulta ambígua demais para resposta dirigida: {term!r} "
            f"({len(selected_ids)} compromissos)"
        )
    if not selected_ids:
        close = difflib.get_close_matches(query, sorted(routes), n=8, cutoff=0.48)
        return (
            {
                "encontrado": False,
                "visibilidade": "narrador",
                "candidatos": [display[key] for key in close],
            },
            [REGISTRY.as_posix()],
        )

    cache: dict[Path, Any] = {}
    sources = [REGISTRY.as_posix()]
    results: list[dict[str, Any]] = []
    for commitment_id in selected_ids:
        item = _mapping(commitments[commitment_id], f"compromissos.{commitment_id}")
        truths: list[dict[str, Any]] = []
        for index, pointer in enumerate(
            _list(item.get("ancoras"), f"{commitment_id}.ancoras")
        ):
            rel, dotted = _validate_pointer(
                repo,
                pointer,
                f"{commitment_id}.ancoras[{index}]",
                cache,
            )
            sources.append(rel.as_posix())
            truths.append(
                {
                    "arquivo": rel.as_posix(),
                    "chave": dotted,
                    "valor": copy.deepcopy(
                        _resolve_dotted(cache[rel], dotted, commitment_id)
                    ),
                }
            )
        result = {
            "id": commitment_id,
            "tipo": item.get("tipo"),
            "estado": item.get("estado"),
            "retomada": item.get("retomada"),
            "verdade_canonica": truths,
        }
        if item.get("destinos_operacionais"):
            result["destinos_operacionais"] = item["destinos_operacionais"]
        if item.get("sem_destino_operacional"):
            result["sem_destino_operacional"] = item["sem_destino_operacional"]
        results.append(result)

    return (
        {
            "encontrado": True,
            "visibilidade": "narrador",
            "regra_de_exposicao": (
                "Verdade reservada não vira conhecimento de Ren nem texto visível "
                "sem descoberta legítima."
            ),
            "compromissos": results,
        },
        list(dict.fromkeys(sources)),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("comando", choices=["check", "status"])
    args = parser.parse_args(argv)
    result = validate_repo(args.repo.resolve())
    if args.comando == "status":
        result["fontes_lidas"] = [REGISTRY.as_posix()]
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
