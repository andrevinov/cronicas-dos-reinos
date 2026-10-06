"""Resultados, métricas e continuação de operações em rollouts isolados."""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from tests import test_analisar_rollout_resultados as fixture

mod = fixture.mod
ROOT = Path(__file__).resolve().parents[1]
WRITE = "poetry run cronica concluir --ticket fixture-estavel"
TERMINAL = "schema_turn_and_session_orchestration: 1\nestado: concluido\n"


def control(turn, identifier, name, arguments):
    return fixture._record({"type": "function_call", "name": name,
        "call_id": identifier, "arguments": json.dumps(arguments),
        "internal_chat_message_metadata_passthrough": {"turn_id": turn}})


class NormalizedOperationResultsTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="resultados-normalizados-")

    def tearDown(self):
        self.temp.cleanup()

    def analyze(self, rows):
        path = Path(self.temp.name) / "rollout.jsonl"
        base = [json.dumps({"type": "event_msg", "payload": {"type": "task_started", "turn_id": "t1"}}),
            fixture._record({"type": "message", "role": "user", "content": [{"type": "input_text", "text": mod.LEGACY_NARRATION_PROMPT}], "internal_chat_message_metadata_passthrough": {"turn_id": "t1"}})]
        path.write_text("\n".join([*base, *rows]) + "\n", encoding="utf-8")
        report = mod.analyze(path)
        outcomes = report["operation_outcomes"]["operations"]
        writes = [item for item in outcomes if item["category"] == "write" and item["state"] != "nao_executada"]
        metrics = report["all_turns"]
        self.assertEqual(metrics["attempted_write_calls"], len(writes))
        self.assertEqual(metrics["successful_write_calls"], sum(item["state"] == "sucesso" for item in writes))
        self.assertEqual(metrics["failed_write_calls"], sum(item["state"] == "falha_operacional" for item in writes))
        self.assertEqual(metrics["attempted_write_calls"], metrics["successful_write_calls"] + metrics["failed_write_calls"] + metrics["unknown_write_calls"])
        self.assertEqual(report["executed_operations"]["summary"]["successful"], sum(item["state"] == "sucesso" for item in outcomes))
        self.assertEqual(sum(item["successful_write_calls"] for item in report["per_narration_turn"]), report["narration_turns"]["successful_write_calls"])
        return report

    def test_valid_yaml_and_structured_json_have_the_same_write_result(self):
        for text in (TERMINAL, '{"estado":"concluido","schema_turn_and_session_orchestration":1}'):
            with self.subTest(text=text):
                report = self.analyze([fixture._call("t1", "w", WRITE), fixture._output("t1", "w", text)])
                self.assertEqual(report["all_turns"]["successful_write_calls"], 1)
                self.assertEqual(report["all_turns"]["write_target_touches"], 2)

    def test_nonzero_timeout_truncation_missing_and_conflicting_results_do_not_pass(self):
        cases = [
            ("Process exited with code 2\n" + TERMINAL, "falha_operacional"),
            ("Command timed out after 10 seconds", "falha_operacional"),
            ("Process exited with code 0\nWarning: truncated output\n" + TERMINAL, "evidencia_insuficiente"),
            ('Process exited with code 0\n{"estado":"erro"}', "falha_operacional"),
            ('{"exit_code":0,"returncode":1,"output":"estado: concluido"}', "falha_operacional"),
            ('exemplo:\n  estado: concluido', "evidencia_insuficiente"),
            ('O manual diz que o sucesso foi garantido.', "evidencia_insuficiente"),
        ]
        for text, state in cases:
            with self.subTest(text=text):
                report = self.analyze([fixture._call("t1", "w", WRITE), fixture._output("t1", "w", text)])
                self.assertEqual(report["operation_outcomes"]["operations"][0]["state"], state)
                self.assertEqual(report["all_turns"]["successful_write_calls"], 0)
        report = self.analyze([fixture._call("t1", "w", WRITE)])
        self.assertEqual(report["all_turns"]["unknown_write_calls"], 1)

    def test_batch_has_one_native_call_and_one_successful_write_without_cost_multiplication(self):
        script = f'const r=await Promise.allSettled([tools.exec_command({{cmd:"rg -n exemplo docs"}}),tools.exec_command({{cmd:{json.dumps(WRITE)}}})]); r.forEach((v,i)=>text({{i,...v}}));'
        output = json.dumps([{"i": 0, "status": "fulfilled", "value": {"exit_code": 0, "output": "texto"}}, {"i": 1, "status": "fulfilled", "value": {"output": TERMINAL}}])
        tokens = json.dumps({"type": "event_msg", "payload": {"type": "token_count", "info": {"last_token_usage": {"input_tokens": 100, "output_tokens": 10}}}})
        report = self.analyze([fixture._call("t1", "batch", script, unified=True), fixture._output("t1", "batch", output), tokens])
        self.assertEqual(report["all_turns"]["tool_calls"], 1)
        self.assertEqual(report["all_turns"]["input_tokens"], 100)
        self.assertEqual(report["all_turns"]["raw_read_calls"], 1)
        self.assertEqual(report["all_turns"]["successful_write_calls"], 1)
        self.assertEqual(report["all_turns"]["write_target_touches"], 2)

    def test_partial_cell_results_survive_wait_in_a_later_turn(self):
        script = f'tools.exec_command({{cmd:"rg -n exemplo docs"}}); tools.exec_command({{cmd:{json.dumps(WRITE)}}});'
        partial = 'Script running with cell ID cell-1\nOutput:\n' + json.dumps({"i": 0, "status": "fulfilled", "value": {"exit_code": 0, "output": "texto"}})
        final = 'Script completed\nOutput:\n' + json.dumps({"i": 1, "status": "fulfilled", "value": {"output": TERMINAL}})
        report = self.analyze([fixture._call("t1", "batch", script, unified=True), fixture._output("t1", "batch", partial),
            control("t2", "wait", "functions.wait", {"cell_id": "cell-1"}), fixture._output("t2", "wait", final)])
        self.assertEqual(report["executed_operations"]["native_calls"], 2)
        self.assertEqual(len(report["operation_outcomes"]["operations"]), 2)
        self.assertEqual(report["all_turns"]["successful_write_calls"], 1)

    def test_subprocess_session_resumes_the_original_operation_and_deduplicates_terminal_results(self):
        pending = json.dumps({"session_id": 42, "output": "fragmento"})
        final = json.dumps({"exit_code": 0, "output": TERMINAL})
        report = self.analyze([fixture._call("t1", "exec", WRITE), fixture._output("t1", "exec", pending),
            control("t1", "resume", "functions.write_stdin", {"session_id": 42}), fixture._output("t1", "resume", final),
            control("t1", "duplicate", "functions.write_stdin", {"session_id": 42}), fixture._output("t1", "duplicate", final)])
        self.assertEqual(report["executed_operations"]["native_calls"], 3)
        self.assertEqual(len(report["operation_outcomes"]["operations"]), 1)
        self.assertEqual(report["all_turns"]["successful_write_calls"], 1)
        self.assertEqual(report["executed_operations"]["summary"]["duplicate_terminal_outputs"], 1)

    def test_nested_session_resumes_with_write_stdin_inside_functions_exec(self):
        script = f'const r=await tools.exec_command({{cmd:{json.dumps(WRITE)}}}); text(r);'
        pending = json.dumps({"session_id": 9, "output": "fragmento"})
        resume = 'const r=await tools.write_stdin({session_id:9,chars:""}); text(r);'
        final = json.dumps({"exit_code": 0, "output": TERMINAL})
        report = self.analyze([fixture._call("t1", "exec", script, unified=True), fixture._output("t1", "exec", pending),
            fixture._call("t1", "resume", resume, unified=True), fixture._output("t1", "resume", final)])
        self.assertEqual(len(report["operation_outcomes"]["operations"]), 1)
        self.assertEqual(report["all_turns"]["successful_write_calls"], 1)

    def test_unfinished_session_and_unknown_resume_do_not_invent_success(self):
        report = self.analyze([fixture._call("t1", "exec", WRITE), fixture._output("t1", "exec", json.dumps({"session_id": 5, "output": TERMINAL})),
            control("t1", "wrong", "functions.write_stdin", {"session_id": 6}), fixture._output("t1", "wrong", TERMINAL)])
        self.assertEqual(report["all_turns"]["unknown_write_calls"], 1)
        self.assertEqual(report["all_turns"]["successful_write_calls"], 0)

    def test_replay_succeeds_without_touching_targets_twice(self):
        replay = TERMINAL + 'commit:\n  resultado: replay_sem_duplicacao\n  exactly_once: true\n  efeito_novo: false\n'
        report = self.analyze([fixture._call("t1", "first", WRITE), fixture._output("t1", "first", TERMINAL),
            fixture._call("t1", "retry", WRITE), fixture._output("t1", "retry", replay)])
        self.assertEqual(report["all_turns"]["successful_write_calls"], 2)
        self.assertEqual(report["all_turns"]["idempotent_write_replays"], 1)
        self.assertEqual(report["all_turns"]["write_target_touches"], 2)

    def test_failed_dice_result_is_successful_execution_without_a_write(self):
        report = self.analyze([fixture._call("t1", "dice", 'poetry run dados ren pericia Furtividade --cd 13 --label teste'),
            fixture._output("t1", "dice", 'Process exited with code 0\nresultado: falha\ntotal: 5\ncd: 13\n')])
        self.assertEqual(report["operation_outcomes"]["operations"][0]["state"], "sucesso")
        self.assertEqual(report["all_turns"]["attempted_write_calls"], 0)

    def test_facade_writer_is_classified_but_help_and_reading_its_name_are_inspections(self):
        command = 'poetry run python ferramentas/world_boundary_resolution.py aplicar lote'
        report = self.analyze([fixture._call('t1', 'world', command), fixture._output('t1', 'world', 'Process exited with code 0\nestado: aplicado\n')])
        self.assertEqual(report['all_turns']['successful_write_calls'], 1)
        self.assertTrue(report['operation_outcomes']['operations'][0]['canonical_write'])
        for inspect in (command + ' --help', "rg -n 'cronica concluir' docs"):
            report = self.analyze([fixture._call('t1', 'inspection', inspect), fixture._output('t1', 'inspection', 'Process exited with code 0\ntexto')])
            self.assertEqual(report['all_turns']['attempted_write_calls'], 0)

    def test_uncertain_inspection_does_not_block_independent_conclusion_but_a_write_does(self):
        spec = importlib.util.spec_from_file_location("resultado_generator", ROOT / 'ferramentas/gerar-avaliacao-sessao.py')
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)
        for command, permitted in [('rg -n erro docs', True), ('poetry run python ferramentas/contexto.py npc exemplo', True), (WRITE, False)]:
            with self.subTest(command=command):
                report = self.analyze([fixture._call("t1", "unknown", command)])
                conclusion = generator._measurement_conclusion(report, {}, {"conclusao_reprodutivel_permitida": True})
                self.assertEqual(conclusion['permitida'], permitted)
                if permitted:
                    self.assertTrue(conclusion['limitacoes'])
                else:
                    self.assertIn('turn_and_session_orchestration', conclusion['bloqueios'][0]['module_ids'])


if __name__ == '__main__':
    unittest.main()
