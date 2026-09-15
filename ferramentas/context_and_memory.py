#!/usr/bin/env python3
"""Fachada pública v2 de contexto e memória.

A escada de acesso, a memória de cena, a retomada e a memória durável mantêm
seus motores e fontes atuais. Esta porta publica uma única identidade modular,
sem cache persistente, scan global, writer ou chamada de orquestração adicional.
"""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any, Callable

import yaml

from _module_facade import attach_coverage, combine_checks
import memoria_cena as _scene_engine
import memoria_duravel as _durable_engine
import npc_continuity_and_social_behavior as _npc_memory
import politica_acesso as _access

FACADE_SCHEMA = 2
MODULE_ID = "context_and_memory"
CAPABILITIES = (
    "routed_context_access",
    "scene_and_durable_memory",
    "knowledge_layer_separation",
)
LEGACY_ALIASES: tuple[str, ...] = ()
LEGACY_COMPONENTS = (
    "contexto",
    "politica_acesso",
    "memoria_cena",
    "memoria_duravel",
    "retomada_cronica",
)

ACCESS_OBSERVATION_KEY = "contexto_modular"
MEMORY_PERSISTENCE_KEY = "memoria_contexto"

# A fachada aponta para os donos atuais; nenhum conteúdo é copiado para outro
# arquivo e os caches derivados continuam reconstruíveis.
SOURCE_OWNERSHIP = {
    "runtime_context": "runtime/contexto.yaml",
    "runtime_scene": "runtime/cena.yaml",
    "pending_overlay": "runtime/eventos-pendentes.jsonl",
    "session_memory": "sessoes/<NNN>/handoff.yaml",
    "scene_cast": "estado/estado-atual.yaml:estado_narrativo.elenco_cena",
    "npc_memory": "estado/npcs/index.yaml + fragmento dirigido",
    "relationship_memory": "estado/relacoes/index.yaml + fragmento dirigido",
    "ren_knowledge": "personagens/jogador/conhecimento/index.yaml + fragmento dirigido",
}

# Política de acesso: compatibilidade para que ``contexto.py`` e o buscador em
# lote dependam desta fachada sem reimplementar L0–L5.
LEVEL_ORDER = _access.LEVEL_ORDER
LEVEL_BUDGETS = _access.LEVEL_BUDGETS
NEXT_LEVEL = _access.NEXT_LEVEL
STOP_CONDITION = _access.STOP_CONDITION
AccessDecision = _access.AccessDecision
AccessPolicyError = _access.AccessPolicyError
classify = _access.classify
validate_escalation = _access.validate_escalation
effective_budget = _access.effective_budget

# Memória de cena/durável: nomes persistidos e erros permanecem idênticos.
VERSION = _scene_engine.VERSION
KEY = _scene_engine.KEY
TICKET_KEY = _scene_engine.TICKET_KEY
CAST_PATH = _scene_engine.CAST_PATH
TRANSACTION_KEY = _durable_engine.TRANSACTION_KEY
MAX_MEMORY_BYTES = _scene_engine.MAX_MEMORY_BYTES
MAX_RECEIPT_BYTES = _scene_engine.MAX_RECEIPT_BYTES
MAX_FACTS = _durable_engine.MAX_FACTS
MAX_BLOCK_BYTES = _durable_engine.MAX_BLOCK_BYTES
SceneMemoryError = _scene_engine.SceneMemoryError
DurableMemoryError = _durable_engine.DurableMemoryError


def _sources(data: dict[str, Any]) -> list[str]:
    raw = data.get("fontes")
    if not isinstance(raw, list):
        raw = data.get("fontes_lidas")
    return list(dict.fromkeys(str(item) for item in (raw or []) if item))


def _has_gap(data: dict[str, Any]) -> bool:
    result = data.get("resultado")
    if isinstance(result, dict):
        if result.get("encontrado") is False or result.get("aprofundamento_necessario") is True:
            return True
        memory = result.get(KEY)
        if isinstance(memory, dict) and memory.get("aprofundamento_necessario") is True:
            return True
    memory = data.get(KEY)
    return isinstance(memory, dict) and memory.get("aprofundamento_necessario") is True


