#!/usr/bin/env python3
"""Contrato operacional de arcos acima do Mundo Vivo.

A camada responde duas perguntas pequenas e determinísticas:

1. esta peça pertence à parte corrente da crônica?
2. onde está a fonte especializada que deve ser consultada se ela se tornar relevante?

O contrato de arco é **orquestrador**, não depósito narrativo. Ele guarda IDs,
guardrails e referências para fontes já existentes; nunca copia plano detalhado,
recursos, restrições, presença, marcos ou prosa de agente. A API resolve os IDs
nos índices especializados e devolve apenas ponteiros. Fragmentos individuais
continuam fechados até uma necessidade concreta.

A camada não executa NPC, não avança direção, não introduz aliado e não cria
fatos. Transições de arco são explícitas, rastreáveis e só podem seguir o próximo
arco declarado.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

import metodos_agentes

INDEX = Path("narrador/arcos/index.yaml")
STATE = Path("narrador/arcos/estado.yaml")
ARCS_DIR = Path("narrador/arcos")
STRATEGIC_INDEX = Path("narrador/agentes/index.yaml")
ENTRIES_INDEX = Path("narrador/entradas/index.yaml")
DIRECTIONS_INDEX = Path("narrador/direcoes/index.yaml")

ARC_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,95}$")
PIECE_ID_RE = ARC_ID_RE
VALID_GROUPS = {"antagonistas", "aliados", "direcoes"}
REFERENCE_INDEXES = {
    "antagonistas": (STRATEGIC_INDEX, "schema_agentes", 2, "agentes"),
    "aliados": (ENTRIES_INDEX, "schema_entradas", 1, "candidatos"),
    "direcoes": (DIRECTIONS_INDEX, "schema_direcoes", 1, "direcoes"),
}
VALID_SOURCE_TYPES = {"documento_reservado"}
MAX_TRANSITIONS = 32
MAX_CONTRACT_BYTES = 8192
MAX_ORCHESTRATED_SOURCES = 8
MAX_OPERATIONAL_LINES = 12
MAX_LINE_EXECUTORS = 6


class ArcContractError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise ArcContractError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ArcContractError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ArcContractError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ArcContractError(f"{label} deve ser texto não vazio")
    return value.strip()


def _id(value: Any, label: str) -> str:
    value = _text(value, label)
    if not PIECE_ID_RE.fullmatch(value):
        raise ArcContractError(f"{label} possui ID inválido: {value}")
    return value


def _repo_rel(value: Any, label: str) -> str:
    value = _text(value, label)
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise ArcContractError(f"{label} deve ser caminho relativo dentro do repositório")
    return path.as_posix()


def _agent_with_details(
    repo: Path,
    agent_id: str,
    meta: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Recompõe detalhe opcional sem impor o schema completo a fixtures de arco."""
    source = _repo_rel(meta.get("arquivo"), f"agentes.{agent_id}.arquivo")
    data = _map(_load(repo / source), source)
    sources = [source]
    pointer = data.get("detalhes_operacionais")
    if pointer is None:
        return data, sources
    pointer = _map(pointer, f"{agent_id}.detalhes_operacionais")
    detail_source = _repo_rel(
        pointer.get("arquivo"), f"{agent_id}.detalhes_operacionais.arquivo"
    )
    detail = _map(_load(repo / detail_source), detail_source)
    if detail.get("agente_id") != agent_id:
        raise ArcContractError(f"detalhes operacionais divergem do agente: {agent_id}")
    sections = _map(detail.get("secoes"), f"{agent_id}.detalhes.secoes")
    declared = set(_list(pointer.get("secoes"), f"{agent_id}.detalhes_operacionais.secoes"))
    if set(sections) != declared:
        raise ArcContractError(f"seções de detalhe divergem do fragmento-base: {agent_id}")
    data = {**data, **sections}
    sources.append(detail_source)
    return data, sources


def _strict_keys(data: dict[str, Any], allowed: set[str], label: str) -> None:
    extra = set(data) - allowed
    if extra:
        raise ArcContractError(f"{label} contém campos não permitidos no orquestrador: {', '.join(sorted(extra))}")


def _atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
        handle.flush()
        os.fsync(handle.fileno())
        tmp = Path(handle.name)
    os.replace(tmp, path)


