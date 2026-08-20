from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import arco_mundo


class ArcWorldGuardTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        for rel in (
            "narrador/arcos/index.yaml",
            "narrador/arcos/estado.yaml",
            "narrador/arcos/parte_1_uma_ponte_para_kozakura.yaml",
            "narrador/arcos/controle-mundo.yaml",
            "narrador/arcos/marcos-aparicao.yaml",
            "narrador/arcos/estado-marcos-aparicao.yaml",
        ):
            src = ROOT / rel
            dst = self.repo / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        controlled = yaml.safe_load((ROOT / "narrador/arcos/controle-mundo.yaml").read_text(encoding="utf-8"))["agentes_estrategicos"]
        agents = {
            agent_id: {
                "nome": agent_id,
                "tipo": "npc" if agent_id != "juppongatana" else "faccao",
                "estado": "ativo",
                "presenca": "presente",
                "atuacao_local": "exige_presenca_fisica" if agent_id != "juppongatana" else "depende_de_membros_presentes",
                "arquivo": f"narrador/agentes/{agent_id}.yaml",
            }
            for agent_id in controlled
        }
        agents["sawagejo_cho"]["estado"] = "latente"
        agents["pan_chu"]["estado"] = "latente"
        agents["night_watch"] = {
            "nome": "Night Watch",
            "tipo": "instituicao",
            "estado": "ativo",
            "presenca": "ancorada",
            "atuacao_local": "estrutura_local",
            "arquivo": "narrador/agentes/night_watch.yaml",
        }
        path = self.repo / "narrador/agentes/index.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump({"schema_agentes": 2, "natureza": "reservado", "agentes": agents}, allow_unicode=True, sort_keys=False), encoding="utf-8")
        runtime = self.repo / "runtime/contexto.yaml"
        runtime.parent.mkdir(parents=True, exist_ok=True)
        runtime.write_text(yaml.safe_dump({"personagem": {"nivel": 6}}, sort_keys=False), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_agente_fora_do_escopo_do_arco_permanece_livre(self):
        gate = arco_mundo.strategic_agent_gate(self.repo, "night_watch", purpose="reavaliacao")
        self.assertTrue(gate["permitido"])
        self.assertFalse(gate["controlado_pelo_arco"])

    def test_kurobane_pode_ser_reavaliado_porque_arco_e_linha_permitam(self):
        gate = arco_mundo.strategic_agent_gate(self.repo, "kurobane_jinzaburo", purpose="reavaliacao")
        self.assertTrue(gate["permitido"])
        self.assertIn("impedir_consolidacao_de_provas", gate["linhas_operacionais"])

    def test_cho_esta_no_arco_mas_marco_ainda_bloqueia_primeira_aparicao(self):
        presence = arco_mundo.strategic_agent_gate(self.repo, "sawagejo_cho", purpose="presenca")
        action = arco_mundo.strategic_agent_gate(self.repo, "sawagejo_cho", purpose="reavaliacao")
        self.assertFalse(presence["permitido"])
        self.assertIn(presence["motivo"], {
            "nivel_minimo_do_marco_nao_alcancado",
            "condicao_narrativa_do_marco_ainda_bloqueada",
        })
        self.assertFalse(action["permitido"])
        self.assertEqual(action["motivo"], "agente_ainda_nao_ativo_no_mundo")
        self.assertIn("pressionar_identidade_marcial_de_ren", action["linhas_operacionais"])

    def test_kurobane_consumido_pode_reaparecer_e_se_mover(self):
        presence = arco_mundo.strategic_agent_gate(self.repo, "kurobane_jinzaburo", purpose="presenca")
        movement = arco_mundo.strategic_agent_gate(self.repo, "kurobane_jinzaburo", purpose="movimento")
        self.assertTrue(presence["permitido"])
        self.assertTrue(movement["permitido"])
        self.assertEqual(presence["marco_aparicao"]["estado_marco"], "consumido")

    def test_shizune_elegivel_passa_marco_sem_canonizar_presenca(self):
        presence = arco_mundo.strategic_agent_gate(self.repo, "kajiwara_shizune", purpose="presenca")
        self.assertTrue(presence["permitido"])
        self.assertEqual(presence["marco_aparicao"]["modo"], "avaliar_primeira_aparicao")

    def test_anji_fica_bloqueado_na_parte_1(self):
        gate = arco_mundo.strategic_agent_gate(self.repo, "yukyuzan_anji", purpose="movimento")
        self.assertFalse(gate["permitido"])
        self.assertEqual(gate["motivo"], "agente_bloqueado_pelo_arco")

    def test_masao_como_plano_mestre_nao_precisa_ser_listado_nas_linhas(self):
        gate = arco_mundo.strategic_agent_gate(self.repo, "masao_hirasawa", purpose="reavaliacao")
        self.assertTrue(gate["permitido"])
        self.assertEqual(gate["motivo"], "agente_mestre_do_arco")

    def test_direcoes_e_entradas_sao_filtradas_pelo_arco(self):
        self.assertTrue(arco_mundo.direction_gate(self.repo, "ponte_de_kozakura")["permitido"])
        self.assertFalse(arco_mundo.direction_gate(self.repo, "shin_kozakura")["permitido"])
        self.assertTrue(arco_mundo.entry_gate(self.repo, "shen_meihua")["permitido"])
        self.assertFalse(arco_mundo.entry_gate(self.repo, "dame_jenilynn_leyland")["permitido"])

    def test_triggers_temporais_bloqueiam_agente_de_arco_sem_linha_ou_fora_do_arco(self):
        records = [
            {"id": "a", "tipo": "reavaliar_agente", "agente": "night_watch"},
            {"id": "b", "tipo": "reavaliar_agente", "agente": "kurobane_jinzaburo"},
            {"id": "c", "tipo": "reavaliar_agente", "agente": "sawagejo_cho"},
            {"id": "d", "tipo": "movimento", "agente": "yukyuzan_anji"},
            {"id": "e", "tipo": "expiracao", "agentes_afetados": ["yukyuzan_anji"]},
        ]
        result = arco_mundo.filter_world_triggers(self.repo, records)
        self.assertEqual([x["id"] for x in result["permitidos"]], ["a", "b", "e"])
        self.assertEqual([x["id"] for x in result["bloqueados"]], ["c", "d"])

    def test_evento_mundial_nao_e_cancelado_so_perde_agentes_bloqueados(self):
        result = arco_mundo.filter_event_agents(
            self.repo,
            ["night_watch", "kurobane_jinzaburo", "sawagejo_cho", "yukyuzan_anji"],
        )
        self.assertEqual(result["permitidos"], ["night_watch", "kurobane_jinzaburo"])
        self.assertEqual(
            {x["agente"] for x in result["bloqueados"]},
            {"sawagejo_cho", "yukyuzan_anji"},
        )

    def test_prune_remove_pendencias_incompativeis_sem_apagar_evento(self):
        state = {
            "pendencias": [
                {"id": "p1", "tipo": "reavaliar_agente", "agente": "yukyuzan_anji"},
                {"id": "p2", "tipo": "avaliar_direcao", "direcao": "shin_kozakura"},
                {"id": "p3", "tipo": "avaliar_entrada", "entrada": "dame_jenilynn_leyland"},
                {"id": "p4", "tipo": "reavaliar_agente", "agente": "night_watch"},
                {"id": "p5", "tipo": "evento_mundial", "agentes_afetados": ["night_watch", "yukyuzan_anji"]},
            ]
        }
        result = arco_mundo.prune_pending(self.repo, state)
        by_id = {x["id"]: x for x in result["estado"]["pendencias"]}
        self.assertEqual(set(by_id), {"p4", "p5"})
        self.assertEqual(by_id["p5"]["agentes_afetados"], ["night_watch"])
        self.assertEqual({x["id"] for x in result["pendencias_removidas"]}, {"p1", "p2", "p3"})

    def test_validacao_confirma_registro_controlado_e_plano_mestre(self):
        result = arco_mundo.validate(self.repo)
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(result["agentes_controlados"], 10)


if __name__ == "__main__":
    unittest.main()
