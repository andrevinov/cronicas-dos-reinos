#!/usr/bin/env python3
"""Progresso transacional de sidequests projetadas no turno.

Esta porta consome a decisão explícita transportada pela projeção de missões
aceitas. Ela valida fatos contra a própria narração, congela os bytes finais de
progresso antes do writer e instala o resultado com recovery idempotente. O
terminal continua delegado às autoridades de progresso, cânone e recompensas já
existentes.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

import _progressao_sidequests_task45_base as progress_base
import oportunidades
import progressao_sidequests
import sidequests_ativas
import turno

SCHEMA = 1
TRANSACTION_KEY = "progresso_sidequests"
JOURNAL = Path("runtime/progresso-sidequests-transacional.yaml")
RECEIPTS = Path("runtime/progresso-sidequests-receipts.jsonl")
MAX_FACTS_PER_MISSION = 4
MAX_FACTS_PER_TURN = 8
MAX_JOURNAL_BYTES = 96 * 1024
VISIBILITIES = {"publica", "narrador"}
PROHIBITED_CAPABILITY_PREFIXES = (
    "narrador/",
)


class TransactionalSidequestProgressError(ValueError):
    pass


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TransactionalSidequestProgressError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise TransactionalSidequestProgressError(f"{label} deve ser lista")
    return value


def _text(
    value: Any,
    label: str,
    *,
    minimum: int = 1,
    maximum: int = 520,
) -> str:
    if not isinstance(value, str):
        raise TransactionalSidequestProgressError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if not minimum <= len(result) <= maximum:
        raise TransactionalSidequestProgressError(
            f"{label} deve ter {minimum}..{maximum} caracteres"
        )
    return result


def _digest(value: Any) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _sha(raw: bytes | str) -> str:
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _yaml(value: Any) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _atomic_yaml(path: Path, value: dict[str, Any]) -> None:
    content = _yaml(value)
    if len(content.encode("utf-8")) > MAX_JOURNAL_BYTES:
        raise TransactionalSidequestProgressError(
            f"journal de progresso excede {MAX_JOURNAL_BYTES} bytes"
        )
    _atomic_text(path, content)


def _load_journal(repo: Path) -> dict[str, Any] | None:
    path = repo / JOURNAL
    if not path.is_file():
        return None
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise TransactionalSidequestProgressError(
            f"journal de progresso inválido: {exc}"
        ) from exc
    journal = _map(raw, "journal de progresso")
    if journal.get("schema_progresso_sidequests_transacional") != SCHEMA:
        raise TransactionalSidequestProgressError(
            "journal de progresso possui schema inesperado"
        )
    return journal


def require_no_open_journal(repo: Path) -> None:
    """Impede qualquer operação nova enquanto uma conclusão pede recovery."""
    journal = _load_journal(repo)
    if journal is None:
        return
    ticket_id = str(journal.get("ticket_id") or "desconhecido")
    raise TransactionalSidequestProgressError(
        "há progresso de sidequest interrompido no ticket "
        f"{ticket_id}; repita o cronica concluir original antes de novo turno"
    )


def _load_receipts(repo: Path) -> list[dict[str, Any]]:
    path = repo / RECEIPTS
    if not path.is_file():
        return []
    result: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TransactionalSidequestProgressError(
                f"receipt de progresso inválido na linha {number}: {exc}"
            ) from exc
        row = _map(value, f"receipt[{number}]")
        if row.get("schema") != SCHEMA or not isinstance(row.get("id"), str):
            raise TransactionalSidequestProgressError(
                f"receipt de progresso inválido na linha {number}"
            )
        result.append(row)
    if len(result) > 64:
        raise TransactionalSidequestProgressError("ledger de progresso excede 64 receipts")
    return result


def _write_receipt(repo: Path, journal: dict[str, Any], result: dict[str, Any]) -> None:
    receipts = _load_receipts(repo)
    receipt = {
        "schema": SCHEMA,
        "id": journal["id"],
        "ticket_id": journal["ticket_id"],
        "transaction_digest": journal["transaction_digest"],
        "resultado": copy.deepcopy(result),
    }
    existing = next((row for row in receipts if row["id"] == receipt["id"]), None)
    if existing is not None:
        if existing != receipt:
            raise TransactionalSidequestProgressError(
                "receipt de progresso existente possui conteúdo divergente"
            )
        return
    receipts.append(receipt)
    receipts = receipts[-64:]
    content = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in receipts
    )
    _atomic_text(repo / RECEIPTS, content)


def writer_transaction(transaction: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(transaction)
    result.pop(TRANSACTION_KEY, None)
    return result


def _decision_rows(
    transaction: dict[str, Any], mission_ids: list[str]
) -> dict[str, dict[str, Any]]:
    raw = transaction.get(TRANSACTION_KEY)
    if raw is None:
        raise TransactionalSidequestProgressError(
            "missão ativa exige progresso_sidequests com uma decisão por missão"
        )
    rows = _list(raw, TRANSACTION_KEY)
    if len(rows) != len(mission_ids):
        raise TransactionalSidequestProgressError(
            "progresso_sidequests deve decidir exatamente todas as missões projetadas"
        )
    result: dict[str, dict[str, Any]] = {}
    for position, row_raw in enumerate(rows):
        row = _map(row_raw, f"{TRANSACTION_KEY}[{position}]")
        mid = _text(row.get("mission_id"), "mission_id", maximum=128)
        if mid in result:
            raise TransactionalSidequestProgressError(
                f"missão duplicada em progresso_sidequests: {mid}"
            )
        has_none = row.get("sem_fato_sidequest") is True
        has_facts = "fatos_sidequest" in row
        expected = {"mission_id", "sem_fato_sidequest"} if has_none else {
            "mission_id",
            "fatos_sidequest",
        }
        if has_none == has_facts or set(row) != expected:
            raise TransactionalSidequestProgressError(
                f"{mid}: escolha exatamente sem_fato_sidequest=true ou fatos_sidequest"
            )
        if has_facts:
            facts = _list(row["fatos_sidequest"], f"{mid}.fatos_sidequest")
            if not 1 <= len(facts) <= MAX_FACTS_PER_MISSION:
                raise TransactionalSidequestProgressError(
                    f"{mid}: fatos_sidequest exige 1..{MAX_FACTS_PER_MISSION} fatos"
                )
        result[mid] = copy.deepcopy(row)
    if set(result) != set(mission_ids):
        missing = sorted(set(mission_ids) - set(result))
        extra = sorted(set(result) - set(mission_ids))
        raise TransactionalSidequestProgressError(
            f"decisões de missão divergentes; ausentes={missing}; extras={extra}"
        )
    if sum(len(row.get("fatos_sidequest") or []) for row in result.values()) > MAX_FACTS_PER_TURN:
        raise TransactionalSidequestProgressError(
            f"turno excede {MAX_FACTS_PER_TURN} fatos de sidequest"
        )
    return result


def _validate_ticket_fresh(repo: Path, ticket_meta: dict[str, Any]) -> None:
    projection = sidequests_ativas.project(repo)
    current = sidequests_ativas._ticket_rows(projection)
    expected = copy.deepcopy(ticket_meta["missoes"])
    if current != expected:
        raise TransactionalSidequestProgressError(
            "projeção de sidequest ficou obsoleta; execute cronica preparar novamente"
        )


def _literal_from_transaction(transaction: dict[str, Any], raw: Any, label: str) -> str:
    evidence = _text(raw, label, minimum=8, maximum=360)
    narration = str(transaction.get("narracao") or "")
    summary = str(transaction.get("resumo") or "")
    if evidence not in narration and evidence not in summary:
        raise TransactionalSidequestProgressError(
            f"{label} não aparece literalmente em narracao ou resumo"
        )
    return evidence


def _canonical_proof(repo: Path, source_raw: Any, evidence_raw: Any, label: str) -> dict[str, str]:
    source = _text(source_raw, f"{label}.fonte", maximum=240)
    rel = Path(source)
    if (
        rel.is_absolute()
        or ".." in rel.parts
        or any(source.startswith(prefix) for prefix in PROHIBITED_CAPABILITY_PREFIXES)
    ):
        raise TransactionalSidequestProgressError(
            f"{label}: planejamento reservado não prova capacidade"
        )
    path = repo / rel
    if not path.is_file():
        raise TransactionalSidequestProgressError(
            f"{label}: fonte canônica inexistente: {source}"
        )
    evidence = _text(evidence_raw, f"{label}.evidencia", minimum=8, maximum=360)
    if evidence not in path.read_text(encoding="utf-8"):
        raise TransactionalSidequestProgressError(
            f"{label}: evidência literal não encontrada em {source}"
        )
    return {"fonte": source, "evidencia": evidence}


def _canonical_actor_source(repo: Path, actor_id: str) -> str:
    index_path = repo / progress_base.NPC_INDEX
    if not index_path.is_file():
        raise TransactionalSidequestProgressError(
            f"ator substituto não possui presença canônica: {actor_id}"
        )
    try:
        index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise TransactionalSidequestProgressError(str(exc)) from exc
    meta = (_map(index, "índice de NPCs").get("npcs") or {}).get(actor_id)
    if not isinstance(meta, dict) or not isinstance(meta.get("arquivo"), str):
        raise TransactionalSidequestProgressError(
            f"ator substituto não possui presença canônica: {actor_id}"
        )
    source = meta["arquivo"]
    if not (repo / source).is_file():
        raise TransactionalSidequestProgressError(
            f"fragmento do ator substituto não existe: {actor_id}"
        )
    return source


def _dependencies(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row["fase_id"]): row
        for row in doc["contrato"].get("dependencias_fases") or []
        if isinstance(row, dict)
    }


def _normalize_substitutions(
    repo: Path,
    transaction: dict[str, Any],
    raw: Any,
    *,
    fact_id: str,
    phases: dict[str, str],
    actors: list[str],
    doc: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = _list(raw, f"{fact_id}.substituicoes")
    dependencies = _dependencies(doc)
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    expected_keys = {
        "fase_id",
        "ator_original",
        "ator_efetivo",
        "capacidade",
        "fonte_capacidade",
        "evidencia_capacidade",
        "evidencia_atuacao",
    }
    for position, row_raw in enumerate(rows):
        row = _map(row_raw, f"{fact_id}.substituicoes[{position}]")
        if set(row) != expected_keys:
            raise TransactionalSidequestProgressError(
                "substituição exige fase, atores, capacidade e duas evidências"
            )
        phase_id = progress_base._slug(row["fase_id"], "substituicao.fase_id")
        if phase_id in seen:
            raise TransactionalSidequestProgressError(
                f"substituição duplicada para a fase {phase_id}"
            )
        seen.add(phase_id)
        dependency = dependencies.get(phase_id)
        if dependency is None or phases.get(phase_id) != "resolvida":
            raise TransactionalSidequestProgressError(
                f"substituição só pode acompanhar fase resolvida: {phase_id}"
            )
        if dependency.get("substituicao_permitida") is not True:
            raise TransactionalSidequestProgressError(
                f"fase não permite substituição: {phase_id}"
            )
        original = progress_base._id(row["ator_original"], "substituicao.ator_original")
        effective = progress_base._id(row["ator_efetivo"], "substituicao.ator_efetivo")
        if original not in dependency.get("atores_necessarios", []) or effective == original:
            raise TransactionalSidequestProgressError(
                f"substituição não corresponde ao ator original de {phase_id}"
            )
        if effective not in actors:
            raise TransactionalSidequestProgressError(
                f"ator efetivo deve constar em atores do fato: {effective}"
            )
        actor_source = _canonical_actor_source(repo, effective)
        capability = _text(row["capacidade"], "substituicao.capacidade", maximum=160)
        capability_proof = _canonical_proof(
            repo,
            row["fonte_capacidade"],
            row["evidencia_capacidade"],
            f"substituicao.{phase_id}.capacidade",
        )
        acting_evidence = _literal_from_transaction(
            transaction,
            row["evidencia_atuacao"],
            f"substituicao.{phase_id}.evidencia_atuacao",
        )
        normalized.append(
            {
                "fase_id": phase_id,
                "ator_original": original,
                "ator_efetivo": effective,
                "capacidade": capability,
                "prova_capacidade": capability_proof,
                "fonte_ator": actor_source,
                "evidencia_atuacao": acting_evidence,
            }
        )
    return normalized


def _validate_actors_for_resolved_phases(
    doc: dict[str, Any],
    phases: dict[str, str],
    actors: list[str],
    substitutions: list[dict[str, Any]],
) -> None:
    substitution_by_phase = {row["fase_id"]: row for row in substitutions}
    actor_state = doc["estado"]["atores"]
    for phase_id, target in phases.items():
        if target != "resolvida":
            continue
        dependency = _dependencies(doc).get(phase_id)
        if dependency is None or not dependency.get("atores_necessarios"):
            continue
        required = list(dependency["atores_necessarios"])
        available_required = [
            actor
            for actor in required
            if actor in actors
            and actor_state.get(actor, {}).get("estado") != "indisponivel"
        ]
        if available_required:
            if phase_id in substitution_by_phase:
                raise TransactionalSidequestProgressError(
                    f"{phase_id}: substituição declarada apesar do ator original efetivo"
                )
            continue
        if phase_id not in substitution_by_phase:
            raise TransactionalSidequestProgressError(
                f"{phase_id}: resolução exige ator necessário ou substituição validada"
            )


def _transition_map(
    raw: Any,
    label: str,
    current: dict[str, Any],
    allowed: set[str],
) -> tuple[dict[str, str], bool]:
    values = _map(raw, label)
    result: dict[str, str] = {}
    changed = False
    for raw_id, raw_target in values.items():
        item_id = progress_base._slug(raw_id, f"{label}.id")
        target = _text(raw_target, f"{label}.{item_id}", maximum=40)
        if item_id not in current or target not in allowed:
            raise TransactionalSidequestProgressError(
                f"transição desconhecida: {label}.{item_id} -> {target}"
            )
        before = current[item_id].get("estado")
        if before in {"resolvida", "satisfeita", "inviavel"} and before != target:
            raise TransactionalSidequestProgressError(
                f"transição terminal não pode ser revertida: {item_id} ({before} -> {target})"
            )
        result[item_id] = target
        changed = changed or before != target
    return result, changed


def _normalize_fact(
    repo: Path,
    transaction: dict[str, Any],
    raw: Any,
    *,
    doc: dict[str, Any],
    transaction_id: str,
    session: int,
) -> dict[str, Any]:
    fact = _map(raw, "fato_sidequest")
    expected = {
        "id",
        "descricao",
        "evidencia",
        "fases",
        "condicoes_sucesso",
        "condicoes_falha",
        "atores",
        "substituicoes",
        "visibilidade",
    }
    if set(fact) != expected:
        raise TransactionalSidequestProgressError(
            f"fato_sidequest possui campos inesperados: {sorted(set(fact) ^ expected)}"
        )
    fact_id = progress_base._slug(fact["id"], "fato.id")
    description = _text(fact["descricao"], "fato.descricao", maximum=520)
    evidence = _literal_from_transaction(transaction, fact["evidencia"], "fato.evidencia")
    phases, phase_changed = _transition_map(
        fact["fases"],
        "fato.fases",
        doc["estado"]["fases"],
        progress_base.PHASE_STATES,
    )
    success, success_changed = _transition_map(
        fact["condicoes_sucesso"],
        "fato.condicoes_sucesso",
        doc["estado"]["condicoes_sucesso"],
        progress_base.CONDITION_STATES,
    )
    failure, failure_changed = _transition_map(
        fact["condicoes_falha"],
        "fato.condicoes_falha",
        doc["estado"]["condicoes_falha"],
        progress_base.CONDITION_STATES,
    )
    if not (phase_changed or success_changed or failure_changed):
        raise TransactionalSidequestProgressError(
            f"{fact_id}: fato deve alterar ao menos uma fase ou condição"
        )
    actors = [
        progress_base._id(value, "fato.atores")
        for value in _list(fact["atores"], "fato.atores")
    ]
    if len(actors) != len(set(actors)):
        raise TransactionalSidequestProgressError(f"{fact_id}: atores duplicados")
    visibility = _text(fact["visibilidade"], "fato.visibilidade", maximum=24)
    if visibility not in VISIBILITIES:
        raise TransactionalSidequestProgressError("fato.visibilidade inválida")
    substitutions = _normalize_substitutions(
        repo,
        transaction,
        fact["substituicoes"],
        fact_id=fact_id,
        phases=phases,
        actors=actors,
        doc=doc,
    )
    _validate_actors_for_resolved_phases(doc, phases, actors, substitutions)
    transcript = f"sessoes/{session:03d}/transcricao.md"
    return {
        "id": fact_id,
        "descricao": description,
        "prova": {"fonte": transcript, "evidencia": evidence},
        "fases": phases,
        "condicoes_sucesso": success,
        "condicoes_falha": failure,
        "atores": actors,
        "substituicoes": substitutions,
        "visibilidade": visibility,
        "fonte_transacional": {
            "tipo": "cronica_concluir",
            "transacao_id": transaction_id,
            "sessao": session,
        },
    }


def _apply_fact(doc: dict[str, Any], fact: dict[str, Any]) -> None:
    fact_id = fact["id"]
    existing = doc["estado"]["fatos"].get(fact_id)
    if existing is not None:
        if existing != fact:
            raise TransactionalSidequestProgressError(
                f"fato {fact_id} já existe com conteúdo divergente"
            )
        return
    if len(doc["estado"]["fatos"]) >= progress_base.MAX_FACTS:
        raise TransactionalSidequestProgressError("orçamento de fatos Task45 esgotado")
    doc["estado"]["fatos"][fact_id] = copy.deepcopy(fact)
    for phase_id, target in fact["fases"].items():
        doc["estado"]["fases"][phase_id] = {
            "estado": target,
            "fato_id": fact_id,
            "motivo_automatico": None,
        }
    for group in ("condicoes_sucesso", "condicoes_falha"):
        for condition_id, target in fact[group].items():
            doc["estado"][group][condition_id]["estado"] = target
            doc["estado"][group][condition_id]["fato_id"] = fact_id
    progress_base._history(
        doc,
        {
            "tipo": "fato_registrado_transacional",
            "id": fact_id,
            "fonte": fact["prova"]["fonte"],
            "transacao_id": fact["fonte_transacional"]["transacao_id"],
            "atores": copy.deepcopy(fact["atores"]),
            "substituicoes": copy.deepcopy(fact["substituicoes"]),
        },
    )


def _load_mission_progress(repo: Path, mission_id: str) -> tuple[dict[str, Any], dict[str, Any], Path]:
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise TransactionalSidequestProgressError(str(exc)) from exc
    mission = state.get("missoes", {}).get(mission_id)
    if not isinstance(mission, dict) or mission.get("estado") != "aceita":
        raise TransactionalSidequestProgressError(
            f"missão não está aceita: {mission_id}"
        )
    if mission.get("origem") != "sidequest_emergente":
        raise TransactionalSidequestProgressError(
            f"missão aceita legada não possui progresso transacional: {mission_id}"
        )
    try:
        doc, rel = progress_base._load_progress(repo, mission, mission_id)
    except progress_base.SidequestProgressionError as exc:
        raise TransactionalSidequestProgressError(str(exc)) from exc
    return mission, doc, rel


def _plan_target(
    repo: Path,
    mission_id: str,
    facts_raw: list[Any],
    transaction: dict[str, Any],
    *,
    transaction_id: str,
    session: int,
) -> dict[str, Any]:
    _mission, doc, rel = _load_mission_progress(repo, mission_id)
    try:
        progress_base._sync_actor_availability(repo, doc)
    except progress_base.SidequestProgressionError as exc:
        raise TransactionalSidequestProgressError(str(exc)) from exc
    before = (repo / rel).read_bytes()
    fact_ids: list[str] = []
    for raw in facts_raw:
        fact = _normalize_fact(
            repo,
            transaction,
            raw,
            doc=doc,
            transaction_id=transaction_id,
            session=session,
        )
        _apply_fact(doc, fact)
        fact_ids.append(fact["id"])
    evaluation = progress_base._evaluation(doc)
    if evaluation["ambiguo"]:
        raise TransactionalSidequestProgressError(
            "fatos tornam sucesso e falha simultaneamente verdadeiros"
        )
    content = _yaml(doc)
    if len(content.encode("utf-8")) > progress_base.MAX_FRAGMENT_BYTES:
        raise TransactionalSidequestProgressError(
            f"fragmento de progresso excede {progress_base.MAX_FRAGMENT_BYTES} bytes"
        )
    terminal = (
        "sucesso"
        if evaluation["sucesso_pronto"]
        else "falha"
        if evaluation["falha_pronta"]
        else None
    )
    return {
        "mission_id": mission_id,
        "path": rel.as_posix(),
        "before_sha256": _sha(before),
        "final_sha256": _sha(content),
        "content": content,
        "fato_ids": fact_ids,
        "terminal": terminal,
    }


def _journal_id(ticket_id: str, transaction: dict[str, Any]) -> str:
    return "sqp-" + _digest(
        {"ticket_id": ticket_id, "transacao": transaction}
    )[:24]


def prepare_conclusion(
    repo: Path,
    *,
    ticket_id: str,
    ticket_meta: dict[str, Any],
    transaction: dict[str, Any],
) -> dict[str, Any]:
    journal_id = _journal_id(ticket_id, transaction)
    existing = _load_journal(repo)
    if existing is not None:
        if (
            existing.get("id") != journal_id
            or existing.get("ticket_id") != ticket_id
            or existing.get("transaction_digest") != _digest(transaction)
        ):
            raise TransactionalSidequestProgressError(
                "há outra conclusão de progresso interrompida; repita a transação original"
        )
        return existing

    receipt = next(
        (row for row in _load_receipts(repo) if row.get("id") == journal_id),
        None,
    )
    if receipt is not None:
        if (
            receipt.get("ticket_id") != ticket_id
            or receipt.get("transaction_digest") != _digest(transaction)
        ):
            raise TransactionalSidequestProgressError(
                "receipt de progresso diverge do retry solicitado"
            )
        return {
            "schema_progresso_sidequests_transacional": SCHEMA,
            "id": journal_id,
            "ticket_id": ticket_id,
            "transaction_digest": _digest(transaction),
            "fase": "ja_instalada",
            "receipt_result": copy.deepcopy(receipt["resultado"]),
        }

    mission_ids = [str(row["mission_id"]) for row in ticket_meta["missoes"]]
    decisions = _decision_rows(transaction, mission_ids)
    _validate_ticket_fresh(repo, ticket_meta)
    writer_tx = writer_transaction(transaction)
    try:
        normalized, session = turno.normalize_transaction(repo, writer_tx)
    except turno.TransactionError as exc:
        raise TransactionalSidequestProgressError(str(exc)) from exc
    transaction_id = str(normalized["id"])
    targets = [
        _plan_target(
            repo,
            mission_id,
            list(decisions[mission_id].get("fatos_sidequest") or []),
            transaction,
            transaction_id=transaction_id,
            session=session,
        )
        for mission_id in mission_ids
        if decisions[mission_id].get("fatos_sidequest")
    ]
    plan = {
        "schema_progresso_sidequests_transacional": SCHEMA,
        "id": journal_id,
        "ticket_id": ticket_id,
        "transaction_digest": _digest(transaction),
        "writer_transaction_digest": _digest(writer_tx),
        "transaction_id": transaction_id,
        "session": session,
        "narration_digest": _sha(str(transaction.get("narracao") or "")),
        "summary_digest": _sha(str(transaction.get("resumo") or "")),
        "missions_decided": len(mission_ids),
        "fase": "validada_aguardando_turno" if targets else "sem_mutacao",
        "targets": targets,
        "progress_installed": [],
        "terminals_installed": [],
    }
    if targets:
        _atomic_yaml(repo / JOURNAL, plan)
    return plan


def _save(repo: Path, journal: dict[str, Any]) -> None:
    _atomic_yaml(repo / JOURNAL, journal)


def install(repo: Path, journal: dict[str, Any], *, transaction: dict[str, Any]) -> dict[str, Any]:
    if journal.get("fase") == "ja_instalada":
        return copy.deepcopy(_map(journal.get("receipt_result"), "receipt.resultado"))
    if journal.get("fase") == "sem_mutacao":
        result = {
            "ok": True,
            "resultado": "sem_fatos_sidequest",
            "missoes_reavaliadas": int(journal.get("missions_decided") or 0),
            "fatos_registrados": 0,
            "terminais": [],
        }
        _write_receipt(repo, journal, result)
        return result
    if journal.get("transaction_digest") != _digest(transaction):
        raise TransactionalSidequestProgressError(
            "transação diverge do journal de progresso"
        )
    journal = copy.deepcopy(journal)
    progress_installed = set(journal.get("progress_installed") or [])
    for target in journal["targets"]:
        mission_id = str(target["mission_id"])
        if mission_id in progress_installed:
            continue
        path = repo / Path(str(target["path"]))
        current = path.read_bytes() if path.is_file() else b""
        current_sha = _sha(current)
        if current_sha == target["final_sha256"]:
            pass
        elif current_sha == target["before_sha256"]:
            _atomic_text(path, str(target["content"]))
        else:
            raise TransactionalSidequestProgressError(
                f"progresso mudou concorrentemente durante instalação: {mission_id}"
            )
        progress_installed.add(mission_id)
        journal["progress_installed"] = sorted(progress_installed)
        journal["fase"] = "instalando_terminais"
        _save(repo, journal)

    terminals_installed = set(journal.get("terminals_installed") or [])
    terminal_results: list[dict[str, Any]] = []
    for target in journal["targets"]:
        mission_id = str(target["mission_id"])
        outcome = target.get("terminal")
        if outcome is None:
            continue
        if mission_id not in terminals_installed:
            try:
                if outcome == "sucesso":
                    result = progressao_sidequests.finalize_success(
                        repo,
                        mission_id,
                        optional_ids=[],
                        evidences={},
                        narration=str(transaction.get("narracao") or ""),
                    )
                else:
                    result = progressao_sidequests.finalize_failure(repo, mission_id)
            except progress_base.SidequestProgressionError as exc:
                raise TransactionalSidequestProgressError(str(exc)) from exc
            terminals_installed.add(mission_id)
            journal["terminals_installed"] = sorted(terminals_installed)
            journal["fase"] = "terminais_instalados"
            _save(repo, journal)
        else:
            result = {"resultado": "ja_instalado"}
        terminal_results.append(
            {"mission_id": mission_id, "terminal": outcome, "resultado": result.get("resultado")}
        )

    result = {
        "ok": True,
        "resultado": "progresso_sidequests_registrado",
        "missoes_reavaliadas": len(journal["targets"]),
        "fatos_registrados": sum(len(target["fato_ids"]) for target in journal["targets"]),
        "fato_ids": {
            target["mission_id"]: list(target["fato_ids"])
            for target in journal["targets"]
        },
        "terminais": terminal_results,
        "transacao_id": journal["transaction_id"],
        "idempotente": True,
    }
    _write_receipt(repo, journal, result)
    (repo / JOURNAL).unlink(missing_ok=True)
    return result


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        journal = _load_journal(repo)
        _load_receipts(repo)
        if journal is not None:
            for target in _list(journal.get("targets"), "journal.targets"):
                _map(target, "journal.target")
            errors.append(
                "há journal de progresso interrompido; repita o cronica concluir original"
            )
    except (TransactionalSidequestProgressError, OSError, yaml.YAMLError) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "erros": errors,
        "journal_aberto": (repo / JOURNAL).is_file(),
        "contrato": {
            "max_missoes": sidequests_ativas.MAX_ACTIVE,
            "max_fatos_por_missao": MAX_FACTS_PER_MISSION,
            "max_fatos_por_turno": MAX_FACTS_PER_TURN,
            "parse_semantico_automatico": False,
            "writer_de_turno": 1,
            "scheduler_novo": 0,
            "rng_novo": 0,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("cmd", choices=["check"])
    args = parser.parse_args(argv)
    result = check(args.repo.resolve())
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
