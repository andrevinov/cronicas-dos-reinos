"""Sondas determinísticas em fixtures temporárias, não uma simulação de narrador.

Mede a saída de componentes reais. Não converte tamanho em tokens e não usa um
roteador aprovado como prova de que um inimigo executou seu plano na ficção.
"""
from __future__ import annotations

import copy
import json
import tempfile
from pathlib import Path

import yaml

from benchmark_narrativo import CATALOG, ROOT, canonical, catalog, digest

SOURCES = ("contexto.py", "contexto_core.py", "compromissos.py", "transacoes.py",
           "agentes_leves.py", "pressao_narrativa.py", "retomada_cronica.py")


def _yaml(repo: Path, path: str, value) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _snapshot(repo: Path) -> dict:
    return {p.relative_to(repo).as_posix(): digest(p.read_bytes())
            for p in repo.rglob("*") if p.is_file()}


def _base(repo: Path) -> None:
    _yaml(repo, "estado/relacoes/index.yaml", {"relacoes": {"lia": {
        "nome": "Lia", "arquivo": "estado/relacoes/lia.yaml"}}})
    _yaml(repo, "estado/npcs/index.yaml", {"npcs": {}})
    _yaml(repo, "cenario/texturas/index.yaml", {"npcs": {}, "locais": {}})
    _yaml(repo, "estado/relacoes/lia.yaml", {"id": "lia", "relacao": {
        "nome": "Lia", "confianca": "baixa", "acordos": ["Ren prometeu devolver a bússola de Lia."]}})
    context = {"sessao": {"numero": 1, "status": "em_sessao", "modo_de_cena": "conversa"},
               "personagem": {"nome": "Ren Kagehira"},
               "tempo": {"data": "14 Eleasis, 1372 DR", "hora_aproximada": "21:30"},
               "localizacao": {"area": "Oficina de Lia", "ponto_exato": "mesa dos mapas"},
               "recursos": {"pv": {"atuais": 10, "maximos": 10}, "focus": {"atuais": 2, "maximos": 2}}}
    _yaml(repo, "runtime/contexto.yaml", context)
    _yaml(repo, "runtime/cena.yaml", {"sessao": 1, "modo": "conversa", "tempo": context["tempo"],
                                      "localizacao": context["localizacao"]})
    (repo / "runtime/eventos-pendentes.jsonl").write_text("", encoding="utf-8")
    _yaml(repo, "estado/estado-atual.yaml", {"sentinela": "fixture isolada; não alterar cânone real"})


def _pending(repo: Path, deltas: list[dict]) -> None:
    record = {"versao": 1, "id": "benchmark-pendente", "sessao": 1,
              "resumo": "Ren devolveu o mapa intacto; Lia mantém o pedido da bússola.", "deltas": deltas}
    (repo / "runtime/eventos-pendentes.jsonl").write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")


def _measure(name: str, args: dict, output, checks: dict, readonly: bool) -> dict:
    text = output if isinstance(output, str) else yaml.safe_dump(output, allow_unicode=True, sort_keys=False)
    return {"componente": name, "argument_bytes": len(canonical(args)),
            "output_bytes": len(text.encode("utf-8")), "sha256_saida": digest(text.encode("utf-8")),
            "checagens_estruturais": checks, "somente_leitura": readonly}


