#!/usr/bin/env python3
"""Rastros observáveis com descoberta transacional atômica.

O passo 7 permanece em ``_rastros_core.py``. Este wrapper acrescenta estado
operacional mínimo (`ativo`/`descoberto`) e prepara/registre a descoberta pelo
mesmo writer de turno usado pela campanha. A origem reservada continua redigida.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml
import _rastros_core as _base

for _name in dir(_base):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_base, _name)

VALID_TRACE_STATES = {"ativo", "descoberto"}


def load_index(repo: Path) -> dict[str, Any]:
    data = _base.load_index(repo)
    for trace_id, meta in data["rastros"].items():
        state = meta.get("estado", "ativo")
        if state not in VALID_TRACE_STATES:
            raise TraceError(f"{trace_id}: estado operacional inválido: {state}")
    return data


def register(repo: Path, spec: Any) -> dict[str, Any]:
    index = load_index(repo)
    trace_id, meta, doc = _base._canonical_spec(repo, spec)
    meta = dict(meta)
    meta["estado"] = "ativo"
    path = repo / meta["arquivo"]
    existing_meta = index["rastros"].get(trace_id)

    if path.exists():
        existing_doc = _base._load(path)
        if existing_doc != doc:
            raise TraceError(f"{trace_id}: fragmento existente diverge do retry")
    else:
        _base._atomic(path, doc)

    if existing_meta is not None:
        old_static = {k: v for k, v in existing_meta.items() if k != "estado"}
        new_static = {k: v for k, v in meta.items() if k != "estado"}
        if old_static != new_static:
            raise TraceError(f"{trace_id}: entrada existente diverge do retry")
        return {
            "ok": True,
            "rastro_id": trace_id,
            "criado": False,
            "conhecimento_alterado": False,
            "fontes_escritas": [],
        }

    index["rastros"][trace_id] = meta
    _base._atomic(repo / INDEX, index)
    return {
        "ok": True,
        "rastro_id": trace_id,
        "criado": True,
        "conhecimento_alterado": False,
        "fontes_escritas": [meta["arquivo"], INDEX.as_posix()],
    }


def candidates(
    repo: Path,
    *,
    access: str = "automatico",
    city: str | None = None,
    area: str | None = None,
    point: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    result = _base.candidates(
        repo,
        access=access,
        city=city,
        area=area,
        point=point,
        tags=tags,
    )
    index = load_index(repo)
    result["rastros"] = [
        item
        for item in result["rastros"]
        if index["rastros"].get(item["id"], {}).get("estado", "ativo") == "ativo"
    ]
    return result


def _assert_discoverable_now(repo: Path, trace_id: str, meta: dict[str, Any]) -> None:
    if meta.get("estado", "ativo") != "ativo":
        raise TraceError(f"{trace_id}: rastro já foi descoberto por Ren")
    now, _ = mundo.load_canonical_time(repo)
    current = _base._canonical_location(repo)
    if not _base._active_at(meta, now):
        raise TraceError(f"{trace_id}: rastro não está disponível no tempo canônico atual")
    if not _base._location_matches(meta["localizacao"], current):
        raise TraceError(f"{trace_id}: rastro não está no escopo espacial atual de Ren")


def prepare_discovery(repo: Path, query: str) -> dict[str, Any]:
    index = load_index(repo)
    trace_id, meta = _base._resolve(index, query)
    _assert_discoverable_now(repo, trace_id, meta)
    shown = _base.show(repo, trace_id)
    trace = shown["resultado"]
    knowledge_delta = {
        "alvo": "conhecimento",
        "op": "registrar",
        "visibilidade": "operacional",
        "valor": {
            "tipo": "rastro_descoberto",
            "rastro": trace_id,
            "texto": trace["fato_observavel"],
            "fonte": f"rastro:{trace_id}",
        },
    }
    trace_delta = {
        "alvo": f"rastro:{trace_id}",
        "op": "set",
        "caminho": "estado",
        "valor": "descoberto",
        "visibilidade": "narrador",
    }
    return {
        **shown,
        "instalou_conhecimento": False,
        "delta_sugerido": knowledge_delta,
        "deltas_transacionais": [knowledge_delta, trace_delta],
        "nota": (
            "Inclua os dois deltas na mesma transação de turno; conhecimento e estado "
            "do rastro serão consolidados no mesmo journal."
        ),
    }


def discover(repo: Path, query: str, transaction: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(transaction, dict):
        raise TraceError("descobrir exige uma transação JSON")
    prepared = prepare_discovery(repo, query)
    tx = dict(transaction)
    existing = tx.get("deltas") or []
    if not isinstance(existing, list):
        raise TraceError("deltas da transação precisam ser lista")
    tx["deltas"] = [*existing, *prepared["deltas_transacionais"]]
    try:
        import turno
        result = turno.register_transaction(repo, tx)
    except Exception as exc:
        if isinstance(exc, TraceError):
            raise
        raise TraceError(str(exc)) from exc
    return {
        "ok": True,
        "rastro_id": prepared["rastro_id"],
        "turno": result,
        "consolidado": bool(result.get("consolidada")),
        "nota": "A descoberta foi registrada pelo mesmo writer transacional de turno.",
    }


def status(repo: Path) -> dict[str, Any]:
    index = load_index(repo)
    now, _ = mundo.load_canonical_time(repo)
    active = sum(
        1
        for meta in index["rastros"].values()
        if meta.get("estado", "ativo") == "ativo" and _base._active_at(meta, now)
    )
    discovered = sum(1 for meta in index["rastros"].values() if meta.get("estado") == "descoberto")
    return {
        "quantidade_indexada": len(index["rastros"]),
        "ativos_no_tempo_atual": active,
        "descobertos_por_ren": discovered,
        "fontes_lidas": [INDEX.as_posix(), TIME.as_posix()],
    }


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    count = 0
    try:
        index = load_index(repo)
        count = len(index["rastros"])
        for trace_id, meta in index["rastros"].items():
            _base.validate_trace(repo, trace_id, meta)
    except (TraceError, mundo.WorldEngineError) as exc:
        errors.append(str(exc))
    return {"ok": not errors, "quantidade_rastros": count, "erros": list(dict.fromkeys(errors))}


def _transaction_from_stdin() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        raise TraceError("descobrir exige transação JSON em stdin")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TraceError(f"JSON da transação inválido: {exc}") from exc
    if not isinstance(value, dict):
        raise TraceError("transação precisa ser objeto JSON")
    return value


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
    disc = sub.add_parser("descobrir")
    disc.add_argument("rastro")
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
            result = register(repo, _base._spec_from_stdin())
        elif args.cmd == "mostrar":
            result = _base.show(repo, args.rastro)
        elif args.cmd == "preparar-descoberta":
            result = prepare_discovery(repo, args.rastro)
        elif args.cmd == "descobrir":
            result = discover(repo, args.rastro, _transaction_from_stdin())
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
