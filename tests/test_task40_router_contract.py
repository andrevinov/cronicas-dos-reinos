from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class Task40HotRouterContractTest(unittest.TestCase):
    def test_agents_acorda_task40_so_com_ancora_causal(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("docs/task40-emergent-sidequest-opportunity-boundary.md", text)
        self.assertIn("conversa comum/incidental = nenhuma chamada", text)
        self.assertIn("âncora causal concreta", text)
        self.assertIn("oportunidade_sidequest.py planejar", text)
        self.assertIn("só autoriza pensar, nunca criar/oferecer quest", text)

    def test_documentacao_e_boundary_existem(self):
        self.assertTrue((ROOT / "docs/task40-emergent-sidequest-opportunity-boundary.md").is_file())
        self.assertTrue((ROOT / "ferramentas/oportunidade_sidequest.py").is_file())
        self.assertTrue((ROOT / "narrador/recompensas/envelope-sidequest.yaml").is_file())


if __name__ == "__main__":
    unittest.main()
