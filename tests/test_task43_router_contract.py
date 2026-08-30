from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class Task43HotRouterContractTest(unittest.TestCase):
    def test_task43_vem_depois_da_materializacao_task41_e_antes_do_lifecycle(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        task41 = text.index("**Task 41:**")
        task43 = text.index("**Task 43:**")
        self.assertLess(task41, task43)
        block = text[task43:]
        self.assertIn("docs/task43-quest-rewards-discoveries-losses.md", text)
        self.assertIn("registrar `contrato_recompensa`", block)
        self.assertIn("antes de resposta/lifecycle", block)
        self.assertIn("Descoberta ≠ obtenção", block)
        self.assertIn("writer transacional", block)
        self.assertIn("perda exige contrato + evidência causal", block)
        self.assertIn("Integração automática fica para Task 46", block)

    def test_preflight_executa_check_task43(self):
        text = (ROOT / "ferramentas/preflight.py").read_text(encoding="utf-8")
        self.assertIn("recompensas de sidequest Task43", text)
        self.assertIn("ferramentas/recompensas_sidequest.py", text)
        self.assertIn('"check"', text)

    def test_engine_docs_e_orcamento_existem(self):
        self.assertTrue((ROOT / "ferramentas/recompensas_sidequest.py").is_file())
        self.assertTrue((ROOT / "docs/task43-quest-rewards-discoveries-losses.md").is_file())
        self.assertTrue((ROOT / "baseline/quest-rewards-orcamento.yaml").is_file())


if __name__ == "__main__":
    unittest.main()
