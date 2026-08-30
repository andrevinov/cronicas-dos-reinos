from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cena_mundo
import ecologia_local
import endpoints
import microeventos_locais as micro


class LocalMicroeventRepositoryTest(unittest.TestCase):
    def test_repositorio_real_valida_catalogo_estado_e_ecologia(self):
        result = micro.validate_repo(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["cartas"], 19)

        ecology = ecologia_local.load_index(ROOT)
        state = micro.load_state(ROOT, micro.load_index(ROOT))
        self.assertEqual(set(state["locais"]), set(ecology["perfis"]))
        self.assertEqual(len(state["locais"]), 11)

    def test_estado_real_nao_inventa_microeventos_retroativos(self):
        raw = yaml.safe_load((ROOT / micro.STATE).read_text(encoding="utf-8"))
        state = micro.load_state(ROOT, micro.load_index(ROOT))
        # O loader só valida o que foi persistido; jogar uma cena real pode
        # legitimamente tornar histórico/decks não vazios sem virar retroatividade.
        self.assertEqual(state, raw)
        self.assertLessEqual(len(state["historico_recente"]), micro.MAX_HISTORY)
        for event in state["historico_recente"]:
            self.assertIn(event["local_id"], state["locais"])
            self.assertIn(event["resultado"], {"rotina", "microevento"})

    def test_todo_local_tem_pool_ecologicamente_compativel(self):
        index = micro.load_index(ROOT)
        ecology = ecologia_local.load_index(ROOT)
        for local_id, profile in ecology["perfis"].items():
            eligible = micro.eligible_cards(index, profile)
            self.assertGreaterEqual(
                len(eligible), micro.MIN_ELIGIBLE_PER_LOCAL, local_id
            )
            for item in eligible:
                self.assertTrue(item["canais"], (local_id, item))
                self.assertTrue(item["tags"], (local_id, item))

    def test_roteadores_ficam_dentro_do_teto_sem_fragmentos(self):
        self.assertLessEqual((ROOT / micro.INDEX).stat().st_size, micro.MAX_INDEX_BYTES)
        self.assertLessEqual((ROOT / micro.STATE).stat().st_size, micro.MAX_STATE_BYTES)
        result = micro.simulate(ROOT, "Galeria dos Escribas", "teste-read-only")
        self.assertLessEqual(len(result["fontes_lidas"]), 4)
        self.assertFalse(any("/cartas/" in path for path in result["fontes_lidas"]))


class LocalMicroeventDeckTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        shutil.copytree(
            ROOT / "cenario/locais",
            self.repo / "cenario/locais",
        )
        shutil.copytree(
            ROOT / "narrador/microeventos-locais",
            self.repo / "narrador/microeventos-locais",
        )
        self.index = micro.load_index(self.repo)
        self.ecology = ecologia_local.load_index(self.repo)

        # Os testes do algoritmo partem de um baralho virgem. O estado copiado
        # da campanha pode estar no meio de um ciclo e com pressão de seca real.
        state = micro.load_state(self.repo, self.index)
        for local_state in state["locais"].values():
            local_state["ocorrencia"] = {"ciclo": 0, "restantes": []}
            local_state["cartas"] = {
                "ciclo": 0,
                "assinatura_pool": None,
                "restantes": [],
            }
        state["historico_recente"] = []
        micro.atomic(self.repo / micro.STATE, state)

    def tearDown(self):
        self.temp.cleanup()

    def _state_bytes(self) -> bytes:
        return (self.repo / micro.STATE).read_bytes()

    def _plan(self, local_id: str, scene_id: str):
        return micro.plan(
            self.repo,
            local_id=local_id,
            scene_id=scene_id,
            profile=self.ecology["perfis"][local_id],
        )

    def _commit(self, local_id: str, scene_id: str):
        planned = self._plan(local_id, scene_id)
        micro.commit_plan(self.repo, planned)
        return planned["publico"]

    def test_simular_mesma_cena_e_byte_a_byte_estavel_sem_escrever(self):
        before = self._state_bytes()
        first = self._plan("galeria_dos_escribas", "scene-a")["publico"]
        second = self._plan("galeria_dos_escribas", "scene-a")["publico"]
        self.assertEqual(first, second)
        self.assertEqual(self._state_bytes(), before)
        self.assertEqual(
            yaml.safe_dump(first, allow_unicode=True, sort_keys=False).encode(),
            yaml.safe_dump(second, allow_unicode=True, sort_keys=False).encode(),
        )

    def test_quatro_cenas_consumidas_tem_exatamente_um_microevento(self):
        local_id = "galeria_dos_escribas"
        occurrence_before = dict(
            micro.load_state(self.repo, self.index)["locais"][local_id]["ocorrencia"]
        )
        results = [
            self._commit(local_id, f"scene-{i}")
            for i in range(1, 5)
        ]
        self.assertEqual(
            sum(item["resultado"] == "avaliar_microevento" for item in results),
            1,
        )

        deck_size = len(self.index["ocorrencia"]["fichas"])
        expected_cycle = occurrence_before["ciclo"]
        expected_remaining = len(occurrence_before["restantes"])
        for _ in results:
            if expected_remaining == 0:
                expected_cycle += 1
                expected_remaining = deck_size
            expected_remaining -= 1

        occurrence_after = micro.load_state(self.repo, self.index)["locais"][local_id]["ocorrencia"]
        self.assertEqual(occurrence_after["ciclo"], expected_cycle)
        self.assertEqual(len(occurrence_after["restantes"]), expected_remaining)

    def test_cartas_nao_repetem_antes_de_esgotar_pool(self):
        cards: list[str] = []
        for i in range(1, 13):
            result = self._commit("galeria_dos_escribas", f"scene-{i}")
            if result["resultado"] == "avaliar_microevento":
                cards.append(result["carta"]["id"])
        self.assertEqual(len(cards), 3)
        self.assertEqual(len(cards), len(set(cards)))

    def test_reabrir_cena_recente_nao_consume_nova_ficha(self):
        first = self._commit("galeria_dos_escribas", "scene-repeat")
        state_before = micro.load_state(self.repo, self.index)
        second_plan = self._plan("galeria_dos_escribas", "scene-repeat")
        self.assertFalse(second_plan["alterou"])
        self.assertTrue(second_plan["publico"]["reutilizado"])
        micro.commit_plan(self.repo, second_plan)
        state_after = micro.load_state(self.repo, self.index)
        self.assertEqual(state_before, state_after)
        self.assertEqual(first["resultado"], second_plan["publico"]["resultado"])
        if "carta" in first:
            self.assertEqual(first["carta"]["id"], second_plan["publico"]["carta"]["id"])

    def test_locais_possuem_decks_independentes(self):
        self._commit("galeria_dos_escribas", "gallery-1")
        state = micro.load_state(self.repo, self.index)
        self.assertEqual(state["locais"]["galeria_dos_escribas"]["ocorrencia"]["ciclo"], 1)
        self.assertEqual(state["locais"]["narwhal_manor"]["ocorrencia"]["ciclo"], 0)
        self.assertEqual(state["locais"]["narwhal_manor"]["ocorrencia"]["restantes"], [])

    def test_pool_muda_quando_ecologia_muda_sem_rerrolar_ocorrencia(self):
        local_id = "galeria_dos_escribas"
        for i in range(1, 5):
            self._commit(local_id, f"base-{i}")
        state_before = micro.load_state(self.repo, self.index)
        cycle_before = state_before["locais"][local_id]["ocorrencia"]["ciclo"]

        profile = dict(self.ecology["perfis"][local_id])
        profile["tags"] = ["documentos", "carga"]
        profile["canais_microevento"] = ["documentos", "carga"]
        self.assertGreaterEqual(
            len(micro.eligible_cards(self.index, profile)),
            micro.MIN_ELIGIBLE_PER_LOCAL,
        )
        planned = micro.plan(
            self.repo,
            local_id=local_id,
            scene_id="pool-mudou",
            profile=profile,
        )
        # Planejamento por si só não toca o estado real nem reinicia a ocorrência.
        state_after = micro.load_state(self.repo, self.index)
        self.assertEqual(state_after["locais"][local_id]["ocorrencia"]["ciclo"], cycle_before)
        self.assertTrue(planned["alterou"])

    def test_configuracao_congela_veto_sem_reroll(self):
        rules = self.index["regras"]
        self.assertTrue(rules["carta_incompativel_com_canone_pode_ser_descartada_sem_reroll"])
        self.assertEqual(rules["npc_nomeado_automatico"], "proibido")
        self.assertEqual(rules["combate_automatico"], "proibido")
        self.assertEqual(rules["quest_automatica"], "proibido")
        self.assertEqual(rules["recompensa_automatica"], "proibido")
        self.assertEqual(rules["segredo_automatico"], "proibido")


class LocalMicroeventSceneIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        shutil.copytree(ROOT / "cenario/locais", self.repo / "cenario/locais")
        shutil.copytree(
            ROOT / "narrador/recompensas",
            self.repo / "narrador/recompensas",
        )
        shutil.copytree(
            ROOT / "narrador/microeventos-locais",
            self.repo / "narrador/microeventos-locais",
        )

    def tearDown(self):
        self.temp.cleanup()

    def _state_bytes(self) -> bytes:
        return (self.repo / micro.STATE).read_bytes()

    def test_preparar_simula_sem_consumir_e_sem_ler_tempo(self):
        before = self._state_bytes()
        with mock.patch.object(cena_mundo.interacoes_mundo, "_now") as now:
            preview = cena_mundo.prepare_scene(
                self.repo,
                scene_id="micro-prep",
                place="Galeria dos Escribas",
                action="entrar",
                tier=1,
                danger="baixa",
            )
        now.assert_not_called()
        self.assertEqual(self._state_bytes(), before)
        self.assertIn("ecologia", preview["local"])
        self.assertIn("microevento_local", preview["local"])
        self.assertIn(micro.INDEX.as_posix(), preview["fontes_lidas"])
        self.assertIn(micro.STATE.as_posix(), preview["fontes_lidas"])
        self.assertEqual(preview["resumo"]["microeventos_para_avaliar"], int(
            preview["local"]["microevento_local"]["resultado"] == "avaliar_microevento"
        ))

    def test_confirmar_consumo_unico_e_revalida_estado_do_baralho(self):
        history_before = len(
            micro.load_state(self.repo, micro.load_index(self.repo))["historico_recente"]
        )
        preview = cena_mundo.prepare_scene(
            self.repo,
            scene_id="micro-confirm",
            place="Galeria dos Escribas",
            action="entrar",
            tier=1,
            danger="baixa",
        )
        before = self._state_bytes()
        committed = cena_mundo.confirm_scene(
            self.repo,
            preparation_id=preview["preparacao_id"],
            scene_id="micro-confirm",
            place="Galeria dos Escribas",
            action="entrar",
            tier=1,
            danger="baixa",
        )
        self.assertNotEqual(self._state_bytes(), before)
        self.assertEqual(
            committed["local"]["microevento_local"]["resultado"],
            preview["local"]["microevento_local"]["resultado"],
        )
        state = micro.load_state(self.repo, micro.load_index(self.repo))
        self.assertEqual(len(state["historico_recente"]), history_before + 1)

    def test_estado_do_baralho_mudando_invalida_preparacao(self):
        preview = cena_mundo.prepare_scene(
            self.repo,
            scene_id="micro-stale",
            place="Galeria dos Escribas",
            action="entrar",
            tier=1,
            danger="baixa",
        )
        state_path = self.repo / micro.STATE
        state_path.write_text(
            state_path.read_text(encoding="utf-8") + "\n# concorrencia\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(cena_mundo.SceneGateError, "obsoleta"):
            cena_mundo.confirm_scene(
                self.repo,
                preparation_id=preview["preparacao_id"],
                scene_id="micro-stale",
                place="Galeria dos Escribas",
                action="entrar",
                tier=1,
                danger="baixa",
            )

    def test_endpoint_de_cena_carrega_ecologia_e_microevento_sem_nova_leitura(self):
        preview = cena_mundo.prepare_scene(
            self.repo,
            scene_id="micro-endpoint",
            place="Galeria dos Escribas",
            action="entrar",
            tier=1,
            danger="baixa",
        )
        result = endpoints.project_scene(preview)
        endpoints.validate_endpoint(result)
        self.assertIn("ecologia_local", result["filtros"])
        self.assertIn("baralho_microevento_local", result["filtros"])
        self.assertIn("ecologia_local", result["disponibilidade"])
        self.assertIn("microevento_local", result["disponibilidade"])
        gate = next(item for item in result["gates"] if item["tipo"] == "microevento_local")
        self.assertIn(gate["resultado"], {"rotina", "avaliar_microevento"})
        self.assertLessEqual(endpoints._rendered_size(result), endpoints.MAX_ENDPOINT_BYTES)

    def test_camadas_ausentes_preservam_fixture_legado(self):
        other = Path(tempfile.mkdtemp())
        try:
            shutil.copytree(ROOT / "cenario/locais", other / "cenario/locais")
            shutil.copytree(ROOT / "narrador/recompensas", other / "narrador/recompensas")
            result = cena_mundo.prepare_scene(
                other,
                scene_id="sem-micro-layer",
                place="Galeria dos Escribas",
                action="entrar",
                tier=1,
                danger="baixa",
            )
            self.assertNotIn("microevento_local", result["local"])
        finally:
            shutil.rmtree(other)


class LocalMicroeventBudgetTest(unittest.TestCase):
    def test_contrato_bate_com_codigo_e_semantica(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/local-microevent-deck-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        limits = contract["limites"]
        self.assertEqual(limits["max_cartas_catalogo"], micro.MAX_CARDS)
        self.assertEqual(limits["max_bytes_catalogo"], micro.MAX_INDEX_BYTES)
        self.assertEqual(limits["max_bytes_estado"], micro.MAX_STATE_BYTES)
        self.assertEqual(limits["max_tags_por_carta"], micro.MAX_CARD_TAGS)
        self.assertEqual(limits["max_canais_por_carta"], micro.MAX_CARD_CHANNELS)
        self.assertEqual(limits["max_chars_premissa"], micro.MAX_PREMISE_CHARS)
        self.assertEqual(limits["max_historico_recente"], micro.MAX_HISTORY)
        self.assertEqual(limits["min_cartas_compativeis_por_local"], micro.MIN_ELIGIBLE_PER_LOCAL)
        self.assertEqual(limits["ocorrencia_rotina"], 3)
        self.assertEqual(limits["ocorrencia_microevento"], 1)
        self.assertEqual(limits["max_fragmentos_narrativos_adicionais"], 0)
        self.assertEqual(limits["max_leituras_tempo_adicionais"], 0)
        self.assertEqual(limits["max_escritas_preparar"], 0)
        self.assertEqual(limits["max_escritas_confirmar_baralho"], 1)
        self.assertEqual(limits["max_schedulers_novos"], 0)
        self.assertEqual(limits["max_scans_repo_por_sorteio"], 0)
        self.assertTrue(contract["invariantes"]["veto_por_canone_nao_rerrola"])
        self.assertTrue(contract["invariantes"]["task_13_pode_aplicar_pressao_de_seca_sem_reescrever_catalogo"])

    def test_contrato_transacional_inclui_microevento_sem_relaxar_prepare(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/cena-transacional-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(contract["preparar"]["max_escritas_repo"], 0)
        self.assertTrue(contract["preparar"]["calcula_microevento_local"])
        self.assertTrue(contract["confirmar"]["consome_no_maximo_um_microevento_local"])
        self.assertTrue(contract["invariantes"]["sem_confirmacao_sem_consumo_microevento"])
        self.assertTrue(contract["invariantes"]["estado_microevento_local_e_fonte_do_fingerprint"])


if __name__ == "__main__":
    unittest.main()
