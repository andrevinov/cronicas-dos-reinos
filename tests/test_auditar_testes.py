from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "ferramentas" / "auditar-testes.py"
spec = importlib.util.spec_from_file_location("auditar_testes", MODULE_PATH)
audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(audit)


class AuditoriaTestesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.tests = self.root / "tests"
        self.tests.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def write_test(self, name: str, source: str) -> Path:
        path = self.tests / name
        path.write_text(source, encoding="utf-8")
        return path

    def test_detecta_leitura_direta_do_estado_vivo_e_congelamento_suspeito(self):
        self.write_test(
            "test_live.py",
            """
import unittest
from pathlib import Path

REPO = Path(__file__).parents[1]

class LiveTest(unittest.TestCase):
    def test_sessao(self):
        atual = (REPO / "estado" / "estado-atual.yaml").read_text(encoding="utf-8")
        self.assertEqual(atual, "sessao: 8")
""",
        )

        report = audit.inventory(self.tests, self.root)
        item = report["arquivos"][0]

        self.assertTrue(item["usa_repo_real"])
        self.assertIn("estado_vivo", item["classificacoes"])
        self.assertEqual(item["leituras_estado_vivo"], ["estado/estado-atual.yaml"])
        self.assertIn("congelamento_suspeito", item["candidatos"])

    def test_fixture_temporaria_com_literal_e_congelamento_legitimo(self):
        self.write_test(
            "test_isolado.py",
            """
import tempfile
import unittest

class IsoladoTest(unittest.TestCase):
    def test_valor_controlado(self):
        with tempfile.TemporaryDirectory() as temp:
            self.assertEqual(len(temp) > 0, True)
""",
        )

        report = audit.inventory(self.tests, self.root)
        item = report["arquivos"][0]

        self.assertTrue(item["usa_isolamento"])
        self.assertIn("unitario", item["classificacoes"])
        self.assertIn("congelamento_legitimo", item["candidatos"])
        self.assertNotIn("congelamento_suspeito", item["candidatos"])

    def test_identifica_corpos_de_teste_exatamente_duplicados(self):
        self.write_test(
            "test_duplicado.py",
            """
import unittest

class DuplicadoTest(unittest.TestCase):
    def test_um(self):
        self.assertEqual(1 + 1, 2)

    def test_dois(self):
        self.assertEqual(1 + 1, 2)
""",
        )

        report = audit.inventory(self.tests, self.root)

        self.assertEqual(len(report["duplicidades_exatas_de_corpo"]), 1)
        self.assertIn("possivel_redundancia", report["arquivos"][0]["candidatos"])

    def test_classifica_task_historica_sem_transformar_a_classificacao_em_veredito(self):
        self.write_test(
            "test_task42_router_contract.py",
            """
import unittest

class RouterContractTest(unittest.TestCase):
    def test_contract(self):
        self.assertTrue(True)
""",
        )

        report = audit.inventory(self.tests, self.root)
        item = report["arquivos"][0]

        self.assertIn("task_historica", item["classificacoes"])
        self.assertIn("contrato", item["classificacoes"])
        self.assertIn("teste_transitorio", item["candidatos"])

    def test_inventario_estatico_e_reproduzivel_e_nao_altera_os_arquivos(self):
        path = self.write_test(
            "test_puro.py",
            """
import unittest

class PuroTest(unittest.TestCase):
    def test_soma(self):
        self.assertEqual(2 + 2, 4)
""",
        )
        before = path.read_bytes()

        first = audit.inventory(self.tests, self.root)
        second = audit.inventory(self.tests, self.root)

        self.assertEqual(first, second)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(sorted(p.name for p in self.tests.iterdir()), ["test_puro.py"])


if __name__ == "__main__":
    unittest.main()
