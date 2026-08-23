from __future__ import annotations

import importlib.util
import io
import subprocess
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import endpoints
import qualidade_abordagem as quality


def load_hyphenated(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"não foi possível carregar {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


roller = load_hyphenated("task20_roller", "rolar-dados.py")
batch = load_hyphenated("task20_batch", "rolar-lote.py")


class ApproachQualityPureTest(unittest.TestCase):
    def test_rubrica_mapeia_exatamente_zero_a_tres(self):
        cases = [
            ({}, 0, "direta"),
            (
                {"preparacao": "Ren preparou a ferramenta adequada antes de entrar."},
                1,
                "preparada",
            ),
            (
                {
                    "preparacao": "Ren preparou a ferramenta adequada antes de entrar.",
                    "informacao": "Ren usa o horário de troca da guarda que já descobriu.",
                },
                2,
                "forte",
            ),
            (
                {
                    "preparacao": "Ren preparou a ferramenta adequada antes de entrar.",
                    "informacao": "Ren usa o horário de troca da guarda que já descobriu.",
                    "adequacao": "Ren escolhe a entrada de serviço, feita para entregas discretas.",
                },
                3,
                "excepcional",
            ),
        ]
        for kwargs, expected, level in cases:
            with self.subTest(expected=expected):
                result = quality.evaluate(**kwargs)
                self.assertEqual(result["bonus"], expected)
                self.assertEqual(result["nivel"], level)
                self.assertEqual(len(result["criterios"]), expected)
                self.assertEqual(result["aplicacao"], "pre_rolagem")

    def test_ordem_dos_criterios_e_estavel(self):
        result = quality.evaluate(
            adequacao="A rota escolhida contorna diretamente o obstáculo principal.",
            preparacao="Ren deixou corda e gancho preparados antes de começar.",
            informacao="Ren usa a planta correta obtida durante a investigação.",
        )
        self.assertEqual(
            [item["id"] for item in result["criterios"]],
            ["preparacao", "informacao", "adequacao"],
        )

    def test_mesma_evidencia_nao_pontua_duas_dimensoes(self):
        evidence = "Ren usa a troca da guarda das vinte e duas horas."
        with self.assertRaisesRegex(quality.ApproachQualityError, "mesma evidência"):
            quality.evaluate(preparacao=evidence, informacao=evidence)

    def test_evidencia_vazia_curta_ou_grande_falha(self):
        for value in ("", "curta", "x" * (quality.MAX_EVIDENCE_CHARS + 1)):
            with self.subTest(value=len(value)):
                with self.assertRaises(quality.ApproachQualityError):
                    quality.evaluate(preparacao=value)

    def test_mesma_entrada_produz_mesmos_bytes(self):
        kwargs = {
            "preparacao": "Ren preparou a ferramenta adequada antes de entrar.",
            "informacao": "Ren usa o horário de troca da guarda que já descobriu.",
        }
        a = yaml.safe_dump(quality.evaluate(**kwargs), allow_unicode=True, sort_keys=False)
        b = yaml.safe_dump(quality.evaluate(**kwargs), allow_unicode=True, sort_keys=False)
        self.assertEqual(a.encode("utf-8"), b.encode("utf-8"))

    def test_compact_modifier_preserva_bonus_e_evidencia(self):
        result = quality.evaluate(
            preparacao="Ren preparou uma cobertura plausível antes da conversa."
        )
        compact = quality.compact_modifier(result)
        self.assertEqual(compact["tipo"], "qualidade_abordagem")
        self.assertEqual(compact["bonus"], 1)
        self.assertEqual(compact["criterios"][0]["id"], "preparacao")
        self.assertNotIn("regra", compact)


class ApproachQualityRollerTest(unittest.TestCase):
    class FixedRng:
        def __init__(self, value: int = 10):
            self.value = value
            self.calls = 0

        def randint(self, _low: int, _high: int) -> int:
            self.calls += 1
            return self.value

    class ForbiddenRng:
        def randint(self, _low: int, _high: int) -> int:
            raise AssertionError("RNG não deve ser chamado")

    def test_sem_abordagem_preserva_argv_byte_logico(self):
        argv = ["ren", "pericia", "furtividade", "--cd", "15"]
        adjusted, result = roller.prepare_argv(argv)
        self.assertEqual(adjusted, argv)
        self.assertEqual(result["bonus"], 0)

    def test_d20_soma_abordagem_ao_bonus_existente(self):
        adjusted, result = roller.prepare_argv(
            [
                "d20",
                "--bonus=4",
                "--abordagem-preparacao",
                "Ren preparou uma identidade de cobertura antes da abordagem.",
                "--abordagem-informacao",
                "Ren usa o nome do supervisor obtido na investigação anterior.",
            ]
        )
        self.assertEqual(result["bonus"], 2)
        self.assertIn("--bonus=6", adjusted)
        self.assertFalse(any(token.startswith("--abordagem-") for token in adjusted))

    def test_pericia_soma_abordagem_ao_bonus_extra_sem_tocar_ficha(self):
        adjusted, result = roller.prepare_argv(
            [
                "ren",
                "pericia",
                "furtividade",
                "--bonus-extra",
                "1",
                "--abordagem-adequacao",
                "Ren escolhe avançar pela faixa de sombra que cobre todo o corredor.",
            ]
        )
        self.assertEqual(result["bonus"], 1)
        index = adjusted.index("--bonus-extra")
        self.assertEqual(adjusted[index + 1], "2")
        self.assertEqual(roller.REN_SKILLS["furtividade"], 7)

    def test_abordagem_nao_e_aceita_em_ataque_save_iniciativa_dano_ou_npc(self):
        commands = [
            ["ren", "ataque", "wakizashi"],
            ["ren", "salvaguarda", "destreza"],
            ["ren", "iniciativa"],
            ["ren", "dano", "wakizashi"],
            ["npc", "d20", "--bonus", "2"],
        ]
        for command in commands:
            with self.subTest(command=command):
                with self.assertRaisesRegex(
                    quality.ApproachQualityError, "só se aplica"
                ):
                    roller.prepare_argv(
                        [
                            *command,
                            "--abordagem-preparacao",
                            "Esta preparação seria indevida neste tipo de rolagem.",
                        ]
                    )

    def test_evidencia_invalida_falha_antes_do_rng(self):
        old_rng = roller._core.RNG
        roller._core.RNG = self.ForbiddenRng()
        try:
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = roller.main(
                    [
                        "d20",
                        "--abordagem-preparacao",
                        "Ren estudou a planta antes de entrar no prédio.",
                        "--abordagem-informacao",
                        "Ren estudou a planta antes de entrar no prédio.",
                    ]
                )
            self.assertEqual(code, 2)
            self.assertIn("mesma evidência", stderr.getvalue())
        finally:
            roller._core.RNG = old_rng

    def test_bonus_e_aplicado_antes_do_dado_e_saida_fica_auditavel(self):
        fixed = self.FixedRng(10)
        old_rng = roller._core.RNG
        roller._core.RNG = fixed
        try:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = roller.main(
                    [
                        "ren",
                        "pericia",
                        "furtividade",
                        "--cd",
                        "20",
                        "--abordagem-preparacao",
                        "Ren preparou roupas e ferramentas adequadas antes da infiltração.",
                        "--abordagem-informacao",
                        "Ren usa o horário de ronda observado durante a vigilância anterior.",
                        "--abordagem-adequacao",
                        "Ren cruza o corredor somente pela zona de sombra contínua.",
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(fixed.calls, 1)
            text = stdout.getvalue()
            self.assertIn("d20 10 + 10 = 20", text)
            self.assertIn("Sucesso", text)
            self.assertIn("Abordagem +3", text)
            self.assertIn("preparacao, informacao, adequacao", text)
        finally:
            roller._core.RNG = old_rng

    def test_lote_reutiliza_a_mesma_porta_publica(self):
        outputs = batch.run_batch(
            TOOLS / "rolar-dados.py",
            [
                [
                    "d20",
                    "--bonus",
                    "0",
                    "--abordagem-preparacao",
                    "Ren preparou uma ferramenta específica antes deste teste.",
                ]
            ],
        )
        self.assertEqual(len(outputs), 1)
        self.assertIn("Abordagem +1", outputs[0])


class ApproachQualityEndpointTest(unittest.TestCase):
    def preview(self):
        return {
            "cena_id": "scene-quality",
            "preparacao_id": "prep-quality",
            "local": None,
            "npcs_canonicos": [],
            "contexto_tags": [],
            "candidatos_contextuais": [],
            "presencas_contextuais": [],
            "entradas_contextuais": [],
            "operacoes_contextuais": [],
            "direcoes_contextuais": [],
            "encontros": [],
            "fontes_lidas": ["x.yaml"],
        }

    def test_sem_evidencia_snapshot_permanece_igual_ao_core(self):
        preview = self.preview()
        self.assertEqual(
            endpoints.project_scene(preview),
            endpoints._ORIGINAL_PROJECT_SCENE(preview),
        )

    def test_abordagem_usa_campo_modificadores_ja_existente(self):
        result = endpoints.project_scene(
            self.preview(),
            approach_preparacao="Ren preparou a cobertura antes de chegar ao encontro.",
            approach_informacao="Ren usa o nome correto aprendido com uma fonte confiável.",
        )
        modifier = next(
            item for item in result["modificadores"] if item["tipo"] == "qualidade_abordagem"
        )
        self.assertEqual(modifier["bonus"], 2)
        self.assertEqual(modifier["aplicacao"], "pre_rolagem")
        self.assertEqual(result["schema_endpoint_deterministico"], 1)
        self.assertIn("qualidade_abordagem_pre_rolagem", result["filtros"])
        endpoints.validate_endpoint(result)

    def test_scene_continua_uma_unica_chamada_subjacente_e_zero_leitura_extra(self):
        preview = self.preview()
        with mock.patch.object(
            endpoints.cena_mundo, "prepare_scene", return_value=preview
        ) as call:
            result = endpoints.scene(
                ROOT,
                scene_id="scene-quality",
                approach_adequacao="Ren escolhe o método que explora diretamente a limitação do obstáculo.",
            )
        call.assert_called_once()
        self.assertEqual(result["modificadores"][0]["bonus"], 1)
        self.assertEqual(result["fontes_lidas"], ["x.yaml"])

    def test_parser_continua_com_cinco_portas_e_flags_so_na_cena(self):
        parser = endpoints.build_parser()
        sub = next(
            action
            for action in parser._actions
            if isinstance(action, __import__("argparse")._SubParsersAction)
        )
        self.assertEqual(
            set(sub.choices),
            {"cena", "fronteira", "pendencias", "direcao", "sidequest"},
        )
        scene_dests = {action.dest for action in sub.choices["cena"]._actions}
        direction_dests = {action.dest for action in sub.choices["direcao"]._actions}
        for dest in (
            "abordagem_preparacao",
            "abordagem_informacao",
            "abordagem_adequacao",
        ):
            self.assertIn(dest, scene_dests)
            self.assertNotIn(dest, direction_dests)


class ApproachQualityBudgetTest(unittest.TestCase):
    def test_contrato_bate_com_codigo_e_endpoint_existente(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/approach-quality-modifier-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        limits = contract["limites"]
        self.assertEqual(limits["criterios"], len(quality.CRITERIA))
        self.assertEqual(limits["bonus_maximo"], quality.MAX_BONUS)
        self.assertEqual(
            limits["max_evidencia_chars_por_criterio"], quality.MAX_EVIDENCE_CHARS
        )
        self.assertEqual(limits["max_leituras_por_avaliacao"], 0)
        self.assertEqual(limits["max_escritas_por_avaliacao"], 0)
        self.assertEqual(limits["max_chamadas_rng_adicionais"], 0)
        self.assertEqual(limits["max_endpoints_novos"], 0)
        self.assertEqual(contract["integracao"]["schema_endpoint_permanece"], endpoints.SCHEMA)
        self.assertEqual(contract["integracao"]["portas_endpoint_permanecem"], 5)
        self.assertEqual(contract["invariantes"]["rubrica"], list(quality.CRITERIA))

    def test_regra_da_mesa_congela_escopo_e_impossibilidade(self):
        policy = yaml.safe_load(
            (ROOT / "regras/qualidade-abordagem.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(policy["schema_qualidade_abordagem"], 1)
        self.assertEqual(policy["guardrails"]["max_bonus"], 3)
        self.assertTrue(policy["guardrails"]["avaliar_antes_do_rng"])
        self.assertTrue(policy["guardrails"]["nao_torna_acao_impossivel_possivel"])
        self.assertTrue(policy["guardrails"]["bonus_da_ficha_permanece_independente"])
        self.assertFalse("ataque" in policy["escopo"]["aplica"])
        self.assertIn("ataque", policy["escopo"]["nao_aplica"])


if __name__ == "__main__":
    unittest.main()
