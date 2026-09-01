from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica
import iniciativa_social
import mundo
import operacoes_concorrentes as operations
import pressao_narrativa as pressure
from tests.test_concurrent_world_operations import ConcurrentOperationFixture
from tests.test_sidequest_success_reactions import RESULT_EVIDENCE, SECOND_EVIDENCE


PRESENTED = "Homens armados fecham as duas saídas da rua."


class ReactivePressureRoutingTest(ConcurrentOperationFixture):
    def setUp(self):
        super().setUp()
        group, _ = self.materialize_group()
        self.group_id = group["grupo_operacoes_id"]
        self.commit_from_boundary(group)

    def _pending(self):
        return pressure.routable_operation_pendings(self.repo)

    def _prepared(self, *, local="rua_da_guarda"):
        payload = {
            "schema_cronica_ticket": 1,
            "preparacao_id": "turn-neutral-pressure-fixture",
            "cena": {
                "scene_id": "scene-pressure",
                "npcs": [],
                "place": local,
                "action": None,
                "tier": None,
                "danger": None,
                "context_tags": [],
                "now_minute": self.now.minute,
                "approach": {"preparacao": None, "informacao": None, "adequacao": None},
            },
        }
        token, digest = cronica.encode_ticket(payload)
        base = {
            "fase": "preparacao",
            "ticket": token,
            "ticket_id": digest,
            "fontes_lidas": [],
            "contrato_conclusao": {},
        }
        return pressure.integrate_prepare(
            self.repo,
            base,
            operation_pendings=self._pending(),
            decode_ticket=cronica.decode_ticket,
            encode_ticket=cronica.encode_ticket,
        )

    def _transaction(self, prepared, outcome="continua"):
        meta = pressure.ticket_meta(cronica.decode_ticket(prepared["ticket"]))
        return {
            "jogador": "Ren reage à situação.",
            "narracao": PRESENTED,
            "resumo": PRESENTED,
            "modo": "combate",
            "deltas": [],
            pressure.TRANSACTION_KEY: {
                "resultados": [
                {
                    "pressao_id": row["pressao_id"],
                    "resultado": outcome,
                    **(
                        {"evidencia_literal": PRESENTED}
                        if row["percepcao_estado"] != "nao_percebida_por_ren"
                        else {}
                    ),
                }
                    for row in meta["itens"]
                ]
            },
        }

    def test_operacao_comprometida_precede_social_e_nova_oportunidade(self):
        social = {
            "id": "press-social",
            "tipo": "iniciativa_social",
            "origem": {"tipo": "npc_presente", "id": "maerra"},
        }
        opportunity = {
            "id": "press-opportunity",
            "tipo": "nova_oportunidade",
            "origem": {"tipo": "oportunidade_sidequest", "id": "opp"},
        }
        operation = {
            "id": "press-operation",
            "tipo": "operacao_comprometida",
            "origem": {"tipo": "operacao_task51", "id": "attack"},
        }
        routed = pressure.sort_items([social, opportunity, operation])
        self.assertEqual([item["tipo"] for item in routed], [
            "operacao_comprometida", "nova_oportunidade", "iniciativa_social"
        ])

    def test_preparo_publico_congela_pressao_encontro_e_mecanica(self):
        prepared = self._prepared()
        items = prepared["pressao_narrativa"]["itens"]
        self.assertEqual(items[0]["tipo"], "operacao_comprometida")
        direct = next(item for item in items if item["origem"]["id"] == "ataque_comitiva")
        self.assertEqual(direct["percepcao_disponivel"]["estado"], "direta")
        self.assertTrue(direct["encontro_preparado"])
        self.assertEqual(direct["mecanica_preparada"]["modo"], "combate")
        self.assertIn(pressure.TICKET_KEY, cronica.decode_ticket(prepared["ticket"]))

    def test_runtime_legado_resolve_nome_humano_do_local_sem_inventar_tag(self):
        self.yaml(
            "runtime/cena.yaml",
            {
                "versao_runtime": 2,
                "natureza": "derivado_descartavel",
                "localizacao": {
                    "area": "Rua da Guarda, Ravens Bluff",
                    "ponto_exato": "trecho entre dois becos",
                },
            },
        )
        prepared = self._prepared(local=None)
        attack = next(
            item
            for item in prepared["pressao_narrativa"]["itens"]
            if item["origem"]["id"] == "ataque_comitiva"
        )
        self.assertEqual(attack["percepcao_disponivel"]["estado"], "direta")

    def test_pressao_bloqueante_exige_decisao_e_conversa_neutra_falha(self):
        prepared = self._prepared()
        meta = pressure.ticket_meta(cronica.decode_ticket(prepared["ticket"]))
        neutral = {
            "jogador": "Ren conversa com Maerra.",
            "narracao": "Maerra responde sobre os documentos.",
            "resumo": "A conversa continua.",
            "modo": "interação",
            "deltas": [],
        }
        with self.assertRaisesRegex(pressure.NarrativePressureError, "conversa neutra"):
            pressure.prepare_conclusion(
                self.repo, ticket_meta_value=meta, transaction=neutral
            )

    def test_bloqueio_causal_valido_adia_sem_apagar_operacao(self):
        prepared = self._prepared()
        meta = pressure.ticket_meta(cronica.decode_ticket(prepared["ticket"]))
        transaction = self._transaction(prepared)
        transaction[pressure.TRANSACTION_KEY]["resultados"] = [
            {
                "pressao_id": row["pressao_id"],
                "resultado": "adiada_por_bloqueio",
                "bloqueio": {
                    "motivo": "Uma barreira física canônica impede contato nesta fração da cena.",
                    "prova": self.proof(SECOND_EVIDENCE),
                },
            }
            for row in meta["itens"]
        ]
        plan = pressure.prepare_conclusion(
            self.repo, ticket_meta_value=meta, transaction=transaction
        )
        result = pressure.install_conclusion(self.repo, plan)
        self.assertTrue(all(item["permanece_ativa"] for item in result["resultados"]))
        self.assertEqual(len(self._pending()), 2)

    def test_pressao_continua_reaparece_no_preparo_seguinte(self):
        first = self._prepared()
        meta = pressure.ticket_meta(cronica.decode_ticket(first["ticket"]))
        plan = pressure.prepare_conclusion(
            self.repo, ticket_meta_value=meta, transaction=self._transaction(first)
        )
        pressure.install_conclusion(self.repo, plan)
        second = self._prepared()
        self.assertEqual(
            [item["id"] for item in first["pressao_narrativa"]["itens"]],
            [item["id"] for item in second["pressao_narrativa"]["itens"]],
        )

    def test_resultado_factual_resolve_somente_a_operacao_declarada(self):
        prepared = self._prepared()
        meta = pressure.ticket_meta(cronica.decode_ticket(prepared["ticket"]))
        transaction = self._transaction(prepared)
        first = transaction[pressure.TRANSACTION_KEY]["resultados"][0]
        first.update(
            {
                "resultado": "resolvida",
                "prova": self.proof(RESULT_EVIDENCE),
                "resultado_factual": "A célula abandonou a operação após resistência comprovada.",
            }
        )
        plan = pressure.prepare_conclusion(
            self.repo, ticket_meta_value=meta, transaction=transaction
        )
        pressure.install_conclusion(self.repo, plan)
        retry_plan = pressure.prepare_conclusion(
            self.repo, ticket_meta_value=meta, transaction=transaction
        )
        pressure.install_conclusion(self.repo, retry_plan)
        state = operations._load_state(self.repo)["grupos"][self.group_id]["operacoes"]
        resolved_id = meta["itens"][0]["operacao_id"]
        other_id = meta["itens"][1]["operacao_id"]
        self.assertEqual(state[resolved_id]["estado"], "resolvida")
        self.assertEqual(state[other_id]["estado"], "comprometida")

    def test_iniciativa_social_nao_fabrica_presenca_conhecimento_ou_sidequest(self):
        social = iniciativa_social.project(
            {
                "nome": "Maerra",
                "medidores": {"risco_percebido": 4},
                "identidade_relacional": "ren",
            },
            relationship_mode="alta_afinidade_alta_confianca",
        )
        absent = pressure.project_social_pressure(
            social,
            npc_id="maerra",
            presence_authorized=False,
            cause_id="fato-conhecido",
            cause_known=True,
        )
        unknown = pressure.project_social_pressure(
            social,
            npc_id="maerra",
            presence_authorized=True,
            cause_id="segredo-nao-descoberto",
            cause_known=False,
        )
        self.assertIsNone(absent)
        self.assertIsNone(unknown)
        projected = pressure.project_social_pressure(
            social,
            npc_id="maerra",
            presence_authorized=True,
            cause_id="fato-conhecido",
            cause_known=True,
        )
        self.assertNotIn("sidequest", projected)
        self.assertNotIn("acao_fisica", projected)

    def test_topico_censura_repetido_sem_fato_novo_e_suprimido(self):
        prior = pressure.authorize_censorship_topic(
            npc_id="maerra",
            topic_id="metodo_interrogatorio",
            fact_id="fato-1",
            fact_digest="a" * 64,
            previous=None,
        )
        repeated = pressure.authorize_censorship_topic(
            npc_id="maerra",
            topic_id="metodo_interrogatorio",
            fact_id="fato-1",
            fact_digest="a" * 64,
            previous=prior,
        )
        self.assertIsNone(repeated)

    def test_fato_novo_reautoriza_topico_social(self):
        prior = pressure.authorize_censorship_topic(
            npc_id="maerra", topic_id="risco", fact_id="fato-1", fact_digest="a" * 64, previous=None
        )
        current = pressure.authorize_censorship_topic(
            npc_id="maerra", topic_id="risco", fact_id="fato-2", fact_digest="b" * 64, previous=prior
        )
        self.assertEqual(current["fato_id"], "fato-2")

    def test_encontro_adulterado_falha_antes_de_validar_resultado(self):
        prepared = self._prepared()
        path = self.repo / operations._encounter_rel("ataque_comitiva")
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        doc["encontro"]["mecanica"]["surpresa"] = True
        path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        meta = pressure.ticket_meta(cronica.decode_ticket(prepared["ticket"]))
        with self.assertRaisesRegex(pressure.NarrativePressureError, "encontro congelado"):
            pressure.prepare_conclusion(
                self.repo, ticket_meta_value=meta, transaction=self._transaction(prepared)
            )

    def test_excecao_do_writer_nao_cobre_pendencia_estranha_ao_ticket(self):
        prepared = self._prepared()
        meta = pressure.ticket_meta(cronica.decode_ticket(prepared["ticket"]))
        allowed = [item["pendencia_id"] for item in meta["itens"]]
        world = mundo.load_world_state(self.repo)
        world["pendencias"].append(
            {
                "id": "mundo-9999999999999999",
                "tipo": "reavaliar_agente",
                "agente": "terceiro",
                "disparado_em": mundo.instant_parts(self.now),
                "motivo": "Outra fronteira continua sob sua autoridade própria.",
                "origem": "fixture",
            }
        )
        mundo._atomic_write_yaml(self.repo / mundo.WORLD_STATE_PATH, world)
        original = mock.Mock(side_effect=RuntimeError("barreira original preservada"))
        with self.assertRaisesRegex(RuntimeError, "preservada"):
            pressure.authorize_registration(
                self.repo,
                {},
                retry=False,
                allowed_pending_ids=allowed,
                original=original,
            )
        original.assert_called_once()

    def test_cronica_preparar_roteia_operacoes_em_vez_de_devolver_gate(self):
        result = cronica.prepare(
            self.repo,
            scene_id="scene-pressure",
            sidequest_signal=None,
        )
        self.assertEqual(result["fase"], "preparacao")
        self.assertIn("pressao_narrativa", result)
        self.assertIn(pressure.TICKET_KEY, cronica.decode_ticket(result["ticket"]))

    def test_turno_livre_nao_le_dominio_adversarial_nem_cria_rng_scheduler(self):
        with mock.patch.object(pressure.operations, "project_operation_pending") as adversarial:
            base = {
                "ticket": cronica.encode_ticket(
                    {
                        "schema_cronica_ticket": 1,
                        "preparacao_id": "turn-neutral-clean",
                        "cena": {
                            "scene_id": "clean", "npcs": [], "place": None,
                            "action": None, "tier": None, "danger": None,
                            "context_tags": [], "now_minute": None,
                            "approach": {"preparacao": None, "informacao": None, "adequacao": None},
                        },
                    }
                )[0],
                "ticket_id": "ignored",
                "fontes_lidas": [],
            }
            result = pressure.integrate_prepare(
                self.repo,
                base,
                operation_pendings=None,
                decode_ticket=cronica.decode_ticket,
                encode_ticket=cronica.encode_ticket,
            )
        adversarial.assert_not_called()
        self.assertIs(result, base)
        budget = yaml.safe_load(
            (ROOT / "baseline/reactive-pressure-routing-orcamento.yaml").read_text(encoding="utf-8")
        )["limites"]
        self.assertEqual(budget["rng_novo"], 0)
        self.assertEqual(budget["scheduler_novo"], 0)
        self.assertEqual(budget["parser_de_tom"], 0)


if __name__ == "__main__":
    unittest.main()
