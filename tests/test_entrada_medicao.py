from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from ferramentas import entrada_medicao as entry

ROOT = Path(__file__).resolve().parents[1]


class MeasurementInputTest(unittest.TestCase):
    """Cenários sintéticos isolados; não congelam valores da campanha viva."""

    def setUp(self):
        self.temp = TemporaryDirectory(prefix="cronicas-entrada-medicao-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.contract = json.loads(entry.DEFAULT_CONTRACT.read_text(encoding="utf-8"))
        self.contract_path = self.root / "contrato.json"
        self.write_json(self.contract_path, self.contract)
        self.module_dir = self.root / "modulos"
        self.module_dir.mkdir()
        self.catalog = {"modulos": [self.module("alpha"), self.module("beta")]}
        for module in self.catalog["modulos"]:
            local = {"schema_contrato_modulo": 1, "versao_contrato": "1.0.0", "module_id": module["id"],
                     "unidade_contexto_legada": "evento", "indicadores": {"amostra": self.indicator()}}
            self.write_json(self.module_dir / (module["id"] + ".json"), local)
        self.paths = {}
        for name in entry.SOURCES:
            path = self.root / f"{name}.json"
            self.write_json(path, self.catalog if name == "catalogo" else {})
            self.paths[name] = path
        self.rollout = self.root / "rollout.jsonl"
        self.rollout.write_text(json.dumps({"type": "session_meta", "payload": {"id": "sessao-sintetica"}, "timestamp": "2026-01-01T00:00:00Z"}) + "\n", encoding="utf-8")
        self.engine = self.root / "engine.py"
        self.engine.write_text("# implementação sintética\n", encoding="utf-8")

    @staticmethod
    def module(name):
        return {"id": name, "versao_implementacao": "1.0.0", "versao_avaliacao": "1.0.0",
                "indicadores_especializados": [{"id": "amostra", "unidade": "contagem"}]}

    @staticmethod
    def indicator():
        return {"unidade_avaliativa": "atividade_modular", "medida": "contagem", "fonte": "observacao",
                "denominador": None, "ausencia_de_evidencia": "indeterminado"}

    @staticmethod
    def write_json(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")

    def prepare(self, **kwargs):
        arguments = dict(session_id="900", source_paths=self.paths,
                         contract_path=self.contract_path, modules_directory=self.module_dir,
                         code_paths={"engine.py": self.engine})
        arguments.update(kwargs)
        return entry.prepare_input(self.rollout, **arguments)

    def codes(self, bundle):
        return {error["codigo"] for error in entry.validate_input(bundle)}

    def test_repeated_immutable_inputs_have_identical_bytes(self):
        first = self.prepare()
        second = self.prepare()
        self.assertEqual(first["status"], "valida")
        self.assertEqual(entry.canonical_bytes(first), entry.canonical_bytes(second))
        self.assertEqual(entry.validate_input(first), [])

    def test_source_append_does_not_change_declared_prefix(self):
        first = self.prepare()
        original = self.rollout.read_bytes()
        with self.rollout.open("ab") as handle:
            handle.write(b'{"registro posterior incompleto"')
        repeated = self.prepare(cutoff_bytes=first["fonte"]["corte_bytes"])
        self.assertEqual(first, repeated)
        self.assertEqual(entry.read_frozen_source(first, self.rollout), original)
        self.assertEqual(self.prepare()["status"], "bloqueada")

    def test_changing_source_prefix_is_rejected(self):
        bundle = self.prepare()
        self.rollout.write_bytes(self.rollout.read_bytes().replace(b"sintetica", b"alterada"))
        with self.assertRaises(entry.InputContractError):
            entry.read_frozen_source(bundle, self.rollout)

    def test_cutoff_and_expected_hash_are_checked(self):
        bundle = self.prepare(expected_sha256="0" * 64)
        self.assertIn("hash_fonte_divergente", self.codes(bundle))
        self.assertEqual(bundle["status"], "bloqueada")
        with self.assertRaises(entry.InputContractError):
            self.prepare(cutoff_bytes=self.rollout.stat().st_size + 1)

    def test_unknown_native_types_do_not_generate_assessed_performance(self):
        self.rollout.write_text('{"type":"formato_futuro","payload":{}}\n', encoding="utf-8")
        bundle = self.prepare()
        self.assertEqual(bundle["status"], "bloqueada")
        self.assertIn("formato_nao_suportado", self.codes(bundle))
        self.assertNotIn("nota_geral_0a100", bundle)

    def test_invalid_json_duplicate_keys_and_non_finite_values_are_explicit(self):
        for text in ['{"type":', '{"type":"event_msg","type":"session_meta","payload":{}}', '{"type":"event_msg","payload":{"n":NaN}}', '{"type":"event_msg","payload":{"n":1e999}}']:
            with self.subTest(text=text):
                self.rollout.write_text(text, encoding="utf-8")
                bundle = self.prepare()
                self.assertIn("registro_json_invalido", self.codes(bundle))
                self.assertEqual(bundle["status"], "bloqueada")

    def test_text_and_block_output_envelopes_are_supported(self):
        for output in ["exit_code: 0\n", [{"type": "input_text", "text": '{"i":0,"value":{"output":"recibo"}}'}]]:
            self.rollout.write_text(json.dumps({"type": "response_item", "payload": {
                "type": "custom_tool_call_output", "call_id": "synthetic-call", "output": output}}), encoding="utf-8")
            bundle = self.prepare()
            self.assertEqual(bundle["status"], "valida")
            self.assertIn("não comprova extração", bundle["escopo_validacao"])

    def test_missing_native_identity_is_not_promoted_to_canonical_identity(self):
        self.rollout.write_text('{"type":"response_item","payload":{"type":"function_call_output","output":"ok"}}', encoding="utf-8")
        bundle = self.prepare()
        self.assertEqual(bundle["status"], "limitada")
        self.assertIn("identidade_chamada_ausente", self.codes(bundle))
        self.assertNotIn("interaction_ref", bundle["fonte"])

    def test_optional_absence_is_explicit_and_required_absence_blocks(self):
        paths = dict(self.paths, adjudicacoes=None)
        bundle = self.prepare(source_paths=paths)
        self.assertEqual(bundle["status"], "limitada")
        self.assertEqual(bundle["snapshots"]["adjudicacoes"]["estado"], "ausente")
        bundle = self.prepare(source_paths=dict(paths, baseline=None))
        self.assertEqual(bundle["status"], "bloqueada")

    def test_mutable_dependencies_are_embedded_and_not_reread(self):
        bundle = self.prepare()
        self.write_json(self.paths["metas"], {"mudanca": "posterior"})
        self.assertEqual(entry.validate_input(bundle), [])
        self.assertEqual(bundle["snapshots"]["metas"]["conteudo"], {})
        self.assertNotEqual(bundle["entrada_id"], self.prepare()["entrada_id"])

    def test_tampering_snapshots_is_detected_even_if_outer_id_is_recomputed(self):
        bundle = self.prepare()
        bundle["snapshots"]["metas"]["conteudo"]["alteracao"] = True
        bundle["entrada_id"] = entry.digest({k: v for k, v in bundle.items() if k != "entrada_id"})
        self.assertIn("snapshot_alterado", self.codes(bundle))

    def test_missing_indicator_or_unknown_unit_is_rejected(self):
        path = self.module_dir / "alpha.json"
        local = json.loads(path.read_text())
        local["indicadores"]["amostra"]["unidade_avaliativa"] = "inventada"
        self.write_json(path, local)
        self.assertIn("unidade_desconhecida", self.codes(self.prepare()))
        local["indicadores"] = {}
        self.write_json(path, local)
        self.assertIn("indicadores_divergentes", self.codes(self.prepare()))

    def test_ratios_require_explicit_denominator(self):
        contract = copy.deepcopy(self.contract)
        contract["indicadores_globais"]["fracao_l0_l2_limpo"]["denominador"] = None
        errors = entry.validate_contract(contract)
        self.assertIn("denominador_ausente", {item["codigo"] for item in errors})

    def test_untrusted_entry_structure_returns_diagnostics(self):
        for field, value in [("fonte", []), ("snapshots", []), ("diagnosticos", [{}]), ("diagnosticos", [{"gravidade": []}]), ("status", "aprovada"), ("status", [])]:
            with self.subTest(field=field):
                bundle = self.prepare()
                bundle[field] = value
                bundle["entrada_id"] = entry.digest({k: v for k, v in bundle.items() if k != "entrada_id"})
                self.assertTrue(any(error["gravidade"] == "bloqueio" for error in entry.validate_input(bundle)))

    def test_malformed_snapshot_wrappers_return_diagnostics(self):
        for value in [[1], {"estado": []}, {"estado": "presente", "conteudo": {}, "sha256": "0" * 64}, {"estado": "presente", "conteudo": {}, "sha256": "0" * 64, "formato": []}]:
            bundle = self.prepare()
            bundle["snapshots"]["catalogo"] = value
            bundle["entrada_id"] = entry.digest({k: v for k, v in bundle.items() if k != "entrada_id"})
            self.assertTrue(entry.validate_input(bundle))

    def test_absence_cannot_hide_content_or_erase_its_diagnostic(self):
        bundle = self.prepare(source_paths=dict(self.paths, adjudicacoes=None))
        bundle["snapshots"]["adjudicacoes"]["conteudo"] = {"sucesso": True}
        bundle["diagnosticos"] = []
        bundle["status"] = "valida"
        bundle["entrada_id"] = entry.digest({k: v for k, v in bundle.items() if k != "entrada_id"})
        self.assertIn("snapshot_invalido", self.codes(bundle))
        self.assertIn("ausencia_nao_diagnosticada", self.codes(bundle))

    def test_source_profiles_and_extra_module_blobs_are_checked(self):
        bundle = self.prepare()
        bundle["fonte"]["perfil"] = "formato_futuro"
        bundle["contratos_modulos"]["extra"] = copy.deepcopy(bundle["contratos_modulos"]["alpha"])
        bundle["entrada_id"] = entry.digest({k: v for k, v in bundle.items() if k != "entrada_id"})
        self.assertIn("fonte_invalida", self.codes(bundle))
        self.assertIn("registro_modulos_divergente", self.codes(bundle))

    def test_invalid_contracts_produce_blocked_input_instead_of_crashing(self):
        for contract in [[], dict(self.contract, formatos=[]), dict(self.contract, formatos={"codex_jsonl_v1": {"tipos_registro": 1}}), dict(self.contract, unidades=[])]:
            with self.subTest(contract=contract):
                self.write_json(self.contract_path, contract)
                self.assertEqual(self.prepare()["status"], "bloqueada")

    def test_invalid_optional_source_is_blocked_without_inventing_absence(self):
        self.paths["adjudicacoes"].write_text("{", encoding="utf-8")
        bundle = self.prepare()
        self.assertEqual(bundle["status"], "bloqueada")
        self.assertEqual(bundle["snapshots"]["adjudicacoes"]["estado"], "invalida")
        self.assertIn("fonte_invalida", self.codes(bundle))
        self.assertNotIn("ausencia_nao_diagnosticada", self.codes(bundle))

    def test_declared_fields_cannot_be_omitted_or_extended_silently(self):
        contract = dict(self.contract, interpretacao_oculta="não declarada")
        self.assertIn("campos_divergentes", {item["codigo"] for item in entry.validate_contract(contract)})
        path = self.module_dir / "alpha.json"
        local = json.loads(path.read_text())
        del local["unidade_contexto_legada"]
        self.write_json(path, local)
        self.assertEqual(self.prepare()["status"], "bloqueada")
        self.write_json(path, dict(local, unidade_contexto_legada="evento"))
        bundle = self.prepare(source_paths=dict(self.paths, adjudicacoes=None))
        del bundle["snapshots"]["adjudicacoes"]["formato"]
        bundle["entrada_id"] = entry.digest({k: v for k, v in bundle.items() if k != "entrada_id"})
        self.assertIn("campos_divergentes", self.codes(bundle))

    def test_cli_prepares_validates_and_preserves_published_entry(self):
        destination = self.root / "entrada.json"
        command = [sys.executable, str(ROOT / "ferramentas/entrada_medicao.py"), "preparar", str(self.rollout),
                   "--sessao-id", "900", "--saida", str(destination), "--contrato", str(self.contract_path),
                   "--contratos-modulos", str(self.module_dir)]
        for name, path in self.paths.items():
            command.extend([f"--{name}", str(path)])
        before = {path.name for path in self.root.iterdir()}
        for _ in range(2):
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "valida")
        original = destination.read_bytes()
        self.assertEqual({path.name for path in self.root.iterdir()} - before, {"entrada.json"})
        with self.rollout.open("ab") as handle:
            handle.write(b"registro posterior incompleto")
        validation = subprocess.run([sys.executable, str(ROOT / "ferramentas/entrada_medicao.py"),
                                     "validar", str(destination), "--rollout", str(self.rollout)], capture_output=True, text=True)
        self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)
        self.write_json(self.paths["metas"], {"nova": "configuração"})
        replacement = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(replacement.returncode, 1)
        self.assertIn("use outro arquivo", replacement.stdout)
        self.assertEqual(destination.read_bytes(), original)

    def test_module_change_preserves_other_module_contract_identity(self):
        first = self.prepare()
        self.catalog["modulos"][0]["versao_implementacao"] = "1.0.1"
        self.write_json(self.paths["catalogo"], self.catalog)
        second = self.prepare()
        self.assertNotEqual(first["entrada_id"], second["entrada_id"])
        self.assertNotEqual(entry.module_contract_id(first, "alpha"), entry.module_contract_id(second, "alpha"))
        self.assertEqual(entry.module_contract_id(first, "beta"), entry.module_contract_id(second, "beta"))

    def test_local_indicator_change_does_not_change_other_module_contract(self):
        first = self.prepare()
        path = self.module_dir / "alpha.json"
        local = json.loads(path.read_text())
        local["versao_contrato"] = "1.1.0"
        local["indicadores"]["amostra"]["ausencia_de_evidencia"] = "nova política local explícita"
        self.write_json(path, local)
        second = self.prepare()
        self.assertNotEqual(entry.module_contract_id(first, "alpha"), entry.module_contract_id(second, "alpha"))
        self.assertEqual(entry.module_contract_id(first, "beta"), entry.module_contract_id(second, "beta"))

    def test_extra_module_uses_registry_without_changing_common_structure(self):
        extra = self.module("gamma")
        self.catalog["modulos"].append(extra)
        self.write_json(self.paths["catalogo"], self.catalog)
        self.write_json(self.module_dir / "gamma.json", {
            "schema_contrato_modulo": 1, "versao_contrato": "1.0.0", "module_id": "gamma",
            "unidade_contexto_legada": "evento", "indicadores": {"amostra": self.indicator()}})
        bundle = self.prepare()
        self.assertEqual(bundle["status"], "valida")
        self.assertEqual(set(bundle["contratos_modulos"]), {"alpha", "beta", "gamma"})


class InstalledMeasurementContractTest(unittest.TestCase):
    def test_declared_contracts_cover_catalog_indicators_with_valid_units(self):
        contract = json.loads(entry.DEFAULT_CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(entry.validate_contract(contract), [])
        catalog = json.loads((ROOT / "evaluation/catalogo-modulos-v2.json").read_text(encoding="utf-8"))
        for module in catalog["modulos"]:
            with self.subTest(module=module["id"]):
                local = json.loads((entry.DEFAULT_MODULES / (module["id"] + ".json")).read_text(encoding="utf-8"))
                self.assertEqual(entry.validate_module_contract(local, module, contract), [])


if __name__ == "__main__":
    unittest.main()
