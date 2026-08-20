from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
import sys
import yaml

ROOT=Path(__file__).parents[1]
TOOLS=ROOT/"ferramentas"
if str(TOOLS) not in sys.path: sys.path.insert(0,str(TOOLS))

import contexto_cena


class ContextSceneAlliesTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.repo=Path(self.temp.name)
        self._write("narrador/mundo/contextos-cena.yaml",{
            "schema_contextos_cena":3,"natureza":"roteador_reservado",
            "orcamento":{"max_tags_por_cena":8,"max_presencas":2,"max_entradas":1,"max_operacoes":2,"max_direcoes":1,"max_candidatos_total":4,"ordenacao":"coincidencias_prioridade_tipo_id"},
            "candidatos":{
                "entrada_shen":{"tipo":"entrada","alvo":"shen","prioridade":100,"min_coincidencias":1,"tags":["pressao_shizune"]},
                "entrada_joen":{"tipo":"entrada","alvo":"joen","prioridade":90,"min_coincidencias":1,"tags":["derrota_grave"]},
            },
        })
        self._write("narrador/arcos/index.yaml",{"schema_arcos":1,"natureza":"roteador_reservado","arcos":{"p1":{"titulo":"P1","ordem":1,"arquivo":"narrador/arcos/p1.yaml","proximo":None}}})
        self._write("narrador/arcos/estado.yaml",{"schema_estado_arcos":2,"natureza":"controle_reservado","arco_atual":"p1","estado":"ativo","historico_transicoes":[]})
        self._write("narrador/arcos/p1.yaml",{
            "schema_arco":4,"natureza":"reservado","estatuto":"contrato_orquestrador_de_arco","id":"p1","titulo":"P1","principio":"fixture",
            "inicio":{"tipo":"fato_canonico","marcador":"inicio","fonte":"campanha.yaml"},"termino":{"tipo":"marco_explicito","marcador":"fim","fonte":"campanha.yaml"},
            "orquestracao":{"fontes":{"plano":{"tipo":"documento_reservado","arquivo":"narrador/masao/plano.md"}},"plano_mestre":{"agente":"masao","objetivo":"obj","referencia":"plano"}},
            "habilitacoes":{"politica_nao_listados":"bloqueados","antagonistas":[],"aliados":["shen","joen"],"direcoes":[]},
            "linhas_operacionais":{"linha":{"objetivo":"obj_linha","executores":["masao"],"referencia":"plano"}},
        })
        self._write("narrador/entradas/index.yaml",{
            "schema_entradas":1,"natureza":"reservado","cadencia_padrao_dias":3,
            "candidatos":{"shen":{"nome":"Shen","ordem":1,"nivel_minimo_normal":6,"arquivo":"narrador/entradas/shen.yaml"},"joen":{"nome":"Joen","ordem":2,"nivel_minimo_normal":7,"arquivo":"narrador/entradas/joen.yaml"}},
        })
        self._state(shen_due=None,shen_state="latente",level=6)

    def tearDown(self): self.temp.cleanup()
    def _write(self,rel,data):
        p=self.repo/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False),encoding="utf-8")
    def _state(self,*,shen_due,shen_state,level,joen_due=None,shen_open=True,joen_open=False):
        self._write("narrador/entradas/estado.yaml",{"schema_estado_entradas":1,"natureza":"controle_reservado","candidatos":{"shen":{"estado":shen_state,"antecipado":False,"proxima_avaliacao":shen_due,"historico_recente":([{"acao":"abrir_janela_contextual"}] if shen_open and shen_due is None and shen_state=="latente" else [])},"joen":{"estado":"latente","antecipado":False,"proxima_avaliacao":joen_due,"historico_recente":([{"acao":"abrir_janela_contextual"}] if joen_open and joen_due is None else [])}}})
        self._write("runtime/contexto.yaml",{"personagem":{"nivel":level}})

    def test_contexto_forte_retorna_shen_somente_com_janela_aberta(self):
        r=contexto_cena.select_candidates(self.repo,["pressao_shizune"],scene_id="s1")
        self.assertEqual([x["id"] for x in r["entradas"]],["shen"])
        self.assertEqual(r["entradas"][0]["modo_avaliacao"],"avaliar_entrada_organica")
        self.assertNotIn("resultado",r["entradas"][0])
        self._state(shen_due={"data":"14 Eleasis, 1372 DR","hora":"06:00"},shen_state="latente",level=6)
        r=contexto_cena.select_candidates(self.repo,["pressao_shizune"],scene_id="s2")
        self.assertEqual(r["entradas"],[])

    def test_joen_nao_aparece_pela_tag_se_shen_ainda_e_foco(self):
        r=contexto_cena.select_candidates(self.repo,["derrota_grave"],scene_id="s3")
        self.assertEqual(r["entradas"],[])

    def test_shen_presente_level7_libera_joen_quando_janela_aberta(self):
        self._state(shen_due=None,shen_state="presente",level=7,joen_due=None,joen_open=True)
        r=contexto_cena.select_candidates(self.repo,["derrota_grave"],scene_id="s4")
        self.assertEqual([x["id"] for x in r["entradas"]],["joen"])

    def test_entrada_contextual_abre_zero_fragmentos(self):
        r=contexto_cena.select_candidates(self.repo,["pressao_shizune"],scene_id="s5")
        self.assertNotIn("narrador/entradas/shen.yaml",r["fontes_lidas"])
        self.assertIn("narrador/entradas/index.yaml",r["fontes_lidas"])
        self.assertIn("narrador/entradas/estado.yaml",r["fontes_lidas"])


if __name__=="__main__": unittest.main()
