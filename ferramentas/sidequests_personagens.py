#!/usr/bin/env python3
"""NV-11 — causas de personagens alimentam o lifecycle atual de sidequests.

O contrato vive no passo NV-08 que já representa a intenção do personagem. Esta
camada faz uma leitura dirigida desse plano e monta um pacote Task40; não cria
missão, oferta, aceite, consequência, scheduler ou estado paralelo.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml

import mundo
import oportunidade_sidequest as opportunity
import oportunidades

SCHEMA = 1
STEP_KEY = "oportunidade_sidequest"
SOURCE_TYPES = {"necessidade", "conflito", "impedimento"}
SOURCE_PREFIXES = {
    "necessidade": "npc.necessidades.",
    "conflito": "npc.conflitos.",
    "impedimento": "npc.impedimentos.",
}
MAX_TEXT = 520
PLAN_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class CharacterSidequestError(ValueError):
    """A causa não possui base canônica suficiente para virar oportunidade."""


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise CharacterSidequestError(f"{label} deve ser mapa")
    return value


def _text(value: Any, label: str, *, minimum: int = 20) -> str:
    if not isinstance(value, str):
        raise CharacterSidequestError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if not minimum <= len(result) <= MAX_TEXT:
        raise CharacterSidequestError(
            f"{label} deve ter entre {minimum} e {MAX_TEXT} caracteres"
        )
    return result


def _digest(value: Any) -> str:
    rendered = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def validate_contract(value: Any) -> dict[str, Any]:
    """Valida a declaração compacta; referências são conferidas pelo View NV-08."""
    contract = copy.deepcopy(_map(value, STEP_KEY))
    expected = {
        "versao",
        "tipo",
        "causa",
        "situacao",
        "motivo_envolver_ren",
        "consequencias",
    }
    if set(contract) != expected or contract.get("versao") != SCHEMA:
        raise CharacterSidequestError(
            f"{STEP_KEY} v{SCHEMA} possui campos divergentes"
        )
    source_type = contract.get("tipo")
    if source_type not in SOURCE_TYPES:
        raise CharacterSidequestError(
            "tipo da causa deve ser necessidade, conflito ou impedimento"
        )
    try:
        import planos_personagens as plans

        cause = copy.deepcopy(plans._ref(contract.get("causa")))
    except (ValueError, TypeError) as exc:
        raise CharacterSidequestError(str(exc)) from exc
    prefix = SOURCE_PREFIXES[source_type]
    if not cause["caminho"].startswith(prefix):
        raise CharacterSidequestError(
            f"causa {source_type} deve apontar para {prefix}<id>"
        )
    consequences = _map(contract.get("consequencias"), "consequencias")
    if set(consequences) != {"agir", "nao_agir"}:
        raise CharacterSidequestError(
            "consequencias exige exatamente agir e nao_agir"
        )
    normalized = {
        "versao": SCHEMA,
        "tipo": source_type,
        "causa": cause,
        "situacao": _text(contract.get("situacao"), "situacao"),
        "motivo_envolver_ren": _text(
            contract.get("motivo_envolver_ren"), "motivo_envolver_ren"
        ),
        "consequencias": {
            "agir": _text(consequences.get("agir"), "consequencias.agir"),
            "nao_agir": _text(
                consequences.get("nao_agir"), "consequencias.nao_agir"
            ),
        },
    }
    try:
        import sidequests_emergentes as emergent

        emergent._agency_scan(normalized, "oportunidade_sidequest")
    except ValueError as exc:
        raise CharacterSidequestError(str(exc)) from exc
    return normalized


def validate_definition(view: Any, plan: dict[str, Any]) -> dict[str, Any] | None:
    """Liga a causa ao próprio responsável e confirma seu valor canônico atual."""
    raw = _map(plan.get("passo"), "passo").get(STEP_KEY)
    if raw is None:
        return None
    contract = validate_contract(raw)
    actor_id = _map(plan.get("agente"), "agente").get("id")
    source = view.npc_path(actor_id)
    if contract["causa"]["arquivo"] != source:
        raise CharacterSidequestError(
            "causa da sidequest deve pertencer ao próprio personagem interessado"
        )
    try:
        view.value(contract["causa"])
    except ValueError as exc:
        raise CharacterSidequestError(str(exc)) from exc
    return contract


def _cause_projection(plan: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    identity = {
        "agente": plan["agente"],
        "tipo": contract["tipo"],
        "causa": contract["causa"],
    }
    return {
        "schema": SCHEMA,
        "id": "scp-" + _digest(identity)[:24],
        "plano_id": plan["id"],
        "plano_revisao": plan["revisao"],
        "estado_plano": plan["estado"],
        "passo_id": plan["passo"]["id"],
        "interessado": copy.deepcopy(plan["agente"]),
        "tipo": contract["tipo"],
        "fonte_canonica": copy.deepcopy(contract["causa"]),
        "situacao": contract["situacao"],
        "motivo_envolver_ren": contract["motivo_envolver_ren"],
        "consequencias_possiveis": copy.deepcopy(contract["consequencias"]),
    }


def _existing_for_cause(
    state: dict[str, Any], cause_id: str
) -> dict[str, Any] | None:
    for mission_id, mission in sorted((state.get("missoes") or {}).items()):
        if not isinstance(mission, dict):
            continue
        cause = mission.get("causa_personagem")
        if isinstance(cause, dict) and cause.get("id") == cause_id:
            return {
                "id": mission.get("id", mission_id),
                "estado": mission.get("estado"),
                "quest_id": mission.get("quest_id"),
            }
    return None


def _bounded(package: dict[str, Any]) -> dict[str, Any]:
    package = copy.deepcopy(package)
    package.pop("orcamento_pacote", None)
    return opportunity._bounded(package)


def plan(
    repo: Path,
    plan_id: str,
    *,
    local_id: str | None = None,
    danger: str = "media",
    tier: int | None = None,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    """Projeta uma causa já declarada para Task40 sem alterar o repositório."""
    if not isinstance(plan_id, str) or not PLAN_ID_RE.fullmatch(plan_id):
        raise CharacterSidequestError("plano_id inválido")
    try:
        import planos_personagens as plans

        world = mundo.load_world_state(repo)
        control = plans._control(copy.deepcopy(world))
        current = control.get(plan_id)
        if not isinstance(current, dict):
            raise CharacterSidequestError(f"plano inexistente: {plan_id}")
        if current.get("estado") in plans.TERMINAL:
            raise CharacterSidequestError("plano terminal não origina nova oportunidade")
        view = plans.View(repo, [])
        contract = validate_definition(view, current)
        if contract is None:
            raise CharacterSidequestError(
                "plano não declara oportunidade_sidequest; não inferir missão da intenção"
            )
    except (plans.PlanError, mundo.WorldEngineError, OSError, yaml.YAMLError) as exc:
        raise CharacterSidequestError(str(exc)) from exc
    if contract["tipo"] == "impedimento" and current["estado"] != "bloqueado":
        raise CharacterSidequestError(
            "impedimento só vira oportunidade enquanto o plano está bloqueado"
        )

    cause = _cause_projection(current, contract)
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise CharacterSidequestError(str(exc)) from exc
    existing = _existing_for_cause(state, cause["id"])
    if existing is not None:
        return _bounded(
            {
                "ok": True,
                "resultado": "causa_personagem_ja_encaminhada",
                "read_only": True,
                "mutacoes_aplicadas": False,
                "causa_personagem": cause,
                "missao_existente": existing,
                "fontes_lidas": [
                    mundo.WORLD_STATE_PATH.as_posix(),
                    oportunidades.INDEX.as_posix(),
                    oportunidades.STATE.as_posix(),
                    *sorted(view.signatures),
                ],
                "metricas": {
                    "intencoes_lidas": 0,
                    "scans_globais": 0,
                    "transcricao_lida": False,
                    "catalogo_task33_aberto": False,
                },
                "regra": (
                    "a mesma causa conserva o estado já decidido; recusa ou abandono "
                    "não são esquecidos e não fabricam punição"
                ),
            }
        )

    try:
        package = opportunity.plan(
            repo,
            signaled=True,
            origin_type="plano_personagem",
            origin_id="plano-personagem:" + cause["id"],
            anchor_type=contract["tipo"],
            anchor=contract["situacao"],
            npc_id=current["agente"]["id"],
            local_id=local_id,
            danger=danger,
            tier=tier,
            now=now,
            character_plan_validated=True,
        )
    except opportunity.EmergentSidequestOpportunityError as exc:
        raise CharacterSidequestError(str(exc)) from exc
    package["causa_personagem"] = cause
    package["fontes_lidas"] = list(
        dict.fromkeys(
            [
                mundo.WORLD_STATE_PATH.as_posix(),
                *sorted(view.signatures),
                *(package.get("fontes_lidas") or []),
            ]
        )
    )
    return _bounded(package)


def validate_authoring_link(
    cause_raw: Any, normalized_spec: dict[str, Any]
) -> None:
    """Impede que a autoria troque interessado, pedido ou consequência da causa."""
    cause = _map(cause_raw, "causa_personagem")
    interested = _map(cause.get("interessado"), "causa_personagem.interessado")
    if normalized_spec["quest_giver"]["id"] != interested.get("id"):
        raise CharacterSidequestError(
            "quest_giver deve ser o personagem interessado na causa NV-11"
        )
    if normalized_spec["oferta"]["premissa"] != cause.get("situacao"):
        raise CharacterSidequestError(
            "premissa da oferta deve preservar a situação concreta NV-11"
        )
    if normalized_spec["oferta"]["pedido"] != cause.get("motivo_envolver_ren"):
        raise CharacterSidequestError(
            "pedido deve preservar o motivo canônico para envolver Ren"
        )
    consequences = _map(
        cause.get("consequencias_possiveis"),
        "causa_personagem.consequencias_possiveis",
    )
    if normalized_spec["stakes"]["consequencia_expiracao"] != consequences.get(
        "nao_agir"
    ):
        raise CharacterSidequestError(
            "consequência de não agir deve permanecer no contrato de stakes"
        )


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        if "plano_personagem" not in opportunity.VALID_ORIGIN_TYPES:
            errors.append("Task40 não reconhece a origem plano_personagem")
        if "abandonada" not in oportunidades.TERMINAL_STATES:
            errors.append("lifecycle não reconhece sidequest abandonada")
    except (OSError, ValueError, yaml.YAMLError) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "erros": errors,
        "contrato": {
            "catalogos_novos": 0,
            "schedulers_novos": 0,
            "chamadas_ia_por_npc": 0,
            "missao_inicial": "oferecida",
            "aceite_automatico": False,
            "recusa_reapresentada": False,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    prepare = sub.add_parser("preparar")
    prepare.add_argument("plano_id")
    prepare.add_argument("--local")
    prepare.add_argument(
        "--periculosidade",
        default="media",
        choices=sorted(__import__("recompensas").VALID_DANGER),
    )
    prepare.add_argument("--tier", type=int)
    sub.add_parser("check")
    args = parser.parse_args(argv)
    try:
        result = (
            check(args.repo.resolve())
            if args.cmd == "check"
            else plan(
                args.repo.resolve(),
                args.plano_id,
                local_id=args.local,
                danger=args.periculosidade,
                tier=args.tier,
            )
        )
    except (CharacterSidequestError, mundo.WorldEngineError) as exc:
        print(yaml.safe_dump({"ok": False, "erro": str(exc)}, allow_unicode=True), end="")
        return 2
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
