from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import ecologia_local
import interacoes_mundo
import recompensas


class RewardBudgetV2RepositoryTest(unittest.TestCase):
    def test_policy_covers_every_current_ecology_family(self):
        tables = recompensas.load_tables(ROOT)
        self.assertEqual(tables["schema_tabelas_recompensas"], 2)
        budget = tables["orcamento_v2"]
        ecology = ecologia_local.load_index(ROOT)
        families = {profile["familia"] for profile in ecology["perfis"].values()}
        self.assertEqual(families, set(budget["perfis_familia"]))

    def test_existing_real_maps_remain_v1_and_are_not_migrated(self):
        index = recompensas.load_index(ROOT)
        self.assertGreater(len(index["mapas"]), 0)
        for local_id, meta in index["mapas"].items():
            data = recompensas.validate_map(ROOT, local_id, meta, load_fragments=True)
            self.assertEqual(data["geracao"]["modo"], recompensas.GENERATOR)
            self.assertNotIn("orcamento_v2", data["geracao"])

    def test_budget_contract_matches_code_constants(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/reward-budget-v2-orcamento.yaml").read_text(encoding="utf-8")
        )
        limits = contract["limites"]
        index = recompensas.load_index(ROOT)
        self.assertEqual(
            limits["max_procedurais_por_mapa"],
            index["orcamento"]["max_procedurais_por_mapa"],
        )
        self.assertEqual(limits["max_totais_por_mapa"], index["orcamento"]["max_totais_por_mapa"])
        self.assertEqual(limits["max_custo_importancia_especial"], recompensas.V2_IMPORTANCE_COST["especial"])
        self.assertEqual(limits["max_custo_item"], max(recompensas.V2_VALUE_COST.values()) + recompensas.V2_IMPORTANCE_COST["especial"])


class RewardBudgetV2PureTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.index = recompensas.load_index(ROOT)
        cls.tables = recompensas.load_tables(ROOT)
        cls.planned = recompensas.load_planned(ROOT)

    def plan(self, family: str, tier: int, danger: str):
        return recompensas._budget_v2_plan(
            self.index,
            self.tables,
            {"familia": family},
            tier,
            danger,
        )

    def test_risk_never_reduces_points_or_value_ceiling(self):
        plans = [self.plan("residencia_urbana", 2, danger) for danger in ("baixa", "media", "alta", "letal")]
        points = [plan["pontos_total"] for plan in plans]
        ceilings = [plan["teto_valor_rank"] for plan in plans]
        self.assertEqual(points, sorted(points))
        self.assertEqual(ceilings, sorted(ceilings))
        self.assertGreater(points[-1], points[0])
        self.assertGreater(ceilings[-1], ceilings[0])

    def test_special_costs_more_than_common_at_same_value(self):
        common = {"id": "common", "valor_aproximado": "moderado", "importancia": "comum"}
        special = {"id": "special", "valor_aproximado": "moderado", "importancia": "especial"}
        self.assertLess(
            recompensas._template_budget_cost(common, self.tables),
            recompensas._template_budget_cost(special, self.tables),
        )

    def test_local_family_restricts_category_pool(self):
        circus = self.plan("acampamento_espetaculo", 4, "letal")
        mansion = self.plan("mansao_privada", 4, "letal")
        self.assertNotIn("item_magico_menor", circus["categorias_ponderadas"])
        self.assertNotIn("pergaminho", circus["categorias_ponderadas"])
        self.assertIn("item_magico_menor", mansion["categorias_ponderadas"])
        self.assertIn("pergaminho", mansion["categorias_ponderadas"])

    def test_same_v2_input_is_byte_stable_and_stays_inside_budget(self):
        ecology = {"familia": "mansao_privada"}
        first, fragments_a = recompensas.generate_map(
            self.index,
            self.tables,
            self.planned,
            "mansao_nova_teste",
            4,
            "letal",
            ecology=ecology,
        )
        second, fragments_b = recompensas.generate_map(
            self.index,
            self.tables,
            self.planned,
            "mansao_nova_teste",
            4,
            "letal",
            ecology=ecology,
        )
        self.assertEqual(
            yaml.safe_dump(first, allow_unicode=True, sort_keys=False),
            yaml.safe_dump(second, allow_unicode=True, sort_keys=False),
        )
        self.assertEqual(fragments_a, fragments_b)
        self.assertEqual(first["geracao"]["modo"], recompensas.GENERATOR_V2)
        budget = first["geracao"]["orcamento_v2"]
        self.assertLessEqual(budget["pontos_gastos"], budget["pontos_total"])
        self.assertEqual(
            budget["pontos_gastos"] + budget["pontos_restantes"],
            budget["pontos_total"],
        )
        self.assertLessEqual(first["geracao"]["procedurais"], budget["max_itens"])
        self.assertEqual(
            budget["pontos_gastos"],
            sum(fragment["geracao"]["custo_orcamento"] for fragment in fragments_a.values()),
        )
        ceiling = recompensas.VALUE_RANK[budget["teto_valor"]]
        for fragment in fragments_a.values():
            self.assertLessEqual(recompensas.VALUE_RANK[fragment["valor_aproximado"]], ceiling)
            self.assertNotEqual(fragment["importancia"], "arco")
            self.assertEqual(fragment["geracao"]["gerador"], recompensas.GENERATOR_V2)

    def test_unknown_synthetic_ecology_family_falls_back_to_v1(self):
        self.assertIsNone(self.plan("familia_inventada", 2, "media"))

    def test_place_and_risk_change_budget_without_reroll_semantics(self):
        small = self.plan("residencia_exterior", 2, "baixa")
        rich = self.plan("mansao_privada", 2, "letal")
        self.assertLess(small["pontos_total"], rich["pontos_total"])
        self.assertLess(small["teto_valor_rank"], rich["teto_valor_rank"])


