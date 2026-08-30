from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
MODULE = TOOLS / "analisar-rollout.py"
spec = importlib.util.spec_from_file_location("analisar_rollout_task46", MODULE)
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


class Task46RolloutTelemetryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp.cleanup()

    def _path(self, rows: list[str]) -> Path:
        path = Path(self.temp.name) / "rollout-task46.jsonl"
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return path

    def test_task46_atribui_sistemas_sem_terceira_chamada(self):
        rows = [
            record("event_msg", {"type": "task_started", "turn_id": "t46"}),
            user("t46", "Ren escuta a proposta e deixa o mundo reagir."),
            call(
                "t46",
                "p1",
                "poetry run cronica preparar --cena-id t46 --oportunidade-sidequest "
                "--sidequest-origem-tipo conversa_npc --sidequest-ancora-tipo problema "
                "--sidequest-ancora 'pedido concreto'",
            ),
            output(
                "t46",
                "p1",
                "Process exited with code 0\nresultado: material_para_planejamento\n"
                "sidequest_emergente_task46: {integrada_ao_ticket: true}\n",
            ),
            call("t46", "c1", "poetry run cronica concluir --ticket crn1.fixture"),
            output(
                "t46",
                "c1",
                "Process exited with code 0\nresultado: sidequest_materializada\n"
                "sistemas_narrativos: [emergent_sidequest_authoring, quest_rewards, "
                "adversarial_integrity, sidequest_progression]\n",
            ),
        ]
        narr = mod.analyze(self._path(rows))["narration_turns"]
        self.assertEqual(narr["orchestration_calls"], 2)
        self.assertEqual(narr["tool_calls"], 2)
        self.assertEqual(narr["cronica_pair_turns"], 1)
        systems = narr["narrative_system_turns"]
        for system in (
            "emergent_sidequest_opportunity",
            "emergent_sidequest_authoring",
            "quest_rewards",
            "adversarial_integrity",
            "sidequest_progression",
        ):
            self.assertEqual(systems[system], 1, system)

    def test_turno_neutro_nao_recebe_atribuicao_task46(self):
        rows = [
            record("event_msg", {"type": "task_started", "turn_id": "neutral"}),
            user("neutral", "Ren observa a rua."),
            call("neutral", "p1", "poetry run cronica preparar --cena-id neutral"),
            output("neutral", "p1", "Process exited with code 0\nfase: preparacao\n"),
            call("neutral", "c1", "poetry run cronica concluir --ticket crn1.fixture"),
            output("neutral", "c1", "Process exited with code 0\nfase: concluida\n"),
        ]
        systems = mod.analyze(self._path(rows))["narration_turns"]["narrative_system_turns"]
        for system in (
            "emergent_sidequest_opportunity",
            "emergent_sidequest_authoring",
            "quest_rewards",
            "adversarial_integrity",
            "sidequest_progression",
        ):
            self.assertEqual(systems[system], 0, system)


if __name__ == "__main__":
    unittest.main()
