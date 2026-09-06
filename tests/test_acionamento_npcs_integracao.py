"""Integração da NV-07 reconciliada: uma fila, writer/journal/CLI reais.

Fixtures isoladas; nenhuma expectativa congela o save vivo. O antigo #120
esperava um segundo controle e autoavaliação recursiva. Agora as mesmas jornadas
usam o contrato já integrado pelo #119. Ver mapa de cobertura no manual.
"""
import ast
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
import cronica
import acionamentos_leves as activation
import agentes_leves as light
import barreira_mundo as barrier
import checkpoint
import consolidar
import _consolidar_core as consolidation_core
import fronteira_mundo
import memoria_duravel
import mundo
import resolver_fronteira as batch
import transacoes
import turno
import test_memoria_duravel_integracao as fixtures

DATE = "7 Eleasis, 1372 DR"
INFO = "informacoes_recebidas"


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
        self.write(activation.INDEX.as_posix(), {"schema_agentes_leves": 2, "natureza": "reservado",
                   "orcamento": {"max_novas_por_checkpoint": 1, "max_pendencias_abertas": 2,
                                 "max_checks_cache_negativo_por_checkpoint": 1,
                                 "ordenacao": "mais_atrasado_prioridade_id"}, "agentes": entries})
        self.write(activation.LIGHT_STATE.as_posix(), {"schema_estado_agentes_leves": 2,
                   "natureza": "controle_reservado", "agentes": states})
        self.write(activation.WORLD.as_posix(), {"schema_estado_mundo": 1, "natureza": "controle_reservado",
                   "processado_ate": {"data": DATE, "hora": "08:03"}, "pendencias": [], "concluidas_recentes": []})
        self.write(mundo.AGENDA_PATH.as_posix(), {"schema_agenda_mundo": 1, "natureza": "reservado",
                   "hora_amanhecer": "06:00", "reavaliacoes": {}, "agendamentos": []})
        time = self.read(mundo.TIME_PATH)
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

    def causes(self):
        return list(self.pending()[0][activation.PENDING_KEY].values())

    def transaction(self, tid="mudanca", *, person=None, deltas=None):
        person = person or self.silva
        # Informação usa o domínio de memória documentado, não um campo arbitrário
        # sem prioridade. O estatuto de rumor deve chegar intacto à avaliação.
        return {"id": tid, "jogador": "Ren conversa sobre o mapa.", "narracao": "O relato do mapa chegou a Silva.",
                "resumo": "Relato entregue.", "modo": "interação",
                "deltas": deltas if deltas is not None else [
                    {"alvo": "relacao:" + person, "op": "set", "caminho": INFO,
                     "valor": {"texto": "A ponte talvez esteja fechada.", "estatuto": "rumor"}}]}

    def time_tx(self, hour="08:10", tid="tempo"):
        return self.transaction(tid, deltas=[{"alvo": "tempo", "op": "instante", "valor": {"data": DATE, "hora": hour}}])

    def install_commitment(self, cid="mapa", *, involved=None, hour="08:10"):
        doc = self.read(activation.STATE)
        doc.setdefault("compromissos", {})[cid] = {
            "tipo": "encontro", "resumo": "Encontrar-se para examinar o mapa.",
            "envolvidos": involved if involved is not None else ["ren", self.silva],
            "janela": {"inicio": {"data": DATE, "hora": hour}}}
        self.write(activation.STATE.as_posix(), doc)
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
        tx = self.transaction()
        result = turno.register_transaction(self.repo, tx)
        self.assertEqual(result["checkpoint_mundo"]["motivo"], "acontecimento_relevante")
        self.assertEqual([p["agente_leve"] for p in self.pending()], [self.silva])
        projected = batch.prepare_batch(self.repo)
        item = projected["itens"][0]
        self.assertEqual(item["classificacao"], "avaliar_condicao_causal")
        memory = item["contexto"][activation.PENDING_KEY]["memoria_atual"]
        self.assertEqual(memory["itens"][self.silva]["relacao"]["dados"][INFO], tx["deltas"][0]["valor"])
        for person in self.people[1:]:
            self.assertEqual((self.repo / f"estado/relacoes/{person}.yaml").read_bytes(), before[person])
        self.assertFalse(transacoes.load_pending(self.repo))
        self.assertTrue(barrier.load_status(self.repo)["bloqueado"])
        self.assertNotIn("acionamento_npcs", self.read(activation.WORLD))

    def test_antes_do_prazo_nao_aciona_e_minuto_exato_forca_checkpoint(self):
        self.install_commitment()
        first = turno.register_transaction(self.repo, self.time_tx("08:09", "antes"))
        self.assertIsNone(first["checkpoint_mundo"])
        self.assertFalse(self.pending())
        second = turno.register_transaction(self.repo, self.time_tx())
        self.assertEqual(second["checkpoint_mundo"]["motivo"], "prazo_relevante")
        self.assertEqual(len(self.pending()), 1)
        self.assertEqual(self.causes()[0]["fase"], "inicio")
        self.assertIn("mapa", self.read(activation.STATE)["compromissos"])

    def test_fronteira_exata_vence_fila_rotineira_cheia_sem_mutacao(self):
        self.install_commitment()
        state = mundo.load_world_state(self.repo)
        state["pendencias"] = [
            {"id": f"mundo-{i:016x}", "tipo": "reavaliar_agente_leve", "agente_leve": person,
             "disparado_em": {"data": DATE, "hora": "06:00"}, "origem": "rotina"}
            for i, person in enumerate(self.people[1:], 1)]
        self.write(activation.WORLD.as_posix(), state)
        before = self.hashes()
        result = fronteira_mundo.query(self.repo, DATE, "08:30")
        self.assertTrue(result["interromper"])
        self.assertEqual(result["fronteira"]["hora"], "08:10")
        self.assertEqual(result["fronteira"]["motivos"], [{"camada": "agentes_leves", "ids": ["compromisso:mapa:inicio"]}])
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
        self.assertIn(activation.WORLD.as_posix(), plan["outputs"])
        self.assertIn(activation.BARRIER.as_posix(), plan["outputs"])
        journal = consolidar.stage_plan(self.repo, plan)
        with self.assertRaises(consolidar.ConsolidationError):
            consolidation_core.install_staged(self.repo, journal, fail_after=1)
        consolidar.resume_consolidation(self.repo)
        self.assertEqual(len(self.pending()), 1)
        self.assertIn(INFO, self.read(f"estado/relacoes/{self.silva}.yaml")["relacao"])
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
        self.assertIn(activation.PENDING_KEY, data["itens"][0]["contexto"])
        self.assertEqual(before, self.hashes())

    def test_lote_fecha_causa_instala_cache_e_retry_preserva_bytes(self):
        turno.register_transaction(self.repo, self.transaction())
        payload = self.noop_payload(batch.prepare_batch(self.repo))
        result = batch.apply_batch(self.repo, payload)
        self.assertEqual(result["quantidade_restante"], 0)
        self.assertFalse(barrier.load_status(self.repo)["bloqueado"])
        self.assertIsNotNone(light.load_state(self.repo)["agentes"][self.silva]["cache_negativo"])
        before = self.hashes()
        again = batch.apply_batch(self.repo, payload)
        self.assertEqual(len(again["ja_aplicadas"]), 1)
        self.assertEqual(before, self.hashes())

    def test_cli_lote_aplica_em_processo_novo_sem_herdar_importacoes(self):
        turno.register_transaction(self.repo, self.transaction())
        cmd = [sys.executable, str(TOOLS / "resolver_fronteira.py"), "--repo", str(self.repo)]
        prepared = subprocess.run([*cmd, "preparar"], capture_output=True, text=True)
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        payload = self.noop_payload(yaml.safe_load(prepared.stdout))
        applied = subprocess.run([*cmd, "aplicar"], input=json.dumps(payload), capture_output=True, text=True)
        self.assertEqual(applied.returncode, 0, applied.stderr)
        self.assertEqual(yaml.safe_load(applied.stdout)["quantidade_restante"], 0)
        self.assertEqual(self.pending(), [])
        self.assertFalse(barrier.load_status(self.repo)["bloqueado"])

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

    def test_noop_causal_exige_nota_e_motivo_concreto(self):
        turno.register_transaction(self.repo, self.transaction())
        pid = self.pending()[0]["id"]
        before = self.hashes()
        for note in (None, "curto", "Sem ação de Ren; nenhuma iniciativa foi realizada."):
            with self.subTest(note=note):
                with self.assertRaises(light.LightAgentError):
                    light.conclude_noop(self.repo, pid, note)
                with self.assertRaises(barrier.WorldPendingBarrierError):
                    barrier.conclude(self.repo, pid, note)
        self.assertEqual(before, self.hashes())

    def test_tres_dependentes_coalescem_em_dois_slots_e_lote_reabastece(self):
        tx = self.transaction(deltas=[{"alvo": "relacao:" + p, "op": "set", "caminho": INFO, "valor": "Relato recebido."}
                                      for p in self.people])
        turno.register_transaction(self.repo, tx)
        prepared = batch.prepare_batch(self.repo)
        self.assertEqual(prepared["quantidade"], 2)
        waiting = self.read(activation.WORLD)[activation.KEY]["aguardando"]
        self.assertEqual(len(waiting), 1)
        active = {p["agente_leve"] for p in self.pending()}
        self.assertEqual(active | set(waiting), set(self.people))
        self.assertFalse(active & set(waiting))
        self.assertEqual(barrier.load_status(self.repo)["quantidade"], 2)
        result = batch.apply_batch(self.repo, self.noop_payload(prepared))
        self.assertEqual(result["quantidade_restante"], 1)
        self.assertTrue(barrier.load_status(self.repo)["bloqueado"])
        self.assertEqual({p["agente_leve"] for p in self.pending()}, set(waiting))
        batch.apply_batch(self.repo, self.noop_payload(batch.prepare_batch(self.repo)))
        self.assertFalse(barrier.load_status(self.repo)["bloqueado"])
        self.assertEqual(self.read(activation.WORLD)[activation.KEY]["aguardando"], {})

    def test_cache_valido_ainda_compacta_rotina_sem_ia_ou_fragmento(self):
        turno.register_transaction(self.repo, self.transaction())
        batch.apply_batch(self.repo, self.noop_payload(batch.prepare_batch(self.repo)))
        state = light.load_state(self.repo)
        state["agentes"][self.silva]["proxima_avaliacao"] = {"data": DATE, "hora": "06:00"}
        self.write(activation.LIGHT_STATE.as_posix(), state)
        with patch.object(light, "load_fragment", side_effect=AssertionError("perfil não deve ser aberto")):
            result = light.process_checkpoint(self.repo)
        self.assertEqual(result["novas_pendencias"], [])
        self.assertEqual(result["noops_compactados"][0]["agente_leve"], self.silva)

    def test_fato_novo_fura_cache_sem_esperar_revisao(self):
        turno.register_transaction(self.repo, self.transaction())
        batch.apply_batch(self.repo, self.noop_payload(batch.prepare_batch(self.repo)))
        tx = self.transaction("novo", deltas=[{"alvo": "relacao:" + self.silva, "op": "set", "caminho": INFO, "valor": "A ponte está aberta."}])
        turno.register_transaction(self.repo, tx)
        self.assertEqual([x["agente_leve"] for x in self.pending()], [self.silva])

    def test_resolucao_preserva_id_sem_loop_e_notifica_outro_dependente(self):
        turno.register_transaction(self.repo, self.transaction())
        pid = self.pending()[0]["id"]
        index = light.load_index(self.repo)
        meta = index["agentes"][self.nera]
        meta["fontes_causais"].append(f"estado/relacoes/{self.silva}.yaml")
        profile = self.read(meta["arquivo"])
        profile["fontes_canonicas"] = list(meta["fontes_causais"])
        self.write(meta["arquivo"], profile)
        meta["perfil_blob_git"] = light._git_blob_sha(self.repo / meta["arquivo"])
        self.write(activation.INDEX.as_posix(), index)
        resolution = self.transaction("resolucao", deltas=[{"alvo": "relacao:" + self.silva, "op": "set", "caminho": INFO,
                       "valor": "Silva verificou o relato e ainda não tem confirmação."}])
        resolution.pop("jogador")
        resolution.update(modo="mundo", tags=[barrier.RESOLUTION_TAG_PREFIX + pid])
        result = turno.register_transaction(self.repo, resolution)
        self.assertTrue(result["checkpoint_mundo"]["disparado"])
        self.assertEqual([p["id"] for p in self.pending() if p["agente_leve"] == self.silva], [pid])
        self.assertEqual(self.read(f"estado/relacoes/{self.silva}.yaml")["relacao"][INFO], resolution["deltas"][0]["valor"])
        barrier.conclude(self.repo, pid, "Verificação registrada e consolidada.")
        self.assertEqual([p["agente_leve"] for p in self.pending()], [self.nera])
        before = self.hashes()
        turno.register_transaction(self.repo, resolution)
        self.assertEqual(before, self.hashes())

    def test_cancelamento_em_resolucao_nao_deixa_prazo_falso(self):
        self.install_commitment(hour="08:03")
        checkpoint.sync_world(self.repo)
        pid = self.pending()[0]["id"]
        tx = self.transaction("cancelado", deltas=[{"alvo": "estado", "op": "remove", "caminho": "compromissos.mapa"}])
        tx.pop("jogador")
        tx.update(modo="mundo", tags=[barrier.RESOLUTION_TAG_PREFIX + pid])
        turno.register_transaction(self.repo, tx)
        self.assertNotIn("mapa", self.read(activation.STATE).get("compromissos", {}))
        self.assertEqual(self.pending(), [])
        state = self.read(activation.WORLD)
        self.assertFalse(state[activation.KEY]["prazos"])
        completed = next(p for p in state["concluidas_recentes"] if p["id"] == pid)
        self.assertEqual(completed["resultado"], "gatilho_revogado")
        checkpoint.sync_world(self.repo)
        self.assertEqual(self.pending(), [])

    def test_promessa_nv04_usa_mesma_dupla_publica_e_aciona_sem_nova_porta(self):
        prepared = cronica.prepare(self.repo, scene_id="causa-fixture", sidequest_signal=None)
        tx = self.fixture.promise("promessa-publica")
        tx["memoria"]["fatos"][0]["compromisso"]["janela"] = {"inicio": {"data": DATE, "hora": "08:10"}}
        cid = memoria_duravel.event_id(tx["id"], tx["memoria"]["fatos"][0]["id"], 3)
        result = cronica.conclude(self.repo, prepared["ticket"], tx)
        self.assertIn(cid, self.read(activation.STATE)["compromissos"])
        self.assertEqual([p["agente_leve"] for p in self.pending()], [self.silva])
        self.assertTrue(result["checkpoint_mundo"]["disparado"])
        self.assertEqual(len(self.causes()), 2)
        self.assertEqual({c["fonte"] for c in self.causes()}, {
            f"estado/relacoes/{self.silva}.yaml", f"estado/estado-atual.yaml:compromissos.{cid}"})

    def test_compromisso_fora_do_recorte_quente_tambem_dispara(self):
        for i in range(14):
            self.install_commitment(f"lateral_{i}", involved=["ren"], hour="08:05")
        self.install_commitment("ultimo_relevante", hour="08:10")
        result = fronteira_mundo.query(self.repo, DATE, "08:11")
        self.assertEqual(result["fronteira"]["hora"], "08:10")
        turno.register_transaction(self.repo, self.time_tx())
        self.assertEqual(self.causes()[0]["compromisso"], "ultimo_relevante")

    def test_turno_neutro_preserva_duas_escritas_sem_leituras_da_extensao(self):
        before = self.hashes()
        with patch.object(activation, "_read", side_effect=AssertionError("leitura causal")), \
             patch.object(activation, "configured", side_effect=AssertionError("índice causal")):
            result = turno.register_transaction(self.repo, self.transaction("neutro", deltas=[]))
        after = self.hashes()
        self.assertIsNone(result["checkpoint_mundo"])
        self.assertEqual({p for p in before.keys() | after.keys() if before.get(p) != after.get(p)},
                         {"runtime/eventos-pendentes.jsonl", "sessoes/003/transcricao.md"})

    def test_bytes_da_fronteira_sao_medidos_sem_declara_los_tokens(self):
        turno.register_transaction(self.repo, self.transaction())
        projected = batch.prepare_batch(self.repo)
        item = projected["itens"][0]["contexto"][activation.PENDING_KEY]
        size = len(yaml.safe_dump(item, allow_unicode=True, sort_keys=False).encode())
        self.assertLessEqual(size, activation.MAX_CONTEXT_BYTES)
        self.assertNotIn(f"narrador/agentes-leves/{self.nera}.yaml", projected["fontes_lidas"])
        print("NV07_BYTES=" + json.dumps({"lote_completo_yaml": len(yaml.safe_dump(projected, allow_unicode=True, sort_keys=False).encode()),
                                         "contexto_causal_yaml": size, "tokens_nativos": None}, sort_keys=True))

    def test_overflow_rejeitado_antes_de_instalar_fatos_e_notificacoes(self):
        record = {"tipo": "encontro", "resumo": "Revisar o documento.", "envolvidos": [self.silva],
                  "janela": {"descricao": "Após o aviso."}}
        tx = self.transaction("muitas-causas", deltas=[
            {"alvo": "estado", "op": "set", "caminho": f"compromissos.mapa_{i}", "valor": deepcopy(record)}
            for i in range(activation.MAX_CAUSES_PER_AGENT + 1)])
        with patch.object(turno, "_run_scene_checkpoint", return_value={"mundo": {}}):
            turno.register_transaction(self.repo, tx)
        before = self.hashes()
        with self.assertRaises(consolidar.ConsolidationError):
            consolidar.build_plan(self.repo, "cena")
        self.assertEqual(before, self.hashes())
        self.assertEqual(self.pending(), [])

    def test_prazo_nao_ganha_duas_notificacoes_apos_checkpoint_e_recovery(self):
        self.install_commitment()
        turno.register_transaction(self.repo, self.time_tx())
        ids = [p["id"] for p in self.pending()]
        self.assertEqual(len(ids), 1)
        for _ in range(3):
            checkpoint.sync_world(self.repo)
            state = self.read(activation.WORLD)
            self.assertNotIn("acionamento_npcs", state)
            self.assertEqual([p["id"] for p in state["pendencias"]], ids)
            self.assertEqual(len(self.causes()), 1)
            self.assertEqual(set(state[activation.KEY]["prazos"]), {f"{self.silva}:mapa:inicio"})


class SingleEngineWiringTest(unittest.TestCase):
    def test_portas_operacionais_nao_importam_segundo_motor(self):
        # ROOT é necessário aqui: a propriedade é o wiring do código instalado,
        # nunca valores de campanha. Impede o merge híbrido de voltar silenciosamente.
        self.assertFalse((TOOLS / "acionamento_npcs.py").exists())
        for filename in ("turno.py", "checkpoint.py", "consolidar.py", "agentes_leves.py",
                         "barreira_mundo.py", "fronteira_mundo.py", "resolver_fronteira.py"):
            tree = ast.parse((TOOLS / filename).read_text(encoding="utf-8"))
            forbidden = [node for node in ast.walk(tree)
                         if (isinstance(node, ast.Name) and node.id == "acionamento_npcs")
                         or (isinstance(node, ast.Import) and any(a.name == "acionamento_npcs" for a in node.names))
                         or (isinstance(node, ast.ImportFrom) and node.module == "acionamento_npcs")]
            self.assertEqual(forbidden, [], filename)


if __name__ == "__main__":
    unittest.main()
