"""Integração do benchmark com os componentes reais, sem usar o save como fixture."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "ferramentas") not in sys.path:
    sys.path.insert(0, str(ROOT / "ferramentas"))

import benchmark_narrativo as bench
import benchmark_sondas
from test_benchmark_narrativo import rollout


class NarrativeBenchmarkIntegrationTest(unittest.TestCase):
    def test_adapter_usa_schema3_e_nao_filtra_fronteira_fora_de_narracao(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "fixture.jsonl"
            rollout(path, ["Olá"], "integracao-fixture", administrative=True)
            before = path.read_bytes()
            report, _ = bench.episode([path])
            self.assertEqual(report["tokens"]["input_tokens"], 9000)
            self.assertEqual(report["tool_calls"], 3)
            self.assertEqual(report["operacional_schema3"][0]["all_turns"]["tool_calls"], 3)
            self.assertEqual(report["operacional_schema3"][0]["schema_version"], 3)
            self.assertEqual(path.read_bytes(), before)

    def test_sondas_reais_sao_deterministicas_e_nao_abrem_save_vivo(self):
        original = Path.open
        forbidden = {"estado", "runtime", "personagens", "narrador", "sessoes", "historico"}

        def guarded(path, *args, **kwargs):
            try:
                relative = path.resolve().relative_to(ROOT.resolve())
            except ValueError:
                relative = None
            if relative is not None and relative.parts and relative.parts[0] in forbidden:
                raise AssertionError(f"sonda tentou acessar o save real: {relative}")
            return original(path, *args, **kwargs)

        with patch.object(Path, "open", guarded):
            first = benchmark_sondas.probe()
            second = benchmark_sondas.probe()
        self.assertEqual(first, second)
        self.assertEqual({x["cenario"] for x in first["episodios"]}, bench.SCENARIOS)
        self.assertIsNone(first["totais"]["tokens_nativos"])
        self.assertTrue(all(r["qualidade_narrada"] == "nao_avaliada" for r in first["episodios"]))
        for row in first["episodios"]:
            for sample in row["amostras"]:
                if row["cenario"] != "iniciativa_fora_cena":
                    self.assertTrue(sample["somente_leitura"], sample)
                self.assertGreater(sample["output_bytes"], 0)
        print("NV02_SONDAS=" + json.dumps(first, ensure_ascii=False, sort_keys=True))

    def test_sonda_nao_pode_ser_usada_como_ensaio_narrado(self):
        with self.assertRaises(bench.NarrativeBenchmarkError):
            bench.compare({"schema_sondas_narrativas": 1}, {"schema_sondas_narrativas": 1})


if __name__ == "__main__":
    unittest.main()
