from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import arcos

with tempfile.TemporaryDirectory() as tmp:
    repo = Path(tmp)
    def write(rel: str, value):
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, str):
            path.write_text(value, encoding="utf-8")
        else:
            path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    write("narrador/arcos/index.yaml", {
        "schema_arcos": 1, "natureza": "roteador_reservado",
        "arcos": {"parte_1": {"titulo": "Parte 1", "ordem": 1, "arquivo": "narrador/arcos/parte_1.yaml", "proximo": None}},
    })
    write("narrador/arcos/estado.yaml", {
        "schema_estado_arcos": 2, "natureza": "controle_reservado",
        "arco_atual": "parte_1", "estado": "ativo", "historico_transicoes": [],
    })
    write("narrador/arcos/parte_1.yaml", {
        "schema_arco": 4, "natureza": "reservado", "estatuto": "contrato_orquestrador_de_arco",
        "id": "parte_1", "titulo": "Parte 1", "principio": "Teste.",
        "inicio": {"tipo": "fato_canonico", "marcador": "inicio", "fonte": "campanha.yaml"},
        "termino": {"tipo": "marco_explicito", "marcador": "fim", "fonte": "campanha.yaml"},
        "orquestracao": {
            "fontes": {"plano_mestre": {"tipo": "documento_reservado", "arquivo": "narrador/masao/plano.md"}},
            "plano_mestre": {"agente": "masao", "objetivo": "objetivo", "referencia": "plano_mestre"},
        },
        "habilitacoes": {"politica_nao_listados": "bloqueados", "antagonistas": ["kurobane"], "aliados": [], "direcoes": []},
        "linhas_operacionais": {"proteger_prova": {"objetivo": "proteger_prova", "executores": ["kurobane"], "referencia": "plano_mestre"}},
    })
    write("narrador/agentes/index.yaml", {
        "schema_agentes": 2, "agentes": {
            "masao": {"nome": "Masao", "arquivo": "narrador/agentes/masao.yaml"},
            "kurobane": {"nome": "Kurobane", "arquivo": "narrador/agentes/kurobane.yaml"},
        },
    })
    write("narrador/agentes/masao.yaml", {"id": "masao"})
    write("narrador/agentes/kurobane.yaml", {
        "id": "kurobane",
        "metodos_operacionais": {"proteger_prova": [{
            "id": "interceptar", "abordagem": "Interceptar fisicamente.",
            "modalidade": "fisica", "tags": ["documentos", "mensageiro"],
        }]},
    })
    write("narrador/entradas/index.yaml", {"schema_entradas": 1, "candidatos": {}})
    write("narrador/direcoes/index.yaml", {"schema_direcoes": 1, "direcoes": {}})
    write("campanha.yaml", "campanha: teste\n")
    write("narrador/masao/plano.md", "# Plano\n")

    result = arcos.resolve_agent_methods(repo, "proteger_prova", executor="kurobane")
    assert result["metodos"][0]["id"] == "interceptar"
    assert len(result["fontes_lidas"]) == 5
    assert result["fonte_agente"] == "narrador/agentes/kurobane.yaml"

print("smoke arcos/linha/métodos: OK")
