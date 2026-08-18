from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "ferramentas" / "agentes.py"
spec = importlib.util.spec_from_file_location("agentes", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

REPO = Path(__file__).parents[1]


class AgentesRepositoryTest(unittest.TestCase):
    def test_repositorio_valida_camadas_de_agentes(self):
        result = mod.validate_repo(REPO)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["quantidade"], 7)

    def test_consulta_de_um_agente_le_apenas_indice_e_fragmento(self):
        result = mod.load_agent(REPO, "Shizune")
        self.assertEqual(result["agente_id"], "kajiwara_shizune")
        self.assertEqual(
            result["fontes_lidas"],
            [
                "narrador/agentes/index.yaml",
                "narrador/agentes/kajiwara_shizune.yaml",
            ],
        )
        self.assertNotIn(
            "narrador/agentes/masao_hirasawa.yaml",
            result["fontes_lidas"],
        )

    def test_indice_permanece_pequeno(self):
        size = (REPO / mod.INDEX_PATH).stat().st_size
        self.assertLessEqual(size, 4096)


class AgentesValidationTest(unittest.TestCase):
    def _repo_minimo(self) -> Path:
        self.temp = tempfile.TemporaryDirectory()
        repo = Path(self.temp.name)
        (repo / "narrador/agentes").mkdir(parents=True)
        (repo / "fontes").mkdir()
        (repo / "fontes/canone.md").write_text(
            "O agente sabe que a ponte existe.\n",
            encoding="utf-8",
        )
        (repo / "narrador/agentes/index.yaml").write_text(
            """schema_agentes: 1
natureza: reservado
agentes:
  teste:
    nome: Agente Teste
    tipo: npc
    estado: ativo
    arquivo: narrador/agentes/teste.yaml
""",
            encoding="utf-8",
        )
        (repo / "narrador/agentes/teste.yaml").write_text(
            """schema_agente: 1
natureza: reservado
id: teste
nome: Agente Teste
tipo: npc
estado: ativo
objetivo_atual: Fazer algo fora de cena.
recursos:
  - informação
restricoes:
  - cautela
conhecimento:
  - id: ponte
    fato: A ponte existe.
    fonte: fontes/canone.md
    evidencia: O agente sabe que a ponte existe.
plano_atual:
  estado: aguardando_oportunidade
  acao: Esperar a janela correta.
  prazo_ou_oportunidade: Quando a ponte estiver livre.
fontes_canonicas:
  - fontes/canone.md
""",
            encoding="utf-8",
        )
        return repo

    def tearDown(self):
        temp = getattr(self, "temp", None)
        if temp is not None:
            temp.cleanup()

    def test_referencia_para_fragmento_inexistente_falha(self):
        repo = self._repo_minimo()
        index = repo / "narrador/agentes/index.yaml"
        index.write_text(
            index.read_text(encoding="utf-8").replace(
                "narrador/agentes/teste.yaml",
                "narrador/agentes/inexistente.yaml",
            ),
            encoding="utf-8",
        )
        result = mod.validate_repo(repo)
        self.assertFalse(result["ok"])
        self.assertIn("arquivo inexistente", result["erros"][0])

    def test_conhecimento_sem_evidencia_na_fonte_falha(self):
        repo = self._repo_minimo()
        agent = repo / "narrador/agentes/teste.yaml"
        agent.write_text(
            agent.read_text(encoding="utf-8").replace(
                "O agente sabe que a ponte existe.",
                "Evidência inventada que não está na fonte.",
            ),
            encoding="utf-8",
        )
        result = mod.validate_repo(repo)
        self.assertFalse(result["ok"])
        self.assertIn("não possui evidência", result["erros"][0])

    def test_conhecimento_nao_pode_usar_fonte_nao_declarada(self):
        repo = self._repo_minimo()
        agent = repo / "narrador/agentes/teste.yaml"
        agent.write_text(
            agent.read_text(encoding="utf-8").replace(
                "fonte: fontes/canone.md",
                "fonte: fontes/outra.md",
            ),
            encoding="utf-8",
        )
        (repo / "fontes/outra.md").write_text(
            "O agente sabe que a ponte existe.\n",
            encoding="utf-8",
        )
        result = mod.validate_repo(repo)
        self.assertFalse(result["ok"])
        self.assertIn("fonte não declarada", result["erros"][0])

    def test_id_do_fragmento_precisa_coincidir_com_indice(self):
        repo = self._repo_minimo()
        agent = repo / "narrador/agentes/teste.yaml"
        agent.write_text(
            agent.read_text(encoding="utf-8").replace("id: teste", "id: outro"),
            encoding="utf-8",
        )
        result = mod.validate_repo(repo)
        self.assertFalse(result["ok"])
        self.assertIn("não coincide", result["erros"][0])


if __name__ == "__main__":
    unittest.main()
