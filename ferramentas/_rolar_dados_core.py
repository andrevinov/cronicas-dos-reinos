#!/usr/bin/env python3
"""Rolador de dados para a campanha Crônicas dos Reinos."""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from random import SystemRandom

import ficha_ren
import mecanica_dnd_5_5e as mechanics


RNG = SystemRandom()


DiceSpec = mechanics.DiceSpec
DiceRoll = mechanics.DiceRoll
D20Roll = mechanics.D20Roll
D20Test = mechanics.D20Test
AttackResolution = mechanics.AttackResolution


REN_ABILITY_LABELS: dict[str, str] = {
    "forca": "Força",
    "destreza": "Destreza",
    "constituicao": "Constituição",
    "inteligencia": "Inteligência",
    "sabedoria": "Sabedoria",
    "carisma": "Carisma",
}

REN_SKILL_LABELS: dict[str, str] = {
    "acrobacia": "Acrobacia",
    "furtividade": "Furtividade",
    "intuicao": "Intuição",
    "percepcao": "Percepção",
    "investigacao": "Investigação",
    "atletismo": "Atletismo",
    "historia": "História",
    "religiao": "Religião",
    "arcana": "Arcana",
    "enganacao": "Enganação",
    "intimidacao": "Intimidação",
    "persuasao": "Persuasão",
    "sobrevivencia": "Sobrevivência",
    "medicina": "Medicina",
    "natureza": "Natureza",
    "prestidigitacao": "Prestidigitação",
    "atuacao": "Atuação",
    "lidar_com_animais": "Lidar com Animais",
}

REN_PASSIVE_LABELS: dict[str, str] = {
    "percepcao": "Percepção passiva",
    "investigacao": "Investigação passiva",
    "intuicao": "Intuição passiva",
}

REN_SAVE_LABELS: dict[str, str] = {
    "forca": "Força",
    "destreza": "Destreza",
    "constituicao": "Constituição",
    "inteligencia": "Inteligência",
    "sabedoria": "Sabedoria",
    "carisma": "Carisma",
}

AttackProfile = ficha_ren.AttackProfile
CANONICAL_REN_SHEET = ficha_ren.DEFAULT_SHEET_PATH


def load_ren_mechanics() -> ficha_ren.RenMechanics:
    return ficha_ren.load(CANONICAL_REN_SHEET)


def normalize_key(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.strip().lower())
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    ascii_text = re.sub(r"[^a-z0-9]+", "_", ascii_text)
    return ascii_text.strip("_")


def signed(value: int) -> str:
    if value < 0:
        return f"- {abs(value)}"
    return f"+ {value}"


def parse_dice(expression: str) -> DiceSpec:
    return mechanics.parse_dice(expression)


def roll_dice(spec: DiceSpec) -> DiceRoll:
    return mechanics.roll_dice(spec, rng=RNG)


def roll_d20(bonus: int = 0, mode: str = "normal") -> D20Roll:
    return mechanics.roll_d20(bonus, mode, rng=RNG)


def critical_spec(spec: DiceSpec) -> DiceSpec:
    return mechanics.critical_spec(spec)


def combine_roll_modes(*modes: str) -> str:
    return mechanics.combine_roll_modes(*modes)


def perform_check(bonus: int = 0, cd: int | None = None, mode: str = "normal") -> D20Test:
    return mechanics.perform_check(bonus, cd, mode, rng=RNG)


def perform_save(bonus: int = 0, cd: int | None = None, mode: str = "normal") -> D20Test:
    return mechanics.perform_save(bonus, cd, mode, rng=RNG)


def perform_attack(attack_bonus: int, ca: int | None, mode: str = "normal") -> AttackResolution:
    return mechanics.perform_attack(attack_bonus, ca, mode, rng=RNG)


def roll_damage(expression: str, *, critical: bool = False) -> DiceRoll:
    return mechanics.roll_damage(expression, critical=critical, rng=RNG)


def format_dice_roll(roll: DiceRoll) -> str:
    dice = f"{roll.spec.count}d{roll.spec.sides}"
    rolls_text = ", ".join(str(value) for value in roll.rolls)
    if roll.spec.count == 1:
        base = f"{dice} {rolls_text}"
    else:
        base = f"{dice} [{rolls_text}]"

    if roll.spec.modifier:
        return f"{base} {signed(roll.spec.modifier)} = {roll.total}"
    return f"{base} = {roll.total}"


def format_d20_roll(roll: D20Roll) -> str:
    if roll.mode == "normal":
        base = f"d20 {roll.chosen}"
    else:
        rolls_text = ", ".join(str(value) for value in roll.rolls)
        base = f"d20 com {roll.mode} [{rolls_text}] -> {roll.chosen}"

    if roll.bonus:
        return f"{base} {signed(roll.bonus)} = {roll.total}"
    return f"{base} = {roll.total}"


