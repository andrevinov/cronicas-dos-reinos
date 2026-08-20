from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import marcos_aparicao


class MarcosAparicaoTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self._write(
            "narrador/arcos/index.yaml",
            {
                "schema_arcos": 1,
                "natureza": "roteador_reservado",
                "arcos": {
                    "parte_1": {
                        "titulo": "Parte 1",
                        "ordem": 1,
                        "arquivo": "narrador/arcos/parte_1.yaml",
                        "proximo": None,
                    }
                },
            },
        )
        self._write(
            "narrador/arcos/estado.yaml",
            {
                "schema_estado_arcos": 2,
                "natureza": "controle_reservado",
                "arco_atual": "parte_1",
                "estado": "ativo",
                "historico_transicoes": [],
            },
        )
        self._write(
            "narrador/arcos/parte_1.yaml",
            {
                "schema_arco": 4,
                "natureza": "reservado",
                "estatuto": "contrato_orquestrador_de_arco",
                "id": "parte_1",
                "titulo": "Parte 1",
                "principio": "Contrato de teste.",
                "inicio": {"tipo": "fato_canonico", "marcador": "inicio", "fonte": "campanha.yaml"},
                "termino": {"tipo": "marco_explicito", "marcador": "fim", "fonte": "campanha.yaml"},
                "orquestracao": {
                    "fontes": {
                        "plano_mestre": {
                            "tipo": "documento_reservado",
                            "arquivo": "narrador/masao/plano.md",
                        }
                    },
                    "plano_mestre": {
                        "agente": "masao",
                        "objetivo": "objetivo",
                        "referencia": "plano_mestre",
                    },
                },
                "habilitacoes": {
                    "politica_nao_listados": "bloqueados",
                    "antagonistas": ["kurobane", "shizune", "cho", "pan"],
                    "aliados": [],
                    "direcoes": [],
                },
                "linhas_operacionais": {
                    "linha": {
                        "objetivo": "objetivo_linha",
                        "executores": ["kurobane", "shizune"],
                        "referencia": "plano_mestre",
                    }
                },
            },
        )
        self._write(
            "narrador/arcos/marcos-aparicao.yaml",
            {
                "schema_marcos_aparicao": 1,
                "natureza": "roteador_reservado",
                "fonte_canonica": "narrador/juppongatana/marcos-de-aparicao.md",
                "regras": {
                    "elegivel_nao_e_aparicao": True,
                    "consumido_nao_bloqueia_reaparicao": True,
                },
                "marcos": {
                    "kurobane": {"arco": "parte_1", "grupo": "antagonistas", "nivel_minimo": 6, "secao_fonte": "### Kurobane", "condicao_id": "provas"},
                    "shizune": {"arco": "parte_1", "grupo": "antagonistas", "nivel_minimo": 6, "secao_fonte": "### Shizune", "condicao_id": "institucional"},
                    "cho": {"arco": "parte_1", "grupo": "antagonistas", "nivel_minimo": 7, "secao_fonte": "### Cho", "condicao_id": "identidade_marcial"},
                    "pan": {"arco": "parte_1", "grupo": "antagonistas", "nivel_minimo": 7, "secao_fonte": "### Pan", "condicao_id": "rota_maritima"},
                },
            },
        )
        self._write(
            "narrador/arcos/estado-marcos-aparicao.yaml",
            {
                "schema_estado_marcos_aparicao": 1,
                "natureza": "controle_reservado",
                "marcos": {
                    "kurobane": {"estado": "consumido", "origem": "sessao", "nota": "já apareceu", "historico_recente": []},
                    "shizune": {"estado": "elegivel", "origem": "plano", "nota": "pode ser avaliada", "historico_recente": []},
                    "cho": {"estado": "bloqueado", "origem": "marcos", "nota": "ainda não", "historico_recente": []},
                    "pan": {"estado": "bloqueado", "origem": "marcos", "nota": "ainda não", "historico_recente": []},
                },
            },
        )
        self._write("runtime/contexto.yaml", {"personagem": {"nivel": 6}})
        self._write(
            "narrador/juppongatana/marcos-de-aparicao.md",
            "# Marcos\n### Kurobane\n### Shizune\n### Cho\n### Pan\n",
            raw=True,
        )

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, rel: str, value, *, raw: bool = False):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if raw:
            path.write_text(value, encoding="utf-8")
        else:
            path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def test_elegivel_mais_nivel_permite_so_avaliacao(self):
        result = marcos_aparicao.gate(self.repo, "shizune")
        self.assertTrue(result["permitido"])
        self.assertEqual(result["modo"], "avaliar_primeira_aparicao")
        self.assertEqual(result["estado_marco"], "elegivel")
        self.assertNotIn("presenca", result)

    def test_bloqueado_impede_mesmo_se_nivel_fosse_suficiente(self):
        result = marcos_aparicao.gate(self.repo, "cho", supplied_level=8)
        self.assertFalse(result["permitido"])
        self.assertEqual(result["motivo"], "condicao_narrativa_do_marco_ainda_bloqueada")

    def test_nivel_minimo_e_trava_independente(self):
        state = yaml.safe_load((self.repo / marcos_aparicao.STATE).read_text())
        state["marcos"]["cho"]["estado"] = "elegivel"
        self._write(marcos_aparicao.STATE.as_posix(), state)
        result = marcos_aparicao.gate(self.repo, "cho")
        self.assertFalse(result["permitido"])
        self.assertEqual(result["motivo"], "nivel_minimo_do_marco_nao_alcancado")

    def test_consumido_nao_bloqueia_reaparicao(self):
        result = marcos_aparicao.gate(self.repo, "kurobane")
        self.assertTrue(result["permitido"])
        self.assertEqual(result["modo"], "reaparicao_nao_bloqueada_pelo_marco")

    def test_arco_bloqueia_antes_de_ler_runtime_e_estado_de_marco(self):
        contract = yaml.safe_load((self.repo / "narrador/arcos/parte_1.yaml").read_text())
        contract["habilitacoes"]["antagonistas"].remove("shizune")
        contract["linhas_operacionais"]["linha"]["executores"].remove("shizune")
        self._write("narrador/arcos/parte_1.yaml", contract)
        (self.repo / marcos_aparicao.RUNTIME).unlink()
        (self.repo / marcos_aparicao.STATE).unlink()
        result = marcos_aparicao.gate(self.repo, "shizune")
        self.assertFalse(result["permitido"])
        self.assertEqual(result["motivo"], "agente_bloqueado_pelo_arco_antes_do_marco")
        self.assertNotIn(marcos_aparicao.RUNTIME.as_posix(), result["fontes_lidas"])

    def test_marcar_elegivel_e_consumir_sao_explicitamente_rastreados(self):
        first = marcos_aparicao.mutate(
            self.repo, "cho", action="marcar_elegivel", origin="teste", note="condição amadureceu"
        )
        self.assertEqual(first["para"], "elegivel")
        second = marcos_aparicao.mutate(
            self.repo, "cho", action="consumir", origin="sessao", note="apareceu"
        )
        self.assertEqual(second["para"], "consumido")
        state = marcos_aparicao.load_state(self.repo)
        self.assertEqual(len(state["marcos"]["cho"]["historico_recente"]), 2)

    def test_bloqueado_nao_pode_ser_consumido_diretamente(self):
        with self.assertRaisesRegex(marcos_aparicao.AppearanceMilestoneError, "bloqueado"):
            marcos_aparicao.mutate(
                self.repo, "pan", action="consumir", origin="teste", note="não pode"
            )

    def test_gate_e_read_only(self):
        before = (self.repo / marcos_aparicao.STATE).read_bytes()
        marcos_aparicao.gate(self.repo, "shizune")
        self.assertEqual(before, (self.repo / marcos_aparicao.STATE).read_bytes())

    def test_validacao_exige_marco_para_todo_antagonista_habilitado(self):
        index = yaml.safe_load((self.repo / marcos_aparicao.INDEX).read_text())
        del index["marcos"]["pan"]
        self._write(marcos_aparicao.INDEX.as_posix(), index)
        state = yaml.safe_load((self.repo / marcos_aparicao.STATE).read_text())
        del state["marcos"]["pan"]
        self._write(marcos_aparicao.STATE.as_posix(), state)
        result = marcos_aparicao.validate(self.repo)
        self.assertFalse(result["ok"])
        self.assertTrue(any("sem marco de aparição: pan" in error for error in result["erros"]))

    def test_validacao_confere_secoes_na_fonte_longa_sem_abri_la_no_gate(self):
        result = marcos_aparicao.validate(self.repo)
        self.assertTrue(result["ok"])
        gate = marcos_aparicao.gate(self.repo, "shizune")
        self.assertNotIn("narrador/juppongatana/marcos-de-aparicao.md", gate["fontes_lidas"])


if __name__ == "__main__":
    unittest.main()
