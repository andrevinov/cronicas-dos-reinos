#!/usr/bin/env python3
"""Descoberta contextual inversa, determinística e barata para abertura de cenas.

A camada recebe apenas tags explícitas já sustentadas pela cena e cruza um
roteador reservado pequeno. Ela pode apontar três classes independentes de
candidato:

- presença/aparição de agente;
- entrada orgânica de aliado futuro;
- linha operacional do arco;
- direção narrativa canônica.

Em todos os casos, candidato significa **avaliar**, nunca executar. A seleção
respeita primeiro o Contrato de Arco e, para antagonistas, o marco mínimo de
aparição. Presença consulta somente controles compactos + índice resumido de agentes; operação para nos controles do arco; direção consulta somente o
estado operacional de direções. Nenhum fragmento narrativo é aberto nesta etapa.
"""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

import yaml

import arcos
import aliados_contextuais
import marcos_aparicao

ROUTER = Path("narrador/mundo/contextos-cena.yaml")
STRATEGIC_INDEX = Path("narrador/agentes/index.yaml")
DIRECTIONS_INDEX = Path("narrador/direcoes/index.yaml")
DIRECTIONS_STATE = Path("narrador/direcoes/estado.yaml")

MAX_CONTEXT_TAGS = 8
MAX_PRESENCE_CANDIDATES = 2
MAX_OPERATION_CANDIDATES = 2
MAX_DIRECTION_CANDIDATES = 1
MAX_ENTRY_CANDIDATES = 1
MAX_CONTEXT_CANDIDATES = 4

VALID_TYPES = {"presenca", "entrada", "operacao", "direcao"}
ARC_GROUPS = ("antagonistas", "aliados")
VALID_ARC_GROUPS = {*ARC_GROUPS, "livre"}
VALID_LOCAL_RULES = {
    "exige_presenca_fisica",
    "permite_rede",
    "estrutura_local",
    "depende_de_membros_presentes",
}
VALID_DIRECTION_STATES = {"ativa", "latente", "suspensa", "concluida"}
TYPE_LIMIT_FIELDS = {
    "presenca": "max_presencas",
    "operacao": "max_operacoes",
    "direcao": "max_direcoes",
    "entrada": "max_entradas",
}
TYPE_ORDER = {"presenca": 0, "entrada": 1, "operacao": 2, "direcao": 3}


class ContextSceneError(ValueError):
    """Erro de contrato do roteador contextual."""


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise ContextSceneError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContextSceneError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ContextSceneError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContextSceneError(f"{label} deve ser texto não vazio")
    return value.strip()


def _strict_keys(data: dict[str, Any], allowed: set[str], label: str) -> None:
    extra = set(data) - allowed
    if extra:
        raise ContextSceneError(
            f"{label} contém campos não permitidos: {', '.join(sorted(extra))}"
        )


def normalize_tag(value: Any) -> str:
    """Normaliza rótulo humano para chave ASCII estável sem interpretação semântica."""
    raw = _text(value, "tag contextual").casefold()
    folded = unicodedata.normalize("NFKD", raw)
    plain = "".join(ch for ch in folded if not unicodedata.combining(ch))
    normalized = re.sub(r"[^a-z0-9]+", "_", plain).strip("_")
    if not normalized:
        raise ContextSceneError("tag contextual não contém identificador utilizável")
    return normalized


def normalize_tags(values: Iterable[Any] | None) -> list[str]:
    raw = list(values or [])
    if len(raw) > MAX_CONTEXT_TAGS:
        raise ContextSceneError(
            f"abertura contextual aceita no máximo {MAX_CONTEXT_TAGS} tags"
        )
    normalized: list[str] = []
    seen: set[str] = set()
    for value in raw:
        tag = normalize_tag(value)
        if tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)
    return normalized


def _candidate_id(value: Any, label: str) -> str:
    value = _text(value, label)
    if normalize_tag(value) != value:
        raise ContextSceneError(f"{label} deve usar chave já normalizada: {value}")
    return value


