from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import reconhecibilidade_persona as fame
import planos_personagens as plans
import turno
import test_planos_personagens as legacy


class ChallengeSchemaTest(unittest.TestCase):
    def ref(self, path, value=True):
        return {"arquivo": "estado/npcs/rival.yaml", "caminho": "npc." + path, "valor": value}

    def step(self):
        return {
            "id": "desafiar_kage",
            "acao": "Procurar Kage e apresentar um desafio formal.",
            "em": {"data": legacy.DATE, "hora": "08:03"},
            "duracao_minutos": 5,
            "local": "Circo",
            "condicoes": [],
            "recursos": [],
            "conhecimento": ["kage_publico"],
            "resolucao": {"tipo": "factual", "sem_oposicao": self.ref("oportunidade.sem_oposicao")},
            "desafio_persona": {
                "persona": "kage",
                "reconhecimento": {
                    "audiencia": "circo_e_artes",
                    "localidade": "ravens_bluff",
                    "marco_publico": "kage_estreia",
                    "confianca_minima": "media",
                    "atribuicao_minima": "provavel",
                },
                "motivacao": self.ref("motivacao_desafio"),
                "conhecimento_persona": "kage_publico",
                "alcance": {"tipo": "fisico", "local": "Circo"},
                "interesse": {"tipo": "marcial", "referencia": self.ref("interesse_desafio", "marcial")},
                "stakes": {
                    "descricao": "Prestígio entre praticantes marciais que acompanham o circo.",
                    "se_aceito": "O rival obtém a chance pública de medir técnica e prestígio com Kage.",
                    "se_recusado": "O rival preserva a motivação, mas não ganha vitória nem notoriedade automática.",
                },
                "protecoes": [self.ref("oportunidade.sem_oposicao")],
            },
        }

    def test_schema_exige_todos_os_requisitos_causais(self):
        step = self.step()
        self.assertEqual(plans._step(step), step)
        for field in sorted(step["desafio_persona"]):
            with self.subTest(field=field):
                bad = deepcopy(step)
                del bad["desafio_persona"][field]
                with self.assertRaises(plans.PlanError):
                    plans._step(bad)

    def test_desafio_nao_funde_chegada_e_nao_resolve_confronto_por_teste(self):
        merged = self.step()
        merged["entrada_local"] = {}
        with self.assertRaisesRegex(plans.PlanError, "passos distintos"):
            plans._step(merged)
        test = self.step()
        test["resolucao"] = {"tipo": "teste", "bonus": self.ref("bonus", 2), "cd": self.ref("cd", 12)}
        with self.assertRaisesRegex(plans.PlanError, "não resolve combate"):
            plans._step(test)

    def test_canal_precisa_ser_o_mesmo_da_resolucao_social(self):
        step = self.step()
        cause = {"arquivo": "estado/npcs/rival.yaml", "caminho": "npc.necessidades.desafio", "valor": True}
        channel = {
            "arquivo": "estado/npcs/rival.yaml",
            "caminho": "npc.canais_contato.kage",
            "valor": {
                "meio": "mensageiro", "origem": "Circo", "destino": "Circo",
                "portador": "mensageiro", "duracao_minima_minutos": 5,
                "conhecimento_id": "kage_publico", "disponivel": True,
            },
        }
        step["desafio_persona"]["motivacao"] = cause
        step["desafio_persona"]["alcance"] = {"tipo": "canal", "persona": "kage", "referencia": channel}
        step["resolucao"] = {
            "tipo": "contato", "modalidade": "retomar_assunto",
            "mensagem": "Kage, aceitaria um desafio formal diante dos artistas?",
            "causa": cause, "canal": channel,
        }
        self.assertEqual(plans._step(step), step)
        bad = deepcopy(step)
        bad["desafio_persona"]["alcance"]["referencia"] = self.ref("outro_canal")
        with self.assertRaises(plans.PlanError):
            plans._step(bad)


