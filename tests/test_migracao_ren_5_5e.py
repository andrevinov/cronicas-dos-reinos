from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import ficha_ren


class Ren55MigrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sheet_raw = yaml.safe_load((ROOT / "personagens/jogador/ficha.yaml").read_text(encoding="utf-8"))
        cls.migration = yaml.safe_load((ROOT / "personagens/jogador/migracao-5-5e.yaml").read_text(encoding="utf-8"))
        cls.mechanics = ficha_ren.load(ROOT / "personagens/jogador/ficha.yaml")
        cls.activation = yaml.safe_load(
            (ROOT / "tests/fixtures/ren-5-5e-activation-snapshot.yaml").read_text(encoding="utf-8")
        )

    def test_task8_promove_5_5e_e_aposenta_shims(self) -> None:
        campaign = yaml.safe_load((ROOT / "campanha.yaml").read_text(encoding="utf-8"))
        ruleset = campaign["sistema"]["ruleset"]
        self.assertEqual(ruleset["atual"], "dnd_5_5e")
        self.assertTrue(ruleset["migracao"]["ativacao"]["permitida"])
        self.assertTrue(ruleset["migracao"]["ativacao"]["requisitos"]["task_8_auditoria_final"])
        self.assertEqual(self.migration["status"], "ativada")
        self.assertFalse((ROOT / "ferramentas/ficha_ren_5_5e.py").exists())
        self.assertFalse((ROOT / "personagens/jogador/resumo-de-poderes-5-5e.md").exists())

    def test_ficha_canonica_viva_permanece_5_5e_sem_congelar_recursos(self) -> None:
        self.assertEqual(self.sheet_raw["personagem"]["sistema"], "Dungeons & Dragons 5.5e")
        self.assertEqual(self.sheet_raw["identidade"]["subclasse"], "Guerreiro das Sombras")
        self.assertIn("focus", self.sheet_raw["recursos_de_classe"])
        self.assertNotIn("ki", self.sheet_raw["recursos_de_classe"])

        focus = self.mechanics.resources["focus"]
        hp = self.mechanics.resources["pontos_de_vida"]
        self.assertGreaterEqual(focus["pontos_atuais"], 0)
        self.assertLessEqual(focus["pontos_atuais"], focus["pontos_maximos"])
        self.assertGreaterEqual(hp["atuais"], 0)
        self.assertLessEqual(hp["atuais"], hp["maximos"])

    def test_snapshot_historico_da_ativacao_preserva_conversao_exata(self) -> None:
        self.assertEqual(self.activation["schema_fixture_ren_5_5e_activation"], 1)
        source = self.activation["origem_2014"]
        target = self.activation["destino_5_5e"]
        self.assertEqual(source["nivel"], target["nivel"])
        self.assertEqual(source["nivel"], self.migration["classe_alvo"]["nivel"])
        self.assertEqual(source["pontos_de_vida"], target["pontos_de_vida"])
        self.assertEqual(source["ki"]["atuais"], target["focus"]["atuais"])
        self.assertEqual(source["ki"]["maximos"], target["focus"]["maximos"])
        self.assertEqual(target["focus"]["maximos"], self.migration["classe_alvo"]["pontos_focus_maximos"])
        self.assertEqual(target["focus"]["cd"], self.migration["classe_alvo"]["cd_focus"])
        self.assertEqual(target["classe_de_armadura"], 17)
        self.assertEqual(target["deslocamento_total"], "55 pés")
        self.assertEqual(target["ataques"]["golpe_desarmado"]["dano"], "1d8+4")
        self.assertEqual(target["ataques"]["wakizashi"]["dano"], "1d8+4")
        self.assertEqual(target["ataques"]["shuriken"]["dano"], "1d4+4")
        self.assertEqual(target["passivos"], {"percepcao": 21, "investigacao": 20, "intuicao": 16})

        legacy = self.activation["efeito_legado_no_instante_da_ativacao"]
        self.assertEqual(legacy["origem_ruleset"], "dnd_5e_2014")
        self.assertTrue(legacy["preservado_por_migracao"])
        self.assertFalse(legacy["recastavel"])
        self.assertEqual(legacy["termino"], "23:30 de 19 Eleasis, 1372 DR")

    def test_shadow_arts_5_5e_e_beneficios_canonizados(self) -> None:
        resources = self.sheet_raw["recursos_de_classe"]
        shadow = resources["artes_sombrias"]
        self.assertEqual(shadow["escuridao"]["custo_focus"], 1)
        self.assertTrue(shadow["escuridao"]["ve_dentro_da_propria_escuridao"])
        self.assertNotIn("magias_com_ki", shadow)
        self.assertIn("Passos sem Pegadas", shadow["removidas_na_5_5e"])
        self.assertIn("Silêncio", shadow["removidas_na_5_5e"])
        self.assertIn("Actor", self.sheet_raw["criacao"]["talentos_bonus_retroativos"])
        self.assertIn("Observant", self.sheet_raw["criacao"]["talentos_bonus_retroativos"])
        senses = self.sheet_raw["sentidos"]
        self.assertEqual(
            self.mechanics.passives,
            {
                "percepcao": senses["percepcao_passiva"],
                "investigacao": senses["investigacao_passiva"],
                "intuicao": senses["intuicao_passiva"],
            },
        )

    def test_decisoes_preservam_migracao_prospectiva(self) -> None:
        text = (ROOT / "regras/decisoes.md").read_text(encoding="utf-8")
        self.assertIn("DEC-0008", text)
        self.assertIn("DEC-0009", text)
        self.assertIn("Ki 1/7 é convertido em Focus 1/7", text)
        self.assertIn("nenhuma sessão, rolagem, gasto, descoberta ou consequência anterior", text)


if __name__ == "__main__":
    unittest.main()
