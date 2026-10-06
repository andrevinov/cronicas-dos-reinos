"""Arquivo reservado no lifecycle; recuperação pós-hoc sem consultar save futuro."""
from __future__ import annotations
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import yaml

VERSION = '1.0.0'
# Domínios causais, contratos e fontes autorizadas; não inclui livros, histórico
# geral, transcrições ou arquivos de sistema. Scan somente no lifecycle.
DOMAINS = ('estado', 'narrador/mundo', 'narrador/elenco', 'narrador/tramas',
           'narrador/indices', 'narrador/sidequest-reacoes',
           'cenario', 'regras', 'fontes', 'personagens/jogador', 'evaluation/contratos-modulos',
           'docs/agente', 'narracao/principios', 'narracao/operacao')
FILES = ('campanha.yaml', 'AGENTS.md', 'evaluation/catalogo-modulos-v2.json',
         'evaluation/module-releases.json', 'evaluation/contrato-medicao.json')
FAMILIES = {
 'context_and_memory': ('AGENTS.md','estado/npcs/index.yaml','estado/relacoes/index.yaml'),
 'turn_and_session_orchestration': ('estado/estado-atual.yaml','estado/tempo.yaml'),
 'narrative_delivery': ('AGENTS.md','narracao/principios/guia-de-narrativa.md'),
 'rules_and_character_state': ('estado/tempo.yaml','personagens/jogador/ficha.yaml'),
 'sidequest_authoring': ('narrador/tramas/sidequests/vivas/estado.yaml','narrador/tramas/recompensas/envelope-sidequest.yaml'),
 'sidequest_lifecycle': ('narrador/tramas/sidequests/vivas/estado.yaml',),
 'canonical_quest_integration': ('campanha.yaml','narrador/tramas/direcoes/index.yaml','narrador/tramas/direcoes/estado.yaml'),
 'npc_continuity_and_social_behavior': ('estado/npcs/index.yaml','estado/relacoes/index.yaml'),
 'scene_world_projection': ('estado/estado-atual.yaml','estado/tempo.yaml','narrador/mundo/condicoes-persistentes.yaml'),
 'world_boundary_resolution': ('estado/tempo.yaml','narrador/mundo/estado.yaml','narrador/mundo/agenda.yaml'),
 'causal_narrative_routing': ('narrador/mundo/agenda.yaml','narrador/tramas/direcoes/index.yaml'),
 'adversarial_operations': ('narrador/mundo/estado.yaml','narrador/sidequest-reacoes/estado.yaml'),
}

def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def archive(repo):
    base = Path(os.environ.get('CRONICAS_EVIDENCIAS_DIR', str(Path.home()/'.local/state/cronicas-evidencias'))).resolve()
    if base.is_relative_to(Path(repo).resolve()):
        raise ValueError('Evidências reservadas precisam ficar fora do repositório servido')
    return base / hashlib.sha256(str(Path(repo).resolve()).encode()).hexdigest()[:16]

def session(repo):
    return int(yaml.safe_load((Path(repo)/'estado/estado-atual.yaml').read_text())['campanha']['sessao_atual'])

def destination(repo, number):
    return archive(repo)/f'{number:03d}.json'

def prepare_storage(repo):
    """Falha antes da abertura se o arquivo reservado não puder ser escrito."""
    config=Path(repo)/'configuracoes/evidencias-sessao.yaml'
    if not config.is_file() or not (yaml.safe_load(config.read_text()) or {}).get('ativo'):return
    directory=archive(repo)
    directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    directory.chmod(0o700)
    fd,name=tempfile.mkstemp(dir=directory)
    os.close(fd);os.unlink(name)

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.parent.chmod(0o700)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as h:
            json.dump(value,h,ensure_ascii=False,sort_keys=True);h.write('\n')
        os.chmod(name,0o600)
        os.replace(name,path)
    finally:
        if os.path.exists(name): os.unlink(name)

def ledger(repo, number, known):
    path = Path(repo)/f'sessoes/{number:03d}/consolidacoes.jsonl'
    result=[]
    if path.is_file():
        for line in path.read_text().splitlines():
            if line.strip():
                item=json.loads(line)
                # Consolidações encapsulam transações em alguns schemas.
                result.extend(item.get('transacoes', []) if 'transacoes' in item else [item.get('id')])
    by_id={r['id']:r for r in known}
    pending=Path(repo)/'runtime/eventos-pendentes.jsonl'
    if pending.is_file():
        for line in pending.read_text().splitlines():
            if line.strip():
                record=json.loads(line)
                if record.get('sessao')==number:by_id[record['id']]=record
    ordered=list(dict.fromkeys([*result,*by_id]))
    return [by_id.get(r,{'id':r,'deltas':[],'cobertura_deltas':'ausente'}) for r in ordered],len(result)

