#!/usr/bin/env python3
"""Guardrail de Contrato de Arco para o Mundo Vivo.

Esta camada NÃO agenda, sorteia, move, ativa, executa ou conclui nada. Ela apenas
filtra peças que outras camadas já pretendiam reconsiderar, respondendo antes:

- o agente estratégico é controlado pelo arco corrente?
- se for, está habilitado nesta parte da crônica?
- para ação autônoma, possui ao menos uma linha operacional corrente?
- a direção/entrada pertence ao arco corrente?
- uma presença/movimentação controlada já passou pelo marco mínimo de aparição?

O objetivo é impedir que scheduler, evento ou fronteira temporal contornem o
Contrato de Arco. Peças não controladas por arco (Night Watch, Red Sail, Casa de
Tyr, agentes leves etc.) permanecem livres e não pagam semântica de habilitação.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Iterable

import yaml

import arcos
import marcos_aparicao

CONTROL = Path("narrador/arcos/controle-mundo.yaml")
STRATEGIC_INDEX = Path("narrador/agentes/index.yaml")
VALID_AGENT_GROUPS = {"antagonistas"}
VALID_PURPOSES = {"reavaliacao", "evento", "movimento", "presenca"}
ACTION_PURPOSES = {"reavaliacao", "evento"}
APPEARANCE_PURPOSES = {"movimento", "presenca"}


class ArcWorldError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise ArcWorldError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ArcWorldError(f"{label} deve ser mapa")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArcWorldError(f"{label} deve ser texto não vazio")
    return value.strip()


def load_control(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / CONTROL), CONTROL.as_posix())
    if data.get("schema_controle_arco_mundo") != 1:
        raise ArcWorldError("controle do arco no Mundo Vivo deve usar schema 1")
    if data.get("natureza") != "roteador_reservado":
        raise ArcWorldError("controle do arco no Mundo Vivo deve ser roteador_reservado")
    agents = _map(data.get("agentes_estrategicos"), "agentes_estrategicos")
    for agent_id, raw in agents.items():
        _text(agent_id, "id de agente controlado")
        meta = _map(raw, f"agentes_estrategicos.{agent_id}")
        group = _text(meta.get("grupo"), f"agentes_estrategicos.{agent_id}.grupo")
        if group not in VALID_AGENT_GROUPS:
            raise ArcWorldError(f"grupo de arco inválido para {agent_id}: {group}")
        require_line = meta.get("requer_linha_para_acao")
        if not isinstance(require_line, bool):
            raise ArcWorldError(
                f"agentes_estrategicos.{agent_id}.requer_linha_para_acao deve ser booleano"
            )
        require_active = meta.get("requer_estado_ativo_para_acao", False)
        if not isinstance(require_active, bool):
            raise ArcWorldError(
                f"agentes_estrategicos.{agent_id}.requer_estado_ativo_para_acao deve ser booleano"
            )
    return data


def context(repo: Path) -> dict[str, Any]:
    try:
        info = arcos.current(repo)
    except arcos.ArcContractError as exc:
        raise ArcWorldError(str(exc)) from exc
    control = load_control(repo)
    return {
        "arco": info,
        "controle": control,
        "fontes_lidas": list(dict.fromkeys([*info["fontes_lidas"], CONTROL.as_posix()])),
    }


def _lines_for(info: dict[str, Any], agent_id: str) -> list[str]:
    return sorted(
        line_id
        for line_id, line in info["linhas_operacionais"].items()
        if agent_id in set(line.get("executores") or [])
    )


def _strategic_states(repo: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    cached = ctx.get("_agentes_estrategicos")
    if isinstance(cached, dict):
        return cached
    data = _map(_load(repo / STRATEGIC_INDEX), STRATEGIC_INDEX.as_posix())
    if data.get("schema_agentes") != 2 or data.get("natureza") != "reservado":
        raise ArcWorldError("índice de agentes estratégicos inválido")
    agents = _map(data.get("agentes"), "agentes")
    ctx["_agentes_estrategicos"] = agents
    ctx.setdefault("fontes_lidas", []).append(STRATEGIC_INDEX.as_posix())
    return agents


def strategic_agent_gate(
    repo: Path,
    agent_id: str,
    *,
    purpose: str,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Filtra agente estratégico sem abrir seu fragmento.

    Agente ausente do roteador é livre. Agente controlado precisa estar habilitado
    no arco; em reavaliação/evento também precisa de linha operacional, exceto o
    agente do plano mestre, que é a própria origem estratégica do arco.
    """
    if purpose not in VALID_PURPOSES:
        raise ArcWorldError(f"finalidade inválida: {purpose}")
    agent_id = _text(agent_id, "agent_id")
    ctx = ctx or context(repo)
    info = ctx["arco"]
    controlled = ctx["controle"]["agentes_estrategicos"].get(agent_id)
    if not isinstance(controlled, dict):
        return {
            "permitido": True,
            "agente": agent_id,
            "finalidade": purpose,
            "controlado_pelo_arco": False,
            "motivo": "agente_fora_do_escopo_do_contrato_de_arco",
            "linhas_operacionais": [],
            "arco_id": info["id"],
            "fontes_lidas": ctx["fontes_lidas"],
        }

    group = controlled["grupo"]
    master = info["plano_mestre"]["agente"]
    enabled = agent_id == master or agent_id in set(info["habilitacoes"][group])
    if not enabled:
        return {
            "permitido": False,
            "agente": agent_id,
            "finalidade": purpose,
            "controlado_pelo_arco": True,
            "grupo": group,
            "motivo": "agente_bloqueado_pelo_arco",
            "linhas_operacionais": [],
            "arco_id": info["id"],
            "fontes_lidas": ctx["fontes_lidas"],
        }

    lines = _lines_for(info, agent_id)
    if purpose in ACTION_PURPOSES and bool(controlled.get("requer_estado_ativo_para_acao", False)):
        agents = _strategic_states(repo, ctx)
        meta = agents.get(agent_id)
        if not isinstance(meta, dict):
            raise ArcWorldError(f"agente controlado inexistente no índice: {agent_id}")
        if meta.get("estado") != "ativo":
            return {
                "permitido": False,
                "agente": agent_id,
                "finalidade": purpose,
                "controlado_pelo_arco": True,
                "grupo": group,
                "motivo": "agente_ainda_nao_ativo_no_mundo",
                "linhas_operacionais": lines,
                "arco_id": info["id"],
                "fontes_lidas": list(dict.fromkeys(ctx["fontes_lidas"])),
            }
    needs_line = bool(controlled["requer_linha_para_acao"]) and purpose in ACTION_PURPOSES
    if needs_line and agent_id != master and not lines:
        return {
            "permitido": False,
            "agente": agent_id,
            "finalidade": purpose,
            "controlado_pelo_arco": True,
            "grupo": group,
            "motivo": "agente_sem_linha_operacional_no_arco",
            "linhas_operacionais": [],
            "arco_id": info["id"],
            "fontes_lidas": ctx["fontes_lidas"],
        }

    appearance = None
    sources = list(ctx["fontes_lidas"])
    if purpose in APPEARANCE_PURPOSES and agent_id != master:
        milestone_ctx = ctx.get("_marcos_aparicao")
        if not isinstance(milestone_ctx, dict):
            try:
                milestone_ctx = marcos_aparicao.context(repo, arc_info=info)
            except marcos_aparicao.AppearanceMilestoneError as exc:
                raise ArcWorldError(str(exc)) from exc
            ctx["_marcos_aparicao"] = milestone_ctx
        try:
            appearance = marcos_aparicao.gate(
                repo, agent_id, ctx=milestone_ctx, arc_info=info
            )
        except marcos_aparicao.AppearanceMilestoneError as exc:
            raise ArcWorldError(str(exc)) from exc
        sources = list(dict.fromkeys([*sources, *appearance.get("fontes_lidas", [])]))
        if not appearance["permitido"]:
            return {
                "permitido": False,
                "agente": agent_id,
                "finalidade": purpose,
                "controlado_pelo_arco": True,
                "grupo": group,
                "motivo": appearance["motivo"],
                "linhas_operacionais": lines,
                "marco_aparicao": appearance,
                "arco_id": info["id"],
                "fontes_lidas": sources,
            }

    return {
        "permitido": True,
        "agente": agent_id,
        "finalidade": purpose,
        "controlado_pelo_arco": True,
        "grupo": group,
        "motivo": "agente_mestre_do_arco" if agent_id == master else "agente_habilitado_pelo_arco",
        "linhas_operacionais": lines,
        "marco_aparicao": appearance,
        "arco_id": info["id"],
        "fontes_lidas": sources,
    }


