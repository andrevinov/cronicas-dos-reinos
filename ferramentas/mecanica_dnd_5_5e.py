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


def resolve_attack_roll(
    roll: D20Roll,
    armor_class: int | None,
) -> AttackResolution:
    checked_ac = _optional_integer(armor_class, "CA")
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
    if checked_ac is None:
        return AttackResolution(
            roll=roll,
            armor_class=None,
            hit=None,
            critical=False,
            automatic=None,
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
