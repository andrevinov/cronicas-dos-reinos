#!/usr/bin/env python3
"""Portas determinísticas compactas para decisões operacionais do narrador.

Esta camada não cria novas regras nem toma decisões narrativas. Ela chama uma
única porta determinística já existente e projeta somente o contrato operacional
necessário para o próximo passo: IDs, filtros, disponibilidade, gates,
modificadores, deltas previstos e próximo passo mecânico.

As portas legadas continuam disponíveis. Esta camada existe para o hot path e é
somente leitura; a futura CLI unificada pode reutilizá-la sem mover semântica.
"""
from __future__ import annotations

import argparse
import copy
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml

import cena_mundo
import direcoes_destino
import fronteira_mundo
import interacoes_mundo
import mundo
import recompensas

SCHEMA = 1
MAX_ENDPOINT_BYTES = 6144
MAX_LIST_ITEMS = 16
REQUIRED_FIELDS = (
    "schema_endpoint_deterministico",
    "ok",
    "endpoint",
    "deterministico",
    "mutante",
    "ids",
    "filtros",
    "disponibilidade",
    "gates",
    "modificadores",
    "deltas_previstos",
    "proximo_passo",
    "fontes_lidas",
)


class EndpointError(ValueError):
    """Erro de contrato das projeções determinísticas."""


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EndpointError(f"{label} deve ser texto não vazio")
    return value.strip()


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EndpointError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise EndpointError(f"{label} deve ser lista")
    return value