def load_index(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / INDEX), INDEX.as_posix())
    if data.get("schema_arcos") != 1:
        raise ArcContractError("índice de arcos deve usar schema_arcos: 1")
    if data.get("natureza") != "roteador_reservado":
        raise ArcContractError("índice de arcos deve ter natureza: roteador_reservado")
    arcs = _map(data.get("arcos"), "arcos")
    if not arcs:
        raise ArcContractError("índice de arcos não pode ser vazio")
    seen_order: set[int] = set()
    files: set[str] = set()
    for arc_id, raw in arcs.items():
        arc_id = _id(arc_id, "id de arco")
        meta = _map(raw, f"arcos.{arc_id}")
        _text(meta.get("titulo"), f"arcos.{arc_id}.titulo")
        order = meta.get("ordem")
        if not isinstance(order, int) or isinstance(order, bool) or order < 1:
            raise ArcContractError(f"arcos.{arc_id}.ordem deve ser inteiro >= 1")
        if order in seen_order:
            raise ArcContractError(f"ordem de arco duplicada: {order}")
        seen_order.add(order)
        raw_file = _text(meta.get("arquivo"), f"arcos.{arc_id}.arquivo")
        expected = (ARCS_DIR / f"{arc_id}.yaml").as_posix()
        if raw_file != expected:
            raise ArcContractError(f"arcos.{arc_id}.arquivo deve ser {expected}")
        if raw_file in files:
            raise ArcContractError(f"arquivo de arco duplicado: {raw_file}")
        files.add(raw_file)
        next_id = meta.get("proximo")
        if next_id is not None:
            _id(next_id, f"arcos.{arc_id}.proximo")
    for arc_id, meta in arcs.items():
        next_id = meta.get("proximo")
        if next_id is not None and next_id not in arcs:
            raise ArcContractError(f"arcos.{arc_id}.proximo referencia arco inexistente: {next_id}")
        if next_id is not None and arcs[next_id]["ordem"] <= meta["ordem"]:
            raise ArcContractError(f"arcos.{arc_id}.proximo deve avançar a ordem da crônica")
    return data


def load_state(repo: Path, index: dict[str, Any] | None = None) -> dict[str, Any]:
    index = index or load_index(repo)
    data = _map(_load(repo / STATE), STATE.as_posix())
    if data.get("schema_estado_arcos") != 2:
        raise ArcContractError("estado de arcos deve usar schema_estado_arcos: 2")
    if data.get("natureza") != "controle_reservado":
        raise ArcContractError("estado de arcos deve ter natureza: controle_reservado")
    current = _id(data.get("arco_atual"), "arcos.arco_atual")
    if current not in index["arcos"]:
        raise ArcContractError(f"arco_atual não existe no índice: {current}")
    if data.get("estado") != "ativo":
        raise ArcContractError("arco atual deve estar ativo")
    history = _list(data.get("historico_transicoes"), "historico_transicoes")
    if len(history) > MAX_TRANSITIONS:
        raise ArcContractError("histórico de transições de arco excedeu o teto")
    for i, item in enumerate(history):
        item = _map(item, f"historico_transicoes[{i}]")
        _id(item.get("de"), f"historico_transicoes[{i}].de")
        _id(item.get("para"), f"historico_transicoes[{i}].para")
        _id(item.get("marco"), f"historico_transicoes[{i}].marco")
        _text(item.get("origem"), f"historico_transicoes[{i}].origem")
        _text(item.get("nota"), f"historico_transicoes[{i}].nota")
    return data


def _condition(value: Any, label: str) -> dict[str, str]:
    data = _map(value, label)
    _strict_keys(data, {"tipo", "marcador", "fonte"}, label)
    marker = _id(data.get("marcador"), f"{label}.marcador")
    source = _repo_rel(data.get("fonte"), f"{label}.fonte")
    kind = _text(data.get("tipo"), f"{label}.tipo")
    if kind not in {"fato_canonico", "marco_direcao", "marco_explicito"}:
        raise ArcContractError(f"{label}.tipo inválido: {kind}")
    return {"tipo": kind, "marcador": marker, "fonte": source}


