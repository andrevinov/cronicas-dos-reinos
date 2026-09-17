#!/usr/bin/env python3
"""Valida e executa o corpus independente do instrumento de avaliação.

O comando não corrige o avaliador. Enquanto houver regressões conhecidas, a
execução termina com código 1 e discrimina falhas do medidor de erros do corpus.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

from ferramentas import entrada_medicao

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = ROOT / "evaluation/regressoes-rollout-v1/corpus.json"
ANALYZER = ROOT / "ferramentas/analisar-rollout.py"
GENERATOR = ROOT / "ferramentas/gerar-avaliacao-sessao.py"
ACCEPTANCE = ROOT / "ferramentas/aceitacao_modular_v2.py"
MISSING = object()


class CorpusError(ValueError):
    """O corpus ou seu gabarito não satisfaz o contrato da atividade 2."""


def _json(path: Path) -> Any:
    try:
        return entrada_medicao._json(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise CorpusError(f"JSON inválido em {path}: {exc}") from exc


def _hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise CorpusError(f"não foi possível calcular hash de {path}: {exc}") from exc


def _inside(base: Path, relative: Any) -> Path:
    if not isinstance(relative, str) or not relative:
        raise CorpusError("caminho relativo vazio ou inválido")
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise CorpusError(f"caminho escapa do corpus: {relative}")
    return path


def _module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise CorpusError(f"não foi possível carregar {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _pointer(value: Any, pointer: str) -> Any:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise CorpusError(f"ponteiro JSON inválido: {pointer!r}")
    current = value
    for raw in pointer[1:].split("/") if pointer != "/" else []:
        key = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list) and key.isdigit() and int(key) < len(current):
            current = current[int(key)]
        else:
            return MISSING
    return current


def _at(value: Any, path: Iterable[Any]) -> Any:
    current = value
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        elif isinstance(current, list) and isinstance(key, int) and 0 <= key < len(current):
            current = current[key]
        else:
            return MISSING
    return current


def _same(left: Any, right: Any) -> bool:
    if left is MISSING or right is MISSING:
        return left is right
    try:
        return entrada_medicao.canonical_bytes(left) == entrada_medicao.canonical_bytes(right)
    except (TypeError, ValueError):
        return False


def _rollout_records(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = entrada_medicao._json(line)
        except ValueError as exc:
            raise CorpusError(f"{path}: linha {line_no}: {exc}") from exc
        if not isinstance(row, dict):
            raise CorpusError(f"{path}: linha {line_no} não é objeto")
        rows.append(row)
    return rows


def validate_corpus(path: Path = DEFAULT_CORPUS) -> dict[str, Any]:
    manifest = _json(path)
    if not isinstance(manifest, dict) or manifest.get("schema_corpus_regressao_rollout") != 1:
        raise CorpusError("corpus precisa usar schema_corpus_regressao_rollout=1")
    expected_fields = {
        "schema_corpus_regressao_rollout", "versao_corpus", "natureza",
        "fonte_expectativas", "escopo", "configuracao", "sha256_configuracao",
        "casos", "relacoes",
    }
    if set(manifest) != expected_fields:
        raise CorpusError(f"campos do corpus divergentes: {sorted(set(manifest) ^ expected_fields)}")
    if not isinstance(manifest.get("fonte_expectativas"), str) or "não gerados pelo avaliador" not in manifest["fonte_expectativas"]:
        raise CorpusError("o corpus precisa declarar independência dos gabaritos")
    base = path.parent
    config = manifest.get("configuracao")
    hashes = manifest.get("sha256_configuracao")
    if not isinstance(config, dict) or not isinstance(hashes, dict):
        raise CorpusError("configuração e seus hashes precisam ser objetos")
    config_files: set[Path] = set()
    for relative in config.values():
        selected = _inside(base, relative)
        if selected.is_dir():
            config_files.update(selected.glob("*.json"))
        else:
            config_files.add(selected)
    actual_hashes = {str(item.relative_to(base)): _hash(item) for item in sorted(config_files)}
    if hashes != actual_hashes:
        raise CorpusError("hashes da configuração congelada divergem")
    contract = _json(_inside(base, config["contrato_medicao"]))
    if entrada_medicao.validate_contract(contract):
        raise CorpusError("contrato de medição congelado é inválido")
    units = set(contract["unidades"])
    cases = manifest.get("casos")
    if not isinstance(cases, list) or not cases:
        raise CorpusError("o corpus precisa conter casos")
    case_ids: set[str] = set()
    for case in cases:
        fields = {
            "case_id", "descricao", "conjunto", "origem", "rollout",
            "sha256_rollout", "gabarito", "sha256_gabarito", "adjudicacoes",
            "sha256_adjudicacoes", "tags",
        }
        if not isinstance(case, dict) or set(case) != fields:
            raise CorpusError("caso com estrutura divergente")
        case_id = case.get("case_id")
        if not isinstance(case_id, str) or not case_id or case_id in case_ids:
            raise CorpusError(f"case_id inválido ou duplicado: {case_id!r}")
        case_ids.add(case_id)
        if case.get("conjunto") != "desenvolvimento" or not isinstance(case.get("descricao"), str) or not case["descricao"] or not isinstance(case.get("tags"), list) or any(not isinstance(tag, str) or not tag for tag in case["tags"]):
            raise CorpusError(f"{case_id}: descrição, conjunto ou tags inválidos")
        origin = case.get("origem")
        if not isinstance(origin, dict) or set(origin) != {"tipo", "referencias_s023"} or origin.get("tipo") not in {"sintetico", "reducao_s023"} or not isinstance(origin.get("referencias_s023"), list) or any(not isinstance(ref, str) or not ref for ref in origin["referencias_s023"]):
            raise CorpusError(f"{case_id}: origem inválida")
        if origin["tipo"] == "reducao_s023" and not origin["referencias_s023"]:
            raise CorpusError(f"{case_id}: redução da sessão 023 exige referência")
        rollout = _inside(base, case["rollout"])
        golden_path = _inside(base, case["gabarito"])
        adjudications_path = _inside(base, case["adjudicacoes"])
        if _hash(rollout) != case["sha256_rollout"] or _hash(golden_path) != case["sha256_gabarito"]:
            raise CorpusError(f"{case_id}: rollout ou gabarito diverge do hash")
        if _hash(adjudications_path) != case["sha256_adjudicacoes"]:
            raise CorpusError(f"{case_id}: adjudicações divergem do hash")
        records = _rollout_records(rollout)
        golden = _json(golden_path)
        if not isinstance(golden, dict) or set(golden) != {"schema_gabarito_regressao", "case_id", "natureza", "checks"} or golden.get("schema_gabarito_regressao") != 1 or golden.get("case_id") != case_id:
            raise CorpusError(f"{case_id}: gabarito inválido")
        check_ids: set[str] = set()
        for check in golden.get("checks") or []:
            required = {"check_id", "operacao", "caminho", "esperado", "unidade_avaliativa", "evidencias", "justificativa"}
            if not isinstance(check, dict) or set(check) != required:
                raise CorpusError(f"{case_id}: check com estrutura divergente")
            check_id = check.get("check_id")
            if not isinstance(check_id, str) or not check_id or check_id in check_ids:
                raise CorpusError(f"{case_id}: check_id inválido ou duplicado")
            check_ids.add(check_id)
            if check.get("operacao") not in {"igual", "ausente"} or not isinstance(check.get("caminho"), list) or not check["caminho"]:
                raise CorpusError(f"{case_id}/{check_id}: operação ou caminho inválido")
            if check.get("unidade_avaliativa") not in units:
                raise CorpusError(f"{case_id}/{check_id}: unidade desconhecida")
            if not isinstance(check.get("justificativa"), str) or not check["justificativa"]:
                raise CorpusError(f"{case_id}/{check_id}: justificativa ausente")
            evidence = check.get("evidencias")
            if not isinstance(evidence, list) or not evidence:
                raise CorpusError(f"{case_id}/{check_id}: evidência ausente")
            for anchor in evidence:
                if not isinstance(anchor, dict) or set(anchor) not in ({"fonte", "linha", "ponteiro", "fragmento"}, {"fonte", "ponteiro", "esperado"}):
                    raise CorpusError(f"{case_id}/{check_id}: âncora inválida")
                if anchor["fonte"] == "rollout":
                    line_no = anchor.get("linha")
                    if not isinstance(line_no, int) or not 1 <= line_no <= len(records):
                        raise CorpusError(f"{case_id}/{check_id}: linha de evidência inválida")
                    observed = _pointer(records[line_no - 1], anchor["ponteiro"])
                    if observed is MISSING or anchor["fragmento"] not in str(observed):
                        raise CorpusError(f"{case_id}/{check_id}: fragmento não está na evidência")
                else:
                    source = _inside(base, anchor["fonte"])
                    observed = _pointer(_json(source), anchor["ponteiro"])
                    if not _same(observed, anchor["esperado"]):
                        raise CorpusError(f"{case_id}/{check_id}: evidência externa diverge")
    relations = manifest.get("relacoes")
    if not isinstance(relations, list) or not relations:
        raise CorpusError("o corpus precisa declarar relações metamórficas")
    relation_ids: set[str] = set()
    for relation in relations:
        fields = {"relation_id", "tipo", "casos", "caminhos", "unidade_excluida", "justificativa"}
        if not isinstance(relation, dict) or set(relation) != fields or relation.get("tipo") != "equivalencia":
            raise CorpusError("relação metamórfica inválida")
        if relation["relation_id"] in relation_ids or set(relation["casos"]) - case_ids or len(relation["casos"]) != 2:
            raise CorpusError("relação duplicada ou aponta para caso inexistente")
        relation_ids.add(relation["relation_id"])
        if not relation["caminhos"] or not isinstance(relation.get("justificativa"), str):
            raise CorpusError("relação sem caminhos ou justificativa")
    return manifest


def _source_paths(base: Path, config: dict[str, str], adjudications: str) -> dict[str, Path]:
    return {
        "catalogo": _inside(base, config["catalogo"]),
        "metas": _inside(base, config["metas"]),
        "baseline": _inside(base, config["baseline"]),
        "guardrails": _inside(base, config["guardrails"]),
        "series": _inside(base, config["series"]),
        "releases": _inside(base, config["releases"]),
        "interacoes": _inside(base, config["interacoes"]),
        "adjudicacoes": _inside(base, adjudications),
        "validade": _inside(base, config["validade"]),
    }


def _read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        if row.get("latencia_segundos") not in {None, ""}:
            row["latencia_segundos"] = float(row["latencia_segundos"])
    return rows


def _operations(analyzer: Any, turns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Consome o contrato futuro `operations`; chamadas diretas continuam válidas."""
    result = []
    for turn in turns:
        for call in turn.get("calls") or []:
            expanded = call.get("operations")
            if isinstance(expanded, list):
                result.extend(item for item in expanded if isinstance(item, dict))
            elif not analyzer._nested_exec_commands(str(call.get("command") or "")):
                result.append(call)
    return result


