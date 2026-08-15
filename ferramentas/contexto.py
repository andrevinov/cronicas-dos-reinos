#!/usr/bin/env python3
"""Porta única de contexto com sobreposição dos deltas transacionais pendentes.

O motor de consulta fragmentada da Etapa 6 vive em `contexto_core.py`. Esta
camada acrescenta o estado efetivo da sessão: durante narração ao vivo, fatos
novos ficam em `runtime/eventos-pendentes.jsonl` até a consolidação e são
projetados aqui sem reescrever os arquivos canônicos.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import contexto_core as core
import transacoes

# Guarda as implementações originais ANTES de substituir os pontos de dispatch
# do núcleo. Sem isso, o caminho CLI recursaria para o próprio wrapper.
_CORE_COMMAND_STATUS = core.command_status
_CORE_COMMAND_SCENE = core.command_scene
_CORE_COMMAND_RELATION = core.command_relation
_CORE_COMMAND_NPC = core.command_npc
_CORE_COMMAND_KNOWLEDGE = core.command_knowledge
_CORE_COMMAND_SEARCH = core.command_search

# Reexporta a API de helpers usada por testes e por ferramentas auxiliares.
DEFAULT_MAX_BYTES = core.DEFAULT_MAX_BYTES
HARD_MAX_BYTES = core.HARD_MAX_BYTES
QUERY_LOG = core.QUERY_LOG
TEXT_SUFFIXES = core.TEXT_SUFFIXES
SKIP_DIRS = core.SKIP_DIRS
REL_INDEX = core.REL_INDEX
NPC_INDEX = core.NPC_INDEX
KNOW_INDEX = core.KNOW_INDEX
KNOW_ACTIVE = core.KNOW_ACTIVE
KNOW_ROOT = core.KNOW_ROOT

load_yaml = core.load_yaml
normalize = core.normalize
truncate_text = core.truncate_text
compact_value = core.compact_value
serialize = core.serialize
fit_budget = core.fit_budget
entity_score = core.entity_score
resolve_entity = core.resolve_entity
compact_relation = core.compact_relation
split_markdown_sections = core.split_markdown_sections
section_score = core.section_score
search_markdown_files = core.search_markdown_files
iter_search_files = core.iter_search_files
generic_search = core.generic_search
envelope = core.envelope
command_rule = core.command_rule
log_query = core.log_query
build_parser = core.build_parser


def _pending(repo: Path) -> list[dict[str, Any]]:
    return transacoes.load_pending(repo)


def _has_overlay(result: dict[str, Any]) -> bool:
    return isinstance(result, dict) and "sobreposicao_transacional" in result


def _add_pending_source(data: dict[str, Any]) -> None:
    sources = list(data.get("fontes") or [])
    pending = transacoes.PENDING_PATH.as_posix()
    if pending not in sources:
        sources.append(pending)
    data["fontes"] = sources


def command_status(repo: Path) -> dict[str, Any]:
    data = _CORE_COMMAND_STATUS(repo)
    context = data.get("resultado")
    if not isinstance(context, dict):
        return data
    effective, _, _ = transacoes.overlay_runtime(context, None, _pending(repo))
    data["resultado"] = effective
    if _has_overlay(effective):
        _add_pending_source(data)
    return data


def command_scene(repo: Path) -> dict[str, Any]:
    data = _CORE_COMMAND_SCENE(repo)
    result = data.get("resultado") or {}
    context = result.get("contexto") if isinstance(result, dict) else None
    scene = result.get("cena") if isinstance(result, dict) else None
    if not isinstance(context, dict) or not isinstance(scene, dict):
        return data
    effective_context, effective_scene, _ = transacoes.overlay_runtime(
        context, scene, _pending(repo)
    )
    data["resultado"] = {"contexto": effective_context, "cena": effective_scene}
    if _has_overlay(effective_context):
        _add_pending_source(data)
    return data


def command_relation(repo: Path, term: str) -> dict[str, Any]:
    data = _CORE_COMMAND_RELATION(repo, term)
    result = data.get("resultado") or {}
    if not isinstance(result, dict) or not result.get("encontrado"):
        return data
    relation = result.get("relacao")
    entity_id = result.get("id")
    if not isinstance(relation, dict) or not isinstance(entity_id, str):
        return data
    effective, applied = transacoes.overlay_target(
        relation, _pending(repo), f"relacao:{entity_id}"
    )
    result["relacao"] = effective
    if applied:
        result["deltas_pendentes_aplicados"] = applied
        _add_pending_source(data)
    return data


def command_npc(repo: Path, term: str) -> dict[str, Any]:
    data = _CORE_COMMAND_NPC(repo, term)
    result = data.get("resultado") or {}
    if not isinstance(result, dict) or not result.get("encontrado"):
        return data
    records = _pending(repo)
    applied_total = 0

    med = result.get("medidores")
    if isinstance(med, dict) and isinstance(med.get("id"), str) and isinstance(med.get("dados"), dict):
        effective, applied = transacoes.overlay_target(
            med["dados"], records, f"npc:{med['id']}"
        )
        med["dados"] = effective
        applied_total += applied

    relation = result.get("relacao")
    if (
        isinstance(relation, dict)
        and isinstance(relation.get("id"), str)
        and isinstance(relation.get("dados"), dict)
    ):
        effective, applied = transacoes.overlay_target(
            relation["dados"], records, f"relacao:{relation['id']}"
        )
        relation["dados"] = effective
        applied_total += applied

    if applied_total:
        result["deltas_pendentes_aplicados"] = applied_total
        _add_pending_source(data)
    return data


def command_knowledge(repo: Path, term: str) -> dict[str, Any]:
    data = _CORE_COMMAND_KNOWLEDGE(repo, term)
    result = data.get("resultado") or {}
    if not isinstance(result, dict):
        return data
    pending = transacoes.search_pending(
        _pending(repo), term, reserved=False, target_prefix="conhecimento", limit=4
    )
    if pending:
        result["pendentes"] = pending
        result["encontrado"] = True
        _add_pending_source(data)
        # Conhecimento ainda não consolidado é atual e dirigido; não deve ser
        # tratado como razão para escalar ao histórico.
        if data.get("nivel") == "L2-L3":
            data["nivel"] = "L2"
    return data


def command_search(
    repo: Path,
    term: str,
    *,
    reserved: bool,
    historical: bool,
) -> dict[str, Any]:
    data = _CORE_COMMAND_SEARCH(
        repo, term, reserved=reserved, historical=historical
    )
    result = data.get("resultado") or {}
    if not isinstance(result, dict):
        return data
    pending = transacoes.search_pending(_pending(repo), term, reserved=reserved, limit=5)
    if not pending:
        return data

    pending_occurrences = [
        {
            "arquivo": transacoes.PENDING_PATH.as_posix(),
            "transacao": item.get("transacao"),
            "sessao": item.get("sessao"),
            "trecho": core.truncate_text(item.get("resumo", ""), 650),
        }
        for item in pending
    ]
    existing = list(result.get("ocorrencias") or [])
    result["ocorrencias"] = (pending_occurrences + existing)[:8]
    result["encontrado"] = True
    _add_pending_source(data)
    return data


def main() -> int:
    # O parser e o controle de orçamento permanecem no núcleo; apenas substituímos
    # os pontos de dispatch. As funções wrapper chamam as referências originais
    # guardadas acima, portanto não há recursão.
    core.command_status = command_status
    core.command_scene = command_scene
    core.command_relation = command_relation
    core.command_npc = command_npc
    core.command_knowledge = command_knowledge
    core.command_search = command_search
    return core.main()


if __name__ == "__main__":
    raise SystemExit(main())