def _orchestration(value: Any, label: str) -> dict[str, Any]:
    data = _map(value, label)
    _strict_keys(data, {"fontes", "plano_mestre"}, label)
    sources = _map(data.get("fontes"), f"{label}.fontes")
    if not sources or len(sources) > MAX_ORCHESTRATED_SOURCES:
        raise ArcContractError(f"{label}.fontes deve ter entre 1 e {MAX_ORCHESTRATED_SOURCES} referências")
    normalized_sources: dict[str, dict[str, str]] = {}
    for source_id, raw in sources.items():
        source_id = _id(source_id, f"{label}.fontes.id")
        meta = _map(raw, f"{label}.fontes.{source_id}")
        _strict_keys(meta, {"tipo", "arquivo"}, f"{label}.fontes.{source_id}")
        kind = _text(meta.get("tipo"), f"{label}.fontes.{source_id}.tipo")
        if kind not in VALID_SOURCE_TYPES:
            raise ArcContractError(f"{label}.fontes.{source_id}.tipo inválido: {kind}")
        normalized_sources[source_id] = {
            "tipo": kind,
            "arquivo": _repo_rel(meta.get("arquivo"), f"{label}.fontes.{source_id}.arquivo"),
        }

    master = _map(data.get("plano_mestre"), f"{label}.plano_mestre")
    _strict_keys(master, {"agente", "objetivo", "referencia"}, f"{label}.plano_mestre")
    agent = _id(master.get("agente"), f"{label}.plano_mestre.agente")
    objective = _id(master.get("objetivo"), f"{label}.plano_mestre.objetivo")
    reference = _id(master.get("referencia"), f"{label}.plano_mestre.referencia")
    if reference not in normalized_sources:
        raise ArcContractError(f"{label}.plano_mestre.referencia inexistente: {reference}")
    return {
        "fontes": normalized_sources,
        "plano_mestre": {"agente": agent, "objetivo": objective, "referencia": reference},
    }


def load_contract(repo: Path, arc_id: str, index: dict[str, Any] | None = None) -> dict[str, Any]:
    arc_id = _id(arc_id, "arc_id")
    index = index or load_index(repo)
    if arc_id not in index["arcos"]:
        raise ArcContractError(f"arco inexistente: {arc_id}")
    path = ARCS_DIR / f"{arc_id}.yaml"
    file_path = repo / path
    try:
        size = file_path.stat().st_size
    except FileNotFoundError as exc:
        raise ArcContractError(f"arquivo inexistente: {path}") from exc
    if size > MAX_CONTRACT_BYTES:
        raise ArcContractError(f"{arc_id}: contrato excede {MAX_CONTRACT_BYTES} bytes; detalhe deve permanecer nas fontes especializadas")
    data = _map(_load(file_path), path.as_posix())
    if data.get("schema_arco") != 4:
        raise ArcContractError(f"{arc_id}: contrato deve usar schema_arco: 4")
    if data.get("natureza") != "reservado":
        raise ArcContractError(f"{arc_id}: contrato deve ter natureza: reservado")
    if data.get("estatuto") != "contrato_orquestrador_de_arco":
        raise ArcContractError(f"{arc_id}: estatuto inválido")
    _strict_keys(
        data,
        {"schema_arco", "natureza", "estatuto", "id", "titulo", "principio", "inicio", "termino", "orquestracao", "habilitacoes", "linhas_operacionais"},
        arc_id,
    )
    if data.get("id") != arc_id:
        raise ArcContractError(f"{arc_id}: id do contrato diverge do arquivo")
    title = _text(data.get("titulo"), f"{arc_id}.titulo")
    if title != index["arcos"][arc_id]["titulo"]:
        raise ArcContractError(f"{arc_id}: título diverge do índice")
    _text(data.get("principio"), f"{arc_id}.principio")
    _condition(data.get("inicio"), f"{arc_id}.inicio")
    _condition(data.get("termino"), f"{arc_id}.termino")
    _orchestration(data.get("orquestracao"), f"{arc_id}.orquestracao")

    enabled = _map(data.get("habilitacoes"), f"{arc_id}.habilitacoes")
    _strict_keys(enabled, {"politica_nao_listados", *VALID_GROUPS}, f"{arc_id}.habilitacoes")
    if enabled.get("politica_nao_listados") != "bloqueados":
        raise ArcContractError(f"{arc_id}: política de não listados deve ser bloqueados")
    normalized_enabled: dict[str, list[str]] = {}
    for group in VALID_GROUPS:
        values = [
            _id(v, f"{arc_id}.habilitacoes.{group}")
            for v in _list(enabled.get(group), f"{arc_id}.habilitacoes.{group}")
        ]
        if len(values) != len(set(values)):
            raise ArcContractError(f"{arc_id}.habilitacoes.{group} não pode conter duplicatas")
        normalized_enabled[group] = values

    lines = _map(data.get("linhas_operacionais"), f"{arc_id}.linhas_operacionais")
    if len(lines) > MAX_OPERATIONAL_LINES:
        raise ArcContractError(
            f"{arc_id}.linhas_operacionais excede o teto de {MAX_OPERATIONAL_LINES}"
        )
    orchestration = _orchestration(data.get("orquestracao"), f"{arc_id}.orquestracao")
    allowed_executors = set(normalized_enabled["antagonistas"]) | {
        orchestration["plano_mestre"]["agente"]
    }
    objectives: set[str] = set()
    for line_id, raw_line in lines.items():
        line_id = _id(line_id, f"{arc_id}.linhas_operacionais.id")
        line = _map(raw_line, f"{arc_id}.linhas_operacionais.{line_id}")
        _strict_keys(
            line,
            {"objetivo", "executores", "referencia"},
            f"{arc_id}.linhas_operacionais.{line_id}",
        )
        objective = _id(
            line.get("objetivo"), f"{arc_id}.linhas_operacionais.{line_id}.objetivo"
        )
        if objective in objectives:
            raise ArcContractError(
                f"{arc_id}.linhas_operacionais possui objetivo duplicado: {objective}"
            )
        objectives.add(objective)
        reference = _id(
            line.get("referencia"), f"{arc_id}.linhas_operacionais.{line_id}.referencia"
        )
        if reference not in orchestration["fontes"]:
            raise ArcContractError(
                f"{arc_id}.linhas_operacionais.{line_id}.referencia inexistente: {reference}"
            )
        executors = [
            _id(value, f"{arc_id}.linhas_operacionais.{line_id}.executores")
            for value in _list(
                line.get("executores"), f"{arc_id}.linhas_operacionais.{line_id}.executores"
            )
        ]
        if not executors or len(executors) > MAX_LINE_EXECUTORS:
            raise ArcContractError(
                f"{arc_id}.linhas_operacionais.{line_id}.executores deve ter entre 1 e {MAX_LINE_EXECUTORS} IDs"
            )
        if len(executors) != len(set(executors)):
            raise ArcContractError(
                f"{arc_id}.linhas_operacionais.{line_id}.executores não pode conter duplicatas"
            )
        invalid = [executor for executor in executors if executor not in allowed_executors]
        if invalid:
            raise ArcContractError(
                f"{arc_id}.linhas_operacionais.{line_id}: executor não habilitado no arco: "
                + ", ".join(invalid)
            )
    overlap = sorted(set(lines) & set(normalized_enabled["direcoes"]))
    if overlap:
        raise ArcContractError(
            f"{arc_id}: direção canônica não pode também ser linha operacional: "
            + ", ".join(overlap)
        )
    return data


