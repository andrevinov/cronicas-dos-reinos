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
        self.assertEqual(result["quantidade"], len(mod.load_index(REPO)["agentes"]))

    def test_consulta_de_um_agente_le_apenas_indice_e_fragmento(self):
        result = mod.load_agent(REPO, "Shizune")
        self.assertEqual(result["agente_id"], "kajiwara_shizune")
        self.assertEqual(
            result["fontes_lidas"],
            ["narrador/agentes/index.yaml", "narrador/agentes/kajiwara_shizune.yaml"],
        )
        self.assertNotIn("narrador/agentes/masao_hirasawa.yaml", result["fontes_lidas"])
        self.assertLessEqual(len(mod._dump(result).encode("utf-8")), mod.MAX_DIRECTED_BYTES)
        self.assertNotIn("metodos_operacionais", result["resultado"])
        self.assertNotIn("autonomia_estrategica", result["resultado"])

    def test_detalhe_dirigido_abre_uma_secao_sem_exceder_l2(self):
        result = mod.load_agent_detail(REPO, "Shizune", "metodos_operacionais")
        self.assertEqual(result["secao"], "metodos_operacionais")
        self.assertEqual(
            result["fontes_lidas"],
            [
                "narrador/agentes/index.yaml",
                "narrador/agentes/kajiwara_shizune.yaml",
                "narrador/agentes/detalhes/kajiwara_shizune.yaml",
            ],
        )
        self.assertLessEqual(len(mod._dump(result).encode("utf-8")), mod.MAX_DIRECTED_BYTES)
        self.assertNotIn("autonomia_estrategica", result["resultado"])

    def test_todas_as_consultas_fragmentadas_respeitam_orcamento(self):
        index = mod.load_index(REPO)
        for agent_id in index["agentes"]:
            base = mod.load_agent(REPO, agent_id)
            self.assertLessEqual(
                len(mod._dump(base).encode("utf-8")),
                mod.MAX_DIRECTED_BYTES,
                agent_id,
            )
            pointer = base["resultado"].get("detalhes_operacionais") or {}
            for section in pointer.get("secoes", []):
                detail = mod.load_agent_detail(REPO, agent_id, section)
                self.assertLessEqual(
                    len(mod._dump(detail).encode("utf-8")),
                    mod.MAX_DIRECTED_BYTES,
                    f"{agent_id}.{section}",
                )

    def test_corven_promovido_le_apenas_indice_e_fragmento_estrategico(self):
        result = mod.load_agent(REPO, "Corven")
        self.assertEqual(result["agente_id"], "corven_dalm")
        self.assertEqual(result["elegibilidade_local"], mod.local_eligibility(result["resultado"]))
        self.assertEqual(
            result["fontes_lidas"],
            ["narrador/agentes/index.yaml", "narrador/agentes/corven_dalm.yaml"],
        )
        self.assertEqual(
            result["resultado"]["fontes_canonicas"],
            ["estado/relacoes/corven_dalm.yaml"],
        )

    def test_indice_permanece_pequeno_mesmo_com_todos_os_juppongatana(self):
        size = (REPO / mod.INDEX_PATH).stat().st_size
        self.assertLessEqual(size, 4096)

    def test_kurobane_elegibilidade_reflete_presenca_corrente(self):
        result = mod.load_agent(REPO, "Kurobane")
        self.assertIn(result["resultado"]["presenca"]["estado"], mod.VALID_PRESENCE_STATES)
        self.assertEqual(result["elegibilidade_local"], mod.local_eligibility(result["resultado"]))

    def test_shizune_elegibilidade_reflete_presenca_corrente(self):
        result = mod.load_agent(REPO, "Shizune")
        self.assertIn(result["resultado"]["presenca"]["estado"], mod.VALID_PRESENCE_STATES)
        self.assertEqual(result["elegibilidade_local"], mod.local_eligibility(result["resultado"]))

    def test_pan_chu_existe_sem_congelar_estado_ou_chegada_correntes(self):
        result = mod.load_agent(REPO, "Pan Chu")
        self.assertEqual(result["agente_id"], "pan_chu")
        self.assertIn(result["resultado"]["estado"], mod.VALID_STATES)
        self.assertIn(result["resultado"]["presenca"]["estado"], mod.VALID_PRESENCE_STATES)
        self.assertEqual(result["elegibilidade_local"], mod.local_eligibility(result["resultado"]))

    def test_coletivo_juppongatana_depende_de_membros_presentes(self):
        result = mod.load_agent(REPO, "Juppongatana")
        self.assertEqual(result["elegibilidade_local"], "condicional")


