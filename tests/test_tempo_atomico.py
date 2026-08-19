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

import tempo_transacional
import transacoes
import turno


class TempoAtomicoWriterTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "runtime").mkdir(parents=True)
        (self.repo / "sessoes/003").mkdir(parents=True)
        (self.repo / "runtime/contexto.yaml").write_text(
            yaml.safe_dump(
                {
                    "sessao": {"numero": 3, "status": "em_sessao"},
                    "tempo": {"data": "10 Eleasis, 1372 DR", "hora_aproximada": "23:55"},
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (self.repo / "runtime/eventos-pendentes.jsonl").write_text("", encoding="utf-8")
        (self.repo / "sessoes/003/transcricao.md").write_text("# Sessão 003\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def tx(self, delta):
        return {
            "jogador": "Ren espera.",
            "narracao": "O tempo passa.",
            "resumo": "O tempo avança.",
            "modo": "descanso",
            "deltas": [delta],
        }

    def test_hora_com_data_embutida_falha_antes_de_qualquer_escrita(self):
        transcript = self.repo / "sessoes/003/transcricao.md"
        pending = self.repo / "runtime/eventos-pendentes.jsonl"
        before_transcript = transcript.read_bytes()
        before_pending = pending.read_bytes()

        with self.assertRaises(transacoes.TransactionError) as ctx:
            turno.register_transaction(
                self.repo,
                self.tx(
                    {
                        "alvo": "tempo",
                        "op": "set",
                        "caminho": "hora_aproximada",
                        "valor": "00:10 de 11 Eleasis",
                    }
                ),
            )

        self.assertIn("HH:MM", str(ctx.exception))
        self.assertEqual(transcript.read_bytes(), before_transcript)
        self.assertEqual(pending.read_bytes(), before_pending)

    def test_data_isolada_tambem_falha_antes_de_escrever(self):
        transcript = self.repo / "sessoes/003/transcricao.md"
        pending = self.repo / "runtime/eventos-pendentes.jsonl"
        before_transcript = transcript.read_bytes()
        before_pending = pending.read_bytes()

        with self.assertRaises(transacoes.TransactionError):
            turno.register_transaction(
                self.repo,
                self.tx(
                    {
                        "alvo": "tempo",
                        "op": "set",
                        "caminho": "data_atual",
                        "valor": "11 Eleasis, 1372 DR",
                    }
                ),
            )

        self.assertEqual(transcript.read_bytes(), before_transcript)
        self.assertEqual(pending.read_bytes(), before_pending)

    def test_instante_persistido_tem_um_unico_delta_temporal(self):
        result = turno.register_transaction(
            self.repo,
            self.tx(
                {
                    "alvo": "tempo",
                    "op": "instante",
                    "valor": {"data": "11 Eleasis, 1372 DR", "hora": "00:10"},
                }
            ),
        )
        self.assertTrue(result["evento_escrito"])
        lines = (self.repo / "runtime/eventos-pendentes.jsonl").read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        temporal = [delta for delta in record["deltas"] if delta.get("alvo") == "tempo"]
        self.assertEqual(
            temporal,
            [
                {
                    "alvo": "tempo",
                    "op": "instante",
                    "valor": {"data": "11 Eleasis, 1372 DR", "hora": "00:10"},
                }
            ],
        )

    def test_expansao_e_pura_e_nao_muta_registro_persistido(self):
        record = {
            "id": "x",
            "deltas": [
                {
                    "alvo": "tempo",
                    "op": "instante",
                    "valor": {"data": "11 Eleasis, 1372 DR", "hora": "05:10"},
                }
            ],
        }
        expanded = tempo_transacional.expand_records([record])[0]
        self.assertEqual(record["deltas"][0]["op"], "instante")
        self.assertEqual(
            [(item["caminho"], item["valor"]) for item in expanded["deltas"]],
            [
                ("data_atual", "11 Eleasis, 1372 DR"),
                ("data", "11 Eleasis, 1372 DR"),
                ("hora_aproximada", "05:10"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
