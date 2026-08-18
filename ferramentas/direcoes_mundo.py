#!/usr/bin/env python3
"""Integra camadas canônicas de baixa frequência à fila do Mundo Vivo.

Lifecycle de NPCs roda primeiro: uma morte já consolidada desliga agenda e
pendências antes que outras camadas reconsiderem o NPC. Em seguida, relógios
sincronizam pressão→consequência e recompõem seu roteador derivado. Direções,
entradas, agentes recorrentes leves e o baralho mundial observam o mesmo
checkpoint antes de ``mundo.py`` mover o cursor. Nenhuma camada faz
acontecimentos ocorrerem sozinha.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Any
import agentes_leves, ciclo_npcs, direcoes, entradas, eventos_mundo, mundo, relogios

def _direction_pending_id(kind,direction_id,when):
    return "mundo-"+hashlib.sha256(f"{kind}|direcao:{direction_id}|{when.minute}".encode()).hexdigest()[:16]
def _pending_direction_ids(ws): return {str(x.get("direcao")) for x in ws.get("pendencias") or [] if isinstance(x,dict) and x.get("direcao")}
def _entries_configured(repo): return (repo/entradas.INDEX).is_file() and (repo/entradas.STATE).is_file()
def _light_agents_configured(repo): return (repo/agentes_leves.INDEX).is_file() and (repo/agentes_leves.STATE).is_file()
def _crossed_dawn(agenda,start,end):
    if end<=start: return False
    dawn=mundo._dawn_minute(agenda)
    return any(start < mundo.WorldInstant(day*1440+dawn) <= end for day in mundo._iter_day_indices(start,end))
def _activation_records(index,state,ws,when):
    pending=_pending_direction_ids(ws); out=[]
    for did,meta in index["direcoes"].items():
        cur=state["direcoes"][did]
        if cur["estado"]!="latente" or did in pending or not direcoes.dependency_satisfied(index,state,did): continue
        act=meta.get("ativacao")
        if act is None: continue
        dep=act["depende_de"]
        out.append({"id":_direction_pending_id("ativar_direcao",did,when),"tipo":"ativar_direcao","direcao":did,"agentes_afetados":[],"disparado_em":mundo.instant_parts(when),"motivo":f"A dependência canônica {dep['direcao']}.{dep['marco']} foi satisfeita; avaliar a ativação sem escolher cena automaticamente.","origem":f"direcoes:{did}.ativacao"})
    return out
def _evaluation_records(index,state,ws,agenda,start,end):
    if end<=start: return []
    pending=_pending_direction_ids(ws); dawn=mundo._dawn_minute(agenda); out=[]
    for did,meta in index["direcoes"].items():
        cur=state["direcoes"][did]
        if cur["estado"]!="ativa" or did in pending: continue
        ev=meta["avaliacao"]; start_day=mundo._date_to_day_index(ev["inicio"]); interval=int(ev["intervalo_dias"]); due=[]
        for day in mundo._iter_day_indices(start,end):
            if day<start_day or (day-start_day)%interval: continue
            when=mundo.WorldInstant(day*1440+dawn)
            if start<when<=end: due.append(when)
        if due:
            when=due[-1]; out.append({"id":_direction_pending_id("avaliar_direcao",did,when),"tipo":"avaliar_direcao","direcao":did,"agentes_afetados":[],"disparado_em":mundo.instant_parts(when),"motivo":f"Reavaliar o marco {cur.get('marco_atual')} da direção {meta['nome']} contra os fatos canônicos já ocorridos; cadência não implica avanço.","origem":f"direcoes:{did}.avaliacao"})
    return out

def process_checkpoint(repo:Path)->dict[str,Any]:
    lifecycle={"ok":True,"configurado":False,"mortos":[],"novos_mortos":[],"pendencias_canceladas":[]}
    if ciclo_npcs.configured(repo): lifecycle={"configurado":True,**ciclo_npcs.sync(repo)}
    clocks={"ok":True,"configurado":False,"pressoes_ativas":0,"consequencias_resolvidas":0,"resolvidos_agora":[],"roteador_alterado":False}
    if relogios.configured(repo): clocks={"configurado":True,**relogios.sync(repo)}
    index=direcoes.load_index(repo); dstate=direcoes.load_state(repo,index); ws=mundo.load_world_state(repo); agenda=mundo.load_agenda(repo); canonical,_=mundo.load_canonical_time(repo); cursor=mundo._state_cursor(ws)
    if cursor>canonical: raise direcoes.DirectionError("cursor do Mundo Vivo está à frente do tempo canônico")
    emitted=_activation_records(index,dstate,ws,canonical); emitted.extend(_evaluation_records(index,dstate,ws,agenda,cursor,canonical)); emitted.sort(key=lambda x:(mundo.parse_instant(x["disparado_em"]["data"],x["disparado_em"]["hora"]).minute,x["id"]))
    added=mundo._merge_pending(ws,emitted)
    if added: mundo._atomic_write_yaml(repo/mundo.WORLD_STATE_PATH,ws)
    entry={"novas_pendencias":[],"entradas_reconsiderar":[],"fontes_lidas":[]}
    if _entries_configured(repo): entry=entradas.process_checkpoint(repo)
    light={"novas_pendencias":[],"agentes_leves_reconsiderar":[],"adiados_por_orcamento":[],"fontes_lidas":[]}
    if _light_agents_configured(repo) and _crossed_dawn(agenda,cursor,canonical): light=agentes_leves.process_checkpoint(repo)
    events={"ok":True,"configurado":False,"dias_processados":0,"dias_rotina":0,"eventos_sorteados":[],"novas_pendencias":[],"eventos_reconsiderar":[],"fontes_lidas":[]}
    if eventos_mundo.configured(repo): events={"configurado":True,**eventos_mundo.process_checkpoint(repo)}
    return {"ok":True,"ciclo_npcs":lifecycle,"relogios":clocks,"eventos_mundo":events,"novas_pendencias":[*added,*(entry.get("novas_pendencias") or []),*(light.get("novas_pendencias") or []),*(events.get("novas_pendencias") or [])],"direcoes_reconsiderar":sorted({x["direcao"] for x in added}),"entradas_reconsiderar":entry.get("entradas_reconsiderar") or [],"agentes_leves_reconsiderar":light.get("agentes_leves_reconsiderar") or [],"agentes_leves_adiados":light.get("adiados_por_orcamento") or [],"eventos_reconsiderar":events.get("eventos_reconsiderar") or [],"fontes_lidas":[*(lifecycle.get("fontes_lidas") or []),*(clocks.get("fontes_expostas") or []),direcoes.INDEX_PATH.as_posix(),direcoes.STATE_PATH.as_posix(),mundo.WORLD_STATE_PATH.as_posix(),mundo.AGENDA_PATH.as_posix(),mundo.TIME_PATH.as_posix(),*(entry.get("fontes_lidas") or []),*(light.get("fontes_lidas") or []),*(events.get("fontes_lidas") or [])]}

def check_repo(repo:Path)->dict[str,Any]:
    result=direcoes.validate_repo(repo); errors=list(result.get("erros") or [])
    try:
        if ciclo_npcs.configured(repo): errors.extend(f"ciclo de NPCs: {e}" for e in ciclo_npcs.validate_repo(repo).get("erros") or [])
        if relogios.configured(repo): errors.extend(f"relógios: {e}" for e in relogios.validate_repo(repo).get("erros") or [])
        if eventos_mundo.configured(repo): errors.extend(f"eventos: {e}" for e in eventos_mundo.validate_repo(repo).get("erros") or [])
        index=direcoes.load_index(repo); known=set(index["direcoes"]); ws=mundo.load_world_state(repo)
        for x in ws.get("pendencias") or []:
            if x.get("tipo") in {"avaliar_direcao","ativar_direcao"} and x.get("direcao") not in known: errors.append(f"pendência do mundo referencia direção inexistente: {x.get('direcao')}")
        if _entries_configured(repo): errors.extend(f"entradas: {e}" for e in entradas.check_world(repo).get("erros") or [])
        if _light_agents_configured(repo): errors.extend(f"agentes leves: {e}" for e in agentes_leves.check_world(repo).get("erros") or [])
    except (agentes_leves.LightAgentError,ciclo_npcs.LifecycleError,direcoes.DirectionError,entradas.EntryError,eventos_mundo.WorldEventError,mundo.WorldEngineError,relogios.ClockError) as e: errors.append(str(e))
    return {"ok":not errors,"erros":list(dict.fromkeys(errors))}
