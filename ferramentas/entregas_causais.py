"""Contrato de entrega causal transacional ao jogador (NV-13).

Toda resolução genérica do Mundo Vivo declara que não produziu informação para
Ren ou registra, no mesmo lote, um único destino causal reservado. O recibo usa
``relogio:entrega_<id>`` porque relógios já participam do journal atômico de
consolidação. Uma entrega sem canal permanece como pendência do Mundo Vivo.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import re
from typing import Any

import yaml

import mundo

SCHEMA = 1
PENDING_TYPE = "entrega_causal"
NON_COMMUNICABLE_TAG = "entrega-causal:nao-comunicavel"
CLOCK_PREFIX = "entrega_"
EXEMPT_PENDING_TYPES = {
    "reavaliar_agente_leve",
    "resolver_reacao_sidequest",
    "resolver_grupo_operacoes",
    "resolver_operacao_adversarial",
    "avaliar_plano_personagem",
    "resolver_sidequest",
}
PENDING_ID_RE = re.compile(r"^mundo-([0-9a-f]{16})$")
PLAN_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")


class DeliveryError(ValueError):
    """Contrato de entrega causal inválido."""


def _text(value: Any, label: str, maximum: int = 1200) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise DeliveryError(f"{label} deve ser texto não vazio de até {maximum} caracteres")
    return value.strip()


def clock_id(pending_id: str) -> str:
    match = PENDING_ID_RE.fullmatch(str(pending_id))
    if not match:
        raise DeliveryError(f"id de pendência inválido: {pending_id!r}")
    return CLOCK_PREFIX + match.group(1)


def target_for(pending_id: str) -> str:
    return "relogio:" + clock_id(pending_id)


def requires_contract(pending: dict[str, Any]) -> bool:
    return str(pending.get("tipo") or "") not in EXEMPT_PENDING_TYPES


def _deadline(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"data", "hora"}:
        raise DeliveryError("prazo de entrega exige data e hora")
    data = _text(value.get("data"), "prazo.data", 80)
    hora = _text(value.get("hora"), "prazo.hora", 5)
    if not re.fullmatch(r"[0-2][0-9]:[0-5][0-9]", hora):
        raise DeliveryError("prazo.hora exige HH:MM")
    try:
        mundo.parse_instant(data, hora)
    except mundo.WorldEngineError as exc:
        raise DeliveryError(str(exc)) from exc
    return {"data": data, "hora": hora}


def _destination(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DeliveryError("destino causal deve ser mapa")
    state = value.get("estado")
    if state == "entregue":
        if set(value) != {"estado", "canal"}:
            raise DeliveryError("destino entregue exige estado e canal")
        return {"estado": state, "canal": _text(value.get("canal"), "canal", 160)}
    if state == "plano":
        if set(value) != {"estado", "plano_id", "responsavel", "canal", "prazo"}:
            raise DeliveryError("destino plano exige plano_id, responsavel, canal e prazo")
        plan_id = _text(value.get("plano_id"), "plano_id", 64)
        if not PLAN_ID_RE.fullmatch(plan_id):
            raise DeliveryError("plano_id inválido")
        return {
            "estado": state,
            "plano_id": plan_id,
            "responsavel": _text(value.get("responsavel"), "responsavel", 96),
            "canal": _text(value.get("canal"), "canal", 160),
            "prazo": _deadline(value.get("prazo")),
        }
    if state == "bloqueada":
        allowed = {"estado", "motivo", "detalhe", "responsavel"}
        if not {"estado", "motivo", "detalhe"} <= set(value) or set(value) - allowed:
            raise DeliveryError("destino bloqueado exige motivo, detalhe e responsavel opcional")
        if value.get("motivo") != "sem_canal":
            raise DeliveryError("bloqueio de entrega só aceita motivo sem_canal")
        result = {
            "estado": state,
            "motivo": "sem_canal",
            "detalhe": _text(value.get("detalhe"), "detalhe", 480),
        }
        if value.get("responsavel") is not None:
            result["responsavel"] = _text(value.get("responsavel"), "responsavel", 96)
        return result
    if state == "falhou":
        if set(value) != {"estado", "canal", "consequencia"}:
            raise DeliveryError("destino falhou exige canal e consequencia")
        return {
            "estado": state,
            "canal": _text(value.get("canal"), "canal", 160),
            "consequencia": _text(value.get("consequencia"), "consequencia", 480),
        }
    if state == "abandonada":
        if set(value) != {"estado", "consequencia"}:
            raise DeliveryError("destino abandonado exige consequencia")
        return {
            "estado": state,
            "consequencia": _text(value.get("consequencia"), "consequencia", 480),
        }
    raise DeliveryError("destino deve ser entregue, plano, bloqueada, falhou ou abandonada")


def validate_event(
    value: Any,
    pending_id: str,
    transaction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    required = {
        "versao", "tipo", "pendencia", "comunicavel", "destinatario",
        "causa", "conteudo", "destino",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise DeliveryError("recibo comunicável possui campos inválidos")
    if value.get("versao") != SCHEMA or value.get("tipo") != "entrega_causal":
        raise DeliveryError("recibo deve usar versao 1 e tipo entrega_causal")
    if value.get("pendencia") != pending_id or value.get("comunicavel") is not True:
        raise DeliveryError("recibo deve apontar a pendência e marcar comunicavel=true")
    if value.get("destinatario") != "ren":
        raise DeliveryError("NV-13 cobre informação destinada a Ren")
    result = {
        "versao": SCHEMA,
        "tipo": "entrega_causal",
        "pendencia": pending_id,
        "comunicavel": True,
        "destinatario": "ren",
        "causa": _text(value.get("causa"), "causa", 480),
        "conteudo": _text(value.get("conteudo"), "conteudo"),
        "destino": _destination(value.get("destino")),
    }
    destination = result["destino"]
    if destination["estado"] == "plano" and transaction is not None:
        expected = f"plano:{destination['plano_id']}"
        if not any(
            isinstance(delta, dict) and delta.get("alvo") == expected
            for delta in transaction.get("deltas") or []
        ):
            raise DeliveryError(f"destino plano exige evento {expected} na mesma transação")
    return result


def _deltas(transaction: dict[str, Any], pending_id: str) -> list[dict[str, Any]]:
    target = target_for(pending_id)
    return [
        delta for delta in transaction.get("deltas") or []
        if isinstance(delta, dict) and delta.get("alvo") == target
    ]


def _validate_delta(
    delta: dict[str, Any], pending_id: str, transaction: dict[str, Any]
) -> dict[str, Any]:
    if delta.get("op") != "registrar" or delta.get("visibilidade") != "narrador" or "caminho" in delta:
        raise DeliveryError("recibo NV-13 exige registrar reservado sem caminho")
    return validate_event(delta.get("valor"), pending_id, transaction)


def validate_retry_shape(transaction: dict[str, Any], pending_id: str) -> None:
    """Revalida marcadores NV-13; o fingerprint transacional fixa seu conteúdo."""
    tags = transaction.get("tags") or []
    negative = NON_COMMUNICABLE_TAG in tags
    deltas = _deltas(transaction, pending_id)
    if negative and deltas:
        raise DeliveryError("retry mistura não-comunicável com recibo comunicável")
    if len(deltas) > 1:
        raise DeliveryError("retry contém recibos de entrega duplicados")
    for delta in deltas:
        _validate_delta(delta, pending_id, transaction)


def validate_resolution(
    pending: dict[str, Any], transaction: dict[str, Any]
) -> dict[str, Any] | None:
    """Writer gate: uma resolução genérica sempre fecha a pergunta comunicável?"""
    if not requires_contract(pending):
        return None
    pending_id = _text(pending.get("id"), "pendencia.id", 32)
    tags = transaction.get("tags") or []
    negative = sum(tag == NON_COMMUNICABLE_TAG for tag in tags)
    deltas = _deltas(transaction, pending_id)
    if negative and deltas:
        raise DeliveryError("resolução mistura não-comunicável com recibo comunicável")
    if negative > 1:
        raise DeliveryError("tag não-comunicável duplicada")
    if negative == 1:
        return None
    if len(deltas) != 1:
        raise DeliveryError(
            "resolução do Mundo Vivo exige exatamente um destino NV-13 ou a tag "
            f"{NON_COMMUNICABLE_TAG}; veja docs/nv13-entrega-causal-transacional.md"
        )
    return _validate_delta(deltas[0], pending_id, transaction)


def latest(repo: Path, pending_id: str) -> dict[str, Any] | None:
    """Consulta dirigida: lê somente o relógio determinístico da causa."""
    path = repo / "narrador/relogios" / f"{clock_id(pending_id)}.yaml"
    if not path.is_file():
        return None
    try:
        doc = yaml.safe_load(path.read_bytes())
    except yaml.YAMLError as exc:
        raise DeliveryError(f"recibo causal inválido: {exc}") from exc
    if not isinstance(doc, dict) or doc.get("schema_relogio") != 1 or not isinstance(doc.get("eventos"), list):
        raise DeliveryError("relógio de entrega causal inválido")
    matches = []
    for item in doc["eventos"]:
        value = item.get("valor") if isinstance(item, dict) else None
        if (
            isinstance(value, dict)
            and value.get("tipo") == "entrega_causal"
            and value.get("pendencia") == pending_id
        ):
            matches.append({
                "transacao": item.get("transacao"),
                "sessao": item.get("sessao"),
                "valor": validate_event(value, pending_id),
            })
    return matches[-1] if matches else None


def blocked_receipt(repo: Path, pending: dict[str, Any]) -> dict[str, Any] | None:
    pending_id = str(pending.get("id") or "")
    receipt = latest(repo, pending_id)
    if receipt is not None:
        return receipt if receipt["valor"]["destino"]["estado"] == "bloqueada" else None
    if pending.get("tipo") != PENDING_TYPE:
        return None
    stored = validate_event(pending.get("entrega_causal"), pending_id)
    if stored["destino"]["estado"] != "bloqueada":
        return None
    return {
        "transacao": pending.get("transacao_origem"),
        "sessao": pending.get("sessao_origem"),
        "valor": stored,
    }


def blocked_projection(repo: Path, pending: dict[str, Any]) -> dict[str, Any] | None:
    receipt = blocked_receipt(repo, pending)
    if receipt is None:
        return None
    value = receipt["valor"]
    when = pending.get("disparado_em") or {}
    return {
        "id": f"entrega:{pending.get('id')}",
        "titulo": "Informação destinada a Ren aguarda canal válido",
        "data": when.get("data"),
        "janela": "até surgir canal causal válido",
        "atraso_dias": 0,
        "nucleo_obrigatorio": value["conteudo"],
        "guardrails": [
            "não expor conteúdo sem canal válido",
            "não concluir enquanto bloqueada",
        ],
        "regra": f"Bloqueio atual: {value['destino']['detalhe']}",
    }


def _new_pending_id(source_id: str, transaction_id: str | None) -> str:
    raw = f"entrega-causal|{source_id}|{transaction_id or 'sem-transacao'}".encode()
    return "mundo-" + hashlib.sha256(raw).hexdigest()[:16]


def materialize_blocked(
    repo: Path,
    pending: dict[str, Any],
    receipt: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Troca causa resolvida por pendência de entrega, sem perder o conteúdo."""
    source_id = str(pending.get("id") or "")
    receipt = receipt or blocked_receipt(repo, pending)
    if receipt is None or receipt["valor"]["destino"]["estado"] != "bloqueada":
        raise DeliveryError("não há entrega bloqueada para preservar")
    state = mundo.load_world_state(repo)
    current = next(
        (item for item in state["pendencias"] if item.get("id") == source_id), None
    )
    if current is None:
        raise DeliveryError("pendência desapareceu antes da preservação da entrega")
    value = deepcopy(receipt["valor"])

    if current.get("tipo") == PENDING_TYPE:
        tx = receipt.get("transacao")
        session = receipt.get("sessao")
        changed = (
            current.get("entrega_causal") != value
            or current.get("transacao_origem") != tx
            or (session is not None and current.get("sessao_origem") != session)
        )
        current["entrega_causal"] = value
        current["transacao_origem"] = tx
        if session is not None:
            current["sessao_origem"] = session
        if changed:
            mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, state)
        return {
            "ok": True,
            "alterou": changed,
            "pendencia": source_id,
            "estado": "bloqueada",
        }

    new_id = _new_pending_id(source_id, receipt.get("transacao"))
    state["pendencias"] = [
        item for item in state["pendencias"] if item.get("id") != source_id
    ]
    completed = {
        "id": source_id,
        "tipo": pending.get("tipo"),
        "disparado_em": deepcopy(pending.get("disparado_em")),
        "resultado": "causa_resolvida_entrega_bloqueada",
    }
    if pending.get("agente"):
        completed["agente"] = pending["agente"]
    if receipt.get("transacao"):
        completed["transacao"] = receipt["transacao"]
    state["concluidas_recentes"].append(completed)
    state["concluidas_recentes"] = state["concluidas_recentes"][-mundo.MAX_RECENT_COMPLETED:]

    stored_value = deepcopy(value)
    stored_value["pendencia"] = new_id
    new_pending = {
        "id": new_id,
        "tipo": PENDING_TYPE,
        "disparado_em": deepcopy(pending.get("disparado_em")),
        "motivo": "Informação destinada a Ren continua bloqueada por ausência de canal causal válido.",
        "origem": f"entrega_causal:{source_id}",
        "entrega_causal": stored_value,
        "transacao_origem": receipt.get("transacao"),
    }
    if receipt.get("sessao") is not None:
        new_pending["sessao_origem"] = receipt["sessao"]
    state["pendencias"].append(new_pending)
    mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, state)
    return {
        "ok": True,
        "alterou": True,
        "pendencia": new_id,
        "estado": "bloqueada",
        "origem": source_id,
    }
