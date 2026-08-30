from __future__ import annotations

import copy
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

import canon_bridge
import canon_bridge_runtime
import eventos_canonicos
import intencoes_canonicas
import locais
import mundo
import oportunidades
import sidequests_emergentes as emergent
import test_emergent_sidequest_authoring_registry_v2 as task41_cases


def _instant(raw: dict) -> mundo.WorldInstant:
    return mundo.parse_instant(raw["data"], raw["hora"])


def _candidate(package: dict, required_modes: set[str]) -> dict:
    now = _instant(package["prazo_mundo"]["agora"])
    horizon = now.minute + 14 * 24 * 60
    index = intencoes_canonicas.load_index(ROOT)
    catalog = eventos_canonicos.load_catalog(ROOT)
    ordered = sorted(
        catalog["eventos"],
        key=lambda event_id: _instant(catalog["eventos"][event_id]["ativacao"]).minute,
    )
    for event_id in ordered:
        if event_id in index["passado_congelado"]:
            continue
        activation = _instant(catalog["eventos"][event_id]["ativacao"])
        if not now.minute < activation.minute <= horizon:
            continue
        intent = intencoes_canonicas.load_intent(
            ROOT, event_id, index=index, catalog=catalog
        )
        contract = intent["contrato_rewrite"]
        if not contract["integracao_sidequest"]:
            continue
        if not required_modes <= set(contract["modos_permitidos"]):
            continue
        return {
            "evento_id": event_id,
            "ativacao": copy.deepcopy(catalog["eventos"][event_id]["ativacao"]),
            "intencao": copy.deepcopy(intent["intencao_canonica"]),
            "elasticidade": {
                "modos": list(contract["modos_permitidos"]),
                "atraso_maximo_horas": contract["atraso_maximo_horas"],
                "satisfacao_antecipada": contract["satisfacao_antecipada"],
                "reancoragem_local": contract["reancoragem_local"],
                "troca_de_atores": contract["troca_de_atores"],
            },
        }
    raise AssertionError(
        f"nenhuma intenção futura no horizonte Task40 aceita modos {sorted(required_modes)}"
    )


def _package_for(candidate: dict) -> dict:
    package = copy.deepcopy(task41_cases.task40_package())
    package["horizonte_intencoes_canonicas"]["compativeis"] = [copy.deepcopy(candidate)]
    package["horizonte_intencoes_canonicas"]["quantidade"] = 1
    return package


def _spec_for(
    package: dict,
    candidate: dict,
    mode: str,
    *,
    deadline: dict | None = None,
    suffix: str = "",
) -> dict:
    spec = task41_cases.quest_spec(package)
    spec["titulo"] = spec["titulo"] + suffix
    if deadline is not None:
        spec["prazo"] = {"tipo": "temporal", "expira_em": copy.deepcopy(deadline)}
    if mode == "lateral":
        spec["relacao_canone"] = {
            "modo": "lateral",
            "intencoes_candidatas": [],
            "justificativa": "A quest permanece lateral e não reserva a espinha canônica.",
        }
    else:
        spec["relacao_canone"] = {
            "modo": mode,
            "intencoes_candidatas": [candidate["evento_id"]],
            "justificativa": (
                "O fim do mini-arco oferece uma ponte causal legítima para a intenção "
                "sem decidir que Ren seguirá essa rota."
            ),
        }
    return spec


