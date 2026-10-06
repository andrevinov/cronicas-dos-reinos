"""Contrato de leitura do painel: operação, amostra, experiência e custo separados."""
from __future__ import annotations

from collections import Counter
import hashlib
import json

from ferramentas.experiencia_avaliacao import RUBRIC_VERSION, scoreable

VERSION = "1.1.0"
EVALUATOR_FILES = {"analisar-rollout.py", "_analisar_rollout_core.py", "resultados_operacoes.py",
                   "atividades_modulares.py", "experiencia_avaliacao.py", "entrada_medicao.py",
                   "interacoes_narrativas.py", "gerar-avaliacao-sessao.py", "apresentacao_avaliacao.py", "revisao_sessao.py"}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()


def quality_state(assessments):
    verified = [x for x in assessments if scoreable(x) and
                (x.get("review") or {}).get("verification") == "verificada"]
    if any("violado" in (x.get("review") or {}).get("guardrails", {}).values() for x in verified):
        return "violacao_critica"
    if any(x.get("quality") == "inadequada" for x in verified):
        return "inadequada_no_criterio"
    if not assessments:
        return "nao_avaliada"
    if not verified:
        return "fontes_insuficientes"
    if all(x.get("eligibility") == "nao" and x.get("activation") == "ausente" for x in verified):
        return "negativa_valida"
    if not any(x.get("quality") in {"adequada", "inadequada"} for x in verified):
        return "fontes_insuficientes"
    return "amostra_insuficiente_para_generalizar"


