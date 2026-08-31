from __future__ import annotations

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "ferramentas/verificar-testes-historicos.py"
spec = importlib.util.spec_from_file_location("verificar_testes_historicos", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class HistoricalTestReviewRepositoryTest(unittest.TestCase):
    def test_todos_os_39_historicos_da_task1_possuem_destino(self):
        report = mod.check(ROOT)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["originais"], 39)
        self.assertEqual(
            report["classificacoes"],
            {
                "historico": 4,
                "permanente": 19,
                "redundante": 7,
                "substituivel": 9,
            },
        )
        self.assertEqual(report["historicos_nao_revisados"], [])
        self.assertEqual(report["fontes_preservadas_ausentes"], [])

    def test_todo_arquivo_removido_tem_cobertura_existente(self):
        entries = mod.load_review(ROOT)
        removed = {
            source: entry
            for source, entry in entries.items()
            if entry["classificacao"] in mod.REMOVED
        }
        self.assertEqual(len(removed), 16)
        for source, entry in removed.items():
            with self.subTest(source=source):
                self.assertFalse((ROOT / source).exists())
                self.assertTrue(entry["cobertura_atual"])
                for target in entry["cobertura_atual"]:
                    self.assertTrue((ROOT / target).is_file(), target)

    def test_discovery_nao_tem_mais_arquivo_nomeado_por_task(self):
        historical_names = sorted(
            path.name
            for path in (ROOT / "tests").glob("test*.py")
            if re.match(r"test_task\d+", path.name, flags=re.IGNORECASE)
        )
        self.assertEqual(historical_names, [])

    def test_historicos_legitimos_continuam_presentes(self):
        entries = mod.load_review(ROOT)
        kept = {
            source: entry["classificacao"]
            for source, entry in entries.items()
            if entry["classificacao"] in mod.KEPT
        }
        self.assertEqual(len(kept), 23)
        self.assertEqual(kept["tests/test_migracao_ren_5_5e.py"], "historico")
        self.assertEqual(kept["tests/test_sidequest_gate_v2.py"], "historico")
        for source in kept:
            self.assertTrue((ROOT / source).is_file(), source)


class HistoricalTestReviewSyntheticTest(unittest.TestCase):
    def test_cobertura_inexistente_e_rejeitada(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "tests").mkdir()
            source = "tests/test_antigo.py"
            (repo / source).write_text("# histórico\n", encoding="utf-8")
            (repo / mod.REVIEW).write_text(
                """schema_revisao_testes_historicos: 1
quantidade_original: 1
arquivos:
  tests/test_antigo.py:
    classificacao: permanente
    requisito: Esta propriedade permanente possui uma descrição suficientemente explícita.
    cobertura_atual:
      - tests/test_destino_inexistente.py
""",
                encoding="utf-8",
            )
            with mock.patch.object(mod, "ORIGINAL_HISTORICAL", {source}):
                with self.assertRaises(mod.HistoricalTestReviewError):
                    mod.load_review(repo)

    def test_substituivel_nao_pode_manter_a_fonte_antiga(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "tests").mkdir()
            source = "tests/test_antigo.py"
            (repo / source).write_text("# antigo\n", encoding="utf-8")
            (repo / "tests/test_novo.py").write_text("# novo\n", encoding="utf-8")
            (repo / mod.REVIEW).write_text(
                """schema_revisao_testes_historicos: 1
quantidade_original: 1
arquivos:
  tests/test_antigo.py:
    classificacao: substituivel
    requisito: Esta propriedade permanente foi movida integralmente para um domínio estável.
    cobertura_atual:
      - tests/test_novo.py
""",
                encoding="utf-8",
            )
            with mock.patch.object(mod, "ORIGINAL_HISTORICAL", {source}):
                with self.assertRaises(mod.HistoricalTestReviewError):
                    mod.load_review(repo)


if __name__ == "__main__":
    unittest.main()