class Task42Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        for rel in (
            oportunidades.INDEX,
            oportunidades.STATE,
            emergent.NPC_INDEX,
            mundo.TIME_PATH,
            mundo.AGENDA_PATH,
            mundo.WORLD_STATE_PATH,
        ):
            target = self.repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, target)
        shutil.copytree(ROOT / locais.INDEX.parent, self.repo / locais.INDEX.parent)
        shutil.copytree(
            ROOT / "narrador/arcos/parte_1",
            self.repo / "narrador/arcos/parte_1",
        )
        # Cada teste começa sem overlay, independentemente do futuro estado vivo do repo.
        bridge = {
            "schema_canon_bridge": 1,
            "natureza": "controle_reservado",
            "reservas": {},
            "resolucoes": {},
            "historico_recente": [],
        }
        (self.repo / canon_bridge.STATE).write_text(
            yaml.safe_dump(bridge, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def materialize(self, package: dict, spec: dict, *, scene_suffix: str) -> dict:
        prep = emergent.prepare(self.repo, package=package, quest=spec)
        return emergent.materialize(
            self.repo,
            package=package,
            quest=spec,
            preparation_id=prep["preparacao_id"],
            offer_was_narrated=True,
            offer_scene_id=f"task42:{scene_suffix}",
            offer_summary=(
                "A oferta foi feita de forma explícita dentro da cena, com pedido concreto "
                "e liberdade real para recusa antes da materialização da missão."
            ),
        )

    def canon_bytes(self, event_id: str) -> tuple[bytes, bytes, bytes]:
        catalog = eventos_canonicos.load_catalog(self.repo)
        event_fragment = Path(catalog["eventos"][event_id]["fragmento"])
        intent_fragment = intencoes_canonicas.INTENTS_DIR / f"{event_id}.yaml"
        return (
            (self.repo / eventos_canonicos.CATALOG).read_bytes(),
            (self.repo / event_fragment).read_bytes(),
            (self.repo / intent_fragment).read_bytes(),
        )


class Task42LifecycleTest(Task42Fixture):
    @classmethod
    def setUpClass(cls):
        base = task41_cases.task40_package()
        cls.bridge_candidate = _candidate(base, set())
        cls.satisfy_candidate = _candidate(base, {"satisfazer"})
        cls.delay_candidate = _candidate(base, {"adiar"})

    def test_recusar_quest_nao_toca_canone_nem_cria_reserva(self):
        candidate = self.bridge_candidate
        package = _package_for(candidate)
        spec = _spec_for(
            package,
            candidate,
            "candidata_ponte",
            deadline=candidate["ativacao"],
        )
        mission = self.materialize(package, spec, scene_suffix="recusa")
        bridge_before = (self.repo / canon_bridge.STATE).read_bytes()
        canon_before = self.canon_bytes(candidate["evento_id"])
        now = _instant(package["prazo_mundo"]["agora"])

        result = canon_bridge_runtime.respond(
            self.repo, mission["mission_id"], "recusar", now=now
        )

        self.assertEqual(result["resultado"], "recusada")
        self.assertEqual((self.repo / canon_bridge.STATE).read_bytes(), bridge_before)
        self.assertEqual(self.canon_bytes(candidate["evento_id"]), canon_before)

    def test_aceitar_lateral_preserva_canone_sem_reserva(self):
        candidate = self.bridge_candidate
        package = _package_for(candidate)
        spec = _spec_for(package, candidate, "lateral")
        mission = self.materialize(package, spec, scene_suffix="lateral")
        bridge_before = (self.repo / canon_bridge.STATE).read_bytes()
        now = _instant(package["prazo_mundo"]["agora"])

        result = canon_bridge_runtime.respond(
            self.repo, mission["mission_id"], "aceitar", now=now
        )

        self.assertEqual(result["resultado"], "aceita")
        self.assertFalse(result["canon_bridge"]["alterou"])
        self.assertEqual((self.repo / canon_bridge.STATE).read_bytes(), bridge_before)

    def test_aceitar_ponte_cria_so_reserva_e_nao_move_ren(self):
        candidate = self.bridge_candidate
        package = _package_for(candidate)
        spec = _spec_for(
            package,
            candidate,
            "candidata_ponte",
            deadline=candidate["ativacao"],
        )
        mission = self.materialize(package, spec, scene_suffix="ponte")
        world_before = (self.repo / mundo.WORLD_STATE_PATH).read_bytes()
        canon_before = self.canon_bytes(candidate["evento_id"])
        now = _instant(package["prazo_mundo"]["agora"])

        result = canon_bridge_runtime.respond(
            self.repo, mission["mission_id"], "aceitar", now=now
        )
        state = canon_bridge.load_state(self.repo)
        reservation = state["reservas"][candidate["evento_id"]]

        self.assertEqual(result["resultado"], "aceita")
        self.assertEqual(reservation["modo"], "ponte")
        self.assertEqual(
            reservation["regra_agencia"], "ancora_causal_nao_move_nem_decide_ren"
        )
        self.assertEqual(
            reservation["ativacao_efetiva"], reservation["ativacao_padrao"]
        )
        self.assertTrue(reservation["ancora_quest"]["locais_fase_final"])
        self.assertEqual((self.repo / mundo.WORLD_STATE_PATH).read_bytes(), world_before)
        self.assertEqual(self.canon_bytes(candidate["evento_id"]), canon_before)

    def test_duas_quests_nao_reservam_a_mesma_intencao(self):
        candidate = self.bridge_candidate
        package = _package_for(candidate)
        first_spec = _spec_for(
            package,
            candidate,
            "candidata_ponte",
            deadline=candidate["ativacao"],
            suffix=" — Primeira",
        )
        second_spec = _spec_for(
            package,
            candidate,
            "candidata_ponte",
            deadline=candidate["ativacao"],
            suffix=" — Segunda",
        )
        first = self.materialize(package, first_spec, scene_suffix="conflito-1")
        second = self.materialize(package, second_spec, scene_suffix="conflito-2")
        now = _instant(package["prazo_mundo"]["agora"])
        canon_bridge_runtime.respond(self.repo, first["mission_id"], "aceitar", now=now)

        with self.assertRaisesRegex(
            canon_bridge_runtime.CanonBridgeRuntimeError,
            "já reservada",
        ):
            canon_bridge_runtime.respond(
                self.repo, second["mission_id"], "aceitar", now=now
            )

        opp = oportunidades.load_state(
            self.repo, oportunidades.load_index(self.repo)
        )
        self.assertEqual(opp["missoes"][second["mission_id"]]["estado"], "oferecida")
        bridge = canon_bridge.load_state(self.repo)
        self.assertEqual(
            bridge["reservas"][candidate["evento_id"]]["mission_id"],
            first["mission_id"],
        )

    def test_adiamento_perdido_libera_fallback_canonico(self):
        candidate = self.delay_candidate
        package = _package_for(candidate)
        base = _instant(candidate["ativacao"])
        max_delay = int(candidate["elasticidade"]["atraso_maximo_horas"])
        delay_hours = min(12, max_delay)
        self.assertGreater(delay_hours, 0)
        effective = mundo.WorldInstant(base.minute + delay_hours * 60)
        spec = _spec_for(
            package,
            candidate,
            "candidata_adiamento",
            deadline=mundo.instant_parts(effective),
        )
        mission = self.materialize(package, spec, scene_suffix="adiamento")
        now = _instant(package["prazo_mundo"]["agora"])
        canon_before = self.canon_bytes(candidate["evento_id"])
        agenda_before = (self.repo / mundo.AGENDA_PATH).read_bytes()
        canon_bridge_runtime.respond(
            self.repo, mission["mission_id"], "aceitar", now=now
        )

        catalog = eventos_canonicos.load_catalog(self.repo)
        schedule_id = catalog["eventos"][candidate["evento_id"]]["agendamento_id"]
        origin = f"agenda:agendamentos.{schedule_id}"
        agenda = mundo.load_agenda(self.repo)
        trigger = next(
            item
            for item in mundo._scheduled_triggers(
                agenda, mundo.WorldInstant(base.minute - 1), base
            )
            if item.get("origem") == origin
        )
        world = mundo.load_world_state(self.repo)
        world["processado_ate"] = mundo.instant_parts(mundo.WorldInstant(base.minute + 1))
        world["pendencias"] = [trigger]
        world["concluidas_recentes"] = []
        mundo._atomic_write_yaml(self.repo / mundo.WORLD_STATE_PATH, world)

        held = canon_bridge_runtime.reconcile_world(
            self.repo, now=mundo.WorldInstant(base.minute + 1)
        )
        self.assertTrue(held["alterou"])
        self.assertFalse(
            any(
                item.get("origem") == origin
                for item in mundo.load_world_state(self.repo)["pendencias"]
            )
        )

        reconciled = canon_bridge_runtime.reconcile(self.repo, now=effective)
        self.assertTrue(reconciled["lifecycle"]["alterou"])
        bridge = canon_bridge.load_state(self.repo)
        self.assertNotIn(candidate["evento_id"], bridge["reservas"])
        opp = oportunidades.load_state(
            self.repo, oportunidades.load_index(self.repo)
        )
        self.assertEqual(opp["missoes"][mission["mission_id"]]["estado"], "falhada")
        fallback = [
            item
            for item in mundo.load_world_state(self.repo)["pendencias"]
            if item.get("origem") == origin
        ]
        self.assertEqual(len(fallback), 1)
        self.assertEqual(fallback[0]["disparado_em"], candidate["ativacao"])
        self.assertEqual((self.repo / mundo.AGENDA_PATH).read_bytes(), agenda_before)
        self.assertEqual(self.canon_bytes(candidate["evento_id"]), canon_before)


class Task42SatisfactionTest(Task42Fixture):
    @classmethod
    def setUpClass(cls):
        base = task41_cases.task40_package()
        cls.candidate = _candidate(base, {"satisfazer"})

    def _convergent(self) -> tuple[dict, dict, dict]:
        candidate = self.candidate
        package = _package_for(candidate)
        spec = _spec_for(
            package,
            candidate,
            "candidata_convergente",
            deadline=candidate["ativacao"],
        )
        mission = self.materialize(package, spec, scene_suffix="convergente")
        now = _instant(package["prazo_mundo"]["agora"])
        canon_bridge_runtime.respond(
            self.repo, mission["mission_id"], "aceitar", now=now
        )
        canon_bridge_runtime.finish(
            self.repo,
            mission["mission_id"],
            "concluida",
            reason="As condições objetivas da sidequest foram alcançadas em jogo.",
            now=mundo.WorldInstant(now.minute + 60),
        )
        return candidate, package, mission

    def test_convergente_so_satisfaz_com_evidencia_para_todos_os_criterios(self):
        candidate, package, mission = self._convergent()
        event_id = candidate["evento_id"]
        canon_before = self.canon_bytes(event_id)
        bridge = canon_bridge.load_state(self.repo)
        self.assertEqual(bridge["reservas"][event_id]["estado"], "aguarda_evidencia")

        with self.assertRaisesRegex(canon_bridge.CanonBridgeError, "uma evidência"):
            canon_bridge.satisfy(
                self.repo,
                mission["mission_id"],
                [],
                note="Tentativa incompleta não pode apagar a realização padrão.",
            )
        self.assertIsNone(canon_bridge.event_overlay(self.repo, event_id).get("realizacao_padrao"))

        intent = intencoes_canonicas.load_intent(self.repo, event_id)
        criteria = intent["intencao_canonica"]["criterios_satisfacao"]
        evidence_rel = Path("sessoes/task42-prova-canonica.txt")
        evidence_path = self.repo / evidence_rel
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        literals = [
            f"PROVA TASK42 {pos}: fato canônico materializado para este critério."
            for pos in range(len(criteria))
        ]
        evidence_path.write_text("\n".join(literals) + "\n", encoding="utf-8")
        evidence = [
            {"criterio": criterion, "fonte": evidence_rel.as_posix(), "evidencia": literal}
            for criterion, literal in zip(criteria, literals)
        ]

        result = canon_bridge.satisfy(
            self.repo,
            mission["mission_id"],
            evidence,
            note="Todos os critérios da intenção foram demonstrados por fatos canônicos independentes do plano.",
        )
        self.assertEqual(result["resultado"], "intencao_satisfeita")
        overlay = canon_bridge.event_overlay(self.repo, event_id)
        self.assertEqual(overlay["estado"], "satisfeita")
        self.assertEqual(
            overlay["realizacao_padrao"], "suprimida_por_intencao_satisfeita"
        )
        self.assertNotIn(event_id, canon_bridge.load_state(self.repo)["reservas"])
        self.assertEqual(self.canon_bytes(event_id), canon_before)

    def test_planejamento_reservado_nao_pode_provar_satisfacao(self):
        candidate, _, mission = self._convergent()
        event_id = candidate["evento_id"]
        intent = intencoes_canonicas.load_intent(self.repo, event_id)
        criteria = intent["intencao_canonica"]["criterios_satisfacao"]
        quest_doc = emergent.show(self.repo, mission["quest_id"])["quest"]
        source = oportunidades.load_state(
            self.repo, oportunidades.load_index(self.repo)
        )["missoes"][mission["mission_id"]]["arquivo"]
        evidence = [
            {
                "criterio": criterion,
                "fonte": source,
                "evidencia": quest_doc["titulo"],
            }
            for criterion in criteria
        ]
        with self.assertRaisesRegex(canon_bridge.CanonBridgeError, "planejamento reservado"):
            canon_bridge.satisfy(
                self.repo,
                mission["mission_id"],
                evidence,
                note="Planejamento não pode provar a si mesmo.",
            )

    def test_integridade_recusa_realizacao_suprimida_sem_intencao_satisfeita(self):
        candidate = self.candidate
        state = canon_bridge.load_state(self.repo)
        state["resolucoes"][candidate["evento_id"]] = {
            "estado": "transformada",
            "realizacao_padrao": "suprimida_somente_por_intencao_satisfeita",
        }
        canon_bridge._atomic(self.repo / canon_bridge.STATE, state)
        result = canon_bridge.check(self.repo)
        self.assertFalse(result["ok"])
        self.assertTrue(
            any("só pode ser suprimida" in error for error in result["erros"]),
            result["erros"],
        )

    def test_passado_congelado_nunca_pode_receber_reserva(self):
        package = _package_for(self.candidate)
        spec = _spec_for(package, self.candidate, "lateral")
        mission = self.materialize(package, spec, scene_suffix="passado")
        state = oportunidades.load_state(
            self.repo, oportunidades.load_index(self.repo)
        )
        record = state["missoes"][mission["mission_id"]]
        doc_path = self.repo / record["arquivo"]
        doc = yaml.safe_load(doc_path.read_text(encoding="utf-8"))
        frozen = next(iter(intencoes_canonicas.load_index(self.repo)["passado_congelado"]))
        doc["relacao_canone"] = {
            "modo": "candidata_ponte",
            "intencoes_candidatas": [frozen],
            "justificativa": "Fixture deliberadamente inválida para provar a barreira do passado.",
            "autoridade": "candidatura_somente_task42_pode_reescrever",
        }
        doc_path.write_text(
            yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        now = _instant(package["prazo_mundo"]["agora"])
        with self.assertRaisesRegex(canon_bridge.CanonBridgeError, "passado materializado"):
            canon_bridge.prepare_lifecycle_transition(
                self.repo, record, "aceita", now
            )


class Task42BudgetTest(unittest.TestCase):
    def test_contrato_congela_custos_e_invariantes(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/canon-bridge-rewriter-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        limits = contract["limites"]
        self.assertEqual(limits["ledger_bytes_max"], canon_bridge.MAX_STATE_BYTES)
        self.assertEqual(
            limits["gap_ponte_convergencia_horas_max"],
            canon_bridge.MAX_CONVERGENCE_GAP_HOURS,
        )
        self.assertEqual(limits["reservas_ativas_max"], 2)
        for key in (
            "schedulers_novos", "rng_novo", "scans_globais",
            "edicoes_task36", "edicoes_task39",
        ):
            self.assertEqual(limits[key], 0)
        self.assertTrue(all(contract["invariantes"].values()))

    def test_engine_nao_cria_scheduler_rng_scan_ou_edita_task36_task39(self):
        core = (ROOT / "ferramentas/canon_bridge.py").read_text(encoding="utf-8")
        runtime = (ROOT / "ferramentas/canon_bridge_runtime.py").read_text(encoding="utf-8")
        joined = core + "\n" + runtime
        for forbidden in (
            "import random", "threading", "asyncio", "subprocess", "os.walk", ".rglob(", ".glob(",
        ):
            self.assertNotIn(forbidden, joined)
        self.assertNotIn("eventos_canonicos.atomic", joined)
        self.assertNotIn("intencoes_canonicas.atomic", joined)

    def test_estado_real_comeca_vazio_e_valido(self):
        result = canon_bridge.check(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["reservas"], 0)
        self.assertEqual(result["resolucoes"], 0)


if __name__ == "__main__":
    unittest.main()
