from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "ferramentas" / "gerar-runtime.py"
spec = importlib.util.spec_from_file_location("gerar_runtime", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

REPO = Path(__file__).parents[1]


class RuntimeTest(unittest.TestCase):
    def test_tail_sentences_reduces_history(self):
        text = "Um. Dois. Três. Quatro. Cinco."
        self.assertEqual(mod.tail_sentences(text, 2, 100), "Quatro. Cinco.")

    def test_tail_sentences_obeys_hard_limit(self):
        text = "Primeiro evento longo. " + ("x" * 300) + ". Último evento."
        result = mod.tail_sentences(text, 3, 80)
        self.assertLessEqual(len(result), 82)  # inclui possível prefixo de reticências
        self.assertIn("Último evento.", result)

    def test_committed_runtime_matches_canonical_sources(self):
        contexto, cena = mod.build_runtime(REPO)
        errors = mod.check_runtime(REPO, contexto, cena)
        self.assertEqual(errors, [])

    def test_hot_files_stay_small(self):
        self.assertLess((REPO / "runtime/contexto.yaml").stat().st_size, 8 * 1024)
        self.assertLess((REPO / "runtime/cena.yaml").stat().st_size, 8 * 1024)

    def test_runtime_declares_itself_derived(self):
        contexto = mod.load_yaml(REPO / "runtime/contexto.yaml")
        cena = mod.load_yaml(REPO / "runtime/cena.yaml")
        self.assertEqual(contexto["natureza"], "derivado_descartavel")
        self.assertEqual(cena["natureza"], "derivado_descartavel")


if __name__ == "__main__":
    unittest.main()
