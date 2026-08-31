"""Visão mecânica alvo de Ren para a migração D&D 5.5e.

A ficha operacional continua sendo ``personagens/jogador/ficha.yaml`` até a Task 8.
Este adaptador é puro: combina a ficha canônica atual com o contrato de migração e
produz a visão que deverá ser promovida quando o gate final for aberto.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

import ficha_ren

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SHEET_PATH = ROOT / "personagens/jogador/ficha.yaml"
DEFAULT_MIGRATION_PATH = ROOT / "personagens/jogador/migracao-5-5e.yaml"
DAMAGE_RE = re.compile(r"^(\d*d\d+)([+-]\d+)?$")
SPEED_RE = re.compile(r"^\s*(\d+)\s*pés\s*$", re.IGNORECASE)


class Ren55MigrationError(ValueError):
    pass


@dataclass(frozen=True)
class TargetAttack:
    label: str
    attack_bonus: int
    damage: str
    damage_type: str


@dataclass(frozen=True)
class Ren55Mechanics:
    ruleset: str
    level: int
    subclass: str
    abilities: dict[str, int]
    skills: dict[str, int]
    passives: dict[str, int]
    saves: dict[str, int]
    proficiency_bonus: int
    attacks: dict[str, TargetAttack]
    armor_class: int
    initiative: int
    speed: int
    hit_points: dict[str, Any]
    focus: dict[str, Any]
    features: dict[str, Any]
    shadow: dict[str, Any]
    legacy_creation: dict[str, Any]


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise Ren55MigrationError(f"{path} precisa ser um mapa")
    return value


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise Ren55MigrationError(f"não foi possível ler {path}") from exc
    return _mapping(data, str(path))


def _damage_with_die(damage: str, die: str) -> str:
    match = DAMAGE_RE.match(damage)
    if match is None:
        raise Ren55MigrationError(f"dano base inesperado: {damage!r}")
    modifier = match.group(2) or ""
    return f"{die}{modifier}"


def _speed_feet(raw: object) -> int:
    if not isinstance(raw, str):
        raise Ren55MigrationError("combate.deslocamento.total precisa ser texto em pés")
    match = SPEED_RE.match(raw)
    if match is None:
        raise Ren55MigrationError(f"deslocamento total inválido: {raw!r}")
    return int(match.group(1))


def load(
    sheet_path: Path = DEFAULT_SHEET_PATH,
    migration_path: Path = DEFAULT_MIGRATION_PATH,
) -> Ren55Mechanics:
    base_path = Path(sheet_path)
    migration_file = Path(migration_path)
    raw = _load_yaml(base_path)
    migration = _load_yaml(migration_file)
    active = ficha_ren.load(base_path)

    if migration.get("personagem") != "Ren Kagehira":
        raise Ren55MigrationError("contrato de migração não pertence a Ren Kagehira")
    if migration.get("ruleset_alvo") != "dnd_5_5e":
        raise Ren55MigrationError("ruleset alvo da migração precisa ser dnd_5_5e")
    activation = _mapping(migration.get("ativacao"), "ativacao")
    if activation.get("aplica_antes_do_gate") is not False:
        raise Ren55MigrationError("migração de Ren não pode ativar antes da Task 8")

    identity = _mapping(raw.get("identidade"), "identidade")
    if identity.get("nivel") != 7 or identity.get("classe") != "Monge":
        raise Ren55MigrationError("Task 5 exige Ren Monge nível 7 como base")

    target_class = _mapping(migration.get("classe_alvo"), "classe_alvo")
    martial_die = target_class.get("dado_artes_marciais")
    if martial_die != "1d8":
        raise Ren55MigrationError("Monge 5.5e nível 7 precisa usar Artes Marciais 1d8")

    target_attacks: dict[str, TargetAttack] = {}
    for key, attack in active.attacks.items():
        damage = attack.damage
        if key in {"golpe_desarmado", "wakizashi"}:
            damage = _damage_with_die(damage, martial_die)
        target_attacks[key] = TargetAttack(
            label=attack.label,
            attack_bonus=attack.attack_bonus,
            damage=damage,
            damage_type=attack.damage_type,
        )

    active_ki = _mapping(active.resources.get("ki"), "recursos ativos.ki")
    focus = {
        "pontos_atuais": active_ki["pontos_atuais"],
        "pontos_maximos": target_class["pontos_focus_maximos"],
        "cd": target_class["cd_focus"],
        "recarga": migration["focus"]["recarga"],
    }
    if focus["pontos_atuais"] < 0 or focus["pontos_atuais"] > focus["pontos_maximos"]:
        raise Ren55MigrationError("mapeamento Ki→Focus produziria valor fora da faixa")

    combat = _mapping(raw.get("combate"), "combate")
    movement = _mapping(combat.get("deslocamento"), "combate.deslocamento")
    speed = _speed_feet(movement.get("total"))

    return Ren55Mechanics(
        ruleset="dnd_5_5e",
        level=7,
        subclass="Guerreiro das Sombras",
        abilities=dict(active.abilities),
        skills=dict(active.skills),
        passives=dict(active.passives),
        saves=dict(active.saves),
        proficiency_bonus=active.resources["proficiencia"]["bonus"],
        attacks=target_attacks,
        armor_class=active.armor_class,
        initiative=active.initiative,
        speed=speed,
        hit_points=dict(active.resources["pontos_de_vida"]),
        focus=focus,
        features=dict(migration["capacidades_nivel_7"]),
        shadow=dict(migration["guerreiro_das_sombras"]),
        legacy_creation=dict(migration["beneficios_de_criacao_preservados"]),
    )
