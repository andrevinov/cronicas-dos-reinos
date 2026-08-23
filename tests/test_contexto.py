from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "ferramentas" / "contexto.py"
spec = importlib.util.spec_from_file_location("contexto", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

REPO = Path(__file__).parents[1]


class ContextoHelpersTest(unittest.TestCase):
    def test_normalize_handles_accents_and_separators(self):
        self.assertEqual(mod.normalize("Visão-no_Escuro"), "visao no escuro")

    def test_resolve_entity_by_partial_name(self):
        mapping = {
            "kethra_dunn": {"nome": "Kethra Dunn"},
            "jack_mooney": {"nome": "Jack Mooney"},
        }
        key, payload, suggestions = mod.resolve_entity(mapping, "kethra")
        self.assertEqual(key, "kethra_dunn")
        self.assertEqual(payload["nome"], "Kethra Dunn")
        self.assertEqual(suggestions, [])

    def test_markdown_search_prefers_matching_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            path = repo / "doc.md"
            path.write_text(
                "# Manual\n\ntexto geral\n\n## Furtividade\n\nRegra de furtividade aqui.\n\n## Combate\n\noutro texto\n",
                encoding="utf-8",
            )
            result = mod.search_markdown_files([path], "furtividade", repo, limit=2)
            self.assertTrue(result)
            self.assertEqual(result[0]["titulo"], "Furtividade")

    def test_budget_is_hard_limit(self):
        data = mod.envelope(
            "teste",
            None,
            "L2",
            ["x.md"],
            {"texto": "a" * 30000, "lista": ["b" * 2000] * 20},
        )
        text, truncated = mod.fit_budget(data, 2048, False)
        self.assertTrue(truncated)
        self.assertLessEqual(len(text.encode("utf-8")), 2048)

    def test_generic_search_keeps_cold_and_secret_material_out_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "cenario").mkdir()
            (repo / "narrador").mkdir()
            (repo / "sessoes/001").mkdir(parents=True)
            (repo / "cenario/publico.md").write_text("agulha pública", encoding="utf-8")
            (repo / "narrador/segredo.md").write_text("agulha secreta", encoding="utf-8")
            (repo / "sessoes/001/resumo.md").write_text("agulha resumida", encoding="utf-8")
            (repo / "sessoes/001/transcricao.md").write_text("agulha fria", encoding="utf-8")

            default = mod.generic_search(repo, "agulha", reserved=False, historical=False)
            default_files = {item["arquivo"] for item in default}
            self.assertIn("cenario/publico.md", default_files)
            self.assertIn("sessoes/001/resumo.md", default_files)
            self.assertNotIn("narrador/segredo.md", default_files)
            self.assertNotIn("sessoes/001/transcricao.md", default_files)

            reserved = mod.generic_search(repo, "agulha", reserved=True, historical=False)
            self.assertIn("narrador/segredo.md", {item["arquivo"] for item in reserved})

            historical = mod.generic_search(repo, "agulha", reserved=False, historical=True)
            historical_files = {item["arquivo"] for item in historical}
            self.assertIn("sessoes/001/resumo.md", historical_files)
            self.assertNotIn("sessoes/001/transcricao.md", historical_files)

            transcripts = mod.generic_search(
                repo, "agulha", reserved=False, historical=True, transcripts=True
            )
            self.assertIn("sessoes/001/transcricao.md", {item["arquivo"] for item in transcripts})


