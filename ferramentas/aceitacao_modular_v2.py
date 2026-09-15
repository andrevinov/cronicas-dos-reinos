#!/usr/bin/env python3
"""Aceitação técnica da arquitetura modular v2 e prontidão da baseline real.

O checker nunca escreve no save canônico. Ele valida contratos e regressões do
repositório, executa uma sessão 900 inteiramente temporária, gera duas vezes o
mesmo pacote pós-hoc e informa separadamente se a primeira sessão real v2 já
existe. A fixture técnica não inaugura a série de experiência do jogador.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

from ferramentas import catalogo_avaliacao as catalog_contract
from ferramentas import interacoes_narrativas as interactions


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path("tests/fixtures/aceitacao-modular-v2.yaml")
ROLLOUT = Path("tests/fixtures/rollout-modules-v2-technical.jsonl")
BASELINE = Path("baseline/modules-v2-technical-acceptance.json")
CATALOG = Path("evaluation/catalogo-modulos-v2.json")
RELEASES = Path("evaluation/module-releases.json")
SESSION_INDEX = Path("evaluation/sessions/index.json")
GENERATOR = ROOT / "ferramentas/gerar-avaliacao-sessao.py"
SCHEMA = 1
FIXTURE_SESSION = 900
EXPECTED_EPISODES = {
    "turno_curto_neutro",
    "cena_social_memoria_relacao",
    "regra_rolagem_recurso",
    "oportunidade_e_autoria",
    "progresso_terminal_exactly_once",
    "permanencia_e_compressao",
    "evento_canonico_devido",
    "operacoes_adversariais_simultaneas",
    "retry_e_recovery",
}
EXPECTED_ARTIFACTS = {
    "manifest.json",
    "telemetria.json",
    "turnos.csv",
    "eventos-modulares.csv",
    "resumo-modulos.csv",
    "resumo-modulos.json",
    "interacoes.json",
    "manifestacoes-jogador.json",
    "adjudicacoes-modulares.json",
    "validade-medicao.json",
    "scorecard.json",
    "relatorio.md",
}
REFERENCE_RE = re.compile(r"^S900-I\d{4}$")


class ModularAcceptanceError(ValueError):
    """Contrato de aceitação modular inválido."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModularAcceptanceError(f"não foi possível ler {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ModularAcceptanceError(f"{label} precisa conter objeto JSON")
    return value


def _load_yaml(path: Path, label: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ModularAcceptanceError(f"não foi possível ler {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ModularAcceptanceError(f"{label} precisa conter mapa YAML")
    return value


def _generator_module():
    spec = importlib.util.spec_from_file_location("aceitacao_rm12_generator", GENERATOR)
    if spec is None or spec.loader is None:
        raise ModularAcceptanceError("gerador de avaliação não pôde ser carregado")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _test_methods(path: Path) -> dict[str, set[str]]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise ModularAcceptanceError(f"teste não pôde ser inspecionado: {path}: {exc}") from exc
    return {
        node.name: {
            child.name
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }


def validate_episode_anchors(repo: Path) -> list[str]:
    fixture = _load_yaml(repo / FIXTURE, FIXTURE.as_posix())
    if fixture.get("schema_aceitacao_modular_v2") != SCHEMA:
        raise ModularAcceptanceError("fixture de episódios precisa usar schema 1")
    episodes = fixture.get("episodios")
    if not isinstance(episodes, dict) or set(episodes) != EXPECTED_EPISODES:
        raise ModularAcceptanceError("fixture não cobre exatamente os nove episódios da RM-12")
    result: list[str] = []
    root = repo.resolve()
    for episode_id in sorted(episodes):
        anchor = episodes[episode_id]
        if not isinstance(anchor, dict) or set(anchor) != {"arquivo", "classe", "teste"}:
            raise ModularAcceptanceError(f"{episode_id}: âncora inválida")
        relative = str(anchor["arquivo"])
        path = (repo / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file() or not relative.startswith("tests/test_"):
            raise ModularAcceptanceError(f"{episode_id}: teste permanente ausente: {relative}")
        methods = _test_methods(path)
        class_name = str(anchor["classe"])
        test_name = str(anchor["teste"])
        if class_name not in methods or test_name not in methods[class_name]:
            raise ModularAcceptanceError(
                f"{episode_id}: âncora inexistente {class_name}.{test_name}"
            )
        result.append(f"{relative}::{class_name}.{test_name}")
    return result


def run_episode_anchors(repo: Path, anchors: list[str]) -> dict[str, Any]:
    targets = []
    for anchor in anchors:
        relative, method = anchor.split("::", 1)
        module = Path(relative).with_suffix("").as_posix().replace("/", ".")
        targets.append(f"{module}.{method}")
    environment = os.environ.copy()
    import_roots = [str(repo), str(repo / "tests")]
    if environment.get("PYTHONPATH"):
        import_roots.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(import_roots)
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", *targets],
        cwd=repo,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        diagnostic = (completed.stderr or completed.stdout).strip()[-4000:]
        raise ModularAcceptanceError(
            f"episódios controlados falharam (exit {completed.returncode}): {diagnostic}"
        )
    return {"ok": True, "quantidade": len(targets)}


def validate_release_history(repo: Path) -> dict[str, Any]:
    catalog = _load_json(repo / CATALOG, CATALOG.as_posix())
    releases = _load_json(repo / RELEASES, RELEASES.as_posix())
    catalog_contract.validate_catalog_v2(catalog)
    catalog_contract.validate_module_releases(releases, catalog)
    missing_fixtures = sorted(
        fixture
        for release in releases["releases"]
        for fixture in release["fixtures"]
        if not (repo / fixture).is_file()
    )
    if missing_fixtures:
        raise ModularAcceptanceError(f"releases apontam fixtures ausentes: {missing_fixtures}")
    current = releases["current_releases"]
    return {
        "schema": releases["schema_module_releases"],
        "releases_historicos": len(releases["releases"]),
        "releases_correntes": len(current),
        "current_release_ids": dict(sorted(current.items())),
    }


def _write_sandbox_contract(repo: Path, source_repo: Path) -> None:
    runtime = repo / "runtime/contexto.yaml"
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_text(
        "sessao:\n  numero: 900\n  status: em_sessao\n",
        encoding="utf-8",
    )
    catalog = repo / CATALOG
    catalog.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_repo / CATALOG, catalog)


def _file_hashes(repo: Path) -> dict[str, str]:
    return {
        path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(repo.rglob("*"))
        if path.is_file()
    }


def exercise_interaction_contract(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    before = _file_hashes(repo)
    prepared = interactions.attach_prepare(repo, {"ticket_id": "ticket-rm12-on"})
    on_ref = prepared["interacao"]["interaction_ref"]
    transaction = {
        "jogador": "Ren observa a rua sem avançar o tempo.",
        "narracao": "A rua permanece calma e devolve a escolha a Ren.",
    }
    conclusion = interactions.attach_conclusion(
        repo,
        {
            "transacao": {"id": "tx-rm12-on", "sessao": FIXTURE_SESSION},
            "rodape_canonico": "RODAPE_CANONICO — fixture",
        },
        transaction,
        ticket_id="ticket-rm12-on",
    )
    retry = interactions.attach_conclusion(
        repo,
        {
            "transacao": {
                "id": "tx-rm12-on",
                "sessao": FIXTURE_SESSION,
                "ja_registrada": True,
            },
            "rodape_canonico": "RODAPE_CANONICO — fixture",
        },
        transaction,
        ticket_id="ticket-rm12-on",
    )
    off = interactions.record_exchange(
        repo,
        interaction_class="OFF",
        input_text="[O identificador também existe em OFF?]",
        response_text="[Sim. O ledger é o mesmo.]",
        client_key="rm12-off",
    )
    recall = interactions.record_exchange(
        repo,
        interaction_class="RECALL",
        input_text="{Qual foi o último fato que Ren conhecia?}",
        response_text="{Apenas o fato autorizado pela camada de conhecimento.}",
        client_key="rm12-recall",
    )
    operational = interactions.record_exchange(
        repo,
        interaction_class="operacional",
        input_text="[Mostre o estado técnico da avaliação.]",
        response_text="[A avaliação permanece pós-hoc.]",
        client_key="rm12-operacional",
    )
    incomplete = interactions.reserve(
        repo,
        interaction_class="OFF",
        correlation_key="rm12-incompleta",
        input_text="[Entrada interrompida.]",
    )
    incomplete_retry = interactions.reserve(
        repo,
        interaction_class="OFF",
        correlation_key="rm12-incompleta",
        input_text="[Entrada interrompida.]",
    )
    next_exchange = interactions.record_exchange(
        repo,
        interaction_class="OFF",
        input_text="[Nova entrada lógica.]",
        response_text="[Nova resposta final.]",
        client_key="rm12-nova",
    )

    event_count = len(interactions.load_events(repo, FIXTURE_SESSION))
    divergent_rejected = False
    try:
        interactions.complete(
            repo,
            reference=on_ref,
            input_text=transaction["jogador"],
            response_text="resposta divergente",
        )
    except interactions.InteractionError:
        divergent_rejected = True
    if len(interactions.load_events(repo, FIXTURE_SESSION)) != event_count:
        raise ModularAcceptanceError("retry divergente alterou o ledger")

    feedback = interactions.record_player_feedback(
        repo,
        interaction_ref=on_ref,
        original_text="A entrega neutra preservou minha escolha.",
        perceived_type="boa_ativacao",
        observation="A resposta não decidiu por Ren.",
        impact="moderado",
    )
    repeated_feedback = interactions.record_player_feedback(
        repo,
        interaction_ref=on_ref,
        original_text="A entrega neutra preservou minha escolha.",
        perceived_type="boa_ativacao",
        observation="A resposta não decidiu por Ren.",
        impact="moderado",
    )
    interactions.adjudicate_feedback(
        repo,
        feedback_id=feedback["feedback_id"],
        state="confirmada",
        reason="A resposta termina antes de qualquer ação voluntária de Ren.",
        module_id="narrative_delivery",
        capability_id="visible_closure",
        confidence="alta",
        evidence=["resposta final da fixture"],
    )
    materialized = interactions.materialize(repo, FIXTURE_SESSION)
    rows = materialized["interactions"]
    refs = [item["interaction_ref"] for item in rows]
    expected_refs = [f"S900-I{ordinal:04d}" for ordinal in range(1, 7)]
    if refs != expected_refs or not all(REFERENCE_RE.fullmatch(ref) for ref in refs):
        raise ModularAcceptanceError(f"ordinais da sessão técnica divergiram: {refs}")
    if incomplete["interaction_ref"] != incomplete_retry["interaction_ref"]:
        raise ModularAcceptanceError("retry da mesma reserva incompleta criou outra identidade")
    if not incomplete_retry["replay"] or next_exchange["interaction_ref"] == incomplete["interaction_ref"]:
        raise ModularAcceptanceError("nova entrada lógica não avançou depois da reserva incompleta")
    if not retry["interacao"]["replay"] or retry["interacao"]["interaction_ref"] != on_ref:
        raise ModularAcceptanceError("retry ON não reutilizou a interação original")
    if conclusion["rodape_canonico"].count(on_ref) != 1:
        raise ModularAcceptanceError("rodapé ON não contém exatamente uma referência")
    for receipt in (off, recall, operational, next_exchange):
        if receipt["visible_marker"].count(receipt["interaction_ref"]) != 1:
            raise ModularAcceptanceError("marcador OFF/RECALL/operacional não é único")
    states = [item["state"] for item in rows]
    if states.count("complete") != 5 or states.count("incomplete") != 1:
        raise ModularAcceptanceError(f"estados de interação divergiram: {states}")
    if not divergent_rejected:
        raise ModularAcceptanceError("hash divergente não foi rejeitado")
    if feedback["feedback_id"] != repeated_feedback["feedback_id"]:
        raise ModularAcceptanceError("a mesma manifestação recebeu dois feedback_id")
    if len(materialized["player_feedback"]) != 1:
        raise ModularAcceptanceError("manifestação idempotente foi duplicada")
    versions = rows[0].get("module_versions") or {}
    if set(versions) != catalog_contract.MODULE_IDS:
        raise ModularAcceptanceError("snapshot da interação não contém os doze módulos")

    after = _file_hashes(repo)
    changed = sorted(
        path for path in before.keys() | after.keys() if before.get(path) != after.get(path)
    )
    expected_ledger = interactions.ledger_path(repo, FIXTURE_SESSION).relative_to(repo).as_posix()
    if changed != [expected_ledger]:
        raise ModularAcceptanceError(f"interação alterou fontes além do ledger: {changed}")
    return materialized, {
        "interacoes_total": len(rows),
        "interacoes_completas": states.count("complete"),
        "interacoes_incompletas": states.count("incomplete"),
        "feedback_idempotente": True,
        "retry_on_idempotente": True,
        "divergencia_hash_rejeitada": True,
        "fontes_alteradas": changed,
        "release_set_id": rows[0]["release_set_id"],
    }


def _generate_technical_package(
    source_repo: Path, sandbox: Path, materialized: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    generator = _generator_module()
    materialized_path = sandbox / "materialized-interactions.json"
    materialized_path.write_text(
        json.dumps(materialized, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    output = sandbox / "package"
    first = generator.generate_session_evaluation(
        source_repo / ROLLOUT,
        session_id=str(FIXTURE_SESSION),
        output_dir=output,
        catalog_path=source_repo / CATALOG,
        targets_path=source_repo / "evaluation/metas-avaliacao-v2.json",
        baseline_path=source_repo / "baseline/rollout-2026-08-15.json",
        interactions_path=materialized_path,
    )
    manifest_before = copy.deepcopy(first["manifest"])
    feedback_before = _load_json(
        output / "manifestacoes-jogador.json", "manifestação técnica"
    )["player_feedback"]

    changed_catalog = _load_json(source_repo / CATALOG, CATALOG.as_posix())
    changed_catalog["modulos"][0]["versao_implementacao"] = "9.0.0"
    changed_catalog_path = sandbox / "catalogo-corrente-alterado.json"
    changed_catalog_path.write_text(
        json.dumps(changed_catalog, ensure_ascii=False), encoding="utf-8"
    )
    second = generator.generate_session_evaluation(
        source_repo / ROLLOUT,
        session_id=str(FIXTURE_SESSION),
        output_dir=output,
        catalog_path=changed_catalog_path,
        targets_path=source_repo / "evaluation/metas-avaliacao-v2.json",
        baseline_path=source_repo / "baseline/rollout-2026-08-15.json",
        interactions_path=materialized_path,
    )
    if manifest_before["versoes_modulos"] != second["manifest"]["versoes_modulos"]:
        raise ModularAcceptanceError("regeneração reescreveu versões históricas da interação")
    feedback_after = _load_json(
        output / "manifestacoes-jogador.json", "manifestação regenerada"
    )["player_feedback"]
    if feedback_before != feedback_after or len(feedback_after) != 1:
        raise ModularAcceptanceError("regeneração perdeu ou duplicou manifestação do jogador")

    manifest = second["manifest"]
    scorecard = second["scorecard"]
    module_rows = _load_json(output / "resumo-modulos.json", "resumo modular")["modulos"]
    packaged_interactions = _load_json(output / "interacoes.json", "interações do pacote")[
        "interactions"
    ]
    if set(path.name for path in output.iterdir()) != EXPECTED_ARTIFACTS:
        raise ModularAcceptanceError("pacote técnico possui conjunto de artefatos divergente")
    if manifest.get("serie_avaliacao") != "modules-v2" or len(module_rows) != 12:
        raise ModularAcceptanceError("pacote técnico não contém a série e os doze módulos pais")
    if [row.get("prioridade_rank") for row in module_rows] != list(range(1, 13)):
        raise ModularAcceptanceError("ranking técnico não contém uma linha por módulo pai")
    if "jogador" in (scorecard.get("eixos") or {}):
        raise ModularAcceptanceError("nota numérica do jogador reapareceu no scorecard v2")
    observed_responses = [item for item in packaged_interactions if item.get("response_present")]
    visible = sum(bool(item.get("visible_exactly_once")) for item in observed_responses)
    if len(observed_responses) != 2 or visible != 2:
        raise ModularAcceptanceError("rollout técnico não preservou referência nas duas respostas")
    if len(packaged_interactions) != 6:
        raise ModularAcceptanceError("ledger e pacote não convergiram nas seis interações")
    metrics = {
        "interacoes_total": len(packaged_interactions),
        "interacoes_completas": sum(item.get("state") == "complete" for item in packaged_interactions),
        "interacoes_incompletas": sum(item.get("state") == "incomplete" for item in packaged_interactions),
        "respostas_finais_no_rollout": len(observed_responses),
        "referencias_visiveis_exatamente_uma_vez": visible,
        "modulos_pais": len(module_rows),
        "turnos_narrativos": manifest["amostra"]["turnos_narrativos"],
        "tokens_narrativos": manifest["amostra"]["tokens_narrativos"],
        "tokens_atribuidos_pais": manifest["amostra"]["tokens_atribuidos_pais"],
    }
    return metrics, {
        "artefatos": sorted(EXPECTED_ARTIFACTS),
        "manifest": manifest,
        "scorecard": scorecard,
        "regeneracao_idempotente": True,
        "versoes_historicas_preservadas": True,
    }


def technical_acceptance(repo: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="cronicas-rm12-") as temporary:
        sandbox = Path(temporary)
        _write_sandbox_contract(sandbox, repo)
        materialized, interaction_result = exercise_interaction_contract(sandbox)
        observed, package = _generate_technical_package(repo, sandbox, materialized)
    baseline = _load_json(repo / BASELINE, BASELINE.as_posix())
    if baseline.get("schema_baseline_modules_v2") != SCHEMA:
        raise ModularAcceptanceError("baseline técnica precisa usar schema 1")
    if baseline.get("inaugura_serie_real") is not False:
        raise ModularAcceptanceError("fixture técnica não pode inaugurar série real")
    if baseline.get("observado") != observed:
        raise ModularAcceptanceError(
            f"baseline técnica divergiu; esperado={baseline.get('observado')}, observado={observed}"
        )
    return {
        "baseline": BASELINE.as_posix(),
        "observado": observed,
        "interacoes": interaction_result,
        "pacote": package,
    }


def first_real_session_status(repo: Path) -> dict[str, Any]:
    index = _load_json(repo / SESSION_INDEX, SESSION_INDEX.as_posix())
    candidates = [
        item
        for item in index.get("sessoes") or []
        if item.get("serie_avaliacao") == "modules-v2" and str(item.get("sessao_id")) != str(FIXTURE_SESSION)
    ]
    if not candidates:
        return {
            "estado": "pendente",
            "aceite_final": False,
            "motivo": "a primeira sessão real v2 ainda precisa ser jogada e auditada",
        }
    entry = candidates[-1]
    package = (repo / "evaluation/sessions" / str(entry["caminho"])).resolve()
    if not package.is_relative_to((repo / "evaluation/sessions").resolve()):
        raise ModularAcceptanceError("índice da primeira sessão real escapa de evaluation/sessions")
    manifest = _load_json(package / "manifest.json", "manifesto da primeira sessão real")
    scorecard = _load_json(package / "scorecard.json", "scorecard da primeira sessão real")
    interactions_data = _load_json(package / "interacoes.json", "interações da primeira sessão real")
    modules = _load_json(package / "resumo-modulos.json", "módulos da primeira sessão real")
    if manifest.get("serie_avaliacao") != "modules-v2":
        raise ModularAcceptanceError("primeira sessão real não pertence a modules-v2")
    if len(manifest.get("versoes_modulos") or []) != 12 or len(modules.get("modulos") or []) != 12:
        raise ModularAcceptanceError("primeira sessão real não preserva os doze módulos")
    observed = [item for item in interactions_data.get("interactions") or [] if item.get("response_present")]
    if "jogador" in (scorecard.get("eixos") or {}):
        raise ModularAcceptanceError("primeira sessão real contém nota numérica do jogador")
    missing_references = sum(not item.get("visible_exactly_once") for item in observed)
    if not observed or missing_references:
        return {
            "estado": "pendente",
            "aceite_final": False,
            "motivo": "primeira sessão real não possui respostas auditáveis com referência única em todas elas",
            "sessao_id": entry["sessao_id"],
            "interacoes_observadas": len(observed),
            "interacoes_sem_referencia_unica": missing_references,
            "status_avaliacao": scorecard.get("status_avaliacao"),
        }
    return {
        "estado": "aceita",
        "aceite_final": True,
        "sessao_id": entry["sessao_id"],
        "interacoes_observadas": len(observed),
        "status_avaliacao": scorecard.get("status_avaliacao"),
    }


def check(repo: Path = ROOT) -> dict[str, Any]:
    repo = Path(repo).resolve()
    try:
        anchors = validate_episode_anchors(repo)
        episodes = run_episode_anchors(repo, anchors)
        releases = validate_release_history(repo)
        technical = technical_acceptance(repo)
        real = first_real_session_status(repo)
    except (
        ModularAcceptanceError,
        catalog_contract.EvaluationCatalogError,
        interactions.InteractionError,
    ) as exc:
        return {"schema_aceitacao_modular_v2": SCHEMA, "ok": False, "erros": [str(exc)]}
    return {
        "schema_aceitacao_modular_v2": SCHEMA,
        "ok": True,
        "erros": [],
        "estado": "aceita" if real["aceite_final"] else "pronta_para_primeira_sessao_real",
        "episodios_ancorados": anchors,
        "execucao_episodios": episodes,
        "releases": releases,
        "aceitacao_tecnica": technical,
        "primeira_sessao_real": real,
        "contrato": {
            "fixture_inaugura_serie_real": False,
            "escrita_save_canonico": False,
            "medicao_no_hot_path": False,
            "nota_numerica_jogador": False,
            "guardrails_participam_media": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comando", choices=("check",))
    args = parser.parse_args()
    payload = check(ROOT)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
