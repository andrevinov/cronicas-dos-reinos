from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO = Path(__file__).parents[1]


class TelemetryRepositoryContractTest(unittest.TestCase):
    def test_telemetry_artifacts_are_present(self):
        required = [
            "ferramentas/analisar-rollout.py",
            "ferramentas/comparar-rollouts.py",
            "docs/agente/telemetria-rollouts.md",
            "baseline/telemetria-step-11.md",
            "baseline/rollout-2026-08-15.json",
            "baseline/metas-rollout-pos-refatoracao.json",
            "tests/fixtures/rollout-step11-mini.jsonl",
        ]
        for rel in required:
            self.assertTrue((REPO / rel).is_file(), rel)

    def test_baseline_keeps_native_and_manual_measurements_distinct(self):
        baseline = json.loads((REPO / "baseline/rollout-2026-08-15.json").read_text(encoding="utf-8"))
        self.assertEqual(baseline["schema_version"], 2)
        narr = baseline["narration_turns"]
        self.assertEqual(narr["turns"], 13)
        self.assertEqual(narr["inference_events"], 203)
        self.assertEqual(narr["tool_calls"], 306)
        categories = narr["manual_audit"]["tool_categories"]
        self.assertEqual(sum(categories.values()), 306)
        self.assertEqual(narr["manual_audit"]["write_target_touches"], 109)

    def test_targets_keep_core_success_criteria(self):
        targets = json.loads(
            (REPO / "baseline/metas-rollout-pos-refatoracao.json").read_text(encoding="utf-8")
        )
        rules = {rule["id"]: rule for rule in targets["narration"]["rules"]}
        self.assertEqual(rules["raw-input-floor"]["value"], 0.70)
        self.assertEqual(rules["inference-rounds"]["value"], 5.0)
        self.assertEqual(rules["write-targets"]["value"], 2.0)
        self.assertEqual(rules["canonical-writes"]["value"], 0.0)
        self.assertEqual(rules["hot-access-share"]["value"], 0.80)

    def test_agent_router_keeps_telemetry_out_of_live_turn(self):
        agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("docs/agente/telemetria-rollouts.md", agents)
        self.assertIn("analisar-rollout.py", agents)
        self.assertIn("medição é pós-hoc", agents)

    def test_tool_readme_documents_opt_in_local_log(self):
        readme = (REPO / "ferramentas/README.md").read_text(encoding="utf-8")
        self.assertIn("desligada por padrão", readme)
        self.assertIn("--log-local", readme)
        self.assertIn("comparar-rollouts.py", readme)


if __name__ == "__main__":
    unittest.main()
