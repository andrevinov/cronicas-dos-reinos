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

import interacoes_mundo
import checkpoint
import mundo
import oportunidades
import recompensas

SNAPSHOT = ROOT / "tests/fixtures/mundo-vivo/integracao-v1.yaml"
BUDGET = ROOT / "baseline/mundo-vivo-integracao-orcamento.yaml"


class IntegrationRepositoryTest(unittest.TestCase):
    def test_repo_real_fecha_integracao(self):
        result = interacoes_mundo.check_repo(ROOT)
        self.assertTrue(result["ok"], result["erros"])

    def test_snapshot_de_integracao_reflete_contratos_reais(self):
        snap = yaml.safe_load(SNAPSHOT.read_text(encoding="utf-8"))
        self.assertEqual(snap["schema_snapshot_integracao_mundo_vivo"], 1)

        opp = oportunidades.load_index(ROOT)
        rewards = recompensas.load_index(ROOT)
        outcomes = [item["resultado"] for item in opp["gate"]["fichas"]]
        self.assertEqual(outcomes.count("nada"), snap["sidequests"]["gate"]["nada"])
        self.assertEqual(
            outcomes.count("oportunidade"),
            snap["sidequests"]["gate"]["oportunidade"],
        )
        self.assertEqual(
            opp["orcamento"]["max_ativas"],
            snap["sidequests"]["max_ativas"],
        )
        self.assertEqual(
            rewards["orcamento"]["max_procedurais_por_mapa"],
            snap["recompensas"]["max_procedurais_por_mapa"],
        )
        self.assertEqual(
            rewards["orcamento"]["max_totais_por_mapa"],
            snap["recompensas"]["max_totais_por_mapa"],
        )


class EncounterIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.now = mundo.parse_instant("11 Eleasis, 1372 DR", "09:00")
        self._write(
            "narrador/oportunidades/index.yaml",
            {
                "schema_oportunidades": 1,
                "natureza": "reservado",
                "semente": "integracao-teste",
                "gate": {
                    "modo": "baralho_sem_reposicao_sha256",
                    "fichas": [
                        *[
                            {"id": f"nada_{i:02d}", "resultado": "nada"}
                            for i in range(1, 9)
                        ],
                        {"id": "oportunidade_01", "resultado": "oportunidade"},
                        {"id": "oportunidade_02", "resultado": "oportunidade"},
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
                        "id": "a",
                        "tipo": "busca",
                        "semente": "Algo pode estar perdido.",
                        "janela": {"tipo": "a_qualquer_momento"},
                        "pode_reabrir": False,
                        "consequencia_sem_ren": "Outra pessoa pode resolver.",
                    },
                    {
                        "id": "b",
                        "tipo": "protecao",
                        "semente": "Alguém pode precisar de proteção.",
                        "janela": {"tipo": "a_qualquer_momento"},
                        "pode_reabrir": False,
                        "consequencia_sem_ren": "Outra proteção pode surgir.",
                    },
                ],
            },
        )
        self._write("estado/relacoes/npc_a.yaml", {"schema_relacao": 2, "id": "npc_a"})

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, rel, value):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def test_um_ciclo_tem_oito_nada_e_duas_avaliacoes_sem_scan_de_perfil(self):
        counts = {"interacao_normal": 0, "avaliar_sidequest": 0}
        for i in range(10):
            result = interacoes_mundo.encounter_event(
                self.repo,
                "npc_a",
                now=self.now,
                encounter_id=f"encontro-{i}",
            )
            counts[result["resultado"]] += 1
            profile_reads = [
                source
                for source in result["fontes_lidas"]
                if source.startswith("narrador/oportunidades/perfis/")
            ]
            if result["resultado"] == "interacao_normal":
                self.assertEqual(profile_reads, [])
            else:
                self.assertEqual(
                    profile_reads,
                    ["narrador/oportunidades/perfis/npc_a.yaml"],
                )
                oportunidades.evaluate(
                    self.repo,
                    result["pendencia"]["id"],
                    "descartar",
                    reason="regressão do gate",
                    now=self.now,
                )

        self.assertEqual(counts, {"interacao_normal": 8, "avaliar_sidequest": 2})
        state = oportunidades.load_state(
            self.repo,
            oportunidades.load_index(self.repo),
        )
        self.assertEqual(state["gate"]["sorteios"], 10)

    def test_encontro_id_continua_idempotente(self):
        first = interacoes_mundo.encounter_event(
            self.repo,
            "npc_a",
            now=self.now,
            encounter_id="mesma-cena",
        )
        draws = oportunidades.load_state(
            self.repo,
            oportunidades.load_index(self.repo),
        )["gate"]["sorteios"]
        second = interacoes_mundo.encounter_event(
            self.repo,
            "npc_a",
            now=self.now,
            encounter_id="mesma-cena",
        )
        self.assertEqual(first["encontro_id"], "mesma-cena")
        self.assertEqual(second["motivo"], "encontro_ja_processado")
        self.assertEqual(
            oportunidades.load_state(
                self.repo,
                oportunidades.load_index(self.repo),
            )["gate"]["sorteios"],
            draws,
        )


class RewardIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        shutil.copytree(ROOT / "narrador/recompensas", self.repo / "narrador/recompensas")
        shutil.copytree(ROOT / "narrador/oportunidades", self.repo / "narrador/oportunidades")
        state = oportunidades.load_state(
            self.repo,
            oportunidades.load_index(self.repo),
        )
        state["missoes"]["sq-teste"] = {
            "id": "sq-teste",
            "estado": "aceita",
            "npc_id": "maerra_thandrel",
            "necessidade_id": "protecao_vulneravel",
        }
        oportunidades.atomic(self.repo / oportunidades.STATE, state)
        self.spec = {
            "id": "premio-sidequest-teste",
            "tipo": "tesouro",
            "condicao_de_descoberta": "entregue por quem prometeu a recompensa",
            "posse": {"tipo": "ambiente"},
            "importancia": "especial",
            "detalhe": {
                "nome": "Bolsa selada",
                "descricao": "Pagamento ligado à sidequest de regressão.",
                "valor_aproximado": "moderado",
                "tags": ["quest", "pagamento"],
            },
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_recompensa_de_quest_entra_uma_vez_sem_rerrolar_area(self):
        queued = interacoes_mundo.attach_quest_reward(
            self.repo,
            "sq-teste",
            "setor_teste",
            self.spec,
        )
        self.assertEqual(queued["resultado"], "planejada_para_mapa_futuro")

        first = interacoes_mundo.local_event(
            self.repo,
            "setor_teste",
            action="entrar",
            tier=1,
            danger="baixa",
        )
        self.assertTrue(first["mapa_criado"])
        map_path = self.repo / "narrador/recompensas/mapas/setor_teste.yaml"
        before = map_path.read_bytes()

        second = interacoes_mundo.local_event(
            self.repo,
            "setor_teste",
            action="explorar",
            tier=4,
            danger="letal",
        )
        self.assertFalse(second["mapa_criado"])
        self.assertEqual(before, map_path.read_bytes())
        self.assertEqual(
            second["fontes_lidas"],
            [
                "narrador/recompensas/index.yaml",
                "narrador/recompensas/mapas/setor_teste.yaml",
            ],
        )

        retry = interacoes_mundo.attach_quest_reward(
            self.repo,
            "sq-teste",
            "setor_teste",
            self.spec,
        )
        self.assertEqual(retry["resultado"], "ja_estava_no_mapa")

        data = yaml.safe_load(map_path.read_text(encoding="utf-8"))
        quest = [
            item
            for item in data["recompensas"]
            if item["id"] == "premio-sidequest-teste"
        ]
        self.assertEqual(len(quest), 1)
        self.assertEqual(quest[0]["origem"], "quest")
        self.assertTrue(recompensas.validate_repo(self.repo)["ok"])


class LifecycleIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.now = mundo.parse_instant("12 Eleasis, 1372 DR", "10:00")
        self._write(
            "narrador/oportunidades/index.yaml",
            {
                "schema_oportunidades": 1,
                "natureza": "reservado",
                "semente": "life",
                "gate": {
                    "modo": "baralho_sem_reposicao_sha256",
                    "fichas": [
                        *[
                            {"id": f"n{i}", "resultado": "nada"}
                            for i in range(8)
                        ],
                        {"id": "o1", "resultado": "oportunidade"},
                        {"id": "o2", "resultado": "oportunidade"},
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
                    "morto": {
                        "nome": "Morto",
                        "estado": "ativo",
                        "arquivo": "narrador/oportunidades/perfis/morto.yaml",
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
                "pendencias_avaliacao": {
                    "sq-p": {
                        "id": "sq-p",
                        "estado": "potencial",
                        "npc_id": "morto",
                        "necessidade_id": "n",
                    }
                },
                "missoes": {
                    "sq-a": {
                        "id": "sq-a",
                        "estado": "aceita",
                        "npc_id": "morto",
                        "necessidade_id": "a",
                    }
                },
                "sementes_consumidas": [],
                "encontros_recentes": [],
                "historico_recente": [],
            },
        )
        self._write(
            "narrador/mundo/ciclo-npcs.yaml",
            {
                "schema_ciclo_npcs": 1,
                "natureza": "controle_reservado",
                "mortos": {
                    "morto": {
                        "estado": "morto",
                        "fonte": "estado/npcs/morto.yaml",
                    }
                },
            },
        )
        self._write(
            "estado/npcs/index.yaml",
            {
                "schema_npcs": 2,
                "npcs": {
                    "morto": {"arquivo": "estado/npcs/morto.yaml"}
                },
            },
        )
        self._write(
            "estado/npcs/morto.yaml",
            {
                "schema_npc": 2,
                "id": "morto",
                "vida": {"estado": "morto"},
            },
        )

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, rel, value):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def test_morte_inviabiliza_potencial_e_faz_aceita_falhar(self):
        result = interacoes_mundo.sync_lifecycle(self.repo, now=self.now)
        self.assertTrue(result["alterou"])
        index = oportunidades.load_index(self.repo)
        state = oportunidades.load_state(self.repo, index)
        self.assertEqual(index["perfis"]["morto"]["estado"], "inativo")
        self.assertNotIn("sq-p", state["pendencias_avaliacao"])
        self.assertEqual(state["missoes"]["sq-a"]["estado"], "falhada")
        self.assertEqual(
            state["missoes"]["sq-a"]["motivo_encerramento"],
            "quest_giver_morto",
        )


class SidequestEffectsIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        shutil.copytree(ROOT / "narrador/oportunidades", self.repo / "narrador/oportunidades")
        shutil.copytree(ROOT / "narrador/relogios", self.repo / "narrador/relogios")
        state = oportunidades.load_state(
            self.repo,
            oportunidades.load_index(self.repo),
        )
        state["missoes"]["sq-efeito"] = {
            "id": "sq-efeito",
            "estado": "aceita",
            "npc_id": "pell",
            "necessidade_id": "teste",
        }
        oportunidades.atomic(self.repo / oportunidades.STATE, state)

    def tearDown(self):
        self.temp.cleanup()

    def test_operacao_pressao_e_consequencia_usam_so_roteadores_compactos(self):
        result = interacoes_mundo.prepare_sidequest_effects(
            self.repo,
            "sq-efeito",
            [
                {
                    "tipo": "operacao",
                    "operacao": "red_sail_reconstruir_cadeia_colm",
                },
                {
                    "tipo": "pressao",
                    "relogio": "rastro_fraco_no_pomar",
                },
                {
                    "tipo": "consequencia",
                    "valor": {
                        "titulo": "Efeito de sidequest",
                        "descricao": "Consequência de regressão.",
                    },
                },
            ],
        )
        self.assertEqual(
            result["fontes_lidas"],
            [
                "narrador/oportunidades/index.yaml",
                "narrador/oportunidades/estado.yaml",
                "narrador/relogios/vinculos.yaml",
            ],
        )
        self.assertEqual(len(result["deltas_transacionais"]), 2)
        pressure = result["deltas_transacionais"][0]
        self.assertEqual(pressure["alvo"], "relogio:rastro_fraco_no_pomar")
        self.assertEqual(pressure["valor"], 1)
        consequence = result["deltas_transacionais"][1]
        self.assertEqual(consequence["alvo"], "consequencia")
        self.assertEqual(
            consequence["valor"]["origem_sidequest"],
            "sq-efeito",
        )
        self.assertFalse(
            any(
                source.endswith("rastro_fraco_no_pomar.yaml")
                for source in result["fontes_lidas"]
            )
        )


class CheckpointIntegrationTest(unittest.TestCase):
    def test_checkpoint_propaga_lifecycle_sem_sortear_sidequest(self):
        repo = Path("/tmp/integracao-checkpoint")
        with (
            mock.patch.object(checkpoint, "_world_configured", return_value=True),
            mock.patch.object(checkpoint, "_directions_configured", return_value=False),
            mock.patch.object(checkpoint, "_integration_configured", return_value=True),
            mock.patch.object(
                checkpoint.interacoes_mundo,
                "sync_lifecycle",
                return_value={
                    "ok": True,
                    "configurado": True,
                    "alterou": True,
                    "missoes_encerradas": ["sq-x"],
                },
            ) as lifecycle,
            mock.patch.object(
                checkpoint.mundo,
                "process_to_canonical",
                return_value={
                    "ok": True,
                    "alterou": False,
                    "novas_pendencias": [],
                    "agentes_reconsiderar": [],
                },
            ),
        ):
            result = checkpoint.sync_world(repo)
        lifecycle.assert_called_once_with(repo)
        self.assertEqual(
            result["integracao_reativa"]["missoes_encerradas"],
            ["sq-x"],
        )
        self.assertEqual(result["novas_pendencias"], [])


class IntegrationBudgetTest(unittest.TestCase):
    def test_contrato_final_de_orcamento(self):
        contract = yaml.safe_load(BUDGET.read_text(encoding="utf-8"))
        self.assertEqual(contract["schema_orcamento_integracao_mundo_vivo"], 1)
        inv = contract["invariantes"]
        self.assertEqual(inv["scan_geral_por_turno"], 0)
        self.assertEqual(inv["geracao_recompensa_repetida"], 0)
        self.assertEqual(inv["sidequest_fora_de_encontro"], 0)
        self.assertEqual(inv["max_fragmentos_por_decisao"], 1)

        limits = contract["limites"]
        self.assertEqual(
            limits["encontro_gate_nada"]["max_fragmentos_narrativos"],
            0,
        )
        self.assertEqual(
            limits["encontro_oportunidade"]["max_fragmentos_narrativos"],
            1,
        )
        self.assertEqual(
            limits["checkpoint_lifecycle"]["max_fragmentos_narrativos_expostos"],
            0,
        )

    def test_novos_roteadores_quentes_ficam_dentro_do_teto(self):
        contract = yaml.safe_load(BUDGET.read_text(encoding="utf-8"))
        limit = contract["limites"]["arquivos_quentes"]
        sizes = {}
        for rel in contract["arquivos_quentes_novos"]:
            path = ROOT / rel
            sizes[rel] = path.stat().st_size
            self.assertLessEqual(
                sizes[rel],
                limit["max_bytes_por_roteador"],
                (rel, sizes[rel]),
            )
        self.assertLessEqual(
            sum(sizes.values()),
            limit["max_bytes_total_novos"],
            sizes,
        )


if __name__ == "__main__":
    unittest.main()
