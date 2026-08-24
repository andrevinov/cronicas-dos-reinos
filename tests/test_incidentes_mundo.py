from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cena_mundo
import ecologia_local
import endpoints
import incidentes_mundo as incidents


class IncidentRepositoryTest(unittest.TestCase):
    def test_repo_real_valida_catalogo_estado_e_cobertura(self):
        result = incidents.check(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertGreaterEqual(result["cartas"], 11)
        self.assertLessEqual(result["cartas"], incidents.MAX_CARDS)

    def test_catalogo_cobre_tipos_serios_planejados(self):
        index = incidents.load_index(ROOT)
        types = {card["tipo"] for card in index["cartas"].values()}
        expected = {
            "briga", "roubo", "perseguicao", "acidente", "incendio",
            "desabamento", "crianca_em_perigo", "extorsao", "guarda",
            "tumulto", "ferimento",
        }
        self.assertTrue(expected <= types)

    def test_global_e_local_tem_frequencias_distintas_e_raras(self):
        index = incidents.load_index(ROOT)
        global_outcomes = [item["resultado"] for item in index["frequencia"]["global"]["fichas"]]
        local_outcomes = [item["resultado"] for item in index["frequencia"]["local"]["fichas"]]
        self.assertEqual(global_outcomes.count("incidente"), 1)
        self.assertEqual(global_outcomes.count("rotina"), 11)
        self.assertEqual(local_outcomes.count("incidente"), 1)
        self.assertEqual(local_outcomes.count("rotina"), 7)

    def test_todo_local_tem_pool_base_sem_depender_de_condicao(self):
        index = incidents.load_index(ROOT)
        ecology = ecologia_local.load_index(ROOT)
        for local_id, profile in ecology["perfis"].items():
            eligible = incidents.eligible_cards(index, profile, scope="local", conditions=[])
            self.assertGreaterEqual(len(eligible), incidents.MIN_LOCAL_ELIGIBLE, local_id)

    def test_condicao_habilita_carta_sem_mudar_baralho_de_ocorrencia(self):
        index = incidents.load_index(ROOT)
        profile = ecologia_local.load_index(ROOT)["perfis"]["narwhal_manor"]
        base = incidents.eligible_cards(index, profile, scope="local", conditions=[])
        rainy = incidents.eligible_cards(
            index,
            profile,
            scope="local",
            conditions=[
                {
                    "tipo": "clima",
                    "intensidade": "forte",
                    "marcadores": ["chuva_forte"],
                }
            ],
        )
        self.assertNotIn("queda_em_piso_molhado", base)
        self.assertIn("queda_em_piso_molhado", rainy)
        self.assertEqual(
            index["frequencia"]["local"]["fichas"],
            incidents.load_index(ROOT)["frequencia"]["local"]["fichas"],
        )

    def test_guardrails_proibem_quest_loot_segredo_e_controle_de_ren(self):
        rules = incidents.load_index(ROOT)["regras"]
        for key in (
            "sem_npc_nomeado_automatico",
            "sem_sidequest_automatica",
            "sem_recompensa_automatica",
            "sem_segredo_automatico",
            "sem_conhecimento_automatico",
            "ren_pode_nao_intervir",
            "combate_nao_e_obrigatorio",
            "ameaca_desproporcional_exige_saida_observavel",
        ):
            self.assertTrue(rules[key])
        self.assertEqual(rules["max_incidentes_por_cena"], 1)
        self.assertEqual(rules["scheduler"], "proibido")


class IncidentDeckTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        shutil.copytree(ROOT / "narrador/incidentes-v2", self.repo / "narrador/incidentes-v2")
        self.index = incidents.load_index(self.repo)
        self.profile = ecologia_local.load_index(ROOT)["perfis"]["galeria_dos_escribas"]

    def tearDown(self):
        self.temp.cleanup()

    def _state(self):
        return incidents.load_state(self.repo, self.index)

    def _plan(self, scene_id: str, conditions=None):
        return incidents.plan(
            self.repo,
            scene_id=scene_id,
            local_id="galeria_dos_escribas",
            profile=self.profile,
            conditions=conditions or [],
        )

    def test_plan_e_read_only_e_deterministico(self):
        before = (self.repo / incidents.STATE).read_bytes()
        first = self._plan("incident-read-only")["publico"]
        second = self._plan("incident-read-only")["publico"]
        self.assertEqual(first, second)
        self.assertEqual((self.repo / incidents.STATE).read_bytes(), before)

    def test_commit_e_retry_nao_consumem_duas_vezes(self):
        first_plan = self._plan("incident-retry")
        incidents.commit_plan(self.repo, first_plan)
        state_before = self._state()
        second = self._plan("incident-retry")
        self.assertFalse(second["alterou"])
        self.assertTrue(second["publico"]["reutilizado"])
        incidents.commit_plan(self.repo, second)
        self.assertEqual(self._state(), state_before)
        self.assertEqual(second["publico"]["resultado"], first_plan["publico"]["resultado"])

    def test_no_maximo_um_incidente_por_cena(self):
        for i in range(1, 40):
            plan = self._plan(f"incident-{i}")
            public = plan["publico"]
            incidents.commit_plan(self.repo, plan)
            if public["resultado"] == "avaliar_incidente":
                self.assertIn(public["origem"], {"global", "local"})
                self.assertIn("incidente", public)
                self.assertGreaterEqual(len(public["incidente"]["rotas_observaveis"]), 1)
                self.assertNotIn("sidequest", public["incidente"])

    def test_baralho_global_e_local_tem_estado_separado(self):
        plan = self._plan("incident-state-separation")
        incidents.commit_plan(self.repo, plan)
        state = self._state()
        self.assertGreaterEqual(state["global"]["ocorrencia"]["ciclo"], 1)
        self.assertIn("galeria_dos_escribas", state["locais"])
        self.assertGreaterEqual(state["locais"]["galeria_dos_escribas"]["ocorrencia"]["ciclo"], 1)

    def test_cartas_condicionais_nao_entram_sem_marcador(self):
        base = incidents.eligible_cards(self.index, self.profile, scope="local", conditions=[])
        condition_only = {
            card_id
            for card_id, card in self.index["cartas"].items()
            if card["condicoes_necessarias"]
        }
        self.assertFalse(condition_only & set(base))


class IncidentSceneIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        shutil.copytree(ROOT / "cenario/locais", self.repo / "cenario/locais")
        shutil.copytree(ROOT / "narrador/recompensas", self.repo / "narrador/recompensas")
        shutil.copytree(ROOT / "narrador/microeventos-locais", self.repo / "narrador/microeventos-locais")
        shutil.copytree(ROOT / "narrador/incidentes-v2", self.repo / "narrador/incidentes-v2")

    def tearDown(self):
        self.temp.cleanup()

    def test_preparar_cena_espacial_nao_consumir_estado_task35(self):
        before = (self.repo / incidents.STATE).read_bytes()
        preview = cena_mundo.prepare_scene(
            self.repo,
            scene_id="task35-prep",
            place="Galeria dos Escribas",
            action="entrar",
            tier=1,
            danger="baixa",
        )
        self.assertEqual((self.repo / incidents.STATE).read_bytes(), before)
        self.assertIn(incidents.INDEX.as_posix(), preview["fontes_lidas"])
        self.assertIn(incidents.STATE.as_posix(), preview["fontes_lidas"])
        self.assertIn("incidentes_para_avaliar", preview["resumo"])
        self.assertIn(preview["resumo"]["incidentes_para_avaliar"], {0, 1})
        if preview["resumo"]["incidentes_para_avaliar"]:
            incident = preview["incidente_mundo"]["incidente"]
            self.assertTrue(incident["rotas_observaveis"])
            self.assertTrue(incident["guardrails"])

    def test_endpoint_quente_projeta_incidente_sem_nova_leitura(self):
        preview = cena_mundo.prepare_scene(
            self.repo,
            scene_id="task35-endpoint",
            place="Galeria dos Escribas",
            action="entrar",
            tier=1,
            danger="baixa",
        )
        sources_before = list(preview["fontes_lidas"])
        preview["incidente_mundo"] = {
            "resultado": "avaliar_incidente",
            "origem": "local",
            "incidente": {
                "id": "briga_publica",
                "tipo": "briga",
                "severidade": "moderada",
                "premissa": "Uma discussão degrada e ameaça ferir terceiros próximos.",
                "rotas_observaveis": ["separar", "negociar", "chamar_ajuda", "nao_intervir", "extra"],
                "atores_comuns": ["trabalhador", "cliente", "guarda", "vizinho", "extra"],
                "guardrails": [
                    "Não escrever decisão de Ren.",
                    "Não criar side quest automaticamente.",
                    "Guardrail excedente não deve entrar no endpoint.",
                ],
            },
        }
        projected = endpoints.project_scene(preview)
        self.assertEqual(projected["ids"]["incidente_mundo"], "briga_publica")
        self.assertIn("incidentes_mundo_v2", projected["filtros"])
        self.assertEqual(projected["gates"][-1]["tipo"], "incidente_mundo_v2")
        view = projected["disponibilidade"]["incidente_mundo"]
        self.assertEqual(view["tipo"], "briga")
        self.assertEqual(len(view["rotas_observaveis"]), endpoints.MAX_INCIDENT_ROUTES)
        self.assertEqual(len(view["atores_comuns"]), endpoints.MAX_INCIDENT_ACTORS)
        self.assertEqual(len(view["guardrails"]), endpoints.MAX_INCIDENT_GUARDRAILS)
        self.assertEqual(projected["fontes_lidas"], sources_before)
        endpoints._base.validate_endpoint(projected)

    def test_confirmar_consumo_unico_do_baralho(self):
        preview = cena_mundo.prepare_scene(
            self.repo,
            scene_id="task35-confirm",
            place="Galeria dos Escribas",
            action="entrar",
            tier=1,
            danger="baixa",
        )
        before = (self.repo / incidents.STATE).read_bytes()
        committed = cena_mundo.confirm_scene(
            self.repo,
            preparation_id=preview["preparacao_id"],
            scene_id="task35-confirm",
            place="Galeria dos Escribas",
            action="entrar",
            tier=1,
            danger="baixa",
        )
        self.assertNotEqual((self.repo / incidents.STATE).read_bytes(), before)
        history = incidents.load_state(self.repo, incidents.load_index(self.repo))["historico_recente"]
        self.assertEqual(sum(item["cena_id"] == "task35-confirm" for item in history), 1)
        self.assertEqual(
            committed["resumo"]["incidentes_para_avaliar"],
            preview["resumo"]["incidentes_para_avaliar"],
        )

    def test_fixture_sem_task35_preserva_fluxo_antigo(self):
        shutil.rmtree(self.repo / "narrador/incidentes-v2")
        preview = cena_mundo.prepare_scene(
            self.repo,
            scene_id="task35-absent",
            place="Galeria dos Escribas",
            action="entrar",
            tier=1,
            danger="baixa",
        )
        self.assertNotIn(incidents.INDEX.as_posix(), preview["fontes_lidas"])
        self.assertNotIn("incidente_mundo", preview)

    def test_task35_parcial_falha_fechado(self):
        (self.repo / incidents.STATE).unlink()
        with self.assertRaisesRegex(cena_mundo.SceneGateError, "incidentes declarada parcialmente"):
            cena_mundo.prepare_scene(
                self.repo,
                scene_id="task35-partial",
                place="Galeria dos Escribas",
                action="entrar",
                tier=1,
                danger="baixa",
            )


class IncidentBudgetTest(unittest.TestCase):
    def test_contrato_bate_com_codigo(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/world-local-incidents-v2-orcamento.yaml").read_text(encoding="utf-8")
        )
        limits = contract["limites"]
        self.assertEqual(limits["chamadas_extras_turno"], 0)
        self.assertEqual(limits["leituras_task35_cena_sem_local"], 0)
        self.assertEqual(limits["leituras_task35_cena_espacial"], 2)
        self.assertEqual(limits["max_incidentes_por_cena"], 1)
        self.assertEqual(limits["max_cartas"], incidents.MAX_CARDS)
        self.assertEqual(limits["max_historico"], incidents.MAX_HISTORY)
        self.assertEqual(limits["max_index_bytes"], incidents.MAX_INDEX_BYTES)
        self.assertEqual(limits["max_estado_bytes"], incidents.MAX_STATE_BYTES)
        self.assertEqual(limits["schedulers_novos"], 0)
        self.assertEqual(limits["scans_globais"], 0)
        self.assertTrue(all(contract["invariantes"].values()))
        self.assertLessEqual((ROOT / incidents.INDEX).stat().st_size, incidents.MAX_INDEX_BYTES)
        self.assertLessEqual((ROOT / incidents.STATE).stat().st_size, incidents.MAX_STATE_BYTES)


if __name__ == "__main__":
    unittest.main()