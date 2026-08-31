from pathlib import Path
import textwrap


MODULE = r'''
"""Primitivas mecânicas internas para o ruleset alvo D&D 5.5e.

Este módulo não conhece Ren, ficha, campanha nem saída textual. Ele recebe todos os
modificadores como dados de entrada, valida antes de consumir RNG e devolve resultados
tipados para que as CLIs apenas apresentem/adaptem a mecânica.

A existência deste módulo durante a migração não ativa D&D 5.5e na campanha. Até o
gate final, ``campanha.yaml`` continua decidindo qual ruleset é operacional.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol, cast


RULESET_ID = "dnd_5_5e"
RollMode = Literal["normal", "vantagem", "desvantagem"]
VALID_ROLL_MODES = frozenset({"normal", "vantagem", "desvantagem"})
MAX_DICE = 100
DICE_PATTERN = re.compile(
    r"^\s*(?:(\d*)d(\d+))\s*([+-]\s*\d+)?\s*$",
    re.IGNORECASE,
)


class RandomSource(Protocol):
    def randint(self, low: int, high: int) -> int: ...


class MechanicsInputError(ValueError):
    """Entrada mecânica inválida detectada antes de qualquer rolagem."""


@dataclass(frozen=True)
class DiceSpec:
    count: int
    sides: int
    modifier: int = 0


@dataclass(frozen=True)
class DiceRoll:
    spec: DiceSpec
    rolls: list[int]

    @property
    def total(self) -> int:
        return sum(self.rolls) + self.spec.modifier


@dataclass(frozen=True)
class D20Roll:
    rolls: list[int]
    chosen: int
    bonus: int
    mode: RollMode

    @property
    def total(self) -> int:
        return self.chosen + self.bonus


@dataclass(frozen=True)
class D20Test:
    kind: Literal["teste", "salvaguarda"]
    roll: D20Roll
    target: int | None
    success: bool | None


@dataclass(frozen=True)
class AttackResolution:
    roll: D20Roll
    armor_class: int | None
    hit: bool | None
    critical: bool
    automatic: Literal["falha", "critico"] | None


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MechanicsInputError(f"{label} precisa ser inteiro")
    return value


def _optional_integer(value: object | None, label: str) -> int | None:
    if value is None:
        return None
    return _integer(value, label)


def validate_roll_mode(mode: str) -> RollMode:
    if not isinstance(mode, str) or mode not in VALID_ROLL_MODES:
        options = ", ".join(sorted(VALID_ROLL_MODES))
        raise MechanicsInputError(f"modo de rolagem inválido: {mode!r}. Opções: {options}")
    return cast(RollMode, mode)


def combine_roll_modes(*modes: str) -> RollMode:
    """Combina fontes de vantagem/desvantagem sem empilhamento.

    Qualquer quantidade de vantagem continua sendo vantagem; idem para desvantagem.
    Se ao menos uma fonte de cada lado coexistir, elas se cancelam e a rolagem é normal.
    """
    validated = [validate_roll_mode(mode) for mode in modes]
    has_advantage = "vantagem" in validated
    has_disadvantage = "desvantagem" in validated
    if has_advantage and has_disadvantage:
        return "normal"
    if has_advantage:
        return "vantagem"
    if has_disadvantage:
        return "desvantagem"
    return "normal"


def parse_dice(expression: str) -> DiceSpec:
    if not isinstance(expression, str):
        raise MechanicsInputError("expressão de dados precisa ser texto")
    match = DICE_PATTERN.match(expression)
    if not match:
        raise MechanicsInputError(
            f"Expressão de dados inválida: {expression!r}. Use formatos como d20, 1d6 ou 2d6+3."
        )

    count_text, sides_text, modifier_text = match.groups()
    count = int(count_text) if count_text else 1
    sides = int(sides_text)
    modifier = int(modifier_text.replace(" ", "")) if modifier_text else 0
    spec = DiceSpec(count=count, sides=sides, modifier=modifier)
    _validate_dice_spec(spec)
    return spec


def _validate_dice_spec(spec: DiceSpec) -> None:
    if not isinstance(spec, DiceSpec):
        raise MechanicsInputError("especificação de dados inválida")
    count = _integer(spec.count, "quantidade de dados")
    sides = _integer(spec.sides, "lados do dado")
    _integer(spec.modifier, "modificador dos dados")
    if count < 1:
        raise MechanicsInputError("A quantidade de dados deve ser pelo menos 1.")
    if sides < 2:
        raise MechanicsInputError("O dado deve ter pelo menos 2 lados.")
    if count > MAX_DICE:
        raise MechanicsInputError("Quantidade de dados alta demais para esta ferramenta.")


def roll_dice(spec: DiceSpec, *, rng: RandomSource) -> DiceRoll:
    _validate_dice_spec(spec)
    rolls = [rng.randint(1, spec.sides) for _ in range(spec.count)]
    return DiceRoll(spec=spec, rolls=rolls)


def roll_d20(
    bonus: int = 0,
    mode: str = "normal",
    *,
    rng: RandomSource,
) -> D20Roll:
    checked_bonus = _integer(bonus, "bônus do d20")
    checked_mode = validate_roll_mode(mode)
    if checked_mode == "normal":
        rolls = [rng.randint(1, 20)]
        chosen = rolls[0]
    else:
        rolls = [rng.randint(1, 20), rng.randint(1, 20)]
        chosen = max(rolls) if checked_mode == "vantagem" else min(rolls)
    return D20Roll(
        rolls=rolls,
        chosen=chosen,
        bonus=checked_bonus,
        mode=checked_mode,
    )


def critical_spec(spec: DiceSpec) -> DiceSpec:
    _validate_dice_spec(spec)
    critical = DiceSpec(
        count=spec.count * 2,
        sides=spec.sides,
        modifier=spec.modifier,
    )
    _validate_dice_spec(critical)
    return critical


def resolve_check_roll(roll: D20Roll, target: int | None) -> D20Test:
    checked_target = _optional_integer(target, "CD")
    success = None if checked_target is None else roll.total >= checked_target
    return D20Test(kind="teste", roll=roll, target=checked_target, success=success)


def resolve_save_roll(roll: D20Roll, target: int | None) -> D20Test:
    checked_target = _optional_integer(target, "CD")
    success = None if checked_target is None else roll.total >= checked_target
    return D20Test(kind="salvaguarda", roll=roll, target=checked_target, success=success)


def perform_check(
    bonus: int = 0,
    target: int | None = None,
    mode: str = "normal",
    *,
    rng: RandomSource,
) -> D20Test:
    checked_bonus = _integer(bonus, "bônus do teste")
    checked_target = _optional_integer(target, "CD")
    checked_mode = validate_roll_mode(mode)
    roll = roll_d20(checked_bonus, checked_mode, rng=rng)
    return resolve_check_roll(roll, checked_target)


def perform_save(
    bonus: int = 0,
    target: int | None = None,
    mode: str = "normal",
    *,
    rng: RandomSource,
) -> D20Test:
    checked_bonus = _integer(bonus, "bônus da salvaguarda")
    checked_target = _optional_integer(target, "CD")
    checked_mode = validate_roll_mode(mode)
    roll = roll_d20(checked_bonus, checked_mode, rng=rng)
    return resolve_save_roll(roll, checked_target)


def resolve_attack_roll(roll: D20Roll, armor_class: int) -> AttackResolution:
    checked_ac = _integer(armor_class, "CA")
    natural = roll.chosen
    if natural == 1:
        return AttackResolution(
            roll=roll,
            armor_class=checked_ac,
            hit=False,
            critical=False,
            automatic="falha",
        )
    if natural == 20:
        return AttackResolution(
            roll=roll,
            armor_class=checked_ac,
            hit=True,
            critical=True,
            automatic="critico",
        )
    return AttackResolution(
        roll=roll,
        armor_class=checked_ac,
        hit=roll.total >= checked_ac,
        critical=False,
        automatic=None,
    )


def perform_attack(
    attack_bonus: int,
    armor_class: int | None,
    mode: str = "normal",
    *,
    rng: RandomSource,
) -> AttackResolution:
    checked_bonus = _integer(attack_bonus, "bônus de ataque")
    checked_ac = _optional_integer(armor_class, "CA")
    checked_mode = validate_roll_mode(mode)
    roll = roll_d20(checked_bonus, checked_mode, rng=rng)
    if checked_ac is None:
        return AttackResolution(
            roll=roll,
            armor_class=None,
            hit=None,
            critical=False,
            automatic=None,
        )
    return resolve_attack_roll(roll, checked_ac)


def roll_damage(
    expression: str,
    *,
    critical: bool = False,
    rng: RandomSource,
) -> DiceRoll:
    if not isinstance(critical, bool):
        raise MechanicsInputError("indicador de crítico precisa ser booleano")
    spec = parse_dice(expression)
    if critical:
        spec = critical_spec(spec)
    return roll_dice(spec, rng=rng)
'''

