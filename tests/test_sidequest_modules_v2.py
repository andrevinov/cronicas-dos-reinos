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

import canonical_quest_integration as canonical
import cronica
from ferramentas import preflight
import sidequest_authoring as authoring
import sidequest_lifecycle as lifecycle


class SidequestModuleContractTest(unittest.TestCase):
    def test_tres_fachadas_cobrem_exatamente_os_nove_aliases_v1(self) -> None:
        catalog = json.loads(
            (ROOT / "evaluation/catalogo-modulos-v2.json").read_text(encoding="utf-8")
        )
        expected = {
            alias: (module["id"], capability["id"])
            for module in catalog["modulos"]
            if module["id"] in {authoring.MODULE_ID, lifecycle.MODULE_ID, canonical.MODULE_ID}
            for capability in module["subcapacidades"]
            for alias in capability["aliases_v1"]
        }
        actual = {
            alias: facade.MODULE_ID
            for facade in (authoring, lifecycle, canonical)
            for alias in facade.LEGACY_ALIASES
        }
        self.assertEqual(len(expected), 9)
        self.assertEqual(set(actual), set(expected))
        self.assertTrue(
            all(actual[alias] == destination[0] for alias, destination in expected.items())
        )

        versions = {
            module["id"]: module["versao_implementacao"]
            for module in catalog["modulos"]
        }
        self.assertEqual(catalog["versao_catalogo"], "2.5.0")
        self.assertEqual(versions[authoring.MODULE_ID], "1.0.0")
        self.assertEqual(versions[lifecycle.MODULE_ID], "1.0.0")
        self.assertEqual(versions[canonical.MODULE_ID], "1.0.0")

    def test_cronica_e_cena_dependem_das_fachadas_publicas(self) -> None:
        self.assertIs(cronica._sidequests46, authoring)
        self.assertIs(cronica._sidequests48, lifecycle)
        self.assertIs(cronica._sidequests49, lifecycle)
        source = (TOOLS / "_cronica_nv14.py").read_text(encoding="utf-8")
        self.assertNotIn("import sidequests_integracao_runtime as _sidequests46", source)
        self.assertNotIn("import sidequests_ativas as _sidequests48", source)
        self.assertNotIn("import progresso_sidequests_transacional as _sidequests49", source)
        scene_source = (TOOLS / "sidequests_canonicas_cena.py").read_text(encoding="utf-8")
        self.assertIn("import canonical_quest_integration as _canonical_quests", scene_source)

    def test_preflight_publica_tres_checks_e_mantem_motores_internos_frios(self) -> None:
        commands = {tuple(item.comando[1:]) for item in preflight.checks(incluir_testes=False)}
        self.assertTrue(
            {
                ("ferramentas/sidequest_authoring.py", "check"),
                ("ferramentas/sidequest_lifecycle.py", "check"),
                ("ferramentas/canonical_quest_integration.py", "check"),
            }
            <= commands
        )
        self.assertFalse(preflight._SIDEQUEST_INTERNAL_CHECKS & commands)

    def test_check_agrega_falha_sem_apagar_diagnostico_do_motor(self) -> None:
        healthy = {"ok": True, "erros": [], "evidencia": "preservada"}
        failure = {"ok": False, "erros": ["falha sintética"]}
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(authoring._opportunity, "check", return_value=healthy),
            patch.object(authoring._registry, "validate_repo", return_value=healthy),
            patch.object(authoring._authoring, "check", return_value=failure),
            patch.object(authoring._integration, "check", return_value=healthy),
            patch.object(authoring._live_causes, "check", return_value=healthy),
        ):
            report = authoring.check(Path(temporary))
        self.assertFalse(report["ok"])
        self.assertIn("quest_authoring: falha sintética", report["erros"])
        self.assertEqual(
            report["componentes"]["opportunity_gate"]["evidencia"],
            "preservada",
        )


class SidequestAuthoringFacadeTest(unittest.TestCase):
    def test_sem_oferta_nao_abre_journal_nem_instala(self) -> None:
        payload = {"cena": {"scene_id": "fixture-rm03"}}
        transaction = {"narracao": "Nenhuma oferta foi feita."}
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(authoring, "recover_matching_journal", return_value=None),
            patch.object(authoring, "_plan_from_ticket", return_value={"pacote": True}),
            patch.object(authoring, "_normalize_offer", return_value=(None, None)),
            patch.object(authoring, "begin_conclusion") as begin,
            patch.object(authoring, "install") as install,
        ):
            prepared = authoring.prepare_conclusion(
                Path(temporary),
                ticket_id="ticket-rm03",
                ticket_payload=payload,
                ticket_meta_value={"schema": 1},
                transaction=transaction,
            )
            result = authoring.install_conclusion(Path(temporary), prepared)
        begin.assert_not_called()
        install.assert_not_called()
        self.assertEqual(result["resultado"], "oferta_nao_materializada")
        self.assertEqual(result["mutacoes_sidequest"], 0)

    def test_oferta_preparada_usa_um_unico_journal_e_instalacao(self) -> None:
        journal = {"id": "journal-rm03"}
        with (
            tempfile.TemporaryDirectory() as temporary,
            patch.object(authoring, "recover_matching_journal", return_value=journal),
            patch.object(
                authoring,
                "install",
                return_value={"ok": True, "resultado": "sidequest_materializada"},
            ) as install,
        ):
            prepared = authoring.prepare_conclusion(
                Path(temporary),
                ticket_id="ticket-rm03",
                ticket_payload={"cena": {"scene_id": "fixture-rm03"}},
                ticket_meta_value={"schema": 1},
                transaction={"narracao": "Oferta literal."},
            )
            result = authoring.install_conclusion(Path(temporary), prepared)
        install.assert_called_once_with(Path(temporary), journal)
        self.assertEqual(result["resultado"], "sidequest_materializada")


if __name__ == "__main__":
    unittest.main()
