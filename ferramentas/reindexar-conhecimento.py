#!/usr/bin/env python3
"""Reconstrói os fragmentos de conhecimento a partir do legado integral da Etapa 6.

O arquivo legado é imutável. Este gerador serve para melhorar índices e recortes sem
reescrever fatos: todo fragmento é um trecho literal do original e a concatenação da
ordem registrada no manifesto precisa reconstruí-lo byte a byte.
"""
from __future__ import annotations

import argparse
import re
import shutil
import unicodedata
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt") from exc

ROOT_DEFAULT = Path(__file__).resolve().parents[1]
LEGACY = Path("historico/legado/conhecimento-acumulado-pre-etapa-6.md")
MANIFEST = Path("historico/legado/migracao-memorias-v1.yaml")
KNOW_DIR = Path("personagens/jogador/conhecimento")
INDEX = KNOW_DIR / "index.yaml"
ACTIVE = KNOW_DIR / "ativo.yaml"
MAX_FRAGMENT = 12 * 1024
MAX_ACTIVE = 8 * 1024
SCHEMA = 2


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=110),
        encoding="utf-8",
    )


def normalize(text: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(text))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = raw.lower().replace("_", " ").replace("-", " ")
    return " ".join(re.findall(r"[a-z0-9]+", raw))


def slugify(text: str) -> str:
    return normalize(text).replace(" ", "-") or "sem-titulo"


def heading(line: str) -> tuple[int, str] | None:
    match = re.match(r"^(#{1,6})\s+(.+?)\s*(?:\r?\n)?$", line)
    if not match:
        return None
    return len(match.group(1)), match.group(2).strip()


def session_from_title(title: str) -> int | None:
    match = re.search(r"Sess[aã]o\s+(\d+)", title, flags=re.IGNORECASE)
    return int(match.group(1)) if match else None


def split_exact_by_bytes(text: str, max_bytes: int = MAX_FRAGMENT) -> list[str]:
    if len(text.encode("utf-8")) <= max_bytes:
        return [text]
    parts: list[str] = []
    buffer: list[str] = []
    size = 0
    for line in text.splitlines(keepends=True):
        encoded = line.encode("utf-8")
        if len(encoded) > max_bytes:
            if buffer:
                parts.append("".join(buffer))
                buffer, size = [], 0
            raw = encoded
            while raw:
                cut = min(max_bytes, len(raw))
                while cut:
                    try:
                        piece = raw[:cut].decode("utf-8")
                        break
                    except UnicodeDecodeError:
                        cut -= 1
                if not cut:
                    raise ValueError("falha ao dividir UTF-8")
                parts.append(piece)
                raw = raw[cut:]
            continue
        if buffer and size + len(encoded) > max_bytes:
            parts.append("".join(buffer))
            buffer, size = [], 0
        buffer.append(line)
        size += len(encoded)
    if buffer:
        parts.append("".join(buffer))
    return parts


def parse_sections(text: str) -> list[dict[str, Any]]:
    """Separa H2 estáveis e qualquer H3 explicitamente marcado com Sessão NNN.

    Alguns registros posteriores deixaram de ficar sob `## Descobertas em jogo` e
    passaram a viver sob outro H2. Por isso a classificação por sessão é feita pelo
    próprio título H3, independentemente do H2 pai.
    """
    lines = text.splitlines(keepends=True)
    h2s: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        parsed = heading(line)
        if parsed and parsed[0] == 2:
            h2s.append((i, parsed[1]))

    result: list[dict[str, Any]] = []
    first = h2s[0][0] if h2s else len(lines)
    if first:
        result.append({"kind": "topico", "title": "Introdução", "session": None, "text": "".join(lines[:first])})

    for n, (start, h2_title) in enumerate(h2s):
        end = h2s[n + 1][0] if n + 1 < len(h2s) else len(lines)
        block = lines[start:end]
        session_h3s: list[tuple[int, str, int]] = []
        for local_i, line in enumerate(block):
            parsed = heading(line)
            if not parsed or parsed[0] != 3:
                continue
            session = session_from_title(parsed[1])
            if session is not None:
                session_h3s.append((local_i, parsed[1], session))

        if not session_h3s:
            result.append({"kind": "topico", "title": h2_title, "session": None, "text": "".join(block)})
            continue

        prefix_end = session_h3s[0][0]
        if prefix_end:
            result.append({"kind": "topico", "title": h2_title, "session": None, "text": "".join(block[:prefix_end])})
        for i, (local_start, title, session) in enumerate(session_h3s):
            local_end = session_h3s[i + 1][0] if i + 1 < len(session_h3s) else len(block)
            result.append({
                "kind": "descoberta",
                "title": title,
                "session": session,
                "text": "".join(block[local_start:local_end]),
            })
    return result


