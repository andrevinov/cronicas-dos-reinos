#!/usr/bin/env python3
"""Camada reservada de agentes autônomos.

Esta ferramenta não executa o mundo e não toma decisões narrativas. Ela oferece
duas operações baratas:

- ``mostrar``: abre apenas o índice e o fragmento do agente pedido;
- ``validar``: manutenção/CI que percorre todos os agentes e confere schema,
  referências, mobilidade e proveniência do conhecimento registrado.

A separação mantém a consulta em jogo fragmentada, enquanto a validação ampla
fica fora do caminho quente. Presença física e conhecimento de Ren são camadas
independentes: um agente pode estar ``presente_oculto`` sem que isso crie
conhecimento para o personagem.
"""
from __future__ import annotations

import argparse
import sys
import unicodedata
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

INDEX_PATH = Path("narrador/agentes/index.yaml")
AGENTS_DIR = Path("narrador/agentes")

VALID_TYPES = {"npc", "faccao", "instituicao"}
VALID_STATES = {"ativo", "latente", "inativo"}
VALID_PLAN_STATES = {
    "em_execucao",
    "aguardando_oportunidade",
    "requer_reavaliacao",
    "sem_plano_registrado",
}
VALID_PRESENCE_STATES = {
    "presente",
    "presente_oculto",
    "fora_da_area",
    "em_viagem",
    "indeterminado",
    "distribuida",
    "ancorada",
}
VALID_MOBILITY_STATES = {
    "sem_deslocamento_registrado",
    "chegada_planejada",
    "saida_planejada",
    "em_deslocamento",
    "nao_aplicavel",
}
VALID_LOCAL_ACTION_RULES = {
    "exige_presenca_fisica",
    "permite_rede",
    "estrutura_local",
    "depende_de_membros_presentes",
}
CONCRETE_PRESENCE_STATES = {
    "presente",
    "presente_oculto",
    "fora_da_area",
    "em_viagem",
}


class AgentValidationError(ValueError):
    """Erro de contrato da camada de agentes."""


def load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AgentValidationError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise AgentValidationError(f"YAML inválido em {path}: {exc}") from exc


