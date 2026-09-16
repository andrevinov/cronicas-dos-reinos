from __future__ import annotations

import hashlib
import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ferramentas import verificar_corpus_avaliacao as corpus

ROOT = Path(__file__).resolve().parents[1]


class EvaluationRegressionCorpusTest(unittest.TestCase):
    """Protege fixtures históricas/isoladas, sem ler o estado vivo da campanha."""

    def test_installed_corpus_has_independent_golden_cases_and_metamorphic_relations(self):
        manifest = corpus.validate_corpus()
        self.assertEqual(manifest["versao_corpus"], "1.0.0")
        self.assertEqual(len(manifest["casos"]), 19)
        self.assertEqual(len(manifest["relacoes"]), 2)
        self.assertEqual(
            sum(
                len(json.loads((corpus.DEFAULT_CORPUS.parent / case["gabarito"]).read_text())["checks"])
                for case in manifest["casos"]
            ),
            201,
        )
        self.assertTrue(all(case["conjunto"] == "desenvolvimento" for case in manifest["casos"]))
        self.assertIn("não gerados pelo avaliador", manifest["fonte_expectativas"])
        session_reductions = [case for case in manifest["casos"] if case["origem"]["tipo"] == "reducao_s023"]
        self.assertEqual(len(session_reductions), 5)
        self.assertTrue(all(case["origem"]["referencias_s023"] for case in session_reductions))

    def test_known_control_cases_pass_through_native_input_and_package(self):
        controls = {
            "preparo_direto_completo",
            "leitura_e_preparo_separados",
            "comando_apenas_citado",
            "preparo_sem_recibos",
            "retry_sem_efeito_duplicado",
            "saida_em_blocos",
        }
        result = corpus.run_corpus(selected=controls)
        self.assertEqual(result["status"], "aprovado")
        self.assertEqual(result["casos_executados"], len(controls))
        self.assertEqual(result["falhas"], 0)
        self.assertGreater(result["checks"], 80)

    def test_golden_tampering_unknown_units_and_false_evidence_are_rejected(self):
        with TemporaryDirectory(prefix="corpus-avaliacao-invalido-") as tmp:
            copied = Path(tmp) / "regressoes"
            shutil.copytree(corpus.DEFAULT_CORPUS.parent, copied)
            manifest_path = copied / "corpus.json"
            manifest = json.loads(manifest_path.read_text())
            selected = manifest["casos"][0]
            golden_path = copied / selected["gabarito"]

            golden = json.loads(golden_path.read_text())
            golden["checks"][0]["unidade_avaliativa"] = "unidade_inventada"
            golden_path.write_text(json.dumps(golden, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            selected["sha256_gabarito"] = hashlib.sha256(golden_path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(corpus.CorpusError, "unidade desconhecida"):
                corpus.validate_corpus(manifest_path)

            shutil.rmtree(copied)
            shutil.copytree(corpus.DEFAULT_CORPUS.parent, copied)
            manifest_path = copied / "corpus.json"
            manifest = json.loads(manifest_path.read_text())
            selected = manifest["casos"][0]
            golden_path = copied / selected["gabarito"]
            golden = json.loads(golden_path.read_text())
            golden["checks"][0]["evidencias"][0]["fragmento"] = "evidência que não existe"
            golden_path.write_text(json.dumps(golden, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            selected["sha256_gabarito"] = hashlib.sha256(golden_path.read_bytes()).hexdigest()
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
            with self.assertRaisesRegex(corpus.CorpusError, "fragmento não está"):
                corpus.validate_corpus(manifest_path)

    def test_hashes_prevent_silent_changes_to_inputs_and_configuration(self):
        with TemporaryDirectory(prefix="corpus-avaliacao-hash-") as tmp:
            copied = Path(tmp) / "regressoes"
            shutil.copytree(corpus.DEFAULT_CORPUS.parent, copied)
            rollout = next((copied / "rollouts").glob("*.jsonl"))
            rollout.write_text(rollout.read_text() + "\n", encoding="utf-8")
            with self.assertRaisesRegex(corpus.CorpusError, "diverge do hash"):
                corpus.validate_corpus(copied / "corpus.json")

            shutil.rmtree(copied)
            shutil.copytree(corpus.DEFAULT_CORPUS.parent, copied)
            config = copied / "config/metas.json"
            data = json.loads(config.read_text())
            data["alteracao_silenciosa"] = True
            config.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(corpus.CorpusError, "configuração congelada divergem"):
                corpus.validate_corpus(copied / "corpus.json")

    def test_unknown_case_selection_is_an_error_instead_of_empty_approval(self):
        with self.assertRaisesRegex(corpus.CorpusError, "casos inexistentes"):
            corpus.run_corpus(selected={"caso_inexistente"})

    def test_comparison_distinguishes_missing_value_null_and_wrong_type(self):
        projection = {"valor_nulo": None, "booleano": True}
        self.assertIs(corpus._at(projection, ["ausente"]), corpus.MISSING)
        self.assertIsNone(corpus._at(projection, ["valor_nulo"]))
        self.assertFalse(corpus._same(True, 1))
        self.assertTrue(corpus._same({"b": 2, "a": 1}, {"a": 1, "b": 2}))


class InitialCorpusResultTest(unittest.TestCase):
    def test_initial_result_is_historical_evidence_not_a_required_live_value(self):
        path = corpus.DEFAULT_CORPUS.parent / "resultado-inicial.json"
        result = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(result["schema_resultado_corpus_regressao"], 1)
        self.assertEqual(result["status"], "reprovado")
        self.assertEqual(result["aprovados"] + result["falhas"], result["checks"])
        self.assertGreater(result["falhas"], 0)
        self.assertEqual(set(result["codigo_sha256"]), {"analisador", "gerador", "aceite", "executor_corpus"})

    def test_activity_3_result_preserves_the_operation_correlation_milestone(self):
        path = corpus.DEFAULT_CORPUS.parent / "resultado-atividade-03.json"
        result = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(result["schema_resultado_corpus_regressao"], 1)
        self.assertEqual(result["status"], "reprovado")
        self.assertEqual(result["checks"], 226)
        self.assertEqual(result["aprovados"], 222)
        self.assertEqual(result["falhas"], 4)

    def test_activity_4_result_preserves_the_outcome_classification_milestone(self):
        path = corpus.DEFAULT_CORPUS.parent / "resultado-atividade-04.json"
        result = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(result["schema_resultado_corpus_regressao"], 1)
        self.assertEqual(result["status"], "reprovado")
        self.assertEqual(result["checks"], 226)
        self.assertEqual(result["aprovados"], 224)
        self.assertEqual(result["falhas"], 2)


if __name__ == "__main__":
    unittest.main()