def _context_probe(repo: Path, sid: str) -> list[dict]:
    import contexto
    import compromissos
    import retomada_cronica

    if sid == "reencontro_aliado":
        relation = {"nome": "Lia", "confianca": "moderada", "personalidade": "acolhedora e independente"}
        relation.update({f"contexto_secundario_{i}": "Anotação antiga de rotina da oficina. " * 28 for i in range(12)})
        relation["acordos"] = ["Ren prometeu devolver a bússola de Lia."]
        relation["momentos_de_vinculo"] = ["Lia abrigou Ren durante a tempestade."]
        _yaml(repo, "estado/relacoes/lia.yaml", {"id": "lia", "relacao": relation})
        before = _snapshot(repo)
        data = contexto.command_npc(repo, "lia")
        text, truncated = contexto.fit_budget(data, 8192, False)
        return [_measure("contexto.command_npc + fit_budget", {"npc": "lia", "max_bytes": 8192}, text,
                         {"promessa_visivel": relation["acordos"][0] in text,
                          "vinculo_visivel": relation["momentos_de_vinculo"][0] in text,
                          "teto_respeitado": len(text.encode("utf-8")) <= 8192,
                          "truncamento_sinalizado": truncated}, _snapshot(repo) == before)]
    if sid == "mudanca_confianca":
        _pending(repo, [{"alvo": "relacao:lia", "op": "set", "caminho": "confianca", "valor": "moderada"}])
        before = _snapshot(repo)
        data = contexto.command_relation(repo, "lia")
        return [_measure("contexto.command_relation", {"npc": "lia"}, data,
                         {"overlay_visivel": data["resultado"]["relacao"]["confianca"] == "moderada"},
                         _snapshot(repo) == before)]
    appointment = {"tipo": "encontro", "resumo": "Ren prometeu devolver a bússola de Lia.",
                   "envolvidos": ["ren", "lia"], "janela": {
                       "inicio": {"data": "14 Eleasis, 1372 DR", "hora": "21:20"},
                       "fim": {"data": "14 Eleasis, 1372 DR", "hora": "21:50"}}}
    _pending(repo, [compromissos.create_delta("bussola", appointment)])
    before = _snapshot(repo)
    if sid == "promessa_pendente":
        data = contexto.command_status(repo)
        items = data["resultado"].get("compromissos", {}).get("itens", {})
        return [_measure("contexto.command_status", {}, data,
                         {"promessa_em_janela": items.get("bussola", {}).get("situacao_temporal") == "em_janela"},
                         _snapshot(repo) == before)]
    data = retomada_cronica.current_snapshot(repo)
    again = retomada_cronica.current_snapshot(repo)
    return [_measure("retomada_cronica.current_snapshot", {}, data,
                     {"local_atual": data["agora"]["local"]["area"] == "Oficina de Lia",
                      "promessa_persistida": "bussola" in data.get("compromissos", {}).get("itens", {}),
                      "sem_transcricao": data["transcricao_lida"] is False,
                      "reconstrucao_estavel": data == again}, _snapshot(repo) == before),
            _measure("retomada_cronica.current_snapshot", {}, again,
                     {"sem_contexto_anterior_como_argumento": True}, _snapshot(repo) == before)]


