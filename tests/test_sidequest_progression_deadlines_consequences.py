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

import barreira_mundo
import integridade_adversarial as adversarial
import mundo
import oportunidades
import progressao_sidequests as progression
import recompensas_sidequest as rewards
import rede_protegida
import test_adversarial_integrity as task44
import test_emergent_sidequest_authoring_registry_v2 as task41
import test_quest_rewards_discoveries_losses as task43
import transacoes


FACT_TEXT = (
    "A rota e a janela de risco foram confirmadas por testemunhos convergentes, e a entrega alcançou um destino seguro fora do controle da oposição."
)
FAIL_TEXT = (
    "A oposição obteve a entrega de forma durável antes do fim da janela e o mensageiro permaneceu alcançável pela célula responsável pela interceptação."
)
CORE_TEXT = (
    "Silva se tornou o elo crítico ainda alcançável e sua permanência inviabiliza a operação da rede."
)


def progression_contract() -> dict:
    return {
        "regra_sucesso": "todas",
        "regra_falha": "qualquer",
        "dependencias_fases": [
            {
                "fase_id": "entender_rota",
                "atores_necessarios": ["silva_elkwood"],
                "substituicao_permitida": False,
            },
            {
                "fase_id": "entrega_em_movimento",
                "atores_necessarios": ["mensageiro_cinza_task41"],
                "substituicao_permitida": False,
            },
        ],
        "efeitos_escaladas": [
            {
                "escalada_id": "interceptar_mensageiro",
                "efeitos_npc": [
                    {"npc_id": "mensageiro_cinza_task41", "estado": "preso"}
                ],
            },
            {
                "escalada_id": "silenciar_elo_critico",
                "efeitos_npc": [
                    {"npc_id": "silva_elkwood", "estado": "desaparecido"}
                ],
            },
        ],
    }


class Task45Fixture(task43.Task43Fixture):
    def setUp(self):
        super().setUp()
        shutil.copytree(ROOT / "estado/npcs", self.repo / "estado/npcs", dirs_exist_ok=True)
        shutil.copytree(ROOT / "narrador/agentes", self.repo / "narrador/agentes")
        for rel in (adversarial.POLICY, rede_protegida.INDEX):
            dst = self.repo / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, dst)
        now = self.now()
        self._yaml(
            mundo.TIME_PATH,
            {
                "schema_tempo": 1,
                "natureza": "tempo_atual",
                "data_atual": mundo.instant_parts(now)["data"],
                "hora_aproximada": mundo.instant_parts(now)["hora"],
            },
        )
        self._yaml(
            mundo.WORLD_STATE_PATH,
            {
                "schema_estado_mundo": 1,
                "natureza": "controle_reservado",
                "processado_ate": mundo.instant_parts(now),
                "pendencias": [],
                "concluidas_recentes": [],
            },
        )
        barreira_mundo.sync(self.repo)
        evidence = self.repo / "sessoes/015/evidencia-task45.md"
        evidence.write_text("\n".join([FACT_TEXT, FAIL_TEXT, CORE_TEXT]) + "\n", encoding="utf-8")

    def _yaml(self, rel: Path | str, value):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def proof45(self, text: str) -> dict:
        return {"fonte": "sessoes/015/evidencia-task45.md", "evidencia": text}

    def setup_quest(self) -> tuple[str, dict]:
        spec = copy.deepcopy(task41.quest_spec(self.package))
        mid = self.materialize(spec)
        self.register(mid, task43.base_contract())
        contract = task44.adversarial_contract(spec)
        prep = adversarial.prepare(self.repo, package=self.package, quest=spec, contract=contract)
        adversarial.materialize(
            self.repo,
            package=self.package,
            quest=spec,
            contract=contract,
            preparation_id=prep["preparacao_id"],
        )
        progression.register_contract(
            self.repo, mid, contract_raw=progression_contract()
        )
        return mid, spec

    def deadline(self, mid: str) -> mundo.WorldInstant:
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        raw = state["missoes"][mid]["janela"]["expira_em"]
        return mundo.parse_instant(raw["data"], raw["hora"])

    def accept45(self, mid: str) -> None:
        oportunidades.respond(self.repo, mid, "aceitar", now=self.now())

    def add_messenger_canonical(self, state: str = "vivo") -> None:
        index_path = self.repo / "estado/npcs/index.yaml"
        index = yaml.safe_load(index_path.read_text(encoding="utf-8"))
        rel = "estado/npcs/mensageiro_cinza_task41.yaml"
        index["npcs"]["mensageiro_cinza_task41"] = {
            "nome": "Mensageiro Cinza",
            "arquivo": rel,
        }
        index["quantidade"] = len(index["npcs"])
        self._yaml("estado/npcs/index.yaml", index)
        self._yaml(
            rel,
            {
                "schema_npc": 2,
                "natureza": "medidores_npc_atuais",
                "id": "mensageiro_cinza_task41",
                "npc": {"nome": "Mensageiro Cinza", "vida": {"estado": state}},
            },
        )


