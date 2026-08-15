from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
MODULE_PATH = TOOLS / "rolar-lote.py"
spec = importlib.util.spec_from_file_location("rolar_lote", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class RollBatchTest(unittest.TestCase):
    def test_reads_array_and_object_formats(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rolls.json"
            path.write_text(json.dumps([["rolar", "1d6"], ["ren", "iniciativa"]]), encoding="utf-8")
            self.assertEqual(len(mod.read_payload(path)), 2)
            path.write_text(json.dumps({"rolagens": ["rolar 1d4", ["d20", "--bonus", "2"]]}), encoding="utf-8")
            self.assertEqual(len(mod.read_payload(path)), 2)

    def test_runs_two_rolls_with_single_batch_process(self):
        commands = [
            ["rolar", "1d6", "--label", "Primeira"],
            ["d20", "--bonus", "2", "--label", "Segunda"],
        ]
        outputs = mod.run_batch(TOOLS / "rolar-dados.py", commands)
        self.assertEqual(len(outputs), 2)
        self.assertIn("Primeira", outputs[0])
        self.assertIn("Segunda", outputs[1])

    def test_rejects_oversized_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "rolls.json"
            path.write_text(json.dumps([["rolar", "1d6"]] * (mod.MAX_ROLLS + 1)), encoding="utf-8")
            with self.assertRaises(mod.BatchError):
                mod.read_payload(path)


if __name__ == "__main__":
    unittest.main()
