#!/usr/bin/env python3
"""API pública da permanência espacial até NV-15 + projeção causal NV-19.

A NV-19 acrescenta somente uma leitura dirigida dos planos ``entrada_local`` ao
resultado já preparado pela permanência. Ela não sorteia personagem, não varre o
cadastro e não altera o recibo espacial: o plano continua sendo resolvido pela
agenda/journal do Mundo Vivo.
"""
from __future__ import annotations

from pathlib import Path

import yaml
import permanencia_espacial_idempotencia as _impl
import planos_personagens as _plans
import mundo as _world

for _name in dir(_impl):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_impl, _name)

_BASE_PREPARE_NV15 = _impl.prepare


def _has_entry_plans(repo: Path) -> bool:
    path = Path(repo) / _world.WORLD_STATE_PATH
    if not path.is_file():
        return False
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return False
    control = raw.get(_plans.KEY) if isinstance(raw, dict) else None
    return isinstance(control, dict) and any(_plans.is_entry_plan(plan) for plan in control.values())


def prepare(repo: Path, *, scene_id: str, place: str | None = None, now=None):
    planned = _BASE_PREPARE_NV15(repo, scene_id=scene_id, place=place, now=now)
    public = planned.get("publico") or {}
    local_id = public.get("local_id")
    if not isinstance(local_id, str) or not local_id or not _has_entry_plans(Path(repo)):
        return planned
    try:
        entry = _plans.project_local_entry(Path(repo), local_id)
    except _plans.PlanError as exc:
        raise SpatialPermanenceError(f"entrada causal: {exc}") from exc
    public["entrada_causal"] = entry
    if entry is not None:
        public["fontes_lidas"] = list(dict.fromkeys([
            *(public.get("fontes_lidas") or []), *(entry.get("fontes_lidas") or [])
        ]))
    return planned


# O namespace interno é usado diretamente por cronica_permanencia.
_impl.prepare = prepare
