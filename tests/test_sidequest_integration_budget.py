from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica
import mundo
import oportunidade_sidequest as opportunity
import sidequests_integracao_runtime as integration
import test_emergent_sidequest_authoring_registry_v2 as authoring_cases


def valid_ticket_payload(scene_id: str) -> dict:
    return {
        "schema_cronica_ticket": cronica._core.SCHEMA,
        "preparacao_id": "fixture-sidequest-integration",
        "cena": cronica._core._request(
            scene_id=scene_id,
            npcs=[],
            place=None,
            action=None,
            tier=None,
            danger=None,
            context_tags=[],
            now=None,
            approach_preparacao=None,
            approach_informacao=None,
            approach_adequacao=None,
        ),
    }


class SidequestNeutralBudgetTest(unittest.TestCase):
    def test_turno_neutro_retorna_exatamente_hotpath_sem_acordar_integracao(self):
        sentinel = {
            "schema_cronica_turno": 1,
            "fase": "preparacao",
            "ticket": "crn1.fixture",
            "ticket_id": "fixture",
        }
        with (
            patch.object(cronica._pending_gate, "prepare_gate", return_value=None),
            patch.object(cronica._hot, "prepare", return_value=sentinel) as base,
            patch.object(
                cronica._sidequests48,
                "integrate_prepare",
                return_value=sentinel,
            ) as active,
            patch.object(
                cronica._sidequests46,
                "integrate_prepare",
                side_effect=AssertionError("turno neutro não pode acordar integração de sidequest"),
            ) as emergent,
        ):
            result = cronica.prepare(ROOT, scene_id="sidequest-integration:neutro", sidequest_signal=None)
        self.assertIs(result, sentinel)
        base.assert_called_once()
        active.assert_called_once()
        emergent.assert_not_called()

    def test_baseline_congela_zero_custo_e_duas_chamadas(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/emergent-sidequests-integration-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        neutral = contract["turno_neutro"]
        self.assertEqual(neutral["chamadas_orquestracao"], 2)
        self.assertEqual(neutral["leituras_task40_45"], 0)
        self.assertEqual(neutral["fragmentos_sidequest_emergente"], 0)
        self.assertEqual(neutral["leituras_horizonte_canonico_adicionais"], 0)
        self.assertEqual(neutral["transcricoes_lidas"], 0)
        active = contract["turno_com_sidequest_ativa"]
        self.assertEqual(active["fragmentos_task45_max"], 2)
        self.assertEqual(active["leituras_task40_autoria"], 0)
        self.assertEqual(active["escritas"], 0)
        self.assertTrue(contract["migracao"]["catalogo_task33_no_hot_path"])
        self.assertEqual(contract["infra"]["schedulers_novos"], 0)
        self.assertEqual(contract["infra"]["relogios_novos"], 0)
        self.assertEqual(contract["infra"]["rng_novo"], 0)
        self.assertEqual(contract["infra"]["scans_globais"], 0)


class SidequestOpportunityBudgetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = authoring_cases.task40_package()

    def signal(self) -> dict:
        origin = self.package["origem"]
        reward = self.package["envelope_recompensa"]
        return {
            "origem_tipo": origin["tipo"],
            "origem_id": origin["id"],
            "ancora_tipo": origin["ancora_tipo"],
            "ancora": origin["ancora"],
            "npc_id": origin.get("npc_id"),
            "local_id": self.package["prazo_mundo"].get("local_id"),
            "periculosidade": reward["periculosidade"],
            "tier": reward["tier"],
        }

    def test_mesma_chamada_preparar_entrega_pacote_limitado_sem_transcricao_legada(self):
        now_raw = self.package["prazo_mundo"]["agora"]
        now = mundo.parse_instant(now_raw["data"], now_raw["hora"])
        token, ticket_id = cronica._core.encode_ticket(valid_ticket_payload("sidequest-integration:budget"))
        base = {
            "schema_cronica_turno": 1,
            "fase": "preparacao",
            "ticket": token,
            "ticket_id": ticket_id,
            "sistemas_narrativos": [],
        }
        result = integration.integrate_prepare(
            ROOT,
            base,
            signal_raw=self.signal(),
            decode_ticket=cronica.decode_ticket,
            encode_ticket=cronica._core.encode_ticket,
            now=now,
        )
        package = result["sidequest_emergente"]
        self.assertEqual(package["resultado"], "material_para_planejamento")
        self.assertLessEqual(
            len(yaml.safe_dump(package, allow_unicode=True, sort_keys=False).encode("utf-8")),
            8 * 1024,
        )
        compatible = package["horizonte_intencoes_canonicas"]["compativeis"]
        self.assertLessEqual(len(compatible), 3)
        self.assertFalse(package["metricas"]["transcricao_lida"])
        self.assertFalse(package["metricas"]["catalogo_task33_aberto"])
        self.assertEqual(package["metricas"]["scans_globais"], 0)
        self.assertEqual(package["metricas"]["escritas"], 0)
        self.assertEqual(result["sidequest_emergente_task46"]["chamadas_orquestracao_adicionais"], 0)
        self.assertTrue(result["sidequest_emergente_task46"]["integrada_ao_ticket"])
        decoded = cronica.decode_ticket(result["ticket"])
        meta = integration.ticket_meta(decoded)
        self.assertIsNotNone(meta)
        self.assertNotIn("horizonte_intencoes_canonicas", meta)
        self.assertNotIn("atores_causalmente_disponiveis", meta)

    def test_integracao_nao_importa_rng_scheduler_nem_scan_global(self):
        for rel in (
            "ferramentas/sidequests_integracao.py",
            "ferramentas/sidequests_integracao_runtime.py",
        ):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("import random", text)
            self.assertNotIn("rglob(", text)
            self.assertNotIn("glob(", text)
            self.assertNotIn("Scheduler", text)

    def test_preflight_executa_gate_de_integracao_sidequest(self):
        items = {
            tuple(item.comando[1:]): item.nome
            for item in __import__("ferramentas.preflight", fromlist=["checks"]).checks(
                incluir_testes=False
            )
        }
        self.assertEqual(
            items[("ferramentas/sidequests_integracao_check.py",)],
            "integração de sidequests emergentes",
        )
        self.assertEqual(
            items[("ferramentas/sidequests_ativas.py", "check")],
            "projeção de sidequests ativas",
        )
        result = integration.check(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["contrato"]["chamadas_orquestracao"], 2)
        self.assertEqual(result["contrato"]["pacote_autoral_max_bytes"], opportunity.MAX_PAYLOAD_BYTES)
        self.assertEqual(result["contrato"]["intencoes_max"], opportunity.MAX_INTENT_FRAGMENTS)


if __name__ == "__main__":
    unittest.main()
