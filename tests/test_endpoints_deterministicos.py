from __future__ import annotations

import argparse
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import endpoints


class EndpointProjectionSnapshotTest(unittest.TestCase):
    def assert_contract(self, value, endpoint_id):
        self.assertEqual(value["schema_endpoint_deterministico"], 1)
        self.assertEqual(value["endpoint"], endpoint_id)
        self.assertTrue(value["deterministico"])
        self.assertFalse(value["mutante"])
        self.assertLessEqual(endpoints._rendered_size(value), endpoints.MAX_ENDPOINT_BYTES)
        endpoints.validate_endpoint(value)

    def test_scene_snapshot(self):
        preview = {
            "cena_id": "scene-x",
            "preparacao_id": "scene-prep-x",
            "local": {"local_id": "local_x"},
            "npcs_canonicos": ["npc_a", "npc_b"],
            "duplicatas_colapsadas": [{"recebido": "A", "npc_id": "npc_a"}],
            "contexto_tags": ["local:porto"],
            "candidatos_contextuais": [{"id": "candidato_x"}],
            "presencas_contextuais": [{"agente": "presenca_x"}],
            "entradas_contextuais": [{"entrada": "entrada_x"}],
            "operacoes_contextuais": [{"operacao": "operacao_x"}],
            "direcoes_contextuais": [{"direcao": "direcao_x"}],
            "encontros": [
                {
                    "npc_id": "npc_a",
                    "encontro_id": "enc-a",
                    "resultado": "interacao_normal",
                    "motivo": "gate_sem_oportunidade",
                    "ficha": "nada_01",
                },
                {
                    "npc_id": "npc_b",
                    "encontro_id": "enc-b",
                    "resultado": "avaliar_sidequest",
                    "ficha": "oportunidade_01",
                    "pendencia": {"id": "sq-1"},
                },
            ],
            "fontes_lidas": ["a.yaml", "b.yaml"],
        }
        result = endpoints.project_scene(preview)
        self.assert_contract(result, "cena.preparar")
        self.assertEqual(
            result,
            {
                "schema_endpoint_deterministico": 1,
                "ok": True,
                "endpoint": "cena.preparar",
                "deterministico": True,
                "mutante": False,
                "ids": {
                    "cena": "scene-x",
                    "preparacao": "scene-prep-x",
                    "local": "local_x",
                    "npcs": ["npc_a", "npc_b"],
                    "encontros": ["enc-a", "enc-b"],
                    "sidequests_potenciais": ["sq-1"],
                    "presencas_contextuais": ["presenca_x"],
                    "entradas_contextuais": ["entrada_x"],
                    "operacoes_contextuais": ["operacao_x"],
                    "direcoes_contextuais": ["direcao_x"],
                    "candidatos_contextuais": ["candidato_x"],
                },
                "filtros": [
                    "resolucao_npc_canonica",
                    "colapso_duplicatas_npc",
                    "registro_local_canonico",
                    "tags_contextuais_tipadas",
                    "exclusao_elenco_contextual",
                ],
                "disponibilidade": {
                    "confirmacao": True,
                    "local_solicitado": True,
                    "npcs": 2,
                    "candidatos_contextuais": 1,
                    "sidequests_para_avaliar": 1,
                },
                "gates": [
                    {
                        "tipo": "sidequest_encontro",
                        "npc_id": "npc_a",
                        "resultado": "interacao_normal",
                        "motivo": "gate_sem_oportunidade",
                        "ficha": "nada_01",
                    },
                    {
                        "tipo": "sidequest_encontro",
                        "npc_id": "npc_b",
                        "resultado": "avaliar_sidequest",
                        "ficha": "oportunidade_01",
                        "pendencia_id": "sq-1",
                    },
                ],
                "modificadores": [],
                "deltas_previstos": [],
                "proximo_passo": {
                    "acao": "registrar_turno_e_confirmar_preparacao",
                    "porta_confirmacao": "cena_mundo.py confirmar",
                    "preparacao_id": "scene-prep-x",
                    "antes": "avaliar_potencial_sem_converter_em_oferta_automaticamente",
                },
                "fontes_lidas": ["a.yaml", "b.yaml"],
            },
        )

    def test_boundary_snapshot(self):
        result = endpoints.project_boundary(
            {
                "ok": True,
                "inicio": {"data": "14 Eleasis, 1372 DR", "hora": "21:20"},
                "alvo": {"data": "15 Eleasis, 1372 DR", "hora": "07:00"},
                "interromper": True,
                "fronteira": {
                    "data": "15 Eleasis, 1372 DR",
                    "hora": "06:00",
                    "minutos_ate_fronteira": 520,
                    "motivos": [
                        {"camada": "agentes_leves", "ids": ["bram_vask"]},
                        {"camada": "eventos_mundo", "ids": ["baralho_mundial"]},
                    ],
                },
                "fontes_lidas": ["estado/tempo.yaml"],
            }
        )
        self.assert_contract(result, "mundo.fronteira")
        self.assertEqual(
            result["ids"]["motivos_por_camada"],
            {
                "agentes_leves": ["bram_vask"],
                "eventos_mundo": ["baralho_mundial"],
            },
        )
        self.assertEqual(result["gates"][0]["resultado"], "interromper")
        self.assertEqual(
            result["proximo_passo"]["acao"],
            "resolver_ate_fronteira_e_checkpoint_antes_de_continuar",
        )

    def test_pending_snapshot(self):
        result = endpoints.project_pending(
            {
                "quantidade": 2,
                "pendencias": [
                    {"id": "p2", "tipo": "evento_mundial"},
                    {"id": "p1", "tipo": "reavaliar_agente_leve"},
                ],
                "fontes_lidas": ["narrador/mundo/estado.yaml"],
            }
        )
        self.assert_contract(result, "mundo.pendencias")
        self.assertEqual(result["ids"]["pendencias"], ["p2", "p1"])
        self.assertEqual(
            result["ids"]["por_tipo"],
            {
                "evento_mundial": ["p2"],
                "reavaliar_agente_leve": ["p1"],
            },
        )
        self.assertFalse(result["disponibilidade"]["novo_turno"])
        self.assertEqual(result["gates"], [{"tipo": "barreira_mundo", "resultado": "bloqueado"}])

    def test_direction_snapshot(self):
        result = endpoints.project_direction(
            {
                "ok": True,
                "direcao_id": "ponte",
                "permitido": True,
                "executavel": False,
                "estado": "ativa",
                "marco_atual": {
                    "id": "m1",
                    "criterio_para_avancar": "Fato canônico suficiente.",
                    "guardrails": ["Não escolher executor."],
                },
                "fontes_lidas": ["indice.yaml", "ponte.yaml"],
            }
        )
        self.assert_contract(result, "direcao.avaliar_destino")
        self.assertEqual(result["ids"], {"direcao": "ponte", "marco": "m1"})
        self.assertEqual(result["gates"][0]["resultado"], "avaliar")
        self.assertEqual(
            result["gates"][0]["criterio_para_avancar"],
            "Fato canônico suficiente.",
        )
        self.assertNotIn("executor", result["ids"])
        self.assertNotIn("executor", result["disponibilidade"])
        self.assertNotIn("executor", result["proximo_passo"])

    def test_sidequest_snapshot_separa_fases(self):
        result = endpoints.project_sidequest(
            {
                "ok": True,
                "sidequest": "sq-1",
                "npc_id": "npc_a",
                "deltas_transacionais": [
                    {
                        "alvo": "relogio:x",
                        "op": "inc",
                        "caminho": "relogio.progresso",
                        "valor": 1,
                    }
                ],
                "vinculos": [{"tipo": "pressao", "id": "x"}],
                "pos_canonico": [
                    {"tipo": "rastro", "especificacao": {"id": "trace-x"}}
                ],
                "fontes_lidas": ["oportunidades.yaml", "relogios.yaml"],
            }
        )
        self.assert_contract(result, "sidequest.preparar_efeitos")
        self.assertEqual(result["ids"]["vinculos"], ["x"])
        self.assertEqual(
            result["deltas_previstos"],
            [
                {
                    "fase": "turno",
                    "delta": {
                        "alvo": "relogio:x",
                        "op": "inc",
                        "caminho": "relogio.progresso",
                        "valor": 1,
                    },
                },
                {
                    "fase": "pos_canonico",
                    "efeito": {"tipo": "rastro", "especificacao": {"id": "trace-x"}},
                },
            ],
        )
        self.assertEqual(result["proximo_passo"]["acao"], "registrar_deltas_no_mesmo_turno")
        self.assertEqual(
            result["proximo_passo"]["depois"],
            "aplicar_pos_canonico_apos_fato_base_canonico",
        )

    def test_mesma_entrada_produz_mesmos_bytes(self):
        raw = {
            "quantidade": 0,
            "pendencias": [],
            "fontes_lidas": ["narrador/mundo/estado.yaml"],
        }
        a = yaml.safe_dump(endpoints.project_pending(raw), allow_unicode=True, sort_keys=False)
        b = yaml.safe_dump(endpoints.project_pending(raw), allow_unicode=True, sort_keys=False)
        self.assertEqual(a.encode("utf-8"), b.encode("utf-8"))

    def test_compactacao_ignora_null_sem_fabricar_string_none(self):
        self.assertEqual(endpoints._compact([None, "a", "", "a", " b "]), ["a", "b"])


