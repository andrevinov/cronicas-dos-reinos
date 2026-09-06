"""Contrato da saída pública de retomada, incluindo erros do subprocesso."""
from pathlib import Path
import subprocess
import sys
import unittest

import yaml
import test_memoria_cena_integracao as fixtures


class SceneMemoryCliTest(unittest.TestCase):
    def test_cli_retomada_preserva_memoria_em_ambos_formatos(self):
        fixture = fixtures.SceneMemoryIntegrationTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixtures.checkpoint.refresh_memory(fixture.repo, "cena")
        fixture.establish()
        program = Path(__file__).resolve().parents[1] / "ferramentas" / "contexto.py"
        for options in (["--json"], []):
            with self.subTest(formato=options or "yaml"):
                process = subprocess.run(
                    [sys.executable, str(program), "--repo", str(fixture.repo), *options, "retomada"],
                    capture_output=True, text=True, check=False,
                )
                diagnostics = f"program={program}\nSTDERR:\n{process.stderr}\nSTDOUT:\n{process.stdout}"
                self.assertEqual(process.returncode, 0, diagnostics)
                output = yaml.safe_load(process.stdout)
                self.assertIn("memoria_cena", output, diagnostics)
                self.assertEqual(output["memoria_cena"]["modo"], "completa")
                self.assertIn("silva_fixture", output["memoria_cena"]["itens"])
                self.assertLessEqual(len(process.stdout.encode("utf-8")), 8192)
