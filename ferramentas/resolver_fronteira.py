#!/usr/bin/env python3
"""Resolve em lote pendências acumuladas numa fronteira temporal do Mundo Vivo.

A camada é deliberadamente estreita:

* ``preparar`` é read-only e abre no máximo um fragmento dirigido por pendência;
* todas as pendências são apresentadas num único lote determinístico;
* ``aplicar`` recebe por stdin somente as decisões ``sem_mudanca`` do narrador;
* eventos canônicos datados nunca aceitam no-op;
* candidatos autônomos de pressão só aceitam no-op com bloqueio canônico concreto;
* agentes leves usam ``conclude_noop`` para preservar o cache negativo causal;
* itens omitidos permanecem abertos e são devolvidos como trabalho restante.

O lote não cria scheduler, estado paralelo nem decisão narrativa automática. Ele reduz
a orquestração: uma fronteira com várias rotinas pode ser avaliada numa inferência e
concluída numa única chamada mutante, sem processar cada agente por ferramenta.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import agentes
import agentes_leves
import barreira_mundo
import direcoes_destino
import mundo
import pressao_ravens_bluff

SCHEMA = 1
MAX_BATCH = 16
MAX_NOTE_CHARS = 800
TOKEN_HEX = 24
BATCH_HEX = 24


class BatchBoundaryError(ValueError):
    """Contrato inválido da resolução em lote."""


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _token(value: Any, length: int = TOKEN_HEX) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()[:length]


def _pending_sort_key(item: dict[str, Any]) -> tuple[int, str]:
    when = item.get("disparado_em") or {}
    instant = mundo.parse_instant(str(when.get("data")), str(when.get("hora")))
    return instant.minute, str(item.get("id") or "")


def _source_list(*groups: Any) -> list[str]:
    result: list[str] = []
    for group in groups:
        if not isinstance(group, list):
            continue
        for value in group:
            if isinstance(value, str) and value and value not in result:
                result.append(value)
    return result


def _compact_agent(data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: data.get(key)
        for key in (
            "estado",
            "objetivo_atual",
            "recursos",
            "restricoes",
            "presenca",
            "atuacao_local",
            "plano_atual",
            "conhecimento",
        )
        if key in data
    }


def _compact_light(data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: data.get(key)
        for key in (
            "rotina_padrao",
            "objetivo_atual",
            "iniciativas_possiveis",
            "regra_de_reavaliacao",
        )
        if key in data
    }


def _compact_direction(data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: data.get(key)
        for key in (
            "direcao_id",
            "nome",
            "permitido",
            "estado",
            "marco_atual",
            "modo_avaliacao",
            "avanco_requer_fato_canonico",
            "regra",
            "motivo",
        )
        if key in data
    }


def _compact_canonical(data: dict[str, Any]) -> dict[str, Any]:
    return {
        key: data.get(key)
        for key in (
            "id",
            "titulo",
            "data",
            "janela",
            "atraso_dias",
            "nucleo_obrigatorio",
            "guardrails",
            "regra",
        )
        if key in data
    }


def _base_item(pending: dict[str, Any]) -> dict[str, Any]:
    return {
        key: pending.get(key)
        for key in (
            "id",
            "tipo",
            "agente",
            "agente_leve",
            "direcao",
            "evento",
            "agendamento",
            "disparado_em",
            "motivo",
            "origem",
        )
        if pending.get(key) is not None
    }


def _project_item(repo: Path, pending: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    sources = [mundo.WORLD_STATE_PATH.as_posix()]
    canonical = barreira_mundo._canonical_event(repo, pending)
    try:
        pressure = pressao_ravens_bluff.candidate_for_pending(repo, pending)
    except pressao_ravens_bluff.PressureError as exc:
        raise BatchBoundaryError(str(exc)) from exc

    item = _base_item(pending)
    context: dict[str, Any] = {}

    if canonical is not None:
        item["classificacao"] = "requer_fato_canonico"
        item["sem_mudanca_permitido"] = False
        context["evento_canonico"] = _compact_canonical(canonical)
    elif pressure is not None:
        item["classificacao"] = "avaliar_candidato_autonomo"
        item["sem_mudanca_permitido"] = "somente_bloqueio_canonico_concreto"
        context["pressao_ravens_bluff"] = pressure
    else:
        item["classificacao"] = "avaliar_no_lote"
        item["sem_mudanca_permitido"] = True

    pending_type = str(pending.get("tipo") or "")
    if pending_type == "reavaliar_agente" and pending.get("agente"):
        try:
            loaded = agentes.load_agent(repo, str(pending["agente"]))
        except agentes.AgentValidationError as exc:
            raise BatchBoundaryError(str(exc)) from exc
        context["agente"] = _compact_agent(loaded["resultado"])
        context["elegibilidade_local"] = loaded.get("elegibilidade_local")
        sources = _source_list(sources, loaded.get("fontes_lidas"))
    elif pending_type == "reavaliar_agente_leve" and pending.get("agente_leve"):
        try:
            loaded = agentes_leves.load_agent(repo, str(pending["agente_leve"]))
        except agentes_leves.LightAgentError as exc:
            raise BatchBoundaryError(str(exc)) from exc
        context["agente_leve"] = _compact_light(loaded["resultado"])
        sources = _source_list(sources, loaded.get("fontes_lidas"))
    elif pending_type == "avaliar_direcao" and pending.get("direcao"):
        try:
            projection = direcoes_destino.project(repo, str(pending["direcao"]))
        except direcoes_destino.DestinationDirectionError as exc:
            raise BatchBoundaryError(str(exc)) from exc
        context["direcao"] = _compact_direction(projection)
        sources = _source_list(sources, projection.get("fontes_lidas"))

    if context:
        item["contexto"] = context

    token_payload = {
        "pendencia": _base_item(pending),
        "classificacao": item["classificacao"],
        "sem_mudanca_permitido": item["sem_mudanca_permitido"],
        "contexto": context,
    }
    item["token"] = _token(token_payload)
    return item, sources


def prepare_batch(repo: Path) -> dict[str, Any]:
    """Projeta todas as pendências abertas em um único contrato read-only."""
    state = mundo.load_world_state(repo)
    pending = sorted(
        [item for item in state.get("pendencias") or [] if isinstance(item, dict)],
        key=_pending_sort_key,
    )
    if len(pending) > MAX_BATCH:
        raise BatchBoundaryError(
            f"fronteira possui {len(pending)} pendências; teto do lote é {MAX_BATCH}"
        )

    items: list[dict[str, Any]] = []
    sources = [mundo.WORLD_STATE_PATH.as_posix()]
    for raw in pending:
        item, item_sources = _project_item(repo, raw)
        items.append(item)
        sources = _source_list(sources, item_sources)

    batch_payload = [{"id": item.get("id"), "token": item["token"]} for item in items]
    batch_id = f"frn1.{_token(batch_payload, BATCH_HEX)}"
    return {
        "schema_resolucao_fronteira": SCHEMA,
        "ok": True,
        "mutante": False,
        "lote_id": batch_id,
        "quantidade": len(items),
        "itens": items,
        "fontes_lidas": sources,
        "proximo_passo": {
            "acao": "decidir_sem_mudanca_em_conjunto",
            "regra": (
                "Avalie todos os itens nesta mesma inferência. Envie em `sem_mudanca` "
                "somente os itens que realmente não criam fato; omita os que exigem ação. "
                "Evento canônico nunca aceita no-op. Candidato autônomo exige bloqueio "
                "canônico concreto."
            ),
            "entrada_aplicar": {
                "lote_id": batch_id,
                "sem_mudanca": [
                    {"id": "<id>", "token": "<token>", "nota": "<motivo concreto>"}
                ],
            },
        },
    }


def _normalize_note(value: Any) -> str:
    if not isinstance(value, str):
        raise BatchBoundaryError("nota de sem_mudanca deve ser texto")
    note = " ".join(value.split())
    if len(note) < 8:
        raise BatchBoundaryError("nota de sem_mudanca deve explicar o motivo")
    if len(note) > MAX_NOTE_CHARS:
        raise BatchBoundaryError(
            f"nota de sem_mudanca excede {MAX_NOTE_CHARS} caracteres"
        )
    return note


def _completed_map(repo: Path) -> dict[str, dict[str, Any]]:
    state = mundo.load_world_state(repo)
    return {
        str(item["id"]): item
        for item in state.get("concluidas_recentes") or []
        if isinstance(item, dict) and item.get("id")
    }


def _parse_plan(payload: Any) -> tuple[str, list[dict[str, str]]]:
    if not isinstance(payload, dict):
        raise BatchBoundaryError("plano de lote deve ser mapa")
    batch_id = payload.get("lote_id")
    if not isinstance(batch_id, str) or not batch_id.startswith("frn1."):
        raise BatchBoundaryError("lote_id inválido")
    raw = payload.get("sem_mudanca")
    if not isinstance(raw, list):
        raise BatchBoundaryError("sem_mudanca deve ser lista")
    if len(raw) > MAX_BATCH:
        raise BatchBoundaryError(f"sem_mudanca excede teto {MAX_BATCH}")

    decisions: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, value in enumerate(raw):
        if not isinstance(value, dict):
            raise BatchBoundaryError(f"sem_mudanca[{index}] deve ser mapa")
        pending_id = value.get("id")
        token = value.get("token")
        if not isinstance(pending_id, str) or not barreira_mundo.PENDING_ID_RE.fullmatch(
            pending_id
        ):
            raise BatchBoundaryError(f"sem_mudanca[{index}].id inválido")
        if pending_id in seen:
            raise BatchBoundaryError(f"pendência repetida no lote: {pending_id}")
        seen.add(pending_id)
        if (
            not isinstance(token, str)
            or len(token) != TOKEN_HEX
            or any(ch not in "0123456789abcdef" for ch in token)
        ):
            raise BatchBoundaryError(f"sem_mudanca[{index}].token inválido")
        decisions.append(
            {"id": pending_id, "token": token, "nota": _normalize_note(value.get("nota"))}
        )
    return batch_id, decisions


def apply_batch(repo: Path, payload: Any) -> dict[str, Any]:
    """Aplica todos os no-ops aprovados numa chamada, com revalidação por item."""
    requested_batch_id, decisions = _parse_plan(payload)
    current = prepare_batch(repo)
    current_by_id = {str(item["id"]): item for item in current["itens"]}
    completed = _completed_map(repo)

    validated: list[tuple[dict[str, str], dict[str, Any] | None]] = []
    already: list[dict[str, Any]] = []

    # Toda validação acontece antes da primeira escrita.
    for decision in decisions:
        pending_id = decision["id"]
        item = current_by_id.get(pending_id)
        if item is None:
            if pending_id in completed:
                already.append(
                    {
                        "id": pending_id,
                        "resultado": "ja_concluida",
                        "conclusao": completed[pending_id],
                    }
                )
                validated.append((decision, None))
                continue
            raise BatchBoundaryError(
                f"pendência {pending_id} não está aberta nem aparece nas conclusões recentes"
            )

        if decision["token"] != item.get("token"):
            raise BatchBoundaryError(
                f"pendência {pending_id} mudou desde preparar; refaça o lote"
            )
        if item.get("classificacao") == "requer_fato_canonico":
            raise BatchBoundaryError(
                f"pendência {pending_id} é evento canônico e não aceita sem_mudanca"
            )
        if item.get("classificacao") == "avaliar_candidato_autonomo":
            barreira_mundo._validate_autonomous_noop(decision["nota"])
        validated.append((decision, item))

    applied: list[dict[str, Any]] = []
    for decision, item in validated:
        if item is None:
            continue
        pending_id = decision["id"]
        if item.get("tipo") == "reavaliar_agente_leve":
            try:
                result = agentes_leves.conclude_noop(repo, pending_id, decision["nota"])
            except agentes_leves.LightAgentError as exc:
                raise BatchBoundaryError(str(exc)) from exc
        else:
            result = barreira_mundo.conclude(
                repo,
                pending_id,
                decision["nota"],
                no_change=item.get("classificacao") == "avaliar_candidato_autonomo",
            )
        applied.append(
            {
                "id": pending_id,
                "resultado": "sem_mudanca_concluida",
                "tipo": item.get("tipo"),
                "detalhe": result.get("concluida"),
            }
        )

    # Agente leve conclui fora da barreira; sincronizar uma vez também repara retries parciais.
    barrier = barreira_mundo.sync(repo)
    remaining = prepare_batch(repo)
    return {
        "schema_resolucao_fronteira": SCHEMA,
        "ok": True,
        "mutante": True,
        "lote_id_solicitado": requested_batch_id,
        "lote_id_atual": remaining["lote_id"],
        "aplicadas": applied,
        "ja_aplicadas": already,
        "quantidade_restante": remaining["quantidade"],
        "requer_resolucao": remaining["itens"],
        "barreira": barrier,
        "idempotente": True,
        "proximo_passo": (
            {"acao": "continuar_turno"}
            if remaining["quantidade"] == 0
            else {
                "acao": "materializar_somente_itens_restantes",
                "regra": (
                    "Os no-ops já foram fechados em lote. Trabalhe somente os itens "
                    "restantes; não reavalie os concluídos."
                ),
            }
        ),
    }


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        result = prepare_batch(repo)
        if result["quantidade"] > MAX_BATCH:
            errors.append("lote excedeu teto")
        if len({item["id"] for item in result["itens"]}) != result["quantidade"]:
            errors.append("lote contém ids duplicados")
    except (
        BatchBoundaryError,
        mundo.WorldEngineError,
        barreira_mundo.WorldPendingBarrierError,
    ) as exc:
        errors.append(str(exc))
    return {"ok": not errors, "erros": errors}


def _read_stdin_plan() -> Any:
    raw = sys.stdin.read()
    if not raw.strip():
        raise BatchBoundaryError("aplicar exige JSON/YAML por stdin")
    try:
        return yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise BatchBoundaryError(f"plano inválido: {exc}") from exc


def _dump(value: dict[str, Any]) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("preparar")
    sub.add_parser("aplicar")
    sub.add_parser("check")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.command == "preparar":
            result = prepare_batch(repo)
        elif args.command == "aplicar":
            result = apply_batch(repo, _read_stdin_plan())
        else:
            result = check(repo)
        print(_dump(result), end="")
        return 0 if result.get("ok", True) else 1
    except (
        BatchBoundaryError,
        mundo.WorldEngineError,
        barreira_mundo.WorldPendingBarrierError,
    ) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
