#!/usr/bin/env python3
"""Permanência espacial até NV-19 + clima NV-21 + avisos públicos NV-22."""
from __future__ import annotations

from pathlib import Path

import yaml
import permanencia_espacial_idempotencia as _impl
import planos_personagens as _plans
import mundo as _world
import clima_diario as _climate
import politica_civica as _civic

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
    if not isinstance(local_id, str) or not local_id:
        return planned

    if _has_entry_plans(Path(repo)):
        try:
            entry = _plans.project_local_entry(Path(repo), local_id)
        except _plans.PlanError as exc:
            raise SpatialPermanenceError(f"entrada causal: {exc}") from exc
        public["entrada_causal"] = entry
        if entry is not None:
            public["fontes_lidas"] = list(dict.fromkeys([
                *(public.get("fontes_lidas") or []), *(entry.get("fontes_lidas") or [])
            ]))

    # NV-21 não sorteia na cena. Esta camada lê apenas o estado ativo congelado
    # pela alvorada e expõe sensorial + disponibilidade de espaços antes da prosa.
    if _climate.configured(Path(repo)):
        try:
            weather = _climate.for_scene(Path(repo), local_id, now=now)
        except _climate.ClimateError as exc:
            raise SpatialPermanenceError(f"clima diário: {exc}") from exc
        public["clima"] = weather.get("ativo")
        public["fontes_lidas"] = list(dict.fromkeys([
            *(public.get("fontes_lidas") or []), *(weather.get("fontes_lidas") or [])
        ]))

    # NV-22: a permanência nunca consulta agenda institucional. Ela projeta
    # somente editais/quadro já publicados e ainda não entregues a Ren.
    if _civic.configured(Path(repo)):
        try:
            notices = _civic.project_for_permanence(
                Path(repo),
                locality=local_id,
                date=public.get("data"),
                period=public.get("periodo"),
                evaluation_id=public.get("avaliacao_id"),
            )
        except _civic.CivicPolicyError as exc:
            raise SpatialPermanenceError(f"política cívica: {exc}") from exc
        if notices.get("avisos"):
            public["avisos_publicos"] = notices
        public["fontes_lidas"] = list(dict.fromkeys([
            *(public.get("fontes_lidas") or []), *(notices.get("fontes_lidas") or [])
        ]))
    return planned


# O namespace interno é usado diretamente por cronica_permanencia.
_impl.prepare = prepare
