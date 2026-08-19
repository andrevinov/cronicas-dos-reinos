#!/usr/bin/env python3
"""Rodapé mecânico determinístico para respostas narrativas.

Não faz inferência semântica e não abre estado canônico amplo. Usa somente os
snapshots runtime já quentes e o buffer transacional já existente, projetando os
deltas pendentes com a mesma função usada por ``contexto.py``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

import transacoes

CONTEXT_PATH = Path("runtime/contexto.yaml")
SCENE_PATH = Path("runtime/cena.yaml")
PREFIX = "RODAPE_CANONICO — "
CLOCK_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")


class FooterError(ValueError):
    """Runtime insuficiente ou inconsistente para formar o rodapé."""


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FooterError(f"arquivo ausente: {path}") from exc
    except yaml.YAMLError as exc:
        raise FooterError(f"YAML inválido em {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise FooterError(f"{path} deve ser mapa")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise FooterError(f"{label} deve ser texto não vazio")
    return " ".join(value.split())


def _clock(value: Any) -> str:
    text = _text(value, "tempo.hora_aproximada")
    match = CLOCK_RE.search(text)
    if not match:
        raise FooterError(f"hora sem HH:MM reconhecível: {text!r}")
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def _date(value: Any) -> str:
    text = _text(value, "tempo.data")
    match = re.fullmatch(r"(\d{1,2})\s+([A-Za-zÀ-ÿ'-]+),\s*\d+\s*DR", text)
    if match:
        return f"{int(match.group(1))} de {match.group(2)}"
    festival = re.fullmatch(r"([A-Za-zÀ-ÿ' -]+),\s*\d+\s*DR", text)
    if festival:
        return festival.group(1).strip()
    return text


def _get_path(document: dict[str, Any], dotted: str) -> Any:
    current: Any = document
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _available(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    normalized = value.casefold()
    if "indisponível" in normalized or "indisponivel" in normalized:
        return False
    return "disponível" in normalized or "disponivel" in normalized


def _magic_segments(context: dict[str, Any]) -> list[str]:
    config = ((context.get("rodape") or {}).get("itens_magicos") or {})
    if not isinstance(config, dict):
        raise FooterError("runtime.rodape.itens_magicos deve ser mapa")
    effects = context.get("efeitos_temporarios") or {}
    if not isinstance(effects, dict):
        effects = {}
    result: list[str] = []
    for item_id in sorted(config):
        item = config[item_id]
        if not isinstance(item, dict):
            continue
        name = item.get("nome")
        path = item.get("caminho_disponibilidade")
        effect_id = item.get("efeito_temporario")
        if not isinstance(name, str) or not name.strip():
            continue
        if isinstance(effect_id, str) and effect_id in effects:
            result.append(f"{name.strip()} ativo")
            continue
        if isinstance(path, str) and _available(_get_path(context, path)):
            result.append(f"{name.strip()} disponível")
    return result


def effective_runtime(repo: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    context = _load_yaml(repo / CONTEXT_PATH)
    scene = _load_yaml(repo / SCENE_PATH) if (repo / SCENE_PATH).is_file() else None
    records = transacoes.load_pending(repo)
    effective, effective_scene, _ = transacoes.overlay_runtime(context, scene, records)
    return effective, effective_scene


def build(repo: Path) -> str:
    context, scene = effective_runtime(repo)
    tempo = context.get("tempo") or {}
    resources = context.get("recursos") or {}
    pv = resources.get("pv") or {}
    ki = resources.get("ki") or {}
    location = (scene or {}).get("localizacao") or context.get("localizacao") or {}

    date = _date(tempo.get("data"))
    clock = _clock(tempo.get("hora_aproximada"))
    place = location.get("ponto_exato") or location.get("area")
    place_text = _text(place, "localização")
    if None in (pv.get("atuais"), pv.get("maximos"), ki.get("atuais"), ki.get("maximos")):
        raise FooterError("PV/Ki incompletos no runtime")
    pv_text = f"PV {pv.get('atuais')}/{pv.get('maximos')}"
    ki_text = f"Ki {ki.get('atuais')}/{ki.get('maximos')}"

    segments = [date, clock, place_text, pv_text, ki_text, *_magic_segments(context)]
    return PREFIX + " · ".join(str(item) for item in segments)


def build_safe(repo: Path) -> str:
    """Rodapé nunca invalida uma transação que já foi persistida."""
    try:
        return build(repo)
    except (FooterError, transacoes.TransactionError, OSError) as exc:
        return PREFIX + f"indisponível ({' '.join(str(exc).split())})"
