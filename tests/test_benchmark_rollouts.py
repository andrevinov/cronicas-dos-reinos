from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
MODULE = ROOT / "ferramentas/benchmark-rollouts.py"
spec = importlib.util.spec_from_file_location("benchmark_rollouts_test", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class BenchmarkRolloutsTest(unittest.TestCase):
    def test_fixture_limpa_aprova_quando_amostra_minima_e_um(self):
        report = mod.benchmark(
            [ROOT / "tests/fixtures/rollout-step11-mini.jsonl"],
            min_turns_override=1,
        )
        self.assertEqual(report["status"], "APROVADO")
        self.assertTrue(report["aprovado"])
        self.assertEqual(report["metricas"]["max_successful_write_calls_per_turn"], 1)
        self.assertEqual(report["metricas"]["max_write_target_touches_per_turn"], 2)
        self.assertEqual(report["metricas"]["schema_discovery_calls"], 0)
        self.assertEqual(report["metricas"]["temporary_turn_file_calls"], 0)
        self.assertTrue(all(rule["ok"] is True for rule in report["regras"]))

    def test_amostra_padrao_exige_cinco_turnos(self):
        report = mod.benchmark([ROOT / "tests/fixtures/rollout-step11-mini.jsonl"])
        self.assertEqual(report["status"], "AMOSTRA INSUFICIENTE")
        self.assertFalse(report["aprovado"])
        self.assertEqual(report["amostra"]["minimo_exigido"], 5)
        self.assertEqual(report["regras"], [])

    def test_regra_final_reprova_writer_extra_e_raw(self):
        targets = {
            "regras": [
                {
                    "id": "writer",
                    "metrica": "max_successful_write_calls_per_turn",
                    "operador": "<=",
                    "valor": 1,
                },
                {
                    "id": "limpo",
                    "metrica": "fraction_turns_l0_l2",
                    "operador": ">=",
                    "valor": 0.8,
                },
            ]
        }
        rules = mod.evaluate(
            {
                "max_successful_write_calls_per_turn": 2,
                "fraction_turns_l0_l2": 0.6,
            },
            targets,
        )
        self.assertEqual([item["ok"] for item in rules], [False, False])

    def test_metrica_ausente_nunca_e_inventada(self):
        rules = mod.evaluate(
            {},
            {
                "regras": [
                    {
                        "id": "x",
                        "metrica": "nao_existe",
                        "operador": "==",
                        "valor": 0,
                    }
                ]
            },
        )
        self.assertIsNone(rules[0]["ok"])


if __name__ == "__main__":
    unittest.main()
