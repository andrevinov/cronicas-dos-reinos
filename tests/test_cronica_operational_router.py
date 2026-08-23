from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]


class CronicaOperationalRouterTest(unittest.TestCase):
    def test_agents_declara_cronica_como_hot_path(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("**Porta operacional preferencial.**", text)
        self.assertIn("poetry run cronica preparar", text)
        self.assertIn("poetry run cronica concluir --ticket", text)
        self.assertIn("poetry run cronica sessao iniciar", text)
        self.assertIn("poetry run cronica sessao encerrar", text)
        self.assertIn("poetry run cronica progressao aplicar", text)
        self.assertIn("não pedir que ele rode CLI manualmente", text)

    def test_protocolo_de_sessao_nao_exige_cli_manual_do_jogador(self):
        text = (ROOT / "narracao/protocolo-de-sessao.md").read_text(encoding="utf-8")
        self.assertIn("a operação é do narrador, não do jogador", text)
        self.assertIn("poetry run cronica sessao status", text)
        self.assertIn("poetry run cronica sessao iniciar", text)
        self.assertIn("poetry run cronica preparar", text)
        self.assertIn("poetry run cronica concluir --ticket", text)
        self.assertIn("poetry run cronica sessao checkpoint", text)
        self.assertIn("poetry run cronica sessao encerrar", text)
        self.assertIn("poetry run cronica sessao recuperar", text)


if __name__ == "__main__":
    unittest.main()
