from pathlib import Path
import textwrap


ADAPTER = r'''
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
'''


TESTS = r'''
from __future__ import annotations

import copy
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import _rolar_dados_core as core
import ficha_ren


class RenSheetSingleSourceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sheet_path = ROOT / "personagens/jogador/ficha.yaml"
        cls.sheet = yaml.safe_load(cls.sheet_path.read_text(encoding="utf-8"))

    def test_adapter_le_atributos_pericias_passivos_e_saves_da_ficha(self) -> None:
        mechanics = ficha_ren.load(self.sheet_path)
        attrs = self.sheet["atributos"]
        self.assertEqual(
            mechanics.abilities,
            {key: attrs[key]["modificador"] for key in ficha_ren.ABILITY_KEYS},
        )
        self.assertEqual(mechanics.skills, self.sheet["pericias"])
        self.assertEqual(
            mechanics.passives,
            {
                "percepcao": self.sheet["sentidos"]["percepcao_passiva"],
                "investigacao": self.sheet["sentidos"]["investigacao_passiva"],
                "intuicao": self.sheet["sentidos"]["intuicao_passiva"],
            },
        )
        self.assertEqual(
            mechanics.saves,
            {key: attrs[key]["bonus_salvaguarda"] for key in ficha_ren.ABILITY_KEYS},
        )

    def test_adapter_le_ataques_ca_iniciativa_e_recursos_da_ficha(self) -> None:
        mechanics = ficha_ren.load(self.sheet_path)
        self.assertEqual(
            [(item.label, item.attack_bonus, item.damage, item.damage_type) for item in mechanics.attacks.values()],
            [
                ("Golpe desarmado", 7, "1d6+4", "contundente"),
                ("Wakizashi", 7, "1d6+4", "perfurante"),
                ("Shuriken", 7, "1d4+4", "perfurante"),
            ],
        )
        self.assertEqual(
            mechanics.armor_class,
            self.sheet["combate"]["classe_de_armadura"]["valor"],
        )
        self.assertEqual(mechanics.initiative, self.sheet["combate"]["iniciativa"])
        self.assertEqual(
            mechanics.resources["pontos_de_vida"],
            {"atuais": 45, "maximos": 52, "dados_de_vida": "7d8"},
        )
        self.assertEqual(
            mechanics.resources["ki"],
            {"pontos_atuais": 1, "pontos_maximos": 7, "cd": 14},
        )
        self.assertEqual(mechanics.resources["proficiencia"], {"bonus": 3})

    def test_adaptador_reflete_edicao_da_ficha_sem_constante_python(self) -> None:
        changed = copy.deepcopy(self.sheet)
        changed["atributos"]["destreza"]["modificador"] = 9
        changed["atributos"]["destreza"]["bonus_salvaguarda"] = 12
        changed["pericias"]["furtividade"] = 11
        changed["sentidos"]["percepcao_passiva"] = 42
        changed["combate"]["classe_de_armadura"]["valor"] = 23
        changed["combate"]["iniciativa"] = 9
        changed["combate"]["ataques"][1]["bonus_ataque"] = 13
        changed["combate"]["ataques"][1]["dano"] = "2d8 + 5 cortante"
        changed["combate"]["pontos_de_vida"]["atuais"] = 44
        changed["recursos_de_classe"]["ki"]["pontos_atuais"] = 3
        changed["recursos_de_classe"]["ki"]["cd"] = 17

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ficha.yaml"
            path.write_text(
                yaml.safe_dump(changed, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            mechanics = ficha_ren.load(path)

        self.assertEqual(mechanics.abilities["destreza"], 9)
        self.assertEqual(mechanics.saves["destreza"], 12)
        self.assertEqual(mechanics.skills["furtividade"], 11)
        self.assertEqual(mechanics.passives["percepcao"], 42)
        self.assertEqual(mechanics.armor_class, 23)
        self.assertEqual(mechanics.initiative, 9)
        self.assertEqual(mechanics.attacks["wakizashi"].attack_bonus, 13)
        self.assertEqual(mechanics.attacks["wakizashi"].damage, "2d8+5")
        self.assertEqual(mechanics.attacks["wakizashi"].damage_type, "cortante")
        self.assertEqual(mechanics.resources["pontos_de_vida"]["atuais"], 44)
        self.assertEqual(mechanics.resources["ki"]["pontos_atuais"], 3)
        self.assertEqual(mechanics.resources["ki"]["cd"], 17)

    def test_core_nao_mantem_tabelas_mecanicas_duplicadas(self) -> None:
        for name in (
            "REN_ABILITIES",
            "REN_SKILLS",
            "REN_PASSIVES",
            "REN_SAVES",
            "REN_ATTACKS",
        ):
            self.assertFalse(hasattr(core, name), name)

    def test_ficha_invalida_falha_antes_do_rng(self) -> None:
        invalid = copy.deepcopy(self.sheet)
        invalid["pericias"]["percepcao"] = "seis"

        class ForbiddenRng:
            def __init__(self) -> None:
                self.calls = 0

            def randint(self, _low: int, _high: int) -> int:
                self.calls += 1
                raise AssertionError("RNG não deve ser chamado")

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ficha.yaml"
            path.write_text(
                yaml.safe_dump(invalid, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            old_sheet = core.CANONICAL_REN_SHEET
            old_rng = core.RNG
            forbidden = ForbiddenRng()
            core.CANONICAL_REN_SHEET = path
            core.RNG = forbidden
            try:
                stderr = io.StringIO()
                with redirect_stderr(stderr):
                    code = core.main(["ren", "pericia", "percepcao"])
                self.assertEqual(code, 2)
                self.assertEqual(forbidden.calls, 0)
                self.assertIn("pericias.percepcao precisa ser inteiro", stderr.getvalue())
            finally:
                core.CANONICAL_REN_SHEET = old_sheet
                core.RNG = old_rng
'''


