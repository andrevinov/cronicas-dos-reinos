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
            """sessao:\n  numero: 3\n  modo_de_cena: combate\nrecursos:\n  pv:\n    atuais: 45\n    maximos: 45\n  ki:\n    atuais: 5\n    maximos: 6\n  ca: 17\n  deslocamento: 55 pés\n  dinheiro_po: 45\ntempo:\n  data: 7 Eleasis\n  hora_aproximada: '08:03'\nlocalizacao:\n  area: estrada\n  ponto_exato: cerca\n""",
            encoding="utf-8",
        )
        (repo / "runtime/cena.yaml").write_text(
            """sessao: 3\nmodo: combate\nlocalizacao:\n  area: estrada\n  ponto_exato: cerca\ntempo:\n  data: 7 Eleasis\n  hora_aproximada: '08:03'\nmecanica_imediata:\n  pv: 45/45\n  ki: 5/6\n  ca: 17\n  deslocamento: 55 pés\nresumo_imediato: antes\nprazos_e_alertas: antes\n""",
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
                    {"alvo": "tempo", "op": "set", "caminho": "hora_aproximada", "valor": "08:04"},
                ],
            },
        )
        status = mod.command_status(repo)
        scene = mod.command_scene(repo)
        self.assertEqual(status["resultado"]["recursos"]["ki"]["atuais"], 3)
        self.assertEqual(status["resultado"]["tempo"]["hora_aproximada"], "08:04")
        self.assertEqual(scene["resultado"]["cena"]["mecanica_imediata"]["ki"], "3/6")
        self.assertIn("runtime/eventos-pendentes.jsonl", status["fontes"])
        self.assertEqual(before, (repo / "runtime/contexto.yaml").read_bytes())

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
        (repo / "personagens/jogador/conhecimento/index.yaml").write_text(
            "topicos: []\nsessoes: {}\n", encoding="utf-8"
        )
        (repo / "personagens/jogador/conhecimento/ativo.yaml").write_text(
            "topicos_prioritarios: []\ndescobertas_recentes: []\n", encoding="utf-8"
        )
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
