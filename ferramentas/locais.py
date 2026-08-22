#!/usr/bin/env python3
"""Identidade canônica de locais com aliases determinísticos e sem scan.

O registro é pequeno e dirigido. Resolver um alias nunca cria local, recompensa,
presença ou fato; apenas devolve o id estável que as demais camadas devem usar.
"""
from __future__ import annotations

import argparse
import difflib
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import yaml

INDEX = Path("cenario/locais/index.yaml")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,95}$")


class LocationError(ValueError):
    pass


def configured(repo: Path) -> bool:
    return (repo / INDEX).is_file()


def declared(repo: Path) -> bool:
    """Distingue fixture sem a camada de uma configuração parcial/quebrada."""
    return (repo / INDEX.parent).exists()


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise LocationError(str(exc)) from exc


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LocationError(f"{label} deve ser texto não vazio")
    return value.strip()


def _normalize(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", _text(value, "referência de local").casefold())
    plain = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return "_".join(re.findall(r"[a-z0-9]+", plain))


def _id(value: Any) -> str:
    value = _text(value, "local_id")
    if not ID_RE.fullmatch(value):
        raise LocationError(
            "local_id canônico deve usar minúsculas ASCII, números, _ ou - (máx. 96)"
        )
    return value


def load_index(repo: Path) -> dict[str, Any]:
    data = _load(repo / INDEX)
    if not isinstance(data, dict):
        raise LocationError("índice de locais deve ser mapa")
    if (
        data.get("schema_locais") != 1
        or data.get("natureza") != "roteador_canonico"
        or data.get("regra") != "alias_nunca_cria_novo_local"
    ):
        raise LocationError("índice canônico de locais inválido")
    mapping = data.get("locais")
    if not isinstance(mapping, dict) or not mapping:
        raise LocationError("índice canônico de locais vazio")

    owners: dict[str, str] = {}
    for raw_id, raw_meta in mapping.items():
        local_id = _id(raw_id)
        if not isinstance(raw_meta, dict):
            raise LocationError(f"locais.{local_id} deve ser mapa")
        name = _text(raw_meta.get("nome"), f"locais.{local_id}.nome")
        aliases = raw_meta.get("aliases") or []
        if not isinstance(aliases, list):
            raise LocationError(f"locais.{local_id}.aliases deve ser lista")
        labels = [local_id, name, *aliases]
        for raw_label in labels:
            label = _normalize(raw_label)
            previous = owners.get(label)
            if previous is not None and previous != local_id:
                raise LocationError(
                    f"alias de local ambíguo {raw_label!r}: {previous} e {local_id}"
                )
            owners[label] = local_id
    data["_aliases"] = owners
    return data


def resolve(repo: Path, supplied: Any) -> dict[str, Any]:
    raw = _text(supplied, "referência de local")

    # Fixtures antigos que não modelam locais continuam podendo exercitar as
    # outras camadas com um ID explícito. Se a pasta cenario/locais existir,
    # porém, a ausência/invalidade do índice é erro: produção permanece fail-closed.
    if not declared(repo):
        legacy = _id(raw)
        return {
            "local_id": legacy,
            "recebido": raw,
            "resolucao": "fixture_sem_registro",
            "nome": legacy,
            "fontes_lidas": [],
        }

    index = load_index(repo)
    mapping = index["locais"]
    if raw in mapping:
        return {
            "local_id": raw,
            "recebido": raw,
            "resolucao": "id_exato",
            "nome": mapping[raw]["nome"],
            "fontes_lidas": [INDEX.as_posix()],
        }

    query = _normalize(raw)
    canonical = index["_aliases"].get(query)
    if canonical is not None:
        return {
            "local_id": canonical,
            "recebido": raw,
            "resolucao": "alias_canonico",
            "nome": mapping[canonical]["nome"],
            "fontes_lidas": [INDEX.as_posix()],
        }

    labels = sorted(index["_aliases"])
    close = difflib.get_close_matches(query, labels, n=4, cutoff=0.68)
    suggestions: list[str] = []
    for label in close:
        candidate = index["_aliases"][label]
        if candidate not in suggestions:
            suggestions.append(candidate)
    suffix = f"; sugestão: {', '.join(suggestions[:3])}" if suggestions else ""
    raise LocationError(
        f"local desconhecido: {raw!r}{suffix}. Local não cadastrado nunca cria novo id por aproximação."
    )


def is_canonical(repo: Path, supplied: Any) -> bool:
    raw = _text(supplied, "local_id")
    index = load_index(repo)
    return raw in index["locais"]


def validate_consumers(repo: Path) -> list[str]:
    """Valida consumidores persistidos sem varrer diretórios narrativos."""
    errors: list[str] = []
    index = load_index(repo)
    canonical = set(index["locais"])

    def require(value: Any, label: str) -> None:
        if not isinstance(value, str) or value not in canonical:
            errors.append(f"{label}: local_id não canônico: {value!r}")

    reward_index = repo / "narrador/recompensas/index.yaml"
    if reward_index.is_file():
        data = _load(reward_index) or {}
        maps = data.get("mapas") if isinstance(data, dict) else None
        if isinstance(maps, dict):
            for local_id in maps:
                require(local_id, f"narrador/recompensas/index.yaml mapas.{local_id}")

    item_index = repo / "narrador/recompensas/itens-index.yaml"
    if item_index.is_file():
        data = _load(item_index) or {}
        rewards = data.get("recompensas") if isinstance(data, dict) else None
        if isinstance(rewards, dict):
            for reward_id, meta in rewards.items():
                if isinstance(meta, dict):
                    require(meta.get("local_id"), f"itens-index.{reward_id}.local_id")

    planned_path = repo / "narrador/recompensas/planejadas.yaml"
    if planned_path.is_file():
        data = _load(planned_path) or {}
        by_place = data.get("por_local") if isinstance(data, dict) else None
        if isinstance(by_place, dict):
            for local_id in by_place:
                require(local_id, f"planejadas.por_local.{local_id}")

    texture_index = repo / "cenario/texturas/index.yaml"
    if texture_index.is_file():
        data = _load(texture_index) or {}
        locations = data.get("locais") if isinstance(data, dict) else None
        if isinstance(locations, dict):
            for local_id in locations:
                require(local_id, f"cenario/texturas/index.yaml locais.{local_id}")
    return errors


def check(repo: Path) -> dict[str, Any]:
    try:
        index = load_index(repo)
        errors = validate_consumers(repo)
    except LocationError as exc:
        return {"ok": False, "erros": [str(exc)], "locais": 0}
    return {
        "ok": not errors,
        "erros": errors,
        "locais": len(index["locais"]),
        "fontes_lidas": [INDEX.as_posix()],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)
    resolver = sub.add_parser("resolver", help="resolve id/nome/alias para id canônico")
    resolver.add_argument("referencia")
    sub.add_parser("check", help="valida registro e consumidores persistidos")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        result = resolve(repo, args.referencia) if args.cmd == "resolver" else check(repo)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0 if result.get("ok", True) else 1
    except LocationError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
