from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]
ANALYZER = ROOT / "ferramentas/analisar-rollout.py"
SPEC = importlib.util.spec_from_file_location("analisar_rollout_atividades", ANALYZER)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


MODULES = (
    "turn_and_session_orchestration",
    "scene_world_projection",
    "sidequest_authoring",
    "sidequest_lifecycle",
    "causal_narrative_routing",
    "npc_continuity_and_social_behavior",
    "context_and_memory",
)
SCENE_ID = "cena-secreta-atividade-5"
PREPARE_COMMAND = (
    f"poetry run cronica preparar --cena-id {SCENE_ID} "
    "--sem-oportunidade-sidequest"
)


def _output(receipts: list[str], *, exit_code: int = 0) -> str:
    lines = [
        f"Process exited with code {exit_code}",
        "schema_turn_and_session_orchestration: 1",
        "estado: preparado" if exit_code == 0 else "estado: erro",
        "schema_avaliacao_oportunidade_sidequest: 1",
        "module_id: sidequest_authoring",
        "classificacao: verdadeiro_negativo",
        "incluida_na_pontuacao: true",
        "cobertura_avaliacao_modular:",
        "  schema_avaliacao_cobertura_modular: 1",
        "  recibos:",
    ]
    lines.extend(f"  - {receipt}" for receipt in receipts)
    return "\n".join(lines) + "\n"


def _complete_receipts() -> list[str]:
    return [f"{module}|preparar|nao_aplicavel|1" for module in MODULES]


def _record(payload: dict) -> str:
    return json.dumps({"type": "response_item", "payload": payload}, ensure_ascii=False)


def _call(call_id: str, command: str, *, unified: bool = False) -> str:
    payload = {
        "type": "custom_tool_call" if unified else "function_call",
        "name": "functions.exec" if unified else "exec_command",
        "call_id": call_id,
        "internal_chat_message_metadata_passthrough": {"turn_id": "t1"},
    }
    if unified:
        payload["input"] = command
    else:
        payload["arguments"] = json.dumps({"cmd": command})
    return _record(payload)


def _result(call_id: str, output: str) -> str:
    return _record(
        {
            "type": "function_call_output",
            "call_id": call_id,
            "output": output,
            "internal_chat_message_metadata_passthrough": {"turn_id": "t1"},
        }
    )


class ModuleActivityLedgerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = TemporaryDirectory(prefix="rollout-atividades-")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _path(self, rows: list[str], name: str = "rollout.jsonl") -> Path:
        preamble = [
            json.dumps(
                {
                    "type": "session_meta",
                    "payload": {
                        "id": "atividade-5",
                        "cli_version": "fixture",
                        "cwd": "/tmp/fixture",
                        "model_provider": "fixture",
                        "context_window": 1000,
                    },
                }
            ),
            json.dumps(
                {
                    "type": "event_msg",
                    "payload": {"type": "task_started", "turn_id": "t1"},
                }
            ),
        ]
        path = Path(self.temp.name) / name
        path.write_text("\n".join([*preamble, *rows]) + "\n", encoding="utf-8")
        return path

    def test_prepare_creates_seven_traceable_activities_without_raw_object(self):
        path = self._path(
            [_call("prepare", PREPARE_COMMAND), _result("prepare", _output(_complete_receipts()))]
        )

        first = mod.analyze(path)["module_activities"]
        second = mod.analyze(path)["module_activities"]

        self.assertEqual(first, second)
        self.assertEqual(first["schema"], 1)
        self.assertEqual(len(first["activities"]), 7)
        self.assertEqual(first["summary"]["complete"], 7)
        self.assertEqual(first["orphan_receipts"], [])
        self.assertEqual(len({item["atividade_id"] for item in first["activities"]}), 7)
        self.assertEqual(len({item["objeto_ref"] for item in first["activities"]}), 1)
        schema = json.loads(
            (ROOT / "evaluation/schemas/atividades-modulares-rollout.schema.json").read_text(
                encoding="utf-8"
            )
        )
        for activity in first["activities"]:
            self.assertEqual(
                set(activity), set(schema["$defs"]["activity"]["properties"])
            )
            self.assertTrue(activity["operacao_id"])
            self.assertTrue(activity["module_id"])
            self.assertEqual(activity["fase"], "preparar")
            self.assertTrue(activity["objeto_ref"].startswith("cena:sha256:"))
            self.assertEqual(activity["receipt_count"], 1)
            self.assertEqual(activity["receipt_units"], 1)
        self.assertNotIn(SCENE_ID, json.dumps(first, ensure_ascii=False))

    def test_grouping_changes_native_calls_but_preserves_activity_facts(self):
        separate = self._path(
            [
                _call("read", "rg -n exemplo docs"),
                _result("read", "Process exited with code 0\ntexto\n"),
                _call("prepare", PREPARE_COMMAND),
                _result("prepare", _output(_complete_receipts())),
            ],
            "separate.jsonl",
        )
        script = (
            "const r=await Promise.allSettled(["
            "tools.exec_command({cmd:\"rg -n exemplo docs\"}),"
            f"tools.exec_command({{cmd:{json.dumps(PREPARE_COMMAND)}}})"
            "]); r.forEach((value,i)=>text({i,...value}));"
        )
        grouped_output = "Script completed\nOutput:\n" + json.dumps(
            [
                {"i": 0, "status": "fulfilled", "value": {"exit_code": 0, "output": "texto"}},
                {
                    "i": 1,
                    "status": "fulfilled",
                    "value": {"exit_code": 0, "output": _output(_complete_receipts())},
                },
            ],
            ensure_ascii=False,
        )
        grouped = self._path(
            [_call("group", script, unified=True), _result("group", grouped_output)],
            "grouped.jsonl",
        )

        separate_report = mod.analyze(separate)
        grouped_report = mod.analyze(grouped)
        projection = lambda report: sorted(
            (
                item["module_id"],
                item["fase"],
                item["objeto_ref"],
                item["receipt_state"],
                item["applicability"],
            )
            for item in report["module_activities"]["activities"]
        )

        self.assertEqual(projection(separate_report), projection(grouped_report))
        self.assertEqual(separate_report["executed_operations"]["native_calls"], 2)
        self.assertEqual(grouped_report["executed_operations"]["native_calls"], 1)

    def test_duplicate_receipt_is_preserved_and_blocks_the_activity(self):
        receipts = _complete_receipts()
        receipts.append("context_and_memory|preparar|nao_aplicavel|1")
        report = mod.analyze(
            self._path([_call("prepare", PREPARE_COMMAND), _result("prepare", _output(receipts))])
        )
        activity = next(
            item
            for item in report["module_activities"]["activities"]
            if item["module_id"] == "context_and_memory"
        )

        self.assertEqual(activity["receipt_state"], "duplicado")
        self.assertEqual(activity["receipt_count"], 2)
        self.assertEqual(len(set(activity["receipt_occurrence_ids"])), 2)
        gate = report["module_coverage_gates"]["context_and_memory"]
        self.assertEqual(gate["duplicate_receipts"], 1)
        self.assertFalse(gate["coverage_complete"])

    def test_units_above_one_do_not_cover_one_activity(self):
        receipts = [
            receipt.replace("context_and_memory|preparar|nao_aplicavel|1", "context_and_memory|preparar|nao_aplicavel|2")
            for receipt in _complete_receipts()
        ]
        report = mod.analyze(
            self._path([_call("prepare", PREPARE_COMMAND), _result("prepare", _output(receipts))])
        )
        activity = next(
            item
            for item in report["module_activities"]["activities"]
            if item["module_id"] == "context_and_memory"
        )

        self.assertEqual(activity["receipt_state"], "incompleto")
        self.assertEqual(activity["receipt_units"], 2)
        self.assertEqual(
            report["module_coverage_gates"]["context_and_memory"]["incomplete_receipts"],
            1,
        )

    def test_wrong_phase_receipt_is_orphan_and_never_satisfies_activity(self):
        receipts = [
            receipt.replace("context_and_memory|preparar", "context_and_memory|concluir")
            for receipt in _complete_receipts()
        ]
        report = mod.analyze(
            self._path([_call("prepare", PREPARE_COMMAND), _result("prepare", _output(receipts))])
        )
        activity = next(
            item
            for item in report["module_activities"]["activities"]
            if item["module_id"] == "context_and_memory"
        )
        orphan = report["module_activities"]["orphan_receipts"]

        self.assertEqual(activity["receipt_state"], "incompleto")
        self.assertEqual(activity["receipt_count"], 0)
        self.assertEqual(len(orphan), 1)
        schema = json.loads(
            (ROOT / "evaluation/schemas/atividades-modulares-rollout.schema.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            set(orphan[0]), set(schema["$defs"]["orphanReceipt"]["properties"])
        )
        self.assertEqual(orphan[0]["fase"], "concluir")
        self.assertEqual(
            report["module_coverage_gates"]["context_and_memory"]["orphan_receipts"],
            1,
        )

    def test_failed_operation_creates_no_activity_or_receipt_obligation(self):
        failed = _output([], exit_code=2).replace("estado: erro", "erro: preparo recusado")
        report = mod.analyze(
            self._path([_call("prepare", PREPARE_COMMAND), _result("prepare", failed)])
        )

        self.assertEqual(report["operation_outcomes"]["operations"][0]["state"], "falha_operacional")
        self.assertEqual(report["module_activities"]["activities"], [])
        self.assertTrue(
            all(
                gate["activity_units"] == 0
                for gate in report["module_coverage_gates"].values()
            )
        )

    def test_gate_assessments_are_a_projection_of_primary_ledger(self):
        receipts = _complete_receipts()
        receipts.remove("context_and_memory|preparar|nao_aplicavel|1")
        report = mod.analyze(
            self._path([_call("prepare", PREPARE_COMMAND), _result("prepare", _output(receipts))])
        )
        activities = report["module_activities"]["activities"]
        gates = report["module_coverage_gates"]

        for module_id in MODULES:
            module_activities = [item for item in activities if item["module_id"] == module_id]
            self.assertEqual(gates[module_id]["activity_units"], len(module_activities))
            self.assertEqual(
                [item["activity_id"] for item in gates[module_id]["assessments"]],
                [item["atividade_id"] for item in module_activities],
            )
        self.assertEqual(gates["context_and_memory"]["missing_receipts"], 1)


if __name__ == "__main__":
    unittest.main()
