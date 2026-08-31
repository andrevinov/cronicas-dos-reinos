from __future__ import annotations

import argparse
import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import contratos_operacionais as contracts
import cronica
import endpoints
import mundo


class OperationalDateContractTest(unittest.TestCase):
    def test_forma_canonica_e_aliases_inequivocos_convergem(self):
        expected = "17 Eleasis, 1372 DR"
        for value in (
            expected,
            "17 Eleasis 1372 DR",
            "17 eleasis 1372",
            "1372-08-17",
            "17/08/1372",
            "17-08-1372",
        ):
            with self.subTest(value=value):
                self.assertEqual(contracts.normalize_date(value), expected)

    def test_iso_europeu_nao_mudam_semantica_do_instante(self):
        canonical = mundo.parse_instant("17 Eleasis, 1372 DR", "06:00")
        self.assertEqual(cronica._instant_arg("1372-08-17", "06:00"), canonical)
        self.assertEqual(cronica._instant_arg("17/08/1372", "06:00"), canonical)

    def test_alias_numerico_invalido_falha_com_exemplos_sem_adivinhar(self):
        with self.assertRaises(contracts.OperationalContractError) as caught:
            contracts.normalize_date("1372-13-17")
        text = str(caught.exception)
        self.assertIn("1 e 12", text)
        self.assertIn("17 Eleasis, 1372 DR", text)

    def test_texto_ambiguo_nao_e_convertido_para_outra_data(self):
        raw = "amanhã de manhã"
        self.assertEqual(contracts.normalize_date(raw), raw)

    def test_endpoint_fronteira_existente_normaliza_sem_nova_porta(self):
        expected = {"schema_endpoint_deterministico": 1, "endpoint": "mundo.fronteira"}
        stdout = io.StringIO()
        with (
            mock.patch.object(endpoints._base, "boundary", return_value=expected) as boundary,
            contextlib.redirect_stdout(stdout),
        ):
            code = endpoints.main(
                [
                    "--repo",
                    str(ROOT),
                    "fronteira",
                    "--data",
                    "1372-08-17",
                    "--hora",
                    "06:00",
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(yaml.safe_load(stdout.getvalue()), expected)
        boundary.assert_called_once_with(
            ROOT,
            date="17 Eleasis, 1372 DR",
            hour="06:00",
        )


class OperationalTicketContractTest(unittest.TestCase):
    def payload(self):
        return {
            "schema_cronica_ticket": 1,
            "preparacao_id": "scene-prep-task25",
            "cena": {
                "scene_id": "s025-ticket",
                "npcs": [],
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

    def test_ticket_completo_continua_roundtrip(self):
        token, digest = cronica.encode_ticket(self.payload())
        self.assertEqual(cronica.decode_ticket(token), self.payload())
        self.assertEqual(cronica.ticket_id(token), digest)

    def test_linha_ticket_completa_e_alias_inequivoco(self):
        token, _ = cronica.encode_ticket(self.payload())
        self.assertEqual(cronica.decode_ticket(f"ticket: {token}"), self.payload())

    def test_ticket_id_curto_falha_com_instrucao_autossuficiente(self):
        token, digest = cronica.encode_ticket(self.payload())
        self.assertTrue(token.startswith("crn1."))
        with self.assertRaises(cronica.CronicaError) as caught:
            cronica.decode_ticket(digest)
        text = str(caught.exception)
        self.assertIn("ticket_id", text)
        self.assertIn("campo `ticket:` completo", text)
        self.assertIn("não chame `--help`", text)

    def test_linha_ticket_id_tambem_e_diagnosticada(self):
        with self.assertRaises(cronica.CronicaError) as caught:
            cronica.decode_ticket("ticket_id: 0123456789abcdef0123")
        self.assertIn("linha `ticket_id:`", str(caught.exception))

    def test_ticket_id_falha_antes_de_tentar_ler_transacao(self):
        _, digest = cronica.encode_ticket(self.payload())
        args = argparse.Namespace(cmd="concluir", ticket=digest, arquivo=None)
        with mock.patch.object(cronica.turno, "read_transaction") as read_transaction:
            with self.assertRaises(cronica.CronicaError) as caught:
                cronica._run_turn(ROOT, args)
        read_transaction.assert_not_called()
        self.assertIn("ticket_id", str(caught.exception))

    def test_preparacao_explica_ticket_sem_criar_novo_campo(self):
        with mock.patch.object(cronica._pending_gate, "prepare_gate", return_value=None):
            result = cronica.prepare(
                ROOT,
                scene_id="s025-ticket-hint",
                sidequest_signal=None,
            )
        discipline = result["contrato_conclusao"]["disciplina"]
        self.assertIn("campo `ticket:` completo", discipline)
        self.assertIn("nunca `ticket_id`", discipline)
        self.assertIn("Não chamar --help", discipline)
        self.assertNotIn("ticket_uso", result)
        self.assertLessEqual(
            len(yaml.safe_dump(result, allow_unicode=True, sort_keys=False).encode("utf-8")),
            cronica.MAX_PREP_OUTPUT_BYTES,
        )


class OperationalParserCompatibilityTest(unittest.TestCase):
    def _prepare(self, argv: list[str]):
        parser = cronica.build_parser()
        return parser.parse_args(
            [
                "preparar",
                "--cena-id",
                "s025-tags",
                "--sem-oportunidade-sidequest",
                *argv,
            ]
        )

    def test_tag_e_alias_da_flag_canonica(self):
        canonical = self._prepare(["--contexto-tag", "assunto:masao"])
        alias = self._prepare(["--tag", "assunto:masao"])
        self.assertEqual(canonical.contexto_tag, ["assunto:masao"])
        self.assertEqual(alias.contexto_tag, canonical.contexto_tag)

    def test_alias_e_canonica_podem_coexistir_sem_perder_ordem(self):
        args = self._prepare(
            [
                "--contexto-tag",
                "local:circo",
                "--tag",
                "assunto:masao",
            ]
        )
        self.assertEqual(args.contexto_tag, ["local:circo", "assunto:masao"])


class OperationalBudgetContractTest(unittest.TestCase):
    def test_baseline_congela_compatibilidade_sem_nova_infra(self):
        data = yaml.safe_load(
            (ROOT / "baseline/harden-operational-contracts-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(data["schema_orcamento_harden_operational_contracts"], 1)
        limits = data["limites"]
        self.assertEqual(limits["max_chamadas_operacionais_extras_turno_livre"], 0)
        self.assertEqual(limits["max_endpoints_novos"], 0)
        self.assertEqual(limits["max_schedulers_novos"], 0)
        self.assertEqual(limits["max_estados_novos"], 0)
        self.assertEqual(limits["max_scans_repo"], 0)
        self.assertTrue(all(data["invariantes"].values()))

    def test_roteador_usa_formas_autoritativas_que_ja_funcionam_no_venv(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("poetry run dados ren pericia", text)
        self.assertIn("poetry run dados-lote", text)
        self.assertNotIn("poetry run rolar-dados", text)
        self.assertNotIn("poetry run rolar-lote", text)
        self.assertIn("ferramentas/endpoints.py fronteira", text)
        self.assertLessEqual((ROOT / "AGENTS.md").stat().st_size, 12288)


if __name__ == "__main__":
    unittest.main()