def load_router(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / ROUTER), ROUTER.as_posix())
    if data.get("schema_contextos_cena") != 3:
        raise ContextSceneError("roteador contextual deve usar schema_contextos_cena: 3")
    if data.get("natureza") != "roteador_reservado":
        raise ContextSceneError("roteador contextual deve ter natureza: roteador_reservado")

    budget = _map(data.get("orcamento"), "contextos_cena.orcamento")
    required_budget = {
        "max_tags_por_cena": MAX_CONTEXT_TAGS,
        "max_presencas": MAX_PRESENCE_CANDIDATES,
        "max_operacoes": MAX_OPERATION_CANDIDATES,
        "max_direcoes": MAX_DIRECTION_CANDIDATES,
        "max_entradas": MAX_ENTRY_CANDIDATES,
        "max_candidatos_total": MAX_CONTEXT_CANDIDATES,
    }
    for field, ceiling in required_budget.items():
        value = budget.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= ceiling:
            raise ContextSceneError(
                f"orcamento.{field} deve ficar entre 1 e {ceiling}"
            )
    if budget.get("ordenacao") != "coincidencias_prioridade_tipo_id":
        raise ContextSceneError("ordenação contextual inválida")

    candidates = _map(data.get("candidatos"), "contextos_cena.candidatos")
    for binding_id, raw_meta in candidates.items():
        binding_id = _candidate_id(binding_id, "id de binding contextual")
        meta = _map(raw_meta, f"candidatos.{binding_id}")
        kind = _text(meta.get("tipo"), f"candidatos.{binding_id}.tipo")
        if kind not in VALID_TYPES:
            raise ContextSceneError(f"candidatos.{binding_id}.tipo inválido: {kind}")

        allowed = {"tipo", "alvo", "prioridade", "min_coincidencias", "tags"}
        if kind == "presenca":
            allowed.add("grupo_arco")
        _strict_keys(meta, allowed, f"candidatos.{binding_id}")

        target = _candidate_id(meta.get("alvo"), f"candidatos.{binding_id}.alvo")
        if kind == "presenca":
            arc_group = _text(meta.get("grupo_arco"), f"candidatos.{binding_id}.grupo_arco")
            if arc_group not in VALID_ARC_GROUPS:
                raise ContextSceneError(
                    f"candidatos.{binding_id}.grupo_arco inválido: {arc_group}"
                )
        elif "grupo_arco" in meta:
            raise ContextSceneError(
                f"candidatos.{binding_id}.grupo_arco só é permitido para presença"
            )

        priority = meta.get("prioridade")
        if not isinstance(priority, int) or isinstance(priority, bool) or priority < 0:
            raise ContextSceneError(
                f"candidatos.{binding_id}.prioridade deve ser inteiro >= 0"
            )
        minimum = meta.get("min_coincidencias", 1)
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
            raise ContextSceneError(
                f"candidatos.{binding_id}.min_coincidencias deve ser inteiro >= 1"
            )
        tags = _list(meta.get("tags"), f"candidatos.{binding_id}.tags")
        if not tags:
            raise ContextSceneError(f"candidatos.{binding_id}.tags não pode ser vazio")
        normalized = [normalize_tag(tag) for tag in tags]
        if len(normalized) != len(set(normalized)):
            raise ContextSceneError(
                f"candidatos.{binding_id}.tags não pode conter duplicatas normalizadas"
            )
        if normalized != tags:
            raise ContextSceneError(
                f"candidatos.{binding_id}.tags deve usar chaves já normalizadas"
            )
        if minimum > len(tags):
            raise ContextSceneError(
                f"candidatos.{binding_id}.min_coincidencias excede quantidade de tags"
            )
        # força validação sem reter cópia normalizada paralela
        _ = target
    return data


def load_strategic_index(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / STRATEGIC_INDEX), STRATEGIC_INDEX.as_posix())
    if data.get("schema_agentes") != 2 or data.get("natureza") != "reservado":
        raise ContextSceneError("índice de agentes estratégicos inválido")
    _map(data.get("agentes"), "agentes")
    return data


def load_directions_index(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / DIRECTIONS_INDEX), DIRECTIONS_INDEX.as_posix())
    if data.get("schema_direcoes") != 1 or data.get("natureza") != "reservado":
        raise ContextSceneError("índice de direções inválido")
    _map(data.get("direcoes"), "direcoes")
    return data


