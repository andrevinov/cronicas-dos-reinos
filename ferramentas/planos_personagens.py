#!/usr/bin/env python3
"""Planos de personagens até a NV-18 + entradas locais causais da NV-19.

A implementação anterior fica congelada em ``_planos_personagens_nv18.py`` e é
executada neste mesmo namespace. A NV-19 não cria scheduler: ``entrada_local`` é
um tipo especializado do plano NV-08, usa a mesma agenda, a mesma pendência do
Mundo Vivo e o mesmo journal transacional.
"""
from __future__ import annotations

from pathlib import Path

_LEGACY_SOURCE = Path(__file__).with_name("_planos_personagens_nv18.py")
_saved_name = globals().get("__name__", "planos_personagens")
globals()["__name__"] = "_planos_personagens_nv18_exec"
exec(compile(_LEGACY_SOURCE.read_text(encoding="utf-8"), str(_LEGACY_SOURCE), "exec"), globals(), globals())
globals()["__name__"] = _saved_name

_BASE_STEP = _step
_BASE_CONTROL = _control
_BASE_GATES = _gates
_BASE_VALIDATE_REGISTRATION = validate_registration
_BASE_PROJECT_PENDING = project_pending
_BASE_COMPILE_BATCH = compile_batch

ENTRY_TYPE = "entrada_local"
ENTRY_KEY = "entrada_local"
MAX_ENTRY_PROJECTION_BYTES = 3072


def _entry_meta(step: dict) -> dict | None:
    raw = step.get(ENTRY_KEY) if isinstance(step, dict) else None
    if raw is None:
        return None
    meta = _map(raw, ENTRY_KEY)
    required = {
        "causa", "origem", "destino", "janela", "duracao_esperada_minutos",
        "conhecimento_necessario", "disponibilidade", "recursos_necessarios",
        "motivo_presenca",
    }
    if set(meta) != required:
        raise PlanError(
            "entrada_local exige causa, origem, destino, janela, duracao_esperada_minutos, "
            "conhecimento_necessario, disponibilidade, recursos_necessarios e motivo_presenca"
        )
    cause = _ref(meta["causa"])
    if cause["valor"] in (None, False, "", [], {}):
        raise PlanError("entrada_local.causa precisa apontar fato canônico positivo")
    origin = _text(meta["origem"], "entrada_local.origem", 120)
    destination = _text(meta["destino"], "entrada_local.destino", 120)
    if origin == destination:
        raise PlanError("entrada_local exige origem e destino distintos")
    window = _map(meta["janela"], "entrada_local.janela")
    if set(window) != {"inicio", "fim"}:
        raise PlanError("entrada_local.janela exige inicio e fim")
    start, end = _instant(window["inicio"]), _instant(window["fim"])
    if end < start:
        raise PlanError("entrada_local.janela termina antes de começar")
    stay = _int(meta["duracao_esperada_minutos"], "entrada_local.duracao_esperada_minutos", 1, 7 * 1440)
    knowledge = _items(meta["conhecimento_necessario"], "entrada_local.conhecimento_necessario", 6)
    for item in knowledge:
        _id(item)
    if len(set(knowledge)) != len(knowledge):
        raise PlanError("entrada_local.conhecimento_necessario possui duplicata")
    availability = _ref(meta["disponibilidade"])
    if availability["valor"] is not True:
        raise PlanError("entrada_local.disponibilidade precisa provar disponibilidade=true")
    resources = _items(meta["recursos_necessarios"], "entrada_local.recursos_necessarios")
    _text(meta["motivo_presenca"], "entrada_local.motivo_presenca", 320)
    if step.get("local") != destination:
        raise PlanError("entrada_local.destino precisa coincidir com passo.local")
    if step.get("conhecimento") != knowledge:
        raise PlanError("entrada_local.conhecimento_necessario deve reutilizar passo.conhecimento")
    if step.get("recursos") != resources:
        raise PlanError("entrada_local.recursos_necessarios deve reutilizar passo.recursos")
    resolution = step.get("resolucao") or {}
    if resolution.get("tipo") != "factual" or resolution.get("sem_oposicao") != availability:
        raise PlanError("entrada_local usa resolução factual e a mesma referência de disponibilidade")
    departure = _instant(step["em"])
    arrival = mundo.WorldInstant(departure.minute + step["duracao_minutos"])
    if arrival < start or arrival > end:
        raise PlanError("duração de deslocamento precisa terminar dentro da janela de chegada")
    if _size(meta) > 1800:
        raise PlanError("entrada_local excede 1800 bytes")
    return meta


