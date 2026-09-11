#!/usr/bin/env python3
"""Planos até NV-19 + desafios causais dependentes de reconhecimento da NV-20.

``desafio_persona`` é uma especialização do mesmo plano NV-08. Não escolhe
challenger, não agenda por fora do Mundo Vivo e não resolve o confronto. Ele só
pode ser criado para um ator explícito cuja motivação, conhecimento, alcance,
interesse, stakes, proteções e reconhecimento da persona sejam comprovados.
"""
from __future__ import annotations

from pathlib import Path

_LEGACY_SOURCE = Path(__file__).with_name("_planos_personagens_nv19.py")
_saved_name = globals().get("__name__", "planos_personagens")
globals()["__name__"] = "_planos_personagens_nv19_exec"
exec(compile(_LEGACY_SOURCE.read_text(encoding="utf-8"), str(_LEGACY_SOURCE), "exec"), globals(), globals())
globals()["__name__"] = _saved_name

import reconhecibilidade_persona as _recognition

_BASE_STEP_NV19 = _step
_BASE_CONTROL_NV19 = _control
_BASE_GATES_NV19 = _gates
_BASE_VALIDATE_REGISTRATION_NV19 = validate_registration
_BASE_PROJECT_PENDING_NV19 = project_pending

CHALLENGE_TYPE = "desafio_persona"
CHALLENGE_KEY = "desafio_persona"
CHALLENGE_INTERESTS = {"marcial", "social", "misto"}
MAX_CHALLENGE_PROJECTION_BYTES = 4096


def _positive_ref(value, label: str):
    ref = _ref(value)
    if ref["valor"] in (None, False, "", [], {}):
        raise PlanError(f"{label} precisa apontar fato canônico positivo")
    return ref


def _challenge_meta(step: dict) -> dict | None:
    raw = step.get(CHALLENGE_KEY) if isinstance(step, dict) else None
    if raw is None:
        return None
    if ENTRY_KEY in step:
        raise PlanError("desafio_persona e entrada_local são passos distintos; não fundir chegada e desafio")
    meta = _map(raw, CHALLENGE_KEY)
    required = {
        "persona", "reconhecimento", "motivacao", "conhecimento_persona",
        "alcance", "interesse", "stakes", "protecoes",
    }
    if set(meta) != required:
        raise PlanError(
            "desafio_persona exige persona, reconhecimento, motivacao, conhecimento_persona, "
            "alcance, interesse, stakes e protecoes"
        )
    persona = _id(meta["persona"])
    recognition = _map(meta["reconhecimento"], "reconhecimento")
    if set(recognition) != {
        "audiencia", "localidade", "marco_publico", "confianca_minima", "atribuicao_minima"
    }:
        raise PlanError("reconhecimento exige audiência, localidade, marco, confiança e atribuição mínimas")
    _id(recognition["audiencia"])
    _text(recognition["localidade"], "localidade de reconhecimento", 96)
    _id(recognition["marco_publico"])
    if recognition["confianca_minima"] not in _recognition.CONFIDENCES:
        raise PlanError("confianca_minima de reconhecimento inválida")
    if recognition["atribuicao_minima"] not in _recognition.ATTRIBUTIONS:
        raise PlanError("atribuicao_minima de reconhecimento inválida")
    _positive_ref(meta["motivacao"], "motivação do desafio")
    knowledge = _id(meta["conhecimento_persona"])
    if knowledge not in step.get("conhecimento", []):
        raise PlanError("conhecimento_persona precisa integrar passo.conhecimento")
    reach = _map(meta["alcance"], "alcance")
    if reach.get("tipo") == "fisico":
        if set(reach) != {"tipo", "local"}:
            raise PlanError("alcance físico exige somente tipo e local")
        if _text(reach["local"], "local de alcance", 120) != step.get("local"):
            raise PlanError("alcance físico precisa coincidir com passo.local")
    elif reach.get("tipo") == "canal":
        if set(reach) != {"tipo", "persona", "referencia"} or reach.get("persona") != persona:
            raise PlanError("alcance por canal exige tipo, a persona-alvo e referência canônica")
        _positive_ref(reach["referencia"], "canal do desafio")
    else:
        raise PlanError("alcance do desafio deve ser fisico ou canal")
    interest = _map(meta["interesse"], "interesse")
    if set(interest) != {"tipo", "referencia"} or interest.get("tipo") not in CHALLENGE_INTERESTS:
        raise PlanError("interesse exige tipo marcial/social/misto e referência canônica")
    _positive_ref(interest["referencia"], "interesse do desafio")
    stakes = _map(meta["stakes"], "stakes")
    if set(stakes) != {"descricao", "se_aceito", "se_recusado"}:
        raise PlanError("stakes exigem descricao, se_aceito e se_recusado")
    for key in ("descricao", "se_aceito", "se_recusado"):
        _text(stakes[key], f"stakes.{key}", 360)
    protections = _items(meta["protecoes"], "protecoes", 4)
    for ref in protections:
        parsed = _ref(ref)
        if parsed["valor"] is not True:
            raise PlanError("proteção canônica do desafio precisa provar compatibilidade=true")
    resolution = step.get("resolucao") or {}
    if resolution.get("tipo") not in {"factual", "contato"}:
        raise PlanError("desafio_persona planeja a abordagem, não resolve combate/teste/operação")
    if reach["tipo"] == "canal":
        if resolution.get("tipo") != "contato" or resolution.get("canal") != reach["referencia"]:
            raise PlanError("desafio por canal reutiliza a resolução contato e a mesma referência de canal")
        if resolution.get("causa") != meta["motivacao"]:
            raise PlanError("contato do desafio precisa reutilizar a motivação como causa")
    if _size(meta) > 2600:
        raise PlanError("desafio_persona excede 2600 bytes")
    return meta


