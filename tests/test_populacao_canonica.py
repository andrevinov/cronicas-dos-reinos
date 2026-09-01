from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import populacao


class PopulacaoCanonicaTest(unittest.TestCase):
    def test_todos_os_npcs_recebem_classificacao_explicita(self):
        result = populacao.validate_repo(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        npc_doc = yaml.safe_load(
            (ROOT / "estado/npcs/index.yaml").read_text(encoding="utf-8")
        )
        relation_doc = yaml.safe_load(
            (ROOT / "estado/relacoes/index.yaml").read_text(encoding="utf-8")
        )
        classes = populacao.load_population(ROOT)["classificacoes"]
        expected_strategic = len(classes["promovidos_agentes_estrategicos"])
        expected_light = len(classes["promovidos_agentes_leves"])
        expected_represented = len(classes["representados_por_agente"])
        expected_persistent = len(classes["persistentes_sem_agenda"])
        self.assertEqual(result["npcs"], npc_doc["quantidade"])
        self.assertEqual(result["relacoes"], relation_doc["quantidade"])
        self.assertEqual(result["estrategicos"], expected_strategic)
        self.assertEqual(result["promovidos"], expected_light)
        self.assertEqual(result["representados"], expected_represented)
        self.assertEqual(result["persistentes"], expected_persistent)
        self.assertEqual(
            result["persistentes"],
            result["npcs"]
            - result["estrategicos"]
            - result["promovidos"]
            - result["representados"],
        )

    def test_npc_sem_relacao_nao_escapa_da_classificacao(self):
        npcs = yaml.safe_load(
            (ROOT / "estado/npcs/index.yaml").read_text(encoding="utf-8")
        )["npcs"]
        relations = yaml.safe_load(
            (ROOT / "estado/relacoes/index.yaml").read_text(encoding="utf-8")
        )["relacoes"]
        classes = populacao.load_population(ROOT)["classificacoes"]
        classified = (
            set(classes["promovidos_agentes_estrategicos"])
            | set(classes["promovidos_agentes_leves"])
            | set(classes["persistentes_sem_agenda"])
            | set(classes["representados_por_agente"])
        )
        self.assertTrue(set(npcs) - set(relations) <= classified)

    def test_novo_npc_sem_relacao_exige_destino_em_cenario_isolado(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            for relative in (
                populacao.POPULATION,
                populacao.NPCS,
                populacao.RELATIONS,
                populacao.STRATEGIC,
                populacao.LIGHT,
            ):
                target = repo / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())

            npc_path = repo / populacao.NPCS
            npc_doc = yaml.safe_load(npc_path.read_text(encoding="utf-8"))
            npc_doc["npcs"]["npc_sem_relacao_fixture"] = {
                "arquivo": "estado/npcs/npc_sem_relacao_fixture.yaml"
            }
            npc_doc["quantidade"] = len(npc_doc["npcs"])
            npc_path.write_text(
                yaml.safe_dump(npc_doc, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )

            missing = populacao.validate_repo(repo)
            self.assertFalse(missing["ok"])
            self.assertIn("npc_sem_relacao_fixture", missing["erros"][0])

            population_path = repo / populacao.POPULATION
            inventory = yaml.safe_load(population_path.read_text(encoding="utf-8"))
            inventory["classificacoes"]["persistentes_sem_agenda"].append(
                "npc_sem_relacao_fixture"
            )
            population_path.write_text(
                yaml.safe_dump(inventory, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            classified = populacao.validate_repo(repo)
        self.assertTrue(classified["ok"], classified["erros"])

    def test_promocao_estrategica_vem_do_canone_existente(self):
        data = populacao.load_population(ROOT)["classificacoes"]
        strategic = set(data["promovidos_agentes_estrategicos"])
        self.assertIn("corven_dalm", strategic)
        self.assertNotIn("corven_dalm", data["promovidos_agentes_leves"])
        self.assertNotIn("corven_dalm", data["persistentes_sem_agenda"])

    def test_promocoes_leves_vem_do_canone_existente(self):
        data = populacao.load_population(ROOT)["classificacoes"]
        established = {
            "bram_vask",
            "halessa_vorn",
            "jack_mooney",
            "kethra_dunn",
            "luath",
            "maerra_thandrel",
            "pell",
            "silva_elkwood",
        }
        self.assertTrue(established <= set(data["promovidos_agentes_leves"]))

    def test_subordinados_nao_duplicam_camada_do_agente_pai(self):
        data = populacao.load_population(ROOT)["classificacoes"]["representados_por_agente"]
        self.assertEqual(data["dain_brass_mord"], "red_sail")
        self.assertEqual(data["rusk_cinza"], "red_sail")
        self.assertEqual(data["sirrus_melandor"], "casa_de_tyr")
        self.assertEqual(data["noll"], "bram_vask")
        self.assertEqual(data["tobb_marlin"], "jack_mooney")

    def test_personagens_importantes_podem_continuar_sem_agenda(self):
        data = populacao.load_population(ROOT)["classificacoes"]
        persistent = set(data["persistentes_sem_agenda"])
        self.assertTrue({"nera_vell", "colm_dunn", "peta"} <= persistent)
        self.assertIn("sella_conferente_galeria", persistent)

    def test_validacao_populacional_nao_cria_cadencia_automaticamente(self):
        agenda_path = ROOT / "narrador/mundo/agenda.yaml"
        before = agenda_path.read_bytes()
        result = populacao.validate_repo(ROOT)
        after = agenda_path.read_bytes()
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(before, after)

    def test_primeiras_reavaliacoes_leves_foram_escalonadas_sem_rajada(self):
        index = yaml.safe_load((ROOT / "narrador/agentes-leves/index.yaml").read_text(encoding="utf-8"))
        starts = {
            agent_id: meta["inicio"]["data"]
            for agent_id, meta in index["agentes"].items()
        }
        expected_initial_starts = {
            "kethra_dunn": "11 Eleasis, 1372 DR",
            "bram_vask": "12 Eleasis, 1372 DR",
            "luath": "13 Eleasis, 1372 DR",
            "silva_elkwood": "14 Eleasis, 1372 DR",
            "maerra_thandrel": "15 Eleasis, 1372 DR",
            "halessa_vorn": "16 Eleasis, 1372 DR",
            "jack_mooney": "17 Eleasis, 1372 DR",
            "pell": "18 Eleasis, 1372 DR",
        }
        for agent_id, start in expected_initial_starts.items():
            self.assertEqual(starts[agent_id], start)
        self.assertEqual(index["orcamento"]["max_novas_por_checkpoint"], 1)
        self.assertEqual(index["orcamento"]["max_pendencias_abertas"], 2)


if __name__ == "__main__":
    unittest.main()
