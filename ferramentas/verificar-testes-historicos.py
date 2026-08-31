#!/usr/bin/env python3
"""Verifica a rastreabilidade da consolidação de testes históricos da Task 3."""
from __future__ import annotations

import argparse
import importlib.util
from collections import Counter
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
AUDITOR = ROOT / "ferramentas/auditar-testes.py"
REVIEW = Path("tests/historical-test-review.yaml")
ALLOWED = {"permanente", "redundante", "historico", "substituivel", "obsoleto"}
KEPT = {"permanente", "historico"}
REMOVED = {"redundante", "substituivel", "obsoleto"}

ORIGINAL_HISTORICAL = {
    "tests/sidequests_canonicas_task32_cases.py",
    "tests/test_adversarial_integrity.py",
    "tests/test_analisar_rollout_task38.py",
    "tests/test_analisar_rollout_task46.py",
    "tests/test_analisar_rollout_task47.py",
    "tests/test_canon_bridge_rewriter.py",
    "tests/test_canon_bridge_schedule_guard.py",
    "tests/test_canonical_intent_rewrite_contract.py",
    "tests/test_condicoes_mundo.py",
    "tests/test_cronica_cli.py",
    "tests/test_cronica_pending_gate_budget.py",
    "tests/test_cronica_transito_urbano.py",
    "tests/test_dialogo_relacional.py",
    "tests/test_emergent_sidequest_authoring_registry_v2.py",
    "tests/test_emergent_sidequest_opportunity_boundary.py",
    "tests/test_incidentes_mundo.py",
    "tests/test_live_campaign_state.py",
    "tests/test_migracao_ren_5_5e.py",
    "tests/test_quest_rewards_discoveries_losses.py",
    "tests/test_rules_catalog.py",
    "tests/test_secret_canon_v2.py",
    "tests/test_secret_npc_quest_catalog.py",
    "tests/test_sidequest_gate_v2.py",
    "tests/test_sidequest_progression_deadlines_consequences.py",
    "tests/test_task38_narrative_systems_integration.py",
    "tests/test_task40_router_contract.py",
    "tests/test_task41_router_contract.py",
    "tests/test_task42_router_contract.py",
    "tests/test_task43_router_contract.py",
    "tests/test_task44_router_contract.py",
    "tests/test_task45_boundary_guard.py",
    "tests/test_task45_router_contract.py",
    "tests/test_task46_budget_regression.py",
    "tests/test_task46_integration_transaction.py",
    "tests/test_task46_rollout_matrix.py",
    "tests/test_task46_router_contract.py",
    "tests/test_task47_explicit_opportunity_decision_gate.py",
    "tests/test_torneio_clandestino.py",
    "tests/test_unified_session_lifecycle.py",
}


class HistoricalTestReviewError(ValueError):
    pass


def _load_auditor():
    spec = importlib.util.spec_from_file_location("auditar_testes_task1", AUDITOR)
    if spec is None or spec.loader is None:
        raise HistoricalTestReviewError("auditor da Task 1 não pôde ser carregado")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_review(repo: Path) -> dict[str, dict[str, Any]]:
    path = repo / REVIEW
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise HistoricalTestReviewError(f"revisão ausente: {REVIEW.as_posix()}") from exc
    except yaml.YAMLError as exc:
        raise HistoricalTestReviewError(f"YAML inválido: {exc}") from exc

    if not isinstance(data, dict) or data.get("schema_revisao_testes_historicos") != 1:
        raise HistoricalTestReviewError("revisão histórica precisa usar schema 1")
    if data.get("quantidade_original") != len(ORIGINAL_HISTORICAL):
        raise HistoricalTestReviewError("quantidade_original diverge da fotografia da Task 1")
    entries = data.get("arquivos")
    if not isinstance(entries, dict):
        raise HistoricalTestReviewError("revisão precisa declarar arquivos")
    actual = set(entries)
    if actual != ORIGINAL_HISTORICAL:
        missing = sorted(ORIGINAL_HISTORICAL - actual)
        extra = sorted(actual - ORIGINAL_HISTORICAL)
        raise HistoricalTestReviewError(
            f"inventário histórico incompleto; ausentes={missing}; extras={extra}"
        )

    clean: dict[str, dict[str, Any]] = {}
    for source, entry in entries.items():
        if not isinstance(entry, dict):
            raise HistoricalTestReviewError(f"entrada inválida: {source}")
        classification = entry.get("classificacao")
        requirement = entry.get("requisito")
        coverage = entry.get("cobertura_atual")
        if classification not in ALLOWED:
            raise HistoricalTestReviewError(f"{source}: classificação inválida")
        if not isinstance(requirement, str) or len(requirement.strip()) < 30:
            raise HistoricalTestReviewError(f"{source}: requisito original insuficiente")
        if not isinstance(coverage, list) or not coverage or not all(
            isinstance(item, str) and item.strip() for item in coverage
        ):
            raise HistoricalTestReviewError(f"{source}: cobertura_atual inválida")
        for target in coverage:
            if not (repo / target).is_file():
                raise HistoricalTestReviewError(
                    f"{source}: cobertura declarada não existe: {target}"
                )
        source_exists = (repo / source).is_file()
        if classification in KEPT and not source_exists:
            raise HistoricalTestReviewError(
                f"{source}: {classification} precisa continuar presente"
            )
        if classification in REMOVED and source_exists:
            raise HistoricalTestReviewError(
                f"{source}: {classification} deveria ter sido consolidado/removido"
            )
        clean[source] = {
            "classificacao": classification,
            "requisito": requirement.strip(),
            "cobertura_atual": list(coverage),
        }
    return clean


def check(repo: Path = ROOT) -> dict[str, Any]:
    repo = repo.resolve()
    entries = load_review(repo)
    auditor = _load_auditor()
    inventory = auditor.inventory(repo / "tests", repo)
    current_historical = set(inventory["classificacoes"].get("task_historica", []))
    allowed_current = {
        source
        for source, entry in entries.items()
        if entry["classificacao"] in KEPT
    }
    unexpected = sorted(current_historical - allowed_current)
    missing_sources = sorted(
        source
        for source, entry in entries.items()
        if entry["classificacao"] in KEPT and not (repo / source).is_file()
    )
    counts = Counter(entry["classificacao"] for entry in entries.values())
    return {
        "schema_verificacao_testes_historicos": 1,
        "ok": not unexpected and not missing_sources,
        "originais": len(entries),
        "classificacoes": dict(sorted(counts.items())),
        "historicos_correntes": sorted(current_historical),
        "historicos_nao_revisados": unexpected,
        "fontes_preservadas_ausentes": missing_sources,
        "removidos_com_cobertura": sorted(
            source
            for source, entry in entries.items()
            if entry["classificacao"] in REMOVED
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        report = check(args.repo)
    except HistoricalTestReviewError as exc:
        print(f"FALHA — revisão de testes históricos: {exc}")
        return 1
    if not report["ok"]:
        print("FALHA — consolidação histórica incompleta")
        for rel in report["historicos_nao_revisados"]:
            print(f"- histórico atual sem classificação: {rel}")
        for rel in report["fontes_preservadas_ausentes"]:
            print(f"- fonte permanente/histórica ausente: {rel}")
        return 1
    counts = report["classificacoes"]
    print(
        "OK — 39 arquivos históricos da Task 1 possuem destino explícito; "
        + ", ".join(f"{key}={value}" for key, value in counts.items())
        + f"; task_historica_corrente={len(report['historicos_correntes'])}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
