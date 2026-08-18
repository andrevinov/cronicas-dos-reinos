#!/usr/bin/env python3
"""Relógios como pressões e consequências de agentes do Mundo Vivo.

Os fragmentos em ``narrador/relogios/*.yaml`` continuam sendo a fonte canônica
do progresso. Cada um possui ``vinculo_agencial``: quem está operacionalmente
ligado à pressão/consequência e, quando couber, qual operação ela materializa.

``vinculos.yaml`` é apenas um roteador derivado e compacto. Consultas em jogo
podem descobrir as pressões ativas de um agente sem abrir todos os relógios.
A sincronização roda em checkpoints de baixa frequência, fora do hot path do
turno; se uma pressão alcança o limite, ela é convertida deterministicamente em
consequência resolvida.
"""
from __future__ import annotations

import argparse
import copy
import os
import sys
import tempfile
import unicodedata
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

INDEX_PATH = Path("narrador/relogios/index.yaml")
ROUTER_PATH = Path("narrador/relogios/vinculos.yaml")
CLOCKS_DIR = Path("narrador/relogios")

VALID_KINDS = {"pressao", "consequencia"}
VALID_STATES = {"ativo", "resolvido"}
VALID_ROLES = {"origem", "explorador", "executor", "afetado", "alvo"}


class ClockError(ValueError):
    """Erro de contrato da camada de relógios/agentes."""


def configured(repo: Path) -> bool:
    return (repo / INDEX_PATH).is_file()


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ClockError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise ClockError(f"YAML inválido em {path}: {exc}") from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ClockError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ClockError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ClockError(f"{label} deve ser texto não vazio")
    return value.strip()


def _nullable_text(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _normalize(value: str) -> str:
    raw = unicodedata.normalize("NFKD", str(value))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    raw = " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in raw).split())
    return raw


def _repo_path(repo: Path, raw: str) -> Path:
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        raise ClockError(f"caminho fora do repositório: {raw}")
    try:
        rel.relative_to(CLOCKS_DIR)
    except ValueError as exc:
        raise ClockError(f"relógio deve permanecer sob {CLOCKS_DIR.as_posix()}: {raw}") from exc
    return repo / rel


def _atomic_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False, width=110)
        handle.flush()
        os.fsync(handle.fileno())
        tmp = Path(handle.name)
    os.replace(tmp, path)


def load_index(repo: Path) -> dict[str, Any]:
    data = _map(_load_yaml(repo / INDEX_PATH), INDEX_PATH.as_posix())
    if data.get("schema_relogios") != 1 or data.get("natureza") != "reservado":
        raise ClockError("índice de relógios inválido")
    clocks = _map(data.get("relogios"), "relogios")
    if data.get("quantidade") != len(clocks):
        raise ClockError("quantidade do índice de relógios diverge do mapa")
    seen: set[str] = set()
    for clock_id, raw in clocks.items():
        _text(clock_id, "id de relógio")
        meta = _map(raw, f"relogios.{clock_id}")
        path = _text(meta.get("arquivo"), f"relogios.{clock_id}.arquivo")
        _repo_path(repo, path)
        if path in seen:
            raise ClockError(f"arquivo de relógio duplicado: {path}")
        seen.add(path)
        session = meta.get("sessao_ultima_atualizacao")
        if not isinstance(session, int) or session < 1:
            raise ClockError(f"{clock_id}.sessao_ultima_atualizacao deve ser inteiro positivo")
    return data


def _binding(clock_id: str, doc: dict[str, Any]) -> dict[str, Any]:
    raw = _map(doc.get("vinculo_agencial"), f"{clock_id}.vinculo_agencial")
    kind = _text(raw.get("tipo"), f"{clock_id}.vinculo_agencial.tipo")
    state = _text(raw.get("estado"), f"{clock_id}.vinculo_agencial.estado")
    if kind not in VALID_KINDS:
        raise ClockError(f"{clock_id}: tipo de vínculo inválido: {kind}")
    if state not in VALID_STATES:
        raise ClockError(f"{clock_id}: estado de vínculo inválido: {state}")
    operation = _nullable_text(raw.get("operacao"), f"{clock_id}.vinculo_agencial.operacao")
    principal = _text(
        raw.get("agente_principal"), f"{clock_id}.vinculo_agencial.agente_principal"
    )
    role = _text(raw.get("papel_agente"), f"{clock_id}.vinculo_agencial.papel_agente")
    if role not in VALID_ROLES:
        raise ClockError(f"{clock_id}: papel de agente inválido: {role}")
    related_raw = _list(
        raw.get("agentes_relacionados") or [],
        f"{clock_id}.vinculo_agencial.agentes_relacionados",
    )
    related: list[str] = []
    for i, value in enumerate(related_raw):
        related.append(
            _text(value, f"{clock_id}.vinculo_agencial.agentes_relacionados[{i}]")
        )
    if len(related) != len(set(related)):
        raise ClockError(f"{clock_id}: agentes_relacionados duplicados")
    if principal in related:
        raise ClockError(f"{clock_id}: agente principal não deve repetir em agentes_relacionados")
    if state == "ativo" and kind != "pressao":
        raise ClockError(f"{clock_id}: vínculo ativo deve ser pressao")
    if state == "ativo" and not operation:
        raise ClockError(f"{clock_id}: pressão ativa exige operação")
    if state == "resolvido" and kind != "consequencia":
        raise ClockError(f"{clock_id}: vínculo resolvido deve ser consequencia")
    return {
        "tipo": kind,
        "estado": state,
        "operacao": operation,
        "agente_principal": principal,
        "papel_agente": role,
        "agentes_relacionados": related,
    }