def current(repo: Path) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    contract = load_contract(repo, state["arco_atual"], index)
    arc_id = state["arco_atual"]
    orchestration = contract["orquestracao"]
    master = orchestration["plano_mestre"]
    master_source = orchestration["fontes"][master["referencia"]]["arquivo"]
    return {
        "id": arc_id,
        "titulo": contract["titulo"],
        "ordem": index["arcos"][arc_id]["ordem"],
        "proximo": index["arcos"][arc_id].get("proximo"),
        "inicio": contract["inicio"],
        "termino": contract["termino"],
        "plano_mestre": {
            "agente": master["agente"],
            "objetivo": master["objetivo"],
            "referencia": master["referencia"],
            "fonte": master_source,
        },
        "fontes_orquestradas": orchestration["fontes"],
        "linhas_operacionais": contract["linhas_operacionais"],
        "habilitacoes": contract["habilitacoes"],
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), (ARCS_DIR / f"{arc_id}.yaml").as_posix()],
    }


def eligibility(repo: Path, group: str, piece_id: str) -> dict[str, Any]:
    if group not in VALID_GROUPS:
        raise ArcContractError(f"grupo de arco inválido: {group}")
    piece_id = _id(piece_id, "piece_id")
    info = current(repo)
    allowed = piece_id in set(info["habilitacoes"][group])
    return {
        "permitido": allowed,
        "grupo": group,
        "id": piece_id,
        "arco_id": info["id"],
        "titulo": info["titulo"],
        "motivo": "habilitado_no_arco" if allowed else "nao_listado_bloqueado_pelo_arco",
        "politica_nao_listados": info["habilitacoes"]["politica_nao_listados"],
        "fontes_lidas": info["fontes_lidas"],
    }



