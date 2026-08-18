#!/usr/bin/env python3
"""Baralho determinístico sem reposição para eventos mundiais de baixa frequência.

Dois baralhos persistentes: ocorrência decide rotina/evento; eventos fornece a
carta concreta. Sorteio nunca cria cânone automaticamente.
"""
from __future__ import annotations
import argparse, hashlib, os, tempfile, unicodedata
from pathlib import Path
from typing import Any
import yaml
import mundo

INDEX=Path("narrador/eventos/index.yaml")
STATE=Path("narrador/eventos/estado.yaml")
CARDS_DIR=Path("narrador/eventos/cartas")
VALID_RESULTS={"rotina","evento"}
VALID_SCALES={"bairro","cidade","regional"}
MAX_HISTORY=64

class WorldEventError(ValueError): pass

def configured(repo): return (repo/INDEX).is_file() and (repo/STATE).is_file()
def load(path):
    try: return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError,yaml.YAMLError) as e: raise WorldEventError(str(e)) from e
def text(v,label):
    if not isinstance(v,str) or not v.strip(): raise WorldEventError(f"{label} deve ser texto não vazio")
    return v.strip()
def amap(v,label):
    if not isinstance(v,dict): raise WorldEventError(f"{label} deve ser mapa")
    return v
def alist(v,label):
    if not isinstance(v,list): raise WorldEventError(f"{label} deve ser lista")
    return v
def norm(v):
    s=unicodedata.normalize("NFKD",str(v)); s="".join(c for c in s if not unicodedata.combining(c))
    return " ".join("".join(c.lower() if c.isalnum() else " " for c in s).split())
def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",encoding="utf-8",dir=path.parent,prefix=f".{path.name}.",delete=False) as h:
        yaml.safe_dump(data,h,allow_unicode=True,sort_keys=False); h.flush(); os.fsync(h.fileno()); tmp=Path(h.name)
    os.replace(tmp,path)
def repo_path(repo,raw,prefix=None):
    p=Path(raw)
    if p.is_absolute() or ".." in p.parts: raise WorldEventError(f"caminho fora do repo: {raw}")
    if prefix is not None:
        try: p.relative_to(prefix)
        except ValueError as e: raise WorldEventError(f"caminho {raw} deve ficar sob {prefix}") from e
    return repo/p

def load_index(repo):
    d=amap(load(repo/INDEX),str(INDEX))
    if d.get("schema_eventos_mundo")!=1 or d.get("natureza")!="reservado": raise WorldEventError("índice de eventos inválido")
    text(d.get("semente"),"semente"); ini=amap(d.get("inicio"),"inicio"); mundo.parse_instant(text(ini.get("data"),"inicio.data"),text(ini.get("hora"),"inicio.hora"))
    occ=amap(d.get("ocorrencia"),"ocorrencia"); fichas=alist(occ.get("fichas"),"ocorrencia.fichas")
    seen=set(); resultados=[]
    for i,x in enumerate(fichas):
        x=amap(x,f"fichas[{i}]"); fid=text(x.get("id"),f"fichas[{i}].id"); r=text(x.get("resultado"),f"fichas[{i}].resultado")
        if fid in seen or r not in VALID_RESULTS: raise WorldEventError("ficha de ocorrência inválida/duplicada")
        seen.add(fid); resultados.append(r)
    if "rotina" not in resultados or "evento" not in resultados: raise WorldEventError("urna precisa de rotina e evento")
    cards=amap(d.get("cartas"),"cartas"); files=set()
    if not cards: raise WorldEventError("catálogo vazio")
    for cid,m in cards.items():
        m=amap(m,f"cartas.{cid}"); text(m.get("nome"),f"{cid}.nome"); text(m.get("categoria"),f"{cid}.categoria"); esc=text(m.get("escala"),f"{cid}.escala")
        if esc not in VALID_SCALES: raise WorldEventError(f"{cid}: escala inválida")
        raw=text(m.get("arquivo"),f"{cid}.arquivo"); repo_path(repo,raw,CARDS_DIR)
        if raw in files: raise WorldEventError("arquivo de carta duplicado")
        files.add(raw)
    return d

def instant(v,label):
    v=amap(v,label); return mundo.parse_instant(text(v.get("data"),label+".data"),text(v.get("hora"),label+".hora"))
