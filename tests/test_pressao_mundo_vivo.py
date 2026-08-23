from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import agentes
import barreira_mundo
import endpoints
import mundo
import pressao_ravens_bluff as pressure


class PressureWorldRepositoryTest(unittest.TestCase):
    def test_rotas_reais_validam_e_masao_empurra_crime_sem_ren(self):
        result = pressure.validate(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertGreaterEqual(result["rotas_mundo_vivo"], 1)

        candidate = pressure.candidate_for_agent(ROOT, "masao_hirasawa")
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate["linha"], "expandir_presenca_de_masao")
        self.assertEqual(candidate["metodo"], "trazer_celulas_em_lotes_pequenos")
        self.assertEqual(candidate["frente"], "crime_e_milicias")
        self.assertEqual((candidate["de"], candidate["para"]), (0, 1))
        self.assertIn("Ren não bloqueia", candidate["regra"])


class PressureWorldApplyTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        files = [
            pressure.PROFILE,
            pressure.STATE,
            agentes.INDEX_PATH,
            Path("narrador/agentes/masao_hirasawa.yaml"),
        ]
        for rel in files:
            dst = self.repo / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, dst)
        self.transaction_id = "s003-abcdef1234567890"
        ledger = self.repo / "sessoes/003/consolidacoes.jsonl"
        ledger.parent.mkdir(parents=True, exist_ok=True)
        ledger.write_text(
            json.dumps({"transacoes": [self.transaction_id]}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        self.pending = {
            "id": "mundo-1111111111111111",
            "tipo": "reavaliar_agente",
            "agente": "masao_hirasawa",
            "disparado_em": {"data": "15 Eleasis, 1372 DR", "hora": "06:00"},
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_fato_consolidado_sobe_uma_frente_e_retry_nao_duplica(self):
        first = pressure.apply_world_resolution(
            self.repo,
            self.pending,
            self.transaction_id,
            "expandir_presenca_de_masao",
            "trazer_celulas_em_lotes_pequenos",
            "Masao instalou pequenos grupos armados sob coberturas civis.",
        )
        self.assertTrue(first["alterou"])
        self.assertEqual(first["frente"], "crime_e_milicias")
        self.assertEqual((first["de"], first["para"]), (0, 1))

        state = pressure.load_state(self.repo)
        self.assertEqual(state["frentes"]["crime_e_milicias"]["nivel"], 1)
        entry = state["frentes"]["crime_e_milicias"]["historico_recente"][-1]
        self.assertEqual(entry["transacao"], self.transaction_id)
        self.assertEqual(entry["pendencia_mundo"], self.pending["id"])
        self.assertEqual(entry["agente"], "masao_hirasawa")

        retry = pressure.apply_world_resolution(
            self.repo,
            self.pending,
            self.transaction_id,
            "expandir_presenca_de_masao",
            "trazer_celulas_em_lotes_pequenos",
            "retry da mesma resolução",
        )
        self.assertFalse(retry["alterou"])
        self.assertTrue(retry["ja_aplicada"])
        self.assertEqual(
            pressure.load_state(self.repo)["frentes"]["crime_e_milicias"]["nivel"],
            1,
        )

    def test_transacao_precisa_estar_no_ledger(self):
        with self.assertRaisesRegex(pressure.PressureError, "ainda não foi consolidada"):
            pressure.apply_world_resolution(
                self.repo,
                self.pending,
                "s003-deadbeefdeadbeef",
                "expandir_presenca_de_masao",
                "trazer_celulas_em_lotes_pequenos",
                "ação ainda não consolidada",
            )
        self.assertEqual(
            pressure.load_state(self.repo)["frentes"]["crime_e_milicias"]["nivel"],
            0,
        )


class PressureWorldBarrierTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "narrador/mundo").mkdir(parents=True)
        self.pending = {
            "id": "mundo-2222222222222222",
            "tipo": "reavaliar_agente",
            "agente": "masao_hirasawa",
            "disparado_em": {"data": "15 Eleasis, 1372 DR", "hora": "06:00"},
        }
        self._write_state([self.pending])
        barreira_mundo.sync(self.repo)
        self.candidate = {
            "pendencia": self.pending["id"],
            "agente": "masao_hirasawa",
            "linha": "expandir_presenca_de_masao",
            "metodo": "trazer_celulas_em_lotes_pequenos",
            "frente": "crime_e_milicias",
            "de": 0,
            "para": 1,
        }

    def tearDown(self):
        self.temp.cleanup()

    def _write_state(self, pending):
        path = self.repo / mundo.WORLD_STATE_PATH
        path.write_text(
            yaml.safe_dump(
                {
                    "schema_estado_mundo": 1,
                    "natureza": "controle_reservado",
                    "processado_ate": {"data": "15 Eleasis, 1372 DR", "hora": "06:00"},
                    "pendencias": pending,
                    "concluidas_recentes": [],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def test_candidato_nao_pode_sumir_em_noop_generico(self):
        with patch.object(
            barreira_mundo.pressao_ravens_bluff,
            "candidate_for_pending",
            return_value=self.candidate,
        ):
            with self.assertRaisesRegex(
                barreira_mundo.WorldPendingBarrierError,
                "possui candidato autônomo",
            ):
                barreira_mundo.conclude(
                    self.repo,
                    self.pending["id"],
                    "avaliado sem mudança",
                )

            with self.assertRaisesRegex(
                barreira_mundo.WorldPendingBarrierError,
                "não bloqueia um plano autônomo",
            ):
                barreira_mundo.conclude(
                    self.repo,
                    self.pending["id"],
                    "Nenhum fato novo surgiu porque Ren não fez nada relevante.",
                    no_change=True,
                )

    def test_conclusao_com_acao_aplica_pressao_antes_de_remover_pendencia(self):
        pressure_result = {"ok": True, "alterou": True, "frente": "crime_e_milicias", "de": 0, "para": 1}
        with patch.object(
            barreira_mundo.pressao_ravens_bluff,
            "candidate_for_pending",
            return_value=self.candidate,
        ), patch.object(
            barreira_mundo.pressao_ravens_bluff,
            "apply_world_resolution",
            return_value=pressure_result,
        ) as apply:
            result = barreira_mundo.conclude(
                self.repo,
                self.pending["id"],
                "Masao colocou homens armados sob coberturas civis.",
                transaction_id="s003-abcdef1234567890",
                line_id="expandir_presenca_de_masao",
                method_id="trazer_celulas_em_lotes_pequenos",
            )

        apply.assert_called_once()
        self.assertEqual(result["pressao_ravens_bluff"], pressure_result)
        self.assertEqual(result["pendencias_restantes"], 0)
        self.assertFalse(result["barreira"]["bloqueado"])


class PressurePendingEndpointTest(unittest.TestCase):
    def test_endpoint_expoe_candidato_sem_criar_fato(self):
        candidate = {
            "pendencia": "mundo-3333333333333333",
            "agente": "masao_hirasawa",
            "linha": "expandir_presenca_de_masao",
            "metodo": "trazer_celulas_em_lotes_pequenos",
            "frente": "crime_e_milicias",
            "de": 0,
            "para": 1,
            "titulo_destino": "capangas isolados",
        }
        result = endpoints.project_pending(
            {
                "quantidade": 1,
                "pendencias": [
                    {
                        "id": candidate["pendencia"],
                        "tipo": "reavaliar_agente",
                        "agente": "masao_hirasawa",
                    }
                ],
                "fontes_lidas": ["narrador/mundo/estado.yaml"],
                "pressao_ravens_bluff": {"candidatos": [candidate]},
            }
        )
        gates = [
            gate
            for gate in result["gates"]
            if gate.get("tipo") == "pressao_ravens_bluff_autonoma"
        ]
        self.assertEqual(len(gates), 1)
        self.assertEqual(gates[0]["frente"], "crime_e_milicias")
        self.assertEqual(gates[0]["metodo"], "trazer_celulas_em_lotes_pequenos")
        self.assertFalse(result["mutante"])
        self.assertEqual(result["deltas_previstos"], [])


if __name__ == "__main__":
    unittest.main()