class ContextoRepositoryTest(unittest.TestCase):
    def test_status_uses_only_hot_runtime_and_pending_overlay(self):
        data = mod.command_status(REPO)
        self.assertEqual(data["nivel"], "L1")
        self.assertEqual(data["resultado"]["personagem"]["nome"], "Ren Kagehira")
        self.assertEqual(data["fontes"][0], "runtime/contexto.yaml")
        self.assertTrue(
            set(data["fontes"]).issubset(
                {"runtime/contexto.yaml", "runtime/eventos-pendentes.jsonl"}
            )
        )
        if data["resultado"].get("sobreposicao_transacional"):
            self.assertIn("runtime/eventos-pendentes.jsonl", data["fontes"])

    def test_relation_lookup_is_targeted(self):
        data = mod.command_relation(REPO, "kethra")
        self.assertTrue(data["resultado"]["encontrado"])
        self.assertEqual(data["resultado"]["relacao"]["nome"], "Kethra Dunn")
        rendered, _ = mod.fit_budget(data, mod.DEFAULT_MAX_BYTES, False)
        self.assertLessEqual(len(rendered.encode("utf-8")), mod.DEFAULT_MAX_BYTES)

    def test_npc_lookup_combines_fast_meter_and_relation(self):
        data = mod.command_npc(REPO, "nera")
        self.assertTrue(data["resultado"]["encontrado"])
        self.assertIsNotNone(data["resultado"]["medidores"])
        self.assertIsNotNone(data["resultado"]["relacao"])

    def test_recurso_broche_combina_mecanica_e_disponibilidade_em_l2(self):
        data = mod.command_resource(REPO, "Broche do Semblante Humilde")
        self.assertTrue(data["resultado"]["encontrado"])
        self.assertEqual(data["nivel"], "L2")
        self.assertEqual(data["resultado"]["mecanica"]["tipo"], "item")
        self.assertEqual(
            data["resultado"]["disponibilidade"]["id"],
            "broche_do_semblante_humilde",
        )
        self.assertIn("personagens/jogador/ficha.yaml", data["fontes"])
        self.assertIn("estado/estado-atual.yaml", data["fontes"])
        rendered, _ = mod.fit_budget(data, mod.DEFAULT_MAX_BYTES, False)
        self.assertLessEqual(len(rendered.encode("utf-8")), mod.DEFAULT_MAX_BYTES)

    def test_recurso_passos_sem_pegadas_encontra_custo_sem_disponibilidade_explicita(self):
        data = mod.command_resource(REPO, "passos sem pegadas")
        self.assertTrue(data["resultado"]["encontrado"])
        mechanic = data["resultado"]["mecanica"]
        self.assertEqual(mechanic["dados"]["nome"], "passos sem pegadas")
        self.assertEqual(mechanic["dados"]["custo"], 2)
        self.assertIsNone(data["resultado"]["disponibilidade"])
        self.assertEqual(data["nivel"], "L2")
        self.assertEqual(
            data["fontes"][:2],
            ["personagens/jogador/ficha.yaml", "estado/estado-atual.yaml"],
        )
        self.assertTrue(
            set(data["fontes"]).issubset(
                {
                    "personagens/jogador/ficha.yaml",
                    "estado/estado-atual.yaml",
                    "runtime/eventos-pendentes.jsonl",
                }
            )
        )

    def test_knowledge_lookup_finds_masao_without_returning_whole_file(self):
        data = mod.command_knowledge(REPO, "Masao")
        self.assertTrue(data["resultado"]["encontrado"])
        rendered, _ = mod.fit_budget(data, mod.DEFAULT_MAX_BYTES, False)
        self.assertLessEqual(len(rendered.encode("utf-8")), mod.DEFAULT_MAX_BYTES)
        self.assertLess(len(rendered), 12000)

    def test_resume_and_session_memory_stay_small(self):
        resume = mod.command_resume(REPO)
        session = mod.command_session(REPO, "3")
        decision = mod.politica.classify("retomada")
        decorated, budget = mod.politica.decorate(
            resume,
            decision,
            requested_budget=mod.DEFAULT_MAX_BYTES,
            after=None,
            reason=None,
        )
        rendered_resume, truncated_resume = mod.fit_budget(decorated, budget, True)
        rendered_session, _ = mod.fit_budget(session, mod.DEFAULT_MAX_BYTES, False)
        self.assertFalse(truncated_resume)
        self.assertLessEqual(len(rendered_resume.encode("utf-8")), 8 * 1024)
        self.assertLessEqual(len(rendered_session.encode("utf-8")), mod.DEFAULT_MAX_BYTES)
        self.assertIsInstance(
            resume["resultado"]["contexto"]["recursos"]["ki"],
            dict,
        )
        self.assertNotIn("sessoes/003/transcricao.md", resume["fontes"])
        self.assertNotIn("sessoes/003/transcricao.md", session["fontes"])


if __name__ == "__main__":
    unittest.main()
