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

import barreira_mundo
import mundo
import operacoes_concorrentes as operations
import reacoes_sidequest as reactions
import resolver_fronteira
from tests.test_sidequest_success_reactions import (
    ACTOR_ID,
    FACT_EVIDENCE,
    FACT_ID,
    KNOWLEDGE_EVIDENCE,
    RESULT_EVIDENCE,
    SECOND_EVIDENCE,
    SECOND_FACT_ID,
    SidequestReactionFixture,
)


CHANNEL_EVIDENCE = "Um mensageiro da rede possui rota e instruções para levar o aviso até Ren."


class ConcurrentOperationFixture(SidequestReactionFixture):
    def setUp(self):
        super().setUp()
        facts = self.repo / "sessoes/001/fatos.md"
        facts.write_text(facts.read_text(encoding="utf-8") + CHANNEL_EVIDENCE + "\n", encoding="utf-8")
        self.threat_classification = "alta"
        self.patchers = [
            mock.patch.object(operations.adversarios, "load_index", return_value={}),
            mock.patch.object(operations.adversarios, "resolve_adversary", side_effect=self._resolve_adversary),
            mock.patch.object(operations.adversarios, "load_adversary", side_effect=self._load_adversary),
            mock.patch.object(operations.adversarios, "load_specialty", side_effect=self._load_specialty),
            mock.patch.object(operations.ameacas, "evaluate", side_effect=self._evaluate_threat),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        super().tearDown()

    @staticmethod
    def _canonical_adversary(query: str) -> str:
        return {
            "capanga": "capanga_cinzento",
            "capanga cinzento": "capanga_cinzento",
            "brutamontes": "brutamontes_cinzento",
        }.get(query.casefold(), query.casefold().replace(" ", "_"))

    def _resolve_adversary(self, _index, query):
        canonical = self._canonical_adversary(query)
        return canonical, {"id": canonical}

    def _load_adversary(self, _repo, query):
        return {"adversario_id": self._canonical_adversary(query), "fontes_lidas": []}

    def _load_specialty(self, _repo, adversary_id, specialty_id):
        return {
            "adversario_id": adversary_id,
            "especialidade_id": specialty_id,
            "fontes_lidas": [],
        }

    def _evaluate_threat(self, *_args, **_kwargs):
        return {
            "resultado": {"classificacao": self.threat_classification},
            "fontes_lidas": [],
        }

    @staticmethod
    def proof(evidence=FACT_EVIDENCE):
        return {"fonte": "sessoes/001/fatos.md", "evidencia": evidence}

    def mechanics(self, *, target="ren", routes=None, composition=None, mode="combate"):
        if mode == "nenhuma":
            reference = None
            composition = []
        else:
            reference = "capanga"
            composition = composition or [
                {
                    "adversario": "capanga",
                    "quantidade": 2,
                    "papel": "combatente",
                    "especialidade_id": None,
                }
            ]
        return {
            "modo": mode,
            "alvo": target,
            "nivel_alvo": 7,
            "recursos_alvo": "plenos",
            "prova_alvo": self.proof(),
            "adversario_referencia": reference,
            "composicao": composition,
            "aliados_presentes": [],
            "terreno": "adversario",
            "iniciativa": "neutra",
            "surpresa": False,
            "objetivo_tatico": "Fixar defensores enquanto a célula cumpre o objetivo material.",
            "rotas_retirada": routes if routes is not None else [
                {
                    "descricao": "Beco lateral conectado a uma rua ainda livre.",
                    "perceptibilidade": "perceptivel",
                    "condicao": "A saída permanece aberta enquanto o beco não for bloqueado.",
                }
            ],
            "capacidade_exclusiva": False,
        }

    def _reactions(self):
        first = self.materialize()
        second_alt = self.alternative(
            alternative_id="extracao_furtiva",
            capability="extrair_registro",
            target_id="testemunha_segura",
            target_type="informacao",
            resource="equipe de extração",
            group="extracao",
        )
        second = self.materialize(
            self.proposal(fact_id=SECOND_FACT_ID, alternatives=[second_alt])
        )
        return first["reaction_id"], second["reaction_id"]

    def group_proposal(self, *, same_cell=False, channels=True):
        first, second = self._reactions()
        operation_a = {
            "id": "ataque_comitiva",
            "reaction_id": first,
            "alternative_id": "ordem_contraditoria",
            "alvo": {"id": "arquivo_publico", "tipo": "informacao"},
            "local": "rua_da_guarda",
            "objetivo": "Tomar a matriz documental durante a distração.",
            "celula_id": "celula_rua",
            "atores": [ACTOR_ID],
            "recursos": ["célula documental"],
            "dependencias": ["A comitiva ainda transporta a matriz documental."],
            "bloqueios_causais": ["A matriz deixa a comitiva antes do ataque."],
            "sinais_perceptiveis": ["Homens armados fecham as duas saídas da rua."],
            "mecanica": self.mechanics(),
        }
        operation_b = {
            "id": "extracao_testemunha",
            "reaction_id": second,
            "alternative_id": "extracao_furtiva",
            "alvo": {"id": "testemunha_segura", "tipo": "informacao"},
            "local": "casa_do_alvorecer",
            "objetivo": "Extrair a testemunha antes que ela seja interrogada.",
            "celula_id": "celula_rua" if same_cell else "celula_templo",
            "atores": [ACTOR_ID],
            "recursos": ["equipe de extração"],
            "dependencias": ["A testemunha permanece no abrigo protegido."],
            "bloqueios_causais": ["A testemunha é removida antes da janela comum."],
            "sinais_perceptiveis": ["Uma janela dos fundos é forçada por uma lâmina fina."],
            "mecanica": self.mechanics(target="guardas_do_templo"),
        }
        channel_rows = []
        if channels:
            channel_rows = [
                {
                    "id": "visao_comitiva",
                    "tipo": "percepcao_direta",
                    "operacao_origem": "ataque_comitiva",
                    "destinatario": "ren",
                    "atraso_minutos": 0,
                    "conhecimentos_permitidos": ["A comitiva está sob ataque na rua da guarda."],
                    "prova_disponibilidade": self.proof(KNOWLEDGE_EVIDENCE),
                },
                {
                    "id": "mensageiro_templo",
                    "tipo": "mensageiro",
                    "operacao_origem": "extracao_testemunha",
                    "destinatario": "ren",
                    "atraso_minutos": 12,
                    "conhecimentos_permitidos": [
                        "A casa do alvorecer foi atacada.",
                        "A testemunha ainda estava viva quando o mensageiro partiu.",
                    ],
                    "prova_disponibilidade": self.proof(CHANNEL_EVIDENCE),
                },
            ]
        return {
            "janela": {
                "minimo": mundo.instant_parts(self.now),
                "maximo": mundo.instant_parts(mundo.WorldInstant(self.now.minute + 120)),
                "condicao": "As duas células recebem o sinal combinado dentro da mesma janela.",
            },
            "simultaneidade": "As células iniciam suas operações sem esperar a escolha ou presença de Ren.",
            "operacoes": [operation_b, operation_a],
            "canais": channel_rows,
            "motivo": "Duas células e recursos distintos permitem pressão simultânea causal.",
        }

    def materialize_group(self, proposal=None):
        proposal = proposal or self.group_proposal()
        prepared = operations.prepare(self.repo, proposal)
        result = operations.materialize(self.repo, proposal, prepared["preparacao_id"])
        return result, proposal

    def commit_from_boundary(self, result, blockers=None):
        batch = resolver_fronteira.prepare_batch(self.repo)
        item = next(row for row in batch["itens"] if row.get("grupo_operacoes_id") == result["grupo_operacoes_id"])
        return resolver_fronteira.apply_batch(
            self.repo,
            {
                "lote_id": batch["lote_id"],
                "grupos_operacoes": [
                    {"id": item["id"], "token": item["token"], "bloqueios": blockers or {}}
                ],
            },
        )


class ConcurrentCommitTest(ConcurrentOperationFixture):
    def test_duas_frentes_independentes_sao_comprometidas_no_mesmo_lote(self):
        group, _ = self.materialize_group()
        applied = self.commit_from_boundary(group)
        result = applied["grupos_comprometidos"][0]
        self.assertEqual(result["operacoes_comprometidas"], ["ataque_comitiva", "extracao_testemunha"])
        state = operations._load_state(self.repo)
        self.assertEqual(len(state["reservas_exclusivas"]), 4)
        self.assertEqual(
            {item["tipo"] for item in mundo.load_world_state(self.repo)["pendencias"]},
            {"resolver_operacao_adversarial"},
        )

    def test_recurso_fisico_repetido_falha_antes_de_qualquer_efeito(self):
        proposal = self.group_proposal(same_cell=True)
        world_before = mundo.load_world_state(self.repo)
        with self.assertRaisesRegex(operations.ConcurrentOperationError, "duplicada"):
            operations.prepare(self.repo, proposal)
        self.assertEqual(mundo.load_world_state(self.repo), world_before)
        self.assertFalse((self.repo / operations.INDEX).exists())

    def test_bloqueio_causal_remove_so_a_operacao_afetada(self):
        group, _ = self.materialize_group()
        blockers = {
            "ataque_comitiva": {
                "motivo": "A matriz saiu da comitiva antes do início da janela compartilhada.",
                "prova": self.proof(SECOND_EVIDENCE),
            }
        }
        result = self.commit_from_boundary(group, blockers)["grupos_comprometidos"][0]
        self.assertEqual(result["operacoes_bloqueadas"], ["ataque_comitiva"])
        self.assertEqual(result["operacoes_comprometidas"], ["extracao_testemunha"])
        state = operations._load_state(self.repo)["grupos"][group["grupo_operacoes_id"]]["operacoes"]
        self.assertEqual(state["ataque_comitiva"]["estado"], "bloqueada")
        self.assertEqual(state["extracao_testemunha"]["estado"], "comprometida")

    def test_retry_do_lote_nao_duplica_encontro_reserva_ou_conclusao(self):
        group, _ = self.materialize_group()
        batch = resolver_fronteira.prepare_batch(self.repo)
        item = next(row for row in batch["itens"] if row.get("grupo_operacoes_id") == group["grupo_operacoes_id"])
        payload = {
            "lote_id": batch["lote_id"],
            "grupos_operacoes": [{"id": item["id"], "token": item["token"], "bloqueios": {}}],
        }
        resolver_fronteira.apply_batch(self.repo, payload)
        before = operations._load_state(self.repo)
        second = resolver_fronteira.apply_batch(self.repo, payload)
        self.assertEqual(before, operations._load_state(self.repo))
        self.assertEqual(len(list((self.repo / operations.ENCOUNTERS).glob("*.yaml"))), 2)
        self.assertEqual(len(second["ja_aplicadas"]), 1)

    def test_queda_parcial_e_recuperada_pelo_journal_sem_duplicacao(self):
        group, _ = self.materialize_group()
        with self.assertRaisesRegex(operations.ConcurrentOperationError, "falha simulada"):
            operations.commit_group(self.repo, group["grupo_operacoes_id"], fail_after=2)
        self.assertTrue((self.repo / operations.JOURNAL).is_file())
        recovered = operations.commit_group(self.repo, group["grupo_operacoes_id"])
        self.assertEqual(recovered["resultado"], "recuperado")
        self.assertFalse((self.repo / operations.JOURNAL).exists())
        self.assertTrue(operations.check(self.repo)["ok"])


class ConcurrentDecisionAndKnowledgeTest(ConcurrentOperationFixture):
    def test_presenca_de_ren_em_uma_frente_nao_fecha_a_remota(self):
        group, _ = self.materialize_group()
        self.commit_from_boundary(group)
        view = operations.project_for_ren(
            self.repo, group["grupo_operacoes_id"], local="rua_da_guarda", now=self.now
        )
        self.assertEqual([item["operacao_id"] for item in view["percepcao_direta"]], ["ataque_comitiva"])
        state = operations._load_state(self.repo)["grupos"][group["grupo_operacoes_id"]]["operacoes"]
        self.assertEqual(state["extracao_testemunha"]["estado"], "comprometida")
        remote_pending = next(
            item for item in mundo.load_world_state(self.repo)["pendencias"]
            if item.get("operacao_id") == "extracao_testemunha"
        )
        with self.assertRaisesRegex(barreira_mundo.WorldPendingBarrierError, "não aceita conclusão genérica"):
            barreira_mundo.conclude(self.repo, remote_pending["id"], "Ren permaneceu na outra frente.")

    def test_operacao_remota_pode_ser_resolvida_independentemente(self):
        group, _ = self.materialize_group()
        self.commit_from_boundary(group)
        operations.resolve_operation(
            self.repo,
            "extracao_testemunha",
            self.proof(RESULT_EVIDENCE),
            "A equipe remota encerrou sua tentativa diante da resistência encontrada.",
        )
        state = operations._load_state(self.repo)["grupos"][group["grupo_operacoes_id"]]["operacoes"]
        self.assertEqual(state["extracao_testemunha"]["estado"], "resolvida")
        self.assertEqual(state["ataque_comitiva"]["estado"], "comprometida")

    def test_sem_canal_nao_existe_conhecimento_remoto_instantaneo(self):
        group, _ = self.materialize_group(self.group_proposal(channels=False))
        self.commit_from_boundary(group)
        view = operations.project_for_ren(
            self.repo, group["grupo_operacoes_id"], local="rua_da_guarda", now=self.now
        )
        self.assertEqual(view["informacao_remota_entregue"], [])
        self.assertEqual(view["operacoes_remotas_ocultas"], 1)

    def test_mensageiro_respeita_atraso_e_escopo_de_conhecimento(self):
        group, _ = self.materialize_group()
        self.commit_from_boundary(group)
        with self.assertRaisesRegex(operations.ConcurrentOperationError, "atraso"):
            operations.deliver_information(
                self.repo,
                "extracao_testemunha",
                "mensageiro_templo",
                ["A casa do alvorecer foi atacada."],
                self.proof(CHANNEL_EVIDENCE),
                now=mundo.WorldInstant(self.now.minute + 11),
            )
        with self.assertRaisesRegex(operations.ConcurrentOperationError, "escopo"):
            operations.deliver_information(
                self.repo,
                "extracao_testemunha",
                "mensageiro_templo",
                ["Masao ordenou pessoalmente o ataque secreto."],
                self.proof(CHANNEL_EVIDENCE),
                now=mundo.WorldInstant(self.now.minute + 12),
            )
        delivered = operations.deliver_information(
            self.repo,
            "extracao_testemunha",
            "mensageiro_templo",
            ["A casa do alvorecer foi atacada."],
            self.proof(CHANNEL_EVIDENCE),
            now=mundo.WorldInstant(self.now.minute + 12),
        )
        view = operations.project_for_ren(
            self.repo,
            group["grupo_operacoes_id"],
            local="rua_da_guarda",
            now=mundo.WorldInstant(self.now.minute + 12),
        )
        self.assertEqual(delivered["resultado"], "entregue")
        self.assertEqual(view["informacao_remota_entregue"][0]["fatos"], ["A casa do alvorecer foi atacada."])


class ConcurrentMechanicsTest(ConcurrentOperationFixture):
    def test_aliases_e_operacoes_possuem_ordem_tecnica_deterministica(self):
        proposal = self.group_proposal()
        extra = {
            "adversario": "brutamontes",
            "quantidade": 1,
            "papel": "apoio",
            "especialidade_id": None,
        }
        for operation in proposal["operacoes"]:
            operation["mecanica"]["composicao"].append(copy.deepcopy(extra))
        reversed_proposal = copy.deepcopy(proposal)
        reversed_proposal["operacoes"].reverse()
        for operation in reversed_proposal["operacoes"]:
            operation["mecanica"]["composicao"].reverse()
        first, _ = operations._contract(self.repo, proposal)
        second, _ = operations._contract(self.repo, reversed_proposal)
        self.assertEqual(first["grupo_operacoes_id"], second["grupo_operacoes_id"])
        self.assertEqual(first["grupo_operacoes"]["ordem_processamento"], ["ataque_comitiva", "extracao_testemunha"])

    def test_encontro_fica_imutavel_depois_da_primeira_rolagem(self):
        group, _ = self.materialize_group()
        self.commit_from_boundary(group)
        operations.register_roll(self.repo, "ataque_comitiva", "rolagem-inicial")
        path = self.repo / operations._encounter_rel("ataque_comitiva")
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        doc["encontro"]["mecanica"]["surpresa"] = True
        path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        with self.assertRaisesRegex(operations.ConcurrentOperationError, "encontro congelado divergente"):
            operations.register_roll(self.repo, "ataque_comitiva", "rolagem-inicial")
        self.assertFalse(operations.check(self.repo)["ok"])

    def test_ator_fora_da_area_ou_indeterminado_nao_executa_acao_fisica(self):
        for presence, local_rule in (("fora_da_area", "exige_presenca_fisica"), ("indeterminado", "estrutura_local")):
            with self.subTest(presence=presence):
                fixture = ConcurrentOperationFixture(methodName="runTest")
                fixture.setUp()
                try:
                    proposal = fixture.group_proposal()
                    fixture._write_agent(presence=presence, local_rule=local_rule)
                    with self.assertRaisesRegex(operations.ConcurrentOperationError, "presença física"):
                        operations.prepare(fixture.repo, proposal)
                finally:
                    fixture.tearDown()

    def test_protected_core_bloqueia_autoefeito_mas_nao_o_risco_de_combate(self):
        grave = self.alternative(
            target_id="guardiao_central",
            target_type="npc",
            severity="grave",
            reversibility="irreversivel",
            impact="vida",
        )
        with self.assertRaisesRegex(reactions.SidequestReactionError, "autoridade"):
            reactions.prepare(self.repo, self._mission_id(), self.proposal(alternatives=[grave]))
        group, _ = self.materialize_group()
        self.commit_from_boundary(group)
        encounter = operations.project_operation_pending(
            self.repo,
            next(item for item in mundo.load_world_state(self.repo)["pendencias"] if item.get("operacao_id") == "ataque_comitiva"),
        )["encontro"]
        self.assertTrue(encounter["guardrails"]["protected_core_nao_remove_risco_de_combate"])
        self.assertEqual(encounter["mecanica"]["modo"], "combate")

    @staticmethod
    def _mission_id():
        from tests.test_sidequest_success_reactions import MISSION_ID
        return MISSION_ID

    def test_ameaca_letal_exige_saida_plausivel_e_perceptivel(self):
        self.threat_classification = "letal"
        proposal = self.group_proposal()
        proposal["operacoes"][0]["mecanica"]["rotas_retirada"] = []
        with self.assertRaisesRegex(operations.ConcurrentOperationError, "saída plausível"):
            operations.prepare(self.repo, proposal)
        valid = self.group_proposal()
        contract, _ = operations._contract(self.repo, valid)
        routes = contract["grupo_operacoes"]["operacoes"][0]["mecanica"]["rotas_retirada"]
        self.assertIn(routes[0]["perceptibilidade"], {"perceptivel", "investigavel"})


class ConcurrentIsolationTest(ConcurrentOperationFixture):
    def test_fixture_e_artefatos_permanecem_fora_do_estado_vivo_do_repo(self):
        group, _ = self.materialize_group()
        self.commit_from_boundary(group)
        self.assertNotEqual(self.repo.resolve(), ROOT.resolve())
        for path in (self.repo / operations.ROOT).rglob("*"):
            self.assertTrue(path.resolve().is_relative_to(self.repo.resolve()))
        contract = operations.check(self.repo)["contrato"]
        budget = yaml.safe_load(
            (ROOT / "baseline/concurrent-adversarial-operations-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )["limites"]
        self.assertEqual(budget["grupos_max"], operations.MAX_GROUPS)
        self.assertEqual(budget["operacoes_por_grupo_max"], operations.MAX_OPERATIONS)
        self.assertEqual(budget["canais_por_grupo_max"], operations.MAX_CHANNELS)
        self.assertEqual(budget["contrato_por_grupo_bytes_max"], operations.MAX_GROUP_BYTES)
        self.assertEqual(budget["encontro_por_operacao_bytes_max"], operations.MAX_ENCOUNTER_BYTES)
        self.assertEqual(contract["scheduler_novo"], 0)
        self.assertEqual(contract["rng_novo"], 0)
        self.assertEqual(contract["scan_global"], 0)


if __name__ == "__main__":
    unittest.main()
