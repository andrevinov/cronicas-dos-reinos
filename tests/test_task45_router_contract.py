from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class Task45RouterContractTest(unittest.TestCase):
    def test_engine_docs_e_orcamento_existem(self):
        self.assertTrue((ROOT / "ferramentas/progressao_sidequests.py").is_file())
        self.assertTrue((ROOT / "docs/task45-sidequest-progression-deadlines-consequences.md").is_file())
        self.assertTrue((ROOT / "baseline/sidequest-progression-orcamento.yaml").is_file())

    def test_preflight_executa_check_task45(self):
        text = (ROOT / "ferramentas/preflight.py").read_text(encoding="utf-8")
        self.assertIn("progressao_sidequests.py", text)
        self.assertIn("progressão e consequências Task45", text)

    def test_task45_reusa_41_43_44_e_task42_no_terminal(self):
        text = (ROOT / "ferramentas/progressao_sidequests.py").read_text(encoding="utf-8")
        self.assertIn("sidequests_emergentes", text)
        self.assertIn("recompensas_sidequest", text)
        self.assertIn("integridade_adversarial", text)
        self.assertIn("canon_bridge_runtime.finish", text)
        self.assertIn("resolver_sidequest", text)


if __name__ == "__main__":
    unittest.main()
