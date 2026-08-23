from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica
import mundo


class CronicaTicketTest(unittest.TestCase):
    def payload(self, *, now_minute=None):
        return {
            "schema_cronica_ticket": 1,
            "preparacao_id": "scene-prep-abc123",
            "cena": {
                "scene_id": "s013-porto",
                "npcs": ["npc_a", "NPC B"],
                "place": "lower_trades",
                "action": "entrar",
                "tier": 2,
                "danger": "media",
                "context_tags": ["local:porto"],
                "now_minute": now_minute,
                "approach": {
                    "preparacao": "Ren preparou uma cobertura plausível antes da entrada.",
                    "informacao": None,
                    "adequacao": None,
                },
            },
        }

    def test_ticket_roundtrip_e_byte_estavel(self):
        payload = self.payload(now_minute=12345)
        token_a, digest_a = cronica.encode_ticket(payload)
        token_b, digest_b = cronica.encode_ticket(payload)
        self.assertEqual(token_a, token_b)
        self.assertEqual(digest_a, digest_b)
        self.assertEqual(cronica.decode_ticket(token_a), payload)
        self.assertEqual(cronica.ticket_id(token_a), digest_a)
        self.assertLessEqual(len(token_a), cronica.MAX_TICKET_CHARS)

    def test_ticket_alterado_falha_checksum_ou_decodificacao(self):
        token, _ = cronica.encode_ticket(self.payload())
        replacement = "A" if token[-1] != "A" else "B"
        corrupted = token[:-1] + replacement
        with self.assertRaises(cronica.CronicaError):
            cronica.decode_ticket(corrupted)

    def test_tempo_explicito_e_preservado_no_ticket(self):
        payload = self.payload(now_minute=9876)
        kwargs = cronica._scene_kwargs(payload)
        self.assertIsInstance(kwargs["now"], mundo.WorldInstant)
        self.assertEqual(kwargs["now"].minute, 9876)

    def test_tempo_omitido_continua_none_e_nao_congela_canon(self):
        payload = self.payload(now_minute=None)
        self.assertIsNone(cronica._scene_kwargs(payload)["now"])

    def test_payload_de_abordagem_viaja_sem_afetar_kwargs_de_confirmacao(self):
        payload = self.payload()
        self.assertEqual(
            cronica._approach_kwargs(payload)["approach_preparacao"],
            "Ren preparou uma cobertura plausível antes da entrada.",
        )
        self.assertNotIn("approach_preparacao", cronica._scene_kwargs(payload))


class CronicaPrepareTest(unittest.TestCase):
    def endpoint(self):
        return {
            "schema_endpoint_deterministico": 1,
            "ids": {
                "cena": "scene-x",
                "preparacao": "scene-prep-x",
                "local": None,
                "npcs": [],
                "encontros": [],
                "sidequests_potenciais": [],
                "presencas_contextuais": [],
                "entradas_contextuais": [],
                "operacoes_contextuais": [],
                "direcoes_contextuais": [],
                "candidatos_contextuais": [],
            },
            "filtros": ["resolucao_npc_canonica"],
            "disponibilidade": {"confirmacao": True},
            "gates": [],
            "modificadores": [
                {
                    "tipo": "qualidade_abordagem",
                    "aplicacao": "pre_rolagem",
                    "bonus": 1,
                }
            ],
            "fontes_lidas": ["x.yaml"],
        }

    def test_preparar_chama_um_endpoint_e_emite_ticket_autocontido(self):
        with mock.patch.object(cronica.endpoints, "scene", return_value=self.endpoint()) as scene:
            result = cronica.prepare(
                ROOT,
                scene_id="scene-x",
                context_tags=["local:porto"],
                approach_preparacao="Ren preparou uma rota de fuga antes da abordagem.",
            )
        scene.assert_called_once()
        self.assertEqual(result["fase"], "preparacao")
        self.assertEqual(result["ids"]["preparacao"], "scene-prep-x")
        self.assertEqual(result["modificadores"][0]["bonus"], 1)
        decoded = cronica.decode_ticket(result["ticket"])
        self.assertEqual(decoded["preparacao_id"], "scene-prep-x")
        self.assertEqual(decoded["cena"]["context_tags"], ["local:porto"])
        self.assertEqual(
            decoded["cena"]["approach"]["preparacao"],
            "Ren preparou uma rota de fuga antes da abordagem.",
        )
        rendered = yaml.safe_dump(result, allow_unicode=True, sort_keys=False).encode("utf-8")
        self.assertLessEqual(len(rendered), cronica.MAX_PREP_OUTPUT_BYTES)

    def test_preparar_nao_cria_runtime_operacional(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp)
            before = list(repo.rglob("*"))
            with mock.patch.object(cronica.endpoints, "scene", return_value=self.endpoint()):
                cronica.prepare(repo, scene_id="scene-x", context_tags=["assunto:x"])
            after = list(repo.rglob("*"))
        self.assertEqual(before, after)


