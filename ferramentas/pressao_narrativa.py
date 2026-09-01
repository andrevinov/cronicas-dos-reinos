#!/usr/bin/env python3
"""Roteamento causal de pressões já autorizadas para o hot path de ``cronica``.

O módulo não agenda eventos, não sorteia encontros e não decide a ação de Ren.
Ele somente ordena projeções que já existem, congela no ticket as pressões
comprometidas e valida que o turno dê destino explícito a cada uma delas.

Pendências ``resolver_operacao_adversarial`` são especiais: depois do compromisso
Task51 elas representam uma situação jogável em andamento, não trabalho de
backoffice a ser concluído antes de narrar. A exceção à barreira é estrita e só
vale quando *todas* as pendências abertas são operações cobertas pelo ticket.
"""
from __future__ import annotations

import copy
import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Callable

import yaml

import iniciativa_social
import mundo
import operacoes_concorrentes as operations

SCHEMA = 1
TICKET_KEY = "contrato_pressao"
TRANSACTION_KEY = "pressao_narrativa"
OPERATION_PENDING_TYPE = "resolver_operacao_adversarial"
RESULTS = {"apresentada", "resolvida", "adiada_por_bloqueio", "continua"}
MAX_ITEMS = 12
MAX_OUTPUT_BYTES = 32 * 1024
MAX_TICKET_ITEMS = 8

PRIORITIES = {
    "pendencia_bloqueante": 1,
    "operacao_comprometida": 1,
    "combate_ativo": 2,
    "perigo_imediato": 2,
    "fronteira_temporal": 3,
    "evidencia_em_risco": 3,
    "pessoa_em_risco": 3,
    "prazo_sidequest": 4,
    "reacao_elegivel": 4,
    "acao_social_solicitada": 5,
    "nova_oportunidade": 6,
    "iniciativa_social": 7,
    "rotina_incidental": 7,
}


class NarrativePressureError(ValueError):
    """Contrato de pressão inválido, obsoleto ou sem resolução explícita."""


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise NarrativePressureError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise NarrativePressureError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str, *, minimum: int = 1, maximum: int = 520) -> str:
    if not isinstance(value, str):
        raise NarrativePressureError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if not minimum <= len(result) <= maximum:
        raise NarrativePressureError(f"{label} deve ter {minimum}..{maximum} caracteres")
    return result


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _pressure_id(kind: str, source_id: str, digest: str) -> str:
    return "press-" + _digest({"tipo": kind, "origem": source_id, "digest": digest})[:20]


