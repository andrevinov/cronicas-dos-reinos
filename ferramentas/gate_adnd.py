#!/usr/bin/env python3
"""Gate formal de proveniência mecânica para material de AD&D.

Lore, aventura e prosa histórica de AD&D continuam livres. O gate só atua quando
um artefato se declara mecanicamente ativo/preparado ou quando ``cronica`` recebe
proveniência AD&D em um contrato mecânico. Nesses casos a origem antiga precisa
ser separada da autoridade mecânica moderna: edição de origem, ruleset de destino
e fonte mecânica são obrigatórios; mecânica literal de AD&D é recusada.
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path
from typing import Any, Iterable

import yaml

SCHEMA = 1
REGISTRY_PATH = Path("regras/adaptacoes-mecanicas.yaml")
CAMPAIGN_PATH = Path("campanha.yaml")
ADND_EDITIONS = {"adnd_1e", "adnd_2e"}
MODERN_RULESETS = {"dnd_5e_2014", "dnd_5_5e"}
ACTIVE_STATES = {"ativo", "preparacao"}

# Chaves suficientemente específicas para representar transporte literal de
# mecânica AD&D. O scanner só é aplicado a material explicitamente mecânico
# derivado de AD&D; prosa narrativa não é inspecionada por heurística.
LEGACY_KEYS = {
    "thac0",
    "thaco",
    "armor_class_descending",
    "ac_descending",
    "classe_armadura_descendente",
    "saving_throw_table",
    "saving_throws_adnd",
    "salvamentos_adnd",
    "save_vs_paralyzation",
    "save_vs_poison",
    "save_vs_death_magic",
    "save_vs_rod_staff_wand",
    "save_vs_petrification_polymorph",
    "save_vs_breath_weapon",
    "save_vs_spell",
    "hit_dice_adnd",
    "movement_adnd",
    "morale_adnd",
    "xp_value_adnd",
}
LEGACY_TEXT_PATTERNS = (
    re.compile(r"\bthac0\b", re.IGNORECASE),
    re.compile(
        r"\bsave\s+vs\.?\s+(?:paraly|poison|death|rod|staff|wand|petrif|breath|spell)",
        re.IGNORECASE,
    ),
)


class ADNDGateError(ValueError):
    """Material antigo não satisfaz o contrato de adaptação mecânica."""


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ADNDGateError(f"{label} precisa ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ADNDGateError(f"{label} precisa ser lista")
    return value


def _text(value: Any, label: str, *, maximum: int = 600) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ADNDGateError(f"{label} precisa ser texto não vazio")
    text = " ".join(value.split())
    if len(text) > maximum:
        raise ADNDGateError(f"{label} excede {maximum} caracteres")
    return text


def _key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _campaign_ruleset(repo: Path) -> str:
    try:
        campaign = yaml.safe_load((repo / CAMPAIGN_PATH).read_text(encoding="utf-8")) or {}
        current = campaign["sistema"]["ruleset"]["atual"]
    except (OSError, yaml.YAMLError, KeyError, TypeError) as exc:
        raise ADNDGateError("não foi possível determinar sistema.ruleset.atual") from exc
    current = _text(current, "sistema.ruleset.atual", maximum=80)
    if current not in MODERN_RULESETS:
        raise ADNDGateError(f"ruleset atual não suportado pelo gate AD&D: {current}")
    return current


def _legacy_hits(value: Any, path: str = "mecanica") -> list[str]:
    hits: list[str] = []
    if isinstance(value, dict):
        for raw_key, child in value.items():
            normalized = _key(raw_key)
            child_path = f"{path}.{raw_key}"
            if normalized in LEGACY_KEYS:
                hits.append(child_path)
            hits.extend(_legacy_hits(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            hits.extend(_legacy_hits(child, f"{path}[{index}]"))
    elif isinstance(value, str):
        if any(pattern.search(value) for pattern in LEGACY_TEXT_PATTERNS):
            hits.append(path)
    return hits


def reject_literal_adnd_mechanics(value: Any, *, label: str = "mecanica") -> None:
    hits = _legacy_hits(value, label)
    if hits:
        shown = ", ".join(hits[:6])
        suffix = " ..." if len(hits) > 6 else ""
        raise ADNDGateError(
            "mecânica AD&D literal proibida; converta para o ruleset de destino antes do runtime: "
            f"{shown}{suffix}"
        )


def normalize_provenance(
    repo: Path,
    raw: Any,
    *,
    for_runtime: bool = False,
) -> dict[str, Any]:
    """Valida metadados de uma adaptação AD&D e devolve forma canônica."""
    data = _map(raw, "proveniencia_mecanica")
    allowed = {
        "edicao_origem",
        "adaptado_para",
        "fonte_mecanica",
        "decisao",
        "fallback_2014",
    }
    extra = set(data) - allowed
    if extra:
        raise ADNDGateError(f"campos de proveniência desconhecidos: {sorted(extra)}")

    origin = _text(data.get("edicao_origem"), "edicao_origem", maximum=80)
    if origin not in ADND_EDITIONS:
        raise ADNDGateError(
            f"edicao_origem precisa ser uma edição AD&D conhecida: {sorted(ADND_EDITIONS)}"
        )
    target = _text(data.get("adaptado_para"), "adaptado_para", maximum=80)
    if target not in MODERN_RULESETS:
        raise ADNDGateError(f"adaptado_para inválido: {target!r}")

    source = _map(data.get("fonte_mecanica"), "fonte_mecanica")
    if set(source) != {"ruleset", "referencia"}:
        raise ADNDGateError("fonte_mecanica exige exatamente ruleset e referencia")
    source_ruleset = _text(source.get("ruleset"), "fonte_mecanica.ruleset", maximum=80)
    reference = _text(source.get("referencia"), "fonte_mecanica.referencia")
    if source_ruleset != target:
        raise ADNDGateError(
            "fonte_mecanica.ruleset precisa coincidir com adaptado_para: "
            f"{source_ruleset!r} != {target!r}"
        )

    decision_raw = data.get("decisao")
    decision = None if decision_raw is None else _text(decision_raw, "decisao", maximum=180)
    fallback_raw = data.get("fallback_2014")
    fallback: dict[str, Any] | None = None
    if target == "dnd_5e_2014":
        fallback_map = _map(fallback_raw, "fallback_2014")
        if set(fallback_map) != {"declarado", "motivo", "decisao"}:
            raise ADNDGateError(
                "fallback_2014 exige exatamente declarado, motivo e decisao"
            )
        if fallback_map.get("declarado") is not True:
            raise ADNDGateError("uso excepcional de mecânica 2014 exige fallback_2014.declarado=true")
        fallback = {
            "declarado": True,
            "motivo": _text(fallback_map.get("motivo"), "fallback_2014.motivo", maximum=320),
            "decisao": _text(fallback_map.get("decisao"), "fallback_2014.decisao", maximum=180),
        }
    elif fallback_raw is not None:
        raise ADNDGateError("fallback_2014 só pode existir quando adaptado_para=dnd_5e_2014")

    if for_runtime:
        current = _campaign_ruleset(repo)
        if target != current:
            raise ADNDGateError(
                "adaptação AD&D não pode entrar no runtime deste ruleset: "
                f"adaptado_para={target}, ruleset.atual={current}"
            )

    result: dict[str, Any] = {
        "schema_gate_adnd": SCHEMA,
        "edicao_origem": origin,
        "adaptado_para": target,
        "fonte_mecanica": {"ruleset": source_ruleset, "referencia": reference},
    }
    if decision is not None:
        result["decisao"] = decision
    if fallback is not None:
        result["fallback_2014"] = fallback
    return result


def validate_runtime_provenance(repo: Path, raw: Any, mechanical_value: Any) -> dict[str, Any]:
    """Gate usado por ``cronica`` antes de uma adaptação AD&D virar ticket."""
    provenance = normalize_provenance(repo, raw, for_runtime=True)
    reject_literal_adnd_mechanics(mechanical_value)
    return provenance


def validate_material(repo: Path, raw: Any, *, for_runtime: bool = False) -> dict[str, Any]:
    """Valida um artefato preparado. Narrativa AD&D continua explicitamente livre."""
    material = _map(raw, "material")
    active = material.get("mecanica_ativa") is True
    provenance_raw = material.get("proveniencia_mecanica")

    if not active:
        if provenance_raw is None:
            return {"mecanica_ativa": False, "resultado": "narrativa_ou_inativo"}
        provenance = normalize_provenance(repo, provenance_raw, for_runtime=for_runtime)
        return {
            "mecanica_ativa": False,
            "resultado": "proveniencia_preparada_sem_runtime",
            "proveniencia_mecanica": provenance,
        }

    if provenance_raw is None:
        raise ADNDGateError("material mecânico ativo de AD&D exige proveniencia_mecanica")
    if "mecanica" not in material:
        raise ADNDGateError("material mecânico ativo de AD&D exige bloco mecanica")
    provenance = normalize_provenance(repo, provenance_raw, for_runtime=for_runtime)
    reject_literal_adnd_mechanics(material.get("mecanica"))
    return {
        "mecanica_ativa": True,
        "resultado": "adaptacao_mecanica_validada",
        "proveniencia_mecanica": provenance,
    }


def _walk_maps(value: Any, path: str = "$") -> Iterable[tuple[str, dict[str, Any]]]:
    if isinstance(value, dict):
        yield path, value
        for key, child in value.items():
            yield from _walk_maps(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_maps(child, f"{path}[{index}]")


def validate_registry(repo: Path, document: Any | None = None) -> list[str]:
    errors: list[str] = []
    if document is None:
        path = repo / REGISTRY_PATH
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            return [f"registro de adaptações AD&D inválido: {exc}"]
    if not isinstance(document, dict):
        return ["registro de adaptações AD&D precisa ser mapa YAML"]
    if document.get("schema_gate_adnd") != SCHEMA:
        errors.append("regras/adaptacoes-mecanicas.yaml exige schema_gate_adnd: 1")
    if document.get("natureza") != "registro_adaptacoes_mecanicas":
        errors.append("registro AD&D perdeu natureza=registro_adaptacoes_mecanicas")
    materials = document.get("materiais")
    if not isinstance(materials, list):
        return errors + ["registro AD&D exige lista materiais"]
    seen: set[str] = set()
    for index, item in enumerate(materials):
        if not isinstance(item, dict):
            errors.append(f"materiais[{index}] precisa ser mapa")
            continue
        item_id = item.get("id")
        if not isinstance(item_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", item_id):
            errors.append(f"materiais[{index}].id inválido: {item_id!r}")
            continue
        if item_id in seen:
            errors.append(f"id de adaptação AD&D duplicado: {item_id}")
            continue
        seen.add(item_id)
        status = item.get("status")
        if status not in {"ativo", "preparacao", "arquivado"}:
            errors.append(f"{item_id}: status inválido: {status!r}")
            continue
        if status not in ACTIVE_STATES:
            continue
        candidate = dict(item)
        candidate["mecanica_ativa"] = True
        try:
            validate_material(repo, candidate, for_runtime=False)
        except ADNDGateError as exc:
            errors.append(f"{item_id}: {exc}")
    return errors


def validate_repository(repo: Path, yaml_docs: dict[str, Any] | None = None) -> list[str]:
    """Subgate de Integridade: registro + material AD&D ativo versionado."""
    errors: list[str] = []
    registry_doc = None if yaml_docs is None else yaml_docs.get(REGISTRY_PATH.as_posix())
    errors.extend(validate_registry(repo, registry_doc))

    if yaml_docs is None:
        yaml_docs = {}
        for path in repo.rglob("*.y*ml"):
            if ".git" in path.parts:
                continue
            try:
                yaml_docs[path.relative_to(repo).as_posix()] = yaml.safe_load(
                    path.read_text(encoding="utf-8")
                )
            except (OSError, yaml.YAMLError):
                continue

    for rel, document in yaml_docs.items():
        if rel == REGISTRY_PATH.as_posix():
            continue
        for node_path, node in _walk_maps(document):
            provenance = node.get("proveniencia_mecanica")
            origin_hint = None
            if isinstance(provenance, dict):
                origin_hint = provenance.get("edicao_origem")
            # Fora do registro dedicado, não sequestrar a chave genérica
            # mecanica_ativa de material nativo. Só inspecionar documentos que
            # já se identificam como derivados de AD&D.
            if origin_hint not in ADND_EDITIONS:
                continue
            try:
                validate_material(repo, node, for_runtime=False)
            except ADNDGateError as exc:
                errors.append(f"{rel}:{node_path}: {exc}")
    return errors


def check(repo: Path) -> dict[str, Any]:
    errors = validate_repository(repo)
    return {
        "ok": not errors,
        "erros": errors,
        "contrato": {
            "narrativa_adnd": "livre",
            "mecanica_adnd_literal_runtime": "proibida",
            "origens": sorted(ADND_EDITIONS),
            "destinos": sorted(MODERN_RULESETS),
            "alvo_preferencial_migracao": "dnd_5_5e",
            "fallback_2014": "declaracao+motivo+decisao obrigatorios",
            "registro": REGISTRY_PATH.as_posix(),
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["check"], default="check")
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    result = check(args.repo.resolve())
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
