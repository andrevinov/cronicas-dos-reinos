"""Contratos puros/IO dirigido: fixtures sintéticas, nunca estado vivo da campanha."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ferramentas"))
import acionamento_npcs as activation


WHEN = {"data": "7 Eleasis, 1372 DR", "hora": "09:00"}


def index_for(names="abcd"):
    return {
        "schema_agentes_leves": 2,
        "orcamento": {"max_novas_por_checkpoint": 1, "max_pendencias_abertas": 2},
        "agentes": {name: {"estado": "ativo", "fontes_causais": [f"estado/relacoes/{name}.yaml"]}
                    for name in names},
    }


def world():
    return {"pendencias": [], "concluidas_recentes": []}


def routine(agent, number):
    return {"id": f"mundo-{number:016x}", "tipo": activation.KIND, "agente_leve": agent,
            "agentes_afetados": [], "disparado_em": dict(WHEN), "origem": f"agentes-leves:{agent}.cadencia"}


def source(agent="a", *, field="vinculo", version=1):
    name = f"estado/relacoes/{agent}.yaml"
    return {"chave": "fonte:" + name, "tipo": "fonte_alterada", "fonte": name,
            "campos": [["relacao", field]], "assinatura": activation.digest(version)}


def appointment(involved=("a",), hour="09:00"):
    return {"tipo": "encontro", "resumo": "Conversar sobre o mapa.", "envolvidos": list(involved),
            "janela": {"inicio": {**WHEN, "hora": hour}}}


class ActivationFixture(unittest.TestCase):
    def setUp(self):
        # Aqui a propriedade é roteamento/ordem, não a conversão do calendário.
        # A integração exercita o parser Harptos real sem este mock.
        self.clock = patch.object(activation, "_minute", lambda when: sum(int(x) * k for x, k in zip(when["hora"].split(":"), (60, 1))))
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.index = index_for()


class CausalQueueTest(ActivationFixture):
    def test_causa_precede_rotinas_sem_aumentar_dois_slots(self):
        state = world()
        state["pendencias"] = [routine("b", 1), routine("c", 2)]
        before = deepcopy(state)
        notices, _ = activation.due_notices(self.index, {"encontro": appointment()}, 540, {})
        result = activation.enqueue(state, self.index, notices, WHEN, "fato")
        self.assertEqual(len(result["pendencias"]), 2)
        self.assertEqual(result["pendencias"][0]["agente_leve"], "a")
        all_ids = {p["id"] for p in result["pendencias"] + activation.deferred(result)}
        self.assertTrue({p["id"] for p in before["pendencias"]} <= all_ids)
        self.assertEqual(len(activation.deferred(result)), 1)
        self.assertEqual(state, before)
        self.assertEqual(self.index["orcamento"]["max_novas_por_checkpoint"], 1)

    def test_mesmo_agente_coalesce_sem_trocar_id_rotineiro(self):
        state = world()
        state["pendencias"] = [routine("a", 1)]
        first = activation.enqueue(state, self.index, {"a": [source()]}, WHEN, "um")
        second = activation.enqueue(first, self.index, {"a": [source(field="acordo", version=2)]}, WHEN, "dois")
        self.assertEqual(len(second["pendencias"]), 1)
        self.assertEqual(second["pendencias"][0]["id"], state["pendencias"][0]["id"])
        cause = second["pendencias"][0][activation.CAUSES][0]
        self.assertEqual(cause["campos"], [["relacao", "acordo"], ["relacao", "vinculo"]])
        self.assertEqual(cause["assinatura"], source(version=2)["assinatura"])

    def test_replay_mesma_causa_e_deterministico_e_idempotente(self):
        notice = {"a": [source()]}
        first = activation.enqueue(world(), self.index, notice, WHEN, "um")
        self.assertEqual(first, activation.enqueue(first, self.index, notice, WHEN, "um"))
        self.assertEqual(first, activation.enqueue(world(), self.index, notice, WHEN, "um"))

    def test_conclusao_reabastece_adiadas_sem_amanhecer(self):
        notices = {a: [source(a)] for a in "abcd"}
        result = activation.enqueue(world(), self.index, notices, WHEN, "um")
        original = {p["id"] for p in result["pendencias"] + activation.deferred(result)}
        finished = []
        while result["pendencias"]:
            item = result["pendencias"].pop(0)
            result["concluidas_recentes"].append(item)
            finished.append(item["id"])
            result = activation.rebalance(result, self.index)
            self.assertLessEqual(len(result["pendencias"]), 2)
        self.assertEqual(set(finished), original)
        self.assertEqual(len(finished), len(original))
        self.assertEqual(activation.deferred(result), [])

    def test_acontecimento_compartilhado_chega_so_aos_assinantes(self):
        self.index["agentes"]["b"]["fontes_causais"] = ["estado/relacoes/a.yaml"]
        notices = activation.source_notices(self.index, {"estado/relacoes/a.yaml": {"relacao": {"a": 1}}},
                                            {"estado/relacoes/a.yaml": {"relacao": {"a": 2}}})
        self.assertEqual(set(notices), {"a", "b"})
        state = activation.enqueue(world(), self.index, notices, WHEN, "um")
        self.assertEqual({p["agente_leve"] for p in state["pendencias"]}, {"a", "b"})

    def test_inativo_nao_recebe_causa_nem_ocupa_slot(self):
        state = activation.enqueue(world(), self.index, {a: [source(a)] for a in "abc"}, WHEN, "um")
        self.index["agentes"][state["pendencias"][0]["agente_leve"]]["estado"] = "inativo"
        result = activation.rebalance(state, self.index)
        self.assertEqual(len(result["pendencias"]), 2)
        self.assertTrue(all(self.index["agentes"][p["agente_leve"]]["estado"] == "ativo" for p in result["pendencias"]))

    def test_fila_cheia_falha_sem_descartar_ou_mutar_entrada(self):
        names = [f"p{i}" for i in range(35)]
        index = index_for(names)
        state = world()
        before = deepcopy(state)
        with self.assertRaises(activation.NpcActivationError):
            activation.enqueue(state, index, {a: [source(a)] for a in names}, WHEN, "um")
        self.assertEqual(state, before)

    def test_resolucao_em_curso_nao_e_preemptada_por_efeito_proprio(self):
        state = activation.enqueue(world(), self.index, {"a": [source()]}, WHEN, "um")
        held = state["pendencias"][0]
        held[activation.RESOLUTION] = {"sessao": 3, "transacao": "acao"}
        incoming, _ = activation.due_notices(self.index, {"encontro": appointment(("a", "b", "c"))}, 540, {})
        result = activation.enqueue(state, self.index, incoming, WHEN, "dois")
        self.assertEqual(result["pendencias"][0]["id"], held["id"])
        self.assertEqual(result["pendencias"][0][activation.CAUSES], held[activation.CAUSES])
        self.assertTrue(any(p["agente_leve"] == "a" and p["id"] != held["id"] for p in activation.deferred(result)))

    def test_dominio_estrategico_nao_e_adiado_pela_fila_leve(self):
        state = world()
        strategic = {"id": "mundo-1111111111111111", "tipo": "reavaliar_agente", "agente": "vilao", "disparado_em": WHEN}
        state["pendencias"] = [strategic]
        result = activation.enqueue(state, self.index, {a: [source(a)] for a in "abcd"}, WHEN, "um")
        self.assertIn(strategic, result["pendencias"])
        self.assertTrue(all(p["tipo"] == activation.KIND for p in activation.deferred(result)))

    def test_neutro_nao_cria_controle_paralelo(self):
        state = world()
        state["pendencias"] = [routine("b", 1)]
        self.assertEqual(activation.rebalance(state, self.index), state)
        self.assertNotIn(activation.CONTROL, state)

    def test_corruptos_e_fontes_nao_declaradas_falham_fechado(self):
        valid = activation.enqueue(world(), self.index, {"a": [source()]}, WHEN, "um")
        bad_cases = []
        for value in (None, [], True):
            bad = deepcopy(valid)
            bad[activation.CONTROL] = value
            bad_cases.append(bad)
        bad = deepcopy(valid)
        bad["pendencias"][0][activation.CAUSES][0]["fonte"] = "segredo.yaml"
        bad_cases.append(bad)
        bad = deepcopy(valid)
        bad["pendencias"][0][activation.CAUSES][0]["executar_acao"] = True
        bad_cases.append(bad)
        for bad in bad_cases:
            with self.subTest(bad=bad), self.assertRaises(activation.NpcActivationError):
                activation.validate_state(bad, self.index)

    def test_id_repetido_entre_ativa_e_adiada_e_recusado(self):
        state = activation.enqueue(world(), self.index, {"a": [source()]}, WHEN, "um")
        state[activation.CONTROL]["adiadas"].append(deepcopy(state["pendencias"][0]))
        with self.assertRaisesRegex(activation.NpcActivationError, "repetida"):
            activation.validate_state(state, self.index)


class CausalDeadlineTest(ActivationFixture):
    def test_hora_exata_acorda_so_envolvido_registrado(self):
        records = {"encontro": appointment(("a", "ren", "A"))}
        before, _ = activation.due_notices(self.index, records, 539, {})
        due, receipts = activation.due_notices(self.index, records, 540, {})
        self.assertEqual(before, {})
        self.assertEqual(list(due), ["a"])
        self.assertEqual(receipts["encontro"]["entregues"], ["inicio:a"])
        self.assertNotIn("resultado", due["a"][0])

    def test_recibo_nao_depende_das_64_conclusoes_recentes(self):
        records = {"encontro": appointment()}
        _, receipts = activation.due_notices(self.index, records, 540, {})
        due, again = activation.due_notices(self.index, records, 600, receipts)
        self.assertEqual(due, {})
        self.assertEqual(again, receipts)

    def test_inicio_e_fim_disparam_uma_vez_cada_sem_concluir_promessa(self):
        record = appointment()
        record["janela"]["fim"] = {**WHEN, "hora": "10:00"}
        snapshot = deepcopy(record)
        start, receipts = activation.due_notices(self.index, {"encontro": record}, 540, {})
        end, receipts = activation.due_notices(self.index, {"encontro": record}, 600, receipts)
        self.assertEqual([c["fase"] for c in start["a"]], ["inicio"])
        self.assertEqual([c["fase"] for c in end["a"]], ["fim"])
        self.assertEqual(record, snapshot)
        self.assertEqual(activation.due_notices(self.index, {"encontro": record}, 601, receipts)[0], {})

    def test_janela_descritiva_nao_inventa_hora(self):
        record = appointment()
        record["janela"] = {"descricao": "Quando o barco chegar."}
        self.assertEqual(activation.due_notices(self.index, {"encontro": record}, 10000, {}), ({}, {}))

    def test_cancelamento_remove_recibo_e_reclassifica_prazo_pendente(self):
        records = {"encontro": appointment()}
        notices, receipts = activation.due_notices(self.index, records, 540, {})
        state = activation.enqueue(world(), self.index, notices, WHEN, "um")
        old_id = state["pendencias"][0]["id"]
        activation._refresh_commitment_causes(state, {})
        cause = state["pendencias"][0][activation.CAUSES][0]
        self.assertEqual(cause["fase"], "removido")
        self.assertEqual(state["pendencias"][0]["id"], old_id)
        self.assertEqual(activation.due_notices(self.index, {}, 600, receipts), ({}, {}))

    def test_substituicao_futura_invalida_recibo_sem_acionar_hora_antiga(self):
        records = {"encontro": appointment()}
        _, receipts = activation.due_notices(self.index, records, 540, {})
        records["encontro"] = appointment(hour="11:00")
        self.assertEqual(activation.due_notices(self.index, records, 600, receipts), ({}, {}))
        due, _ = activation.due_notices(self.index, records, 660, receipts)
        self.assertEqual(list(due), ["a"])

    def test_mudanca_de_envolvidos_notifica_antigos_e_novos(self):
        changes = activation.commitment_notices(self.index, {"encontro": appointment(("a",))},
                                               {"encontro": appointment(("b",))})
        self.assertEqual(set(changes), {"a", "b"})
        self.assertEqual(activation.commitment_notices(self.index, {}, {}), {})

    def test_dois_prazos_simultaneos_coalescem_por_agente(self):
        records = {"mapa": appointment(), "selo": appointment()}
        changes, _ = activation.due_notices(self.index, records, 540, {})
        result = activation.enqueue(world(), self.index, changes, WHEN, "um")
        self.assertEqual(len(result["pendencias"]), 1)
        self.assertEqual(len(result["pendencias"][0][activation.CAUSES]), 2)

    def test_recibo_malformado_nao_silencia_prazo(self):
        state = world()
        state[activation.CONTROL] = {"versao": 1, "adiadas": [], "prazos": {"encontro": {"assinatura": "falsa", "entregues": ["inicio:a"]}}}
        with self.assertRaises(activation.NpcActivationError):
            activation.validate_state(state, self.index)

    def test_inicio_e_fim_atrasados_nao_exigem_replay_dos_dias(self):
        record = appointment()
        record["janela"]["fim"] = {**WHEN, "hora": "10:00"}
        due, _ = activation.due_notices(self.index, {"encontro": record}, 100000, {})
        self.assertEqual(len(due["a"]), 2)


class CausalProjectionTest(ActivationFixture):
    def setUp(self):
        super().setUp()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.index_patch = patch.object(activation, "_index", return_value=self.index)
        self.index_mock = self.index_patch.start()
        self.addCleanup(self.index_patch.stop)

    def write(self, rel, value):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def project(self, doc):
        rel = "estado/relacoes/a.yaml"
        self.write(rel, doc)
        cause = source()
        cause["assinatura"] = activation.digest(doc)
        pending = routine("a", 1)
        pending[activation.CAUSES] = [cause]
        return pending, activation.project_pending(self.repo, pending)

    def test_mudanca_le_so_a_fonte_declarada_nao_outros_perfis(self):
        _, (result, sources) = self.project({"relacao": {"vinculo": "Aliado por escolha."}})
        self.assertEqual(sources, [activation.LIGHT_INDEX, "estado/relacoes/a.yaml"])
        self.assertEqual(result["causas"][0]["fatos"][0]["valor"], "Aliado por escolha.")
        self.assertEqual(result["autoridade"], "avaliacao_do_narrador_nao_conhecimento_do_npc")

    def test_rumor_preserva_estatuto_sem_transmitir_a_outro_npc(self):
        value = {"estatuto": "rumor", "texto": "A ponte teria caído."}
        pending, (result, _) = self.project({"relacao": {"vinculo": value}})
        self.assertEqual(result["causas"][0]["fatos"][0]["valor"], value)
        self.assertEqual(pending["agente_leve"], "a")
        self.assertNotIn("b", result)

    def test_fato_indivisivel_grande_exige_aprofundamento_sem_corte(self):
        _, (result, _) = self.project({"relacao": {"vinculo": "Um fato indivisível. " * 700}})
        self.assertLessEqual(len(activation._dump(result)), activation.MAX_CONTEXT_BYTES)
        self.assertIn("aprofundamento_necessario", result["causas"][0])
        self.assertNotIn("fatos", result["causas"][0])
        self.assertNotIn("…", json.dumps(result, ensure_ascii=False))

    def test_fonte_mudada_invalida_assinatura_do_contexto(self):
        pending, (before, _) = self.project({"relacao": {"vinculo": "Antes"}})
        self.write("estado/relacoes/a.yaml", {"relacao": {"vinculo": "Depois"}})
        after, _ = activation.project_pending(self.repo, pending)
        self.assertNotEqual(before["assinatura_conjunto"], after["assinatura_conjunto"])
        self.assertTrue(after["causas"][0]["fonte_alterada_desde_acionamento"])

    def test_delecao_e_explicita_nao_string_none(self):
        _, (result, _) = self.project({"relacao": {}})
        self.assertEqual(result["causas"][0]["fatos"][0], {"campo": ["relacao", "vinculo"], "existe": False})

    def test_projecao_e_read_only(self):
        pending, (before, _) = self.project({"relacao": {"vinculo": "Antes"}})
        files = {p: p.read_bytes() for p in self.repo.rglob("*") if p.is_file()}
        source_pending = deepcopy(pending)
        after, _ = activation.project_pending(self.repo, pending)
        self.assertEqual(before, after)
        self.assertEqual(pending, source_pending)
        self.assertEqual(files, {p: p.read_bytes() for p in self.repo.rglob("*") if p.is_file()})

    def test_causa_nao_pode_escapar_por_symlink(self):
        pending, _ = self.project({"relacao": {"vinculo": "Antes"}})
        path = self.repo / "estado/relacoes/a.yaml"
        path.unlink()
        path.symlink_to("/etc/hosts")
        with self.assertRaises(activation.NpcActivationError):
            activation.project_pending(self.repo, pending)

    def test_sem_causa_nao_le_indices_ou_fontes(self):
        with patch.object(activation, "_read", side_effect=AssertionError("leitura indevida")):
            self.assertEqual(activation.project_pending(self.repo, routine("a", 1)), ({}, []))
        self.index_mock.assert_not_called()


class CausalDependencyTest(ActivationFixture):
    def test_metadados_nao_viram_evento(self):
        src = "estado/relacoes/a.yaml"
        old = {src: {"schema_relacao": 2, "relacao": {"vinculo": "Aliado"}}}
        new = deepcopy(old)
        new[src]["ultima_sessao"] = 999
        self.assertEqual(activation.source_notices(self.index, old, new), {})

    def test_fonte_nao_assinada_nao_acorda_ninguem(self):
        src = "estado/relacoes/desconhecido.yaml"
        self.assertEqual(activation.source_notices(self.index, {src: {}}, {src: {"x": 1}}), {})

    def test_lista_e_tratada_como_fato_inteiro(self):
        src = "estado/relacoes/a.yaml"
        notices = activation.source_notices(self.index, {src: {"relacao": {"memorias": ["antes"]}}},
                                            {src: {"relacao": {"memorias": ["antes", "depois"]}}})
        self.assertEqual(notices["a"][0]["campos"], [["relacao", "memorias"]])

    def test_muitos_campos_preservam_endereco_pai_sem_descartar(self):
        src = "estado/relacoes/a.yaml"
        notices = activation.source_notices(self.index, {src: {"relacao": {}}},
                                            {src: {"relacao": {f"p{i}": i for i in range(20)}}})
        self.assertEqual(notices["a"][0]["campos"], [["relacao"]])

    def test_gate_neutro_tem_zero_leitura_e_zero_consulta_de_indice(self):
        with patch.object(activation, "_index", side_effect=AssertionError("índice indevido")), \
             patch.object(activation, "_read", side_effect=AssertionError("leitura indevida")):
            self.assertFalse(activation.changed_dependency(Path("/ausente"), {"deltas": []}))
            self.assertFalse(activation.changed_dependency(Path("/ausente"), {"deltas": [{"alvo": "ficha", "op": "inc", "caminho": "x", "valor": 1}]}))
            self.assertFalse(activation.changed_dependency(Path("/ausente"), {"deltas": [{"alvo": "relacao:a", "visibilidade": "narrador"}]}))

    def test_refill_sem_controle_nao_consulta_indice(self):
        with patch.object(activation, "_index", side_effect=AssertionError("índice indevido")):
            state = world()
            self.assertIs(activation.refill(Path("/ausente"), state), state)


if __name__ == "__main__":
    unittest.main()
