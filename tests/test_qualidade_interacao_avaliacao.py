from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ANALYZER = ROOT / "ferramentas/analisar-rollout.py"
GENERATOR = ROOT / "ferramentas/gerar-avaliacao-sessao.py"
ANALYZER_SPEC = importlib.util.spec_from_file_location(
    "analisar_rollout_qualidade", ANALYZER
)
analyzer = importlib.util.module_from_spec(ANALYZER_SPEC)
assert ANALYZER_SPEC.loader is not None
ANALYZER_SPEC.loader.exec_module(analyzer)
SPEC = importlib.util.spec_from_file_location("gerar_avaliacao_qualidade", GENERATOR)
generator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(generator)


def assessment(
    assessment_id: str,
    interaction_ref: str,
    *,
    eligibility: str = "sim",
    activation: str = "presente",
    quality: str = "adequada",
    state: str = "confirmada",
    criterion_id: str = "turnos_com_fechamento_jogavel_claro",
) -> dict:
    return {
        "schema_quality_assessment": 1,
        "assessment_id": assessment_id,
        "interaction_ref": interaction_ref,
        "module_id": "narrative_delivery",
        "capability_id": "visible_closure",
        "criterion_id": criterion_id,
        "evaluator": "fixture-humana",
        "eligibility": eligibility,
        "activation": activation,
        "quality": quality,
        "evidence": [
            {
                "source": "interaction",
                "locator": f"{interaction_ref}/response",
                "observation": "A consequência narrada está explicitamente identificada.",
                "visibility": "publica",
            }
        ],
        "adjudication": {
            "state": state,
            "reason": "Revisão humana da interação congelada.",
        },
    }


def ledger(*refs: str) -> dict:
    return {
        "interactions": [
            {"interaction_ref": reference, "response_present": True}
            for reference in refs
        ],
        "events": [],
        "corrections": [],
        "semantic_audits": [],
        "quality_assessments": [],
        "player_feedback": [],
        "module_parent_costs": [],
    }


def adjudications(*items: dict) -> dict:
    return {
        "schema_adjudicacoes_modulares": 2,
        "corrections": [],
        "semantic_audits": [],
        "quality_assessments": list(items),
        "player_feedback": [],
    }


def narrative_catalog() -> list[dict]:
    return [
        {
            "id": "narrative_delivery",
            "responsabilidade": "entregar narração",
            "visibilidade_jogador": "direta",
            "rotulo_jogador": "Narração",
            "versao_implementacao": "1.0.2",
            "versao_avaliacao": "4.0.0",
            "subcapacidades": [
                {"id": "visible_closure", "responsabilidade": "fechar o turno"}
            ],
        }
    ]


