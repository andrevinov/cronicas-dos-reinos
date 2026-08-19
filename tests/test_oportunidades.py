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

import mundo
import oportunidades


class OportunidadesRepoTest(unittest.TestCase):
    def test_repo_real_valida_perfis_e_orcamento(self):
        result = oportunidades.validate_repo(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["perfis"], 12)

        index = oportunidades.load_index(ROOT)
        self.assertEqual(index["orcamento"]["max_ativas"], 2)
        self.assertEqual(index["orcamento"]["max_em_aberto"], 3)
        self.assertEqual(index["orcamento"]["max_pendencias_avaliacao"], 1)
        self.assertEqual(index["orcamento"]["cooldown_oferta_dias"], [2, 3])

    def test_gate_real_e_oito_por_dois_sem_scheduler(self):
        index = oportunidades.load_index(ROOT)
        results = [item["resultado"] for item in index["gate"]["fichas"]]
        self.assertEqual(results.count("nada"), 8)
        self.assertEqual(results.count("oportunidade"), 2)
        self.assertEqual(index["regras"]["acionamento"], "encontro_com_npc")
        self.assertEqual(index["regras"]["scheduler"], "proibido")
        self.assertEqual(index["regras"]["scan_geral_npcs"], "proibido")

    def test_indice_e_compacto(self):
        self.assertLessEqual(
            (ROOT / "narrador/oportunidades/index.yaml").stat().st_size,
            4096,
        )


class OportunidadesSinteticasTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.now = mundo.parse_instant("10 Eleasis, 1372 DR", "12:00")

        self.index = {
            "schema_oportunidades": 1,
            "natureza": "reservado",
            "semente": "seed-sidequest",
            "gate": {
                "modo": "baralho_sem_reposicao_sha256",
                "fichas": [
                    *[
                        {"id": f"nada_{i:02d}", "resultado": "nada"}
                        for i in range(1, 9)
                    ],
                    {"id": "op_01", "resultado": "oportunidade"},
                    {"id": "op_02", "resultado": "oportunidade"},
                ],
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
            },
            "perfis": {
                "npc_a": {
                    "nome": "NPC A",
                    "estado": "ativo",
                    "arquivo": "narrador/oportunidades/perfis/npc_a.yaml",
                },
                "npc_b": {
                    "nome": "NPC B",
                    "estado": "ativo",
                    "arquivo": "narrador/oportunidades/perfis/npc_b.yaml",
                },
                "npc_c": {
                    "nome": "NPC C",
                    "estado": "ativo",
                    "arquivo": "narrador/oportunidades/perfis/npc_c.yaml",
                },
            },
        }
        self.state = {
            "schema_estado_oportunidades": 1,
            "natureza": "controle_reservado",
            "gate": {"ciclo": 0, "restantes": [], "sorteios": 0},
            "cooldown_ate": None,
            "pendencias_avaliacao": {},
            "missoes": {},
            "sementes_consumidas": [],
            "encontros_recentes": [],
            "historico_recente": [],
        }
        self.profile_a = self.profile(
            "npc_a",
            [
                self.need(
                    "a_temporal",
                    "investigacao",
                    {"tipo": "temporal", "duracao_horas": 24},
                    False,
                ),
                self.need(
                    "a_reabre",
                    "favor",
                    {"tipo": "a_qualquer_momento"},
                    True,
                ),
            ],
        )
        self.profile_b = self.profile(
            "npc_b",
            [
                self.need(
                    "b_um",
                    "entrega",
                    {"tipo": "a_qualquer_momento"},
                    False,
                ),
            ],
        )
        self.profile_c = self.profile(
            "npc_c",
            [
                self.need(
                    "c_um",
                    "protecao",
                    {"tipo": "enquanto_condicao", "condicao": "risco continuar"},
                    False,
                ),
            ],
        )

        self.y("narrador/oportunidades/index.yaml", self.index)
        self.y("narrador/oportunidades/estado.yaml", self.state)
        self.y("narrador/oportunidades/perfis/npc_a.yaml", self.profile_a)
        self.y("narrador/oportunidades/perfis/npc_b.yaml", self.profile_b)
        self.y("narrador/oportunidades/perfis/npc_c.yaml", self.profile_c)
        self.y(
            "estado/relacoes/index.yaml",
            {
                "schema_relacoes": 2,
                "relacoes": {
                    npc: {"arquivo": f"estado/relacoes/{npc}.yaml"}
                    for npc in ("npc_a", "npc_b", "npc_c")
                },
            },
        )
        for npc in ("npc_a", "npc_b", "npc_c"):
            self.y(f"estado/relacoes/{npc}.yaml", {"id": npc})

    def tearDown(self):
        self.temp.cleanup()

    def y(self, rel, value):
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

    def profile(self, npc_id, needs):
        return {
            "schema_perfil_oportunidades": 1,
            "natureza": "reservado",
            "estatuto": "sementes_nao_canonicas_ate_resolucao",
            "npc_id": npc_id,
            "nome": npc_id,
            "fonte_npc": f"estado/relacoes/{npc_id}.yaml",
            "necessidades": needs,
        }

    def need(self, need_id, kind, window, reopen):
        return {
            "id": need_id,
            "tipo": kind,
            "semente": f"semente {need_id}",
            "janela": window,
            "pode_reabrir": reopen,
            "consequencia_sem_ren": f"consequência possível {need_id}",
        }

    def force_gate(self, result):
        state = self.read_state()
        token = "op_01" if result == "oportunidade" else "nada_01"
        state["gate"] = {"ciclo": 1, "restantes": [token], "sorteios": 0}
        self.y("narrador/oportunidades/estado.yaml", state)

    def test_baralho_sem_reposicao_e_deterministico(self):
        index = oportunidades.load_index(self.repo)
        first = oportunidades.load_state(self.repo, index)
        second = oportunidades.load_state(self.repo, index)

        draws_a = [oportunidades.draw_gate(first, index) for _ in range(10)]
        draws_b = [oportunidades.draw_gate(second, index) for _ in range(10)]

        self.assertEqual(draws_a, draws_b)
        self.assertEqual(len({token for token, _ in draws_a}), 10)
        results = [result for _, result in draws_a]
        self.assertEqual(results.count("nada"), 8)
        self.assertEqual(results.count("oportunidade"), 2)

    def test_oportunidade_cria_potencial_nao_oferta(self):
        self.force_gate("oportunidade")
        result = oportunidades.encounter(self.repo, "npc_a", now=self.now)

        self.assertEqual(result["resultado"], "avaliar_sidequest")
        self.assertEqual(result["pendencia"]["estado"], "potencial")
        state = self.read_state()
        self.assertEqual(state["missoes"], {})
        self.assertEqual(len(state["pendencias_avaliacao"]), 1)
        self.assertEqual(
            result["fontes_lidas"],
            [
                "narrador/oportunidades/index.yaml",
                "narrador/oportunidades/estado.yaml",
                "narrador/oportunidades/perfis/npc_a.yaml",
            ],
        )

    def test_pendencia_global_bloqueia_sem_abrir_outro_perfil(self):
        self.force_gate("oportunidade")
        first = oportunidades.encounter(self.repo, "npc_a", now=self.now)
        self.assertEqual(first["resultado"], "avaliar_sidequest")

        second = oportunidades.encounter(self.repo, "npc_b", now=self.now)
        self.assertEqual(second["resultado"], "interacao_normal")
        self.assertEqual(
            second["motivo"],
            "ja_existe_pendencia_global_de_avaliacao",
        )
        self.assertEqual(
            second["fontes_lidas"],
            [
                "narrador/oportunidades/index.yaml",
                "narrador/oportunidades/estado.yaml",
            ],
        )

    def test_oferta_inicia_cooldown_global_de_dois_ou_tres_dias(self):
        self.force_gate("oportunidade")
        pending = oportunidades.encounter(self.repo, "npc_a", now=self.now)["pendencia"]
        offered = oportunidades.evaluate(
            self.repo,
            pending["id"],
            "oferecer",
            reason="faz sentido canônico",
            now=self.now,
        )
        self.assertEqual(offered["resultado"], "oferecida")

        cooldown = oportunidades._parse_parts(offered["cooldown_ate"], "cooldown")
        delta_days = (cooldown.minute - self.now.minute) // 1440
        self.assertIn(delta_days, {2, 3})

        blocked = oportunidades.encounter(self.repo, "npc_b", now=self.now)
        self.assertEqual(blocked["motivo"], "cooldown_global_de_oferta")
        self.assertEqual(
            blocked["fontes_lidas"],
            [
                "narrador/oportunidades/index.yaml",
                "narrador/oportunidades/estado.yaml",
            ],
        )

    def test_descartar_semente_impede_repeticao(self):
        self.force_gate("oportunidade")
        first = oportunidades.encounter(
            self.repo,
            "npc_a",
            now=self.now,
            encounter_id="encontro-1",
        )["pendencia"]
        first_need = first["necessidade_id"]
        oportunidades.evaluate(
            self.repo,
            first["id"],
            "descartar",
            reason="não combina com a cena",
            now=self.now,
        )

        self.force_gate("oportunidade")
        second = oportunidades.encounter(
            self.repo,
            "npc_a",
            now=self.now,
            encounter_id="encontro-2",
        )["pendencia"]
        self.assertNotEqual(second["necessidade_id"], first_need)

    def test_limite_de_ativas_bloqueia_gate_sem_abrir_perfil(self):
        state = self.read_state()
        for n, npc in enumerate(("npc_a", "npc_b"), start=1):
            state["missoes"][f"m{n}"] = {
                "id": f"m{n}",
                "estado": "aceita",
                "npc_id": npc,
                "necessidade_id": f"x{n}",
                "janela": {"tipo": "a_qualquer_momento"},
            }
        self.y("narrador/oportunidades/estado.yaml", state)

        result = oportunidades.encounter(self.repo, "npc_c", now=self.now)
        self.assertEqual(result["motivo"], "limite_de_sidequests_ativas")
        self.assertEqual(
            result["fontes_lidas"],
            [
                "narrador/oportunidades/index.yaml",
                "narrador/oportunidades/estado.yaml",
            ],
        )

    def test_mesmo_encontro_nao_sorteia_duas_vezes(self):
        self.force_gate("nada")
        first = oportunidades.encounter(
            self.repo,
            "npc_a",
            now=self.now,
            encounter_id="sessao-1:cena-2:npc-a",
        )
        self.assertEqual(first["motivo"], "gate_sem_oportunidade")
        self.assertEqual(self.read_state()["gate"]["sorteios"], 1)

        second = oportunidades.encounter(
            self.repo,
            "npc_a",
            now=self.now,
            encounter_id="sessao-1:cena-2:npc-a",
        )
        self.assertEqual(second["motivo"], "encontro_ja_processado")
        self.assertEqual(self.read_state()["gate"]["sorteios"], 1)
        self.assertEqual(
            second["fontes_lidas"],
            [
                "narrador/oportunidades/index.yaml",
                "narrador/oportunidades/estado.yaml",
            ],
        )

    def test_temporal_aceita_falha_reativamente_sem_scheduler(self):
        state = self.read_state()
        state["sementes_consumidas"].append("npc_a:a_reabre")
        state["gate"] = {"ciclo": 1, "restantes": ["op_01"], "sorteios": 0}
        self.y("narrador/oportunidades/estado.yaml", state)

        pending = oportunidades.encounter(self.repo, "npc_a", now=self.now)["pendencia"]
        self.assertEqual(pending["janela"]["tipo"], "temporal")
        oportunidades.evaluate(
            self.repo,
            pending["id"],
            "oferecer",
            reason="oferta válida",
            now=self.now,
        )
        oportunidades.respond(
            self.repo,
            pending["id"],
            "aceitar",
            now=self.now,
        )

        later = mundo.WorldInstant(self.now.minute + 25 * 60)
        status = oportunidades.status(self.repo, now=later)
        self.assertEqual(status["missoes_por_estado"]["falhada"], 1)

    def test_recusa_fica_registrada_e_pode_reabrir_sem_duplicar(self):
        state = self.read_state()
        state["sementes_consumidas"].append("npc_a:a_temporal")
        state["gate"] = {"ciclo": 1, "restantes": ["op_01"], "sorteios": 0}
        self.y("narrador/oportunidades/estado.yaml", state)

        pending = oportunidades.encounter(self.repo, "npc_a", now=self.now)["pendencia"]
        oportunidades.evaluate(
            self.repo,
            pending["id"],
            "oferecer",
            reason="faz sentido",
            now=self.now,
        )
        oportunidades.respond(
            self.repo,
            pending["id"],
            "recusar",
            now=self.now,
        )
        refused = self.read_state()["missoes"][pending["id"]]
        self.assertEqual(refused["estado"], "recusada")

        later = mundo.WorldInstant(self.now.minute + 4 * 1440)
        reopened = oportunidades.reopen(
            self.repo,
            pending["id"],
            reason="circunstâncias mudaram",
            now=later,
        )
        self.assertEqual(reopened["resultado"], "oferecida")
        self.assertEqual(len(self.read_state()["missoes"]), 1)


if __name__ == "__main__":
    unittest.main()
