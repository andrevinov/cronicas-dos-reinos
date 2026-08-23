from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica_hotpath as hot
import microeventos_locais as micro
import microeventos_transito as transit
import pressao_ravens_bluff as pressao


class UrbanTransitBudgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = yaml.safe_load(
            (ROOT / "baseline/urban-transit-ecology-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )

    def test_contrato_congela_duas_chamadas_e_zero_infra_paralela(self):
        limits = self.contract["limites"]
        self.assertEqual(limits["max_novos_catalogos"], 0)
        self.assertEqual(limits["max_novos_arquivos_estado"], 0)
        self.assertEqual(limits["max_novos_schedulers"], 0)
        self.assertEqual(limits["max_novos_endpoints"], 0)
        self.assertEqual(limits["max_novos_algoritmos_baralho"], 0)
        self.assertEqual(limits["max_novos_rng"], 0)
        self.assertEqual(limits["max_chamadas_orquestracao_por_turno"], 2)
        self.assertEqual(limits["max_fontes_transito_preparar"], 4)
        self.assertEqual(limits["max_escritas_transito_preparar"], 0)
        self.assertEqual(limits["max_escritas_transito_confirmar"], 1)
        self.assertEqual(limits["max_historico_transito_recente"], transit.MAX_HISTORY)

    def test_reutiliza_exatamente_catalogo_estado_e_helpers_existentes(self):
        self.assertEqual(transit.micro.INDEX, micro.INDEX)
        self.assertEqual(transit.micro.STATE, micro.STATE)
        source = (ROOT / "ferramentas/microeventos_transito.py").read_text(encoding="utf-8")
        self.assertNotIn("def atomic(", source)
        self.assertNotIn("def deck_order(", source)
        self.assertNotIn("import random", source)
        self.assertNotIn("import secrets", source)
        self.assertIn("micro._draw_occurrence", source)
        self.assertIn("micro._draw_card", source)
        self.assertIn("micro.commit_plan", source)

    def test_ocorrencia_continua_tres_para_um(self):
        index = micro.load_index(ROOT)
        results = [item["resultado"] for item in index["ocorrencia"]["fichas"]]
        self.assertEqual(results.count("rotina"), self.contract["limites"]["ocorrencia_rotina"])
        self.assertEqual(
            results.count("microevento"),
            self.contract["limites"]["ocorrencia_microevento"],
        )

    def test_fontes_sao_quatro_roteadores_compactos_e_pressao_e_read_only(self):
        result = transit.plan(ROOT, scene_id="budget-source-check")["publico"]
        self.assertEqual(
            result["fontes_lidas"],
            [
                micro.INDEX.as_posix(),
                micro.STATE.as_posix(),
                pressao.PROFILE.as_posix(),
                pressao.STATE.as_posix(),
            ],
        )
        self.assertLessEqual(
            len(result["fontes_lidas"]),
            self.contract["limites"]["max_fontes_transito_preparar"],
        )

    def test_hot_path_declara_mesma_dupla_preparar_concluir(self):
        contract = hot._transaction_contract()
        self.assertIn("cronica concluir", contract["comando"])
        source = (ROOT / "ferramentas/cronica_hotpath.py").read_text(encoding="utf-8")
        self.assertIn("urban_transit", source)
        self.assertNotIn("endpoints.transito", source)
        self.assertNotIn("cena_mundo_v5", source)


if __name__ == "__main__":
    unittest.main()
