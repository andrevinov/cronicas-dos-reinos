from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import ficha_ren
import ficha_ren_5_5e


class Ren55MigrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.active_path = ROOT / "personagens/jogador/ficha.yaml"
        cls.migration_path = ROOT / "personagens/jogador/migracao-5-5e.yaml"
        cls.active_raw = yaml.safe_load(cls.active_path.read_text(encoding="utf-8"))
        cls.migration = yaml.safe_load(cls.migration_path.read_text(encoding="utf-8"))
        cls.active = ficha_ren.load(cls.active_path)
        cls.target = ficha_ren_5_5e.load(cls.active_path, cls.migration_path)

    def test_task5_nao_ativa_5_5e_antes_da_task8(self) -> None:
        campaign = yaml.safe_load((ROOT / "campanha.yaml").read_text(encoding="utf-8"))
        ruleset = campaign["sistema"]["ruleset"]
        self.assertEqual(ruleset["atual"], "dnd_5e_2014")
        self.assertEqual(ruleset["alvo"], "dnd_5_5e")
        self.assertFalse(ruleset["migracao"]["ativacao"]["permitida"])
        self.assertTrue(ruleset["migracao"]["ativacao"]["requisitos"]["task_5_conversao_ren"])
        self.assertEqual(self.active_raw["personagem"]["sistema"], "Dungeons & Dragons 5e")
        self.assertIn("ki", self.active_raw["recursos_de_classe"])
        self.assertNotIn("focus", self.active_raw["recursos_de_classe"])
        self.assertFalse(self.migration["ativacao"]["aplica_antes_do_gate"])

    def test_identidade_nivel_e_numeros_centrais_sao_preservados(self) -> None:
        self.assertEqual((self.target.ruleset, self.target.level, self.target.subclass), ("dnd_5_5e", 7, "Guerreiro das Sombras"))
        self.assertEqual(self.target.armor_class, 17)
        self.assertEqual(self.target.hit_points, {"atuais": 45, "maximos": 52, "dados_de_vida": "7d8"})
        self.assertEqual(self.target.initiative, 4)
        self.assertEqual(self.target.proficiency_bonus, 3)
        self.assertEqual(self.target.speed, 55)
        self.assertEqual(self.target.abilities, self.active.abilities)
        self.assertEqual(self.target.saves, self.active.saves)

    def test_focus_substitui_ki_sem_restaurar_recurso(self) -> None:
        self.assertEqual(self.target.focus, {"pontos_atuais": 1, "pontos_maximos": 7, "cd": 14, "recarga": "descanso curto ou longo"})
        self.assertEqual(self.target.focus["pontos_atuais"], self.active.resources["ki"]["pontos_atuais"])

    def test_focus_atual_deriva_do_estado_efetivo_e_nao_de_constante(self) -> None:
        changed = copy.deepcopy(self.active_raw)
        changed["recursos_de_classe"]["ki"]["pontos_atuais"] = 3
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ficha.yaml"
            path.write_text(yaml.safe_dump(changed, allow_unicode=True, sort_keys=False), encoding="utf-8")
            target = ficha_ren_5_5e.load(path, self.migration_path)
        self.assertEqual(target.focus["pontos_atuais"], 3)

    def test_ataques_usam_artes_marciais_1d8_sem_transformar_dardo_em_arma_de_monge(self) -> None:
        attacks = self.target.attacks
        self.assertEqual((attacks["golpe_desarmado"].attack_bonus, attacks["golpe_desarmado"].damage), (7, "1d8+4"))
        self.assertEqual((attacks["wakizashi"].attack_bonus, attacks["wakizashi"].damage), (7, "1d8+4"))
        self.assertEqual((attacks["shuriken"].attack_bonus, attacks["shuriken"].damage), (7, "1d4+4"))
        self.assertEqual(self.migration["classe_alvo"]["dado_artes_marciais"], "1d8")
        self.assertFalse(self.migration["ataques_alvo"]["shuriken"]["arma_monge_5_5e"])

    def test_capacidades_de_monge_nivel_7_foram_convertidas(self) -> None:
        features = self.target.features
        metabolism = features["uncanny_metabolism"]
        self.assertEqual(metabolism["cura_ren_nivel_7"], "7 + 1d8")
        self.assertEqual(metabolism["recarga"], "1 uso por descanso longo")
        deflect = features["deflect_attacks"]
        self.assertEqual(deflect["reducao_ren_nivel_7"], "1d10 + 11")
        redirect = deflect["redirecionar_se_reduzir_a_zero"]
        self.assertEqual(redirect["alcance_se_ataque_corpo_a_corpo_pes"], 5)
        self.assertEqual(redirect["alcance_se_ataque_a_distancia_pes"], 60)
        self.assertEqual(redirect["dano_falha"], "2d8 + 4")
        self.assertEqual(features["slow_fall"]["reducao_ren_nivel_7"], 35)
        stunning = features["stunning_strike"]
        self.assertEqual(stunning["limite"], "uma vez por turno")
        self.assertIn("deslocamento pela metade", stunning["sucesso"])
        self.assertIn("Força", features["empowered_strikes"]["efeito"])
        self.assertIn("Incapacitado", features["evasion"]["restricao"])

    def test_focus_basico_reflete_as_acoes_revisadas(self) -> None:
        uses = self.migration["focus"]["usos"]
        self.assertFalse(uses["flurry_of_blows"]["requer_acao_atacar_antes"])
        self.assertIn("gratuito", uses["patient_defense"])
        self.assertIn("gratuito", uses["step_of_the_wind"])
        self.assertIn("Esquivar", uses["patient_defense"]["com_focus"])
        self.assertIn("salto dobrado", uses["step_of_the_wind"]["com_focus"])

    def test_guerreiro_das_sombras_perde_magias_2014_e_ganha_darkness_revisada(self) -> None:
        arts = self.target.shadow["shadow_arts"]
        self.assertEqual(arts["darkvision_pes"], 60)
        darkness = arts["darkness"]
        self.assertEqual(darkness["custo_focus"], 1)
        self.assertTrue(darkness["ve_dentro_da_propria_escuridao"])
        self.assertEqual(darkness["mover_area_no_inicio_do_turno_pes"], 60)
        removed = set(arts["removidas_da_versao_2014"])
        self.assertIn("Passos sem Pegadas", removed)
        self.assertIn("Silêncio", removed)
        shadow_step = self.target.shadow["shadow_step"]
        self.assertEqual(shadow_step["alcance_pes"], 60)
        self.assertEqual(shadow_step["custo_focus"], 0)
        self.assertIn("vantagem", shadow_step["efeito_pos_teleporte"])

    def test_beneficios_de_criacao_e_passivos_permanecem_canonizados(self) -> None:
        legacy = self.target.legacy_creation
        self.assertTrue(legacy["nao_sao_fallback_ruleset_2014"])
        self.assertTrue(legacy["nao_reconstroem_origem_5_5e"])
        self.assertTrue(legacy["nao_concedem_novos_origin_feats"])
        self.assertTrue(legacy["movel"]["preservar_texto_funcional_existente"])
        self.assertTrue(legacy["actor"]["preservar_texto_funcional_existente"])
        self.assertTrue(legacy["observant"]["preservar_texto_funcional_existente"])
        self.assertEqual(self.target.passives, {"percepcao": 21, "investigacao": 20, "intuicao": 16})
        self.assertEqual(self.target.skills, self.active.skills)

    def test_decisao_proibe_rebuild_e_retroatividade(self) -> None:
        text = (ROOT / "regras/decisoes.md").read_text(encoding="utf-8")
        self.assertIn("DEC-0008", text)
        self.assertIn("não reconstruir a origem de Ren", text)
        self.assertIn("não reescreve sessões concluídas, rolagens, recursos gastos", text)
        self.assertIn("staged e não operacional até a Task 8", text)
        self.assertIn("Ki vira Focus 1:1", text)


if __name__ == "__main__":
    unittest.main()
