from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import canon_bridge
import canon_bridge_runtime


class LiveCampaignStateRegressionTest(unittest.TestCase):
    def test_sidequests_aceitas_respeitam_o_contrato_task42(self) -> None:
        result = canon_bridge_runtime.check(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        state = canon_bridge.load_state(ROOT)
        self.assertEqual(result["reservas"], len(state["reservas"]))
        self.assertEqual(result["resolucoes"], len(state["resolucoes"]))


if __name__ == "__main__":
    unittest.main()
