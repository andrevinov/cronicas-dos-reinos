#!/usr/bin/env python3
"""Contatos sociais até NV-18 + presença causal compartilhada da NV-19."""
from __future__ import annotations

from pathlib import Path

_LEGACY_SOURCE = Path(__file__).with_name("_contatos_sociais_nv18.py")
_saved_name = globals().get("__name__", "contatos_sociais")
globals()["__name__"] = "_contatos_sociais_nv18_exec"
exec(compile(_LEGACY_SOURCE.read_text(encoding="utf-8"), str(_LEGACY_SOURCE), "exec"), globals(), globals())
globals()["__name__"] = _saved_name

_BASE_PRESENT = _present


def _present(view, aid: str, local: str) -> bool:
    """Emissário e contato presencial obedecem à mesma presença NV-19."""
    helper = getattr(plans, "presence_at", None)
    if helper is None:
        return _BASE_PRESENT(view, aid, local)
    return bool(helper(view, aid, local))
