from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import contexto
import identidades
import transacoes


class IdentityRegistryTest(unittest.TestCase):
    def test_registro_tem_ren_shinta_kage_sem_afirmar_quem_sabe(self):
        registry = identidades.load_registry(ROOT)
        self.assertEqual(registry["principal"], "ren")
        self.assertEqual(set(registry["identidades"]), {"ren", "shinta", "kage"})
        self.assertEqual(identidades.resolve_identity(registry, "Shinta Ryoushi"), "shinta")
        self.assertEqual(identidades.resolve_identity(registry, "Kage"), "kage")
        self.assertTrue(registry["regras"]["suspeita_nao_e_conhecimento_confirmado"])
        self.assertEqual(identidades.check(ROOT), [])

    def test_estado_vazio_nao_inventa_suspeita_retroativa(self):
        registry = identidades.load_registry(ROOT)
        projected = identidades.project(identidades.empty_state(), registry)
        self.assertEqual(projected["suspeitas"], [])
        self.assertEqual(projected["confirmacoes"], [])


class IdentityEvidenceTest(unittest.TestCase):
    def test_actor_sucesso_bloqueia_so_evidencia_de_atuacao(self):
        acted = identidades.propose_evidence(
            ROOT,
            npc="Kethra",
            observed="kage",
            possible="ren",
            evidence_type="atuacao",
            fact="Kage sustentou a voz e os maneirismos diante de Kethra sem deslize observável.",
            source="teste:actor-sucesso",
            actor_result="sucesso",
        )
        self.assertEqual(acted["resultado"], "sem_delta")

        physical = identidades.propose_evidence(
            ROOT,
            npc="Kethra",
            observed="kage",
            possible="ren",
            evidence_type="fisica",
            fact="Kethra percebeu que Kage tem a mesma cicatriz visível e proporções corporais de Ren.",
            source="teste:semelhanca-fisica",
            actor_result="sucesso",
        )
        self.assertEqual(physical["resultado"], "registrar_delta")
        projected = physical["projecao_depois"]
        self.assertEqual(projected["suspeitas"][0]["grau"], "possibilidade")
        self.assertEqual(projected["suspeitas"][0]["evidencias"], 1)
        self.assertEqual(projected["confirmacoes"], [])

    def test_evidencias_acumulam_uma_por_fato_e_nunca_auto_confirmam(self):
        registry = identidades.load_registry(ROOT)
        entity_id = "kethra_dunn"
        state = identidades.empty_state()
        facts = [
            ("fisica", "Kethra reconheceu em Kage a mesma cicatriz discreta que já havia visto em Ren.", "teste:pista-1"),
            ("contextual", "Kage demonstrou conhecer um detalhe da fuga de Colm que Kethra havia contado apenas a Ren.", "teste:pista-2"),
            ("contradicao", "Kage reagiu ao nome de Colm antes que Kethra explicasse por que aquele nome importava.", "teste:pista-3"),
        ]
        for index, (kind, fact, source) in enumerate(facts, start=1):
            new = copy.deepcopy(state)
            existing = next(
                (item for item in new["suspeitas"] if item["observada"] == "kage" and item["possivel"] == "ren"),
                None,
            )
            evidence = {
                "id": identidades.evidence_id(entity_id, "kage", "ren", kind, source, fact),
                "tipo": kind,
                "fonte": source,
            }
            if existing is None:
                new["suspeitas"].append({"observada": "kage", "possivel": "ren", "evidencias": [evidence]})
            else:
                existing["evidencias"].append(evidence)
            delta = {
                "alvo": f"npc:{entity_id}",
                "op": "set",
                "caminho": identidades.STATE_FIELD,
                "valor": new,
                "motivo_identidade": "evidencia",
                "fato_canonico": fact,
                "fonte": source,
                "actor_resultado": "nao_aplicavel",
            }
            state = identidades.validate_transition(entity_id, state, delta, registry)
            self.assertEqual(len(state["suspeitas"][0]["evidencias"]), index)
            self.assertEqual(state["confirmacoes"], [])

        projection = identidades.project(state, registry)
        self.assertEqual(projection["suspeitas"][0]["grau"], "suspeita_forte")
        self.assertEqual(projection["confirmacoes"], [])

    def test_mesma_evidencia_e_idempotente(self):
        kwargs = dict(
            repo=ROOT,
            npc="Kethra",
            observed="kage",
            possible="ren",
            evidence_type="fisica",
            fact="Kethra percebeu em Kage a mesma marca fina junto ao maxilar que havia notado em Ren.",
            source="teste:pista-idempotente",
            actor_result="nao_aplicavel",
        )
        first = identidades.propose_evidence(**kwargs)
        self.assertEqual(first["resultado"], "registrar_delta")
        state = first["delta"]["valor"]
        eid = state["suspeitas"][0]["evidencias"][0]["id"]
        expected = identidades.evidence_id(
            "kethra_dunn", "kage", "ren", "fisica", kwargs["source"], kwargs["fact"]
        )
        self.assertEqual(eid, expected)

    def test_confirmacao_exige_fato_explicito_e_remove_so_aresta_equivalente(self):
        registry = identidades.load_registry(ROOT)
        evidence_fact = "Kethra viu Kage usar um gesto idêntico ao de Ren ao ajustar a faixa do punho."
        source = "teste:pista-confirmacao"
        before = {
            "schema_reconhecimento_identidade": 1,
            "suspeitas": [
                {
                    "observada": "kage",
                    "possivel": "ren",
                    "evidencias": [
                        {
                            "id": identidades.evidence_id("kethra_dunn", "kage", "ren", "fisica", source, evidence_fact),
                            "tipo": "fisica",
                            "fonte": source,
                        }
                    ],
                },
                {
                    "observada": "shinta",
                    "possivel": "ren",
                    "evidencias": [
                        {
                            "id": identidades.evidence_id("kethra_dunn", "shinta", "ren", "contextual", "teste:outra", "Shinta conhecia um detalhe que Kethra associava apenas a Ren e ao resgate de Colm."),
                            "tipo": "contextual",
                            "fonte": "teste:outra",
                        }
                    ],
                },
            ],
            "confirmacoes": [],
        }
        after = copy.deepcopy(before)
        after["suspeitas"] = [item for item in after["suspeitas"] if item["observada"] != "kage"]
        after["confirmacoes"].append({"observada": "kage", "identidade": "ren", "fonte": "teste:confirmado"})
        delta = {
            "alvo": "npc:kethra_dunn",
            "op": "set",
            "caminho": identidades.STATE_FIELD,
            "valor": after,
            "motivo_identidade": "confirmacao",
            "fato_canonico": "Kethra viu Ren retirar pessoalmente a caracterização de Kage e assumir seu próprio nome diante dela.",
            "fonte": "teste:confirmado",
            "actor_resultado": "nao_aplicavel",
            "confirmacao_canonica": True,
        }
        validated = identidades.validate_transition("kethra_dunn", before, delta, registry)
        self.assertEqual(len(validated["confirmacoes"]), 1)
        self.assertEqual(validated["suspeitas"][0]["observada"], "shinta")

        invalid = copy.deepcopy(delta)
        invalid.pop("confirmacao_canonica")
        with self.assertRaises(identidades.IdentitySuspicionError):
            identidades.validate_identity_delta(invalid, registry)


