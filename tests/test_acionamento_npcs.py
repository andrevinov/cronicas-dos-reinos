"""Regressões de domínio da segunda NV-07, reconciliadas com acionamentos_leves.

As fixtures são sintéticas. Não manter uma segunda implementação só para testar
seu próprio schema: fila, prazos e projeção abaixo exercitam o motor da main.
Rastreabilidade da substituição: docs/agente/acionamento-causal-npcs.md.
"""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ferramentas"))
import acionamentos_leves as causal
import resolver_fronteira as batch
import test_acionamentos_leves as fixtures

WHEN = {"data": "7 Eleasis, 1372 DR", "hora": "09:00"}


def when(hour="09:00"):
    return {**WHEN, "hora": hour}


def index_for(names="abcd"):
    return {"orcamento": {"max_novas_por_checkpoint": 1, "max_pendencias_abertas": 2},
            "agentes": {a: {"estado": "ativo", "fontes_causais": [f"estado/relacoes/{a}.yaml"]} for a in names}}


def world():
    return {"pendencias": [], "concluidas_recentes": [], "processado_ate": when()}


def routine(agent, number):
    return {"id": f"mundo-{number:016x}", "tipo": "reavaliar_agente_leve", "agente_leve": agent,
            "agentes_afetados": [], "disparado_em": when(), "origem": f"agentes-leves:{agent}.cadencia"}


def signal(agent="a", version=1):
    source = f"estado/relacoes/{agent}.yaml"
    return {"tipo": "mudanca", "fonte": source, "em": when(),
            "assinatura": causal._digest([source, version]), "lote": str(version)}


def appointment(involved=("a",), hour="09:00"):
    return {"tipo": "encontro", "resumo": "Conversar sobre o mapa.", "envolvidos": list(involved),
            "janela": {"inicio": when(hour)}}


def enqueue(state, index, notices):
    # O chamador transacional trabalha sobre uma cópia staged; dispatch é in-place.
    result = deepcopy(state)
    for agent, changes in notices.items():
        for key, cause in changes.items():
            causal._enqueue(result, agent, key, cause)
    causal.dispatch(result, index)
    return result


