from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "ferramentas/gerar-avaliacao-sessao.py"
SPEC = importlib.util.spec_from_file_location("gerar_avaliacao_agregacao", GENERATOR)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


def _row(
    module_id: str,
    *,
    applicability: str = "aplicavel",
    activation: str = "ativou a contento",
    calibration: float | None = 80.0,
    efficacy: float | None = 70.0,
    reliability: float | None = 60.0,
) -> dict:
    return {
        "modulo": module_id,
        "aplicabilidade_avaliacao": applicability,
        "avaliacao_ativacao": activation,
        "principais_problemas_de_ativacao": (
            "recibo ausente" if applicability == "falha_instrumentacao" else ""
        ),
        "nota_calibracao_0a100": calibration,
        "nota_eficacia_integridade_0a100": efficacy,
        "nota_confiabilidade_proxy_0a100": reliability,
    }


class FailClosedSessionAggregationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.targets = json.loads(mod.DEFAULT_TARGETS.read_text(encoding="utf-8"))
        self.report = {
            "narration_turns": {
                "turns": 1,
                "input_tokens": 50,
                "cached_input_tokens": 0,
                "output_tokens": 10,
                "avg_inference_events_per_turn": 1,
                "avg_tool_calls_per_turn": 2,
                "avg_orchestration_calls_per_turn": 2,
                "fraction_turns_with_cronica_pair": 1.0,
                "fraction_turns_l0_l2": 1.0,
                "fraction_turns_with_raw_read": 0.0,
                "raw_read_calls": 0,
                "schema_discovery_calls": 0,
            },
            "compactions": 0,
        }
        self.ledger = {"interactions": [], "semantic_audits": [], "player_feedback": []}
        self.validity = {"violacoes_criticas": []}
        self.baseline = {"narration_turns": {"turns": 1, "input_tokens": 100}}

    def _card(self, rows: list[dict]) -> dict:
        return mod._scorecard_v2(
            "fixture",
            self.report,
            self.ledger,
            rows,
            self.validity,
            self.baseline,
            self.targets,
            [10.0],
        )

    def test_blocked_components_cannot_change_axes_or_overall_score(self) -> None:
        baseline = [
            _row("blocked", applicability="falha_instrumentacao", calibration=1, efficacy=1, reliability=1),
            _row("valid", calibration=80, efficacy=70, reliability=60),
        ]
        mutated = copy.deepcopy(baseline)
        mutated[0].update(
            {
                "nota_calibracao_0a100": 99,
                "nota_eficacia_integridade_0a100": 99,
                "nota_confiabilidade_proxy_0a100": 99,
            }
        )

        first = self._card(baseline)
        second = self._card(mutated)

        self.assertEqual(first["eixos"], second["eixos"])
        self.assertEqual(first["nota_geral_0a100"], second["nota_geral_0a100"])
        self.assertEqual(first["eixos"]["calibracao"]["nota_0a100"], 80.0)
        self.assertEqual(first["eixos"]["eficacia_integridade"]["nota_0a100"], 70.0)

    def test_scorecard_exposes_blocked_modules_and_valid_denominators(self) -> None:
        card = self._card(
            [
                _row("blocked", applicability="falha_instrumentacao"),
                _row("valid", reliability=None),
            ]
        )
        aggregation = card["agregacao_modular"]
        schema = json.loads(
            (ROOT / "evaluation/schemas/agregacao-scorecard-v2.schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(set(aggregation), set(schema["properties"]))
        self.assertEqual(card["status_avaliacao"], "bloqueada_instrumentacao")
        self.assertEqual(aggregation["status"], "bloqueada_instrumentacao")
        self.assertFalse(aggregation["conclusao_permitida"])
        self.assertTrue(aggregation["nota_parcial_componentes_validos"])
        self.assertEqual(aggregation["modulos_catalogados"], 2)
        self.assertEqual(aggregation["modulos_incluidos"], 1)
        self.assertEqual(aggregation["modulos_nao_avaliaveis"], [])
        self.assertEqual(
            aggregation["modulos_bloqueados"],
            [
                {
                    "module_id": "blocked",
                    "motivo": "falha_instrumentacao",
                    "diagnostico": "recibo ausente",
                }
            ],
        )
        calibration = aggregation["denominadores"]["calibracao"]
        self.assertEqual(calibration["componentes_validos"], 1)
        self.assertEqual(calibration["module_ids"], ["valid"])
        self.assertEqual(calibration["modulos_bloqueados_excluidos"], ["blocked"])
        reliability = aggregation["denominadores"]["confiabilidade"]
        self.assertEqual(reliability["componentes_modulares_validos"], 0)
        self.assertEqual(reliability["componentes_globais_validos"], ["par_cronica_exato"])
        report = mod._report_markdown_v2(
            {"sessao_id": "fixture"}, card, []
        )
        self.assertIn(
            "Desempenho operacional parcial sobre componentes válidos", report
        )
        self.assertIn("Módulos bloqueados excluídos: blocked", report)

    def test_activation_failure_label_also_blocks_inconsistent_legacy_row(self) -> None:
        card = self._card(
            [
                _row(
                    "legacy-blocked",
                    applicability="evidencia_insuficiente",
                    activation="falha de instrumentação",
                    calibration=100,
                ),
                _row("valid", calibration=40),
            ]
        )

        self.assertEqual(card["eixos"]["calibracao"]["nota_0a100"], 40.0)
        self.assertEqual(
            [item["module_id"] for item in card["agregacao_modular"]["modulos_bloqueados"]],
            ["legacy-blocked"],
        )

    def test_unblocked_component_remains_part_of_the_denominator(self) -> None:
        first = self._card([_row("valid", calibration=20)])
        second = self._card([_row("valid", calibration=90)])

        self.assertNotEqual(first["eixos"], second["eixos"])
        self.assertNotEqual(first["nota_geral_0a100"], second["nota_geral_0a100"])
        self.assertEqual(first["agregacao_modular"]["status"], "completa")
        self.assertTrue(first["agregacao_modular"]["conclusao_permitida"])

    def test_non_applicable_residual_component_is_not_a_valid_denominator(self) -> None:
        card = self._card(
            [
                _row("valid", calibration=55),
                _row("na", applicability="nao_aplicavel", calibration=100),
            ]
        )

        self.assertEqual(card["eixos"]["calibracao"]["nota_0a100"], 55.0)
        self.assertEqual(
            card["agregacao_modular"]["modulos_nao_avaliaveis"],
            [{"module_id": "na", "motivo": "nao_aplicavel"}],
        )


if __name__ == "__main__":
    unittest.main()
