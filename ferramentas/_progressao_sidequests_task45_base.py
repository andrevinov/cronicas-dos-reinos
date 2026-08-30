#!/usr/bin/env python3
"""Task 45 — Sidequest Progression, Deadlines & Consequences.

Sidequests emergentes passam a ter progresso factual, disponibilidade de atores,
prazos e desfechos executáveis. Esta camada não cria scheduler, não varre o repo e
não inventa stakes depois do fato: Task41 define a mini-história, Task43 congela
recompensas/perdas, Task44 congela adversários e escaladas, e Task45 executa esses
contratos quando fatos canônicos, falha ou prazo tornam um desfecho devido.

Prazo vencido não mata NPC automaticamente. A missão é encerrada pelo lifecycle já
existente e uma pendência ``resolver_sidequest`` entra na fila do Mundo Vivo. A
resolução exige escolher uma escalada Task44 já congelada e prová-la literalmente;
só então uma transação de mundo materializa consequência/NPC e a pendência fecha.
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

import barreira_mundo
import canon_bridge_runtime
import integridade_adversarial as adversarial
import mundo
import oportunidades
import recompensas_sidequest as quest_rewards
import sidequests_emergentes as emergent
import transacoes
import turno

PROGRESS_DIR = Path("narrador/sidequests-emergentes/progresso")
NPC_INDEX = Path("estado/npcs/index.yaml")
SCHEMA = 1
MAX_FRAGMENT_BYTES = 24 * 1024
MAX_PROJECT_BYTES = 8 * 1024
MAX_HISTORY = 32
MAX_FACTS = 48
MAX_ACTORS = 24
MAX_TEXT = 520
MAX_EVIDENCE = 360
MAX_PENDING_TASK45 = 2

SUCCESS_RULES = {"todas", "qualquer"}
FAILURE_RULES = {"todas", "qualquer"}
PHASE_STATES = {"indeterminada", "possivel", "impossivel", "resolvida"}
CONDITION_STATES = {"pendente", "satisfeita", "inviavel"}
UNAVAILABLE_LIFE_STATES = {"morto", "incapacitado", "desaparecido", "preso"}
NPC_EFFECT_STATES = set(UNAVAILABLE_LIFE_STATES)
FORBIDDEN_PROOF_PREFIXES = (
    "narrador/sidequests-emergentes/",
    "narrador/arcos/parte_1/intencoes/",
    "narrador/arcos/parte_1/eventos/",
)
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_:-]{0,95}$")


class SidequestProgressionError(ValueError):
    pass


def configured(repo: Path) -> bool:
    return (repo / oportunidades.INDEX).is_file() and (repo / oportunidades.STATE).is_file()


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise SidequestProgressionError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SidequestProgressionError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise SidequestProgressionError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str, minimum: int = 1, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise SidequestProgressionError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if len(result) < minimum or len(result) > maximum:
        raise SidequestProgressionError(f"{label} deve ter {minimum}..{maximum} caracteres")
    return result


def _id(value: Any, label: str) -> str:
    result = _text(value, label, maximum=128)
    if not ID_RE.fullmatch(result):
        raise SidequestProgressionError(f"{label} deve usar id ASCII minúsculo estável")
    return result


def _slug(value: Any, label: str) -> str:
    result = _text(value, label, maximum=96)
    if not SLUG_RE.fullmatch(result):
        raise SidequestProgressionError(f"{label} deve usar slug ASCII minúsculo")
    return result


def _bytes(value: Any) -> bytes:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8")


def _atomic(path: Path, data: dict[str, Any]) -> None:
    raw = _bytes(data)
    if len(raw) > MAX_FRAGMENT_BYTES:
        raise SidequestProgressionError(
            f"fragmento Task45 excede {MAX_FRAGMENT_BYTES} bytes: {len(raw)}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "wb", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
        tmp = Path(handle.name)
    os.replace(tmp, path)


def _progress_rel(quest_id: str) -> Path:
    if not re.fullmatch(r"qse-[0-9a-f]{16}", quest_id):
        raise SidequestProgressionError("quest_id emergente inválido")
    return PROGRESS_DIR / f"{quest_id}.yaml"


def _mission(repo: Path, ref: str) -> tuple[dict[str, Any], str, dict[str, Any]]:
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise SidequestProgressionError(str(exc)) from exc
    matches = [
        (mid, mission)
        for mid, mission in state.get("missoes", {}).items()
        if isinstance(mission, dict)
        and mission.get("origem") == "sidequest_emergente"
        and ref in {mid, mission.get("id"), mission.get("quest_id")}
    ]
    if len(matches) != 1:
        raise SidequestProgressionError(f"sidequest emergente inexistente/ambígua: {ref}")
    return state, matches[0][0], matches[0][1]


def _quest(repo: Path, mission: dict[str, Any]) -> dict[str, Any]:
    rel = mission.get("arquivo")
    if not isinstance(rel, str) or not rel.startswith("narrador/sidequests-emergentes/quests/"):
        raise SidequestProgressionError("missão Task41 sem fragmento reservado válido")
    doc = _map(_load(repo / rel), rel)
    if doc.get("schema_sidequest_emergente") != 2 or doc.get("id") != mission.get("quest_id"):
        raise SidequestProgressionError("fragmento Task41 inválido/divergente")
    return doc


def _proof(repo: Path, raw: Any, label: str) -> dict[str, str]:
    data = _map(raw, label)
    if set(data) != {"fonte", "evidencia"}:
        raise SidequestProgressionError(f"{label} exige fonte e evidencia")
    source = _text(data["fonte"], f"{label}.fonte", maximum=240)
    rel = Path(source)
    if rel.is_absolute() or ".." in rel.parts or any(source.startswith(p) for p in FORBIDDEN_PROOF_PREFIXES):
        raise SidequestProgressionError("planejamento reservado não pode provar progresso")
    path = repo / rel
    if not path.is_file():
        raise SidequestProgressionError(f"fonte inexistente: {source}")
    evidence = _text(data["evidencia"], f"{label}.evidencia", 8, MAX_EVIDENCE)
    if evidence not in " ".join(path.read_text(encoding="utf-8").split()):
        raise SidequestProgressionError(f"evidência literal não encontrada em {source}")
    return {"fonte": source, "evidencia": evidence}


def _actor_ids(quest: dict[str, Any]) -> tuple[list[str], set[str]]:
    ids: list[str] = []
    new_ids = {str(item["id"]) for item in quest.get("npcs_novos") or [] if isinstance(item, dict)}
    groups = [
        quest.get("npcs_existentes") or [],
        quest.get("npcs_novos") or [],
        quest.get("antagonistas") or [],
        quest.get("juppongatana") or [],
    ]
    giver = quest.get("quest_giver") or {}
    if isinstance(giver, dict) and isinstance(giver.get("id"), str):
        ids.append(giver["id"])
    for group in groups:
        for item in group:
            if isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"] not in ids:
                ids.append(item["id"])
    if len(ids) > MAX_ACTORS:
        raise SidequestProgressionError(f"elenco Task45 excede {MAX_ACTORS} atores")
    return ids, new_ids


def _normalize_dependencies(raw: Any, quest: dict[str, Any], actors: set[str]) -> list[dict[str, Any]]:
    phase_ids = [str(item["id"]) for item in quest.get("fases") or []]
    rows = _list(raw, "dependencias_fases")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pos, raw_row in enumerate(rows):
        row = _map(raw_row, f"dependencias_fases[{pos}]")
        if set(row) != {"fase_id", "atores_necessarios", "substituicao_permitida"}:
            raise SidequestProgressionError("dependência de fase exige fase_id/atores_necessarios/substituicao_permitida")
        phase_id = _slug(row["fase_id"], f"dependencias[{pos}].fase_id")
        if phase_id not in phase_ids or phase_id in seen:
            raise SidequestProgressionError(f"fase desconhecida/duplicada em dependências: {phase_id}")
        seen.add(phase_id)
        required = [_id(value, f"dependencias[{pos}].atores_necessarios") for value in _list(row["atores_necessarios"], "atores_necessarios")]
        if len(required) != len(set(required)) or set(required) - actors:
            raise SidequestProgressionError(f"{phase_id}: ator necessário deve pertencer ao elenco Task41")
        if not isinstance(row["substituicao_permitida"], bool):
            raise SidequestProgressionError("substituicao_permitida deve ser booleano")
        result.append({
            "fase_id": phase_id,
            "atores_necessarios": required,
            "substituicao_permitida": row["substituicao_permitida"],
        })
    if seen != set(phase_ids):
        raise SidequestProgressionError("Task45 deve classificar exatamente todas as fases Task41")
    return result


def _effect_compatible(escalation: dict[str, Any], state: str) -> bool:
    severity = escalation["gravidade"]
    impact = escalation["classe_impacto"]
    reversibility = escalation["reversibilidade"]
    if state == "morto":
        return severity == "grave" and impact == "vida" and reversibility == "irreversivel"
    if state in {"desaparecido", "preso"}:
        return impact == "liberdade" and severity in {"moderada", "grave"}
    if state == "incapacitado":
        return impact == "saude" and severity in {"moderada", "grave"}
    return False


def _normalize_effects(raw: Any, adv_contract: dict[str, Any]) -> list[dict[str, Any]]:
    escalations = {item["id"]: item for item in adv_contract["escaladas_possiveis"]}
    terminal = set(adv_contract["consequencias_de_falha"]) | set(adv_contract["consequencias_de_inacao"])
    risk_types = {item["id"]: item["tipo"] for item in adv_contract["alvos_em_risco"]}
    rows = _list(raw, "efeitos_escaladas")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pos, raw_row in enumerate(rows):
        row = _map(raw_row, f"efeitos_escaladas[{pos}]")
        if set(row) != {"escalada_id", "efeitos_npc"}:
            raise SidequestProgressionError("efeito de escalada exige escalada_id/efeitos_npc")
        eid = _slug(row["escalada_id"], f"efeitos_escaladas[{pos}].escalada_id")
        if eid not in terminal or eid in seen:
            raise SidequestProgressionError(f"escalada terminal desconhecida/duplicada: {eid}")
        seen.add(eid)
        escalation = escalations[eid]
        effects: list[dict[str, str]] = []
        affected: set[str] = set()
        for idx, raw_effect in enumerate(_list(row["efeitos_npc"], f"{eid}.efeitos_npc")):
            effect = _map(raw_effect, f"{eid}.efeitos_npc[{idx}]")
            if set(effect) != {"npc_id", "estado"}:
                raise SidequestProgressionError("efeito NPC exige npc_id/estado")
            npc_id = _id(effect["npc_id"], f"{eid}.npc_id")
            state = _slug(effect["estado"], f"{eid}.estado")
            if npc_id in affected or npc_id not in escalation["alvos"] or risk_types.get(npc_id) != "npc":
                raise SidequestProgressionError(f"{eid}: efeito NPC precisa apontar alvo NPC da própria escalada")
            if state not in NPC_EFFECT_STATES or not _effect_compatible(escalation, state):
                raise SidequestProgressionError(f"{eid}: estado {state} incompatível com gravidade/classe/reversibilidade congeladas")
            affected.add(npc_id)
            effects.append({"npc_id": npc_id, "estado": state})
        result.append({"escalada_id": eid, "efeitos_npc": effects})
    if seen != terminal:
        raise SidequestProgressionError("Task45 deve classificar todas as escaladas de falha/inação Task44, mesmo quando efeitos_npc é vazio")
    return result


def _initial_conditions(values: list[str], prefix: str) -> dict[str, Any]:
    return {
        f"{prefix}_{idx:02d}": {"texto": text, "estado": "pendente", "fato_id": None}
        for idx, text in enumerate(values, 1)
    }


def _initial_state(quest: dict[str, Any], actors: list[str]) -> dict[str, Any]:
    return {
        "fases": {
            str(item["id"]): {"estado": "indeterminada", "fato_id": None, "motivo_automatico": None}
            for item in quest["fases"]
        },
        "condicoes_sucesso": _initial_conditions(list(quest["condicoes_sucesso"]), "sucesso"),
        "condicoes_falha": _initial_conditions(list(quest["condicoes_falha"]), "falha"),
        "atores": {actor: {"estado": "desconhecido", "vida_estado": None, "fonte": None} for actor in actors},
        "fatos": {},
        "consequencias_ativadas": {},
        "terminal": None,
        "historico_recente": [],
    }


def register_contract(repo: Path, mission_ref: str, *, contract_raw: Any) -> dict[str, Any]:
    opp, mid, mission = _mission(repo, mission_ref)
    if mission.get("estado") not in {"oferecida", "adiada"}:
        raise SidequestProgressionError("contrato Task45 deve ser congelado antes do aceite")
    quest = _quest(repo, mission)
    try:
        reward_doc, reward_rel = quest_rewards._load_contract(repo, mission, mid)
        adv_doc, adv_rel = adversarial.load_contract(repo, mission)
    except (quest_rewards.QuestRewardError, adversarial.AdversarialIntegrityError) as exc:
        raise SidequestProgressionError(str(exc)) from exc
    data = _map(contract_raw, "contrato_progressao")
    expected = {"regra_sucesso", "regra_falha", "dependencias_fases", "efeitos_escaladas"}
    if set(data) != expected:
        raise SidequestProgressionError("contrato_progressao possui estrutura inesperada")
    success_rule = _slug(data["regra_sucesso"], "regra_sucesso")
    failure_rule = _slug(data["regra_falha"], "regra_falha")
    if success_rule not in SUCCESS_RULES or failure_rule not in FAILURE_RULES:
        raise SidequestProgressionError("regra_sucesso/regra_falha deve ser todas ou qualquer")
    actors, new_ids = _actor_ids(quest)
    dependencies = _normalize_dependencies(data["dependencias_fases"], quest, set(actors))
    effects = _normalize_effects(data["efeitos_escaladas"], adv_doc["contrato"])
    qid = str(mission["quest_id"])
    rel = _progress_rel(qid)
    doc = {
        "schema_progressao_sidequest": SCHEMA,
        "natureza": "reservado",
        "mission_id": mid,
        "quest_id": qid,
        "quest_file": mission["arquivo"],
        "contrato_recompensa": reward_rel.as_posix(),
        "contrato_adversarial": adv_rel,
        "prazo": copy.deepcopy(mission.get("janela")),
        "contrato": {
            "regra_sucesso": success_rule,
            "regra_falha": failure_rule,
            "dependencias_fases": dependencies,
            "efeitos_escaladas": effects,
            "escaladas_falha": list(adv_doc["contrato"]["consequencias_de_falha"]),
            "escaladas_inacao": list(adv_doc["contrato"]["consequencias_de_inacao"]),
        },
        "atores_novos_reservados": sorted(new_ids),
        "estado": _initial_state(quest, actors),
        "guardrails": {
            "progresso_por_fato_nao_checklist": True,
            "prazo_usa_relogio_existente": True,
            "sem_scheduler": True,
            "consequencia_so_task44": True,
            "recompensa_so_task43_apos_sucesso": True,
            "canon_terminal_via_task42": True,
        },
    }
    path = repo / rel
    created = False
    if path.is_file():
        old = _map(_load(path), rel.as_posix())
        comparable = copy.deepcopy(old)
        if comparable != doc:
            # Estado pode ter avançado; contrato, identidade e prazo precisam ser os mesmos.
            for key in ("schema_progressao_sidequest", "natureza", "mission_id", "quest_id", "quest_file", "contrato_recompensa", "contrato_adversarial", "prazo", "contrato", "atores_novos_reservados", "guardrails"):
                if old.get(key) != doc.get(key):
                    raise SidequestProgressionError("contrato Task45 existente diverge")
    else:
        _atomic(path, doc)
        created = True
    changed = mission.get("progresso_sidequest") != rel.as_posix()
    if changed:
        mission["progresso_sidequest"] = rel.as_posix()
        oportunidades.atomic(repo / oportunidades.STATE, opp)
    return {
        "ok": True,
        "resultado": "contrato_registrado" if created else "contrato_ja_existia",
        "mission_id": mid,
        "quest_id": qid,
        "arquivo": rel.as_posix(),
        "mission_pointer_reparado": changed,
        "fases": len(dependencies),
        "atores": len(actors),
    }


def _load_progress(repo: Path, mission: dict[str, Any], mid: str) -> tuple[dict[str, Any], Path]:
    qid = str(mission.get("quest_id") or "")
    expected = _progress_rel(qid)
    if mission.get("progresso_sidequest") != expected.as_posix():
        raise SidequestProgressionError(f"{mid}: sidequest emergente sem contrato Task45 obrigatório")
    doc = _map(_load(repo / expected), expected.as_posix())
    if doc.get("schema_progressao_sidequest") != SCHEMA or doc.get("mission_id") != mid or doc.get("quest_id") != qid:
        raise SidequestProgressionError(f"{mid}: fragmento Task45 inválido")
    state = _map(doc.get("estado"), "Task45.estado")
    for key in ("fases", "condicoes_sucesso", "condicoes_falha", "atores", "fatos", "consequencias_ativadas"):
        _map(state.get(key), f"Task45.estado.{key}")
    history = _list(state.get("historico_recente"), "Task45.historico_recente")
    if len(history) > MAX_HISTORY or len(state["fatos"]) > MAX_FACTS:
        raise SidequestProgressionError("estado Task45 excede orçamento")
    if len(_bytes(doc)) > MAX_FRAGMENT_BYTES:
        raise SidequestProgressionError("fragmento Task45 excede orçamento")
    return doc, expected


def _history(doc: dict[str, Any], item: dict[str, Any]) -> None:
    history = doc["estado"]["historico_recente"]
    history.append(item)
    doc["estado"]["historico_recente"] = history[-MAX_HISTORY:]


def _npc_life(repo: Path, npc_id: str) -> tuple[str | None, str | None, bool]:
    path = repo / NPC_INDEX
    if not path.is_file():
        return None, None, False
    index = _map(_load(path), NPC_INDEX.as_posix())
    meta = (index.get("npcs") or {}).get(npc_id)
    if not isinstance(meta, dict) or not isinstance(meta.get("arquivo"), str):
        return None, NPC_INDEX.as_posix(), False
    rel = meta["arquivo"]
    doc = _map(_load(repo / rel), rel)
    body = doc.get("npc") if isinstance(doc.get("npc"), dict) else doc
    life = body.get("vida") if isinstance(body, dict) and isinstance(body.get("vida"), dict) else {}
    state = life.get("estado") if isinstance(life.get("estado"), str) else None
    return state, rel, True


def _sync_actor_availability(repo: Path, doc: dict[str, Any]) -> bool:
    changed = False
    reserved_new = set(doc.get("atores_novos_reservados") or [])
    actors = doc["estado"]["atores"]
    for actor_id, current in actors.items():
        life, source, exists = _npc_life(repo, actor_id)
        if life in UNAVAILABLE_LIFE_STATES:
            status = "indisponivel"
        elif exists:
            status = "disponivel"
        elif actor_id in reserved_new:
            status = "reservado_nao_presente"
        else:
            status = "disponibilidade_nao_rastreada"
        wanted = {"estado": status, "vida_estado": life, "fonte": source}
        if current != wanted:
            actors[actor_id] = wanted
            changed = True
    for dep in doc["contrato"]["dependencias_fases"]:
        phase = doc["estado"]["fases"][dep["fase_id"]]
        if phase["estado"] == "resolvida" or dep["substituicao_permitida"]:
            continue
        unavailable = [
            aid for aid in dep["atores_necessarios"]
            if actors.get(aid, {}).get("estado") == "indisponivel"
        ]
        if unavailable and (
            phase["estado"] != "impossivel"
            or phase.get("motivo_automatico") != {"tipo": "ator_indisponivel", "atores": unavailable}
        ):
            phase["estado"] = "impossivel"
            phase["fato_id"] = None
            phase["motivo_automatico"] = {"tipo": "ator_indisponivel", "atores": unavailable}
            changed = True
    return changed


def _condition_ready(values: dict[str, Any], rule: str) -> bool:
    states = [item.get("estado") for item in values.values()]
    if not states:
        return False
    if rule == "todas":
        return all(state == "satisfeita" for state in states)
    return any(state == "satisfeita" for state in states)


def _evaluation(doc: dict[str, Any]) -> dict[str, Any]:
    state = doc["estado"]
    success = _condition_ready(state["condicoes_sucesso"], doc["contrato"]["regra_sucesso"])
    failure = _condition_ready(state["condicoes_falha"], doc["contrato"]["regra_falha"])
    return {
        "sucesso_pronto": success,
        "falha_pronta": failure,
        "ambiguo": success and failure,
    }


def record_fact(repo: Path, mission_ref: str, *, fact_raw: Any) -> dict[str, Any]:
    _, mid, mission = _mission(repo, mission_ref)
    if mission.get("estado") != "aceita":
        raise SidequestProgressionError("progresso factual Task45 exige sidequest aceita")
    doc, rel = _load_progress(repo, mission, mid)
    fact = _map(fact_raw, "fato")
    expected = {"id", "descricao", "prova", "fases", "condicoes_sucesso", "condicoes_falha"}
    if set(fact) != expected:
        raise SidequestProgressionError("fato Task45 possui estrutura inesperada")
    fact_id = _slug(fact["id"], "fato.id")
    normalized = {
        "id": fact_id,
        "descricao": _text(fact["descricao"], "fato.descricao"),
        "prova": _proof(repo, fact["prova"], "fato.prova"),
        "fases": copy.deepcopy(_map(fact["fases"], "fato.fases")),
        "condicoes_sucesso": copy.deepcopy(_map(fact["condicoes_sucesso"], "fato.condicoes_sucesso")),
        "condicoes_falha": copy.deepcopy(_map(fact["condicoes_falha"], "fato.condicoes_falha")),
    }
    existing = doc["estado"]["fatos"].get(fact_id)
    if existing is not None:
        if existing != normalized:
            raise SidequestProgressionError(f"fato {fact_id} já existe com conteúdo divergente")
        return {"ok": True, "resultado": "fato_ja_registrado", "mission_id": mid, "avaliacao": _evaluation(doc)}
    if len(doc["estado"]["fatos"]) >= MAX_FACTS:
        raise SidequestProgressionError(f"Task45 atingiu max_fatos={MAX_FACTS}")
    for phase_id, target in normalized["fases"].items():
        if phase_id not in doc["estado"]["fases"] or target not in PHASE_STATES:
            raise SidequestProgressionError(f"transição de fase inválida: {phase_id} -> {target}")
    for group in ("condicoes_sucesso", "condicoes_falha"):
        target_group = doc["estado"][group]
        for cid, target in normalized[group].items():
            if cid not in target_group or target not in CONDITION_STATES:
                raise SidequestProgressionError(f"transição de condição inválida: {cid} -> {target}")
    doc["estado"]["fatos"][fact_id] = normalized
    for phase_id, target in normalized["fases"].items():
        doc["estado"]["fases"][phase_id] = {"estado": target, "fato_id": fact_id, "motivo_automatico": None}
    for group in ("condicoes_sucesso", "condicoes_falha"):
        for cid, target in normalized[group].items():
            doc["estado"][group][cid]["estado"] = target
            doc["estado"][group][cid]["fato_id"] = fact_id
    _sync_actor_availability(repo, doc)
    _history(doc, {"tipo": "fato_registrado", "id": fact_id, "fonte": normalized["prova"]["fonte"]})
    _atomic(repo / rel, doc)
    return {"ok": True, "resultado": "fato_registrado", "mission_id": mid, "avaliacao": _evaluation(doc)}


def _deadline(mission: dict[str, Any]) -> mundo.WorldInstant | None:
    window = mission.get("janela")
    if not isinstance(window, dict) or window.get("tipo") != "temporal":
        return None
    raw = window.get("expira_em")
    if not isinstance(raw, dict):
        return None
    return mundo.parse_instant(str(raw.get("data")), str(raw.get("hora")))


def _terminalize(
    repo: Path,
    mid: str,
    mission: dict[str, Any],
    doc: dict[str, Any],
    rel: Path,
    outcome: str,
    *,
    reason: str,
    current: mundo.WorldInstant,
    trigger: str,
) -> dict[str, Any]:
    terminal = doc["estado"].get("terminal")
    if isinstance(terminal, dict):
        if terminal.get("resultado") != outcome:
            raise SidequestProgressionError("Task45 já possui desfecho terminal divergente")
        return terminal
    if mission.get("estado") != outcome:
        try:
            result = canon_bridge_runtime.finish(repo, mid, outcome, reason=reason, now=current)
        except canon_bridge_runtime.CanonBridgeRuntimeError as exc:
            raise SidequestProgressionError(str(exc)) from exc
        mission = result["missao"]
    terminal = {
        "resultado": outcome,
        "gatilho": trigger,
        "em": mundo.instant_parts(current),
        "motivo": reason,
        "pendencia_id": None,
    }
    doc["estado"]["terminal"] = terminal
    _history(doc, {"tipo": "desfecho_terminal", "resultado": outcome, "gatilho": trigger, "em": mundo.instant_parts(current)})
    _atomic(repo / rel, doc)
    return terminal


def _allowed_escalations(doc: dict[str, Any], trigger: str) -> list[str]:
    if trigger == "inacao":
        return list(doc["contrato"]["escaladas_inacao"])
    if trigger == "falha":
        return list(doc["contrato"]["escaladas_falha"])
    return []


def _emit_pending(repo: Path, mid: str, mission: dict[str, Any], doc: dict[str, Any], rel: Path, *, trigger: str, when: mundo.WorldInstant) -> dict[str, Any]:
    allowed = _allowed_escalations(doc, trigger)
    if not allowed:
        return {"emitida": False, "motivo": "sem_escalada_terminal_contratada", "id": None}
    world = mundo.load_world_state(repo)
    source = f"task45:{mid}:{trigger}"
    pid = mundo._pending_id("resolver_sidequest", source, when)
    if any(item.get("id") == pid for item in world["pendencias"]):
        emitted = False
    elif any(item.get("id") == pid for item in world["concluidas_recentes"]):
        emitted = False
    else:
        active_task45 = sum(1 for item in world["pendencias"] if item.get("tipo") == "resolver_sidequest")
        if active_task45 >= MAX_PENDING_TASK45:
            raise SidequestProgressionError(f"fila Task45 excederia max_pendencias={MAX_PENDING_TASK45}")
        item = {
            "id": pid,
            "tipo": "resolver_sidequest",
            "missao": mid,
            "quest_id": mission["quest_id"],
            "resultado": mission["estado"],
            "gatilho": trigger,
            "escaladas_permitidas": allowed,
            "disparado_em": mundo.instant_parts(when),
            "motivo": "Desfecho de sidequest exige materializar consequência causal já congelada.",
            "origem": source,
        }
        mundo._merge_pending(world, [item])
        mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, world)
        emitted = True
    terminal = doc["estado"].get("terminal")
    if isinstance(terminal, dict) and terminal.get("pendencia_id") != pid:
        terminal["pendencia_id"] = pid
        _atomic(repo / rel, doc)
    barreira_mundo.sync(repo)
    return {"emitida": emitted, "id": pid, "escaladas_permitidas": allowed}


def finalize_success(
    repo: Path,
    mission_ref: str,
    *,
    optional_ids: Any | None,
    evidences: Any | None,
    narration: str,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    _, mid, mission = _mission(repo, mission_ref)
    doc, rel = _load_progress(repo, mission, mid)
    _sync_actor_availability(repo, doc)
    evaluation = _evaluation(doc)
    if evaluation["ambiguo"]:
        raise SidequestProgressionError("fatos tornam sucesso e falha simultaneamente verdadeiros; resolva a ambiguidade causal antes do desfecho")
    if not evaluation["sucesso_pronto"]:
        raise SidequestProgressionError("condições factuais ainda não autorizam sucesso")
    current = now or mundo.load_canonical_time(repo)[0]
    terminal = _terminalize(repo, mid, mission, doc, rel, "concluida", reason="condicoes_factuais_task45_satisfeitas", current=current, trigger="sucesso")
    try:
        reward = quest_rewards.apply_success(repo, mid, optional_ids=optional_ids, evidences=evidences, narration=narration)
    except quest_rewards.QuestRewardError as exc:
        raise SidequestProgressionError(str(exc)) from exc
    terminal["recompensa_resultado"] = reward.get("resultado")
    _atomic(repo / rel, doc)
    return {"ok": True, "resultado": "concluida", "mission_id": mid, "recompensa": reward}


def finalize_failure(
    repo: Path,
    mission_ref: str,
    *,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    _, mid, mission = _mission(repo, mission_ref)
    doc, rel = _load_progress(repo, mission, mid)
    _sync_actor_availability(repo, doc)
    evaluation = _evaluation(doc)
    if evaluation["ambiguo"]:
        raise SidequestProgressionError("fatos tornam sucesso e falha simultaneamente verdadeiros; resolva a ambiguidade causal")
    if not evaluation["falha_pronta"]:
        raise SidequestProgressionError("condições factuais ainda não autorizam falha")
    current = now or mundo.load_canonical_time(repo)[0]
    _terminalize(repo, mid, mission, doc, rel, "falhada", reason="condicoes_factuais_task45_satisfeitas", current=current, trigger="falha")
    state, _, mission = _mission(repo, mid)
    pending = _emit_pending(repo, mid, mission, doc, rel, trigger="falha", when=current)
    return {"ok": True, "resultado": "falhada", "mission_id": mid, "pendencia": pending}


def reconcile(repo: Path, *, now: mundo.WorldInstant | None = None) -> dict[str, Any]:
    if not configured(repo):
        return {"ok": True, "configurado": False, "alterou": False, "resultados": []}
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise SidequestProgressionError(str(exc)) from exc
    current = now or mundo.load_canonical_time(repo)[0]
    results: list[dict[str, Any]] = []
    changed = False
    for mid, mission in list(state.get("missoes", {}).items()):
        if not isinstance(mission, dict) or mission.get("origem") != "sidequest_emergente":
            continue
        if mission.get("estado") not in {"oferecida", "adiada", "aceita", "falhada", "expirada"}:
            continue
        doc, rel = _load_progress(repo, mission, mid)
        if _sync_actor_availability(repo, doc):
            _atomic(repo / rel, doc)
            changed = True
        deadline = _deadline(mission)
        if deadline is None or current.minute < deadline.minute:
            continue
        if mission["estado"] in {"oferecida", "adiada"}:
            _terminalize(repo, mid, mission, doc, rel, "expirada", reason="prazo_task45_ultrapassado_sem_aceite", current=current, trigger="expiracao_oferta")
            results.append({"mission_id": mid, "resultado": "expirada", "pendencia": None})
            changed = True
            continue
        if mission["estado"] == "aceita":
            _terminalize(repo, mid, mission, doc, rel, "falhada", reason="prazo_task45_ultrapassado", current=current, trigger="inacao")
            _, _, refreshed = _mission(repo, mid)
            pending = _emit_pending(repo, mid, refreshed, doc, rel, trigger="inacao", when=deadline)
            results.append({"mission_id": mid, "resultado": "falhada", "pendencia": pending})
            changed = True
            continue
        terminal = doc["estado"].get("terminal")
        if mission["estado"] == "falhada" and isinstance(terminal, dict) and terminal.get("gatilho") == "inacao":
            pending = _emit_pending(repo, mid, mission, doc, rel, trigger="inacao", when=deadline)
            results.append({"mission_id": mid, "resultado": "falhada", "pendencia": pending})
    return {"ok": True, "configurado": True, "alterou": changed, "resultados": results, "scheduler_novo": 0}


def project_pending(repo: Path, pending: dict[str, Any]) -> dict[str, Any]:
    if pending.get("tipo") != "resolver_sidequest":
        raise SidequestProgressionError("pendência não pertence à Task45")
    mid = _id(pending.get("missao"), "pendencia.missao")
    _, _, mission = _mission(repo, mid)
    doc, rel = _load_progress(repo, mission, mid)
    adv_doc, adv_rel = adversarial.load_contract(repo, mission)
    allowed = [_slug(value, "escalada_permitida") for value in pending.get("escaladas_permitidas") or []]
    escalations = {
        item["id"]: item for item in adv_doc["contrato"]["escaladas_possiveis"]
        if item["id"] in allowed
    }
    unavailable = [aid for aid, meta in doc["estado"]["atores"].items() if meta.get("estado") == "indisponivel"]
    result = {
        "mission_id": mid,
        "quest_id": mission["quest_id"],
        "titulo": mission.get("titulo"),
        "resultado": pending.get("resultado"),
        "gatilho": pending.get("gatilho"),
        "prazo": copy.deepcopy(doc.get("prazo")),
        "atores_indisponiveis": unavailable,
        "escaladas": [
            {
                "id": item["id"],
                "antagonista_id": item["antagonista_id"],
                "condicao": item["condicao"],
                "consequencia": item["consequencia"],
                "gravidade": item["gravidade"],
                "prioridade": item["prioridade"],
                "alvos": item["alvos"],
            }
            for item in escalations.values()
        ],
        "regra": "escolha somente consequência cuja condição esteja canonicamente provada; não existe no-op Task45",
        "fontes_lidas": [oportunidades.STATE.as_posix(), rel.as_posix(), adv_rel],
    }
    if len(_bytes(result)) > MAX_PROJECT_BYTES:
        raise SidequestProgressionError("projeção Task45 excede orçamento")
    return result


def _effect_map(doc: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    return {item["escalada_id"]: item["efeitos_npc"] for item in doc["contrato"]["efeitos_escaladas"]}


def _txid(mid: str, pending_id: str, escalation_id: str) -> str:
    raw = f"task45|{mid}|{pending_id}|{escalation_id}".encode()
    return "task45-" + hashlib.sha256(raw).hexdigest()[:20]


def _tx_exists(repo: Path, txid: str) -> bool:
    try:
        if any(item.get("id") == txid for item in transacoes.load_pending(repo)):
            return True
        session = turno.current_session(repo)
    except (transacoes.TransactionError, OSError, ValueError) as exc:
        raise SidequestProgressionError(str(exc)) from exc
    ledger = repo / "sessoes" / f"{session:03d}" / turno.LEDGER_NAME
    if not ledger.is_file():
        return False
    for pos, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SidequestProgressionError(f"ledger inválido {ledger}:{pos}: {exc}") from exc
        if txid in (item.get("transacoes") or []):
            return True
    return False


def _pending_record(repo: Path, pending_id: str, mid: str) -> tuple[dict[str, Any] | None, bool]:
    world = mundo.load_world_state(repo)
    item = next((x for x in world["pendencias"] if x.get("id") == pending_id), None)
    if item is not None:
        if item.get("tipo") != "resolver_sidequest" or item.get("missao") != mid:
            raise SidequestProgressionError("pendência Task45 diverge da missão")
        return item, True
    completed = any(x.get("id") == pending_id for x in world["concluidas_recentes"])
    return None, completed


def resolve_pending(
    repo: Path,
    mission_ref: str,
    pending_id: str,
    *,
    chosen_escalation_id: str,
    proofs: Any,
    blocker: Any | None,
    narration: str,
    loss_evidences: Any | None = None,
    loss_narration: str | None = None,
) -> dict[str, Any]:
    _, mid, mission = _mission(repo, mission_ref)
    if mission.get("estado") not in {"falhada", "expirada"}:
        raise SidequestProgressionError("consequência terminal Task45 exige missão falhada/expirada")
    doc, rel = _load_progress(repo, mission, mid)
    item, completed = _pending_record(repo, pending_id, mid)
    terminal = _map(doc["estado"].get("terminal"), "Task45.terminal")
    if terminal.get("pendencia_id") != pending_id:
        raise SidequestProgressionError("pendência não corresponde ao desfecho Task45")
    allowed = _allowed_escalations(doc, str(terminal.get("gatilho")))
    chosen = _slug(chosen_escalation_id, "escalada_escolhida")
    if chosen not in allowed:
        raise SidequestProgressionError("escalada escolhida não pertence ao gatilho terminal da quest")
    proof_map = _map(proofs, "provas_escaladas")
    if chosen not in proof_map:
        raise SidequestProgressionError("escalada escolhida exige prova causal literal")
    activated = doc["estado"]["consequencias_ativadas"].get(chosen)
    if activated is None:
        if item is None and not completed:
            raise SidequestProgressionError("pendência Task45 não está aberta nem concluída")
        try:
            choice = adversarial.resolve_escalation_choice(
                repo,
                mid,
                chosen_escalation_id=chosen,
                proofs=proof_map,
                blocker=blocker,
            )
            adv_doc, _ = adversarial.load_contract(repo, mission)
            escalation = next(x for x in adv_doc["contrato"]["escaladas_possiveis"] if x["id"] == chosen)
            raw_consequence = {
                "titulo": f"Sidequest — {mission.get('titulo') or mission['quest_id']}",
                "descricao": escalation["consequencia"],
                "gravidade": escalation["gravidade"],
                "reversibilidade": escalation["reversibilidade"],
                "classe_impacto": escalation["classe_impacto"],
                "alvos_npc": list(escalation["alvos"]),
                "escalada_id": chosen,
            }
            authorized = adversarial.authorize_sidequest_consequence(repo, mid, raw_consequence, proof=proof_map[chosen])
        except adversarial.AdversarialIntegrityError as exc:
            raise SidequestProgressionError(str(exc)) from exc
        deltas = [{"alvo": "consequencia", "op": "registrar", "valor": authorized["valor"]}]
        for effect in _effect_map(doc).get(chosen, []):
            deltas.append({
                "alvo": f"npc:{effect['npc_id']}",
                "op": "set",
                "caminho": "vida.estado",
                "valor": effect["estado"],
            })
        txid = _txid(mid, pending_id, chosen)
        if not _tx_exists(repo, txid):
            transaction = {
                "id": txid,
                "narracao": _text(narration, "narracao", 20, 2400),
                "resumo": _text(f"Sidequest {mission['quest_id']} materializa a consequência {chosen}.", "resumo", 12, 500),
                "modo": "mundo",
                "tags": ["task45-sidequest", f"missao:{mid}", f"resolver-pendencia-mundo:{pending_id}"],
                "deltas": deltas,
            }
            try:
                writer = turno.register_transaction(repo, transaction)
            except (transacoes.TransactionError, OSError, yaml.YAMLError, ValueError) as exc:
                raise SidequestProgressionError(str(exc)) from exc
        else:
            writer = {"ja_registrada": True}
        activated = {
            "escalada_id": chosen,
            "transacao": txid,
            "autoridade": authorized["autoridade"],
            "prova": authorized["valor"]["prova_causal"],
            "efeitos_npc": copy.deepcopy(_effect_map(doc).get(chosen, [])),
            "escolha_adversarial": {
                "obrigatorias_demonstradas": choice["obrigatorias_demonstradas"],
                "bloqueio_causal": choice["bloqueio_causal"],
            },
        }
        doc["estado"]["consequencias_ativadas"][chosen] = activated
        _history(doc, {"tipo": "consequencia_materializada", "escalada_id": chosen, "transacao": txid})
        _atomic(repo / rel, doc)
    else:
        writer = {"ja_registrada": True}
    if item is not None:
        try:
            conclusion = barreira_mundo.conclude(repo, pending_id, f"Task45 materializou {chosen} para {mid}")
        except (barreira_mundo.WorldPendingBarrierError, mundo.WorldEngineError) as exc:
            raise SidequestProgressionError(str(exc)) from exc
    else:
        conclusion = {"ja_concluida": completed}
    losses = None
    if loss_evidences is not None:
        try:
            losses = quest_rewards.apply_losses(
                repo,
                mid,
                evidences=loss_evidences,
                narration=loss_narration or narration,
            )
        except quest_rewards.QuestRewardError as exc:
            raise SidequestProgressionError(str(exc)) from exc
    return {
        "ok": True,
        "resultado": "consequencia_materializada",
        "mission_id": mid,
        "escalada_id": chosen,
        "transacao_id": activated["transacao"],
        "writer": writer,
        "pendencia": conclusion,
        "perdas": losses,
    }


def status(repo: Path, mission_ref: str) -> dict[str, Any]:
    _, mid, mission = _mission(repo, mission_ref)
    doc, rel = _load_progress(repo, mission, mid)
    changed = _sync_actor_availability(repo, doc)
    if changed:
        _atomic(repo / rel, doc)
    deadline = _deadline(mission)
    current = mundo.load_canonical_time(repo)[0] if (repo / mundo.TIME_PATH).is_file() else None
    return {
        "ok": True,
        "mission_id": mid,
        "quest_id": mission["quest_id"],
        "estado_missao": mission["estado"],
        "fases": copy.deepcopy(doc["estado"]["fases"]),
        "condicoes_sucesso": copy.deepcopy(doc["estado"]["condicoes_sucesso"]),
        "condicoes_falha": copy.deepcopy(doc["estado"]["condicoes_falha"]),
        "atores": copy.deepcopy(doc["estado"]["atores"]),
        "terminal": copy.deepcopy(doc["estado"]["terminal"]),
        "avaliacao": _evaluation(doc),
        "prazo": copy.deepcopy(doc["prazo"]),
        "prazo_vencido": bool(deadline and current and current.minute >= deadline.minute),
        "fontes_lidas": [oportunidades.STATE.as_posix(), rel.as_posix()],
    }


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    missions = contracts = 0
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
        if index["orcamento"]["max_ativas"] != 2:
            errors.append("Task45 depende de max_ativas=2 como autoridade existente")
        for mid, mission in state.get("missoes", {}).items():
            if not isinstance(mission, dict) or mission.get("origem") != "sidequest_emergente":
                continue
            missions += 1
            try:
                doc, _ = _load_progress(repo, mission, mid)
                _quest(repo, mission)
                quest_rewards._load_contract(repo, mission, mid)
                adversarial.load_contract(repo, mission)
                contracts += 1
                if len(_bytes(doc)) > MAX_FRAGMENT_BYTES:
                    raise SidequestProgressionError(f"{mid}: fragmento Task45 excede orçamento")
            except (SidequestProgressionError, quest_rewards.QuestRewardError, adversarial.AdversarialIntegrityError) as exc:
                errors.append(str(exc))
    except oportunidades.OpportunityError as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "erros": list(dict.fromkeys(errors)),
        "missoes_emergentes": missions,
        "contratos": contracts,
        "max_fragment_bytes": MAX_FRAGMENT_BYTES,
        "max_project_bytes": MAX_PROJECT_BYTES,
        "max_fatos": MAX_FACTS,
        "max_pendencias_task45": MAX_PENDING_TASK45,
        "scheduler_novo": 0,
        "rng_novo": 0,
        "scan_global": 0,
    }


def _stdin() -> dict[str, Any]:
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        return _map(yaml.safe_load(raw), "stdin")
    except yaml.YAMLError as exc:
        raise SidequestProgressionError(str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    reg = sub.add_parser("registrar-contrato"); reg.add_argument("mission_id")
    fact = sub.add_parser("fato"); fact.add_argument("mission_id")
    success = sub.add_parser("sucesso"); success.add_argument("mission_id"); success.add_argument("--narracao", required=True)
    failure = sub.add_parser("falha"); failure.add_argument("mission_id")
    resolve = sub.add_parser("resolver"); resolve.add_argument("mission_id"); resolve.add_argument("pending_id"); resolve.add_argument("escalada_id"); resolve.add_argument("--narracao", required=True)
    st = sub.add_parser("status"); st.add_argument("mission_id")
    sub.add_parser("reconciliar")
    sub.add_parser("check")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        payload = _stdin() if args.cmd in {"registrar-contrato", "fato", "sucesso", "resolver"} else {}
        if args.cmd == "registrar-contrato":
            out = register_contract(repo, args.mission_id, contract_raw=payload.get("contrato_progressao"))
        elif args.cmd == "fato":
            out = record_fact(repo, args.mission_id, fact_raw=payload.get("fato"))
        elif args.cmd == "sucesso":
            out = finalize_success(repo, args.mission_id, optional_ids=payload.get("opcionais"), evidences=payload.get("evidencias"), narration=args.narracao)
        elif args.cmd == "falha":
            out = finalize_failure(repo, args.mission_id)
        elif args.cmd == "resolver":
            out = resolve_pending(
                repo, args.mission_id, args.pending_id,
                chosen_escalation_id=args.escalada_id,
                proofs=payload.get("provas_escaladas") or {},
                blocker=payload.get("bloqueio"),
                narration=args.narracao,
                loss_evidences=payload.get("evidencias_perdas"),
                loss_narration=payload.get("narracao_perdas"),
            )
        elif args.cmd == "status":
            out = status(repo, args.mission_id)
        elif args.cmd == "reconciliar":
            out = reconcile(repo)
        else:
            out = check(repo)
        print(yaml.safe_dump(out, allow_unicode=True, sort_keys=False), end="")
        return 0 if out.get("ok") else 1
    except (SidequestProgressionError, mundo.WorldEngineError) as exc:
        print(yaml.safe_dump({"ok": False, "erro": str(exc)}, allow_unicode=True, sort_keys=False), end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