def access_observation(
    data: dict[str, Any],
    decision: AccessDecision,
    *,
    reason: str | None,
    budget: int,
) -> dict[str, Any]:
    """Resume a decisão de acesso sem afirmar suficiência sem evidência."""

    sources = _sources(data)
    gap = _has_gap(data)
    escalated = _access.LEVEL_ORDER[decision.level] >= _access.LEVEL_ORDER["L3"]
    if gap:
        outcome = "lacuna_preservada"
    elif escalated:
        outcome = "aprofundamento_justificado"
    else:
        outcome = "contexto_suficiente"
    transcript_sources = [source for source in sources if "transcricao" in source.casefold()]
    return {
        "schema_context_and_memory": FACADE_SCHEMA,
        "module_id": MODULE_ID,
        "evento_modular": "consulta",
        "resultado_modular": outcome,
        "efeito_materializado": False,
        "nivel_acesso": decision.level,
        "fontes_consultadas": len(sources),
        "lacuna_preservada": gap,
        "escalada_justificada": bool(reason) if escalated else None,
        "transcricao_lida": bool(transcript_sources),
        "teto_bytes": budget,
        "scan_global_novo": False,
    }


def decorate(
    data: dict[str, Any],
    decision: AccessDecision,
    *,
    requested_budget: int,
    after: str | None,
    reason: str | None,
) -> tuple[dict[str, Any], int]:
    """Aplica o orçamento existente e publica o recibo do acesso dirigido."""

    out, budget = _access.decorate(
        data,
        decision,
        requested_budget=requested_budget,
        after=after,
        reason=reason,
    )
    out[ACCESS_OBSERVATION_KEY] = access_observation(
        out,
        decision,
        reason=reason,
        budget=budget,
    )
    attach_coverage(
        out,
        module_id=MODULE_ID,
        phase="consulta",
        applicability="aplicavel",
    )
    return out, budget


def attach(
    repo: Path,
    prepared: dict[str, Any],
    *,
    decode_ticket: Callable[[str], dict[str, Any]],
    encode_ticket: Callable[[dict[str, Any]], tuple[str, str]],
    participants: list[str] | None = None,
    base_in_context: Any = None,
    prospective_participants: list[str] | None = None,
    max_output_bytes: int = 8192,
) -> dict[str, Any]:
    """Entrega memória de cena no preparo existente, sem terceira chamada."""

    result = _npc_memory.attach(
        repo,
        prepared,
        decode_ticket=decode_ticket,
        encode_ticket=encode_ticket,
        participants=participants,
        base_in_context=base_in_context,
        prospective_participants=prospective_participants,
        max_output_bytes=max_output_bytes,
    )
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="preparar",
        applicability="aplicavel",
    )


def resume(
    repo: Path,
    result: dict[str, Any],
    *,
    max_output_bytes: int = 8192,
    records: list[dict[str, Any]] | None = None,
    measure: Callable[[Any], int] = _scene_engine.size,
) -> dict[str, Any]:
    """Entrega memória completa em retomada fria; recibo de cache não entra."""

    return _npc_memory.resume(
        repo,
        result,
        max_output_bytes=max_output_bytes,
        records=records,
        measure=measure,
    )


def compile_cast(
    payload: dict[str, Any],
    transaction: dict[str, Any],
    *,
    repo: Path | None = None,
) -> dict[str, Any]:
    return _npc_memory.compile_cast(payload, transaction, repo=repo)


def prepare_transaction(repo: Path, transaction: dict[str, Any]) -> dict[str, Any]:
    """Compila memória no writer atual, preservando o guard social da RM-05."""

    return _npc_memory.prepare_transaction(repo, transaction)


