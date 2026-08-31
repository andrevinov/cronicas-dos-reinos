from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
MODULE = TOOLS / "analisar-rollout.py"
spec = importlib.util.spec_from_file_location("analisar_rollout_task47", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def record(type_: str, payload: dict) -> str:
    return json.dumps({"type": type_, "payload": payload}, ensure_ascii=False)


def call(turn: str, call_id: str, cmd: str) -> str:
    return record(
        "response_item",
        {
            "type": "function_call",
            "name": "exec_command",
            "call_id": call_id,
            "arguments": json.dumps({"cmd": cmd}),
            "internal_chat_message_metadata_passthrough": {"turn_id": turn},
        },
    )


def output(turn: str, call_id: str, text: str) -> str:
    return record(
        "response_item",
        {
            "type": "function_call_output",
            "call_id": call_id,
            "output": text,
            "internal_chat_message_metadata_passthrough": {"turn_id": turn},
        },
    )


class Task47RolloutDecisionGateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()

    def _analyze(self, commands: list[str]) -> dict:
        rows: list[str] = []
        for index, command in enumerate(commands, 1):
            turn = f"t{index}"
            call_id = f"p{index}"
            rows.extend(
                [
                    record("event_msg", {"type": "task_started", "turn_id": turn}),
                    call(turn, call_id, command),
                    output(turn, call_id, "Process exited with code 0\nfase: preparacao\n"),
                ]
            )
        path = Path(self.temp.name) / "rollout-task47.jsonl"
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return mod.analyze(path)

    def test_gate_aprova_cobertura_total_positiva_e_negativa(self):
        report = self._analyze(
            [
                "poetry run cronica preparar --cena-id positivo --oportunidade-sidequest "
                "--sidequest-origem-tipo fato_de_cena --sidequest-ancora-tipo problema "
                "--sidequest-ancora 'há um problema causal concreto nesta cena'",
                "poetry run cronica preparar --cena-id negativo --sem-oportunidade-sidequest",
            ]
        )
        gate = report["task47_opportunity_decision_gate"]
        self.assertTrue(gate["ok"])
        self.assertEqual(gate["prepare_calls"], 2)
        self.assertEqual(gate["valid_decisions"], 2)
        self.assertEqual(gate["violations"], 0)
        self.assertEqual(gate["coverage"], 1.0)
        self.assertEqual(gate["decisions"]["oportunidade"], 1)
        self.assertEqual(gate["decisions"]["sem_oportunidade"], 1)

    def test_gate_reprova_rollout_com_preparar_sem_decisao(self):
        report = self._analyze(
            ["poetry run cronica preparar --cena-id maerra-sem-decisao --npc maerra_thandrel"]
        )
        gate = report["task47_opportunity_decision_gate"]
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["prepare_calls"], 1)
        self.assertEqual(gate["valid_decisions"], 0)
        self.assertEqual(gate["violations"], 1)
        self.assertEqual(gate["coverage"], 0.0)
        self.assertEqual(gate["decisions"]["ausente"], 1)

    def test_gate_reprova_comando_com_duas_decisoes(self):
        report = self._analyze(
            [
                "poetry run cronica preparar --cena-id conflito "
                "--oportunidade-sidequest --sem-oportunidade-sidequest"
            ]
        )
        gate = report["task47_opportunity_decision_gate"]
        self.assertFalse(gate["ok"])
        self.assertEqual(gate["decisions"]["conflito"], 1)
        self.assertEqual(gate["violations"], 1)


if __name__ == "__main__":
    unittest.main()
