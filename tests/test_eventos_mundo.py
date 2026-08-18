from __future__ import annotations
import sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import yaml

ROOT=Path(__file__).parents[1]
TOOLS=ROOT/"ferramentas"
if str(TOOLS) not in sys.path: sys.path.insert(0,str(TOOLS))
import eventos_mundo, mundo

class EventosRepoTest(unittest.TestCase):
    def test_repo_real_valida_dez_cartas(self):
        r=eventos_mundo.validate_repo(ROOT); self.assertTrue(r["ok"],r["erros"]); self.assertEqual(r["quantidade_cartas"],10)
    def test_estado_inicial_sem_retroatividade(self):
        r=eventos_mundo.status(ROOT); self.assertEqual(r["processado_ate"]["data"],"10 Eleasis, 1372 DR"); self.assertEqual(r["ocorrencia"]["ciclo"],0); self.assertEqual(r["eventos"]["ciclo"],0); self.assertEqual(r["historico_recente"],[])
    def test_urna_real_e_sete_por_tres(self):
        idx=eventos_mundo.load_index(ROOT); out=[x["resultado"] for x in idx["ocorrencia"]["fichas"]]; self.assertEqual(out.count("rotina"),7); self.assertEqual(out.count("evento"),3)
    def test_consulta_e_fragmentada(self):
        r=eventos_mundo.show(ROOT,"Acidente no porto"); self.assertEqual(r["evento_id"],"acidente_no_porto"); self.assertEqual(r["fontes_lidas"],["narrador/eventos/index.yaml","narrador/eventos/cartas/acidente_no_porto.yaml"])