def load_state(repo,index=None):
    index=index or load_index(repo); d=amap(load(repo/STATE),str(STATE))
    if d.get("schema_estado_eventos_mundo")!=1 or d.get("natureza")!="controle_reservado": raise WorldEventError("estado de eventos inválido")
    instant(d.get("processado_ate"),"processado_ate")
    valid={"ocorrencia":{x["id"] for x in index["ocorrencia"]["fichas"]},"eventos":set(index["cartas"])}
    for name in ("ocorrencia","eventos"):
        deck=amap(d.get(name),name); c=deck.get("ciclo"); rem=alist(deck.get("restantes"),name+".restantes")
        if not isinstance(c,int) or c<0 or len(rem)!=len(set(rem)) or set(rem)-valid[name]: raise WorldEventError(f"{name}: estado inválido")
        if c==0 and rem: raise WorldEventError(f"{name}: ciclo 0 exige vazio")
    hist=alist(d.get("historico_recente"),"historico_recente")
    if len(hist)>MAX_HISTORY: raise WorldEventError("histórico grande demais")
    return d

def deck_order(seed,deck,cycle,ids):
    return sorted(ids,key=lambda x:hashlib.sha256(f"{seed}|{deck}|{cycle}|{x}".encode()).hexdigest())
def draw(state,section,ids,seed):
    d=state[section]
    if not d["restantes"]: d["ciclo"]+=1; d["restantes"]=deck_order(seed,section,d["ciclo"],ids)
    return d["restantes"].pop(0)
def pending_id(cid,when): return "mundo-"+hashlib.sha256(f"evento_mundial|{cid}|{when.minute}".encode()).hexdigest()[:16]
def dawns(start,end,dawn,minimum):
    return [mundo.WorldInstant(day*1440+dawn) for day in mundo._iter_day_indices(start,end) if start < mundo.WorldInstant(day*1440+dawn) <= end and mundo.WorldInstant(day*1440+dawn) >= minimum]

def process_checkpoint(repo):
    idx=load_index(repo); st=load_state(repo,idx); agenda=mundo.load_agenda(repo); now,_=mundo.load_canonical_time(repo); ws=mundo.load_world_state(repo)
    done=instant(st["processado_ate"],"processado_ate")
    if done>now: raise WorldEventError("cursor do baralho está à frente do tempo canônico")
    due=dawns(done,now,mundo._dawn_minute(agenda),instant(idx["inicio"],"inicio"))
    sources=[str(INDEX),str(STATE),str(mundo.AGENDA_PATH),str(mundo.TIME_PATH),str(mundo.WORLD_STATE_PATH)]
    if not due: return {"ok":True,"alterou":False,"dias_processados":0,"dias_rotina":0,"eventos_sorteados":[],"novas_pendencias":[],"eventos_reconsiderar":[],"fontes_lidas":sources}
    seed=idx["semente"]; tmap={x["id"]:x["resultado"] for x in idx["ocorrencia"]["fichas"]}; tids=list(tmap); cids=list(idx["cartas"]); emitted=[]; rotina=0; sorteados=[]
    for when in due:
        token=draw(st,"ocorrencia",tids,seed); result=tmap[token]; hist={"amanhecer":mundo.instant_parts(when),"ficha_ocorrencia":token,"resultado":result}
        if result=="rotina": rotina+=1
        else:
            cid=draw(st,"eventos",cids,seed); meta=idx["cartas"][cid]; hist["evento"]=cid; sorteados.append(cid)
            emitted.append({"id":pending_id(cid,when),"tipo":"evento_mundial","evento":cid,"categoria":meta["categoria"],"escala":meta["escala"],"agentes_afetados":[],"disparado_em":mundo.instant_parts(when),"motivo":f"Carta mundial '{meta['nome']}' sorteada sem reposição; resolver sem torná-la canônica automaticamente.","origem":f"eventos:{cid}"})
        st["historico_recente"].append(hist); st["historico_recente"]=st["historico_recente"][-MAX_HISTORY:]; st["processado_ate"]=mundo.instant_parts(when)
    added=mundo._merge_pending(ws,emitted)
    if added: mundo._atomic_write_yaml(repo/mundo.WORLD_STATE_PATH,ws)
    atomic(repo/STATE,st)
    return {"ok":True,"alterou":True,"dias_processados":len(due),"dias_rotina":rotina,"eventos_sorteados":sorteados,"novas_pendencias":added,"eventos_reconsiderar":[x["evento"] for x in added],"fontes_lidas":sources}

