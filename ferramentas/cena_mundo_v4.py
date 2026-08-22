#!/usr/bin/env python3
"""Extensão da abertura transacional com stubs persistentes e ecologia local."""
from __future__ import annotations

import argparse
import copy
from pathlib import Path
from typing import Any

import _cena_mundo_core as _core
import ecologia_local
import npc_stubs

# Reexporta a API legado para que imports existentes continuem funcionando.
for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

_base_build_parser = _core.build_parser
_base_local_spec = _core._local_spec


def _local_spec(
    repo: Path,
    place: str | None,
    action: str | None,
    tier: int | None,
    danger: str | None,
) -> dict[str, Any] | None:
    """Anexa ecologia somente depois de o local já estar canonizado."""
    spec = _base_local_spec(repo, place, action, tier, danger)
    if spec is None:
        return None

    # Fixtures legados sem a camada de identidade de locais continuam podendo
    # exercitar outras regras. Produção (ou fixture que declarou registro local)
    # permanece fail-closed: se há local canônico, o perfil ecológico é obrigatório.
    if spec.get("resolucao_local") == "fixture_sem_registro":
        return spec

    try:
        ecology = ecologia_local.lookup_canonical(repo, spec["local_id"])
    except ecologia_local.LocalEcologyError as exc:
        raise _core.SceneGateError(str(exc)) from exc
    spec = copy.deepcopy(spec)
    spec["ecologia"] = copy.deepcopy(ecology["perfil"])
    spec["fontes_lidas"] = list(
        dict.fromkeys([*(spec.get("fontes_lidas") or []), *ecology["fontes_lidas"]])
    )
    return spec