def operational_lines(repo: Path) -> dict[str, Any]:
    """Lista as necessidades estratégicas ativas do arco sem abrir fontes narrativas."""
    info = current(repo)
    lines: list[dict[str, Any]] = []
    for line_id, line in info["linhas_operacionais"].items():
        reference = line["referencia"]
        source = info["fontes_orquestradas"][reference]["arquivo"]
        lines.append(
            {
                "id": line_id,
                "objetivo": line["objetivo"],
                "executores": list(line["executores"]),
                "referencia": reference,
                "fonte_estrategica": source,
            }
        )
    return {
        "ok": True,
        "arco_id": info["id"],
        "titulo": info["titulo"],
        "linhas": lines,
        "regra": (
            "linha operacional é necessidade estratégica habilitada pelo arco; "
            "não é ação, ordem executada nem fato canônico"
        ),
        "fontes_lidas": info["fontes_lidas"],
    }


def resolve_operational_line(
    repo: Path, line_id: str, *, executor: str | None = None
) -> dict[str, Any]:
    """Resolve uma linha e opcionalmente checa se um executor pode servi-la.

    O caminho é deliberadamente barato: somente os três controles do arco. A
    validação de manutenção garante que todos os executores declarados existem e
    pertencem ao conjunto estratégico permitido.
    """
    line_id = _id(line_id, "line_id")
    info = current(repo)
    line = info["linhas_operacionais"].get(line_id)
    if not isinstance(line, dict):
        return {
            "permitida": False,
            "linha_id": line_id,
            "arco_id": info["id"],
            "titulo": info["titulo"],
            "motivo": "linha_nao_declarada_no_arco",
            "fontes_lidas": info["fontes_lidas"],
        }
    reference = line["referencia"]
    source = info["fontes_orquestradas"][reference]["arquivo"]
    result: dict[str, Any] = {
        "permitida": True,
        "linha_id": line_id,
        "arco_id": info["id"],
        "titulo": info["titulo"],
        "objetivo": line["objetivo"],
        "executores": list(line["executores"]),
        "referencia": reference,
        "fonte_estrategica": source,
        "motivo": "linha_operacional_habilitada_no_arco",
        "regra": (
            "a linha define o problema estratégico; o agente ainda decide como agir "
            "segundo seu próprio fragmento e restrições"
        ),
        "fontes_lidas": info["fontes_lidas"],
    }
    if executor is not None:
        executor_id = _id(executor, "executor")
        result["executor_consultado"] = executor_id
        result["executor_permitido"] = executor_id in set(line["executores"])
        result["motivo_executor"] = (
            "executor_habilitado_para_linha"
            if result["executor_permitido"]
            else "executor_nao_habilitado_para_linha"
        )
    return result


def resolve_agent_methods(
    repo: Path, line_id: str, *, executor: str
) -> dict[str, Any]:
    """Abre exatamente um fragmento de agente e devolve seus métodos para a linha.

    A linha e o executor são validados primeiro só com os controles do arco. Se o
    executor não estiver autorizado, o fragmento nem é aberto. Métodos são
    repertório de abordagem, não ação escolhida nem fato canônico.
    """
    gate = resolve_operational_line(repo, line_id, executor=executor)
    if not gate.get("permitida") or not gate.get("executor_permitido"):
        return {
            **gate,
            "metodos": [],
            "fonte_agente": None,
            "regra_metodos": (
                "sem executor autorizado não há consulta ao fragmento do agente"
            ),
        }

    executor_id = gate["executor_consultado"]
    agents = _load_reference_index(repo, STRATEGIC_INDEX, "schema_agentes", 2, "agentes")
    meta = agents.get(executor_id)
    if not isinstance(meta, dict):
        raise ArcContractError(f"executor inexistente no índice de agentes: {executor_id}")
    source = _repo_rel(meta.get("arquivo"), f"agentes.{executor_id}.arquivo")
    try:
        agent, agent_sources = _agent_with_details(repo, executor_id, meta)
        methods = metodos_agentes.for_line(
            agent, line_id, expected_agent_id=executor_id
        )
    except metodos_agentes.AgentMethodError as exc:
        raise ArcContractError(str(exc)) from exc
    return {
        **gate,
        "metodos": methods,
        "fonte_agente": source,
        "motivo_metodos": (
            "traducao_operacional_disponivel" if methods else "executor_sem_traducao_operacional"
        ),
        "regra_metodos": (
            "método é repertório de abordagem do agente para a linha; presença, contexto, "
            "restrições e decisão narrativa ainda governam se e como algo acontece"
        ),
        "fontes_lidas": list(
            dict.fromkeys(
                [*gate["fontes_lidas"], STRATEGIC_INDEX.as_posix(), *agent_sources]
            )
        ),
    }