REN_COMMANDS = r'''
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
    print(format_check(label, roll_d20(bonus, current_mode(args)), args.cd))
    return 0


def cmd_ren_skill(args: argparse.Namespace) -> int:
    ren = load_ren_mechanics()
    key = resolve_key(ren.skills, args.nome, "Perícia")
    bonus = ren.skills[key] + args.bonus_extra
    label = args.label or f"Teste de {REN_SKILL_LABELS[key]} (Ren)"
    print(format_check(label, roll_d20(bonus, current_mode(args)), args.cd))
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
    print(format_check(label, roll_d20(bonus, current_mode(args)), args.cd))
    return 0


def cmd_ren_initiative(args: argparse.Namespace) -> int:
    ren = load_ren_mechanics()
    bonus = ren.initiative + args.bonus_extra
    label = args.label or "Iniciativa (Ren)"
    print(format_check(label, roll_d20(bonus, current_mode(args)), None))
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
    spec = parse_dice(attack.damage)
    result = roll_dice(critical_spec(spec) if args.critico else spec)
    suffix = " crítico" if args.critico else ""
    print(
        f"Dano com {attack.label} (Ren{suffix}): "
        f"{format_dice_roll(result)} {attack.damage_type}."
    )
    return 0
'''


def remove_between(text: str, start: str, end: str) -> str:
    try:
        start_at = text.index(start)
        end_at = text.index(end, start_at)
    except ValueError as exc:
        raise SystemExit(f"patch marker not found: {start!r} -> {end!r}") from exc
    return text[:start_at] + text[end_at:]


Path("ferramentas/ficha_ren.py").write_text(
    textwrap.dedent(ADAPTER).lstrip(), encoding="utf-8"
)
Path("tests/test_ficha_ren.py").write_text(
    textwrap.dedent(TESTS).lstrip(), encoding="utf-8"
)

core_path = Path("ferramentas/_rolar_dados_core.py")
core = core_path.read_text(encoding="utf-8")
if "import ficha_ren" not in core:
    core = core.replace(
        "from random import SystemRandom\n",
        "from random import SystemRandom\n\nimport ficha_ren\n",
        1,
    )

core = remove_between(
    core,
    "@dataclass(frozen=True)\nclass AttackProfile:",
    "REN_ABILITIES: dict[str, int] = {",
)
for name, next_name in (
    ("REN_ABILITIES", "REN_ABILITY_LABELS"),
    ("REN_SKILLS", "REN_SKILL_LABELS"),
    ("REN_PASSIVES", "REN_PASSIVE_LABELS"),
    ("REN_SAVES", "REN_SAVE_LABELS"),
):
    core = remove_between(
        core,
        f"{name}: dict[str, int] = {{",
        f"{next_name}: dict[str, str] = {{",
    )
