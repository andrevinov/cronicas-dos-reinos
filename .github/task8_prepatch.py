from __future__ import annotations

from pathlib import Path

path = Path(__file__).with_name("task8_apply.py")
text = path.read_text(encoding="utf-8")

replacements = [
    (
        '    ("    if ki_max < 0 or not 0 <= ki_current <= ki_max:\\n        raise RenSheetError(\\"recursos_de_classe.ki possui faixa inválida\\")\\n", "    if focus_max < 0 or not 0 <= focus_current <= focus_max:\\n        raise RenSheetError(\\"recursos_de_classe.focus possui faixa inválida\\")\\n"),',
        '    ("    if ki_max < 0 or ki_current < 0 or ki_current > ki_max:\\n        raise RenSheetError(\\"recursos_de_classe.ki possui faixa inválida\\")\\n", "    if focus_max < 0 or focus_current < 0 or focus_current > focus_max:\\n        raise RenSheetError(\\"recursos_de_classe.focus possui faixa inválida\\")\\n"),',
    ),
    (
        '    ("        \\"ki\\": {\\n            \\"pontos_maximos\\": ki_max,\\n            \\"pontos_atuais\\": ki_current,\\n            \\"cd\\": ki_dc,\\n        },", "        \\"focus\\": {\\n            \\"pontos_maximos\\": focus_max,\\n            \\"pontos_atuais\\": focus_current,\\n            \\"cd\\": focus_dc,\\n        },"),',
        '    ("        \\"ki\\": {\\n            \\"pontos_atuais\\": ki_current,\\n            \\"pontos_maximos\\": ki_max,\\n            \\"cd\\": ki_dc,\\n        },", "        \\"focus\\": {\\n            \\"pontos_atuais\\": focus_current,\\n            \\"pontos_maximos\\": focus_max,\\n            \\"cd\\": focus_dc,\\n        },"),',
    ),
    (
        'self.mechanics.hit_points, {"atuais": 45, "maximos": 52}',
        'self.mechanics.resources["pontos_de_vida"], {"atuais": 45, "maximos": 52, "dados_de_vida": "7d8"}',
    ),
    (
        'self.assertEqual(self.mechanics.speed, 55)',
        'self.assertEqual(self.sheet_raw["combate"]["deslocamento"]["total"], "55 pés")',
    ),
    (
        'self.assertEqual(damage.rolls, (4, 5))',
        'self.assertEqual(damage.rolls, [4, 5])',
    ),
]
for old, new in replacements:
    if old in text:
        text = text.replace(old, new, 1)

old_shadow = '''    shadow = class_resources.get("artes_sombrias") or {}
    rendered_shadow = yaml.safe_dump(shadow, allow_unicode=True).casefold()
    if "passos sem pegadas" in rendered_shadow or "silêncio" in rendered_shadow or "silencio" in rendered_shadow:
        errors.append("Shadow Arts ativa ainda oferece magia removida da versão 2014")'''
new_shadow = '''    shadow = class_resources.get("artes_sombrias") or {}
    active_shadow = {key: value for key, value in shadow.items() if key != "removidas_na_5_5e"}
    rendered_shadow = yaml.safe_dump(active_shadow, allow_unicode=True).casefold()
    if "passos sem pegadas" in rendered_shadow or "silêncio" in rendered_shadow or "silencio" in rendered_shadow:
        errors.append("Shadow Arts ativa ainda oferece magia removida da versão 2014")'''
if old_shadow not in text:
    raise SystemExit("Task 8 Shadow Arts validator marker not found")
text = text.replace(old_shadow, new_shadow, 1)

path.write_text(text, encoding="utf-8")

# O teste integrado da Task 7 precisa seguir o ruleset vivo após o cutover:
# 5.5e entra no runtime e a ponte 2014, mesmo explicitamente declarada, é recusada
# quando usada como destino mecânico corrente.
test_path = Path("tests/test_gate_adnd.py")
test_text = test_path.read_text(encoding="utf-8")
old = '''        approved = dict(base)
        approved["proveniencia"] = provenance_2014(fallback=True)
        contract = mecanica_cronica.normalize_spec(ROOT, approved)
        self.assertEqual(contract["proveniencia"]["edicao_origem"], "adnd_2e")
        self.assertTrue(contract["proveniencia"]["fallback_2014"]["declarado"])

        future = dict(base)
        future["proveniencia"] = provenance_55()
        with self.assertRaisesRegex(mecanica_cronica.MechanicalContractError, "gate AD&D"):
            mecanica_cronica.normalize_spec(ROOT, future)'''
new = '''        approved = dict(base)
        approved["proveniencia"] = provenance_55()
        contract = mecanica_cronica.normalize_spec(ROOT, approved)
        self.assertEqual(contract["proveniencia"]["edicao_origem"], "adnd_2e")
        self.assertEqual(contract["proveniencia"]["adaptado_para"], "dnd_5_5e")
        self.assertNotIn("fallback_2014", contract["proveniencia"])

        legacy = dict(base)
        legacy["proveniencia"] = provenance_2014(fallback=True)
        with self.assertRaisesRegex(mecanica_cronica.MechanicalContractError, "gate AD&D"):
            mecanica_cronica.normalize_spec(ROOT, legacy)'''
if old not in test_text:
    raise SystemExit("Task 7 integration assertion marker not found")
test_path.write_text(test_text.replace(old, new, 1), encoding="utf-8")

print("Task 8 staging prepatch applied.")
