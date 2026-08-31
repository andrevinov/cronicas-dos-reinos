from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import _rolar_dados_core as core
import mecanica_dnd_5_5e as mechanics


class SequenceRng:
    def __init__(self, values: list[int]):
        self.values = iter(values)
        self.calls = 0

    def randint(self, low: int, high: int) -> int:
        self.calls += 1
        value = next(self.values)
        if not low <= value <= high:
            raise AssertionError(f"valor de teste fora da faixa {low}..{high}: {value}")
        return value


class ForbiddenRng:
    def __init__(self):
        self.calls = 0

    def randint(self, _low: int, _high: int) -> int:
        self.calls += 1
        raise AssertionError("RNG não deve ser chamado")


class Dnd55MechanicsCoreTest(unittest.TestCase):
    def test_identidade_do_ruleset_e_ausencia_de_dependencia_de_ren(self) -> None:
        self.assertEqual(mechanics.RULESET_ID, "dnd_5_5e")
        source = (TOOLS / "mecanica_dnd_5_5e.py").read_text(encoding="utf-8")
        self.assertNotIn("ficha_ren", source)
        self.assertNotIn("Ren Kagehira", source)

    def test_core_publico_reexporta_tipos_mas_delega_a_regra(self) -> None:
        self.assertIs(core.DiceSpec, mechanics.DiceSpec)
        self.assertIs(core.DiceRoll, mechanics.DiceRoll)
        self.assertIs(core.D20Roll, mechanics.D20Roll)
        source = (TOOLS / "_rolar_dados_core.py").read_text(encoding="utf-8")
        self.assertNotIn("class DiceSpec", source)
        self.assertNotIn("class D20Roll", source)
        self.assertNotIn("DICE_PATTERN =", source)

    def test_rng_controlado_normal_vantagem_e_desvantagem(self) -> None:
        normal_rng = SequenceRng([11])
        normal = mechanics.roll_d20(3, "normal", rng=normal_rng)
        self.assertEqual((normal.rolls, normal.chosen, normal.total), ([11], 11, 14))
        self.assertEqual(normal_rng.calls, 1)

        advantage_rng = SequenceRng([4, 17])
        advantage = mechanics.roll_d20(2, "vantagem", rng=advantage_rng)
        self.assertEqual((advantage.rolls, advantage.chosen, advantage.total), ([4, 17], 17, 19))
        self.assertEqual(advantage_rng.calls, 2)

        disadvantage_rng = SequenceRng([4, 17])
        disadvantage = mechanics.roll_d20(2, "desvantagem", rng=disadvantage_rng)
        self.assertEqual((disadvantage.rolls, disadvantage.chosen, disadvantage.total), ([4, 17], 4, 6))
        self.assertEqual(disadvantage_rng.calls, 2)

    def test_fontes_de_vantagem_e_desvantagem_nao_empilham_e_se_cancelam(self) -> None:
        self.assertEqual(mechanics.combine_roll_modes(), "normal")
        self.assertEqual(mechanics.combine_roll_modes("vantagem", "vantagem"), "vantagem")
        self.assertEqual(
            mechanics.combine_roll_modes("desvantagem", "desvantagem"),
            "desvantagem",
        )
        self.assertEqual(
            mechanics.combine_roll_modes("vantagem", "desvantagem", "vantagem"),
            "normal",
        )

    def test_um_natural_nao_e_falha_automatica_em_teste(self) -> None:
        result = mechanics.perform_check(
            bonus=20,
            target=15,
            rng=SequenceRng([1]),
        )
        self.assertEqual(result.roll.chosen, 1)
        self.assertTrue(result.success)

    def test_vinte_natural_nao_e_sucesso_automatico_em_salvaguarda(self) -> None:
        result = mechanics.perform_save(
            bonus=-10,
            target=15,
            rng=SequenceRng([20]),
        )
        self.assertEqual(result.roll.chosen, 20)
        self.assertFalse(result.success)
        self.assertEqual(result.kind, "salvaguarda")

    def test_um_natural_e_falha_automatica_em_ataque(self) -> None:
        result = mechanics.perform_attack(
            attack_bonus=100,
            armor_class=5,
            rng=SequenceRng([1]),
        )
        self.assertFalse(result.hit)
        self.assertFalse(result.critical)
        self.assertEqual(result.automatic, "falha")

    def test_vinte_natural_e_acerto_critico_automatico_em_ataque(self) -> None:
        result = mechanics.perform_attack(
            attack_bonus=-100,
            armor_class=99,
            rng=SequenceRng([20]),
        )
        self.assertTrue(result.hit)
        self.assertTrue(result.critical)
        self.assertEqual(result.automatic, "critico")

    def test_ataque_comum_resolve_total_contra_ca(self) -> None:
        hit = mechanics.perform_attack(
            attack_bonus=7,
            armor_class=17,
            rng=SequenceRng([10]),
        )
        miss = mechanics.perform_attack(
            attack_bonus=6,
            armor_class=17,
            rng=SequenceRng([10]),
        )
        self.assertTrue(hit.hit)
        self.assertFalse(miss.hit)
        self.assertFalse(hit.critical)
        self.assertFalse(miss.critical)

    def test_dano_critico_dobra_dados_mas_nao_modificador(self) -> None:
        normal = mechanics.roll_damage("1d6+4", rng=SequenceRng([3]))
        critical = mechanics.roll_damage(
            "1d6+4",
            critical=True,
            rng=SequenceRng([3, 5]),
        )
        self.assertEqual((normal.spec.count, normal.spec.modifier, normal.total), (1, 4, 7))
        self.assertEqual(
            (critical.spec.count, critical.spec.modifier, critical.total),
            (2, 4, 12),
        )

    def test_entradas_invalidas_falham_antes_do_rng(self) -> None:
        cases = [
            lambda rng: mechanics.roll_d20(0, "supervantagem", rng=rng),
            lambda rng: mechanics.perform_check(0, "15", rng=rng),
            lambda rng: mechanics.perform_save(0, "15", rng=rng),
            lambda rng: mechanics.perform_attack(5, "17", rng=rng),
            lambda rng: mechanics.roll_dice(mechanics.DiceSpec(0, 6), rng=rng),
        ]
        for call in cases:
            with self.subTest(call=call):
                rng = ForbiddenRng()
                with self.assertRaises(mechanics.MechanicsInputError):
                    call(rng)
                self.assertEqual(rng.calls, 0)

    def test_cli_publica_mantem_saida_logica_de_d20(self) -> None:
        fixed = SequenceRng([10])
        old_rng = core.RNG
        core.RNG = fixed
        try:
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = core.main(["d20", "--bonus", "5", "--cd", "15", "--label", "Teste"])
            self.assertEqual(code, 0)
            self.assertEqual(fixed.calls, 1)
            self.assertEqual(stdout.getvalue().strip(), "Teste: d20 10 + 5 = 15 contra CD 15. Sucesso.")
        finally:
            core.RNG = old_rng


if __name__ == "__main__":
    unittest.main()