def _domain_projection(analyzer: Any, report: dict[str, Any], module_rows: list[dict[str, Any]], turns: list[dict[str, Any]]) -> dict[str, Any]:
    operations = _operations(analyzer, turns)
    completed = [item for item in operations if item.get("command_executed") is not False and item.get("output_success") is True]
    failed = [item for item in operations if item.get("command_executed") is not False and item.get("output_success") is False]
    unknown = [item for item in operations if item.get("command_executed") is not False and item.get("output_success") is None]
    preparations = sum(
        item.get("output_success") is True
        and any(program in {"cronica", "cronica.py"} and args[:1] == ["preparar"] for program, args in analyzer._command_invocations(str(item.get("command") or "")))
        for item in operations
    )
    events = (report.get("modular_ledger_v2") or {}).get("events") or []
    return {
        "operacoes_concluidas": len(completed),
        "operacoes_falhas": len(failed),
        "resultados_indeterminados": len(unknown),
        "preparos_concluidos": preparations,
        "efeitos_memoria_persistida": sum(
            item.get("module_id") == "context_and_memory"
            and item.get("materialized_result_observed") == "memoria_persistida"
            for item in events
        ),
        "modulos_bloqueados": sum(item.get("aplicabilidade_avaliacao") == "falha_instrumentacao" for item in module_rows),
        "auditorias_semanticas": len((report.get("modular_ledger_v2") or {}).get("semantic_audits") or []),
        "qualidade_narrativa_auditada": bool((report.get("modular_ledger_v2") or {}).get("semantic_audits")),
    }


