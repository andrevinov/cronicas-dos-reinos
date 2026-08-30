from __future__ import annotations

import copy
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

import intencoes_canonicas
import oportunidade_sidequest as emergent
import oportunidades


class EmergentBoundaryZeroCostTest(unittest.TestCase):
    def test_conversa_normal_sem_sinal_faz_zero_leituras(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = emergent.plan(Path(tmp), signaled=False)
        self.assertEqual(result["resultado"], "nao_sinalizada")
        self.assertEqual(result["fontes_lidas"], [])
        self.assertFalse(result["mutacoes_aplicadas"])
        self.assertTrue(result["read_only"])

    def test_oportunidade_recusada_pelo_codex_faz_zero_leituras_e_escritas(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            before = sorted(root.iterdir())
            result = emergent.decline()
            after = sorted(root.iterdir())
        self.assertEqual(result["resultado"], "oportunidade_recusada_pelo_narrador")
        self.assertEqual(result["fontes_lidas"], [])
        self.assertEqual(before, after)
        self.assertEqual(result["metricas"]["intencoes_lidas"], 0)

    def test_presenca_incidental_falha_antes_da_primeira_leitura(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(
                emergent.EmergentSidequestOpportunityError,
                "presença incidental",
            ):
                emergent.plan(
                    Path(tmp),
                    signaled=True,
                    origin_type="presenca_incidental",
                    origin_id="npc-incidental",
                    anchor_type="presenca",
                    anchor="Uma pessoa apareceu incidentalmente na cena sem problema ou pedido concreto.",
                )


class EmergentBoundaryFailFastTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        target = self.repo / oportunidades.INDEX
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / oportunidades.INDEX, target)
        state = copy.deepcopy(oportunidades.load_state(ROOT, oportunidades.load_index(ROOT)))
        state["missoes"] = {
            "m1": {"id": "m1", "estado": "aceita", "npc_id": "a", "necessidade_id": "a"},
            "m2": {"id": "m2", "estado": "aceita", "npc_id": "b", "necessidade_id": "b"},
        }
        state_path = self.repo / oportunidades.STATE
        state_path.write_text(
            yaml.safe_dump(state, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_duas_aceitas_retornam_limite_sem_horizonte_secreto(self):
        with mock.patch.object(
            emergent,
            "_intent_horizon",
            side_effect=AssertionError("Task39 não deve abrir com limite ativo"),
        ), mock.patch.object(
            emergent,
            "_effective_relationship",
            side_effect=AssertionError("relação não deve abrir com limite ativo"),
        ), mock.patch.object(
            emergent,
            "_causal_actors_and_juppongatana",
            side_effect=AssertionError("atores não devem abrir com limite ativo"),
        ), mock.patch.object(
            emergent,
            "_reward_envelope",
            side_effect=AssertionError("recompensa não deve abrir com limite ativo"),
        ):
            result = emergent.plan(
                self.repo,
                signaled=True,
                origin_type="fato_de_cena",
                origin_id="cena-limite",
                anchor_type="problema",
                anchor="A cena materializou um problema concreto que em outra situação poderia virar aventura.",
            )
        self.assertEqual(result["resultado"], "limite_ativas")
        self.assertEqual(
            result["fontes_lidas"],
            [oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix()],
        )
        self.assertEqual(result["metricas"]["intencoes_lidas"], 0)
        self.assertNotIn("horizonte_intencoes_canonicas", result)


class EmergentBoundaryRepositoryTest(unittest.TestCase):
    def _signal(self, **overrides):
        values = {
            "signaled": True,
            "origin_type": "conversa_npc",
            "origin_id": "teste-task40-silva",
            "anchor_type": "problema",
            "anchor": (
                "A conversa trouxe uma necessidade concreta, causalmente ancorada na cena, "
                "que pode sustentar uma aventura sem presumir que Ren aceitará."
            ),
            "npc_id": "silva_elkwood",
            "local_id": "jack_mooney_sons_circus",
            "danger": "media",
        }
        values.update(overrides)
        return emergent.plan(ROOT, **values)

    def test_planejamento_real_e_read_only_idempotente_e_limitado(self):
        protected = [
            ROOT / oportunidades.STATE,
            ROOT / "narrador/mundo/condicoes-persistentes.yaml",
            ROOT / "narrador/juppongatana/estado-progressao.yaml",
            ROOT / "narrador/recompensas/index.yaml",
            ROOT / intencoes_canonicas.INDEX,
        ]
        before = {path.as_posix(): path.read_bytes() for path in protected}
        first = self._signal()
        second = self._signal()
        after = {path.as_posix(): path.read_bytes() for path in protected}

        self.assertEqual(first, second)
        self.assertEqual(before, after)
        self.assertEqual(first["resultado"], "material_para_planejamento")
        self.assertTrue(first["read_only"])
        self.assertFalse(first["mutacoes_aplicadas"])
        self.assertLessEqual(emergent._rendered_bytes(first), emergent.MAX_PAYLOAD_BYTES)
        self.assertLessEqual(
            first["horizonte_intencoes_canonicas"]["avaliadas"],
            emergent.MAX_INTENT_FRAGMENTS,
        )
        self.assertLessEqual(len(first["atores_causalmente_disponiveis"]), emergent.MAX_ACTORS)
        self.assertLessEqual(len(first["juppongatana_possiveis"]), emergent.MAX_JUPPONGATANA)
        self.assertIsNotNone(first["relacao_efetiva"])
        self.assertEqual(first["relacao_efetiva"]["npc_id"], "silva_elkwood")

    def test_fontes_nao_varrem_catalogo_task33_transcricao_ou_evento_task36(self):
        result = self._signal()
        sources = result["fontes_lidas"]
        self.assertFalse(any("transcricao" in source for source in sources), sources)
        self.assertFalse(any(source.startswith("narrador/sidequests-canonicas/") for source in sources), sources)
        self.assertFalse(any(source.startswith("narrador/arcos/parte_1/eventos/") for source in sources), sources)
        intent_sources = [
            source
            for source in sources
            if source.startswith("narrador/arcos/parte_1/intencoes/")
        ]
        self.assertLessEqual(len(intent_sources), emergent.MAX_INTENT_FRAGMENTS)
        self.assertFalse(result["metricas"]["catalogo_task33_aberto"])
        self.assertFalse(result["metricas"]["transcricao_lida"])
        self.assertEqual(result["metricas"]["scans_globais"], 0)

    def test_envelope_de_recompensa_planeja_sem_gerar_item(self):
        before = (ROOT / "narrador/recompensas/index.yaml").read_bytes()
        result = self._signal()
        after = (ROOT / "narrador/recompensas/index.yaml").read_bytes()
        envelope = result["envelope_recompensa"]
        self.assertEqual(before, after)
        self.assertEqual(envelope["tier"], 2)
        self.assertEqual(envelope["periculosidade"], "media")
        self.assertEqual(envelope["familia_local"], "acampamento_espetaculo")
        self.assertGreaterEqual(envelope["pontos"], 1)
        self.assertNotIn("item", envelope)
        self.assertNotIn("recompensa", envelope)

    def test_atores_e_juppongatana_sao_candidatos_nao_escolhas(self):
        result = self._signal(origin_type="mensagem", npc_id=None, origin_id="mensagem-teste-task40")
        actors = result["atores_causalmente_disponiveis"]
        possible = result["juppongatana_possiveis"]
        self.assertTrue(all(item["causal_agora"] for item in actors))
        self.assertLessEqual(len(possible), 4)
        self.assertTrue(all("causal_agora" in item for item in possible))
        self.assertFalse(result["autoridade"]["pode_criar_missao"])
        self.assertFalse(result["autoridade"]["pode_reescrever_intencao"])


class EmergentBoundaryBudgetContractTest(unittest.TestCase):
    def test_contrato_congela_tetos_e_zero_infra(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/emergent-sidequest-opportunity-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        limits = contract["limites"]
        self.assertEqual(limits["payload_bytes_max"], emergent.MAX_PAYLOAD_BYTES)
        self.assertEqual(limits["intencoes_canonicas_max"], emergent.MAX_INTENT_FRAGMENTS)
        self.assertEqual(limits["horizonte_intencoes_dias"], emergent.MAX_HORIZON_DAYS)
        self.assertEqual(limits["atores_causais_max"], emergent.MAX_ACTORS)
        self.assertEqual(limits["juppongatana_possiveis_max"], emergent.MAX_JUPPONGATANA)
        for key in (
            "escritas_planejar",
            "escritas_recusar",
            "leituras_sem_sinal",
            "leituras_recusar",
            "schedulers_novos",
            "rng_novo",
            "scans_globais",
            "estados_persistentes_novos",
        ):
            self.assertEqual(limits[key], 0)
        self.assertTrue(all(contract["invariantes"].values()))

    def test_implementacao_nao_varre_repo_nem_importa_rng_scheduler(self):
        source = (ROOT / "ferramentas/oportunidade_sidequest.py").read_text(encoding="utf-8")
        for forbidden in (
            "import random",
            "threading",
            "asyncio",
            "subprocess",
            "os.walk",
            ".rglob(",
            ".glob(",
        ):
            self.assertNotIn(forbidden, source)

    def test_envelope_derivado_continua_alinhado_ao_reward_budget_v2(self):
        result = emergent.check(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["max_payload_bytes"], 8192)
        self.assertEqual(result["max_intencoes"], 3)
        self.assertEqual(result["rng_novo"], 0)
        self.assertEqual(result["scans_globais"], 0)


if __name__ == "__main__":
    unittest.main()