core = remove_between(
    core,
    "REN_ATTACKS: dict[str, AttackProfile] = {",
    "def normalize_key(text: str) -> str:",
)
bridge = (
    "AttackProfile = ficha_ren.AttackProfile\n"
    "CANONICAL_REN_SHEET = ficha_ren.DEFAULT_SHEET_PATH\n\n\n"
    "def load_ren_mechanics() -> ficha_ren.RenMechanics:\n"
    "    return ficha_ren.load(CANONICAL_REN_SHEET)\n\n\n"
)
core = core.replace(
    "def normalize_key(text: str) -> str:\n",
    bridge + "def normalize_key(text: str) -> str:\n",
    1,
)
start = core.index("def cmd_ren_list(_: argparse.Namespace) -> int:")
end = core.index("def cmd_npc_d20(args: argparse.Namespace) -> int:", start)
core = core[:start] + textwrap.dedent(REN_COMMANDS).lstrip() + "\n\n" + core[end:]
core_path.write_text(core, encoding="utf-8")

feat_path = Path("tests/test_talentos_ren.py")
feat = feat_path.read_text(encoding="utf-8")
old = '''    def test_core_espelha_atributos_pericias_salvaguarda_e_passivos(self):
        self.assertEqual(core.REN_ABILITIES["inteligencia"], 2)
        self.assertEqual(core.REN_ABILITIES["carisma"], 0)
        self.assertEqual(core.REN_SKILLS["investigacao"], 5)
        self.assertEqual(core.REN_SKILLS["percepcao"], 6)
        self.assertEqual(core.REN_SAVES["inteligencia"], 2)
        self.assertEqual(core.REN_PASSIVES["percepcao"], 21)
        self.assertEqual(core.REN_PASSIVES["investigacao"], 20)
'''
new = '''    def test_core_consome_adaptador_da_ficha_canonica(self):
        mechanics = core.load_ren_mechanics()
        self.assertEqual(mechanics.abilities["inteligencia"], 2)
        self.assertEqual(mechanics.abilities["carisma"], 0)
        self.assertEqual(mechanics.skills["investigacao"], 5)
        self.assertEqual(mechanics.skills["percepcao"], 6)
        self.assertEqual(mechanics.saves["inteligencia"], 2)
        self.assertEqual(mechanics.passives["percepcao"], 21)
        self.assertEqual(mechanics.passives["investigacao"], 20)
'''
if old not in feat:
    raise SystemExit("old Ren mirror test not found")
feat_path.write_text(feat.replace(old, new, 1), encoding="utf-8")

quality_path = Path("tests/test_qualidade_abordagem.py")
quality = quality_path.read_text(encoding="utf-8")
old = '        self.assertEqual(roller.REN_SKILLS["furtividade"], 7)\n'
new = '        self.assertEqual(roller.load_ren_mechanics().skills["furtividade"], 7)\n'
if old not in quality:
    raise SystemExit("approach Ren skill assertion not found")
quality_path.write_text(quality.replace(old, new, 1), encoding="utf-8")

campaign_path = Path("campanha.yaml")
campaign = campaign_path.read_text(encoding="utf-8")
old = "          task_3_ficha_fonte_unica: false\n"
if old not in campaign:
    raise SystemExit("Task 3 gate marker not found")
campaign = campaign.replace(old, "          task_3_ficha_fonte_unica: true\n", 1)
reference = '    rolador_de_dados: "ferramentas/rolar-dados.py"\n'
if reference not in campaign:
    raise SystemExit("roller reference marker not found")
campaign = campaign.replace(
    reference,
    reference + '    adaptador_ficha_ren: "ferramentas/ficha_ren.py"\n',
    1,
)
campaign_path.write_text(campaign, encoding="utf-8")

docs_path = Path("docs/agente/regras-e-rolagens.md")
docs = docs_path.read_text(encoding="utf-8")
marker = "## Filosofia de fidelidade: aproximadamente 70%\n"
section = '''## Ficha mecânica única de Ren

`personagens/jogador/ficha.yaml` é a única fonte persistida dos números mecânicos de Ren. `ferramentas/ficha_ren.py` apenas valida e adapta essa ficha para os consumidores; não mantém cópia numérica própria. O rolador não deve declarar tabelas paralelas de atributos, perícias, passivos, salvaguardas, ataques, CA, iniciativa ou recursos de Ren.

Qualquer comando `ren ...` carrega e valida a ficha antes de chamar o RNG. Ficha ausente ou mecanicamente inválida deve falhar fechado antes da rolagem, em vez de recorrer a valores Python antigos ou defaults silenciosos.

'''
if marker not in docs:
    raise SystemExit("docs marker not found")
docs_path.write_text(docs.replace(marker, section + marker, 1), encoding="utf-8")
