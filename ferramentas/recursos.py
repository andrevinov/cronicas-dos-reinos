#!/usr/bin/env python3
"""Consulta compacta de recursos de Ren e projeção de efeitos temporários.

Este módulo mantém duas responsabilidades pequenas e relacionadas ao hot path:

- localizar item, habilidade, talento ou ataque na ficha sem devolver a ficha inteira,
  combinando a mecânica encontrada com a disponibilidade corrente no estado;
- projetar deltas de ``estado.efeitos_temporarios`` sobre runtime/cena enquanto o
  checkpoint ainda não consolidou os eventos pendentes.

A representação canônica de um efeito temporário é um item em
``estado/estado-atual.yaml -> efeitos_temporarios.<id>``. O valor deve ser pequeno
e autoexplicativo, normalmente com ``nome``, ``efeito``, ``origem`` e pelo menos
``gatilho_consumo`` ou ``expira``. Criação usa ``set``; consumo/expiração usa
``remove`` no mesmo caminho.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterable

import contexto_core as core
import transacoes

SHEET_PATH = Path("personagens/jogador/ficha.yaml")
STATE_PATH = Path("estado/estado-atual.yaml")
EFFECTS_ROOT = "efeitos_temporarios"

RESOURCE_ROOTS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("recursos_de_classe",), "habilidade"),
    (("talentos",), "talento"),
    (("combate", "ataques"), "ataque"),
    (("equipamento", "itens"), "item"),
    (("background", "caracteristica_narrativa"), "caracteristica"),
)


def _get(document: Any, path: tuple[str, ...]) -> Any:
    current = document
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _label_from_key(key: str) -> str:
    return key.replace("_", " ").replace("-", " ").strip()


def _candidate(
    candidates: list[dict[str, Any]],
    *,
    label: str,
    value: Any,
    path: tuple[str, ...],
    kind: str,
) -> None:
    if not str(label).strip():
        return
    candidates.append(
        {
            "nome": str(label).strip(),
            "tipo": kind,
            "caminho": ".".join(path),
            "dados": value,
        }
    )


def _collect(value: Any, path: tuple[str, ...], kind: str, candidates: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        explicit_name = value.get("nome")
        if isinstance(explicit_name, str) and explicit_name.strip():
            _candidate(candidates, label=explicit_name, value=value, path=path, kind=kind)
        for key, child in value.items():
            if key == "nome":
                continue
            child_path = path + (str(key),)
            if isinstance(child, dict):
                label = child.get("nome") if isinstance(child.get("nome"), str) else _label_from_key(str(key))
                _candidate(candidates, label=label, value=child, path=child_path, kind=kind)
                _collect(child, child_path, kind, candidates)
            elif isinstance(child, list):
                _collect(child, child_path, kind, candidates)
        return

    if isinstance(value, list):
        for index, child in enumerate(value):
            child_path = path + (str(index),)
            if isinstance(child, dict):
                label = child.get("nome") if isinstance(child.get("nome"), str) else path[-1] if path else "recurso"
                _candidate(candidates, label=label, value=child, path=child_path, kind=kind)
                _collect(child, child_path, kind, candidates)
            elif isinstance(child, str):
                _candidate(candidates, label=child, value=child, path=child_path, kind=kind)


def _score(label: str, payload: Any, term: str) -> int:
    query = core.normalize(term)
    if not query:
        return 0
    label_n = core.normalize(label)
    try:
        body_n = core.normalize(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    except TypeError:
        body_n = core.normalize(payload)
    tokens = [token for token in query.split() if token]
    if query == label_n:
        return 140
    if query in label_n:
        return 110
    if tokens and all(token in label_n for token in tokens):
        return 90
    if query in body_n:
        return 70
    if tokens and all(token in body_n for token in tokens):
        return 55
    return 0


def find_sheet_resource(sheet: dict[str, Any], term: str) -> tuple[dict[str, Any] | None, list[str]]:
    candidates: list[dict[str, Any]] = []
    for root, kind in RESOURCE_ROOTS:
        value = _get(sheet, root)
        if value is None:
            continue
        _collect(value, root, kind, candidates)

    ranked = [(_score(item["nome"], item["dados"], term), item) for item in candidates]
    ranked = [(score, item) for score, item in ranked if score]
    ranked.sort(key=lambda pair: (-pair[0], len(pair[1]["caminho"]), pair[1]["caminho"]))
    if not ranked:
        return None, []

    best_score, best = ranked[0]
    if best_score < 55:
        return None, [item["nome"] for _, item in ranked[:5]]
    result = dict(best)
    result["dados"] = core.compact_value(best["dados"], string_limit=1400, list_limit=8, depth=5)
    return result, [item["nome"] for _, item in ranked[1:6]]


def find_availability(state: dict[str, Any], term: str) -> dict[str, Any] | None:
    resources = state.get("recursos") or {}
    mapping = resources.get("disponibilidades") if isinstance(resources, dict) else None
    if not isinstance(mapping, dict):
        return None
    ranked: list[tuple[int, str, Any]] = []
    for key, value in mapping.items():
        score = _score(str(key), value, term)
        if score:
            ranked.append((score, str(key), value))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    if not ranked or ranked[0][0] < 55:
        return None
    _, key, value = ranked[0]
    return {"id": key, "estado": core.compact_value(value, string_limit=900, list_limit=6, depth=3)}


def find_related_effects(state: dict[str, Any], term: str, *, limit: int = 3) -> list[dict[str, Any]]:
    mapping = state.get(EFFECTS_ROOT)
    if not isinstance(mapping, dict):
        return []
    ranked: list[tuple[int, str, Any]] = []
    for key, value in mapping.items():
        label = value.get("nome") if isinstance(value, dict) and isinstance(value.get("nome"), str) else str(key)
        score = max(_score(str(key), value, term), _score(label, value, term))
        if score:
            ranked.append((score, str(key), value))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [
        {
            "id": key,
            "dados": core.compact_value(value, string_limit=900, list_limit=6, depth=4),
        }
        for score, key, value in ranked[:limit]
        if score >= 55
    ]


def _current_records(state: dict[str, Any], records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    campaign = state.get("campanha") or {}
    session = campaign.get("sessao_atual") if isinstance(campaign, dict) else None
    return transacoes.pending_for_session(records, session if isinstance(session, int) else None)


def command_resource(repo: Path, term: str, records: Iterable[dict[str, Any]]) -> dict[str, Any]:
    sheet = core.load_yaml(repo / SHEET_PATH) or {}
    state = core.load_yaml(repo / STATE_PATH) or {}
    if not isinstance(sheet, dict) or not isinstance(state, dict):
        raise ValueError("ficha ou estado atual inválido para consulta de recurso")

    current = _current_records(state, records)
    effective_state, applied = transacoes.overlay_target(state, current, "estado")
    mechanic, suggestions = find_sheet_resource(sheet, term)
    availability = find_availability(effective_state, term)
    effects = find_related_effects(effective_state, term)
    found = mechanic is not None or availability is not None or bool(effects)
    sources = [SHEET_PATH.as_posix(), STATE_PATH.as_posix()]
    if applied:
        sources.append(transacoes.PENDING_PATH.as_posix())
    return core.envelope(
        "recurso",
        term,
        "L2",
        sources,
        {
            "encontrado": found,
            "mecanica": mechanic,
            "disponibilidade": availability,
            "efeitos_temporarios_relacionados": effects,
            "candidatos": suggestions if not found else [],
            "deltas_de_estado_pendentes_aplicados": applied,
        },
    )


def is_effect_delta(delta: dict[str, Any]) -> bool:
    return (
        delta.get("alvo") == "estado"
        and isinstance(delta.get("caminho"), str)
        and str(delta["caminho"]).startswith(EFFECTS_ROOT + ".")
        and delta.get("op") in {"set", "remove"}
        and delta.get("visibilidade", "operacional") != "narrador"
    )


def apply_pending_effects(
    context: dict[str, Any],
    scene: dict[str, Any] | None,
    records: Iterable[dict[str, Any]],
) -> int:
    """Projeta somente efeitos temporários; os demais deltas continuam em overlay_runtime."""
    session = ((context.get("sessao") or {}).get("numero"))
    current = transacoes.pending_for_session(records, session if isinstance(session, int) else None)
    applied = 0
    for record in current:
        for delta in record.get("deltas", []):
            if not is_effect_delta(delta):
                continue
            mapped = copy.deepcopy(delta)
            transacoes.apply_delta(context, mapped)
            if scene is not None:
                transacoes.apply_delta(scene, copy.deepcopy(mapped))
            applied += 1
    return applied
