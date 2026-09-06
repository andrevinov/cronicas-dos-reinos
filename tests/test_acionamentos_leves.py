"""Acionamentos em fixtures temporárias: não congela nem modifica a campanha viva."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "ferramentas"
sys.path.insert(0, str(TOOLS))
import yaml
import acionamentos_leves as causal
import agentes_leves as light
import barreira_mundo as barrier
import consolidar
import cronica
import fronteira_mundo
import mundo
import resolver_fronteira as batch
import transacoes
import turno
import test_memoria_duravel_integracao as fixtures

DATE = "7 Eleasis, 1372 DR"
NOTE = "O acesso está bloqueado pela ponte fechada; aguardar uma passagem disponível."


def when(hour="08:03"):
    return {"data": DATE, "hora": hour}


def signal(source="estado/relacoes/silva_fixture.yaml", hour="08:03", suffix="a"):
    return {"tipo": "mudanca", "fonte": source, "em": when(hour),
            "assinatura": causal._digest([source, suffix]), "lote": suffix}


class CausalQueueTest(unittest.TestCase):
    def setUp(self):
        self.index = {"agentes": {aid: {"estado": "ativo"} for aid in ("a", "b", "c", "d")},
                      "orcamento": {"max_novas_por_checkpoint": 1, "max_pendencias_abertas": 2}}
        self.world = {"schema_estado_mundo": 1, "natureza": "controle_reservado",
                      "processado_ate": when(), "pendencias": [], "concluidas_recentes": []}

    def routine(self, aid, digit):
        return {"id": "mundo-" + digit * 16, "tipo": "reavaliar_agente_leve",
                "agente_leve": aid, "agentes_afetados": [], "disparado_em": when(),
                "origem": "agentes-leves:" + aid + ".cadencia"}

    def test_prazo_precede_rotina_sem_aumentar_teto_e_rotina_retorna_mesmo_id(self):
        routines = [self.routine("a", "a"), self.routine("b", "b")]
        self.world["pendencias"] = deepcopy(routines)
        causal._enqueue(self.world, "c", "fonte", signal())
        causal.dispatch(self.world, self.index)
        self.assertEqual(len(self.world["pendencias"]), 2)
        self.assertEqual(len(self.world[causal.KEY]["rotinas_suspensas"]), 1)
        self.assertIn("c", {p["agente_leve"] for p in self.world["pendencias"]})
        self.world["pendencias"] = [p for p in self.world["pendencias"] if p["agente_leve"] != "c"]
        causal.dispatch(self.world, self.index)
        self.assertEqual({p["id"] for p in self.world["pendencias"]}, {p["id"] for p in routines})
        self.assertEqual(self.world[causal.KEY]["rotinas_suspensas"], {})

    def test_rotina_do_mesmo_agente_e_promovida_sem_duplicar(self):
        pending = self.routine("a", "a")
        self.world["pendencias"] = [pending]
        causal._enqueue(self.world, "a", "fonte", signal())
        causal.dispatch(self.world, self.index)
        self.assertEqual(len(self.world["pendencias"]), 1)
        self.assertEqual(self.world["pendencias"][0]["id"], pending["id"])
        self.assertIn(causal.PENDING_KEY, pending)

    def test_backlog_preserva_todos_sem_terceira_pendencia_ativa(self):
        for aid in self.index["agentes"]:
            causal._enqueue(self.world, aid, "fonte", signal(suffix=aid))
        causal.dispatch(self.world, self.index)
        self.assertEqual(len(self.world["pendencias"]), 2)
        self.assertEqual(len(self.world[causal.KEY]["aguardando"]), 2)
        self.world["pendencias"].pop(0)
        causal.dispatch(self.world, self.index)
        self.assertEqual(len(self.world["pendencias"]), 2)
        self.assertEqual(len(self.world[causal.KEY]["aguardando"]), 1)

    def test_dependencias_independentes_coexistem_e_mesma_fonte_coalesce(self):
        causal._enqueue(self.world, "a", "x", signal(suffix="primeiro"))
        causal._enqueue(self.world, "a", "y", signal(suffix="outro"))
        causal._enqueue(self.world, "a", "x", signal(suffix="mais_recente"))
        causal.dispatch(self.world, self.index)
        causes = self.world["pendencias"][0][causal.PENDING_KEY]
        self.assertEqual(set(causes), {"x", "y"})
        self.assertEqual(causes["x"]["lote"], "mais_recente")

    def test_prazos_exigem_instantes_estruturados_e_envolvidos_ativos(self):
        state = {"compromissos": {"mapa": {"tipo": "encontro", "resumo": "Entregar mapa.",
                 "envolvidos": ["ren", "a"], "janela": {"inicio": when("08:08"), "fim": when("09:00")}}}}
        self.assertEqual(causal.deadline_events(state, self.index, {}, when()), [])
        due = causal.deadline_events(state, self.index, {}, when("08:08"))
        self.assertEqual([(a, k) for a, k, _ in due], [("a", "mapa:inicio")])
        state["compromissos"]["mapa"]["janela"] = {"descricao": "algum dia pela manhã"}
        self.assertEqual(causal.deadline_events(state, self.index, {}, when("23:59")), [])

    def test_prazo_vence_fonte_sem_depender_da_ordem_do_indice(self):
        for aid in ("a", "b"):
            causal._enqueue(self.world, aid, "fonte", signal())
        state = {"compromissos": {"mapa": {"tipo": "encontro", "resumo": "Entregar mapa.",
                 "envolvidos": ["ren", "c"], "janela": {"inicio": when()}}}}
        causal._refresh_deadlines(self.world, state, self.index, when())
        causal.dispatch(self.world, self.index)
        self.assertIn("c", {p["agente_leve"] for p in self.world["pendencias"]})
        self.assertEqual(len(self.world["pendencias"]), 2)

    def test_recibo_persiste_apos_expulsao_do_historico_recente(self):
        state = {"compromissos": {"mapa": {"tipo": "encontro", "resumo": "Entregar mapa.",
                 "envolvidos": ["a"], "janela": {"inicio": when()}}}}
        causal._refresh_deadlines(self.world, state, self.index, when())
        causal.dispatch(self.world, self.index)
        self.world["pendencias"].clear()
        self.world["concluidas_recentes"] = [{"id": str(i)} for i in range(70)]
        causal._refresh_deadlines(self.world, state, self.index, when("09:00"))
        causal.dispatch(self.world, self.index)
        self.assertEqual(self.world["pendencias"], [])
        self.assertEqual(len(self.world[causal.KEY]["prazos"]), 1)

    def test_cancelamento_remove_condicao_sem_fabricar_cumprimento(self):
        state = {"compromissos": {"mapa": {"tipo": "encontro", "resumo": "Entregar mapa.",
                 "envolvidos": ["a"], "janela": {"inicio": when()}}}}
        causal._refresh_deadlines(self.world, state, self.index, when())
        causal.dispatch(self.world, self.index)
        causal._refresh_deadlines(self.world, {"compromissos": {}}, self.index, when())
        self.assertEqual(self.world["pendencias"], [])
        self.assertEqual(self.world[causal.KEY]["prazos"], {})
        self.assertEqual(self.world["concluidas_recentes"][-1]["resultado"], "gatilho_revogado")

    def test_substituicao_tem_nova_versao_e_nao_reutiliza_prazo_antigo(self):
        record = {"tipo": "encontro", "resumo": "Entregar mapa.", "envolvidos": ["a"], "janela": {"inicio": when()}}
        state = {"compromissos": {"mapa": record}}
        causal._refresh_deadlines(self.world, state, self.index, when())
        causal.dispatch(self.world, self.index)
        record["janela"]["inicio"] = when("09:00")
        causal._refresh_deadlines(self.world, state, self.index, when())
        self.assertEqual(self.world["pendencias"], [])
        causal._refresh_deadlines(self.world, state, self.index, when("09:00"))
        causal.dispatch(self.world, self.index)
        self.assertEqual(len(self.world["pendencias"]), 1)

    def test_inativo_nao_e_acionado_por_compromisso(self):
        self.index["agentes"]["a"]["estado"] = "inativo"
        state = {"compromissos": {"mapa": {"tipo": "encontro", "resumo": "Mapa.",
                  "envolvidos": ["a"], "janela": {"inicio": when()}}}}
        self.assertEqual(causal.deadline_events(state, self.index, {}, when()), [])

    def test_controle_malformado_ou_excedido_falha_explicito(self):
        for i in range(causal.MAX_CAUSES_PER_AGENT + 1):
            causal._enqueue(self.world, "a", str(i), signal(suffix=str(i)))
        with self.assertRaises(causal.ActivationError):
            causal._validate_control(self.world)


class CausalActivationIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.DurableMemoryIntegrationTest()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.repo = self.f.repo
        self.write = self.f.write
        self.people = self.f.people
        # A fixture NV-04 não precisava ativar Mundo Vivo. Nesta integração o
        # relógio precisa cumprir o schema real, sem afrouxar seu validador.
        time = self.read(causal.TIME)
        time["schema_tempo"] = 1
        self.write(causal.TIME.as_posix(), time)
        self.write("narrador/mundo/agenda.yaml", {"schema_agenda_mundo": 1, "natureza": "reservado",
                  "hora_amanhecer": "06:00", "reavaliacoes": {}, "agendamentos": []})
        self.write("narrador/mundo/estado.yaml", {"schema_estado_mundo": 1, "natureza": "controle_reservado",
                  "processado_ate": when(), "pendencias": [], "concluidas_recentes": []})
        agents = {}
        states = {}
        for aid in self.people:
            source = f"estado/relacoes/{aid}.yaml"
            name = self.read(source)["relacao"]["nome"]
            fact = {"descricao": "Preservar os acordos e agir com prudência.", "fonte": source, "evidencia": name}
            profile = f"narrador/agentes-leves/{aid}.yaml"
            self.write(profile, {"schema_agente_leve": 1, "natureza": "reservado", "id": aid,
                       "nome": name, "perfil_operacional": "recorrente_leve", "rotina_padrao": fact,
                       "objetivo_atual": fact, "iniciativas_possiveis": [fact],
                       "regra_de_reavaliacao": "Mudança não implica sucesso automático.", "fontes_canonicas": [source]})
            agents[aid] = {"nome": name, "perfil_operacional": "recorrente_leve", "estado": "ativo",
                           "prioridade": 1, "intervalo_dias": 3, "inicio": when(), "arquivo": profile,
                           "fontes_causais": [source], "perfil_blob_git": light._git_blob_sha(self.repo / profile)}
            states[aid] = {"estado": "ativo", "proxima_avaliacao": {"data": "8 Eleasis, 1372 DR", "hora": "06:00"},
                           "cache_negativo": None}
        self.write(causal.INDEX.as_posix(), {"schema_agentes_leves": 2, "natureza": "reservado", "agentes": agents,
                   "orcamento": {"max_novas_por_checkpoint": 1, "max_pendencias_abertas": 2,
                   "ordenacao": "mais_atrasado_prioridade_id", "max_checks_cache_negativo_por_checkpoint": 1}})
        self.write(causal.LIGHT_STATE.as_posix(), {"schema_estado_agentes_leves": 2,
                   "natureza": "controle_reservado", "agentes": states})
        barrier.sync(self.repo)

    def read(self, path):
        return yaml.safe_load((self.repo / path).read_text(encoding="utf-8"))

    def world(self):
        return mundo.load_world_state(self.repo)

    def simple(self, tid="conversa", deltas=None):
        return {"id": tid, "jogador": "Ren escuta sua aliada.", "narracao": "A aliada continuou a conversa.",
                "resumo": "Continuaram a conversa.", "modo": "interação", "deltas": deltas or []}

    def due_commitment(self, aid="silva_fixture", hour="08:08"):
        state = self.read(causal.STATE)
        state["compromissos"] = {"mapa": {"tipo": "encontro", "resumo": "Entregar o mapa.",
                    "envolvidos": ["ren", aid], "janela": {"inicio": when(hour), "fim": when("09:00")}}}
        self.write(causal.STATE.as_posix(), state)

    def mark(self, tid="marco"):
        return self.f.tx(tid, "marco", "Silva lembrou a Ren que a ponte está fechada para passagem.")

    def open_mark(self):
        cronica.conclude(self.repo, self.f.token, self.mark())
        return self.world()["pendencias"][0]

    def plan(self):
        prepared = batch.prepare_batch(self.repo)
        return {"lote_id": prepared["lote_id"], "sem_mudanca": [
                {"id": p["id"], "token": p["token"], "nota": NOTE} for p in prepared["itens"]]}

    def test_turno_neutro_preserva_duas_escritas_sem_leitura_causal(self):
        with patch.object(causal, "_read", side_effect=AssertionError("leitura causal indevida")):
            cronica.conclude(self.repo, self.f.token, self.simple())
        self.assertEqual(self.world()["pendencias"], [])
        self.assertEqual(len(transacoes.load_pending(self.repo)), 1)

    def test_mudanca_relacional_acorda_somente_afetado_antes_de_amanhecer(self):
        self.open_mark()
        self.assertEqual([p["agente_leve"] for p in self.world()["pendencias"]], ["silva_fixture"])
        self.assertEqual(transacoes.load_pending(self.repo), [])
        self.assertIn("ponte", json.dumps(self.read("estado/relacoes/silva_fixture.yaml"), ensure_ascii=False))
        self.assertTrue(barrier.load_status(self.repo)["bloqueado"])

    def test_promessa_nv04_dispara_por_envolvido_sem_inventar_fato_para_terceiro(self):
        cronica.conclude(self.repo, self.f.token, self.f.promise())
        self.assertEqual([p["agente_leve"] for p in self.world()["pendencias"]], ["silva_fixture"])
        self.assertNotIn("memorias_importantes", self.read("estado/relacoes/nera_fixture.yaml")["relacao"])

    def test_set_sem_alteracao_nao_dispara_nem_staging_inventa_sinal(self):
        value = self.read("estado/relacoes/silva_fixture.yaml")["relacao"]["nome"]
        tx = self.simple(deltas=[{"alvo": "relacao:silva_fixture", "op": "set", "caminho": "nome", "valor": value}])
        cronica.conclude(self.repo, self.f.token, tx)
        self.assertEqual(len(transacoes.load_pending(self.repo)), 1)
        consolidar.consolidate(self.repo, "cena")
        self.assertEqual(self.world()["pendencias"], [])

    def test_fronteira_encontra_prazo_em_cinco_minutos_mesmo_com_duas_rotinas(self):
        self.due_commitment()
        world = self.world()
        world["pendencias"] = [CausalQueueTest().routine(aid, digit) for aid, digit in
                               [("nera_fixture", "a"), ("luath_fixture", "b")]]
        self.write(causal.WORLD.as_posix(), world)
        before = self.f.hashes()
        result = fronteira_mundo.query(self.repo, DATE, "08:30")
        self.assertEqual(before, self.f.hashes())
        self.assertTrue(result["interromper"])
        self.assertEqual(result["fronteira"]["hora"], "08:08")
        self.assertEqual(result["fronteira"]["minutos_ate_fronteira"], 5)

    def test_cinco_minutos_acionam_prazo_no_writer_real_sem_terceira_chamada(self):
        self.due_commitment()
        tx = self.simple("tempo", [{"alvo": "tempo", "op": "instante", "valor": when("08:08")}])
        cronica.conclude(self.repo, self.f.token, tx)
        pending = self.world()["pendencias"]
        self.assertEqual([p["agente_leve"] for p in pending], ["silva_fixture"])
        self.assertTrue(any(c["tipo"] == "prazo" for c in pending[0][causal.PENDING_KEY].values()))
        self.assertIn("mapa", self.read(causal.STATE)["compromissos"])

    def test_preparar_lote_e_read_only_e_so_abre_um_fragmento_do_afetado(self):
        self.open_mark()
        before = self.f.hashes()
        reads = []
        original = Path.read_text
        def read(path, *args, **kwargs):
            reads.append(path.relative_to(self.repo).as_posix())
            return original(path, *args, **kwargs)
        with patch.object(Path, "read_text", read):
            result = batch.prepare_batch(self.repo)
        self.assertEqual(before, self.f.hashes())
        fragments = [p for p in reads if p.startswith(("estado/relacoes/", "estado/npcs/", "narrador/agentes-leves/"))
                     and not p.endswith(("/index.yaml", "/estado.yaml"))]
        self.assertEqual(fragments, ["estado/relacoes/silva_fixture.yaml"])
        self.assertNotIn("nera_fixture.yaml", str(reads))
        self.assertLessEqual(causal._size(result), 8192)

    def test_aplicar_lote_reutiliza_cache_negativo_e_retry_nao_reabre_prazo(self):
        self.open_mark()
        plan = self.plan()
        result = batch.apply_batch(self.repo, plan)
        self.assertEqual(result["quantidade_restante"], 0)
        self.assertIsNotNone(light.load_state(self.repo)["agentes"]["silva_fixture"]["cache_negativo"])
        before = self.f.hashes()
        batch.apply_batch(self.repo, plan)
        self.assertEqual(before, self.f.hashes())

    def test_noop_recusa_ausencia_de_ren_antes_de_qualquer_escrita(self):
        self.open_mark()
        plan = self.plan()
        plan["sem_mudanca"][0]["nota"] = "Ren não fez nada e nenhum fato novo aconteceu."
        before = self.f.hashes()
        with self.assertRaises(ValueError):
            batch.apply_batch(self.repo, plan)
        self.assertEqual(before, self.f.hashes())

    def test_token_fica_obsoleto_quando_causa_ou_fragmento_muda(self):
        self.open_mark()
        plan = self.plan()
        source = "estado/relacoes/silva_fixture.yaml"
        doc = self.read(source)
        doc["relacao"]["vinculo"] = "Outro acontecimento ainda não avaliado."
        self.write(source, doc)
        before = self.f.hashes()
        with self.assertRaises(ValueError):
            batch.apply_batch(self.repo, plan)
        self.assertEqual(before, self.f.hashes())

    def test_retry_do_turno_consolidado_nao_duplica_acionamento(self):
        self.open_mark()
        before = self.f.hashes()
        cronica.conclude(self.repo, self.f.token, self.mark())
        self.assertEqual(before, self.f.hashes())

    def test_journal_inclui_sinal_e_barreira_e_recupera_mesmos_bytes(self):
        with patch.object(turno, "detect_world_checkpoint", return_value=None):
            cronica.conclude(self.repo, self.f.token, self.mark())
        plan = consolidar.build_plan(self.repo, "cena")
        self.assertIn(causal.WORLD.as_posix(), plan["outputs"])
        self.assertIn(causal.BARRIER.as_posix(), plan["outputs"])
        journal = consolidar.stage_plan(self.repo, plan)
        with self.assertRaises(consolidar.ConsolidationError):
            consolidar.install_staged(self.repo, journal, fail_after=2)
        with self.assertRaises(ValueError):
            causal.reconcile(self.repo, self.world())
        consolidar.resume_consolidation(self.repo)
        self.assertEqual((self.repo / causal.WORLD).read_bytes(), plan["outputs"][causal.WORLD.as_posix()])
        self.assertTrue(barrier.load_status(self.repo)["bloqueado"])
        self.assertEqual(transacoes.load_pending(self.repo), [])

    def test_prazo_nao_e_suprimido_pelo_cache_negativo_valido(self):
        self.open_mark()
        batch.apply_batch(self.repo, self.plan())
        self.due_commitment(hour="08:03")
        barrier.sync(self.repo)
        pending = self.world()["pendencias"]
        self.assertEqual(len(pending), 1)
        self.assertTrue(any(c["tipo"] == "prazo" for c in pending[0][causal.PENDING_KEY].values()))

    def test_concluir_noop_direto_escoa_backlog_sem_outro_amanhecer(self):
        world = self.world()
        for aid in self.people:
            causal._enqueue(world, aid, "fonte", signal(f"estado/relacoes/{aid}.yaml", suffix=aid))
        causal.dispatch(world, light.load_index(self.repo))
        self.write(causal.WORLD.as_posix(), world)
        barrier.sync(self.repo)
        first = self.world()["pendencias"][0]["id"]
        before_ids = {p["id"] for p in self.world()["pendencias"]}
        light.conclude_noop(self.repo, first, NOTE)
        after = self.world()
        self.assertEqual(len(after["pendencias"]), 2)
        self.assertEqual(after[causal.KEY]["aguardando"], {})
        self.assertTrue({p["id"] for p in after["pendencias"]} - before_ids)
        self.assertTrue(barrier.load_status(self.repo)["bloqueado"])

    def test_cli_real_prepara_lote_com_causa_e_sem_leitura_da_transcricao(self):
        self.open_mark()
        before = self.f.hashes()
        process = subprocess.run([sys.executable, str(TOOLS / "resolver_fronteira.py"), "--repo", str(self.repo), "preparar"],
                                 check=False, capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = yaml.safe_load(process.stdout)
        self.assertEqual(result["itens"][0]["classificacao"], "avaliar_condicao_causal")
        self.assertNotIn("transcricao.md", str(result["fontes_lidas"]))
        self.assertEqual(before, self.f.hashes())

    def test_indice_de_fragmento_renomeado_continua_roteando_para_o_id_canonico(self):
        old = self.repo / "estado/relacoes/silva_fixture.yaml"
        new = self.repo / "estado/relacoes/silva_memoria.yaml"
        old.rename(new)
        index = self.read("estado/relacoes/index.yaml")
        index["relacoes"]["silva_fixture"]["arquivo"] = new.relative_to(self.repo).as_posix()
        self.write("estado/relacoes/index.yaml", index)
        li = light.load_index(self.repo)
        li["agentes"]["silva_fixture"]["fontes_causais"] = [new.relative_to(self.repo).as_posix()]
        self.write(causal.INDEX.as_posix(), li)
        self.open_mark()
        self.assertEqual([p["agente_leve"] for p in self.world()["pendencias"]], ["silva_fixture"])
        self.assertIn("silva_memoria.yaml", str(self.world()["pendencias"][0][causal.PENDING_KEY]))


if __name__ == "__main__":
    unittest.main()
