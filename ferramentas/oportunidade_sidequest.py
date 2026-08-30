#!/usr/bin/env python3
"""Task 40 — Emergent Sidequest Opportunity Boundary.

Esta porta NÃO cria sidequest. Ela só monta um pacote reservado de planejamento
quando o próprio narrador sinaliza que uma cena produziu uma âncora causal
concreta suficiente para talvez nascer uma aventura.

Sem sinal explícito não há leitura. Presença incidental não é âncora. A porta é
somente-leitura, não sorteia nada, não varre NPCs/quests e não abre o catálogo
secreto da Task 33. Se o orçamento de missões já estiver cheio, falha cedo antes
de consultar relação, mundo, arco, Juppongatana, recompensa ou Task 39.
"""
from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any

import yaml

import arco_mundo
import condicoes_mundo
import ecologia_local
import estado_relacional
import eventos_canonicos
import intencoes_canonicas
import mundo
import oportunidades
import progressao_juppongatana
import recompensas
import transacoes

MAX_PAYLOAD_BYTES = 8 * 1024
MAX_INTENT_FRAGMENTS = 3
MAX_HORIZON_DAYS = 14
MAX_ACTORS = 6
MAX_JUPPONGATANA = 4
MAX_ANCHOR_CHARS = 320
MIN_ANCHOR_CHARS = 20
MAX_OPEN_QUESTS_PROJECTED = 3
REWARD_ENVELOPE = Path("narrador/recompensas/envelope-sidequest.yaml")
SHEET = Path("personagens/jogador/ficha.yaml")
NPC_INDEX = estado_relacional.NPC_INDEX

VALID_ORIGIN_TYPES = {
    "conversa_npc",
    "carta",
    "mensagem",
    "consequencia_npc",
    "evento_canonico",
    "fato_de_cena",
}
VALID_ANCHOR_TYPES = {
    "pedido",
    "necessidade",
    "problema",
    "pista",
    "ameaca",
    "consequencia",
    "mudanca",
    "mensagem",
    "carta",
    "conflito",
}
FORBIDDEN_ORIGIN_TYPES = {"presenca_incidental"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
NPC_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,95}$")
VALUE_RANK = {"baixo": 1, "moderado": 2, "alto": 3}
VALUE_BY_RANK = {value: key for key, value in VALUE_RANK.items()}


class EmergentSidequestOpportunityError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise EmergentSidequestOpportunityError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EmergentSidequestOpportunityError(f"{label} deve ser mapa")
    return value


def _text(value: Any, label: str, *, minimum: int = 1, maximum: int | None = None) -> str:
    if not isinstance(value, str):
        raise EmergentSidequestOpportunityError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if len(result) < minimum:
        raise EmergentSidequestOpportunityError(f"{label} deve ter ao menos {minimum} caracteres")
    if maximum is not None and len(result) > maximum:
        raise EmergentSidequestOpportunityError(f"{label} excede {maximum} caracteres")
    return result


def _stable_id(value: Any, label: str) -> str:
    result = _text(value, label, maximum=128)
    if not ID_RE.fullmatch(result):
        raise EmergentSidequestOpportunityError(
            f"{label} deve ser id estável ASCII minúsculo (a-z, 0-9, _, ., :, -)"
        )
    return result


def _npc_id(value: Any) -> str:
    result = _text(value, "npc_id", maximum=96)
    if not NPC_RE.fullmatch(result):
        raise EmergentSidequestOpportunityError("npc_id deve ser slug ASCII minúsculo")
    return result


def _local_id(value: Any) -> str:
    result = _text(value, "local_id", maximum=96)
    if not NPC_RE.fullmatch(result):
        raise EmergentSidequestOpportunityError("local_id deve ser id canônico ASCII minúsculo")
    return result


def _rendered_bytes(payload: dict[str, Any]) -> int:
    return len(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False).encode("utf-8")
    )


