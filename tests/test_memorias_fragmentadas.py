from __future__ import annotations

import importlib.util
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

    def test_contexto_conhecimento_encontra_sessao_003_sem_monolito(self):
        data = contexto.command_knowledge(ROOT, "ponte baixa")
        self.assertTrue(data["resultado"]["encontrado"])
        self.assertNotIn("personagens/jogador/conhecimento.md", data["fontes"])
        self.assertTrue(
            any("conhecimento/descobertas/sessao-003" in path for path in data["fontes"]),
            data["fontes"],
        )
        rendered, _ = contexto.fit_budget(data, contexto.DEFAULT_MAX_BYTES, False)
        self.assertLessEqual(len(rendered.encode("utf-8")), contexto.DEFAULT_MAX_BYTES)


if __name__ == "__main__":
    unittest.main()