TESTS = r'''
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
'''


def replace_between(text: str, start: str, end: str, replacement: str) -> str:
    start_index = text.index(start)
    end_index = text.index(end, start_index)
    return text[:start_index] + replacement + text[end_index:]


Path("ferramentas/mecanica_dnd_5_5e.py").write_text(
    textwrap.dedent(MODULE).lstrip(), encoding="utf-8"
)
Path("tests/test_mecanica_dnd_5_5e.py").write_text(
    textwrap.dedent(TESTS).lstrip(), encoding="utf-8"
)

core_path = Path("ferramentas/_rolar_dados_core.py")
core = core_path.read_text(encoding="utf-8")
core = core.replace("from dataclasses import dataclass\n", "", 1)
core = core.replace("import ficha_ren\n", "import ficha_ren\nimport mecanica_dnd_5_5e as mechanics\n", 1)
core = "\n".join(
    line for line in core.splitlines() if not line.startswith("DICE_PATTERN = ")
) + "\n"

aliases = '''DiceSpec = mechanics.DiceSpec\nDiceRoll = mechanics.DiceRoll\nD20Roll = mechanics.D20Roll\nD20Test = mechanics.D20Test\nAttackResolution = mechanics.AttackResolution\n\n\n'''
core = replace_between(
    core,
    "@dataclass(frozen=True)\nclass DiceSpec:",
    "REN_ABILITY_LABELS:",
    aliases + "REN_ABILITY_LABELS:",
)

