#!/usr/bin/env python3
"""Compatibilidade Task31 e roteamento opaco Task32/33.

O gate procedural continua aposentado. O índice quente só identifica o conjunto
curado de quest-givers; quando o NPC explícito pertence a esse conjunto, a Task 33
abre um único roteador reservado daquele NPC. Nenhum gate, detalhe, estado de
oportunidades, pressão, tempo ou baralho é aberto aqui.

Fixtures antigas sem marcador Task31 preservam o motor legado.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import yaml

import interacoes_mundo as integration
import oportunidades
import sidequests_canonicas

RETIREMENT = "gate_procedural_retirado_task31"
NEW_SOURCE = "canonica_explicita"
_BASE_ENCOUNTER_EVENT = integration.encounter_event


class SidequestGateV2Error(ValueError):
    """Erro de contrato do adaptador de aposentadoria."""


def _retirement_contract(index: dict[str, Any]) -> None:
    if index.get("estatuto_operacional") != RETIREMENT:
        raise SidequestGateV2Error(
            "indice nao declara aposentadoria operacional da Task 31"
        )
    if index.get("nova_origem_sidequests") != NEW_SOURCE:
        raise SidequestGateV2Error(
            "nova origem de sidequests deve ser canonica_explicita"
        )
    gate = index.get("gate")
    if (
        not isinstance(gate, dict)
        or gate.get("estatuto") != "legado_congelado_nao_operacional"
    ):
        raise SidequestGateV2Error(
            "baralho legado precisa permanecer congelado e nao operacional"
        )
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
            raise SidequestGateV2Error(
                f"regra de aposentadoria divergente: {key}"
            )
    profiles = index.get("perfis")
    if not isinstance(profiles, dict):
        raise SidequestGateV2Error(
            "perfis procedurais ausentes para auditoria"
        )
    active = [
        npc_id
        for npc_id, meta in profiles.items()
        if isinstance(meta, dict) and meta.get("estado") == "ativo"
    ]
    if active:
        raise SidequestGateV2Error(
            "perfil procedural ainda ativo apos Task 31: "
            + ", ".join(sorted(active))
        )
    # Valida apenas o contrato compacto quente; fragmentos entram sob demanda.
    sidequests_canonicas._router(index)


def encounter_event(
    repo: Path,
    npc_id: str,
    *,
    now=None,
    encounter_id: str | None = None,
) -> dict[str, Any]:
    """Produção: resolve + roteia opacos. Fixture legado: motor histórico."""
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
        refs, route_sources = sidequests_canonicas.route_for_npc_with_sources(
            repo,
            index,
            str(resolution["npc_id"]),
        )
    except (
        oportunidades.OpportunityError,
        SidequestGateV2Error,
        sidequests_canonicas.CanonicalSidequestError,
    ) as exc:
        raise integration.IntegrationError(str(exc)) from exc

    result: dict[str, Any] = {
        "ok": True,
        "resultado": "interacao_normal",
        "motivo": "gate_procedural_retirado",
        "npc_id": resolution["npc_id"],
        "sidequest": {
            "gate_procedural": "retirado",
            "nova_origem": NEW_SOURCE,
            "engine": sidequests_canonicas.ENGINE_ID,
            "regra": (
                "encontro nao gera sidequest procedural; somente fonte canonica "
                "explicita pode ficar elegivel"
            ),
        },
        "fontes_lidas": list(
            dict.fromkeys(
                [*(resolution.get("fontes_lidas") or []), *route_sources]
            )
        ),
    }
    # Campo interno consumido pela camada de cena. Contém apenas id/path/prioridade
    # opacos e nunca gate ou detalhe da missão.
    if refs:
        result["_sidequest_canonica_refs"] = refs
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
        canonical = sidequests_canonicas.check(repo)
    except (
        oportunidades.OpportunityError,
        SidequestGateV2Error,
        sidequests_canonicas.CanonicalSidequestError,
    ) as exc:
        return {"ok": False, "erros": [str(exc)]}

    errors: list[str] = []
    if state.get("pendencias_avaliacao"):
        errors.append("pendencia procedural anterior ainda esta ativa")
    legacy = state.get("legado_procedural")
    if (
        not isinstance(legacy, dict)
        or legacy.get("estatuto") != "somente_auditoria_nao_operacional"
    ):
        errors.append(
            "estado nao preserva auditoria do gate procedural aposentado"
        )
    errors.extend(
        f"sidequest_canonica: {item}"
        for item in canonical.get("erros") or []
    )
    return {
        "ok": not errors,
        "estatuto": RETIREMENT,
        "nova_origem_sidequests": NEW_SOURCE,
        "perfis_procedurais_ativos": 0,
        "pendencias_ativas": len(state.get("pendencias_avaliacao") or {}),
        "sidequests_canonicas": {
            "engine": sidequests_canonicas.ENGINE_ID,
            "quest_givers": canonical.get("quest_givers", 0),
            "quests_roteadas": canonical.get("quests_roteadas", 0),
        },
        "baralho_legado": {
            "ciclo": state["gate"]["ciclo"],
            "sorteios": state["gate"]["sorteios"],
            "restantes": len(state["gate"]["restantes"]),
        },
        "erros": errors,
        "fontes_lidas": [
            oportunidades.INDEX.as_posix(),
            oportunidades.STATE.as_posix(),
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    encounter_parser = sub.add_parser(
        "encontro",
        help="confirma aposentadoria e roteia somente refs canônicas opacas",
    )
    encounter_parser.add_argument("npc")
    encounter_parser.add_argument("--encontro-id")
    sub.add_parser("check", help="valida aposentadoria e engine canônico")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "check":
            result = check(repo)
            code = 0 if result["ok"] else 1
        else:
            result = encounter_event(
                repo,
                args.npc,
                encounter_id=args.encontro_id,
            )
            code = 0
        print(
            yaml.safe_dump(result, allow_unicode=True, sort_keys=False),
            end="",
        )
        return code
    except (
        SidequestGateV2Error,
        integration.IntegrationError,
        sidequests_canonicas.CanonicalSidequestError,
    ) as exc:
        print(f"ERRO: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
