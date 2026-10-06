"""Executor isolado por CLI pública. Prosa é entrada; nunca decide seu mérito.

Variantes controlam omissões/prosa, não desativam gates. A revisão nova da
entrega é separada dos pareceres reaplicados por testes de regressão.
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import yaml

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/'ferramentas'
sys.path[:0]=[str(ROOT),str(TOOLS),str(ROOT/'tests')]
import test_evidencias_sessao as evidence_fixture
import test_memoria_duravel_integracao as memory_fixture
import test_locais as local_fixture
import test_recompensas as reward_fixture
from ferramentas import entrada_medicao, revisao_sessao

SCENARIO=ROOT/'tests/fixtures/episodio-integrado.json'

class Episode:
    def __init__(self, root, variant='correta'):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True);self.root.chmod(0o700)
        self.fixture=evidence_fixture.SessionEvidenceTest();self.fixture.setUp()
        self.repo=self.root/'repo'
        shutil.copytree(self.fixture.repo,self.repo)
        self.config=json.loads(SCENARIO.read_text());self.variant=variant
        self.mutation=self.config['variants'][variant]
        self.env={**os.environ,'CRONICAS_EVIDENCIAS_DIR':str(self.root/'reservado')}
        self.rows=[{'type':'session_meta','payload':{'id':'episodio-integrado-'+variant,'cwd':'/sandbox'}}]
        self.outputs={};self.calls=0;self.turn=None;self.steps=[]
        self.call('cronica.py',['sessao','encerrar'])
        donor=memory_fixture.DurableMemoryIntegrationTest();donor.setUp()
        try:
            for domain in ('estado/npcs','estado/relacoes','cenario/texturas'):
                shutil.copytree(donor.repo/domain,self.repo/domain,dirs_exist_ok=True)
        finally:donor.doCleanups()
        for plural in ('npcs','relacoes'):
            path=self.repo/f'estado/{plural}/index.yaml';index=yaml.safe_load(path.read_text())
            index[plural]['silva_fixture']['aliases']=['Silva']
            self.write(path.relative_to(self.repo),index)
        npc=yaml.safe_load((self.repo/'estado/npcs/silva_fixture.yaml').read_text())
        npc['npc'].update(identidade_relacional='ren',objetivo_atual='Conferir as rotas e obter o mapa antes de fechar o registro.',presenca_confirmada={'local':'abrigo_fixture','ponto':'mesa','fonte':'fontes/episodio.md'})
        npc['npc']['medidores'].update(afinidade=8,confianca=8)
        self.write('estado/npcs/silva_fixture.yaml',npc)
        registry=local_fixture.LocalRegistrySyntheticTest();registry.repo=self.repo
        registry._write_registry({'abrigo_fixture':{'nome':'Abrigo da fixture','aliases':['abrigo']}})
        registry._write_ecology(['abrigo_fixture'])
        reward_fixture.RecompensasSinteticasTest._copy_base(self.repo)
        # Baralhos reais com estado inicial controlado: próxima ficha é rotina.
        # Não há patch do produtor nem retirada de gatilho no retry.
        import ecologia_local
        ecology=self.read('cenario/locais/ecologia.yaml')
        ecology['perfis']['abrigo_fixture']=deepcopy(ecologia_local.load_index(ROOT)['perfis']['galeria_dos_escribas'])
        self.write('cenario/locais/ecologia.yaml',ecology)
        for domain in ('microeventos-locais','incidentes'):
            dest=self.repo/f'narrador/mundo/{domain}';dest.mkdir(parents=True,exist_ok=True)
            shutil.copy2(ROOT/f'narrador/mundo/{domain}/index.yaml',dest/'index.yaml')
        micro=self.read('narrador/mundo/microeventos-locais/index.yaml')
        incidents=self.read('narrador/mundo/incidentes/index.yaml')
        def deck(tokens):
            routine=next(t['id'] for t in tokens if t['resultado']=='rotina')
            return {'ocorrencia':{'ciclo':1,'restantes':[routine]},'cartas':{'ciclo':0,'restantes':[],'assinatura_pool':None}}
        self.write('narrador/mundo/microeventos-locais/estado.yaml',{'schema_estado_microeventos_locais':1,'natureza':'controle_reservado','locais':{'abrigo_fixture':deck(micro['ocorrencia']['fichas'])},'historico_recente':[]})
        self.write('narrador/mundo/incidentes/estado.yaml',{'schema_estado_incidentes_mundo':1,'natureza':'controle_reservado','cidade':'ravens_bluff','global':deck(incidents['frequencia']['global']['fichas']),'locais':{'abrigo_fixture':deck(incidents['frequencia']['local']['fichas'])},'historico_recente':[]})
        self.date='11 Eleasis, 1372 DR'
        state=self.read('estado/estado-atual.yaml');state['tempo'].update(data_exata=self.date,hora_aproximada='11:35',clima='chuva miúda',periodo_do_dia='manhã')
        state['localizacao'].update(area='estrada',ponto_exato='diante do abrigo');state['localizacao'].pop('local_id',None)
        state.pop('estado_narrativo',None);self.write('estado/estado-atual.yaml',state)
        time=self.read('estado/tempo.yaml');time.update(data_atual=self.date,hora_aproximada='11:35',clima='chuva miúda',periodo_do_dia='manhã');self.write('estado/tempo.yaml',time)
        self.write('narrador/mundo/agenda.yaml',{'schema_agenda_mundo':1,'natureza':'reservado','hora_amanhecer':'06:00','reavaliacoes':{},'agendamentos':[{'id':'prazo_mapa_fixture','tipo':'expiracao','em':{'data':self.date,'hora':'11:50'},'motivo':'Limite anunciado para conferir a entrega; não é evento canônico nem cancela o compromisso.'}]})
        self.write('narrador/mundo/estado.yaml',{'schema_estado_mundo':1,'natureza':'controle_reservado','processado_ate':{'data':self.date,'hora':'11:35'},'pendencias':[],'concluidas_recentes':[]})
        self.write('narrador/tramas/segredo-episodio.yaml',{'segredo':'SEGREDO_RESERVADO_DO_EPISODIO','descoberta':'não ocorreu'})
        self.write('cenario/locais/presenca-episodio.yaml',{'silva_fixture':{'local':'abrigo_fixture','ponto':'mesa','fonte':'fontes/episodio.md'}})
        (self.repo/'fontes/episodio.md').write_text('Silva está à mesa no abrigo. Ela precisa conferir as rotas. Chove miúdo. O mapa só será entregue se Ren o fizer.\n')
        self.call('cronica.py',['sessao','iniciar'])

    def close(self):self.fixture.doCleanups()
    def read(self,rel):return yaml.safe_load((self.repo/rel).read_text())
    def write(self,rel,value):evidence_fixture.fixtures.write_yaml(self.repo,rel,value)
    def begin(self,step):
        self.turn=step['id'];self.current=step;self.rows.extend([
          {'type':'event_msg','payload':{'type':'task_started','turn_id':self.turn}},
          {'type':'response_item','payload':{'type':'message','role':'user','content':[{'type':'input_text','text':step['jogador']}]}}])
    def call(self,tool,args,body=None,check=True):
        cmd=[sys.executable,str(TOOLS/tool),'--repo',str(self.repo),*args]
        completed=subprocess.run(cmd,input=json.dumps(body,ensure_ascii=False) if body is not None else None,capture_output=True,text=True,env=self.env)
        self.calls+=1;cid=f'cli-{self.calls}'
        if self.turn:
            meta={'turn_id':self.turn}
            self.rows.extend([
              {'type':'response_item','payload':{'type':'function_call','name':'exec_command','call_id':cid,'arguments':json.dumps({'cmd':shlex.join(cmd), 'stdin': json.dumps(body,ensure_ascii=False) if body is not None else None}),'internal_chat_message_metadata_passthrough':meta}},
              {'type':'response_item','payload':{'type':'function_call_output','call_id':cid,'output':f'Process exited with code {completed.returncode}\n'+completed.stdout+completed.stderr,'internal_chat_message_metadata_passthrough':meta}}])
        if check and completed.returncode:raise RuntimeError(f'{tool} {args[:2]}: {completed.stdout}{completed.stderr}')
        result=yaml.safe_load(completed.stdout) if completed.stdout else None
        self.outputs.setdefault(self.turn or 'lifecycle',[]).append({'tool':tool,'args':args,'exit_code':completed.returncode,'stdout_bytes':len(completed.stdout.encode('utf-8')),'result':result})
        return result
    def prepare(self,step,extra=()):
        return self.call('cronica.py',['preparar','--cena-id',step['id'],'--sem-oportunidade-sidequest',*extra])
    def conclude(self,step,prepared,deltas=None,memory=None):
        prosa=self.mutation.get('prosa',{}).get(step['id'],step['narracao'])
        spatial=prepared.get('permanencia_espacial') or {}
        card=(spatial.get('microevento_local') or {}).get('carta') or {}
        spatial_evidence=None
        if spatial.get('exige_decisao_conclusao'):
            if card.get('id')!='carga_marca_confusa':raise ValueError('Candidato novo exige prosa e decisão próprias: '+str(card.get('id')))
            spatial_evidence='Silva confere uma marca ambígua numa carga ao lado do registro e corrige a contagem da folha, sem pedir que Ren resolva o trabalho por ela.'
            prosa=spatial_evidence+' '+prosa
        tx={'id':'episodio-'+step['id'],'jogador':step['jogador'],'narracao':prosa,'resumo':'Episódio controlado: '+step['id'],'modo':'interação','deltas':deltas or []}
        if memory is not None:tx['memoria']=memory
        if spatial_evidence:tx['permanencia_espacial']={'avaliacao_id':spatial['avaliacao_id'],'resultado':'resolvida','evidencia_literal':spatial_evidence}
        initiative=prepared.get('iniciativa_elenco') or {}
        if initiative.get('selecionada'):
            excerpt='Ainda estou esperando o mapa combinado.' if step['id'] in ('espera_limite','continuacao') else 'Eu preciso fechar as rotas antes de sair; você consegue trazer o mapa antes das onze e cinquenta?'
            if excerpt not in prosa:raise ValueError('A abertura requerida precisa prosa própria, não recibo automático')
            tx['iniciativa_elenco']={'decisao_id':initiative['selecionada'],'resultado':'apresentada','evidencia_literal':excerpt}
        result=self.call('cronica.py',['concluir','--ticket',prepared['ticket']],tx)
        self.rows.append({'type':'response_item','payload':{'type':'message','role':'assistant','channel':'final','content':[{'type':'output_text','text':prosa+'\n'+result['rodape_canonico']}]}})
        self.steps.append({'id':step['id'],'jogador':step['jogador'],'narracao':prosa,'prepare':prepared,'conclude':result,'transaction':tx})
        return result
    def run(self):
        for step in self.config['steps']:
            self.begin(step);sid=step['id'];extra=['--participante','Silva']
            if sid=='prospecto':extra+=['--interlocutor','silva_fixture']
            elif sid=='entrada':extra+=['--local','abrigo','--acao','entrar','--tier','1','--periculosidade','baixa']
            elif sid in ('conversa','nova_interacao','retomada_fria'):extra+=['--interlocutor','silva_fixture']
            elif sid in ('espera_limite','continuacao'):extra=['--permanencia-local','--interlocutor','silva_fixture']
            if sid in ('espera_limite','continuacao'):
                frontier=self.call('endpoints.py',['fronteira','--data',self.date,'--hora','12:14'])
                self.frontier=frontier
            if sid=='retomada_fria':self.call('cronica.py',['sessao','status'])
            prepared=self.prepare(step,extra)
            if prepared.get('fase')=='bloqueada_pendencias_mundo':
                batch=self.call('world_boundary_resolution.py',['preparar'])
                decisions=[{'id':item['id'],'token':item['token'],'nota':'Expiração do prazo informado avaliada; o compromisso continua pendente e nenhuma entrega, cancelamento ou novo evento canônico ocorreu.'} for item in batch['itens'] if item.get('sem_mudanca_permitido') is True]
                if len(decisions)!=len(batch['itens']):raise RuntimeError('Pendência exige resolução específica; não converter em no-op')
                self.call('world_boundary_resolution.py',['aplicar'],{'lote_id':batch['lote_id'],'sem_mudanca':decisions})
                prepared=self.prepare(step,extra)
            if prepared.get('proximo_passo',{}).get('acao')!='narrar_e_concluir':raise RuntimeError(prepared)
            # Aprofundar só a lacuna efetivamente necessária, pelo contrato
            # L1/L2 existente. Não rodar avaliador nem consulta preventiva.
            items=(prepared.get('memoria_cena') or {}).get('itens') or {}
            commitments=items.get('@compromissos') or {}
            if commitments.get('memoria_relevante',{}).get('aprofundamento_necessario'):
                self.call('contexto.py',['status'])
            actor=items.get('silva_fixture') or {}
            if sid in ('espera_limite','continuacao') and 'medidores' not in actor:
                self.call('contexto.py',['npc','Silva','--campo','/medidores'])
            deltas=[];memory=None
            if sid=='entrada':
                deltas=[{'alvo':'estado','op':'set','caminho':'localizacao.area','valor':'abrigo_fixture'}, {'alvo':'estado','op':'set','caminho':'localizacao.ponto_exato','valor':'mesa'}, {'alvo':'estado','op':'set','caminho':'estado_narrativo.elenco_cena','valor':{'versao':1,'cena_id':sid,'local':{'area':'abrigo_fixture','ponto_exato':'mesa'},'participantes':['silva_fixture']}}]
            if sid=='promessa' and not self.mutation.get('omitir_memoria_promessa'):
                memory={'versao':1,'fatos':[{'id':'mapa','tipo':'promessa','participantes':['ren','silva_fixture'],'evidencia':{'campo':'narracao','trecho':'Ren promete entregar o mapa a Silva antes das onze e cinquenta.'},'operacao':'registrar','compromisso':{'tipo':'compromisso','resumo':'Entregar o mapa a Silva antes das onze e cinquenta.','janela':{'fim':{'data':self.date,'hora':'11:50'}}}}]}
            if sid in ('espera_limite','continuacao'):
                hour=self.frontier['disponibilidade']['janela_consultada']['limite_narravel']['hora']
                deltas=[{'alvo':'tempo','op':'instante','valor':{'data':self.date,'hora':hour}}]
            self.conclude(step,prepared,deltas,memory)
            if sid in ('nova_interacao','espera_limite','continuacao'):
                self.begin({'id':'checkpoint-'+sid,'jogador':'[Checkpoint de cena.]'})
                self.call('cronica.py',['sessao','checkpoint'])
                self.rows.append({'type':'response_item','payload':{'type':'message','role':'assistant','channel':'final','content':[{'type':'output_text','text':'Checkpoint controlado concluído.'}]}})
        self.begin({'id':'encerramento','jogador':'[Encerre a sessão.]'})
        self.call('cronica.py',['sessao','encerrar'])
        self.rows.append({'type':'response_item','payload':{'type':'message','role':'assistant','channel':'final','content':[{'type':'output_text','text':'Sessão controlada encerrada.'}]}})
        rollout=self.root/'rollout.jsonl';rollout.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in self.rows)+'\n')
        with rollout.open('a') as h:h.write(json.dumps({'type':'event_msg','payload':{'type':'task_started','turn_id':'manutencao'}})+'\n')
        import evidencias_sessao
        import hashlib
        archive=Path(self.env['CRONICAS_EVIDENCIAS_DIR'])/hashlib.sha256(str(self.repo.resolve()).encode()).hexdigest()[:16]/'005.json'
        bundle=entrada_medicao.prepare_input(rollout,session_id='005',session_evidence=archive)
        (self.root/'entrada.json').write_text(json.dumps(bundle,ensure_ascii=False))
        (self.root/'observacoes.json').write_text(json.dumps({'steps':self.steps,'outputs':self.outputs},ensure_ascii=False))
        for path in (rollout,self.root/'entrada.json',self.root/'observacoes.json'):path.chmod(0o600)
        return rollout,bundle
