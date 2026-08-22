#!/usr/bin/env python3
"""Identidade canônica mínima para NPCs nomeados que ainda não possuem camada própria.

O stub é deliberadamente barato: nome + ID estável + persistência inicial
``persistente_sem_agenda``. Criá-lo NÃO promove o NPC a agente estratégico, agente
leve, sidequest giver ou entrada agendada.

A abertura transacional de cena usa ``resolve_or_propose`` durante ``preparar``;
só ``ensure_many`` materializa identidades depois de a cena aceita ser confirmada.
"""
from __future__ import annotations

import difflib
import hashlib
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

import yaml

NPC_INDEX = Path("estado/npcs/index.yaml")
RELATION_INDEX = Path("estado/relacoes/index.yaml")
STRATEGIC_INDEX = Path("narrador/agentes/index.yaml")
LIGHT_INDEX = Path("narrador/agentes-leves/index.yaml")
AGENDA = Path("narrador/mundo/agenda.yaml")
PERSISTENCE = "persistente_sem_agenda"
MAX_NAME_CHARS = 80
MAX_NAME_WORDS = 6
MAX_STUBS_PER_SCENE = 6
MAX_INDEX_BYTES = 48 * 1024
MIN_ALIAS_CHARS = 3

_GENERIC_TOKENS = {
    "anonimo", "anonima", "criança", "crianca", "garoto", "garota", "guarda",
    "homem", "mulher", "mercador", "mercadora", "soldado", "soldada", "trabalhador",
    "trabalhadora", "velho", "velha", "cliente", "mensageiro", "mensageira", "capanga",
    "bystander", "child", "guard", "man", "merchant", "messenger", "soldier", "woman", "worker",
}


class NpcStubError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise NpcStubError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise NpcStubError(f"YAML inválido em {path}: {exc}") from exc


def _optional(repo: Path, rel: Path) -> dict[str, Any] | None:
    path = repo / rel
    if not path.is_file():
        return None
    value = _load(path)
    if not isinstance(value, dict):
        raise NpcStubError(f"{rel.as_posix()} deve conter mapa")
    return value


def _dump(value: Any) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=110)


def _atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        tmp = Path(handle.name)
    os.replace(tmp, path)


def _install_exact(path: Path, text: str) -> None:
    if path.is_file():
        if path.read_text(encoding="utf-8") != text:
            raise NpcStubError(f"artefato órfão/divergente já existe: {path}")
        return
    _atomic(path, text)


def normalize_ref(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NpcStubError("referência de NPC deve ser texto não vazio")
    folded = unicodedata.normalize("NFKD", value.strip().casefold())
    plain = "".join(ch for ch in folded if not unicodedata.combining(ch))
    result = re.sub(r"[^a-z0-9]+", "_", plain).strip("_")
    if not result:
        raise NpcStubError("referência de NPC não contém identificador utilizável")
    return result


def _safe_id(name: str) -> str:
    base = normalize_ref(name)
    if len(base) <= 64:
        return base
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:10]
    return f"{base[:52].rstrip('_')}_{digest}"


def _entities(doc: dict[str, Any] | None, key: str) -> dict[str, dict[str, Any]]:
    if not doc:
        return {}
    raw = doc.get(key) or {}
    if not isinstance(raw, dict):
        raise NpcStubError(f"índice inválido: {key}")
    result: dict[str, dict[str, Any]] = {}
    for entity_id, meta in raw.items():
        if not isinstance(entity_id, str) or not entity_id or not isinstance(meta, dict):
            continue
        name = meta.get("nome")
        if not isinstance(name, str) or not name.strip():
            continue
        aliases = meta.get("aliases") or []
        if not isinstance(aliases, list):
            aliases = []
        result[entity_id] = {
            "nome": name.strip(),
            "aliases": [str(item).strip() for item in aliases if isinstance(item, str) and item.strip()],
            "meta": meta,
        }
    return result


def _labels(entity_id: str, entity: dict[str, Any]) -> set[str]:
    values = {entity_id, entity["nome"], *(entity.get("aliases") or [])}
    result: set[str] = set()
    for value in values:
        normalized = normalize_ref(value)
        result.add(normalized)
        result.update(token for token in normalized.split("_") if len(token) >= MIN_ALIAS_CHARS)
    return result


