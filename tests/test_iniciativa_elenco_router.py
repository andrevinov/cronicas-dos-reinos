from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class PresentCastInitiativeRouterTest(unittest.TestCase):
    def test_router_separa_participante_presenca_e_interlocutor(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("--interlocutor <id>", text)
        self.assertIn("Participante não vira interlocutor sozinho", text)
        self.assertIn("interlocutor não cria presença, encontro ou side quest", text)
        self.assertIn("docs/nv16-iniciativa-elenco-presente.md", text)

    def test_router_permanece_dentro_do_orcamento_existente(self):
        self.assertLessEqual((ROOT / "AGENTS.md").stat().st_size, 13312)


if __name__ == "__main__":
    unittest.main()
