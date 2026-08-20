from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import metodos_agentes


class MetodosAgentesTest(unittest.TestCase):
    def _base(self):
        return {
            "id": "agente_teste",
            "metodos_operacionais": {
                "linha_teste": [
                    {
                        "id": "metodo_teste",
                        "abordagem": "Uma abordagem genérica e ainda não executada.",
                        "modalidade": "mista",
                        "tags": ["documentos", "vigilancia"],
                    }
                ]
            },
        }

    def test_normaliza_metodo_compacto(self):
        result = metodos_agentes.from_agent(self._base())
        self.assertEqual(result["linha_teste"][0]["id"], "metodo_teste")
        self.assertEqual(result["linha_teste"][0]["modalidade"], "mista")

    def test_campos_de_alvo_momento_ou_acao_concreta_sao_rejeitados(self):
        for field in ("alvo", "momento", "acao", "resultado"):
            with self.subTest(field=field):
                data = self._base()
                data["metodos_operacionais"]["linha_teste"][0][field] = "algo"
                with self.assertRaisesRegex(metodos_agentes.AgentMethodError, "campos não permitidos"):
                    metodos_agentes.from_agent(data)

    def test_modalidade_precisa_ser_controlada(self):
        data = self._base()
        data["metodos_operacionais"]["linha_teste"][0]["modalidade"] = "telepatica"
        with self.assertRaisesRegex(metodos_agentes.AgentMethodError, "modalidade inválida"):
            metodos_agentes.from_agent(data)

    def test_tags_sao_obrigatorias_unicas_e_limitadas(self):
        data = self._base()
        data["metodos_operacionais"]["linha_teste"][0]["tags"] = ["x", "x"]
        with self.assertRaisesRegex(metodos_agentes.AgentMethodError, "duplicatas"):
            metodos_agentes.from_agent(data)

    def test_ids_de_metodo_sao_unicos_no_agente(self):
        data = self._base()
        data["metodos_operacionais"]["outra_linha"] = [
            {
                "id": "metodo_teste",
                "abordagem": "Outra abordagem.",
                "modalidade": "fisica",
                "tags": ["rota"],
            }
        ]
        with self.assertRaisesRegex(metodos_agentes.AgentMethodError, "método duplicado"):
            metodos_agentes.from_agent(data)

    def test_tetos_do_schema_batem_com_o_orcamento(self):
        import yaml
        budget = yaml.safe_load(
            (ROOT / "baseline/mundo-vivo-integracao-orcamento.yaml").read_text(encoding="utf-8")
        )["limites"]["traducao_linha_por_agente"]
        self.assertEqual(
            metodos_agentes.MAX_METHODS_PER_LINE, budget["max_metodos_por_linha_agente"]
        )
        self.assertEqual(
            metodos_agentes.MAX_TAGS_PER_METHOD, budget["max_tags_por_metodo"]
        )

    def test_agente_sem_metodos_continua_valido_para_outras_camadas(self):
        self.assertEqual(metodos_agentes.from_agent({"id": "agente_teste"}), {})


if __name__ == "__main__":
    unittest.main()
