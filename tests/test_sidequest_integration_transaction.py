from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica
import oportunidades
import sidequests_integracao_runtime as integration
import test_adversarial_integrity as adversarial_cases
import test_emergent_sidequest_authoring_registry_v2 as authoring_cases
import test_quest_rewards_discoveries_losses as reward_cases
import test_sidequest_progression_deadlines_consequences as progression_cases


OFFER_EVIDENCE = (
    "Silva pede a Ren que proteja a entrega durante a janela ameaçada e deixa claro que ele pode recusar."
)


def integration_block(package: dict) -> dict:
    quest = copy.deepcopy(authoring_cases.quest_spec(package))
    return {
        "oferta": {
            "materializar": True,
            "evidencia": OFFER_EVIDENCE,
            "resumo": (
                "Silva formulou o pedido de proteção da entrega e deixou a decisão inteiramente com Ren."
            ),
        },
        "quest": quest,
        "contrato_recompensa": copy.deepcopy(reward_cases.base_contract()),
        "contrato_adversarial": copy.deepcopy(adversarial_cases.adversarial_contract(quest)),
        "contrato_progressao": copy.deepcopy(progression_cases.progression_contract()),
    }


def integration_ticket() -> str:
    payload = {
        "schema_cronica_ticket": cronica._core.SCHEMA,
        "preparacao_id": "turn-neutral-sidequest-integration",
        "cena": cronica._core._request(
            scene_id="sidequest-integration:oferta",
            npcs=[],
            place=None,
            action=None,
            tier=None,
            danger=None,
            context_tags=[],
            now=None,
            approach_preparacao=None,
            approach_informacao=None,
            approach_adequacao=None,
        ),
        integration.TICKET_KEY: {
            "schema": integration.SCHEMA,
            "sinal": {},
            "pacote_digest": "a" * 64,
        },
    }
    return cronica._core.encode_ticket(payload)[0]


