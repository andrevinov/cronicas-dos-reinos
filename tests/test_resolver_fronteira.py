from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import resolver_fronteira


def pending(
    pending_id: str,
    kind: str,
    *,
    agent: str | None = None,
    light: str | None = None,
    direction: str | None = None,
) -> dict:
    item = {
        "id": pending_id,
        "tipo": kind,
        "disparado_em": {"data": "17 Eleasis, 1372 DR", "hora": "06:00"},
        "motivo": "reavaliar sem transformar cadência em fato automático",
        "origem": "fixture",
    }
    if agent:
        item["agente"] = agent
    if light:
        item["agente_leve"] = light
    if direction:
        item["direcao"] = direction
    return item


class ResolverFronteiraPrepareTest(unittest.TestCase):
    def test_preparar_agrupa_contexto_dirigido_em_um_lote(self):
        world = {
            "pendencias": [
                pending("mundo-1111111111111111", "reavaliar_agente", agent="red_sail"),
                pending("mundo-2222222222222222", "reavaliar_agente_leve", light="maerra"),
                pending(
                    "mundo-3333333333333333",
                    "avaliar_direcao",
                    direction="golden_lily_em_ravens_bluff",
                ),
            ],
            "concluidas_recentes": [],
        }
        agent = {
            "agente_id": "red_sail",
            "fontes_lidas": ["narrador/agentes/index.yaml", "narrador/agentes/red_sail.yaml"],
            "elegibilidade_local": {"permitida": True},
            "resultado": {
                "estado": "ativo",
                "objetivo_atual": "localizar Ren",
                "restricoes": ["não expor a rede"],
                "plano_atual": {"estado": "em_execucao", "acao": "buscar"},
            },
        }
        light = {
            "agente_leve_id": "maerra",
            "fontes_lidas": [
                "narrador/agentes-leves/index.yaml",
                "narrador/agentes-leves/estado.yaml",
                "narrador/agentes-leves/maerra.yaml",
            ],
            "cache_negativo": None,
            "resultado": {
                "rotina_padrao": {"descricao": "trabalho pastoral"},
                "objetivo_atual": {"descricao": "cuidar da comunidade"},
                "iniciativas_possiveis": [],
                "regra_de_reavaliacao": "rotina é padrão",
            },
        }
        direction = {
            "direcao_id": "golden_lily_em_ravens_bluff",
            "permitido": True,
            "estado": "ativa",
            "marco_atual": {
                "id": "rumores",
                "criterio_para_avancar": "fato canônico suficiente",
                "guardrails": ["cadência não implica avanço"],
            },
            "avanco_requer_fato_canonico": True,
            "fontes_lidas": [
                "narrador/direcoes/index.yaml",
                "narrador/direcoes/estado.yaml",
                "narrador/direcoes/golden.yaml",
            ],
        }

        with (
            patch.object(resolver_fronteira.mundo, "load_world_state", return_value=world),
            patch.object(
                resolver_fronteira.barreira_mundo, "_canonical_event", return_value=None
            ),
            patch.object(
                resolver_fronteira.pressao_ravens_bluff,
                "candidate_for_pending",
                return_value=None,
            ),
            patch.object(resolver_fronteira.agentes, "load_agent", return_value=agent) as a,
            patch.object(
                resolver_fronteira.agentes_leves, "load_agent", return_value=light
            ) as l,
            patch.object(
                resolver_fronteira.direcoes_destino, "project", return_value=direction
            ) as d,
        ):
            result = resolver_fronteira.prepare_batch(ROOT)

        self.assertFalse(result["mutante"])
        self.assertEqual(result["quantidade"], 3)
        self.assertTrue(result["lote_id"].startswith("frn1."))
        self.assertEqual(len({item["token"] for item in result["itens"]}), 3)
        a.assert_called_once_with(ROOT, "red_sail")
        l.assert_called_once_with(ROOT, "maerra")
        d.assert_called_once_with(ROOT, "golden_lily_em_ravens_bluff")
        self.assertEqual(
            [item["classificacao"] for item in result["itens"]],
            ["avaliar_no_lote", "avaliar_no_lote", "avaliar_no_lote"],
        )
        self.assertIn("plano_atual", result["itens"][0]["contexto"]["agente"])
        self.assertIn("rotina_padrao", result["itens"][1]["contexto"]["agente_leve"])
        self.assertTrue(
            result["itens"][2]["contexto"]["direcao"]["avanco_requer_fato_canonico"]
        )

    def test_evento_canonico_nunca_oferece_sem_mudanca(self):
        world = {
            "pendencias": [
                pending("mundo-aaaaaaaaaaaaaaaa", "expiracao"),
            ],
            "concluidas_recentes": [],
        }
        canonical = {
            "id": "emboscada_do_restaurante",
            "titulo": "A velha e os três homens",
            "nucleo_obrigatorio": ["a abordagem acontece"],
            "guardrails": ["não decidir por Ren"],
        }
        with (
            patch.object(resolver_fronteira.mundo, "load_world_state", return_value=world),
            patch.object(
                resolver_fronteira.barreira_mundo,
                "_canonical_event",
                return_value=canonical,
            ),
            patch.object(
                resolver_fronteira.pressao_ravens_bluff,
                "candidate_for_pending",
                return_value=None,
            ),
        ):
            result = resolver_fronteira.prepare_batch(ROOT)

        item = result["itens"][0]
        self.assertEqual(item["classificacao"], "requer_fato_canonico")
        self.assertFalse(item["sem_mudanca_permitido"])
        self.assertEqual(
            item["contexto"]["evento_canonico"]["id"], "emboscada_do_restaurante"
        )


