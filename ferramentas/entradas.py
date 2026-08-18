#!/usr/bin/env python3
"""Elegibilidade determinística de entrada dos aliados futuros."""
from __future__ import annotations
import argparse, hashlib, os, tempfile, unicodedata
from pathlib import Path
import yaml
import mundo

INDEX=Path("narrador/entradas/index.yaml")
STATE=Path("narrador/entradas/estado.yaml")
RUNTIME=Path("runtime/contexto.yaml")
DIR=Path("narrador/entradas")
VALID={"latente","presente","inviavel"}
TERMINAIS={"presente","inviavel"}

class EntryError(ValueError): pass

def load(path):
    try: return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError,yaml.YAMLError) as e: raise EntryError(str(e)) from e

def text(v,label):
    if not isinstance(v,str) or not v.strip(): raise EntryError(f"{label} deve ser texto não vazio")
    return v.strip()

def norm(v): return " ".join(str(v).split())

def lookup(v):
    s=unicodedata.normalize("NFKD",v)
    s="".join(c for c in s if not unicodedata.combining(c))
    return " ".join("".join(c.lower() if c.isalnum() else " " for c in s).split())

def atomic(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile("w",encoding="utf-8",dir=path.parent,delete=False) as h:
        yaml.safe_dump(data,h,allow_unicode=True,sort_keys=False); h.flush(); os.fsync(h.fileno()); tmp=Path(h.name)
    os.replace(tmp,path)

def load_index(repo):
    d=load(repo/INDEX)
    if not isinstance(d,dict) or d.get("schema_entradas")!=1 or d.get("natureza")!="reservado": raise EntryError("índice de entradas inválido")
    if not isinstance(d.get("cadencia_padrao_dias"),int) or d["cadencia_padrao_dias"]<1: raise EntryError("cadência inválida")
    c=d.get("candidatos")
    if not isinstance(c,dict) or not c: raise EntryError("candidatos ausentes")
    orders=[]; files=set()
    for cid,m in c.items():
        if not isinstance(m,dict): raise EntryError(f"{cid}: metadados inválidos")
        text(m.get("nome"),f"{cid}.nome")
        if not isinstance(m.get("ordem"),int) or m["ordem"]<1: raise EntryError(f"{cid}: ordem inválida")
        if not isinstance(m.get("nivel_minimo_normal"),int) or m["nivel_minimo_normal"]<1: raise EntryError(f"{cid}: nível inválido")
        raw=text(m.get("arquivo"),f"{cid}.arquivo"); p=Path(raw)
        if p.is_absolute() or ".." in p.parts or DIR not in p.parents: raise EntryError(f"{cid}: arquivo fora de narrador/entradas")
        if raw in files: raise EntryError("arquivo duplicado")
        files.add(raw); orders.append(m["ordem"])
    if sorted(orders)!=list(range(1,len(orders)+1)): raise EntryError("ordens devem formar 1..N")
    return d

def parse_due(v,label):
    if v is None: return None
    if not isinstance(v,dict): raise EntryError(f"{label} inválido")
    return mundo.parse_instant(text(v.get("data"),label+".data"),text(v.get("hora"),label+".hora"))

def load_state(repo,index=None):
    index=index or load_index(repo); d=load(repo/STATE)
    if not isinstance(d,dict) or d.get("schema_estado_entradas")!=1 or d.get("natureza")!="controle_reservado": raise EntryError("estado de entradas inválido")
    states=d.get("candidatos")
    if not isinstance(states,dict) or set(states)!=set(index["candidatos"]): raise EntryError("estado não corresponde ao índice")
    anticipated=[]
    for cid,s in states.items():
        if not isinstance(s,dict) or s.get("estado") not in VALID or not isinstance(s.get("antecipado"),bool): raise EntryError(f"{cid}: estado inválido")
        if s["estado"] in TERMINAIS and s["antecipado"]: raise EntryError(f"{cid}: estado terminal antecipado")
        if s["estado"] in TERMINAIS and s.get("proxima_avaliacao") is not None: raise EntryError(f"{cid}: estado terminal agendado")
        if s["antecipado"]: anticipated.append(cid)
        parse_due(s.get("proxima_avaliacao"),cid+".proxima_avaliacao")
        if not isinstance(s.get("historico_recente"),list): raise EntryError(f"{cid}: histórico inválido")
    if len(anticipated)>1: raise EntryError("somente um antecipado por vez")
    return d

def ordered(index): return [cid for cid,_ in sorted(index["candidatos"].items(),key=lambda x:x[1]["ordem"])]
def normal(index,state): return next((cid for cid in ordered(index) if state["candidatos"][cid]["estado"]=="latente"),None)
def anticipated(state): return next((cid for cid,s in state["candidatos"].items() if s["antecipado"] and s["estado"]=="latente"),None)
def focus(index,state): return anticipated(state) or normal(index,state)

def resolve(index,q):
    if q in index["candidatos"]: return q,index["candidatos"][q]
    w=lookup(q); hits=[]
    for cid,m in index["candidatos"].items():
        pool={lookup(cid),lookup(m["nome"])}
        if w in pool or any(w and w in x for x in pool): hits.append((cid,m))
    if len(hits)!=1: raise EntryError(f"candidato não encontrado/ambíguo: {q}")
    return hits[0]

def level(repo):
    v=((load(repo/RUNTIME) or {}).get("personagem") or {}).get("nivel")
    if not isinstance(v,int) or v<1: raise EntryError("nível de Ren inválido no runtime")
    return v

def next_dawn(repo):
    now,_=mundo.load_canonical_time(repo); dawn=mundo._dawn_minute(mundo.load_agenda(repo)); day,clock=divmod(now.minute,1440)
    return mundo.WorldInstant((day+(1 if clock>=dawn else 0))*1440+dawn)

def record(action,origin,note,when): return {"acao":action,"em":mundo.instant_parts(when),"origem":text(origin,"origem"),"nota":text(note,"nota")}

def mutate(repo,q,action,origin,note):
    index=load_index(repo); state=load_state(repo,index); cid,_=resolve(index,q); cur=state["candidatos"][cid]; now,_=mundo.load_canonical_time(repo)
    if cur["estado"]=="inviavel": raise EntryError(f"{cid} está inviável e não pode entrar em cena")
    if cur["estado"]=="presente":
        if action=="confirmar": return {"ok":True,"alterou":False,"candidato":cid}
        raise EntryError(f"{cid} já está presente")
    if action=="antecipar":
        other=anticipated(state)
        if other and other!=cid: raise EntryError(f"já existe candidato antecipado: {other}")
        cur["antecipado"]=True; cur["proxima_avaliacao"]=mundo.instant_parts(next_dawn(repo))
    else:
        cur["estado"]="presente"; cur["antecipado"]=False; cur["proxima_avaliacao"]=None
    cur["historico_recente"].append(record(action,origin,note,now)); cur["historico_recente"]=cur["historico_recente"][-24:]
    nxt=normal(index,state)
    if action=="confirmar" and nxt and not anticipated(state) and state["candidatos"][nxt]["proxima_avaliacao"] is None: state["candidatos"][nxt]["proxima_avaliacao"]=mundo.instant_parts(next_dawn(repo))
    atomic(repo/STATE,state)
    return {"ok":True,"alterou":True,"candidato":cid,"proximo_candidato_normal":nxt}

def validate_fragment(repo,cid,meta,full):
    raw=meta["arquivo"]; d=load(repo/raw)
    if not isinstance(d,dict) or d.get("schema_entrada")!=1 or d.get("natureza")!="reservado": raise EntryError(f"{cid}: fragmento inválido")
    if d.get("id")!=cid or d.get("nome")!=meta["nome"] or d.get("ordem")!=meta["ordem"] or d.get("nivel_minimo_normal")!=meta["nivel_minimo_normal"]: raise EntryError(f"{cid}: fragmento diverge do índice")
    src=d.get("fontes_canonicas"); anchors=d.get("ancoras")
    if not isinstance(src,list) or not src or not isinstance(anchors,list) or not anchors: raise EntryError(f"{cid}: proveniência ausente")
    for a in anchors:
        source=text(a.get("fonte"),"fonte"); evidence=text(a.get("evidencia"),"evidencia")
        if source not in src: raise EntryError(f"{cid}: fonte não declarada")
        if full:
            p=repo/source
            if not p.is_file() or norm(evidence) not in norm(p.read_text(encoding="utf-8")): raise EntryError(f"{cid}: evidência não localizada")
    return d

def show(repo,q):
    index=load_index(repo); state=load_state(repo,index); cid,meta=resolve(index,q); d=validate_fragment(repo,cid,meta,False); lv=level(repo)
    return {"candidato":cid,"estado":state["candidatos"][cid],"caminho_normal":cid==normal(index,state),"elegivel_por_nivel":state["candidatos"][cid]["estado"]=="latente" and lv>=meta["nivel_minimo_normal"],"fontes_lidas":[str(INDEX),str(STATE),meta["arquivo"],str(RUNTIME)],"resultado":d}

def status(repo):
    index=load_index(repo); state=load_state(repo,index); n=normal(index,state); a=anticipated(state); f=a or n; lv=level(repo); detail=None
    if f:
        m=index["candidatos"][f]; s=state["candidatos"][f]
        detail={"id":f,"nome":m["nome"],"via":"antecipacao" if a else "ordem_preferencial","nivel_atual":lv,"nivel_minimo_normal":m["nivel_minimo_normal"],"elegivel_por_nivel":lv>=m["nivel_minimo_normal"],"proxima_avaliacao":s["proxima_avaliacao"]}
    inviaveis=[cid for cid,s in state["candidatos"].items() if s["estado"]=="inviavel"]
    return {"candidato_normal":n,"candidato_antecipado":a,"candidato_em_foco":detail,"inviaveis":inviaveis,"fontes_lidas":[str(INDEX),str(STATE),str(RUNTIME)]}

def validate(repo):
    errors=[]
    try:
        index=load_index(repo); state=load_state(repo,index)
        for cid,m in index["candidatos"].items(): validate_fragment(repo,cid,m,True)
        n=normal(index,state)
        for cid,s in state["candidatos"].items():
            if s["estado"] in TERMINAIS and s["proxima_avaliacao"] is not None: errors.append(f"{cid}: terminal agendado")
            if cid!=n and not s["antecipado"] and s["estado"]=="latente" and s["proxima_avaliacao"] is not None: errors.append(f"{cid}: fora da ordem agendado")
    except (EntryError,mundo.WorldEngineError) as e: errors.append(str(e))
    return {"ok":not errors,"quantidade":len(index["candidatos"]) if "index" in locals() else 0,"erros":errors}

def pending_id(cid,when): return "mundo-"+hashlib.sha256(f"avaliar_entrada|{cid}|{when.minute}".encode()).hexdigest()[:16]

def process_checkpoint(repo):
    index=load_index(repo); state=load_state(repo,index); ws=mundo.load_world_state(repo); now,_=mundo.load_canonical_time(repo); cid=focus(index,state)
    sources=[str(INDEX),str(STATE),str(RUNTIME),str(mundo.WORLD_STATE_PATH),str(mundo.TIME_PATH)]
    if not cid: return {"ok":True,"novas_pendencias":[],"entradas_reconsiderar":[],"fontes_lidas":sources}
    cur=state["candidatos"][cid]; due=parse_due(cur["proxima_avaliacao"],cid+".proxima_avaliacao")
    if due is None or due>now: return {"ok":True,"novas_pendencias":[],"entradas_reconsiderar":[],"fontes_lidas":sources}
    cadence=index["cadencia_padrao_dias"]; cur["proxima_avaliacao"]=mundo.instant_parts(mundo.WorldInstant(due.minute+cadence*1440))
    opened={x.get("entrada") for x in ws["pendencias"] if x.get("tipo")=="avaliar_entrada"}
    if cid in opened: atomic(repo/STATE,state); return {"ok":True,"novas_pendencias":[],"entradas_reconsiderar":[],"fontes_lidas":sources}
    meta=index["candidatos"][cid]; lv=level(repo)
    if not cur["antecipado"] and lv<meta["nivel_minimo_normal"]: atomic(repo/STATE,state); return {"ok":True,"novas_pendencias":[],"entradas_reconsiderar":[],"adiada_por_nivel":cid,"fontes_lidas":sources}
    rec={"id":pending_id(cid,due),"tipo":"avaliar_entrada","entrada":cid,"agentes_afetados":[],"disparado_em":mundo.instant_parts(due),"motivo":f"Avaliar entrada de {meta['nome']} sem fazê-la acontecer automaticamente.","origem":f"entradas:{cid}"}
    added=mundo._merge_pending(ws,[rec])
    if added: mundo._atomic_write_yaml(repo/mundo.WORLD_STATE_PATH,ws)
    atomic(repo/STATE,state)
    return {"ok":True,"novas_pendencias":added,"entradas_reconsiderar":[cid] if added else [],"fontes_lidas":sources}

def check_world(repo):
    r=validate(repo); errors=list(r["erros"])
    try:
        known=set(load_index(repo)["candidatos"]); ws=mundo.load_world_state(repo); opened=[]
        for x in ws["pendencias"]:
            if x.get("tipo")=="avaliar_entrada":
                if x.get("entrada") not in known: errors.append(f"entrada inexistente: {x.get('entrada')}")
                else: opened.append(x["entrada"])
        if len(opened)>1: errors.append("mais de uma avaliação de entrada aberta")
    except (EntryError,mundo.WorldEngineError) as e: errors.append(str(e))
    return {"ok":not errors,"erros":list(dict.fromkeys(errors))}

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__); p.add_argument("--repo",type=Path,default=Path.cwd()); sub=p.add_subparsers(dest="cmd",required=True)
    sub.add_parser("status"); sub.add_parser("validar"); q=sub.add_parser("mostrar"); q.add_argument("candidato")
    for c in ("antecipar","confirmar"):
        q=sub.add_parser(c); q.add_argument("candidato"); q.add_argument("--origem",required=True); q.add_argument("--nota",required=True)
    a=p.parse_args(argv); repo=a.repo.resolve()
    try:
        if a.cmd=="status": r=status(repo)
        elif a.cmd=="validar": r=validate(repo)
        elif a.cmd=="mostrar": r=show(repo,a.candidato)
        else: r=mutate(repo,a.candidato,a.cmd,a.origem,a.nota)
        print(yaml.safe_dump(r,allow_unicode=True,sort_keys=False),end="")
        return 0 if r.get("ok",True) else 1
    except (EntryError,mundo.WorldEngineError) as e:
        print(f"erro: {e}")
        return 1

if __name__=="__main__": raise SystemExit(main())
