from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

import yaml

from ferramentas import _module_facade


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault(name, module)
    spec.loader.exec_module(module)
    return module


analyzer = _load(ROOT / "ferramentas" / "analisar-rollout.py", "fail_closed_analyzer")
generator = _load(
    ROOT / "ferramentas" / "gerar-avaliacao-sessao.py",
    "fail_closed_generator",
)


def _coverage(*receipts: str) -> dict:
    return {
        "block_present": True,
        "schema_present": True,
        "receipts": [
            {
                "module_id": raw.split("|")[0],
                "phase": raw.split("|")[1],
                "applicability": raw.split("|")[2],
                "units": int(raw.split("|")[3]),
                "complete": True,
            }
            for raw in receipts
        ],
    }


def _parsed_coverage(*receipts: str) -> dict:
    """Passa o envelope compacto real pelo parser do detector."""

    result = {
        _module_facade.COVERAGE_KEY: {
            _module_facade.COVERAGE_SCHEMA_KEY: _module_facade.COVERAGE_SCHEMA,
            "recibos": [],
        }
    }
    for raw in receipts:
        module_id, phase, applicability, units = raw.split("|")
        _module_facade.attach_coverage(
            result,
            module_id=module_id,
            phase=phase,
            applicability=applicability,
            units=int(units),
        )
    return analyzer._module_coverage_receipts(
        yaml.safe_dump(result, allow_unicode=True, sort_keys=False)
    )


_PREPARE_MODULES = (
    "turn_and_session_orchestration",
    "scene_world_projection",
    "sidequest_authoring",
    "sidequest_lifecycle",
    "causal_narrative_routing",
    "npc_continuity_and_social_behavior",
    "context_and_memory",
)
_CONCLUDE_MODULES = (
    "turn_and_session_orchestration",
    "context_and_memory",
    "npc_continuity_and_social_behavior",
    "rules_and_character_state",
    "narrative_delivery",
)


def _na_coverage_case(module_id: str, *, omit: str | None = None) -> dict:
    """Cria uma atividade pública cuja cobertura é explicitamente N/A."""

    if module_id in _PREPARE_MODULES:
        phase = "preparar"
        expected = _PREPARE_MODULES
        call = {
            "call_id": f"na-{module_id}",
            "command": (
                "poetry run cronica preparar --cena-id fail-closed "
                "--sem-oportunidade-sidequest"
            ),
            "command_executed": True,
            "output_success": True,
            "orchestration_receipt": {"state": "preparado"},
            "opportunity_assessment": {"classification": "nao_aplicavel"},
        }
    elif module_id in {"rules_and_character_state", "narrative_delivery"}:
        phase = "concluir"
        expected = _CONCLUDE_MODULES
        call = {
            "call_id": f"na-{module_id}",
            "command": "poetry run cronica concluir --ticket crn1.fixture",
            "command_executed": True,
            "output_success": True,
            "orchestration_receipt": {"state": "concluido"},
            "delivery_receipt": {},
        }
    elif module_id == "world_boundary_resolution":
        phase = "fronteira"
        expected = (module_id,)
        call = {
            "call_id": f"na-{module_id}",
            "command": (
                "poetry run python ferramentas/endpoints.py fronteira "
                "--data '1 Eleasis, 1372 DR' --hora 10:00"
            ),
            "command_executed": True,
            "output_success": True,
        }
    elif module_id == "adversarial_operations":
        phase = "consulta"
        expected = (module_id,)
        call = {
            "call_id": f"na-{module_id}",
            "command": (
                "poetry run python ferramentas/adversarial_operations.py status"
            ),
            "command_executed": True,
            "output_success": True,
        }
    else:  # pragma: no cover - torna fixture inválida ruidosa
        raise AssertionError(f"módulo sem cenário N/A: {module_id}")

    receipts = tuple(
        f"{expected_module}|{phase}|nao_aplicavel|1"
        for expected_module in expected
        if expected_module != omit
    )
    call["module_coverage"] = _parsed_coverage(*receipts)
    return call


