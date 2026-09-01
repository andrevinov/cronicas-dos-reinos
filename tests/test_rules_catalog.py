from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import catalogo_regras
import contexto


class RulesCatalogContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.document = catalogo_regras.read_document(ROOT)

    def test_catalogo_real_e_valido_e_marca_task2(self) -> None:
        result = catalogo_regras.check(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertGreaterEqual(result["regras"], 5)
        campaign = contexto.load_yaml(ROOT / "campanha.yaml")
        requirements = campaign["sistema"]["ruleset"]["migracao"]["ativacao"]["requisitos"]
        self.assertTrue(requirements["task_2_catalogo"])

    def test_ids_duplicados_falham(self) -> None:
        document = copy.deepcopy(self.document)
        document["regras"].append(copy.deepcopy(document["regras"][0]))
        with self.assertRaisesRegex(catalogo_regras.RuleCatalogError, "id duplicado"):
            catalogo_regras.validate_document(ROOT, document)

    def test_alias_duplicado_ou_ambiguo_falha(self) -> None:
        document = copy.deepcopy(self.document)
        document["regras"][1]["aliases"].append("furtividade")
        with self.assertRaisesRegex(catalogo_regras.RuleCatalogError, "alias duplicado"):
            catalogo_regras.validate_document(ROOT, document)

    def test_fonte_inexistente_falha_fechado(self) -> None:
        document = copy.deepcopy(self.document)
        document["regras"][0]["fonte"]["arquivo"] = "regras/nao-existe.md"
        with self.assertRaisesRegex(catalogo_regras.RuleCatalogError, "fonte inexistente"):
            catalogo_regras.validate_document(ROOT, document)

    def test_conflito_de_versao_nao_reintroduz_2014_no_catalogo_ativo(self) -> None:
        document = copy.deepcopy(self.document)
        document["regras"][0]["ruleset"] = "dnd_5e_2014"
        with self.assertRaisesRegex(catalogo_regras.RuleCatalogError, "conflito de versão"):
            catalogo_regras.validate_document(ROOT, document)

    def test_regra_inexistente_preserva_fallback_textual(self) -> None:
        data = contexto.command_rule(ROOT, "zzqvwxyz314159")
        self.assertFalse(data["resultado"]["encontrado"])
        self.assertFalse(data["resultado"]["catalogada"])
        self.assertIn("regras/catalogo.yaml", data["fontes"])

    def test_alias_furtividade_retorna_identidade_executor_e_autoridade(self) -> None:
        data = contexto.command_rule(ROOT, "stealth")
        result = data["resultado"]
        self.assertTrue(result["encontrado"])
        self.assertTrue(result["catalogada"])
        self.assertEqual(data["nivel"], "L2")
        self.assertEqual(result["id"], "furtividade_oposta")
        self.assertEqual(result["ruleset"], "dnd_5_5e")
        self.assertEqual(result["autoridade"], "ruleset_atual")
        self.assertEqual(result["executor"], "dados")
        self.assertEqual(result["persistencia"], "nenhuma")
        self.assertEqual(result["documentacao"]["titulo"], "Testes resistidos")
        self.assertIn("Furtividade", result["documentacao"]["conteudo"])

    def test_retorno_catalogado_cabe_no_orcamento_l2(self) -> None:
        data = contexto.command_rule(ROOT, "furtividade")
        rendered, truncated = contexto.fit_budget(data, contexto.DEFAULT_MAX_BYTES, False)
        self.assertFalse(truncated)
        self.assertLessEqual(len(rendered.encode("utf-8")), contexto.DEFAULT_MAX_BYTES)
        self.assertEqual(
            data["fontes"],
            ["regras/catalogo.yaml", "campanha.yaml", "regras/resolucao-de-acoes.md"],
        )

    def test_gasto_focus_expoe_receita_operacional_completa_em_l2(self) -> None:
        data = contexto.command_rule(ROOT, "gastar focus")
        result = data["resultado"]
        recipe = result["receita_operacional"]
        self.assertEqual(data["nivel"], "L2")
        self.assertEqual(recipe["preparar"]["atalho"], "--gasto-focus 1")
        obligation = recipe["preparar"]["mecanica_json"]["obrigacoes"][0]
        self.assertEqual(obligation["id"], "focus_spend")
        self.assertEqual(obligation["custo"], 1)
        self.assertEqual(
            recipe["concluir"]["deltas"],
            [
                {
                    "alvo": "estado",
                    "op": "inc",
                    "caminho": "recursos.focus.atuais",
                    "valor": -1,
                }
            ],
        )
        rendered, truncated = contexto.fit_budget(data, contexto.DEFAULT_MAX_BYTES, False)
        self.assertFalse(truncated)
        self.assertLessEqual(len(rendered.encode("utf-8")), contexto.DEFAULT_MAX_BYTES)

    def test_escuridao_das_artes_sombrias_esta_catalogada_com_custo_e_receita(self) -> None:
        data = contexto.command_rule(ROOT, "shadow arts darkness")
        result = data["resultado"]
        self.assertTrue(result["catalogada"])
        self.assertEqual(result["id"], "artes_sombrias_escuridao")
        self.assertEqual(result["ruleset"], "dnd_5_5e")
        self.assertIn("1 Focus", result["resumo_interno"])
        obligation = result["receita_operacional"]["preparar"]["mecanica_json"]["obrigacoes"][0]
        self.assertEqual(obligation["id"], "focus_darkness")
        self.assertEqual(obligation["regra"], "artes_sombrias_escuridao")

    def test_receita_operacional_malformada_falha_fechado(self) -> None:
        document = copy.deepcopy(self.document)
        document["regras"][0]["receita_operacional"] = {"preparar": {}}
        with self.assertRaisesRegex(catalogo_regras.RuleCatalogError, "receita_operacional"):
            catalogo_regras.validate_document(ROOT, document)

    def test_documentacao_humana_e_ancora_obrigatoria(self) -> None:
        document = copy.deepcopy(self.document)
        document["regras"][0]["fonte"]["secao"] = "Seção que não existe"
        with self.assertRaisesRegex(catalogo_regras.RuleCatalogError, "seção humana inexistente"):
            catalogo_regras.validate_document(ROOT, document)


if __name__ == "__main__":
    unittest.main()
