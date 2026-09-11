#!/usr/bin/env python3
"""Checkpoint até NV-18 + reconciliação climática determinística NV-21."""
from __future__ import annotations

from pathlib import Path

_LEGACY_SOURCE = Path(__file__).with_name("_checkpoint_nv17.py")
_saved_name = globals().get("__name__", "checkpoint")
globals()["__name__"] = "_checkpoint_nv17_exec"
exec(compile(_LEGACY_SOURCE.read_text(encoding="utf-8"), str(_LEGACY_SOURCE), "exec"), globals(), globals())
globals()["__name__"] = _saved_name

_BASE_SYNC_WORLD = sync_world
_BASE_CHECK = check
_BASE_STATUS = status
_BASE_MAIN = main

import clima_diario
import obrigacoes_temporais


def sync_world(repo: Path) -> dict[str, Any]:
    temporal = obrigacoes_temporais.sync_checkpoint(repo)
    result = _BASE_SYNC_WORLD(repo)
    # Clima é reconciliado depois do cursor normal do Mundo Vivo. A autoridade
    # diária é própria e idempotente: repetir o checkpoint não rerrola a data.
    climate = clima_diario.sync_dawn(repo)
    result["obrigacoes_temporais"] = temporal
    result["clima_diario"] = climate
    return result


def check(repo: Path) -> list[str]:
    errors = list(_BASE_CHECK(repo))
    temporal = obrigacoes_temporais.check(repo)
    errors.extend(
        f"obrigações temporais: {error}" for error in temporal.get("erros") or []
    )
    if clima_diario.configured(repo):
        climate = clima_diario.check(repo)
        errors.extend(f"clima diário: {error}" for error in climate.get("erros") or [])
    return list(dict.fromkeys(errors))


def status(repo: Path) -> dict[str, Any]:
    result = _BASE_STATUS(repo)
    result["obrigacoes_temporais"] = obrigacoes_temporais.status_view(repo)
    if clima_diario.configured(repo):
        result["clima_diario"] = clima_diario.status_view(repo)
    return result


if __name__ == "__main__":
    raise SystemExit(_BASE_MAIN())