class InteractionQualityLedgerTest(unittest.TestCase):
    def test_missed_opportunity_exists_without_detected_module_event(self) -> None:
        item = assessment(
            "quality-missed",
            "S023-I0001",
            activation="ausente",
            quality="nao_aplicavel",
        )
        applied = analyzer.apply_modular_adjudications(
            ledger("S023-I0001"), adjudications(item)
        )

        self.assertEqual(applied["quality_assessments"][0], item)
        rows = generator._module_summary_v2(
            narrative_catalog(),
            applied,
            [],
            json.loads(generator.DEFAULT_TARGETS.read_text(encoding="utf-8")),
            0,
        )
        row = rows[0]
        self.assertEqual(row["avaliacoes_qualidade_pontuaveis"], 1)
        self.assertEqual(row["oportunidades_qualitativas_perdidas"], 1)
        self.assertEqual(row["nota_oportunidade_interacao_0a100"], 0.0)
        self.assertIsNone(row["nota_qualidade_interacao_0a100"])
        self.assertEqual(row["nota_experiencia_interacao_0a100"], 0.0)

    def test_operational_conformity_does_not_manufacture_interaction_quality(self) -> None:
        source = ledger("S023-I0001")
        source["events"] = [
            {
                "event_id": "delivery",
                "module_id": "narrative_delivery",
                "capability_id": "visible_closure",
                "turn_ordinal": 1,
                "call_ids_observed": ["call-1"],
                "eligibility_observed": "sim",
                "activation_observed": "efeito",
                "effect_observed": True,
                "inference_confidence": "alta",
                "adjudication": None,
            }
        ]

        row = generator._module_summary_v2(
            narrative_catalog(),
            source,
            [],
            json.loads(generator.DEFAULT_TARGETS.read_text(encoding="utf-8")),
            0,
        )[0]

        self.assertEqual(row["nota_conformidade_operacional_0a100"], 100.0)
        self.assertEqual(row["efeitos_conformidade_operacional_avaliaveis"], 1)
        self.assertIsNone(row["nota_qualidade_interacao_0a100"])
        self.assertEqual(row["qualidade_interacao_status"], "nao_avaliada")

    def test_only_confirmed_assessments_enter_explicit_denominators(self) -> None:
        items = [
            assessment("quality-ok", "S023-I0001"),
            assessment(
                "quality-bad",
                "S023-I0002",
                quality="inadequada",
            ),
            assessment(
                "quality-pending",
                "S023-I0003",
                quality="inadequada",
                state="pendente",
            ),
        ]
        applied = analyzer.apply_modular_adjudications(
            ledger("S023-I0001", "S023-I0002", "S023-I0003"),
            adjudications(*items),
        )
        row = generator._module_summary_v2(
            narrative_catalog(),
            applied,
            [],
            json.loads(generator.DEFAULT_TARGETS.read_text(encoding="utf-8")),
            0,
        )[0]

        self.assertEqual(row["avaliacoes_qualidade_recebidas"], 3)
        self.assertEqual(row["avaliacoes_qualidade_confirmadas"], 2)
        self.assertEqual(row["avaliacoes_qualidade_pendentes"], 1)
        self.assertEqual(row["avaliacoes_qualidade_pontuaveis"], 2)
        self.assertEqual(row["denominador_qualidade_interacao"], 2)
        self.assertEqual(row["nota_qualidade_interacao_0a100"], 50.0)
        self.assertEqual(row["denominador_oportunidade_qualitativa"], 2)
        self.assertEqual(row["nota_oportunidade_interacao_0a100"], 100.0)
        self.assertEqual(row["nota_experiencia_interacao_0a100"], 75.0)
        scorecard = generator._scorecard_v2(
            "023",
            {"narration_turns": {}},
            applied,
            [row],
            {"violacoes_criticas": []},
            {"narration_turns": {}},
            json.loads(generator.DEFAULT_TARGETS.read_text(encoding="utf-8")),
            [],
        )
        self.assertEqual(scorecard["qualidade_interacao"]["avaliacoes_recebidas"], 3)
        self.assertEqual(scorecard["qualidade_interacao"]["avaliacoes_pontuaveis"], 2)
        self.assertEqual(scorecard["qualidade_interacao"]["modulos_com_nota_qualidade"], 1)

    def test_duplicate_unit_unknown_criterion_and_empty_evidence_fail_closed(self) -> None:
        first = assessment("quality-1", "S023-I0001")
        duplicate = assessment("quality-2", "S023-I0001")
        with self.assertRaisesRegex(analyzer.RolloutError, "duplicada"):
            analyzer.apply_modular_adjudications(
                ledger("S023-I0001"), adjudications(first, duplicate)
            )

        unknown = assessment(
            "quality-unknown",
            "S023-I0001",
            criterion_id="criterio_inventado",
        )
        with self.assertRaisesRegex(analyzer.RolloutError, "não pertence"):
            analyzer.apply_modular_adjudications(
                ledger("S023-I0001"), adjudications(unknown)
            )

        without_evidence = assessment("quality-empty", "S023-I0001")
        without_evidence["evidence"] = []
        with self.assertRaisesRegex(analyzer.RolloutError, "não pode ser vazio"):
            analyzer.apply_modular_adjudications(
                ledger("S023-I0001"), adjudications(without_evidence)
            )

    def test_reserved_evidence_is_hashed_before_entering_the_public_ledger(self) -> None:
        item = assessment("quality-reserved", "S023-I0001")
        item["evidence"] = [
            {
                "source": "canonical",
                "locator": "narrador/segredo/exemplo",
                "observation": "conteúdo reservado usado somente na adjudicação",
                "visibility": "reservada",
            }
        ]

        applied = analyzer.apply_modular_adjudications(
            ledger("S023-I0001"), adjudications(item)
        )
        evidence = applied["quality_assessments"][0]["evidence"][0]

        self.assertTrue(evidence["locator"].startswith("sha256:"))
        self.assertTrue(evidence["observation"].startswith("sha256:"))
        self.assertNotIn("segredo", json.dumps(applied, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
