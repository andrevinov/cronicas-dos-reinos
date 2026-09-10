from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import sidequests_vivas as live  # noqa: E402


class LegacySidequestMigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / live.MIGRATION_EVIDENCE.parent).mkdir(parents=True)
        (self.repo / live.MIGRATION_EVIDENCE).write_text(
            yaml.safe_dump(
                {
                    "schema_evidencias_migracao_nv17": 1,
                    "natureza": "declaracao_reservada",
                    "mapeamentos": {},
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def test_unmapped_cold_items_are_archived_with_explicit_reason(self):
        entries = [("qsc-000000000001", "silva_elkwood"), ("qsc-000000000002", "jack_mooney")]
        with mock.patch.object(live, "_legacy_entries", return_value=entries):
            receipt = live.migrate_legacy(self.repo)
        self.assertTrue(receipt["executada"])
        self.assertEqual(receipt["convertidas"], [])
        self.assertEqual(len(receipt["arquivadas"]), 2)
        self.assertTrue(all(row["motivo"] == "sem_evidencia_canonica_explicita_de_causa_viva_nv11" for row in receipt["arquivadas"]))
        self.assertTrue(receipt["politica"]["nao_copiar_terminal_reacao_recompensa_necessidade"])

    def test_second_migration_uses_receipt_without_scanning_legacy(self):
        entries = [("qsc-000000000001", "nera_vell")]
        with mock.patch.object(live, "_legacy_entries", return_value=entries):
            first = live.migrate_legacy(self.repo)
        with mock.patch.object(live, "_legacy_entries", side_effect=AssertionError("catálogo não pode ser relido")):
            second = live.migrate_legacy(self.repo)
        self.assertEqual(first, second)

    def test_explicit_nv11_mapping_converts_only_cause_identity(self):
        evidence = {
            "schema_evidencias_migracao_nv17": 1,
            "natureza": "declaracao_reservada",
            "mapeamentos": {"qsc-000000000001": "nera_precisa_ajuda"},
        }
        (self.repo / live.MIGRATION_EVIDENCE).write_text(
            yaml.safe_dump(evidence, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        conversion = {
            "id": "qsc-000000000001",
            "estado": "convertida_em_causa_nv11",
            "npc_id": "nera_vell",
            "plano_id": "nera_precisa_ajuda",
            "causa_id": "scp-canonica",
            "fonte_causa": {"arquivo": "estado/npcs/nera_vell.yaml", "caminho": "npc.necessidades.ajuda", "valor": True},
            "regra": "somente a causa NV-11 sobrevive",
        }
        with mock.patch.object(live, "_legacy_entries", return_value=[("qsc-000000000001", "nera_vell")]), mock.patch.object(live, "_migration_conversion", return_value=conversion) as convert:
            receipt = live.migrate_legacy(self.repo)
        convert.assert_called_once_with(self.repo, "qsc-000000000001", "nera_vell", "nera_precisa_ajuda")
        self.assertEqual(receipt["convertidas"], [conversion])
        row = receipt["convertidas"][0]
        for forbidden in ("titulo", "terminal", "reacao", "recompensa", "necessidade"):
            self.assertNotIn(forbidden, row)


if __name__ == "__main__":
    unittest.main()
