"""NV-11 em fixtures: causas de NPCs entram no lifecycle existente."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica
import mundo
import oportunidade_sidequest
import oportunidades
import planos_personagens as plans
import sidequests_emergentes as emergent
import sidequests_integracao as integration
import sidequests_personagens as characters
from test_planos_personagens import DATE, NOW, PlanFixture


class CharacterSidequestFixture(PlanFixture):
    def setUp(self):
        super().setUp()
        for rel in (oportunidades.INDEX, oportunidades.STATE):
            target = self.repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, target)
        state = self.read(oportunidades.STATE.as_posix())
        state["missoes"] = {}
        state["pendencias_avaliacao"] = {}
        state["sementes_consumidas"] = []
        state["historico_recente"] = []
        state["cooldown_ate"] = None
        self.write(oportunidades.STATE.as_posix(), state)

        npc = self.read(self.source)
        npc["npc"].update(
            {
                "necessidades": {
                    "documentos_ameacados": "Os documentos precisam chegar antes que a rota seja fechada."
                },
                "conflitos": {
                    "dever_e_seguranca": "A entrega protege terceiros, mas expõe a escriba."
                },
                "impedimentos": {
                    "ponte_fechada": "A ponte fechada impede a rota conhecida."
                },
            }
        )
        self.write(self.source, npc)

    def contract(self, source_type: str = "necessidade") -> dict:
        path = {
            "necessidade": "necessidades.documentos_ameacados",
            "conflito": "conflitos.dever_e_seguranca",
            "impedimento": "impedimentos.ponte_fechada",
        }[source_type]
        value = self.read(self.source)["npc"]
        for part in path.split("."):
            value = value[part]
        return {
            "versao": 1,
            "tipo": source_type,
            "causa": self.ref(path, value),
            "situacao": (
                "A entrega documental está presa a uma janela concreta e a rota "
                "pode deixar de existir antes da chegada."
            ),
            "motivo_envolver_ren": (
                "A escriba pede a ajuda de Ren porque ele conhece a região e pode "
                "escolher se quer intervir na rota ameaçada."
            ),
            "consequencias": {
                "agir": (
                    "A entrega pode alcançar um caminho seguro, sujeita aos riscos e "
                    "à resolução mecânica da tentativa."
                ),
                "nao_agir": (
                    "A rota pode fechar e obrigar a escriba a abandonar a entrega "
                    "sem que isso imponha punição artificial a Ren."
                ),
            },
        }

    def opportunity_step(self, source_type: str = "necessidade") -> dict:
        step = self.step(cost=0)
        step[characters.STEP_KEY] = self.contract(source_type)
        return step

    @staticmethod
    def opportunity_router_stub(*_args, **kwargs) -> dict:
        now = kwargs.get("now") or mundo.parse_instant(NOW["data"], NOW["hora"])
        return {
            "ok": True,
            "resultado": "material_para_planejamento",
            "read_only": True,
            "mutacoes_aplicadas": False,
            "origem": {
                "tipo": kwargs["origin_type"],
                "id": kwargs["origin_id"],
                "npc_id": kwargs["npc_id"],
                "ancora_tipo": kwargs["anchor_type"],
                "ancora": kwargs["anchor"],
            },
            "quests": {"ativas": 0, "abertas": 0, "max_ativas": 2, "max_abertas": 3, "atuais": []},
            "prazo_mundo": {"agora": mundo.instant_parts(now), "local_id": kwargs.get("local_id"), "condicoes_persistentes": []},
            "horizonte_intencoes_canonicas": {"compativeis": []},
            "atores_causalmente_disponiveis": [],
            "juppongatana_possiveis": [],
            "envelope_recompensa": {"regra": "fixture", "teto_valor": "moderado"},
            "autoridade": {"pode_planejar": True, "pode_criar_missao": False, "pode_oferecer_missao": False, "pode_reescrever_intencao": False, "pode_marcar_intencao_satisfeita": False},
            "fontes_lidas": [],
            "metricas": {"intencoes_lidas": 0, "scans_globais": 0, "catalogo_task33_aberto": False, "transcricao_lida": False, "escritas": 0},
        }

    def project(self, plan_id: str = "documentos") -> dict:
        with patch.object(characters.opportunity, "plan", side_effect=self.opportunity_router_stub):
            return characters.plan(self.repo, plan_id, danger="media", tier=2)


class CharacterOpportunityTest(CharacterSidequestFixture):
    def test_necessidade_pode_ser_preparada_antes_de_conversa_com_ren(self):
        self.define(step=self.opportunity_step())
        before = self.hashes()
        package = self.project()
        self.assertEqual(package["resultado"], "material_para_planejamento")
        self.assertEqual(package["origem"]["tipo"], "plano_personagem")
        cause = package["causa_personagem"]
        self.assertEqual(cause["interessado"]["id"], self.actor)
        self.assertEqual(cause["tipo"], "necessidade")
        self.assertIn("motivo_envolver_ren", cause)
        self.assertEqual(set(cause["consequencias_possiveis"]), {"agir", "nao_agir"})
        self.assertEqual(before, self.hashes())

    def test_causa_de_outro_personagem_falha_antes_do_writer(self):
        step = self.opportunity_step()
        other = f"estado/npcs/{self.people[1]}.yaml"
        doc = self.read(other)
        doc["npc"]["necessidades"] = {
            "documentos_ameacados": "Outra necessidade que pertence a outra pessoa."
        }
        self.write(other, doc)
        step[characters.STEP_KEY]["causa"] = {
            "arquivo": other,
            "caminho": "npc.necessidades.documentos_ameacados",
            "valor": "Outra necessidade que pertence a outra pessoa.",
        }
        before = self.hashes()
        with self.assertRaisesRegex(ValueError, "próprio personagem"):
            self.define(step=step)
        self.assertEqual(before, self.hashes())

    def test_impedimento_so_fica_elegivel_quando_plano_esta_bloqueado(self):
        self.define(step=self.opportunity_step("impedimento"))
        with self.assertRaisesRegex(characters.CharacterSidequestError, "bloqueado"):
            self.project()
        payload = self.payload(
            "bloquear",
            motivo="A ponte fechada impede a rota conhecida.",
            retomar_em={"data": DATE, "hora": "08:20"},
        )
        __import__("resolver_fronteira").apply_batch(self.repo, payload)
        self.assertEqual(self.project()["causa_personagem"]["estado_plano"], "bloqueado")

    def test_cronica_aceita_plano_como_sinal_sem_ancora_manual(self):
        parser = cronica.build_parser()
        args = parser.parse_args(
            [
                "preparar",
                "--cena-id",
                "nv11-fixture",
                "--oportunidade-sidequest",
                "--sidequest-plano",
                "documentos",
            ]
        )
        self.assertEqual(
            cronica._sidequest_signal_from_args(args),
            {
                "plano_id": "documentos",
                "local_id": None,
                "periculosidade": "media",
                "tier": None,
            },
        )
        args = parser.parse_args(
            [
                "preparar",
                "--cena-id",
                "nv11-invalida",
                "--oportunidade-sidequest",
                "--sidequest-plano",
                "documentos",
                "--sidequest-ancora",
                "uma âncora manual concorrente não deve ser aceita",
            ]
        )
        with self.assertRaisesRegex(cronica.CronicaError, "não pode acompanhar"):
            cronica._sidequest_signal_from_args(args)

    def test_integracao_carrega_causa_no_mesmo_ticket(self):
        self.define(step=self.opportunity_step())
        base_payload = {
            "schema_cronica_ticket": 1,
            "preparacao_id": "prep-nv11-fixture",
            "cena": {
                "scene_id": "nv11-fixture",
                "npcs": [],
                "place": None,
                "action": None,
                "tier": None,
                "danger": None,
                "context_tags": [],
                "now_minute": None,
                "approach": {"preparacao": None, "informacao": None, "adequacao": None},
            },
        }
        token, tid = cronica._core.encode_ticket(base_payload)
        base = {"ticket": token, "ticket_id": tid, "fase": "preparacao"}
        before = self.hashes()
        with patch.object(characters.opportunity, "plan", side_effect=self.opportunity_router_stub):
            result = integration.integrate_prepare(
                self.repo,
                base,
                signal_raw={"plano_id": "documentos", "local_id": None, "periculosidade": "media", "tier": 2},
                decode_ticket=cronica._core.decode_ticket,
                encode_ticket=cronica._core.encode_ticket,
            )
        meta = integration.ticket_meta(cronica._core.decode_ticket(result["ticket"]))
        self.assertTrue(result["sidequest_emergente_task46"]["integrada_ao_ticket"])
        self.assertEqual(meta["sinal"]["modo"], "plano_personagem")
        self.assertEqual(meta["sinal"]["causa_id"], result["sidequest_emergente"]["causa_personagem"]["id"])
        with patch.object(characters.opportunity, "plan", side_effect=self.opportunity_router_stub):
            replayed = integration._plan_from_ticket(self.repo, meta)
        self.assertEqual(replayed, result["sidequest_emergente"])
        self.assertEqual(before, self.hashes())

    def test_origem_de_plano_nao_pode_contornar_a_referencia_dirigida(self):
        with self.assertRaisesRegex(
            oportunidade_sidequest.EmergentSidequestOpportunityError,
            "--sidequest-plano",
        ):
            oportunidade_sidequest._validate_signal(
                origin_type="plano_personagem",
                origin_id="plano-personagem:forjado",
                anchor_type="necessidade",
                anchor="Uma necessidade escrita manualmente tentaria contornar o contrato dirigido.",
                npc_id=self.actor,
                local_id=None,
                danger="media",
                tier=2,
            )

    def test_recusa_preserva_causa_e_impede_reoferta_indefinida(self):
        self.define(step=self.opportunity_step())
        package = self.project()
        cause = package["causa_personagem"]
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        state["missoes"]["sqe-fixture"] = {
            "id": "sqe-fixture",
            "estado": "oferecida",
            "origem": "sidequest_emergente",
            "npc_id": self.actor,
            "necessidade_id": "fixture",
            "causa_personagem": cause,
        }
        oportunidades.atomic(self.repo / oportunidades.STATE, state)
        world_before = (self.repo / mundo.WORLD_STATE_PATH).read_bytes()
        refused = oportunidades.respond(
            self.repo,
            "sqe-fixture",
            "recusar",
            now=mundo.parse_instant(NOW["data"], NOW["hora"]),
        )
        self.assertEqual(refused["resultado"], "recusada")
        with patch.object(
            characters.opportunity,
            "plan",
            side_effect=AssertionError("causa recusada não deve voltar à Task40"),
        ):
            repeated = characters.plan(self.repo, "documentos", danger="media", tier=2)
        self.assertEqual(repeated["resultado"], "causa_personagem_ja_encaminhada")
        self.assertEqual(repeated["missao_existente"]["estado"], "recusada")
        self.assertEqual(world_before, (self.repo / mundo.WORLD_STATE_PATH).read_bytes())


class CharacterLifecycleTest(CharacterSidequestFixture):
    def test_registro_nasce_oferecido_e_abandono_exige_aceite(self):
        cause = {
            "id": "scp-0123456789abcdef01234567",
            "interessado": {"tipo": "leve", "id": self.actor},
        }
        mission = emergent._mission_record(
            qid="qse-0123456789abcdef",
            spec={
                "quest_giver": {"id": self.actor},
                "tipo": "favor",
                "titulo": "A rota dos documentos",
                "objetivo": "Levar os documentos por uma rota ainda segura.",
                "prazo": {"tipo": "a_qualquer_momento"},
                "stakes": {"consequencia_expiracao": "A rota pode fechar."},
                "recompensas": [],
            },
            package={"prazo_mundo": {"agora": NOW}, "causa_personagem": cause},
            preparation_id="sqe-prep-0123456789abcdef01234567",
            offer_scene_id="nv11:fixture",
        )
        self.assertEqual(mission["estado"], "oferecida")
        self.assertEqual(mission["causa_personagem"], cause)

        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        state["missoes"][mission["id"]] = mission
        oportunidades.atomic(self.repo / oportunidades.STATE, state)
        now = mundo.parse_instant(NOW["data"], NOW["hora"])
        with self.assertRaisesRegex(oportunidades.OpportunityError, "aceita"):
            oportunidades.abandon(self.repo, mission["id"], reason="Ren não assumiu a missão.", now=now)
        oportunidades.respond(self.repo, mission["id"], "aceitar", now=now)
        world_before = (self.repo / mundo.WORLD_STATE_PATH).read_bytes()
        result = oportunidades.abandon(
            self.repo,
            mission["id"],
            reason="Ren encerrou explicitamente sua participação.",
            now=now,
        )
        self.assertEqual(result["resultado"], "abandonada")
        self.assertFalse(result["consequencia_automatica"])
        self.assertEqual(world_before, (self.repo / mundo.WORLD_STATE_PATH).read_bytes())
        with self.assertRaisesRegex(oportunidades.OpportunityError, "encerrada"):
            oportunidades.finish(
                self.repo,
                mission["id"],
                "concluida",
                reason="Não pode concluir após abandono.",
                now=now,
            )

    def test_autoria_nao_pode_trocar_interessado_pedido_ou_consequencia(self):
        cause = {
            "interessado": {"tipo": "leve", "id": self.actor},
            "situacao": "Uma situação concreta ligada ao plano precisa ser apresentada.",
            "motivo_envolver_ren": "A pessoa interessada formula um pedido que Ren pode aceitar ou recusar.",
            "consequencias_possiveis": {
                "agir": "A situação pode melhorar depois da resolução factual.",
                "nao_agir": "O problema pode seguir seu curso sem punição artificial.",
            },
        }
        spec = {
            "quest_giver": {"id": self.actor},
            "oferta": {"premissa": cause["situacao"], "pedido": cause["motivo_envolver_ren"]},
            "stakes": {"consequencia_expiracao": cause["consequencias_possiveis"]["nao_agir"]},
        }
        characters.validate_authoring_link(cause, spec)
        for path, value in (
            (("quest_giver", "id"), self.people[1]),
            (("oferta", "pedido"), "Um pedido inventado substitui a causa original."),
            (("stakes", "consequencia_expiracao"), "Uma punição inventada."),
        ):
            changed = deepcopy(spec)
            changed[path[0]][path[1]] = value
            with self.assertRaises(characters.CharacterSidequestError):
                characters.validate_authoring_link(cause, changed)


if __name__ == "__main__":
    unittest.main()