def sort_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ordena atenção de modo determinístico, sem escolher ação para Ren."""
    if len(items) > MAX_ITEMS:
        raise NarrativePressureError(f"roteador excede {MAX_ITEMS} matérias causais")
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for pos, raw in enumerate(items):
        item = copy.deepcopy(_map(raw, f"pressao[{pos}]"))
        kind = _text(item.get("tipo"), f"pressao[{pos}].tipo", maximum=64)
        if kind not in PRIORITIES:
            raise NarrativePressureError(f"tipo de pressão desconhecido: {kind}")
        pressure_id = _text(item.get("id"), f"pressao[{pos}].id", maximum=96)
        if pressure_id in seen:
            raise NarrativePressureError(f"pressão duplicada: {pressure_id}")
        seen.add(pressure_id)
        item["prioridade"] = PRIORITIES[kind]
        normalized.append(item)
    return sorted(normalized, key=lambda item: (item["prioridade"], item["id"]))


def routable_operation_pendings(repo: Path) -> list[dict[str, Any]] | None:
    """Retorna operações quando elas são a fila inteira; ``None`` preserva o gate.

    Esta função pertence ao caminho raro em que o marcador do Mundo Vivo já
    informou bloqueio. O turno neutro livre nunca abre estado adversarial.
    """
    try:
        world = mundo.load_world_state(repo)
    except mundo.WorldEngineError as exc:
        raise NarrativePressureError(str(exc)) from exc
    pending = list(world.get("pendencias") or [])
    if not pending or any(item.get("tipo") != OPERATION_PENDING_TYPE for item in pending):
        return None
    return sorted(pending, key=lambda item: str(item.get("id")))


def _scene_local(repo: Path, payload: dict[str, Any]) -> str | None:
    scene = _map(payload.get("cena"), "ticket.cena")
    place = scene.get("place")
    if isinstance(place, str) and place.strip():
        return place.strip()
    for tag in scene.get("context_tags") or []:
        if isinstance(tag, str) and tag.startswith("local:") and tag[6:].strip():
            return tag[6:].strip()
    # A leitura do runtime só ocorre quando já existe operação comprometida.
    path = repo / "runtime/cena.yaml"
    if not path.is_file():
        return None
    try:
        runtime = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    location = runtime.get("localizacao") if isinstance(runtime, dict) else None
    if not isinstance(location, dict):
        return None
    canonical = location.get("local_id")
    if isinstance(canonical, str) and canonical.strip():
        return canonical.strip()
    area = location.get("area")
    if not isinstance(area, str) or not area.strip():
        return None
    # Runtime legado pode guardar somente o nome humano. A primeira parcela é
    # o lugar, seguida por bairro/cidade; normalizá-la não cria local novo e só
    # serve para comparar com o ID já congelado na operação.
    raw = unicodedata.normalize("NFKD", area.split(",", 1)[0].casefold())
    plain = "".join(ch for ch in raw if not unicodedata.combining(ch))
    normalized = "_".join(re.findall(r"[a-z0-9]+", plain))
    return normalized or None


def _operation_item(
    repo: Path,
    pending: dict[str, Any],
    *,
    local: str | None,
    now: mundo.WorldInstant | None,
) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    try:
        projected = operations.project_operation_pending(repo, pending)
        perception = operations.project_for_ren(
            repo,
            projected["grupo_operacoes_id"],
            local=local,
            now=now,
        )
    except operations.ConcurrentOperationError as exc:
        raise NarrativePressureError(str(exc)) from exc
    operation_id = projected["operacao_id"]
    direct = next(
        (item for item in perception["percepcao_direta"] if item["operacao_id"] == operation_id),
        None,
    )
    delivered = [
        item
        for item in perception["informacao_remota_entregue"]
        if item["operacao_id"] == operation_id
    ]
    if direct is not None:
        available = {"estado": "direta", "sinais": direct["sinais"]}
    elif delivered:
        available = {
            "estado": "indireta_entregue",
            "entregas": [
                {key: item[key] for key in ("id", "canal_id", "entregue_em", "fatos")}
                for item in delivered
            ],
        }
    else:
        available = {
            "estado": "nao_percebida_por_ren",
            "regra": "não narrar detalhe remoto sem canal; a operação continua no mundo",
        }
    mechanics = _map(projected.get("encontro"), "operacao.encontro")
    mechanics_digest = _digest(mechanics)
    authorization = {
        "pendencia_id": str(pending["id"]),
        "operacao_id": operation_id,
        "grupo_operacoes_id": projected["grupo_operacoes_id"],
        "percepcao_estado": available["estado"],
        "contrato_digest": _digest(
            {
                "pendencia": pending,
                "estado": projected["estado"],
                "local": projected["local"],
                "encontro_digest": mechanics_digest,
                "bloqueios": projected.get("bloqueios_causais") or [],
            }
        ),
    }
    item = {
        "id": _pressure_id("operacao_comprometida", operation_id, authorization["contrato_digest"]),
        "tipo": "operacao_comprometida",
        "origem": {
            "tipo": "operacao_adversarial_task51",
            "id": operation_id,
            "grupo_id": projected["grupo_operacoes_id"],
        },
        "urgencia": "comprometida",
        "janela": {"inicio": pending.get("disparado_em"), "termino": None},
        "percepcao_disponivel": available,
        "resolucao": "obrigatoria",
        "bloqueios_aplicaveis": list(projected.get("bloqueios_causais") or []),
        "contrato_digest": authorization["contrato_digest"],
        "encontro_preparado": True,
        "mecanica_preparada": {
            "modo": (_map(mechanics.get("mecanica"), "encontro.mecanica")).get("modo"),
            "digest": mechanics_digest,
            "antes_da_primeira_rolagem": True,
        },
        "guardrail": "ordena atenção; Ren conserva escolha de reação e a força do encontro não muda pós-rolagem",
    }
    return item, authorization, list(projected.get("fontes_lidas") or [])


def _deadline_items(prepared: dict[str, Any]) -> list[dict[str, Any]]:
    projection = prepared.get("sidequests_ativas")
    if not isinstance(projection, dict):
        return []
    result = []
    for mission in projection.get("missoes") or []:
        if not isinstance(mission, dict) or not mission.get("prazo"):
            continue
        source_id = str(mission.get("mission_id"))
        digest = str((mission.get("digests") or {}).get("missao") or mission.get("digest_missao") or _digest(mission))
        result.append(
            {
                "id": _pressure_id("prazo_sidequest", source_id, digest),
                "tipo": "prazo_sidequest",
                "origem": {"tipo": "missao_ativa", "id": source_id},
                "urgencia": "janela_declarada",
                "janela": copy.deepcopy(mission["prazo"]),
                "percepcao_disponivel": {"estado": "conhecida_por_ren"},
                "resolucao": "opcional_neste_turno",
                "bloqueios_aplicaveis": [],
                "contrato_digest": digest,
            }
        )
    return result


def _opportunity_items(prepared: dict[str, Any]) -> list[dict[str, Any]]:
    opportunity = prepared.get("sidequest_emergente")
    if not isinstance(opportunity, dict):
        return []
    origin = opportunity.get("origem")
    if not isinstance(origin, dict) or not isinstance(origin.get("id"), str):
        # Pacote incompleto não é matéria causal roteável. A camada Task46 é
        # quem valida seu contrato; isto também preserva stubs de teste antigos.
        return []
    source_id = origin["id"]
    digest = _digest(opportunity)
    return [
        {
            "id": _pressure_id("nova_oportunidade", source_id, digest),
            "tipo": "nova_oportunidade",
            "origem": {"tipo": "oportunidade_sidequest", "id": source_id},
            "urgencia": "opcional",
            "janela": opportunity.get("janela"),
            "percepcao_disponivel": {"estado": "causa_presente_na_cena"},
            "resolucao": "opcional",
            "bloqueios_aplicaveis": [],
            "contrato_digest": digest,
        }
    ]


def integrate_prepare(
    repo: Path,
    prepared: dict[str, Any],
    *,
    operation_pendings: list[dict[str, Any]] | None,
    decode_ticket: Callable[[str], dict[str, Any]],
    encode_ticket: Callable[[dict[str, Any]], tuple[str, str]],
) -> dict[str, Any]:
    """Anexa projeção e contrato. Sem matéria causal, devolve o objeto intacto."""
    items: list[dict[str, Any]] = [
        *_deadline_items(prepared),
        *_opportunity_items(prepared),
    ]
    authorizations: list[dict[str, str]] = []
    sources: list[str] = []
    if not operation_pendings and not items:
        return prepared
    payload = decode_ticket(str(prepared["ticket"]))
    scene = _map(payload.get("cena"), "ticket.cena")
    now_raw = scene.get("now_minute")
    now = mundo.WorldInstant(now_raw) if isinstance(now_raw, int) and not isinstance(now_raw, bool) else None
    if operation_pendings:
        local = _scene_local(repo, payload)
        for pending in operation_pendings:
            item, authorization, read = _operation_item(repo, pending, local=local, now=now)
            items.append(item)
            authorizations.append(authorization)
            sources.extend(read)
    ordered = sort_items(items)
    result = copy.deepcopy(prepared)
    result["pressao_narrativa"] = {
        "schema_pressao_narrativa": SCHEMA,
        "itens": ordered,
        "regra_ordem": "prioridade organiza atenção e nunca escolhe ação, intenção ou resposta de Ren",
        "metricas": {"rng_novo": 0, "scheduler_novo": 0, "scan_global": 0},
    }
    if authorizations:
        if len(authorizations) > MAX_TICKET_ITEMS:
            raise NarrativePressureError("ticket excede teto de pressões comprometidas")
        meta = {
            "schema": SCHEMA,
            "itens": [
                {
                    "pressao_id": next(
                        item["id"]
                        for item in ordered
                        if item["tipo"] == "operacao_comprometida"
                        and item["origem"]["id"] == authorization["operacao_id"]
                    ),
                    **authorization,
                }
                for authorization in authorizations
            ],
        }
        payload[TICKET_KEY] = meta
        token, digest = encode_ticket(payload)
        result["ticket"] = token
        result["ticket_id"] = digest
        result.setdefault("contrato_conclusao", {})["pressao_narrativa_task52"] = (
            "Para cada pressão comprometida, declarar em pressao_narrativa.resultados "
            "apresentada, resolvida, adiada_por_bloqueio ou continua; conversa neutra não a encerra."
        )
    result["fontes_lidas"] = list(dict.fromkeys([*(result.get("fontes_lidas") or []), *sources]))
    size = len(yaml.safe_dump(result, allow_unicode=True, sort_keys=False).encode("utf-8"))
    if size > MAX_OUTPUT_BYTES:
        raise NarrativePressureError(
            f"preparação com pressão excede orçamento: {size} > {MAX_OUTPUT_BYTES} bytes"
        )
    return result


def ticket_meta(payload: dict[str, Any]) -> dict[str, Any] | None:
    raw = payload.get(TICKET_KEY)
    if raw is None:
        return None
    meta = _map(raw, TICKET_KEY)
    if set(meta) != {"schema", "itens"} or meta.get("schema") != SCHEMA:
        raise NarrativePressureError("contrato_pressao inválido")
    rows = _list(meta.get("itens"), "contrato_pressao.itens")
    if not 1 <= len(rows) <= MAX_TICKET_ITEMS:
        raise NarrativePressureError("contrato_pressao exige 1..8 itens")
    expected = {
        "pressao_id", "pendencia_id", "operacao_id", "grupo_operacoes_id",
        "percepcao_estado", "contrato_digest"
    }
    seen: set[str] = set()
    for pos, raw_row in enumerate(rows):
        row = _map(raw_row, f"contrato_pressao.itens[{pos}]")
        if set(row) != expected:
            raise NarrativePressureError("linha de contrato_pressao possui campos divergentes")
        for key in expected:
            _text(row.get(key), f"contrato_pressao.{key}", maximum=128)
        if row["pressao_id"] in seen:
            raise NarrativePressureError("pressão comprometida duplicada no ticket")
        seen.add(row["pressao_id"])
    return meta


def strip_ticket_payload(payload: dict[str, Any]) -> dict[str, Any]:
    clean = copy.deepcopy(payload)
    clean.pop(TICKET_KEY, None)
    return clean


def _literal_evidence(transaction: dict[str, Any], value: Any) -> str:
    evidence = _text(value, "evidencia_literal", minimum=8, maximum=360)
    haystack = "\n".join(
        str(transaction.get(key) or "") for key in ("narracao", "resumo")
    )
    if evidence not in haystack:
        raise NarrativePressureError(
            "evidencia_literal da pressão deve aparecer literalmente em narracao ou resumo"
        )
    return evidence


def _fresh_authorization(
    repo: Path,
    row: dict[str, Any],
    *,
    allow_resolved_retry: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    world = mundo.load_world_state(repo)
    pending = next(
        (item for item in world.get("pendencias") or [] if item.get("id") == row["pendencia_id"]),
        None,
    )
    if isinstance(pending, dict) and pending.get("tipo") == OPERATION_PENDING_TYPE:
        try:
            projected = operations.project_operation_pending(repo, pending)
        except operations.ConcurrentOperationError as exc:
            raise NarrativePressureError(str(exc)) from exc
    elif allow_resolved_retry:
        try:
            contract, operation, state_row, source = operations._operation_context(
                repo, row["operacao_id"]
            )
            if state_row.get("estado") not in {"comprometida", "resolvida"}:
                raise NarrativePressureError("retry não encontra operação resolvida")
            reconstructed = operations._operation_pending(contract, operation)
            if reconstructed["id"] != row["pendencia_id"]:
                raise NarrativePressureError("retry reconstruiu pendência divergente")
            encounter_source = operations._encounter_rel(row["operacao_id"]).as_posix()
            encounter = operations._load(repo / encounter_source, encounter_source)
            if encounter.get("encontro_digest") != operations._digest(encounter.get("encontro")):
                raise NarrativePressureError("encontro congelado divergente no retry")
            pending = reconstructed
            projected = {
                "operacao_id": operation["id"],
                "grupo_operacoes_id": contract["grupo_operacoes_id"],
                # O digest congela a autorização no instante comprometido. O
                # estado resolvido é aceito aqui somente para retry idempotente.
                "estado": "comprometida",
                "local": operation["local"],
                "bloqueios_causais": operation["bloqueios_causais"],
                "encontro": encounter["encontro"],
                "fontes_lidas": [source, encounter_source],
            }
        except operations.ConcurrentOperationError as exc:
            raise NarrativePressureError(str(exc)) from exc
    else:
        raise NarrativePressureError(
            f"pressão {row['pressao_id']} ficou obsoleta; execute cronica preparar novamente"
        )
    fresh_digest = _digest(
        {
            "pendencia": pending,
            "estado": projected["estado"],
            "local": projected["local"],
            "encontro_digest": _digest(projected["encontro"]),
            "bloqueios": projected.get("bloqueios_causais") or [],
        }
    )
    if (
        projected["operacao_id"] != row["operacao_id"]
        or projected["grupo_operacoes_id"] != row["grupo_operacoes_id"]
        or fresh_digest != row["contrato_digest"]
    ):
        raise NarrativePressureError(
            f"pressão {row['pressao_id']} divergiu; execute cronica preparar novamente"
        )
    return (
        pending
        if any(item.get("id") == pending.get("id") for item in world.get("pendencias") or [])
        else None,
        projected,
    )


def prepare_conclusion(
    repo: Path,
    *,
    ticket_meta_value: dict[str, Any] | None,
    transaction: dict[str, Any],
) -> dict[str, Any] | None:
    block_raw = transaction.get(TRANSACTION_KEY)
    if ticket_meta_value is None:
        if block_raw not in (None, {}):
            raise NarrativePressureError("transação traz pressão sem contrato no ticket")
        return None
    if block_raw is None:
        raise NarrativePressureError(
            "toda pressão comprometida exige decisão explícita; conversa neutra não encerra a ameaça"
        )
    block = _map(block_raw, "transacao.pressao_narrativa")
    if set(block) != {"resultados"}:
        raise NarrativePressureError("pressao_narrativa aceita somente resultados")
    results_raw = _list(block.get("resultados"), "pressao_narrativa.resultados")
    results: dict[str, dict[str, Any]] = {}
    for pos, raw in enumerate(results_raw):
        item = _map(raw, f"pressao_narrativa.resultados[{pos}]")
        pressure_id = _text(item.get("pressao_id"), "resultado.pressao_id", maximum=96)
        if pressure_id in results:
            raise NarrativePressureError(f"resultado de pressão duplicado: {pressure_id}")
        results[pressure_id] = item
    contracted = {row["pressao_id"]: row for row in ticket_meta_value["itens"]}
    if set(results) != set(contracted):
        raise NarrativePressureError(
            "toda pressão comprometida exige decisão explícita; conversa neutra não encerra a ameaça"
        )
    plan = {"itens": [], "pendencias_autorizadas": []}
    for pressure_id in sorted(contracted):
        contract_row = contracted[pressure_id]
        result = results[pressure_id]
        outcome = _text(result.get("resultado"), "resultado.resultado", maximum=40)
        if outcome not in RESULTS:
            raise NarrativePressureError(f"resultado de pressão inválido: {outcome}")
        pending, projected = _fresh_authorization(
            repo,
            contract_row,
            allow_resolved_retry=outcome == "resolvida",
        )
        visible = contract_row["percepcao_estado"] != "nao_percebida_por_ren"
        expected_fields = {"pressao_id", "resultado"}
        plan_item: dict[str, Any] = {
            "pressao_id": pressure_id,
            "resultado": outcome,
            "operacao_id": contract_row["operacao_id"],
            "pendencia_id": contract_row["pendencia_id"],
        }
        if outcome == "adiada_por_bloqueio":
            expected_fields = {"pressao_id", "resultado", "bloqueio"}
            blocker = _map(result.get("bloqueio"), "resultado.bloqueio")
            if set(blocker) != {"motivo", "prova"}:
                raise NarrativePressureError("adiamento exige bloqueio com motivo e prova")
            normalized = operations._normalized_blockers(
                repo,
                {contract_row["operacao_id"]: blocker},
                {contract_row["operacao_id"]},
            )[contract_row["operacao_id"]]
            plan_item["bloqueio"] = normalized
        else:
            if outcome == "apresentada" and not visible:
                raise NarrativePressureError(
                    "operação remota sem percepção/canal não pode ser apresentada a Ren"
                )
            if visible:
                expected_fields.add("evidencia_literal")
                evidence = _literal_evidence(transaction, result.get("evidencia_literal"))
                plan_item["evidencia_literal"] = evidence
            if outcome == "resolvida":
                expected_fields |= {"prova", "resultado_factual"}
                proof = operations._proof(repo, result.get("prova"), "resultado.prova")
                factual = _text(
                    result.get("resultado_factual"),
                    "resultado.resultado_factual",
                    minimum=12,
                )
                try:
                    _, _, operation_state, _ = operations._operation_context(
                        repo, contract_row["operacao_id"]
                    )
                except operations.ConcurrentOperationError as exc:
                    raise NarrativePressureError(str(exc)) from exc
                if operation_state.get("estado") == "resolvida" and operation_state.get(
                    "resolucao"
                ) != {"resultado": factual, "prova": proof}:
                    raise NarrativePressureError(
                        "retry de pressão resolvida diverge do resultado factual já instalado"
                    )
                plan_item.update({"prova": proof, "resultado_factual": factual})
        if set(result) != expected_fields:
            raise NarrativePressureError(
                f"resultado {pressure_id} possui campos divergentes: {sorted(set(result) ^ expected_fields)}"
            )
        # A projeção do encontro é revalidada acima antes de qualquer rolagem/registro.
        if not isinstance(projected.get("encontro"), dict):
            raise NarrativePressureError("ataque comprometido perdeu encontro/mecânica preparados")
        plan["itens"].append(plan_item)
        if pending is not None:
            plan["pendencias_autorizadas"].append(pending["id"])
    return plan


def writer_transaction(transaction: dict[str, Any]) -> dict[str, Any]:
    clean = copy.deepcopy(transaction)
    clean.pop(TRANSACTION_KEY, None)
    return clean


def authorize_registration(
    repo: Path,
    transaction: dict[str, Any],
    *,
    retry: bool,
    allowed_pending_ids: list[str],
    original: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    """Exceção estrita ao writer para operações representadas no ticket."""
    if retry:
        return original(repo, transaction, retry=retry)
    world = mundo.load_world_state(repo)
    pending = list(world.get("pendencias") or [])
    allowed = set(allowed_pending_ids)
    if pending and all(
        item.get("tipo") == OPERATION_PENDING_TYPE and item.get("id") in allowed
        for item in pending
    ):
        return {
            "ok": True,
            "retry": False,
            "pendencia_resolvida": None,
            "barreira": {
                "bloqueado": True,
                "quantidade": len(pending),
                "roteadas_por_contrato_pressao": sorted(allowed),
            },
        }
    return original(repo, transaction, retry=retry)


def install_conclusion(repo: Path, plan: dict[str, Any] | None) -> dict[str, Any] | None:
    if plan is None:
        return None
    installed = []
    for item in plan["itens"]:
        if item["resultado"] == "resolvida":
            try:
                resolved = operations.resolve_operation(
                    repo,
                    item["operacao_id"],
                    item["prova"],
                    item["resultado_factual"],
                )
            except operations.ConcurrentOperationError as exc:
                raise NarrativePressureError(str(exc)) from exc
            installed.append({"pressao_id": item["pressao_id"], "dominio": resolved})
        else:
            installed.append(
                {
                    "pressao_id": item["pressao_id"],
                    "resultado": item["resultado"],
                    "permanece_ativa": True,
                }
            )
    return {
        "schema_pressao_narrativa": SCHEMA,
        "resultados": installed,
        "regra": "apresentada/continua/adiada preservam a operação; só resultado factual a encerra",
    }


def project_social_pressure(
    social_projection: dict[str, Any],
    *,
    npc_id: str,
    presence_authorized: bool,
    cause_id: str | None,
    cause_known: bool,
) -> dict[str, Any] | None:
    """Converte iniciativa já projetada sem fabricar presença ou conhecimento."""
    try:
        social = iniciativa_social.validate_projection(copy.deepcopy(social_projection))
    except ValueError as exc:
        raise NarrativePressureError(str(exc)) from exc
    if not presence_authorized:
        return None
    if social["exige_motivo"] and (not cause_id or not cause_known):
        return None
    if cause_id is not None and not cause_known:
        return None
    source_id = _text(npc_id, "npc_id", maximum=128)
    digest = _digest({"npc": source_id, "social": social, "causa": cause_id})
    return {
        "id": _pressure_id("iniciativa_social", source_id, digest),
        "tipo": "iniciativa_social",
        "origem": {"tipo": "npc_presente", "id": source_id},
        "urgencia": "incidental",
        "janela": None,
        "percepcao_disponivel": {"estado": "npc_ja_presente_ou_contatavel"},
        "resolucao": "opcional",
        "bloqueios_aplicaveis": [],
        "causa_id": cause_id,
        "contrato_digest": digest,
        "guardrail": "não cria presença, segredo, ação física, sidequest ou interrupção superior",
    }


def authorize_censorship_topic(
    *,
    npc_id: str,
    topic_id: str,
    fact_id: str,
    fact_digest: str,
    previous: dict[str, str] | None,
) -> dict[str, str] | None:
    """Suprime estruturalmente a mesma censura até existir fato causal novo."""
    try:
        return iniciativa_social.authorize_censorship_topic(
            npc_id=npc_id,
            topic_id=topic_id,
            fact_id=fact_id,
            fact_digest=fact_digest,
            previous=previous,
        )
    except ValueError as exc:
        raise NarrativePressureError(str(exc)) from exc


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    budget_path = repo / "baseline/reactive-pressure-routing-orcamento.yaml"
    try:
        budget = _map(yaml.safe_load(budget_path.read_text(encoding="utf-8")), "orçamento")
        limits = _map(budget.get("limites"), "orçamento.limites")
        expected = {
            "itens_por_preparo_max": MAX_ITEMS,
            "pressoes_comprometidas_por_ticket_max": MAX_TICKET_ITEMS,
            "preparo_com_pressao_bytes_max": MAX_OUTPUT_BYTES,
            "rng_novo": 0,
            "scheduler_novo": 0,
            "scans_globais": 0,
            "parser_de_tom": 0,
        }
        if limits != expected:
            errors.append("baseline de pressão narrativa diverge das constantes")
    except (OSError, yaml.YAMLError, NarrativePressureError) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "erros": errors,
        "contrato": {
            "prioridades": dict(PRIORITIES),
            "resultados": sorted(RESULTS),
            "rng_novo": 0,
            "scheduler_novo": 0,
            "scan_global": 0,
            "parser_de_tom": 0,
        },
        "fontes_lidas": ["baseline/reactive-pressure-routing-orcamento.yaml"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("cmd", choices=["check"])
    args = parser.parse_args(argv)
    try:
        result = check(args.repo)
    except NarrativePressureError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False).rstrip())
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
