from __future__ import annotations

import copy
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

import mundo  # noqa: E402
import permanencia_espacial as stay  # noqa: E402


class SpatialFreshnessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "estado").mkdir(parents=True)
        self._write_location("circo_hooft")

    def tearDown(self):
        self.temp.cleanup()

    def _write_location(self, local_id: str):
        (self.repo / "estado/estado-atual.yaml").write_text(
            yaml.safe_dump(
                {"localizacao": {"area": local_id, "local_id": local_id}},
                allow_unicode=True,
            ),
            encoding="utf-8",
        )

    def _record(self, *, evaluation_id: str, local_id: str, date: str, period: str):
        record = {
            "id": evaluation_id,
            "chave": f"{local_id}|{date}|{period}",
            "local_id": local_id,
            "data": date,
            "periodo": period,
            "estado": "ativa",
            "pressao_primaria": "microevento:rotina",
            "candidatos": [
                {
                    "id": "microevento:rotina",
                    "tipo": "rotina_local",
                    "prioridade": 7,
                    "origem": "microeventos_locais",
                    "decisao": "primaria",
                }
            ],
            "ecologia": {"ritmo": "normal", "tags": [], "canais_microevento": []},
            "presenca_incidental": {
                "resultado": "nenhuma_presenca_incidental",
                "candidatos": [],
            },
            "microevento_local": {
                "resultado": "avaliar_microevento",
                "carta": {"id": "rotina"},
            },
            "incidente_local": {"resultado": "rotina", "origem": None},
            "condicoes_ambientais": [],
            "decisao": None,
            "fontes_lidas": [stay.STATE.as_posix()],
        }
        record["digest"] = stay._record_digest(record)
        return record

    def test_active_candidate_is_carried_into_next_period_without_producer_draw(self):
        previous = self._record(
            evaluation_id="perm-anterior",
            local_id="circo_hooft",
            date="21 Eleasis, 1372 DR",
            period="dia",
        )
        stay._atomic(
            self.repo / stay.STATE,
            {
                "schema_estado_permanencia_espacial": 1,
                "natureza": "controle_reservado",
                "avaliacoes": {previous["id"]: previous},
                "ordem_recente": [previous["id"]],
            },
        )
        current = mundo.parse_instant("21 Eleasis, 1372 DR", "18:30")
        with mock.patch.object(
            stay.locais,
            "resolve",
            return_value={
                "local_id": "circo_hooft",
                "fontes_lidas": ["cenario/locais/index.yaml"],
            },
        ), mock.patch.object(
            stay.mundo, "load_agenda", return_value={"hora_amanhecer": "06:00"}
        ), mock.patch.object(stay.ecologia_local, "lookup_canonical") as ecology, mock.patch.object(
            stay.microeventos_locais, "plan"
        ) as micro, mock.patch.object(stay.incidentes_mundo, "plan") as incident:
            result = stay.prepare(self.repo, scene_id="outra-cena", now=current)

        self.assertEqual(result["publico"]["avaliacao_id"], "perm-anterior")
        self.assertTrue(result["publico"]["carregada_de_janela_anterior"])
        self.assertEqual(result["publico"]["pressao_primaria"], "microevento:rotina")
        ecology.assert_not_called()
        micro.assert_not_called()
        incident.assert_not_called()

    def test_location_change_invalidates_active_candidate_from_old_place(self):
        previous = self._record(
            evaluation_id="perm-circo",
            local_id="circo_hooft",
            date="21 Eleasis, 1372 DR",
            period="dia",
        )
        state = {
            "schema_estado_permanencia_espacial": 1,
            "natureza": "controle_reservado",
            "avaliacoes": {previous["id"]: copy.deepcopy(previous)},
            "ordem_recente": [previous["id"]],
        }
        changed = stay._invalidate_other_locations(
            state,
            "porto_ravens_bluff",
            {"data": "21 Eleasis, 1372 DR", "hora": "16:00"},
        )
        self.assertTrue(changed)
        invalidated = state["avaliacoes"]["perm-circo"]
        self.assertEqual(invalidated["estado"], "invalidada")
        self.assertEqual(invalidated["decisao"]["resultado"], "invalidada")
        self.assertIn("âncora espacial", invalidated["decisao"]["motivo"])
        # Estado/decisão são mutáveis, portanto não alteram a identidade congelada do ticket.
        self.assertEqual(invalidated["digest"], previous["digest"])


if __name__ == "__main__":
    unittest.main()