def _step(value: Any) -> dict:
    if not isinstance(value, dict) or CHALLENGE_KEY not in value:
        return _BASE_STEP_NV19(value)
    legacy = deepcopy(value)
    raw = legacy.pop(CHALLENGE_KEY)
    _BASE_STEP_NV19(legacy)
    full = deepcopy(value)
    full[CHALLENGE_KEY] = raw
    _challenge_meta(full)
    if _size(full) > 4200:
        raise PlanError("passo desafio_persona excede 4200 bytes")
    return full


def is_challenge_plan(plan: Any) -> bool:
    return (
        isinstance(plan, dict)
        and isinstance(plan.get("passo"), dict)
        and isinstance(plan["passo"].get(CHALLENGE_KEY), dict)
    )


def _control(world: dict) -> dict:
    control = _BASE_CONTROL_NV19(world)
    active: dict[tuple[str, str], str] = {}
    for pid, plan in control.items():
        special = is_challenge_plan(plan)
        if special:
            if plan.get("tipo") not in (None, CHALLENGE_TYPE):
                raise PlanError("plano com contrato desafio_persona possui tipo divergente")
            plan["tipo"] = CHALLENGE_TYPE
            meta = _challenge_meta(plan["passo"])
            assert meta is not None
            if plan["estado"] not in TERMINAL:
                key = (plan["agente"]["id"], meta["persona"])
                previous = active.get(key)
                if previous is not None and previous != pid:
                    raise PlanError("o mesmo ator não pode manter dois desafios ativos contra a mesma persona")
                active[key] = pid
        elif plan.get("tipo") == CHALLENGE_TYPE:
            raise PlanError("tipo desafio_persona exige contrato no passo")
    return control


def _actor_knowledge(view: View, plan: dict, meta: dict, profile: dict) -> dict:
    aid = plan["agente"]["id"]
    npc_source = view.npc_path(aid)
    npc = view.read(npc_source)["npc"]
    rows = [
        item for item in [*profile.get("conhecimento", []), *npc.get("conhecimento", [])]
        if isinstance(item, dict) and item.get("id") == meta["conhecimento_persona"]
    ]
    if len(rows) != 1:
        raise PlanError("desafio exige exatamente um conhecimento próprio e dirigido da persona")
    knowledge = rows[0]
    if knowledge.get("persona") != meta["persona"]:
        raise PlanError("conhecimento do desafiante não identifica a persona-alvo declarada")
    source = _text(knowledge.get("fonte"), "fonte de conhecimento")
    evidence = _text(knowledge.get("evidencia"), "evidência de conhecimento", 520)
    if not _contains_text(view.read(source), evidence):
        raise PlanError("evidência do conhecimento da persona deixou de existir")
    return knowledge


def _challenge_requirements(view: View, plan: dict) -> tuple[list[str], dict | None]:
    blockers: list[str] = []
    projection = None
    meta = _challenge_meta(plan["passo"])
    if meta is None:
        return blockers, projection
    try:
        profile, sources = _actor(view, plan["agente"])
        if plan["objetivo"] not in _objectives(profile):
            raise PlanError("objetivo do desafio deixou de corresponder à motivação canônica do ator")
        npc_source = view.npc_path(plan["agente"]["id"])
        owned_sources = set(sources) | {npc_source}
        for label, ref in (
            ("motivação", meta["motivacao"]),
            ("interesse", meta["interesse"]["referencia"]),
        ):
            if ref["arquivo"] not in owned_sources:
                raise PlanError(f"{label} do desafio precisa pertencer ao próprio ator")
            view.value(ref)
        _actor_knowledge(view, plan, meta, profile)
        rec = meta["reconhecimento"]
        projection = _recognition.query(
            view.repo,
            persona=meta["persona"],
            audience=rec["audiencia"],
            locality=rec["localidade"],
            records=view.records,
        )
        if not _recognition.meets_requirement(
            projection,
            milestone=rec["marco_publico"],
            min_confidence=rec["confianca_minima"],
            min_attribution=rec["atribuicao_minima"],
        ):
            blockers.append("reconhecimento público ainda não sustenta este desafio")
        reach = meta["alcance"]
        if reach["tipo"] == "fisico":
            if not presence_at(view, plan["agente"]["id"], reach["local"]):
                blockers.append("ator não possui alcance físico atual para emitir o desafio")
        else:
            ref = reach["referencia"]
            if ref["arquivo"] not in owned_sources:
                raise PlanError("canal de desafio precisa pertencer ao próprio ator")
            channel = view.value(ref)
            if isinstance(channel, dict):
                if channel.get("disponivel") is not True:
                    blockers.append("canal do desafio não está disponível")
            elif not channel:
                blockers.append("canal do desafio não está disponível")
        for ref in meta["protecoes"]:
            view.value(ref)
    except (ValueError, OSError, yaml.YAMLError, _recognition.RecognizabilityError) as exc:
        blockers.append(str(exc))
    return list(dict.fromkeys(blockers)), projection


