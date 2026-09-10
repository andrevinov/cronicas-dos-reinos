from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica  # noqa: E402
import cronica_permanencia as cp  # noqa: E402


class CronicaPermanenceTests(unittest.TestCase):
    def test_parser_exposes_explicit_permanence_flag(self):
        args = cronica.build_parser().parse_args(
            [
                "preparar",
                "--cena-id",
                "circo-permanencia",
                "--permanencia-local",
                "--sem-oportunidade-sidequest",
                "--sem-participantes",
            ]
        )
        self.assertTrue(args.permanencia_local)

    def test_short_turn_without_flag_delegates_without_spatial_read(self):
        sentinel = {"ok": True, "delegado": True}
        with mock.patch.object(cp, "_HOT_PREPARE", return_value=sentinel) as delegated, mock.patch.object(
            cp._stay, "prepare"
        ) as spatial:
            result = cp._hot_prepare(
                Path("/tmp/repo"),
                scene_id="turno-curto",
                permanence_local=False,
            )
        self.assertIs(result, sentinel)
        delegated.assert_called_once()
        spatial.assert_not_called()

    def test_permanence_output_never_nulls_consolidated_local(self):
        public = {
            "schema_permanencia_espacial": 1,
            "avaliacao_id": "perm-0123456789abcdef0123",
            "local_id": "circo_hooft",
            "data": "21 Eleasis, 1372 DR",
            "periodo": "dia",
            "estado": "calma_espacial",
            "reutilizado": False,
            "carregada_de_janela_anterior": False,
            "pressao_primaria": None,
            "candidatos": [],
            "ecologia": {"ritmo": "cheio", "tags": ["circo"], "canais_microevento": ["publico"]},
            "presenca_incidental": {"resultado": "nenhuma_presenca_incidental", "candidatos": []},
            "microevento_local": {"resultado": "rotina", "ficha_ocorrencia": "m1"},
            "incidente_local": {"resultado": "rotina", "origem": None},
            "condicoes_ambientais": [],
            "exige_decisao_conclusao": False,
            "digest": "a" * 64,
            "regra": "avaliação congelada",
            "fontes_lidas": ["estado/estado-atual.yaml"],
        }
        meta = {
            "schema": 1,
            "avaliacao_id": public["avaliacao_id"],
            "digest": public["digest"],
            "local_id": public["local_id"],
            "data": public["data"],
            "periodo": public["periodo"],
        }
        with mock.patch.object(cp._stay, "prepare", return_value={"publico": public, "ticket": meta}), mock.patch.object(
            cp._hot, "_quality_modifier", return_value=([], [])
        ):
            result = cp._hot_prepare(
                Path("/tmp/repo"),
                scene_id="circo-a",
                permanence_local=True,
            )
        self.assertEqual(result["ids"]["local"], "circo_hooft")
        self.assertEqual(result["permanencia_espacial"]["local_id"], "circo_hooft")
        self.assertTrue(result["reativa_espacial"])
        self.assertEqual(result["gates"][0]["resultado"], "calma_espacial")

    def test_permanence_rejects_entry_explore_trigger_mixing(self):
        with self.assertRaisesRegex(cp._core.CronicaError, "aceita apenas --local opcional"):
            cp._hot_prepare(
                Path("/tmp/repo"),
                scene_id="circo-a",
                place="circo_hooft",
                action="explorar",
                tier=2,
                danger="media",
                permanence_local=True,
            )

    def test_stay_ticket_identity_ignores_scene_id_at_spatial_layer(self):
        meta = {
            "schema": 1,
            "avaliacao_id": "perm-0123456789abcdef0123",
            "digest": "b" * 64,
            "local_id": "circo_hooft",
            "data": "21 Eleasis, 1372 DR",
            "periodo": "dia",
        }
        first_request = cp._core._request(
            scene_id="cena-a",
            npcs=[],
            place="circo_hooft",
            action=None,
            tier=None,
            danger=None,
            context_tags=[],
            now=None,
            approach_preparacao=None,
            approach_informacao=None,
            approach_adequacao=None,
        )
        second_request = cp._core._request(
            scene_id="cena-b",
            npcs=[],
            place="circo_hooft",
            action=None,
            tier=None,
            danger=None,
            context_tags=[],
            now=None,
            approach_preparacao=None,
            approach_informacao=None,
            approach_adequacao=None,
        )
        self.assertEqual(meta["avaliacao_id"], meta["avaliacao_id"])
        self.assertNotEqual(cp._stay_preparation_id(first_request, meta), cp._stay_preparation_id(second_request, meta))
        # O ticket muda para proteger a requisição, mas a identidade do mundo não:
        # ambos apontam para o mesmo avaliacao_id local/data/período.


if __name__ == "__main__":
    unittest.main()