def _initiative(repo: Path) -> list[dict]:
    import agentes_leves
    _yaml(repo, "estado/tempo.yaml", {"schema_tempo": 1, "natureza": "tempo_atual",
                                      "data_atual": "14 Eleasis, 1372 DR", "hora_aproximada": "21:30"})
    _yaml(repo, "narrador/mundo/estado.yaml", {"schema_estado_mundo": 1, "natureza": "controle_reservado",
                                             "processado_ate": {"data": "13 Eleasis, 1372 DR", "hora": "06:00"},
                                             "pendencias": [], "concluidas_recentes": []})
    agents, states = {}, {}
    for key in ("lia", "bor"):
        agents[key] = {"nome": key.title(), "perfil_operacional": "recorrente_leve", "estado": "ativo",
                       "prioridade": 2, "intervalo_dias": 3,
                       "inicio": {"data": "14 Eleasis, 1372 DR", "hora": "06:00"},
                       "arquivo": f"narrador/agentes-leves/{key}.yaml"}
        states[key] = {"estado": "ativo", "proxima_avaliacao": copy.deepcopy(agents[key]["inicio"])}
        _yaml(repo, f"narrador/agentes-leves/{key}.yaml", {
            "schema_agente_leve": 1, "natureza": "reservado", "id": key, "nome": key.title(),
            "perfil_operacional": "recorrente_leve",
            "rotina_padrao": {"descricao": "Trabalha na oficina.", "fonte": "fontes/canone.md", "evidencia": "Trabalha na oficina."},
            "objetivo_atual": {"descricao": "Busca ajuda para o transporte.", "fonte": "fontes/canone.md", "evidencia": "Busca ajuda para o transporte."},
            "iniciativas_possiveis": [{"descricao": "Pode procurar Ren na praça.", "fonte": "fontes/canone.md", "evidencia": "Pode procurar Ren na praça."}],
            "regra_de_reavaliacao": "Rotina é o padrão.", "fontes_canonicas": ["fontes/canone.md"]})
    (repo / "fontes").mkdir()
    (repo / "fontes/canone.md").write_text("Trabalha na oficina. Busca ajuda para o transporte. Pode procurar Ren na praça.\n", encoding="utf-8")
    _yaml(repo, "narrador/agentes-leves/index.yaml", {"schema_agentes_leves": 1, "natureza": "reservado",
          "orcamento": {"max_novas_por_checkpoint": 1, "max_pendencias_abertas": 2,
                        "ordenacao": "mais_atrasado_prioridade_id"}, "agentes": agents})
    _yaml(repo, "narrador/agentes-leves/estado.yaml", {"schema_estado_agentes_leves": 1,
                                                      "natureza": "controle_reservado", "agentes": states})
    sentinel = (repo / "estado/estado-atual.yaml").read_bytes()
    result = agentes_leves.process_checkpoint(repo)
    represented = set(result["agentes_leves_reconsiderar"]) | set(result["adiados_por_orcamento"])
    return [_measure("agentes_leves.process_checkpoint (não executa intenção)", {}, result,
                     {"devidos_nao_somem": represented == set(agents),
                      "sem_mutacao_publica": (repo / "estado/estado-atual.yaml").read_bytes() == sentinel}, False)]


def _fronts(repo: Path) -> list[dict]:
    import pressao_narrativa
    items = [{"id": "ponte", "tipo": "operacao_comprometida", "origem": "bor"},
             {"id": "deposito", "tipo": "operacao_comprometida", "origem": "ves"}]
    before = _snapshot(repo)
    result = pressao_narrativa.sort_items(items)
    return [_measure("pressao_narrativa.sort_items (roteamento, não execução)", {"items": items}, result,
                     {"duas_frentes_preservadas": {x["id"] for x in result} == {"ponte", "deposito"},
                      "ordem_estavel": result == pressao_narrativa.sort_items(list(reversed(items)))},
                     _snapshot(repo) == before)]


def probe(catalog_path: Path = CATALOG) -> dict:
    data = catalog(catalog_path)
    results = []
    for scenario in data["cenarios"]:
        sid = scenario["id"]
        with tempfile.TemporaryDirectory(prefix="cronica-benchmark-") as tmp:
            repo = Path(tmp)
            _base(repo)
            if sid == "iniciativa_fora_cena":
                samples = _initiative(repo)
            elif sid == "frentes_adversarias":
                samples = _fronts(repo)
            else:
                samples = _context_probe(repo, sid)
        results.append({"cenario": sid, "amostras": samples,
                        "qualidade_narrada": "nao_avaliada", "tokens_nativos": None})
    return {"schema_sondas_narrativas": 1, "natureza": "medicao_componentes_em_fixtures",
            "catalogo_sha256": digest(canonical(data)),
            "codigo_componentes_sha256": {p: digest((ROOT / "ferramentas" / p).read_bytes()) for p in SOURCES},
            "episodios": results,
            "totais": {"invocacoes_locais": sum(len(r["amostras"]) for r in results),
                       "argument_bytes": sum(s["argument_bytes"] for r in results for s in r["amostras"]),
                       "output_bytes": sum(s["output_bytes"] for r in results for s in r["amostras"]),
                       "tokens_nativos": None},
            "status": "DIAGNOSTICO_COMPONENTES_NAO_E_VEREDITO_NARRATIVO",
            "limites": ["Não executa uma IA nem mede tokens nativos.",
                        "Cadência e roteamento não provam execução de planos ou qualidade literária.",
                        "Nenhum dado de campanha é usado como fixture ou alterado."]}
