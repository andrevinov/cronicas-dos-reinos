#!/usr/bin/env python3
"""NV-18: obrigações temporais, reconciliação de estado obsoleto e no-op seguro.

A fonte ficcional continua sendo ``estado.compromissos``. Este módulo mantém
somente índice/recibos reservados, descobre obrigações vencidas de forma dirigida
e entrega a pressão ao acionamento causal de agentes leves já existente. Não há
novo scheduler, RNG ou autoria. Histórico só é aberto pela migração one-shot.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import yaml

import compromissos
import mundo

STATE_PATH = Path("estado/estado-atual.yaml")
TIME_PATH = Path("estado/tempo.yaml")
CONFIG_PATH = Path("narrador/obrigacoes-temporais/evidencias.yaml")
TRACKER_PATH = Path("narrador/obrigacoes-temporais/estado.yaml")
INDEX_PATH = Path("narrador/obrigacoes-temporais/indice.yaml")
SCHEMA = 1
MAX_ACTIVE = 32
MAX_DUE_PER_CHECKPOINT = 8


class TemporalObligationError(ValueError):
    """Contrato NV-18 inválido ou operação causal insegura."""


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise TemporalObligationError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise TemporalObligationError(f"YAML inválido em {path}: {exc}") from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TemporalObligationError(f"{label} deve ser mapa")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TemporalObligationError(f"{label} deve ser texto não vazio")
    return " ".join(value.split())


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any, size: int = 24) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()[:size]


def _file_digest(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise TemporalObligationError(f"não foi possível ler fonte causal: {path}") from exc


def _repo_path(repo: Path, raw: str) -> Path:
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        raise TemporalObligationError(f"fonte fora do repositório: {raw}")
    resolved = (repo / rel).resolve()
    if not resolved.is_relative_to(repo.resolve()):
        raise TemporalObligationError(f"fonte fora do repositório: {raw}")
    return resolved


def _normalized(value: str) -> str:
    return " ".join(value.split())


def _verify_literal(repo: Path, source: dict[str, Any], label: str) -> None:
    path = _repo_path(repo, _text(source.get("arquivo"), f"{label}.arquivo"))
    evidence = _text(source.get("evidencia_literal"), f"{label}.evidencia_literal")
    try:
        haystack = _normalized(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise TemporalObligationError(f"{label}: não foi possível ler {path}") from exc
    if _normalized(evidence) not in haystack:
        raise TemporalObligationError(
            f"{label}: evidência literal não localizada em {source['arquivo']}"
        )


def configured(repo: Path) -> bool:
    return all((repo / path).is_file() for path in (CONFIG_PATH, TRACKER_PATH, INDEX_PATH, STATE_PATH, TIME_PATH))


def load_tracker(repo: Path) -> dict[str, Any]:
    data = _map(_load_yaml(repo / TRACKER_PATH), TRACKER_PATH.as_posix())
    if data.get("schema_estado_obrigacoes_temporais") != SCHEMA:
        raise TemporalObligationError("estado NV-18 deve usar schema_estado_obrigacoes_temporais: 1")
    if data.get("natureza") != "controle_reservado":
        raise TemporalObligationError("estado NV-18 deve ter natureza: controle_reservado")
    migration = _map(data.get("migracao"), "migracao")
    if not isinstance(migration.get("executada"), bool):
        raise TemporalObligationError("migracao.executada deve ser booleana")
    for field in ("adiamentos", "despachos"):
        value = data.get(field)
        if not isinstance(value, dict):
            raise TemporalObligationError(f"{field} deve ser mapa")
    return data


def _state(repo: Path) -> dict[str, Any]:
    return _map(_load_yaml(repo / STATE_PATH), STATE_PATH.as_posix())


def temporal_records_from_state(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = state.get("compromissos") or {}
    if not isinstance(raw, dict):
        raise TemporalObligationError("estado.compromissos deve ser mapa")
    result: dict[str, dict[str, Any]] = {}
    for cid, record in raw.items():
        try:
            compromissos.commitment_path(cid)
            normalized = compromissos.validate_record(record)
        except compromissos.CommitmentError as exc:
            raise TemporalObligationError(f"compromissos.{cid}: {exc}") from exc
        if compromissos.is_temporal(normalized):
            result[cid] = normalized
    if len(result) > MAX_ACTIVE:
        raise TemporalObligationError(f"obrigações temporais ativas excedem teto de {MAX_ACTIVE}")
    return result


def current_temporal_records(repo: Path) -> dict[str, dict[str, Any]]:
    return temporal_records_from_state(_state(repo))


def build_index(records: dict[str, dict[str, Any]]) -> dict[str, Any]:
    by_date: dict[str, list[str]] = {}
    by_condition: dict[str, list[str]] = {}
    by_owner: dict[str, list[str]] = {}
    reconcile: list[str] = []
    for cid, record in sorted(records.items()):
        meta = record["obrigacao_temporal"]
        owner = meta["responsavel"]
        by_owner.setdefault(owner, []).append(cid)
        trigger = meta["prazo_ou_condicao"]
        if "instante" in trigger:
            instant = trigger["instante"]
            key = f"{instant['data']}T{instant['hora']}"
            by_date.setdefault(key, []).append(cid)
        elif "data" in trigger:
            by_date.setdefault(trigger["data"], []).append(cid)
        else:
            key = _digest(trigger["condicao"], 16)
            by_condition.setdefault(key, []).append(cid)
        if meta.get("estado") == "reconciliar":
            reconcile.append(cid)
    return {
        "schema_indice_obrigacoes_temporais": SCHEMA,
        "natureza": "indice_reservado_derivado",
        "por_data": by_date,
        "por_condicao": by_condition,
        "por_responsavel": by_owner,
        "reconciliar": reconcile,
    }


def _load_index(repo: Path) -> dict[str, Any]:
    data = _map(_load_yaml(repo / INDEX_PATH), INDEX_PATH.as_posix())
    if data.get("schema_indice_obrigacoes_temporais") != SCHEMA:
        raise TemporalObligationError("índice NV-18 deve usar schema_indice_obrigacoes_temporais: 1")
    if data.get("natureza") != "indice_reservado_derivado":
        raise TemporalObligationError("índice NV-18 deve ter natureza: indice_reservado_derivado")
    for field in ("por_data", "por_condicao", "por_responsavel"):
        if not isinstance(data.get(field), dict):
            raise TemporalObligationError(f"indice.{field} deve ser mapa")
    if not isinstance(data.get("reconciliar"), list):
        raise TemporalObligationError("indice.reconciliar deve ser lista")
    return data


def _canonical_now(repo: Path) -> mundo.WorldInstant:
    current, _ = mundo.load_canonical_time(repo)
    return current


def _trigger_due(meta: dict[str, Any], now: mundo.WorldInstant) -> bool:
    if meta.get("estado") == "reconciliar":
        return True
    trigger = meta["prazo_ou_condicao"]
    if "instante" in trigger:
        raw = trigger["instante"]
        return mundo.parse_instant(raw["data"], raw["hora"]).minute <= now.minute
    if "data" in trigger:
        # Data sem hora só vence depois que o dia canônico inteiro ficou para trás.
        return mundo.parse_instant(trigger["data"], "23:59").minute < now.minute
    return False


def _obligation_digest(record: dict[str, Any]) -> str:
    return _digest(record, 32)


def _deferral_blocks(
    repo: Path,
    cid: str,
    record: dict[str, Any],
    tracker: dict[str, Any],
    now: mundo.WorldInstant,
) -> bool:
    item = tracker["adiamentos"].get(cid)
    if not isinstance(item, dict):
        return False
    if item.get("assinatura_obrigacao") != _obligation_digest(record):
        return False
    kind = item.get("tipo")
    if kind == "instante":
        raw = item.get("em") or {}
        try:
            resume = mundo.parse_instant(str(raw.get("data")), str(raw.get("hora")))
        except mundo.WorldEngineError as exc:
            raise TemporalObligationError(f"adiamento {cid} possui instante inválido") from exc
        return now.minute < resume.minute
    if kind == "condicao":
        source = record["obrigacao_temporal"]["fonte_canonica"]["arquivo"]
        if item.get("fonte") != source:
            return False
        return item.get("assinatura_fonte") == _file_digest(_repo_path(repo, source))
    raise TemporalObligationError(f"adiamento {cid} possui tipo inválido")


def due_records(
    repo: Path,
    *,
    owner: str | None = None,
    now: mundo.WorldInstant | None = None,
) -> dict[str, dict[str, Any]]:
    records = current_temporal_records(repo)
    tracker = load_tracker(repo)
    now = now or _canonical_now(repo)
    result: dict[str, dict[str, Any]] = {}
    for cid, record in records.items():
        meta = record["obrigacao_temporal"]
        if owner is not None and meta["responsavel"] != owner:
            continue
        if not _trigger_due(meta, now):
            continue
        if _deferral_blocks(repo, cid, record, tracker, now):
            continue
        result[cid] = record
    return result


def _legacy_exact_deadline(record: dict[str, Any], now: mundo.WorldInstant) -> bool:
    window = record.get("janela") or {}
    for phase in ("inicio", "fim"):
        raw = window.get(phase)
        if isinstance(raw, dict):
            try:
                if mundo.parse_instant(raw["data"], raw["hora"]).minute <= now.minute:
                    return True
            except (KeyError, mundo.WorldEngineError):
                pass
    return False


def _cause_present(world: dict[str, Any], owner: str, key: str) -> str | None:
    control = world.get("acionamentos_leves") or {}
    waiting = (control.get("aguardando") or {}).get(owner) or {}
    if key in waiting:
        return "aguardando"
    for pending in world.get("pendencias") or []:
        if pending.get("agente_leve") == owner and key in (pending.get("acionamento_causal") or {}):
            return str(pending.get("id"))
    return None


def _dispatch_nonexact_due(
    repo: Path,
    due: dict[str, dict[str, Any]],
    now: mundo.WorldInstant,
    tracker: dict[str, Any],
) -> list[dict[str, Any]]:
    if not due:
        return []
    import acionamentos_leves
    import agentes_leves

    if not acionamentos_leves.configured(repo):
        return []
    index = agentes_leves.load_index(repo)
    active = {
        aid for aid, meta in index["agentes"].items()
        if isinstance(meta, dict) and meta.get("estado") == "ativo"
    }
    world = mundo.load_world_state(repo)
    original_world = deepcopy(world)
    projected: list[dict[str, Any]] = []
    for cid, record in list(sorted(due.items()))[:MAX_DUE_PER_CHECKPOINT]:
        owner = record["obrigacao_temporal"]["responsavel"]
        if owner not in active:
            projected.append({"id": cid, "responsavel": owner, "resultado": "sem_agente_leve_ativo"})
            continue
        has_deferral = isinstance(tracker["adiamentos"].get(cid), dict)
        if _legacy_exact_deadline(record, now) and not has_deferral:
            # Primeiro vencimento exato: `acionamentos_leves.reconcile` já cria
            # `prazo`, de prioridade máxima. Depois de um no-op adiado, o prazo
            # original já possui recibo e a retomada volta por esta fila causal.
            projected.append({"id": cid, "responsavel": owner, "resultado": "prazo_existente"})
            continue
        key = f"nv18:{cid}"
        present = _cause_present(world, owner, key)
        signature = _obligation_digest(record)
        if present is None:
            cause_signature = _digest([cid, signature], 24)
            acionamentos_leves._enqueue(
                world,
                owner,
                key,
                {
                    "tipo": "mudanca",
                    "fonte": f"{STATE_PATH.as_posix()}:compromissos.{cid}",
                    "em": mundo.instant_parts(now),
                    "assinatura": cause_signature,
                    "lote": f"nv18-{cause_signature}",
                },
            )
        acionamentos_leves.dispatch(world, index)
        present = _cause_present(world, owner, key) or "aguardando"
        previous = tracker["despachos"].get(cid)
        if not isinstance(previous, dict) or previous.get("assinatura_obrigacao") != signature or previous.get("fila") != present:
            tracker["despachos"][cid] = {
                "assinatura_obrigacao": signature,
                "em": mundo.instant_parts(now),
                "fila": present,
                "via": "acionamento_causal_existente",
            }
        projected.append({"id": cid, "responsavel": owner, "resultado": "acionamento_causal", "fila": present})
    if world != original_world:
        mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, world)
    return projected


def sync_checkpoint(repo: Path) -> dict[str, Any]:
    """Projeta somente obrigações ativas/tocadas, antes da sincronização comum."""
    if not configured(repo):
        return {"configurado": False, "alterou": False, "devidas": []}
    records = current_temporal_records(repo)
    tracker = load_tracker(repo)
    expected_index = build_index(records)
    current_index = _load_index(repo)
    changed = False
    if current_index != expected_index:
        mundo._atomic_write_yaml(repo / INDEX_PATH, expected_index)
        changed = True

    now = _canonical_now(repo)
    due = due_records(repo, now=now)
    projected = _dispatch_nonexact_due(repo, due, now, tracker)
    active_ids = set(records)
    tracker["adiamentos"] = {
        cid: value for cid, value in tracker["adiamentos"].items() if cid in active_ids
    }
    tracker["despachos"] = {
        cid: value for cid, value in tracker["despachos"].items() if cid in active_ids
    }
    before = _load_yaml(repo / TRACKER_PATH)
    if before != tracker:
        mundo._atomic_write_yaml(repo / TRACKER_PATH, tracker)
        changed = True
    return {
        "configurado": True,
        "alterou": changed,
        "devidas": sorted(due),
        "projecoes": projected,
        "fontes_lidas": [STATE_PATH.as_posix(), TIME_PATH.as_posix(), TRACKER_PATH.as_posix(), INDEX_PATH.as_posix()],
    }


def _pending_owner(repo: Path, pending_id: str) -> str | None:
    world = mundo.load_world_state(repo)
    for pending in world.get("pendencias") or []:
        if pending.get("id") == pending_id and pending.get("tipo") == "reavaliar_agente_leve":
            owner = pending.get("agente_leve")
            return str(owner) if isinstance(owner, str) and owner else None
    return None


def _prepared_for_pending(tracker: dict[str, Any], pending_id: str) -> list[str]:
    return sorted(
        cid for cid, item in tracker["adiamentos"].items()
        if isinstance(item, dict)
        and item.get("pendencia_origem") == pending_id
        and item.get("estado") == "preparado"
    )


def _followup(
    repo: Path,
    records: dict[str, dict[str, Any]],
    pending_id: str,
    now: mundo.WorldInstant,
    *,
    data: str | None,
    hora: str | None,
    condicao: str | None,
) -> dict[str, dict[str, Any]]:
    exact_requested = data is not None or hora is not None
    condition_requested = condicao is not None
    if exact_requested and condition_requested:
        raise TemporalObligationError("use nova data/hora OU nova condição, nunca ambos")
    if not exact_requested and not condition_requested:
        raise TemporalObligationError(
            "no-op de obrigação temporal vencida exige --retomar-data + --retomar-hora ou --retomar-condicao"
        )
    if exact_requested:
        if data is None or hora is None:
            raise TemporalObligationError("--retomar-data e --retomar-hora devem ser usados juntos")
        try:
            resume = mundo.parse_instant(data, hora)
        except mundo.WorldEngineError as exc:
            raise TemporalObligationError(str(exc)) from exc
        if resume.minute <= now.minute:
            raise TemporalObligationError("próxima reavaliação precisa estar no futuro")
    else:
        condicao = _text(condicao, "retomar_condicao")

    result: dict[str, dict[str, Any]] = {}
    for cid, record in records.items():
        base = {
            "estado": "preparado",
            "pendencia_origem": pending_id,
            "assinatura_obrigacao": _obligation_digest(record),
        }
        if exact_requested:
            base.update({"tipo": "instante", "em": {"data": data, "hora": hora}})
        else:
            source = record["obrigacao_temporal"]["fonte_canonica"]["arquivo"]
            base.update(
                {
                    "tipo": "condicao",
                    "condicao": condicao,
                    "fonte": source,
                    "assinatura_fonte": _file_digest(_repo_path(repo, source)),
                }
            )
        result[cid] = base
    return result


def conclude_noop(
    repo: Path,
    pending_id: str,
    note: str | None,
    *,
    retomar_data: str | None,
    retomar_hora: str | None,
    retomar_condicao: str | None,
    base_conclude: Callable[[Path, str, str | None], dict[str, Any]],
) -> dict[str, Any]:
    if not configured(repo):
        if any(value is not None for value in (retomar_data, retomar_hora, retomar_condicao)):
            raise TemporalObligationError("follow-up NV-18 usado em repositório sem NV-18 instalado")
        return base_conclude(repo, pending_id, note)

    tracker = load_tracker(repo)
    prepared = _prepared_for_pending(tracker, pending_id)
    owner = _pending_owner(repo, pending_id)
    due = due_records(repo, owner=owner) if owner else {}

    if not due and not prepared:
        if any(value is not None for value in (retomar_data, retomar_hora, retomar_condicao)):
            raise TemporalObligationError("follow-up temporal fornecido sem obrigação temporal vencida")
        return base_conclude(repo, pending_id, note)

    if due:
        followup = _followup(
            repo,
            due,
            pending_id,
            _canonical_now(repo),
            data=retomar_data,
            hora=retomar_hora,
            condicao=retomar_condicao,
        )
        tracker["adiamentos"].update(followup)
        # Escreve antes de retirar a pendência: queda intermediária mantém o
        # futuro explícito e o retry consegue terminar sem perder causalidade.
        mundo._atomic_write_yaml(repo / TRACKER_PATH, tracker)
        prepared = sorted(followup)
    elif any(value is not None for value in (retomar_data, retomar_hora, retomar_condicao)):
        raise TemporalObligationError("retry já possui follow-up temporal preparado; não o substitua")

    result = base_conclude(repo, pending_id, note)
    tracker = load_tracker(repo)
    for cid in prepared:
        item = tracker["adiamentos"].get(cid)
        if isinstance(item, dict) and item.get("pendencia_origem") == pending_id:
            item["estado"] = "ativo"
    mundo._atomic_write_yaml(repo / TRACKER_PATH, tracker)
    result = deepcopy(result)
    result["obrigacoes_temporais"] = {
        "adiadas": prepared,
        "regra": "no-op preservou próxima data/condição; obrigação não foi encerrada",
    }
    return result


def _load_config(repo: Path) -> dict[str, Any]:
    data = _map(_load_yaml(repo / CONFIG_PATH), CONFIG_PATH.as_posix())
    if data.get("schema_migracao_obrigacoes_temporais") != SCHEMA:
        raise TemporalObligationError("evidências NV-18 devem usar schema_migracao_obrigacoes_temporais: 1")
    if data.get("natureza") != "reservado":
        raise TemporalObligationError("evidências NV-18 devem ter natureza: reservado")
    if not isinstance(data.get("candidatos"), dict):
        raise TemporalObligationError("evidencias.candidatos deve ser mapa")
    return data


def migrate(repo: Path) -> dict[str, Any]:
    """Migração dirigida: só candidatos com evidência literal; nunca varre transcrições."""
    tracker = load_tracker(repo)
    if tracker["migracao"]["executada"]:
        return {"ok": True, "ja_executada": True, "convertidos": [], "fontes_lidas": [TRACKER_PATH.as_posix()]}
    config = _load_config(repo)
    state = _state(repo)
    commitments = state.setdefault("compromissos", {})
    if not isinstance(commitments, dict):
        raise TemporalObligationError("estado.compromissos deve ser mapa")
    converted: list[str] = []
    read_sources = [TRACKER_PATH.as_posix(), CONFIG_PATH.as_posix(), STATE_PATH.as_posix()]
    for cid, candidate in sorted(config["candidatos"].items()):
        candidate = _map(candidate, f"candidatos.{cid}")
        historical = _map(candidate.get("evidencia_historica"), f"candidatos.{cid}.evidencia_historica")
        _verify_literal(repo, historical, f"candidatos.{cid}.evidencia_historica")
        read_sources.append(historical["arquivo"])
        record = compromissos.validate_record(candidate.get("registro"))
        if not compromissos.is_temporal(record):
            raise TemporalObligationError(f"candidatos.{cid} não produz obrigação temporal")
        _verify_literal(repo, record["obrigacao_temporal"]["fonte_canonica"], f"candidatos.{cid}.fonte_canonica")
        read_sources.append(record["obrigacao_temporal"]["fonte_canonica"]["arquivo"])
        existing = commitments.get(cid)
        if existing is not None and compromissos.validate_record(existing) != record:
            raise TemporalObligationError(f"migração conflita com compromisso já existente: {cid}")
        commitments[cid] = record
        converted.append(cid)
    mundo._atomic_write_yaml(repo / STATE_PATH, state)
    tracker["migracao"] = {
        "executada": True,
        "politica": "somente_evidencia_literal_dirigida",
        "convertidos": converted,
    }
    mundo._atomic_write_yaml(repo / TRACKER_PATH, tracker)
    mundo._atomic_write_yaml(repo / INDEX_PATH, build_index(temporal_records_from_state(state)))
    return {"ok": True, "ja_executada": False, "convertidos": converted, "fontes_lidas": list(dict.fromkeys(read_sources))}


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        if not configured(repo):
            return {"ok": True, "configurado": False, "erros": []}
        records = current_temporal_records(repo)
        tracker = load_tracker(repo)
        index = _load_index(repo)
        expected = build_index(records)
        if index != expected:
            errors.append("índice de obrigações temporais diverge do estado canônico")
        for cid, record in records.items():
            try:
                _verify_literal(
                    repo,
                    record["obrigacao_temporal"]["fonte_canonica"],
                    f"compromissos.{cid}.fonte_canonica",
                )
            except TemporalObligationError as exc:
                errors.append(str(exc))
        active = set(records)
        for cid, item in tracker["adiamentos"].items():
            if cid not in active:
                errors.append(f"adiamento órfão para obrigação inexistente: {cid}")
                continue
            if not isinstance(item, dict) or item.get("estado") not in {"preparado", "ativo"}:
                errors.append(f"adiamento inválido: {cid}")
                continue
            if item.get("assinatura_obrigacao") != _obligation_digest(records[cid]):
                errors.append(f"adiamento obsoleto precisa ser reconciliado: {cid}")
        if tracker["migracao"].get("executada") is not True:
            errors.append("migração NV-18 ainda não foi executada")
    except (TemporalObligationError, compromissos.CommitmentError, mundo.WorldEngineError, OSError) as exc:
        errors.append(str(exc))
    return {"ok": not errors, "configurado": True, "erros": list(dict.fromkeys(errors))}


def status_view(repo: Path) -> dict[str, Any]:
    if not configured(repo):
        return {"configurado": False}
    records = current_temporal_records(repo)
    due = due_records(repo)
    tracker = load_tracker(repo)
    return {
        "configurado": True,
        "ativas": len(records),
        "devidas": sorted(due),
        "adiadas": sorted(tracker["adiamentos"]),
        "migracao_executada": tracker["migracao"]["executada"],
        "fontes_lidas": [STATE_PATH.as_posix(), TIME_PATH.as_posix(), TRACKER_PATH.as_posix(), INDEX_PATH.as_posix()],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("check")
    sub.add_parser("migrar")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.command == "status":
            result = status_view(repo)
        elif args.command == "migrar":
            result = migrate(repo)
        else:
            result = check(repo)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0 if result.get("ok", True) else 1
    except (TemporalObligationError, compromissos.CommitmentError, mundo.WorldEngineError, OSError) as exc:
        print(f"ERRO: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