def format_check(label: str, roll: D20Roll, cd: int | None) -> str:
    resolution = mechanics.resolve_check_roll(roll, cd)
    text = f"{label}: {format_d20_roll(roll)}"
    if resolution.success is not None:
        result = "Sucesso" if resolution.success else "Falha"
        text += f" contra CD {resolution.target}. {result}."
    else:
        text += "."
    return text


def attack_result(roll: D20Roll, ca: int | None) -> tuple[str, bool, bool]:
    if ca is None:
        return "", False, False
    resolution = mechanics.resolve_attack_roll(roll, ca)
    if resolution.automatic == "falha":
        return "Falha automática.", False, False
    if resolution.automatic == "critico":
        return "Acerto crítico.", True, True
    if resolution.hit:
        return "Acerto.", True, False
    return "Erro.", False, False


def format_attack(
    *,
    label: str,
    attack_bonus: int,
    damage_expression: str | None,
    damage_type: str,
    ca: int | None,
    mode: str,
) -> str:
    resolution = perform_attack(attack_bonus, ca, mode)
    attack_roll = resolution.roll
    text = f"{label}: {format_d20_roll(attack_roll)}"

    hit = False
    critical = False
    if ca is not None:
        result_text, hit, critical = attack_result(attack_roll, ca)
        text += f" contra CA {ca}. {result_text}"
    else:
        text += "."

    if damage_expression and (hit or ca is None):
        damage_roll = roll_damage(damage_expression, critical=critical)
        prefix = "Dano crítico" if critical else "Dano"
        if ca is None:
            prefix = "Dano se acertar"
        text += f" {prefix}: {format_dice_roll(damage_roll)}"
        if damage_type:
            text += f" {damage_type}"
        text += "."

    return text


def current_mode(args: argparse.Namespace) -> str:
    modes: list[str] = []
    if getattr(args, "vantagem", False):
        modes.append("vantagem")
    if getattr(args, "desvantagem", False):
        modes.append("desvantagem")
    return combine_roll_modes(*modes)


def resolve_key(table: dict[str, object], name: str, kind: str) -> str:
    key = normalize_key(name)
    if key in table:
        return key
    options = ", ".join(sorted(table))
    raise KeyError(f"{kind} desconhecido: {name!r}. Opções: {options}.")


def add_advantage_flags(parser: argparse.ArgumentParser) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--vantagem", action="store_true", help="rola dois d20 e usa o maior")
    group.add_argument("--desvantagem", action="store_true", help="rola dois d20 e usa o menor")


