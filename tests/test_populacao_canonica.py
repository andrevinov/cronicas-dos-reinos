from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import populacao


class PopulacaoCanonicaTest(unittest.TestCase):
    def test_todas_as_35_relacoes_recebem_classificacao_explicita(self):
        result = populacao.validate_repo(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["relacoes"], 35)
        self.assertEqual(result["promovidos"], 8)
        self.assertEqual(result["representados"], 6)
        self.assertEqual(result["persistentes"], 21)

    def test_promocoes_vem_do_canone_existente(self):
        data = populacao.load_population(ROOT)["classificacoes"]
        self.assertEqual(
            set(data["promovidos_agentes_leves"]),
            {
                "bram_vask",
                "halessa_vorn",
                "jack_mooney",
                "kethra_dunn",
                "luath",
                "maerra_thandrel",
                "pell",
                "silva_elkwood",
            },
        )

    def test_subordinados_nao_duplicam_scheduler_do_agente_pai(self):
        data = populacao.load_population(ROOT)["classificacoes"]["representados_por_agente"]
        self.assertEqual(data["dain_brass_mord"], "red_sail")
        self.assertEqual(data["rusk_cinza"], "red_sail")
        self.assertEqual(data["sirrus_melandor"], "casa_de_tyr")
        self.assertEqual(data["noll"], "bram_vask")
        self.assertEqual(data["tobb_marlin"], "jack_mooney")

    def test_personagens_importantes_podem_continuar_sem_agenda(self):
        data = populacao.load_population(ROOT)["classificacoes"]
        persistent = set(data["persistentes_sem_agenda"])
        self.assertTrue({"nera_vell", "colm_dunn", "corven_dalm", "peta"} <= persistent)

    def test_primeiras_reavaliacoes_foram_escalonadas_sem_rajada(self):
        index = yaml.safe_load((ROOT / "narrador/agentes-leves/index.yaml").read_text(encoding="utf-8"))
        starts = {
            agent_id: meta["inicio"]["data"]
            for agent_id, meta in index["agentes"].items()
        }
        self.assertEqual(
            starts,
            {
                "kethra_dunn": "11 Eleasis, 1372 DR",
                "bram_vask": "12 Eleasis, 1372 DR",
                "luath": "13 Eleasis, 1372 DR",
                "silva_elkwood": "14 Eleasis, 1372 DR",
                "maerra_thandrel": "15 Eleasis, 1372 DR",
                "halessa_vorn": "16 Eleasis, 1372 DR",
                "jack_mooney": "17 Eleasis, 1372 DR",
                "pell": "18 Eleasis, 1372 DR",
            },
        )
        self.assertEqual(index["orcamento"]["max_novas_por_checkpoint"], 1)
        self.assertEqual(index["orcamento"]["max_pendencias_abertas"], 2)


if __name__ == "__main__":
    unittest.main()