def direction_gate(repo: Path, direction_id: str, *, ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    direction_id = _text(direction_id, "direction_id")
    ctx = ctx or context(repo)
    info = ctx["arco"]
    allowed = direction_id in set(info["habilitacoes"]["direcoes"])
    return {
        "permitido": allowed,
        "direcao": direction_id,
        "motivo": "direcao_habilitada_pelo_arco" if allowed else "direcao_bloqueada_pelo_arco",
        "arco_id": info["id"],
        "fontes_lidas": ctx["fontes_lidas"],
    }


def entry_gate(repo: Path, entry_id: str, *, ctx: dict[str, Any] | None = None) -> dict[str, Any]:
    entry_id = _text(entry_id, "entry_id")
    ctx = ctx or context(repo)
    info = ctx["arco"]
    allowed = entry_id in set(info["habilitacoes"]["aliados"])
    return {
        "permitido": allowed,
        "entrada": entry_id,
        "motivo": "entrada_habilitada_pelo_arco" if allowed else "entrada_bloqueada_pelo_arco",
        "arco_id": info["id"],
        "fontes_lidas": ctx["fontes_lidas"],
    }


def filter_world_triggers(
    repo: Path,
    records: Iterable[dict[str, Any]],
    *,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Filtra triggers temporais já calculados pelo mundo, sem mutar estado."""
    ctx = ctx or context(repo)
    kept: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    sources = list(ctx["fontes_lidas"])
    for record in records:
        kind = record.get("tipo")
        agent = record.get("agente")
        purpose = "reavaliacao" if kind == "reavaliar_agente" else "movimento" if kind == "movimento" else None
        if purpose and isinstance(agent, str) and agent:
            gate = strategic_agent_gate(repo, agent, purpose=purpose, ctx=ctx)
            sources.extend(gate.get("fontes_lidas") or [])
            if not gate["permitido"]:
                blocked.append({"id": record.get("id"), "tipo": kind, "agente": agent, "motivo": gate["motivo"]})
                continue
        kept.append(record)
    return {
        "permitidos": kept,
        "bloqueados": blocked,
        "fontes_lidas": list(dict.fromkeys(sources)),
    }


def filter_event_agents(
    repo: Path,
    agent_ids: Iterable[str],
    *,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Remove agentes estratégicos bloqueados sem cancelar o evento mundial."""
    ctx = ctx or context(repo)
    allowed: list[str] = []
    blocked: list[dict[str, str]] = []
    for agent_id in agent_ids:
        gate = strategic_agent_gate(repo, str(agent_id), purpose="evento", ctx=ctx)
        if gate["permitido"]:
            allowed.append(str(agent_id))
        else:
            blocked.append({"agente": str(agent_id), "motivo": gate["motivo"]})
    return {
        "permitidos": allowed,
        "bloqueados": blocked,
        "fontes_lidas": ctx["fontes_lidas"],
    }


def prune_pending(
    repo: Path,
    world_state: dict[str, Any],
    *,
    ctx: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Remove pendências incompatíveis com o arco e poda candidatos de eventos.

    Não transforma cancelamento em fato: apenas evita que uma avaliação antiga ou
    produzida por camada ainda não migrada atravesse o guardrail do arco.
    """
    ctx = ctx or context(repo)
    state = copy.deepcopy(world_state)
    kept: list[dict[str, Any]] = []
    removed: list[dict[str, str]] = []
    events_changed: list[str] = []

    for item in state.get("pendencias") or []:
        kind = item.get("tipo")
        if kind in {"reavaliar_agente", "movimento"} and item.get("agente"):
            purpose = "reavaliacao" if kind == "reavaliar_agente" else "movimento"
            gate = strategic_agent_gate(repo, str(item["agente"]), purpose=purpose, ctx=ctx)
            if not gate["permitido"]:
                removed.append({"id": str(item.get("id")), "motivo": gate["motivo"]})
                continue
        elif kind in {"avaliar_direcao", "ativar_direcao"} and item.get("direcao"):
            gate = direction_gate(repo, str(item["direcao"]), ctx=ctx)
            if not gate["permitido"]:
                removed.append({"id": str(item.get("id")), "motivo": gate["motivo"]})
                continue
        elif kind == "avaliar_entrada" and item.get("entrada"):
            gate = entry_gate(repo, str(item["entrada"]), ctx=ctx)
            if not gate["permitido"]:
                removed.append({"id": str(item.get("id")), "motivo": gate["motivo"]})
                continue
        elif kind == "evento_mundial":
            values = item.get("agentes_afetados")
            if isinstance(values, list) and values:
                filtered = filter_event_agents(repo, [str(v) for v in values], ctx=ctx)
                if filtered["permitidos"] != values:
                    item["agentes_afetados"] = filtered["permitidos"]
                    events_changed.append(str(item.get("id")))
        kept.append(item)

    state["pendencias"] = kept
    return {
        "estado": state,
        "alterou": bool(removed or events_changed),
        "pendencias_removidas": removed,
        "eventos_atualizados": events_changed,
        "fontes_lidas": ctx["fontes_lidas"],
    }


def validate(repo: Path) -> dict[str, Any]:
    control = load_control(repo)
    try:
        info = arcos.current(repo)
    except arcos.ArcContractError as exc:
        raise ArcWorldError(str(exc)) from exc
    index = _map(_load(repo / STRATEGIC_INDEX), STRATEGIC_INDEX.as_posix())
    if index.get("schema_agentes") != 2:
        raise ArcWorldError("índice de agentes estratégicos deve usar schema 2")
    agents = _map(index.get("agentes"), "agentes")
    missing = sorted(set(control["agentes_estrategicos"]) - set(agents))
    if missing:
        raise ArcWorldError("controle de arco referencia agente inexistente: " + ", ".join(missing))
    master = info["plano_mestre"]["agente"]
    if master not in control["agentes_estrategicos"]:
        raise ArcWorldError("agente do plano mestre deve estar no controle do Mundo Vivo")
    milestone_validation = marcos_aparicao.validate(repo, check_source=False)
    if not milestone_validation["ok"]:
        raise ArcWorldError(
            "marcos de aparição inválidos: " + "; ".join(milestone_validation["erros"])
        )
    return {
        "ok": True,
        "arco_id": info["id"],
        "agentes_controlados": len(control["agentes_estrategicos"]),
        "fontes_lidas": list(dict.fromkeys([*info["fontes_lidas"], CONTROL.as_posix(), STRATEGIC_INDEX.as_posix(), marcos_aparicao.INDEX.as_posix(), marcos_aparicao.STATE.as_posix()])),
    }
