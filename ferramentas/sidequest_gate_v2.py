#!/usr/bin/env python3
"""Compatibilidade da Task 31: o Side Quest Gate procedural esta aposentado.

O nome do modulo permanece porque ``cena_mundo.py`` ja o usa como adaptador da
porta de encontro. No repo real, a implementacao nova resolve apenas a identidade
do NPC e retorna interacao normal: nao abre estado de oportunidades, perfil
procedural, pressao de aventura, tempo nem baralho.

Fixtures/repositórios antigos que ainda nao declaram a aposentadoria usam o motor
legado capturado na importacao. Isso preserva testes e migracoes historicas sem
reativar o gate na campanha atual.

O lifecycle de missoes continua em ``oportunidades.py`` para fontes canonicas
explicitas. O catalogo/engine canonico e responsabilidade da Task 32.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

import interacoes_mundo as integration
import oportunidades

RETIREMENT = "gate_procedural_retirado_task31"
NEW_SOURCE = "canonica_explicita"
_BASE_ENCOUNTER_EVENT = integration.encounter_event


class SidequestGateV2Error(ValueError):
    """Erro de contrato do adaptador de aposentadoria."""


def _retirement_contract(index: dict[str, Any]) -> None:
    if index.get("estatuto_operacional") != RETIREMENT:
        raise SidequestGateV2Error("indice nao declara aposentadoria operacional da Task 31")
    if index.get("nova_origem_sidequests") != NEW_SOURCE:
        raise SidequestGateV2Error("nova origem de sidequests deve ser canonica_explicita")
    gate = index.get("gate")
    if not isinstance(gate, dict) or gate.get("estatuto") != "legado_congelado_nao_operacional":
        raise SidequestGateV2Error("baralho legado precisa permanecer congelado e nao operacional")
    rules = index.get("regras")
    if not isinstance(rules, dict):
        raise SidequestGateV2Error("regras de oportunidades ausentes")
    required = {
        "gate_procedural_operacional": False,
        "encontro_nao_gera_nova_sidequest": True,
        "fonte_nova_sidequest": NEW_SOURCE,
        "perfis_procedurais_sao_legado": True,
    }
    for key, expected in required.items():
        if rules.get(key) != expected:
            raise SidequestGateV2Error(f"regra de aposentadoria divergente: {key}")
    profiles = index.get("perfis")
    if not isinstance(profiles, dict):
        raise SidequestGateV2Error("perfis procedurais ausentes para auditoria")
    active = [
        npc_id
        for npc_id, meta in profiles.items()
        if isinstance(meta, dict) and meta.get("estado") == "ativo"
    ]
    if active:
        raise SidequestGateV2Error(
            "perfil procedural ainda ativo apos Task 31: " + ", ".join(sorted(active))
        )


def encounter_event(
    repo: Path,
    npc_id: str,
    *,
    now=None,
    encounter_id: str | None = None,
) -> dict[str, Any]:
    """Repo Task31: resolve sem gate. Fixture legado: preserva comportamento antigo."""
    try:
        index = oportunidades.load_index(repo)
    except oportunidades.OpportunityError as exc:
        raise integration.IntegrationError(str(exc)) from exc

    if index.get("estatuto_operacional") != RETIREMENT:
        return _BASE_ENCOUNTER_EVENT(
            repo,
            npc_id,
            now=now,
            encounter_id=encounter_id,
        )

    try:
        _retirement_contract(index)
        resolution = integration.resolve_encounter_npc(repo, npc_id, index)
    except (oportunidades.OpportunityError, SidequestGateV2Error) as exc:
        raise integration.IntegrationError(str(exc)) from exc

    result: dict[str, Any] = {
        "ok": True,
        "resultado": "interacao_normal",
        "motivo": "gate_procedural_retirado",
        "npc_id": resolution["npc_id"],
        "sidequest": {
            "gate_procedural": "retirado",
            "nova_origem": NEW_SOURCE,
            "regra": "encontro com NPC nao gera sidequest; aguarde fonte canonica explicita",
        },
        "fontes_lidas": list(resolution.get("fontes_lidas") or []),
    }
    if encounter_id is not None:
        result["encontro_id"] = encounter_id
    if resolution.get("recebido") != resolution.get("npc_id"):
        result["npc_recebido"] = resolution.get("recebido")
        result["resolucao_npc"] = resolution.get("resolucao")
    return result


def check(repo: Path) -> dict[str, Any]:
    try:
        index = oportunidades.load_index(repo)
        _retirement_contract(index)
        state = oportunidades.load_state(repo, index)
    except (oportunidades.OpportunityError, SidequestGateV2Error) as exc:
        return {"ok": False, "erros": [str(exc)]}

    errors: list[str] = []
    if state.get("pendencias_avaliacao"):
        errors.append("pendencia procedural anterior ainda esta ativa")
    legacy = state.get("legado_procedural")
    if not isinstance(legacy, dict) or legacy.get("estatuto") != "somente_auditoria_nao_operacional":
        errors.append("estado nao preserva auditoria do gate procedural aposentado")
    return {
        "ok": not errors,
        "estatuto": RETIREMENT,
        "nova_origem_sidequests": NEW_SOURCE,
        "perfis_procedurais_ativos": 0,
        "pendencias_ativas": len(state.get("pendencias_avaliacao") or {}),
        "baralho_legado": {
            "ciclo": state["gate"]["ciclo"],
            "sorteios": state["gate"]["sorteios"],
            "restantes": len(state["gate"]["restantes"]),
        },
        "erros": errors,
        "fontes_lidas": [oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix()],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)
    encounter_parser = sub.add_parser("encontro", help="confirma que encontro nao gera sidequest procedural")
    encounter_parser.add_argument("npc")
    encounter_parser.add_argument("--encontro-id")
    sub.add_parser("check", help="valida aposentadoria do gate procedural")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "check":
            result = check(repo)
            code = 0 if result["ok"] else 1
        else:
            result = encounter_event(repo, args.npc, encounter_id=args.encontro_id)
            code = 0
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return code
    except (SidequestGateV2Error, integration.IntegrationError) as exc:
        print(f"ERRO: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
