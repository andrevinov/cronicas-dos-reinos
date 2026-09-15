#!/usr/bin/env python3
"""Valida o contrato modular v2 e protege a comparabilidade das séries.

Este módulo é exclusivamente pós-hoc. Ele não lê nem altera estado canônico e
não participa do hot path de narração.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = ROOT / "evaluation" / "catalogo-modulos-v2.json"
DEFAULT_GUARDRAILS = ROOT / "evaluation" / "catalogo-guardrails-v2.json"
DEFAULT_SERIES_POLICY = ROOT / "evaluation" / "series-avaliacao.json"
DEFAULT_RELEASES = ROOT / "evaluation" / "module-releases.json"
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")

MODULE_IDS = frozenset(
    {
        "context_and_memory",
        "turn_and_session_orchestration",
        "narrative_delivery",
        "rules_and_character_state",
        "sidequest_authoring",
        "sidequest_lifecycle",
        "canonical_quest_integration",
        "npc_continuity_and_social_behavior",
        "scene_world_projection",
        "world_boundary_resolution",
        "causal_narrative_routing",
        "adversarial_operations",
    }
)

V1_ITEM_IDS = frozenset(
    {
        "emergent_sidequest_opportunity",
        "emergent_sidequest_authoring",
        "active_sidequest_reassessment",
        "transactional_sidequest_progress",
        "sidequest_progression",
        "quest_rewards",
        "sidequest_success_reactions",
        "canon_bridge",
        "canonical_secret_quests",
        "npc_social_initiative",
        "world_local_incidents",
        "persistent_world_conditions",
        "liveness_boundary",
        "batch_world_boundary",
        "reactive_pressure_routing",
        "secret_canon",
        "adversarial_integrity",
        "concurrent_adversarial_operations",
        "seven_names_migration_regression",
        "underground_tournament",
    }
)

NON_MODULE_V1_IDS = frozenset(
    {"seven_names_migration_regression", "underground_tournament"}
)
ANALYSIS_UNITS = frozenset({"turno", "cena", "fronteira", "sessao", "evento"})
PLAYER_VISIBILITIES = frozenset({"direta", "indireta", "tecnica", "reservada"})
SERIES_IDS = frozenset({"legacy-v1", "modules-v2"})


class EvaluationCatalogError(ValueError):
    """Indica violação do contrato estrutural de avaliação."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationCatalogError(f"não foi possível ler {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvaluationCatalogError(f"{path} precisa conter um objeto JSON")
    return value


def _required_text(value: dict[str, Any], key: str, owner: str) -> str:
    item = value.get(key)
    if not isinstance(item, str) or not item.strip():
        raise EvaluationCatalogError(f"{owner}: {key} é obrigatório")
    return item


def _required_nonempty_list(value: dict[str, Any], key: str, owner: str) -> list[Any]:
    item = value.get(key)
    if not isinstance(item, list) or not item:
        raise EvaluationCatalogError(f"{owner}: {key} precisa ser uma lista não vazia")
    return item


def validate_catalog_v2(catalog: dict[str, Any]) -> None:
    """Valida estrutura e invariantes sem depender de pacote externo de schema."""

    if catalog.get("schema_catalogo_modulos") != 2:
        raise EvaluationCatalogError("schema_catalogo_modulos precisa ser 2")
    if catalog.get("serie_avaliacao") != "modules-v2":
        raise EvaluationCatalogError("o catálogo v2 precisa declarar serie_avaliacao=modules-v2")
    if catalog.get("padrao_producao") is not True or catalog.get("estado") != "producao":
        raise EvaluationCatalogError("modules-v2 precisa ser o padrão de produção depois da RM-11")

    coverage = catalog.get("contrato_cobertura_fail_closed")
    if not isinstance(coverage, dict) or coverage.get("schema") != 1:
        raise EvaluationCatalogError(
            "catálogo precisa declarar contrato_cobertura_fail_closed schema 1"
        )
    covered_modules = coverage.get("modulos")
    if not isinstance(covered_modules, list) or set(covered_modules) != MODULE_IDS:
        raise EvaluationCatalogError(
            "contrato fail-closed precisa cobrir exatamente os doze módulos"
        )
    for key in (
        "nao_aplicavel_exige_recibo_explicito",
        "nd_exige_zero_atividade_avaliativa",
        "pontuacao_exige_aplicabilidade_e_evidencia",
    ):
        if coverage.get(key) is not True:
            raise EvaluationCatalogError(f"contrato fail-closed exige {key}=true")
    for key in ("atividade_sem_recibo", "recibo_incompleto"):
        if coverage.get(key) != "falha_instrumentacao":
            raise EvaluationCatalogError(
                f"contrato fail-closed exige {key}=falha_instrumentacao"
            )

    modules = _required_nonempty_list(catalog, "modulos", "catálogo")
    module_ids = [str(item.get("id") or "") for item in modules if isinstance(item, dict)]
    if len(modules) != len(MODULE_IDS) or set(module_ids) != MODULE_IDS:
        missing = sorted(MODULE_IDS - set(module_ids))
        extra = sorted(set(module_ids) - MODULE_IDS)
        raise EvaluationCatalogError(
            "o catálogo precisa conter exatamente os doze módulos v2; "
            f"ausentes={missing}, extras={extra}"
        )
    if len(module_ids) != len(set(module_ids)):
        raise EvaluationCatalogError("IDs de módulos v2 precisam ser únicos")

    subcapabilities: dict[tuple[str, str], dict[str, Any]] = {}
    aliases: dict[str, tuple[str, str]] = {}
    for module in modules:
        module_id = _required_text(module, "id", "módulo")
        owner = f"módulo {module_id}"
        _required_text(module, "responsabilidade", owner)
        _required_text(module, "escopo", owner)
        unit = _required_text(module, "unidade_analise", owner)
        if unit not in ANALYSIS_UNITS:
            raise EvaluationCatalogError(f"{owner}: unidade_analise inválida: {unit}")
        visibility = _required_text(module, "visibilidade_jogador", owner)
        if visibility not in PLAYER_VISIBILITIES:
            raise EvaluationCatalogError(f"{owner}: visibilidade_jogador inválida: {visibility}")
        _required_text(module, "versao_implementacao", owner)
        _required_text(module, "versao_avaliacao", owner)
        if int(str(module["versao_avaliacao"]).split(".")[0]) < 4:
            raise EvaluationCatalogError(
                f"{owner}: contrato fail-closed exige avaliação major 4 ou superior"
            )

        eligibility = module.get("contrato_elegibilidade")
        if not isinstance(eligibility, dict):
            raise EvaluationCatalogError(f"{owner}: contrato_elegibilidade é obrigatório")
        _required_text(eligibility, "gatilho", f"{owner}.contrato_elegibilidade")
        _required_nonempty_list(
            eligibility, "evidencias_minimas", f"{owner}.contrato_elegibilidade"
        )
        exclusions = eligibility.get("exclusoes")
        if not isinstance(exclusions, list):
            raise EvaluationCatalogError(
                f"{owner}.contrato_elegibilidade: exclusoes precisa ser uma lista"
            )
        _required_nonempty_list(module, "resultados_possiveis", owner)
        _required_nonempty_list(module, "indicadores_especializados", owner)
        _required_nonempty_list(module, "guardrails_aplicaveis", owner)

        subitems = _required_nonempty_list(module, "subcapacidades", owner)
        local_ids: set[str] = set()
        for subitem in subitems:
            if not isinstance(subitem, dict):
                raise EvaluationCatalogError(f"{owner}: subcapacidade inválida")
            sub_id = _required_text(subitem, "id", f"subcapacidade de {module_id}")
            _required_text(subitem, "responsabilidade", f"subcapacidade {module_id}.{sub_id}")
            if sub_id in local_ids:
                raise EvaluationCatalogError(f"{owner}: subcapacidade duplicada: {sub_id}")
            local_ids.add(sub_id)
            subcapabilities[(module_id, sub_id)] = subitem
            subaliases = subitem.get("aliases_v1")
            if not isinstance(subaliases, list):
                raise EvaluationCatalogError(
                    f"subcapacidade {module_id}.{sub_id}: aliases_v1 precisa ser uma lista"
                )
            for alias in subaliases:
                if alias in aliases:
                    raise EvaluationCatalogError(f"alias v1 duplicado: {alias}")
                aliases[str(alias)] = (module_id, sub_id)

    migrations = _required_nonempty_list(catalog, "migracao_v1", "catálogo")
    origins = [str(item.get("origem") or "") for item in migrations if isinstance(item, dict)]
    if set(origins) != V1_ITEM_IDS or len(origins) != len(V1_ITEM_IDS):
        missing = sorted(V1_ITEM_IDS - set(origins))
        extra = sorted(set(origins) - V1_ITEM_IDS)
        raise EvaluationCatalogError(
            f"mapa v1 → v2 incompleto ou duplicado; ausentes={missing}, extras={extra}"
        )

    for migration in migrations:
        origin = _required_text(migration, "origem", "migração v1")
        nature = _required_text(migration, "natureza_destino", f"migração {origin}")
        if nature == "subcapacidade":
            module_id = _required_text(migration, "modulo", f"migração {origin}")
            sub_id = _required_text(migration, "subcapacidade", f"migração {origin}")
            if (module_id, sub_id) not in subcapabilities:
                raise EvaluationCatalogError(
                    f"migração {origin}: destino inexistente {module_id}.{sub_id}"
                )
            if aliases.get(origin) != (module_id, sub_id):
                raise EvaluationCatalogError(
                    f"migração {origin}: destino diverge do alias da subcapacidade"
                )
        elif nature == "regressao_historica":
            if origin != "seven_names_migration_regression":
                raise EvaluationCatalogError(f"migração {origin}: regressão histórica indevida")
        elif nature == "extensao_campanha":
            if origin != "underground_tournament":
                raise EvaluationCatalogError(f"migração {origin}: extensão de campanha indevida")
        else:
            raise EvaluationCatalogError(f"migração {origin}: natureza_destino inválida: {nature}")

    expected_aliases = V1_ITEM_IDS - NON_MODULE_V1_IDS
    if set(aliases) != expected_aliases:
        missing = sorted(expected_aliases - set(aliases))
        extra = sorted(set(aliases) - expected_aliases)
        raise EvaluationCatalogError(
            f"aliases v1 de subcapacidades incompletos; ausentes={missing}, extras={extra}"
        )

    layers = catalog.get("camadas_nao_modulares")
    if not isinstance(layers, dict):
        raise EvaluationCatalogError("camadas_nao_modulares é obrigatório")
    regression_ids = {
        str(item.get("id") or "") for item in layers.get("regressoes_historicas") or []
    }
    extension_ids = {
        str(item.get("id") or "") for item in layers.get("extensoes_campanha") or []
    }
    if regression_ids != {"seven_names_migration_regression"}:
        raise EvaluationCatalogError("Sete Nomes precisa ser regressão histórica")
    if extension_ids != {"underground_tournament"}:
        raise EvaluationCatalogError("Torneio Clandestino precisa ser extensão da campanha")
    if (regression_ids | extension_ids) & set(module_ids):
        raise EvaluationCatalogError("cenário/regressão não pode ser módulo de primeira classe")


def validate_guardrails(data: dict[str, Any], catalog: dict[str, Any]) -> None:
    if data.get("schema_catalogo_guardrails") != 1:
        raise EvaluationCatalogError("schema_catalogo_guardrails precisa ser 1")
    if data.get("participa_media_modular") is not False:
        raise EvaluationCatalogError("guardrails não podem participar da média modular")
    guardrails = _required_nonempty_list(data, "guardrails", "catálogo de guardrails")
    ids: list[str] = []
    for guardrail in guardrails:
        guardrail_id = _required_text(guardrail, "id", "guardrail")
        ids.append(guardrail_id)
        owner = f"guardrail {guardrail_id}"
        _required_text(guardrail, "responsabilidade", owner)
        _required_text(guardrail, "severidade", owner)
        if guardrail.get("participa_media_modular") is not False:
            raise EvaluationCatalogError(f"{owner}: não pode participar da média modular")
        if "peso_media_modular" in guardrail or "peso" in guardrail:
            raise EvaluationCatalogError(f"{owner}: não pode receber peso de média modular")
    if len(ids) != len(set(ids)):
        raise EvaluationCatalogError("IDs de guardrails precisam ser únicos")

    known = set(ids)
    for module in catalog.get("modulos") or []:
        unknown = set(module.get("guardrails_aplicaveis") or []) - known
        if unknown:
            raise EvaluationCatalogError(
                f"módulo {module.get('id')}: guardrails inexistentes: {sorted(unknown)}"
            )


def validate_series_policy(policy: dict[str, Any]) -> None:
    if policy.get("schema_politica_series_avaliacao") != 2:
        raise EvaluationCatalogError("schema_politica_series_avaliacao precisa ser 2")
    if policy.get("serie_padrao_producao") != "modules-v2":
        raise EvaluationCatalogError("modules-v2 precisa ser o padrão depois da RM-11")
    classification = policy.get("classificacao") or {}
    if classification.get("serie_quando_campo_ausente") != "legacy-v1":
        raise EvaluationCatalogError("pacote sem serie_avaliacao precisa ser legacy-v1")
    series = policy.get("series") or []
    ids = {str(item.get("id") or "") for item in series if isinstance(item, dict)}
    if ids != SERIES_IDS:
        raise EvaluationCatalogError(f"séries esperadas={sorted(SERIES_IDS)}, recebidas={sorted(ids)}")
    compatibility = policy.get("comparabilidade") or {}
    if compatibility.get("agregacao_entre_series") != "proibida":
        raise EvaluationCatalogError("agregação entre séries precisa ser proibida")
    if compatibility.get("versoes_incompativeis") != "separar_series_temporais":
        raise EvaluationCatalogError("versões incompatíveis precisam formar séries temporais separadas")
    modular = compatibility.get("comparacao_modular") or {}
    if modular.get("dimensao_em_disputa") != "module_implementation_version":
        raise EvaluationCatalogError("comparação modular precisa disputar versões de implementação")


def _semver_change(previous: str, current: str, owner: str) -> str:
    if not SEMVER_RE.fullmatch(previous) or not SEMVER_RE.fullmatch(current):
        raise EvaluationCatalogError(f"{owner}: versões precisam ser SemVer")
    before = tuple(int(part) for part in previous.split("."))
    after = tuple(int(part) for part in current.split("."))
    if after < before:
        raise EvaluationCatalogError(f"{owner}: versão não pode retroceder")
    if after == before:
        return "none"
    if after[0] != before[0]:
        return "major"
    if after[1] != before[1]:
        return "minor"
    return "patch"


def validate_module_releases(data: dict[str, Any], catalog: dict[str, Any]) -> None:
    if data.get("schema_module_releases") != 2:
        raise EvaluationCatalogError("schema_module_releases precisa ser 2")
    releases = _required_nonempty_list(data, "releases", "histórico de releases")
    current_refs = data.get("current_releases")
    if not isinstance(current_refs, dict) or set(current_refs) != MODULE_IDS:
        raise EvaluationCatalogError("current_releases precisa apontar os doze módulos")
    by_id: dict[str, dict[str, Any]] = {}
    last_by_module: dict[str, dict[str, Any]] = {}
    version_pairs: set[tuple[str, str, str]] = set()
    for release in releases:
        module_id = _required_text(release, "module_id", "release")
        if module_id not in MODULE_IDS:
            raise EvaluationCatalogError(f"release de módulo desconhecido: {module_id}")
        release_id = _required_text(release, "release_id", f"release {module_id}")
        if release_id in by_id:
            raise EvaluationCatalogError(f"release_id duplicado: {release_id}")
        for key in ("implementation_version", "evaluation_version"):
            value = _required_text(release, key, f"release {module_id}")
            if not SEMVER_RE.fullmatch(value):
                raise EvaluationCatalogError(f"release {module_id}: {key} não é SemVer")
        expected_id = (
            f"{module_id}/impl-{release['implementation_version']}"
            f"/eval-{release['evaluation_version']}"
        )
        if release_id != expected_id:
            raise EvaluationCatalogError(
                f"release {module_id}: release_id precisa ser {expected_id}"
            )
        pair = (module_id, release["implementation_version"], release["evaluation_version"])
        if pair in version_pairs:
            raise EvaluationCatalogError(f"release duplicado para o par de versões: {release_id}")
        version_pairs.add(pair)
        previous = release.get("previous")
        if not isinstance(previous, dict):
            raise EvaluationCatalogError(f"release {module_id}: previous é obrigatório")
        prior_release = last_by_module.get(module_id)
        if prior_release is not None and (
            previous.get("implementation_version")
            != prior_release["implementation_version"]
            or previous.get("evaluation_version") != prior_release["evaluation_version"]
        ):
            raise EvaluationCatalogError(
                f"release {module_id}: previous precisa apontar a release anterior do log"
            )
        for key in ("implementation_change", "evaluation_change"):
            if release.get(key) not in {"none", "patch", "minor", "major"}:
                raise EvaluationCatalogError(f"release {module_id}: {key} inválido")
        implementation_change = _semver_change(
            _required_text(previous, "implementation_version", f"release {module_id}.previous"),
            release["implementation_version"],
            f"release {module_id}.implementation_version",
        )
        evaluation_change = _semver_change(
            _required_text(previous, "evaluation_version", f"release {module_id}.previous"),
            release["evaluation_version"],
            f"release {module_id}.evaluation_version",
        )
        if release["implementation_change"] != implementation_change:
            raise EvaluationCatalogError(
                f"release {module_id}: implementation_change não corresponde ao SemVer"
            )
        if release["evaluation_change"] != evaluation_change:
            raise EvaluationCatalogError(
                f"release {module_id}: evaluation_change não corresponde ao SemVer"
            )
        if release.get("compatibility") not in {"compatible", "incompatible_implementation", "incompatible_evaluation", "incompatible_both"}:
            raise EvaluationCatalogError(f"release {module_id}: compatibilidade inválida")
        incompatible_implementation = implementation_change == "major"
        incompatible_evaluation = evaluation_change == "major"
        expected_compatibility = (
            "incompatible_both"
            if incompatible_implementation and incompatible_evaluation
            else "incompatible_implementation"
            if incompatible_implementation
            else "incompatible_evaluation"
            if incompatible_evaluation
            else "compatible"
        )
        if release["compatibility"] != expected_compatibility:
            raise EvaluationCatalogError(
                f"release {module_id}: compatibility deveria ser {expected_compatibility}"
            )
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", _required_text(release, "effective_date", f"release {module_id}")):
            raise EvaluationCatalogError(f"release {module_id}: effective_date precisa ser YYYY-MM-DD")
        _required_text(release, "source_revision", f"release {module_id}")
        _required_text(release, "reason", f"release {module_id}")
        _required_nonempty_list(release, "fixtures", f"release {module_id}")
        by_id[release_id] = release
        last_by_module[module_id] = release
    catalog_modules = {item["id"]: item for item in catalog.get("modulos") or []}
    for module_id, module in catalog_modules.items():
        release_id = current_refs[module_id]
        if release_id != last_by_module[module_id]["release_id"]:
            raise EvaluationCatalogError(
                f"current_releases.{module_id} precisa apontar a última release do log"
            )
        release = by_id.get(release_id)
        if release is None or release.get("module_id") != module_id:
            raise EvaluationCatalogError(
                f"current_releases.{module_id} aponta release ausente ou de outro módulo"
            )
        if release["implementation_version"] != module["versao_implementacao"]:
            raise EvaluationCatalogError(f"release {module_id}: versão de implementação diverge do catálogo")
        if release["evaluation_version"] != module["versao_avaliacao"]:
            raise EvaluationCatalogError(f"release {module_id}: versão de avaliação diverge do catálogo")


def evaluation_series(manifest: dict[str, Any], policy: dict[str, Any] | None = None) -> str:
    """Classifica manifestos legados sem reescrevê-los."""

    fallback = "legacy-v1"
    if policy is not None:
        fallback = str((policy.get("classificacao") or {}).get("serie_quando_campo_ausente") or fallback)
    series = str(manifest.get("serie_avaliacao") or fallback)
    if series not in SERIES_IDS:
        raise EvaluationCatalogError(f"serie_avaliacao desconhecida: {series}")
    return series


def comparability_key(
    manifest: dict[str, Any], policy: dict[str, Any] | None = None
) -> tuple[str, ...]:
    """Produz a chave cuja igualdade é exigida para uma agregação numérica."""

    series = evaluation_series(manifest, policy)
    versions = manifest.get("versoes") or {}
    fields = ["catalogo_modulos", "metas", "gerador"]
    if policy is not None:
        configured = (policy.get("comparabilidade") or {}).get("campos_versao")
        if isinstance(configured, list) and configured:
            fields = [str(item) for item in configured]
    return (series, *(str(versions.get(field, "ausente")) for field in fields))


def require_comparable(
    manifests: Iterable[dict[str, Any]], policy: dict[str, Any] | None = None
) -> tuple[str, ...] | None:
    """Falha antes da média caso haja série ou versão incompatível."""

    keys = {comparability_key(manifest, policy) for manifest in manifests}
    if not keys:
        return None
    if len(keys) != 1:
        raise EvaluationCatalogError(
            "agregação incompatível; separe por serie_avaliacao e versões: "
            + ", ".join("/".join(key) for key in sorted(keys))
        )
    return next(iter(keys))


def module_comparability_key(manifest: dict[str, Any], module_id: str) -> tuple[str, str]:
    """Chave modular: implementação pode variar; a régua precisa permanecer."""

    for item in manifest.get("versoes_modulos") or []:
        if item.get("module_id") == module_id:
            evaluation = item.get("module_evaluation_version")
            if not evaluation:
                break
            return module_id, str(evaluation)
    raise EvaluationCatalogError(f"manifesto não preserva versão de avaliação de {module_id}")


def require_module_comparable(
    manifests: Iterable[dict[str, Any]], module_id: str
) -> tuple[str, str] | None:
    keys = {module_comparability_key(manifest, module_id) for manifest in manifests}
    if not keys:
        return None
    if len(keys) != 1:
        raise EvaluationCatalogError(
            f"avaliações incompatíveis para {module_id}: "
            + ", ".join("/".join(key) for key in sorted(keys))
        )
    return next(iter(keys))


def validate_defaults() -> None:
    catalog = load_json(DEFAULT_CATALOG)
    guardrails = load_json(DEFAULT_GUARDRAILS)
    policy = load_json(DEFAULT_SERIES_POLICY)
    releases = load_json(DEFAULT_RELEASES)
    validate_catalog_v2(catalog)
    validate_guardrails(guardrails, catalog)
    validate_series_policy(policy)
    validate_module_releases(releases, catalog)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emite confirmação estruturada")
    args = parser.parse_args()
    try:
        validate_defaults()
    except EvaluationCatalogError as exc:
        print(f"FALHA NO CATÁLOGO DE AVALIAÇÃO — {exc}")
        return 1
    result = {
        "status": "ok",
        "catalogo": str(DEFAULT_CATALOG.relative_to(ROOT)),
        "modulos_primeira_classe": len(MODULE_IDS),
        "itens_v1_mapeados": len(V1_ITEM_IDS),
        "serie_padrao_producao": "modules-v2",
        "historico_releases": str(DEFAULT_RELEASES.relative_to(ROOT)),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else "CATÁLOGO DE AVALIAÇÃO — OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