def _payload(clock_id: str, doc: dict[str, Any], binding: dict[str, Any]) -> dict[str, Any]:
    if doc.get("schema_relogio") != 1 or doc.get("natureza") != "reservado":
        raise ClockError(f"{clock_id}: fragmento de relógio inválido")
    if doc.get("id") != clock_id:
        raise ClockError(f"{clock_id}: id interno diverge do índice")
    clock = _map(doc.get("relogio"), f"{clock_id}.relogio")
    _text(clock.get("titulo"), f"{clock_id}.relogio.titulo")
    progress = clock.get("progresso")
    limit = clock.get("limite")
    if not isinstance(progress, int) or progress < 0:
        raise ClockError(f"{clock_id}.progresso deve ser inteiro >= 0")
    if not isinstance(limit, int) or limit < 1:
        raise ClockError(f"{clock_id}.limite deve ser inteiro >= 1")
    if progress > limit:
        raise ClockError(f"{clock_id}: progresso {progress} excede limite {limit}")
    _text(clock.get("descricao"), f"{clock_id}.relogio.descricao")
    _text(clock.get("consequencia_no_limite"), f"{clock_id}.relogio.consequencia_no_limite")
    _list(doc.get("eventos"), f"{clock_id}.eventos")
    if binding["estado"] == "ativo" and progress >= limit:
        raise ClockError(
            f"{clock_id}: pressão alcançou o limite mas ainda está ativa; execute sincronizar"
        )
    if binding["estado"] == "resolvido" and progress < limit:
        raise ClockError(f"{clock_id}: consequência resolvida ainda não alcançou o limite")
    return clock


def load_clock_doc(repo: Path, clock_id: str, meta: dict[str, Any]) -> dict[str, Any]:
    path = _repo_path(repo, _text(meta.get("arquivo"), f"{clock_id}.arquivo"))
    doc = _map(_load_yaml(path), meta["arquivo"])
    binding = _binding(clock_id, doc)
    _payload(clock_id, doc, binding)
    return doc


def _validate_agents(
    clock_id: str,
    binding: dict[str, Any],
    known_agents: set[str],
) -> None:
    ids = {binding["agente_principal"], *binding["agentes_relacionados"]}
    missing = sorted(ids - known_agents)
    if missing:
        raise ClockError(f"{clock_id}: agentes inexistentes no vínculo: {', '.join(missing)}")


