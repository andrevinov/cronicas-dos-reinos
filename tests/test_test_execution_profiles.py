from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ferramentas import testes

ROOT = Path(__file__).parents[1]


class TestExecutionProfilesTest(unittest.TestCase):
    def test_fast_e_curado_existente_e_contido_na_suite_full(self):
        fast = testes.fast_files(ROOT)
        full = set(testes.full_files(ROOT))

        self.assertGreaterEqual(len(fast), 10)
        self.assertEqual(len(fast), len(set(fast)))
        self.assertTrue(all(path in full for path in fast))
        self.assertTrue(all(path.name.startswith("test_") for path in fast))

    def test_dominios_documentados_resolvem_para_testes_e_aceitam_acentos(self):
        aliases = {
            "mecânica": "mecanica",
            "crônica": "cronica",
            "sessões": "sessoes",
            "sidequests": "sidequests",
            "mundo": "mundo",
            "runtime": "runtime",
        }
        full = set(testes.full_files(ROOT))

        for supplied, canonical in aliases.items():
            with self.subTest(domain=supplied):
                self.assertEqual(testes.normalize_domain(supplied), canonical)
                selected = testes.domain_files([supplied], ROOT)
                self.assertTrue(selected)
                self.assertTrue(all(path in full for path in selected))

    def test_multiplos_dominios_sao_unidos_sem_duplicacao(self):
        cronica = set(testes.domain_files(["cronica"], ROOT))
        runtime = set(testes.domain_files(["runtime"], ROOT))
        combined = testes.domain_files(["cronica", "runtime"], ROOT)

        self.assertEqual(set(combined), cronica | runtime)
        self.assertEqual(len(combined), len(set(combined)))

    def test_dominio_inexistente_falha_explicitamente(self):
        with self.assertRaises(testes.ProfileError):
            testes.normalize_domain("qualquer-coisa")

    def test_loader_de_perfil_executa_unittest_sem_plugin_externo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            tests_dir = repo / "tests"
            tests_dir.mkdir()
            sample = tests_dir / "test_sample.py"
            sample.write_text(
                "import unittest\n\n"
                "class SampleTest(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        self.assertEqual(2 + 2, 4)\n",
                encoding="utf-8",
            )

            suite = testes.load_selected_suite([sample], repo)
            self.assertEqual(suite.countTestCases(), 1)

    def test_full_e_exatamente_o_discovery_canonico(self):
        command = testes.full_command()
        self.assertEqual(
            command,
            (sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"),
        )

        completed = subprocess.CompletedProcess(command, 0)
        with patch("ferramentas.testes.subprocess.run", return_value=completed) as run:
            self.assertEqual(testes.run_full(ROOT), 0)

        run.assert_called_once_with(command, cwd=ROOT, check=False)

    def test_ci_continua_com_suite_full_obrigatoria(self):
        workflow = (ROOT / ".github/workflows/integridade.yml").read_text(encoding="utf-8")
        self.assertIn("python -m unittest discover -s tests -v", workflow)

    def test_documentacao_expoe_quatro_responsabilidades(self):
        doc = (ROOT / "docs/agente/perfis-de-testes.md").read_text(encoding="utf-8")
        for command in (
            "poetry run test-fast",
            "poetry run test-domain",
            "poetry run test-full",
            "poetry run preflight",
        ):
            self.assertIn(command, doc)
        self.assertIn("obrigatório antes do merge", doc)


if __name__ == "__main__":
    unittest.main()