def _aggregate_property(generator: Any, session_id: str, report: dict[str, Any], module_rows: list[dict[str, Any]], validity: dict[str, Any], baseline: dict[str, Any], targets: dict[str, Any]) -> bool:
    blocked = [index for index, row in enumerate(module_rows) if row.get("aplicabilidade_avaliacao") == "falha_instrumentacao"]
    if not blocked:
        return False
    outcomes = []
    for value in (1.0, 99.0):
        changed = copy.deepcopy(module_rows)
        for index in blocked:
            for key in ("nota_calibracao_0a100", "nota_eficacia_integridade_0a100", "nota_confiabilidade_proxy_0a100"):
                changed[index][key] = value
        card = generator._scorecard_v2(session_id, report, report["modular_ledger_v2"], changed, validity, baseline, targets, [])
        outcomes.append({"nota": card.get("nota_geral_0a100"), "eixos": card.get("eixos")})
    return _same(outcomes[0], outcomes[1])


def _acceptance_property(acceptance: Any, output: Path, module_rows: list[dict[str, Any]], root: Path) -> bool:
    package = root / "evaluation/sessions/990"
    package.mkdir(parents=True)
    for name in (
        "manifest.json",
        "scorecard.json",
        "interacoes.json",
        "resumo-modulos.json",
        "proveniencia-medicao.json",
    ):
        (package / name).write_bytes((output / name).read_bytes())
    (root / "evaluation/sessions/index.json").write_text(json.dumps({"sessoes": [{"sessao_id": "990", "serie_avaliacao": "modules-v2", "caminho": "990"}]}), encoding="utf-8")
    state = acceptance.first_real_session_status(root)
    blocked = any(item.get("aplicabilidade_avaliacao") == "falha_instrumentacao" for item in module_rows)
    return not (blocked and state.get("aceite_final") is True)