class ResolverFronteiraApplyTest(unittest.TestCase):
    def item(self, pending_id: str, kind: str, classification: str, token: str) -> dict:
        return {
            "id": pending_id,
            "tipo": kind,
            "classificacao": classification,
            "sem_mudanca_permitido": True,
            "token": token,
        }

    def test_aplicar_fecha_varios_noops_numa_unica_operacao(self):
        t1 = "1" * resolver_fronteira.TOKEN_HEX
        t2 = "2" * resolver_fronteira.TOKEN_HEX
        t3 = "3" * resolver_fronteira.TOKEN_HEX
        current = {
            "lote_id": "frn1." + "a" * resolver_fronteira.BATCH_HEX,
            "itens": [
                self.item(
                    "mundo-1111111111111111",
                    "reavaliar_agente_leve",
                    "avaliar_no_lote",
                    t1,
                ),
                self.item(
                    "mundo-2222222222222222",
                    "reavaliar_agente",
                    "avaliar_no_lote",
                    t2,
                ),
                self.item(
                    "mundo-3333333333333333",
                    "reavaliar_agente",
                    "avaliar_candidato_autonomo",
                    t3,
                ),
            ],
        }
        remaining = {
            "lote_id": "frn1." + "b" * resolver_fronteira.BATCH_HEX,
            "quantidade": 0,
            "itens": [],
        }
        payload = {
            "lote_id": current["lote_id"],
            "sem_mudanca": [
                {
                    "id": "mundo-1111111111111111",
                    "token": t1,
                    "nota": "Rotina confirmada sem causa causal nova.",
                },
                {
                    "id": "mundo-2222222222222222",
                    "token": t2,
                    "nota": "Plano permanece estável e não produz fato novo nesta cadência.",
                },
                {
                    "id": "mundo-3333333333333333",
                    "token": t3,
                    "nota": (
                        "A restrição canônica de presença impede a operação autônoma "
                        "nesta janela temporal."
                    ),
                },
            ],
        }

        with (
            patch.object(
                resolver_fronteira, "prepare_batch", side_effect=[current, remaining]
            ),
            patch.object(resolver_fronteira, "_completed_map", return_value={}),
            patch.object(
                resolver_fronteira.agentes_leves,
                "conclude_noop",
                return_value={"concluida": {"id": "mundo-1111111111111111"}},
            ) as light,
            patch.object(
                resolver_fronteira.barreira_mundo,
                "conclude",
                side_effect=[
                    {"concluida": {"id": "mundo-2222222222222222"}},
                    {"concluida": {"id": "mundo-3333333333333333"}},
                ],
            ) as generic,
            patch.object(
                resolver_fronteira.barreira_mundo,
                "sync",
                return_value={"bloqueado": False, "quantidade": 0},
            ) as sync,
        ):
            result = resolver_fronteira.apply_batch(ROOT, payload)

        light.assert_called_once()
        self.assertEqual(generic.call_count, 2)
        self.assertFalse(generic.call_args_list[0].kwargs["no_change"])
        self.assertTrue(generic.call_args_list[1].kwargs["no_change"])
        sync.assert_called_once_with(ROOT)
        self.assertEqual(len(result["aplicadas"]), 3)
        self.assertEqual(result["quantidade_restante"], 0)
        self.assertEqual(result["proximo_passo"], {"acao": "continuar_turno"})

    def test_plano_stale_falha_antes_de_escrever(self):
        token = "1" * resolver_fronteira.TOKEN_HEX
        current = {
            "lote_id": "frn1." + "a" * resolver_fronteira.BATCH_HEX,
            "itens": [
                self.item(
                    "mundo-1111111111111111",
                    "reavaliar_agente",
                    "avaliar_no_lote",
                    token,
                )
            ],
        }
        payload = {
            "lote_id": current["lote_id"],
            "sem_mudanca": [
                {
                    "id": "mundo-1111111111111111",
                    "token": "2" * resolver_fronteira.TOKEN_HEX,
                    "nota": "Nada mudou de modo causal.",
                }
            ],
        }
        with (
            patch.object(resolver_fronteira, "prepare_batch", return_value=current),
            patch.object(resolver_fronteira, "_completed_map", return_value={}),
            patch.object(resolver_fronteira.barreira_mundo, "conclude") as conclude,
        ):
            with self.assertRaises(resolver_fronteira.BatchBoundaryError):
                resolver_fronteira.apply_batch(ROOT, payload)
        conclude.assert_not_called()

    def test_evento_canonico_e_rejeitado_antes_de_escrever(self):
        token = "1" * resolver_fronteira.TOKEN_HEX
        item = self.item(
            "mundo-1111111111111111",
            "expiracao",
            "requer_fato_canonico",
            token,
        )
        item["sem_mudanca_permitido"] = False
        current = {
            "lote_id": "frn1." + "a" * resolver_fronteira.BATCH_HEX,
            "itens": [item],
        }
        payload = {
            "lote_id": current["lote_id"],
            "sem_mudanca": [
                {
                    "id": item["id"],
                    "token": token,
                    "nota": "Tentativa de no-op que deve ser rejeitada.",
                }
            ],
        }
        with (
            patch.object(resolver_fronteira, "prepare_batch", return_value=current),
            patch.object(resolver_fronteira, "_completed_map", return_value={}),
            patch.object(resolver_fronteira.barreira_mundo, "conclude") as conclude,
        ):
            with self.assertRaises(resolver_fronteira.BatchBoundaryError):
                resolver_fronteira.apply_batch(ROOT, payload)
        conclude.assert_not_called()

    def test_retry_reconhece_item_ja_concluido(self):
        pending_id = "mundo-1111111111111111"
        current = {
            "lote_id": "frn1." + "b" * resolver_fronteira.BATCH_HEX,
            "quantidade": 0,
            "itens": [],
        }
        payload = {
            "lote_id": "frn1." + "a" * resolver_fronteira.BATCH_HEX,
            "sem_mudanca": [
                {
                    "id": pending_id,
                    "token": "1" * resolver_fronteira.TOKEN_HEX,
                    "nota": "Rotina previamente concluída de forma rastreável.",
                }
            ],
        }
        completed = {
            pending_id: {
                "id": pending_id,
                "tipo": "reavaliar_agente",
                "nota": "Rotina previamente concluída de forma rastreável.",
            }
        }
        with (
            patch.object(
                resolver_fronteira, "prepare_batch", side_effect=[current, current]
            ),
            patch.object(resolver_fronteira, "_completed_map", return_value=completed),
            patch.object(resolver_fronteira.barreira_mundo, "conclude") as conclude,
            patch.object(
                resolver_fronteira.barreira_mundo,
                "sync",
                return_value={"bloqueado": False, "quantidade": 0},
            ),
        ):
            result = resolver_fronteira.apply_batch(ROOT, payload)

        conclude.assert_not_called()
        self.assertEqual(result["aplicadas"], [])
        self.assertEqual(result["ja_aplicadas"][0]["id"], pending_id)
        self.assertTrue(result["idempotente"])


if __name__ == "__main__":
    unittest.main()