def test_compact_receipt_is_versioned_and_deduplicated() -> None:
    result: dict = {}
    _module_facade.attach_coverage(
        result,
        module_id="context_and_memory",
        phase="preparar",
        applicability="aplicavel",
    )
    _module_facade.attach_coverage(
        result,
        module_id="context_and_memory",
        phase="preparar",
        applicability="nao_aplicavel",
    )

    block = result[_module_facade.COVERAGE_KEY]
    assert block[_module_facade.COVERAGE_SCHEMA_KEY] == 1
    assert block["recibos"] == [
        "context_and_memory|preparar|nao_aplicavel|1"
    ]


def test_catalog_applies_fail_closed_contract_to_all_modules() -> None:
    catalog = json.loads(
        (ROOT / "evaluation" / "catalogo-modulos-v2.json").read_text(encoding="utf-8")
    )
    contract = catalog["contrato_cobertura_fail_closed"]
    module_ids = {item["id"] for item in catalog["modulos"]}

    assert set(contract["modulos"]) == module_ids
    assert len(module_ids) == 12
    assert contract["atividade_sem_recibo"] == "falha_instrumentacao"
    assert contract["nd_exige_zero_atividade_avaliativa"] is True
    assert all(item["versao_avaliacao"] == "4.0.0" for item in catalog["modulos"])


def test_detector_requires_all_seven_prepare_receipts() -> None:
    receipts = (
        "turn_and_session_orchestration|preparar|aplicavel|1",
        "scene_world_projection|preparar|nao_aplicavel|1",
        "sidequest_authoring|preparar|indeterminado|1",
        "sidequest_lifecycle|preparar|nao_aplicavel|1",
        "causal_narrative_routing|preparar|nao_aplicavel|1",
        "npc_continuity_and_social_behavior|preparar|nao_aplicavel|1",
        "context_and_memory|preparar|aplicavel|1",
    )
    call = {
        "call_id": "prepare-1",
        "command": "poetry run cronica preparar --cena-id fail-closed --sem-oportunidade-sidequest",
        "command_executed": True,
        "output_success": True,
        "orchestration_receipt": {"state": "preparado"},
        "opportunity_assessment": {"classification": "indeterminado"},
        "module_coverage": _coverage(*receipts),
    }
    gates = analyzer._module_coverage_gates(
        [{"turn_id": "turn-1", "calls": [call]}]
    )

    for module_id in (
        "turn_and_session_orchestration",
        "scene_world_projection",
        "sidequest_authoring",
        "sidequest_lifecycle",
        "causal_narrative_routing",
        "npc_continuity_and_social_behavior",
        "context_and_memory",
    ):
        assert gates[module_id]["activity_units"] == 1
        assert gates[module_id]["coverage_complete"] is True
        assert gates[module_id]["complete_receipts"] == 1


def test_detector_marks_missing_and_semantically_incomplete_receipts() -> None:
    call = {
        "call_id": "prepare-2",
        "command": "poetry run cronica preparar --cena-id fail-closed --sem-oportunidade-sidequest",
        "command_executed": True,
        "output_success": True,
        "orchestration_receipt": {"state": "preparado"},
        "opportunity_assessment": None,
        "module_coverage": _coverage(
            "turn_and_session_orchestration|preparar|aplicavel|1",
            "scene_world_projection|preparar|nao_aplicavel|1",
            "sidequest_authoring|preparar|indeterminado|1",
            "sidequest_lifecycle|preparar|nao_aplicavel|1",
            "causal_narrative_routing|preparar|nao_aplicavel|1",
            "npc_continuity_and_social_behavior|preparar|nao_aplicavel|1",
        ),
    }
    gates = analyzer._module_coverage_gates(
        [{"turn_id": "turn-2", "calls": [call]}]
    )

    assert gates["context_and_memory"]["missing_receipts"] == 1
    assert gates["context_and_memory"]["coverage_complete"] is False
    assert gates["sidequest_authoring"]["incomplete_receipts"] == 1
    assert gates["sidequest_authoring"]["coverage_complete"] is False


