from __future__ import annotations

import copy
import hashlib
import json
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
import reacoes_sidequest as reactions
import rede_protegida
import resolver_fronteira


MISSION_ID = "sqe-1111111111111111"
QUEST_ID = "qse-2222222222222222"
ACTOR_ID = "rede_cinzenta"
FACT_ID = "arquivo_preservado"
SECOND_FACT_ID = "testemunha_preservada"
FACT_EVIDENCE = "O arquivo foi preservado e expôs a rota usada pela célula clandestina."
SECOND_EVIDENCE = "A testemunha chegou a custódia segura e confirmou a cadeia operacional."
KNOWLEDGE_EVIDENCE = "A rede soube que o arquivo público contém a rota da célula."
RESULT_EVIDENCE = "A operação terminou e seus recursos deixaram de estar comprometidos."


def _digest(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SidequestReactionFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.now = mundo.parse_instant("10 Eleasis, 1372 DR", "18:00")
        self._write_sources()
        self._write_world()
        self._write_opportunities()
        self._write_agent()
        self._write_protected_policy()
        self._write_mission(completed=True)

    def tearDown(self):
        self.temp.cleanup()

    def yaml(self, rel: str | Path, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _write_sources(self) -> None:
        path = self.repo / "sessoes/001/fatos.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "\n".join(
                [FACT_EVIDENCE, SECOND_EVIDENCE, KNOWLEDGE_EVIDENCE, RESULT_EVIDENCE]
            )
            + "\n",
            encoding="utf-8",
        )

    def _write_world(self) -> None:
        parts = mundo.instant_parts(self.now)
        self.yaml(
            mundo.TIME_PATH,
            {
                "schema_tempo": 1,
                "natureza": "tempo_atual",
                "data_atual": parts["data"],
                "hora_aproximada": parts["hora"],
            },
        )
        self.yaml(
            mundo.AGENDA_PATH,
            {
                "schema_agenda_mundo": 1,
                "natureza": "reservado",
                "hora_amanhecer": "06:00",
                "reavaliacoes": {},
                "agendamentos": [],
            },
        )
        self.yaml(
            mundo.WORLD_STATE_PATH,
            {
                "schema_estado_mundo": 1,
                "natureza": "controle_reservado",
                "processado_ate": parts,
                "pendencias": [],
                "concluidas_recentes": [],
            },
        )
        barreira_mundo.sync(self.repo)

    def _write_opportunities(self) -> None:
        cards = [
            {"id": f"nada_{position:02d}", "resultado": "nada"}
            for position in range(1, 9)
        ] + [
            {"id": f"oportunidade_{position:02d}", "resultado": "oportunidade"}
            for position in range(1, 3)
        ]
        self.yaml(
            oportunidades.INDEX,
            {
                "schema_oportunidades": 1,
                "natureza": "reservado",
                "semente": "fixture-reacoes-causais",
                "gate": {"modo": "baralho_sem_reposicao_sha256", "fichas": cards},
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

    def _write_agent(self, *, presence="distribuida", local_rule="estrutura_local") -> None:
        self.yaml(
            "narrador/agentes/index.yaml",
            {
                "schema_agentes": 2,
                "natureza": "reservado",
                "agentes": {
                    ACTOR_ID: {
                        "nome": "Rede Cinzenta",
                        "tipo": "faccao",
                        "estado": "ativo",
                        "presenca": presence,
                        "atuacao_local": local_rule,
                        "arquivo": f"narrador/agentes/{ACTOR_ID}.yaml",
                    }
                },
            },
        )
        concrete = presence in {"presente", "presente_oculto", "fora_da_area", "em_viagem"}
        self.yaml(
            f"narrador/agentes/{ACTOR_ID}.yaml",
            {
                "schema_agente": 2,
                "natureza": "reservado",
                "id": ACTOR_ID,
                "nome": "Rede Cinzenta",
                "tipo": "faccao",
                "estado": "ativo",
                "objetivo_atual": "Impedir que a rota clandestina seja reconstruída por autoridades locais.",
                "recursos": ["célula documental", "equipe de extração"],
                "restricoes": ["evitar exposição pública ampla"],
                "fontes_canonicas": ["sessoes/001/fatos.md"],
                "presenca": {
                    "referencia": "Ravens Bluff",
                    "estado": presence,
                    "detalhe": "A rede opera na cidade conforme sua presença registrada.",
                    "fonte": "sessoes/001/fatos.md" if concrete else None,
                    "evidencia": KNOWLEDGE_EVIDENCE if concrete else None,
                },
                "mobilidade": {
                    "estado": "sem_deslocamento_registrado",
                    "origem": None,
                    "destino": None,
                    "prazo": None,
                },
                "atuacao_local": {
                    "regra": local_rule,
                    "escopo": "Ravens Bluff",
                    "observacao": "A estrutura pode agir apenas dentro do alcance canônico registrado.",
                },
                "conhecimento": [
                    {
                        "id": "arquivo_revelado",
                        "fato": "O arquivo público contém a rota da célula.",
                        "fonte": "sessoes/001/fatos.md",
                        "evidencia": KNOWLEDGE_EVIDENCE,
                    }
                ],
                "plano_atual": {
                    "estado": "requer_reavaliacao",
                    "acao": "Escolher um método compatível com exposição e recursos.",
                    "prazo_ou_oportunidade": "Depois que a rota se tornou conhecida.",
                },
                "metodos_operacionais": {
                    "proteger_rota": [
                        {
                            "id": "fraudar_ordem",
                            "abordagem": "Produzir uma ordem contraditória por intermediários.",
                            "modalidade": "indireta",
                            "tags": ["documentos"],
                        },
                        {
                            "id": "extrair_registro",
                            "abordagem": "Remover furtivamente o registro exposto.",
                            "modalidade": "mista",
                            "tags": ["extracao"],
                        },
                    ]
                },
            },
        )

    def _write_protected_policy(self) -> None:
        dst = self.repo / adversarial.POLICY
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / adversarial.POLICY, dst)
        policy = yaml.safe_load((ROOT / rede_protegida.INDEX).read_text(encoding="utf-8"))
        policy["membros"] = {
            "guardiao_central": {
                "nome": "Guardião Central",
                "grupo": "nucleo_apoio",
                "fonte": "estado/relacoes/guardiao_central.yaml",
            }
        }
        self.yaml(rede_protegida.INDEX, policy)

    def _fact(self, fact_id: str, evidence: str) -> dict:
        return {
            "id": fact_id,
            "descricao": "Um fato verificável alterou a exposição material da rede.",
            "prova": {"fonte": "sessoes/001/fatos.md", "evidencia": evidence},
            "fases": {},
            "condicoes_sucesso": {},
            "condicoes_falha": {},
            "canonizado_em": mundo.instant_parts(self.now),
        }

    def _write_mission(self, *, completed: bool) -> None:
        quest_rel = f"narrador/sidequests-emergentes/quests/{QUEST_ID}.yaml"
        progress_rel = f"narrador/sidequests-emergentes/progresso/{QUEST_ID}.yaml"
        adversarial_rel = f"narrador/sidequests-emergentes/stakes/{QUEST_ID}.yaml"
        mission = {
            "id": MISSION_ID,
            "estado": "concluida" if completed else "aceita",
            "origem": "sidequest_emergente",
            "quest_id": QUEST_ID,
            "arquivo": quest_rel,
            "progresso_sidequest": progress_rel,
            "contrato_adversarial": adversarial_rel,
        }
        self.yaml(
            oportunidades.STATE,
            {
                "schema_estado_oportunidades": 1,
                "natureza": "controle_reservado",
                "gate": {"ciclo": 0, "restantes": [], "sorteios": 0},
                "cooldown_ate": None,
                "pendencias_avaliacao": {},
                "missoes": {MISSION_ID: mission},
                "sementes_consumidas": [],
                "encontros_recentes": [],
                "historico_recente": [],
            },
        )
        self.yaml(
            quest_rel,
            {
                "schema_sidequest_emergente": 2,
                "natureza": "reservado",
                "id": QUEST_ID,
                "titulo": "O Arquivo Exposto",
            },
        )
        terminal = (
            {
                "resultado": "concluida",
                "gatilho": "sucesso",
                "em": mundo.instant_parts(self.now),
                "motivo": "condições factuais satisfeitas",
                "pendencia_id": None,
            }
            if completed
            else None
        )
        self.yaml(
            progress_rel,
            {
                "schema_progressao_sidequest": 1,
                "natureza": "reservado",
                "mission_id": MISSION_ID,
                "quest_id": QUEST_ID,
                "estado": {
                    "fatos": {
                        FACT_ID: self._fact(FACT_ID, FACT_EVIDENCE),
                        SECOND_FACT_ID: self._fact(SECOND_FACT_ID, SECOND_EVIDENCE),
                    },
                    "terminal": terminal,
                },
            },
        )
        task44_contract = {"origem": "contrato adversarial congelado antes do aceite"}
        self.yaml(
            adversarial_rel,
            {
                "schema_integridade_adversarial": 1,
                "natureza": "reservado",
                "quest_id": QUEST_ID,
                "mission_id": MISSION_ID,
                "preparacao_id": "adv-prep-sintetica",
                "contrato_digest": _digest(task44_contract),
                "contrato": task44_contract,
                "guardrails": {},
                "historico_recente": [],
            },
        )

    def alternative(
        self,
        *,
        alternative_id="ordem_contraditoria",
        capability="fraudar_ordem",
        knowledge=None,
        target_id="arquivo_publico",
        target_type="informacao",
        resource="célula documental",
        physical=False,
        group="metodo_principal",
        severity="moderada",
        reversibility="reversivel",
        impact="juridico",
    ):
        return {
            "id": alternative_id,
            "tipo": "juridica" if not physical else "furtiva",
            "titulo": "Operação sobre o arquivo exposto",
            "objetivo": "Impedir que a cadeia documental produza nova exposição.",
            "resultado_possivel": "A rede tenta neutralizar a utilidade do arquivo por um método previamente autorizado.",
            "capacidade_id": capability,
            "conhecimentos_requeridos": knowledge or ["arquivo_revelado"],
            "alvos": [{"id": target_id, "tipo": target_type}],
            "recursos_exigidos": [resource],
            "exige_presenca_fisica": physical,
            "grupo_exclusividade": group,
            "gravidade": severity,
            "reversibilidade": reversibility,
            "classe_impacto": impact,
            "bloqueios_causais": ["O arquivo deixa de estar acessível antes do compromisso."],
        }

    def proposal(
        self,
        *,
        classification="reacao_mundo",
        trigger_type="terminal_sucesso",
        fact_id=FACT_ID,
        alternatives=None,
        link=None,
        minimum=None,
    ):
        if classification == "sem_reacao":
            return {
                "classificacao": classification,
                "gatilho": {"tipo": trigger_type, "fato_id": fact_id},
                "motivo": "Nenhuma ação material é sustentada pelos fatos e capacidades atuais.",
            }
        minimum = minimum or self.now
        return {
            "classificacao": classification,
            "gatilho": {"tipo": trigger_type, "fato_id": fact_id},
            "antagonista_id": ACTOR_ID,
            "alternativas": alternatives or [self.alternative()],
            "janela": {
                "minimo": mundo.instant_parts(minimum),
                "maximo": mundo.instant_parts(mundo.WorldInstant(minimum.minute + 240)),
                "condicao": "A rota exposta permanece alcançável e os recursos continuam disponíveis.",
            },
            "vinculo_canonico": link,
            "motivo": "O fato novo expõe a infraestrutura e sustenta resposta autônoma proporcional.",
        }

    def materialize(self, proposal=None):
        proposal = proposal or self.proposal()
        prepared = reactions.prepare(self.repo, MISSION_ID, proposal)
        return reactions.materialize(
            self.repo,
            MISSION_ID,
            proposal,
            preparation_id=prepared["preparacao_id"],
        )


class SidequestReactionOriginTest(SidequestReactionFixture):
    def test_sucesso_gera_contrato_sem_reabrir_missao_ou_alterar_stakes_originais(self):
        task44_path = self.repo / f"narrador/sidequests-emergentes/stakes/{QUEST_ID}.yaml"
        before = task44_path.read_bytes()
        result = self.materialize()
        mission = oportunidades.load_state(
            self.repo, oportunidades.load_index(self.repo)
        )["missoes"][MISSION_ID]
        self.assertEqual(mission["estado"], "concluida")
        self.assertEqual(task44_path.read_bytes(), before)
        self.assertFalse(result["missao_reaberta"])
        self.assertTrue((self.repo / reactions._contract_rel(result["reaction_id"])).is_file())

    def test_progresso_excepcional_declarado_tambem_pode_ser_gatilho(self):
        self._write_mission(completed=False)
        proposal = self.proposal(trigger_type="progresso_excepcional")
        result = self.materialize(proposal)
        self.assertEqual(result["estado"], "elegivel")
        mission = oportunidades.load_state(
            self.repo, oportunidades.load_index(self.repo)
        )["missoes"][MISSION_ID]
        self.assertEqual(mission["estado"], "aceita")

    def test_planejamento_reservado_nao_prova_gatilho(self):
        progress_path = self.repo / f"narrador/sidequests-emergentes/progresso/{QUEST_ID}.yaml"
        progress = yaml.safe_load(progress_path.read_text(encoding="utf-8"))
        reserved = self.repo / "narrador/sidequests-emergentes/provas/futura.md"
        reserved.parent.mkdir(parents=True, exist_ok=True)
        reserved.write_text(FACT_EVIDENCE + "\n", encoding="utf-8")
        progress["estado"]["fatos"][FACT_ID]["prova"]["fonte"] = reserved.relative_to(self.repo).as_posix()
        self.yaml(progress_path.relative_to(self.repo), progress)
        with self.assertRaisesRegex(reactions.SidequestReactionError, "planejamento reservado"):
            reactions.prepare(self.repo, MISSION_ID, self.proposal())


class SidequestReactionGateTest(SidequestReactionFixture):
    def _one_valid_one_blocked(self, blocked):
        prepared = reactions.prepare(
            self.repo,
            MISSION_ID,
            self.proposal(alternatives=[self.alternative(), blocked]),
        )
        self.assertEqual(prepared["alternativas_elegiveis"], ["ordem_contraditoria"])
        self.assertEqual(len(prepared["alternativas_bloqueadas"]), 1)
        return prepared["alternativas_bloqueadas"][0]["motivos"]

    def test_capacidade_ausente_bloqueia_somente_a_alternativa(self):
        blocked = self.alternative(
            alternative_id="metodo_inventado",
            capability="capacidade_inexistente",
            resource="equipe de extração",
            group="outra_rota",
        )
        reasons = self._one_valid_one_blocked(blocked)
        self.assertIn("capacidade_nao_disponivel", reasons)

    def test_conhecimento_ausente_bloqueia_acao_sobre_alvo_desconhecido(self):
        blocked = self.alternative(
            alternative_id="alvo_desconhecido",
            knowledge=["segredo_nao_adquirido"],
            resource="equipe de extração",
            group="outra_rota",
        )
        reasons = self._one_valid_one_blocked(blocked)
        self.assertTrue(any(reason.startswith("conhecimento_canonico_ausente") for reason in reasons))

    def test_presenca_fisica_incompativel_bloqueia_ator_local(self):
        self._write_agent(presence="fora_da_area", local_rule="exige_presenca_fisica")
        blocked = self.alternative(
            alternative_id="extracao_local",
            capability="extrair_registro",
            resource="equipe de extração",
            physical=True,
            group="outra_rota",
        )
        reasons = self._one_valid_one_blocked(blocked)
        self.assertIn("presenca_fisica_incompativel", reasons)

    def test_direcao_isolada_nao_substitui_capacidade(self):
        bad = self.alternative(capability="capacidade_inexistente")
        proposal = self.proposal(
            alternatives=[bad],
            link={"tipo": "direcao", "id": "destino_canonico"},
        )
        with self.assertRaisesRegex(reactions.SidequestReactionError, "capacidade"):
            reactions.prepare(self.repo, MISSION_ID, proposal)

    def test_protected_core_e_gravidade_continuam_no_gate_adversarial(self):
        grave = self.alternative(
            target_id="guardiao_central",
            target_type="npc",
            severity="grave",
            reversibility="irreversivel",
            impact="vida",
        )
        with self.assertRaisesRegex(reactions.SidequestReactionError, "autoridade"):
            reactions.prepare(self.repo, MISSION_ID, self.proposal(alternatives=[grave]))


class SidequestReactionLifecycleTest(SidequestReactionFixture):
    def test_reacao_mundo_entra_na_fila_e_fronteira_nao_aceita_noop(self):
        result = self.materialize()
        world = mundo.load_world_state(self.repo)
        self.assertEqual(len(world["pendencias"]), 1)
        self.assertEqual(world["pendencias"][0]["reaction_id"], result["reaction_id"])
        batch = resolver_fronteira.prepare_batch(self.repo)
        item = batch["itens"][0]
        self.assertEqual(item["classificacao"], "requer_resolucao_reacao")
        with self.assertRaisesRegex(resolver_fronteira.BatchBoundaryError, "não aceita sem_mudanca"):
            resolver_fronteira.apply_batch(
                self.repo,
                {
                    "lote_id": batch["lote_id"],
                    "sem_mudanca": [
                        {"id": item["id"], "token": item["token"], "nota": "A reação seria ignorada sem causa material."}
                    ],
                },
            )

    def test_oportunidade_sucessora_nao_cria_sidequest_nem_pendencia(self):
        opportunities_before = (self.repo / oportunidades.STATE).read_bytes()
        result = self.materialize(self.proposal(classification="oportunidade_sucessora"))
        self.assertEqual(result["estado"], "planejada")
        self.assertEqual((self.repo / oportunidades.STATE).read_bytes(), opportunities_before)
        self.assertEqual(mundo.load_world_state(self.repo)["pendencias"], [])

    def test_sem_reacao_nao_cria_arquivo_estado_ou_pendencia(self):
        before = mundo.load_world_state(self.repo)
        result = self.materialize(self.proposal(classification="sem_reacao"))
        self.assertEqual(result["resultado"], "sem_reacao")
        self.assertFalse((self.repo / reactions.INDEX).exists())
        self.assertFalse((self.repo / reactions.STATE).exists())
        self.assertEqual(mundo.load_world_state(self.repo), before)

    def test_replay_nao_duplica_contrato_ou_pendencia(self):
        proposal = self.proposal()
        first = self.materialize(proposal)
        second = self.materialize(proposal)
        self.assertEqual(first["reaction_id"], second["reaction_id"])
        self.assertEqual(second["resultado"], "ja_materializada")
        self.assertEqual(len(mundo.load_world_state(self.repo)["pendencias"]), 1)
        self.assertEqual(len(reactions._load_index(self.repo)["reacoes"]), 1)

    def test_janela_futura_usa_checkpoint_existente_sem_scheduler(self):
        future = mundo.WorldInstant(self.now.minute + 60)
        result = self.materialize(self.proposal(minimum=future))
        self.assertEqual(result["estado"], "planejada")
        self.assertEqual(mundo.load_world_state(self.repo)["pendencias"], [])
        reconciled = reactions.reconcile(self.repo, now=future)
        self.assertEqual(len(reconciled["novas_pendencias"]), 1)
        self.assertEqual(reactions.status(self.repo, result["reaction_id"])["estado"]["estado"], "elegivel")

    def test_alternativas_exclusivas_nao_sao_comprometidas_juntas(self):
        second = self.alternative(
            alternative_id="extracao_furtiva",
            capability="extrair_registro",
            resource="equipe de extração",
            physical=False,
        )
        result = self.materialize(self.proposal(alternatives=[self.alternative(), second]))
        with self.assertRaisesRegex(reactions.SidequestReactionError, "mutuamente exclusivas"):
            reactions.commit(
                self.repo,
                result["reaction_id"],
                ["ordem_contraditoria", "extracao_furtiva"],
            )

    def test_recurso_comprometido_nao_pode_ser_reutilizado(self):
        first = self.materialize(self.proposal())
        reactions.commit(self.repo, first["reaction_id"], ["ordem_contraditoria"])
        alternative_available = self.alternative(
            alternative_id="extracao_furtiva",
            capability="extrair_registro",
            resource="equipe de extração",
            group="outra_rota",
        )
        second_proposal = self.proposal(
            fact_id=SECOND_FACT_ID,
            alternatives=[self.alternative(), alternative_available],
        )
        prepared = reactions.prepare(self.repo, MISSION_ID, second_proposal)
        self.assertEqual(prepared["alternativas_elegiveis"], ["extracao_furtiva"])
        reasons = prepared["alternativas_bloqueadas"][0]["motivos"]
        self.assertTrue(any(reason.startswith("recurso_ja_comprometido") for reason in reasons))

    def test_compromisso_precede_resultado_e_resolucao_nao_reabre_missao(self):
        materialized = self.materialize()
        reaction_id = materialized["reaction_id"]
        committed = reactions.commit(self.repo, reaction_id, ["ordem_contraditoria"])
        self.assertEqual(committed["resultado"], "comprometida")
        resolved = reactions.resolve(
            self.repo,
            reaction_id,
            proof={"fonte": "sessoes/001/fatos.md", "evidencia": RESULT_EVIDENCE},
            result="A operação foi encerrada pelo resultado factual já registrado.",
        )
        mission = oportunidades.load_state(
            self.repo, oportunidades.load_index(self.repo)
        )["missoes"][MISSION_ID]
        self.assertEqual(resolved["resultado"], "resolvida")
        self.assertEqual(mission["estado"], "concluida")
        self.assertEqual(mundo.load_world_state(self.repo)["pendencias"], [])
        self.assertEqual(reactions._load_state(self.repo)["recursos_comprometidos"], {})


class SidequestReactionBudgetTest(unittest.TestCase):
    def test_orcamento_congela_limites_e_proibe_infraestrutura_paralela(self):
        baseline = yaml.safe_load(
            (ROOT / "baseline/sidequest-success-reactions-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        limits = baseline["limites"]
        self.assertEqual(limits["reacoes_max"], reactions.MAX_REACTIONS)
        self.assertEqual(limits["alternativas_por_reacao_max"], reactions.MAX_ALTERNATIVES)
        self.assertEqual(limits["alvos_por_reacao_max"], reactions.MAX_TARGETS)
        self.assertEqual(limits["recursos_por_alternativa_max"], reactions.MAX_RESOURCES)
        self.assertEqual(limits["contrato_por_reacao_bytes_max"], reactions.MAX_CONTRACT_BYTES)
        self.assertEqual(limits["preparacao_bytes_max"], reactions.MAX_PREP_BYTES)
        self.assertEqual(limits["janela_dias_max"], reactions.MAX_WINDOW_DAYS)
        self.assertEqual(limits["schedulers_novos"], 0)
        self.assertEqual(limits["rng_novo"], 0)
        self.assertEqual(limits["scans_globais"], 0)
        source = (ROOT / "ferramentas/reacoes_sidequest.py").read_text(encoding="utf-8")
        self.assertNotIn("import random", source)
        self.assertNotIn(".glob(", source)
        self.assertNotIn(".rglob(", source)

    def test_repo_sem_dominio_configurado_e_valido_e_check_e_read_only(self):
        before = {
            rel: (ROOT / rel).read_bytes() if (ROOT / rel).is_file() else None
            for rel in (reactions.INDEX, reactions.STATE)
        }
        result = reactions.check(ROOT)
        after = {
            rel: (ROOT / rel).read_bytes() if (ROOT / rel).is_file() else None
            for rel in (reactions.INDEX, reactions.STATE)
        }
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(before, after)
        self.assertEqual(result["contrato"]["scheduler_novo"], 0)
        self.assertEqual(result["contrato"]["rng_novo"], 0)
        self.assertEqual(result["contrato"]["scan_global"], 0)


if __name__ == "__main__":
    unittest.main()
