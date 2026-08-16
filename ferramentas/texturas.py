#!/usr/bin/env python3
"""Consulta paletas narrativas compactas de NPCs e locais.

Paletas em ``cenario/texturas`` são apoio descritivo opcional. Elas não substituem
estado, relações, segredos, regras nem eventos pendentes e permanecem pequenas para
que presença literária não exija busca ampla no repositório.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

INDEX_PATH = Path("cenario/texturas/index.yaml")
MAX_FRAGMENT_BYTES = 2 * 1024
KINDS = {"npcs", "locais"}


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def normalize(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = raw.lower().replace("_", " ").replace("-", " ")
    return " ".join(re.findall(r"[a-z0-9]+", raw))


def _score(key: str, entry: dict[str, Any], term: str) -> int:
    query = normalize(term)
    if not query:
        return 0
    values = [normalize(key), normalize(entry.get("nome", ""))]
    aliases = entry.get("aliases") or []
    if isinstance(aliases, list):
        values.extend(normalize(item) for item in aliases)
    values = [value for value in values if value]
    if query in values:
        return 100
    if any(value.startswith(query) for value in values):
        return 85
    if any(query in value for value in values):
        return 70
    tokens = set(query.split())
    if tokens and any(tokens.issubset(set(value.split())) for value in values):
        return 60
    return 0


def lookup(repo: Path, kind: str, term: str) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    """Retorna paleta compacta, fontes e candidatos sem varrer o cenário inteiro."""
    if kind not in KINDS:
        raise ValueError(f"tipo de textura inválido: {kind}")
    index_file = repo / INDEX_PATH
    if not index_file.is_file():
        return None, [], []
    index = load_yaml(index_file) or {}
    mapping = index.get(kind) if isinstance(index, dict) else None
    if not isinstance(mapping, dict):
        return None, [INDEX_PATH.as_posix()], []

    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for key, raw_entry in mapping.items():
        if not isinstance(raw_entry, dict):
            continue
        score = _score(str(key), raw_entry, term)
        if score:
            ranked.append((score, str(key), raw_entry))
    ranked.sort(key=lambda item: (-item[0], item[1]))

    if not ranked:
        query_tokens = set(normalize(term).split())
        candidates: list[str] = []
        for entry in mapping.values():
            if not isinstance(entry, dict):
                continue
            label = str(entry.get("nome") or "")
            haystack = normalize(" ".join([label, *(str(x) for x in entry.get("aliases") or [])]))
            if query_tokens and any(token in haystack for token in query_tokens):
                candidates.append(label)
        return None, [INDEX_PATH.as_posix()], candidates[:8]

    best = ranked[0]
    ties = [item for item in ranked if item[0] == best[0]]
    if len(ties) > 1 and best[0] < 100:
        return None, [INDEX_PATH.as_posix()], [str(item[2].get("nome") or item[1]) for item in ties[:8]]

    _, key, entry = best
    rel = entry.get("arquivo")
    if not isinstance(rel, str):
        raise ValueError(f"textura sem arquivo no índice: {kind}.{key}")
    path = repo / rel
    if not path.is_file():
        raise ValueError(f"fragmento de textura indexado ausente: {rel}")
    size = path.stat().st_size
    limit = int(index.get("limite_fragmento_bytes") or MAX_FRAGMENT_BYTES)
    if size > limit:
        raise ValueError(f"fragmento de textura excede {limit} bytes: {rel} ({size})")

    payload = load_yaml(path)
    if not isinstance(payload, dict):
        raise ValueError(f"fragmento de textura inválido: {rel}")
    result = {
        "id": key,
        "nome": payload.get("nome") or entry.get("nome"),
        "natureza": payload.get("natureza"),
        "autoridade": payload.get("autoridade"),
        "paleta": {
            k: v
            for k, v in payload.items()
            if k not in {"schema_textura", "natureza", "id", "nome", "autoridade"}
        },
    }
    return result, [INDEX_PATH.as_posix(), rel], []


def validate(repo: Path) -> list[str]:
    errors: list[str] = []
    index_file = repo / INDEX_PATH
    if not index_file.is_file():
        return [f"índice de texturas ausente: {INDEX_PATH.as_posix()}"]
    try:
        index = load_yaml(index_file) or {}
    except Exception as exc:
        return [f"índice de texturas inválido: {exc}"]
    limit = int(index.get("limite_fragmento_bytes") or MAX_FRAGMENT_BYTES)
    for kind in KINDS:
        mapping = index.get(kind) or {}
        if not isinstance(mapping, dict):
            errors.append(f"cenario/texturas/index.yaml: {kind} não é mapa")
            continue
        for key, entry in mapping.items():
            if not isinstance(entry, dict) or not isinstance(entry.get("arquivo"), str):
                errors.append(f"textura inválida no índice: {kind}.{key}")
                continue
            path = repo / entry["arquivo"]
            if not path.is_file():
                errors.append(f"fragmento de textura ausente: {entry['arquivo']}")
                continue
            if path.stat().st_size > limit:
                errors.append(f"fragmento de textura grande demais: {entry['arquivo']}")
            try:
                payload = load_yaml(path)
            except Exception as exc:
                errors.append(f"fragmento de textura inválido {entry['arquivo']}: {exc}")
                continue
            if not isinstance(payload, dict) or payload.get("id") != key:
                errors.append(f"id de textura divergente: {entry['arquivo']}")
    return errors
