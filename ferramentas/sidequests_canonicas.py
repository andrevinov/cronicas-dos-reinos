#!/usr/bin/env python3
"""Task 32 engine + Task 33 fragmented NPC quest catalog routing.

Task 32 semantics remain in ``_sidequests_canonicas_task32.py``. Task 33 moves
opaque refs out of the opportunities index into one tiny router per recurring
quest-giver. Desde a Task46, esse catálogo é legado frio: estas portas continuam
funcionando quando chamadas explicitamente, mas encontros ao vivo não as acordam.
"""
from __future__ import annotations

import copy
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import _sidequests_canonicas_task32 as _core
import oportunidades

for _name in dir(_core):
    if not _name.startswith("__"):
        globals()[_name] = getattr(_core, _name)

ROUTERS_DIR = Path("narrador/sidequests-canonicas/roteadores")
FRAGMENTED_ROUTING = "fragmentado_por_npc_task33"
FRAGMENTED_ROUTING_COLD = "fragmentado_por_npc_task33_legado_frio"
ROUTER_FRAGMENT_SCHEMA = 1
NPC_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,95}$")

_BASE_ROUTER = _core._router
_BASE_EVALUATE_FOR_NPC = _core.evaluate_for_npc
_BASE_OFFER = _core.offer
_BASE_EFFECTS = _core.effects_for_mission
_BASE_CHECK = _core.check


def _router(index: dict[str, Any]) -> dict[str, Any]:
    raw = index.get(ROUTER_KEY)
    if not isinstance(raw, dict):
        raise CanonicalSidequestError("índice de oportunidades não declara sidequests_canonicas")
    if isinstance(raw.get("por_npc"), dict):
        return _BASE_ROUTER(index)
    routing = raw.get("roteamento")
    if (
        raw.get("schema_sidequests_canonicas") != 1
        or raw.get("engine") != ENGINE_ID
        or raw.get("detalhes_somente_apos_gate") is not True
        or raw.get("scheduler") != "proibido"
        or raw.get("rng") != "proibido"
        or routing not in {FRAGMENTED_ROUTING, FRAGMENTED_ROUTING_COLD}
    ):
        raise CanonicalSidequestError("roteador fragmentado de sidequests canônicas inválido")
    allowed = {
        "schema_sidequests_canonicas", "engine", "detalhes_somente_apos_gate",
        "scheduler", "rng", "roteamento", "estatuto", "origem_operacional",
    }
    extra = set(raw) - allowed
    if extra:
        raise CanonicalSidequestError(
            "roteador fragmentado possui campos desconhecidos: " + ", ".join(sorted(extra))
        )
    if routing == FRAGMENTED_ROUTING_COLD:
        if raw.get("estatuto") != "legado_frio_task46" or raw.get("origem_operacional") is not False:
            raise CanonicalSidequestError(
                "roteador Task33 legado frio precisa declarar estatuto e origem_operacional=false"
            )
    elif raw.get("estatuto") is not None or raw.get("origem_operacional") is not None:
        raise CanonicalSidequestError(
            "metadados Task46 só são aceitos no roteamento legado frio"
        )
    if not isinstance(index.get("perfis"), dict):
        raise CanonicalSidequestError("índice sem perfis para roteamento Task33")
    return raw


def _route_path(npc_id: str) -> Path:
    if not isinstance(npc_id, str) or not NPC_ID_RE.fullmatch(npc_id):
        raise CanonicalSidequestError(f"npc_id inválido para catálogo: {npc_id!r}")
    return ROUTERS_DIR / f"{npc_id}.yaml"


def _normalized_refs(npc_id: str, refs: Any) -> list[dict[str, Any]]:
    refs = _list(refs, f"roteador.{npc_id}.refs")
    if len(refs) > MAX_REFS_PER_NPC:
        raise CanonicalSidequestError(f"{npc_id}: máximo de {MAX_REFS_PER_NPC} referências")
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for pos, raw_ref in enumerate(refs):
        ref = _map(raw_ref, f"{npc_id}[{pos}]")
        if set(ref) != {"id", "gate", "prioridade"}:
            raise CanonicalSidequestError(f"{npc_id}[{pos}] deve conter somente id, gate e prioridade")
        qid = _quest_id(ref["id"], f"{npc_id}[{pos}].id")
        if qid in seen:
            raise CanonicalSidequestError(f"sidequest duplicada no roteador {npc_id}: {qid}")
        seen.add(qid)
        _repo_path(Path("/repo"), ref["gate"], GATES_DIR)
        priority = _integer(ref["prioridade"], f"{qid}.prioridade", 0, 100)
        result.append({"id": qid, "gate": str(ref["gate"]), "prioridade": priority, "npc_id": npc_id})
    return sorted(result, key=lambda item: (-item["prioridade"], item["id"]))