def load_directions_state(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / DIRECTIONS_STATE), DIRECTIONS_STATE.as_posix())
    if data.get("schema_estado_direcoes") != 1:
        raise ContextSceneError("estado de direções deve usar schema_estado_direcoes: 1")
    if data.get("natureza") != "controle_reservado":
        raise ContextSceneError("estado de direções deve ter natureza: controle_reservado")
    directions = _map(data.get("direcoes"), "estado_direcoes.direcoes")
    for direction_id, raw in directions.items():
        item = _map(raw, f"estado_direcoes.{direction_id}")
        state = _text(item.get("estado"), f"estado_direcoes.{direction_id}.estado")
        if state not in VALID_DIRECTION_STATES:
            raise ContextSceneError(f"estado inválido para direção {direction_id}: {state}")
        current = item.get("marco_atual")
        if state == "concluida":
            if current is not None:
                raise ContextSceneError(
                    f"direção concluída {direction_id} deve ter marco_atual nulo"
                )
        else:
            _text(current, f"estado_direcoes.{direction_id}.marco_atual")
    return data


def _evaluation_mode(meta: dict[str, Any]) -> str | None:
    """Decide apenas se o agente merece avaliação; nunca estabelece sua presença."""
    if meta.get("estado") != "ativo":
        return None

    presence = meta.get("presenca")
    rule = meta.get("atuacao_local")
    if rule not in VALID_LOCAL_RULES:
        raise ContextSceneError(f"regra de atuação local inválida no índice: {rule}")

    if rule == "exige_presenca_fisica":
        if presence in {"presente", "presente_oculto"}:
            return "presenca_confirmada"
        if presence == "indeterminado":
            return "avaliar_estabelecimento_presenca"
        return None
    if rule == "permite_rede":
        return "atuacao_por_rede"
    if rule == "estrutura_local":
        if presence in {"presente", "presente_oculto", "distribuida", "ancorada"}:
            return "estrutura_local"
        return None
    return None


def _arc_line_catalog(repo: Path) -> tuple[dict[str, str], list[str]]:
    """Catálogo frio para validar bindings de linhas em todos os arcos."""
    try:
        index = arcos.load_index(repo)
        catalog: dict[str, str] = {}
        sources = [arcos.INDEX.as_posix()]
        for arc_id in index["arcos"]:
            contract = arcos.load_contract(repo, arc_id, index)
            sources.append((arcos.ARCS_DIR / f"{arc_id}.yaml").as_posix())
            for line_id in contract["linhas_operacionais"]:
                if line_id in catalog:
                    raise ContextSceneError(
                        f"linha operacional contextual ambígua: {line_id} aparece em {catalog[line_id]} e {arc_id}"
                    )
                catalog[line_id] = arc_id
        return catalog, sources
    except arcos.ArcContractError as exc:
        raise ContextSceneError(str(exc)) from exc


def validate(repo: Path) -> dict[str, Any]:
    """Validação fria/CI dos bindings sem abrir fragmentos narrativos."""
    router = load_router(repo)
    sources = [ROUTER.as_posix()]

    presence_targets = {
        meta["alvo"]
        for meta in router["candidatos"].values()
        if meta["tipo"] == "presenca"
    }
    entry_targets = {
        meta["alvo"]
        for meta in router["candidatos"].values()
        if meta["tipo"] == "entrada"
    }
    operation_targets = {
        meta["alvo"]
        for meta in router["candidatos"].values()
        if meta["tipo"] == "operacao"
    }
    direction_targets = {
        meta["alvo"]
        for meta in router["candidatos"].values()
        if meta["tipo"] == "direcao"
    }

    if presence_targets:
        agents = load_strategic_index(repo)["agentes"]
        sources.append(STRATEGIC_INDEX.as_posix())
        missing = sorted(presence_targets - set(agents))
        if missing:
            raise ContextSceneError(
                "binding contextual referencia agente inexistente: " + ", ".join(missing)
            )

    if entry_targets:
        try:
            ally_validation = aliados_contextuais.validate(repo)
        except aliados_contextuais.AllyContextError as exc:
            raise ContextSceneError(str(exc)) from exc
        if not ally_validation["ok"]:
            raise ContextSceneError("entradas contextuais inválidas: " + "; ".join(ally_validation["erros"]))
        entry_index = aliados_contextuais.load_index(repo)
        sources.extend([aliados_contextuais.INDEX.as_posix(), aliados_contextuais.STATE.as_posix(), aliados_contextuais.RUNTIME.as_posix()])
        missing = sorted(entry_targets - set(entry_index["candidatos"]))
        if missing:
            raise ContextSceneError("binding contextual referencia aliado inexistente: " + ", ".join(missing))

    if operation_targets:
        catalog, arc_sources = _arc_line_catalog(repo)
        sources.extend(arc_sources)
        missing = sorted(operation_targets - set(catalog))
        if missing:
            raise ContextSceneError(
                "binding contextual referencia linha operacional inexistente: "
                + ", ".join(missing)
            )

    if direction_targets:
        directions = load_directions_index(repo)["direcoes"]
        sources.append(DIRECTIONS_INDEX.as_posix())
        missing = sorted(direction_targets - set(directions))
        if missing:
            raise ContextSceneError(
                "binding contextual referencia direção inexistente: " + ", ".join(missing)
            )

    try:
        current_arc = arcos.current(repo)
    except arcos.ArcContractError as exc:
        raise ContextSceneError(str(exc)) from exc
    sources.extend(current_arc["fontes_lidas"])

    if presence_targets:
        milestone_validation = marcos_aparicao.validate(repo, check_source=False)
        if not milestone_validation["ok"]:
            raise ContextSceneError(
                "marcos de aparição inválidos: " + "; ".join(milestone_validation["erros"])
            )
        sources.extend([marcos_aparicao.INDEX.as_posix(), marcos_aparicao.STATE.as_posix()])

    return {
        "ok": True,
        "bindings": len(router["candidatos"]),
        "tipos": {
            kind: sum(1 for meta in router["candidatos"].values() if meta["tipo"] == kind)
            for kind in sorted(VALID_TYPES)
        },
        "arco": {"arco_id": current_arc["id"], "titulo": current_arc["titulo"]},
        "fontes_lidas": list(dict.fromkeys(sources)),
    }


