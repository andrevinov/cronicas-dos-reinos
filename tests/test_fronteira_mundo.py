from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).parents[1] / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import agentes_leves
import direcoes
import entradas
import eventos_mundo
import fronteira_mundo
import mundo


class FronteiraMundoTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        for rel in (
            direcoes.INDEX_PATH,
            direcoes.STATE_PATH,
            entradas.INDEX,
            entradas.STATE,
            agentes_leves.INDEX,
            agentes_leves.STATE,
            eventos_mundo.INDEX,
            eventos_mundo.STATE,
        ):
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("placeholder: true\n", encoding="utf-8")

        self.start = mundo.parse_instant("11 Eleasis, 1372 DR", "05:10")
        self.agenda = {
            "hora_amanhecer": "06:00",
            "reavaliacoes": {
                "red_sail": {
                    "cadencia": "amanhecer",
                    "intervalo_dias": 1,
                    "inicio": "11 Eleasis, 1372 DR",
                    "motivo": "teste",
                },
                "night_watch": {
                    "cadencia": "amanhecer",
                    "intervalo_dias": 1,
                    "inicio": "11 Eleasis, 1372 DR",
                    "motivo": "teste",
                },
            },
            "agendamentos": [],
        }
        self.world_state = {"pendencias": [], "concluidas_recentes": []}
        self.direction_index = {
            "direcoes": {
                "ponte": {
                    "avaliacao": {
                        "inicio": "11 Eleasis, 1372 DR",
                        "intervalo_dias": 1,
                    }
                }
            }
        }
        self.direction_state = {"direcoes": {"ponte": {"estado": "ativa"}}}
        self.entry_index = {
            "candidatos": {
                "shen": {"ordem": 1},
                "joen": {"ordem": 2},
            }
        }
        self.entry_state = {
            "candidatos": {
                "shen": {
                    "estado": "latente",
                    "antecipado": False,
                    "proxima_avaliacao": {
                        "data": "11 Eleasis, 1372 DR",
                        "hora": "06:00",
                    },
                },
                "joen": {
                    "estado": "latente",
                    "antecipado": False,
                    "proxima_avaliacao": None,
                },
            }
        }
        self.light_index = {
            "orcamento": {"max_pendencias_abertas": 2},
            "agentes": {
                "kethra": {"estado": "ativo"},
                "bram": {"estado": "ativo"},
            },
        }
        self.light_state = {
            "agentes": {
                "kethra": {
                    "proxima_avaliacao": {
                        "data": "11 Eleasis, 1372 DR",
                        "hora": "06:00",
                    }
                },
                "bram": {
                    "proxima_avaliacao": {
                        "data": "12 Eleasis, 1372 DR",
                        "hora": "06:00",
                    }
                },
            }
        }
        self.event_index = {
            "inicio": {"data": "11 Eleasis, 1372 DR", "hora": "06:00"}
        }
        self.event_state = {
            "processado_ate": {"data": "10 Eleasis, 1372 DR", "hora": "06:00"}
        }

    def tearDown(self):
        self.temp.cleanup()

    def run_boundary(self, target: mundo.WorldInstant, *, agenda=None, world_state=None):
        with (
            patch.object(
                fronteira_mundo.mundo,
                "load_canonical_time",
                return_value=(self.start, {}),
            ),
            patch.object(
                fronteira_mundo.mundo,
                "load_agenda",
                return_value=agenda or self.agenda,
            ),
            patch.object(
                fronteira_mundo.mundo,
                "load_world_state",
                return_value=world_state or self.world_state,
            ),
            patch.object(
                fronteira_mundo.direcoes,
                "load_index",
                return_value=self.direction_index,
            ),
            patch.object(
                fronteira_mundo.direcoes,
                "load_state",
                return_value=self.direction_state,
            ),
            patch.object(
                fronteira_mundo.entradas,
                "load_index",
                return_value=self.entry_index,
            ),
            patch.object(
                fronteira_mundo.entradas,
                "load_state",
                return_value=self.entry_state,
            ),
            patch.object(
                fronteira_mundo.agentes_leves,
                "load_index",
                return_value=self.light_index,
            ),
            patch.object(
                fronteira_mundo.agentes_leves,
                "load_state",
                return_value=self.light_state,
            ),
            patch.object(
                fronteira_mundo.eventos_mundo,
                "load_index",
                return_value=self.event_index,
            ),
            patch.object(
                fronteira_mundo.eventos_mundo,
                "load_state",
                return_value=self.event_state,
            ),
        ):
            return fronteira_mundo.next_boundary(self.repo, target)

    def test_0510_ate_1150_para_no_amanhecer_e_agrupa_camadas(self):
        target = mundo.parse_instant("11 Eleasis, 1372 DR", "11:50")
        result = self.run_boundary(target)

        self.assertTrue(result["interromper"])
        self.assertEqual(result["fronteira"]["data"], "11 Eleasis, 1372 DR")
        self.assertEqual(result["fronteira"]["hora"], "06:00")
        self.assertEqual(result["fronteira"]["minutos_ate_fronteira"], 50)
        reasons = {
            item["camada"]: item["ids"] for item in result["fronteira"]["motivos"]
        }
        self.assertEqual(reasons["agentes_estrategicos"], ["night_watch", "red_sail"])
        self.assertEqual(reasons["direcoes"], ["ponte"])
        self.assertEqual(reasons["entradas"], ["shen"])
        self.assertEqual(reasons["agentes_leves"], ["kethra"])
        self.assertEqual(reasons["eventos_mundo"], ["baralho_mundial"])

    def test_alvo_antes_da_primeira_fronteira_nao_interrompe(self):
        target = mundo.parse_instant("11 Eleasis, 1372 DR", "05:59")
        result = self.run_boundary(target)
        self.assertFalse(result["interromper"])
        self.assertIsNone(result["fronteira"])

    def test_fronteira_exatamente_no_alvo_interrompe(self):
        target = mundo.parse_instant("11 Eleasis, 1372 DR", "06:00")
        result = self.run_boundary(target)
        self.assertTrue(result["interromper"])
        self.assertEqual(result["fronteira"]["hora"], "06:00")

    def test_agendamento_exato_anterior_vence_o_amanhecer(self):
        agenda = copy.deepcopy(self.agenda)
        agenda["agendamentos"] = [
            {
                "id": "mensageiro-0540",
                "tipo": "movimento",
                "agente": "red_sail",
                "em": {"data": "11 Eleasis, 1372 DR", "hora": "05:40"},
                "motivo": "teste",
            }
        ]
        target = mundo.parse_instant("11 Eleasis, 1372 DR", "11:50")
        result = self.run_boundary(target, agenda=agenda)
        self.assertEqual(result["fronteira"]["hora"], "05:40")
        self.assertEqual(
            result["fronteira"]["motivos"],
            [{"camada": "agendamentos", "ids": ["mensageiro-0540"]}],
        )

    def test_consulta_nao_expoe_fragmentos(self):
        target = mundo.parse_instant("11 Eleasis, 1372 DR", "11:50")
        result = self.run_boundary(target)
        self.assertLessEqual(len(result["fontes_lidas"]), 11)
        self.assertFalse(
            any(
                "/perfis/" in path
                or "/cartas/" in path
                or (
                    path.startswith("narrador/agentes/")
                    and path != "narrador/agentes/index.yaml"
                )
                for path in result["fontes_lidas"]
            )
        )

    def test_alvo_no_passado_e_rejeitado(self):
        target = mundo.parse_instant("11 Eleasis, 1372 DR", "05:09")
        with self.assertRaises(fronteira_mundo.BoundaryError):
            self.run_boundary(target)


class FronteiraRouterContractTest(unittest.TestCase):
    def test_agents_exige_fronteira_antes_de_comprimir_horas(self):
        agents = (Path(__file__).parents[1] / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("fronteira_mundo.py", agents)
        self.assertIn("antes de narrar", agents.lower())
        self.assertIn("dormir", agents.lower())
        self.assertIn("não chamar", agents.lower())


if __name__ == "__main__":
    unittest.main()
