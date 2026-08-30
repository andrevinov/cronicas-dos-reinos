#!/usr/bin/env python3
"""Compatibilidade Task31/32/33 depois da integração emergente Task46.

O gate procedural continua aposentado. Desde a Task46, encontros ao vivo não
roteiam mais o catálogo Task33: o narrador só acorda Task40 por âncora causal
explícita na mesma porta ``cronica preparar``. Task32/33 permanecem frios para
compatibilidade, auditoria e quests já narradas.

Fixtures antigas com o estatuto Task31 ainda preservam o roteamento opaco antigo;
assim a migração não apaga a capacidade de auditar/reproduzir o legado.
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
INTEGRATED = "sidequests_emergentes_integradas_task46"
LEGACY_SOURCE = "canonica_explicita"
NEW_SOURCE = "emergente_causal_task40"
_BASE_ENCOUNTER_EVENT = integration.encounter_event


class SidequestGateV2Error(ValueError):
    """Erro de contrato do adaptador de aposentadoria."""


def _common_contract(index: dict[str, Any]) -> None:
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
        "perfis_procedurais_sao_legado": True,
    }
    for key, expected in required.items():
        if rules.get(key) != expected:
            raise SidequestGateV2Error(
                f"regra de aposentadoria divergente: {key}"
            )
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
            "perfil procedural ainda ativo apos aposentadoria: "
            + ", ".join(sorted(active))
        )


def _retirement_contract(index: dict[str, Any]) -> str:
    """Valida modo antigo ou integrado sem acordar Task33 no modo Task46."""
    _common_contract(index)
    status = index.get("estatuto_operacional")
    rules = index["regras"]
    if status == RETIREMENT:
        if index.get("nova_origem_sidequests") != LEGACY_SOURCE:
            raise SidequestGateV2Error(
                "Task31 exige nova origem canonica_explicita"
            )
        if rules.get("fonte_nova_sidequest") != LEGACY_SOURCE:
            raise SidequestGateV2Error("fonte Task31 divergente")
        # Apenas o modo histórico abre o roteador Task32/33.
        sidequests_canonicas._router(index)
        return RETIREMENT
    if status == INTEGRATED:
        if index.get("nova_origem_sidequests") != NEW_SOURCE:
            raise SidequestGateV2Error(
                "Task46 exige origem emergente_causal_task40"
            )
        if rules.get("fonte_nova_sidequest") != NEW_SOURCE:
            raise SidequestGateV2Error("fonte Task46 divergente")
        if rules.get("task32_task33_origem_operacional") is not False:
            raise SidequestGateV2Error("Task32/33 ainda aparecem como origem operacional")
        if rules.get("task40_exige_ancora_causal_explicita") is not True:
            raise SidequestGateV2Error("Task40 precisa exigir âncora causal explícita")
        return INTEGRATED
    raise SidequestGateV2Error(
        f"estatuto de sidequest desconhecido: {status!r}"
    )


def encounter_event(
    repo: Path,
    npc_id: str,
    *,
    now=None,
    encounter_id: str | None = None,
) -> dict[str, Any]:
    """Produção Task46: resolve NPC sem abrir Task33; legado Task31 preservado."""
    try:
        index = oportunidades.load_index(repo)
    except oportunidades.OpportunityError as exc:
        raise integration.IntegrationError(str(exc)) from exc

    status = index.get("estatuto_operacional")
    if status not in {RETIREMENT, INTEGRATED}:
        return _BASE_ENCOUNTER_EVENT(
            repo,
            npc_id,
            now=now,
            encounter_id=encounter_id,
        )

    try:
        mode = _retirement_contract(index)
        resolution = integration.resolve_encounter_npc(repo, npc_id, index)
    except (
        oportunidades.OpportunityError,
        SidequestGateV2Error,
        sidequests_canonicas.CanonicalSidequestError,
    ) as exc:
        raise integration.IntegrationError(str(exc)) from exc

    if mode == INTEGRATED:
        result: dict[str, Any] = {
            "ok": True,
            "resultado": "interacao_normal",
            "motivo": "sidequests_emergentes_task46",
            "npc_id": resolution["npc_id"],
            "sidequest": {
                "gate_procedural": "retirado",
                "nova_origem": NEW_SOURCE,
                "task32_task33": "legado_frio",
                "regra": (
                    "encontro por si só não gera nem roteia quest; somente uma âncora "
                    "causal concreta sinalizada em cronica preparar acorda Task40"
                ),
            },
            "fontes_lidas": list(resolution.get("fontes_lidas") or []),
        }
        if encounter_id is not None:
            result["encontro_id"] = encounter_id
        if resolution.get("recebido") != resolution.get("npc_id"):
            result["npc_recebido"] = resolution.get("recebido")
            result["resolucao_npc"] = resolution.get("resolucao")
        return result

    # Compatibilidade histórica Task31: refs opacas ainda podem ser auditadas.
    try:
        refs, route_sources = sidequests_canonicas.route_for_npc_with_sources(
            repo,
            index,
            str(resolution["npc_id"]),
        )
    except sidequests_canonicas.CanonicalSidequestError as exc:
        raise integration.IntegrationError(str(exc)) from exc
    result = {
        "ok": True,
        "resultado": "interacao_normal",
        "motivo": "gate_procedural_retirado",
        "npc_id": resolution["npc_id"],
        "sidequest": {
            "gate_procedural": "retirado",
            "nova_origem": LEGACY_SOURCE,
            "engine": sidequests_canonicas.ENGINE_ID,
            "regra": (
                "encontro nao gera sidequest procedural; somente fonte canonica "
                "explicita pode ficar elegivel"
            ),
        },
        "fontes_lidas": list(
            dict.fromkeys([*(resolution.get("fontes_lidas") or []), *route_sources])
        ),
    }
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
        mode = _retirement_contract(index)
        state = oportunidades.load_state(repo, index)
        # Task32/33 continuam auditáveis, mas esta leitura só ocorre no check frio.
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
        errors.append("estado nao preserva auditoria do gate procedural aposentado")
    errors.extend(
        f"sidequest_canonica: {item}"
        for item in canonical.get("erros") or []
    )
    return {
        "ok": not errors,
        "estatuto": mode,
        "nova_origem_sidequests": (
            NEW_SOURCE if mode == INTEGRATED else LEGACY_SOURCE
        ),
        "task32_task33_hot_path": False if mode == INTEGRATED else True,
        "perfis_procedurais_ativos": 0,
        "pendencias_ativas": len(state.get("pendencias_avaliacao") or {}),
        "sidequests_canonicas": {
            "engine": sidequests_canonicas.ENGINE_ID,
            "estatuto": "legado_frio" if mode == INTEGRATED else "compatibilidade_task31",
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
        help="confirma aposentadoria; Task46 não roteia catálogo Task33 ao vivo",
    )
    encounter_parser.add_argument("npc")
    encounter_parser.add_argument("--encontro-id")
    sub.add_parser("check", help="valida aposentadoria e legado frio")
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
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
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