def _build_router(
    index: dict[str, Any],
    docs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    clocks: dict[str, Any] = {}
    by_agent: dict[str, dict[str, list[str]]] = {}
    operations: dict[str, dict[str, Any]] = {}

    for clock_id in sorted(index["relogios"]):
        doc = docs[clock_id]
        binding = _binding(clock_id, doc)
        clock_payload = _map(doc.get("relogio"), f"{clock_id}.relogio")
        entry = {
            "titulo": _text(clock_payload.get("titulo"), f"{clock_id}.relogio.titulo"),
            "tipo": binding["tipo"],
            "estado": binding["estado"],
            "operacao": binding["operacao"],
            "agente_principal": binding["agente_principal"],
            "papel_agente": binding["papel_agente"],
            "agentes_relacionados": binding["agentes_relacionados"],
            "arquivo": index["relogios"][clock_id]["arquivo"],
        }
        clocks[clock_id] = entry

        all_agents = [binding["agente_principal"], *binding["agentes_relacionados"]]
        for agent_id in all_agents:
            bucket = by_agent.setdefault(
                agent_id,
                {
                    "pressoes_ativas": [],
                    "consequencias_resolvidas": [],
                    "operacoes_com_pressao_ativa": [],
                },
            )
            if binding["estado"] == "ativo":
                bucket["pressoes_ativas"].append(clock_id)
                if binding["operacao"] and binding["operacao"] not in bucket["operacoes_com_pressao_ativa"]:
                    bucket["operacoes_com_pressao_ativa"].append(binding["operacao"])
            else:
                bucket["consequencias_resolvidas"].append(clock_id)

        operation = binding["operacao"]
        if operation:
            op = operations.setdefault(
                operation,
                {
                    "agente_principal": binding["agente_principal"],
                    "agentes_relacionados": list(binding["agentes_relacionados"]),
                    "pressoes_ativas": [],
                    "consequencias_resolvidas": [],
                },
            )
            if op["agente_principal"] != binding["agente_principal"]:
                raise ClockError(
                    f"operação {operation} possui agentes principais divergentes"
                )
            if op["agentes_relacionados"] != binding["agentes_relacionados"]:
                op["agentes_relacionados"] = sorted(
                    set(op["agentes_relacionados"]) | set(binding["agentes_relacionados"])
                )
            target = (
                "pressoes_ativas" if binding["estado"] == "ativo"
                else "consequencias_resolvidas"
            )
            op[target].append(clock_id)

    for bucket in by_agent.values():
        for key in bucket:
            bucket[key] = sorted(bucket[key])
    for op in operations.values():
        op["agentes_relacionados"] = sorted(op["agentes_relacionados"])
        op["pressoes_ativas"] = sorted(op["pressoes_ativas"])
        op["consequencias_resolvidas"] = sorted(op["consequencias_resolvidas"])
        op["situacao_relogios"] = "com_pressao_ativa" if op["pressoes_ativas"] else "sem_pressao_ativa"

    return {
        "schema_vinculos_relogios": 1,
        "natureza": "roteador_derivado",
        "descricao": (
            "Roteador compacto derivado dos vinculos_agenciais dos relógios; "
            "não é fonte independente de fatos."
        ),
        "quantidade": len(clocks),
        "pressoes_ativas": sum(
            1 for item in clocks.values() if item["estado"] == "ativo"
        ),
        "consequencias_resolvidas": sum(
            1 for item in clocks.values() if item["estado"] == "resolvido"
        ),
        "operacoes": dict(sorted(operations.items())),
        "por_agente": dict(sorted(by_agent.items())),
        "relogios": clocks,
    }


def load_router(repo: Path) -> dict[str, Any]:
    data = _map(_load_yaml(repo / ROUTER_PATH), ROUTER_PATH.as_posix())
    if data.get("schema_vinculos_relogios") != 1:
        raise ClockError("roteador de vínculos deve usar schema_vinculos_relogios: 1")
    if data.get("natureza") != "roteador_derivado":
        raise ClockError("roteador de vínculos deve ter natureza: roteador_derivado")
    _map(data.get("por_agente"), "vinculos.por_agente")
    _map(data.get("relogios"), "vinculos.relogios")
    return data


def sync(repo: Path) -> dict[str, Any]:
    """Sincroniza transição pressão→consequência e recompõe o roteador derivado."""
    index = load_index(repo)
    agent_index = agentes.load_index(repo)
    known_agents = set(agent_index["agentes"])
    docs: dict[str, dict[str, Any]] = {}
    resolved_now: list[str] = []
    updated_fragments: list[str] = []

    for clock_id, meta in index["relogios"].items():
        path = _repo_path(repo, meta["arquivo"])
        doc = _map(_load_yaml(path), meta["arquivo"])
        binding = _binding(clock_id, doc)
        clock = _map(doc.get("relogio"), f"{clock_id}.relogio")
        progress = clock.get("progresso")
        limit = clock.get("limite")
        if not isinstance(progress, int) or not isinstance(limit, int):
            raise ClockError(f"{clock_id}: progresso/limite inválidos")
        if binding["estado"] == "ativo" and progress >= limit:
            raw_binding = doc["vinculo_agencial"]
            raw_binding["estado"] = "resolvido"
            raw_binding["tipo"] = "consequencia"
            binding = _binding(clock_id, doc)
            _atomic_yaml(path, doc)
            resolved_now.append(clock_id)
            updated_fragments.append(meta["arquivo"])
        _validate_agents(clock_id, binding, known_agents)
        _payload(clock_id, doc, binding)
        docs[clock_id] = doc

    router = _build_router(index, docs)
    router_path = repo / ROUTER_PATH
    previous = _load_yaml(router_path) if router_path.is_file() else None
    router_changed = previous != router
    if router_changed:
        _atomic_yaml(router_path, router)

    return {
        "ok": True,
        "quantidade": len(docs),
        "pressoes_ativas": router["pressoes_ativas"],
        "consequencias_resolvidas": router["consequencias_resolvidas"],
        "resolvidos_agora": sorted(resolved_now),
        "fragmentos_atualizados": sorted(updated_fragments),
        "roteador_alterado": router_changed,
        "fragmentos_lidos": len(docs),
        "fontes_expostas": [INDEX_PATH.as_posix(), ROUTER_PATH.as_posix()],
    }


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        index = load_index(repo)
        agent_index = agentes.load_index(repo)
        known_agents = set(agent_index["agentes"])
        docs: dict[str, dict[str, Any]] = {}
        for clock_id, meta in index["relogios"].items():
            doc = load_clock_doc(repo, clock_id, meta)
            binding = _binding(clock_id, doc)
            _validate_agents(clock_id, binding, known_agents)
            docs[clock_id] = doc
        expected = _build_router(index, docs)
        actual = load_router(repo)
        if actual != expected:
            errors.append("roteador de vínculos está desatualizado; execute sincronizar")
    except (ClockError, agentes.AgentValidationError) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "quantidade": len(index["relogios"]) if "index" in locals() else 0,
        "pressoes_ativas": (
            expected.get("pressoes_ativas", 0) if "expected" in locals() else 0
        ),
        "consequencias_resolvidas": (
            expected.get("consequencias_resolvidas", 0) if "expected" in locals() else 0
        ),
        "erros": errors,
    }


