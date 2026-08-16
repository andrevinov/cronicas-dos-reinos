#!/usr/bin/env python3
"""Consulta contexto da campanha com saída pequena, previsível e orientada por domínio.

A ferramenta é a porta normal de leitura operacional. Desde a Etapa 6, relações,
medidores de NPC e conhecimento são resolvidos por índice e por um fragmento
específico, sem carregar os antigos depósitos acumulativos.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc


DEFAULT_MAX_BYTES = 8 * 1024
HARD_MAX_BYTES = 16 * 1024
QUERY_LOG = Path("runtime/consultas-contexto.jsonl")
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".txt", ".json"}
SKIP_DIRS = {".git", "books", "imagens", "__pycache__", "legado"}
REL_INDEX = Path("estado/relacoes/index.yaml")
NPC_INDEX = Path("estado/npcs/index.yaml")
KNOW_INDEX = Path("personagens/jogador/conhecimento/index.yaml")
KNOW_ACTIVE = Path("personagens/jogador/conhecimento/ativo.yaml")
KNOW_ROOT = Path("personagens/jogador/conhecimento")


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def normalize(text: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(text))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = raw.lower().replace("_", " ").replace("-", " ")
    return " ".join(re.findall(r"[a-z0-9]+", raw))


def truncate_text(text: Any, limit: int) -> str:
    value = " ".join(str(text).split())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def compact_value(value: Any, *, string_limit: int, list_limit: int, depth: int) -> Any:
    if depth <= 0:
        if isinstance(value, (dict, list)):
            return "[… conteúdo adicional omitido …]"
        return truncate_text(value, string_limit)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 24:
                out["_omitidos"] = len(value) - index
                break
            out[str(key)] = compact_value(
                item,
                string_limit=string_limit,
                list_limit=list_limit,
                depth=depth - 1,
            )
        return out
    if isinstance(value, list):
        items = [
            compact_value(
                item,
                string_limit=string_limit,
                list_limit=list_limit,
                depth=depth - 1,
            )
            for item in value[:list_limit]
        ]
        if len(value) > list_limit:
            items.append(f"… {len(value) - list_limit} item(ns) omitido(s)")
        return items
    if isinstance(value, str):
        return truncate_text(value, string_limit)
    return value


def serialize(data: Any, as_json: bool) -> str:
    if as_json:
        return json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=110)


def fit_budget(envelope: dict[str, Any], max_bytes: int, as_json: bool) -> tuple[str, bool]:
    max_bytes = max(1024, min(max_bytes, HARD_MAX_BYTES))
    text = serialize(envelope, as_json)
    if len(text.encode("utf-8")) <= max_bytes:
        return text, False

    original_result = envelope.get("resultado")
    for string_limit, list_limit, depth in ((900, 8, 4), (600, 6, 4), (350, 4, 3), (180, 3, 3)):
        candidate = dict(envelope)
        candidate["resultado"] = compact_value(
            original_result,
            string_limit=string_limit,
            list_limit=list_limit,
            depth=depth,
        )
        candidate["truncado_por_orcamento"] = True
        text = serialize(candidate, as_json)
        if len(text.encode("utf-8")) <= max_bytes:
            return text, True

    fallback = {
        "consulta": envelope.get("consulta"),
        "nivel": envelope.get("nivel"),
        "fontes": envelope.get("fontes", []),
        "resultado": {
            "aviso": "Resultado excedeu o orçamento de contexto. Refine a consulta para uma entidade ou termo mais específico."
        },
        "truncado_por_orcamento": True,
    }
    return serialize(fallback, as_json), True


def entity_score(key: str, payload: Any, term: str) -> int:
    query = normalize(term)
    if not query:
        return 0
    key_n = normalize(key)
    name_n = normalize(payload.get("nome")) if isinstance(payload, dict) else ""
    candidates = [key_n, name_n]
    if query in candidates:
        return 100
    if any(value.startswith(query) for value in candidates if value):
        return 85
    if any(query in value for value in candidates if value):
        return 70
    tokens = set(query.split())
    for value in candidates:
        if tokens and tokens.issubset(set(value.split())):
            return 60
    return 0


def resolve_entity(mapping: Any, term: str) -> tuple[str | None, Any | None, list[str]]:
    if not isinstance(mapping, dict):
        return None, None, []
    ranked: list[tuple[int, str, Any]] = []
    for key, payload in mapping.items():
        score = entity_score(str(key), payload, term)
        if score:
            ranked.append((score, str(key), payload))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    if not ranked:
        query = normalize(term)
        suggestions = []
        for key, payload in mapping.items():
            label = payload.get("nome") if isinstance(payload, dict) else key
            if any(token in normalize(label) for token in query.split() if token):
                suggestions.append(str(label))
        return None, None, suggestions[:8]
    best_score = ranked[0][0]
    ties = [item for item in ranked if item[0] == best_score]
    if len(ties) > 1 and best_score < 100:
        names = [
            str(payload.get("nome") or key) if isinstance(payload, dict) else key
            for _, key, payload in ties[:8]
        ]
        return None, None, names
    _, key, payload = ranked[0]
    return key, payload, []


def compact_relation(payload: dict[str, Any]) -> dict[str, Any]:
    """Mantém compatibilidade com chamadas antigas e limita relações já compactas."""
    return compact_value(payload, string_limit=900, list_limit=8, depth=4)


def split_markdown_sections(text: str) -> list[dict[str, Any]]:
    lines = text.splitlines()
    sections: list[dict[str, Any]] = []
    current_heading = "Introdução"
    current_start = 1
    buffer: list[str] = []

    def flush() -> None:
        nonlocal buffer
        body = "\n".join(buffer).strip()
        if body:
            sections.append({"titulo": current_heading, "linha": current_start, "conteudo": body})
        buffer = []

    for lineno, line in enumerate(lines, 1):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if match:
            flush()
            current_heading = match.group(2).strip()
            current_start = lineno
        else:
            buffer.append(line)
    flush()
    return sections


def section_score(section: dict[str, Any], term: str) -> int:
    query = normalize(term)
    if not query:
        return 0
    heading = normalize(section.get("titulo", ""))
    body = normalize(section.get("conteudo", ""))
    score = 0
    if query == heading:
        score += 120
    elif query in heading:
        score += 90
    query_tokens = [token for token in query.split() if token]
    if query in body:
        score += 50
    score += min(30, sum(body.count(token) for token in query_tokens) * 3)
    if query_tokens and all(token in body or token in heading for token in query_tokens):
        score += 25
    return score


def search_markdown_files(
    paths: Iterable[Path], term: str, repo: Path, limit: int = 3
) -> list[dict[str, Any]]:
    ranked: list[tuple[int, str, dict[str, Any]]] = []
    seen: set[Path] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(repo).as_posix()
        for section in split_markdown_sections(text):
            score = section_score(section, term)
            if score:
                ranked.append((score, rel, section))
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]["linha"]))
    return [
        {
            "arquivo": rel,
            "linha": section["linha"],
            "titulo": section["titulo"],
            "relevancia": score,
            "conteudo": truncate_text(section["conteudo"], 2400),
        }
        for score, rel, section in ranked[:limit]
    ]


def _iter_text_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def iter_search_files(repo: Path, *, reserved: bool, historical: bool) -> Iterable[Path]:
    """Escopo da busca genérica.

    A busca normal vê apenas material operacional/público. `historico/` e
    transcrições completas entram somente com --historico; `narrador/` somente
    com --reservado.
    """
    roots = ["estado", "personagens/jogador", "cenario", "regras", "narracao"]
    if reserved:
        roots.append("narrador")
    for root_name in roots:
        yield from _iter_text_files(repo / root_name)

    if historical:
        historical_root = repo / "historico"
        if historical_root.exists():
            for path in historical_root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                    continue
                yield path

    sessions = repo / "sessoes"
    if sessions.exists():
        for session_dir in sessions.iterdir():
            if not session_dir.is_dir():
                continue
            for name in ("resumo.md", "alteracoes-de-estado.yaml", "consequencias.md", "experiencia.md"):
                path = session_dir / name
                if path.is_file():
                    yield path
            if historical:
                trans = session_dir / "transcricao.md"
                if trans.is_file():
                    yield trans


def generic_search(
    repo: Path,
    term: str,
    *,
    reserved: bool,
    historical: bool,
    limit: int = 8,
) -> list[dict[str, Any]]:
    query = normalize(term)
    tokens = [token for token in query.split() if token]
    if not tokens:
        return []
    matches: list[tuple[int, str, int, str]] = []
    for path in iter_search_files(repo, reserved=reserved, historical=historical):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(repo).as_posix()
        for index, line in enumerate(lines):
            line_n = normalize(line)
            if not all(token in line_n for token in tokens):
                continue
            score = 20 + sum(line_n.count(token) for token in tokens)
            start = max(0, index - 1)
            end = min(len(lines), index + 2)
            snippet = " ".join(part.strip() for part in lines[start:end] if part.strip())
            matches.append((score, rel, index + 1, truncate_text(snippet, 650)))
    matches.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [
        {"arquivo": rel, "linha": line, "trecho": snippet}
        for _, rel, line, snippet in matches[:limit]
    ]


def envelope(
    command: str,
    term: str | None,
    level: str,
    sources: list[str],
    result: Any,
) -> dict[str, Any]:
    query: dict[str, Any] = {"comando": command}
    if term is not None:
        query["termo"] = term
    return {"consulta": query, "nivel": level, "fontes": sources, "resultado": result}


def _resolve_index(
    repo: Path,
    index_path: Path,
    mapping_key: str,
    term: str,
) -> tuple[str | None, dict[str, Any] | None, list[str], dict[str, Any]]:
    data = load_yaml(repo / index_path) or {}
    mapping = data.get(mapping_key) if isinstance(data, dict) else None
    key, entry, suggestions = resolve_entity(mapping, term)
    return key, entry if isinstance(entry, dict) else None, suggestions, data


def _load_fragment(repo: Path, entry: dict[str, Any] | None, payload_key: str) -> tuple[Any, str | None]:
    if not entry:
        return None, None
    rel = entry.get("arquivo")
    if not isinstance(rel, str):
        return None, None
    doc = load_yaml(repo / rel) or {}
    payload = doc.get(payload_key) if isinstance(doc, dict) else None
    return payload, rel


def command_scene(repo: Path) -> dict[str, Any]:
    context = load_yaml(repo / "runtime/contexto.yaml")
    scene = load_yaml(repo / "runtime/cena.yaml")
    return envelope(
        "cena",
        None,
        "L1-L2",
        ["runtime/contexto.yaml", "runtime/cena.yaml"],
        {"contexto": context, "cena": scene},
    )


def command_status(repo: Path) -> dict[str, Any]:
    context = load_yaml(repo / "runtime/contexto.yaml")
    return envelope("status", None, "L1", ["runtime/contexto.yaml"], context)


def command_relation(repo: Path, term: str) -> dict[str, Any]:
    key, entry, suggestions, _ = _resolve_index(repo, REL_INDEX, "relacoes", term)
    if entry is None:
        return envelope(
            "relacao",
            term,
            "L2",
            [REL_INDEX.as_posix()],
            {"encontrado": False, "candidatos": suggestions},
        )

    payload, fragment = _load_fragment(repo, entry, "relacao")
    if not isinstance(payload, dict):
        raise ValueError(f"fragmento de relação inválido para {key}")
    sources = [REL_INDEX.as_posix()]
    if fragment:
        sources.append(fragment)
    result = {
        "encontrado": True,
        "id": key,
        "relacao": compact_relation(payload),
        "historico_disponivel": entry.get("historico"),
    }
    return envelope("relacao", term, "L2", sources, result)


def command_npc(repo: Path, term: str) -> dict[str, Any]:
    med_key, med_entry, med_suggestions, _ = _resolve_index(repo, NPC_INDEX, "npcs", term)
    rel_key, rel_entry, rel_suggestions, _ = _resolve_index(repo, REL_INDEX, "relacoes", term)

    med_payload, med_fragment = _load_fragment(repo, med_entry, "npc")
    rel_payload, rel_fragment = _load_fragment(repo, rel_entry, "relacao")
    found = isinstance(med_payload, dict) or isinstance(rel_payload, dict)
    result: dict[str, Any] = {"encontrado": found, "medidores": None, "relacao": None}
    sources = [NPC_INDEX.as_posix(), REL_INDEX.as_posix()]

    if isinstance(med_payload, dict):
        result["medidores"] = {
            "id": med_key,
            "dados": compact_value(med_payload, string_limit=750, list_limit=6, depth=4),
        }
        if med_fragment:
            sources.append(med_fragment)
    if isinstance(rel_payload, dict):
        result["relacao"] = {
            "id": rel_key,
            "dados": compact_relation(rel_payload),
            "historico_disponivel": rel_entry.get("historico") if rel_entry else None,
        }
        if rel_fragment:
            sources.append(rel_fragment)
    if not found:
        result["candidatos"] = list(dict.fromkeys(med_suggestions + rel_suggestions))[:8]

    return envelope("npc", term, "L2", list(dict.fromkeys(sources)), result)


def _knowledge_active_paths(repo: Path) -> list[Path]:
    active = load_yaml(repo / KNOW_ACTIVE) or {}
    paths: list[Path] = []
    for group in ("topicos_prioritarios", "descobertas_recentes", "incrementais_recentes"):
        for entry in active.get(group, []) if isinstance(active, dict) else []:
            if not isinstance(entry, dict):
                continue
            for rel in entry.get("arquivos", []):
                path = repo / str(rel)
                if path.is_file():
                    paths.append(path)
    return paths


def command_knowledge(repo: Path, term: str) -> dict[str, Any]:
    active_paths = _knowledge_active_paths(repo)
    active_matches = search_markdown_files(active_paths, term, repo, limit=3)

    # Um acerto forte no recorte ativo já basta. Caso contrário, o processo local
    # pesquisa os demais fragmentos; apenas os trechos vencedores entram no contexto.
    if active_matches and active_matches[0]["relevancia"] >= 90:
        matches = active_matches
        level = "L2"
    else:
        all_paths = sorted(
            path for path in (repo / KNOW_ROOT).rglob("*.md")
            if path.is_file()
        )
        matches = search_markdown_files(all_paths, term, repo, limit=3)
        level = "L2-L3"

    sources = [KNOW_ACTIVE.as_posix(), KNOW_INDEX.as_posix()]
    sources.extend(item["arquivo"] for item in matches)
    return envelope(
        "conhecimento",
        term,
        level,
        list(dict.fromkeys(sources)),
        {"encontrado": bool(matches), "trechos": matches},
    )


def command_rule(repo: Path, term: str) -> dict[str, Any]:
    rules = sorted((repo / "regras").glob("*.md"))
    matches = search_markdown_files(rules, term, repo, limit=3)
    sources = list(dict.fromkeys(item["arquivo"] for item in matches)) or ["regras/"]
    return envelope(
        "regra",
        term,
        "L2-L3",
        sources,
        {"encontrado": bool(matches), "trechos": matches},
    )


def command_search(
    repo: Path,
    term: str,
    *,
    reserved: bool,
    historical: bool,
) -> dict[str, Any]:
    matches = generic_search(repo, term, reserved=reserved, historical=historical, limit=8)
    level = "L4" if historical else "L3"
    sources = list(dict.fromkeys(item["arquivo"] for item in matches))
    scope = {
        "reservado": reserved,
        "historico_com_transcricoes_e_arquivos_frios": historical,
    }
    return envelope(
        "buscar",
        term,
        level,
        sources,
        {"escopo": scope, "encontrado": bool(matches), "ocorrencias": matches},
    )


def log_query(repo: Path, data: dict[str, Any], output_bytes: int, truncated: bool) -> None:
    path = repo / QUERY_LOG
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts_utc": datetime.now(timezone.utc).isoformat(),
        "comando": (data.get("consulta") or {}).get("comando"),
        "termo": (data.get("consulta") or {}).get("termo"),
        "nivel": data.get("nivel"),
        "fontes": len(data.get("fontes") or []),
        "bytes_saida": output_bytes,
        "truncado": truncated,
    }
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="emite JSON em vez de YAML")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help=f"orçamento máximo de saída; padrão {DEFAULT_MAX_BYTES} bytes, teto {HARD_MAX_BYTES}",
    )
    parser.add_argument("--sem-log", action="store_true", help="não registra metadados locais da consulta")

    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("cena", help="contexto quente + recorte imediato da cena")
    sub.add_parser("status", help="somente o contexto quente operacional")

    for name, help_text in (
        ("npc", "medidores e relação atual de um NPC"),
        ("relacao", "relação atual com uma entidade"),
        ("conhecimento", "o que Ren sabe sobre um assunto"),
        ("regra", "trechos das regras internas sobre um assunto"),
    ):
        child = sub.add_parser(name, help=help_text)
        child.add_argument("termo")

    search = sub.add_parser("buscar", help="busca limitada por ponteiros e ocorrências")
    search.add_argument("termo")
    search.add_argument("--reservado", action="store_true", help="inclui narrador/ na busca")
    search.add_argument(
        "--historico",
        action="store_true",
        help="inclui transcrições e histórico frio; usar somente após fontes correntes não bastarem",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo = args.repo.resolve()
    try:
        if args.command == "cena":
            data = command_scene(repo)
        elif args.command == "status":
            data = command_status(repo)
        elif args.command == "npc":
            data = command_npc(repo, args.termo)
        elif args.command == "relacao":
            data = command_relation(repo, args.termo)
        elif args.command == "conhecimento":
            data = command_knowledge(repo, args.termo)
        elif args.command == "regra":
            data = command_rule(repo, args.termo)
        elif args.command == "buscar":
            data = command_search(
                repo,
                args.termo,
                reserved=args.reservado,
                historical=args.historico,
            )
        else:
            raise ValueError(f"comando desconhecido: {args.command}")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        print(f"FALHA DE CONSULTA — {exc}")
        return 1

    text, truncated = fit_budget(data, args.max_bytes, args.json)
    output_bytes = len(text.encode("utf-8"))
    if not args.sem_log:
        try:
            log_query(repo, data, output_bytes, truncated)
        except OSError:
            pass
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
