"""Iniciativa própria e duas frentes em fixtures, sem missão ou save vivo."""
from copy import deepcopy
import json
from unittest.mock import patch

from test_planos_personagens import PlanFixture
from tests.test_concurrent_world_operations import ConcurrentOperationFixture, ACTOR_ID, CHANNEL_EVIDENCE
import cronica
import mundo
import operacoes_concorrentes as operations
import planos_personagens as plans
import reacoes_sidequest as reactions
import resolver_fronteira as batch
import turno
import pressao_narrativa as pressure


class AdversarialPlanFixture(PlanFixture, ConcurrentOperationFixture):
    def setUp(self):
        PlanFixture.setUp(self)
        self.now = mundo.load_canonical_time(self.repo)[0]
        self._write_sources()
        facts = self.repo / "sessoes/001/fatos.md"
        facts.write_text(facts.read_text() + CHANNEL_EVIDENCE + "\n", encoding="utf-8")
        self._write_agent()
        self._write_protected_policy()
        self.outcome = "A célula perdeu o acesso ao arquivo e abandonou a ordem falsa."

    def tearDown(self):
        # PlanFixture administra seu TemporaryDirectory por addCleanup.
        pass

    def proposal_from_plans(self):
        with patch.object(self, "_reactions", return_value=(None, None)):
            proposal = ConcurrentOperationFixture.group_proposal(self)
        source = f"narrador/agentes/{ACTOR_ID}.yaml"
        actor = self.read(source)
        actor["implantacoes"] = {}
        definitions = []
        for i, op in enumerate(proposal["operacoes"]):
            op.pop("reaction_id")
            aid = op.pop("alternative_id")
            op["mecanica"] = self.mechanics(mode="nenhuma")
            pid = op["id"]
            alternative = self.alternative(alternative_id=aid,
                capability="extrair_registro" if i == 0 else "fraudar_ordem",
                target_id=op["alvo"]["id"], target_type=op["alvo"]["tipo"], resource=op["recursos"][0])
            alternative["objetivo"] = actor["objetivo_atual"]
            deployment = {"local": op["local"], "celula_id": op["celula_id"], "estado": "disponivel",
                          "em_deslocamento": False, "recursos": sorted(op["recursos"])}
            actor["implantacoes"][op["celula_id"]] = deployment
            op["origem_plano"] = {"id": pid, "revisao": 1, "alternativa": alternative,
                "implantacao": {"arquivo": source, "caminho": "implantacoes." + op["celula_id"], "valor": deployment}}
            step = {"id": "executar", "acao": op["objetivo"], "em": mundo.instant_parts(self.now),
                    "duracao_minutos": 0, "local": op["local"], "condicoes": [], "recursos": [],
                    "conhecimento": alternative["conhecimentos_requeridos"],
                    "resolucao": {"tipo": "operacao", "operacao_id": op["id"]}}
            definitions.append({"alvo": "plano:" + pid, "op": "registrar", "visibilidade": "narrador",
                "valor": {"evento": "definir", "revisao": 0, "fato": "A rede decidiu executar duas frentes do seu plano.",
                    "agente": {"tipo": "estrategico", "id": ACTOR_ID}, "objetivo": actor["objetivo_atual"], "passo": step}})
            proposal["canais"].append({"id": "retorno_" + pid, "tipo": "mensageiro", "operacao_origem": pid,
                "destinatario": ACTOR_ID, "atraso_minutos": 5, "conhecimentos_permitidos": [self.outcome],
                "prova_disponibilidade": self.proof(CHANNEL_EVIDENCE)})
        self.write(source, actor)
        fact = definitions[0]["valor"]["fato"]
        turno.register_transaction(self.repo, {"id": "definir-frentes", "modo": "mundo", "narracao": fact,
            "resumo": fact, "deltas": definitions})
        return proposal

    def prepare_and_materialize(self, proposal=None):
        proposal = proposal or self.proposal_from_plans()
        prepared = operations.prepare(self.repo, proposal)
        return operations.materialize(self.repo, proposal, prepared["preparacao_id"]), proposal

    def start(self):
        group, proposal = self.prepare_and_materialize()
        self.commit_from_boundary(group)
        prepared = batch.prepare_batch(self.repo)
        decisions = [{"id": item["id"], "token": item["token"], "evento": {"evento": "tentar", "revisao": 1,
                      "fato": "As células começaram suas ações independentes."}}
                     for item in prepared["itens"] if item["tipo"] == plans.PENDING_TYPE]
        batch.apply_batch(self.repo, {"lote_id": prepared["lote_id"], "planos": decisions})
        return group, proposal

    def resolve_first(self, **kwargs):
        path = self.repo / "sessoes/001/fatos.md"
        path.write_text(path.read_text() + self.outcome + "\n", encoding="utf-8")
        return operations.resolve_operation(self.repo, "ataque_comitiva", self.proof(self.outcome), self.outcome,
                                            desfecho="falha", **kwargs)

    def turn(self, prepared, *, txid="turno-frentes", hour=None):
        meta = cronica.decode_ticket(prepared["ticket"])
        tx = {"id": txid, "modo": "exploração", "jogador": "Ren aguarda no pátio.",
              "narracao": "Os minutos passam no pátio sem novidades perceptíveis.",
              "resumo": "Ren aguarda; as frentes remotas continuam.", "deltas": []}
        if pressure.TICKET_KEY in meta:
            tx[pressure.TRANSACTION_KEY] = {"resultados": [{"pressao_id": p["pressao_id"], "resultado": "continua"}
                                                         for p in meta[pressure.TICKET_KEY]["itens"]]}
        if hour:
            tx["deltas"].append({"alvo": "tempo", "op": "instante", "valor": {"data": mundo.instant_parts(self.now)["data"], "hora": hour}})
        return tx

    def play(self, prepared, *, txid="turno-frentes", hour=None):
        return cronica.conclude(self.repo, prepared["ticket"], self.turn(prepared, txid=txid, hour=hour))