wrappers = '''def parse_dice(expression: str) -> DiceSpec:\n    return mechanics.parse_dice(expression)\n\n\ndef roll_dice(spec: DiceSpec) -> DiceRoll:\n    return mechanics.roll_dice(spec, rng=RNG)\n\n\ndef roll_d20(bonus: int = 0, mode: str = "normal") -> D20Roll:\n    return mechanics.roll_d20(bonus, mode, rng=RNG)\n\n\ndef critical_spec(spec: DiceSpec) -> DiceSpec:\n    return mechanics.critical_spec(spec)\n\n\ndef combine_roll_modes(*modes: str) -> str:\n    return mechanics.combine_roll_modes(*modes)\n\n\ndef perform_check(bonus: int = 0, cd: int | None = None, mode: str = "normal") -> D20Test:\n    return mechanics.perform_check(bonus, cd, mode, rng=RNG)\n\n\ndef perform_save(bonus: int = 0, cd: int | None = None, mode: str = "normal") -> D20Test:\n    return mechanics.perform_save(bonus, cd, mode, rng=RNG)\n\n\ndef perform_attack(attack_bonus: int, ca: int | None, mode: str = "normal") -> AttackResolution:\n    return mechanics.perform_attack(attack_bonus, ca, mode, rng=RNG)\n\n\ndef roll_damage(expression: str, *, critical: bool = False) -> DiceRoll:\n    return mechanics.roll_damage(expression, critical=critical, rng=RNG)\n\n\n'''
core = replace_between(core, "def parse_dice(", "def format_dice_roll(", wrappers + "def format_dice_roll(")

format_check = '''def format_check(label: str, roll: D20Roll, cd: int | None) -> str:\n    resolution = mechanics.resolve_check_roll(roll, cd)\n    text = f"{label}: {format_d20_roll(roll)}"\n    if resolution.success is not None:\n        result = "Sucesso" if resolution.success else "Falha"\n        text += f" contra CD {resolution.target}. {result}."\n    else:\n        text += "."\n    return text\n\n\n'''
core = replace_between(core, "def format_check(", "def attack_result(", format_check + "def attack_result(")

