from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import endpoints
import mundo
import torneio_clandestino as tour
import torneio_clandestino_cena as tour_scene


class TournamentRepositoryTest(unittest.TestCase):
    def test_repo_real_valida_quadro_multinoite_sem_retroatividade(self):
        result = tour.check(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(set(result["regioes"]), {"faerun", "kara_tur"})
        index = tour.load_index(ROOT)
        state = tour.load_state(ROOT, index)
        self.assertEqual(len(index["agenda_relativa"]), 5)
        self.assertEqual(index["agenda_relativa"][-1]["offset_dias"], 14)
        self.assertTrue(index["agenda_relativa"][-1]["final"])
        self.assertEqual(state["estado"], "latente")
        self.assertEqual(state["agenda"], [])

    def test_documentacao_publica_permanece_spoiler_light(self):
        public = (ROOT / "docs/task37-underground-tournament-mini-arc.md").read_text(encoding="utf-8").lower()
        index = tour.load_index(ROOT)
        for item in index["agenda_relativa"][:-1]:
            detail = yaml.safe_load((ROOT / item["fragmento"]).read_text(encoding="utf-8"))
            self.assertNotIn(detail["oponente"]["nome"].lower(), public)
            self.assertNotIn(detail["oponente"]["tradicao"].lower(), public)
        prize = yaml.safe_load((ROOT / index["premio"]["fragmento"]).read_text(encoding="utf-8"))
        self.assertNotIn(prize["integral"]["informacao"].lower(), public)

    def test_final_e_slot_causal_e_task54_continua_autoridade(self):
        index = tour.load_index(ROOT)
        detail = yaml.safe_load((ROOT / index["agenda_relativa"][-1]["fragmento"]).read_text(encoding="utf-8"))
        self.assertEqual(detail["oponente_slot"]["tipo"], "kozakuriano_conhecido")
        self.assertTrue(index["regras"]["task54_permanece_autoridade_de_neutralizacao"])
        rendered = yaml.safe_dump(detail, allow_unicode=True).lower()
        self.assertIn("task 54", rendered)
        self.assertIn("neutralização durável", rendered)

    def test_convite_so_abre_detalhe_depois_de_data_nivel_e_confianca(self):
        early = tour.invitation_candidate(ROOT, now=mundo.parse_instant("17 Eleasis, 1372 DR", "19:00"))
        self.assertEqual(early["motivo"], "janela_temporal_fechada")
        fragment = tour.load_index(ROOT)["convite"]["fragmento"]
        self.assertNotIn(fragment, early["fontes_lidas"])

        now = mundo.parse_instant("22 Eleasis, 1372 DR", "12:00")
        with mock.patch.object(tour.entradas, "level", return_value=7):
            low = tour.invitation_candidate(ROOT, now=now)
        self.assertEqual(low["motivo"], "nivel_insuficiente")
        self.assertNotIn(fragment, low["fontes_lidas"])

        with mock.patch.object(tour.entradas, "level", return_value=9), mock.patch.object(
            tour, "_effective_luath", return_value=({"vinculo": 4, "confianca": 7, "risco_percebido": 8}, ["fixture:luath"])
        ):
            ready = tour.invitation_candidate(ROOT, now=now)
        self.assertTrue(ready["disponivel"])
        self.assertIn(fragment, ready["fontes_lidas"])


class TournamentSceneAdapterTest(unittest.TestCase):
    def test_sem_luath_explicito_nao_consulta_task37(self):
        base = {"npcs_canonicos": ["nera_vell"], "fontes_lidas": ["base.yaml"], "resumo": {}, "regra": "base"}
        with mock.patch.object(tour_scene, "_BASE_OPEN_SCENE", return_value=base), mock.patch.object(
            tour_scene.torneio_clandestino, "invitation_candidate", side_effect=AssertionError("nao deve consultar")
        ):
            result = tour_scene.open_scene(ROOT, scene_id="sem-luath")
        self.assertNotIn("torneio_clandestino", result)

    def test_luath_explicito_pode_projetar_convite_sem_autoaceite(self):
        base = {"npcs_canonicos": ["luath"], "fontes_lidas": ["base.yaml"], "resumo": {}, "regra": "base"}
        candidate = {
            "disponivel": True,
            "torneio": "circuito_subterraneo_parte1",
            "npc": "luath",
            "convite": {"premissa": "p", "pedido": "q", "guardrails": ["g"]},
            "fontes_lidas": [tour.INDEX.as_posix(), tour.STATE.as_posix(), "convite.yaml"],
        }
        with mock.patch.object(tour_scene, "_BASE_OPEN_SCENE", return_value=base), mock.patch.object(
            tour_scene.torneio_clandestino, "invitation_candidate", return_value=candidate
        ):
            result = tour_scene.open_scene(ROOT, scene_id="com-luath")
        self.assertEqual(result["resumo"]["convites_miniarco_para_avaliar"], 1)
        self.assertIn("Ren pode recusar", result["regra"])

    def test_endpoint_compacta_convite_sem_nova_leitura(self):
        endpoint = {"ids": {}, "filtros": [], "disponibilidade": {}, "gates": [], "proximo_passo": {}}
        preview = {
            "torneio_clandestino": {
                "disponivel": True,
                "torneio": "circuito_subterraneo_parte1",
                "npc": "luath",
                "convite": {
                    "premissa": "Uma oportunidade clandestina foi encontrada.",
                    "pedido": "Luath pergunta se Ren quer entrar por vontade propria.",
                    "guardrails": ["Ren pode recusar", "identidade e escolha do jogador"],
                },
            }
        }
        endpoints._project_tournament_invite(endpoint, preview)
        self.assertEqual(endpoint["gates"][0]["resultado"], "convite_disponivel")
        self.assertTrue(endpoint["disponibilidade"]["torneio_clandestino"]["recusa_permitida"])
        self.assertIn("não registre aceite", endpoint["proximo_passo"]["torneio_clandestino"])


class TournamentFixtureTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        shutil.copytree(ROOT / tour.ROOT, self.repo / tour.ROOT)
        source = self.repo / "sessoes/001/resumo.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            "Luath ofereceu a Ren uma entrada voluntaria no circuito clandestino.\n"
            "Ren aceitou entrar no circuito usando a identidade escolhida.\n"
            "Ren recusou entrar no circuito clandestino.\n"
            "Ren retirou-se voluntariamente do circuito clandestino.\n"
            "Ren venceu a primeira noite do circuito.\n"
            "Ren perdeu a primeira noite do circuito.\n"
            "Ren perdeu a segunda noite do circuito.\n"
            "Ren venceu a segunda noite do circuito.\n"
            "Ren venceu a terceira noite do circuito.\n"
            "Ren venceu a semifinal do circuito.\n"
            "Ren venceu a final do circuito.\n"
            "O intermediario entregou a informacao conquistada no circuito.\n",
            encoding="utf-8",
        )
        self.source = "sessoes/001/resumo.md"
        self.accepted_at = mundo.parse_instant("22 Eleasis, 1372 DR", "12:00")

    def tearDown(self):
        self.temp.cleanup()

    def _write_state(self, state):
        (self.repo / tour.STATE).write_text(yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def _invite_state(self):
        state = tour.load_state(self.repo)
        state["estado"] = "convidado"
        state["convite"] = {
            "oferecido_em": mundo.instant_parts(self.accepted_at),
            "fonte": self.source,
            "evidencia": "Luath ofereceu a Ren uma entrada voluntaria no circuito clandestino.",
            "resposta": None,
            "respondido_em": None,
        }
        self._write_state(state)

    def _accept(self, persona="kage"):
        self._invite_state()
        with mock.patch.object(tour.mundo, "load_canonical_time", return_value=(self.accepted_at, {})):
            return tour.respond(
                self.repo, "aceitar", source=self.source,
                evidence="Ren aceitou entrar no circuito usando a identidade escolhida.", persona=persona,
            )

    def _conclude(self, position: int, outcome: str, evidence: str, *, now=None):
        scheduled = tour.load_state(self.repo)["agenda"][position]
        due = mundo.parse_instant(scheduled["em"]["data"], scheduled["em"]["hora"])
        with mock.patch.object(tour.mundo, "load_canonical_time", return_value=(now or due, {})):
            return tour.conclude_round(
                self.repo,
                scheduled["id"],
                outcome,
                source=self.source,
                evidence=evidence,
            )

    def test_recusa_fecha_miniarco_sem_agenda_ou_penalidade_automatica(self):
        self._invite_state()
        with mock.patch.object(tour.mundo, "load_canonical_time", return_value=(self.accepted_at, {})):
            result = tour.respond(
                self.repo, "recusar", source=self.source,
                evidence="Ren recusou entrar no circuito clandestino.",
            )
        self.assertEqual(result["resultado"], "recusado")
        state = tour.load_state(self.repo)
        self.assertEqual(state["estado"], "recusado")
        self.assertEqual(state["agenda"], [])

    def test_aceite_ancora_cinco_noites_e_identidade_escolhida(self):
        self._accept("kage")
        state = tour.load_state(self.repo)
        self.assertEqual(state["inscricao"]["identidade"], "kage")
        self.assertEqual(len(state["agenda"]), 5)
        base_day = self.accepted_at.minute // 1440
        offsets = [
            mundo.parse_instant(item["em"]["data"], item["em"]["hora"]).minute // 1440 - base_day
            for item in state["agenda"]
        ]
        self.assertEqual(offsets, [1, 4, 7, 10, 14])

    def test_fronteira_para_na_primeira_noite_sem_pendencia_mundo(self):
        self._accept()
        state = tour.load_state(self.repo)
        due = mundo.parse_instant(state["agenda"][0]["em"]["data"], state["agenda"][0]["em"]["hora"])
        result = tour.next_boundary(self.repo, self.accepted_at, mundo.WorldInstant(due.minute + 2 * 1440))
        self.assertEqual(result["quando"], due)
        self.assertEqual(result["rodada"], state["agenda"][0]["id"])
        self.assertNotIn("pendencia", result)

    def test_rodada_devida_abre_exatamente_um_fragmento(self):
        self._accept()
        scheduled = tour.load_state(self.repo)["agenda"][0]
        due = mundo.parse_instant(scheduled["em"]["data"], scheduled["em"]["hora"])
        with mock.patch.object(tour.mundo, "load_canonical_time", return_value=(due, {})):
            view = tour.round_view(self.repo)
        self.assertEqual(view["resultado"], "rodada_devida")
        self.assertEqual(len([p for p in view["fontes_lidas"] if "/rodadas/" in p]), 1)

    def test_retry_atrasado_nao_conclui_a_rodada_seguinte(self):
        self._accept()
        second = tour.load_state(self.repo)["agenda"][1]
        late = mundo.WorldInstant(mundo.parse_instant(second["em"]["data"], second["em"]["hora"]).minute + 30)
        first = tour.load_state(self.repo)["agenda"][0]
        with mock.patch.object(tour.mundo, "load_canonical_time", return_value=(late, {})):
            one = tour.conclude_round(
                self.repo, first["id"], "vitoria", source=self.source,
                evidence="Ren venceu a primeira noite do circuito.",
            )
            retry = tour.conclude_round(
                self.repo, first["id"], "vitoria", source=self.source,
                evidence="Ren venceu a primeira noite do circuito.",
            )
        self.assertTrue(one["alterou"])
        self.assertFalse(retry["alterou"])
        state = tour.load_state(self.repo)
        self.assertEqual([item["id"] for item in state["rodadas_concluidas"]], [first["id"]])

    def test_retirada_entre_noites_e_sempre_registravel(self):
        self._accept()
        between = mundo.WorldInstant(self.accepted_at.minute + 6 * 60)
        with mock.patch.object(tour.mundo, "load_canonical_time", return_value=(between, {})):
            result = tour.withdraw(
                self.repo,
                source=self.source,
                evidence="Ren retirou-se voluntariamente do circuito clandestino.",
            )
        self.assertEqual(result["resultado"], "abandonado")
        state = tour.load_state(self.repo)
        self.assertEqual(state["estado"], "abandonado")
        later = mundo.WorldInstant(self.accepted_at.minute + 20 * 1440)
        self.assertIsNone(tour.next_boundary(self.repo, between, later)["quando"])

    def test_duas_derrotas_classificatorias_eliminam_sem_reescrever(self):
        self._accept()
        one = self._conclude(0, "derrota", "Ren perdeu a primeira noite do circuito.")
        self.assertEqual(one["estado_torneio"], "ativo")
        two = self._conclude(1, "derrota", "Ren perdeu a segunda noite do circuito.")
        self.assertEqual(two["estado_torneio"], "eliminado")
        self.assertEqual(tour.load_state(self.repo)["derrotas_classificatorias"], 2)

    def test_semifinal_libera_pista_parcial_e_final_vencida_integral(self):
        self._accept()
        evidences = [
            "Ren venceu a primeira noite do circuito.",
            "Ren venceu a segunda noite do circuito.",
            "Ren venceu a terceira noite do circuito.",
            "Ren venceu a semifinal do circuito.",
        ]
        for index, evidence in enumerate(evidences):
            self._conclude(index, "vitoria", evidence)
        self.assertEqual(tour.load_state(self.repo)["premio"]["estado"], "parcial_disponivel")
        self.assertEqual(tour.prize_view(self.repo)["grau"], "parcial")

        final = tour.load_state(self.repo)["agenda"][4]
        due = mundo.parse_instant(final["em"]["data"], final["em"]["hora"])
        candidate = {"id": "fixture_kozakuriano", "nome": "Fixture", "origem": "Kozakura", "estado_entrada": "presente", "confirmar_entrada_se_aparecer": False}
        with mock.patch.object(tour, "_final_candidate", return_value=(candidate, ["fixture:final"])), mock.patch.object(
            tour.mundo, "load_canonical_time", return_value=(due, {})
        ):
            result = tour.conclude_round(
                self.repo, final["id"], "vitoria", source=self.source,
                evidence="Ren venceu a final do circuito.",
            )
        self.assertEqual(result["estado_torneio"], "encerrado")
        self.assertEqual(result["premio"], "integral_disponivel")
        full = tour.prize_view(self.repo)
        self.assertEqual(full["grau"], "integral")
        self.assertNotIn("conhecimento_de_ren", full["premio"])

    def test_entrega_do_premio_preserva_proveniencia_e_retry(self):
        self._accept()
        state = tour.load_state(self.repo)
        state["estado"] = "encerrado"
        state["premio"]["estado"] = "integral_disponivel"
        self._write_state(state)
        delivered_at = mundo.WorldInstant(self.accepted_at.minute + 15 * 1440)
        evidence = "O intermediario entregou a informacao conquistada no circuito."
        with mock.patch.object(tour.mundo, "load_canonical_time", return_value=(delivered_at, {})):
            first = tour.deliver_prize(self.repo, source=self.source, evidence=evidence)
            retry = tour.deliver_prize(self.repo, source=self.source, evidence=evidence)
        self.assertTrue(first["alterou"])
        self.assertFalse(retry["alterou"])
        self.assertEqual(retry["fonte"], self.source)
        self.assertEqual(retry["evidencia"], evidence)
        persisted = tour.load_state(self.repo)["premio"]
        self.assertEqual(persisted["fonte"], self.source)
        self.assertEqual(persisted["evidencia"], evidence)


class TournamentBudgetTest(unittest.TestCase):
    def test_contrato_congela_zero_scheduler_e_lazy_loading(self):
        budget = yaml.safe_load((ROOT / "baseline/underground-tournament-mini-arc-orcamento.yaml").read_text(encoding="utf-8"))
        limits = budget["limites"]
        self.assertEqual(limits["chamadas_extras_turno_comum"], 0)
        self.assertEqual(limits["leituras_task37_cena_sem_luath"], 0)
        self.assertEqual(limits["rodadas_total"], 5)
        self.assertEqual(limits["duracao_final_dias"], 14)
        self.assertEqual(limits["fragmentos_rodada_abertos_por_consulta"], 1)
        self.assertEqual(limits["schedulers_novos"], 0)
        self.assertEqual(limits["pendencias_mundo_novas"], 0)
        self.assertEqual(limits["rng_progressao_novo"], 0)
        self.assertTrue(all(budget["invariantes"].values()))
        self.assertLessEqual((ROOT / tour.INDEX).stat().st_size, limits["max_index_bytes"])
        self.assertLessEqual((ROOT / tour.STATE).stat().st_size, limits["max_estado_bytes"])
        for item in tour.load_index(ROOT)["agenda_relativa"]:
            self.assertLessEqual((ROOT / item["fragmento"]).stat().st_size, limits["max_fragmento_bytes"])


if __name__ == "__main__":
    unittest.main()