def _load_reference_index(
    repo: Path,
    path: Path,
    schema_key: str,
    schema_value: int,
    field: str,
) -> dict[str, Any]:
    data = _map(_load(repo / path), path.as_posix())
    if data.get(schema_key) != schema_value:
        raise ArcContractError(f"{path}: schema inesperado")
    return _map(data.get(field), f"{path}:{field}")


def _piece_meta(repo: Path, group: str, piece_id: str) -> tuple[dict[str, Any], str]:
    path, schema_key, schema_value, field = REFERENCE_INDEXES[group]
    entries = _load_reference_index(repo, path, schema_key, schema_value, field)
    raw = entries.get(piece_id)
    if not isinstance(raw, dict):
        singular = {"antagonistas": "antagonista", "aliados": "aliado", "direcoes": "direção"}[group]
        raise ArcContractError(f"{singular} inexistente: {piece_id}")
    name = _text(raw.get("nome"), f"{group}.{piece_id}.nome")
    file_path = _repo_rel(raw.get("arquivo"), f"{group}.{piece_id}.arquivo")
    return {"id": piece_id, "nome": name, "arquivo": file_path}, path.as_posix()


def resolve_piece(repo: Path, group: str, piece_id: str) -> dict[str, Any]:
    """Resolve um item habilitado para sua fonte sem abrir o fragmento.

    Se o arco bloquear a peça, para só nos três controles do arco. Se permitir,
    lê apenas o índice especializado daquela classe e devolve o caminho do
    fragmento que *poderá* ser aberto depois por necessidade concreta.
    """
    gate = eligibility(repo, group, piece_id)
    if not gate["permitido"]:
        return {
            **gate,
            "fonte_especializada": None,
            "referencias_estrategicas": {},
        }
    meta, index_source = _piece_meta(repo, group, piece_id)
    info = current(repo)
    strategic_refs: dict[str, str] = {}
    if group == "antagonistas":
        strategic_refs["plano_mestre"] = info["plano_mestre"]["fonte"]
        if "marcos_antagonistas" in info["fontes_orquestradas"]:
            strategic_refs["marcos_antagonistas"] = info["fontes_orquestradas"]["marcos_antagonistas"]["arquivo"]
    return {
        **gate,
        "nome": meta["nome"],
        "fonte_especializada": meta["arquivo"],
        "referencias_estrategicas": strategic_refs,
        "regra": "ponteiros apenas; nenhum fragmento narrativo foi aberto",
        "fontes_lidas": list(dict.fromkeys([*gate["fontes_lidas"], index_source])),
    }


def manifest(repo: Path) -> dict[str, Any]:
    """Monta o mapa derivado do arco atual sem abrir nenhum fragmento narrativo."""
    info = current(repo)
    groups: dict[str, list[dict[str, str]]] = {}
    sources = list(info["fontes_lidas"])
    for group in sorted(VALID_GROUPS):
        items: list[dict[str, str]] = []
        path, schema_key, schema_value, field = REFERENCE_INDEXES[group]
        entries = _load_reference_index(repo, path, schema_key, schema_value, field)
        sources.append(path.as_posix())
        for piece_id in info["habilitacoes"][group]:
            raw = entries.get(piece_id)
            if not isinstance(raw, dict):
                singular = {"antagonistas": "antagonista", "aliados": "aliado", "direcoes": "direção"}[group]
                raise ArcContractError(f"{info['id']}: {singular} inexistente: {piece_id}")
            items.append(
                {
                    "id": piece_id,
                    "nome": _text(raw.get("nome"), f"{group}.{piece_id}.nome"),
                    "arquivo": _repo_rel(raw.get("arquivo"), f"{group}.{piece_id}.arquivo"),
                }
            )
        groups[group] = items
    return {
        "ok": True,
        "arco_id": info["id"],
        "titulo": info["titulo"],
        "plano_mestre": info["plano_mestre"],
        "fontes_orquestradas": info["fontes_orquestradas"],
        "linhas_operacionais": operational_lines(repo)["linhas"],
        "habilitados": groups,
        "papeis": {
            "arco": "espaco_estrategico_permitido",
            "direcoes": "restricoes_destino_nao_executaveis",
            "linhas_operacionais": "problemas_estrategicos_nao_acoes",
        },
        "regra": "manifesto derivado de ponteiros; conteúdo especializado permanece nas fontes originais",
        "fontes_lidas": list(dict.fromkeys(sources)),
    }