def _step(value: Any) -> dict:
    if not isinstance(value, dict) or ENTRY_KEY not in value:
        return _BASE_STEP(value)
    legacy = deepcopy(value)
    raw = legacy.pop(ENTRY_KEY)
    _BASE_STEP(legacy)
    full = deepcopy(value)
    full[ENTRY_KEY] = raw
    _entry_meta(full)
    if _size(full) > 3600:
        raise PlanError("passo entrada_local excede 3600 bytes")
    return full


def is_entry_plan(plan: Any) -> bool:
    return isinstance(plan, dict) and isinstance(plan.get("passo"), dict) and isinstance(plan["passo"].get(ENTRY_KEY), dict)


def _control(world: dict) -> dict:
    control = _BASE_CONTROL(world)
    active_by_actor: dict[str, str] = {}
    for pid, plan in control.items():
        special = is_entry_plan(plan)
        if special:
            if plan.get("tipo") not in (None, ENTRY_TYPE):
                raise PlanError("plano com contrato entrada_local possui tipo divergente")
            plan["tipo"] = ENTRY_TYPE
            _entry_meta(plan["passo"])
            if plan["estado"] not in TERMINAL:
                actor = plan["agente"]["id"]
                previous = active_by_actor.get(actor)
                if previous is not None and previous != pid:
                    raise PlanError("um personagem não pode ter duas entradas_locais ativas")
                active_by_actor[actor] = pid
        elif plan.get("tipo") == ENTRY_TYPE:
            raise PlanError("tipo entrada_local exige contrato no passo")
    return control


def _entry_presence(view: View, aid: str) -> tuple[str, dict]:
    source = view.npc_path(aid)
    npc = view.read(source)["npc"]
    presence = npc.get("presenca") or {}
    if not isinstance(presence, dict):
        raise PlanError("presença dinâmica do NPC deve ser mapa")
    return source, presence


def _presence_expired(view: View, presence: dict) -> bool:
    raw = presence.get("expira_em")
    if not isinstance(raw, dict):
        return False
    try:
        return view.now().minute >= _instant(raw).minute
    except (PlanError, mundo.WorldEngineError):
        raise PlanError("presença causal possui expira_em inválido")


def presence_at(view: View, aid: str, local: str) -> bool:
    _, presence = _entry_presence(view, aid)
    if _presence_expired(view, presence):
        return False
    return (
        presence.get("estado") == "presente"
        and presence.get("local") == local
        and presence.get("em_deslocamento") is False
    )


def _gates(view: View, plan: dict, now: mundo.WorldInstant) -> list[str]:
    if not is_entry_plan(plan):
        blockers = _BASE_GATES(view, plan, now)
        if not blockers:
            try:
                _, presence = _entry_presence(view, plan["agente"]["id"])
                if presence.get("local") == plan["passo"]["local"] and _presence_expired(view, presence):
                    blockers.append("presença causal nesse local já expirou")
            except PlanError:
                pass
        return blockers

    blockers: list[str] = []
    step, aid = plan["passo"], plan["agente"]["id"]
    meta = _entry_meta(step)
    assert meta is not None
    try:
        doc, sources = _actor(view, plan["agente"])
        if plan["objetivo"] not in _objectives(doc):
            raise PlanError("objetivo deixou de corresponder à intenção canônica do agente")
        if now < _instant(step["em"]):
            blockers.append("condição temporal ainda não chegou")
        latest_arrival = mundo.WorldInstant(now.minute + step["duracao_minutos"])
        if latest_arrival > _instant(meta["janela"]["fim"]):
            blockers.append("janela de chegada venceu; adiar explicitamente em vez de apagar a entrada")
        control = arco_mundo.context(view.repo)
        if aid in control.get("controle", {}).get("agentes_estrategicos", {}) or doc.get("tipo") == "faccao":
            raise PlanError("agente adversarial exige operação existente; entrada_local não contorna o arco")
        npc_source, presence = _entry_presence(view, aid)
        if _presence_expired(view, presence):
            blockers.append("origem declarada perdeu presença válida")
        if not (
            presence.get("local") == meta["origem"]
            and presence.get("estado") == "presente"
            and presence.get("em_deslocamento") is False
        ):
            blockers.append("origem não possui presença física disponível para iniciar o deslocamento")
        available = {k["id"]: k for k in doc.get("conhecimento", []) if isinstance(k, dict) and "id" in k}
        npc = view.read(npc_source)["npc"]
        available.update({k["id"]: k for k in npc.get("conhecimento", []) if isinstance(k, dict) and "id" in k})
        for kid in step["conhecimento"]:
            knowledge = available.get(kid)
            if knowledge is None:
                blockers.append(f"conhecimento indisponível para o agente: {kid}")
                continue
            source = _text(knowledge.get("fonte"), "fonte de conhecimento")
            evidence = _text(knowledge.get("evidencia"), "evidencia de conhecimento", 520)
            if not _contains_text(view.read(source), evidence):
                blockers.append(f"evidência do conhecimento {kid} deixou de existir")
        for ref in step["condicoes"]:
            view.value(ref)
        view.value(meta["causa"])
        view.value(meta["disponibilidade"])
        for resource in step["recursos"]:
            amount = view.value({"arquivo": npc_source, "caminho": "npc." + resource["caminho"], "valor": None}, match=False)
            if type(amount) is not int or amount < resource["quantidade"]:
                blockers.append(f"recurso insuficiente: {resource['caminho']}")
        view.value(step["resolucao"]["sem_oposicao"])
    except (ValueError, OSError, yaml.YAMLError) as exc:
        blockers.append(str(exc))
    return list(dict.fromkeys(blockers))


