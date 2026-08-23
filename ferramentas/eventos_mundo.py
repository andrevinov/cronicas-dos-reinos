#!/usr/bin/env python3
"""Baralho determinístico sem reposição para eventos mundiais de baixa frequência.

Dois baralhos persistentes: ocorrência decide rotina/evento; eventos fornece a
carta concreta. Sorteio nunca cria cânone automaticamente. Quando uma carta é
sorteada, um roteador barato cruza tags operacionais com sensibilidades de agentes
e pré-seleciona poucos candidatos que podem ser afetados. Isso também não cria
ação nem fato: apenas evita varrer todos os agentes na resolução.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

import yaml

import mundo
import arco_mundo
import rede_protegida

INDEX = Path("narrador/eventos/index.yaml")
STATE = Path("narrador/eventos/estado.yaml")
INTERACTIONS = Path("narrador/eventos/interacoes.yaml")
CARDS_DIR = Path("narrador/eventos/cartas")
STRATEGIC_INDEX = Path("narrador/agentes/index.yaml")
LIGHT_INDEX = Path("narrador/agentes-leves/index.yaml")

VALID_RESULTS = {"rotina", "evento"}
VALID_SCALES = {"bairro", "cidade", "regional"}
MAX_HISTORY = 64


class WorldEventError(ValueError):
    pass


def configured(repo: Path) -> bool:
    return (repo / INDEX).is_file() and (repo / STATE).is_file()


def load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise WorldEventError(str(exc)) from exc


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorldEventError(f"{label} deve ser texto não vazio")
    return value.strip()


def amap(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WorldEventError(f"{label} deve ser mapa")
    return value


def alist(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise WorldEventError(f"{label} deve ser lista")
    return value


def strings(value: Any, label: str) -> list[str]:
    values = alist(value, label)
    result = [text(item, f"{label}[{i}]") for i, item in enumerate(values)]
    if len(result) != len(set(result)):
        raise WorldEventError(f"{label} não pode conter duplicatas")
    return result


def norm(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return " ".join(
        "".join(ch.lower() if ch.isalnum() else " " for ch in raw).split()
    )


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


def repo_path(repo: Path, raw: str, prefix: Path | None = None) -> Path:
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        raise WorldEventError(f"caminho fora do repo: {raw}")
    if prefix is not None:
        try:
            rel.relative_to(prefix)
        except ValueError as exc:
            raise WorldEventError(f"caminho {raw} deve ficar sob {prefix}") from exc
    return repo / rel


def load_index(repo: Path) -> dict[str, Any]:
    data = amap(load(repo / INDEX), str(INDEX))
    if data.get("schema_eventos_mundo") != 1 or data.get("natureza") != "reservado":
        raise WorldEventError("índice de eventos inválido")
    text(data.get("semente"), "semente")
    start = amap(data.get("inicio"), "inicio")
    mundo.parse_instant(
        text(start.get("data"), "inicio.data"),
        text(start.get("hora"), "inicio.hora"),
    )

    occurrence = amap(data.get("ocorrencia"), "ocorrencia")
    tokens = alist(occurrence.get("fichas"), "ocorrencia.fichas")
    seen: set[str] = set()
    results: list[str] = []
    for i, item in enumerate(tokens):
        item = amap(item, f"fichas[{i}]")
        token_id = text(item.get("id"), f"fichas[{i}].id")
        result = text(item.get("resultado"), f"fichas[{i}].resultado")
        if token_id in seen or result not in VALID_RESULTS:
            raise WorldEventError("ficha de ocorrência inválida/duplicada")
        seen.add(token_id)
        results.append(result)
    if "rotina" not in results or "evento" not in results:
        raise WorldEventError("urna precisa de rotina e evento")

    cards = amap(data.get("cartas"), "cartas")
    if not cards:
        raise WorldEventError("catálogo vazio")
    files: set[str] = set()
    for card_id, meta in cards.items():
        meta = amap(meta, f"cartas.{card_id}")
        text(meta.get("nome"), f"{card_id}.nome")
        text(meta.get("categoria"), f"{card_id}.categoria")
        scale = text(meta.get("escala"), f"{card_id}.escala")
        if scale not in VALID_SCALES:
            raise WorldEventError(f"{card_id}: escala inválida")
        strings(meta.get("tags"), f"{card_id}.tags")
        raw = text(meta.get("arquivo"), f"{card_id}.arquivo")
        repo_path(repo, raw, CARDS_DIR)
        if raw in files:
            raise WorldEventError("arquivo de carta duplicado")
        files.add(raw)
    return data


def instant(value: Any, label: str) -> mundo.WorldInstant:
    value = amap(value, label)
    return mundo.parse_instant(
        text(value.get("data"), label + ".data"),
        text(value.get("hora"), label + ".hora"),
    )


def load_state(repo: Path, index: dict[str, Any] | None = None) -> dict[str, Any]:
    index = index or load_index(repo)
    data = amap(load(repo / STATE), str(STATE))
    if (
        data.get("schema_estado_eventos_mundo") != 1
        or data.get("natureza") != "controle_reservado"
    ):
        raise WorldEventError("estado de eventos inválido")
    instant(data.get("processado_ate"), "processado_ate")
    valid = {
        "ocorrencia": {item["id"] for item in index["ocorrencia"]["fichas"]},
        "eventos": set(index["cartas"]),
    }
    for name in ("ocorrencia", "eventos"):
        deck = amap(data.get(name), name)
        cycle = deck.get("ciclo")
        remaining = alist(deck.get("restantes"), name + ".restantes")
        if (
            not isinstance(cycle, int)
            or cycle < 0
            or len(remaining) != len(set(remaining))
            or set(remaining) - valid[name]
        ):
            raise WorldEventError(f"{name}: estado inválido")
        if cycle == 0 and remaining:
            raise WorldEventError(f"{name}: ciclo 0 exige vazio")
    history = alist(data.get("historico_recente"), "historico_recente")
    if len(history) > MAX_HISTORY:
        raise WorldEventError("histórico grande demais")
    return data


def _load_operational_indexes(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    strategic = amap(load(repo / STRATEGIC_INDEX), str(STRATEGIC_INDEX))
    light = amap(load(repo / LIGHT_INDEX), str(LIGHT_INDEX))
    if strategic.get("schema_agentes") != 2 or not isinstance(
        strategic.get("agentes"), dict
    ):
        raise WorldEventError("índice de agentes estratégicos inválido")
    if light.get("schema_agentes_leves") not in {1, 2} or not isinstance(
        light.get("agentes"), dict
    ):
        raise WorldEventError("índice de agentes leves inválido")
    return strategic, light


def load_interactions(
    repo: Path,
    operational_indexes: tuple[dict[str, Any], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    data = amap(load(repo / INTERACTIONS), str(INTERACTIONS))
    if (
        data.get("schema_interacoes_eventos") != 1
        or data.get("natureza") != "roteador_reservado"
    ):
        raise WorldEventError("roteador de interações de eventos inválido")
    budget = amap(data.get("orcamento"), "interacoes.orcamento")
    for field in ("max_estrategicos_por_evento", "max_leves_por_evento"):
        value = budget.get(field)
        if not isinstance(value, int) or value < 0:
            raise WorldEventError(f"interacoes.orcamento.{field} deve ser inteiro >= 0")
    if budget.get("ordenacao") != "coincidencias_prioridade_id":
        raise WorldEventError("ordenação de interações inválida")

    strategic, light = operational_indexes or _load_operational_indexes(repo)
    known = {
        "estrategicos": set(strategic["agentes"]),
        "leves": set(light["agentes"]),
    }
    for layer in ("estrategicos", "leves"):
        rules = amap(data.get(layer), f"interacoes.{layer}")
        for agent_id, rule in rules.items():
            if agent_id not in known[layer]:
                raise WorldEventError(
                    f"interacoes.{layer} referencia agente inexistente: {agent_id}"
                )
            rule = amap(rule, f"interacoes.{layer}.{agent_id}")
            priority = rule.get("prioridade")
            if not isinstance(priority, int) or priority < 0:
                raise WorldEventError(
                    f"interacoes.{layer}.{agent_id}.prioridade deve ser inteiro >= 0"
                )
            if not strings(rule.get("tags"), f"interacoes.{layer}.{agent_id}.tags"):
                raise WorldEventError(f"interacoes.{layer}.{agent_id}.tags vazio")
    return data


def _strategic_eligible(meta: dict[str, Any]) -> bool:
    if meta.get("estado") != "ativo":
        return False
    presence = meta.get("presenca")
    rule = meta.get("atuacao_local")
    if rule == "exige_presenca_fisica":
        return presence in {"presente", "presente_oculto"}
    if rule == "permite_rede":
        return True
    if rule == "estrutura_local":
        return presence in {"presente", "presente_oculto", "distribuida", "ancorada"}
    if rule == "depende_de_membros_presentes":
        return False
    return False


def _light_eligible(meta: dict[str, Any]) -> bool:
    return meta.get("estado") == "ativo"


def _rank(
    tags: list[str],
    rules: dict[str, Any],
    current: dict[str, Any],
    *,
    eligible,
    limit: int,
) -> list[str]:
    wanted = set(tags)
    scored: list[tuple[int, int, str]] = []
    for agent_id, rule in rules.items():
        meta = current.get(agent_id)
        if not isinstance(meta, dict) or not eligible(meta):
            continue
        matches = wanted & set(rule["tags"])
        if matches:
            scored.append((len(matches), int(rule["prioridade"]), agent_id))
    scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [agent_id for _, _, agent_id in scored[:limit]]


def routing_context(repo: Path) -> dict[str, Any]:
    strategic, light = _load_operational_indexes(repo)
    router = load_interactions(repo, (strategic, light))
    try:
        arc_ctx = arco_mundo.context(repo)
        filtered = {}
        blocked = []
        for agent_id, meta in strategic["agentes"].items():
            gate = arco_mundo.strategic_agent_gate(repo, agent_id, purpose="evento", ctx=arc_ctx)
            if gate["permitido"]:
                filtered[agent_id] = meta
            else:
                blocked.append({"agente": agent_id, "motivo": gate["motivo"]})
        strategic = {**strategic, "agentes": filtered}
    except arco_mundo.ArcWorldError as exc:
        raise WorldEventError(str(exc)) from exc
    try:
        protected = (
            rede_protegida.load_policy(repo)
            if rede_protegida.configured(repo)
            else None
        )
    except rede_protegida.ProtectedNetworkError as exc:
        raise WorldEventError(str(exc)) from exc
    return {
        "router": router,
        "strategic": strategic,
        "light": light,
        "rede_protegida": protected,
        "agentes_estrategicos_bloqueados_pelo_arco": blocked,
        "fontes_lidas": list(dict.fromkeys([
            INTERACTIONS.as_posix(),
            STRATEGIC_INDEX.as_posix(),
            LIGHT_INDEX.as_posix(),
            *arc_ctx["fontes_lidas"],
            *([rede_protegida.INDEX.as_posix()] if protected is not None else []),
        ])),
    }


def route_agents(tags: list[str], context: dict[str, Any]) -> dict[str, list[str]]:
    router = context["router"]
    budget = router["orcamento"]
    strategic = _rank(
        tags,
        router["estrategicos"],
        context["strategic"]["agentes"],
        eligible=_strategic_eligible,
        limit=budget["max_estrategicos_por_evento"],
    )
    light = _rank(
        tags,
        router["leves"],
        context["light"]["agentes"],
        eligible=_light_eligible,
        limit=budget["max_leves_por_evento"],
    )
    policy = context.get("rede_protegida")
    if not isinstance(policy, dict):
        return {"estrategicos": strategic, "leves": light}
    partition = rede_protegida.partition_candidates(policy, light)
    return {
        "estrategicos": strategic,
        "leves": partition["afetados"],
        "nucleo_protegido": partition["nucleo_protegido"],
    }


def deck_order(seed: str, deck: str, cycle: int, ids: list[str]) -> list[str]:
    return sorted(
        ids,
        key=lambda item: hashlib.sha256(
            f"{seed}|{deck}|{cycle}|{item}".encode()
        ).hexdigest(),
    )


def draw(
    state: dict[str, Any],
    section: str,
    ids: list[str],
    seed: str,
) -> str:
    deck = state[section]
    if not deck["restantes"]:
        deck["ciclo"] += 1
        deck["restantes"] = deck_order(seed, section, deck["ciclo"], ids)
    return deck["restantes"].pop(0)


def pending_id(card_id: str, when: mundo.WorldInstant) -> str:
    return "mundo-" + hashlib.sha256(
        f"evento_mundial|{card_id}|{when.minute}".encode()
    ).hexdigest()[:16]


def dawns(
    start: mundo.WorldInstant,
    end: mundo.WorldInstant,
    dawn: int,
    minimum: mundo.WorldInstant,
) -> list[mundo.WorldInstant]:
    return [
        mundo.WorldInstant(day * 1440 + dawn)
        for day in mundo._iter_day_indices(start, end)
        if start < mundo.WorldInstant(day * 1440 + dawn) <= end
        and mundo.WorldInstant(day * 1440 + dawn) >= minimum
    ]


def process_checkpoint(repo: Path) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    agenda = mundo.load_agenda(repo)
    now, _ = mundo.load_canonical_time(repo)
    world_state = mundo.load_world_state(repo)
    done = instant(state["processado_ate"], "processado_ate")
    if done > now:
        raise WorldEventError("cursor do baralho está à frente do tempo canônico")
    due = dawns(
        done,
        now,
        mundo._dawn_minute(agenda),
        instant(index["inicio"], "inicio"),
    )
    sources = [
        INDEX.as_posix(),
        STATE.as_posix(),
        mundo.AGENDA_PATH.as_posix(),
        mundo.TIME_PATH.as_posix(),
        mundo.WORLD_STATE_PATH.as_posix(),
    ]
    if not due:
        return {
            "ok": True,
            "alterou": False,
            "dias_processados": 0,
            "dias_rotina": 0,
            "eventos_sorteados": [],
            "novas_pendencias": [],
            "eventos_reconsiderar": [],
            "agentes_evento_reconsiderar": [],
            "agentes_leves_evento_reconsiderar": [],
            "nucleo_protegido_evento_reconsiderar": [],
            "fontes_lidas": sources,
        }

    seed = index["semente"]
    token_map = {
        item["id"]: item["resultado"] for item in index["ocorrencia"]["fichas"]
    }
    token_ids = list(token_map)
    card_ids = list(index["cartas"])
    emitted: list[dict[str, Any]] = []
    routine_days = 0
    drawn: list[str] = []
    routing: dict[str, Any] | None = None

    for when in due:
        token = draw(state, "ocorrencia", token_ids, seed)
        result = token_map[token]
        history = {
            "amanhecer": mundo.instant_parts(when),
            "ficha_ocorrencia": token,
            "resultado": result,
        }
        if result == "rotina":
            routine_days += 1
        else:
            card_id = draw(state, "eventos", card_ids, seed)
            meta = index["cartas"][card_id]
            history["evento"] = card_id
            drawn.append(card_id)
            if routing is None:
                routing = routing_context(repo)
                sources.extend(routing["fontes_lidas"])
            affected = route_agents(meta["tags"], routing)
            pending = {
                "id": pending_id(card_id, when),
                "tipo": "evento_mundial",
                "evento": card_id,
                "categoria": meta["categoria"],
                "escala": meta["escala"],
                "agentes_afetados": affected["estrategicos"],
                "agentes_leves_afetados": affected["leves"],
                "disparado_em": mundo.instant_parts(when),
                "motivo": (
                    f"Carta mundial '{meta['nome']}' sorteada sem reposição; "
                    "resolver a manifestação e seus possíveis efeitos sobre os "
                    "agentes pré-filtrados sem criar cânone automaticamente."
                ),
                "origem": f"eventos:{card_id}",
            }
            core = affected.get("nucleo_protegido") or []
            if core:
                pending["nucleo_protegido_reconsiderar"] = core
                pending["protecao_rede_central"] = rede_protegida.event_guard(
                    routing["rede_protegida"], core
                )
            emitted.append(pending)
        state["historico_recente"].append(history)
        state["historico_recente"] = state["historico_recente"][-MAX_HISTORY:]
        state["processado_ate"] = mundo.instant_parts(when)

    added = mundo._merge_pending(world_state, emitted)
    if added:
        mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, world_state)
    atomic(repo / STATE, state)
    strategic_ids = sorted(
        {
            agent
            for item in added
            for agent in item.get("agentes_afetados") or []
        }
    )
    light_ids = sorted(
        {
            agent
            for item in added
            for agent in item.get("agentes_leves_afetados") or []
        }
    )
    protected_ids = sorted(
        {
            agent
            for item in added
            for agent in item.get("nucleo_protegido_reconsiderar") or []
        }
    )
    return {
        "ok": True,
        "alterou": True,
        "dias_processados": len(due),
        "dias_rotina": routine_days,
        "eventos_sorteados": drawn,
        "novas_pendencias": added,
        "eventos_reconsiderar": [item["evento"] for item in added],
        "agentes_evento_reconsiderar": strategic_ids,
        "agentes_leves_evento_reconsiderar": light_ids,
        "nucleo_protegido_evento_reconsiderar": protected_ids,
        "fontes_lidas": list(dict.fromkeys(sources)),
    }


def prune_dead_candidates(repo: Path, dead: set[str]) -> dict[str, Any]:
    """Remove mortos de listas passivas de candidatos sem cancelar o evento."""
    if not dead or not (repo / mundo.WORLD_STATE_PATH).is_file():
        return {"ok": True, "alterou": False, "pendencias_atualizadas": []}
    world_state = mundo.load_world_state(repo)
    changed_ids: list[str] = []
    for item in world_state.get("pendencias") or []:
        if not isinstance(item, dict) or item.get("tipo") != "evento_mundial":
            continue
        changed = False
        for field in (
            "agentes_afetados",
            "agentes_leves_afetados",
            "nucleo_protegido_reconsiderar",
        ):
            values = item.get(field)
            if not isinstance(values, list):
                continue
            filtered = [value for value in values if value not in dead]
            if filtered != values:
                item[field] = filtered
                changed = True
        if changed:
            changed_ids.append(item["id"])
    if changed_ids:
        mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, world_state)
    return {
        "ok": True,
        "alterou": bool(changed_ids),
        "pendencias_atualizadas": changed_ids,
    }


def validate_card(
    repo: Path,
    card_id: str,
    meta: dict[str, Any],
) -> dict[str, Any]:
    raw = text(meta.get("arquivo"), f"{card_id}.arquivo")
    data = amap(load(repo_path(repo, raw, CARDS_DIR)), raw)
    if (
        data.get("schema_evento_mundo") != 1
        or data.get("natureza") != "reservado"
        or data.get("estatuto") != "molde_nao_canonico_ate_resolucao"
    ):
        raise WorldEventError(f"{card_id}: fragmento inválido")
    if (
        data.get("id") != card_id
        or data.get("nome") != meta["nome"]
        or data.get("categoria") != meta["categoria"]
        or data.get("escala") != meta["escala"]
    ):
        raise WorldEventError(f"{card_id}: fragmento diverge do índice")
    text(data.get("premissa"), card_id + ".premissa")
    text(data.get("pergunta_de_resolucao"), card_id + ".pergunta")
    guardrails = strings(data.get("guardrails"), f"{card_id}.guardrails")
    card_tags = strings(data.get("tags"), f"{card_id}.tags")
    if not guardrails or not card_tags:
        raise WorldEventError(f"{card_id}: guardrails/tags vazios")
    if card_tags != meta["tags"]:
        raise WorldEventError(f"{card_id}: tags do fragmento divergem do índice")
    return data


def resolve(index: dict[str, Any], query: str) -> tuple[str, dict[str, Any]]:
    if query in index["cartas"]:
        return query, index["cartas"][query]
    wanted = norm(query)
    hits: list[tuple[str, dict[str, Any]]] = []
    for card_id, meta in index["cartas"].items():
        pool = {norm(card_id), norm(meta["nome"])}
        if wanted in pool or any(wanted and wanted in item for item in pool):
            hits.append((card_id, meta))
    if len(hits) != 1:
        raise WorldEventError(f"carta não encontrada/ambígua: {query}")
    return hits[0]


def show(repo: Path, query: str) -> dict[str, Any]:
    index = load_index(repo)
    card_id, meta = resolve(index, query)
    card = validate_card(repo, card_id, meta)
    return {
        "evento_id": card_id,
        "fontes_lidas": [INDEX.as_posix(), meta["arquivo"]],
        "resultado": card,
    }


def status(repo: Path) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    return {
        "processado_ate": state["processado_ate"],
        "ocorrencia": {
            "ciclo": state["ocorrencia"]["ciclo"],
            "restantes": len(state["ocorrencia"]["restantes"]),
            "total_por_ciclo": len(index["ocorrencia"]["fichas"]),
        },
        "eventos": {
            "ciclo": state["eventos"]["ciclo"],
            "restantes": len(state["eventos"]["restantes"]),
            "total_por_ciclo": len(index["cartas"]),
        },
        "historico_recente": state["historico_recente"],
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix()],
    }


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        index = load_index(repo)
        state = load_state(repo, index)
        strategic, light = _load_operational_indexes(repo)
        router = load_interactions(repo, (strategic, light))
        for card_id, meta in index["cartas"].items():
            validate_card(repo, card_id, meta)

        world_state = mundo.load_world_state(repo)
        known_cards = set(index["cartas"])
        known_strategic = set(strategic["agentes"])
        known_light = set(light["agentes"])
        max_strategic = router["orcamento"]["max_estrategicos_por_evento"]
        max_light = router["orcamento"]["max_leves_por_evento"]
        protected_policy = (
            rede_protegida.load_policy(repo)
            if rede_protegida.configured(repo)
            else None
        )
        protected_ids = (
            rede_protegida.protected_ids(protected_policy)
            if isinstance(protected_policy, dict)
            else set()
        )
        if isinstance(protected_policy, dict):
            validation = rede_protegida.validate(repo)
            errors.extend(
                f"rede protegida: {error}" for error in validation["erros"]
            )
        for item in world_state.get("pendencias") or []:
            if item.get("tipo") != "evento_mundial":
                continue
            if item.get("evento") not in known_cards:
                errors.append(f"evento inexistente: {item.get('evento')}")
            strategic_ids = item.get("agentes_afetados") or []
            light_ids = item.get("agentes_leves_afetados") or []
            protected_pending = item.get("nucleo_protegido_reconsiderar") or []
            if set(strategic_ids) - known_strategic:
                errors.append("evento referencia agente estratégico inexistente")
            if set(light_ids) - known_light:
                errors.append("evento referencia agente leve inexistente")
            if set(protected_pending) - known_light:
                errors.append("evento referencia núcleo protegido inexistente")
            if set(protected_pending) - protected_ids:
                errors.append("evento marca NPC não protegido como núcleo protegido")
            if set(light_ids) & protected_ids:
                errors.append("evento marca núcleo protegido como afetado diretamente")
            if (
                len(strategic_ids) > max_strategic
                or len(light_ids) + len(protected_pending) > max_light
            ):
                errors.append("evento excede orçamento de interações agenciais")

        now, _ = mundo.load_canonical_time(repo)
        if instant(state["processado_ate"], "processado_ate") > now:
            errors.append("estado de eventos além do tempo canônico")
    except (
        WorldEventError,
        mundo.WorldEngineError,
        rede_protegida.ProtectedNetworkError,
    ) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "quantidade_cartas": len(index["cartas"]) if "index" in locals() else 0,
        "erros": list(dict.fromkeys(errors)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("processar")
    sub.add_parser("validar")
    show_parser = sub.add_parser("mostrar")
    show_parser.add_argument("evento")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "status":
            result = status(repo)
        elif args.cmd == "processar":
            result = process_checkpoint(repo)
        elif args.cmd == "validar":
            result = validate_repo(repo)
        else:
            result = show(repo, args.evento)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0 if args.cmd != "validar" or result["ok"] else 1
    except (WorldEventError, mundo.WorldEngineError) as exc:
        print(f"erro: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
