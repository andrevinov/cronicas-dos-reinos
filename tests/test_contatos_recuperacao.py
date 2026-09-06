"""Integração e recuperação de contatos; somente cenários temporários anotados."""
from copy import deepcopy
import json
import subprocess
import sys
from unittest.mock import patch

import yaml

from test_contatos_sociais import ContactFixture, TOOLS, DATE
import contatos_sociais as contacts
import cronica
import planos_personagens as plans
import mundo
import turno
import transacoes
import consolidar
import _consolidar_core as core
import barreira_mundo as barrier
import memoria_duravel


class ContactRecoveryTest(ContactFixture):
    def test_entrega_e_recibo_sao_recuperados_pelo_journal_existente(self):
        self.ready(); p = self.prepare(); tx = self.tx(p)
        with patch.object(turno, "_run_scene_checkpoint", return_value={}):
            cronica.conclude(self.repo, p["ticket"], tx)
        with self.assertRaises(core.ConsolidationError):
            consolidar.consolidate(self.repo, "cena", fail_after=3)
        before = self.hashes()
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(before, self.hashes())
        consolidar.consolidate(self.repo, "cena")
        barrier.sync(self.repo)
        self.assertEqual(self.plan()["estado"], contacts.WAITING)
        self.assertEqual(len(mundo.load_world_state(self.repo)[contacts.RECEIPTS]), 1)
        self.assertEqual(self.read(self.source)["npc"]["recursos"]["moedas"], 2)
        before = self.hashes()
        cronica.conclude(self.repo, p["ticket"], tx)
        self.assertEqual(before, self.hashes())

    def test_conclusao_interrompida_antes_checkpoint_nao_reoferece_mensagem(self):
        self.ready(); p = self.prepare(); tx = self.tx(p)
        with patch.object(turno, "_run_scene_checkpoint", side_effect=RuntimeError("interrupção")):
            with self.assertRaises(RuntimeError): cronica.conclude(self.repo, p["ticket"], tx)
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "interrompida"): self.prepare()
        self.assertEqual(before, self.hashes())
        cronica.conclude(self.repo, p["ticket"], tx)
        self.assertEqual(self.plan()["estado"], contacts.WAITING)
        self.assertFalse(transacoes.load_pending(self.repo))
        self.assertNotIn(contacts.TICKET_KEY, self.prepare())

    def test_retry_frio_pela_cli_nao_ressuscita_contato(self):
        self.ready(); p = self.prepare(); tx = self.tx(p)
        args = [sys.executable, str(TOOLS / "cronica.py"), "--repo", str(self.repo), "concluir", "--ticket", p["ticket"]]
        first = subprocess.run(args, input=json.dumps(tx), text=True, capture_output=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self.hashes()
        again = subprocess.run(args, input=json.dumps(tx), text=True, capture_output=True)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertTrue(yaml.safe_load(again.stdout)["transacao"]["ja_registrada"])
        self.assertEqual(before, self.hashes())

    def test_retry_antigo_apos_saida_nao_teletransporta_aliado(self):
        self.ready(); p = self.prepare(); tx = self.tx(p)
        cronica.conclude(self.repo, p["ticket"], tx)
        doc = self.read(self.source); doc["npc"]["presenca"]["local"] = "Casa"; self.write(self.source, doc)
        state = self.read("estado/estado-atual.yaml")
        state["estado_narrativo"]["elenco_cena"]["participantes"] = []
        self.write("estado/estado-atual.yaml", state)
        before = self.hashes()
        cronica.conclude(self.repo, p["ticket"], tx)
        self.assertEqual(before, self.hashes())

    def test_marca_nv04_coexiste_com_contato_e_seu_replay(self):
        self.ready(); p = self.prepare(); tx = self.tx(p)
        text = "Ren agradeceu o convite à escriba."
        tx["narracao"] += " " + text
        tx["memoria"] = {"versao": 1, "fatos": [{"id": "agradecimento", "tipo": "marco",
            "participantes": ["ren", self.actor], "texto": text, "evidencia": {"campo": "narracao", "trecho": text}}]}
        cronica.conclude(self.repo, p["ticket"], tx)
        self.assertEqual(self.plan()["estado"], contacts.WAITING)
        relation = self.read(f"estado/relacoes/{self.actor}.yaml")["relacao"]
        self.assertIn(text, json.dumps(relation, ensure_ascii=False))
        before = self.hashes()
        cronica.conclude(self.repo, p["ticket"], tx)
        self.assertEqual(before, self.hashes())

    def test_desistencia_apos_recusa_nao_reabre_mesma_necessidade(self):
        self.ready(); p = self.prepare(); cronica.conclude(self.repo, p["ticket"], self.tx(p))
        # A resposta/escolha é um fato narrado, nunca inferido da entrega.
        fact = "A escriba desistiu do convite depois da recusa de Ren."
        tx = {"id": "desistir-convite", "modo": "mundo", "narracao": fact, "resumo": fact,
            "deltas": [{"alvo": "plano:documentos", "op": "registrar", "visibilidade": "narrador",
                "valor": {"evento": "desistir", "revisao": self.plan()["revisao"], "fato": fact, "motivo": fact}}]}
        turno.register_transaction(self.repo, tx)
        self.assertEqual(self.plan()["estado"], "desistiu")
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "já foi comunicada"):
            self.define("repetido", step=deepcopy(self.plan()["passo"]))
        self.assertEqual(before, self.hashes())

    def test_chegada_por_writer_publico_torna_contato_elegivel(self):
        self.ready(origin="Circo", dest="Casa")
        state = self.read("estado/estado-atual.yaml"); state["localizacao"]["area"] = "Casa"
        self.write("estado/estado-atual.yaml", state)
        p = self.prepare()
        self.assertNotIn(contacts.TICKET_KEY, p)
        self.assertEqual(p["contatos_adiados"]["quantidade"], 1)
        tx = {"id": "chegada-escriba", "modo": "mundo", "narracao": "A escriba concluiu o trajeto até a casa.",
            "resumo": "Chegada após o trajeto.", "deltas": [{"alvo": "npc:" + self.actor,
                "op": "set", "caminho": "presenca.local", "valor": "Casa"}]}
        cronica.conclude(self.repo, p["ticket"], tx)
        # NV07 preserva a notificação legítima da mudança de presença. Ela é
        # decidida no lote existente; não pode ser descartada para forçar contato.
        import resolver_fronteira
        prepared = resolver_fronteira.prepare_batch(self.repo)
        causal = [item for item in prepared["itens"] if item["tipo"] == "reavaliar_agente_leve"]
        self.assertEqual(len(causal), 1)
        resolver_fronteira.apply_batch(self.repo, {"lote_id": prepared["lote_id"], "sem_mudanca": [
            {"id": item["id"], "token": item["token"],
             "nota": "A chegada já registrada pertence ao contato em curso; não existe outra necessidade a resolver."}
            for item in causal]})
        before = self.hashes()
        self.assertIn(contacts.TICKET_KEY, self.prepare())
        self.assertEqual(before, self.hashes())


