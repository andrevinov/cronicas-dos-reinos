from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import adversarios
import dungeons
import ecologia_local
import microeventos_locais
import recompensas


class DungeonRepositoryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = dungeons.load_contract(ROOT)
        cls.index = dungeons.load_index(ROOT, cls.contract)
        cls.dungeon_id = "sarbreen_poroes_secos"
        cls.meta = cls.index["dungeons"][cls.dungeon_id]
        cls.manifest = dungeons.load_manifest(
            ROOT, cls.dungeon_id, cls.meta, cls.contract, cross_validate=True
        )

    def test_repositorio_real_valida_dungeon_e_quatro_niveis(self):
        result = dungeons.validate_repo(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["dungeons"], len(self.index["dungeons"]))
        self.assertEqual(
            result["niveis"],
            sum(len(dungeons.load_manifest(ROOT, dungeon_id, meta, self.contract)["estrutura"]["niveis"])
                for dungeon_id, meta in self.index["dungeons"].items()),
        )
        self.assertEqual(
            [item["numero"] for item in self.manifest["estrutura"]["niveis"]],
            [1, 2, 3, 4],
        )

    def test_piloto_preserva_fronteira_canonica_de_sarbreen(self):
        scope = self.manifest["escopo_canonico"]
        preserved = " ".join(scope["fatos_preservados"]).casefold()
        excluded = " ".join(scope["nao_estabelece"]).casefold()
        self.assertIn("cidade anã quebrada", preserved)
        self.assertIn("balança velha", preserved)
        self.assertIn("ponte de kozakura", excluded)
        self.assertEqual(self.manifest["estatuto"], "preparada_nao_materializada")
        self.assertFalse(self.manifest["recompensa_final"]["obtencao_automatica"])

    def test_todo_nivel_e_conectado_tem_recuo_e_contrajogo(self):
        for meta in self.manifest["estrutura"]["niveis"]:
            query = dungeons.show_level(ROOT, self.dungeon_id, meta["numero"])
            level = query["nivel"]
            areas = {area["id"]: area for area in level["areas"]}
            reached = dungeons._connected_areas(areas, level["entrada_area"])
            self.assertEqual(reached, set(areas), meta["numero"])
            self.assertTrue(any(item["tipo"] == "recuo" for item in level["saidas"]))
            for encounter in level["encontros"]:
                self.assertGreaterEqual(len(encounter["alternativas"]), 3)
                self.assertTrue(encounter["retirada"])
            for danger in level["perigos"]:
                self.assertTrue(danger["sinalizacao"])
                self.assertGreaterEqual(len(danger["contrajogo"]), 2)

    def test_encontros_referenciam_criaturas_de_ficha_cheia_e_ameaca_congelada(self):
        references: set[str] = set()
        classifications: set[str] = set()
        for meta in self.manifest["estrutura"]["niveis"]:
            level = dungeons.show_level(ROOT, self.dungeon_id, meta["numero"])["nivel"]
            for encounter in level["encontros"]:
                references.update(item["id"] for item in encounter["adversarios"])
                classifications.add(encounter["avaliacao_referencia"]["classificacao"])
        self.assertGreaterEqual(len(references), 3)
        self.assertIn("letal", classifications)
        adversary_index = adversarios.load_index(ROOT)
        self.assertLessEqual(references, set(adversary_index["adversarios"]))
        roper_id = "arquetipo_estrangulador_adaptado_5_5e"
        roper = adversarios.load_adversary(ROOT, roper_id)["resultado"]
        self.assertEqual(roper["proveniencia"]["origem"], "adaptado_edicao_anterior")
        self.assertEqual(roper["ruleset"], "dnd_5_5e")

    def test_recompensa_final_reutiliza_catalogo_e_exige_obtencao(self):
        reward = self.manifest["recompensa_final"]
        planned_catalog = recompensas.load_planned(ROOT)
        planned = planned_catalog["por_local"][self.manifest["local_id"]]
        matches = [item for item in planned if item["id"] == reward["id"]]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["condicao_de_descoberta"], reward["condicao"])
        self.assertNotIn("estado", matches[0])
        self.assertEqual(matches[0]["origem"], "autoral")
        generated, _ = recompensas.generate_map(
            recompensas.load_index(ROOT),
            recompensas.load_tables(ROOT),
            planned_catalog,
            self.manifest["local_id"],
            3,
            "letal",
            ecology=ecologia_local.lookup_canonical(ROOT, self.manifest["local_id"])["perfil"],
        )
        generated_reward = next(item for item in generated["recompensas"] if item["id"] == reward["id"])
        self.assertEqual(generated_reward["estado"], "oculto")
        self.assertEqual(generated["geracao"]["planejadas"], 1)

    def test_consultas_sao_dirigidas_e_nao_abrem_fichas_ou_outros_niveis(self):
        limit = self.contract["orcamento"]["consulta_max_bytes"]
        manifest_query = dungeons.show(ROOT, self.dungeon_id)
        self.assertLessEqual(len(dungeons._dump(manifest_query).encode("utf-8")), limit)
        self.assertFalse(any("nivel-" in source for source in manifest_query["fontes_lidas"]))
        for number in range(1, 5):
            query = dungeons.show_level(ROOT, self.dungeon_id, number)
            self.assertLessEqual(len(dungeons._dump(query).encode("utf-8")), limit)
            level_sources = [source for source in query["fontes_lidas"] if "nivel-" in source]
            self.assertEqual(level_sources, [f"narrador/dungeons/sarbreen_poroes_secos/nivel-{number}.yaml"])
            self.assertFalse(any("adversarios/fichas" in source for source in query["fontes_lidas"]))
            self.assertFalse(any("recompensas/planejadas" in source for source in query["fontes_lidas"]))

    def test_local_tem_ecologia_e_pool_sem_materializar_presenca(self):
        profile = ecologia_local.lookup_canonical(ROOT, self.manifest["local_id"])["perfil"]
        self.assertEqual(profile["familia"], "ruina_subterranea")
        eligible = microeventos_locais.eligible_cards(microeventos_locais.load_index(ROOT), profile)
        self.assertGreaterEqual(len(eligible), microeventos_locais.MIN_ELIGIBLE_PER_LOCAL)
        self.assertNotIn("presenca", profile)
        self.assertNotIn("evento", profile)


class DungeonSyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        shutil.copy2(ROOT / "campanha.yaml", self.repo / "campanha.yaml")
        shutil.copytree(ROOT / "narrador/dungeons", self.repo / "narrador/dungeons")
        shutil.copytree(ROOT / "narrador/adversarios", self.repo / "narrador/adversarios")
        shutil.copytree(ROOT / "cenario/locais", self.repo / "cenario/locais")
        rewards = self.repo / "narrador/recompensas"
        rewards.mkdir(parents=True)
        shutil.copy2(ROOT / "narrador/recompensas/planejadas.yaml", rewards / "planejadas.yaml")
        manifest = yaml.safe_load(
            (ROOT / "narrador/dungeons/sarbreen_poroes_secos/manifesto.yaml").read_text(encoding="utf-8")
        )
        for raw in manifest["escopo_canonico"]["ancoras"]:
            source = ROOT / raw
            target = self.repo / raw
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def tearDown(self):
        self.temp.cleanup()

    def _load(self, rel: str):
        return yaml.safe_load((self.repo / rel).read_text(encoding="utf-8"))

    def _write(self, rel: str, value) -> None:
        (self.repo / rel).write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

    def test_area_desconectada_falha_fechada(self):
        rel = "narrador/dungeons/sarbreen_poroes_secos/nivel-1.yaml"
        level = self._load(rel)
        level["areas"].extend(
            [
                {
                    "id": "ilha_a", "nome": "Ilha A", "tipo": "exploracao",
                    "descricao": "Área sintética isolada.", "sinais": ["a", "b"],
                    "conexoes": ["ilha_b"],
                },
                {
                    "id": "ilha_b", "nome": "Ilha B", "tipo": "exploracao",
                    "descricao": "Área sintética isolada.", "sinais": ["c", "d"],
                    "conexoes": ["ilha_a"],
                },
            ]
        )
        self._write(rel, level)
        result = dungeons.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("desconectadas", result["erros"][0])

    def test_recompensa_automatica_falha_fechada(self):
        rel = "narrador/dungeons/sarbreen_poroes_secos/manifesto.yaml"
        manifest = self._load(rel)
        manifest["recompensa_final"]["obtencao_automatica"] = True
        self._write(rel, manifest)
        result = dungeons.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("automática", result["erros"][0])

    def test_classificacao_de_ameaca_desatualizada_falha_fechada(self):
        rel = "narrador/dungeons/sarbreen_poroes_secos/nivel-2.yaml"
        level = self._load(rel)
        level["encontros"][0]["avaliacao_referencia"]["classificacao"] = "moderada"
        self._write(rel, level)
        result = dungeons.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("diverge da avaliação", result["erros"][0])


if __name__ == "__main__":
    unittest.main()