attack_result = '''def attack_result(roll: D20Roll, ca: int | None) -> tuple[str, bool, bool]:\n    if ca is None:\n        return "", False, False\n    resolution = mechanics.resolve_attack_roll(roll, ca)\n    if resolution.automatic == "falha":\n        return "Falha automática.", False, False\n    if resolution.automatic == "critico":\n        return "Acerto crítico.", True, True\n    if resolution.hit:\n        return "Acerto.", True, False\n    return "Erro.", False, False\n\n\n'''
core = replace_between(core, "def attack_result(", "def format_attack(", attack_result + "def format_attack(")

format_attack = '''def format_attack(\n    *,\n    label: str,\n    attack_bonus: int,\n    damage_expression: str | None,\n    damage_type: str,\n    ca: int | None,\n    mode: str,\n) -> str:\n    resolution = perform_attack(attack_bonus, ca, mode)\n    attack_roll = resolution.roll\n    text = f"{label}: {format_d20_roll(attack_roll)}"\n\n    hit = False\n    critical = False\n    if ca is not None:\n        result_text, hit, critical = attack_result(attack_roll, ca)\n        text += f" contra CA {ca}. {result_text}"\n    else:\n        text += "."\n\n    if damage_expression and (hit or ca is None):\n        damage_roll = roll_damage(damage_expression, critical=critical)\n        prefix = "Dano crítico" if critical else "Dano"\n        if ca is None:\n            prefix = "Dano se acertar"\n        text += f" {prefix}: {format_dice_roll(damage_roll)}"\n        if damage_type:\n            text += f" {damage_type}"\n        text += "."\n\n    return text\n\n\n'''
core = replace_between(core, "def format_attack(", "def current_mode(", format_attack + "def current_mode(")

old_current_mode = '''def current_mode(args: argparse.Namespace) -> str:\n    if getattr(args, "vantagem", False):\n        return "vantagem"\n    if getattr(args, "desvantagem", False):\n        return "desvantagem"\n    return "normal"\n'''
new_current_mode = '''def current_mode(args: argparse.Namespace) -> str:\n    modes: list[str] = []\n    if getattr(args, "vantagem", False):\n        modes.append("vantagem")\n    if getattr(args, "desvantagem", False):\n        modes.append("desvantagem")\n    return combine_roll_modes(*modes)\n'''
if old_current_mode not in core:
    raise SystemExit("current_mode block not found")
core = core.replace(old_current_mode, new_current_mode, 1)

