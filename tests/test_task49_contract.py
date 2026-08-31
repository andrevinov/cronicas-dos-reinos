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

from ferramentas import poetry_cli
import sidequest_authoring_capsule as capsule


class Task49ContractTest(unittest.TestCase):
    def test_baseline_congela_capsula_transporte_e_zero_infra(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/single-authoring-capsule-safe-transport-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        limits = contract["limites"]
        self.assertEqual(limits["turno_neutro_leituras_task40_45"], 0)
        self.assertEqual(limits["chamadas_orquestracao_por_turno"], 2)
        self.assertEqual(limits["contrato_capsula_max_bytes"], capsule.MAX_CONTRACT_BYTES)
        self.assertEqual(limits["capsula_input_max_bytes"], capsule.MAX_CAPSULE_BYTES)
        for key in (
            "writers_novos",
            "schedulers_novos",
            "relogios_novos",
            "rng_novo",
            "scans_globais_novos",
            "estados_persistentes_novos",
        ):
            self.assertEqual(limits[key], 0)
        self.assertTrue(all(contract["invariantes"].values()))

    def test_poetry_cronica_aponta_para_adapter_task49_sem_novo_comando(self):
        with patch.object(sys, "argv", ["cronica", "preparar"]), patch(
            "ferramentas.poetry_cli.subprocess.run"
        ) as run:
            run.return_value.returncode = 0
            code = poetry_cli.cronica()
        self.assertEqual(code, 0)
        args, kwargs = run.call_args
        self.assertEqual(Path(args[0][1]), ROOT / "ferramentas/cronica_task49.py")
        self.assertEqual(args[0][2:], ["preparar"])
        self.assertEqual(kwargs["cwd"], ROOT)
        self.assertFalse(kwargs["check"])

    def test_docs_task49_existentes_e_spoiler_light(self):
        text = (ROOT / "docs/task49-single-authoring-capsule-safe-transport.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("capsula_autoral", text)
        self.assertIn("validadores 41/43/44/45", text)
        self.assertIn("stdin", text)
        self.assertNotIn("Sete Nomes Antes do Amanhecer", text)


if __name__ == "__main__":
    unittest.main()
