from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import sidequest_authoring_capsule as capsule
import sidequests_integracao_runtime as integration
import test_emergent_sidequest_authoring_registry_v2 as task41
import test_task46_integration_transaction as task46


def capsule_from_legacy(block: dict) -> dict:
    return {
        "schema": capsule.SCHEMA,
        "aventura": copy.deepcopy(block["quest"]),
        "recompensas": copy.deepcopy(block["contrato_recompensa"]),
        "adversidade": copy.deepcopy(block["contrato_adversarial"]),
        "progressao": copy.deepcopy(block["contrato_progressao"]),
    }


class Task49CapsuleContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = task41.task40_package()
        cls.legacy = task46.task46_block(cls.package)

    def test_contrato_autoral_e_autocontido_compacto_e_sem_quatro_apis(self):
        contract = capsule.authoring_contract(self.package)
        rendered = yaml.safe_dump(contract, allow_unicode=True, sort_keys=False).encode("utf-8")
        self.assertLessEqual(len(rendered), capsule.MAX_CONTRACT_BYTES)
        self.assertEqual(contract["schema_capsula_autoral"], 1)
        self.assertEqual(
            contract["forma"]["sidequest_emergente"],
            ["oferta", "capsula_autoral"],
        )
        self.assertEqual(
            set(contract["campos"]),
            {"aventura", "recompensas", "adversidade", "progressao"},
        )
        self.assertIn("lateral", contract["enums"]["relacao_canone.modo"])
        self.assertIn("obrigatoria_se_condicao", contract["enums"]["adversidade.prioridade"])
        self.assertIn("qualquer", contract["enums"]["progressao.regra"])
        text = yaml.safe_dump(contract, allow_unicode=True, sort_keys=False)
        self.assertIn("não consulte schemas internos", text)
        self.assertIn("stdin", text)
        self.assertIn("write_stdin", text)

    def test_capsula_compila_exatamente_para_bloco_task46_existente(self):
        raw = {
            "oferta": copy.deepcopy(self.legacy["oferta"]),
            "capsula_autoral": capsule_from_legacy(self.legacy),
        }
        compiled, mode = capsule.compile_block(raw)
        self.assertEqual(mode, "capsula_task49_v1")
        self.assertEqual(compiled, self.legacy)

    def test_payload_task46_legado_permanece_compativel_para_recovery(self):
        compiled, mode = capsule.compile_block(self.legacy)
        self.assertEqual(mode, "legado_task46")
        self.assertEqual(compiled, self.legacy)

    def test_capsula_com_chave_extra_falha_antes_de_qualquer_validator(self):
        raw = {
            "oferta": copy.deepcopy(self.legacy["oferta"]),
            "capsula_autoral": capsule_from_legacy(self.legacy),
        }
        raw["capsula_autoral"]["api_task43"] = "não permitido"
        with self.assertRaisesRegex(capsule.SidequestAuthoringCapsuleError, "capsula_autoral divergente"):
            capsule.compile_block(raw)

    def test_compilacao_preserva_os_validadores_41_43_44_45(self):
        raw = {
            "oferta": copy.deepcopy(self.legacy["oferta"]),
            "capsula_autoral": capsule_from_legacy(self.legacy),
        }
        compiled, _ = capsule.compile_block(raw)
        plan = integration.prepare_installation(
            ROOT,
            package=self.package,
            block=compiled,
            offer_scene_id="task49:equivalencia",
            offer_summary=compiled["oferta"]["resumo"],
        )
        self.assertTrue(plan["quest_id"].startswith("qse-"))
        self.assertTrue(plan["reward_path"].endswith(".yaml"))
        self.assertTrue(plan["adversarial_path"].endswith(".yaml"))
        self.assertTrue(plan["progress_path"].endswith(".yaml"))

    def test_enum_invalido_continua_falhando_no_validator_existente(self):
        raw = {
            "oferta": copy.deepcopy(self.legacy["oferta"]),
            "capsula_autoral": capsule_from_legacy(self.legacy),
        }
        raw["capsula_autoral"]["progressao"]["regra_sucesso"] = "percentual_75"
        compiled, _ = capsule.compile_block(raw)
        with self.assertRaisesRegex(
            integration.EmergentSidequestIntegrationError,
            "regra_sucesso/regra_falha",
        ):
            integration.prepare_installation(
                ROOT,
                package=self.package,
                block=compiled,
                offer_scene_id="task49:enum-invalido",
                offer_summary=compiled["oferta"]["resumo"],
            )


