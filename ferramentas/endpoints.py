#!/usr/bin/env python3
"""Endpoints determinísticos com contratos operacionais endurecidos.

O contrato original da Task 10 está preservado em ``_endpoints_core.py``. Esta
camada acrescenta qualidade de abordagem, projeções raras de Mundo Vivo e, desde
a Task 32, a sidequest canônica já selecionada pela preparação de cena. Nenhuma
dessas projeções adiciona leitura ao endpoint: só compacta dados já calculados.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Any

import yaml

import _endpoints_core as _base
import contratos_operacionais
import pressao_ravens_bluff
import qualidade_abordagem

_ORIGINAL_PROJECT_SCENE = _base.project_scene
_ORIGINAL_BUILD_PARSER = _base.build_parser
MAX_PRESSURE_CANDIDATES = 4
MAX_CANONICAL_EVENTS = 1

for _name in dir(_base):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_base, _name)


def _normalized_date(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return contratos_operacionais.normalize_date(value)
    except contratos_operacionais.OperationalContractError as exc:
        raise _base.EndpointError(str(exc)) from exc


def _quality(
    *,
    preparacao: str | None = None,
    informacao: str | None = None,
    adequacao: str | None = None,
) -> dict[str, Any]:
    return qualidade_abordagem.evaluate(
        preparacao=preparacao,
        informacao=informacao,
        adequacao=adequacao,
    )


def _canonical_module(repo: Path):
    """Carrega o calendário somente no caminho raro em que ele existe no repo."""
    catalog = repo / "narrador/arcos/parte_1/eventos-canonicos.yaml"
    if not catalog.is_file():
        return None
    try:
        import eventos_canonicos
        return eventos_canonicos
    except ModuleNotFoundError as exc:
        if exc.name != "eventos_canonicos":
            raise
        module_path = Path(__file__).with_name("eventos_canonicos.py")
        spec = importlib.util.spec_from_file_location("eventos_canonicos", module_path)
        if spec is None or spec.loader is None:
            raise _base.EndpointError(
                "não foi possível carregar ferramentas/eventos_canonicos.py"
            ) from exc
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("eventos_canonicos", module)
        spec.loader.exec_module(module)
        return module


def _project_canonical_sidequest(
    result: dict[str, Any],
    preview: dict[str, Any],
) -> None:
    selected = preview.get("sidequest_canonica")
    if not isinstance(selected, dict):
        return
    projection = selected.get("oferta")
    if not isinstance(projection, dict):
        return
    offer = projection.get("oferta")
    if not isinstance(offer, dict):
        offer = {}

    quest_id = selected.get("id")
    npc_id = selected.get("npc_id")
    result["ids"]["sidequest_canonica"] = quest_id
    if "sidequest_canonica_task32" not in result["filtros"]:
        result["filtros"].append("sidequest_canonica_task32")
    result["disponibilidade"]["sidequest_canonica"] = {
        "id": quest_id,
        "npc_id": npc_id,
        "tipo": projection.get("tipo"),
        "titulo": projection.get("titulo"),
        "objetivo": projection.get("objetivo"),
        "premissa": offer.get("premissa"),
        "pedido": offer.get("pedido"),
        "guardrails": list(offer.get("guardrails") or [])[:3],
        "recusa_permitida": True,
    }
    result["gates"].append(
        {
            "tipo": "sidequest_canonica",
            "resultado": "disponivel",
            "id": quest_id,
            "npc_id": npc_id,
            "modo": selected.get("modo"),
            "regra": "disponível não é oferecida nem aceita; Ren controla a resposta",
        }
    )
    result["proximo_passo"]["sidequest_canonica"] = (
        "se o NPC realmente formular este pedido na narração aceita, depois de cronica concluir "
        "registre a oferta com sidequests_canonicas.py oferecer <id> --npc <npc>; não autoaceite"
    )


def project_scene(
    preview: dict[str, Any],
    *,
    approach_preparacao: str | None = None,
    approach_informacao: str | None = None,
    approach_adequacao: str | None = None,
) -> dict[str, Any]:
    result = _ORIGINAL_PROJECT_SCENE(preview)
    quality = _quality(
        preparacao=approach_preparacao,
        informacao=approach_informacao,
        adequacao=approach_adequacao,
    )
    if int(quality["bonus"]) > 0:
        result["modificadores"].append(
            qualidade_abordagem.compact_modifier(quality)
        )
        if "qualidade_abordagem_pre_rolagem" not in result["filtros"]:
            result["filtros"].append("qualidade_abordagem_pre_rolagem")
    _project_canonical_sidequest(result, preview)
    _base.validate_endpoint(result)
    return result


def scene(
    repo: Path,
    *,
    scene_id: str,
    npcs: list[str] | None = None,
    place: str | None = None,
    action: str | None = None,
    tier: int | None = None,
    danger: str | None = None,
    context_tags: list[str] | None = None,
    now: _base.mundo.WorldInstant | None = None,
    approach_preparacao: str | None = None,
    approach_informacao: str | None = None,
    approach_adequacao: str | None = None,
) -> dict[str, Any]:
    preview = _base.cena_mundo.prepare_scene(
        repo,
        scene_id=scene_id,
        npcs=npcs,
        place=place,
        action=action,
        tier=tier,
        danger=danger,
        context_tags=context_tags,
        now=now,
    )
    return project_scene(
        preview,
        approach_preparacao=approach_preparacao,
        approach_informacao=approach_informacao,
        approach_adequacao=approach_adequacao,
    )


def project_pending(result: dict[str, Any]) -> dict[str, Any]:
    projected = _base.project_pending(result)

    canonical = result.get("eventos_canonicos")
    events = (
        list(canonical.get("eventos") or [])
        if isinstance(canonical, dict)
        else []
    )
    if events:
        visible_events = events[:MAX_CANONICAL_EVENTS]
        projected["ids"]["eventos_canonicos"] = [
            item.get("evento")
            for item in visible_events
            if item.get("evento")
        ]
        for item in visible_events:
            projected["gates"].append(
                {
                    "tipo": "evento_canonico_datado",
                    "resultado": "devido",
                    "pendencia": item.get("pendencia"),
                    "evento": item.get("evento"),
                    "titulo": item.get("titulo"),
                    "data": item.get("data"),
                    "janela": item.get("janela"),
                    "atraso_dias": item.get("atraso_dias"),
                    "nucleo_obrigatorio": list(
                        item.get("nucleo_obrigatorio") or []
                    )[:3],
                    "guardrails": list(item.get("guardrails") or [])[:3],
                    "regra": (
                        "núcleo obrigatório; forma e resultado flexíveis; "
                        "nunca escrever decisão de Ren"
                    ),
                }
            )
        projected["proximo_passo"]["evento_canonico"] = (
            "materialize o núcleo na primeira forma causal plausível por transação modo:mundo com a tag "
            "resolver-pendencia-mundo:<id>; depois conclua pela barreira com --transacao. "
            "Não use --sem-mudanca: se o núcleo estiver temporariamente impossível, mantenha a pendência aberta."
        )

    integration = result.get("pressao_ravens_bluff")
    candidates = (
        list(integration.get("candidatos") or [])
        if isinstance(integration, dict)
        else []
    )
    if candidates:
        visible = candidates[:MAX_PRESSURE_CANDIDATES]
        projected["ids"]["pressao_ravens_bluff"] = [
            item.get("pendencia")
            for item in visible
            if item.get("pendencia")
        ]
        for item in visible:
            projected["gates"].append(
                {
                    "tipo": "pressao_ravens_bluff_autonoma",
                    "resultado": "candidato",
                    "pendencia": item.get("pendencia"),
                    "agente": item.get("agente"),
                    "linha": item.get("linha"),
                    "metodo": item.get("metodo"),
                    "frente": item.get("frente"),
                    "de": item.get("de"),
                    "para": item.get("para"),
                    "titulo_destino": item.get("titulo_destino"),
                    "regra": (
                        "ausência de iniciativa de Ren não bloqueia; "
                        "no-op exige bloqueio canônico concreto"
                    ),
                }
            )
        projected["proximo_passo"]["pressao_ravens_bluff"] = (
            "se o candidato for legal para o agente, materialize a ação de mundo; depois conclua "
            "a pendência informando transação, linha e método. Se houver bloqueio canônico real, use --sem-mudanca."
        )

    _base.validate_endpoint(projected)
    return projected


def pending(repo: Path) -> dict[str, Any]:
    raw = _base.mundo.pending_view(repo)
    pendings = list(raw.get("pendencias") or [])
    pressure = pressao_ravens_bluff.pending_candidates(repo, pendings)
    canonical_module = _canonical_module(repo)
    if canonical_module is None:
        canonical = {"eventos": [], "fontes_lidas": []}
    else:
        try:
            canonical = canonical_module.pending_projection(repo, pendings)
        except canonical_module.CanonicalEventError as exc:
            raise _base.EndpointError(str(exc)) from exc
    raw["pressao_ravens_bluff"] = pressure
    raw["eventos_canonicos"] = canonical
    raw["fontes_lidas"] = list(
        dict.fromkeys(
            [
                *(raw.get("fontes_lidas") or []),
                *(pressure.get("fontes_lidas") or []),
                *(canonical.get("fontes_lidas") or []),
            ]
        )
    )
    return project_pending(raw)


def _add_approach_flags(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--abordagem-preparacao",
        help="evidência de preparação concreta que favorece o teste",
    )
    parser.add_argument(
        "--abordagem-informacao",
        help="evidência de informação relevante usada pelo plano",
    )
    parser.add_argument(
        "--abordagem-adequacao",
        help="evidência de que o método se ajusta especialmente bem ao obstáculo",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = _ORIGINAL_BUILD_PARSER()
    sub = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    _add_approach_flags(sub.choices["cena"])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "cena":
            result = scene(
                repo,
                scene_id=args.cena_id,
                npcs=args.npc,
                place=args.local,
                action=args.acao,
                tier=args.tier,
                danger=args.periculosidade,
                context_tags=args.contexto_tag,
                now=_base._instant_arg(
                    _normalized_date(args.data),
                    args.hora,
                ),
                approach_preparacao=args.abordagem_preparacao,
                approach_informacao=args.abordagem_informacao,
                approach_adequacao=args.abordagem_adequacao,
            )
        elif args.cmd == "fronteira":
            result = _base.boundary(
                repo,
                date=_normalized_date(args.data),
                hour=args.hora,
            )
        elif args.cmd == "pendencias":
            result = pending(repo)
        elif args.cmd == "direcao":
            result = _base.direction(repo, args.direcao)
        else:
            result = _base.sidequest(repo, args.id, _base._stdin())
        print(
            yaml.safe_dump(result, allow_unicode=True, sort_keys=False),
            end="",
        )
        return 0
    except (
        pressao_ravens_bluff.PressureError,
        qualidade_abordagem.ApproachQualityError,
        contratos_operacionais.OperationalContractError,
        _base.EndpointError,
        _base.cena_mundo.SceneGateError,
        _base.direcoes_destino.DestinationDirectionError,
        _base.fronteira_mundo.BoundaryError,
        _base.interacoes_mundo.IntegrationError,
        _base.mundo.WorldEngineError,
        OSError,
        yaml.YAMLError,
    ) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
