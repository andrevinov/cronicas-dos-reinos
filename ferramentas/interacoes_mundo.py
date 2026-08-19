#!/usr/bin/env python3
"""Integração reativa entre locais, encontros, side quests e Mundo Vivo.

Esta camada NÃO roda por turno nem por amanhecer. O narrador a chama somente
quando existe um gatilho real da cena:

- Ren entra/explora um local -> mapa de recompensas;
- Ren inicia um encontro elegível com NPC -> gate raro de side quest;
- uma side quest precisa preparar efeitos persistentes -> deltas transacionais;
- um resultado já canônico precisa materializar rastro/recompensa;
- checkpoint/lifecycle precisa invalidar oportunidades de quest giver morto.

O turno comum continua com duas escritas. Esta camada nunca transforma
possibilidade em cânone por conta própria.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

import yaml

import ciclo_npcs
import mundo
import oportunidades
import rastros
import recompensas
import relogios

OPPORTUNITY_INDEX = oportunidades.INDEX
OPPORTUNITY_STATE = oportunidades.STATE
REWARD_INDEX = recompensas.INDEX
REWARD_ITEM_INDEX = recompensas.ITEM_INDEX
REWARD_PLANNED = recompensas.PLANNED
RELATIONS = oportunidades.RELATIONS
NPC_INDEX = ciclo_npcs.NPC_INDEX

VALID_LOCAL_ACTIONS = {"entrar", "explorar"}
VALID_EFFECTS = {"agente", "operacao", "pressao", "consequencia", "rastro", "recompensa"}
MAX_EFFECTS = 6
OPEN_MISSIONS = oportunidades.OPEN_STATES
TERMINAL_MISSIONS = oportunidades.TERMINAL_STATES


class IntegrationError(ValueError):
    pass


def configured(repo: Path) -> bool:
    return all(
        (repo / path).is_file()
        for path in (OPPORTUNITY_INDEX, OPPORTUNITY_STATE, REWARD_INDEX)
    )


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IntegrationError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise IntegrationError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IntegrationError(f"{label} deve ser texto não vazio")
    return value.strip()


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise IntegrationError(str(exc)) from exc


def _now(
    repo: Path,
    supplied: mundo.WorldInstant | None,
) -> tuple[mundo.WorldInstant, list[str]]:
    try:
        return oportunidades._now(repo, supplied)
    except (oportunidades.OpportunityError, mundo.WorldEngineError) as exc:
        raise IntegrationError(str(exc)) from exc


def _history(state: dict[str, Any], item: dict[str, Any]) -> None:
    oportunidades._history(state, item)


def _need_key(npc_id: str, need_id: str) -> str:
    return oportunidades._need_key(npc_id, need_id)


def _compact_sources(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def local_event(
    repo: Path,
    place: str,
    *,
    action: str,
    tier: int,
    danger: str,
) -> dict[str, Any]:
    """Garante/reutiliza o mapa apenas em entrada ou exploração real."""
    if action not in VALID_LOCAL_ACTIONS:
        raise IntegrationError("acao local deve ser entrar ou explorar")
    try:
        result = recompensas.ensure(repo, place, tier, danger)
    except recompensas.RewardMapError as exc:
        raise IntegrationError(str(exc)) from exc
    return {
        "ok": True,
        "gatilho": f"local:{action}",
        "local_id": result["mapa"]["local_id"],
        "mapa_criado": bool(result["criado"]),
        "mapa": result["mapa"],
        "regra": "mapa preparado não significa recompensa descoberta",
        "fontes_lidas": result["fontes_lidas"],
    }


def _encounter_block(
    state: dict[str, Any],
    index: dict[str, Any],
    npc_id: str,
) -> tuple[str | None, int, int]:
    active, opened = oportunidades._mission_counts(state)
    blocked = oportunidades._blocked_for_npc(state, npc_id)
    if blocked is None and state["pendencias_avaliacao"]:
        blocked = "ja_existe_pendencia_global_de_avaliacao"
    if blocked is None and active >= index["orcamento"]["max_ativas"]:
        blocked = "limite_de_sidequests_ativas"
    if blocked is None and opened >= index["orcamento"]["max_em_aberto"]:
        blocked = "limite_de_sidequests_em_aberto"
    if blocked is None and state.get("cooldown_ate") is not None:
        blocked = "cooldown_global_de_oferta"
    return blocked, active, opened


def encounter_event(
    repo: Path,
    npc_id: str,
    *,
    now: mundo.WorldInstant | None = None,
    encounter_id: str | None = None,
) -> dict[str, Any]:
    """Gate raro otimizado: só abre perfil quando a ficha diz oportunidade."""
    try:
        index = oportunidades.load_index(repo)
    except oportunidades.OpportunityError as exc:
        raise IntegrationError(str(exc)) from exc
    meta = index["perfis"].get(npc_id)
    if not isinstance(meta, dict) or meta.get("estado") != "ativo":
        return {
            "ok": True,
            "resultado": "interacao_normal",
            "motivo": "npc_sem_perfil_ativo",
            "npc_id": npc_id,
            "fontes_lidas": [OPPORTUNITY_INDEX.as_posix()],
        }

    try:
        state = oportunidades.load_state(repo, index)
        current, time_sources = _now(repo, now)
        changed = oportunidades.prune_expired(state, current)
        key = oportunidades._encounter_key(npc_id, current, encounter_id)
    except oportunidades.OpportunityError as exc:
        raise IntegrationError(str(exc)) from exc

    sources = [OPPORTUNITY_INDEX.as_posix(), OPPORTUNITY_STATE.as_posix(), *time_sources]
    if key in state["encontros_recentes"]:
        if changed:
            oportunidades.atomic(repo / OPPORTUNITY_STATE, state)
        return {
            "ok": True,
            "resultado": "interacao_normal",
            "motivo": "encontro_ja_processado",
            "npc_id": npc_id,
            "encontro_id": key,
            "fontes_lidas": _compact_sources(sources),
        }

    blocked, active, opened = _encounter_block(state, index, npc_id)
    if blocked is not None:
        if changed:
            oportunidades.atomic(repo / OPPORTUNITY_STATE, state)
        return {
            "ok": True,
            "resultado": "interacao_normal",
            "motivo": blocked,
            "npc_id": npc_id,
            "ativas": active,
            "em_aberto": opened,
            "cooldown_ate": state.get("cooldown_ate"),
            "fontes_lidas": _compact_sources(sources),
        }

    state["encontros_recentes"].append(key)
    state["encontros_recentes"] = state["encontros_recentes"][-oportunidades.MAX_HISTORY :]
    token, gate = oportunidades.draw_gate(state, index)

    if gate == "nada":
        oportunidades.atomic(repo / OPPORTUNITY_STATE, state)
        return {
            "ok": True,
            "resultado": "interacao_normal",
            "motivo": "gate_sem_oportunidade",
            "ficha": token,
            "npc_id": npc_id,
            "encontro_id": key,
            "fontes_lidas": _compact_sources(sources),
        }

    try:
        profile = oportunidades.load_profile(repo, npc_id, index)
        available = oportunidades._available_needs(state, profile, npc_id)
    except oportunidades.OpportunityError as exc:
        raise IntegrationError(str(exc)) from exc
    profile_path = index["perfis"][npc_id]["arquivo"]
    sources.append(profile_path)
    if not available:
        oportunidades.atomic(repo / OPPORTUNITY_STATE, state)
        return {
            "ok": True,
            "resultado": "interacao_normal",
            "motivo": "oportunidade_sem_necessidade_disponivel",
            "ficha": token,
            "npc_id": npc_id,
            "encontro_id": key,
            "fontes_lidas": _compact_sources(sources),
        }

    need = oportunidades.choose_need(index["_seed"], npc_id, available)
    raw_id = (
        f"{index['_seed']}|{npc_id}|{need['id']}|"
        f"{state['gate']['ciclo']}|{state['gate']['sorteios']}"
    )
    import hashlib

    pending_id = "sq-" + hashlib.sha256(raw_id.encode()).hexdigest()[:16]
    pending = {
        "id": pending_id,
        "estado": "potencial",
        "npc_id": npc_id,
        "npc_nome": index["perfis"][npc_id]["nome"],
        "necessidade_id": need["id"],
        "tipo": need["tipo"],
        "semente": need["semente"],
        "janela": oportunidades._window_at(need, current),
        "pode_reabrir": need["pode_reabrir"],
        "consequencia_sem_ren": need["consequencia_sem_ren"],
        "fonte_npc": profile["fonte_npc"],
        "gerada_em": mundo.instant_parts(current),
        "regra": "potencial_nao_significa_oferecida",
    }
    state["pendencias_avaliacao"][pending_id] = pending
    oportunidades.atomic(repo / OPPORTUNITY_STATE, state)
    return {
        "ok": True,
        "resultado": "avaliar_sidequest",
        "ficha": token,
        "npc_id": npc_id,
        "encontro_id": key,
        "pendencia": pending,
        "instrucao": (
            "Avaliar a semente contra o cânone atual. Só oferecer após decisão "
            "explícita; potencial não é fala nem missão."
        ),
        "fontes_lidas": _compact_sources(sources),
    }


def _canonical_dead_for_profiles(
    repo: Path,
    profile_ids: set[str],
) -> tuple[set[str], list[str]]:
    dead = set()
    sources: list[str] = []
    if ciclo_npcs.configured(repo):
        dead |= ciclo_npcs.dead_ids(repo)
        sources.append(ciclo_npcs.REGISTRY.as_posix())

    npc_index = ciclo_npcs._optional_map(repo, NPC_INDEX)
    if npc_index:
        sources.append(NPC_INDEX.as_posix())
        for npc_id in sorted(profile_ids):
            state, source = ciclo_npcs._canonical_life(repo, npc_id, npc_index)
            if state == "morto":
                dead.add(npc_id)
                if source:
                    sources.append(source)
    return dead, _compact_sources(sources)


def sync_lifecycle(
    repo: Path,
    *,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    """Inviabiliza oportunidades quando o quest giver morreu no cânone."""
    if not (repo / OPPORTUNITY_INDEX).is_file() or not (repo / OPPORTUNITY_STATE).is_file():
        return {"ok": True, "configurado": False, "alterou": False, "fontes_lidas": []}
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
        current, time_sources = _now(repo, now)
    except (oportunidades.OpportunityError, mundo.WorldEngineError) as exc:
        raise IntegrationError(str(exc)) from exc

    dead, dead_sources = _canonical_dead_for_profiles(repo, set(index["perfis"]))
    changed_index = False
    changed_state = oportunidades.prune_expired(state, current)
    invalidated: list[str] = []
    failed: list[str] = []

    for npc_id in sorted(dead & set(index["perfis"])):
        meta = index["perfis"][npc_id]
        if meta.get("estado") != "inativo":
            meta["estado"] = "inativo"
            changed_index = True

    for pid, item in list(state["pendencias_avaliacao"].items()):
        if item.get("npc_id") not in dead:
            continue
        key = _need_key(item["npc_id"], item["necessidade_id"])
        if key not in state["sementes_consumidas"]:
            state["sementes_consumidas"].append(key)
        del state["pendencias_avaliacao"][pid]
        invalidated.append(pid)
        _history(
            state,
            {
                "tipo": "avaliacao_descartada",
                "id": pid,
                "npc_id": item["npc_id"],
                "motivo": "quest_giver_morto",
                "em": mundo.instant_parts(current),
            },
        )
        changed_state = True

    for mission in state["missoes"].values():
        if mission.get("npc_id") not in dead or mission.get("estado") not in OPEN_MISSIONS:
            continue
        before = mission["estado"]
        target = "falhada" if before == "aceita" else "expirada"
        mission["estado"] = target
        mission["encerrada_em"] = mundo.instant_parts(current)
        mission["motivo_encerramento"] = "quest_giver_morto"
        failed.append(mission["id"])
        _history(
            state,
            {
                "tipo": "missao_encerrada",
                "id": mission["id"],
                "de": before,
                "para": target,
                "motivo": "quest_giver_morto",
                "em": mundo.instant_parts(current),
            },
        )
        changed_state = True

    if changed_index:
        oportunidades.atomic(repo / OPPORTUNITY_INDEX, index)
    if changed_state:
        oportunidades.atomic(repo / OPPORTUNITY_STATE, state)

    return {
        "ok": True,
        "configurado": True,
        "alterou": changed_index or changed_state,
        "quest_givers_mortos": sorted(dead & set(index["perfis"])),
        "avaliacoes_inviabilizadas": invalidated,
        "missoes_encerradas": failed,
        "fontes_lidas": _compact_sources(
            [OPPORTUNITY_INDEX.as_posix(), OPPORTUNITY_STATE.as_posix(), *time_sources, *dead_sources]
        ),
    }


def _mission(
    repo: Path,
    mission_id: str,
    *,
    states: set[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise IntegrationError(str(exc)) from exc
    mission = state["missoes"].get(mission_id)
    if not isinstance(mission, dict):
        raise IntegrationError(f"sidequest inexistente: {mission_id}")
    if states is not None and mission.get("estado") not in states:
        allowed = ", ".join(sorted(states))
        raise IntegrationError(
            f"sidequest {mission_id} precisa estar em {{{allowed}}}; atual={mission.get('estado')}"
        )
    return index, state, mission


def _normalize_quest_reward(spec: Any) -> dict[str, Any]:
    spec = copy.deepcopy(_map(spec, "recompensa"))
    origin = spec.get("origem")
    if origin not in (None, "quest"):
        raise IntegrationError("recompensa ligada à sidequest deve ter origem quest")
    spec["origem"] = "quest"
    try:
        return recompensas._validate_planned_spec(spec, "recompensa_sidequest")
    except recompensas.RewardMapError as exc:
        raise IntegrationError(str(exc)) from exc


def _find_planned_by_id(planned: dict[str, Any], rid: str) -> tuple[str, dict[str, Any]] | None:
    found: tuple[str, dict[str, Any]] | None = None
    for place, entries in planned["por_local"].items():
        for entry in entries:
            if entry.get("id") != rid:
                continue
            if found is not None:
                raise IntegrationError(f"recompensa planejada duplicada: {rid}")
            found = (place, entry)
    return found


def attach_quest_reward(
    repo: Path,
    mission_id: str,
    place: str,
    spec: Any,
) -> dict[str, Any]:
    """Anexa recompensa quest sem rerrolar o núcleo procedural do local."""
    _, _, mission = _mission(
        repo,
        mission_id,
        states={"aceita", "concluida", "falhada", "expirada"},
    )
    place = recompensas.local_id(place)
    spec = _normalize_quest_reward(spec)
    rid = spec["id"]

    try:
        reward_index = recompensas.load_index(repo)
        item_index = recompensas.load_item_index(repo)
        planned = recompensas.load_planned(repo)
    except recompensas.RewardMapError as exc:
        raise IntegrationError(str(exc)) from exc

    existing_planned = _find_planned_by_id(planned, rid)
    if existing_planned is not None:
        old_place, old_spec = existing_planned
        if old_place != place or old_spec != spec:
            raise IntegrationError(f"ID de recompensa {rid} já planejado com conteúdo divergente")
    else:
        planned["por_local"].setdefault(place, []).append(spec)
        recompensas.atomic(repo / REWARD_PLANNED, planned)

    meta = reward_index["mapas"].get(place)
    if meta is None:
        return {
            "ok": True,
            "resultado": "planejada_para_mapa_futuro",
            "sidequest": mission_id,
            "recompensa_id": rid,
            "local_id": place,
            "duplicada": existing_planned is not None,
            "fontes_lidas": [
                OPPORTUNITY_INDEX.as_posix(),
                OPPORTUNITY_STATE.as_posix(),
                REWARD_INDEX.as_posix(),
                REWARD_ITEM_INDEX.as_posix(),
                REWARD_PLANNED.as_posix(),
            ],
        }

    map_path = recompensas.repo_path(repo, meta["arquivo"], recompensas.MAPS_DIR)
    data = _map(_load(map_path), meta["arquivo"])
    entries = _list(data.get("recompensas"), f"{place}.recompensas")
    existing_entry = next((entry for entry in entries if entry.get("id") == rid), None)

    generated_entries, fragments = recompensas._planned_entries(
        {"por_local": {place: [spec]}},
        place,
    )
    wanted_entry = generated_entries[0]
    wanted_fragment = fragments[rid]

    if existing_entry is not None:
        if existing_entry != wanted_entry:
            raise IntegrationError(f"{rid}: mapa já contém recompensa divergente")
        item_meta = item_index["recompensas"].get(rid)
        expected_meta = {
            "local_id": place,
            "mapa": meta["arquivo"],
            "arquivo": wanted_entry["arquivo"],
        }
        if item_meta not in (None, expected_meta):
            raise IntegrationError(f"{rid}: índice dirigido diverge da recompensa existente")
        if item_meta is None:
            item_index["recompensas"][rid] = expected_meta
            recompensas.atomic(repo / REWARD_ITEM_INDEX, item_index)
        recompensas.install_once(repo / wanted_entry["arquivo"], wanted_fragment)
        if meta.get("quantidade") != len(entries):
            meta["quantidade"] = len(entries)
            reward_index["mapas"][place] = meta
            recompensas.atomic(repo / REWARD_INDEX, reward_index)
        return {
            "ok": True,
            "resultado": "ja_estava_no_mapa",
            "sidequest": mission_id,
            "recompensa_id": rid,
            "local_id": place,
            "duplicada": True,
            "fontes_lidas": [
                OPPORTUNITY_INDEX.as_posix(),
                OPPORTUNITY_STATE.as_posix(),
                REWARD_INDEX.as_posix(),
                REWARD_ITEM_INDEX.as_posix(),
                REWARD_PLANNED.as_posix(),
                meta["arquivo"],
            ],
        }

    if len(entries) >= reward_index["orcamento"]["max_totais_por_mapa"]:
        raise IntegrationError(
            f"{place}: mapa já atingiu max_totais_por_mapa="
            f"{reward_index['orcamento']['max_totais_por_mapa']}"
        )
    if rid in item_index["recompensas"]:
        raise IntegrationError(f"ID global de recompensa já pertence a outro mapa: {rid}")

    recompensas.install_once(repo / wanted_entry["arquivo"], wanted_fragment)
    item_index["recompensas"][rid] = {
        "local_id": place,
        "mapa": meta["arquivo"],
        "arquivo": wanted_entry["arquivo"],
    }
    recompensas.atomic(repo / REWARD_ITEM_INDEX, item_index)

    entries.append(wanted_entry)
    generation = data.get("geracao")
    if isinstance(generation, dict):
        generation["planejadas"] = int(generation.get("planejadas") or 0) + 1
    recompensas.atomic(map_path, data)

    meta["quantidade"] = len(entries)
    reward_index["mapas"][place] = meta
    recompensas.atomic(repo / REWARD_INDEX, reward_index)
    return {
        "ok": True,
        "resultado": "adicionada_ao_mapa_existente",
        "sidequest": mission_id,
        "recompensa_id": rid,
        "local_id": place,
        "duplicada": False,
        "chave_procedural_preservada": data.get("geracao", {}).get("chave"),
        "fontes_lidas": [
            OPPORTUNITY_INDEX.as_posix(),
            OPPORTUNITY_STATE.as_posix(),
            REWARD_INDEX.as_posix(),
            REWARD_ITEM_INDEX.as_posix(),
            REWARD_PLANNED.as_posix(),
            meta["arquivo"],
        ],
    }


def _agent_indexes(repo: Path) -> tuple[set[str], list[str]]:
    sources: list[str] = []
    known: set[str] = set()
    strategic_path = Path("narrador/agentes/index.yaml")
    light_path = Path("narrador/agentes-leves/index.yaml")
    for path, key in ((strategic_path, "agentes"), (light_path, "agentes")):
        if not (repo / path).is_file():
            continue
        doc = _map(_load(repo / path), path.as_posix())
        known |= set(_map(doc.get(key), key))
        sources.append(path.as_posix())
    return known, sources


def prepare_sidequest_effects(
    repo: Path,
    mission_id: str,
    effects: Any,
) -> dict[str, Any]:
    """Prepara efeitos; só pressão/consequência viram deltas do turno."""
    _, _, mission = _mission(repo, mission_id, states={"aceita"})
    effects = _list(effects, "efeitos")
    if len(effects) > MAX_EFFECTS:
        raise IntegrationError(f"uma decisão de sidequest aceita no máximo {MAX_EFFECTS} efeitos")

    router = None
    known_agents: set[str] | None = None
    deltas: list[dict[str, Any]] = []
    post: list[dict[str, Any]] = []
    links: list[dict[str, Any]] = []
    sources = [OPPORTUNITY_INDEX.as_posix(), OPPORTUNITY_STATE.as_posix()]

    for pos, raw in enumerate(effects):
        effect = _map(raw, f"efeitos[{pos}]")
        kind = _text(effect.get("tipo"), f"efeitos[{pos}].tipo")
        if kind not in VALID_EFFECTS:
            raise IntegrationError(f"tipo de efeito desconhecido: {kind}")

        if kind == "agente":
            agent_id = _text(effect.get("agente"), "efeito.agente")
            if known_agents is None:
                known_agents, agent_sources = _agent_indexes(repo)
                sources.extend(agent_sources)
            if agent_id not in known_agents:
                links.append(
                    {
                        "tipo": "agente_novo",
                        "id": agent_id,
                        "acao": "classificar_pela_taxonomia_npc_v2_antes_de_criar_agencia",
                    }
                )
            else:
                links.append({"tipo": "agente_existente", "id": agent_id})
            continue

        if kind in {"operacao", "pressao"}:
            if router is None:
                try:
                    router = relogios.load_router(repo)
                except relogios.ClockError as exc:
                    raise IntegrationError(str(exc)) from exc
                sources.append(relogios.ROUTER_PATH.as_posix())

        if kind == "operacao":
            operation = _text(effect.get("operacao"), "efeito.operacao")
            meta = router["operacoes"].get(operation)
            if not isinstance(meta, dict):
                raise IntegrationError(f"operação inexistente no roteador: {operation}")
            links.append(
                {
                    "tipo": "operacao",
                    "id": operation,
                    "agente_principal": meta["agente_principal"],
                    "situacao_relogios": meta["situacao_relogios"],
                }
            )
            continue

        if kind == "pressao":
            clock_id = _text(effect.get("relogio"), "efeito.relogio")
            clock = router["relogios"].get(clock_id)
            if not isinstance(clock, dict):
                raise IntegrationError(f"pressão/relogio inexistente: {clock_id}")
            if clock.get("estado") != "ativo" or clock.get("tipo") != "pressao":
                raise IntegrationError(f"{clock_id}: somente pressão ativa pode avançar")
            deltas.append(
                {
                    "alvo": f"relogio:{clock_id}",
                    "op": "inc",
                    "caminho": "relogio.progresso",
                    "valor": 1,
                    "visibilidade": "narrador",
                }
            )
            links.append(
                {
                    "tipo": "pressao",
                    "id": clock_id,
                    "operacao": clock.get("operacao"),
                    "agente_principal": clock.get("agente_principal"),
                }
            )
            continue

        if kind == "consequencia":
            value = copy.deepcopy(_map(effect.get("valor"), "efeito.consequencia.valor"))
            value.setdefault("origem_sidequest", mission_id)
            deltas.append({"alvo": "consequencia", "op": "registrar", "valor": value})
            continue

        if kind == "rastro":
            spec = copy.deepcopy(_map(effect.get("especificacao"), "efeito.rastro.especificacao"))
            post.append({"tipo": "rastro", "especificacao": spec})
            continue

        if kind == "recompensa":
            place = recompensas.local_id(effect.get("local_id"))
            spec = _normalize_quest_reward(effect.get("especificacao"))
            post.append(
                {
                    "tipo": "recompensa",
                    "local_id": place,
                    "especificacao": spec,
                }
            )
            continue

    return {
        "ok": True,
        "sidequest": mission_id,
        "npc_id": mission["npc_id"],
        "deltas_transacionais": deltas,
        "vinculos": links,
        "pos_canonico": post,
        "regra": (
            "Inclua deltas_transacionais no mesmo turno que narra o efeito. "
            "Execute pos_canonico somente depois que a origem do fato estiver canônica."
        ),
        "fontes_lidas": _compact_sources(sources),
    }


def apply_post_sidequest(
    repo: Path,
    mission_id: str,
    effects: Any,
) -> dict[str, Any]:
    """Materializa apenas efeitos cujo fato-base já virou cânone."""
    _, _, mission = _mission(repo, mission_id, states=TERMINAL_MISSIONS)
    effects = _list(effects, "efeitos_pos_canonico")
    if len(effects) > MAX_EFFECTS:
        raise IntegrationError(f"pós-sidequest aceita no máximo {MAX_EFFECTS} efeitos")

    results: list[dict[str, Any]] = []
    for raw in effects:
        effect = _map(raw, "efeito_pos_canonico")
        kind = _text(effect.get("tipo"), "efeito_pos_canonico.tipo")
        if kind == "rastro":
            try:
                result = rastros.register(repo, effect.get("especificacao"))
            except (rastros.TraceError, mundo.WorldEngineError) as exc:
                raise IntegrationError(str(exc)) from exc
            results.append({"tipo": "rastro", **result})
        elif kind == "recompensa":
            result = attach_quest_reward(
                repo,
                mission_id,
                effect.get("local_id"),
                effect.get("especificacao"),
            )
            results.append({"tipo": "recompensa", **result})
        else:
            raise IntegrationError(
                "pós-canônico aceita somente rastro ou recompensa; "
                "pressões/consequências pertencem ao turno transacional"
            )
    return {
        "ok": True,
        "sidequest": mission_id,
        "estado": mission["estado"],
        "resultados": results,
    }


def status(repo: Path) -> dict[str, Any]:
    result = {
        "ok": True,
        "recompensas": recompensas.status(repo),
        "oportunidades": oportunidades.status(repo),
    }
    return result


def check_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    rewards = recompensas.validate_repo(repo)
    opportunities = oportunidades.validate_repo(repo)
    errors.extend(f"recompensas: {item}" for item in rewards.get("erros") or [])
    errors.extend(f"oportunidades: {item}" for item in opportunities.get("erros") or [])

    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
        dead, _ = _canonical_dead_for_profiles(repo, set(index["perfis"]))
        for npc_id in sorted(dead & set(index["perfis"])):
            if index["perfis"][npc_id].get("estado") != "inativo":
                errors.append(f"lifecycle: quest giver morto ainda ativo: {npc_id}")
        for item in state["pendencias_avaliacao"].values():
            if item.get("npc_id") in dead:
                errors.append(f"lifecycle: avaliação de quest giver morto: {item['id']}")
        for item in state["missoes"].values():
            if item.get("npc_id") in dead and item.get("estado") in OPEN_MISSIONS:
                errors.append(f"lifecycle: sidequest aberta de quest giver morto: {item['id']}")
    except (IntegrationError, oportunidades.OpportunityError) as exc:
        errors.append(str(exc))

    return {
        "ok": not errors,
        "erros": list(dict.fromkeys(errors)),
        "recompensas": {
            "mapas": rewards.get("mapas", 0),
            "itens": rewards.get("recompensas", 0),
        },
        "oportunidades": {"perfis": opportunities.get("perfis", 0)},
    }


def _instant_arg(data: str | None, hour: str | None) -> mundo.WorldInstant | None:
    if data is None and hour is None:
        return None
    if not data or not hour:
        raise IntegrationError("--data e --hora devem ser usados juntos")
    try:
        return mundo.parse_instant(data, hour)
    except mundo.WorldEngineError as exc:
        raise IntegrationError(str(exc)) from exc


def _stdin() -> Any:
    raw = sys.stdin.read()
    if not raw.strip():
        raise IntegrationError("comando exige YAML/JSON em stdin")
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise IntegrationError(f"stdin inválido: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_local = sub.add_parser("local")
    p_local.add_argument("local_id")
    p_local.add_argument("--acao", choices=sorted(VALID_LOCAL_ACTIONS), required=True)
    p_local.add_argument("--tier", type=int, required=True)
    p_local.add_argument("--periculosidade", choices=sorted(recompensas.VALID_DANGER), required=True)

    p_enc = sub.add_parser("encontro")
    p_enc.add_argument("npc_id")
    p_enc.add_argument("--encontro-id", required=True)
    p_enc.add_argument("--data")
    p_enc.add_argument("--hora")

    p_life = sub.add_parser("lifecycle")
    p_life.add_argument("--data")
    p_life.add_argument("--hora")

    p_prep = sub.add_parser("preparar-sidequest")
    p_prep.add_argument("id")

    p_post = sub.add_parser("pos-sidequest")
    p_post.add_argument("id")

    p_reward = sub.add_parser("recompensa-sidequest")
    p_reward.add_argument("id")
    p_reward.add_argument("local_id")

    sub.add_parser("status")
    sub.add_parser("check")

    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        if args.cmd == "local":
            result = local_event(
                repo,
                args.local_id,
                action=args.acao,
                tier=args.tier,
                danger=args.periculosidade,
            )
        elif args.cmd == "encontro":
            result = encounter_event(
                repo,
                args.npc_id,
                encounter_id=args.encontro_id,
                now=_instant_arg(args.data, args.hora),
            )
        elif args.cmd == "lifecycle":
            result = sync_lifecycle(
                repo,
                now=_instant_arg(args.data, args.hora),
            )
        elif args.cmd == "preparar-sidequest":
            result = prepare_sidequest_effects(repo, args.id, _stdin())
        elif args.cmd == "pos-sidequest":
            result = apply_post_sidequest(repo, args.id, _stdin())
        elif args.cmd == "recompensa-sidequest":
            result = attach_quest_reward(repo, args.id, args.local_id, _stdin())
        elif args.cmd == "status":
            result = status(repo)
        else:
            result = check_repo(repo)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0 if result.get("ok") else 1
    except (
        IntegrationError,
        oportunidades.OpportunityError,
        recompensas.RewardMapError,
        relogios.ClockError,
        rastros.TraceError,
        mundo.WorldEngineError,
    ) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
