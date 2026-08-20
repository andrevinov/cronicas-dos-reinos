from pathlib import Path
import sys

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
sys.path.insert(0, str(TOOLS))

import marcos_aparicao

shizune = marcos_aparicao.gate(ROOT, "kajiwara_shizune", supplied_level=6)
kurobane = marcos_aparicao.gate(ROOT, "kurobane_jinzaburo", supplied_level=6)
cho = marcos_aparicao.gate(ROOT, "sawagejo_cho", supplied_level=7)
pan = marcos_aparicao.gate(ROOT, "pan_chu", supplied_level=7)

assert shizune["permitido"] and shizune["modo"] == "avaliar_primeira_aparicao"
assert kurobane["permitido"] and kurobane["modo"] == "reaparicao_nao_bloqueada_pelo_marco"
assert not cho["permitido"] and cho["estado_marco"] == "bloqueado"
assert pan["permitido"] and pan["estado_marco"] == "elegivel" and pan["modo"] == "avaliar_primeira_aparicao"
assert "narrador/juppongatana/marcos-de-aparicao.md" not in shizune["fontes_lidas"]
print("smoke marcos de aparição: OK")
