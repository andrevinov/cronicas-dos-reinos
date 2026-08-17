from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
sys.path.insert(0, str(TOOLS))

import turno


class TurnoCicloSessaoTest(unittest.TestCase):
    def test_turno_recusa_registro_enquanto_campanha_esta_entre_sessoes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "runtime").mkdir(parents=True)
            (repo / "runtime/contexto.yaml").write_text(
                "sessao:\n  numero: 3\n  status: entre_sessoes\n",
                encoding="utf-8",
            )
            with self.assertRaises(turno.TransactionError) as ctx:
                turno.register_transaction(
                    repo,
                    {
                        "jogador": "Ren avança.",
                        "narracao": "A história continua.",
                        "resumo": "Tentativa indevida entre sessões.",
                        "deltas": [],
                    },
                )
            self.assertIn("sessoes.py iniciar", str(ctx.exception))
            self.assertFalse((repo / "sessoes/003/transcricao.md").exists())
            self.assertFalse((repo / "runtime/eventos-pendentes.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
