from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))

import cena_mundo
import endpoints
import mundo
import oportunidades
import sidequests_canonicas as canonical
import sidequests_canonicas_cena

from sidequests_canonicas_task32_cases import (
    CanonicalSecretQuestBudgetTest,
    CanonicalSecretQuestSyntheticTest,
)


class CanonicalSecretQuestRepositoryTest(unittest.TestCase):
    def test_repo_real_aceita_catalogo_sem_expor_detalhes_no_check(self):
        index = oportunidades.load_index(ROOT)
        router = index["sidequests_canonicas"]
        self.assertEqual(router["engine"], canonical.ENGINE_ID)
        self.assertEqual(router["roteamento"], canonical.FRAGMENTED_ROUTING)
        self.assertNotIn("por_npc", router)
        mapping, sources = canonical.catalog_refs(ROOT, index)
        self.assertTrue(mapping)
        self.assertEqual(len(sources), len(mapping))
        result = canonical.check(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertGreater(result["quest_givers"], 0)
        self.assertGreater(result["quests_roteadas"], 0)
        self.assertEqual(result["detalhes_expostos"], 0)

    def test_encontro_real_sem_refs_continua_sem_acionar_engine(self):
        now = mundo.parse_instant("17 Eleasis, 1372 DR", "18:00")
        with mock.patch.object(
            sidequests_canonicas_cena.sidequests_canonicas,
            "select_from_refs",
            side_effect=AssertionError("engine não deveria rodar sem refs"),
        ):
            preview = cena_mundo.prepare_scene(
                ROOT,
                scene_id="task33:repo-sem-ref",
                npcs=["sorn_kel"],
                now=now,
            )
        self.assertNotIn("sidequest_canonica", preview)
        self.assertFalse(
            any("sidequests-canonicas/gates" in item for item in preview["fontes_lidas"])
        )
        self.assertFalse(
            any("sidequests-canonicas/roteadores" in item for item in preview["fontes_lidas"])
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


if __name__ == "__main__":
    unittest.main()
