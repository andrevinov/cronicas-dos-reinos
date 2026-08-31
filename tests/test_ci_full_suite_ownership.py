from __future__ import annotations

import unittest
from pathlib import Path

from ferramentas import preflight


ROOT = Path(__file__).parents[1]
INTEGRITY_WORKFLOW = ROOT / ".github/workflows/integridade.yml"
PREFLIGHT_WORKFLOW = ROOT / ".github/workflows/preflight.yml"
FULL_SUITE_COMMAND = "python -m unittest discover -s tests -v"
CI_PREFLIGHT_COMMAND = "python ferramentas/preflight.py --sem-testes"


class CiFullSuiteOwnershipTest(unittest.TestCase):
    def test_integridade_e_unica_dona_da_suite_completa_no_fluxo_normal_de_pr(self):
        integrity = INTEGRITY_WORKFLOW.read_text(encoding="utf-8")
        preflight_workflow = PREFLIGHT_WORKFLOW.read_text(encoding="utf-8")

        self.assertIn(FULL_SUITE_COMMAND, integrity)
        self.assertNotIn(FULL_SUITE_COMMAND, preflight_workflow)
        self.assertEqual(
            integrity.count(FULL_SUITE_COMMAND) + preflight_workflow.count(FULL_SUITE_COMMAND),
            1,
        )
        self.assertIn(CI_PREFLIGHT_COMMAND, preflight_workflow)

    def test_preflight_local_continua_completo_por_padrao(self):
        full = preflight.checks()
        without_tests = preflight.checks(incluir_testes=False)

        full_commands = {" ".join(item.comando) for item in full}
        without_test_commands = {" ".join(item.comando) for item in without_tests}

        self.assertTrue(any(FULL_SUITE_COMMAND in command for command in full_commands))
        self.assertFalse(any(FULL_SUITE_COMMAND in command for command in without_test_commands))
        self.assertEqual(len(full), len(without_tests) + 1)


if __name__ == "__main__":
    unittest.main()
