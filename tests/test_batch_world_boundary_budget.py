from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
BASELINE = ROOT / "baseline/batch-world-boundary-resolution-orcamento.yaml"
SOURCE = ROOT / "ferramentas/resolver_fronteira.py"


class BatchWorldBoundaryBudgetTest(unittest.TestCase):
    def test_contrato_congela_limites_e_invariantes(self):
        data = yaml.safe_load(BASELINE.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_orcamento_batch_fronteira"], 1)
        self.assertEqual(data["natureza"], "contrato_de_regressao")

        limits = data["limites"]
        self.assertEqual(limits["max_pendencias_por_lote"], 16)
        self.assertEqual(limits["max_fragmentos_dirigidos_por_pendencia"], 1)
        self.assertEqual(limits["max_orquestracoes_preparar"], 1)
        self.assertEqual(limits["max_orquestracoes_aplicar"], 1)
        self.assertEqual(limits["escritas_preparar"], 0)
        self.assertEqual(limits["schedulers_adicionados"], 0)
        self.assertEqual(limits["estados_paralelos_adicionados"], 0)
        self.assertEqual(limits["scans_globais_adicionados"], 0)

        invariants = data["invariantes"]
        required = {
            "preparar_e_read_only",
            "todas_decisoes_validam_antes_da_primeira_escrita",
            "token_por_pendencia_detecta_staleness",
            "itens_omitidos_permanecem_abertos",
            "evento_canonico_nunca_aceita_noop",
            "candidato_autonomo_exige_bloqueio_canonico_concreto_para_noop",
            "agente_leve_reutiliza_cache_negativo_causal",
            "cache_negativo_continua_restrito_a_agentes_leves",
            "lote_nao_escolhe_acao_de_agente",
            "lote_nao_cria_fato_canonico",
            "lote_nao_decide_por_ren",
            "retry_parcial_e_idempotente",
        }
        self.assertTrue(required <= set(invariants))
        self.assertTrue(all(invariants[key] for key in required))

    def test_implementacao_nao_cria_scheduler_ou_estado_paralelo(self):
        source = SOURCE.read_text(encoding="utf-8")
        self.assertIn("MAX_BATCH = 16", source)
        self.assertIn("def prepare_batch", source)
        self.assertIn("def apply_batch", source)
        self.assertNotIn("schedule.", source)
        self.assertNotIn("threading", source)
        self.assertNotIn("asyncio", source)
        self.assertNotIn("STATE_PATH =", source)


if __name__ == "__main__":
    unittest.main()
