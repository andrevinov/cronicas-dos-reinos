from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import agentes_leves as light


class MundoVivoNoopBudgetTest(unittest.TestCase):
    def setUp(self):
        self.contract = yaml.safe_load(
            (ROOT / "baseline/mundo-vivo-noop-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )

    def test_tetos_batem_com_codigo_e_indice_real(self):
        self.assertEqual(self.contract["schema_orcamento_mundo_vivo_noop"], 1)
        limits = self.contract["limites"]
        index = light.load_index(ROOT)
        self.assertEqual(
            limits["max_checks_cache_negativo_por_checkpoint"],
            index["orcamento"]["max_checks_cache_negativo_por_checkpoint"],
        )
        self.assertEqual(limits["max_fontes_causais_por_agente"], light.MAX_CAUSAL_SOURCES)
        self.assertEqual(limits["max_bytes_por_fonte_causal"], light.MAX_CAUSAL_SOURCE_BYTES)
        self.assertEqual(
            limits["max_novas_pendencias_leves_por_checkpoint"],
            index["orcamento"]["max_novas_por_checkpoint"],
        )
        self.assertEqual(
            limits["max_pendencias_leves_abertas"],
            index["orcamento"]["max_pendencias_abertas"],
        )
        self.assertEqual(limits["max_escritas_cache_hit"], 1)
        self.assertEqual(limits["max_escritas_concluir_noop"], 2)
        self.assertEqual(limits["fragmentos_abertos_cache_hit"], 0)
        self.assertEqual(limits["leituras_causais_sem_cache"], 0)
        self.assertEqual(limits["schedulers_adicionados"], 0)

    def test_invariantes_nao_expandem_cache_para_outras_camadas(self):
        inv = self.contract["invariantes"]
        self.assertTrue(inv["cache_so_nasce_de_noop_explicito"])
        self.assertTrue(inv["cache_restrito_a_agentes_leves"])
        self.assertTrue(inv["cache_nao_afeta_direcao"])
        self.assertTrue(inv["cache_nao_afeta_evento_mundial"])
        self.assertTrue(inv["cache_stale_falha_aberto_para_avaliacao"])
        self.assertTrue(inv["cache_ausente_preserva_comportamento_anterior"])
        self.assertTrue(inv["concluir_noop_e_idempotente"])
        self.assertTrue(inv["queda_entre_escritas_mantem_pendencia_bloqueante"])

    def test_roteador_operacional_usa_concluir_noop_so_para_agente_leve(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("tipo: reavaliar_agente_leve", text)
        self.assertIn("agentes_leves.py concluir-noop <id>", text)
        self.assertIn("Para qualquer outra pendência sem mudança", text)
        self.assertIn("barreira_mundo.py concluir <id>", text)
        self.assertIn("docs/agente/mundo-vivo-noop-compaction.md", text)


if __name__ == "__main__":
    unittest.main()
