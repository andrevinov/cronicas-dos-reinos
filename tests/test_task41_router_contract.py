from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class Task41HotRouterContractTest(unittest.TestCase):
    def test_agents_exige_oferta_real_antes_de_materializar(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("docs/task41-emergent-sidequest-authoring-registry-v2.md", text)
        self.assertIn("sidequests_emergentes.py preparar", text)
        self.assertIn("narrar oferta → `cronica concluir` → materializar", text)
        self.assertIn("sem oferta, não materializar", text)
        self.assertIn("Nasce `oferecida` em `oportunidades.py`", text)
        self.assertIn("rewards/stakes e cânone ficam só declarados", text)

    def test_documentacao_engine_e_orcamento_existem(self):
        self.assertTrue((ROOT / "docs/task41-emergent-sidequest-authoring-registry-v2.md").is_file())
        self.assertTrue((ROOT / "ferramentas/sidequests_emergentes.py").is_file())
        self.assertTrue((ROOT / "baseline/emergent-sidequest-authoring-v2-orcamento.yaml").is_file())

    def test_task40_continua_sendo_a_porta_anterior(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        task40 = text.index("**Task 40:**")
        task41 = text.index("**Task 41:**")
        self.assertLess(task40, task41)
        self.assertIn("conversa comum/incidental = nenhuma chamada", text[task40:task41])
        self.assertIn("âncora causal concreta", text[task40:task41])
        self.assertIn("só autoriza pensar, nunca criar/oferecer quest", text[task40:task41])


if __name__ == "__main__":
    unittest.main()