def _matches(query: str, entities: dict[str, dict[str, Any]]) -> tuple[list[str], str | None]:
    exact: set[str] = set()
    aliases: set[str] = set()
    for entity_id, entity in entities.items():
        normalized_id = normalize_ref(entity_id)
        normalized_name = normalize_ref(entity["nome"])
        explicit_aliases = {normalize_ref(item) for item in entity.get("aliases") or []}
        if query in {normalized_id, normalized_name, *explicit_aliases}:
            exact.add(entity_id)
            continue
        if len(query) < MIN_ALIAS_CHARS:
            continue
        if query in _labels(entity_id, entity):
            aliases.add(entity_id)
    if exact:
        return sorted(exact), "nome_ou_id_normalizado"
    if aliases:
        return sorted(aliases), "alias_univoco"
    return [], None


def _known(repo: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    npc_doc = _optional(repo, NPC_INDEX)
    rel_doc = _optional(repo, RELATION_INDEX)
    known = _entities(rel_doc, "relacoes")
    for entity_id, entity in _entities(npc_doc, "npcs").items():
        known.setdefault(entity_id, entity)
    sources = [rel.as_posix() for rel in (NPC_INDEX, RELATION_INDEX) if (repo / rel).is_file()]
    return known, sources


def _suggest(query: str, entities: dict[str, dict[str, Any]]) -> list[str]:
    labels: dict[str, set[str]] = {}
    for entity_id, entity in entities.items():
        for label in _labels(entity_id, entity):
            labels.setdefault(label, set()).add(entity_id)
    close = difflib.get_close_matches(query, sorted(labels), n=5, cutoff=0.72)
    result: list[str] = []
    for label in close:
        for entity_id in sorted(labels[label]):
            if entity_id not in result:
                result.append(entity_id)
            if len(result) >= 3:
                return result
    return result


def _looks_like_reusable_name(raw: str) -> bool:
    text = raw.strip()
    if len(text) > MAX_NAME_CHARS or not any(ch.isalpha() for ch in text):
        return False
    # IDs/typos digitados em minúsculas continuam falhando; a criação automática
    # exige uma referência que se apresente como nome próprio na cena.
    if not any(ch.isupper() for ch in text if ch.isalpha()):
        return False
    words = re.findall(r"[^\W\d_][\w'’.-]*", text, flags=re.UNICODE)
    if not words or len(words) > MAX_NAME_WORDS:
        return False
    normalized_words = normalize_ref(text).split("_")
    return not normalized_words or not all(token in _GENERIC_TOKENS for token in normalized_words)


def _identity(entity_id: str, name: str, *, automatic: bool) -> dict[str, Any]:
    return {
        "npc_id": entity_id,
        "nome": name,
        "persistencia": PERSISTENCE if automatic else "canonico_sem_perfil",
        "stub_automatico": automatic,
    }


def guard_resolution(repo: Path, supplied: str, resolved_id: str) -> list[str]:
    """Impede que um alias resolvido por outra camada ignore um stub homônimo."""
    npc_doc = _optional(repo, NPC_INDEX)
    entities = _entities(npc_doc, "npcs")
    query = normalize_ref(supplied)
    matches, _ = _matches(query, entities)
    other = [item for item in matches if item != resolved_id]
    if other:
        raise NpcStubError(
            f"referência de NPC ambígua {supplied!r}: "
            + ", ".join(sorted({resolved_id, *other}))
            + "; use o ID estável completo"
        )
    return [NPC_INDEX.as_posix()] if (repo / NPC_INDEX).is_file() else []


def resolve_or_propose(repo: Path, supplied: str) -> dict[str, Any]:
    """Resolve um NPC já indexado ou propõe stub somente para nome próprio inequívoco."""
    raw = supplied.strip() if isinstance(supplied, str) else supplied
    query = normalize_ref(raw)
    known, sources = _known(repo)
    npc_doc = _optional(repo, NPC_INDEX)
    npc_entities = _entities(npc_doc, "npcs")

    matches, mode = _matches(query, npc_entities)
    if len(matches) == 1:
        entity_id = matches[0]
        meta = npc_entities[entity_id]["meta"]
        automatic = meta.get("persistencia") == PERSISTENCE
        return {
            "npc_id": entity_id,
            "recebido": raw,
            "resolucao": mode or "id_canonico",
            "identidade_stub": _identity(entity_id, npc_entities[entity_id]["nome"], automatic=automatic),
            "fontes_lidas": sources,
        }
    if len(matches) > 1:
        raise NpcStubError(
            f"referência de NPC ambígua {raw!r}: " + ", ".join(matches) + "; use o ID estável completo"
        )

    # Mesmo que o chamador já tenha consultado relações, repetimos a trava aqui:
    # criação de identidade nunca pode atropelar um homônimo conhecido.
    global_matches, _ = _matches(query, known)
    if global_matches:
        raise NpcStubError(
            f"referência {raw!r} já coincide com identidade canônica: "
            + ", ".join(global_matches)
            + "; não criar stub novo"
        )

    suggestions = _suggest(query, known)
    if suggestions:
        raise NpcStubError(
            f"NPC desconhecido {raw!r} parece alias/typo de identidade existente: "
            + ", ".join(suggestions)
            + "; desambigue antes de criar stub"
        )
    if not _looks_like_reusable_name(str(raw)):
        raise NpcStubError(
            f"NPC desconhecido {raw!r} não parece nome próprio reutilizável; "
            "figurantes anônimos não recebem stub automático"
        )

    entity_id = _safe_id(str(raw))
    if entity_id in known:
        raise NpcStubError(
            f"ID derivado {entity_id!r} já pertence a outra identidade; use nome/qualificador mais específico"
        )
    return {
        "npc_id": entity_id,
        "recebido": raw,
        "resolucao": "stub_persistente_proposto",
        "identidade_stub": _identity(entity_id, str(raw).strip(), automatic=True),
        "fontes_lidas": sources,
    }


def _stub_bytes(identity: dict[str, Any], scene_id: str) -> tuple[str, str, str]:
    npc_id = str(identity["npc_id"])
    name = str(identity["nome"])
    fragment = {
        "schema_npc": 2,
        "natureza": "medidores_npc_atuais",
        "id": npc_id,
        "npc": {
            "nome": name,
            "persistencia": PERSISTENCE,
            "origem_identidade": {"tipo": "cena_confirmada", "cena_id": scene_id},
        },
    }
    history = {
        "schema_historico_npc": 2,
        "id": npc_id,
        "origem": "npc-stub-automatico",
        "eventos_pos_migracao": [
            {
                "tipo": "identidade_persistente_criada",
                "cena_id": scene_id,
                "nome": name,
                "classificacao_inicial": PERSISTENCE,
            }
        ],
    }
    return _dump(fragment), _dump(history), name


def ensure_stub(repo: Path, identity: dict[str, Any], *, scene_id: str) -> dict[str, Any]:
    if not isinstance(identity, dict) or not identity.get("stub_automatico"):
        return {"criado": False, "ignorado": True}
    npc_id = str(identity.get("npc_id") or "")
    name = str(identity.get("nome") or "")
    if not npc_id or _safe_id(name) != npc_id:
        raise NpcStubError("identidade de stub não corresponde ao ID determinístico esperado")

    index = _optional(repo, NPC_INDEX)
    if not index or index.get("schema_npcs") != 2 or not isinstance(index.get("npcs"), dict):
        raise NpcStubError("estado/npcs/index.yaml inválido para criação de stub")
    mapping = index["npcs"]
    existing = mapping.get(npc_id)
    fragment_rel = Path("estado/npcs") / f"{npc_id}.yaml"
    history_rel = Path("historico/npcs") / f"{npc_id}.yaml"
    fragment_text, history_text, name = _stub_bytes(identity, scene_id)

    if isinstance(existing, dict):
        existing_name = existing.get("nome")
        if normalize_ref(existing_name) != normalize_ref(name):
            raise NpcStubError(f"ID {npc_id} já pertence a {existing_name!r}")
        if existing.get("persistencia") != PERSISTENCE:
            raise NpcStubError(
                f"NPC {npc_id} já possui identidade canônica não-stub; não reclassificar automaticamente"
            )
        if existing.get("arquivo") != fragment_rel.as_posix():
            raise NpcStubError(f"NPC {npc_id} aponta para fragmento inesperado")
        if not (repo / fragment_rel).is_file():
            raise NpcStubError(f"stub indexado sem fragmento: {fragment_rel}")
        return {"criado": False, "npc_id": npc_id, "arquivo": fragment_rel.as_posix()}

    # Revalida homônimos imediatamente antes da escrita.
    known, _ = _known(repo)
    for other_id, entity in known.items():
        if other_id == npc_id:
            continue
        if normalize_ref(entity["nome"]) == normalize_ref(name):
            raise NpcStubError(
                f"nome {name!r} já pertence a {other_id}; desambigue antes de persistir"
            )

    # Fragmento/histórico primeiro; índice por último. Uma queda intermediária é
    # recuperável por retry porque os bytes são determinísticos e verificados.
    _install_exact(repo / fragment_rel, fragment_text)
    _install_exact(repo / history_rel, history_text)
    mapping[npc_id] = {
        "nome": name,
        "persistencia": PERSISTENCE,
        "arquivo": fragment_rel.as_posix(),
        "historico": history_rel.as_posix(),
        "bytes_fragmento": len(fragment_text.encode("utf-8")),
    }
    index["quantidade"] = len(mapping)
    index_text = _dump(index)
    if len(index_text.encode("utf-8")) > MAX_INDEX_BYTES:
        raise NpcStubError("índice de NPCs excederia o teto operacional de 48 KiB")
    _atomic(repo / NPC_INDEX, index_text)
    return {"criado": True, "npc_id": npc_id, "arquivo": fragment_rel.as_posix()}


def ensure_many(repo: Path, identities: list[dict[str, Any]], *, scene_id: str) -> list[dict[str, Any]]:
    automatic = [item for item in identities if isinstance(item, dict) and item.get("stub_automatico")]
    unique: dict[str, dict[str, Any]] = {str(item["npc_id"]): item for item in automatic}
    if len(unique) > MAX_STUBS_PER_SCENE:
        raise NpcStubError(f"uma cena cria no máximo {MAX_STUBS_PER_SCENE} stubs de NPC")
    return [ensure_stub(repo, unique[npc_id], scene_id=scene_id) for npc_id in sorted(unique)]


def check_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        index = _optional(repo, NPC_INDEX) or {}
        mapping = index.get("npcs") or {}
        if not isinstance(mapping, dict):
            raise NpcStubError("estado/npcs/index.yaml.npcs deve ser mapa")
        strategic = (_optional(repo, STRATEGIC_INDEX) or {}).get("agentes") or {}
        light = (_optional(repo, LIGHT_INDEX) or {}).get("agentes") or {}
        agenda = _optional(repo, AGENDA) or {}
        recurrences = agenda.get("reavaliacoes") or {}
        schedules = agenda.get("agendamentos") or []
        scheduled = {
            str(item.get("agente"))
            for item in schedules
            if isinstance(item, dict) and item.get("agente") is not None
        }
        stubs = 0
        for npc_id, meta in mapping.items():
            if not isinstance(meta, dict) or meta.get("persistencia") != PERSISTENCE:
                continue
            stubs += 1
            rel = meta.get("arquivo")
            if not isinstance(rel, str) or not (repo / rel).is_file():
                errors.append(f"stub {npc_id} sem fragmento válido")
                continue
            doc = _load(repo / rel)
            body = doc.get("npc") if isinstance(doc, dict) else None
            if not isinstance(body, dict) or body.get("persistencia") != PERSISTENCE:
                errors.append(f"stub {npc_id} diverge da classificação persistente_sem_agenda")
            if npc_id in strategic or npc_id in light or npc_id in recurrences or npc_id in scheduled:
                errors.append(f"stub {npc_id} ganhou camada autônoma/agenda sem promoção explícita")
        return {"ok": not errors, "stubs": stubs, "erros": errors}
    except NpcStubError as exc:
        return {"ok": False, "stubs": 0, "erros": [str(exc)]}
