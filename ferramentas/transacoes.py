#!/usr/bin/env python3
"""Primitivas transacionais para a narração ao vivo de Crônicas dos Reinos.

O arquivo `runtime/eventos-pendentes.jsonl` guarda uma linha por avanço narrativo
até a consolidação. Cada linha contém somente metadados, resumo, deltas e rolagens
ocultas necessárias; a prosa completa continua apenas na transcrição.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
PENDING_PATH = Path("runtime/eventos-pendentes.jsonl")
CONSOLIDATION_JOURNAL = Path("runtime/consolidacao-em-andamento.json")
TRANSCRIPT_MARKER_PREFIX = "turno-transacional:"
ALLOWED_OPS = {"set", "inc", "append", "remove", "registrar"}
ALLOWED_VISIBILITY = {"operacional", "narrador"}
TARGET_RE = re.compile(r"^[a-z][a-z0-9_]*(?::[a-z0-9_]+)?$")
MAX_SUMMARY_CHARS = 1600
MAX_DELTAS = 64
MAX_HIDDEN_ROLLS = 32


class TransactionError(ValueError):
    """Erro de schema, consistência ou aplicação de uma transação."""


def normalize(text: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(text))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = raw.lower().replace("_", " ").replace("-", " ")
    return " ".join(re.findall(r"[a-z0-9]+", raw))


def transaction_marker(transaction_id: str) -> str:
    return f"<!-- {TRANSCRIPT_MARKER_PREFIX}{transaction_id} -->"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_transaction_id(transaction: dict[str, Any], session: int) -> str:
    """Gera ID estável a partir da parte que aparece na transcrição.

    Reexecutar exatamente a mesma operação após uma interrupção produz o mesmo
    ID e permite reparar apenas o lado que faltou, sem duplicar o outro.
    """
    explicit = transaction.get("id")
    if explicit is not None:
        if not isinstance(explicit, str) or not explicit.strip():
            raise TransactionError("id da transação precisa ser string não vazia")
        return explicit.strip()

    seed = {
        "sessao": session,
        "jogador": transaction.get("jogador") or "",
        "narracao": transaction.get("narracao") or "",
        "resumo": transaction.get("resumo") or "",
    }
    digest = hashlib.sha256(_canonical_json(seed).encode("utf-8")).hexdigest()[:16]
    return f"s{session:03d}-{digest}"


def validate_delta(delta: Any) -> dict[str, Any]:
    if not isinstance(delta, dict):
        raise TransactionError("cada delta precisa ser objeto JSON")

    target = delta.get("alvo")
    if not isinstance(target, str) or not TARGET_RE.fullmatch(target):
        raise TransactionError(f"alvo de delta inválido: {target!r}")

    op = delta.get("op")
    if op not in ALLOWED_OPS:
        raise TransactionError(f"operação de delta inválida: {op!r}")

    visibility = delta.get("visibilidade", "operacional")
    if visibility not in ALLOWED_VISIBILITY:
        raise TransactionError(f"visibilidade inválida: {visibility!r}")

    path = delta.get("caminho")
    if op != "registrar":
        if not isinstance(path, str) or not path.strip():
            raise TransactionError(f"delta {op!r} exige caminho")
        if any(not part for part in path.split(".")):
            raise TransactionError(f"caminho de delta inválido: {path!r}")

    if op in {"set", "inc", "append"} and "valor" not in delta:
        raise TransactionError(f"delta {op!r} exige valor")
    if op == "inc" and not isinstance(delta.get("valor"), (int, float)):
        raise TransactionError("delta 'inc' exige valor numérico")
    if op == "registrar" and "valor" not in delta:
        raise TransactionError("delta 'registrar' exige valor")

    return delta


def validate_pending_record(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise TransactionError("registro pendente precisa ser objeto JSON")
    if record.get("versao") != SCHEMA_VERSION:
        raise TransactionError(f"versão transacional inesperada: {record.get('versao')!r}")
    transaction_id = record.get("id")
    if not isinstance(transaction_id, str) or not transaction_id.strip():
        raise TransactionError("registro pendente sem id válido")
    session = record.get("sessao")
    if not isinstance(session, int) or session < 1:
        raise TransactionError("registro pendente sem sessao inteira positiva")
    summary = record.get("resumo", "")
    if not isinstance(summary, str):
        raise TransactionError("resumo pendente precisa ser string")
    if len(summary) > MAX_SUMMARY_CHARS:
        raise TransactionError(
            f"resumo pendente excede {MAX_SUMMARY_CHARS} caracteres: {len(summary)}"
        )

    deltas = record.get("deltas", [])
    if not isinstance(deltas, list):
        raise TransactionError("deltas precisa ser lista")
    if len(deltas) > MAX_DELTAS:
        raise TransactionError(f"transação excede {MAX_DELTAS} deltas")
    for delta in deltas:
        validate_delta(delta)

    hidden = record.get("rolagens_ocultas", [])
    if not isinstance(hidden, list) or any(not isinstance(item, str) for item in hidden):
        raise TransactionError("rolagens_ocultas precisa ser lista de strings")
    if len(hidden) > MAX_HIDDEN_ROLLS:
        raise TransactionError(f"transação excede {MAX_HIDDEN_ROLLS} rolagens ocultas")

    mode = record.get("modo")
    if mode is not None and not isinstance(mode, str):
        raise TransactionError("modo precisa ser string quando presente")
    return record


def build_pending_record(transaction: dict[str, Any], session: int) -> dict[str, Any]:
    transaction_id = stable_transaction_id(transaction, session)
    summary = transaction.get("resumo") or ""
    if not isinstance(summary, str):
        raise TransactionError("resumo da transação precisa ser string")
    if not summary.strip():
        narration = str(transaction.get("narracao") or "").strip()
        summary = " ".join(narration.split())[:500]

    record: dict[str, Any] = {
        "versao": SCHEMA_VERSION,
        "id": transaction_id,
        "sessao": session,
        "resumo": summary.strip(),
        "deltas": transaction.get("deltas") or [],
    }
    for key in ("modo", "tempo_mundo", "rolagens_ocultas", "tags"):
        value = transaction.get(key)
        if value not in (None, [], ""):
            record[key] = value
    validate_pending_record(record)
    return record


def load_pending(repo: Path) -> list[dict[str, Any]]:
    if (repo / CONSOLIDATION_JOURNAL).exists():
        raise TransactionError(
            "consolidação em andamento; execute ferramentas/consolidar.py recuperar antes de ler ou registrar novos turnos"
        )
    path = repo / PENDING_PATH
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    ids: set[str] = set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TransactionError(f"JSONL inválido em {PENDING_PATH}:{number}: {exc}") from exc
        try:
            validate_pending_record(record)
        except TransactionError as exc:
            raise TransactionError(f"{PENDING_PATH}:{number}: {exc}") from exc
        transaction_id = record["id"]
        if transaction_id in ids:
            raise TransactionError(f"id transacional duplicado em {PENDING_PATH}: {transaction_id}")
        ids.add(transaction_id)
        records.append(record)
    return records


def pending_for_session(records: Iterable[dict[str, Any]], session: int | None) -> list[dict[str, Any]]:
    if session is None:
        return list(records)
    return [record for record in records if record.get("sessao") == session]


def deltas_for_target(records: Iterable[dict[str, Any]], target: str) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for record in records:
        for delta in record.get("deltas", []):
            if delta.get("alvo") == target:
                result.append(delta)
    return result


def _walk_parent(document: dict[str, Any], path: str, create: bool) -> tuple[dict[str, Any], str]:
    parts = path.split(".")
    current: dict[str, Any] = document
    for part in parts[:-1]:
        value = current.get(part)
        if value is None and create:
            value = {}
            current[part] = value
        if not isinstance(value, dict):
            raise TransactionError(f"caminho atravessa valor não mapeável: {path!r}")
        current = value
    return current, parts[-1]


def apply_delta(document: dict[str, Any], delta: dict[str, Any]) -> None:
    op = delta["op"]
    if op == "registrar":
        return
    path = str(delta["caminho"])
    parent, key = _walk_parent(document, path, create=op in {"set", "append"})

    if op == "set":
        parent[key] = copy.deepcopy(delta.get("valor"))
        return
    if op == "inc":
        if key not in parent or not isinstance(parent[key], (int, float)):
            raise TransactionError(f"não é possível incrementar caminho ausente/não numérico: {path}")
        parent[key] += delta["valor"]
        return
    if op == "append":
        if key not in parent:
            parent[key] = []
        if not isinstance(parent[key], list):
            raise TransactionError(f"não é possível anexar a valor não-lista: {path}")
        parent[key].append(copy.deepcopy(delta.get("valor")))
        return
    if op == "remove":
        if key not in parent:
            return
        if "valor" not in delta:
            parent.pop(key, None)
            return
        value = delta.get("valor")
        target = parent[key]
        if isinstance(target, list):
            parent[key] = [item for item in target if item != value]
        elif target == value:
            parent.pop(key, None)
        return
    raise TransactionError(f"operação não implementada: {op}")


def overlay_target(
    payload: dict[str, Any], records: Iterable[dict[str, Any]], target: str
) -> tuple[dict[str, Any], int]:
    result = copy.deepcopy(payload)
    applied = 0
    for delta in deltas_for_target(records, target):
        if delta.get("visibilidade", "operacional") == "narrador":
            continue
        if delta.get("op") == "registrar":
            continue
        apply_delta(result, delta)
        applied += 1
    return result, applied


def _apply_mapped(
    document: dict[str, Any],
    destination: str,
    delta: dict[str, Any],
) -> None:
    mapped = dict(delta)
    mapped["caminho"] = destination
    apply_delta(document, mapped)


def overlay_runtime(
    context: dict[str, Any],
    scene: dict[str, Any] | None,
    records: Iterable[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any] | None, int]:
    """Projeta deltas correntes sobre runtime sem reescrever os arquivos quentes."""
    context_out = copy.deepcopy(context)
    scene_out = copy.deepcopy(scene) if scene is not None else None
    session = ((context_out.get("sessao") or {}).get("numero"))
    current_records = pending_for_session(records, session if isinstance(session, int) else None)
    applied = 0

    state_map = {
        "recursos.pontos_de_vida.atuais": "recursos.pv.atuais",
        "recursos.pontos_de_vida.maximos": "recursos.pv.maximos",
        "recursos.ki.atuais": "recursos.ki.atuais",
        "recursos.ki.maximos": "recursos.ki.maximos",
        "recursos.classe_de_armadura": "recursos.ca",
        "recursos.deslocamento": "recursos.deslocamento",
        "recursos.dinheiro.po": "recursos.dinheiro_po",
        "campanha.modo_de_cena_atual": "sessao.modo_de_cena",
        "tempo.data_exata": "tempo.data",
        "tempo.hora_aproximada": "tempo.hora_aproximada",
        "tempo.periodo_do_dia": "tempo.periodo",
        "tempo.clima": "tempo.clima",
    }
    time_map = {
        "data_atual": "tempo.data",
        "hora_aproximada": "tempo.hora_aproximada",
        "periodo_do_dia": "tempo.periodo",
        "clima": "tempo.clima",
    }

    for record in current_records:
        for delta in record.get("deltas", []):
            if delta.get("visibilidade", "operacional") == "narrador":
                continue
            target = delta.get("alvo")
            path = delta.get("caminho")
            if delta.get("op") == "registrar" or not isinstance(path, str):
                continue

            destination: str | None = None
            if target == "estado":
                if path in state_map:
                    destination = state_map[path]
                elif path.startswith("localizacao."):
                    destination = path
            elif target == "tempo" and path in time_map:
                destination = time_map[path]

            if destination is not None:
                _apply_mapped(context_out, destination, delta)
                applied += 1

            if scene_out is None:
                continue
            if target == "estado":
                if path == "campanha.modo_de_cena_atual":
                    _apply_mapped(scene_out, "modo", delta)
                elif path in {"localizacao.area", "localizacao.ponto_exato"}:
                    _apply_mapped(scene_out, path, delta)
                elif path == "localizacao.descricao_operacional":
                    _apply_mapped(scene_out, "resumo_imediato", delta)
                elif path == "tempo.data_exata":
                    _apply_mapped(scene_out, "tempo.data", delta)
                elif path == "tempo.hora_aproximada":
                    _apply_mapped(scene_out, "tempo.hora_aproximada", delta)
                elif path == "tempo.prazo_relevante":
                    _apply_mapped(scene_out, "prazos_e_alertas", delta)
                elif path == "recursos.classe_de_armadura":
                    _apply_mapped(scene_out, "mecanica_imediata.ca", delta)
                elif path == "recursos.deslocamento":
                    _apply_mapped(scene_out, "mecanica_imediata.deslocamento", delta)
            elif target == "tempo":
                if path == "data_atual":
                    _apply_mapped(scene_out, "tempo.data", delta)
                elif path == "hora_aproximada":
                    _apply_mapped(scene_out, "tempo.hora_aproximada", delta)
                elif path == "prazo_relevante":
                    _apply_mapped(scene_out, "prazos_e_alertas", delta)

    if scene_out is not None:
        resources = context_out.get("recursos") or {}
        pv = resources.get("pv") or {}
        ki = resources.get("ki") or {}
        mechanics = scene_out.setdefault("mecanica_imediata", {})
        if pv.get("atuais") is not None and pv.get("maximos") is not None:
            mechanics["pv"] = f"{pv.get('atuais')}/{pv.get('maximos')}"
        if ki.get("atuais") is not None and ki.get("maximos") is not None:
            mechanics["ki"] = f"{ki.get('atuais')}/{ki.get('maximos')}"

    if current_records:
        meta = {
            "eventos_pendentes": len(current_records),
            "ultima_transacao": current_records[-1].get("id"),
        }
        context_out["sobreposicao_transacional"] = meta
        if scene_out is not None:
            scene_out["sobreposicao_transacional"] = copy.deepcopy(meta)
    return context_out, scene_out, applied


def _searchable_delta(delta: dict[str, Any], reserved: bool) -> str:
    if delta.get("visibilidade", "operacional") == "narrador" and not reserved:
        return ""
    pieces = [delta.get("alvo"), delta.get("caminho"), delta.get("valor")]
    return _canonical_json(pieces)


def search_pending(
    records: Iterable[dict[str, Any]],
    term: str,
    *,
    reserved: bool = False,
    target_prefix: str | None = None,
    limit: int = 6,
) -> list[dict[str, Any]]:
    tokens = [token for token in normalize(term).split() if token]
    if not tokens:
        return []
    matches: list[dict[str, Any]] = []
    for record in records:
        searchable = [record.get("resumo", "")]
        matched_deltas: list[dict[str, Any]] = []
        for delta in record.get("deltas", []):
            target = str(delta.get("alvo") or "")
            if target_prefix and not target.startswith(target_prefix):
                continue
            text = _searchable_delta(delta, reserved)
            if text:
                searchable.append(text)
                matched_deltas.append(delta)
        if reserved:
            searchable.extend(record.get("rolagens_ocultas", []))
        blob = normalize(" ".join(str(item) for item in searchable))
        if not all(token in blob for token in tokens):
            continue
        public_deltas = [
            delta
            for delta in matched_deltas
            if reserved or delta.get("visibilidade", "operacional") != "narrador"
        ]
        matches.append(
            {
                "transacao": record.get("id"),
                "sessao": record.get("sessao"),
                "resumo": record.get("resumo"),
                "deltas": public_deltas[:6],
            }
        )
        if len(matches) >= limit:
            break
    return matches


def record_fingerprint(record: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(record).encode("utf-8")).hexdigest()
