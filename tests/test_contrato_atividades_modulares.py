"""Associação e omissão de subfases usando produtores reais em repositório isolado."""
from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

import yaml

from ferramentas import atividades_modulares as contract
from ferramentas import _module_facade as facade
from ferramentas import verificar_aceite_avaliacao as acceptance
from tests import test_analisar_rollout_atividades as fixture
from tests import test_cronica_iniciativa_nv16 as initiative_fixture
from tests.test_resultados_operacoes import control
from tests import test_analisar_rollout_resultados as operation_fixture
from tests.test_fail_closed_evaluation import generator

analyzer = fixture.mod
NPC = "npc_continuity_and_social_behavior"


class ModuleActivityContractTest(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(prefix="contrato-atividades-")
        self.repo = Path(self.temp.name)
        self.token = initiative_fixture.CronicaInitiativeCompositionTest()._automatic_ticket()
        self.ticket_id, self.payload = contract.observed_ticket(self.token)
        self.command = f"poetry run cronica concluir --ticket {self.token}"

    def tearDown(self):
        self.temp.cleanup()

    def conclusion(self):
        # Writer anterior substituído; a instalação de iniciativa e a emissão
        # de seu recibo são reais e só escrevem no TemporaryDirectory.
        with mock.patch.object(initiative_fixture.layer, "_BASE_CONCLUDE", return_value={
            "fase": "concluida", "ticket_id": "interno",
            "transacao": {"id": "tx-atividade"},
        }):
            result = initiative_fixture.layer.conclude(self.repo, self.token, {
                "jogador": "Ren observa.", "narracao": "A conversa não se abre.",
                "resumo": "Sem abertura social.", "modo": "interação", "deltas": [],
            })
        for module in contract.CONCLUDE_MODULES:
            facade.attach_coverage(result, module_id=module, phase="concluir", applicability="nao_aplicavel")
        result["interacao"] = {"schema_narrative_interaction": 1, "interaction_ref": "S001-I0001"}
        return initiative_fixture.layer._base._turn_orchestration.publish_turn(result, "concluir")

    def analyze(self, result, *, rows=None, command=None):
        output = "Process exited with code 0\n" + yaml.safe_dump(result, allow_unicode=True, sort_keys=False)
        rows = rows or [fixture._call("conclude", command or self.command), fixture._result("conclude", output)]
        path = self.repo / "rollout.jsonl"
        path.write_text("\n".join([json.dumps({"type": "event_msg", "payload": {
            "type": "task_started", "turn_id": "t1"}}), *rows]) + "\n", encoding="utf-8")
        return analyzer.analyze(path)

    def subactivity(self, report):
        return next(item for item in report["module_activities"]["activities"]
                    if item["fase"] == "concluir_iniciativa")

    def test_real_producer_and_detector_share_phase_ticket_version_and_interaction(self):
        report = self.analyze(self.conclusion())
        activity = self.subactivity(report)
        self.assertEqual(report["module_activities"]["orphan_receipts"], [])
        self.assertEqual(activity["receipt_state"], "completo")
        self.assertEqual(activity["fonte_expectativa"], "ticket")
        self.assertEqual(activity["versao_produtor"], contract.producer_hash())
        self.assertEqual(activity["contrato_atividades"], contract.CONTRACT_VERSION)
        self.assertEqual(activity["ticket_ref"], contract.object_ref("ticket_id", self.ticket_id))
        self.assertEqual(activity["interacao_ref"], "S001-I0001")
        gate = report["module_coverage_gates"][NPC]
        self.assertEqual(gate["activity_units"], 2)  # duas fases, não dois efeitos
        self.assertEqual(gate["duplicate_receipts"], 0)
        self.assertTrue(gate["coverage_complete"])

    def test_removing_only_subreceipt_is_missing_even_with_generic_receipt(self):
        result = self.conclusion()
        result["iniciativa_elenco"]["cobertura_avaliacao_modular"]["recibos"] = []
        report = self.analyze(result)
        self.assertEqual(self.subactivity(report)["receipt_state"], "ausente")
        self.assertEqual(report["module_coverage_gates"][NPC]["missing_receipts"], 1)

    def test_sidequest_installation_does_not_require_a_prepare_opportunity_receipt(self):
        result = self.conclusion()
        result["sidequest_emergente"] = {"resultado": "oferta_nao_materializada"}
        facade.attach_coverage(result["sidequest_emergente"], module_id="sidequest_authoring",
                               phase="instalar", applicability="nao_aplicavel")
        contract.bind_output(result)
        report = self.analyze(result)
        gate = report["module_coverage_gates"]["sidequest_authoring"]
        self.assertEqual(gate["activity_units"], 1)
        self.assertEqual(gate["not_applicable_units"], 1)
        self.assertTrue(gate["coverage_complete"])

    def test_global_repo_option_does_not_hide_the_operation(self):
        report = self.analyze(self.conclusion(), command=f"poetry run cronica --repo /tmp/isolado concluir --ticket {self.token}")
        self.assertEqual(self.subactivity(report)["receipt_state"], "completo")

    def test_all_published_routes_use_existing_phases(self):
        for (program, operation), (module, phase) in contract.DIRECT_ROUTES.items():
            with self.subTest(program=program, operation=operation):
                self.assertEqual(contract.phase_contract(module, phase)["unidades"], 1)
                self.assertEqual(contract.operation_phases(program, [operation]), [(module, phase)])
        for (operation, module, phase) in contract.SUBPHASES:
            self.assertTrue(contract.phase_contract(module, phase)["escopo_negativa"])

    def test_unknown_contract_version_keeps_the_activity_incomplete(self):
        result = self.conclusion()
        result["iniciativa_elenco"]["cobertura_avaliacao_modular"]["contrato_atividades"] = "99.0.0"
        self.assertEqual(self.subactivity(self.analyze(result))["receipt_state"], "incompleto")

    def test_receipt_association_does_not_promote_uncertain_execution_to_success(self):
        result = {}
        facade.attach_coverage(result, module_id="context_and_memory", phase="consulta", applicability="aplicavel")
        command = "poetry run python ferramentas/contexto.py status"
        output = yaml.safe_dump(result, sort_keys=False)
        report = self.analyze(result, rows=[fixture._call("read", command), fixture._result("read", output)])
        self.assertEqual(report["operation_outcomes"]["operations"][0]["state"], "evidencia_insuficiente")
        activity = report["module_activities"]["activities"][0]
        self.assertEqual(activity["operation_state"], "evidencia_insuficiente")
        self.assertEqual(activity["receipt_state"], "completo")
        self.assertEqual(report["module_activities"]["orphan_receipts"], [])

    def test_json_coverage_with_host_prefix_retains_the_same_binding_as_yaml(self):
        result = {}
        facade.attach_coverage(result, module_id="context_and_memory", phase="consulta", applicability="nao_aplicavel")
        yaml_output = yaml.safe_dump(result, sort_keys=False)
        json_output = "Wall time: 0.1\nProcess exited with code 0\nOutput:\n" + json.dumps(result)
        self.assertEqual(analyzer._module_coverage_receipts(yaml_output)["receipts"],
                         analyzer._module_coverage_receipts(json_output)["receipts"])

    def test_removing_whole_subenvelope_still_leaves_independent_ticket_obligation(self):
        result = self.conclusion()
        del result["iniciativa_elenco"]
        report = self.analyze(result)
        self.assertEqual(self.subactivity(report)["receipt_state"], "ausente")
        self.assertEqual(self.subactivity(report)["fonte_expectativa"], "ticket")

    def test_other_ticket_receipt_is_contradictory_and_orphan(self):
        result = self.conclusion()
        block = result["iniciativa_elenco"]["cobertura_avaliacao_modular"]
        block["vinculo"]["ticket_ref"] = contract.object_ref("ticket_id", "outro-ticket")
        report = self.analyze(result)
        self.assertEqual(self.subactivity(report)["receipt_state"], "contraditorio")
        self.assertEqual(report["module_activities"]["orphan_receipts"][0]["reason"], "ticket_divergente")
        self.assertFalse(report["module_coverage_gates"][NPC]["coverage_complete"])
        self.assertTrue(report["module_coverage_gates"]["context_and_memory"]["coverage_complete"])

    def test_wrong_object_does_not_satisfy_the_subactivity(self):
        result = self.conclusion()
        result["iniciativa_elenco"]["cobertura_avaliacao_modular"]["vinculo"]["objeto_ref"] = contract.object_ref("ticket_id", "outro")
        report = self.analyze(result)
        self.assertEqual(self.subactivity(report)["receipt_state"], "contraditorio")
        self.assertEqual(report["module_activities"]["orphan_receipts"][0]["reason"], "objeto_divergente")

    def test_unknown_phase_is_rejected_by_producer_and_remains_orphan_in_observed_output(self):
        with self.assertRaisesRegex(ValueError, "fora do contrato"):
            facade.attach_coverage({}, module_id=NPC, phase="inventada", applicability="aplicavel")
        result = self.conclusion()
        result["cobertura_avaliacao_modular"]["recibos"].append(f"{NPC}|inventada|aplicavel|1")
        report = self.analyze(result)
        self.assertEqual(report["module_activities"]["orphan_receipts"][0]["fase"], "inventada")
        self.assertFalse(report["module_coverage_gates"][NPC]["coverage_complete"])

    def test_duplicate_and_conflicting_receipts_have_different_failure_states(self):
        base = self.conclusion()
        for applicability, status, field in (("aplicavel", "duplicado", "duplicate_receipts"),
                                              ("nao_aplicavel", "contraditorio", "contradictory_receipts")):
            with self.subTest(status=status):
                result = copy.deepcopy(base)
                result["iniciativa_elenco"]["cobertura_avaliacao_modular"]["recibos"].append(
                    f"{NPC}|concluir_iniciativa|{applicability}|1")
                report = self.analyze(result)
                self.assertEqual(self.subactivity(report)["receipt_state"], status)
                self.assertGreater(report["module_coverage_gates"][NPC][field], 0)

    def test_new_negative_requires_cause_and_examined_scope(self):
        result = self.conclusion()
        block = result["cobertura_avaliacao_modular"]
        key = f"{NPC}|concluir"
        negative = {"causa": "", "escopo": "fatos_sociais_do_lote"}
        block.setdefault("negativas", {})[key] = negative
        default = contract.phase_contract(NPC, "concluir")
        self.assertTrue(default["causa_negativa"])
        self.assertEqual(negative["escopo"], "fatos_sociais_do_lote")
        negative["causa"] = ""
        report = self.analyze(result)
        generic = next(item for item in report["module_activities"]["activities"]
                       if item["module_id"] == NPC and item["fase"] == "concluir")
        self.assertEqual(generic["receipt_state"], "incompleto")

    def test_retry_and_recovery_keep_logical_activity_without_a_second_effect(self):
        original = self.conclusion()
        for outcome in ("replay_sem_duplicacao", "reparo_recuperado_sem_duplicacao"):
            with self.subTest(outcome=outcome):
                replay = copy.deepcopy(original)
                replay["orquestracao"]["commit"].update(resultado=outcome, efeito_novo=False)
                first = "Process exited with code 0\n" + yaml.safe_dump(original, sort_keys=False)
                second = "Process exited with code 0\n" + yaml.safe_dump(replay, sort_keys=False)
                report = self.analyze(original, rows=[fixture._call("first", self.command), fixture._result("first", first),
                    fixture._call("retry", self.command), fixture._result("retry", second)])
                activities = [item for item in report["module_activities"]["activities"] if item["fase"] == "concluir_iniciativa"]
                self.assertEqual(len(activities), 2)
                self.assertEqual(activities[0]["atividade_logica_id"], activities[1]["atividade_logica_id"])
                self.assertNotEqual(activities[0]["atividade_id"], activities[1]["atividade_id"])
                self.assertTrue(activities[1]["reutilizada"])
                self.assertEqual(report["module_coverage_gates"][NPC]["duplicate_receipts"], 0)

    def test_fragment_and_repeated_terminal_result_do_not_duplicate_subactivity(self):
        result = self.conclusion()
        output = yaml.safe_dump(result, sort_keys=False)
        split = output.index("iniciativa_elenco:") + 20
        pending = json.dumps({"session_id": 42, "output": output[:split]})
        final = json.dumps({"exit_code": 0, "output": output[split:]})
        report = self.analyze(result, rows=[fixture._call("conclude", self.command), fixture._result("conclude", pending),
            control("t1", "resume", "functions.write_stdin", {"session_id": 42}), operation_fixture._output("t1", "resume", final),
            control("t1", "duplicate", "functions.write_stdin", {"session_id": 42}), operation_fixture._output("t1", "duplicate", final)])
        direct = self.analyze(result)
        self.assertEqual(self.subactivity(report)["atividade_id"], self.subactivity(direct)["atividade_id"])
        self.assertEqual(report["module_activities"]["summary"]["activities"], 6)
        self.assertEqual(report["module_activities"]["orphan_receipts"], [])

    def test_orphan_with_zero_expected_activity_blocks_only_its_module_summary(self):
        result = {"consulta": "status"}
        facade.attach_coverage(result, module_id="context_and_memory", phase="consulta", applicability="aplicavel")
        facade.attach_coverage(result, module_id="world_boundary_resolution", phase="fronteira", applicability="aplicavel")
        report = self.analyze(result, command="poetry run python ferramentas/contexto.py status")
        catalog = json.loads((fixture.ROOT / "evaluation/catalogo-modulos-v2.json").read_text())["modulos"]
        targets = json.loads((fixture.ROOT / "evaluation/metas-avaliacao-v2.json").read_text())
        rows = generator._module_summary_v2(catalog, report["modular_ledger_v2"], [], targets, 0,
                                           module_coverage_gates=report["module_coverage_gates"])
        world = next(row for row in rows if row["modulo"] == "world_boundary_resolution")
        memory = next(row for row in rows if row["modulo"] == "context_and_memory")
        self.assertEqual(world["aplicabilidade_avaliacao"], "falha_instrumentacao")
        self.assertEqual(world["recibos_cobertura_orfaos"], 1)
        self.assertIsNone(world["nota_desempenho_provisoria_0a100"])
        self.assertNotEqual(memory["aplicabilidade_avaliacao"], "falha_instrumentacao")

    def test_native_reanalysis_reads_only_the_declared_frozen_prefix(self):
        self.analyze(self.conclusion())
        path = self.repo / "rollout.jsonl"
        frozen = path.read_bytes()
        historical = {"sessao_id": "001", "fonte": {
            "corte_bytes": len(frozen), "sha256": hashlib.sha256(frozen).hexdigest(),
            "bruto_versionado": False,
        }, "desenvolvimento": [{"ancoras": []}], "reservado": [{"ancoras": []}]}
        future = [fixture._call("future", "poetry run cronica sessao status"),
                  fixture._result("future", "Process exited with code 0\n")]
        path.write_bytes(frozen + ("\n".join(future) + "\n").encode())
        before = path.read_bytes()
        result = acceptance.measure_native_activities(path, historical)
        self.assertEqual(result["metricas_operacionais"]["tool_calls"], 1)
        self.assertEqual(result["atividades"]["por_fase"][f"{NPC}|concluir_iniciativa"], 1)
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
