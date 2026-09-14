from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import context_and_memory as context_memory
import contexto
import cronica
from ferramentas import preflight
import npc_continuity_and_social_behavior as npc_continuity
import retomada_cronica


def durable_information() -> dict:
    evidence = "Ren contou a Silva que a ponte caiu, mas apresentou isso apenas como rumor."
    return {
        "jogador": "Ren conversa com Silva.",
        "narracao": evidence,
        "resumo": "Silva recebeu um rumor.",
        "deltas": [],
        "memoria": {
            "versao": 1,
            "fatos": [
                {
                    "id": "ponte",
                    "tipo": "informacao",
                    "participantes": ["ren", "silva_fixture", "nera_fixture"],
                    "evidencia": {"campo": "narracao", "trecho": evidence},
                    "texto": evidence,
                    "emissor": "ren",
                    "destinatario": "silva_fixture",
                    "canal": "presencial",
                    "estatuto": "rumor",
                }
            ],
        },
    }


def scene_document(name: str = "Silva") -> dict:
    return {
        "consulta": {"comando": "npc", "termo": "silva_fixture"},
        "fontes": ["estado/relacoes/silva_fixture.yaml"],
        "resultado": {
            "encontrado": True,
            "relacao": {
                "id": "silva_fixture",
                "dados": {
                    "nome": name,
                    "informacoes_recebidas": [
                        {"texto": "A ponte caiu.", "estatuto": "rumor"}
                    ],
                },
            },
        },
    }


class ContextAndMemoryModuleContractTest(unittest.TestCase):
    def test_catalogo_e_hot_paths_publicam_um_unico_modulo(self) -> None:
        catalog = json.loads(
            (ROOT / "evaluation/catalogo-modulos-v2.json").read_text(
                encoding="utf-8"
            )
        )
        module = next(
            item for item in catalog["modulos"]
            if item["id"] == context_memory.MODULE_ID
        )

        self.assertEqual(catalog["versao_catalogo"], "2.5.0")
        self.assertEqual(module["versao_implementacao"], "1.0.0")
        self.assertEqual(
            {item["id"] for item in module["subcapacidades"]},
            set(context_memory.CAPABILITIES),
        )
        self.assertEqual(context_memory.LEGACY_ALIASES, ())
        self.assertIs(contexto.context_memory, context_memory)
        self.assertIs(contexto.politica, context_memory)
        self.assertIs(contexto.memoria_cena, context_memory)
        self.assertIs(cronica._scene_memory, context_memory)
        self.assertIs(cronica._durable, context_memory)
        self.assertIs(cronica._npc_continuity, npc_continuity)
        self.assertIs(retomada_cronica.memoria_cena, context_memory)
        self.assertIs(context_memory.project, context_memory.project_scene_memory)

    def test_preflight_publica_um_check_e_fontes_mantem_seus_donos(self) -> None:
        commands = [
            tuple(item.comando[1:])
            for item in preflight.checks(incluir_testes=False)
        ]
        self.assertEqual(
            commands.count(("ferramentas/context_and_memory.py", "check")),
            1,
        )
        self.assertEqual(len(context_memory.SOURCE_OWNERSHIP), 8)
        self.assertEqual(
            len(set(context_memory.SOURCE_OWNERSHIP.values())),
            len(context_memory.SOURCE_OWNERSHIP),
        )
        report = context_memory.check(ROOT)
        self.assertTrue(report["ok"], report["erros"])
        self.assertFalse(report["contrato"]["parallel_state"])
        self.assertFalse(report["contrato"]["new_global_scan"])
        self.assertEqual(report["contrato"]["additional_orchestration_calls"], 0)


