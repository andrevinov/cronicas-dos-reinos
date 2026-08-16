from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
MODULE = TOOLS / "comparar-rollouts.py"
spec = importlib.util.spec_from_file_location("comparar_rollouts_test", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class CompareRolloutsTest(unittest.TestCase):
    def baseline(self):
        return {
            "source": {"session_id": "old"},
            "narration_turns": {
                "turns": 10,
                "inference_events": 100,
                "tool_calls": 200,
                "input_tokens": 1_000_000,
                "cached_input_tokens": 900_000,
                "approx_uncached_input_tokens": 100_000,
                "output_tokens": 10000,
                "reasoning_output_tokens": 3000,
                "manual_audit": {
                    "tool_categories": {
                        "read_search": 80,
                        "write": 50,
                        "dice": 40,
                        "validation": 20,
                        "other": 10,
                    },
                    "write_target_touches": 80,
                },
            },
        }

    def report(self, turns=5):
        return {
            "source": {"session_id": "new"},
            "narration_turns": {
                "turns": turns,
                "inference_events": turns * 3,
                "tool_calls": turns * 4,
                "input_tokens": turns * 20_000,
                "cached_input_tokens": turns * 18_000,
                "approx_uncached_input_tokens": turns * 2_000,
                "output_tokens": turns * 500,
                "reasoning_output_tokens": turns * 100,
                "tool_output_bytes": turns * 1000,
                "tool_categories": {
                    "read_search": turns,
                    "write": turns,
                    "dice": turns,
                    "other": turns,
                },
                "write_target_touches": turns * 2,
                "canonical_write_target_touches": 0,
                "transcript_read_calls": 0,
                "turns_without_read_search": 0,
                "peak_input_tokens": 25000,
                "max_access_level_by_turn": {"L1": turns},
            },
        }

    def test_normalizes_per_narrative_turn(self):
        result = mod.compare(self.baseline(), [self.report()])
        before = result["baseline"]["narration"]
        after = result["after"]["narration"]
        self.assertEqual(before["input_tokens_per_turn"], 100000)
        self.assertEqual(after["input_tokens_per_turn"], 20000)
        self.assertEqual(after["inference_events_per_turn"], 3)
        self.assertEqual(after["tool_calls_per_turn"], 4)
        self.assertEqual(after["write_target_touches_per_turn"], 2)
        self.assertEqual(result["delta"]["input_tokens_per_turn"]["reduction_fraction"], 0.8)

    def test_aggregates_multiple_post_rollouts(self):
        result = mod.compare(self.baseline(), [self.report(5), self.report(3)])
        self.assertEqual(result["after"]["narration"]["turns"], 8)
        self.assertEqual(result["after"]["narration"]["inference_events_per_turn"], 3)
        self.assertEqual(result["after"]["access_distribution"], {"L1": 8})
        self.assertEqual(result["after"]["narration"]["fraction_turns_l0_l2"], 1.0)

    def test_target_evaluation_uses_reduction_and_after_metrics(self):
        targets = {
            "narration": {
                "rules": [
                    {
                        "id": "raw",
                        "metric": "input_tokens_per_turn",
                        "source": "reduction",
                        "operator": ">=",
                        "value": 0.70,
                    },
                    {
                        "id": "rounds",
                        "metric": "inference_events_per_turn",
                        "source": "after",
                        "operator": "<=",
                        "value": 5,
                    },
                ]
            }
        }
        result = mod.compare(self.baseline(), [self.report()], targets)
        self.assertEqual([item["passed"] for item in result["targets"]], [True, True])

    def test_missing_baseline_metric_is_not_invented(self):
        result = mod.compare(self.baseline(), [self.report()])
        delta = result["delta"]["tool_output_bytes_per_turn"]
        self.assertIsNone(delta["before"])
        self.assertIsNone(delta["reduction_fraction"])


if __name__ == "__main__":
    unittest.main()