class CausalChallengeJourneyTest(legacy.PlanFixture):
    FACT = "Kage concluiu uma apresentação pública diante do público do circo e foi anunciado pelo nome artístico."

    def setUp(self):
        super().setUp()
        self._install_registries_and_fame()
        self._prepare_actor()

    def _install_registries_and_fame(self):
        identity = {
            "schema_identidades_ren": 1,
            "natureza": "registro_canonico_de_personas_do_jogador",
            "principal": "ren",
            "observacao": "Fixture NV-20.",
            "identidades": {
                "ren": {"nome": "Ren", "tipo": "identidade_principal", "aliases": ["Ren"]},
                "shinta": {"nome": "Shinta", "tipo": "cobertura", "aliases": ["Shinta"]},
                "kage": {"nome": "Kage", "tipo": "persona_publica", "aliases": ["Kage"]},
            },
            "regras": {
                "actor_nao_e_metamorfose": True,
                "suspeita_nao_e_conhecimento_confirmado": True,
                "suspeita_forte_nao_confirma_sozinha": True,
                "confirmacao_exige_fato_canonico_explicito": True,
            },
        }
        self.write("personagens/jogador/identidades.yaml", identity)
        social = self.repo / "cenario/regioes/ravens-bluff/faccoes.md"
        social.parent.mkdir(parents=True, exist_ok=True)
        social.write_text("# Estrutura social da fixture NV-20\n", encoding="utf-8")
        self.write("cenario/regioes/ravens-bluff/publicos-reputacao.yaml", {
            "schema_publicos_reputacao": 1,
            "cidade": "ravens_bluff",
            "natureza": "registro_canonico_de_publicos_sociais",
            "fonte_estrutura_social": "cenario/regioes/ravens-bluff/faccoes.md",
            "observacao": "Fixture dirigida.",
            "publicos": {
                "circo_e_artes": {"nome": "Circo e artes", "aliases": ["circo"], "descricao": "Público cultural."},
            },
            "regras": {
                "publico_nao_e_opiniao_individual": True,
                "publico_nao_compartilha_conhecimento_secreto_automaticamente": True,
                "reputacoes_de_personas_nao_se_fundem_automaticamente": True,
            },
        })
        proposal = fame.propose_public_performance(
            self.repo, persona="kage", audiences=["circo_e_artes"], locality="ravens_bluff",
            milestone="kage_estreia", fact=self.FACT, source="fixture:kage_estreia", records=[]
        )
        state = self.read("estado/estado-atual.yaml")
        state[fame.STATE_ROOT] = deepcopy(proposal["deltas"][1]["valor"])
        self.write("estado/estado-atual.yaml", state)

    def _prepare_actor(self):
        npc = self.read(self.source)
        npc["npc"]["motivacao_desafio"] = True
        npc["npc"]["interesse_desafio"] = "marcial"
        npc["npc"]["conhecimento"] = [
            {
                "id": "kage_publico", "persona": "kage",
                "fonte": "estado/estado-atual.yaml", "evidencia": self.FACT,
            }
        ]
        self.write(self.source, npc)

        relation_path = f"estado/relacoes/{self.actor}.yaml"
        relation = self.read(relation_path)
        relation["relacao"]["ambicao_desafio"] = "Desafiar Kage por prestígio."
        self.write(relation_path, relation)

        profile_path = f"narrador/agentes-leves/{self.actor}.yaml"
        profile = self.read(profile_path)
        profile["objetivo_atual"] = {
            "descricao": "Desafiar Kage por prestígio.",
            "fonte": relation_path,
            "evidencia": "Desafiar Kage por prestígio.",
        }
        self.write(profile_path, profile)
        index_path = "narrador/agentes-leves/index.yaml"
        index = self.read(index_path)
        index["agentes"][self.actor]["perfil_blob_git"] = plans.agentes_leves._git_blob_sha(self.repo / profile_path)
        self.write(index_path, index)

    def challenge_step(self):
        step = self.step(sid="desafiar_kage", cost=0)
        step["acao"] = "Apresentar a Kage um desafio formal sem decidir a resposta dele."
        step["conhecimento"] = ["kage_publico"]
        step["resolucao"] = {"tipo": "factual", "sem_oposicao": self.ref("oportunidade.sem_oposicao", True)}
        step["desafio_persona"] = {
            "persona": "kage",
            "reconhecimento": {
                "audiencia": "circo_e_artes",
                "localidade": "ravens_bluff",
                "marco_publico": "kage_estreia",
                "confianca_minima": "media",
                "atribuicao_minima": "provavel",
            },
            "motivacao": self.ref("motivacao_desafio", True),
            "conhecimento_persona": "kage_publico",
            "alcance": {"tipo": "fisico", "local": "Circo"},
            "interesse": {"tipo": "marcial", "referencia": self.ref("interesse_desafio", "marcial")},
            "stakes": {
                "descricao": "Prestígio marcial diante do circuito artístico.",
                "se_aceito": "Haverá um confronto futuro apenas se Kage aceitar explicitamente.",
                "se_recusado": "A recusa não concede vitória nem altera identidade ou reputação automaticamente.",
            },
            "protecoes": [self.ref("oportunidade.sem_oposicao", True)],
        }
        return step

    def define_challenge(self, pid="desafio"):
        event = {
            "evento": "definir", "revisao": 0,
            "fato": "O rival decidiu procurar Kage para apresentar um desafio formal.",
            "agente": {"tipo": "leve", "id": self.actor},
            "objetivo": "Desafiar Kage por prestígio.",
            "passo": self.challenge_step(),
        }
        tx = {
            "id": "definir-" + pid, "modo": "mundo", "narracao": event["fato"], "resumo": event["fato"],
            "deltas": [{"alvo": "plano:" + pid, "op": "registrar", "visibilidade": "narrador", "valor": event}],
        }
        return turno.register_transaction(self.repo, tx)

    def test_desafiante_plausivel_pode_planejar_reacao_a_fama(self):
        self.define_challenge()
        plan = self.plan("desafio")
        self.assertEqual(plan["tipo"], plans.CHALLENGE_TYPE)
        self.assertEqual(plan["passo"]["desafio_persona"]["persona"], "kage")
        item = next(row for row in self.items() if row["contexto"]["plano_personagem"]["plano"]["id"] == "desafio")
        projected = item["contexto"]["plano_personagem"]["desafio_persona"]
        self.assertEqual(projected["reconhecimento"]["nivel"], "reconhecivel")
        self.assertEqual(projected["marco_causal"], "kage_estreia")
        self.assertFalse(item["sem_mudanca_permitido"])

    def test_sem_fama_suficiente_desafio_nem_e_planejado(self):
        state = self.read("estado/estado-atual.yaml")
        state.pop(fame.STATE_ROOT, None)
        self.write("estado/estado-atual.yaml", state)
        with self.assertRaisesRegex(ValueError, "reconhecimento público"):
            self.define_challenge("sem_fama")

    def test_conhecimento_da_persona_nao_pode_ser_conhecimento_de_ren(self):
        npc = self.read(self.source)
        npc["npc"]["conhecimento"][0]["persona"] = "ren"
        self.write(self.source, npc)
        with self.assertRaisesRegex(ValueError, "persona-alvo"):
            self.define_challenge("conhecimento_errado")

    def test_motivacao_interesse_alcance_e_protecoes_sao_revalidados(self):
        cases = [
            ("motivacao_desafio", False, "motivação"),
            ("interesse_desafio", "nenhum", "interesse"),
            ("presenca", {"local": "Porto", "estado": "presente", "em_deslocamento": False}, "alcance físico"),
            ("oportunidade", {"sem_oposicao": False, "cd": 13}, "condição mudou"),
        ]
        original = self.read(self.source)
        for key, value, message in cases:
            with self.subTest(key=key):
                npc = deepcopy(original)
                npc["npc"][key] = value
                self.write(self.source, npc)
                with self.assertRaisesRegex(ValueError, message):
                    self.define_challenge("falha_" + key)
        self.write(self.source, original)

    def test_fama_pode_ser_causa_dirigida_de_entrada_nv19_sem_sortear_ator(self):
        ref = plans.challenge_fame_reference(
            self.repo, persona="kage", audience="circo_e_artes",
            locality="ravens_bluff", milestone="kage_estreia"
        )
        self.assertEqual(ref["arquivo"], "estado/estado-atual.yaml")
        self.assertEqual(ref["valor"]["persona"], "kage")
        self.assertEqual(plans._ref(ref), ref)


if __name__ == "__main__":
    unittest.main()
