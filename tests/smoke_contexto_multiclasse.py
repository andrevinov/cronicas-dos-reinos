from __future__ import annotations

import sys
import tempfile
from pathlib import Path
import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
sys.path.insert(0, str(TOOLS))

import contexto_cena


def write(repo: Path, rel: str, value) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")


with tempfile.TemporaryDirectory() as tmp:
    repo = Path(tmp)
    # Usa o roteador real da fase 6 e um contrato mínimo coerente com seus alvos.
    target = repo / contexto_cena.ROUTER
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((ROOT / contexto_cena.ROUTER).read_bytes())

    write(repo, "narrador/arcos/index.yaml", {
        "schema_arcos": 1, "natureza": "roteador_reservado",
        "arcos": {"parte_1": {"titulo": "Parte 1", "ordem": 1, "arquivo": "narrador/arcos/parte_1.yaml", "proximo": None}},
    })
    write(repo, "narrador/arcos/estado.yaml", {
        "schema_estado_arcos": 2, "natureza": "controle_reservado", "arco_atual": "parte_1", "estado": "ativo", "historico_transicoes": [],
    })
    write(repo, "narrador/arcos/parte_1.yaml", {
        "schema_arco": 4, "natureza": "reservado", "estatuto": "contrato_orquestrador_de_arco", "id": "parte_1", "titulo": "Parte 1", "principio": "smoke",
        "inicio": {"tipo": "fato_canonico", "marcador": "inicio", "fonte": "campanha.yaml"},
        "termino": {"tipo": "marco_explicito", "marcador": "fim", "fonte": "campanha.yaml"},
        "orquestracao": {"fontes": {"plano": {"tipo": "documento_reservado", "arquivo": "narrador/masao/plano.md"}}, "plano_mestre": {"agente": "masao_hirasawa", "objetivo": "objetivo", "referencia": "plano"}},
        "habilitacoes": {"politica_nao_listados": "bloqueados", "antagonistas": ["kajiwara_shizune"], "aliados": [], "direcoes": ["ponte_de_kozakura"]},
        "linhas_operacionais": {
            "impedir_consolidacao_de_provas": {"objetivo": "impedir_provas", "executores": ["kajiwara_shizune"], "referencia": "plano"},
            "mapear_rede_de_apoio_de_ren": {"objetivo": "mapear_rede", "executores": ["kajiwara_shizune"], "referencia": "plano"},
            "proteger_cadeia_logistica": {"objetivo": "logistica", "executores": ["masao_hirasawa"], "referencia": "plano"},
            "preservar_monopolio_da_ponte": {"objetivo": "ponte", "executores": ["masao_hirasawa"], "referencia": "plano"},
        },
    })
    write(repo, "narrador/arcos/marcos-aparicao.yaml", {
        "schema_marcos_aparicao": 1, "natureza": "roteador_reservado",
        "fonte_canonica": "narrador/juppongatana/marcos-de-aparicao.md",
        "regras": {"elegivel_nao_e_aparicao": True, "consumido_nao_bloqueia_reaparicao": True},
        "marcos": {
            "kajiwara_shizune": {"arco": "parte_1", "grupo": "antagonistas", "nivel_minimo": 6, "secao_fonte": "### Kajiwara Shizune", "condicao_id": "institucional"}
        },
    })
    write(repo, "narrador/arcos/estado-marcos-aparicao.yaml", {
        "schema_estado_marcos_aparicao": 1, "natureza": "controle_reservado",
        "marcos": {"kajiwara_shizune": {"estado": "elegivel", "origem": "smoke", "nota": "ok", "historico_recente": []}},
    })
    write(repo, "runtime/contexto.yaml", {"personagem": {"nivel": 6}})
    write(repo, "narrador/agentes/index.yaml", {
        "schema_agentes": 2, "natureza": "reservado", "agentes": {
            "kajiwara_shizune": {"nome": "Kajiwara Shizune", "estado": "ativo", "presenca": "indeterminado", "atuacao_local": "exige_presenca_fisica"},
            "masao_hirasawa": {"nome": "Masao Hirasawa", "estado": "ativo", "presenca": "indeterminado", "atuacao_local": "permite_rede"},
        },
    })
    write(repo, "narrador/direcoes/estado.yaml", {
        "schema_estado_direcoes": 1, "natureza": "controle_reservado", "direcoes": {
            "ponte_de_kozakura": {"estado": "ativa", "marco_atual": "coisas_plausiveis", "marcos_concluidos": [], "historico_recente": []}
        },
    })

    result = contexto_cena.select_candidates(
        repo, ["documentos", "escrituracao", "registros"], scene_id="s009:tomas-escritorio"
    )
    assert [x["id"] for x in result["presencas"]] == ["kajiwara_shizune"]
    assert [x["id"] for x in result["operacoes"]] == ["impedir_consolidacao_de_provas"]
    assert [x["id"] for x in result["direcoes"]] == ["ponte_de_kozakura"]
    assert result["direcoes"][0]["marco_atual"] == "coisas_plausiveis"
    assert len(result["fontes_lidas"]) <= 9
    assert result["presencas"][0]["marco_aparicao"]["estado"] == "elegivel"
    assert all("narrador/agentes/kajiwara_shizune.yaml" not in source for source in result["fontes_lidas"])

print("smoke descoberta contextual multiclasse: OK")
