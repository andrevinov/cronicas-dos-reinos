from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import iniciativa_elenco
import memoria_cena_iniciativa


class PresentCastInitiativeIntegrationContractTest(unittest.TestCase):
    def test_composicao_reusa_documents_sem_contexto_npc_por_interlocutor(self):
        source = (TOOLS / "memoria_cena_iniciativa.py").read_text(encoding="utf-8")
        self.assertEqual(source.count("memory.documents("), 1)
        self.assertNotIn("command_npc", source)
        self.assertNotIn("rglob(", source)
        self.assertNotIn("glob(", source)

    def test_selecao_nao_varre_indices_para_resolver_interlocutor(self):
        source = (TOOLS / "iniciativa_elenco.py").read_text(encoding="utf-8")
        self.assertIn("npc_id in index", source)
        self.assertNotIn("for npc_id in index", source)
        self.assertNotIn("rglob(", source)
        self.assertNotIn("random", source)

    def test_janela_de_permanencia_nao_depende_de_scene_id(self):
        first = {
            "cena": {"scene_id": "circo-a"},
            "permanencia_espacial": {"local_id": "circo_hooft", "data": "21 Eleasis, 1372 DR", "periodo": "anoitecer"},
        }
        second = {
            "cena": {"scene_id": "circo-b"},
            "permanencia_espacial": {"local_id": "circo_hooft", "data": "21 Eleasis, 1372 DR", "periodo": "anoitecer"},
        }
        window_a, kind_a, _ = iniciativa_elenco._window(first)
        window_b, kind_b, _ = iniciativa_elenco._window(second)
        self.assertEqual(kind_a, "permanencia")
        self.assertEqual(kind_b, "permanencia")
        self.assertEqual(window_a, window_b)

    def test_extensao_sem_interlocutores_delega_ao_attach_anterior(self):
        self.assertIsNot(memoria_cena_iniciativa.attach, memoria_cena_iniciativa._BASE_ATTACH)
        self.assertIsNone(memoria_cena_iniciativa._CURRENT.get())


if __name__ == "__main__":
    unittest.main()
