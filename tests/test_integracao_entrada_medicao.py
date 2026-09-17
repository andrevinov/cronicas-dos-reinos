from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from ferramentas import entrada_medicao


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "ferramentas/gerar-avaliacao-sessao.py"
TECHNICAL_ROLLOUT = ROOT / "tests/fixtures/rollout-modules-v2-technical.jsonl"


def _load_generator():
    spec = importlib.util.spec_from_file_location("test_frozen_evaluation_generator", GENERATOR_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FrozenMeasurementIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="integracao-entrada-medicao-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.generator = _load_generator()
        self.rollout = self.root / "rollout.jsonl"
        self.rollout.write_bytes(TECHNICAL_ROLLOUT.read_bytes())
        self.catalog = self.root / "catalogo.json"
        self.catalog.write_bytes(entrada_medicao.DEFAULT_SOURCES["catalogo"].read_bytes())
        self.interactions = self._json(
            "interacoes.json",
            {
                "schema_narrative_interactions": 1,
                "session": 900,
                "interactions": [],
                "player_feedback": [],
            },
        )
        self.adjudications = self._json(
            "adjudicacoes.json",
            {
                "schema_adjudicacoes_modulares": 2,
                "corrections": [],
                "semantic_audits": [],
                "quality_assessments": [],
                "player_feedback": [],
            },
        )
        self.validity = self._json(
            "validade.json",
            {
                "schema_validade_medicao": 2,
                "sessao_id": "900",
                "metricas_adjudicadas": {},
                "correcoes": [],
                "violacoes_criticas": [],
            },
        )

    def _json(self, name: str, value: object) -> Path:
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def _sources(self) -> dict[str, Path | None]:
        sources = dict(entrada_medicao.DEFAULT_SOURCES)
        sources.update(
            {
                "catalogo": self.catalog,
                "interacoes": self.interactions,
                "adjudicacoes": self.adjudications,
                "validade": self.validity,
            }
        )
        return sources

    def _freeze(self, rollout: Path | None = None) -> dict:
        bundle = entrada_medicao.prepare_input(
            rollout or self.rollout,
            session_id="900",
            source_paths=self._sources(),
        )
        self.assertEqual(bundle["status"], "valida", bundle["diagnosticos"])
        return bundle

    @staticmethod
    def _bytes(directory: Path) -> dict[str, bytes]:
        return {path.name: path.read_bytes() for path in directory.iterdir() if path.is_file()}

    def _generate(self, bundle: dict, output: Path, rollout: Path | None = None):
        return self.generator.generate_session_evaluation(
            rollout or self.rollout,
            session_id="900",
            output_dir=output,
            measurement_input=bundle,
        )

    def test_same_entry_reproduces_all_artifact_bytes_and_ignores_later_source_changes(self):
        bundle = self._freeze()
        first = self.root / "first"
        self._generate(bundle, first)

        with self.rollout.open("ab") as stream:
            stream.write(b'{"registro posterior incompleto"')
        changed = json.loads(self.catalog.read_text(encoding="utf-8"))
        changed["modulos"][0]["versao_implementacao"] = "99.0.0"
        self.catalog.write_text(json.dumps(changed), encoding="utf-8")
        self.interactions.write_text("{}", encoding="utf-8")

        second = self.root / "second"
        result = self._generate(bundle, second)
        self.assertEqual(self._bytes(first), self._bytes(second))
        self.assertEqual(result["manifest"]["fonte"]["bytes"], bundle["fonte"]["corte_bytes"])
        self.assertEqual(result["manifest"]["fonte"]["sha256"], bundle["fonte"]["sha256"])
        self.assertEqual(result["manifest"]["fonte"]["arquivo"], "fonte-congelada.jsonl")
        provenance = json.loads((second / "proveniencia-medicao.json").read_text(encoding="utf-8"))
        self.assertEqual(provenance["entrada_id"], bundle["entrada_id"])
        self.assertTrue(provenance["conclusao_reprodutivel_permitida"])

    def test_tampering_code_and_environment_fail_before_output_creation(self):
        for field in ("snapshot", "code", "environment", "optional_schema"):
            with self.subTest(field=field):
                bundle = copy.deepcopy(self._freeze())
                if field == "snapshot":
                    bundle["snapshots"]["metas"]["conteudo"]["alterada"] = True
                elif field == "code":
                    bundle["codigo_sha256"]["ferramentas/analisar-rollout.py"] = "0" * 64
                    bundle["entrada_id"] = entrada_medicao.digest(
                        {key: value for key, value in bundle.items() if key != "entrada_id"}
                    )
                elif field == "environment":
                    bundle["ambiente"]["python"] = "0.0.0"
                    bundle["entrada_id"] = entrada_medicao.digest(
                        {key: value for key, value in bundle.items() if key != "entrada_id"}
                    )
                else:
                    snapshot = bundle["snapshots"]["adjudicacoes"]
                    snapshot["conteudo"]["schema_adjudicacoes_modulares"] = 99
                    snapshot["sha256"] = entrada_medicao.digest(snapshot["conteudo"])
                    bundle["entrada_id"] = entrada_medicao.digest(
                        {key: value for key, value in bundle.items() if key != "entrada_id"}
                    )
                output = self.root / f"blocked-{field}"
                with self.assertRaises(self.generator.EvaluationError):
                    self._generate(bundle, output)
                self.assertFalse(output.exists())

    def test_unknown_rollout_format_is_refused_before_scoring(self):
        rollout = self.root / "unknown.jsonl"
        rollout.write_text('{"type":"formato_futuro","payload":{}}\n', encoding="utf-8")
        bundle = entrada_medicao.prepare_input(
            rollout, session_id="900", source_paths=self._sources()
        )
        self.assertEqual(bundle["status"], "bloqueada")
        output = self.root / "unknown-package"
        with self.assertRaises(self.generator.EvaluationError):
            self._generate(bundle, output, rollout)
        self.assertFalse(output.exists())

    def test_missing_and_ambiguous_results_block_dependent_conclusions(self):
        missing = self.root / "missing.jsonl"
        missing.write_text(
            "\n".join(
                [
                    json.dumps({"type": "session_meta", "payload": {"id": "frozen"}}),
                    json.dumps({"type": "event_msg", "payload": {"type": "task_started", "turn_id": "t1"}}),
                    json.dumps(
                        {
                            "type": "response_item",
                            "payload": {
                                "type": "function_call",
                                "name": "exec_command",
                                "call_id": "missing",
                                "arguments": json.dumps({"cmd": "poetry run cronica preparar --cena-id x --sem-oportunidade-sidequest"}),
                                "internal_chat_message_metadata_passthrough": {"turn_id": "t1"},
                            },
                        }
                    ),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        script = (
            "const results=await Promise.allSettled(["
            "tools.exec_command({cmd:\"rg -n um docs\"}),"
            "tools.exec_command({cmd:\"rg -n dois docs\"})]);"
            "results.forEach((r,i)=>text({i,...r}));"
        )
        nested = "Script completed\nOutput:\n" + json.dumps(
            [
                {"i": 0, "status": "fulfilled", "value": {"exit_code": 0, "output": "um"}},
                {"i": 0, "status": "fulfilled", "value": {"exit_code": 0, "output": "duplicado"}},
            ]
        )
        ambiguous = self.root / "ambiguous.jsonl"
        ambiguous.write_text(
            "\n".join(
                [
                    json.dumps({"type": "session_meta", "payload": {"id": "frozen"}}),
                    json.dumps({"type": "event_msg", "payload": {"type": "task_started", "turn_id": "t1"}}),
                    json.dumps({"type": "response_item", "payload": {"type": "custom_tool_call", "name": "functions.exec", "call_id": "group", "input": script, "internal_chat_message_metadata_passthrough": {"turn_id": "t1"}}}),
                    json.dumps({"type": "response_item", "payload": {"type": "function_call_output", "call_id": "group", "output": nested, "internal_chat_message_metadata_passthrough": {"turn_id": "t1"}}}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        for rollout, code in (
            (missing, "resultado_operacao_ausente"),
            (ambiguous, "correlacao_ambigua"),
        ):
            with self.subTest(code=code):
                bundle = self._freeze(rollout)
                output = self.root / f"package-{code}"
                result = self._generate(bundle, output, rollout)
                conclusion = result["scorecard"]["conclusao_medicao"]
                self.assertFalse(conclusion["permitida"])
                self.assertIn(code, {item["codigo"] for item in conclusion["bloqueios"]})
                self.assertEqual(result["scorecard"]["status_avaliacao"], "bloqueada_evidencia")

    def test_frozen_mode_never_reads_stale_package_files_and_direct_mode_is_unverified(self):
        bundle = self._freeze()
        output = self.root / "stale"
        output.mkdir()
        (output / "validade-medicao.json").write_text("{", encoding="utf-8")
        (output / "adjudicacoes-modulares.json").write_text("{", encoding="utf-8")
        frozen = self._generate(bundle, output)
        self.assertTrue(frozen["manifest"]["proveniencia_medicao"]["conclusao_reprodutivel_permitida"])

        direct_output = self.root / "direct"
        direct = self.generator.generate_session_evaluation(
            self.rollout,
            session_id="900",
            output_dir=direct_output,
            catalog_path=entrada_medicao.DEFAULT_SOURCES["catalogo"],
            targets_path=entrada_medicao.DEFAULT_SOURCES["metas"],
            baseline_path=entrada_medicao.DEFAULT_SOURCES["baseline"],
        )
        conclusion = direct["scorecard"]["conclusao_medicao"]
        self.assertFalse(conclusion["entrada_congelada"])
        self.assertFalse(conclusion["reproducao_verificada"])
        self.assertIn("entrada_nao_congelada", {item["codigo"] for item in conclusion["bloqueios"]})


if __name__ == "__main__":
    unittest.main()
