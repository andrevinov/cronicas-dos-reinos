#!/usr/bin/env python3
"""Medidor explícito das frentes de pressão de Ravens Bluff na Parte 1.

Não é relógio nem direção canônica: nenhuma frente sobe porque o tempo passou.
Mudanças exigem um fato canônico e evidência literal em arquivo do repositório.
Ren não recebe automaticamente conhecimento da causa ou sequer da mudança.
"""
from __future__ import annotations
import argparse, os, tempfile
from pathlib import Path
from typing import Any
import yaml

PROFILE=Path('narrador/arcos/parte_1/pressao-ravens-bluff.yaml')
STATE=Path('narrador/arcos/parte_1/estado-pressao-ravens-bluff.yaml')
MAX_HISTORY=24
BANNED_EVIDENCE_PREFIX=Path('narrador/arcos')

class PressureError(ValueError): pass

def load(path):
    try:return yaml.safe_load(path.read_text(encoding='utf-8'))
    except (FileNotFoundError,yaml.YAMLError) as e: raise PressureError(str(e)) from e

def mp(v,label):
    if not isinstance(v,dict): raise PressureError(f'{label} deve ser mapa')
    return v

def ls(v,label):
    if not isinstance(v,list): raise PressureError(f'{label} deve ser lista')
    return v

def txt(v,label):
    if not isinstance(v,str) or not v.strip(): raise PressureError(f'{label} deve ser texto não vazio')
    return v.strip()

def norm(v): return ' '.join(str(v).split())
def rel(v,label):
    p=Path(txt(v,label))
    if p.is_absolute() or '..' in p.parts: raise PressureError(f'{label} deve ficar no repositório')
    return p

def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False) as h:
        yaml.safe_dump(data,h,allow_unicode=True,sort_keys=False); h.flush(); os.fsync(h.fileno()); tmp=Path(h.name)
    os.replace(tmp,path)

def load_profile(repo):
    d=mp(load(repo/PROFILE),str(PROFILE))
    if d.get('schema_pressao_ravens_bluff')!=1 or d.get('natureza')!='reservado': raise PressureError('perfil de pressão inválido')
    rules=mp(d.get('regras'),'regras'); lo=rules.get('nivel_minimo'); hi=rules.get('nivel_maximo')
    if lo!=0 or hi!=4 or rules.get('mudanca_maxima_por_registro')!=1 or rules.get('avanco_automatico') is not False: raise PressureError('regras de pressão divergiram do contrato')
    fronts=mp(d.get('frentes'),'frentes')
    if not fronts: raise PressureError('frentes ausentes')
    for fid,raw in fronts.items():
        f=mp(raw,f'frentes.{fid}'); txt(f.get('nome'),f'{fid}.nome'); lines=ls(f.get('linhas_relacionadas'),f'{fid}.linhas_relacionadas')
        if not lines: raise PressureError(f'{fid}: precisa de linha relacionada')
        levels=ls(f.get('niveis'),f'{fid}.niveis')
        if [x.get('nivel') for x in levels]!=list(range(lo,hi+1)): raise PressureError(f'{fid}: níveis devem formar 0..4')
        for item in levels:
            txt(item.get('titulo'),f'{fid}.titulo'); sig=ls(item.get('sinais'),f'{fid}.sinais')
            if not sig or any(not isinstance(x,str) or not x.strip() for x in sig): raise PressureError(f'{fid}: sinais inválidos')
    return d

def load_state(repo,profile=None):
    profile=profile or load_profile(repo); d=mp(load(repo/STATE),str(STATE))
    if d.get('schema_estado_pressao_ravens_bluff')!=1 or d.get('natureza')!='controle_reservado': raise PressureError('estado de pressão inválido')
    fs=mp(d.get('frentes'),'estado.frentes')
    if set(fs)!=set(profile['frentes']): raise PressureError('estado de pressão diverge do perfil')
    for fid,item in fs.items():
        item=mp(item,f'estado.{fid}'); level=item.get('nivel')
        if not isinstance(level,int) or isinstance(level,bool) or not 0<=level<=4: raise PressureError(f'{fid}: nível inválido')
        hist=ls(item.get('historico_recente'),f'{fid}.historico_recente')
        if len(hist)>MAX_HISTORY: raise PressureError(f'{fid}: histórico excedeu teto')
    return d