class CausalQueueTest(unittest.TestCase):
    def setUp(self):
        self.index = index_for()

    def test_causa_precede_rotinas_sem_aumentar_dois_slots(self):
        state = world()
        state["pendencias"] = [routine("b", 1), routine("c", 2)]
        before = deepcopy(state)
        result = enqueue(state, self.index, {"a": {"fonte": signal()}})
        self.assertEqual(len(result["pendencias"]), 2)
        self.assertIn("a", {p["agente_leve"] for p in result["pendencias"]})
        all_ids = {p["id"] for p in result["pendencias"]} | set(result[causal.KEY]["rotinas_suspensas"])
        self.assertTrue({p["id"] for p in before["pendencias"]} <= all_ids)
        self.assertEqual(len(result[causal.KEY]["rotinas_suspensas"]), 1)
        self.assertEqual(state, before)
        self.assertEqual(self.index["orcamento"]["max_novas_por_checkpoint"], 1)

    def test_mesmo_agente_coalesce_sem_trocar_id_rotineiro(self):
        state = world()
        state["pendencias"] = [routine("a", 1)]
        first = enqueue(state, self.index, {"a": {"fonte": signal()}})
        second = enqueue(first, self.index, {"a": {"fonte": signal(version=2), "outra": signal(version=3)}})
        self.assertEqual(len(second["pendencias"]), 1)
        self.assertEqual(second["pendencias"][0]["id"], state["pendencias"][0]["id"])
        causes = second["pendencias"][0][causal.PENDING_KEY]
        self.assertEqual(set(causes), {"fonte", "outra"})
        self.assertEqual(causes["fonte"]["assinatura"], signal(version=2)["assinatura"])

    def test_replay_mesma_causa_e_deterministico_e_idempotente(self):
        notices = {"a": {"fonte": signal()}}
        first = enqueue(world(), self.index, notices)
        self.assertEqual(first, enqueue(first, self.index, notices))
        self.assertEqual(first, enqueue(world(), self.index, notices))

    def test_conclusao_reabastece_adiadas_sem_amanhecer(self):
        result = enqueue(world(), self.index, {a: {"fonte": signal(a)} for a in "abcd"})
        finished = []
        while result["pendencias"]:
            item = result["pendencias"].pop(0)
            result["concluidas_recentes"].append(item)
            finished.append(item["agente_leve"])
            causal.dispatch(result, self.index)
            self.assertLessEqual(len(result["pendencias"]), 2)
        self.assertEqual(sorted(finished), list("abcd"))
        self.assertEqual(result[causal.KEY]["aguardando"], {})

    def test_acontecimento_compartilhado_tem_somente_assinantes_explicitos(self):
        self.index["agentes"]["b"]["fontes_causais"] = ["estado/relacoes/a.yaml"]
        self.assertEqual(causal._dependencies(self.index)["estado/relacoes/a.yaml"], {"a", "b"})
        self.assertNotIn("estado/relacoes/desconhecido.yaml", causal._dependencies(self.index))

    def test_inativo_nao_recebe_causa_nem_ocupa_slot(self):
        result = enqueue(world(), self.index, {a: {"fonte": signal(a)} for a in "abc"})
        inactive = result["pendencias"][0]["agente_leve"]
        self.index["agentes"][inactive]["estado"] = "inativo"
        causal._refresh_deadlines(result, {"compromissos": {}}, self.index, when())
        causal.dispatch(result, self.index)
        self.assertEqual(len(result["pendencias"]), 2)
        self.assertTrue(all(p["agente_leve"] != inactive for p in result["pendencias"]))

    def test_fila_cheia_falha_sem_descartar_a_entrada_staged(self):
        names = [f"p{i}" for i in range(causal.MAX_SIGNALS + 1)]
        state = world()
        before = deepcopy(state)
        with self.assertRaises(causal.ActivationError):
            enqueue(state, index_for(names), {a: {"fonte": signal(a)} for a in names})
        self.assertEqual(state, before)

    def test_notificar_nao_executa_acao_nem_atribui_conhecimento(self):
        with patch("builtins.open", side_effect=AssertionError("dispatch não deve escrever arquivos")):
            result = enqueue(world(), self.index, {"a": {"fonte": signal()}})
        pending = result["pendencias"][0]
        for key in ("sucesso", "acao_executada", "conhecimento", "presenca", "deltas"):
            self.assertNotIn(key, pending)
        self.assertEqual(pending["agente_leve"], "a")

    def test_dominio_estrategico_nao_e_adiado_pela_fila_leve(self):
        state = world()
        strategic = {"id": "mundo-1111111111111111", "tipo": "reavaliar_agente", "agente": "vilao", "disparado_em": when()}
        state["pendencias"] = [strategic]
        result = enqueue(state, self.index, {a: {"fonte": signal(a)} for a in "abcd"})
        self.assertIn(strategic, result["pendencias"])
        self.assertNotIn(strategic["id"], result[causal.KEY]["rotinas_suspensas"])

    def test_neutro_nao_cria_controle_paralelo(self):
        with patch.object(causal, "configured", side_effect=AssertionError("consulta indevida")):
            self.assertIsNone(causal.checkpoint_trigger(Path("/ausente"), [], {"deltas": []}))

    def test_controle_e_causas_malformados_falham_fechado(self):
        valid = enqueue(world(), self.index, {"a": {"fonte": signal()}})
        cases = []
        for value in ([], True, {"versao": 7}):
            bad = deepcopy(valid)
            bad[causal.KEY] = value
            cases.append(bad)
        for key, value in (("tipo", "executar_acao"), ("assinatura", "invalida"), ("em", {})):
            bad = deepcopy(valid)
            bad["pendencias"][0][causal.PENDING_KEY]["fonte"][key] = value
            cases.append(bad)
        for bad in cases:
            with self.subTest(bad=bad), self.assertRaises(causal.ActivationError):
                causal._validate_control(bad)

    def test_reposicao_nao_duplica_id_entre_rotina_ativa_e_suspensa(self):
        state = world()
        state["pendencias"] = [routine("b", 1), routine("c", 2)]
        result = enqueue(state, self.index, {"a": {"fonte": signal()}})
        for _ in range(3):
            causal.dispatch(result, self.index)
            ids = [p["id"] for p in result["pendencias"]] + list(result[causal.KEY]["rotinas_suspensas"])
            self.assertEqual(len(ids), len(set(ids)))
        result["pendencias"] = [p for p in result["pendencias"] if p["agente_leve"] != "a"]
        causal.dispatch(result, self.index)
        self.assertEqual({p["id"] for p in result["pendencias"]}, {p["id"] for p in state["pendencias"]})


