from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cena_mundo
import cena_mundo_v4
import oportunidades
import sidequest_gate_v2 as retired


class RetiredSidequestGateRepositoryTest(unittest.TestCase):
    def test_repositorio_declara_aposentadoria_e_perfis_inativos(self):
        index = oportunidades.load_index(ROOT)
        self.assertEqual(index["estatuto_operacional"], retired.RETIREMENT)
        self.assertEqual(index["nova_origem_sidequests"], "canonica_explicita")
        self.assertEqual(index["gate"]["estatuto"], "legado_congelado_nao_operacional")
        self.assertFalse(index["regras"]["gate_procedural_operacional"])
        self.assertTrue(index["regras"]["encontro_nao_gera_nova_sidequest"])
        self.assertEqual(
            [npc for npc, meta in index["perfis"].items() if meta["estado"] == "ativo"],
            [],
        )

    def test_pendencia_procedural_real_foi_aposentada_sem_virar_missao(self):
        index = oportunidades.load_index(ROOT)
        state = oportunidades.load_state(ROOT, index)
        self.assertEqual(state["pendencias_avaliacao"], {})
        self.assertEqual(state["missoes"], {})
        legacy = state["legado_procedural"]
        self.assertEqual(legacy["estatuto"], "somente_auditoria_nao_operacional")
        self.assertIn("sq-5ca38554df96dc88", legacy["pendencias_aposentadas"])
        self.assertTrue(
            any(
                item.get("tipo") == "avaliacao_aposentada_task31"
                and item.get("id") == "sq-5ca38554df96dc88"
                for item in state["historico_recente"]
            )
        )

    def test_porta_de_cena_instala_adaptador_aposentado(self):
        self.assertIs(
            cena_mundo_v4._core.interacoes_mundo.encounter_event,
            retired.encounter_event,
        )
        self.assertIs(cena_mundo.prepare_scene, cena_mundo_v4.prepare_scene)
        self.assertFalse((ROOT / "ferramentas/cena_mundo_v5.py").exists())

    def test_encontro_nao_sorteia_nao_le_estado_perfil_nem_pressao(self):
        state_path = ROOT / oportunidades.STATE
        before = state_path.read_bytes()
        with mock.patch.object(
            oportunidades,
            "draw_gate",
            side_effect=AssertionError("gate procedural nao pode sortear"),
        ), mock.patch.object(
            oportunidades,
            "load_state",
            side_effect=AssertionError("encontro aposentado nao deve abrir estado"),
        ), mock.patch.object(
            oportunidades,
            "load_profile",
            side_effect=AssertionError("encontro aposentado nao deve abrir perfil"),
        ):
            result = retired.encounter_event(
                ROOT,
                "maerra_thandrel",
                encounter_id="task31:maerra",
            )
        self.assertEqual(result["resultado"], "interacao_normal")
        self.assertEqual(result["motivo"], "gate_procedural_retirado")
        self.assertEqual(result["sidequest"]["nova_origem"], "canonica_explicita")
        self.assertEqual(result["fontes_lidas"], [oportunidades.INDEX.as_posix()])
        self.assertEqual(state_path.read_bytes(), before)

    def test_alias_ainda_resolve_sem_reativar_gate(self):
        result = retired.encounter_event(ROOT, "Irmã Maerra")
        self.assertEqual(result["npc_id"], "maerra_thandrel")
        self.assertEqual(result["npc_recebido"], "Irmã Maerra")
        self.assertEqual(result["motivo"], "gate_procedural_retirado")
        self.assertNotIn(oportunidades.STATE.as_posix(), result["fontes_lidas"])

    def test_primitiva_legada_do_repo_tambem_nao_gera_potencial(self):
        state_path = ROOT / oportunidades.STATE
        before = state_path.read_bytes()
        result = oportunidades.encounter(
            ROOT,
            "maerra_thandrel",
            encounter_id="legacy-direct-task31",
        )
        self.assertEqual(result["resultado"], "interacao_normal")
        self.assertEqual(result["motivo"], "npc_sem_perfil_ativo")
        self.assertEqual(result["fontes_lidas"], [oportunidades.INDEX.as_posix()])
        self.assertEqual(state_path.read_bytes(), before)

    def test_check_real_confirma_aposentadoria_sem_consultar_pressao(self):
        result = retired.check(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["estatuto"], retired.RETIREMENT)
        self.assertEqual(result["nova_origem_sidequests"], "canonica_explicita")
        self.assertEqual(result["perfis_procedurais_ativos"], 0)
        self.assertEqual(result["pendencias_ativas"], 0)
        self.assertEqual(result["baralho_legado"]["sorteios"], 22)

    def test_baralho_e_pressao_ficam_so_como_legado_congelado(self):
        index = oportunidades.load_index(ROOT)
        results = [item["resultado"] for item in index["gate"]["fichas"]]
        self.assertEqual(results.count("nada"), 8)
        self.assertEqual(results.count("oportunidade"), 2)
        self.assertEqual(
            index["gate"]["pressao_aventura"]["estatuto"],
            "legado_congelado_nao_modula_sidequest",
        )
        self.assertFalse(index["regras"]["gate_procedural_operacional"])


class RetiredSidequestGateBudgetTest(unittest.TestCase):
    def test_novo_contrato_congela_zero_draw_zero_pressao_zero_write(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/retire-procedural-sidequest-gate-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        limits = contract["limites"]
        self.assertEqual(limits["draws_por_encontro"], 0)
        self.assertEqual(limits["leituras_pressao_por_encontro"], 0)
        self.assertEqual(limits["leituras_estado_oportunidades_por_encontro"], 0)
        self.assertEqual(limits["leituras_perfil_procedural_por_encontro"], 0)
        self.assertEqual(limits["escritas_oportunidades_por_encontro"], 0)
        self.assertEqual(limits["perfis_procedurais_ativos"], 0)
        self.assertTrue(all(contract["invariantes"].values()))


if __name__ == "__main__":
    unittest.main()