class EventosSinteticosTest(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); self.repo=Path(self.t.name)
        self.y("narrador/eventos/index.yaml",{"schema_eventos_mundo":1,"natureza":"reservado","semente":"seed","inicio":{"data":"11 Eleasis, 1372 DR","hora":"06:00"},"ocorrencia":{"fichas":[{"id":"r","resultado":"rotina"},{"id":"e","resultado":"evento"}]},"cartas":{"a":{"nome":"Carta A","categoria":"teste","escala":"bairro","arquivo":"narrador/eventos/cartas/a.yaml"},"b":{"nome":"Carta B","categoria":"teste","escala":"cidade","arquivo":"narrador/eventos/cartas/b.yaml"}}})
        for cid,esc in (("a","bairro"),("b","cidade")):
            self.y(f"narrador/eventos/cartas/{cid}.yaml",{"schema_evento_mundo":1,"natureza":"reservado","estatuto":"molde_nao_canonico_ate_resolucao","id":cid,"nome":f"Carta {cid.upper()}","categoria":"teste","escala":esc,"premissa":"Algo pode acontecer.","pergunta_de_resolucao":"O que realmente acontece?","guardrails":["Não canonizar automaticamente."],"tags":["teste"]})
        self.y("narrador/eventos/estado.yaml",{"schema_estado_eventos_mundo":1,"natureza":"controle_reservado","processado_ate":{"data":"10 Eleasis, 1372 DR","hora":"06:00"},"ocorrencia":{"ciclo":0,"restantes":[]},"eventos":{"ciclo":0,"restantes":[]},"historico_recente":[]})
        self.y("narrador/mundo/agenda.yaml",{"schema_agenda_mundo":1,"natureza":"reservado","hora_amanhecer":"06:00","reavaliacoes":{},"agendamentos":[]})
        self.y("narrador/mundo/estado.yaml",{"schema_estado_mundo":1,"natureza":"controle_reservado","processado_ate":{"data":"10 Eleasis, 1372 DR","hora":"17:42"},"pendencias":[],"concluidas_recentes":[]})
        self.tempo("10 Eleasis, 1372 DR","17:42 de 10 Eleasis")
    def tearDown(self): self.t.cleanup()
    def y(self,rel,v):
        p=self.repo/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(yaml.safe_dump(v,allow_unicode=True,sort_keys=False),encoding="utf-8")
    def read(self,rel): return yaml.safe_load((self.repo/rel).read_text(encoding="utf-8"))
    def tempo(self,d,h): self.y("estado/tempo.yaml",{"schema_tempo":1,"natureza":"tempo_atual","data_atual":d,"hora_aproximada":h})
    def test_ordem_e_reprodutivel(self):
        a=eventos_mundo.deck_order("x","eventos",1,["a","b","c","d"]); b=eventos_mundo.deck_order("x","eventos",1,["a","b","c","d"]); self.assertEqual(a,b); self.assertEqual(sorted(a),["a","b","c","d"])
    def test_rotina_nao_cria_pendencia(self):
        st=self.read("narrador/eventos/estado.yaml"); st["ocorrencia"]={"ciclo":1,"restantes":["r","e"]}; self.y("narrador/eventos/estado.yaml",st); self.tempo("11 Eleasis, 1372 DR","06:01 de 11 Eleasis"); r=eventos_mundo.process_checkpoint(self.repo); self.assertEqual(r["dias_rotina"],1); self.assertEqual(r["novas_pendencias"],[])
    def test_evento_cria_pendencia_sem_abrir_fragmento(self):
        st=self.read("narrador/eventos/estado.yaml"); st["ocorrencia"]={"ciclo":1,"restantes":["e","r"]}; st["eventos"]={"ciclo":1,"restantes":["a","b"]}; self.y("narrador/eventos/estado.yaml",st); self.tempo("11 Eleasis, 1372 DR","06:01 de 11 Eleasis"); r=eventos_mundo.process_checkpoint(self.repo); self.assertEqual(r["eventos_reconsiderar"],["a"]); self.assertNotIn("narrador/eventos/cartas/a.yaml",r["fontes_lidas"]); p=self.read("narrador/mundo/estado.yaml")["pendencias"][0]; self.assertEqual(p["tipo"],"evento_mundial"); self.assertEqual(p["agentes_afetados"],[])
    def test_sem_repeticao_antes_de_esgotar(self):
        idx=self.read("narrador/eventos/index.yaml"); idx["ocorrencia"]["fichas"]=[{"id":"e1","resultado":"evento"},{"id":"e2","resultado":"evento"},{"id":"r","resultado":"rotina"}]; self.y("narrador/eventos/index.yaml",idx); st=self.read("narrador/eventos/estado.yaml"); st["ocorrencia"]={"ciclo":1,"restantes":["e1","e2","r"]}; st["eventos"]={"ciclo":1,"restantes":["a","b"]}; self.y("narrador/eventos/estado.yaml",st); self.tempo("12 Eleasis, 1372 DR","06:01 de 12 Eleasis"); r=eventos_mundo.process_checkpoint(self.repo); self.assertEqual(r["eventos_sorteados"],["a","b"]); self.assertEqual(len(set(r["eventos_sorteados"])),2)
    def test_retry_repara_sem_duplicar(self):
        st=self.read("narrador/eventos/estado.yaml"); st["ocorrencia"]={"ciclo":1,"restantes":["e","r"]}; st["eventos"]={"ciclo":1,"restantes":["a","b"]}; self.y("narrador/eventos/estado.yaml",st); dawn=mundo.parse_instant("11 Eleasis, 1372 DR","06:00"); ws=self.read("narrador/mundo/estado.yaml"); ws["pendencias"]=[{"id":eventos_mundo.pending_id("a",dawn),"tipo":"evento_mundial","evento":"a","categoria":"teste","escala":"bairro","agentes_afetados":[],"disparado_em":mundo.instant_parts(dawn),"motivo":"já gravado","origem":"eventos:a"}]; self.y("narrador/mundo/estado.yaml",ws); self.tempo("11 Eleasis, 1372 DR","06:01 de 11 Eleasis"); r=eventos_mundo.process_checkpoint(self.repo); self.assertEqual(r["novas_pendencias"],[]); self.assertEqual(len(self.read("narrador/mundo/estado.yaml")["pendencias"]),1); self.assertEqual(self.read("narrador/eventos/estado.yaml")["eventos"]["restantes"],["b"])
    def test_fragmento_canonico_e_rejeitado(self):
        d=self.read("narrador/eventos/cartas/a.yaml"); d["estatuto"]="canonico"; self.y("narrador/eventos/cartas/a.yaml",d); r=eventos_mundo.validate_repo(self.repo); self.assertFalse(r["ok"])

if __name__=="__main__": unittest.main()
