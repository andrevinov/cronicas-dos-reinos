from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica
import mundo
import oportunidades
import progresso_sidequests_transacional as transactional_progress
import recompensas_sidequest
import sidequests_ativas
import test_sidequest_progression_deadlines_consequences as progression_cases
import transacoes


TURN_EVIDENCE = (
    "A rota e a janela de risco foram confirmadas por testemunhos convergentes, "
    "e a entrega alcançou um destino seguro fora do controle da oposição."
)
LUATH_EVIDENCE = (
    "Luath verificou pessoalmente a origem institucional da ordem diante de Ren."
)


class TransactionalProgressFixture(progression_cases.Task45Fixture):
    def accepted_mission(self) -> str:
        mission_id, _ = self.setup_quest()
        self.accept45(mission_id)
        return mission_id

    def ticket(self) -> tuple[str, dict]:
        request = cronica._core._request(
            scene_id="transactional-sidequest-progress",
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
        preparation_id = cronica._hot._neutral_preparation_id(request)
        token, ticket_id = cronica._core.encode_ticket(
            {
                "schema_cronica_ticket": cronica._core.SCHEMA,
                "preparacao_id": preparation_id,
                "cena": request,
            }
        )
        base = {
            "schema_cronica_turno": 1,
            "fase": "preparacao",
            "ticket": token,
            "ticket_id": ticket_id,
            "filtros": [],
            "disponibilidade": {},
            "fontes_lidas": [],
            "contrato_conclusao": {"campos": {}},
        }
        prepared = sidequests_ativas.integrate_prepare(
            self.repo,
            base,
            decode_ticket=cronica.decode_ticket,
            encode_ticket=cronica._core.encode_ticket,
        )
        payload = cronica.decode_ticket(prepared["ticket"])
        meta = sidequests_ativas.ticket_meta(payload)
        assert meta is not None
        return prepared["ticket"], meta

    def transaction(self, mission_id: str, decision: dict) -> dict:
        return {
            "id": "tx-transactional-sidequest-progress",
            "narracao": (
                "Ren apresenta os elementos reunidos. " + TURN_EVIDENCE + " " + LUATH_EVIDENCE
            ),
            "resumo": "A investigação produziu fatos verificáveis sobre a missão aceita.",
            "modo": "interacao",
            "deltas": [],
            transactional_progress.TRANSACTION_KEY: [
                {"mission_id": mission_id, **decision}
            ],
        }

    def fact(
        self,
        *,
        phases: dict | None = None,
        success: dict | None = None,
        failure: dict | None = None,
        actors: list[str] | None = None,
        substitutions: list[dict] | None = None,
        evidence: str = TURN_EVIDENCE,
        fact_id: str = "fato_transacional",
        visibility: str = "narrador",
    ) -> dict:
        return {
            "id": fact_id,
            "descricao": "A atuação registrada alterou objetivamente o estado da missão.",
            "evidencia": evidence,
            "fases": phases or {},
            "condicoes_sucesso": success or {},
            "condicoes_falha": failure or {},
            "atores": actors or [],
            "substituicoes": substitutions or [],
            "visibilidade": visibility,
        }

    def progress_path(self, mission_id: str) -> Path:
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        return self.repo / state["missoes"][mission_id]["progresso_sidequest"]


class TransactionalProgressDecisionTest(TransactionalProgressFixture):
    def test_missao_projetada_exige_decisao_antes_do_writer(self):
        mission_id = self.accepted_mission()
        token, _ = self.ticket()
        transaction = self.transaction(mission_id, {"sem_fato_sidequest": True})
        transaction.pop(transactional_progress.TRANSACTION_KEY)
        with patch.object(cronica, "_conclude_base") as writer:
            with self.assertRaisesRegex(cronica.CronicaError, "exige progresso_sidequests"):
                cronica.conclude(self.repo, token, transaction)
        writer.assert_not_called()

    def test_sem_fato_registra_turno_sem_alterar_fragmento_de_progresso(self):
        mission_id = self.accepted_mission()
        token, _ = self.ticket()
        path = self.progress_path(mission_id)
        before = path.read_bytes()
        transaction = self.transaction(mission_id, {"sem_fato_sidequest": True})
        result = cronica.conclude(self.repo, token, transaction)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(
            result["progresso_sidequests"]["resultado"], "sem_fatos_sidequest"
        )
        self.assertEqual(len(transacoes.load_pending(self.repo)), 1)

    def test_evidencia_ausente_falha_antes_do_writer_e_do_journal(self):
        mission_id = self.accepted_mission()
        token, _ = self.ticket()
        fact = self.fact(phases={"entender_rota": "resolvida"}, actors=["silva_elkwood"])
        fact["evidencia"] = "Este trecho factual não aparece em nenhuma parte do turno corrente."
        transaction = self.transaction(mission_id, {"fatos_sidequest": [fact]})
        with patch.object(cronica, "_conclude_base") as writer:
            with self.assertRaisesRegex(cronica.CronicaError, "não aparece literalmente"):
                cronica.conclude(self.repo, token, transaction)
        writer.assert_not_called()
        self.assertFalse((self.repo / transactional_progress.JOURNAL).exists())


class TransactionalProgressFactTest(TransactionalProgressFixture):
    def test_fato_valido_resolve_fase_na_mesma_conclusao(self):
        mission_id = self.accepted_mission()
        token, _ = self.ticket()
        fact = self.fact(
            phases={"entender_rota": "resolvida"},
            actors=["silva_elkwood"],
        )
        result = cronica.conclude(
            self.repo,
            token,
            self.transaction(mission_id, {"fatos_sidequest": [fact]}),
        )
        doc = yaml.safe_load(self.progress_path(mission_id).read_text(encoding="utf-8"))
        self.assertEqual(doc["estado"]["fases"]["entender_rota"]["estado"], "resolvida")
        self.assertIn("fato_transacional", doc["estado"]["fatos"])
        self.assertEqual(result["progresso_sidequests"]["fatos_registrados"], 1)

    def test_substituto_competente_e_permitido_fica_no_historico(self):
        mission_id = self.accepted_mission()
        path = self.progress_path(mission_id)
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        dependency = next(
            row for row in doc["contrato"]["dependencias_fases"]
            if row["fase_id"] == "entender_rota"
        )
        dependency["substituicao_permitida"] = True
        path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        token, _ = self.ticket()
        substitution = {
            "fase_id": "entender_rota",
            "ator_original": "silva_elkwood",
            "ator_efetivo": "luath",
            "capacidade": "verificação institucional pela Night Watch",
            "fonte_capacidade": "estado/npcs/luath.yaml",
            "evidencia_capacidade": "grupo: City Guard / Night Watch",
            "evidencia_atuacao": LUATH_EVIDENCE,
        }
        fact = self.fact(
            phases={"entender_rota": "resolvida"},
            actors=["luath"],
            substitutions=[substitution],
            evidence=LUATH_EVIDENCE,
        )
        cronica.conclude(
            self.repo,
            token,
            self.transaction(mission_id, {"fatos_sidequest": [fact]}),
        )
        installed = yaml.safe_load(path.read_text(encoding="utf-8"))
        history = installed["estado"]["historico_recente"][-1]
        self.assertEqual(history["substituicoes"][0]["ator_efetivo"], "luath")
        self.assertEqual(history["substituicoes"][0]["fonte_ator"], "estado/npcs/luath.yaml")

    def test_substituto_proibido_ou_ausente_e_recusado(self):
        mission_id = self.accepted_mission()
        token, _ = self.ticket()
        substitution = {
            "fase_id": "entender_rota",
            "ator_original": "silva_elkwood",
            "ator_efetivo": "luath",
            "capacidade": "verificação institucional",
            "fonte_capacidade": "estado/npcs/luath.yaml",
            "evidencia_capacidade": "grupo: City Guard / Night Watch",
            "evidencia_atuacao": LUATH_EVIDENCE,
        }
        fact = self.fact(
            phases={"entender_rota": "resolvida"},
            actors=["luath"],
            substitutions=[substitution],
            evidence=LUATH_EVIDENCE,
        )
        with self.assertRaisesRegex(cronica.CronicaError, "não permite substituição"):
            cronica.conclude(
                self.repo,
                token,
                self.transaction(mission_id, {"fatos_sidequest": [fact]}),
            )

    def test_substituto_sem_presenca_canonica_e_recusado(self):
        mission_id = self.accepted_mission()
        path = self.progress_path(mission_id)
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        next(
            row for row in doc["contrato"]["dependencias_fases"]
            if row["fase_id"] == "entender_rota"
        )["substituicao_permitida"] = True
        path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        token, _ = self.ticket()
        substitution = {
            "fase_id": "entender_rota",
            "ator_original": "silva_elkwood",
            "ator_efetivo": "oficial_inexistente",
            "capacidade": "verificação institucional",
            "fonte_capacidade": "estado/npcs/luath.yaml",
            "evidencia_capacidade": "grupo: City Guard / Night Watch",
            "evidencia_atuacao": LUATH_EVIDENCE,
        }
        fact = self.fact(
            phases={"entender_rota": "resolvida"},
            actors=["oficial_inexistente"],
            substitutions=[substitution],
            evidence=LUATH_EVIDENCE,
        )
        with self.assertRaisesRegex(cronica.CronicaError, "presença canônica"):
            cronica.conclude(
                self.repo,
                token,
                self.transaction(mission_id, {"fatos_sidequest": [fact]}),
            )

    def test_substituto_sem_prova_de_capacidade_e_recusado(self):
        mission_id = self.accepted_mission()
        path = self.progress_path(mission_id)
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        next(
            row for row in doc["contrato"]["dependencias_fases"]
            if row["fase_id"] == "entender_rota"
        )["substituicao_permitida"] = True
        path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        token, _ = self.ticket()
        substitution = {
            "fase_id": "entender_rota",
            "ator_original": "silva_elkwood",
            "ator_efetivo": "luath",
            "capacidade": "verificação institucional",
            "fonte_capacidade": "estado/npcs/luath.yaml",
            "evidencia_capacidade": "capacidade que não existe no fragmento canônico",
            "evidencia_atuacao": LUATH_EVIDENCE,
        }
        fact = self.fact(
            phases={"entender_rota": "resolvida"},
            actors=["luath"],
            substitutions=[substitution],
            evidence=LUATH_EVIDENCE,
        )
        with self.assertRaisesRegex(cronica.CronicaError, "evidência literal não encontrada"):
            cronica.conclude(
                self.repo,
                token,
                self.transaction(mission_id, {"fatos_sidequest": [fact]}),
            )

    def test_prova_reservada_nao_vaza_na_projecao(self):
        mission_id = self.accepted_mission()
        token, _ = self.ticket()
        fact = self.fact(
            phases={"entender_rota": "resolvida"},
            actors=["silva_elkwood"],
        )
        cronica.conclude(
            self.repo,
            token,
            self.transaction(mission_id, {"fatos_sidequest": [fact]}),
        )
        projection = sidequests_ativas.project(self.repo)
        rendered = yaml.safe_dump(projection, allow_unicode=True, sort_keys=False)
        self.assertNotIn(TURN_EVIDENCE, rendered)
        self.assertNotIn("fonte_transacional", rendered)


class TransactionalProgressTerminalTest(TransactionalProgressFixture):
    def complete_fact(self) -> dict:
        return self.fact(
            phases={
                "entender_rota": "resolvida",
                "entrega_em_movimento": "resolvida",
            },
            success={"sucesso_01": "satisfeita", "sucesso_02": "satisfeita"},
            actors=["silva_elkwood", "mensageiro_cinza_task41"],
            fact_id="sucesso_factual_completo",
        )

    def test_condicao_parcial_nao_encerra_missao(self):
        mission_id = self.accepted_mission()
        token, _ = self.ticket()
        fact = self.fact(
            success={"sucesso_01": "satisfeita"},
            fact_id="sucesso_parcial",
        )
        result = cronica.conclude(
            self.repo,
            token,
            self.transaction(mission_id, {"fatos_sidequest": [fact]}),
        )
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        self.assertEqual(state["missoes"][mission_id]["estado"], "aceita")
        self.assertEqual(result["progresso_sidequests"]["terminais"], [])

    def test_sucesso_completo_encerra_e_recompensa_exatamente_uma_vez(self):
        mission_id = self.accepted_mission()
        token, _ = self.ticket()
        transaction = self.transaction(
            mission_id,
            {"fatos_sidequest": [self.complete_fact()]},
        )
        first = cronica.conclude(self.repo, token, transaction)
        second = cronica.conclude(self.repo, token, transaction)
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        rewards = recompensas_sidequest.status(self.repo, mission_id)
        self.assertEqual(state["missoes"][mission_id]["estado"], "concluida")
        self.assertEqual(rewards["recompensas"]["pagamento_silva"]["estado"], "obtida")
        self.assertEqual(len(transacoes.load_pending(self.repo)), 2)
        self.assertEqual(first["progresso_sidequests"], second["progresso_sidequests"])

    def test_sucesso_e_falha_simultaneos_falham_antes_do_writer(self):
        mission_id = self.accepted_mission()
        token, _ = self.ticket()
        fact = self.complete_fact()
        fact["condicoes_falha"] = {"falha_01": "satisfeita"}
        transaction = self.transaction(mission_id, {"fatos_sidequest": [fact]})
        with patch.object(cronica, "_conclude_base") as writer:
            with self.assertRaisesRegex(cronica.CronicaError, "simultaneamente"):
                cronica.conclude(self.repo, token, transaction)
        writer.assert_not_called()

    def test_falha_factual_encerra_e_emite_consequencia_uma_vez(self):
        mission_id = self.accepted_mission()
        token, _ = self.ticket()
        fact = self.fact(
            failure={"falha_01": "satisfeita"},
            fact_id="falha_factual_confirmada",
        )
        transaction = self.transaction(mission_id, {"fatos_sidequest": [fact]})
        first = cronica.conclude(self.repo, token, transaction)
        second = cronica.conclude(self.repo, token, transaction)
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        pending = [
            row
            for row in mundo.load_world_state(self.repo)["pendencias"]
            if row.get("tipo") == "resolver_sidequest"
            and row.get("missao") == mission_id
        ]
        self.assertEqual(state["missoes"][mission_id]["estado"], "falhada")
        self.assertEqual(len(pending), 1)
        self.assertEqual(first["progresso_sidequests"], second["progresso_sidequests"])

    def test_missao_terminal_nao_aceita_fato_novo_de_outro_turno(self):
        mission_id = self.accepted_mission()
        token, _ = self.ticket()
        first = self.transaction(mission_id, {"fatos_sidequest": [self.complete_fact()]})
        cronica.conclude(self.repo, token, first)
        second = copy.deepcopy(first)
        second["id"] = "tx-fato-posterior-ao-terminal"
        second["narracao"] += " Um fato posterior tenta reabrir a missão já encerrada."
        second[transactional_progress.TRANSACTION_KEY][0]["fatos_sidequest"][0]["id"] = (
            "fato_posterior_ao_terminal"
        )
        with self.assertRaisesRegex(cronica.CronicaError, "obsoleta"):
            cronica.conclude(self.repo, token, second)


class TransactionalProgressRecoveryTest(TransactionalProgressFixture):
    def test_ticket_obsoleto_por_mudanca_concorrente_falha_fechado(self):
        mission_id = self.accepted_mission()
        token, _ = self.ticket()
        path = self.progress_path(mission_id)
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        doc["estado"]["historico_recente"].append({"tipo": "mudanca_concorrente"})
        path.write_text(yaml.safe_dump(doc, allow_unicode=True, sort_keys=False), encoding="utf-8")
        fact = self.fact(phases={"entender_rota": "resolvida"}, actors=["silva_elkwood"])
        with self.assertRaisesRegex(cronica.CronicaError, "obsoleta"):
            cronica.conclude(
                self.repo,
                token,
                self.transaction(mission_id, {"fatos_sidequest": [fact]}),
            )
        self.assertEqual(transacoes.load_pending(self.repo), [])

    def test_queda_apos_writer_e_recuperada_sem_duplicar_transcricao(self):
        mission_id = self.accepted_mission()
        token, _ = self.ticket()
        fact = self.fact(phases={"entender_rota": "resolvida"}, actors=["silva_elkwood"])
        transaction = self.transaction(mission_id, {"fatos_sidequest": [fact]})
        original_install = transactional_progress.install
        with patch.object(
            cronica._sidequests49,
            "install",
            side_effect=transactional_progress.TransactionalSidequestProgressError(
                "queda sintética após writer"
            ),
        ):
            with self.assertRaisesRegex(cronica.CronicaError, "queda sintética"):
                cronica.conclude(self.repo, token, transaction)
        self.assertTrue((self.repo / transactional_progress.JOURNAL).is_file())
        result = original_install(
            self.repo,
            transactional_progress.prepare_conclusion(
                self.repo,
                ticket_id=cronica._core.ticket_id(token),
                ticket_meta=sidequests_ativas.ticket_meta(cronica.decode_ticket(token)),
                transaction=transaction,
            ),
            transaction=transaction,
        )
        transcript = (self.repo / "sessoes/015/transcricao.md").read_text(encoding="utf-8")
        self.assertEqual(transcript.count("tx-transactional-sidequest-progress"), 1)
        self.assertEqual(result["fatos_registrados"], 1)

    def test_journal_interrompido_bloqueia_novo_preparo(self):
        mission_id = self.accepted_mission()
        token, meta = self.ticket()
        fact = self.fact(phases={"entender_rota": "resolvida"}, actors=["silva_elkwood"])
        transaction = self.transaction(mission_id, {"fatos_sidequest": [fact]})
        transactional_progress.prepare_conclusion(
            self.repo,
            ticket_id=cronica._core.ticket_id(token),
            ticket_meta=meta,
            transaction=transaction,
        )
        with self.assertRaisesRegex(cronica.CronicaError, "repita o cronica concluir"):
            cronica.prepare(
                self.repo,
                scene_id="novo-turno-bloqueado",
                sidequest_signal=None,
            )
        check = transactional_progress.check(self.repo)
        self.assertFalse(check["ok"])
        self.assertTrue(check["journal_aberto"])

    def test_queda_depois_do_primeiro_byte_staged_e_recuperavel(self):
        mission_id = self.accepted_mission()
        token, meta = self.ticket()
        fact = self.fact(phases={"entender_rota": "resolvida"}, actors=["silva_elkwood"])
        transaction = self.transaction(mission_id, {"fatos_sidequest": [fact]})
        plan = transactional_progress.prepare_conclusion(
            self.repo,
            ticket_id=cronica._core.ticket_id(token),
            ticket_meta=meta,
            transaction=transaction,
        )
        transacoes_result = __import__("turno").register_transaction(
            self.repo, transactional_progress.writer_transaction(transaction)
        )
        self.assertEqual(transacoes_result["id"], "tx-transactional-sidequest-progress")
        with patch.object(transactional_progress, "_save", side_effect=OSError("queda staged")):
            with self.assertRaisesRegex(OSError, "queda staged"):
                transactional_progress.install(self.repo, plan, transaction=transaction)
        recovered = transactional_progress.install(
            self.repo,
            transactional_progress.prepare_conclusion(
                self.repo,
                ticket_id=cronica._core.ticket_id(token),
                ticket_meta=meta,
                transaction=transaction,
            ),
            transaction=transaction,
        )
        self.assertEqual(recovered["fatos_registrados"], 1)
        self.assertFalse((self.repo / transactional_progress.JOURNAL).exists())


if __name__ == "__main__":
    unittest.main()