def _resolve_npcs(
    repo: Path,
    refs: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]], list[str], bool]:
    if len(refs) > _core.MAX_SCENE_NPCS:
        raise _core.SceneGateError(
            f"abertura de cena aceita no máximo {_core.MAX_SCENE_NPCS} referências de NPC"
        )
    if not refs:
        return [], [], [], False
    try:
        index = _core.oportunidades.load_index(repo)
    except _core.oportunidades.OpportunityError as exc:
        raise _core.SceneGateError(str(exc)) from exc

    unique: dict[str, dict[str, Any]] = {}
    duplicates: list[dict[str, str]] = []
    sources = [_core.oportunidades.INDEX.as_posix()]

    for raw in refs:
        # Repetição do mesmo nome novo na própria preparação deve colapsar antes
        # de depender de persistência no índice.
        raw_query = npc_stubs.normalize_ref(raw)
        repeated = next(
            (
                item
                for item in unique.values()
                if isinstance(item.get("identidade_stub"), dict)
                and raw_query
                in {
                    npc_stubs.normalize_ref(item["npc_id"]),
                    npc_stubs.normalize_ref(item["identidade_stub"]["nome"]),
                }
            ),
            None,
        )
        if repeated is not None:
            duplicates.append({"recebido": str(raw), "npc_id": repeated["npc_id"]})
            continue

        try:
            resolution = _core.interacoes_mundo.resolve_encounter_npc(repo, raw, index)
            if resolution.get("resolucao") == "alias_univoco":
                try:
                    sources.extend(
                        npc_stubs.guard_resolution(repo, str(raw), str(resolution["npc_id"]))
                    )
                except npc_stubs.NpcStubError as exc:
                    raise _core.SceneGateError(str(exc)) from exc
        except _core.interacoes_mundo.IntegrationError:
            try:
                resolution = npc_stubs.resolve_or_propose(repo, str(raw))
            except npc_stubs.NpcStubError as exc:
                raise _core.SceneGateError(str(exc)) from exc

        sources.extend(resolution.get("fontes_lidas") or [])
        canonical = resolution["npc_id"]
        if canonical in unique:
            duplicates.append({"recebido": str(raw), "npc_id": canonical})
            continue
        unique[canonical] = resolution

    ordered = [unique[npc_id] for npc_id in sorted(unique)]
    profiles = index.get("perfis") or {}
    has_active_profile = any(
        not isinstance(item.get("identidade_stub"), dict)
        and isinstance(profiles.get(item["npc_id"]), dict)
        and profiles[item["npc_id"]].get("estado") == "ativo"
        for item in ordered
    )
    return ordered, duplicates, list(dict.fromkeys(sources)), has_active_profile


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
    now: _core.mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    scene_id = _core._scene_id(scene_id)
    npc_refs = list(npcs or [])
    raw_context_tags = list(context_tags or [])
    try:
        normalized_context_tags = _core.contexto_cena.normalize_tags(raw_context_tags)
    except _core.contexto_cena.ContextSceneError as exc:
        raise _core.SceneGateError(str(exc)) from exc
    local_spec = _core._local_spec(repo, place, action, tier, danger)
    if local_spec is None and not npc_refs and not normalized_context_tags:
        raise _core.SceneGateError(
            "abertura de cena exige ao menos um gatilho local, NPC ou tag contextual"
        )

    resolutions, duplicates, resolution_sources, has_active_profile = _resolve_npcs(repo, npc_refs)
    canonical_npcs = [item["npc_id"] for item in resolutions]
    try:
        contextual = _core.contexto_cena.select_candidates(
            repo,
            normalized_context_tags,
            scene_id=scene_id,
            exclude_ids=canonical_npcs,
        )
    except _core.contexto_cena.ContextSceneError as exc:
        raise _core.SceneGateError(str(exc)) from exc

    current = now
    time_sources: list[str] = []
    if has_active_profile and current is None:
        try:
            current, time_sources = _core.interacoes_mundo._now(repo, None)
        except _core.interacoes_mundo.IntegrationError as exc:
            raise _core.SceneGateError(str(exc)) from exc

    local_result: dict[str, Any] | None = None
    sources = [
        *(local_spec.get("fontes_lidas") if local_spec is not None else []),
        *resolution_sources,
        *(contextual.get("fontes_lidas") or []),
        *time_sources,
    ]
    if local_spec is not None:
        try:
            local_result = _core.interacoes_mundo.local_event(
                repo,
                local_spec["local_id"],
                action=local_spec["acao"],
                tier=local_spec["tier"],
                danger=local_spec["periculosidade"],
            )
        except _core.interacoes_mundo.IntegrationError as exc:
            raise _core.SceneGateError(str(exc)) from exc
        local_result["local_ref_recebido"] = local_spec["local_ref_recebido"]
        local_result["resolucao_local"] = local_spec["resolucao_local"]
        if isinstance(local_spec.get("ecologia"), dict):
            local_result["ecologia"] = copy.deepcopy(local_spec["ecologia"])
        sources.extend(local_result.get("fontes_lidas") or [])

    encounters: list[dict[str, Any]] = []
    identities: dict[str, dict[str, Any]] = {}
    for resolution in resolutions:
        npc_id = resolution["npc_id"]
        identity = resolution.get("identidade_stub")
        if isinstance(identity, dict):
            identities[npc_id] = copy.deepcopy(identity)
            result = {
                "ok": True,
                "resultado": "interacao_normal",
                "motivo": (
                    "npc_persistente_sem_agenda"
                    if identity.get("stub_automatico")
                    else "npc_canonico_sem_perfil"
                ),
                "npc_id": npc_id,
                "persistencia": identity.get("persistencia"),
                "fontes_lidas": resolution.get("fontes_lidas") or [],
            }
            if resolution.get("recebido") != npc_id:
                result["npc_id_recebido"] = resolution.get("recebido")
                result["resolucao_id"] = resolution.get("resolucao")
        else:
            try:
                result = _core.interacoes_mundo.encounter_event(
                    repo,
                    npc_id,
                    now=current,
                    encounter_id=_core._encounter_id(scene_id, npc_id),
                )
            except _core.interacoes_mundo.IntegrationError as exc:
                raise _core.SceneGateError(str(exc)) from exc
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
        "stubs_npc": [identities[npc_id] for npc_id in sorted(identities)],
        "contexto_tags": contextual["tags"],
        "contexto_arco": contextual.get("arco"),
        "candidatos_contextuais": contextual["candidatos"],
        "presencas_contextuais": contextual.get("presencas") or [],
        "entradas_contextuais": contextual.get("entradas") or [],
        "operacoes_contextuais": contextual.get("operacoes") or [],
        "direcoes_contextuais": contextual.get("direcoes") or [],
        "encontros": encounters,
        "resumo": _core._summary(encounters, local_result, contextual),
        "regra": (
            "NPC já processado não consome novo gate; NPC recém-chegado usa encontro_id estável. "
            "NPC nomeado sem identidade pode receber stub persistente_sem_agenda somente na confirmação. "
            "Ecologia local restringe plausibilidade, mas não estabelece presença ou evento. "
            "Tags contextuais usam namespace tipo:valor; presença exige coincidência local explícita. "
            "Candidatos contextuais são somente obrigações de avaliar: não estabelecem aparição, "
            "não executam linha operacional e não avançam direção canônica."
        ),
        "fontes_lidas": list(dict.fromkeys(sources)),
    }


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
    now: _core.mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    expected = _core._text(preparation_id, "preparacao_id")
    fresh = _core.prepare_scene(
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
        raise _core.SceneGateError(
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
    try:
        persisted = npc_stubs.ensure_many(
            repo,
            committed.get("stubs_npc") or [],
            scene_id=scene_id,
        )
    except npc_stubs.NpcStubError as exc:
        raise _core.SceneGateError(str(exc)) from exc
    committed["stubs_npc_persistidos"] = persisted
    committed["fase"] = "confirmacao"
    committed["preparacao_id"] = expected
    committed["preparacao_revalidada"] = True
    committed["mutacoes_aplicadas"] = True
    return committed


def _context_tag_arg(value: str) -> str:
    """Valida e normaliza `--contexto-tag` já na borda do argparse."""
    try:
        return _core.contexto_cena.normalize_tag(value)
    except _core.contexto_cena.ContextSceneError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _configure_context_tag_actions(parser: argparse.ArgumentParser) -> None:
    for action in parser._actions:
        if action.dest == "contexto_tag":
            action.type = _context_tag_arg
            action.help = (
                "tag contextual tipada tipo:valor; tipos: local, assunto, acao, pessoa, risco; "
                "máximo 8, sem busca semântica"
            )
        if isinstance(action, argparse._SubParsersAction):
            for subparser in action.choices.values():
                _configure_context_tag_actions(subparser)


def build_parser() -> argparse.ArgumentParser:
    parser = _base_build_parser()
    _configure_context_tag_actions(parser)
    return parser


# As funções do core resolvem nomes no próprio namespace; redirecionar os símbolos
# faz prepare_scene/main reutilizarem todo o contrato existente sem duplicar CLI.
_core._local_spec = _local_spec
_core._resolve_npcs = _resolve_npcs
_core.open_scene = open_scene
_core.confirm_scene = confirm_scene
_core.build_parser = build_parser

prepare_scene = _core.prepare_scene
main = _core.main


if __name__ == "__main__":
    raise SystemExit(main())
