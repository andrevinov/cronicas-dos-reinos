"""Propriedades da revisão pós-sessão em episódios isolados e histórico congelado.

Replay verifica pipeline e sensibilidade às decisões registradas. A execução
semântica original está no pacote de aceite, não é simulada por este teste.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import unittest
from tempfile import TemporaryDirectory

from ferramentas import entrada_medicao as frozen
from ferramentas import revisao_sessao as workflow
from ferramentas import verificar_revisao_experiencia as benchmark

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = benchmark.check_reference()
EPISODES = workflow.load(benchmark.CORPUS / MANIFEST["active_corpus"])["episodes"]
JUDGMENTS = {case["id"]: case for case in workflow.load(benchmark.CORPUS / "pareceres-executados.json")["cases"]}


class SessionReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def episode(self, identifier="e01v2", *, full=False):
        episode = next(case for case in EPISODES if case["id"] == identifier)
        path = self.root / f"{identifier}.jsonl"
        path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in episode["records"]) + "\n")
        bundle = frozen.prepare_input(path, session_id="999")
        request = workflow.prepare(path, bundle, criterion_ids=None if full else [episode["criterion_id"]])
        judgment = copy.deepcopy(JUDGMENTS[identifier]["submission"])
        judgment["request_id"] = request["request_id"]
        return path, bundle, request, judgment

    def test_all_episode_sources_keep_intention_and_reference_out_of_reviewer_input(self):
        for episode in EPISODES:
            _, _, request, _ = self.episode(episode["id"])
            frame = workflow.cases(request)["cases"][0]
            with self.subTest(case=episode["id"]):
                self.assertTrue(frame["complete"])
                self.assertTrue(next(source["text"] for source in frame["sources"] if source["kind"] == "input"))
                self.assertNotIn("checks", request)
                self.assertNotIn("property", request)
                self.assertNotIn("expected", request)

    def test_default_scope_cannot_close_after_one_of_thirty_four_criteria(self):
        _, _, request, judgment = self.episode(full=True)
        self.assertEqual(len(request["required_units"]), 34)
        self.assertEqual(request["scope"], "integral")
        with self.assertRaisesRegex(ValueError, "incompleta"):
            workflow.compile_reviews(request, judgment)

    def test_duplicate_foreign_literal_and_producer_decisions_cannot_publish(self):
        _, _, request, judgment = self.episode()
        for failure in ("duplicate", "foreign", "quote", "producer"):
            changed = copy.deepcopy(judgment)
            if failure == "duplicate":
                changed["decisions"].append(changed["decisions"][0])
            elif failure == "foreign":
                changed["decisions"][0]["criterion_id"] = "narrative_delivery.visible_closure"
            elif failure == "quote":
                changed["decisions"][0]["evidence"][-1]["quote"] = "Texto que a fonte nunca apresentou."
            else:
                changed["reviewer"]["role"] = "produtor"
            with self.subTest(failure=failure), self.assertRaises((ValueError, KeyError)):
                workflow.compile_reviews(request, changed)

    def test_known_omission_needs_actionable_diagnosis_and_cause_limit(self):
        _, _, request, judgment = self.episode()
        for failure in ("missing", "invented_stage", "unproved_cause", "overactivation"):
            changed = copy.deepcopy(judgment)
            if failure == "missing":
                changed["decisions"][0]["diagnosis"] = None
            elif failure == "invented_stage":
                changed["decisions"][0]["diagnosis"]["stage"] = "certeza_sem_fonte"
            elif failure == "unproved_cause":
                changed["decisions"][0]["diagnosis"]["cause_status"] = "confirmada_por_reproducao"
            else:
                changed["decisions"][0].update({"eligibility": "nao", "activation": "presente", "quality": "adequada", "diagnosis": None})
            with self.subTest(failure=failure), self.assertRaises(ValueError):
                workflow.compile_reviews(request, changed)

    def test_same_successful_operations_distinguish_prose_without_npc_receipt(self):
        compiled = []
        descriptors = []
        for identifier in ("e01v1", "e01v2"):
            _, _, request, judgment = self.episode(identifier)
            compiled.append(workflow.compile_reviews(request, judgment)["quality_assessments"][0])
            descriptors.append(request["frames"][0]["operations"])
        self.assertEqual(descriptors[0], descriptors[1])
        self.assertEqual([item["activation"] for item in compiled], ["presente", "ausente"])
        self.assertTrue(all(operation["success"] for operation in descriptors[0]))
        self.assertNotIn("npc", json.dumps(descriptors))

    def test_publish_is_atomic_idempotent_and_expurgates_private_evidence(self):
        path, bundle, request, judgment = self.episode()
        output = self.root / "pacote"
        before = path.read_bytes()
        result = workflow.publish(path, bundle, request, judgment, output)
        self.assertEqual(result, workflow.publish(path, bundle, request, judgment, output))
        self.assertEqual(path.read_bytes(), before)
        score = workflow.load(output / "scorecard.json")
        self.assertEqual(score["revisao_semantica"]["units_reviewed"], 1)
        self.assertEqual(score["revisao_semantica"]["scope"], "parcial_declarado")
        self.assertIsNone(score["nota_geral_0a100"])
        self.assertEqual(score["filas_prioridade"]["problemas_experiencia"]["module_ids"], ["npc_continuity_and_social_behavior"])
        exported = (output / "avaliacoes-qualidade.json").read_text()
        self.assertNotIn("conhecimento_Ilara", exported)
        self.assertFalse((output / "entrada-revisao.json").exists())
        (output / "scorecard.json").unlink()
        with self.assertRaisesRegex(ValueError, "incompleto"):
            workflow.publish(path, bundle, request, judgment, output)

    def test_unreviewed_run_and_changed_source_leave_no_public_package(self):
        path, bundle, request, judgment = self.episode()
        output = self.root / "publico"
        judgment["decisions"] = []
        with self.assertRaisesRegex(ValueError, "incompleta"):
            workflow.publish(path, bundle, request, judgment, output)
        self.assertFalse(output.exists())
        path.write_text(path.read_text().replace("Ilara", "Outro_ator"))
        with self.assertRaises(ValueError):
            workflow.publish(path, bundle, request, judgment, output)
        self.assertFalse(output.exists())

    def test_append_after_frozen_cut_does_not_change_the_reviewed_episode(self):
        path, bundle, request, judgment = self.episode()
        with path.open("a") as handle:
            handle.write(json.dumps({"type": "compacted", "payload": {}}) + "\n")
        result = workflow.publish(path, bundle, request, judgment, self.root / "pacote")
        self.assertEqual(result["request_id"], request["request_id"])

    def test_critical_violation_stays_first_even_with_null_experience_score(self):
        path, bundle, request, judgment = self.episode("e11v2")
        workflow.publish(path, bundle, request, judgment, self.root / "pacote")
        rows = workflow.load(self.root / "pacote/resumo-modulos.json")["modulos"]
        narrative = next(row for row in rows if row["modulo"] == "narrative_delivery")
        self.assertIsNone(narrative["nota_experiencia_interacao_0a100"])
        self.assertEqual(narrative["fila_experiencia_rank"], 1)
        self.assertTrue(narrative["violacoes_guardrail_experiencia"])

    def test_recorded_review_replay_is_explicit_and_always_positive_mutation_fails(self):
        benchmark.prepare_episodes(self.root)
        replay = benchmark.measure(self.root, benchmark.CORPUS / "pareceres-executados.json", replay=True)
        self.assertEqual(replay["status"], "aprovado")
        self.assertEqual(replay["cases"], 24)
        self.assertIn("replay", replay["mode"])
        changed = workflow.load(benchmark.CORPUS / "pareceres-executados.json")
        for case in changed["cases"]:
            decision = case["submission"]["decisions"][0]
            decision.update({"state": "avaliada", "eligibility": "sim", "activation": "presente", "quality": "adequada", "guardrails": {}, "diagnosis": None})
        fake = self.root / "aprovacao-indiscriminada.json"
        fake.write_text(json.dumps(changed, ensure_ascii=False))
        measured = benchmark.measure(self.root, fake, replay=True)
        self.assertEqual(measured["status"], "reprovado")
        self.assertLess(measured["passed_checks"], measured["checks"])


if __name__ == "__main__":
    unittest.main()
