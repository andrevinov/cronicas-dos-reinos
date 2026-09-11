from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1] / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import planos_personagens as plans
import resolver_fronteira as batch
import mundo
import test_planos_personagens as legacy


class EntryLocalSchemaTest(unittest.TestCase):
    def ref(self, path="npc.disponivel", value=True):
        return {"arquivo": "estado/npcs/visitante.yaml", "caminho": path, "valor": value}

    def step(self):
        availability = self.ref()
        resources = [{"caminho": "recursos.moedas", "quantidade": 1}]
        return {
            "id": "visitar",
            "acao": "Ir ao circo por uma causa já estabelecida.",
            "em": {"data": "7 Eleasis, 1372 DR", "hora": "10:00"},
            "duracao_minutos": 30,
            "local": "Circo",
            "condicoes": [],
            "recursos": resources,
            "conhecimento": ["rota_circo"],
            "resolucao": {"tipo": "factual", "sem_oposicao": availability},
            "entrada_local": {
                "causa": self.ref("npc.motivos.visita", True),
                "origem": "Porto",
                "destino": "Circo",
                "janela": {
                    "inicio": {"data": "7 Eleasis, 1372 DR", "hora": "10:30"},
                    "fim": {"data": "7 Eleasis, 1372 DR", "hora": "11:30"},
                },
                "duracao_esperada_minutos": 90,
                "conhecimento_necessario": ["rota_circo"],
                "disponibilidade": availability,
                "recursos_necessarios": resources,
                "motivo_presenca": "Entregar um recado que exige presença física.",
            },
        }

    def test_schema_exige_contrato_completo_e_coerente(self):
        step = self.step()
        self.assertEqual(plans._step(step), step)
        for field in sorted(step["entrada_local"]):
            with self.subTest(field=field):
                bad = deepcopy(step)
                del bad["entrada_local"][field]
                with self.assertRaises(plans.PlanError):
                    plans._step(bad)

    def test_origem_destino_e_janela_nao_podem_ser_relaxados(self):
        same = self.step()
        same["entrada_local"]["origem"] = "Circo"
        with self.assertRaisesRegex(plans.PlanError, "origem e destino"):
            plans._step(same)
        late = self.step()
        late["duracao_minutos"] = 100
        with self.assertRaisesRegex(plans.PlanError, "janela"):
            plans._step(late)

    def test_conhecimento_recursos_e_disponibilidade_reutilizam_contrato_do_passo(self):
        for mutate in ("conhecimento", "recursos", "disponibilidade"):
            with self.subTest(mutate=mutate):
                bad = self.step()
                if mutate == "conhecimento":
                    bad["entrada_local"]["conhecimento_necessario"] = []
                elif mutate == "recursos":
                    bad["entrada_local"]["recursos_necessarios"] = []
                else:
                    bad["entrada_local"]["disponibilidade"] = self.ref("npc.outra", True)
                with self.assertRaises(plans.PlanError):
                    plans._step(bad)


