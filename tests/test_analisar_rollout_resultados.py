from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
ANALYZER = ROOT / "ferramentas/analisar-rollout.py"
SPEC = importlib.util.spec_from_file_location("analisar_rollout_resultados", ANALYZER)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


def _record(payload: dict) -> str:
    return json.dumps({"type": "response_item", "payload": payload}, ensure_ascii=False)


def _call(turn: str, call_id: str, command: str, *, unified: bool = False) -> str:
    return _record(
        {
            "type": "custom_tool_call" if unified else "function_call",
            "name": "functions.exec" if unified else "exec_command",
            "call_id": call_id,
            "input" if unified else "arguments": (
                command if unified else json.dumps({"cmd": command})
            ),
            "internal_chat_message_metadata_passthrough": {"turn_id": turn},
        }
    )


def _output(turn: str, call_id: str, text: str) -> str:
    return _record(
        {
            "type": "function_call_output",
            "call_id": call_id,
            "output": text,
            "internal_chat_message_metadata_passthrough": {"turn_id": turn},
        }
    )


class OperationOutcomeClassificationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory(prefix="resultado-operacao-")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _path(self, rows: list[str]) -> Path:
        base = [
            json.dumps(
                {
                    "type": "session_meta",
                    "payload": {
                        "id": "resultado-operacao",
                        "cli_version": "fixture",
                        "cwd": "/tmp/fixture",
                        "model_provider": "fixture",
                        "context_window": 1000,
                    },
                }
            ),
            json.dumps(
                {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "t1"}}
            ),
        ]
        path = Path(self.temp.name) / "rollout.jsonl"
        path.write_text("\n".join([*base, *rows]) + "\n", encoding="utf-8")
        return path

    def test_fulfilled_envelope_does_not_hide_domain_failure_without_exit_code(self):
        script = (
            "const results=await Promise.allSettled(["
            "tools.exec_command({cmd:\"poetry run python ferramentas/"
            "world_boundary_resolution.py aplicar lote\"}),"
            "tools.exec_command({cmd:\"rg -n lote docs\"})]);"
            "results.forEach((r,i)=>text({i,...r}));"
        )
        nested = "Script completed\nOutput:\n" + json.dumps(
            [
                {"status": "fulfilled", "value": {"output": "erro: lote recusado"}},
                {"status": "fulfilled", "value": {"exit_code": 0, "output": "texto"}},
            ]
        )
        path = self._path([_call("t1", "grupo", script, unified=True), _output("t1", "grupo", nested)])

        report = mod.analyze(path)
        outcomes = report["operation_outcomes"]
        self.assertEqual([item["state"] for item in outcomes["operations"]], ["falha_operacional", "sucesso"])
        self.assertEqual(outcomes["summary"]["operational_failures"], 1)
        self.assertEqual(outcomes["operations"][0]["evidence"]["marker"], "erro_terminal")
        self.assertIn("falha=1", mod._human(report))
        self.assertEqual(
            report["module_coverage_gates"]["world_boundary_resolution"]["activity_units"],
            0,
        )

    def test_envelope_success_without_terminal_signal_is_insufficient_evidence(self):
        script = (
            "const r=await tools.exec_command({cmd:\"poetry run cronica preparar "
            "--cena-id x --sem-oportunidade-sidequest\"}); text(r.output);"
        )
        path = self._path(
            [
                _call("t1", "sem-sinal", script, unified=True),
                _output("t1", "sem-sinal", "Script completed\ntexto sem estado terminal"),
            ]
        )

        report = mod.analyze(path)
        outcome = report["operation_outcomes"]["operations"][0]
        self.assertEqual(outcome["state"], "evidencia_insuficiente")
        self.assertEqual(outcome["evidence"]["marker"], "sem_sinal_terminal")
        self.assertEqual(
            report["module_coverage_gates"]["turn_and_session_orchestration"]["activity_units"],
            0,
        )

    def test_error_word_found_by_generic_read_is_not_an_operational_failure(self):
        path = self._path(
            [
                _call("t1", "leitura", "rg -n erro docs"),
                _output("t1", "leitura", "erro: exemplo documentado"),
            ]
        )
        outcome = mod.analyze(path)["operation_outcomes"]["operations"][0]
        self.assertEqual(outcome["state"], "evidencia_insuficiente")
        self.assertNotEqual(outcome["evidence"]["marker"], "erro_terminal")

    def test_missing_result_and_pre_execution_failure_are_distinct(self):
        missing = self._path(
            [_call("t1", "ausente", "poetry run cronica preparar --cena-id x --sem-oportunidade-sidequest")]
        )
        self.assertEqual(
            mod.analyze(missing)["operation_outcomes"]["operations"][0]["state"],
            "resultado_ausente",
        )

        prevented = self._path(
            [
                _call(
                    "t1",
                    "impedida",
                    "const encoded=btoa(payload); const r=await tools.exec_command("
                    "{cmd:\"poetry run cronica concluir --ticket x\"});",
                    unified=True,
                ),
                _output(
                    "t1",
                    "impedida",
                    "Script failed\nScript error:\nReferenceError: btoa is not defined",
                ),
            ]
        )
        outcome = mod.analyze(prevented)["operation_outcomes"]["operations"][0]
        self.assertEqual(outcome["state"], "nao_executada")
        self.assertEqual(outcome["evidence"]["marker"], "falha_antes_da_invocacao")

    def test_receipt_absence_and_confirmed_inapplicability_have_distinct_assessments(self):
        missing_output = (
            "Process exited with code 0\n"
            "schema_turn_and_session_orchestration: 1\nestado: preparado\n"
        )
        not_applicable_output = missing_output + (
            "cobertura_avaliacao_modular:\n"
            "  schema_avaliacao_cobertura_modular: 1\n"
            "  recibos:\n"
            "  - turn_and_session_orchestration|preparar|nao_aplicavel|1\n"
            "  - scene_world_projection|preparar|nao_aplicavel|1\n"
            "  - sidequest_authoring|preparar|nao_aplicavel|1\n"
            "  - sidequest_lifecycle|preparar|nao_aplicavel|1\n"
            "  - causal_narrative_routing|preparar|nao_aplicavel|1\n"
            "  - npc_continuity_and_social_behavior|preparar|nao_aplicavel|1\n"
            "  - context_and_memory|preparar|nao_aplicavel|1\n"
        )
        command = "poetry run cronica preparar --cena-id x --sem-oportunidade-sidequest"
        path = self._path(
            [
                _call("t1", "sem-recibo", command),
                _output("t1", "sem-recibo", missing_output),
                _call("t1", "nao-aplicavel", command),
                _output("t1", "nao-aplicavel", not_applicable_output),
                _call("t1", "indeterminado", command),
                _output(
                    "t1",
                    "indeterminado",
                    not_applicable_output.replace("nao_aplicavel", "indeterminado"),
                ),
            ]
        )

        gate = mod.analyze(path)["module_coverage_gates"]["turn_and_session_orchestration"]
        self.assertEqual(
            [item["assessment_state"] for item in gate["assessments"]],
            [
                "falha_instrumentacao_recibo_ausente",
                "nao_aplicavel",
                "evidencia_insuficiente",
            ],
        )
        self.assertTrue(all(item["operation_id"] for item in gate["assessments"]))
        self.assertTrue(all(item["evidence"]["output_sha256"] for item in gate["assessments"]))

    def test_detector_invariant_failure_is_not_reported_as_operational_failure(self):
        outcome = mod._final_operation_outcome(
            {
                "operation_id": "t1/c1/0",
                "correlation_status": "resultado_ausente",
                "command_executed": True,
                "output_seen": False,
                "output_success": True,
                "output_text": "",
            }
        )
        self.assertEqual(outcome["state"], "erro_detector")
        self.assertEqual(outcome["evidence"]["source"], "invariante_detector")


if __name__ == "__main__":
    unittest.main()
