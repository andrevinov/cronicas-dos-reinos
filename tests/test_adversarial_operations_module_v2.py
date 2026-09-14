from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml


ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import adversarial_operations as adversarial
from ferramentas import preflight
import mundo
import pressao_narrativa
import resolver_fronteira
from tests.test_concurrent_world_operations import (
    CHANNEL_EVIDENCE,
    ConcurrentOperationFixture,
    RESULT_EVIDENCE,
)
from test_planos_adversarios import AdversarialPlanFixture


class AdversarialOperationsModuleContractTest(unittest.TestCase):
    def test_aliases_catalogo_e_fachada_publicam_um_unico_pai(self) -> None:
        catalog = json.loads(
            (ROOT / "evaluation/catalogo-modulos-v2.json").read_text(
                encoding="utf-8"
            )
        )
        module = next(
            item for item in catalog["modulos"] if item["id"] == adversarial.MODULE_ID
        )
        aliases = {
            alias
            for capability in module["subcapacidades"]
            for alias in capability["aliases_v1"]
        }

        self.assertEqual(catalog["versao_catalogo"], "3.0.0")
        self.assertEqual(module["versao_implementacao"], "1.0.0")
        self.assertEqual(aliases, set(adversarial.LEGACY_ALIASES))
        self.assertEqual(
            {item["id"] for item in module["subcapacidades"]},
            set(adversarial.CAPABILITIES),
        )
        self.assertIs(pressao_narrativa.operations, adversarial)
        self.assertIs(resolver_fronteira.operacoes_adversariais, adversarial)

    def test_preflight_substitui_os_dois_checks_internos_por_um_gate(self) -> None:
        commands = [
            tuple(item.comando[1:])
            for item in preflight.checks(incluir_testes=False)
        ]
        public = ("ferramentas/adversarial_operations.py", "check")
        self.assertEqual(commands.count(public), 1)
        self.assertFalse(preflight._ADVERSARIAL_INTERNAL_CHECKS & set(commands))

    def test_fontes_preservam_donos_e_nao_ha_estado_paralelo(self) -> None:
        self.assertEqual(
            set(adversarial.SOURCE_OWNERSHIP),
            {
                "integrity_policy",
                "adversarial_contracts",
                "operation_index",
                "operation_control",
                "operation_contracts",
                "frozen_encounters",
                "recovery_journal",
            },
        )
        self.assertEqual(len(set(adversarial.SOURCE_OWNERSHIP.values())), 7)
        report = adversarial.check(ROOT)
        self.assertTrue(report["ok"], report["erros"])
        self.assertFalse(report["contrato"]["parallel_state"])
        self.assertFalse(report["contrato"]["historical_contract_rewrite"])
        self.assertEqual(report["contrato"]["additional_orchestration_calls"], 0)

    def test_violacao_de_integridade_fica_fora_da_media_modular(self) -> None:
        failure = {"ok": False, "erros": ["capacidade fabricada"]}
        healthy = {"ok": True, "erros": []}
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(adversarial._integrity, "validate_repo", return_value=failure),
            patch.object(adversarial._operations, "check", return_value=healthy),
        ):
            report = adversarial.check(Path(temporary))

        guardrail = report["avaliacao_guardrail"]
        self.assertFalse(report["ok"])
        self.assertEqual(guardrail["estado"], "violado")
        self.assertFalse(guardrail["participa_media_modular"])
        self.assertIn(
            "adversarial_contract_integrity: capacidade fabricada",
            guardrail["violacoes"],
        )


