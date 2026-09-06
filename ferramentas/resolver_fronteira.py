#!/usr/bin/env python3
"""Resolve em lote pendências acumuladas numa fronteira temporal do Mundo Vivo.

A camada é deliberadamente estreita:

* ``preparar`` é read-only e abre no máximo um fragmento dirigido por pendência;
* todas as pendências são apresentadas num único lote determinístico;
* ``aplicar`` recebe por stdin somente as decisões ``sem_mudanca`` do narrador;
* eventos canônicos datados nunca aceitam no-op;
* consequências Task45 ``resolver_sidequest`` nunca aceitam no-op genérico;
* candidatos autônomos de pressão só aceitam no-op com bloqueio canônico concreto;
* agentes leves usam ``conclude_noop`` para preservar o cache negativo causal;
* itens omitidos permanecem abertos e são devolvidos como trabalho restante.

O lote não cria scheduler, estado paralelo nem decisão narrativa automática. Ele reduz
a orquestração: uma fronteira com várias rotinas pode ser avaliada numa inferência e
concluída numa única chamada mutante, sem processar cada agente por ferramenta.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import agentes
import agentes_leves
import barreira_mundo
import direcoes_destino
import mundo
import operacoes_concorrentes
import pressao_ravens_bluff
import reacoes_sidequest
import acionamentos_leves
import planos_personagens

SCHEMA = 1
MAX_BATCH = 16
MAX_NOTE_CHARS = 800
TOKEN_HEX = 24
BATCH_HEX = 24


class BatchBoundaryError(ValueError):
    """Contrato inválido da resolução em lote."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _token(value: Any, length: int = TOKEN_HEX) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()[:length]


def _pending_sort_key(item: dict[str, Any], *, causal_queued: bool = False) -> tuple[int, int, str]:
    when = item.get("disparado_em") or {}
    instant = mundo.parse_instant(str(when.get("data")), str(when.get("hora")))
    routine = (causal_queued and item.get("tipo") == "reavaliar_agente_leve"
               and not item.get("acionamento_causal"))
    return int(routine), instant.minute, str(item.get("id") or "")


def _source_list(*groups: Any) -> list[str]:
    result: list[str] = []
    for group in groups:
        if not isinstance(group, list):
            continue
        for value in group:
            if isinstance(value, str) and value and value not in result:
                result.append(value)
    return result


def _compact_agent(data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: data.get(key)
        for key in (
            "estado",
            "objetivo_atual",
            "recursos",
            "restricoes",
            "presenca",
            "atuacao_local",
            "plano_atual",
            "conhecimento",
        )
        if key in data
    }


def _compact_light(data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: data.get(key)
        for key in (
            "rotina_padrao",
            "objetivo_atual",
            "iniciativas_possiveis",
            "regra_de_reavaliacao",
        )
        if key in data
    }


def _compact_direction(data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: data.get(key)
        for key in (
            "direcao_id",
            "nome",
            "permitido",
            "estado",
            "marco_atual",
            "modo_avaliacao",
            "avanco_requer_fato_canonico",
            "regra",
            "motivo",
        )
        if key in data
    }


def _compact_canonical(data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: data.get(key)
        for key in (
            "id",
            "titulo",
            "data",
            "janela",
            "atraso_dias",
            "nucleo_obrigatorio",
            "guardrails",
            "regra",
        )
        if key in data
    }


def _base_item(pending: dict[str, Any]) -> dict[str, Any]:
    return {
        key: pending.get(key)
        for key in (
            "id",
            "tipo",
            "agente",
            "agente_leve",
            "direcao",
            "evento",
            "agendamento",
            "disparado_em",
            "motivo",
            "origem",
            "acionamento_causal",
        )
        if pending.get(key) is not None
    }


