"""Composição final do contrato NV-15 sobre o núcleo de permanência espacial.

Mantém o digest do ticket independente do estado de conclusão, torna retry
idempotente e alinha presença incidental ao mesmo período operacional da NV-14.
Nenhuma dessas adaptações cria I/O adicional fora de ``--permanencia-local``.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import _permanencia_espacial_core as _stay

_BASE_PREPARE = _stay.prepare
_BASE_PREPARE_CONCLUSION = _stay.prepare_conclusion


def _record_digest(record: dict[str, Any]) -> str:
    """Congela a avaliação, não o marcador mutável de resolução."""
    value = copy.deepcopy(record)
    value.pop("digest", None)
    value.pop("estado", None)
    value.pop("decisao", None)
    return _stay._digest(value)


def prepare(
    repo: Path,
    *,
    scene_id: str,
    place: str | None = None,
    now=None,
) -> dict[str, Any]:
    """Usa a mesma janela nomeada da NV-14 também no produtor de presença.

    ``presenca_incidental`` já é estável por dia/período/local/NPC, mas sua
    função histórica de período tinha horários próprios. Durante uma permanência
    fazemos a projeção usar o período operacional já calculado pela NV-14; fora
    desta chamada o módulo permanece intocado.
    """
    repo = Path(repo).resolve()
    current, _ = _stay._instant(repo, now)
    local_id, _ = _stay.resolve_location(repo, place)
    window = _stay._window(repo, local_id, current)
    original_period = _stay.presenca_incidental.period_from_instant
    _stay.presenca_incidental.period_from_instant = lambda _instant: window["periodo"]
    try:
        return _BASE_PREPARE(repo, scene_id=scene_id, place=place, now=current)
    finally:
        _stay.presenca_incidental.period_from_instant = original_period


def prepare_conclusion(
    repo: Path,
    meta: Any,
    transaction: dict[str, Any],
) -> dict[str, Any] | None:
    """Aceita retry apenas quando ele repete literalmente a decisão instalada."""
    public = _stay.revalidate(repo, meta)
    if public["estado"] not in _stay.RESULTS:
        return _BASE_PREPARE_CONCLUSION(repo, meta, transaction)

    block = transaction.get("permanencia_espacial")
    if not isinstance(block, dict):
        raise _stay.SpatialPermanenceError(
            "retry de pressão espacial concluída exige repetir o mesmo bloco permanencia_espacial"
        )
    state = _stay.load_state(repo)
    record = state["avaliacoes"].get(public["avaliacao_id"])
    if not isinstance(record, dict):
        raise _stay.SpatialPermanenceError("retry não encontra avaliação espacial instalada")
    existing = copy.deepcopy(record.get("decisao") or {})
    existing.pop("em", None)
    if block != existing:
        raise _stay.SpatialPermanenceError(
            "retry de permanência diverge da decisão espacial já instalada"
        )
    return existing


# Instala a política no namespace onde as funções do núcleo resolvem seus nomes.
_stay._record_digest = _record_digest
_stay.prepare = prepare
_stay.prepare_conclusion = prepare_conclusion

for _name in dir(_stay):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_stay, _name)
