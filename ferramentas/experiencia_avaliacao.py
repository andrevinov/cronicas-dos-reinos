"""Revisão pós-hoc com fontes do instante; nunca consulta o save atual.

Regras determinísticas têm escopo limitado. Demais critérios exigem parecer
semântico vinculado à entrada, contexto e resposta final, não a um recibo.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any

import yaml

VERSION = "1.2.0"
RUBRIC_VERSION = "objetivos-jogo/1.0.0"
DIAGNOSES = {"extracao_avaliacao", "comportamento_modulo", "instrucao_dado", "limitacao_fonte"}
CAUSAL_STAGES = {"causa", "elegibilidade", "selecao", "contexto", "narracao", "persistencia", "recuperacao", "medicao", "indeterminada"}


def digest(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def criteria(catalog: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {s["contrato_objetivo"]["criterio_id"]: s["contrato_objetivo"]
            for m in catalog["modulos"] for s in m["subcapacidades"] if s.get("contrato_objetivo")}


def frames(turns, catalog, visible, operations, source_sha256=None):
    """Devolve descritores exportáveis e textos efêmeros para verificar citações.

    OBS identifica uma observação sem inventar interação canônica. Saídas só
    entram após sucesso observado e antes da resposta. Contexto reservado não
    é exportado. A completude é local, nunca um snapshot integral do mundo.
    """
    public, private, previous, history, tool_history = [], {}, None, [], []
    objectives = criteria(catalog)
    for turn in turns:
        response = visible(turn)
        inputs = turn.get("user_messages") or []
        if not inputs and not response:
            continue
        input_text = "\n".join(inputs)
        text = str((response or {}).get("text") or "")
        refs = re.findall(r"\bS\d{3,}-I\d{4,}\b", text)
        # Feedback OFF mencionando outra interação não é resposta daquela interação.
        ref = refs[-1] if refs and ("RODAPE_CANONICO" in text or not text.strip().startswith("[")) else None
        key = ref or "OBS-" + digest(str(turn.get("turn_id")))[:20]
        sources = {}

        def source(kind, body, visibility="publica", suffix=None):
            locator = f"{key}/{suffix or kind}"
            sources[locator] = {"locator": locator, "kind": kind, "text": body,
                                "sha256": digest(body), "visibility": visibility}
            return locator

        source("input", input_text)
        source("response", text)
        if previous:
            source("prior_response", previous["text"])
        for old_ref, old_text in history:
            source("historical_response", old_text, suffix="history/" + old_ref)
        # A revisão precisa comparar com o contexto realmente entregue antes,
        # incluindo estado, capacidades e promessas de turnos anteriores.
        for old_locator, old_source in tool_history:
            loc = source("historical_" + old_source["kind"], old_source["text"],
                         "reservada", "history-source/" + old_locator)
            sources[loc]["available_before_response"] = old_source["available_before_response"]
        op_descriptors, contexts = [], []
        for op in operations(turn):
            op_id = str(op.get("operation_id"))
            cmd = str(op.get("command") or "")
            output = str(op.get("output_text") or "")
            output_line = op.get("output_line")
            response_line = (response or {}).get("source_line")
            in_time = not (output_line and response_line and output_line > response_line)
            command_loc = source("command", cmd, "reservada", op_id + "/command")
            sources[command_loc]["available_before_response"] = not (op.get("command_line") and response_line and op["command_line"] > response_line)
            loc = source("output", output, "reservada", op_id + "/output")
            sources[loc]["available_before_response"] = in_time
            op_descriptors.append({"operation_id": op_id, "command_sha256": digest(cmd),
                                   "output_sha256": digest(output), "success": op.get("output_success"),
                                   "available_before_response": in_time})
            if op.get("output_success") is True and in_time and re.search(
                r"(?:contexto\.py|endpoints\.py)\s+(?:cena|retomada)\b", cmd
            ):
                contexts.append((loc, output))
        # A operação normalizada pode conter um template sem os valores do
        # payload, ou perder saídas de um lote cuja correlação é desconhecida.
        # Conservar o envelope nativo permite revisar essas fontes sem inferir
        # execução/sucesso dos comandos internos nem executar JavaScript.
        for call in turn.get("calls") or []:
            parent = str(call.get("call_id") or call.get("parent_call_id") or "")
            if not parent:
                continue
            related = [op for op in op_descriptors if parent in op["operation_id"]]
            for kind, field in (("native_tool_input", "raw_input"), ("native_tool_output", "output_text")):
                body = call.get(field)
                if not isinstance(body, str) or not body:
                    continue
                loc = source(kind, body, "reservada", "native/" + parent + "/" + kind)
                sources[loc]["available_before_response"] = all(op["available_before_response"] for op in related)
        descriptor = {"evaluation_ref": key, "interaction_ref": ref,
                      "source_cut_sha256": source_sha256, "rubric_sha256": digest(objectives),
                      "class": "OFF" if input_text.strip().startswith("[") and input_text.strip().endswith("]") and "RODAPE_CANONICO" not in text else "ON",
                      "turn_id": str(turn.get("turn_id")), "input_sha256": digest(input_text),
                      "response_sha256": digest(text) if response else None,
                      "sources": [{k: v for k, v in s.items() if k != "text"} for s in sources.values()],
                      "operations": op_descriptors,
                      "complete": bool(inputs and response and (not ref or refs.count(ref) == 1)),
                      "historical_context": "fontes_entregues_no_instante_snapshot_integral_nao_presumido"}
        descriptor["frame_sha256"] = digest(descriptor)
        descriptor["criteria"] = {criterion: {"state": "indeterminada", "opportunity": "indeterminada",
                                               "reason": "Fontes e parecer por critério necessários; execução não aprova experiência."}
                                  for criterion in objectives}
        public.append(descriptor)
        private[key] = {"descriptor": descriptor, "sources": sources, "contexts": contexts}
        tool_history.extend((loc, dict(value)) for loc, value in sources.items()
                            if value["kind"] in {"native_tool_input", "native_tool_output"})
        if response and not input_text.strip().startswith("["):
            previous = {"text": text}
        if response and ref:
            history.append((ref, text))
    return public, private


def evidence(source: dict[str, Any], quote: str, observation: str | None = None):
    start = source["text"].find(quote)
    if not quote or start < 0:
        raise ValueError("citação literal não pertence à fonte")
    return {"source": "interaction" if source["kind"] in {"input", "response", "prior_response"} else "rollout",
            "locator": source["locator"], "observation": observation or quote,
            "visibility": source["visibility"], "source_sha256": source["sha256"],
            "start": start, "end": start + len(quote), "literal": quote, "literal_sha256": digest(quote)}


def review(frame, identity="regras-deterministicas-poshoc", uncertainty="", conflicts=None, diagnosis=None):
    return {"schema": 1, "reviewer_role": "revisor_poshoc", "rubric_version": RUBRIC_VERSION,
            "configuration": {"engine": VERSION, "mode": "poshoc_fontes_congeladas", "reviewer": identity},
            "frame_sha256": frame["descriptor"]["frame_sha256"], "uncertainty": uncertainty,
            "dependency_operation_ids": [],
            "guardrails": {},
            "conflicts": conflicts or [], "diagnosis": diagnosis,
            "independence": "revisao_separada_do_produtor_nao_equivale_a_validacao_cega_por_terceiro"}


def _context(text):
    # Só uma consulta de cena com campos factuais; não interpreta prosa, ticket ou
    # afirmação do módulo avaliado como gabarito. Wrappers do executor são ignorados.
    match = re.search(r"(?m)^consulta: cena\s*$", text)
    if not match:
        return None
    try:
        data = yaml.safe_load(text[match.start():])
    except yaml.YAMLError:
        return None
    return data if isinstance(data, dict) else None


def deterministic_assessments(private):
    """Avalia a obrigação explícita de aviso, quando todos os gates são factuais.

    Não generaliza silêncio para omissão. Sem conteúdo exigido/resultado literal,
    percepção, presença, canal ou impedimentos completos, aguarda revisão.
    """
    result = []
    for ref, frame in private.items():
        if not frame["descriptor"]["complete"] or frame["descriptor"]["class"] == "OFF":
            continue
        response = frame["sources"][ref + "/response"]
        for loc, output in frame["contexts"]:
            data = _context(output)
            if not data or not isinstance(data.get("elenco_presente"), list):
                continue
            actors = [k.removeprefix("objetivo_") for k in data if k.startswith("objetivo_")]
            if len(actors) != 1:
                continue  # compromisso sem ator/precedência inequívocos exige revisão
            for actor in actors:
                required = {"compromisso_vencido", "canal", "impedimentos", "conhecimento_" + actor,
                            "objetivo_" + actor}
                if not required <= data.keys() or not isinstance(data["impedimentos"], list):
                    continue
                # Adapter de obrigação de aviso, não heurística de toda iniciativa.
                if data["compromisso_vencido"] != "transmitir_aviso_agora":
                    continue
                known = data["conhecimento_" + actor]
                if not isinstance(known, str) or not known or (known not in {"desconhecido", "apenas_narrador"} and not re.search(r"_confirmad[ao]$", known)):
                    continue
                if not str(data["objetivo_" + actor]).startswith("avisar_"):
                    continue
                eligible = actor in data["elenco_presente"] and data["canal"] == "conversa_presencial" and known not in {None, "desconhecido", "apenas_narrador"} and not data["impedimentos"]
                # Negativa explícita ou entrega explícita; linguagem não reconhecida
                # fica indeterminada, jamais aprovada por tamanho ou marcador.
                absent = re.search(r"\b(?:sem aviso|não (?:transmite|transmitiu|dá|deu) o aviso)\b", response["text"], re.I)
                present = re.search(rf"\b{re.escape(actor)}\s+(?:avisa|avisou|transmite o aviso)\b", response["text"], re.I)
                if bool(absent) == bool(present):
                    continue
                activation = "ausente" if absent else "presente"
                diagnosis = None
                if eligible and absent:
                    diagnosis = {"category": "comportamento_modulo", "finding": "Obrigação social alcançável não chegou à resposta.",
                                 "correction": "Carregar compromisso vencido com percepção e canal na seleção de iniciativa; silêncio exige impedimento ou adiamento rastreável.",
                                 "test": "Manter os mesmos comandos e gates; retirar o aviso deve criar omissão, entregá-lo deve eliminá-la."}
                quote = (absent or present).group(0)
                result.append({"schema_quality_assessment": 1,
                               "assessment_id": "opportunity-" + digest([ref, loc, actor])[:20],
                               "interaction_ref": ref, "module_id": "npc_continuity_and_social_behavior",
                               "capability_id": "social_initiative", "criterion_id": "npc_continuity_and_social_behavior.social_initiative",
                               "evaluator": "regras-deterministicas-poshoc", "eligibility": "sim" if eligible else "nao",
                               "activation": activation, "quality": "nao_aplicavel" if absent else "indeterminada",
                               "evidence": [evidence(frame["sources"][loc], output[output.index("consulta:"):]), evidence(response, quote)],
                               "adjudication": {"state": "confirmada", "reason": "Gates factuais de presença, percepção, compromisso, canal e impedimentos; resultado explícito na resposta final."},
                               "review": review(frame, diagnosis=diagnosis)})
    return result


def verify_reviews(assessments, private):
    """Revalida inclusive pareceres exportados: hashes + offsets, sem confiar
    no campo 'verificado' trazido pelo próprio arquivo. Conflito absteve-se.
    """
    result = copy.deepcopy(assessments)
    for item in result:
        meta = item.get("review")
        if meta is None:  # compatibilidade explícita, não é confirmação AMV-04
            continue
        frame = private.get(item.get("interaction_ref"))
        if not frame or meta.get("schema") != 1 or meta.get("frame_sha256") != frame["descriptor"]["frame_sha256"]:
            raise ValueError("parecer sem vínculo ao recorte efetivamente avaliado")
        if meta.get("rubric_version") != RUBRIC_VERSION or not isinstance(meta.get("configuration"), dict) or not meta["configuration"]:
            raise ValueError("parecer exige versão de rubrica e configuração")
        if not isinstance(meta.get("uncertainty"), str) or not isinstance(meta.get("conflicts"), list):
            raise ValueError("parecer exige incerteza e conflitos explícitos")
        if any(not isinstance(conflict, str) for conflict in meta["conflicts"]):
            raise ValueError("conflitos precisam de descrição literal")
        if meta["configuration"].get("reviewer") != item.get("evaluator"):
            raise ValueError("revisor diverge da configuração registrada")
        kinds = set()
        future_source = False
        for ev in item.get("evidence") or []:
            source = frame["sources"].get(ev.get("locator"))
            if not source or ev.get("source_sha256") != source["sha256"]:
                raise ValueError("evidência não pertence às fontes históricas do recorte")
            start, end = ev.get("start"), ev.get("end")
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(source["text"]):
                raise ValueError("citação exige offsets válidos")
            literal = source["text"][start:end]
            if digest(literal) != ev.get("literal_sha256") or (ev.get("literal") != literal and ev.get("literal") != "sha256:" + digest(literal)):
                raise ValueError("citação literal divergente da fonte")
            if ev.get("visibility") != source["visibility"]:
                raise ValueError("evidência não pode promover fonte reservada a pública")
            kinds.add(source["kind"])
            future_source |= source.get("available_before_response") is False
        diagnosis = meta.get("diagnosis")
        if diagnosis is not None and (not isinstance(diagnosis, dict) or diagnosis.get("category") not in DIAGNOSES or not all(diagnosis.get(k) for k in ("finding", "correction", "test"))):
            raise ValueError("achado exige categoria, diagnóstico, correção e teste")
        if diagnosis and "stage" in diagnosis and diagnosis["stage"] not in CAUSAL_STAGES:
            raise ValueError("estágio causal inválido")
        if diagnosis and "cause_status" in diagnosis and diagnosis["cause_status"] not in {"hipotese", "confirmada_por_reproducao"}:
            raise ValueError("estado da hipótese causal inválido")
        # Texto público reservado é derivado por export_assessment, nunca aceito
        # de um arquivo de pareceres que poderia promover seu próprio segredo.
        meta.pop("public_diagnosis", None)
        if item.get("adjudication", {}).get("state") == "confirmada" and not {"input", "response"} <= kinds and item.get("evaluator") != "regras-deterministicas-poshoc":
            raise ValueError("revisão semântica confirmada exige intenção e resposta final literais")
        dependencies = meta.get("dependency_operation_ids")
        if not isinstance(dependencies, list):
            raise ValueError("parecer exige dependências operacionais explícitas")
        operations = {op["operation_id"]: op for op in frame["descriptor"]["operations"]}
        if any(op not in operations for op in dependencies):
            raise ValueError("parecer aponta dependência operacional inexistente")
        guardrails = meta.get("guardrails")
        if not isinstance(guardrails, dict) or any(value not in {"ok", "violado", "indeterminada", "nao_aplicavel"} for value in guardrails.values()):
            raise ValueError("parecer exige guardrails explícitos com estados válidos")
        unknown_guardrails = set(guardrails) - {"player_agency", "knowledge_secrecy", "roll_integrity", "canonical_consistency"}
        if unknown_guardrails:
            raise ValueError("guardrail inexistente")
        blocked = (not frame["descriptor"]["complete"] or future_source or bool(meta["conflicts"]) or meta.get("reviewer_role") != "revisor_poshoc" or
                   any(operations[op]["success"] is not True or not operations[op]["available_before_response"] for op in dependencies))
        meta["verification"] = "verificada" if not blocked else "bloqueada"
        if blocked:
            item["adjudication"] = {"state": "indeterminada", "reason": "Corte incompleto, conflito ou autoavaliação do produtor; fora do denominador."}
    return result


def export_assessment(item):
    result = copy.deepcopy(item)
    reserved = False
    for ev in result["evidence"]:
        if ev["visibility"] == "reservada":
            reserved = True
            for key in ("observation", "literal"):
                value = ev.get(key)
                if value and not value.startswith("sha256:"):
                    ev[key] = "sha256:" + digest(value)
    # Localizador opaco é necessário para revalidar sem revelar o conteúdo.
    if reserved and result.get("review"):
        meta = result["review"]
        if meta.get("decision_state") and meta.get("diagnosis"):
            # Texto por estados públicos; não promove a justificativa privada.
            stage = meta["diagnosis"].get("stage", "indeterminada")
            corrections = {
                "persistencia": "Conferir a transação que deveria registrar o efeito e sua recuperação sem duplicação.",
                "recuperacao": "Conferir se a memória persistida foi recuperada e entregue à cena posterior.",
                "narracao": "Confrontar fatos e obrigações entregues ao narrador com a resposta final visível.",
                "contexto": "Conferir quais fatos relevantes foram entregues ao narrador e quais ficaram ausentes.",
                "selecao": "Conferir a seleção da causa alcançável e a justificativa de eventual adiamento.",
            }
            meta["public_diagnosis"] = {
                "finding": ("Fontes insuficientes para concluir este critério."
                            if meta["decision_state"] == "fontes_insuficientes"
                            else "Oportunidade elegível omitida da resposta."
                            if result["eligibility"] == "sim" and result["activation"] == "ausente"
                            else "Resultado inadequado no critério avaliado."),
                "correction": corrections.get(stage, "Rastrear causa, elegibilidade, decisão, contexto entregue, prosa e persistência para localizar a falha."),
                "test": "Comparar episódios com os mesmos fatos e operações, incluindo o efeito adequado, sua omissão e uma negativa legítima.",
            }
        for key in ("uncertainty", "conflicts"):
            if meta.get(key):
                meta[key] = ((meta[key] if meta[key].startswith("sha256:") else "sha256:" + digest(meta[key]))
                             if key == "uncertainty" else [x if x.startswith("sha256:") else "sha256:" + digest(x) for x in meta[key]])
        diagnosis = meta.get("diagnosis")
        if diagnosis:
            for key in ("finding", "correction", "test"):
                if not diagnosis[key].startswith("sha256:"):
                    diagnosis[key] = "sha256:" + digest(diagnosis[key])
        result["adjudication"]["reason"] = "Revisão de fontes do instante; conteúdo reservado protegido. Evidência revalidável por hash e offsets."
    return result


def scoreable(item):
    meta = item.get("review")
    return item.get("adjudication", {}).get("state") == "confirmada" and (meta is None or (meta.get("verification") == "verificada" and not meta.get("conflicts")))


def summarize(public, assessments):
    result = copy.deepcopy(public)
    by_ref = {x["evaluation_ref"]: x for x in result}
    for item in assessments:
        frame = by_ref.get(item["interaction_ref"])
        if not frame or item["criterion_id"] not in frame["criteria"]:
            continue
        eligibility, activation = item["eligibility"], item["activation"]
        opportunity = "indeterminada"
        if scoreable(item):
            if eligibility == "sim" and activation in {"presente", "ausente"}:
                opportunity = "atendida" if activation == "presente" else "omitida"
            elif eligibility == "nao" and activation == "ausente":
                opportunity = "negativa_valida"
            elif eligibility == "nao" and activation == "presente":
                opportunity = "sobreativacao"
        frame["criteria"][item["criterion_id"]] = {"state": item["adjudication"]["state"], "opportunity": opportunity,
                                                   "quality": item["quality"] if scoreable(item) else "indeterminada",
                                                   "assessment_id": item["assessment_id"]}
    return {"schema": 1, "engine_version": VERSION, "rubric_version": RUBRIC_VERSION, "frames": result,
            "regra": "Operações e recibos não aprovam experiência; fontes insuficientes, conflitos e autoavaliação ficam fora do denominador."}