class Task45DeadlineTest(Task45Fixture):
    def test_aceita_com_prazo_ultrapassado_falha_e_emite_uma_pendencia(self):
        mid, _ = self.setup_quest()
        self.accept45(mid)
        late = mundo.WorldInstant(self.deadline(mid).minute + 1)
        first = progression.reconcile(self.repo, now=late)
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        self.assertEqual(state["missoes"][mid]["estado"], "falhada")
        world = mundo.load_world_state(self.repo)
        pending = [item for item in world["pendencias"] if item.get("tipo") == "resolver_sidequest"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["gatilho"], "inacao")
        second = progression.reconcile(self.repo, now=late)
        world2 = mundo.load_world_state(self.repo)
        self.assertEqual(len([item for item in world2["pendencias"] if item.get("tipo") == "resolver_sidequest"]), 1)
        self.assertTrue(first["alterou"])
        self.assertFalse(any(item.get("emitida") for item in [x.get("pendencia") or {} for x in second["resultados"]]))

    def test_oferecida_ou_adiada_expira_sem_consequencia_adversarial(self):
        mid, _ = self.setup_quest()
        late = mundo.WorldInstant(self.deadline(mid).minute + 1)
        progression.reconcile(self.repo, now=late)
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        self.assertEqual(state["missoes"][mid]["estado"], "expirada")
        self.assertEqual(mundo.load_world_state(self.repo)["pendencias"], [])


class Task45FactAndActorTest(Task45Fixture):
    def test_ator_incapacitado_torna_fase_incompativel_impossivel(self):
        mid, _ = self.setup_quest()
        silva_path = self.repo / "estado/npcs/silva_elkwood.yaml"
        silva = yaml.safe_load(silva_path.read_text(encoding="utf-8"))
        silva.setdefault("npc", {}).setdefault("vida", {})["estado"] = "incapacitado"
        silva_path.write_text(yaml.safe_dump(silva, allow_unicode=True, sort_keys=False), encoding="utf-8")
        view = progression.status(self.repo, mid)
        self.assertEqual(view["atores"]["silva_elkwood"]["estado"], "indisponivel")
        self.assertEqual(view["fases"]["entender_rota"]["estado"], "impossivel")
        self.assertEqual(view["fases"]["entender_rota"]["motivo_automatico"]["tipo"], "ator_indisponivel")

    def test_fato_canonico_muda_fases_e_condicoes_sem_percentual(self):
        mid, _ = self.setup_quest()
        self.accept45(mid)
        fact = {
            "id": "entrega_segura_confirmada",
            "descricao": "A rota foi estabelecida e a entrega terminou em destino seguro.",
            "prova": self.proof45(FACT_TEXT),
            "fases": {"entender_rota": "resolvida", "entrega_em_movimento": "resolvida"},
            "condicoes_sucesso": {"sucesso_01": "satisfeita", "sucesso_02": "satisfeita"},
            "condicoes_falha": {},
        }
        first = progression.record_fact(self.repo, mid, fact_raw=fact)
        second = progression.record_fact(self.repo, mid, fact_raw=fact)
        self.assertTrue(first["avaliacao"]["sucesso_pronto"])
        self.assertEqual(second["resultado"], "fato_ja_registrado")
        view = progression.status(self.repo, mid)
        self.assertNotIn("percentual", yaml.safe_dump(view))


class Task45RewardTest(Task45Fixture):
    def test_recompensa_so_depois_de_sucesso_factual_e_retry_nao_duplica(self):
        mid, _ = self.setup_quest()
        self.accept45(mid)
        with self.assertRaisesRegex(progression.SidequestProgressionError, "não autorizam sucesso"):
            progression.finalize_success(
                self.repo,
                mid,
                optional_ids=[],
                evidences={},
                narration="Silva tenta pagar antes de o mundo ter estabelecido qualquer sucesso factual da missão.",
            )
        self.assertEqual(transacoes.load_pending(self.repo), [])
        progression.record_fact(
            self.repo,
            mid,
            fact_raw={
                "id": "sucesso_confirmado",
                "descricao": "As duas condições objetivas de sucesso tornaram-se fatos canônicos.",
                "prova": self.proof45(FACT_TEXT),
                "fases": {"entender_rota": "resolvida", "entrega_em_movimento": "resolvida"},
                "condicoes_sucesso": {"sucesso_01": "satisfeita", "sucesso_02": "satisfeita"},
                "condicoes_falha": {},
            },
        )
        first = progression.finalize_success(
            self.repo,
            mid,
            optional_ids=[],
            evidences={},
            narration="Silva confirma o cumprimento da missão e entrega a Ren as trezentas peças de ouro que estavam contratadas como recompensa principal.",
        )
        second = progression.finalize_success(
            self.repo,
            mid,
            optional_ids=[],
            evidences={},
            narration="Silva confirma novamente o mesmo pagamento já registrado, sem criar uma segunda recompensa.",
        )
        self.assertEqual(first["recompensa"]["resultado"], "recompensas_obtidas")
        self.assertEqual(second["recompensa"]["resultado"], "nenhuma_recompensa_nova")
        self.assertEqual(len(transacoes.load_pending(self.repo)), 1)