def _load_fragmented_route(repo: Path, index: dict[str, Any], npc_id: str) -> tuple[list[dict[str, Any]], list[str]]:
    router = _router(index)
    if isinstance(router.get("por_npc"), dict):
        return _core.route_for_npc(index, npc_id), []
    profiles = index.get("perfis") or {}
    if npc_id not in profiles:
        return [], []
    rel = _route_path(npc_id)
    data = _map(_load(repo / rel), rel.as_posix())
    if (
        data.get("schema_roteador_sidequests_canonicas") != ROUTER_FRAGMENT_SCHEMA
        or data.get("natureza") != "reservado"
        or data.get("npc_id") != npc_id
        or set(data) != {"schema_roteador_sidequests_canonicas", "natureza", "npc_id", "refs"}
    ):
        raise CanonicalSidequestError(f"roteador fragmentado inválido: {rel}")
    return _normalized_refs(npc_id, data["refs"]), [rel.as_posix()]


def route_for_npc(index: dict[str, Any], npc_id: str, repo: Path | None = None) -> list[dict[str, Any]]:
    router = _router(index)
    if isinstance(router.get("por_npc"), dict):
        return _core.route_for_npc(index, npc_id)
    if npc_id not in (index.get("perfis") or {}):
        return []
    if repo is None:
        raise CanonicalSidequestError("roteamento fragmentado exige raiz do repositório para quest-giver catalogado")
    refs, _ = _load_fragmented_route(repo, index, npc_id)
    return refs


def route_for_npc_with_sources(repo: Path, index: dict[str, Any], npc_id: str) -> tuple[list[dict[str, Any]], list[str]]:
    return _load_fragmented_route(repo, index, npc_id)


def quest_giver_ids(index: dict[str, Any], repo: Path | None = None) -> set[str]:
    router = _router(index)
    if isinstance(router.get("por_npc"), dict):
        return set(router["por_npc"])
    profiles = set((index.get("perfis") or {}))
    if repo is None:
        return profiles
    return {npc_id for npc_id in profiles if (repo / _route_path(npc_id)).is_file()}


def catalog_refs(repo: Path, index: dict[str, Any] | None = None) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    if index is None:
        index = oportunidades.load_index(repo)
    _router(index)
    mapping: dict[str, list[dict[str, Any]]] = {}
    sources: list[str] = []
    seen: set[str] = set()
    for npc_id in sorted(quest_giver_ids(index, repo)):
        refs, route_sources = _load_fragmented_route(repo, index, npc_id)
        for ref in refs:
            if ref["id"] in seen:
                raise CanonicalSidequestError(f"sidequest roteada por mais de um NPC: {ref['id']}")
            seen.add(ref["id"])
        mapping[npc_id] = refs
        sources.extend(route_sources)
    return mapping, list(dict.fromkeys(sources))


