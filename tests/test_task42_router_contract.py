from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class Task42HotRouterContractTest(unittest.TestCase):
    def test_task42_vem_depois_da_autoria_task41(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        task41 = text.index("**Task 41:**")
        task42 = text.index("**Task 42:**")
        self.assertLess(task41, task42)
        self.assertIn("docs/task42-canon-bridge-rewriter.md", text)

    def test_router_preserva_agencia_e_prova_antes_de_suprimir(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        block = text[text.index("**Task 42:**"):]
        self.assertIn("canon_bridge_runtime.py", block)
        self.assertIn("nunca move Ren", block)
        self.assertIn("só suprimem realização padrão com evidência", block)
        self.assertIn("`reconciliar` libera fallback", block)
        self.assertIn("Integração automática fica para Task 46", block)

    def test_preflight_executa_check_task42(self):
        text = (ROOT / "ferramentas/preflight.py").read_text(encoding="utf-8")
        self.assertIn("canon bridge Task42", text)
        self.assertIn("ferramentas/canon_bridge_runtime.py", text)
        self.assertIn('"check"', text)


if __name__ == "__main__":
    unittest.main()