class Task45ConsequenceTest(Task45Fixture):
    def _fail_and_pending(self, mid: str) -> str:
        self.accept45(mid)
        progression.record_fact(
            self.repo,
            mid,
            fact_raw={
                "id": "oposicao_obteve_entrega",
                "descricao": "A oposição obteve de modo durável aquilo que a missão deveria proteger.",
                "prova": self.proof45(FAIL_TEXT),
                "fases": {"entrega_em_movimento": "resolvida"},
                "condicoes_sucesso": {},
                "condicoes_falha": {"falha_01": "satisfeita"},
            },
        )
        result = progression.finalize_failure(self.repo, mid)
        return result["pendencia"]["id"]

    def test_consequencia_e_npc_aplicam_uma_vez_e_retry_repara(self):
        mid, _ = self.setup_quest()
        self.add_messenger_canonical()
        pending_id = self._fail_and_pending(mid)
        proof = self.proof45(FAIL_TEXT)
        first = progression.resolve_pending(
            self.repo,
            mid,
            pending_id,
            chosen_escalation_id="interceptar_mensageiro",
            proofs={"interceptar_mensageiro": proof},
            blocker=None,
            narration="A célula alcança o Mensageiro Cinza antes que ele abandone a rota e o retira de circulação, materializando a interceptação que já estava prevista.",
        )
        second = progression.resolve_pending(
            self.repo,
            mid,
            pending_id,
            chosen_escalation_id="interceptar_mensageiro",
            proofs={"interceptar_mensageiro": proof},
            blocker=None,
            narration="A mesma interceptação é reavaliada em retry e não pode criar uma segunda captura ou uma segunda consequência.",
        )
        pending = transacoes.load_pending(self.repo)
        self.assertEqual(len(pending), 1)
        npc_deltas = [d for d in pending[0]["deltas"] if d.get("alvo") == "npc:mensageiro_cinza_task41"]
        self.assertEqual(npc_deltas, [{"alvo": "npc:mensageiro_cinza_task41", "op": "set", "caminho": "vida.estado", "valor": "preso"}])
        self.assertEqual(first["transacao_id"], second["transacao_id"])
        self.assertEqual(mundo.load_world_state(self.repo)["pendencias"], [])

    def test_protected_core_continua_bloqueando_sidequest_lateral_grave(self):
        mid, _ = self.setup_quest()
        pending_id = self._fail_and_pending(mid)
        with self.assertRaises(progression.SidequestProgressionError):
            progression.resolve_pending(
                self.repo,
                mid,
                pending_id,
                chosen_escalation_id="silenciar_elo_critico",
                proofs={"silenciar_elo_critico": self.proof45(CORE_TEXT)},
                blocker=None,
                narration="A rede tenta remover Silva da circulação, mas a autoridade lateral precisa respeitar o Protected Core antes de qualquer materialização.",
            )
        self.assertEqual(transacoes.load_pending(self.repo), [])
        self.assertEqual(len(mundo.load_world_state(self.repo)["pendencias"]), 1)


class Task45BudgetAndCanonContractTest(unittest.TestCase):
    def test_repo_real_sem_quest_emergente_permanece_valido_e_sem_infra_nova(self):
        result = progression.check(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["scheduler_novo"], 0)
        self.assertEqual(result["rng_novo"], 0)
        self.assertEqual(result["scan_global"], 0)
        self.assertLessEqual(progression.MAX_PROJECT_BYTES, 8192)
        self.assertEqual(progression.MAX_PENDING_TASK45, 2)

    def test_falha_terminal_usa_task42_e_nao_motor_paralelo_de_canone(self):
        source = (ROOT / "ferramentas/progressao_sidequests.py").read_text(encoding="utf-8")
        self.assertIn("canon_bridge_runtime.finish", source)
        self.assertNotIn("import canon_bridge\n", source)
        self.assertNotIn("import random", source)
        self.assertNotIn("sched", source.lower().replace("scheduler", ""))

    def test_maximo_de_duas_aceitas_continua_autoridade_de_oportunidades(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            for rel in (oportunidades.INDEX, oportunidades.STATE):
                dst = repo / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ROOT / rel, dst)
            index = oportunidades.load_index(repo)
            state = oportunidades.load_state(repo, index)
            now = mundo.parse_instant("12 Eleasis, 1372 DR", "10:00")
            for i in range(3):
                mid = f"manual-{i}"
                state["missoes"][mid] = {
                    "id": mid,
                    "estado": "oferecida",
                    "npc_id": f"npc_{i}",
                    "necessidade_id": f"n_{i}",
                    "janela": {"tipo": "a_qualquer_momento"},
                }
            oportunidades.atomic(repo / oportunidades.STATE, state)
            oportunidades.respond(repo, "manual-0", "aceitar", now=now)
            oportunidades.respond(repo, "manual-1", "aceitar", now=now)
            with self.assertRaisesRegex(oportunidades.OpportunityError, "limite de side quests ativas"):
                oportunidades.respond(repo, "manual-2", "aceitar", now=now)


if __name__ == "__main__":
    unittest.main()
