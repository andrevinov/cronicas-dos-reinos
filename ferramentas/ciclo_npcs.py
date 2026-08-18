#!/usr/bin/env python3
"""Lifecycle terminal de NPCs do Mundo Vivo.

A morte é registrada no cânone normal do NPC como ``vida.estado: morto``. Esta
camada observa apenas NPCs que participam de mecanismos operacionais e converte
a morte canônica em desligamento determinístico: agenda, agentes estratégicos,
agentes leves, entradas futuras e pendências abertas.

Ausência de ``vida`` nunca ressuscita ninguém. O registro reservado em
``narrador/mundo/ciclo-npcs.yaml`` é terminal até uma futura operação explícita de
ressurreição ser implementada.
"""
from __future__ import annotations

import argparse
import os
import tempfile
from pathlib import Path
from typing import Any

import yaml

import mundo

REGISTRY = Path("narrador/mundo/ciclo-npcs.yaml")
NPC_INDEX = Path("estado/npcs/index.yaml")
STRATEGIC_INDEX = Path("narrador/agentes/index.yaml")
LIGHT_INDEX = Path("narrador/agentes-leves/index.yaml")
LIGHT_STATE = Path("narrador/agentes-leves/estado.yaml")
ENTRY_INDEX = Path("narrador/entradas/index.yaml")
ENTRY_STATE = Path("narrador/entradas/estado.yaml")
MAX_RECENT_COMPLETED = 64


class LifecycleError(ValueError):
    pass


def configured(repo: Path) -> bool:
    return (repo / REGISTRY).is_file()


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LifecycleError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise LifecycleError(f"YAML inválido em {path}: {exc}") from exc


def _atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
        handle.flush()
        os.fsync(handle.fileno())
        tmp = Path(handle.name)
    os.replace(tmp, path)


def load_registry(repo: Path) -> dict[str, Any]:
    data = _load(repo / REGISTRY)
    if not isinstance(data, dict) or data.get("schema_ciclo_npcs") != 1:
        raise LifecycleError("registro deve usar schema_ciclo_npcs: 1")
    if data.get("natureza") != "controle_reservado":
        raise LifecycleError("registro de ciclo deve ter natureza: controle_reservado")
    mortos = data.get("mortos")
    if not isinstance(mortos, dict):
        raise LifecycleError("ciclo-npcs.mortos deve ser mapa")
    for npc_id, item in mortos.items():
        if not isinstance(npc_id, str) or not npc_id:
            raise LifecycleError("id inválido em ciclo-npcs.mortos")
        if not isinstance(item, dict) or item.get("estado") != "morto":
            raise LifecycleError(f"{npc_id}: lifecycle terminal deve usar estado: morto")
        if not isinstance(item.get("fonte"), str) or not item["fonte"]:
            raise LifecycleError(f"{npc_id}: morte sem fonte canônica")
    return data


def _optional_map(repo: Path, rel: Path) -> dict[str, Any] | None:
    path = repo / rel
    if not path.is_file():
        return None
    data = _load(path)
    if not isinstance(data, dict):
        raise LifecycleError(f"{rel.as_posix()} deve conter mapa")
    return data


def _operational_ids(repo: Path) -> set[str]:
    ids: set[str] = set()
    strategic = _optional_map(repo, STRATEGIC_INDEX)
    if strategic:
        for npc_id, meta in (strategic.get("agentes") or {}).items():
            if isinstance(meta, dict) and meta.get("tipo") == "npc":
                ids.add(str(npc_id))
    light = _optional_map(repo, LIGHT_INDEX)
    if light:
        ids.update(str(value) for value in (light.get("agentes") or {}))
    entries = _optional_map(repo, ENTRY_INDEX)
    if entries:
        ids.update(str(value) for value in (entries.get("candidatos") or {}))
    return ids


def _canonical_life(repo: Path, npc_id: str, npc_index: dict[str, Any]) -> tuple[str | None, str | None]:
    entry = (npc_index.get("npcs") or {}).get(npc_id)
    if not isinstance(entry, dict) or not isinstance(entry.get("arquivo"), str):
        return None, None
    rel = Path(entry["arquivo"])
    path = repo / rel
    if not path.is_file():
        return None, None
    doc = _load(path)
    if not isinstance(doc, dict):
        return None, None
    body = doc.get("npc") if isinstance(doc.get("npc"), dict) else doc
    life = body.get("vida") if isinstance(body, dict) else None
    if not isinstance(life, dict):
        life = doc.get("vida")
    state = life.get("estado") if isinstance(life, dict) else None
    return (str(state) if isinstance(state, str) else None), rel.as_posix()


