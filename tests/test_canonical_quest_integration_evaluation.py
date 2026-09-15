from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import canonical_quest_integration as canonical


class CanonicalQuestIntegrationEvaluationTest(unittest.TestCase):
    def test_contrato_exige_recibo_e_nunca_converte_ausencia_em_nd(self) -> None:
        healthy = {"ok": True, "erros": []}
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(canonical._bridge, "check", return_value=healthy),
            patch.object(canonical._canonical, "check", return_value=healthy),
        ):
            report = canonical.check(Path(temporary))

        self.assertTrue(report["ok"])
        self.assertEqual(report["contrato"]["implementation_version"], "2.0.0")
        self.assertEqual(report["contrato"]["evaluation_version"], "4.0.0")
        self.assertTrue(
            report["contrato"]["assessment_receipt_required_per_quest_activity"]
        )
        self.assertFalse(report["contrato"]["missing_receipt_can_be_nd"])

    def test_oferta_publica_recibo_opaco_da_capacidade_reversa(self) -> None:
        offered = {
            "ok": True,
            "resultado": "oferecida",
            "missao": {"id": "sqc-identidade-interna"},
        }
        with patch.object(canonical._canonical, "offer", return_value=offered):
            result = canonical.materialize_canonical_offer(
                Path("/fixture"),
                "qsc-segredo",
                npc_id="npc",
            )

        receipt = result["avaliacoes_integracao_canonica"][0]
        self.assertEqual(receipt["capability_id"], "canon_to_quest_opportunity")
        self.assertEqual(receipt["classificacao"], "verdadeiro_positivo")
        self.assertTrue(receipt["recibo_completo"])
        self.assertNotIn("sqc-identidade-interna", json.dumps(receipt))
        self.assertNotIn("qsc-segredo", json.dumps(receipt))
        self.assertIn(
            "canonical_quest_integration.py responder",
            result["proximo_passo"],
        )

    def test_lifecycle_de_quest_canonica_emite_cobertura_sem_ledger_de_ponte(self) -> None:
        mission = {
            "id": "sqc-identidade-interna",
            "quest_id": "qsc-segredo",
            "origem": "sidequest_canonica",
            "estado": "aceita",
        }
        with patch.object(
            canonical._bridge,
            "_mission",
            return_value=({}, {}, mission),
        ):
            receipt = canonical.assess_mission(
                Path("/fixture"),
                mission["id"],
                trigger="resposta",
            )

        self.assertEqual(receipt["capability_id"], "canon_to_quest_opportunity")
        self.assertEqual(receipt["classificacao"], "indeterminado")
        self.assertFalse(receipt["incluida_na_pontuacao"])
        self.assertTrue(receipt["recibo_completo"])


if __name__ == "__main__":
    unittest.main()
