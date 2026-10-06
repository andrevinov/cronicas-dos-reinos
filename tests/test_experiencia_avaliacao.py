"""Finalidade, oportunidade e fontes históricas; cenários isolados do save."""
from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ferramentas import experiencia_avaliacao as experience
from ferramentas import verificar_aceite_avaliacao as acceptance

ROOT = Path(__file__).resolve().parents[1]
analyzer = acceptance.corpus._module(acceptance.corpus.ANALYZER, "experiencia_analyzer_test")
generator = acceptance.corpus._module(acceptance.corpus.GENERATOR, "experiencia_generator_test")
CATALOG = json.loads((ROOT / "evaluation/catalogo-modulos-v2.json").read_text())
BASE = json.loads((ROOT / "evaluation/aceite-avaliacao-v1/entradas/iniciativa_omitida.json").read_text())


class ExperienceReviewTest(unittest.TestCase):
    def test_native_envelope_preserves_writer_payload_and_uncorrelated_batch_output(self):
        raw = 'const payload = {deltas: [], memoria: {fatos: []}}; writer(payload)'
        output = '### npc\nresultado:\n  encontrado: false\n'
        turn = {"turn_id": "envelope-nativo", "user_messages": ["Falo com o NPC."],
                "calls": [{"call_id": "lote", "raw_input": raw, "output_text": output}]}
        _, private = experience.frames([turn], CATALOG,
            lambda _: {"text": "O NPC responde.", "source_line": 8},
            lambda _: [{"operation_id": "envelope-nativo/lote/0", "command": 'writer(${payload})',
                        "output_text": "", "output_success": None, "output_line": 6}], "fonte")
        frame = next(iter(private.values()))
        native = {source["kind"]: source for source in frame["sources"].values() if source["kind"].startswith("native_")}
        self.assertEqual(native["native_tool_input"]["text"], raw)
        self.assertEqual(native["native_tool_output"]["text"], output)
        self.assertTrue(all(source["visibility"] == "reservada" for source in native.values()))
        assessment = self.assessment(frame)
        assessment["evidence"].append(experience.evidence(native["native_tool_input"], raw))
        verified = experience.verify_reviews([assessment], private)[0]
        self.assertEqual(verified["review"]["verification"], "verificada")
        exported = json.dumps(experience.export_assessment(verified))
        self.assertNotIn(raw, exported)
        self.assertIsNone(frame["descriptor"]["operations"][0]["success"])
        abstention = copy.deepcopy(verified)
        abstention["quality"] = "indeterminada"
        abstention["adjudication"]["state"] = "indeterminada"
        abstention["review"]["decision_state"] = "fontes_insuficientes"
        abstention["review"]["diagnosis"] = {"stage": "indeterminada", "finding": "Fonte privada ausente",
            "correction": "Preservar fonte anterior", "test": "Comparar presença/ausência da fonte"}
        public_abstention = experience.export_assessment(abstention)
        self.assertEqual(public_abstention["review"]["public_diagnosis"]["finding"],
                         "Fontes insuficientes para concluir este critério.")
        later = {"turn_id": "outro-turno", "user_messages": ["E agora?"], "calls": []}
        _, contexts = experience.frames([turn, later], CATALOG,
            lambda _: {"text": "O NPC responde.", "source_line": 8},
            lambda item: [] if item is later else [{"operation_id": "envelope-nativo/lote/0", "command": "writer",
                        "output_text": "", "output_success": None, "output_line": 6}], "fonte")
        subsequent = list(contexts.values())[-1]
        inherited = next(source for source in subsequent["sources"].values()
                         if source["kind"] == "historical_native_tool_output")
        self.assertEqual(inherited["text"], output)
        self.assertEqual(inherited["visibility"], "reservada")
        self.assertTrue(inherited["available_before_response"])

    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "episodio.jsonl"

    def analyze(self, response=None, context=None, input_text=None):
        records = copy.deepcopy(BASE["registros"])
        if response is not None:
            records[-1]["payload"]["content"][0]["text"] = response
        if context is not None:
            records[1]["payload"]["output"] = context
        if input_text is not None:
            records[2]["payload"]["content"][0]["text"] = input_text
        self.path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n")
        return analyzer.analyze(self.path)["modular_ledger_v2"]

    def frame(self):
        ordered = analyzer._scan_observations(self.path, None)[0]
        return next(iter(experience.frames(ordered, CATALOG, analyzer._visible_response,
                                           analyzer._turn_operations, experience.digest(self.path.read_text()))[1].values()))

    def assessment(self, frame, state="confirmada", quality="inadequada"):
        ref = frame["descriptor"]["evaluation_ref"]
        return {"schema_quality_assessment": 1, "assessment_id": "parecer-cena",
                "interaction_ref": ref, "module_id": "narrative_delivery", "capability_id": "narrative_density",
                "criterion_id": "narrative_delivery.narrative_density", "evaluator": "revisor-poshoc-do-teste",
                "eligibility": "sim", "activation": "presente", "quality": quality,
                "evidence": [experience.evidence(frame["sources"][ref + "/input"], frame["sources"][ref + "/input"]["text"]),
                             experience.evidence(frame["sources"][ref + "/response"], frame["sources"][ref + "/response"]["text"])],
                "adjudication": {"state": state, "reason": "Aviso devido foi ignorado, sem impedimento observado."},
                "review": experience.review(frame, "revisor-poshoc-do-teste")}

    def test_same_operations_different_fiction_changes_opportunity_without_npc_receipt(self):
        omitted = self.analyze()["quality_assessments"]
        delivered = self.analyze("O vigia avisa os moradores da cheia.")["quality_assessments"]
        self.assertEqual(omitted[0]["activation"], "ausente")
        self.assertEqual(delivered[0]["activation"], "presente")
        self.assertEqual(generator._interaction_quality_metrics(omitted)["oportunidades_perdidas"], 1)
        self.assertEqual(generator._interaction_quality_metrics(delivered)["oportunidades_perdidas"], 0)
        self.assertIsNone(generator._interaction_quality_metrics(delivered)["nota_qualidade_0a100"])

    def test_strategic_silence_no_perception_and_absent_actor_are_valid_negatives(self):
        original = BASE["registros"][1]["payload"]["output"]
        for before, after in [("impedimentos: []", "impedimentos: [silencio_estrategico]"),
                              ("cheia_confirmada", "apenas_narrador"),
                              ("elenco_presente: [vigia]", "elenco_presente: []")]:
            ledger = self.analyze(context=original.replace(before, after))
            metrics = generator._interaction_quality_metrics(ledger["quality_assessments"])
            with self.subTest(after=after):
                self.assertEqual(metrics["oportunidades_perdidas"], 0)
                self.assertEqual(metrics["matriz_oportunidade"]["verdadeiro_negativo"], 1)

    def test_missing_knowledge_rumor_and_off_do_not_manufacture_opportunities(self):
        original = BASE["registros"][1]["payload"]["output"]
        for context, user in [(original.replace("conhecimento_vigia: cheia_confirmada\n", ""), None),
                              (original.replace("cheia_confirmada", "rumor_de_cheia"), None),
                              (original, "[Apenas consulte a cena, sem avançar.]")]:
            ledger = self.analyze(context=context, input_text=user)
            self.assertFalse(ledger["quality_assessments"])

    def test_literal_binding_detects_changed_final_and_rejects_writer_as_response(self):
        self.analyze()
        frame = self.frame(); item = self.assessment(frame)
        verified = experience.verify_reviews([item], {frame["descriptor"]["evaluation_ref"]: frame})
        self.assertTrue(experience.scoreable(verified[0]))
        item["evidence"][-1]["literal"] = "O vigia transmitiu o aviso."
        with self.assertRaisesRegex(ValueError, "literal divergente"):
            experience.verify_reviews([item], {frame["descriptor"]["evaluation_ref"]: frame})
        item = self.assessment(frame)
        self.analyze("O vigia avisa os moradores da cheia.")
        changed = self.frame()
        with self.assertRaisesRegex(ValueError, "vínculo"):
            experience.verify_reviews([item], {changed["descriptor"]["evaluation_ref"]: changed})

    def test_pending_conflict_incomplete_and_producer_cannot_confirm_quality(self):
        self.analyze(); frame = self.frame(); ref = frame["descriptor"]["evaluation_ref"]
        for condition in ["pendente", "conflict", "incomplete", "producer"]:
            current = copy.deepcopy(frame); item = self.assessment(current, quality="adequada")
            if condition == "pendente":item["adjudication"]["state"] = "pendente"
            elif condition == "conflict":item["review"]["conflicts"] = ["Fonte anterior diverge."]
            elif condition == "incomplete":current["descriptor"]["complete"] = False
            else:item["review"]["reviewer_role"] = "produtor"
            result = experience.verify_reviews([item], {ref: current})
            with self.subTest(condition=condition):
                self.assertEqual(generator._interaction_quality_metrics(result)["denominador_qualidade"], 0)

    def test_reserved_excerpts_are_redacted_and_export_can_be_reverified(self):
        ledger = self.analyze(); frame = self.frame(); ref = frame["descriptor"]["evaluation_ref"]
        exported = ledger["quality_assessments"][0]
        self.assertNotIn("cheia_confirmada", json.dumps(exported))
        result = experience.verify_reviews([exported], {ref: frame})
        self.assertTrue(experience.scoreable(result[0]))
        result[0]["evidence"][0]["visibility"] = "publica"
        with self.assertRaisesRegex(ValueError, "reservada"):
            experience.verify_reviews(result, {ref: frame})

    def test_isolated_import_cannot_forge_verified_review(self):
        ledger = self.analyze(); frame = self.frame(); item = self.assessment(frame, quality="adequada")
        item["review"]["verification"] = "verificada"
        result = analyzer.apply_modular_adjudications(ledger, {"schema_adjudicacoes_modulares": 2, "quality_assessments": [item]})
        self.assertFalse(experience.scoreable(result["quality_assessments"][-1]))

    def test_generator_keeps_missed_opportunity_visible_with_zero_module_activity(self):
        ledger = self.analyze()
        targets = json.loads((ROOT / "evaluation/metas-avaliacao-v2.json").read_text())
        rows = generator._module_summary_v2(CATALOG["modulos"], ledger, [], targets, 0)
        npc = next(row for row in rows if row["modulo"] == "npc_continuity_and_social_behavior")
        self.assertEqual(npc["oportunidades_qualitativas_perdidas"], 1)
        self.assertEqual(npc["estado_experiencia"], "provisoria")
        self.assertIn("omissão", npc["principais_problemas_de_ativacao"])
        self.assertIsNone(npc["nota_conformidade_operacional_0a100"])

    def test_semantic_pair_scores_visible_outcome_and_not_equal_tool_execution(self):
        values = []
        for response, quality in [("O vigia permanece parado. A conversa termina sem aviso.", "inadequada"),
                                  ("O vigia avisa os moradores da cheia.", "adequada")]:
            ledger = self.analyze(response); frame = self.frame()
            item = self.assessment(frame, quality=quality)
            reviewed = analyzer.adjudicate_rollout(ledger, {"schema_adjudicacoes_modulares": 2, "quality_assessments": [item]}, self.path)
            relevant = [x for x in reviewed["quality_assessments"] if x["module_id"] == "narrative_delivery"]
            values.append(generator._interaction_quality_metrics(relevant)["nota_qualidade_0a100"])
        self.assertEqual(values, [0, 100])

    def test_pending_operation_dependency_blocks_positive_review(self):
        self.analyze(); frame = self.frame(); item = self.assessment(frame, quality="adequada")
        op = frame["descriptor"]["operations"][0]
        item["review"]["dependency_operation_ids"] = [op["operation_id"]]
        op["success"] = None
        verified = experience.verify_reviews([item], {frame["descriptor"]["evaluation_ref"]: frame})
        self.assertFalse(experience.scoreable(verified[0]))

    def test_conflicting_reviewers_are_excluded_from_metrics(self):
        ledger = self.analyze(); frame = self.frame(); one = self.assessment(frame)
        two = copy.deepcopy(one); two["assessment_id"] = "parecer-concorrente"; two["quality"] = "adequada"
        result = analyzer.adjudicate_rollout(ledger, {"schema_adjudicacoes_modulares": 2, "quality_assessments": [one, two]}, self.path)
        relevant = [x for x in result["quality_assessments"] if x["module_id"] == "narrative_delivery"]
        self.assertEqual(generator._interaction_quality_metrics(relevant)["denominador_qualidade"], 0)

    def test_guardrail_is_not_averaged_with_other_positive_criteria(self):
        self.analyze(); frame = self.frame(); item = self.assessment(frame, quality="inadequada")
        item["review"]["guardrails"] = {"player_agency": "violado"}
        verified = experience.verify_reviews([item], {frame["descriptor"]["evaluation_ref"]: frame})
        metrics = generator._interaction_quality_metrics(verified)
        self.assertIsNone(metrics["nota_experiencia_0a100"])
        self.assertEqual(metrics["violacoes_guardrail"], ["parecer-cena"])

    def test_player_complaint_even_partially_adjudicated_is_not_factual_opportunity(self):
        ledger = self.analyze()
        ledger["player_feedback"] = [{"perceived_type": "sobreativacao_percebida", "player_module_id": "narrative_delivery",
                                      "original_text": "Foi uma péssima escolha.", "adjudication": {"state": "parcial", "reason": "Em revisão."}}]
        targets = json.loads((ROOT / "evaluation/metas-avaliacao-v2.json").read_text())
        row = next(r for r in generator._module_summary_v2(CATALOG["modulos"], ledger, [], targets, 0)
                   if r["modulo"] == "narrative_delivery")
        self.assertEqual(row["manifestacoes_jogador"], 1)
        self.assertEqual(row["falsos_positivos"], 0)
        self.assertIsNone(row["nota_experiencia_interacao_0a100"])

    def test_full_package_consumes_review_and_regeneration_does_not_duplicate_it(self):
        self.analyze(); frame = self.frame(); item = self.assessment(frame)
        imported = Path(self.temp.name) / "pareceres.json"
        imported.write_text(json.dumps({"schema_adjudicacoes_modulares": 2, "quality_assessments": [item]}))
        output = Path(self.temp.name) / "pacote"
        for adjudications in (imported, None):
            generator.generate_session_evaluation(self.path, session_id="999", output_dir=output,
                                                   adjudications_path=adjudications)
            data = json.loads((output / "avaliacoes-qualidade.json").read_text())
            self.assertEqual(len(data["assessments"]), 2)
            self.assertEqual(len(data["experience_review"]["frames"]), 1)
            self.assertTrue(all(experience.scoreable(row) for row in data["assessments"]))
            self.assertNotIn("cheia_confirmada", (output / "avaliacoes-qualidade.json").read_text())


if __name__ == "__main__":
    unittest.main()
