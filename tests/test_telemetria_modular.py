from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "ferramentas" / "analisar-rollout.py"
SPEC = importlib.util.spec_from_file_location("telemetria_modular", SCRIPT)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


def record(type_: str, payload: dict) -> str:
    return json.dumps({"type": type_, "payload": payload}, ensure_ascii=False)


def with_turn(turn: str, type_: str, **payload: object) -> str:
    return record(
        "response_item",
        {
            "type": type_,
            **payload,
            "internal_chat_message_metadata_passthrough": {"turn_id": turn},
        },
    )


def user(turn: str, text: str) -> str:
    return with_turn(
        turn,
        "message",
        role="user",
        content=[{"type": "input_text", "text": text}],
    )


def assistant(turn: str, text: str) -> str:
    return with_turn(
        turn,
        "message",
        role="assistant",
        content=[{"type": "output_text", "text": text}],
    )


def call(turn: str, call_id: str, command: str) -> str:
    return with_turn(
        turn,
        "function_call",
        name="exec_command",
        call_id=call_id,
        arguments=json.dumps({"cmd": command}),
    )


def output(turn: str, call_id: str, text: str) -> str:
    return with_turn(turn, "function_call_output", call_id=call_id, output=text)


def tokens(input_tokens: int, cached: int, output_tokens: int) -> str:
    return record(
        "event_msg",
        {
            "type": "token_count",
            "info": {
                "last_token_usage": {
                    "input_tokens": input_tokens,
                    "cached_input_tokens": cached,
                    "output_tokens": output_tokens,
                    "reasoning_output_tokens": 0,
                }
            },
        },
    )


class ModularTelemetryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def rollout(self, rows: list[str], name: str = "rollout-modular.jsonl") -> Path:
        path = self.root / name
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        return path

    def base_rows(self, turn: str = "turno-1") -> list[str]:
        return [
            record("session_meta", {"session_id": "session-fixture", "cwd": "/fixture"}),
            record("event_msg", {"type": "task_started", "turn_id": turn}),
        ]

    def test_varias_subcapacidades_contam_um_pai_e_custo_fecha_uma_vez(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", "Ren aceita avançar a investigação."),
            call(
                "turno-1",
                "p1",
                "poetry run cronica preparar --cena-id sq --oportunidade-sidequest "
                "--sidequest-origem-tipo fato_de_cena --sidequest-ancora-tipo problema "
                "--sidequest-ancora 'problema concreto'",
            ),
            output(
                "turno-1",
                "p1",
                "Process exited with code 0\nactive_sidequest_reassessment\n"
                "sidequest_materializada\n",
            ),
            call("turno-1", "c1", "poetry run cronica concluir --ticket crn1.fixture"),
            output(
                "turno-1",
                "c1",
                "Process exited with code 0\ntransactional_sidequest_progress\n"
                "progresso_sidequests_registrado\nsidequest_progression\nquest_rewards\n",
            ),
            tokens(100, 80, 20),
            assistant("turno-1", "A investigação avança.\nRODAPE_CANONICO"),
        ]
        ledger = mod.analyze(self.rollout(rows))["modular_ledger_v2"]
        lifecycle = [
            event for event in ledger["events"] if event["module_id"] == "sidequest_lifecycle"
        ]
        self.assertGreaterEqual(len(lifecycle), 3)
        parent_cost_events = [
            event
            for event in lifecycle
            if event["cost"]["parent_allocation_role"] == "primario"
        ]
        self.assertEqual(len(parent_cost_events), 1)
        self.assertTrue(
            all(event["cost"]["capability_cost_mode"] == "exposicao_apenas" for event in lifecycle)
        )

        parent_total = sum(row["total_tokens"] for row in ledger["module_parent_costs"])
        self.assertEqual(parent_total, 120)
        self.assertTrue(
            all(item["difference"] == 0 for item in ledger["cost_closure"].values())
        )

    def test_regressao_historica_e_extensao_nao_recebem_score_nem_custo(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", mod.LEGACY_NARRATION_PROMPT),
            call(
                "turno-1",
                "x1",
                "python3 ferramentas/migracao_sete_nomes.py status",
            ),
            output(
                "turno-1",
                "x1",
                "Process exited with code 0\nschema_migracao_sete_nomes: 1\n",
            ),
            call(
                "turno-1",
                "x2",
                "python3 ferramentas/torneio_clandestino.py status",
            ),
            output(
                "turno-1",
                "x2",
                "Process exited with code 0\ntorneio_clandestino: ativo\n",
            ),
            assistant("turno-1", "O mundo segue em movimento."),
        ]
        ledger = mod.analyze(self.rollout(rows))["modular_ledger_v2"]
        observations = {item["item_id"]: item for item in ledger["non_module_observations"]}

        self.assertEqual(
            observations["seven_names_migration_regression"]["classification"],
            "regressao_historica",
        )
        self.assertEqual(
            observations["underground_tournament"]["classification"],
            "extensao_campanha",
        )
        self.assertTrue(
            all(
                not item["receives_modular_score"] and not item["receives_parent_cost"]
                for item in observations.values()
            )
        )
        self.assertFalse(
            {"seven_names_migration_regression", "underground_tournament"}
            & {event["module_id"] for event in ledger["events"]}
        )

    def test_gate_neutro_nao_e_confundido_com_efeito(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", "Ren observa a rua."),
            call(
                "turno-1",
                "p1",
                "poetry run cronica preparar --cena-id neutro --sem-oportunidade-sidequest",
            ),
            output("turno-1", "p1", "Process exited with code 0\nfase: preparacao\n"),
            call("turno-1", "c1", "poetry run cronica concluir --ticket crn1.fixture"),
            output("turno-1", "c1", "Process exited with code 0\nfase: concluida\n"),
            assistant("turno-1", "Nada novo se oferece como missão."),
        ]
        report = mod.analyze(self.rollout(rows))
        gate = next(
            event
            for event in report["modular_ledger_v2"]["events"]
            if event["module_id"] == "sidequest_authoring"
            and event["capability_id"] == "opportunity_gate"
        )
        self.assertEqual(gate["eligibility_observed"], "nao")
        self.assertEqual(gate["activation_observed"], "gate_neutro")
        self.assertFalse(gate["effect_observed"])
        self.assertIsNone(gate["materialized_result_observed"])
        self.assertEqual(
            report["narration_turns"]["narrative_system_turns"]["emergent_sidequest_opportunity"],
            0,
        )

    def test_alias_v1_resolve_para_uma_unica_subcapacidade_sem_inventar_elegibilidade(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", mod.LEGACY_NARRATION_PROMPT),
            call(
                "turno-1",
                "p1",
                "poetry run cronica preparar --cena-id ativa --sem-oportunidade-sidequest",
            ),
            output(
                "turno-1",
                "p1",
                "Process exited with code 0\nactive_sidequest_reassessment\n",
            ),
            assistant("turno-1", "A investigação continua."),
        ]
        events = mod.analyze(self.rollout(rows))["modular_ledger_v2"]["events"]
        resolved = [
            event
            for event in events
            if event["module_id"] == "sidequest_lifecycle"
            and event["capability_id"] == "active_reassessment"
        ]
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0]["eligibility_observed"], "indeterminada")
        self.assertIsNone(resolved[0]["adjudication"])

    def test_adjudicacao_preserva_observado_e_registra_correcao(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", mod.LEGACY_NARRATION_PROMPT),
            call("turno-1", "p1", "poetry run cronica preparar --cena-id ativa"),
            output(
                "turno-1",
                "p1",
                "Process exited with code 0\nactive_sidequest_reassessment\n",
            ),
            assistant("turno-1", "A investigação continua."),
        ]
        ledger = mod.analyze(self.rollout(rows))["modular_ledger_v2"]
        observed = next(
            event
            for event in ledger["events"]
            if event["capability_id"] == "active_reassessment"
        )
        corrected = mod.apply_modular_adjudications(
            ledger,
            {
                "corrections": [
                    {
                        "event_id": observed["event_id"],
                        "eligibility": "nao",
                        "activation": "ausente",
                        "effect_observed": False,
                        "reason": "marcador apareceu apenas em texto diagnóstico",
                        "evidence": ["auditoria manual do output"],
                    }
                ]
            },
        )
        event = next(item for item in corrected["events"] if item["event_id"] == observed["event_id"])
        self.assertEqual(event["activation_observed"], "consulta")
        self.assertEqual(event["eligibility_observed"], "indeterminada")
        self.assertEqual(event["adjudication"]["activation"], "ausente")
        self.assertEqual(corrected["corrections"][0]["observed_preserved"]["activation"], "consulta")

    def test_quatro_modulos_novos_possuem_sinais_observaveis(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", "Ren tenta perceber a ameaça."),
            call("turno-1", "r1", "python3 ferramentas/contexto.py regra percepcao"),
            output("turno-1", "r1", "Process exited with code 0\nnivel: L2\n"),
            call("turno-1", "d1", "poetry run dados ren pericia percepcao --cd 15"),
            output("turno-1", "d1", "Process exited with code 0\nresultado: 18\n"),
            call(
                "turno-1",
                "p1",
                "poetry run cronica preparar --cena-id regra --sem-oportunidade-sidequest",
            ),
            output("turno-1", "p1", "Process exited with code 0\nfase: preparacao\n"),
            call("turno-1", "c1", "poetry run cronica concluir --ticket crn1.fixture"),
            output("turno-1", "c1", "Process exited with code 0\nfase: concluida\n"),
            assistant("turno-1", "MECÂNICA — Percepção 18 contra CD 15.\nRODAPE_CANONICO"),
        ]
        ledger = mod.analyze(self.rollout(rows))["modular_ledger_v2"]
        parents = {event["module_id"] for event in ledger["events"]}
        self.assertTrue(
            {
                "context_and_memory",
                "turn_and_session_orchestration",
                "narrative_delivery",
                "rules_and_character_state",
            }.issubset(parents)
        )
        orchestration = next(
            event
            for event in ledger["events"]
            if event["module_id"] == "turn_and_session_orchestration"
            and event["capability_id"] == "transactional_turn"
        )
        self.assertIn("ticket", orchestration["signal_sources"])
        self.assertEqual(orchestration["session_id"], "session-fixture")
        self.assertEqual(orchestration["analysis_unit"], "turno")

    def test_fachadas_rm03_preservam_atribuicao_dos_aliases_v1(self) -> None:
        self.assertIn(
            "emergent_sidequest_authoring",
            mod._narrative_systems_from_command(
                "python3 ferramentas/sidequest_authoring.py check"
            ),
        )
        self.assertIn(
            "active_sidequest_reassessment",
            mod._narrative_systems_from_command(
                "python3 ferramentas/sidequest_lifecycle.py status sqe-fixture"
            ),
        )
        canonical = mod._narrative_systems_from_command(
            "python3 ferramentas/canonical_quest_integration.py oferecer qsc-fixture --npc silva"
        )
        self.assertIn("canonical_secret_quests", canonical)
        self.assertNotIn("canon_bridge", canonical)

    def test_fachadas_rm04_preservam_aliases_e_separam_neutro_de_material(self) -> None:
        scene = mod._narrative_systems_from_command(
            "python3 ferramentas/scene_world_projection.py check"
        )
        self.assertTrue(
            {"world_local_incidents", "persistent_world_conditions"} <= scene
        )
        frontier = mod._narrative_systems_from_command(
            "python3 ferramentas/world_boundary_resolution.py fronteira "
            "--data '18 Eleasis, 1372 DR' --hora 10:00"
        )
        self.assertIn("liveness_boundary", frontier)
        self.assertNotIn("batch_world_boundary", frontier)

        neutral = mod._legacy_activation(
            "batch_world_boundary",
            "resultado_modular: sem_pendencias",
            "output",
        )
        neutral_applied = mod._legacy_activation(
            "batch_world_boundary",
            "resultado_modular: gate_neutro_aplicado",
            "output",
        )
        material = mod._legacy_activation(
            "batch_world_boundary",
            "resultado_modular: lote_aplicado",
            "output",
        )
        routed_empty = mod._legacy_activation(
            "reactive_pressure_routing",
            "resultado_modular: sem_materia",
            "output",
        )
        self.assertEqual(neutral, ("gate_neutro", "resultado_neutro", None, False))
        self.assertEqual(
            neutral_applied,
            ("gate_neutro", "resultado_neutro", None, False),
        )
        self.assertEqual(material, ("efeito", "efeito_observado", "efeito_materializado", True))
        self.assertEqual(routed_empty, ("gate_neutro", "resultado_neutro", None, False))

    def test_rm05_separa_consulta_de_continuidade_e_iniciativa_real(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", mod.LEGACY_NARRATION_PROMPT),
            call("turno-1", "n1", "python3 ferramentas/contexto.py npc silva_elkwood"),
            output(
                "turno-1",
                "n1",
                "Process exited with code 0\ndialogo_relacional:\n  iniciativa_social:\n"
                "personalidade_decisoria:\n  natureza: orientacao\n",
            ),
            assistant("turno-1", "Ren organiza a lembrança antes de agir."),
        ]
        events = mod.analyze(self.rollout(rows))["modular_ledger_v2"]["events"]
        npc_events = [
            event
            for event in events
            if event["module_id"] == "npc_continuity_and_social_behavior"
        ]
        self.assertEqual(
            {event["capability_id"] for event in npc_events},
            {"presence_and_identity", "relationship_memory_reputation"},
        )
        self.assertNotIn("social_initiative", {event["capability_id"] for event in npc_events})

        rows = self.base_rows("turno-check") + [
            user("turno-check", mod.LEGACY_NARRATION_PROMPT),
            call(
                "turno-check",
                "check",
                "python3 ferramentas/npc_continuity_and_social_behavior.py check",
            ),
            output(
                "turno-check",
                "check",
                "Process exited with code 0\nmodule_id: "
                "npc_continuity_and_social_behavior\nok: true\n",
            ),
            assistant("turno-check", "A verificação estrutural terminou."),
        ]
        events = mod.analyze(self.rollout(rows, "rollout-module-check.jsonl"))[
            "modular_ledger_v2"
        ]["events"]
        self.assertNotIn(
            "social_initiative",
            {
                event["capability_id"]
                for event in events
                if event["module_id"] == "npc_continuity_and_social_behavior"
            },
        )

        rows = self.base_rows("turno-2") + [
            user("turno-2", mod.LEGACY_NARRATION_PROMPT),
            call(
                "turno-2",
                "p2",
                "poetry run cronica preparar --cena-id conversa "
                "--sem-oportunidade-sidequest --interlocutor silva_elkwood",
            ),
            output(
                "turno-2",
                "p2",
                "Process exited with code 0\niniciativa_elenco:\n"
                "  selecionada: ini-fixture\n"
                "  itens:\n  - presenca: elenco_cena\n    contexto_npc: presente\n",
            ),
            assistant("turno-2", "Silva parece prestes a abordar um assunto."),
        ]
        events = mod.analyze(self.rollout(rows, "rollout-initiative.jsonl"))[
            "modular_ledger_v2"
        ]["events"]
        social = next(
            event
            for event in events
            if event["module_id"] == "npc_continuity_and_social_behavior"
            and event["capability_id"] == "social_initiative"
        )
        self.assertEqual(social["eligibility_observed"], "sim")
        self.assertEqual(social["activation_observed"], "decisao")
        self.assertEqual(social["detector_version"], "2.2.0")

    def test_rm05_observa_persistencia_social_como_efeito(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", mod.LEGACY_NARRATION_PROMPT),
            call(
                "turno-1",
                "c1",
                "poetry run cronica concluir --ticket fixture",
            ),
            output(
                "turno-1",
                "c1",
                "Process exited with code 0\ncontinuidade_npc:\n"
                "  module_id: npc_continuity_and_social_behavior\n"
                "  fatos_sociais_persistidos: 1\n"
                "  fatos_sociais_com_evidencia: 1\n",
            ),
            assistant("turno-1", "Silva conserva a lembrança desta conversa."),
        ]
        events = mod.analyze(self.rollout(rows, "rollout-social-memory.jsonl"))[
            "modular_ledger_v2"
        ]["events"]
        event = next(
            item
            for item in events
            if item["module_id"] == "npc_continuity_and_social_behavior"
            and item["capability_id"] == "relationship_memory_reputation"
        )
        self.assertEqual(event["activation_observed"], "efeito")
        self.assertEqual(event["observed_result"], "fato_social_persistido")
        self.assertEqual(
            event["materialized_result_observed"], "memoria_social_persistida"
        )
        self.assertTrue(event["effect_observed"])

    def test_visao_legada_e_read_only(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", "Ren observa a rua."),
            call("turno-1", "p1", "poetry run cronica preparar --cena-id antiga"),
            output("turno-1", "p1", "Process exited with code 0\nfase: preparacao\n"),
            assistant("turno-1", "A rua permanece calma."),
        ]
        rollout = self.rollout(rows)
        original = rollout.read_bytes()
        report = mod.analyze(rollout)
        legacy = mod.telemetry_view(report, "legacy-v1")
        self.assertEqual(report["narrative_systems_schema"], 2)
        self.assertIn("modular_ledger_v2", report)
        self.assertEqual(legacy["narrative_systems_schema"], 1)
        self.assertNotIn("modular_ledger_v2", legacy)
        self.assertEqual(
            legacy["narration_turns"]["narrative_system_turns"],
            report["narration_turns"]["narrative_system_turns"],
        )
        self.assertEqual(rollout.read_bytes(), original)
        self.assertFalse(report["measurement"]["writes_during_analysis"])
        self.assertEqual(report["modular_ledger_v2"]["measurement_mode"], "post_hoc_read_only")

    def test_schemas_do_ledger_e_adjudicacao_sao_publicados(self) -> None:
        for filename in ("ledger-modular-v2.schema.json", "adjudicacoes-ledger-v2.schema.json"):
            schema = json.loads(
                (ROOT / "evaluation" / "schemas" / filename).read_text(encoding="utf-8")
            )
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertFalse(schema.get("additionalProperties", True))


if __name__ == "__main__":
    unittest.main()
