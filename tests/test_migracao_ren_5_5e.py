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

    def test_task8_promove_5_5e_e_aposenta_shims(self) -> None:
        campaign = yaml.safe_load((ROOT / "campanha.yaml").read_text(encoding="utf-8"))
        ruleset = campaign["sistema"]["ruleset"]
        self.assertEqual(ruleset["atual"], "dnd_5_5e")
        self.assertTrue(ruleset["migracao"]["ativacao"]["permitida"])
        self.assertTrue(ruleset["migracao"]["ativacao"]["requisitos"]["task_8_auditoria_final"])
        self.assertEqual(self.migration["status"], "ativada")
        self.assertFalse((ROOT / "ferramentas/ficha_ren_5_5e.py").exists())
        self.assertFalse((ROOT / "personagens/jogador/resumo-de-poderes-5-5e.md").exists())

    def test_ficha_canonica_e_o_perfil_5_5e(self) -> None:
        self.assertEqual(self.sheet_raw["personagem"]["sistema"], "Dungeons & Dragons 5.5e")
        self.assertEqual(self.sheet_raw["identidade"]["subclasse"], "Guerreiro das Sombras")
        self.assertIn("focus", self.sheet_raw["recursos_de_classe"])
        self.assertNotIn("ki", self.sheet_raw["recursos_de_classe"])
        self.assertEqual(self.mechanics.resources["focus"], {"pontos_maximos": 7, "pontos_atuais": 1, "cd": 14})

    def test_numeros_centrais_e_ataques_convertidos(self) -> None:
        self.assertEqual(self.mechanics.armor_class, 17)
        self.assertEqual(self.mechanics.resources["pontos_de_vida"], {"atuais": 45, "maximos": 52, "dados_de_vida": "7d8"})
        self.assertEqual(self.sheet_raw["combate"]["deslocamento"]["total"], "55 pés")
        self.assertEqual(self.mechanics.attacks["golpe_desarmado"].damage, "1d8+4")
        self.assertEqual(self.mechanics.attacks["wakizashi"].damage, "1d8+4")
        self.assertEqual(self.mechanics.attacks["shuriken"].damage, "1d4+4")

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
        self.assertEqual(self.mechanics.passives, {"percepcao": 21, "investigacao": 20, "intuicao": 16})

    def test_decisoes_preservam_migracao_prospectiva(self) -> None:
        text = (ROOT / "regras/decisoes.md").read_text(encoding="utf-8")
        self.assertIn("DEC-0008", text)
        self.assertIn("DEC-0009", text)
        self.assertIn("Ki 1/7 é convertido em Focus 1/7", text)
        self.assertIn("nenhuma sessão, rolagem, gasto, descoberta ou consequência anterior", text)


if __name__ == "__main__":
    unittest.main()
