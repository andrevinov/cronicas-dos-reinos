#!/usr/bin/env python3
"""Catálogo executável e dirigido das regras mecânicas da campanha.

O catálogo identifica regra, versão, autoridade, executor e persistência, mas não
substitui a documentação humana. Cada entrada precisa apontar para uma seção real em
``regras/*.md``. A consulta catalogada é L2; regras ainda não catalogadas preservam o
fallback textual legado enquanto a migração estiver incompleta.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable

import yaml

import contexto_core as core

CATALOG_PATH = Path("regras/catalogo.yaml")
CAMPAIGN_PATH = Path("campanha.yaml")
SCHEMA = 1
REQUIRED_FIELDS = {
    "id", "aliases", "dominio", "ruleset", "autoridade", "fonte",
    "resumo_interno", "executor", "persistencia", "house_rule",
}
EXECUTORS = {"narrador", "dados", "cronica", "progressao"}
PERSISTENCE = {"nenhuma", "turno_transacional", "checkpoint", "estado_canonico"}
ID_RE = re.compile(r"^[a-z0-9_]+$")


class RuleCatalogError(ValueError):
    pass


def read_document(repo: Path) -> dict[str, Any]:
    path = repo / CATALOG_PATH
    if not path.is_file():
        raise RuleCatalogError(f"catálogo de regras ausente: {CATALOG_PATH.as_posix()}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise RuleCatalogError("catálogo de regras precisa ser um mapa YAML")
    return data


def _ruleset_contract(repo: Path) -> tuple[str, str, list[str]]:
    path = repo / CAMPAIGN_PATH
    if not path.is_file():
        raise RuleCatalogError("campanha.yaml ausente para validar ruleset do catálogo")
    campaign = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    try:
        ruleset = campaign["sistema"]["ruleset"]
        current = str(ruleset["atual"])
        target = str(ruleset["alvo"])
        hierarchy = list(ruleset["hierarquia_mecanica"])
    except (KeyError, TypeError) as exc:
        raise RuleCatalogError("contrato sistema.ruleset inválido em campanha.yaml") from exc
    return current, target, [str(item) for item in hierarchy]


def _source_path(repo: Path, rel: Any) -> Path:
    if not isinstance(rel, str) or not rel.strip():
        raise RuleCatalogError("fonte.arquivo precisa ser caminho textual")
    path = Path(rel)
    if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != "regras":
        raise RuleCatalogError(f"fonte fora de regras/: {rel}")
    target = repo / path
    if not target.is_file():
        raise RuleCatalogError(f"fonte inexistente: {rel}")
    if target.suffix.lower() != ".md":
        raise RuleCatalogError(f"fonte humana precisa ser Markdown: {rel}")
    return target


def _find_section(repo: Path, source: dict[str, Any]) -> dict[str, Any]:
    path = _source_path(repo, source.get("arquivo"))
    section_name = source.get("secao")
    if not isinstance(section_name, str) or not section_name.strip():
        raise RuleCatalogError("fonte.secao precisa identificar uma seção humana")
    wanted = core.normalize(section_name)
    text = path.read_text(encoding="utf-8")
    for section in core.split_markdown_sections(text):
        if core.normalize(section.get("titulo", "")) == wanted:
            return {
                "arquivo": path.relative_to(repo).as_posix(),
                "linha": section["linha"],
                "titulo": section["titulo"],
                "conteudo": core.truncate_text(section["conteudo"], 2200),
            }
    raise RuleCatalogError(
        f"seção humana inexistente em {source.get('arquivo')}: {section_name}"
    )


def validate_document(repo: Path, document: dict[str, Any]) -> dict[str, Any]:
    if document.get("schema_catalogo_regras") != SCHEMA:
        raise RuleCatalogError("schema_catalogo_regras precisa ser 1")
    if document.get("natureza") != "indice_executavel":
        raise RuleCatalogError("natureza do catálogo precisa ser indice_executavel")
    rules = document.get("regras")
    if not isinstance(rules, list) or not rules:
        raise RuleCatalogError("regras precisa ser lista não vazia")

    current, target, hierarchy = _ruleset_contract(repo)
    known_rulesets = {current, target}
    seen_ids: set[str] = set()
    names: dict[str, str] = {}

    for position, rule in enumerate(rules, 1):
        if not isinstance(rule, dict):
            raise RuleCatalogError(f"regra #{position} precisa ser mapa")
        missing = REQUIRED_FIELDS - set(rule)
        if missing:
            raise RuleCatalogError(
                f"regra #{position} sem campos obrigatórios: {', '.join(sorted(missing))}"
            )
        rule_id = rule.get("id")
        if not isinstance(rule_id, str) or not ID_RE.fullmatch(rule_id):
            raise RuleCatalogError(f"id de regra inválido: {rule_id!r}")
        if rule_id in seen_ids:
            raise RuleCatalogError(f"id duplicado no catálogo: {rule_id}")
        seen_ids.add(rule_id)

        aliases = rule.get("aliases")
        if not isinstance(aliases, list) or not all(
            isinstance(alias, str) and alias.strip() for alias in aliases
        ):
            raise RuleCatalogError(f"{rule_id}: aliases precisa ser lista textual")
        for label in [rule_id, *aliases]:
            normalized = core.normalize(label)
            if not normalized:
                raise RuleCatalogError(f"{rule_id}: alias vazio após normalização")
            owner = names.get(normalized)
            if owner is not None:
                raise RuleCatalogError(
                    f"alias duplicado ou ambíguo: {label!r} pertence a {owner} e {rule_id}"
                )
            names[normalized] = rule_id

        domain = rule.get("dominio")
        if not isinstance(domain, str) or not ID_RE.fullmatch(domain):
            raise RuleCatalogError(f"{rule_id}: dominio inválido")

        rule_ruleset = rule.get("ruleset")
        if rule_ruleset not in known_rulesets:
            raise RuleCatalogError(f"{rule_id}: ruleset desconhecido: {rule_ruleset}")
        if rule_ruleset != current:
            raise RuleCatalogError(
                f"{rule_id}: conflito de versão; catálogo operacional usa {current}, não {rule_ruleset}"
            )

        authority = rule.get("autoridade")
        if authority not in hierarchy:
            raise RuleCatalogError(f"{rule_id}: autoridade desconhecida: {authority}")
        if rule.get("executor") not in EXECUTORS:
            raise RuleCatalogError(f"{rule_id}: executor desconhecido: {rule.get('executor')}")
        if rule.get("persistencia") not in PERSISTENCE:
            raise RuleCatalogError(
                f"{rule_id}: persistência desconhecida: {rule.get('persistencia')}"
            )

        summary = rule.get("resumo_interno")
        if not isinstance(summary, str) or not summary.strip() or len(summary) > 900:
            raise RuleCatalogError(f"{rule_id}: resumo_interno ausente ou grande demais")
        house_rule = rule.get("house_rule")
        if house_rule is not None and (
            not isinstance(house_rule, str) or not ID_RE.fullmatch(house_rule)
        ):
            raise RuleCatalogError(f"{rule_id}: house_rule precisa ser id ou null")
        source = rule.get("fonte")
        if not isinstance(source, dict):
            raise RuleCatalogError(f"{rule_id}: fonte precisa ser mapa")
        _find_section(repo, source)

    contract = document.get("contrato") or {}
    if not isinstance(contract, dict):
        raise RuleCatalogError("contrato do catálogo precisa ser mapa")
    if contract.get("nivel_consulta_catalogada") != "L2":
        raise RuleCatalogError("consulta catalogada precisa permanecer L2")
    if int(contract.get("max_resultado_l2_bytes", 0)) > core.DEFAULT_MAX_BYTES:
        raise RuleCatalogError("orçamento do catálogo excede o teto L2")
    return document


def load_catalog(repo: Path) -> dict[str, Any]:
    return validate_document(repo, read_document(repo))


def resolve_rule(document: dict[str, Any], term: str) -> tuple[dict[str, Any] | None, list[str]]:
    query = core.normalize(term)
    index: dict[str, dict[str, Any]] = {}
    for rule in document["regras"]:
        for label in [rule["id"], *rule["aliases"]]:
            index[core.normalize(label)] = rule
    if query in index:
        return index[query], []
    tokens = set(query.split())
    ranked: list[tuple[int, str]] = []
    for rule in document["regras"]:
        labels = [rule["id"], *rule["aliases"]]
        normalized = [core.normalize(label) for label in labels]
        score = 20 if query and any(query in label for label in normalized) else 0
        score += max([len(tokens & set(label.split())) for label in normalized] or [0])
        if score:
            ranked.append((score, rule["id"]))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return None, [rule_id for _, rule_id in ranked[:6]]


def command_rule(
    repo: Path,
    term: str,
    *,
    fallback: Callable[[Path, str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    document = load_catalog(repo)
    rule, candidates = resolve_rule(document, term)
    if rule is None:
        if fallback is None:
            return core.envelope(
                "regra", term, "L2",
                [CATALOG_PATH.as_posix(), CAMPAIGN_PATH.as_posix()],
                {"encontrado": False, "catalogada": False, "candidatos_catalogo": candidates},
            )
        data = fallback(repo, term)
        result = data.get("resultado")
        if isinstance(result, dict):
            result["catalogada"] = False
            result["candidatos_catalogo"] = candidates
        sources = [CATALOG_PATH.as_posix(), *list(data.get("fontes") or [])]
        data["fontes"] = list(dict.fromkeys(sources))
        return data

    documentation = _find_section(repo, rule["fonte"])
    result = {
        "encontrado": True,
        "catalogada": True,
        "id": rule["id"],
        "aliases": list(rule["aliases"]),
        "dominio": rule["dominio"],
        "ruleset": rule["ruleset"],
        "autoridade": rule["autoridade"],
        "executor": rule["executor"],
        "persistencia": rule["persistencia"],
        "house_rule": rule["house_rule"],
        "resumo_interno": rule["resumo_interno"],
        "fonte": dict(rule["fonte"]),
        "documentacao": documentation,
    }
    return core.envelope(
        "regra", term, "L2",
        [CATALOG_PATH.as_posix(), CAMPAIGN_PATH.as_posix(), documentation["arquivo"]],
        result,
    )


def check(repo: Path) -> dict[str, Any]:
    try:
        document = load_catalog(repo)
        current, _, _ = _ruleset_contract(repo)
    except (RuleCatalogError, OSError, yaml.YAMLError) as exc:
        return {"ok": False, "erros": [str(exc)], "regras": 0}
    return {
        "ok": True,
        "erros": [],
        "regras": len(document["regras"]),
        "ruleset": current,
        "nivel_consulta": "L2",
    }