def test_scoreboard_reserves_nd_for_zero_activity() -> None:
    catalog = json.loads(
        (ROOT / "evaluation" / "catalogo-modulos-v2.json").read_text(encoding="utf-8")
    )
    context = next(
        item for item in catalog["modulos"] if item["id"] == "context_and_memory"
    )
    targets = json.loads(
        (ROOT / "evaluation" / "metas-avaliacao-v2.json").read_text(encoding="utf-8")
    )
    base_gate = {
        "schema": 1,
        "module_id": "context_and_memory",
        "activity_units": 0,
        "receipts": 0,
        "complete_receipts": 0,
        "applicable_units": 0,
        "not_applicable_units": 0,
        "indeterminate_units": 0,
        "missing_receipts": 0,
        "incomplete_receipts": 0,
        "duplicate_receipts": 0,
        "coverage_complete": True,
    }

    def row(gate: dict) -> dict:
        return generator._module_summary_v2(
            [context],
            {"events": [], "player_feedback": [], "semantic_audits": []},
            [],
            targets,
            0,
            module_coverage_gates={"context_and_memory": gate},
        )[0]

    no_activity = row(base_gate)
    assert no_activity["avaliacao_ativacao"] == "N/D"
    assert no_activity["aplicabilidade_avaliacao"] == "sem_atividade"

    missing = row(
        {
            **base_gate,
            "activity_units": 1,
            "missing_receipts": 1,
            "coverage_complete": False,
        }
    )
    assert missing["avaliacao_ativacao"] == "falha de instrumentação"
    assert missing["aplicabilidade_avaliacao"] == "falha_instrumentacao"
    assert missing["nota_desempenho_provisoria_0a100"] is None

    not_applicable = row(
        {
            **base_gate,
            "activity_units": 1,
            "receipts": 1,
            "complete_receipts": 1,
            "not_applicable_units": 1,
        }
    )
    assert not_applicable["avaliacao_ativacao"] == "não aplicável"
    assert not_applicable["aplicabilidade_avaliacao"] == "nao_aplicavel"


