from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import arcos
import agentes
import contexto_cena
import metodos_agentes

LINE = "neutralizar_ren_sem_expor_a_rede"
EXECUTORS = {"masao_hirasawa", "kajiwara_shizune", "kurobane_jinzaburo"}
SOURCE = ROOT / "narrador/arcos/parte_1/neutralizacao-ren.yaml"
BUDGET = ROOT / "baseline/clandestine-neutralization-ren-orcamento.yaml"


class ClandestineNeutralizationArcTest(unittest.TestCase):
    def test_decima_segunda_linha_usa_teto_existente_sem_aumenta_lo(self):
        arc = arcos.load_contract(ROOT, "parte_1_uma_ponte_para_kozakura")
        self.assertEqual(arcos.MAX_OPERATIONAL_LINES, 12)
        self.assertEqual(len(arc["linhas_operacionais"]), 12)
        self.assertEqual(arcos.MAX_ORCHESTRATED_SOURCES, 8)
        self.assertEqual(len(arc["orquestracao"]["fontes"]), 8)

    def test_linha_tem_objetivo_clandestino_e_executores_compatíveis(self):
        arc = arcos.load_contract(ROOT, "parte_1_uma_ponte_para_kozakura")
        line = arc["linhas_operacionais"][LINE]
        self.assertEqual(
            line["objetivo"],
            "reduzir_capacidade_de_interferencia_de_ren_sem_revelar_comando_rotas_ou_ponte",
        )
        self.assertEqual(set(line["executores"]), EXECUTORS)
        self.assertEqual(line["referencia"], "neutralizacao_ren")
        self.assertNotIn("pan_chu", line["executores"])
        self.assertNotIn("sawagejo_cho", line["executores"])
        self.assertEqual(
            arc["orquestracao"]["fontes"]["neutralizacao_ren"]["arquivo"],
            "narrador/arcos/parte_1/neutralizacao-ren.yaml",
        )

    def test_fonte_especializada_preserva_ponto_cego_de_masao_e_nao_forca_morte(self):
        data = yaml.safe_load(SOURCE.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_neutralizacao_ren"], 1)
        self.assertEqual(data["natureza"], "reservado")
        self.assertEqual(data["estatuto"], "restricao_operacional_nao_canonica")
        self.assertTrue(data["condicao_de_uso"]["exige_evidencia_canonica_de_interferencia"])
        guard = data["guardrails"]
        self.assertTrue(guard["habilitado_nao_significa_escolhido"])
        self.assertTrue(guard["neutralizacao_nao_significa_morte"])
        self.assertTrue(guard["sucesso_nao_e_automatico"])
        self.assertTrue(guard["fato_so_existe_apos_resolucao"])
        self.assertTrue(guard["preservar_compartimentacao_da_rede"])
        self.assertTrue(guard["conhecimento_do_agente_limita_identidades_vinculos_e_rotas"])
        self.assertTrue(guard["metodo_fisico_exige_presenca_e_acesso_validos"])
        self.assertIn("ainda pode pensar", data["relacao_com_masao"])
        self.assertIn("ameaça central", data["relacao_com_masao"])

    def test_resolver_linha_continua_barato_e_nao_abre_executor(self):
        result = arcos.resolve_operational_line(ROOT, LINE)
        self.assertTrue(result["permitida"])
        self.assertEqual(set(result["executores"]), EXECUTORS)
        self.assertEqual(
            result["fonte_estrategica"],
            "narrador/arcos/parte_1/neutralizacao-ren.yaml",
        )
        self.assertEqual(len(result["fontes_lidas"]), 3)
        self.assertFalse(
            any(source.startswith("narrador/agentes/") for source in result["fontes_lidas"])
        )


class ClandestineNeutralizationMethodsTest(unittest.TestCase):
    def _methods(self, agent_id: str):
        data = agentes.load_agent_complete(ROOT, agent_id)["resultado"]
        return metodos_agentes.for_line(data, LINE, expected_agent_id=agent_id)

    def test_cada_executor_tem_duas_traducoes_compactas_e_sigilosas(self):
        for agent_id in sorted(EXECUTORS):
            methods = self._methods(agent_id)
            self.assertEqual(len(methods), 2, agent_id)
            for method in methods:
                self.assertIn("neutralizacao", method["tags"])
                self.assertIn("sigilo_rede", method["tags"])
                self.assertNotIn("matar", method["abordagem"].casefold())
                self.assertLessEqual(len(method["tags"]), 8)

    def test_modalidade_respeita_personalidade_e_presenca(self):
        self.assertEqual(
            {item["modalidade"] for item in self._methods("masao_hirasawa")},
            {"indireta"},
        )
        self.assertEqual(
            {item["modalidade"] for item in self._methods("kajiwara_shizune")},
            {"indireta"},
        )
        self.assertEqual(
            {item["modalidade"] for item in self._methods("kurobane_jinzaburo")},
            {"fisica"},
        )

    def test_resolver_metodos_abre_base_e_no_maximo_um_detalhe(self):
        for agent_id in sorted(EXECUTORS):
            result = arcos.resolve_agent_methods(ROOT, LINE, executor=agent_id)
            self.assertTrue(result["executor_permitido"])
            self.assertEqual(len(result["metodos"]), 2)
            self.assertEqual(result["fonte_agente"], f"narrador/agentes/{agent_id}.yaml")
            fragments = [
                source for source in result["fontes_lidas"]
                if source.startswith("narrador/agentes/") and source.endswith(".yaml")
                and source != "narrador/agentes/index.yaml"
            ]
            expected = [f"narrador/agentes/{agent_id}.yaml"]
            base = agentes.load_agent(ROOT, agent_id)["resultado"]
            pointer = base.get("detalhes_operacionais")
            if pointer:
                expected.append(pointer["arquivo"])
            self.assertEqual(fragments, expected)
            self.assertLessEqual(len(result["fontes_lidas"]), 6)


class ClandestineNeutralizationContextTest(unittest.TestCase):
    def test_kage_e_getsuei_sozinhos_nao_acionam_neutralizacao(self):
        result = contexto_cena.select_candidates(
            ROOT,
            ["pessoa:kage", "assunto:getsuei_ryu"],
            scene_id="task15-marcial",
        )
        self.assertNotIn(LINE, [item["id"] for item in result["operacoes"]])
        self.assertIn(
            "pressionar_identidade_marcial_de_ren",
            [item["id"] for item in result["operacoes"]],
        )

    def test_interferencia_explicita_de_ren_expoe_linha_sem_escolher_executor(self):
        result = contexto_cena.select_candidates(
            ROOT,
            ["pessoa:kage", "risco:ren_compromete_operacao"],
            scene_id="task15-interferencia",
        )
        matches = [item for item in result["operacoes"] if item["id"] == LINE]
        self.assertEqual(len(matches), 1)
        item = matches[0]
        self.assertEqual(set(item["executores"]), EXECUTORS)
        self.assertNotIn("executor", item)
        self.assertNotIn("metodo", item)
        self.assertFalse(any(source.startswith("narrador/agentes/") for source in result["fontes_lidas"]))

    def test_duas_tags_de_ameaca_explicitamente_ligadas_a_ren_tambem_bastam(self):
        result = contexto_cena.select_candidates(
            ROOT,
            ["risco:ren_expoe_rede", "assunto:ren_interferencia_repetida"],
            scene_id="task15-ameaca",
        )
        self.assertIn(LINE, [item["id"] for item in result["operacoes"]])


class ClandestineNeutralizationBudgetTest(unittest.TestCase):
    def test_contrato_congela_escopo_sem_scheduler_ou_estado_novo(self):
        data = yaml.safe_load(BUDGET.read_text(encoding="utf-8"))
        self.assertEqual(data["schema_orcamento_neutralizacao_ren"], 1)
        self.assertEqual(data["limites"]["max_linhas_operacionais_no_arco"], 12)
        self.assertEqual(data["limites"]["executores_da_linha"], 3)
        self.assertEqual(data["limites"]["max_metodos_por_executor"], 2)
        self.assertEqual(data["limites"]["max_schedulers_novos"], 0)
        self.assertEqual(data["limites"]["max_estados_novos"], 0)
        self.assertEqual(data["limites"]["max_scans_novos"], 0)
        self.assertEqual(data["contexto"]["min_coincidencias"], 2)
        self.assertTrue(data["invariantes"]["neutralizacao_nao_significa_morte"])
        self.assertTrue(data["invariantes"]["ren_nao_vira_ameaca_central_automaticamente"])
        self.assertTrue(data["invariantes"]["executor_nao_e_escolhido_pelo_contexto"])
        self.assertTrue(data["invariantes"]["metodo_nao_e_escolhido_pelo_contexto"])


if __name__ == "__main__":
    unittest.main()
