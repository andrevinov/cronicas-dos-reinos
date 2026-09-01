from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from ferramentas import preflight


ROOT = Path(__file__).parents[1]


class PreflightTest(unittest.TestCase):
    def test_preflight_reune_os_gates_essenciais_sem_mutacao_operacional(self):
        items = preflight.checks()
        names = {item.nome for item in items}
        self.assertIn("testes unitários", names)
        self.assertIn("turno transacional", names)
        self.assertIn("consolidação", names)
        self.assertIn("memória de sessões", names)
        self.assertIn("checkpoint", names)
        self.assertIn("runtime derivado", names)
        self.assertIn("integridade estrutural e semântica", names)
        self.assertIn("baseline histórica", names)
        self.assertIn("auditoria final e retomada", names)

        commands = [" ".join(item.comando) for item in items]
        self.assertFalse(any(" turno.py registrar" in command for command in commands))
        self.assertFalse(any(" consolidar.py cena" in command for command in commands))
        self.assertFalse(any(" consolidar.py sessao" in command for command in commands))
        self.assertFalse(any(" checkpoint.py cena" in command for command in commands))
        self.assertFalse(any(" checkpoint.py sessao" in command for command in commands))
        self.assertTrue(any("gerar-runtime.py --check" in command for command in commands))

    def test_preflight_inclui_gates_de_sidequest_por_comando_estavel(self):
        commands = {tuple(item.comando[1:]) for item in preflight.checks(incluir_testes=False)}
        expected = {
            ("ferramentas/recompensas_sidequest.py", "check"),
            ("ferramentas/integridade_adversarial.py", "check"),
            ("ferramentas/progressao_sidequests.py", "check"),
            ("ferramentas/sidequests_integracao_check.py",),
            ("ferramentas/sidequests_ativas.py", "check"),
            ("ferramentas/progresso_sidequests_transacional.py", "check"),
            ("ferramentas/oportunidades.py", "check"),
            ("ferramentas/canon_bridge_runtime.py", "check"),
        }
        self.assertTrue(expected <= commands)

        names = {item.nome for item in preflight.checks(incluir_testes=False)}
        self.assertIn("recompensas de sidequest", names)
        self.assertIn("integridade adversarial", names)
        self.assertIn("progressão e consequências de sidequest", names)
        self.assertIn("integração de sidequests emergentes", names)
        self.assertIn("projeção de sidequests ativas", names)
        self.assertIn("progresso transacional de sidequests", names)
        self.assertIn("canon bridge", names)
        self.assertFalse(any("Task4" in name for name in names))

    def test_sem_testes_remove_apenas_unittest(self):
        full = preflight.checks(incluir_testes=True)
        short = preflight.checks(incluir_testes=False)
        self.assertEqual(len(full), len(short) + 1)
        self.assertNotIn("testes unitários", {item.nome for item in short})
        self.assertIn("auditoria final e retomada", {item.nome for item in short})

    def test_fail_fast_para_no_primeiro_gate_vermelho(self):
        with patch.object(preflight.subprocess, "run") as run:
            run.side_effect = [SimpleNamespace(returncode=0), SimpleNamespace(returncode=1)]
            results = preflight.run_preflight(ROOT, incluir_testes=False, fail_fast=True)
        self.assertEqual(len(results), 2)
        self.assertTrue(results[0].ok)
        self.assertFalse(results[1].ok)
        self.assertEqual(run.call_count, 2)

    def test_summary_expoe_gate_que_falhou(self):
        check = preflight.Check("exemplo", ("python", "x"), "teste")
        result = preflight.Result(check, 3, 0.1)
        text = preflight._summary([result])
        self.assertIn("VEREDITO: FALHA", text)
        self.assertIn("exemplo: exit 3", text)


if __name__ == "__main__":
    unittest.main()
