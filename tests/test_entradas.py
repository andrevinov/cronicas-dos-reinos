from __future__ import annotations
import tempfile, unittest
from pathlib import Path
import yaml

ROOT=Path(__file__).parents[1]
TOOLS=ROOT/"ferramentas"
import sys
if str(TOOLS) not in sys.path: sys.path.insert(0,str(TOOLS))
import entradas

class EntradasRepositoryTest(unittest.TestCase):
    def test_repositorio_real_valida_cinco_aliados(self):
        r=entradas.validate(ROOT)
        self.assertTrue(r["ok"],r["erros"]); self.assertEqual(r["quantidade"],5)

    def test_estado_inicial_so_agenda_shen(self):
        index=entradas.load_index(ROOT); state=entradas.load_state(ROOT,index)
        self.assertEqual(entradas.normal(index,state),"shen_meihua")
        self.assertEqual(state["candidatos"]["shen_meihua"]["proxima_avaliacao"],{"data":"11 Eleasis, 1372 DR","hora":"06:00"})
        for cid in entradas.ordered(index)[1:]: self.assertIsNone(state["candidatos"][cid]["proxima_avaliacao"])

    def test_status_real_identifica_shen_sem_abrir_fragmentos(self):
        r=entradas.status(ROOT)
        self.assertEqual(r["candidato_normal"],"shen_meihua"); self.assertEqual(r["candidato_em_foco"]["nivel_atual"],6)
        self.assertTrue(r["candidato_em_foco"]["elegivel_por_nivel"])
        self.assertEqual(r["fontes_lidas"],["narrador/entradas/index.yaml","narrador/entradas/estado.yaml","runtime/contexto.yaml"])

    def test_consulta_de_jenilynn_e_fragmentada(self):
        r=entradas.show(ROOT,"Jenilynn")
        self.assertEqual(r["candidato"],"dame_jenilynn_leyland")
        self.assertIn("narrador/entradas/dame_jenilynn_leyland.yaml",r["fontes_lidas"])
        self.assertNotIn("narrador/entradas/shen_meihua.yaml",r["fontes_lidas"])

class EntradasSyntheticTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.repo=Path(self.tmp.name)
        for p in ("narrador/entradas","narrador/mundo","runtime","estado","fontes"): (self.repo/p).mkdir(parents=True,exist_ok=True)
        (self.repo/"fontes/canone.md").write_text("1. A;\n2. B.\nJanela A.\nJanela B.\n",encoding="utf-8")
        self.write("narrador/entradas/index.yaml",{"schema_entradas":1,"natureza":"reservado","cadencia_padrao_dias":3,"candidatos":{"a":{"nome":"Aliado A","ordem":1,"nivel_minimo_normal":6,"arquivo":"narrador/entradas/a.yaml"},"b":{"nome":"Aliado B","ordem":2,"nivel_minimo_normal":9,"arquivo":"narrador/entradas/b.yaml"}}})
        self.write("narrador/entradas/estado.yaml",{"schema_estado_entradas":1,"natureza":"controle_reservado","candidatos":{"a":{"estado":"latente","antecipado":False,"proxima_avaliacao":{"data":"11 Eleasis, 1372 DR","hora":"06:00"},"historico_recente":[]},"b":{"estado":"latente","antecipado":False,"proxima_avaliacao":None,"historico_recente":[]}}})
        for cid,name,order,level,ev in (("a","Aliado A",1,6,"1. A;"),("b","Aliado B",2,9,"2. B.")):
            self.write(f"narrador/entradas/{cid}.yaml",{"schema_entrada":1,"natureza":"reservado","id":cid,"nome":name,"ordem":order,"nivel_minimo_normal":level,"janela_preferencial":f"Janela {cid.upper()}.","gatilhos_fortes":["gatilho"],"forma_preferencial":"forma","funcao_imediata":"função","ancoras":[{"fonte":"fontes/canone.md","evidencia":ev}],"fontes_canonicas":["fontes/canone.md"]})
        self.write("runtime/contexto.yaml",{"personagem":{"nivel":6}})
        self.write("estado/tempo.yaml",{"schema_tempo":1,"natureza":"tempo_atual","data_atual":"11 Eleasis, 1372 DR","hora_aproximada":"06:00 de 11 Eleasis"})
        self.write("narrador/mundo/agenda.yaml",{"schema_agenda_mundo":1,"natureza":"reservado","hora_amanhecer":"06:00","reavaliacoes":{},"agendamentos":[]})
        self.write("narrador/mundo/estado.yaml",{"schema_estado_mundo":1,"natureza":"controle_reservado","processado_ate":{"data":"10 Eleasis, 1372 DR","hora":"17:42"},"pendencias":[],"concluidas_recentes":[]})

    def tearDown(self): self.tmp.cleanup()
    def write(self,rel,obj):
        p=self.repo/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(yaml.safe_dump(obj,allow_unicode=True,sort_keys=False),encoding="utf-8")
    def read(self,rel): return yaml.safe_load((self.repo/rel).read_text(encoding="utf-8"))

    def test_checkpoint_gera_uma_unica_avaliacao_e_avanca_cadencia(self):
        r=entradas.process_checkpoint(self.repo)
        self.assertEqual(r["entradas_reconsiderar"],["a"]); self.assertEqual(len(r["novas_pendencias"]),1)
        self.assertEqual(r["novas_pendencias"][0]["tipo"],"avaliar_entrada")
        self.assertEqual(self.read("narrador/entradas/estado.yaml")["candidatos"]["a"]["proxima_avaliacao"],{"data":"14 Eleasis, 1372 DR","hora":"06:00"})
        self.assertNotIn("narrador/entradas/a.yaml",r["fontes_lidas"])

    def test_nivel_baixo_adia_sem_criar_pendencia(self):
        rt=self.read("runtime/contexto.yaml"); rt["personagem"]["nivel"]=5; self.write("runtime/contexto.yaml",rt)
        r=entradas.process_checkpoint(self.repo)
        self.assertEqual(r["novas_pendencias"],[]); self.assertEqual(r["adiada_por_nivel"],"a")
        self.assertEqual(self.read("narrador/mundo/estado.yaml")["pendencias"],[])

    def test_pendencia_aberta_nao_duplica(self):
        entradas.process_checkpoint(self.repo)
        t=self.read("estado/tempo.yaml"); t["data_atual"]="14 Eleasis, 1372 DR"; t["hora_aproximada"]="06:00 de 14 Eleasis"; self.write("estado/tempo.yaml",t)
        r=entradas.process_checkpoint(self.repo)
        self.assertEqual(r["novas_pendencias"],[]); self.assertEqual(len(self.read("narrador/mundo/estado.yaml")["pendencias"]),1)

    def test_confirmar_primeiro_libera_segundo_no_proximo_amanhecer(self):
        r=entradas.mutate(self.repo,"a","confirmar","sessao:9","A entrou em cena.")
        self.assertEqual(r["proximo_candidato_normal"],"b")
        st=self.read("narrador/entradas/estado.yaml"); self.assertEqual(st["candidatos"]["a"]["estado"],"presente")
        self.assertEqual(st["candidatos"]["b"]["proxima_avaliacao"],{"data":"12 Eleasis, 1372 DR","hora":"06:00"})

    def test_antecipacao_fura_ordem_e_nivel_mas_e_unica(self):
        entradas.mutate(self.repo,"b","antecipar","consequencia:test","Pedido direto de ajuda.")
        st=self.read("narrador/entradas/estado.yaml"); self.assertEqual(entradas.focus(entradas.load_index(self.repo),st),"b")
        with self.assertRaises(entradas.EntryError): entradas.mutate(self.repo,"a","antecipar","x","y")
        t=self.read("estado/tempo.yaml"); t["data_atual"]="12 Eleasis, 1372 DR"; t["hora_aproximada"]="06:00 de 12 Eleasis"; self.write("estado/tempo.yaml",t)
        r=entradas.process_checkpoint(self.repo); self.assertEqual(r["entradas_reconsiderar"],["b"])

    def test_confirmacao_exige_origem_e_nota(self):
        with self.assertRaises(entradas.EntryError): entradas.mutate(self.repo,"a","confirmar","","")

    def test_avaliacao_nao_toca_estado_publico(self):
        p=self.repo/"estado/estado-atual.yaml"; p.write_text("sentinela: intacta\n",encoding="utf-8"); before=p.read_bytes()
        entradas.process_checkpoint(self.repo); self.assertEqual(before,p.read_bytes())

    def test_validacao_rejeita_evidencia_inventada(self):
        a=self.read("narrador/entradas/a.yaml"); a["ancoras"][0]["evidencia"]="não existe"; self.write("narrador/entradas/a.yaml",a)
        r=entradas.validate(self.repo); self.assertFalse(r["ok"]); self.assertIn("evidência",r["erros"][0])

if __name__=="__main__": unittest.main()