def validate_card(repo,cid,meta):
    raw=text(meta.get("arquivo"),f"{cid}.arquivo"); d=amap(load(repo_path(repo,raw,CARDS_DIR)),raw)
    if d.get("schema_evento_mundo")!=1 or d.get("natureza")!="reservado" or d.get("estatuto")!="molde_nao_canonico_ate_resolucao": raise WorldEventError(f"{cid}: fragmento inválido")
    if d.get("id")!=cid or d.get("nome")!=meta["nome"] or d.get("categoria")!=meta["categoria"] or d.get("escala")!=meta["escala"]: raise WorldEventError(f"{cid}: fragmento diverge do índice")
    text(d.get("premissa"),cid+".premissa"); text(d.get("pergunta_de_resolucao"),cid+".pergunta")
    for field in ("guardrails","tags"):
        vals=alist(d.get(field),f"{cid}.{field}")
        if not vals: raise WorldEventError(f"{cid}.{field} vazio")
        for i,v in enumerate(vals): text(v,f"{cid}.{field}[{i}]")
    return d

def resolve(idx,q):
    if q in idx["cartas"]: return q,idx["cartas"][q]
    w=norm(q); hits=[]
    for cid,m in idx["cartas"].items():
        pool={norm(cid),norm(m["nome"])}
        if w in pool or any(w and w in x for x in pool): hits.append((cid,m))
    if len(hits)!=1: raise WorldEventError(f"carta não encontrada/ambígua: {q}")
    return hits[0]
def show(repo,q):
    idx=load_index(repo); cid,m=resolve(idx,q); card=validate_card(repo,cid,m); return {"evento_id":cid,"fontes_lidas":[str(INDEX),m["arquivo"]],"resultado":card}
def status(repo):
    idx=load_index(repo); st=load_state(repo,idx); return {"processado_ate":st["processado_ate"],"ocorrencia":{"ciclo":st["ocorrencia"]["ciclo"],"restantes":len(st["ocorrencia"]["restantes"]),"total_por_ciclo":len(idx["ocorrencia"]["fichas"])},"eventos":{"ciclo":st["eventos"]["ciclo"],"restantes":len(st["eventos"]["restantes"]),"total_por_ciclo":len(idx["cartas"])},"historico_recente":st["historico_recente"],"fontes_lidas":[str(INDEX),str(STATE)]}
def validate_repo(repo):
    errors=[]
    try:
        idx=load_index(repo); st=load_state(repo,idx)
        for cid,m in idx["cartas"].items(): validate_card(repo,cid,m)
        ws=mundo.load_world_state(repo); known=set(idx["cartas"])
        for x in ws.get("pendencias") or []:
            if x.get("tipo")=="evento_mundial" and x.get("evento") not in known: errors.append(f"evento inexistente: {x.get('evento')}")
        now,_=mundo.load_canonical_time(repo)
        if instant(st["processado_ate"],"processado_ate")>now: errors.append("estado de eventos além do tempo canônico")
    except (WorldEventError,mundo.WorldEngineError) as e: errors.append(str(e))
    return {"ok":not errors,"quantidade_cartas":len(idx["cartas"]) if "idx" in locals() else 0,"erros":list(dict.fromkeys(errors))}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--repo",type=Path,default=Path.cwd()); sub=p.add_subparsers(dest="cmd",required=True)
    sub.add_parser("status"); sub.add_parser("processar"); sub.add_parser("validar"); q=sub.add_parser("mostrar"); q.add_argument("evento"); a=p.parse_args(argv); repo=a.repo.resolve()
    try:
        r=status(repo) if a.cmd=="status" else process_checkpoint(repo) if a.cmd=="processar" else validate_repo(repo) if a.cmd=="validar" else show(repo,a.evento)
        print(yaml.safe_dump(r,allow_unicode=True,sort_keys=False),end=""); return 0 if a.cmd!="validar" or r["ok"] else 1
    except (WorldEventError,mundo.WorldEngineError) as e: print(f"erro: {e}"); return 1
if __name__=="__main__": raise SystemExit(main())
