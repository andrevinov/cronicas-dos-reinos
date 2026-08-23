#!/usr/bin/env python3
"""Gate frio da população jogável de "Uma Ponte para Kozakura"."""
from __future__ import annotations
import argparse
from pathlib import Path
from typing import Any
import yaml
import arcos, autonomia_juppongatana, pressao_ravens_bluff, contexto_cena, eventos_canonicos

ARC='parte_1_uma_ponte_para_kozakura'
EXPECTED_ANT={'kurobane_jinzaburo','kajiwara_shizune','pan_chu','sawagejo_cho'}
FORBIDDEN={'yukyuzan_anji','uonuma_usui','kureha_shiranui','amagiri_seishiro','wetuji','fuji'}
EXPECTED_ALLIES={'shen_meihua','tsukishiro_joen'}
EXPECTED_DIR={'ponte_de_kozakura','golden_lily_em_ravens_bluff'}
EXPECTED_LINES={'impedir_consolidacao_de_provas','proteger_cadeia_logistica','mapear_rede_de_apoio_de_ren','mascarar_origem_kozakuriana','preservar_monopolio_da_ponte','expandir_presenca_de_masao','ocupar_espaco_urbano','desgastar_autoridade_de_ravens_bluff','pressionar_ren_por_vinculos','pressionar_identidade_marcial_de_ren','sustentar_cobertura_maritima'}
PRINCIPLES=Path('narrador/arcos/parte_1/principios-de-conducao.yaml')
DISCOVERY=Path('narrador/arcos/parte_1/descoberta-e-consequencias.yaml')
LIFE=Path('narrador/arcos/parte_1/vida-civil.yaml')
DIRECTION_INDEX=Path('narrador/direcoes/index.yaml'); DIRECTION_STATE=Path('narrador/direcoes/estado.yaml'); AGENDA=Path('narrador/mundo/agenda.yaml')

class PartOneError(ValueError): pass

def load(path):
    try:return yaml.safe_load(path.read_text(encoding='utf-8'))
    except (FileNotFoundError,yaml.YAMLError) as e: raise PartOneError(str(e)) from e

def mp(v,label):
    if not isinstance(v,dict): raise PartOneError(f'{label} deve ser mapa')
    return v

def validate_story_files(repo:Path):
    p=mp(load(repo/PRINCIPLES),str(PRINCIPLES)); d=mp(load(repo/DISCOVERY),str(DISCOVERY)); l=mp(load(repo/LIFE),str(LIFE))
    if p.get('schema_principios_parte_1')!=1 or p.get('arco')!=ARC: raise PartOneError('princípios da Parte 1 inválidos')
    j=mp(p.get('juppongatana'),'juppongatana')
    if mp(j.get('aparicao'),'aparicao').get('estatuto')!='evento_revelacao': raise PartOneError('aparição da Juppongatana deve ser evento/revelação')
    a=mp(j.get('autonomia'),'autonomia')
    for flag in ('nunca_sabotar_masao','nao_sao_minions_passivos','alvo_pessoal_exige_conhecimento_canonico','podem_agir_fora_da_presenca_de_ren'):
        if a.get(flag) is not True: raise PartOneError(f'princípio ausente: {flag}')
    jogador=mp(p.get('jogador'),'jogador')
    if jogador.get('nunca_escrever_decisao_de_ren') is not True: raise PartOneError('agência de Ren perdeu guardrail')
    if jogador.get('evento_canonico_pode_forcar_situacao') is not True: raise PartOneError('evento canônico não possui prioridade operacional')
    if d.get('schema_descoberta_consequencias')!=1 or d.get('arco')!=ARC: raise PartOneError('contrato de descoberta inválido')
    rules=mp(d.get('regras'),'descoberta.regras')
    if rules.get('ren_nao_e_notificado_automaticamente') is not True or rules.get('feito_lendario_deve_ter_repercussao') is not True: raise PartOneError('descoberta/consequência perdeu guardrail')
    if l.get('schema_vida_civil_parte_1')!=1 or l.get('arco')!=ARC: raise PartOneError('vida civil inválida')
    if mp(mp(l.get('dojo'),'dojo').get('night_watch'),'dojo.night_watch').get('automatico') is not False: raise PartOneError('contrato com Night Watch não pode ser automático')
    if mp(l.get('relacoes'),'relacoes').get('automatico') is not False: raise PartOneError('romance não pode ser automático')
    return [str(PRINCIPLES),str(DISCOVERY),str(LIFE)]

