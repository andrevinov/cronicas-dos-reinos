from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import eventos_mundo
import mundo


class EventosRepoTest(unittest.TestCase):
    def test_repo_real_valida_dez_cartas_e_roteador(self):
        result = eventos_mundo.validate_repo(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["quantidade_cartas"], 10)
        router = eventos_mundo.load_interactions(ROOT)
        self.assertEqual(router["orcamento"]["max_estrategicos_por_evento"], 2)
        self.assertEqual(router["orcamento"]["max_leves_por_evento"], 1)

    def test_estado_inicial_sem_retroatividade(self):
        result = eventos_mundo.status(ROOT)
        self.assertEqual(result["processado_ate"]["data"], "10 Eleasis, 1372 DR")
        self.assertEqual(result["ocorrencia"]["ciclo"], 0)
        self.assertEqual(result["eventos"]["ciclo"], 0)
        self.assertEqual(result["historico_recente"], [])

    def test_urna_real_e_sete_por_tres(self):
        index = eventos_mundo.load_index(ROOT)
        results = [item["resultado"] for item in index["ocorrencia"]["fichas"]]
        self.assertEqual(results.count("rotina"), 7)
        self.assertEqual(results.count("evento"), 3)

    def test_consulta_e_fragmentada(self):
        result = eventos_mundo.show(ROOT, "Acidente no porto")
        self.assertEqual(result["evento_id"], "acidente_no_porto")
        self.assertEqual(
            result["fontes_lidas"],
            [
                "narrador/eventos/index.yaml",
                "narrador/eventos/cartas/acidente_no_porto.yaml",
            ],
        )

    def test_inspecao_portuaria_acorda_so_candidatos_baratos(self):
        index = eventos_mundo.load_index(ROOT)
        context = eventos_mundo.routing_context(ROOT)
        routed = eventos_mundo.route_agents(
            index["cartas"]["inspecao_portuaria_reforcada"]["tags"],
            context,
        )
        self.assertEqual(routed["estrategicos"], ["red_sail", "night_watch"])
        self.assertEqual(routed["leves"], ["luath"])
        self.assertEqual(
            context["fontes_lidas"],
            [
                "narrador/eventos/interacoes.yaml",
                "narrador/agentes/index.yaml",
                "narrador/agentes-leves/index.yaml",
            ],
        )

    def test_doenca_leve_prioriza_maerra_sem_agente_estrategico(self):
        index = eventos_mundo.load_index(ROOT)
        routed = eventos_mundo.route_agents(
            index["cartas"]["surto_de_doenca_leve"]["tags"],
            eventos_mundo.routing_context(ROOT),
        )
        self.assertEqual(routed["estrategicos"], [])
        self.assertEqual(routed["leves"], ["maerra_thandrel"])


class EventosSinteticosTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.y(
            "narrador/eventos/index.yaml",
            {
                "schema_eventos_mundo": 1,
                "natureza": "reservado",
                "semente": "seed",
                "inicio": {"data": "11 Eleasis, 1372 DR", "hora": "06:00"},
                "ocorrencia": {
                    "fichas": [
                        {"id": "r", "resultado": "rotina"},
                        {"id": "e", "resultado": "evento"},
                    ]
                },
                "cartas": {
                    "a": {
                        "nome": "Carta A",
                        "categoria": "teste",
                        "escala": "bairro",
                        "tags": ["porto", "comercio"],
                        "arquivo": "narrador/eventos/cartas/a.yaml",
                    },
                    "b": {
                        "nome": "Carta B",
                        "categoria": "teste",
                        "escala": "cidade",
                        "tags": ["saude"],
                        "arquivo": "narrador/eventos/cartas/b.yaml",
                    },
                },
            },
        )
        self.y(
            "narrador/eventos/cartas/a.yaml",
            {
                "schema_evento_mundo": 1,
                "natureza": "reservado",
                "estatuto": "molde_nao_canonico_ate_resolucao",
                "id": "a",
                "nome": "Carta A",
                "categoria": "teste",
                "escala": "bairro",
                "premissa": "Algo pode acontecer.",
                "pergunta_de_resolucao": "O que realmente acontece?",
                "guardrails": ["Não canonizar automaticamente."],
                "tags": ["porto", "comercio"],
            },
        )
        self.y(
            "narrador/eventos/cartas/b.yaml",
            {
                "schema_evento_mundo": 1,
                "natureza": "reservado",
                "estatuto": "molde_nao_canonico_ate_resolucao",
                "id": "b",
                "nome": "Carta B",
                "categoria": "teste",
                "escala": "cidade",
                "premissa": "Algo pode acontecer.",
                "pergunta_de_resolucao": "O que realmente acontece?",
                "guardrails": ["Não canonizar automaticamente."],
                "tags": ["saude"],
            },
        )
        self.y(
            "narrador/eventos/interacoes.yaml",
            {
                "schema_interacoes_eventos": 1,
                "natureza": "roteador_reservado",
                "orcamento": {
                    "max_estrategicos_por_evento": 2,
                    "max_leves_por_evento": 1,
                    "ordenacao": "coincidencias_prioridade_id",
                },
                "estrategicos": {
                    "s1": {"prioridade": 3, "tags": ["porto"]},
                    "s2": {"prioridade": 2, "tags": ["porto", "comercio"]},
                    "s3": {"prioridade": 5, "tags": ["porto"]},
                    "s_inativo": {"prioridade": 99, "tags": ["porto", "comercio"]},
                },
                "leves": {
                    "l1": {"prioridade": 3, "tags": ["porto"]},
                    "l2": {"prioridade": 2, "tags": ["saude"]},
                    "l_inativo": {"prioridade": 99, "tags": ["porto", "comercio"]},
                },
            },
        )
        strategic_meta = {
            "tipo": "instituicao",
            "estado": "ativo",
            "presenca": "ancorada",
            "atuacao_local": "estrutura_local",
            "arquivo": "unused.yaml",
            "nome": "unused",
        }
        self.y(
            "narrador/agentes/index.yaml",
            {
                "schema_agentes": 2,
                "natureza": "reservado",
                "agentes": {
                    "s1": {**strategic_meta, "nome": "S1"},
                    "s2": {**strategic_meta, "nome": "S2"},
                    "s3": {
                        **strategic_meta,
                        "nome": "S3",
                        "tipo": "npc",
                        "presenca": "presente",
                        "atuacao_local": "exige_presenca_fisica",
                    },
                    "s_inativo": {
                        **strategic_meta,
                        "nome": "Off",
                        "estado": "inativo",
                    },
                },
            },
        )
        self.y(
            "narrador/agentes-leves/index.yaml",
            {
                "schema_agentes_leves": 1,
                "natureza": "reservado",
                "agentes": {
                    "l1": {"estado": "ativo"},
                    "l2": {"estado": "ativo"},
                    "l_inativo": {"estado": "inativo"},
                },
            },
        )
        self.y(
            "narrador/eventos/estado.yaml",
            {
                "schema_estado_eventos_mundo": 1,
                "natureza": "controle_reservado",
                "processado_ate": {"data": "10 Eleasis, 1372 DR", "hora": "06:00"},
                "ocorrencia": {"ciclo": 0, "restantes": []},
                "eventos": {"ciclo": 0, "restantes": []},
                "historico_recente": [],
            },
        )
        self.y(
            "narrador/mundo/agenda.yaml",
            {
                "schema_agenda_mundo": 1,
                "natureza": "reservado",
                "hora_amanhecer": "06:00",
                "reavaliacoes": {},
                "agendamentos": [],
            },
        )
        self.y(
            "narrador/mundo/estado.yaml",
            {
                "schema_estado_mundo": 1,
                "natureza": "controle_reservado",
                "processado_ate": {"data": "10 Eleasis, 1372 DR", "hora": "17:42"},
                "pendencias": [],
                "concluidas_recentes": [],
            },
        )
        self.tempo("10 Eleasis, 1372 DR", "17:42 de 10 Eleasis")

    def tearDown(self):
        self.temp.cleanup()

    def y(self, rel, value):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def read(self, rel):
        return yaml.safe_load((self.repo / rel).read_text(encoding="utf-8"))

    def tempo(self, data, hora):
        self.y(
            "estado/tempo.yaml",
            {
                "schema_tempo": 1,
                "natureza": "tempo_atual",
                "data_atual": data,
                "hora_aproximada": hora,
            },
        )

    def force_event_a(self):
        state = self.read("narrador/eventos/estado.yaml")
        state["ocorrencia"] = {"ciclo": 1, "restantes": ["e", "r"]}
        state["eventos"] = {"ciclo": 1, "restantes": ["a", "b"]}
        self.y("narrador/eventos/estado.yaml", state)
        self.tempo("11 Eleasis, 1372 DR", "06:01 de 11 Eleasis")

    def test_ordem_e_reprodutivel(self):
        first = eventos_mundo.deck_order("x", "eventos", 1, ["a", "b", "c", "d"])
        second = eventos_mundo.deck_order("x", "eventos", 1, ["a", "b", "c", "d"])
        self.assertEqual(first, second)
        self.assertEqual(sorted(first), ["a", "b", "c", "d"])

    def test_rotina_nao_le_roteador_nem_indices_de_agentes(self):
        state = self.read("narrador/eventos/estado.yaml")
        state["ocorrencia"] = {"ciclo": 1, "restantes": ["r", "e"]}
        self.y("narrador/eventos/estado.yaml", state)
        self.tempo("11 Eleasis, 1372 DR", "06:01 de 11 Eleasis")
        result = eventos_mundo.process_checkpoint(self.repo)
        self.assertEqual(result["dias_rotina"], 1)
        self.assertEqual(result["novas_pendencias"], [])
        self.assertNotIn("narrador/eventos/interacoes.yaml", result["fontes_lidas"])
        self.assertNotIn("narrador/agentes/index.yaml", result["fontes_lidas"])
        self.assertNotIn("narrador/agentes-leves/index.yaml", result["fontes_lidas"])

    def test_evento_cria_uma_pendencia_com_orcamento_sem_abrir_fragmentos(self):
        self.force_event_a()
        result = eventos_mundo.process_checkpoint(self.repo)
        self.assertEqual(result["eventos_reconsiderar"], ["a"])
        self.assertNotIn("narrador/eventos/cartas/a.yaml", result["fontes_lidas"])
        self.assertIn("narrador/eventos/interacoes.yaml", result["fontes_lidas"])
        pending = self.read("narrador/mundo/estado.yaml")["pendencias"]
        self.assertEqual(len(pending), 1)
        item = pending[0]
        self.assertEqual(item["tipo"], "evento_mundial")
        self.assertEqual(item["agentes_afetados"], ["s2", "s3"])
        self.assertEqual(item["agentes_leves_afetados"], ["l1"])
        self.assertEqual(result["agentes_evento_reconsiderar"], ["s2", "s3"])
        self.assertEqual(result["agentes_leves_evento_reconsiderar"], ["l1"])

    def test_inativos_nao_entram_mesmo_com_prioridade_alta(self):
        routed = eventos_mundo.route_agents(
            ["porto", "comercio"],
            eventos_mundo.routing_context(self.repo),
        )
        self.assertNotIn("s_inativo", routed["estrategicos"])
        self.assertNotIn("l_inativo", routed["leves"])

    def test_sem_repeticao_antes_de_esgotar(self):
        index = self.read("narrador/eventos/index.yaml")
        index["ocorrencia"]["fichas"] = [
            {"id": "e1", "resultado": "evento"},
            {"id": "e2", "resultado": "evento"},
            {"id": "r", "resultado": "rotina"},
        ]
        self.y("narrador/eventos/index.yaml", index)
        state = self.read("narrador/eventos/estado.yaml")
        state["ocorrencia"] = {"ciclo": 1, "restantes": ["e1", "e2", "r"]}
        state["eventos"] = {"ciclo": 1, "restantes": ["a", "b"]}
        self.y("narrador/eventos/estado.yaml", state)
        self.tempo("12 Eleasis, 1372 DR", "06:01 de 12 Eleasis")
        result = eventos_mundo.process_checkpoint(self.repo)
        self.assertEqual(result["eventos_sorteados"], ["a", "b"])
        self.assertEqual(len(set(result["eventos_sorteados"])), 2)

    def test_retry_repara_sem_duplicar_e_preserva_roteamento(self):
        self.force_event_a()
        dawn = mundo.parse_instant("11 Eleasis, 1372 DR", "06:00")
        world = self.read("narrador/mundo/estado.yaml")
        world["pendencias"] = [
            {
                "id": eventos_mundo.pending_id("a", dawn),
                "tipo": "evento_mundial",
                "evento": "a",
                "categoria": "teste",
                "escala": "bairro",
                "agentes_afetados": ["s2", "s3"],
                "agentes_leves_afetados": ["l1"],
                "disparado_em": mundo.instant_parts(dawn),
                "motivo": "já gravado",
                "origem": "eventos:a",
            }
        ]
        self.y("narrador/mundo/estado.yaml", world)
        result = eventos_mundo.process_checkpoint(self.repo)
        self.assertEqual(result["novas_pendencias"], [])
        self.assertEqual(len(self.read("narrador/mundo/estado.yaml")["pendencias"]), 1)
        self.assertEqual(
            self.read("narrador/eventos/estado.yaml")["eventos"]["restantes"],
            ["b"],
        )

    def test_morto_e_removido_de_evento_pendente_sem_cancelar_evento(self):
        dawn = mundo.parse_instant("11 Eleasis, 1372 DR", "06:00")
        world = self.read("narrador/mundo/estado.yaml")
        world["pendencias"] = [
            {
                "id": eventos_mundo.pending_id("a", dawn),
                "tipo": "evento_mundial",
                "evento": "a",
                "categoria": "teste",
                "escala": "bairro",
                "agentes_afetados": ["s2", "s3"],
                "agentes_leves_afetados": ["l1"],
                "disparado_em": mundo.instant_parts(dawn),
                "motivo": "teste",
                "origem": "eventos:a",
            }
        ]
        self.y("narrador/mundo/estado.yaml", world)
        result = eventos_mundo.prune_dead_candidates(self.repo, {"s3", "l1"})
        self.assertTrue(result["alterou"])
        pending = self.read("narrador/mundo/estado.yaml")["pendencias"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["agentes_afetados"], ["s2"])
        self.assertEqual(pending[0]["agentes_leves_afetados"], [])

    def test_tags_do_indice_e_fragmento_nao_podem_divergir(self):
        data = self.read("narrador/eventos/cartas/a.yaml")
        data["tags"] = ["outra"]
        self.y("narrador/eventos/cartas/a.yaml", data)
        result = eventos_mundo.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertTrue(any("tags" in error for error in result["erros"]))

    def test_roteador_rejeita_agente_inexistente(self):
        router = self.read("narrador/eventos/interacoes.yaml")
        router["estrategicos"]["fantasma"] = {"prioridade": 1, "tags": ["porto"]}
        self.y("narrador/eventos/interacoes.yaml", router)
        result = eventos_mundo.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertTrue(any("inexistente" in error for error in result["erros"]))

    def test_fragmento_canonico_e_rejeitado(self):
        data = self.read("narrador/eventos/cartas/a.yaml")
        data["estatuto"] = "canonico"
        self.y("narrador/eventos/cartas/a.yaml", data)
        result = eventos_mundo.validate_repo(self.repo)
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
