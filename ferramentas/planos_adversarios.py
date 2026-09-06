"""Origem NV-10 para operações existentes: intenção própria, execução e retorno.

Não mantém outro catálogo, agenda, recurso ou inteligência. O plano NV-08 é a
origem; capacidade/implantação vêm do agente; o contrato Task51 congela a ação.
"""
from copy import deepcopy
from pathlib import Path

import mundo
import planos_personagens as plans
import reacoes_sidequest as reactions
import transacoes

TICKET_KEY = "planos_aguardando"


def origin(repo: Path, raw: dict, operation: dict) -> tuple[dict, dict, dict, list[str]]:
    """Valida origem antes de materializar e novamente antes do compromisso."""
    import acionamentos_leves
    acionamentos_leves.require_stable_canon(repo)
    if any(plans.events(record) for record in transacoes.load_pending(repo)):
        raise plans.PlanError("consolidar planos pendentes antes de preparar operações")
    if not isinstance(raw, dict) or set(raw) != {"id", "revisao", "alternativa", "implantacao"}:
        raise plans.PlanError("origem_plano exige id, revisao, alternativa e implantacao")
    pid = plans._id(raw["id"])
    plans._int(raw["revisao"], "revisão da origem", 1)
    world = mundo.load_world_state(repo)
    plan = plans._control(world).get(pid)
    if (plan is None or plan["estado"] != "pretende" or plan["revisao"] != raw["revisao"]
            or plan["agente"]["tipo"] != "estrategico"):
        raise plans.PlanError("operação exige intenção estratégica atual, com revisão correspondente")
    step = plan["passo"]
    if (step["resolucao"] != {"tipo": "operacao", "operacao_id": operation["id"]}
            or step["local"] != operation["local"] or step["acao"] != operation["objetivo"]):
        raise plans.PlanError("operação não corresponde ao próximo passo/local do plano")
    view = plans.View(repo, [])
    profile, _ = plans._actor(view, plan["agente"])
    if plan["objetivo"] not in plans._objectives(profile):
        raise plans.PlanError("objetivo estratégico deixou de estar estabelecido")
    actor = reactions._agent(repo, plan["agente"]["id"])
    for ref in step["condicoes"]:
        view.value(ref)
    alternative, _, knowledge = reactions._alternative(repo, raw["alternativa"], 0, actor, set())
    if alternative["estado"] != "elegivel":
        raise plans.PlanError("iniciativa bloqueada: " + "; ".join(alternative["motivos_bloqueio"]))
    if (alternative["objetivo"] != plan["objetivo"]
            or set(alternative["conhecimentos_requeridos"]) != set(step["conhecimento"])):
        raise plans.PlanError("alternativa deve servir ao objetivo e ao conhecimento do plano")
    # Conhecimento declarado é disponibilidade, não certeza do rumor nem licença
    # para inventar um alvo. Não aceitar uma iniciativa sem nenhuma base informada.
    if not knowledge:
        raise plans.PlanError("iniciativa exige conhecimento próprio com fonte e evidência")
    deployment = plans._ref(raw["implantacao"])
    if deployment["arquivo"] != actor["fonte"] or not deployment["caminho"].startswith("implantacoes."):
        raise plans.PlanError("implantação pertence ao próprio agente, não a Ren ou a outro ator")
    expected = {"local": operation["local"], "celula_id": operation["celula_id"],
                "estado": "disponivel", "em_deslocamento": False,
                "recursos": sorted(operation["recursos"])}
    if view.value(deployment) != expected:
        raise plans.PlanError("implantação não comprova célula, local e recursos disponíveis")
    sources = [mundo.WORLD_STATE_PATH.as_posix(), *view.signatures, *actor["fontes_lidas"],
               *(item["prova"]["fonte"] for item in knowledge)]
    normalized_origin = {"id": pid, "revisao": raw["revisao"],
                         "alternativa": {key: deepcopy(alternative[key]) for key in raw["alternativa"]},
                         "implantacao": deepcopy(deployment)}
    return normalized_origin, plan, actor, list(dict.fromkeys(sources))


def validate_attempt(view: plans.View, plan: dict, operation: dict) -> None:
    source = operation.get("origem_plano")
    if source is None:
        return
    if source["id"] != plan["id"] or source["revisao"] != plan["revisao"]:
        raise plans.PlanError("operação comprometida pertence a outro passo/revisão do plano")