def _bounded(payload: dict[str, Any]) -> dict[str, Any]:
    size = _rendered_bytes(payload)
    if size > MAX_PAYLOAD_BYTES:
        raise EmergentSidequestOpportunityError(
            f"pacote Task40 excede orçamento: {size} > {MAX_PAYLOAD_BYTES} bytes"
        )
    payload["orcamento_pacote"] = {
        "bytes": size,
        "max_bytes": MAX_PAYLOAD_BYTES,
        "intencoes_lidas": int(payload.get("metricas", {}).get("intencoes_lidas", 0)),
        "max_intencoes": MAX_INTENT_FRAGMENTS,
    }
    # O metadado acima também precisa caber no teto real de saída.
    final_size = _rendered_bytes(payload)
    if final_size > MAX_PAYLOAD_BYTES:
        raise EmergentSidequestOpportunityError(
            f"pacote Task40 excede orçamento após metadados: {final_size} > {MAX_PAYLOAD_BYTES} bytes"
        )
    payload["orcamento_pacote"]["bytes"] = final_size
    return payload


def decline() -> dict[str, Any]:
    """Codex viu a cena e decidiu que não há oportunidade: zero leitura, zero escrita."""
    return _bounded(
        {
            "ok": True,
            "resultado": "oportunidade_recusada_pelo_narrador",
            "read_only": True,
            "mutacoes_aplicadas": False,
            "fontes_lidas": [],
            "metricas": {"intencoes_lidas": 0, "scans_globais": 0},
        }
    )


def _validate_signal(
    *,
    origin_type: Any,
    origin_id: Any,
    anchor_type: Any,
    anchor: Any,
    npc_id: Any,
    local_id: Any,
    danger: Any,
    tier: Any,
) -> dict[str, Any]:
    origin_type = _text(origin_type, "origem_tipo", maximum=40)
    if origin_type in FORBIDDEN_ORIGIN_TYPES:
        raise EmergentSidequestOpportunityError(
            "presença incidental nunca é âncora suficiente para Task40"
        )
    if origin_type not in VALID_ORIGIN_TYPES:
        raise EmergentSidequestOpportunityError(
            "origem_tipo deve ser: " + ", ".join(sorted(VALID_ORIGIN_TYPES))
        )
    origin_id = _stable_id(origin_id, "origem_id")
    anchor_type = _text(anchor_type, "ancora_tipo", maximum=40)
    if anchor_type == "presenca" or anchor_type not in VALID_ANCHOR_TYPES:
        raise EmergentSidequestOpportunityError(
            "ancora_tipo deve representar fato causal concreto, nunca mera presença"
        )
    anchor = _text(
        anchor,
        "ancora",
        minimum=MIN_ANCHOR_CHARS,
        maximum=MAX_ANCHOR_CHARS,
    )
    if origin_type in {"conversa_npc", "consequencia_npc"} and npc_id is None:
        raise EmergentSidequestOpportunityError(
            f"{origin_type} exige npc_id explícito; Task40 não procura NPCs"
        )
    npc = _npc_id(npc_id) if npc_id is not None else None
    local = _local_id(local_id) if local_id is not None else None
    if danger not in recompensas.VALID_DANGER:
        raise EmergentSidequestOpportunityError(
            "periculosidade deve ser baixa, media, alta ou letal"
        )
    if tier is not None and (
        isinstance(tier, bool) or not isinstance(tier, int) or not 1 <= tier <= 4
    ):
        raise EmergentSidequestOpportunityError("tier deve ficar entre 1 e 4")
    return {
        "origem_tipo": origin_type,
        "origem_id": origin_id,
        "ancora_tipo": anchor_type,
        "ancora": anchor,
        "npc_id": npc,
        "local_id": local,
        "periculosidade": danger,
        "tier": tier,
    }


