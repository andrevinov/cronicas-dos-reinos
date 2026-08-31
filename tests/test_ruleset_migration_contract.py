from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


class RulesetMigrationContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.campaign = yaml.safe_load((ROOT / "campanha.yaml").read_text(encoding="utf-8"))
        cls.ruleset = cls.campaign["sistema"]["ruleset"]
        cls.sources = (ROOT / "regras/fontes.md").read_text(encoding="utf-8")
        cls.house_rules = (ROOT / "regras/regras-da-casa.md").read_text(encoding="utf-8")
        cls.agent_rules = (ROOT / "docs/agente/regras-e-rolagens.md").read_text(encoding="utf-8")

    def test_schema_declara_ruleset_atual_alvo_e_migracao(self) -> None:
        self.assertEqual(self.ruleset["atual"], "dnd_5e_2014")
        self.assertEqual(self.ruleset["alvo"], "dnd_5_5e")
        migration = self.ruleset["migracao"]
        self.assertEqual(migration["status"], "em_andamento")
        self.assertEqual(migration["ativacao"]["gate"], "task_8_auditoria_final")
        self.assertTrue(migration["ativacao"]["requisitos"]["task_1_contrato"])
        self.assertTrue(migration["ativacao"]["requisitos"]["task_7_gate_adnd"])

    def test_hierarquia_mecanica_e_estavel(self) -> None:
        self.assertEqual(
            self.ruleset["hierarquia_mecanica"],
            [
                "decisoes_campanha",
                "regras_da_casa",
                "ruleset_atual",
                "compatibilidade_aprovada",
                "fontes_adaptadas",
            ],
        )

    def test_5_5e_nao_pode_ser_ativado_com_migracao_incompleta(self) -> None:
        migration = self.ruleset["migracao"]
        activation = migration["ativacao"]
        requirements = activation["requisitos"]

        if migration["status"] != "concluida":
            self.assertEqual(self.ruleset["atual"], "dnd_5e_2014")
            self.assertFalse(activation["permitida"])

        if self.ruleset["atual"] == self.ruleset["alvo"]:
            self.assertEqual(migration["status"], "concluida")
            self.assertTrue(activation["permitida"])
            self.assertTrue(all(requirements.values()))

    def test_compatibilidade_nao_mistura_rulesets_implicitamente(self) -> None:
        compatibility = self.ruleset["compatibilidade"]
        self.assertEqual(
            compatibility["uso_5_5e_antes_da_ativacao"],
            "somente_migracao",
        )
        self.assertEqual(
            compatibility["fallback_5e_2014_apos_ativacao"],
            "somente_sem_equivalente_5_5e_e_com_aprovacao_explicita",
        )
        self.assertEqual(
            compatibility["material_adnd"],
            "adaptar_para_ruleset_atual",
        )
        gate = compatibility["gate_adnd"]
        self.assertEqual(gate["narrativa"], "livre")
        self.assertEqual(gate["mecanica_literal_runtime"], "proibida")
        self.assertEqual(gate["alvo_preferencial_migracao"], "dnd_5_5e")
        self.assertEqual(gate["fallback_2014"], "exige_declaracao_motivo_e_decisao")

    def test_sessoes_e_decisoes_antigas_sao_preservadas(self) -> None:
        preservation = self.ruleset["preservacao_historica"]
        self.assertEqual(preservation["sessoes_concluidas"], "preservar")
        self.assertEqual(
            preservation["decisoes_existentes"],
            "preservar_ate_substituicao_explicita_prospectiva",
        )
        self.assertFalse(preservation["reescrita_retroativa"])
        self.assertIn("não reescreve sessões concluídas", self.sources)
        self.assertIn("não reescrever sessões concluídas", self.house_rules)
        self.assertIn("não reescrever sessões concluídas", self.agent_rules)


if __name__ == "__main__":
    unittest.main()