def durable_persistence_observation(
    source: dict[str, Any],
    compiled: dict[str, Any],
) -> dict[str, Any] | None:
    """Projeta somente contagens de fatos já validados, sem vazar conteúdo."""

    block = source.get(TRANSACTION_KEY) if isinstance(source, dict) else None
    facts = block.get("fatos") if isinstance(block, dict) else None
    if not isinstance(facts, list) or not facts:
        return None
    by_type = {
        kind: sum(
            isinstance(fact, dict) and fact.get("tipo") == kind for fact in facts
        )
        for kind in ("promessa", "informacao", "relacao", "marco")
    }
    with_evidence = sum(
        isinstance(fact, dict)
        and isinstance(fact.get("evidencia"), dict)
        and bool(fact["evidencia"].get("trecho"))
        for fact in facts
    )
    destinations: set[str] = set()
    for delta in compiled.get("deltas") or []:
        target = str(delta.get("alvo") or "")
        if target == "conhecimento":
            destinations.add("conhecimento_ren")
        elif target == "estado" and str(delta.get("caminho") or "").startswith("compromissos"):
            destinations.add("compromissos")
        elif target.startswith("npc:"):
            destinations.add("medidores_npc")
        elif target.startswith("relacao:"):
            destinations.add("memoria_relacional")
    return {
        "schema_context_and_memory": FACADE_SCHEMA,
        "module_id": MODULE_ID,
        "transacao_id": compiled.get("id"),
        "fatos_esperados": len(facts),
        "fatos_validados": len(facts),
        "fatos_com_evidencia": with_evidence,
        "por_tipo": by_type,
        "camadas_destino": sorted(destinations),
    }


