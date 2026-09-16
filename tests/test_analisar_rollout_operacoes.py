from __future__ import annotations

import hashlib
import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
ANALYZER = ROOT / "ferramentas/analisar-rollout.py"
SPEC = importlib.util.spec_from_file_location("analisar_rollout_operacoes", ANALYZER)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


PREPARE_COMMAND = (
    "poetry run cronica preparar --cena-id teste-operacoes "
    "--sem-oportunidade-sidequest"
)
PREPARE_OUTPUT = """Process exited with code 0
schema_turn_and_session_orchestration: 1
estado: preparado
cobertura_avaliacao_modular:
  schema_avaliacao_cobertura_modular: 1
  recibos:
  - turn_and_session_orchestration|preparar|nao_aplicavel|1
  - scene_world_projection|preparar|nao_aplicavel|1
  - sidequest_authoring|preparar|nao_aplicavel|1
  - sidequest_lifecycle|preparar|nao_aplicavel|1
  - causal_narrative_routing|preparar|nao_aplicavel|1
  - npc_continuity_and_social_behavior|preparar|nao_aplicavel|1
  - context_and_memory|preparar|nao_aplicavel|1
"""


def _record(payload: dict) -> str:
    return json.dumps({"type": "response_item", "payload": payload}, ensure_ascii=False)


