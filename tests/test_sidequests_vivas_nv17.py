from __future__ import annotations

import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import mundo  # noqa: E402
import planos_personagens  # noqa: E402
import sidequests_personagens  # noqa: E402
import sidequests_vivas as live  # noqa: E402


class LiveSidequestDirectedTests(unittest.TestCase):
    def test_due_plan_ids_uses_only_nv08_schedule_index(self):
        now = mundo.parse_instant("21 Eleasis, 1372 DR", "12:00")
        agenda = {
            "agendamentos": [
                {
                    "id": "nv08.silva_socorro.3",
                    "tipo": "avaliar_plano_personagem",
                    "em": {"data": "21 Eleasis, 1372 DR", "hora": "10:00"},
                },
                {
                    "id": "nv08.futuro.1",
                    "tipo": "avaliar_plano_personagem",
                    "em": {"data": "21 Eleasis, 1372 DR", "hora": "14:00"},
                },
                {
                    "id": "outra.coisa",
                    "tipo": "movimento",
                    "em": {"data": "21 Eleasis, 1372 DR", "hora": "09:00"},
                },
            ]
        }
        with mock.patch.object(live.mundo, "load_agenda", return_value=agenda):
            ids, sources = live.due_plan_ids(Path("/repo"), now)
        self.assertEqual(ids, ["silva_socorro"])
        self.assertEqual(sources, [mundo.AGENDA_PATH.as_posix()])

    def _plan(self):
        return {
            "id": "silva_socorro",
            "agente": {"tipo": "leve", "id": "silva_elkwood"},
            "estado": "pretende",
            "passo": {
                "id": "pedir_ajuda",
                "em": {"data": "21 Eleasis, 1372 DR", "hora": "10:00"},
                "local": "circo_hooft",
                "condicoes": [],
                "conhecimento": ["risco_abrigo"],
                "resolucao": {"tipo": "factual"},
            },
        }

    def _contract(self):
        return {
            "versao": 1,
            "tipo": "necessidade",
            "causa": {
                "arquivo": "estado/npcs/silva_elkwood.yaml",
                "caminho": "npc.necessidades.abrigo_em_risco",
                "valor": True,
            },
            "situacao": "O abrigo perdeu uma rota segura já estabelecida.",
            "motivo_envolver_ren": "Ren conhece a trilha que permaneceu transitável.",
            "consequencias": {"nao_agir": "A rede precisa adiar o deslocamento."},
        }

    def _candidate(self, *, active: int):
        plan = self._plan()
        return {
            "id": "scp-causa",
            "plano_id": plan["id"],
            "causa": {"tipo": "necessidade"},
            "dono": plan["agente"],
            "bloqueio": {"estado_plano": "pretende", "condicoes": []},
            "conhecimento": ["risco_abrigo"],
            "alcance": {"alcança_ren": True, "tipo": "elenco_presente"},
            "reavaliacao": {"em": plan["passo"]["em"], "condicoes": []},
            "stakes": {"nao_agir": "A rede precisa adiar o deslocamento."},
            "protecoes": {"oferta_nao_e_aceite": True},
            "motivo_envolver_ren": "Ren conhece a trilha.",
            "vencida": True,
            "vencida_em_minuto": mundo.parse_instant(
                "21 Eleasis, 1372 DR", "10:00"
            ).minute,
            "prioridade_elevada_por_zero_ativas": active == 0,
        }

    def _collect(self, *, active: int, contract):
        plan = self._plan()
        world = {planos_personagens.KEY: {plan["id"]: plan}}
        index = {"orcamento": {"max_ativas": 2}}
        state = {"missoes": {}}
        candidate = self._candidate(active=active)
        now = mundo.parse_instant("21 Eleasis, 1372 DR", "12:00")
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(
                    live,
                    "due_plan_ids",
                    return_value=([plan["id"]], [mundo.AGENDA_PATH.as_posix()]),
                )
            )
            stack.enter_context(
                mock.patch.object(
                    live,
                    "_opportunity_state",
                    return_value=(index, state, ["narrador/oportunidades/estado.yaml"]),
                )
            )
            stack.enter_context(
                mock.patch.object(live, "_mission_budget", return_value=(active, active, 2))
            )
            stack.enter_context(mock.patch.object(live.mundo, "load_world_state", return_value=world))
            stack.enter_context(
                mock.patch.object(
                    live,
                    "_scene",
                    return_value=(mock.Mock(), {"localizacao": {}}, [], None),
                )
            )
            stack.enter_context(mock.patch.object(live, "_scene_local", return_value=("circo_hooft", [])))
            stack.enter_context(
                mock.patch.object(planos_personagens, "View", return_value=mock.Mock(signatures={}))
            )
            stack.enter_context(
                mock.patch.object(sidequests_personagens, "validate_definition", return_value=contract)
            )
            stack.enter_context(
                mock.patch.object(
                    sidequests_personagens,
                    "_cause_projection",
                    return_value={"id": "scp-causa"},
                )
            )
            stack.enter_context(
                mock.patch.object(sidequests_personagens, "_existing_for_cause", return_value=None)
            )
            stack.enter_context(
                mock.patch.object(live, "_live_need", return_value=(candidate, []))
            )
            return live.collect_due(
                Path("/repo"), now=now, participants=["silva_elkwood"]
            )

    def test_presence_and_zero_active_do_not_create_cause(self):
        result = self._collect(active=0, contract=None)
        self.assertEqual(result["causas"], [])
        self.assertIsNone(result["selecionada"])
        self.assertEqual(result["resultado"], "sem_causa_nv11_vencida")

    def test_zero_active_only_boosts_valid_existing_cause(self):
        result = self._collect(active=0, contract=self._contract())
        self.assertEqual(result["selecionada"]["id"], "scp-causa")
        self.assertTrue(result["selecionada"]["prioridade_elevada_por_zero_ativas"])
        self.assertEqual(result["metricas"]["catalogo_legado_lido"], 0)
        self.assertEqual(result["metricas"]["chamadas_ia"], 0)

    def test_active_limit_blocks_new_opportunity_without_erasing_cause(self):
        result = self._collect(active=2, contract=self._contract())
        self.assertEqual(len(result["causas"]), 1)
        self.assertIsNone(result["selecionada"])
        self.assertEqual(result["resultado"], "limite_ativas")

    def test_same_local_without_confirmed_presence_is_not_reach(self):
        plan = self._plan()
        with mock.patch.object(
            live,
            "_canonical_local",
            return_value=("circo_hooft", ["cenario/locais/index.yaml"]),
        ):
            reach, _ = live._reach(
                Path("/repo"),
                view=mock.Mock(),
                plan=plan,
                present=set(),
                local_id="circo_hooft",
            )
        self.assertFalse(reach["alcança_ren"])
        self.assertEqual(reach["tipo"], "mesmo_local_sem_presenca_confirmada")


class LiveSidequestWindowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / live.STATE.parent).mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _projection(plan_id: str, cause_id: str):
        return {
            "schema_sidequests_vivas": 1,
            "resultado": "causa_viva_alcancavel",
            "selecionada": {
                "id": cause_id,
                "plano_id": plan_id,
                "alcance": {"alcança_ren": True, "tipo": "elenco_presente"},
            },
            "causas": [],
            "orcamento": {"ativas": 0, "abertas": 0, "max_ativas": 2},
            "local_id": "circo_hooft",
            "fontes_lidas": [],
        }

    def test_negative_manual_decision_cannot_hide_due_cause_and_retry_is_stable(self):
        now = mundo.parse_instant("21 Eleasis, 1372 DR", "12:00")
        window = {
            "id": "21 Eleasis, 1372 DR|dia",
            "data": "21 Eleasis, 1372 DR",
            "periodo": "dia",
        }
        projection = self._projection("plano_a", "scp-a")
        with mock.patch.object(live, "_now", return_value=(now, [])), mock.patch.object(
            live, "_window", return_value=(window, [])
        ), mock.patch.object(live, "collect_due", return_value=projection) as collect:
            routed_a = live.route_prepare(self.repo, manual_signal=None, danger="media")
            routed_b = live.route_prepare(self.repo, manual_signal=None, danger="media")
        self.assertEqual(routed_a["sinal_efetivo"]["plano_id"], "plano_a")
        self.assertEqual(routed_b["sinal_efetivo"]["plano_id"], "plano_a")
        self.assertEqual(routed_b["resultado"], "reserva_reutilizada")
        self.assertEqual(collect.call_count, 1)
        self.assertEqual(len(live.load_state(self.repo)["janelas"]), 1)

    def test_due_cause_precedes_new_scene_anchor_in_same_window(self):
        now = mundo.parse_instant("21 Eleasis, 1372 DR", "12:00")
        window = {
            "id": "21 Eleasis, 1372 DR|dia",
            "data": "21 Eleasis, 1372 DR",
            "periodo": "dia",
        }
        projection = self._projection("plano_a", "scp-a")
        manual = {
            "origem_tipo": "evento_cena",
            "origem_id": "cena-1",
            "ancora_tipo": "fato",
            "ancora": "algo concreto surgiu na própria cena",
            "npc_id": None,
            "local_id": "circo_hooft",
            "periculosidade": "media",
            "tier": None,
        }
        with mock.patch.object(live, "_now", return_value=(now, [])), mock.patch.object(
            live, "_window", return_value=(window, [])
        ), mock.patch.object(live, "collect_due", return_value=projection):
            routed = live.route_prepare(
                self.repo, manual_signal=manual, danger="media"
            )
        self.assertEqual(routed["sinal_efetivo"]["plano_id"], "plano_a")
        self.assertTrue(routed["ancora_manual_adiada"])


if __name__ == "__main__":
    unittest.main()
