from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "ferramentas/verificar-congelamentos-estado-vivo.py"
spec = importlib.util.spec_from_file_location("verificar_congelamentos_estado_vivo", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class LiveStateFreezeReviewRepositoryTest(unittest.TestCase):
    def test_todo_suspeito_corrente_tem_revisao_semantica(self):
        report = mod.check(ROOT)
        self.assertTrue(report["ok"], report["nao_revisados"])
        self.assertEqual(report["nao_revisados"], [])
        self.assertGreaterEqual(len(report["decisoes"]), len(report["revisados"]))

    def test_nove_candidatos_originais_tem_decisao_registrada(self):
        report = mod.check(ROOT)
        expected = {
            "tests/test_auditoria_final.py",
            "tests/test_identidades_suspeita.py",
            "tests/test_migracao_ren_5_5e.py",
            "tests/test_papeis_conversacionais.py",
            "tests/test_populacao_canonica.py",
            "tests/test_reputacao_publica.py",
            "tests/test_rodape_turno.py",
            "tests/test_ruleset_5_5e_activation.py",
            "tests/test_talentos_ren.py",
        }
        self.assertEqual(set(report["decisoes"]), expected)

    def test_revisao_manual_registra_freezes_indiretos_adicionais(self):
        report = mod.check(ROOT)
        expected = {
            "tests/test_agentes.py",
            "tests/test_ciclo_npcs.py",
            "tests/test_condicoes_mundo.py",
            "tests/test_direcoes.py",
            "tests/test_progressao_juppongatana.py",
            "tests/test_rastros.py",
        }
        self.assertEqual(set(report["revisoes_indiretas"]), expected)


class LiveStateFreezeReviewSyntheticTest(unittest.TestCase):
    def test_suspeito_novo_sem_revisao_falha(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "tests").mkdir()
            (repo / "estado").mkdir()
            (repo / "tests/test_live.py").write_text(
                """
import unittest
from pathlib import Path
ROOT = Path(__file__).parents[1]
class LiveTest(unittest.TestCase):
    def test_valor(self):
        text = (ROOT / 'estado' / 'estado-atual.yaml').read_text(encoding='utf-8')
        self.assertEqual(text, 'sessao: 8')
""",
                encoding="utf-8",
            )
            (repo / "tests/test_revisado.py").write_text(
                """
import unittest
class RevisadoTest(unittest.TestCase):
    def test_puro(self):
        self.assertTrue(True)
""",
                encoding="utf-8",
            )
            (repo / "estado/estado-atual.yaml").write_text("sessao: 9\n", encoding="utf-8")
            (repo / "tests/live-state-freeze-review.yaml").write_text(
                """schema_revisao_congelamento_estado_vivo: 1
arquivos:
  tests/test_revisado.py:
    status: justificado
    motivo: Este registro sintético válido deixa deliberadamente o freeze novo sem revisão.
""",
                encoding="utf-8",
            )
            report = mod.check(repo)
            self.assertFalse(report["ok"])
            self.assertEqual(report["nao_revisados"], ["tests/test_live.py"])

    def test_manifesto_rejeita_motivo_vazio(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "tests").mkdir()
            (repo / "tests/test_live.py").write_text("# teste\n", encoding="utf-8")
            (repo / "tests/live-state-freeze-review.yaml").write_text(
                """schema_revisao_congelamento_estado_vivo: 1
arquivos:
  tests/test_live.py:
    status: corrigido
    motivo: curto
""",
                encoding="utf-8",
            )
            with self.assertRaises(mod.LiveStateFreezeReviewError):
                mod.load_review(repo)

    def test_revisao_direta_e_indireta_nao_podem_duplicar_o_mesmo_arquivo(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            (repo / "tests").mkdir()
            (repo / "tests/test_live.py").write_text("# teste\n", encoding="utf-8")
            (repo / "tests/live-state-freeze-review.yaml").write_text(
                """schema_revisao_congelamento_estado_vivo: 1
arquivos:
  tests/test_live.py:
    status: corrigido
    motivo: A decisão direta possui justificativa suficiente para o cenário sintético.
revisoes_indiretas:
  tests/test_live.py:
    status: corrigido
    motivo: A duplicação deliberada deve ser recusada pelo verificador da revisão.
""",
                encoding="utf-8",
            )
            with self.assertRaises(mod.LiveStateFreezeReviewError):
                mod.check(repo)


if __name__ == "__main__":
    unittest.main()
