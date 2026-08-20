from __future__ import annotations
import importlib.util,shutil,tempfile,unittest,yaml
from pathlib import Path
ROOT=Path(__file__).parents[1]
spec=importlib.util.spec_from_file_location('apply11',ROOT/'APLICAR-FASE11.py'); apply11=importlib.util.module_from_spec(spec); spec.loader.exec_module(apply11)

class Phase11PatchTest(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); self.repo=Path(self.t.name)
        # required new files
        for rel in ('narrador/direcoes/golden_lily_em_ravens_bluff.yaml','narrador/arcos/parte_1/pressao-ravens-bluff.yaml','ferramentas/autonomia_juppongatana.py'):
            dst=self.repo/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(ROOT/rel,dst)
        self.write('narrador/direcoes/index.yaml',{'schema_direcoes':1,'natureza':'reservado','direcoes':{'ponte_de_kozakura':{'nome':'Ponte de Kozakura','arquivo':'narrador/direcoes/ponte_de_kozakura.yaml','avaliacao':{'cadencia':'amanhecer','intervalo_dias':2,'inicio':'12 Eleasis, 1372 DR'},'ativacao':None}}})
        self.write('narrador/direcoes/estado.yaml',{'schema_estado_direcoes':1,'natureza':'controle_reservado','direcoes':{'ponte_de_kozakura':{'estado':'ativa','marco_atual':'coisas_plausiveis','marcos_concluidos':[],'historico_recente':[]}}})
        self.write('narrador/mundo/agenda.yaml',{'schema_agenda_mundo':1,'natureza':'reservado','hora_amanhecer':'06:00','reavaliacoes':{'kurobane_jinzaburo':{'cadencia':'amanhecer','intervalo_dias':2,'inicio':'12 Eleasis, 1372 DR','motivo':'x'}},'agendamentos':[]})
    def tearDown(self): self.t.cleanup()
    def write(self,rel,d):
        p=self.repo/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(yaml.safe_dump(d,allow_unicode=True,sort_keys=False),encoding='utf-8')
    def test_patch_adiciona_direcao_reavaliacoes_e_relogio_exato(self):
        self.assertTrue(apply11.patch_directions(self.repo)); self.assertTrue(apply11.patch_agenda(self.repo))
        idx=yaml.safe_load((self.repo/'narrador/direcoes/index.yaml').read_text()); st=yaml.safe_load((self.repo/'narrador/direcoes/estado.yaml').read_text()); ag=yaml.safe_load((self.repo/'narrador/mundo/agenda.yaml').read_text())
        self.assertIn('golden_lily_em_ravens_bluff',idx['direcoes']); self.assertEqual(st['direcoes']['golden_lily_em_ravens_bluff']['marco_atual'],'rumores_de_grande_navio')
        event=[x for x in ag['agendamentos'] if x['id']=='chegada_golden_lily_27_eleasis'][0]
        self.assertEqual(event['em'],{'data':'27 Eleasis, 1372 DR','hora':'10:00'}); self.assertEqual(event['tipo'],'movimento'); self.assertEqual(event['agente'],'pan_chu')
        self.assertIn('kajiwara_shizune',ag['reavaliacoes']); self.assertIn('sawagejo_cho',ag['reavaliacoes']); self.assertIn('pan_chu',ag['reavaliacoes'])
    def test_patch_e_idempotente(self):
        apply11.patch_directions(self.repo); apply11.patch_agenda(self.repo)
        self.assertFalse(apply11.patch_directions(self.repo)); self.assertFalse(apply11.patch_agenda(self.repo))
        ag=yaml.safe_load((self.repo/'narrador/mundo/agenda.yaml').read_text()); self.assertEqual(sum(1 for x in ag['agendamentos'] if x['id']=='chegada_golden_lily_27_eleasis'),1)
if __name__=='__main__': unittest.main()
