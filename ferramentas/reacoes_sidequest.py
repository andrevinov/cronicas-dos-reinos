#!/usr/bin/env python3
"""Reações causais posteriores ao progresso ou sucesso de sidequests.

O domínio cria um contrato reservado novo a partir de um fato Task45/49 já
canônico. Ele nunca altera a missão nem seu contrato adversarial original. Uma
reação do mundo usa a fila existente; uma oportunidade sucessora permanece
apenas planejada; ``sem_reacao`` não persiste artefato algum.
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
from pathlib import Path
from typing import Any

import yaml

import agentes
import barreira_mundo
import canon_bridge
import direcoes_destino
import integridade_adversarial as adversarial
import mundo
import oportunidades

SCHEMA = 1
ROOT = Path("narrador/sidequest-reacoes")
INDEX = ROOT / "index.yaml"
STATE = ROOT / "estado.yaml"
CONTRACTS = ROOT / "contratos"

CLASSIFICATIONS = {"reacao_mundo", "oportunidade_sucessora", "sem_reacao"}
TRIGGER_TYPES = {"terminal_sucesso", "progresso_excepcional"}
REACTION_STATES = {"planejada", "elegivel", "comprometida", "resolvida", "cancelada"}
ALTERNATIVE_TYPES = {"juridica", "furtiva", "violenta", "social", "logistica"}
TARGET_TYPES = {"npc", "instituicao", "recurso", "propriedade", "informacao", "local", "outro"}
MAX_REACTIONS = 16
MAX_ALTERNATIVES = 8
MAX_TARGETS = 10
MAX_RESOURCES = 8
MAX_HISTORY = 48
MAX_CONTRACT_BYTES = 32 * 1024
MAX_PREP_BYTES = 12 * 1024
MAX_WINDOW_DAYS = 30
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_:-]{0,95}$")
REACTION_RE = re.compile(r"^rsq-[0-9a-f]{20}$")
FORBIDDEN_PROOF_PREFIXES = (
    "narrador/sidequest-reacoes/",
    "narrador/sidequests-emergentes/",
    "narrador/arcos/parte_1/intencoes/",
    "narrador/arcos/parte_1/eventos/",
)


class SidequestReactionError(ValueError):
    pass


def configured(repo: Path) -> bool:
    return (repo / INDEX).is_file() or (repo / STATE).is_file()


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SidequestReactionError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise SidequestReactionError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str, *, minimum: int = 1, maximum: int = 520) -> str:
    if not isinstance(value, str):
        raise SidequestReactionError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if not minimum <= len(result) <= maximum:
        raise SidequestReactionError(
            f"{label} deve ter {minimum}..{maximum} caracteres"
        )
    return result


def _id(value: Any, label: str) -> str:
    result = _text(value, label, maximum=128)
    if not ID_RE.fullmatch(result):
        raise SidequestReactionError(f"{label} deve ser ID ASCII minúsculo estável")
    return result


def _slug(value: Any, label: str) -> str:
    result = _text(value, label, maximum=96)
    if not SLUG_RE.fullmatch(result):
        raise SidequestReactionError(f"{label} deve ser slug ASCII minúsculo")
    return result


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _yaml(value: Any) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        return _map(yaml.safe_load(path.read_text(encoding="utf-8")), label)
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise SidequestReactionError(str(exc)) from exc


def _atomic(path: Path, value: dict[str, Any], *, maximum: int | None = None) -> None:
    rendered = _yaml(value)
    if maximum is not None and len(rendered.encode("utf-8")) > maximum:
        raise SidequestReactionError(
            f"{path.as_posix()} excede orçamento de {maximum} bytes"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _safe_proof(repo: Path, raw: Any, label: str) -> dict[str, str]:
    proof = _map(raw, label)
    if set(proof) != {"fonte", "evidencia"}:
        raise SidequestReactionError(f"{label} exige fonte e evidencia")
    source = _text(proof["fonte"], f"{label}.fonte", maximum=240)
    rel = Path(source)
    if (
        rel.is_absolute()
        or ".." in rel.parts
        or any(source.startswith(prefix) for prefix in FORBIDDEN_PROOF_PREFIXES)
    ):
        raise SidequestReactionError(
            f"{label}: planejamento reservado não serve como prova causal"
        )
    path = repo / rel
    if not path.is_file():
        raise SidequestReactionError(f"{label}: fonte inexistente: {source}")
    evidence = _text(proof["evidencia"], f"{label}.evidencia", minimum=8, maximum=360)
    if evidence not in " ".join(path.read_text(encoding="utf-8").split()):
        raise SidequestReactionError(f"{label}: evidência não é literal em {source}")
    return {"fonte": source, "evidencia": evidence}


def _parts(value: Any, label: str) -> tuple[dict[str, str], mundo.WorldInstant]:
    raw = _map(value, label)
    if set(raw) != {"data", "hora"}:
        raise SidequestReactionError(f"{label} exige data e hora")
    parts = {
        "data": _text(raw["data"], f"{label}.data", maximum=80),
        "hora": _text(raw["hora"], f"{label}.hora", maximum=12),
    }
    try:
        return parts, mundo.parse_instant(parts["data"], parts["hora"])
    except mundo.WorldEngineError as exc:
        raise SidequestReactionError(str(exc)) from exc


def _mission(repo: Path, ref: str) -> tuple[dict[str, Any], str, dict[str, Any]]:
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise SidequestReactionError(str(exc)) from exc
    matches = [
        (mission_id, mission)
        for mission_id, mission in state.get("missoes", {}).items()
        if isinstance(mission, dict)
        and mission.get("origem") == "sidequest_emergente"
        and ref in {mission_id, mission.get("id"), mission.get("quest_id")}
    ]
    if len(matches) != 1:
        raise SidequestReactionError(f"sidequest emergente inexistente/ambígua: {ref}")
    return state, matches[0][0], matches[0][1]


def _progress(repo: Path, mission_id: str, mission: dict[str, Any]) -> tuple[dict[str, Any], str]:
    source = mission.get("progresso_sidequest")
    if not isinstance(source, str) or not source.startswith(
        "narrador/sidequests-emergentes/progresso/"
    ):
        raise SidequestReactionError("missão não possui fragmento Task45 válido")
    doc = _load(repo / source, source)
    if (
        doc.get("schema_progressao_sidequest") != 1
        or doc.get("natureza") != "reservado"
        or doc.get("mission_id") != mission_id
        or doc.get("quest_id") != mission.get("quest_id")
    ):
        raise SidequestReactionError("fragmento Task45 divergente")
    return doc, source


def _trigger(
    repo: Path,
    mission_id: str,
    mission: dict[str, Any],
    progress: dict[str, Any],
    raw: Any,
) -> dict[str, Any]:
    trigger = _map(raw, "gatilho")
    if set(trigger) != {"tipo", "fato_id"}:
        raise SidequestReactionError("gatilho exige tipo e fato_id")
    trigger_type = _text(trigger["tipo"], "gatilho.tipo", maximum=32)
    if trigger_type not in TRIGGER_TYPES:
        raise SidequestReactionError("gatilho.tipo inválido")
    fact_id = _id(trigger["fato_id"], "gatilho.fato_id")
    fact = _map(
        (_map(progress.get("estado"), "progresso.estado").get("fatos") or {}).get(fact_id),
        f"fato {fact_id}",
    )
    proof = _safe_proof(repo, fact.get("prova"), f"fato {fact_id}.prova")
    if trigger_type == "terminal_sucesso":
        terminal = _map(progress["estado"].get("terminal"), "progresso.terminal")
        if mission.get("estado") != "concluida" or terminal.get("resultado") != "concluida":
            raise SidequestReactionError(
                "terminal_sucesso exige missão e Task45 concluídas factualmente"
            )
        occurred, _ = _parts(terminal.get("em"), "progresso.terminal.em")
    else:
        if mission.get("estado") not in {"aceita", "concluida"}:
            raise SidequestReactionError(
                "progresso excepcional exige missão aceita ou concluída"
            )
        if "canonizado_em" not in fact:
            raise SidequestReactionError(
                "fato excepcional não possui canonizado_em Task49; migre-o antes da reação"
            )
        occurred, _ = _parts(fact["canonizado_em"], f"fato {fact_id}.canonizado_em")
    return {
        "tipo": trigger_type,
        "fato_id": fact_id,
        "descricao": _text(fact.get("descricao"), f"fato {fact_id}.descricao"),
        "prova": proof,
        "canonizado_em": occurred,
    }


def _agent(repo: Path, actor_id: str) -> dict[str, Any]:
    try:
        loaded = agentes.load_agent_complete(repo, actor_id)
    except agentes.AgentValidationError as exc:
        raise SidequestReactionError(str(exc)) from exc
    actor = loaded["resultado"]
    if actor.get("estado") != "ativo":
        raise SidequestReactionError(f"antagonista não está ativo: {actor_id}")
    capabilities = adversarial._flatten_methods(actor)
    knowledge = {
        str(item["id"]): copy.deepcopy(item)
        for item in actor.get("conhecimento") or []
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    return {
        "id": actor_id,
        "tipo": actor.get("tipo"),
        "objetivo_atual": _text(actor.get("objetivo_atual"), "antagonista.objetivo_atual"),
        "recursos": list(actor.get("recursos") or []),
        "restricoes": list(actor.get("restricoes") or []),
        "presenca": copy.deepcopy(actor.get("presenca") or {}),
        "mobilidade": copy.deepcopy(actor.get("mobilidade") or {}),
        "atuacao_local": copy.deepcopy(actor.get("atuacao_local") or {}),
        "elegibilidade_local": loaded.get("elegibilidade_local"),
        "capacidades": capabilities,
        "conhecimento": knowledge,
        "fonte": loaded["fontes_lidas"][1],
        "fontes_lidas": list(loaded["fontes_lidas"]),
    }


def _targets(raw: Any, label: str) -> list[dict[str, str]]:
    rows = _list(raw, label)
    if not 1 <= len(rows) <= MAX_TARGETS:
        raise SidequestReactionError(f"{label} exige 1..{MAX_TARGETS} alvos")
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for position, value in enumerate(rows):
        item = _map(value, f"{label}[{position}]")
        if set(item) != {"id", "tipo"}:
            raise SidequestReactionError("alvo exige id e tipo")
        target = {
            "id": _id(item["id"], f"{label}[{position}].id"),
            "tipo": _text(item["tipo"], f"{label}[{position}].tipo", maximum=24),
        }
        if target["tipo"] not in TARGET_TYPES:
            raise SidequestReactionError(f"tipo de alvo inválido: {target['tipo']}")
        key = (target["tipo"], target["id"])
        if key in seen:
            raise SidequestReactionError(f"alvo duplicado: {target['id']}")
        seen.add(key)
        result.append(target)
    return result


def _consequence(raw: dict[str, Any], targets: list[dict[str, str]]) -> dict[str, Any]:
    return {
        "titulo": _text(raw["titulo"], "alternativa.titulo", maximum=160),
        "descricao": _text(raw["resultado_possivel"], "alternativa.resultado_possivel"),
        "gravidade": _text(raw["gravidade"], "alternativa.gravidade", maximum=16),
        "reversibilidade": _text(
            raw["reversibilidade"], "alternativa.reversibilidade", maximum=16
        ),
        "classe_impacto": _text(
            raw["classe_impacto"], "alternativa.classe_impacto", maximum=24
        ),
        "alvos_npc": [target["id"] for target in targets if target["tipo"] == "npc"],
    }


def _alternative(
    repo: Path,
    raw: Any,
    position: int,
    actor: dict[str, Any],
    unavailable_resources: set[str],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    item = _map(raw, f"alternativas[{position}]")
    expected = {
        "id", "tipo", "titulo", "objetivo", "resultado_possivel", "capacidade_id",
        "conhecimentos_requeridos", "alvos", "recursos_exigidos",
        "exige_presenca_fisica", "grupo_exclusividade", "gravidade",
        "reversibilidade", "classe_impacto", "bloqueios_causais",
    }
    if set(item) != expected:
        raise SidequestReactionError(
            f"alternativa possui campos divergentes: {sorted(set(item) ^ expected)}"
        )
    alternative_id = _slug(item["id"], f"alternativas[{position}].id")
    kind = _text(item["tipo"], f"{alternative_id}.tipo", maximum=20)
    if kind not in ALTERNATIVE_TYPES:
        raise SidequestReactionError(f"{alternative_id}: tipo operacional inválido")
    capability_id = _slug(item["capacidade_id"], f"{alternative_id}.capacidade_id")
    required_knowledge = [
        _slug(value, f"{alternative_id}.conhecimentos_requeridos")
        for value in _list(
            item["conhecimentos_requeridos"],
            f"{alternative_id}.conhecimentos_requeridos",
        )
    ]
    if len(required_knowledge) != len(set(required_knowledge)):
        raise SidequestReactionError(f"{alternative_id}: conhecimento duplicado")
    targets = _targets(item["alvos"], f"{alternative_id}.alvos")
    resources = [
        _text(value, f"{alternative_id}.recursos_exigidos", maximum=240)
        for value in _list(item["recursos_exigidos"], f"{alternative_id}.recursos_exigidos")
    ]
    if len(resources) > MAX_RESOURCES or len(resources) != len(set(resources)):
        raise SidequestReactionError(
            f"{alternative_id}: recursos excedem {MAX_RESOURCES} ou estão duplicados"
        )
    physical = item["exige_presenca_fisica"]
    if not isinstance(physical, bool):
        raise SidequestReactionError(f"{alternative_id}.exige_presenca_fisica deve ser bool")
    group_raw = item["grupo_exclusividade"]
    group = None if group_raw is None else _slug(group_raw, f"{alternative_id}.grupo_exclusividade")
    blockers = [
        _text(value, f"{alternative_id}.bloqueios_causais", minimum=8)
        for value in _list(item["bloqueios_causais"], f"{alternative_id}.bloqueios_causais")
    ]
    if len(blockers) != len(set(blockers)):
        raise SidequestReactionError(f"{alternative_id}: bloqueios duplicados")

    reasons: list[str] = []
    capability = actor["capacidades"].get(capability_id)
    if capability is None:
        reasons.append("capacidade_nao_disponivel")
    missing_knowledge = sorted(set(required_knowledge) - set(actor["conhecimento"]))
    if missing_knowledge:
        reasons.append("conhecimento_canonico_ausente:" + ",".join(missing_knowledge))
    missing_resources = [value for value in resources if value not in actor["recursos"]]
    if missing_resources:
        reasons.append("recurso_canonico_ausente:" + "|".join(missing_resources))
    already_committed = [value for value in resources if value in unavailable_resources]
    if already_committed:
        reasons.append("recurso_ja_comprometido:" + "|".join(already_committed))
    presence_state = str(actor["presenca"].get("estado") or "")
    if physical and (
        presence_state not in {"presente", "presente_oculto"}
        or actor["elegibilidade_local"] != "sim"
    ):
        reasons.append("presenca_fisica_incompativel")

    consequence = _consequence(item, targets)
    try:
        protected = adversarial.authorize_external_consequence(
            repo, consequence, authority="procedural"
        )
    except adversarial.AdversarialIntegrityError as exc:
        protected = None
        reasons.append("integridade_adversarial:" + str(exc))

    knowledge_snapshots: list[dict[str, Any]] = []
    for knowledge_id in required_knowledge:
        knowledge = actor["conhecimento"].get(knowledge_id)
        if knowledge is None:
            continue
        try:
            proof = _safe_proof(
                repo,
                {"fonte": knowledge.get("fonte"), "evidencia": knowledge.get("evidencia")},
                f"conhecimento {knowledge_id}",
            )
        except SidequestReactionError as exc:
            reasons.append("conhecimento_sem_prova:" + str(exc))
            continue
        knowledge_snapshots.append(
            {"id": knowledge_id, "fato": knowledge.get("fato"), "prova": proof}
        )

    normalized = {
        "id": alternative_id,
        "tipo": kind,
        "titulo": consequence["titulo"],
        "objetivo": _text(item["objetivo"], f"{alternative_id}.objetivo"),
        "resultado_possivel": consequence["descricao"],
        "capacidade_id": capability_id,
        "conhecimentos_requeridos": required_knowledge,
        "alvos": targets,
        "recursos_exigidos": resources,
        "exige_presenca_fisica": physical,
        "grupo_exclusividade": group,
        "gravidade": consequence["gravidade"],
        "reversibilidade": consequence["reversibilidade"],
        "classe_impacto": consequence["classe_impacto"],
        "bloqueios_causais": blockers,
        "estado": "elegivel" if not reasons else "bloqueada",
        "motivos_bloqueio": reasons,
        "autoridade_consequencia": (
            protected["autoridade"] if protected is not None else None
        ),
    }
    capabilities = []
    if capability is not None:
        capabilities.append(
            {"id": capability_id, "fonte": actor["fonte"], **copy.deepcopy(capability)}
        )
    return normalized, capabilities, knowledge_snapshots


def _window(raw: Any, fact_instant: mundo.WorldInstant) -> dict[str, Any]:
    value = _map(raw, "janela")
    if set(value) != {"minimo", "maximo", "condicao"}:
        raise SidequestReactionError("janela exige minimo, maximo e condicao")
    minimum_parts, minimum = _parts(value["minimo"], "janela.minimo")
    maximum_parts, maximum = _parts(value["maximo"], "janela.maximo")
    if minimum < fact_instant:
        raise SidequestReactionError("janela de reação não pode começar antes do fato")
    if maximum < minimum:
        raise SidequestReactionError("janela.maximo deve ser posterior a janela.minimo")
    if maximum.minute - minimum.minute > MAX_WINDOW_DAYS * 1440:
        raise SidequestReactionError(
            f"janela de reação excede {MAX_WINDOW_DAYS} dias"
        )
    return {
        "minimo": minimum_parts,
        "maximo": maximum_parts,
        "condicao": _text(value["condicao"], "janela.condicao"),
    }


def _normalize_link(
    repo: Path, raw: Any, mission_id: str
) -> tuple[dict[str, str] | None, list[str]]:
    if raw is None:
        return None, []
    value = _map(raw, "vinculo_canonico")
    if set(value) != {"tipo", "id"}:
        raise SidequestReactionError("vinculo_canonico exige tipo e id")
    kind = _text(value["tipo"], "vinculo_canonico.tipo", maximum=24)
    if kind not in {"direcao", "ponte_task42"}:
        raise SidequestReactionError("vinculo_canonico.tipo inválido")
    link_id = _id(value["id"], "vinculo_canonico.id")
    if kind == "direcao":
        try:
            projected = direcoes_destino.project(repo, link_id)
        except direcoes_destino.DestinationDirectionError as exc:
            raise SidequestReactionError(str(exc)) from exc
        return {"tipo": kind, "id": link_id}, list(projected.get("fontes_lidas") or [])
    try:
        bridge = canon_bridge.load_state(repo)
    except canon_bridge.CanonBridgeError as exc:
        raise SidequestReactionError(str(exc)) from exc
    reservation = bridge.get("reservas", {}).get(link_id)
    if not isinstance(reservation, dict) or reservation.get("mission_id") != mission_id:
        raise SidequestReactionError(
            "vínculo ponte Task42 não corresponde à missão de origem"
        )
    return {"tipo": kind, "id": link_id}, [canon_bridge.STATE.as_posix()]


def _contract(
    repo: Path, mission_ref: str, proposal_raw: Any
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    proposal = _map(proposal_raw, "avaliacao_reacao")
    classification = _text(proposal.get("classificacao"), "classificacao", maximum=32)
    if classification not in CLASSIFICATIONS:
        raise SidequestReactionError("classificacao de reação inválida")
    expected = (
        {"classificacao", "gatilho", "motivo"}
        if classification == "sem_reacao"
        else {
            "classificacao", "gatilho", "antagonista_id", "alternativas", "janela",
            "vinculo_canonico", "motivo",
        }
    )
    if set(proposal) != expected:
        raise SidequestReactionError(
            f"avaliação possui campos divergentes: {sorted(set(proposal) ^ expected)}"
        )
    _, mission_id, mission = _mission(repo, mission_ref)
    progress, progress_source = _progress(repo, mission_id, mission)
    trigger = _trigger(repo, mission_id, mission, progress, proposal["gatilho"])
    reason = _text(proposal["motivo"], "motivo", minimum=12)
    if classification == "sem_reacao":
        return None, {
            "classification": classification,
            "mission_id": mission_id,
            "quest_id": mission["quest_id"],
            "trigger": trigger,
            "reason": reason,
            "sources": [oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix(), progress_source, trigger["prova"]["fonte"]],
        }

    actor_id = _slug(proposal["antagonista_id"], "antagonista_id")
    actor = _agent(repo, actor_id)
    origin_key = _digest(
        {
            "mission_id": mission_id,
            "fato_id": trigger["fato_id"],
            "antagonista_id": actor_id,
        }
    )
    unavailable_resources: set[str] = set()
    reaction_sources: list[str] = []
    if configured(repo):
        existing_index = _load_index(repo)
        existing_state = _load_state(repo)
        same_origin = {
            rid
            for rid, row in existing_index["reacoes"].items()
            if isinstance(row, dict) and row.get("chave_origem") == origin_key
        }
        for reservation in existing_state["recursos_comprometidos"].values():
            if (
                isinstance(reservation, dict)
                and reservation.get("antagonista_id") == actor_id
                and reservation.get("reaction_id") not in same_origin
                and isinstance(reservation.get("recurso"), str)
            ):
                unavailable_resources.add(reservation["recurso"])
        reaction_sources.extend([INDEX.as_posix(), STATE.as_posix()])
    raw_alternatives = _list(proposal["alternativas"], "alternativas")
    if not 1 <= len(raw_alternatives) <= MAX_ALTERNATIVES:
        raise SidequestReactionError(
            f"reação exige 1..{MAX_ALTERNATIVES} alternativas"
        )
    alternatives: list[dict[str, Any]] = []
    capabilities: dict[str, dict[str, Any]] = {}
    knowledge: dict[str, dict[str, Any]] = {}
    for position, raw in enumerate(raw_alternatives):
        alternative, option_capabilities, option_knowledge = _alternative(
            repo, raw, position, actor, unavailable_resources
        )
        if alternative["id"] in {item["id"] for item in alternatives}:
            raise SidequestReactionError(f"alternativa duplicada: {alternative['id']}")
        alternatives.append(alternative)
        for item in option_capabilities:
            capabilities.setdefault(item["id"], item)
        for item in option_knowledge:
            knowledge.setdefault(item["id"], item)
    eligible = [item for item in alternatives if item["estado"] == "elegivel"]
    if not eligible:
        raise SidequestReactionError(
            "classificação material exige ao menos uma alternativa com capacidade, conhecimento, presença, recursos e autoridade"
        )

    _, fact_instant = _parts(trigger["canonizado_em"], "gatilho.canonizado_em")
    window = _window(proposal["janela"], fact_instant)
    try:
        _, task44_source = adversarial.load_contract(repo, mission)
    except adversarial.AdversarialIntegrityError as exc:
        raise SidequestReactionError(str(exc)) from exc
    task44_path = repo / task44_source
    targets = []
    seen_targets: set[tuple[str, str]] = set()
    for alternative in alternatives:
        for target in alternative["alvos"]:
            key = (target["tipo"], target["id"])
            if key not in seen_targets:
                seen_targets.add(key)
                targets.append(copy.deepcopy(target))
    link, link_sources = _normalize_link(
        repo, proposal["vinculo_canonico"], mission_id
    )
    core = {
        "mission_id": mission_id,
        "quest_id": mission["quest_id"],
        "classificacao": classification,
        "gatilho": trigger,
        "antagonista": {
            "id": actor_id,
            "objetivo_atual": actor["objetivo_atual"],
            "fonte": actor["fonte"],
            "presenca": actor["presenca"],
            "mobilidade": actor["mobilidade"],
            "atuacao_local": actor["atuacao_local"],
            "restricoes": actor["restricoes"],
        },
        "capacidades_canonicas": list(capabilities.values()),
        "conhecimentos_canonicos": list(knowledge.values()),
        "alvos_possiveis": targets,
        "janela": window,
        "alternativas": alternatives,
        "vinculo_canonico": link,
        "motivo_avaliacao": reason,
        "origem_task44": {"arquivo": task44_source, "sha256": _sha(task44_path)},
        "guardrails": {
            "missao_original_nao_reabre": True,
            "contrato_task44_original_imutavel": True,
            "direcao_nao_substitui_capacidade_conhecimento_presenca": True,
            "reacao_mundo_independe_de_aceite_de_ren": True,
            "oportunidade_sucessora_exige_task47_e_oferta_literal": True,
            "sem_rng": True,
            "sem_scheduler_novo": True,
        },
    }
    reaction_id = "rsq-" + _digest(core)[:20]
    contract = {
        "schema_reacao_sidequest": SCHEMA,
        "natureza": "reservado",
        "reaction_id": reaction_id,
        "contrato_digest": _digest(core),
        "contrato": core,
    }
    sources = list(
        dict.fromkeys(
            [
                oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix(),
                progress_source, trigger["prova"]["fonte"], task44_source,
                adversarial.POLICY.as_posix(), *actor["fontes_lidas"],
                *(item["prova"]["fonte"] for item in knowledge.values()),
                *link_sources,
                *reaction_sources,
            ]
        )
    )
    return contract, {
        "classification": classification,
        "mission_id": mission_id,
        "quest_id": mission["quest_id"],
        "trigger": trigger,
        "reason": reason,
        "reaction_id": reaction_id,
        "eligible": [item["id"] for item in eligible],
        "blocked": [
            {"id": item["id"], "motivos": item["motivos_bloqueio"]}
            for item in alternatives if item["estado"] == "bloqueada"
        ],
        "sources": sources,
    }


def _fingerprints(repo: Path, sources: list[str]) -> list[dict[str, str | None]]:
    return [
        {
            "fonte": source,
            "sha256": _sha(repo / source) if (repo / source).is_file() else None,
        }
        for source in sorted(dict.fromkeys(sources))
    ]


def prepare(repo: Path, mission_ref: str, proposal: Any) -> dict[str, Any]:
    contract, meta = _contract(repo, mission_ref, proposal)
    preparation_id = "rsq-prep-" + _digest(
        {
            "contrato": contract,
            "sem_reacao": None if contract is not None else meta,
            "fontes": _fingerprints(repo, meta["sources"]),
        }
    )[:24]
    result = {
        "schema_preparacao_reacao_sidequest": SCHEMA,
        "ok": True,
        "read_only": True,
        "classificacao": meta["classification"],
        "mission_id": meta["mission_id"],
        "quest_id": meta["quest_id"],
        "reaction_id": meta.get("reaction_id"),
        "preparacao_id": preparation_id,
        "alternativas_elegiveis": meta.get("eligible", []),
        "alternativas_bloqueadas": meta.get("blocked", []),
        "mutacoes_aplicadas": False,
        "fontes_lidas": meta["sources"],
        "regra": (
            "preparar não executa reação, não cria sidequest sucessora e não altera "
            "o contrato adversarial original"
        ),
    }
    if len(_yaml(result).encode("utf-8")) > MAX_PREP_BYTES:
        raise SidequestReactionError(
            f"preparação de reação excede {MAX_PREP_BYTES} bytes"
        )
    return result


def _empty_index() -> dict[str, Any]:
    return {
        "schema_reacoes_sidequest": SCHEMA,
        "natureza": "reservado",
        "reacoes": {},
    }


def _empty_state() -> dict[str, Any]:
    return {
        "schema_estado_reacoes_sidequest": SCHEMA,
        "natureza": "controle_reservado",
        "reacoes": {},
        "recursos_comprometidos": {},
        "historico_recente": [],
    }


def _load_index(repo: Path, *, allow_missing: bool = False) -> dict[str, Any]:
    if allow_missing and not (repo / INDEX).is_file():
        return _empty_index()
    data = _load(repo / INDEX, INDEX.as_posix())
    if data.get("schema_reacoes_sidequest") != SCHEMA or data.get("natureza") != "reservado":
        raise SidequestReactionError("índice de reações inválido")
    _map(data.get("reacoes"), "indice.reacoes")
    return data


def _load_state(repo: Path, *, allow_missing: bool = False) -> dict[str, Any]:
    if allow_missing and not (repo / STATE).is_file():
        return _empty_state()
    data = _load(repo / STATE, STATE.as_posix())
    if (
        data.get("schema_estado_reacoes_sidequest") != SCHEMA
        or data.get("natureza") != "controle_reservado"
    ):
        raise SidequestReactionError("estado de reações inválido")
    _map(data.get("reacoes"), "estado.reacoes")
    _map(data.get("recursos_comprometidos"), "estado.recursos_comprometidos")
    _list(data.get("historico_recente"), "estado.historico_recente")
    return data


def _contract_rel(reaction_id: str) -> Path:
    if not REACTION_RE.fullmatch(reaction_id):
        raise SidequestReactionError("reaction_id inválido")
    return CONTRACTS / f"{reaction_id}.yaml"


def _load_contract(repo: Path, reaction_id: str) -> tuple[dict[str, Any], str]:
    index = _load_index(repo)
    meta = _map(index["reacoes"].get(reaction_id), f"indice.{reaction_id}")
    source = _text(meta.get("arquivo"), f"indice.{reaction_id}.arquivo", maximum=240)
    if source != _contract_rel(reaction_id).as_posix():
        raise SidequestReactionError("índice aponta contrato de reação divergente")
    doc = _load(repo / source, source)
    contract = _map(doc.get("contrato"), f"{reaction_id}.contrato")
    if (
        doc.get("schema_reacao_sidequest") != SCHEMA
        or doc.get("natureza") != "reservado"
        or doc.get("reaction_id") != reaction_id
        or doc.get("contrato_digest") != _digest(contract)
    ):
        raise SidequestReactionError(f"contrato de reação divergente: {reaction_id}")
    return doc, source


def _pending(contract: dict[str, Any]) -> dict[str, Any]:
    core = contract["contrato"]
    minimum, instant = _parts(core["janela"]["minimo"], "janela.minimo")
    reaction_id = contract["reaction_id"]
    actor_id = core["antagonista"]["id"]
    return {
        "id": mundo._pending_id(
            "resolver_reacao_sidequest", f"reacoes_sidequest.{reaction_id}", instant
        ),
        "tipo": "resolver_reacao_sidequest",
        "reaction_id": reaction_id,
        "missao": core["mission_id"],
        "quest_id": core["quest_id"],
        "agente": actor_id,
        "agentes_afetados": [actor_id],
        "disparado_em": minimum,
        "janela": copy.deepcopy(core["janela"]),
        "motivo": "Reação causal elegível exige selecionar e comprometer alternativa autorizada.",
        "origem": f"reacao-sidequest:{reaction_id}",
    }


def _enqueue(repo: Path, contract: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    pending = _pending(contract)
    try:
        world = mundo.load_world_state(repo)
    except mundo.WorldEngineError as exc:
        raise SidequestReactionError(str(exc)) from exc
    added = mundo._merge_pending(world, [pending])
    if added:
        mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, world)
    barreira_mundo.sync(repo, world)
    return pending, bool(added)


def materialize(
    repo: Path,
    mission_ref: str,
    proposal: Any,
    *,
    preparation_id: str,
) -> dict[str, Any]:
    prepared = prepare(repo, mission_ref, proposal)
    if prepared["preparacao_id"] != preparation_id:
        raise SidequestReactionError("preparação de reação obsoleta/divergente")
    if prepared["classificacao"] == "sem_reacao":
        return {
            "ok": True,
            "resultado": "sem_reacao",
            "mission_id": prepared["mission_id"],
            "reaction_id": None,
            "mutacoes_aplicadas": False,
        }
    contract, meta = _contract(repo, mission_ref, proposal)
    assert contract is not None
    reaction_id = contract["reaction_id"]
    index = _load_index(repo, allow_missing=True)
    state = _load_state(repo, allow_missing=True)
    origin_key = _digest(
        {
            "mission_id": meta["mission_id"],
            "fato_id": meta["trigger"]["fato_id"],
            "antagonista_id": contract["contrato"]["antagonista"]["id"],
        }
    )
    divergent = [
        rid for rid, row in index["reacoes"].items()
        if isinstance(row, dict) and row.get("chave_origem") == origin_key and rid != reaction_id
    ]
    if divergent:
        raise SidequestReactionError(
            "fato/antagonista já possui reação divergente: " + ", ".join(divergent)
        )
    if reaction_id not in index["reacoes"] and len(index["reacoes"]) >= MAX_REACTIONS:
        raise SidequestReactionError(f"índice excede {MAX_REACTIONS} reações")
    rel = _contract_rel(reaction_id)
    rendered = _yaml(contract)
    if (repo / rel).is_file():
        if (repo / rel).read_text(encoding="utf-8") != rendered:
            raise SidequestReactionError("contrato de reação existente diverge")
    else:
        _atomic(repo / rel, contract, maximum=MAX_CONTRACT_BYTES)

    index_changed = reaction_id not in index["reacoes"]
    expected_meta = {
        "reaction_id": reaction_id,
        "mission_id": meta["mission_id"],
        "quest_id": meta["quest_id"],
        "classificacao": meta["classification"],
        "chave_origem": origin_key,
        "arquivo": rel.as_posix(),
    }
    existing_meta = index["reacoes"].get(reaction_id)
    if existing_meta is not None and existing_meta != expected_meta:
        raise SidequestReactionError("índice de reação existente diverge")
    index["reacoes"][reaction_id] = expected_meta
    if len(index["reacoes"]) > MAX_REACTIONS:
        raise SidequestReactionError(f"índice excede {MAX_REACTIONS} reações")
    _atomic(repo / INDEX, index)

    now, _ = mundo.load_canonical_time(repo)
    minimum = mundo.parse_instant(
        contract["contrato"]["janela"]["minimo"]["data"],
        contract["contrato"]["janela"]["minimo"]["hora"],
    )
    initial = (
        "elegivel"
        if meta["classification"] == "reacao_mundo" and now >= minimum
        else "planejada"
    )
    expected_state = {
        "estado": initial,
        "classificacao": meta["classification"],
        "pendencia_id": None,
        "alternativas_comprometidas": [],
        "comprometida_em": None,
        "resolucao": None,
    }
    existing_state = state["reacoes"].get(reaction_id)
    if existing_state is None:
        state["reacoes"][reaction_id] = expected_state
        state["historico_recente"].append(
            {"tipo": "reacao_materializada", "reaction_id": reaction_id, "estado": initial}
        )
        state["historico_recente"] = state["historico_recente"][-MAX_HISTORY:]
    elif existing_state["classificacao"] != meta["classification"]:
        raise SidequestReactionError("estado de reação existente diverge")
    _atomic(repo / STATE, state)

    pending = None
    added = False
    effective_state = state["reacoes"][reaction_id]["estado"]
    if initial == "elegivel" and effective_state in {"planejada", "elegivel", "comprometida"}:
        pending, added = _enqueue(repo, contract)
        state = _load_state(repo)
        row = state["reacoes"][reaction_id]
        if row["pendencia_id"] not in {None, pending["id"]}:
            raise SidequestReactionError("reação aponta pendência divergente")
        if row["estado"] == "planejada":
            row["estado"] = "elegivel"
        row["pendencia_id"] = pending["id"]
        _atomic(repo / STATE, state)
    return {
        "ok": True,
        "resultado": "ja_materializada" if not index_changed else "materializada",
        "reaction_id": reaction_id,
        "mission_id": meta["mission_id"],
        "classificacao": meta["classification"],
        "estado": state["reacoes"][reaction_id]["estado"],
        "pendencia": pending,
        "pendencia_adicionada": added,
        "missao_reaberta": False,
        "contrato_task44_alterado": False,
    }


def _resource_key(actor_id: str, resource: str) -> str:
    return actor_id + ":" + hashlib.sha256(resource.encode("utf-8")).hexdigest()[:16]


def commit(repo: Path, reaction_id: str, alternative_ids: list[str]) -> dict[str, Any]:
    contract, source = _load_contract(repo, reaction_id)
    state = _load_state(repo)
    row = _map(state["reacoes"].get(reaction_id), f"estado.{reaction_id}")
    chosen = [_slug(value, "alternative_id") for value in alternative_ids]
    if not chosen or len(chosen) != len(set(chosen)):
        raise SidequestReactionError("compromisso exige alternativas únicas")
    if row["estado"] == "comprometida":
        if row["alternativas_comprometidas"] != chosen:
            raise SidequestReactionError("reação já comprometida com alternativas divergentes")
        return {
            "ok": True,
            "resultado": "ja_comprometida",
            "reaction_id": reaction_id,
            "alternativas": chosen,
        }
    if row["estado"] != "elegivel":
        raise SidequestReactionError("somente reação elegível pode ser comprometida")
    alternatives = {item["id"]: item for item in contract["contrato"]["alternativas"]}
    selected = []
    for alternative_id in chosen:
        option = alternatives.get(alternative_id)
        if not isinstance(option, dict) or option.get("estado") != "elegivel":
            raise SidequestReactionError(f"alternativa não é elegível: {alternative_id}")
        selected.append(option)
    groups = [item["grupo_exclusividade"] for item in selected if item["grupo_exclusividade"]]
    if len(groups) != len(set(groups)):
        raise SidequestReactionError(
            "alternativas mutuamente exclusivas não podem ser comprometidas juntas"
        )
    task44 = contract["contrato"]["origem_task44"]
    if _sha(repo / task44["arquivo"]) != task44["sha256"]:
        raise SidequestReactionError("contrato Task44 original mudou após avaliação")
    actor = _agent(repo, contract["contrato"]["antagonista"]["id"])
    keys: list[tuple[str, str, str]] = []
    seen_keys: set[str] = set()
    for option in selected:
        if option["capacidade_id"] not in actor["capacidades"]:
            raise SidequestReactionError(
                f"capacidade deixou de estar disponível: {option['capacidade_id']}"
            )
        if set(option["conhecimentos_requeridos"]) - set(actor["conhecimento"]):
            raise SidequestReactionError("conhecimento deixou de estar disponível")
        if option["exige_presenca_fisica"] and (
            actor["presenca"].get("estado") not in {"presente", "presente_oculto"}
            or actor["elegibilidade_local"] != "sim"
        ):
            raise SidequestReactionError("presença física deixou de ser compatível")
        consequence = {
            "titulo": option["titulo"],
            "descricao": option["resultado_possivel"],
            "gravidade": option["gravidade"],
            "reversibilidade": option["reversibilidade"],
            "classe_impacto": option["classe_impacto"],
            "alvos_npc": [target["id"] for target in option["alvos"] if target["tipo"] == "npc"],
        }
        try:
            adversarial.authorize_external_consequence(
                repo, consequence, authority="procedural"
            )
        except adversarial.AdversarialIntegrityError as exc:
            raise SidequestReactionError(str(exc)) from exc
        for resource in option["recursos_exigidos"]:
            if resource not in actor["recursos"]:
                raise SidequestReactionError(f"recurso deixou de estar disponível: {resource}")
            key = _resource_key(actor["id"], resource)
            if key in seen_keys:
                raise SidequestReactionError(
                    "o mesmo recurso exclusivo não pode servir a duas alternativas"
                )
            seen_keys.add(key)
            existing = state["recursos_comprometidos"].get(key)
            if existing is not None and existing.get("reaction_id") != reaction_id:
                raise SidequestReactionError(
                    f"recurso já comprometido por outra reação: {resource}"
                )
            keys.append((key, resource, option["id"]))
    now, _ = mundo.load_canonical_time(repo)
    for key, resource, alternative_id in keys:
        state["recursos_comprometidos"][key] = {
            "reaction_id": reaction_id,
            "alternative_id": alternative_id,
            "antagonista_id": actor["id"],
            "recurso": resource,
        }
    row["estado"] = "comprometida"
    row["alternativas_comprometidas"] = chosen
    row["comprometida_em"] = mundo.instant_parts(now)
    state["historico_recente"].append(
        {"tipo": "reacao_comprometida", "reaction_id": reaction_id, "alternativas": chosen}
    )
    state["historico_recente"] = state["historico_recente"][-MAX_HISTORY:]
    _atomic(repo / STATE, state)
    return {
        "ok": True,
        "resultado": "comprometida",
        "reaction_id": reaction_id,
        "alternativas": chosen,
        "recursos": [resource for _, resource, _ in keys],
        "contrato": source,
        "regra": "compromisso antecede narração, encontro e rolagem",
    }


def resolve(repo: Path, reaction_id: str, *, proof: Any, result: str) -> dict[str, Any]:
    _load_contract(repo, reaction_id)
    state = _load_state(repo)
    row = _map(state["reacoes"].get(reaction_id), f"estado.{reaction_id}")
    normalized_result = _text(result, "resultado", minimum=12)
    causal = _safe_proof(repo, proof, "prova_resultado")
    if row["estado"] == "resolvida":
        existing = _map(row.get("resolucao"), "resolucao")
        if existing.get("resultado") != normalized_result or existing.get("prova") != causal:
            raise SidequestReactionError("reação já resolvida com resultado divergente")
    elif row["estado"] != "comprometida":
        raise SidequestReactionError("resultado factual exige reação comprometida")
    else:
        row["estado"] = "resolvida"
        row["resolucao"] = {"resultado": normalized_result, "prova": causal}
        for key, resource in list(state["recursos_comprometidos"].items()):
            if isinstance(resource, dict) and resource.get("reaction_id") == reaction_id:
                del state["recursos_comprometidos"][key]
        state["historico_recente"].append(
            {"tipo": "reacao_resolvida", "reaction_id": reaction_id, "fonte": causal["fonte"]}
        )
        state["historico_recente"] = state["historico_recente"][-MAX_HISTORY:]
        _atomic(repo / STATE, state)
    pending_id = row.get("pendencia_id")
    world = mundo.load_world_state(repo)
    open_ids = {item.get("id") for item in world["pendencias"]}
    completed_ids = {item.get("id") for item in world["concluidas_recentes"]}
    if pending_id in open_ids:
        conclusion = mundo.conclude(
            repo, pending_id, f"reação {reaction_id} encerrada por fato canônico"
        )
        barreira_mundo.sync(repo)
    elif pending_id in completed_ids:
        conclusion = {"ja_concluida": True, "id": pending_id}
    else:
        raise SidequestReactionError("pendência da reação não está aberta nem concluída")
    return {
        "ok": True,
        "resultado": "resolvida",
        "reaction_id": reaction_id,
        "prova": causal,
        "pendencia": conclusion,
        "missao_reaberta": False,
    }


def reconcile(repo: Path, *, now: mundo.WorldInstant | None = None) -> dict[str, Any]:
    if not configured(repo):
        return {"ok": True, "configurado": False, "alterou": False, "novas_pendencias": []}
    index = _load_index(repo)
    state = _load_state(repo)
    current = now or mundo.load_canonical_time(repo)[0]
    changed = False
    pending_rows: list[dict[str, Any]] = []
    for reaction_id in sorted(index["reacoes"]):
        contract, _ = _load_contract(repo, reaction_id)
        row = _map(state["reacoes"].get(reaction_id), f"estado.{reaction_id}")
        if contract["contrato"]["classificacao"] != "reacao_mundo":
            continue
        # Uma reação reivindicada por um grupo concorrente passa a ser
        # orquestrada pela pendência única do grupo. Reenfileirá-la aqui
        # criaria duas autoridades para o mesmo compromisso adversarial.
        if row.get("grupo_operacoes_id"):
            continue
        minimum = mundo.parse_instant(
            contract["contrato"]["janela"]["minimo"]["data"],
            contract["contrato"]["janela"]["minimo"]["hora"],
        )
        if row["estado"] == "planejada" and current.minute >= minimum.minute:
            row["estado"] = "elegivel"
            changed = True
        if row["estado"] in {"elegivel", "comprometida"}:
            pending = _pending(contract)
            if row.get("pendencia_id") not in {None, pending["id"]}:
                raise SidequestReactionError("estado aponta pendência divergente")
            if row.get("pendencia_id") is None:
                row["pendencia_id"] = pending["id"]
                changed = True
            pending_rows.append(pending)
    world = mundo.load_world_state(repo)
    added = mundo._merge_pending(world, pending_rows)
    if added:
        mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, world)
        changed = True
    if changed:
        _atomic(repo / STATE, state)
    barreira_mundo.sync(repo, world)
    return {
        "ok": True,
        "configurado": True,
        "alterou": changed,
        "novas_pendencias": added,
    }


def project_pending(repo: Path, pending: dict[str, Any]) -> dict[str, Any]:
    reaction_id = _text(pending.get("reaction_id"), "pendencia.reaction_id", maximum=32)
    contract, source = _load_contract(repo, reaction_id)
    state = _load_state(repo)
    row = _map(state["reacoes"].get(reaction_id), f"estado.{reaction_id}")
    if pending.get("id") != row.get("pendencia_id"):
        raise SidequestReactionError("pendência não corresponde ao estado da reação")
    alternatives = [
        {
            key: item.get(key)
            for key in (
                "id", "tipo", "titulo", "objetivo", "alvos", "recursos_exigidos",
                "grupo_exclusividade", "gravidade", "reversibilidade", "classe_impacto",
                "estado", "motivos_bloqueio",
            )
        }
        for item in contract["contrato"]["alternativas"]
    ]
    return {
        "reaction_id": reaction_id,
        "estado": row["estado"],
        "missao": contract["contrato"]["mission_id"],
        "gatilho": {
            "tipo": contract["contrato"]["gatilho"]["tipo"],
            "fato_id": contract["contrato"]["gatilho"]["fato_id"],
        },
        "antagonista_id": contract["contrato"]["antagonista"]["id"],
        "objetivo": contract["contrato"]["antagonista"]["objetivo_atual"],
        "janela": contract["contrato"]["janela"],
        "alternativas": alternatives,
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), source],
    }


def status(repo: Path, reaction_id: str | None = None) -> dict[str, Any]:
    if not configured(repo):
        return {"ok": True, "configurado": False, "reacoes": 0}
    index = _load_index(repo)
    state = _load_state(repo)
    if reaction_id is not None:
        contract, source = _load_contract(repo, reaction_id)
        return {
            "ok": True,
            "configurado": True,
            "reaction_id": reaction_id,
            "estado": copy.deepcopy(state["reacoes"][reaction_id]),
            "contrato": copy.deepcopy(contract["contrato"]),
            "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), source],
        }
    counts = {name: 0 for name in REACTION_STATES}
    for row in state["reacoes"].values():
        if isinstance(row, dict) and row.get("estado") in counts:
            counts[row["estado"]] += 1
    return {
        "ok": True,
        "configurado": True,
        "reacoes": len(index["reacoes"]),
        "por_estado": counts,
        "recursos_comprometidos": len(state["recursos_comprometidos"]),
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix()],
    }


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    count = 0
    if configured(repo):
        try:
            if not (repo / INDEX).is_file() or not (repo / STATE).is_file():
                raise SidequestReactionError("índice e estado de reações devem existir juntos")
            index = _load_index(repo)
            state = _load_state(repo)
            if set(index["reacoes"]) != set(state["reacoes"]):
                raise SidequestReactionError("índice e estado possuem reações divergentes")
            if len(index["reacoes"]) > MAX_REACTIONS:
                raise SidequestReactionError("orçamento de reações excedido")
            origins: set[str] = set()
            world = mundo.load_world_state(repo)
            pending_by_id = {item.get("id"): item for item in world["pendencias"]}
            for reaction_id, meta in index["reacoes"].items():
                if not REACTION_RE.fullmatch(reaction_id):
                    raise SidequestReactionError(f"reaction_id inválido: {reaction_id}")
                row = _map(meta, f"indice.{reaction_id}")
                origin = _text(row.get("chave_origem"), f"{reaction_id}.chave_origem")
                if origin in origins:
                    raise SidequestReactionError("chave causal de reação duplicada")
                origins.add(origin)
                contract, source = _load_contract(repo, reaction_id)
                if len((repo / source).read_bytes()) > MAX_CONTRACT_BYTES:
                    raise SidequestReactionError(f"contrato excede orçamento: {reaction_id}")
                task44 = contract["contrato"]["origem_task44"]
                if _sha(repo / task44["arquivo"]) != task44["sha256"]:
                    raise SidequestReactionError(
                        f"contrato Task44 original divergiu: {reaction_id}"
                    )
                current = _map(state["reacoes"][reaction_id], f"estado.{reaction_id}")
                if current.get("estado") not in REACTION_STATES:
                    raise SidequestReactionError(f"estado de reação inválido: {reaction_id}")
                if current["estado"] in {"elegivel", "comprometida"}:
                    pending_id = current.get("pendencia_id")
                    if pending_id not in pending_by_id:
                        raise SidequestReactionError(
                            f"reação ativa sem pendência do Mundo Vivo: {reaction_id}"
                        )
            for key, reservation in state["recursos_comprometidos"].items():
                reservation = _map(reservation, f"recursos.{key}")
                rid = reservation.get("reaction_id")
                if rid not in state["reacoes"] or state["reacoes"][rid]["estado"] != "comprometida":
                    raise SidequestReactionError(f"recurso órfão ou não comprometido: {key}")
            count = len(index["reacoes"])
        except (SidequestReactionError, mundo.WorldEngineError, OSError, yaml.YAMLError) as exc:
            errors.append(str(exc))
    return {
        "ok": not errors,
        "configurado": configured(repo),
        "erros": errors,
        "reacoes": count,
        "contrato": {
            "max_reacoes": MAX_REACTIONS,
            "max_alternativas": MAX_ALTERNATIVES,
            "max_alvos": MAX_TARGETS,
            "max_recursos": MAX_RESOURCES,
            "contrato_bytes_max": MAX_CONTRACT_BYTES,
            "preparacao_bytes_max": MAX_PREP_BYTES,
            "scheduler_novo": 0,
            "rng_novo": 0,
            "scan_global": 0,
        },
    }


def _stdin() -> Any:
    try:
        return yaml.safe_load(sys.stdin.read())
    except yaml.YAMLError as exc:
        raise SidequestReactionError(str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    prep = sub.add_parser("preparar")
    prep.add_argument("missao")
    material = sub.add_parser("materializar")
    material.add_argument("missao")
    material.add_argument("--preparacao-id", required=True)
    commit_parser = sub.add_parser("comprometer")
    commit_parser.add_argument("reaction_id")
    commit_parser.add_argument("alternativas", nargs="+")
    resolve_parser = sub.add_parser("resolver")
    resolve_parser.add_argument("reaction_id")
    resolve_parser.add_argument("--resultado", required=True)
    show = sub.add_parser("status")
    show.add_argument("reaction_id", nargs="?")
    sub.add_parser("reconciliar")
    sub.add_parser("check")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "preparar":
            result = prepare(repo, args.missao, _stdin())
        elif args.cmd == "materializar":
            result = materialize(
                repo, args.missao, _stdin(), preparation_id=args.preparacao_id
            )
        elif args.cmd == "comprometer":
            result = commit(repo, args.reaction_id, args.alternativas)
        elif args.cmd == "resolver":
            result = resolve(repo, args.reaction_id, proof=_stdin(), result=args.resultado)
        elif args.cmd == "status":
            result = status(repo, args.reaction_id)
        elif args.cmd == "reconciliar":
            result = reconcile(repo)
        else:
            result = check(repo)
        print(_yaml(result), end="")
        return 0 if result.get("ok", True) else 1
    except (SidequestReactionError, mundo.WorldEngineError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