class IdentityTransactionalIntegrationTest(unittest.TestCase):
    def test_writer_aceita_delta_proposto_e_contexto_ve_overlay_antes_checkpoint(self):
        proposal = identidades.propose_evidence(
            ROOT,
            npc="Kethra",
            observed="kage",
            possible="ren",
            evidence_type="contextual",
            fact="Kage citou espontaneamente um detalhe operacional que Kethra havia transmitido apenas a Ren.",
            source="teste:overlay-identidade",
            actor_result="nao_aplicavel",
        )
        delta = proposal["delta"]
        transacoes.validate_delta(delta)
        record = {
            "versao": transacoes.SCHEMA_VERSION,
            "id": "tx-identidade-overlay",
            "sessao": 999,
            "resumo": "Kethra reuniu uma nova pista contextual ligando Kage a Ren sem obter confirmação definitiva.",
            "deltas": [delta],
        }
        with mock.patch.object(contexto, "_pending", return_value=[record]):
            data = contexto.command_npc(ROOT, "Kethra")
        state = data["resultado"]["medidores"]["dados"][identidades.STATE_FIELD]
        self.assertEqual(state["suspeitas"][0]["observada"], "kage")
        self.assertEqual(len(state["suspeitas"][0]["evidencias"]), 1)
        self.assertEqual(data["resultado"]["deltas_pendentes_aplicados"], 1)
        self.assertIn(transacoes.PENDING_PATH.as_posix(), data["fontes"])

    def test_batch_rejeita_actor_sucesso_com_pista_puramente_performatica(self):
        registry = identidades.load_registry(ROOT)
        fact = "Kage deixou escapar por um instante a cadência vocal de Ren durante uma conversa com Kethra."
        source = "teste:actor-nao-pode-vazar"
        state = identidades.empty_state()
        new = copy.deepcopy(state)
        new["suspeitas"].append(
            {
                "observada": "kage",
                "possivel": "ren",
                "evidencias": [
                    {
                        "id": identidades.evidence_id("kethra_dunn", "kage", "ren", "atuacao", source, fact),
                        "tipo": "atuacao",
                        "fonte": source,
                    }
                ],
            }
        )
        delta = {
            "alvo": "npc:kethra_dunn",
            "op": "set",
            "caminho": identidades.STATE_FIELD,
            "valor": new,
            "motivo_identidade": "evidencia",
            "fato_canonico": fact,
            "fonte": source,
            "actor_resultado": "sucesso",
        }
        with self.assertRaises(identidades.IdentitySuspicionError):
            identidades.validate_transition("kethra_dunn", state, delta, registry)


class IdentityBudgetTest(unittest.TestCase):
    def test_contrato_congela_zero_custo_comum_e_sem_estado_paralelo(self):
        data = yaml.safe_load(
            (ROOT / "baseline/identity-suspicion-recognition-orcamento.yaml").read_text(encoding="utf-8")
        )
        limits = data["limites"]
        self.assertEqual(limits["max_arestas_suspeita_por_npc"], identidades.MAX_EDGES)
        self.assertEqual(limits["max_evidencias_por_aresta"], identidades.MAX_EVIDENCE)
        self.assertEqual(limits["max_estado_bytes"], identidades.MAX_STATE_BYTES)
        self.assertEqual(limits["chamadas_extras_por_encontro_comum"], 0)
        self.assertEqual(limits["fontes_extras_contexto_npc_sem_suspeita"], 0)
        self.assertEqual(limits["schedulers_novos"], 0)
        self.assertEqual(limits["rng_novo"], 0)
        self.assertEqual(limits["estado_paralelo_novo"], 0)
        self.assertTrue(all(data["invariantes"].values()))


if __name__ == "__main__":
    unittest.main()