def _prefilter(
    router: dict[str, Any], wanted: set[str], excluded_presence: set[str]
) -> list[tuple[str, dict[str, Any], list[str]]]:
    result: list[tuple[str, dict[str, Any], list[str]]] = []
    for binding_id, rule in router["candidatos"].items():
        if rule["tipo"] in {"presenca", "entrada"} and rule["alvo"] in excluded_presence:
            continue
        matches = sorted(wanted & set(rule["tags"]))
        if len(matches) < int(rule.get("min_coincidencias", 1)):
            continue
        result.append((binding_id, rule, matches))
    return result


def _filter_by_arc(
    repo: Path,
    candidates: list[tuple[str, dict[str, Any], list[str]]],
) -> tuple[
    list[tuple[str, dict[str, Any], list[str]]],
    dict[str, Any],
    list[str],
    dict[str, Any] | None,
]:
    needs_arc = any(
        rule["tipo"] in {"entrada", "operacao", "direcao"}
        or (rule["tipo"] == "presenca" and rule["grupo_arco"] in ARC_GROUPS)
        for _, rule, _ in candidates
    )
    if not needs_arc:
        return candidates, {"aplicado": False, "bloqueados": 0, "bloqueados_por_tipo": {}}, [], None

    try:
        info = arcos.current(repo)
    except arcos.ArcContractError as exc:
        raise ContextSceneError(str(exc)) from exc

    lines = info["linhas_operacionais"]
    directions = set(info["habilitacoes"]["direcoes"])
    kept: list[tuple[str, dict[str, Any], list[str]]] = []
    blocked_by_type = {kind: 0 for kind in VALID_TYPES}

    for binding_id, rule, matches in candidates:
        kind = rule["tipo"]
        target = rule["alvo"]
        allowed = True
        if kind == "presenca":
            group = rule["grupo_arco"]
            if group in ARC_GROUPS:
                allowed = target in set(info["habilitacoes"][group])
        elif kind == "entrada":
            allowed = target in set(info["habilitacoes"]["aliados"])
        elif kind == "operacao":
            allowed = target in lines
        elif kind == "direcao":
            allowed = target in directions
        if not allowed:
            blocked_by_type[kind] += 1
            continue
        kept.append((binding_id, rule, matches))

    blocked_total = sum(blocked_by_type.values())
    return (
        kept,
        {
            "aplicado": True,
            "arco_id": info["id"],
            "titulo": info["titulo"],
            "bloqueados": blocked_total,
            "bloqueados_por_tipo": blocked_by_type,
            "politica": info["habilitacoes"]["politica_nao_listados"],
        },
        info["fontes_lidas"],
        info,
    )


