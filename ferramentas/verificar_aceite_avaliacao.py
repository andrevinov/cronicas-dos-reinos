#!/usr/bin/env python3
"""Valida referências do G0 e mede regressões sem corrigir o avaliador.

--validar aprova apenas os artefatos da AMV-01. --medir compara a implementação
com expectativas congeladas e retorna 1 quando encontra defeitos. Nenhum desses
modos declara G0 aprovado nem escreve no save ou nos pacotes históricos.
--reavaliar-atividades usa somente o prefixo histórico declarado e confere suas
âncoras; publica contagens operacionais, não adjudicações semânticas.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ferramentas import catalogo_avaliacao as catalog
from ferramentas import verificar_corpus_avaliacao as corpus

DEFAULT_MANIFEST = ROOT / "evaluation/aceite-avaliacao-v1/manifest.json"


class AcceptanceReferenceError(ValueError):
    pass


def read_json(path: Path) -> Any:
    return corpus._json(path)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_reference(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    data = read_json(path)
    if data.get("schema_referencia_aceite_avaliacao") != 1:
        raise AcceptanceReferenceError("schema de referência desconhecido")
    if data.get("estado") != "congelado_antes_das_correcoes":
        raise AcceptanceReferenceError("referência não pode declarar o avaliador aprovado")
    base = path.parent
    files = data.get("hashes")
    if not isinstance(files, dict) or not files:
        raise AcceptanceReferenceError("referência precisa congelar arquivos e hashes")
    for relative, expected in files.items():
        selected = corpus._inside(base, relative)
        if sha(selected) != expected:
            raise AcceptanceReferenceError(f"hash divergente: {relative}")
    frozen_catalog = read_json(corpus._inside(base, data["catalogo"]))
    catalog.validate_catalog_v2(frozen_catalog)
    if "contrato_objetivos_avaliacao" not in frozen_catalog:
        raise AcceptanceReferenceError("catálogo precisa declarar objetivos das capacidades")
    targets = read_json(corpus._inside(base, data["metas"]))
    if not {"pesos_sessao", "pesos_modulo", "faixas_desempenho"} <= set(targets):
        raise AcceptanceReferenceError("metas não correspondem ao gerador modular")
    required = {data["catalogo"], data["metas"], data["gabarito_s024"], data["inventario"]}
    seen: set[str] = set()
    groups: set[str] = set()
    for case in data.get("casos", []):
        identifier = case.get("case_id")
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise AcceptanceReferenceError("caso sem identidade ou duplicado")
        seen.add(identifier)
        group = case.get("conjunto")
        if group not in {"desenvolvimento", "reservado"}:
            raise AcceptanceReferenceError(f"{identifier}: conjunto desconhecido")
        groups.add(group)
        required.add(case["entrada"])
        fixture = read_json(corpus._inside(base, case["entrada"]))
        if fixture.get("natureza") != "cenario_sintetico_isolado_nao_e_sessao_real":
            raise AcceptanceReferenceError(f"{identifier}: natureza do cenário ausente")
        checks = case.get("checks")
        if not isinstance(checks, list) or not checks:
            raise AcceptanceReferenceError(f"{identifier}: gabarito vazio")
        check_ids: set[str] = set()
        for check in checks:
            if check.get("check_id") in check_ids or not check.get("check_id"):
                raise AcceptanceReferenceError(f"{identifier}: check duplicado ou vazio")
            check_ids.add(check["check_id"])
            if not isinstance(check.get("caminho"), list) or not check["caminho"]:
                raise AcceptanceReferenceError(f"{identifier}: caminho de observação ausente")
            if "esperado" not in check or not check.get("justificativa"):
                raise AcceptanceReferenceError(f"{identifier}: expectativa sem justificação")
            anchor = check.get("evidencia")
            if not isinstance(anchor, dict):
                raise AcceptanceReferenceError(f"{identifier}: evidência ausente")
            observed = corpus._pointer(fixture, anchor.get("ponteiro", ""))
            if observed is corpus.MISSING or anchor.get("fragmento", "") not in str(observed):
                raise AcceptanceReferenceError(f"{identifier}: evidência não pertence à entrada")
            if not anchor.get("fragmento"):
                raise AcceptanceReferenceError(f"{identifier}: fragmento de evidência vazio")
    if not seen or groups != {"desenvolvimento", "reservado"} or not required <= set(files):
        raise AcceptanceReferenceError("referência sem arquivos congelados ou sem recorte reservado")
    historical = read_json(corpus._inside(base, data["gabarito_s024"]))
    if historical.get("sessao_id") != "024" or historical.get("natureza") != "referencia_historica_nao_reescreve_o_pacote":
        raise AcceptanceReferenceError("referência histórica deve preservar a sessão 024")
    source = historical.get("fonte", {})
    if not isinstance(source.get("corte_bytes"), int) or source["corte_bytes"] <= 0:
        raise AcceptanceReferenceError("corte histórico inválido")
    if source.get("bruto_versionado") is not False:
        raise AcceptanceReferenceError("rollout bruto deve permanecer fora do Git")
    known_criteria = {
        capability["contrato_objetivo"]["criterio_id"]
        for module in frozen_catalog["modulos"]
        for capability in module["subcapacidades"]
    }
    for group in ("desenvolvimento", "reservado"):
        entries = historical.get(group)
        if not isinstance(entries, list) or not entries:
            raise AcceptanceReferenceError(f"gabarito histórico sem {group}")
        for entry in entries:
            if not entry.get("expectativas") or not entry.get("ancoras"):
                raise AcceptanceReferenceError("referência histórica sem expectativa e fonte")
            for expectation in entry["expectativas"]:
                if expectation.get("criterio") not in known_criteria:
                    raise AcceptanceReferenceError("referência histórica usa critério desconhecido")
                if expectation.get("estado_referencia") not in {"confirmada", "parcial", "pendente"}:
                    raise AcceptanceReferenceError("julgamento de referência sem estado explícito")
                if not expectation.get("justificativa"):
                    raise AcceptanceReferenceError("julgamento sem justificativa")
    return data


def verify_native_source(path: Path, historical: dict[str, Any]) -> dict[str, Any]:
    source = historical["fonte"]
    with path.open("rb") as handle:
        content = handle.read(source["corte_bytes"])
    if len(content) != source["corte_bytes"] or hashlib.sha256(content).hexdigest() != source["sha256"]:
        raise AcceptanceReferenceError("rollout disponível não corresponde ao corte histórico")
    if not content.endswith(b"\n"):
        raise AcceptanceReferenceError("corte histórico termina no meio de um registro")
    records = [json.loads(line) for line in content.decode("utf-8").splitlines()]
    count = 0
    for group in ("desenvolvimento", "reservado"):
        for entry in historical[group]:
            for anchor in entry["ancoras"]:
                line = anchor["linha"]
                if type(line) is not int or not 1 <= line <= len(records):
                    raise AcceptanceReferenceError("âncora fora do corte histórico")
                value = corpus._pointer(records[line - 1], anchor["ponteiro"])
                if not isinstance(value, str) or hashlib.sha256(value.encode()).hexdigest() != anchor["sha256_texto"]:
                    raise AcceptanceReferenceError("texto histórico diverge da âncora")
                count += 1
    return {"fonte_verificada": True, "bytes": len(content), "ancoras_verificadas": count}


def _row(generator: Any, data: dict[str, Any], modules: list[dict[str, Any]], targets: dict[str, Any], gates=None):
    rows = generator._module_summary_v2(modules, data, [], targets, 0, module_coverage_gates=gates)
    return next(item for item in rows if item["modulo"] == data.get("module_id", "narrative_delivery"))


def observe_dashboard(scorecard: dict[str, Any]) -> dict[str, Any]:
    """Executa as funções reais de apresentação com DOM mínimo, sem rede."""
    node = shutil.which("node")
    if node is None:
        return {"disponivel": False, "motivo": "node_ausente"}
    source = (ROOT / "evaluation/dashboard/app.js").read_text(encoding="utf-8")
    functions = []
    for name in ("scoreBand", "scoreColor", "renderScore"):
        start = source.index(f"  function {name}(")
        end = source.index("\n  }", start) + len("\n  }")
        functions.append(source[start:end])
    script = """