class AdversarialInitiativeTest(AdversarialPlanFixture):
    def test_duas_frentes_nascem_de_intencao_sem_reacao_ou_missao(self):
        proposal = self.proposal_from_plans()
        before = self.hashes()
        p = operations.prepare(self.repo, proposal)
        self.assertEqual(before, self.hashes())
        group = operations.materialize(self.repo, proposal, p["preparacao_id"])
        self.assertEqual(group["reacoes_reivindicadas"], [])
        self.assertFalse((self.repo / reactions.STATE).exists())
        self.commit_from_boundary(group)
        for op in proposal["operacoes"]:
            _, contract, row, _ = operations._operation_context(self.repo, op["id"])
            self.assertEqual(row["estado"], "comprometida")
            self.assertEqual(contract["objetivo_estrategico"], self.plan(op["id"])["objetivo"])
        self.assertTrue(operations.check(self.repo)["ok"])

    def test_falha_de_uma_frente_preserva_outra_e_exige_retorno_antes_adaptacao(self):
        self.start()
        self.resolve_first()
        self.assertEqual(operations._operation_context(self.repo, "extracao_testemunha")[2]["estado"], "comprometida")
        plan = self.plan("ataque_comitiva")
        event = {"evento": "resolver", "revisao": plan["revisao"], "fato": self.outcome,
                 "resultado": "falha", "seguimento": "desistir", "motivo": self.outcome,
                 "passo": None, "retomar_em": None, "rolagem": None, "prova": None}
        prepared = batch.prepare_batch(self.repo)
        item = next(item for item in prepared["itens"] if item.get("contexto", {}).get("plano_personagem", {}).get("plano", {}).get("id") == "ataque_comitiva")
        decision = {"lote_id": prepared["lote_id"], "planos": [{"id": item["id"], "token": item["token"], "evento": event}]}
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "não chegou"):
            batch.apply_batch(self.repo, decision)
        self.assertEqual(before, self.hashes())
        with self.assertRaisesRegex(ValueError, "atraso"):
            operations.deliver_information(self.repo, "ataque_comitiva", "retorno_ataque_comitiva", [self.outcome], self.proof(self.outcome))
        p = cronica.prepare(self.repo, scene_id="patio", sidequest_signal=None, memory_participants=[])
        self.assertNotEqual(p["fase"], "bloqueada_pendencias_mundo")
        self.play(p, hour="08:08")
        operations.deliver_information(self.repo, "ataque_comitiva", "retorno_ataque_comitiva", [self.outcome],
                                       self.proof(self.outcome), now=mundo.WorldInstant(self.now.minute + 5))
        prepared = batch.prepare_batch(self.repo)
        item = next(item for item in prepared["itens"] if item.get("contexto", {}).get("plano_personagem", {}).get("plano", {}).get("id") == "ataque_comitiva")
        decision = {"lote_id": prepared["lote_id"], "planos": [{"id": item["id"], "token": item["token"], "evento": event}]}
        batch.apply_batch(self.repo, decision)
        self.assertEqual(self.plan("ataque_comitiva")["estado"], "desistiu")
        self.assertIn("retorno_ao_agente", self.plan("ataque_comitiva")["ultima_tentativa"]["resultado"])
        self.assertEqual(self.plan("extracao_testemunha")["estado"], "tentou")
        before = self.hashes()
        batch.apply_batch(self.repo, decision)
        self.assertEqual(before, self.hashes())

    def test_capacidade_conhecimento_implantacao_e_recursos_reais_sao_obrigatorios(self):
        proposal = self.proposal_from_plans()
        source = f"narrador/agentes/{ACTOR_ID}.yaml"
        original = self.read(source)
        mutations = [("metodos_operacionais", {}), ("conhecimento", []), ("implantacoes", {}), ("recursos", [])]
        for key, value in mutations:
            with self.subTest(key=key):
                actor = deepcopy(original)
                actor[key] = value
                self.write(source, actor)
                before = self.hashes()
                with self.assertRaises(ValueError): operations.prepare(self.repo, proposal)
                self.assertEqual(before, self.hashes())
        self.write(source, original)

    def test_passo_obsoleto_nao_ganha_compromisso(self):
        group, _ = self.prepare_and_materialize()
        world = mundo.load_world_state(self.repo)
        world[plans.KEY]["ataque_comitiva"]["revisao"] += 1
        self.write(mundo.WORLD_STATE_PATH, world)
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "revisão"):
            operations.commit_group(self.repo, group["grupo_operacoes_id"])
        self.assertEqual(before, self.hashes())

    def test_impedir_uma_frente_registra_bloqueio_e_preserva_a_outra(self):
        group, _ = self.prepare_and_materialize()
        blocker = {"ataque_comitiva": {"motivo": "A matriz saiu da rua antes do início da operação.",
                                        "prova": self.proof()}}
        result = self.commit_from_boundary(group, blocker)["grupos_comprometidos"][0]
        self.assertEqual(result["operacoes_bloqueadas"], ["ataque_comitiva"])
        self.assertEqual(result["operacoes_comprometidas"], ["extracao_testemunha"])
        rows = operations._load_state(self.repo)["grupos"][group["grupo_operacoes_id"]]["operacoes"]
        self.assertEqual(rows["ataque_comitiva"]["estado"], "bloqueada")
        self.assertEqual(rows["ataque_comitiva"]["bloqueio"], blocker["ataque_comitiva"])
        self.assertEqual(rows["extracao_testemunha"]["estado"], "comprometida")

    def test_reserva_do_plano_impede_reuso_por_reacao_posterior(self):
        group, _ = self.prepare_and_materialize()
        self.commit_from_boundary(group)
        self._write_opportunities()
        self._write_mission(completed=True)
        reaction = self.materialize()
        reactions.reconcile(self.repo)
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "operação"):
            reactions.commit(self.repo, reaction["reaction_id"], ["ordem_contraditoria"])
        self.assertEqual(before, self.hashes())

    def test_resultado_interrompido_recupera_fila_e_reservas_uma_vez(self):
        self.start()
        with self.assertRaisesRegex(ValueError, "simulada"):
            self.resolve_first(fail_after=1)
        operations.resolve_operation(self.repo, "ataque_comitiva", self.proof(self.outcome), self.outcome, desfecho="falha")
        before = self.hashes()
        operations.resolve_operation(self.repo, "ataque_comitiva", self.proof(self.outcome), self.outcome, desfecho="falha")
        self.assertEqual(before, self.hashes())
        self.assertFalse((self.repo / operations.JOURNAL).exists())
        self.assertEqual(len(operations._load_state(self.repo)["reservas_exclusivas"]), 1)

    def test_materializacao_interrompida_recupera_sem_criar_reacao_ficticia(self):
        proposal = self.proposal_from_plans()
        p = operations.prepare(self.repo, proposal)
        with self.assertRaisesRegex(ValueError, "simulada"):
            operations.materialize(self.repo, proposal, p["preparacao_id"], fail_after=2)
        operations.materialize(self.repo, proposal, p["preparacao_id"])
        self.assertTrue(operations.check(self.repo)["ok"])
        self.assertFalse((self.repo / reactions.STATE).exists())
        before = self.hashes()
        operations.materialize(self.repo, proposal, p["preparacao_id"])
        self.assertEqual(before, self.hashes())

    def test_operacoes_jogaveis_nao_ficam_atras_do_proprio_plano(self):
        self.start()
        before = self.hashes()
        p = cronica.prepare(self.repo, scene_id="patio", sidequest_signal=None, memory_participants=[])
        self.assertEqual(before, self.hashes())
        self.assertNotEqual(p["fase"], "bloqueada_pendencias_mundo")
        self.assertEqual(len(p["pressao_narrativa"]["itens"]), 2)
        self.assertEqual(len(p["planos_aguardando"]), 2)
        tx = self.turn(p)
        cronica.conclude(self.repo, p["ticket"], tx)
        self.assertEqual(len(mundo.pending_view(self.repo)["pendencias"]), 4)
        after = self.hashes()
        cronica.conclude(self.repo, p["ticket"], tx)
        self.assertEqual(after, self.hashes())