def validate(repo: Path, *, references: bool = True) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    contracts = {arc_id: load_contract(repo, arc_id, index) for arc_id in index["arcos"]}
    sources = [
        INDEX.as_posix(),
        STATE.as_posix(),
        *[(ARCS_DIR / f"{arc_id}.yaml").as_posix() for arc_id in index["arcos"]],
    ]

    if references:
        reference_indexes: dict[str, dict[str, Any]] = {}
        for group, (path, schema_key, schema_value, field) in REFERENCE_INDEXES.items():
            reference_indexes[group] = _load_reference_index(repo, path, schema_key, schema_value, field)
            sources.append(path.as_posix())
        agents = reference_indexes["antagonistas"]
        declared_lines: dict[str, tuple[str, set[str]]] = {}

        for arc_id, contract in contracts.items():
            for line_id, line in contract["linhas_operacionais"].items():
                if line_id in declared_lines:
                    other_arc = declared_lines[line_id][0]
                    raise ArcContractError(
                        f"linha operacional deve ter ID globalmente único: {line_id} aparece em {other_arc} e {arc_id}"
                    )
                declared_lines[line_id] = (arc_id, set(line["executores"]))
            orchestration = contract["orquestracao"]
            master = orchestration["plano_mestre"]["agente"]
            if master not in agents:
                raise ArcContractError(f"{arc_id}: agente do plano mestre inexistente: {master}")
            for source_id, source in orchestration["fontes"].items():
                source_path = source["arquivo"]
                if not (repo / source_path).is_file():
                    raise ArcContractError(f"{arc_id}.orquestracao.fontes.{source_id}: fonte inexistente: {source_path}")
            overlap = sorted(set(contract["linhas_operacionais"]) & set(contract["habilitacoes"]["direcoes"]))
            if overlap:
                raise ArcContractError(
                    f"{arc_id}: direção canônica não pode também ser linha operacional: "
                    + ", ".join(overlap)
                )
            for group in VALID_GROUPS:
                singular = {"antagonistas": "antagonista", "aliados": "aliado", "direcoes": "direção"}[group]
                for item in contract["habilitacoes"][group]:
                    meta = reference_indexes[group].get(item)
                    if not isinstance(meta, dict):
                        raise ArcContractError(f"{arc_id}: {singular} inexistente: {item}")
                    file_path = _repo_rel(meta.get("arquivo"), f"{arc_id}.{group}.{item}.arquivo")
                    if not (repo / file_path).is_file():
                        raise ArcContractError(f"{arc_id}: fonte de {singular} inexistente: {file_path}")
            for line_id, line in contract["linhas_operacionais"].items():
                for executor in line["executores"]:
                    if executor not in agents:
                        raise ArcContractError(
                            f"{arc_id}.linhas_operacionais.{line_id}: executor inexistente: {executor}"
                        )
                    try:
                        agent_data, agent_sources = _agent_with_details(
                            repo, executor, agents[executor]
                        )
                        agent_methods = metodos_agentes.from_agent(
                            agent_data, expected_agent_id=executor
                        )
                    except metodos_agentes.AgentMethodError as exc:
                        raise ArcContractError(str(exc)) from exc
                    sources.extend(agent_sources)
                    if line_id not in agent_methods:
                        raise ArcContractError(
                            f"{arc_id}.linhas_operacionais.{line_id}: executor {executor} "
                            "não possui tradução em metodos_operacionais"
                        )
            for condition_name in ("inicio", "termino"):
                source = contract[condition_name]["fonte"]
                if not (repo / source).is_file():
                    raise ArcContractError(f"{arc_id}.{condition_name}: fonte inexistente: {source}")

        # Manutenção fria: traduções existentes não podem apontar para linha inexistente
        # nem conceder uma linha a agente que o contrato não declarou como executor.
        checked_agent_ids: set[str] = set()
        for agent_id, meta in agents.items():
            if agent_id in checked_agent_ids:
                continue
            checked_agent_ids.add(agent_id)
            try:
                agent_data, agent_sources = _agent_with_details(repo, agent_id, meta)
                method_map = metodos_agentes.from_agent(
                    agent_data, expected_agent_id=agent_id
                )
                sources.extend(agent_sources)
            except metodos_agentes.AgentMethodError as exc:
                raise ArcContractError(str(exc)) from exc
            for line_id in method_map:
                declared = declared_lines.get(line_id)
                if declared is None:
                    raise ArcContractError(
                        f"{agent_id}.metodos_operacionais referencia linha inexistente: {line_id}"
                    )
                arc_id, executors = declared
                if agent_id not in executors:
                    raise ArcContractError(
                        f"{agent_id}.metodos_operacionais.{line_id}: agente não é executor declarado em {arc_id}"
                    )

    return {
        "ok": True,
        "arco_atual": state["arco_atual"],
        "quantidade_arcos": len(index["arcos"]),
        "transicoes_registradas": len(state["historico_transicoes"]),
        "fontes_lidas": list(dict.fromkeys(sources)),
    }