def validate_runtime_hooks(repo:Path):
    idx=mp(load(repo/DIRECTION_INDEX),str(DIRECTION_INDEX)); st=mp(load(repo/DIRECTION_STATE),str(DIRECTION_STATE)); ag=mp(load(repo/AGENDA),str(AGENDA))
    if 'golden_lily_em_ravens_bluff' not in mp(idx.get('direcoes'),'direcoes'): raise PartOneError('direção Golden Lily não integrada ao índice')
    gs=mp(mp(st.get('direcoes'),'estado_direcoes').get('golden_lily_em_ravens_bluff'),'golden state')
    if gs.get('estado')!='ativa' or gs.get('marco_atual')!='rumores_de_grande_navio': raise PartOneError('estado inicial Golden Lily inválido')
    schedules=[x for x in ag.get('agendamentos') or [] if isinstance(x,dict) and x.get('id')=='chegada_golden_lily_27_eleasis']
    if len(schedules)!=1: raise PartOneError('agendamento canônico Golden Lily ausente/duplicado')
    s=schedules[0]
    if s.get('tipo')!='movimento' or s.get('agente')!='pan_chu' or s.get('em')!={'data':'27 Eleasis, 1372 DR','hora':'10:00'} or s.get('evento_canonico')!='chegada_golden_lily': raise PartOneError('agendamento Golden Lily divergente')
    rec=mp(ag.get('reavaliacoes'),'reavaliacoes')
    for aid in ('kajiwara_shizune','sawagejo_cho','pan_chu'):
        if aid not in rec: raise PartOneError(f'reavaliação autônoma ausente: {aid}')
    return [str(DIRECTION_INDEX),str(DIRECTION_STATE),str(AGENDA)]

def validate(repo:Path):
    errors=[]; sources=[]
    try:
        arc=arcos.current(repo); sources+=arc['fontes_lidas']
        if arc['id']!=ARC: raise PartOneError(f'arco corrente não é Parte 1: {arc["id"]}')
        enabled=arc['habilitacoes']
        ants=set(enabled['antagonistas']); allies=set(enabled['aliados']); dirs=set(enabled['direcoes'])
        if ants!=EXPECTED_ANT: raise PartOneError(f'antagonistas Parte 1 divergiram: {sorted(ants)}')
        if ants & FORBIDDEN: raise PartOneError('Juppongatana posterior vazou para Parte 1')
        if allies!=EXPECTED_ALLIES: raise PartOneError('aliados Parte 1 divergiram')
        if dirs!=EXPECTED_DIR: raise PartOneError('direções Parte 1 divergiram')
        if set(arc['linhas_operacionais'])!=EXPECTED_LINES: raise PartOneError('linhas operacionais Parte 1 divergiram')
        av=autonomia_juppongatana.validate(repo); sources+=av.get('fontes_lidas') or []
        if not av['ok'] or set(av['agentes'])!=EXPECTED_ANT: raise PartOneError('autonomia dos quatro Juppongatana inválida: '+'; '.join(av.get('erros') or []))
        pr=pressao_ravens_bluff.validate(repo); sources+=pr.get('fontes_lidas') or []
        if not pr['ok'] or pr['frentes']!=5: raise PartOneError('pressão urbana inválida: '+'; '.join(pr.get('erros') or []))
        cv=contexto_cena.validate(repo); sources+=cv.get('fontes_lidas') or []
        if not cv['ok']: raise PartOneError('roteador contextual inválido')
        ce=eventos_canonicos.validate(repo); sources+=ce.get('fontes_lidas') or []
        if not ce['ok'] or ce['eventos']!=17: raise PartOneError('calendário canônico da Parte 1 inválido: '+'; '.join(ce.get('erros') or []))
        sources+=validate_story_files(repo); sources+=validate_runtime_hooks(repo)
    except (PartOneError,arcos.ArcContractError,autonomia_juppongatana.AutonomyError,pressao_ravens_bluff.PressureError,contexto_cena.ContextSceneError,eventos_canonicos.CanonicalEventError) as e: errors.append(str(e))
    return {'ok':not errors,'arco':ARC,'erros':errors,'fontes_lidas':list(dict.fromkeys(sources))}
def status(repo:Path):
    v=validate(repo)
    if not v['ok']: return v
    arc=arcos.current(repo); pressure=pressao_ravens_bluff.status(repo)
    return {'ok':True,'titulo':arc['titulo'],'antagonistas':arc['habilitacoes']['antagonistas'],'aliados':arc['habilitacoes']['aliados'],'direcoes':arc['habilitacoes']['direcoes'],'linhas_operacionais':list(arc['linhas_operacionais']),'eventos_canonicos':17,'pressao':[{k:x[k] for k in ('id','nivel','titulo')} for x in pressure['frentes']],'regra':'mundo aberto entre e durante eventos; núcleos datados obrigatórios, forma e resultado emergentes','fontes_lidas':list(dict.fromkeys([*v['fontes_lidas'],*pressure['fontes_lidas']]))}
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--repo',type=Path,default=Path.cwd()); p.add_argument('cmd',choices=['validar','status']); a=p.parse_args(argv); r=validate(a.repo.resolve()) if a.cmd=='validar' else status(a.repo.resolve()); print(yaml.safe_dump(r,allow_unicode=True,sort_keys=False),end=''); return 0 if r.get('ok') else 1
if __name__=='__main__': raise SystemExit(main())