class CausalDeadlineTest(unittest.TestCase):
    def setUp(self):
        self.index = index_for()

    def test_hora_exata_acorda_so_envolvido_ativo(self):
        self.index["agentes"]["b"]["estado"] = "inativo"
        state = {"compromissos": {"encontro": appointment(("a", "b", "ren"))}}
        self.assertEqual(causal.deadline_events(state, self.index, {}, when("08:59")), [])
        due = causal.deadline_events(state, self.index, {}, when())
        self.assertEqual([(a, k) for a, k, _ in due], [("a", "encontro:inicio")])
        self.assertNotIn("resultado", due[0][2])

    def test_recibo_nao_depende_das_conclusoes_recentes(self):
        state = {"compromissos": {"encontro": appointment()}}
        queue = world()
        causal._refresh_deadlines(queue, state, self.index, when())
        receipts = deepcopy(queue[causal.KEY]["prazos"])
        queue["concluidas_recentes"] = [{"id": str(i)} for i in range(100)]
        self.assertEqual(causal.deadline_events(state, self.index, receipts, when("11:00")), [])

    def test_inicio_e_fim_disparam_uma_vez_sem_concluir_promessa(self):
        record = appointment()
        record["janela"]["fim"] = when("10:00")
        state = {"compromissos": {"encontro": record}}
        before = deepcopy(state)
        queue = world()
        causal._refresh_deadlines(queue, state, self.index, when())
        receipts = queue[causal.KEY]["prazos"]
        due = causal.deadline_events(state, self.index, receipts, when("10:00"))
        self.assertEqual([c[2]["fase"] for c in due], ["fim"])
        causal._refresh_deadlines(queue, state, self.index, when("10:00"))
        self.assertEqual(causal.deadline_events(state, self.index, queue[causal.KEY]["prazos"], when("10:01")), [])
        self.assertEqual(state, before)

    def test_janela_descritiva_nao_inventa_hora(self):
        record = appointment()
        record["janela"] = {"descricao": "Quando o barco chegar."}
        self.assertEqual(causal.deadline_events({"compromissos": {"encontro": record}}, self.index, {}, when("23:59")), [])

    def test_cancelamento_revoga_prazo_sem_fabricar_resultado(self):
        queue = world()
        causal._refresh_deadlines(queue, {"compromissos": {"encontro": appointment()}}, self.index, when())
        causal.dispatch(queue, self.index)
        pid = queue["pendencias"][0]["id"]
        causal._refresh_deadlines(queue, {"compromissos": {}}, self.index, when())
        self.assertEqual(queue["pendencias"], [])
        self.assertEqual(queue[causal.KEY]["prazos"], {})
        self.assertEqual(queue["concluidas_recentes"][-1]["id"], pid)
        self.assertEqual(queue["concluidas_recentes"][-1]["resultado"], "gatilho_revogado")

    def test_substituicao_futura_invalida_prazo_antigo(self):
        queue = world()
        causal._refresh_deadlines(queue, {"compromissos": {"encontro": appointment()}}, self.index, when())
        causal.dispatch(queue, self.index)
        state = {"compromissos": {"encontro": appointment(hour="11:00")}}
        causal._refresh_deadlines(queue, state, self.index, when("10:00"))
        self.assertEqual(queue["pendencias"], [])
        self.assertEqual(queue[causal.KEY]["prazos"], {})
        self.assertEqual(len(causal.deadline_events(state, self.index, {}, when("11:00"))), 1)

    def test_mudanca_de_envolvido_revoga_antigo_e_entrega_novo(self):
        queue = world()
        causal._refresh_deadlines(queue, {"compromissos": {"encontro": appointment()}}, self.index, when())
        causal.dispatch(queue, self.index)
        causal._refresh_deadlines(queue, {"compromissos": {"encontro": appointment(("b",))}}, self.index, when())
        causal.dispatch(queue, self.index)
        self.assertEqual([p["agente_leve"] for p in queue["pendencias"]], ["b"])
        self.assertEqual(set(queue[causal.KEY]["prazos"]), {"b:encontro:inicio"})

    def test_dois_prazos_simultaneos_coalescem_por_agente(self):
        queue = world()
        state = {"compromissos": {"mapa": appointment(), "selo": appointment()}}
        causal._refresh_deadlines(queue, state, self.index, when())
        causal.dispatch(queue, self.index)
        self.assertEqual(len(queue["pendencias"]), 1)
        self.assertEqual(len(queue["pendencias"][0][causal.PENDING_KEY]), 2)

    def test_recibo_malformado_nao_silencia_prazo(self):
        queue = world()
        causal._control(queue)["prazos"] = {"a:encontro:inicio": "falsa"}
        with self.assertRaises(causal.ActivationError):
            causal._validate_control(queue)

    def test_inicio_e_fim_atrasados_nao_exigem_replay_dos_dias(self):
        record = appointment()
        record["janela"]["fim"] = when("10:00")
        due = causal.deadline_events({"compromissos": {"encontro": record}}, self.index, {},
                                    {"data": "27 Eleasis, 1372 DR", "hora": "23:59"})
        self.assertEqual([c[2]["fase"] for c in due], ["inicio", "fim"])


class CausalProjectionTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.CausalActivationIntegrationTest()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.repo = self.f.repo
        self.aid = self.f.people[0]
        self.source = f"estado/relacoes/{self.aid}.yaml"

    def project(self, value):
        doc = self.f.read(self.source)
        doc["relacao"]["vinculo"] = value
        self.f.write(self.source, doc)
        self.pending = {**routine(self.aid, 1), causal.PENDING_KEY: {self.source: fixtures.signal(self.source)}}
        return causal.pending_context(self.repo, self.pending)

    def test_mudanca_le_so_fragmento_dirigido_nao_outros_perfis(self):
        result = self.project("Aliado por escolha.")
        self.assertEqual(result["fragmento"], self.source)
        fragment_sources = [p for p in result["fontes_lidas"] if p.startswith("estado/relacoes/") and not p.endswith("index.yaml")]
        self.assertEqual(fragment_sources, [self.source])
        self.assertEqual(result["memoria_atual"]["itens"][self.aid]["relacao"]["dados"]["vinculo"], "Aliado por escolha.")

    def test_rumor_preserva_estatuto_sem_transmitir_a_outro_npc(self):
        value = {"estatuto": "rumor", "texto": "A ponte teria caído."}
        other_files = {p: (self.repo / f"estado/relacoes/{p}.yaml").read_bytes() for p in self.f.people[1:]}
        result = self.project(value)
        self.assertEqual(result["memoria_atual"]["itens"][self.aid]["relacao"]["dados"]["vinculo"], value)
        for person, raw in other_files.items():
            self.assertEqual((self.repo / f"estado/relacoes/{person}.yaml").read_bytes(), raw)
            self.assertNotIn(person, result["memoria_atual"]["itens"])

    def test_fato_indivisivel_grande_exige_aprofundamento_sem_corte(self):
        text = "Um fato indivisível. " * 700
        result = self.project(text)
        self.assertLessEqual(causal._size(result), causal.MAX_CONTEXT_BYTES)
        self.assertTrue(result["memoria_atual"]["aprofundamento_necessario"])
        self.assertNotIn(text[:300], json.dumps(result, ensure_ascii=False))
        self.assertEqual(self.f.read(self.source)["relacao"]["vinculo"], text)
        self.assertEqual(result["fragmento"], self.source)

    def test_fonte_mudada_invalida_assinatura_inclusive_campo_nao_projetado(self):
        before = self.project("Antes")
        doc = self.f.read(self.source)
        doc["relacao"]["anotacao_secundaria"] = "Detalhe adicional, não no recorte."
        self.f.write(self.source, doc)
        after = causal.pending_context(self.repo, self.pending)
        self.assertNotEqual(before["base_fonte"], after["base_fonte"])

    def test_remocao_reflete_ausencia_sem_manter_valor_obsoleto(self):
        before = self.project("Vínculo cancelado.")
        doc = self.f.read(self.source)
        del doc["relacao"]["vinculo"]
        self.f.write(self.source, doc)
        after = causal.pending_context(self.repo, self.pending)
        self.assertNotIn("vinculo", after["memoria_atual"]["itens"][self.aid]["relacao"]["dados"])
        self.assertNotEqual(before["base_fonte"], after["base_fonte"])

    def test_projecao_e_read_only(self):
        result = self.project("Antes")
        files = {p: p.read_bytes() for p in self.repo.rglob("*") if p.is_file()}
        pending = deepcopy(self.pending)
        self.assertEqual(result, causal.pending_context(self.repo, self.pending))
        self.assertEqual(pending, self.pending)
        self.assertEqual(files, {p: p.read_bytes() for p in self.repo.rglob("*") if p.is_file()})

    def test_causa_nao_pode_escapar_por_symlink(self):
        self.project("Antes")
        path = self.repo / self.source
        path.unlink()
        path.symlink_to("/etc/hosts")
        with self.assertRaises(ValueError):
            causal.pending_context(self.repo, self.pending)

    def test_lote_vazio_nao_le_fontes_de_acionamento(self):
        with patch.object(causal, "pending_context", side_effect=AssertionError("projeção indevida")), \
             patch.object(causal, "_read", side_effect=AssertionError("leitura causal indevida")):
            self.assertEqual(batch.prepare_batch(self.repo)["quantidade"], 0)


