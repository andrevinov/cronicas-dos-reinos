from __future__ import annotations

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
import cena_mundo_v4
import interacoes_mundo
import mundo
import oportunidades
import pressao_aventura
import sidequest_gate_v2 as gate_v2


class SidequestGateV2RepositoryTest(unittest.TestCase):
    def test_repositorio_real_declara_v2_sem_resetar_estado_existente(self):
        index = oportunidades.load_index(ROOT)
        contract = gate_v2._contract(index)
        self.assertEqual(contract["versao"], 2)
        self.assertEqual(
            contract["promocoes_nada_por_nivel"],
            {0: 0, 1: 1, 2: 2, 3: 3},
        )
        state = oportunidades.load_state(ROOT, index)
        gate = state["gate"]
        token_ids = [item["id"] for item in index["gate"]["fichas"]]
        draws = gate["sorteios"]
        if draws == 0:
            self.assertEqual(gate["ciclo"], 0)
            self.assertEqual(gate["restantes"], [])
        else:
            expected_cycle = (draws - 1) // len(token_ids) + 1
            consumed_in_cycle = (draws - 1) % len(token_ids) + 1
            expected_order = oportunidades.gate_order(
                index["_seed"], expected_cycle, token_ids
            )
            self.assertEqual(gate["ciclo"], expected_cycle)
            self.assertEqual(gate["restantes"], expected_order[consumed_in_cycle:])

    def test_promocoes_sao_prefixos_deterministicos_e_preservam_raridade(self):
        index = oportunidades.load_index(ROOT)
        sets = [gate_v2.promoted_nada_tokens(index, level) for level in range(4)]
        self.assertEqual([len(value) for value in sets], [0, 1, 2, 3])
        self.assertTrue(set(sets[1]) <= set(sets[2]) <= set(sets[3]))
        self.assertEqual([2 + len(value) for value in sets], [2, 3, 4, 5])

    def test_cena_publica_permanece_v4_e_adapta_so_encontro(self):
        self.assertIs(
            cena_mundo_v4._core.interacoes_mundo.encounter_event,
            gate_v2.encounter_event,
        )
        self.assertIs(cena_mundo.prepare_scene, cena_mundo_v4.prepare_scene)
        self.assertFalse((ROOT / "ferramentas/cena_mundo_v5.py").exists())
        self.assertIsNot(gate_v2._BASE_ENCOUNTER_EVENT, gate_v2.encounter_event)

    def test_check_real_e_verde_e_pressao_derivada_sem_retroatividade(self):
        result = gate_v2.check(ROOT)
        expected = pressao_aventura.status_for_gate(ROOT)["pressao_aventura"]
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["versao"], 2)
        self.assertEqual(result["gate_base"], {"nada": 8, "oportunidade": 2})
        self.assertEqual(result["pressao_atual"], expected)