replacements = {
'''def cmd_d20(args: argparse.Namespace) -> int:\n    roll = roll_d20(args.bonus, current_mode(args))\n    label = args.label or "Teste"\n    print(format_check(label, roll, args.cd))\n    return 0\n''':
'''def cmd_d20(args: argparse.Namespace) -> int:\n    result = perform_check(args.bonus, args.cd, current_mode(args))\n    label = args.label or "Teste"\n    print(format_check(label, result.roll, args.cd))\n    return 0\n''',
'''def cmd_ren_ability(args: argparse.Namespace) -> int:\n    ren = load_ren_mechanics()\n    key = resolve_key(ren.abilities, args.atributo, "Atributo")\n    bonus = ren.abilities[key] + args.bonus_extra\n    label = args.label or f"Teste de {REN_ABILITY_LABELS[key]} (Ren)"\n    print(format_check(label, roll_d20(bonus, current_mode(args)), args.cd))\n    return 0\n''':
'''def cmd_ren_ability(args: argparse.Namespace) -> int:\n    ren = load_ren_mechanics()\n    key = resolve_key(ren.abilities, args.atributo, "Atributo")\n    bonus = ren.abilities[key] + args.bonus_extra\n    label = args.label or f"Teste de {REN_ABILITY_LABELS[key]} (Ren)"\n    result = perform_check(bonus, args.cd, current_mode(args))\n    print(format_check(label, result.roll, args.cd))\n    return 0\n''',
'''def cmd_ren_skill(args: argparse.Namespace) -> int:\n    ren = load_ren_mechanics()\n    key = resolve_key(ren.skills, args.nome, "Perícia")\n    bonus = ren.skills[key] + args.bonus_extra\n    label = args.label or f"Teste de {REN_SKILL_LABELS[key]} (Ren)"\n    print(format_check(label, roll_d20(bonus, current_mode(args)), args.cd))\n    return 0\n''':
'''def cmd_ren_skill(args: argparse.Namespace) -> int:\n    ren = load_ren_mechanics()\n    key = resolve_key(ren.skills, args.nome, "Perícia")\n    bonus = ren.skills[key] + args.bonus_extra\n    label = args.label or f"Teste de {REN_SKILL_LABELS[key]} (Ren)"\n    result = perform_check(bonus, args.cd, current_mode(args))\n    print(format_check(label, result.roll, args.cd))\n    return 0\n''',
'''def cmd_ren_save(args: argparse.Namespace) -> int:\n    ren = load_ren_mechanics()\n    key = resolve_key(ren.saves, args.atributo, "Salvaguarda")\n    bonus = ren.saves[key] + args.bonus_extra\n    label = args.label or f"Salvaguarda de {REN_SAVE_LABELS[key]} (Ren)"\n    print(format_check(label, roll_d20(bonus, current_mode(args)), args.cd))\n    return 0\n''':
'''def cmd_ren_save(args: argparse.Namespace) -> int:\n    ren = load_ren_mechanics()\n    key = resolve_key(ren.saves, args.atributo, "Salvaguarda")\n    bonus = ren.saves[key] + args.bonus_extra\n    label = args.label or f"Salvaguarda de {REN_SAVE_LABELS[key]} (Ren)"\n    result = perform_save(bonus, args.cd, current_mode(args))\n    print(format_check(label, result.roll, args.cd))\n    return 0\n''',
'''def cmd_ren_initiative(args: argparse.Namespace) -> int:\n    ren = load_ren_mechanics()\n    bonus = ren.initiative + args.bonus_extra\n    label = args.label or "Iniciativa (Ren)"\n    print(format_check(label, roll_d20(bonus, current_mode(args)), None))\n    return 0\n''':
'''def cmd_ren_initiative(args: argparse.Namespace) -> int:\n    ren = load_ren_mechanics()\n    bonus = ren.initiative + args.bonus_extra\n    label = args.label or "Iniciativa (Ren)"\n    result = perform_check(bonus, None, current_mode(args))\n    print(format_check(label, result.roll, None))\n    return 0\n''',
'''def cmd_ren_damage(args: argparse.Namespace) -> int:\n    ren = load_ren_mechanics()\n    key = resolve_key(ren.attacks, args.nome, "Ataque")\n    attack = ren.attacks[key]\n    spec = parse_dice(attack.damage)\n    result = roll_dice(critical_spec(spec) if args.critico else spec)\n    suffix = " crítico" if args.critico else ""\n    print(\n        f"Dano com {attack.label} (Ren{suffix}): "\n        f"{format_dice_roll(result)} {attack.damage_type}."\n    )\n    return 0\n''':
'''def cmd_ren_damage(args: argparse.Namespace) -> int:\n    ren = load_ren_mechanics()\n    key = resolve_key(ren.attacks, args.nome, "Ataque")\n    attack = ren.attacks[key]\n    result = roll_damage(attack.damage, critical=args.critico)\n    suffix = " crítico" if args.critico else ""\n    print(\n        f"Dano com {attack.label} (Ren{suffix}): "\n        f"{format_dice_roll(result)} {attack.damage_type}."\n    )\n    return 0\n''',
'''def cmd_npc_d20(args: argparse.Namespace) -> int:\n    label_base = args.label or "Teste"\n    label = f"{label_base} ({args.nome})" if args.nome else label_base\n    print(format_check(label, roll_d20(args.bonus, current_mode(args)), args.cd))\n    return 0\n''':
'''def cmd_npc_d20(args: argparse.Namespace) -> int:\n    label_base = args.label or "Teste"\n    label = f"{label_base} ({args.nome})" if args.nome else label_base\n    result = perform_check(args.bonus, args.cd, current_mode(args))\n    print(format_check(label, result.roll, args.cd))\n    return 0\n''',
}
for old, new in replacements.items():
    if old not in core:
        raise SystemExit("expected core command block not found")
    core = core.replace(old, new, 1)

core_path.write_text(core, encoding="utf-8")

