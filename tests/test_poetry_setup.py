from __future__ import annotations

import sys
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from ferramentas import poetry_cli

ROOT = Path(__file__).parents[1]


class PoetrySetupTest(unittest.TestCase):
    def test_pyproject_declares_dependency_and_expected_commands(self):
        data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(data["project"]["requires-python"], ">=3.12,<4.0")
        self.assertIn("PyYAML>=6.0,<7.0", data["project"]["dependencies"])

        scripts = data["project"]["scripts"]
        expected = {
            "entrada",
            "contexto",
            "cronica",
            "turno",
            "checkpoint",
            "consolidar",
            "auditoria",
            "integridade",
            "runtime",
            "sessoes",
            "dados",
            "dados-lote",
            "rollout",
            "rollout-comparar",
            "rollout-benchmark",
            "preflight",
            "test-fast",
            "test-domain",
            "test-full",
            "testes",
        }
        self.assertEqual(set(scripts), expected)
        self.assertTrue(all(value.startswith("ferramentas.poetry_cli:") for value in scripts.values()))
        self.assertNotIn("rolar-dados", scripts)
        self.assertNotIn("rolar-lote", scripts)

    def test_poetry_keeps_virtualenv_inside_repo(self):
        data = tomllib.loads((ROOT / "poetry.toml").read_text(encoding="utf-8"))
        self.assertIs(data["virtualenvs"]["in-project"], True)

    def test_every_wrapper_target_exists(self):
        targets = {
            "entrada.py",
            "contexto.py",
            "cronica.py",
            "turno.py",
            "checkpoint.py",
            "consolidar.py",
            "auditoria-final.py",
            "verificar-integridade.py",
            "gerar-runtime.py",
            "sessoes.py",
            "rolar-dados.py",
            "rolar-lote.py",
            "analisar-rollout.py",
            "comparar-rollouts.py",
            "benchmark-rollouts.py",
            "preflight.py",
            "testes.py",
        }
        for name in targets:
            self.assertTrue((ROOT / "ferramentas" / name).is_file(), name)

    def test_wrapper_uses_current_venv_python_and_repo_as_cwd(self):
        with patch.object(sys, "argv", ["contexto", "status"]), patch(
            "ferramentas.poetry_cli.subprocess.run"
        ) as run:
            run.return_value.returncode = 0
            code = poetry_cli.contexto()

        self.assertEqual(code, 0)
        args, kwargs = run.call_args
        self.assertEqual(args[0][0], sys.executable)
        self.assertEqual(Path(args[0][1]), ROOT / "ferramentas/contexto.py")
        self.assertEqual(args[0][2:], ["status"])
        self.assertEqual(kwargs["cwd"], ROOT)
        self.assertFalse(kwargs["check"])

    def test_test_profile_wrappers_prefixam_perfil_sem_perder_argumentos(self):
        cases = (
            (poetry_cli.test_fast, "test-fast", ["fast", "--list"]),
            (poetry_cli.test_domain, "test-domain", ["domain", "mecânica", "--list"]),
            (poetry_cli.test_full, "test-full", ["full", "--list"]),
            (poetry_cli.testes, "testes", ["full", "--list"]),
        )
        for wrapper, argv0, expected_tail in cases:
            extra = expected_tail[1:]
            with self.subTest(wrapper=wrapper.__name__), patch.object(
                sys, "argv", [argv0, *extra]
            ), patch("ferramentas.poetry_cli.subprocess.run") as run:
                run.return_value.returncode = 0
                self.assertEqual(wrapper(), 0)
                args, kwargs = run.call_args
                self.assertEqual(args[0][0], sys.executable)
                self.assertEqual(Path(args[0][1]), ROOT / "ferramentas/testes.py")
                self.assertEqual(args[0][2:], expected_tail)
                self.assertEqual(kwargs["cwd"], ROOT)
                self.assertFalse(kwargs["check"])


if __name__ == "__main__":
    unittest.main()