def canonical_dead(repo: Path) -> dict[str, str]:
    npc_index = _optional_map(repo, NPC_INDEX)
    if not npc_index:
        return {}
    result: dict[str, str] = {}
    for npc_id in sorted(_operational_ids(repo)):
        state, source = _canonical_life(repo, npc_id, npc_index)
        if state == "morto" and source:
            result[npc_id] = source
    return result


def dead_ids(repo: Path) -> set[str]:
    if not configured(repo):
        return set()
    return set(load_registry(repo)["mortos"])


def _next_dawn(repo: Path) -> dict[str, str]:
    now, _ = mundo.load_canonical_time(repo)
    agenda = mundo.load_agenda(repo)
    dawn = mundo._dawn_minute(agenda)
    day, clock = divmod(now.minute, 1440)
    target = mundo.WorldInstant((day + (1 if clock >= dawn else 0)) * 1440 + dawn)
    return mundo.instant_parts(target)


def _deactivate_strategic(repo: Path, dead: set[str]) -> tuple[bool, list[str]]:
    index = _optional_map(repo, STRATEGIC_INDEX)
    if not index:
        return False, []
    changed = False
    files: list[str] = []
    agents = index.get("agentes") or {}
    for npc_id in sorted(dead & set(agents)):
        meta = agents[npc_id]
        if not isinstance(meta, dict) or meta.get("tipo") != "npc":
            continue
        if meta.get("estado") != "inativo":
            meta["estado"] = "inativo"
            changed = True
        raw = meta.get("arquivo")
        if isinstance(raw, str) and (repo / raw).is_file():
            fragment = _load(repo / raw)
            if isinstance(fragment, dict) and fragment.get("estado") != "inativo":
                fragment["estado"] = "inativo"
                _atomic(repo / raw, fragment)
                files.append(raw)
    if changed:
        _atomic(repo / STRATEGIC_INDEX, index)
    return changed, files


def _deactivate_light(repo: Path, dead: set[str]) -> bool:
    index = _optional_map(repo, LIGHT_INDEX)
    state = _optional_map(repo, LIGHT_STATE)
    if not index or not state:
        return False
    changed = False
    agents = index.get("agentes") or {}
    states = state.get("agentes") or {}
    for npc_id in sorted(dead & set(agents)):
        if isinstance(agents[npc_id], dict) and agents[npc_id].get("estado") != "inativo":
            agents[npc_id]["estado"] = "inativo"
            changed = True
        if isinstance(states.get(npc_id), dict) and states[npc_id].get("estado") != "inativo":
            states[npc_id]["estado"] = "inativo"
            changed = True
    if changed:
        _atomic(repo / LIGHT_INDEX, index)
        _atomic(repo / LIGHT_STATE, state)
    return changed


def _invalidate_entries(repo: Path, dead: set[str]) -> list[str]:
    index = _optional_map(repo, ENTRY_INDEX)
    state = _optional_map(repo, ENTRY_STATE)
    if not index or not state:
        return []
    candidates = index.get("candidatos") or {}
    states = state.get("candidatos") or {}
    changed: list[str] = []
    now, _ = mundo.load_canonical_time(repo)
    for npc_id in sorted(dead & set(candidates)):
        item = states.get(npc_id)
        if not isinstance(item, dict) or item.get("estado") != "latente":
            continue
        item["estado"] = "inviavel"
        item["antecipado"] = False
        item["proxima_avaliacao"] = None
        history = item.setdefault("historico_recente", [])
        if isinstance(history, list):
            history.append({
                "acao": "inviabilizar_por_morte",
                "em": mundo.instant_parts(now),
                "origem": "ciclo-npcs",
                "nota": "Morte canônica anterior à entrada em cena; não agendar aparição.",
            })
            item["historico_recente"] = history[-24:]
        changed.append(npc_id)
    if changed:
        anticipated = any(
            isinstance(item, dict) and item.get("antecipado") and item.get("estado") == "latente"
            for item in states.values()
        )
        if not anticipated:
            ordered = sorted(candidates, key=lambda cid: candidates[cid]["ordem"])
            nxt = next((cid for cid in ordered if states[cid].get("estado") == "latente"), None)
            if nxt and states[nxt].get("proxima_avaliacao") is None:
                states[nxt]["proxima_avaliacao"] = _next_dawn(repo)
        _atomic(repo / ENTRY_STATE, state)
    return changed


