"""Fronteiras causais completas sobre uma fixture isolada, sem herança de casos."""
from copy import deepcopy
import unittest

import test_acionamentos_leves as cases

causal = cases.causal
batch = cases.batch
barrier = cases.barrier
light = cases.light
cronica = cases.cronica
turno = cases.turno
consolidar = cases.consolidar


class CausalBoundaryRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.f = cases.CausalActivationIntegrationTest()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.repo = self.f.repo

    def enqueue(self, people):
        world = self.f.world()
        for aid in people:
            source = f"estado/relacoes/{aid}.yaml"
            causal._enqueue(world, aid, source, cases.signal(source, suffix=aid))
        causal.dispatch(world, light.load_index(self.repo))
        self.f.write(causal.WORLD.as_posix(), world)
        barrier.sync(self.repo)
        return self.f.world()["pendencias"]

    def test_duas_causas_ativas_compartilham_orcamento_de_saida_do_lote(self):
        self.enqueue(self.f.people[:2])
        before = self.f.f.hashes()
        prepared = batch.prepare_batch(self.repo)
        self.assertEqual(prepared["quantidade"], 2)
        self.assertLessEqual(causal._size(prepared), 8192)
        for item in prepared["itens"]:
            self.assertEqual(item["classificacao"], "avaliar_condicao_causal")
            self.assertLessEqual(causal._size(item["contexto"]["acionamento_causal"]), causal.MAX_CONTEXT_BYTES)
        self.assertEqual(before, self.f.f.hashes())

    def test_lote_tem_condicao_antes_de_rotina_antiga_sem_perder_ids(self):
        self.enqueue(["silva_fixture"])
        world = self.f.world()
        routine = cases.CausalQueueTest().routine("nera_fixture", "c")
        routine["disparado_em"] = cases.when("07:00")
        world["pendencias"].append(routine)
        self.f.write(causal.WORLD.as_posix(), world)
        prepared = batch.prepare_batch(self.repo)
        self.assertEqual(prepared["itens"][0]["agente_leve"], "silva_fixture")
        self.assertEqual(prepared["itens"][1]["id"], routine["id"])
        self.assertIn("agente_leve", prepared["itens"][1]["contexto"])

    def test_resolucao_da_propria_fonte_nao_gera_loop_mas_notifica_dependente(self):
        pending = self.enqueue(["silva_fixture"])[0]
        index = light.load_index(self.repo)
        index["agentes"]["nera_fixture"]["fontes_causais"] = ["estado/relacoes/silva_fixture.yaml"]
        self.f.write(causal.INDEX.as_posix(), index)
        transaction = {"id": "resposta-causal", "modo": "mundo",
                       "narracao": "Silva decidiu aguardar a reabertura da ponte.",
                       "resumo": "Silva decidiu aguardar a reabertura da ponte.",
                       "tags": [f"resolver-pendencia-mundo:{pending['id']}"],
                       "deltas": [{"alvo": "relacao:silva_fixture", "op": "set",
                                   "caminho": "vinculo", "valor": "Aguardar a ponte, preservando o acordo."}]}
        turno.register_transaction(self.repo, transaction)
        world = self.f.world()
        own = [p for p in world["pendencias"] if p.get("agente_leve") == "silva_fixture"]
        self.assertEqual(len(own), 1)
        self.assertEqual(own[0]["id"], pending["id"])
        self.assertEqual(own[0][causal.PENDING_KEY], pending[causal.PENDING_KEY])
        self.assertIn("nera_fixture", {p.get("agente_leve") for p in world["pendencias"]})
        self.assertNotIn("ponte", str(self.f.read("estado/relacoes/nera_fixture.yaml")))

    def test_fim_da_janela_reavalia_sem_repetir_inicio_ja_decidido(self):
        self.f.due_commitment(hour="08:03")
        barrier.sync(self.repo)
        batch.apply_batch(self.repo, self.f.plan())
        self.assertEqual(self.f.world()["pendencias"], [])
        tx = self.f.simple("fim-janela", [{"alvo": "tempo", "op": "instante", "valor": cases.when("09:00")}])
        cronica.conclude(self.repo, self.f.f.token, tx)
        pending = self.f.world()["pendencias"]
        self.assertEqual(len(pending), 1)
        phases = {c.get("fase") for c in pending[0][causal.PENDING_KEY].values() if c["tipo"] == "prazo"}
        self.assertEqual(phases, {"fim"})
        self.assertIn("mapa", self.f.read(causal.STATE)["compromissos"])

    def test_conclusao_direta_com_journal_aberto_falha_antes_de_cache_ou_estado(self):
        pending = self.enqueue(["silva_fixture"])[0]
        import _consolidar_core
        (self.repo / _consolidar_core.JOURNAL_PATH).write_text('{}', encoding="utf-8")
        before = self.f.f.hashes()
        with self.assertRaises(ValueError):
            light.conclude_noop(self.repo, pending["id"], cases.NOTE)
        self.assertEqual(before, self.f.f.hashes())

    def test_barreira_nao_conclui_causa_sobre_canone_parcial(self):
        pending = self.enqueue(["silva_fixture"])[0]
        import _consolidar_core
        (self.repo / _consolidar_core.JOURNAL_PATH).write_text('{}', encoding="utf-8")
        before = self.f.f.hashes()
        with self.assertRaises(ValueError):
            barrier.conclude(self.repo, pending["id"], cases.NOTE, no_change=True)
        self.assertEqual(before, self.f.f.hashes())

    def test_token_mudado_recusa_lote_inteiro_antes_de_aplicar_primeira_decisao(self):
        self.enqueue(self.f.people[:2])
        plan = self.f.plan()
        world = self.f.world()
        second = world["pendencias"][1]
        second[causal.PENDING_KEY]["novo"] = cases.signal(suffix="mudanca-posterior")
        self.f.write(causal.WORLD.as_posix(), world)
        before = self.f.f.hashes()
        with self.assertRaises(ValueError):
            batch.apply_batch(self.repo, plan)
        self.assertEqual(before, self.f.f.hashes())


if __name__ == "__main__":
    unittest.main()
