#!/usr/bin/env python3
"""Audita organização, referências e orçamentos da área reservada.

A auditoria é fria e read-only. Erros objetivos — referência quebrada, ciclo não
classificado, autoridade duplicada, elenco divergente ou consulta acima do teto —
integram o gate de integridade. Alcançabilidade e possível repetição continuam
como suspeitas para revisão humana, nunca como veredito automático de lixo.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

try:
    import agentes
    import progressao_juppongatana
except ModuleNotFoundError:
    from ferramentas import agentes, progressao_juppongatana


CONTRACT = Path("narrador/estrutura.yaml")
NARRATOR = Path("narrador")
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".py", ".json", ".jsonl", ".txt"}
REFERENCE_RE = re.compile(
    r"narrador/[A-Za-z0-9_.\-/]+\.(?:md|ya?ml|png)(?:#[A-Za-z0-9_.\-]+)?"
)


class NarratorStructureError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise NarratorStructureError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise NarratorStructureError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise NarratorStructureError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise NarratorStructureError(f"{label} deve ser texto não vazio")
    return value.strip()


def _relative(value: Any, label: str) -> str:
    raw = _text(value, label)
    path = Path(raw.split("#", 1)[0])
    if path.is_absolute() or ".." in path.parts:
        raise NarratorStructureError(f"{label} deve ficar dentro do repositório")
    return path.as_posix()


def load_contract(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / CONTRACT), CONTRACT.as_posix())
    if data.get("schema_estrutura_narrador") != 1:
        raise NarratorStructureError("schema_estrutura_narrador deve ser 1")
    if data.get("natureza") != "contrato_reservado_de_organizacao":
        raise NarratorStructureError("natureza do contrato estrutural inválida")
    policy = _map(data.get("politica"), "politica")
    if policy.get("consulta_dirigida_max_bytes") != agentes.MAX_DIRECTED_BYTES:
        raise NarratorStructureError("orçamento dirigido diverge da camada de agentes")
    return data


def _text_files(repo: Path) -> list[Path]:
    return [
        path
        for path in repo.rglob("*")
        if path.is_file()
        and path.suffix.lower() in TEXT_SUFFIXES
        and ".git" not in path.parts
        and path.name != "transcricao.md"
    ]


def reference_graph(repo: Path) -> tuple[dict[str, set[str]], list[str], set[str]]:
    narrator_files = {
        path.relative_to(repo).as_posix()
        for path in (repo / NARRATOR).rglob("*")
        if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES | {".png"}
    }
    graph: dict[str, set[str]] = {
        rel: set() for rel in narrator_files if Path(rel).suffix.lower() in TEXT_SUFFIXES
    }
    broken: set[str] = set()
    referenced: set[str] = set()
    non_recursive_sources = {
        CONTRACT.as_posix(),
        "narrador/juppongatana.md",
        "narrador/juppongatana/index.yaml",
    }
    for path in _text_files(repo):
        source = path.relative_to(repo).as_posix()
        text = path.read_text(encoding="utf-8")
        for raw in REFERENCE_RE.findall(text):
            target = raw.split("#", 1)[0]
            referenced.add(target)
            if source.startswith("narrador/") and not (repo / target).is_file():
                broken.add(f"{source} -> {raw}")
            provenance_or_route = (
                source in non_recursive_sources
                or source.startswith("narrador/agentes/")
            )
            if (
                source in graph
                and target in narrator_files
                and source != target
                and not provenance_or_route
            ):
                graph[source].add(target)
    return graph, sorted(broken), referenced


def strongly_connected(graph: dict[str, set[str]]) -> list[frozenset[str]]:
    index = 0
    indices: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    active: set[str] = set()
    result: list[frozenset[str]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = low[node] = index
        index += 1
        stack.append(node)
        active.add(node)
        for target in graph.get(node, set()):
            if target not in graph:
                continue
            if target not in indices:
                visit(target)
                low[node] = min(low[node], low[target])
            elif target in active:
                low[node] = min(low[node], indices[target])
        if low[node] == indices[node]:
            component: set[str] = set()
            while True:
                current = stack.pop()
                active.remove(current)
                component.add(current)
                if current == node:
                    break
            if len(component) > 1:
                result.append(frozenset(component))

    for node in graph:
        if node not in indices:
            visit(node)
    return result


def _allowed_cycles(contract: dict[str, Any]) -> set[frozenset[str]]:
    allowed: set[frozenset[str]] = set()
    for index, raw in enumerate(_list(contract.get("ciclos_permitidos"), "ciclos_permitidos")):
        item = _map(raw, f"ciclos_permitidos[{index}]")
        files = frozenset(
            _relative(value, f"ciclos_permitidos[{index}].arquivos")
            for value in _list(item.get("arquivos"), f"ciclos_permitidos[{index}].arquivos")
        )
        if len(files) < 2:
            raise NarratorStructureError("ciclo permitido precisa declarar ao menos dois arquivos")
        _text(item.get("natureza"), f"ciclos_permitidos[{index}].natureza")
        _text(item.get("motivo"), f"ciclos_permitidos[{index}].motivo")
        if files in allowed:
            raise NarratorStructureError("ciclo permitido duplicado")
        allowed.add(files)
    return allowed


def _validate_authorities(repo: Path, contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    authorities = _map(contract.get("autoridades"), "autoridades")
    files: dict[str, str] = {}
    for authority_id, raw in authorities.items():
        item = _map(raw, f"autoridades.{authority_id}")
        rel = _relative(item.get("arquivo"), f"autoridades.{authority_id}.arquivo")
        _text(item.get("escopo"), f"autoridades.{authority_id}.escopo")
        if rel in files:
            errors.append(
                f"autoridade duplicada no mesmo arquivo: {files[rel]} e {authority_id} -> {rel}"
            )
        files[rel] = authority_id
        if not (repo / rel).is_file():
            errors.append(f"autoridade aponta para arquivo inexistente: {authority_id} -> {rel}")

    derivations = _map(contract.get("derivacoes"), "derivacoes")
    for derivation_id, raw in derivations.items():
        item = _map(raw, f"derivacoes.{derivation_id}")
        rel = _relative(item.get("arquivo"), f"derivacoes.{derivation_id}.arquivo")
        source = _text(item.get("deriva_de"), f"derivacoes.{derivation_id}.deriva_de")
        _text(item.get("propriedade_validada"), f"derivacoes.{derivation_id}.propriedade_validada")
        if source not in authorities:
            errors.append(f"derivação aponta para autoridade inexistente: {derivation_id} -> {source}")
        if not (repo / rel).is_file():
            errors.append(f"derivação aponta para arquivo inexistente: {derivation_id} -> {rel}")
    return errors


def _validate_redirects(repo: Path, contract: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    redirects = _map(contract.get("redirecionamentos"), "redirecionamentos")
    for source_raw, raw in redirects.items():
        source = _relative(source_raw, "redirecionamentos.origem")
        item = _map(raw, f"redirecionamentos.{source}")
        destination = _relative(item.get("destino"), f"redirecionamentos.{source}.destino")
        moved = _relative(
            item.get("conteudo_movido_para"),
            f"redirecionamentos.{source}.conteudo_movido_para",
        )
        _text(item.get("motivo"), f"redirecionamentos.{source}.motivo")
        for rel in (source, destination, moved):
            if not (repo / rel).is_file():
                errors.append(f"redirecionamento aponta para arquivo inexistente: {rel}")
        if (repo / source).is_file():
            text = (repo / source).read_text(encoding="utf-8")
            if destination not in text or moved not in text or "não é fonte\nautoritativa" not in text:
                errors.append(f"redirecionamento legado não declara destino e ausência de autoridade: {source}")
            if len(text.encode("utf-8")) > 1024:
                errors.append(f"redirecionamento legado voltou a acumular conteúdo: {source}")
    return errors


def _validate_roster(repo: Path) -> list[str]:
    errors: list[str] = []
    try:
        roster = progressao_juppongatana.load_roster(repo, check_routes=True)
        index = agentes.load_index(repo)["agentes"]
    except (progressao_juppongatana.JuppongatanaProgressionError, agentes.AgentValidationError) as exc:
        return [str(exc)]
    for member_id, meta in roster.items():
        agent = index.get(member_id)
        if not isinstance(agent, dict):
            errors.append(f"membro sem entrada derivada no índice de agentes: {member_id}")
            continue
        if agent.get("nome") != meta.get("nome"):
            errors.append(f"nome derivado diverge da autoridade de elenco: {member_id}")
        if agent.get("arquivo") != meta.get("agente"):
            errors.append(f"rota derivada de agente diverge da autoridade de elenco: {member_id}")
    return errors


def _reachability_suspects(
    repo: Path,
    contract: dict[str, Any],
    referenced: set[str],
) -> list[str]:
    exclusions = [
        _relative(value, "exclusoes_de_alcancabilidade")
        for value in _list(contract.get("exclusoes_de_alcancabilidade"), "exclusoes_de_alcancabilidade")
    ]
    roots = {
        _relative(value, "raizes_de_consulta")
        for value in _list(contract.get("raizes_de_consulta"), "raizes_de_consulta")
    }
    for rel in roots:
        if not (repo / rel).is_file():
            raise NarratorStructureError(f"raiz de consulta inexistente: {rel}")
    conventional = {"README.md", "index.yaml", "estado.yaml"}
    suspects: list[str] = []
    for path in (repo / NARRATOR).rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(repo).as_posix()
        if any(rel == prefix or rel.startswith(prefix + "/") for prefix in exclusions):
            continue
        if rel in roots or path.name in conventional or path.parent == repo / NARRATOR:
            continue
        if rel not in referenced:
            suspects.append(rel)
    return sorted(suspects)


def audit(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        contract = load_contract(repo)
        errors.extend(_validate_authorities(repo, contract))
        errors.extend(_validate_redirects(repo, contract))
        errors.extend(_validate_roster(repo))
        graph, broken, referenced = reference_graph(repo)
        errors.extend(f"referência quebrada: {item}" for item in broken)
        cycles = set(strongly_connected(graph))
        allowed = _allowed_cycles(contract)
        for component in sorted(cycles - allowed, key=lambda value: sorted(value)):
            errors.append("ciclo não classificado: " + " <-> ".join(sorted(component)))
        for component in sorted(allowed - cycles, key=lambda value: sorted(value)):
            errors.append("ciclo permitido declarado mas ausente: " + " <-> ".join(sorted(component)))
        agent_result = agentes.validate_repo(repo)
        errors.extend(f"agentes: {item}" for item in agent_result["erros"])
        suspects = _reachability_suspects(repo, contract, referenced)
    except NarratorStructureError as exc:
        errors.append(str(exc))
        cycles = set()
        suspects = []
        graph = {}
    return {
        "ok": not errors,
        "erros": list(dict.fromkeys(errors)),
        "suspeitas_revisao_humana": suspects,
        "ciclos_classificados": len(cycles),
        "arquivos_no_grafo": len(graph),
        "regra_suspeitas": "suspeita não é veredito de lixo e não bloqueia o gate",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("comando", choices=("validar", "auditar"), nargs="?", default="auditar")
    args = parser.parse_args(argv)
    result = audit(args.repo.resolve())
    if args.comando == "validar":
        result = {key: value for key, value in result.items() if key != "suspeitas_revisao_humana"}
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
