from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


class Task46RouterContractTest(unittest.TestCase):
    def test_agents_declara_integracao_na_mesma_dupla(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("docs/task46-emergent-sidequests-integration-budget-regression.md", text)
        self.assertIn("docs/task47-explicit-opportunity-decision-gate.md", text)
        block = text[text.index("**Task 46:**"):]
        self.assertIn("cronica preparar ... --oportunidade-sidequest", block)
        self.assertIn("mesmo `cronica concluir`", block)
        self.assertIn("Decisão negativa explícita = zero Task40–45", block)
        self.assertIn("--sem-oportunidade-sidequest", block)
        self.assertIn("Task32/33 = legado frio, nunca origem/hot path", block)
        self.assertIn("2 chamadas de orquestração por turno", text)

    def test_indice_real_aponta_task40_e_task33_fica_frio(self):
        index = yaml.safe_load(
            (ROOT / "narrador/oportunidades/index.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(index["nova_origem_sidequests"], "emergente_causal_task40")
        self.assertEqual(index["regras"]["fonte_nova_sidequest"], "emergente_causal_task40")
        self.assertFalse(index["regras"]["task32_task33_origem_operacional"])
        self.assertEqual(index["sidequests_canonicas"]["estatuto"], "legado_frio_task46")
        self.assertFalse(index["sidequests_canonicas"]["origem_operacional"])

    def test_engine_docs_baseline_e_preflight_existem(self):
        for rel in (
            "ferramentas/sidequests_integracao.py",
            "ferramentas/sidequests_integracao_runtime.py",
            "ferramentas/sidequests_integracao_check.py",
            "docs/task46-emergent-sidequests-integration-budget-regression.md",
            "baseline/emergent-sidequests-integration-orcamento.yaml",
            "docs/task47-explicit-opportunity-decision-gate.md",
            "baseline/explicit-opportunity-decision-gate-orcamento.yaml",
        ):
            self.assertTrue((ROOT / rel).is_file(), rel)
        preflight = (ROOT / "ferramentas/preflight.py").read_text(encoding="utf-8")
        self.assertIn("integração sidequests Task46", preflight)
        self.assertIn("sidequests_integracao_check.py", preflight)


if __name__ == "__main__":
    unittest.main()
