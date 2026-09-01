#!/usr/bin/env python3
"""Valida a autonomia estratégica dos Juppongatana habilitados no arco corrente.

Autonomia descreve impulso e escalada possível, nunca uma ação já escolhida.
O perfil vive no fragmento do próprio agente para não duplicar personalidade no
Contrato de Arco. Alvos pessoais só podem ser usados quando o vínculo é conhecido
canonicamente; nenhum perfil concede onisciência.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any
import yaml
import arcos
import agentes

AGENTS_INDEX=Path('narrador/agentes/index.yaml')
VALID_INITIATIVE={'baixa','media','alta'}
MAX_IMPULSES=6
MAX_ESCALATIONS=6
MAX_EXAMPLES=4

class AutonomyError(ValueError): pass

def load(path:Path)->Any:
    try:return yaml.safe_load(path.read_text(encoding='utf-8'))
    except (FileNotFoundError,yaml.YAMLError) as e: raise AutonomyError(str(e)) from e

def mp(v,label):
    if not isinstance(v,dict): raise AutonomyError(f'{label} deve ser mapa')
    return v

def ls(v,label):
    if not isinstance(v,list): raise AutonomyError(f'{label} deve ser lista')
    return v

def txt(v,label):
    if not isinstance(v,str) or not v.strip(): raise AutonomyError(f'{label} deve ser texto não vazio')
    return v.strip()

def strict(v,allowed,label):
    extra=set(v)-set(allowed)
    if extra: raise AutonomyError(f'{label} contém campos não permitidos: {", ".join(sorted(extra))}')

def load_index(repo:Path):
    d=mp(load(repo/AGENTS_INDEX),str(AGENTS_INDEX))
    if d.get('schema_agentes')!=2 or d.get('natureza')!='reservado': raise AutonomyError('índice de agentes inválido')
    return mp(d.get('agentes'),'agentes')

def normalize_profile(v:Any,agent_id:str)->dict[str,Any]:
    d=mp(v,f'{agent_id}.autonomia_estrategica')
    strict(d,{'papel_no_arco','iniciativa','regra_masao','regra_conhecimento_vinculos','impulsos','feito_lendario','escaladas_condicionais'},f'{agent_id}.autonomia_estrategica')
    role=txt(d.get('papel_no_arco'),f'{agent_id}.papel_no_arco')
    initiative=txt(d.get('iniciativa'),f'{agent_id}.iniciativa')
    if initiative not in VALID_INITIATIVE: raise AutonomyError(f'{agent_id}: iniciativa inválida')
    if d.get('regra_masao')!='nao_sabotar_plano_mestre': raise AutonomyError(f'{agent_id}: autonomia deve respeitar plano mestre de Masao')
    if d.get('regra_conhecimento_vinculos')!='exige_conhecimento_canonico': raise AutonomyError(f'{agent_id}: vínculos exigem conhecimento canônico')
    impulses=[txt(x,f'{agent_id}.impulsos') for x in ls(d.get('impulsos'),f'{agent_id}.impulsos')]
    if not 1<=len(impulses)<=MAX_IMPULSES: raise AutonomyError(f'{agent_id}: impulsos fora do teto')
    legend=mp(d.get('feito_lendario'),f'{agent_id}.feito_lendario')
    strict(legend,{'principio','exemplos_nao_obrigatorios'},f'{agent_id}.feito_lendario')
    principle=txt(legend.get('principio'),f'{agent_id}.feito_lendario.principio')
    examples=[txt(x,f'{agent_id}.feito_lendario.exemplos') for x in ls(legend.get('exemplos_nao_obrigatorios'),f'{agent_id}.feito_lendario.exemplos')]
    if not 1<=len(examples)<=MAX_EXAMPLES: raise AutonomyError(f'{agent_id}: exemplos lendários fora do teto')
    escalations=[]
    ids=set()
    for i,raw in enumerate(ls(d.get('escaladas_condicionais'),f'{agent_id}.escaladas_condicionais')):
        item=mp(raw,f'{agent_id}.escaladas[{i}]'); strict(item,{'id','quando','abordagem'},f'{agent_id}.escaladas[{i}]')
        eid=txt(item.get('id'),f'{agent_id}.escaladas[{i}].id')
        if eid in ids: raise AutonomyError(f'{agent_id}: escalada duplicada {eid}')
        ids.add(eid); escalations.append({'id':eid,'quando':txt(item.get('quando'),'quando'),'abordagem':txt(item.get('abordagem'),'abordagem')})
    if not 1<=len(escalations)<=MAX_ESCALATIONS: raise AutonomyError(f'{agent_id}: escaladas fora do teto')
    return {'papel_no_arco':role,'iniciativa':initiative,'regra_masao':'nao_sabotar_plano_mestre','regra_conhecimento_vinculos':'exige_conhecimento_canonico','impulsos':impulses,'feito_lendario':{'principio':principle,'exemplos_nao_obrigatorios':examples},'escaladas_condicionais':escalations}

def enabled_profiles(repo:Path)->dict[str,Any]:
    try: info=arcos.current(repo)
    except arcos.ArcContractError as e: raise AutonomyError(str(e)) from e
    index=load_index(repo); rows={}; sources=[*info['fontes_lidas'],AGENTS_INDEX.as_posix()]
    for agent_id in info['habilitacoes']['antagonistas']:
        meta=index.get(agent_id)
        if not isinstance(meta,dict): raise AutonomyError(f'agente habilitado inexistente: {agent_id}')
        try: loaded=agentes.load_agent_complete(repo,agent_id)
        except agentes.AgentValidationError as e: raise AutonomyError(str(e)) from e
        data=mp(loaded['resultado'],agent_id)
        rows[agent_id]=normalize_profile(data.get('autonomia_estrategica'),agent_id); sources.extend(loaded['fontes_lidas'])
    return {'arco_id':info['id'],'perfis':rows,'fontes_lidas':list(dict.fromkeys(sources))}

def validate(repo:Path):
    try:
        r=enabled_profiles(repo)
        return {'ok':True,'quantidade':len(r['perfis']),'agentes':sorted(r['perfis']),'fontes_lidas':r['fontes_lidas'],'erros':[]}
    except (AutonomyError,arcos.ArcContractError) as e:
        return {'ok':False,'quantidade':0,'agentes':[],'fontes_lidas':[],'erros':[str(e)]}

def show(repo:Path,agent_id:str):
    r=enabled_profiles(repo)
    if agent_id not in r['perfis']: raise AutonomyError(f'agente não habilitado no arco: {agent_id}')
    return {'agente':agent_id,'autonomia':r['perfis'][agent_id],'regra':'perfil é repertório de iniciativa, não ação escolhida','fontes_lidas':r['fontes_lidas']}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--repo',type=Path,default=Path.cwd()); sub=p.add_subparsers(dest='cmd',required=True)
    sub.add_parser('validar'); s=sub.add_parser('mostrar'); s.add_argument('agente')
    a=p.parse_args(argv); repo=a.repo.resolve()
    try:r=validate(repo) if a.cmd=='validar' else show(repo,a.agente); print(yaml.safe_dump(r,allow_unicode=True,sort_keys=False),end=''); return 0 if r.get('ok',True) else 1
    except AutonomyError as e: print(f'erro: {e}',file=__import__('sys').stderr); return 1
if __name__=='__main__': raise SystemExit(main())