def _resolve_agent_query(repo: Path, router: dict[str, Any], query: str) -> tuple[str, list[str]]:
    if query in router["por_agente"]:
        return query, [ROUTER_PATH.as_posix()]
    index = agentes.load_index(repo)
    agent_id, _ = agentes.resolve_agent(index, query)
    return agent_id, [ROUTER_PATH.as_posix(), agentes.INDEX_PATH.as_posix()]


def by_agent(repo: Path, query: str, *, include_resolved: bool = False) -> dict[str, Any]:
    """Consulta barata: normalmente lê somente o roteador derivado."""
    router = load_router(repo)
    agent_id, sources = _resolve_agent_query(repo, router, query)
    bucket = copy.deepcopy(
        router["por_agente"].get(
            agent_id,
            {"pressoes_ativas": [], "consequencias_resolvidas": [], "operacoes_com_pressao_ativa": []},
        )
    )
    result = {
        "agente": agent_id,
        "operacoes_com_pressao_ativa": bucket["operacoes_com_pressao_ativa"],
        "pressoes_ativas": bucket["pressoes_ativas"],
    }
    if include_resolved:
        result["consequencias_resolvidas"] = bucket["consequencias_resolvidas"]
    return {**result, "fontes_lidas": sources}


def show(repo: Path, query: str) -> dict[str, Any]:
    index = load_index(repo)
    router = load_router(repo)
    if query in index["relogios"]:
        clock_id = query
    else:
        wanted = _normalize(query)
        matches = [
            candidate
            for candidate, item in router["relogios"].items()
            if wanted in {_normalize(candidate), _normalize(item.get("titulo") or "")}
        ]
        if len(matches) != 1:
            raise ClockError(f"relógio não encontrado/ambíguo: {query}")
        clock_id = matches[0]
    meta = index["relogios"][clock_id]
    doc = load_clock_doc(repo, clock_id, meta)
    return {
        "relogio_id": clock_id,
        "vinculo": router["relogios"][clock_id],
        "resultado": doc,
        "fontes_lidas": [ROUTER_PATH.as_posix(), INDEX_PATH.as_posix(), meta["arquivo"]],
    }


def status(repo: Path) -> dict[str, Any]:
    router = load_router(repo)
    return {
        "quantidade": router["quantidade"],
        "pressoes_ativas": router["pressoes_ativas"],
        "consequencias_resolvidas": router["consequencias_resolvidas"],
        "operacoes_com_pressao_ativa": sorted(
            op_id
            for op_id, item in router["operacoes"].items()
            if item["situacao_relogios"] == "com_pressao_ativa"
        ),
        "fontes_lidas": [ROUTER_PATH.as_posix()],
    }


def _dump(value: dict[str, Any]) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("sincronizar")
    sub.add_parser("validar")
    show_parser = sub.add_parser("mostrar")
    show_parser.add_argument("relogio")
    agent_parser = sub.add_parser("por-agente")
    agent_parser.add_argument("agente")
    agent_parser.add_argument("--todos", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.command == "status":
            result = status(repo)
        elif args.command == "sincronizar":
            result = sync(repo)
        elif args.command == "validar":
            result = validate_repo(repo)
        elif args.command == "mostrar":
            result = show(repo, args.relogio)
        else:
            result = by_agent(repo, args.agente, include_resolved=args.todos)
        print(_dump(result), end="")
        if args.command == "validar":
            return 0 if result["ok"] else 1
        return 0
    except (ClockError, agentes.AgentValidationError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
