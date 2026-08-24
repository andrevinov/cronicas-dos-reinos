from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
MODULE = TOOLS / "analisar-rollout.py"
spec = importlib.util.spec_from_file_location("analisar_rollout_task38", MODULE)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def record(type_: str, payload: dict) -> str:
    return json.dumps({"type": type_, "payload": payload}, ensure_ascii=False)


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


class Task38RolloutTelemetryTest(unittest.TestCase):
    def _path(self, rows: list[str]) -> Path:
        self.temp = tempfile.TemporaryDirectory()
        path = Path(self.temp.name) / "task38-rollout.jsonl"
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return path

    def tearDown(self):
        if hasattr(self, "temp"):
            self.temp.cleanup()

    def test_schema3_permanece_compativel_com_extensao_task38(self):
        rows = [
            record("event_msg", {"type": "task_started", "turn_id": "t1"}),
            user("t1", "Ren observa a rua e espera a reação do mundo."),
            call("t1", "p1", "poetry run cronica preparar --cena-id t38"),
            output("t1", "p1", "Process exited with code 0\nfase: preparacao\n"),
            call("t1", "c1", "poetry run cronica concluir --ticket crn1.fixture"),
            output("t1", "c1", "Process exited with code 0\nfase: concluida\n"),
        ]
        report = mod.analyze(self._path(rows))
        self.assertEqual(report["schema_version"], 3)
        self.assertEqual(report["narrative_systems_schema"], 1)
        self.assertEqual(report["narration_turns"]["turns"], 1)
        self.assertEqual(report["narration_turns"]["orchestration_calls"], 2)
        self.assertEqual(report["narration_turns"]["cronica_pair_turns"], 1)
        self.assertEqual(report["narration_turns"]["fraction_turns_with_cronica_pair"], 1.0)

    def test_saida_do_cronica_atribui_sistemas_sem_nova_tool_call(self):
        rows = [
            record("event_msg", {"type": "task_started", "turn_id": "t1"}),
            user("t1", "Ren entra no local e observa o que acontece."),
            call("t1", "p1", "poetry run cronica preparar --cena-id t38 --local porto --acao entrar --tier 1 --periculosidade baixa"),
            output(
                "t1",
                "p1",
                "Process exited with code 0\n"
                "incidente_mundo: {resultado: avaliar_incidente}\n"
                "sidequest_canonica: {id: qsc-111111111111}\n"
                "condicoes_persistentes_ativas: 1\n"
                "torneio_clandestino: {disponivel: true}\n",
            ),
            call("t1", "c1", "poetry run cronica concluir --ticket crn1.fixture"),
            output("t1", "c1", "Process exited with code 0\nfase: concluida\n"),
        ]
        narr = mod.analyze(self._path(rows))["narration_turns"]
        systems = narr["narrative_system_turns"]
        self.assertEqual(systems["world_local_incidents"], 1)
        self.assertEqual(systems["canonical_secret_quests"], 1)
        self.assertEqual(systems["persistent_world_conditions"], 1)
        self.assertEqual(systems["underground_tournament"], 1)
        self.assertEqual(narr["tool_calls"], 2)
        self.assertEqual(narr["orchestration_calls"], 2)

    def test_batch_e_canone_principal_podem_coexistir_na_mesma_chamada(self):
        rows = [
            record("event_msg", {"type": "task_started", "turn_id": "t1"}),
            user("t1", mod.LEGACY_NARRATION_PROMPT),
            call("t1", "b1", "python3 ferramentas/resolver_fronteira.py preparar"),
            output(
                "t1",
                "b1",
                "Process exited with code 0\nlote_id: frn1.aaaaaaaa\n"
                "classificacao: requer_fato_canonico\nevento_canonico_datado: true\n",
            ),
        ]
        narr = mod.analyze(self._path(rows))["narration_turns"]
        systems = narr["narrative_system_turns"]
        self.assertEqual(systems["batch_world_boundary"], 1)
        self.assertEqual(systems["secret_canon"], 1)

    def test_contexto_npc_e_reputacao_recebem_classificacao_atual(self):
        self.assertEqual(
            mod._narrative_systems_from_command("python3 ferramentas/contexto.py npc Nera"),
            {"npc_social_initiative"},
        )
        self.assertEqual(
            mod._access_level_from_command("python3 ferramentas/contexto.py reputacao ren"),
            "L2",
        )

    def test_dados_e_dados_lote_sao_dice_sem_depender_dos_wrappers_legados(self):
        for command in (
            "poetry run dados ren pericia percepção --cd 15",
            "poetry run dados-lote",
        ):
            with self.subTest(command=command):
                raw = json.dumps({"cmd": command})
                self.assertEqual(mod._classify_tool("exec_command", raw), "dice")

    def test_humano_expoe_orquestracao_e_sistemas(self):
        rows = [
            record("event_msg", {"type": "task_started", "turn_id": "t1"}),
            user("t1", mod.LEGACY_NARRATION_PROMPT),
            call("t1", "n1", "python3 ferramentas/contexto.py npc Nera"),
            output("t1", "n1", "Process exited with code 0\nnivel: L2\niniciativa_social: {modo: espontanea}\n"),
        ]
        human = mod._human(mod.analyze(self._path(rows)))
        self.assertIn("SISTEMAS NARRATIVOS", human)
        self.assertIn("npc_social_initiative=1", human)


if __name__ == "__main__":
    unittest.main()
