#!/usr/bin/env python3
"""Consulta paletas narrativas compactas de NPCs e locais.

Paletas em ``cenario/texturas`` são apoio descritivo opcional. Elas não substituem
estado, relações, segredos, regras nem eventos pendentes e permanecem pequenas para
que presença literária não exija busca ampla no repositório.

Papéis conversacionais compactos podem viver inline no mesmo índice já consultado
por ``contexto.py npc``. Eles orientam o ângulo de resposta de NPCs recorrentes sem
criar conhecimento, roteiro ou nova leitura de fragmento.
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

import locais

INDEX_PATH = Path("cenario/texturas/index.yaml")
MAX_FRAGMENT_BYTES = 2 * 1024
KINDS = {"npcs", "locais"}
CONVERSATION_ROLES = {
    "clinico_pratico",
    "espelho_afetivo",
    "guardia_pragmatica",
    "institucional_probatorio",
    "operacional_civico",
    "pastoral_moral",
    "patrono_pragmatico",
    "sobrevivencia_civil",
}
CONVERSATION_LIST_FIELDS = ("prioriza", "forma_de_responder", "evita")
MAX_CONVERSATION_ITEMS = 3
MAX_CONVERSATION_TEXT = 220
CONVERSATION_AUTHORITY = (
    "Perfil interpretativo: orienta o ângulo da resposta quando o NPC legitimamente "
    "pode aconselhar. Não cria conhecimento, fato, segredo, competência ou decisão."
)


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


def _conversation_profile(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} precisa ser mapa")
    allowed = {"papel", *CONVERSATION_LIST_FIELDS, "limite_de_autoridade"}
    extra = sorted(set(value) - allowed)
    if extra:
        raise ValueError(f"{label} possui campos desconhecidos: {', '.join(extra)}")

    role = value.get("papel")
    if role not in CONVERSATION_ROLES:
        raise ValueError(f"{label}.papel inválido: {role!r}")

    result: dict[str, Any] = {"papel": role}
    for field in CONVERSATION_LIST_FIELDS:
        items = value.get(field)
        if (
            not isinstance(items, list)
            or not items
            or len(items) > MAX_CONVERSATION_ITEMS
            or any(not isinstance(item, str) or not item.strip() for item in items)
        ):
            raise ValueError(
                f"{label}.{field} deve ter 1–{MAX_CONVERSATION_ITEMS} textos não vazios"
            )
        compact = [" ".join(item.split()) for item in items]
        if any(len(item) > MAX_CONVERSATION_TEXT for item in compact):
            raise ValueError(
                f"{label}.{field} excede {MAX_CONVERSATION_TEXT} caracteres por item"
            )
        result[field] = compact

    authority = value.get("limite_de_autoridade")
    if not isinstance(authority, str) or not authority.strip():
        raise ValueError(f"{label}.limite_de_autoridade precisa ser texto não vazio")
    authority = " ".join(authority.split())
    if len(authority) > MAX_CONVERSATION_TEXT:
        raise ValueError(
            f"{label}.limite_de_autoridade excede {MAX_CONVERSATION_TEXT} caracteres"
        )
    result["limite_de_autoridade"] = authority
    return result


def lookup(repo: Path, kind: str, term: str) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    """Retorna paleta compacta, fontes e candidatos sem varrer o cenário inteiro.

    Locais são normalizados pelo registro canônico antes de consultar a textura.
    Assim um alias pode encontrar a paleta correta, mas nunca cria uma segunda
    identidade operacional para o mesmo lugar.

    Para NPCs, uma entrada pode conter só ``papel_conversacional``. Nesse caso o
    resultado usa apenas o índice que já seria lido pela consulta e não abre
    fragmento narrativo adicional.
    """
    if kind not in KINDS:
        raise ValueError(f"tipo de textura inválido: {kind}")

    query_term = term
    canonical: dict[str, Any] | None = None
    canonical_sources: list[str] = []
    if kind == "locais":
        canonical = locais.resolve(repo, term)
        query_term = canonical["local_id"]
        canonical_sources = list(canonical["fontes_lidas"])

    index_file = repo / INDEX_PATH
    if not index_file.is_file():
        return None, canonical_sources, []
    index = load_yaml(index_file) or {}
    mapping = index.get(kind) if isinstance(index, dict) else None
    if not isinstance(mapping, dict):
        return None, list(dict.fromkeys([*canonical_sources, INDEX_PATH.as_posix()])), []

    ranked: list[tuple[int, str, dict[str, Any]]] = []
    for key, raw_entry in mapping.items():
        if not isinstance(raw_entry, dict):
            continue
        score = _score(str(key), raw_entry, query_term)
        if score:
            ranked.append((score, str(key), raw_entry))
    ranked.sort(key=lambda item: (-item[0], item[1]))

    if not ranked:
        if kind == "locais" and canonical is not None:
            return None, list(dict.fromkeys([*canonical_sources, INDEX_PATH.as_posix()])), []
        query_tokens = set(normalize(query_term).split())
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
        return None, list(dict.fromkeys([*canonical_sources, INDEX_PATH.as_posix()])), [
            str(item[2].get("nome") or item[1]) for item in ties[:8]
        ]

    _, key, entry = best
    if kind == "locais" and canonical is not None and key != canonical["local_id"]:
        raise ValueError(
            f"textura local {key!r} diverge do id canônico {canonical['local_id']!r}"
        )

    conversation: dict[str, Any] | None = None
    if entry.get("papel_conversacional") is not None:
        if kind != "npcs":
            raise ValueError(f"papel conversacional só é válido para NPC: {kind}.{key}")
        conversation = _conversation_profile(
            entry["papel_conversacional"],
            f"{INDEX_PATH.as_posix()}:npcs.{key}.papel_conversacional",
        )

    rel = entry.get("arquivo")
    payload: dict[str, Any] = {}
    fragment_sources: list[str] = []
    if rel is not None:
        if not isinstance(rel, str):
            raise ValueError(f"arquivo de textura inválido no índice: {kind}.{key}")
        path = repo / rel
        if not path.is_file():
            raise ValueError(f"fragmento de textura indexado ausente: {rel}")
        size = path.stat().st_size
        limit = int(index.get("limite_fragmento_bytes") or MAX_FRAGMENT_BYTES)
        if size > limit:
            raise ValueError(f"fragmento de textura excede {limit} bytes: {rel} ({size})")
        raw_payload = load_yaml(path)
        if not isinstance(raw_payload, dict):
            raise ValueError(f"fragmento de textura inválido: {rel}")
        payload = raw_payload
        fragment_sources.append(rel)
    elif conversation is None:
        raise ValueError(f"textura sem arquivo nem papel conversacional: {kind}.{key}")

    result: dict[str, Any] = {
        "id": key,
        "nome": payload.get("nome") or entry.get("nome"),
        "natureza": payload.get("natureza")
        or ("papel_conversacional_sugestivo" if conversation is not None else None),
        "autoridade": payload.get("autoridade")
        or (CONVERSATION_AUTHORITY if conversation is not None else None),
    }
    if conversation is not None:
        result["papel_conversacional"] = conversation

    palette = {
        k: v
        for k, v in payload.items()
        if k not in {"schema_textura", "natureza", "id", "nome", "autoridade"}
    }
    if palette:
        result["paleta"] = palette

    if canonical is not None:
        result["local_ref_recebido"] = canonical["recebido"]
        result["resolucao_local"] = canonical["resolucao"]
    return result, list(
        dict.fromkeys([*canonical_sources, INDEX_PATH.as_posix(), *fragment_sources])
    ), []


def validate(repo: Path) -> list[str]:
    errors: list[str] = []
    index_file = repo / INDEX_PATH
    if not index_file.is_file():
        return [f"índice de texturas ausente: {INDEX_PATH.as_posix()}"]
    try:
        index = load_yaml(index_file) or {}
    except Exception as exc:
        return [f"índice de texturas inválido: {exc}"]
    if index.get("schema_texturas") not in {1, 2}:
        errors.append(f"schema_texturas inesperado: {index.get('schema_texturas')!r}")
    limit = int(index.get("limite_fragmento_bytes") or MAX_FRAGMENT_BYTES)
    for kind in KINDS:
        mapping = index.get(kind) or {}
        if not isinstance(mapping, dict):
            errors.append(f"cenario/texturas/index.yaml: {kind} não é mapa")
            continue
        for key, entry in mapping.items():
            if kind == "locais":
                try:
                    if not locais.is_canonical(repo, key):
                        errors.append(f"textura usa local_id não canônico: {key}")
                except locais.LocationError as exc:
                    errors.append(f"registro canônico de locais inválido: {exc}")
            if not isinstance(entry, dict):
                errors.append(f"textura inválida no índice: {kind}.{key}")
                continue

            conversation = entry.get("papel_conversacional")
            if conversation is not None:
                if kind != "npcs":
                    errors.append(f"papel conversacional fora de NPC: {kind}.{key}")
                else:
                    try:
                        _conversation_profile(
                            conversation,
                            f"{INDEX_PATH.as_posix()}:npcs.{key}.papel_conversacional",
                        )
                    except ValueError as exc:
                        errors.append(str(exc))

            rel = entry.get("arquivo")
            if rel is None:
                if conversation is None:
                    errors.append(f"textura sem arquivo nem papel conversacional: {kind}.{key}")
                continue
            if not isinstance(rel, str):
                errors.append(f"arquivo de textura inválido no índice: {kind}.{key}")
                continue
            path = repo / rel
            if not path.is_file():
                errors.append(f"fragmento de textura ausente: {rel}")
                continue
            if path.stat().st_size > limit:
                errors.append(f"fragmento de textura grande demais: {rel}")
            try:
                payload = load_yaml(path)
            except Exception as exc:
                errors.append(f"fragmento de textura inválido {rel}: {exc}")
                continue
            if not isinstance(payload, dict) or payload.get("id") != key:
                errors.append(f"id de textura divergente: {rel}")
    return errors