def _synthetic_inline_index(index: dict[str, Any], mapping: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    synthetic = copy.deepcopy(index)
    raw = synthetic[ROUTER_KEY]
    raw.pop("roteamento", None)
    raw.pop("estatuto", None)
    raw.pop("origem_operacional", None)
    raw["por_npc"] = {
        npc_id: [{key: ref[key] for key in ("id", "gate", "prioridade")} for ref in refs]
        for npc_id, refs in mapping.items()
    }
    return synthetic


@contextmanager
def _patched_index(repo: Path, index: dict[str, Any], mapping: dict[str, list[dict[str, Any]]]) -> Iterator[None]:
    synthetic = _synthetic_inline_index(index, mapping)
    original = oportunidades.load_index
    def loader(requested_repo: Path) -> dict[str, Any]:
        if Path(requested_repo).resolve() == repo.resolve():
            return copy.deepcopy(synthetic)
        return original(requested_repo)
    oportunidades.load_index = loader
    try:
        yield
    finally:
        oportunidades.load_index = original


def evaluate_for_npc(repo: Path, npc_id: str, *, local: str | None = None, now: mundo.WorldInstant | None = None, diagnostics: bool = False) -> dict[str, Any]:
    index = oportunidades.load_index(repo)
    router = _router(index)
    if isinstance(router.get("por_npc"), dict):
        return _BASE_EVALUATE_FOR_NPC(repo, npc_id, local=local, now=now, diagnostics=diagnostics)
    refs, route_sources = _load_fragmented_route(repo, index, npc_id)
    if not refs:
        return {
            "ok": True, "resultado": "nenhuma_sidequest_canonica_roteada", "npc_id": npc_id,
            "gates_avaliados": 0, "detalhes_lidos": 0,
            "fontes_lidas": [oportunidades.INDEX.as_posix()],
        }
    with _patched_index(repo, index, {npc_id: refs}):
        result = _BASE_EVALUATE_FOR_NPC(repo, npc_id, local=local, now=now, diagnostics=diagnostics)
    result["fontes_lidas"] = list(dict.fromkeys([*route_sources, *(result.get("fontes_lidas") or [])]))
    return result


def _fragment_ref(repo: Path, index: dict[str, Any], npc_id: str, quest_id: str) -> tuple[dict[str, Any], list[str]]:
    qid = _quest_id(quest_id)
    refs, sources = _load_fragmented_route(repo, index, npc_id)
    for ref in refs:
        if ref["id"] == qid:
            return ref, sources
    raise CanonicalSidequestError(f"{qid}: não roteada para {npc_id}")


def offer(repo: Path, quest_id: str, *, npc_id: str, local: str | None = None, now: mundo.WorldInstant | None = None) -> dict[str, Any]:
    index = oportunidades.load_index(repo)
    router = _router(index)
    if isinstance(router.get("por_npc"), dict):
        return _BASE_OFFER(repo, quest_id, npc_id=npc_id, local=local, now=now)
    ref, route_sources = _fragment_ref(repo, index, npc_id, quest_id)
    with _patched_index(repo, index, {npc_id: [ref]}):
        result = _BASE_OFFER(repo, quest_id, npc_id=npc_id, local=local, now=now)
    result["fontes_lidas"] = list(dict.fromkeys([*route_sources, *(result.get("fontes_lidas") or [])]))
    return result


def effects_for_mission(repo: Path, mission_id_value: str) -> dict[str, Any]:
    index = oportunidades.load_index(repo)
    router = _router(index)
    if isinstance(router.get("por_npc"), dict):
        return _BASE_EFFECTS(repo, mission_id_value)
    state = oportunidades.load_state(repo, index)
    mission = state.get("missoes", {}).get(mission_id_value)
    if not isinstance(mission, dict):
        raise CanonicalSidequestError(f"sidequest inexistente: {mission_id_value}")
    npc_id = str(mission.get("npc_id") or "")
    quest_id = str(mission.get("quest_id") or "")
    ref, route_sources = _fragment_ref(repo, index, npc_id, quest_id)
    with _patched_index(repo, index, {npc_id: [ref]}):
        result = _BASE_EFFECTS(repo, mission_id_value)
    result["fontes_lidas"] = list(dict.fromkeys([*route_sources, *(result.get("fontes_lidas") or [])]))
    return result


def check(repo: Path) -> dict[str, Any]:
    index = oportunidades.load_index(repo)
    router = _router(index)
    if isinstance(router.get("por_npc"), dict):
        return _BASE_CHECK(repo)
    mapping, sources = catalog_refs(repo, index)
    with _patched_index(repo, index, mapping):
        result = _BASE_CHECK(repo)
    result["roteadores_fragmentados"] = len(mapping)
    result["fontes_roteadores"] = len(sources)
    result["estatuto_task46"] = (
        "legado_frio" if router.get("roteamento") == FRAGMENTED_ROUTING_COLD else "compatibilidade"
    )
    return result


_core._router = _router
_core.evaluate_for_npc = evaluate_for_npc
_core.offer = offer
_core.effects_for_mission = effects_for_mission
_core.check = check
main = _core.main

if __name__ == "__main__":
    raise SystemExit(main())
