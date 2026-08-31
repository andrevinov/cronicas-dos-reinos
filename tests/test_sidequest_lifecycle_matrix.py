from __future__ import annotations

import copy
import shutil
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import canon_bridge
import canon_bridge_runtime
import intencoes_canonicas
import mundo
import oportunidades
import progressao_sidequests as progression
import sidequests_integracao_runtime as integration
import test_adversarial_integrity as adversarial_cases
import test_canon_bridge_rewriter as bridge_cases
import test_emergent_sidequest_authoring_registry_v2 as authoring_cases
import test_quest_rewards_discoveries_losses as reward_cases
import test_sidequest_progression_deadlines_consequences as progression_cases


class SidequestLifecycleFixture(progression_cases.Task45Fixture):
    def setUp(self):
        super().setUp()
        agenda = self.repo / mundo.AGENDA_PATH
        agenda.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / mundo.AGENDA_PATH, agenda)
        shutil.copytree(
            ROOT / "narrador/arcos/parte_1",
            self.repo / "narrador/arcos/parte_1",
            dirs_exist_ok=True,
        )
        bridge = {
            "schema_canon_bridge": 1,
            "natureza": "controle_reservado",
            "reservas": {},
            "resolucoes": {},
            "historico_recente": [],
        }
        path = self.repo / canon_bridge.STATE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(bridge, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def install_spec(self, package: dict, spec: dict, suffix: str) -> str:
        block = {
            "oferta": {
                "materializar": True,
                "evidencia": "Oferta fixture de integração",
                "resumo": "A oferta causal foi narrada explicitamente e a resposta permaneceu sob controle de Ren.",
            },
            "quest": copy.deepcopy(spec),
            "contrato_recompensa": copy.deepcopy(reward_cases.base_contract()),
            "contrato_adversarial": copy.deepcopy(adversarial_cases.adversarial_contract(spec)),
            "contrato_progressao": copy.deepcopy(progression_cases.progression_contract()),
        }
        plan = integration.prepare_installation(
            self.repo,
            package=package,
            block=block,
            offer_scene_id=f"sidequest:matrix:{suffix}",
            offer_summary=block["oferta"]["resumo"],
        )
        journal = integration.begin_conclusion(
            self.repo,
            ticket_id=f"ticket-sidequest-{suffix}",
            transaction={
                "narracao": "Oferta fixture de integração",
                "resumo": f"Materialização de sidequest {suffix}",
            },
            plan=plan,
        )
        result = integration.install(self.repo, journal)
        self.assertEqual(result["instalacoes_logicas"], 1)
        return plan["mission_id"]

    def now_for(self, package: dict) -> mundo.WorldInstant:
        raw = package["prazo_mundo"]["agora"]
        return mundo.parse_instant(raw["data"], raw["hora"])


class SidequestLifecycleMatrixTest(SidequestLifecycleFixture):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        base = cls.package
        cls.bridge_candidate = bridge_cases._candidate(base, set())
        cls.satisfy_candidate = bridge_cases._candidate(base, {"satisfazer"})
        cls.delay_candidate = bridge_cases._candidate(base, {"adiar"})

    def test_cenario_quest_lateral_aceita_nao_toca_canon_bridge(self):
        package = copy.deepcopy(self.package)
        spec = authoring_cases.quest_spec(package)
        mid = self.install_spec(package, spec, "lateral")
        before = (self.repo / canon_bridge.STATE).read_bytes()
        result = canon_bridge_runtime.respond(
            self.repo, mid, "aceitar", now=self.now_for(package)
        )
        self.assertEqual(result["resultado"], "aceita")
        self.assertFalse(result["canon_bridge"]["alterou"])
        self.assertEqual((self.repo / canon_bridge.STATE).read_bytes(), before)

    def test_cenario_duas_ativas_continua_bloqueando_terceira(self):
        package = copy.deepcopy(self.package)
        for pos in (1, 2):
            spec = authoring_cases.quest_spec(package)
            spec["titulo"] += f" — Ativa {pos}"
            mid = self.install_spec(package, spec, f"ativa-{pos}")
            oportunidades.respond(self.repo, mid, "aceitar", now=self.now_for(package))
        third = authoring_cases.quest_spec(package)
        third["titulo"] += " — Terceira"
        block = {
            "oferta": {"materializar": True, "evidencia": "Oferta", "resumo": "Terceira oferta causal que não pode furar o orçamento de duas sidequests aceitas."},
            "quest": third,
            "contrato_recompensa": reward_cases.base_contract(),
            "contrato_adversarial": adversarial_cases.adversarial_contract(third),
            "contrato_progressao": progression_cases.progression_contract(),
        }
        with self.assertRaisesRegex(
            integration.EmergentSidequestIntegrationError,
            "limite_ativas|ativas",
        ):
            integration.prepare_installation(
                self.repo,
                package=package,
                block=block,
                offer_scene_id="sidequest:matrix:third",
                offer_summary=block["oferta"]["resumo"],
            )

    def test_cenario_ponte_reserva_canone_sem_mover_ren(self):
        candidate = self.bridge_candidate
        package = bridge_cases._package_for(candidate)
        spec = bridge_cases._spec_for(
            package,
            candidate,
            "candidata_ponte",
            deadline=candidate["ativacao"],
        )
        mid = self.install_spec(package, spec, "ponte")
        result = canon_bridge_runtime.respond(
            self.repo, mid, "aceitar", now=self.now_for(package)
        )
        self.assertEqual(result["resultado"], "aceita")
        reservation = canon_bridge.load_state(self.repo)["reservas"][candidate["evento_id"]]
        self.assertEqual(reservation["modo"], "ponte")
        self.assertEqual(
            reservation["regra_agencia"], "ancora_causal_nao_move_nem_decide_ren"
        )

    def test_cenario_recusada_nao_cria_reserva(self):
        candidate = self.bridge_candidate
        package = bridge_cases._package_for(candidate)
        spec = bridge_cases._spec_for(
            package,
            candidate,
            "candidata_ponte",
            deadline=candidate["ativacao"],
        )
        mid = self.install_spec(package, spec, "recusada")
        before = (self.repo / canon_bridge.STATE).read_bytes()
        result = canon_bridge_runtime.respond(
            self.repo, mid, "recusar", now=self.now_for(package)
        )
        self.assertEqual(result["resultado"], "recusada")
        self.assertEqual((self.repo / canon_bridge.STATE).read_bytes(), before)

    def test_cenario_expirada_sem_aceite_permanece_sem_consequencia_adversarial(self):
        package = copy.deepcopy(self.package)
        spec = authoring_cases.quest_spec(package)
        mid = self.install_spec(package, spec, "expirada")
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        deadline = state["missoes"][mid]["janela"]["expira_em"]
        late = mundo.WorldInstant(
            mundo.parse_instant(deadline["data"], deadline["hora"]).minute + 1
        )
        progression.reconcile(self.repo, now=late)
        after = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        self.assertEqual(after["missoes"][mid]["estado"], "expirada")
        self.assertEqual(
            [
                item
                for item in mundo.load_world_state(self.repo)["pendencias"]
                if item.get("tipo") == "resolver_sidequest"
            ],
            [],
        )

    def test_cenario_concluida_pode_satisfazer_intencao_so_com_evidencia(self):
        candidate = self.satisfy_candidate
        package = bridge_cases._package_for(candidate)
        spec = bridge_cases._spec_for(
            package,
            candidate,
            "candidata_convergente",
            deadline=candidate["ativacao"],
        )
        mid = self.install_spec(package, spec, "convergente")
        now = self.now_for(package)
        canon_bridge_runtime.respond(self.repo, mid, "aceitar", now=now)
        progression.record_fact(
            self.repo,
            mid,
            fact_raw={
                "id": "sidequest_sucesso_canonico",
                "descricao": "As condições objetivas da sidequest foram cumpridas por fatos canônicos.",
                "prova": self.proof45(progression_cases.FACT_TEXT),
                "fases": {"entender_rota": "resolvida", "entrega_em_movimento": "resolvida"},
                "condicoes_sucesso": {"sucesso_01": "satisfeita", "sucesso_02": "satisfeita"},
                "condicoes_falha": {},
            },
        )
        progression.finalize_success(
            self.repo,
            mid,
            optional_ids=[],
            evidences={},
            narration=(
                "Silva reconhece que os fatos objetivos da missão foram cumpridos e entrega a recompensa principal prevista no contrato."
            ),
        )
        event_id = candidate["evento_id"]
        self.assertEqual(
            canon_bridge.load_state(self.repo)["reservas"][event_id]["estado"],
            "aguarda_evidencia",
        )
        intent = intencoes_canonicas.load_intent(self.repo, event_id)
        criteria = intent["intencao_canonica"]["criterios_satisfacao"]
        evidence_rel = Path("sessoes/015/prova-intencao-sidequest.txt")
        literals = [
            f"PROVA SIDEQUEST {pos}: fato canônico materializado independente do planejamento."
            for pos in range(len(criteria))
        ]
        path = self.repo / evidence_rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(literals) + "\n", encoding="utf-8")
        result = canon_bridge.satisfy(
            self.repo,
            mid,
            [
                {"criterio": criterion, "fonte": evidence_rel.as_posix(), "evidencia": literal}
                for criterion, literal in zip(criteria, literals)
            ],
            note="Todos os critérios da intenção foram provados por fatos canônicos independentes da sidequest reservada.",
        )
        self.assertEqual(result["resultado"], "intencao_satisfeita")
        overlay = canon_bridge.event_overlay(self.repo, event_id)
        self.assertEqual(overlay["estado"], "satisfeita")
        self.assertEqual(
            overlay["realizacao_padrao"], "suprimida_por_intencao_satisfeita"
        )

    def test_cenario_falha_libera_forma_sem_apagar_intencao(self):
        candidate = self.delay_candidate
        package = bridge_cases._package_for(candidate)
        base = mundo.parse_instant(candidate["ativacao"]["data"], candidate["ativacao"]["hora"])
        delay = min(12, int(candidate["elasticidade"]["atraso_maximo_horas"]))
        self.assertGreater(delay, 0)
        effective = mundo.WorldInstant(base.minute + delay * 60)
        spec = bridge_cases._spec_for(
            package,
            candidate,
            "candidata_adiamento",
            deadline=mundo.instant_parts(effective),
        )
        mid = self.install_spec(package, spec, "falha-rewrite")
        canon_bridge_runtime.respond(self.repo, mid, "aceitar", now=self.now_for(package))
        progression.reconcile(self.repo, now=effective)
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        self.assertEqual(state["missoes"][mid]["estado"], "falhada")
        self.assertNotIn(candidate["evento_id"], canon_bridge.load_state(self.repo)["reservas"])
        overlay = canon_bridge.event_overlay(self.repo, candidate["evento_id"])
        if overlay is not None:
            self.assertNotEqual(overlay.get("estado"), "satisfeita")
            self.assertNotEqual(
                overlay.get("realizacao_padrao"), "suprimida_por_intencao_satisfeita"
            )
        intent = intencoes_canonicas.load_intent(self.repo, candidate["evento_id"])
        self.assertTrue(intent["intencao_canonica"]["criterios_satisfacao"])


if __name__ == "__main__":
    unittest.main()
