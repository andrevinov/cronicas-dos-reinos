from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from ferramentas import catalogo_avaliacao


ROOT = Path(__file__).parents[1]
CATALOG_PATH = ROOT / "evaluation" / "catalogo-modulos-v2.json"
GUARDRAILS_PATH = ROOT / "evaluation" / "catalogo-guardrails-v2.json"
POLICY_PATH = ROOT / "evaluation" / "series-avaliacao.json"
SCHEMAS = ROOT / "evaluation" / "schemas"


class EvaluationCatalogContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.catalog = catalogo_avaliacao.load_json(CATALOG_PATH)
        self.guardrails = catalogo_avaliacao.load_json(GUARDRAILS_PATH)
        self.policy = catalogo_avaliacao.load_json(POLICY_PATH)

    def test_catalogo_contem_exatamente_os_doze_modulos_de_primeira_classe(self) -> None:
        catalogo_avaliacao.validate_catalog_v2(self.catalog)
        ids = {module["id"] for module in self.catalog["modulos"]}
        self.assertEqual(ids, catalogo_avaliacao.MODULE_IDS)
        self.assertEqual(len(self.catalog["modulos"]), 12)

    def test_unidade_e_contrato_de_elegibilidade_sao_obrigatorios(self) -> None:
        without_unit = copy.deepcopy(self.catalog)
        without_unit["modulos"][0].pop("unidade_analise")
        with self.assertRaisesRegex(catalogo_avaliacao.EvaluationCatalogError, "unidade_analise"):
            catalogo_avaliacao.validate_catalog_v2(without_unit)

        without_contract = copy.deepcopy(self.catalog)
        without_contract["modulos"][0].pop("contrato_elegibilidade")
        with self.assertRaisesRegex(
            catalogo_avaliacao.EvaluationCatalogError, "contrato_elegibilidade"
        ):
            catalogo_avaliacao.validate_catalog_v2(without_contract)

    def test_todos_os_itens_v1_tem_destino_unico_e_aliases_nao_duplicam(self) -> None:
        catalogo_avaliacao.validate_catalog_v2(self.catalog)
        migrations = self.catalog["migracao_v1"]
        self.assertEqual(
            {item["origem"] for item in migrations}, catalogo_avaliacao.V1_ITEM_IDS
        )
        aliases = [
            alias
            for module in self.catalog["modulos"]
            for subcapability in module["subcapacidades"]
            for alias in subcapability["aliases_v1"]
        ]
        self.assertEqual(len(aliases), len(set(aliases)))
        self.assertEqual(
            set(aliases),
            catalogo_avaliacao.V1_ITEM_IDS - catalogo_avaliacao.NON_MODULE_V1_IDS,
        )

    def test_regressao_e_extensao_nao_entram_no_ranking_modular(self) -> None:
        module_ids = {module["id"] for module in self.catalog["modulos"]}
        layers = self.catalog["camadas_nao_modulares"]
        regression = layers["regressoes_historicas"][0]
        extension = layers["extensoes_campanha"][0]
        self.assertEqual(regression["id"], "seven_names_migration_regression")
        self.assertEqual(extension["id"], "underground_tournament")
        self.assertFalse(regression["recebe_nota_modular"])
        self.assertFalse(extension["recebe_nota_modular"])
        self.assertTrue({regression["id"], extension["id"]}.isdisjoint(module_ids))

    def test_guardrails_criticos_ficam_fora_da_media_modular(self) -> None:
        catalogo_avaliacao.validate_guardrails(self.guardrails, self.catalog)
        self.assertFalse(self.guardrails["participa_media_modular"])
        for guardrail in self.guardrails["guardrails"]:
            self.assertFalse(guardrail["participa_media_modular"])
            self.assertNotIn("peso", guardrail)
            self.assertNotIn("peso_media_modular", guardrail)

        invalid = copy.deepcopy(self.guardrails)
        invalid["guardrails"][0]["peso_media_modular"] = 10
        with self.assertRaisesRegex(catalogo_avaliacao.EvaluationCatalogError, "peso"):
            catalogo_avaliacao.validate_guardrails(invalid, self.catalog)

    def test_schemas_publicados_sao_json_validos_e_apontam_para_draft_2020(self) -> None:
        expected = {
            "catalogo-modulos-v2.schema.json",
            "catalogo-guardrails-v2.schema.json",
            "series-avaliacao.schema.json",
            "ledger-modular-v2.schema.json",
            "adjudicacoes-ledger-v2.schema.json",
        }
        self.assertEqual({path.name for path in SCHEMAS.glob("*.json")}, expected)
        for filename in expected:
            schema = json.loads((SCHEMAS / filename).read_text(encoding="utf-8"))
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertFalse(schema.get("additionalProperties", True))


class EvaluationSeriesPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = catalogo_avaliacao.load_json(POLICY_PATH)

    def test_catalogo_v1_continua_padrao_e_campo_ausente_e_legado(self) -> None:
        catalogo_avaliacao.validate_series_policy(self.policy)
        self.assertEqual(self.policy["serie_padrao_producao"], "legacy-v1")
        self.assertEqual(catalogo_avaliacao.evaluation_series({}, self.policy), "legacy-v1")

        session_021 = catalogo_avaliacao.load_json(
            ROOT / "evaluation" / "sessions" / "021" / "manifest.json"
        )
        self.assertNotIn("serie_avaliacao", session_021)
        self.assertEqual(
            catalogo_avaliacao.evaluation_series(session_021, self.policy), "legacy-v1"
        )

    def test_agregacao_recusa_series_ou_versoes_incompativeis(self) -> None:
        legacy = {
            "serie_avaliacao": "legacy-v1",
            "versoes": {"catalogo_modulos": 1, "metas": 1, "gerador": 1},
        }
        same = copy.deepcopy(legacy)
        self.assertEqual(
            catalogo_avaliacao.require_comparable([legacy, same], self.policy),
            ("legacy-v1", "1", "1", "1"),
        )

        modules_v2 = copy.deepcopy(legacy)
        modules_v2["serie_avaliacao"] = "modules-v2"
        modules_v2["versoes"]["catalogo_modulos"] = 2
        with self.assertRaisesRegex(catalogo_avaliacao.EvaluationCatalogError, "incompatível"):
            catalogo_avaliacao.require_comparable([legacy, modules_v2], self.policy)

        changed_targets = copy.deepcopy(legacy)
        changed_targets["versoes"]["metas"] = 2
        with self.assertRaisesRegex(catalogo_avaliacao.EvaluationCatalogError, "incompatível"):
            catalogo_avaliacao.require_comparable([legacy, changed_targets], self.policy)


if __name__ == "__main__":
    unittest.main()