def feedback(repo: Path, plan: dict, *, now=None) -> dict:
    """O resultado do mundo só orienta o agente depois de chegar pelo canal."""
    import operacoes_concorrentes as operations
    _, operation, row, _ = operations._operation_context(repo, plan["passo"]["resolucao"]["operacao_id"])
    if not operation.get("origem_plano"):
        return {}
    if row["estado"] != "resolvida":
        raise plans.PlanError("operação ainda não possui resultado para o agente")
    current = now or mundo.load_canonical_time(repo)[0]
    state = operations._load_state(repo)
    for delivery in state["entregas_informacao"]:
        if (delivery["operacao_id"] == operation["id"]
                and delivery["destinatario"] == plan["agente"]["id"]
                and row["resolucao"]["resultado"] in delivery["fatos"]
                and plans._instant(delivery["entregue_em"]) <= current):
            operations._proof(repo, delivery["prova"], "retorno ao agente")
            return {"entrega_id": delivery["id"], "recebido_em": delivery["entregue_em"]}
    raise plans.PlanError("resultado remoto ainda não chegou ao agente por canal comprovado")


def passive(repo: Path, world: dict) -> list[dict]:
    """Planos dependentes não impedem jogar a operação nem esperar o mensageiro."""
    import operacoes_concorrentes as operations
    pendings = {p["id"] for p in world["pendencias"] if p["tipo"] == plans.PENDING_TYPE}
    if not pendings:
        return []
    if (repo / operations.JOURNAL).exists():
        raise plans.PlanError("recuperar journal da operação antes de retomar planos")
    result = []
    for plan in plans._control(world).values():
        if (plan["pendencia_id"] not in pendings or plan["estado"] != "tentou"
                or plan["passo"]["resolucao"]["tipo"] != "operacao"):
            continue
        _, operation, row, _ = operations._operation_context(repo, plan["passo"]["resolucao"]["operacao_id"])
        origin = operation.get("origem_plano")
        if not origin or origin["id"] != plan["id"] or origin["revisao"] + 1 != plan["revisao"]:
            continue
        waiting = "operacao" if row["estado"] == "comprometida" else None
        if row["estado"] == "resolvida":
            try:
                feedback(repo, plan)
            except plans.PlanError:
                waiting = "retorno_ao_agente"
        if waiting:
            result.append({"id": plan["pendencia_id"], "plano_id": plan["id"], "aguarda": waiting,
                           "assinatura": plans._digest([plan, row])})
    return sorted(result, key=lambda item: item["id"])


def attach(repo: Path, prepared: dict, rows: list[dict], *, decode_ticket, encode_ticket,
           max_output_bytes: int) -> dict:
    if not rows:
        return prepared
    out = deepcopy(prepared)
    payload = decode_ticket(out["ticket"])
    payload[TICKET_KEY] = rows
    out["ticket"], out["ticket_id"] = encode_ticket(payload)
    out[TICKET_KEY] = [{k: row[k] for k in ("plano_id", "aguarda")} for row in rows]
    out.setdefault("fontes_lidas", []).extend([mundo.WORLD_STATE_PATH.as_posix()])
    if plans._size(out) > max_output_bytes:
        raise plans.PlanError("planos indispensáveis excedem orçamento conjunto; preparar cena mais dirigida")
    return out


def validate_ticket(repo: Path, payload: dict, transaction: dict) -> list[str]:
    rows = payload.get(TICKET_KEY)
    if rows is None:
        return []
    import memoria_duravel
    if not isinstance(rows, list) or not rows or len(rows) > plans.MAX_PLANS:
        raise plans.PlanError("ticket de planos aguardando inválido")
    if any(not isinstance(r, dict) or set(r) != {"id", "plano_id", "aguarda", "assinatura"} for r in rows):
        raise plans.PlanError("ticket de planos aguardando divergente")
    records = transacoes.load_pending(repo)
    session = plans.View(repo, []).read("estado/estado-atual.yaml")["campanha"]["sessao_atual"]
    tid = transacoes.stable_transaction_id(transaction, session)
    if not (any(r["id"] == tid for r in records) or memoria_duravel._already_consolidated(repo, session, tid)):
        if rows != passive(repo, mundo.load_world_state(repo)):
            raise plans.PlanError("operação/retorno do plano mudou; preparar novamente")
    return [r["id"] for r in rows]


def authorize(repo, transaction, *, retry, plans_pending, operations_pending, contacts_pending, original):
    if retry:
        return original(repo, transaction, retry=True)
    world = mundo.load_world_state(repo)
    active_passive = {r["id"] for r in passive(repo, world)}
    allowed = set(plans_pending) | set(operations_pending) | set(contacts_pending)
    if (active_passive == set(plans_pending) and world["pendencias"]
            and all(p["id"] in allowed for p in world["pendencias"])):
        return {"ok": True, "retry": False, "pendencia_resolvida": None,
                "barreira": {"bloqueado": True, "planos_dependentes": plans_pending}}
    return original(repo, transaction, retry=False)
