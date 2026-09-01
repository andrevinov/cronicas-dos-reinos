from __future__ import annotations

import copy
import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
TESTS = ROOT / "tests"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
if str(TESTS) not in sys.path:
    sys.path.insert(0, str(TESTS))

import barreira_mundo
import cronica
import migracao_sete_nomes as migration
import mundo
import oportunidades
import operacoes_concorrentes as operations
import reacoes_sidequest as reactions
import recompensas_sidequest
import resolver_fronteira
import sidequests_ativas
import transacoes
import test_transactional_sidequest_progress as transactional_cases


SNAPSHOT = ROOT / "tests/fixtures/historical/seven-names-session-017-end.yaml"
BUDGET = ROOT / "baseline/seven-names-migration-integration-orcamento.yaml"
INSTITUTIONAL_EVIDENCE = (
    "Luath confirmou diante de Ren que a ordem não possui autoridade institucional "
    "válida e que sua matriz prova a falsificação."
)
REACTION_KNOWLEDGE = (
    "A rede de Masao soube que a cativa e a matriz seriam transferidas pela Night Watch."
)
SECOND_REACTION_KNOWLEDGE = (
    "A rede de Masao soube que a Casa da Aurora Menor ainda protegia as sete crianças."
)
OPERATION_TARGET_EVIDENCE = (
    "Ren e a Night Watch iniciaram a transferência da cativa e da matriz pelas ruas da cidade."
)


