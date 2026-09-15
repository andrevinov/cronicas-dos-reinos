from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica
import narrative_delivery as delivery
from ferramentas import preflight


def result(*, retry: bool = False) -> dict:
    return {
        "fase": "concluida",
        "ticket_id": "ticket-rm09",
        "transacao": {
            "id": "tx-rm09",
            "sessao": 21,
            "ja_registrada": retry,
        },
        "rodape_canonico": "RODAPE_CANONICO — fixture",
    }


class NarrativeDeliveryContractTest(unittest.TestCase):
    def test_catalogo_hot_path_e_preflight_publicam_um_unico_modulo(self) -> None:
        catalog = json.loads(
            (ROOT / "evaluation/catalogo-modulos-v2.json").read_text(encoding="utf-8")
        )
        module = next(item for item in catalog["modulos"] if item["id"] == delivery.MODULE_ID)
        commands = [tuple(item.comando[1:]) for item in preflight.checks(incluir_testes=False)]

        self.assertEqual(catalog["versao_catalogo"], "5.0.0")
        self.assertEqual(module["versao_implementacao"], "1.0.2")
        self.assertEqual(module["versao_avaliacao"], "4.0.0")
        self.assertEqual(
            {item["id"] for item in module["subcapacidades"]},
            set(delivery.CAPABILITIES),
        )
        self.assertIs(cronica._narrative_delivery, delivery)
        self.assertEqual(
            commands.count(("ferramentas/narrative_delivery.py", "check")),
            1,
        )

    def test_contrato_recusa_juiz_literario_e_escrita_canonica(self) -> None:
        report = delivery.check(ROOT)
        contract = report["contrato"]

        self.assertTrue(report["ok"], report["erros"])
        self.assertFalse(contract["automatic_literary_judge"])
        self.assertFalse(contract["short_turn_is_quality_failure"])
        self.assertFalse(contract["guardrails_are_compensable"])
        self.assertFalse(contract["rewrites_narration"])
        self.assertFalse(contract["exposes_narration_in_receipt"])
        self.assertFalse(contract["decides_for_player"])
        self.assertFalse(contract["publishes_reserved_content"])
        self.assertEqual(contract["canonical_writes"], 0)
        self.assertEqual(contract["additional_orchestration_calls"], 0)
        self.assertFalse(contract["telemetry_in_hot_path"])

    def test_hot_path_valida_antes_do_writer_e_publica_no_output_existente(self) -> None:
        source = (TOOLS / "_cronica_nv14.py").read_text(encoding="utf-8")
        conclude_source = source[source.index("def conclude(") : source.index("\ndef register(")]

        self.assertLess(
            conclude_source.index("_narrative_delivery.validate_transaction"),
            conclude_source.index("_conclude_base("),
        )
        self.assertLess(
            conclude_source.index("_narrative_delivery.publish_conclusion"),
            conclude_source.index("_turn_orchestration.publish_turn"),
        )