roller_path = Path("ferramentas/rolar-dados.py")
roller = roller_path.read_text(encoding="utf-8")
actor_start = roller.index("    has_advantage = \"--vantagem\" in clean\n")
actor_end = roller.index("\n\ndef _prepare_argv_context", actor_start)
actor = '''    has_advantage = "--vantagem" in clean\n    has_disadvantage = "--desvantagem" in clean\n    if has_advantage and has_disadvantage:\n        raise FeatContextError("vantagem e desvantagem não podem ser declaradas juntas")\n\n    current = (\n        "desvantagem"\n        if has_disadvantage\n        else "vantagem"\n        if has_advantage\n        else "normal"\n    )\n    combined = _core.combine_roll_modes(current, "vantagem")\n    clean = [token for token in clean if token not in {"--vantagem", "--desvantagem"}]\n    if combined != "normal":\n        clean.append(f"--{combined}")\n\n    if current == "desvantagem":\n        note = "Actor: vantagem por outra identidade cancelou a desvantagem; rolagem normal"\n    elif current == "vantagem":\n        note = "Actor: vantagem por outra identidade já estava representada"\n    else:\n        note = "Actor: vantagem por outra identidade aplicada"\n    return clean, note\n'''
roller = roller[:actor_start] + actor + roller[actor_end:]
roller_path.write_text(roller, encoding="utf-8")

campaign_path = Path("campanha.yaml")
campaign = campaign_path.read_text(encoding="utf-8")
old_flag = "          task_4_nucleo_mecanico: false\n"
if old_flag not in campaign:
    raise SystemExit("Task 4 flag not found")
campaign = campaign.replace(old_flag, "          task_4_nucleo_mecanico: true\n", 1)
marker = '    adaptador_ficha_ren: "ferramentas/ficha_ren.py"\n'
if marker not in campaign:
    raise SystemExit("campaign tools marker not found")
campaign = campaign.replace(
    marker,
    marker + '    nucleo_mecanico_5_5e: "ferramentas/mecanica_dnd_5_5e.py"\n',
    1,
)
campaign_path.write_text(campaign, encoding="utf-8")

docs_path = Path("docs/agente/regras-e-rolagens.md")
docs = docs_path.read_text(encoding="utf-8")
marker = "## Filosofia de fidelidade: aproximadamente 70%\n"
section = '''## Núcleo mecânico 5.5e\n\n`ferramentas/mecanica_dnd_5_5e.py` concentra as primitivas mecânicas do ruleset alvo: dados, d20, vantagem/desvantagem, testes, salvaguardas, ataques, críticos e dano. O módulo é interno e genérico: não conhece Ren, ficha, campanha nem apresentação textual. `dados` permanece a CLI pública e adapta entradas/saídas para esse núcleo.\n\nToda entrada mecânica que puder ser validada sem aleatoriedade deve falhar antes do RNG. Em particular, modo de rolagem, expressão de dados, modificadores e alvos inválidos não podem consumir dado. 1 e 20 naturais têm tratamento automático em jogadas de ataque; testes e salvaguardas continuam resolvidos pelo total contra a CD, sem sucesso/falha automática apenas pelo valor natural. Crítico dobra os dados de dano, não o modificador.\n\nA presença do núcleo 5.5e não muda `sistema.ruleset.atual`: enquanto o gate de migração não for concluído, seu uso por `dados` fica restrito às primitivas cuja semântica é compatível com o ruleset operacional. Nenhuma regra exclusiva de 5.5e pode entrar silenciosamente na narração antes da ativação final.\n\n'''
if marker not in docs:
    raise SystemExit("docs Task 4 marker not found")
docs_path.write_text(docs.replace(marker, section + marker, 1), encoding="utf-8")

readme_path = Path("ferramentas/README.md")
readme = readme_path.read_text(encoding="utf-8")
marker = "### Rolagens em lote\n"
section = '''### Núcleo mecânico interno\n\n`dados` continua sendo a interface pública. A matemática compartilhada de d20, testes, salvaguardas, ataques, vantagem/desvantagem, críticos e dano fica em `mecanica_dnd_5_5e.py`; consumidores operacionais não devem chamar esse módulo diretamente. Durante a migração, isso não ativa 5.5e por si só: `campanha.yaml` continua sendo a autoridade do ruleset em uso.\n\n'''
if marker not in readme:
    raise SystemExit("README roll marker not found")
readme_path.write_text(readme.replace(marker, section + marker, 1), encoding="utf-8")
