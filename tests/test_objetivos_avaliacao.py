"""Contratos e referências isolados; nenhum teste exige valores do save vivo."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from ferramentas import catalogo_avaliacao as catalog
from ferramentas import verificar_aceite_avaliacao as acceptance


REFERENCE = acceptance.DEFAULT_MANIFEST


class ModulePurposeContractTest(unittest.TestCase):
    def setUp(self):
        manifest = acceptance.read_json(REFERENCE)
        self.catalog = acceptance.read_json(REFERENCE.parent / manifest["catalogo"])

    def test_each_capability_has_its_own_purpose_negative_and_knowledge_guardrails(self):
        catalog.validate_catalog_v2(self.catalog)
        for module in self.catalog["modulos"]:
            for capability in module["subcapacidades"]:
                objective = capability["contrato_objetivo"]
                self.assertEqual(objective["criterio_id"], f"{module['id']}.{capability['id']}")
                self.assertEqual(set(objective["guardrails"]), set(module["guardrails_aplicaveis"]))
                self.assertNotEqual(objective["resultado_verificavel"], objective["negativa_valida"])

    def test_missing_sources_negative_and_purpose_are_rejected(self):
        for key in ("fontes_necessarias", "negativa_valida", "objetivo_jogo"):
            invalid = copy.deepcopy(self.catalog)
            invalid["modulos"][0]["subcapacidades"][0]["contrato_objetivo"].pop(key)
            with self.subTest(key=key), self.assertRaisesRegex(catalog.EvaluationCatalogError, "incompleto"):
                catalog.validate_catalog_v2(invalid)

    def test_success_absence_and_guardrails_cannot_manufacture_experience_approval(self):
        for key in ("sucesso_operacional_nao_confirma_experiencia", "oportunidade_independe_de_recibo", "guardrail_fora_da_media", "ausencia_de_fonte_nao_e_negativa"):
            invalid = copy.deepcopy(self.catalog)
            invalid["contrato_objetivos_avaliacao"][key] = False
            with self.subTest(key=key), self.assertRaisesRegex(catalog.EvaluationCatalogError, key):
                catalog.validate_catalog_v2(invalid)

    def test_unknown_owner_unit_and_missing_guardrail_fail(self):
        invalid_values = {"responsavel": "outro_modulo", "unidade": "sessao", "guardrails": ["player_agency"]}
        for key, value in invalid_values.items():
            invalid = copy.deepcopy(self.catalog)
            invalid["modulos"][0]["subcapacidades"][0]["contrato_objetivo"][key] = value
            with self.subTest(key=key), self.assertRaises(catalog.EvaluationCatalogError):
                catalog.validate_catalog_v2(invalid)

    def test_old_frozen_catalog_is_readable_but_installed_catalog_cannot_drop_objectives(self):
        historical = copy.deepcopy(self.catalog)
        historical.pop("contrato_objetivos_avaliacao")
        for module in historical["modulos"]:
            for capability in module["subcapacidades"]:
                capability.pop("contrato_objetivo")
        catalog.validate_catalog_v2(historical)
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "catalogo.json"
            path.write_text(json.dumps(historical), encoding="utf-8")
            with patch.object(catalog, "DEFAULT_CATALOG", path), self.assertRaisesRegex(catalog.EvaluationCatalogError, "preservar"):
                catalog.validate_defaults()


class AcceptanceReferenceTest(unittest.TestCase):
    def _copy(self, directory):
        target = Path(directory) / "referencia"
        shutil.copytree(REFERENCE.parent, target)
        return target / "manifest.json"

    def _rewrite(self, manifest_path, relative, value):
        path = manifest_path.parent / relative
        path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")
        manifest = acceptance.read_json(manifest_path)
        manifest["hashes"][relative] = acceptance.sha(path)
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    def test_valid_reference_has_separate_reserved_cases_and_explicit_pending_judgment(self):
        manifest = acceptance.validate_reference()
        self.assertTrue(any(case["conjunto"] == "reservado" for case in manifest["casos"]))
        historical = acceptance.read_json(REFERENCE.parent / manifest["gabarito_s024"])
        pending = [item for entry in historical["desenvolvimento"] for item in entry["expectativas"] if item["estado_referencia"] == "pendente"]
        self.assertTrue(pending)
        self.assertFalse(historical["fonte"]["bruto_versionado"])

    def test_hash_tampering_is_not_a_detector_failure(self):
        with TemporaryDirectory() as tmp:
            path = self._copy(tmp)
            fixture = next((path.parent / "entradas").glob("*.json"))
            fixture.write_text(fixture.read_text() + "\n", encoding="utf-8")
            with self.assertRaisesRegex(acceptance.AcceptanceReferenceError, "hash divergente"):
                acceptance.validate_reference(path)

    def test_false_evidence_even_with_updated_hash_is_rejected(self):
        with TemporaryDirectory() as tmp:
            path = self._copy(tmp)
            manifest = acceptance.read_json(path)
            manifest["casos"][0]["checks"][0]["evidencia"]["fragmento"] = "frase que não existe"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(acceptance.AcceptanceReferenceError, "não pertence"):
                acceptance.validate_reference(path)

    def test_empty_checks_and_removing_reserved_set_cannot_yield_approval(self):
        for change in ("empty", "reserved"):
            with TemporaryDirectory() as tmp:
                path = self._copy(tmp)
                manifest = acceptance.read_json(path)
                if change == "empty":
                    manifest["casos"][0]["checks"] = []
                else:
                    manifest["casos"] = [case for case in manifest["casos"] if case["conjunto"] != "reservado"]
                path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.subTest(change=change), self.assertRaises(acceptance.AcceptanceReferenceError):
                    acceptance.validate_reference(path)

    def test_wrong_target_configuration_and_unknown_historical_criterion_are_rejected(self):
        with TemporaryDirectory() as tmp:
            path = self._copy(tmp)
            manifest = acceptance.read_json(path)
            self._rewrite(path, manifest["metas"], {"schema_version": 1, "narration": {}})
            with self.assertRaisesRegex(acceptance.AcceptanceReferenceError, "metas"):
                acceptance.validate_reference(path)
        with TemporaryDirectory() as tmp:
            path = self._copy(tmp)
            manifest = acceptance.read_json(path)
            historical = acceptance.read_json(path.parent / manifest["gabarito_s024"])
            historical["desenvolvimento"][0]["expectativas"][0]["criterio"] = "criterio_inventado"
            self._rewrite(path, manifest["gabarito_s024"], historical)
            with self.assertRaisesRegex(acceptance.AcceptanceReferenceError, "critério desconhecido"):
                acceptance.validate_reference(path)

    def test_native_source_is_checked_by_prefix_hash_and_specific_text_anchor(self):
        record = {"payload": {"text": "entrada histórica isolada"}}
        frozen = (json.dumps(record, ensure_ascii=False) + "\n").encode()
        history = {"fonte": {"corte_bytes": len(frozen), "sha256": hashlib.sha256(frozen).hexdigest()}, "desenvolvimento": [{"ancoras": [{"linha": 1, "ponteiro": "/payload/text", "sha256_texto": hashlib.sha256(record["payload"]["text"].encode()).hexdigest()}]}], "reservado": []}
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "historico.jsonl"
            path.write_bytes(frozen + b'{"nova_interacao":true}\n')
            result = acceptance.verify_native_source(path, history)
            self.assertEqual(result["ancoras_verificadas"], 1)
            history["desenvolvimento"][0]["ancoras"][0]["sha256_texto"] = "0" * 64
            with self.assertRaisesRegex(acceptance.AcceptanceReferenceError, "âncora"):
                acceptance.verify_native_source(path, history)
            path.write_bytes(b"outra fonte\n")
            with self.assertRaisesRegex(acceptance.AcceptanceReferenceError, "corte histórico"):
                acceptance.verify_native_source(path, history)

    def test_unknown_selection_and_reference_claiming_approval_fail_closed(self):
        with self.assertRaisesRegex(acceptance.AcceptanceReferenceError, "seleção"):
            acceptance.measure(group="inexistente")
        with TemporaryDirectory() as tmp:
            path = self._copy(tmp)
            manifest = acceptance.read_json(path)
            manifest["estado"] = "aprovado"
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(acceptance.AcceptanceReferenceError, "aprovado"):
                acceptance.validate_reference(path)


if __name__ == "__main__":
    unittest.main()