def _gates(view: View, plan: dict, now: mundo.WorldInstant) -> list[str]:
    blockers = list(_BASE_GATES_NV19(view, plan, now))
    if not is_challenge_plan(plan):
        return blockers
    extra, _projection = _challenge_requirements(view, plan)
    return list(dict.fromkeys([*blockers, *extra]))


def _introduced_challenge(event: dict) -> dict | None:
    step = event.get("passo")
    return step if isinstance(step, dict) and isinstance(step.get(CHALLENGE_KEY), dict) else None


def _candidate_for_definition(repo: Path, prior: list[dict], pid: str, event: dict) -> dict | None:
    step = _introduced_challenge(event)
    if step is None:
        return None
    if event.get("evento") == "definir":
        return {
            "id": pid,
            "agente": deepcopy(event["agente"]),
            "objetivo": event["objetivo"],
            "passo": deepcopy(step),
            "estado": "pretende",
            "revisao": event["revisao"] + 1,
            "ultima_tentativa": None,
            "pendencia_id": None,
        }
    old = _effective_plan_before(Path(repo), prior, pid)
    if old is None:
        raise PlanError("novo desafio exige plano existente ou evento definir")
    candidate = deepcopy(old)
    candidate["passo"] = deepcopy(step)
    candidate["estado"] = "pretende"
    return candidate


def validate_registration(repo: Path, transaction: dict, record: dict, prior: list[dict]) -> None:
    for delta in events(record):
        event = delta.get("valor") or {}
        pid = delta["alvo"][len(PREFIX):]
        candidate = _candidate_for_definition(Path(repo), prior, pid, event)
        if candidate is None:
            continue
        view = View(Path(repo), prior)
        blockers, _projection = _challenge_requirements(view, candidate)
        if blockers:
            raise PlanError("desafio_persona não pode ser planejado: " + "; ".join(blockers))
    _BASE_VALIDATE_REGISTRATION_NV19(Path(repo), transaction, record, prior)


def project_pending(repo: Path, pending: dict) -> dict:
    result = _BASE_PROJECT_PENDING_NV19(Path(repo), pending)
    plan = result.get("plano")
    if not is_challenge_plan(plan):
        return result
    meta = _challenge_meta(plan["passo"])
    assert meta is not None
    view = View(Path(repo), transacoes.load_pending(Path(repo)))
    extra, projection = _challenge_requirements(view, plan)
    result["bloqueios"] = list(dict.fromkeys([*(result.get("bloqueios") or []), *extra]))
    result[CHALLENGE_KEY] = {
        "tipo": CHALLENGE_TYPE,
        "persona": meta["persona"],
        "ator": deepcopy(plan["agente"]),
        "reconhecimento": deepcopy(projection) if projection is not None else None,
        "marco_causal": meta["reconhecimento"]["marco_publico"],
        "alcance": {"tipo": meta["alcance"]["tipo"]},
        "interesse": meta["interesse"]["tipo"],
        "stakes": deepcopy(meta["stakes"]),
        "protecoes_verificadas": len(meta["protecoes"]),
        "regra": (
            "fama não gera desafiante aleatório: este plano pertence ao ator explícito e "
            "depende de motivação, conhecimento, alcance, interesse, stakes e proteções"
        ),
    }
    if projection is not None:
        result["fontes_lidas"] = list(dict.fromkeys([
            *(result.get("fontes_lidas") or []), *(projection.get("fontes_lidas") or [])
        ]))
    if _size(result[CHALLENGE_KEY]) > MAX_CHALLENGE_PROJECTION_BYTES:
        raise PlanError("projeção desafio_persona excede orçamento")
    return result


def challenge_fame_reference(repo: Path, *, persona: str, audience: str, locality: str, milestone: str) -> dict:
    """Retorna a causa canônica que também pode alimentar uma entrada_local NV-19."""
    projection = _recognition.query(
        Path(repo), persona=persona, audience=audience, locality=locality
    )
    match = next(
        (item for item in projection["eventos"] if item["marco_publico"] == milestone),
        None,
    )
    if match is None:
        raise PlanError("marco de fama não existe na consulta dirigida")
    state = _recognition._effective_state(
        Path(repo), _recognition.load_audiences(Path(repo)),
        _recognition.load_identities(Path(repo)), None
    )[0]
    event = state["eventos"].get(match["id"])
    if event is None:
        raise PlanError("evento de fama desapareceu durante a consulta")
    return _recognition.event_reference(event)