class CausalDependencyTest(unittest.TestCase):
    def test_mesmo_valor_nao_vira_acontecimento(self):
        document = {"id": "a", "ultima_sessao": 99, "relacao": {"vinculo": "Aliado"}}
        record = {"deltas": [{"alvo": "relacao:a", "op": "set", "caminho": "vinculo", "valor": "Aliado"}]}
        with patch.object(causal, "_read", return_value=document):
            self.assertFalse(causal._changed_source(Path("/fixture"), "estado/relacoes/a.yaml", [], record))

    def test_fonte_nao_assinada_nao_acorda_ninguem(self):
        deps = causal._dependencies(index_for())
        self.assertNotIn("estado/relacoes/desconhecido.yaml", deps)
        self.assertEqual(deps["estado/relacoes/a.yaml"], {"a"})

    def test_lista_alterada_e_detectada_inteira_sem_mutar_original(self):
        doc = {"id": "a", "relacao": {"marcos": ["antes"]}}
        before = deepcopy(doc)
        record = {"deltas": [{"alvo": "relacao:a", "op": "set", "caminho": "marcos", "valor": ["antes", "depois"]}]}
        with patch.object(causal, "_read", return_value=doc):
            self.assertTrue(causal._changed_source(Path("/fixture"), "estado/relacoes/a.yaml", [], record))
        self.assertEqual(doc, before)

    def test_varias_alteracoes_pendentes_usam_estado_efetivo(self):
        doc = {"id": "a", "relacao": {"vinculo": "Antigo"}}
        prior = [{"deltas": [{"alvo": "relacao:a", "op": "set", "caminho": "vinculo", "valor": "Novo"}]}]
        with patch.object(causal, "_read", return_value=doc):
            self.assertFalse(causal._changed_source(Path("/fixture"), "estado/relacoes/a.yaml", prior, prior[0]))
            different = {"deltas": [{"alvo": "relacao:a", "op": "set", "caminho": "vinculo", "valor": "Outro"}]}
            self.assertTrue(causal._changed_source(Path("/fixture"), "estado/relacoes/a.yaml", prior, different))

    def test_gate_neutro_tem_zero_leitura_e_zero_consulta_de_indice(self):
        with patch.object(causal, "configured", side_effect=AssertionError("índice indevido")), \
             patch.object(causal, "_read", side_effect=AssertionError("leitura indevida")):
            for deltas in ([], [{"alvo": "ficha", "op": "inc", "caminho": "x", "valor": 1}],
                           [{"alvo": "relacao:a", "visibilidade": "narrador"}]):
                self.assertIsNone(causal.checkpoint_trigger(Path("/ausente"), [], {"deltas": deltas}))

    def test_reconciliacao_legada_sem_camada_nao_consulta_indice(self):
        with patch.object(causal, "configured", return_value=False), \
             patch.object(causal, "_read", side_effect=AssertionError("leitura indevida")):
            state = world()
            self.assertIs(causal.reconcile(Path("/ausente"), state), state)


if __name__ == "__main__":
    unittest.main()
