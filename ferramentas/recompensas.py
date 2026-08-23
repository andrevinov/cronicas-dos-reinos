#!/usr/bin/env python3
"""Mapas determinísticos de itens e recompensas por local.

A camada é reativa: só deve ser chamada quando a narração entra/explora um local.
Um mapa é criado no máximo uma vez a partir de seed + local + tier + periculosidade
e depois passa a ser reutilizado. O mapa compacto contém somente metadados
operacionais; detalhes de cada recompensa ficam em fragmentos dirigidos.

Esta ferramenta NÃO pertence ao checkpoint do Mundo Vivo e não transforma
"item existe" em "Ren encontrou". Descoberta/obtenção continuam decisões
narrativas e, quando integradas ao fluxo ao vivo, devem passar pelo pipeline
transacional normal.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml

import ecologia_local

INDEX = Path("narrador/recompensas/index.yaml")
ITEM_INDEX = Path("narrador/recompensas/itens-index.yaml")
TABLES = Path("narrador/recompensas/tabelas.yaml")
PLANNED = Path("narrador/recompensas/planejadas.yaml")
MAPS_DIR = Path("narrador/recompensas/mapas")
ITEMS_DIR = Path("narrador/recompensas/itens")

GENERATOR = "deterministico_v1"
GENERATOR_V2 = "deterministico_v2"
VALID_GENERATORS = {GENERATOR, GENERATOR_V2}
VALUE_RANK = {"baixo": 1, "moderado": 2, "alto": 3}
VALUE_BY_RANK = {value: key for key, value in VALUE_RANK.items()}
V2_VALUE_COST = {"baixo": 1, "moderado": 2, "alto": 3}
V2_IMPORTANCE_COST = {"comum": 0, "especial": 2}
VALID_DANGER = {"baixa", "media", "alta", "letal"}
VALID_STATES = {"oculto", "descoberto", "obtido", "indisponivel"}
VALID_IMPORTANCE = {"comum", "especial", "arco"}
VALID_ORIGINS = {"procedural", "quest", "direcao_canonica", "autoral"}
VALID_POSSESSION = {"ambiente", "papel_local", "npc"}
VALID_LOCAL_ROLES = {"guardiao", "ocupante"}
LOCAL_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,95}$")
REWARD_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,127}$")


class RewardMapError(ValueError):
    pass


def load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise RewardMapError(str(exc)) from exc


def amap(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RewardMapError(f"{label} deve ser mapa")
    return value


def alist(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise RewardMapError(f"{label} deve ser lista")
    return value


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RewardMapError(f"{label} deve ser texto não vazio")
    return value.strip()


def integer(value: Any, label: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise RewardMapError(f"{label} deve ser inteiro >= {minimum}")
    return value


def local_id(value: Any) -> str:
    value = text(value, "local_id")
    if not LOCAL_RE.fullmatch(value):
        raise RewardMapError(
            "local_id deve usar somente minúsculas ASCII, números, _ ou - (máx. 96)"
        )
    return value


def reward_id(value: Any) -> str:
    value = text(value, "recompensa.id")
    if not REWARD_RE.fullmatch(value):
        raise RewardMapError(
            "id de recompensa deve usar somente minúsculas ASCII, números, _ ou -"
        )
    return value


def repo_path(repo: Path, raw: str, prefix: Path | None = None) -> Path:
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        raise RewardMapError(f"caminho fora do repo: {raw}")
    if prefix is not None:
        try:
            rel.relative_to(prefix)
        except ValueError as exc:
            raise RewardMapError(f"caminho {raw} deve ficar sob {prefix}") from exc
    return repo / rel


def _dump(data: Any) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


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


def install_once(path: Path, data: dict[str, Any]) -> None:
    """Instala bytes determinísticos; órfão idêntico é recuperável, divergente não."""
    rendered = _dump(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != rendered:
            raise RewardMapError(f"artefato já existe com conteúdo divergente: {path}")
        return
    path.write_text(rendered, encoding="utf-8")


def load_index(repo: Path) -> dict[str, Any]:
    data = amap(load(repo / INDEX), str(INDEX))
    if data.get("schema_recompensas") != 1 or data.get("natureza") != "reservado":
        raise RewardMapError("índice de recompensas inválido")
    text(data.get("semente"), "semente")
    budget = amap(data.get("orcamento"), "orcamento")
    procedural_max = integer(
        budget.get("max_procedurais_por_mapa"), "orcamento.max_procedurais_por_mapa", 1
    )
    total_max = integer(
        budget.get("max_totais_por_mapa"), "orcamento.max_totais_por_mapa", procedural_max
    )
    if total_max < procedural_max:
        raise RewardMapError("max_totais_por_mapa não pode ser menor que max_procedurais")
    rules = amap(data.get("regras"), "regras")
    expected = {
        "geracao": "sha256_seed_local_tier_periculosidade",
        "mapa_gerado_uma_vez": True,
        "reroll": "proibido",
        "item_existir_nao_significa_descoberta": True,
        "recompensa_de_arco_procedural": "proibida",
    }
    for key, value in expected.items():
        if rules.get(key) != value:
            raise RewardMapError(f"regra obrigatória divergente: {key}")
    maps = amap(data.get("mapas"), "mapas")
    for place, meta in maps.items():
        local_id(place)
        meta = amap(meta, f"mapas.{place}")
        raw = text(meta.get("arquivo"), f"mapas.{place}.arquivo")
        repo_path(repo, raw, MAPS_DIR)
        tier = integer(meta.get("tier"), f"mapas.{place}.tier", 1)
        danger = text(meta.get("periculosidade"), f"mapas.{place}.periculosidade")
        if danger not in VALID_DANGER:
            raise RewardMapError(f"{place}: periculosidade inválida")
        integer(meta.get("quantidade"), f"mapas.{place}.quantidade", 0)
        text(meta.get("chave_geracao"), f"mapas.{place}.chave_geracao")
        if tier > 99:
            raise RewardMapError(f"{place}: tier absurdo")
    return data


def load_item_index(repo: Path) -> dict[str, Any]:
    data = amap(load(repo / ITEM_INDEX), str(ITEM_INDEX))
    if (
        data.get("schema_indice_itens_recompensa") != 1
        or data.get("natureza") != "reservado"
        or data.get("regra") != "lookup_dirigido_sem_scan"
    ):
        raise RewardMapError("índice dirigido de itens inválido")
    items = amap(data.get("recompensas"), "recompensas")
    for rid, meta in items.items():
        reward_id(rid)
        meta = amap(meta, f"recompensas.{rid}")
        local_id(meta.get("local_id"))
        repo_path(repo, text(meta.get("mapa"), f"{rid}.mapa"), MAPS_DIR)
        repo_path(repo, text(meta.get("arquivo"), f"{rid}.arquivo"), ITEMS_DIR)
    return data


def load_tables(repo: Path) -> dict[str, Any]:
    data = amap(load(repo / TABLES), str(TABLES))
    if (
        data.get("schema_tabelas_recompensas") not in {1, 2}
        or data.get("natureza") != "reservado"
        or data.get("gerador") != GENERATOR
    ):
        raise RewardMapError("tabelas de recompensas inválidas")

    tiers = amap(data.get("tiers"), "tiers")
    for raw_tier, entry in tiers.items():
        try:
            tier = int(raw_tier)
        except (TypeError, ValueError) as exc:
            raise RewardMapError(f"tier inválido nas tabelas: {raw_tier!r}") from exc
        if tier < 1:
            raise RewardMapError("tiers devem começar em 1")
        entry = amap(entry, f"tiers.{raw_tier}")
        low = integer(entry.get("min"), f"tiers.{raw_tier}.min", 0)
        high = integer(entry.get("max"), f"tiers.{raw_tier}.max", low)
        if high < low:
            raise RewardMapError(f"tiers.{raw_tier}: max < min")
        categories = alist(entry.get("categorias"), f"tiers.{raw_tier}.categorias")
        if not categories:
            raise RewardMapError(f"tiers.{raw_tier}.categorias vazio")
        for category in categories:
            text(category, f"tiers.{raw_tier}.categorias")

    bonus = amap(data.get("bonus_periculosidade"), "bonus_periculosidade")
    if set(bonus) != VALID_DANGER:
        raise RewardMapError("bonus_periculosidade deve cobrir baixa/media/alta/letal")
    for danger, value in bonus.items():
        integer(value, f"bonus_periculosidade.{danger}", 0)

    conditions = alist(data.get("condicoes"), "condicoes")
    seen_conditions: set[str] = set()
    for i, condition in enumerate(conditions):
        condition = amap(condition, f"condicoes[{i}]")
        cid = text(condition.get("id"), f"condicoes[{i}].id")
        if cid in seen_conditions:
            raise RewardMapError(f"condição duplicada: {cid}")
        seen_conditions.add(cid)
        text(condition.get("texto"), f"condicoes[{i}].texto")
        possessions = alist(condition.get("posses"), f"condicoes[{i}].posses")
        if not possessions:
            raise RewardMapError(f"{cid}: posses vazias")
        for value in possessions:
            if text(value, f"{cid}.posses") not in {
                "ambiente",
                "guardiao_local",
                "ocupante_local",
            }:
                raise RewardMapError(f"{cid}: posse procedural inválida")

    catalog = amap(data.get("catalogo"), "catalogo")
    if not catalog:
        raise RewardMapError("catálogo procedural vazio")
    referenced_categories = {
        text(category, "categoria") for tier in tiers.values() for category in tier["categorias"]
    }
    if referenced_categories - set(catalog):
        raise RewardMapError(
            "categorias sem catálogo: " + ", ".join(sorted(referenced_categories - set(catalog)))
        )
    for category, templates in catalog.items():
        templates = alist(templates, f"catalogo.{category}")
        if not templates:
            raise RewardMapError(f"catalogo.{category} vazio")
        seen_templates: set[str] = set()
        for i, template in enumerate(templates):
            template = amap(template, f"catalogo.{category}[{i}]")
            tid = text(template.get("id"), f"{category}[{i}].id")
            if tid in seen_templates:
                raise RewardMapError(f"template duplicado em {category}: {tid}")
            seen_templates.add(tid)
            text(template.get("nome"), f"{tid}.nome")
            text(template.get("descricao"), f"{tid}.descricao")
            text(template.get("valor_aproximado"), f"{tid}.valor_aproximado")
            minimum = integer(template.get("tier_min"), f"{tid}.tier_min", 1)
            maximum = integer(template.get("tier_max"), f"{tid}.tier_max", minimum)
            if maximum < minimum:
                raise RewardMapError(f"{tid}: tier_max < tier_min")
            importance = text(template.get("importancia"), f"{tid}.importancia")
            if importance not in {"comum", "especial"}:
                raise RewardMapError(f"{tid}: template procedural não pode ser de arco")
            tags = alist(template.get("tags"), f"{tid}.tags")
            for tag in tags:
                text(tag, f"{tid}.tags")
    if data.get("schema_tabelas_recompensas") == 2:
        _validate_budget_v2(data)
    return data


def load_planned(repo: Path) -> dict[str, Any]:
    data = amap(load(repo / PLANNED), str(PLANNED))
    if (
        data.get("schema_recompensas_planejadas") != 1
        or data.get("natureza") != "reservado"
    ):
        raise RewardMapError("catálogo de recompensas planejadas inválido")
    by_place = amap(data.get("por_local"), "por_local")
    for place, entries in by_place.items():
        local_id(place)
        entries = alist(entries, f"por_local.{place}")
        for i, spec in enumerate(entries):
            _validate_planned_spec(spec, f"por_local.{place}[{i}]")
    return data


def _hash_int(seed: str, *parts: Any) -> int:
    raw = "|".join([seed, *(str(part) for part in parts)])
    return int(hashlib.sha256(raw.encode("utf-8")).hexdigest(), 16)


def _choice(seed: str, namespace: str, values: list[Any]) -> Any:
    if not values:
        raise RewardMapError(f"seleção sem candidatos: {namespace}")
    return values[_hash_int(seed, namespace) % len(values)]


def _eligible_templates(
    tables: dict[str, Any],
    category: str,
    tier: int,
) -> list[dict[str, Any]]:
    return [
        template
        for template in tables["catalogo"][category]
        if template["tier_min"] <= tier <= template["tier_max"]
    ]


def _pick_template(
    seed: str,
    place: str,
    tier: int,
    danger: str,
    category: str,
    slot: int,
    candidates: list[dict[str, Any]],
    used: set[str],
) -> dict[str, Any]:
    if not candidates:
        raise RewardMapError(
            f"nenhum template elegível para categoria={category}, tier={tier}"
        )
    ordered = sorted(
        candidates,
        key=lambda item: hashlib.sha256(
            f"{seed}|{place}|{tier}|{danger}|template|{slot}|{item['id']}".encode("utf-8")
        ).hexdigest(),
    )
    for candidate in ordered:
        if candidate["id"] not in used:
            return candidate
    return ordered[0]


def generation_key(
    seed: str,
    place: str,
    tier: int,
    danger: str,
    *,
    generator: str = GENERATOR,
    family: str | None = None,
) -> str:
    parts = [seed, place, str(tier), danger, generator]
    if family is not None:
        parts.append(family)
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def _procedural_possession(seed: str, namespace: str, condition: dict[str, Any]) -> dict[str, str]:
    chosen = _choice(seed, namespace, list(condition["posses"]))
    if chosen == "ambiente":
        return {"tipo": "ambiente"}
    if chosen == "guardiao_local":
        return {"tipo": "papel_local", "papel": "guardiao"}
    if chosen == "ocupante_local":
        return {"tipo": "papel_local", "papel": "ocupante"}
    raise RewardMapError(f"posse procedural desconhecida: {chosen}")


def validate_possession(value: Any, label: str) -> dict[str, Any]:
    value = amap(value, label)
    kind = text(value.get("tipo"), label + ".tipo")
    if kind not in VALID_POSSESSION:
        raise RewardMapError(f"{label}: tipo de posse inválido")
    if kind == "ambiente":
        if set(value) != {"tipo"}:
            raise RewardMapError(f"{label}: ambiente não aceita campos extras")
    elif kind == "papel_local":
        role = text(value.get("papel"), label + ".papel")
        if role not in VALID_LOCAL_ROLES:
            raise RewardMapError(f"{label}: papel_local inválido")
        if set(value) != {"tipo", "papel"}:
            raise RewardMapError(f"{label}: papel_local possui campos extras")
    else:
        npc = text(value.get("npc"), label + ".npc")
        if set(value) != {"tipo", "npc"}:
            raise RewardMapError(f"{label}: npc possui campos extras")
        if not npc:
            raise RewardMapError(f"{label}: npc vazio")
    return value


def _validate_planned_spec(value: Any, label: str) -> dict[str, Any]:
    spec = amap(value, label)
    reward_id(spec.get("id"))
    text(spec.get("tipo"), label + ".tipo")
    text(spec.get("condicao_de_descoberta"), label + ".condicao_de_descoberta")
    validate_possession(spec.get("posse"), label + ".posse")
    importance = text(spec.get("importancia"), label + ".importancia")
    if importance not in VALID_IMPORTANCE:
        raise RewardMapError(f"{label}: importância inválida")
    origin = text(spec.get("origem"), label + ".origem")
    if origin not in VALID_ORIGINS - {"procedural"}:
        raise RewardMapError(f"{label}: recompensa planejada não pode ter origem procedural")
    detail = amap(spec.get("detalhe"), label + ".detalhe")
    text(detail.get("nome"), label + ".detalhe.nome")
    text(detail.get("descricao"), label + ".detalhe.descricao")
    text(detail.get("valor_aproximado"), label + ".detalhe.valor_aproximado")
    for tag in alist(detail.get("tags"), label + ".detalhe.tags"):
        text(tag, label + ".detalhe.tags")
    return spec


def _signed_integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
        raise RewardMapError(f"{label} deve ser inteiro entre {minimum} e {maximum}")
    return value


def _validate_budget_v2(tables: dict[str, Any]) -> dict[str, Any]:
    cfg = amap(tables.get("orcamento_v2"), "orcamento_v2")
    expected = {
        "gerador", "pontos_por_tier", "max_itens_por_tier", "bonus_risco",
        "aumento_teto_valor_risco", "custo_valor", "custo_importancia", "perfis_familia",
    }
    if set(cfg) != expected:
        raise RewardMapError(f"orcamento_v2 possui campos divergentes: {sorted(set(cfg) ^ expected)}")
    if cfg.get("gerador") != GENERATOR_V2:
        raise RewardMapError("orcamento_v2.gerador deve ser deterministico_v2")
    tier_keys = set(tables["tiers"])
    for field in ("pontos_por_tier", "max_itens_por_tier"):
        values = amap(cfg.get(field), f"orcamento_v2.{field}")
        if set(values) != tier_keys:
            raise RewardMapError(f"orcamento_v2.{field} deve cobrir todos os tiers")
        for tier, value in values.items():
            integer(value, f"orcamento_v2.{field}.{tier}", 1)
    if any(value > 4 for value in cfg["max_itens_por_tier"].values()):
        raise RewardMapError("orcamento_v2.max_itens_por_tier não pode exceder 4")
    for field in ("bonus_risco", "aumento_teto_valor_risco"):
        values = amap(cfg.get(field), f"orcamento_v2.{field}")
        if set(values) != VALID_DANGER:
            raise RewardMapError(f"orcamento_v2.{field} deve cobrir todos os riscos")
        for danger, value in values.items():
            integer(value, f"orcamento_v2.{field}.{danger}", 0)
    if amap(cfg.get("custo_valor"), "orcamento_v2.custo_valor") != V2_VALUE_COST:
        raise RewardMapError("orcamento_v2.custo_valor diverge do contrato")
    if amap(cfg.get("custo_importancia"), "orcamento_v2.custo_importancia") != V2_IMPORTANCE_COST:
        raise RewardMapError("orcamento_v2.custo_importancia diverge do contrato")
    profiles = amap(cfg.get("perfis_familia"), "orcamento_v2.perfis_familia")
    if not profiles:
        raise RewardMapError("orcamento_v2.perfis_familia vazio")
    catalog = set(tables["catalogo"])
    for family, raw in profiles.items():
        family = text(family, "familia")
        profile = amap(raw, f"orcamento_v2.perfis_familia.{family}")
        if set(profile) != {"modificador_pontos", "teto_valor_base", "categorias"}:
            raise RewardMapError(f"perfil v2 de {family} possui campos divergentes")
        _signed_integer(profile["modificador_pontos"], f"{family}.modificador_pontos", -2, 2)
        ceiling = text(profile["teto_valor_base"], f"{family}.teto_valor_base")
        if ceiling not in VALUE_RANK:
            raise RewardMapError(f"{family}: teto_valor_base inválido")
        categories = alist(profile["categorias"], f"{family}.categorias")
        if not categories or len(categories) != len(set(categories)):
            raise RewardMapError(f"{family}: categorias vazias ou duplicadas")
        unknown = {text(item, f"{family}.categorias") for item in categories} - catalog
        if unknown:
            raise RewardMapError(f"{family}: categorias fora do catálogo: {sorted(unknown)}")
    return cfg


def _budget_v2_plan(index, tables, ecology, tier, danger):
    if tables.get("schema_tabelas_recompensas") != 2 or not isinstance(ecology, dict):
        return None
    cfg = _validate_budget_v2(tables)
    family = text(ecology.get("familia"), "ecologia.familia")
    profile = cfg["perfis_familia"].get(family)
    if not isinstance(profile, dict):
        raise RewardMapError(f"família ecológica sem perfil Reward Budget v2: {family}")
    tier_key = str(tier)
    points = max(1, int(cfg["pontos_por_tier"][tier_key]) + int(cfg["bonus_risco"][danger]) + int(profile["modificador_pontos"]))
    ceiling_rank = min(max(VALUE_RANK.values()), VALUE_RANK[profile["teto_valor_base"]] + int(cfg["aumento_teto_valor_risco"][danger]))
    max_items = min(int(cfg["max_itens_por_tier"][tier_key]), int(index["orcamento"]["max_procedurais_por_mapa"]))
    allowed = set(profile["categorias"])
    weighted_categories = [category for category in tables["tiers"][tier_key]["categorias"] if category in allowed]
    if not weighted_categories:
        raise RewardMapError(f"{family}: nenhuma categoria v2 compatível com tier {tier}")
    return {
        "familia": family,
        "pontos_total": points,
        "teto_valor": VALUE_BY_RANK[ceiling_rank],
        "teto_valor_rank": ceiling_rank,
        "max_itens": max_items,
        "categorias_ponderadas": weighted_categories,
    }


def _template_budget_cost(template, tables):
    cfg = tables["orcamento_v2"]
    value = text(template.get("valor_aproximado"), f"{template.get('id')}.valor_aproximado")
    importance = text(template.get("importancia"), f"{template.get('id')}.importancia")
    if value not in cfg["custo_valor"] or importance not in cfg["custo_importancia"]:
        raise RewardMapError(f"template {template.get('id')}: custo Reward Budget v2 indefinido")
    return int(cfg["custo_valor"][value]) + int(cfg["custo_importancia"][importance])


def _procedural_count(
    index: dict[str, Any],
    tables: dict[str, Any],
    seed: str,
    place: str,
    tier: int,
    danger: str,
) -> int:
    tier_config = tables["tiers"].get(str(tier))
    if not isinstance(tier_config, dict):
        raise RewardMapError(f"tier sem tabela: {tier}")
    low = tier_config["min"]
    high = tier_config["max"]
    base = low + (_hash_int(seed, place, tier, danger, "quantidade") % (high - low + 1))
    total = base + tables["bonus_periculosidade"][danger]
    return min(total, index["orcamento"]["max_procedurais_por_mapa"])


def _procedural_entries_v1(
    index: dict[str, Any],
    tables: dict[str, Any],
    place: str,
    tier: int,
    danger: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    seed = index["semente"]
    tier_config = tables["tiers"].get(str(tier))
    if not isinstance(tier_config, dict):
        raise RewardMapError(f"tier sem tabela: {tier}")
    count = _procedural_count(index, tables, seed, place, tier, danger)
    used_templates: set[str] = set()
    map_entries: list[dict[str, Any]] = []
    fragments: dict[str, dict[str, Any]] = {}

    for offset in range(count):
        slot = offset + 1
        category = _choice(
            seed,
            f"{place}|{tier}|{danger}|categoria|{slot}",
            list(tier_config["categorias"]),
        )
        candidates = _eligible_templates(tables, category, tier)
        template = _pick_template(
            seed, place, tier, danger, category, slot, candidates, used_templates
        )
        used_templates.add(template["id"])
        condition = _choice(
            seed,
            f"{place}|{tier}|{danger}|condicao|{slot}",
            list(tables["condicoes"]),
        )
        possession = _procedural_possession(
            seed,
            f"{place}|{tier}|{danger}|posse|{slot}",
            condition,
        )
        rid = reward_id(f"{place}-r{slot:02d}")
        item_path = (ITEMS_DIR / f"{rid}.yaml").as_posix()
        map_entries.append(
            {
                "id": rid,
                "tipo": category,
                "estado": "oculto",
                "condicao_de_descoberta": condition["texto"],
                "posse": possession,
                "importancia": template["importancia"],
                "origem": "procedural",
                "arquivo": item_path,
            }
        )
        fragments[rid] = {
            "schema_recompensa": 1,
            "natureza": "reservado",
            "id": rid,
            "local_id": place,
            "tipo": category,
            "nome": template["nome"],
            "descricao": template["descricao"],
            "valor_aproximado": template["valor_aproximado"],
            "importancia": template["importancia"],
            "origem": "procedural",
            "tags": list(template["tags"]),
            "geracao": {
                "modo": "procedural_deterministica",
                "gerador": GENERATOR,
                "template": template["id"],
                "slot": slot,
                "chave": hashlib.sha256(
                    f"{seed}|{place}|{tier}|{danger}|item|{slot}|{template['id']}".encode(
                        "utf-8"
                    )
                ).hexdigest()[:24],
            },
        }
    return map_entries, fragments


def _procedural_entries_v2(index, tables, place, tier, danger, plan):
    seed = index["semente"]
    remaining = int(plan["pontos_total"])
    used_templates = set()
    map_entries = []
    fragments = {}
    weighted = []
    for weight, category in enumerate(plan["categorias_ponderadas"]):
        for template in _eligible_templates(tables, category, tier):
            value = text(template.get("valor_aproximado"), f"{template['id']}.valor_aproximado")
            if value not in VALUE_RANK or VALUE_RANK[value] > plan["teto_valor_rank"]:
                continue
            weighted.append((weight, category, template, _template_budget_cost(template, tables)))
    if not weighted:
        raise RewardMapError(f"{place}: Reward Budget v2 não encontrou template plausível para {plan['familia']}")
    for offset in range(plan["max_itens"]):
        slot = offset + 1
        ordered = sorted(
            weighted,
            key=lambda item: hashlib.sha256(
                f"{seed}|{place}|{tier}|{danger}|{GENERATOR_V2}|{plan['familia']}|slot|{slot}|peso|{item[0]}|categoria|{item[1]}|template|{item[2]['id']}".encode("utf-8")
            ).hexdigest(),
        )
        chosen = next((item for item in ordered if item[2]["id"] not in used_templates and item[3] <= remaining), None)
        if chosen is None:
            break
        _, category, template, cost = chosen
        used_templates.add(template["id"])
        remaining -= cost
        condition = _choice(seed, f"{place}|{tier}|{danger}|{GENERATOR_V2}|condicao|{slot}", list(tables["condicoes"]))
        possession = _procedural_possession(seed, f"{place}|{tier}|{danger}|{GENERATOR_V2}|posse|{slot}", condition)
        rid = reward_id(f"{place}-r{slot:02d}")
        item_path = (ITEMS_DIR / f"{rid}.yaml").as_posix()
        map_entries.append({
            "id": rid, "tipo": category, "estado": "oculto",
            "condicao_de_descoberta": condition["texto"], "posse": possession,
            "importancia": template["importancia"], "origem": "procedural", "arquivo": item_path,
        })
        fragments[rid] = {
            "schema_recompensa": 1, "natureza": "reservado", "id": rid,
            "local_id": place, "tipo": category, "nome": template["nome"],
            "descricao": template["descricao"], "valor_aproximado": template["valor_aproximado"],
            "importancia": template["importancia"], "origem": "procedural", "tags": list(template["tags"]),
            "geracao": {
                "modo": "procedural_deterministica", "gerador": GENERATOR_V2,
                "template": template["id"], "slot": slot, "custo_orcamento": cost,
                "familia_local": plan["familia"],
                "chave": hashlib.sha256(
                    f"{seed}|{place}|{tier}|{danger}|{GENERATOR_V2}|{plan['familia']}|item|{slot}|{template['id']}".encode("utf-8")
                ).hexdigest()[:24],
            },
        }
    return map_entries, fragments


def _planned_entries(
    planned: dict[str, Any],
    place: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    map_entries: list[dict[str, Any]] = []
    fragments: dict[str, dict[str, Any]] = {}
    for spec in planned["por_local"].get(place, []):
        spec = _validate_planned_spec(spec, f"planejadas.{place}")
        rid = reward_id(spec["id"])
        item_path = (ITEMS_DIR / f"{rid}.yaml").as_posix()
        map_entries.append(
            {
                "id": rid,
                "tipo": spec["tipo"],
                "estado": "oculto",
                "condicao_de_descoberta": spec["condicao_de_descoberta"],
                "posse": dict(spec["posse"]),
                "importancia": spec["importancia"],
                "origem": spec["origem"],
                "arquivo": item_path,
            }
        )
        detail = spec["detalhe"]
        fragments[rid] = {
            "schema_recompensa": 1,
            "natureza": "reservado",
            "id": rid,
            "local_id": place,
            "tipo": spec["tipo"],
            "nome": detail["nome"],
            "descricao": detail["descricao"],
            "valor_aproximado": detail["valor_aproximado"],
            "importancia": spec["importancia"],
            "origem": spec["origem"],
            "tags": list(detail["tags"]),
            "geracao": {"modo": "planejada"},
        }
    return map_entries, fragments


def generate_map(
    index: dict[str, Any],
    tables: dict[str, Any],
    planned: dict[str, Any],
    place: str,
    tier: int,
    danger: str,
    *,
    ecology: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    place = local_id(place)
    if danger not in VALID_DANGER:
        raise RewardMapError("periculosidade deve ser baixa, media, alta ou letal")
    integer(tier, "tier", 1)
    if str(tier) not in tables["tiers"]:
        raise RewardMapError(f"tier sem tabela: {tier}")

    budget_v2 = _budget_v2_plan(index, tables, ecology, tier, danger)
    if budget_v2 is None:
        procedural_entries, procedural_fragments = _procedural_entries_v1(index, tables, place, tier, danger)
    else:
        procedural_entries, procedural_fragments = _procedural_entries_v2(index, tables, place, tier, danger, budget_v2)
    planned_entries, planned_fragments = _planned_entries(planned, place)
    entries = procedural_entries + planned_entries
    if len(entries) > index["orcamento"]["max_totais_por_mapa"]:
        raise RewardMapError(
            f"{place}: {len(entries)} recompensas excedem max_totais_por_mapa="
            f"{index['orcamento']['max_totais_por_mapa']}"
        )
    ids = [item["id"] for item in entries]
    if len(ids) != len(set(ids)):
        raise RewardMapError(f"{place}: IDs de recompensa duplicados")

    fragments = {**procedural_fragments, **planned_fragments}
    generator = GENERATOR_V2 if budget_v2 is not None else GENERATOR
    key = generation_key(index["semente"], place, tier, danger, generator=generator, family=budget_v2["familia"] if budget_v2 is not None else None)
    generation = {
        "modo": generator, "chave": key, "imutavel": True,
        "procedurais": len(procedural_entries), "planejadas": len(planned_entries),
    }
    if budget_v2 is not None:
        spent = sum(int(fragment["geracao"]["custo_orcamento"]) for fragment in procedural_fragments.values())
        generation["orcamento_v2"] = {
            "familia_local": budget_v2["familia"], "pontos_total": budget_v2["pontos_total"],
            "pontos_gastos": spent, "pontos_restantes": budget_v2["pontos_total"] - spent,
            "teto_valor": budget_v2["teto_valor"], "max_itens": budget_v2["max_itens"],
        }
    result = {
        "schema_mapa_recompensas": 1,
        "natureza": "reservado",
        "local_id": place,
        "tier": tier,
        "periculosidade": danger,
        "geracao": generation,
        "regra_descoberta": "existir_no_mapa_nao_significa_que_ren_encontrou",
        "recompensas": entries,
    }
    return result, fragments


def validate_map(
    repo: Path,
    place: str,
    meta: dict[str, Any],
    *,
    load_fragments: bool = False,
) -> dict[str, Any]:
    place = local_id(place)
    raw = text(meta.get("arquivo"), f"mapas.{place}.arquivo")
    path = repo_path(repo, raw, MAPS_DIR)
    data = amap(load(path), raw)
    if (
        data.get("schema_mapa_recompensas") != 1
        or data.get("natureza") != "reservado"
        or data.get("local_id") != place
    ):
        raise RewardMapError(f"{place}: mapa inválido")
    if data.get("tier") != meta.get("tier") or data.get("periculosidade") != meta.get(
        "periculosidade"
    ):
        raise RewardMapError(f"{place}: mapa diverge do índice")
    generation = amap(data.get("geracao"), f"{place}.geracao")
    generator = generation.get("modo")
    if (generator not in VALID_GENERATORS or generation.get("chave") != meta.get("chave_geracao") or generation.get("imutavel") is not True):
        raise RewardMapError(f"{place}: metadados de geração inválidos")
    if generator == GENERATOR_V2:
        budget = amap(generation.get("orcamento_v2"), f"{place}.geracao.orcamento_v2")
        required = {"familia_local", "pontos_total", "pontos_gastos", "pontos_restantes", "teto_valor", "max_itens"}
        if set(budget) != required:
            raise RewardMapError(f"{place}: resumo Reward Budget v2 inválido")
        total = integer(budget["pontos_total"], f"{place}.pontos_total", 1)
        spent = integer(budget["pontos_gastos"], f"{place}.pontos_gastos", 0)
        remaining = integer(budget["pontos_restantes"], f"{place}.pontos_restantes", 0)
        if spent + remaining != total:
            raise RewardMapError(f"{place}: aritmética Reward Budget v2 inválida")
        if text(budget["teto_valor"], f"{place}.teto_valor") not in VALUE_RANK:
            raise RewardMapError(f"{place}: teto de valor v2 inválido")
        integer(budget["max_itens"], f"{place}.max_itens", 1)
        text(budget["familia_local"], f"{place}.familia_local")
    if data.get("regra_descoberta") != "existir_no_mapa_nao_significa_que_ren_encontrou":
        raise RewardMapError(f"{place}: regra de descoberta ausente")
    entries = alist(data.get("recompensas"), f"{place}.recompensas")
    if len(entries) != meta.get("quantidade"):
        raise RewardMapError(f"{place}: quantidade diverge do índice")
    seen: set[str] = set()
    for i, item in enumerate(entries):
        item = amap(item, f"{place}.recompensas[{i}]")
        rid = reward_id(item.get("id"))
        if rid in seen:
            raise RewardMapError(f"{place}: recompensa duplicada {rid}")
        seen.add(rid)
        text(item.get("tipo"), f"{rid}.tipo")
        state = text(item.get("estado"), f"{rid}.estado")
        if state not in VALID_STATES:
            raise RewardMapError(f"{rid}: estado inválido")
        text(item.get("condicao_de_descoberta"), f"{rid}.condicao_de_descoberta")
        validate_possession(item.get("posse"), f"{rid}.posse")
        importance = text(item.get("importancia"), f"{rid}.importancia")
        origin = text(item.get("origem"), f"{rid}.origem")
        if importance not in VALID_IMPORTANCE or origin not in VALID_ORIGINS:
            raise RewardMapError(f"{rid}: importância/origem inválida")
        if origin == "procedural" and importance == "arco":
            raise RewardMapError(f"{rid}: recompensa procedural não pode ser de arco")
        item_path = text(item.get("arquivo"), f"{rid}.arquivo")
        repo_path(repo, item_path, ITEMS_DIR)
        if load_fragments:
            fragment = validate_fragment(repo, rid, item_path)
            if (
                fragment["local_id"] != place
                or fragment["tipo"] != item["tipo"]
                or fragment["importancia"] != importance
                or fragment["origem"] != origin
            ):
                raise RewardMapError(f"{rid}: fragmento diverge do mapa")
    return data


def validate_fragment(repo: Path, rid: str, raw: str) -> dict[str, Any]:
    rid = reward_id(rid)
    data = amap(load(repo_path(repo, raw, ITEMS_DIR)), raw)
    if (
        data.get("schema_recompensa") != 1
        or data.get("natureza") != "reservado"
        or data.get("id") != rid
    ):
        raise RewardMapError(f"{rid}: fragmento inválido")
    local_id(data.get("local_id"))
    text(data.get("tipo"), f"{rid}.tipo")
    text(data.get("nome"), f"{rid}.nome")
    text(data.get("descricao"), f"{rid}.descricao")
    text(data.get("valor_aproximado"), f"{rid}.valor_aproximado")
    importance = text(data.get("importancia"), f"{rid}.importancia")
    origin = text(data.get("origem"), f"{rid}.origem")
    if importance not in VALID_IMPORTANCE or origin not in VALID_ORIGINS:
        raise RewardMapError(f"{rid}: importância/origem inválida")
    if origin == "procedural" and importance == "arco":
        raise RewardMapError(f"{rid}: recompensa procedural de arco proibida")
    for tag in alist(data.get("tags"), f"{rid}.tags"):
        text(tag, f"{rid}.tags")
    generation = amap(data.get("geracao"), f"{rid}.geracao")
    mode = text(generation.get("modo"), f"{rid}.geracao.modo")
    if origin == "procedural":
        generator = generation.get("gerador")
        if (mode != "procedural_deterministica" or generator not in VALID_GENERATORS or not isinstance(generation.get("slot"), int) or generation.get("slot") < 1):
            raise RewardMapError(f"{rid}: proveniência procedural inválida")
        text(generation.get("template"), f"{rid}.geracao.template")
        text(generation.get("chave"), f"{rid}.geracao.chave")
        if generator == GENERATOR_V2:
            integer(generation.get("custo_orcamento"), f"{rid}.geracao.custo_orcamento", 1)
            text(generation.get("familia_local"), f"{rid}.geracao.familia_local")
    elif mode != "planejada":
        raise RewardMapError(f"{rid}: recompensa não procedural deve ser planejada")
    return data


def _compact_map(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "local_id": data["local_id"],
        "tier": data["tier"],
        "periculosidade": data["periculosidade"],
        "quantidade": len(data["recompensas"]),
        "elegiveis": [
            {
                "id": item["id"],
                "tipo": item["tipo"],
                "estado": item["estado"],
                "condicao_de_descoberta": item["condicao_de_descoberta"],
                "posse": item["posse"],
                "importancia": item["importancia"],
                "origem": item["origem"],
            }
            for item in data["recompensas"]
            if item["estado"] in {"oculto", "descoberto"}
        ],
        "regra": "item existir no mapa não significa que Ren o encontrou",
    }


def consult(repo: Path, place: str) -> dict[str, Any]:
    place = local_id(place)
    index = load_index(repo)
    meta = index["mapas"].get(place)
    if meta is None:
        return {
            "ok": True,
            "mapa_existe": False,
            "local_id": place,
            "acao": "gerar_uma_vez_se_a_exploracao_exigir",
            "fontes_lidas": [INDEX.as_posix()],
        }
    data = validate_map(repo, place, meta)
    return {
        "ok": True,
        "mapa_existe": True,
        "mapa": _compact_map(data),
        "fontes_lidas": [INDEX.as_posix(), meta["arquivo"]],
    }


def ensure(
    repo: Path,
    place: str,
    tier: int,
    danger: str,
    *,
    ecology: dict[str, Any] | None = None,
) -> dict[str, Any]:
    place = local_id(place)
    if danger not in VALID_DANGER:
        raise RewardMapError("periculosidade deve ser baixa, media, alta ou letal")
    integer(tier, "tier", 1)
    index = load_index(repo)
    existing = index["mapas"].get(place)
    if existing is not None:
        data = validate_map(repo, place, existing)
        return {
            "ok": True,
            "criado": False,
            "mapa": _compact_map(data),
            "observacao": "mapa existente reutilizado; tier/periculosidade recebidos não rerrolam a área",
            "fontes_lidas": [INDEX.as_posix(), existing["arquivo"]],
        }

    ecology_sources: list[str] = []
    if ecology is None and (repo / ecologia_local.INDEX).is_file():
        try:
            ecology_lookup = ecologia_local.lookup_canonical(repo, place)
        except ecologia_local.LocalEcologyError as exc:
            raise RewardMapError(str(exc)) from exc
        ecology = ecology_lookup["perfil"]
        ecology_sources.extend(ecology_lookup["fontes_lidas"])
    tables = load_tables(repo)
    planned = load_planned(repo)
    item_index = load_item_index(repo)
    data, fragments = generate_map(index, tables, planned, place, tier, danger, ecology=ecology)
    map_path = (MAPS_DIR / f"{place}.yaml").as_posix()

    for item in data["recompensas"]:
        rid = item["id"]
        install_once(repo / item["arquivo"], fragments[rid])
    install_once(repo / map_path, data)

    # Ordem deliberada: índice dirigido primeiro, índice de mapas por último.
    # Se cair entre ambos, nova execução regenera os mesmos bytes e repara o
    # índice final sem rerrolar.
    for item in data["recompensas"]:
        rid = item["id"]
        expected = {
            "local_id": place,
            "mapa": map_path,
            "arquivo": item["arquivo"],
        }
        current = item_index["recompensas"].get(rid)
        if current is not None and current != expected:
            raise RewardMapError(f"ID global de recompensa já pertence a outro artefato: {rid}")
        item_index["recompensas"][rid] = expected
    atomic(repo / ITEM_INDEX, item_index)

    meta = {
        "arquivo": map_path,
        "tier": tier,
        "periculosidade": danger,
        "quantidade": len(data["recompensas"]),
        "chave_geracao": data["geracao"]["chave"],
    }
    index["mapas"][place] = meta
    atomic(repo / INDEX, index)
    return {
        "ok": True,
        "criado": True,
        "mapa": _compact_map(data),
        "fontes_lidas": [
            INDEX.as_posix(),
            TABLES.as_posix(),
            PLANNED.as_posix(),
            ITEM_INDEX.as_posix(),
            *ecology_sources,
        ],
        "arquivos_criados": [
            map_path,
            *(item["arquivo"] for item in data["recompensas"]),
        ],
    }


def show(repo: Path, query: str) -> dict[str, Any]:
    rid = reward_id(query)
    item_index = load_item_index(repo)
    meta = item_index["recompensas"].get(rid)
    if meta is None:
        raise RewardMapError(f"recompensa não encontrada: {rid}")
    map_data = amap(load(repo_path(repo, meta["mapa"], MAPS_DIR)), meta["mapa"])
    entry = next(
        (item for item in map_data.get("recompensas", []) if item.get("id") == rid),
        None,
    )
    if not isinstance(entry, dict):
        raise RewardMapError(f"{rid}: índice aponta para mapa sem a recompensa")
    detail = validate_fragment(repo, rid, meta["arquivo"])
    return {
        "ok": True,
        "recompensa_id": rid,
        "operacional": {
            "local_id": meta["local_id"],
            "estado": entry["estado"],
            "condicao_de_descoberta": entry["condicao_de_descoberta"],
            "posse": entry["posse"],
            "importancia": entry["importancia"],
            "origem": entry["origem"],
        },
        "detalhe": detail,
        "fontes_lidas": [ITEM_INDEX.as_posix(), meta["mapa"], meta["arquivo"]],
    }


def status(repo: Path) -> dict[str, Any]:
    index = load_index(repo)
    maps = index["mapas"]
    return {
        "ok": True,
        "mapas": len(maps),
        "recompensas_indexadas": sum(meta["quantidade"] for meta in maps.values()),
        "locais": sorted(maps),
        "fontes_lidas": [INDEX.as_posix()],
    }


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    counts = {"mapas": 0, "recompensas": 0, "procedurais": 0, "planejadas": 0}
    try:
        index = load_index(repo)
        item_index = load_item_index(repo)
        load_tables(repo)
        load_planned(repo)
        seen: dict[str, tuple[str, str]] = {}

        for place, meta in index["mapas"].items():
            data = validate_map(repo, place, meta, load_fragments=True)
            counts["mapas"] += 1
            for item in data["recompensas"]:
                rid = item["id"]
                counts["recompensas"] += 1
                if item["origem"] == "procedural":
                    counts["procedurais"] += 1
                else:
                    counts["planejadas"] += 1
                if rid in seen:
                    raise RewardMapError(
                        f"recompensa {rid} aparece em dois mapas: {seen[rid][0]} e {place}"
                    )
                seen[rid] = (place, item["arquivo"])
                expected = {
                    "local_id": place,
                    "mapa": meta["arquivo"],
                    "arquivo": item["arquivo"],
                }
                if item_index["recompensas"].get(rid) != expected:
                    raise RewardMapError(f"{rid}: índice dirigido diverge do mapa")

        extra_indexed = sorted(set(item_index["recompensas"]) - set(seen))
        if extra_indexed:
            raise RewardMapError(
                "índice dirigido contém recompensas sem mapa: " + ", ".join(extra_indexed)
            )

        map_files = {
            path.relative_to(repo).as_posix()
            for path in (repo / MAPS_DIR).glob("*.yaml")
            if path.is_file()
        } if (repo / MAPS_DIR).is_dir() else set()
        indexed_maps = {meta["arquivo"] for meta in index["mapas"].values()}
        if map_files != indexed_maps:
            raise RewardMapError(
                f"arquivos de mapa divergem do índice; "
                f"órfãos={sorted(map_files-indexed_maps)}, ausentes={sorted(indexed_maps-map_files)}"
            )

        item_files = {
            path.relative_to(repo).as_posix()
            for path in (repo / ITEMS_DIR).glob("*.yaml")
            if path.is_file()
        } if (repo / ITEMS_DIR).is_dir() else set()
        indexed_items = {meta["arquivo"] for meta in item_index["recompensas"].values()}
        if item_files != indexed_items:
            raise RewardMapError(
                f"fragmentos divergem do índice; "
                f"órfãos={sorted(item_files-indexed_items)}, ausentes={sorted(indexed_items-item_files)}"
            )
    except RewardMapError as exc:
        errors.append(str(exc))
    return {"ok": not errors, "erros": errors, **counts}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[1]
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p_consult = sub.add_parser("consultar", help="consulta compacta por local")
    p_consult.add_argument("local_id")

    p_ensure = sub.add_parser("garantir", help="cria uma vez ou reutiliza mapa existente")
    p_ensure.add_argument("local_id")
    p_ensure.add_argument("--tier", type=int, required=True)
    p_ensure.add_argument(
        "--periculosidade", choices=sorted(VALID_DANGER), required=True
    )

    p_show = sub.add_parser("mostrar", help="abre um único fragmento de recompensa")
    p_show.add_argument("recompensa_id")

    sub.add_parser("status", help="mostra somente o índice compacto")
    sub.add_parser("check", help="validação ampla para CI/manutenção")

    args = parser.parse_args()
    repo = args.repo.resolve()
    try:
        if args.comando == "consultar":
            result = consult(repo, args.local_id)
        elif args.comando == "garantir":
            result = ensure(repo, args.local_id, args.tier, args.periculosidade)
        elif args.comando == "mostrar":
            result = show(repo, args.recompensa_id)
        elif args.comando == "status":
            result = status(repo)
        else:
            result = validate_repo(repo)
    except RewardMapError as exc:
        print(_dump({"ok": False, "erro": str(exc)}), end="")
        return 1

    print(_dump(result), end="")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