def _normalize_lookup(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(
        "".join(ch.lower() if ch.isalnum() else " " for ch in text).split()
    )


def _normalize_evidence(value: str) -> str:
    return " ".join(str(value).split())


def _repo_path(repo: Path, raw: str, *, expected_prefix: Path | None = None) -> Path:
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        raise AgentValidationError(f"caminho fora do repositório: {raw}")
    if expected_prefix is not None:
        try:
            rel.relative_to(expected_prefix)
        except ValueError as exc:
            raise AgentValidationError(
                f"caminho {raw} deve permanecer sob {expected_prefix.as_posix()}"
            ) from exc
    return repo / rel


def _nonempty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentValidationError(f"{label} deve ser texto não vazio")
    return value.strip()


def _nullable_string(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _nonempty_string(value, label)


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list):
        raise AgentValidationError(f"{label} deve ser lista")
    result: list[str] = []
    for index, item in enumerate(value):
        result.append(_nonempty_string(item, f"{label}[{index}]"))
    return result


def load_index(repo: Path) -> dict[str, Any]:
    path = repo / INDEX_PATH
    data = load_yaml(path)
    if not isinstance(data, dict):
        raise AgentValidationError(f"{INDEX_PATH.as_posix()} deve conter um mapa")
    if data.get("schema_agentes") != 2:
        raise AgentValidationError("schema_agentes deve ser 2")
    if data.get("natureza") != "reservado":
        raise AgentValidationError("índice de agentes deve ter natureza: reservado")
    agents = data.get("agentes")
    if not isinstance(agents, dict) or not agents:
        raise AgentValidationError("índice deve possuir mapa não vazio em agentes")

    seen_files: set[str] = set()
    for agent_id, meta in agents.items():
        _nonempty_string(agent_id, "id do agente no índice")
        if not isinstance(meta, dict):
            raise AgentValidationError(f"agentes.{agent_id} deve ser mapa")
        _nonempty_string(meta.get("nome"), f"agentes.{agent_id}.nome")
        agent_type = _nonempty_string(meta.get("tipo"), f"agentes.{agent_id}.tipo")
        if agent_type not in VALID_TYPES:
            raise AgentValidationError(f"agentes.{agent_id}.tipo inválido: {agent_type}")
        state = _nonempty_string(meta.get("estado"), f"agentes.{agent_id}.estado")
        if state not in VALID_STATES:
            raise AgentValidationError(f"agentes.{agent_id}.estado inválido: {state}")
        presence = _nonempty_string(meta.get("presenca"), f"agentes.{agent_id}.presenca")
        if presence not in VALID_PRESENCE_STATES:
            raise AgentValidationError(f"agentes.{agent_id}.presenca inválida: {presence}")
        local_rule = _nonempty_string(meta.get("atuacao_local"), f"agentes.{agent_id}.atuacao_local")
        if local_rule not in VALID_LOCAL_ACTION_RULES:
            raise AgentValidationError(f"agentes.{agent_id}.atuacao_local inválida: {local_rule}")
        raw_path = _nonempty_string(meta.get("arquivo"), f"agentes.{agent_id}.arquivo")
        _repo_path(repo, raw_path, expected_prefix=AGENTS_DIR)
        if raw_path == INDEX_PATH.as_posix():
            raise AgentValidationError("índice não pode apontar para si mesmo")
        if raw_path in seen_files:
            raise AgentValidationError(f"arquivo de agente duplicado no índice: {raw_path}")
        seen_files.add(raw_path)
    return data


def resolve_agent(index: dict[str, Any], query: str) -> tuple[str, dict[str, Any]]:
    agents = index["agentes"]
    if query in agents:
        return query, agents[query]
    wanted = _normalize_lookup(query)
    matches: list[tuple[str, dict[str, Any]]] = []
    for agent_id, meta in agents.items():
        candidates = {_normalize_lookup(agent_id), _normalize_lookup(meta["nome"])}
        if wanted in candidates or any(wanted and wanted in candidate for candidate in candidates):
            matches.append((agent_id, meta))
    if not matches:
        raise AgentValidationError(f"agente não encontrado: {query}")
    if len(matches) > 1:
        names = ", ".join(agent_id for agent_id, _ in matches)
        raise AgentValidationError(f"consulta ambígua para {query!r}: {names}")
    return matches[0]


def local_eligibility(agent: dict[str, Any]) -> str:
    """Retorna sim/não/condicional sem consultar qualquer outro arquivo."""
    if agent.get("estado") != "ativo":
        return "nao"
    presence = (agent.get("presenca") or {}).get("estado")
    rule = (agent.get("atuacao_local") or {}).get("regra")
    if rule == "exige_presenca_fisica":
        return "sim" if presence in {"presente", "presente_oculto"} else "nao"
    if rule == "permite_rede":
        return "sim"
    if rule == "estrutura_local":
        return "sim" if presence in {"presente", "presente_oculto", "distribuida", "ancorada"} else "nao"
    if rule == "depende_de_membros_presentes":
        return "condicional"
    raise AgentValidationError(f"regra de atuação local inválida: {rule}")


def _validate_presence(repo: Path, agent_id: str, meta: dict[str, Any], data: dict[str, Any], *, source_set: set[str], check_sources: bool) -> None:
    presence = data.get("presenca")
    if not isinstance(presence, dict):
        raise AgentValidationError(f"{agent_id}.presenca deve ser mapa")
    reference = _nonempty_string(presence.get("referencia"), f"{agent_id}.presenca.referencia")
    if reference != "Ravens Bluff":
        raise AgentValidationError(f"{agent_id}.presenca.referencia deve ser Ravens Bluff nesta etapa")
    state = _nonempty_string(presence.get("estado"), f"{agent_id}.presenca.estado")
    if state not in VALID_PRESENCE_STATES:
        raise AgentValidationError(f"{agent_id}: presença inválida: {state}")
    if state != meta.get("presenca"):
        raise AgentValidationError(f"{agent_id}: presença diverge do índice")
    _nonempty_string(presence.get("detalhe"), f"{agent_id}.presenca.detalhe")
    source = _nullable_string(presence.get("fonte"), f"{agent_id}.presenca.fonte")
    evidence = _nullable_string(presence.get("evidencia"), f"{agent_id}.presenca.evidencia")
    if state in CONCRETE_PRESENCE_STATES:
        if not source or not evidence:
            raise AgentValidationError(f"{agent_id}: presença concreta {state} exige fonte e evidencia")
        if source not in source_set:
            raise AgentValidationError(f"{agent_id}: presença usa fonte não declarada: {source}")
        if check_sources:
            source_path = _repo_path(repo, source)
            if not source_path.is_file():
                raise AgentValidationError(f"{agent_id}: fonte canônica inexistente: {source}")
            source_text = _normalize_evidence(source_path.read_text(encoding="utf-8"))
            if _normalize_evidence(evidence) not in source_text:
                raise AgentValidationError(f"{agent_id}: presença não possui evidência localizável em {source}")
    elif source is not None or evidence is not None:
        if not source or not evidence:
            raise AgentValidationError(f"{agent_id}: fonte e evidencia de presença devem aparecer juntas")
        if source not in source_set:
            raise AgentValidationError(f"{agent_id}: presença usa fonte não declarada: {source}")


def _validate_mobility(agent_id: str, data: dict[str, Any]) -> None:
    mobility = data.get("mobilidade")
    if not isinstance(mobility, dict):
        raise AgentValidationError(f"{agent_id}.mobilidade deve ser mapa")
    state = _nonempty_string(mobility.get("estado"), f"{agent_id}.mobilidade.estado")
    if state not in VALID_MOBILITY_STATES:
        raise AgentValidationError(f"{agent_id}: mobilidade inválida: {state}")
    origin = _nullable_string(mobility.get("origem"), f"{agent_id}.mobilidade.origem")
    destination = _nullable_string(mobility.get("destino"), f"{agent_id}.mobilidade.destino")
    _nullable_string(mobility.get("prazo"), f"{agent_id}.mobilidade.prazo")
    if state in {"chegada_planejada", "em_deslocamento"} and not destination:
        raise AgentValidationError(f"{agent_id}: {state} exige destino")
    if state == "saida_planejada" and not origin:
        raise AgentValidationError(f"{agent_id}: saida_planejada exige origem")
    if state in {"sem_deslocamento_registrado", "nao_aplicavel"} and (origin is not None or destination is not None):
        raise AgentValidationError(f"{agent_id}: {state} não deve carregar origem/destino ativos")


def _validate_local_action(agent_id: str, meta: dict[str, Any], data: dict[str, Any]) -> None:
    local = data.get("atuacao_local")
    if not isinstance(local, dict):
        raise AgentValidationError(f"{agent_id}.atuacao_local deve ser mapa")
    rule = _nonempty_string(local.get("regra"), f"{agent_id}.atuacao_local.regra")
    if rule not in VALID_LOCAL_ACTION_RULES:
        raise AgentValidationError(f"{agent_id}: regra local inválida: {rule}")
    if rule != meta.get("atuacao_local"):
        raise AgentValidationError(f"{agent_id}: atuação local diverge do índice")
    _nonempty_string(local.get("escopo"), f"{agent_id}.atuacao_local.escopo")
    _nonempty_string(local.get("observacao"), f"{agent_id}.atuacao_local.observacao")


def _validate_agent_shape(repo: Path, agent_id: str, meta: dict[str, Any], data: Any, *, check_sources: bool) -> None:
    if not isinstance(data, dict):
        raise AgentValidationError(f"{agent_id}: fragmento deve conter mapa")
    if data.get("schema_agente") != 2:
        raise AgentValidationError(f"{agent_id}: schema_agente deve ser 2")
    if data.get("natureza") != "reservado":
        raise AgentValidationError(f"{agent_id}: natureza deve ser reservado")
    if data.get("id") != agent_id:
        raise AgentValidationError(f"{agent_id}: id interno {data.get('id')!r} não coincide com o índice")
    if data.get("nome") != meta.get("nome"):
        raise AgentValidationError(f"{agent_id}: nome diverge do índice")
    if data.get("tipo") != meta.get("tipo"):
        raise AgentValidationError(f"{agent_id}: tipo diverge do índice")
    if data.get("estado") != meta.get("estado"):
        raise AgentValidationError(f"{agent_id}: estado diverge do índice")
    _nonempty_string(data.get("objetivo_atual"), f"{agent_id}.objetivo_atual")
    _string_list(data.get("recursos"), f"{agent_id}.recursos")
    _string_list(data.get("restricoes"), f"{agent_id}.restricoes")
    sources = _string_list(data.get("fontes_canonicas"), f"{agent_id}.fontes_canonicas")
    if len(sources) != len(set(sources)):
        raise AgentValidationError(f"{agent_id}: fontes_canonicas duplicadas")
    source_set = set(sources)
    _validate_presence(repo, agent_id, meta, data, source_set=source_set, check_sources=check_sources)
    _validate_mobility(agent_id, data)
    _validate_local_action(agent_id, meta, data)
    plan = data.get("plano_atual")
    if not isinstance(plan, dict):
        raise AgentValidationError(f"{agent_id}.plano_atual deve ser mapa")
    plan_state = _nonempty_string(plan.get("estado"), f"{agent_id}.plano_atual.estado")
    if plan_state not in VALID_PLAN_STATES:
        raise AgentValidationError(f"{agent_id}: estado de plano inválido: {plan_state}")
    action = plan.get("acao")
    if plan_state == "sem_plano_registrado":
        if action not in (None, ""):
            raise AgentValidationError(f"{agent_id}: sem_plano_registrado exige acao nula")
    else:
        _nonempty_string(action, f"{agent_id}.plano_atual.acao")
    _nonempty_string(plan.get("prazo_ou_oportunidade"), f"{agent_id}.plano_atual.prazo_ou_oportunidade")
    knowledge = data.get("conhecimento")
    if not isinstance(knowledge, list):
        raise AgentValidationError(f"{agent_id}.conhecimento deve ser lista")
    seen_knowledge: set[str] = set()
    for index, item in enumerate(knowledge):
        if not isinstance(item, dict):
            raise AgentValidationError(f"{agent_id}.conhecimento[{index}] deve ser mapa")
        knowledge_id = _nonempty_string(item.get("id"), f"{agent_id}.conhecimento[{index}].id")
        if knowledge_id in seen_knowledge:
            raise AgentValidationError(f"{agent_id}: conhecimento duplicado: {knowledge_id}")
        seen_knowledge.add(knowledge_id)
        _nonempty_string(item.get("fato"), f"{agent_id}.conhecimento[{index}].fato")
        source = _nonempty_string(item.get("fonte"), f"{agent_id}.conhecimento[{index}].fonte")
        evidence = _nonempty_string(item.get("evidencia"), f"{agent_id}.conhecimento[{index}].evidencia")
        if source not in source_set:
            raise AgentValidationError(f"{agent_id}: conhecimento {knowledge_id} usa fonte não declarada: {source}")
        if check_sources:
            source_path = _repo_path(repo, source)
            if not source_path.is_file():
                raise AgentValidationError(f"{agent_id}: fonte canônica inexistente: {source}")
            source_text = _normalize_evidence(source_path.read_text(encoding="utf-8"))
            if _normalize_evidence(evidence) not in source_text:
                raise AgentValidationError(f"{agent_id}: conhecimento {knowledge_id} não possui evidência localizável em {source}")
    if check_sources:
        for source in sources:
            source_path = _repo_path(repo, source)
            if not source_path.is_file():
                raise AgentValidationError(f"{agent_id}: fonte canônica inexistente: {source}")


def load_agent(repo: Path, query: str) -> dict[str, Any]:
    """Abre índice + um único fragmento; não percorre outros agentes nem fontes."""
    index = load_index(repo)
    agent_id, meta = resolve_agent(index, query)
    raw_path = _nonempty_string(meta["arquivo"], f"agentes.{agent_id}.arquivo")
    path = _repo_path(repo, raw_path, expected_prefix=AGENTS_DIR)
    if not path.is_file():
        raise AgentValidationError(f"agente {agent_id} aponta para arquivo inexistente: {raw_path}")
    data = load_yaml(path)
    _validate_agent_shape(repo, agent_id, meta, data, check_sources=False)
    return {
        "agente_id": agent_id,
        "fontes_lidas": [INDEX_PATH.as_posix(), raw_path],
        "elegibilidade_local": local_eligibility(data),
        "resultado": data,
    }


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        index = load_index(repo)
    except AgentValidationError as exc:
        return {"ok": False, "quantidade": 0, "erros": [str(exc)]}
    agents = index["agentes"]
    for agent_id, meta in agents.items():
        try:
            raw_path = _nonempty_string(meta["arquivo"], f"agentes.{agent_id}.arquivo")
            path = _repo_path(repo, raw_path, expected_prefix=AGENTS_DIR)
            if not path.is_file():
                raise AgentValidationError(f"agente {agent_id} aponta para arquivo inexistente: {raw_path}")
            data = load_yaml(path)
            _validate_agent_shape(repo, agent_id, meta, data, check_sources=True)
        except AgentValidationError as exc:
            errors.append(str(exc))
    return {"ok": not errors, "quantidade": len(agents), "erros": errors}


def _dump(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="raiz do repositório (padrão: diretório atual)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validar", help="valida índice, fragmentos, mobilidade, fontes e evidências")
    show = sub.add_parser("mostrar", help="abre somente um agente por id ou nome")
    show.add_argument("agente")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.command == "validar":
            result = validate_repo(repo)
            print(_dump(result), end="")
            return 0 if result["ok"] else 1
        result = load_agent(repo, args.agente)
        print(_dump(result), end="")
        return 0
    except AgentValidationError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
