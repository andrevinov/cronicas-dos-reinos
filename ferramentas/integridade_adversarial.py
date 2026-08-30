#!/usr/bin/env python3
"""Task 44 — Adversarial Integrity & Consequence Authority.

Antagonistas perseguem objetivos com as capacidades, conhecimento e restrições que
realmente possuem. Sidequests emergentes recebem um contrato adversarial reservado
antes do aceite; consequências posteriores precisam apontar para uma escalada desse
contrato e para evidência canônica de que sua condição ocorreu.

A camada também classifica autoridade de consequência sobre o Protected Core:
procedural e sidequest lateral continuam sob o guardrail antigo; sidequest
canônica, evento canônico, ação de Ren e combate resolvido podem criar risco real,
mas somente com a autoridade/evidência exigidas. Proteção contra arbitrariedade não
é proteção contra consequência.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml

import agentes
import canon_bridge
import oportunidades
import rede_protegida
import sidequests_emergentes as emergent

POLICY = Path("narrador/mundo/autoridade-consequencias.yaml")
CONTRACTS_DIR = Path("narrador/sidequests-emergentes/stakes")
SCHEMA = 1
MAX_CONTRACT_BYTES = 24 * 1024
MAX_PREP_BYTES = 8 * 1024
MAX_HISTORY = 24
MAX_OBJECTIVES = 8
MAX_CAPABILITIES = 16
MAX_KNOWLEDGE = 16
MAX_ESCALATIONS = 12
MAX_RISK_TARGETS = 10
MAX_TEXT = 520
MAX_EVIDENCE = 360

SEVERITIES = ("leve", "moderada", "grave")
SEVERITY_RANK = {name: idx for idx, name in enumerate(SEVERITIES)}
REVERSIBILITY = set(rede_protegida.REVERSIBILITY)
IMPACT_CLASSES = set(rede_protegida.IMPACT_CLASSES)
AUTHORITIES = {
    "procedural",
    "sidequest_lateral",
    "sidequest_canonica",
    "evento_canonico",
    "acao_de_ren",
    "combate_resolvido",
}
PRIORITIES = {"possivel", "preferencial", "obrigatoria_se_condicao"}
RISK_TARGET_TYPES = {
    "npc", "instituicao", "recurso", "propriedade", "informacao", "oportunidade", "outro"
}
CAPABILITY_SOURCES = {"agente", "quest"}
KNOWLEDGE_SOURCES = {"agente", "quest"}
FORBIDDEN_PROOF_PREFIXES = (
    "narrador/sidequests-emergentes/",
    "narrador/arcos/parte_1/intencoes/",
    "narrador/arcos/parte_1/eventos/",
)
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_:-]{0,95}$")


class AdversarialIntegrityError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise AdversarialIntegrityError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AdversarialIntegrityError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise AdversarialIntegrityError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str, *, minimum: int = 1, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise AdversarialIntegrityError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if len(result) < minimum:
        raise AdversarialIntegrityError(f"{label} deve ter ao menos {minimum} caracteres")
    if len(result) > maximum:
        raise AdversarialIntegrityError(f"{label} excede {maximum} caracteres")
    return result


def _id(value: Any, label: str) -> str:
    result = _text(value, label, maximum=128)
    if not ID_RE.fullmatch(result):
        raise AdversarialIntegrityError(f"{label} deve ser id ASCII minúsculo estável")
    return result


def _slug(value: Any, label: str) -> str:
    result = _text(value, label, maximum=96)
    if not SLUG_RE.fullmatch(result):
        raise AdversarialIntegrityError(f"{label} deve ser slug ASCII minúsculo")
    return result


def _yaml_bytes(value: Any) -> bytes:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8")


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _atomic(path: Path, data: dict[str, Any]) -> None:
    rendered = _yaml_bytes(data)
    if len(rendered) > MAX_CONTRACT_BYTES:
        raise AdversarialIntegrityError(
            f"contrato Task44 excede {MAX_CONTRACT_BYTES} bytes: {len(rendered)}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "wb", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
        tmp = Path(handle.name)
    os.replace(tmp, path)


def _contract_path(quest_id: str) -> Path:
    if not re.fullmatch(r"qse-[0-9a-f]{16}", quest_id):
        raise AdversarialIntegrityError("quest_id emergente inválido")
    return CONTRACTS_DIR / f"{quest_id}.yaml"


def load_policy(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / POLICY), POLICY.as_posix())
    if set(data) != {
        "schema_autoridade_consequencias", "natureza", "regra_fundamental",
        "regra_nao_amaciar", "autoridades", "invariantes"
    }:
        raise AdversarialIntegrityError("política Task44 possui estrutura inesperada")
    if data["schema_autoridade_consequencias"] != SCHEMA:
        raise AdversarialIntegrityError("schema da autoridade de consequências inválido")
    if data["natureza"] != "guardrail_reservado":
        raise AdversarialIntegrityError("natureza da autoridade de consequências inválida")
    _text(data["regra_fundamental"], "regra_fundamental")
    _text(data["regra_nao_amaciar"], "regra_nao_amaciar")
    authorities = _map(data["autoridades"], "autoridades")
    if set(authorities) != AUTHORITIES:
        raise AdversarialIntegrityError("política deve declarar exatamente as seis autoridades Task44")
    for authority, raw in authorities.items():
        meta = _map(raw, f"autoridades.{authority}")
        if set(meta) != {"nucleo_protegido", "exige_evidencia_canonica", "exige_vinculo_task42"}:
            raise AdversarialIntegrityError(f"autoridade {authority} possui campos inesperados")
        if meta["nucleo_protegido"] not in {
            "guardrail_procedural", "risco_real_condicionado", "risco_real"
        }:
            raise AdversarialIntegrityError(f"autoridade {authority}: política de núcleo inválida")
        if not isinstance(meta["exige_evidencia_canonica"], bool):
            raise AdversarialIntegrityError(f"autoridade {authority}: exige_evidencia_canonica inválido")
        if not isinstance(meta["exige_vinculo_task42"], bool):
            raise AdversarialIntegrityError(f"autoridade {authority}: exige_vinculo_task42 inválido")
    invariants = _map(data["invariantes"], "invariantes")
    if not invariants or not all(value is True for value in invariants.values()):
        raise AdversarialIntegrityError("invariantes Task44 devem permanecer verdadeiras")
    return data


def _safe_proof(repo: Path, raw: Any, label: str) -> dict[str, str]:
    proof = _map(raw, label)
    if set(proof) != {"fonte", "evidencia"}:
        raise AdversarialIntegrityError(f"{label} exige fonte e evidencia")
    source = _text(proof["fonte"], f"{label}.fonte", maximum=240)
    rel = Path(source)
    if rel.is_absolute() or ".." in rel.parts:
        raise AdversarialIntegrityError(f"{label}.fonte deve ficar dentro do repo")
    posix = rel.as_posix()
    if any(posix.startswith(prefix) for prefix in FORBIDDEN_PROOF_PREFIXES):
        raise AdversarialIntegrityError(
            f"{label}.fonte não pode usar planejamento reservado como prova causal"
        )
    path = repo / rel
    if not path.is_file():
        raise AdversarialIntegrityError(f"fonte causal inexistente: {posix}")
    evidence = _text(proof["evidencia"], f"{label}.evidencia", maximum=MAX_EVIDENCE)
    haystack = " ".join(path.read_text(encoding="utf-8").split())
    if evidence not in haystack:
        raise AdversarialIntegrityError(f"evidência causal não é literal em {posix}")
    return {"fonte": posix, "evidencia": evidence}


def _flatten_methods(agent: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    groups = agent.get("metodos_operacionais") or {}
    if not isinstance(groups, dict):
        return result
    for objective, entries in groups.items():
        if not isinstance(entries, list):
            continue
        for raw in entries:
            if not isinstance(raw, dict) or not isinstance(raw.get("id"), str):
                continue
            cid = raw["id"]
            if cid in result:
                raise AdversarialIntegrityError(f"capacidade duplicada no agente: {cid}")
            result[cid] = {
                "id": cid,
                "objetivo_operacional": str(objective),
                "abordagem": raw.get("abordagem"),
                "modalidade": raw.get("modalidade"),
                "tags": list(raw.get("tags") or []),
            }
    return result


def _agent_snapshot(repo: Path, actor_id: str) -> dict[str, Any] | None:
    try:
        loaded = agentes.load_agent(repo, actor_id)
    except agentes.AgentValidationError as exc:
        if "agente não encontrado" in str(exc):
            return None
        raise AdversarialIntegrityError(str(exc)) from exc
    agent = loaded["resultado"]
    knowledge = {
        str(item["id"]): copy.deepcopy(item)
        for item in (agent.get("conhecimento") or [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    autonomy = agent.get("autonomia_estrategica") or {}
    conditional = {}
    if isinstance(autonomy, dict):
        for raw in autonomy.get("escaladas_condicionais") or []:
            if isinstance(raw, dict) and isinstance(raw.get("id"), str):
                conditional[raw["id"]] = copy.deepcopy(raw)
    return {
        "id": actor_id,
        "objetivo_atual": agent.get("objetivo_atual"),
        "recursos": list(agent.get("recursos") or []),
        "restricoes": list(agent.get("restricoes") or []),
        "capacidades": _flatten_methods(agent),
        "conhecimento": knowledge,
        "escaladas_condicionais": conditional,
        "fontes_lidas": loaded["fontes_lidas"],
    }


def agent_option(
    repo: Path,
    actor_id: str,
    capability_id: str,
    *,
    required_knowledge: list[str] | None = None,
) -> dict[str, Any]:
    """Gate de competência: método inexistente ou segredo desconhecido nunca vira opção."""
    actor_id = _slug(actor_id, "actor_id")
    capability_id = _slug(capability_id, "capability_id")
    snapshot = _agent_snapshot(repo, actor_id)
    if snapshot is None:
        return {
            "permitida": False,
            "motivo": "ator_nao_e_agente_estrategico",
            "actor_id": actor_id,
            "capability_id": capability_id,
            "fontes_lidas": [agentes.INDEX_PATH.as_posix()],
        }
    required = [_slug(item, "required_knowledge") for item in (required_knowledge or [])]
    missing = sorted(set(required) - set(snapshot["conhecimento"]))
    if capability_id not in snapshot["capacidades"]:
        return {
            "permitida": False,
            "motivo": "capacidade_nao_disponivel",
            "actor_id": actor_id,
            "capability_id": capability_id,
            "conhecimento_ausente": missing,
            "fontes_lidas": snapshot["fontes_lidas"],
        }
    if missing:
        return {
            "permitida": False,
            "motivo": "conhecimento_canonico_ausente",
            "actor_id": actor_id,
            "capability_id": capability_id,
            "conhecimento_ausente": missing,
            "fontes_lidas": snapshot["fontes_lidas"],
        }
    return {
        "permitida": True,
        "motivo": "capacidade_e_conhecimento_disponiveis",
        "actor_id": actor_id,
        "capability": copy.deepcopy(snapshot["capacidades"][capability_id]),
        "fontes_lidas": snapshot["fontes_lidas"],
    }


def agent_conditional_escalation(
    repo: Path,
    actor_id: str,
    escalation_id: str,
    *,
    proof: Any | None = None,
) -> dict[str, Any]:
    """Escalada forte só entra no espaço de opções quando seu gatilho é demonstrado."""
    actor_id = _slug(actor_id, "actor_id")
    escalation_id = _slug(escalation_id, "escalation_id")
    snapshot = _agent_snapshot(repo, actor_id)
    if snapshot is None or escalation_id not in snapshot["escaladas_condicionais"]:
        return {
            "permitida": False,
            "motivo": "escalada_nao_declarada_pelo_agente",
            "actor_id": actor_id,
            "escalation_id": escalation_id,
            "fontes_lidas": snapshot["fontes_lidas"] if snapshot else [agentes.INDEX_PATH.as_posix()],
        }
    if proof is None:
        return {
            "permitida": False,
            "motivo": "gatilho_nao_demonstrado",
            "actor_id": actor_id,
            "escalation_id": escalation_id,
            "escalada": copy.deepcopy(snapshot["escaladas_condicionais"][escalation_id]),
            "fontes_lidas": snapshot["fontes_lidas"],
        }
    causal = _safe_proof(repo, proof, "prova_gatilho")
    return {
        "permitida": True,
        "motivo": "gatilho_causal_demonstrado",
        "actor_id": actor_id,
        "escalation_id": escalation_id,
        "escalada": copy.deepcopy(snapshot["escaladas_condicionais"][escalation_id]),
        "prova": causal,
        "fontes_lidas": [*snapshot["fontes_lidas"], causal["fonte"]],
    }


def _quest_text(spec: dict[str, Any]) -> str:
    return " ".join(yaml.safe_dump(spec, allow_unicode=True, sort_keys=True).split())


def _actor_meta(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {
        item["id"]: {**copy.deepcopy(item), "origem": "antagonista"}
        for item in spec["antagonistas"]
    }
    for item in spec["juppongatana"]:
        result[item["id"]] = {**copy.deepcopy(item), "origem": "juppongatana"}
    return result


def _normalize_objectives(raw: Any, actors: dict[str, dict[str, Any]]) -> list[dict[str, str]]:
    items = _list(raw, "objetivos_antagonistas")
    if not 1 <= len(items) <= MAX_OBJECTIVES:
        raise AdversarialIntegrityError("objetivos_antagonistas fora do orçamento")
    result, seen = [], set()
    for pos, item in enumerate(items):
        data = _map(item, f"objetivos_antagonistas[{pos}]")
        if set(data) != {"antagonista_id", "objetivo"}:
            raise AdversarialIntegrityError("objetivo antagonista exige antagonista_id e objetivo")
        aid = _slug(data["antagonista_id"], f"objetivos[{pos}].antagonista_id")
        if aid not in actors or aid in seen:
            raise AdversarialIntegrityError(f"objetivo referencia antagonista inválido/duplicado: {aid}")
        seen.add(aid)
        objective = _text(data["objetivo"], f"objetivos[{pos}].objetivo")
        original = actors[aid]
        if original.get("origem") == "antagonista" and objective != original.get("objetivo"):
            raise AdversarialIntegrityError(
                f"objetivo Task44 de {aid} deve preservar o objetivo congelado na Task41"
            )
        result.append({"antagonista_id": aid, "objetivo": objective})
    if seen != set(actors):
        raise AdversarialIntegrityError(
            "contrato adversarial precisa declarar objetivo para todo antagonista/Juppongatana da quest"
        )
    return result


def _normalize_capabilities(
    repo: Path,
    raw: Any,
    actors: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, set[str]], list[str]]:
    items = _list(raw, "capacidades_disponiveis")
    if not 1 <= len(items) <= MAX_CAPABILITIES:
        raise AdversarialIntegrityError("capacidades_disponiveis fora do orçamento")
    result: list[dict[str, Any]] = []
    by_actor: dict[str, set[str]] = {aid: set() for aid in actors}
    sources: list[str] = []
    snapshots: dict[str, dict[str, Any] | None] = {}
    seen: set[tuple[str, str]] = set()
    for pos, item in enumerate(items):
        data = _map(item, f"capacidades_disponiveis[{pos}]")
        if set(data) != {"antagonista_id", "capacidade_id", "fonte", "descricao"}:
            raise AdversarialIntegrityError(
                "capacidade exige antagonista_id, capacidade_id, fonte e descricao"
            )
        aid = _slug(data["antagonista_id"], f"capacidades[{pos}].antagonista_id")
        cid = _slug(data["capacidade_id"], f"capacidades[{pos}].capacidade_id")
        source = _text(data["fonte"], f"capacidades[{pos}].fonte", maximum=16)
        if aid not in actors or source not in CAPABILITY_SOURCES or (aid, cid) in seen:
            raise AdversarialIntegrityError(f"capacidade inválida/duplicada: {aid}:{cid}")
        seen.add((aid, cid))
        if aid not in snapshots:
            snapshots[aid] = _agent_snapshot(repo, aid)
            if snapshots[aid] is not None:
                sources.extend(snapshots[aid]["fontes_lidas"])
        snapshot = snapshots[aid]
        if snapshot is not None:
            if source != "agente" or cid not in snapshot["capacidades"]:
                raise AdversarialIntegrityError(
                    f"agente estratégico {aid} não pode receber capacidade inventada pela quest: {cid}"
                )
        elif source != "quest":
            raise AdversarialIntegrityError(
                f"ator não estratégico {aid} deve declarar capacidade como fonte quest"
            )
        description = _text(data["descricao"], f"capacidades[{pos}].descricao")
        result.append({
            "antagonista_id": aid,
            "capacidade_id": cid,
            "fonte": source,
            "descricao": description,
        })
        by_actor[aid].add(cid)
    for aid in actors:
        if not by_actor[aid]:
            raise AdversarialIntegrityError(f"antagonista sem capacidade disponível: {aid}")
    return result, by_actor, list(dict.fromkeys(sources))


def _normalize_knowledge(
    repo: Path,
    raw: Any,
    actors: dict[str, dict[str, Any]],
    quest_text: str,
) -> tuple[list[dict[str, Any]], dict[str, set[str]], list[str]]:
    items = _list(raw, "conhecimentos_disponiveis")
    if len(items) > MAX_KNOWLEDGE:
        raise AdversarialIntegrityError("conhecimentos_disponiveis excede orçamento")
    result: list[dict[str, Any]] = []
    by_actor: dict[str, set[str]] = {aid: set() for aid in actors}
    sources: list[str] = []
    snapshots: dict[str, dict[str, Any] | None] = {}
    seen: set[tuple[str, str]] = set()
    for pos, item in enumerate(items):
        data = _map(item, f"conhecimentos_disponiveis[{pos}]")
        if set(data) != {"antagonista_id", "conhecimento_id", "fonte", "evidencia"}:
            raise AdversarialIntegrityError(
                "conhecimento exige antagonista_id, conhecimento_id, fonte e evidencia"
            )
        aid = _slug(data["antagonista_id"], f"conhecimentos[{pos}].antagonista_id")
        kid = _slug(data["conhecimento_id"], f"conhecimentos[{pos}].conhecimento_id")
        source = _text(data["fonte"], f"conhecimentos[{pos}].fonte", maximum=16)
        if aid not in actors or source not in KNOWLEDGE_SOURCES or (aid, kid) in seen:
            raise AdversarialIntegrityError(f"conhecimento inválido/duplicado: {aid}:{kid}")
        seen.add((aid, kid))
        evidence = _text(data["evidencia"], f"conhecimentos[{pos}].evidencia", maximum=MAX_EVIDENCE)
        if aid not in snapshots:
            snapshots[aid] = _agent_snapshot(repo, aid)
            if snapshots[aid] is not None:
                sources.extend(snapshots[aid]["fontes_lidas"])
        snapshot = snapshots[aid]
        if snapshot is not None:
            if source != "agente" or kid not in snapshot["conhecimento"]:
                raise AdversarialIntegrityError(
                    f"agente estratégico {aid} não pode conhecer segredo não registrado: {kid}"
                )
            canonical = snapshot["conhecimento"][kid]
            if evidence != canonical.get("fato"):
                raise AdversarialIntegrityError(
                    f"evidencia de conhecimento {aid}:{kid} deve reproduzir o fato canônico do agente"
                )
        else:
            if source != "quest" or evidence not in quest_text:
                raise AdversarialIntegrityError(
                    f"conhecimento autoral {aid}:{kid} precisa de evidência literal na própria quest"
                )
        result.append({
            "antagonista_id": aid,
            "conhecimento_id": kid,
            "fonte": source,
            "evidencia": evidence,
        })
        by_actor[aid].add(kid)
    return result, by_actor, list(dict.fromkeys(sources))


def _normalize_risk_targets(raw: Any, spec: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    items = _list(raw, "alvos_em_risco")
    if not 1 <= len(items) <= MAX_RISK_TARGETS:
        raise AdversarialIntegrityError("alvos_em_risco fora do orçamento")
    quest_npcs = {
        item["id"] for item in [*spec["npcs_existentes"], *spec["npcs_novos"]]
    }
    result: list[dict[str, Any]] = []
    maximum: dict[str, str] = {}
    for pos, item in enumerate(items):
        data = _map(item, f"alvos_em_risco[{pos}]")
        if set(data) != {"id", "tipo", "gravidade_maxima", "descricao"}:
            raise AdversarialIntegrityError(
                "alvo em risco exige id, tipo, gravidade_maxima e descricao"
            )
        rid = _id(data["id"], f"alvos_em_risco[{pos}].id")
        kind = _text(data["tipo"], f"alvos_em_risco[{pos}].tipo", maximum=24)
        severity = _text(data["gravidade_maxima"], f"alvos_em_risco[{pos}].gravidade_maxima", maximum=16)
        if rid in maximum or kind not in RISK_TARGET_TYPES or severity not in SEVERITY_RANK:
            raise AdversarialIntegrityError(f"alvo em risco inválido/duplicado: {rid}")
        if kind == "npc" and rid not in quest_npcs:
            raise AdversarialIntegrityError(
                f"NPC em risco precisa estar declarado no elenco Task41: {rid}"
            )
        maximum[rid] = severity
        result.append({
            "id": rid,
            "tipo": kind,
            "gravidade_maxima": severity,
            "descricao": _text(data["descricao"], f"alvos_em_risco[{pos}].descricao"),
        })
    return result, maximum


def _normalize_escalations(
    raw: Any,
    actors: dict[str, dict[str, Any]],
    capabilities: dict[str, set[str]],
    knowledge: dict[str, set[str]],
    risk_max: dict[str, str],
    global_max: str,
) -> list[dict[str, Any]]:
    items = _list(raw, "escaladas_possiveis")
    if not 1 <= len(items) <= MAX_ESCALATIONS:
        raise AdversarialIntegrityError("escaladas_possiveis fora do orçamento")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pos, item in enumerate(items):
        data = _map(item, f"escaladas_possiveis[{pos}]")
        expected = {
            "id", "antagonista_id", "condicao", "capacidade_id",
            "conhecimentos_requeridos", "alvos", "gravidade", "reversibilidade",
            "classe_impacto", "consequencia", "prioridade", "bloqueios_causais",
        }
        if set(data) != expected:
            raise AdversarialIntegrityError(f"escalada[{pos}] possui estrutura inválida")
        eid = _slug(data["id"], f"escaladas[{pos}].id")
        aid = _slug(data["antagonista_id"], f"escaladas[{pos}].antagonista_id")
        cid = _slug(data["capacidade_id"], f"escaladas[{pos}].capacidade_id")
        if eid in seen or aid not in actors or cid not in capabilities.get(aid, set()):
            raise AdversarialIntegrityError(f"escalada inválida/duplicada: {eid}")
        seen.add(eid)
        required = [
            _slug(value, f"escaladas[{pos}].conhecimentos_requeridos")
            for value in _list(data["conhecimentos_requeridos"], f"escaladas[{pos}].conhecimentos_requeridos")
        ]
        missing = sorted(set(required) - knowledge.get(aid, set()))
        if missing:
            raise AdversarialIntegrityError(
                f"{eid}: antagonista não conhece {', '.join(missing)}; vilania não concede onisciência"
            )
        targets = [
            _id(value, f"escaladas[{pos}].alvos")
            for value in _list(data["alvos"], f"escaladas[{pos}].alvos")
        ]
        if not targets or len(targets) != len(set(targets)) or set(targets) - set(risk_max):
            raise AdversarialIntegrityError(f"{eid}: alvos devem vir de alvos_em_risco")
        severity = _text(data["gravidade"], f"escaladas[{pos}].gravidade", maximum=16)
        reversibility = _text(data["reversibilidade"], f"escaladas[{pos}].reversibilidade", maximum=16)
        impact = _text(data["classe_impacto"], f"escaladas[{pos}].classe_impacto", maximum=24)
        priority = _text(data["prioridade"], f"escaladas[{pos}].prioridade", maximum=32)
        if severity not in SEVERITY_RANK or reversibility not in REVERSIBILITY or impact not in IMPACT_CLASSES:
            raise AdversarialIntegrityError(f"{eid}: classificação de consequência inválida")
        if priority not in PRIORITIES:
            raise AdversarialIntegrityError(f"{eid}: prioridade inválida")
        if SEVERITY_RANK[severity] > SEVERITY_RANK[global_max]:
            raise AdversarialIntegrityError(f"{eid}: excede gravidade_maxima_causal da quest")
        for target in targets:
            if SEVERITY_RANK[severity] > SEVERITY_RANK[risk_max[target]]:
                raise AdversarialIntegrityError(
                    f"{eid}: gravidade excede teto causal declarado para {target}"
                )
        blockers = [
            _text(value, f"escaladas[{pos}].bloqueios_causais[{idx}]")
            for idx, value in enumerate(_list(data["bloqueios_causais"], f"escaladas[{pos}].bloqueios_causais"))
        ]
        result.append({
            "id": eid,
            "antagonista_id": aid,
            "condicao": _text(data["condicao"], f"escaladas[{pos}].condicao"),
            "capacidade_id": cid,
            "conhecimentos_requeridos": required,
            "alvos": targets,
            "gravidade": severity,
            "reversibilidade": reversibility,
            "classe_impacto": impact,
            "consequencia": _text(data["consequencia"], f"escaladas[{pos}].consequencia"),
            "prioridade": priority,
            "bloqueios_causais": blockers,
        })
    return result


def normalize_contract(
    repo: Path,
    package_raw: Any,
    quest_raw: Any,
    contract_raw: Any,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], list[str]]:
    """Valida o contrato Task44 sem escrever."""
    try:
        package, spec, base_sources = emergent.normalize_spec(repo, package_raw, quest_raw)
    except emergent.EmergentSidequestAuthoringError as exc:
        raise AdversarialIntegrityError(str(exc)) from exc
    contract = copy.deepcopy(_map(contract_raw, "contrato_adversarial"))
    expected = {
        "objetivos_antagonistas", "capacidades_disponiveis", "conhecimentos_disponiveis",
        "estado_se_ren_nao_intervier", "escaladas_possiveis", "consequencias_de_falha",
        "consequencias_de_inacao", "alvos_em_risco", "gravidade_maxima_causal",
    }
    if set(contract) != expected:
        raise AdversarialIntegrityError(
            f"schema contrato_adversarial divergente; faltando={sorted(expected-set(contract))}; extras={sorted(set(contract)-expected)}"
        )
    actors = _actor_meta(spec)
    if not actors:
        raise AdversarialIntegrityError("Task44 exige ao menos um antagonista")
    objectives = _normalize_objectives(contract["objetivos_antagonistas"], actors)
    capabilities, capability_map, capability_sources = _normalize_capabilities(
        repo, contract["capacidades_disponiveis"], actors
    )
    quest_text = _quest_text(spec)
    knowledge, knowledge_map, knowledge_sources = _normalize_knowledge(
        repo, contract["conhecimentos_disponiveis"], actors, quest_text
    )
    risk_targets, risk_max = _normalize_risk_targets(contract["alvos_em_risco"], spec)
    global_max = _text(contract["gravidade_maxima_causal"], "gravidade_maxima_causal", maximum=16)
    if global_max not in SEVERITY_RANK:
        raise AdversarialIntegrityError("gravidade_maxima_causal deve ser leve, moderada ou grave")
    escalations = _normalize_escalations(
        contract["escaladas_possiveis"], actors, capability_map, knowledge_map, risk_max, global_max
    )
    escalation_ids = {item["id"] for item in escalations}
    def refs(raw: Any, label: str) -> list[str]:
        values = [_slug(value, label) for value in _list(raw, label)]
        if len(values) != len(set(values)) or set(values) - escalation_ids:
            raise AdversarialIntegrityError(f"{label} deve referenciar escaladas únicas existentes")
        return values
    failure = refs(contract["consequencias_de_falha"], "consequencias_de_falha")
    inaction = refs(contract["consequencias_de_inacao"], "consequencias_de_inacao")
    if not failure and not inaction:
        raise AdversarialIntegrityError(
            "contrato adversarial precisa declarar consequência de falha ou de inação"
        )
    normalized = {
        "objetivos_antagonistas": objectives,
        "capacidades_disponiveis": capabilities,
        "conhecimentos_disponiveis": knowledge,
        "estado_se_ren_nao_intervier": _text(
            contract["estado_se_ren_nao_intervier"], "estado_se_ren_nao_intervier"
        ),
        "escaladas_possiveis": escalations,
        "consequencias_de_falha": failure,
        "consequencias_de_inacao": inaction,
        "alvos_em_risco": risk_targets,
        "gravidade_maxima_causal": global_max,
    }
    sources = list(dict.fromkeys([*base_sources, *capability_sources, *knowledge_sources, POLICY.as_posix()]))
    load_policy(repo)
    return package, spec, normalized, sources


def _prep_id(quest_id: str, contract: dict[str, Any], sources: list[str], repo: Path) -> str:
    fingerprints = []
    for source in sorted(dict.fromkeys(sources)):
        path = repo / source
        fingerprints.append({
            "fonte": source,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
        })
    return "adv-prep-" + _digest({
        "quest_id": quest_id,
        "contrato": contract,
        "fontes": fingerprints,
    })[:24]


def prepare(
    repo: Path,
    *,
    package: Any,
    quest: Any,
    contract: Any,
) -> dict[str, Any]:
    package_n, spec, normalized, sources = normalize_contract(repo, package, quest, contract)
    qid = emergent._quest_id(package_n, spec)
    prep = _prep_id(qid, normalized, sources, repo)
    result = {
        "ok": True,
        "fase": "preparacao_adversarial",
        "read_only": True,
        "mutacoes_aplicadas": False,
        "quest_id": qid,
        "mission_id": emergent.mission_id(qid),
        "preparacao_id": prep,
        "gravidade_maxima_causal": normalized["gravidade_maxima_causal"],
        "resumo": {
            "antagonistas": len(normalized["objetivos_antagonistas"]),
            "capacidades": len(normalized["capacidades_disponiveis"]),
            "conhecimentos": len(normalized["conhecimentos_disponiveis"]),
            "escaladas": len(normalized["escaladas_possiveis"]),
            "alvos_em_risco": len(normalized["alvos_em_risco"]),
        },
        "regra": (
            "o contrato congela trajetória adversarial antes do aceite; preparar não executa "
            "ameaça, dano, morte, captura, perda nem ação de Ren"
        ),
        "fontes_lidas": sources,
    }
    size = len(_yaml_bytes(result))
    if size > MAX_PREP_BYTES:
        raise AdversarialIntegrityError(
            f"preparação Task44 excede {MAX_PREP_BYTES} bytes: {size}"
        )
    result["orcamento_saida"] = {"bytes": size, "max_bytes": MAX_PREP_BYTES}
    return result


def _mission(repo: Path, mission_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise AdversarialIntegrityError(str(exc)) from exc
    mission = state["missoes"].get(mission_id)
    if not isinstance(mission, dict) or mission.get("origem") != "sidequest_emergente":
        raise AdversarialIntegrityError(f"sidequest emergente inexistente: {mission_id}")
    return state, mission


def materialize(
    repo: Path,
    *,
    package: Any,
    quest: Any,
    contract: Any,
    preparation_id: str,
) -> dict[str, Any]:
    prepared = prepare(repo, package=package, quest=quest, contract=contract)
    if prepared["preparacao_id"] != preparation_id:
        raise AdversarialIntegrityError("preparação Task44 obsoleta/divergente")
    qid = prepared["quest_id"]
    mid = prepared["mission_id"]
    _, mission = _mission(repo, mid)
    quest_path = repo / str(mission.get("arquivo"))
    if not quest_path.is_file() or mission.get("quest_id") != qid:
        raise AdversarialIntegrityError("Task44 só materializa depois da Task41")
    _, _, normalized, sources = normalize_contract(repo, package, quest, contract)
    doc = {
        "schema_integridade_adversarial": SCHEMA,
        "natureza": "reservado",
        "quest_id": qid,
        "mission_id": mid,
        "preparacao_id": preparation_id,
        "contrato_digest": _digest(normalized),
        "contrato": normalized,
        "guardrails": {
            "sem_plot_armor_por_conveniencia": True,
            "sem_onisciencia_de_antagonista": True,
            "sem_escalada_sem_capacidade": True,
            "sem_amaciamento_de_escalada_obrigatoria": True,
            "consequencia_real_exige_evidencia_causal": True,
            "execucao_terminal_reservada_task45": True,
        },
        "historico_recente": [],
    }
    path = repo / _contract_path(qid)
    rendered = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
    if path.exists():
        if path.read_text(encoding="utf-8") != rendered:
            raise AdversarialIntegrityError("contrato adversarial já existe com conteúdo divergente")
        return {
            "ok": True,
            "resultado": "ja_materializado",
            "quest_id": qid,
            "mission_id": mid,
            "arquivo": _contract_path(qid).as_posix(),
            "mutacoes_aplicadas": False,
        }
    _atomic(path, doc)
    return {
        "ok": True,
        "resultado": "materializado",
        "quest_id": qid,
        "mission_id": mid,
        "arquivo": _contract_path(qid).as_posix(),
        "mutacoes_aplicadas": True,
        "fontes_lidas": list(dict.fromkeys([*sources, str(mission.get("arquivo"))])),
    }


def load_contract(repo: Path, mission: dict[str, Any]) -> tuple[dict[str, Any], str]:
    qid = mission.get("quest_id")
    if not isinstance(qid, str):
        raise AdversarialIntegrityError("missão emergente sem quest_id")
    rel = _contract_path(qid)
    doc = _map(_load(repo / rel), rel.as_posix())
    if (
        doc.get("schema_integridade_adversarial") != SCHEMA
        or doc.get("natureza") != "reservado"
        or doc.get("quest_id") != qid
        or doc.get("mission_id") != mission.get("id")
    ):
        raise AdversarialIntegrityError(f"contrato adversarial divergente: {qid}")
    contract = _map(doc.get("contrato"), f"{qid}.contrato")
    if doc.get("contrato_digest") != _digest(contract):
        raise AdversarialIntegrityError(f"digest adversarial divergente: {qid}")
    return doc, rel.as_posix()


def sidequest_authority(repo: Path, mission: dict[str, Any]) -> dict[str, Any]:
    raw = mission.get("arquivo")
    if not isinstance(raw, str):
        raise AdversarialIntegrityError("missão emergente sem arquivo Task41")
    quest = _map(_load(repo / raw), raw)
    relation = _map(quest.get("relacao_canone"), "relacao_canone")
    if relation.get("modo") == "lateral":
        return {
            "autoridade": "sidequest_lateral",
            "reserva": None,
            "fontes_lidas": [raw],
        }
    try:
        state = canon_bridge.load_state(repo)
    except canon_bridge.CanonBridgeError as exc:
        raise AdversarialIntegrityError(str(exc)) from exc
    matches = [
        {"evento_id": event_id, **copy.deepcopy(reservation)}
        for event_id, reservation in state["reservas"].items()
        if isinstance(reservation, dict)
        and reservation.get("mission_id") == mission.get("id")
        and reservation.get("estado") in canon_bridge.RESERVATION_STATES
    ]
    if len(matches) != 1:
        raise AdversarialIntegrityError(
            "sidequest não lateral só recebe autoridade canônica com exatamente uma reserva Task42 ativa"
        )
    return {
        "autoridade": "sidequest_canonica",
        "reserva": matches[0],
        "fontes_lidas": [raw, canon_bridge.STATE.as_posix()],
    }


def _normalized_consequence(raw: Any) -> dict[str, Any]:
    value = copy.deepcopy(_map(raw, "consequencia"))
    severity = _text(value.get("gravidade"), "consequencia.gravidade", maximum=16)
    reversibility = _text(value.get("reversibilidade"), "consequencia.reversibilidade", maximum=16)
    impact = _text(value.get("classe_impacto"), "consequencia.classe_impacto", maximum=24)
    if severity not in SEVERITY_RANK or reversibility not in REVERSIBILITY or impact not in IMPACT_CLASSES:
        raise AdversarialIntegrityError("classificação de consequência inválida")
    targets = [
        _slug(item, "consequencia.alvos_npc")
        for item in _list(value.get("alvos_npc"), "consequencia.alvos_npc")
    ]
    if len(targets) != len(set(targets)):
        raise AdversarialIntegrityError("consequencia.alvos_npc possui duplicatas")
    value["gravidade"] = severity
    value["reversibilidade"] = reversibility
    value["classe_impacto"] = impact
    value["alvos_npc"] = targets
    return value


def _find_escalation(contract: dict[str, Any], escalation_id: str) -> dict[str, Any]:
    escalation_id = _slug(escalation_id, "escalada_id")
    matches = [
        item for item in contract["escaladas_possiveis"]
        if item.get("id") == escalation_id
    ]
    if len(matches) != 1:
        raise AdversarialIntegrityError(f"escalada não existe no contrato Task44: {escalation_id}")
    return matches[0]


def authorize_sidequest_consequence(
    repo: Path,
    mission_id: str,
    raw: Any,
    *,
    proof: Any,
) -> dict[str, Any]:
    """Autoriza consequência emergente contra o contrato já congelado."""
    _, mission = _mission(repo, mission_id)
    if mission.get("estado") not in {"aceita", "concluida", "falhada", "expirada"}:
        raise AdversarialIntegrityError("consequência exige sidequest aceita ou encerrada")
    doc, contract_source = load_contract(repo, mission)
    contract = doc["contrato"]
    value = _normalized_consequence(raw)
    escalation_id = _slug(value.get("escalada_id"), "consequencia.escalada_id")
    escalation = _find_escalation(contract, escalation_id)
    if value["gravidade"] != escalation["gravidade"]:
        raise AdversarialIntegrityError(
            "consequência não pode ser amaciada ou agravada depois: gravidade diverge do contrato"
        )
    if value["reversibilidade"] != escalation["reversibilidade"]:
        raise AdversarialIntegrityError("reversibilidade diverge da escalada congelada")
    if value["classe_impacto"] != escalation["classe_impacto"]:
        raise AdversarialIntegrityError("classe_impacto diverge da escalada congelada")
    if value["alvos_npc"] != [item for item in escalation["alvos"] if item in value["alvos_npc"]]:
        if set(value["alvos_npc"]) != set(escalation["alvos"]):
            raise AdversarialIntegrityError("alvos divergem da escalada congelada")
    causal = _safe_proof(repo, proof, "prova_causal")
    authority = sidequest_authority(repo, mission)
    protected_policy = rede_protegida.load_policy(repo)
    protected = sorted(set(value["alvos_npc"]) & rede_protegida.protected_ids(protected_policy))
    sources = [
        oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix(), contract_source,
        *authority["fontes_lidas"], causal["fonte"], rede_protegida.INDEX.as_posix(), POLICY.as_posix(),
    ]
    load_policy(repo)
    if authority["autoridade"] == "sidequest_lateral":
        try:
            guarded = rede_protegida.guard_consequence(repo, value, origem="sidequest")
        except rede_protegida.ProtectedNetworkError as exc:
            raise AdversarialIntegrityError(str(exc)) from exc
        value = guarded["valor"]
        sources.extend(guarded["fontes_lidas"])
    else:
        # A reserva Task42 converte a origem de procedural para canônica, mas não
        # inventa risco: alvo, gravidade e condição continuam congelados na Task44.
        if protected and authority["reserva"] is None:
            raise AdversarialIntegrityError("núcleo protegido exige reserva canônica ativa")
    value["escalada_id"] = escalation_id
    value["autoridade_consequencia"] = authority["autoridade"]
    value["prova_causal"] = causal
    value["contrato_adversarial"] = contract_source
    if authority["reserva"] is not None:
        value["vinculo_canonico"] = {
            "evento_id": authority["reserva"]["evento_id"],
            "intencao_id": authority["reserva"].get("intencao_id"),
            "modo": authority["reserva"].get("modo"),
        }
    return {
        "ok": True,
        "valor": value,
        "autoridade": authority["autoridade"],
        "alvos_protegidos": protected,
        "fontes_lidas": list(dict.fromkeys(sources)),
    }


def authorize_external_consequence(
    repo: Path,
    raw: Any,
    *,
    authority: str,
    proof: Any | None = None,
) -> dict[str, Any]:
    """Autoriza procedural/evento canônico/ação de Ren/combate sem plot armor oculto."""
    if authority not in AUTHORITIES or authority.startswith("sidequest_"):
        raise AdversarialIntegrityError("use authorize_sidequest_consequence para sidequests")
    value = _normalized_consequence(raw)
    load_policy(repo)
    protected_policy = rede_protegida.load_policy(repo)
    protected = sorted(set(value["alvos_npc"]) & rede_protegida.protected_ids(protected_policy))
    if authority == "procedural":
        try:
            guarded = rede_protegida.guard_consequence(repo, value, origem="evento_mundial")
        except rede_protegida.ProtectedNetworkError as exc:
            raise AdversarialIntegrityError(str(exc)) from exc
        value = guarded["valor"]
        causal = None
    else:
        if proof is None:
            raise AdversarialIntegrityError(
                f"autoridade {authority} exige evidência canônica literal da consequência"
            )
        causal = _safe_proof(repo, proof, "prova_causal")
        value["prova_causal"] = causal
    value["autoridade_consequencia"] = authority
    return {
        "ok": True,
        "valor": value,
        "autoridade": authority,
        "alvos_protegidos": protected,
        "fontes_lidas": list(dict.fromkeys([
            POLICY.as_posix(), rede_protegida.INDEX.as_posix(),
            *([causal["fonte"]] if causal else []),
        ])),
    }


def resolve_escalation_choice(
    repo: Path,
    mission_id: str,
    *,
    chosen_escalation_id: str,
    proofs: dict[str, Any],
    blocker: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Impede amaciamento retrospectivo de escalada marcada obrigatória."""
    _, mission = _mission(repo, mission_id)
    doc, source = load_contract(repo, mission)
    contract = doc["contrato"]
    chosen = _find_escalation(contract, chosen_escalation_id)
    matched: list[str] = []
    proof_sources: list[str] = []
    for escalation in contract["escaladas_possiveis"]:
        raw_proof = proofs.get(escalation["id"])
        if raw_proof is None:
            continue
        causal = _safe_proof(repo, raw_proof, f"provas.{escalation['id']}")
        matched.append(escalation["id"])
        proof_sources.append(causal["fonte"])
    mandatory = [
        item["id"] for item in contract["escaladas_possiveis"]
        if item["id"] in matched and item["prioridade"] == "obrigatoria_se_condicao"
    ]
    blocker_result = None
    if mandatory and chosen["id"] not in mandatory:
        if blocker is None:
            raise AdversarialIntegrityError(
                "há escalada obrigatoria_se_condicao demonstrada; consequência mais branda exige bloqueio causal"
            )
        b = _map(blocker, "bloqueio")
        if set(b) != {"escalada_id", "indice", "fonte", "evidencia"}:
            raise AdversarialIntegrityError("bloqueio exige escalada_id, indice, fonte e evidencia")
        eid = _slug(b["escalada_id"], "bloqueio.escalada_id")
        target = _find_escalation(contract, eid)
        if eid not in mandatory:
            raise AdversarialIntegrityError("bloqueio precisa apontar para escalada obrigatória demonstrada")
        index = b["indice"]
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < len(target["bloqueios_causais"]):
            raise AdversarialIntegrityError("indice de bloqueio causal inválido")
        blocker_result = _safe_proof(
            repo,
            {"fonte": b["fonte"], "evidencia": b["evidencia"]},
            "bloqueio.prova",
        )
        blocker_result["regra"] = target["bloqueios_causais"][index]
        proof_sources.append(blocker_result["fonte"])
    return {
        "ok": True,
        "escolhida": chosen["id"],
        "condicoes_demonstradas": matched,
        "obrigatorias_demonstradas": mandatory,
        "bloqueio_causal": blocker_result,
        "regra": (
            "não escolher consequência mais branda por conveniência; escalada obrigatória só cede a bloqueio causal demonstrado"
        ),
        "fontes_lidas": list(dict.fromkeys([
            oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix(), source, *proof_sources
        ])),
    }


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    contracts = 0
    try:
        load_policy(repo)
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
        for mission in state["missoes"].values():
            if not isinstance(mission, dict) or mission.get("origem") != "sidequest_emergente":
                continue
            contracts += 1
            try:
                load_contract(repo, mission)
            except AdversarialIntegrityError as exc:
                errors.append(str(exc))
    except (AdversarialIntegrityError, oportunidades.OpportunityError) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "contratos": contracts,
        "erros": list(dict.fromkeys(errors)),
        "fontes_lidas": [POLICY.as_posix(), oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix()],
    }


def _stdin() -> Any:
    import sys
    raw = sys.stdin.read()
    if not raw.strip():
        raise AdversarialIntegrityError("comando exige YAML/JSON em stdin")
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise AdversarialIntegrityError(str(exc)) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    show = sub.add_parser("agente")
    show.add_argument("actor_id")
    show.add_argument("capability_id")
    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        if args.cmd == "check":
            result = validate_repo(repo)
        else:
            result = agent_option(repo, args.actor_id, args.capability_id)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0 if result.get("ok", result.get("permitida", False)) else 1
    except AdversarialIntegrityError as exc:
        print(yaml.safe_dump({"ok": False, "erro": str(exc)}, allow_unicode=True, sort_keys=False), end="")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
