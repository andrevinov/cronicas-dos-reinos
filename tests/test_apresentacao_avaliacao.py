"""Conclusões não se fortalecem pela exclusão de evidência ou por economia."""
import copy
import unittest

from ferramentas import apresentacao_avaliacao as view


def assessment(**changes):
    result = {"assessment_id": "review", "module_id": "npc", "quality": "adequada",
              "eligibility": "sim", "activation": "presente",
              "adjudication": {"state": "confirmada"},
              "review": {"verification": "verificada", "conflicts": [], "guardrails": {}}}
    result.update(changes)
    return result


class EvaluationPresentationTest(unittest.TestCase):
    def publish(self, reviews, *, critical=False):
        card = {"nota_geral_0a100": 100, "conclusao_medicao": {"permitida": True},
                "agregacao_modular": {"conclusao_permitida": True},
                "violacoes_criticas": [{"guardrail": "agency"}] if critical else []}
        rows = [{"modulo": "npc", "versao_implementacao": "1.0", "versao_avaliacao": "4.0",
                 "tokens_totais_atribuidos_fracionados": 100}]
        ledger = {"quality_assessments": reviews, "module_parent_costs": [{"total_tokens": 100}],
                  "experience_review": {"frames": [{"criteria": {"npc.voice": {
                      "state": "confirmada" if reviews else "nao_avaliada",
                      "assessment_id": "review" if reviews else None,
                      "opportunity": "atendida" if reviews else "indeterminada"}}}]}}
        view.publish(card, rows, ledger, {"narration_turns": {"input_tokens": 80, "output_tokens": 20}},
                     {"rubrica": "1"}, {}, {"modulos": [{"id": "npc", "versao_avaliacao": "4.1"}]})
        return card, rows

    def test_operacao_cem_nao_aprova_qualidade_zero(self):
        card, rows = self.publish([assessment(quality="inadequada")])
        self.assertEqual(card["nota_operacional_parcial_0a100"], 100)
        self.assertEqual(rows[0]["leitura_experiencia"]["estado"], "inadequada_no_criterio")
        self.assertFalse(card["apresentacao"]["conclusao_global_permitida"])
        self.assertIsNone(card["apresentacao"]["nota_global_publicavel"])

    def test_ausencia_insuficiencia_e_negativa_sao_diferentes(self):
        self.assertEqual(view.quality_state([]), "nao_avaliada")
        self.assertEqual(view.quality_state([assessment(adjudication={"state": "indeterminada"})]), "fontes_insuficientes")
        self.assertEqual(view.quality_state([assessment(eligibility="nao", activation="ausente")]), "negativa_valida")
        self.assertEqual(view.quality_state([assessment()]), "amostra_insuficiente_para_generalizar")
        self.assertEqual(view.quality_state([assessment(review=None)]), "fontes_insuficientes")

    def test_violacao_nao_e_compensada_e_custo_fecha_uma_vez(self):
        card, rows = self.publish([assessment(review={"verification": "verificada", "conflicts": [],
                                                       "guardrails": {"agency": "violado"}})], critical=True)
        self.assertEqual(card["apresentacao"]["validade"], "comprometida_guardrail")
        self.assertEqual(card["apresentacao"]["qualidade"], "violacao_critica")
        self.assertEqual(card["custos"]["diferenca_fechamento"], 0)
        self.assertEqual(card["custos"]["observado"], rows[0]["custo"]["compartilhado_alocado"])
        self.assertIsNone(card["custos"]["marginal"])
        self.assertIsNone(card["custos"]["exclusivo_observado"])

    def test_indeterminados_nao_apagam_cobertura_nem_criam_conclusao(self):
        card, rows = self.publish([])
        self.assertEqual(card["apresentacao"]["cobertura"]["sem_parecer"], 1)
        self.assertEqual(rows[0]["leitura_experiencia"]["pendencias"], 1)
        self.assertEqual(rows[0]["versao_avaliacao"], "4.0")
        self.assertEqual(rows[0]["versao_avaliador_revisao"], "4.1")
        self.assertFalse(card["apresentacao"]["conclusao_global_permitida"])

    def test_comparabilidade_e_por_modulo_e_por_recorte_de_custo(self):
        def keys(implementation="1.0", detector="1", turn_count=2, catalog_version="1"):
            rows = [{"modulo": name, "versao_implementacao": implementation if name == "npc" else "1.0",
                     "versao_avaliacao": "4.0"} for name in ("npc", "narrative")]
            view.publish({"nota_geral_0a100": 100}, rows, {}, {"narration_turns": {"turns": turn_count}},
                         {"detector": detector, "catalogo_modulos": catalog_version}, {},
                         {"modulos": [{"id": name, "versao_avaliacao": "4.1"} for name in ("npc", "narrative")]})
            return {r["modulo"]: r["comparabilidade"] for r in rows}
        baseline = keys()
        changed_module = keys(implementation="2.0", catalog_version="2")
        self.assertNotEqual(baseline["npc"], changed_module["npc"])
        self.assertEqual(baseline["narrative"], changed_module["narrative"])
        self.assertNotEqual(baseline["narrative"], keys(detector="2")["narrative"])
        self.assertNotEqual(baseline["npc"]["custo"], keys(turn_count=3)["npc"]["custo"])
        self.assertEqual(baseline["npc"]["qualidade"], keys(turn_count=3)["npc"]["qualidade"])