class AgentesValidationTest(unittest.TestCase):
    def _repo_minimo(self) -> Path:
        self.temp = tempfile.TemporaryDirectory()
        repo = Path(self.temp.name)
        (repo / "narrador/agentes").mkdir(parents=True)
        (repo / "fontes").mkdir()
        (repo / "fontes/canone.md").write_text(
            "O agente sabe que a ponte existe.\nO agente chegou a Ravens Bluff.\n",
            encoding="utf-8",
        )
        (repo / "narrador/agentes/index.yaml").write_text(
            """schema_agentes: 2
natureza: reservado
agentes:
  teste:
    nome: Agente Teste
    tipo: npc
    estado: ativo
    presenca: presente
    atuacao_local: exige_presenca_fisica
    arquivo: narrador/agentes/teste.yaml
""",
            encoding="utf-8",
        )
        (repo / "narrador/agentes/teste.yaml").write_text(
            """schema_agente: 2
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
presenca:
  referencia: Ravens Bluff
  estado: presente
  detalhe: O agente chegou e está na cidade.
  fonte: fontes/canone.md
  evidencia: O agente chegou a Ravens Bluff.
mobilidade:
  estado: sem_deslocamento_registrado
  origem: null
  destino: null
  prazo: null
atuacao_local:
  regra: exige_presenca_fisica
  escopo: Ravens Bluff
  observacao: Precisa estar fisicamente presente.
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
        index.write_text(index.read_text(encoding="utf-8").replace("narrador/agentes/teste.yaml", "narrador/agentes/inexistente.yaml"), encoding="utf-8")
        result = mod.validate_repo(repo)
        self.assertFalse(result["ok"])
        self.assertIn("arquivo inexistente", result["erros"][0])

    def test_conhecimento_sem_evidencia_na_fonte_falha(self):
        repo = self._repo_minimo()
        agent = repo / "narrador/agentes/teste.yaml"
        agent.write_text(agent.read_text(encoding="utf-8").replace("O agente sabe que a ponte existe.", "Evidência inventada que não está na fonte."), encoding="utf-8")
        result = mod.validate_repo(repo)
        self.assertFalse(result["ok"])
        self.assertIn("não possui evidência", result["erros"][0])

    def test_conhecimento_nao_pode_usar_fonte_nao_declarada(self):
        repo = self._repo_minimo()
        agent = repo / "narrador/agentes/teste.yaml"
        agent.write_text(agent.read_text(encoding="utf-8").replace("fonte: fontes/canone.md", "fonte: fontes/outra.md", 1), encoding="utf-8")
        (repo / "fontes/outra.md").write_text("O agente chegou a Ravens Bluff.\n", encoding="utf-8")
        result = mod.validate_repo(repo)
        self.assertFalse(result["ok"])
        self.assertIn("presença usa fonte não declarada", result["erros"][0])

    def test_id_do_fragmento_precisa_coincidir_com_indice(self):
        repo = self._repo_minimo()
        agent = repo / "narrador/agentes/teste.yaml"
        agent.write_text(agent.read_text(encoding="utf-8").replace("id: teste", "id: outro"), encoding="utf-8")
        result = mod.validate_repo(repo)
        self.assertFalse(result["ok"])
        self.assertIn("não coincide", result["erros"][0])

    def test_presenca_concreta_sem_fonte_falha(self):
        repo = self._repo_minimo()
        agent = repo / "narrador/agentes/teste.yaml"
        text = agent.read_text(encoding="utf-8")
        text = text.replace("  fonte: fontes/canone.md\n  evidencia: O agente chegou a Ravens Bluff.\n", "  fonte: null\n  evidencia: null\n")
        agent.write_text(text, encoding="utf-8")
        result = mod.validate_repo(repo)
        self.assertFalse(result["ok"])
        self.assertIn("presença concreta", result["erros"][0])

    def test_em_viagem_bloqueia_acao_local_direta(self):
        repo = self._repo_minimo()
        index = repo / "narrador/agentes/index.yaml"
        index.write_text(index.read_text(encoding="utf-8").replace("presenca: presente", "presenca: em_viagem"), encoding="utf-8")
        agent = repo / "narrador/agentes/teste.yaml"
        text = agent.read_text(encoding="utf-8")
        text = text.replace("  estado: presente\n", "  estado: em_viagem\n", 1)
        text = text.replace("  estado: sem_deslocamento_registrado\n  origem: null\n  destino: null\n  prazo: null\n", "  estado: em_deslocamento\n  origem: Ravens Bluff\n  destino: Calaunt\n  prazo: duas semanas\n")
        agent.write_text(text, encoding="utf-8")
        result = mod.load_agent(repo, "teste")
        self.assertEqual(result["elegibilidade_local"], "nao")

    def test_presenca_oculta_nao_cria_conhecimento_para_ren(self):
        repo = self._repo_minimo()
        index = repo / "narrador/agentes/index.yaml"
        index.write_text(index.read_text(encoding="utf-8").replace("presenca: presente", "presenca: presente_oculto"), encoding="utf-8")
        agent = repo / "narrador/agentes/teste.yaml"
        text = agent.read_text(encoding="utf-8").replace("  estado: presente\n", "  estado: presente_oculto\n", 1)
        start = text.index("conhecimento:\n")
        end = text.index("plano_atual:\n")
        text = text[:start] + "conhecimento: []\n" + text[end:]
        agent.write_text(text, encoding="utf-8")
        result = mod.load_agent(repo, "teste")
        self.assertEqual(result["elegibilidade_local"], "sim")
        self.assertEqual(result["resultado"]["conhecimento"], [])


if __name__ == "__main__":
    unittest.main()