def publish_memory_persistence(
    result: dict[str, Any],
    observation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Publica o recibo somente depois de o writer transacional retornar."""

    if observation is None:
        return attach_coverage(
            result,
            module_id=MODULE_ID,
            phase="concluir",
            applicability="nao_aplicavel",
        )
    out = copy.deepcopy(observation)
    transaction = result.get("transacao") if isinstance(result, dict) else None
    retry = isinstance(transaction, dict) and transaction.get("ja_registrada") is True
    out.update(
        evento_modular="consulta" if retry else "efeito_material",
        resultado_modular=(
            "retry_sem_duplicacao" if retry else "memoria_duravel_persistida"
        ),
        efeito_materializado=not retry,
        fatos_persistidos_novos=0 if retry else out["fatos_validados"],
        fatos_confirmados=out["fatos_validados"],
    )
    result[MEMORY_PERSISTENCE_KEY] = out
    systems = result.setdefault("sistemas_narrativos", [])
    if MODULE_ID not in systems:
        systems.append(MODULE_ID)
    return attach_coverage(
        result,
        module_id=MODULE_ID,
        phase="concluir",
        applicability="aplicavel",
    )


# Consultas internas dirigidas usadas por produtores já existentes. Elas não
# expõem busca fuzzy nem criam uma segunda implementação de memória.
size = _scene_engine.size
receipt = _scene_engine.receipt
load_scene = _scene_engine.load_scene
documents = _scene_engine.documents


def project_scene_memory(
    docs: dict[str, Any],
    *,
    scope: str,
    budget: int,
    base: dict[str, Any] | None = None,
    sources: list[str] | None = None,
    measure: Callable[[Any], int] = _scene_engine.size,
) -> dict[str, Any]:
    return _scene_engine.project(
        docs,
        scope=scope,
        budget=budget,
        base=base,
        sources=sources,
        measure=measure,
    )


# Nome público histórico usado por produtores internos já existentes.
project = project_scene_memory


def validate_cast(value: Any) -> dict[str, Any] | None:
    return _scene_engine.cast(value)


cast = validate_cast


def scene_time(state: dict[str, Any], records: list[dict[str, Any]]) -> tuple[str, str]:
    return _scene_engine._time(state, records)


def already_consolidated(repo: Path, session: int, transaction_id: str) -> bool:
    return _durable_engine._already_consolidated(repo, session, transaction_id)


def compile_durable_memory(
    transaction: dict[str, Any], transaction_id: str, session: int
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    return _durable_engine.compile_transaction(transaction, transaction_id, session)


def _access_check(_repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    expected = {
        "status": "L1",
        "cena": "L2",
        "retomada": "L2",
        "npc": "L2",
        "local": "L2",
        "relacao": "L2",
        "recurso": "L2",
        "conhecimento": "L2",
        "regra": "L2",
        "reputacao": "L2",
        "continuidade": "L2",
    }
    for command, level in expected.items():
        if classify(command).level != level:
            errors.append(f"{command} não resolve em {level}")
    if classify("buscar", historical=True, transcripts=True).required_after != "L4":
        errors.append("transcrição não exige L4 anterior")
    if LEVEL_BUDGETS != {
        "L1": 4096,
        "L2": 8192,
        "L3": 8192,
        "L4": 12288,
        "L4T": 16384,
    }:
        errors.append("tetos L1–L4T divergentes")
    return {"ok": not errors, "erros": errors, "tetos": dict(LEVEL_BUDGETS)}


def _memory_check(_repo: Path) -> dict[str, Any]:
    evidence = "Ren relatou a Silva que a ponte caiu, mas somente como rumor."
    transaction = {
        "jogador": "Ren conversa com Silva.",
        "narracao": evidence,
        "resumo": "Silva recebeu um rumor.",
        "deltas": [],
        "memoria": {
            "versao": 1,
            "fatos": [
                {
                    "id": "rumor_ponte",
                    "tipo": "informacao",
                    "participantes": ["ren", "silva_fixture", "nera_fixture"],
                    "evidencia": {"campo": "narracao", "trecho": evidence},
                    "texto": evidence,
                    "emissor": "ren",
                    "destinatario": "silva_fixture",
                    "canal": "presencial",
                    "estatuto": "rumor",
                }
            ],
        },
    }
    errors: list[str] = []
    try:
        writer, _ = compile_durable_memory(transaction, "check-context-memory", 1)
        targets = [delta.get("alvo") for delta in writer.get("deltas") or []]
        if targets != ["relacao:silva_fixture"]:
            errors.append("informação vazou para participante não destinatário")
        if writer["deltas"][0]["valor"].get("estatuto") != "rumor":
            errors.append("rumor foi promovido a fato")
    except (KeyError, ValueError) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "erros": errors,
        "memoria_cena_bytes_max": MAX_MEMORY_BYTES,
        "fatos_por_conclusao_max": MAX_FACTS,
    }


def _cold_resume_check(repo: Path) -> dict[str, Any]:
    import retomada_cronica

    errors: list[str] = []
    snapshot = retomada_cronica.current_snapshot(repo, include_memory=False)
    sources = list(snapshot.get("fontes_lidas") or [])
    if snapshot.get("transcricao_lida") is not False:
        errors.append("retomada fria não declarou transcrição fechada")
    if any("transcricao" in source.casefold() for source in sources):
        errors.append("retomada fria abriu transcrição")
    for key in ("sessao", "agora", "fontes_lidas"):
        if key not in snapshot:
            errors.append(f"retomada fria sem {key}")
    return {"ok": not errors, "erros": errors, "fontes_lidas": sources}


def check(repo: Path) -> dict[str, Any]:
    return combine_checks(
        repo,
        module_id=MODULE_ID,
        capabilities=CAPABILITIES,
        legacy_components=LEGACY_COMPONENTS,
        checks=(
            ("routed_context_access", _access_check),
            ("scene_and_durable_memory", _memory_check),
            ("cold_resume", _cold_resume_check),
        ),
        contract={
            "source_ownership": SOURCE_OWNERSHIP,
            "l0_requires_tool_call": False,
            "l3_plus_requires_demonstrated_gap": True,
            "transcript_is_normal_resume_source": False,
            "scene_receipt_survives_context_loss": False,
            "narrator_knowledge_is_ren_or_npc_knowledge": False,
            "rumor_becomes_fact": False,
            "durable_memory_uses_existing_writer": True,
            "additional_orchestration_calls": 0,
            "new_global_scan": False,
            "parallel_state": False,
        },
    )


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
