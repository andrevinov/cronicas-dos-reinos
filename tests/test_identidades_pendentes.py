from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import identidades
import transacoes


class PendingIdentityEvidenceTest(unittest.TestCase):
    def test_segunda_pista_parte_do_overlay_ainda_nao_consolidado(self):
        first = identidades.propose_evidence(
            ROOT,
            npc="Kethra",
            observed="kage",
            possible="ren",
            evidence_type="fisica",
            fact="Kethra percebeu que Kage repete a mesma marca fina junto ao maxilar que havia visto em Ren.",
            source="teste:pendente-1",
            actor_result="nao_aplicavel",
        )
        self.assertEqual(first["resultado"], "registrar_delta")
        pending = [
            {
                "versao": transacoes.SCHEMA_VERSION,
                "id": "tx-pista-pendente-1",
                "sessao": 999,
                "resumo": "Kethra reuniu uma primeira pista sobre Kage.",
                "deltas": [first["delta"]],
            }
        ]
        with mock.patch.object(transacoes, "load_pending", return_value=pending):
            second = identidades.propose_evidence(
                ROOT,
                npc="Kethra",
                observed="kage",
                possible="ren",
                evidence_type="contextual",
                fact="Kage conhecia um detalhe da fuga de Colm que Kethra havia transmitido somente a Ren.",
                source="teste:pendente-2",
                actor_result="nao_aplicavel",
            )
        self.assertEqual(second["resultado"], "registrar_delta")
        projection = second["projecao_depois"]
        self.assertEqual(projection["suspeitas"][0]["grau"], "suspeita")
        self.assertEqual(projection["suspeitas"][0]["evidencias"], 2)

    def test_validacao_de_lote_sem_delta_nao_le_registro(self):
        records = [{"id": "tx-comum", "deltas": []}]
        with mock.patch.object(identidades, "load_registry", side_effect=AssertionError("não deve ler")):
            self.assertEqual(identidades.validate_batch(Path("/tmp/sem-registro"), records), 0)


if __name__ == "__main__":
    unittest.main()