const scorecard = JSON.parse(process.argv[1]);
const nodes = new Map();
const $ = key => { if (!nodes.has(key)) nodes.set(key,{textContent:'',className:'',style:{setProperty(){}}}); return nodes.get(key); };
const state={scorecard,manifestations:[],localManifestations:[],sessionEntry:{sessao_id:'024'}};
const number = value => value == null ? null : Number(value);
const clamp = value => Math.max(0,Math.min(100,value));
const formatScore = value => value == null ? 'N/D' : String(value);
const isV2=()=>true;
const previewSessionScore=()=>({score:scorecard.nota_geral_0a100,player:null});
const playerScores=()=>({global:null,answered:0});
const comparableSessions=()=>[];
const PT={format:String};
""" + "\n".join(functions) + """
renderScore();
const band=$('#overallBand').textContent;
console.log(JSON.stringify({disponivel:true,faixa_visivel:band,nao_exibe_saudavel:!band.toLowerCase().includes('saud'),nota_principal_sem_numero:!/[0-9]/.test($('#overallScore').textContent)}));
"""
    result = subprocess.run([node, "-e", script, json.dumps(scorecard)], capture_output=True, text=True, check=True, timeout=15)
    return json.loads(result.stdout)


def observe(fixture: dict[str, Any], analyzer: Any, generator: Any, modules: list[dict[str, Any]], targets: dict[str, Any], work: Path) -> dict[str, Any]:
    kind = fixture["tipo"]
    if kind in {"rollout", "omissao"}:
        path = work / "cenario.jsonl"
        path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in fixture["registros"]), encoding="utf-8")
        report = analyzer.analyze(path)
        if kind == "rollout":
            rows = generator._module_summary_v2(modules, report["modular_ledger_v2"], [], targets, 0, module_coverage_gates=report["module_coverage_gates"])
            return {"metricas": report["all_turns"], "resultados": report["operation_outcomes"], "cobertura": report["module_coverage_gates"], "modulos": {row["modulo"]: row for row in rows}}
        assessments = report["modular_ledger_v2"].get("quality_assessments", [])
        matches = [item for item in assessments if item.get("module_id") == fixture["module_id"] and item.get("eligibility") == "sim" and item.get("activation") == "ausente" and (item.get("adjudication") or {}).get("state") == "confirmada"]
        return {"omissoes_elegiveis_avaliadas": len(matches)}
    if kind == "qualidade":
        applied = analyzer.apply_modular_adjudications(fixture["ledger"], fixture["adjudicacoes"])
        row = _row(generator, applied, modules, targets)
        scorecard = generator._scorecard_v2("900", {"narration_turns": {}}, applied, [row], {"violacoes_criticas": []}, {"narration_turns": {}}, targets, [])
        return {"modulo": row, "scorecard": scorecard, "aprovacao_geral_saudavel": scorecard.get("faixa_geral") == "saudavel"}
    if kind == "painel":
        return observe_dashboard(fixture["scorecard"])
    raise AcceptanceReferenceError(f"tipo de cenário desconhecido: {kind}")


def measure(path: Path = DEFAULT_MANIFEST, group: str = "desenvolvimento") -> dict[str, Any]:
    if group not in {"desenvolvimento", "reservado", "todos"}:
        raise AcceptanceReferenceError("seleção de conjunto inválida")
    data = validate_reference(path)
    base = path.parent
    analyzer = corpus._module(corpus.ANALYZER, "aceite_objetivos_analyzer")
    generator = corpus._module(corpus.GENERATOR, "aceite_objetivos_generator")
    modules = read_json(corpus._inside(base, data["catalogo"]))["modulos"]
    targets = read_json(corpus._inside(base, data["metas"]))
    results = []
    selected = [case for case in data["casos"] if group == "todos" or case["conjunto"] == group]
    if not selected:
        raise AcceptanceReferenceError("nenhum caso selecionado; aprovação vazia é proibida")
    with tempfile.TemporaryDirectory(prefix="aceite-objetivos-") as directory:
        for index, case in enumerate(selected):
            work = Path(directory) / str(index)
            work.mkdir()
            observed = observe(read_json(corpus._inside(base, case["entrada"])), analyzer, generator, modules, targets, work)
            for check in case["checks"]:
                value = corpus._at(observed, check["caminho"])
                results.append({"case_id": case["case_id"], "check_id": check["check_id"], "esperado": check["esperado"], "observado": None if value is corpus.MISSING else value, "disponivel": value is not corpus.MISSING, "ok": corpus._same(value, check["esperado"]), "justificativa": check["justificativa"]})
    failures = sum(not result["ok"] for result in results)
    return {"schema_resultado_referencia_avaliacao": 1, "natureza": "medicao_de_regressoes_nao_aceite_final", "conjunto": group, "manifest_sha256": sha(path), "codigo_sha256": {"analisador": sha(corpus.ANALYZER), "parser_historico": sha(ROOT / "ferramentas/_analisar_rollout_core.py"), "decisao_terminal": sha(ROOT / "ferramentas/resultados_operacoes.py"), "contrato_atividades": sha(ROOT / "ferramentas/atividades_modulares.py"), "experiencia": sha(ROOT / "ferramentas/experiencia_avaliacao.py"), "gerador": sha(corpus.GENERATOR), "dashboard": sha(ROOT / "evaluation/dashboard/app.js"), "apresentacao": sha(ROOT / "ferramentas/apresentacao_avaliacao.py"), "executor": sha(Path(__file__))}, "status_regressoes": "reprovado" if failures else "aprovado", "g0": "nao_decidido_por_este_comando; consultar_verificacao_amv05", "casos": len(selected), "checks": len(results), "falhas": failures, "resultados": results}


def measure_native_activities(path: Path, historical: dict[str, Any]) -> dict[str, Any]:
    """Reanalisa apenas o corte congelado; publica contagens, nunca seu bruto."""
    verified = verify_native_source(path, historical)
    analyzer = corpus._module(corpus.ANALYZER, "aceite_atividades_nativas")
    with path.open("rb") as handle:
        content = handle.read(historical["fonte"]["corte_bytes"])
    with tempfile.TemporaryDirectory(prefix="aceite-atividades-") as temporary:
        cut = Path(temporary) / "fonte.jsonl"
        cut.write_bytes(content)
        report = analyzer.analyze(cut)
    ledger = report["module_activities"]
    activities = ledger["activities"]
    phases = Counter(f"{row['module_id']}|{row['fase']}" for row in activities)
    orphan_phases = Counter(f"{row['module_id']}|{row['fase']}" for row in ledger["orphan_receipts"])
    fields = ("activity_units", "complete_receipts", "missing_receipts", "incomplete_receipts",
              "duplicate_receipts", "contradictory_receipts", "orphan_receipts", "coverage_complete")
    metrics = report["all_turns"]
    return {
        "schema_reanalise_atividades": 1,
        "natureza": "reanalise_de_associacao_historica_sem_reescrever_pacote_024",
        "sessao_id": historical["sessao_id"], "fonte": historical["fonte"],
        "verificacao_fonte": verified, "detector": analyzer.MODULAR_DETECTOR_VERSION,
        "codigo_sha256": {str(source.relative_to(ROOT)): sha(source) for source in
                          (corpus.ANALYZER, ROOT / "ferramentas/atividades_modulares.py",
                           ROOT / "ferramentas/_module_facade.py", ROOT / "ferramentas/resultados_operacoes.py",
                           Path(__file__))},
        "atividades": {"resumo": ledger["summary"], "por_fase": dict(sorted(phases.items())),
                       "por_estado_operacional": dict(sorted(Counter(row["operation_state"] for row in activities).items())),
                       "orfaos_por_fase": dict(sorted(orphan_phases.items())),
                       "compatibilidade_sem_gatilho_independente": sum(row["fonte_expectativa"] ==
                           "compatibilidade_legada_sem_gatilho_independente" for row in activities),
                       "versao_produtor_ausente_no_historico": sum(row["versao_produtor"] is None for row in activities)},
        "cobertura_modular": {module: {key: value[key] for key in fields}
                             for module, value in report["module_coverage_gates"].items()},
        "metricas_operacionais": {key: metrics[key] for key in
            ("attempted_write_calls", "successful_write_calls", "failed_write_calls", "unknown_write_calls",
             "tool_calls", "input_tokens", "write_target_touches")},
        "limites": ["Associação de passagens não mede qualidade da experiência.",
                    "Metadados ausentes no histórico permanecem ausentes; versões atuais não são atribuídas ao produtor antigo.",
                    "Atividade sem recibo específico continua bloqueada; o recibo genérico não a cobre."],
        "g0": "pendente_experiencia_e_dashboard_amv04_05",
    }


def measure_native_experience(path: Path, historical: dict[str, Any], adjudications_path: Path) -> dict[str, Any]:
    """Consome pareceres separados do produtor, verifica fontes e publica recorte.

    A integridade das referências e a calibração não são validação cega por
    terceiro. O dashboard completo continua sendo a entrega da AMV-05.
    """
    verified = verify_native_source(path, historical)
    analyzer = corpus._module(corpus.ANALYZER, "aceite_experiencia_nativa")
    generator = corpus._module(corpus.GENERATOR, "aceite_experiencia_gerador")
    with path.open("rb") as handle:
        content = handle.read(historical["fonte"]["corte_bytes"])
    with tempfile.TemporaryDirectory(prefix="aceite-experiencia-") as temporary:
        cut = Path(temporary) / "fonte.jsonl"
        cut.write_bytes(content)
        report = analyzer.analyze(cut, modular_adjudications=read_json(adjudications_path))
    ledger = report["modular_ledger_v2"]
    assessments = ledger["quality_assessments"]
    if not assessments or not any(row.get("review", {}).get("verification") == "verificada" for row in assessments):
        raise AcceptanceReferenceError("revisão sem pareceres vinculados e verificados; aprovação vazia proibida")
    calibration = []
    for group in ("desenvolvimento", "reservado"):
        for reference in historical[group]:
            for expectation in reference["expectativas"]:
                matches = [row for row in assessments if row["interaction_ref"] == reference["interaction_ref"]
                           and row["criterion_id"] == expectation["criterio"]]
                calibration.append({"reference_id": reference["reference_id"], "conjunto": group,
                                    "criterion_id": expectation["criterio"], "referencia": expectation,
                                    "assessments": [row["assessment_id"] for row in matches],
                                    "estados_observados": [row["adjudication"]["state"] for row in matches],
                                    "limite": "Comparação de estados e parecer literal; independência estatística ou entre autores não demonstrada."})
    if any(not row["assessments"] for row in calibration):
        raise AcceptanceReferenceError("revisão não cobre todos os critérios do gabarito, inclusive reservado")
    per_module = {module: generator._interaction_quality_metrics([row for row in assessments if row["module_id"] == module])
                  for module in {m["id"] for m in read_json(catalog.DEFAULT_CATALOG)["modulos"]}}
    source_frames = ledger["experience_review"]["frames"]
    recorded = ROOT / "evaluation/sessions/024/interacoes.json"
    recorded_versions = {row["interaction_ref"]: row.get("module_versions") for row in read_json(recorded).get("interactions", []) if row.get("interaction_ref")}
    return {"schema_reanalise_experiencia": 1, "natureza": "revisao_poshoc_nao_reescreve_execucao_historica",
            "sessao_id": historical["sessao_id"], "fonte": historical["fonte"], "verificacao_fonte": verified,
            "pareceres_sha256": sha(adjudications_path), "rubrica": ledger["experience_review"]["rubric_version"],
            "versoes_execucao_historica": {"source_sha256": sha(recorded), "por_interacao": recorded_versions,
                                           "regra": "Metadados históricos preservados; versão da rubrica nova não é versão executada na 024."},
            "codigo_sha256": {str(source.relative_to(ROOT)): sha(source) for source in
                              (corpus.ANALYZER, corpus.GENERATOR, ROOT / "ferramentas/experiencia_avaliacao.py", Path(__file__))},
            "quality_assessments": assessments, "player_feedback": ledger["player_feedback"],
            "metricas_por_modulo": per_module, "calibracao_por_criterio": calibration,
            "cobertura": {"frames": len(source_frames), "unidades_criterio": sum(len(frame["criteria"]) for frame in source_frames),
                          "criterios_com_parecer": len({(row["interaction_ref"], row["criterion_id"]) for row in assessments}),
                          "sem_parecer": sum(not value.get("assessment_id") for frame in source_frames for value in frame["criteria"].values()),
                          "indeterminados_ou_sem_parecer": sum(value["state"] == "indeterminada" for frame in source_frames for value in frame["criteria"].values())},
            "limites": ["Snapshot integral anterior não reconstruído; nenhum estado atual foi usado.",
                        "Critérios sem fonte ou parecer suficiente permanecem fora dos denominadores.",
                        "Revisão separada do produtor não é validação cega por terceiro.",
                        "Qualidade da prosa não prova persistência futura de promessa, recompensa ou plano."],
            "g0": "revisao_semantica_entregue_dashboard_pendente_amv05"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifesto", type=Path, default=DEFAULT_MANIFEST)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--validar", action="store_true")
    modes.add_argument("--medir", action="store_true")
    modes.add_argument("--reavaliar-atividades", action="store_true")
    modes.add_argument("--reavaliar-experiencia", action="store_true")
    parser.add_argument("--conjunto", choices=("desenvolvimento", "reservado", "todos"), default="desenvolvimento")
    parser.add_argument("--fonte", type=Path, help="Confere corte e âncoras sem copiar o bruto.")
    parser.add_argument("--adjudicacoes", type=Path, help="Pareceres pós-hoc com evidência literal e vínculo ao corte.")
    parser.add_argument("--saida", type=Path, help="Novo resultado; nunca sobrescreve outro resultado.")
    args = parser.parse_args()
    try:
        reference = validate_reference(args.manifesto)
        historical = read_json(corpus._inside(args.manifesto.parent, reference["gabarito_s024"]))
        if args.reavaliar_experiencia:
            if not args.fonte or not args.adjudicacoes:
                raise AcceptanceReferenceError("--reavaliar-experiencia exige --fonte e --adjudicacoes")
            result = measure_native_experience(args.fonte, historical, args.adjudicacoes)
        elif args.reavaliar_atividades:
            if not args.fonte:
                raise AcceptanceReferenceError("--reavaliar-atividades exige --fonte com o rollout histórico")
            result = measure_native_activities(args.fonte, historical)
        else:
            result = measure(args.manifesto, args.conjunto) if args.medir else {"status_artefatos": "valido", "g0": "nao_avaliado", "casos": len(reference["casos"])}
        if args.fonte and not args.reavaliar_atividades and not args.reavaliar_experiencia:
            result.update(verify_native_source(args.fonte, historical))
        if args.saida:
            corpus._write_once(args.saida, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(result.get("status_regressoes") == "reprovado")
    except (AcceptanceReferenceError, corpus.CorpusError, catalog.EvaluationCatalogError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "erro_referencia", "mensagem": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