def _project_open_quests(state: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for mission_id, mission in sorted((state.get("missoes") or {}).items()):
        if not isinstance(mission, dict) or mission.get("estado") not in oportunidades.OPEN_STATES:
            continue
        item = {"id": mission.get("id", mission_id), "estado": mission.get("estado")}
        for key in ("quest_id", "npc_id", "origem", "tipo"):
            value = mission.get(key)
            if value is not None:
                item[key] = value
        result.append(item)
    return result[:MAX_OPEN_QUESTS_PROJECTED]


def _early_budget_gate(
    repo: Path,
) -> tuple[dict[str, Any], dict[str, Any], list[str], dict[str, Any] | None]:
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise EmergentSidequestOpportunityError(str(exc)) from exc
    sources = [oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix()]
    active, opened = oportunidades._mission_counts(state)
    budget = index["orcamento"]
    status = {
        "ativas": active,
        "abertas": opened,
        "max_ativas": budget["max_ativas"],
        "max_abertas": budget["max_em_aberto"],
        "atuais": _project_open_quests(state),
    }
    if active >= budget["max_ativas"]:
        return index, state, sources, {
            "ok": True,
            "resultado": "limite_ativas",
            "read_only": True,
            "mutacoes_aplicadas": False,
            "quests": status,
            "regra": "o horizonte secreto não é aberto quando duas sidequests já estão aceitas",
            "fontes_lidas": sources,
            "metricas": {"intencoes_lidas": 0, "scans_globais": 0},
        }
    if opened >= budget["max_em_aberto"]:
        return index, state, sources, {
            "ok": True,
            "resultado": "limite_abertas",
            "read_only": True,
            "mutacoes_aplicadas": False,
            "quests": status,
            "regra": "o horizonte secreto não é aberto quando o orçamento de missões abertas já está cheio",
            "fontes_lidas": sources,
            "metricas": {"intencoes_lidas": 0, "scans_globais": 0},
        }
    return index, state, sources, None


def _effective_relationship(
    repo: Path,
    npc_id: str | None,
) -> tuple[dict[str, Any] | None, list[str]]:
    if npc_id is None:
        return None, []
    data = _map(_load(repo / NPC_INDEX), NPC_INDEX.as_posix())
    npcs = _map(data.get("npcs"), "estado/npcs/index.yaml:npcs")
    entry = npcs.get(npc_id)
    if not isinstance(entry, dict) or not isinstance(entry.get("arquivo"), str):
        raise EmergentSidequestOpportunityError(
            f"{npc_id}: NPC não existe no índice; Task40 não faz busca aproximada"
        )
    rel = Path(entry["arquivo"])
    doc = _map(_load(repo / rel), rel.as_posix())
    payload = _map(doc.get("npc"), f"{rel}:npc")
    try:
        pending = transacoes.load_pending(repo)
        effective, _ = transacoes.overlay_target(payload, pending, f"npc:{npc_id}")
        projection = estado_relacional.project(effective.get("medidores"))
    except (OSError, ValueError, estado_relacional.RelationshipStateError) as exc:
        raise EmergentSidequestOpportunityError(str(exc)) from exc
    projection.update(
        {
            "npc_id": npc_id,
            "nome": effective.get("nome") or entry.get("nome") or npc_id,
            "identidade_relacional": effective.get("identidade_relacional", "ren"),
        }
    )
    sources = [NPC_INDEX.as_posix(), rel.as_posix()]
    if (repo / transacoes.PENDING_PATH).is_file():
        sources.append(transacoes.PENDING_PATH.as_posix())
    return projection, list(dict.fromkeys(sources))


def _intent_horizon(
    repo: Path,
    now: mundo.WorldInstant,
) -> tuple[list[dict[str, Any]], list[str], int]:
    try:
        index = intencoes_canonicas.load_index(repo)
        catalog = eventos_canonicos.load_catalog(repo)
    except (
        intencoes_canonicas.CanonicalIntentError,
        eventos_canonicos.CanonicalEventError,
    ) as exc:
        raise EmergentSidequestOpportunityError(str(exc)) from exc

    horizon = now.minute + MAX_HORIZON_DAYS * 24 * 60
    candidates: list[tuple[int, str, dict[str, Any]]] = []
    for event_id, meta in catalog["eventos"].items():
        if event_id in index["passado_congelado"]:
            continue
        instant = mundo.parse_instant(meta["ativacao"]["data"], meta["ativacao"]["hora"])
        if now.minute < instant.minute <= horizon:
            candidates.append((instant.minute, event_id, meta))
    candidates.sort(key=lambda item: (item[0], item[1]))
    selected = candidates[:MAX_INTENT_FRAGMENTS]

    sources = [intencoes_canonicas.INDEX.as_posix(), eventos_canonicos.CATALOG.as_posix()]
    compatible: list[dict[str, Any]] = []
    for minute, event_id, meta in selected:
        try:
            intent = intencoes_canonicas.load_intent(
                repo,
                event_id,
                index=index,
                catalog=catalog,
            )
        except intencoes_canonicas.CanonicalIntentError as exc:
            raise EmergentSidequestOpportunityError(str(exc)) from exc
        sources.append(intent["_fonte"])
        contract = intent["contrato_rewrite"]
        if not contract["integracao_sidequest"]:
            continue
        compatible.append(
            {
                "evento_id": event_id,
                "ativacao": copy.deepcopy(meta["ativacao"]),
                "intencao": copy.deepcopy(intent["intencao_canonica"]),
                "elasticidade": {
                    "modos": list(contract["modos_permitidos"]),
                    "atraso_maximo_horas": contract["atraso_maximo_horas"],
                    "satisfacao_antecipada": contract["satisfacao_antecipada"],
                    "reancoragem_local": contract["reancoragem_local"],
                    "troca_de_atores": contract["troca_de_atores"],
                },
            }
        )
    return compatible, list(dict.fromkeys(sources)), len(selected)


def _causal_actors_and_juppongatana(
    repo: Path,
    npc_id: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    try:
        ctx = arco_mundo.context(repo)
    except arco_mundo.ArcWorldError as exc:
        raise EmergentSidequestOpportunityError(str(exc)) from exc
    sources = list(ctx.get("fontes_lidas") or [])
    if not ctx.get("configurado"):
        origin = [{"id": npc_id, "papel": "origem"}] if npc_id else []
        return origin, [], sources

    arc = ctx["arco"]
    ordered: list[str] = [arc["plano_mestre"]["agente"]]
    for line in arc["linhas_operacionais"].values():
        for executor in line.get("executores") or []:
            if executor not in ordered:
                ordered.append(executor)

    actors: list[dict[str, Any]] = []
    if npc_id is not None:
        actors.append({"id": npc_id, "papel": "origem", "causal_agora": True})
    allowed_ids: set[str] = set()
    for agent_id in ordered:
        if len(actors) >= MAX_ACTORS:
            break
        try:
            gate = arco_mundo.strategic_agent_gate(
                repo,
                agent_id,
                purpose="reavaliacao",
                ctx=ctx,
            )
        except arco_mundo.ArcWorldError as exc:
            raise EmergentSidequestOpportunityError(str(exc)) from exc
        sources.extend(gate.get("fontes_lidas") or [])
        if not gate["permitido"]:
            continue
        allowed_ids.add(agent_id)
        if agent_id == npc_id:
            continue
        actors.append(
            {
                "id": agent_id,
                "papel": "ator_estrategico",
                "linhas": list(gate.get("linhas_operacionais") or [])[:4],
                "causal_agora": True,
            }
        )

    try:
        strategic = arco_mundo._strategic_states(repo, ctx)
        policy = progressao_juppongatana.load_policy(repo)
        progression = progressao_juppongatana.load_state(repo)
    except (
        arco_mundo.ArcWorldError,
        progressao_juppongatana.JuppongatanaProgressionError,
    ) as exc:
        raise EmergentSidequestOpportunityError(str(exc)) from exc
    sources.extend(
        [
            arco_mundo.STRATEGIC_INDEX.as_posix(),
            progressao_juppongatana.POLICY.as_posix(),
            progressao_juppongatana.STATE.as_posix(),
        ]
    )
    neutralized = {
        item["membro"]
        for item in progression["neutralizacoes"]
        if isinstance(item, dict) and isinstance(item.get("membro"), str)
    }
    possible: list[dict[str, Any]] = []
    for member_id in arc["habilitacoes"]["antagonistas"]:
        if member_id not in policy["membros"] or member_id in neutralized:
            continue
        meta = policy["membros"][member_id]
        agent = strategic.get(member_id, {})
        possible.append(
            {
                "id": member_id,
                "nome": meta["nome"],
                "circulo": meta["circulo"],
                "estado": agent.get("estado"),
                "presenca": agent.get("presenca"),
                "causal_agora": member_id in allowed_ids,
            }
        )
        if len(possible) >= MAX_JUPPONGATANA:
            break
    return actors, possible, list(dict.fromkeys(sources))


def _character_tier(repo: Path) -> tuple[int, list[str]]:
    data = _map(_load(repo / SHEET), SHEET.as_posix())
    identity = _map(data.get("identidade"), "ficha.identidade")
    level = identity.get("nivel")
    if isinstance(level, bool) or not isinstance(level, int) or level < 1:
        raise EmergentSidequestOpportunityError("ficha não contém nível válido")
    if level <= 4:
        tier = 1
    elif level <= 10:
        tier = 2
    elif level <= 16:
        tier = 3
    else:
        tier = 4
    return tier, [SHEET.as_posix()]


def _load_reward_router(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / REWARD_ENVELOPE), REWARD_ENVELOPE.as_posix())
    if (
        data.get("schema_envelope_sidequest") != 1
        or data.get("natureza") != "roteador_operacional_nao_canonico"
        or data.get("fonte_autoritativa") != recompensas.TABLES.as_posix()
        or data.get("geracao") != "proibida_task40"
    ):
        raise EmergentSidequestOpportunityError("roteador de envelope de recompensa Task40 inválido")
    return data


def _reward_envelope(
    repo: Path,
    *,
    tier: int | None,
    danger: str,
    local_id: str | None,
) -> tuple[dict[str, Any], list[str]]:
    sources: list[str] = [REWARD_ENVELOPE.as_posix()]
    router = _load_reward_router(repo)
    if tier is None:
        tier, tier_sources = _character_tier(repo)
        sources.extend(tier_sources)
    key = str(tier)
    tiers = _map(router.get("tiers"), "envelope.tiers")
    risks = _map(router.get("riscos"), "envelope.riscos")
    families = _map(router.get("familias"), "envelope.familias")
    if key not in tiers or danger not in risks:
        raise EmergentSidequestOpportunityError("tier/risco ausente no envelope Task40")
    tier_cfg = _map(tiers[key], f"tiers.{key}")
    risk_cfg = _map(risks[danger], f"riscos.{danger}")

    result: dict[str, Any] = {
        "tier": tier,
        "periculosidade": danger,
        "max_itens": tier_cfg["max_itens"],
        "pontos_base": tier_cfg["pontos_base"],
        "bonus_risco": risk_cfg["bonus_pontos"],
        "regra": "envelope de planejamento; Task40 não sorteia, cria ou entrega recompensa",
    }
    if local_id is None:
        result.update(
            {
                "familia_local": None,
                "pontos": tier_cfg["pontos_base"] + risk_cfg["bonus_pontos"],
                "teto_valor": "refinar_quando_houver_local_canonico",
                "categorias": [],
            }
        )
        return result, list(dict.fromkeys(sources))

    try:
        ecology = ecologia_local.lookup_canonical(repo, local_id)
    except ecologia_local.LocalEcologyError as exc:
        raise EmergentSidequestOpportunityError(str(exc)) from exc
    sources.extend(ecology.get("fontes_lidas") or [])
    family = ecology["perfil"]["familia"]
    family_cfg = families.get(family)
    if not isinstance(family_cfg, dict):
        raise EmergentSidequestOpportunityError(
            f"família ecológica sem envelope Task40: {family}"
        )
    base_rank = VALUE_RANK[family_cfg["teto_valor_base"]]
    ceiling = min(3, base_rank + int(risk_cfg["aumento_teto_valor"]))
    points = max(
        1,
        int(tier_cfg["pontos_base"])
        + int(risk_cfg["bonus_pontos"])
        + int(family_cfg["modificador_pontos"]),
    )
    result.update(
        {
            "familia_local": family,
            "pontos": points,
            "teto_valor": VALUE_BY_RANK[ceiling],
            "categorias": list(family_cfg["categorias"]),
        }
    )
    return result, list(dict.fromkeys(sources))


def _world_projection(
    repo: Path,
    *,
    now: mundo.WorldInstant,
    local_id: str | None,
) -> tuple[dict[str, Any], list[str]]:
    try:
        conditions = condicoes_mundo.project(repo, local_id=local_id, now=now)
    except condicoes_mundo.WorldConditionError as exc:
        raise EmergentSidequestOpportunityError(str(exc)) from exc
    return {
        "agora": mundo.instant_parts(now),
        "local_id": local_id,
        "condicoes_persistentes": list(conditions.get("ativas") or []),
    }, list(conditions.get("fontes_lidas") or [])


def plan(
    repo: Path,
    *,
    signaled: bool,
    origin_type: str | None = None,
    origin_id: str | None = None,
    anchor_type: str | None = None,
    anchor: str | None = None,
    npc_id: str | None = None,
    local_id: str | None = None,
    danger: str = "media",
    tier: int | None = None,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    """Monta o pacote Task40. Nunca escreve nem materializa uma sidequest."""
    if not signaled:
        return _bounded(
            {
                "ok": True,
                "resultado": "nao_sinalizada",
                "read_only": True,
                "mutacoes_aplicadas": False,
                "fontes_lidas": [],
                "metricas": {"intencoes_lidas": 0, "scans_globais": 0},
            }
        )

    # Toda validação da âncora ocorre antes da primeira leitura do repositório.
    signal = _validate_signal(
        origin_type=origin_type,
        origin_id=origin_id,
        anchor_type=anchor_type,
        anchor=anchor,
        npc_id=npc_id,
        local_id=local_id,
        danger=danger,
        tier=tier,
    )

    index, state, sources, blocked = _early_budget_gate(repo)
    if blocked is not None:
        blocked["origem"] = {
            "tipo": signal["origem_tipo"],
            "id": signal["origem_id"],
            "ancora_tipo": signal["ancora_tipo"],
        }
        return _bounded(blocked)

    if now is None:
        try:
            now, _ = mundo.load_canonical_time(repo)
        except mundo.WorldEngineError as exc:
            raise EmergentSidequestOpportunityError(str(exc)) from exc
        sources.append(mundo.TIME_PATH.as_posix())

    relationship, relation_sources = _effective_relationship(repo, signal["npc_id"])
    sources.extend(relation_sources)
    world, world_sources = _world_projection(
        repo,
        now=now,
        local_id=signal["local_id"],
    )
    sources.extend(world_sources)
    intents, intent_sources, intent_reads = _intent_horizon(repo, now)
    sources.extend(intent_sources)
    actors, juppongatana, actor_sources = _causal_actors_and_juppongatana(
        repo,
        signal["npc_id"],
    )
    sources.extend(actor_sources)
    reward, reward_sources = _reward_envelope(
        repo,
        tier=signal["tier"],
        danger=signal["periculosidade"],
        local_id=signal["local_id"],
    )
    sources.extend(reward_sources)

    active, opened = oportunidades._mission_counts(state)
    payload = {
        "ok": True,
        "resultado": "material_para_planejamento",
        "read_only": True,
        "mutacoes_aplicadas": False,
        "origem": {
            "tipo": signal["origem_tipo"],
            "id": signal["origem_id"],
            "npc_id": signal["npc_id"],
            "ancora_tipo": signal["ancora_tipo"],
            "ancora": signal["ancora"],
        },
        "relacao_efetiva": relationship,
        "quests": {
            "ativas": active,
            "abertas": opened,
            "max_ativas": index["orcamento"]["max_ativas"],
            "max_abertas": index["orcamento"]["max_em_aberto"],
            "atuais": _project_open_quests(state),
        },
        "prazo_mundo": world,
        "horizonte_intencoes_canonicas": {
            "janela_dias": MAX_HORIZON_DAYS,
            "avaliadas": intent_reads,
            "compativeis": intents,
            "regra": "no máximo três intenções cronologicamente próximas são abertas; ausência de match não autoriza scan adicional",
        },
        "atores_causalmente_disponiveis": actors,
        "juppongatana_possiveis": juppongatana,
        "envelope_recompensa": reward,
        "autoridade": {
            "pode_planejar": True,
            "pode_criar_missao": False,
            "pode_oferecer_missao": False,
            "pode_reescrever_intencao": False,
            "pode_marcar_intencao_satisfeita": False,
            "regra": "o pacote autoriza pensar uma aventura, não canonizá-la; descartar é sempre válido",
        },
        "fontes_lidas": list(dict.fromkeys(sources)),
        "metricas": {
            "intencoes_lidas": intent_reads,
            "scans_globais": 0,
            "catalogo_task33_aberto": False,
            "transcricao_lida": False,
            "escritas": 0,
        },
    }
    return _bounded(payload)


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        router = _load_reward_router(repo)
        authoritative = recompensas.load_tables(repo)
        cfg = authoritative["orcamento_v2"]
        expected_tiers = {
            str(key): {
                "pontos_base": int(cfg["pontos_por_tier"][str(key)]),
                "max_itens": int(cfg["max_itens_por_tier"][str(key)]),
            }
            for key in range(1, 5)
        }
        if router.get("tiers") != expected_tiers:
            errors.append("envelope Task40 divergiu dos tiers do Reward Budget v2")
        expected_risks = {
            danger: {
                "bonus_pontos": int(cfg["bonus_risco"][danger]),
                "aumento_teto_valor": int(cfg["aumento_teto_valor_risco"][danger]),
            }
            for danger in sorted(recompensas.VALID_DANGER)
        }
        if router.get("riscos") != expected_risks:
            errors.append("envelope Task40 divergiu dos riscos do Reward Budget v2")
        expected_families = {
            family: {
                "modificador_pontos": int(meta["modificador_pontos"]),
                "teto_valor_base": meta["teto_valor_base"],
                "categorias": list(meta["categorias"]),
            }
            for family, meta in cfg["perfis_familia"].items()
        }
        if router.get("familias") != expected_families:
            errors.append("envelope Task40 divergiu dos perfis de família do Reward Budget v2")
        if _rendered_bytes(router) > 4096:
            errors.append("roteador de envelope Task40 excede 4 KiB")
        if MAX_INTENT_FRAGMENTS != 3 or MAX_PAYLOAD_BYTES != 8192:
            errors.append("constantes de orçamento Task40 divergiram do contrato inicial")
    except (
        EmergentSidequestOpportunityError,
        recompensas.RewardMapError,
    ) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "erros": errors,
        "max_payload_bytes": MAX_PAYLOAD_BYTES,
        "max_intencoes": MAX_INTENT_FRAGMENTS,
        "schedulers_novos": 0,
        "rng_novo": 0,
        "estados_persistentes_novos": 0,
        "scans_globais": 0,
    }


def _dump(payload: dict[str, Any]) -> str:
    return yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("recusar", help="descarta a hipótese sem ler o repositório")
    sub.add_parser("check", help="valida contrato frio e envelope derivado")
    p = sub.add_parser("planejar", help="abre a boundary após âncora causal explícita")
    p.add_argument("--origem-tipo", required=True, choices=sorted(VALID_ORIGIN_TYPES | FORBIDDEN_ORIGIN_TYPES))
    p.add_argument("--origem-id", required=True)
    p.add_argument("--ancora-tipo", required=True)
    p.add_argument("--ancora", required=True)
    p.add_argument("--npc")
    p.add_argument("--local")
    p.add_argument("--periculosidade", default="media", choices=sorted(recompensas.VALID_DANGER))
    p.add_argument("--tier", type=int)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "recusar":
            result = decline()
        elif args.cmd == "check":
            result = check(repo)
        else:
            result = plan(
                repo,
                signaled=True,
                origin_type=args.origem_tipo,
                origin_id=args.origem_id,
                anchor_type=args.ancora_tipo,
                anchor=args.ancora,
                npc_id=args.npc,
                local_id=args.local,
                danger=args.periculosidade,
                tier=args.tier,
            )
    except (
        EmergentSidequestOpportunityError,
        mundo.WorldEngineError,
    ) as exc:
        print(_dump({"ok": False, "erro": str(exc)}), end="")
        return 2
    print(_dump(result), end="")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
