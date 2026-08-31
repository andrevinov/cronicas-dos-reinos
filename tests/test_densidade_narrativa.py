from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
REPO = Path(__file__).parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import contexto
import politica_acesso
import texturas


def load_script(name: str, filename: str):
    path = TOOLS / filename
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


gerar_runtime = load_script("gerar_runtime_densidade_test", "gerar-runtime.py")
checkpoint = load_script("checkpoint_densidade_test", "checkpoint.py")


class ContratoNarrativoTest(unittest.TestCase):
    def test_economia_de_contexto_nao_limita_prosa(self):
        agents = (REPO / "AGENTS.md").read_text(encoding="utf-8")
        density = (REPO / "docs/agente/densidade-narrativa.md").read_text(encoding="utf-8")
        guide = (REPO / "narracao/guia-de-narrativa.md").read_text(encoding="utf-8")

        self.assertIn("Economia de contexto não é economia de prosa", agents)
        self.assertIn("Economia de contexto não é economia de prosa", density)
        self.assertIn("Economia de contexto não é economia de prosa", guide)
        self.assertNotIn("entre duas frases e três parágrafos", guide)
        self.assertIn("### 1. `narracao` — a cena", density)
        self.assertIn("resumo   = o significado da cena", density)
        self.assertIn("### 3. `deltas` — mudanças persistentes", density)

    def test_texturas_sao_pequenas_e_validas(self):
        self.assertEqual(texturas.validate(REPO), [])
        index = texturas.load_yaml(REPO / texturas.INDEX_PATH)
        limit = int(index["limite_fragmento_bytes"])
        for kind in ("npcs", "locais"):
            for entry in index[kind].values():
                rel = entry.get("arquivo")
                if rel is None:
                    self.assertIn("papel_conversacional", entry)
                    continue
                self.assertLessEqual((REPO / rel).stat().st_size, limit)


class ContextoNarrativoTest(unittest.TestCase):
    def test_iria_e_encontrada_por_consulta_npc_e_traz_textura(self):
        data = contexto.command_npc(REPO, "Iria Doss")
        result = data["resultado"]
        self.assertTrue(result["encontrado"])
        self.assertIsNotNone(result.get("relacao"))
        self.assertIsNotNone(result.get("textura_narrativa"))
        self.assertEqual(result["textura_narrativa"]["id"], "iria_doss")
        rendered, _ = contexto.fit_budget(data, contexto.DEFAULT_MAX_BYTES, False)
        self.assertLessEqual(len(rendered.encode("utf-8")), contexto.DEFAULT_MAX_BYTES)

    def test_local_e_consulta_l2_compacta(self):
        decision = politica_acesso.classify("local")
        self.assertEqual(decision.level, "L2")
        data = contexto.command_local(REPO, "casa de Iria Doss")
        self.assertTrue(data["resultado"]["encontrado"])
        self.assertEqual(data["resultado"]["textura_narrativa"]["id"], "casa_iria_doss")
        rendered, _ = contexto.fit_budget(data, contexto.DEFAULT_MAX_BYTES, False)
        self.assertLessEqual(len(rendered.encode("utf-8")), contexto.DEFAULT_MAX_BYTES)


class AutoridadeTemporalTest(unittest.TestCase):
    def test_checkpoint_nao_espelha_texto_livre_de_prazo(self):
        self.assertNotIn(
            checkpoint.PRAZO_MIRROR_LEGADO,
            checkpoint.consolidar.TIME_MIRRORS,
        )
        self.assertIn(
            ("tempo.hora_aproximada", "hora_aproximada"),
            checkpoint.consolidar.TIME_MIRRORS,
        )

    def test_runtime_prefere_prazo_de_tempo_yaml(self):
        estado = {
            "campanha": {"sessao_atual": 3, "status": "em_sessao", "modo_de_cena_atual": "interacao"},
            "personagem": {
                "nome": "Ren Kagehira",
                "nivel": 6,
                "classe": "Monge",
                "subclasse": "Guerreiro das Sombras",
                "arquivo_ficha": "personagens/jogador/ficha.yaml",
            },
            "localizacao": {
                "plano": "Material",
                "mundo": "Toril",
                "continente": "Faerûn",
                "regiao": "The Vast",
                "cidade": "Ravens Bluff",
                "area": "teste",
                "ponto_exato": "teste",
                "descricao_operacional": "Ren está no lugar de teste.",
            },
            "tempo": {
                "data_exata": "7 Eleasis, 1372 DR",
                "hora_aproximada": "08:25",
                "periodo_do_dia": "manhã",
                "clima": "úmido",
                "prazo_relevante": "texto legado que não deve vencer",
            },
            "recursos": {
                "pontos_de_vida": {"atuais": 45, "maximos": 45},
                "focus": {"atuais": 5, "maximos": 6},
                "classe_de_armadura": 17,
                "deslocamento": "55 pés",
                "dinheiro": {"po": 45},
            },
        }
        tempo = {
            "data_atual": {"valor": "7 Eleasis, 1372 DR"},
            "hora_aproximada": "08:25",
            "periodo_do_dia": "manhã",
            "clima": "úmido",
            "prazo_relevante": "autoridade temporal correta",
        }
        ficha = {
            "personagem": {"nome": "Ren Kagehira"},
            "identidade": {"nivel": 6},
        }
        _, scene = gerar_runtime.build_runtime_from_documents(estado, tempo, ficha)
        self.assertEqual(scene["prazos_e_alertas"], "autoridade temporal correta")


if __name__ == "__main__":
    unittest.main()
