from __future__ import annotations

import shutil
import sys
import tempfile
import types
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
sys.path.insert(0, str(TOOLS))

# Dependências que a abertura contextual pura não deve tocar.
interacoes = types.ModuleType("interacoes_mundo")
interacoes.VALID_LOCAL_ACTIONS = {"entrar", "explorar"}
class IntegrationError(ValueError):
    pass
interacoes.IntegrationError = IntegrationError
interacoes.resolve_encounter_npc = lambda *a, **k: (_ for _ in ()).throw(AssertionError("não deveria resolver NPC"))
interacoes.local_event = lambda *a, **k: (_ for _ in ()).throw(AssertionError("não deveria tocar local"))
interacoes.encounter_event = lambda *a, **k: (_ for _ in ()).throw(AssertionError("não deveria tocar encontro"))
interacoes._now = lambda *a, **k: (_ for _ in ()).throw(AssertionError("não deveria ler tempo"))
sys.modules["interacoes_mundo"] = interacoes

mundo = types.ModuleType("mundo")
class WorldEngineError(ValueError):
    pass
class WorldInstant:
    pass
mundo.WorldEngineError = WorldEngineError
mundo.WorldInstant = WorldInstant
mundo.parse_instant = lambda d, h: (d, h)
sys.modules["mundo"] = mundo

oportunidades = types.ModuleType("oportunidades")
oportunidades.INDEX = Path("narrador/oportunidades/index.yaml")
class OpportunityError(ValueError):
    pass
oportunidades.OpportunityError = OpportunityError
oportunidades.load_index = lambda *a, **k: (_ for _ in ()).throw(AssertionError("não deveria ler oportunidades"))
sys.modules["oportunidades"] = oportunidades

recompensas = types.ModuleType("recompensas")
recompensas.VALID_DANGER = {"baixa", "media", "alta"}
class RewardMapError(ValueError):
    pass
recompensas.RewardMapError = RewardMapError
recompensas.local_id = lambda value: value
sys.modules["recompensas"] = recompensas

import cena_mundo

with tempfile.TemporaryDirectory() as tmp:
    repo = Path(tmp)
    for rel in [
        "narrador/mundo/contextos-cena.yaml",
        "narrador/arcos/index.yaml",
        "narrador/arcos/estado.yaml",
        "narrador/arcos/parte_1_uma_ponte_para_kozakura.yaml",
        "narrador/arcos/marcos-aparicao.yaml",
        "narrador/arcos/estado-marcos-aparicao.yaml",
    ]:
        src = ROOT / rel
        dst = repo / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    agents = {
        "schema_agentes": 2,
        "natureza": "reservado",
        "agentes": {
            "kajiwara_shizune": {
                "nome": "Kajiwara Shizune",
                "estado": "ativo",
                "presenca": "indeterminado",
                "atuacao_local": "exige_presenca_fisica",
            }
        },
    }
    path = repo / "narrador/agentes/index.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(agents, allow_unicode=True, sort_keys=False), encoding="utf-8")
    runtime = repo / "runtime/contexto.yaml"
    runtime.parent.mkdir(parents=True, exist_ok=True)
    runtime.write_text(yaml.safe_dump({"personagem": {"nivel": 6}}, sort_keys=False), encoding="utf-8")

    result = cena_mundo.open_scene(
        repo,
        scene_id="s009:tomas-escritorio",
        context_tags=["documentos", "escrituração"],
    )
    assert result["npcs_canonicos"] == []
    assert result["encontros"] == []
    assert result["local"] is None
    assert result["candidatos_contextuais"][0]["id"] == "kajiwara_shizune"
    assert result["candidatos_contextuais"][0]["modo_avaliacao"] == "avaliar_estabelecimento_presenca"
    assert result["resumo"]["candidatos_contextuais"] == 1
    assert "narrador/arcos/marcos-aparicao.yaml" in result["fontes_lidas"]
    assert "narrador/arcos/estado-marcos-aparicao.yaml" in result["fontes_lidas"]
    assert "runtime/contexto.yaml" in result["fontes_lidas"]
    assert "narrador/agentes/index.yaml" in result["fontes_lidas"]
    assert result["candidatos_contextuais"][0]["marco_aparicao"]["estado"] == "elegivel"

args = cena_mundo.build_parser().parse_args([
    "abrir", "--cena-id", "s009", "--contexto-tag", "documentos",
    "--contexto-tag", "escrituração",
])
assert args.contexto_tag == ["documentos", "escrituração"]
print("smoke integração cena_mundo/contexto/arco: OK")
