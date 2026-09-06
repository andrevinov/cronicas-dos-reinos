"""NV-09 em fixtures: contato real, transporte, prioridade e replay sem save vivo."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ferramentas"))
import contatos_sociais as contacts
import cronica
import memoria_cena
import mundo
import planos_personagens as plans
import resolver_fronteira as batch
import transacoes
import turno
import barreira_mundo as barrier
import consolidar
import _consolidar_core as core
from test_planos_personagens import PlanFixture, DATE

TOOLS = Path(__file__).resolve().parents[1] / "ferramentas"


class ContactFixture(PlanFixture):
    def setUp(self):
        super().setUp()
        self.message = "Venha tomar chá comigo quando tiver um momento."
        state = self.read("estado/estado-atual.yaml")
        state["localizacao"].update({"area": "Circo", "ponto_exato": "pátio"})
        state["estado_narrativo"] = {"elenco_cena": {"versao": 1, "cena_id": "contato",
            "local": memoria_cena.location(state), "participantes": []}}
        self.write("estado/estado-atual.yaml", state)
        for aid in self.people:
            doc = self.read(f"estado/npcs/{aid}.yaml")
            doc["npc"].update({"necessidades": {"companhia": "Deseja companhia para o chá."},
                "canais_contato": {"circo": {"meio": "presencial", "origem": "Circo", "destino": "Circo",
                    "portador": None, "duracao_minima_minutos": 0, "conhecimento_id": "documentos", "disponivel": True}}})
            self.write(f"estado/npcs/{aid}.yaml", doc)

    def contact_step(self, *, aid=None, modality="convite", messenger=False, origin="Circo", dest="Circo", duration=5):
        aid = aid or self.actor
        source = f"estado/npcs/{aid}.yaml"
        doc = self.read(source)
        channel = {"meio": "mensageiro" if messenger else "presencial", "origem": origin, "destino": dest,
            "portador": self.people[2] if messenger else None, "duracao_minima_minutos": duration if messenger or origin != dest else 0,
            "conhecimento_id": "documentos", "disponivel": True}
        doc["npc"]["canais_contato"]["circo"] = channel
        doc["npc"]["presenca"]["local"] = origin
        self.write(source, doc)
        step = self.step(actor=aid)
        step.update({"id": "convidar", "acao": "Procurar companhia para o chá.", "local": origin,
            "duracao_minutos": duration, "resolucao": {"tipo": "contato", "modalidade": modality,
                "mensagem": self.message, "causa": self.ref("necessidades.companhia", doc["npc"]["necessidades"]["companhia"], source),
                "canal": self.ref("canais_contato.circo", channel, source)}})
        return step

    def ready(self, pid="documentos", **kwargs):
        self.define(pid, step=self.contact_step(**kwargs), actor=kwargs.get("aid"))
        self.attempt(pid=pid)
        self.advance()

    def prepare(self, **kwargs):
        return cronica.prepare(self.repo, scene_id=kwargs.pop("scene_id", "contato"), sidequest_signal=None, **kwargs)

    def tx(self, prepared, *, outcome="entregue", tid="contato-entregue"):
        selected = prepared[contacts.TICKET_KEY]
        evidence = "A aliada iniciou a conversa por vontade própria."
        block = {"plano_id": selected["plano_id"], "resultado": outcome, "evidencia": evidence}
        if outcome == "adiado":
            block.update({"motivo": "A conversa presente ainda exige atenção.", "retomar_em": {"data": DATE, "hora": "08:20"}})
        return {"id": tid, "modo": "interação", "jogador": "Ren observa o pátio.",
            "narracao": evidence + " " + selected["mensagem"], "resumo": "Contato do aliado, sem aceite presumido.",
            contacts.TICKET_KEY: block, "deltas": []}

    def contact_plans(self):
        return mundo.load_world_state(self.repo)[plans.KEY]


class EffectiveContactTest(ContactFixture):
    def test_aliado_inicia_sem_ren_procurar_e_registra_mensagem_e_elenco(self):
        self.ready()
        before = self.hashes()
        prepared = self.prepare()
        self.assertEqual(self.hashes(), before)
        self.assertEqual(prepared[contacts.TICKET_KEY]["npc_id"], self.actor)
        self.assertEqual(prepared["pressao_narrativa"]["itens"][0]["tipo"], "iniciativa_social")
        tx = self.tx(prepared)
        cronica.conclude(self.repo, prepared["ticket"], tx)
        plan = self.plan()
        self.assertEqual(plan["estado"], "aguarda_resposta")
        self.assertEqual(plan["ultima_tentativa"]["resultado"]["resultado"], "contato_entregue")
        self.assertEqual(plan["ultima_tentativa"]["resultado"]["resposta_de_ren"], "nao_presumida")
        self.assertFalse(mundo.pending_view(self.repo)["pendencias"])
        state = self.read("estado/estado-atual.yaml")
        self.assertEqual(state["estado_narrativo"]["elenco_cena"]["participantes"], [self.actor])
        knowledge = list((self.repo / "personagens/jogador/conhecimento/incrementais").rglob("*.md"))
        self.assertTrue(any(self.message in p.read_text() for p in knowledge))
        self.assertFalse(state.get("compromissos"))
        self.assertNotIn(contacts.TICKET_KEY, self.prepare())

    def test_mensageiro_entrega_sem_trazer_remetente_para_elenco(self):
        self.ready(messenger=True, origin="Circo", dest="Circo")
        doc = self.read(self.source)
        doc["npc"]["presenca"]["local"] = "Casa"
        self.write(self.source, doc)
        prepared = self.prepare()
        self.assertEqual(prepared[contacts.TICKET_KEY]["meio"], "mensageiro")
        cronica.conclude(self.repo, prepared["ticket"], self.tx(prepared))
        state = self.read("estado/estado-atual.yaml")
        self.assertEqual(state["estado_narrativo"]["elenco_cena"]["participantes"], [self.people[2]])
        self.assertEqual(self.read(self.source)["npc"]["presenca"]["local"], "Casa")
        self.assertEqual(self.read(self.source)["npc"]["recursos"]["moedas"], 2)

    def test_procurar_exige_chegada_real_apos_transporte(self):
        self.ready(origin="Circo", dest="Casa")
        state = self.read("estado/estado-atual.yaml")
        state["localizacao"]["area"] = "Casa"
        self.write("estado/estado-atual.yaml", state)
        self.assertNotIn(contacts.TICKET_KEY, self.prepare())
        # Chegada é um fato independente, não efeito automático de cronica preparar.
        doc = self.read(self.source)
        doc["npc"]["presenca"]["local"] = "Casa"
        self.write(self.source, doc)
        self.assertIn(contacts.TICKET_KEY, self.prepare())

    def test_duas_iniciativas_um_slot_e_restante_preservada(self):
        self.define(step=self.contact_step())
        self.define("segunda", actor=self.people[1], step=self.contact_step(aid=self.people[1]))
        p = self.payload()
        p["planos"].extend(self.payload(pid="segunda")["planos"])
        batch.apply_batch(self.repo, p)
        self.advance()
        prepared = self.prepare()
        self.assertEqual(len(prepared["pressao_narrativa"]["itens"]), 1)
        chosen = prepared[contacts.TICKET_KEY]["plano_id"]
        cronica.conclude(self.repo, prepared["ticket"], self.tx(prepared))
        self.assertEqual(len(mundo.pending_view(self.repo)["pendencias"]), 1)
        self.assertNotIn(contacts.TICKET_KEY, self.prepare())
        second = self.prepare(scene_id="proxima_cena")
        self.assertNotEqual(chosen, second[contacts.TICKET_KEY]["plano_id"])

    def test_adiar_agenda_oportunidade_futura_sem_entregar(self):
        self.ready()
        p = self.prepare()
        cronica.conclude(self.repo, p["ticket"], self.tx(p, outcome="adiado"))
        self.assertEqual(self.plan()["estado"], "tentou")
        self.assertIsNone(self.plan()["ultima_tentativa"]["resultado"])
        self.assertNotIn(contacts.TICKET_KEY, self.prepare())
        self.advance("08:20")
        self.assertIn(contacts.TICKET_KEY, self.prepare())

    def test_mesma_necessidade_nao_reabre_mudando_id_ou_mensagem(self):
        self.ready()
        p = self.prepare()
        cronica.conclude(self.repo, p["ticket"], self.tx(p))
        step = self.contact_step()
        step["resolucao"]["mensagem"] = "Ainda quer tomar chá?"
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "já foi comunicada"):
            self.define("outro", step=step)
        self.assertEqual(before, self.hashes())

    def test_causa_materialmente_nova_permite_novo_contato(self):
        self.ready()
        p = self.prepare()
        cronica.conclude(self.repo, p["ticket"], self.tx(p))
        doc = self.read(self.source)
        doc["npc"]["necessidades"]["companhia"] = "Agora precisa conversar sobre uma dificuldade nova."
        self.write(self.source, doc)
        self.define("novo", step=self.contact_step())
        self.assertEqual(self.plan("novo")["estado"], "pretende")

    def test_modalidades_incluem_convivencia_e_pedido_sem_sidequest(self):
        for kind in sorted(contacts.MODALITIES):
            with self.subTest(kind=kind):
                step = self.contact_step(modality=kind)
                self.assertEqual(plans._step(step)["resolucao"]["modalidade"], kind)
        self.assertIn("convite", contacts.MODALITIES)
        self.assertIn("pedir_ajuda", contacts.MODALITIES)


class ContactSafetyTest(ContactFixture):
    def test_intencao_ainda_bloqueia_para_tentar_no_lote(self):
        self.define(step=self.contact_step())
        self.assertEqual(self.prepare()["fase"], "bloqueada_pendencias_mundo")

    def test_antes_do_prazo_nao_entrega(self):
        self.define(step=self.contact_step())
        self.attempt()
        self.assertNotIn(contacts.TICKET_KEY, self.prepare())

    def test_local_errado_nao_bloqueia_turno_nem_inventa_mensagem(self):
        self.ready()
        state = self.read("estado/estado-atual.yaml")
        state["localizacao"]["area"] = "Casa"
        self.write("estado/estado-atual.yaml", state)
        p = self.prepare()
        self.assertNotIn(contacts.TICKET_KEY, p)
        cronica.conclude(self.repo, p["ticket"], {"id": "ren-longe", "modo": "interação", "jogador": "Ren descansa.",
            "narracao": "A casa permanece silenciosa.", "resumo": "Ren fica em casa.", "deltas": []})
        self.assertEqual(self.plan()["estado"], "tentou")
        self.assertEqual(len(mundo.pending_view(self.repo)["pendencias"]), 1)

    def test_canal_indisponivel_presenca_deslocamento_e_identidade_impedem_entrega(self):
        self.ready()
        original = self.read(self.source)
        changes = [{"canais_contato": {}}, {"presenca": {"local": "Casa", "estado": "presente", "em_deslocamento": False}},
                   {"presenca": {"local": "Circo", "estado": "presente", "em_deslocamento": True}},
                   {"identidade_relacional": "shinta"}, {"conhecimento": []}, {"necessidades": {}}]
        for change in changes:
            with self.subTest(change=change):
                doc = deepcopy(original); doc["npc"].update(change); self.write(self.source, doc)
                before = self.hashes()
                self.assertNotIn(contacts.TICKET_KEY, self.prepare())
                self.assertEqual(before, self.hashes())

    def test_mensageiro_ausente_na_origem_impede_envio(self):
        step = self.contact_step(messenger=True)
        source = f"estado/npcs/{self.people[2]}.yaml"
        doc = self.read(source); doc["npc"]["presenca"]["local"] = "Casa"; self.write(source, doc)
        self.define(step=step)
        with self.assertRaisesRegex(ValueError, "mensageiro"):
            self.attempt()

    def test_transporte_nao_pode_ser_zerado_ou_encurtado(self):
        step = self.contact_step(messenger=True)
        step["duracao_minutos"] = 0
        self.define(step=step)
        with self.assertRaisesRegex(ValueError, "duração"):
            self.attempt()
        step["resolucao"]["canal"]["valor"]["duracao_minima_minutos"] = 0
        with self.assertRaises(ValueError):
            plans._step(step)

    def test_causa_de_terceiro_e_conhecimento_de_ren_nao_autorizam(self):
        step = self.contact_step()
        step["resolucao"]["causa"]["arquivo"] = f"estado/npcs/{self.people[1]}.yaml"
        self.define(step=step)
        with self.assertRaisesRegex(ValueError, "próprio NPC"):
            self.attempt()

    def test_contato_sem_resultado_explicito_falha_antes_de_escrita(self):
        self.ready(); p = self.prepare(); tx = self.tx(p); tx.pop(contacts.TICKET_KEY)
        before = self.hashes()
        with self.assertRaises(ValueError):
            cronica.conclude(self.repo, p["ticket"], tx)
        self.assertEqual(before, self.hashes())

    def test_aceite_automatico_e_mensagem_nao_narrada_sao_recusados(self):
        self.ready(); p = self.prepare()
        for corrupt in ("aceito", "texto"):
            tx = self.tx(p)
            if corrupt == "aceito": tx[contacts.TICKET_KEY]["resultado"] = "aceito"
            else: tx["narracao"] = tx[contacts.TICKET_KEY]["evidencia"]
            before = self.hashes()
            with self.assertRaises(ValueError): cronica.conclude(self.repo, p["ticket"], tx)
            self.assertEqual(before, self.hashes())

    def test_token_obsoleto_rejeita_mudanca_causa_canal_ou_presenca(self):
        self.ready(); p = self.prepare(); original = self.read(self.source)
        for changes in ({"necessidades": {}}, {"canais_contato": {}}, {"presenca": {}}):
            doc = deepcopy(original); doc["npc"].update(changes); self.write(self.source, doc)
            before = self.hashes()
            with self.assertRaises(ValueError): cronica.conclude(self.repo, p["ticket"], self.tx(p))
            self.assertEqual(before, self.hashes())

    def test_nao_entrega_enquanto_ren_muda_de_local(self):
        self.ready(); p = self.prepare(); tx = self.tx(p)
        tx["deltas"] = [{"alvo": "estado", "op": "set", "caminho": "localizacao.area", "valor": "Casa"}]
        before = self.hashes()
        with self.assertRaises(ValueError): cronica.conclude(self.repo, p["ticket"], tx)
        self.assertEqual(before, self.hashes())

    def test_sucesso_fora_de_cena_nao_substitui_entrega(self):
        self.ready()
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "entrega"):
            batch.apply_batch(self.repo, self.result_payload())
        self.assertEqual(before, self.hashes())

    def test_nenhuma_porta_noop_apaga_contato(self):
        self.ready(); pid = self.plan()["pendencia_id"]
        before = self.hashes()
        for fun in (mundo.conclude, barrier.conclude):
            with self.assertRaises(ValueError): fun(self.repo, pid, "Ren não veio buscar o recado.")
        self.assertEqual(before, self.hashes())

    def test_pendencia_estranha_nao_e_autorizada_pelo_ticket(self):
        self.ready(); p = self.prepare()
        world = mundo.load_world_state(self.repo)
        world["pendencias"].append({"id": "mundo-1234567890abcdef", "tipo": "resolver_sidequest", "disparado_em": {"data": DATE, "hora": "08:08"}})
        self.write(mundo.WORLD_STATE_PATH.as_posix(), world); barrier.sync(self.repo)
        before = self.hashes()
        with self.assertRaises(ValueError): cronica.conclude(self.repo, p["ticket"], self.tx(p))
        self.assertEqual(before, self.hashes())
        self.assertEqual(self.prepare()["fase"], "bloqueada_pendencias_mundo")

    def test_adiamento_imediato_nao_vira_loop(self):
        self.ready(); p = self.prepare(); tx = self.tx(p, outcome="adiado")
        tx[contacts.TICKET_KEY]["retomar_em"]["hora"] = "08:08"
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "futura"): cronica.conclude(self.repo, p["ticket"], tx)
        self.assertEqual(before, self.hashes())

    def test_recurso_nao_e_cobrado_na_projecao_ou_entrega(self):
        self.ready(); before = self.read(self.source)["npc"]["recursos"]["moedas"]
        p = self.prepare(); self.prepare()
        cronica.conclude(self.repo, p["ticket"], self.tx(p))
        self.assertEqual(before, self.read(self.source)["npc"]["recursos"]["moedas"])

    def test_registro_isolado_e_confirmacao_nao_contornam_entrega(self):
        self.ready(); p = self.prepare()
        before = self.hashes()
        with self.assertRaises(ValueError): cronica.confirm(self.repo, p["ticket"])
        with self.assertRaises(ValueError): cronica.register(self.repo, p["ticket"], self.tx(p))
        self.assertEqual(before, self.hashes())


class ContactPriorityAndReplayTest(ContactFixture):
    def test_operacao_tem_prioridade_sem_abrir_aliado(self):
        self.ready()
        p = cronica._hot.prepare(self.repo, scene_id="contato")
        p["pressao_narrativa"] = {"itens": [{"id": "ameaca", "tipo": "operacao_comprometida", "prioridade": 1}]}
        with patch.object(contacts, "delivery", side_effect=AssertionError("não abrir aliado sob ameaça")):
            out = contacts.prepare(self.repo, p, mundo.pending_view(self.repo)["pendencias"],
                decode_ticket=cronica.decode_ticket, encode_ticket=cronica.encode_ticket, max_output_bytes=8192)
        self.assertNotIn(contacts.TICKET_KEY, out)
        self.assertEqual(out["pressao_narrativa"], p["pressao_narrativa"])

    def test_combate_e_interacao_solicitada_adiam_iniciativa(self):
        self.ready()
        state = self.read("estado/estado-atual.yaml"); state["campanha"]["modo_de_cena_atual"] = "combate"
        self.write("estado/estado-atual.yaml", state)
        self.assertNotIn(contacts.TICKET_KEY, self.prepare())
        state["campanha"]["modo_de_cena_atual"] = "interacao"; self.write("estado/estado-atual.yaml", state)
        # A entrada de cena reativa é testada em sua borda de contrato: esta
        # fixture não instala o catálogo de oportunidades alheio ao contato.
        p = cronica._hot.prepare(self.repo, scene_id="contato")
        payload = cronica.decode_ticket(p["ticket"]); payload["cena"]["npcs"] = [self.people[1]]
        p["ticket"], p["ticket_id"] = cronica.encode_ticket(payload)
        p = contacts.prepare(self.repo, p, mundo.pending_view(self.repo)["pendencias"],
            decode_ticket=cronica.decode_ticket, encode_ticket=cronica.encode_ticket, max_output_bytes=8192)
        self.assertNotIn(contacts.TICKET_KEY, p)

    def test_retry_consolidado_nao_repete_mensagem_recurso_ou_elenco(self):
        self.ready(); p = self.prepare(); tx = self.tx(p)
        cronica.conclude(self.repo, p["ticket"], tx)
        before = self.hashes()
        result = cronica.conclude(self.repo, p["ticket"], tx)
        self.assertEqual(before, self.hashes())
        self.assertTrue(result["transacao"]["ja_registrada"])

    def test_retry_divergente_nao_finge_ser_original(self):
        self.ready(); p = self.prepare(); tx = self.tx(p)
        cronica.conclude(self.repo, p["ticket"], tx)
        tx["deltas"] = [{"alvo": "estado", "op": "set", "caminho": "campanha.modo_de_cena_atual", "valor": "descanso"}]
        before = self.hashes()
        with self.assertRaises(ValueError): cronica.conclude(self.repo, p["ticket"], tx)
        self.assertEqual(before, self.hashes())

    def test_retomada_cli_fria_reconstroi_contato_sem_historico_chat(self):
        self.ready()
        before = self.hashes()
        result = subprocess.run([sys.executable, str(TOOLS / "cronica.py"), "--repo", str(self.repo), "preparar",
            "--cena-id", "contato", "--sem-oportunidade-sidequest"], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(yaml.safe_load(result.stdout)[contacts.TICKET_KEY]["mensagem"], self.message)
        self.assertEqual(before, self.hashes())

    def test_neutro_tem_saida_identica_sem_leitura_de_contatos(self):
        with patch.object(contacts, "delivery", side_effect=AssertionError), patch.object(contacts, "partition_gate", side_effect=AssertionError):
            before = self.prepare()
            with patch.object(contacts, "prepare", side_effect=lambda repo, prepared, *args, **kwargs: prepared):
                after = self.prepare()
        self.assertEqual(yaml.safe_dump(before), yaml.safe_dump(after))

    def test_medicao_inclui_ticket_e_nao_afirma_economia_de_tokens(self):
        neutral = self.prepare(); self.ready(); active = self.prepare(); tx = self.tx(active)
        self.assertLessEqual(plans._size(active), 8192)
        self.assertLessEqual(plans._size(active[contacts.TICKET_KEY]), contacts.MAX_PROJECTION_BYTES)
        self.assertLessEqual(len(active["ticket"]), cronica.MAX_TICKET_CHARS)
        print("NV09_BYTES=" + json.dumps({"neutro": plans._size(neutral), "preparo_com_contato": plans._size(active),
            "argumentos_conclusao": plans._size(tx), "ticket": len(active["ticket"]), "tokens_nativos": None}))

    def test_fila_rejeita_duas_definicoes_para_a_mesma_causa(self):
        self.define(step=self.contact_step())
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "ativo"): self.define("duplicado", step=self.step_contact_copy())
        self.assertEqual(before, self.hashes())

    def step_contact_copy(self):
        return deepcopy(self.plan()["passo"])
