"""Adaptador da ficha canônica de Ren para consumidores mecânicos.

Não calcula nem duplica números de Ren: transforma os valores já persistidos em
``personagens/jogador/ficha.yaml`` no formato pequeno usado pelo rolador.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_SHEET_PATH = Path(__file__).resolve().parents[1] / "personagens/jogador/ficha.yaml"
ABILITY_KEYS = (
    "forca",
    "destreza",
    "constituicao",
    "inteligencia",
    "sabedoria",
    "carisma",
)
PASSIVE_FIELDS = {
    "percepcao": "percepcao_passiva",
    "investigacao": "investigacao_passiva",
    "intuicao": "intuicao_passiva",
}
DAMAGE_RE = re.compile(
    r"^\s*((?:\d*)d\d+(?:\s*[+-]\s*\d+)?)\s+(.+?)\s*$",
    re.IGNORECASE,
)


class RenSheetError(ValueError):
    """A ficha canônica não satisfaz o contrato mecânico mínimo do rolador."""


@dataclass(frozen=True)
class AttackProfile:
    label: str
    attack_bonus: int
    damage: str
    damage_type: str


@dataclass(frozen=True)
class RenMechanics:
    abilities: dict[str, int]
    skills: dict[str, int]
    passives: dict[str, int]
    saves: dict[str, int]
    attacks: dict[str, AttackProfile]
    armor_class: int
    initiative: int
    resources: dict[str, Any]


def _normalize_key(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.strip().lower())
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    ascii_text = re.sub(r"[^a-z0-9]+", "_", ascii_text)
    return ascii_text.strip("_")


def _mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RenSheetError(f"{path} precisa ser um mapa")
    return value


def _required(mapping: dict[str, Any], key: str, path: str) -> Any:
    if key not in mapping:
        raise RenSheetError(f"campo mecânico ausente: {path}.{key}")
    return mapping[key]


def _integer(mapping: dict[str, Any], key: str, path: str) -> int:
    value = _required(mapping, key, path)
    if isinstance(value, bool) or not isinstance(value, int):
        raise RenSheetError(f"{path}.{key} precisa ser inteiro")
    return value


def _text(mapping: dict[str, Any], key: str, path: str) -> str:
    value = _required(mapping, key, path)
    if not isinstance(value, str) or not value.strip():
        raise RenSheetError(f"{path}.{key} precisa ser texto não vazio")
    return value.strip()


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise RenSheetError(f"não foi possível ler a ficha canônica: {path}") from exc
    return _mapping(data, "ficha")


def _skills(data: dict[str, Any]) -> dict[str, int]:
    raw = _mapping(_required(data, "pericias", "ficha"), "pericias")
    if not raw:
        raise RenSheetError("pericias não pode ser vazio")
    result: dict[str, int] = {}
    for name, value in raw.items():
        if not isinstance(name, str) or not name.strip():
            raise RenSheetError("pericias contém nome inválido")
        if isinstance(value, bool) or not isinstance(value, int):
            raise RenSheetError(f"pericias.{name} precisa ser inteiro")
        key = _normalize_key(name)
        if not key or key in result:
            raise RenSheetError(f"perícia duplicada ou inválida após normalização: {name!r}")
        result[key] = value
    return result


def _attacks(data: dict[str, Any]) -> dict[str, AttackProfile]:
    combat = _mapping(_required(data, "combate", "ficha"), "combate")
    raw = _required(combat, "ataques", "combate")
    if not isinstance(raw, list) or not raw:
        raise RenSheetError("combate.ataques precisa ser lista não vazia")
    result: dict[str, AttackProfile] = {}
    for index, item in enumerate(raw):
        path = f"combate.ataques[{index}]"
        attack = _mapping(item, path)
        name = _text(attack, "nome", path)
        key = _normalize_key(name)
        if not key or key in result:
            raise RenSheetError(f"ataque duplicado ou inválido: {name!r}")
        bonus = _integer(attack, "bonus_ataque", path)
        damage_text = _text(attack, "dano", path)
        match = DAMAGE_RE.match(damage_text)
        if match is None:
            raise RenSheetError(
                f"{path}.dano precisa conter expressão de dados e tipo de dano"
            )
        damage = re.sub(r"\s+", "", match.group(1))
        damage_type = match.group(2).strip()
        result[key] = AttackProfile(name, bonus, damage, damage_type)
    return result


def load(path: Path = DEFAULT_SHEET_PATH) -> RenMechanics:
    data = _load_yaml(Path(path))

    character = _mapping(_required(data, "personagem", "ficha"), "personagem")
    if _text(character, "nome", "personagem") != "Ren Kagehira":
        raise RenSheetError("a ficha mecânica esperada precisa pertencer a Ren Kagehira")

    attrs = _mapping(_required(data, "atributos", "ficha"), "atributos")
    abilities: dict[str, int] = {}
    saves: dict[str, int] = {}
    for key in ABILITY_KEYS:
        attr = _mapping(_required(attrs, key, "atributos"), f"atributos.{key}")
        abilities[key] = _integer(attr, "modificador", f"atributos.{key}")
        saves[key] = _integer(attr, "bonus_salvaguarda", f"atributos.{key}")

    senses = _mapping(_required(data, "sentidos", "ficha"), "sentidos")
    passives = {
        key: _integer(senses, field, "sentidos")
        for key, field in PASSIVE_FIELDS.items()
    }

    combat = _mapping(_required(data, "combate", "ficha"), "combate")
    armor = _mapping(
        _required(combat, "classe_de_armadura", "combate"),
        "combate.classe_de_armadura",
    )
    armor_class = _integer(armor, "valor", "combate.classe_de_armadura")
    initiative = _integer(combat, "iniciativa", "combate")

    hp = _mapping(
        _required(combat, "pontos_de_vida", "combate"),
        "combate.pontos_de_vida",
    )
    hp_max = _integer(hp, "maximos", "combate.pontos_de_vida")
    hp_current = _integer(hp, "atuais", "combate.pontos_de_vida")
    hit_dice = _text(hp, "dados_de_vida", "combate.pontos_de_vida")
    if hp_max < 1 or hp_current < 0 or hp_current > hp_max:
        raise RenSheetError("combate.pontos_de_vida possui faixa inválida")

    class_resources = _mapping(
        _required(data, "recursos_de_classe", "ficha"),
        "recursos_de_classe",
    )
    ki = _mapping(
        _required(class_resources, "ki", "recursos_de_classe"),
        "recursos_de_classe.ki",
    )
    ki_max = _integer(ki, "pontos_maximos", "recursos_de_classe.ki")
    ki_current = _integer(ki, "pontos_atuais", "recursos_de_classe.ki")
    ki_dc = _integer(ki, "cd", "recursos_de_classe.ki")
    if ki_max < 0 or ki_current < 0 or ki_current > ki_max:
        raise RenSheetError("recursos_de_classe.ki possui faixa inválida")

    proficiency = _mapping(_required(data, "proficiencia", "ficha"), "proficiencia")
    proficiency_bonus = _integer(proficiency, "bonus", "proficiencia")

    resources: dict[str, Any] = {
        "pontos_de_vida": {
            "atuais": hp_current,
            "maximos": hp_max,
            "dados_de_vida": hit_dice,
        },
        "ki": {
            "pontos_atuais": ki_current,
            "pontos_maximos": ki_max,
            "cd": ki_dc,
        },
        "proficiencia": {"bonus": proficiency_bonus},
    }

    return RenMechanics(
        abilities=abilities,
        skills=_skills(data),
        passives=passives,
        saves=saves,
        attacks=_attacks(data),
        armor_class=armor_class,
        initiative=initiative,
        resources=resources,
    )