class EndpointAdapterTest(unittest.TestCase):
    def test_cena_chama_exatamente_uma_porta_subjacente(self):
        preview = {
            "cena_id": "x",
            "preparacao_id": "p",
            "local": None,
            "npcs_canonicos": [],
            "contexto_tags": [],
            "candidatos_contextuais": [],
            "presencas_contextuais": [],
            "entradas_contextuais": [],
            "operacoes_contextuais": [],
            "direcoes_contextuais": [],
            "encontros": [],
            "fontes_lidas": ["x.yaml"],
        }
        with mock.patch.object(endpoints.cena_mundo, "prepare_scene", return_value=preview) as call:
            result = endpoints.scene(ROOT, scene_id="x")
        call.assert_called_once()
        self.assertEqual(result["endpoint"], "cena.preparar")

    def test_cada_wrapper_limita_se_a_uma_chamada_sem_recalculo(self):
        with mock.patch.object(
            endpoints.fronteira_mundo,
            "query",
            return_value={
                "inicio": {},
                "alvo": {},
                "interromper": False,
                "fronteira": None,
                "fontes_lidas": [],
            },
        ) as boundary_call:
            endpoints.boundary(ROOT, date="14 Eleasis, 1372 DR", hour="22:00")
        boundary_call.assert_called_once()

        with mock.patch.object(
            endpoints.mundo,
            "pending_view",
            return_value={"quantidade": 0, "pendencias": [], "fontes_lidas": []},
        ) as pending_call:
            endpoints.pending(ROOT)
        pending_call.assert_called_once()

        with mock.patch.object(
            endpoints.direcoes_destino,
            "project",
            return_value={
                "direcao_id": "d",
                "permitido": False,
                "executavel": False,
                "motivo": "bloqueada_pelo_arco",
                "fontes_lidas": [],
            },
        ) as direction_call:
            endpoints.direction(ROOT, "d")
        direction_call.assert_called_once()

        with mock.patch.object(
            endpoints.interacoes_mundo,
            "prepare_sidequest_effects",
            return_value={
                "sidequest": "sq",
                "npc_id": "n",
                "deltas_transacionais": [],
                "vinculos": [],
                "pos_canonico": [],
                "fontes_lidas": [],
            },
        ) as sidequest_call:
            endpoints.sidequest(ROOT, "sq", [])
        sidequest_call.assert_called_once()


