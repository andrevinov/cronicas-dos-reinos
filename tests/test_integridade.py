from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
MODULE_PATH = ROOT / "ferramentas" / "verificar-integridade.py"
spec = importlib.util.spec_from_file_location("verificar_integridade", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class IntegridadeHelpersTest(unittest.TestCase):
    def test_get_path(self):
        self.assertEqual(mod.get_path({"a": {"b": 3}}, "a.b"), 3)
        with self.assertRaises(KeyError):
            mod.get_path({"a": {}}, "a.c")

    def test_duplicate_yaml_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x.yaml"
            path.write_text("a: 1\na: 2\n", encoding="utf-8")
            with self.assertRaises(Exception):
                mod.load_yaml(path)


class AgentRouterTest(unittest.TestCase):
    def test_real_router_has_current_manual_index(self):
        errors = mod.validate_agent_router(ROOT)
        self.assertEqual(errors, [])

    def test_broken_manual_index_entry_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            marker_text = (
                "Nunca leia por precaução\n"
                "Se for suficiente, pare\n"
                "Economia de contexto não é economia de prosa\n"
                "runtime/contexto.yaml\n"
                "runtime/cena.yaml\n"
                "docs/agente/operacao/acesso-e-operacoes.md\n"
                "docs/agente/narrativa/densidade-narrativa.md\n"
                "docs/agente/README.md\n"
            )
            (repo / "AGENTS.md").write_text(marker_text, encoding="utf-8")
            index = repo / mod.AGENT_INDEX
            index.parent.mkdir(parents=True)
            index.write_text("[ausente](fundamentos/ausente.md)\n", encoding="utf-8")
            errors = mod.validate_agent_router(repo)
            self.assertTrue(any("aponta para arquivo ausente" in error for error in errors))

    def test_oversized_router_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            text = (
                "Nunca leia por precaução\n"
                "Se for suficiente, pare\n"
                "Economia de contexto não é economia de prosa\n"
                "runtime/contexto.yaml\n"
                "runtime/cena.yaml\n"
                "docs/agente/operacao/acesso-e-operacoes.md\n"
                "docs/agente/narrativa/densidade-narrativa.md\n"
                "docs/agente/README.md\n"
                + ("x" * (mod.AGENTS_MAX_BYTES + 1))
            )
            (repo / "AGENTS.md").write_text(text, encoding="utf-8")
            index = repo / mod.AGENT_INDEX
            index.parent.mkdir(parents=True)
            index.write_text("# Manuais\n", encoding="utf-8")
            errors = mod.validate_agent_router(repo)
            self.assertTrue(any("excede o limite do roteador" in error for error in errors))


class NarratorStructureTest(unittest.TestCase):
    def test_repo_real_tem_autoridades_ciclos_e_orcamentos_classificados(self):
        result = mod.estrutura_narrador.audit(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["erros"], [])
        self.assertEqual(result["suspeitas_revisao_humana"], [])
        self.assertGreater(result["arquivos_no_grafo"], 0)

    def test_referencia_quebrada_em_fonte_reservada_e_detectada(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            path = repo / "narrador/origem.md"
            path.parent.mkdir(parents=True)
            path.write_text("Consultar narrador/inexistente.yaml.\n", encoding="utf-8")
            _, broken, _ = mod.estrutura_narrador.reference_graph(repo)
            self.assertEqual(
                broken,
                ["narrador/origem.md -> narrador/inexistente.yaml"],
            )

    def test_historico_preserva_referencia_antiga_sem_virar_rota_atual(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            path = repo / "narrador/historico/sessoes/001/preparacao.md"
            path.parent.mkdir(parents=True)
            path.write_text(
                "Fonte usada então: narrador/caminho-antigo.yaml.\n",
                encoding="utf-8",
            )
            _, broken, _ = mod.estrutura_narrador.reference_graph(repo)
            self.assertEqual(broken, [])

    def test_ciclo_multiarquivo_e_identificado_sem_inferir_que_e_lixo(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            folder = repo / "narrador"
            folder.mkdir()
            (folder / "a.yaml").write_text(
                "proximo: narrador/b.yaml\n", encoding="utf-8"
            )
            (folder / "b.yaml").write_text(
                "proximo: narrador/a.yaml\n", encoding="utf-8"
            )
            graph, broken, _ = mod.estrutura_narrador.reference_graph(repo)
            self.assertEqual(broken, [])
            self.assertEqual(
                mod.estrutura_narrador.strongly_connected(graph),
                [frozenset({"narrador/a.yaml", "narrador/b.yaml"})],
            )

    def test_juppongatana_tem_uma_unica_raiz_atual(self):
        path = ROOT / "narrador/elenco/juppongatana/README.md"
        text = path.read_text(encoding="utf-8")
        self.assertIn("Estatuto canônico", text)
        self.assertFalse((ROOT / "narrador/juppongatana.md").exists())


if __name__ == "__main__":
    unittest.main()
