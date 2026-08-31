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
print("Task 8 staging prepatch applied.")