class EndpointRepositoryContractTest(unittest.TestCase):
    def test_orcamento_congela_custo_e_campos(self):
        data = yaml.safe_load(
            (ROOT / "baseline/endpoints-deterministicos-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(data["schema_endpoints_deterministicos"], 1)
        self.assertEqual(data["limites"]["max_bytes_por_endpoint"], endpoints.MAX_ENDPOINT_BYTES)
        self.assertEqual(data["limites"]["max_itens_lista_generica"], endpoints.MAX_LIST_ITEMS)
        self.assertEqual(data["limites"]["max_chamadas_subjacentes_por_endpoint"], 1)
        self.assertEqual(data["limites"]["max_leituras_adicionais_da_projecao"], 0)
        self.assertEqual(data["limites"]["max_escritas_por_endpoint"], 0)
        self.assertEqual(data["limites"]["max_schedulers_novos"], 0)
        self.assertEqual(
            data["campos_obrigatorios"],
            [
                "ids",
                "filtros",
                "disponibilidade",
                "gates",
                "modificadores",
                "deltas_previstos",
                "proximo_passo",
            ],
        )
        self.assertTrue(data["invariantes"]["cli_unificada_da_task_21_nao_e_implementada_aqui"])
        self.assertTrue(data["meta_rollout"]["proibido_inventar_reducao_sem_rollout"])

    def test_endpoints_reais_de_pendencia_e_direcao_validam(self):
        endpoints.validate_endpoint(endpoints.pending(ROOT))
        result = endpoints.direction(ROOT, "ponte_de_kozakura")
        endpoints.validate_endpoint(result)
        self.assertFalse(result["disponibilidade"]["executavel"])

    def test_parser_expoe_cinco_portas_sem_turno_unificado(self):
        parser = endpoints.build_parser()
        sub = next(
            action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
        )
        self.assertEqual(
            set(sub.choices),
            {"cena", "fronteira", "pendencias", "direcao", "sidequest"},
        )
        self.assertNotIn("turno", sub.choices)

    def test_roteador_quente_usa_endpoints_sem_estourar_orcamento(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        for command in (
            "endpoints.py pendencias",
            "endpoints.py cena",
            "endpoints.py direcao",
            "endpoints.py fronteira",
            "endpoints.py sidequest",
        ):
            self.assertIn(command, text)
        self.assertIn("cena_mundo.py confirmar", text)
        self.assertLessEqual((ROOT / "AGENTS.md").stat().st_size, 13312)


if __name__ == "__main__":
    unittest.main()
