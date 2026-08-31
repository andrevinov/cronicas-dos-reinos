from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

MODULE_PATH = TOOLS / "auditoria-final.py"
spec = importlib.util.spec_from_file_location("auditoria_final", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


class AuditoriaFinalTest(unittest.TestCase):
    def test_hot_only_resume_reconstructs_current_scene_without_transcript(self):
        result = mod.gate_hot_only_resume(ROOT)
        self.assertFalse(result["transcricao_lida"])
        self.assertLessEqual(result["bytes_saida"], 8192)
        snapshot = result["snapshot"]

        # A retomada é definida pelo estado operacional efetivo: checkpoint quente
        # mais deltas ainda pendentes. Comparar com estado-atual puro fica obsoleto
        # assim que a sessão avança antes do próximo checkpoint.
        effective_context, effective_scene, _ = mod._effective_runtime(ROOT)
        self.assertEqual(snapshot["sessao"], effective_context["sessao"]["numero"])
        self.assertEqual(snapshot["personagem"], effective_context["personagem"]["nome"])
        self.assertEqual(snapshot["nivel"], effective_context["personagem"]["nivel"])
        self.assertEqual(snapshot["pv"], effective_context["recursos"]["pv"])
        self.assertEqual(snapshot["focus"], effective_context["recursos"]["focus"])
        self.assertEqual(snapshot["ca"], effective_context["recursos"]["ca"])
        self.assertEqual(
            snapshot["resumo_imediato"],
            mod.contexto_core.truncate_text(effective_scene.get("resumo_imediato", ""), 1400),
        )
        self.assertFalse(any("transcricao" in str(source) for source in result["fontes"]))

    def test_pending_overlay_is_visible_only_in_sandbox(self):
        before = (ROOT / "runtime/eventos-pendentes.jsonl").read_bytes()
        result = mod.gate_pending_overlay_resume(ROOT)
        after = (ROOT / "runtime/eventos-pendentes.jsonl").read_bytes()
        self.assertTrue(result["somente_sandbox"])
        self.assertEqual(result["ki_efetivo"], result["ki_base"] - 1)
        self.assertEqual(before, after)

    def test_protected_digest_is_stable_for_read_only_operations(self):
        first = mod.protected_digest(ROOT)
        _ = mod.baseline_snapshot(ROOT)
        second = mod.protected_digest(ROOT)
        self.assertEqual(first, second)

    def test_no_raw_rollout_is_tracked_outside_fixture(self):
        result = mod.gate_no_raw_rollout_tracked(ROOT)
        self.assertEqual(result["rollouts_brutos_versionados"], 0)

    def test_final_engineering_contract_exists(self):
        for rel in mod.EXPECTED_ENGINEERING_PATHS:
            self.assertTrue((ROOT / rel).is_file(), rel)
        self.assertTrue((ROOT / "docs/agente/auditoria-final.md").is_file())
        self.assertTrue((ROOT / "baseline/auditoria-final-step-12.md").is_file())
        self.assertFalse((ROOT / "runtime/consolidacao-em-andamento.json").exists())


if __name__ == "__main__":
    unittest.main()
