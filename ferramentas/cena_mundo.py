#!/usr/bin/env python3
"""Porta única para gatilhos reativos na abertura/alteração de uma cena.

Objetivo: reduzir omissões de orquestração. Em vez de o narrador lembrar de chamar
separadamente recompensa local e gate de sidequest para cada NPC, esta porta
recebe o conjunto operacional da cena e despacha somente os gatilhos presentes.

Não é scheduler e não roda por turno comum. A mesma ``cena_id`` pode ser chamada
novamente quando o elenco/local muda: encontros já processados viram no-op por
idempotência e somente NPCs recém-chegados consomem novo gate.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

import interacoes_mundo
import mundo
import oportunidades
import recompensas

MAX_SCENE_NPCS = 12
SCENE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}$")


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
        local_id = recompensas.local_id(place)
    except recompensas.RewardMapError as exc:
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
        "local_id": local_id,
        "acao": action,
        "tier": tier,
        "periculosidade": danger,
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

    # Encontros que começam simultaneamente precisam de ordem independente da
    # ordem acidental dos argumentos do CLI.
    ordered = [unique[npc_id] for npc_id in sorted(unique)]
    has_active_profile = any(
        isinstance(index["perfis"].get(item["npc_id"]), dict)
        and index["perfis"][item["npc_id"]].get("estado") == "ativo"
        for item in ordered
    )
    return ordered, duplicates, list(dict.fromkeys(sources)), has_active_profile


def _encounter_id(scene_id: str, npc_id: str) -> str:
    return f"scene:{scene_id}:npc:{npc_id}"


def _summary(encounters: list[dict[str, Any]], local: dict[str, Any] | None) -> dict[str, int]:
    return {
        "gatilhos_locais": 1 if local is not None else 0,
        "encontros": len(encounters),
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
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    """Valida toda identidade antes de mutar e despacha gatilhos da cena."""
    scene_id = _scene_id(scene_id)
    npc_refs = list(npcs or [])
    local_spec = _local_spec(place, action, tier, danger)
    if local_spec is None and not npc_refs:
        raise SceneGateError("abertura de cena exige ao menos um gatilho local ou NPC")

    # Fase 1: resolução somente-leitura. Se houver typo/ambiguidade, nenhum mapa
    # ou gate é tocado.
    resolutions, duplicates, resolution_sources, has_active_profile = _resolve_npcs(
        repo, npc_refs
    )

    current = now
    time_sources: list[str] = []
    if has_active_profile and current is None:
        try:
            current, time_sources = interacoes_mundo._now(repo, None)
        except interacoes_mundo.IntegrationError as exc:
            raise SceneGateError(str(exc)) from exc

    local_result: dict[str, Any] | None = None
    sources = [*resolution_sources, *time_sources]
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
        "npcs_canonicos": [item["npc_id"] for item in resolutions],
        "duplicatas_colapsadas": duplicates,
        "encontros": encounters,
        "resumo": _summary(encounters, local_result),
        "regra": (
            "Repetir a mesma cena_id é seguro. NPC já processado não consome novo gate; "
            "NPC recém-chegado na mesma cena usa um encontro_id derivado estável."
        ),
        "fontes_lidas": list(dict.fromkeys(sources)),
    }


def _instant_arg(data: str | None, hour: str | None) -> mundo.WorldInstant | None:
    if data is None and hour is None:
        return None
    if not data or not hour:
        raise SceneGateError("--data e --hora devem ser usados juntos")
    try:
        return mundo.parse_instant(data, hour)
    except mundo.WorldEngineError as exc:
        raise SceneGateError(str(exc)) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)
    abrir = sub.add_parser("abrir", help="despacha local + NPCs de uma fronteira de cena")
    abrir.add_argument("--cena-id", required=True)
    abrir.add_argument("--npc", action="append", default=[])
    abrir.add_argument("--local")
    abrir.add_argument("--acao", choices=sorted(interacoes_mundo.VALID_LOCAL_ACTIONS))
    abrir.add_argument("--tier", type=int)
    abrir.add_argument("--periculosidade", choices=sorted(recompensas.VALID_DANGER))
    abrir.add_argument("--data")
    abrir.add_argument("--hora")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        result = open_scene(
            repo,
            scene_id=args.cena_id,
            npcs=args.npc,
            place=args.local,
            action=args.acao,
            tier=args.tier,
            danger=args.periculosidade,
            now=_instant_arg(args.data, args.hora),
        )
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0
    except (
        SceneGateError,
        interacoes_mundo.IntegrationError,
        oportunidades.OpportunityError,
        recompensas.RewardMapError,
        mundo.WorldEngineError,
    ) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
