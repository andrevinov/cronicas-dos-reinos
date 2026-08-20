from __future__ import annotations
import tempfile, sys
from pathlib import Path
import yaml
ROOT=Path(__file__).parents[1]; TOOLS=ROOT/'ferramentas'; sys.path.insert(0,str(TOOLS))
import aliados_contextuais

def w(root,rel,data):
    p=root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(yaml.safe_dump(data,allow_unicode=True,sort_keys=False),encoding='utf-8')
with tempfile.TemporaryDirectory() as tmp:
    r=Path(tmp)
    w(r,'narrador/arcos/index.yaml',{'schema_arcos':1,'natureza':'roteador_reservado','arcos':{'p1':{'titulo':'P1','ordem':1,'arquivo':'narrador/arcos/p1.yaml','proximo':None}}})
    w(r,'narrador/arcos/estado.yaml',{'schema_estado_arcos':2,'natureza':'controle_reservado','arco_atual':'p1','estado':'ativo','historico_transicoes':[]})
    w(r,'narrador/arcos/p1.yaml',{'schema_arco':4,'natureza':'reservado','estatuto':'contrato_orquestrador_de_arco','id':'p1','titulo':'P1','principio':'smoke','inicio':{'tipo':'fato_canonico','marcador':'i','fonte':'campanha.yaml'},'termino':{'tipo':'marco_explicito','marcador':'f','fonte':'campanha.yaml'},'orquestracao':{'fontes':{'p':{'tipo':'documento_reservado','arquivo':'narrador/masao/plano.md'}},'plano_mestre':{'agente':'masao','objetivo':'o','referencia':'p'}},'habilitacoes':{'politica_nao_listados':'bloqueados','antagonistas':[],'aliados':['shen'],'direcoes':[]},'linhas_operacionais':{'l':{'objetivo':'o2','executores':['masao'],'referencia':'p'}}})
    w(r,'narrador/entradas/index.yaml',{'schema_entradas':1,'natureza':'reservado','cadencia_padrao_dias':3,'candidatos':{'shen':{'nome':'Shen','ordem':1,'nivel_minimo_normal':6,'arquivo':'narrador/entradas/shen.yaml'}}})
    w(r,'narrador/entradas/estado.yaml',{'schema_estado_entradas':1,'natureza':'controle_reservado','candidatos':{'shen':{'estado':'latente','antecipado':False,'proxima_avaliacao':None,'historico_recente':[{'acao':'abrir_janela_contextual'}]}}})
    w(r,'runtime/contexto.yaml',{'personagem':{'nivel':6}})
    g=aliados_contextuais.gate(r,'shen')
    assert g['permitido'] and g['modo']=='avaliar_entrada_organica'
print('smoke aliados contextuais: OK')
