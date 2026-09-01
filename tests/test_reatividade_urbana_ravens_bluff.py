from __future__ import annotations

from pathlib import Path
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "narrador/arcos/parte_1/teia-urbana-ravens-bluff/index.yaml"
VIDA_CIVIL = ROOT / "narrador/arcos/parte_1/vida-civil.yaml"
EVENTOS = ROOT / "narrador/arcos/parte_1/eventos-canonicos.yaml"


def load_yaml(path: Path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


class RavensBluffUrbanReactivityTests(unittest.TestCase):
    def test_index_preserves_agency_and_reactive_boundaries(self):
        data = load_yaml(INDEX)
        self.assertEqual(data["schema_teia_urbana_ravens_bluff"], 1)
        self.assertEqual(data["natureza"], "reservado")
        self.assertEqual(data["cidade"], "ravens_bluff")
        self.assertEqual(data["fronteira_integracao"]["data"], "20 Eleasis, 1372 DR")
        self.assertEqual(data["fronteira_integracao"]["retroatividade"], "proibida")
        self.assertEqual(data["regras"]["scheduler"], "proibido")
        self.assertEqual(data["regras"]["aparicao_automatica"], "proibida")
        self.assertEqual(data["regras"]["sidequest_automatica"], "proibida")
        self.assertEqual(data["regras"]["conhecimento_automatico_de_ren"], "proibido")
        self.assertEqual(data["regras"]["alinhamento_fixo_com_ren_ou_masao"], "proibido")
        self.assertTrue(data["regras"]["usar_objetivo_proprio_do_npc"])
        self.assertIn("Task40", data["integracao_operacional"]["sidequests"])
        self.assertLessEqual(len(INDEX.read_bytes()), 8192)

    def test_fragmentos_are_directed_small_and_causally_authored(self):
        index = load_yaml(INDEX)
        total_nucleos = 0
        for route_id, route in index["roteador"].items():
            fragment_path = ROOT / route["arquivo"]
            self.assertTrue(fragment_path.is_file(), route_id)
            self.assertLessEqual(len(fragment_path.read_bytes()), 4096, route_id)
            fragment = load_yaml(fragment_path)
            self.assertEqual(fragment["schema_fragmento_teia_urbana"], 1)
            self.assertEqual(fragment["natureza"], "reservado")
            self.assertEqual(fragment["id"], route_id)
            for npc in (fragment.get("nucleos") or {}).values():
                total_nucleos += 1
                self.assertTrue(npc["objetivo_proprio"])
                self.assertEqual(set(npc["vetores"]), {"ren", "masao", "ambos"})
                self.assertTrue(npc["sidequests"]["exige_ancora_causal"])
                self.assertTrue(npc["mundo_vivo"]["sinais"])
                self.assertTrue(npc["guardrails"])
                self.assertNotIn("alinhamento_fixo", npc)
        self.assertGreaterEqual(total_nucleos, 5)

    def test_preferred_breathing_windows_do_not_collide_with_dated_canon(self):
        urban = load_yaml(INDEX)
        canon = load_yaml(EVENTOS)
        due_dates = {
            event["ativacao"]["data"]
            for event in canon["eventos"].values()
            if isinstance(event, dict) and isinstance(event.get("ativacao"), dict)
        }
        for date in urban["janelas_preferenciais"]["primeiras_folgas"]:
            self.assertNotIn(date, due_dates)

    def test_vida_civil_routes_to_the_urban_layer_without_automation(self):
        vida = load_yaml(VIDA_CIVIL)
        route = vida["teia_urbana_ravens_bluff"]
        self.assertEqual(
            route["arquivo"],
            "narrador/arcos/parte_1/teia-urbana-ravens-bluff/index.yaml",
        )
        self.assertFalse(route["automatico"])

    def test_sensitive_continuity_guards_remain_explicit(self):
        index = load_yaml(INDEX)
        masks = load_yaml(ROOT / index["roteador"]["mascaras_frascos"]["arquivo"])
        narwhal = load_yaml(ROOT / index["roteador"]["narwhal_futuro"]["arquivo"])
        self.assertTrue(
            any(
                "falsificador da calaria" in guard
                for guard in masks["nucleos"]["mortimer_mittlemer"]["guardrails"]
            )
        )
        self.assertTrue(
            any(
                "retroativa" in guard
                for guard in narwhal["nucleos"]["docara"]["guardrails"]
            )
        )


if __name__ == "__main__":
    unittest.main()