class FailClosedEvaluationTest(unittest.TestCase):
    """Mantém o contrato novo dentro do discovery oficial por ``unittest``."""

    def test_compact_receipt_is_versioned_and_deduplicated(self) -> None:
        test_compact_receipt_is_versioned_and_deduplicated()

    def test_catalog_applies_fail_closed_contract_to_all_modules(self) -> None:
        test_catalog_applies_fail_closed_contract_to_all_modules()
        catalog = json.loads(
            (ROOT / "evaluation" / "catalogo-modulos-v2.json").read_text(
                encoding="utf-8"
            )
        )
        module_ids = {item["id"] for item in catalog["modulos"]}
        self.assertEqual(
            set(analyzer.FAIL_CLOSED_MODULE_IDS),
            module_ids - {"canonical_quest_integration"},
        )
        self.assertEqual(len(analyzer.FAIL_CLOSED_MODULE_IDS), 11)

    def test_detector_requires_all_seven_prepare_receipts(self) -> None:
        test_detector_requires_all_seven_prepare_receipts()

    def test_detector_marks_missing_and_incomplete_receipts(self) -> None:
        test_detector_marks_missing_and_semantically_incomplete_receipts()

    def test_scoreboard_reserves_nd_for_zero_activity(self) -> None:
        test_scoreboard_reserves_nd_for_zero_activity()

    def test_detector_reads_real_yaml_coverage_envelope(self) -> None:
        result: dict = {}
        _module_facade.attach_coverage(
            result,
            module_id="scene_world_projection",
            phase="preparar",
            applicability="nao_aplicavel",
        )
        parsed = analyzer._module_coverage_receipts(
            yaml.safe_dump(
                result,
                allow_unicode=True,
                sort_keys=False,
            )
        )
        self.assertTrue(parsed["block_present"])
        self.assertTrue(parsed["schema_present"])
        self.assertEqual(
            parsed["receipts"][0],
            {
                "module_id": "scene_world_projection",
                "phase": "preparar",
                "applicability": "nao_aplicavel",
                "units": 1,
                "complete": True,
            },
        )

    def test_missing_na_receipt_fails_closed_for_every_module(self) -> None:
        """N/A só existe com recibo; apagar um recibo nunca pode virar N/A/N/D."""

        catalog = json.loads(
            (ROOT / "evaluation" / "catalogo-modulos-v2.json").read_text(
                encoding="utf-8"
            )
        )
        catalog_by_id = {item["id"]: item for item in catalog["modulos"]}
        targets = json.loads(
            (ROOT / "evaluation" / "metas-avaliacao-v2.json").read_text(
                encoding="utf-8"
            )
        )
        module_ids = tuple(analyzer.FAIL_CLOSED_MODULE_IDS)
        self.assertEqual(len(module_ids), 11)

        def scoreboard_row(module_id: str, gate: dict) -> dict:
            return generator._module_summary_v2(
                [catalog_by_id[module_id]],
                {"events": [], "player_feedback": [], "semantic_audits": []},
                [],
                targets,
                0,
                module_coverage_gates={module_id: gate},
            )[0]

        for module_id in module_ids:
            with self.subTest(module=module_id):
                baseline_call = _na_coverage_case(module_id)
                expected_ids = {
                    expected_id
                    for expected_id, _phase in analyzer._expected_module_activities(
                        baseline_call
                    )
                }
                self.assertIn(module_id, expected_ids)

                baseline_gates = analyzer._module_coverage_gates(
                    [{"turn_id": f"baseline-{module_id}", "calls": [baseline_call]}]
                )
                baseline_gate = baseline_gates[module_id]
                self.assertEqual(baseline_gate["activity_units"], 1)
                self.assertEqual(baseline_gate["complete_receipts"], 1)
                self.assertEqual(baseline_gate["not_applicable_units"], 1)
                self.assertEqual(baseline_gate["missing_receipts"], 0)
                self.assertTrue(baseline_gate["coverage_complete"])

                baseline_row = scoreboard_row(module_id, baseline_gate)
                self.assertEqual(
                    baseline_row["avaliacao_ativacao"], "não aplicável"
                )
                self.assertEqual(
                    baseline_row["aplicabilidade_avaliacao"], "nao_aplicavel"
                )

                mutated_call = _na_coverage_case(module_id, omit=module_id)
                mutated_gates = analyzer._module_coverage_gates(
                    [{"turn_id": f"mutated-{module_id}", "calls": [mutated_call]}]
                )
                mutated_gate = mutated_gates[module_id]
                self.assertEqual(mutated_gate["activity_units"], 1)
                self.assertEqual(mutated_gate["receipts"], 0)
                self.assertEqual(mutated_gate["complete_receipts"], 0)
                self.assertEqual(mutated_gate["not_applicable_units"], 0)
                self.assertEqual(mutated_gate["missing_receipts"], 1)
                self.assertEqual(mutated_gate["incomplete_receipts"], 0)
                self.assertFalse(mutated_gate["coverage_complete"])
                self.assertEqual(
                    mutated_gate["assessments"][0]["receipt_status"], "ausente"
                )

                # A mutação é isolada: todos os demais recibos exigidos pela
                # mesma porta pública permanecem completos e explicitamente N/A.
                for sibling_id in expected_ids - {module_id}:
                    sibling_gate = mutated_gates[sibling_id]
                    self.assertEqual(sibling_gate["activity_units"], 1)
                    self.assertEqual(sibling_gate["complete_receipts"], 1)
                    self.assertEqual(sibling_gate["not_applicable_units"], 1)
                    self.assertEqual(sibling_gate["missing_receipts"], 0)
                    self.assertTrue(sibling_gate["coverage_complete"])

                mutated_row = scoreboard_row(module_id, mutated_gate)
                self.assertEqual(
                    mutated_row["avaliacao_ativacao"], "falha de instrumentação"
                )
                self.assertEqual(
                    mutated_row["aplicabilidade_avaliacao"],
                    "falha_instrumentacao",
                )
                self.assertNotIn(
                    mutated_row["avaliacao_ativacao"], {"N/D", "não aplicável"}
                )
                self.assertIsNone(
                    mutated_row["nota_desempenho_provisoria_0a100"]
                )
                self.assertEqual(mutated_row["recibos_cobertura_ausentes"], 1)
                self.assertIn(
                    "1 recibo(s) de cobertura ausente(s)",
                    mutated_row["principais_problemas_de_ativacao"],
                )