class EntryLocalJourneyTest(legacy.PlanFixture):
    def setUp(self):
        super().setUp()
        for aid in self.people:
            path = f"estado/npcs/{aid}.yaml"
            doc = self.read(path)
            doc["npc"]["presenca"] = {
                "local": "Origem",
                "estado": "presente",
                "em_deslocamento": False,
            }
            self.write(path, doc)

    def entry_step(self, *, actor=None, sid="visitar"):
        aid = actor or self.actor
        step = self.step(sid=sid, hour="08:03", cost=1, actor=aid)
        step["local"] = "Circo"
        step["duracao_minutos"] = 5
        availability = self.ref("oportunidade.sem_oposicao", True, f"estado/npcs/{aid}.yaml")
        step["resolucao"] = {"tipo": "factual", "sem_oposicao": availability}
        step["entrada_local"] = {
            "causa": self.ref("oportunidade.sem_oposicao", True, f"estado/npcs/{aid}.yaml"),
            "origem": "Origem",
            "destino": "Circo",
            "janela": {
                "inicio": {"data": legacy.DATE, "hora": "08:08"},
                "fim": {"data": legacy.DATE, "hora": "08:30"},
            },
            "duracao_esperada_minutos": 60,
            "conhecimento_necessario": list(step["conhecimento"]),
            "disponibilidade": availability,
            "recursos_necessarios": deepcopy(step["recursos"]),
            "motivo_presenca": "A rotina documental exige uma visita causal ao circo.",
        }
        return step

    def current_pending(self, pid="documentos"):
        plan = self.plan(pid)
        return next(p for p in mundo.load_world_state(self.repo)["pendencias"] if p["id"] == plan["pendencia_id"])

    def apply_entry(self, action, fact, *, pid="documentos", retomar_em=None):
        prepared = batch.prepare_batch(self.repo)
        pending = self.current_pending(pid)
        item = next(row for row in prepared["itens"] if row["id"] == pending["id"])
        decision = plans.compile_entry_decision(
            self.repo, pending, acao=action, fato=fact, retomar_em=retomar_em
        )
        payload = {
            "lote_id": prepared["lote_id"],
            "planos": [{"id": pending["id"], "token": item["token"], **decision}],
        }
        return batch.apply_batch(self.repo, payload)

    def test_cadastro_isolado_nao_cria_cameo(self):
        self.assertIsNone(plans.project_local_entry(self.repo, "Circo"))

    def test_movimento_e_chegada_usam_mesmo_plano_e_mesma_transacao(self):
        self.define(step=self.entry_step())
        self.assertEqual(self.plan()["tipo"], plans.ENTRY_TYPE)
        projected = plans.project_local_entry(self.repo, "Circo")
        self.assertEqual(projected["plano_id"], "documentos")
        self.assertEqual(projected["fase"], "partida_devida")

        with mock.patch.object(legacy.turno, "register_transaction", wraps=legacy.turno.register_transaction) as writer:
            self.apply_entry("iniciar", "A escriba iniciou a viagem ao circo.")
        tx = writer.call_args.args[1]
        self.assertTrue(any(d.get("alvo") == "plano:documentos" for d in tx["deltas"]))
        self.assertTrue(any(d.get("alvo") == f"npc:{self.actor}" and d.get("caminho") == "presenca" for d in tx["deltas"]))
        moving = self.read(self.source)["npc"]["presenca"]
        self.assertEqual(moving["estado"], "em_deslocamento")
        self.assertEqual(moving["destino"], "Circo")

        self.advance("08:08")
        due = plans.project_local_entry(self.repo, "Circo")
        self.assertEqual(due["fase"], "chegada_devida")
        self.apply_entry("chegar", "A escriba chegou ao circo para cumprir o motivo da visita.")
        arrived = self.read(self.source)["npc"]["presenca"]
        self.assertEqual(arrived["estado"], "presente")
        self.assertEqual(arrived["local"], "Circo")
        self.assertFalse(arrived["em_deslocamento"])
        self.assertEqual(arrived["plano_entrada"], "documentos")
        self.assertEqual(self.plan()["estado"], "concluido")

        later = mundo.parse_instant(legacy.DATE, "09:09")
        effective = plans.effective_presence(self.repo, self.actor, now=later)
        self.assertFalse(effective["presenca"]["presente"])
        self.assertEqual(effective["presenca"]["estado_efetivo"], "expirada")

    def test_adiamento_preserva_plano_e_nao_move_personagem(self):
        self.define(step=self.entry_step())
        before = deepcopy(self.read(self.source)["npc"]["presenca"])
        self.apply_entry(
            "adiar",
            "A saída precisou ser adiada por um bloqueio concreto.",
            retomar_em={"data": legacy.DATE, "hora": "08:20"},
        )
        plan = self.plan()
        self.assertEqual(plan["estado"], "bloqueado")
        self.assertIsNotNone(plan["pendencia_id"])
        self.assertEqual(self.read(self.source)["npc"]["presenca"], before)
        self.assertIsNone(plans.project_local_entry(self.repo, "Circo"))

    def test_uma_janela_projeta_no_maximo_uma_entrada_e_abre_um_ator(self):
        other = self.people[1]
        self.define("a_visita", step=self.entry_step(sid="a_visita"))
        self.define("b_visita", actor=other, step=self.entry_step(actor=other, sid="b_visita"))
        with mock.patch.object(plans.agentes_leves, "load_agent", wraps=plans.agentes_leves.load_agent) as load:
            result = plans.project_local_entry(self.repo, "Circo")
        self.assertIn(result["plano_id"], {"a_visita", "b_visita"})
        self.assertEqual(load.call_count, 1)

    def test_tentativa_manual_sem_delta_de_presenca_falha_fechado(self):
        self.define(step=self.entry_step())
        payload = self.payload("tentar")
        with self.assertRaisesRegex(ValueError, "movimento/presença"):
            batch.apply_batch(self.repo, payload)


if __name__ == "__main__":
    unittest.main()
