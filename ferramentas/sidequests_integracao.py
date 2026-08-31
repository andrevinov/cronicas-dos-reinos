#!/usr/bin/env python3
"""Task 46 — Emergent Sidequests Integration & Budget Regression.

Esta camada liga as Tasks 40–45 à mesma dupla operacional ``cronica preparar`` /
``cronica concluir``. Ela é deliberadamente fria: sem sinal explícito de
``oportunidade_sidequest`` nenhuma função daqui é chamada pelo hot path.

No turno raro, ``preparar`` anexa o pacote read-only da Task40 ao resultado e põe
no ticket apenas uma âncora compacta + digest. ``concluir`` recomputa o pacote e
valida Task41/43/44/45 antes de qualquer escrita. Se a oferta realmente aparece
na narração, um único journal Task46 instala os quatro fragmentos reservados e o
registro de missão; retries reparam somente alvos ausentes e nunca duplicam a
sidequest.

O journal pode existir antes do registro normal do turno: ele é recovery técnico,
não cânone, missão, recompensa, NPC ou consequência. Assim uma falha do writer
não cria quest fantasma e o mesmo ``cronica concluir`` pode ser repetido.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Callable

import yaml

import _progressao_sidequests_task45_base as progress_base
import integridade_adversarial as adversarial
import oportunidade_sidequest as opportunity
import oportunidades
import recompensas_sidequest as quest_rewards
import sidequests_emergentes as emergent

SCHEMA = 1
TICKET_KEY = "sidequest_emergente_task46"
TRANSACTION_KEY = "sidequest_emergente"
JOURNAL = Path("runtime/sidequest-emergente-task46.yaml")
MAX_AUTHOR_PACKET_BYTES = 8 * 1024
MAX_COMBINED_PREP_BYTES = 16 * 1024
MAX_CANON_INTENTS = 3
MAX_INSTALL_TARGETS = 5


class EmergentSidequestIntegrationError(ValueError):
    """Contrato ou recuperação inválida da integração Task46."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _yaml(value: Any) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def _yaml_size(value: Any) -> int:
    return len(_yaml(value).encode("utf-8"))


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EmergentSidequestIntegrationError(f"{label} deve ser mapa")
    return value


def _text(value: Any, label: str, minimum: int = 1, maximum: int = 2000) -> str:
    if not isinstance(value, str):
        raise EmergentSidequestIntegrationError(f"{label} deve ser texto")
    text = " ".join(value.split())
    if not minimum <= len(text) <= maximum:
        raise EmergentSidequestIntegrationError(
            f"{label} deve ter entre {minimum} e {maximum} caracteres"
        )
    return text


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        tmp = Path(handle.name)
    os.replace(tmp, path)


def _atomic_yaml(path: Path, value: Any) -> None:
    _atomic_text(path, _yaml(value))


def _signal_from_raw(raw: Any) -> dict[str, Any]:
    data = copy.deepcopy(_map(raw, "oportunidade_sidequest"))
    expected = {
        "origem_tipo", "origem_id", "ancora_tipo", "ancora", "npc_id",
        "local_id", "periculosidade", "tier",
    }
    if set(data) != expected:
        raise EmergentSidequestIntegrationError(
            f"sinal Task46 divergente; faltando={sorted(expected-set(data))}; extras={sorted(set(data)-expected)}"
        )
    try:
        return opportunity._validate_signal(
            origin_type=data["origem_tipo"],
            origin_id=data["origem_id"],
            anchor_type=data["ancora_tipo"],
            anchor=data["ancora"],
            npc_id=data["npc_id"],
            local_id=data["local_id"],
            danger=data["periculosidade"],
            tier=data["tier"],
        )
    except opportunity.EmergentSidequestOpportunityError as exc:
        raise EmergentSidequestIntegrationError(str(exc)) from exc


