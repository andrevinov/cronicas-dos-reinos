from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
sys.path.insert(0, str(TOOLS))
MODULE_PATH = TOOLS / "contexto.py"
spec = importlib.util.spec_from_file_location("contexto_transacional", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class ContextoTransactionalTest(unittest.TestCase):
    def make_repo(self) -> Path:
        self.temp = tempfile.TemporaryDirectory()
        repo = Path(self.temp.name)
        (repo / "runtime").mkdir(parents=True)
        (repo / "estado/relacoes").mkdir(parents=True)
        (repo / "personagens/jogador/conhecimento/topicos").mkdir(parents=True)
        (repo / "runtime/contexto.yaml").write_text(
            """sessao:\n  numero: 3\n  modo_de_cena: combate\nrecursos:\n  pv:\n    atuais: 45\n    maximos: 45\n  ki:\n    atuais: 5\n    maximos: 6\n  ca: 17\n  deslocamento: 55 pés\n  dinheiro_po: 45\ntempo:\n  data: 7 Eleasis, 1372 DR\n  hora_aproximada: '08:03'\nlocalizacao:\n  area: estrada\n  ponto_exato: cerca\n""",
            encoding="utf-8",
        )
        (repo / "runtime/cena.yaml").write_text(
            """sessao: 3\nmodo: combate\nlocalizacao:\n  area: estrada\n  ponto_exato: cerca\ntempo:\n  data: 7 Eleasis, 1372 DR\n  hora_aproximada: '08:03'\nmecanica_imediata:\n  pv: 45/45\n  ki: 5/6\n  ca: 17\n  deslocamento: 55 pés\nresumo_imediato: antes\nprazos_e_alertas: antes\n""",
            encoding="utf-8",
        )
        (repo / "runtime/eventos-pendentes.jsonl").write_text("", encoding="utf-8")
        return repo

    def tearDown(self):
        if hasattr(self, "temp"):
            self.temp.cleanup()

    def append_event(self, repo: Path, record: dict):
        with (repo / "runtime/eventos-pendentes.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def add_empty_knowledge_index(self, repo: Path):
        (repo / "personagens/jogador/conhecimento/index.yaml").write_text(
            "topicos: []\nsessoes: {}\n", encoding="utf-8"
        )
        (repo / "personagens/jogador/conhecimento/ativo.yaml").write_text(
            "topicos_prioritarios: []\ndescobertas_recentes: []\n", encoding="utf-8"
        )

    def test_status_and_scene_show_effective_resources_without_runtime_rewrite(self):
        repo = self.make_repo()
        before = (repo / "runtime/contexto.yaml").read_bytes()
        self.append_event(
            repo,
            {
                "versao": 1,
                "id": "t1",
                "sessao": 3,
                "resumo": "Ren gasta Ki e avança.",
                "deltas": [
                    {"alvo": "estado", "op": "inc", "caminho": "recursos.ki.atuais", "valor": -2},
                    {
                        "alvo": "tempo",
                        "op": "instante",
                        "valor": {"data": "7 Eleasis, 1372 DR", "hora": "08:04"},
                    },
                ],
            },
        )
        status = mod.command_status(repo)
        scene = mod.command_scene(repo)
        self.assertEqual(status["resultado"]["recursos"]["ki"]["atuais"], 3)
        self.assertEqual(status["resultado"]["tempo"]["data"], "7 Eleasis, 1372 DR")
        self.assertEqual(status["resultado"]["tempo"]["hora_aproximada"], "08:04")
        self.assertEqual(scene["resultado"]["cena"]["mecanica_imediata"]["ki"], "3/6")
        self.assertEqual(scene["resultado"]["cena"]["tempo"]["data"], "7 Eleasis, 1372 DR")
        self.assertIn("runtime/eventos-pendentes.jsonl", status["fontes"])
        self.assertEqual(before, (repo / "runtime/contexto.yaml").read_bytes())

    def test_efeito_temporario_aparece_e_some_antes_do_checkpoint(self):
        repo = self.make_repo()
        effect = {
            "nome": "Ensaio do corredor",
            "efeito": "vantagem no primeiro teste relevante para manter o acompanhamento sem exposição",
            "origem": "Investigação 24 durante o reconhecimento físico",
            "gatilho_consumo": "primeiro teste da operação em que o conhecimento ajude",
            "expira": "ao fim da operação de perseguição",
        }
        self.append_event(
            repo,
            {
                "versao": 1,
                "id": "efeito-set",
                "sessao": 3,
                "resumo": "Ren memoriza o corredor de perseguição.",
                "deltas": [
                    {
                        "alvo": "estado",
                        "op": "set",
                        "caminho": "efeitos_temporarios.vantagem_corredor",
                        "valor": effect,
                    }
                ],
            },
        )
        status = mod.command_status(repo)
        scene = mod.command_scene(repo)
        self.assertEqual(
            status["resultado"]["efeitos_temporarios"]["vantagem_corredor"]["nome"],
            "Ensaio do corredor",
        )
        self.assertIn("vantagem_corredor", scene["resultado"]["cena"]["efeitos_temporarios"])

        self.append_event(
            repo,
            {
                "versao": 1,
                "id": "efeito-remove",
                "sessao": 3,
                "resumo": "A vantagem preparada foi consumida.",
                "deltas": [
                    {
                        "alvo": "estado",
                        "op": "remove",
                        "caminho": "efeitos_temporarios.vantagem_corredor",
                    }
                ],
            },
        )
        status_after = mod.command_status(repo)
        scene_after = mod.command_scene(repo)
        self.assertNotIn("vantagem_corredor", status_after["resultado"].get("efeitos_temporarios", {}))
        self.assertNotIn(
            "vantagem_corredor",
            scene_after["resultado"]["cena"].get("efeitos_temporarios", {}),
        )

    def test_relation_uses_fragment_plus_pending_delta(self):
        repo = self.make_repo()
        (repo / "estado/relacoes/index.yaml").write_text(
            """relacoes:\n  kethra_dunn:\n    nome: Kethra Dunn\n    arquivo: estado/relacoes/kethra_dunn.yaml\n    historico: historico/relacoes/kethra_dunn.yaml\n""",
            encoding="utf-8",
        )
        (repo / "estado/relacoes/kethra_dunn.yaml").write_text(
            """relacao:\n  nome: Kethra Dunn\n  confianca: baixa\n""", encoding="utf-8"
        )
        self.append_event(
            repo,
            {
                "versao": 1,
                "id": "t2",
                "sessao": 3,
                "resumo": "Kethra confia mais em Ren.",
                "deltas": [
                    {"alvo": "relacao:kethra_dunn", "op": "set", "caminho": "confianca", "valor": "moderada"}
                ],
            },
        )
        data = mod.command_relation(repo, "kethra")
        self.assertEqual(data["resultado"]["relacao"]["confianca"], "moderada")
        self.assertEqual(data["resultado"]["deltas_pendentes_aplicados"], 1)

    def test_new_knowledge_is_visible_before_consolidation(self):
        repo = self.make_repo()
        self.add_empty_knowledge_index(repo)
        self.append_event(
            repo,
            {
                "versao": 1,
                "id": "t3",
                "sessao": 3,
                "resumo": "Ren descobre uma marca violeta na balança velha.",
                "deltas": [
                    {
                        "alvo": "conhecimento",
                        "op": "registrar",
                        "valor": {"assunto": "balança velha", "texto": "marca violeta"},
                    }
                ],
            },
        )
        data = mod.command_knowledge(repo, "marca violeta")
        self.assertTrue(data["resultado"]["encontrado"])
        self.assertTrue(data["resultado"]["pendentes"])
        self.assertIn("runtime/eventos-pendentes.jsonl", data["fontes"])

    def test_generic_event_summary_does_not_become_character_knowledge(self):
        repo = self.make_repo()
        self.add_empty_knowledge_index(repo)
        self.append_event(
            repo,
            {
                "versao": 1,
                "id": "t3b",
                "sessao": 3,
                "resumo": "Um inimigo chamado Corvo Azul age fora da vista de Ren.",
                "deltas": [
                    {
                        "alvo": "consequencia",
                        "op": "registrar",
                        "visibilidade": "narrador",
                        "valor": {"texto": "Corvo Azul prepara uma emboscada."},
                    }
                ],
            },
        )
        data = mod.command_knowledge(repo, "Corvo Azul")
        self.assertFalse(data["resultado"]["encontrado"])
        self.assertNotIn("pendentes", data["resultado"])

    def test_generic_search_prefers_pending_current_fact(self):
        repo = self.make_repo()
        self.append_event(
            repo,
            {
                "versao": 1,
                "id": "t4",
                "sessao": 3,
                "resumo": "A testemunha cita o moinho azul.",
                "deltas": [],
            },
        )
        data = mod.command_search(repo, "moinho azul", reserved=False, historical=False)
        self.assertTrue(data["resultado"]["encontrado"])
        self.assertEqual(data["resultado"]["ocorrencias"][0]["transacao"], "t4")


if __name__ == "__main__":
    unittest.main()