class ContactBoundarySafetyTest(ContactFixture):
    def test_sem_autoridade_instalada_conserva_barreira_sem_ler_memoria(self):
        (self.repo / mundo.WORLD_STATE_PATH).unlink()
        with patch.object(plans.View, "read", side_effect=AssertionError("não ler memória")):
            self.assertIsNone(contacts.partition_gate(self.repo))

    def test_evento_direto_sem_mensagem_literal_e_recusado(self):
        self.ready(); p = self.prepare(); tx = self.tx(p)
        payload = cronica.decode_ticket(p["ticket"])
        tx = cronica._scene_memory.compile_cast(payload, tx, repo=self.repo)
        raw, _ = contacts.compile_conclusion(self.repo, payload, tx)
        raw["narracao"] = tx[contacts.TICKET_KEY]["evidencia"]
        record = transacoes.build_pending_record(raw, 3)
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "mensagem"):
            plans.validate_registration(self.repo, raw, record, [])
        self.assertEqual(before, self.hashes())

    def test_movimento_do_portador_no_mesmo_lote_nao_prova_chegada(self):
        self.ready(messenger=True); p = self.prepare(); tx = self.tx(p)
        tx["deltas"] = [{"alvo": "npc:" + self.people[2], "op": "set", "caminho": "presenca.local", "valor": "Outra cidade"}]
        before = self.hashes()
        with self.assertRaises(ValueError): cronica.conclude(self.repo, p["ticket"], tx)
        self.assertEqual(before, self.hashes())

    def test_aguarda_resposta_sem_recibo_nao_silencia_pendencia(self):
        self.ready(); world = mundo.load_world_state(self.repo)
        plan = world[plans.KEY]["documentos"]; plan["estado"] = contacts.WAITING; plan["pendencia_id"] = None
        with self.assertRaisesRegex(ValueError, "recibo"): plans._control(world)

    def test_recibo_corrompido_ou_excedido_falha_sem_descartar(self):
        for key in ("z" * 24, "abc"):
            with self.assertRaises(ValueError): contacts.receipts({contacts.RECEIPTS: {key: {}}})
        receipt = {"plano": "documentos", "transacao": "tx", "cena_id": "contato", "sessao": 3}
        world = {contacts.RECEIPTS: {f"{i:024x}": receipt for i in range(contacts.MAX_RECEIPTS + 1)}}
        original = deepcopy(world)
        with self.assertRaisesRegex(ValueError, "teto"): contacts.receipts(world)
        self.assertEqual(original, world)

    def test_leituras_sao_dirigidas_sem_biografia_de_terceiro(self):
        self.ready(); observed = []
        original = plans.View.read
        def tracked(view, source):
            observed.append(str(source))
            return original(view, source)
        with patch.object(plans.View, "read", tracked): self.prepare()
        self.assertFalse(any(self.people[1] in s or self.people[2] in s for s in observed))
        self.assertFalse(any(s.startswith("sessoes/") for s in observed))

    def test_symlink_na_fonte_de_canal_nao_escapa_do_repo(self):
        self.ready(); path = self.repo / self.source
        path.unlink(); path.symlink_to("/etc/passwd")
        before = self.hashes()
        p = self.prepare()
        self.assertNotIn(contacts.TICKET_KEY, p)
        self.assertTrue(p["contatos_adiados"]["diagnostico"])
        self.assertEqual(before, self.hashes())

    def test_interlocutor_desconhecido_nao_apaga_elenco_na_retomada(self):
        self.ready(); state = self.read("estado/estado-atual.yaml")
        state["estado_narrativo"]["elenco_cena"] = None; self.write("estado/estado-atual.yaml", state)
        p = self.prepare(); cronica.conclude(self.repo, p["ticket"], self.tx(p))
        self.assertIsNone(self.read("estado/estado-atual.yaml")["estado_narrativo"]["elenco_cena"])
        self.assertEqual(self.plan()["estado"], contacts.WAITING)

    def test_contrato_mecanico_nao_e_interrompido_por_contato(self):
        self.ready(); p = cronica._hot.prepare(self.repo, scene_id="contato")
        payload = cronica.decode_ticket(p["ticket"]); payload["mecanica_cronica"] = {"fixture": True}
        p["ticket"], p["ticket_id"] = cronica.encode_ticket(payload)
        with patch.object(contacts, "delivery", side_effect=AssertionError("não consultar aliado")):
            out = contacts.prepare(self.repo, p, mundo.pending_view(self.repo)["pendencias"],
                decode_ticket=cronica.decode_ticket, encode_ticket=cronica.encode_ticket, max_output_bytes=8192)
        self.assertNotIn(contacts.TICKET_KEY, out)
        self.assertEqual(out["contatos_adiados"]["motivo"], "prioridade_superior")