def transition(
    repo: Path,
    *,
    target: str,
    marker: str,
    origin: str,
    note: str,
) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    current_id = state["arco_atual"]
    current_contract = load_contract(repo, current_id, index)
    target = _id(target, "target")
    marker = _id(marker, "marker")
    origin = _text(origin, "origin")
    note = _text(note, "note")
    expected = index["arcos"][current_id].get("proximo")
    if expected is None:
        raise ArcContractError(f"{current_id} ainda não declara próximo arco")
    if target != expected:
        raise ArcContractError(f"transição inválida: {current_id} só pode avançar para {expected}")
    required_marker = current_contract["termino"]["marcador"]
    if marker != required_marker:
        raise ArcContractError(f"marco de término incorreto: esperado {required_marker}")
    next_contract = load_contract(repo, target, index)
    item = {"de": current_id, "para": target, "marco": marker, "origem": origin, "nota": note}
    state["historico_transicoes"].append(item)
    state["historico_transicoes"] = state["historico_transicoes"][-MAX_TRANSITIONS:]
    state["arco_atual"] = target
    _atomic(repo / STATE, state)
    return {
        "ok": True,
        "de": current_id,
        "para": target,
        "titulo": next_contract["titulo"],
        "transicao": item,
        "regra": "transição explícita apenas para o próximo arco declarado; nenhum fato narrativo é criado por este comando",
        "fontes_lidas": [
            INDEX.as_posix(),
            STATE.as_posix(),
            (ARCS_DIR / f"{current_id}.yaml").as_posix(),
            (ARCS_DIR / f"{target}.yaml").as_posix(),
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    check = sub.add_parser("checar")
    check.add_argument("grupo", choices=sorted(VALID_GROUPS))
    check.add_argument("id")
    resolve = sub.add_parser("resolver")
    resolve.add_argument("grupo", choices=sorted(VALID_GROUPS))
    resolve.add_argument("id")
    sub.add_parser("manifesto")
    sub.add_parser("linhas")
    line = sub.add_parser("linha")
    line.add_argument("id")
    line.add_argument("--executor")
    methods = sub.add_parser("metodos")
    methods.add_argument("id", help="ID da linha operacional")
    methods.add_argument("--executor", required=True)
    sub.add_parser("validar")
    move = sub.add_parser("transicionar")
    move.add_argument("--para", required=True)
    move.add_argument("--marco", required=True)
    move.add_argument("--origem", required=True)
    move.add_argument("--nota", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "status":
            result = current(repo)
        elif args.cmd == "checar":
            result = eligibility(repo, args.grupo, args.id)
        elif args.cmd == "resolver":
            result = resolve_piece(repo, args.grupo, args.id)
        elif args.cmd == "manifesto":
            result = manifest(repo)
        elif args.cmd == "linhas":
            result = operational_lines(repo)
        elif args.cmd == "linha":
            result = resolve_operational_line(repo, args.id, executor=args.executor)
        elif args.cmd == "metodos":
            result = resolve_agent_methods(repo, args.id, executor=args.executor)
        elif args.cmd == "validar":
            result = validate(repo)
        elif args.cmd == "transicionar":
            result = transition(repo, target=args.para, marker=args.marco, origin=args.origem, note=args.nota)
        else:
            raise ArcContractError(f"comando desconhecido: {args.cmd}")
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0
    except ArcContractError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