class CronicaLifecycleTest(unittest.TestCase):
    def token(self):
        token, _ = cronica.encode_ticket(
            {
                "schema_cronica_ticket": 1,
                "preparacao_id": "scene-prep-x",
                "cena": {
                    "scene_id": "scene-x",
                    "npcs": ["npc_a"],
                    "place": None,
                    "action": None,
                    "tier": None,
                    "danger": None,
                    "context_tags": [],
                    "now_minute": None,
                    "approach": {
                        "preparacao": None,
                        "informacao": None,
                        "adequacao": None,
                    },
                },
            }
        )
        return token

    def transaction(self):
        return {
            "jogador": "Ren observa o corredor.",
            "narracao": "O corredor permanece silencioso.",
            "resumo": "Ren verifica o corredor.",
            "modo": "exploração",
            "deltas": [],
        }

    def committed(self):
        return {
            "cena_id": "scene-x",
            "preparacao_id": "scene-prep-x",
            "mutacoes_aplicadas": True,
            "resumo": {"encontros": 1},
            "fontes_lidas": ["cena.yaml"],
        }

    def registered(self):
        return {
            "id": "tx-1",
            "sessao": 13,
            "deltas": 0,
            "transcricao_escrita": True,
            "evento_escrito": True,
            "reparo_parcial": False,
            "ja_registrada": False,
            "consolidada": False,
            "checkpoint_mundo": None,
            "avisos": [],
        }

    def test_concluir_ordena_preflight_confirmacao_registro(self):
        order = []

        def preflight(_repo, _transaction):
            order.append("preflight")
            return {"id": "tx-1", "checkpoint_previsto": None}

        def confirm(*_args, **_kwargs):
            order.append("confirmar")
            return self.committed()

        def register(*_args, **_kwargs):
            order.append("registrar")
            return self.registered()

        with (
            mock.patch.object(cronica, "_preflight_registration", side_effect=preflight),
            mock.patch.object(cronica.cena_mundo, "confirm_scene", side_effect=confirm) as confirmation,
            mock.patch.object(cronica.turno, "register_transaction", side_effect=register) as registration,
            mock.patch.object(cronica.rodape_turno, "build_safe", return_value="RODAPE_CANONICO — ok"),
        ):
            result = cronica.conclude(ROOT, self.token(), self.transaction())
        self.assertEqual(order, ["preflight", "confirmar", "registrar"])
        confirmation.assert_called_once()
        registration.assert_called_once_with(ROOT, self.transaction())
        self.assertEqual(result["fase"], "concluida")
        self.assertTrue(result["cena"]["confirmada"])
        self.assertEqual(result["transacao"]["id"], "tx-1")
        self.assertEqual(result["rodape_canonico"], "RODAPE_CANONICO — ok")

    def test_confirmacao_falha_antes_de_qualquer_registro(self):
        with (
            mock.patch.object(
                cronica,
                "_preflight_registration",
                return_value={"id": "tx-1", "checkpoint_previsto": None},
            ),
            mock.patch.object(
                cronica.cena_mundo,
                "confirm_scene",
                side_effect=cronica.cena_mundo.SceneGateError("obsoleta"),
            ),
            mock.patch.object(cronica.turno, "register_transaction") as registration,
        ):
            with self.assertRaises(cronica.cena_mundo.SceneGateError):
                cronica.conclude(ROOT, self.token(), self.transaction())
        registration.assert_not_called()

    def test_falha_de_registro_apos_confirmacao_e_parcial_explicita(self):
        with (
            mock.patch.object(
                cronica,
                "_preflight_registration",
                return_value={"id": "tx-partial", "checkpoint_previsto": None},
            ),
            mock.patch.object(cronica.cena_mundo, "confirm_scene", return_value=self.committed()),
            mock.patch.object(
                cronica.turno,
                "register_transaction",
                side_effect=cronica.turno.TransactionError("falha de escrita"),
            ),
        ):
            with self.assertRaises(cronica.PartialConclusionError) as caught:
                cronica.conclude(ROOT, self.token(), self.transaction())
        self.assertEqual(caught.exception.transaction_id, "tx-partial")
        self.assertIn("reparo-pos-confirmacao", str(caught.exception))

    def test_confirmar_explicito_nao_registra_turno(self):
        with (
            mock.patch.object(cronica.cena_mundo, "confirm_scene", return_value=self.committed()) as confirmation,
            mock.patch.object(cronica.turno, "register_transaction") as registration,
        ):
            result = cronica.confirm(ROOT, self.token())
        confirmation.assert_called_once()
        registration.assert_not_called()
        self.assertEqual(result["fase"], "confirmacao")
        self.assertTrue(result["mutacoes_aplicadas"])

    def test_registrar_explicitamente_revalida_por_padrao(self):
        with (
            mock.patch.object(cronica, "_revalidate_ticket", return_value={}) as revalidate,
            mock.patch.object(cronica.turno, "register_transaction", return_value=self.registered()) as register,
            mock.patch.object(cronica.rodape_turno, "build_safe", return_value="RODAPE_CANONICO — ok"),
        ):
            result = cronica.register(ROOT, self.token(), self.transaction())
        revalidate.assert_called_once()
        register.assert_called_once()
        self.assertTrue(result["confirmacao_pendente"])

    def test_reparo_pos_confirmacao_pula_revalidacao_da_cena(self):
        with (
            mock.patch.object(cronica, "_revalidate_ticket") as revalidate,
            mock.patch.object(cronica.turno, "register_transaction", return_value=self.registered()),
            mock.patch.object(cronica.rodape_turno, "build_safe", return_value="RODAPE_CANONICO — ok"),
        ):
            cronica.register(
                ROOT,
                self.token(),
                self.transaction(),
                revalidate=False,
            )
        revalidate.assert_not_called()


