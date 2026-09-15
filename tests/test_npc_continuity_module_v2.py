from __future__ import annotations

from copy import deepcopy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml


ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica
import context_and_memory as context_memory
from ferramentas import preflight
import npc_continuity_and_social_behavior as continuity
import retomada_cronica


class NpcContinuityModuleContractTest(unittest.TestCase):
    def test_catalogo_alias_e_hot_paths_publicam_um_modulo(self) -> None:
        catalog = json.loads(
            (ROOT / "evaluation/catalogo-modulos-v2.json").read_text(encoding="utf-8")
        )
        module = next(
            item for item in catalog["modulos"] if item["id"] == continuity.MODULE_ID
        )
        aliases = {
            alias
            for capability in module["subcapacidades"]
            for alias in capability["aliases_v1"]
        }

        self.assertEqual(catalog["versao_catalogo"], "5.0.0")
        self.assertEqual(module["versao_implementacao"], continuity.IMPLEMENTATION_VERSION)
        self.assertEqual(module["versao_avaliacao"], "4.0.0")
        self.assertEqual(aliases, set(continuity.LEGACY_ALIASES))
        self.assertEqual(
            {item["id"] for item in module["subcapacidades"]},
            set(continuity.CAPABILITIES),
        )
        self.assertIs(cronica._npc_continuity, continuity)
        self.assertIs(cronica._scene_memory, context_memory)
        self.assertIs(cronica._durable, context_memory)
        self.assertIs(retomada_cronica.memoria_cena, context_memory)

        base_source = (TOOLS / "_cronica_nv14.py").read_text(encoding="utf-8")
        initiative_source = (TOOLS / "cronica_iniciativa.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("import memoria_duravel as _durable", base_source)
        self.assertNotIn("import memoria_cena as _scene_memory", base_source)
        self.assertNotIn("import iniciativa_elenco as _initiative", initiative_source)

    def test_preflight_publica_check_modular_unico(self) -> None:
        commands = [
            tuple(item.comando[1:])
            for item in preflight.checks(incluir_testes=False)
        ]
        target = (
            "ferramentas/npc_continuity_and_social_behavior.py",
            "check",
        )
        self.assertEqual(commands.count(target), 1)

    def test_fontes_continuam_com_donos_distintos_e_sem_estado_paralelo(self) -> None:
        self.assertEqual(
            set(continuity.SOURCE_OWNERSHIP),
            {
                "scene_cast",
                "npc_state",
                "relationship_and_memory",
                "identity",
                "reputation",
                "initiative_receipts",
                "name_catalog",
                "name_reservations",
            },
        )
        self.assertEqual(len(set(continuity.SOURCE_OWNERSHIP.values())), 8)
        report = continuity.check(ROOT)
        self.assertTrue(report["ok"], report["erros"])
        self.assertFalse(report["contrato"]["parallel_state"])
        self.assertEqual(report["contrato"]["additional_orchestration_calls"], 0)


class NpcContextAndBehaviorTest(unittest.TestCase):
    def test_presente_contactavel_mencionado_e_conhecido_nao_se_confundem(self) -> None:
        expected = {
            "presente": dict(present=["npc_fixture"], known=True),
            "contactavel": dict(contactable=["npc_fixture"], known=True),
            "mencionado": dict(mentioned=["npc_fixture"], known=True),
            "apenas_conhecido": dict(known=True),
        }
        for state, inputs in expected.items():
            with self.subTest(state=state):
                self.assertEqual(
                    continuity.classify_actor_context("npc_fixture", **inputs), state
                )

        self.assertEqual(
            continuity.classify_actor_context(
                "npc_fixture",
                present=["npc_fixture"],
                contactable=["npc_fixture"],
                mentioned=["npc_fixture"],
                known=True,
            ),
            "presente",
        )

    def test_voz_e_objetivo_usam_estrutura_e_gate_sem_executar_acao(self) -> None:
        fixture = yaml.safe_load(
            (ROOT / "tests/fixtures/personalidade-papeis.yaml").read_text(
                encoding="utf-8"
            )
        )
        role = fixture["npcs"]["silva_elkwood"]["papel_conversacional"]
        profile = continuity.project_voice("silva_elkwood", role)
        self.assertIsNotNone(profile)
        assert profile is not None
        for criterion in profile["estavel"].values():
            if criterion is None:
                continue
            source: object = role
            for part in criterion["origem"].strip("/").split("/"):
                source = source[int(part)] if isinstance(source, list) else source[part]  # type: ignore[index]
            self.assertEqual(criterion["texto"], source)

        options = [
            {
                "id": "visitar_aliado",
                "conduta": "visitar um aliado distante",
                "favorece": {},
                "contraria": {},
                "viabilidade": {
                    "conhecimento": True,
                    "capacidade": True,
                    "recursos": True,
                    "presenca_ou_canal": False,
                    "autoridade": True,
                },
            }
        ]
        decision = continuity.evaluate_autonomous_options(profile, options)
        self.assertEqual(decision["alternativas"][0]["status"], "inviavel_declarada")
        self.assertFalse(decision["executa_acao"])
        self.assertFalse(decision["sucesso_garantido"])

    def test_informacao_transmitida_nao_vaza_para_terceiro_participante(self) -> None:
        text = "Ren disse a Silva que a ponte caiu, mas apresentou isso apenas como rumor."
        transaction = {
            "jogador": "Ren conversa com Silva.",
            "narracao": text,
            "resumo": "Silva recebeu um rumor.",
            "deltas": [],
            "memoria": {
                "versao": 1,
                "fatos": [
                    {
                        "id": "ponte",
                        "tipo": "informacao",
                        "participantes": ["ren", "silva_fixture", "nera_fixture"],
                        "evidencia": {"campo": "narracao", "trecho": text},
                        "texto": text,
                        "emissor": "ren",
                        "destinatario": "silva_fixture",
                        "canal": "presencial",
                        "estatuto": "rumor",
                    }
                ],
            },
        }
        writer, _ = continuity._durable.compile_transaction(
            transaction, "tx-conhecimento-dirigido", 3
        )
        targets = [delta["alvo"] for delta in writer["deltas"]]
        self.assertEqual(targets, ["relacao:silva_fixture"])
        self.assertNotIn("relacao:nera_fixture", targets)
        self.assertEqual(writer["deltas"][0]["valor"]["estatuto"], "rumor")

    def test_mudanca_relacional_solta_falha_e_fato_duravel_gera_par_atomico(self) -> None:
        loose = {
            "deltas": [
                {
                    "alvo": "npc:silva_fixture",
                    "op": "inc",
                    "caminho": "medidores.confianca",
                    "valor": 1,
                    "fato_canonico": "Silva reconheceu uma escolha concreta de Ren nesta conversa.",
                    "fonte": "fixture:rm05",
                }
            ]
        }
        with self.assertRaisesRegex(
            continuity.DurableMemoryError, "memoria.fatos tipo relacao"
        ):
            continuity._require_durable_relationship_facts(loose)

        text = "Silva agradeceu a franqueza de Ren e passou a confiar mais nele."
        durable = {
            "jogador": "Ren fala com franqueza.",
            "narracao": text,
            "resumo": text,
            "deltas": [],
            "memoria": {
                "versao": 1,
                "fatos": [
                    {
                        "id": "confianca",
                        "tipo": "relacao",
                        "participantes": ["ren", "silva_fixture"],
                        "evidencia": {"campo": "narracao", "trecho": text},
                        "npc": "silva_fixture",
                        "eixo": "confianca",
                        "anterior": 5,
                        "variacao": 1,
                    }
                ],
            },
        }
        writer, _ = continuity._durable.compile_transaction(
            durable, "tx-relacao-atomica", 3
        )
        self.assertEqual(len(writer["deltas"]), 2)
        self.assertEqual(
            {(delta["alvo"], delta["op"]) for delta in writer["deltas"]},
            {("npc:silva_fixture", "inc"), ("relacao:silva_fixture", "append")},
        )

        observation = continuity.social_persistence_observation(durable)
        self.assertEqual(
            observation,
            {
                "schema_npc_continuity": 2,
                "module_id": continuity.MODULE_ID,
                "fatos_sociais_persistidos": 1,
                "fatos_sociais_com_evidencia": 1,
                "por_tipo": {
                    "informacao": 0,
                    "relacao": 1,
                    "promessa": 0,
                    "marco": 0,
                },
            },
        )
        result = continuity.publish_social_persistence(
            {"fase": "concluida"}, observation
        )
        self.assertEqual(result[continuity.SOCIAL_PERSISTENCE_KEY], observation)
        self.assertEqual(result["sistemas_narrativos"], [continuity.MODULE_ID])

    def test_sem_fato_social_nao_decora_conclusao(self) -> None:
        result = {"fase": "concluida"}
        self.assertIsNone(continuity.social_persistence_observation(result))
        self.assertIs(continuity.publish_social_persistence(result, None), result)
        self.assertNotIn(continuity.SOCIAL_PERSISTENCE_KEY, result)

    def test_interlocutor_apenas_mencionado_permanece_inelegivel(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repo = Path(temporary)
            indexes = [{"npc_fixture": {"arquivo": "estado/npcs/npc_fixture.yaml"}}, {}, {}]
            out, meta = continuity.prepare_initiative(
                repo,
                {"fontes_lidas": [], "contrato_conclusao": {}},
                {"cena": {"scene_id": "cena-rm05", "npcs": [], "place": None}},
                interlocutors=["npc_fixture"],
                physical=[],
                contactable=[],
                mentioned=["npc_fixture"],
                docs={},
                indexes=indexes,
                scene_mode="interacao",
            )
        item = out[continuity.INITIATIVE_PUBLIC_KEY]["itens"][0]
        self.assertEqual(item["contexto_npc"], "mencionado")
        self.assertEqual(item["presenca"], "ausente")
        self.assertEqual(item["resultado_automatico"], "nao_elegivel")
        self.assertEqual(item["motivo_automatico"], "ausencia")
        self.assertIsNone(out[continuity.INITIATIVE_PUBLIC_KEY]["selecionada"])
        metrics = out[continuity.INITIATIVE_PUBLIC_KEY]["metricas"]
        self.assertEqual(metrics["elegiveis_por_presenca_ou_contato"], 0)
        self.assertEqual(metrics["silencios_explicitos"], 1)
        self.assertEqual(metrics["contextos"]["mencionado"], 1)
        self.assertNotIn("pressao_narrativa", out)
        self.assertNotIn("sidequest", yaml.safe_dump(meta, allow_unicode=True))


class NpcContinuityCostAndResumeTest(unittest.TestCase):
    def test_turno_sem_npc_delega_sem_nova_leitura_ou_decoracao(self) -> None:
        sentinel = {"fase": "preparacao", "ticket": "fixture"}
        with (
            continuity.interlocutors(None),
            patch.object(
                continuity._scene_social, "_BASE_ATTACH", return_value=sentinel
            ) as base,
            patch.object(Path, "read_text", side_effect=AssertionError("leitura extra")),
        ):
            result = continuity.attach(
                Path("/fixture"),
                sentinel,
                decode_ticket=lambda _: {},
                encode_ticket=lambda _: ("", ""),
            )
        self.assertIs(result, sentinel)
        base.assert_called_once()

    def test_retomada_fria_delega_uma_vez_e_preserva_pacote_estruturado(self) -> None:
        base = {"sessao": 22}
        projected = {
            **base,
            continuity.KEY: {
                "versao": 1,
                "modo": "completa",
                "itens": {"npc_fixture": {"relacao": {"dados": {"confianca": 6}}}},
            },
        }
        with patch.object(
            continuity._scene_memory, "resume", return_value=deepcopy(projected)
        ) as resume:
            result = continuity.resume(Path("/fixture"), base)
        resume.assert_called_once()
        self.assertEqual(result, projected)
        self.assertEqual(result[continuity.KEY]["modo"], "completa")


if __name__ == "__main__":
    unittest.main()
