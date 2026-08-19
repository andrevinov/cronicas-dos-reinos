from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import recompensas


class RecompensasRepoTest(unittest.TestCase):
    def test_repo_real_valida_mapas_persistidos(self):
        index = recompensas.load_index(ROOT)
        result = recompensas.validate_repo(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["mapas"], len(index["mapas"]))
        self.assertEqual(
            result["recompensas"],
            sum(meta["quantidade"] for meta in index["mapas"].values()),
        )

    def test_local_sem_mapa_custa_so_indice(self):
        result = recompensas.consult(ROOT, "sarbreen_setor_a")
        self.assertFalse(result["mapa_existe"])
        self.assertEqual(
            result["fontes_lidas"],
            ["narrador/recompensas/index.yaml"],
        )

    def test_status_tambem_e_so_indice(self):
        index = recompensas.load_index(ROOT)
        result = recompensas.status(ROOT)
        self.assertEqual(result["mapas"], len(index["mapas"]))
        self.assertEqual(
            result["recompensas_indexadas"],
            sum(meta["quantidade"] for meta in index["mapas"].values()),
        )
        self.assertEqual(result["fontes_lidas"], ["narrador/recompensas/index.yaml"])


class RecompensasSinteticasTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self._copy_base(self.repo)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _copy_base(repo: Path) -> None:
        target = repo / "narrador/recompensas"
        target.mkdir(parents=True, exist_ok=True)
        for name in ("index.yaml", "itens-index.yaml", "tabelas.yaml", "planejadas.yaml"):
            shutil.copy2(ROOT / "narrador/recompensas" / name, target / name)

        # Fixtures sintéticos herdam schema/seed/tabelas da campanha, mas nunca o
        # estado vivo. Referências persistidas para mapas/itens reais tornariam o
        # sandbox dependente dos artefatos da sessão atual.
        index_path = target / "index.yaml"
        index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
        index["mapas"] = {}
        index_path.write_text(
            yaml.safe_dump(index, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

        items_path = target / "itens-index.yaml"
        items = yaml.safe_load(items_path.read_text(encoding="utf-8"))
        items["recompensas"] = {}
        items_path.write_text(
            yaml.safe_dump(items, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    @staticmethod
    def _all_yaml_bytes(repo: Path) -> dict[str, bytes]:
        base = repo / "narrador/recompensas"
        return {
            path.relative_to(repo).as_posix(): path.read_bytes()
            for path in sorted(base.rglob("*.yaml"))
        }

    def test_mesma_seed_local_tier_e_perigo_gera_bytes_identicos(self):
        with tempfile.TemporaryDirectory() as other_raw:
            other = Path(other_raw)
            self._copy_base(other)
            a = recompensas.ensure(self.repo, "sarbreen_setor_a", 3, "alta")
            b = recompensas.ensure(other, "sarbreen_setor_a", 3, "alta")
            self.assertTrue(a["criado"])
            self.assertTrue(b["criado"])
            self.assertEqual(self._all_yaml_bytes(self.repo), self._all_yaml_bytes(other))

    def test_mapa_existente_nunca_rerrola_nem_le_tabelas(self):
        first = recompensas.ensure(self.repo, "sarbreen_setor_a", 2, "alta")
        self.assertTrue(first["criado"])
        before = self._all_yaml_bytes(self.repo)

        second = recompensas.ensure(self.repo, "sarbreen_setor_a", 4, "letal")
        after = self._all_yaml_bytes(self.repo)

        self.assertFalse(second["criado"])
        self.assertEqual(second["mapa"]["tier"], 2)
        self.assertEqual(second["mapa"]["periculosidade"], "alta")
        self.assertEqual(before, after)
        self.assertEqual(
            second["fontes_lidas"],
            [
                "narrador/recompensas/index.yaml",
                "narrador/recompensas/mapas/sarbreen_setor_a.yaml",
            ],
        )

    def test_procedural_nunca_cria_item_de_arco_e_comeca_oculto(self):
        result = recompensas.ensure(self.repo, "ruinas_tier4", 4, "letal")
        self.assertLessEqual(result["mapa"]["quantidade"], 4)
        self.assertGreater(result["mapa"]["quantidade"], 0)
        for item in result["mapa"]["elegiveis"]:
            self.assertEqual(item["estado"], "oculto")
            self.assertEqual(item["origem"], "procedural")
            self.assertNotEqual(item["importancia"], "arco")
        check = recompensas.validate_repo(self.repo)
        self.assertTrue(check["ok"], check["erros"])
        self.assertEqual(check["recompensas"], check["procedurais"])

    def test_consulta_local_e_compacta_e_nao_abre_fragmentos(self):
        recompensas.ensure(self.repo, "docas_armazem_7", 2, "media")
        result = recompensas.consult(self.repo, "docas_armazem_7")
        self.assertTrue(result["mapa_existe"])
        self.assertEqual(
            result["fontes_lidas"],
            [
                "narrador/recompensas/index.yaml",
                "narrador/recompensas/mapas/docas_armazem_7.yaml",
            ],
        )
        self.assertTrue(result["mapa"]["elegiveis"])
        for item in result["mapa"]["elegiveis"]:
            self.assertNotIn("nome", item)
            self.assertNotIn("descricao", item)
            self.assertNotIn("valor_aproximado", item)
            self.assertNotIn("arquivo", item)

    def test_detalhe_e_lookup_dirigido_sem_scan(self):
        generated = recompensas.ensure(self.repo, "ponte_baixa_deposito", 2, "baixa")
        rid = generated["mapa"]["elegiveis"][0]["id"]
        result = recompensas.show(self.repo, rid)
        self.assertEqual(result["recompensa_id"], rid)
        self.assertIn("nome", result["detalhe"])
        self.assertEqual(
            result["fontes_lidas"],
            [
                "narrador/recompensas/itens-index.yaml",
                "narrador/recompensas/mapas/ponte_baixa_deposito.yaml",
                f"narrador/recompensas/itens/{rid}.yaml",
            ],
        )

    def test_recompensa_planejada_de_arco_mistura_sem_virar_procedural(self):
        planned_path = self.repo / "narrador/recompensas/planejadas.yaml"
        planned = yaml.safe_load(planned_path.read_text(encoding="utf-8"))
        planned["por_local"]["templo_teste"] = [
            {
                "id": "reliquia_teste_autoral",
                "tipo": "reliquia",
                "condicao_de_descoberta": "abrir o relicário selado após a condição canônica apropriada",
                "posse": {"tipo": "ambiente"},
                "importancia": "arco",
                "origem": "autoral",
                "detalhe": {
                    "nome": "Relíquia de teste",
                    "descricao": "Objeto autoral usado somente para provar separação de proveniência.",
                    "valor_aproximado": "não aplicável",
                    "tags": ["teste", "arco"],
                },
            }
        ]
        planned_path.write_text(
            yaml.safe_dump(planned, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

        result = recompensas.ensure(self.repo, "templo_teste", 1, "baixa")
        arc = [item for item in result["mapa"]["elegiveis"] if item["importancia"] == "arco"]
        self.assertEqual(len(arc), 1)
        self.assertEqual(arc[0]["origem"], "autoral")
        detail = recompensas.show(self.repo, "reliquia_teste_autoral")["detalhe"]
        self.assertEqual(detail["geracao"]["modo"], "planejada")
        check = recompensas.validate_repo(self.repo)
        self.assertTrue(check["ok"], check["erros"])

    def test_planejada_procedural_ou_procedural_de_arco_e_rejeitada(self):
        planned_path = self.repo / "narrador/recompensas/planejadas.yaml"
        planned = yaml.safe_load(planned_path.read_text(encoding="utf-8"))
        planned["por_local"]["local_ruim"] = [
            {
                "id": "ruim",
                "tipo": "reliquia",
                "condicao_de_descoberta": "achar",
                "posse": {"tipo": "ambiente"},
                "importancia": "arco",
                "origem": "procedural",
                "detalhe": {
                    "nome": "Ruim",
                    "descricao": "Não deveria validar.",
                    "valor_aproximado": "alto",
                    "tags": [],
                },
            }
        ]
        planned_path.write_text(
            yaml.safe_dump(planned, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        with self.assertRaises(recompensas.RewardMapError):
            recompensas.ensure(self.repo, "local_ruim", 1, "baixa")

    def test_ids_locais_distintos_produzem_chaves_distintas(self):
        a = recompensas.ensure(self.repo, "setor_a", 2, "media")
        b = recompensas.ensure(self.repo, "setor_b", 2, "media")
        map_a = yaml.safe_load(
            (self.repo / "narrador/recompensas/mapas/setor_a.yaml").read_text(encoding="utf-8")
        )
        map_b = yaml.safe_load(
            (self.repo / "narrador/recompensas/mapas/setor_b.yaml").read_text(encoding="utf-8")
        )
        self.assertNotEqual(map_a["geracao"]["chave"], map_b["geracao"]["chave"])
        self.assertTrue(a["criado"])
        self.assertTrue(b["criado"])


if __name__ == "__main__":
    unittest.main()
