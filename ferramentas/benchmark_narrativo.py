#!/usr/bin/env python3
"""Benchmark pós-hoc de episódios completos; nunca é chamado pelo narrador.

Mantém três coisas distintas: sondas de componentes, revisão narrativa com
proveniência e tráfego nativo. Bytes não viram tokens; ausências não viram zero.
O analisador público schema 3 continua dono das classificações operacionais.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "tests/fixtures/narrative-benchmark-v1.json"
TOKEN_KEYS = ("input_tokens", "cached_input_tokens", "output_tokens", "reasoning_output_tokens")
CALL_TYPES = {"function_call", "custom_tool_call"}
OUTPUT_TYPES = {"function_call_output", "custom_tool_call_output"}
SCENARIOS = {"reencontro_aliado", "promessa_pendente", "mudanca_confianca",
             "iniciativa_fora_cena", "frentes_adversarias", "retomada_fria"}


class NarrativeBenchmarkError(ValueError):
    pass


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise NarrativeBenchmarkError(f"chave JSON duplicada: {key}")
        result[key] = value
    return result


def _parse(text: str) -> Any:
    try:
        return json.loads(text, object_pairs_hook=_unique,
                          parse_constant=lambda x: (_ for _ in ()).throw(
                              NarrativeBenchmarkError(f"número JSON inválido: {x}")))
    except json.JSONDecodeError as exc:
        raise NarrativeBenchmarkError(f"JSON inválido: {exc}") from exc


def load(path: Path) -> dict:
    value = _parse(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise NarrativeBenchmarkError(f"{path.name}: esperado objeto JSON")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise NarrativeBenchmarkError(message)


def catalog(path: Path = CATALOG) -> dict:
    data = load(path)
    require(data.get("schema") == 1 and data.get("natureza") == "cenario_sintetico_isolado",
            "catálogo deve declarar schema e isolamento")
    items = data.get("cenarios")
    require(isinstance(items, list) and all(isinstance(x, dict) for x in items), "cenários inválidos")
    ids = [x.get("id") for x in items]
    require(len(ids) == len(SCENARIOS) and set(ids) == SCENARIOS, "catálogo deve cobrir os seis episódios")
    for item in items:
        steps = item.get("passos", [])
        criteria = item.get("criterios", [])
        require(len(steps) >= 5 and all(isinstance(s, dict) and isinstance(s.get("entrada"), str)
                                      and s["entrada"].strip() for s in steps), "episódio exige cinco passos")
        require(bool(item.get("estado_inicial")), "episódio sem estado inicial")
        require(bool(criteria) and all(isinstance(c, dict) and c.get("id") and c.get("descricao")
                                      for c in criteria), "critérios ausentes")
        require(len({c["id"] for c in criteria}) == len(criteria), "critério duplicado")
    return data


def _text(payload: dict) -> str:
    parts = payload.get("content") or []
    if isinstance(parts, str):
        return parts
    return "".join(p if isinstance(p, str) else str(p.get("text") or p.get("output_text") or "")
                   for p in parts if isinstance(p, (dict, str)))


def _string(value: Any) -> str:
    return value if isinstance(value, str) else canonical(value).decode("utf-8")


def _read_records(path: Path) -> list[dict | None]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            records.append(None)  # conserva numeração física das evidências
            continue
        record = _parse(line)
        require(isinstance(record, dict) and isinstance(record.get("payload", {}), dict),
                "registro JSONL inválido")
        records.append(record)
    require(any(records), "rollout vazio")
    return records


def _native(records: list[dict | None]) -> dict:
    values = {key: [] for key in TOKEN_KEYS}
    active, metered, finished = set(), set(), set()
    current = None
    sessions, models, prompts = [], set(), []
    issues, seen_totals = [], {}
    call_ids, output_ids = set(), set()
    last_total = None
    events = duplicates = calls = outputs = input_bytes = output_bytes = words = compactions = 0
    for record in records:
        if record is None:
            continue
        kind, p = record.get("type"), record.get("payload", {})
        subtype = p.get("type")
        if kind == "session_meta":
            sessions.append(p.get("id") or p.get("session_id"))
        if kind == "turn_context":
            if p.get("model") or p.get("model_name"):
                models.add(p.get("model") or p.get("model_name"))
        if kind == "turn_context" or (kind == "event_msg" and subtype == "task_started"):
            current = p.get("turn_id") or current
        if kind == "compacted":
            compactions += 1
        if kind == "response_item":
            meta = p.get("internal_chat_message_metadata_passthrough") or {}
            turn = meta.get("turn_id") or current
            if subtype in CALL_TYPES | OUTPUT_TYPES or (subtype == "message" and p.get("role") == "assistant"):
                if turn:
                    active.add(turn)
                else:
                    issues.append("atividade_sem_turno")
            if subtype in CALL_TYPES:
                calls += 1
                cid = p.get("call_id") or p.get("tool_call_id")
                if not cid or cid in call_ids:
                    issues.append("chamada_sem_id_ou_id_duplicado")
                call_ids.add(cid)
                value = next((p[k] for k in ("arguments", "input", "params") if k in p), "")
                input_bytes += len(_string(value).encode("utf-8"))
            elif subtype in OUTPUT_TYPES:
                outputs += 1
                cid = p.get("call_id") or p.get("tool_call_id")
                if not cid or cid in output_ids or cid not in call_ids:
                    issues.append("resultado_sem_chamada_unica")
                output_ids.add(cid)
                value = next((p[k] for k in ("output", "content", "result") if k in p), "")
                output_bytes += len(_string(value).encode("utf-8"))
            elif subtype == "message" and p.get("role") == "user":
                text = _text(p)
                if text and not text.startswith("# AGENTS.md instructions"):
                    prompts.append(text)
            elif subtype == "message" and p.get("role") == "assistant" and p.get("channel") == "final":
                words += len(_text(p).split())
                if turn:
                    finished.add(turn)
        if kind == "event_msg" and subtype in {"task_complete", "task_completed"}:
            if p.get("turn_id") or current:
                finished.add(p.get("turn_id") or current)
        if kind != "event_msg" or subtype != "token_count":
            continue
        info = p.get("info") or {}
        usage = info.get("last_token_usage")
        if not isinstance(usage, dict) or not usage:
            issues.append("token_count_sem_uso")
            continue
        total = info.get("total_token_usage")
        if isinstance(total, dict) and total:
            key = canonical(total)
            if key in seen_totals:
                duplicates += 1
                if seen_totals[key] != canonical(usage):
                    issues.append("uso_divergente_para_mesmo_total")
                continue
            seen_totals[key] = canonical(usage)
            if last_total is not None:
                for field in TOKEN_KEYS:
                    a, b = last_total.get(field), total.get(field)
                    if type(a) is int and type(b) is int:
                        if b < a:
                            issues.append("contador_cumulativo_regrediu")
                        elif type(usage.get(field)) is int and b - a != usage[field]:
                            issues.append("lacuna_em_contadores_cumulativos")
            elif any(type(total.get(k)) is int and type(usage.get(k)) is int
                     and total[k] != usage[k] for k in ("input_tokens", "output_tokens")):
                issues.append("inicio_do_rollout_parcial")
            last_total = total
        events += 1
        if current:
            metered.add(current)
        else:
            issues.append("uso_sem_turno")
        for field in TOKEN_KEYS:
            value = usage.get(field)
            require(value is None or (type(value) is int and value >= 0), "contador nativo inválido")
            values[field].append(value)
        if all(type(usage.get(k)) is int for k in ("input_tokens", "cached_input_tokens")):
            require(usage["cached_input_tokens"] <= usage["input_tokens"], "cache excede entrada")
        if all(type(usage.get(k)) is int for k in ("output_tokens", "reasoning_output_tokens")):
            require(usage["reasoning_output_tokens"] <= usage["output_tokens"], "raciocínio excede saída")
    if len(sessions) != 1 or not sessions[0]:
        issues.append("sessao_nativa_ausente_ou_ambigua")
    if not models:
        issues.append("modelo_nativo_ausente")
    if not active or not active <= metered:
        issues.append("turnos_sem_medicao")
    if not active <= finished:
        issues.append("turnos_incompletos")
    if calls != outputs or call_ids != output_ids:
        issues.append("chamadas_sem_resultado_ou_resultados_orfaos")
    tokens = {k: sum(v) if v and all(x is not None for x in v) else None for k, v in values.items()}
    if tokens["input_tokens"] is None or tokens["output_tokens"] is None:
        issues.append("tokens_essenciais_ausentes")
    return {"tokens": tokens, "inference_events": events, "eventos_duplicados": duplicates,
            "tool_calls": calls, "argument_bytes": input_bytes, "tool_output_bytes": output_bytes,
            "palavras_narradas": words, "compactacoes": compactions,
            "problemas_cobertura": sorted(set(issues)), "session_id": sessions[0] if len(sessions) == 1 else None,
            "modelos": sorted(models), "entradas": prompts}


def analyzer() -> Callable:
    path = ROOT / "ferramentas/analisar-rollout.py"
    spec = importlib.util.spec_from_file_location("narrative_benchmark_rollout_adapter", path)
    require(spec is not None and spec.loader is not None, "analisador indisponível")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.analyze


def _sum_optional(items: list[dict], key: str) -> int | None:
    values = [x.get(key) for x in items]
    return sum(values) if values and all(type(v) is int for v in values) else None


def episode(paths: list[Path], analyze: Callable | None = None) -> tuple[dict, list[list]]:
    require(bool(paths), "episódio sem segmentos")
    analyze = analyze or analyzer()
    scans, raw, operational, hashes = [], [], [], []
    for path in paths:
        content = path.read_bytes()
        require(digest(content) not in hashes, "segmento duplicado no episódio")
        hashes.append(digest(content))
        records = _read_records(path)
        raw.append(records)
        scans.append(_native(records))
        report = analyze(path)
        require(report.get("schema_version") == 3, "analisador precisa preservar schema 3")
        operational.append({"schema_version": 3,
                            "all_turns": {k: report.get("all_turns", {}).get(k) for k in
                                          ("turns", "tool_calls", "raw_read_calls", "schema_discovery_calls",
                                           "failed_write_calls", "unknown_write_calls", "orchestration_calls")}})
    ids = [s["session_id"] for s in scans if s["session_id"]]
    require(len(set(ids)) == len(ids), "mesma sessão repartida ou duplicada: forneça o arquivo completo")
    tokens = {k: _sum_optional([s["tokens"] for s in scans], k) for k in TOKEN_KEYS}
    traffic = None if any(tokens[k] is None for k in ("input_tokens", "output_tokens")) else tokens["input_tokens"] + tokens["output_tokens"]
    uncached = None if tokens["input_tokens"] is None or tokens["cached_input_tokens"] is None else tokens["input_tokens"] - tokens["cached_input_tokens"]
    return {"segmentos": [{"sha256": h, "session_id": s["session_id"]} for h, s in zip(hashes, scans)],
            "modelos": sorted({m for s in scans for m in s["modelos"]}),
            "tokens": {**tokens, "input_plus_output_tokens": traffic, "uncached_input_tokens": uncached},
            **{k: sum(s[k] for s in scans) for k in ("inference_events", "eventos_duplicados", "tool_calls",
                                                    "argument_bytes", "tool_output_bytes", "palavras_narradas", "compactacoes")},
            "problemas_cobertura": sorted({p for s in scans for p in s["problemas_cobertura"]}),
            "entradas_por_segmento": [s["entradas"] for s in scans],
            "operacional_schema3": operational}, raw


def _review(criteria: list[dict], observations: dict, raw: list[list]) -> dict:
    require(set(observations) <= {c["id"] for c in criteria}, "observação de critério desconhecido")
    result = {}
    for criterion in criteria:
        key = criterion["id"]
        obs = observations.get(key, {})
        require(isinstance(obs, dict), "observação inválida")
        verdict = obs.get("resultado", "nao_avaliado")
        require(verdict in {"aprovado", "reprovado", "nao_avaliado"}, "resultado de revisão inválido")
        evidence = []
        if verdict != "nao_avaliado":
            require(isinstance(obs.get("avaliador"), str) and bool(obs["avaliador"].strip()), "avaliador obrigatório")
            require(isinstance(obs.get("justificativa"), str) and len(obs["justificativa"].strip()) >= 20,
                    "revisão exige justificativa semântica")
            require(isinstance(obs.get("evidencias"), list) and bool(obs["evidencias"]), "revisão sem evidência")
            for e in obs["evidencias"]:
                require(isinstance(e, dict) and type(e.get("segmento")) is int and type(e.get("linha")) is int,
                        "endereço de evidência inválido")
                si, li = e["segmento"], e["linha"]
                require(0 <= si < len(raw) and 1 <= li <= len(raw[si]), "evidência fora do rollout")
                record = raw[si][li - 1] or {}
                p = record.get("payload", {})
                require(record.get("type") == "response_item" and p.get("type") == "message"
                        and p.get("role") == "assistant" and p.get("channel") == "final",
                        "evidência narrativa deve vir da resposta final, nunca do prompt ou planejamento")
                quote = e.get("trecho")
                require(isinstance(quote, str) and len(quote.strip()) >= 12 and quote in _text(p),
                        "evidência não literal")
                evidence.append({"segmento": si, "linha": li, "sha256_trecho": digest(quote.encode("utf-8"))})
        result[key] = {"resultado": verdict, "avaliador": obs.get("avaliador"), "evidencias": evidence,
                       "metodo": "revisao_semantica_declarada; codigo_verifica_apenas_proveniencia_literal"}
    return result


def collect(manifest_path: Path, catalog_path: Path = CATALOG, analyze: Callable | None = None) -> dict:
    manifest, scenarios = load(manifest_path), catalog(catalog_path)
    require(manifest.get("schema") == 1 and manifest.get("integral") is True, "manifesto deve declarar episódios integrais")
    require(manifest.get("natureza") in {"ensaio_narrado", "fixture_sintetica"}, "natureza de medição ausente")
    require(isinstance(manifest.get("codigo_ref"), str) and re.fullmatch(r"[0-9a-f]{40}", manifest["codigo_ref"]) is not None,
            "codigo_ref deve identificar o commit medido")
    config = manifest.get("configuracao")
    require(isinstance(config, dict) and all(k in config for k in ("modelo", "parametros", "ruleset")),
            "configuração de execução incompleta")
    require(manifest.get("catalogo_sha256") == digest(canonical(scenarios)), "catálogo divergiu do ensaio")
    runs = manifest.get("episodios")
    require(isinstance(runs, list) and bool(runs), "manifesto sem episódios")
    seen, source_hashes, results = set(), set(), []
    by_id = {c["id"]: c for c in scenarios["cenarios"]}
    for run in runs:
        require(isinstance(run, dict) and run.get("cenario") in by_id, "cenário desconhecido")
        require(isinstance(run.get("repeticao"), str) and bool(run["repeticao"]), "repetição não identificada")
        require(isinstance(run.get("seed"), str) and bool(run["seed"]), "seed não declarada")
        key = (run["cenario"], run["repeticao"])
        require(key not in seen, "episódio duplicado")
        seen.add(key)
        names = run.get("segmentos")
        require(isinstance(names, list) and bool(names) and all(isinstance(p, str) and p for p in names), "segmentos inválidos")
        paths = [(manifest_path.parent / p).resolve() for p in names]
        measured, raw = episode(paths, analyze=analyze)
        for segment in measured["segmentos"]:
            require(segment["sha256"] not in source_hashes, "um rollout não pode contar em dois episódios")
            source_hashes.add(segment["sha256"])
        scenario = by_id[run["cenario"]]
        prompts = measured.pop("entradas_por_segmento")
        expected = [s["entrada"] for s in scenario["passos"]]
        if [p for segment in prompts for p in segment] != expected:
            measured["problemas_cobertura"].append("roteiro_incompleto_ou_divergente")
        boundaries = [sum(len(x) for x in prompts[:i]) for i in range(len(prompts))]
        required_boundaries = [i for i, s in enumerate(scenario["passos"]) if s.get("contexto") == "frio"]
        if boundaries != required_boundaries:
            measured["problemas_cobertura"].append("fronteiras_de_contexto_divergentes")
        if measured["modelos"] != [config["modelo"]]:
            measured["problemas_cobertura"].append("modelo_observado_divergente")
        measured["problemas_cobertura"] = sorted(set(measured["problemas_cobertura"]))
        results.append({"cenario": key[0], "repeticao": key[1], "seed": run["seed"],
                        "medicao": measured,
                        "criterios": _review(scenario["criterios"], run.get("observacoes", {}), raw)})
    return {"schema_benchmark_narrativo": 1, "natureza": manifest["natureza"],
            "codigo_ref": manifest["codigo_ref"], "catalogo_sha256": digest(canonical(scenarios)),
            "configuracao": config, "episodios": sorted(results, key=lambda r: (r["cenario"], r["repeticao"])),
            "status": "MEDIDO_SEM_VEREDITO_DE_ECONOMIA",
            "nota": "Tráfego não é faturamento. Revisão semântica não é provada por substring. Brutos não são copiados."}


def compare(before: dict, after: dict) -> dict:
    for report in (before, after):
        require(report.get("schema_benchmark_narrativo") == 1 and isinstance(report.get("episodios"), list),
                "comparação exige relatórios de episódios, não sondas de componentes")
        require(isinstance(report.get("configuracao"), dict) and bool(report["configuracao"])
                and isinstance(report.get("catalogo_sha256"), str) and bool(report["catalogo_sha256"]),
                "relatório sem identidade de ensaio")
        for run in report["episodios"]:
            require(isinstance(run.get("criterios"), dict) and bool(run["criterios"]),
                    "relatório sem critérios")
    problems, failures, rows = [], [], []
    if before.get("natureza") != "ensaio_narrado" or after.get("natureza") != "ensaio_narrado":
        problems.append("dados_sinteticos_nao_provam_economia_real")
    for key in ("catalogo_sha256", "configuracao"):
        if before.get(key) != after.get(key):
            problems.append(f"{key}_incomparavel")
    def indexed(report):
        out = {}
        for r in report["episodios"]:
            key = (r["cenario"], r["repeticao"])
            require(key not in out, "relatório contém episódio duplicado")
            out[key] = r
        return out
    old, new = indexed(before), indexed(after)
    if set(old) != set(new) or {k[0] for k in old} != SCENARIOS:
        problems.append("amostra_incompleta_ou_nao_pareada")
    for key in sorted(set(old) & set(new)):
        a, b = old[key], new[key]
        am, bm = a["medicao"], b["medicao"]
        if a["seed"] != b["seed"]:
            problems.append(f"{key}:seed_divergente")
        if am["problemas_cobertura"] or bm["problemas_cobertura"]:
            problems.append(f"{key}:cobertura_insuficiente")
        if set(a["criterios"]) != set(b["criterios"]):
            problems.append(f"{key}:criterios_divergentes")
        for cid, verdict in b["criterios"].items():
            if verdict["resultado"] == "nao_avaliado" or a["criterios"].get(cid, {}).get("resultado") == "nao_avaliado":
                problems.append(f"{key}:{cid}:sem_avaliacao")
            elif verdict["resultado"] != "aprovado":
                failures.append(f"{key}:{cid}:qualidade_insuficiente")
        aw, bw = am["palavras_narradas"], bm["palavras_narradas"]
        if aw <= 0 or bw <= 0 or not 0.8 <= bw / aw <= 1.25:
            problems.append(f"{key}:volume_narrativo_incomparavel")
        at, bt = am["tokens"].get("input_plus_output_tokens"), bm["tokens"].get("input_plus_output_tokens")
        if type(at) is not int or type(bt) is not int:
            problems.append(f"{key}:tokens_ausentes")
        rows.append({"cenario": key[0], "repeticao": key[1], "antes_tokens": at, "depois_tokens": bt,
                     "antes_bytes_saida": am["tool_output_bytes"], "depois_bytes_saida": bm["tool_output_bytes"]})
    totals = {}
    for label, report in (("antes", before), ("depois", after)):
        measures = [r["medicao"] for r in report["episodios"]]
        tokens = [m["tokens"] for m in measures]
        traffic = [x.get("input_plus_output_tokens") for x in tokens]
        valid = bool(traffic) and all(type(v) is int for v in traffic)
        totals[label] = {k: _sum_optional(tokens, k) for k in (*TOKEN_KEYS, "input_plus_output_tokens", "uncached_input_tokens")}
        totals[label]["p95_tokens_por_episodio"] = sorted(traffic)[max(0, math.ceil(0.95 * len(traffic)) - 1)] if valid else None
    a, b = totals["antes"], totals["depois"]
    if a["input_plus_output_tokens"] is not None and b["input_plus_output_tokens"] is not None:
        if b["input_plus_output_tokens"] > a["input_plus_output_tokens"]:
            failures.append("trafego_total_aumentou")
    if all(type(r[k]) is int for r in (a, b) for k in ("uncached_input_tokens", "output_tokens")):
        if b["uncached_input_tokens"] + b["output_tokens"] > a["uncached_input_tokens"] + a["output_tokens"]:
            failures.append("entrada_nao_cache_mais_saida_aumentou")
    elif (a["uncached_input_tokens"] is None) != (b["uncached_input_tokens"] is None):
        problems.append("cobertura_cache_divergente")
    status = "INCONCLUSIVO" if problems else "REPROVADO" if failures else "APROVADO"
    return {"schema_comparacao_narrativa": 1, "status": status, "aprovado": status == "APROVADO",
            "problemas": sorted(set(problems)), "falhas": sorted(set(failures)), "totais": totals, "episodios": rows,
            "nota": "Critérios precisam de revisão; cache e raciocínio são parcelas, não tokens somados outra vez."}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalogo", type=Path, default=CATALOG)
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("cenarios")
    sub.add_parser("sondar")
    p = sub.add_parser("manifesto")
    p.add_argument("--codigo-ref", required=True)
    p.add_argument("--modelo", required=True)
    p.add_argument("--ruleset", required=True)
    p = sub.add_parser("coletar")
    p.add_argument("manifesto", type=Path)
    p = sub.add_parser("comparar")
    p.add_argument("antes", type=Path)
    p.add_argument("depois", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.comando == "cenarios":
            result = catalog(args.catalogo)
            result = {"catalogo_sha256": digest(canonical(result)), **result}
        elif args.comando == "sondar":
            from benchmark_sondas import probe
            result = probe(args.catalogo)
        elif args.comando == "manifesto":
            data = catalog(args.catalogo)
            require(re.fullmatch(r"[0-9a-f]{40}", args.codigo_ref) is not None, "commit inválido")
            result = {"schema": 1, "natureza": "ensaio_narrado", "integral": False,
                      "codigo_ref": args.codigo_ref, "catalogo_sha256": digest(canonical(data)),
                      "configuracao": {"modelo": args.modelo, "ruleset": args.ruleset, "parametros": {}},
                      "episodios": [{"cenario": c["id"], "repeticao": "1", "seed": "registrar-seed-do-ensaio",
                                     "segmentos": [f"{c['id']}-{i}.jsonl" for i in range(
                                         sum(p["contexto"] == "frio" for p in c["passos"]))],
                                     "observacoes": {x["id"]: {"resultado": "nao_avaliado"} for x in c["criterios"]}}
                                    for c in data["cenarios"]]}
        elif args.comando == "coletar":
            result = collect(args.manifesto, args.catalogo)
        else:
            result = compare(load(args.antes), load(args.depois))
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 2 if result.get("status") == "INCONCLUSIVO" else 1 if result.get("status") == "REPROVADO" else 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FALHA DE BENCHMARK NARRATIVO — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
