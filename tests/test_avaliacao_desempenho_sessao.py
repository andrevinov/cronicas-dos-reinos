from __future__ import annotations

import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "ferramentas" / "gerar-avaliacao-sessao.py"
SPEC = importlib.util.spec_from_file_location("gerar_avaliacao_sessao", SCRIPT)
mod = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(mod)


def record(timestamp: str, type_: str, payload: dict) -> str:
    return json.dumps({"timestamp": timestamp, "type": type_, "payload": payload}, ensure_ascii=False)


def response(turn: str, type_: str, **payload: object) -> str:
    return record(
        str(payload.pop("timestamp")),
        "response_item",
        {
            "type": type_,
            **payload,
            "internal_chat_message_metadata_passthrough": {"turn_id": turn},
        },
    )


class SessionPerformanceEvaluationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.rollout = self.root / "rollout-fixture.jsonl"
        rows = [
            record(
                "2026-01-01T12:00:00Z",
                "session_meta",
                {"session_id": "codex-fixture", "cwd": "/fixture"},
            ),
            record(
                "2026-01-01T12:00:01Z",
                "event_msg",
                {"type": "task_started", "turn_id": "turno-1"},
            ),
            response(
                "turno-1",
                "message",
                timestamp="2026-01-01T12:00:02Z",
                role="user",
                content=[{"type": "input_text", "text": "Ren observa a rua."}],
            ),
            response(
                "turno-1",
                "custom_tool_call",
                timestamp="2026-01-01T12:00:03Z",
                name="exec",
                call_id="preparar-1",
                input="poetry run cronica preparar --cena-id fixture --sem-oportunidade-sidequest",
            ),
            response(
                "turno-1",
                "custom_tool_call_output",
                timestamp="2026-01-01T12:00:04Z",
                call_id="preparar-1",
                output=(
                    "Process exited with code 0\n"
                    "iniciativa_social: {resultado: silencio}\n"
                    "emergent_sidequest_opportunity: {resultado: sem_oportunidade}\n"
                ),
            ),
            response(
                "turno-1",
                "custom_tool_call",
                timestamp="2026-01-01T12:00:05Z",
                name="exec",
                call_id="concluir-1",
                input="poetry run cronica concluir --ticket fixture",
            ),
            response(
                "turno-1",
                "custom_tool_call_output",
                timestamp="2026-01-01T12:00:06Z",
                call_id="concluir-1",
                output=(
                    "Process exited with code 0\nfase: concluida\n"
                    "interacao:\n  schema_narrative_interaction: 1\n"
                    "  interaction_id: interaction-fixture\n"
                    "  interaction_ref: S022-I0001\n  session: 22\n"
                    "  ordinal: 1\n  class: ON\n  state: complete\n"
                ),
            ),
            record(
                "2026-01-01T12:00:07Z",
                "event_msg",
                {
                    "type": "token_count",
                    "info": {
                        "last_token_usage": {
                            "input_tokens": 100,
                            "cached_input_tokens": 80,
                            "output_tokens": 20,
                            "reasoning_output_tokens": 5,
                        }
                    },
                },
            ),
            response(
                "turno-1",
                "message",
                timestamp="2026-01-01T12:00:08Z",
                role="assistant",
                content=[{"type": "output_text", "text": "A rua permanece calma.\nInteração S022-I0001"}],
            ),
        ]
        self.rollout.write_text("\n".join(rows) + "\n", encoding="utf-8")

        self.catalog = self.root / "catalogo.json"
        self.catalog.write_text(
            json.dumps(
                {
                    "schema_catalogo_modulos": 1,
                    "modulos": [
                        {
                            "id": "emergent_sidequest_opportunity",
                            "responsabilidade": "decidir oportunidade",
                            "visibilidade_jogador": "tecnica",
                            "indicadores_especializados": ["cobertura"],
                        },
                        {
                            "id": "npc_social_initiative",
                            "responsabilidade": "decidir iniciativa",
                            "visibilidade_jogador": "direta",
                            "rotulo_jogador": "Iniciativa social",
                            "indicadores_especializados": ["janela"],
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.targets = self.root / "metas.json"
        self.targets.write_text(
            json.dumps(
                {
                    "schema_metas_avaliacao": 1,
                    "pesos_sessao": {
                        "calibracao": 25,
                        "eficacia_integridade": 25,
                        "confiabilidade": 15,
                        "economia": 20,
                        "fluidez": 5,
                        "jogador": 10,
                    },
                    "pesos_modulo": {
                        "calibracao": 25,
                        "eficacia_integridade": 25,
                        "confiabilidade": 15,
                        "economia": 20,
                        "fluidez": 5,
                        "jogador": 10,
                    },
                    "notas_avaliacao_ativacao": {"ativou a contento": 90},
                    "notas_impacto_1a5": {"1": 90},
                    "metas_globais": {
                        "reducao_input_bruto_minima": 0.7,
                        "inferencias_por_turno": 5,
                        "tools_por_turno": 5,
                        "fracao_l0_l2_limpo": 0.8,
                    },
                    "latencia_segundos": {"mediana": 60, "p90": 120},
                    "faixas_desempenho": [
                        {"id": "excelente", "minimo": 90},
                        {"id": "critico", "minimo": 0},
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.baseline = self.root / "baseline.json"
        self.baseline.write_text(
            json.dumps({"narration_turns": {"turns": 1, "input_tokens": 1000}}),
            encoding="utf-8",
        )
        self.audit = self.root / "auditoria.csv"
        with self.audit.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=mod.AUDIT_COLUMNS)
            writer.writeheader()
            writer.writerow(
                {
                    "modulo": "npc_social_initiative",
                    "avaliacao_ativacao": "ativou a contento",
                    "impacto_experiencia_1a5": "1",
                    "impacto_custo_1a5": "1",
                    "prioridade_rank": "1",
                }
            )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def generate(self) -> Path:
        output = self.root / "pacote"
        mod.generate_session_evaluation(
            self.rollout,
            session_id="fixture",
            output_dir=output,
            catalog_path=self.catalog,
            targets_path=self.targets,
            baseline_path=self.baseline,
            audit_path=self.audit,
        )
        return output

    def test_gera_pacote_com_custo_fracionado_aditivo(self) -> None:
        output = self.generate()
        expected = {
            "manifest.json",
            "telemetria.json",
            "turnos.csv",
            "eventos-modulares.csv",
            "auditoria-modulos.csv",
            "resumo-modulos.csv",
            "feedback-jogador.csv",
            "validade-medicao.json",
            "scorecard.json",
            "relatorio.md",
            "resumo-modulos.json",
        }
        self.assertEqual({path.name for path in output.iterdir()}, expected)
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["serie_avaliacao"], "legacy-v1")
        self.assertEqual(manifest["versoes"]["sistemas_narrativos"], 1)
        self.assertEqual(manifest["amostra"]["turnos_narrativos"], 1)
        self.assertEqual(manifest["amostra"]["eventos_modulo_turno"], 2)
        self.assertEqual(manifest["amostra"]["tokens_narrativos"], 120)
        self.assertEqual(manifest["amostra"]["tokens_atribuidos_fracionados"], 120)
        self.assertFalse(manifest["fonte"]["bruto_copiado_para_repo"])
        self.assertFalse((output / self.rollout.name).exists())

        module_json = json.loads((output / "resumo-modulos.json").read_text(encoding="utf-8"))
        self.assertEqual(len(module_json["modulos"]), 2)

        with (output / "eventos-modulares.csv").open(encoding="utf-8", newline="") as stream:
            events = list(csv.DictReader(stream))
        self.assertEqual(sum(int(row["tokens_totais_atribuidos_fracionados"]) for row in events), 120)
        self.assertEqual({row["estado_ativacao"] for row in events}, {"observada"})
        with (output / "turnos.csv").open(encoding="utf-8", newline="") as stream:
            turns = list(csv.DictReader(stream))
        self.assertEqual(turns[0]["latencia_segundos"], "6.0")

    def test_regeneracao_preserva_feedback_do_jogador(self) -> None:
        output = self.generate()
        feedback = output / "feedback-jogador.csv"
        with feedback.open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        for row in rows:
            if row["tipo"] == "global" and row["item"] == "ritmo":
                row["nota_1a5"] = "4"
                row["comentario"] = "ritmo preservado"
        with feedback.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=mod.FEEDBACK_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

        mod.generate_session_evaluation(
            self.rollout,
            session_id="fixture",
            output_dir=output,
            catalog_path=self.catalog,
            targets_path=self.targets,
            baseline_path=self.baseline,
        )
        with feedback.open(encoding="utf-8", newline="") as stream:
            preserved = list(csv.DictReader(stream))
        rhythm = next(row for row in preserved if row["item"] == "ritmo")
        self.assertEqual(rhythm["nota_1a5"], "4")
        self.assertEqual(rhythm["comentario"], "ritmo preservado")

    def test_reconstroi_indice_quando_pacote_fica_em_sessions(self) -> None:
        sessions = self.root / "sessions"
        output = sessions / "fixture"
        mod.generate_session_evaluation(
            self.rollout,
            session_id="fixture",
            output_dir=output,
            catalog_path=self.catalog,
            targets_path=self.targets,
            baseline_path=self.baseline,
            audit_path=self.audit,
        )

        index = json.loads((sessions / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["schema_indice_avaliacoes"], 1)
        self.assertEqual(len(index["sessoes"]), 1)
        self.assertEqual(index["sessoes"][0]["sessao_id"], "fixture")
        self.assertEqual(index["sessoes"][0]["serie_avaliacao"], "legacy-v1")
        self.assertEqual(
            index["sessoes"][0]["chave_comparabilidade"],
            ["legacy-v1", "ausente", "1"],
        )
        self.assertEqual(index["sessoes"][0]["caminho"], "fixture")

    def test_gerador_v2_publica_doze_pais_versoes_e_interacoes_sem_nota_do_jogador(self) -> None:
        output = self.root / "pacote-v2"
        frozen = self.root / "interacoes.json"
        frozen.write_text(
            json.dumps(
                {
                    "schema_narrative_interactions": 1,
                    "session": 22,
                    "interactions": [
                        {
                            "interaction_ref": "S022-I0001",
                            "module_versions": {
                                "turn_and_session_orchestration": {
                                    "implementation_version": "1.0.0",
                                    "evaluation_version": "3.0.0",
                                }
                            },
                        }
                    ],
                    "player_feedback": [],
                }
            ),
            encoding="utf-8",
        )
        result = mod.generate_session_evaluation(
            self.rollout,
            session_id="022",
            output_dir=output,
            catalog_path=mod.DEFAULT_CATALOG,
            targets_path=mod.DEFAULT_TARGETS,
            baseline_path=self.baseline,
            interactions_path=frozen,
        )

        self.assertEqual(result["manifest"]["serie_avaliacao"], "modules-v2")
        self.assertEqual(result["manifest"]["schema_pacote_avaliacao"], 2)
        self.assertEqual(len(result["manifest"]["versoes_modulos"]), 12)
        self.assertNotIn("jogador", result["scorecard"]["eixos"])
        modules = json.loads((output / "resumo-modulos.json").read_text(encoding="utf-8"))["modulos"]
        self.assertEqual(len(modules), 12)
        self.assertTrue(all(item["prioridade_rank"] is None for item in modules))
        self.assertFalse(result["scorecard"]["filas_prioridade"]["ranking_global_existe"])
        self.assertFalse(
            result["scorecard"]["filas_prioridade"]["custo_e_experiencia_misturados"]
        )
        self.assertTrue(all(item["versao_implementacao"] for item in modules))
        authoring = next(item for item in modules if item["modulo"] == "sidequest_authoring")
        self.assertEqual(authoring["gate_oportunidade_preparos"], 1)
        self.assertEqual(authoring["gate_oportunidade_decisoes_validas"], 1)
        self.assertEqual(authoring["gate_oportunidade_violacoes"], 0)
        self.assertEqual(authoring["gate_oportunidade_conformidade_pct"], 100.0)
        self.assertEqual(authoring["falsos_positivos"], 0)
        self.assertEqual(authoring["ativacoes_observadas"], 0)
        self.assertEqual(authoring["versao_implementacao"], "2.0.1")
        self.assertEqual(authoring["versao_avaliacao"], "4.0.0")
        self.assertEqual(authoring["avaliacoes_oportunidade_recebidas"], 0)
        self.assertEqual(authoring["avaliacoes_oportunidade_pontuaveis"], 0)
        self.assertEqual(authoring["aplicabilidade_avaliacao"], "falha_instrumentacao")
        self.assertIsNone(authoring["nota_desempenho_provisoria_0a100"])
        self.assertIsNone(authoring["nota_confiabilidade_proxy_0a100"])
        self.assertEqual(authoring["avaliacao_ativacao"], "falha de instrumentação")
        self.assertEqual(authoring["confianca_amostra_sessao"], "N/D")
        self.assertFalse(authoring["custo_exposto_participa_prioridade"])
        self.assertIsNotNone(authoring["fila_reparo_medidor_rank"])
        self.assertFalse(
            authoring["custo_atribuicao_contabil"]["causalidade_inferida"]
        )
        self.assertEqual(authoring["unidades_avaliativas_obrigatorias"], 1)
        self.assertEqual(authoring["recibos_cobertura_ausentes"], 1)
        self.assertIn("recibo(s) de cobertura ausente", authoring["principais_problemas_de_ativacao"])
        orchestration = next(item for item in modules if item["modulo"] == "turn_and_session_orchestration")
        self.assertEqual(orchestration["versao_implementacao"], "1.0.0")
        interactions = json.loads((output / "interacoes.json").read_text(encoding="utf-8"))["interactions"]
        self.assertEqual(interactions[0]["interaction_ref"], "S022-I0001")
        self.assertTrue(interactions[0]["visible_exactly_once"])
        self.assertTrue((output / "manifestacoes-jogador.json").is_file())
        quality = json.loads(
            (output / "avaliacoes-qualidade.json").read_text(encoding="utf-8")
        )
        self.assertEqual(quality["schema_avaliacoes_qualidade"], 1)
        self.assertEqual(quality["assessments"], [])
        self.assertEqual(
            result["manifest"]["artefatos"]["avaliacoes_qualidade"],
            "avaliacoes-qualidade.json",
        )
        self.assertFalse((output / "feedback-jogador.csv").exists())

    def test_scoreboard_nao_inventa_nota_e_incorpora_gates_feedback_e_auditoria(self) -> None:
        def module(module_id: str) -> dict:
            return {
                "id": module_id,
                "responsabilidade": module_id,
                "visibilidade_jogador": "direta",
                "rotulo_jogador": module_id,
                "versao_implementacao": "1.0.0",
                "versao_avaliacao": "3.0.0",
                "subcapacidades": [{"id": "cap", "responsabilidade": "cap"}],
            }

        def event(
            event_id: str,
            module_id: str,
            eligibility: str,
            activation: str,
            effect: bool | None,
        ) -> dict:
            return {
                "event_id": event_id,
                "module_id": module_id,
                "capability_id": "cap",
                "turn_ordinal": 1,
                "eligibility_observed": eligibility,
                "activation_observed": activation,
                "effect_observed": effect,
                "inference_confidence": "alta",
                "call_ids_observed": [f"call-{event_id}"],
                "adjudication": None,
            }

        catalog = [
            module("gate_module"),
            module("evidence_only"),
            module("feedback_module"),
            module("scene_module"),
            module("guardrail_module"),
            module("narrative_delivery"),
            module("without_evidence"),
        ]
        ledger = {
            "events": [
                event("gate", "gate_module", "sim", "gate_neutro", None),
                event("observed", "evidence_only", "indeterminada", "consulta", None),
                event("scene-gate", "scene_module", "sim", "gate_neutro", None),
                event("delivery", "narrative_delivery", "sim", "efeito", True),
            ],
            "player_feedback": [
                {
                    "perceived_type": "continuidade",
                    "system_suggestion": {"module_id": "feedback_module"},
                    "adjudication": {"state": "confirmada"},
                },
                {
                    "perceived_type": "continuidade",
                    "system_suggestion": {"module_id": "scene_module"},
                    "adjudication": {"state": "confirmada"},
                },
                {
                    "feedback_id": "feedback-guardrail",
                    "interaction_ref": "S022-I0009",
                    "perceived_type": "possivel_guardrail",
                    "system_suggestion": {"module_id": "guardrail_module"},
                    "adjudication": {"state": "confirmada"},
                },
            ],
            "semantic_audits": [
                {
                    "event_id": "delivery",
                    "dimensions": {
                        "progressao_jogavel": "adequado",
                        "densidade_proporcional": "inadequado",
                        "voz_e_dialogo": "indeterminado",
                    },
                }
            ],
            "module_parent_costs": [],
        }
        targets = json.loads(mod.DEFAULT_TARGETS.read_text(encoding="utf-8"))
        rows = mod._module_summary_v2(
            catalog,
            ledger,
            [{"ordinal": 1, "latencia_segundos": 30.0}],
            targets,
            100,
        )
        by_id = {row["modulo"]: row for row in rows}

        gate = by_id["gate_module"]
        self.assertEqual(gate["ativacoes_observadas"], 1)
        self.assertEqual(gate["falsos_negativos"], 0)
        self.assertEqual(gate["nota_calibracao_0a100"], 100.0)
        self.assertIsNotNone(gate["nota_desempenho_provisoria_0a100"])

        evidence_only = by_id["evidence_only"]
        self.assertEqual(evidence_only["chamadas_detectadas"], 1)
        self.assertEqual(evidence_only["aplicabilidade_avaliacao"], "evidencia_insuficiente")
        self.assertIsNone(evidence_only["nota_confiabilidade_proxy_0a100"])
        self.assertIsNone(evidence_only["nota_desempenho_provisoria_0a100"])

        feedback = by_id["feedback_module"]
        self.assertEqual(feedback["efeitos_avaliaveis"], 1)
        self.assertEqual(feedback["nota_eficacia_integridade_0a100"], 0.0)
        self.assertEqual(feedback["aplicabilidade_avaliacao"], "aplicavel")
        self.assertEqual(feedback["confianca_amostra_sessao"], "baixa")
        self.assertNotIn(
            "nenhuma evidência observável",
            feedback["principais_problemas_de_ativacao"],
        )

        scene = by_id["scene_module"]
        self.assertEqual(scene["chamadas_detectadas"], 1)
        self.assertEqual(scene["ativacoes_observadas"], 1)
        self.assertEqual(scene["nota_calibracao_0a100"], 100.0)
        self.assertEqual(scene["nota_eficacia_integridade_0a100"], 0.0)
        self.assertGreater(scene["nota_desempenho_provisoria_0a100"], 0.0)

        guardrail = by_id["guardrail_module"]
        self.assertIsNone(guardrail["nota_desempenho_provisoria_0a100"])
        self.assertIn("guardrail(s) confirmado(s)", guardrail["principais_problemas_de_ativacao"])

        scorecard = mod._scorecard_v2(
            "022",
            {"narration_turns": {}},
            ledger,
            rows,
            {"violacoes_criticas": []},
            {"narration_turns": {"input_tokens": 100}},
            targets,
            [],
        )
        self.assertEqual(scorecard["status_avaliacao"], "comprometida")
        self.assertEqual(scorecard["manifestacoes"]["guardrails_confirmados"], 1)
        self.assertEqual(
            scorecard["violacoes_criticas"][0]["feedback_id"],
            "feedback-guardrail",
        )

        delivery = by_id["narrative_delivery"]
        self.assertEqual(delivery["auditorias_semanticas"], 1)
        self.assertEqual(delivery["dimensoes_semanticas_avaliadas"], 2)
        self.assertEqual(delivery["dimensoes_semanticas_inadequadas"], 1)
        self.assertEqual(delivery["efeitos_avaliaveis"], 3)
        self.assertEqual(delivery["nota_eficacia_integridade_0a100"], 66.67)
        self.assertEqual(
            by_id["without_evidence"]["aplicabilidade_avaliacao"],
            "sem_evidencia",
        )

    def test_sidequest_v4_usa_matriz_objetiva_e_exclui_indeterminado(self) -> None:
        catalog = [
            {
                "id": "sidequest_authoring",
                "responsabilidade": "avaliar oportunidade",
                "visibilidade_jogador": "direta",
                "rotulo_jogador": "Sidequests",
                "versao_implementacao": "2.0.0",
                "versao_avaliacao": "4.0.0",
                "subcapacidades": [
                    {"id": "opportunity_gate", "responsabilidade": "gate"}
                ],
            }
        ]
        classifications = [
            "verdadeiro_positivo",
            "verdadeiro_negativo",
            "falso_positivo",
            "falso_negativo",
            "indeterminado",
        ]
        ledger = {
            "events": [],
            "player_feedback": [],
            "semantic_audits": [],
            "module_parent_costs": [],
            "interactions": [
                {
                    "turn_id": f"turno-{index}",
                    "interaction_ref": f"S022-I{index:04d}",
                }
                for index in range(1, 6)
            ],
        }
        gate_audit = {
            "prepare_calls": 5,
            "valid_decisions": 5,
            "violations": 0,
            "coverage": 1.0,
            "objective_assessment": {
                "receipts": 5,
                "scoreable": 4,
                "indeterminate": 1,
                "assessments": [
                    {
                        "turn_id": f"turno-{index}",
                        "classification": classification,
                    }
                    for index, classification in enumerate(classifications, 1)
                ],
            },
        }
        targets = json.loads(mod.DEFAULT_TARGETS.read_text(encoding="utf-8"))

        row = mod._module_summary_v2(
            catalog,
            ledger,
            [],
            targets,
            0,
            gate_audit,
        )[0]

        self.assertEqual(row["verdadeiros_positivos"], 1)
        self.assertEqual(row["verdadeiros_negativos"], 1)
        self.assertEqual(row["falsos_positivos"], 1)
        self.assertEqual(row["falsos_negativos"], 1)
        self.assertEqual(row["avaliacoes_oportunidade_pontuaveis"], 4)
        self.assertEqual(row["avaliacoes_oportunidade_indeterminadas"], 1)
        self.assertEqual(row["precisao_oportunidade"], 50.0)
        self.assertEqual(row["cobertura_oportunidade"], 50.0)
        self.assertEqual(row["especificidade_oportunidade"], 50.0)
        self.assertEqual(row["acuracia_balanceada_oportunidade"], 50.0)
        self.assertEqual(row["nota_calibracao_0a100"], 50.0)

    def test_integracao_canonica_v4_separa_resultado_na_e_falha_de_cobertura(self) -> None:
        catalog = [
            {
                "id": "canonical_quest_integration",
                "responsabilidade": "integrar missões ao cânone",
                "visibilidade_jogador": "reservada",
                "rotulo_jogador": "Integração canônica",
                "versao_implementacao": "2.0.0",
                "versao_avaliacao": "4.0.0",
                "subcapacidades": [
                    {"id": "sidequest_to_canon_bridge", "responsabilidade": "ponte"}
                ],
            }
        ]
        ledger = {
            "events": [],
            "player_feedback": [],
            "semantic_audits": [],
            "module_parent_costs": [],
        }
        targets = json.loads(mod.DEFAULT_TARGETS.read_text(encoding="utf-8"))

        success = mod._module_summary_v2(
            catalog,
            ledger,
            [],
            targets,
            0,
            None,
            {
                "activity_units": 1,
                "receipts": 1,
                "scoreable": 1,
                "non_scoreable": 0,
                "indeterminate": 0,
                "missing_receipts": 0,
                "incomplete_receipts": 0,
                "coverage_complete": True,
                "confusion_matrix": {"verdadeiro_positivo": 1},
            },
        )[0]
        not_applicable = mod._module_summary_v2(
            catalog,
            ledger,
            [],
            targets,
            0,
            None,
            {
                "activity_units": 2,
                "receipts": 2,
                "scoreable": 1,
                "non_scoreable": 1,
                "indeterminate": 0,
                "missing_receipts": 0,
                "incomplete_receipts": 0,
                "coverage_complete": True,
                "confusion_matrix": {"verdadeiro_negativo": 1},
            },
        )[0]
        instrumentation_failure = mod._module_summary_v2(
            catalog,
            ledger,
            [],
            targets,
            0,
            None,
            {
                "activity_units": 2,
                "receipts": 1,
                "scoreable": 0,
                "non_scoreable": 1,
                "indeterminate": 0,
                "missing_receipts": 1,
                "incomplete_receipts": 0,
                "coverage_complete": False,
                "confusion_matrix": {},
            },
        )[0]

        self.assertEqual(success["avaliacao_ativacao"], "ativou a contento")
        self.assertEqual(success["nota_calibracao_0a100"], 100.0)
        self.assertIsNotNone(success["nota_desempenho_provisoria_0a100"])
        self.assertEqual(success["aplicabilidade_avaliacao"], "aplicavel")

        self.assertEqual(not_applicable["avaliacao_ativacao"], "não aplicável")
        self.assertEqual(not_applicable["aplicabilidade_avaliacao"], "nao_aplicavel")
        self.assertIsNone(not_applicable["nota_desempenho_provisoria_0a100"])
        self.assertFalse(not_applicable["custo_exposto_participa_prioridade"])

        self.assertEqual(
            instrumentation_failure["avaliacao_ativacao"],
            "falha de instrumentação",
        )
        self.assertEqual(
            instrumentation_failure["aplicabilidade_avaliacao"],
            "evidencia_insuficiente",
        )
        self.assertIsNone(
            instrumentation_failure["nota_desempenho_provisoria_0a100"]
        )
        self.assertIn(
            "1 recibo(s) ausente(s)",
            instrumentation_failure["principais_problemas_de_ativacao"],
        )

if __name__ == "__main__":
    unittest.main()
