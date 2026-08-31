from __future__ import annotations

import unittest
from pathlib import Path

from ferramentas import preflight


ROOT = Path(__file__).parents[1]
INTEGRITY_WORKFLOW = ROOT / ".github/workflows/integridade.yml"
PREFLIGHT_WORKFLOW = ROOT / ".github/workflows/preflight.yml"
FULL_SUITE_COMMAND = "python -m unittest discover -s tests -v"
CI_PREFLIGHT_COMMAND = "python ferramentas/preflight.py --sem-testes"
AUDIT_WITHOUT_TESTS = "python ferramentas/auditoria-final.py --json --sem-testes"


class CiFullSuiteOwnershipTest(unittest.TestCase):
    def test_integridade_e_unica_dona_da_suite_completa_no_fluxo_normal_de_pr(self):
        integrity = INTEGRITY_WORKFLOW.read_text(encoding="utf-8")
        preflight_workflow = PREFLIGHT_WORKFLOW.read_text(encoding="utf-8")

        self.assertEqual(integrity.count(FULL_SUITE_COMMAND), 1)
        self.assertNotIn(FULL_SUITE_COMMAND, preflight_workflow)
        self.assertIn(CI_PREFLIGHT_COMMAND, preflight_workflow)
        self.assertIn(AUDIT_WITHOUT_TESTS, integrity)

    def test_preflight_local_continua_completo_por_padrao_sem_repetir_na_auditoria(self):
        full = preflight.checks()
        without_tests = preflight.checks(incluir_testes=False)

        full_commands = [" ".join(item.comando) for item in full]
        without_test_commands = [" ".join(item.comando) for item in without_tests]

        self.assertEqual(sum(FULL_SUITE_COMMAND in command for command in full_commands), 1)
        self.assertFalse(any(FULL_SUITE_COMMAND in command for command in without_test_commands))
        self.assertEqual(len(full), len(without_tests) + 1)

        full_audit = next(item for item in full_commands if "auditoria-final.py" in item)
        short_audit = next(item for item in without_test_commands if "auditoria-final.py" in item)
        self.assertIn("--sem-testes", full_audit)
        self.assertIn("--sem-testes", short_audit)


if __name__ == "__main__":
    unittest.main()
