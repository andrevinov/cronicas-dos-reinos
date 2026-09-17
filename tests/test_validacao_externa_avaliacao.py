from __future__ import annotations

import hashlib
import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ferramentas import validar_amostra_externa_avaliacao as external


ROOT = Path(__file__).resolve().parents[1]


class ExternalEvaluationValidationTest(unittest.TestCase):
    def test_installed_real_sample_matches_independent_expectations(self):
        result = external.validate_external_sample(ROOT)
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "aprovado")
        self.assertEqual(result["sessao_origem"], "022")
        self.assertEqual(result["operacoes_esperadas"], 6)
        self.assertEqual(result["operacoes_observadas"], 6)
        self.assertEqual(result["checks_reprovados"], 0)
        self.assertFalse(result["fonte_integral_verificada"])
        self.assertIn("prospectivo", result["limitacao"])

    def test_sample_hash_prevents_silent_input_change(self):
        with TemporaryDirectory(prefix="validacao-externa-hash-") as temporary:
            copied = Path(temporary) / "validacao"
            shutil.copytree(ROOT / "evaluation/validacao-externa-v1", copied)
            sample = copied / "amostra-s022.jsonl"
            sample.write_bytes(sample.read_bytes() + b"\n")
            with self.assertRaisesRegex(external.ExternalValidationError, "hash da amostra"):
                external.validate_external_sample(ROOT, manifest_path=copied / "manifest.json")

    def test_semantic_divergence_fails_after_valid_rehash(self):
        with TemporaryDirectory(prefix="validacao-externa-gabarito-") as temporary:
            copied = Path(temporary) / "validacao"
            shutil.copytree(ROOT / "evaluation/validacao-externa-v1", copied)
            golden_path = copied / "gabarito-s022.json"
            golden = json.loads(golden_path.read_text(encoding="utf-8"))
            golden["expectativas"][0]["state"] = "falha_operacional"
            golden_path.write_text(
                json.dumps(golden, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            manifest_path = copied / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["gabarito"]["sha256"] = hashlib.sha256(golden_path.read_bytes()).hexdigest()
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            result = external.validate_external_sample(ROOT, manifest_path=manifest_path)
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "reprovado")
            self.assertEqual(result["checks_reprovados"], 1)

    def test_declared_source_lines_are_individually_hash_anchored(self):
        manifest = json.loads(external.DEFAULT_MANIFEST.read_text(encoding="utf-8"))
        records = manifest["amostra"]["registros"]
        self.assertEqual(len(records), len(manifest["amostra"]["linhas_fonte"]))
        self.assertEqual(
            [item["linha_fonte"] for item in records],
            manifest["amostra"]["linhas_fonte"],
        )
        self.assertEqual(len({item["sha256"] for item in records}), len(records))


if __name__ == "__main__":
    unittest.main()
