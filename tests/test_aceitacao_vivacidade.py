from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import aceitacao_vivacidade as acceptance
import fronteira_vivacidade as live
import mundo
import preflight


class IntegratedVivacityAcceptanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = acceptance.load_fixture(ROOT)

    def test_dia_carregado_da_destino_a_todas_as_causas_sem_descarte(self):
        result = acceptance.evaluate_episode(
            acceptance.LOADED,
            self.fixture["episodios"][acceptance.LOADED],
        )
        self.assertTrue(result["ok"])
        self.assertFalse(result["calma_justificada"])
        self.assertEqual(
            result["destinos"]["mensagem:nera-aviso"],
            "entregue",
        )
        self.assertEqual(
            result["destinos"]["compromisso:audiencia-circo"],
            "entregue",
        )
        self.assertEqual(
            result["destinos"]["causa-nv11:ajuda-silva"],
            "entregue",
        )
        self.assertEqual(
            result["destinos"]["mensagem:segredo-sem-canal"],
            "bloqueada",
        )
        self.assertEqual(result["pendentes_apos_alvo"], [])
        self.assertEqual(result["iniciativa"]["decisoes"], 2)
        self.assertEqual(result["iniciativa"]["apresentadas"], 1)
        self.assertEqual(
            result["permanencia"]["local_id"],
            "jack_mooney_sons_circus",
        )
        self.assertLessEqual(result["bytes"], live.MAX_OUTPUT_BYTES)

    def test_dia_carregado_prova_cadeias_causais_semanticas(self):
        result = acceptance.evaluate_episode(
            acceptance.LOADED,
            self.fixture["episodios"][acceptance.LOADED],
        )
        edges = set(result["grafo_semantico"]["arestas_obrigatorias"])
        for source, target in acceptance.REQUIRED_SEMANTIC_EDGES:
            self.assertIn(f"{source}->{target}", edges)
        systems = set(result["grafo_semantico"]["sistemas"])
        self.assertIn("politica_civica", systems)
        self.assertIn("clima_diario", systems)
        self.assertIn("presenca_incidental", systems)
        self.assertIn("mecanica_gate", systems)
        self.assertIn("consequencia_relacional", systems)
        self.assertIn("consequencia_reputacao", systems)
        self.assertIn("permanencia_espacial", systems)
        self.assertIn("cronica", systems)

    def test_dia_legitimamente_calmo_emite_recibo_em_todas_as_janelas(self):
        result = acceptance.evaluate_episode(
            acceptance.CALM,
            self.fixture["episodios"][acceptance.CALM],
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["calma_justificada"])
        self.assertEqual(result["eventos_substantivos"], 0)
        self.assertEqual(result["recibos_calma"], result["janelas"])
        self.assertEqual(result["iniciativa"]["decisoes"], 0)
        self.assertLessEqual(result["bytes"], live.MAX_OUTPUT_BYTES)

    def test_rollout_operacional_e_analisado_por_ordem_causal_e_sucesso(self):
        result = acceptance.analyze_operational_rollout(ROOT)
        self.assertTrue(result["ok"])
        self.assertEqual(
            [item["etapa"] for item in result["cadeia_semantica"]],
            ["contexto", "mecanica", "writer"],
        )
        self.assertIn("ordem causal", result["avaliacao"])
        self.assertIn("writer", result["avaliacao"])

    def test_regressoes_obrigatorias_estao_ancoradas_em_testes_reais(self):
        anchors = acceptance.validate_regression_anchors(
            ROOT,
            self.fixture["regressoes"],
        )
        self.assertEqual(len(anchors), len(acceptance.REQUIRED_REGRESSIONS))
        self.assertTrue(any("test_entregas_causais.py" in item for item in anchors))
        self.assertTrue(any("test_iniciativa_elenco.py" in item for item in anchors))
        self.assertTrue(any("test_clima_diario_integracao_nv21.py" in item for item in anchors))
        self.assertTrue(any("test_politica_civica_integracao_nv22.py" in item for item in anchors))

    def test_orcamento_proibe_segunda_orquestracao_e_preserva_tetos(self):
        budget = acceptance.load_budget(ROOT)
        self.assertFalse(budget["arquitetura"]["scheduler_novo"])
        self.assertFalse(budget["arquitetura"]["fila_nova"])
        self.assertFalse(budget["arquitetura"]["hot_path_novo"])
        self.assertFalse(budget["arquitetura"]["writer_novo"])
        self.assertTrue(budget["arquitetura"]["reusa_fronteira_vivacidade"])
        self.assertEqual(budget["limites"]["max_candidatas"], live.MAX_CANDIDATES)
        self.assertEqual(budget["limites"]["max_bytes_projecao"], live.MAX_OUTPUT_BYTES)

    def test_turno_curto_nao_acorda_fronteira_e_longo_reusa_janelas_existentes(self):
        short_start = mundo.parse_instant("21 Eleasis, 1372 DR", "14:00")
        short_target = mundo.parse_instant("21 Eleasis, 1372 DR", "14:30")
        self.assertEqual(live.consultation_windows(short_start, short_target, 6 * 60), [])

        long_start = mundo.parse_instant("21 Eleasis, 1372 DR", "06:00")
        long_target = mundo.parse_instant("21 Eleasis, 1372 DR", "18:00")
        windows = live.consultation_windows(long_start, long_target, 6 * 60)
        self.assertGreaterEqual(len(windows), 3)
        self.assertTrue(all(item["gatilho"] in live.WINDOW_TRIGGERS for item in windows))

    def test_preflight_expoe_gate_read_only_da_aceitacao(self):
        gates = [
            item
            for item in preflight.checks(incluir_testes=False)
            if item.nome == "aceitação integrada de vivacidade"
        ]
        self.assertEqual(len(gates), 1)
        self.assertEqual(
            gates[0].comando[-2:],
            ("ferramentas/aceitacao_vivacidade.py", "check"),
        )

    def test_nome_do_teste_permanente_e_de_dominio(self):
        self.assertNotIn("nv23", Path(__file__).name.lower())
        self.assertNotIn("task", Path(__file__).name.lower())

    def test_checker_integrado_fecha_verde_sem_mutacao(self):
        result = acceptance.check(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertFalse(result["orcamento"]["segunda_orquestracao"])


if __name__ == "__main__":
    unittest.main()
