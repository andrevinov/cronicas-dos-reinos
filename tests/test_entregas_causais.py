from __future__ import annotations

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
import entregas_causais
import mundo

PENDING_ID = "mundo-1111111111111111"


class EntregasCausaisContractTest(unittest.TestCase):
    def pending(self, kind: str = "reavaliar_agente") -> dict:
        return {
            "id": PENDING_ID,
            "tipo": kind,
            "agente": "red_sail",
            "agentes_afetados": ["red_sail"],
            "disparado_em": {"data": "11 Eleasis, 1372 DR", "hora": "06:00"},
            "motivo": "Avaliar uma iniciativa sem fazê-la acontecer automaticamente.",
            "origem": "agenda:reavaliacoes.red_sail",
        }

    def event(self, destination: dict, pending_id: str = PENDING_ID) -> dict:
        return {
            "versao": 1,
            "tipo": "entrega_causal",
            "pendencia": pending_id,
            "comunicavel": True,
            "destinatario": "ren",
            "causa": "A resolução do mundo produziu uma informação destinada a Ren.",
            "conteudo": "A patrulha descobriu movimento incomum no cais sul.",
            "destino": destination,
        }

    def delta(self, destination: dict, pending_id: str = PENDING_ID) -> dict:
        return {
            "alvo": entregas_causais.target_for(pending_id),
            "op": "registrar",
            "visibilidade": "narrador",
            "valor": self.event(destination, pending_id),
        }

    def transaction(self, *, tags=None, deltas=None) -> dict:
        return {
            "modo": "mundo",
            "narracao": "O mundo avança fora da presença de Ren.",
            "resumo": "Resolução de uma pendência do Mundo Vivo.",
            "tags": list(tags or []),
            "deltas": list(deltas or []),
        }

    def test_destinos_finais_validos(self):
        cases = [
            {"estado": "entregue", "canal": "mensageiro confiável em Ravens Bluff"},
            {
                "estado": "plano",
                "plano_id": "avisar_ren",
                "responsavel": "shinta",
                "canal": "encontro presencial",
                "prazo": {"data": "12 Eleasis, 1372 DR", "hora": "09:00"},
            },
            {
                "estado": "bloqueada",
                "motivo": "sem_canal",
                "detalhe": "Ren está fora do alcance e nenhum mensageiro conhece sua posição.",
            },
            {
                "estado": "falhou",
                "canal": "mensageiro",
                "consequencia": "O mensageiro foi interceptado antes de alcançar Ren.",
            },
            {
                "estado": "abandonada",
                "consequencia": "A fonte decidiu não correr o risco de transmitir a informação.",
            },
        ]
        for destination in cases:
            with self.subTest(destination=destination["estado"]):
                tx = self.transaction(deltas=[self.delta(destination)])
                if destination["estado"] == "plano":
                    tx["deltas"].append(
                        {"alvo": "plano:avisar_ren", "op": "registrar", "valor": {}}
                    )
                result = entregas_causais.validate_resolution(self.pending(), tx)
                self.assertIsNotNone(result)
                self.assertEqual(result["destino"]["estado"], destination["estado"])

    def test_resolucao_generica_exige_destino_ou_negativa_explicita(self):
        with self.assertRaises(entregas_causais.DeliveryError) as ctx:
            entregas_causais.validate_resolution(self.pending(), self.transaction())
        self.assertIn("exatamente um destino NV-13", str(ctx.exception))

        tx = self.transaction(tags=[entregas_causais.NON_COMMUNICABLE_TAG])
        self.assertIsNone(entregas_causais.validate_resolution(self.pending(), tx))

    def test_negativa_nao_pode_coexistir_com_recibo(self):
        tx = self.transaction(
            tags=[entregas_causais.NON_COMMUNICABLE_TAG],
            deltas=[self.delta({"estado": "entregue", "canal": "mensageiro"})],
        )
        with self.assertRaises(entregas_causais.DeliveryError):
            entregas_causais.validate_resolution(self.pending(), tx)
        with self.assertRaises(entregas_causais.DeliveryError):
            entregas_causais.validate_retry_shape(tx, PENDING_ID)

    def test_recibo_precisa_ser_reservado_e_sem_caminho(self):
        delta = self.delta({"estado": "entregue", "canal": "mensageiro"})
        delta["visibilidade"] = "operacional"
        with self.assertRaises(entregas_causais.DeliveryError):
            entregas_causais.validate_resolution(
                self.pending(), self.transaction(deltas=[delta])
            )

        delta = self.delta({"estado": "entregue", "canal": "mensageiro"})
        delta["caminho"] = "estado"
        with self.assertRaises(entregas_causais.DeliveryError):
            entregas_causais.validate_resolution(
                self.pending(), self.transaction(deltas=[delta])
            )

    def test_plano_exige_evento_do_plano_na_mesma_transacao(self):
        destination = {
            "estado": "plano",
            "plano_id": "avisar_ren",
            "responsavel": "shinta",
            "canal": "encontro presencial",
            "prazo": {"data": "12 Eleasis, 1372 DR", "hora": "09:00"},
        }
        tx = self.transaction(deltas=[self.delta(destination)])
        with self.assertRaises(entregas_causais.DeliveryError) as ctx:
            entregas_causais.validate_resolution(self.pending(), tx)
        self.assertIn("plano:avisar_ren", str(ctx.exception))

        tx["deltas"].append({"alvo": "plano:avisar_ren", "op": "registrar", "valor": {}})
        result = entregas_causais.validate_resolution(self.pending(), tx)
        self.assertEqual(result["destino"]["estado"], "plano")

    def test_tipos_com_writer_de_dominio_nao_sao_forcados_pelo_gate_generico(self):
        for kind in sorted(entregas_causais.EXEMPT_PENDING_TYPES):
            with self.subTest(kind=kind):
                self.assertIsNone(
                    entregas_causais.validate_resolution(self.pending(kind), self.transaction())
                )


class EntregasCausaisPersistenceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "narrador/mundo").mkdir(parents=True)
        (self.repo / "runtime").mkdir(parents=True)
        self.pending = {
            "id": PENDING_ID,
            "tipo": "movimento",
            "agente": "red_sail",
            "agentes_afetados": ["red_sail"],
            "disparado_em": {"data": "11 Eleasis, 1372 DR", "hora": "06:00"},
            "motivo": "Resolver movimento fora de cena.",
            "origem": "agenda:agendamentos.movimento_red_sail",
        }
        self.write_state([self.pending])

    def tearDown(self):
        self.temp.cleanup()

    def write_state(self, pending: list[dict]) -> None:
        path = self.repo / mundo.WORLD_STATE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(
                {
                    "schema_estado_mundo": 1,
                    "natureza": "controle_reservado",
                    "processado_ate": {"data": "11 Eleasis, 1372 DR", "hora": "15:30"},
                    "pendencias": pending,
                    "concluidas_recentes": [],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def blocked_event(self, pending_id: str = PENDING_ID) -> dict:
        return {
            "versao": 1,
            "tipo": "entrega_causal",
            "pendencia": pending_id,
            "comunicavel": True,
            "destinatario": "ren",
            "causa": "A patrulha obteve uma informação para Ren.",
            "conteudo": "Há homens armados vigiando a saída leste.",
            "destino": {
                "estado": "bloqueada",
                "motivo": "sem_canal",
                "detalhe": "Nenhum portador sabe onde Ren está neste momento.",
            },
        }

    def test_entrega_bloqueada_substitui_causa_por_pendencia_e_e_idempotente(self):
        receipt = {
            "transacao": "s003-nv13blocked",
            "sessao": 3,
            "valor": self.blocked_event(),
        }
        first = entregas_causais.materialize_blocked(self.repo, self.pending, receipt)
        self.assertTrue(first["alterou"])
        self.assertNotEqual(first["pendencia"], PENDING_ID)

        state = mundo.load_world_state(self.repo)
        self.assertEqual(len(state["pendencias"]), 1)
        current = state["pendencias"][0]
        self.assertEqual(current["id"], first["pendencia"])
        self.assertEqual(current["tipo"], entregas_causais.PENDING_TYPE)
        self.assertEqual(current["entrega_causal"]["pendencia"], current["id"])
        self.assertEqual(state["concluidas_recentes"][0]["id"], PENDING_ID)
        self.assertEqual(
            state["concluidas_recentes"][0]["resultado"],
            "causa_resolvida_entrega_bloqueada",
        )

        second = entregas_causais.materialize_blocked(self.repo, current)
        self.assertFalse(second["alterou"])
        self.assertEqual(second["pendencia"], current["id"])
        state_again = mundo.load_world_state(self.repo)
        self.assertEqual(len(state_again["pendencias"]), 1)
        self.assertEqual(len(state_again["concluidas_recentes"]), 1)

    def test_projecao_bloqueada_preserva_conteudo_sem_expor_canal_falso(self):
        new_id = entregas_causais.materialize_blocked(
            self.repo,
            self.pending,
            {"transacao": "s003-nv13blocked", "sessao": 3, "valor": self.blocked_event()},
        )["pendencia"]
        current = next(
            item for item in mundo.load_world_state(self.repo)["pendencias"]
            if item["id"] == new_id
        )
        projection = entregas_causais.blocked_projection(self.repo, current)
        self.assertIsNotNone(projection)
        self.assertEqual(
            projection["nucleo_obrigatorio"],
            "Há homens armados vigiando a saída leste.",
        )
        self.assertIn("não expor conteúdo sem canal válido", projection["guardrails"])

    def test_latest_le_recibo_do_relogio_transacional(self):
        clock = self.repo / "narrador/relogios" / f"{entregas_causais.clock_id(PENDING_ID)}.yaml"
        clock.parent.mkdir(parents=True, exist_ok=True)
        event = self.blocked_event()
        clock.write_text(
            yaml.safe_dump(
                {
                    "schema_relogio": 1,
                    "id": entregas_causais.clock_id(PENDING_ID),
                    "natureza": "reservado",
                    "relogio": {},
                    "eventos": [
                        {"transacao": "s003-nv13blocked", "sessao": 3, "valor": event}
                    ],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        result = entregas_causais.latest(self.repo, PENDING_ID)
        self.assertEqual(result["transacao"], "s003-nv13blocked")
        self.assertEqual(result["valor"]["destino"]["estado"], "bloqueada")


class EntregasCausaisBarrierTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "runtime").mkdir(parents=True)
        (self.repo / "narrador/mundo").mkdir(parents=True)
        self.pending = {
            "id": PENDING_ID,
            "tipo": "movimento",
            "agentes_afetados": [],
            "disparado_em": {"data": "11 Eleasis, 1372 DR", "hora": "06:00"},
            "motivo": "Resolver movimento fora de cena.",
            "origem": "agenda:agendamentos.movimento",
        }
        self.write_state([self.pending])
        barreira_mundo.sync(self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def write_state(self, pending: list[dict]) -> None:
        (self.repo / mundo.WORLD_STATE_PATH).write_text(
            yaml.safe_dump(
                {
                    "schema_estado_mundo": 1,
                    "natureza": "controle_reservado",
                    "processado_ate": {"data": "11 Eleasis, 1372 DR", "hora": "15:30"},
                    "pendencias": pending,
                    "concluidas_recentes": [],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def tx(self, *, tags=None, deltas=None) -> dict:
        return {
            "modo": "mundo",
            "narracao": "O mundo resolve a pendência.",
            "resumo": "Pendência resolvida.",
            "tags": [f"{barreira_mundo.RESOLUTION_TAG_PREFIX}{PENDING_ID}", *(tags or [])],
            "deltas": list(deltas or []),
        }

    def delivered_delta(self) -> dict:
        value = {
            "versao": 1,
            "tipo": "entrega_causal",
            "pendencia": PENDING_ID,
            "comunicavel": True,
            "destinatario": "ren",
            "causa": "A resolução produziu notícia para Ren.",
            "conteudo": "O cais sul foi fechado pela guarda.",
            "destino": {"estado": "entregue", "canal": "mensageiro da guarda"},
        }
        return {
            "alvo": entregas_causais.target_for(PENDING_ID),
            "op": "registrar",
            "visibilidade": "narrador",
            "valor": value,
        }

    def test_writer_repete_trava_e_rejeita_resolucao_sem_destino(self):
        with self.assertRaises(barreira_mundo.WorldPendingBarrierError) as ctx:
            barreira_mundo.authorize_registration(self.repo, self.tx(), retry=False)
        self.assertIn("exatamente um destino NV-13", str(ctx.exception))

    def test_writer_aceita_destino_entregue_no_mesmo_lote(self):
        result = barreira_mundo.authorize_registration(
            self.repo,
            self.tx(deltas=[self.delivered_delta()]),
            retry=False,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["pendencia_resolvida"], PENDING_ID)

    def test_writer_aceita_nao_comunicavel_explicito(self):
        result = barreira_mundo.authorize_registration(
            self.repo,
            self.tx(tags=[entregas_causais.NON_COMMUNICABLE_TAG]),
            retry=False,
        )
        self.assertTrue(result["ok"])
        self.assertEqual(result["pendencia_resolvida"], PENDING_ID)


if __name__ == "__main__":
    unittest.main()
