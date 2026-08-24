from __future__ import annotations

import copy
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
import endpoints
import mundo
import oportunidades
import sidequest_gate_v2
import sidequests_canonicas as canonical
import sidequests_canonicas_cena
import transacoes


class CanonicalSecretQuestRepositoryTest(unittest.TestCase):
    def test_repo_real_instala_engine_vazio_sem_inventar_catalogo(self):
        index = oportunidades.load_index(ROOT)
        router = index["sidequests_canonicas"]
        self.assertEqual(router["engine"], canonical.ENGINE_ID)
        self.assertEqual(router["por_npc"], {})
        result = canonical.check(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["quest_givers"], 0)
        self.assertEqual(result["quests_roteadas"], 0)
        self.assertEqual(result["detalhes_expostos"], 0)

    def test_encontro_real_sem_refs_nao_aciona_engine(self):
        now = mundo.parse_instant("15 Eleasis, 1372 DR", "18:00")
        with mock.patch.object(
            sidequests_canonicas_cena.sidequests_canonicas,
            "select_from_refs",
            side_effect=AssertionError("engine não deveria rodar sem refs"),
        ):
            preview = cena_mundo.prepare_scene(
                ROOT,
                scene_id="task32:repo-sem-catalogo",
                npcs=["maerra_thandrel"],
                now=now,
            )
        self.assertNotIn("sidequest_canonica", preview)
        self.assertFalse(
            any("sidequests-canonicas/gates" in item for item in preview["fontes_lidas"])
        )

    def test_endpoint_projeta_pedido_sem_autoaceite(self):
        preview = {
            "cena_id": "task32-endpoint",
            "preparacao_id": "scene-prep-task32",
            "local": None,
            "npcs_canonicos": ["npc_a"],
            "contexto_tags": [],
            "candidatos_contextuais": [],
            "presencas_contextuais": [],
            "entradas_contextuais": [],
            "operacoes_contextuais": [],
            "direcoes_contextuais": [],
            "encontros": [],
            "fontes_lidas": ["narrador/oportunidades/index.yaml"],
            "sidequest_canonica": {
                "id": "qsc-222222222222",
                "npc_id": "npc_a",
                "modo": "nova",
                "oferta": {
                    "id": "qsc-222222222222",
                    "npc_id": "npc_a",
                    "tipo": "investigacao",
                    "titulo": "Título reservado elegível",
                    "objetivo": "Investigar um problema concreto.",
                    "janela": {"tipo": "a_qualquer_momento"},
                    "pode_reabrir": True,
                    "consequencia_sem_ren": "O problema segue outro curso.",
                    "oferta": {
                        "recusa_permitida": True,
                        "premissa": "Há um problema que o NPC pode explicar.",
                        "pedido": "O NPC pede ajuda sem presumir aceite.",
                        "guardrails": ["Ren decide a resposta."],
                    },
                },
            },
        }
        result = endpoints.project_scene(preview)
        self.assertEqual(result["ids"]["sidequest_canonica"], "qsc-222222222222")
        self.assertTrue(
            result["disponibilidade"]["sidequest_canonica"]["recusa_permitida"]
        )
        gate = next(item for item in result["gates"] if item["tipo"] == "sidequest_canonica")
        self.assertEqual(gate["resultado"], "disponivel")
        self.assertIn("não autoaceite", result["proximo_passo"]["sidequest_canonica"])


class CanonicalSecretQuestSyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.now = mundo.parse_instant("15 Eleasis, 1372 DR", "12:00")
        self.q1 = "qsc-111111111111"
        self.q2 = "qsc-222222222222"
        self.q3 = "qsc-333333333333"
        self._write("narrador/oportunidades/index.yaml", self._index())
        self._write("narrador/oportunidades/estado.yaml", self._state())
        self._write(
            "estado/npcs/index.yaml",
            {
                "schema_npcs": 2,
                "npcs": {
                    "npc_a": {
                        "nome": "NPC A",
                        "arquivo": "estado/npcs/npc_a.yaml",
                    }
                },
            },
        )
        self._write_npc(affinity=6, trust=6)
        self._write(
            "personagens/jogador/identidades.yaml",
            {
                "schema_identidades_ren": 1,
                "principal": "ren",
                "identidades": {
                    "ren": {"nome": "Ren Kagehira", "aliases": ["Ren"]},
                    "shinta": {"nome": "Shinta", "aliases": []},
                    "kage": {"nome": "Kage", "aliases": []},
                },
            },
        )
        path = self.repo / "personagens/jogador/conhecimento/teste.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Ren conhece o sinal chamado selo vermelho.\n", encoding="utf-8")
        self._write("estado/mundo-task32.yaml", {"pressao": {"nivel": 2}})
        self._write_gate(
            self.q1,
            detail="narrador/sidequests-canonicas/segredos/qsc-111111111111.yaml",
            conditions={"locais": ["local_b"]},
        )
        self._write_gate(
            self.q2,
            detail="narrador/sidequests-canonicas/segredos/qsc-222222222222.yaml",
            conditions={
                "locais": ["local_a"],
                "janela": {
                    "inicio": {"data": "14 Eleasis, 1372 DR", "hora": "00:00"},
                    "fim": {"data": "20 Eleasis, 1372 DR", "hora": "23:59"},
                },
                "relacao": {"afinidade_min": 6, "confianca_min": 6},
                "conhecimento": [
                    {
                        "arquivo": "personagens/jogador/conhecimento/teste.md",
                        "termo": "selo vermelho",
                        "presente": True,
                    }
                ],
                "mundo": [
                    {
                        "arquivo": "estado/mundo-task32.yaml",
                        "caminho": "pressao.nivel",
                        "operador": "maior_igual",
                        "valor": 2,
                    }
                ],
                "identidade": {"persona_relacional": ["ren"]},
            },
        )
        self._write_detail(self.q2)
        self._write_gate(
            self.q3,
            detail="narrador/sidequests-canonicas/segredos/qsc-333333333333.yaml",
            conditions={
                "locais": ["local_a"],
                "identidade": {
                    "persona_relacional": ["ren"],
                    "suspeitas": [
                        {
                            "observada": "shinta",
                            "possivel": "ren",
                            "min_evidencias": 2,
                        }
                    ],
                    "confirmacoes": [
                        {
                            "observada": "shinta",
                            "identidade": "ren",
                            "presente": False,
                        }
                    ],
                },
            },
        )

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _index(self):
        return {
            "schema_oportunidades": 1,
            "natureza": "reservado",
            "semente": "task32-test",
            "estatuto_operacional": "gate_procedural_retirado_task31",
            "nova_origem_sidequests": "canonica_explicita",
            "gate": {
                "versao": 2,
                "modo": "baralho_sem_reposicao_sha256",
                "estatuto": "legado_congelado_nao_operacional",
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
                "gate_procedural_operacional": False,
                "encontro_nao_gera_nova_sidequest": True,
                "fonte_nova_sidequest": "canonica_explicita",
                "perfis_procedurais_sao_legado": True,
            },
            "sidequests_canonicas": {
                "schema_sidequests_canonicas": 1,
                "engine": canonical.ENGINE_ID,
                "detalhes_somente_apos_gate": True,
                "scheduler": "proibido",
                "rng": "proibido",
                "por_npc": {
                    "npc_a": [
                        {
                            "id": self.q1,
                            "gate": f"narrador/sidequests-canonicas/gates/{self.q1}.yaml",
                            "prioridade": 90,
                        },
                        {
                            "id": self.q2,
                            "gate": f"narrador/sidequests-canonicas/gates/{self.q2}.yaml",
                            "prioridade": 80,
                        },
                        {
                            "id": self.q3,
                            "gate": f"narrador/sidequests-canonicas/gates/{self.q3}.yaml",
                            "prioridade": 70,
                        },
                    ]
                },
            },
            "perfis": {
                "npc_a": {
                    "nome": "NPC A",
                    "estado": "inativo",
                    "arquivo": "narrador/oportunidades/perfis/npc_a.yaml",
                }
            },
        }

    def _state(self):
        return {
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

    def _write_npc(self, *, affinity: int, trust: int, identity_state=None):
        payload = {
            "nome": "NPC A",
            "identidade_relacional": "ren",
            "medidores": {
                "vinculo": affinity,
                "confianca": trust,
                "risco_percebido": 2,
            },
        }
        if identity_state is not None:
            payload["reconhecimento_identidade"] = identity_state
        self._write("estado/npcs/npc_a.yaml", {"npc": payload})

    def _write_gate(self, qid: str, *, detail: str, conditions: dict):
        self._write(
            f"narrador/sidequests-canonicas/gates/{qid}.yaml",
            {
                "schema_gate_sidequest_canonica": 1,
                "natureza": "reservado",
                "id": qid,
                "npc_id": "npc_a",
                "detalhe": detail,
                "condicoes": conditions,
            },
        )

    def _write_detail(self, qid: str):
        self._write(
            f"narrador/sidequests-canonicas/segredos/{qid}.yaml",
            {
                "schema_sidequest_canonica": 1,
                "natureza": "reservado",
                "id": qid,
                "npc_id": "npc_a",
                "tipo": "investigacao",
                "titulo": "Problema reservado",
                "objetivo": "Investigar um fato concreto sem roteiro de solução.",
                "janela": {"tipo": "a_qualquer_momento"},
                "pode_reabrir": True,
                "consequencia_sem_ren": "O problema continua e pode seguir outro curso.",
                "oferta": {
                    "recusa_permitida": True,
                    "premissa": "NPC A tem um problema que pode explicar organicamente.",
                    "pedido": "NPC A pede ajuda, sem presumir que Ren aceitará.",
                    "guardrails": ["Não escrever decisão de Ren."],
                },
                "efeitos": [
                    {
                        "tipo": "consequencia",
                        "valor": {"id": "efeito-task32", "estado": "possivel"},
                    }
                ],
            },
        )

    def _refs(self, *ids: str):
        index = oportunidades.load_index(self.repo)
        mapping = {item["id"]: item for item in canonical.route_for_npc(index, "npc_a")}
        return [mapping[qid] for qid in ids]

    def test_roteador_e_opaco_e_nao_abre_gate(self):
        with mock.patch.object(
            canonical,
            "_load_gate",
            side_effect=AssertionError("route_for_npc não pode abrir gate"),
        ):
            refs = canonical.route_for_npc(
                oportunidades.load_index(self.repo),
                "npc_a",
            )
        self.assertEqual([item["id"] for item in refs], [self.q1, self.q2, self.q3])
        self.assertEqual(set(refs[0]), {"id", "gate", "prioridade", "npc_id"})

    def test_gate_bloqueado_nao_abre_detalhe_e_proximo_elegivel_abre_um(self):
        # q1 aponta para local_b e seu detalhe nem existe. Se houver leitura
        # antecipada, o teste falha antes de chegar a q2.
        result = canonical.select_from_refs(
            self.repo,
            self._refs(self.q1, self.q2),
            local_id="local_a",
            now=self.now,
        )
        self.assertEqual(result["resultado"], "sidequest_canonica_disponivel")
        self.assertEqual(result["sidequest"]["id"], self.q2)
        self.assertEqual(result["detalhes_lidos"], 1)
        self.assertNotIn(
            f"narrador/sidequests-canonicas/segredos/{self.q1}.yaml",
            result["fontes_lidas"],
        )

    def test_relacao_pendente_pode_abrir_gate_antes_do_checkpoint(self):
        self._write_npc(affinity=5, trust=6)
        blocked = canonical.select_from_refs(
            self.repo,
            self._refs(self.q2),
            local_id="local_a",
            now=self.now,
            diagnostics=True,
        )
        self.assertEqual(blocked["resultado"], "nenhuma_sidequest_canonica")
        self.assertEqual(blocked["diagnostico"][0]["bloqueio"], "relacao")

        pending = [
            {
                "versao": 1,
                "id": "txn-task32-relacao",
                "sessao": 1,
                "resumo": "Afinidade aumentou por um fato canônico concreto.",
                "deltas": [
                    {
                        "alvo": "npc:npc_a",
                        "op": "inc",
                        "caminho": "medidores.vinculo",
                        "valor": 1,
                    }
                ],
            }
        ]
        with mock.patch.object(transacoes, "load_pending", return_value=pending):
            eligible = canonical.select_from_refs(
                self.repo,
                self._refs(self.q2),
                local_id="local_a",
                now=self.now,
            )
        self.assertEqual(eligible["sidequest"]["id"], self.q2)

    def test_suspeita_e_confirmacao_sao_gates_distintos(self):
        blocked = canonical.select_from_refs(
            self.repo,
            self._refs(self.q3),
            local_id="local_a",
            now=self.now,
            diagnostics=True,
        )
        self.assertEqual(blocked["diagnostico"][0]["bloqueio"], "identidade")
        self.assertEqual(blocked["detalhes_lidos"], 0)

        identity_state = {
            "schema_reconhecimento_identidade": 1,
            "suspeitas": [
                {
                    "observada": "shinta",
                    "possivel": "ren",
                    "evidencias": [
                        {"id": "ids-1111111111111111", "tipo": "fisica", "fonte": "sessao:1"},
                        {"id": "ids-2222222222222222", "tipo": "contextual", "fonte": "sessao:2"},
                    ],
                }
            ],
            "confirmacoes": [],
        }
        self._write_npc(affinity=6, trust=6, identity_state=identity_state)
        self._write_detail(self.q3)
        eligible = canonical.select_from_refs(
            self.repo,
            self._refs(self.q3),
            local_id="local_a",
            now=self.now,
        )
        self.assertEqual(eligible["sidequest"]["id"], self.q3)

    def test_oferta_e_idempotente_sem_cooldown_e_recusa_pode_reabrir(self):
        first = canonical.offer(
            self.repo,
            self.q2,
            npc_id="npc_a",
            local="local_a",
            now=self.now,
        )
        mid = first["missao"]["id"]
        self.assertEqual(first["resultado"], "oferecida")
        self.assertTrue(first["recusa_permitida"])
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        self.assertIsNone(state["cooldown_ate"])
        self.assertEqual(state["missoes"][mid]["origem"], "sidequest_canonica")

        retry = canonical.offer(
            self.repo,
            self.q2,
            npc_id="npc_a",
            local="local_a",
            now=self.now,
        )
        self.assertEqual(retry["resultado"], "ja_registrada")

        oportunidades.respond(self.repo, mid, "recusar", now=self.now)
        reopened = canonical.offer(
            self.repo,
            self.q2,
            npc_id="npc_a",
            local="local_a",
            now=self.now,
        )
        self.assertEqual(reopened["resultado"], "oferecida")
        self.assertTrue(reopened["reabertura"])
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        self.assertIsNone(state["cooldown_ate"])

    def test_efeitos_so_abrem_depois_do_aceite(self):
        offered = canonical.offer(
            self.repo,
            self.q2,
            npc_id="npc_a",
            local="local_a",
            now=self.now,
        )
        mid = offered["missao"]["id"]
        with self.assertRaises(canonical.CanonicalSidequestError):
            canonical.effects_for_mission(self.repo, mid)
        oportunidades.respond(self.repo, mid, "aceitar", now=self.now)
        effects = canonical.effects_for_mission(self.repo, mid)
        self.assertEqual(effects["sidequest"], mid)
        self.assertEqual(len(effects["efeitos"]), 1)

    def test_orcamento_de_duas_ativas_bloqueia_antes_do_detalhe(self):
        state = self._state()
        state["missoes"] = {
            "a": {"id": "a", "estado": "aceita", "npc_id": "x", "necessidade_id": "x"},
            "b": {"id": "b", "estado": "aceita", "npc_id": "y", "necessidade_id": "y"},
        }
        self._write("narrador/oportunidades/estado.yaml", state)
        (self.repo / f"narrador/sidequests-canonicas/segredos/{self.q2}.yaml").unlink()
        result = canonical.select_from_refs(
            self.repo,
            self._refs(self.q2),
            local_id="local_a",
            now=self.now,
            diagnostics=True,
        )
        self.assertEqual(result["resultado"], "nenhuma_sidequest_canonica")
        self.assertEqual(result["diagnostico"][0]["bloqueio"], "limite_ativas")
        self.assertEqual(result["detalhes_lidos"], 0)

    def test_adapter_task31_so_transporta_refs_opacas(self):
        result = sidequest_gate_v2.encounter_event(
            self.repo,
            "npc_a",
            encounter_id="task32:npc-a",
            now=self.now,
        )
        self.assertEqual(result["motivo"], "gate_procedural_retirado")
        refs = result["_sidequest_canonica_refs"]
        self.assertEqual([item["id"] for item in refs], [self.q1, self.q2, self.q3])
        self.assertNotIn("narrador/oportunidades/estado.yaml", result["fontes_lidas"])


class CanonicalSecretQuestBudgetTest(unittest.TestCase):
    def test_contrato_congela_lazy_loading_e_zero_infra(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/canonical-secret-quest-engine-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        limits = contract["limites"]
        self.assertEqual(limits["refs_opacas_por_npc"], canonical.MAX_REFS_PER_NPC)
        self.assertEqual(limits["gates_por_cena"], canonical.MAX_GATE_FRAGMENTS_PER_SCENE)
        self.assertEqual(limits["detalhes_secretos_por_cena"], canonical.MAX_DETAIL_FRAGMENTS_PER_SCENE)
        self.assertEqual(limits["bytes_por_detalhe"], canonical.MAX_DETAIL_BYTES)
        for field in (
            "leituras_task32_sem_refs_roteadas",
            "escritas_avaliar",
            "escritas_preparar_cena",
            "schedulers_novos",
            "rng_novo",
            "scans_globais",
            "estados_persistentes_novos",
        ):
            self.assertEqual(limits[field], 0)
        self.assertTrue(all(contract["invariantes"].values()))

    def test_engine_nao_importa_rng_scheduler_ou_scan_global(self):
        source = (ROOT / "ferramentas/sidequests_canonicas.py").read_text(encoding="utf-8")
        for forbidden in ("import random", "threading", "asyncio", ".rglob(", ".glob("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
