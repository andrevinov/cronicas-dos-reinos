"""Contato efetivo: um passo NV-08 chega à cena pela prioridade social existente.

Não agenda por conta própria nem mantém uma fila paralela. A tentativa pertence
ao plano, transporte exige presença comprovada e a entrega usa o mesmo journal
do turno. Receber uma mensagem não significa aceitar o pedido nem concluí-lo.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from typing import Any

import yaml

import planos_personagens as plans
import mundo
import transacoes

TICKET_KEY = "contato_social"
RECEIPTS = "contatos_sociais_entregues"
DELIVER = "entregar_contato"
DEFER = "adiar_contato"
WAITING = "aguarda_resposta"
MAX_RECEIPTS = 64
MAX_RECEIPT_BYTES = 12 * 1024
MAX_PROJECTION_BYTES = 2048
MODALITIES = {"procurar", "recado", "convite", "pedir_ajuda", "retomar_assunto"}


def is_contact(plan: dict) -> bool:
    return plan.get("passo", {}).get("resolucao", {}).get("tipo") == "contato"


def validate_resolution(value: Any) -> dict:
    value = plans._map(value, "resolução de contato")
    if set(value) != {"tipo", "modalidade", "mensagem", "causa", "canal"} or value["tipo"] != "contato":
        raise plans.PlanError("contato exige tipo, modalidade, mensagem, causa e canal")
    if not isinstance(value["modalidade"], str) or value["modalidade"] not in MODALITIES:
        raise plans.PlanError("modalidade de contato desconhecida")
    plans._text(value["mensagem"], "mensagem", 240)
    plans._ref(value["causa"])
    if not value["causa"]["caminho"].startswith("npc.necessidades.") or not value["causa"]["valor"]:
        raise plans.PlanError("contato exige necessidade própria estabelecida, não intenção inventada")
    channel_ref = plans._ref(value["canal"])
    if not channel_ref["caminho"].startswith("npc.canais_contato."):
        raise plans.PlanError("canal deve estar estabelecido no próprio NPC")
    channel = plans._map(channel_ref["valor"], "canal")
    if set(channel) != {"meio", "origem", "destino", "portador", "duracao_minima_minutos", "conhecimento_id", "disponivel"}:
        raise plans.PlanError("canal exige meio, origem, destino, portador, duração mínima, conhecimento e disponibilidade")
    if not isinstance(channel["meio"], str) or channel["meio"] not in {"presencial", "mensageiro"} or channel["disponivel"] is not True:
        raise plans.PlanError("canal presencial/mensageiro precisa estar disponível")
    for key in ("origem", "destino"):
        plans._text(channel[key], key, 120)
    plans._id(channel["conhecimento_id"])
    minimum = plans._int(channel["duracao_minima_minutos"], "duração de transporte", 0, 7 * 1440)
    if channel["meio"] == "presencial":
        if channel["portador"] is not None:
            raise plans.PlanError("contato presencial não usa portador")
    else:
        plans._id(channel["portador"])
        if channel["portador"] == "ren" or minimum == 0:
            raise plans.PlanError("mensageiro não pode ser Ren nem entregar instantaneamente")
    if channel["origem"] != channel["destino"] and minimum == 0:
        raise plans.PlanError("deslocamento exige duração positiva pré-comprometida")
    return value


def validate_event(event: dict) -> None:
    extra = {"motivo", "retomar_em"} if event.get("evento") == DEFER else set()
    if set(event) != {"evento", "revisao", "fato", "assinatura", "cena_id"} | extra:
        raise plans.PlanError("evento de contato possui campos divergentes")
    plans._int(event["revisao"], "revisão")
    plans._text(event["fato"], "evidência do contato")
    plans._text(event["cena_id"], "cena do contato", 120)
    if not isinstance(event["assinatura"], str) or not re.fullmatch(r"[0-9a-f]{24}", event["assinatura"]):
        raise plans.PlanError("assinatura de contato inválida")
    if extra:
        plans._text(event["motivo"], "motivo")
        plans._instant(event["retomar_em"])


def receipts(world: dict) -> dict:
    values = world.get(RECEIPTS, {})
    if not isinstance(values, dict) or len(values) > MAX_RECEIPTS or plans._size(values) > MAX_RECEIPT_BYTES:
        raise plans.PlanError("recibos de contato excedem o teto; preservar histórico, não descartar")
    for key, receipt in values.items():
        if (not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{24}", key) or not isinstance(receipt, dict)
                or set(receipt) != {"plano", "transacao", "cena_id", "sessao"}):
            raise plans.PlanError("recibo de contato inválido")
        plans._id(receipt["plano"])
        plans._text(receipt["transacao"], "transação")
        plans._text(receipt["cena_id"], "cena do contato", 120)
        plans._int(receipt["sessao"], "sessão do contato", 1)
    return values


def cause_key(plan: dict) -> str:
    # Mudar o ID, o assunto ou a formulação do pedido não reabre a mesma causa.
    return plans._digest([plan["agente"]["id"], plan["passo"]["resolucao"]["causa"]])


def validate_definition(world: dict, plan: dict) -> None:
    if not is_contact(plan):
        return
    key = cause_key(plan)
    if key in receipts(world):
        raise plans.PlanError("necessidade já foi comunicada; requer causa materialmente nova")
    for other in world.get(plans.KEY, {}).values():
        if (other["id"] != plan["id"] and is_contact(other)
                and other["estado"] not in plans.TERMINAL and cause_key(other) == key):
            raise plans.PlanError("mesma necessidade já possui contato ativo")


def _present(view: plans.View, aid: str, local: str) -> bool:
    npc = view.read(view.npc_path(aid))["npc"]
    presence = npc.get("presenca", {})
    return (isinstance(presence, dict) and presence.get("estado") == "presente"
            and presence.get("local") == local and presence.get("em_deslocamento") is False
            and npc.get("morto") is not True and npc.get("estado_vital") != "morto")


def _basis(view: plans.View, plan: dict) -> tuple[dict, dict, dict]:
    resolution = validate_resolution(plan["passo"]["resolucao"])
    owner = plan["agente"]["id"]
    source = view.npc_path(owner)
    if any(resolution[key]["arquivo"] != source for key in ("causa", "canal")):
        raise plans.PlanError("causa e canal pertencem ao próprio NPC, não ao narrador ou a Ren")
    view.value(resolution["causa"])
    channel = view.value(resolution["canal"])
    npc = view.read(source)["npc"]
    if npc.get("identidade_relacional", "ren") != "ren":
        raise plans.PlanError("contato dirigido a Ren não funde outra identidade relacional")
    if channel["conhecimento_id"] not in plan["passo"]["conhecimento"]:
        raise plans.PlanError("canal exige conhecimento próprio do destino")
    if channel["origem"] != plan["passo"]["local"]:
        raise plans.PlanError("origem do contato diverge do local de execução")
    if plan["passo"]["duracao_minutos"] < channel["duracao_minima_minutos"]:
        raise plans.PlanError("tentativa encurta duração de transporte pré-comprometida")
    return resolution, channel, npc


def attempt_gate(view: plans.View, plan: dict) -> None:
    _, channel, _ = _basis(view, plan)
    if channel["meio"] == "mensageiro" and not _present(view, channel["portador"], channel["origem"]):
        raise plans.PlanError("mensageiro não está disponível na origem")


def location(state: dict) -> str | None:
    local = state.get("localizacao") or {}
    return local.get("local_id") or local.get("area")


def delivery(view: plans.View, plan: dict) -> dict:
    """Revalida a chegada, nunca a deduz somente da passagem do tempo."""
    if plan["estado"] != "tentou" or not is_contact(plan):
        raise plans.PlanError("contato exige tentativa anterior ainda aberta")
    attempt = plan["ultima_tentativa"]
    if view.now() < plans._instant(attempt["terminar_em"]):
        raise plans.PlanError("transporte ainda não terminou")
    profile, _ = plans._actor(view, plan["agente"])
    if plan["objetivo"] not in plans._objectives(profile):
        raise plans.PlanError("intenção canônica mudou")
    resolution, channel, npc = _basis(view, plan)
    # Conhecimento pode ter sido revogado depois do envio; não aproveitar token velho.
    knowledge_rows = npc.get("conhecimento", [])
    if not isinstance(knowledge_rows, list):
        raise plans.PlanError("conhecimento do NPC deve ser lista")
    known = {k.get("id"): k for k in [*profile.get("conhecimento", []), *knowledge_rows] if isinstance(k, dict)}
    knowledge = known.get(channel["conhecimento_id"])
    if (knowledge is None or not plans._contains_text(view.read(plans._text(knowledge.get("fonte"), "fonte do canal")), plans._text(knowledge.get("evidencia"), "evidência do canal", 520))):
        raise plans.PlanError("conhecimento do canal deixou de ter evidência")
    state = view.read("estado/estado-atual.yaml")
    if location(state) != channel["destino"]:
        raise plans.PlanError("Ren não está no destino declarado")
    carrier = channel["portador"] if channel["meio"] == "mensageiro" else plan["agente"]["id"]
    if not _present(view, carrier, channel["destino"]):
        raise plans.PlanError("chegada do interlocutor/portador não está estabelecida; não teleportar")
    for ref in plan["passo"]["condicoes"]:
        view.value(ref)
    import dialogo_relacional
    import iniciativa_social
    meters = plans._map(npc.get("medidores", {}), "medidores do remetente")
    mode = dialogo_relacional.relationship_mode(meters.get("vinculo"), meters.get("confianca"))
    social = iniciativa_social.project(npc, relationship_mode=mode)
    if social is None:
        raise plans.PlanError("iniciativa social sem estado relacional; não presumir intimidade")
    visible = {"plano_id": plan["id"], "npc_id": plan["agente"]["id"],
               "nome": profile["nome"], "modalidade": resolution["modalidade"],
               "meio": channel["meio"], "portador": channel["portador"],
               "mensagem": resolution["mensagem"], "destino": channel["destino"],
               "causa": resolution["causa"]["valor"], "modo_social": social["modo"]}
    return {"visivel": visible, "social": social,
            "assinatura": plans._digest([plan, view.signatures]),
            "fontes": sorted(view.signatures)}


def partition_gate(repo: Path) -> tuple[list[dict], list[dict]] | None:
    """Somente contatos já tentados e operações jogáveis atravessam a barreira."""
    # Sem autoridade instalada, conservar a barreira existente; nunca inventar
    # fila vazia nem autorização para atravessá-la.
    if not (repo / mundo.WORLD_STATE_PATH).is_file():
        return None
    import acionamentos_leves
    acionamentos_leves.require_stable_canon(repo)
    world = mundo.load_world_state(repo)
    control = plans._control(world)
    contacts, operations = [], []
    for pending in world["pendencias"]:
        if pending["tipo"] == "resolver_operacao_adversarial":
            operations.append(pending)
            continue
        matches = [p for p in control.values() if p["pendencia_id"] == pending["id"]]
        if (pending["tipo"] != plans.PENDING_TYPE or len(matches) != 1
                or not is_contact(matches[0]) or matches[0]["estado"] != "tentou"):
            return None
        contacts.append(pending)
    return (operations, contacts) if contacts else None


def _queue_signature(world: dict, pending_ids: list[str]) -> str:
    return plans._digest([p for _, p in sorted(world.get(plans.KEY, {}).items()) if p["pendencia_id"] in pending_ids])


def prepare(repo: Path, prepared: dict, pending: list[dict], *, decode_ticket, encode_ticket,
            max_output_bytes: int) -> dict:
    if not pending:
        return prepared
    import pressao_narrativa as pressure
    prior = transacoes.load_pending(repo)
    if any(plans.events(r) for r in prior):
        raise plans.PlanError("conclusão de plano interrompida; recuperar checkpoint antes de preparar")
    world = mundo.load_world_state(repo)
    payload = decode_ticket(prepared["ticket"])
    request = payload["cena"]
    pending_ids = sorted(p["id"] for p in pending)
    candidates, sources, deferred = [], [], []
    # Matérias de prioridade superior têm precedência sem carregar cada aliado.
    higher = any(i["prioridade"] < pressure.PRIORITIES["iniciativa_social"]
                 for i in prepared.get("pressao_narrativa", {}).get("itens", []))
    state = plans.View(repo, prior).read("estado/estado-atual.yaml")
    higher = higher or bool(request.get("npcs") or request.get("place") or payload.get("transito_urbano")
                            or payload.get("mecanica_cronica"))
    higher = higher or state.get("campanha", {}).get("modo_de_cena_atual") in {"combate", "perigo_imediato"}
    already_in_scene = any(r["cena_id"] == request["scene_id"] and r["sessao"] == state["campanha"]["sessao_atual"]
                           for r in receipts(world).values())
    if not higher and not already_in_scene:
        for plan in world[plans.KEY].values():
            if plan["pendencia_id"] not in pending_ids:
                continue
            view = plans.View(repo, prior)
            try:
                candidate = delivery(view, plan)
                if cause_key(plan) in receipts(world):
                    raise plans.PlanError("contato pendente já foi entregue")
                candidate["plano"] = plan
                candidates.append(candidate)
            except plans.PlanError as exc:
                deferred.append({"plano_id": plan["id"], "motivo": str(exc)})
                # Condição ausente não vira presença. A pendência continua inteira;
                # o lote do Mundo Vivo permite diagnosticar/cancelar/replanejar.
            sources.extend(view.signatures)
    selected = None
    result = deepcopy(prepared)
    if candidates:
        candidates.sort(key=lambda c: (plans._instant(c["plano"]["ultima_tentativa"]["terminar_em"]), c["plano"]["id"]))
        candidate = candidates[0]
        plan, visible = candidate["plano"], candidate["visivel"]
        social_item = pressure.project_social_pressure(candidate["social"], npc_id=visible["npc_id"],
                        presence_authorized=True, cause_id=cause_key(plan), cause_known=True)
        if social_item is None:
            raise plans.PlanError("contato sem autorização social")
        social_item["origem"]["tipo"] = "contato_de_plano"
        existing = result.get("pressao_narrativa", {}).get("itens", [])
        result["pressao_narrativa"] = {"schema_pressao_narrativa": pressure.SCHEMA,
            "itens": pressure.sort_items([*existing, social_item]),
            "regra_ordem": "Uma iniciativa por cena; pedido não decide a resposta de Ren."}
        result[TICKET_KEY] = {**visible, "regra": "Apresentar contato sem presumir aceite; envio não é conhecimento nem presença do remetente remoto."}
        selected = {"id": plan["id"], "revisao": plan["revisao"], "assinatura": candidate["assinatura"], **visible}
        result.setdefault("contrato_conclusao", {})["contato_social"] = {
            "plano_id": plan["id"], "resultado": "entregue|adiado", "evidencia": "trecho literal da narração",
            "regra": "entregue exige mensagem literal; adiado exige motivo e retomar_em futuros; não significa aceite"}
    if selected is None:
        result["contatos_adiados"] = {"quantidade": len(pending_ids),
            "motivo": "prioridade_superior" if higher else "contato_ja_entregue_nesta_cena" if already_in_scene else "sem_canal_disponivel",
            "diagnostico": deferred, "regra": "Pendências preservadas; não narrar chegada nem mensagem. Resolver pela fronteira se a condição se tornar impossível."}
    payload[TICKET_KEY] = {"pendencias": pending_ids, "fila": _queue_signature(world, pending_ids), "selecionado": selected}
    result["ticket"], result["ticket_id"] = encode_ticket(payload)
    result["fontes_lidas"] = list(dict.fromkeys([*result.get("fontes_lidas", []), mundo.WORLD_STATE_PATH.as_posix(),
                                               "estado/estado-atual.yaml", transacoes.PENDING_PATH.as_posix(), *sources]))
    if plans._size(result.get(TICKET_KEY, {})) > MAX_PROJECTION_BYTES or plans._size(result) > max_output_bytes:
        raise plans.PlanError("contato indispensável excede orçamento conjunto; não cortar nem elevar teto")
    return result


def knowledge_delta(selected: dict) -> dict:
    return {"alvo": "conhecimento", "op": "registrar", "valor": {
        "tipo": "contato_recebido", "emissor": selected["npc_id"], "canal": selected["meio"],
        "estatuto": "mensagem_atribuida", "fonte": "plano:" + selected["plano_id"],
        "texto": "Mensagem de " + selected["nome"] + ": " + selected["mensagem"]}}


def compile_conclusion(repo: Path, payload: dict, transaction: dict) -> tuple[dict, list[str]]:
    meta, block = payload.get(TICKET_KEY), transaction.get(TICKET_KEY)
    if meta is None:
        if block is not None:
            raise plans.PlanError("contato sem autorização no ticket")
        return transaction, []
    if not isinstance(meta, dict) or set(meta) != {"pendencias", "fila", "selecionado"}:
        raise plans.PlanError("ticket de contato inválido")
    selected = meta["selecionado"]
    out = deepcopy(transaction)
    out.pop(TICKET_KEY, None)
    if selected is None:
        if block is not None:
            raise plans.PlanError("nenhum contato foi selecionado nesta cena")
    else:
        block = plans._map(block, "conclusão do contato")
        outcome = block.get("resultado")
        extras = {"motivo", "retomar_em"} if outcome == "adiado" else set()
        if (not isinstance(outcome, str) or outcome not in {"entregue", "adiado"} or set(block) != {"plano_id", "resultado", "evidencia"} | extras
                or block["plano_id"] != selected["id"]):
            raise plans.PlanError("contato selecionado exige entrega ou adiamento explícito; aceite não é automático")
        evidence = plans._text(block["evidencia"], "evidência")
        narration = transaction.get("narracao", "")
        if evidence not in narration or (outcome == "entregue" and selected["mensagem"] not in narration):
            raise plans.PlanError("entrega exige mensagem e evidência literais na narração")
        event = {"evento": DELIVER if outcome == "entregue" else DEFER, "revisao": selected["revisao"],
                 "fato": evidence, "assinatura": selected["assinatura"], "cena_id": payload["cena"]["scene_id"], **{k: block[k] for k in extras}}
        validate_event(event)
        delta = {"alvo": plans.PREFIX + selected["id"], "op": "registrar", "visibilidade": "narrador", "valor": event}
        if any(plans.touches(d) for d in out.get("deltas", [])):
            raise plans.PlanError("não duplicar evento de contato nem executar outro plano na mesma cena")
        out["deltas"] = [*out.get("deltas", []), delta]
        if outcome == "entregue":
            knowledge = knowledge_delta(selected)
            if any(d.get("alvo") == "conhecimento" and d.get("valor") == knowledge["valor"] for d in out["deltas"]):
                raise plans.PlanError("mensagem já possui delta de conhecimento duplicado")
            out["deltas"].append(knowledge)
            # Só o interlocutor/portador comprovado entra no elenco. Mensageiro
            # não transporta o remetente; elenco desconhecido permanece lacuna.
            import memoria_cena
            cast = payload.get(memoria_cena.TICKET_KEY, {}).get("elenco")
            if cast is not None:
                cast = deepcopy(cast)
                physical = selected["npc_id"] if selected["meio"] == "presencial" else selected["portador"]
                cast["participantes"] = sorted(set([*cast["participantes"], physical]))
                memoria_cena.cast(cast)
                existing = [d for d in out["deltas"] if d.get("alvo") == "estado" and d.get("caminho") == memoria_cena.CAST_PATH]
                # O compilador NV05 já fez esse delta; não sobrescrever elenco
                # final explicitamente contraditório enviado pelo narrador.
                if existing and existing[0].get("valor") != payload[memoria_cena.TICKET_KEY]["elenco"]:
                    final_cast = memoria_cena.cast(existing[0].get("valor"))
                    if final_cast is None or physical not in final_cast["participantes"]:
                        raise plans.PlanError("elenco final contradiz contato presencial")
                    cast = final_cast
                out["deltas"] = [d for d in out["deltas"] if d not in existing]
                out["deltas"].append({"alvo": "estado", "op": "set", "caminho": memoria_cena.CAST_PATH, "valor": cast})
    # Reconstruir antes de conferir replay permite reparar buffer/transcrição e
    # repetir entrega antiga sem depender da situação atual do canal ou de Ren.
    import memoria_duravel
    state = plans.View(repo, []).read("estado/estado-atual.yaml")
    session = state["campanha"]["sessao_atual"]
    txid = transacoes.stable_transaction_id(out, session)
    records = transacoes.load_pending(repo)
    if any(r["id"] == txid for r in records) or memoria_duravel._already_consolidated(repo, session, txid):
        return out, meta["pendencias"]
    world = mundo.load_world_state(repo)
    if _queue_signature(world, meta["pendencias"]) != meta["fila"]:
        raise plans.PlanError("fila de contatos mudou; preparar novamente")
    if selected is not None:
        plan = world[plans.KEY].get(selected["id"])
        fresh = delivery(plans.View(repo, records), plan)
        if fresh["assinatura"] != selected["assinatura"] or fresh["visivel"] != {k: selected[k] for k in fresh["visivel"]}:
            raise plans.PlanError("contato/canal/causa ficou obsoleto; preparar novamente")
    return out, meta["pendencias"]


def apply_event(before: plans.View, after: plans.View, world: dict, plan: dict, event: dict, record: dict):
    """Muta apenas o stage em memória; o journal NV-08 instala tudo junto."""
    fresh = delivery(before, plan)
    if event["assinatura"] != fresh["assinatura"]:
        raise plans.PlanError("assinatura do contato ficou obsoleta")
    now = after.now()
    if event["evento"] == DEFER:
        when = plans._instant(event["retomar_em"])
        if when <= now:
            raise plans.PlanError("adiamento de contato exige oportunidade futura")
        return when
    channel = plan["passo"]["resolucao"]["canal"]["valor"]
    current = before.read("estado/estado-atual.yaml").get("localizacao", {})
    resulting = after.read("estado/estado-atual.yaml").get("localizacao", {})
    if (location(after.read("estado/estado-atual.yaml")) != channel["destino"]
            or any(current.get(k) != resulting.get(k) for k in ("local_id", "area"))):
        raise plans.PlanError("entrega não pode acompanhar teletransporte/mudança de local de Ren")
    # A mesma conclusão não pode mover o portador, invalidar o canal ou criar a
    # necessidade e ainda se apoiar na versão anterior para forçar entrega.
    delivery(after, plan)
    if any(r["cena_id"] == event["cena_id"] and r["sessao"] == record["sessao"] for r in receipts(world).values()):
        raise plans.PlanError("esta cena já recebeu uma iniciativa; preservar as demais")
    if knowledge_delta(fresh["visivel"]) not in record["deltas"]:
        raise plans.PlanError("entrega exige mensagem atribuída pareada no mesmo registro")
    key = cause_key(plan)
    if key in receipts(world):
        raise plans.PlanError("mesma causa já foi entregue")
    world.setdefault(RECEIPTS, {})[key] = {"plano": plan["id"], "transacao": record["id"],
                                            "cena_id": event["cena_id"], "sessao": record["sessao"]}
    receipts(world)
    plan["estado"] = WAITING
    plan["ultima_tentativa"]["resultado"] = {"resultado": "contato_entregue", "transacao": record["id"],
        "fato": event["fato"], "resposta_de_ren": "nao_presumida"}
    return None


def authorize_registration(repo: Path, transaction: dict, *, retry: bool, contacts: list[str],
                           operations: list[str], original):
    if retry:
        return original(repo, transaction, retry=True)
    partition = partition_gate(repo)
    if partition is not None:
        actual_ops, actual_contacts = partition
        if {p["id"] for p in actual_ops} <= set(operations) and {p["id"] for p in actual_contacts} <= set(contacts):
            return {"ok": True, "retry": False, "pendencia_resolvida": None,
                    "barreira": {"bloqueado": True, "contatos_roteados": contacts}}
    return original(repo, transaction, retry=False)
