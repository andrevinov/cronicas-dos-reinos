from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica
import oportunidades
import sidequests_ativas


class ActiveSidequestFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        self._yaml(
            oportunidades.INDEX,
            {
                "schema_oportunidades": 1,
                "natureza": "reservado",
                "semente": "active-sidequest-projection-fixture",
                "gate": {
                    "modo": "baralho_sem_reposicao_sha256",
                    "fichas": [
                        *[
                            {"id": f"nada_{index:02d}", "resultado": "nada"}
                            for index in range(1, 9)
                        ],
                        {"id": "oportunidade_01", "resultado": "oportunidade"},
                        {"id": "oportunidade_02", "resultado": "oportunidade"},
                    ],
                },
                "orcamento": {
                    "max_ativas": 2,
                    "max_em_aberto": 3,
                    "max_pendencias_avaliacao": 1,
                    "cooldown_oferta_dias": [2, 3],
                },
                "regras": {
                    "acionamento": "encontro_com_npc",
                    "scheduler": "proibido",
                    "scan_geral_npcs": "proibido",
                    "necessidade_nao_e_oferta": True,
                    "oferta_nao_e_aceite": True,
                    "consequencia_sem_ren_nao_e_automatica": True,
                },
                "perfis": {},
            },
        )
        self.state = {
            "schema_estado_oportunidades": 1,
            "natureza": "controle_reservado",
            "gate": {"ciclo": 0, "restantes": [], "sorteios": 0},
            "cooldown_ate": None,
            "pendencias_avaliacao": {},
            "missoes": {},
            "sementes_consumidas": [],
            "encontros_recentes": [],
            "historico_recente": [],
        }
        self._write_state()

    def tearDown(self):
        self.tmp.cleanup()

    def _yaml(self, rel: Path | str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _write_state(self) -> None:
        self._yaml(oportunidades.STATE, self.state)

    def add_mission(
        self,
        suffix: str,
        *,
        state: str = "aceita",
        origin: str = "sidequest_emergente",
    ) -> tuple[str, str]:
        mid = f"sqe-{suffix * 16}"
        qid = f"qse-{suffix * 16}"
        progress_rel = Path(
            f"narrador/sidequests-emergentes/progresso/{qid}.yaml"
        )
        mission = {
            "id": mid,
            "estado": state,
            "origem": origin,
            "quest_id": qid,
            "titulo": f"Missão {suffix}",
            "janela": {
                "tipo": "temporal",
                "expira_em": {"data": "2 Eleasis, 1372 DR", "hora": "06:00"},
            },
        }
        if origin == "sidequest_emergente":
            mission["progresso_sidequest"] = progress_rel.as_posix()
            self._yaml(
                progress_rel,
                {
                    "schema_progressao_sidequest": 1,
                    "mission_id": mid,
                    "quest_id": qid,
                    "contrato": {
                        "dependencias_fases": [
                            {
                                "fase_id": "verificar_origem",
                                "atores_necessarios": ["verificador_fixture"],
                                "substituicao_permitida": True,
                            }
                        ],
                        "efeitos_escaladas": [
                            {
                                "escalada_id": "interceptar_prova",
                                "efeitos_npc": [],
                            }
                        ],
                    },
                    "estado": {
                        "fases": {
                            "verificar_origem": {
                                "estado": "indeterminada",
                                "fato_id": None,
                            }
                        },
                        "condicoes_sucesso": {
                            "sucesso_01": {"estado": "pendente", "fato_id": None}
                        },
                        "condicoes_falha": {
                            "falha_01": {"estado": "pendente", "fato_id": None}
                        },
                        "atores": {
                            "verificador_fixture": {
                                "estado": "reservado_nao_presente",
                                "vida_estado": None,
                            }
                        },
                        "terminal": None,
                    },
                },
            )
        self.state["missoes"][mid] = mission
        self._write_state()
        return mid, qid

    @staticmethod
    def preparation(scene_id: str = "active-sidequest-fixture") -> dict:
        request = cronica._core._request(
            scene_id=scene_id,
            npcs=[],
            place=None,
            action=None,
            tier=None,
            danger=None,
            context_tags=[],
            now=None,
            approach_preparacao=None,
            approach_informacao=None,
            approach_adequacao=None,
        )
        token, ticket_id = cronica._core.encode_ticket(
            {
                "schema_cronica_ticket": cronica._core.SCHEMA,
                "preparacao_id": "turn-neutral-active-sidequest-fixture",
                "cena": request,
            }
        )
        return {
            "schema_cronica_turno": 1,
            "fase": "preparacao",
            "ticket": token,
            "ticket_id": ticket_id,
            "filtros": [],
            "disponibilidade": {},
            "fontes_lidas": [],
            "contrato_conclusao": {"campos": {}},
        }


class ActiveSidequestProjectionTest(ActiveSidequestFixture):
    def test_sem_ativas_preserva_preparacao_base_sem_fragmento_de_progresso(self):
        base = self.preparation()
        result = sidequests_ativas.integrate_prepare(
            self.repo,
            base,
            decode_ticket=cronica.decode_ticket,
            encode_ticket=cronica._core.encode_ticket,
        )
        self.assertIs(result, base)
        projection = sidequests_ativas.project(self.repo)
        self.assertEqual(projection["resultado"], "sem_ativas")
        self.assertEqual(projection["metricas"]["fragmentos_task45_lidos"], 0)

    def test_missao_aceita_e_projetada_read_only_no_ticket(self):
        mid, qid = self.add_mission("a")
        before = {
            path.relative_to(self.repo).as_posix(): path.read_bytes()
            for path in self.repo.rglob("*")
            if path.is_file()
        }
        result = sidequests_ativas.integrate_prepare(
            self.repo,
            self.preparation(),
            decode_ticket=cronica.decode_ticket,
            encode_ticket=cronica._core.encode_ticket,
        )
        after = {
            path.relative_to(self.repo).as_posix(): path.read_bytes()
            for path in self.repo.rglob("*")
            if path.is_file()
        }
        self.assertEqual(before, after)
        self.assertEqual(result["sidequests_ativas"]["quantidade"], 1)
        mission = result["sidequests_ativas"]["missoes"][0]
        self.assertEqual(mission["mission_id"], mid)
        self.assertEqual(mission["quest_id"], qid)
        self.assertEqual(mission["fases"]["verificar_origem"], "indeterminada")
        self.assertEqual(mission["pressoes_adversariais_contratadas"], ["interceptar_prova"])
        meta = sidequests_ativas.ticket_meta(cronica.decode_ticket(result["ticket"]))
        self.assertEqual(meta["missoes"][0]["mission_id"], mid)
        self.assertNotIn("fases", meta["missoes"][0])

    def test_duas_ativas_sao_ordenadas_e_respeitam_orcamento(self):
        second, _ = self.add_mission("b")
        first, _ = self.add_mission("a")
        result = sidequests_ativas.project(self.repo)
        self.assertEqual(
            [item["mission_id"] for item in result["missoes"]],
            [first, second],
        )
        self.assertEqual(result["metricas"]["fragmentos_task45_lidos"], 2)
        self.assertLessEqual(
            len(yaml.safe_dump(result, allow_unicode=True, sort_keys=False).encode("utf-8")),
            sidequests_ativas.MAX_PROJECTION_BYTES,
        )

    def test_terceira_ativa_falha_fechado(self):
        self.add_mission("a")
        self.add_mission("b")
        self.add_mission("c")
        with self.assertRaisesRegex(sidequests_ativas.ActiveSidequestError, "teto 2"):
            sidequests_ativas.project(self.repo)

    def test_estados_nao_aceitos_nao_entram_na_projecao_ativa(self):
        for suffix, state in zip("abcdef", sorted(oportunidades.MISSION_STATES - {"aceita"})):
            self.add_mission(suffix, state=state)
        result = sidequests_ativas.project(self.repo)
        self.assertEqual(result["quantidade"], 0)

    def test_legado_aceito_e_observavel_sem_abrir_progresso_emergente(self):
        mid, _ = self.add_mission("a", origin="sidequest_canonica")
        result = sidequests_ativas.project(self.repo)
        self.assertEqual(result["missoes"][0]["mission_id"], mid)
        self.assertEqual(result["missoes"][0]["progresso"], "legado_sem_task45")
        self.assertEqual(result["metricas"]["fragmentos_task45_lidos"], 0)

    def test_consulta_aceita_mission_id_quest_id_e_inexistente(self):
        mid, qid = self.add_mission("a")
        by_mid = sidequests_ativas.query(self.repo, mid)
        by_qid = sidequests_ativas.query(self.repo, qid)
        missing = sidequests_ativas.query(self.repo, "qse-ffffffffffffffff")
        self.assertTrue(by_mid["encontrada"])
        self.assertEqual(by_mid["missao"], by_qid["missao"])
        self.assertFalse(missing["encontrada"])
        self.assertEqual(missing["resultado"], "inexistente")

    def test_consulta_distingue_terminal_sem_inclui_lo_na_lista_ativa(self):
        mid, _ = self.add_mission("a", state="concluida")
        projection = sidequests_ativas.project(self.repo)
        status = sidequests_ativas.query(self.repo, mid)
        self.assertEqual(projection["quantidade"], 0)
        self.assertTrue(status["encontrada"])
        self.assertEqual(status["missao"]["estado"], "concluida")

    def test_metadados_de_autoria_e_reavaliacao_coexistem_no_mesmo_ticket(self):
        self.add_mission("a")
        base = self.preparation()
        payload = cronica.decode_ticket(base["ticket"])
        payload[cronica._sidequests46.TICKET_KEY] = {
            "schema": cronica._sidequests46.SCHEMA,
            "sinal": {"origem_tipo": "local", "ancora_tipo": "fato"},
            "pacote_digest": "a" * 64,
        }
        base["ticket"], base["ticket_id"] = cronica._core.encode_ticket(payload)
        result = sidequests_ativas.integrate_prepare(
            self.repo,
            base,
            decode_ticket=cronica.decode_ticket,
            encode_ticket=cronica._core.encode_ticket,
        )
        integrated = cronica.decode_ticket(result["ticket"])
        self.assertIsNotNone(cronica._sidequests46.ticket_meta(integrated))
        self.assertIsNotNone(sidequests_ativas.ticket_meta(integrated))

    def test_ticket_de_reavaliacao_corrompido_e_recusado(self):
        payload = {sidequests_ativas.TICKET_KEY: {"schema": 1, "missoes": []}}
        with self.assertRaisesRegex(sidequests_ativas.ActiveSidequestError, "uma ou duas"):
            sidequests_ativas.ticket_meta(payload)

    def test_decisao_negativa_nao_acorda_autoria_mas_projeta_ativa(self):
        mid, _ = self.add_mission("a")
        base = self.preparation("negative-with-active-sidequest")
        with (
            patch.object(cronica._pending_gate, "prepare_gate", return_value=None),
            patch.object(cronica._hot, "prepare", return_value=base),
            patch.object(
                cronica._sidequests46,
                "integrate_prepare",
                side_effect=AssertionError("decisão negativa não pode autorar sidequest"),
            ) as authoring,
            patch.object(
                cronica._mechanics,
                "attach_to_prepare",
                side_effect=lambda _repo, prepared, _spec, **_kwargs: prepared,
            ),
        ):
            result = cronica.prepare(
                self.repo,
                scene_id="negative-with-active-sidequest",
                sidequest_signal=None,
            )
        authoring.assert_not_called()
        self.assertEqual(result["sidequests_ativas"]["missoes"][0]["mission_id"], mid)
        self.assertIn("active_sidequest_reassessment", result["sistemas_narrativos"])

    def test_check_declara_zero_mutacao_rng_scheduler_e_scan(self):
        self.add_mission("a")
        result = sidequests_ativas.check(self.repo)
        self.assertTrue(result["ok"], result["erros"])
        contract = result["contrato"]
        self.assertEqual(contract["escritas"], 0)
        self.assertEqual(contract["rng_novo"], 0)
        self.assertEqual(contract["schedulers_novos"], 0)
        self.assertEqual(contract["scans_globais"], 0)


if __name__ == "__main__":
    unittest.main()