class NarrativeDeliveryReceiptTest(unittest.TestCase):
    def test_recibo_correlaciona_entrega_e_mede_sem_dar_nota(self) -> None:
        transaction = {
            "narracao": "A porta se abre.\n\nMECÂNICA — Percepção resolveu a incerteza.",
            "modo": "mecanico",
        }
        source = result()
        before = copy.deepcopy(source)
        published = delivery.publish_conclusion(source, transaction)
        receipt = published[delivery.RECEIPT_KEY]

        self.assertEqual(source, before)
        self.assertEqual(receipt["correlacao"]["ticket_id"], "ticket-rm09")
        self.assertEqual(receipt["correlacao"]["transacao_id"], "tx-rm09")
        self.assertEqual(receipt["estrutura"]["linhas_mecanica"], 1)
        self.assertEqual(receipt["avaliacao_semantica"], "nao_realizada")
        self.assertEqual(receipt["manifestacoes_jogador"], 0)
        self.assertFalse(receipt["guardrails_participam_media"])
        self.assertFalse(receipt["escrita_canonica_pelo_modulo"])
        self.assertLessEqual(delivery._size(receipt), delivery.MAX_RECEIPT_BYTES)

    def test_retry_preserva_id_da_entrega_e_nao_declara_nova_persistencia(self) -> None:
        transaction = {"narracao": "A chuva cessa.", "modo": "curto"}
        first = delivery.publish_conclusion(result(), transaction)[delivery.RECEIPT_KEY]
        replay = delivery.publish_conclusion(result(retry=True), transaction)[delivery.RECEIPT_KEY]

        self.assertEqual(first["entrega_id"], replay["entrega_id"])
        self.assertEqual(first["estado"], "prosa_registrada")
        self.assertEqual(replay["estado"], "replay_sem_nova_persistencia")

    def test_turno_curto_e_observado_sem_ser_penalizado(self) -> None:
        receipt = delivery.publish_conclusion(
            result(), {"narracao": "Silêncio.", "modo": "curto"}
        )[delivery.RECEIPT_KEY]

        self.assertEqual(receipt["estrutura"]["palavras"], 1)
        self.assertEqual(receipt["avaliacao_semantica"], "nao_realizada")
        self.assertNotIn("nota", receipt["estrutura"])

    def test_mecanica_precisa_permanecer_em_camada_explicita(self) -> None:
        with self.assertRaisesRegex(delivery.NarrativeDeliveryError, "mecânica explícita"):
            delivery.validate_transaction(
                {"narracao": "Ren perdeu 4 PV.", "modo": "mecanico"}
            )

    def test_classe_livre_nao_pode_inchar_o_recibo_pos_writer(self) -> None:
        receipt = delivery.publish_conclusion(
            result(),
            {"narracao": "A chama oscila.", "modo": "x" * 4_096},
        )[delivery.RECEIPT_KEY]

        self.assertEqual(receipt["classe_turno"], "nao_declarada")
        self.assertLessEqual(delivery._size(receipt), delivery.MAX_RECEIPT_BYTES)

    def test_observacao_pura_nao_altera_fontes_canonicas(self) -> None:
        paths = [ROOT / "campanha.yaml", ROOT / "estado/estado-atual.yaml"]
        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths
            if path.is_file()
        }
        delivery.publish_conclusion(result(), {"narracao": "A chama oscila."})
        after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths
            if path.is_file()
        }
        self.assertEqual(before, after)

    def test_recibo_nao_copia_prosa_agencia_ou_conteudo_reservado(self) -> None:
        narration = "A testemunha guarda a identidade reservada sem agir por Ren."
        transaction = {"narracao": narration, "modo": "interacao"}
        before = copy.deepcopy(transaction)
        receipt = delivery.publish_conclusion(result(), transaction)[delivery.RECEIPT_KEY]

        self.assertEqual(transaction, before)
        serialized = json.dumps(receipt, ensure_ascii=False)
        self.assertNotIn(narration, serialized)
        self.assertNotIn("identidade reservada", serialized)
        self.assertNotIn("acao_ren", receipt)


class NarrativeDeliveryHumanEvidenceTest(unittest.TestCase):
    def test_auditoria_separa_semantica_de_guardrails_criticos(self) -> None:
        audit = delivery.validate_semantic_audit(
            {
                "dimensoes": {
                    "progressao_jogavel": "adequado",
                    "densidade_proporcional": "adequado",
                    "voz_e_dialogo": "indeterminado",
                    "camadas_de_conhecimento": "inadequado",
                    "conclusao_aberta": "adequado",
                },
                "guardrails": {
                    "player_agency": "violado",
                    "knowledge_secrecy": "ok",
                    "roll_integrity": "ok",
                },
                "evidencias": ["Ren recebeu uma ação voluntária não declarada."],
            }
        )

        self.assertIsNone(audit["nota_literaria_automatica"])
        self.assertFalse(audit["guardrails_compensaveis"])
        self.assertEqual(audit["guardrails"]["player_agency"], "violado")

    def test_manifestacao_por_interacao_nao_vira_nota(self) -> None:
        feedback = delivery.validate_player_feedback(
            {
                "interaction_ref": "S022-I0049",
                "texto_original": "Havia uma oportunidade de iniciativa.",
                "tipo_percebido": "oportunidade_percebida",
            }
        )
        self.assertEqual(feedback["interaction_ref"], "S022-I0049")
        self.assertEqual(feedback["estado"], "pendente")
        self.assertIsNone(feedback["nota_numerica"])
        self.assertFalse(feedback["altera_guardrails"])

        with self.assertRaisesRegex(delivery.NarrativeDeliveryError, "interaction_ref"):
            delivery.validate_player_feedback(
                {
                    "interaction_ref": "turno-49",
                    "texto_original": "Sem referência estável.",
                    "tipo_percebido": "oportunidade_percebida",
                }
            )


if __name__ == "__main__":
    unittest.main()
