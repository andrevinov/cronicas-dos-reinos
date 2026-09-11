from __future__ import annotations

from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica
import preflight


class CivicOperationalContractTest(unittest.TestCase):
    def test_cronica_expoe_causalidade_e_economia_nv22(self):
        contract = cronica._transaction_contract()
        self.assertIn("politica_civica_nv22", contract)
        text = contract["politica_civica_nv22"]
        self.assertIn("instituição autorizada", text)
        self.assertIn("ausência normal de nova lei", text)
        self.assertIn("nunca aleatório", text)
        self.assertIn("mesmo writer", text)
        self.assertIn("recibo NV-13", text)

    def test_preflight_inclui_check_read_only_da_nv22(self):
        checks = preflight.checks(incluir_testes=False)
        matches = [item for item in checks if item.nome == "política cívica e avisos públicos"]
        self.assertEqual(len(matches), 1)
        self.assertEqual(
            matches[0].comando[-2:],
            ("ferramentas/politica_civica.py", "check"),
        )


if __name__ == "__main__":
    unittest.main()
