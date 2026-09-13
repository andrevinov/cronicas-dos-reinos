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
                output="Process exited with code 0\nfase: concluida\n",
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
                content=[{"type": "output_text", "text": "A rua permanece calma."}],
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
            ["legacy-v1", "1", "1", "1"],
        )
        self.assertEqual(index["sessoes"][0]["caminho"], "fixture")


if __name__ == "__main__":
    unittest.main()
