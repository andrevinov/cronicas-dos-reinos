from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica_pending_gate


class CronicaPendingGateBudgetTest(unittest.TestCase):
    def test_contrato_congela_custo_e_invariantes(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/pending-gate-cronica-preparar-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(contract["schema_orcamento_pending_gate_cronica"], 1)
        self.assertEqual(contract["natureza"], "contrato_de_regressao")
        limits = contract["limites"]
        self.assertEqual(limits["max_leituras_caminho_livre"], 1)
        self.assertEqual(limits["max_leituras_caminho_bloqueado"], 2)
        self.assertEqual(
            limits["max_saida_bloqueada_bytes"],
            cronica_pending_gate.MAX_BLOCKED_OUTPUT_BYTES,
        )
        self.assertEqual(limits["max_escritas_preparar"], 0)
        self.assertEqual(limits["max_chamadas_hotpath_quando_bloqueado"], 0)
        self.assertEqual(limits["max_tickets_emitidos_quando_bloqueado"], 0)
        self.assertEqual(limits["max_endpoints_novos"], 0)
        self.assertEqual(limits["max_schedulers_novos"], 0)
        self.assertEqual(limits["max_estados_novos"], 0)
        self.assertEqual(limits["max_scans_repo"], 0)
        required = {
            "gate_roda_antes_da_preparacao_de_cena",
            "caminho_livre_preserva_saida_da_task21",
            "caminho_livre_le_somente_marcador",
            "marcador_bloqueado_confirma_estado_autoritativo",
            "confirmacao_bloqueada_e_read_only",
            "marcador_stale_bloqueado_nao_cria_deadlock",
            "bloqueio_nao_emite_ticket",
            "task23_permanece_autoridade_de_resolucao_em_lote",
            "cronica_preparar_nao_resolve_pendencias",
            "cronica_concluir_nao_resolve_pendencias",
            "writer_mantem_barreira_como_defesa_final",
        }
        invariants = contract["invariantes"]
        self.assertTrue(required <= set(invariants))
        self.assertTrue(all(invariants[key] for key in required))

    def test_roteador_remove_leitura_manual_e_mantem_task23_como_proximo_passo(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("Barreira de pendências vive dentro de `cronica preparar`", text)
        self.assertIn("fase: bloqueada_pendencias_mundo", text)
        self.assertIn("resolver_fronteira.py preparar", text)
        self.assertIn("resolver_fronteira.py aplicar", text)
        self.assertIn("O writer repete a trava", text)
        self.assertNotIn(
            "Antes de novo ON, ler `runtime/mundo-pendencias.yaml`",
            text,
        )
        self.assertLessEqual((ROOT / "AGENTS.md").stat().st_size, 13312)


if __name__ == "__main__":
    unittest.main()
