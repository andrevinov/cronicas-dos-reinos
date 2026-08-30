from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import resolver_fronteira


class Task45BoundaryGuardTest(unittest.TestCase):
    def test_resolver_sidequest_e_projetada_sem_noop_e_sem_acordar_outros_motores(self):
        pending = {
            "id": "mundo-4545454545454545",
            "tipo": "resolver_sidequest",
            "disparado_em": {"data": "17 Eleasis, 1372 DR", "hora": "06:00"},
            "motivo": "prazo Task45 venceu e a consequência causal precisa ser materializada",
            "origem": "sidequest:qse-fixture",
        }
        world = {"pendencias": [pending], "concluidas_recentes": []}

        with (
            patch.object(resolver_fronteira.mundo, "load_world_state", return_value=world),
            patch.object(resolver_fronteira.barreira_mundo, "_canonical_event") as canonical,
            patch.object(
                resolver_fronteira.pressao_ravens_bluff, "candidate_for_pending"
            ) as pressure,
        ):
            result = resolver_fronteira.prepare_batch(ROOT)

        item = result["itens"][0]
        self.assertEqual(item["classificacao"], "requer_resolucao_sidequest")
        self.assertFalse(item["sem_mudanca_permitido"])
        canonical.assert_not_called()
        pressure.assert_not_called()

    def test_resolver_sidequest_recusa_sem_mudanca_antes_de_qualquer_escrita(self):
        token = "4" * resolver_fronteira.TOKEN_HEX
        item = {
            "id": "mundo-4545454545454545",
            "tipo": "resolver_sidequest",
            "classificacao": "requer_resolucao_sidequest",
            "sem_mudanca_permitido": False,
            "token": token,
        }
        current = {
            "lote_id": "frn1." + "4" * resolver_fronteira.BATCH_HEX,
            "quantidade": 1,
            "itens": [item],
        }
        payload = {
            "lote_id": current["lote_id"],
            "sem_mudanca": [
                {
                    "id": item["id"],
                    "token": token,
                    "nota": "Tentativa de descartar consequência Task45 como no-op genérico.",
                }
            ],
        }

        with (
            patch.object(resolver_fronteira, "prepare_batch", return_value=current),
            patch.object(resolver_fronteira, "_completed_map", return_value={}),
            patch.object(resolver_fronteira.barreira_mundo, "conclude") as conclude,
            patch.object(resolver_fronteira.barreira_mundo, "sync") as sync,
        ):
            with self.assertRaisesRegex(
                resolver_fronteira.BatchBoundaryError,
                "resolução Task45.*não aceita sem_mudanca",
            ):
                resolver_fronteira.apply_batch(ROOT, payload)

        conclude.assert_not_called()
        sync.assert_not_called()


if __name__ == "__main__":
    unittest.main()
