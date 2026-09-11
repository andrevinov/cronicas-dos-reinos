#!/usr/bin/env python3
"""Trânsito urbano até NV-20 + efeitos climáticos read-only da NV-21."""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

_IMPL_SOURCE = Path(__file__).with_name("_microeventos_transito_nv20.py")
_saved_name = globals().get("__name__", "microeventos_transito")
globals()["__name__"] = "_microeventos_transito_nv20_exec"
exec(compile(_IMPL_SOURCE.read_text(encoding="utf-8"), str(_IMPL_SOURCE), "exec"), globals(), globals())
globals()["__name__"] = _saved_name

_BASE_PLAN_NV20 = plan
_BASE_VALIDATE_REPO_NV20 = validate_repo
_BASE_MAIN_NV20 = main

import clima_diario as _climate


def _weather(repo: Path, scope: str):
    if not _climate.configured(Path(repo)):
        return None
    try:
        return _climate.for_travel(Path(repo), region=scope)
    except _climate.ClimateError as exc:
        raise TransitMicroeventError(str(exc)) from exc


def _combined_fingerprint(base: str, weather) -> str:
    if weather is None:
        return base
    active = weather.get("ativo")
    climate = active.get("fingerprint") if isinstance(active, dict) else "sem_clima_ativo"
    return hashlib.sha256(f"{base}|nv21|{climate}".encode("utf-8")).hexdigest()


def _decorate(base: dict, weather) -> dict:
    if weather is None:
        return base
    result = copy.deepcopy(base)
    result["fingerprint"] = _combined_fingerprint(base["fingerprint"], weather)
    public = result["publico"]
    public["clima_diario"] = copy.deepcopy(weather.get("ativo"))
    public["fontes_lidas"] = list(dict.fromkeys([
        *(public.get("fontes_lidas") or []), *(weather.get("fontes_lidas") or [])
    ]))
    return result


def plan(repo: Path, *, scene_id: str, scope: str = TRANSIT_SCOPE):
    base = _BASE_PLAN_NV20(Path(repo), scene_id=scene_id, scope=scope)
    return _decorate(base, _weather(Path(repo), scope))


def revalidate(repo: Path, *, scene_id: str, expected_fingerprint: str, scope: str = TRANSIT_SCOPE):
    planned = plan(Path(repo), scene_id=scene_id, scope=scope)
    if planned["fingerprint"] != expected_fingerprint:
        raise TransitMicroeventError(
            "preparação do trânsito urbano ficou obsoleta; clima/pressão/deck mudaram; execute `cronica preparar` novamente"
        )
    return planned


def confirm(repo: Path, *, scene_id: str, expected_fingerprint: str, scope: str = TRANSIT_SCOPE):
    planned = revalidate(
        Path(repo), scene_id=scene_id, expected_fingerprint=expected_fingerprint, scope=scope
    )
    # O consumo continua pertencendo ao mesmo estado/writer do baralho anterior.
    # Não chamamos o ``confirm`` congelado porque sua resolução global de
    # ``revalidate`` apontaria para o fingerprint composto NV-21.
    base = _BASE_PLAN_NV20(Path(repo), scene_id=scene_id, scope=scope)
    if base["confirmado"]:
        return {**planned["publico"], "mutacoes_aplicadas": False}
    try:
        changed = micro.commit_plan(
            Path(repo),
            {"alterou": base["alterou"], "estado_planejado": base["estado_planejado"]},
        )
    except micro.LocalMicroeventError as exc:
        raise TransitMicroeventError(str(exc)) from exc
    return {**planned["publico"], "mutacoes_aplicadas": bool(changed)}


def validate_repo(repo: Path):
    result = _BASE_VALIDATE_REPO_NV20(Path(repo))
    errors = list(result.get("erros") or [])
    if _climate.configured(Path(repo)):
        climate = _climate.check(Path(repo))
        errors.extend(f"clima diário: {item}" for item in climate.get("erros") or [])
        result["fontes_lidas"] = list(dict.fromkeys([
            *(result.get("fontes_lidas") or []), _climate.STATE.as_posix(), _climate.CONFIG.as_posix()
        ]))
    result["erros"] = list(dict.fromkeys(errors))
    result["ok"] = not result["erros"]
    return result


if __name__ == "__main__":
    raise SystemExit(_BASE_MAIN_NV20())
