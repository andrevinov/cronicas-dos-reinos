from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class Task44HotRouterContractTest(unittest.TestCase):
    def test_task44_congela_adversario_antes_do_lifecycle(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        task41 = text.index("**Task 41:**")
        task44 = text.index("**Task 44:**")
        self.assertLess(task41, task44)
        block = text[task44:]
        self.assertIn("docs/task44-adversarial-integrity-consequence-authority.md", text)
        self.assertIn("preparar `contrato_adversarial` junto da Task41 antes da oferta", block)
        self.assertIn("integridade_adversarial.py", block)
        self.assertIn("antes do lifecycle", block)
        self.assertIn("Capacidade/conhecimento precisam ser reais", block)
        self.assertIn("lateral mantém Protected Core", block)
        self.assertIn("vínculo Task42 pode autorizar risco canônico", block)
        self.assertIn("`obrigatoria_se_condicao` não amacia sem bloqueio causal", block)
        self.assertIn("Execução terminal: Task45", block)
        self.assertIn("integração quente: Task46", block)

    def test_preflight_executa_check_task44(self):
        text = (ROOT / "ferramentas/preflight.py").read_text(encoding="utf-8")
        self.assertIn("integridade adversarial Task44", text)
        self.assertIn("ferramentas/integridade_adversarial.py", text)
        self.assertIn('"check"', text)

    def test_engine_policy_docs_e_orcamento_existem(self):
        self.assertTrue((ROOT / "ferramentas/integridade_adversarial.py").is_file())
        self.assertTrue((ROOT / "narrador/mundo/autoridade-consequencias.yaml").is_file())
        self.assertTrue((ROOT / "docs/task44-adversarial-integrity-consequence-authority.md").is_file())
        self.assertTrue((ROOT / "baseline/adversarial-integrity-orcamento.yaml").is_file())


if __name__ == "__main__":
    unittest.main()