class SidequestGateV2SyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.now = mundo.parse_instant("14 Eleasis, 1372 DR", "12:00")
        gate_v2._PRESSURE_CACHE.clear()
        self._write(
            "narrador/oportunidades/index.yaml",
            {
                "schema_oportunidades": 1,
                "natureza": "reservado",
                "semente": "sidequest-v2-test",
                "gate": {
                    "versao": 2,
                    "modo": "baralho_sem_reposicao_sha256",
                    "fichas": [
                        *[
                            {"id": f"nada_{i:02d}", "resultado": "nada"}
                            for i in range(1, 9)
                        ],
                        {"id": "oportunidade_01", "resultado": "oportunidade"},
                        {"id": "oportunidade_02", "resultado": "oportunidade"},
                    ],
                    "pressao_aventura": {
                        "origem": "adventure_drought_pressure",
                        "fonte": "narrador/microeventos-locais/estado.yaml",
                        "ordenacao_promovidos": "sha256_seed_token",
                        "promocoes_nada_por_nivel": {0: 0, 1: 1, 2: 2, 3: 3},
                    },
                },
                "orcamento": {
                    "max_ativas": 2,
                    "max_em_aberto": 3,
                    "max_pendencias_avaliacao": 1,
                    "cooldown_oferta_dias": [2, 3],
                },
                "regras": {
                    "acionamento": "encontro_com_npc",
                    "scheduler": "proibido",
                    "scan_geral_npcs": "proibido",
                    "necessidade_nao_e_oferta": True,
                    "oferta_nao_e_aceite": True,
                    "consequencia_sem_ren_nao_e_automatica": True,
                    "pressao_aventura_modula_gate": True,
                    "pressao_nao_fura_orcamento": True,
                    "pressao_nao_rerrola": True,
                },
                "perfis": {
                    "npc_a": {
                        "nome": "NPC A",
                        "estado": "ativo",
                        "arquivo": "narrador/oportunidades/perfis/npc_a.yaml",
                    }
                },
            },
        )
        self._write(
            "narrador/oportunidades/estado.yaml",
            {
                "schema_estado_oportunidades": 1,
                "natureza": "controle_reservado",
                "gate": {"ciclo": 0, "restantes": [], "sorteios": 0},
                "cooldown_ate": None,
                "pendencias_avaliacao": {},
                "missoes": {},
                "sementes_consumidas": [],
                "encontros_recentes": [],
                "historico_recente": [],
            },
        )
        self._write(
            "narrador/oportunidades/perfis/npc_a.yaml",
            {
                "schema_perfil_oportunidades": 1,
                "natureza": "reservado",
                "estatuto": "sementes_nao_canonicas_ate_resolucao",
                "npc_id": "npc_a",
                "nome": "NPC A",
                "fonte_npc": "estado/relacoes/npc_a.yaml",
                "necessidades": [
                    {
                        "id": "pedido_a",
                        "tipo": "busca",
                        "semente": "Algo pequeno precisa ser encontrado.",
                        "janela": {"tipo": "a_qualquer_momento"},
                        "pode_reabrir": False,
                        "consequencia_sem_ren": "Outra pessoa pode resolver.",
                    },
                    {
                        "id": "pedido_b",
                        "tipo": "favor",
                        "semente": "Um favor discreto pode ser pedido.",
                        "janela": {"tipo": "a_qualquer_momento"},
                        "pode_reabrir": False,
                        "consequencia_sem_ren": "O favor pode perder relevância.",
                    },
                ],
            },
        )
        self._write(
            "estado/relacoes/index.yaml",
            {
                "schema_relacoes": 2,
                "relacoes": {
                    "npc_a": {
                        "nome": "NPC A",
                        "arquivo": "estado/relacoes/npc_a.yaml",
                    }
                },
            },
        )
        self._write(
            "estado/relacoes/npc_a.yaml",
            {"schema_relacao": 2, "id": "npc_a"},
        )
        self.set_pressure(0)

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def read_state(self):
        return yaml.safe_load(
            (self.repo / "narrador/oportunidades/estado.yaml").read_text(
                encoding="utf-8"
            )
        )

    def set_pressure(self, streak: int) -> None:
        history = [
            {
                "cena_id": f"seca-{i}",
                "local_id": "local_x",
                "ficha_ocorrencia": "rotina_01",
                "resultado": "rotina",
            }
            for i in range(streak)
        ]
        self._write(
            "narrador/microeventos-locais/estado.yaml",
            {
                "schema_estado_microeventos_locais": 1,
                "natureza": "controle_reservado",
                "locais": {},
                "historico_recente": history,
            },
        )
        gate_v2._PRESSURE_CACHE.clear()

    def force_token(self, token: str) -> None:
        state = self.read_state()
        state["gate"] = {"ciclo": 1, "restantes": [token], "sorteios": 0}
        self._write("narrador/oportunidades/estado.yaml", state)

    def promoted(self, level: int) -> list[str]:
        return gate_v2.promoted_nada_tokens(
            oportunidades.load_index(self.repo), level
        )

    def test_oportunidade_base_nao_le_pressao(self):
        self.force_token("oportunidade_01")
        with mock.patch.object(
            gate_v2,
            "pressure_for_gate",
            side_effect=AssertionError("pressão não deveria ser lida"),
        ):
            result = gate_v2.encounter_event(
                self.repo,
                "npc_a",
                now=self.now,
                encounter_id="base-op",
            )
        self.assertEqual(result["resultado"], "avaliar_sidequest")
        self.assertEqual(result["motivo"], "gate_oportunidade_base")
        self.assertFalse(result["gate_v2"]["promovido_por_pressao"])
        self.assertNotIn("pressao_aventura", result["gate_v2"])
        self.assertEqual(self.read_state()["missoes"], {})

    def test_nivel_zero_preserva_nada_e_nao_abre_perfil(self):
        token = self.promoted(3)[0]
        self.force_token(token)
        result = gate_v2.encounter_event(
            self.repo,
            "npc_a",
            now=self.now,
            encounter_id="normal",
        )
        self.assertEqual(result["resultado"], "interacao_normal")
        self.assertEqual(result["motivo"], "gate_sem_oportunidade")
        self.assertEqual(result["gate_v2"]["resultado_base"], "nada")
        self.assertFalse(result["gate_v2"]["promovido_por_pressao"])
        self.assertIn(
            "narrador/microeventos-locais/estado.yaml", result["fontes_lidas"]
        )
        self.assertNotIn(
            "narrador/oportunidades/perfis/npc_a.yaml", result["fontes_lidas"]
        )

    def test_pressao_critica_promove_nada_mas_so_cria_potencial(self):
        self.set_pressure(8)
        token = self.promoted(3)[0]
        self.force_token(token)
        result = gate_v2.encounter_event(
            self.repo,
            "npc_a",
            now=self.now,
            encounter_id="critico",
        )
        self.assertEqual(result["resultado"], "avaliar_sidequest")
        self.assertEqual(result["motivo"], "gate_v2_promovido_por_pressao")
        self.assertEqual(result["gate_v2"]["resultado_base"], "nada")
        self.assertEqual(result["gate_v2"]["resultado"], "oportunidade")
        self.assertTrue(result["gate_v2"]["promovido_por_pressao"])
        self.assertEqual(result["gate_v2"]["pressao_aventura"]["nivel"], 3)
        self.assertEqual(result["pendencia"]["estado"], "potencial")
        state = self.read_state()
        self.assertEqual(state["missoes"], {})
        self.assertEqual(len(state["pendencias_avaliacao"]), 1)
        persisted = next(iter(state["pendencias_avaliacao"].values()))
        self.assertNotIn("origem_gate", persisted)

    def test_critica_ainda_deixa_cinco_resultados_nada_no_ciclo(self):
        self.set_pressure(8)
        index = oportunidades.load_index(self.repo)
        promoted = set(gate_v2.promoted_nada_tokens(index, 3))
        unpromoted = next(
            item["id"]
            for item in index["gate"]["fichas"]
            if item["resultado"] == "nada" and item["id"] not in promoted
        )
        self.force_token(unpromoted)
        result = gate_v2.encounter_event(
            self.repo,
            "npc_a",
            now=self.now,
            encounter_id="critico-nada",
        )
        self.assertEqual(result["resultado"], "interacao_normal")
        self.assertFalse(result["gate_v2"]["promovido_por_pressao"])
        self.assertEqual(len(promoted), 3)

    def test_barreira_bloqueia_antes_de_draw_e_pressao(self):
        state = self.read_state()
        state["cooldown_ate"] = mundo.instant_parts(
            mundo.WorldInstant(self.now.minute + 1440)
        )
        self._write("narrador/oportunidades/estado.yaml", state)
        with mock.patch.object(
            gate_v2,
            "pressure_for_gate",
            side_effect=AssertionError("pressão não deveria ser lida"),
        ):
            result = gate_v2.encounter_event(
                self.repo,
                "npc_a",
                now=self.now,
                encounter_id="bloqueado",
            )
        self.assertEqual(result["motivo"], "cooldown_global_de_oferta")
        self.assertEqual(self.read_state()["gate"]["sorteios"], 0)
        self.assertNotIn("gate_v2", result)

    def test_mesmo_encontro_nao_relanca_gate_v2(self):
        self.set_pressure(8)
        token = self.promoted(3)[0]
        self.force_token(token)
        first = gate_v2.encounter_event(
            self.repo,
            "npc_a",
            now=self.now,
            encounter_id="idem",
        )
        self.assertEqual(first["resultado"], "avaliar_sidequest")
        draws = self.read_state()["gate"]["sorteios"]
        second = gate_v2.encounter_event(
            self.repo,
            "npc_a",
            now=self.now,
            encounter_id="idem",
        )
        self.assertEqual(second["motivo"], "encontro_ja_processado")
        self.assertEqual(self.read_state()["gate"]["sorteios"], draws)
        self.assertNotIn("gate_v2", second)

    def test_camadas_de_pressao_ausentes_equivalem_nivel_zero(self):
        shutil.rmtree(self.repo / "narrador/microeventos-locais")
        gate_v2._PRESSURE_CACHE.clear()
        token = self.promoted(3)[0]
        self.force_token(token)
        result = gate_v2.encounter_event(
            self.repo,
            "npc_a",
            now=self.now,
            encounter_id="legacy",
        )
        self.assertEqual(result["resultado"], "interacao_normal")
        self.assertFalse(
            result["gate_v2"]["pressao_aventura"]["configurada"]
        )
        self.assertNotIn(
            "narrador/microeventos-locais/estado.yaml", result["fontes_lidas"]
        )

    def test_configuracao_parcial_de_pressao_falha_sem_persistir_draw(self):
        shutil.rmtree(self.repo / "narrador/microeventos-locais")
        (self.repo / "narrador/microeventos-locais").mkdir(parents=True)
        gate_v2._PRESSURE_CACHE.clear()
        token = self.promoted(3)[0]
        self.force_token(token)
        before = (self.repo / "narrador/oportunidades/estado.yaml").read_bytes()
        with self.assertRaises(interacoes_mundo.IntegrationError):
            gate_v2.encounter_event(
                self.repo,
                "npc_a",
                now=self.now,
                encounter_id="parcial",
            )
        after = (self.repo / "narrador/oportunidades/estado.yaml").read_bytes()
        self.assertEqual(before, after)

    def test_cache_de_pressao_e_um_por_mesma_versao_de_estado(self):
        self.set_pressure(6)
        index = oportunidades.load_index(self.repo)
        state_a = oportunidades.load_state(self.repo, index)
        state_b = oportunidades.load_state(self.repo, index)
        promoted = gate_v2.promoted_nada_tokens(index, 2)
        state_a["gate"] = {
            "ciclo": 1,
            "restantes": [promoted[0]],
            "sorteios": 0,
        }
        state_b["gate"] = {
            "ciclo": 1,
            "restantes": [promoted[1]],
            "sorteios": 0,
        }
        original = pressao_aventura.status_for_gate
        with mock.patch.object(
            gate_v2.pressao_aventura,
            "status_for_gate",
            wraps=original,
        ) as call:
            gate_v2.draw_gate_v2(self.repo, state_a, index)
            gate_v2.draw_gate_v2(self.repo, state_b, index)
        self.assertEqual(call.call_count, 1)

    def test_adaptador_chama_orquestrador_existente_uma_vez(self):
        self.force_token("oportunidade_01")
        with mock.patch.object(
            gate_v2,
            "_BASE_ENCOUNTER_EVENT",
            wraps=gate_v2._BASE_ENCOUNTER_EVENT,
        ) as call:
            result = gate_v2.encounter_event(
                self.repo,
                "npc_a",
                now=self.now,
                encounter_id="single-orchestrator",
            )
        self.assertEqual(result["resultado"], "avaliar_sidequest")
        self.assertEqual(call.call_count, 1)

    def test_preview_shadow_nao_persiste_potencial_promovido(self):
        self.set_pressure(8)
        token = self.promoted(3)[0]
        self.force_token(token)
        before = (self.repo / "narrador/oportunidades/estado.yaml").read_bytes()
        with cena_mundo._preview_effects(self.repo):
            result = gate_v2.encounter_event(
                self.repo,
                "npc_a",
                now=self.now,
                encounter_id="preview",
            )
        self.assertEqual(result["resultado"], "avaliar_sidequest")
        self.assertEqual(
            before,
            (self.repo / "narrador/oportunidades/estado.yaml").read_bytes(),
        )