class Task49CronicaAdapterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = task41.task40_package()
        cls.legacy = task46.task46_block(cls.package)

    def setUp(self):
        # Importar aqui deixa explícito que o adapter é a superfície operacional,
        # sem alterar a ordem dos testes Task46/48 anteriores durante discovery.
        import cronica_task49 as task49
        self.task49 = task49

    def test_turno_neutro_permanece_byte_logicamente_inalterado(self):
        sentinel = {"fase": "preparacao", "ticket": "crn1.neutro", "ticket_id": "neutro"}
        with patch.object(self.task49, "_ORIGINAL_PREPARE", return_value=sentinel):
            result = self.task49.prepare(ROOT, scene_id="task49-neutro", sidequest_signal=None)
        self.assertIs(result, sentinel)

    def test_preparacao_rara_entrega_capsula_na_mesma_chamada(self):
        fake = {
            "fase": "preparacao",
            "sidequest_emergente": copy.deepcopy(self.package),
            "sidequest_emergente_task46": {
                "integrada_ao_ticket": True,
                "chamadas_orquestracao_adicionais": 0,
            },
        }
        with (
            patch.object(self.task49, "_ORIGINAL_PREPARE", return_value=fake),
            patch.object(self.task49._base._sidequests46._base, "_yaml_size", return_value=8000),
        ):
            result = self.task49.prepare(ROOT, scene_id="task49-raro", sidequest_signal={})
        self.assertEqual(result["contrato_autoria_sidequest"]["schema_capsula_autoral"], 1)
        self.assertEqual(
            result["sidequest_emergente_task46"]["formato_autoral"],
            "capsula_task49_v1",
        )
        self.assertEqual(
            result["sidequest_emergente_task46"]["transporte_autoral"],
            "stdin_json_unico",
        )

    def test_concluir_compila_capsula_antes_de_delegar_ao_task46(self):
        transaction = {
            "narracao": "Oferta narrada com clareza — decisão permanece com Ren.",
            "resumo": "Oferta causal narrada.",
            "modo": "interacao",
            "deltas": [],
            integration.TRANSACTION_KEY: {
                "oferta": copy.deepcopy(self.legacy["oferta"]),
                "capsula_autoral": capsule_from_legacy(self.legacy),
            },
        }
        delegated = {
            "fase": "concluida",
            "sidequest_emergente": {"resultado": "sidequest_materializada"},
        }
        with patch.object(self.task49, "_ORIGINAL_CONCLUDE", return_value=delegated) as original:
            result = self.task49.conclude(ROOT, "ticket-task49", transaction)
        sent = original.call_args.args[2]
        self.assertEqual(sent[integration.TRANSACTION_KEY], self.legacy)
        self.assertEqual(result["sidequest_emergente"]["formato_autoral"], "capsula_task49_v1")

    def test_capsula_invalida_falha_antes_do_concluir_existente(self):
        transaction = {
            integration.TRANSACTION_KEY: {
                "oferta": copy.deepcopy(self.legacy["oferta"]),
                "capsula_autoral": {"schema": 1},
            }
        }
        with patch.object(self.task49, "_ORIGINAL_CONCLUDE") as original:
            with self.assertRaisesRegex(self.task49._base.CronicaError, "Task49"):
                self.task49.conclude(ROOT, "ticket-task49", transaction)
        original.assert_not_called()


class Task49SafeTransportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = task41.task40_package()
        cls.legacy = task46.task46_block(cls.package)

    def test_stdin_json_grande_unicode_chega_inteiro_sem_arquivo_temporario(self):
        transaction = {
            "narracao": "Árvore — criança — Kozakura — " + ("çãõ漢字" * 900),
            "resumo": "Payload grande de transporte Task49.",
            "modo": "interacao",
            "deltas": [],
            integration.TRANSACTION_KEY: {
                "oferta": copy.deepcopy(self.legacy["oferta"]),
                "capsula_autoral": capsule_from_legacy(self.legacy),
            },
        }
        code = (
            "import json,sys; "
            f"sys.path.insert(0,{str(TOOLS)!r}); "
            "import turno,sidequest_authoring_capsule as c; "
            "tx=turno.read_transaction(None); b,m=c.compile_block(tx['sidequest_emergente']); "
            "print(json.dumps({'modo':m,'titulo':b['quest']['titulo'],'narracao':tx['narracao']},ensure_ascii=False))"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            input=json.dumps(transaction, ensure_ascii=False),
            text=True,
            capture_output=True,
            cwd=ROOT,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["modo"], "capsula_task49_v1")
        self.assertEqual(result["titulo"], self.legacy["quest"]["titulo"])
        self.assertEqual(result["narracao"], transaction["narracao"])


if __name__ == "__main__":
    unittest.main()