def capture(repo, phase):
    """Só lifecycle. Nunca imprime arquivos, caminho reservado ou conteúdo."""
    repo=Path(repo)
    config=repo/'configuracoes/evidencias-sessao.yaml'
    if not config.is_file() or not (yaml.safe_load(config.read_text()) or {}).get('ativo'):
        return {'schema':1,'estado':'nao_configurada'}
    number=session(repo); path=destination(repo,number)
    pack=json.loads(path.read_text()) if path.is_file() else {
        'schema':1,'version':VERSION,'sessao':f'{number:03d}','inicio_preservado':phase=='iniciar',
        'objects':{},'points':[],'records':[],'families':FAMILIES}
    if path.is_file():validate(pack)
    if pack.get('encerrada'):
        # Retry posterior não captura manutenção como se fosse parte do jogo.
        return {'schema':1,'estado':'congelada','snapshot_id':pack['points'][-1]['id']}
    paths={repo/rel for rel in FILES if (repo/rel).is_file()}
    for domain in DOMAINS:
        paths.update(p for p in (repo/domain).rglob('*') if p.is_file() and p.suffix in {'.yaml','.json','.md'})
    sources={}
    for p in sorted(paths):
        if not p.resolve().is_relative_to(repo.resolve()):
            raise ValueError('Fonte causal aponta para fora do repositório')
        body=p.read_text(encoding='utf-8'); sha=hashlib.sha256(body.encode()).hexdigest()
        sources[p.relative_to(repo).as_posix()]=sha; pack['objects'][sha]=body
    records,cursor=ledger(repo,number,pack['records'])
    point={'phase':phase,'cursor':cursor,'instante':yaml.safe_load((repo/'estado/tempo.yaml').read_text()),'files':sources}
    point['id']=digest(point)
    if not any(p['id']==point['id'] for p in pack['points']):pack['points'].append(point)
    pack['records']=records;pack['encerrada']=phase=='encerrar'
    pack['sha256']=digest({k:v for k,v in pack.items() if k!='sha256'})
    write(path,pack)
    return {'schema':1,'estado':'congelada' if pack['encerrada'] else 'capturada','snapshot_id':point['id']}

def validate(pack):
    if pack.get('schema')!=1 or pack.get('sha256')!=digest({k:v for k,v in pack.items() if k!='sha256'}):
        raise ValueError('Pacote causal alterado ou schema inválido')
    for sha,body in pack['objects'].items():
        if hashlib.sha256(body.encode()).hexdigest()!=sha:raise ValueError('Fonte causal alterada')
    for point in pack['points']:
        if point['id']!=digest({k:v for k,v in point.items() if k!='id'}):raise ValueError('Instante causal alterado')
        if set(point['files'].values())-pack['objects'].keys():raise ValueError('Conteúdo causal ausente')

def validate_closed(pack):
    validate(pack)
    if not pack.get('encerrada') or not pack['points'] or pack['points'][-1]['phase']!='encerrar':
        raise ValueError('Captura causal ainda não foi encerrada')

def before(pack, transaction_id):
    """Reconstrói somente alvos suportados; lacuna não vira estado presumido."""
    import transacoes
    import tempo_transacional
    import consolidar
    validate(pack)
    records=pack['records']; indices=[i for i,r in enumerate(records) if r.get('id')==transaction_id]
    if len(indices)!=1: return {},['transacao_sem_vinculo_univoco']
    idx=indices[0]
    points=[p for p in pack['points'] if p['cursor']<=idx and p['phase'] in {'iniciar','checkpoint'}]
    if not points:return {},['instante_inicial_ausente']
    point=max(enumerate(points),key=lambda pair:(pair[1]['cursor'],pair[0]))[1]
    files={rel:pack['objects'][sha] for rel,sha in point['files'].items()}; gaps=[]
    for record in records[point['cursor']:idx]:
        if record.get('cobertura_deltas')=='ausente':gaps.append('deltas_ausentes:'+record['id'])
        touched={'estado':set(),'tempo':set(),'ficha':set()}
        for delta in tempo_transacional.expand_atomic_deltas(record.get('deltas',[])):
            target=delta['alvo']; rel={'estado':'estado/estado-atual.yaml','tempo':'estado/tempo.yaml','ficha':'personagens/jogador/ficha.yaml'}.get(target)
            key=None
            if ':' in target and target.split(':')[0] in {'npc','relacao'}:
                kind,actor=target.split(':',1); plural='npcs' if kind=='npc' else 'relacoes'
                index=yaml.safe_load(files.get(f'estado/{plural}/index.yaml','{}')) or {}
                rel=(index.get(plural,{}).get(actor,{}) or {}).get('arquivo');key=kind
            if rel is None or rel not in files or delta['op']=='registrar':
                gaps.append(f'alvo_nao_reconstruido:{target}');continue
            doc=yaml.safe_load(files[rel]); payload=doc[key] if key else doc
            try:transacoes.apply_delta(payload,delta)
            except (transacoes.TransactionError,ValueError,KeyError,TypeError) as exc:
                gaps.append(f'delta_nao_reconstruido:{target}:{type(exc).__name__}');continue
            files[rel]=yaml.safe_dump(doc,allow_unicode=True,sort_keys=False)
            if target in touched:touched[target].add(delta.get('caminho'))
        main=('estado/estado-atual.yaml','estado/tempo.yaml','personagens/jogador/ficha.yaml')
        if all(rel in files for rel in main):
            docs=[yaml.safe_load(files[rel]) for rel in main]
            consolidar.sync_mirrors(*docs,touched['estado'],touched['tempo'],touched['ficha'])
            for rel,doc in zip(main,docs):files[rel]=yaml.safe_dump(doc,allow_unicode=True,sort_keys=False)
    if not pack['inicio_preservado']:gaps.append('captura_iniciada_depois_da_abertura')
    # Mudança direta não tem ordem por interação demonstrada. Não atribuí-la
    # retroativamente a todas as respostas do intervalo.
    for boundary in pack['points']:
        if boundary['phase']=='antes_checkpoint' and boundary['cursor']==point['cursor']:
            changed={p for p in set(point['files'])|set(boundary['files'])
                     if point['files'].get(p)!=boundary['files'].get(p)}
            gaps.extend('mudanca_sem_ordem_intermediaria:'+p for p in sorted(changed))
    return files,sorted(set(gaps))

