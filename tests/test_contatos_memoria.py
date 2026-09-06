"""Memória e elenco na primeira interação de contatos, em fixtures isoladas."""
from copy import deepcopy
import json

from test_contatos_sociais import ContactFixture
import cronica
import memoria_cena


class ContactSceneMemoryTest(ContactFixture):
    def test_primeiro_preparo_traz_memoria_sem_confirmar_elenco(self):
        self.ready()
        before = self.hashes()
        prepared = self.prepare()
        memory = prepared[memoria_cena.KEY]
        self.assertIn(self.actor, memory.get("itens", {}))
        self.assertIn("Cuida dos documentos (fixture).", json.dumps(memory, ensure_ascii=False))
        self.assertEqual(memory["participantes_previstos"], [self.actor])
        self.assertEqual(cronica.decode_ticket(prepared["ticket"])[memoria_cena.TICKET_KEY]["elenco"]["participantes"], [])
        self.assertLessEqual(memoria_cena.size(memory), memoria_cena.MAX_MEMORY_BYTES)
        self.assertLessEqual(memoria_cena.size(prepared), 8192)
        self.assertEqual(before, self.hashes())
        cronica.conclude(self.repo, prepared["ticket"], self.tx(prepared, outcome="adiado"))
        self.assertEqual(self.read("estado/estado-atual.yaml")["estado_narrativo"]["elenco_cena"]["participantes"], [])
        self.assertNotIn(self.actor, self.prepare()[memoria_cena.KEY].get("itens", {}))

    def test_elenco_desconhecido_recebe_memoria_sem_ser_inventado(self):
        self.ready()
        state = self.read("estado/estado-atual.yaml")
        state["estado_narrativo"]["elenco_cena"] = None
        self.write("estado/estado-atual.yaml", state)
        prepared = self.prepare()
        memory = prepared[memoria_cena.KEY]
        self.assertIn(self.actor, memory.get("itens", {}))
        self.assertIsNone(memory["participantes"])
        self.assertTrue(memory["aprofundamento_necessario"])
        cronica.conclude(self.repo, prepared["ticket"], self.tx(prepared))
        self.assertIsNone(self.read("estado/estado-atual.yaml")["estado_narrativo"]["elenco_cena"])

    def test_mensageiro_tem_memoria_sem_presenca_do_remetente_remoto(self):
        self.ready(messenger=True)
        sender = self.read(self.source)
        sender["npc"]["presenca"]["local"] = "Casa"
        self.write(self.source, sender)
        prepared = self.prepare()
        memory = prepared[memoria_cena.KEY]
        self.assertIn(self.people[2], memory.get("itens", {}))
        self.assertNotIn(self.actor, memory.get("itens", {}))
        self.assertEqual(memory["participantes_previstos"], [self.people[2]])

    def test_memoria_do_contato_reutiliza_apenas_base_declarada(self):
        self.ready()
        first = self.prepare()[memoria_cena.KEY]
        self.assertIn(self.actor, first.get("itens", {}))
        warm = self.prepare(memory_base_in_context=first["recibo"])[memoria_cena.KEY]
        self.assertEqual(warm["modo"], "delta")
        self.assertNotIn(self.actor, warm["itens"])
        cold = self.prepare()[memoria_cena.KEY]
        self.assertEqual(cold["modo"], "completa")
        self.assertIn(self.actor, cold["itens"])

    def test_entrega_preserva_elenco_final_explicitamente_compativel(self):
        self.ready()
        prepared = self.prepare(memory_participants=[self.people[1]])
        tx = self.tx(prepared)
        final_cast = deepcopy(cronica.decode_ticket(prepared["ticket"])[memoria_cena.TICKET_KEY]["elenco"])
        final_cast["participantes"] = [self.actor]
        tx["narracao"] += " A outra interlocutora se despediu e deixou a conversa."
        tx["deltas"] = [{"alvo": "estado", "op": "set", "caminho": memoria_cena.CAST_PATH, "valor": final_cast}]
        cronica.conclude(self.repo, prepared["ticket"], tx)
        self.assertEqual(self.read("estado/estado-atual.yaml")["estado_narrativo"]["elenco_cena"], final_cast)
        before = self.hashes()
        cronica.conclude(self.repo, prepared["ticket"], tx)
        self.assertEqual(before, self.hashes())

    def test_entrega_rejeita_elenco_final_que_exclui_interlocutor(self):
        self.ready()
        prepared = self.prepare()
        tx = self.tx(prepared)
        final_cast = deepcopy(cronica.decode_ticket(prepared["ticket"])[memoria_cena.TICKET_KEY]["elenco"])
        final_cast["participantes"] = [self.people[1]]
        tx["deltas"] = [{"alvo": "estado", "op": "set", "caminho": memoria_cena.CAST_PATH, "valor": final_cast}]
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "elenco final contradiz"):
            cronica.conclude(self.repo, prepared["ticket"], tx)
        self.assertEqual(before, self.hashes())