def _movement_presence(plan: dict, now: mundo.WorldInstant) -> dict:
    meta = _entry_meta(plan["passo"])
    assert meta is not None
    arrival = mundo.WorldInstant(now.minute + plan["passo"]["duracao_minutos"])
    return {
        "estado": "em_deslocamento",
        "local": meta["origem"],
        "em_deslocamento": True,
        "origem": meta["origem"],
        "destino": meta["destino"],
        "plano_entrada": plan["id"],
        "iniciado_em": mundo.instant_parts(now),
        "chegada_prevista": mundo.instant_parts(arrival),
        "motivo_presenca": meta["motivo_presenca"],
    }


def _arrival_presence(plan: dict, now: mundo.WorldInstant) -> dict:
    meta = _entry_meta(plan["passo"])
    assert meta is not None
    expires = mundo.WorldInstant(now.minute + meta["duracao_esperada_minutos"])
    return {
        "estado": "presente",
        "local": meta["destino"],
        "em_deslocamento": False,
        "origem": meta["origem"],
        "destino": meta["destino"],
        "plano_entrada": plan["id"],
        "chegou_em": mundo.instant_parts(now),
        "expira_em": mundo.instant_parts(expires),
        "motivo_presenca": meta["motivo_presenca"],
    }


def _entry_delta(aid: str, value: dict) -> dict:
    return {"alvo": "npc:" + aid, "op": "set", "caminho": "presenca", "valor": value, "visibilidade": "operacional"}


def _effective_plan_before(repo: Path, prior: list[dict], pid: str) -> dict | None:
    if not prior:
        return _control(deepcopy(mundo.load_world_state(repo))).get(pid)
    world, _ = compute(repo, prior)
    return _control(world).get(pid)