def _presence_rows(
    repo: Path,
    entries: list[tuple[str, dict[str, Any], list[str]]],
    *,
    scene_id: str,
    arc_info: dict[str, Any] | None,
) -> tuple[list[tuple[int, int, str, dict[str, Any]]], list[str]]:
    if not entries:
        return [], []

    controlled_targets = [
        rule["alvo"]
        for _, rule, _ in entries
        if rule.get("grupo_arco") == "antagonistas"
    ]
    milestone_results: dict[str, dict[str, Any]] = {}
    milestone_sources: list[str] = []
    if controlled_targets:
        try:
            checked = marcos_aparicao.gates(
                repo, controlled_targets, arc_info=arc_info
            )
        except marcos_aparicao.AppearanceMilestoneError as exc:
            raise ContextSceneError(str(exc)) from exc
        milestone_results = checked["resultados"]
        milestone_sources = checked["fontes_lidas"]

    allowed_entries: list[tuple[str, dict[str, Any], list[str], dict[str, Any] | None]] = []
    for binding_id, rule, matches in entries:
        milestone = None
        if rule.get("grupo_arco") == "antagonistas":
            milestone = milestone_results.get(rule["alvo"])
            if not isinstance(milestone, dict):
                raise ContextSceneError(
                    f"marco de aparição ausente para candidato {rule['alvo']}"
                )
            if not milestone.get("permitido"):
                continue
        allowed_entries.append((binding_id, rule, matches, milestone))

    if not allowed_entries:
        return [], milestone_sources

    agents = load_strategic_index(repo)["agentes"]
    rows: list[tuple[int, int, str, dict[str, Any]]] = []
    for binding_id, rule, matches, milestone in allowed_entries:
        target = rule["alvo"]
        current = agents.get(target)
        if not isinstance(current, dict):
            raise ContextSceneError(
                f"candidato contextual referencia agente inexistente: {target}"
            )
        mode = _evaluation_mode(current)
        if mode is None:
            continue
        item = {
            "id": target,
            "binding_id": binding_id,
            "tipo": "presenca",
            "nome": _text(current.get("nome"), f"agentes.{target}.nome"),
            "grupo_arco": rule["grupo_arco"],
            "coincidencias": matches,
            "prioridade": rule["prioridade"],
            "presenca_resumida": current.get("presenca"),
            "atuacao_local": current.get("atuacao_local"),
            "modo_avaliacao": mode,
            "marco_aparicao": (
                {
                    "estado": milestone.get("estado_marco"),
                    "nivel_atual": milestone.get("nivel_atual"),
                    "nivel_minimo": milestone.get("nivel_minimo"),
                    "condicao_id": milestone.get("condicao_id"),
                    "modo": milestone.get("modo"),
                    "motivo": milestone.get("motivo"),
                }
                if isinstance(milestone, dict)
                else None
            ),
            "avaliacao_id": f"scene:{scene_id}:contexto:presenca:{target}",
            "consulta_dirigida": f"python3 ferramentas/agentes.py mostrar {target}",
            "regra": (
                "candidato de presença exige avaliação narrativa; não estabelece "
                "presença, aparição, conhecimento ou ação"
            ),
        }
        rows.append((len(matches), int(rule["prioridade"]), binding_id, item))
    return rows, list(dict.fromkeys([*milestone_sources, STRATEGIC_INDEX.as_posix()]))


def _entry_rows(
    repo: Path,
    arc_info: dict[str, Any] | None,
    entries: list[tuple[str, dict[str, Any], list[str]]],
    *,
    scene_id: str,
) -> tuple[list[tuple[int, int, str, dict[str, Any]]], list[str]]:
    if not entries:
        return [], []
    if arc_info is None:
        raise ContextSceneError("entrada contextual exige Contrato de Arco")
    targets = [rule["alvo"] for _, rule, _ in entries]
    try:
        checked = aliados_contextuais.gates(repo, targets, arc_info=arc_info)
    except aliados_contextuais.AllyContextError as exc:
        raise ContextSceneError(str(exc)) from exc
    rows: list[tuple[int, int, str, dict[str, Any]]] = []
    for binding_id, rule, matches in entries:
        entry_id = rule["alvo"]
        gate = checked["resultados"].get(entry_id)
        if not isinstance(gate, dict):
            raise ContextSceneError(f"gate contextual ausente para aliado {entry_id}")
        if not gate.get("permitido"):
            continue
        item = {
            "id": entry_id,
            "binding_id": binding_id,
            "tipo": "entrada",
            "entrada_id": entry_id,
            "nome": gate["nome"],
            "coincidencias": matches,
            "prioridade": rule["prioridade"],
            "ordem": gate["ordem"],
            "nivel_atual": gate["nivel_atual"],
            "nivel_minimo": gate["nivel_minimo"],
            "modo_avaliacao": "avaliar_entrada_organica",
            "avaliacao_id": f"scene:{scene_id}:contexto:entrada:{entry_id}",
            "consulta_dirigida": f"python3 ferramentas/entradas.py mostrar {entry_id}",
            "regra": (
                "candidato de entrada significa apenas que a janela temporal, a ordem, "
                "o arco e o contexto permitem avaliar uma aparição orgânica; não confirma presença"
            ),
        }
        rows.append((len(matches), int(rule["prioridade"]), binding_id, item))
    return rows, checked["fontes_lidas"]