def add_cd(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--cd", type=int, help="classe de dificuldade do teste")


def cmd_roll(args: argparse.Namespace) -> int:
    spec = parse_dice(args.expressao)
    result = roll_dice(spec)
    label = args.label or f"Rolagem {args.expressao}"
    print(f"{label}: {format_dice_roll(result)}.")
    return 0


def cmd_d20(args: argparse.Namespace) -> int:
    result = perform_check(args.bonus, args.cd, current_mode(args))
    label = args.label or "Teste"
    print(format_check(label, result.roll, args.cd))
    return 0


def cmd_ren_list(_: argparse.Namespace) -> int:
    ren = load_ren_mechanics()
    print("Atributos de Ren:")
    for name, bonus in sorted(ren.abilities.items()):
        print(f"- {name}: {REN_ABILITY_LABELS[name]} {signed(bonus).replace(' ', '')}")

    print("\nPerícias de Ren:")
    for name, bonus in sorted(ren.skills.items()):
        print(f"- {name}: {REN_SKILL_LABELS[name]} {signed(bonus).replace(' ', '')}")

    print("\nValores passivos de Ren:")
    for name, value in sorted(ren.passives.items()):
        print(f"- {name}: {REN_PASSIVE_LABELS[name]} {value}")

    print("\nSalvaguardas de Ren:")
    for name, bonus in sorted(ren.saves.items()):
        print(f"- {name}: {REN_SAVE_LABELS[name]} {signed(bonus).replace(' ', '')}")

    print("\nAtaques de Ren:")
    for key, attack in sorted(ren.attacks.items()):
        print(
            f"- {key}: ataque {signed(attack.attack_bonus).replace(' ', '')}, "
            f"dano {attack.damage} {attack.damage_type}"
        )
    return 0


def cmd_ren_ability(args: argparse.Namespace) -> int:
    ren = load_ren_mechanics()
    key = resolve_key(ren.abilities, args.atributo, "Atributo")
    bonus = ren.abilities[key] + args.bonus_extra
    label = args.label or f"Teste de {REN_ABILITY_LABELS[key]} (Ren)"
    result = perform_check(bonus, args.cd, current_mode(args))
    print(format_check(label, result.roll, args.cd))
    return 0


def cmd_ren_skill(args: argparse.Namespace) -> int:
    ren = load_ren_mechanics()
    key = resolve_key(ren.skills, args.nome, "Perícia")
    bonus = ren.skills[key] + args.bonus_extra
    label = args.label or f"Teste de {REN_SKILL_LABELS[key]} (Ren)"
    result = perform_check(bonus, args.cd, current_mode(args))
    print(format_check(label, result.roll, args.cd))
    return 0


def cmd_ren_passive(args: argparse.Namespace) -> int:
    ren = load_ren_mechanics()
    key = resolve_key(ren.passives, args.nome, "Valor passivo")
    print(f"{REN_PASSIVE_LABELS[key]} (Ren): {ren.passives[key]}.")
    return 0


def cmd_ren_save(args: argparse.Namespace) -> int:
    ren = load_ren_mechanics()
    key = resolve_key(ren.saves, args.atributo, "Salvaguarda")
    bonus = ren.saves[key] + args.bonus_extra
    label = args.label or f"Salvaguarda de {REN_SAVE_LABELS[key]} (Ren)"
    result = perform_save(bonus, args.cd, current_mode(args))
    print(format_check(label, result.roll, args.cd))
    return 0


def cmd_ren_initiative(args: argparse.Namespace) -> int:
    ren = load_ren_mechanics()
    bonus = ren.initiative + args.bonus_extra
    label = args.label or "Iniciativa (Ren)"
    result = perform_check(bonus, None, current_mode(args))
    print(format_check(label, result.roll, None))
    return 0


def cmd_ren_attack(args: argparse.Namespace) -> int:
    ren = load_ren_mechanics()
    key = resolve_key(ren.attacks, args.nome, "Ataque")
    attack = ren.attacks[key]
    label = args.label or f"Ataque com {attack.label} (Ren)"
    print(
        format_attack(
            label=label,
            attack_bonus=attack.attack_bonus + args.bonus_extra,
            damage_expression=None if args.sem_dano else attack.damage,
            damage_type=attack.damage_type,
            ca=args.ca,
            mode=current_mode(args),
        )
    )
    return 0


def cmd_ren_damage(args: argparse.Namespace) -> int:
    ren = load_ren_mechanics()
    key = resolve_key(ren.attacks, args.nome, "Ataque")
    attack = ren.attacks[key]
    result = roll_damage(attack.damage, critical=args.critico)
    suffix = " crítico" if args.critico else ""
    print(
        f"Dano com {attack.label} (Ren{suffix}): "
        f"{format_dice_roll(result)} {attack.damage_type}."
    )
    return 0


def cmd_npc_d20(args: argparse.Namespace) -> int:
    label_base = args.label or "Teste"
    label = f"{label_base} ({args.nome})" if args.nome else label_base
    result = perform_check(args.bonus, args.cd, current_mode(args))
    print(format_check(label, result.roll, args.cd))
    return 0


def cmd_npc_attack(args: argparse.Namespace) -> int:
    subject = args.nome or "NPC"
    weapon = f" com {args.arma}" if args.arma else ""
    label = args.label or f"Ataque{weapon} ({subject})"
    print(
        format_attack(
            label=label,
            attack_bonus=args.bonus_ataque,
            damage_expression=args.dano,
            damage_type=args.tipo_dano or "",
            ca=args.ca,
            mode=current_mode(args),
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Rolador de dados offline para Crônicas dos Reinos.",
    )
    subparsers = parser.add_subparsers(dest="comando", required=True)

    roll_parser = subparsers.add_parser("rolar", aliases=["roll"], help="rola uma expressão como 2d6+3")
    roll_parser.add_argument("expressao", help="expressão de dados: d20, 1d6, 2d6+3")
    roll_parser.add_argument("--label", help="rótulo exibido na saída")
    roll_parser.set_defaults(func=cmd_roll)

    d20_parser = subparsers.add_parser("d20", help="rola um teste genérico de d20")
    d20_parser.add_argument("--bonus", type=int, default=0, help="modificador total do teste")
    add_cd(d20_parser)
    d20_parser.add_argument("--label", help="rótulo exibido na saída")
    add_advantage_flags(d20_parser)
    d20_parser.set_defaults(func=cmd_d20)

    ren_parser = subparsers.add_parser("ren", help="atalhos baseados na ficha atual de Ren")
    ren_subparsers = ren_parser.add_subparsers(dest="ren_comando", required=True)

    ren_list_parser = ren_subparsers.add_parser("listar", aliases=["list"], help="lista atalhos de Ren")
    ren_list_parser.set_defaults(func=cmd_ren_list)

    ability_parser = ren_subparsers.add_parser("atributo", aliases=["ability"], help="rola teste de atributo de Ren")
    ability_parser.add_argument("atributo", help="nome do atributo")
    add_cd(ability_parser)
    ability_parser.add_argument("--bonus-extra", type=int, default=0, help="modificador circunstancial adicional")
    ability_parser.add_argument("--label", help="rótulo exibido na saída")
    add_advantage_flags(ability_parser)
    ability_parser.set_defaults(func=cmd_ren_ability)

    skill_parser = ren_subparsers.add_parser("pericia", aliases=["skill"], help="rola perícia de Ren")
    skill_parser.add_argument("nome", help="nome da perícia")
    add_cd(skill_parser)
    skill_parser.add_argument("--bonus-extra", type=int, default=0, help="modificador circunstancial adicional")
    skill_parser.add_argument("--label", help="rótulo exibido na saída")
    add_advantage_flags(skill_parser)
    skill_parser.set_defaults(func=cmd_ren_skill)

    passive_parser = ren_subparsers.add_parser("passivo", aliases=["passive"], help="consulta valor passivo de Ren")
    passive_parser.add_argument("nome", help="percepcao, investigacao ou intuicao")
    passive_parser.set_defaults(func=cmd_ren_passive)

    save_parser = ren_subparsers.add_parser("salvaguarda", aliases=["save"], help="rola salvaguarda de Ren")
    save_parser.add_argument("atributo", help="atributo da salvaguarda")
    add_cd(save_parser)
    save_parser.add_argument("--bonus-extra", type=int, default=0, help="modificador circunstancial adicional")
    save_parser.add_argument("--label", help="rótulo exibido na saída")
    add_advantage_flags(save_parser)
    save_parser.set_defaults(func=cmd_ren_save)

    initiative_parser = ren_subparsers.add_parser("iniciativa", aliases=["initiative"], help="rola iniciativa de Ren")
    initiative_parser.add_argument("--bonus-extra", type=int, default=0, help="modificador circunstancial adicional")
    initiative_parser.add_argument("--label", help="rótulo exibido na saída")
    add_advantage_flags(initiative_parser)
    initiative_parser.set_defaults(func=cmd_ren_initiative)

    attack_parser = ren_subparsers.add_parser("ataque", aliases=["attack"], help="rola ataque de Ren")
    attack_parser.add_argument("nome", help="golpe_desarmado, wakizashi ou shuriken")
    attack_parser.add_argument("--ca", type=int, help="classe de armadura do alvo")
    attack_parser.add_argument("--bonus-extra", type=int, default=0, help="modificador circunstancial adicional")
    attack_parser.add_argument("--sem-dano", action="store_true", help="não rola dano junto do ataque")
    attack_parser.add_argument("--label", help="rótulo exibido na saída")
    add_advantage_flags(attack_parser)
    attack_parser.set_defaults(func=cmd_ren_attack)

    damage_parser = ren_subparsers.add_parser("dano", aliases=["damage"], help="rola dano de um ataque de Ren")
    damage_parser.add_argument("nome", help="golpe_desarmado, wakizashi ou shuriken")
    damage_parser.add_argument("--critico", action="store_true", help="dobra os dados de dano")
    damage_parser.set_defaults(func=cmd_ren_damage)

    npc_parser = subparsers.add_parser("npc", help="rolagens genéricas de NPCs")
    npc_subparsers = npc_parser.add_subparsers(dest="npc_comando", required=True)

    npc_d20_parser = npc_subparsers.add_parser("d20", help="rola teste de d20 de NPC")
    npc_d20_parser.add_argument("--nome", help="nome do NPC")
    npc_d20_parser.add_argument("--bonus", type=int, default=0, help="modificador total do teste")
    add_cd(npc_d20_parser)
    npc_d20_parser.add_argument("--label", help="rótulo exibido na saída")
    add_advantage_flags(npc_d20_parser)
    npc_d20_parser.set_defaults(func=cmd_npc_d20)

    npc_attack_parser = npc_subparsers.add_parser("ataque", aliases=["attack"], help="rola ataque de NPC")
    npc_attack_parser.add_argument("--nome", help="nome do NPC")
    npc_attack_parser.add_argument("--arma", help="arma ou ataque usado")
    npc_attack_parser.add_argument("--bonus-ataque", type=int, required=True, help="modificador total de ataque")
    npc_attack_parser.add_argument("--dano", help="expressão de dano, como 1d6+2")
    npc_attack_parser.add_argument("--tipo-dano", help="tipo de dano")
    npc_attack_parser.add_argument("--ca", type=int, help="classe de armadura do alvo")
    npc_attack_parser.add_argument("--label", help="rótulo exibido na saída")
    add_advantage_flags(npc_attack_parser)
    npc_attack_parser.set_defaults(func=cmd_npc_attack)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (KeyError, ValueError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