class UnifiedAdversarialOperationTest(ConcurrentOperationFixture):
    def hashes(self) -> dict[str, str]:
        return {
            str(path.relative_to(self.repo)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in self.repo.rglob("*")
            if path.is_file()
        }

    def through_facade(self):
        proposal = self.group_proposal()
        prepared = adversarial.prepare(self.repo, proposal)
        group = adversarial.materialize(
            self.repo,
            proposal,
            prepared["preparacao_id"],
        )
        committed = adversarial.commit_group(self.repo, group["grupo_operacoes_id"])
        return proposal, prepared, group, committed

    def test_duas_frentes_usam_o_mesmo_contrato_e_reservas_separadas(self) -> None:
        _, prepared, _, committed = self.through_facade()

        self.assertEqual(prepared["evento_modular"], "consulta")
        self.assertTrue(prepared["operacoes_simultaneas"])
        self.assertEqual(committed["evento_modular"], "compromisso")
        self.assertEqual(committed["quantidade_frentes"], 2)
        self.assertEqual(
            committed["operacoes_comprometidas"],
            ["ataque_comitiva", "extracao_testemunha"],
        )
        state = adversarial.operation_control_state(self.repo)
        owners = {
            (row["grupo_operacoes_id"], row["operacao_id"])
            for row in state["reservas_exclusivas"].values()
        }
        self.assertEqual(
            {operation_id for _, operation_id in owners},
            {"ataque_comitiva", "extracao_testemunha"},
        )

    def test_recurso_exclusivo_duplicado_falha_antes_da_mutacao(self) -> None:
        proposal = self.group_proposal(same_cell=True)
        before = self.hashes()
        with self.assertRaisesRegex(adversarial.ConcurrentOperationError, "duplicada"):
            adversarial.prepare(self.repo, proposal)
        self.assertEqual(before, self.hashes())
        self.assertFalse((self.repo / adversarial.INDEX).exists())

    def test_capacidade_removida_falha_antes_do_compromisso(self) -> None:
        proposal = self.group_proposal()
        prepared = adversarial.prepare(self.repo, proposal)
        group = adversarial.materialize(
            self.repo,
            proposal,
            prepared["preparacao_id"],
        )
        actor_path = self.repo / "narrador/elenco/agentes/rede_cinzenta.yaml"
        actor = yaml.safe_load(actor_path.read_text(encoding="utf-8"))
        actor["metodos_operacionais"] = {}
        actor_path.write_text(
            yaml.safe_dump(actor, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        before = self.hashes()

        with self.assertRaisesRegex(
            adversarial.ConcurrentOperationError, "capacidade indisponível"
        ):
            adversarial.commit_group(self.repo, group["grupo_operacoes_id"])

        self.assertEqual(before, self.hashes())

    def test_retry_de_compromisso_e_efeito_nao_duplica_estado(self) -> None:
        _, _, group, _ = self.through_facade()
        before_commit_retry = self.hashes()
        retried_commit = adversarial.commit_group(
            self.repo, group["grupo_operacoes_id"]
        )
        self.assertEqual(retried_commit["resultado_modular"], "retry_sem_duplicacao")
        self.assertFalse(retried_commit["efeito_materializado"])
        self.assertEqual(before_commit_retry, self.hashes())

        first = adversarial.resolve_operation(
            self.repo,
            "ataque_comitiva",
            self.proof(RESULT_EVIDENCE),
            RESULT_EVIDENCE,
        )
        before_effect_retry = self.hashes()
        second = adversarial.resolve_operation(
            self.repo,
            "ataque_comitiva",
            self.proof(RESULT_EVIDENCE),
            RESULT_EVIDENCE,
        )
        self.assertEqual(first["evento_modular"], "efeito_material")
        self.assertTrue(first["efeito_materializado"])
        self.assertEqual(second["resultado_modular"], "retry_sem_duplicacao")
        self.assertFalse(second["efeito_materializado"])
        self.assertEqual(before_effect_retry, self.hashes())

    def test_consequencia_informacional_atravessa_a_fachada(self) -> None:
        _, _, group, _ = self.through_facade()
        delivered = adversarial.deliver_information(
            self.repo,
            "extracao_testemunha",
            "mensageiro_templo",
            ["A casa do alvorecer foi atacada."],
            self.proof(CHANNEL_EVIDENCE),
            now=mundo.WorldInstant(self.now.minute + 12),
        )

        self.assertEqual(delivered["module_id"], adversarial.MODULE_ID)
        self.assertTrue(group["grupo_operacoes_id"].startswith("gop-"))
        self.assertEqual(delivered["evento_modular"], "efeito_material")
        self.assertEqual(
            delivered["resultado_modular"],
            "consequencia_informacional_entregue",
        )
        self.assertTrue(delivered["efeito_materializado"])
        self.assertEqual(delivered["fatos"], ["A casa do alvorecer foi atacada."])

    def test_ordem_de_resolucao_nao_altera_resultados_comprometidos(self) -> None:
        def resolve(fixture, order):
            proposal = fixture.group_proposal()
            prepared = adversarial.prepare(fixture.repo, proposal)
            group = adversarial.materialize(
                fixture.repo, proposal, prepared["preparacao_id"]
            )
            adversarial.commit_group(fixture.repo, group["grupo_operacoes_id"])
            frozen = {
                operation_id: adversarial.project_operation_snapshot(
                    fixture.repo, operation_id
                )["encontro"]
                for operation_id in order
            }
            for operation_id in order:
                adversarial.resolve_operation(
                    fixture.repo,
                    operation_id,
                    fixture.proof(RESULT_EVIDENCE),
                    RESULT_EVIDENCE,
                )
            rows = adversarial.operation_control_state(fixture.repo)["grupos"][
                group["grupo_operacoes_id"]
            ]["operacoes"]
            return frozen, {
                operation_id: rows[operation_id]["resolucao"]
                for operation_id in sorted(rows)
            }

        first = resolve(self, ["ataque_comitiva", "extracao_testemunha"])
        other = ConcurrentOperationFixture(methodName="runTest")
        other.setUp()
        try:
            second = resolve(other, ["extracao_testemunha", "ataque_comitiva"])
        finally:
            other.tearDown()
        self.assertEqual(first, second)


class SimpleAdversarialOperationTest(AdversarialPlanFixture):
    def test_operacao_simples_atravessa_a_mesma_fachada(self) -> None:
        proposal = self.proposal_from_plans()
        selected = proposal["operacoes"][0]
        proposal["operacoes"] = [selected]
        proposal["canais"] = [
            channel
            for channel in proposal["canais"]
            if channel["operacao_origem"] == selected["id"]
        ]

        prepared = adversarial.prepare(self.repo, proposal)
        group = adversarial.materialize(
            self.repo, proposal, prepared["preparacao_id"]
        )
        committed = adversarial.commit_group(self.repo, group["grupo_operacoes_id"])

        self.assertFalse(prepared["operacoes_simultaneas"])
        self.assertEqual(prepared["quantidade_frentes"], 1)
        self.assertEqual(committed["operacoes_comprometidas"], [selected["id"]])
        self.assertFalse(committed["operacoes_simultaneas"])


if __name__ == "__main__":
    unittest.main()
