from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import sidequests_integracao_runtime as integration


class Task48ContractTest(unittest.TestCase):
    def test_baseline_congela_digest_relogio_e_zero_infra(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/stable-task40-snapshot-effective-clock-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        limits = contract["limites"]
        self.assertEqual(limits["turno_neutro_leituras_task40_45"], 0)
        self.assertEqual(limits["chamadas_orquestracao_por_turno"], 2)
        self.assertEqual(limits["digest_semantico_sha256_hex_chars"], 64)
        self.assertEqual(limits["pacote_autoral_max_bytes"], integration.MAX_AUTHOR_PACKET_BYTES)
        self.assertEqual(limits["preparacao_rara_max_bytes"], integration.MAX_COMBINED_PREP_BYTES)
        for key in (
            "schedulers_novos",
            "relogios_novos",
            "rng_novo",
            "scans_globais_novos",
            "estados_persistentes_novos",
        ):
            self.assertEqual(limits[key], 0)
        self.assertEqual(
            set(contract["campos_observacionais_fora_do_digest"]),
            set(integration.SEMANTIC_DIGEST_EXCLUDED),
        )
        self.assertTrue(all(contract["invariantes"].values()))

    def test_router_documenta_task48_sem_inchar_hot_context(self):
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertTrue((ROOT / "docs/task48-stable-task40-snapshot-effective-clock.md").is_file())
        self.assertIn("relógio efetivo + digest semântico", agents)
        self.assertIn("cronica preparar", agents)
        self.assertIn("cronica concluir", agents)
        self.assertIn("2 chamadas de orquestração por turno", agents)
        self.assertLessEqual(len(agents.encode("utf-8")), 12 * 1024)

    def test_check_task46_agora_congela_invariantes_task48(self):
        result = integration.check(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["contrato"]["digest_task40"], "semantico_task48_v1")
        self.assertEqual(
            result["contrato"]["relogio_task40"],
            "canonico_mais_overlay_transacional",
        )


if __name__ == "__main__":
    unittest.main()
