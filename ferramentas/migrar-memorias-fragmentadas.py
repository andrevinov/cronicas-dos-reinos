#!/usr/bin/env python3
"""Etapa 6: fragmenta relações, medidores de NPC e conhecimento acumulativo.

A migração é conservadora:
- preserva os três arquivos monolíticos originais byte a byte em historico/legado/;
- cria índices pequenos e fragmentos por entidade/assunto;
- separa o estado atual de cada relação de sua narrativa histórica;
- permite reconstruir integralmente o conhecimento legado concatenando os fragmentos;
- oferece --check para impedir regressão estrutural depois da migração.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import unicodedata
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt") from exc


REL_SOURCE = Path("estado/relacoes.yaml")
NPC_SOURCE = Path("estado/medidores-npcs.yaml")
KNOW_SOURCE = Path("personagens/jogador/conhecimento.md")

REL_LEGACY = Path("historico/legado/relacoes-acumuladas-pre-etapa-6.yaml")
NPC_LEGACY = Path("historico/legado/medidores-npcs-pre-etapa-6.yaml")
KNOW_LEGACY = Path("historico/legado/conhecimento-acumulado-pre-etapa-6.md")
MANIFEST = Path("historico/legado/migracao-memorias-v1.yaml")

REL_DIR = Path("estado/relacoes")
REL_INDEX = REL_DIR / "index.yaml"
REL_HISTORY_DIR = Path("historico/relacoes")
NPC_DIR = Path("estado/npcs")
NPC_INDEX = NPC_DIR / "index.yaml"
NPC_SCALE = NPC_DIR / "escala.yaml"
KNOW_DIR = Path("personagens/jogador/conhecimento")
KNOW_INDEX = KNOW_DIR / "index.yaml"
KNOW_ACTIVE = KNOW_DIR / "ativo.yaml"

SCHEMA_VERSION = 2
MAX_ENTITY_FRAGMENT = 12 * 1024
MAX_KNOW_FRAGMENT = 12 * 1024
MAX_ROUTER = 4 * 1024
MAX_REL_INDEX = 32 * 1024
MAX_NPC_INDEX = 24 * 1024
MAX_KNOW_INDEX = 20 * 1024
MAX_ACTIVE = 8 * 1024

EXPECTED_BLOBS = {
    REL_LEGACY: "6a8b7765c98aa31ca6b4355a78a879185f4361f0",
    NPC_LEGACY: "7170959e9a1539e7449593e04a8e8fba7375caf3",
    KNOW_LEGACY: "9ff35d2650f6da2496a3989d4786414a049ebe3f",
}

CORE_RELATION_KEYS = (
    "nome",
    "tipo",
    "local",
    "status",
    "atitude_para_ren",
    "confianca",
    "respeito",
    "ultima_alteracao",
)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def dump_yaml(data: Any) -> bytes:
    return yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        width=110,
    ).encode("utf-8")


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dump_yaml(data))


def git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def normalize(text: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(text))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = raw.lower().replace("_", " ").replace("-", " ")
    return " ".join(re.findall(r"[a-z0-9]+", raw))


def slugify(text: str) -> str:
    slug = normalize(text).replace(" ", "-")
    return slug or "sem-titulo"


def tail_sentences(text: str, *, count: int = 2, max_chars: int = 700) -> str:
    compact = " ".join(str(text).split())
    if len(compact) <= max_chars:
        return compact
    sentences = re.split(r"(?<=[.!?])\s+", compact)
    candidate = " ".join(sentences[-count:]).strip()
    if not candidate:
        candidate = compact[-max_chars:]
    if len(candidate) > max_chars:
        candidate = candidate[-max_chars:]
    return candidate.lstrip(" ,;:-")


def compact_current_value(value: Any, *, list_limit: int, string_limit: int, omitted: dict[str, int], key: str) -> Any:
    if isinstance(value, list):
        if len(value) > list_limit:
            omitted[key] = len(value) - list_limit
        selected = value[-list_limit:] if list_limit else []
        return [compact_current_value(v, list_limit=list_limit, string_limit=string_limit, omitted=omitted, key=key) for v in selected]
    if isinstance(value, dict):
        return {
            str(k): compact_current_value(v, list_limit=list_limit, string_limit=string_limit, omitted=omitted, key=f"{key}.{k}")
            for k, v in value.items()
        }
    if isinstance(value, str) and len(value) > string_limit:
        omitted[f"{key}:texto_truncado"] = len(value) - string_limit
        return value[: string_limit - 1].rstrip() + "…"
    return value


def build_current_relation(entity_id: str, payload: dict[str, Any], history_path: Path) -> dict[str, Any]:
    for list_limit, string_limit in ((10, 1000), (8, 850), (6, 700), (4, 500), (3, 350), (2, 240)):
        omitted: dict[str, int] = {}
        current: dict[str, Any] = {}
        for key in CORE_RELATION_KEYS:
            if key in payload:
                current[key] = payload[key]

        motivo = payload.get("motivo")
        if isinstance(motivo, str) and motivo.strip():
            current["motivo_atual"] = tail_sentences(motivo, count=2, max_chars=min(700, string_limit))

        for key, value in payload.items():
            if key in CORE_RELATION_KEYS or key == "motivo":
                continue
            if key.startswith(("historico", "interacoes", "memoria")):
                continue
            current[key] = compact_current_value(
                value,
                list_limit=list_limit,
                string_limit=string_limit,
                omitted=omitted,
                key=key,
            )

        document: dict[str, Any] = {
            "schema_relacao": SCHEMA_VERSION,
            "natureza": "estado_relacao_atual",
            "id": entity_id,
            "historico": history_path.as_posix(),
            "relacao": current,
        }
        if omitted:
            document["conteudo_mais_antigo_no_historico"] = omitted
        if len(dump_yaml(document)) <= MAX_ENTITY_FRAGMENT:
            return document

    fallback = {
        key: payload[key]
        for key in CORE_RELATION_KEYS
        if key in payload
    }
    if isinstance(payload.get("motivo"), str):
        fallback["motivo_atual"] = tail_sentences(payload["motivo"], count=1, max_chars=260)
    return {
        "schema_relacao": SCHEMA_VERSION,
        "natureza": "estado_relacao_atual",
        "id": entity_id,
        "historico": history_path.as_posix(),
        "relacao": fallback,
        "conteudo_mais_antigo_no_historico": {"fallback_por_tamanho": True},
    }


def migrate_relations(root: Path, source_bytes: bytes) -> dict[str, Any]:
    REL_LEGACY_PATH = root / REL_LEGACY
    REL_LEGACY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REL_LEGACY_PATH.write_bytes(source_bytes)
    source = yaml.safe_load(source_bytes.decode("utf-8")) or {}
    relations = source.get("relacoes") if isinstance(source, dict) else None
    if not isinstance(relations, dict):
        raise ValueError("estado/relacoes.yaml não contém mapping 'relacoes'")

    index_entries: dict[str, Any] = {}
    for entity_id, payload in relations.items():
        if not isinstance(payload, dict):
            raise ValueError(f"relação {entity_id!r} não é objeto")
        entity_id = str(entity_id)
        history_rel = REL_HISTORY_DIR / f"{entity_id}.yaml"
        current_rel = REL_DIR / f"{entity_id}.yaml"
        write_yaml(
            root / history_rel,
            {
                "schema_historico_relacao": 1,
                "id": entity_id,
                "origem": REL_LEGACY.as_posix(),
                "relacao": payload,
            },
        )
        current_doc = build_current_relation(entity_id, payload, history_rel)
        write_yaml(root / current_rel, current_doc)
        relation_now = current_doc["relacao"]
        index_entries[entity_id] = {
            "nome": payload.get("nome", entity_id),
            "tipo": payload.get("tipo"),
            "status": payload.get("status"),
            "atitude_para_ren": payload.get("atitude_para_ren"),
            "confianca": payload.get("confianca"),
            "respeito": payload.get("respeito"),
            "arquivo": current_rel.as_posix(),
            "historico": history_rel.as_posix(),
            "bytes_fragmento": len(dump_yaml(current_doc)),
            "campos_atuais": len(relation_now),
        }

    write_yaml(
        root / REL_INDEX,
        {
            "schema_relacoes": SCHEMA_VERSION,
            "natureza": "indice_relacoes_atuais",
            "historico_acumulado": REL_LEGACY.as_posix(),
            "quantidade": len(index_entries),
            "relacoes": index_entries,
        },
    )
    write_yaml(
        root / REL_SOURCE,
        {
            "schema_relacoes": SCHEMA_VERSION,
            "natureza": "roteador_fragmentado",
            "index": REL_INDEX.as_posix(),
            "historico_acumulado": REL_LEGACY.as_posix(),
            "consulta_recomendada": "python3 ferramentas/contexto.py relacao <nome>",
        },
    )
    return {"quantidade": len(index_entries), "ids": list(index_entries)}


def migrate_npcs(root: Path, source_bytes: bytes) -> dict[str, Any]:
    legacy = root / NPC_LEGACY
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(source_bytes)
    source = yaml.safe_load(source_bytes.decode("utf-8")) or {}
    npcs = source.get("npcs") if isinstance(source, dict) else None
    if not isinstance(npcs, dict):
        raise ValueError("estado/medidores-npcs.yaml não contém mapping 'npcs'")

    global_data = {key: value for key, value in source.items() if key != "npcs"}
    global_data["fonte_legada"] = NPC_LEGACY.as_posix()
    write_yaml(root / NPC_SCALE, global_data)

    index_entries: dict[str, Any] = {}
    for entity_id, payload in npcs.items():
        if not isinstance(payload, dict):
            raise ValueError(f"medidor de NPC {entity_id!r} não é objeto")
        entity_id = str(entity_id)
        fragment = NPC_DIR / f"{entity_id}.yaml"
        document = {
            "schema_npc": SCHEMA_VERSION,
            "natureza": "medidores_npc_atuais",
            "id": entity_id,
            "npc": payload,
        }
        write_yaml(root / fragment, document)
        index_entries[entity_id] = {
            "nome": payload.get("nome", entity_id),
            "grupo": payload.get("grupo"),
            "medidores": payload.get("medidores"),
            "natureza_do_vinculo": payload.get("natureza_do_vinculo"),
            "subtexto_romantico": payload.get("subtexto_romantico"),
            "arquivo": fragment.as_posix(),
            "bytes_fragmento": len(dump_yaml(document)),
        }

    write_yaml(
        root / NPC_INDEX,
        {
            "schema_npcs": SCHEMA_VERSION,
            "natureza": "indice_medidores_npcs",
            "escala": NPC_SCALE.as_posix(),
            "fonte_legada": NPC_LEGACY.as_posix(),
            "quantidade": len(index_entries),
            "npcs": index_entries,
        },
    )
    write_yaml(
        root / NPC_SOURCE,
        {
            "schema": SCHEMA_VERSION,
            "natureza": "roteador_fragmentado",
            "index": NPC_INDEX.as_posix(),
            "escala": NPC_SCALE.as_posix(),
            "fonte_legada": NPC_LEGACY.as_posix(),
            "consulta_recomendada": "python3 ferramentas/contexto.py npc <nome>",
        },
    )
    return {"quantidade": len(index_entries), "ids": list(index_entries)}


def heading(line: str) -> tuple[int, str] | None:
    match = re.match(r"^(#{1,6})\s+(.+?)\s*(?:\r?\n)?$", line)
    if not match:
        return None
    return len(match.group(1)), match.group(2).strip()


def split_exact_by_bytes(text: str, max_bytes: int) -> list[str]:
    if len(text.encode("utf-8")) <= max_bytes:
        return [text]
    lines = text.splitlines(keepends=True)
    parts: list[str] = []
    buffer: list[str] = []
    size = 0
    for line in lines:
        encoded = line.encode("utf-8")
        if len(encoded) > max_bytes:
            if buffer:
                parts.append("".join(buffer))
                buffer = []
                size = 0
            raw = encoded
            while raw:
                cut = min(max_bytes, len(raw))
                while cut > 0:
                    try:
                        piece = raw[:cut].decode("utf-8")
                        break
                    except UnicodeDecodeError:
                        cut -= 1
                if cut <= 0:
                    raise ValueError("não foi possível dividir UTF-8 com segurança")
                parts.append(piece)
                raw = raw[cut:]
            continue
        if buffer and size + len(encoded) > max_bytes:
            parts.append("".join(buffer))
            buffer = []
            size = 0
        buffer.append(line)
        size += len(encoded)
    if buffer:
        parts.append("".join(buffer))
    return parts


def parse_knowledge_sections(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines(keepends=True)
    h2_positions: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        parsed = heading(line)
        if parsed and parsed[0] == 2:
            h2_positions.append((i, parsed[1]))

    sections: list[dict[str, Any]] = []
    first_h2 = h2_positions[0][0] if h2_positions else len(lines)
    if first_h2 > 0:
        sections.append({"kind": "preambulo", "title": "Introdução", "session": None, "text": "".join(lines[:first_h2])})

    for pos_index, (start, title) in enumerate(h2_positions):
        end = h2_positions[pos_index + 1][0] if pos_index + 1 < len(h2_positions) else len(lines)
        block = lines[start:end]
        if normalize(title) != "descobertas em jogo":
            sections.append({"kind": "topico", "title": title, "session": None, "text": "".join(block)})
            continue

        h3_positions: list[tuple[int, str]] = []
        for local_i, line in enumerate(block):
            parsed = heading(line)
            if parsed and parsed[0] == 3:
                h3_positions.append((local_i, parsed[1]))
        first_h3 = h3_positions[0][0] if h3_positions else len(block)
        if first_h3 > 0:
            sections.append({"kind": "descobertas_intro", "title": title, "session": None, "text": "".join(block[:first_h3])})
        for h3_i, (local_start, h3_title) in enumerate(h3_positions):
            local_end = h3_positions[h3_i + 1][0] if h3_i + 1 < len(h3_positions) else len(block)
            match = re.search(r"Sess[aã]o\s+(\d+)", h3_title, flags=re.IGNORECASE)
            session = int(match.group(1)) if match else None
            sections.append({
                "kind": "descoberta",
                "title": h3_title,
                "session": session,
                "text": "".join(block[local_start:local_end]),
            })
    return sections


def migrate_knowledge(root: Path, source_bytes: bytes) -> dict[str, Any]:
    legacy = root / KNOW_LEGACY
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_bytes(source_bytes)
    text = source_bytes.decode("utf-8")
    sections = parse_knowledge_sections(text)

    order: list[str] = []
    top_index: list[dict[str, Any]] = []
    sessions: dict[int, list[dict[str, Any]]] = {}
    top_counter = 0
    discovery_counter: dict[int | None, int] = {}

    for section in sections:
        kind = section["kind"]
        title = section["title"]
        session = section["session"]
        if kind in {"preambulo", "topico", "descobertas_intro"}:
            top_counter += 1
            base_dir = KNOW_DIR / "topicos"
            base_name = f"{top_counter:02d}-{slugify(title)}"
        else:
            discovery_counter[session] = discovery_counter.get(session, 0) + 1
            seq = discovery_counter[session]
            session_dir = f"sessao-{session:03d}" if session is not None else "geral"
            base_dir = KNOW_DIR / "descobertas" / session_dir
            base_name = f"{seq:03d}-{slugify(title)}"

        parts = split_exact_by_bytes(section["text"], MAX_KNOW_FRAGMENT)
        paths: list[str] = []
        for part_index, part in enumerate(parts, start=1):
            suffix = "" if len(parts) == 1 else f"-parte-{part_index:02d}"
            rel = base_dir / f"{base_name}{suffix}.md"
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(part.encode("utf-8"))
            paths.append(rel.as_posix())
            order.append(rel.as_posix())

        entry = {
            "titulo": title,
            "arquivos": paths,
            "bytes": sum(len((root / p).read_bytes()) for p in paths),
        }
        if kind == "descoberta":
            sessions.setdefault(session or 0, []).append(entry)
        else:
            top_index.append(entry)

    session_index_refs: dict[str, Any] = {}
    for session, entries in sorted(sessions.items()):
        session_name = f"sessao-{session:03d}" if session else "geral"
        index_rel = KNOW_DIR / "descobertas" / session_name / "index.yaml"
        write_yaml(
            root / index_rel,
            {
                "schema_conhecimento_sessao": SCHEMA_VERSION,
                "sessao": session if session else None,
                "quantidade": len(entries),
                "fragmentos": entries,
            },
        )
        session_index_refs[str(session) if session else "geral"] = {
            "index": index_rel.as_posix(),
            "quantidade": len(entries),
        }

    write_yaml(
        root / KNOW_INDEX,
        {
            "schema_conhecimento": SCHEMA_VERSION,
            "natureza": "indice_fragmentado",
            "historico_acumulado": KNOW_LEGACY.as_posix(),
            "topicos": top_index,
            "sessoes": session_index_refs,
        },
    )

    latest_session = max((s for s in sessions if s), default=0)
    priority_tokens = ("masao", "ravens bluff", "pistas atuais")
    priority_topics = [
        entry for entry in top_index
        if any(token in normalize(entry["titulo"]) for token in priority_tokens)
    ]
    latest_entries = sessions.get(latest_session, [])[-8:] if latest_session else []
    write_yaml(
        root / KNOW_ACTIVE,
        {
            "schema_conhecimento_ativo": SCHEMA_VERSION,
            "natureza": "roteador_derivado",
            "sessao_mais_recente": latest_session or None,
            "topicos_prioritarios": priority_topics,
            "descobertas_recentes": latest_entries,
            "observacao": "Este arquivo só roteia consultas; fatos permanecem nos fragmentos de conhecimento.",
        },
    )

    router = (
        "# Conhecimento de Ren — roteador\n\n"
        "O conhecimento do personagem foi fragmentado para evitar leitura do histórico inteiro.\n\n"
        f"- índice: `{KNOW_INDEX.as_posix()}`\n"
        f"- recorte ativo: `{KNOW_ACTIVE.as_posix()}`\n"
        f"- cópia integral pré-migração: `{KNOW_LEGACY.as_posix()}` (fria; auditoria apenas)\n\n"
        "Consulta normal:\n\n"
        "```bash\npython3 ferramentas/contexto.py conhecimento \"assunto\"\n```\n\n"
        "Não abra todos os fragmentos preventivamente. A ferramenta procura internamente e devolve somente os trechos relevantes.\n"
    )
    (root / KNOW_SOURCE).write_text(router, encoding="utf-8")
    return {"fragmentos": len(order), "ordem": order, "sessoes": sorted(sessions)}


def migrated(root: Path) -> bool:
    try:
        rel = load_yaml(root / REL_SOURCE)
        npc = load_yaml(root / NPC_SOURCE)
        knowledge_text = (root / KNOW_SOURCE).read_text(encoding="utf-8")
    except (OSError, yaml.YAMLError):
        return False
    return (
        isinstance(rel, dict)
        and rel.get("schema_relacoes") == SCHEMA_VERSION
        and rel.get("natureza") == "roteador_fragmentado"
        and isinstance(npc, dict)
        and npc.get("schema") == SCHEMA_VERSION
        and npc.get("natureza") == "roteador_fragmentado"
        and "Conhecimento de Ren — roteador" in knowledge_text
    )


def ensure_size(path: Path, limit: int, errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"arquivo ausente: {path}")
        return
    size = path.stat().st_size
    if size > limit:
        errors.append(f"arquivo excede limite: {path} = {size} > {limit} bytes")


def check(root: Path) -> list[str]:
    errors: list[str] = []
    for rel_path, expected in EXPECTED_BLOBS.items():
        path = root / rel_path
        if not path.is_file():
            errors.append(f"legado ausente: {rel_path}")
            continue
        actual = git_blob_sha(path.read_bytes())
        if actual != expected:
            errors.append(f"blob legado alterado em {rel_path}: {actual} != {expected}")

    if not migrated(root):
        errors.append("roteadores da Etapa 6 não estão aplicados")
        return errors

    ensure_size(root / REL_SOURCE, MAX_ROUTER, errors)
    ensure_size(root / NPC_SOURCE, MAX_ROUTER, errors)
    ensure_size(root / KNOW_SOURCE, MAX_ROUTER, errors)
    ensure_size(root / REL_INDEX, MAX_REL_INDEX, errors)
    ensure_size(root / NPC_INDEX, MAX_NPC_INDEX, errors)
    ensure_size(root / KNOW_INDEX, MAX_KNOW_INDEX, errors)
    ensure_size(root / KNOW_ACTIVE, MAX_ACTIVE, errors)

    legacy_rel = load_yaml(root / REL_LEGACY) or {}
    legacy_relations = legacy_rel.get("relacoes") if isinstance(legacy_rel, dict) else None
    rel_index = load_yaml(root / REL_INDEX) or {}
    indexed_relations = rel_index.get("relacoes") if isinstance(rel_index, dict) else None
    if not isinstance(legacy_relations, dict) or not isinstance(indexed_relations, dict):
        errors.append("índice ou legado de relações inválido")
    else:
        if set(legacy_relations) != set(indexed_relations):
            errors.append("IDs de relações divergiram entre legado e índice")
        for entity_id, payload in legacy_relations.items():
            entry = indexed_relations.get(entity_id) or {}
            current_path = root / str(entry.get("arquivo", ""))
            history_path = root / str(entry.get("historico", ""))
            ensure_size(current_path, MAX_ENTITY_FRAGMENT, errors)
            if not history_path.is_file():
                errors.append(f"histórico de relação ausente: {entity_id}")
                continue
            history = load_yaml(history_path) or {}
            if history.get("relacao") != payload:
                errors.append(f"histórico lógico da relação divergiu: {entity_id}")
            if current_path.is_file():
                current = load_yaml(current_path) or {}
                if current.get("id") != entity_id:
                    errors.append(f"fragmento de relação com ID incorreto: {entity_id}")
                if ((current.get("relacao") or {}).get("nome")) != payload.get("nome"):
                    errors.append(f"nome divergiu no fragmento de relação: {entity_id}")

    legacy_npc = load_yaml(root / NPC_LEGACY) or {}
    legacy_npcs = legacy_npc.get("npcs") if isinstance(legacy_npc, dict) else None
    npc_index = load_yaml(root / NPC_INDEX) or {}
    indexed_npcs = npc_index.get("npcs") if isinstance(npc_index, dict) else None
    if not isinstance(legacy_npcs, dict) or not isinstance(indexed_npcs, dict):
        errors.append("índice ou legado de NPCs inválido")
    else:
        if set(legacy_npcs) != set(indexed_npcs):
            errors.append("IDs de NPCs divergiram entre legado e índice")
        for entity_id, payload in legacy_npcs.items():
            entry = indexed_npcs.get(entity_id) or {}
            fragment = root / str(entry.get("arquivo", ""))
            ensure_size(fragment, MAX_ENTITY_FRAGMENT, errors)
            if fragment.is_file():
                data = load_yaml(fragment) or {}
                if data.get("npc") != payload:
                    errors.append(f"medidores do NPC divergiram: {entity_id}")
        scale = load_yaml(root / NPC_SCALE) or {}
        expected_scale = {k: v for k, v in legacy_npc.items() if k != "npcs"}
        scale_without_meta = {k: v for k, v in scale.items() if k != "fonte_legada"}
        if scale_without_meta != expected_scale:
            errors.append("escala/configuração global de medidores divergiu do legado")

    manifest = load_yaml(root / MANIFEST) or {}
    knowledge_meta = manifest.get("conhecimento") if isinstance(manifest, dict) else None
    order = knowledge_meta.get("ordem_fragmentos") if isinstance(knowledge_meta, dict) else None
    if not isinstance(order, list) or not order:
        errors.append("manifesto não contém ordem de fragmentos de conhecimento")
    else:
        reconstructed = bytearray()
        for rel in order:
            path = root / str(rel)
            ensure_size(path, MAX_KNOW_FRAGMENT, errors)
            if path.is_file():
                reconstructed.extend(path.read_bytes())
        legacy_bytes = (root / KNOW_LEGACY).read_bytes()
        if bytes(reconstructed) != legacy_bytes:
            errors.append("fragmentos de conhecimento não reconstroem byte a byte o arquivo legado")

    return errors


def migrate(root: Path) -> None:
    if migrated(root):
        errors = check(root)
        if errors:
            raise ValueError("migração já aplicada, mas inválida: " + "; ".join(errors))
        print("OK — migração da Etapa 6 já aplicada.")
        return

    rel_bytes = (root / REL_SOURCE).read_bytes()
    npc_bytes = (root / NPC_SOURCE).read_bytes()
    know_bytes = (root / KNOW_SOURCE).read_bytes()

    expected_sources = {
        REL_SOURCE: EXPECTED_BLOBS[REL_LEGACY],
        NPC_SOURCE: EXPECTED_BLOBS[NPC_LEGACY],
        KNOW_SOURCE: EXPECTED_BLOBS[KNOW_LEGACY],
    }
    for source, expected in expected_sources.items():
        actual = git_blob_sha((root / source).read_bytes())
        if actual != expected:
            raise ValueError(f"fonte {source} mudou antes da migração: {actual} != {expected}")

    relation_meta = migrate_relations(root, rel_bytes)
    npc_meta = migrate_npcs(root, npc_bytes)
    knowledge_meta = migrate_knowledge(root, know_bytes)
    write_yaml(
        root / MANIFEST,
        {
            "schema_migracao_memorias": 1,
            "relacoes": {
                "origem": REL_LEGACY.as_posix(),
                "blob": EXPECTED_BLOBS[REL_LEGACY],
                "quantidade": relation_meta["quantidade"],
            },
            "npcs": {
                "origem": NPC_LEGACY.as_posix(),
                "blob": EXPECTED_BLOBS[NPC_LEGACY],
                "quantidade": npc_meta["quantidade"],
            },
            "conhecimento": {
                "origem": KNOW_LEGACY.as_posix(),
                "blob": EXPECTED_BLOBS[KNOW_LEGACY],
                "fragmentos": knowledge_meta["fragmentos"],
                "ordem_fragmentos": knowledge_meta["ordem"],
            },
        },
    )

    errors = check(root)
    if errors:
        raise ValueError("; ".join(errors))
    print(
        "OK — relações, NPCs e conhecimento foram fragmentados com legado preservado. "
        f"Relações: {relation_meta['quantidade']}; NPCs: {npc_meta['quantidade']}; "
        f"fragmentos de conhecimento: {knowledge_meta['fragmentos']}."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=repo_root())
    parser.add_argument("--check", action="store_true", help="somente verifica a migração já aplicada")
    args = parser.parse_args()
    root = args.repo.resolve()
    try:
        if args.check:
            errors = check(root)
            if errors:
                print("FALHA — memórias fragmentadas inválidas:")
                for error in errors:
                    print(f"- {error}")
                return 1
            print("OK — relações, NPCs e conhecimento permanecem fragmentados e íntegros.")
            return 0
        migrate(root)
        return 0
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"FALHA — {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
