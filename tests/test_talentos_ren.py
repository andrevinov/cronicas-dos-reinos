from __future__ import annotations

import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import _rolar_dados_core as core
import ficha_ren
import politica_acesso
import retomada_cronica


def load_hyphenated(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"não foi possível carregar {filename}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


roller = load_hyphenated("ren_feat_roller", "rolar-dados.py")


class RenFeatCanonTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sheet = yaml.safe_load(
            (ROOT / "personagens/jogador/ficha.yaml").read_text(encoding="utf-8")
        )

    def test_talentos_sao_bonus_de_criacao_sem_consumir_movel_ou_asi(self):
        creation = self.sheet["criacao"]
        self.assertEqual(creation["talento_inicial"], "Móvel")
        self.assertEqual(creation["talentos_bonus_retroativos"], ["Actor", "Observant"])
        self.assertEqual(creation["escolha_observant"], "Inteligência")
        self.assertIn("movel", self.sheet["talentos"])
        self.assertIn("actor", self.sheet["talentos"])
        self.assertIn("observant", self.sheet["talentos"])
        self.assertEqual(
            self.sheet["aumentos_de_atributo"]["nivel_4"]["escolha"],
            "+1 Destreza, +1 Sabedoria",
        )

    def test_observant_escolhe_inteligencia_sem_buff_de_combate_indireto(self):
        attrs = self.sheet["atributos"]
        intelligence = attrs["inteligencia"]
        wisdom = attrs["sabedoria"]
        dexterity = attrs["destreza"]
        proficiency = self.sheet["proficiencia"]["bonus"]

        self.assertEqual(self.sheet["criacao"]["escolha_observant"], "Inteligência")
        self.assertEqual(intelligence["modificador"], (intelligence["valor"] - 10) // 2)
        self.assertEqual(wisdom["modificador"], (wisdom["valor"] - 10) // 2)
        if not intelligence["salvaguarda_proficiente"]:
            self.assertEqual(intelligence["bonus_salvaguarda"], intelligence["modificador"])
        self.assertEqual(
            self.sheet["combate"]["classe_de_armadura"]["valor"],
            10 + dexterity["modificador"] + wisdom["modificador"],
        )
        self.assertEqual(
            self.sheet["recursos_de_classe"]["focus"]["cd"],
            8 + proficiency + wisdom["modificador"],
        )

    def test_actor_e_observant_produzem_relacoes_mecanicas_corretas(self):
        attrs = self.sheet["atributos"]
        skills = self.sheet["pericias"]
        senses = self.sheet["sentidos"]
        proficiency = self.sheet["proficiencia"]["bonus"]
        int_mod = attrs["inteligencia"]["modificador"]
        wis_mod = attrs["sabedoria"]["modificador"]
        cha_mod = attrs["carisma"]["modificador"]

        self.assertEqual(attrs["carisma"]["modificador"], (attrs["carisma"]["valor"] - 10) // 2)
        self.assertEqual(skills["investigacao"], int_mod + proficiency)
        self.assertEqual(skills["percepcao"], wis_mod + proficiency)
        for skill in ("historia", "religiao", "arcana", "natureza"):
            self.assertEqual(skills[skill], int_mod)
        self.assertEqual(skills["enganacao"], cha_mod)
        self.assertEqual(skills["atuacao"], cha_mod)
        self.assertEqual(senses["percepcao_passiva"], 10 + skills["percepcao"] + 5)
        self.assertEqual(senses["investigacao_passiva"], 10 + skills["investigacao"] + 5)
        self.assertEqual(senses["intuicao_passiva"], 10 + skills["intuicao"])

    def test_actor_aceita_identidade_inventada_e_separa_mimetismo(self):
        actor = self.sheet["talentos"]["actor"]
        self.assertIn("pessoa diferente de Ren Kagehira", actor["vantagem_outra_identidade"])
        self.assertIn("Shinta Ryoushi", actor["identidades_validas"])
        self.assertIn("inventada", actor["identidades_validas"])
        self.assertIn("pessoa real específica", actor["identidades_validas"])
        self.assertIn("benefício separado", actor["observacao"])
        self.assertIn("não é pré-requisito", actor["observacao"])
        self.assertIn("assumidamente como Ren", actor["observacao"])

    def test_decisao_congela_gatilho_e_proibe_reescrever_o_passado(self):
        text = (ROOT / "regras/decisoes.md").read_text(encoding="utf-8")
        self.assertIn("DEC-0007", text)
        self.assertIn("pessoa diferente de Ren Kagehira", text)
        self.assertIn("Shinta Ryoushi", text)
        self.assertIn("A vantagem e o mimetismo são benefícios separados", text)
        self.assertIn("não reescrevem cenas, rolagens, descobertas ou falhas já canonizadas", text)
        self.assertIn("não consomem o talento Móvel", text)


class RenFeatRollerTest(unittest.TestCase):
    class SequenceRng:
        def __init__(self, values):
            self.values = iter(values)
            self.calls = 0

        def randint(self, _low: int, _high: int) -> int:
            self.calls += 1
            return next(self.values)

    def test_core_consome_adaptador_da_ficha_canonica(self):
        mechanics = core.load_ren_mechanics()
        sheet = ficha_ren.load(ROOT / "personagens/jogador/ficha.yaml")
        self.assertEqual(mechanics.abilities, sheet.abilities)
        self.assertEqual(mechanics.skills, sheet.skills)
        self.assertEqual(mechanics.saves, sheet.saves)
        self.assertEqual(mechanics.passives, sheet.passives)

    def test_actor_so_entra_quando_outra_identidade_e_declarada(self):
        normal, _ = roller.prepare_argv(["ren", "pericia", "enganacao"])
        self.assertNotIn("--vantagem", normal)

        actor, _ = roller.prepare_argv(
            ["ren", "pericia", "enganacao", roller.ACTOR_FLAG]
        )
        self.assertEqual(roller.ACTOR_FLAG, "--actor-outra-identidade")
        self.assertIn("--vantagem", actor)
        self.assertNotIn(roller.ACTOR_FLAG, actor)

    def test_actor_funciona_para_atuacao_de_identidade_mas_nao_performance_comum(self):
        normal, _ = roller.prepare_argv(["ren", "pericia", "atuacao"])
        self.assertNotIn("--vantagem", normal)

        actor, _ = roller.prepare_argv(
            ["ren", "pericia", "atuacao", roller.ACTOR_FLAG]
        )
        self.assertIn("--vantagem", actor)
        with self.assertRaises(roller.FeatContextError):
            roller.prepare_argv(
                ["ren", "pericia", "percepcao", roller.ACTOR_FLAG]
            )

    def test_actor_cancela_desvantagem_em_vez_de_empilhar(self):
        actor, _ = roller.prepare_argv(
            [
                "ren",
                "pericia",
                "enganacao",
                "--desvantagem",
                roller.ACTOR_FLAG,
            ]
        )
        self.assertNotIn("--vantagem", actor)
        self.assertNotIn("--desvantagem", actor)

    def test_actor_aplica_vantagem_antes_do_rng_e_audita_saida(self):
        fixed = self.SequenceRng([4, 17])
        old_rng = roller._core.RNG
        roller._core.RNG = fixed
        try:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = roller.main(
                    [
                        "ren",
                        "pericia",
                        "enganacao",
                        "--cd",
                        "12",
                        roller.ACTOR_FLAG,
                    ]
                )
            self.assertEqual(code, 0)
            self.assertEqual(fixed.calls, 2)
            text = stdout.getvalue()
            self.assertIn("d20 com vantagem [4, 17] -> 17", text)
            self.assertIn("Sucesso", text)
            self.assertIn("Actor: vantagem por outra identidade aplicada", text)
        finally:
            roller._core.RNG = old_rng

    def test_actor_invalido_falha_antes_do_rng(self):
        class ForbiddenRng:
            def randint(self, _low, _high):
                raise AssertionError("RNG não deve ser chamado")

        old_rng = roller._core.RNG
        roller._core.RNG = ForbiddenRng()
        try:
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                code = roller.main(
                    ["ren", "pericia", "furtividade", roller.ACTOR_FLAG]
                )
            self.assertEqual(code, 2)
            self.assertIn("Actor só concede vantagem", stderr.getvalue())
        finally:
            roller._core.RNG = old_rng

    def test_passivo_e_consulta_sem_rng(self):
        expected = core.load_ren_mechanics().passives["percepcao"]
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = core.main(["ren", "passivo", "percepcao"])
        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue().strip(), f"Percepção passiva (Ren): {expected}.")


class RenFeatHotContextTest(unittest.TestCase):
    def test_runtime_quente_expoe_gatilho_sem_ambiguidade(self):
        runtime = yaml.safe_load(
            (ROOT / "runtime/contexto.yaml").read_text(encoding="utf-8")
        )
        mechanics = ficha_ren.load(ROOT / "personagens/jogador/ficha.yaml")
        cap = runtime["capacidades_contextuais"]
        actor = cap["actor"]
        self.assertEqual(
            cap["passivos"],
            {
                "percepcao": mechanics.passives["percepcao"],
                "investigacao": mechanics.passives["investigacao"],
            },
        )
        self.assertEqual(actor["flag_rolagem"], "--actor-outra-identidade")
        self.assertEqual(actor["vantagem_outra_identidade"], ["enganacao", "atuacao"])
        self.assertIn("real ou inventada", actor["gatilho"])
        self.assertIn("Shinta Ryoushi", actor["gatilho"])
        self.assertIn("não é pré-requisito", actor["mimetismo_separado"])
        self.assertIn("leitura_labial", cap["observant"])

    def test_l1_nao_descarta_actor_observant(self):
        runtime = yaml.safe_load(
            (ROOT / "runtime/contexto.yaml").read_text(encoding="utf-8")
        )
        compact = politica_acesso._compact_l1_result(runtime)
        expected = runtime["capacidades_contextuais"]
        actor = compact["capacidades_contextuais"]["actor"]
        self.assertEqual(
            compact["capacidades_contextuais"]["passivos"]["percepcao"],
            expected["passivos"]["percepcao"],
        )
        self.assertEqual(actor["flag_rolagem"], expected["actor"]["flag_rolagem"])
        self.assertIn("Shinta Ryoushi", actor["gatilho"])

    def test_retomada_carrega_capacidades_no_mesmo_pacote(self):
        runtime = yaml.safe_load(
            (ROOT / "runtime/contexto.yaml").read_text(encoding="utf-8")
        )
        snapshot = retomada_cronica.current_snapshot(ROOT)
        cap = snapshot["capacidades_contextuais"]
        expected = runtime["capacidades_contextuais"]
        self.assertEqual(cap["passivos"], expected["passivos"])
        self.assertEqual(
            cap["actor"]["vantagem_outra_identidade"],
            expected["actor"]["vantagem_outra_identidade"],
        )
        self.assertIn("inventada", cap["actor"]["gatilho"])


if __name__ == "__main__":
    unittest.main()
