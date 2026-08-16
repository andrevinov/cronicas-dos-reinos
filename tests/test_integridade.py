from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "ferramentas" / "verificar-integridade.py"
spec = importlib.util.spec_from_file_location("verificar_integridade", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class IntegridadeHelpersTest(unittest.TestCase):
    def test_get_path(self):
        self.assertEqual(mod.get_path({"a": {"b": 3}}, "a.b"), 3)
        with self.assertRaises(KeyError):
            mod.get_path({"a": {}}, "a.c")

    def test_duplicate_yaml_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.yaml"
            path.write_text("a: 1\na: 2\n", encoding="utf-8")
            with self.assertRaises(Exception):
                mod.load_yaml(path)


class AgentRouterTest(unittest.TestCase):
    def test_real_router_has_full_legacy_coverage(self):
        coverage = mod.load_yaml(ROOT / mod.AGENT_COVERAGE)
        errors = mod.validate_agent_router(ROOT, {mod.AGENT_COVERAGE: coverage})
        self.assertEqual(errors, [])

    def test_missing_legacy_section_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            marker_text = (
                "Nunca leia por precaução\n"
                "Se for suficiente, pare\n"
                "docs/agente/acesso-e-operacoes.md\n"
                "docs/agente/cobertura-agents-v1.yaml\n"
            )
            (repo / "AGENTS.md").write_text(marker_text, encoding="utf-8")
            (repo / "doc.md").write_text("ok\n", encoding="utf-8")
            sections = {number: "x" for number in range(1, 58)}
            coverage = {
                "origem": {"sha_blob": mod.LEGACY_AGENT_SHA, "secoes": 58},
                "documentos": {"x": "doc.md"},
                "secoes": sections,
            }
            errors = mod.validate_agent_router(repo, {mod.AGENT_COVERAGE: coverage})
            self.assertTrue(any("cobertura de AGENTS incompleta" in error for error in errors))

    def test_oversized_router_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            text = (
                "Nunca leia por precaução\n"
                "Se for suficiente, pare\n"
                "docs/agente/acesso-e-operacoes.md\n"
                "docs/agente/cobertura-agents-v1.yaml\n"
                + ("x" * (mod.AGENTS_MAX_BYTES + 1))
            )
            (repo / "AGENTS.md").write_text(text, encoding="utf-8")
            (repo / "doc.md").write_text("ok\n", encoding="utf-8")
            coverage = {
                "origem": {"sha_blob": mod.LEGACY_AGENT_SHA, "secoes": 58},
                "documentos": {"x": "doc.md"},
                "secoes": {number: "x" for number in range(1, 59)},
            }
            errors = mod.validate_agent_router(repo, {mod.AGENT_COVERAGE: coverage})
            self.assertTrue(any("excede o limite do roteador" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
