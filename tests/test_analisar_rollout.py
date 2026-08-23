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


def call(turn: str, call_id: str, cmd: str, *, custom: bool = False, name: str = "exec_command") -> str:
    payload = {
        "type": "custom_tool_call" if custom else "function_call",
        "name": name,
        "call_id": call_id,
        "internal_chat_message_metadata_passthrough": {"turn_id": turn},
    }
    if custom:
        payload["input"] = json.dumps({"cmd": cmd}) if name != "apply_patch" else cmd
    else:
        payload["arguments"] = json.dumps({"cmd": cmd})
    return record("response_item", payload)


def output(turn: str, call_id: str, text: str, *, custom: bool = False) -> str:
    return record(
        "response_item",
        {
            "type": "custom_tool_call_output" if custom else "function_call_output",
            "call_id": call_id,
            "output": text,
            "internal_chat_message_metadata_passthrough": {"turn_id": turn},
        },
    )


def user(turn: str, text: str) -> str:
    return record(
        "response_item",
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": text}],
            "internal_chat_message_metadata_passthrough": {"turn_id": turn},
        },
    )


class RolloutTelemetryTest(unittest.TestCase):
    def _path(self, rows: list[str], name: str = "rollout-mini.jsonl") -> Path:
        self.temp = tempfile.TemporaryDirectory()
        path = Path(self.temp.name) / name
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return path

    def make_rollout(self) -> Path:
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
            user("t1", mod.LEGACY_NARRATION_PROMPT),
            call("t1", "c1", "python3 ferramentas/contexto.py status"),
            output("t1", "c1", "Process exited with code 0\nFinal output:\nnivel: L1\nresultado: ok\n"),
            record(
                "event_msg",
                {"type": "token_count", "info": {"last_token_usage": {
                    "input_tokens": 1000, "cached_input_tokens": 800,
                    "output_tokens": 50, "reasoning_output_tokens": 10,
                }}},
            ),
            call("t1", "c2", "python3 ferramentas/rolar-lote.py", custom=True),
            output("t1", "c2", "Ataque: 18\n", custom=True),
            record(
                "event_msg",
                {"type": "token_count", "info": {"last_token_usage": {
                    "input_tokens": 1100, "cached_input_tokens": 900,
                    "output_tokens": 60, "reasoning_output_tokens": 20,
                }}},
            ),
            call(
                "t1", "c3",
                "python3 ferramentas/turno.py registrar <<'JSON'\n{\"narracao\":\"ok\"}\nJSON",
            ),
            output("t1", "c3", "OK — turno transacional registrado"),
            record(
                "event_msg",
                {"type": "token_count", "info": {"last_token_usage": {
                    "input_tokens": 1200, "cached_input_tokens": 1000,
                    "output_tokens": 70, "reasoning_output_tokens": 30,
                }}},
            ),
            record("world_state", {"state": {"agents_md": {"text": "x" * 123}}}),
            record("compacted", {"replacement": "mini"}),
            record("event_msg", {"type": "task_started", "turn_id": "t2"}),
            user("t2", "Apenas uma tarefa de manutenção."),
            record(
                "event_msg",
                {"type": "token_count", "info": {"last_token_usage": {
                    "input_tokens": 500, "cached_input_tokens": 300,
                    "output_tokens": 20, "reasoning_output_tokens": 5,
                }}},
            ),
        ]
        return self._path(rows)

    def make_temp_file_rollout(self) -> Path:
        patch_add = (
            "*** Begin Patch\n*** Add File: .turno-temporario.json\n"
            "+{\"narracao\":\"ok\"}\n*** End Patch"
        )
        patch_delete = (
            "*** Begin Patch\n*** Delete File: .turno-temporario.json\n*** End Patch"
        )
        rows = [
            record("event_msg", {"type": "task_started", "turn_id": "t1"}),
            user("t1", mod.LEGACY_NARRATION_PROMPT),
            call("t1", "p1", patch_add, custom=True, name="apply_patch"),
            call(
                "t1", "w1",
                "python3 ferramentas/turno.py registrar --arquivo .turno-temporario.json",
            ),
            call("t1", "p2", patch_delete, custom=True, name="apply_patch"),
        ]
        return self._path(rows, "rollout-temp-turn.jsonl")

    def tearDown(self):
        if hasattr(self, "temp"):
            self.temp.cleanup()

    def test_native_and_operational_metrics(self):
        report = mod.analyze(self.make_rollout())
        self.assertEqual(report["schema_version"], 3)
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
        self.assertEqual(narr["routed_context_calls"], 1)
        self.assertEqual(narr["raw_read_calls"], 0)
        self.assertEqual(narr["schema_discovery_calls"], 0)
        self.assertEqual(narr["attempted_write_calls"], 1)
        self.assertEqual(narr["successful_write_calls"], 1)
        self.assertEqual(narr["failed_write_calls"], 0)
        self.assertEqual(narr["write_target_touches"], 2)
        self.assertEqual(narr["canonical_write_target_touches"], 0)
        self.assertEqual(narr["transcript_read_calls"], 0)
        self.assertEqual(narr["max_access_level_by_turn"], {"L1": 1})
        self.assertEqual(narr["fraction_turns_l0_l2"], 1.0)
        self.assertGreater(narr["tool_output_bytes"], 0)

    def test_l2_plus_raw_is_not_counted_as_clean_l0_l2(self):
        rows = [
            record("event_msg", {"type": "task_started", "turn_id": "t1"}),
            user("t1", mod.LEGACY_NARRATION_PROMPT),
            call("t1", "c1", "python3 ferramentas/contexto.py cena"),
            output("t1", "c1", "Process exited with code 0\nnivel: L2\n"),
            call("t1", "c2", "sed -n '1,120p' estado/estado-atual.yaml"),
            output("t1", "c2", "Process exited with code 0\nFinal output: estado\n"),
        ]
        narr = mod.analyze(self._path(rows, "raw.jsonl"))["narration_turns"]
        self.assertEqual(narr["routed_context_calls"], 1)
        self.assertEqual(narr["raw_read_calls"], 1)
        self.assertEqual(narr["turns_with_raw_read"], 1)
        self.assertEqual(narr["max_access_level_by_turn"], {"L2+RAW": 1})
        self.assertEqual(narr["fraction_turns_l0_l2"], 0.0)
        self.assertIn("L2+RAW", mod._human({
            "source": {"filename": "x", "session_id": "s"},
            "compactions": 0,
            "all_turns": narr,
            "narration_turns": narr,
        }))

    def test_help_and_tool_source_read_are_schema_discovery_not_successful_write(self):
        rows = [
            record("event_msg", {"type": "task_started", "turn_id": "t1"}),
            user("t1", mod.LEGACY_NARRATION_PROMPT),
            call("t1", "h1", "python3 ferramentas/turno.py registrar --help"),
            output("t1", "h1", "Process exited with code 0\nusage: turno.py registrar\n"),
            call("t1", "s1", "sed -n '1,120p' ferramentas/transacoes.py"),
            output("t1", "s1", "Process exited with code 0\nFinal output: def apply_delta\n"),
            call("t1", "w1", "python3 ferramentas/turno.py registrar <<'JSON'\n{}\nJSON"),
            output("t1", "w1", "Process exited with code 1\nFinal output: FALHA DE TURNO\n"),
        ]
        narr = mod.analyze(self._path(rows, "schema.jsonl"))["narration_turns"]
        self.assertEqual(narr["schema_discovery_calls"], 2)
        self.assertEqual(narr["raw_read_calls"], 1)
        self.assertEqual(narr["attempted_write_calls"], 1)
        self.assertEqual(narr["successful_write_calls"], 0)
        self.assertEqual(narr["failed_write_calls"], 1)
        self.assertEqual(narr["write_target_touches"], 0)
        self.assertEqual(narr["attempted_write_target_touches"], 2)

    def test_output_is_correlated_by_call_id_not_only_position(self):
        rows = [
            record("event_msg", {"type": "task_started", "turn_id": "t1"}),
            user("t1", mod.LEGACY_NARRATION_PROMPT),
            call("t1", "w1", "python3 ferramentas/turno.py registrar <<'JSON'\n{}\nJSON"),
            call("t1", "r1", "python3 ferramentas/contexto.py status"),
            output("t1", "r1", "Process exited with code 0\nnivel: L1\n"),
            output("t1", "w1", "Process exited with code 1\nFALHA DE TURNO\n"),
        ]
        narr = mod.analyze(self._path(rows, "call-id.jsonl"))["narration_turns"]
        self.assertEqual(narr["failed_write_calls"], 1)
        self.assertEqual(narr["successful_write_calls"], 0)
        self.assertEqual(narr["max_access_level_by_turn"], {"L1": 1})

    def test_temporary_turn_file_is_explicit_operational_violation(self):
        report = mod.analyze(self.make_temp_file_rollout())
        narr = report["narration_turns"]
        self.assertEqual(narr["violations"]["temporary_turn_file_calls"], 3)
        self.assertEqual(narr["violations"]["turns_with_temporary_turn_file"], 1)
        self.assertEqual(narr["fraction_turns_without_temporary_turn_file"], 0.0)
        self.assertEqual(narr["unknown_write_calls"], 3)
        self.assertIn("VIOLAÇÃO", mod._human(report))
        self.assertIn(".turno-temporario.json", mod._human(report))

    def test_apply_patch_extracts_target_and_payload(self):
        patch = "*** Begin Patch\n*** Update File: estado/estado-atual.yaml\n@@\n-a\n+b\n*** End Patch"
        self.assertEqual(mod._classify_tool("apply_patch", patch), "write")
        self.assertEqual(mod._infer_write_paths("apply_patch", patch), ["estado/estado-atual.yaml"])
        self.assertGreater(mod._patch_payload_size("apply_patch", patch), 0)
        self.assertTrue(mod._is_canonical_write("estado/estado-atual.yaml"))

    def test_turno_help_is_not_inferred_as_write(self):
        raw = json.dumps({"cmd": "python3 ferramentas/turno.py registrar --help"})
        self.assertEqual(mod._classify_tool("exec_command", raw), "read_search")
        self.assertEqual(mod._infer_write_paths("exec_command", raw), [])

    def test_turno_writer_infers_only_two_operational_targets(self):
        raw = json.dumps({"cmd": "python3 ferramentas/turno.py registrar"})
        self.assertEqual(
            mod._infer_write_paths("exec_command", raw),
            ["sessoes/NNN/transcricao.md", "runtime/eventos-pendentes.jsonl"],
        )

    def test_cronica_mutacoes_sao_writers_e_preparar_nao_e(self):
        writers = [
            "python3 ferramentas/cronica.py concluir --ticket abc",
            "python3 ferramentas/cronica.py registrar --ticket abc",
            "python3 ferramentas/cronica.py confirmar --ticket abc",
            "poetry run cronica concluir --ticket abc",
            "cronica registrar --ticket abc",
        ]
        for command in writers:
            with self.subTest(command=command):
                raw = json.dumps({"cmd": command})
                self.assertEqual(mod._classify_tool("exec_command", raw), "write")
        prepare = json.dumps({"cmd": "cronica preparar --cena-id x"})
        self.assertNotEqual(mod._classify_tool("exec_command", prepare), "write")

    def test_cronica_concluir_e_registrar_inferem_alvos_do_turno(self):
        for command in (
            "cronica concluir --ticket abc",
            "python3 ferramentas/cronica.py registrar --ticket abc",
        ):
            with self.subTest(command=command):
                raw = json.dumps({"cmd": command})
                self.assertEqual(
                    mod._infer_write_paths("exec_command", raw),
                    ["sessoes/NNN/transcricao.md", "runtime/eventos-pendentes.jsonl"],
                )

    def test_batch_context_search_is_detected_as_l3(self):
        command = (
            "python3 ferramentas/contexto-buscar-muitos.py 'menino' 'barril seco' "
            "--apos L2 --motivo 'lacunas da mesma decisão'"
        )
        self.assertEqual(mod._access_level_from_command(command), "L3")

    def test_transcript_search_is_detected_as_l4t(self):
        command = (
            "python3 ferramentas/contexto.py buscar 'frase' --historico --transcricoes "
            "--apos L4 --motivo 'preciso da fala literal registrada'"
        )
        self.assertEqual(mod._access_level_from_command(command), "L4T")

    def test_tool_success_understands_exit_codes_and_short_ok(self):
        self.assertTrue(mod._tool_success({}, "Process exited with code 0\n"))
        self.assertFalse(mod._tool_success({}, "Process exited with code 2\n"))
        self.assertTrue(mod._tool_success({}, "OK — concluído"))
        self.assertFalse(mod._tool_success({}, "FALHA DE CONSULTA — nope"))
        self.assertIsNone(mod._tool_success({}, "resultado sem status explícito"))


if __name__ == "__main__":
    unittest.main()