def validate(repo):
    try:p=load_profile(repo); s=load_state(repo,p); return {'ok':True,'frentes':len(p['frentes']),'erros':[],'fontes_lidas':[str(PROFILE),str(STATE)]}
    except PressureError as e:return {'ok':False,'frentes':0,'erros':[str(e)],'fontes_lidas':[]}
def status(repo):
    p=load_profile(repo); s=load_state(repo,p); rows=[]
    for fid,meta in p['frentes'].items():
        lv=s['frentes'][fid]['nivel']; cur=meta['niveis'][lv]; nxt=meta['niveis'][lv+1] if lv<4 else None
        rows.append({'id':fid,'nome':meta['nome'],'nivel':lv,'titulo':cur['titulo'],'sinais_atuais':cur['sinais'],'proximo_nivel':({'nivel':nxt['nivel'],'titulo':nxt['titulo']} if nxt else None)})
    return {'arco':p['arco'],'frentes':rows,'regra':'níveis registram pressão canônica; não concedem descoberta da causa a Ren','fontes_lidas':[str(PROFILE),str(STATE)]}
def adjust(repo,front,delta,source,evidence,origin,note):
    if delta not in {-1,1}: raise PressureError('delta deve ser -1 ou 1')
    p=load_profile(repo); s=load_state(repo,p)
    if front not in p['frentes']: raise PressureError(f'frente inexistente: {front}')
    src=rel(source,'fonte')
    if src == BANNED_EVIDENCE_PREFIX or BANNED_EVIDENCE_PREFIX in src.parents:
        raise PressureError('arquivo de planejamento do arco não pode provar sua própria pressão')
    path=repo/src
    if not path.is_file(): raise PressureError(f'fonte canônica inexistente: {src}')
    ev=txt(evidence,'evidencia')
    if norm(ev) not in norm(path.read_text(encoding='utf-8')): raise PressureError('evidência literal não localizada na fonte')
    cur=s['frentes'][front]['nivel']; target=cur+delta
    if not 0<=target<=4: raise PressureError('mudança sairia do intervalo 0..4')
    item={'de':cur,'para':target,'fonte':src.as_posix(),'evidencia':ev,'origem':txt(origin,'origem'),'nota':txt(note,'nota')}
    s['frentes'][front]['nivel']=target; s['frentes'][front]['historico_recente'].append(item); s['frentes'][front]['historico_recente']=s['frentes'][front]['historico_recente'][-MAX_HISTORY:]
    atomic(repo/STATE,s)
    return {'ok':True,'frente':front,'de':cur,'para':target,'registro':item,'regra':'mudança de pressão não revela automaticamente causa a Ren','fontes_lidas':[str(PROFILE),str(STATE),src.as_posix()]}
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--repo',type=Path,default=Path.cwd()); sub=p.add_subparsers(dest='cmd',required=True)
    sub.add_parser('validar'); sub.add_parser('status'); a=sub.add_parser('ajustar'); a.add_argument('frente'); a.add_argument('--delta',type=int,choices=[-1,1],required=True); a.add_argument('--fonte',required=True); a.add_argument('--evidencia',required=True); a.add_argument('--origem',required=True); a.add_argument('--nota',required=True)
    x=p.parse_args(argv); repo=x.repo.resolve()
    try:r=validate(repo) if x.cmd=='validar' else status(repo) if x.cmd=='status' else adjust(repo,x.frente,x.delta,x.fonte,x.evidencia,x.origem,x.nota); print(yaml.safe_dump(r,allow_unicode=True,sort_keys=False),end=''); return 0 if r.get('ok',True) else 1
    except PressureError as e: print(f'erro: {e}',file=__import__('sys').stderr); return 1
if __name__=='__main__': raise SystemExit(main())
