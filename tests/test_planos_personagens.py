"""Jornadas isoladas: planos não herdam valores atuais nem alteram o save vivo."""
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
import planos_personagens as plans
import resolver_fronteira as batch
import turno
import transacoes
import mundo
import barreira_mundo as barrier
import consolidar
import _consolidar_core as core
import fronteira_mundo
import _rolar_dados_core as dice
import test_acionamento_npcs_integracao as fixtures

DATE = "7 Eleasis, 1372 DR"
NOW = {"data": DATE, "hora": "08:03"}


class PlanFixture(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.CausalActivationIntegrationTest()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.repo, self.write, self.read = fixture.repo, fixture.write, fixture.read
        self.people = fixture.people
        self.actor = fixture.silva
        self.source = f"estado/npcs/{self.actor}.yaml"
        for aid in self.people:
            doc = self.read(f"estado/npcs/{aid}.yaml")
            doc["npc"].update({"recursos": {"moedas": 3}, "bonus": 2,
                "presenca": {"local": "Circo", "estado": "presente", "em_deslocamento": False},
                "oportunidade": {"sem_oposicao": True, "cd": 13},
                "conhecimento": [{"id": "documentos", "fonte": f"estado/relacoes/{aid}.yaml",
                                  "evidencia": "Cuida dos documentos (fixture)."}]})
            self.write(f"estado/npcs/{aid}.yaml", doc)
        self.counter = 0

    def hashes(self):
        return {str(p.relative_to(self.repo)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.repo.rglob("*") if p.is_file()}

    def ref(self, path, value, source=None):
        return {"arquivo": source or self.source, "caminho": "npc." + path, "valor": value}

    def step(self, sid="preparar", hour="08:03", *, test=False, cost=1, actor=None):
        source = f"estado/npcs/{actor or self.actor}.yaml"
        return {"id": sid, "acao": "Preparar os documentos para entrega.", "em": {"data": DATE, "hora": hour},
            "duracao_minutos": 5, "local": "Circo", "condicoes": [],
            "recursos": [{"caminho": "recursos.moedas", "quantidade": cost}] if cost else [],
            "conhecimento": ["documentos"], "resolucao": (
                {"tipo": "teste", "bonus": self.ref("bonus", 2, source), "cd": self.ref("oportunidade.cd", 13, source)}
                if test else {"tipo": "factual", "sem_oposicao": self.ref("oportunidade.sem_oposicao", True, source)})}

    def define_tx(self, pid="documentos", *, step=None, actor=None):
        aid = actor or self.actor
        event = {"evento": "definir", "revisao": 0, "fato": "A escriba decidiu preparar os documentos.",
                 "agente": {"tipo": "leve", "id": aid}, "objetivo": "Rotina documental.",
                 "passo": step or self.step(actor=aid)}
        return {"id": "definir-" + pid, "modo": "mundo", "narracao": event["fato"], "resumo": event["fato"],
                "deltas": [{"alvo": "plano:" + pid, "op": "registrar", "visibilidade": "narrador", "valor": event}]}

    def define(self, pid="documentos", **kw):
        tx = self.define_tx(pid, **kw)
        turno.register_transaction(self.repo, tx)
        return tx

    def plan(self, pid="documentos"):
        return mundo.load_world_state(self.repo)[plans.KEY][pid]

    def items(self):
        return [i for i in batch.prepare_batch(self.repo)["itens"] if i["tipo"] == plans.PENDING_TYPE]

    def payload(self, kind="tentar", *, pid="documentos", **fields):
        prepared = batch.prepare_batch(self.repo)
        item = next(i for i in prepared["itens"] if i.get("contexto", {}).get("plano_personagem", {}).get("plano", {}).get("id") == pid)
        event = {"evento": kind, "revisao": self.plan(pid)["revisao"],
                 "fato": "A escriba começou a preparar os documentos.", **fields}
        return {"lote_id": prepared["lote_id"], "planos": [{"id": item["id"], "token": item["token"], "evento": event}]}

    def attempt(self, **kw):
        payload = self.payload(**kw)
        batch.apply_batch(self.repo, payload)
        return payload

    def advance(self, hour="08:08"):
        self.counter += 1
        return turno.register_transaction(self.repo, {"id": f"tempo-plano-{self.counter}", "modo": "exploração",
            "jogador": "Ren aguarda no quarto.", "narracao": "Alguns minutos se passam enquanto Ren permanece no quarto.",
            "resumo": "O tempo passou.", "deltas": [{"alvo": "tempo", "op": "instante", "valor": {"data": DATE, "hora": hour}}]})

    def result_payload(self, *, follow="concluir", outcome="sucesso", step=None, roll=None, pid="documentos"):
        fact = "A escriba terminou os documentos." if outcome == "sucesso" else "A tentativa de preparar os documentos falhou."
        value = "prontos" if outcome == "sucesso" else "falhou"
        result = self.payload("resolver", pid=pid, fato=fact, resultado=outcome, seguimento=follow,
                             motivo="O resultado exige uma nova escolha de conduta.", passo=step,
                             retomar_em=None, rolagem=roll, prova=None if roll is not None else self.ref("documentos", value))
        decision = result["planos"][0]
        if roll is None:
            decision["deltas"] = [{"alvo": "npc:" + self.actor, "op": "set", "caminho": "documentos", "valor": value}]
        else:
            label = "plano:" + pid + ":" + self.plan(pid)["ultima_tentativa"]["transacao"]
            decision["rolagens_ocultas"] = [dice.format_check(label, dice.D20Roll([roll], roll, 2, "normal"), 13)]
        return result


class PlansJourneyTest(PlanFixture):
    def test_intencao_nao_executa_nem_consume_recurso(self):
        tx = self.define()
        self.assertEqual(self.plan()["estado"], "pretende")
        self.assertIsNone(self.plan()["ultima_tentativa"])
        self.assertEqual(self.read(self.source)["npc"]["recursos"]["moedas"], 3)
        self.assertTrue(barrier.load_status(self.repo)["bloqueado"])
        self.assertIn(tx["id"], (self.repo / "sessoes/003/consolidacoes.jsonl").read_text())
        before = self.hashes()
        item = self.items()[0]
        self.assertEqual(item["classificacao"], "dar_continuidade_plano")
        self.assertFalse(item["sem_mudanca_permitido"])
        self.assertEqual(before, self.hashes())

    def test_plano_avanca_sem_contato_com_ren_e_reagenda_o_proximo_passo(self):
        self.define()
        self.attempt()
        self.assertEqual(self.plan()["estado"], "tentou")
        self.assertIsNone(self.plan()["ultima_tentativa"]["resultado"])
        self.assertEqual(self.read(self.source)["npc"]["recursos"]["moedas"], 2)
        self.assertFalse(mundo.pending_view(self.repo)["pendencias"])
        advance = self.advance()
        self.assertEqual(advance["checkpoint_mundo"]["motivo"], "prazo_plano")
        payload = self.result_payload(follow="prosseguir", step=self.step("entregar", "08:13"))
        batch.apply_batch(self.repo, payload)
        self.assertEqual(self.plan()["estado"], "pretende")
        self.assertEqual(self.plan()["passo"]["id"], "entregar")
        self.assertEqual(self.plan()["ultima_tentativa"]["resultado"]["resultado"], "sucesso")
        self.assertEqual(self.read(self.source)["npc"]["documentos"], "prontos")
        # Registros autônomos não recebem ação inventada do jogador.
        ledger = [json.loads(line) for line in (self.repo / "sessoes/003/consolidacoes.jsonl").read_text().splitlines()]
        self.assertEqual(sum(len(r.get(plans.KEY, [])) for r in ledger), 3)
        self.assertFalse(transacoes.load_pending(self.repo))

    def test_retry_do_lote_nao_repete_tentativa_nem_custo(self):
        self.define()
        payload = self.attempt()
        before = self.hashes()
        result = batch.apply_batch(self.repo, payload)
        self.assertEqual(len(result["ja_aplicadas"]), 1)
        self.assertEqual(before, self.hashes())
        self.assertEqual(self.read(self.source)["npc"]["recursos"]["moedas"], 2)

    def test_retry_divergente_nao_e_aceito_como_decisao_original(self):
        self.define()
        payload = self.attempt()
        payload["planos"][0]["evento"]["fato"] = "Outra decisão sobre os documentos."
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "diverge"):
            batch.apply_batch(self.repo, payload)
        self.assertEqual(before, self.hashes())

    def test_duas_tentativas_independentes_em_uma_transacao_e_um_lote(self):
        self.define()
        self.define("segunda", actor=self.people[1])
        a, b = self.payload(), self.payload(pid="segunda")
        a["planos"].extend(b["planos"])
        with patch.object(turno, "register_transaction", wraps=turno.register_transaction) as writer:
            batch.apply_batch(self.repo, a)
        self.assertEqual(writer.call_count, 1)
        self.assertEqual(self.plan()["ultima_tentativa"]["transacao"], self.plan("segunda")["ultima_tentativa"]["transacao"])

    def test_noop_generico_nao_apaga_plano_pendente(self):
        self.define()
        prepared = batch.prepare_batch(self.repo)
        item = self.items()[0]
        before = self.hashes()
        with self.assertRaises(ValueError):
            batch.apply_batch(self.repo, {"lote_id": prepared["lote_id"], "sem_mudanca": [{"id": item["id"], "token": item["token"], "nota": "Ren não procurou a escriba."}]})
        for conclude in (mundo.conclude, barrier.conclude):
            with self.assertRaises(ValueError):
                conclude(self.repo, item["id"], "Nada ocorreu porque Ren não apareceu.")
        self.assertEqual(before, self.hashes())

    def test_token_muda_quando_o_recurso_muda_sem_escrita_indevida(self):
        self.define()
        payload = self.payload()
        doc = self.read(self.source)
        doc["npc"]["recursos"]["moedas"] = 0
        self.write(self.source, doc)
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "mudou"):
            batch.apply_batch(self.repo, payload)
        self.assertEqual(before, self.hashes())
        self.assertIn("insuficiente", " ".join(self.items()[0]["contexto"]["plano_personagem"]["bloqueios"]))

    def test_falta_de_presenca_conhecimento_ou_oposicao_bloqueia_sem_inventar(self):
        self.define()
        original = self.read(self.source)
        cases = [({"presenca": {"local": "Outra cidade", "estado": "presente", "em_deslocamento": False}}, "presença"),
                 ({"presenca": {"local": "Circo", "estado": "presente", "em_deslocamento": True}}, "deslocamento"),
                 ({"conhecimento": []}, "conhecimento"),
                 ({"oportunidade": {"sem_oposicao": False, "cd": 13}}, "condição")]
        for changes, word in cases:
            with self.subTest(word=word):
                doc = deepcopy(original)
                doc["npc"].update(changes)
                self.write(self.source, doc)
                payload = self.payload()
                before = self.hashes()
                with self.assertRaisesRegex(ValueError, word):
                    batch.apply_batch(self.repo, payload)
                self.assertEqual(before, self.hashes())
        self.write(self.source, original)

    def test_bloqueio_tem_motivo_e_reavalia_no_instante_previsto(self):
        self.define()
        payload = self.payload("bloquear", motivo="A ponte fechada impede a entrega.", retomar_em={"data": DATE, "hora": "08:10"})
        batch.apply_batch(self.repo, payload)
        self.assertEqual(self.plan()["estado"], "bloqueado")
        self.assertIn("ponte", self.plan()["motivo"])
        self.assertFalse(self.items())
        boundary = fronteira_mundo.query(self.repo, DATE, "08:30")
        self.assertTrue(boundary["interromper"])
        self.assertEqual(boundary["fronteira"]["hora"], "08:10")

    def test_falha_mecanica_muda_estrategia_sem_conceder_sucesso(self):
        self.define(step=self.step(test=True))
        self.attempt()
        self.advance()
        step = self.step("pedir_ajuda", "08:12")
        step["acao"] = "Procurar uma escriba com mais experiência."
        payload = self.result_payload(follow="mudar_estrategia", outcome="falha", step=step, roll=4)
        batch.apply_batch(self.repo, payload)
        result = self.plan()["ultima_tentativa"]["resultado"]
        self.assertEqual(result["resultado"], "falha")
        self.assertIn("= 6 contra CD 13. Falha.", result["rolagem"])
        self.assertEqual(self.plan()["passo"]["id"], "pedir_ajuda")
        self.assertEqual(self.plan()["estado"], "pretende")

    def test_sucesso_mecanico_depende_da_cd_original(self):
        self.define(step=self.step(test=True))
        self.attempt()
        self.advance()
        bad = self.result_payload(outcome="sucesso", roll=4)
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "diverge"):
            batch.apply_batch(self.repo, bad)
        self.assertEqual(before, self.hashes())
        good = self.result_payload(roll=15)
        batch.apply_batch(self.repo, good)
        self.assertEqual(self.plan()["estado"], "concluido")

    def test_sem_recibo_de_rolagem_registrado_resultado_mecanico_e_recusado(self):
        self.define(step=self.step(test=True))
        self.attempt()
        self.advance()
        payload = self.result_payload(roll=15)
        payload["planos"][0]["rolagens_ocultas"] = []
        with self.assertRaisesRegex(ValueError, "rolagem"):
            batch.apply_batch(self.repo, payload)

    def test_resultado_sem_tentativa_nao_concede_objetivo(self):
        self.define()
        payload = self.result_payload()
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "tentativa"):
            batch.apply_batch(self.repo, payload)
        self.assertEqual(before, self.hashes())

    def test_nao_alterar_ou_desistir_de_tentativa_sem_registrar_resultado(self):
        self.define()
        self.attempt()
        self.advance()
        for kind, fields in [("desistir", {"motivo": "Desistir sem apagar o acontecido."}),
                             ("replanejar", {"motivo": "Mudar de estratégia.", "passo": self.step("outra")})]:
            before = self.hashes()
            with self.assertRaisesRegex(ValueError, "tentativa"):
                batch.apply_batch(self.repo, self.payload(kind, **fields))
            self.assertEqual(before, self.hashes())

    def test_rejeita_intencao_inventada_e_efeitos_sobre_ren_antes_de_escrever(self):
        tx = self.define_tx()
        tx["deltas"][0]["valor"]["objetivo"] = "Conquistar o mundo por vingança."
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "intenção"):
            turno.register_transaction(self.repo, tx)
        self.assertEqual(before, self.hashes())
        self.define()
        payload = self.payload()
        payload["planos"][0]["deltas"] = [{"alvo": "estado", "op": "inc", "caminho": "recursos.focus.atuais", "valor": -1}]
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "Ren"):
            batch.apply_batch(self.repo, payload)
        self.assertEqual(before, self.hashes())

    def test_recurso_compartilhado_nao_e_gasto_duas_vezes_no_lote(self):
        self.define(step=self.step(cost=2))
        self.define("segunda", step=self.step("segunda", cost=2))
        payload = self.payload()
        payload["planos"].extend(self.payload(pid="segunda")["planos"])
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "insuficientes"):
            batch.apply_batch(self.repo, payload)
        self.assertEqual(before, self.hashes())

    def test_cli_em_outro_processo_reconstroi_plano_sem_historico_chat(self):
        self.define()
        self.attempt()
        self.advance()
        before = self.hashes()
        result = subprocess.run([sys.executable, str(TOOLS / "resolver_fronteira.py"), "--repo", str(self.repo), "preparar"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        item = yaml.safe_load(result.stdout)["itens"][0]
        self.assertEqual(item["contexto"]["plano_personagem"]["plano"]["estado"], "tentou")
        self.assertEqual(before, self.hashes())

    def test_journal_interrompido_recupera_todos_os_arquivos_sem_duplicar(self):
        tx = self.define_tx()
        with patch.object(turno, "_run_scene_checkpoint", return_value={}):
            turno.register_transaction(self.repo, tx)
        with self.assertRaises(core.ConsolidationError):
            consolidar.consolidate(self.repo, "cena", fail_after=2)
        with self.assertRaises(ValueError):
            plans.compute(self.repo, transacoes.load_pending(self.repo))
        consolidar.consolidate(self.repo, "cena")
        barrier.sync(self.repo)
        self.assertEqual(self.plan()["estado"], "pretende")
        self.assertEqual(len(self.items()), 1)
        before = self.hashes()
        turno.register_transaction(self.repo, tx)
        self.assertEqual(before, self.hashes())

    def test_tetos_e_ausencia_de_leitura_de_outros_perfis(self):
        self.define()
        with patch.object(plans.agentes_leves, "load_agent", wraps=plans.agentes_leves.load_agent) as directed:
            projection = self.items()[0]["contexto"]["plano_personagem"]
        self.assertEqual(directed.call_count, 1)
        self.assertEqual(directed.call_args.args, (self.repo, self.actor))
        self.assertLessEqual(plans._size(projection), plans.MAX_CONTEXT_BYTES)
        self.assertEqual(batch.MAX_BATCH, 16)


class PlansSafetyTest(PlanFixture):
    def test_recovery_de_tentativa_instala_custo_e_plano_uma_unica_vez(self):
        self.define()
        payload = self.payload()
        items = {i["id"]: i for i in batch.prepare_batch(self.repo)["itens"]}
        tx = plans.compile_batch(self.repo, payload["planos"], items)
        with patch.object(turno, "_run_scene_checkpoint", return_value={}):
            turno.register_transaction(self.repo, tx)
        with self.assertRaises(core.ConsolidationError):
            consolidar.consolidate(self.repo, "cena", fail_after=4)
        consolidar.consolidate(self.repo, "cena")
        barrier.sync(self.repo)
        self.assertEqual(self.plan()["estado"], "tentou")
        self.assertEqual(self.read(self.source)["npc"]["recursos"]["moedas"], 2)
        before = self.hashes()
        turno.register_transaction(self.repo, tx)
        batch.apply_batch(self.repo, payload)
        self.assertEqual(before, self.hashes())

    def test_intencao_no_cronica_concluir_e_barreira_no_preparar_seguinte(self):
        import cronica
        ticket = cronica.prepare(self.repo, scene_id="plano-fixture", sidequest_signal=None)["ticket"]
        tx = self.define_tx()
        tx["modo"] = "interação"
        tx["jogador"] = "Ren pergunta pelos documentos."
        result = cronica.conclude(self.repo, ticket, tx)
        self.assertEqual(self.plan()["estado"], "pretende")
        self.assertEqual(result["transacao"]["deltas"], 1)
        gate = cronica.prepare(self.repo, scene_id="depois-do-plano", sidequest_signal=None)
        self.assertEqual(gate["fase"], "bloqueada_pendencias_mundo")
        self.attempt()
        self.assertEqual(self.plan()["estado"], "tentou")

    def test_orcamento_mede_argumentos_resultados_sem_alegar_tokens(self):
        empty = batch.prepare_batch(self.repo)
        self.define()
        prep = batch.prepare_batch(self.repo)
        payload = self.payload()
        result = batch.apply_batch(self.repo, payload)
        measured = {"lote_neutro_yaml_bytes": plans._size(empty),
                    "preparar_um_plano_yaml_bytes": plans._size(prep),
                    "argumentos_tentar_yaml_bytes": plans._size(payload),
                    "aplicar_um_plano_yaml_bytes": plans._size(result),
                    "contexto_plano_yaml_bytes": plans._size(prep["itens"][0]["contexto"]["plano_personagem"]),
                    "tokens_nativos": None, "qualidade_narrada": "nao_avaliada"}
        self.assertLessEqual(measured["contexto_plano_yaml_bytes"], plans.MAX_CONTEXT_BYTES)
        self.assertNotIn("planos", empty["proximo_passo"]["entrada_aplicar"])
        self.assertIn("planos", prep["proximo_passo"]["entrada_aplicar"])
        print("NV08_BYTES=" + json.dumps(measured, ensure_ascii=False, sort_keys=True))

    def test_retry_consolidado_confere_fingerprint_inclusive_efeitos(self):
        tx = self.define()
        changed = deepcopy(tx)
        changed["deltas"].append({"alvo": "npc:" + self.actor, "op": "set", "caminho": "documentos", "valor": "inventados"})
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "retry consolidado"):
            turno.register_transaction(self.repo, changed)
        self.assertEqual(before, self.hashes())
        turno.register_transaction(self.repo, tx)
        self.assertEqual(before, self.hashes())

    def test_rejeita_avanco_do_tempo_embutido_na_decisao_do_plano(self):
        self.define()
        payload = self.payload()
        payload["planos"][0]["deltas"] = [{"alvo": "tempo", "op": "instante", "valor": {"data": DATE, "hora": "12:00"}}]
        before = self.hashes()
        with self.assertRaises(ValueError):
            batch.apply_batch(self.repo, payload)
        self.assertEqual(before, self.hashes())

    def test_tentativa_comprometida_nao_pode_ter_cd_reescrita(self):
        self.define(step=self.step(test=True))
        self.attempt()
        world = mundo.load_world_state(self.repo)
        world[plans.KEY]["documentos"]["passo"]["resolucao"]["cd"]["valor"] = 1
        with self.assertRaisesRegex(ValueError, "contrato da tentativa"):
            plans.check_control(world, mundo.load_agenda(self.repo))

    def test_fato_antigo_nao_prova_resultado_novo(self):
        doc = self.read(self.source)
        doc["npc"]["documentos"] = "prontos"
        self.write(self.source, doc)
        self.define()
        self.attempt()
        self.advance()
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "já existia"):
            batch.apply_batch(self.repo, self.result_payload())
        self.assertEqual(before, self.hashes())

    def test_efeito_factual_sem_delta_pareado_e_recusado(self):
        self.define()
        self.attempt()
        self.advance()
        payload = self.result_payload()
        payload["planos"][0]["deltas"] = []
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "pareada"):
            batch.apply_batch(self.repo, payload)
        self.assertEqual(before, self.hashes())

    def test_falha_pode_encerrar_por_desistencia_mas_nao_por_sucesso(self):
        self.define(step=self.step(test=True))
        self.attempt()
        self.advance()
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "não prova objetivo"):
            batch.apply_batch(self.repo, self.result_payload(outcome="falha", roll=4))
        self.assertEqual(before, self.hashes())
        batch.apply_batch(self.repo, self.result_payload(follow="desistir", outcome="falha", roll=4))
        self.assertEqual(self.plan()["estado"], "desistiu")
        self.assertEqual(self.plan()["ultima_tentativa"]["resultado"]["resultado"], "falha")
        self.assertFalse(self.items())
        plans.check_control(mundo.load_world_state(self.repo), mundo.load_agenda(self.repo))

    def test_plano_terminal_pode_ser_substituido_com_revisao_sem_apagar_ledger(self):
        self.define()
        self.attempt()
        self.advance()
        batch.apply_batch(self.repo, self.result_payload())
        ledger_path = self.repo / "sessoes/003/consolidacoes.jsonl"
        old_lines = ledger_path.read_text().splitlines()
        tx = self.define_tx()
        tx["id"] = "nova-intencao"
        tx["deltas"][0]["valor"]["revisao"] = self.plan()["revisao"]
        tx["deltas"][0]["valor"]["passo"] = self.step("nova", "08:20")
        turno.register_transaction(self.repo, tx)
        self.assertEqual(ledger_path.read_text().splitlines()[:len(old_lines)], old_lines)
        self.assertEqual(self.plan()["estado"], "pretende")
        self.assertIsNone(self.plan()["ultima_tentativa"])

    def test_plano_futuro_nao_aceita_tentativa_antes_da_condicao(self):
        self.define(step=self.step(hour="08:20"))
        self.assertFalse(self.items())
        event = {"evento": "tentar", "revisao": 1, "fato": "A escriba tenta começar antes da hora."}
        tx = {"id": "cedo-demais", "modo": "mundo", "narracao": event["fato"], "deltas": [
            {"alvo": "plano:documentos", "op": "registrar", "visibilidade": "narrador", "valor": event}]}
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "prazo aberto"):
            turno.register_transaction(self.repo, tx)
        self.assertEqual(before, self.hashes())

    def test_bloqueio_imediato_nao_cria_loop_de_reavaliacao(self):
        self.define()
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "futura"):
            batch.apply_batch(self.repo, self.payload("bloquear", motivo="A ponte está fechada.", retomar_em=NOW))
        self.assertEqual(before, self.hashes())

    def test_custo_nao_pode_ser_compensado_por_set_no_mesmo_lote(self):
        self.define()
        payload = self.payload()
        payload["planos"][0]["deltas"] = [{"alvo": "npc:" + self.actor, "op": "set", "caminho": "recursos.moedas", "valor": 100}]
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "consumo exato"):
            batch.apply_batch(self.repo, payload)
        self.assertEqual(before, self.hashes())

    def test_teto_de_planos_nao_descarta_intencoes_antigas(self):
        for n in range(plans.MAX_PLANS):
            self.define("plano_" + str(n), step=self.step("passo_" + str(n), "08:20", cost=0))
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "teto"):
            self.define("excesso", step=self.step("excesso", "08:20", cost=0))
        self.assertEqual(before, self.hashes())

    def test_check_encontra_agendamento_ausente_sem_varrer_npcs(self):
        self.define()
        world, agenda = mundo.load_world_state(self.repo), mundo.load_agenda(self.repo)
        agenda["agendamentos"] = []
        with patch.object(plans.agentes_leves, "load_agent", side_effect=AssertionError("scan indevido")):
            with self.assertRaisesRegex(ValueError, "agenda"):
                plans.check_control(world, agenda)

    def test_conhecimento_de_ren_nao_supre_lacuna_do_npc(self):
        self.define()
        doc = self.read(self.source)
        doc["npc"]["conhecimento"] = []
        self.write(self.source, doc)
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "conhecimento indisponível"):
            batch.apply_batch(self.repo, self.payload())
        self.assertEqual(before, self.hashes())

    def test_fato_deve_estar_literalmente_na_narracao_do_turno(self):
        tx = self.define_tx()
        tx["narracao"] = "Ren permaneceu em seu quarto sem observar a escriba."
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "literalmente"):
            turno.register_transaction(self.repo, tx)
        self.assertEqual(before, self.hashes())

    def test_referencia_nao_pode_escapar_do_repositorio(self):
        for source in ("../fora.yaml", "/tmp/fora.yaml", "estado/../fora.yaml"):
            with self.subTest(source=source):
                step = self.step()
                step["resolucao"]["sem_oposicao"]["arquivo"] = source
                before = self.hashes()
                with self.assertRaises(ValueError):
                    self.define(step=step)
                self.assertEqual(before, self.hashes())

    def test_preparacao_antiga_e_invalida_apos_mudanca_de_objetivo(self):
        self.define()
        payload = self.payload()
        path = f"narrador/agentes-leves/{self.actor}.yaml"
        doc = self.read(path)
        doc["objetivo_atual"]["descricao"] = "Outra intenção documental."
        self.write(path, doc)
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "mudou"):
            batch.apply_batch(self.repo, payload)
        self.assertEqual(before, self.hashes())

    def test_grupo_invalido_nao_grava_antes_a_tentativa_valida(self):
        import operacoes_concorrentes as operations
        self.define()
        payload = self.payload()
        prepared = batch.prepare_batch(self.repo)
        fake = {"id": "mundo-" + "a" * 16, "token": "a" * 24,
                "classificacao": "comprometer_grupo_operacoes", "grupo_operacoes_id": "grupo"}
        prepared["itens"].append(fake)
        payload["grupos_operacoes"] = [{"id": fake["id"], "token": fake["token"], "bloqueios": {}}]
        before = self.hashes()
        with patch.object(batch, "prepare_batch", return_value=prepared), patch.object(
                operations, "commit_group", side_effect=operations.ConcurrentOperationError("prova inválida")) as check:
            with self.assertRaisesRegex(ValueError, "prova inválida"):
                batch.apply_batch(self.repo, payload)
        self.assertTrue(check.call_args.kwargs["validate_only"])
        self.assertEqual(before, self.hashes())

    def test_token_nao_depende_da_memoria_do_chat_e_plano_fechado_nao_incha_lote(self):
        empty = batch.prepare_batch(self.repo)
        self.define()
        first = self.items()[0]["token"]
        self.assertEqual(first, self.items()[0]["token"])
        self.attempt()
        self.advance()
        batch.apply_batch(self.repo, self.result_payload())
        self.assertEqual(empty, batch.prepare_batch(self.repo))

    def test_cli_aplica_evento_e_nao_apenas_projeta_em_processo_novo(self):
        self.define()
        payload = self.payload()
        result = subprocess.run([sys.executable, str(TOOLS / "resolver_fronteira.py"), "--repo", str(self.repo), "aplicar"],
                                input=yaml.safe_dump(payload, allow_unicode=True), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(yaml.safe_load(result.stdout)["ok"])
        self.assertEqual(self.plan()["estado"], "tentou")
        self.assertEqual(self.read(self.source)["npc"]["recursos"]["moedas"], 2)

    def test_schema_rejeita_bool_no_lugar_de_numero_e_campo_desconhecido(self):
        for key, value in (("duracao_minutos", True), ("sucesso_automatico", True)):
            with self.subTest(key=key):
                step = self.step()
                step[key] = value
                with self.assertRaises(ValueError):
                    plans._step(step)



if __name__ == "__main__":
    unittest.main()