class RewardBudgetV2IntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        reward_dir = self.repo / "narrador/recompensas"
        reward_dir.mkdir(parents=True, exist_ok=True)
        for name in ("index.yaml", "itens-index.yaml", "tabelas.yaml", "planejadas.yaml"):
            shutil.copy2(ROOT / "narrador/recompensas" / name, reward_dir / name)
        index_path = reward_dir / "index.yaml"
        index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
        index["mapas"] = {}
        index_path.write_text(yaml.safe_dump(index, allow_unicode=True, sort_keys=False), encoding="utf-8")
        items_path = reward_dir / "itens-index.yaml"
        items = yaml.safe_load(items_path.read_text(encoding="utf-8"))
        items["recompensas"] = {}
        items_path.write_text(yaml.safe_dump(items, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def copy_ecology(self):
        target = self.repo / ecologia_local.INDEX
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / ecologia_local.INDEX, target)

    def test_direct_new_map_reads_ecology_once_and_uses_v2(self):
        self.copy_ecology()
        result = recompensas.ensure(self.repo, "galeria_dos_escribas", 1, "baixa")
        self.assertTrue(result["criado"])
        self.assertEqual(
            result["fontes_lidas"],
            [
                recompensas.INDEX.as_posix(),
                recompensas.TABLES.as_posix(),
                recompensas.PLANNED.as_posix(),
                recompensas.ITEM_INDEX.as_posix(),
                ecologia_local.INDEX.as_posix(),
            ],
        )
        persisted = yaml.safe_load(
            (self.repo / "narrador/recompensas/mapas/galeria_dos_escribas.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(persisted["geracao"]["modo"], recompensas.GENERATOR_V2)
        self.assertEqual(persisted["geracao"]["orcamento_v2"]["familia_local"], "entreposto_documental")

    def test_preloaded_ecology_is_not_read_again(self):
        self.copy_ecology()
        profile = ecologia_local.lookup_canonical(ROOT, "galeria_dos_escribas")["perfil"]
        with mock.patch.object(
            ecologia_local,
            "lookup_canonical",
            side_effect=AssertionError("ecologia já carregada não deve ser relida"),
        ):
            result = recompensas.ensure(
                self.repo,
                "galeria_dos_escribas",
                1,
                "baixa",
                ecology=profile,
            )
        self.assertTrue(result["criado"])
        self.assertNotIn(ecologia_local.INDEX.as_posix(), result["fontes_lidas"])

    def test_fixture_without_ecology_keeps_legacy_v1(self):
        result = recompensas.ensure(self.repo, "fixture_sem_ecologia", 2, "alta")
        self.assertTrue(result["criado"])
        persisted = yaml.safe_load(
            (self.repo / "narrador/recompensas/mapas/fixture_sem_ecologia.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(persisted["geracao"]["modo"], recompensas.GENERATOR)

    def test_local_event_forwards_preloaded_ecology(self):
        profile = {"familia": "entreposto_documental"}
        fake = {
            "criado": False,
            "mapa": {"local_id": "galeria_dos_escribas"},
            "fontes_lidas": [recompensas.INDEX.as_posix()],
        }
        with mock.patch.object(recompensas, "ensure", return_value=fake) as ensure:
            interacoes_mundo.local_event(
                self.repo,
                "galeria_dos_escribas",
                action="entrar",
                tier=1,
                danger="baixa",
                ecology=profile,
            )
        ensure.assert_called_once_with(
            self.repo,
            "galeria_dos_escribas",
            1,
            "baixa",
            ecology=profile,
        )


if __name__ == "__main__":
    unittest.main()
