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


def modern_output(turn: str, call_id: str, result: dict) -> str:
    return with_turn(
        turn,
        "custom_tool_call_output",
        call_id=call_id,
        output=[{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
    )


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


def at(row: str, timestamp: str) -> str:
    value = json.loads(row)
    value["timestamp"] = timestamp
    return json.dumps(value, ensure_ascii=False)


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

    def test_rm10_correlaciona_regra_alvo_rolagem_recurso_e_tempo(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", "Ren tenta perceber a ameaça."),
            call("turno-1", "r1", "python3 ferramentas/contexto.py regra percepcao"),
            output("turno-1", "r1", "Process exited with code 0\nregra: percepção\n"),
            call("turno-1", "d1", "poetry run dados ren pericia percepcao --cd 15"),
            output("turno-1", "d1", "Process exited with code 0\nresultado: 18\n"),
            call(
                "turno-1",
                "c1",
                "poetry run cronica concluir --ticket crn1.rm10",
            ),
            output(
                "turno-1",
                "c1",
                "Process exited with code 0\n"
                "regras_estado_personagem:\n"
                "  schema_rules_and_character_state: 1\n"
                "  evento_id: mechanics-rm10\n"
                "  estado: commit_validado\n"
                "  correlacao:\n    ticket_id: ticket-rm10\n"
                "    transacao_id: tx-rm10\n    sessao: 21\n"
                "  contrato:\n"
                "    regras: 1\n    obrigacoes: 2\n    obrigacoes_d20: 1\n"
                "    obrigacoes_recurso: 1\n    resolucoes: 2\n"
                "    recursos_aplicados: 1\n    validado_antes_do_writer: true\n"
                "  mutacoes:\n    categorias:\n    - recursos\n    - tempo_atomico\n"
                "    deltas_relevantes: 2\n    tempo_atomico: true\n"
                "  commit:\n    exactly_once: true\n    efeito_novo: true\n"
                "  guardrails:\n    roll_integrity: ok\n"
                "    canonical_consistency: ok\n",
            ),
            tokens(80, 50, 20),
            assistant(
                "turno-1",
                "MECÂNICA — Percepção 18 contra CD 15.\nRODAPE_CANONICO",
            ),
        ]
        report = mod.analyze(self.rollout(rows, "rollout-rm10.jsonl"))
        metrics = report["narration_turns"]["rules_and_character_state"]

        self.assertEqual(metrics["consultas_regra"]["total"], 1)
        self.assertEqual(metrics["redescobertas_schema_cli"], 0)
        self.assertEqual(metrics["rolagens"]["chamadas"], 1)
        self.assertEqual(metrics["rolagens"]["alvo_predefinido"], 1)
        self.assertEqual(metrics["rolagens"]["proporcao_alvo_predefinido"], 1.0)
        self.assertEqual(metrics["contratos"]["recibos_observados"], 1)
        self.assertEqual(metrics["contratos"]["obrigacoes_d20"], 1)
        self.assertEqual(metrics["contratos"]["proporcao_recursos_aplicados"], 1.0)
        self.assertEqual(metrics["contratos"]["integridade_resultado_consequencia"], 1.0)
        self.assertEqual(metrics["estado_personagem_tempo"]["deltas_relevantes"], 2)
        self.assertEqual(
            metrics["estado_personagem_tempo"]["proporcao_deltas_persistentes_validos"],
            1.0,
        )
        self.assertEqual(metrics["estado_personagem_tempo"]["instantes_atomicos"], 1)
        self.assertEqual(
            metrics["estado_personagem_tempo"]["categorias_observadas"],
            {"recursos": 1, "tempo_atomico": 1},
        )

        ledger = report["modular_ledger_v2"]
        events = [
            event
            for event in ledger["events"]
            if event["module_id"] == "rules_and_character_state"
        ]
        self.assertEqual(
            {event["capability_id"] for event in events},
            {"rules_resolution", "roll_execution", "character_time_state"},
        )
        self.assertTrue(any(event["observed_result"] == "rolagem_resolvida" for event in events))
        self.assertTrue(any(event["observed_result"] == "estado_commitado" for event in events))
        parent = next(
            row
            for row in ledger["module_parent_costs"]
            if row["module_id"] == "rules_and_character_state"
        )
        self.assertGreater(parent["total_tokens"], 0)
        self.assertTrue(all(event["detector_version"] == "2.7.0" for event in events))

    def test_rm10_nao_ativa_em_narrativa_pura_ou_delta_generico_de_local(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", "Ren atravessa a praça."),
            call(
                "turno-1",
                "c1",
                "poetry run cronica concluir --ticket crn1.neutro "
                "'{\"deltas\":[{\"alvo\":\"estado\",\"op\":\"set\","
                "\"caminho\":\"localizacao.local_atual\",\"valor\":\"ravens_bluff\"}]}'",
            ),
            output("turno-1", "c1", "Process exited with code 0\nfase: concluida\n"),
            assistant("turno-1", "A praça se abre adiante.\nRODAPE_CANONICO"),
        ]
        report = mod.analyze(self.rollout(rows, "rollout-rm10-neutro.jsonl"))
        modules = {
            event["module_id"] for event in report["modular_ledger_v2"]["events"]
        }

        self.assertNotIn("rules_and_character_state", modules)
        metrics = report["narration_turns"]["rules_and_character_state"]
        self.assertEqual(metrics["rolagens"]["chamadas"], 0)
        self.assertEqual(metrics["estado_personagem_tempo"]["deltas_relevantes"], 0)

    def test_rm10_redescoberta_de_cli_nao_conta_como_rolagem(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", mod.LEGACY_NARRATION_PROMPT),
            call("turno-1", "h1", "poetry run dados --help"),
            output("turno-1", "h1", "Process exited with code 0\nusage: dados\n"),
            assistant("turno-1", "Ren ainda avalia a situação.\nRODAPE_CANONICO"),
        ]
        report = mod.analyze(self.rollout(rows, "rollout-rm10-help.jsonl"))
        metrics = report["narration_turns"]["rules_and_character_state"]
        event = next(
            event
            for event in report["modular_ledger_v2"]["events"]
            if event["module_id"] == "rules_and_character_state"
        )

        self.assertEqual(metrics["redescobertas_schema_cli"], 1)
        self.assertEqual(metrics["rolagens"]["chamadas"], 0)
        self.assertEqual(event["capability_id"], "rules_resolution")
        self.assertEqual(event["observed_result"], "redescoberta_assinatura")
        self.assertFalse(event["effect_observed"])

    def test_rm10_guarda_bloqueio_e_correcao_do_jogador_sem_compensar(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", mod.LEGACY_NARRATION_PROMPT),
            call(
                "turno-1",
                "c1",
                "poetry run cronica concluir --ticket crn1.rm10",
            ),
            output(
                "turno-1",
                "c1",
                "Process exited with code 1\nresultado mecânico diverge da primitiva\n",
            ),
            assistant("turno-1", "A resolução foi interrompida."),
            record("event_msg", {"type": "task_started", "turn_id": "turno-2"}),
            user("turno-2", "O resultado da rolagem foi alterado; precisa de correção."),
            assistant("turno-2", "Entendido."),
            record("event_msg", {"type": "task_started", "turn_id": "turno-3"}),
            user("turno-3", "O resultado da rolagem foi 18 e Ren segue adiante."),
            assistant("turno-3", "Entendido."),
        ]
        report = mod.analyze(self.rollout(rows, "rollout-rm10-guardrail.jsonl"))
        metrics = report["all_turns"]["rules_and_character_state"]
        event = next(
            event
            for event in report["modular_ledger_v2"]["events"]
            if event["module_id"] == "rules_and_character_state"
        )

        self.assertEqual(metrics["guardrails"]["bloqueios_observados"], 1)
        self.assertTrue(metrics["guardrails"]["nao_compensaveis"])
        self.assertEqual(metrics["correcoes_mecanicas_jogador"], 1)
        self.assertEqual(event["observed_result"], "guardrail_bloqueou")
        self.assertFalse(event["effect_observed"])

    def test_rm09_correlaciona_resposta_final_sem_julgar_prosa(self) -> None:
        rows = self.base_rows() + [
            at(user("turno-1", "Ren abre a porta."), "2026-09-14T12:00:00Z"),
            call(
                "turno-1",
                "p1",
                "poetry run cronica preparar --cena-id rm09 --sem-oportunidade-sidequest",
            ),
            output("turno-1", "p1", "Process exited with code 0\nfase: preparacao\n"),
            call("turno-1", "c1", "poetry run cronica concluir --ticket crn1.rm09"),
            output(
                "turno-1",
                "c1",
                "Process exited with code 0\nfase: concluida\n"
                "entrega_narrativa:\n"
                "  schema_narrative_delivery: 1\n"
                "  entrega_id: delivery-rm09\n"
                "  estado: prosa_registrada\n"
                "  correlacao:\n    ticket_id: ticket-rm09\n"
                "    transacao_id: tx-rm09\n    sessao: 21\n"
                "  classe_turno: comum\n"
                "  estrutura:\n    caracteres: 28\n    palavras: 5\n"
                "    paragrafos: 1\n    linhas_mecanica: 0\n"
                "  rodape:\n    emitido: true\n"
                "  avaliacao_semantica: nao_realizada\n",
            ),
            at(
                with_turn(
                    "turno-1",
                    "message",
                    role="assistant",
                    channel="commentary",
                    content=[{"type": "output_text", "text": "Concluindo o turno."}],
                ),
                "2026-09-14T12:00:03Z",
            ),
            at(
                with_turn(
                    "turno-1",
                    "message",
                    role="assistant",
                    channel="final",
                    content=[
                        {
                            "type": "output_text",
                            "text": "A porta se abre.\nRODAPE_CANONICO — fixture",
                        }
                    ],
                ),
                "2026-09-14T12:00:05Z",
            ),
        ]
        report = mod.analyze(self.rollout(rows, "rollout-rm09-delivery.jsonl"))
        metrics = report["narration_turns"]["narrative_delivery"]

        self.assertEqual(metrics["respostas_observadas"], 1)
        self.assertEqual(metrics["recibos_observados"], 1)
        self.assertEqual(metrics["entregas_correlacionadas"], 1)
        self.assertEqual(metrics["rodapes_em_ultima_linha"], 1)
        self.assertEqual(metrics["latencia"]["media_segundos"], 5.0)
        self.assertIsNone(metrics["nota_literaria_automatica"])
        self.assertEqual(metrics["auditoria_semantica"]["estado"], "nao_realizada")

        events = report["modular_ledger_v2"]["events"]
        closure = next(
            event for event in events
            if event["module_id"] == "narrative_delivery"
            and event["capability_id"] == "visible_closure"
        )
        density = next(
            event for event in events
            if event["module_id"] == "narrative_delivery"
            and event["capability_id"] == "narrative_density"
        )
        self.assertEqual(closure["observed_result"], "entrega_correlacionada")
        self.assertEqual(closure["signal_sources"], ["output", "resposta"])
        self.assertEqual(density["observed_result"], "densidade_nao_avaliada")
        self.assertIsNone(density["effect_observed"])

    def test_rm09_comentario_sem_final_nao_vira_entrega_narrativa(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", mod.LEGACY_NARRATION_PROMPT),
            with_turn(
                "turno-1",
                "message",
                role="assistant",
                channel="commentary",
                content=[{"type": "output_text", "text": "Ainda processando o turno."}],
            ),
        ]
        report = mod.analyze(self.rollout(rows, "rollout-rm09-interrompido.jsonl"))
        metrics = report["narration_turns"]["narrative_delivery"]

        self.assertEqual(metrics["respostas_observadas"], 0)
        closure = next(
            event
            for event in report["modular_ledger_v2"]["events"]
            if event["module_id"] == "narrative_delivery"
            and event["capability_id"] == "visible_closure"
        )
        self.assertEqual(closure["observed_result"], "resposta_ausente")
        self.assertFalse(closure["effect_observed"])

    def test_rm09_feedback_e_auditoria_nao_compensam_guardrail(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", mod.LEGACY_NARRATION_PROMPT),
            assistant("turno-1", "A cena avança.\nRODAPE_CANONICO — fixture"),
        ]
        ledger = mod.analyze(
            self.rollout(rows, "rollout-rm09-human.jsonl")
        )["modular_ledger_v2"]
        event = next(
            item for item in ledger["events"]
            if item["module_id"] == "narrative_delivery"
            and item["capability_id"] == "visible_closure"
        )
        self.assertEqual(ledger["semantic_audits"], [])
        self.assertEqual(ledger["player_feedback"], [])

        adjudicated = mod.apply_modular_adjudications(
            ledger,
            {
                "corrections": [],
                "semantic_audits": [
                    {
                        "event_id": event["event_id"],
                        "evaluator": "auditor-fixture",
                        "dimensions": {
                            "progressao_jogavel": "adequado",
                            "densidade_proporcional": "adequado",
                            "voz_e_dialogo": "indeterminado",
                            "camadas_de_conhecimento": "adequado",
                            "conclusao_aberta": "adequado",
                        },
                        "guardrails": {
                            "player_agency": "violado",
                            "knowledge_secrecy": "ok",
                            "roll_integrity": "ok",
                        },
                        "evidence": ["ação de Ren inferida indevidamente"],
                    }
                ],
                "player_feedback": [
                    {
                        "event_id": event["event_id"],
                        "ratings": {
                            "ritmo": 5,
                            "naturalidade": 5,
                            "profundidade": None,
                            "agencia_percebida": 2,
                        },
                        "comment": "Boa forma, mas tirou minha decisão.",
                    }
                ],
            },
        )

        audit = adjudicated["semantic_audits"][0]
        feedback = adjudicated["player_feedback"][0]
        self.assertIsNone(audit["automatic_literary_score"])
        self.assertFalse(audit["guardrails_compensable"])
        self.assertEqual(audit["guardrails"]["player_agency"], "violado")
        self.assertEqual(feedback["aggregation_role"], "percepcao_com_peso_limitado")
        self.assertTrue(feedback["guardrails_unchanged"])

    def test_rm08_mede_correlacao_duracao_idempotencia_e_classe_de_custo(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", mod.LEGACY_NARRATION_PROMPT),
            call(
                "turno-1",
                "p1",
                "poetry run cronica preparar --cena-id rm08 --sem-oportunidade-sidequest",
            ),
            output(
                "turno-1",
                "p1",
                "Script completed\nWall time 0.2 seconds\nProcess exited with code 0\nOutput:\n"
                "fase: preparacao\nticket_id: ticket-rm08\n"
                "orquestracao:\n"
                "  schema_turn_and_session_orchestration: 1\n"
                "  operacao: preparar\n  estado: preparado\n"
                "  correlacao:\n    ticket_id: ticket-rm08\n",
            ),
            call("turno-1", "d1", "poetry run dados ren pericia percepcao --cd 14"),
            output("turno-1", "d1", "Process exited with code 0\nresultado: 18\n"),
            call("turno-1", "c1", "poetry run cronica concluir --ticket crn1.fixture"),
            output(
                "turno-1",
                "c1",
                "Script completed\nWall time 0.4 seconds\nProcess exited with code 0\nOutput:\n"
                "fase: concluida\nticket_id: ticket-rm08\n"
                "orquestracao:\n"
                "  schema_turn_and_session_orchestration: 1\n"
                "  operacao: concluir\n  estado: concluido\n"
                "  correlacao:\n    ticket_id: ticket-rm08\n"
                "  commit:\n"
                "    resultado: commit_exatamente_uma_vez\n"
                "    exactly_once: true\n    efeito_novo: true\n"
                "    duplicado: false\n    incompleto: false\n",
            ),
            tokens(80, 60, 20),
            assistant("turno-1", "A percepção resolve a incerteza.\nRODAPE_CANONICO"),
        ]
        report = mod.analyze(self.rollout(rows, "rollout-rm08-receipts.jsonl"))
        metrics = report["narration_turns"]["turn_and_session_orchestration"]

        self.assertEqual(metrics["calls_by_class"]["turno_primario"], 2)
        self.assertEqual(metrics["exact_prepare_conclude_pairs"], 1)
        self.assertEqual(metrics["successful_exact_pairs"], 1)
        self.assertEqual(metrics["correlated_pairs"], 1)
        self.assertEqual(metrics["mismatched_pairs"], 0)
        self.assertEqual(metrics["duration_by_phase"]["preparar"]["media_segundos"], 0.2)
        self.assertEqual(metrics["duration_by_phase"]["concluir"]["media_segundos"], 0.4)

        ledger = report["modular_ledger_v2"]
        events = [
            event for event in ledger["events"]
            if event["module_id"] == "turn_and_session_orchestration"
        ]
        transactional = next(
            event for event in events if event["capability_id"] == "transactional_turn"
        )
        commit = next(
            event for event in events if event["capability_id"] == "idempotent_commit"
        )
        self.assertEqual(transactional["observed_result"], "ciclo_concluido")
        self.assertEqual(commit["observed_result"], "commit_exatamente_uma_vez")
        self.assertTrue(all(event["cost"]["attribution_class"] == "controle" for event in events))
        parent = next(
            row for row in ledger["module_parent_costs"]
            if row["module_id"] == "turn_and_session_orchestration"
        )
        self.assertEqual(parent["cost_class"], "controle")
        by_class = {row["cost_class"]: row for row in ledger["cost_class_totals"]}
        self.assertEqual(
            by_class["controle"]["total_tokens"] + by_class["dominio"]["total_tokens"],
            100,
        )

    def test_rm08_falha_de_ticket_nao_e_atribuida_a_sidequest_por_aproximacao(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", mod.LEGACY_NARRATION_PROMPT),
            call("turno-1", "c1", "poetry run cronica concluir --ticket crn1.stale"),
            output(
                "turno-1",
                "c1",
                "Process exited with code 1\n"
                "transactional_sidequest_progress\n"
                "FALHA CRONICA — preparação do ticket ficou obsoleta; execute cronica preparar novamente\n",
            ),
            tokens(20, 10, 5),
        ]
        report = mod.analyze(self.rollout(rows, "rollout-rm08-stale.jsonl"))
        metrics = report["narration_turns"]["turn_and_session_orchestration"]
        parents = {
            event["module_id"] for event in report["modular_ledger_v2"]["events"]
        }

        self.assertEqual(metrics["tickets"]["obsoletos"], 1)
        self.assertNotIn("sidequest_lifecycle", parents)
        orchestration = next(
            event for event in report["modular_ledger_v2"]["events"]
            if event["module_id"] == "turn_and_session_orchestration"
            and event["capability_id"] == "transactional_turn"
        )
        self.assertEqual(orchestration["observed_result"], "ticket_obsoleto")

    def test_rm08_lifecycle_tem_classe_propria_sem_ciclo_de_turno_falso(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", mod.LEGACY_NARRATION_PROMPT),
            call("turno-1", "s1", "poetry run cronica sessao recuperar"),
            output(
                "turno-1",
                "s1",
                "Process exited with code 0\nWall time 0.7 seconds\n"
                "fase: recuperada\nsessao: 21\n"
                "orquestracao:\n"
                "  schema_turn_and_session_orchestration: 1\n"
                "  unidade: sessao\n  operacao: recuperar\n  estado: recuperado\n"
                "  sessao: 21\n  recuperada: true\n"
                "  ordem_canonica_preservada: true\n",
            ),
            tokens(20, 10, 5),
            assistant("turno-1", "A sessão foi recuperada antes de qualquer nova narração."),
        ]
        report = mod.analyze(self.rollout(rows, "rollout-rm08-session.jsonl"))
        metrics = report["all_turns"]["turn_and_session_orchestration"]
        events = [
            event for event in report["modular_ledger_v2"]["events"]
            if event["module_id"] == "turn_and_session_orchestration"
        ]

        self.assertEqual(metrics["calls_by_class"], {"lifecycle_sessao": 1})
        self.assertEqual(metrics["session_lifecycle"]["operations"], {"recuperar": 1})
        self.assertEqual(metrics["session_lifecycle"]["fraction_successful"], 1.0)
        self.assertEqual(metrics["duration_by_phase"]["sessao:recuperar"]["media_segundos"], 0.7)
        self.assertEqual(
            {event["capability_id"] for event in events},
            {"session_lifecycle"},
        )

    def test_rm08_desembrulha_output_moderno_e_preserva_duracao(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", mod.LEGACY_NARRATION_PROMPT),
            call("turno-1", "s1", "poetry run cronica sessao status"),
            modern_output(
                "turno-1",
                "s1",
                {
                    "exit_code": 0,
                    "wall_time_seconds": 0.35,
                    "output": (
                        "fase: status\n"
                        "orquestracao:\n"
                        "  schema_turn_and_session_orchestration: 1\n"
                        "  unidade: sessao\n"
                        "  operacao: status\n"
                        "  estado: observado\n"
                    ),
                },
            ),
            tokens(20, 10, 5),
        ]
        report = mod.analyze(self.rollout(rows, "rollout-rm08-modern.jsonl"))
        metrics = report["all_turns"]["turn_and_session_orchestration"]

        self.assertEqual(metrics["session_lifecycle"]["successful"], {"status": 1})
        self.assertEqual(
            metrics["duration_by_phase"]["sessao:status"]["media_segundos"],
            0.35,
        )
        self.assertEqual(metrics["session_lifecycle"]["receipts_observed"], 1)

    def test_rm07_registra_l0_quando_o_turno_nao_precisa_ler(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", mod.LEGACY_NARRATION_PROMPT),
            call(
                "turno-1",
                "p1",
                "poetry run cronica preparar --cena-id l0 --sem-oportunidade-sidequest",
            ),
            output("turno-1", "p1", "Process exited with code 0\nfase: preparacao\n"),
            call("turno-1", "c1", "poetry run cronica concluir --ticket crn1.l0"),
            output("turno-1", "c1", "Process exited with code 0\nfase: concluida\n"),
            tokens(40, 30, 10),
            assistant("turno-1", "A cena continua sem exigir nova consulta."),
        ]
        events = mod.analyze(
            self.rollout(rows, "rollout-context-l0.jsonl")
        )["modular_ledger_v2"]["events"]
        access = next(
            event for event in events
            if event["module_id"] == "context_and_memory"
            and event["capability_id"] == "routed_context_access"
        )
        self.assertEqual(access["observed_result"], "contexto_l0_suficiente")
        self.assertEqual(access["observable_evidence"], ["turn:l0_context_sufficient"])
        self.assertEqual(access["detector_version"], "2.7.0")

    def test_rm07_detecta_aprofundamento_raw_e_leitura_redundante(self) -> None:
        rows = [record("session_meta", {"session_id": "session-fixture", "cwd": "/fixture"})]
        scenarios = (
            (
                "profundo",
                "python3 ferramentas/contexto.py buscar frase --historico --transcricoes "
                "--apos L4 --motivo 'O histórico estruturado não contém a fala literal necessária.'",
                "nivel: L4T\ncontexto_modular:\n  schema_context_and_memory: 2\n",
                "aprofundamento_justificado",
            ),
            (
                "raw",
                "sed -n '1,80p' sessoes/021/transcricao.md",
                "trecho bruto",
                "acesso_cru_sem_justificativa",
            ),
        )
        for turn, command, result, _ in scenarios:
            rows.extend(
                [
                    record("event_msg", {"type": "task_started", "turn_id": turn}),
                    user(turn, mod.LEGACY_NARRATION_PROMPT),
                    call(turn, turn, command),
                    output(turn, turn, "Process exited with code 0\n" + result),
                    assistant(turn, "A continuidade é preservada."),
                ]
            )
        rows.extend(
            [
                record("event_msg", {"type": "task_started", "turn_id": "repetido"}),
                user("repetido", mod.LEGACY_NARRATION_PROMPT),
                call("repetido", "r1", "python3 ferramentas/contexto.py npc silva"),
                output("repetido", "r1", "Process exited with code 0\nnivel: L2\n"),
                call("repetido", "r2", "python3 ferramentas/contexto.py npc silva"),
                output("repetido", "r2", "Process exited with code 0\nnivel: L2\n"),
                assistant("repetido", "Silva mantém a mesma postura."),
            ]
        )
        events = mod.analyze(
            self.rollout(rows, "rollout-context-depth.jsonl")
        )["modular_ledger_v2"]["events"]
        results = {
            event["turn_id"]: event["observed_result"]
            for event in events
            if event["module_id"] == "context_and_memory"
            and event["capability_id"] == "routed_context_access"
        }
        self.assertEqual(
            results,
            {
                "profundo": "aprofundamento_justificado",
                "raw": "acesso_cru_sem_justificativa",
                "repetido": "leitura_redundante",
            },
        )

    def test_rm07_detecta_contexto_e_memoria_de_cena_obsoletos(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", mod.LEGACY_NARRATION_PROMPT),
            call("turno-1", "r1", "python3 ferramentas/contexto.py cena"),
            output(
                "turno-1",
                "r1",
                "Process exited with code 1\npreparação de elenco obsoleta\n",
            ),
            assistant("turno-1", "A preparação precisa ser refeita."),
        ]
        events = mod.analyze(
            self.rollout(rows, "rollout-context-stale.jsonl")
        )["modular_ledger_v2"]["events"]
        by_capability = {
            event["capability_id"]: event["observed_result"]
            for event in events
            if event["module_id"] == "context_and_memory"
        }

        self.assertEqual(
            by_capability["routed_context_access"],
            "contexto_obsoleto",
        )
        self.assertEqual(
            by_capability["scene_and_durable_memory"],
            "memoria_de_cena_obsoleta",
        )

    def test_rm07_memoria_commit_e_camadas_tem_custo_parental_unico(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", mod.LEGACY_NARRATION_PROMPT),
            call(
                "turno-1",
                "m1",
                "poetry run cronica concluir --ticket crn1.memoria '{\"memoria\": {\"versao\": 1}}'",
            ),
            output(
                "turno-1",
                "m1",
                "Process exited with code 0\n"
                "memoria_contexto:\n"
                "  schema_context_and_memory: 2\n"
                "  resultado_modular: memoria_duravel_persistida\n"
                "  evento_modular: efeito_material\n"
                "  camadas_destino: [memoria_relacional]\n",
            ),
            tokens(60, 40, 20),
            assistant("turno-1", "O rumor permanece atribuído a quem o recebeu."),
        ]
        ledger = mod.analyze(
            self.rollout(rows, "rollout-context-memory-effect.jsonl")
        )["modular_ledger_v2"]
        events = [
            event for event in ledger["events"]
            if event["module_id"] == "context_and_memory"
        ]
        memory = next(
            event for event in events
            if event["capability_id"] == "scene_and_durable_memory"
        )
        layers = next(
            event for event in events
            if event["capability_id"] == "knowledge_layer_separation"
        )

        self.assertEqual(memory["activation_observed"], "efeito")
        self.assertEqual(memory["materialized_result_observed"], "memoria_persistida")
        self.assertEqual(layers["observed_result"], "camadas_preservadas")
        attributed = [
            event["cost"]["parent_attributed_additive"]["total_tokens"]
            for event in events
        ]
        self.assertEqual(sum(value > 0 for value in attributed), 1)
        parent = next(
            row for row in ledger["module_parent_costs"]
            if row["module_id"] == "context_and_memory"
        )
        self.assertEqual(sum(attributed), parent["total_tokens"])

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
        self.assertEqual(social["detector_version"], "2.7.0")

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

    def test_rm06_separa_consulta_compromisso_e_efeito_sem_duplicar_custo(self) -> None:
        rows: list[str] = [
            record(
                "session_meta",
                {"session_id": "session-adversarial", "cwd": "/fixture"},
            )
        ]
        phases = (
            (
                "consulta",
                "poetry run python ferramentas/adversarial_operations.py preparar",
                "proposta_adversarial_validada",
            ),
            (
                "compromisso",
                "poetry run python ferramentas/adversarial_operations.py "
                "comprometer gop-fixture",
                "operacao_adversarial_comprometida",
            ),
            (
                "efeito_material",
                "poetry run python ferramentas/adversarial_operations.py "
                "resolver operacao-fixture --resultado factual",
                "operacao_adversarial_resolvida",
            ),
        )
        for ordinal, (event_kind, command, result) in enumerate(phases, 1):
            turn = f"adversarial-{ordinal}"
            call_id = f"a{ordinal}"
            rows.extend(
                [
                    record("event_msg", {"type": "task_started", "turn_id": turn}),
                    user(turn, mod.LEGACY_NARRATION_PROMPT),
                    call(turn, call_id, command),
                    output(
                        turn,
                        call_id,
                        "Process exited with code 0\n"
                        "schema_adversarial_operations: 2\n"
                        f"evento_modular: {event_kind}\n"
                        f"resultado_modular: {result}\n"
                        "quantidade_frentes: 2\n"
                        "operacoes_simultaneas: true\n",
                    ),
                    tokens(30, 20, 10),
                    assistant(turn, "A força externa conserva seu compromisso."),
                ]
            )

        ledger = mod.analyze(
            self.rollout(rows, "rollout-adversarial-events.jsonl")
        )["modular_ledger_v2"]
        integrity = [
            event
            for event in ledger["events"]
            if event["module_id"] == "adversarial_operations"
            and event["capability_id"] == "adversarial_contract_integrity"
        ]
        concurrent = [
            event
            for event in ledger["events"]
            if event["module_id"] == "adversarial_operations"
            and event["capability_id"] == "concurrent_operations"
        ]

        self.assertEqual(
            [event["activation_observed"] for event in integrity],
            ["consulta", "decisao", "efeito"],
        )
        self.assertEqual(len(concurrent), 3)
        self.assertTrue(all(event["eligibility_observed"] == "sim" for event in concurrent))
        for turn_ordinal in range(1, 4):
            per_turn = [
                event
                for event in ledger["events"]
                if event["turn_ordinal"] == turn_ordinal
                and event["module_id"] == "adversarial_operations"
            ]
            attributed = [
                event["cost"]["parent_attributed_additive"]["total_tokens"]
                for event in per_turn
            ]
            self.assertEqual(sum(value > 0 for value in attributed), 1)
            self.assertEqual(
                sum(attributed),
                next(
                    event["cost"]["parent_attributed_additive"]["total_tokens"]
                    for event in per_turn
                    if event["cost"]["parent_allocation_role"] == "primario"
                ),
            )
        parent = next(
            row
            for row in ledger["module_parent_costs"]
            if row["module_id"] == "adversarial_operations"
        )
        self.assertGreater(parent["total_tokens"], 0)
        self.assertEqual(integrity[0]["detector_version"], "2.7.0")

    def test_rm06_operacao_simples_nao_ativa_subcapacidade_concorrente(self) -> None:
        rows = self.base_rows() + [
            user("turno-1", mod.LEGACY_NARRATION_PROMPT),
            call(
                "turno-1",
                "simple",
                "poetry run python ferramentas/adversarial_operations.py preparar",
            ),
            output(
                "turno-1",
                "simple",
                "Process exited with code 0\n"
                "schema_adversarial_operations: 2\n"
                "evento_modular: consulta\n"
                "resultado_modular: proposta_adversarial_validada\n"
                "quantidade_frentes: 1\n"
                "operacoes_simultaneas: false\n",
            ),
            assistant("turno-1", "A força externa prepara uma ação própria."),
        ]
        events = mod.analyze(
            self.rollout(rows, "rollout-simple-adversarial.jsonl")
        )["modular_ledger_v2"]["events"]
        capabilities = {
            event["capability_id"]
            for event in events
            if event["module_id"] == "adversarial_operations"
        }
        self.assertEqual(capabilities, {"adversarial_contract_integrity"})

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