def _signal_for_ticket(signal: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    now = _map(_map(package.get("prazo_mundo"), "pacote.prazo_mundo").get("agora"), "pacote.agora")
    return {
        "origem_tipo": signal["origem_tipo"],
        "origem_id": signal["origem_id"],
        "ancora_tipo": signal["ancora_tipo"],
        "ancora": signal["ancora"],
        "npc_id": signal["npc_id"],
        "local_id": signal["local_id"],
        "periculosidade": signal["periculosidade"],
        "tier": signal["tier"],
        "agora": {"data": str(now.get("data")), "hora": str(now.get("hora"))},
    }


def _plan_from_ticket(repo: Path, meta: dict[str, Any]) -> dict[str, Any]:
    signal = _map(meta.get("sinal"), "ticket.sinal")
    now_raw = _map(signal.get("agora"), "ticket.sinal.agora")
    try:
        opportunity.mundo.parse_instant(str(now_raw.get("data")), str(now_raw.get("hora")))
        package = opportunity.plan(
            repo,
            signaled=True,
            origin_type=signal.get("origem_tipo"),
            origin_id=signal.get("origem_id"),
            anchor_type=signal.get("ancora_tipo"),
            anchor=signal.get("ancora"),
            npc_id=signal.get("npc_id"),
            local_id=signal.get("local_id"),
            danger=str(signal.get("periculosidade")),
            tier=signal.get("tier"),
        )
    except (opportunity.EmergentSidequestOpportunityError, opportunity.mundo.WorldEngineError) as exc:
        raise EmergentSidequestIntegrationError(str(exc)) from exc
    if package.get("resultado") != "material_para_planejamento":
        raise EmergentSidequestIntegrationError(
            f"pacote Task40 deixou de estar disponível: {package.get('resultado')}"
        )
    current_now = _map(
        _map(package.get("prazo_mundo"), "pacote.prazo_mundo").get("agora"),
        "pacote.agora",
    )
    if {
        "data": str(current_now.get("data")),
        "hora": str(current_now.get("hora")),
    } != {
        "data": str(now_raw.get("data")),
        "hora": str(now_raw.get("hora")),
    }:
        raise EmergentSidequestIntegrationError(
            "tempo canônico mudou desde cronica preparar; descarte o ticket e prepare novamente"
        )
    if _digest(package) != meta.get("pacote_digest"):
        raise EmergentSidequestIntegrationError(
            "pacote Task40 mudou desde cronica preparar; descarte o ticket e prepare novamente"
        )
    return package


def integrate_prepare(
    repo: Path,
    base_result: dict[str, Any],
    *,
    signal_raw: Any,
    decode_ticket: Callable[[str], dict[str, Any]],
    encode_ticket: Callable[[dict[str, Any]], tuple[str, str]],
    now: Any | None = None,
) -> dict[str, Any]:
    """Anexa Task40 a uma preparação já existente sem mudar o caminho neutro."""
    signal = _signal_from_raw(signal_raw)
    try:
        package = opportunity.plan(
            repo,
            signaled=True,
            origin_type=signal["origem_tipo"],
            origin_id=signal["origem_id"],
            anchor_type=signal["ancora_tipo"],
            anchor=signal["ancora"],
            npc_id=signal["npc_id"],
            local_id=signal["local_id"],
            danger=signal["periculosidade"],
            tier=signal["tier"],
            now=now,
        )
    except opportunity.EmergentSidequestOpportunityError as exc:
        raise EmergentSidequestIntegrationError(str(exc)) from exc

    result = copy.deepcopy(base_result)
    result["sidequest_emergente"] = package
    result.setdefault("sistemas_narrativos", []).append("emergent_sidequest_opportunity")

    if package.get("resultado") != "material_para_planejamento":
        result["sidequest_emergente_task46"] = {
            "integrada_ao_ticket": False,
            "motivo": package.get("resultado"),
            "chamadas_orquestracao_adicionais": 0,
        }
        return result

    if _yaml_size(package) > MAX_AUTHOR_PACKET_BYTES:
        raise EmergentSidequestIntegrationError("pacote autoral Task40 excedeu 8 KiB")
    compatible = ((_map(package.get("horizonte_intencoes_canonicas"), "horizonte")).get("compativeis") or [])
    if len(compatible) > MAX_CANON_INTENTS:
        raise EmergentSidequestIntegrationError("Task40 expôs mais de três intenções canônicas")
    metrics = _map(package.get("metricas"), "pacote.metricas")
    if metrics.get("transcricao_lida") is not False or metrics.get("catalogo_task33_aberto") is not False:
        raise EmergentSidequestIntegrationError("Task46 recusou pacote que abriu transcrição/Task33")

    token = result.get("ticket")
    if not isinstance(token, str):
        raise EmergentSidequestIntegrationError("preparação cronica não retornou ticket")
    payload = copy.deepcopy(decode_ticket(token))
    payload[TICKET_KEY] = {
        "schema": SCHEMA,
        "sinal": _signal_for_ticket(signal, package),
        "pacote_digest": _digest(package),
    }
    new_token, new_id = encode_ticket(payload)
    result["ticket"] = new_token
    result["ticket_id"] = new_id
    result["sidequest_emergente_task46"] = {
        "integrada_ao_ticket": True,
        "pacote_bytes": _yaml_size(package),
        "intencoes_candidatas": len(compatible),
        "chamadas_orquestracao_adicionais": 0,
        "regra": "autorar nesta mesma inferência; concluir materializa somente se a oferta realmente for narrada",
    }
    total = _yaml_size(result)
    if total > MAX_COMBINED_PREP_BYTES:
        raise EmergentSidequestIntegrationError(
            f"preparação rara Task46 excede {MAX_COMBINED_PREP_BYTES} bytes: {total}"
        )
    return result


def ticket_meta(payload: dict[str, Any]) -> dict[str, Any] | None:
    raw = payload.get(TICKET_KEY)
    if raw is None:
        return None
    meta = _map(raw, TICKET_KEY)
    if set(meta) != {"schema", "sinal", "pacote_digest"} or meta.get("schema") != SCHEMA:
        raise EmergentSidequestIntegrationError("metadados Task46 do ticket são inválidos")
    digest = meta.get("pacote_digest")
    if not isinstance(digest, str) or len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise EmergentSidequestIntegrationError("digest Task40 inválido no ticket")
    _map(meta.get("sinal"), "ticket.sinal")
    return copy.deepcopy(meta)


def strip_ticket_payload(payload: dict[str, Any]) -> dict[str, Any]:
    clean = copy.deepcopy(payload)
    clean.pop(TICKET_KEY, None)
    return clean


def _normalize_offer(transaction: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    raw = transaction.get(TRANSACTION_KEY)
    if raw is None:
        return None, None
    block = copy.deepcopy(_map(raw, TRANSACTION_KEY))
    expected = {"oferta", "quest", "contrato_recompensa", "contrato_adversarial", "contrato_progressao"}
    if set(block) != expected:
        raise EmergentSidequestIntegrationError(
            f"bloco sidequest_emergente divergente; faltando={sorted(expected-set(block))}; extras={sorted(set(block)-expected)}"
        )
    offer = _map(block["oferta"], "sidequest_emergente.oferta")
    if set(offer) != {"materializar", "evidencia", "resumo"} or offer.get("materializar") is not True:
        raise EmergentSidequestIntegrationError(
            "oferta Task46 exige materializar=true, evidencia literal e resumo"
        )
    evidence = _text(offer["evidencia"], "oferta.evidencia", 8, 400)
    summary = _text(offer["resumo"], "oferta.resumo", 20, 320)
    narration = _text(transaction.get("narracao"), "transacao.narracao", 1, 12000)
    if evidence not in " ".join(narration.split()):
        raise EmergentSidequestIntegrationError(
            "oferta Task46 não aparece literalmente na narração; sem oferta efetiva não nasce quest"
        )
    return block, {"evidencia": evidence, "resumo": summary}


def _reward_doc(
    repo: Path,
    *,
    qid: str,
    mid: str,
    quest_doc: dict[str, Any],
    package: dict[str, Any],
    raw: Any,
) -> tuple[dict[str, Any], Path]:
    try:
        contract = quest_rewards._normalize_contract(repo, raw, quest_doc, package)
    except quest_rewards.QuestRewardError as exc:
        raise EmergentSidequestIntegrationError(str(exc)) from exc
    rel = quest_rewards._contract_rel(qid)
    doc = {
        "schema_recompensas_sidequest": quest_rewards.SCHEMA,
        "natureza": "reservado",
        "mission_id": mid,
        "quest_id": qid,
        "quest_file": emergent._quest_path(qid).as_posix(),
        "pacote_task40_digest": quest_doc["pacote_task40_digest"],
        "contrato_recompensa": contract,
        "estado": quest_rewards._initial_state(contract),
        "guardrails": {
            "descoberta_nao_e_obtencao": True,
            "perda_exige_contrato_e_prova": True,
            "efeito_real_transacional": True,
            "scheduler": "proibido",
        },
    }
    return doc, rel


def _adversarial_doc(
    repo: Path,
    *,
    package: dict[str, Any],
    quest_raw: Any,
    qid: str,
    mid: str,
    raw: Any,
) -> tuple[dict[str, Any], Path]:
    try:
        _, _, contract, sources = adversarial.normalize_contract(repo, package, quest_raw, raw)
        prep_id = adversarial._prep_id(qid, contract, sources, repo)
    except adversarial.AdversarialIntegrityError as exc:
        raise EmergentSidequestIntegrationError(str(exc)) from exc
    rel = adversarial._contract_path(qid)
    return {
        "schema_integridade_adversarial": adversarial.SCHEMA,
        "natureza": "reservado",
        "quest_id": qid,
        "mission_id": mid,
        "preparacao_id": prep_id,
        "contrato_digest": adversarial._digest(contract),
        "contrato": contract,
        "guardrails": {
            "sem_plot_armor_por_conveniencia": True,
            "sem_onisciencia_de_antagonista": True,
            "sem_escalada_sem_capacidade": True,
            "sem_amaciamento_de_escalada_obrigatoria": True,
            "consequencia_real_exige_evidencia_causal": True,
            "execucao_terminal_reservada_task45": True,
        },
        "historico_recente": [],
    }, rel


def _progress_doc(
    *,
    qid: str,
    mid: str,
    mission: dict[str, Any],
    quest_doc: dict[str, Any],
    reward_rel: Path,
    adversarial_rel: Path,
    adversarial_doc: dict[str, Any],
    raw: Any,
) -> tuple[dict[str, Any], Path]:
    data = copy.deepcopy(_map(raw, "contrato_progressao"))
    expected = {"regra_sucesso", "regra_falha", "dependencias_fases", "efeitos_escaladas"}
    if set(data) != expected:
        raise EmergentSidequestIntegrationError("contrato_progressao possui estrutura inesperada")
    try:
        success_rule = progress_base._slug(data["regra_sucesso"], "regra_sucesso")
        failure_rule = progress_base._slug(data["regra_falha"], "regra_falha")
        if success_rule not in progress_base.SUCCESS_RULES or failure_rule not in progress_base.FAILURE_RULES:
            raise progress_base.SidequestProgressionError(
                "regra_sucesso/regra_falha deve ser todas ou qualquer"
            )
        actors, new_ids = progress_base._actor_ids(quest_doc)
        dependencies = progress_base._normalize_dependencies(
            data["dependencias_fases"], quest_doc, set(actors)
        )
        adv_contract = _map(adversarial_doc.get("contrato"), "contrato_adversarial.normalizado")
        effects = progress_base._normalize_effects(data["efeitos_escaladas"], adv_contract)
    except progress_base.SidequestProgressionError as exc:
        raise EmergentSidequestIntegrationError(str(exc)) from exc
    rel = progress_base._progress_rel(qid)
    doc = {
        "schema_progressao_sidequest": progress_base.SCHEMA,
        "natureza": "reservado",
        "mission_id": mid,
        "quest_id": qid,
        "quest_file": mission["arquivo"],
        "contrato_recompensa": reward_rel.as_posix(),
        "contrato_adversarial": adversarial_rel.as_posix(),
        "prazo": copy.deepcopy(mission.get("janela")),
        "contrato": {
            "regra_sucesso": success_rule,
            "regra_falha": failure_rule,
            "dependencias_fases": dependencies,
            "efeitos_escaladas": effects,
            "escaladas_falha": list(adv_contract["consequencias_de_falha"]),
            "escaladas_inacao": list(adv_contract["consequencias_de_inacao"]),
        },
        "atores_novos_reservados": sorted(new_ids),
        "estado": progress_base._initial_state(quest_doc, actors),
        "guardrails": {
            "progresso_por_fato_nao_checklist": True,
            "prazo_usa_relogio_existente": True,
            "sem_scheduler": True,
            "consequencia_so_task44": True,
            "recompensa_so_task43_apos_sucesso": True,
            "canon_terminal_via_task42": True,
        },
    }
    if _yaml_size(doc) > progress_base.MAX_FRAGMENT_BYTES:
        raise EmergentSidequestIntegrationError("fragmento Task45 excede orçamento")
    return doc, rel


def prepare_installation(
    repo: Path,
    *,
    package: dict[str, Any],
    block: dict[str, Any],
    offer_scene_id: str,
    offer_summary: str,
) -> dict[str, Any]:
    """Valida Task41/43/44/45 e monta os bytes finais sem escrever."""
    quest_raw = block["quest"]
    try:
        package_n, spec, reference_sources = emergent.normalize_spec(repo, package, quest_raw)
        qid = emergent._quest_id(package_n, spec)
        mid = emergent.mission_id(qid)
        _, _, budget_sources, existing = emergent._budget_state(repo, qid=qid)
        sources = [*reference_sources, *budget_sources]
        prep_id = emergent._preparation_id(repo, package_n, spec, sources)
    except emergent.EmergentSidequestAuthoringError as exc:
        raise EmergentSidequestIntegrationError(str(exc)) from exc
    if existing is not None:
        raise EmergentSidequestIntegrationError("Task46 não materializa por cima de quest já existente")

    scene = emergent._id(offer_scene_id, "oferta.cena_id")
    summary = emergent._text(offer_summary, "oferta.resumo", minimum=20, maximum=320)
    quest_doc = emergent._quest_document(
        qid=qid,
        preparation_id=prep_id,
        package=package_n,
        spec=spec,
        offer_scene_id=scene,
        offer_summary=summary,
    )
    mission = emergent._mission_record(
        qid=qid,
        spec=spec,
        package=package_n,
        preparation_id=prep_id,
        offer_scene_id=scene,
    )
    reward_doc, reward_rel = _reward_doc(
        repo, qid=qid, mid=mid, quest_doc=quest_doc, package=package_n,
        raw=block["contrato_recompensa"],
    )
    adv_doc, adv_rel = _adversarial_doc(
        repo, package=package_n, quest_raw=quest_raw, qid=qid, mid=mid,
        raw=block["contrato_adversarial"],
    )
    mission["contrato_recompensa"] = reward_rel.as_posix()
    progress_doc, progress_rel = _progress_doc(
        qid=qid,
        mid=mid,
        mission=mission,
        quest_doc=quest_doc,
        reward_rel=reward_rel,
        adversarial_rel=adv_rel,
        adversarial_doc=adv_doc,
        raw=block["contrato_progressao"],
    )
    mission["progresso_sidequest"] = progress_rel.as_posix()
    return {
        "schema": SCHEMA,
        "quest_id": qid,
        "mission_id": mid,
        "package": package_n,
        "package_digest": _digest(package_n),
        "quest_path": emergent._quest_path(qid).as_posix(),
        "quest_doc": quest_doc,
        "reward_path": reward_rel.as_posix(),
        "reward_doc": reward_doc,
        "adversarial_path": adv_rel.as_posix(),
        "adversarial_doc": adv_doc,
        "progress_path": progress_rel.as_posix(),
        "progress_doc": progress_doc,
        "mission": mission,
    }


def _journal_id(ticket_id: str, transaction: dict[str, Any], plan: dict[str, Any]) -> str:
    return "sq46-" + _digest({
        "ticket_id": ticket_id,
        "transacao": transaction,
        "mission_id": plan["mission_id"],
        "package_digest": plan["package_digest"],
    })[:24]


def _load_journal(repo: Path) -> dict[str, Any] | None:
    path = repo / JOURNAL
    if not path.is_file():
        return None
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise EmergentSidequestIntegrationError(f"journal Task46 inválido: {exc}") from exc
    return _map(value, "journal Task46")


def begin_conclusion(
    repo: Path,
    *,
    ticket_id: str,
    transaction: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Congela recovery técnico depois de todas as validações e antes do writer."""
    jid = _journal_id(ticket_id, transaction, plan)
    existing = _load_journal(repo)
    if existing is not None:
        if existing.get("id") != jid:
            raise EmergentSidequestIntegrationError(
                "há outra conclusão Task46 interrompida; repita primeiro o cronica concluir original"
            )
        return existing
    journal = {
        "schema_task46_journal": SCHEMA,
        "id": jid,
        "ticket_id": ticket_id,
        "transaction_digest": _digest(transaction),
        "fase": "validada_aguardando_turno",
        "plan": copy.deepcopy(plan),
        "targets": None,
    }
    _atomic_yaml(repo / JOURNAL, journal)
    return journal


def _fresh_state_target(repo: Path, plan: dict[str, Any]) -> tuple[dict[str, Any], str]:
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise EmergentSidequestIntegrationError(str(exc)) from exc
    mid = plan["mission_id"]
    old = state["missoes"].get(mid)
    if isinstance(old, dict):
        if old == plan["mission"]:
            return state, _yaml(state)
        raise EmergentSidequestIntegrationError(f"colisão de mission_id Task46: {mid}")
    active, opened = oportunidades._mission_counts(state)
    if active >= index["orcamento"]["max_ativas"]:
        raise EmergentSidequestIntegrationError("limite_ativas")
    if opened >= index["orcamento"]["max_em_aberto"]:
        raise EmergentSidequestIntegrationError("limite_abertas")
    state["missoes"][mid] = copy.deepcopy(plan["mission"])
    package = plan["package"]
    state["historico_recente"].append({
        "tipo": "sidequest_emergente_materializada_task46",
        "id": mid,
        "quest_id": plan["quest_id"],
        "npc_id": plan["mission"]["npc_id"],
        "em": copy.deepcopy(package["prazo_mundo"]["agora"]),
    })
    state["historico_recente"] = state["historico_recente"][-oportunidades.MAX_HISTORY:]
    return state, _yaml(state)


def _freeze_targets(repo: Path, journal: dict[str, Any]) -> dict[str, Any]:
    if isinstance(journal.get("targets"), list):
        return journal
    plan = _map(journal.get("plan"), "journal.plan")
    _, state_text = _fresh_state_target(repo, plan)
    targets = [
        {"path": plan["quest_path"], "content": _yaml(plan["quest_doc"])},
        {"path": plan["reward_path"], "content": _yaml(plan["reward_doc"])},
        {"path": plan["adversarial_path"], "content": _yaml(plan["adversarial_doc"])},
        {"path": plan["progress_path"], "content": _yaml(plan["progress_doc"])},
        {"path": oportunidades.STATE.as_posix(), "content": state_text},
    ]
    if len(targets) != MAX_INSTALL_TARGETS:
        raise EmergentSidequestIntegrationError("Task46 perdeu alvo da instalação transacional")
    journal = copy.deepcopy(journal)
    journal["targets"] = [
        {**target, "sha256": hashlib.sha256(target["content"].encode("utf-8")).hexdigest()}
        for target in targets
    ]
    journal["fase"] = "instalando_sidequest"
    _atomic_yaml(repo / JOURNAL, journal)
    return journal


def install(repo: Path, journal: dict[str, Any]) -> dict[str, Any]:
    """Uma instalação Task46 multi-arquivo, journalada e idempotente."""
    journal = _freeze_targets(repo, journal)
    changed: list[str] = []
    for target in journal["targets"]:
        rel = Path(str(target["path"]))
        path = repo / rel
        content = str(target["content"])
        if path.is_file():
            existing = path.read_text(encoding="utf-8")
            if existing == content:
                continue
            # O estado de oportunidades é congelado no início da instalação; se
            # divergir no meio, não sobrescrevemos causalidade concorrente.
            raise EmergentSidequestIntegrationError(
                f"alvo Task46 divergiu durante instalação: {rel.as_posix()}"
            )
        _atomic_text(path, content)
        changed.append(rel.as_posix())
    # STATE sempre existe no repo, então o loop acima o veria como divergente.
    # Aplicamos o estado por último somente se ainda não contém a missão; isto
    # mantém os quatro fragmentos órfãos recuperáveis e a missão como commit point.
    state_target = journal["targets"][-1]
    state_path = repo / Path(str(state_target["path"]))
    desired_state = str(state_target["content"])
    current_state = state_path.read_text(encoding="utf-8") if state_path.is_file() else ""
    if current_state != desired_state:
        try:
            current = oportunidades.load_state(repo, oportunidades.load_index(repo))
        except oportunidades.OpportunityError as exc:
            raise EmergentSidequestIntegrationError(str(exc)) from exc
        mid = journal["plan"]["mission_id"]
        existing_mission = current["missoes"].get(mid)
        if isinstance(existing_mission, dict):
            if existing_mission != journal["plan"]["mission"]:
                raise EmergentSidequestIntegrationError("missão Task46 já existe com conteúdo divergente")
        else:
            # Nenhuma outra mutação de oportunidades pode ser silenciosamente
            # perdida entre freeze e commit point.
            frozen = yaml.safe_load(desired_state)
            without = copy.deepcopy(frozen)
            without["missoes"].pop(mid, None)
            without["historico_recente"] = [
                item for item in without.get("historico_recente") or []
                if not (isinstance(item, dict) and item.get("id") == mid and item.get("tipo") == "sidequest_emergente_materializada_task46")
            ]
            if current != without:
                raise EmergentSidequestIntegrationError(
                    "estado de oportunidades mudou durante instalação Task46; repita após reconciliar"
                )
            _atomic_text(state_path, desired_state)
            changed.append(oportunidades.STATE.as_posix())
    (repo / JOURNAL).unlink(missing_ok=True)
    return {
        "ok": True,
        "resultado": "sidequest_materializada",
        "mission_id": journal["plan"]["mission_id"],
        "quest_id": journal["plan"]["quest_id"],
        "transacao_instalacao": journal["id"],
        "arquivos_alterados": changed,
        "instalacoes_logicas": 1,
        "idempotente": True,
    }


def recover_matching_journal(
    repo: Path, *, ticket_id: str, transaction: dict[str, Any]
) -> dict[str, Any] | None:
    journal = _load_journal(repo)
    if journal is None:
        return None
    if journal.get("ticket_id") != ticket_id or journal.get("transaction_digest") != _digest(transaction):
        raise EmergentSidequestIntegrationError(
            "há uma conclusão Task46 interrompida com outro ticket/transação"
        )
    return journal


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        if MAX_AUTHOR_PACKET_BYTES != opportunity.MAX_PAYLOAD_BYTES:
            errors.append("teto Task46 do pacote autoral diverge da Task40")
        if MAX_CANON_INTENTS != opportunity.MAX_CANON_INTENTS:
            errors.append("teto Task46 de intenções diverge da Task40")
        index = oportunidades.load_index(repo)
        if index.get("nova_origem_sidequests") not in {
            "emergente_causal_task40", "canonica_explicita"
        }:
            errors.append("origem operacional de sidequests desconhecida")
        journal = _load_journal(repo)
        if journal is not None and journal.get("schema_task46_journal") != SCHEMA:
            errors.append("journal Task46 possui schema inesperado")
    except (EmergentSidequestIntegrationError, oportunidades.OpportunityError, OSError, yaml.YAMLError) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "erros": errors,
        "contrato": {
            "turno_neutro_leituras_task40_45": 0,
            "turno_neutro_fragmentos_emergentes": 0,
            "turno_neutro_horizonte_canonico": 0,
            "chamadas_orquestracao": 2,
            "pacote_autoral_max_bytes": MAX_AUTHOR_PACKET_BYTES,
            "intencoes_max": MAX_CANON_INTENTS,
            "instalacoes_por_oferta": 1,
            "schedulers_novos": 0,
            "relogios_novos": 0,
        },
    }
