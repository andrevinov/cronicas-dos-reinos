from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


class CommitmentBudgetContractTest(unittest.TestCase):
    def test_contrato_congela_compromissos_compactos_sem_scheduler(self):
        data = yaml.safe_load(
            (ROOT / "baseline/compromissos-orcamento.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(data["schema_orcamento_compromissos"], 1)
        self.assertEqual(data["limites"]["max_itens_quentes"], 4)
        self.assertEqual(data["limites"]["max_fragmentos_narrativos"], 0)
        self.assertEqual(data["limites"]["escritas_extras_turno_comum"], 0)
        inv = data["invariantes"]
        self.assertTrue(inv["compromisso_e_estado_corrente_nao_scheduler"])
        self.assertTrue(inv["registro_usa_mesma_transacao_do_turno"])
        self.assertTrue(inv["situacao_temporal_e_derivada_read_only"])
        self.assertTrue(inv["janela_encerrada_nao_muta_canone"])
        self.assertTrue(inv["compromisso_pendente_visivel_em_l1_l2"])
        self.assertTrue(inv["compromisso_nao_duplica_runtime_cena"])
        self.assertTrue(inv["turno_sem_compromisso_nao_tem_leitura_extra"])


if __name__ == "__main__":
    unittest.main()
