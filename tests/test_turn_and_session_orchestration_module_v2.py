from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml


ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica
from ferramentas import preflight
import turn_and_session_orchestration as orchestration


class TurnAndSessionOrchestrationContractTest(unittest.TestCase):
    def test_catalogo_fachada_e_preflight_publicam_um_unico_pai(self) -> None:
        catalog = json.loads(
            (ROOT / "evaluation/catalogo-modulos-v2.json").read_text(encoding="utf-8")
        )
        module = next(
            item for item in catalog["modulos"] if item["id"] == orchestration.MODULE_ID
        )
        commands = [
            tuple(item.comando[1:])
            for item in preflight.checks(incluir_testes=False)
        ]

        self.assertEqual(catalog["versao_catalogo"], "5.0.0")
        self.assertEqual(module["versao_implementacao"], "1.0.2")
        self.assertEqual(module["versao_avaliacao"], "4.0.0")
        self.assertEqual(
            {item["id"] for item in module["subcapacidades"]},
            set(orchestration.CAPABILITIES),
        )
        self.assertIs(cronica._turn_orchestration, orchestration)
        self.assertEqual(
            commands.count(
                ("ferramentas/turn_and_session_orchestration.py", "check")
            ),
            1,
        )
        self.assertFalse(preflight._ORCHESTRATION_INTERNAL_CHECKS & set(commands))

    def test_contrato_nao_cria_writer_estado_ou_chamada_ritual(self) -> None:
        report = orchestration.check(ROOT)
        contract = report["contrato"]

        self.assertFalse(contract["parallel_state"])
        self.assertFalse(contract["parallel_writer"])
        self.assertFalse(contract["telemetry_in_hot_path"])
        self.assertFalse(contract["checkpoint_required_each_turn"])
        self.assertEqual(contract["additional_orchestration_calls"], 0)
        self.assertEqual(contract["primary_turn_calls"], ["preparar", "concluir"])
        self.assertEqual(
            contract["checkpoint_order"],
            ["canonico", "ciclo", "mundo", "memoria"],
        )


class CorrelatedTurnReceiptTest(unittest.TestCase):
    def prepared(self) -> dict:
        return {
            "schema_cronica_turno": 1,
            "fase": "preparacao",
            "ticket_id": "ticket-rm08",
            "ticket": "crn1.ticket-rm08.fixture",
            "ids": {"cena": "cena-rm08", "preparacao": "prep-rm08"},
        }

    def concluded(self, *, retry: bool = False, repaired: bool = False) -> dict:
        return {
            "schema_cronica_turno": 1,
            "fase": "concluida",
            "ticket_id": "ticket-rm08",
            "cena": {"id": "cena-rm08", "preparacao_id": "prep-rm08"},
            "transacao": {
                "id": "tx-rm08",
                "sessao": 21,
                "ja_registrada": retry,
                "reparo_parcial": repaired,
                "consolidada": False,
            },
        }

    def test_turno_neutro_tem_duas_posicoes_e_correlacao_estavel(self) -> None:
        prepared = orchestration.publish_turn(self.prepared(), "preparar")
        # Uma rolagem material pode ocorrer aqui; ela não altera o recibo nem o ticket.
        concluded = orchestration.publish_turn(self.concluded(), "concluir")
        first = prepared[orchestration.RECEIPT_KEY]
        second = concluded[orchestration.RECEIPT_KEY]

        self.assertEqual(first["fluxo"]["posicao"], 1)
        self.assertEqual(second["fluxo"]["posicao"], 2)
        self.assertEqual(first["fluxo"]["chamadas_primarias_esperadas"], 2)
        self.assertEqual(first["correlacao"]["ticket_id"], second["correlacao"]["ticket_id"])
        self.assertEqual(first["correlacao"]["preparacao_id"], second["correlacao"]["preparacao_id"])
        self.assertTrue(second["commit"]["exactly_once"])
        self.assertEqual(second["commit"]["resultado"], "commit_exatamente_uma_vez")

    def test_retry_e_reparo_nao_declaram_segundo_efeito(self) -> None:
        replay = orchestration.publish_turn(
            self.concluded(retry=True), "concluir"
        )[orchestration.RECEIPT_KEY]
        repaired = orchestration.publish_turn(
            self.concluded(repaired=True), "concluir"
        )[orchestration.RECEIPT_KEY]

        self.assertEqual(replay["commit"]["resultado"], "replay_sem_duplicacao")
        self.assertFalse(replay["commit"]["efeito_novo"])
        self.assertFalse(replay["commit"]["duplicado"])
        self.assertEqual(
            repaired["commit"]["resultado"],
            "reparo_recuperado_sem_duplicacao",
        )
        self.assertFalse(repaired["commit"]["efeito_novo"])
        self.assertFalse(repaired["efeito_materializado"])

    def test_journal_interrompido_bloqueia_preparo_antes_do_hotpath(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            journal = repo / orchestration._consolidation.JOURNAL_PATH
            journal.parent.mkdir(parents=True)
            journal.write_text(
                json.dumps({"tipo": "inicio_sessao"}),
                encoding="utf-8",
            )
            before = journal.read_bytes()

            with mock.patch.object(cronica._hot, "prepare") as hot:
                result = cronica.prepare(repo, scene_id="cena-bloqueada")

            hot.assert_not_called()
            self.assertEqual(result["fase"], "bloqueada_recuperacao_sessao")
            self.assertFalse(result["disponibilidade"]["narracao"])
            self.assertNotIn("ticket", result)
            self.assertEqual(
                result["orquestracao"]["estado"], "bloqueado_recuperacao"
            )
            self.assertIn("cronica sessao recuperar", result["proximo_passo"]["comando"])
            self.assertEqual(journal.read_bytes(), before)

    def test_lifecycle_publica_recibo_sem_transformar_checkpoint_em_turno(self) -> None:
        raw = {
            "schema_cronica_sessao": 1,
            "fase": "checkpoint",
            "sessao": 21,
            "canonico": {"sem_pendencias": True},
            "ciclo": {},
            "mundo": {},
            "memoria": {},
        }
        with mock.patch.object(
            cronica.ciclo_cronica, "session_checkpoint", return_value=raw
        ) as checkpoint:
            result = cronica._run_session(ROOT, "checkpoint")

        checkpoint.assert_called_once_with(ROOT)
        receipt = result["orquestracao"]
        self.assertEqual(receipt["unidade"], "sessao")
        self.assertEqual(receipt["estado"], "checkpoint_concluido")
        self.assertTrue(receipt["ordem_canonica_preservada"])
        self.assertFalse(receipt["checkpoint_por_turno"])

    def test_recibo_compacto_cabe_na_reserva_de_preparo(self) -> None:
        out = orchestration.publish_turn(self.prepared(), "preparar")
        receipt = out[orchestration.RECEIPT_KEY]
        self.assertLessEqual(orchestration._size(receipt), orchestration.MAX_RECEIPT_BYTES)
        self.assertLessEqual(
            len(yaml.safe_dump(receipt, allow_unicode=True).encode("utf-8")),
            orchestration.RECEIPT_RESERVE_BYTES,
        )


if __name__ == "__main__":
    unittest.main()
