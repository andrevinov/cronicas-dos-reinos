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
from ferramentas import preflight
import rules_and_character_state as rules_state


def conclusion(*, retry: bool = False) -> dict:
    return {
        "fase": "concluida",
        "ticket_id": "ticket-rm10",
        "transacao": {
            "id": "tx-rm10",
            "sessao": 21,
            "ja_registrada": retry,
            "reparo_parcial": False,
            "consolidada": False,
        },
    }


def mechanical_ticket() -> dict:
    return {
        "mecanica_cronica": {
            "regras": ["fixture_regra"],
            "obrigacoes": [
                {
                    "id": "fixture_teste",
                    "tipo": "teste",
                    "regra": "fixture_regra",
                },
                {
                    "id": "fixture_focus",
                    "tipo": "gasto_recurso",
                    "regra": "fixture_regra",
                    "recurso": "focus",
                    "custo": 1,
                },
            ],
        }
    }


def mechanical_transaction() -> dict:
    return {
        "mecanica": {
            "resolucoes": [
                {"id": "fixture_teste", "tipo": "teste", "resultado": "sucesso"},
                {"id": "fixture_focus", "tipo": "gasto_recurso", "aplicado": True},
            ]
        },
        "deltas": [
            {
                "alvo": "estado",
                "op": "inc",
                "caminho": "recursos.focus.atuais",
                "valor": -1,
            },
            {
                "alvo": "tempo",
                "op": "instante",
                "valor": {"data": "11 Eleasis, 1372 DR", "hora": "05:10"},
            },
        ],
    }


class RulesAndCharacterStateContractTest(unittest.TestCase):
    def test_catalogo_hot_path_e_preflight_publicam_um_unico_modulo(self) -> None:
        catalog = json.loads(
            (ROOT / "evaluation/catalogo-modulos-v2.json").read_text(encoding="utf-8")
        )
        module = next(item for item in catalog["modulos"] if item["id"] == rules_state.MODULE_ID)
        commands = [tuple(item.comando[1:]) for item in preflight.checks(incluir_testes=False)]

        self.assertEqual(catalog["versao_catalogo"], "2.8.0")
        self.assertEqual(module["versao_implementacao"], "1.0.0")
        self.assertEqual(
            {item["id"] for item in module["subcapacidades"]},
            set(rules_state.CAPABILITIES),
        )
        self.assertIs(cronica._rules_and_character_state, rules_state)
        self.assertEqual(
            commands.count(("ferramentas/rules_and_character_state.py", "check")),
            1,
        )

    def test_contrato_reusa_autoridades_sem_rng_writer_ou_estado_paralelo(self) -> None:
        report = rules_state.check(ROOT)
        contract = report["contrato"]

        self.assertTrue(report["ok"], report["erros"])
        self.assertFalse(contract["difficulty_changes_after_roll"])
        self.assertFalse(contract["result_changes_after_roll"])
        self.assertFalse(contract["focus_without_ticket_obligation"])
        self.assertFalse(contract["direct_live_state_write"])
        self.assertFalse(contract["guardrails_are_compensable"])
        self.assertFalse(contract["new_rng"])
        self.assertFalse(contract["new_writer"])
        self.assertFalse(contract["parallel_state"])
        self.assertEqual(contract["additional_orchestration_calls"], 0)

    def test_consistencia_compara_relacoes_vivas_sem_congelar_numeros(self) -> None:
        report = rules_state.state_consistency(ROOT)

        self.assertTrue(report["ok"], report["erros"])
        self.assertFalse(report["valores_absolutos_congelados"])
        self.assertEqual(len(report["fontes"]), 4)

    def test_hot_path_publica_depois_do_writer_e_antes_dos_recibos_externos(self) -> None:
        source = (TOOLS / "_cronica_nv14.py").read_text(encoding="utf-8")
        conclude_source = source[source.index("def conclude(") : source.index("\ndef register(")]

        self.assertLess(
            conclude_source.index("_conclude_base("),
            conclude_source.index("_rules_and_character_state.publish_conclusion"),
        )
        self.assertLess(
            conclude_source.index("_rules_and_character_state.publish_conclusion"),
            conclude_source.index("_narrative_delivery.publish_conclusion"),
        )
        self.assertLess(
            conclude_source.index("_rules_and_character_state.publish_conclusion"),
            conclude_source.index("_turn_orchestration.publish_turn"),
        )