def _operation_rows(
    arc_info: dict[str, Any] | None,
    entries: list[tuple[str, dict[str, Any], list[str]]],
    *,
    scene_id: str,
) -> list[tuple[int, int, str, dict[str, Any]]]:
    if not entries:
        return []
    if arc_info is None:
        raise ContextSceneError("operação contextual exige Contrato de Arco")
    lines = arc_info["linhas_operacionais"]
    rows: list[tuple[int, int, str, dict[str, Any]]] = []
    for binding_id, rule, matches in entries:
        line_id = rule["alvo"]
        line = lines.get(line_id)
        if not isinstance(line, dict):
            raise ContextSceneError(
                f"linha operacional contextual não existe no arco atual: {line_id}"
            )
        item = {
            "id": line_id,
            "binding_id": binding_id,
            "tipo": "operacao",
            "linha_id": line_id,
            "objetivo": line["objetivo"],
            "executores": list(line["executores"]),
            "coincidencias": matches,
            "prioridade": rule["prioridade"],
            "modo_avaliacao": "avaliar_linha_operacional",
            "avaliacao_id": f"scene:{scene_id}:contexto:operacao:{line_id}",
            "consulta_dirigida": f"python3 ferramentas/arcos.py linha {line_id}",
            "regra": (
                "candidato operacional indica que uma necessidade estratégica pode aproveitar "
                "a cena; não escolhe executor, método, alvo nem ação"
            ),
        }
        rows.append((len(matches), int(rule["prioridade"]), binding_id, item))
    return rows


def _direction_rows(
    repo: Path,
    entries: list[tuple[str, dict[str, Any], list[str]]],
    *,
    scene_id: str,
) -> tuple[list[tuple[int, int, str, dict[str, Any]]], list[str]]:
    if not entries:
        return [], []
    state = load_directions_state(repo)
    directions = state["direcoes"]
    rows: list[tuple[int, int, str, dict[str, Any]]] = []
    for binding_id, rule, matches in entries:
        direction_id = rule["alvo"]
        current = directions.get(direction_id)
        if not isinstance(current, dict):
            raise ContextSceneError(
                f"estado não contém direção contextual: {direction_id}"
            )
        if current.get("estado") != "ativa":
            continue
        milestone = _text(
            current.get("marco_atual"), f"estado_direcoes.{direction_id}.marco_atual"
        )
        item = {
            "id": direction_id,
            "binding_id": binding_id,
            "tipo": "direcao",
            "direcao_id": direction_id,
            "papel": "restricao_destino",
            "executavel": False,
            "marco_atual": milestone,
            "coincidencias": matches,
            "prioridade": rule["prioridade"],
            "modo_avaliacao": "avaliar_sustentacao_do_marco",
            "avaliacao_id": f"scene:{scene_id}:contexto:direcao:{direction_id}",
            "consulta_dirigida": f"python3 ferramentas/direcoes.py avaliar-destino {direction_id}",
            "regra": (
                "candidato de direção aponta uma restrição de destino: avaliar se fatos já canônicos "
                "sustentam o marco atual; não escolhe executor/ação/método e não avança a direção"
            ),
        }
        rows.append((len(matches), int(rule["prioridade"]), binding_id, item))
    return rows, [DIRECTIONS_STATE.as_posix()]


