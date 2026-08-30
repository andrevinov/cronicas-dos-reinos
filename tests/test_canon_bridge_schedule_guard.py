from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import canon_bridge
import mundo


class Task42ScheduleGuardTest(unittest.TestCase):
    def test_passado_materializado_usa_tipo_real_do_agendamento(self):
        event_id = "evento_sintetico"
        schedule_id = "agenda_sintetica"
        activation = {"data": "19 Eleasis, 1372 DR", "hora": "10:00"}
        base = mundo.parse_instant(activation["data"], activation["hora"])
        completed_id = mundo._pending_id(
            "movimento", f"agendamentos.{schedule_id}", base
        )
        catalog = {
            "eventos": {
                event_id: {
                    "agendamento_id": schedule_id,
                    "ativacao": activation,
                }
            }
        }
        world = {
            "pendencias": [],
            "concluidas_recentes": [{"id": completed_id}],
        }
        agenda = {
            "agendamentos": [
                {"id": schedule_id, "tipo": "movimento", "em": activation}
            ]
        }

        with (
            mock.patch.object(mundo, "load_world_state", return_value=world),
            mock.patch.object(mundo, "load_agenda", return_value=agenda),
        ):
            result = canon_bridge._world_event_status(ROOT, catalog, event_id)

        self.assertEqual(result["completed"], [{"id": completed_id}])


if __name__ == "__main__":
    unittest.main()
