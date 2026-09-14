from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import barreira_mundo
import causal_narrative_routing as routing
import cronica
import cronica_permanencia
import endpoints
from ferramentas import preflight
import scene_world_projection as projection
import world_boundary_resolution as boundary


class WorldCausalModuleContractTest(unittest.TestCase):
    def test_tres_fachadas_cobrem_exatamente_os_seis_aliases_v1(self) -> None:
        catalog = json.loads(
            (ROOT / "evaluation/catalogo-modulos-v2.json").read_text(encoding="utf-8")
        )
        facades = (projection, boundary, routing)
        expected = {
            alias: (module["id"], capability["id"])
            for module in catalog["modulos"]
            if module["id"] in {facade.MODULE_ID for facade in facades}
            for capability in module["subcapacidades"]
            for alias in capability["aliases_v1"]
        }
        actual = {
            alias: facade.MODULE_ID
            for facade in facades
            for alias in facade.LEGACY_ALIASES
        }

        self.assertEqual(len(expected), 6)
        self.assertEqual(set(actual), set(expected))
        self.assertTrue(
            all(actual[alias] == destination[0] for alias, destination in expected.items())
        )
        versions = {
            module["id"]: module["versao_implementacao"]
            for module in catalog["modulos"]
        }
        self.assertEqual(catalog["versao_catalogo"], "2.5.0")
        self.assertTrue(
            all(versions[facade.MODULE_ID] == "1.0.0" for facade in facades)
        )

    def test_hot_path_depende_das_fachadas_sem_nova_orquestracao(self) -> None:
        self.assertIs(cronica._core.cena_mundo, projection)
        self.assertIs(endpoints._base.cena_mundo, projection)
        self.assertIs(cronica_permanencia._world_projection, projection)
        self.assertIs(
            cronica_permanencia._stay,
            projection.spatial_permanence,
        )
        self.assertIs(cronica._pressure52, routing)
        self.assertIs(endpoints.fronteira_torneio, boundary)
        self.assertIs(barreira_mundo._canonical_module(ROOT), routing)

    def test_preflight_publica_tres_checks_e_preserva_aceitacao_como_regressao(self) -> None:
        commands = {tuple(item.comando[1:]) for item in preflight.checks(incluir_testes=False)}
        expected = {
            ("ferramentas/scene_world_projection.py", "check"),
            ("ferramentas/world_boundary_resolution.py", "check"),
            ("ferramentas/causal_narrative_routing.py", "check"),
        }
        self.assertTrue(expected <= commands)
        self.assertFalse(preflight._WORLD_CAUSAL_INTERNAL_CHECKS & commands)
        self.assertIn(
            ("ferramentas/aceitacao_vivacidade.py", "check"),
            commands,
        )


class SceneWorldProjectionFacadeTest(unittest.TestCase):
    def test_cena_e_permanencia_delegam_uma_vez_aos_motores_existentes(self) -> None:
        scene_result = {"preparacao_id": "scene-fixture"}
        stay_result = {"publico": {"avaliacao_id": "stay-fixture"}}
        with (
            patch.object(projection._scene, "prepare_scene", return_value=scene_result) as scene,
            patch.object(
                projection.spatial_permanence,
                "prepare",
                return_value=stay_result,
            ) as stay,
        ):
            projected = projection.prepare_scene(Path("/fixture"), scene_id="rm04")
            permanence = projection.prepare_permanence(
                Path("/fixture"), scene_id="rm04-stay"
            )

        scene.assert_called_once_with(Path("/fixture"), scene_id="rm04")
        stay.assert_called_once_with(Path("/fixture"), scene_id="rm04-stay")
        self.assertIs(projected, scene_result)
        self.assertIs(permanence, stay_result)

    def test_check_preserva_diagnostico_de_cada_produtor(self) -> None:
        healthy = {"ok": True, "erros": [], "evidencia": "preservada"}
        failure = {"ok": False, "erros": ["falha sintética"]}
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(projection._ecology, "check", return_value=healthy),
            patch.object(projection._microevents, "validate_repo", return_value=healthy),
            patch.object(projection._incidents, "check", return_value=failure),
            patch.object(projection._conditions, "check", return_value=healthy),
        ):
            report = projection.check(Path(temporary))

        self.assertFalse(report["ok"])
        self.assertIn("local_incidents: falha sintética", report["erros"])
        self.assertEqual(
            report["componentes"]["local_microevents"]["evidencia"],
            "preservada",
        )