def _prune_agenda(repo: Path, dead: set[str]) -> dict[str, int]:
    agenda = _optional_map(repo, mundo.AGENDA_PATH)
    if not agenda:
        return {"reavaliacoes": 0, "agendamentos": 0}
    recurrences = agenda.get("reavaliacoes") or {}
    removed_recurrences = 0
    for npc_id in sorted(dead & set(recurrences)):
        recurrences.pop(npc_id, None)
        removed_recurrences += 1

    schedules = list(agenda.get("agendamentos") or [])
    kept = []
    removed_schedules = 0
    changed_affected = False
    for item in schedules:
        actor = item.get("agente") if isinstance(item, dict) else None
        if actor in dead:
            removed_schedules += 1
            continue
        if isinstance(item, dict) and isinstance(item.get("agentes_afetados"), list):
            filtered = [value for value in item["agentes_afetados"] if value not in dead]
            if filtered != item["agentes_afetados"]:
                item = dict(item)
                item["agentes_afetados"] = filtered
                changed_affected = True
        kept.append(item)
    if removed_recurrences or removed_schedules or changed_affected:
        agenda["agendamentos"] = kept
        _atomic(repo / mundo.AGENDA_PATH, agenda)
    return {"reavaliacoes": removed_recurrences, "agendamentos": removed_schedules}


def _cancel_pending(repo: Path, dead: set[str]) -> list[dict[str, Any]]:
    path = repo / mundo.WORLD_STATE_PATH
    if not path.is_file():
        return []
    state = mundo.load_world_state(repo)
    kept = []
    cancelled = []
    for item in state.get("pendencias") or []:
        actor = item.get("agente") or item.get("agente_leve") or item.get("entrada")
        if actor in dead:
            completed = {
                "id": item["id"],
                "tipo": item["tipo"],
                "disparado_em": item["disparado_em"],
                "cancelada": "ator_morto",
                "nota": f"Pendência cancelada automaticamente: {actor} está morto no cânone.",
            }
            if item.get("agente"):
                completed["agente"] = item["agente"]
            if item.get("agente_leve"):
                completed["agente_leve"] = item["agente_leve"]
            if item.get("entrada"):
                completed["entrada"] = item["entrada"]
            cancelled.append(completed)
            continue
        if isinstance(item.get("agentes_afetados"), list):
            filtered = [value for value in item["agentes_afetados"] if value not in dead]
            if filtered != item["agentes_afetados"]:
                item = dict(item)
                item["agentes_afetados"] = filtered
        kept.append(item)
    if cancelled or kept != state.get("pendencias"):
        state["pendencias"] = kept
        state["concluidas_recentes"].extend(cancelled)
        state["concluidas_recentes"] = state["concluidas_recentes"][-MAX_RECENT_COMPLETED:]
        mundo._atomic_write_yaml(path, state)
    return cancelled


def sync(repo: Path) -> dict[str, Any]:
    registry = load_registry(repo)
    detected = canonical_dead(repo)
    new_dead: list[str] = []
    for npc_id, source in detected.items():
        if npc_id not in registry["mortos"]:
            registry["mortos"][npc_id] = {"estado": "morto", "fonte": source}
            new_dead.append(npc_id)
    if new_dead:
        _atomic(repo / REGISTRY, registry)

    dead = set(registry["mortos"])
    strategic_changed, strategic_files = _deactivate_strategic(repo, dead)
    light_changed = _deactivate_light(repo, dead)
    invalid_entries = _invalidate_entries(repo, dead)
    pruned = _prune_agenda(repo, dead)
    cancelled = _cancel_pending(repo, dead)
    return {
        "ok": True,
        "mortos": sorted(dead),
        "novos_mortos": sorted(new_dead),
        "agentes_estrategicos_desativados": strategic_changed,
        "fragmentos_estrategicos_atualizados": strategic_files,
        "agentes_leves_desativados": light_changed,
        "entradas_inviabilizadas": invalid_entries,
        "agenda_removida": pruned,
        "pendencias_canceladas": [item["id"] for item in cancelled],
        "fontes_lidas": [REGISTRY.as_posix(), NPC_INDEX.as_posix()],
    }


def status(repo: Path) -> dict[str, Any]:
    registry = load_registry(repo)
    return {
        "mortos": sorted(registry["mortos"]),
        "quantidade": len(registry["mortos"]),
        "fontes_lidas": [REGISTRY.as_posix()],
    }


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        registry = load_registry(repo)
        npc_index = _optional_map(repo, NPC_INDEX) or {}
        for npc_id, item in registry["mortos"].items():
            state, source = _canonical_life(repo, npc_id, npc_index)
            if state != "morto":
                errors.append(f"{npc_id}: lifecycle diz morto, mas o cânone do NPC não registra vida.estado=morto")
            elif source != item["fonte"]:
                errors.append(f"{npc_id}: fonte de morte diverge do NPC canônico")
    except LifecycleError as exc:
        errors.append(str(exc))
    return {"ok": not errors, "erros": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("sincronizar")
    sub.add_parser("validar")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "status":
            result = status(repo)
        elif args.cmd == "sincronizar":
            result = sync(repo)
        else:
            result = validate_repo(repo)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0 if result.get("ok", True) else 1
    except (LifecycleError, mundo.WorldEngineError) as exc:
        print(f"erro: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
