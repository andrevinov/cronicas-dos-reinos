#!/usr/bin/env python3
"""Oportunidades raras e determinísticas de side quests por encontro com NPCs.

A camada é reativa: só roda quando Ren encontra/interage com um NPC elegível.
Um baralho global sem reposição decide "interação normal" vs. "oportunidade".
Oportunidade NÃO significa que a missão foi oferecida: cria apenas uma pendência
de avaliação com uma semente compatível com aquele NPC. Só depois o narrador pode
confirmar a oferta.

Não há scheduler, scan de NPCs ou ação automática de consequência.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

import mundo

INDEX = Path("narrador/oportunidades/index.yaml")
STATE = Path("narrador/oportunidades/estado.yaml")
PROFILES_DIR = Path("narrador/oportunidades/perfis")
RELATIONS = Path("estado/relacoes/index.yaml")

VALID_GATE_RESULTS = {"nada", "oportunidade"}
VALID_TYPES = {
    "busca",
    "protecao",
    "investigacao",
    "resgate",
    "entrega",
    "aquisicao",
    "exploracao",
    "mediacao",
    "favor",
    "problema_cotidiano",
    "segredo_pessoal",
    "trabalho_profissional",
}
VALID_WINDOWS = {"a_qualquer_momento", "temporal", "enquanto_condicao"}
MISSION_STATES = {
    "oferecida",
    "aceita",
    "adiada",
    "recusada",
    "expirada",
    "concluida",
    "falhada",
}
OPEN_STATES = {"oferecida", "aceita", "adiada"}
ACTIVE_STATES = {"aceita"}
TERMINAL_STATES = {"recusada", "expirada", "concluida", "falhada"}
MAX_HISTORY = 64


class OpportunityError(ValueError):
    pass


def load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise OpportunityError(str(exc)) from exc


def amap(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise OpportunityError(f"{label} deve ser mapa")
    return value


def alist(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise OpportunityError(f"{label} deve ser lista")
    return value


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OpportunityError(f"{label} deve ser texto não vazio")
    return value.strip()


def integer(value: Any, label: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise OpportunityError(f"{label} deve ser inteiro >= {minimum}")
    return value


def repo_path(repo: Path, raw: str, prefix: Path | None = None) -> Path:
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        raise OpportunityError(f"caminho fora do repo: {raw}")
    if prefix is not None:
        try:
            rel.relative_to(prefix)
        except ValueError as exc:
            raise OpportunityError(f"caminho {raw} deve ficar sob {prefix}") from exc
    return repo / rel


def atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
        handle.flush()
        os.fsync(handle.fileno())
        tmp = Path(handle.name)
    os.replace(tmp, path)


def load_index(repo: Path) -> dict[str, Any]:
    data = amap(load(repo / INDEX), str(INDEX))
    if data.get("schema_oportunidades") != 1 or data.get("natureza") != "reservado":
        raise OpportunityError("índice de oportunidades inválido")
    seed = text(data.get("semente"), "semente")

    gate = amap(data.get("gate"), "gate")
    if gate.get("modo") != "baralho_sem_reposicao_sha256":
        raise OpportunityError("gate deve usar baralho_sem_reposicao_sha256")
    tokens = alist(gate.get("fichas"), "gate.fichas")
    seen: set[str] = set()
    results: list[str] = []
    for i, raw in enumerate(tokens):
        item = amap(raw, f"gate.fichas[{i}]")
        token_id = text(item.get("id"), f"gate.fichas[{i}].id")
        result = text(item.get("resultado"), f"gate.fichas[{i}].resultado")
        if token_id in seen or result not in VALID_GATE_RESULTS:
            raise OpportunityError("ficha de gate inválida/duplicada")
        seen.add(token_id)
        results.append(result)
    if results.count("nada") != 8 or results.count("oportunidade") != 2:
        raise OpportunityError("gate v1 deve conter exatamente 8 nada + 2 oportunidade")

    budget = amap(data.get("orcamento"), "orcamento")
    max_active = integer(budget.get("max_ativas"), "orcamento.max_ativas", 1)
    max_open = integer(budget.get("max_em_aberto"), "orcamento.max_em_aberto", max_active)
    max_pending = integer(
        budget.get("max_pendencias_avaliacao"),
        "orcamento.max_pendencias_avaliacao",
        1,
    )
    if max_open < max_active:
        raise OpportunityError("max_em_aberto não pode ser menor que max_ativas")
    if max_pending != 1:
        raise OpportunityError("v1 exige no máximo 1 pendência de avaliação global")
    cooldown = alist(budget.get("cooldown_oferta_dias"), "orcamento.cooldown_oferta_dias")
    if not cooldown or any(not isinstance(day, int) or day < 1 for day in cooldown):
        raise OpportunityError("cooldown_oferta_dias inválido")

    rules = amap(data.get("regras"), "regras")
    required = {
        "acionamento": "encontro_com_npc",
        "scheduler": "proibido",
        "scan_geral_npcs": "proibido",
        "necessidade_nao_e_oferta": True,
        "oferta_nao_e_aceite": True,
        "consequencia_sem_ren_nao_e_automatica": True,
    }
    for key, expected in required.items():
        if rules.get(key) != expected:
            raise OpportunityError(f"regra obrigatória divergente: {key}")

    profiles = amap(data.get("perfis"), "perfis")
    for npc_id, meta in profiles.items():
        text(npc_id, "npc_id")
        meta = amap(meta, f"perfis.{npc_id}")
        text(meta.get("nome"), f"perfis.{npc_id}.nome")
        if meta.get("estado") not in {"ativo", "inativo"}:
            raise OpportunityError(f"{npc_id}: estado de perfil inválido")
        raw = text(meta.get("arquivo"), f"perfis.{npc_id}.arquivo")
        repo_path(repo, raw, PROFILES_DIR)
    data["_seed"] = seed
    return data


def _parse_parts(value: Any, label: str) -> mundo.WorldInstant:
    value = amap(value, label)
    return mundo.parse_instant(
        text(value.get("data"), label + ".data"),
        text(value.get("hora"), label + ".hora"),
    )


def load_state(repo: Path, index: dict[str, Any] | None = None) -> dict[str, Any]:
    index = index or load_index(repo)
    data = amap(load(repo / STATE), str(STATE))
    if (
        data.get("schema_estado_oportunidades") != 1
        or data.get("natureza") != "controle_reservado"
    ):
        raise OpportunityError("estado de oportunidades inválido")
    gate = amap(data.get("gate"), "gate")
    cycle = integer(gate.get("ciclo"), "gate.ciclo", 0)
    remaining = alist(gate.get("restantes"), "gate.restantes")
    draws = integer(gate.get("sorteios"), "gate.sorteios", 0)
    valid_tokens = {item["id"] for item in index["gate"]["fichas"]}
    if len(remaining) != len(set(remaining)) or set(remaining) - valid_tokens:
        raise OpportunityError("gate.restantes inválido")
    if cycle == 0 and remaining:
        raise OpportunityError("ciclo 0 exige baralho ainda vazio")
    if draws < 0:
        raise OpportunityError("gate.sorteios inválido")

    cooldown = data.get("cooldown_ate")
    if cooldown is not None:
        _parse_parts(cooldown, "cooldown_ate")

    pending = amap(data.get("pendencias_avaliacao"), "pendencias_avaliacao")
    missions = amap(data.get("missoes"), "missoes")
    consumed = alist(data.get("sementes_consumidas"), "sementes_consumidas")
    if len(consumed) != len(set(consumed)):
        raise OpportunityError("sementes_consumidas contém duplicatas")
    history = alist(data.get("historico_recente"), "historico_recente")
    if len(history) > MAX_HISTORY:
        raise OpportunityError("histórico recente grande demais")
    for pid, item in pending.items():
        item = amap(item, f"pendencias_avaliacao.{pid}")
        if item.get("id") != pid or item.get("estado") != "potencial":
            raise OpportunityError(f"pendência inválida: {pid}")
    for mid, item in missions.items():
        item = amap(item, f"missoes.{mid}")
        if item.get("id") != mid or item.get("estado") not in MISSION_STATES:
            raise OpportunityError(f"missão inválida: {mid}")
    return data


def load_profile(repo: Path, npc_id: str, index: dict[str, Any] | None = None) -> dict[str, Any]:
    index = index or load_index(repo)
    meta = index["perfis"].get(npc_id)
    if not isinstance(meta, dict):
        raise OpportunityError(f"NPC sem perfil de oportunidade: {npc_id}")
    raw = text(meta.get("arquivo"), f"perfis.{npc_id}.arquivo")
    data = amap(load(repo_path(repo, raw, PROFILES_DIR)), raw)
    if (
        data.get("schema_perfil_oportunidades") != 1
        or data.get("natureza") != "reservado"
        or data.get("estatuto") != "sementes_nao_canonicas_ate_resolucao"
        or data.get("npc_id") != npc_id
    ):
        raise OpportunityError(f"{npc_id}: perfil inválido")
    source = text(data.get("fonte_npc"), f"{npc_id}.fonte_npc")
    repo_path(repo, source)
    needs = alist(data.get("necessidades"), f"{npc_id}.necessidades")
    seen: set[str] = set()
    for i, raw_need in enumerate(needs):
        need = amap(raw_need, f"{npc_id}.necessidades[{i}]")
        need_id = text(need.get("id"), f"{npc_id}.necessidades[{i}].id")
        if need_id in seen:
            raise OpportunityError(f"{npc_id}: necessidade duplicada: {need_id}")
        seen.add(need_id)
        kind = text(need.get("tipo"), f"{npc_id}.{need_id}.tipo")
        if kind not in VALID_TYPES:
            raise OpportunityError(f"{npc_id}.{need_id}: tipo inválido")
        text(need.get("semente"), f"{npc_id}.{need_id}.semente")
        window = amap(need.get("janela"), f"{npc_id}.{need_id}.janela")
        wtype = text(window.get("tipo"), f"{npc_id}.{need_id}.janela.tipo")
        if wtype not in VALID_WINDOWS:
            raise OpportunityError(f"{npc_id}.{need_id}: janela inválida")
        if wtype == "temporal":
            integer(window.get("duracao_horas"), f"{npc_id}.{need_id}.duracao_horas", 1)
        elif wtype == "enquanto_condicao":
            text(window.get("condicao"), f"{npc_id}.{need_id}.condicao")
        if not isinstance(need.get("pode_reabrir"), bool):
            raise OpportunityError(f"{npc_id}.{need_id}.pode_reabrir deve ser booleano")
        text(
            need.get("consequencia_sem_ren"),
            f"{npc_id}.{need_id}.consequencia_sem_ren",
        )
    return data


def gate_order(seed: str, cycle: int, ids: list[str]) -> list[str]:
    return sorted(
        ids,
        key=lambda token: hashlib.sha256(
            f"{seed}|sidequest-gate|{cycle}|{token}".encode()
        ).hexdigest(),
    )


def draw_gate(state: dict[str, Any], index: dict[str, Any]) -> tuple[str, str]:
    gate = state["gate"]
    tokens = {item["id"]: item["resultado"] for item in index["gate"]["fichas"]}
    if not gate["restantes"]:
        gate["ciclo"] += 1
        gate["restantes"] = gate_order(
            index["_seed"], gate["ciclo"], list(tokens)
        )
    token = gate["restantes"].pop(0)
    gate["sorteios"] += 1
    return token, tokens[token]


def _cooldown_days(index: dict[str, Any], mission_id: str) -> int:
    values = index["orcamento"]["cooldown_oferta_dias"]
    digest = hashlib.sha256(
        f"{index['_seed']}|cooldown|{mission_id}".encode()
    ).hexdigest()
    return values[int(digest[:8], 16) % len(values)]


def _mission_counts(state: dict[str, Any]) -> tuple[int, int]:
    values = [item["estado"] for item in state["missoes"].values()]
    active = sum(value in ACTIVE_STATES for value in values)
    opened = sum(value in OPEN_STATES for value in values)
    return active, opened


def _need_key(npc_id: str, need_id: str) -> str:
    return f"{npc_id}:{need_id}"


def _available_needs(
    state: dict[str, Any],
    profile: dict[str, Any],
    npc_id: str,
) -> list[dict[str, Any]]:
    consumed = set(state["sementes_consumidas"])
    pending_keys = {
        _need_key(item["npc_id"], item["necessidade_id"])
        for item in state["pendencias_avaliacao"].values()
    }
    mission_keys = {
        _need_key(item["npc_id"], item["necessidade_id"])
        for item in state["missoes"].values()
    }
    blocked = consumed | pending_keys | mission_keys
    return [
        item
        for item in profile["necessidades"]
        if _need_key(npc_id, item["id"]) not in blocked
    ]


def choose_need(seed: str, npc_id: str, needs: list[dict[str, Any]]) -> dict[str, Any]:
    if not needs:
        raise OpportunityError("nenhuma necessidade disponível")
    return min(
        needs,
        key=lambda item: hashlib.sha256(
            f"{seed}|necessidade|{npc_id}|{item['id']}".encode()
        ).hexdigest(),
    )


def _window_at(need: dict[str, Any], now: mundo.WorldInstant) -> dict[str, Any]:
    raw = need["janela"]
    wtype = raw["tipo"]
    if wtype == "a_qualquer_momento":
        return {"tipo": wtype}
    if wtype == "enquanto_condicao":
        return {"tipo": wtype, "condicao": raw["condicao"]}
    expires = mundo.WorldInstant(now.minute + int(raw["duracao_horas"]) * 60)
    return {
        "tipo": "temporal",
        "expira_em": mundo.instant_parts(expires),
    }


def _now(repo: Path, supplied: mundo.WorldInstant | None) -> tuple[mundo.WorldInstant, list[str]]:
    if supplied is not None:
        return supplied, []
    now, _ = mundo.load_canonical_time(repo)
    return now, [mundo.TIME_PATH.as_posix()]


def _window_expired(window: Any, now: mundo.WorldInstant) -> bool:
    if not isinstance(window, dict) or window.get("tipo") != "temporal":
        return False
    raw = window.get("expira_em")
    if not isinstance(raw, dict):
        return False
    return _parse_parts(raw, "janela.expira_em") <= now


def _history(state: dict[str, Any], item: dict[str, Any]) -> None:
    state["historico_recente"].append(item)
    state["historico_recente"] = state["historico_recente"][-MAX_HISTORY:]


def prune_expired(state: dict[str, Any], now: mundo.WorldInstant) -> bool:
    changed = False
    for pid, item in list(state["pendencias_avaliacao"].items()):
        if _window_expired(item.get("janela"), now):
            state["sementes_consumidas"].append(
                _need_key(item["npc_id"], item["necessidade_id"])
            )
            _history(
                state,
                {
                    "tipo": "avaliacao_descartada",
                    "id": pid,
                    "npc_id": item["npc_id"],
                    "motivo": "janela_temporal_encerrada",
                    "em": mundo.instant_parts(now),
                },
            )
            del state["pendencias_avaliacao"][pid]
            changed = True

    for item in state["missoes"].values():
        if item["estado"] not in {"oferecida", "adiada", "aceita"}:
            continue
        if not _window_expired(item.get("janela"), now):
            continue
        before = item["estado"]
        item["estado"] = "falhada" if before == "aceita" else "expirada"
        item["encerrada_em"] = mundo.instant_parts(now)
        item["motivo_encerramento"] = "janela_temporal_encerrada"
        _history(
            state,
            {
                "tipo": "missao_encerrada",
                "id": item["id"],
                "de": before,
                "para": item["estado"],
                "em": mundo.instant_parts(now),
            },
        )
        changed = True

    cooldown = state.get("cooldown_ate")
    if cooldown is not None and _parse_parts(cooldown, "cooldown_ate") <= now:
        state["cooldown_ate"] = None
        changed = True
    return changed


def _blocked_for_npc(state: dict[str, Any], npc_id: str) -> str | None:
    for item in state["pendencias_avaliacao"].values():
        if item["npc_id"] == npc_id:
            return "npc_ja_tem_avaliacao_pendente"
    for item in state["missoes"].values():
        if item["npc_id"] == npc_id and item["estado"] in OPEN_STATES:
            return "npc_ja_tem_sidequest_em_aberto"
    return None


def encounter(
    repo: Path,
    npc_id: str,
    *,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    index = load_index(repo)
    sources = [INDEX.as_posix(), STATE.as_posix()]
    meta = index["perfis"].get(npc_id)
    if not isinstance(meta, dict) or meta.get("estado") != "ativo":
        return {
            "ok": True,
            "resultado": "interacao_normal",
            "motivo": "npc_sem_perfil_ativo",
            "npc_id": npc_id,
            "fontes_lidas": [INDEX.as_posix()],
        }

    state = load_state(repo, index)
    current, time_sources = _now(repo, now)
    sources.extend(time_sources)
    changed = prune_expired(state, current)

    budget = index["orcamento"]
    active, opened = _mission_counts(state)
    blocked = _blocked_for_npc(state, npc_id)
    if blocked is None and state["pendencias_avaliacao"]:
        blocked = "ja_existe_pendencia_global_de_avaliacao"
    if blocked is None and active >= budget["max_ativas"]:
        blocked = "limite_de_sidequests_ativas"
    if blocked is None and opened >= budget["max_em_aberto"]:
        blocked = "limite_de_sidequests_em_aberto"
    if blocked is None and state.get("cooldown_ate") is not None:
        blocked = "cooldown_global_de_oferta"

    if blocked is not None:
        if changed:
            atomic(repo / STATE, state)
        return {
            "ok": True,
            "resultado": "interacao_normal",
            "motivo": blocked,
            "npc_id": npc_id,
            "ativas": active,
            "em_aberto": opened,
            "cooldown_ate": state.get("cooldown_ate"),
            "fontes_lidas": list(dict.fromkeys(sources)),
        }

    profile = load_profile(repo, npc_id, index)
    sources.append(index["perfis"][npc_id]["arquivo"])
    available = _available_needs(state, profile, npc_id)
    if not available:
        if changed:
            atomic(repo / STATE, state)
        return {
            "ok": True,
            "resultado": "interacao_normal",
            "motivo": "npc_sem_necessidade_disponivel",
            "npc_id": npc_id,
            "fontes_lidas": list(dict.fromkeys(sources)),
        }

    token, result = draw_gate(state, index)
    if result == "nada":
        atomic(repo / STATE, state)
        return {
            "ok": True,
            "resultado": "interacao_normal",
            "motivo": "gate_sem_oportunidade",
            "ficha": token,
            "npc_id": npc_id,
            "fontes_lidas": list(dict.fromkeys(sources)),
        }

    need = choose_need(index["_seed"], npc_id, available)
    raw_id = (
        f"{index['_seed']}|{npc_id}|{need['id']}|"
        f"{state['gate']['ciclo']}|{state['gate']['sorteios']}"
    )
    pending_id = "sq-" + hashlib.sha256(raw_id.encode()).hexdigest()[:16]
    pending = {
        "id": pending_id,
        "estado": "potencial",
        "npc_id": npc_id,
        "npc_nome": index["perfis"][npc_id]["nome"],
        "necessidade_id": need["id"],
        "tipo": need["tipo"],
        "semente": need["semente"],
        "janela": _window_at(need, current),
        "pode_reabrir": need["pode_reabrir"],
        "consequencia_sem_ren": need["consequencia_sem_ren"],
        "fonte_npc": profile["fonte_npc"],
        "gerada_em": mundo.instant_parts(current),
        "regra": "potencial_nao_significa_oferecida",
    }
    state["pendencias_avaliacao"][pending_id] = pending
    atomic(repo / STATE, state)
    return {
        "ok": True,
        "resultado": "avaliar_sidequest",
        "ficha": token,
        "npc_id": npc_id,
        "pendencia": pending,
        "instrucao": (
            "Avaliar se a semente faz sentido com o estado canônico atual do NPC. "
            "Se necessário, abrir somente fonte_npc. Oferecer ou descartar explicitamente."
        ),
        "fontes_lidas": list(dict.fromkeys(sources)),
    }


def evaluate(
    repo: Path,
    pending_id: str,
    decision: str,
    *,
    reason: str,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    if decision not in {"oferecer", "descartar"}:
        raise OpportunityError("decisão deve ser oferecer ou descartar")
    reason = text(reason, "motivo")
    index = load_index(repo)
    state = load_state(repo, index)
    current, time_sources = _now(repo, now)
    pruned = prune_expired(state, current)
    pending = state["pendencias_avaliacao"].get(pending_id)
    if not isinstance(pending, dict):
        if pruned:
            atomic(repo / STATE, state)
        raise OpportunityError(f"pendência inexistente: {pending_id}")

    key = _need_key(pending["npc_id"], pending["necessidade_id"])
    if decision == "descartar":
        if key not in state["sementes_consumidas"]:
            state["sementes_consumidas"].append(key)
        del state["pendencias_avaliacao"][pending_id]
        _history(
            state,
            {
                "tipo": "avaliacao_descartada",
                "id": pending_id,
                "npc_id": pending["npc_id"],
                "motivo": reason,
                "em": mundo.instant_parts(current),
            },
        )
        atomic(repo / STATE, state)
        return {
            "ok": True,
            "resultado": "descartada_sem_oferta",
            "id": pending_id,
            "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), *time_sources],
        }

    active, opened = _mission_counts(state)
    budget = index["orcamento"]
    if active >= budget["max_ativas"] or opened >= budget["max_em_aberto"]:
        raise OpportunityError("orçamento de sidequests não permite nova oferta")
    if state.get("cooldown_ate") is not None:
        raise OpportunityError("cooldown global impede nova oferta")

    mission = dict(pending)
    mission["estado"] = "oferecida"
    mission["oferecida_em"] = mundo.instant_parts(current)
    mission["motivo_da_oferta"] = reason
    mission.pop("regra", None)
    mission.pop("gerada_em", None)
    state["missoes"][pending_id] = mission
    del state["pendencias_avaliacao"][pending_id]
    if key not in state["sementes_consumidas"]:
        state["sementes_consumidas"].append(key)
    cooldown_days = _cooldown_days(index, pending_id)
    state["cooldown_ate"] = mundo.instant_parts(
        mundo.WorldInstant(current.minute + cooldown_days * 1440)
    )
    _history(
        state,
        {
            "tipo": "missao_oferecida",
            "id": pending_id,
            "npc_id": mission["npc_id"],
            "cooldown_dias": cooldown_days,
            "em": mundo.instant_parts(current),
        },
    )
    atomic(repo / STATE, state)
    return {
        "ok": True,
        "resultado": "oferecida",
        "missao": mission,
        "cooldown_ate": state["cooldown_ate"],
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), *time_sources],
    }


def respond(
    repo: Path,
    mission_id: str,
    response: str,
    *,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    mapping = {"aceitar": "aceita", "adiar": "adiada", "recusar": "recusada"}
    if response not in mapping:
        raise OpportunityError("resposta deve ser aceitar, adiar ou recusar")
    index = load_index(repo)
    state = load_state(repo, index)
    current, time_sources = _now(repo, now)
    pruned = prune_expired(state, current)
    mission = state["missoes"].get(mission_id)
    if not isinstance(mission, dict):
        if pruned:
            atomic(repo / STATE, state)
        raise OpportunityError(f"missão inexistente: {mission_id}")
    if mission["estado"] not in {"oferecida", "adiada"}:
        if pruned:
            atomic(repo / STATE, state)
        raise OpportunityError(f"missão não aceita resposta em estado {mission['estado']}")

    target = mapping[response]
    if target == "aceita":
        active, _ = _mission_counts(state)
        if active >= index["orcamento"]["max_ativas"]:
            raise OpportunityError("limite de sidequests ativas atingido")
    before = mission["estado"]
    mission["estado"] = target
    mission["ultima_decisao_em"] = mundo.instant_parts(current)
    _history(
        state,
        {
            "tipo": "resposta_sidequest",
            "id": mission_id,
            "de": before,
            "para": target,
            "em": mundo.instant_parts(current),
        },
    )
    atomic(repo / STATE, state)
    return {
        "ok": True,
        "resultado": target,
        "missao": mission,
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), *time_sources],
    }


def finish(
    repo: Path,
    mission_id: str,
    outcome: str,
    *,
    reason: str,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    if outcome not in {"concluida", "falhada", "expirada"}:
        raise OpportunityError("resultado final inválido")
    reason = text(reason, "motivo")
    index = load_index(repo)
    state = load_state(repo, index)
    current, time_sources = _now(repo, now)
    pruned = prune_expired(state, current)
    mission = state["missoes"].get(mission_id)
    if not isinstance(mission, dict):
        if pruned:
            atomic(repo / STATE, state)
        raise OpportunityError(f"missão inexistente: {mission_id}")
    if mission["estado"] not in {"oferecida", "aceita", "adiada"}:
        if pruned:
            atomic(repo / STATE, state)
        raise OpportunityError(f"missão já está encerrada: {mission['estado']}")
    if outcome == "concluida" and mission["estado"] != "aceita":
        raise OpportunityError("somente missão aceita pode ser concluída")
    before = mission["estado"]
    mission["estado"] = outcome
    mission["encerrada_em"] = mundo.instant_parts(current)
    mission["motivo_encerramento"] = reason
    _history(
        state,
        {
            "tipo": "missao_encerrada",
            "id": mission_id,
            "de": before,
            "para": outcome,
            "em": mundo.instant_parts(current),
        },
    )
    atomic(repo / STATE, state)
    return {
        "ok": True,
        "resultado": outcome,
        "missao": mission,
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), *time_sources],
    }


def reopen(
    repo: Path,
    mission_id: str,
    *,
    reason: str,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    reason = text(reason, "motivo")
    index = load_index(repo)
    state = load_state(repo, index)
    current, time_sources = _now(repo, now)
    pruned = prune_expired(state, current)
    mission = state["missoes"].get(mission_id)
    if not isinstance(mission, dict):
        if pruned:
            atomic(repo / STATE, state)
        raise OpportunityError(f"missão inexistente: {mission_id}")
    if mission["estado"] != "recusada" or not mission.get("pode_reabrir"):
        if pruned:
            atomic(repo / STATE, state)
        raise OpportunityError("missão não pode ser reaberta")
    _, opened = _mission_counts(state)
    if opened >= index["orcamento"]["max_em_aberto"]:
        raise OpportunityError("limite de sidequests em aberto atingido")
    if state.get("cooldown_ate") is not None:
        raise OpportunityError("cooldown global impede reabertura")
    if _window_expired(mission.get("janela"), current):
        raise OpportunityError("janela da missão já encerrou")

    mission["estado"] = "oferecida"
    mission["reaberta_em"] = mundo.instant_parts(current)
    mission["motivo_reabertura"] = reason
    cooldown_days = _cooldown_days(index, mission_id + "|reabertura")
    state["cooldown_ate"] = mundo.instant_parts(
        mundo.WorldInstant(current.minute + cooldown_days * 1440)
    )
    _history(
        state,
        {
            "tipo": "missao_reaberta",
            "id": mission_id,
            "cooldown_dias": cooldown_days,
            "em": mundo.instant_parts(current),
        },
    )
    atomic(repo / STATE, state)
    return {
        "ok": True,
        "resultado": "oferecida",
        "missao": mission,
        "cooldown_ate": state["cooldown_ate"],
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), *time_sources],
    }


def show(repo: Path, item_id: str) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    item = state["pendencias_avaliacao"].get(item_id)
    kind = "potencial"
    if item is None:
        item = state["missoes"].get(item_id)
        kind = "missao"
    if item is None:
        raise OpportunityError(f"oportunidade inexistente: {item_id}")
    return {
        "ok": True,
        "tipo": kind,
        "resultado": item,
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix()],
    }


def status(repo: Path, *, now: mundo.WorldInstant | None = None) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    current, time_sources = _now(repo, now)
    changed = prune_expired(state, current)
    if changed:
        atomic(repo / STATE, state)
    active, opened = _mission_counts(state)
    return {
        "ok": True,
        "gate": {
            "ciclo": state["gate"]["ciclo"],
            "restantes": len(state["gate"]["restantes"]),
            "sorteios": state["gate"]["sorteios"],
            "composicao_por_ciclo": {"nada": 8, "oportunidade": 2},
        },
        "cooldown_ate": state.get("cooldown_ate"),
        "pendencias_avaliacao": list(state["pendencias_avaliacao"]),
        "ativas": active,
        "em_aberto": opened,
        "missoes_por_estado": {
            state_name: sum(
                item["estado"] == state_name for item in state["missoes"].values()
            )
            for state_name in sorted(MISSION_STATES)
        },
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), *time_sources],
    }


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        index = load_index(repo)
        state = load_state(repo, index)
        relations = amap(load(repo / RELATIONS), str(RELATIONS))
        known_relations = set(amap(relations.get("relacoes"), "relacoes"))
        for npc_id, meta in index["perfis"].items():
            if npc_id not in known_relations:
                errors.append(f"perfil aponta para relação inexistente: {npc_id}")
                continue
            if meta.get("estado") == "ativo":
                profile = load_profile(repo, npc_id, index)
                if not profile["necessidades"]:
                    errors.append(f"perfil ativo sem necessidades: {npc_id}")
                source = profile["fonte_npc"]
                if not (repo / source).is_file():
                    errors.append(f"{npc_id}: fonte_npc ausente: {source}")
        if len(state["pendencias_avaliacao"]) > index["orcamento"]["max_pendencias_avaliacao"]:
            errors.append("pendências de avaliação excedem orçamento")
        active, opened = _mission_counts(state)
        if active > index["orcamento"]["max_ativas"]:
            errors.append("sidequests ativas excedem orçamento")
        if opened > index["orcamento"]["max_em_aberto"]:
            errors.append("sidequests em aberto excedem orçamento")
    except OpportunityError as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "erros": errors,
        "perfis": len(index["perfis"]) if "index" in locals() else 0,
    }


def _instant_arg(data: str | None, hora: str | None) -> mundo.WorldInstant | None:
    if data is None and hora is None:
        return None
    if not data or not hora:
        raise OpportunityError("--data e --hora devem ser usados juntos")
    return mundo.parse_instant(data, hora)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_enc = sub.add_parser("encontro")
    p_enc.add_argument("npc_id")
    p_enc.add_argument("--data")
    p_enc.add_argument("--hora")

    p_eval = sub.add_parser("avaliar")
    p_eval.add_argument("id")
    p_eval.add_argument("decisao", choices=["oferecer", "descartar"])
    p_eval.add_argument("--motivo", required=True)
    p_eval.add_argument("--data")
    p_eval.add_argument("--hora")

    p_resp = sub.add_parser("responder")
    p_resp.add_argument("id")
    p_resp.add_argument("resposta", choices=["aceitar", "adiar", "recusar"])
    p_resp.add_argument("--data")
    p_resp.add_argument("--hora")

    p_end = sub.add_parser("finalizar")
    p_end.add_argument("id")
    p_end.add_argument("resultado", choices=["concluida", "falhada", "expirada"])
    p_end.add_argument("--motivo", required=True)
    p_end.add_argument("--data")
    p_end.add_argument("--hora")

    p_reopen = sub.add_parser("reabrir")
    p_reopen.add_argument("id")
    p_reopen.add_argument("--motivo", required=True)
    p_reopen.add_argument("--data")
    p_reopen.add_argument("--hora")

    p_show = sub.add_parser("mostrar")
    p_show.add_argument("id")

    p_status = sub.add_parser("status")
    p_status.add_argument("--data")
    p_status.add_argument("--hora")

    sub.add_parser("check")

    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        if args.cmd == "encontro":
            result = encounter(repo, args.npc_id, now=_instant_arg(args.data, args.hora))
        elif args.cmd == "avaliar":
            result = evaluate(
                repo,
                args.id,
                args.decisao,
                reason=args.motivo,
                now=_instant_arg(args.data, args.hora),
            )
        elif args.cmd == "responder":
            result = respond(
                repo,
                args.id,
                args.resposta,
                now=_instant_arg(args.data, args.hora),
            )
        elif args.cmd == "finalizar":
            result = finish(
                repo,
                args.id,
                args.resultado,
                reason=args.motivo,
                now=_instant_arg(args.data, args.hora),
            )
        elif args.cmd == "reabrir":
            result = reopen(
                repo,
                args.id,
                reason=args.motivo,
                now=_instant_arg(args.data, args.hora),
            )
        elif args.cmd == "mostrar":
            result = show(repo, args.id)
        elif args.cmd == "status":
            result = status(repo, now=_instant_arg(args.data, args.hora))
        else:
            result = validate_repo(repo)
            if not result["ok"]:
                for error in result["erros"]:
                    print(f"- {error}")
                return 1
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False).rstrip())
        return 0
    except OpportunityError as exc:
        print(f"ERRO: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