def _evaluate_case(case: dict[str, Any], base: Path, config: dict[str, str], analyzer: Any, generator: Any, acceptance: Any, work: Path) -> dict[str, Any]:
    rollout = _inside(base, case["rollout"])
    sources = _source_paths(base, config, case["adjudicacoes"])
    frozen = entrada_medicao.prepare_input(
        rollout, session_id="990", source_paths=sources,
        contract_path=_inside(base, config["contrato_medicao"]),
        modules_directory=_inside(base, config["contratos_modulos"]),
    )
    projection: dict[str, Any] = {"entrada": frozen}
    if frozen["status"] == "bloqueada":
        return projection
    analyzer._CATALOG_V2_PATH = sources["catalogo"]
    output = work / case["case_id"] / "pacote"
    result = generator.generate_session_evaluation(
        rollout,
        session_id="990",
        output_dir=output,
        measurement_input=frozen,
    )
    report = _json(output / "telemetria.json")
    modules = _json(output / "resumo-modulos.json")["modulos"]
    scorecard = _json(output / "scorecard.json")
    turns, _ = analyzer._scan_observations(rollout, None)
    projection.update({"telemetria": report, "resumo_modulos": {"modulos": modules}, "scorecard": scorecard})
    projection["dominio"] = _domain_projection(analyzer, report, modules, turns)
    projection["propriedades"] = {
        "agregado_ignora_componentes_bloqueados": _aggregate_property(
            generator, "990", report, modules, _json(sources["validade"]), _json(sources["baseline"]), _json(sources["metas"])
        )
    }
    if "aceite" in case.get("tags", []):
        projection["propriedades"]["aceite_recusa_instrumentacao_falha"] = _acceptance_property(
            acceptance, output, modules, work / case["case_id"] / "aceite"
        )
    return projection


