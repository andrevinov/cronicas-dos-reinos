"""Lifecycle real em sandbox, fonte congelada e revisão sem save futuro."""
from copy import deepcopy
import json
import os
import shutil
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import yaml
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'ferramentas'),str(ROOT/'tests')]
import evidencias_sessao as capture
import cronica
import ciclo_cronica
import test_unified_session_lifecycle as fixtures
import test_agentes as agent_fixtures
from ferramentas import entrada_medicao as frozen
from ferramentas import revisao_sessao as review

class SessionEvidenceTest(unittest.TestCase):
 def setUp(self):
  self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.repo=self.root/'repo';self.repo.mkdir()
  fixtures.make_session_repo(self.repo)
  tempo=yaml.safe_load((self.repo/'estado/tempo.yaml').read_text());tempo['schema_tempo']=1;self.write('estado/tempo.yaml',tempo)
  self.env=patch.dict(os.environ,{'CRONICAS_EVIDENCIAS_DIR':str(self.root/'privado')});self.env.start();self.addCleanup(self.env.stop)
  self.write('configuracoes/evidencias-sessao.yaml',{'ativo':True})
  self.write('campanha.yaml',{'campanha':'isolada','limite':'destino não determina escolhas'})
  contract=self.repo/'evaluation/contratos-modulos/fixture.json';contract.parent.mkdir(parents=True,exist_ok=True);contract.write_text(json.dumps({'schema':1,'regra':'Oferta exige causa e canal legítimos.'},ensure_ascii=False))
  (self.repo/'AGENTS.md').write_text('O jogador controla as decisões de Ren.')
  self.write('estado/relacoes/index.yaml',{'schema_relacoes':2,'relacoes':{},'quantidade':0})
  self.write('estado/npcs/index.yaml',{'schema_npcs':2,'npcs':{},'quantidade':0})
  ciclo_cronica.session_close(self.repo)
  self.date='9 Eleasis, 1372 DR'
  self.write('narrador/mundo/agenda.yaml',{'schema_agenda_mundo':1,'natureza':'reservado','hora_amanhecer':'06:00','reavaliacoes':{},'agendamentos':[
   {'id':'SEGREDO_CAUSA_NAO_SELECIONADA','tipo':'expiracao','em':{'data':self.date,'hora':'18:30'},'motivo':'Fim da oportunidade reservada.'}]})
  self.write('narrador/mundo/estado.yaml',{'schema_estado_mundo':1,'natureza':'controle_reservado','processado_ate':{'data':self.date,'hora':'18:20'},'pendencias':[],'concluidas_recentes':[]})
  actors=agent_fixtures.AgentesValidationTest();actor_repo=actors._repo_minimo();self.addCleanup(actors.tearDown)
  shutil.copytree(actor_repo/'narrador/elenco',self.repo/'narrador/elenco',dirs_exist_ok=True)
  shutil.copytree(actor_repo/'fontes',self.repo/'fontes',dirs_exist_ok=True)
  self.write('estado/impedimento-fixture.yaml',{'canal':'ausente','presenca':'não confirmada','decisao':'sem encontro legítimo'})
  ciclo_cronica.session_start(self.repo)
 def write(self,path,value):fixtures.write_yaml(self.repo,path,value)
 def play(self):
  records=[{'type':'session_meta','payload':{'id':'controle-captura','cwd':'/isolado'}}]
  for n in (1,2):
   txid=f'tx-fonte-{n}';turn=f't{n}';text='Ren observa a ponte por dois minutos.' if n==1 else 'Ren observa a ponte.'
   prepared=cronica.prepare(self.repo,scene_id=txid,sidequest_signal=None,memory_participants=[])
   result=cronica.conclude(self.repo,prepared['ticket'],{'id':txid,'jogador':text,'narracao':'A água passa sob a ponte.','resumo':'Observou a ponte.','modo':'exploração','deltas':[
    {'alvo':'estado','op':'inc','caminho':'recursos.dinheiro.po','valor':2},
    {'alvo':'tempo','op':'instante','valor':{'data':self.date,'hora':'18:22'}}] if n==1 else []})
   records.extend([{'type':'event_msg','payload':{'type':'task_started','turn_id':turn}},
    {'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':text}]}},
    {'type':'response_item','payload':{'type':'function_call','name':'exec_command','call_id':txid,'arguments':json.dumps({'cmd':'poetry run cronica concluir --ticket fixture'}),'internal_chat_message_metadata_passthrough':{'turn_id':turn}}},
    {'type':'response_item','payload':{'type':'function_call_output','call_id':txid,'output':'Process exited with code 0\n'+json.dumps(result,ensure_ascii=False),'internal_chat_message_metadata_passthrough':{'turn_id':turn}}},
    {'type':'response_item','payload':{'type':'message','role':'assistant','content':[{'type':'output_text','text':'A água passa sob a ponte.\n'+result['rodape_canonico']}]}}])
  closed=ciclo_cronica.session_close(self.repo)
  # Porta pública publica o recibo da orquestração no mesmo output.
  import turn_and_session_orchestration as orchestration
  closed=orchestration.publish_session(closed,'encerrar')
  records.extend([{'type':'event_msg','payload':{'type':'task_started','turn_id':'encerramento'}},
   {'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':'[Encerre a sessão.]'}]}},
   {'type':'response_item','payload':{'type':'function_call_output','call_id':'fechar','output':json.dumps(closed,ensure_ascii=False)}},
   {'type':'response_item','payload':{'type':'message','role':'assistant','channel':'final','content':[{'type':'output_text','text':'Sessão encerrada.'}]}}])
  path=self.root/'rollout.jsonl';path.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in records)+'\n')
  cutoff=path.stat().st_size
  with path.open('a') as h:h.write(json.dumps({'type':'event_msg','payload':{'type':'task_started','turn_id':'manutencao'}})+'\n')
  archive=capture.destination(self.repo,4)
  bundle=frozen.prepare_input(path,session_id='004',session_evidence=archive)
  return path,archive,bundle,cutoff
 def test_encerramento_congela_causa_contrato_impedimento_deltas_e_corte(self):
  path,archive,bundle,cutoff=self.play();before=archive.read_bytes()
  pack=json.loads(before);capture.validate(pack)
  self.assertTrue(pack['inicio_preservado']);self.assertTrue(pack['encerrada'])
  files,gaps=capture.before(pack,'tx-fonte-2');self.assertFalse(gaps)
  self.assertEqual(yaml.safe_load(files['estado/estado-atual.yaml'])['recursos']['dinheiro']['po'],36)
  self.assertEqual(yaml.safe_load(files['estado/tempo.yaml'])['hora_aproximada'],'18:22')
  self.assertEqual(yaml.safe_load(files['estado/estado-atual.yaml'])['tempo']['hora_aproximada'],'18:22')
  self.assertIn('SEGREDO_CAUSA_NAO_SELECIONADA',files['narrador/mundo/agenda.yaml'])
  import agentes
  actor=yaml.safe_load(files['narrador/elenco/agentes/teste.yaml'])
  self.assertEqual(agentes.local_eligibility(actor),'sim')
  self.assertIn('Quando a ponte estiver livre',actor['plano_atual']['prazo_ou_oportunidade'])
  self.assertIn('ausente',files['estado/impedimento-fixture.yaml'])
  self.assertIn('destino',files['campanha.yaml'])
  self.assertIn('canal legítimos',files['evaluation/contratos-modulos/fixture.json'])
  self.assertEqual(bundle['fonte']['corte_bytes'],cutoff)
  self.assertEqual(archive.stat().st_mode&0o777,0o600);self.assertEqual(archive.parent.stat().st_mode&0o777,0o700)
  state=yaml.safe_load((self.repo/'estado/estado-atual.yaml').read_text());state['recursos']['dinheiro']['po']=999;self.write('estado/estado-atual.yaml',state)
  self.write('narrador/mundo/agenda.yaml',{'agendamentos':[]})
  self.assertEqual(capture.capture(self.repo,'encerrar')['estado'],'congelada')
  self.assertEqual(before,archive.read_bytes())
  request=review.prepare(path,bundle,criterion_ids=['narrative_delivery.narrative_density'])
  refs=[c['evaluation_ref'] for c in review.cases(request)['cases'] if c['turn_id'] in ('t1','t2')]
  request=review.prepare(path,bundle,criterion_ids=['narrative_delivery.narrative_density'],interaction_refs=refs)
  cases=review.cases(request)['cases'];second=next(c for c in cases if c['turn_id']=='t2')
  source=next(s for s in second['sources'] if s['kind']=='frozen_state' and 'estado/estado-atual.yaml' in s['text'])
  self.assertIn('36',source['text']);self.assertNotIn('999',source['text'])
  causal=next(s for s in second['sources'] if s['kind']=='frozen_state' and 'SEGREDO_CAUSA_NAO_SELECIONADA' in s['text'])
  self.assertEqual(causal['visibility'],'reservada')
  self.assertNotIn('SEGREDO_CAUSA_NAO_SELECIONADA',json.dumps(request['frames']))
  self.assertFalse(any(d['gravidade']=='bloqueio' for d in frozen.validate_input(bundle)))
 def test_ausencia_de_fonte_e_abstencao_especifica_publicam_sem_segredo(self):
  path,archive,bundle,_=self.play()
  request=review.prepare(path,bundle,criterion_ids=['sidequest_lifecycle.active_reassessment'])
  refs=[c['evaluation_ref'] for c in review.cases(request)['cases'] if c['turn_id'] in ('t1','t2')]
  request=review.prepare(path,bundle,criterion_ids=['sidequest_lifecycle.active_reassessment'],interaction_refs=refs)
  decisions=[]
  for frame in review.cases(request)['cases']:
   coverage=next(s for s in frame['sources'] if s['kind']=='causal_coverage')
   self.assertIn('estado/npcs/index.yaml',coverage['text'])
   decisions.append({'interaction_ref':frame['evaluation_ref'],'criterion_id':'sidequest_lifecycle.active_reassessment','state':'fontes_insuficientes','reason':'Estado de quests vivas ausente na fixture; não determinar se existia uma missão aceita exigindo reavaliação.','evidence':[{'locator':coverage['locator'],'quote':coverage['text']}],'guardrails':{},'diagnosis':None})
  submission={'request_id':request['request_id'],'reviewer':{'identity':'revisao-controlada-fontes','role':'revisor_poshoc','configuration':{'executor':'agente','mode':'replay_de_abstencao_explicita'}},'decisions':decisions}
  review.publish(path,bundle,request,submission,self.root/'publico')
  self.assertEqual(review.load(self.root/'publico/scorecard.json')['revisao_semantica']['insufficient_sources'],len(decisions))
  for p in (self.root/'publico').iterdir():
   if p.is_file():self.assertNotIn('SEGREDO_CAUSA_NAO_SELECIONADA',p.read_text())
 def test_turno_neutro_nao_captura_nem_varre_arquivo_causal(self):
  archive=capture.destination(self.repo,4);before=archive.read_bytes()
  with patch.object(capture,'capture',side_effect=AssertionError('captura no hot path')):
   prepared=cronica.prepare(self.repo,scene_id='neutro',sidequest_signal=None,memory_participants=[])
   result=cronica.conclude(self.repo,prepared['ticket'],{'id':'neutro','jogador':'Ren observa.','narracao':'A ponte permanece aberta.','resumo':'Observou.','modo':'exploração','deltas':[]})
  self.assertEqual(before,archive.read_bytes());self.assertLessEqual(len(yaml.safe_dump(prepared,allow_unicode=True).encode()),8192)
 def test_adulteracao_falha_e_captura_na_arvore_servida_e_recusada(self):
  _,archive,bundle,_=self.play();changed=deepcopy(bundle);changed['evidencias_sessao']['conteudo']['records'][0]['deltas']=[]
  self.assertTrue(any(d['codigo']=='evidencias_causais_invalidas' for d in frozen.validate_input(changed)))
  with patch.dict(os.environ,{'CRONICAS_EVIDENCIAS_DIR':str(self.repo/'evaluation/segredo')}),self.assertRaisesRegex(ValueError,'fora'):
   capture.capture(self.repo,'checkpoint')

 def test_abertura_interrompida_recupera_captura_e_destino_invalido_nao_abre(self):
  import consolidar
  ciclo_cronica.session_close(self.repo)
  state=(self.repo/'estado/estado-atual.yaml').read_bytes()
  with patch.dict(os.environ,{'CRONICAS_EVIDENCIAS_DIR':str(self.repo/'servido')}),self.assertRaises(ValueError):
   ciclo_cronica.session_start(self.repo)
  self.assertEqual(state,(self.repo/'estado/estado-atual.yaml').read_bytes())
  with self.assertRaises(consolidar.ConsolidationError):ciclo_cronica.session_start(self.repo,fail_after=2)
  result=ciclo_cronica.session_recover(self.repo)
  self.assertEqual(result['evidencias_sessao']['estado'],'capturada')
  pack=json.loads(capture.destination(self.repo,5).read_text());capture.validate(pack)
  self.assertTrue(pack['inicio_preservado'])
  with self.assertRaisesRegex(ValueError,'encerrada'):capture.validate_closed(pack)

 def test_mudanca_sem_ordem_e_recibo_final_ausente_nao_viram_certeza(self):
  path,archive,_,_=self.play();pack=json.loads(archive.read_text())
  pack['points'][0]['files'].pop('campanha.yaml')
  pack['points'][0]['id']=capture.digest({k:v for k,v in pack['points'][0].items() if k!='id'})
  pack['sha256']=capture.digest({k:v for k,v in pack.items() if k!='sha256'})
  _,gaps=capture.before(pack,'tx-fonte-2')
  self.assertIn('mudanca_sem_ordem_intermediaria:campanha.yaml',gaps)
  rows=[json.loads(r) for r in path.read_text().splitlines()]
  rows=[r for r in rows if r.get('payload',{}).get('channel')!='final']
  path.write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
  with self.assertRaisesRegex(ValueError,'resposta final'):capture.closure_cutoff(path,4)

 def test_vinculo_transacional_ignora_falha_e_saida_posterior(self):
  body=json.dumps({'exit_code':0,'output':json.dumps({'transacao':{'id':'tx-valida'}})})
  source={'kind':'native_tool_output','text':body}
  self.assertEqual(capture.transaction_id({'a':source}),'tx-valida')
  self.assertIsNone(capture.transaction_id({'a':dict(source,available_before_response=False)}))
  self.assertIsNone(capture.transaction_id({'a':dict(source,text=body.replace('"exit_code": 0','"exit_code": 1'))}))