def _compact(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value is None:
            continue
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _bounded(values: Iterable[Any]) -> tuple[list[str], int]:
    compact = _compact(values)
    return compact[:MAX_LIST_ITEMS], max(0, len(compact) - MAX_LIST_ITEMS)


def _entity_id(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    for key in (
        "id",
        "npc_id",
        "agente",
        "agente_id",
        "entrada",
        "direcao",
        "direcao_id",
        "operacao",
        "linha",
        "peca",
    ):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _ids_from(items: Any) -> list[str]:
    if not isinstance(items, list):
        return []
    return _compact(value for item in items if (value := _entity_id(item)))


def _rendered_size(value: dict[str, Any]) -> int:
    return len(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8")
    )


def validate_endpoint(value: Any) -> dict[str, Any]:
    data = _map(value, "endpoint")
    missing = [field for field in REQUIRED_FIELDS if field not in data]
    if missing:
        raise EndpointError("endpoint sem campos obrigatórios: " + ", ".join(missing))
    if data["schema_endpoint_deterministico"] != SCHEMA:
        raise EndpointError(f"schema_endpoint_deterministico deve ser {SCHEMA}")
    if data["ok"] is not True or data["deterministico"] is not True:
        raise EndpointError("endpoint determinístico válido exige ok=true e deterministico=true")
    if data["mutante"] is not False:
        raise EndpointError("Task 10 expõe somente endpoints não mutantes")
    _text(data["endpoint"], "endpoint.endpoint")
    _map(data["ids"], "endpoint.ids")
    _list(data["filtros"], "endpoint.filtros")
    _map(data["disponibilidade"], "endpoint.disponibilidade")
    _list(data["gates"], "endpoint.gates")
    _list(data["modificadores"], "endpoint.modificadores")
    _list(data["deltas_previstos"], "endpoint.deltas_previstos")
    _map(data["proximo_passo"], "endpoint.proximo_passo")
    _list(data["fontes_lidas"], "endpoint.fontes_lidas")
    size = _rendered_size(data)
    if size > MAX_ENDPOINT_BYTES:
        raise EndpointError(
            f"endpoint excede orçamento: {size} bytes > {MAX_ENDPOINT_BYTES}"
        )
    return data


def _build(
    endpoint: str,
    *,
    ids: dict[str, Any],
    filtros: list[str],
    disponibilidade: dict[str, Any],
    gates: list[dict[str, Any]],
    modificadores: list[dict[str, Any]] | None = None,
    deltas_previstos: list[dict[str, Any]] | None = None,
    proximo_passo: dict[str, Any],
    fontes_lidas: list[str],
) -> dict[str, Any]:
    result = {
        "schema_endpoint_deterministico": SCHEMA,
        "ok": True,
        "endpoint": endpoint,
        "deterministico": True,
        "mutante": False,
        "ids": copy.deepcopy(ids),
        "filtros": _compact(filtros),
        "disponibilidade": copy.deepcopy(disponibilidade),
        "gates": copy.deepcopy(gates),
        "modificadores": copy.deepcopy(modificadores or []),
        "deltas_previstos": copy.deepcopy(deltas_previstos or []),
        "proximo_passo": copy.deepcopy(proximo_passo),
        "fontes_lidas": _compact(fontes_lidas),
    }
    validate_endpoint(result)
    return result


def project_scene(preview: dict[str, Any]) -> dict[str, Any]:
    """Projeta uma preparação de cena já calculada, sem nova leitura."""
    preview = _map(preview, "preparacao_cena")
    encounters = list(preview.get("encontros") or [])
    sidequests = []
    gates: list[dict[str, Any]] = []
    encounter_ids: list[str] = []
    for item in encounters:
        if not isinstance(item, dict):
            continue
        npc_id = item.get("npc_id")
        encounter_id = item.get("encontro_id")
        if isinstance(encounter_id, str):
            encounter_ids.append(encounter_id)
        pending = item.get("pendencia")
        pending_id = pending.get("id") if isinstance(pending, dict) else None
        if isinstance(pending_id, str):
            sidequests.append(pending_id)
        gate = {
            "tipo": "sidequest_encontro",
            "npc_id": npc_id,
            "resultado": item.get("resultado"),
        }
        for key in ("motivo", "ficha"):
            if item.get(key) is not None:
                gate[key] = item[key]
        if pending_id is not None:
            gate["pendencia_id"] = pending_id
        gates.append(gate)

    local = preview.get("local") if isinstance(preview.get("local"), dict) else None
    filters = ["resolucao_npc_canonica", "colapso_duplicatas_npc"]
    if local is not None:
        filters.append("registro_local_canonico")
    if preview.get("contexto_tags"):
        filters.extend(
            [
                "tags_contextuais_tipadas",
                "exclusao_elenco_contextual",
            ]
        )

    presence_ids = _ids_from(preview.get("presencas_contextuais"))
    entry_ids = _ids_from(preview.get("entradas_contextuais"))
    operation_ids = _ids_from(preview.get("operacoes_contextuais"))
    direction_ids = _ids_from(preview.get("direcoes_contextuais"))
    candidate_ids = _ids_from(preview.get("candidatos_contextuais"))

    npc_ids, npc_omitted = _bounded(preview.get("npcs_canonicos") or [])
    encounter_ids, encounter_omitted = _bounded(encounter_ids)
    candidate_ids, candidate_omitted = _bounded(candidate_ids)

    ids = {
        "cena": preview.get("cena_id"),
        "preparacao": preview.get("preparacao_id"),
        "local": local.get("local_id") if local else None,
        "npcs": npc_ids,
        "encontros": encounter_ids,
        "sidequests_potenciais": _compact(sidequests),
        "presencas_contextuais": presence_ids,
        "entradas_contextuais": entry_ids,
        "operacoes_contextuais": operation_ids,
        "direcoes_contextuais": direction_ids,
        "candidatos_contextuais": candidate_ids,
    }
    omitted = npc_omitted + encounter_omitted + candidate_omitted
    if omitted:
        ids["ids_omitidos_por_orcamento"] = omitted

    sidequest_count = sum(
        isinstance(item, dict) and item.get("resultado") == "avaliar_sidequest"
        for item in encounters
    )
    next_step: dict[str, Any] = {
        "acao": "registrar_turno_e_confirmar_preparacao",
        "porta_confirmacao": "cena_mundo.py confirmar",
        "preparacao_id": preview.get("preparacao_id"),
    }
    if sidequest_count:
        next_step["antes"] = "avaliar_potencial_sem_converter_em_oferta_automaticamente"

    return _build(
        "cena.preparar",
        ids=ids,
        filtros=filters,
        disponibilidade={
            "confirmacao": bool(preview.get("preparacao_id")),
            "local_solicitado": local is not None,
            "npcs": len(preview.get("npcs_canonicos") or []),
            "candidatos_contextuais": len(preview.get("candidatos_contextuais") or []),
            "sidequests_para_avaliar": sidequest_count,
        },
        gates=gates,
        modificadores=[],
        deltas_previstos=[],
        proximo_passo=next_step,
        fontes_lidas=list(preview.get("fontes_lidas") or []),
    )


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
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    return project_scene(
        cena_mundo.prepare_scene(
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
    )


def project_boundary(result: dict[str, Any]) -> dict[str, Any]:
    result = _map(result, "fronteira")
    boundary = result.get("fronteira") if isinstance(result.get("fronteira"), dict) else None
    reasons = list(boundary.get("motivos") or []) if boundary else []
    grouped = {
        str(item.get("camada")): list(item.get("ids") or [])
        for item in reasons
        if isinstance(item, dict) and item.get("camada")
    }
    interrupt = bool(result.get("interromper"))
    if interrupt:
        next_step = {
            "acao": "resolver_ate_fronteira_e_checkpoint_antes_de_continuar",
            "fronteira": {
                "data": boundary.get("data"),
                "hora": boundary.get("hora"),
            },
        }
    else:
        next_step = {"acao": "pode_comprimir_ate_alvo"}
    gates = [
        {
            "tipo": "fronteira_temporal",
            "resultado": "interromper" if interrupt else "livre",
        }
    ]
    if boundary and boundary.get("minutos_ate_fronteira") is not None:
        gates[0]["minutos_ate_fronteira"] = boundary["minutos_ate_fronteira"]
    return _build(
        "mundo.fronteira",
        ids={"motivos_por_camada": grouped},
        filtros=[
            "tempo_canonico",
            "contrato_arco",
            "estado_das_camadas",
            "pendencias_abertas",
            "orcamentos_de_camada",
        ],
        disponibilidade={
            "alvo_inteiro_sem_checkpoint": not interrupt,
            "inicio": result.get("inicio"),
            "alvo": result.get("alvo"),
        },
        gates=gates,
        modificadores=[],
        deltas_previstos=[],
        proximo_passo=next_step,
        fontes_lidas=list(result.get("fontes_lidas") or []),
    )


def boundary(repo: Path, *, date: str, hour: str) -> dict[str, Any]:
    return project_boundary(fronteira_mundo.query(repo, date, hour))


def project_pending(result: dict[str, Any]) -> dict[str, Any]:
    result = _map(result, "pendencias")
    pending = list(result.get("pendencias") or [])
    by_type: dict[str, list[str]] = {}
    for item in pending:
        if not isinstance(item, dict):
            continue
        pid = item.get("id")
        kind = str(item.get("tipo") or "desconhecido")
        if isinstance(pid, str):
            by_type.setdefault(kind, []).append(pid)
    ids, omitted = _bounded(item.get("id") for item in pending if isinstance(item, dict))
    id_map: dict[str, Any] = {
        "pendencias": ids,
        "por_tipo": {key: _compact(values) for key, values in sorted(by_type.items())},
    }
    if omitted:
        id_map["pendencias_omitidas_por_orcamento"] = omitted
    blocked = bool(pending)
    return _build(
        "mundo.pendencias",
        ids=id_map,
        filtros=["fila_reservada_mundo"],
        disponibilidade={
            "novo_turno": not blocked,
            "quantidade": int(result.get("quantidade") or len(pending)),
        },
        gates=[
            {
                "tipo": "barreira_mundo",
                "resultado": "bloqueado" if blocked else "livre",
            }
        ],
        modificadores=[],
        deltas_previstos=[],
        proximo_passo={
            "acao": (
                "resolver_pendencias_antes_de_novo_turno"
                if blocked
                else "continuar_turno"
            )
        },
        fontes_lidas=list(result.get("fontes_lidas") or []),
    )


def pending(repo: Path) -> dict[str, Any]:
    return project_pending(mundo.pending_view(repo))


def project_direction(result: dict[str, Any]) -> dict[str, Any]:
    result = _map(result, "direcao")
    milestone = result.get("marco_atual") if isinstance(result.get("marco_atual"), dict) else None
    allowed = bool(result.get("permitido"))
    gate: dict[str, Any] = {
        "tipo": "direcao_destino",
        "resultado": "avaliar" if allowed else "bloqueada",
    }
    if result.get("motivo") is not None:
        gate["motivo"] = result["motivo"]
    if milestone is not None:
        gate["criterio_para_avancar"] = milestone.get("criterio_para_avancar")
        gate["guardrails"] = list(milestone.get("guardrails") or [])
    return _build(
        "direcao.avaliar_destino",
        ids={
            "direcao": result.get("direcao_id"),
            "marco": milestone.get("id") if milestone else None,
        },
        filtros=["contrato_arco", "estado_direcao", "restricao_destino"],
        disponibilidade={
            "permitido": allowed,
            "executavel": False,
            "estado": result.get("estado"),
        },
        gates=[gate],
        modificadores=[],
        deltas_previstos=[],
        proximo_passo={
            "acao": (
                "avaliar_fato_canonico_para_marco"
                if allowed
                else "nao_avancar_direcao"
            )
        },
        fontes_lidas=list(result.get("fontes_lidas") or []),
    )


def direction(repo: Path, query: str) -> dict[str, Any]:
    return project_direction(direcoes_destino.project(repo, query))


def project_sidequest(result: dict[str, Any]) -> dict[str, Any]:
    result = _map(result, "sidequest")
    deltas = [
        {"fase": "turno", "delta": copy.deepcopy(delta)}
        for delta in result.get("deltas_transacionais") or []
    ]
    deltas.extend(
        {"fase": "pos_canonico", "efeito": copy.deepcopy(effect)}
        for effect in result.get("pos_canonico") or []
    )
    links = list(result.get("vinculos") or [])
    link_ids = _compact(
        value
        for item in links
        if isinstance(item, dict)
        for value in [item.get("id")]
        if isinstance(value, str)
    )
    has_turn = bool(result.get("deltas_transacionais"))
    has_post = bool(result.get("pos_canonico"))
    if has_turn:
        next_step: dict[str, Any] = {"acao": "registrar_deltas_no_mesmo_turno"}
        if has_post:
            next_step["depois"] = "aplicar_pos_canonico_apos_fato_base_canonico"
    elif has_post:
        next_step = {"acao": "canonizar_fato_base_antes_de_pos_canonico"}
    else:
        next_step = {"acao": "registrar_turno_sem_delta_extra"}
    return _build(
        "sidequest.preparar_efeitos",
        ids={
            "sidequest": result.get("sidequest"),
            "npc": result.get("npc_id"),
            "vinculos": link_ids,
        },
        filtros=[
            "sidequest_aceita",
            "tipos_de_efeito_controlados",
            "maximo_seis_efeitos",
            "agente_novo_exige_classificacao_npc_v2",
        ],
        disponibilidade={
            "deltas_no_turno": len(result.get("deltas_transacionais") or []),
            "efeitos_pos_canonico": len(result.get("pos_canonico") or []),
            "vinculos": len(links),
        },
        gates=[{"tipo": "estado_sidequest", "resultado": "aceita"}],
        modificadores=[],
        deltas_previstos=deltas,
        proximo_passo=next_step,
        fontes_lidas=list(result.get("fontes_lidas") or []),
    )


def sidequest(repo: Path, mission_id: str, effects: Any) -> dict[str, Any]:
    return project_sidequest(
        interacoes_mundo.prepare_sidequest_effects(repo, mission_id, effects)
    )


def _instant_arg(date: str | None, hour: str | None) -> mundo.WorldInstant | None:
    if date is None and hour is None:
        return None
    if not date or not hour:
        raise EndpointError("--data e --hora devem ser usados juntos")
    try:
        return mundo.parse_instant(date, hour)
    except mundo.WorldEngineError as exc:
        raise EndpointError(str(exc)) from exc


def _stdin() -> Any:
    raw = sys.stdin.read()
    if not raw.strip():
        raise EndpointError("sidequest exige YAML/JSON em stdin")
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise EndpointError(f"stdin inválido: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)

    scene_parser = sub.add_parser("cena", help="prepara cena em contrato compacto")
    scene_parser.add_argument("--cena-id", required=True)
    scene_parser.add_argument("--npc", action="append", default=[])
    scene_parser.add_argument("--contexto-tag", action="append", default=[])
    scene_parser.add_argument("--local")
    scene_parser.add_argument("--acao", choices=sorted(interacoes_mundo.VALID_LOCAL_ACTIONS))
    scene_parser.add_argument("--tier", type=int)
    scene_parser.add_argument("--periculosidade", choices=sorted(recompensas.VALID_DANGER))
    scene_parser.add_argument("--data")
    scene_parser.add_argument("--hora")

    boundary_parser = sub.add_parser("fronteira", help="consulta fronteira temporal compacta")
    boundary_parser.add_argument("--data", required=True)
    boundary_parser.add_argument("--hora", required=True)

    sub.add_parser("pendencias", help="consulta barreira do Mundo Vivo compacta")

    direction_parser = sub.add_parser("direcao", help="avalia restrição de destino compacta")
    direction_parser.add_argument("direcao")

    sidequest_parser = sub.add_parser("sidequest", help="prepara efeitos estruturados por stdin")
    sidequest_parser.add_argument("id")
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
                now=_instant_arg(args.data, args.hora),
            )
        elif args.cmd == "fronteira":
            result = boundary(repo, date=args.data, hour=args.hora)
        elif args.cmd == "pendencias":
            result = pending(repo)
        elif args.cmd == "direcao":
            result = direction(repo, args.direcao)
        else:
            result = sidequest(repo, args.id, _stdin())
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0
    except (
        EndpointError,
        cena_mundo.SceneGateError,
        direcoes_destino.DestinationDirectionError,
        fronteira_mundo.BoundaryError,
        interacoes_mundo.IntegrationError,
        mundo.WorldEngineError,
        OSError,
        yaml.YAMLError,
    ) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
