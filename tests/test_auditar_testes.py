from __future__ import annotations

import importlib.util
import sys
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
import sys
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

    def test_root_definido_apenas_para_carregar_modulo_nao_conta_como_repo_real(self):
        self.write_test(
            "test_loader.py",
            """
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "ferramentas" / "modulo.py"

class LoaderTest(unittest.TestCase):
    def test_puro(self):
        self.assertEqual(2 + 2, 4)
""",
        )

        report = audit.inventory(self.tests, self.root)
        item = report["arquivos"][0]

        self.assertFalse(item["usa_repo_real"])
        self.assertIn("unitario", item["classificacoes"])

    def test_task_mencionada_apenas_em_string_nao_classifica_arquivo(self):
        self.write_test(
            "test_texto.py",
            """
import unittest

EXEMPLO = "test_task42_router_contract.py"

class TextoTest(unittest.TestCase):
    def test_texto(self):
        self.assertIn("task42", EXEMPLO)
""",
        )

        report = audit.inventory(self.tests, self.root)
        item = report["arquivos"][0]

        self.assertNotIn("task_historica", item["classificacoes"])
        self.assertNotIn("teste_transitorio", item["candidatos"])

    def test_medicao_mantem_raiz_do_repo_importavel_como_unittest_cli(self):
        (self.root / "support_module.py").write_text("VALUE = 42\n", encoding="utf-8")
        self.write_test(
            "test_import_raiz_auditoria.py",
            """
import unittest
import support_module

class ImportRootTest(unittest.TestCase):
    def test_import(self):
        self.assertEqual(support_module.VALUE, 42)
""",
        )

        try:
            measurement, success = audit.measure_suite(
                self.tests,
                top=5,
                root=self.root,
            )
        finally:
            sys.modules.pop("test_import_raiz_auditoria", None)
            sys.modules.pop("support_module", None)

        self.assertTrue(success, measurement["execucao"]["problemas"])
        self.assertEqual(measurement["execucao"]["testes_executados"], 1)

    def test_medicao_captura_saida_dos_testes_sem_contaminar_relatorio(self):
        self.write_test(
            "test_saida.py",
            """
import sys
import unittest

class SaidaTest(unittest.TestCase):
    def test_saida(self):
        print("ruido stdout")
        print("ruido stderr", file=sys.stderr)
        self.assertTrue(True)
""",
        )

        try:
            measurement, success = audit.measure_suite(
                self.tests,
                top=5,
                root=self.root,
            )
        finally:
            sys.modules.pop("test_saida", None)

        self.assertTrue(success, measurement["execucao"]["problemas"])
        self.assertGreater(measurement["execucao"]["stdout_capturado_bytes"], 0)
        self.assertGreater(measurement["execucao"]["stderr_capturado_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