def publish(scorecard, rows, ledger, report, versions, provenance, catalog):
    """Publica somente recortes verificados; nunca transforma média operacional em qualidade."""
    assessments = ledger.get("quality_assessments") or []
    frames = (ledger.get("experience_review") or {}).get("frames") or []
    total = sum(len(x.get("criteria") or {}) for x in frames)
    states = Counter(c.get("state", "nao_avaliada") for f in frames
                     for c in (f.get("criteria") or {}).values())
    covered = sum(bool(c.get("assessment_id")) for f in frames
                  for c in (f.get("criteria") or {}).values())
    verified = sum(scoreable(x) and (x.get("review") or {}).get("verification") == "verificada"
                   for x in assessments)
    incomplete = (scorecard.get("conclusao_medicao", {}).get("permitida") is not True or
                  scorecard.get("agregacao_modular", {}).get("conclusao_permitida") is not True)
    critical = scorecard.get("violacoes_criticas") or []
    scorecard["nota_operacional_parcial_0a100"] = scorecard.get("nota_geral_0a100")
    scorecard["nota_geral_0a100"] = None
    scorecard["faixa_geral"] = "comprometida" if critical else "sem_conclusao_global"
    scorecard["apresentacao"] = {
        "schema": 1, "versao": VERSION,
        "validade": "comprometida_guardrail" if critical else "incompleta" if incomplete else "operacao_observavel",
        "qualidade": quality_state(assessments), "conclusao_global_permitida": False,
        "nota_global_publicavel": None,
        "cobertura": {"unidades_interacao_criterio": total, "com_parecer": covered,
                      "sem_parecer": total - covered, "confirmadas_verificadas": verified,
                      "estados": dict(states)},
        "regra": "Parecer local não aprova o sistema. Sem cobertura e estabilidade, nenhuma média global conclusiva.",
    }
    all_turns = report.get("all_turns") or {}
    scorecard["operacoes_recorte_completo"] = {key: all_turns.get(key) for key in (
        "turns", "tool_calls", "input_tokens", "output_tokens", "attempted_write_calls",
        "successful_write_calls", "failed_write_calls", "unknown_write_calls", "write_target_touches")}
    workflow = (ledger.get("experience_review") or {}).get("workflow")
    if workflow:
        scorecard["revisao_semantica"] = workflow
    parent_tokens = sum(x.get("total_tokens", 0) for x in ledger.get("module_parent_costs") or [])
    narration_tokens = sum((report.get("narration_turns") or {}).get(k, 0)
                           for k in ("input_tokens", "output_tokens"))
    scorecard["custos"] = {
        "unidade": "tokens", "escopo": "inferencias_dos_turnos_narrativos",
        "observado": narration_tokens, "compartilhado_alocado": parent_tokens,
        "diferenca_fechamento": narration_tokens - parent_tokens,
        "exclusivo_observado": None, "marginal": None, "estimativa_causal": False,
        "regra": "Rateio contábil entre pais, uma vez. Exposição de subcapacidades não é somável. Contexto nativo não identifica custo exclusivo ou marginal.",
    }
    catalog_by_id = {x["id"]: x for x in catalog["modulos"]}
    evaluator = {k: v for k, v in versions.items() if k != "catalogo_modulos"}
    evaluator_code = {k: v for k, v in provenance.get("codigo_sha256", {}).items()
                      if k.rsplit("/", 1)[-1] in EVALUATOR_FILES}
    for row in rows:
        module_id = row["modulo"]
        local = [x for x in assessments if x.get("module_id") == module_id]
        verified_local = [x for x in local if scoreable(x) and
                          (x.get("review") or {}).get("verification") == "verificada"]
        unit_states = [c for f in frames for key, c in (f.get("criteria") or {}).items()
                       if key.startswith(module_id + ".")]
        opportunities = Counter(c.get("opportunity", "indeterminada") for c in unit_states)
        row["leitura_experiencia"] = {
            "estado": quality_state(local), "unidades": len(unit_states),
            "com_parecer": sum(bool(c.get("assessment_id")) for c in unit_states),
            "confirmadas_verificadas": len(verified_local),
            "pendencias": len(unit_states) - len(verified_local),
            "elegiveis": opportunities["atendida"] + opportunities["omitida"],
            "atendidas": opportunities["atendida"], "omitidas": opportunities["omitida"],
            "negativas_validas": opportunities["negativa_valida"],
            "indeterminadas": opportunities["indeterminada"],
            "assessment_ids": [x["assessment_id"] for x in local],
        }
        row["custo"] = {"unidade": "tokens", "escopo": "inferencias_dos_turnos_narrativos",
                        "compartilhado_alocado": row.get("tokens_totais_atribuidos_fracionados"),
                        "exclusivo_observado": None, "marginal": None, "estimativa_causal": False}
        # A implementação vem do recibo histórico. A régua vem da entrada desta revisão.
        definition = catalog_by_id[module_id]
        row["versao_avaliador_revisao"] = definition["versao_avaliacao"]
        row["comparabilidade"] = {
            "qualidade": digest({"implementacao": row["versao_implementacao"],
                                 "avaliacao_executada": row["versao_avaliacao"],
                                 "avaliador": evaluator, "avaliacao_revisao": definition["versao_avaliacao"],
                                 "codigo": evaluator_code,
                                 "criterios": [c.get("contrato_objetivo") for c in definition.get("subcapacidades", [])],
                                 "contratos": provenance.get("contratos_modulos", {}).get(module_id),
                                 "metas": provenance.get("snapshots", {}).get("metas"),
                                 "unidade": "interacao_criterio", "publicacao": VERSION}),
            "custo": digest({"implementacao": row["versao_implementacao"], "avaliador": evaluator,
                              "codigo": evaluator_code,
                              "escopo": "inferencias_dos_turnos_narrativos",
                              "unidade": "tokens", "atribuicao": "rateio_pais",
                              "recorte_equivalente": {"turnos": (report.get("narration_turns") or {}).get("turns"),
                                                       "inferencias": (report.get("narration_turns") or {}).get("inference_events")}}),
        }
    return scorecard["apresentacao"]


def index_view(manifest, scorecard, rows):
    """Entrada leve de série. Ausência de validade explícita nunca autoriza comparação."""
    presentation = scorecard.get("apresentacao") or {}
    result = {"apresentacao": presentation, "revisao": manifest.get("revisao"),
            "versoes": manifest.get("versoes"), "versoes_modulos": manifest.get("versoes_modulos"),
            "conclusao_medicao": scorecard.get("conclusao_medicao"),
            "agregacao_modular": scorecard.get("agregacao_modular"),
            "series_modulos": [{"module_id": x["modulo"], "comparabilidade": x.get("comparabilidade"),
                                 "estado": x.get("leitura_experiencia", {}).get("estado", "nao_avaliada"),
                                 "qualidade": x.get("nota_qualidade_interacao_0a100"),
                                 "custo": x.get("custo"),
                                 "guardrail": bool(x.get("violacoes_guardrail_experiencia"))}
                                for x in rows]}
    if manifest.get("serie_avaliacao") == "modules-v2":
        result["nota_operacional_parcial_0a100"] = scorecard.get("nota_operacional_parcial_0a100", scorecard.get("nota_geral_0a100"))
        result["nota_geral_0a100"] = None
        result["faixa_geral"] = "comprometida" if scorecard.get("violacoes_criticas") else "sem_conclusao_global"
    return result