def _project_item(repo: Path, pending: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    sources = [mundo.WORLD_STATE_PATH.as_posix()]
    item = _base_item(pending)
    # A causa completa integra o token, mas a saída a apresenta uma única vez.
    item.pop("acionamento_causal", None)
    context: dict[str, Any] = {}
    pending_type = str(pending.get("tipo") or "")

    # Task45 já fez o trabalho temporal e emitiu uma pendência causal explícita.
    # Não reinterprete esse contrato como rotina/no-op e não abra outros motores
    # apenas para decidir algo que só progressao_sidequests pode materializar.
    if pending_type == planos_personagens.PENDING_TYPE:
        try:
            projection = planos_personagens.project_pending(repo, pending)
        except (ValueError, OSError, yaml.YAMLError) as exc:
            raise BatchBoundaryError(str(exc)) from exc
        item["classificacao"] = "dar_continuidade_plano"
        item["sem_mudanca_permitido"] = False
        context["plano_personagem"] = projection
        sources = _source_list(sources, projection["fontes_lidas"])
    elif pending_type == "resolver_grupo_operacoes":
        try:
            group = operacoes_concorrentes.project_group_pending(repo, pending)
        except operacoes_concorrentes.ConcurrentOperationError as exc:
            raise BatchBoundaryError(str(exc)) from exc
        item["grupo_operacoes_id"] = group["grupo_operacoes_id"]
        item["classificacao"] = "comprometer_grupo_operacoes"
        item["sem_mudanca_permitido"] = False
        context["grupo_operacoes"] = {
            key: group[key]
            for key in (
                "grupo_operacoes_id", "estado", "janela", "simultaneidade",
                "operacoes", "canais", "ordem_processamento",
            )
        }
        sources = _source_list(sources, group.get("fontes_lidas"))
    elif pending_type == "resolver_operacao_adversarial":
        try:
            operation = operacoes_concorrentes.project_operation_pending(repo, pending)
        except operacoes_concorrentes.ConcurrentOperationError as exc:
            raise BatchBoundaryError(str(exc)) from exc
        item["grupo_operacoes_id"] = operation["grupo_operacoes_id"]
        item["operacao_id"] = operation["operacao_id"]
        item["classificacao"] = "requer_resolucao_operacao"
        item["sem_mudanca_permitido"] = False
        context["operacao_adversarial"] = {
            key: operation[key]
            for key in (
                "grupo_operacoes_id", "operacao_id", "estado", "local",
                "alvo", "objetivo", "sinais_perceptiveis", "encontro",
            )
        }
        sources = _source_list(sources, operation.get("fontes_lidas"))
    elif pending_type == "resolver_reacao_sidequest":
        try:
            reaction = reacoes_sidequest.project_pending(repo, pending)
        except reacoes_sidequest.SidequestReactionError as exc:
            raise BatchBoundaryError(str(exc)) from exc
        item["reaction_id"] = reaction["reaction_id"]
        item["classificacao"] = "requer_resolucao_reacao"
        item["sem_mudanca_permitido"] = False
        context["reacao_sidequest"] = {
            key: reaction[key]
            for key in (
                "reaction_id", "estado", "missao", "gatilho", "antagonista_id",
                "objetivo", "janela", "alternativas",
            )
        }
        sources = _source_list(sources, reaction.get("fontes_lidas"))
    elif pending_type == "resolver_sidequest":
        item["classificacao"] = "requer_resolucao_sidequest"
        item["sem_mudanca_permitido"] = False
    else:
        canonical = barreira_mundo._canonical_event(repo, pending)
        try:
            pressure = pressao_ravens_bluff.candidate_for_pending(repo, pending)
        except pressao_ravens_bluff.PressureError as exc:
            raise BatchBoundaryError(str(exc)) from exc

        if canonical is not None:
            item["classificacao"] = "requer_fato_canonico"
            item["sem_mudanca_permitido"] = False
            context["evento_canonico"] = _compact_canonical(canonical)
        elif pressure is not None:
            item["classificacao"] = "avaliar_candidato_autonomo"
            item["sem_mudanca_permitido"] = "somente_bloqueio_canonico_concreto"
            context["pressao_ravens_bluff"] = pressure
        else:
            item["classificacao"] = "avaliar_no_lote"
            item["sem_mudanca_permitido"] = True

    if pending_type == "reavaliar_agente" and pending.get("agente"):
        try:
            loaded = agentes.load_agent(repo, str(pending["agente"]))
        except agentes.AgentValidationError as exc:
            raise BatchBoundaryError(str(exc)) from exc
        context["agente"] = _compact_agent(loaded["resultado"])
        context["elegibilidade_local"] = loaded.get("elegibilidade_local")
        sources = _source_list(sources, loaded.get("fontes_lidas"))
    elif pending_type == "reavaliar_agente_leve" and pending.get("agente_leve"):
        try:
            if pending.get("acionamento_causal"):
                projection = acionamentos_leves.pending_context(repo, pending)
                context["acionamento_causal"] = projection
                sources = _source_list(sources, projection.get("fontes_lidas"))
                if item["classificacao"] == "avaliar_no_lote":
                    item["classificacao"] = "avaliar_condicao_causal"
                    item["sem_mudanca_permitido"] = "somente_motivo_concreto"
            else:
                loaded = agentes_leves.load_agent(repo, str(pending["agente_leve"]))
                context["agente_leve"] = _compact_light(loaded["resultado"])
                sources = _source_list(sources, loaded.get("fontes_lidas"))
        except (ValueError, OSError, yaml.YAMLError) as exc:
            raise BatchBoundaryError(str(exc)) from exc
    elif pending_type == "avaliar_direcao" and pending.get("direcao"):
        try:
            projection = direcoes_destino.project(repo, str(pending["direcao"]))
        except direcoes_destino.DestinationDirectionError as exc:
            raise BatchBoundaryError(str(exc)) from exc
        context["direcao"] = _compact_direction(projection)
        sources = _source_list(sources, projection.get("fontes_lidas"))

    if context:
        item["contexto"] = context

    token_payload = {
        "pendencia": _base_item(pending),
        "classificacao": item["classificacao"],
        "sem_mudanca_permitido": item["sem_mudanca_permitido"],
        "contexto": context,
    }
    item["token"] = _token(token_payload)
    return item, sources


def prepare_batch(repo: Path) -> dict[str, Any]:
    """Projeta todas as pendências abertas em um único contrato read-only."""
    state = mundo.load_world_state(repo)
    if acionamentos_leves.KEY in state:
        try:
            acionamentos_leves.require_stable_canon(repo)
            acionamentos_leves._validate_control(state)
        except ValueError as exc:
            raise BatchBoundaryError(str(exc)) from exc
    pending = [item for item in state.get("pendencias") or [] if isinstance(item, dict)]
    # Sem causa nova, conservar exatamente a ordenação temporal anterior.
    # A prioridade só desloca rotinas quando há condição causal no mesmo lote.
    causal_queued = any(item.get("acionamento_causal") for item in pending)
    pending.sort(key=lambda item: _pending_sort_key(item, causal_queued=causal_queued))
    if len(pending) > MAX_BATCH:
        raise BatchBoundaryError(
            f"fronteira possui {len(pending)} pendências; teto do lote é {MAX_BATCH}"
        )

    items: list[dict[str, Any]] = []
    sources = [mundo.WORLD_STATE_PATH.as_posix()]
    for raw in pending:
        item, item_sources = _project_item(repo, raw)
        items.append(item)
        sources = _source_list(sources, item_sources)

    batch_payload = [{"id": item.get("id"), "token": item["token"]} for item in items]
    batch_id = f"frn1.{_token(batch_payload, BATCH_HEX)}"
    result = {
        "schema_resolucao_fronteira": SCHEMA,
        "ok": True,
        "mutante": False,
        "lote_id": batch_id,
        "quantidade": len(items),
        "itens": items,
        "fontes_lidas": sources,
        "proximo_passo": {
            "acao": "decidir_sem_mudanca_em_conjunto",
            "regra": (
                "Avalie todos os itens nesta mesma inferência. Envie em `sem_mudanca` "
                "somente os itens que realmente não criam fato; omita os que exigem ação. "
                "Evento canônico e consequência Task45 nunca aceitam no-op. Candidato "
                "autônomo exige bloqueio canônico concreto. Grupos concorrentes são "
                "comprometidos por inteiro em `grupos_operacoes`. Condição causal leve "
                "exige motivo concreto; ausência de Ren não cancela um prazo."
            ),
            "entrada_aplicar": {
                "lote_id": batch_id,
                "sem_mudanca": [
                    {"id": "<id>", "token": "<token>", "nota": "<motivo concreto>"}
                ],
                "grupos_operacoes": [
                    {"id": "<id>", "token": "<token>", "bloqueios": {}}
                ],
            },
        },
    }

    if any(i["classificacao"] == "dar_continuidade_plano" for i in items):
        result["proximo_passo"]["entrada_aplicar"]["planos"] = [
            {"id": "<id>", "token": "<token>", "evento": "<tentar/resolver/replanejar/bloquear/desistir>"}]
        result["proximo_passo"]["regra"] += (
            " Planos usam `planos` neste mesmo lote: registrar evento e revisão, fato literal, "
            "resultado com prova/mecânica e seguimento. Contrato: docs/nv08-planos-personagens.md.")
    return result


def _normalize_note(value: Any) -> str:
    if not isinstance(value, str):
        raise BatchBoundaryError("nota de sem_mudanca deve ser texto")
    note = " ".join(value.split())
    if len(note) < 8:
        raise BatchBoundaryError("nota de sem_mudanca deve explicar o motivo")
    if len(note) > MAX_NOTE_CHARS:
        raise BatchBoundaryError(
            f"nota de sem_mudanca excede {MAX_NOTE_CHARS} caracteres"
        )
    return note


def _completed_map(repo: Path) -> dict[str, dict[str, Any]]:
    state = mundo.load_world_state(repo)
    return {
        str(item["id"]): item
        for item in state.get("concluidas_recentes") or []
        if isinstance(item, dict) and item.get("id")
    }


def _valid_token(token: Any, label: str) -> str:
    if (
        not isinstance(token, str)
        or len(token) != TOKEN_HEX
        or any(ch not in "0123456789abcdef" for ch in token)
    ):
        raise BatchBoundaryError(f"{label} inválido")
    return token


def _parse_plan(payload: Any) -> tuple[str, list[dict], list[dict], list[dict]]:
    if not isinstance(payload, dict):
        raise BatchBoundaryError("plano de lote deve ser mapa")
    batch_id = payload.get("lote_id")
    if not isinstance(batch_id, str) or not batch_id.startswith("frn1."):
        raise BatchBoundaryError("lote_id inválido")
    if set(payload) - {"lote_id", "sem_mudanca", "grupos_operacoes", "planos"}:
        raise BatchBoundaryError("plano de lote possui campos desconhecidos")
    raw = payload.get("sem_mudanca", [])
    if not isinstance(raw, list):
        raise BatchBoundaryError("sem_mudanca deve ser lista")
    if len(raw) > MAX_BATCH:
        raise BatchBoundaryError(f"sem_mudanca excede teto {MAX_BATCH}")

    decisions: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, value in enumerate(raw):
        if not isinstance(value, dict):
            raise BatchBoundaryError(f"sem_mudanca[{index}] deve ser mapa")
        pending_id = value.get("id")
        token = value.get("token")
        if not isinstance(pending_id, str) or not barreira_mundo.PENDING_ID_RE.fullmatch(
            pending_id
        ):
            raise BatchBoundaryError(f"sem_mudanca[{index}].id inválido")
        if pending_id in seen:
            raise BatchBoundaryError(f"pendência repetida no lote: {pending_id}")
        seen.add(pending_id)
        token = _valid_token(token, f"sem_mudanca[{index}].token")
        decisions.append(
            {"id": pending_id, "token": token, "nota": _normalize_note(value.get("nota"))}
        )
    raw_groups = payload.get("grupos_operacoes", [])
    if not isinstance(raw_groups, list) or len(raw_groups) > MAX_BATCH:
        raise BatchBoundaryError(f"grupos_operacoes deve ser lista com até {MAX_BATCH} itens")
    groups: list[dict[str, Any]] = []
    for index, value in enumerate(raw_groups):
        if not isinstance(value, dict) or set(value) != {"id", "token", "bloqueios"}:
            raise BatchBoundaryError(f"grupos_operacoes[{index}] possui estrutura inválida")
        pending_id = value["id"]
        if not isinstance(pending_id, str) or not barreira_mundo.PENDING_ID_RE.fullmatch(pending_id):
            raise BatchBoundaryError(f"grupos_operacoes[{index}].id inválido")
        if pending_id in seen:
            raise BatchBoundaryError(f"pendência repetida no lote: {pending_id}")
        seen.add(pending_id)
        if not isinstance(value["bloqueios"], dict):
            raise BatchBoundaryError(f"grupos_operacoes[{index}].bloqueios deve ser mapa")
        groups.append(
            {
                "id": pending_id,
                "token": _valid_token(value["token"], f"grupos_operacoes[{index}].token"),
                "bloqueios": value["bloqueios"],
            }
        )
    plans = payload.get("planos", [])
    if not isinstance(plans, list) or len(plans) + len(groups) + len(decisions) > MAX_BATCH:
        raise BatchBoundaryError("decisões do lote excedem o teto")
    for value in plans:
        if (not isinstance(value, dict) or set(value) - {"id", "token", "evento", "rolagens_ocultas", "deltas"}
                or not {"id", "token", "evento"} <= set(value)):
            raise BatchBoundaryError("decisão de plano exige id, token e evento")
        if not isinstance(value["id"], str) or not barreira_mundo.PENDING_ID_RE.fullmatch(value["id"]):
            raise BatchBoundaryError("id de pendência de plano inválido")
        if value["id"] in seen:
            raise BatchBoundaryError("pendência repetida no lote")
        seen.add(value["id"])
        _valid_token(value["token"], "planos.token")
        if not isinstance(value["evento"], dict):
            raise BatchBoundaryError("evento de plano deve ser mapa")
        effects = value.get("deltas", [])
        if not isinstance(effects, list) or len(effects) > 8 or any(planos_personagens.touches(d) for d in effects):
            raise BatchBoundaryError("efeitos do plano devem ser até oito deltas normais")
        try:
            for delta in effects:
                planos_personagens.transacoes.validate_delta(delta)
        except ValueError as exc:
            raise BatchBoundaryError(str(exc)) from exc
        rolls = value.get("rolagens_ocultas", [])
        if not isinstance(rolls, list) or len(rolls) > 1 or any(not isinstance(r, str) for r in rolls):
            raise BatchBoundaryError("decisão admite até uma saída literal de rolagem")
    return batch_id, decisions, groups, plans


def apply_batch(repo: Path, payload: Any) -> dict[str, Any]:
    """Aplica todos os no-ops aprovados numa chamada, com revalidação por item."""
    requested_batch_id, decisions, group_decisions, plan_decisions = _parse_plan(payload)
    current = prepare_batch(repo)
    current_by_id = {str(item["id"]): item for item in current["itens"]}
    completed = _completed_map(repo)

    validated: list[tuple[dict[str, str], dict[str, Any] | None]] = []
    already: list[dict[str, Any]] = []
    validated_groups: list[tuple[dict[str, Any], dict[str, Any] | None]] = []

    # Toda validação acontece antes da primeira escrita.
    for decision in decisions:
        pending_id = decision["id"]
        item = current_by_id.get(pending_id)
        if item is None:
            if pending_id in completed:
                already.append(
                    {
                        "id": pending_id,
                        "resultado": "ja_concluida",
                        "conclusao": completed[pending_id],
                    }
                )
                validated.append((decision, None))
                continue
            raise BatchBoundaryError(
                f"pendência {pending_id} não está aberta nem aparece nas conclusões recentes"
            )

        if decision["token"] != item.get("token"):
            raise BatchBoundaryError(
                f"pendência {pending_id} mudou desde preparar; refaça o lote"
            )
        if item.get("classificacao") == "dar_continuidade_plano":
            raise BatchBoundaryError("plano não aceita no-op genérico; registrar continuidade ou bloqueio")
        if item.get("classificacao") == "requer_fato_canonico":
            raise BatchBoundaryError(
                f"pendência {pending_id} é evento canônico e não aceita sem_mudanca"
            )
        if item.get("classificacao") == "requer_resolucao_sidequest":
            raise BatchBoundaryError(
                f"pendência {pending_id} exige resolução Task45 e não aceita sem_mudanca"
            )
        if item.get("classificacao") == "requer_resolucao_reacao":
            raise BatchBoundaryError(
                f"pendência {pending_id} exige compromisso/resolução da reação e não aceita sem_mudanca"
            )
        if item.get("classificacao") in {"comprometer_grupo_operacoes", "requer_resolucao_operacao"}:
            raise BatchBoundaryError(
                f"pendência {pending_id} pertence a operação adversarial e não aceita sem_mudanca"
            )
        if item.get("classificacao") in {"avaliar_candidato_autonomo", "avaliar_condicao_causal"}:
            barreira_mundo._validate_autonomous_noop(decision["nota"])
        validated.append((decision, item))

    for decision in group_decisions:
        pending_id = decision["id"]
        item = current_by_id.get(pending_id)
        if item is None:
            if pending_id in completed:
                already.append(
                    {"id": pending_id, "resultado": "ja_concluida", "conclusao": completed[pending_id]}
                )
                validated_groups.append((decision, None))
                continue
            raise BatchBoundaryError(
                f"pendência de grupo {pending_id} não está aberta nem concluída"
            )
        if decision["token"] != item.get("token"):
            raise BatchBoundaryError(
                f"pendência {pending_id} mudou desde preparar; refaça o lote"
            )
        if item.get("classificacao") != "comprometer_grupo_operacoes":
            raise BatchBoundaryError(f"pendência {pending_id} não é grupo de operações")
        validated_groups.append((decision, item))

    fresh_plans = []
    for decision in plan_decisions:
        item = current_by_id.get(decision["id"])
        if item is None:
            done = completed.get(decision["id"])
            if done is None or done.get("tipo") != planos_personagens.PENDING_TYPE:
                raise BatchBoundaryError("pendência de plano ausente")
            # O recibo precisa corresponder à decisão, não apenas ao mesmo ID.
            if done.get("decisao") != planos_personagens._digest(decision):
                raise BatchBoundaryError("retry de plano diverge da decisão já registrada")
            already.append({"id": decision["id"], "resultado": "ja_concluida", "conclusao": done})
            continue
        if item["classificacao"] != "dar_continuidade_plano" or item["token"] != decision["token"]:
            raise BatchBoundaryError("plano mudou desde preparar; refazer lote")
        fresh_plans.append(decision)
    try:
        plan_transaction = planos_personagens.compile_batch(repo, fresh_plans, current_by_id)
    except (ValueError, OSError, yaml.YAMLError) as exc:
        raise BatchBoundaryError(str(exc)) from exc

    # Um lote misto não pode gravar planos para só depois descobrir um grupo
    # inválido. Validação pura reutiliza exatamente o contrato do motor existente.
    if plan_transaction is not None:
        owners = {current_by_id[d["id"]]["contexto"]["plano_personagem"]["plano"]["agente"]["id"]
                  for d in fresh_plans}
        if any(item and (item.get("agente_leve") or item.get("agente")) in owners
               for _, item in validated):
            raise BatchBoundaryError("não concluir rotina e alterar plano do mesmo agente no mesmo lote")
        try:
            for decision, item in validated_groups:
                if item is not None:
                    operacoes_concorrentes.commit_group(repo, item["grupo_operacoes_id"],
                                                        decision["bloqueios"], validate_only=True)
        except operacoes_concorrentes.ConcurrentOperationError as exc:
            raise BatchBoundaryError(str(exc)) from exc

    plan_result = None
    if plan_transaction is not None:
        import turno
        try:
            plan_result = turno.register_transaction(repo, plan_transaction)
        except (ValueError, OSError, yaml.YAMLError) as exc:
            raise BatchBoundaryError(str(exc)) from exc

    applied: list[dict[str, Any]] = []
    committed_groups: list[dict[str, Any]] = []
    for decision, item in validated_groups:
        if item is None:
            continue
        try:
            result = operacoes_concorrentes.commit_group(
                repo, item["grupo_operacoes_id"], decision["bloqueios"]
            )
        except operacoes_concorrentes.ConcurrentOperationError as exc:
            raise BatchBoundaryError(str(exc)) from exc
        committed_groups.append(result)

    for decision, item in validated:
        if item is None:
            continue
        pending_id = decision["id"]
        if item.get("tipo") == "reavaliar_agente_leve":
            try:
                result = agentes_leves.conclude_noop(repo, pending_id, decision["nota"])
            except agentes_leves.LightAgentError as exc:
                raise BatchBoundaryError(str(exc)) from exc
        else:
            result = barreira_mundo.conclude(
                repo,
                pending_id,
                decision["nota"],
                no_change=item.get("classificacao") == "avaliar_candidato_autonomo",
            )
        applied.append(
            {
                "id": pending_id,
                "resultado": "sem_mudanca_concluida",
                "tipo": item.get("tipo"),
                "detalhe": result.get("concluida"),
            }
        )

    # Sincronizar também repara retries parciais e promove causas ainda aguardando.
    barrier = barreira_mundo.sync(repo)
    remaining = prepare_batch(repo)
    return {
        "schema_resolucao_fronteira": SCHEMA,
        "ok": True,
        "mutante": True,
        "lote_id_solicitado": requested_batch_id,
        "lote_id_atual": remaining["lote_id"],
        "aplicadas": applied,
        "grupos_comprometidos": committed_groups,
        **({"planos_aplicados": plan_result} if plan_result is not None else {}),
        "ja_aplicadas": already,
        "quantidade_restante": remaining["quantidade"],
        "requer_resolucao": remaining["itens"],
        "barreira": barrier,
        "idempotente": True,
        "proximo_passo": (
            {"acao": "continuar_turno"}
            if remaining["quantidade"] == 0
            else {
                "acao": "materializar_somente_itens_restantes",
                "regra": (
                    "Os no-ops já foram fechados em lote. Trabalhe somente os itens "
                    "restantes; não reavalie os concluídos."
                ),
            }
        ),
    }


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        result = prepare_batch(repo)
        if result["quantidade"] > MAX_BATCH:
            errors.append("lote excedeu teto")
        if len({item["id"] for item in result["itens"]}) != result["quantidade"]:
            errors.append("lote contém ids duplicados")
    except (
        BatchBoundaryError,
        mundo.WorldEngineError,
        barreira_mundo.WorldPendingBarrierError,
    ) as exc:
        errors.append(str(exc))
    return {"ok": not errors, "erros": errors}


def _read_stdin_plan() -> Any:
    raw = sys.stdin.read()
    if not raw.strip():
        raise BatchBoundaryError("aplicar exige JSON/YAML por stdin")
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise BatchBoundaryError(f"plano inválido: {exc}") from exc


def _dump(value: dict[str, Any]) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preparar")
    sub.add_parser("aplicar")
    sub.add_parser("check")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.command == "preparar":
            result = prepare_batch(repo)
        elif args.command == "aplicar":
            result = apply_batch(repo, _read_stdin_plan())
        else:
            result = check(repo)
        print(_dump(result), end="")
        return 0 if result.get("ok", True) else 1
    except (
        BatchBoundaryError,
        mundo.WorldEngineError,
        barreira_mundo.WorldPendingBarrierError,
    ) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
