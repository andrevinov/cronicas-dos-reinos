#!/usr/bin/env python3
"""Porta pública/recovery da integração Task46.

O estado de oportunidades é o commit point da instalação: os quatro fragmentos
reservados podem ser reparados idempotentemente, mas a missão só passa a existir
depois que todos eles estão presentes e íntegros.
"""
from __future__ import annotations

import copy
from pathlib import Path

import yaml

import sidequests_integracao as _base

for _name in dir(_base):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_base, _name)


def install(repo: Path, journal: dict) -> dict:
    """Instala uma sidequest em uma única transação Task46 recuperável."""
    journal = _base._freeze_targets(repo, journal)
    changed: list[str] = []

    # Fragmentos reservados primeiro. Retry aceita somente bytes idênticos.
    for target in journal["targets"][:-1]:
        rel = Path(str(target["path"]))
        path = repo / rel
        content = str(target["content"])
        if path.is_file():
            if path.read_text(encoding="utf-8") != content:
                raise _base.EmergentSidequestIntegrationError(
                    f"alvo Task46 divergiu durante instalação: {rel.as_posix()}"
                )
            continue
        _base._atomic_text(path, content)
        changed.append(rel.as_posix())

    # O estado compacto é o commit point e entra por último.
    state_target = journal["targets"][-1]
    state_path = repo / Path(str(state_target["path"]))
    desired_state = str(state_target["content"])
    current_text = state_path.read_text(encoding="utf-8") if state_path.is_file() else ""
    if current_text != desired_state:
        try:
            current = _base.oportunidades.load_state(
                repo, _base.oportunidades.load_index(repo)
            )
        except _base.oportunidades.OpportunityError as exc:
            raise _base.EmergentSidequestIntegrationError(str(exc)) from exc
        mid = journal["plan"]["mission_id"]
        existing = current["missoes"].get(mid)
        if isinstance(existing, dict):
            if existing != journal["plan"]["mission"]:
                raise _base.EmergentSidequestIntegrationError(
                    "missão Task46 já existe com conteúdo divergente"
                )
        else:
            frozen = yaml.safe_load(desired_state)
            without = copy.deepcopy(frozen)
            without["missoes"].pop(mid, None)
            without["historico_recente"] = [
                item
                for item in without.get("historico_recente") or []
                if not (
                    isinstance(item, dict)
                    and item.get("id") == mid
                    and item.get("tipo") == "sidequest_emergente_materializada_task46"
                )
            ]
            if current != without:
                raise _base.EmergentSidequestIntegrationError(
                    "estado de oportunidades mudou durante instalação Task46; repita após reconciliar"
                )
            _base._atomic_text(state_path, desired_state)
            changed.append(_base.oportunidades.STATE.as_posix())

    (repo / _base.JOURNAL).unlink(missing_ok=True)
    return {
        "ok": True,
        "resultado": "sidequest_materializada",
        "mission_id": journal["plan"]["mission_id"],
        "quest_id": journal["plan"]["quest_id"],
        "transacao_instalacao": journal["id"],
        "arquivos_alterados": changed,
        "instalacoes_logicas": 1,
        "idempotente": True,
    }


# A porta pública deve usar a implementação corrigida.
globals()["install"] = install
