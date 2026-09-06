"""Integração causal/temporal em campanha sintética, sem consultar o save vivo.

Usa o calendário, writer, journal, lote e CLI reais. Narração anotada não equivale
à avaliação de uma IA nem mede tokens nativos de um episódio.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import yaml

TOOLS = Path(__file__).resolve().parents[1] / "ferramentas"
sys.path.insert(0, str(TOOLS))
import acionamento_npcs as activation
import agentes_leves as light
import barreira_mundo as barrier
import checkpoint
import consolidar
import cronica
import fronteira_mundo
import memoria_duravel
import mundo
import resolver_fronteira as batch
import transacoes
import turno
import test_memoria_duravel_integracao as fixtures

DATE = "7 Eleasis, 1372 DR"


class CausalActivationIntegrationTest(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.DurableMemoryIntegrationTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.repo, self.write = fixture.repo, fixture.write
        self.people = list(fixture.people)
        self.silva, self.nera, self.luath = self.people
        entries, states = {}, {}
        for i, person in enumerate(self.people):
            source = f"estado/relacoes/{person}.yaml"
            doc = self.read(source)
            doc["relacao"]["rotina"] = "Cuida dos documentos (fixture)."
            self.write(source, doc)
            name = doc["relacao"]["nome"]
            rel = f"narrador/agentes-leves/{person}.yaml"
            evidence = {"descricao": "Rotina documental.", "fonte": source,
                        "evidencia": "Cuida dos documentos (fixture)."}
            self.write(rel, {"schema_agente_leve": 1, "natureza": "reservado", "id": person,
                             "nome": name, "perfil_operacional": "recorrente_leve",
                             "fontes_canonicas": [source], "rotina_padrao": evidence,
                             "objetivo_atual": evidence, "iniciativas_possiveis": [],
                             "regra_de_reavaliacao": "Avaliar apenas causas comprovadas."})
            entries[person] = {"nome": name, "perfil_operacional": "recorrente_leve",
                               "estado": "ativo", "prioridade": 9-i, "intervalo_dias": 1,
                               "inicio": {"data": DATE, "hora": "06:00"}, "arquivo": rel,
                               "fontes_causais": [source], "perfil_blob_git": light._git_blob_sha(self.repo / rel)}
            states[person] = {"estado": "ativo", "proxima_avaliacao": {"data": "8 Eleasis, 1372 DR", "hora": "06:00"},
                              "cache_negativo": None}
        self.write(activation.LIGHT_INDEX, {"schema_agentes_leves": 2, "natureza": "reservado",
                   "orcamento": {"max_novas_por_checkpoint": 1, "max_pendencias_abertas": 2,
                                 "max_checks_cache_negativo_por_checkpoint": 1,
                                 "ordenacao": "mais_atrasado_prioridade_id"}, "agentes": entries})
        self.write(activation.LIGHT_STATE, {"schema_estado_agentes_leves": 2,
                   "natureza": "controle_reservado", "agentes": states})
        self.write(activation.WORLD, {"schema_estado_mundo": 1, "natureza": "controle_reservado",
                   "processado_ate": {"data": DATE, "hora": "08:03"}, "pendencias": [], "concluidas_recentes": []})
        self.write(mundo.AGENDA_PATH.as_posix(), {"schema_agenda_mundo": 1, "natureza": "reservado",
                   "hora_amanhecer": "06:00", "reavaliacoes": {}, "agendamentos": []})
        time = self.read(mundo.TIME_PATH.as_posix())
        time["schema_tempo"] = 1
        self.write(mundo.TIME_PATH.as_posix(), time)
        barrier.sync(self.repo)

    def read(self, path):
        return yaml.safe_load((self.repo / path).read_text(encoding="utf-8"))

    def hashes(self):
        return {p.relative_to(self.repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.repo.rglob("*") if p.is_file()}

    def pending(self):
        return mundo.load_world_state(self.repo)["pendencias"]

    def transaction(self, tid="mudanca", *, person=None, deltas=None):
        person = person or self.silva
        return {"id": tid, "jogador": "Ren conversa sobre o mapa.", "narracao": "O relato do mapa chegou a Silva.",
                "resumo": "Relato entregue.", "modo": "interação",
                "deltas": deltas if deltas is not None else [
                    {"alvo": "relacao:" + person, "op": "set", "caminho": "relato_recebido",
                     "valor": {"texto": "A ponte talvez esteja fechada.", "estatuto": "rumor"}}]}

    def time_tx(self, hour="08:10", tid="tempo"):
        return self.transaction(tid, deltas=[{"alvo": "tempo", "op": "instante", "valor": {"data": DATE, "hora": hour}}])

    def install_commitment(self, cid="mapa", *, involved=None, hour="08:10"):
        doc = self.read(activation.STATE)
        doc.setdefault("compromissos", {})[cid] = {
            "tipo": "encontro", "resumo": "Encontrar-se para examinar o mapa.",
            "envolvidos": involved if involved is not None else ["ren", self.silva],
            "janela": {"inicio": {"data": DATE, "hora": hour}}}
        self.write(activation.STATE, doc)
        return doc["compromissos"][cid]

    def noop_payload(self, prepared):
        return {"lote_id": prepared["lote_id"], "sem_mudanca": [
            {"id": x["id"], "token": x["token"], "nota": "Relato incerto; mantém a rotina até verificar a fonte."}
            for x in prepared["itens"]]}

    def test_fixture_valida_perfis_e_mundo_sem_constantes_vivas(self):
        self.assertTrue(light.validate_repo(self.repo)["ok"])
        self.assertEqual(light.load_index(self.repo)["orcamento"]["max_pendencias_abertas"], 2)

    def test_writer_diurno_aciona_so_dependente_e_preserva_rumor(self):
        before = {p: (self.repo / f"estado/relacoes/{p}.yaml").read_bytes() for p in self.people}
        result = turno.register_transaction(self.repo, self.transaction())
        self.assertEqual(result["checkpoint_mundo"]["motivo"], "acontecimento_npc")
        self.assertEqual([p["agente_leve"] for p in self.pending()], [self.silva])
        projected = batch.prepare_batch(self.repo)
        self.assertIn("rumor", json.dumps(projected, ensure_ascii=False))
        self.assertEqual(projected["itens"][0]["classificacao"], "avaliar_condicao_concreta")
        for person in self.people[1:]:
            self.assertEqual((self.repo / f"estado/relacoes/{person}.yaml").read_bytes(), before[person])
        self.assertFalse(transacoes.load_pending(self.repo))
        self.assertTrue(barrier.load_status(self.repo)["bloqueado"])

    def test_antes_do_prazo_nao_aciona_e_minuto_exato_forca_checkpoint(self):
        self.install_commitment()
        first = turno.register_transaction(self.repo, self.time_tx("08:09", "antes"))
        self.assertIsNone(first["checkpoint_mundo"])
        self.assertFalse(self.pending())
        second = turno.register_transaction(self.repo, self.time_tx())
        self.assertEqual(second["checkpoint_mundo"]["motivo"], "prazo_npc")
        self.assertEqual(len(self.pending()), 1)
        self.assertEqual(self.pending()[0][activation.CAUSES][0]["fase"], "inicio")
        self.assertIn("mapa", self.read(activation.STATE)["compromissos"])

    def test_fronteira_exata_vence_fila_rotineira_cheia_sem_mutacao(self):
        self.install_commitment()
        state = mundo.load_world_state(self.repo)
        state["pendencias"] = [
            {"id": f"mundo-{i:016x}", "tipo": activation.KIND, "agente_leve": person,
             "disparado_em": {"data": DATE, "hora": "06:00"}, "origem": "rotina"}
            for i, person in enumerate(self.people[1:], 1)]
        self.write(activation.WORLD, state)
        before = self.hashes()
        result = fronteira_mundo.query(self.repo, DATE, "08:30")
        self.assertTrue(result["interromper"])
        self.assertEqual(result["fronteira"]["hora"], "08:10")
        self.assertEqual(result["fronteira"]["motivos"], [{"camada": "agentes_leves", "ids": [self.silva]}])
        self.assertEqual(before, self.hashes())

    def test_checkpoint_recovery_reapresenta_devido_sem_amanhecer(self):
        self.install_commitment(hour="08:03")
        checkpoint.sync_world(self.repo)
        ids = [p["id"] for p in self.pending()]
        self.assertEqual(len(ids), 1)
        checkpoint.sync_world(self.repo)
        self.assertEqual([p["id"] for p in self.pending()], ids)

    def test_mudanca_e_notificacao_entram_no_mesmo_journal(self):
        with patch.object(turno, "_run_scene_checkpoint", return_value={"mundo": {}}):
            turno.register_transaction(self.repo, self.transaction())
        before = self.hashes()
        plan = consolidar.build_plan(self.repo, "cena")
        self.assertEqual(before, self.hashes())
        self.assertIn(activation.WORLD, plan["outputs"])
        self.assertIn(activation.BARRIER, plan["outputs"])
        journal = consolidar.stage_plan(self.repo, plan)
        with self.assertRaises(consolidar.ConsolidationError):
            consolidar.install_staged(self.repo, journal, fail_after=1)
        consolidar.resume_consolidation(self.repo)
        self.assertEqual(len(self.pending()), 1)
        self.assertIn("relato_recebido", self.read(f"estado/relacoes/{self.silva}.yaml")["relacao"])
        self.assertTrue(barrier.load_status(self.repo)["bloqueado"])
        before = self.hashes()
        turno.register_transaction(self.repo, self.transaction())
        self.assertEqual(before, self.hashes())

    def test_retry_apos_checkpoint_e_frio_nao_duplica_acao_ou_notificacao(self):
        tx = self.transaction()
        turno.register_transaction(self.repo, tx)
        before = self.hashes()
        result = subprocess.run([sys.executable, str(TOOLS / "turno.py"), "--repo", str(self.repo), "registrar"],
                                input=json.dumps(tx), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, self.hashes())

    def test_preparo_de_lote_frio_e_somente_leitura(self):
        turno.register_transaction(self.repo, self.transaction())
        before = self.hashes()
        result = subprocess.run([sys.executable, str(TOOLS / "resolver_fronteira.py"), "--repo", str(self.repo), "preparar"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = yaml.safe_load(result.stdout)
        self.assertEqual(data["quantidade"], 1)
        self.assertIn("acionamento_npc", data["itens"][0]["contexto"])
        self.assertEqual(before, self.hashes())

    def test_lote_fecha_causa_instala_cache_e_retry_preserva_bytes(self):
        turno.register_transaction(self.repo, self.transaction())
        prepared = batch.prepare_batch(self.repo)
        payload = self.noop_payload(prepared)
        result = batch.apply_batch(self.repo, payload)
        self.assertEqual(result["quantidade_restante"], 0)
        self.assertFalse(barrier.load_status(self.repo)["bloqueado"])
        self.assertIsNotNone(light.load_state(self.repo)["agentes"][self.silva]["cache_negativo"])
        before = self.hashes()
        again = batch.apply_batch(self.repo, payload)
        self.assertEqual(len(again["ja_aplicadas"]), 1)
        self.assertEqual(before, self.hashes())

    def test_lote_obsoleto_recusa_todos_antes_da_primeira_escrita(self):
        turno.register_transaction(self.repo, self.transaction())
        prepared = batch.prepare_batch(self.repo)
        rel = f"estado/relacoes/{self.silva}.yaml"
        doc = self.read(rel)
        doc["relacao"]["fato_novo"] = "A fonte confirmou apenas uma parte."
        self.write(rel, doc)
        before = self.hashes()
        with self.assertRaises(batch.BatchBoundaryError):
            batch.apply_batch(self.repo, self.noop_payload(prepared))
        self.assertEqual(before, self.hashes())

    def test_noop_causal_exige_nota_e_nao_aceita_conclusao_generica(self):
        turno.register_transaction(self.repo, self.transaction())
        pid = self.pending()[0]["id"]
        before = self.hashes()
        with self.assertRaises(light.LightAgentError):
            light.conclude_noop(self.repo, pid)
        with self.assertRaises(barrier.WorldPendingBarrierError):
            barrier.conclude(self.repo, pid, "sem avaliação explícita")
        self.assertEqual(before, self.hashes())

    def test_tres_dependentes_coalescem_em_dois_slots_e_lote_reabastece(self):
        tx = self.transaction(deltas=[{"alvo": "relacao:" + p, "op": "set", "caminho": "aviso", "valor": "Relato recebido."}
                                      for p in self.people])
        turno.register_transaction(self.repo, tx)
        prepared = batch.prepare_batch(self.repo)
        self.assertEqual(prepared["quantidade"], 2)
        self.assertEqual(prepared["avaliacoes_npcs_adiadas"], 1)
        self.assertEqual(barrier.load_status(self.repo)["quantidade"], 3)
        result = batch.apply_batch(self.repo, self.noop_payload(prepared))
        self.assertEqual(result["quantidade_restante"], 1)
        self.assertTrue(barrier.load_status(self.repo)["bloqueado"])
        batch.apply_batch(self.repo, self.noop_payload(batch.prepare_batch(self.repo)))
        self.assertFalse(barrier.load_status(self.repo)["bloqueado"])

    def test_cache_valido_ainda_compacta_rotina_sem_ia_ou_fragmento(self):
        turno.register_transaction(self.repo, self.transaction())
        batch.apply_batch(self.repo, self.noop_payload(batch.prepare_batch(self.repo)))
        state = light.load_state(self.repo)
        state["agentes"][self.silva]["proxima_avaliacao"] = {"data": DATE, "hora": "06:00"}
        self.write(activation.LIGHT_STATE, state)
        with patch.object(light, "load_fragment", side_effect=AssertionError("perfil não deve ser aberto")):
            result = light.process_checkpoint(self.repo)
        self.assertEqual(result["novas_pendencias"], [])
        self.assertEqual(result["noops_compactados"][0]["agente_leve"], self.silva)

    def test_fato_novo_fura_cache_sem_esperar_revisao(self):
        turno.register_transaction(self.repo, self.transaction())
        batch.apply_batch(self.repo, self.noop_payload(batch.prepare_batch(self.repo)))
        tx = self.transaction("novo", deltas=[{"alvo": "relacao:" + self.silva, "op": "set", "caminho": "confirmacao", "valor": "A ponte está aberta."}])
        turno.register_transaction(self.repo, tx)
        self.assertEqual([x["agente_leve"] for x in self.pending()], [self.silva])

    def test_resolucao_com_mudanca_nao_preempta_a_propria_pendencia(self):
        turno.register_transaction(self.repo, self.transaction())
        pid = self.pending()[0]["id"]
        resolution = self.transaction("resolucao", deltas=[{"alvo": "relacao:" + self.silva, "op": "set", "caminho": "verificacao", "valor": "Silva verificou o relato e ainda não tem confirmação."}])
        resolution.pop("jogador")
        resolution["modo"] = "mundo"
        resolution["tags"] = [barrier.RESOLUTION_TAG_PREFIX + pid]
        turno.register_transaction(self.repo, resolution)
        self.assertEqual(self.pending()[0]["id"], pid)
        self.assertEqual(self.pending()[0][activation.RESOLUTION]["transacao"], "resolucao")
        with self.assertRaises(light.LightAgentError):
            light.conclude_noop(self.repo, pid, "não deve apagar resolução")
        barrier.conclude(self.repo, pid, "Verificação registrada e consolidada.")
        self.assertNotIn(pid, [p["id"] for p in self.pending()])
        self.assertEqual(len(self.pending()), 1)
        self.assertIn("verificacao", json.dumps(batch.prepare_batch(self.repo), ensure_ascii=False))

    def test_cancelamento_em_resolucao_nao_deixa_prazo_falso(self):
        self.install_commitment(hour="08:03")
        checkpoint.sync_world(self.repo)
        pid = self.pending()[0]["id"]
        tx = self.transaction("cancelado", deltas=[{"alvo": "estado", "op": "remove", "caminho": "compromissos.mapa"}])
        tx.pop("jogador")
        tx.update(modo="mundo", tags=[barrier.RESOLUTION_TAG_PREFIX + pid])
        turno.register_transaction(self.repo, tx)
        barrier.conclude(self.repo, pid, "Cancelamento explícito consolidado.")
        pending = self.pending()[0]
        self.assertTrue(all(c["fase"] == "removido" for c in pending[activation.CAUSES]))
        self.assertFalse(self.read(activation.WORLD)[activation.CONTROL]["prazos"])

    def test_promessa_nv04_usa_mesma_dupla_publica_e_aciona_sem_nova_porta(self):
        prepared = cronica.prepare(self.repo, scene_id="causa-fixture", sidequest_signal=None)
        tx = self.fixture.promise("promessa-publica")
        tx["memoria"]["fatos"][0]["compromisso"]["janela"] = {"inicio": {"data": DATE, "hora": "08:10"}}
        result = cronica.conclude(self.repo, prepared["ticket"], tx)
        cid = memoria_duravel.event_id("promessa-publica", "fato", 3)
        self.assertIn(cid, self.read(activation.STATE)["compromissos"])
        self.assertEqual([p["agente_leve"] for p in self.pending()], [self.silva])
        self.assertTrue(result["transacao"]["checkpoint_mundo"]["disparado"])
        self.assertEqual(len(self.pending()[0][activation.CAUSES]), 2)

    def test_compromisso_fora_do_recorte_quente_tambem_dispara(self):
        for i in range(14):
            self.install_commitment(f"lateral_{i}", involved=["ren"], hour="08:05")
        self.install_commitment("ultimo_relevante", hour="08:10")
        result = fronteira_mundo.query(self.repo, DATE, "08:11")
        self.assertEqual(result["fronteira"]["hora"], "08:10")
        turno.register_transaction(self.repo, self.time_tx())
        self.assertEqual(self.pending()[0][activation.CAUSES][0]["compromisso"], "ultimo_relevante")

    def test_turno_neutro_preserva_duas_escritas_sem_leituras_da_extensao(self):
        before = self.hashes()
        with patch.object(activation, "_index", side_effect=AssertionError("índice causal")), \
             patch.object(activation, "_read", side_effect=AssertionError("leitura causal")):
            result = turno.register_transaction(self.repo, self.transaction("neutro", deltas=[]))
        after = self.hashes()
        self.assertIsNone(result["checkpoint_mundo"])
        self.assertEqual({p for p in before.keys() | after.keys() if before.get(p) != after.get(p)},
                         {"runtime/eventos-pendentes.jsonl", "sessoes/003/transcricao.md"})

    def test_bytes_da_fronteira_sao_medidos_sem_declara_los_tokens(self):
        turno.register_transaction(self.repo, self.transaction())
        projected = batch.prepare_batch(self.repo)
        item = projected["itens"][0]["contexto"]["acionamento_npc"]
        size = len(yaml.safe_dump(item, allow_unicode=True, sort_keys=False).encode())
        self.assertLessEqual(size, activation.MAX_CONTEXT_BYTES)
        self.assertNotIn(f"narrador/agentes-leves/{self.nera}.yaml", projected["fontes_lidas"])
        print("NV07_BYTES=" + json.dumps({"lote_completo_yaml": len(yaml.safe_dump(projected, allow_unicode=True, sort_keys=False).encode()),
                                         "contexto_causal_yaml": size, "tokens_nativos": None}, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
