"""Entrega causal transacional ao jogador (NV-13)."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import re
from typing import Any

import yaml

import mundo

SCHEMA = 1
PENDING_TYPE = "entrega_causal"
NON_COMMUNICABLE_TAG = "entrega-causal:nao-comunicavel"
CLOCK_PREFIX = "entrega_"
EXEMPT_PENDING_TYPES = {
    "resolver_reacao_sidequest",
    "resolver_grupo_operacoes",
    "resolver_operacao_adversarial",
    "avaliar_plano_personagem",
    "resolver_sidequest",
}
PENDING_ID_RE = re.compile(r"^mundo-([0-9a-f]{16})$")
PLAN_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class DeliveryError(ValueError):
    pass


def _text(value: Any, label: str, maximum: int = 1200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise DeliveryError(f"{label} deve ser texto não vazio de até {maximum} caracteres")
    return value.strip()


def clock_id(pending_id: str) -> str:
    match = PENDING_ID_RE.fullmatch(str(pending_id))
    if not match:
        raise DeliveryError(f"id de pendência inválido: {pending_id!r}")
    return CLOCK_PREFIX + match.group(1)


def target_for(pending_id: str) -> str:
    return "relogio:" + clock_id(pending_id)


def requires_contract(pending: dict[str, Any]) -> bool:
    return str(pending.get("tipo") or "") not in EXEMPT_PENDING_TYPES
