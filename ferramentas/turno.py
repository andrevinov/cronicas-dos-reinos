#!/usr/bin/env python3
"""Registra um avanço narrativo em duas escritas: transcrição + deltas pendentes.

Uso preferencial em uma única chamada de ferramenta:

    python3 ferramentas/turno.py registrar <<'JSON'
    {
      "jogador": "Ren tenta ...",
      "narracao": "...",
      "resumo": "Ren alcança o alvo e gasta 1 Ki.",
      "modo": "combate",
      "deltas": [
        {"alvo": "estado", "op": "inc", "caminho": "recursos.ki.atuais", "valor": -1}
      ]
    }
    JSON

A operação é idempotente. Se houver interrupção entre as duas escritas, repetir a
mesma entrada repara somente o lado ausente sem duplicar o outro.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

from transacoes import (
    PENDING_PATH,
    TransactionError,
    build_pending_record,
    load_pending,
    record_fingerprint,
    transaction_marker,
    validate_pending_record,
)

MAX_PENDING_BYTES = 512 * 1024


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def current_session(repo: Path) -> int:
    runtime = load_yaml(repo / "runtime/contexto.yaml") or {}
    session = ((runtime.get("sessao") or {}).get("numero")) if isinstance(runtime, dict) else None
    if not isinstance(session, int) or session < 1:
        raise TransactionError("runtime/contexto.yaml não define sessão atual válida")
    return session


def read_transaction(path: Path | None) -> dict[str, Any]:
    if path is None:
        raw = sys.stdin.read()
    else:
        raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        raise TransactionError("entrada JSON da transação está vazia")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TransactionError(f"JSON da transação inválido: {exc}") from exc
    if not isinstance(value, dict):
        raise TransactionError("transação precisa ser objeto JSON")
    return value


def normalize_transaction(repo: Path, transaction: dict[str, Any]) -> tuple[dict[str, Any], int]:
    session = transaction.get("sessao", current_session(repo))
    if not isinstance(session, int) or session < 1:
        raise TransactionError("sessao precisa ser inteiro positivo")
    active = current_session(repo)
    if session != active:
        raise TransactionError(f"transação é da sessão {session}, mas runtime está na sessão {active}")

    narration = transaction.get("narracao")
    if not isinstance(narration, str) or not narration.strip():
        raise TransactionError("narracao precisa ser string não vazia")
    player = transaction.get("jogador")
    if player is not None and not isinstance(player, str):
        raise TransactionError("jogador precisa ser string quando presente")

    record = build_pending_record(transaction, session)
    normalized = dict(transaction)
    normalized["id"] = record["id"]
    normalized["sessao"] = session
    normalized["resumo"] = record["resumo"]
    normalized["deltas"] = record.get("deltas", [])
    return normalized, session


def render_transcript_block(transaction: dict[str, Any]) -> str:
    marker = transaction_marker(str(transaction["id"]))
    parts = [marker]
    player = (transaction.get("jogador") or "").strip()
    if player:
        parts.extend(["**Jogador**", "", player])
    parts.extend(["**Narrador**", "", str(transaction["narracao"]).strip()])
    return "\n".join(parts).rstrip() + "\n"


def _append_block(existing: str, block: str) -> str:
    if not existing:
        return block
    return existing.rstrip() + "\n\n" + block


def _append_jsonl(existing: str, record: dict[str, Any]) -> str:
    line = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if not existing:
        return line + "\n"
    return existing.rstrip("\n") + "\n" + line + "\n"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def register_transaction(repo: Path, transaction: dict[str, Any]) -> dict[str, Any]:
    normalized, session = normalize_transaction(repo, transaction)
    record = build_pending_record(normalized, session)
    transaction_id = record["id"]
    transcript_path = repo / "sessoes" / f"{session:03d}" / "transcricao.md"
    pending_path = repo / PENDING_PATH
    if not transcript_path.is_file():
        raise TransactionError(f"transcrição da sessão não existe: {transcript_path.relative_to(repo)}")
    if not pending_path.exists():
        raise TransactionError(f"arquivo pendente não existe: {PENDING_PATH}")

    transcript = transcript_path.read_text(encoding="utf-8")
    pending_text = pending_path.read_text(encoding="utf-8")
    marker = transaction_marker(transaction_id)
    marker_count = transcript.count(marker)
    if marker_count > 1:
        raise TransactionError(f"marcador transacional duplicado na transcrição: {transaction_id}")

    existing_records = load_pending(repo)
    by_id = {item["id"]: item for item in existing_records}
    existing_record = by_id.get(transaction_id)
    if existing_record is not None and record_fingerprint(existing_record) != record_fingerprint(record):
        raise TransactionError(
            f"id {transaction_id} já existe com conteúdo diferente; não sobrescrever silenciosamente"
        )

    need_transcript = marker_count == 0
    need_pending = existing_record is None
    if need_pending:
        candidate_pending = _append_jsonl(pending_text, record)
        if len(candidate_pending.encode("utf-8")) > MAX_PENDING_BYTES:
            raise TransactionError(
                f"{PENDING_PATH} excederia {MAX_PENDING_BYTES} bytes; consolidar antes de continuar"
            )
    else:
        candidate_pending = pending_text

    candidate_transcript = (
        _append_block(transcript, render_transcript_block(normalized)) if need_transcript else transcript
    )

    # Escrevemos o delta primeiro. Se o processo cair antes da transcrição, a
    # repetição da mesma entrada detecta o ID e repara apenas a transcrição.
    if need_pending:
        _atomic_write(pending_path, candidate_pending)
    if need_transcript:
        _atomic_write(transcript_path, candidate_transcript)

    return {
        "id": transaction_id,
        "sessao": session,
        "transcricao": transcript_path.relative_to(repo).as_posix(),
        "eventos": PENDING_PATH.as_posix(),
        "deltas": len(record.get("deltas", [])),
        "transcricao_escrita": need_transcript,
        "evento_escrito": need_pending,
        "reparo_parcial": need_transcript != need_pending,
        "ja_registrada": not need_transcript and not need_pending,
    }


def check_transactions(repo: Path) -> list[str]:
    errors: list[str] = []
    try:
        records = load_pending(repo)
    except TransactionError as exc:
        return [str(exc)]

    pending_path = repo / PENDING_PATH
    if pending_path.exists() and pending_path.stat().st_size > MAX_PENDING_BYTES:
        errors.append(
            f"{PENDING_PATH} excede limite operacional: {pending_path.stat().st_size} > {MAX_PENDING_BYTES}"
        )

    for record in records:
        session = record["sessao"]
        transcript_path = repo / "sessoes" / f"{session:03d}" / "transcricao.md"
        if not transcript_path.is_file():
            errors.append(f"transação {record['id']} aponta para sessão sem transcrição: {session:03d}")
            continue
        text = transcript_path.read_text(encoding="utf-8")
        count = text.count(transaction_marker(record["id"]))
        if count != 1:
            errors.append(
                f"transação {record['id']} possui {count} marcador(es) na transcrição; esperado 1"
            )
    return errors


def status(repo: Path) -> dict[str, Any]:
    records = load_pending(repo)
    return {
        "eventos_pendentes": len(records),
        "bytes_pendentes": (repo / PENDING_PATH).stat().st_size if (repo / PENDING_PATH).exists() else 0,
        "ultima_transacao": records[-1]["id"] if records else None,
        "sessao_atual": current_session(repo),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="comando", required=True)

    register = sub.add_parser("registrar", help="registra transcrição + deltas em uma única operação")
    register.add_argument("--arquivo", type=Path, help="JSON da transação; sem opção, lê stdin")

    sub.add_parser("check", help="valida schema e correspondência com marcadores da transcrição")
    sub.add_parser("status", help="mostra somente metadados do buffer transacional")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo = args.repo.resolve()
    try:
        if args.comando == "registrar":
            transaction = read_transaction(args.arquivo)
            result = register_transaction(repo, transaction)
            print(
                "OK — turno transacional registrado: "
                f"{result['id']} | deltas={result['deltas']} | "
                f"transcrição={'sim' if result['transcricao_escrita'] else 'já existia'} | "
                f"evento={'sim' if result['evento_escrito'] else 'já existia'}"
            )
            if result["reparo_parcial"]:
                print("OK — inconsistência parcial anterior foi reparada de forma idempotente.")
            return 0
        if args.comando == "check":
            errors = check_transactions(repo)
            if errors:
                print("FALHA TRANSACIONAL")
                for error in errors:
                    print(f"- {error}")
                return 1
            print("OK — buffer transacional e marcadores de transcrição estão consistentes.")
            return 0
        if args.comando == "status":
            print(json.dumps(status(repo), ensure_ascii=False, indent=2))
            return 0
        raise TransactionError(f"comando desconhecido: {args.comando}")
    except (OSError, TransactionError, yaml.YAMLError) as exc:
        print(f"FALHA DE TURNO — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
