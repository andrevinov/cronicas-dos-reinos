from __future__ import annotations
import shutil,sys,tempfile,unittest,yaml
from pathlib import Path
ROOT=Path(__file__).parents[1]; TOOLS=ROOT/'ferramentas'
if str(TOOLS) not in sys.path: sys.path.insert(0,str(TOOLS))
import pressao_ravens_bluff as pr

class PressureMutationTest(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); self.repo=Path(self.t.name)
        for rel in (pr.PROFILE,pr.STATE):
            dst=self.repo/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/rel,dst)
        src=self.repo/'sessoes/011/consequencias.md'; src.parent.mkdir(parents=True,exist_ok=True); src.write_text('A Night Watch recebeu vinte novas ocorrências ligadas às docas.\n',encoding='utf-8')
    def tearDown(self): self.t.cleanup()
    def test_ajuste_exige_evidencia_literal_e_muda_um_nivel(self):
        r=pr.adjust(self.repo,'desgaste_da_autoridade',1,'sessoes/011/consequencias.md','A Night Watch recebeu vinte novas ocorrências ligadas às docas.','sessao 11','sobrecarga registrada')
        self.assertEqual((r['de'],r['para']),(0,1)); self.assertEqual(pr.load_state(self.repo)['frentes']['desgaste_da_autoridade']['nivel'],1)
    def test_nao_pode_pular_nivel(self):
        with self.assertRaises(pr.PressureError): pr.adjust(self.repo,'desgaste_da_autoridade',2,'sessoes/011/consequencias.md','A Night Watch recebeu vinte novas ocorrências ligadas às docas.','x','x')
    def test_planejamento_nao_prova_a_si_mesmo(self):
        with self.assertRaisesRegex(pr.PressureError,'não pode provar'):
            pr.adjust(self.repo,'custo_de_vida',1,str(pr.PROFILE),'Frentes medem consequências acumuladas','x','x')
    def test_evidencia_inventada_falha(self):
        with self.assertRaisesRegex(pr.PressureError,'não localizada'):
            pr.adjust(self.repo,'custo_de_vida',1,'sessoes/011/consequencias.md','algo que não existe','x','x')
if __name__=='__main__': unittest.main()