class SidequestIntegrationTransactionTest(progression_cases.Task45Fixture):
    def transaction(self, *, with_sidequest: bool = True) -> dict:
        narration = (
            "Silva baixa a voz antes de explicar o risco. "
            + OFFER_EVIDENCE
            + " A decisão permanece com Ren."
        )
        tx = {
            "narracao": narration,
            "resumo": "Silva apresenta uma oferta causal de sidequest sem decidir a resposta de Ren.",
            "modo": "interacao",
            "deltas": [],
        }
        if with_sidequest:
            tx[integration.TRANSACTION_KEY] = integration_block(self.package)
        return tx

    def test_instalacao_completa_tem_um_commit_point_e_reusa_lifecycle(self):
        block = integration_block(self.package)
        plan = integration.prepare_installation(
            self.repo,
            package=self.package,
            block=block,
            offer_scene_id="sidequest-integration:oferta",
            offer_summary=block["oferta"]["resumo"],
        )
        journal = integration.begin_conclusion(
            self.repo,
            ticket_id="ticket-sidequest-integration-fixture",
            transaction=self.transaction(),
            plan=plan,
        )
        result = integration.install(self.repo, journal)
        self.assertEqual(result["resultado"], "sidequest_materializada")
        self.assertEqual(result["instalacoes_logicas"], 1)
        self.assertFalse((self.repo / integration.JOURNAL).exists())
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        mission = state["missoes"][plan["mission_id"]]
        self.assertEqual(mission["estado"], "oferecida")
        self.assertEqual(mission["origem"], "sidequest_emergente")
        self.assertEqual(mission["contrato_recompensa"], plan["reward_path"])
        self.assertEqual(mission["contrato_adversarial"], plan["adversarial_path"])
        self.assertEqual(mission["progresso_sidequest"], plan["progress_path"])
        for key in ("quest_path", "reward_path", "adversarial_path", "progress_path"):
            self.assertTrue((self.repo / plan[key]).is_file(), key)
        oportunidades.respond(self.repo, plan["mission_id"], "aceitar", now=self.now())
        accepted = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        self.assertEqual(accepted["missoes"][plan["mission_id"]]["estado"], "aceita")

    def test_retry_da_instalacao_nao_duplica_missao_ou_fragmentos(self):
        block = integration_block(self.package)
        plan = integration.prepare_installation(
            self.repo,
            package=self.package,
            block=block,
            offer_scene_id="sidequest-integration:oferta",
            offer_summary=block["oferta"]["resumo"],
        )
        journal = integration.begin_conclusion(
            self.repo,
            ticket_id="ticket-sidequest-integration-retry",
            transaction=self.transaction(),
            plan=plan,
        )
        first = integration.install(self.repo, journal)
        second = integration.install(self.repo, journal)
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        self.assertEqual(list(state["missoes"]), [plan["mission_id"]])
        self.assertEqual(first["transacao_instalacao"], second["transacao_instalacao"])
        self.assertEqual(second["arquivos_alterados"], [])
        self.assertEqual(second["instalacoes_logicas"], 1)

    def test_cronica_concluir_sem_oferta_nao_cria_quest(self):
        token = integration_ticket()
        tx = self.transaction(with_sidequest=False)
        before = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        with (
            patch.object(cronica._sidequests46, "recover_matching_journal", return_value=None),
            patch.object(cronica._sidequests46, "_plan_from_ticket", return_value=self.package),
            patch.object(
                cronica,
                "_conclude_base",
                return_value={"fase": "concluida", "sistemas_narrativos": []},
            ) as base,
            patch.object(cronica._sidequests46, "install") as install,
        ):
            result = cronica.conclude(self.repo, token, tx)
        base.assert_called_once()
        self.assertNotIn(integration.TRANSACTION_KEY, base.call_args.args[2])
        install.assert_not_called()
        after = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        self.assertEqual(before, after)
        self.assertEqual(
            result["sidequest_emergente"]["resultado"], "oferta_nao_materializada"
        )

    def test_cronica_concluir_valida_antes_do_writer_e_instala_na_mesma_chamada(self):
        token = integration_ticket()
        tx = self.transaction()
        with (
            patch.object(cronica._sidequests46, "recover_matching_journal", return_value=None),
            patch.object(cronica._sidequests46, "_plan_from_ticket", return_value=self.package),
            patch.object(
                cronica,
                "_conclude_base",
                return_value={"fase": "concluida", "sistemas_narrativos": []},
            ) as base,
        ):
            result = cronica.conclude(self.repo, token, tx)
        base.assert_called_once()
        self.assertIn(integration.TRANSACTION_KEY, tx)
        self.assertNotIn(integration.TRANSACTION_KEY, base.call_args.args[2])
        self.assertEqual(result["sidequest_emergente"]["resultado"], "sidequest_materializada")
        self.assertEqual(result["sidequest_emergente"]["instalacoes_logicas"], 1)
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        self.assertEqual(len(state["missoes"]), 1)

    def test_contrato_invalido_falha_antes_do_writer(self):
        token = integration_ticket()
        tx = self.transaction()
        tx[integration.TRANSACTION_KEY]["contrato_progressao"]["regra_sucesso"] = "percentual_75"
        with (
            patch.object(cronica._sidequests46, "recover_matching_journal", return_value=None),
            patch.object(cronica._sidequests46, "_plan_from_ticket", return_value=self.package),
            patch.object(cronica, "_conclude_base") as base,
        ):
            with self.assertRaises(cronica.CronicaError):
                cronica.conclude(self.repo, token, tx)
        base.assert_not_called()
        self.assertFalse((self.repo / integration.JOURNAL).exists())
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        self.assertEqual(state["missoes"], {})

    def test_falha_do_writer_deixa_journal_e_retry_repara_sem_duplicar(self):
        token = integration_ticket()
        tx = self.transaction()
        calls = [
            cronica.CronicaError("writer interrompido"),
            {"fase": "concluida", "sistemas_narrativos": []},
        ]
        with (
            patch.object(cronica._sidequests46, "_plan_from_ticket", return_value=self.package),
            patch.object(cronica, "_conclude_base", side_effect=calls),
        ):
            with self.assertRaises(cronica.CronicaError):
                cronica.conclude(self.repo, token, tx)
            self.assertTrue((self.repo / integration.JOURNAL).is_file())
            first_state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
            self.assertEqual(first_state["missoes"], {})
            result = cronica.conclude(self.repo, token, tx)
        self.assertFalse((self.repo / integration.JOURNAL).exists())
        self.assertEqual(result["sidequest_emergente"]["resultado"], "sidequest_materializada")
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        self.assertEqual(len(state["missoes"]), 1)


if __name__ == "__main__":
    unittest.main()