class ContactMixedPressureTest(ContactFixture):
    def test_operacoes_reais_tem_precedencia_em_fila_mista_sem_apagar_contato(self):
        import shutil
        import operacoes_concorrentes as operations
        import pressao_narrativa as pressure
        from tests.test_concurrent_world_operations import ConcurrentOperationFixture
        self.ready()
        operation_fixture = ConcurrentOperationFixture()
        operation_fixture.setUp()
        self.addCleanup(operation_fixture.tearDown)
        group, _ = operation_fixture.materialize_group()
        operations.commit_group(operation_fixture.repo, group["grupo_operacoes_id"])
        # Composição de dois cenários isolados, nunca cópia do estado vivo.
        shutil.copytree(operation_fixture.repo / operations.ROOT, self.repo / operations.ROOT)
        world = mundo.load_world_state(self.repo)
        world["pendencias"].extend(mundo.pending_view(operation_fixture.repo)["pendencias"])
        self.write(mundo.WORLD_STATE_PATH, world)
        time = self.read(mundo.TIME_PATH)
        time.update({"data_atual": "10 Eleasis, 1372 DR", "hora_aproximada": "18:00"})
        self.write(mundo.TIME_PATH, time)
        state = self.read("estado/estado-atual.yaml")
        state["tempo"].update({"data_exata": "10 Eleasis, 1372 DR", "hora_aproximada": "18:00"})
        self.write("estado/estado-atual.yaml", state)
        barrier.sync(self.repo)
        before = self.hashes()
        with patch.object(contacts, "delivery", side_effect=AssertionError("não avaliar aliado sob ameaça")):
            p = self.prepare()
        self.assertEqual(before, self.hashes())
        self.assertNotIn(contacts.TICKET_KEY, p)
        self.assertEqual(len(p["pressao_narrativa"]["itens"]), 2)
        meta = cronica.decode_ticket(p["ticket"])[pressure.TICKET_KEY]
        tx = {"id": "fila-mista", "modo": "interação", "jogador": "Ren observa o pátio.",
              "narracao": "O pátio permanece tranquilo; o que está distante não foi percebido.",
              "resumo": "Situação remota continua sem conhecimento gratuito.", "deltas": [],
              pressure.TRANSACTION_KEY: {"resultados": [
                  {"pressao_id": row["pressao_id"], "resultado": "continua"} for row in meta["itens"]]}}
        cronica.conclude(self.repo, p["ticket"], tx)
        self.assertEqual(len(mundo.pending_view(self.repo)["pendencias"]), 3)
        self.assertEqual(self.plan()["estado"], "tentou")
        for op in ("ataque_comitiva", "extracao_testemunha"):
            self.assertEqual(operations._operation_context(self.repo, op)[2]["estado"], "comprometida")
