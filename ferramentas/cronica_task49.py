#!/usr/bin/env python3
"""Task 49 — adapter operacional da cápsula autoral sobre ``cronica``.

Não cria outro motor de turno. Importa a porta já endurecida pelas Tasks47/48,
decora somente a preparação rara e compila a cápsula para o contrato Task46
antes de delegar ao mesmo ``cronica concluir``.
"""
from __future__ import annotations

import copy
from typing import Any

import cronica as _base
import sidequest_authoring_capsule as capsule

_ORIGINAL_PREPARE = _base.prepare
_ORIGINAL_CONCLUDE = _base.conclude
_ORIGINAL_TRANSACTION_CONTRACT = _base._hot._transaction_contract


def _transaction_contract() -> dict[str, Any]:
    contract = _ORIGINAL_TRANSACTION_CONTRACT()
    contract["sidequest_emergente_task46"] = (
        "Em ticket com oportunidade, use sidequest_emergente={oferta,capsula_autoral}; "
        "o contrato autoral completo vem na própria saída de preparar. Sem oferta literal, omita o bloco."
    )
    return contract


def _decorate_authoring_contract(result: dict[str, Any]) -> dict[str, Any]:
    marker = result.get("sidequest_emergente_task46")
    package = result.get("sidequest_emergente")
    if (
        not isinstance(marker, dict)
        or marker.get("integrada_ao_ticket") is not True
        or not isinstance(package, dict)
    ):
        return result
    decorated = copy.deepcopy(result)
    try:
        decorated["contrato_autoria_sidequest"] = capsule.authoring_contract(package)
    except capsule.SidequestAuthoringCapsuleError as exc:
        raise _base.CronicaError(f"Task49: {exc}") from exc
    marker_out = copy.deepcopy(decorated["sidequest_emergente_task46"])
    marker_out["formato_autoral"] = "capsula_task49_v1"
    marker_out["transporte_autoral"] = "stdin_json_unico"
    decorated["sidequest_emergente_task46"] = marker_out
    size = _base._sidequests46._base._yaml_size(decorated)
    if size > _base._sidequests46.MAX_COMBINED_PREP_BYTES:
        raise _base.CronicaError(
            f"Task49: preparação rara excede {_base._sidequests46.MAX_COMBINED_PREP_BYTES} bytes: {size}"
        )
    return decorated


def prepare(*args, **kwargs):
    return _decorate_authoring_contract(_ORIGINAL_PREPARE(*args, **kwargs))


def _compile_transaction(transaction: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    raw = transaction.get(_base._sidequests46.TRANSACTION_KEY)
    if raw is None:
        return transaction, None
    try:
        block, mode = capsule.compile_block(raw)
    except capsule.SidequestAuthoringCapsuleError as exc:
        raise _base.CronicaError(f"Task49: {exc}") from exc
    compiled = copy.deepcopy(transaction)
    compiled[_base._sidequests46.TRANSACTION_KEY] = block
    return compiled, mode


def conclude(repo, token: str, transaction: dict[str, Any]):
    compiled, mode = _compile_transaction(transaction)
    result = _ORIGINAL_CONCLUDE(repo, token, compiled)
    if mode == "capsula_task49_v1" and isinstance(result.get("sidequest_emergente"), dict):
        result = copy.deepcopy(result)
        result["sidequest_emergente"]["formato_autoral"] = mode
    return result


# ``cronica._run_turn`` resolve estes nomes no módulo em tempo de execução.
# Assim o parser/lifecycle/recovery continuam sendo exatamente os mesmos.
_base.prepare = prepare
_base.conclude = conclude
_base._hot._transaction_contract = _transaction_contract


def main(argv: list[str] | None = None) -> int:
    return _base.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
