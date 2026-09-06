"""Ensaios sintéticos do medidor: números abaixo não são consumo real da campanha."""
from __future__ import annotations

import copy
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import benchmark_narrativo as bench


def fake_analyzer(path):
    records = bench._read_records(path)
    calls = sum(1 for r in records if r and r.get("payload", {}).get("type") in bench.CALL_TYPES)
    return {"schema_version": 3, "all_turns": {"tool_calls": calls, "turns": 5},
            "narration_turns": {"tool_calls": 0}}


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def rollout(path, prompts, session, *, input_tokens=1000, output_tokens=200, words=60, missing=None,
            administrative=False):
    """Produz trace controlado; nunca é descrito como uma execução real de modelo."""
    records = [{"type": "session_meta", "payload": {"id": session, "cli_version": "fixture"}}]
    total = {k: 0 for k in bench.TOKEN_KEYS}
    evidence = []
    for n, prompt in enumerate(prompts):
        tid = f"{session}-{n}"
        records.extend([
            {"type": "event_msg", "payload": {"type": "task_started", "turn_id": tid}},
            {"type": "turn_context", "payload": {"turn_id": tid, "model": "modelo-fixture"}},
            {"type": "response_item", "payload": {"type": "message", "role": "user", "content": [{"text": prompt}]}}
        ])
        for phase in ("preparar", "concluir"):
            cid = f"{tid}-{phase}"
            records.extend([
                {"type": "response_item", "payload": {"type": "function_call", "name": "exec_command", "call_id": cid,
                  "arguments": json.dumps({"cmd": f"cronica {phase} --sem-oportunidade-sidequest"})}},
                {"type": "response_item", "payload": {"type": "function_call_output", "call_id": cid, "output": "OK fixture"}}
            ])
        text = "Lia mantém a promessa sem decidir por Ren. " + "oficina " * words
        records.append({"type": "response_item", "payload": {"type": "message", "role": "assistant", "channel": "final", "content": [{"text": text}]}})
        evidence.append(len(records))
        usage = {"input_tokens": input_tokens, "cached_input_tokens": input_tokens // 2,
                 "output_tokens": output_tokens, "reasoning_output_tokens": output_tokens // 4}
        total = {k: total[k] + usage[k] for k in bench.TOKEN_KEYS}
        if missing:
            usage.pop(missing, None)
        records.append({"type": "event_msg", "payload": {"type": "token_count", "info": {
            "last_token_usage": usage, "total_token_usage": copy.deepcopy(total)}}})
    if administrative:
        records.extend([
            {"type": "event_msg", "payload": {"type": "task_started", "turn_id": "manutencao"}},
            {"type": "response_item", "payload": {"type": "function_call", "name": "exec_command", "call_id": "world",
               "arguments": '{"cmd":"python ferramentas/resolver_fronteira.py preparar"}'}},
            {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "world", "output": "fila verificada"}},
            {"type": "event_msg", "payload": {"type": "token_count", "info": {"last_token_usage": {
                "input_tokens": 8000, "cached_input_tokens": 0, "output_tokens": 300, "reasoning_output_tokens": 40}}}},
            {"type": "event_msg", "payload": {"type": "task_complete", "turn_id": "manutencao"}}
        ])
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
    return evidence, records


class EpisodeMeasurementTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "rollout.jsonl"

    def measure(self, **kwargs):
        rollout(self.path, ["Olá"], "s1", **kwargs)
        return bench.episode([self.path], fake_analyzer)[0]

    def test_episode_counts_world_work_outside_narrative_turns(self):
        report = self.measure(administrative=True)
        self.assertEqual(report["tokens"]["input_tokens"], 9000)
        self.assertEqual(report["tokens"]["input_plus_output_tokens"], 9500)
        self.assertEqual(report["tool_calls"], 3)
        self.assertEqual(report["operacional_schema3"][0]["all_turns"]["tool_calls"], 3)
        self.assertEqual(report["problemas_cobertura"], [])

    def test_cache_and_reasoning_are_not_added_twice(self):
        report = self.measure()
        self.assertEqual(report["tokens"]["input_plus_output_tokens"], 1200)
        self.assertEqual(report["tokens"]["uncached_input_tokens"], 500)
        self.assertEqual(report["tokens"]["reasoning_output_tokens"], 50)
        self.assertGreater(report["argument_bytes"], 0)
        self.assertGreater(report["tool_output_bytes"], 0)

    def test_missing_cache_is_null_not_zero(self):
        report = self.measure(missing="cached_input_tokens")
        self.assertIsNone(report["tokens"]["cached_input_tokens"])
        self.assertIsNone(report["tokens"]["uncached_input_tokens"])
        self.assertEqual(report["tokens"]["input_tokens"], 1000)

    def test_missing_input_makes_economy_inconclusive(self):
        report = self.measure(missing="input_tokens")
        self.assertIsNone(report["tokens"]["input_plus_output_tokens"])
        self.assertIn("tokens_essenciais_ausentes", report["problemas_cobertura"])

    def test_empty_usage_does_not_count_as_free_inference(self):
        _, records = rollout(self.path, ["Olá"], "s1")
        records[-1]["payload"]["info"]["last_token_usage"] = {}
        self.rewrite(records)
        report = bench.episode([self.path], fake_analyzer)[0]
        self.assertIsNone(report["tokens"]["input_tokens"])
        self.assertIn("token_count_sem_uso", report["problemas_cobertura"])

    def rewrite(self, records):
        self.path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")

    def test_duplicate_cumulative_snapshot_is_not_charged_twice(self):
        _, records = rollout(self.path, ["Olá"], "s1")
        records.append(copy.deepcopy(records[-1]))
        self.rewrite(records)
        report = bench.episode([self.path], fake_analyzer)[0]
        self.assertEqual(report["tokens"]["input_tokens"], 1000)
        self.assertEqual(report["eventos_duplicados"], 1)

    def test_missing_events_detected_from_cumulative_gap(self):
        _, records = rollout(self.path, ["Olá", "Voltei"], "s1")
        records[-1]["payload"]["info"]["total_token_usage"]["input_tokens"] += 1
        self.rewrite(records)
        report = bench.episode([self.path], fake_analyzer)[0]
        self.assertIn("lacuna_em_contadores_cumulativos", report["problemas_cobertura"])

    def test_no_usage_anywhere_does_not_report_zero_tokens(self):
        _, records = rollout(self.path, ["Olá"], "s1")
        self.rewrite(records[:-1])
        report = bench.episode([self.path], fake_analyzer)[0]
        self.assertIsNone(report["tokens"]["input_tokens"])
        self.assertIn("turnos_sem_medicao", report["problemas_cobertura"])

    def test_duplicate_segment_or_native_session_rejected(self):
        rollout(self.path, ["Olá"], "s1")
        with self.assertRaises(bench.NarrativeBenchmarkError):
            bench.episode([self.path, self.path], fake_analyzer)
        other = self.path.with_name("outra.jsonl")
        rollout(other, ["Outro"], "s1")
        with self.assertRaises(bench.NarrativeBenchmarkError):
            bench.episode([self.path, other], fake_analyzer)

    def test_partial_first_cumulative_counter_is_not_a_full_episode(self):
        _, records = rollout(self.path, ["Olá"], "s1")
        records[-1]["payload"]["info"]["total_token_usage"]["input_tokens"] += 100
        self.rewrite(records)
        self.assertIn("inicio_do_rollout_parcial", bench.episode([self.path], fake_analyzer)[0]["problemas_cobertura"])

    def test_invalid_native_counters_are_rejected(self):
        for value in (-1, True, 1.5):
            with self.subTest(value=value):
                _, records = rollout(self.path, ["Olá"], "s1")
                records[-1]["payload"]["info"]["last_token_usage"]["input_tokens"] = value
                self.rewrite(records)
                with self.assertRaises(bench.NarrativeBenchmarkError):
                    bench.episode([self.path], fake_analyzer)

    def test_incomplete_tools_remain_visible(self):
        _, records = rollout(self.path, ["Olá"], "s1")
        self.rewrite([r for r in records if r.get("payload", {}).get("type") != "function_call_output"])
        report = bench.episode([self.path], fake_analyzer)[0]
        self.assertEqual(report["tool_calls"], 2)
        self.assertIn("chamadas_sem_resultado_ou_resultados_orfaos", report["problemas_cobertura"])

    def test_read_only_and_raw_content_not_in_report(self):
        rollout(self.path, ["Uma mensagem privada da fixture"], "s1")
        before = self.path.read_bytes()
        result, _ = bench.episode([self.path], fake_analyzer)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertNotIn(str(self.path), json.dumps(result))


class NarrativeBenchmarkTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.catalog = bench.catalog()
        self.manifest_path = self.repo / "manifesto.json"

    def manifest(self, **kwargs):
        runs = []
        for scenario in self.catalog["cenarios"]:
            sid = scenario["id"]
            groups = []
            for step in scenario["passos"]:
                if step["contexto"] == "frio":
                    groups.append([])
                groups[-1].append(step["entrada"])
            segments, evidences = [], []
            for n, prompts in enumerate(groups):
                name = f"{sid}-{n}.jsonl"
                proof, _ = rollout(self.repo / name, prompts, f"{sid}-{n}", **kwargs)
                segments.append(name)
                evidences.append({"segmento": n, "linha": proof[-1], "trecho": "Lia mantém a promessa sem decidir por Ren."})
            observations = {c["id"]: {"resultado": "aprovado", "avaliador": "fixture:avaliador-sintetico",
                                      "justificativa": "Parecer sintético que testa a proveniência, não a qualidade real.",
                                      "evidencias": [evidences[-1]]} for c in scenario["criterios"]}
            runs.append({"cenario": sid, "repeticao": "1", "seed": "fixa", "segmentos": segments,
                         "observacoes": observations})
        manifest = {"schema": 1, "natureza": "fixture_sintetica", "integral": True, "codigo_ref": "a"*40,
                    "catalogo_sha256": bench.digest(bench.canonical(self.catalog)),
                    "configuracao": {"modelo": "modelo-fixture", "parametros": {}, "ruleset": "fixture"},
                    "episodios": runs}
        write_json(self.manifest_path, manifest)
        return manifest

    def collect(self, **kwargs):
        self.manifest(**kwargs)
        return bench.collect(self.manifest_path, analyze=fake_analyzer)

    def pair(self):
        before = self.collect()
        before["natureza"] = "ensaio_narrado"  # apenas para exercitar o contrato de comparação
        return before, copy.deepcopy(before)

    def test_catalog_has_six_scenarios_five_steps_and_explicit_cold_resume(self):
        self.assertEqual({s["id"] for s in self.catalog["cenarios"]}, bench.SCENARIOS)
        self.assertTrue(all(len(s["passos"]) == 5 for s in self.catalog["cenarios"]))
        resume = next(s for s in self.catalog["cenarios"] if s["id"] == "retomada_fria")
        self.assertEqual(sum(s["contexto"] == "frio" for s in resume["passos"]), 2)

    def test_collect_requires_no_canonical_or_live_files(self):
        report = self.collect()
        self.assertEqual(len(report["episodios"]), 6)
        self.assertTrue(all(not r["medicao"]["problemas_cobertura"] for r in report["episodios"]))
        self.assertNotIn("Lia mantém", json.dumps(report, ensure_ascii=False))

    def test_synthetic_measurement_never_proves_real_savings(self):
        report = self.collect()
        self.assertEqual(bench.compare(report, report)["status"], "INCONCLUSIVO")

    def test_same_complete_paired_episodes_can_pass(self):
        before, after = self.pair()
        result = bench.compare(before, after)
        self.assertEqual(result["status"], "APROVADO", result)

    def test_less_tool_output_with_more_tokens_fails(self):
        before, after = self.pair()
        m = after["episodios"][0]["medicao"]
        m["tool_output_bytes"] = 1
        m["tokens"]["input_plus_output_tokens"] += 100
        self.assertIn("trafego_total_aumentou", bench.compare(before, after)["falhas"])

    def test_much_shorter_narration_cannot_buy_approval(self):
        before, after = self.pair()
        after["episodios"][0]["medicao"]["palavras_narradas"] = 1
        self.assertEqual(bench.compare(before, after)["status"], "INCONCLUSIVO")

    def test_missing_tokens_never_pass_even_when_bytes_drop(self):
        before, after = self.pair()
        after["episodios"][0]["medicao"]["tokens"]["input_plus_output_tokens"] = None
        self.assertEqual(bench.compare(before, after)["status"], "INCONCLUSIVO")

    def test_quality_failure_prevents_approval_despite_savings(self):
        before, after = self.pair()
        criterion = next(iter(after["episodios"][0]["criterios"].values()))
        criterion["resultado"] = "reprovado"
        self.assertEqual(bench.compare(before, after)["status"], "REPROVADO")

    def test_absent_review_is_not_a_pass(self):
        m = self.manifest()
        m["episodios"][0]["observacoes"] = {}
        write_json(self.manifest_path, m)
        report = bench.collect(self.manifest_path, analyze=fake_analyzer)
        report["natureza"] = "ensaio_narrado"
        self.assertEqual(bench.compare(report, report)["status"], "INCONCLUSIVO")

    def test_claimed_evidence_must_be_literal_final_assistant_text(self):
        m = self.manifest()
        obs = next(iter(m["episodios"][0]["observacoes"].values()))
        obs["evidencias"][0]["trecho"] = "Essa frase nunca foi dita por ninguém."
        write_json(self.manifest_path, m)
        with self.assertRaises(bench.NarrativeBenchmarkError):
            bench.collect(self.manifest_path, analyze=fake_analyzer)
        m = self.manifest()
        obs = next(iter(m["episodios"][0]["observacoes"].values()))
        obs["evidencias"][0]["linha"] = 4
        write_json(self.manifest_path, m)
        with self.assertRaises(bench.NarrativeBenchmarkError):
            bench.collect(self.manifest_path, analyze=fake_analyzer)

    def test_changed_prompt_or_missing_cold_segment_is_inconclusive(self):
        m = self.manifest()
        path = self.repo / m["episodios"][0]["segmentos"][0]
        content = path.read_text(encoding="utf-8").replace("Entro na oficina", "Saio da oficina")
        path.write_text(content, encoding="utf-8")
        report = bench.collect(self.manifest_path, analyze=fake_analyzer)
        self.assertTrue(any("roteiro_incompleto_ou_divergente" in r["medicao"]["problemas_cobertura"] for r in report["episodios"]))

    def test_duplicate_episode_or_reused_rollout_is_rejected(self):
        for mode in ("episode", "rollout"):
            m = self.manifest()
            if mode == "episode":
                m["episodios"].append(copy.deepcopy(m["episodios"][0]))
            else:
                m["episodios"][1]["segmentos"] = m["episodios"][0]["segmentos"]
                m["episodios"][1]["observacoes"] = {}
            write_json(self.manifest_path, m)
            with self.assertRaises(bench.NarrativeBenchmarkError):
                bench.collect(self.manifest_path, analyze=fake_analyzer)

    def test_different_models_seeds_or_missing_episode_are_incomparable(self):
        for mode in ("model", "seed", "episode"):
            before, after = self.pair()
            if mode == "model":
                after["configuracao"]["modelo"] = "outro"
            elif mode == "seed":
                after["episodios"][0]["seed"] = "outra"
            else:
                after["episodios"].pop()
            self.assertEqual(bench.compare(before, after)["status"], "INCONCLUSIVO")

    def test_corrupt_catalog_is_not_silently_used(self):
        m = self.manifest()
        m["catalogo_sha256"] = "errado"
        write_json(self.manifest_path, m)
        with self.assertRaises(bench.NarrativeBenchmarkError):
            bench.collect(self.manifest_path, analyze=fake_analyzer)

    def test_cli_inconclusive_exit_two_and_failure_exit_one(self):
        report = self.collect()
        path = self.repo / "report.json"
        write_json(path, report)
        with redirect_stdout(io.StringIO()):
            self.assertEqual(bench.main(["comparar", str(path), str(path)]), 2)
        with redirect_stderr(io.StringIO()):
            self.assertEqual(bench.main(["coletar", str(self.repo / "missing.json")]), 1)

    def test_duplicate_json_key_and_nan_rejected(self):
        for text in ('{"a":1,"a":2}', '{"a":NaN}'):
            self.manifest_path.write_text(text, encoding="utf-8")
            with self.assertRaises(bench.NarrativeBenchmarkError):
                bench.load(self.manifest_path)


if __name__ == "__main__":
    unittest.main()
