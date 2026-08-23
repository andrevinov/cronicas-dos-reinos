#!/usr/bin/env python3
"""Ecologia determinística para deslocamentos urbanos em Ravens Bluff.

Esta camada NÃO cria um segundo baralho. Ela reutiliza catálogo, fichas,
ordenamento SHA-256 e writer do Local Microevent Deck, mas mantém um escopo
operacional de trânsito separado dos ``local_id`` canônicos. As frentes de
pressão de Ravens Bluff apenas mudam a textura elegível; este módulo nunca
avança nem escreve pressão.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import sys
from pathlib import Path
from typing import Any

import yaml

import ecologia_local
import microeventos_locais as micro
import pressao_ravens_bluff as pressao

SCHEMA = 1
TRANSIT_SCOPE = "ravens_bluff"
STATE_KEY = "transitos"
HISTORY_KEY = "historico_transito_recente"
MAX_HISTORY = 16

BASE_PROFILE: dict[str, Any] = {
    "familia": "transito_urbano",
    "acesso": "publico",
    "ritmo_baseline": {
        "amanhecer": 2,
        "dia": 3,
        "anoitecer": 3,
        "noite": 2,
    },
    "tags": ["rua_urbana"],
    "atores_comuns": [
        "pedestres",
        "carroceiros",
        "estivadores",
        "vendedores_ambulantes",
        "mensageiros",
        "patrulheiros",
    ],
    "canais_microevento": ["transito"],
}

# Nível > 0 torna a frente perceptível na textura urbana. O valor do nível não
# altera a frequência 3:1; serve para graduar a manifestação na narração.
FRONT_ECOLOGY: dict[str, tuple[str, str]] = {
    "custo_de_vida": ("comercio", "abastecimento"),
    "ocupacao_imobiliaria": ("residencia", "vizinhanca"),
    "crime_e_milicias": ("seguranca", "seguranca"),
    "desgaste_da_autoridade": ("institucional", "atendimento"),
    "presenca_oriental": ("carga", "carga"),
}


class TransitMicroeventError(ValueError):
    """Erro de contrato do escopo de trânsito urbano."""


def _scope(value: Any) -> str:
    if value != TRANSIT_SCOPE:
        raise TransitMicroeventError(
            f"escopo de trânsito inválido: {value!r}; esperado {TRANSIT_SCOPE}"
        )
    return TRANSIT_SCOPE


def _levels(profile: dict[str, Any], state: dict[str, Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for front_id in profile["frentes"]:
        value = state["frentes"][front_id]["nivel"]
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value <= 4
        ):
            raise TransitMicroeventError(f"nível inválido em {front_id}: {value!r}")
        result[front_id] = value
    if set(result) != set(FRONT_ECOLOGY):
        raise TransitMicroeventError(
            "frentes de pressão de Ravens Bluff divergiram do contrato de trânsito"
        )
    return result


def profile_for_levels(levels: dict[str, int]) -> dict[str, Any]:
    """Produz perfil ecológico em memória; nenhuma presença ou fato é criado."""
    if set(levels) != set(FRONT_ECOLOGY):
        raise TransitMicroeventError("snapshot de pressão incompleto para trânsito")
    profile = copy.deepcopy(BASE_PROFILE)
    for front_id, (tag, channel) in FRONT_ECOLOGY.items():
        level = levels[front_id]
        if (
            not isinstance(level, int)
            or isinstance(level, bool)
            or not 0 <= level <= 4
        ):
            raise TransitMicroeventError(f"nível inválido em {front_id}: {level!r}")
        if level <= 0:
            continue
        if tag not in profile["tags"]:
            profile["tags"].append(tag)
        if channel not in profile["canais_microevento"]:
            profile["canais_microevento"].append(channel)
    try:
        return ecologia_local._validate_profile("transito_ravens_bluff", profile)
    except ecologia_local.LocalEcologyError as exc:
        raise TransitMicroeventError(str(exc)) from exc


def _empty_scope_state() -> dict[str, Any]:
    return {
        "ocorrencia": {"ciclo": 0, "restantes": []},
        "cartas": {"ciclo": 0, "assinatura_pool": None, "restantes": []},
    }


def _validate_transit_state(
    state: dict[str, Any], index: dict[str, Any]
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    scopes = state.get(STATE_KEY)
    history = state.get(HISTORY_KEY)
    if scopes is None and history is None:
        return None, []
    if not isinstance(scopes, dict) or not isinstance(history, list):
        raise TransitMicroeventError(
            "estado de trânsito parcial: transitos e historico_transito_recente devem coexistir"
        )
    if set(scopes) != {TRANSIT_SCOPE}:
        raise TransitMicroeventError("estado de trânsito deve conter somente ravens_bluff")
    scope_state = scopes[TRANSIT_SCOPE]
    if not isinstance(scope_state, dict) or set(scope_state) != {"ocorrencia", "cartas"}:
        raise TransitMicroeventError("estado de trânsito de Ravens Bluff inválido")
    token_ids = {item["id"] for item in index["ocorrencia"]["fichas"]}
    card_ids = set(index["cartas"])
    try:
        micro._validate_deck(
            scope_state["ocorrencia"],
            "transitos.ravens_bluff.ocorrencia",
            allowed=token_ids,
            card_deck=False,
        )
        micro._validate_deck(
            scope_state["cartas"],
            "transitos.ravens_bluff.cartas",
            allowed=card_ids,
            card_deck=True,
        )
    except micro.LocalMicroeventError as exc:
        raise TransitMicroeventError(str(exc)) from exc
    if len(history) > MAX_HISTORY:
        raise TransitMicroeventError(
            f"historico_transito_recente excede {MAX_HISTORY} entradas"
        )
    for i, item in enumerate(history):
        label = f"historico_transito_recente[{i}]"
        if not isinstance(item, dict):
            raise TransitMicroeventError(f"{label} deve ser mapa")
        required = {
            "cena_id",
            "escopo_transito",
            "ficha_ocorrencia",
            "resultado",
            "pressao_niveis",
            "preparacao_fingerprint",
        }
        if not required <= set(item):
            raise TransitMicroeventError(f"{label} incompleto")
        if not isinstance(item["cena_id"], str) or not item["cena_id"].strip():
            raise TransitMicroeventError(f"{label}.cena_id inválido")
        _scope(item["escopo_transito"])
        if item["ficha_ocorrencia"] not in token_ids:
            raise TransitMicroeventError(f"{label}.ficha_ocorrencia inválida")
        if item["resultado"] not in {"rotina", "microevento"}:
            raise TransitMicroeventError(f"{label}.resultado inválido")
        card_id = item.get("carta_id")
        if card_id is not None and card_id not in card_ids:
            raise TransitMicroeventError(f"{label}.carta_id inválida")
        levels_raw = item["pressao_niveis"]
        if not isinstance(levels_raw, dict) or set(levels_raw) != set(FRONT_ECOLOGY):
            raise TransitMicroeventError(f"{label}.pressao_niveis inválido")
        for front_id, value in levels_raw.items():
            if (
                not isinstance(value, int)
                or isinstance(value, bool)
                or not 0 <= value <= 4
            ):
                raise TransitMicroeventError(
                    f"{label}.pressao_niveis.{front_id} inválido"
                )
        fingerprint = item["preparacao_fingerprint"]
        if (
            not isinstance(fingerprint, str)
            or len(fingerprint) != 64
            or any(ch not in "0123456789abcdef" for ch in fingerprint)
        ):
            raise TransitMicroeventError(f"{label}.preparacao_fingerprint inválido")
    return scope_state, history


def _semantic_fingerprint(
    *,
    scene_id: str,
    index: dict[str, Any],
    scope_state: dict[str, Any] | None,
    transit_history: list[dict[str, Any]],
    pressure_profile: dict[str, Any],
    pressure_state: dict[str, Any],
) -> str:
    snapshot = {
        "schema": SCHEMA,
        "escopo": TRANSIT_SCOPE,
        "cena_id": scene_id,
        "microeventos": {
            "semente": index["semente"],
            "ocorrencia": index["ocorrencia"],
            "cartas": index["cartas"],
        },
        "estado_transito": scope_state,
        "historico_transito": transit_history,
        "pressao_perfil": pressure_profile["frentes"],
        "pressao_estado": pressure_state["frentes"],
    }
    raw = yaml.safe_dump(
        snapshot, allow_unicode=True, sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _existing(
    history: list[dict[str, Any]], scene_id: str
) -> dict[str, Any] | None:
    for item in reversed(history):
        if (
            item.get("escopo_transito") == TRANSIT_SCOPE
            and item.get("cena_id") == scene_id
        ):
            return item
    return None


def _pressure_public(
    pressure_profile: dict[str, Any], levels: dict[str, int]
) -> dict[str, Any]:
    fronts: list[dict[str, Any]] = []
    for front_id in pressure_profile["frentes"]:
        level = levels[front_id]
        meta = pressure_profile["frentes"][front_id]["niveis"][level]
        fronts.append(
            {
                "id": front_id,
                "nivel": level,
                "titulo": meta["titulo"],
                "sinais": list(meta["sinais"]) if level > 0 else [],
            }
        )
    return {
        "max_nivel": max(levels.values()),
        "frentes_ativas": sum(level > 0 for level in levels.values()),
        "frentes": fronts,
        "regra": (
            "pressão apenas colore a textura elegível; trânsito não avança frentes, "
            "não revela automaticamente a causa e não altera a frequência 3:1"
        ),
    }


def _public_result(
    *,
    index: dict[str, Any],
    scene_id: str,
    history: dict[str, Any],
    pressure_profile: dict[str, Any],
    reused: bool,
) -> dict[str, Any]:
    levels = dict(history["pressao_niveis"])
    profile = profile_for_levels(levels)
    eligible = micro.eligible_cards(index, profile)
    result = history["resultado"]
    payload: dict[str, Any] = {
        "ok": True,
        "tipo": "microevento_transito_urbano",
        "escopo": TRANSIT_SCOPE,
        "cena_id": scene_id,
        "resultado": "avaliar_microevento" if result == "microevento" else "rotina",
        "ficha_ocorrencia": history["ficha_ocorrencia"],
        "reutilizado": reused,
        "cartas_elegiveis": len(eligible),
        "pressao_ravens_bluff": _pressure_public(pressure_profile, levels),
        "fontes_lidas": [
            micro.INDEX.as_posix(),
            micro.STATE.as_posix(),
            pressao.PROFILE.as_posix(),
            pressao.STATE.as_posix(),
        ],
        "regra": (
            "Deslocamento urbano é escopo operacional, não local canônico. A carta é "
            "candidata de textura: pode ser descartada por cânone forte sem rerroll; "
            "não cria NPC nomeado, combate, sidequest, recompensa, pista ou segredo."
        ),
    }
    if result != "microevento":
        return payload
    card_id = history.get("carta_id")
    card = index["cartas"].get(card_id)
    match = next((item for item in eligible if item["id"] == card_id), None)
    if not isinstance(card, dict) or match is None:
        raise TransitMicroeventError(
            f"carta confirmada de trânsito não é compatível com seu snapshot: {card_id}"
        )
    payload["carta"] = {
        "id": card_id,
        "nome": card["nome"],
        "categoria": card["categoria"],
        "premissa": card["premissa"],
        "canais_compativeis": match["canais"],
        "tags_compativeis": match["tags"],
        "atores_comuns": list(profile["atores_comuns"]),
        "guardrails": list(index["guardrails_globais"]),
    }
    return payload


def plan(repo: Path, *, scene_id: str, scope: str = TRANSIT_SCOPE) -> dict[str, Any]:
    """Planeja o trânsito sem persistir; confirmação decide o consumo."""
    _scope(scope)
    if not isinstance(scene_id, str) or not scene_id.strip():
        raise TransitMicroeventError("cena_id deve ser texto não vazio")
    scene_id = scene_id.strip()
    try:
        index = micro.load_index(repo)
        state = micro.load_state(repo, index)
        pressure_profile = pressao.load_profile(repo)
        pressure_state = pressao.load_state(repo, pressure_profile)
    except (micro.LocalMicroeventError, pressao.PressureError) as exc:
        raise TransitMicroeventError(str(exc)) from exc

    scope_state, transit_history = _validate_transit_state(state, index)
    existing = _existing(transit_history, scene_id)
    if existing is not None:
        return {
            "publico": _public_result(
                index=index,
                scene_id=scene_id,
                history=existing,
                pressure_profile=pressure_profile,
                reused=True,
            ),
            "fingerprint": existing["preparacao_fingerprint"],
            "estado_planejado": state,
            "alterou": False,
            "confirmado": True,
        }

    levels = _levels(pressure_profile, pressure_state)
    ecology = profile_for_levels(levels)
    eligible = micro.eligible_cards(index, ecology)
    if len(eligible) < micro.MIN_ELIGIBLE_PER_LOCAL:
        raise TransitMicroeventError(
            f"trânsito urbano possui somente {len(eligible)} cartas compatíveis; "
            f"mínimo {micro.MIN_ELIGIBLE_PER_LOCAL}"
        )
    fingerprint = _semantic_fingerprint(
        scene_id=scene_id,
        index=index,
        scope_state=scope_state,
        transit_history=transit_history,
        pressure_profile=pressure_profile,
        pressure_state=pressure_state,
    )

    planned = copy.deepcopy(state)
    planned.setdefault(STATE_KEY, {})
    planned.setdefault(HISTORY_KEY, [])
    if TRANSIT_SCOPE not in planned[STATE_KEY]:
        planned[STATE_KEY][TRANSIT_SCOPE] = _empty_scope_state()
    local_state = planned[STATE_KEY][TRANSIT_SCOPE]
    operational_label = f"transito_{TRANSIT_SCOPE}"
    token_id = micro._draw_occurrence(local_state["ocorrencia"], index, operational_label)
    token = next(item for item in index["ocorrencia"]["fichas"] if item["id"] == token_id)
    history: dict[str, Any] = {
        "cena_id": scene_id,
        "escopo_transito": TRANSIT_SCOPE,
        "ficha_ocorrencia": token_id,
        "resultado": token["resultado"],
        "pressao_niveis": levels,
        "preparacao_fingerprint": fingerprint,
    }
    if token["resultado"] == "microevento":
        history["carta_id"] = micro._draw_card(
            local_state["cartas"], index, operational_label, eligible
        )
    planned[HISTORY_KEY].append(history)
    planned[HISTORY_KEY] = planned[HISTORY_KEY][-MAX_HISTORY:]

    rendered = yaml.safe_dump(planned, allow_unicode=True, sort_keys=False).encode("utf-8")
    if len(rendered) > micro.MAX_STATE_BYTES:
        raise TransitMicroeventError(
            f"estado compartilhado de microeventos excederia {micro.MAX_STATE_BYTES} bytes"
        )
    return {
        "publico": _public_result(
            index=index,
            scene_id=scene_id,
            history=history,
            pressure_profile=pressure_profile,
            reused=False,
        ),
        "fingerprint": fingerprint,
        "estado_planejado": planned,
        "alterou": True,
        "confirmado": False,
    }


def revalidate(
    repo: Path,
    *,
    scene_id: str,
    expected_fingerprint: str,
    scope: str = TRANSIT_SCOPE,
) -> dict[str, Any]:
    planned = plan(repo, scene_id=scene_id, scope=scope)
    if planned["fingerprint"] != expected_fingerprint:
        raise TransitMicroeventError(
            "preparação do trânsito urbano ficou obsoleta; execute `cronica preparar` novamente"
        )
    return planned


def confirm(
    repo: Path,
    *,
    scene_id: str,
    expected_fingerprint: str,
    scope: str = TRANSIT_SCOPE,
) -> dict[str, Any]:
    """Consome exatamente o plano revalidado; nunca toca no estado de pressão."""
    planned = revalidate(
        repo,
        scene_id=scene_id,
        expected_fingerprint=expected_fingerprint,
        scope=scope,
    )
    if planned["confirmado"]:
        return {**planned["publico"], "mutacoes_aplicadas": False}
    try:
        changed = micro.commit_plan(
            repo,
            {
                "alterou": planned["alterou"],
                "estado_planejado": planned["estado_planejado"],
            },
        )
    except micro.LocalMicroeventError as exc:
        raise TransitMicroeventError(str(exc)) from exc
    return {**planned["publico"], "mutacoes_aplicadas": bool(changed)}


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    eligible_base = 0
    sources = [
        micro.INDEX.as_posix(),
        micro.STATE.as_posix(),
        pressao.PROFILE.as_posix(),
        pressao.STATE.as_posix(),
    ]
    try:
        index = micro.load_index(repo)
        state = micro.load_state(repo, index)
        pressure_profile = pressao.load_profile(repo)
        pressure_state = pressao.load_state(repo, pressure_profile)
        _validate_transit_state(state, index)
        base_levels = {front_id: 0 for front_id in FRONT_ECOLOGY}
        eligible_base = len(micro.eligible_cards(index, profile_for_levels(base_levels)))
        if eligible_base < micro.MIN_ELIGIBLE_PER_LOCAL:
            errors.append(
                f"trânsito basal possui somente {eligible_base} cartas compatíveis"
            )
        current = _levels(pressure_profile, pressure_state)
        profile_for_levels(current)
        maxed = {front_id: 4 for front_id in FRONT_ECOLOGY}
        profile_for_levels(maxed)
    except (
        TransitMicroeventError,
        micro.LocalMicroeventError,
        pressao.PressureError,
        ecologia_local.LocalEcologyError,
    ) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "escopo": TRANSIT_SCOPE,
        "cartas_basais_elegiveis": eligible_base,
        "erros": list(dict.fromkeys(errors)),
        "fontes_lidas": sources,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sim = sub.add_parser("simular", help="planeja trânsito read-only")
    sim.add_argument("--cena-id", required=True)
    sub.add_parser("check", help="valida integração do trânsito com baralho e pressão")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "simular":
            result = plan(repo, scene_id=args.cena_id)["publico"]
        else:
            result = validate_repo(repo)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0 if result.get("ok", True) else 1
    except TransitMicroeventError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
