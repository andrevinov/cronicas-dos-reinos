"""Narrações anotadas em sandbox; não são benchmark de extração automática por IA."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "ferramentas"
sys.path.insert(0, str(TOOLS))
import yaml
import cronica
import contexto
import consolidar
import memoria_duravel as memory
import transacoes
import turno
import test_consolidacao as fixtures


class DurableMemoryIntegrationTest(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.ConsolidacaoTest()
        fixture.setUp()
        self.addCleanup(fixture.tearDown)
        self.repo, self.write = fixture.repo, fixture._write_yaml
        self.people = ["silva_fixture", "nera_fixture", "luath_fixture"]
        for kind, plural in (("relacao", "relacoes"), ("npc", "npcs")):
            entries = {}
            for npc in self.people:
                name = npc.split("_")[0].title() + " (fixture)"
                relative = f"estado/{plural}/{npc}.yaml"
                entries[npc] = {"nome": name, "arquivo": relative}
                payload = {"nome": name}
                if kind == "npc":
                    payload["medidores"] = {"vinculo": 7, "confianca": 5, "risco_percebido": 1}
                self.write(relative, {"id": npc, f"schema_{kind}": 2, kind: payload})
            self.write(f"estado/{plural}/index.yaml", {plural: entries, "quantidade": 3})
        self.write("cenario/texturas/index.yaml", {"npcs": {}, "locais": {}})
        prepared = cronica.prepare(self.repo, scene_id="memoria-fixture", sidequest_signal=None)
        self.token = prepared["ticket"]

    def hashes(self):
        return {p.relative_to(self.repo).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.repo.rglob("*") if p.is_file()}

    def tx(self, tid, kind, text, **fields):
        people = fields.pop("participantes", ["ren", "silva_fixture"])
        fact = {"id": "fato", "tipo": kind, "participantes": people,
                "evidencia": {"campo": "narracao", "trecho": text}, **fields}
        if kind in ("marco", "informacao"):
            fact.setdefault("texto", text)
        return {"id": tid, "jogador": "Ren conversa com Silva.", "narracao": text,
                "resumo": text, "modo": "interação", "deltas": [],
                "memoria": {"versao": 1, "fatos": [fact]}}

    def promise(self, tid="promessa"):
        return self.tx(tid, "promessa", "Ren prometeu entregar o mapa a Silva antes do anoitecer.",
                       operacao="registrar", compromisso={"tipo": "compromisso", "resumo": "Entregar o mapa a Silva."})

    def active(self):
        data = contexto.command_status(self.repo)["resultado"]
        return (data.get("compromissos") or {}).get("itens", {})

    def promise_record(self, tid="promessa"):
        eid = memory.event_id(tid, "fato", 3)
        record = deepcopy(self.active()[eid])
        record.pop("situacao_temporal", None)
        return eid, record

    def relation(self, npc="silva_fixture"):
        return contexto.command_relation(self.repo, npc)["resultado"]["relacao"]

    def complete(self, operation, tid="fecho"):
        eid, old = self.promise_record()
        text = {"cumprir": "Ren entregou o mapa a Silva, que deu o acordo por cumprido.",
                "cancelar": "Ren e Silva cancelaram explicitamente o compromisso de entregar o mapa.",
                "substituir": "Ren e Silva trocaram a entrega do mapa pela devolução do selo."}[operation]
        return self.tx(tid, "promessa", text,
                       operacao=operation, compromisso_id=eid, anterior=old)

    def test_promessa_aparece_antes_do_checkpoint_e_so_usa_duas_escritas(self):
        tx = self.promise()
        before = self.hashes()
        result = cronica.conclude(self.repo, self.token, tx)
        after = self.hashes()
        self.assertEqual({p for p in before.keys() | after.keys() if before.get(p) != after.get(p)},
                         {"runtime/eventos-pendentes.jsonl", "sessoes/003/transcricao.md"})
        self.assertIn(memory.event_id("promessa", "fato", 3), self.active())
        self.assertEqual(result["transacao"]["deltas"], 2)
        self.assertEqual(self.relation()["memorias_importantes"][0]["operacao"], "registrar")

    def test_retry_pendente_nao_duplica_fato_ou_promessa(self):
        tx = self.promise()
        cronica.conclude(self.repo, self.token, tx)
        before = self.hashes()
        cronica.conclude(self.repo, self.token, tx)
        self.assertEqual(before, self.hashes())
        self.assertEqual(len(self.relation()["memorias_importantes"]), 1)
        self.assertEqual(len(self.active()), 1)

    def test_cumprir_remove_ativo_e_preserva_evidencia_de_fecho(self):
        cronica.conclude(self.repo, self.token, self.promise())
        tx = self.complete("cumprir")
        cronica.conclude(self.repo, self.token, tx)
        self.assertFalse(self.active())
        self.assertEqual(self.relation()["memorias_importantes"][-1]["operacao"], "cumprir")
        before = self.hashes()
        cronica.conclude(self.repo, self.token, tx)
        self.assertEqual(before, self.hashes())

    def test_cancelar_remove_ativo_sem_apagar_acontecimento(self):
        cronica.conclude(self.repo, self.token, self.promise())
        tx = self.complete("cancelar")
        cronica.conclude(self.repo, self.token, tx)
        consolidar.consolidate(self.repo, "cena")
        self.assertFalse(self.active())
        history = yaml.safe_load((self.repo / "historico/relacoes/silva_fixture.yaml").read_text())
        self.assertEqual(len(history["eventos_pos_migracao"]), 2)
        self.assertIn("cancelar", json.dumps(history, ensure_ascii=False))

    def test_substituir_fecha_anterior_e_cria_novo_na_mesma_transacao(self):
        cronica.conclude(self.repo, self.token, self.promise())
        tx = self.complete("substituir", "troca")
        tx["memoria"]["fatos"][0]["compromisso"] = {"tipo": "compromisso", "resumo": "Devolver o selo a Silva."}
        cronica.conclude(self.repo, self.token, tx)
        self.assertEqual(list(self.active()), [memory.event_id("troca", "fato", 3)])
        self.assertEqual(self.active()[memory.event_id("troca", "fato", 3)]["resumo"], "Devolver o selo a Silva.")
        self.assertEqual(transacoes.load_pending(self.repo)[-1]["deltas"][0]["op"], "remove")
        self.assertEqual(transacoes.load_pending(self.repo)[-1]["deltas"][1]["op"], "set")

    def test_anterior_obsoleto_nao_fecha_ou_substitui_outro_compromisso(self):
        cronica.conclude(self.repo, self.token, self.promise())
        for operation in ("cumprir", "cancelar", "substituir"):
            tx = self.complete(operation)
            tx["memoria"]["fatos"][0]["anterior"]["resumo"] = "Outro compromisso."
            if operation == "substituir":
                tx["memoria"]["fatos"][0]["compromisso"] = {"tipo": "compromisso", "resumo": "Outro."}
            before = self.hashes()
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                cronica.conclude(self.repo, self.token, tx)
            self.assertEqual(before, self.hashes())

    def test_promessa_reutiliza_janela_e_schema_do_dominio(self):
        tx = self.promise()
        fact = tx["memoria"]["fatos"][0]
        fact["compromisso"] = {"tipo": "encontro", "resumo": "Encontrar Silva.",
                              "janela": {"inicio": {"data": "7 Eleasis, 1372 DR", "hora": "09:00"},
                                         "fim": {"data": "7 Eleasis, 1372 DR", "hora": "10:00"}}}
        cronica.conclude(self.repo, self.token, tx)
        self.assertEqual(next(iter(self.active().values()))["situacao_temporal"], "futuro")

    def test_janela_invertida_falha_antes_do_writer(self):
        tx = self.promise()
        tx["memoria"]["fatos"][0]["compromisso"]["janela"] = {
            "inicio": {"data": "7 Eleasis, 1372 DR", "hora": "10:00"},
            "fim": {"data": "7 Eleasis, 1372 DR", "hora": "09:00"}}
        before = self.hashes()
        with self.assertRaises(ValueError):
            cronica.conclude(self.repo, self.token, tx)
        self.assertEqual(before, self.hashes())

    def test_informacao_preserva_rumor_e_nao_confere_conhecimento_a_terceiros(self):
        text = "O barqueiro disse que a ponte caiu, mas isso ainda é um rumor."
        tx = self.tx("rumor", "informacao", text, emissor="ren", destinatario="silva_fixture",
                     canal="presencial", estatuto="rumor", participantes=["ren", "silva_fixture", "nera_fixture"])
        cronica.conclude(self.repo, self.token, tx)
        self.assertEqual(self.relation()["informacoes_recebidas"][0]["estatuto"], "rumor")
        self.assertNotIn("informacoes_recebidas", self.relation("nera_fixture"))
        self.assertFalse(any(d["alvo"] == "conhecimento" for d in transacoes.load_pending(self.repo)[0]["deltas"]))

    def test_informacao_para_ren_sobrevive_ao_checkpoint_sem_promover_rumor(self):
        text = "O barqueiro disse que a ponte caiu, mas isso ainda é um rumor."
        tx = self.tx("ren-informado", "informacao", text, emissor="silva_fixture", destinatario="ren",
                     canal="mensagem_entregue", estatuto="rumor")
        cronica.conclude(self.repo, self.token, tx)
        before = contexto.command_knowledge(self.repo, "barqueiro")
        self.assertTrue(before["resultado"]["encontrado"])
        self.assertIn("rumor recebido", json.dumps(before, ensure_ascii=False))
        consolidar.consolidate(self.repo, "cena")
        after = contexto.command_knowledge(self.repo, "barqueiro")
        self.assertTrue(after["resultado"]["encontrado"])
        self.assertIn("rumor recebido", json.dumps(after, ensure_ascii=False))

    def relationship_tx(self, tid="confianca", previous=5):
        return self.tx(tid, "relacao", "Silva agradeceu a honestidade de Ren e mostrou mais confiança.",
                       npc="silva_fixture", eixo="confianca", anterior=previous, variacao=1)

    def trust(self):
        data = contexto.command_npc(self.repo, "silva_fixture")
        return data["resultado"]["medidores"]["dados"]["medidores"]["confianca"]

    def test_relacao_usa_medidor_efetivo_sem_novo_sistema(self):
        cronica.conclude(self.repo, self.token, self.relationship_tx())
        self.assertEqual(self.trust(), 6)
        before = self.hashes()
        with self.assertRaises(ValueError):
            cronica.conclude(self.repo, self.token, self.relationship_tx("segunda", previous=5))
        self.assertEqual(before, self.hashes())
        cronica.conclude(self.repo, self.token, self.relationship_tx("segunda", previous=6))
        self.assertEqual(self.trust(), 7)

    def test_retry_frio_de_relacao_nao_incrementa_novamente(self):
        tx = self.relationship_tx()
        cronica.conclude(self.repo, self.token, tx)
        consolidar.consolidate(self.repo, "cena")
        before = self.hashes()
        cronica.conclude(self.repo, self.token, tx)
        self.assertEqual(before, self.hashes())
        self.assertEqual(self.trust(), 6)

    def test_retry_de_promessa_antiga_nao_ressuscita_depois_de_cumprida(self):
        original = self.promise()
        cronica.conclude(self.repo, self.token, original)
        close = self.complete("cumprir")
        cronica.conclude(self.repo, self.token, close)
        consolidar.consolidate(self.repo, "cena")
        before = self.hashes()
        cronica.conclude(self.repo, self.token, original)
        cronica.conclude(self.repo, self.token, close)
        self.assertEqual(before, self.hashes())
        self.assertFalse(self.active())

    def test_retry_divergente_e_recusado_antes_e_depois_da_consolidacao(self):
        tx = self.promise()
        cronica.conclude(self.repo, self.token, tx)
        changed = deepcopy(tx)
        changed["memoria"]["fatos"][0]["compromisso"]["resumo"] = "Outro mapa e outro acordo."
        for checkpoint in (False, True):
            if checkpoint:
                consolidar.consolidate(self.repo, "cena")
            before = self.hashes()
            with self.subTest(checkpoint=checkpoint), self.assertRaises(ValueError):
                cronica.conclude(self.repo, self.token, changed)
            self.assertEqual(before, self.hashes())

    def test_retry_usa_historico_dirigido_quando_marca_foi_arquivada(self):
        tx = self.promise()
        cronica.conclude(self.repo, self.token, tx)
        consolidar.consolidate(self.repo, "cena")
        path = self.repo / "estado/relacoes/silva_fixture.yaml"
        doc = yaml.safe_load(path.read_text())
        doc["relacao"].pop("memorias_importantes")
        self.write("estado/relacoes/silva_fixture.yaml", doc)
        before = self.hashes()
        # A projeção/validação da memória não lê transcrição; o writer legado ainda
        # a consulta para reparar seu próprio marcador.
        original = Path.read_text
        def guarded(path, *args, **kwargs):
            if path.name == "transcricao.md":
                raise AssertionError("compiler leu transcrição")
            return original(path, *args, **kwargs)
        with patch.object(Path, "read_text", guarded):
            memory.prepare_transaction(self.repo, tx)
        cronica.conclude(self.repo, self.token, tx)
        self.assertEqual(before, self.hashes())

    def test_interrupcao_entre_buffer_e_transcricao_e_reparavel(self):
        tx = self.promise()
        original = turno._atomic_write
        def interrupt(path, content):
            if path.name == "transcricao.md":
                raise OSError("queda simulada depois do buffer")
            return original(path, content)
        with patch.object(turno, "_atomic_write", interrupt), self.assertRaises(Exception):
            cronica.conclude(self.repo, self.token, tx)
        self.assertEqual(len(transacoes.load_pending(self.repo)), 1)
        cronica.conclude(self.repo, self.token, tx)
        self.assertEqual(len(transacoes.load_pending(self.repo)), 1)
        self.assertEqual(len(self.relation()["memorias_importantes"]), 1)
        self.assertEqual(turno.check_transactions(self.repo), [])

    def test_evidencia_invalida_falha_antes_de_qualquer_journal(self):
        tx = self.promise()
        tx["memoria"]["fatos"][0]["evidencia"]["trecho"] = "Um acontecimento que nunca foi narrado neste turno."
        before = self.hashes()
        with patch.object(cronica, "_conclude_base") as writer, \
             patch.object(cronica._sidequests49, "prepare_conclusion") as progress, \
             patch.object(cronica._sidequests46, "begin_conclusion") as journal, self.assertRaises(ValueError):
            cronica.conclude(self.repo, self.token, tx)
        writer.assert_not_called()
        progress.assert_not_called()
        journal.assert_not_called()
        self.assertEqual(before, self.hashes())

    def test_participante_desconhecido_nao_cria_npc_ou_fragmento(self):
        tx = self.promise()
        tx["memoria"]["fatos"][0]["participantes"] = ["ren", "silva_typo"]
        before = self.hashes()
        with self.assertRaises(ValueError):
            cronica.conclude(self.repo, self.token, tx)
        self.assertEqual(before, self.hashes())

    def test_fragmento_excedido_falha_antes_de_contaminar_buffer(self):
        self.write("estado/relacoes/silva_fixture.yaml", {"id": "silva_fixture", "relacao": {
            "nome": "Silva fixture", "detalhe": "x" * memory.MAX_FRAGMENT_BYTES}})
        before = self.hashes()
        with self.assertRaises(ValueError):
            cronica.conclude(self.repo, self.token, self.promise())
        self.assertEqual(before, self.hashes())

    def test_registrar_isolado_nao_ignora_bloco_de_memoria(self):
        before = self.hashes()
        with self.assertRaises(ValueError):
            cronica.register(self.repo, self.token, self.promise())
        self.assertEqual(before, self.hashes())

    def test_cli_publica_aceita_mesmo_ticket_e_stdin(self):
        proc = subprocess.run([sys.executable, str(TOOLS / "cronica.py"), "--repo", str(self.repo),
                               "concluir", "--ticket", self.token], input=json.dumps(self.promise(), ensure_ascii=False),
                              text=True, capture_output=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        self.assertIn(memory.event_id("promessa", "fato", 3), self.active())

    def test_episodio_anotado_reconstroi_quatro_tipos_sem_contexto_de_chat(self):
        promise = self.promise()
        text = "O barqueiro disse que a ponte caiu, mas isso ainda é um rumor."
        info = self.tx("relato", "informacao", text, emissor="ren", destinatario="silva_fixture",
                       canal="presencial", estatuto="rumor")
        text = "Silva ensinou a Ren o sinal de acolhida da casa."
        mark = self.tx("acolhida", "marco", text)
        for tx in (promise, info, self.relationship_tx(), mark):
            cronica.conclude(self.repo, self.token, tx)
        consolidar.consolidate(self.repo, "cena")
        # Novo processo recebe apenas o repositório, não a prosa do chat anterior.
        code = "import json,sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import contexto;print(json.dumps(contexto.command_relation(Path(sys.argv[2]),'silva_fixture'),ensure_ascii=False))"
        proc = subprocess.run([sys.executable, "-c", code, str(TOOLS), str(self.repo)],
                              text=True, capture_output=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        relation = json.loads(proc.stdout)["resultado"]["relacao"]
        self.assertEqual({m["tipo"] for m in relation["memorias_importantes"]}, {"promessa", "relacao", "marco"})
        self.assertEqual(relation["informacoes_recebidas"][0]["estatuto"], "rumor")
        self.assertEqual(self.trust(), 6)
        self.assertEqual(len(self.active()), 1)

    def test_turno_sem_bloco_preserva_preparo_e_conclusao_sem_leitura_de_memoria(self):
        tx = self.promise()
        tx.pop("memoria")
        with patch.object(memory, "_load", side_effect=AssertionError("memória acordou sem fatos")):
            prepared = cronica.prepare(self.repo, scene_id="neutro-fixture", sidequest_signal=None)
            self.assertNotIn("memoria", prepared)
            result = cronica.conclude(self.repo, prepared["ticket"], tx)
        self.assertEqual(result["transacao"]["deltas"], 0)
        # Ausência de anotação não é prova de ausência de promessa na prosa.
        self.assertFalse(self.active())


    def test_informacao_e_conhecimento_independente_coexistem_ate_checkpoint(self):
        text = "O barqueiro disse que a ponte caiu, mas isso ainda é um rumor."
        tx = self.tx("dois-conhecimentos", "informacao", text, emissor="silva_fixture", destinatario="ren",
                     canal="presencial", estatuto="rumor")
        raw_text = "Ren reconheceu uma pegada diferente no portão."
        tx["deltas"] = [{"alvo": "conhecimento", "op": "registrar",
                         "valor": {"texto": raw_text, "fonte": "observacao_direta"}}]
        cronica.conclude(self.repo, self.token, tx)
        deltas = transacoes.load_pending(self.repo)[0]["deltas"]
        self.assertEqual(sum(d["alvo"] == "conhecimento" for d in deltas), 2)
        consolidar.consolidate(self.repo, "cena")
        self.assertTrue(contexto.command_knowledge(self.repo, "barqueiro")["resultado"]["encontrado"])
        self.assertTrue(contexto.command_knowledge(self.repo, "pegada")["resultado"]["encontrado"])
        before = self.hashes()
        cronica.conclude(self.repo, self.token, tx)
        self.assertEqual(before, self.hashes())

    def test_par_de_rastro_e_informacao_preservam_validacao_transacional(self):
        text = "O barqueiro disse que a ponte caiu, mas isso ainda é um rumor."
        tx = self.tx("rastro-e-relato", "informacao", text, emissor="silva_fixture", destinatario="ren",
                     canal="presencial", estatuto="rumor")
        trace = "rastro-0123456789abcdef"
        tx["deltas"] = [
            {"alvo": "conhecimento", "op": "registrar", "valor": {
                "tipo": "rastro_descoberto", "rastro": trace, "fonte": "rastro:" + trace,
                "texto": "Pegadas novas junto ao portão."}},
            {"alvo": "rastro:" + trace, "op": "set", "caminho": "estado",
             "valor": "descoberto", "visibilidade": "narrador"},
        ]
        writer, _ = memory.compile_transaction(tx, tx["id"], 3)
        record = transacoes.build_pending_record(writer, 3)
        self.assertEqual(record["deltas"][:2], tx["deltas"])
        self.assertEqual(sum(d["alvo"] == "conhecimento" for d in record["deltas"]), 2)

    def test_mesmo_id_cliente_em_sessoes_distintas_preserva_ambas_memorias_e_historicos(self):
        tx = self.promise("id_reutilizado")
        cronica.conclude(self.repo, self.token, tx)
        consolidar.consolidate(self.repo, "cena")
        first_id = memory.event_id("id_reutilizado", "fato", 3)
        # Avanço de sessão somente na fixture: nenhuma cópia da transcrição antiga.
        state = yaml.safe_load((self.repo / "estado/estado-atual.yaml").read_text())
        state["campanha"]["sessao_atual"] = 4
        self.write("estado/estado-atual.yaml", state)
        hot = yaml.safe_load((self.repo / "runtime/contexto.yaml").read_text())
        hot["sessao"]["numero"] = 4
        self.write("runtime/contexto.yaml", hot)
        scene = yaml.safe_load((self.repo / "runtime/cena.yaml").read_text())
        scene["sessao"] = 4
        self.write("runtime/cena.yaml", scene)
        (self.repo / "sessoes/004").mkdir()
        (self.repo / "sessoes/004/transcricao.md").write_text("# Sessão sintética 004\n", encoding="utf-8")
        token = cronica.prepare(self.repo, scene_id="outra-sessao", sidequest_signal=None)["ticket"]
        cronica.conclude(self.repo, token, tx)
        second_id = memory.event_id("id_reutilizado", "fato", 4)
        self.assertNotEqual(first_id, second_id)
        self.assertEqual(set(self.active()), {first_id, second_id})
        consolidar.consolidate(self.repo, "cena")
        memories = self.relation()["memorias_importantes"]
        self.assertEqual({row["id"] for row in memories}, {first_id, second_id})
        history = yaml.safe_load((self.repo / "historico/relacoes/silva_fixture.yaml").read_text())
        events = history["eventos_pos_migracao"]
        self.assertEqual(len(events), 2)
        self.assertEqual(len({row["transacao"] for row in events}), 2)
        before = self.hashes()
        cronica.conclude(self.repo, token, tx)
        self.assertEqual(before, self.hashes())


if __name__ == "__main__":
    unittest.main()
