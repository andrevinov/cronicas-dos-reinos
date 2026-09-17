from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "ferramentas/gerar-avaliacao-sessao.py"
SPEC = importlib.util.spec_from_file_location("gerar_avaliacao_filas", GENERATOR)
generator = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(generator)


def row(
    module_id: str,
    *,
    applicability: str = "aplicavel",
    experience: float | None = None,
    adjudicated: int = 0,
    tokens: int = 0,
    share: float = 0.0,
    expected: int | None = None,
    missing: int | None = None,
    incomplete: int | None = None,
    duplicate: int | None = None,
) -> dict:
    return {
        "modulo": module_id,
        "aplicabilidade_avaliacao": applicability,
        "avaliacao_ativacao": (
            "falha de instrumentação"
            if applicability == "falha_instrumentacao"
            else "ativou a contento"
        ),
        "nota_experiencia_interacao_0a100": experience,
        "avaliacoes_qualidade_pontuaveis": adjudicated,
        "tokens_totais_atribuidos_fracionados": tokens,
        "participacao_tokens_fracionados_pct": share,
        "unidades_avaliativas_obrigatorias": expected,
        "recibos_cobertura_ausentes": missing,
        "recibos_cobertura_incompletos": incomplete,
        "recibos_cobertura_duplicados": duplicate,
    }


class IndependentPriorityQueuesTest(unittest.TestCase):
    def test_cost_mutation_cannot_change_repair_or_experience_queues(self) -> None:
        source = [
            row(
                "repair-half",
                applicability="falha_instrumentacao",
                tokens=10,
                expected=2,
                missing=1,
            ),
            row(
                "repair-all",
                applicability="falha_instrumentacao",
                tokens=900,
                expected=4,
                missing=4,
            ),
            row("experience-bad", experience=25, adjudicated=1, tokens=1),
            row("experience-good", experience=90, adjudicated=5, tokens=10_000),
        ]
        first = generator._assign_priority_queues(copy.deepcopy(source))
        mutated = copy.deepcopy(source)
        for item in mutated:
            item["tokens_totais_atribuidos_fracionados"] = (
                1 if item["tokens_totais_atribuidos_fracionados"] > 1 else 20_000
            )
        second = generator._assign_priority_queues(mutated)

        def ranks(rows: list[dict], field: str) -> dict[str, int | None]:
            return {item["modulo"]: item[field] for item in rows}

        self.assertEqual(
            ranks(first, "fila_reparo_medidor_rank"),
            ranks(second, "fila_reparo_medidor_rank"),
        )
        self.assertEqual(
            ranks(first, "fila_experiencia_rank"),
            ranks(second, "fila_experiencia_rank"),
        )
        self.assertEqual(ranks(first, "fila_reparo_medidor_rank")["repair-all"], 1)
        self.assertEqual(ranks(first, "fila_experiencia_rank")["experience-bad"], 1)
        self.assertNotEqual(
            ranks(first, "fila_investigacao_custo_rank"),
            ranks(second, "fila_investigacao_custo_rank"),
        )

    def test_experience_requires_explicit_adjudicated_denominator(self) -> None:
        rows = generator._assign_priority_queues(
            [
                row("numeric-without-evidence", experience=10, adjudicated=0),
                row("adjudicated", experience=75, adjudicated=1),
            ]
        )

        without_evidence, adjudicated = rows
        self.assertIsNone(without_evidence["fila_experiencia_rank"])
        self.assertIsNone(
            without_evidence["pontuacao_prioridade_experiencia_0a100"]
        )
        self.assertEqual(adjudicated["fila_experiencia_rank"], 1)
        self.assertEqual(adjudicated["pontuacao_prioridade_experiencia_0a100"], 25.0)

    def test_rows_keep_catalog_order_and_legacy_global_rank_is_disabled(self) -> None:
        source = [
            row("catalog-z", experience=100, adjudicated=1, tokens=1),
            row("catalog-a", experience=0, adjudicated=1, tokens=100),
        ]
        assigned = generator._assign_priority_queues(copy.deepcopy(source))

        self.assertEqual([item["modulo"] for item in assigned], ["catalog-z", "catalog-a"])
        self.assertTrue(all(item["prioridade_rank"] is None for item in assigned))
        self.assertTrue(
            all(item["pontuacao_prioridade_0a100"] is None for item in assigned)
        )
        self.assertTrue(
            all(item["prioridade_legada_descontinuada"] for item in assigned)
        )

    def test_accounting_cost_is_explicitly_non_causal(self) -> None:
        assigned = generator._assign_priority_queues(
            [row("cost", tokens=321, share=12.3456)]
        )[0]

        self.assertEqual(assigned["fila_investigacao_custo_rank"], 1)
        self.assertEqual(
            assigned["custo_atribuicao_contabil"],
            {
                "metodo": "divisao_inteira_igual_entre_modulos_pais_observados_no_turno_com_classe_controle_separada",
                "tokens_atribuidos": 321,
                "participacao_sessao_pct": 12.3456,
                "causalidade_inferida": False,
                "uso_permitido": "reconciliacao_contabil_e_triagem_para_investigacao",
            },
        )
        self.assertFalse(assigned["custo_exposto_participa_prioridade"])

    def test_scorecard_summary_has_three_independent_contiguous_queues(self) -> None:
        rows = generator._assign_priority_queues(
            [
                row(
                    "repair",
                    applicability="falha_instrumentacao",
                    expected=1,
                    missing=1,
                ),
                row("experience", experience=20, adjudicated=2),
                row("cost", tokens=900),
            ]
        )
        summary = generator._priority_queues_summary(rows)
        schema = json.loads(
            (ROOT / "evaluation/schemas/filas-prioridade-v2.schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(set(summary), set(schema["properties"]))
        self.assertFalse(summary["ranking_global_existe"])
        self.assertFalse(summary["custo_e_experiencia_misturados"])
        self.assertEqual(summary["reparo_medidor"]["module_ids"], ["repair"])
        self.assertEqual(
            summary["problemas_experiencia"]["module_ids"], ["experience"]
        )
        self.assertEqual(summary["investigacao_custo"]["module_ids"], ["cost"])
        self.assertFalse(summary["investigacao_custo"]["causalidade_inferida"])


if __name__ == "__main__":
    unittest.main()
