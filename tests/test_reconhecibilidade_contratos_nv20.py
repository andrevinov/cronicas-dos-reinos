from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica
import preflight


class RecognitionOperationalContractTest(unittest.TestCase):
    def test_cronica_expoe_regra_do_mesmo_writer_sem_consultar_placar(self):
        contract = cronica._transaction_contract()
        self.assertIn("reconhecibilidade_persona_nv20", contract)
        text = contract["reconhecibilidade_persona_nv20"]
        self.assertIn("mesmo writer", text)
        self.assertIn("não confirma identidade real", text)
        self.assertIn("nunca escolha desafiante aleatoriamente", text)

    def test_preflight_inclui_check_read_only_da_nv20(self):
        checks = preflight.checks(incluir_testes=False)
        matches = [item for item in checks if item.nome == "reconhecibilidade de personas"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(
            matches[0].comando[-2:],
            ("ferramentas/reconhecibilidade_persona.py", "check"),
        )


if __name__ == "__main__":
    unittest.main()
