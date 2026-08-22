#!/usr/bin/env python3
"""Porta transacional para gatilhos reativos na abertura/alteração de uma cena.

A narração ao vivo usa duas fases:

- ``preparar``: calcula contexto, mapa de recompensa e gates de encontro contra
  sombras em memória, sem persistir qualquer efeito;
- ``confirmar``: refaz a preparação, valida seu identificador e só então aplica
  as mesmas primitivas mutantes já existentes.

``open_scene`` permanece como primitiva de baixo nível para manutenção/testes e
é deliberadamente mutante. O CLI não a expõe diretamente.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import yaml

import contexto_cena
import interacoes_mundo
import locais
import mundo
import oportunidades
import recompensas

MAX_SCENE_NPCS = 12
SCENE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}$")
PREPARATION_PREFIX = "scene-prep-"


class SceneGateError(ValueError):
    pass


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SceneGateError(f"{label} deve ser texto não vazio")
    return value.strip()


def _scene_id(value: Any) -> str:
    value = _text(value, "cena_id")
    if not SCENE_ID_RE.fullmatch(value):
        raise SceneGateError(
            "cena_id deve usar somente ASCII alfanumérico, . _ : / - e ter no máximo 120 caracteres"
        )
    return value


def _local_spec(
    repo: Path,
    place: str | None,
    action: str | None,
    tier: int | None,
    danger: str | None,
) -> dict[str, Any] | None:
    supplied = [place is not None, action is not None, tier is not None, danger is not None]
    if not any(supplied):
        return None
    if not all(supplied):
        raise SceneGateError(
            "gatilho local exige --local, --acao, --tier e --periculosidade juntos"
        )
    try:
        resolution = locais.resolve(repo, place)
    except locais.LocationError as exc:
        raise SceneGateError(str(exc)) from exc
    if action not in interacoes_mundo.VALID_LOCAL_ACTIONS:
        raise SceneGateError("acao local deve ser entrar ou explorar")
    if not isinstance(tier, int) or isinstance(tier, bool) or tier < 1 or tier > 4:
        raise SceneGateError("tier local deve ficar entre 1 e 4")
    if danger not in recompensas.VALID_DANGER:
        raise SceneGateError(
            "periculosidade deve ser uma de: " + ", ".join(sorted(recompensas.VALID_DANGER))
        )
    return {
        "local_id": resolution["local_id"],
        "local_ref_recebido": resolution["recebido"],
        "resolucao_local": resolution["resolucao"],
        "acao": action,
        "tier": tier,
        "periculosidade": danger,
        "fontes_lidas": resolution["fontes_lidas"],
    }


def _resolve_npcs(
    repo: Path,
    refs: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[str], bool]:
    if len(refs) > MAX_SCENE_NPCS:
        raise SceneGateError(
            f"abertura de cena aceita no máximo {MAX_SCENE_NPCS} referências de NPC"
        )
    if not refs:
        return [], [], [], False
    try:
        index = oportunidades.load_index(repo)
    except oportunidades.OpportunityError as exc:
        raise SceneGateError(str(exc)) from exc

    unique: dict[str, dict[str, Any]] = {}
    duplicates: list[dict[str, str]] = []
    sources = [oportunidades.INDEX.as_posix()]
    for raw in refs:
        try:
            resolution = interacoes_mundo.resolve_encounter_npc(repo, raw, index)
        except interacoes_mundo.IntegrationError as exc:
            raise SceneGateError(str(exc)) from exc
        sources.extend(resolution.get("fontes_lidas") or [])
        canonical = resolution["npc_id"]
        if canonical in unique:
            duplicates.append({"recebido": str(raw), "npc_id": canonical})
            continue
        unique[canonical] = resolution

    ordered = [unique[npc_id] for npc_id in sorted(unique)]
    has_active_profile = any(
        isinstance(index["perfis"].get(item["npc_id"]), dict)
        and index["perfis"][item["npc_id"]].get("estado") == "ativo"
        for item in ordered
    )
    return ordered, duplicates, list(dict.fromkeys(sources)), has_active_profile


def _encounter_id(scene_id: str, npc_id: str) -> str:
    return f"scene:{scene_id}:npc:{npc_id}"


def _summary(
    encounters: list[dict[str, Any]],
    local: dict[str, Any] | None,
    contextual: dict[str, Any],
) -> dict[str, int]:
    return {
        "gatilhos_locais": 1 if local is not None else 0,
        "encontros": len(encounters),
        "candidatos_contextuais": len(contextual.get("candidatos") or []),
        "presencas_contextuais": len(contextual.get("presencas") or []),
        "entradas_contextuais": len(contextual.get("entradas") or []),
        "operacoes_contextuais": len(contextual.get("operacoes") or []),
        "direcoes_contextuais": len(contextual.get("direcoes") or []),
        "gates_sem_oportunidade": sum(
            item.get("motivo") == "gate_sem_oportunidade" for item in encounters
        ),
        "avaliacoes_sidequest": sum(
            item.get("resultado") == "avaliar_sidequest" for item in encounters
        ),
        "sem_perfil_ativo": sum(
            item.get("motivo") == "npc_sem_perfil_ativo" for item in encounters
        ),
        "encontros_ja_processados": sum(
            item.get("motivo") == "encontro_ja_processado" for item in encounters
        ),
    }


def open_scene(
    repo: Path,
    *,
    scene_id: str,
    npcs: list[str] | None = None,
    place: str | None = None,
    action: str | None = None,
    tier: int | None = None,
    danger: str | None = None,
    context_tags: list[str] | None = None,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    """Primitiva mutante: valida tudo primeiro e depois despacha os efeitos."""
    scene_id = _scene_id(scene_id)
    npc_refs = list(npcs or [])
    raw_context_tags = list(context_tags or [])
    try:
        normalized_context_tags = contexto_cena.normalize_tags(raw_context_tags)
    except contexto_cena.ContextSceneError as exc:
        raise SceneGateError(str(exc)) from exc
    local_spec = _local_spec(repo, place, action, tier, danger)
    if local_spec is None and not npc_refs and not normalized_context_tags:
        raise SceneGateError(
            "abertura de cena exige ao menos um gatilho local, NPC ou tag contextual"
        )

    # Toda identidade/configuração é validada antes do primeiro efeito.
    resolutions, duplicates, resolution_sources, has_active_profile = _resolve_npcs(
        repo, npc_refs
    )
    canonical_npcs = [item["npc_id"] for item in resolutions]
    try:
        contextual = contexto_cena.select_candidates(
            repo,
            normalized_context_tags,
            scene_id=scene_id,
            exclude_ids=canonical_npcs,
        )
    except contexto_cena.ContextSceneError as exc:
        raise SceneGateError(str(exc)) from exc

    current = now
    time_sources: list[str] = []
    if has_active_profile and current is None:
        try:
            current, time_sources = interacoes_mundo._now(repo, None)
        except interacoes_mundo.IntegrationError as exc:
            raise SceneGateError(str(exc)) from exc

    local_result: dict[str, Any] | None = None
    sources = [
        *(local_spec.get("fontes_lidas") if local_spec is not None else []),
        *resolution_sources,
        *(contextual.get("fontes_lidas") or []),
        *time_sources,
    ]
    if local_spec is not None:
        try:
            local_result = interacoes_mundo.local_event(
                repo,
                local_spec["local_id"],
                action=local_spec["acao"],
                tier=local_spec["tier"],
                danger=local_spec["periculosidade"],
            )
        except interacoes_mundo.IntegrationError as exc:
            raise SceneGateError(str(exc)) from exc
        local_result["local_ref_recebido"] = local_spec["local_ref_recebido"]
        local_result["resolucao_local"] = local_spec["resolucao_local"]
        sources.extend(local_result.get("fontes_lidas") or [])

    encounters: list[dict[str, Any]] = []
    for resolution in resolutions:
        npc_id = resolution["npc_id"]
        try:
            result = interacoes_mundo.encounter_event(
                repo,
                npc_id,
                now=current,
                encounter_id=_encounter_id(scene_id, npc_id),
            )
        except interacoes_mundo.IntegrationError as exc:
            raise SceneGateError(str(exc)) from exc
        encounters.append(result)
        sources.extend(result.get("fontes_lidas") or [])

    return {
        "ok": True,
        "gatilho": "abertura_cena_reativa",
        "cena_id": scene_id,
        "local": local_result,
        "npcs_recebidos": npc_refs,
        "npcs_canonicos": canonical_npcs,
        "duplicatas_colapsadas": duplicates,
        "contexto_tags": contextual["tags"],
        "contexto_arco": contextual.get("arco"),
        "candidatos_contextuais": contextual["candidatos"],
        "presencas_contextuais": contextual.get("presencas") or [],
        "entradas_contextuais": contextual.get("entradas") or [],
        "operacoes_contextuais": contextual.get("operacoes") or [],
        "direcoes_contextuais": contextual.get("direcoes") or [],
        "encontros": encounters,
        "resumo": _summary(encounters, local_result, contextual),
        "regra": (
            "NPC já processado não consome novo gate; NPC recém-chegado usa encontro_id estável. "
            "Candidatos contextuais são somente obrigações de avaliar: não estabelecem aparição, "
            "não executam linha operacional e não avançam direção canônica."
        ),
        "fontes_lidas": list(dict.fromkeys(sources)),
    }


def _validate_preview_install(path: Path, data: dict[str, Any]) -> None:
    """Mantém a validação de órfão divergente sem instalar arquivo novo."""
    if not path.exists():
        return
    dump = getattr(recompensas, "_dump", None)
    if dump is None:
        return
    rendered = dump(data)
    if path.read_text(encoding="utf-8") != rendered:
        raise recompensas.RewardMapError(
            f"artefato já existe com conteúdo divergente: {path}"
        )


@contextmanager
def _preview_effects(repo: Path) -> Iterator[None]:
    """Substitui somente as portas de escrita por sombras em memória.

    O gate de sidequest precisa enxergar, dentro da mesma preparação, as mudanças
    simuladas pelo NPC anterior. Por isso ``load_state`` e ``atomic`` compartilham
    uma sombra sequencial. Nenhuma alteração toca o repositório.
    """
    patched: list[tuple[Any, str, Any]] = []
    shadow_state: dict[str, Any] | None = None

    def replace(module: Any, name: str, value: Any) -> Any | None:
        if not hasattr(module, name):
            return None
        original = getattr(module, name)
        patched.append((module, name, original))
        setattr(module, name, value)
        return original

    original_load_state = getattr(oportunidades, "load_state", None)

    if original_load_state is not None:
        def shadow_load_state(repo_arg: Path, index: dict[str, Any]) -> dict[str, Any]:
            nonlocal shadow_state
            if shadow_state is None:
                shadow_state = copy.deepcopy(original_load_state(repo_arg, index))
            return copy.deepcopy(shadow_state)

        replace(oportunidades, "load_state", shadow_load_state)

    if hasattr(oportunidades, "atomic"):
        def shadow_opportunity_atomic(path: Path, data: dict[str, Any]) -> None:
            nonlocal shadow_state
            state_path = repo / getattr(oportunidades, "STATE", Path("__missing__"))
            if Path(path) == state_path:
                shadow_state = copy.deepcopy(data)

        replace(oportunidades, "atomic", shadow_opportunity_atomic)

    if hasattr(recompensas, "install_once"):
        replace(recompensas, "install_once", _validate_preview_install)
    if hasattr(recompensas, "atomic"):
        replace(recompensas, "atomic", lambda _path, _data: None)

    try:
        yield
    finally:
        for module, name, original in reversed(patched):
            setattr(module, name, original)


def _source_fingerprints(repo: Path, sources: list[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for raw in sorted(dict.fromkeys(str(item) for item in sources)):
        rel = Path(raw)
        if rel.is_absolute() or ".." in rel.parts:
            result.append({"fonte": raw, "sha256": None})
            continue
        path = repo / rel
        digest = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        result.append({"fonte": raw, "sha256": digest})
    return result


def _preparation_id(repo: Path, preview: dict[str, Any]) -> str:
    payload = {
        "resultado": preview,
        "fontes": _source_fingerprints(repo, preview.get("fontes_lidas") or []),
    }
    rendered = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return PREPARATION_PREFIX + hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:20]


def prepare_scene(
    repo: Path,
    *,
    scene_id: str,
    npcs: list[str] | None = None,
    place: str | None = None,
    action: str | None = None,
    tier: int | None = None,
    danger: str | None = None,
    context_tags: list[str] | None = None,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    """Calcula exatamente o que a confirmação faria, sem escrever no repo."""
    with _preview_effects(repo):
        simulated = open_scene(
            repo,
            scene_id=scene_id,
            npcs=npcs,
            place=place,
            action=action,
            tier=tier,
            danger=danger,
            context_tags=context_tags,
            now=now,
        )

    preparation_id = _preparation_id(repo, simulated)
    result = copy.deepcopy(simulated)
    result["gatilho"] = "preparacao_cena_reativa"
    result["fase"] = "preparacao"
    result["preparacao_id"] = preparation_id
    result["mutacoes_aplicadas"] = False
    if isinstance(result.get("local"), dict) and "mapa_criado" in result["local"]:
        result["local"]["mapa_seria_criado"] = bool(result["local"]["mapa_criado"])
        result["local"]["mapa_criado"] = False
    result["regra_confirmacao"] = (
        "Narrar somente a cena aceita. Depois, confirmar com o mesmo conjunto de parâmetros "
        "e este preparacao_id. Preparação abandonada não deixa estado residual."
    )
    return result


def confirm_scene(
    repo: Path,
    *,
    preparation_id: str,
    scene_id: str,
    npcs: list[str] | None = None,
    place: str | None = None,
    action: str | None = None,
    tier: int | None = None,
    danger: str | None = None,
    context_tags: list[str] | None = None,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    """Revalida uma preparação e aplica os efeitos somente se ela ainda é atual."""
    expected = _text(preparation_id, "preparacao_id")
    fresh = prepare_scene(
        repo,
        scene_id=scene_id,
        npcs=npcs,
        place=place,
        action=action,
        tier=tier,
        danger=danger,
        context_tags=context_tags,
        now=now,
    )
    if fresh["preparacao_id"] != expected:
        raise SceneGateError(
            "preparação de cena ficou obsoleta; refaça `cena_mundo.py preparar` antes de confirmar"
        )

    committed = open_scene(
        repo,
        scene_id=scene_id,
        npcs=npcs,
        place=place,
        action=action,
        tier=tier,
        danger=danger,
        context_tags=context_tags,
        now=now,
    )
    committed["fase"] = "confirmacao"
    committed["preparacao_id"] = expected
    committed["preparacao_revalidada"] = True
    committed["mutacoes_aplicadas"] = True
    return committed


def _instant_arg(data: str | None, hour: str | None) -> mundo.WorldInstant | None:
    if data is None and hour is None:
        return None
    if not data or not hour:
        raise SceneGateError("--data e --hora devem ser usados juntos")
    try:
        return mundo.parse_instant(data, hour)
    except mundo.WorldEngineError as exc:
        raise SceneGateError(str(exc)) from exc


def _add_scene_args(parser: argparse.ArgumentParser, *, confirmation: bool = False) -> None:
    parser.add_argument("--cena-id", required=True)
    parser.add_argument("--npc", action="append", default=[])
    parser.add_argument(
        "--contexto-tag",
        action="append",
        default=[],
        help="rótulo já estabelecido pela cena; máximo 8, sem busca semântica",
    )
    parser.add_argument("--local")
    parser.add_argument("--acao", choices=sorted(interacoes_mundo.VALID_LOCAL_ACTIONS))
    parser.add_argument("--tier", type=int)
    parser.add_argument("--periculosidade", choices=sorted(recompensas.VALID_DANGER))
    parser.add_argument("--data")
    parser.add_argument("--hora")
    if confirmation:
        parser.add_argument("--preparacao-id", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)

    preparar = sub.add_parser(
        "preparar",
        help="calcula local + NPCs + contexto sem persistir efeitos",
    )
    _add_scene_args(preparar)

    # Compatibilidade operacional: o antigo verbo passa a ser seguro/read-only.
    abrir = sub.add_parser(
        "abrir",
        help="alias legado de preparar; não persiste efeitos",
    )
    _add_scene_args(abrir)

    confirmar = sub.add_parser(
        "confirmar",
        help="revalida a preparação aceita e só então persiste os efeitos",
    )
    _add_scene_args(confirmar, confirmation=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        kwargs = {
            "scene_id": args.cena_id,
            "npcs": args.npc,
            "place": args.local,
            "action": args.acao,
            "tier": args.tier,
            "danger": args.periculosidade,
            "context_tags": args.contexto_tag,
            "now": _instant_arg(args.data, args.hora),
        }
        if args.cmd in {"preparar", "abrir"}:
            result = prepare_scene(repo, **kwargs)
            if args.cmd == "abrir":
                result["alias_cli"] = "abrir->preparar"
        else:
            result = confirm_scene(
                repo,
                preparation_id=args.preparacao_id,
                **kwargs,
            )
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0
    except (
        SceneGateError,
        contexto_cena.ContextSceneError,
        interacoes_mundo.IntegrationError,
        locais.LocationError,
        oportunidades.OpportunityError,
        recompensas.RewardMapError,
        mundo.WorldEngineError,
    ) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
