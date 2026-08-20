from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import aliados_contextuais


class AllyContextTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self._write("narrador/arcos/index.yaml", {
            "schema_arcos": 1, "natureza": "roteador_reservado",
            "arcos": {"parte_1": {"titulo": "Parte 1", "ordem": 1, "arquivo": "narrador/arcos/parte_1.yaml", "proximo": None}},
        })
        self._write("narrador/arcos/estado.yaml", {
            "schema_estado_arcos": 2, "natureza": "controle_reservado",
            "arco_atual": "parte_1", "estado": "ativo", "historico_transicoes": [],
        })
        self._write("narrador/arcos/parte_1.yaml", {
            "schema_arco": 4, "natureza": "reservado", "estatuto": "contrato_orquestrador_de_arco",
            "id": "parte_1", "titulo": "Parte 1", "principio": "Fixture de aliados contextuais.",
            "inicio": {"tipo": "fato_canonico", "marcador": "inicio", "fonte": "campanha.yaml"},
            "termino": {"tipo": "marco_explicito", "marcador": "fim", "fonte": "campanha.yaml"},
            "orquestracao": {
                "fontes": {"plano_mestre": {"tipo": "documento_reservado", "arquivo": "narrador/masao/plano.md"}},
                "plano_mestre": {"agente": "masao", "objetivo": "objetivo", "referencia": "plano_mestre"},
            },
            "habilitacoes": {
                "politica_nao_listados": "bloqueados", "antagonistas": [],
                "aliados": ["shen", "joen"], "direcoes": [],
            },
            "linhas_operacionais": {
                "linha": {"objetivo": "objetivo_linha", "executores": ["masao"], "referencia": "plano_mestre"},
            },
        })
        self._write("narrador/entradas/index.yaml", {
            "schema_entradas": 1, "natureza": "reservado", "cadencia_padrao_dias": 3,
            "candidatos": {
                "shen": {"nome": "Shen", "ordem": 1, "nivel_minimo_normal": 6, "arquivo": "narrador/entradas/shen.yaml"},
                "joen": {"nome": "Joen", "ordem": 2, "nivel_minimo_normal": 7, "arquivo": "narrador/entradas/joen.yaml"},
                "futuro": {"nome": "Futuro", "ordem": 3, "nivel_minimo_normal": 8, "arquivo": "narrador/entradas/futuro.yaml"},
            },
        })
        self._state(shen_due=None, shen_state="latente", level=6)

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, rel, data):
        p=self.repo/rel; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False),encoding="utf-8")

    def _state(self, *, shen_due, shen_state, level, shen_anticipated=False, joen_due=None, joen_state="latente", shen_open=True, joen_open=False):
        self._write("narrador/entradas/estado.yaml", {
            "schema_estado_entradas": 1, "natureza": "controle_reservado",
            "candidatos": {
                "shen": {"estado": shen_state, "antecipado": shen_anticipated, "proxima_avaliacao": shen_due, "historico_recente": ([{"acao": "abrir_janela_contextual"}] if shen_open and shen_due is None and shen_state == "latente" else [])},
                "joen": {"estado": joen_state, "antecipado": False, "proxima_avaliacao": joen_due, "historico_recente": ([{"acao": "abrir_janela_contextual"}] if joen_open and joen_due is None and joen_state == "latente" else [])},
                "futuro": {"estado": "latente", "antecipado": False, "proxima_avaliacao": None, "historico_recente": []},
            },
        })
        self._write("runtime/contexto.yaml", {"personagem": {"nivel": level}})

    def test_shen_com_janela_aberta_e_foco_pode_ser_avaliada(self):
        gate=aliados_contextuais.gate(self.repo,"shen")
        self.assertTrue(gate["permitido"])
        self.assertEqual(gate["motivo"],"janela_contextual_aberta")
        self.assertEqual(gate["modo"],"avaliar_entrada_organica")

    def test_data_futura_bloqueia_mesmo_com_arco_e_nivel(self):
        self._state(shen_due={"data":"14 Eleasis, 1372 DR","hora":"06:00"}, shen_state="latente", level=6)
        gate=aliados_contextuais.gate(self.repo,"shen")
        self.assertFalse(gate["permitido"])
        self.assertEqual(gate["motivo"],"janela_contextual_ainda_fechada")

    def test_joen_nao_fura_ordem_enquanto_shen_latente(self):
        gate=aliados_contextuais.gate(self.repo,"joen")
        self.assertFalse(gate["permitido"])
        self.assertEqual(gate["motivo"],"aguarda_ordem_preferencial")

    def test_joen_vira_foco_depois_de_shen_presente_mas_ainda_respeita_nivel(self):
        self._state(shen_due=None, shen_state="presente", level=6, joen_due=None, joen_open=True)
        gate=aliados_contextuais.gate(self.repo,"joen")
        self.assertFalse(gate["permitido"])
        self.assertEqual(gate["motivo"],"nivel_minimo_nao_alcancado")
        self._state(shen_due=None, shen_state="presente", level=7, joen_due=None, joen_open=True)
        self.assertTrue(aliados_contextuais.gate(self.repo,"joen")["permitido"])

    def test_aliado_presente_ou_inviavel_nao_e_proposto(self):
        self._state(shen_due=None, shen_state="presente", level=7, joen_due=None, joen_state="inviavel")
        self.assertEqual(aliados_contextuais.gate(self.repo,"shen")["motivo"],"aliado_ja_presente")
        self.assertEqual(aliados_contextuais.gate(self.repo,"joen")["motivo"],"aliado_inviavel")

    def test_fora_do_arco_para_antes_de_ler_entradas(self):
        # "futuro" existe na camada de entradas mas não está habilitado no arco.
        (self.repo/"narrador/entradas/estado.yaml").unlink()
        gate=aliados_contextuais.gate(self.repo,"futuro")
        self.assertFalse(gate["permitido"])
        self.assertEqual(gate["motivo"],"aliado_bloqueado_pelo_arco")
        self.assertNotIn("narrador/entradas/estado.yaml", gate["fontes_lidas"])

    def test_null_sem_registro_de_abertura_nao_vira_janela_por_acidente(self):
        self._state(shen_due=None, shen_state="latente", level=6, shen_open=False)
        gate=aliados_contextuais.gate(self.repo,"shen")
        self.assertFalse(gate["permitido"])
        self.assertEqual(gate["motivo"],"janela_contextual_nao_aberta")

    def test_gate_e_somente_leitura(self):
        path=self.repo/"narrador/entradas/estado.yaml"; before=path.read_bytes()
        aliados_contextuais.gate(self.repo,"shen")
        self.assertEqual(before,path.read_bytes())

    def test_antecipacao_nao_fura_janela_temporal(self):
        self._state(shen_due={"data":"13 Eleasis, 1372 DR","hora":"06:00"}, shen_state="latente", level=5, shen_anticipated=True)
        gate=aliados_contextuais.gate(self.repo,"shen")
        self.assertFalse(gate["permitido"])
        self.assertEqual(gate["motivo"],"janela_contextual_ainda_fechada")
        self._state(shen_due=None, shen_state="latente", level=5, shen_anticipated=True, shen_open=True)
        self.assertTrue(aliados_contextuais.gate(self.repo,"shen")["permitido"])


if __name__ == "__main__":
    unittest.main()
