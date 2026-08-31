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
