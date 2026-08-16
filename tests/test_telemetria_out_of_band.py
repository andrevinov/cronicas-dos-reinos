from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
MODULE = TOOLS / "contexto.py"
spec = importlib.util.spec_from_file_location("contexto_telemetria_test", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class OutOfBandTelemetryTest(unittest.TestCase):
    def test_context_query_does_not_log_by_default(self):
        args = mod.build_parser().parse_args(["status"])
        self.assertFalse(args.log_local)
        self.assertFalse(args.sem_log)

    def test_local_log_is_explicit_opt_in(self):
        args = mod.build_parser().parse_args(["--log-local", "status"])
        self.assertTrue(args.log_local)

    def test_legacy_sem_log_remains_accepted_without_enabling_log(self):
        args = mod.build_parser().parse_args(["--sem-log", "status"])
        self.assertFalse(args.log_local)
        self.assertTrue(args.sem_log)


if __name__ == "__main__":
    unittest.main()
