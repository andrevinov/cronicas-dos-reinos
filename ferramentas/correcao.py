#!/usr/bin/env python3
"""Correção canônica explícita para a ponta causal da sessão.

Uma correção não é um novo acontecimento do mundo. Ela retifica o último avanço
normal registrado, preserva o texto/histórico original para auditoria e aplica
valores corretivos pelo mesmo pipeline transacional da campanha.

Fluxo:

    python3 ferramentas/correcao.py preparar <transacao> <<'JSON'
    { ... }
    JSON

    python3 ferramentas/correcao.py aplicar <transacao> --preparacao-id corr-prep-... <<'JSON'
    { ... }
    JSON

O payload aceita:

- ``motivo``: por que a versão registrada é inválida;
- ``retificacao``: formulação curta do fato correto;
- ``resumo``: resumo operacional da correção;
- ``deltas``: somente ``set``/``remove`` idempotentes, já expressando o estado
  correto que deve prevalecer;
- ``invalidar_mapas``: mapas procedurais criados pela cena errada que devem ser
  removidos, desde que continuem totalmente ocultos e sem conteúdo planejado.

A operação só corrige a última transação normal da sessão. Se houver avanço
posterior, falha fechada: corrigir fatos antigos sem replay dos dependentes seria
reescrever causalidade por conveniência.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import yaml

import checkpoint
import consolidar
import recompensas
import rodape_turno
import transacoes
import turno

CORRECTION_PREFIX = "corr-"
PREPARATION_PREFIX = "corr-prep-"
CORRECTION_TAG_PREFIX = "correcao:"
CORRECTIONS_NAME = "correcoes.jsonl"
JOURNAL = Path("runtime/correcao-em-andamento.json")
MAX_MAP_INVALIDATIONS = 4
ALLOWED_CORRECTION_OPS = {"set", "remove"}
MARKER_RE = re.compile(r"<!--\s*turno-transacional:([^\s]+)\s*-->")


class CorrectionError(ValueError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CorrectionError(f"{label} deve ser texto não vazio")
    return " ".join(value.split())


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
        temp = Path(handle.name)
    os.replace(temp, path)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CorrectionError(f"JSON inválido em {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CorrectionError(f"{path} deve conter objeto JSON")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    result: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CorrectionError(f"JSONL inválido em {path}:{number}: {exc}") from exc
        if not isinstance(value, dict):
            raise CorrectionError(f"registro não-objeto em {path}:{number}")
        result.append(value)
    return result


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    records = _read_jsonl(path)
    record_id = record.get("id")
    matches = [item for item in records if item.get("id") == record_id]
    if matches:
        if len(matches) != 1 or matches[0] != record:
            raise CorrectionError(f"correção {record_id} já existe com conteúdo divergente")
        return
    records.append(record)
    text = "".join(_canonical_json(item) + "\n" for item in records)
    _atomic_write(path, text)


def _current_session_number(repo: Path) -> int:
    try:
        return turno.current_session_info(repo)[0]
    except transacoes.TransactionError as exc:
        raise CorrectionError(str(exc)) from exc


def _session(repo: Path) -> int:
    try:
        session, status = turno.current_session_info(repo)
    except transacoes.TransactionError as exc:
        raise CorrectionError(str(exc)) from exc
    if status != "em_sessao":
        raise CorrectionError(f"correção canônica exige sessão ativa; status atual: {status!r}")
    return session


def _session_dir(repo: Path, session: int) -> Path:
    return repo / "sessoes" / f"{session:03d}"


def _corrections_path(repo: Path, session: int) -> Path:
    return _session_dir(repo, session) / CORRECTIONS_NAME


def _transcript_path(repo: Path, session: int) -> Path:
    return _session_dir(repo, session) / "transcricao.md"


def _transcript_ids(repo: Path, session: int) -> list[str]:
    path = _transcript_path(repo, session)
    if not path.is_file():
        raise CorrectionError(f"transcrição ausente: {path.relative_to(repo)}")
    return MARKER_RE.findall(path.read_text(encoding="utf-8"))


def _ledger_batches(repo: Path, session: int) -> list[dict[str, Any]]:
    try:
        return consolidar.load_ledger(repo, session)
    except consolidar.ConsolidationError as exc:
        raise CorrectionError(str(exc)) from exc


def _target_status(repo: Path, session: int, target: str) -> dict[str, Any]:
    target = _text(target, "transação alvo")
    if target.startswith(CORRECTION_PREFIX):
        raise CorrectionError("uma correção não pode corrigir outra correção automaticamente")

    ids = _transcript_ids(repo, session)
    if ids.count(target) != 1:
        if target not in ids:
            raise CorrectionError(
                f"transação não aparece na transcrição da sessão {session:03d}: {target}"
            )
        raise CorrectionError(f"transação alvo possui marcador duplicado na transcrição: {target}")
    normal_ids = [item for item in ids if not item.startswith(CORRECTION_PREFIX)]
    if not normal_ids or normal_ids[-1] != target:
        later = normal_ids[normal_ids.index(target) + 1 :] if target in normal_ids else []
        suffix = f"; avanços posteriores: {', '.join(later[-3:])}" if later else ""
        raise CorrectionError(
            "correção automática só é permitida na ponta causal da sessão" + suffix
        )

    try:
        pending = transacoes.load_pending(repo)
    except transacoes.TransactionError as exc:
        raise CorrectionError(str(exc)) from exc
    pending_matches = [item for item in pending if item.get("id") == target]
    ledger_matches: list[dict[str, Any]] = []
    for batch in _ledger_batches(repo, session):
        if target in (batch.get("transacoes") or []):
            ledger_matches.append(batch)

    if len(pending_matches) > 1 or len(ledger_matches) > 1:
        raise CorrectionError(f"transação alvo aparece mais de uma vez: {target}")
    if pending_matches and ledger_matches:
        raise CorrectionError(f"transação {target} está simultaneamente pendente e consolidada")
    if pending_matches:
        return {"estado": "pendente", "registro": copy.deepcopy(pending_matches[0]), "batch": None}
    if ledger_matches:
        return {"estado": "consolidada", "registro": None, "batch": copy.deepcopy(ledger_matches[0])}
    raise CorrectionError(
        f"transação {target} possui marcador, mas não está no buffer nem no ledger; repare a sessão antes de corrigir"
    )


def _normalize_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise CorrectionError("payload de correção deve ser objeto JSON")
    allowed = {"motivo", "retificacao", "resumo", "deltas", "invalidar_mapas"}
    extra = sorted(set(payload) - allowed)
    if extra:
        raise CorrectionError("campos desconhecidos no payload: " + ", ".join(extra))

    result = {
        "motivo": _text(payload.get("motivo"), "motivo"),
        "retificacao": _text(payload.get("retificacao"), "retificacao"),
        "resumo": _text(payload.get("resumo"), "resumo"),
    }
    raw_deltas = payload.get("deltas") or []
    if not isinstance(raw_deltas, list):
        raise CorrectionError("deltas deve ser lista")
    deltas: list[dict[str, Any]] = []
    for raw in raw_deltas:
        try:
            delta = copy.deepcopy(transacoes.validate_delta(raw))
        except transacoes.TransactionError as exc:
            raise CorrectionError(str(exc)) from exc
        if delta.get("op") not in ALLOWED_CORRECTION_OPS:
            raise CorrectionError(
                "correção automática aceita somente deltas idempotentes set/remove; "
                f"recebido {delta.get('op')!r}"
            )
        if delta.get("visibilidade", "operacional") == "narrador":
            raise CorrectionError("correção canônica automática não altera estado reservado oculto")
        deltas.append(delta)
    result["deltas"] = deltas

    raw_maps = payload.get("invalidar_mapas") or []
    if not isinstance(raw_maps, list) or any(not isinstance(item, str) for item in raw_maps):
        raise CorrectionError("invalidar_mapas deve ser lista de IDs de local")
    if len(raw_maps) > MAX_MAP_INVALIDATIONS:
        raise CorrectionError(f"uma correção invalida no máximo {MAX_MAP_INVALIDATIONS} mapas")
    maps: list[str] = []
    for raw in raw_maps:
        try:
            local_id = recompensas.local_id(raw)
        except recompensas.RewardMapError as exc:
            raise CorrectionError(str(exc)) from exc
        if local_id not in maps:
            maps.append(local_id)
    result["invalidar_mapas"] = maps

    if not deltas and not maps:
        raise CorrectionError("correção precisa alterar ao menos um delta ou invalidar um mapa derivado")
    return result


def _payload_hash(target: str, payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        _canonical_json({"corrige": target, "payload": payload}).encode("utf-8")
    ).hexdigest()


def _correction_id(session: int, target: str, payload: dict[str, Any]) -> str:
    digest = _payload_hash(target, payload)[:16]
    return f"{CORRECTION_PREFIX}s{session:03d}-{digest}"


def _sha(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _safe_map_plan(repo: Path, local_ids: list[str]) -> list[dict[str, Any]]:
    if not local_ids:
        return []
    try:
        index = recompensas.load_index(repo)
        item_index = recompensas.load_item_index(repo)
    except recompensas.RewardMapError as exc:
        raise CorrectionError(str(exc)) from exc

    result: list[dict[str, Any]] = []
    for local_id in local_ids:
        meta = index["mapas"].get(local_id)
        if meta is None:
            result.append({"local_id": local_id, "estado": "ja_ausente"})
            continue
        try:
            data = recompensas.validate_map(repo, local_id, meta, load_fragments=True)
        except recompensas.RewardMapError as exc:
            raise CorrectionError(str(exc)) from exc
        rewards = data.get("recompensas") or []
        if any(item.get("estado") != "oculto" for item in rewards):
            raise CorrectionError(
                f"mapa {local_id} já possui recompensa descoberta/obtida; invalidação automática seria destrutiva"
            )
        if any(item.get("origem") != "procedural" for item in rewards):
            raise CorrectionError(
                f"mapa {local_id} possui recompensa planejada/autoral; correção automática não pode apagá-la"
            )
        generation = data.get("geracao") or {}
        if int(generation.get("planejadas") or 0) != 0:
            raise CorrectionError(f"mapa {local_id} contém conteúdo planejado")

        reward_entries: list[dict[str, Any]] = []
        for item in rewards:
            rid = str(item["id"])
            indexed = item_index["recompensas"].get(rid)
            if not isinstance(indexed, dict) or indexed.get("local_id") != local_id:
                raise CorrectionError(f"índice dirigido diverge para recompensa {rid}")
            reward_entries.append(
                {
                    "id": rid,
                    "arquivo": str(item["arquivo"]),
                    "sha256": _sha(repo / str(item["arquivo"])),
                }
            )
        result.append(
            {
                "local_id": local_id,
                "estado": "remover",
                "mapa": str(meta["arquivo"]),
                "mapa_sha256": _sha(repo / str(meta["arquivo"])),
                "chave_geracao": str(meta["chave_geracao"]),
                "recompensas": reward_entries,
            }
        )
    return result


def _fingerprint_sources(
    repo: Path,
    session: int,
    map_plan: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    paths = [
        _transcript_path(repo, session),
        repo / transacoes.PENDING_PATH,
        repo / "sessoes" / f"{session:03d}" / consolidar.LEDGER_NAME,
        _corrections_path(repo, session),
    ]
    if map_plan:
        paths.extend([repo / recompensas.INDEX, repo / recompensas.ITEM_INDEX])
        for item in map_plan:
            if item.get("estado") != "remover":
                continue
            paths.append(repo / str(item["mapa"]))
            paths.extend(repo / str(reward["arquivo"]) for reward in item.get("recompensas") or [])
    result = []
    for path in paths:
        try:
            rel = path.relative_to(repo).as_posix()
        except ValueError:
            rel = str(path)
        result.append({"fonte": rel, "sha256": _sha(path)})
    return result


def prepare_correction(repo: Path, target: str, payload: Any) -> dict[str, Any]:
    session = _session(repo)
    normalized = _normalize_payload(payload)
    target_info = _target_status(repo, session, target)
    map_plan = _safe_map_plan(repo, normalized["invalidar_mapas"])
    sources = _fingerprint_sources(repo, session, map_plan)
    correction_id = _correction_id(session, target, normalized)
    preparation_seed = {
        "correcao_id": correction_id,
        "alvo_estado": target_info["estado"],
        "payload_hash": _payload_hash(target, normalized),
        "fontes": sources,
        "mapas": map_plan,
    }
    preparation_id = PREPARATION_PREFIX + hashlib.sha256(
        _canonical_json(preparation_seed).encode("utf-8")
    ).hexdigest()[:20]
    return {
        "ok": True,
        "fase": "preparacao_correcao",
        "sessao": session,
        "corrige": target,
        "alvo_estado": target_info["estado"],
        "correcao_id": correction_id,
        "preparacao_id": preparation_id,
        "deltas_corretivos": len(normalized["deltas"]),
        "mapas": map_plan,
        "mutacoes_aplicadas": False,
        "regra": (
            "Correção não é acontecimento novo. Só a ponta causal pode ser retificada automaticamente; "
            "aplicar exige esta preparação ainda atual."
        ),
        "fontes": sources,
        "_payload": normalized,
    }


def _journal_payload(prepared: dict[str, Any], target: str) -> dict[str, Any]:
    return {
        "schema_correcao_em_andamento": 1,
        "natureza": "journal_recuperavel",
        "id": prepared["correcao_id"],
        "preparacao_id": prepared["preparacao_id"],
        "corrige": target,
        "sessao": prepared["sessao"],
        "alvo_estado": prepared["alvo_estado"],
        "payload_hash": _payload_hash(target, prepared["_payload"]),
        "payload": prepared["_payload"],
        "mapas": prepared["mapas"],
    }


def _write_journal(repo: Path, value: dict[str, Any]) -> None:
    _atomic_write(repo / JOURNAL, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _load_or_start_journal(
    repo: Path,
    target: str,
    preparation_id: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    existing = _read_json(repo / JOURNAL)
    if existing is not None:
        if (
            existing.get("corrige") != target
            or existing.get("payload_hash") != _payload_hash(target, payload)
            or existing.get("preparacao_id") != preparation_id
        ):
            raise CorrectionError(
                "outra correção está em andamento; repita a operação original ou remova o journal somente após auditoria"
            )
        return existing, True

    prepared = prepare_correction(repo, target, payload)
    if prepared["preparacao_id"] != preparation_id:
        raise CorrectionError("preparação de correção ficou obsoleta; execute `correcao.py preparar` novamente")
    journal = _journal_payload(prepared, target)
    _write_journal(repo, journal)
    return journal, False


@contextmanager
def _correction_registration_mode() -> Iterator[None]:
    """Autoriza apenas esta retificação a atravessar uma barreira causada pela cena errada."""
    original_authorize = turno.barreira_mundo.authorize_registration
    original_detect = turno.detect_world_checkpoint

    def authorize(_repo: Path, _transaction: dict[str, Any], *, retry: bool) -> dict[str, Any]:
        return {
            "ok": True,
            "retry": retry,
            "pendencia_resolvida": None,
            "barreira": {"modo": "correcao_canonica"},
        }

    turno.barreira_mundo.authorize_registration = authorize
    turno.detect_world_checkpoint = lambda _repo, _prior, _record: None
    try:
        yield
    finally:
        turno.barreira_mundo.authorize_registration = original_authorize
        turno.detect_world_checkpoint = original_detect


def _force_checkpoint(repo: Path) -> dict[str, Any]:
    try:
        return checkpoint.checkpoint(repo, "cena")
    except Exception as exc:
        raise CorrectionError(
            "correção foi registrada, mas o checkpoint falhou; repita `correcao.py aplicar` "
            "para retomar pelo journal"
        ) from exc


def _apply_map_invalidations(repo: Path, plan: list[dict[str, Any]]) -> list[str]:
    removals = [item for item in plan if item.get("estado") == "remover"]
    if not removals:
        return []

    try:
        index = recompensas.load_index(repo)
        item_index = recompensas.load_item_index(repo)
    except recompensas.RewardMapError as exc:
        raise CorrectionError(str(exc)) from exc

    removed: list[str] = []
    for item in removals:
        local_id = str(item["local_id"])
        current = index["mapas"].get(local_id)
        if current is not None and str(current.get("chave_geracao")) != str(item["chave_geracao"]):
            raise CorrectionError(f"mapa {local_id} mudou desde a preparação; não remover")
        index["mapas"].pop(local_id, None)
        for reward in item.get("recompensas") or []:
            rid = str(reward["id"])
            indexed = item_index["recompensas"].get(rid)
            if indexed is not None and indexed.get("local_id") != local_id:
                raise CorrectionError(f"recompensa {rid} passou a pertencer a outro local")
            item_index["recompensas"].pop(rid, None)
        removed.append(local_id)

    # Primeiro removemos referências; arquivos viram, no pior caso de crash, órfãos recuperáveis.
    recompensas.atomic(repo / recompensas.ITEM_INDEX, item_index)
    recompensas.atomic(repo / recompensas.INDEX, index)
    for item in removals:
        (repo / str(item["mapa"])).unlink(missing_ok=True)
        for reward in item.get("recompensas") or []:
            (repo / str(reward["arquivo"])).unlink(missing_ok=True)
    return removed


def _audit_record(
    journal: dict[str, Any],
    transaction_result: dict[str, Any],
    removed_maps: list[str],
) -> dict[str, Any]:
    payload = journal["payload"]
    return {
        "schema_correcao_canonica": 1,
        "natureza": "auditoria_retificacao",
        "id": journal["id"],
        "corrige": journal["corrige"],
        "transacao_corretiva": transaction_result["id"],
        "sessao": journal["sessao"],
        "alvo_estado_antes": journal["alvo_estado"],
        "motivo": payload["motivo"],
        "retificacao": payload["retificacao"],
        "resumo": payload["resumo"],
        "deltas_corretivos": len(payload["deltas"]),
        "mapas_invalidados": removed_maps,
        "nao_e_evento_novo": True,
    }


def apply_correction(
    repo: Path,
    target: str,
    preparation_id: str,
    payload: Any,
) -> dict[str, Any]:
    normalized = _normalize_payload(payload)
    session = _session(repo)
    correction_id = _correction_id(session, target, normalized)
    corrections_path = _corrections_path(repo, session)
    prior = _read_jsonl(corrections_path)
    existing = next((item for item in prior if item.get("id") == correction_id), None)
    if existing is not None:
        journal = _read_json(repo / JOURNAL)
        if journal is not None:
            if journal.get("id") != correction_id:
                raise CorrectionError(
                    "auditoria da correção existe, mas o journal pertence a outra operação; não limpar automaticamente"
                )
            (repo / JOURNAL).unlink(missing_ok=True)
        return {
            "ok": True,
            "fase": "correcao_ja_aplicada",
            "correcao_id": correction_id,
            "corrige": target,
            "ja_aplicada": True,
            "auditoria": corrections_path.relative_to(repo).as_posix(),
            "rodape": rodape_turno.build_safe(repo),
        }

    journal, resumed = _load_or_start_journal(
        repo,
        target,
        _text(preparation_id, "preparacao_id"),
        normalized,
    )
    if journal.get("id") != correction_id:
        raise CorrectionError("journal de correção não corresponde ao payload atual")

    corrective_tx = {
        "id": correction_id,
        "narracao": (
            f"CORREÇÃO CANÔNICA — {normalized['retificacao']} "
            f"Retifica {target}; não representa um novo acontecimento do mundo."
        ),
        "resumo": f"Correção canônica de {target}: {normalized['resumo']}",
        "modo": "correcao",
        "tags": [f"{CORRECTION_TAG_PREFIX}{target}", "nao-evento-mundo"],
        "deltas": normalized["deltas"],
    }

    try:
        with _correction_registration_mode():
            transaction_result = turno.register_transaction(repo, corrective_tx)
    except transacoes.TransactionError as exc:
        raise CorrectionError(str(exc)) from exc

    checkpoint_result = _force_checkpoint(repo)
    removed_maps = _apply_map_invalidations(repo, journal.get("mapas") or [])
    audit = _audit_record(journal, transaction_result, removed_maps)
    _append_jsonl(corrections_path, audit)
    (repo / JOURNAL).unlink(missing_ok=True)

    return {
        "ok": True,
        "fase": "correcao_aplicada",
        "correcao_id": correction_id,
        "corrige": target,
        "transacao_corretiva": transaction_result["id"],
        "retomada_de_journal": resumed,
        "checkpoint": checkpoint_result,
        "mapas_invalidados": removed_maps,
        "auditoria": corrections_path.relative_to(repo).as_posix(),
        "nao_e_evento_novo": True,
        "rodape": rodape_turno.build_safe(repo),
    }


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    if (repo / JOURNAL).exists():
        errors.append(
            f"correção interrompida em {JOURNAL}; repita `correcao.py aplicar` antes de avançar a campanha"
        )
    try:
        session = _current_session_number(repo)
        transcript = _transcript_path(repo, session).read_text(encoding="utf-8")
        ledger_ids = consolidar.consolidated_ids(_ledger_batches(repo, session))
        seen: set[str] = set()
        for item in _read_jsonl(_corrections_path(repo, session)):
            cid = item.get("id")
            if not isinstance(cid, str) or not cid.startswith(CORRECTION_PREFIX):
                errors.append("registro de correção sem id válido")
                continue
            if cid in seen:
                errors.append(f"correção duplicada: {cid}")
            seen.add(cid)
            if item.get("nao_e_evento_novo") is not True:
                errors.append(f"{cid}: correção perdeu marcador nao_e_evento_novo")
            if item.get("transacao_corretiva") != cid:
                errors.append(f"{cid}: auditoria aponta para transação corretiva divergente")
            if cid not in ledger_ids:
                errors.append(f"{cid}: transação corretiva não está consolidada")
            if transcript.count(transacoes.transaction_marker(cid)) != 1:
                errors.append(f"{cid}: marcador de correção ausente/duplicado na transcrição")
    except (CorrectionError, consolidar.ConsolidationError, transacoes.TransactionError, OSError) as exc:
        errors.append(str(exc))
    return {"ok": not errors, "erros": errors}


def _read_payload(path: Path | None) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8") if path is not None else sys.stdin.read()
    if not raw.strip():
        raise CorrectionError("payload JSON da correção está vazio")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CorrectionError(f"payload JSON inválido: {exc}") from exc
    if not isinstance(value, dict):
        raise CorrectionError("payload JSON precisa ser objeto")
    return value


def _public_preparation(value: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(value)
    result.pop("_payload", None)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)

    prepare = sub.add_parser("preparar", help="valida uma correção da ponta causal sem escrever")
    prepare.add_argument("transacao")
    prepare.add_argument("--arquivo", type=Path)

    apply = sub.add_parser("aplicar", help="registra, checkpointa e audita uma correção preparada")
    apply.add_argument("transacao")
    apply.add_argument("--preparacao-id", required=True)
    apply.add_argument("--arquivo", type=Path)

    sub.add_parser("check", help="valida journal e auditoria de correções da sessão atual")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "check":
            result = check(repo)
            print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
            return 0 if result["ok"] else 1
        payload = _read_payload(args.arquivo)
        if args.cmd == "preparar":
            result = _public_preparation(prepare_correction(repo, args.transacao, payload))
        else:
            result = apply_correction(repo, args.transacao, args.preparacao_id, payload)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0
    except (
        CorrectionError,
        consolidar.ConsolidationError,
        transacoes.TransactionError,
        recompensas.RewardMapError,
    ) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
