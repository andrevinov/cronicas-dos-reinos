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

import ecologia_local
import endpoints
import microeventos_locais as micro
import pressao_aventura as pressure


class AdventurePressurePureTest(unittest.TestCase):
    @staticmethod
    def _history(results: list[str]):
        return [{"resultado": result} for result in results]

    def test_niveis_sobem_em_4_6_8_cenas_secas(self):
        self.assertEqual(pressure.level_for(0), 0)
        self.assertEqual(pressure.level_for(3), 0)
        self.assertEqual(pressure.level_for(4), 1)
        self.assertEqual(pressure.level_for(5), 1)
        self.assertEqual(pressure.level_for(6), 2)
        self.assertEqual(pressure.level_for(7), 2)
        self.assertEqual(pressure.level_for(8), 3)
        self.assertEqual(pressure.level_for(40), 3)

    def test_microevento_encerra_sequencia_seca_operacional(self):
        history = self._history(["rotina"] * 8 + ["microevento", "rotina", "rotina"])
        self.assertEqual(pressure.dry_streak(history), 2)
        self.assertEqual(pressure.status_from_history(history)["nivel"], 0)

    def test_nivel_leve_promove_so_rotina_03(self):
        history = self._history(["rotina"] * 4)
        self.assertEqual(
            pressure.apply(history, token_id="rotina_01", base_result="rotina")["resultado"],
            "rotina",
        )
        promoted = pressure.apply(history, token_id="rotina_03", base_result="rotina")
        self.assertTrue(promoted["promovido"])
        self.assertEqual(promoted["resultado"], "microevento")

    def test_nivel_alto_promove_duas_fichas_e_critico_todas(self):
        high = self._history(["rotina"] * 6)
        self.assertFalse(pressure.apply(high, token_id="rotina_01", base_result="rotina")["promovido"])
        self.assertTrue(pressure.apply(high, token_id="rotina_02", base_result="rotina")["promovido"])
        critical = self._history(["rotina"] * 8)
        for token in ("rotina_01", "rotina_02", "rotina_03"):
            self.assertTrue(pressure.apply(critical, token_id=token, base_result="rotina")["promovido"])

    def test_microevento_base_nunca_e_rebaixado(self):
        result = pressure.apply(
            self._history(["rotina"] * 20),
            token_id="microevento_01",
            base_result="microevento",
        )
        self.assertFalse(result["promovido"])
        self.assertEqual(result["resultado"], "microevento")


class AdventurePressureIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        shutil.copytree(ROOT / "cenario/locais", self.repo / "cenario/locais")
        shutil.copytree(
            ROOT / "narrador/microeventos-locais",
            self.repo / "narrador/microeventos-locais",
        )
        self.index = micro.load_index(self.repo)
        self.ecology = ecologia_local.load_index(self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def _write_state(self, state):
        (self.repo / micro.STATE).write_text(
            yaml.safe_dump(state, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _prime_history(self, dry: int, token: str = "rotina_01"):
        state = micro.load_state(self.repo, self.index)
        local_ids = list(state["locais"])
        state["historico_recente"] = [
            {
                "cena_id": f"dry-{i}",
                "local_id": local_ids[i % len(local_ids)],
                "ficha_ocorrencia": "rotina_01",
                "resultado": "rotina",
            }
            for i in range(dry)
        ]
        target = state["locais"]["galeria_dos_escribas"]["ocorrencia"]
        target["ciclo"] = 1
        target["restantes"] = [token]
        self._write_state(state)

    def test_critica_promove_proxima_rotina_sem_reordenar_deck(self):
        self._prime_history(8, "rotina_01")
        before = micro.load_state(self.repo, self.index)
        planned = micro.plan(
            self.repo,
            local_id="galeria_dos_escribas",
            scene_id="critical-next",
            profile=self.ecology["perfis"]["galeria_dos_escribas"],
        )
        public = planned["publico"]
        self.assertEqual(public["resultado_base"], "rotina")
        self.assertEqual(public["resultado"], "avaliar_microevento")
        self.assertTrue(public["pressao_aventura"]["promovido"])
        self.assertEqual(public["pressao_aventura"]["nivel"], 3)
        # Plan continua read-only; o token só some do estado planejado.
        after = micro.load_state(self.repo, self.index)
        self.assertEqual(before, after)
        self.assertEqual(
            planned["estado_planejado"]["locais"]["galeria_dos_escribas"]["ocorrencia"]["ciclo"],
            1,
        )

    def test_sem_seca_mesma_ficha_continua_rotina(self):
        self._prime_history(0, "rotina_01")
        public = micro.plan(
            self.repo,
            local_id="galeria_dos_escribas",
            scene_id="normal-next",
            profile=self.ecology["perfis"]["galeria_dos_escribas"],
        )["publico"]
        self.assertEqual(public["resultado"], "rotina")
        self.assertEqual(public["pressao_aventura"]["nivel"], 0)
        self.assertFalse(public["pressao_aventura"]["promovido"])

    def test_pressao_nao_adiciona_fontes_ao_plano_local(self):
        self._prime_history(8, "rotina_01")
        public = micro.plan(
            self.repo,
            local_id="galeria_dos_escribas",
            scene_id="sources",
            profile=self.ecology["perfis"]["galeria_dos_escribas"],
        )["publico"]
        self.assertEqual(public["fontes_lidas"], [micro.INDEX.as_posix(), micro.STATE.as_posix()])

    def test_endpoint_usa_modificadores_sem_nova_leitura(self):
        preview = {
            "cena_id": "x",
            "preparacao_id": "p",
            "local": {
                "local_id": "galeria_dos_escribas",
                "microevento_local": {
                    "resultado": "avaliar_microevento",
                    "pressao_aventura": {
                        "nivel": 2,
                        "nome": "alta",
                        "cenas_secas_antes": 6,
                        "promovido": True,
                    },
                    "carta": {
                        "id": "c1",
                        "nome": "Carta",
                        "categoria": "fluxo",
                        "premissa": "Algo pequeno acontece.",
                        "canais_compativeis": ["trabalho"],
                        "tags_compativeis": ["trabalho"],
                        "atores_comuns": ["trabalhador"],
                        "guardrails": ["Não escalar."],
                    },
                },
            },
            "npcs_canonicos": [],
            "contexto_tags": [],
            "candidatos_contextuais": [],
            "presencas_contextuais": [],
            "entradas_contextuais": [],
            "operacoes_contextuais": [],
            "direcoes_contextuais": [],
            "encontros": [],
            "fontes_lidas": [micro.INDEX.as_posix(), micro.STATE.as_posix()],
        }
        result = endpoints.project_scene(preview)
        endpoints.validate_endpoint(result)
        self.assertEqual(
            result["modificadores"],
            [{
                "tipo": "pressao_seca_aventura",
                "nivel": 2,
                "nome": "alta",
                "cenas_secas_antes": 6,
                "promovido": True,
            }],
        )
        self.assertEqual(result["fontes_lidas"], preview["fontes_lidas"])

    def test_status_real_reflete_historico_persistido_sem_retroatividade(self):
        state = micro.load_state(ROOT, micro.load_index(ROOT))
        expected = pressure.status_from_history(list(state.get("historico_recente") or []))
        result = pressure.status(ROOT)
        self.assertEqual(result["pressao_aventura"], expected)
        self.assertEqual(
            result["fontes_lidas"],
            [micro.INDEX.as_posix(), micro.STATE.as_posix()],
        )


class AdventurePressureBudgetTest(unittest.TestCase):
    def test_contrato_bate_com_codigo_e_nao_cria_custo_novo(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/adventure-drought-pressure-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(contract["schema_adventure_drought_pressure"], 1)
        self.assertEqual(
            [item[0] for item in pressure.THRESHOLDS],
            [0, 4, 6, 8],
        )
        self.assertEqual(contract["limites"]["max_nivel"], 3)
        self.assertEqual(
            contract["limites"]["max_seca_reportada"],
            pressure.MAX_DRY_STREAK_REPORTED,
        )
        for field in (
            "max_fontes_adicionais_hot_path",
            "max_leituras_tempo_adicionais",
            "max_escritas_adicionais",
            "max_schedulers_novos",
            "max_scans_semanticos",
            "max_candidatos_adicionais_por_cena",
        ):
            self.assertEqual(contract["limites"][field], 0)
        inv = contract["invariantes"]
        self.assertTrue(inv["baralho_base_permanece_3_rotina_1_microevento"])
        self.assertTrue(inv["pressao_nao_reseta_nem_reordena_deck"])
        self.assertTrue(inv["pressao_so_atua_em_cena_local_ja_acionada"])
        self.assertTrue(inv["veto_canônico_continua_sem_reroll"])
        self.assertTrue(inv["task_14_pode_consultar_pressao_sem_mudar_este_contrato"])


if __name__ == "__main__":
    unittest.main()
