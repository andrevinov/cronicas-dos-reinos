#!/usr/bin/env python3
"""Rastros observáveis entre a verdade reservada do mundo e o conhecimento de Ren.

Um rastro registra somente o que pode ser percebido. A causa verdadeira permanece
na fonte canônica apontada por ``origem`` e não é exposta por consultas normais.
Esta etapa não instala conhecimento: ``preparar-descoberta`` apenas devolve um
delta sugerido para o pipeline transacional, cuja integração automática pertence
ao passo 8 do Mundo Vivo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

import yaml

import mundo

INDEX = Path("narrador/rastros/index.yaml")
ITEMS = Path("narrador/rastros/itens")
CURRENT_STATE = Path("estado/estado-atual.yaml")
TIME = mundo.TIME_PATH

VALID_TYPES = {"fisico", "documental", "rumor", "comportamental", "institucional"}
VALID_SCOPES = {"cidade", "area", "ponto"}
VALID_ACCESS = {"automatico", "investigacao", "interacao", "rumor"}
FORBIDDEN_SOURCE_PREFIXES = (
    "narrador/eventos/cartas/",
    "narrador/rastros/",
)
FORBIDDEN_SOURCES = {
    "narrador/eventos/estado.yaml",
    "narrador/mundo/estado.yaml",
}
MAX_INDEX_BYTES = 16384


class TraceError(ValueError):
    pass


def configured(repo: Path) -> bool:
    return (repo / INDEX).is_file()


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TraceError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise TraceError(f"YAML inválido em {path}: {exc}") from exc


def _atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
        handle.flush()
        os.fsync(handle.fileno())
        tmp = Path(handle.name)
    os.replace(tmp, path)


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TraceError(f"{label} deve ser texto não vazio")
    return value.strip()


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TraceError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise TraceError(f"{label} deve ser lista")
    return value


def _norm(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in raw).split())


def _repo_path(repo: Path, raw: str, prefix: Path | None = None) -> Path:
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        raise TraceError(f"caminho fora do repo: {raw}")
    if prefix is not None:
        try:
            rel.relative_to(prefix)
        except ValueError as exc:
            raise TraceError(f"caminho {raw} deve ficar sob {prefix.as_posix()}") from exc
    return repo / rel


def _instant(value: Any, label: str) -> mundo.WorldInstant:
    value = _map(value, label)
    return mundo.parse_instant(
        _text(value.get("data"), f"{label}.data"),
        _text(value.get("hora"), f"{label}.hora"),
    )


def load_index(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / INDEX), INDEX.as_posix())
    if data.get("schema_indice_rastros") != 1 or data.get("natureza") != "reservado":
        raise TraceError("índice de rastros inválido")
    traces = _map(data.get("rastros"), "rastros")
    if (repo / INDEX).stat().st_size > MAX_INDEX_BYTES:
        raise TraceError(f"índice de rastros excede {MAX_INDEX_BYTES} bytes; arquivar/fragmentar")
    files: set[str] = set()
    for trace_id, meta in traces.items():
        _validate_route(repo, trace_id, meta)
        raw = meta["arquivo"]
        if raw in files:
            raise TraceError(f"arquivo de rastro duplicado: {raw}")
        files.add(raw)
    return data


def _validate_location(value: Any, label: str) -> dict[str, Any]:
    loc = _map(value, label)
    scope = _text(loc.get("escopo"), f"{label}.escopo")
    if scope not in VALID_SCOPES:
        raise TraceError(f"{label}.escopo inválido: {scope}")
    city = _text(loc.get("cidade"), f"{label}.cidade")
    area = loc.get("area")
    point = loc.get("ponto")
    if scope in {"area", "ponto"}:
        _text(area, f"{label}.area")
    if scope == "ponto":
        _text(point, f"{label}.ponto")
    return {"escopo": scope, "cidade": city, "area": area, "ponto": point}


def _validate_persistence(value: Any, label: str) -> dict[str, Any]:
    persistence = _map(value, label)
    available = _instant(persistence.get("disponivel_de"), f"{label}.disponivel_de")
    expires_raw = persistence.get("expira_em")
    expires = None if expires_raw is None else _instant(expires_raw, f"{label}.expira_em")
    if expires is not None and expires <= available:
        raise TraceError(f"{label}.expira_em precisa ser posterior a disponivel_de")
    return persistence


def _validate_route(repo: Path, trace_id: str, meta: Any) -> dict[str, Any]:
    if not isinstance(trace_id, str) or not trace_id:
        raise TraceError("id de rastro inválido")
    meta = _map(meta, f"rastros.{trace_id}")
    _text(meta.get("nome"), f"{trace_id}.nome")
    kind = _text(meta.get("tipo"), f"{trace_id}.tipo")
    if kind not in VALID_TYPES:
        raise TraceError(f"{trace_id}: tipo inválido")
    access = _text(meta.get("acesso"), f"{trace_id}.acesso")
    if access not in VALID_ACCESS:
        raise TraceError(f"{trace_id}: acesso inválido")
    _validate_location(meta.get("localizacao"), f"{trace_id}.localizacao")
    _validate_persistence(meta.get("persistencia"), f"{trace_id}.persistencia")
    tags = _list(meta.get("tags"), f"{trace_id}.tags")
    if not tags:
        raise TraceError(f"{trace_id}: tags vazias")
    for pos, tag in enumerate(tags):
        _text(tag, f"{trace_id}.tags[{pos}]")
    raw = _text(meta.get("arquivo"), f"{trace_id}.arquivo")
    _repo_path(repo, raw, ITEMS)
    return meta


def _validate_source(repo: Path, origin: Any, trace_id: str) -> dict[str, Any]:
    origin = _map(origin, f"{trace_id}.origem")
    if origin.get("estatuto") != "fato_canonico":
        raise TraceError(f"{trace_id}: origem.estatuto deve ser fato_canonico")
    raw = _text(origin.get("fonte"), f"{trace_id}.origem.fonte")
    if raw in FORBIDDEN_SOURCES or any(raw.startswith(prefix) for prefix in FORBIDDEN_SOURCE_PREFIXES):
        raise TraceError(f"{trace_id}: fonte operacional/não canônica não pode originar rastro: {raw}")
    source = _repo_path(repo, raw)
    if not source.is_file():
        raise TraceError(f"{trace_id}: fonte canônica inexistente: {raw}")
    evidence = _text(origin.get("evidencia"), f"{trace_id}.origem.evidencia")
    if evidence not in source.read_text(encoding="utf-8"):
        raise TraceError(f"{trace_id}: evidência não encontrada literalmente em {raw}")
    reference = origin.get("referencia")
    if reference is not None:
        _text(reference, f"{trace_id}.origem.referencia")
    return origin


def validate_trace(repo: Path, trace_id: str, meta: dict[str, Any]) -> dict[str, Any]:
    raw = meta["arquivo"]
    doc = _map(_load(_repo_path(repo, raw, ITEMS)), raw)
    if doc.get("schema_rastro") != 1 or doc.get("natureza") != "reservado":
        raise TraceError(f"{trace_id}: fragmento inválido")
    if doc.get("estatuto") != "evidencia_observavel_nao_conhecimento":
        raise TraceError(f"{trace_id}: estatuto inválido")
    if doc.get("id") != trace_id:
        raise TraceError(f"{trace_id}: id diverge do fragmento")
    for field in ("nome", "tipo", "acesso", "localizacao", "persistencia", "tags"):
        if doc.get(field) != meta.get(field):
            raise TraceError(f"{trace_id}: {field} diverge do índice")
    _text(doc.get("manifestacao"), f"{trace_id}.manifestacao")
    _text(doc.get("fato_observavel"), f"{trace_id}.fato_observavel")
    _validate_source(repo, doc.get("origem"), trace_id)
    return doc


def _canonical_location(repo: Path) -> dict[str, str]:
    state = _map(_load(repo / CURRENT_STATE), CURRENT_STATE.as_posix())
    loc = _map(state.get("localizacao"), "estado.localizacao")
    return {
        "cidade": str(loc.get("cidade") or ""),
        "area": str(loc.get("area") or ""),
        "ponto": str(loc.get("ponto_exato") or ""),
    }


def _location_matches(trace_loc: dict[str, Any], current: dict[str, str]) -> bool:
    if _norm(trace_loc["cidade"]) != _norm(current.get("cidade")):
        return False
    scope = trace_loc["escopo"]
    if scope == "cidade":
        return True
    if _norm(trace_loc.get("area")) != _norm(current.get("area")):
        return False
    if scope == "area":
        return True
    return _norm(trace_loc.get("ponto")) == _norm(current.get("ponto"))


def _active_at(meta: dict[str, Any], when: mundo.WorldInstant) -> bool:
    persistence = meta["persistencia"]
    if when < _instant(persistence["disponivel_de"], "disponivel_de"):
        return False
    expires = persistence.get("expira_em")
    return expires is None or when < _instant(expires, "expira_em")


def candidates(
    repo: Path,
    *,
    access: str = "automatico",
    city: str | None = None,
    area: str | None = None,
    point: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    if access != "todos" and access not in VALID_ACCESS:
        raise TraceError(f"acesso inválido: {access}")
    index = load_index(repo)
    current = _canonical_location(repo)
    if city is not None:
        current["cidade"] = city
    if area is not None:
        current["area"] = area
    if point is not None:
        current["ponto"] = point
    now, _ = mundo.load_canonical_time(repo)
    wanted = {_norm(tag) for tag in (tags or []) if str(tag).strip()}
    result = []
    for trace_id, meta in index["rastros"].items():
        if access != "todos" and meta["acesso"] != access:
            continue
        if not _active_at(meta, now) or not _location_matches(meta["localizacao"], current):
            continue
        trace_tags = {_norm(tag) for tag in meta["tags"]}
        if wanted and not (wanted & trace_tags):
            continue
        result.append(
            {
                "id": trace_id,
                "nome": meta["nome"],
                "tipo": meta["tipo"],
                "acesso": meta["acesso"],
                "escopo": meta["localizacao"]["escopo"],
                "tags": meta["tags"],
            }
        )
    result.sort(key=lambda item: (item["acesso"], item["tipo"], item["id"]))
    return {
        "localizacao": current,
        "acesso": access,
        "rastros": result,
        "fontes_lidas": [INDEX.as_posix(), CURRENT_STATE.as_posix(), TIME.as_posix()],
    }


def _resolve(index: dict[str, Any], query: str) -> tuple[str, dict[str, Any]]:
    if query in index["rastros"]:
        return query, index["rastros"][query]
    needle = _norm(query)
    hits = []
    for trace_id, meta in index["rastros"].items():
        pool = {_norm(trace_id), _norm(meta["nome"])}
        if needle in pool or any(needle and needle in item for item in pool):
            hits.append((trace_id, meta))
    if len(hits) != 1:
        raise TraceError(f"rastro não encontrado/ambíguo: {query}")
    return hits[0]


def show(repo: Path, query: str) -> dict[str, Any]:
    index = load_index(repo)
    trace_id, meta = _resolve(index, query)
    doc = validate_trace(repo, trace_id, meta)
    visible = {
        key: doc[key]
        for key in (
            "id",
            "nome",
            "tipo",
            "manifestacao",
            "fato_observavel",
            "localizacao",
            "acesso",
            "persistencia",
            "tags",
        )
    }
    return {
        "rastro_id": trace_id,
        "resultado": visible,
        "fontes_lidas": [INDEX.as_posix(), meta["arquivo"]],
        "origem_reservada_exposta": False,
    }


def prepare_discovery(repo: Path, query: str) -> dict[str, Any]:
    shown = show(repo, query)
    trace = shown["resultado"]
    delta = {
        "alvo": "conhecimento",
        "op": "registrar",
        "visibilidade": "operacional",
        "valor": {
            "tipo": "rastro_descoberto",
            "rastro": trace["id"],
            "texto": trace["fato_observavel"],
            "fonte": f"rastro:{trace['id']}",
        },
    }
    return {
        **shown,
        "instalou_conhecimento": False,
        "delta_sugerido": delta,
        "nota": "Passo 7 somente prepara a descoberta; o passo 8 integra este delta à transação do turno.",
    }


def _canonical_spec(repo: Path, spec: Any) -> tuple[str, dict[str, Any], dict[str, Any]]:
    spec = _map(spec, "rastro")
    name = _text(spec.get("nome"), "nome")
    kind = _text(spec.get("tipo"), "tipo")
    if kind not in VALID_TYPES:
        raise TraceError("tipo de rastro inválido")
    manifestation = _text(spec.get("manifestacao"), "manifestacao")
    observable = _text(spec.get("fato_observavel"), "fato_observavel")
    access = _text(spec.get("acesso"), "acesso")
    if access not in VALID_ACCESS:
        raise TraceError("acesso de rastro inválido")
    location = _validate_location(spec.get("localizacao"), "localizacao")
    persistence = _validate_persistence(spec.get("persistencia"), "persistencia")
    tags = _list(spec.get("tags"), "tags")
    if not tags:
        raise TraceError("tags vazias")
    tags = [_text(tag, "tag") for tag in tags]
    origin = _validate_source(repo, spec.get("origem"), "novo_rastro")
    stable = {
        "nome": name,
        "tipo": kind,
        "manifestacao": manifestation,
        "fato_observavel": observable,
        "acesso": access,
        "localizacao": location,
        "persistencia": persistence,
        "tags": tags,
        "origem": origin,
    }
    trace_id = spec.get("id")
    if trace_id is None:
        seed = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        trace_id = "rastro-" + hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    trace_id = _text(trace_id, "id")
    if any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_-" for ch in trace_id):
        raise TraceError("id de rastro deve usar minúsculas, números, _ ou -")
    raw = f"{ITEMS.as_posix()}/{trace_id}.yaml"
    meta = {
        "nome": name,
        "tipo": kind,
        "acesso": access,
        "localizacao": location,
        "persistencia": persistence,
        "tags": tags,
        "arquivo": raw,
    }
    doc = {
        "schema_rastro": 1,
        "natureza": "reservado",
        "estatuto": "evidencia_observavel_nao_conhecimento",
        "id": trace_id,
        "nome": name,
        "tipo": kind,
        "manifestacao": manifestation,
        "fato_observavel": observable,
        "localizacao": location,
        "acesso": access,
        "persistencia": persistence,
        "tags": tags,
        "origem": origin,
    }
    return trace_id, meta, doc


def register(repo: Path, spec: Any) -> dict[str, Any]:
    index = load_index(repo)
    trace_id, meta, doc = _canonical_spec(repo, spec)
    path = repo / meta["arquivo"]
    existing_meta = index["rastros"].get(trace_id)
    if path.exists():
        existing_doc = _load(path)
        if existing_doc != doc:
            raise TraceError(f"{trace_id}: fragmento existente diverge do retry")
    else:
        _atomic(path, doc)
    if existing_meta is not None and existing_meta != meta:
        raise TraceError(f"{trace_id}: entrada existente diverge do retry")
    changed = existing_meta is None
    if changed:
        index["rastros"][trace_id] = meta
        _atomic(repo / INDEX, index)
    return {
        "ok": True,
        "rastro_id": trace_id,
        "criado": changed,
        "conhecimento_alterado": False,
        "fontes_escritas": [meta["arquivo"]] + ([INDEX.as_posix()] if changed else []),
    }


def status(repo: Path) -> dict[str, Any]:
    index = load_index(repo)
    now, _ = mundo.load_canonical_time(repo)
    active = sum(1 for meta in index["rastros"].values() if _active_at(meta, now))
    return {
        "quantidade_indexada": len(index["rastros"]),
        "ativos_no_tempo_atual": active,
        "fontes_lidas": [INDEX.as_posix(), TIME.as_posix()],
    }


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    count = 0
    try:
        index = load_index(repo)
        count = len(index["rastros"])
        for trace_id, meta in index["rastros"].items():
            validate_trace(repo, trace_id, meta)
    except (TraceError, mundo.WorldEngineError) as exc:
        errors.append(str(exc))
    return {"ok": not errors, "quantidade_rastros": count, "erros": list(dict.fromkeys(errors))}


def _spec_from_stdin() -> Any:
    raw = sys.stdin.read()
    if not raw.strip():
        raise TraceError("registrar exige YAML/JSON em stdin")
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise TraceError(f"stdin inválido: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("validar")
    sub.add_parser("registrar", help="lê uma especificação YAML/JSON de stdin")
    show_p = sub.add_parser("mostrar")
    show_p.add_argument("rastro")
    prep = sub.add_parser("preparar-descoberta")
    prep.add_argument("rastro")
    cand = sub.add_parser("candidatos")
    cand.add_argument("--acesso", default="automatico", choices=sorted(VALID_ACCESS | {"todos"}))
    cand.add_argument("--cidade")
    cand.add_argument("--area")
    cand.add_argument("--ponto")
    cand.add_argument("--tag", action="append", default=[])
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "status":
            result = status(repo)
        elif args.cmd == "validar":
            result = validate_repo(repo)
        elif args.cmd == "registrar":
            result = register(repo, _spec_from_stdin())
        elif args.cmd == "mostrar":
            result = show(repo, args.rastro)
        elif args.cmd == "preparar-descoberta":
            result = prepare_discovery(repo, args.rastro)
        else:
            result = candidates(
                repo,
                access=args.acesso,
                city=args.cidade,
                area=args.area,
                point=args.ponto,
                tags=args.tag,
            )
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0 if args.cmd != "validar" or result["ok"] else 1
    except (TraceError, mundo.WorldEngineError) as exc:
        print(f"erro: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