class SidequestGateV2BudgetTest(unittest.TestCase):
    def test_contrato_congela_raridade_orcamento_e_custo(self):
        data = yaml.safe_load(
            (ROOT / "baseline/sidequest-gate-v2-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(data["schema_orcamento_sidequest_gate_v2"], 1)
        self.assertEqual(data["gate_base"]["nada"], 8)
        self.assertEqual(data["gate_base"]["oportunidade"], 2)
        self.assertEqual(
            data["pressao"]["promocoes_nada_por_nivel"],
            {0: 0, 1: 1, 2: 2, 3: 3},
        )
        self.assertEqual(
            data["pressao"]["oportunidades_efetivas_max_por_ciclo"],
            {0: 2, 1: 3, 2: 4, 3: 5},
        )
        self.assertEqual(data["limites"]["max_draws_base_por_encontro"], 1)
        self.assertEqual(data["limites"]["max_rerolls"], 0)
        self.assertEqual(data["limites"]["max_schedulers_novos"], 0)
        self.assertTrue(data["invariantes"]["pressao_nao_fura_cooldown"])
        self.assertTrue(data["invariantes"]["potencial_nao_e_oferta"])

    def test_orcamento_integrado_explicita_unica_fonte_nova(self):
        data = yaml.safe_load(
            (ROOT / "baseline/mundo-vivo-integracao-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        v2 = data["limites"]["sidequest_gate_v2"]
        self.assertEqual(v2["max_fontes_pressao_por_ficha_nada"], 1)
        self.assertEqual(v2["max_draws_por_encontro"], 1)
        self.assertEqual(v2["max_rerolls"], 0)
        self.assertEqual(data["limites"]["encontro_gate_nada"]["max_fontes"], 4)
        self.assertEqual(
            data["limites"]["encontro_oportunidade"]["max_fontes"], 5
        )


if __name__ == "__main__":
    unittest.main()