def _take(
    rows: list[tuple[int, int, str, dict[str, Any]]], limit: int
) -> list[tuple[int, int, str, dict[str, Any]]]:
    rows.sort(key=lambda row: (-row[0], -row[1], row[2]))
    return rows[:limit]


def select_candidates(
    repo: Path,
    tags: Iterable[Any] | None,
    *,
    scene_id: str,
    exclude_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Pré-seleciona presença + operação + direção sem abrir fragmentos narrativos."""
    normalized = normalize_tags(tags)
    empty = {
        "presencas": [],
        "entradas": [],
        "operacoes": [],
        "direcoes": [],
        "candidatos": [],
    }
    if not normalized:
        return {
            "tags": [],
            **empty,
            "arco": {"aplicado": False, "bloqueados": 0, "bloqueados_por_tipo": {}},
            "fontes_lidas": [],
            "regra": "sem tags contextuais, nenhuma descoberta inversa é executada",
        }

    router = load_router(repo)
    budget = router["orcamento"]
    if len(normalized) > budget["max_tags_por_cena"]:
        raise ContextSceneError(
            f"roteador permite no máximo {budget['max_tags_por_cena']} tags por cena"
        )

    prefiltered = _prefilter(router, set(normalized), set(exclude_ids or []))
    if not prefiltered:
        return {
            "tags": normalized,
            **empty,
            "arco": {"aplicado": False, "bloqueados": 0, "bloqueados_por_tipo": {}},
            "fontes_lidas": [ROUTER.as_posix()],
            "regra": "nenhuma afinidade contextual atingiu o limiar mínimo",
        }

    kept, arc_meta, arc_sources, arc_info = _filter_by_arc(repo, prefiltered)
    if not kept:
        return {
            "tags": normalized,
            **empty,
            "arco": arc_meta,
            "fontes_lidas": [ROUTER.as_posix(), *arc_sources],
            "regra": "afinidades encontradas, mas nenhuma está habilitada no arco atual",
        }

    by_type: dict[str, list[tuple[str, dict[str, Any], list[str]]]] = {
        kind: [] for kind in VALID_TYPES
    }
    for entry in kept:
        by_type[entry[1]["tipo"]].append(entry)

    presence_rows, presence_sources = _presence_rows(
        repo, by_type["presenca"], scene_id=scene_id, arc_info=arc_info
    )
    entry_rows, entry_sources = _entry_rows(
        repo, arc_info, by_type["entrada"], scene_id=scene_id
    )
    operation_rows = _operation_rows(
        arc_info, by_type["operacao"], scene_id=scene_id
    )
    direction_rows, direction_sources = _direction_rows(
        repo, by_type["direcao"], scene_id=scene_id
    )

    selected_rows: list[tuple[int, int, str, dict[str, Any]]] = []
    for kind, rows in (
        ("presenca", presence_rows),
        ("entrada", entry_rows),
        ("operacao", operation_rows),
        ("direcao", direction_rows),
    ):
        selected_rows.extend(_take(rows, int(budget[TYPE_LIMIT_FIELDS[kind]])))

    selected_rows.sort(
        key=lambda row: (-row[0], -row[1], TYPE_ORDER[row[3]["tipo"]], row[2])
    )
    selected_rows = selected_rows[: int(budget["max_candidatos_total"])]
    candidates = [row[3] for row in selected_rows]
    presences = [item for item in candidates if item["tipo"] == "presenca"]
    entries = [item for item in candidates if item["tipo"] == "entrada"]
    operations = [item for item in candidates if item["tipo"] == "operacao"]
    directions = [item for item in candidates if item["tipo"] == "direcao"]

    return {
        "tags": normalized,
        "presencas": presences,
        "entradas": entries,
        "operacoes": operations,
        "direcoes": directions,
        "candidatos": candidates,
        "arco": arc_meta,
        "fontes_lidas": list(
            dict.fromkeys(
                [
                    ROUTER.as_posix(),
                    *arc_sources,
                    *presence_sources,
                    *entry_sources,
                    *direction_sources,
                ]
            )
        ),
        "regra": (
            "Python pré-seleciona presença, entrada de aliado, linha operacional e direção; presença antagonista "
            "também precisa passar pelo marco mínimo de aparição. Cada item é somente obrigação de avaliar. Nenhuma presença/entrada é estabelecida, nenhuma "
            "operação é executada e nenhuma direção avança automaticamente."
        ),
    }