class CronicaParserAndBudgetTest(unittest.TestCase):
    def test_parser_expoe_fluxo_e_portas_de_reparo(self):
        parser = cronica.build_parser()
        sub = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        self.assertEqual(
            set(sub.choices),
            {"preparar", "concluir", "registrar", "confirmar"},
        )
        self.assertIn(
            "reparo_pos_confirmacao",
            {action.dest for action in sub.choices["registrar"]._actions},
        )

    def test_budget_congela_duas_chamadas_no_fluxo_preferencial(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/unified-cronica-turn-cli-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(contract["schema_orcamento_cronica_turn_cli"], 1)
        self.assertEqual(contract["fluxo_preferencial"]["chamadas_operacionais_por_turno"], 2)
        self.assertEqual(contract["limites"]["max_ticket_chars"], cronica.MAX_TICKET_CHARS)
        self.assertEqual(
            contract["limites"]["max_saida_preparacao_bytes"],
            cronica.MAX_PREP_OUTPUT_BYTES,
        )
        self.assertEqual(contract["limites"]["max_endpoints_novos"], 0)
        self.assertTrue(contract["invariantes"]["ticket_autocontido_sem_persistencia"])
        self.assertTrue(contract["meta_rollout"]["proibido_inventar_reducao_sem_rollout"])

    def test_pyproject_instala_cronica_e_entrypoint_existe(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('cronica = "ferramentas.poetry_cli:cronica"', pyproject)
        from ferramentas import poetry_cli
        self.assertTrue(callable(poetry_cli.cronica))

    def test_endpoints_task10_continua_com_cinco_portas(self):
        import endpoints
        parser = endpoints.build_parser()
        sub = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        self.assertEqual(
            set(sub.choices),
            {"cena", "fronteira", "pendencias", "direcao", "sidequest"},
        )


if __name__ == "__main__":
    unittest.main()
