"""Continuidade de planos na agenda e no journal do Mundo Vivo (NV-08).

Controle reservado, não uma segunda ficha ou um resolvedor de efeitos. Eventos
``plano:<id>`` acompanham os deltas normais; tentar, resolver e escolher a próxima
conduta são decisões distintas. Leituras/previews não consomem RNG nem escrevem.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any

import yaml

import agentes
import agentes_leves
import arco_mundo
import mundo
import transacoes

KEY = "planos_personagens"
PREFIX = "plano:"
PENDING_TYPE = "avaliar_plano_personagem"
SCHEDULE_PREFIX = "nv08."
MAX_PLANS = 8
MAX_CONTROL_BYTES = 24 * 1024
MAX_CONTEXT_BYTES = 4096
MAX_REFERENCE_BYTES = 32 * 1024
ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
EVENTS = {"definir", "tentar", "resolver", "replanejar", "bloquear", "desistir",
          "entregar_contato", "adiar_contato"}
DORMANT = {"aguarda_resposta"}
TERMINAL = {"concluido", "desistiu"}


class PlanError(ValueError):
    """Plano sem base suficiente: rejeitar, não inventar o que está faltando."""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode()).hexdigest()[:24]


def _size(value: Any) -> int:
    return len(yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8"))


def _map(value: Any, label: str) -> dict:
    if not isinstance(value, dict):
        raise PlanError(f"{label} deve ser mapa")
    return value


def _text(value: Any, label: str, maximum: int = 240) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise PlanError(f"{label} deve ser texto não vazio de até {maximum} caracteres")
    return value


def _id(value: Any) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        raise PlanError("ID de plano/agente/passo inválido")
    return value


def _int(value: Any, label: str, minimum: int = 0, maximum: int = 10**6) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise PlanError(f"{label} deve ser inteiro entre {minimum} e {maximum}")
    return value


def _instant(value: Any) -> mundo.WorldInstant:
    if not isinstance(value, dict) or set(value) != {"data", "hora"}:
        raise PlanError("instante do plano exige data e hora")
    if not isinstance(value["hora"], str) or not re.fullmatch(r"[0-2][0-9]:[0-5][0-9]", value["hora"]):
        raise PlanError("hora do plano exige HH:MM")
    return mundo.parse_instant(value["data"], value["hora"])


def _items(value: Any, label: str, limit: int = 4) -> list:
    if not isinstance(value, list) or len(value) > limit:
        raise PlanError(f"{label} deve ser lista de até {limit} itens")
    return value


def _ref(value: Any) -> dict:
    ref = _map(value, "referência canônica")
    if set(ref) != {"arquivo", "caminho", "valor"}:
        raise PlanError("referência exige arquivo, caminho e valor esperado")
    path = Path(_text(ref["arquivo"], "arquivo"))
    if (path.is_absolute() or ".." in path.parts or path.suffix != ".yaml"
            or path.parts[0] not in {"estado", "narrador"}):
        raise PlanError("referência deve permanecer em YAML canônico dentro do repositório")
    field = _text(ref["caminho"], "caminho")
    if any(not part for part in field.split(".")) or _size(ref["valor"]) > 512:
        raise PlanError("referência inválida ou grande demais; apontar um fato dirigido")
    return ref


def _step(value: Any) -> dict:
    step = _map(value, "passo")
    required = {"id", "acao", "em", "duracao_minutos", "local", "condicoes", "recursos", "conhecimento", "resolucao"}
    if set(step) != required:
        raise PlanError(f"campos do passo divergentes: {sorted(set(step) ^ required)}")
    _id(step["id"])
    _text(step["acao"], "acao")
    _instant(step["em"])
    _int(step["duracao_minutos"], "duracao_minutos", 0, 7 * 1440)
    _text(step["local"], "local", 120)
    for ref in _items(step["condicoes"], "condicoes"):
        _ref(ref)
    paths = set()
    for resource in _items(step["recursos"], "recursos"):
        if not isinstance(resource, dict) or set(resource) != {"caminho", "quantidade"}:
            raise PlanError("custo exige caminho e quantidade")
        path = resource["caminho"]
        if not isinstance(path, str) or not re.fullmatch(r"recursos\.[a-z][a-z0-9_]*", path):
            raise PlanError("custo só usa recursos numéricos do próprio NPC")
        _int(resource["quantidade"], "quantidade", 1)
        if path in paths:
            raise PlanError("recurso duplicado no passo")
        paths.add(path)
    known = _items(step["conhecimento"], "conhecimento", 6)
    for kid in known:
        _id(kid)
    if len(set(known)) != len(known):
        raise PlanError("conhecimento duplicado")
    resolution = _map(step["resolucao"], "resolucao")
    kind = resolution.get("tipo")
    if kind == "factual":
        if set(resolution) != {"tipo", "sem_oposicao"} or _ref(resolution["sem_oposicao"])["valor"] is not True:
            raise PlanError("ação factual exige referência canônica sem_oposicao=true")
    elif kind == "teste":
        if set(resolution) != {"tipo", "bonus", "cd"}:
            raise PlanError("teste exige bônus e CD canônicos, fixados antes da tentativa")
        _int(_ref(resolution["bonus"])["valor"], "bonus", -20, 40)
        _int(_ref(resolution["cd"])["valor"], "cd", 1, 50)
    elif kind == "contato":
        import contatos_sociais
        contatos_sociais.validate_resolution(resolution)
    elif kind == "operacao":
        if set(resolution) != {"tipo", "operacao_id"}:
            raise PlanError("operação exige somente operacao_id; seu motor mantém os efeitos")
        _text(resolution["operacao_id"], "operacao_id", 128)
        if step["recursos"]:
            raise PlanError("recursos de operação são reservados pelo motor existente, nunca cobrados duas vezes")
    else:
        raise PlanError("resolução deve ser factual, teste ou operacao; combate não vira teste simples")
    if _size(step) > 2400:
        raise PlanError("passo excede 2400 bytes; reduzir somente detalhes secundários")
    return step


def touches(delta: Any) -> bool:
    return isinstance(delta, dict) and isinstance(delta.get("alvo"), str) and delta["alvo"].startswith(PREFIX)


def events(record: dict) -> list[dict]:
    return [delta for delta in record.get("deltas", []) if touches(delta)]


def validate_delta(delta: dict) -> dict:
    _id(delta["alvo"][len(PREFIX):])
    if set(delta) != {"alvo", "op", "visibilidade", "valor"} or delta.get("op") != "registrar" or delta.get("visibilidade") != "narrador":
        raise PlanError("plano aceita somente registrar reservado; não editar seu estado diretamente")
    event = _map(delta["valor"], "evento de plano")
    kind = event.get("evento")
    if kind not in EVENTS:
        raise PlanError("evento de plano desconhecido")
    if kind in {"entregar_contato", "adiar_contato"}:
        import contatos_sociais
        contatos_sociais.validate_event(event)
        return delta
    common = {"evento", "revisao", "fato"}
    extra = {
        "definir": {"agente", "objetivo", "passo"}, "tentar": set(),
        "resolver": {"resultado", "seguimento", "motivo", "passo", "retomar_em", "rolagem", "prova"},
        "replanejar": {"passo", "motivo"}, "bloquear": {"motivo", "retomar_em"},
        "desistir": {"motivo"},
    }[kind]
    if set(event) != common | extra:
        raise PlanError(f"campos do evento {kind} divergentes: {sorted(set(event) ^ (common | extra))}")
    _int(event["revisao"], "revisao")
    _text(event["fato"], "fato")
    if kind == "definir":
        actor = _map(event["agente"], "agente")
        if set(actor) != {"tipo", "id"} or actor["tipo"] not in {"leve", "estrategico"}:
            raise PlanError("agente exige tipo leve/estrategico e ID canônico")
        _id(actor["id"])
        if actor["id"] == "ren":
            raise PlanError("o motor não decide planos do jogador")
        _text(event["objetivo"], "objetivo", 520)
    if "motivo" in event:
        _text(event["motivo"], "motivo")
    if kind in {"definir", "replanejar"}:
        _step(event["passo"])
    if kind == "bloquear":
        _instant(event["retomar_em"])
    if kind == "resolver":
        if event["resultado"] not in {"sucesso", "falha", "parcial"}:
            raise PlanError("resultado deve ser sucesso, falha ou parcial")
        follow = event["seguimento"]
        if follow not in {"prosseguir", "mudar_estrategia", "bloquear", "desistir", "concluir"}:
            raise PlanError("resultado exige uma escolha explícita de continuidade")
        if follow in {"prosseguir", "mudar_estrategia"}:
            _step(event["passo"])
        elif event["passo"] is not None:
            raise PlanError("passo só acompanha prosseguir/mudar_estrategia")
        if follow == "bloquear":
            _instant(event["retomar_em"])
        elif event["retomar_em"] is not None:
            raise PlanError("retomar_em só acompanha bloqueio")
        if event["prova"] is not None:
            _ref(event["prova"])
        if event["rolagem"] is not None:
            _int(event["rolagem"], "d20", 1, 20)
    return delta


class View:
    """Leituras dirigidas com os deltas anteriores; nunca procurar todos os NPCs."""

    def __init__(self, repo: Path, records: list[dict]):
        self.repo, self.records = repo, records
        self.signatures: dict[str, str] = {}
        self.cache: dict[str, dict] = {}

    def read(self, relative: str | Path) -> dict:
        relative = str(relative)
        if relative in self.cache:
            return self.cache[relative]
        path = self.repo / relative
        if not path.resolve().is_relative_to(self.repo.resolve()) or path.is_symlink():
            raise PlanError("fonte canônica sai do repositório ou é link simbólico")
        if not path.is_file() or path.stat().st_size > MAX_REFERENCE_BYTES:
            raise PlanError(f"fonte ausente ou acima do teto: {relative}")
        data = _map(yaml.safe_load(path.read_bytes()), relative)
        data = deepcopy(data)
        target, payload = None, data
        if relative == mundo.TIME_PATH.as_posix():
            target = "tempo"
        elif relative == "estado/estado-atual.yaml":
            target = "estado"
        elif relative.startswith("estado/npcs/") and isinstance(data.get("npc"), dict):
            target, payload = "npc:" + data.get("id", Path(relative).stem), data["npc"]
        elif relative.startswith("estado/relacoes/") and isinstance(data.get("relacao"), dict):
            target, payload = "relacao:" + data.get("id", Path(relative).stem), data["relacao"]
        if target:
            import tempo_transacional
            for record in self.records:
                for delta in tempo_transacional.expand_atomic_deltas(record.get("deltas", [])):
                    if delta.get("alvo") == target:
                        transacoes.apply_delta(payload, delta)
        self.signatures[relative] = _digest(data)
        self.cache[relative] = data
        return data

    def value(self, ref: dict, *, match: bool = True) -> Any:
        _ref(ref)
        value: Any = self.read(ref["arquivo"])
        for part in ref["caminho"].split("."):
            if not isinstance(value, dict) or part not in value:
                raise PlanError(f"fato ausente: {ref['arquivo']}:{ref['caminho']}")
            value = value[part]
        if match and (type(value) is not type(ref["valor"]) or value != ref["valor"]):
            raise PlanError(f"condição mudou: {ref['arquivo']}:{ref['caminho']}")
        return value

    def now(self) -> mundo.WorldInstant:
        time = self.read(mundo.TIME_PATH)
        return mundo.parse_instant(time.get("data_atual") or time.get("data"), time["hora_aproximada"])

    def npc_path(self, aid: str) -> str:
        index = self.read("estado/npcs/index.yaml")
        meta = (index.get("npcs") or {}).get(aid)
        if not isinstance(meta, dict):
            raise PlanError(f"NPC sem estado indexado: {aid}")
        path = meta.get("arquivo")
        if not isinstance(path, str) or not path.startswith("estado/npcs/"):
            raise PlanError("estado do NPC fora do domínio")
        doc = self.read(path)
        if doc.get("id", aid) != aid or not isinstance(doc.get("npc"), dict):
            raise PlanError("estado do NPC não corresponde ao responsável")
        return path


def _actor(view: View, actor: dict) -> tuple[dict, list[str]]:
    aid = actor["id"]
    loaded = (agentes_leves.load_agent(view.repo, aid) if actor["tipo"] == "leve"
              else agentes.load_agent(view.repo, aid))
    doc = loaded["resultado"]
    sources = loaded["fontes_lidas"]
    # O perfil e o índice também integram o token. Cache negativo não é evidência
    # de conhecimento, localização ou recurso.
    for source in sources:
        if Path(source).stem == aid:
            view.signatures[source] = _digest(doc)
            view.cache[source] = doc
        elif source != agentes_leves.STATE.as_posix():
            view.read(source)
    if actor["tipo"] == "estrategico":
        gate = arco_mundo.strategic_agent_gate(view.repo, aid, purpose="evento")
        if not gate["permitido"]:
            raise PlanError("agente não está habilitado pelo contrato de arco")
        for source in gate.get("fontes_lidas", []):
            view.read(source)
    else:
        if agentes_leves.load_index(view.repo)["agentes"][aid]["estado"] != "ativo":
            raise PlanError("agente leve inativo")
    return doc, sources


def _objectives(actor: dict) -> set[str]:
    goal = actor.get("objetivo_atual")
    values = [goal.get("descricao") if isinstance(goal, dict) else goal,
              (actor.get("plano_atual") or {}).get("acao")]
    values.extend(i.get("descricao") for i in actor.get("iniciativas_possiveis", []) if isinstance(i, dict))
    return {value for value in values if isinstance(value, str)}


def _operation(view: View, plan: dict) -> tuple[dict, dict]:
    import operacoes_concorrentes as operations
    if (view.repo / operations.JOURNAL).exists():
        raise PlanError("operação interrompida; recuperar seu journal antes de continuar o plano")
    opid = plan["passo"]["resolucao"]["operacao_id"]
    contract, operation, row, source = operations._operation_context(view.repo, opid)
    if operation["antagonista_id"] != plan["agente"]["id"]:
        raise PlanError("operação pertence a outro responsável")
    if operation["local"] != plan["passo"]["local"]:
        raise PlanError("local do passo diverge da operação")
    view.signatures[source] = _digest(contract)
    view.signatures[operations.STATE.as_posix()] = _digest(row)
    return operation, row


def _contains_text(value: Any, evidence: str) -> bool:
    if isinstance(value, str):
        return evidence in value
    if isinstance(value, dict):
        return any(_contains_text(v, evidence) for v in value.values())
    if isinstance(value, list):
        return any(_contains_text(v, evidence) for v in value)
    return False


def _gates(view: View, plan: dict, now: mundo.WorldInstant) -> list[str]:
    blockers = []
    step, aid = plan["passo"], plan["agente"]["id"]
    try:
        doc, sources = _actor(view, plan["agente"])
        if plan["objetivo"] not in _objectives(doc):
            raise PlanError("objetivo deixou de corresponder à intenção canônica do agente")
        if now < _instant(step["em"]):
            blockers.append("condição temporal ainda não chegou")
        if step["resolucao"]["tipo"] == "operacao":
            operation, row = _operation(view, plan)
            import planos_adversarios
            planos_adversarios.validate_attempt(view, plan, operation)
            if row["estado"] != "comprometida":
                blockers.append("operação ainda não está comprometida pelo motor existente")
            return blockers
        # Agentes do arco adversarial/facções não contornam Task44/50/51 pelo
        # caminho factual. O objetivo maior continua sendo trabalho da NV-10.
        control = arco_mundo.context(view.repo)
        if aid in control.get("controle", {}).get("agentes_estrategicos", {}) or doc.get("tipo") == "faccao":
            raise PlanError("agente adversarial exige operação existente, não ação factual simplificada")
        npc_source = view.npc_path(aid)
        npc = view.read(npc_source)["npc"]
        if plan["agente"]["tipo"] == "estrategico":
            present = (agentes.local_eligibility(doc) == "sim"
                       and doc["presenca"]["referencia"] == step["local"]
                       and doc["mobilidade"]["estado"] not in {"em_deslocamento", "chegada_planejada"})
        else:
            presence = npc.get("presenca") or {}
            present = (presence.get("local") == step["local"]
                       and presence.get("estado") == "presente"
                       and presence.get("em_deslocamento") is False)
        if not present:
            blockers.append("presença/deslocamento não permite executar nesse local")
        available = {k["id"]: k for k in doc.get("conhecimento", []) if isinstance(k, dict) and "id" in k}
        # Conhecimento suplementar pertence ao próprio NPC, não ao jogador nem
        # ao catálogo do narrador. Cada fato mantém fonte e evidência literal.
        available.update({k["id"]: k for k in npc.get("conhecimento", []) if isinstance(k, dict) and "id" in k})
        for kid in step["conhecimento"]:
            knowledge = available.get(kid)
            if knowledge is None:
                blockers.append(f"conhecimento indisponível para o agente: {kid}")
                continue
            source = _text(knowledge.get("fonte"), "fonte de conhecimento")
            evidence = _text(knowledge.get("evidencia"), "evidencia de conhecimento", 520)
            canonical = view.read(source)
            if not _contains_text(canonical, evidence):
                blockers.append(f"evidência do conhecimento {kid} deixou de existir")
        for ref in step["condicoes"]:
            view.value(ref)
        for resource in step["recursos"]:
            amount = view.value({"arquivo": npc_source, "caminho": "npc." + resource["caminho"], "valor": None}, match=False)
            if type(amount) is not int or amount < resource["quantidade"]:
                blockers.append(f"recurso insuficiente: {resource['caminho']}")
        resolution = step["resolucao"]
        if resolution["tipo"] == "factual":
            view.value(resolution["sem_oposicao"])
        elif resolution["tipo"] == "contato":
            import contatos_sociais
            contatos_sociais.attempt_gate(view, plan)
        else:
            # Bônus deve vir do responsável, não de Ren ou de outro NPC.
            if resolution["bonus"]["arquivo"] not in {npc_source, *sources}:
                raise PlanError("bônus não pertence ao responsável pela tentativa")
            view.value(resolution["bonus"])
            view.value(resolution["cd"])
    except (ValueError, OSError, yaml.YAMLError) as exc:
        blockers.append(str(exc))
    return blockers


def _control(world: dict) -> dict:
    control = world.setdefault(KEY, {})
    if not isinstance(control, dict) or len(control) > MAX_PLANS or _size(control) > MAX_CONTROL_BYTES:
        raise PlanError("controle de planos excede o teto; não descartar planos silenciosamente")
    import contatos_sociais
    contatos_sociais.receipts(world)
    for pid, plan in control.items():
        _id(pid)
        if not isinstance(plan, dict) or plan.get("estado") not in {"pretende", "tentou", "bloqueado", *TERMINAL, *DORMANT}:
            raise PlanError("estado de plano inválido")
        _int(plan.get("revisao"), "revisao", 1)
        if plan.get("id") != pid:
            raise PlanError("ID interno do plano diverge do controle")
        actor = _map(plan.get("agente"), "agente do plano")
        if set(actor) != {"tipo", "id"} or actor["tipo"] not in {"leve", "estrategico"}:
            raise PlanError("responsável do plano inválido")
        _id(actor["id"])
        _text(plan.get("objetivo"), "objetivo", 520)
        _text(plan.get("motivo"), "motivo")
        _step(plan.get("passo"))
        pending = plan.get("pendencia_id")
        if plan["estado"] in TERMINAL | DORMANT:
            if pending is not None:
                raise PlanError("plano terminal não pode conservar pendência")
        elif not isinstance(pending, str) or not re.fullmatch(r"mundo-[0-9a-f]{16}", pending):
            raise PlanError("plano ativo precisa de pendência temporal identificada")
        attempt = plan.get("ultima_tentativa")
        if attempt is not None:
            _map(attempt, "tentativa")
            _text(attempt.get("transacao"), "transação da tentativa")
            _id(attempt.get("passo"))
            start = _instant(attempt.get("iniciada_em"))
            end = _instant(attempt.get("terminar_em"))
            if end < start:
                raise PlanError("tentativa termina antes de começar")
        if plan["estado"] in DORMANT:
            if (not contatos_sociais.is_contact(plan) or not isinstance(attempt, dict)
                    or (attempt.get("resultado") or {}).get("resultado") != "contato_entregue"
                    or contatos_sociais.cause_key(plan) not in contatos_sociais.receipts(world)):
                raise PlanError("aguarda_resposta exige contato entregue com recibo, não objetivo concluído")
        if plan["estado"] == "tentou":
            if (attempt is None or attempt.get("resultado") is not None
                    or attempt.get("passo") != plan["passo"]["id"]
                    or attempt.get("contrato") != _digest(plan["passo"])):
                raise PlanError("contrato da tentativa mudou ou já possui resultado")
    return control


def check_control(world: dict, agenda: dict) -> None:
    """Invariantes de controle/agenda, sem abrir os perfis dos personagens."""
    control = _control(world)
    schedules = [item for item in agenda.get("agendamentos", [])
                 if item["id"].startswith(SCHEDULE_PREFIX)]
    expected = {SCHEDULE_PREFIX + pid + "." + str(p["revisao"]): p
                for pid, p in control.items() if p["estado"] not in TERMINAL | DORMANT}
    if {s["id"] for s in schedules} != set(expected) or len(schedules) != len(expected):
        raise PlanError("agenda e planos ativos divergem")
    for schedule in schedules:
        if schedule["tipo"] != PENDING_TYPE:
            raise PlanError("agendamento de plano possui tipo divergente")
        when = _instant(schedule["em"])
        pending = mundo._scheduled_triggers({"agendamentos": [schedule]},
                    mundo.WorldInstant(when.minute - 1), when)[0]
        if pending["id"] != expected[schedule["id"]]["pendencia_id"]:
            raise PlanError("identidade da pendência diverge do agendamento do plano")
    known = {p["pendencia_id"] for p in expected.values()}
    if any(p["id"] not in known for p in world["pendencias"] if p["tipo"] == PENDING_TYPE):
        raise PlanError("pendência de plano órfã")


def _schedule(world: dict, agenda: dict, pid: str, plan: dict, when: mundo.WorldInstant | None, now: mundo.WorldInstant, record: dict) -> None:
    old_id = plan.get("pendencia_id")
    old = next((p for p in world["pendencias"] if p["id"] == old_id), None)
    if old is not None:
        world["pendencias"].remove(old)
        world["concluidas_recentes"].append({
            "id": old_id, "tipo": PENDING_TYPE, "disparado_em": old["disparado_em"],
            "transacao": record["id"], "plano_id": pid, "nota": plan["motivo"],
            "decisao": next((t.rsplit(":", 1)[1] for t in record.get("tags", [])
                             if t.startswith("plano-decisao:" + old_id + ":")), None),
        })
        world["concluidas_recentes"] = world["concluidas_recentes"][-mundo.MAX_RECENT_COMPLETED:]
    prefix = SCHEDULE_PREFIX + pid + "."
    agenda["agendamentos"] = [s for s in agenda.get("agendamentos", []) if not s["id"].startswith(prefix)]
    plan["pendencia_id"] = None
    if when is None:
        return
    when = max(when, now)
    sid = prefix + str(plan["revisao"])
    schedule = {"id": sid, "tipo": PENDING_TYPE, "em": mundo.instant_parts(when),
                "motivo": "Dar continuidade ao plano; intenção ou tentativa não concede sucesso."}
    agenda["agendamentos"].append(schedule)
    pending = mundo._scheduled_triggers({"agendamentos": [schedule]}, mundo.WorldInstant(when.minute - 1), when)[0]
    plan["pendencia_id"] = pending["id"]
    if when <= now:
        mundo._merge_pending(world, [pending])


def _result(view: View, plan: dict, event: dict, record: dict, now: mundo.WorldInstant) -> dict:
    attempt = plan["ultima_tentativa"]
    if not attempt or plan["estado"] != "tentou" or attempt["resultado"] is not None:
        raise PlanError("resultado exige tentativa ainda não resolvida")
    if attempt["transacao"] == record["id"] or now < _instant(attempt["terminar_em"]):
        raise PlanError("não transformar intenção em sucesso nem concluir antes de terminar o deslocamento/ação")
    resolution = plan["passo"]["resolucao"]
    outcome: dict = {"resultado": event["resultado"], "transacao": record["id"], "fato": event["fato"]}
    if resolution["tipo"] == "teste":
        import _rolar_dados_core as dice
        if event["rolagem"] is None or event["prova"] is not None:
            raise PlanError("resultado mecânico exige o d20 efetivo, não apenas prosa")
        roll = dice.D20Roll([event["rolagem"]], event["rolagem"], resolution["bonus"]["valor"], "normal")
        expected = "sucesso" if roll.total >= resolution["cd"]["valor"] else "falha"
        label = "plano:" + plan["id"] + ":" + attempt["transacao"]
        receipt = dice.format_check(label, roll, resolution["cd"]["valor"])
        if receipt not in record.get("rolagens_ocultas", []) or event["resultado"] != expected:
            raise PlanError("desfecho diverge da rolagem/CD comprometida; registrar a saída literal de dados")
        outcome["rolagem"] = receipt
    elif resolution["tipo"] == "operacao":
        if event["rolagem"] is not None or event["prova"] is not None:
            raise PlanError("operação já tem prova e mecânica próprias")
        _, row = _operation(view, plan)
        if row["estado"] != "resolvida" or not row.get("resolucao"):
            raise PlanError("operação ainda não tem resultado canônico")
        if row["resolucao"].get("desfecho") != event["resultado"]:
            raise PlanError("operação exige desfecho estruturado correspondente; prosa não implica sucesso")
        if event["fato"] != row["resolucao"]["resultado"]:
            raise PlanError("o fato deve preservar literalmente o resultado da operação")
        outcome["operacao"] = deepcopy(row["resolucao"])
        import planos_adversarios
        receipt = planos_adversarios.feedback(view.repo, plan, now=now)
        if receipt:
            outcome["retorno_ao_agente"] = receipt
    else:
        if resolution["tipo"] == "contato" and event["resultado"] == "sucesso":
            raise PlanError("entrega de contato usa cronica concluir, não sucesso automático fora de cena")
        if event["rolagem"] is not None or event["prova"] is None:
            raise PlanError("resultado factual exige prova em estado canônico, não apenas vontade")
        proof = event["prova"]
        owner = plan["agente"]["id"]
        if proof["arquivo"] != view.npc_path(owner) or not proof["caminho"].startswith("npc."):
            raise PlanError("prova factual deve apontar consequência no estado do próprio NPC")
        path = proof["caminho"][4:]
        changed = [d for d in record["deltas"] if d.get("alvo") == "npc:" + owner
                   and d.get("caminho") == path and d.get("op") in {"set", "inc", "append"}]
        if not changed:
            raise PlanError("prova factual exige consequência pareada na mesma transação")
        view.value(proof)
        prior = View(view.repo, view.records[:-1])
        try:
            old_value = prior.value(proof, match=False)
        except PlanError:
            old_value = object()
        if old_value == proof["valor"]:
            raise PlanError("fato já existia; não atribuir novo sucesso a um resultado antigo")
        outcome["prova"] = deepcopy(event["prova"])
    return outcome


def compute(repo: Path, records: list[dict]) -> tuple[dict, dict]:
    """Stage puro sobre estado efetivo; o journal existente instala o lote inteiro."""
    import acionamentos_leves
    acionamentos_leves.require_stable_canon(repo)
    world = deepcopy(mundo.load_world_state(repo))
    agenda = deepcopy(mundo.load_agenda(repo))
    control = _control(world)
    previous: list[dict] = []
    for record in records:
        changes = events(record)
        if not changes:
            previous.append(record)
            continue
        seen, costs = set(), Counter()
        before = View(repo, previous)
        after = View(repo, [*previous, record])
        now = after.now()
        for delta in changes:
            validate_delta(delta)
            pid, event = delta["alvo"][len(PREFIX):], delta["valor"]
            if pid in seen:
                raise PlanError("um evento por plano e por transação; tentativa e resultado não se fundem")
            seen.add(pid)
            old = control.get(pid)
            if event["revisao"] != (old["revisao"] if old else 0):
                raise PlanError(f"revisão obsoleta do plano {pid}")
            kind = event["evento"]
            if kind == "definir":
                if old and old["estado"] not in TERMINAL:
                    raise PlanError("plano ativo não pode ser sobrescrito por outra intenção")
                doc, _ = _actor(before, event["agente"])
                if event["objetivo"] not in _objectives(doc):
                    raise PlanError("objetivo deve corresponder à intenção já estabelecida no perfil")
                plan = {"id": pid, "agente": deepcopy(event["agente"]), "objetivo": event["objetivo"],
                        "passo": deepcopy(event["passo"]), "estado": "pretende", "revisao": event["revisao"],
                        "ultima_tentativa": None, "pendencia_id": None}
                import contatos_sociais
                contatos_sociais.validate_definition(world, plan)
                control[pid] = plan
                when = _instant(plan["passo"]["em"])
            elif kind in {"entregar_contato", "adiar_contato"}:
                import contatos_sociais
                if old is None or not any(p["id"] == old.get("pendencia_id") for p in world["pendencias"]):
                    raise PlanError("contato sem pendência atual")
                plan = old
                when = contatos_sociais.apply_event(before, after, world, plan, event, record)
            else:
                if old is None or old["estado"] in TERMINAL:
                    raise PlanError("evento exige plano ativo")
                plan = old
                if record.get("modo") != "mundo":
                    raise PlanError("execução de plano exige transação modo:mundo, sem ação de Ren")
                if plan["estado"] not in DORMANT and not any(p["id"] == plan.get("pendencia_id") for p in world["pendencias"]):
                    raise PlanError("plano ainda não tem condição/prazo aberto na fila do mundo")
                if kind == "tentar":
                    if plan["estado"] not in {"pretende", "bloqueado"}:
                        raise PlanError("tentativa já está em curso; não executar/cobrar novamente")
                    import contatos_sociais
                    contatos_sociais.validate_definition(world, plan)
                    blockers = _gates(before, plan, now)
                    if blockers:
                        raise PlanError("tentativa bloqueada: " + "; ".join(blockers))
                    for resource in plan["passo"]["recursos"]:
                        costs[("npc:" + plan["agente"]["id"], resource["caminho"])] += resource["quantidade"]
                    when = mundo.WorldInstant(now.minute + plan["passo"]["duracao_minutos"])
                    plan["estado"] = "tentou"
                    plan["ultima_tentativa"] = {"transacao": record["id"], "passo": plan["passo"]["id"],
                        "contrato": _digest(plan["passo"]), "iniciada_em": mundo.instant_parts(now),
                        "terminar_em": mundo.instant_parts(when), "resultado": None}
                elif kind == "resolver":
                    outcome = _result(after, plan, event, record, now)
                    plan["ultima_tentativa"]["resultado"] = outcome
                    follow = event["seguimento"]
                    if follow == "concluir" and event["resultado"] != "sucesso":
                        raise PlanError("falha/parcial não prova objetivo alcançado; replanejar, bloquear ou desistir")
                    if follow in {"prosseguir", "mudar_estrategia"}:
                        if event["passo"]["id"] == plan["passo"]["id"]:
                            raise PlanError("próximo passo precisa de identidade distinta")
                        if follow == "mudar_estrategia" and event["passo"]["acao"] == plan["passo"]["acao"]:
                            raise PlanError("mudar estratégia exige mudar a conduta, não somente o rótulo")
                        plan["passo"], plan["estado"] = deepcopy(event["passo"]), "pretende"
                        when = _instant(plan["passo"]["em"])
                    elif follow == "bloquear":
                        plan["estado"], when = "bloqueado", _instant(event["retomar_em"])
                    else:
                        plan["estado"], when = ("concluido" if follow == "concluir" else "desistiu"), None
                else:
                    if plan["estado"] == "tentou":
                        raise PlanError("tentativa em curso precisa de resultado; não reescrever nem apagar a tentativa")
                    if kind == "replanejar":
                        if event["passo"]["id"] == plan["passo"]["id"]:
                            raise PlanError("replanejar exige um novo passo explícito")
                        plan["passo"], plan["estado"] = deepcopy(event["passo"]), "pretende"
                        when = _instant(plan["passo"]["em"])
                    elif kind == "bloquear":
                        plan["estado"], when = "bloqueado", _instant(event["retomar_em"])
                    else:
                        plan["estado"], when = "desistiu", None
                if plan["estado"] == "bloqueado" and when <= now:
                    raise PlanError("bloqueio exige oportunidade futura de reavaliação, não loop imediato")
            if kind in {"replanejar", "resolver"} and plan["estado"] == "pretende":
                import contatos_sociais
                contatos_sociais.validate_definition(world, plan)
            plan["revisao"] += 1
            plan["motivo"] = event.get("motivo", event["fato"])
            plan["ultima_transacao"] = record["id"]
            _schedule(world, agenda, pid, plan, when, now, record)
        # Custos agregados por transação, contra o estado anterior. Nem dois
        # planos podem gastar a mesma última moeda, nem um set compensar o inc.
        for (target, path), amount in costs.items():
            npc = target.split(":")[1]
            source = before.npc_path(npc)
            available = before.value({"arquivo": source, "caminho": "npc." + path, "valor": None}, match=False)
            if type(available) is not int or available < amount:
                raise PlanError("recursos insuficientes para o lote de tentativas")
            touching = [d for d in record["deltas"] if d.get("alvo") == target and (
                d.get("caminho") == path or str(d.get("caminho", "")).startswith(path + ".")
                or path.startswith(str(d.get("caminho", "")) + "."))]
            expected = {"alvo": target, "op": "inc", "caminho": path, "valor": -amount, "visibilidade": "operacional"}
            if touching != [expected]:
                raise PlanError("tentativa exige consumo exato dos recursos na mesma transação")
        check_control(world, agenda)
        previous.append(record)
    return world, agenda


def validate_registration(repo: Path, transaction: dict, record: dict, prior: list[dict]) -> None:
    changes = events(record)
    if not changes:
        return
    for delta in changes:
        validate_delta(delta)
        if delta["valor"]["evento"] == "entregar_contato":
            plan = mundo.load_world_state(repo).get(KEY, {}).get(delta["alvo"][len(PREFIX):])
            if not isinstance(plan, dict) or plan["passo"]["resolucao"].get("mensagem", "") not in str(transaction.get("narracao", "")):
                raise PlanError("mensagem entregue deve aparecer literalmente na narração")
        if delta["valor"]["fato"] not in str(transaction.get("narracao", "")):
            raise PlanError("fato do plano deve aparecer literalmente na narração registrada")
    if any(d["valor"]["evento"] not in {"definir", "entregar_contato", "adiar_contato"} for d in changes):
        if transaction.get("jogador") not in (None, "") or record.get("modo") != "mundo":
            raise PlanError("execução autônoma não carrega ação do jogador")
        # Ações simples só alteram seu próprio estado. Efeitos adversariais,
        # combate e recursos de outras entidades continuam nos motores próprios.
        world = mundo.load_world_state(repo)
        owners = {"npc:" + world.get(KEY, {}).get(d["alvo"][len(PREFIX):], {}).get("agente", {}).get("id", "") for d in changes}
        if any(not touches(d) and d.get("alvo") not in owners for d in record["deltas"]):
            raise PlanError("execução do plano não autoriza decidir por Ren nem alterar outros atores")
    compute(repo, [*prior, record])


def verify_replay(repo: Path, session: int, record: dict) -> None:
    """Retry consolidado precisa repetir o registro completo, não só o ID."""
    ledger = repo / f"sessoes/{session:03d}/consolidacoes.jsonl"
    receipts = [event for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()
                for event in json.loads(line).get(KEY, []) if event.get("transacao") == record["id"]]
    if len(receipts) != 1 or receipts[0].get("fingerprint") != transacoes.record_fingerprint(record):
        raise PlanError("retry consolidado de plano diverge do registro original")


def stage(repo: Path, consolidation: dict, records: list[dict]) -> None:
    if not any(events(r) for r in records):
        return
    world, agenda = compute(repo, records)
    outputs = consolidation["outputs"]
    outputs[mundo.WORLD_STATE_PATH.as_posix()] = yaml.safe_dump(world, allow_unicode=True, sort_keys=False).encode()
    outputs[mundo.AGENDA_PATH.as_posix()] = yaml.safe_dump(agenda, allow_unicode=True, sort_keys=False).encode()
    import barreira_mundo
    outputs[barreira_mundo.BARRIER_PATH.as_posix()] = yaml.safe_dump(barreira_mundo.payload_from_state(world), allow_unicode=True, sort_keys=False).encode()
    # O histórico usa o ledger já existente. Nada é apagado quando o próximo
    # resultado substitui a última tentativa no controle compacto.
    import _consolidar_core as core
    path = f"sessoes/{consolidation['sessao']:03d}/{core.LEDGER_NAME}"
    ledger = [json.loads(line) for line in outputs[path].decode().splitlines() if line.strip()]
    entry = next(row for row in ledger if row["id"] == consolidation["batch"])
    entry[KEY] = [{"transacao": r["id"], "fingerprint": transacoes.record_fingerprint(r),
                   "eventos": deepcopy(events(r))} for r in records if events(r)]
    entry["arquivos_afetados"] = sorted(set(entry.get("arquivos_afetados", [])) | {
        mundo.WORLD_STATE_PATH.as_posix(), mundo.AGENDA_PATH.as_posix()})
    outputs[path] = core.jsonl_text(ledger)


def project_pending(repo: Path, pending: dict) -> dict:
    import acionamentos_leves
    acionamentos_leves.require_stable_canon(repo)
    world = mundo.load_world_state(repo)
    control = _control(world)
    matches = [p for p in control.values() if p["pendencia_id"] == pending["id"]]
    if len(matches) != 1 or pending["tipo"] != PENDING_TYPE:
        raise PlanError("pendência não corresponde a um único plano atual")
    plan = matches[0]
    view = View(repo, [])
    now = view.now()
    blockers = _gates(view, plan, now) if plan["estado"] != "tentou" else []
    if plan["estado"] == "tentou" and plan["passo"]["resolucao"]["tipo"] == "operacao":
        _operation(view, plan)
    if plan["estado"] == "tentou" and plan["passo"]["resolucao"]["tipo"] == "contato":
        import contatos_sociais
        try:
            contatos_sociais.delivery(view, plan)
        except PlanError as exc:
            blockers.append(str(exc))
    result = {"plano": deepcopy(plan), "bloqueios": blockers,
              "assinatura_fontes": _digest(view.signatures),
              "fontes_lidas": [mundo.WORLD_STATE_PATH.as_posix(), *sorted(view.signatures)],
              "regra": "Intenção não é tentativa; tentativa não é sucesso. Resultado exige prova/mecânica e seguimento explícito."}
    if _size(result) > MAX_CONTEXT_BYTES:
        raise PlanError("plano indispensável excede 4 KiB; detalhar por referência, não truncar")
    return result


def compile_batch(repo: Path, decisions: list[dict], items: dict[str, dict]) -> dict | None:
    """Um registro de mundo para todas as decisões de planos do lote existente."""
    if not decisions:
        return None
    deltas, facts, rolls, costs = [], [], [], Counter()
    for decision in decisions:
        item = items[decision["id"]]
        plan = item["contexto"]["plano_personagem"]["plano"]
        event = deepcopy(decision["evento"])
        delta = {"alvo": PREFIX + plan["id"], "op": "registrar", "visibilidade": "narrador", "valor": event}
        validate_delta(delta)
        if event["revisao"] != plan["revisao"] or event["evento"] == "definir":
            raise PlanError("decisão não corresponde à revisão preparada")
        deltas.append(delta)
        deltas.extend(deepcopy(decision.get("deltas", [])))
        facts.append(event["fato"])
        rolls.extend(decision.get("rolagens_ocultas", []))
        if event["evento"] == "tentar":
            for cost in plan["passo"]["recursos"]:
                costs[("npc:" + plan["agente"]["id"], cost["caminho"])] += cost["quantidade"]
    deltas += [{"alvo": t, "op": "inc", "caminho": p, "valor": -q, "visibilidade": "operacional"} for (t, p), q in sorted(costs.items())]
    transaction = {"id": "planos-" + _digest(decisions), "modo": "mundo", "narracao": "\n\n".join(facts),
                   "resumo": "Continuidade de planos fora de cena.", "deltas": deltas, "rolagens_ocultas": rolls,
                   "tags": ["plano-decisao:" + d["id"] + ":" + _digest(d) for d in decisions]}
    import turno
    normalized, session = turno.normalize_transaction(repo, transaction)
    record = transacoes.build_pending_record(normalized, session)
    validate_registration(repo, normalized, record, transacoes.load_pending(repo))
    return transaction
