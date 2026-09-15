from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import interacoes_narrativas as interactions


class NarrativeInteractionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "runtime").mkdir()
        (self.repo / "runtime/contexto.yaml").write_text(
            "sessao:\n  numero: 22\n  status: em_sessao\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_reserva_retry_conclusao_e_proximo_ordinal_sao_estaveis(self) -> None:
        first = interactions.reserve(
            self.repo, interaction_class="ON", correlation_key="ticket:abc"
        )
        replay = interactions.reserve(
            self.repo, interaction_class="ON", correlation_key="ticket:abc"
        )
        self.assertEqual(first["interaction_ref"], "S022-I0001")
        self.assertEqual(replay["interaction_ref"], first["interaction_ref"])
        self.assertTrue(replay["replay"])

        completed = interactions.complete(
            self.repo,
            reference=first["interaction_ref"],
            input_text="Ren observa.",
            response_text="A rua está calma.",
            ticket_id="abc",
        )
        completed_replay = interactions.complete(
            self.repo,
            reference=first["interaction_ref"],
            input_text="Ren observa.",
            response_text="A rua está calma.",
            ticket_id="abc",
        )
        self.assertEqual(completed["state"], "complete")
        self.assertTrue(completed_replay["replay"])

        second = interactions.reserve(
            self.repo, interaction_class="ON", correlation_key="ticket:abc"
        )
        self.assertEqual(second["interaction_ref"], "S022-I0001")
        next_input = interactions.reserve(
            self.repo, interaction_class="ON", correlation_key="ticket:def"
        )
        self.assertEqual(next_input["interaction_ref"], "S022-I0002")

    def test_retry_divergente_falha_sem_reescrever_o_par(self) -> None:
        reserved = interactions.reserve(
            self.repo, interaction_class="OFF", correlation_key="off:1"
        )
        interactions.complete(
            self.repo,
            reference=reserved["interaction_ref"],
            input_text="[Pergunta]",
            response_text="[Resposta]",
        )
        with self.assertRaisesRegex(interactions.InteractionError, "diverge"):
            interactions.complete(
                self.repo,
                reference=reserved["interaction_ref"],
                input_text="[Pergunta alterada]",
                response_text="[Resposta]",
            )

    def test_troca_off_recebe_marcador_e_nao_guarda_prosa(self) -> None:
        receipt = interactions.record_exchange(
            self.repo,
            interaction_class="OFF",
            input_text="[Como funciona?]",
            response_text="[Assim.]",
        )
        self.assertEqual(receipt["visible_marker"], "INTERAÇÃO — S022-I0001")
        serialized = json.dumps(interactions.load_events(self.repo, 22), ensure_ascii=False)
        self.assertNotIn("Como funciona?", serialized)
        self.assertNotIn("Assim.", serialized)

    def test_manifestacao_preserva_original_e_adjudicacao_em_nova_linha(self) -> None:
        exchange = interactions.record_exchange(
            self.repo,
            interaction_class="OFF",
            input_text="[pergunta]",
            response_text="[resposta]",
        )
        feedback = interactions.record_player_feedback(
            self.repo,
            interaction_ref=exchange["interaction_ref"],
            original_text="Havia oportunidade para um NPC agir.",
            perceived_type="oportunidade_percebida",
            impact="alto",
        )
        interactions.adjudicate_feedback(
            self.repo,
            feedback_id=feedback["feedback_id"],
            state="confirmada",
            reason="Presença e janela social estavam comprovadas.",
            module_id="npc_continuity_and_social_behavior",
            capability_id="social_initiative",
            confidence="alta",
            evidence=["elenco consolidado"],
        )
        item = interactions.materialize(self.repo, 22)["player_feedback"][0]
        self.assertEqual(item["original_text"], "Havia oportunidade para um NPC agir.")
        self.assertEqual(item["adjudication"]["state"], "confirmada")
        self.assertEqual(
            item["system_suggestion"]["module_id"],
            "npc_continuity_and_social_behavior",
        )

    def test_rodape_mantem_referencia_na_ultima_linha(self) -> None:
        footer = interactions.append_footer(
            "RODAPE_CANONICO — 1 de Eleasis · 08:00", "S022-I0049"
        )
        self.assertEqual(
            footer,
            "RODAPE_CANONICO — 1 de Eleasis · 08:00 · Interação S022-I0049",
        )

    def test_integracao_so_ativa_com_catalogo_rm11_instalado(self) -> None:
        payload = {"ticket_id": "ticket-sem-rm11"}
        self.assertIs(interactions.attach_prepare(self.repo, payload), payload)
        self.assertFalse(interactions.ledger_path(self.repo, 22).exists())

    def test_preparar_concluir_e_retry_propagam_a_mesma_referencia_on(self) -> None:
        source = ROOT / "evaluation/catalogo-modulos-v2.json"
        target = self.repo / "evaluation/catalogo-modulos-v2.json"
        target.parent.mkdir()
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        prepared = interactions.attach_prepare(self.repo, {"ticket_id": "ticket-on"})
        reference = prepared["interacao"]["interaction_ref"]
        self.assertLessEqual(
            len(json.dumps(prepared["interacao"], ensure_ascii=False).encode("utf-8")),
            interactions.PREPARE_RECEIPT_RESERVE_BYTES,
        )
        transaction = {"jogador": "Ren observa.", "narracao": "A rua está calma."}
        result = {
            "transacao": {"id": "tx-on", "sessao": 22, "ja_registrada": False},
            "rodape_canonico": "RODAPE_CANONICO — ok",
        }
        completed = interactions.attach_conclusion(
            self.repo, result, transaction, ticket_id="ticket-on"
        )
        replay = interactions.attach_conclusion(
            self.repo,
            {**result, "transacao": {**result["transacao"], "ja_registrada": True}},
            transaction,
            ticket_id="ticket-on",
        )

        self.assertEqual(completed["interacao"]["interaction_ref"], reference)
        self.assertEqual(replay["interacao"]["interaction_ref"], reference)
        self.assertTrue(replay["interacao"]["replay"])
        self.assertEqual(completed["rodape_canonico"].count(reference), 1)

    def test_snapshot_de_release_impede_reescrita_historica_de_versao(self) -> None:
        source = ROOT / "evaluation/catalogo-modulos-v2.json"
        target = self.repo / "evaluation/catalogo-modulos-v2.json"
        target.parent.mkdir()
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
        exchange = interactions.record_exchange(
            self.repo,
            interaction_class="OFF",
            input_text="[Versão?]",
            response_text="[Versão vigente preservada.]",
        )

        changed = json.loads(target.read_text(encoding="utf-8"))
        changed["modulos"][0]["versao_implementacao"] = "9.0.0"
        target.write_text(json.dumps(changed), encoding="utf-8")
        materialized = interactions.materialize(self.repo, 22)
        item = next(
            value for value in materialized["interactions"]
            if value["interaction_ref"] == exchange["interaction_ref"]
        )

        self.assertEqual(
            item["module_versions"]["context_and_memory"]["implementation_version"],
            "1.0.2",
        )


if __name__ == "__main__":
    unittest.main()