def run_corpus(path: Path = DEFAULT_CORPUS, selected: set[str] | None = None) -> dict[str, Any]:
    manifest = validate_corpus(path)
    known_cases = {case["case_id"] for case in manifest["casos"]}
    if selected and selected - known_cases:
        raise CorpusError(f"casos inexistentes: {sorted(selected - known_cases)}")
    base, config = path.parent, manifest["configuracao"]
    analyzer = _module(ANALYZER, "corpus_analyzer")
    generator = _module(GENERATOR, "corpus_generator")
    acceptance = _module(ACCEPTANCE, "corpus_acceptance")
    original_loader = generator._load_module

    def frozen_loader(module_path: Path, name: str) -> Any:
        if Path(module_path).resolve() == ANALYZER.resolve():
            return analyzer
        return original_loader(module_path, name)

    generator._load_module = frozen_loader
    outcomes: dict[str, dict[str, Any]] = {}
    checks = []
    with tempfile.TemporaryDirectory(prefix="corpus-avaliacao-") as tmp:
        work = Path(tmp)
        for case in manifest["casos"]:
            if selected and case["case_id"] not in selected:
                continue
            projection = _evaluate_case(case, base, config, analyzer, generator, acceptance, work)
            outcomes[case["case_id"]] = projection
            golden = _json(_inside(base, case["gabarito"]))
            for expected in golden["checks"]:
                observed = _at(projection, expected["caminho"])
                passed = observed is MISSING if expected["operacao"] == "ausente" else _same(observed, expected["esperado"])
                checks.append({
                    "tipo": "gabarito", "case_id": case["case_id"], "check_id": expected["check_id"],
                    "ok": passed, "caminho": expected["caminho"], "esperado": expected["esperado"],
                    "observado_disponivel": observed is not MISSING,
                    "observado": None if observed is MISSING else observed,
                    "unidade_avaliativa": expected["unidade_avaliativa"],
                })
        for relation in manifest["relacoes"]:
            left_id, right_id = relation["casos"]
            if left_id not in outcomes or right_id not in outcomes:
                continue
            for index, pointer in enumerate(relation["caminhos"], 1):
                left, right = _at(outcomes[left_id], pointer), _at(outcomes[right_id], pointer)
                checks.append({
                    "tipo": "relacao", "case_id": relation["relation_id"], "check_id": f"caminho-{index}",
                    "ok": _same(left, right), "caminho": pointer,
                    "esperado": "valores equivalentes", "observado_disponivel": left is not MISSING and right is not MISSING,
                    "observado": {"esquerda": None if left is MISSING else left, "direita": None if right is MISSING else right},
                    "unidade_avaliativa": "atividade_modular",
                })
    failures = [item for item in checks if not item["ok"]]
    return {
        "schema_resultado_corpus_regressao": 1,
        "versao_corpus": manifest["versao_corpus"],
        "corpus_sha256": _hash(path),
        "codigo_sha256": {
            "analisador": _hash(ANALYZER),
            "gerador": _hash(GENERATOR),
            "aceite": _hash(ACCEPTANCE),
            "executor_corpus": _hash(Path(__file__).resolve()),
        },
        "status": "aprovado" if not failures else "reprovado",
        "casos_executados": len(outcomes), "checks": len(checks), "aprovados": len(checks) - len(failures),
        "falhas": len(failures), "resultados": checks,
    }


def _write_once(path: Path, value: dict[str, Any]) -> None:
    data = entrada_medicao.canonical_bytes(value) + b"\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != data:
        raise CorpusError("a saída já contém outro resultado; use outro arquivo")
    if not path.exists():
        path.write_bytes(data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--somente-validar", action="store_true")
    parser.add_argument("--caso", action="append", default=[])
    parser.add_argument("--saida", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        if args.somente_validar:
            manifest = validate_corpus(args.corpus)
            result = {"status": "valido", "casos": len(manifest["casos"]), "relacoes": len(manifest["relacoes"])}
            code = 0
        else:
            result = run_corpus(args.corpus, set(args.caso) or None)
            code = int(result["status"] != "aprovado")
        if args.saida:
            _write_once(args.saida, result)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"corpus: {result['status']}")
            if "checks" in result:
                print(f"casos={result['casos_executados']} checks={result['checks']} aprovados={result['aprovados']} falhas={result['falhas']}")
                failures = [entry for entry in result["resultados"] if not entry["ok"]]
                for item in failures[:20]:
                    print(f"- {item['case_id']}/{item['check_id']}: esperado={item['esperado']!r}; observado={item['observado']!r}")
                if len(failures) > 20:
                    print(f"... mais {len(failures) - 20} falha(s); use --json ou --saida para o relatório completo.")
            else:
                print(f"casos={result['casos']} relações={result['relacoes']}")
        return code
    except (CorpusError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "erro_corpus", "mensagem": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