def _call(turn: str, call_id: str, command: str, *, name: str = "exec_command") -> str:
    return _record(
        {
            "type": "custom_tool_call" if name == "functions.exec" else "function_call",
            "name": name,
            "call_id": call_id,
            "input" if name == "functions.exec" else "arguments": (
                command if name == "functions.exec" else json.dumps({"cmd": command})
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


def _nested_output(entries: list[dict]) -> str:
    return "Script completed\nOutput:\n" + json.dumps(entries, ensure_ascii=False)


class ExecutedOperationTelemetryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory(prefix="rollout-operacoes-")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _path(self, rows: list[str], name: str = "rollout.jsonl") -> Path:
        preamble = [
            json.dumps(
                {
                    "type": "session_meta",
                    "payload": {
                        "id": "teste-operacoes",
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
        path = Path(self.temp.name) / name
        path.write_text("\n".join([*preamble, *rows]) + "\n", encoding="utf-8")
        return path

    def test_grouped_call_preserves_native_metric_and_correlates_each_operation(self):
        script = (
            "const results=await Promise.allSettled(["
            "tools.exec_command({cmd:\"rg -n exemplo docs\"}),"
            f"tools.exec_command({{cmd:{json.dumps(PREPARE_COMMAND)}}})"
            "]); results.forEach((r,i)=>text({i,...r}));"
        )
        result = _nested_output(
            [
                {"i": 0, "status": "fulfilled", "value": {"exit_code": 0, "output": "texto"}},
                {
                    "i": 1,
                    "status": "fulfilled",
                    "value": {"exit_code": 0, "output": PREPARE_OUTPUT},
                },
            ]
        )
        path = self._path([_call("t1", "grupo", script, name="functions.exec"), _output("t1", "grupo", result)])

        report = mod.analyze(path)
        ledger = report["executed_operations"]
        self.assertEqual(report["all_turns"]["tool_calls"], 1)
        self.assertEqual(ledger["native_calls"], 1)
        self.assertEqual(ledger["grouped_native_calls"], 1)
        self.assertEqual(ledger["summary"]["operations"], 2)
        self.assertEqual(ledger["summary"]["successful"], 2)
        self.assertEqual([item["operation_index"] for item in ledger["operations"]], [0, 1])
        self.assertEqual(
            [item["correlation_status"] for item in ledger["operations"]],
            ["indice_explicito", "indice_explicito"],
        )
        self.assertTrue(all("command" not in item and "output_text" not in item for item in ledger["operations"]))

        turns, _ = mod._scan_observations(path, None)
        operations = turns[0]["calls"][0]["operations"]
        self.assertEqual(operations[0]["module_coverage"]["receipts"], [])
        self.assertEqual(len(operations[1]["module_coverage"]["receipts"]), 7)

    def test_explicit_indexes_win_when_nested_results_arrive_in_reverse_order(self):
        read_command = "rg -n exemplo docs"
        script = (
            f"tools.exec_command({{cmd:{json.dumps(read_command)}}});"
            f"tools.exec_command({{cmd:{json.dumps(PREPARE_COMMAND)}}});"
        )
        result = _nested_output(
            [
                {"i": 1, "status": "fulfilled", "value": {"exit_code": 0, "output": PREPARE_OUTPUT}},
                {"i": 0, "status": "fulfilled", "value": {"exit_code": 0, "output": "leitura"}},
            ]
        )
        path = self._path([_call("t1", "reverso", script, name="functions.exec"), _output("t1", "reverso", result)])

        ledger = mod.analyze(path)["executed_operations"]
        first, second = ledger["operations"]
        self.assertEqual(first["result_index"], 0)
        self.assertEqual(second["result_index"], 1)
        self.assertEqual(first["output_sha256"], hashlib.sha256(b"leitura").hexdigest())
        self.assertEqual(second["output_sha256"], hashlib.sha256(PREPARE_OUTPUT.encode()).hexdigest())

    def test_intermediate_fragment_waits_for_terminal_result(self):
        path = self._path(
            [
                _call("t1", "fragmento", PREPARE_COMMAND),
                _output("t1", "fragmento", "Script running with cell ID celula-1"),
                _output("t1", "fragmento", PREPARE_OUTPUT),
            ]
        )

        ledger = mod.analyze(path)["executed_operations"]
        self.assertEqual(ledger["summary"]["successful"], 1)
        self.assertEqual(ledger["summary"]["intermediate_fragments"], 1)
        self.assertEqual(ledger["operations"][0]["correlation_status"], "chamada_nativa")

    def test_duplicate_terminal_result_does_not_complete_the_next_call(self):
        path = self._path(
            [
                _call("t1", "primeira", PREPARE_COMMAND),
                _output("t1", "primeira", PREPARE_OUTPUT),
                _call("t1", "segunda", PREPARE_COMMAND),
                _output("t1", "primeira", PREPARE_OUTPUT),
            ]
        )

        ledger = mod.analyze(path)["executed_operations"]
        self.assertEqual(ledger["summary"]["successful"], 1)
        self.assertEqual(ledger["summary"]["indeterminate"], 1)
        self.assertEqual(ledger["summary"]["duplicate_terminal_outputs"], 1)
        self.assertTrue(ledger["operations"][0]["output_seen"])
        self.assertFalse(ledger["operations"][1]["output_seen"])

    def test_unknown_call_id_does_not_fall_back_to_a_pending_call(self):
        path = self._path(
            [
                _call("t1", "esperada", PREPARE_COMMAND),
                _output("t1", "desconhecida", PREPARE_OUTPUT),
            ]
        )

        operation = mod.analyze(path)["executed_operations"]["operations"][0]
        self.assertFalse(operation["output_seen"])
        self.assertEqual(operation["result_state"], "indeterminado")
        self.assertEqual(operation["correlation_status"], "pendente")

    def test_read_mentions_do_not_activate_receipts_but_public_context_query_does(self):
        receipt = (
            "cobertura_avaliacao_modular:\n"
            "  schema_avaliacao_cobertura_modular: 1\n"
            "  recibos:\n"
            "  - context_and_memory|consulta|nao_aplicavel|1\n"
        )
        path = self._path(
            [
                _call("t1", "busca", "rg -n cobertura_avaliacao_modular docs"),
                _output("t1", "busca", receipt),
                _call("t1", "contexto", "poetry run python ferramentas/contexto.py regra --termo teste"),
                _output("t1", "contexto", receipt),
            ]
        )

        turns, _ = mod._scan_observations(path, None)
        first, second = mod._turn_operations(turns[0])
        self.assertEqual(first["category"], "read_search")
        self.assertEqual(first["module_coverage"]["receipts"], [])
        self.assertEqual(second["category"], "read_search")
        self.assertEqual(len(second["module_coverage"]["receipts"]), 1)
        self.assertEqual(second["module_coverage"]["receipts"][0]["module_id"], "context_and_memory")


if __name__ == "__main__":
    unittest.main()
