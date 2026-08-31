from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica


class ExplicitOpportunityDecisionGateTest(unittest.TestCase):
    def test_cli_recusa_preparar_sem_decisao_explicita(self):
        parser = cronica.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["preparar", "--cena-id", "sidequest-sem-decisao"])

    def test_cli_decisoes_sao_mutuamente_exclusivas(self):
        parser = cronica.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "preparar",
                    "--cena-id",
                    "sidequest-conflito",
                    "--oportunidade-sidequest",
                    "--sem-oportunidade-sidequest",
                ]
            )

    def test_prepare_programatico_omitido_falha_antes_de_qualquer_leitura(self):
        with (
            patch.object(cronica._pending_gate, "prepare_gate") as pending,
            patch.object(cronica._hot, "prepare") as hot,
        ):
            with self.assertRaisesRegex(cronica.CronicaError, "decisão explícita"):
                cronica.prepare(ROOT, scene_id="sidequest-programatico-omitido")
        pending.assert_not_called()
        hot.assert_not_called()

    def test_decisao_negativa_preserva_hotpath_e_nao_acorda_integracao_sidequest(self):
        sentinel = {
            "schema_cronica_turno": 1,
            "fase": "preparacao",
            "ticket": "crn1.sidequest",
            "ticket_id": "sidequest",
        }
        with (
            patch.object(cronica._pending_gate, "prepare_gate", return_value=None),
            patch.object(cronica._hot, "prepare", return_value=sentinel) as hot,
            patch.object(
                cronica._sidequests46,
                "integrate_prepare",
                side_effect=AssertionError("decisão negativa não pode acordar integração de sidequest"),
            ) as emergent,
        ):
            result = cronica.prepare(
                ROOT,
                scene_id="sidequest-neutro",
                sidequest_signal=None,
            )
        self.assertIs(result, sentinel)
        hot.assert_called_once()
        emergent.assert_not_called()

    def test_oportunidade_positiva_chama_integracao_exatamente_uma_vez(self):
        base = {
            "schema_cronica_turno": 1,
            "fase": "preparacao",
            "ticket": "crn1.base",
            "ticket_id": "base",
        }
        integrated = {**base, "sidequest_emergente": {"resultado": "material_para_planejamento"}}
        signal = {
            "origem_tipo": "conversa_npc",
            "origem_id": "sidequest-maerra",
            "ancora_tipo": "necessidade",
            "ancora": "Maerra mantém sete crianças sob abrigo e Ren pergunta se ela precisa de ajuda.",
            "npc_id": "maerra_thandrel",
            "local_id": None,
            "periculosidade": "media",
            "tier": None,
        }
        with (
            patch.object(cronica._pending_gate, "prepare_gate", return_value=None),
            patch.object(cronica._hot, "prepare", return_value=base),
            patch.object(cronica._sidequests46, "integrate_prepare", return_value=integrated) as emergent,
        ):
            result = cronica.prepare(
                ROOT,
                scene_id="sidequest-maerra",
                sidequest_signal=signal,
            )
        self.assertIs(result, integrated)
        emergent.assert_called_once()
        self.assertEqual(emergent.call_args.kwargs["signal_raw"], signal)

    def test_oportunidade_incompleta_falha_antes_do_pending_gate(self):
        parser = cronica.build_parser()
        args = parser.parse_args(
            [
                "preparar",
                "--cena-id",
                "sidequest-incompleta",
                "--oportunidade-sidequest",
            ]
        )
        with (
            patch.object(cronica._pending_gate, "prepare_gate") as pending,
            patch.object(cronica._hot, "prepare") as hot,
        ):
            with self.assertRaisesRegex(cronica.CronicaError, "âncora causal completa"):
                cronica._run_turn(ROOT, args)
        pending.assert_not_called()
        hot.assert_not_called()

    def test_decisao_negativa_rejeita_campos_de_ancora(self):
        parser = cronica.build_parser()
        args = parser.parse_args(
            [
                "preparar",
                "--cena-id",
                "sidequest-negativa-com-ancora",
                "--sem-oportunidade-sidequest",
                "--sidequest-ancora",
                "isto não pode acompanhar a decisão negativa",
            ]
        )
        with self.assertRaisesRegex(cronica.CronicaError, "não podem acompanhar"):
            cronica._sidequest_signal_from_args(args)

    def test_regressao_maerra_exige_decisao_e_infere_npc_na_positiva(self):
        parser = cronica.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(
                [
                    "preparar",
                    "--cena-id",
                    "s15-maerra-sem-decisao",
                    "--npc",
                    "maerra_thandrel",
                ]
            )
        args = parser.parse_args(
            [
                "preparar",
                "--cena-id",
                "s15-maerra-com-oportunidade",
                "--npc",
                "maerra_thandrel",
                "--oportunidade-sidequest",
                "--sidequest-origem-tipo",
                "conversa_npc",
                "--sidequest-ancora-tipo",
                "necessidade",
                "--sidequest-ancora",
                "Maerra mantém sete crianças sob abrigo provisório e Ren pergunta se ela precisa de ajuda.",
            ]
        )
        signal = cronica._sidequest_signal_from_args(args)
        self.assertIsNotNone(signal)
        self.assertEqual(signal["npc_id"], "maerra_thandrel")
        self.assertEqual(signal["origem_id"], "s15-maerra-com-oportunidade")


if __name__ == "__main__":
    unittest.main()
