#!/usr/bin/env python3
"""Inventário e telemetria somente leitura da suíte de testes.

O modo padrão faz análise estática. ``--medir`` executa a suíte padrão do
unittest uma única vez para coletar duração por teste e por arquivo.
Nenhum relatório é persistido pelo script: a saída vai apenas para stdout.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import os
import re
import sys
import time
import unittest
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TESTS_DIR = ROOT / "tests"

DISCOVERY_PATTERN = "test*.py"
LIVE_PREFIXES = (
    "estado/",
    "runtime/",
)
LIVE_EXACT = {
    "personagens/jogador/ficha.yaml",
    "sessoes/index.yaml",
}
TEMP_MARKERS = {
    "TemporaryDirectory",
    "NamedTemporaryFile",
    "mkdtemp",
    "tempfile",
}
CATEGORY_ORDER = (
    "unitario",
    "integracao",
    "contrato",
    "snapshot_historico",
    "estado_vivo",
    "regressao",
    "smoke",
    "performance",
    "migracao",
    "task_historica",
)
TASK_RE = re.compile(r"(?:^|[_\W])task[_-]?\d+", re.IGNORECASE)


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _is_literal(node: ast.AST) -> bool:
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_literal(item) for item in node.elts)
    if isinstance(node, ast.Dict):
        return all(
            key is None or _is_literal(key)
            for key in node.keys
        ) and all(_is_literal(value) for value in node.values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _is_literal(node.operand)
    return False


def _assertion_has_literal_equality(node: ast.AST) -> bool:
    if isinstance(node, ast.Assert) and isinstance(node.test, ast.Compare):
        values = [node.test.left, *node.test.comparators]
        if any(isinstance(op, (ast.Eq, ast.NotEq)) for op in node.test.ops):
            return any(_is_literal(value) for value in values)
        return False

    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return False
    if node.func.attr not in {
        "assertEqual",
        "assertNotEqual",
        "assertDictEqual",
        "assertListEqual",
        "assertTupleEqual",
    }:
        return False
    return any(_is_literal(arg) for arg in node.args[:2])


class _StaticVisitor(ast.NodeVisitor):
    """Extrai sinais sem executar o arquivo analisado."""

    def __init__(self) -> None:
        self.bindings: dict[str, str] = {}
        self.names: set[str] = set()
        self.imports: set[str] = set()
        self.test_nodes: list[tuple[str, ast.AST]] = []
        self.literal_assert_lines: list[int] = []
        self.read_paths: set[str] = set()
        self.root_references = 0

    def visit_Name(self, node: ast.Name) -> None:
        self.names.add(node.id)
        if node.id in {"ROOT", "REPO", "REPO_ROOT", "ROOT_DIR"}:
            self.root_references += 1
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        if node.module:
            self.imports.add(node.module)
        for alias in node.names:
            self.names.add(alias.asname or alias.name)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        resolved = self._resolve_path(node.value)
        if resolved is not None:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.bindings[target.id] = resolved
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name) and node.value is not None:
            resolved = self._resolve_path(node.value)
            if resolved is not None:
                self.bindings[node.target.id] = resolved
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name.startswith("test"):
            self.test_nodes.append((node.name, node))
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node.name.startswith("test"):
            self.test_nodes.append((node.name, node))
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        if _assertion_has_literal_equality(node):
            self.literal_assert_lines.append(node.lineno)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if _assertion_has_literal_equality(node):
            self.literal_assert_lines.append(node.lineno)

        read_path: str | None = None
        if isinstance(node.func, ast.Name) and node.func.id == "open" and node.args:
            read_path = self._resolve_path(node.args[0])
        elif isinstance(node.func, ast.Attribute):
            if node.func.attr in {"read_text", "read_bytes", "open"}:
                read_path = self._resolve_path(node.func.value)

        if read_path:
            self.read_paths.add(_normalize_candidate_path(read_path))
        self.generic_visit(node)

    def _resolve_path(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value

        if isinstance(node, ast.Name):
            if node.id in self.bindings:
                return self.bindings[node.id]
            if node.id in {"ROOT", "REPO", "REPO_ROOT", "ROOT_DIR"}:
                return "<ROOT>"
            return None

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "Path" and node.args:
                return self._resolve_path(node.args[0])
            return None

        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            left = self._resolve_path(node.left)
            right = self._resolve_path(node.right)
            if left is not None and right is not None:
                return f"{left.rstrip('/')}/{right.lstrip('/')}"

        return None


def _normalize_candidate_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    if normalized.startswith("<ROOT>/"):
        normalized = normalized[len("<ROOT>/") :]
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _is_live_path(path: str) -> bool:
    normalized = _normalize_candidate_path(path)
    return normalized in LIVE_EXACT or normalized.startswith(LIVE_PREFIXES)


def _test_fingerprint(node: ast.AST) -> str:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        module = ast.Module(body=node.body, type_ignores=[])
    else:
        module = ast.Module(body=[node], type_ignores=[])
    payload = ast.dump(module, include_attributes=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _classify(
    relpath: str,
    source: str,
    visitor: _StaticVisitor,
    live_reads: list[str],
    uses_isolation: bool,
) -> list[str]:
    haystack = f"{relpath}\n{source}".lower()
    categories: set[str] = set()

    if live_reads:
        categories.add("estado_vivo")
    if "contrato" in haystack or "contract" in haystack:
        categories.add("contrato")
    if any(token in haystack for token in ("snapshot", "historico", "histórico", "baseline_historica")):
        categories.add("snapshot_historico")
    if any(token in haystack for token in ("regressao", "regressão", "regression")):
        categories.add("regressao")
    if Path(relpath).name.startswith("smoke_") or "smoke" in haystack:
        categories.add("smoke")
    if any(token in haystack for token in ("budget", "orcamento", "orçamento", "performance", "benchmark", "latencia", "latência")):
        categories.add("performance")
    if any(token in haystack for token in ("migracao", "migração", "migration", "migrar")):
        categories.add("migracao")
    if TASK_RE.search(haystack):
        categories.add("task_historica")

    uses_subprocess = any(name.startswith("subprocess") for name in visitor.imports)
    uses_real_repo = visitor.root_references > 0 or any(
        path.startswith(("<ROOT>/", "estado/", "runtime/", "personagens/", "sessoes/"))
        for path in visitor.read_paths
    )
    if uses_subprocess or uses_real_repo or "integration" in haystack or "integracao" in haystack:
        categories.add("integracao")

    if not (uses_subprocess or uses_real_repo or live_reads) and (
        uses_isolation or not categories.intersection({"integracao", "estado_vivo"})
    ):
        categories.add("unitario")

    return [category for category in CATEGORY_ORDER if category in categories]


def _scan_file(path: Path, root: Path) -> dict[str, Any]:
    relpath = _relative(path, root)
    source = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=relpath)
    except SyntaxError as exc:
        return {
            "arquivo": relpath,
            "discovery_unittest": path.name.startswith("test") and path.suffix == ".py",
            "erro_ast": f"{exc.msg} (linha {exc.lineno})",
            "testes_declarados": 0,
            "classificacoes": [],
            "usa_repo_real": False,
            "usa_isolamento": False,
            "leituras_estado_vivo": [],
            "assertions_literais": [],
            "candidatos": [],
        }

    visitor = _StaticVisitor()
    visitor.visit(tree)

    names_and_imports = visitor.names | visitor.imports
    uses_isolation = (
        bool(TEMP_MARKERS & names_and_imports)
        or "tests/fixtures" in source.replace("\\", "/")
        or "/fixtures/" in source.replace("\\", "/")
    )
    live_reads = sorted(path for path in visitor.read_paths if _is_live_path(path))
    uses_real_repo = visitor.root_references > 0 or bool(live_reads)
    categories = _classify(relpath, source, visitor, live_reads, uses_isolation)

    candidates: list[str] = []
    if live_reads and visitor.literal_assert_lines:
        candidates.append("congelamento_suspeito")
    elif visitor.literal_assert_lines and (
        uses_isolation or any(cat in categories for cat in ("snapshot_historico", "migracao"))
    ):
        candidates.append("congelamento_legitimo")
    if "task_historica" in categories:
        candidates.append("teste_transitorio")

    fingerprints = [
        {
            "teste": name,
            "fingerprint": _test_fingerprint(node),
            "linha": getattr(node, "lineno", None),
        }
        for name, node in visitor.test_nodes
    ]

    return {
        "arquivo": relpath,
        "discovery_unittest": path.name.startswith("test") and path.suffix == ".py",
        "testes_declarados": len(visitor.test_nodes),
        "classificacoes": categories,
        "usa_repo_real": uses_real_repo,
        "usa_isolamento": uses_isolation,
        "leituras_estado_vivo": live_reads,
        "assertions_literais": sorted(set(visitor.literal_assert_lines)),
        "candidatos": candidates,
        "_fingerprints": fingerprints,
    }


def inventory(tests_dir: Path = DEFAULT_TESTS_DIR, root: Path = ROOT) -> dict[str, Any]:
    """Retorna inventário estático determinístico, sem escrever no repositório."""
    test_files = sorted(path for path in tests_dir.rglob("*.py") if "__pycache__" not in path.parts)
    files = [_scan_file(path, root) for path in test_files]

    fingerprint_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in files:
        for fingerprint in item.pop("_fingerprints", []):
            fingerprint_groups[fingerprint["fingerprint"]].append(
                {
                    "arquivo": item["arquivo"],
                    "teste": fingerprint["teste"],
                    "linha": fingerprint["linha"],
                }
            )

    duplicates = [
        sorted(group, key=lambda entry: (entry["arquivo"], entry["teste"], entry["linha"] or 0))
        for group in fingerprint_groups.values()
        if len(group) > 1
    ]
    duplicates.sort(key=lambda group: [(item["arquivo"], item["teste"]) for item in group])
    duplicate_files = {entry["arquivo"] for group in duplicates for entry in group}
    for item in files:
        if item["arquivo"] in duplicate_files:
            item["candidatos"].append("possivel_redundancia")
        item["candidatos"] = sorted(set(item["candidatos"]))

    category_counts = Counter(
        category
        for item in files
        for category in item["classificacoes"]
    )

    dependencies = {
        "repo_real": sorted(item["arquivo"] for item in files if item["usa_repo_real"]),
        "temporarios_ou_fixtures_isoladas": sorted(
            item["arquivo"] for item in files if item["usa_isolamento"]
        ),
        "estado_vivo_direto": [
            {
                "arquivo": item["arquivo"],
                "alvos": item["leituras_estado_vivo"],
            }
            for item in files
            if item["leituras_estado_vivo"]
        ],
    }

    candidate_names = (
        "congelamento_legitimo",
        "congelamento_suspeito",
        "possivel_redundancia",
        "teste_transitorio",
    )
    candidates = {
        name: sorted(item["arquivo"] for item in files if name in item["candidatos"])
        for name in candidate_names
    }

    return {
        "schema_version": 1,
        "modo": "estatico",
        "fonte": {
            "diretorio": _relative(tests_dir, root),
            "padrao_unittest": DISCOVERY_PATTERN,
            "observacao": "Arquivos auxiliares e smoke fora do padrão também entram no inventário estático.",
        },
        "totais": {
            "arquivos_python": len(files),
            "arquivos_descobertos_unittest": sum(item["discovery_unittest"] for item in files),
            "arquivos_auxiliares": sum(not item["discovery_unittest"] for item in files),
            "testes_declarados_ast": sum(item["testes_declarados"] for item in files),
            "testes_declarados_em_discovery": sum(
                item["testes_declarados"] for item in files if item["discovery_unittest"]
            ),
            "erros_ast": sum("erro_ast" in item for item in files),
        },
        "classificacoes": {
            category: category_counts.get(category, 0)
            for category in CATEGORY_ORDER
        },
        "dependencias": dependencies,
        "candidatos": candidates,
        "duplicidades_exatas_de_corpo": duplicates,
        "arquivos": files,
        "nota": (
            "Classificações e candidatos são heurísticos: servem para triagem humana, "
            "não autorizam remoção nem alteração automática de testes."
        ),
    }


class _TimingResult(unittest.TextTestResult):
    def __init__(self, stream: Any, descriptions: bool, verbosity: int) -> None:
        super().__init__(stream, descriptions, verbosity)
        self._starts: dict[str, float] = {}
        self.timings: list[dict[str, Any]] = []
        self.status_by_id: dict[str, str] = {}

    def startTest(self, test: unittest.case.TestCase) -> None:
        test_id = test.id()
        self._starts[test_id] = time.perf_counter()
        self.status_by_id[test_id] = "ok"
        super().startTest(test)

    def addFailure(self, test: unittest.case.TestCase, err: Any) -> None:
        self.status_by_id[test.id()] = "failure"
        super().addFailure(test, err)

    def addError(self, test: unittest.case.TestCase, err: Any) -> None:
        self.status_by_id[test.id()] = "error"
        super().addError(test, err)

    def addSkip(self, test: unittest.case.TestCase, reason: str) -> None:
        self.status_by_id[test.id()] = "skip"
        super().addSkip(test, reason)

    def stopTest(self, test: unittest.case.TestCase) -> None:
        test_id = test.id()
        started = self._starts.pop(test_id, time.perf_counter())
        elapsed = time.perf_counter() - started
        module_name = test.__class__.__module__
        module = sys.modules.get(module_name)
        module_file = getattr(module, "__file__", None)
        arquivo = _relative(Path(module_file), ROOT) if module_file else None
        self.timings.append(
            {
                "teste": test_id,
                "arquivo": arquivo,
                "duracao_s": round(elapsed, 6),
                "status": self.status_by_id.get(test_id, "ok"),
            }
        )
        super().stopTest(test)


def measure_suite(tests_dir: Path = DEFAULT_TESTS_DIR, top: int = 20) -> tuple[dict[str, Any], bool]:
    """Executa a mesma discovery padrão e mede cada caso individualmente."""
    old_cwd = Path.cwd()
    try:
        os.chdir(ROOT)
        suite = unittest.defaultTestLoader.discover(str(tests_dir), pattern=DISCOVERY_PATTERN)
        stream = io.StringIO()
        runner = unittest.TextTestRunner(
            stream=stream,
            verbosity=0,
            resultclass=_TimingResult,
        )
        started = time.perf_counter()
        result = runner.run(suite)
        total = time.perf_counter() - started
    finally:
        os.chdir(old_cwd)

    assert isinstance(result, _TimingResult)
    timings = sorted(
        result.timings,
        key=lambda item: (-item["duracao_s"], item["teste"]),
    )
    by_file: dict[str, dict[str, Any]] = {}
    for item in result.timings:
        arquivo = item["arquivo"] or "<desconhecido>"
        bucket = by_file.setdefault(
            arquivo,
            {"arquivo": arquivo, "duracao_s": 0.0, "testes": 0},
        )
        bucket["duracao_s"] += item["duracao_s"]
        bucket["testes"] += 1

    file_timings = []
    for bucket in by_file.values():
        bucket["duracao_s"] = round(bucket["duracao_s"], 6)
        file_timings.append(bucket)
    file_timings.sort(key=lambda item: (-item["duracao_s"], item["arquivo"]))

    execution = {
        "comando_equivalente": "python -m unittest discover -s tests -v",
        "testes_executados": result.testsRun,
        "duracao_total_s": round(total, 6),
        "soma_duracoes_testes_s": round(sum(item["duracao_s"] for item in result.timings), 6),
        "falhas": len(result.failures),
        "erros": len(result.errors),
        "pulados": len(result.skipped),
        "sucesso": result.wasSuccessful(),
    }
    measurement = {
        "execucao": execution,
        "mais_lentos": {
            "arquivos": file_timings[:top],
            "testes": timings[:top],
        },
        "duracao_por_arquivo": file_timings,
        "duracao_por_teste": sorted(result.timings, key=lambda item: item["teste"]),
    }
    return measurement, result.wasSuccessful()


def _add_measurement(inventory_report: dict[str, Any], measurement: dict[str, Any], top: int) -> dict[str, Any]:
    report = inventory_report
    report["modo"] = "medido"
    report["execucao"] = measurement["execucao"]
    report["mais_lentos"] = measurement["mais_lentos"]
    report["duracao_por_arquivo"] = measurement["duracao_por_arquivo"]
    report["duracao_por_teste"] = measurement["duracao_por_teste"]
    report["totais"]["testes_executados"] = measurement["execucao"]["testes_executados"]

    expensive = {
        item["arquivo"]
        for item in measurement["mais_lentos"]["arquivos"][:top]
        if item["arquivo"] != "<desconhecido>"
    }
    report["candidatos"]["teste_caro"] = sorted(expensive)
    for item in report["arquivos"]:
        if item["arquivo"] in expensive:
            item["candidatos"] = sorted(set([*item["candidatos"], "teste_caro"]))
    return report


def _human_summary(report: dict[str, Any], top: int) -> str:
    totals = report["totais"]
    lines = [
        "AUDITORIA DA SUÍTE DE TESTES",
        f"modo: {report['modo']}",
        (
            "arquivos Python: "
            f"{totals['arquivos_python']} "
            f"({totals['arquivos_descobertos_unittest']} no discovery; "
            f"{totals['arquivos_auxiliares']} auxiliares)"
        ),
        f"testes declarados (AST): {totals['testes_declarados_ast']}",
        f"arquivos usando repositório real: {len(report['dependencias']['repo_real'])}",
        (
            "arquivos usando TemporaryDirectory/fixtures: "
            f"{len(report['dependencias']['temporarios_ou_fixtures_isoladas'])}"
        ),
        (
            "arquivos com leitura direta de estado vivo: "
            f"{len(report['dependencias']['estado_vivo_direto'])}"
        ),
        (
            "candidatos a congelamento suspeito: "
            f"{len(report['candidatos']['congelamento_suspeito'])}"
        ),
        (
            "arquivos históricos de Task: "
            f"{report['classificacoes']['task_historica']}"
        ),
        (
            "grupos de corpos de teste exatamente duplicados: "
            f"{len(report['duplicidades_exatas_de_corpo'])}"
        ),
    ]

    if report["modo"] == "medido":
        execution = report["execucao"]
        lines.extend(
            [
                "",
                (
                    f"execução: {execution['testes_executados']} testes em "
                    f"{execution['duracao_total_s']:.3f}s "
                    f"({'OK' if execution['sucesso'] else 'FALHA'})"
                ),
                "",
                f"{min(top, len(report['mais_lentos']['arquivos']))} arquivos mais lentos:",
            ]
        )
        for item in report["mais_lentos"]["arquivos"][:top]:
            lines.append(
                f"  {item['duracao_s']:8.3f}s  {item['testes']:4d}  {item['arquivo']}"
            )
        lines.extend(["", f"{min(top, len(report['mais_lentos']['testes']))} testes mais lentos:"])
        for item in report["mais_lentos"]["testes"][:top]:
            lines.append(f"  {item['duracao_s']:8.3f}s  {item['teste']}")

    lines.extend(
        [
            "",
            "Triagem apenas: candidatos heurísticos não autorizam exclusão ou refatoração automática.",
        ]
    )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Inventaria a suíte e, opcionalmente, mede duração por teste/arquivo."
    )
    parser.add_argument(
        "--medir",
        action="store_true",
        help="executa a suíte unittest completa uma vez e adiciona telemetria de duração",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emite o relatório completo como JSON determinístico",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="quantidade de arquivos/testes lentos destacados (padrão: 20)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.top < 1:
        raise SystemExit("--top deve ser >= 1")

    report = inventory()
    success = True
    if args.medir:
        measurement, success = measure_suite(top=args.top)
        report = _add_measurement(report, measurement, args.top)
    else:
        report["candidatos"]["teste_caro"] = []

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(_human_summary(report, args.top))
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
