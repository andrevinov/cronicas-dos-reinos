from __future__ import annotations

import copy
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

import _cronica_turn_core as turn_core
import cronica
import mecanica_cronica


class MechanicalRepo:
    def __init__(self, root: Path, *, focus: int = 1):
        self.root = root
        (root / "regras").mkdir(parents=True)
        (root / "estado").mkdir(parents=True)
        (root / "regras/resolucao-de-acoes.md").write_text(
            "# Resolução de ações\n\n## Fórmula básica\n\nd20 + modificador.\n\n"
            "## Gasto de recursos de classe\n\nGastos são declarados antes da consequência.\n",
            encoding="utf-8",
        )
        campaign = {
            "sistema": {
                "ruleset": {
                    "atual": "dnd_5_5e",
                    "alvo": "dnd_5_5e",
                    "hierarquia_mecanica": ["ruleset_atual"],
                }
            }
        }
        (root / "campanha.yaml").write_text(
            yaml.safe_dump(campaign, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        catalog = {
            "schema_catalogo_regras": 1,
            "natureza": "indice_executavel",
            "contrato": {
                "fonte_ruleset": "campanha.yaml#sistema.ruleset",
                "fallback_textual": True,
                "nivel_consulta_catalogada": "L2",
                "max_resultado_l2_bytes": 8192,
            },
            "regras": [
                {
                    "id": "teste_d20_basico",
                    "aliases": ["teste"],
                    "dominio": "resolucao",
                    "ruleset": "dnd_5_5e",
                    "autoridade": "ruleset_atual",
                    "fonte": {"arquivo": "regras/resolucao-de-acoes.md", "secao": "Fórmula básica"},
                    "resumo_interno": "Teste d20 contra alvo fixado antes da rolagem.",
                    "executor": "dados",
                    "persistencia": "nenhuma",
                    "house_rule": None,
                },
                {
                    "id": "gasto_recurso_classe",
                    "aliases": ["gasto focus"],
                    "dominio": "recursos",
                    "ruleset": "dnd_5_5e",
                    "autoridade": "ruleset_atual",
                    "fonte": {"arquivo": "regras/resolucao-de-acoes.md", "secao": "Gasto de recursos de classe"},
                    "resumo_interno": "O recurso precisa existir e estar disponível antes do gasto.",
                    "executor": "cronica",
                    "persistencia": "turno_transacional",
                    "house_rule": None,
                },
            ],
        }
        (root / "regras/catalogo.yaml").write_text(
            yaml.safe_dump(catalog, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        self.write_focus(focus)

    def write_focus(self, current: int) -> None:
        state = {"recursos": {"focus": {"atuais": current, "maximos": 7}}}
        (self.root / "estado/estado-atual.yaml").write_text(
            yaml.safe_dump(state, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

    def check_spec(self, *, effects=None) -> dict:
        obligation = {
            "id": "checagem",
            "tipo": "teste",
            "regra": "teste",
            "bonus": 5,
            "alvo": 15,
            "modo": "normal",
        }
        if effects is not None:
            obligation["efeitos"] = effects
        return {"regras": ["teste"], "obrigacoes": [obligation]}

    def spend_spec(self, cost: int = 1) -> dict:
        return {
            "regras": ["gasto focus"],
            "obrigacoes": [
                {
                    "id": "focus_darkness",
                    "tipo": "gasto_recurso",
                    "regra": "gasto focus",
                    "recurso": "focus",
                    "custo": cost,
                }
            ],
        }


def base_transaction(*, deltas=None, mechanical=None) -> dict:
    tx = {
        "jogador": "Ren age.",
        "narracao": "A consequência é resolvida.",
        "resumo": "Turno de teste.",
        "modo": "exploração",
        "deltas": list(deltas or []),
    }
    if mechanical is not None:
        tx["mecanica"] = mechanical
    return tx


class CronicaMechanicalContractTest(unittest.TestCase):
    def test_atalho_gasto_focus_compila_para_contrato_mecanico(self) -> None:
        parser = cronica.build_parser()
        args = parser.parse_args(
            [
                "preparar",
                "--cena-id",
                "atalho-focus",
                "--sem-oportunidade-sidequest",
                "--gasto-focus",
                "1",
            ]
        )
        self.assertEqual(
            cronica._mechanical_spec_from_args(args),
            {
                "regras": ["gasto_recurso_classe"],
                "obrigacoes": [
                    {
                        "id": "focus_spend",
                        "tipo": "gasto_recurso",
                        "regra": "gasto_recurso_classe",
                        "recurso": "focus",
                        "custo": 1,
                    }
                ],
            },
        )

    def test_atalho_gasto_focus_recusa_custo_invalido_e_json_concorrente(self) -> None:
        parser = cronica.build_parser()
        invalid = parser.parse_args(
            [
                "preparar",
                "--cena-id",
                "atalho-focus-invalido",
                "--sem-oportunidade-sidequest",
                "--gasto-focus",
                "0",
            ]
        )
        with self.assertRaisesRegex(turn_core.CronicaError, "inteiro positivo"):
            cronica._mechanical_spec_from_args(invalid)

        conflict = parser.parse_args(
            [
                "preparar",
                "--cena-id",
                "atalho-focus-conflito",
                "--sem-oportunidade-sidequest",
                "--gasto-focus",
                "1",
                "--mecanica-json",
                '{"regras":[],"obrigacoes":[]}',
            ]
        )
        with self.assertRaisesRegex(turn_core.CronicaError, "mutuamente exclusivos"):
            cronica._mechanical_spec_from_args(conflict)

    def test_turno_puramente_narrativo_nao_abre_catalogo_nem_estado(self) -> None:
        base = {"ticket": "irrelevante", "ticket_id": "x"}
        with mock.patch.object(
            mecanica_cronica.catalogo_regras, "load_catalog", side_effect=AssertionError("catálogo não deve abrir")
        ), mock.patch.object(
            mecanica_cronica, "_resource_state", side_effect=AssertionError("estado não deve abrir")
        ):
            result = mecanica_cronica.attach_to_prepare(
                ROOT,
                base,
                None,
                decode_ticket=lambda _token: {},
                encode_ticket=lambda _payload: ("novo", "id"),
                max_ticket_chars=4096,
                max_output_bytes=8192,
            )
        self.assertIs(result, base)

    def test_focus_nao_pode_ficar_negativo_e_gasto_exige_disponibilidade(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture = MechanicalRepo(repo, focus=1)
            ok = mecanica_cronica.normalize_spec(repo, fixture.spend_spec(1))
            self.assertEqual(ok["snapshot_recursos"]["focus"]["atuais"], 1)
            with self.assertRaisesRegex(mecanica_cronica.MechanicalContractError, "recurso insuficiente"):
                mecanica_cronica.normalize_spec(repo, fixture.spend_spec(2))

            fixture.write_focus(0)
            with self.assertRaisesRegex(mecanica_cronica.MechanicalContractError, "recurso insuficiente"):
                mecanica_cronica.normalize_spec(repo, fixture.spend_spec(1))

    def test_ticket_mecanico_fica_obsoleto_quando_recurso_muda(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture = MechanicalRepo(repo, focus=1)
            contract = mecanica_cronica.normalize_spec(repo, fixture.spend_spec())
            payload = {mecanica_cronica.TICKET_KEY: contract}
            fixture.write_focus(0)
            with self.assertRaisesRegex(mecanica_cronica.MechanicalTicketStaleError, "obsoleto"):
                mecanica_cronica.revalidate_ticket(repo, payload)

    def test_gasto_exige_resolucao_e_delta_exatos(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture = MechanicalRepo(repo, focus=1)
            contract = mecanica_cronica.normalize_spec(repo, fixture.spend_spec())
            payload = {mecanica_cronica.TICKET_KEY: contract}
            delta = {"alvo": "estado", "op": "inc", "caminho": "recursos.focus.atuais", "valor": -1}
            resolution = {
                "resolucoes": [
                    {"obrigacao_id": "focus_darkness", "tipo": "gasto_recurso", "aplicado": True}
                ]
            }
            clean = mecanica_cronica.validate_transaction(
                repo, payload, base_transaction(deltas=[delta], mechanical=resolution)
            )
            self.assertNotIn("mecanica", clean)
            self.assertEqual(clean["deltas"], [delta])

            with self.assertRaisesRegex(mecanica_cronica.MechanicalContractError, "exige exatamente um delta"):
                mecanica_cronica.validate_transaction(
                    repo, payload, base_transaction(deltas=[], mechanical=resolution)
                )

    def test_gasto_sem_ticket_mecanico_e_recusado(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            MechanicalRepo(repo, focus=1)
            delta = {"alvo": "estado", "op": "inc", "caminho": "recursos.focus.atuais", "valor": -1}
            with self.assertRaisesRegex(mecanica_cronica.MechanicalContractError, "exige obrigação"):
                mecanica_cronica.validate_transaction(repo, {}, base_transaction(deltas=[delta]))

    def test_ticket_resolucao_incompativel_falha(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture = MechanicalRepo(repo)
            contract = mecanica_cronica.normalize_spec(repo, fixture.check_spec())
            payload = {mecanica_cronica.TICKET_KEY: contract}
            wrong = {
                "resolucoes": [
                    {
                        "obrigacao_id": "outra",
                        "tipo": "teste",
                        "rolagens": [10],
                        "escolhido": 10,
                        "total": 15,
                        "resultado": "sucesso",
                    }
                ]
            }
            with self.assertRaisesRegex(mecanica_cronica.MechanicalContractError, "ticket/resolução incompatível"):
                mecanica_cronica.validate_transaction(repo, payload, base_transaction(mechanical=wrong))

    def test_resolucao_d20_e_recalculada_pelo_nucleo_e_governa_consequencia(self) -> None:
        success_delta = {"alvo": "estado", "op": "inc", "caminho": "marcadores.teste", "valor": 1}
        failure_delta = {"alvo": "estado", "op": "inc", "caminho": "marcadores.teste", "valor": -1}
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture = MechanicalRepo(repo)
            contract = mecanica_cronica.normalize_spec(
                repo,
                fixture.check_spec(effects={"sucesso": [success_delta], "falha": [failure_delta]}),
            )
            payload = {mecanica_cronica.TICKET_KEY: contract}
            receipt = {
                "resolucoes": [
                    {
                        "obrigacao_id": "checagem",
                        "tipo": "teste",
                        "rolagens": [10],
                        "escolhido": 10,
                        "total": 15,
                        "resultado": "sucesso",
                    }
                ]
            }
            with mock.patch.object(
                mecanica_cronica.dnd, "perform_check", wraps=mecanica_cronica.dnd.perform_check
            ) as core_call:
                clean = mecanica_cronica.validate_transaction(
                    repo, payload, base_transaction(deltas=[success_delta], mechanical=receipt)
                )
            core_call.assert_called_once()
            self.assertEqual(clean["deltas"], [success_delta])

            with self.assertRaisesRegex(mecanica_cronica.MechanicalContractError, "consequência mecânica incompatível"):
                mecanica_cronica.validate_transaction(
                    repo, payload, base_transaction(deltas=[failure_delta], mechanical=receipt)
                )

            forged = copy.deepcopy(receipt)
            forged["resolucoes"][0]["total"] = 99
            with self.assertRaisesRegex(mecanica_cronica.MechanicalContractError, "diverge da primitiva"):
                mecanica_cronica.validate_transaction(
                    repo, payload, base_transaction(deltas=[success_delta], mechanical=forged)
                )

    def test_attach_emite_ids_e_obrigacoes_no_ticket(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture = MechanicalRepo(repo)
            token, ticket_id = turn_core.encode_ticket(
                {
                    "schema_cronica_ticket": turn_core.SCHEMA,
                    "preparacao_id": "turn-neutral-test",
                    "cena": {
                        "scene_id": "teste",
                        "npcs": [],
                        "place": None,
                        "action": None,
                        "tier": None,
                        "danger": None,
                        "context_tags": [],
                        "agora": None,
                        "approach": {"preparacao": None, "informacao": None, "adequacao": None},
                    },
                }
            )
            base = {"ticket": token, "ticket_id": ticket_id, "contrato_conclusao": {"campos": {}}}
            result = mecanica_cronica.attach_to_prepare(
                repo,
                base,
                fixture.check_spec(),
                decode_ticket=turn_core.decode_ticket,
                encode_ticket=turn_core.encode_ticket,
                max_ticket_chars=turn_core.MAX_TICKET_CHARS,
                max_output_bytes=turn_core.MAX_PREP_OUTPUT_BYTES,
            )
            payload = turn_core.decode_ticket(result["ticket"])
            self.assertEqual(result["mecanica"]["regras"], ["teste_d20_basico"])
            self.assertEqual(result["mecanica"]["obrigacoes"][0]["id"], "checagem")
            self.assertEqual(
                result["mecanica"]["resolucao_modelo"]["resolucoes"][0]["obrigacao_id"],
                "checagem",
            )
            self.assertIn(mecanica_cronica.TICKET_KEY, payload)
            self.assertIn("mecanica", result["contrato_conclusao"]["campos"])

    def test_modelo_de_resolucao_de_gasto_e_concreto(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture = MechanicalRepo(repo)
            contract = mecanica_cronica.normalize_spec(repo, fixture.spend_spec())
            summary = mecanica_cronica.public_summary(contract)
            self.assertEqual(
                summary["resolucao_modelo"],
                {
                    "resolucoes": [
                        {
                            "obrigacao_id": "focus_darkness",
                            "tipo": "gasto_recurso",
                            "aplicado": True,
                        }
                    ]
                },
            )

    def test_meta_de_duas_chamadas_de_orquestracao_permanece(self) -> None:
        budget = yaml.safe_load(
            (ROOT / "baseline/unified-cronica-turn-cli-orcamento.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(budget["fluxo_preferencial"]["chamadas_operacionais_por_turno"], 2)
        self.assertEqual(budget["limites"]["max_endpoints_novos"], 0)


class PublicCronicaMechanicalIntegrationTest(unittest.TestCase):
    def test_concluir_valida_mecanica_antes_de_delegar_e_writer_nao_recebe_envelope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture = MechanicalRepo(repo, focus=1)
            contract = mecanica_cronica.normalize_spec(repo, fixture.spend_spec())
            payload = {
                "schema_cronica_ticket": turn_core.SCHEMA,
                "preparacao_id": "turn-neutral-test",
                "cena": {
                    "scene_id": "teste",
                    "npcs": [],
                    "place": None,
                    "action": None,
                    "tier": None,
                    "danger": None,
                    "context_tags": [],
                    "agora": None,
                    "approach": {"preparacao": None, "informacao": None, "adequacao": None},
                },
                mecanica_cronica.TICKET_KEY: contract,
            }
            token, _ = turn_core.encode_ticket(payload)
            delta = {"alvo": "estado", "op": "inc", "caminho": "recursos.focus.atuais", "valor": -1}
            tx = base_transaction(
                deltas=[delta],
                mechanical={
                    "resolucoes": [
                        {"obrigacao_id": "focus_darkness", "tipo": "gasto_recurso", "aplicado": True}
                    ]
                },
            )
            with mock.patch.object(cronica, "_conclude_base", return_value={"ok": True}) as delegate:
                result = cronica.conclude(repo, token, tx)
            self.assertTrue(result["ok"])
            delegated = delegate.call_args.args[2]
            self.assertNotIn("mecanica", delegated)
            self.assertEqual(delegated["deltas"], [delta])


if __name__ == "__main__":
    unittest.main()