class RulesAndCharacterStateReceiptTest(unittest.TestCase):
    def test_turno_puramente_narrativo_nao_ativa_o_modulo(self) -> None:
        source = conclusion()
        published = rules_state.publish_conclusion(
            source,
            {"narracao": "A chama oscila.", "deltas": []},
            {},
        )

        self.assertIs(published, source)
        self.assertNotIn(rules_state.RECEIPT_KEY, published)

    def test_estado_generico_do_mundo_nao_e_atribuido_ao_personagem(self) -> None:
        published = rules_state.publish_conclusion(
            conclusion(),
            {
                "deltas": [
                    {
                        "alvo": "estado",
                        "op": "set",
                        "caminho": "localizacao.local_atual",
                        "valor": "ravens_bluff",
                    }
                ]
            },
            {},
        )

        self.assertNotIn(rules_state.RECEIPT_KEY, published)

    def test_recibo_correlaciona_contrato_rolagem_recurso_e_tempo(self) -> None:
        source = conclusion()
        transaction = mechanical_transaction()
        ticket = mechanical_ticket()
        before = (copy.deepcopy(source), copy.deepcopy(transaction), copy.deepcopy(ticket))

        receipt = rules_state.publish_conclusion(source, transaction, ticket)[
            rules_state.RECEIPT_KEY
        ]

        self.assertEqual((source, transaction, ticket), before)
        self.assertEqual(receipt["correlacao"]["ticket_id"], "ticket-rm10")
        self.assertEqual(receipt["contrato"]["obrigacoes_d20"], 1)
        self.assertEqual(receipt["contrato"]["obrigacoes_recurso"], 1)
        self.assertEqual(receipt["contrato"]["recursos_aplicados"], 1)
        self.assertEqual(receipt["mutacoes"]["deltas_relevantes"], 2)
        self.assertTrue(receipt["mutacoes"]["tempo_atomico"])
        self.assertEqual(receipt["guardrails"]["roll_integrity"], "ok")
        self.assertTrue(receipt["contrato"]["validado_antes_do_writer"])
        self.assertFalse(receipt["escrita_canonica_pelo_modulo"])
        self.assertLessEqual(rules_state._size(receipt), rules_state.MAX_RECEIPT_BYTES)

    def test_retry_preserva_id_e_nao_declara_segundo_efeito(self) -> None:
        transaction = mechanical_transaction()
        ticket = mechanical_ticket()
        first = rules_state.publish_conclusion(conclusion(), transaction, ticket)[
            rules_state.RECEIPT_KEY
        ]
        replay = rules_state.publish_conclusion(
            conclusion(retry=True), transaction, ticket
        )[rules_state.RECEIPT_KEY]

        self.assertEqual(first["evento_id"], replay["evento_id"])
        self.assertEqual(first["estado"], "commit_validado")
        self.assertEqual(replay["estado"], "replay_sem_novo_efeito")
        self.assertTrue(replay["commit"]["exactly_once"])
        self.assertFalse(replay["commit"]["efeito_novo"])

    def test_observacao_pura_nao_escreve_fontes_canonicas(self) -> None:
        paths = [
            ROOT / "campanha.yaml",
            ROOT / "personagens/jogador/ficha.yaml",
            ROOT / "estado/estado-atual.yaml",
            ROOT / "estado/tempo.yaml",
        ]
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}

        rules_state.publish_conclusion(
            conclusion(), mechanical_transaction(), mechanical_ticket()
        )

        after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
