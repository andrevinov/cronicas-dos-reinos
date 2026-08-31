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
        self.assertEqual(
            (attrs["inteligencia"]["valor"], attrs["inteligencia"]["modificador"]),
            (14, 2),
        )
        self.assertEqual(attrs["inteligencia"]["bonus_salvaguarda"], 2)
        self.assertEqual(
            (attrs["sabedoria"]["valor"], attrs["sabedoria"]["modificador"]),
            (17, 3),
        )
        self.assertEqual(self.sheet["combate"]["classe_de_armadura"]["valor"], 17)
        self.assertEqual(self.sheet["recursos_de_classe"]["ki"]["cd"], 14)

    def test_actor_e_observant_produzem_os_numeros_corretos(self):
        attrs = self.sheet["atributos"]
        skills = self.sheet["pericias"]
        senses = self.sheet["sentidos"]
        self.assertEqual(
            (attrs["carisma"]["valor"], attrs["carisma"]["modificador"]),
            (11, 0),
        )
        self.assertEqual(skills["investigacao"], 5)
        self.assertEqual(skills["percepcao"], 6)
        for skill in ("historia", "religiao", "arcana", "natureza"):
            self.assertEqual(skills[skill], 2)
        self.assertEqual(skills["enganacao"], 0)
        self.assertEqual(skills["atuacao"], 0)
        self.assertEqual(senses["percepcao_passiva"], 21)
        self.assertEqual(senses["investigacao_passiva"], 20)
        self.assertEqual(senses["intuicao_passiva"], 16)

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
        self.assertEqual(mechanics.abilities["inteligencia"], 2)
        self.assertEqual(mechanics.abilities["carisma"], 0)
        self.assertEqual(mechanics.skills["investigacao"], 5)
        self.assertEqual(mechanics.skills["percepcao"], 6)
        self.assertEqual(mechanics.saves["inteligencia"], 2)
        self.assertEqual(mechanics.passives["percepcao"], 21)
        self.assertEqual(mechanics.passives["investigacao"], 20)

    def test_actor_so_entra_quando_outra_identidade_e_declarada(self):
        # Sem a declaração contextual, representa uma mentira feita assumidamente
        # como Ren: Actor não deve inventar vantagem.
        normal, _ = roller.prepare_argv(["ren", "pericia", "enganacao"])
        self.assertNotIn("--vantagem", normal)

        # A flag representa que o teste serve para estabelecer/sustentar uma
        # pessoa diferente de Ren — inclusive uma identidade inventada como Shinta.
        actor, _ = roller.prepare_argv(
            ["ren", "pericia", "enganacao", roller.ACTOR_FLAG]
        )
        self.assertEqual(roller.ACTOR_FLAG, "--actor-outra-identidade")
        self.assertIn("--vantagem", actor)
        self.assertNotIn(roller.ACTOR_FLAG, actor)

    def test_actor_funciona_para_atuacao_de_identidade_mas_nao_performance_comum(self):
        # Atuação comum, sem tentativa de passar-se por outra pessoa, não ganha Actor.
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
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            code = core.main(["ren", "passivo", "percepcao"])
        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue().strip(), "Percepção passiva (Ren): 21.")


class RenFeatHotContextTest(unittest.TestCase):
    def test_runtime_quente_expoe_gatilho_sem_ambiguidade(self):
        runtime = yaml.safe_load(
            (ROOT / "runtime/contexto.yaml").read_text(encoding="utf-8")
        )
        cap = runtime["capacidades_contextuais"]
        actor = cap["actor"]
        self.assertEqual(cap["passivos"], {"percepcao": 21, "investigacao": 20})
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
        actor = compact["capacidades_contextuais"]["actor"]
        self.assertEqual(
            compact["capacidades_contextuais"]["passivos"]["percepcao"], 21
        )
        self.assertEqual(actor["flag_rolagem"], "--actor-outra-identidade")
        self.assertIn("Shinta Ryoushi", actor["gatilho"])

    def test_retomada_carrega_capacidades_no_mesmo_pacote(self):
        snapshot = retomada_cronica.current_snapshot(ROOT)
        cap = snapshot["capacidades_contextuais"]
        self.assertEqual(cap["passivos"]["investigacao"], 20)
        self.assertEqual(
            cap["actor"]["vantagem_outra_identidade"],
            ["enganacao", "atuacao"],
        )
        self.assertIn("inventada", cap["actor"]["gatilho"])


if __name__ == "__main__":
    unittest.main()
