from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
MODULE = TOOLS / "analisar-rollout.py"
spec = importlib.util.spec_from_file_location("analisar_rollout_test", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def record(type_: str, payload: dict) -> str:
    return json.dumps({"type": type_, "payload": payload}, ensure_ascii=False)


class RolloutTelemetryTest(unittest.TestCase):
    def make_rollout(self) -> Path:
        self.temp = tempfile.TemporaryDirectory()
        path = Path(self.temp.name) / "rollout-mini.jsonl"
        rows = [
            record(
                "session_meta",
                {
                    "id": "sessao-mini",
                    "cli_version": "0.test",
                    "cwd": "/repo",
                    "model_provider": "openai",
                    "context_window": 258400,
                },
            ),
            record("event_msg", {"type": "task_started", "turn_id": "t1"}),
            record(
                "response_item",
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": mod.LEGACY_NARRATION_PROMPT}],
                    "internal_chat_message_metadata_passthrough": {"turn_id": "t1"},
                },
            ),
            record(
                "response_item",
                {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": json.dumps({"cmd": "python3 ferramentas/contexto.py status"}),
                    "internal_chat_message_metadata_passthrough": {"turn_id": "t1"},
                },
            ),
            record(
                "response_item",
                {
                    "type": "function_call_output",
                    "output": "nivel: L1\nresultado: ok\n",
                    "internal_chat_message_metadata_passthrough": {"turn_id": "t1"},
                },
            ),
            record(
                "event_msg",
                {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {
                            "input_tokens": 1000,
                            "cached_input_tokens": 800,
                            "output_tokens": 50,
                            "reasoning_output_tokens": 10,
                        }
                    },
                },
            ),
            record(
                "response_item",
                {
                    "type": "custom_tool_call",
                    "name": "exec_command",
                    "input": json.dumps({"cmd": "python3 ferramentas/rolar-lote.py"}),
                    "internal_chat_message_metadata_passthrough": {"turn_id": "t1"},
                },
            ),
            record(
                "response_item",
                {
                    "type": "custom_tool_call_output",
                    "output": "Ataque: 18\n",
                    "internal_chat_message_metadata_passthrough": {"turn_id": "t1"},
                },
            ),
            record(
                "event_msg",
                {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {
                            "input_tokens": 1100,
                            "cached_input_tokens": 900,
                            "output_tokens": 60,
                            "reasoning_output_tokens": 20,
                        }
                    },
                },
            ),
            record(
                "response_item",
                {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": json.dumps(
                        {
                            "cmd": "python3 ferramentas/turno.py registrar <<'JSON'\n{\"narracao\":\"ok\"}\nJSON"
                        }
                    ),
                    "internal_chat_message_metadata_passthrough": {"turn_id": "t1"},
                },
            ),
            record(
                "response_item",
                {
                    "type": "function_call_output",
                    "output": "OK — turno transacional registrado",
                    "internal_chat_message_metadata_passthrough": {"turn_id": "t1"},
                },
            ),
            record(
                "event_msg",
                {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {
                            "input_tokens": 1200,
                            "cached_input_tokens": 1000,
                            "output_tokens": 70,
                            "reasoning_output_tokens": 30,
                        }
                    },
                },
            ),
            record("world_state", {"state": {"agents_md": {"text": "x" * 123}}}),
            record("compacted", {"replacement": "mini"}),
            record("event_msg", {"type": "task_started", "turn_id": "t2"}),
            record(
                "response_item",
                {
                    "type": "message",
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Apenas uma tarefa de manutenção."}],
                    "internal_chat_message_metadata_passthrough": {"turn_id": "t2"},
                },
            ),
            record(
                "event_msg",
                {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {
                            "input_tokens": 500,
                            "cached_input_tokens": 300,
                            "output_tokens": 20,
                            "reasoning_output_tokens": 5,
                        }
                    },
                },
            ),
        ]
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return path

    def tearDown(self):
        if hasattr(self, "temp"):
            self.temp.cleanup()

    def test_native_and_operational_metrics(self):
        report = mod.analyze(self.make_rollout())
        self.assertEqual(report["schema_version"], 2)
        self.assertEqual(report["compactions"], 1)
        self.assertEqual(report["agents_md"]["chars_first"], 123)
        self.assertEqual(report["all_turns"]["turns"], 2)
        narr = report["narration_turns"]
        self.assertEqual(narr["turns"], 1)
        self.assertEqual(narr["inference_events"], 3)
        self.assertEqual(narr["input_tokens"], 3300)
        self.assertEqual(narr["cached_input_tokens"], 2700)
        self.assertEqual(narr["approx_uncached_input_tokens"], 600)
        self.assertEqual(narr["peak_input_tokens"], 1200)
        self.assertEqual(narr["tool_calls"], 3)
        self.assertEqual(narr["tool_categories"]["read_search"], 1)
        self.assertEqual(narr["tool_categories"]["dice"], 1)
        self.assertEqual(narr["tool_categories"]["write"], 1)
        self.assertEqual(narr["write_target_touches"], 2)
        self.assertEqual(narr["canonical_write_target_touches"], 0)
        self.assertEqual(narr["transcript_read_calls"], 0)
        self.assertEqual(narr["max_access_level_by_turn"], {"L1": 1})
        self.assertEqual(narr["fraction_turns_l0_l2"], 1.0)
        self.assertGreater(narr["tool_output_bytes"], 0)

    def test_apply_patch_extracts_target_and_payload(self):
        patch = "*** Begin Patch\n*** Update File: estado/estado-atual.yaml\n@@\n-a\n+b\n*** End Patch"
        self.assertEqual(mod._classify_tool("apply_patch", patch), "write")
        self.assertEqual(mod._infer_write_paths("apply_patch", patch), ["estado/estado-atual.yaml"])
        self.assertGreater(mod._patch_payload_size("apply_patch", patch), 0)
        self.assertTrue(mod._is_canonical_write("estado/estado-atual.yaml"))

    def test_turno_writer_infers_only_two_operational_targets(self):
        raw = json.dumps({"cmd": "python3 ferramentas/turno.py registrar"})
        self.assertEqual(
            mod._infer_write_paths("exec_command", raw),
            ["sessoes/NNN/transcricao.md", "runtime/eventos-pendentes.jsonl"],
        )

    def test_transcript_search_is_detected_as_l4t(self):
        command = (
            "python3 ferramentas/contexto.py buscar 'frase' --historico --transcricoes "
            "--apos L4 --motivo 'preciso da fala literal registrada'"
        )
        self.assertEqual(mod._access_level_from_command(command), "L4T")


if __name__ == "__main__":
    unittest.main()