def validate_registration(repo: Path, transaction: dict, record: dict, prior: list[dict]) -> None:
    changes = events(record)
    entry_changes = []
    for delta in changes:
        event = delta.get("valor") or {}
        pid = delta["alvo"][len(PREFIX):]
        if event.get("evento") == "definir":
            if isinstance((event.get("passo") or {}).get(ENTRY_KEY), dict):
                entry_changes.append((pid, event, None))
        else:
            plan = _effective_plan_before(repo, prior, pid)
            if is_entry_plan(plan):
                entry_changes.append((pid, event, plan))

    if entry_changes:
        if len(entry_changes) != 1:
            raise PlanError("uma transação materializa no máximo uma entrada_local")
        pid, event, plan = entry_changes[0]
        kind = event["evento"]
        non_plan = [d for d in record.get("deltas", []) if not touches(d)]
        if kind == "definir":
            if non_plan:
                raise PlanError("definir entrada_local não materializa presença nem efeito")
        elif kind == "tentar":
            assert plan is not None
            view = View(repo, prior)
            now = view.now()
            expected_presence = _movement_presence(plan, now)
            presence = [d for d in non_plan if d.get("alvo") == "npc:" + plan["agente"]["id"] and d.get("caminho") == "presenca"]
            if presence != [_entry_delta(plan["agente"]["id"], expected_presence)]:
                raise PlanError("iniciar entrada_local exige movimento/presença exatos na mesma transação")
            allowed_paths = {"presenca", *[r["caminho"] for r in plan["passo"]["recursos"]]}
            if any(d.get("alvo") != "npc:" + plan["agente"]["id"] or d.get("caminho") not in allowed_paths for d in non_plan):
                raise PlanError("entrada_local não autoriza efeitos laterais na tentativa")
        elif kind == "resolver":
            assert plan is not None
            if event.get("resultado") != "sucesso" or event.get("seguimento") != "concluir":
                raise PlanError("entrada_local materializada só conclui com chegada factual bem-sucedida")
            if event.get("passo") is not None or event.get("retomar_em") is not None or event.get("rolagem") is not None:
                raise PlanError("chegada factual não cria passo/retomada/rolagem implícitos")
            view = View(repo, [*prior, record])
            now = view.now()
            expected_presence = _arrival_presence(plan, now)
            expected_delta = _entry_delta(plan["agente"]["id"], expected_presence)
            if non_plan != [expected_delta]:
                raise PlanError("resolver entrada_local exige presença de chegada como único efeito e na mesma transação")
            proof = event.get("prova")
            expected_proof = {"arquivo": view.npc_path(plan["agente"]["id"]), "caminho": "npc.presenca", "valor": expected_presence}
            if proof != expected_proof:
                raise PlanError("chegada exige prova factual da presença produzida na mesma transação")
        elif kind == "bloquear":
            if non_plan:
                raise PlanError("adiar entrada_local preserva presença e só reagenda o plano")
        elif kind in {"replanejar", "desistir"}:
            if non_plan:
                raise PlanError("replanejar/desistir entrada_local não materializa presença")
            if kind == "replanejar" and not isinstance((event.get("passo") or {}).get(ENTRY_KEY), dict):
                raise PlanError("replanejar entrada_local exige outro passo entrada_local")

    _BASE_VALIDATE_REGISTRATION(repo, transaction, record, prior)


def project_pending(repo: Path, pending: dict) -> dict:
    result = _BASE_PROJECT_PENDING(repo, pending)
    plan = result.get("plano")
    if not is_entry_plan(plan):
        return result
    meta = _entry_meta(plan["passo"])
    assert meta is not None
    view = View(Path(repo), transacoes.load_pending(Path(repo)))
    now = view.now()
    blockers = list(result.get("bloqueios") or [])
    phase = "partida_devida"
    if plan["estado"] == "tentou":
        phase = "chegada_devida" if now >= _instant(plan["ultima_tentativa"]["terminar_em"]) else "em_deslocamento"
        _, presence = _entry_presence(view, plan["agente"]["id"])
        expected = _movement_presence(plan, _instant(plan["ultima_tentativa"]["iniciada_em"]))
        if presence != expected:
            blockers.append("presença em deslocamento divergiu do movimento comprometido")
        if phase == "em_deslocamento":
            blockers.append("deslocamento ainda não terminou")
    result["bloqueios"] = list(dict.fromkeys(blockers))
    result[ENTRY_KEY] = {
        "tipo": ENTRY_TYPE,
        "fase": phase,
        "agente": deepcopy(plan["agente"]),
        "origem": meta["origem"],
        "destino": meta["destino"],
        "janela": deepcopy(meta["janela"]),
        "duracao_esperada_minutos": meta["duracao_esperada_minutos"],
        "motivo_presenca": meta["motivo_presenca"],
        "regra": "cadastro isolado não cria cameo; chegada exige este plano, presença e movimento na mesma transação",
    }
    return result


