from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import checkpoint
import clima_diario as climate
import incidentes_mundo as incidents
import microeventos_transito as transit
import permanencia_espacial
import preflight


class ClimateCheckpointCompositionTest(unittest.TestCase):
    def test_checkpoint_reconcilia_clima_sem_novo_scheduler(self):
        base = {"configurado": True, "alterou": False, "novas_pendencias": []}
        climate_result = {"configurado": True, "alterou": True, "avaliacoes": [{"data": "x"}]}
        with mock.patch.object(checkpoint.obrigacoes_temporais, "sync_checkpoint", return_value={}), \
             mock.patch.object(checkpoint, "_BASE_SYNC_WORLD", return_value=base), \
             mock.patch.object(checkpoint.clima_diario, "sync_dawn", return_value=climate_result) as sync:
            result = checkpoint.sync_world(Path("/fixture"))
        sync.assert_called_once_with(Path("/fixture"))
        self.assertEqual(result["clima_diario"], climate_result)
        self.assertEqual(result["novas_pendencias"], [])


class ClimateSceneCompositionTest(unittest.TestCase):
    def test_permanencia_expoe_sensorial_e_disponibilidade_sem_sortear(self):
        repo = Path("/fixture")
        base = {"publico": {"local_id": "circo", "fontes_lidas": ["base.yaml"]}}
        active = {
            "id": "clima-aaaaaaaaaaaaaaaa",
            "estado": "chuva_forte",
            "sensorial": ["chuva forte"],
            "espacos": {"exteriores": "restrito", "expostos": "restrito", "marcadores": []},
        }
        with mock.patch.object(permanencia_espacial, "_BASE_PREPARE_NV15", return_value=copy.deepcopy(base)), \
             mock.patch.object(permanencia_espacial, "_has_entry_plans", return_value=False), \
             mock.patch.object(permanencia_espacial._climate, "configured", return_value=True), \
             mock.patch.object(permanencia_espacial._climate, "for_scene", return_value={
                 "ativo": active, "fontes_lidas": ["estado/clima-diario.yaml"]
             }) as view:
            result = permanencia_espacial.prepare(repo, scene_id="cena")
        view.assert_called_once_with(repo, "circo", now=None)
        self.assertEqual(result["publico"]["clima"], active)
        self.assertEqual(result["publico"]["clima"]["espacos"]["exteriores"], "restrito")


class ClimateTransitCompositionTest(unittest.TestCase):
    def test_clima_entra_no_fingerprint_e_payload_sem_rerroll(self):
        repo = Path("/fixture")
        base = {
            "publico": {"fontes_lidas": ["a", "b", "c", "d"], "resultado": "rotina"},
            "fingerprint": "a" * 64,
            "estado_planejado": {},
            "alterou": True,
            "confirmado": False,
        }
        weather = {
            "configurado": True,
            "regiao": "ravens_bluff",
            "ativo": {
                "id": "clima-aaaaaaaaaaaaaaaa",
                "estado": "vento",
                "intensidade": "moderada",
                "deslocamento": {"tempo_percentual": 110, "marcadores": ["vento_forte"]},
                "fingerprint": "b" * 64,
            },
            "fontes_lidas": ["estado/clima-diario.yaml", "estado/tempo.yaml"],
        }
        expected = hashlib.sha256(("a" * 64 + "|nv21|" + "b" * 64).encode("utf-8")).hexdigest()
        with mock.patch.object(transit, "_BASE_PLAN_NV20", return_value=copy.deepcopy(base)), \
             mock.patch.object(transit._climate, "configured", return_value=True), \
             mock.patch.object(transit._climate, "for_travel", return_value=weather):
            result = transit.plan(repo, scene_id="move")
        self.assertEqual(result["fingerprint"], expected)
        self.assertEqual(result["publico"]["clima_diario"]["deslocamento"]["tempo_percentual"], 110)
        self.assertEqual(len(result["publico"]["fontes_lidas"]), 6)


class ClimateIncidentCompositionTest(unittest.TestCase):
    def test_chuva_forte_alimenta_filtro_existente_de_incidentes(self):
        condition = {
            "tipo": "clima",
            "intensidade": "forte",
            "marcadores": ["chuva_forte", "piso_molhado", "visibilidade_reduzida"],
        }
        tokens = incidents.condition_tokens([condition])
        self.assertIn("chuva_forte", tokens)
        self.assertIn("tipo_clima", tokens)
        index = incidents.load_index(ROOT)
        card = index["cartas"]["queda_em_piso_molhado"]
        self.assertTrue(set(card["condicoes_necessarias"]) <= tokens)


class ClimateBudgetAndPreflightTest(unittest.TestCase):
    def test_orcamento_congela_zero_ia_scheduler_e_rng_opaco(self):
        import yaml
        contract = yaml.safe_load((ROOT / "baseline/clima-diario-nv21-orcamento.yaml").read_text(encoding="utf-8"))
        self.assertEqual(contract["limites"]["max_avaliacoes_por_dia_regiao"], 1)
        self.assertFalse(contract["arquitetura"]["scheduler_novo"])
        self.assertFalse(contract["arquitetura"]["chamada_ia"])
        self.assertFalse(contract["arquitetura"]["rng_opaco"])
        source = (ROOT / "ferramentas/clima_diario.py").read_text(encoding="utf-8")
        self.assertNotIn("import random", source)
        self.assertNotIn("import secrets", source)
        self.assertNotIn("apscheduler", source.lower())

    def test_preflight_inclui_gate_read_only_do_clima(self):
        rows = [item for item in preflight.checks(incluir_testes=False) if item.nome == "clima diário determinístico"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].comando[-2:], ("ferramentas/clima_diario.py", "check"))


if __name__ == "__main__":
    unittest.main()
