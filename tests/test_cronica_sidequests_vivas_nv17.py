from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica_sidequests_vivas as bridge  # noqa: E402


class CronicaLiveSidequestIntegrationTests(unittest.TestCase):
    def _route(self):
        return {
            "schema_sidequests_vivas": 1,
            "janela": {"id": "21 Eleasis, 1372 DR|dia", "data": "21 Eleasis, 1372 DR", "periodo": "dia"},
            "resultado": "causa_viva_projetada",
            "sinal_efetivo": {"plano_id": "silva_socorro", "local_id": "circo_hooft", "periculosidade": "media", "tier": 2},
            "origem": "causa_nv11_vencida",
            "reutilizada": False,
            "causa_viva": {
                "id": "scp-causa",
                "plano_id": "silva_socorro",
                "causa": {"tipo": "necessidade"},
                "dono": {"tipo": "leve", "id": "silva_elkwood"},
                "bloqueio": {"estado_plano": "pretende", "condicoes": []},
                "conhecimento": [],
                "alcance": {"alcança_ren": True, "tipo": "elenco_presente"},
                "reavaliacao": {"em": {"data": "21 Eleasis, 1372 DR", "hora": "10:00"}, "condicoes": []},
                "stakes": {"nao_agir": "risco permanece"},
                "protecoes": {"oferta_nao_e_aceite": True},
                "motivo_envolver_ren": "Ren possui acesso relevante.",
                "prioridade_elevada_por_zero_ativas": True,
            },
            "ancora_manual_adiada": False,
            "projecao": {"causas": [{"id": "scp-causa"}], "orcamento": {"ativas": 0, "abertas": 0, "max_ativas": 2}},
            "fontes_lidas": [],
        }

    def test_negative_task47_is_replaced_by_due_live_cause(self):
        captured = {}

        def base_prepare(*args, **kwargs):
            captured.update(kwargs)
            return {"fase": "preparada", "sistemas_narrativos": []}

        with mock.patch.object(bridge._pending_gate, "prepare_gate", return_value=None), mock.patch.object(bridge._live, "route_prepare", return_value=self._route()) as route, mock.patch.object(bridge, "_BASE_PREPARE", side_effect=base_prepare):
            result = bridge.prepare(
                Path("/repo"),
                scene_id="cena",
                sidequest_signal=None,
                npcs=["silva_elkwood"],
                place="circo_hooft",
                danger="media",
                tier=2,
            )
        route.assert_called_once()
        self.assertEqual(captured["sidequest_signal"]["plano_id"], "silva_socorro")
        self.assertEqual(result["sidequests_vivas"]["causa_viva"]["id"], "scp-causa")
        self.assertIn("live_sidequests_by_cause", result["sistemas_narrativos"])

    def test_blocking_world_gate_does_not_reserve_or_discover_sidequest(self):
        gate = {"fase": "bloqueada_pendencias_mundo"}
        with mock.patch.object(bridge._pending_gate, "prepare_gate", return_value=gate), mock.patch.object(bridge._live, "route_prepare") as route, mock.patch.object(bridge, "_BASE_PREPARE", return_value=gate) as base:
            result = bridge.prepare(Path("/repo"), sidequest_signal=None)
        route.assert_not_called()
        base.assert_called_once()
        self.assertEqual(result, gate)

    def test_manual_anchor_remains_available_when_no_live_cause_exists(self):
        manual = {"origem": {"tipo": "evento_cena", "id": "ancora", "ancora_tipo": "fato", "ancora": "pedido novo explicitamente narrado"}, "local_id": "circo_hooft", "periculosidade": "media", "tier": 2}
        routed = self._route()
        routed.update({"resultado": "ancora_cena_encaminhada", "sinal_efetivo": manual, "origem": "ancora_cena", "causa_viva": None, "projecao": {"causas": [], "orcamento": {"ativas": 0, "abertas": 0, "max_ativas": 2}}})
        captured = {}
        with mock.patch.object(bridge._pending_gate, "prepare_gate", return_value=None), mock.patch.object(bridge._live, "route_prepare", return_value=routed), mock.patch.object(bridge, "_BASE_PREPARE", side_effect=lambda *a, **k: captured.update(k) or {"fase": "preparada"}):
            bridge.prepare(Path("/repo"), sidequest_signal=manual)
        self.assertEqual(captured["sidequest_signal"], manual)


if __name__ == "__main__":
    unittest.main()