def generate(root: Path) -> None:
    legacy = root / LEGACY
    if not legacy.is_file():
        raise ValueError(f"legado ausente: {LEGACY}")
    manifest_path = root / MANIFEST
    manifest = load_yaml(manifest_path) or {}
    text = legacy.read_text(encoding="utf-8")

    if (root / KNOW_DIR).exists():
        shutil.rmtree(root / KNOW_DIR)
    (root / KNOW_DIR).mkdir(parents=True, exist_ok=True)

    order: list[str] = []
    topics: list[dict[str, Any]] = []
    sessions: dict[int, list[dict[str, Any]]] = {}
    topic_seq = 0
    session_seq: dict[int, int] = {}

    for section in parse_sections(text):
        title = section["title"]
        session = section["session"]
        if section["kind"] == "descoberta":
            assert isinstance(session, int)
            session_seq[session] = session_seq.get(session, 0) + 1
            seq = session_seq[session]
            base_dir = KNOW_DIR / "descobertas" / f"sessao-{session:03d}"
            base_name = f"{seq:03d}-{slugify(title)}"
        else:
            topic_seq += 1
            base_dir = KNOW_DIR / "topicos"
            base_name = f"{topic_seq:02d}-{slugify(title)}"

        pieces = split_exact_by_bytes(section["text"])
        paths: list[str] = []
        for part_no, piece in enumerate(pieces, 1):
            suffix = "" if len(pieces) == 1 else f"-parte-{part_no:02d}"
            rel = base_dir / f"{base_name}{suffix}.md"
            path = root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(piece.encode("utf-8"))
            order.append(rel.as_posix())
            paths.append(rel.as_posix())
        entry = {"titulo": title, "arquivos": paths, "bytes": sum((root / p).stat().st_size for p in paths)}
        if section["kind"] == "descoberta":
            sessions.setdefault(session, []).append(entry)
        else:
            topics.append(entry)

    session_refs: dict[str, Any] = {}
    for session, entries in sorted(sessions.items()):
        rel = KNOW_DIR / "descobertas" / f"sessao-{session:03d}" / "index.yaml"
        write_yaml(root / rel, {
            "schema_conhecimento_sessao": SCHEMA,
            "sessao": session,
            "quantidade": len(entries),
            "fragmentos": entries,
        })
        session_refs[str(session)] = {"index": rel.as_posix(), "quantidade": len(entries)}

    write_yaml(root / INDEX, {
        "schema_conhecimento": SCHEMA,
        "natureza": "indice_fragmentado",
        "historico_acumulado": LEGACY.as_posix(),
        "topicos": topics,
        "sessoes": session_refs,
    })

    state = load_yaml(root / "estado/estado-atual.yaml") or {}
    current_session = ((state.get("campanha") or {}).get("sessao_atual"))
    known_sessions = sorted(sessions)
    latest = current_session if current_session in sessions else (known_sessions[-1] if known_sessions else None)
    priority_words = ("masao", "ravens bluff", "pistas atuais")
    priority_topics = [entry for entry in topics if any(word in normalize(entry["titulo"]) for word in priority_words)]
    recent = sessions.get(latest, [])[-8:] if latest else []
    write_yaml(root / ACTIVE, {
        "schema_conhecimento_ativo": SCHEMA,
        "natureza": "roteador_derivado",
        "sessao_atual_da_campanha": current_session,
        "sessao_mais_recente_indexada": latest,
        "topicos_prioritarios": priority_topics,
        "descobertas_recentes": recent,
        "observacao": "Roteador de acesso; os fatos permanecem nos fragmentos literais do conhecimento de Ren.",
    })

    knowledge_meta = manifest.setdefault("conhecimento", {})
    knowledge_meta["fragmentos"] = len(order)
    knowledge_meta["ordem_fragmentos"] = order
    knowledge_meta["sessoes_indexadas"] = known_sessions
    write_yaml(manifest_path, manifest)

    errors = check(root)
    if errors:
        raise ValueError("; ".join(errors))
    print(f"OK — conhecimento reindexado em {len(order)} fragmentos; sessões explícitas: {known_sessions}.")


def check(root: Path) -> list[str]:
    errors: list[str] = []
    manifest = load_yaml(root / MANIFEST) or {}
    meta = manifest.get("conhecimento") or {}
    order = meta.get("ordem_fragmentos")
    if not isinstance(order, list) or not order:
        return ["manifesto sem ordem de fragmentos"]
    rebuilt = bytearray()
    for rel in order:
        path = root / str(rel)
        if not path.is_file():
            errors.append(f"fragmento ausente: {rel}")
            continue
        if path.stat().st_size > MAX_FRAGMENT:
            errors.append(f"fragmento grande demais: {rel} ({path.stat().st_size} bytes)")
        rebuilt.extend(path.read_bytes())
    if bytes(rebuilt) != (root / LEGACY).read_bytes():
        errors.append("ordem de fragmentos não reconstrói o legado byte a byte")

    active = load_yaml(root / ACTIVE) or {}
    state = load_yaml(root / "estado/estado-atual.yaml") or {}
    current_session = ((state.get("campanha") or {}).get("sessao_atual"))
    indexed_sessions = meta.get("sessoes_indexadas") or []
    if current_session in indexed_sessions and active.get("sessao_mais_recente_indexada") != current_session:
        errors.append("ativo.yaml não aponta para a sessão atual apesar de ela estar indexada")
    if (root / ACTIVE).stat().st_size > MAX_ACTIVE:
        errors.append(f"ativo.yaml excede {MAX_ACTIVE} bytes")
    for session in indexed_sessions:
        index_path = root / KNOW_DIR / "descobertas" / f"sessao-{int(session):03d}" / "index.yaml"
        if not index_path.is_file():
            errors.append(f"índice de sessão ausente: {session}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT_DEFAULT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = args.repo.resolve()
    try:
        if args.check:
            errors = check(root)
            if errors:
                print("FALHA — índice de conhecimento inválido:")
                for error in errors:
                    print(f"- {error}")
                return 1
            print("OK — conhecimento fragmentado reconstrói o legado e o recorte ativo está coerente.")
            return 0
        generate(root)
        return 0
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"FALHA — {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
