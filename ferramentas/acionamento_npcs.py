#!/usr/bin/env python3
"""Acionamento causal de agentes leves, dentro das filas e journals existentes.

Dependências são as fontes_causais declaradas e os envolvidos de compromissos.
Uma notificação solicita avaliação; não transmite conhecimento, executa um plano,
cria presença ou cumpre um compromisso. Nenhuma função chama IA ou sorteia dados.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

import yaml

CONTROL = "acionamento_npcs"
CAUSES = "causas_npc"
STATE = "estado/estado-atual.yaml"
WORLD = "narrador/mundo/estado.yaml"
LIGHT_INDEX = "narrador/agentes-leves/index.yaml"
LIGHT_STATE = "narrador/agentes-leves/estado.yaml"
PENDING = "runtime/eventos-pendentes.jsonl"
BARRIER = "runtime/mundo-pendencias.yaml"
KIND = "reavaliar_agente_leve"
MAX_WAITING = 32
MAX_CAUSES = 16
MAX_POINTERS = 16
MAX_CONTROL_BYTES = 32768
MAX_SOURCE_BYTES = 32768
MAX_WORLD_BYTES = 131072
RESOLUTION = "resolucao_npc"
MAX_CONTEXT_BYTES = 3072
MAX_COMMITMENTS = 64


class NpcActivationError(ValueError):
    """Contrato de notificação inválido; falhar antes de persistir."""


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise NpcActivationError("acionamento exige dados JSON finitos") from exc


def digest(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _dump(value: Any) -> bytes:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8")


def _path(repo: Path, source: str) -> Path:
    rel = Path(source)
    if rel.is_absolute() or ".." in rel.parts or not source:
        raise NpcActivationError("fonte fora do repositório")
    path = repo / rel
    if not path.resolve().is_relative_to(repo.resolve()):
        raise NpcActivationError("fonte escapa do repositório por link simbólico")
    return path


def _read(repo: Path, source: str, outputs: dict[str, bytes] | None = None) -> Any:
    path = _path(repo, source)
    raw = outputs[source] if outputs is not None and source in outputs else path.read_bytes()
    limit = MAX_WORLD_BYTES if source == WORLD else MAX_SOURCE_BYTES
    if len(raw) > limit:
        raise NpcActivationError(f"fonte causal excede {limit} bytes: {source}")
    try:
        return yaml.safe_load(raw.decode("utf-8")) or {}
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise NpcActivationError(f"fonte causal inválida: {source}") from exc


def _index(repo: Path) -> dict[str, Any] | None:
    # Sem camada instalada, fixtures e consumidores antigos mantêm o contrato.
    if not (repo / LIGHT_INDEX).is_file():
        return None
    import agentes_leves
    index = agentes_leves.load_index(repo)
    if index["schema_agentes_leves"] != 2:
        return None
    if not all((repo / p).is_file() for p in (LIGHT_STATE, WORLD)):
        raise NpcActivationError("camada causal schema 2 incompleta")
    agentes_leves.load_state(repo, index)
    return index


def _active(index: dict[str, Any]) -> dict[str, Any]:
    return {key: meta for key, meta in index["agentes"].items() if meta.get("estado") == "ativo"}


def subscriptions(index: dict[str, Any]) -> dict[str, set[str]]:
    """Índice reverso em memória; não abre nenhum fragmento de NPC."""
    result: dict[str, set[str]] = {}
    for agent, meta in _active(index).items():
        for source in meta.get("fontes_causais", []):
            result.setdefault(source, set()).add(agent)
    return result


def _control(state: dict[str, Any]) -> dict[str, Any]:
    value = state.get(CONTROL)
    if CONTROL not in state:
        return {"versao": 1, "adiadas": [], "prazos": {}}
    if (not isinstance(value, dict) or type(value.get("versao")) is not int
            or value["versao"] != 1 or set(value) != {"versao", "adiadas", "prazos"}):
        raise NpcActivationError("controle de acionamento inválido")
    if not isinstance(value["adiadas"], list) or len(value["adiadas"]) > MAX_WAITING:
        raise NpcActivationError("fila causal adiada excede o limite ou é inválida")
    if not isinstance(value["prazos"], dict) or len(value["prazos"]) > MAX_COMMITMENTS:
        raise NpcActivationError("recibos de prazo inválidos")
    for cid, receipt in value["prazos"].items():
        if not isinstance(cid, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", cid):
            raise NpcActivationError("ID de recibo de compromisso inválido")
        if (not isinstance(receipt, dict) or set(receipt) != {"assinatura", "entregues"}
                or not isinstance(receipt["assinatura"], str)
                or not re.fullmatch(r"[0-9a-f]{64}", receipt["assinatura"])
                or not isinstance(receipt["entregues"], list)
                or len(receipt["entregues"]) > 12
                or any(not isinstance(x, str) or not re.fullmatch(r"(?:inicio|fim):[a-z][a-z0-9_]{0,79}", x)
                       for x in receipt["entregues"])):
            raise NpcActivationError("recibo de compromisso inválido")
        if len(receipt["entregues"]) != len(set(receipt["entregues"])):
            raise NpcActivationError("entrega temporal duplicada")
    if len(_dump(value)) > MAX_CONTROL_BYTES:
        raise NpcActivationError("controle de acionamento excede o orçamento")
    return copy.deepcopy(value)


def deferred(state: dict[str, Any]) -> list[dict[str, Any]]:
    return _control(state)["adiadas"] if CONTROL in state else []


def _minute(when: dict[str, str]) -> int:
    import mundo
    if not isinstance(when, dict) or set(when) != {"data", "hora"}:
        raise NpcActivationError("instante causal exige data e hora")
    return mundo.parse_instant(when["data"], when["hora"]).minute


def _rank(item: dict[str, Any]) -> tuple[int, int, str]:
    causes = item.get(CAUSES) or []
    rank = 0 if any(c.get("fase") in {"inicio", "fim"} for c in causes) else 1 if causes else 2
    return rank, _minute(item["disparado_em"]), str(item["id"])


def validate_state(state: dict[str, Any], index: dict[str, Any]) -> None:
    if CONTROL not in state and not any(CAUSES in p for p in state.get("pendencias", [])):
        return
    if CONTROL not in state and "schema_estado_mundo" in state:
        raise NpcActivationError("pendência causal sem controle de entrega")
    control = _control(state)
    ids: set[str] = set()
    known = index["agentes"]
    for item in [*state.get("pendencias", []), *control["adiadas"]]:
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise NpcActivationError("item de fila inválido")
        if item["id"] in ids:
            raise NpcActivationError("pendência repetida entre fila aberta e adiada")
        ids.add(item["id"])
        if item.get("tipo") != KIND:
            if item in control["adiadas"]:
                raise NpcActivationError("somente agentes leves podem ser adiados nesta fila")
            continue
        agent = item.get("agente_leve")
        if agent not in known:
            raise NpcActivationError("fila referencia agente desconhecido")
        _minute(item["disparado_em"])
        if RESOLUTION in item:
            resolution = item[RESOLUTION]
            if (not isinstance(resolution, dict) or set(resolution) != {"sessao", "transacao"}
                    or type(resolution["sessao"]) is not int or resolution["sessao"] < 1
                    or not isinstance(resolution["transacao"], str)
                    or not 1 <= len(resolution["transacao"]) <= 160):
                raise NpcActivationError("resolução transacional de NPC inválida")
        if CAUSES in item:
            causes = item[CAUSES]
            if not isinstance(causes, list) or not 1 <= len(causes) <= MAX_CAUSES:
                raise NpcActivationError("causas ausentes ou acima do limite")
            keys: set[str] = set()
            for cause in causes:
                if not isinstance(cause, dict) or not isinstance(cause.get("chave"), str):
                    raise NpcActivationError("causa inválida")
                if cause["chave"] in keys:
                    raise NpcActivationError("causa duplicada")
                keys.add(cause["chave"])
                if cause.get("tipo") == "fonte_alterada":
                    if set(cause) != {"chave", "tipo", "fonte", "campos", "assinatura"}:
                        raise NpcActivationError("campos desconhecidos na causa de fonte")
                    if cause["chave"] != "fonte:" + str(cause.get("fonte")):
                        raise NpcActivationError("chave de fonte inconsistente")
                    if cause.get("fonte") not in known[agent].get("fontes_causais", []):
                        raise NpcActivationError("fonte não declarada para o agente")
                    fields = cause.get("campos")
                    if not isinstance(fields, list) or not 1 <= len(fields) <= MAX_POINTERS:
                        raise NpcActivationError("ponteiros causais inválidos")
                    for field in fields:
                        if not isinstance(field, list) or any(not isinstance(p, str) for p in field):
                            raise NpcActivationError("ponteiro causal deve ser lista de chaves")
                elif cause.get("tipo") == "compromisso":
                    if cause.get("fase") not in {"inicio", "fim", "alterado", "removido"}:
                        raise NpcActivationError("fase de compromisso inválida")
                    if set(cause) != {"chave", "tipo", "compromisso", "fase", "assinatura"}:
                        raise NpcActivationError("campos desconhecidos na causa de compromisso")
                    cid = cause.get("compromisso")
                    if not isinstance(cid, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", cid):
                        raise NpcActivationError("compromisso sem ID válido")
                    suffix = cause["fase"] if cause["fase"] in {"inicio", "fim"} else "mudanca"
                    if cause["chave"] != f"compromisso:{cid}:{suffix}":
                        raise NpcActivationError("chave de compromisso inconsistente")
                else:
                    raise NpcActivationError("tipo de causa desconhecido")
                signature = cause.get("assinatura")
                if (not isinstance(signature, str) or len(signature) != 64
                        or any(c not in "0123456789abcdef" for c in signature)):
                    raise NpcActivationError("assinatura causal inválida")
    if ids & {p["id"] for p in state.get("concluidas_recentes", [])}:
        raise NpcActivationError("fila causal contém item já concluído")


def rebalance(state: dict[str, Any], index: dict[str, Any], *, pinned: Iterable[str] = ()) -> dict[str, Any]:
    """Prioriza causas sem aumentar os dois slots e sem descartar rotinas.

    A parte adiada pertence ao mesmo estado do Mundo Vivo. Não é agenda, memória
    paralela ou decisão de IA. A ordem não depende de chamadas ou sorteios.
    """
    validate_state(state, index)
    result = copy.deepcopy(state)
    control = _control(result)
    if CONTROL not in result and not any(p.get(CAUSES) for p in result["pendencias"]):
        return result
    active = _active(index)
    all_items = [*result["pendencias"], *control["adiadas"]]
    others = [p for p in result["pendencias"] if p.get("tipo") != KIND]
    light = [p for p in all_items if p.get("tipo") == KIND and p.get("agente_leve") in active]
    pinned_ids = set(pinned) | {p["id"] for p in light if p.get(RESOLUTION)}
    light.sort(key=lambda p: (0 if p["id"] in pinned_ids else 1, *_rank(p)))
    limit = int(index["orcamento"]["max_pendencias_abertas"])
    chosen: list[dict[str, Any]] = []
    waiting: list[dict[str, Any]] = []
    selected_agents: set[str] = set()
    for item in light:
        agent = item["agente_leve"]
        if len(chosen) < limit and agent not in selected_agents:
            chosen.append(item)
            selected_agents.add(agent)
        else:
            waiting.append(item)
    result["pendencias"] = others + chosen
    control["adiadas"] = waiting
    result[CONTROL] = control
    validate_state(result, index)
    return result


def enqueue(state: dict[str, Any], index: dict[str, Any], notices: dict[str, list[dict[str, Any]]],
            when: dict[str, str], origin: str, *, pinned: Iterable[str] = ()) -> dict[str, Any]:
    """Coalesce por agente/fonte. O ID de uma avaliação já aberta não é trocado."""
    result = copy.deepcopy(state)
    control = _control(result)
    pinned_ids = set(pinned) | {p["id"] for p in [*result["pendencias"], *control["adiadas"]] if p.get(RESOLUTION)}
    for agent in sorted(notices):
        if agent not in _active(index) or not notices[agent]:
            continue
        available = [p for p in [*result["pendencias"], *control["adiadas"]]
                     if p.get("tipo") == KIND and p.get("agente_leve") == agent and p["id"] not in pinned_ids]
        if available:
            item = min(available, key=_rank)
        else:
            item = {
                "id": "mundo-" + digest([agent, origin, notices[agent]])[:16],
                "tipo": KIND, "agente_leve": agent, "agentes_afetados": [],
                "disparado_em": copy.deepcopy(when),
                "motivo": "Avaliar condição concreta; não executar ação nem atribuir conhecimento automaticamente.",
                "origem": "acionamento-npcs:" + origin,
            }
            if any(p.get("id") == item["id"] for p in result.get("concluidas_recentes", [])):
                continue
            result["pendencias"].append(item)
        by_key = {c["chave"]: c for c in item.get(CAUSES, [])}
        for notice in notices[agent]:
            notice = copy.deepcopy(notice)
            previous = by_key.get(notice["chave"])
            if previous and notice["tipo"] == "fonte_alterada":
                # Duas mudanças antes da avaliação conservam ambos os endereços.
                fields = sorted({tuple(x) for x in previous["campos"] + notice["campos"]})
                notice["campos"] = [list(x) for x in fields] if len(fields) <= MAX_POINTERS else [[]]
            by_key[notice["chave"]] = notice
        item[CAUSES] = [by_key[key] for key in sorted(by_key)]
    if notices:
        result[CONTROL] = control
    return rebalance(result, index, pinned=pinned)


def _changed_paths(before: Any, after: Any, path: tuple[str, ...] = ()) -> list[list[str]]:
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        result: list[list[str]] = []
        keys = set(before) | set(after)
        if any(not isinstance(key, str) for key in keys):
            return [list(path)]
        for key in sorted(keys):
            if key not in before or key not in after:
                result.append([*path, key])
            else:
                result.extend(_changed_paths(before[key], after[key], (*path, key)))
        return result if len(result) <= MAX_POINTERS else [list(path)]
    return [list(path)]


def source_notices(index: dict[str, Any], before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for source, agents in subscriptions(index).items():
        if source not in after or source not in before:
            continue
        # Metadados do fragmento não são um acontecimento vivido pelo NPC.
        old, new = before[source], after[source]
        if not isinstance(old, dict) or not isinstance(new, dict):
            raise NpcActivationError("fonte de relação deve ser mapa")
        fields = _changed_paths(old.get("relacao", old), new.get("relacao", new))
        if not fields:
            continue
        prefix = ["relacao"] if "relacao" in new else []
        cause = {"chave": "fonte:" + source, "tipo": "fonte_alterada", "fonte": source,
                 "campos": [prefix + p for p in fields], "assinatura": digest(new)}
        for agent in sorted(agents):
            result.setdefault(agent, []).append(copy.deepcopy(cause))
    return result


def _commitments(value: Any) -> dict[str, Any]:
    import compromissos
    if value is None:
        return {}
    if not isinstance(value, dict) or len(value) > MAX_COMMITMENTS:
        raise NpcActivationError("compromissos excedem o limite do acionamento")
    result = {}
    for key, raw in value.items():
        compromissos.commitment_path(key)
        result[key] = compromissos.validate_record(raw)
    return result


def commitment_notices(index: dict[str, Any], before: dict[str, Any], after: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    active = _active(index)
    for cid in sorted(set(before) | set(after)):
        old, new = before.get(cid), after.get(cid)
        if old == new:
            continue
        involved = set((old or {}).get("envolvidos", [])) | set((new or {}).get("envolvidos", []))
        cause = {"chave": "compromisso:" + cid + ":mudanca", "tipo": "compromisso",
                 "compromisso": cid, "fase": "removido" if new is None else "alterado",
                 "assinatura": digest(new)}
        for agent in sorted(involved & set(active)):
            result.setdefault(agent, []).append(copy.deepcopy(cause))
    return result


def due_notices(index: dict[str, Any], records: dict[str, Any], now: int, receipts: dict[str, Any]) -> tuple[dict[str, list[dict[str, Any]]], dict[str, Any]]:
    result: dict[str, list[dict[str, Any]]] = {}
    updated: dict[str, Any] = {}
    active = _active(index)
    for cid, record in sorted(records.items()):
        signature = digest(record)
        previous = receipts.get(cid)
        delivered: set[str] = set()
        if previous is not None:
            if (not isinstance(previous, dict) or set(previous) != {"assinatura", "entregues"}
                    or not isinstance(previous["entregues"], list)
                    or any(not isinstance(x, str) for x in previous["entregues"])):
                raise NpcActivationError("recibo temporal inválido")
            if previous["assinatura"] == signature:
                delivered.update(previous["entregues"])
        for phase in ("inicio", "fim"):
            raw = (record.get("janela") or {}).get(phase)
            if raw is None or _minute(raw) > now:
                continue
            for agent in sorted(set(record.get("envolvidos", [])) & set(active)):
                key = phase + ":" + agent
                if key in delivered:
                    continue
                result.setdefault(agent, []).append({
                    "chave": f"compromisso:{cid}:{phase}", "tipo": "compromisso",
                    "compromisso": cid, "fase": phase, "assinatura": signature,
                })
                delivered.add(key)
        if delivered:
            updated[cid] = {"assinatura": signature, "entregues": sorted(delivered)}
    return result, updated


def _merge_notices(*groups: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for group in groups:
        for agent, causes in group.items():
            result.setdefault(agent, []).extend(causes)
    return result


def _pin(records: Iterable[dict[str, Any]]) -> set[str]:
    prefix = "resolver-pendencia-mundo:"
    return {tag[len(prefix):] for record in records for tag in record.get("tags", []) if tag.startswith(prefix)}


def _refresh_commitment_causes(state: dict[str, Any], records: dict[str, Any]) -> None:
    """Uma janela substituída vira mudança a avaliar, não prazo falso ou punição.

    A identidade da pendência permanece utilizável para conclusão/recuperação.
    Um item em resolução não pode ser preemptado pela consequência dele próprio.
    """
    control = _control(state)
    for collection in (state["pendencias"], control["adiadas"]):
        for item in collection:
            if not item.get(CAUSES) or item.get(RESOLUTION):
                continue
            updated = {}
            for raw in item[CAUSES]:
                cause = copy.deepcopy(raw)
                if cause["tipo"] == "compromisso":
                    current = records.get(cause["compromisso"])
                    if cause["assinatura"] != digest(current):
                        cause.update(chave=f"compromisso:{cause['compromisso']}:mudanca",
                                     fase="removido" if current is None else "alterado",
                                     assinatura=digest(current))
                updated[cause["chave"]] = cause
            item[CAUSES] = [updated[key] for key in sorted(updated)]
    if CONTROL in state:
        state[CONTROL] = control


def stage_notifications(repo: Path, plan: dict[str, Any] | None, records: list[dict[str, Any]]) -> bool:
    """Acopla notificações ao MESMO journal do fato que as causou; zero escrita."""
    if plan is None or not plan.get("batch"):
        return False
    outputs = plan["outputs"]
    if not any(p.startswith("estado/relacoes/") or p == STATE or p == "estado/tempo.yaml" for p in outputs):
        return False
    index = _index(repo)
    if index is None:
        return False
    changed = set(outputs) & set(subscriptions(index))
    old_sources = {p: _read(repo, p) for p in sorted(changed)}
    new_sources = {p: _read(repo, p, outputs) for p in sorted(changed)}
    old_doc = _read(repo, STATE) if (repo / STATE).is_file() else {}
    new_doc = _read(repo, STATE, outputs) if STATE in outputs else old_doc
    old_commitments = _commitments(old_doc.get("compromissos"))
    new_commitments = _commitments(new_doc.get("compromissos"))
    import mundo
    time_doc = _read(repo, "estado/tempo.yaml", outputs)
    now = mundo.parse_instant(time_doc.get("data_atual") or time_doc.get("data"), time_doc["hora_aproximada"])
    state = copy.deepcopy(_read(repo, WORLD, outputs))
    before_world = copy.deepcopy(state)
    control = _control(state)
    pinned = _pin(records)
    for item in state["pendencias"]:
        if item["id"] in pinned and item.get("tipo") == KIND:
            record = next(r for r in records if item["id"] in _pin([r]))
            item[RESOLUTION] = {"sessao": record["sessao"], "transacao": record["id"]}
    _refresh_commitment_causes(state, new_commitments)
    due, receipts = due_notices(index, new_commitments, now.minute, control["prazos"])
    notices = _merge_notices(source_notices(index, old_sources, new_sources),
                             commitment_notices(index, old_commitments, new_commitments), due)
    if not notices and CONTROL not in state:
        return False
    control = _control(state)
    control["prazos"] = receipts
    state[CONTROL] = control
    state = enqueue(state, index, notices, mundo.instant_parts(now), str(plan["batch"]), pinned=_pin(records))
    if state == before_world:
        return False
    import barreira_mundo
    outputs[WORLD] = _dump(state)
    outputs[BARRIER] = _dump(barreira_mundo.payload_from_state(state))
    ledger_path = f"sessoes/{plan['sessao']:03d}/consolidacoes.jsonl"
    if ledger_path in outputs:
        ledger = [json.loads(line) for line in outputs[ledger_path].decode("utf-8").splitlines() if line.strip()]
        for batch in ledger:
            if batch.get("id") == plan["batch"]:
                batch["arquivos_afetados"] = sorted(set(batch.get("arquivos_afetados", [])) | {WORLD, BARRIER})
        outputs[ledger_path] = ("".join(_json(x) + "\n" for x in ledger)).encode("utf-8")
    return True


def sync_deadlines(repo: Path) -> dict[str, Any]:
    """Checkpoint/recovery: prazos exatos, sem exigir um novo amanhecer."""
    index = _index(repo)
    if index is None or not (repo / STATE).is_file():
        return {"alterou": False, "novas_pendencias": []}
    import mundo
    state = mundo.load_world_state(repo)
    original = copy.deepcopy(state)
    commitments = _commitments(_read(repo, STATE).get("compromissos"))
    now, _ = mundo.load_canonical_time(repo)
    control = _control(state)
    _refresh_commitment_causes(state, commitments)
    notices, receipts = due_notices(index, commitments, now.minute, control["prazos"])
    if not notices and CONTROL not in state:
        return {"alterou": False, "novas_pendencias": []}
    control = _control(state)
    control["prazos"] = receipts
    state[CONTROL] = control
    state = enqueue(state, index, notices, mundo.instant_parts(now), "prazo")
    changed = state != original
    if changed:
        mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, state)
    old_ids = {p["id"] for p in original["pendencias"]}
    return {"alterou": changed, "novas_pendencias": [p for p in state["pendencias"] if p["id"] not in old_ids]}


def refill(repo: Path, state: dict[str, Any]) -> dict[str, Any]:
    """Reutilizada pela conclusão e pela barreira; sem controle, zero leitura."""
    if CONTROL not in state:
        return state
    index = _index(repo)
    if index is None:
        raise NpcActivationError("fila causal sem camada de agentes leves schema 2")
    return rebalance(state, index)


def changed_dependency(repo: Path, record: dict[str, Any], prior: Iterable[dict[str, Any]] = ()) -> bool:
    """Gate do writer: negativo barato; os destinatários vêm de índices explícitos."""
    deltas = [d for d in record.get("deltas", []) if d.get("visibilidade", "operacional") != "narrador"]
    if not any(str(d.get("alvo", "")).startswith("relacao:")
               or (d.get("alvo") == "estado" and str(d.get("caminho", "")).startswith("compromissos.")) for d in deltas):
        return False
    index = _index(repo)
    if index is None:
        return False
    active = set(_active(index))
    deps = subscriptions(index)
    relation_index = None
    previous = None
    for delta in deltas:
        target = str(delta.get("alvo", ""))
        if target.startswith("relacao:"):
            if relation_index is None:
                relation_index = _read(repo, "estado/relacoes/index.yaml").get("relacoes", {})
            meta = relation_index.get(target.split(":", 1)[1], {})
            if meta.get("arquivo") in deps:
                return True
        if delta.get("alvo") == "estado" and str(delta.get("caminho", "")).startswith("compromissos."):
            if previous is None:
                previous = effective_commitments(repo, prior, session=record.get("sessao"))
            cid = delta["caminho"].split(".", 1)[1]
            old = previous.get(cid) or {}
            new = delta.get("valor") or {}
            if active & (set(old.get("envolvidos", [])) | set(new.get("envolvidos", []))):
                return True
    return False


def effective_commitments(repo: Path, records: Iterable[dict[str, Any]], *, session: int | None = None) -> dict[str, Any]:
    doc = _read(repo, STATE) if (repo / STATE).is_file() else {}
    value = copy.deepcopy(doc.get("compromissos") or {})
    session = session if session is not None else (doc.get("campanha") or {}).get("sessao_atual")
    import compromissos
    for record in records:
        if session is not None and record.get("sessao", session) != session:
            continue
        for delta in record.get("deltas", []):
            if not compromissos.is_commitment_delta(delta):
                continue
            compromissos.validate_delta(delta)
            cid = delta["caminho"].split(".", 1)[1]
            if delta["op"] == "remove":
                value.pop(cid, None)
            else:
                value[cid] = copy.deepcopy(delta["valor"])
    return _commitments(value)


def deadline_reached(repo: Path, records: Iterable[dict[str, Any]], after: Any) -> bool:
    index = _index(repo)
    if index is None or not (repo / STATE).is_file():
        return False
    state = _read(repo, WORLD)
    notices, _ = due_notices(index, effective_commitments(repo, records), after.minute, _control(state)["prazos"])
    return bool(notices)


def boundary_candidates(repo: Path, index: dict[str, Any], state: dict[str, Any], start: Any, target: Any,
                        sources: list[str]) -> list[tuple[int, str, str]]:
    if index.get("schema_agentes_leves") != 2 or not (repo / STATE).is_file():
        return []
    records = []
    sources.append(STATE)
    if (repo / PENDING).is_file():
        import transacoes
        records = transacoes.load_pending(repo)
        sources.append(PENDING)
    commitments = effective_commitments(repo, records)
    receipts = _control(state)["prazos"]
    # Consultar apenas os dois instantes declarados em cada compromisso, nunca dias.
    moments = {_minute(raw) for record in commitments.values()
               for raw in (record.get("janela") or {}).values()
               if isinstance(raw, dict) and set(raw) == {"data", "hora"}}
    result: set[tuple[int, str, str]] = set()
    for instant in sorted(x for x in moments if x <= target.minute):
        due, _ = due_notices(index, commitments, instant, receipts)
        for agent in due:
            result.add((max(start.minute, instant), "agentes_leves", agent))
    return sorted(result)


def project_pending(repo: Path, pending: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Causas e fatos inteiros dirigidos; excesso vira lacuna, não texto truncado."""
    if not pending.get(CAUSES):
        return {}, []
    index = _index(repo)
    if index is None:
        raise NpcActivationError("pendência causal sem dependências instaladas")
    validate_state({"pendencias": [pending], "concluidas_recentes": []}, index)
    sources = [LIGHT_INDEX]
    loaded: dict[str, Any] = {}
    items: list[dict[str, Any]] = []
    for cause in pending[CAUSES]:
        source = cause.get("fonte", STATE)
        if source not in loaded:
            loaded[source] = _read(repo, source)
            sources.append(source)
        doc = loaded[source]
        value = doc if cause["tipo"] == "fonte_alterada" else (doc.get("compromissos") or {}).get(cause["compromisso"])
        item = {"causa": copy.deepcopy(cause), "assinatura_atual": digest(value)}
        if cause["tipo"] == "fonte_alterada":
            facts = []
            for path in cause["campos"]:
                current = value
                exists = True
                for key in path:
                    if not isinstance(current, dict) or key not in current:
                        exists = False
                        break
                    current = current[key]
                facts.append({"campo": path, "existe": exists, **({"valor": current} if exists else {})})
            item["fatos"] = facts
        else:
            item["compromisso_atual"] = value
        if digest(value) != cause["assinatura"]:
            item["fonte_alterada_desde_acionamento"] = True
            item["aprofundamento_necessario"] = {"fonte": source, "motivo": "fonte mudou fora desta notificação; revalidar o estado atual"}
        items.append(item)
    result: dict[str, Any] = {"causas": items, "autoridade": "avaliacao_do_narrador_nao_conhecimento_do_npc",
                              "regra": "Prazo não é sucesso/falha. Consultar lacunas antes de decidir; preservar agência, presença e conhecimento."}
    if len(_dump(result)) > MAX_CONTEXT_BYTES:
        # O fato inteiro sai, mas o endereço e a necessidade permanecem explícitos.
        for item in sorted(items, key=lambda x: len(_dump(x)), reverse=True):
            item.pop("fatos", None)
            item.pop("compromisso_atual", None)
            item["aprofundamento_necessario"] = {"fonte": item["causa"].get("fonte", STATE),
                                                 "campos": item["causa"].get("campos", [["compromissos", item["causa"].get("compromisso")]])}
            if len(_dump(result)) <= MAX_CONTEXT_BYTES:
                break
    # O hash engloba TODAS as causas/fontes, inclusive as que precisem de leitura
    # dirigida. Uma mudança fora da página ainda invalida o token do lote.
    result["assinatura_conjunto"] = digest(items)
    result["quantidade_causas"] = len(items)
    if len(_dump(result)) > MAX_CONTEXT_BYTES:
        result["aprofundamento_necessario"] = {
            "fonte": WORLD, "pendencia": pending["id"], "campo": CAUSES,
            "fontes_causais": list(dict.fromkeys(c.get("fonte", STATE) for c in pending[CAUSES])),
        }
        result["causas"] = []
        for item in items:
            result["causas"].append(item)
            if len(_dump(result)) > MAX_CONTEXT_BYTES:
                result["causas"].pop()
                break
    return result, list(dict.fromkeys(sources))