def transaction_id(sources):
    ids=set()
    def walk(v):
        if isinstance(v,dict):
            if v.get('exit_code') not in (None,0):return
            tx=v.get('transacao')
            if isinstance(tx,dict) and isinstance(tx.get('id'),str):ids.add(tx['id'])
            for child in v.values():walk(child)
        elif isinstance(v,list):
            for child in v:walk(child)
        elif isinstance(v,str):
            body=v.split('Output:\n')[-1]
            if body.startswith('Process exited with code 0'):body=body.split('\n',1)[-1]
            elif body.startswith('Process exited with code'):return
            try:
                parsed=yaml.safe_load(body)
                if isinstance(parsed,(dict,list)):walk(parsed)
            except yaml.YAMLError:pass
    for source in sources.values():
        if source['kind'] not in {'output','native_tool_output'} or source.get('available_before_response') is False:continue
        walk(source['text'])
    return next(iter(ids)) if len(ids)==1 else None

def add_sources(pack, sources, source):
    """Fontes de revisão, não uma alegação de entrega ao narrador."""
    tx=transaction_id(sources); files,gaps=before(pack,tx)
    coverage={'version':VERSION,'inicio_preservado':pack['inicio_preservado'],'transaction_id':tx,
              'lacunas_reconstrucao':gaps,'families':{family:{'required':list(paths),'missing':[p for p in paths if p not in files]}
              for family,paths in pack['families'].items()},'entregue_ao_narrador':False}
    source('causal_coverage',json.dumps(coverage,ensure_ascii=False,sort_keys=True),'reservada')
    for rel,body in files.items():
        source('frozen_state',json.dumps({'arquivo':rel,'conteudo':body,'reconstrucao':'parcial' if gaps else 'por_snapshot_e_deltas'},ensure_ascii=False,sort_keys=True),
               'reservada','causal/'+hashlib.sha256(rel.encode()).hexdigest()[:24])

def closure_cutoff(path, number):
    """Recibo estrutural de encerramento + resposta final; nunca por frase solta."""
    closed=False;offset=0
    def receipt(value):
        if isinstance(value,dict):
            if 'exit_code' in value and value['exit_code'] not in (None,0):return False
            if (value.get('schema_turn_and_session_orchestration')==1 and value.get('operacao')=='encerrar'
                    and value.get('estado')=='encerrado' and str(value.get('sessao')).zfill(3)==str(number).zfill(3)):
                return True
            return any(receipt(v) for v in value.values())
        if isinstance(value,list):return any(receipt(v) for v in value)
        if isinstance(value,str):
            body=value.split('Output:\n')[-1]
            if body.startswith('Process exited with code 0'):body=body.split('\n',1)[-1]
            elif body.startswith('Process exited with code'):return False
            try:
                parsed=yaml.safe_load(body)
                return receipt(parsed) if isinstance(parsed,(dict,list)) else False
            except yaml.YAMLError:return False
        return False
    for raw in Path(path).read_bytes().splitlines(keepends=True):
        offset+=len(raw)
        item=json.loads(raw);payload=item.get('payload',{})
        if payload.get('type')=='function_call_output' and receipt(payload.get('output')):closed=True
        if closed and payload.get('type')=='task_started':
            raise ValueError('Novo turno antes da resposta final de encerramento; declarar o corte explicitamente')
        if closed and payload.get('type')=='message' and payload.get('role')=='assistant' and payload.get('channel','final')=='final':
            return offset
    raise ValueError('Recibo de encerramento e resposta final não encontrados; não congelar manutenção como sessão')