class WorldBoundaryResolutionFacadeTest(unittest.TestCase):
    def test_lote_distingue_gate_neutro_de_efeito_material(self) -> None:
        retry = {"ok": True, "aplicadas": [], "quantidade_restante": 0}
        neutral = {
            "ok": True,
            "aplicadas": [
                {"id": "pending-fixture", "resultado": "sem_mudanca_concluida"}
            ],
            "quantidade_restante": 0,
        }
        material = {
            "ok": True,
            "aplicadas": [],
            "grupos_comprometidos": [{"id": "group-fixture"}],
            "quantidade_restante": 0,
        }
        with patch.object(
            boundary._batch,
            "apply_batch",
            side_effect=[retry, neutral, material],
        ):
            first = boundary.apply_batch(Path("/fixture"), {"lote_id": "one"})
            second = boundary.apply_batch(Path("/fixture"), {"lote_id": "two"})
            third = boundary.apply_batch(Path("/fixture"), {"lote_id": "three"})

        self.assertEqual(first["resultado_modular"], "retry_sem_duplicacao")
        self.assertFalse(first["efeito_materializado"])
        self.assertEqual(second["resultado_modular"], "gate_neutro_aplicado")
        self.assertFalse(second["efeito_materializado"])
        self.assertEqual(third["resultado_modular"], "lote_aplicado")
        self.assertTrue(third["efeito_materializado"])

    def test_ausencia_de_causa_produz_calma_com_cobertura_completa(self) -> None:
        report = boundary._check_liveness(Path("/fixture"))
        self.assertTrue(report["ok"])
        projection_result = report["projecao"]
        self.assertEqual(
            projection_result["recibo_calma"]["estado"],
            "calma_justificada",
        )
        self.assertEqual(
            len(projection_result["cobertura"]),
            len(boundary._liveness.REQUIRED_DOMAINS),
        )


class CausalNarrativeRoutingFacadeTest(unittest.TestCase):
    def matter(self, matter_id: str, kind: str) -> dict[str, object]:
        return {
            "id": matter_id,
            "tipo": kind,
            "autorizada": True,
            "fonte_causal": f"fixture/{matter_id}.yaml",
        }

    def test_evento_datado_e_pressao_comprometida_nao_sao_soterrados(self) -> None:
        report = routing.route_authorized(
            [
                self.matter("incidental", "iniciativa_social"),
                self.matter("operacao", "operacao_comprometida"),
                self.matter("canon", "evento_canonico_datado"),
            ]
        )

        self.assertEqual(report["resultado_modular"], "evento_canonico_datado")
        self.assertEqual(report["materia_primaria"]["id"], "canon")
        self.assertEqual(
            [item["id"] for item in report["materias_adiadas"]],
            ["operacao", "incidental"],
        )
        self.assertEqual(report["metricas"]["fontes_abertas_pelo_roteador"], 0)

    def test_gate_neutro_nao_fabrica_ameaca(self) -> None:
        report = routing.route_authorized([])
        self.assertEqual(report["resultado_modular"], "sem_materia")
        self.assertIsNone(report["materia_primaria"])
        self.assertFalse(report["efeito_materializado"])

    def test_materia_sem_autorizacao_e_rejeitada(self) -> None:
        with self.assertRaises(routing.CausalNarrativeRoutingError):
            routing.route_authorized(
                [{"id": "ameaça", "tipo": "perigo_imediato", "fonte_causal": "x"}]
            )


if __name__ == "__main__":
    unittest.main()