class SevenNamesHistoricalFixture(transactional_cases.TransactionalProgressFixture):
    def setUp(self):
        super().setUp()
        self.snapshot = yaml.safe_load(SNAPSHOT.read_text(encoding="utf-8"))
        self.mission_id = self.snapshot["identidade"]["mission_id"]
        self.quest_id = self.snapshot["identidade"]["quest_id"]
        self._install_snapshot()

    def _install_snapshot(self) -> None:
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        state["missoes"] = {
            self.mission_id: copy.deepcopy(self.snapshot["oportunidade"]["missao"])
        }
        state["historico_recente"] = [
            {
                "tipo": "resposta_sidequest",
                "id": self.mission_id,
                "de": "oferecida",
                "para": "aceita",
                "em": {"data": "19 Eleasis, 1372 DR", "hora": "20:00"},
            }
        ]
        oportunidades.atomic(self.repo / oportunidades.STATE, state)
        documents = {
            f"narrador/sidequests-emergentes/quests/{self.quest_id}.yaml": self.snapshot["quest_task41"],
            f"narrador/sidequests-emergentes/recompensas/{self.quest_id}.yaml": self.snapshot["recompensa_task43"],
            f"narrador/sidequests-emergentes/stakes/{self.quest_id}.yaml": self.snapshot["contrato_task44"],
            f"narrador/sidequests-emergentes/progresso/{self.quest_id}.yaml": self.snapshot["progresso_task45"],
        }
        for rel, value in documents.items():
            self._yaml(rel, copy.deepcopy(value))
        for rel, lines in self.snapshot["fontes_canonicas"].items():
            path = self.repo / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        (self.repo / "runtime/contexto.yaml").write_text(
            "sessao:\n  numero: 17\n  status: em_sessao\n", encoding="utf-8"
        )
        session = self.repo / "sessoes/017"
        session.mkdir(parents=True, exist_ok=True)
        (session / "transcricao.md").write_text(
            "# Sessão 017 — continuação controlada da regressão histórica\n",
            encoding="utf-8",
        )
        now = mundo.parse_instant("20 Eleasis, 1372 DR", "00:31")
        self._yaml(
            mundo.TIME_PATH,
            {
                "schema_tempo": 1,
                "natureza": "tempo_atual",
                "data_atual": "20 Eleasis, 1372 DR",
                "hora_aproximada": "00:31",
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

    def progress_path(self) -> Path:
        return self.repo / f"narrador/sidequests-emergentes/progresso/{self.quest_id}.yaml"

    def task44_path(self) -> Path:
        return self.repo / f"narrador/sidequests-emergentes/stakes/{self.quest_id}.yaml"

    def apply_migration(self) -> dict:
        prepared = migration.dry_run(self.repo, self.quest_id)
        return migration.apply(
            self.repo, self.mission_id, prepared["preparacao_id"]
        )

    @staticmethod
    def _base_preparation(scene_id: str) -> dict:
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
                "preparacao_id": cronica._hot._neutral_preparation_id(request),
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

    def negative_prepare(self) -> dict:
        scene_id = "seven-names-institutional-verification"
        with patch.object(
            cronica._hot, "prepare", return_value=self._base_preparation(scene_id)
        ):
            return cronica.prepare(
                self.repo,
                scene_id=scene_id,
                sidequest_signal=None,
            )

    def institutional_transaction(self) -> dict:
        substitution = {
            "fase_id": "verificar_autoridade",
            "ator_original": "verificador_transferencias_sete_nomes",
            "ator_efetivo": "luath",
            "capacidade": "verificação institucional pela Night Watch",
            "fonte_capacidade": "estado/npcs/luath.yaml",
            "evidencia_capacidade": "grupo: City Guard / Night Watch",
            "evidencia_atuacao": INSTITUTIONAL_EVIDENCE,
        }
        fact = {
            "id": "luath_confirma_falsidade_institucional",
            "descricao": (
                "Luath concluiu institucionalmente que a ordem era falsa e vinculou "
                "a matriz preservada à falsificação."
            ),
            "evidencia": INSTITUTIONAL_EVIDENCE,
            "fases": {"verificar_autoridade": "resolvida"},
            "condicoes_sucesso": {"sucesso_01": "satisfeita"},
            "condicoes_falha": {},
            "atores": ["luath"],
            "substituicoes": [substitution],
            "visibilidade": "narrador",
        }
        return {
            "id": "s017-seven-names-institutional-verification",
            "narracao": (
                "Luath termina o exame formal da matriz e dos documentos. "
                + INSTITUTIONAL_EVIDENCE
            ),
            "resumo": "A falsidade da ordem foi confirmada por autoridade competente antes do prazo.",
            "modo": "interacao",
            "deltas": [],
            "progresso_sidequests": [
                {"mission_id": self.mission_id, "fatos_sidequest": [fact]}
            ],
        }

    def _install_reaction_knowledge(self) -> dict[str, str]:
        rel = "sessoes/017/reacao-sete-nomes-fixture.md"
        source = self.repo / rel
        source.write_text(
            "\n".join(
                [
                    REACTION_KNOWLEDGE,
                    SECOND_REACTION_KNOWLEDGE,
                    OPERATION_TARGET_EVIDENCE,
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        agent_path = self.repo / "narrador/agentes/masao_hirasawa.yaml"
        agent = yaml.safe_load(agent_path.read_text(encoding="utf-8"))
        agent["conhecimento"].extend(
            [
                {
                    "id": "provas_em_transferencia",
                    "fato": "A cativa e a matriz seriam transferidas pela Night Watch.",
                    "fonte": rel,
                    "evidencia": REACTION_KNOWLEDGE,
                },
                {
                    "id": "criancas_na_casa_aurora",
                    "fato": "A Casa da Aurora Menor ainda protegia as sete crianças.",
                    "fonte": rel,
                    "evidencia": SECOND_REACTION_KNOWLEDGE,
                },
            ]
        )
        if rel not in agent["fontes_canonicas"]:
            agent["fontes_canonicas"].append(rel)
        self._yaml("narrador/agentes/masao_hirasawa.yaml", agent)
        return {"fonte": rel, "evidencia": OPERATION_TARGET_EVIDENCE}

    @staticmethod
    def _alternative(
        *,
        alternative_id: str,
        capability: str,
        knowledge: str,
        target_id: str,
        target_type: str,
        resource: str,
        kind: str,
        group: str,
    ) -> dict:
        return {
            "id": alternative_id,
            "tipo": kind,
            "titulo": "Resposta compartimentada à exposição documental",
            "objetivo": "Reduzir a utilidade institucional das provas sem expor a cadeia de comando.",
            "resultado_possivel": "Uma célula tenta alcançar o alvo usando somente recursos e conhecimento já registrados.",
            "capacidade_id": capability,
            "conhecimentos_requeridos": [knowledge],
            "alvos": [{"id": target_id, "tipo": target_type}],
            "recursos_exigidos": [resource],
            "exige_presenca_fisica": False,
            "grupo_exclusividade": group,
            "gravidade": "moderada",
            "reversibilidade": "reversivel",
            "classe_impacto": "juridico",
            "bloqueios_causais": ["O alvo deixa de estar acessível antes do compromisso."],
        }

    def _reaction_proposal(
        self,
        *,
        fact_id: str,
        trigger_type: str,
        alternatives: list[dict],
    ) -> dict:
        now = mundo.parse_instant("20 Eleasis, 1372 DR", "00:31")
        return {
            "classificacao": "reacao_mundo",
            "gatilho": {"tipo": trigger_type, "fato_id": fact_id},
            "antagonista_id": "masao_hirasawa",
            "alternativas": alternatives,
            "janela": {
                "minimo": mundo.instant_parts(now),
                "maximo": mundo.instant_parts(mundo.WorldInstant(now.minute + 120)),
                "condicao": "As provas e protegidos permanecem alcançáveis dentro da janela registrada.",
            },
            "vinculo_canonico": None,
            "motivo": "Os fatos novos expõem a célula documental e justificam reavaliação separada da missão encerrada.",
        }

    @staticmethod
    def _mechanics(proof: dict[str, str], target: str) -> dict:
        return {
            "modo": "nenhuma",
            "alvo": target,
            "nivel_alvo": 7,
            "recursos_alvo": "gastos",
            "prova_alvo": proof,
            "adversario_referencia": None,
            "composicao": [],
            "aliados_presentes": [],
            "terreno": "neutra",
            "iniciativa": "neutra",
            "surpresa": False,
            "objetivo_tatico": "Preservar a ação do mundo sem presumir que a pressão se tornará combate.",
            "rotas_retirada": [],
            "capacidade_exclusiva": False,
        }


class SevenNamesMigrationTest(SevenNamesHistoricalFixture):
    def test_snapshot_declara_natureza_instante_motivo_e_limite_historico(self):
        self.assertEqual(self.snapshot["natureza"], "snapshot_historico_isolado")
        self.assertEqual(self.snapshot["instante"]["sessao"], 17)
        self.assertIn("regressão", self.snapshot["motivo"])
        self.assertIn("não descreve obrigatoriamente", self.snapshot["aviso"])

    def test_dry_run_por_ambos_ids_e_read_only(self):
        before = {
            path.relative_to(self.repo).as_posix(): path.read_bytes()
            for path in self.repo.rglob("*")
            if path.is_file()
        }
        by_mission = migration.dry_run(self.repo, self.mission_id)
        by_quest = migration.dry_run(self.repo, self.quest_id)
        after = {
            path.relative_to(self.repo).as_posix(): path.read_bytes()
            for path in self.repo.rglob("*")
            if path.is_file()
        }
        self.assertEqual(before, after)
        self.assertEqual(by_mission["preparacao_id"], by_quest["preparacao_id"])
        self.assertEqual(by_mission["fase_institucional"], "possivel")
        self.assertEqual(by_mission["condicoes_sucesso"]["sucesso_02"], "satisfeita")
        self.assertIsNone(by_mission["terminal"])

    def test_aplicacao_preserva_contrato_adversarial_e_nao_materializa_reacao(self):
        task44_before = self.task44_path().read_bytes()
        result = self.apply_migration()
        progress = yaml.safe_load(self.progress_path().read_text(encoding="utf-8"))
        self.assertEqual(self.task44_path().read_bytes(), task44_before)
        self.assertEqual(result["fase_institucional"], "possivel")
        self.assertIsNone(progress["estado"]["terminal"])
        self.assertTrue(progress["estado"]["necessita_reavaliacao_reacao"]["estado"])
        self.assertFalse((self.repo / reactions.ROOT).exists())
        self.assertTrue((self.repo / migration.RECEIPT).is_file())

    def test_retry_e_recovery_sao_idempotentes(self):
        prepared = migration.dry_run(self.repo, self.mission_id)
        with self.assertRaisesRegex(migration.SevenNamesMigrationError, "falha simulada"):
            migration.apply(
                self.repo,
                self.mission_id,
                prepared["preparacao_id"],
                fail_after=1,
            )
        self.assertTrue((self.repo / migration.JOURNAL).is_file())
        recovered = migration.apply(
            self.repo, self.mission_id, prepared["preparacao_id"]
        )
        repeated = migration.apply(
            self.repo, self.quest_id, prepared["preparacao_id"]
        )
        self.assertEqual(recovered["resultado"], "recuperada")
        self.assertEqual(repeated["resultado"], "ja_aplicada")
        self.assertFalse((self.repo / migration.JOURNAL).exists())

    def test_evidencia_nao_literal_falha_antes_de_escrita(self):
        source = self.repo / "sessoes/017/resumo.md"
        source.write_text("Fonte histórica deliberadamente incompleta.\n", encoding="utf-8")
        with self.assertRaisesRegex(migration.SevenNamesMigrationError, "evidência literal"):
            migration.dry_run(self.repo, self.mission_id)
        self.assertFalse((self.repo / migration.RECEIPT).exists())
        self.assertFalse((self.repo / migration.JOURNAL).exists())


class SevenNamesEndToEndRegressionTest(SevenNamesHistoricalFixture):
    def test_desvio_pela_calaria_chega_a_terminal_reacao_e_operacoes_separadas(self):
        self.apply_migration()
        task44_before = self.task44_path().read_bytes()

        prepared = self.negative_prepare()
        self.assertEqual(prepared["sidequests_ativas"]["quantidade"], 1)
        projected = prepared["sidequests_ativas"]["missoes"][0]
        self.assertEqual(projected["mission_id"], self.mission_id)
        self.assertEqual(projected["fases"]["verificar_autoridade"], "possivel")

        transaction = self.institutional_transaction()
        first = cronica.conclude(self.repo, prepared["ticket"], transaction)
        second = cronica.conclude(self.repo, prepared["ticket"], transaction)
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        progress = yaml.safe_load(self.progress_path().read_text(encoding="utf-8"))
        rewards = recompensas_sidequest.status(self.repo, self.mission_id)
        self.assertEqual(state["missoes"][self.mission_id]["estado"], "concluida")
        self.assertEqual(progress["estado"]["terminal"]["resultado"], "concluida")
        self.assertEqual(
            progress["estado"]["fatos"]["luath_confirma_falsidade_institucional"]
            ["substituicoes"][0]["ator_efetivo"],
            "luath",
        )
        self.assertEqual(
            rewards["recompensas"]["contato_verificador_transferencias"]["estado"],
            "obtida",
        )
        self.assertEqual(first["progresso_sidequests"], second["progresso_sidequests"])
        self.assertEqual(self.task44_path().read_bytes(), task44_before)

        target_proof = self._install_reaction_knowledge()
        valid_transfer = self._alternative(
            alternative_id="fraude_na_transferencia",
            capability="compartimentar_pressao_sobre_ren",
            knowledge="provas_em_transferencia",
            target_id="matriz_sete_nomes",
            target_type="recurso",
            resource="selos falsos, documentos, carga e pressão sobre testemunhas",
            kind="juridica",
            group="transferencia",
        )
        blocked = self._alternative(
            alternative_id="metodo_sem_capacidade",
            capability="teleporte_inventado",
            knowledge="provas_em_transferencia",
            target_id="matriz_sete_nomes",
            target_type="recurso",
            resource="Red Sail, Narwhal, rotas baixas e aquisição de imóveis",
            kind="logistica",
            group="impossivel",
        )
        proposal_a = self._reaction_proposal(
            fact_id="luath_confirma_falsidade_institucional",
            trigger_type="terminal_sucesso",
            alternatives=[valid_transfer, blocked],
        )
        reaction_a_prepared = reactions.prepare(
            self.repo, self.mission_id, proposal_a
        )
        self.assertEqual(reaction_a_prepared["alternativas_elegiveis"], ["fraude_na_transferencia"])
        self.assertTrue(reaction_a_prepared["alternativas_bloqueadas"])
        reaction_a = reactions.materialize(
            self.repo,
            self.mission_id,
            proposal_a,
            preparation_id=reaction_a_prepared["preparacao_id"],
        )

        valid_house = self._alternative(
            alternative_id="pressao_sobre_abrigo",
            capability="saturar_capacidade_de_resposta",
            knowledge="criancas_na_casa_aurora",
            target_id="casa_aurora_menor",
            target_type="local",
            resource="intermediários locais e autoridades corrompidas",
            kind="social",
            group="abrigo",
        )
        proposal_b = self._reaction_proposal(
            fact_id="confissao_cinza_azul_vincula_masao",
            trigger_type="progresso_excepcional",
            alternatives=[valid_house],
        )
        reaction_b_prepared = reactions.prepare(
            self.repo, self.mission_id, proposal_b
        )
        reaction_b = reactions.materialize(
            self.repo,
            self.mission_id,
            proposal_b,
            preparation_id=reaction_b_prepared["preparacao_id"],
        )
        self.assertNotEqual(reaction_a["reaction_id"], reaction_b["reaction_id"])
        self.assertEqual(self.task44_path().read_bytes(), task44_before)

        operation_rows = [
            {
                "id": "interceptar_transferencia_sete_nomes",
                "reaction_id": reaction_a["reaction_id"],
                "alternative_id": "fraude_na_transferencia",
                "alvo": {"id": "matriz_sete_nomes", "tipo": "recurso"},
                "local": "rua_da_guarda",
                "objetivo": "Tomar ou invalidar a matriz durante a transferência institucional.",
                "celula_id": None,
                "atores": ["masao_hirasawa"],
                "recursos": ["selos falsos, documentos, carga e pressão sobre testemunhas"],
                "dependencias": ["A matriz permanece em transferência pela cidade."],
                "bloqueios_causais": ["A matriz chega ao cofre antes do início da operação."],
                "sinais_perceptiveis": ["Uma ordem contraditória tenta interromper a escolta."],
                "mecanica": self._mechanics(target_proof, "ren"),
            },
            {
                "id": "pressionar_casa_aurora_sete_nomes",
                "reaction_id": reaction_b["reaction_id"],
                "alternative_id": "pressao_sobre_abrigo",
                "alvo": {"id": "casa_aurora_menor", "tipo": "local"},
                "local": "casa_aurora_menor",
                "objetivo": "Saturar a resposta institucional ao redor do abrigo.",
                "celula_id": None,
                "atores": ["masao_hirasawa"],
                "recursos": ["intermediários locais e autoridades corrompidas"],
                "dependencias": ["As crianças permanecem protegidas no abrigo."],
                "bloqueios_causais": ["As crianças deixam o abrigo antes da janela comum."],
                "sinais_perceptiveis": ["Mensagens administrativas conflitantes chegam ao abrigo."],
                "mecanica": self._mechanics(target_proof, "guardas_do_abrigo"),
            },
        ]
        now = mundo.parse_instant("20 Eleasis, 1372 DR", "00:31")
        group_proposal = {
            "janela": {
                "minimo": mundo.instant_parts(now),
                "maximo": mundo.instant_parts(mundo.WorldInstant(now.minute + 120)),
                "condicao": "Duas frentes e recursos distintos permanecem disponíveis na mesma janela.",
            },
            "simultaneidade": "As duas operações podem começar sem esperar uma escolha de Ren.",
            "operacoes": operation_rows,
            "canais": [],
            "motivo": "As frentes usam recursos exclusivos distintos e preservam resultados independentes.",
        }
        group_prepared = operations.prepare(self.repo, group_proposal)
        group = operations.materialize(
            self.repo, group_proposal, group_prepared["preparacao_id"]
        )
        batch = resolver_fronteira.prepare_batch(self.repo)
        item = next(
            row
            for row in batch["itens"]
            if row.get("grupo_operacoes_id") == group["grupo_operacoes_id"]
        )
        payload = {
            "lote_id": batch["lote_id"],
            "grupos_operacoes": [
                {"id": item["id"], "token": item["token"], "bloqueios": {}}
            ],
        }
        committed = resolver_fronteira.apply_batch(self.repo, payload)
        retry = resolver_fronteira.apply_batch(self.repo, payload)
        group_state = operations._load_state(self.repo)
        reservations = group_state["reservas_exclusivas"]
        self.assertEqual(len(reservations), 2)
        self.assertEqual(len(set(reservations)), 2)
        self.assertEqual(
            committed["grupos_comprometidos"][0]["operacoes_comprometidas"],
            ["interceptar_transferencia_sete_nomes", "pressionar_casa_aurora_sete_nomes"],
        )
        self.assertEqual(len(retry["ja_aplicadas"]), 1)
        self.assertEqual(self.task44_path().read_bytes(), task44_before)
        self.assertEqual(len(transacoes.load_pending(self.repo)), 2)


class SevenNamesRepositoryContractTest(unittest.TestCase):
    def test_snapshot_e_orcamento_sao_historicos_e_o_check_real_e_read_only(self):
        snapshot = yaml.safe_load(SNAPSHOT.read_text(encoding="utf-8"))
        budget = yaml.safe_load(BUDGET.read_text(encoding="utf-8"))
        self.assertEqual(snapshot["natureza"], "snapshot_historico_isolado")
        self.assertEqual(budget["natureza"], "contrato_de_regressao")
        limits = budget["limites"]
        self.assertLessEqual(SNAPSHOT.stat().st_size, limits["snapshot_historico_bytes_max"])
        self.assertEqual(limits["fatos_historicos_importados_max"], len(migration.FACTS))
        self.assertEqual(limits["rng_novo"], 0)
        self.assertEqual(limits["scheduler_novo"], 0)
        self.assertEqual(limits["scans_globais"], 0)
        task44 = ROOT / "narrador/sidequests-emergentes/stakes/qse-c721ace29e628024.yaml"
        before = hashlib.sha256(task44.read_bytes()).hexdigest()
        result = migration.check(ROOT)
        after = hashlib.sha256(task44.read_bytes()).hexdigest()
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(before, after)
        self.assertEqual(result["contrato"]["rng_novo"], 0)
        self.assertEqual(result["contrato"]["scheduler_novo"], 0)
        self.assertEqual(result["contrato"]["scan_global"], 0)


if __name__ == "__main__":
    unittest.main()