class RoutedContextAccessTest(unittest.TestCase):
    def test_l0_nao_exige_chamada_e_l3_l4t_exigem_lacuna(self) -> None:
        self.assertFalse(
            context_memory.check(ROOT)["contrato"]["l0_requires_tool_call"]
        )
        search = context_memory.classify("buscar")
        transcript = context_memory.classify(
            "buscar", historical=True, transcripts=True
        )
        with self.assertRaises(context_memory.AccessPolicyError):
            context_memory.validate_escalation(
                search,
                after="L2",
                reason="por precaução",
            )
        with self.assertRaises(context_memory.AccessPolicyError):
            context_memory.validate_escalation(
                transcript,
                after="L3",
                reason="A busca histórica não contém a formulação literal necessária.",
            )
        self.assertEqual(transcript.required_after, "L4")

    def test_consulta_dirigida_emite_recibo_e_nao_escreve_runtime(self) -> None:
        paths = [
            ROOT / "runtime/contexto.yaml",
            ROOT / "runtime/cena.yaml",
            ROOT / "runtime/eventos-pendentes.jsonl",
        ]
        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths
            if path.is_file()
        }
        raw = contexto.command_status(ROOT)
        decorated, budget = context_memory.decorate(
            raw,
            context_memory.classify("status"),
            requested_budget=99999,
            after=None,
            reason=None,
        )
        after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths
            if path.is_file()
        }

        receipt = decorated[context_memory.ACCESS_OBSERVATION_KEY]
        self.assertEqual(before, after)
        self.assertEqual(budget, 4096)
        self.assertEqual(receipt["module_id"], context_memory.MODULE_ID)
        self.assertEqual(receipt["nivel_acesso"], "L1")
        self.assertEqual(receipt["resultado_modular"], "contexto_suficiente")
        self.assertFalse(receipt["transcricao_lida"])

    def test_retomada_fria_e_completa_sem_transcricao(self) -> None:
        snapshot = retomada_cronica.current_snapshot(ROOT, include_memory=True)
        self.assertFalse(snapshot["transcricao_lida"])
        self.assertFalse(
            any(
                "transcricao" in source.casefold()
                for source in snapshot["fontes_lidas"]
            )
        )
        self.assertIn(context_memory.KEY, snapshot)
        self.assertEqual(snapshot[context_memory.KEY]["modo"], "completa")


class SceneAndDurableMemoryTest(unittest.TestCase):
    def test_recibo_de_cena_evitar_retransmissao_equivalente(self) -> None:
        docs = {"silva_fixture": scene_document()}
        first = context_memory.project_scene_memory(
            docs,
            scope="a" * 24,
            budget=context_memory.MAX_MEMORY_BYTES,
        )
        second = context_memory.project_scene_memory(
            docs,
            scope="a" * 24,
            budget=context_memory.MAX_MEMORY_BYTES,
            base=first["recibo"],
        )

        self.assertEqual(first["modo"], "completa")
        self.assertEqual(second["modo"], "delta")
        self.assertEqual(second["itens"], {})
        self.assertLess(context_memory.size(second), context_memory.size(first))

    def test_fato_duravel_preserva_destinatario_e_retry_nao_duplica(self) -> None:
        source = durable_information()
        compiled, _ = context_memory.compile_durable_memory(
            source,
            "transacao-rm07",
            3,
        )
        self.assertEqual(
            [delta["alvo"] for delta in compiled["deltas"]],
            ["relacao:silva_fixture"],
        )
        self.assertEqual(compiled["deltas"][0]["valor"]["estatuto"], "rumor")

        observation = context_memory.durable_persistence_observation(
            source,
            compiled,
        )
        first = context_memory.publish_memory_persistence(
            {"fase": "concluida", "transacao": {"ja_registrada": False}},
            observation,
        )[context_memory.MEMORY_PERSISTENCE_KEY]
        retry = context_memory.publish_memory_persistence(
            {"fase": "concluida", "transacao": {"ja_registrada": True}},
            observation,
        )[context_memory.MEMORY_PERSISTENCE_KEY]

        self.assertEqual(first["fatos_persistidos_novos"], 1)
        self.assertTrue(first["efeito_materializado"])
        self.assertEqual(retry["fatos_persistidos_novos"], 0)
        self.assertEqual(retry["fatos_confirmados"], 1)
        self.assertFalse(retry["efeito_materializado"])
        self.assertEqual(retry["resultado_modular"], "retry_sem_duplicacao")


if __name__ == "__main__":
    unittest.main()
