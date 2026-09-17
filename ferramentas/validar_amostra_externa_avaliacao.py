#!/usr/bin/env python3
"""Valida uma amostra real externa ao corpus de desenvolvimento da avaliação.

A amostra é um recorte imutável de rollout. O gabarito descreve apenas estados
operacionais observáveis e foi escrito sem usar notas produzidas pelo avaliador.
O comando é pós-hoc e somente leitura.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "evaluation/validacao-externa-v1/manifest.json"
ANALYZER = ROOT / "ferramentas/analisar-rollout.py"
SCHEMA = 1


class ExternalValidationError(ValueError):
    """A amostra externa ou sua proveniência não satisfaz o contrato."""


def _json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExternalValidationError(f"não foi possível ler {label}: {exc}") from exc
    if not isinstance(value, dict):
        raise ExternalValidationError(f"{label} precisa conter objeto JSON")
    return value


def _sha256(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ExternalValidationError(f"não foi possível calcular hash de {path}: {exc}") from exc


def _relative_path(base: Path, relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ExternalValidationError(f"{label} precisa ser caminho relativo não vazio")
    path = (base / relative).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ExternalValidationError(f"{label} escapa de {base}")
    return path


def _repo_path(repo: Path, relative: Any, label: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ExternalValidationError(f"{label} precisa ser caminho relativo não vazio")
    path = (repo / relative).resolve()
    if not path.is_relative_to(repo.resolve()):
        raise ExternalValidationError(f"{label} escapa do repositório")
    return path


def _analyzer(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location("validacao_externa_analisador", path)
    if spec is None or spec.loader is None:
        raise ExternalValidationError("analisador não pôde ser carregado")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _validate_manifest_structure(manifest: dict[str, Any]) -> None:
    expected = {
        "schema_validacao_externa_avaliacao",
        "validacao_id",
        "natureza",
        "independencia",
        "fonte",
        "amostra",
        "gabarito",
    }
    if manifest.get("schema_validacao_externa_avaliacao") != SCHEMA:
        raise ExternalValidationError("manifesto externo precisa usar schema 1")
    if set(manifest) != expected:
        raise ExternalValidationError(
            f"campos do manifesto externo divergentes: {sorted(set(manifest) ^ expected)}"
        )
    independence = manifest.get("independencia")
    required_independence = {
        "conjunto",
        "fora_corpus_desenvolvimento",
        "sessao_usada_para_diagnostico_s023",
        "expectativas_geradas_pelo_avaliador",
        "limitacao",
    }
    if not isinstance(independence, dict) or set(independence) != required_independence:
        raise ExternalValidationError("declaração de independência externa inválida")
    if (
        independence.get("conjunto") != "validacao_externa_historica"
        or independence.get("fora_corpus_desenvolvimento") is not True
        or independence.get("sessao_usada_para_diagnostico_s023") is not False
        or independence.get("expectativas_geradas_pelo_avaliador") is not False
    ):
        raise ExternalValidationError("amostra não declara independência suficiente")


def _validate_source_anchor(repo: Path, source: dict[str, Any]) -> None:
    expected = {
        "sessao_id",
        "codex_session_id",
        "arquivo",
        "bytes",
        "sha256",
        "manifesto_pacote",
    }
    if not isinstance(source, dict) or set(source) != expected:
        raise ExternalValidationError("âncora da fonte real possui estrutura inválida")
    if source.get("sessao_id") != "022":
        raise ExternalValidationError("amostra externa deve permanecer vinculada à sessão 022")
    package_path = _repo_path(repo, source.get("manifesto_pacote"), "manifesto_pacote")
    package = _json(package_path, "manifesto histórico da sessão 022")
    package_source = package.get("fonte") or {}
    if package.get("sessao_id") != source["sessao_id"] or package.get("serie_avaliacao") != "modules-v2":
        raise ExternalValidationError("manifesto histórico não identifica a sessão modules-v2 esperada")
    comparisons = {
        "arquivo": package_source.get("arquivo"),
        "bytes": package_source.get("bytes"),
        "sha256": package_source.get("sha256"),
        "codex_session_id": package_source.get("codex_session_id"),
    }
    if comparisons != {key: source[key] for key in comparisons}:
        raise ExternalValidationError("âncora da fonte diverge do manifesto histórico da sessão 022")


def _validate_sample(sample: Path, declaration: dict[str, Any]) -> None:
    expected = {"arquivo", "sha256", "linhas_fonte", "registros"}
    if not isinstance(declaration, dict) or set(declaration) != expected:
        raise ExternalValidationError("declaração da amostra possui estrutura inválida")
    if _sha256(sample) != declaration.get("sha256"):
        raise ExternalValidationError("hash da amostra externa diverge")
    raw_lines = sample.read_bytes().splitlines()
    source_lines = declaration.get("linhas_fonte")
    records = declaration.get("registros")
    if (
        not isinstance(source_lines, list)
        or not isinstance(records, list)
        or len(raw_lines) != len(source_lines)
        or len(raw_lines) != len(records)
    ):
        raise ExternalValidationError("mapa de linhas da amostra externa é inconsistente")
    for raw, source_line, record in zip(raw_lines, source_lines, records):
        if (
            not isinstance(source_line, int)
            or isinstance(source_line, bool)
            or source_line <= 0
            or not isinstance(record, dict)
            or set(record) != {"linha_fonte", "sha256"}
            or record.get("linha_fonte") != source_line
            or record.get("sha256") != hashlib.sha256(raw).hexdigest()
        ):
            raise ExternalValidationError("hash ou origem de registro da amostra diverge")
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ExternalValidationError(f"registro JSONL externo inválido: {exc}") from exc
        if not isinstance(decoded, dict):
            raise ExternalValidationError("cada registro da amostra precisa ser objeto JSON")


def _validate_full_source(source_path: Path, source: dict[str, Any], sample: Path, lines: list[int]) -> None:
    if source_path.stat().st_size != source.get("bytes") or _sha256(source_path) != source.get("sha256"):
        raise ExternalValidationError("rollout integral diverge da âncora congelada")
    source_records = source_path.read_bytes().splitlines()
    try:
        selected = [source_records[number - 1] for number in lines]
    except IndexError as exc:
        raise ExternalValidationError("linha declarada não existe no rollout integral") from exc
    if selected != sample.read_bytes().splitlines():
        raise ExternalValidationError("recorte não corresponde às linhas declaradas do rollout integral")


def _validate_golden(golden: dict[str, Any], validation_id: str) -> None:
    expected = {
        "schema_gabarito_validacao_externa",
        "validacao_id",
        "natureza",
        "regra",
        "expectativas",
        "resumo",
    }
    if golden.get("schema_gabarito_validacao_externa") != SCHEMA or set(golden) != expected:
        raise ExternalValidationError("gabarito externo possui estrutura inválida")
    if golden.get("validacao_id") != validation_id:
        raise ExternalValidationError("gabarito e manifesto usam identidades diferentes")
    expectations = golden.get("expectativas")
    if not isinstance(expectations, list) or not expectations:
        raise ExternalValidationError("gabarito externo não possui expectativas")
    identities: set[tuple[str, int]] = set()
    valid_states = {
        "sucesso",
        "falha_operacional",
        "nao_executada",
        "resultado_ausente",
        "resultado_ambiguo",
        "evidencia_insuficiente",
        "erro_detector",
    }
    for item in expectations:
        if not isinstance(item, dict) or set(item) != {
            "parent_call_id", "operation_index", "state", "evidence", "justificativa"
        }:
            raise ExternalValidationError("expectativa externa possui estrutura inválida")
        identity = (item.get("parent_call_id"), item.get("operation_index"))
        evidence = item.get("evidence")
        if (
            not isinstance(identity[0], str)
            or not isinstance(identity[1], int)
            or isinstance(identity[1], bool)
            or identity in identities
            or item.get("state") not in valid_states
            or not isinstance(evidence, dict)
            or set(evidence) != {"source", "marker"}
            or not all(isinstance(evidence.get(key), str) and evidence[key] for key in evidence)
            or not isinstance(item.get("justificativa"), str)
            or not item["justificativa"]
        ):
            raise ExternalValidationError("expectativa externa é ambígua ou inválida")
        identities.add(identity)


def validate_external_sample(
    repo: Path = ROOT,
    *,
    manifest_path: Path | None = None,
    source_path: Path | None = None,
) -> dict[str, Any]:
    repo = Path(repo).resolve()
    manifest_path = Path(manifest_path or repo / DEFAULT_MANIFEST.relative_to(ROOT)).resolve()
    manifest = _json(manifest_path, "manifesto da validação externa")
    _validate_manifest_structure(manifest)
    _validate_source_anchor(repo, manifest.get("fonte") or {})

    base = manifest_path.parent
    sample_declaration = manifest.get("amostra") or {}
    sample = _relative_path(base, sample_declaration.get("arquivo"), "arquivo da amostra")
    _validate_sample(sample, sample_declaration)

    golden_declaration = manifest.get("gabarito") or {}
    if not isinstance(golden_declaration, dict) or set(golden_declaration) != {"arquivo", "sha256"}:
        raise ExternalValidationError("declaração do gabarito possui estrutura inválida")
    golden_path = _relative_path(base, golden_declaration.get("arquivo"), "arquivo do gabarito")
    if _sha256(golden_path) != golden_declaration.get("sha256"):
        raise ExternalValidationError("hash do gabarito externo diverge")
    golden = _json(golden_path, "gabarito da validação externa")
    _validate_golden(golden, str(manifest.get("validacao_id") or ""))

    if source_path is not None:
        _validate_full_source(
            Path(source_path),
            manifest["fonte"],
            sample,
            sample_declaration["linhas_fonte"],
        )

    analyzer_path = repo / "ferramentas/analisar-rollout.py"
    analyzer = _analyzer(analyzer_path)
    report = analyzer.analyze(sample)
    ledger = report.get("operation_outcomes") or {}
    actual = {
        (item.get("parent_call_id"), item.get("operation_index")): item
        for item in ledger.get("operations") or []
    }
    expected_identities = {
        (item["parent_call_id"], item["operation_index"])
        for item in golden["expectativas"]
    }
    checks: list[dict[str, Any]] = []
    for expected_item in golden["expectativas"]:
        identity = (expected_item["parent_call_id"], expected_item["operation_index"])
        observed_item = actual.get(identity)
        observed = None
        if observed_item is not None:
            evidence = observed_item.get("evidence") or {}
            observed = {
                "state": observed_item.get("state"),
                "evidence": {
                    "source": evidence.get("source"),
                    "marker": evidence.get("marker"),
                },
            }
        expected_value = {
            "state": expected_item["state"],
            "evidence": expected_item["evidence"],
        }
        checks.append(
            {
                "parent_call_id": identity[0],
                "operation_index": identity[1],
                "ok": observed == expected_value,
                "esperado": expected_value,
                "observado": observed,
            }
        )
    unexpected = sorted(
        f"{call_id}/{index}"
        for call_id, index in set(actual) - expected_identities
    )
    summary_ok = ledger.get("summary") == golden.get("resumo")
    failures = [item for item in checks if not item["ok"]]
    status = "aprovado" if not failures and not unexpected and summary_ok else "reprovado"
    return {
        "schema_resultado_validacao_externa": SCHEMA,
        "validacao_id": manifest["validacao_id"],
        "status": status,
        "ok": status == "aprovado",
        "sessao_origem": manifest["fonte"]["sessao_id"],
        "natureza": manifest["natureza"],
        "fonte_integral_verificada": source_path is not None,
        "amostra_sha256": sample_declaration["sha256"],
        "gabarito_sha256": golden_declaration["sha256"],
        "analisador_sha256": _sha256(analyzer_path),
        "operacoes_esperadas": len(golden["expectativas"]),
        "operacoes_observadas": len(actual),
        "checks_aprovados": len(checks) - len(failures),
        "checks_reprovados": len(failures),
        "resumo_ok": summary_ok,
        "operacoes_inesperadas": unexpected,
        "checks": checks,
        "limitacao": manifest["independencia"]["limitacao"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifesto", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--fonte", type=Path, help="rollout integral opcional para conferir a extração")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = validate_external_sample(
            ROOT,
            manifest_path=args.manifesto,
            source_path=args.fonte,
        )
    except (ExternalValidationError, OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({"status": "erro_validacao_externa", "mensagem": str(exc)}, ensure_ascii=False))
        return 2
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(
            f"validacao externa: {result['status']} | "
            f"operacoes={result['operacoes_observadas']} | "
            f"checks={result['checks_aprovados']}/{result['operacoes_esperadas']}"
        )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
