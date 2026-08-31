#!/usr/bin/env python3
"""Gate permanente de consistência do ruleset D&D 5.5e após a Task 8."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
OBSOLETE_SHIMS = (
    "ferramentas/ficha_ren_5_5e.py",
    "personagens/jogador/resumo-de-poderes-5-5e.md",
)


def load(repo: Path, rel: str) -> Any:
    return yaml.safe_load((repo / rel).read_text(encoding="utf-8"))


def validate(repo: Path) -> list[str]:
    errors: list[str] = []
    try:
        campaign = load(repo, "campanha.yaml")
        sheet = load(repo, "personagens/jogador/ficha.yaml")
        state = load(repo, "estado/estado-atual.yaml")
        context = load(repo, "runtime/contexto.yaml")
        scene = load(repo, "runtime/cena.yaml")
        catalog = load(repo, "regras/catalogo.yaml")
        migration = load(repo, "personagens/jogador/migracao-5-5e.yaml")
    except Exception as exc:
        return [f"não foi possível carregar contrato 5.5e: {exc}"]

    ruleset = (((campaign or {}).get("sistema") or {}).get("ruleset") or {})
    activation = ((ruleset.get("migracao") or {}).get("ativacao") or {})
    requirements = activation.get("requisitos") or {}
    if ruleset.get("atual") != "dnd_5_5e" or ruleset.get("alvo") != "dnd_5_5e":
        errors.append("ruleset atual/alvo precisa ser dnd_5_5e")
    if (ruleset.get("migracao") or {}).get("status") != "concluida":
        errors.append("migração 5.5e precisa estar concluída")
    if activation.get("permitida") is not True:
        errors.append("ativação 5.5e precisa permanecer permitida")
    if not isinstance(requirements, dict) or not requirements or not all(value is True for value in requirements.values()):
        errors.append("todos os requisitos do gate de ativação precisam permanecer true")

    identity = (sheet or {}).get("identidade") or {}
    class_resources = (sheet or {}).get("recursos_de_classe") or {}
    if ((sheet or {}).get("personagem") or {}).get("sistema") != "Dungeons & Dragons 5.5e":
        errors.append("ficha ativa não declara Dungeons & Dragons 5.5e")
    if identity.get("subclasse") != "Guerreiro das Sombras":
        errors.append("ficha ativa não usa Guerreiro das Sombras")
    if "focus" not in class_resources or "ki" in class_resources:
        errors.append("ficha ativa precisa usar Focus e não pode manter Ki estrutural")
    old_features = {"aparar_projeteis", "quietude_da_mente", "golpes_potencializados_por_ki"}
    leftover = sorted(old_features & set(class_resources))
    if leftover:
        errors.append(f"ficha ativa ainda contém características 2014 substituídas: {leftover}")
    shadow = class_resources.get("artes_sombrias") or {}
    active_shadow = {key: value for key, value in shadow.items() if key != "removidas_na_5_5e"}
    rendered_shadow = yaml.safe_dump(active_shadow, allow_unicode=True).casefold()
    if "passos sem pegadas" in rendered_shadow or "silêncio" in rendered_shadow or "silencio" in rendered_shadow:
        errors.append("Shadow Arts ativa ainda oferece magia removida da versão 2014")

    state_resources = (state or {}).get("recursos") or {}
    state_person = (state or {}).get("personagem") or {}
    if state_person.get("subclasse") != "Guerreiro das Sombras":
        errors.append("estado vivo não usa Guerreiro das Sombras")
    if "focus" not in state_resources or "ki" in state_resources:
        errors.append("estado vivo precisa usar Focus e não pode manter Ki estrutural")
    availability = state_resources.get("disponibilidades") or {}
    if "silencio" in availability or "silêncio" in availability:
        errors.append("estado vivo ainda oferece Silêncio como capacidade recastável")

    legacy = ((state or {}).get("efeitos_temporarios") or {}).get("passos_sem_pegadas")
    if legacy is not None:
        if not isinstance(legacy, dict):
            errors.append("efeito legado Passos sem Pegadas precisa ser mapa")
        else:
            if legacy.get("origem_ruleset") != "dnd_5e_2014":
                errors.append("Passos sem Pegadas preservado precisa declarar origem 2014")
            if legacy.get("preservado_por_migracao") is not True or legacy.get("recastavel") is not False:
                errors.append("Passos sem Pegadas legado precisa ser preservado e não recastável")

    focus_sheet = class_resources.get("focus") or {}
    focus_state = state_resources.get("focus") or {}
    if focus_sheet.get("pontos_atuais") != focus_state.get("atuais") or focus_sheet.get("pontos_maximos") != focus_state.get("maximos"):
        errors.append("Focus diverge entre ficha e estado")

    context_resources = (context or {}).get("recursos") or {}
    scene_mechanics = (scene or {}).get("mecanica_imediata") or {}
    if "focus" not in context_resources or "ki" in context_resources:
        errors.append("runtime/contexto precisa usar Focus sem Ki")
    expected_focus = {"atuais": focus_state.get("atuais"), "maximos": focus_state.get("maximos")}
    if context_resources.get("focus") != expected_focus:
        errors.append("Focus do runtime diverge do estado")
    expected_text = f"{focus_state.get('atuais')}/{focus_state.get('maximos')}"
    if scene_mechanics.get("focus") != expected_text or "ki" in scene_mechanics:
        errors.append("runtime/cena precisa expor Focus coerente sem Ki")

    rules = (catalog or {}).get("regras") or []
    bad_rules = [item.get("id") for item in rules if isinstance(item, dict) and item.get("ruleset") != "dnd_5_5e"]
    if bad_rules:
        errors.append(f"catálogo operacional contém regras fora de 5.5e: {bad_rules}")

    if (migration or {}).get("status") != "ativada" or ((migration or {}).get("ativacao") or {}).get("concluida") is not True:
        errors.append("registro de migração de Ren não está marcado como ativado")
    for rel in OBSOLETE_SHIMS:
        if (repo / rel).exists():
            errors.append(f"shim temporário da migração ainda existe: {rel}")
    summary = (repo / "personagens/jogador/resumo-de-poderes.md").read_text(encoding="utf-8")
    if "STAGED / NÃO OPERACIONAL" in summary or "Guerreiro das Sombras" not in summary:
        errors.append("resumo de poderes ativo não foi promovido corretamente")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["check"], default="check")
    parser.add_argument("--repo", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    errors = validate(args.repo.resolve())
    if errors:
        print("FALHA — consistência D&D 5.5e")
        for error in errors:
            print(f"- {error}")
        return 1
    print("OK — ruleset D&D 5.5e ativo e sem estado híbrido.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
