from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import ficha_ren
import gate_adnd
import mecanica_dnd_5_5e as dnd
import ruleset_5_5e

_spec = importlib.util.spec_from_file_location("rolar_dados_publico_task8", TOOLS / "rolar-dados.py")
assert _spec is not None and _spec.loader is not None
rolar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rolar)


class FixedRng:
    def __init__(self, values):
        self.values = list(values)
        self.index = 0

    def randint(self, low: int, high: int) -> int:
        value = self.values[self.index]
        self.index += 1
        if not low <= value <= high:
            raise AssertionError(value)
        return value


class Ruleset55ActivationE2ETest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sheet = ficha_ren.load(ROOT / "personagens/jogador/ficha.yaml")
        cls.state = yaml.safe_load((ROOT / "estado/estado-atual.yaml").read_text(encoding="utf-8"))

    def test_gate_final_nao_encontra_estado_hibrido(self) -> None:
        self.assertEqual(ruleset_5_5e.validate(ROOT), [])

    def test_furtividade_e_actor_continuam_operacionais(self) -> None:
        stealth = dnd.perform_check(self.sheet.skills["furtividade"], 15, "normal", rng=FixedRng([10]))
        self.assertTrue(stealth.success)
        self.assertEqual(stealth.roll.total, 17)
        argv, note = rolar._apply_actor(["ren", "pericia", "enganacao", "--cd", "12", "--actor-outra-identidade"])
        self.assertIn("--vantagem", argv)
        self.assertIn("Actor", note)

    def test_combate_e_critico_usam_artes_marciais_d8(self) -> None:
        attack = self.sheet.attacks["golpe_desarmado"]
        self.assertEqual((attack.attack_bonus, attack.damage), (7, "1d8+4"))
        result = dnd.perform_attack(attack.attack_bonus, 17, "normal", rng=FixedRng([20]))
        self.assertTrue(result.critical)
        damage = dnd.roll_damage(attack.damage, critical=True, rng=FixedRng([4, 5]))
        self.assertEqual(damage.rolls, [4, 5])
        self.assertEqual(damage.total, 13)

    def test_focus_e_shadow_monk_estao_ativos_sem_recaste_2014(self) -> None:
        self.assertEqual(self.state["recursos"]["focus"]["atuais"], 1)
        self.assertNotIn("ki", self.state["recursos"])
        resources = yaml.safe_load((ROOT / "personagens/jogador/ficha.yaml").read_text(encoding="utf-8"))["recursos_de_classe"]
        self.assertEqual(resources["artes_sombrias"]["escuridao"]["custo_focus"], 1)
        self.assertNotIn("magias_com_ki", resources["artes_sombrias"])
        legacy = self.state["efeitos_temporarios"]["passos_sem_pegadas"]
        self.assertEqual(legacy["origem_ruleset"], "dnd_5e_2014")
        self.assertFalse(legacy["recastavel"])
        self.assertEqual(legacy["termino"], "23:30 de 19 Eleasis, 1372 DR")

    def test_encontro_adnd_convertido_atravessa_gate_e_nucleo_5_5e(self) -> None:
        fixture = yaml.safe_load((ROOT / "tests/fixtures/adnd-encounter-5-5e.yaml").read_text(encoding="utf-8"))
        validated = gate_adnd.validate_material(ROOT, fixture, for_runtime=True)
        self.assertEqual(validated["proveniencia_mecanica"]["adaptado_para"], "dnd_5_5e")
        attack = fixture["mecanica"]["ataque"]
        result = dnd.perform_attack(attack["bonus"], attack["ca_alvo"], "normal", rng=FixedRng([12]))
        self.assertTrue(result.hit)
        self.assertEqual(result.roll.total, 16)


if __name__ == "__main__":
    unittest.main()
