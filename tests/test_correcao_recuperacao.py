from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import correcao
import transacoes


class CorrectionTerminalRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "runtime").mkdir(parents=True)
        (self.repo / "sessoes/003").mkdir(parents=True)
        self._runtime("em_sessao")

    def tearDown(self):
        self.temp.cleanup()

    def _runtime(self, status: str) -> None:
        (self.repo / "runtime/contexto.yaml").write_text(
            yaml.safe_dump(
                {
                    "sessao": {"numero": 3, "status": status},
                    "tempo": {"data": "7 Eleasis, 1372 DR", "hora_aproximada": "08:03"},
                    "localizacao": {"area": "teste", "ponto_exato": "teste"},
                    "recursos": {
                        "pv": {"atuais": 45, "maximos": 45},
                        "ki": {"atuais": 5, "maximos": 6},
                    },
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def test_retry_pos_auditoria_limpa_journal_terminal(self):
        target = "tx-alvo"
        payload = {
            "motivo": "erro factual",
            "retificacao": "o fato correto substitui a versão anterior",
            "resumo": "retificação de regressão",
            "deltas": [
                {"alvo": "estado", "op": "set", "caminho": "localizacao.area", "valor": "correto"}
            ],
            "invalidar_mapas": [],
        }
        normalized = correcao._normalize_payload(payload)
        cid = correcao._correction_id(3, target, normalized)
        audit = {
            "schema_correcao_canonica": 1,
            "natureza": "auditoria_retificacao",
            "id": cid,
            "corrige": target,
            "transacao_corretiva": cid,
            "sessao": 3,
            "alvo_estado_antes": "consolidada",
            "motivo": normalized["motivo"],
            "retificacao": normalized["retificacao"],
            "resumo": normalized["resumo"],
            "deltas_corretivos": 1,
            "mapas_invalidados": [],
            "nao_e_evento_novo": True,
        }
        (self.repo / "sessoes/003/correcoes.jsonl").write_text(
            json.dumps(audit, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        (self.repo / correcao.JOURNAL).write_text(
            json.dumps(
                {
                    "schema_correcao_em_andamento": 1,
                    "natureza": "journal_recuperavel",
                    "id": cid,
                    "corrige": target,
                    "payload_hash": correcao._payload_hash(target, normalized),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

        result = correcao.apply_correction(self.repo, target, "corr-prep-antiga", payload)
        self.assertTrue(result["ja_aplicada"])
        self.assertFalse((self.repo / correcao.JOURNAL).exists())

    def test_check_continua_valido_entre_sessoes(self):
        self._runtime("entre_sessoes")
        cid = "corr-s003-1234567890abcdef"
        target = "tx-alvo"
        (self.repo / "sessoes/003/transcricao.md").write_text(
            "# Sessão 003\n\n"
            + transacoes.transaction_marker(target)
            + "\ntexto original\n\n"
            + transacoes.transaction_marker(cid)
            + "\nCORREÇÃO CANÔNICA\n",
            encoding="utf-8",
        )
        (self.repo / "sessoes/003/consolidacoes.jsonl").write_text(
            json.dumps({"id": "batch-1", "transacoes": [target, cid]}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        audit = {
            "schema_correcao_canonica": 1,
            "natureza": "auditoria_retificacao",
            "id": cid,
            "corrige": target,
            "transacao_corretiva": cid,
            "sessao": 3,
            "alvo_estado_antes": "consolidada",
            "motivo": "erro",
            "retificacao": "correto",
            "resumo": "correção",
            "deltas_corretivos": 1,
            "mapas_invalidados": [],
            "nao_e_evento_novo": True,
        }
        (self.repo / "sessoes/003/correcoes.jsonl").write_text(
            json.dumps(audit, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        self.assertEqual(correcao.check(self.repo), {"ok": True, "erros": []})


class CorrectionBudgetContractTest(unittest.TestCase):
    def test_contrato_congela_correcao_fora_do_hot_path(self):
        budget = yaml.safe_load(
            (ROOT / "baseline/mundo-vivo-integracao-orcamento.yaml").read_text(encoding="utf-8")
        )
        correction = budget["limites"]["correcao_canonica"]
        self.assertEqual(correction["preparacao_escritas"], 0)
        self.assertEqual(correction["max_mapas_invalidados"], 4)
        self.assertTrue(correction["somente_ponta_causal"])
        self.assertEqual(correction["deltas_automaticos"], ["set", "remove"])
        self.assertFalse(correction["scheduler_novo"])
        invariants = budget["invariantes"]
        self.assertTrue(invariants["correcao_canonica_fora_do_hot_path"])
        self.assertTrue(invariants["correcao_canonica_nao_e_evento_novo"])
        self.assertTrue(invariants["correcao_antiga_exige_replay_manual"])
        self.assertTrue(invariants["mapa_descoberto_nao_e_invalidado_automaticamente"])


if __name__ == "__main__":
    unittest.main()
