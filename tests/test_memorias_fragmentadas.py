from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]


def load_module(name: str, relative: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


migration = load_module("migrar_memorias", "ferramentas/migrar-memorias-fragmentadas.py")
reindex = load_module("reindexar_conhecimento", "ferramentas/reindexar-conhecimento.py")
contexto = load_module("contexto_step6", "ferramentas/contexto.py")


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def build_knowledge_fixture(root: Path, *, active_matches: bool) -> tuple[str, str]:
    knowledge = root / "personagens/jogador/conhecimento"
    active_rel = "personagens/jogador/conhecimento/incrementais/sessao-999/atual.md"
    historical_rel = "personagens/jogador/conhecimento/descobertas/sessao-003/historico.md"
    active_path = root / active_rel
    historical_path = root / historical_rel
    active_path.parent.mkdir(parents=True, exist_ok=True)
    historical_path.parent.mkdir(parents=True, exist_ok=True)

    active_path.write_text(
        (
            "# Ponte Baixa\n\nInformação operacional recente sobre Ponte Baixa.\n"
            if active_matches
            else "# Outro assunto\n\nInformação recente sem relação com a consulta.\n"
        ),
        encoding="utf-8",
    )
    historical_path.write_text(
        "# Ponte Baixa\n\nInformação fragmentada antiga sobre Ponte Baixa.\n",
        encoding="utf-8",
    )

    knowledge.mkdir(parents=True, exist_ok=True)
    (knowledge / "index.yaml").write_text("schema_conhecimento: 2\n", encoding="utf-8")
    (knowledge / "ativo.yaml").write_text(
        yaml.safe_dump(
            {
                "schema_conhecimento_ativo": 2,
                "topicos_prioritarios": [],
                "descobertas_recentes": [],
                "incrementais_recentes": [
                    {
                        "titulo": "Informação corrente",
                        "arquivos": [active_rel],
                    }
                ],
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return active_rel, historical_rel


class MemoriasFragmentadasTest(unittest.TestCase):
    def test_migracao_permanente_esta_integra(self):
        self.assertEqual(migration.check(ROOT), [])
        self.assertEqual(reindex.check(ROOT), [])

    def test_legados_fundamentais_foram_preservados_byte_a_byte(self):
        for rel, expected in migration.EXPECTED_BLOBS.items():
            data = (ROOT / rel).read_bytes()
            self.assertEqual(migration.git_blob_sha(data), expected, rel.as_posix())

    def test_todas_as_relacoes_legadas_continuam_presentes_e_novas_podem_surgir(self):
        legacy = load_yaml(ROOT / migration.REL_LEGACY)["relacoes"]
        index = load_yaml(ROOT / migration.REL_INDEX)["relacoes"]
        self.assertTrue(set(legacy).issubset(set(index)))
        self.assertGreaterEqual(len(index), len(legacy))
        for entity_id, entry in index.items():
            current = ROOT / entry["arquivo"]
            historical = ROOT / entry["historico"]
            self.assertTrue(current.is_file(), entity_id)
            self.assertTrue(historical.is_file(), entity_id)
            self.assertLessEqual(current.stat().st_size, migration.MAX_ENTITY_FRAGMENT)

    def test_kethra_atual_nao_carrega_a_cronologia_completa(self):
        index = load_yaml(ROOT / migration.REL_INDEX)["relacoes"]
        entry = index["kethra_dunn"]
        current = load_yaml(ROOT / entry["arquivo"])
        historical = load_yaml(ROOT / entry["historico"])
        legacy = load_yaml(ROOT / migration.REL_LEGACY)["relacoes"]["kethra_dunn"]

        relation = current["relacao"]
        self.assertEqual(relation["nome"], "Kethra Dunn")
        self.assertNotIn("motivo", relation)
        self.assertIn("motivo_atual", relation)
        self.assertEqual(historical["relacao"], legacy)
        self.assertLess((ROOT / entry["arquivo"]).stat().st_size, 6 * 1024)

    def test_todos_os_medidores_legados_continuam_presentes_e_novos_podem_surgir(self):
        legacy = load_yaml(ROOT / migration.NPC_LEGACY)["npcs"]
        index = load_yaml(ROOT / migration.NPC_INDEX)["npcs"]
        self.assertTrue(set(legacy).issubset(set(index)))
        self.assertGreaterEqual(len(index), len(legacy))
        for entity_id, entry in index.items():
            fragment = ROOT / entry["arquivo"]
            self.assertTrue(fragment.is_file(), entity_id)
            self.assertLessEqual(fragment.stat().st_size, migration.MAX_ENTITY_FRAGMENT)

    def test_conhecimento_reconstroi_exatamente_o_monolito_legado(self):
        manifest = load_yaml(ROOT / migration.MANIFEST)
        order = manifest["conhecimento"]["ordem_fragmentos"]
        rebuilt = b"".join((ROOT / rel).read_bytes() for rel in order)
        self.assertEqual(rebuilt, (ROOT / migration.KNOW_LEGACY).read_bytes())
        self.assertGreater(len(order), 50)
        self.assertIn(3, manifest["conhecimento"]["sessoes_indexadas"])

    def test_recorte_ativo_e_coerente_com_o_indice_sem_exigir_escrita_por_turno(self):
        active = load_yaml(ROOT / reindex.ACTIVE)
        state = load_yaml(ROOT / "estado/estado-atual.yaml")
        index = load_yaml(ROOT / reindex.INDEX)
        current_session = state["campanha"]["sessao_atual"]
        indexed_sessions = {
            int(session)
            for section in (index.get("sessoes") or {}, index.get("incrementais") or {})
            for session in section
        }
        latest_indexed = max(indexed_sessions) if indexed_sessions else None
        self.assertIsInstance(active["sessao_atual_da_campanha"], int)
        self.assertLessEqual(active["sessao_atual_da_campanha"], current_session)
        self.assertEqual(active["sessao_mais_recente_indexada"], latest_indexed)
        self.assertLessEqual((ROOT / reindex.ACTIVE).stat().st_size, reindex.MAX_ACTIVE)

    def test_roteadores_monoliticos_ficaram_pequenos(self):
        for path in (migration.REL_SOURCE, migration.NPC_SOURCE, migration.KNOW_SOURCE):
            self.assertLess((ROOT / path).stat().st_size, migration.MAX_ROUTER)

    def test_contexto_relacao_le_indice_e_um_fragmento(self):
        data = contexto.command_relation(ROOT, "kethra")
        self.assertTrue(data["resultado"]["encontrado"])
        self.assertEqual(data["resultado"]["relacao"]["nome"], "Kethra Dunn")
        self.assertIn("estado/relacoes/index.yaml", data["fontes"])
        self.assertIn("estado/relacoes/kethra_dunn.yaml", data["fontes"])
        self.assertNotIn("estado/relacoes.yaml", data["fontes"])

    def test_contexto_npc_nao_reabre_os_monolitos(self):
        data = contexto.command_npc(ROOT, "nera")
        self.assertTrue(data["resultado"]["encontrado"])
        self.assertIsNotNone(data["resultado"]["medidores"])
        self.assertIsNotNone(data["resultado"]["relacao"])
        self.assertNotIn("estado/medidores-npcs.yaml", data["fontes"])
        self.assertNotIn("estado/relacoes.yaml", data["fontes"])
        self.assertTrue(any(path.startswith("estado/npcs/") for path in data["fontes"]))

    def test_contexto_conhecimento_prioriza_recorte_ativo_quando_ha_acerto_forte(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            active_rel, historical_rel = build_knowledge_fixture(repo, active_matches=True)
            data = contexto.command_knowledge(repo, "ponte baixa")

        self.assertTrue(data["resultado"]["encontrado"])
        self.assertIn(active_rel, data["fontes"])
        self.assertNotIn(historical_rel, data["fontes"])
        self.assertNotIn("personagens/jogador/conhecimento.md", data["fontes"])

    def test_contexto_conhecimento_faz_fallback_para_fragmentos_quando_ativo_nao_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            active_rel, historical_rel = build_knowledge_fixture(repo, active_matches=False)
            data = contexto.command_knowledge(repo, "ponte baixa")

        self.assertTrue(data["resultado"]["encontrado"])
        self.assertIn(historical_rel, data["fontes"])
        self.assertNotIn(active_rel, data["fontes"])
        self.assertNotIn("personagens/jogador/conhecimento.md", data["fontes"])

    def test_contexto_conhecimento_real_nao_depende_de_sessao_fixa(self):
        data = contexto.command_knowledge(ROOT, "ponte baixa")
        self.assertTrue(data["resultado"]["encontrado"])
        self.assertNotIn("personagens/jogador/conhecimento.md", data["fontes"])
        self.assertTrue(
            any(
                path.startswith("personagens/jogador/conhecimento/") and path.endswith(".md")
                for path in data["fontes"]
            ),
            data["fontes"],
        )
        rendered, _ = contexto.fit_budget(data, contexto.DEFAULT_MAX_BYTES, False)
        self.assertLessEqual(len(rendered.encode("utf-8")), contexto.DEFAULT_MAX_BYTES)


if __name__ == "__main__":
    unittest.main()
