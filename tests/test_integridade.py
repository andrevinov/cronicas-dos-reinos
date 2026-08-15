from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "ferramentas" / "verificar-integridade.py"
spec = importlib.util.spec_from_file_location("verificar_integridade", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class IntegridadeHelpersTest(unittest.TestCase):
    def test_get_path(self):
        self.assertEqual(mod.get_path({"a": {"b": 3}}, "a.b"), 3)
        with self.assertRaises(KeyError):
            mod.get_path({"a": {}}, "a.c")

    def test_duplicate_yaml_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.yaml"
            path.write_text("a: 1\na: 2\n", encoding="utf-8")
            with self.assertRaises(Exception):
                mod.load_yaml(path)


if __name__ == "__main__":
    unittest.main()