def project_local_entry(repo: Path, local_id: str) -> dict | None:
    """Projeta no máximo uma entrada vencida dirigida ao local; não abre população."""
    repo = Path(repo).resolve()
    import acionamentos_leves
    acionamentos_leves.require_stable_canon(repo)
    world = mundo.load_world_state(repo)
    control = _control(world)
    pending = {p["id"]: p for p in world.get("pendencias", []) if isinstance(p, dict)}
    rows = []
    for pid, plan in control.items():
        if not is_entry_plan(plan) or plan["estado"] in TERMINAL:
            continue
        meta = _entry_meta(plan["passo"])
        if meta is None or meta["destino"] != local_id:
            continue
        pend = pending.get(plan.get("pendencia_id"))
        if pend is None or pend.get("tipo") != PENDING_TYPE:
            continue
        when = _instant(pend["disparado_em"])
        rows.append((when.minute, pid, pend))
    if not rows:
        return None
    _, _, selected = sorted(rows, key=lambda row: (row[0], row[1]))[0]
    projection = project_pending(repo, selected)
    plan = projection["plano"]
    meta = projection[ENTRY_KEY]
    result = {
        "tipo": ENTRY_TYPE,
        "plano_id": plan["id"],
        "pendencia_id": selected["id"],
        "agente": deepcopy(plan["agente"]),
        "fase": meta["fase"],
        "origem": meta["origem"],
        "destino": meta["destino"],
        "janela": deepcopy(meta["janela"]),
        "duracao_esperada_minutos": meta["duracao_esperada_minutos"],
        "motivo_presenca": meta["motivo_presenca"],
        "bloqueios": list(projection.get("bloqueios") or []),
        "fontes_lidas": list(projection.get("fontes_lidas") or []),
        "regra": "no máximo uma entrada vencida por janela/local; demais planos permanecem pendentes",
    }
    if _size(result) > MAX_ENTRY_PROJECTION_BYTES:
        raise PlanError("projeção entrada_local excede orçamento")
    return result


def compile_entry_decision(repo: Path, pending: dict, *, acao: str, fato: str, retomar_em: dict | None = None) -> dict:
    """Compila uma decisão NV-19 para o mesmo lote de planos já existente."""
    repo = Path(repo).resolve()
    projection = project_pending(repo, pending)
    plan = projection["plano"]
    if not is_entry_plan(plan):
        raise PlanError("pendência não pertence a entrada_local")
    _text(fato, "fato da entrada")
    revision = plan["revisao"]
    if acao == "adiar":
        if plan["estado"] == "tentou":
            raise PlanError("chegada já em deslocamento permanece pendente; não apagar a tentativa com adiamento")
        if retomar_em is None:
            raise PlanError("adiar entrada_local exige retomar_em futuro")
        when = _instant(retomar_em)
        if when <= View(repo, transacoes.load_pending(repo)).now():
            raise PlanError("adiar entrada_local exige retomar_em futuro")
        return {"evento": {"evento": "bloquear", "revisao": revision, "fato": fato,
                            "motivo": fato, "retomar_em": deepcopy(retomar_em)}, "deltas": []}
    if projection.get("bloqueios"):
        raise PlanError("entrada_local bloqueada: " + "; ".join(projection["bloqueios"]))
    view = View(repo, transacoes.load_pending(repo))
    now = view.now()
    if acao == "iniciar":
        if plan["estado"] not in {"pretende", "bloqueado"}:
            raise PlanError("iniciar exige entrada_local ainda não tentada")
        return {"evento": {"evento": "tentar", "revisao": revision, "fato": fato},
                "deltas": [_entry_delta(plan["agente"]["id"], _movement_presence(plan, now))]}
    if acao == "chegar":
        if plan["estado"] != "tentou" or now < _instant(plan["ultima_tentativa"]["terminar_em"]):
            raise PlanError("chegar exige deslocamento concluído")
        presence = _arrival_presence(plan, now)
        proof = {"arquivo": view.npc_path(plan["agente"]["id"]), "caminho": "npc.presenca", "valor": presence}
        event = {"evento": "resolver", "revisao": revision, "fato": fato,
                 "resultado": "sucesso", "seguimento": "concluir", "motivo": fato,
                 "passo": None, "retomar_em": None, "rolagem": None, "prova": proof}
        return {"evento": event, "deltas": [_entry_delta(plan["agente"]["id"], presence)]}
    raise PlanError("ação entrada_local deve ser iniciar, chegar ou adiar")


def effective_presence(repo: Path, aid: str, *, now: mundo.WorldInstant | None = None) -> dict:
    """Leitura dirigida: expiração é derivada sem apagar o rastro canônico bruto."""
    repo = Path(repo).resolve()
    records = transacoes.load_pending(repo)
    view = View(repo, records)
    source, raw = _entry_presence(view, aid)
    current = now or view.now()
    result = deepcopy(raw)
    expires = raw.get("expira_em")
    if isinstance(expires, dict) and current >= _instant(expires):
        result["estado_efetivo"] = "expirada"
        result["presente"] = False
    else:
        result["estado_efetivo"] = raw.get("estado")
        result["presente"] = raw.get("estado") == "presente" and raw.get("em_deslocamento") is False
    return {"npc": aid, "presenca": result, "fonte": source}
