from __future__ import annotations

import importlib.util
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


REPO = Path(__file__).parents[1]
TOOLS = REPO / "ferramentas"
sys.path.insert(0, str(TOOLS))
MODULE_PATH = TOOLS / "ameacas.py"
SPEC = importlib.util.spec_from_file_location("ameacas", MODULE_PATH)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


class ThreatRepositoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = mod.load_contract(REPO)
        cls.profiles = mod.load_profiles(REPO, cls.contract)["perfis"]
        cls.index = mod.adversarios.load_index(REPO)["adversarios"]
        cls.roster = yaml.safe_load(
            (REPO / "narrador/juppongatana/index.yaml").read_text(encoding="utf-8")
        )["membros"]

    def test_perfis_cobrem_registro_e_juppongatana_continua_canonica(self):
        self.assertEqual(set(self.profiles), set(self.index))
        self.assertLessEqual(set(self.roster), set(self.profiles))
        for adversary_id in self.roster:
            self.assertEqual(self.profiles[adversary_id]["natureza"], "ator_canonico")

    def test_biblioteca_tem_npcs_e_criaturas_reutilizaveis_de_ficha_cheia(self):
        templates = {
            adversary_id
            for adversary_id, profile in self.profiles.items()
            if profile["natureza"] == "arquetipo_reutilizavel"
        }
        self.assertGreaterEqual(len(templates), 4)
        self.assertGreaterEqual(
            sum(self.index[item]["tipo"] == "npc" for item in templates), 2
        )
        self.assertGreaterEqual(
            sum(self.index[item]["tipo"] == "criatura" for item in templates), 2
        )
        for adversary_id in templates:
            sheet = mod.adversarios.load_adversary(REPO, adversary_id)["resultado"]
            repertoire = sum(
                len(sheet[group])
                for group in ("acoes", "acoes_bonus", "reacoes", "acoes_lendarias")
            )
            self.assertGreaterEqual(repertoire, 6, adversary_id)
            self.assertIn(
                sheet["proveniencia"]["origem"],
                {"original_campanha", "adaptado_edicao_anterior"},
            )
            if sheet["proveniencia"]["origem"] == "adaptado_edicao_anterior":
                self.assertTrue(sheet["proveniencia"]["adaptacao"])
                self.assertTrue(sheet["proveniencia"]["referencia"])
            self.assertIn("presença", sheet["proveniencia"]["adaptacao"])
            for specialty_id in sheet["especialidades"]["ids"]:
                detail = mod.adversarios.load_specialty(REPO, adversary_id, specialty_id)
                self.assertTrue(detail["resultado"]["procedimentos"], adversary_id)

    def test_combate_e_especialidade_podem_ter_ameacas_diferentes(self):
        combat = mod.evaluate(REPO, "kajiwara_shizune", vector="combate", level=7)
        specialty = mod.evaluate(REPO, "kajiwara_shizune", vector="especialidade", level=7)
        self.assertEqual(combat["resultado"]["classificacao"], "moderada")
        self.assertEqual(specialty["resultado"]["classificacao"], "letal")

    def test_internos_sao_esmagadores_para_nivel_sete_sem_congelar_ren(self):
        for adversary_id in ("amagiri_seishiro", "wetuji", "fuji"):
            result = mod.evaluate(REPO, adversary_id, vector="combate", level=7)
            self.assertEqual(result["resultado"]["classificacao"], "esmagadora")
            self.assertTrue(result["resultado"]["saida_observavel_obrigatoria"])

    def test_consultas_permanecem_dirigidas_e_abaixo_de_quatro_kib(self):
        ceiling = self.contract["orcamento"]["consulta_max_bytes"]
        for adversary_id, profile in self.profiles.items():
            for vector in self.contract["vetores"]:
                result = mod.evaluate(
                    REPO,
                    adversary_id,
                    vector=vector,
                    level=min(profile["patamares"][vector], 20),
                )
                self.assertLessEqual(len(mod._dump(result).encode("utf-8")), ceiling)
                self.assertEqual(len(result["fontes_lidas"]), 4)
                self.assertNotIn(self.index[adversary_id]["arquivo"], result["fontes_lidas"])


class ThreatSyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "narrador/adversarios").mkdir(parents=True)
        shutil.copy(REPO / mod.CONTRACT_PATH, self.repo / mod.CONTRACT_PATH)
        shutil.copy(
            REPO / mod.adversarios.CONTRACT_PATH,
            self.repo / mod.adversarios.CONTRACT_PATH,
        )
        self._write(
            "campanha.yaml",
            {"sistema": {"ruleset": {"atual": "dnd_5_5e"}}},
        )
        self._write(
            mod.adversarios.INDEX_PATH.as_posix(),
            {
                "schema_indice_adversarios": 1,
                "natureza": "reservado",
                "contrato": mod.adversarios.CONTRACT_PATH.as_posix(),
                "adversarios": {
                    "arquetipo_teste": {
                        "nome": "Arquétipo — Teste",
                        "tipo": "npc",
                        "funcao": "hibrido",
                        "arquivo": "narrador/adversarios/fichas/arquetipo_teste.yaml",
                        "especialidades_arquivo": "narrador/adversarios/especialidades/arquetipo_teste.yaml",
                    }
                },
            },
        )
        self.profile = {
            "schema_perfis_ameaca": 1,
            "natureza": "reservado",
            "contrato": mod.CONTRACT_PATH.as_posix(),
            "perfis": {
                "arquetipo_teste": {
                    "natureza": "arquetipo_reutilizavel",
                    "patamares": {"combate": 8, "especialidade": 6},
                    "vetores": ["controle"],
                    "sinalizacao": "Guarda e rota são visíveis.",
                    "saidas_plausiveis": ["recuar"],
                }
            },
        }
        self._write(mod.PROFILES_PATH.as_posix(), self.profile)

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, relative: str, data: object) -> None:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def test_calculo_e_deterministico_e_contexto_so_muda_componentes_declarados(self):
        base = mod.evaluate(self.repo, "arquetipo_teste", vector="combate", level=7)
        repeated = mod.evaluate(self.repo, "arquetipo_teste", vector="combate", level=7)
        lethal = mod.evaluate(
            self.repo,
            "arquetipo_teste",
            vector="combate",
            level=7,
            resources="gastos",
        )
        with_ally = mod.evaluate(
            self.repo,
            "arquetipo_teste",
            vector="combate",
            level=7,
            allies=1,
        )
        self.assertEqual(base, repeated)
        self.assertEqual(base["resultado"]["classificacao"], "alta")
        self.assertEqual(lethal["resultado"]["classificacao"], "letal")
        self.assertEqual(with_ally["resultado"]["classificacao"], "moderada")
        self.assertTrue(lethal["resultado"]["saida_observavel_obrigatoria"])

    def test_perfil_ausente_ou_extra_falha_fechado(self):
        self.profile["perfis"]["outro"] = self.profile["perfis"]["arquetipo_teste"]
        self._write(mod.PROFILES_PATH.as_posix(), self.profile)
        with self.assertRaisesRegex(mod.ThreatValidationError, "perfis divergem"):
            mod.load_profiles(self.repo)

    def test_aliado_quantidade_e_contexto_invalidos_falham_antes_do_calculo(self):
        with self.assertRaises(mod.ThreatValidationError):
            mod.evaluate(self.repo, "arquetipo_teste", vector="combate", level=7, allies=6)
        with self.assertRaises(mod.ThreatValidationError):
            mod.evaluate(self.repo, "arquetipo_teste", vector="combate", level=7, enemies=0)
        with self.assertRaises(mod.ThreatValidationError):
            mod.evaluate(self.repo, "arquetipo_teste", vector="combate", level=7, terrain="inventado")


if __name__ == "__main__":
    unittest.main()
