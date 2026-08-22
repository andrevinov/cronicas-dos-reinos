#!/usr/bin/env python3
"""Agentes recorrentes leves do Mundo Vivo.

A camada existe para NPCs que continuam vivendo fora de cena, mas cuja rotina é
o padrão. Checkpoints de amanhecer fazem apenas uma pré-seleção determinística;
fragmentos só são abertos quando uma pendência concreta precisa ser resolvida.

Schema 2 adiciona cache negativo causal: depois de uma avaliação explícita concluir
que nada extraordinário mudou, a próxima cadência pode ser compactada sem abrir o
fragmento do agente se as fontes canônicas declaradas e a versão do perfil forem
idênticas. Qualquer divergência invalida o cache e restaura a avaliação normal.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import mundo

INDEX = Path("narrador/agentes-leves/index.yaml")
STATE = Path("narrador/agentes-leves/estado.yaml")
DIR = Path("narrador/agentes-leves")
CAUSAL_ROOT = Path("estado/relacoes")
VALID_STATES = {"ativo", "inativo"}
PROFILE = "recorrente_leve"
SUPPORTED_SCHEMAS = {1, 2}
MAX_CAUSAL_SOURCES = 2
MAX_CAUSAL_SOURCE_BYTES = 32768
CACHE_SIGNATURE_HEX_LEN = 64
PROFILE_BLOB_HEX_LEN = 40
NOOP_RESULT = "rotina_sem_mudanca"


class LightAgentError(ValueError):
    """Erro de contrato da camada de agentes leves."""


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LightAgentError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise LightAgentError(f"YAML inválido em {path}: {exc}") from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LightAgentError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise LightAgentError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LightAgentError(f"{label} deve ser texto não vazio")
    return value.strip()


def _hex(value: Any, length: int, label: str) -> str:
    text = _text(value, label).lower()
    if len(text) != length or any(ch not in "0123456789abcdef" for ch in text):
        raise LightAgentError(f"{label} deve ser hexadecimal de {length} caracteres")
    return text


def _normalize(value: str) -> str:
    raw = unicodedata.normalize("NFKD", str(value))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return " ".join(raw.split()).lower()


def _repo_path(repo: Path, raw: str, *, prefix: Path | None = None) -> Path:
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        raise LightAgentError(f"caminho fora do repositório: {raw}")
    if prefix is not None:
        try:
            rel.relative_to(prefix)
        except ValueError as exc:
            raise LightAgentError(
                f"caminho {raw} deve permanecer sob {prefix.as_posix()}"
            ) from exc
    return repo / rel


def _git_blob_sha(path: Path) -> str:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise LightAgentError(f"não foi possível ler perfil: {path}") from exc
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _schema(index: dict[str, Any]) -> int:
    value = index.get("schema_agentes_leves")
    if value not in SUPPORTED_SCHEMAS:
        raise LightAgentError("índice deve usar schema_agentes_leves: 1 ou 2")
    return int(value)


def _causal_sources(meta: dict[str, Any], agent_id: str) -> list[str]:
    raw = _list(meta.get("fontes_causais"), f"agentes.{agent_id}.fontes_causais")
    if not 1 <= len(raw) <= MAX_CAUSAL_SOURCES:
        raise LightAgentError(
            f"{agent_id}.fontes_causais deve ter entre 1 e {MAX_CAUSAL_SOURCES} fontes"
        )
    result: list[str] = []
    seen: set[str] = set()
    for i, value in enumerate(raw):
        source = _text(value, f"agentes.{agent_id}.fontes_causais[{i}]")
        _repo_path(Path("."), source, prefix=CAUSAL_ROOT)
        if source in seen:
            raise LightAgentError(f"{agent_id}.fontes_causais contém duplicata: {source}")
        seen.add(source)
        result.append(source)
    return result


def load_index(repo: Path) -> dict[str, Any]:
    data = _map(_load_yaml(repo / INDEX), INDEX.as_posix())
    schema = _schema(data)
    if data.get("natureza") != "reservado":
        raise LightAgentError("índice de agentes leves deve ter natureza: reservado")

    budget = _map(data.get("orcamento"), "orcamento")
    max_new = budget.get("max_novas_por_checkpoint")
    max_open = budget.get("max_pendencias_abertas")
    if not isinstance(max_new, int) or isinstance(max_new, bool) or max_new < 1:
        raise LightAgentError("orcamento.max_novas_por_checkpoint deve ser inteiro >= 1")
    if not isinstance(max_open, int) or isinstance(max_open, bool) or max_open < 1:
        raise LightAgentError("orcamento.max_pendencias_abertas deve ser inteiro >= 1")
    if max_new > max_open:
        raise LightAgentError("max_novas_por_checkpoint não pode exceder max_pendencias_abertas")
    if budget.get("ordenacao") != "mais_atrasado_prioridade_id":
        raise LightAgentError("orcamento.ordenacao deve ser mais_atrasado_prioridade_id")
    if schema == 2:
        max_checks = budget.get("max_checks_cache_negativo_por_checkpoint")
        if max_checks != 1:
            raise LightAgentError(
                "schema 2 exige orcamento.max_checks_cache_negativo_por_checkpoint: 1"
            )

    agents = _map(data.get("agentes"), "agentes")
    if not agents:
        raise LightAgentError("índice de agentes leves não pode ser vazio")
    files: set[str] = set()
    for agent_id, raw in agents.items():
        agent_id = _text(agent_id, "id de agente leve")
        meta = _map(raw, f"agentes.{agent_id}")
        _text(meta.get("nome"), f"agentes.{agent_id}.nome")
        if meta.get("perfil_operacional") != PROFILE:
            raise LightAgentError(f"{agent_id}.perfil_operacional deve ser {PROFILE}")
        state = _text(meta.get("estado"), f"agentes.{agent_id}.estado")
        if state not in VALID_STATES:
            raise LightAgentError(f"estado inválido para {agent_id}: {state}")
        priority = meta.get("prioridade")
        if not isinstance(priority, int) or isinstance(priority, bool) or not 0 <= priority <= 9:
            raise LightAgentError(f"{agent_id}.prioridade deve ser inteiro entre 0 e 9")
        interval = meta.get("intervalo_dias")
        if not isinstance(interval, int) or isinstance(interval, bool) or interval < 1:
            raise LightAgentError(f"{agent_id}.intervalo_dias deve ser inteiro >= 1")
        start = _map(meta.get("inicio"), f"agentes.{agent_id}.inicio")
        mundo.parse_instant(
            _text(start.get("data"), f"agentes.{agent_id}.inicio.data"),
            _text(start.get("hora"), f"agentes.{agent_id}.inicio.hora"),
        )
        raw_path = _text(meta.get("arquivo"), f"agentes.{agent_id}.arquivo")
        _repo_path(repo, raw_path, prefix=DIR)
        if raw_path in files:
            raise LightAgentError(f"arquivo de agente leve duplicado: {raw_path}")
        files.add(raw_path)
        if schema == 2:
            _causal_sources(meta, agent_id)
            _hex(meta.get("perfil_blob_git"), PROFILE_BLOB_HEX_LEN, f"{agent_id}.perfil_blob_git")
    return data


def _validate_cache(cache: Any, agent_id: str) -> None:
    if cache is None:
        return
    item = _map(cache, f"{agent_id}.cache_negativo")
    _hex(
        item.get("assinatura_causal"),
        CACHE_SIGNATURE_HEX_LEN,
        f"{agent_id}.cache_negativo.assinatura_causal",
    )
    _text(item.get("pendencia_origem"), f"{agent_id}.cache_negativo.pendencia_origem")
    confirmed = _map(item.get("confirmado_em"), f"{agent_id}.cache_negativo.confirmado_em")
    mundo.parse_instant(
        _text(confirmed.get("data"), f"{agent_id}.cache_negativo.confirmado_em.data"),
        _text(confirmed.get("hora"), f"{agent_id}.cache_negativo.confirmado_em.hora"),
    )
    hits = item.get("acertos_compactados")
    if not isinstance(hits, int) or isinstance(hits, bool) or hits < 0:
        raise LightAgentError(f"{agent_id}.cache_negativo.acertos_compactados deve ser inteiro >= 0")
    last = item.get("ultima_compactacao")
    if last is not None:
        last_map = _map(last, f"{agent_id}.cache_negativo.ultima_compactacao")
        mundo.parse_instant(
            _text(last_map.get("data"), f"{agent_id}.cache_negativo.ultima_compactacao.data"),
            _text(last_map.get("hora"), f"{agent_id}.cache_negativo.ultima_compactacao.hora"),
        )


def load_state(repo: Path, index: dict[str, Any] | None = None) -> dict[str, Any]:
    index = index or load_index(repo)
    index_schema = _schema(index)
    data = _map(_load_yaml(repo / STATE), STATE.as_posix())
    state_schema = data.get("schema_estado_agentes_leves")
    if state_schema != index_schema:
        raise LightAgentError(
            f"estado deve usar schema_estado_agentes_leves: {index_schema} para acompanhar o índice"
        )
    if data.get("natureza") != "controle_reservado":
        raise LightAgentError("estado de agentes leves deve ter natureza: controle_reservado")
    states = _map(data.get("agentes"), "estado.agentes")
    expected = set(index["agentes"])
    actual = set(states)
    if expected != actual:
        raise LightAgentError(
            f"estado/índice divergem; ausentes={sorted(expected-actual)}, extras={sorted(actual-expected)}"
        )
    for agent_id, raw in states.items():
        item = _map(raw, f"estado.agentes.{agent_id}")
        if item.get("estado") != index["agentes"][agent_id]["estado"]:
            raise LightAgentError(f"{agent_id}: estado diverge do índice")
        next_eval = _map(item.get("proxima_avaliacao"), f"{agent_id}.proxima_avaliacao")
        mundo.parse_instant(
            _text(next_eval.get("data"), f"{agent_id}.proxima_avaliacao.data"),
            _text(next_eval.get("hora"), f"{agent_id}.proxima_avaliacao.hora"),
        )
        if state_schema == 2:
            _validate_cache(item.get("cache_negativo"), agent_id)
    return data


def _validate_evidence(
    repo: Path, source: str, evidence: str, label: str, *, check_sources: bool
) -> None:
    if not check_sources:
        return
    path = _repo_path(repo, source)
    if not path.is_file():
        raise LightAgentError(f"{label}: fonte canônica inexistente: {source}")
    haystack = " ".join(path.read_text(encoding="utf-8").split())
    needle = " ".join(evidence.split())
    if needle not in haystack:
        raise LightAgentError(f"{label}: evidência não localizada em {source}")


def load_fragment(
    repo: Path,
    agent_id: str,
    meta: dict[str, Any],
    *,
    check_sources: bool = False,
) -> dict[str, Any]:
    raw_path = _text(meta.get("arquivo"), f"agentes.{agent_id}.arquivo")
    path = _repo_path(repo, raw_path, prefix=DIR)
    data = _map(_load_yaml(path), raw_path)
    if data.get("schema_agente_leve") != 1:
        raise LightAgentError(f"{agent_id}: schema_agente_leve deve ser 1")
    if data.get("natureza") != "reservado":
        raise LightAgentError(f"{agent_id}: natureza deve ser reservado")
    if data.get("id") != agent_id or data.get("nome") != meta.get("nome"):
        raise LightAgentError(f"{agent_id}: id/nome divergem do índice")
    if data.get("perfil_operacional") != PROFILE:
        raise LightAgentError(f"{agent_id}: perfil_operacional deve ser {PROFILE}")

    sources = _list(data.get("fontes_canonicas"), f"{agent_id}.fontes_canonicas")
    source_list: list[str] = []
    source_set: set[str] = set()
    for i, source in enumerate(sources):
        normalized = _text(source, f"{agent_id}.fontes_canonicas[{i}]")
        source_list.append(normalized)
        source_set.add(normalized)

    for field in ("rotina_padrao", "objetivo_atual"):
        item = _map(data.get(field), f"{agent_id}.{field}")
        _text(item.get("descricao"), f"{agent_id}.{field}.descricao")
        source = _text(item.get("fonte"), f"{agent_id}.{field}.fonte")
        evidence = _text(item.get("evidencia"), f"{agent_id}.{field}.evidencia")
        if source not in source_set:
            raise LightAgentError(f"{agent_id}.{field}: fonte não declarada: {source}")
        _validate_evidence(repo, source, evidence, f"{agent_id}.{field}", check_sources=check_sources)

    initiatives = _list(data.get("iniciativas_possiveis"), f"{agent_id}.iniciativas_possiveis")
    for i, raw in enumerate(initiatives):
        item = _map(raw, f"{agent_id}.iniciativas_possiveis[{i}]")
        _text(item.get("descricao"), f"{agent_id}.iniciativas_possiveis[{i}].descricao")
        source = _text(item.get("fonte"), f"{agent_id}.iniciativas_possiveis[{i}].fonte")
        evidence = _text(item.get("evidencia"), f"{agent_id}.iniciativas_possiveis[{i}].evidencia")
        if source not in source_set:
            raise LightAgentError(
                f"{agent_id}.iniciativas_possiveis[{i}]: fonte não declarada: {source}"
            )
        _validate_evidence(
            repo,
            source,
            evidence,
            f"{agent_id}.iniciativas_possiveis[{i}]",
            check_sources=check_sources,
        )
    _text(data.get("regra_de_reavaliacao"), f"{agent_id}.regra_de_reavaliacao")

    if meta.get("fontes_causais") is not None:
        expected = _causal_sources(meta, agent_id)
        if source_list != expected:
            raise LightAgentError(
                f"{agent_id}: fontes_causais do índice devem coincidir exatamente com fontes_canonicas do perfil"
            )
    return data


def _causal_bytes(repo: Path, source: str) -> bytes:
    path = _repo_path(repo, source, prefix=CAUSAL_ROOT)
    try:
        data = path.read_bytes()
    except FileNotFoundError as exc:
        raise LightAgentError(f"fonte causal inexistente: {source}") from exc
    except OSError as exc:
        raise LightAgentError(f"não foi possível ler fonte causal: {source}") from exc
    if len(data) > MAX_CAUSAL_SOURCE_BYTES:
        raise LightAgentError(
            f"fonte causal excede {MAX_CAUSAL_SOURCE_BYTES} bytes: {source}"
        )
    return data


def causal_signature(
    repo: Path, agent_id: str, meta: dict[str, Any]
) -> tuple[str, list[str]]:
    """Assina apenas fontes causais compactas; nunca abre o perfil narrativo."""
    sources = _causal_sources(meta, agent_id)
    rows = []
    for source in sources:
        data = _causal_bytes(repo, source)
        rows.append({"fonte": source, "sha256": hashlib.sha256(data).hexdigest()})
    payload = {
        "agente": agent_id,
        "perfil_blob_git": _hex(
            meta.get("perfil_blob_git"), PROFILE_BLOB_HEX_LEN, f"{agent_id}.perfil_blob_git"
        ),
        "fontes": rows,
    }
    rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest(), sources


def resolve_agent(index: dict[str, Any], query: str) -> tuple[str, dict[str, Any]]:
    if query in index["agentes"]:
        return query, index["agentes"][query]
    wanted = _normalize(query)
    matches = []
    for agent_id, meta in index["agentes"].items():
        candidates = {_normalize(agent_id), _normalize(meta["nome"])}
        if wanted in candidates or any(wanted and wanted in value for value in candidates):
            matches.append((agent_id, meta))
    if not matches:
        raise LightAgentError(f"agente leve não encontrado: {query}")
    if len(matches) > 1:
        raise LightAgentError(
            f"consulta ambígua para {query!r}: {', '.join(item[0] for item in matches)}"
        )
    return matches[0]


def load_agent(repo: Path, query: str) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    agent_id, meta = resolve_agent(index, query)
    fragment = load_fragment(repo, agent_id, meta, check_sources=False)
    return {
        "agente_leve_id": agent_id,
        "proxima_avaliacao": state["agentes"][agent_id]["proxima_avaliacao"],
        "cache_negativo": state["agentes"][agent_id].get("cache_negativo"),
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), meta["arquivo"]],
        "resultado": fragment,
    }


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        index = load_index(repo)
        load_state(repo, index)
        schema = _schema(index)
        for agent_id, meta in index["agentes"].items():
            fragment = load_fragment(repo, agent_id, meta, check_sources=True)
            if schema == 2:
                raw_path = _text(meta.get("arquivo"), f"agentes.{agent_id}.arquivo")
                profile_path = _repo_path(repo, raw_path, prefix=DIR)
                expected_blob = _hex(
                    meta.get("perfil_blob_git"),
                    PROFILE_BLOB_HEX_LEN,
                    f"{agent_id}.perfil_blob_git",
                )
                actual_blob = _git_blob_sha(profile_path)
                if actual_blob != expected_blob:
                    raise LightAgentError(
                        f"{agent_id}: perfil_blob_git desatualizado; esperado {actual_blob}"
                    )
                for source in _causal_sources(meta, agent_id):
                    _causal_bytes(repo, source)
                if fragment["fontes_canonicas"] != meta["fontes_causais"]:
                    raise LightAgentError(
                        f"{agent_id}: fontes causais divergem do perfil narrativo"
                    )
    except LightAgentError as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "quantidade": len(index["agentes"]) if "index" in locals() else 0,
        "schema": index.get("schema_agentes_leves") if "index" in locals() else None,
        "erros": errors,
    }


def _pending_id(agent_id: str, due: mundo.WorldInstant) -> str:
    raw = f"reavaliar_agente_leve|{agent_id}|{due.minute}".encode("utf-8")
    return "mundo-" + hashlib.sha256(raw).hexdigest()[:16]


def _light_pending(world_state: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for item in world_state.get("pendencias") or []
        if isinstance(item, dict) and item.get("tipo") == "reavaliar_agente_leve"
    ]


def _next_future(
    due: mundo.WorldInstant, interval_days: int, canonical: mundo.WorldInstant
) -> mundo.WorldInstant:
    step = interval_days * 1440
    value = mundo.WorldInstant(due.minute + step)
    while value <= canonical:
        value = mundo.WorldInstant(value.minute + step)
    return value


def _set_next(state: dict[str, Any], agent_id: str, instant: mundo.WorldInstant) -> None:
    state["agentes"][agent_id]["proxima_avaliacao"] = mundo.instant_parts(instant)


def _cache_hit(
    repo: Path,
    index: dict[str, Any],
    state: dict[str, Any],
    agent_id: str,
    meta: dict[str, Any],
) -> tuple[bool, str | None, list[str]]:
    if _schema(index) != 2:
        return False, None, []
    cache = state["agentes"][agent_id].get("cache_negativo")
    if not isinstance(cache, dict):
        return False, None, []
    signature, sources = causal_signature(repo, agent_id, meta)
    return signature == cache["assinatura_causal"], signature, sources


def process_checkpoint(repo: Path) -> dict[str, Any]:
    """Seleciona poucos NPCs leves; cache válido compacta rotina sem perfil."""
    index = load_index(repo)
    state = load_state(repo, index)
    canonical, _ = mundo.load_canonical_time(repo)
    world_state = mundo.load_world_state(repo)

    open_pending = _light_pending(world_state)
    open_agents = {
        str(item.get("agente_leve")) for item in open_pending if item.get("agente_leve")
    }
    open_ids = {str(item.get("id")) for item in open_pending if item.get("id")}
    completed_ids = {
        str(item.get("id"))
        for item in world_state.get("concluidas_recentes") or []
        if isinstance(item, dict) and item.get("id")
    }

    state_changed = False
    candidates: list[tuple[mundo.WorldInstant, int, str, dict[str, Any]]] = []
    for agent_id, meta in index["agentes"].items():
        if meta["estado"] != "ativo":
            continue
        raw_due = state["agentes"][agent_id]["proxima_avaliacao"]
        due = mundo.parse_instant(raw_due["data"], raw_due["hora"])
        pid = _pending_id(agent_id, due)

        if pid in open_ids or pid in completed_ids:
            next_due = _next_future(due, int(meta["intervalo_dias"]), canonical)
            _set_next(state, agent_id, next_due)
            state_changed = True
            continue

        if agent_id in open_agents or due > canonical:
            continue
        candidates.append((due, -int(meta["prioridade"]), agent_id, meta))

    candidates.sort(key=lambda item: (item[0].minute, item[1], item[2]))
    budget = index["orcamento"]
    available_open = max(0, int(budget["max_pendencias_abertas"]) - len(open_pending))
    limit = min(int(budget["max_novas_por_checkpoint"]), available_open)
    selected = candidates[:limit]

    emitted: list[dict[str, Any]] = []
    compacted: list[dict[str, Any]] = []
    invalidated: list[str] = []
    causal_sources_read: list[str] = []
    cache_checks = 0

    for due, _neg_priority, agent_id, meta in selected:
        hit, current_signature, sources = _cache_hit(repo, index, state, agent_id, meta)
        if current_signature is not None:
            cache_checks += 1
            causal_sources_read.extend(sources)
        if hit:
            next_due = _next_future(due, int(meta["intervalo_dias"]), canonical)
            _set_next(state, agent_id, next_due)
            cache = state["agentes"][agent_id]["cache_negativo"]
            cache["acertos_compactados"] = int(cache["acertos_compactados"]) + 1
            cache["ultima_compactacao"] = mundo.instant_parts(canonical)
            compacted.append(
                {
                    "agente_leve": agent_id,
                    "resultado": "noop_compactado",
                    "vencida_em": mundo.instant_parts(due),
                    "proxima_avaliacao": mundo.instant_parts(next_due),
                    "acertos_compactados": cache["acertos_compactados"],
                }
            )
            state_changed = True
            continue

        if current_signature is not None:
            state["agentes"][agent_id]["cache_negativo"] = None
            invalidated.append(agent_id)
            state_changed = True

        emitted.append(
            {
                "id": _pending_id(agent_id, due),
                "tipo": "reavaliar_agente_leve",
                "agente_leve": agent_id,
                "agentes_afetados": [],
                "disparado_em": mundo.instant_parts(due),
                "motivo": (
                    f"Reavaliar {meta['nome']} fora de cena. Rotina é o padrão; "
                    "só registrar iniciativa se o estado atual oferecer causa concreta."
                ),
                "origem": f"agentes-leves:{agent_id}.cadencia",
            }
        )

    added = mundo._merge_pending(world_state, emitted)
    if added:
        mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, world_state)
        added_ids = {item["id"] for item in added}
        for due, _neg_priority, agent_id, meta in selected:
            if _pending_id(agent_id, due) in added_ids:
                _set_next(
                    state,
                    agent_id,
                    _next_future(due, int(meta["intervalo_dias"]), canonical),
                )
                state_changed = True

    if state_changed:
        mundo._atomic_write_yaml(repo / STATE, state)

    deferred = [agent_id for _due, _priority, agent_id, _meta in candidates[limit:]]
    return {
        "ok": True,
        "novas_pendencias": added,
        "agentes_leves_reconsiderar": [item["agente_leve"] for item in added],
        "noops_compactados": compacted,
        "caches_invalidados": invalidated,
        "adiados_por_orcamento": deferred,
        "orcamento": {
            "max_novas_por_checkpoint": budget["max_novas_por_checkpoint"],
            "max_pendencias_abertas": budget["max_pendencias_abertas"],
            "max_checks_cache_negativo_por_checkpoint": (
                budget.get("max_checks_cache_negativo_por_checkpoint", 0)
            ),
            "checks_cache_negativo": cache_checks,
            "pendencias_abertas_antes": len(open_pending),
        },
        "fontes_lidas": list(
            dict.fromkeys(
                [
                    INDEX.as_posix(),
                    STATE.as_posix(),
                    mundo.TIME_PATH.as_posix(),
                    mundo.WORLD_STATE_PATH.as_posix(),
                    *causal_sources_read,
                ]
            )
        ),
    }


def _completed_for(world_state: dict[str, Any], pending_id: str) -> dict[str, Any] | None:
    for item in world_state.get("concluidas_recentes") or []:
        if isinstance(item, dict) and item.get("id") == pending_id:
            return item
    return None


def conclude_noop(repo: Path, pending_id: str, note: str | None = None) -> dict[str, Any]:
    """Registra no-op explícito e instala cache antes de remover a pendência.

    A ordem é proposital: se o processo cair entre as duas escritas, a pendência
    continua bloqueando o avanço e um retry termina a operação. Cache sozinho
    nunca cria acontecimento nem remove a barreira.
    """
    pending_id = _text(pending_id, "id da pendência")
    index = load_index(repo)
    if _schema(index) != 2:
        raise LightAgentError("concluir-noop exige schema_agentes_leves: 2")
    state = load_state(repo, index)
    world_state = mundo.load_world_state(repo)

    matches = [item for item in _light_pending(world_state) if item.get("id") == pending_id]
    if not matches:
        completed = _completed_for(world_state, pending_id)
        cached_agent = next(
            (
                agent_id
                for agent_id, item in state["agentes"].items()
                if isinstance(item.get("cache_negativo"), dict)
                and item["cache_negativo"].get("pendencia_origem") == pending_id
            ),
            None,
        )
        if completed is not None and cached_agent is not None:
            return {
                "ok": True,
                "ja_concluida": True,
                "agente_leve": cached_agent,
                "concluida": completed,
                "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), mundo.WORLD_STATE_PATH.as_posix()],
            }
        raise LightAgentError(f"pendência leve não encontrada: {pending_id}")

    pending = matches[0]
    agent_id = _text(pending.get("agente_leve"), "pendência.agente_leve")
    meta = index["agentes"].get(agent_id)
    if not isinstance(meta, dict):
        raise LightAgentError(f"pendência referencia agente leve inexistente: {agent_id}")

    signature, causal_sources = causal_signature(repo, agent_id, meta)
    canonical, _ = mundo.load_canonical_time(repo)
    cache = {
        "assinatura_causal": signature,
        "pendencia_origem": pending_id,
        "confirmado_em": mundo.instant_parts(canonical),
        "acertos_compactados": 0,
        "ultima_compactacao": None,
    }
    state["agentes"][agent_id]["cache_negativo"] = cache
    mundo._atomic_write_yaml(repo / STATE, state)

    # Releitura depois da primeira escrita torna retry seguro se houver queda.
    world_state = mundo.load_world_state(repo)
    still_pending = [
        item for item in _light_pending(world_state) if item.get("id") == pending_id
    ]
    if still_pending:
        pending = still_pending[0]
        world_state["pendencias"] = [
            item for item in world_state["pendencias"] if item.get("id") != pending_id
        ]
        completed = {
            "id": pending_id,
            "tipo": "reavaliar_agente_leve",
            "agente_leve": agent_id,
            "disparado_em": pending["disparado_em"],
            "resultado": NOOP_RESULT,
        }
        if note:
            completed["nota"] = _text(note, "nota")
        world_state["concluidas_recentes"].append(completed)
        world_state["concluidas_recentes"] = world_state["concluidas_recentes"][
            -mundo.MAX_RECENT_COMPLETED:
        ]
        mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, world_state)
    else:
        completed = _completed_for(world_state, pending_id)
        if completed is None:
            raise LightAgentError(
                "pendência desapareceu durante concluir-noop sem conclusão rastreável"
            )

    return {
        "ok": True,
        "ja_concluida": False,
        "agente_leve": agent_id,
        "cache_negativo": cache,
        "concluida": completed,
        "pendencias_restantes": len(world_state["pendencias"]),
        "fontes_lidas": list(
            dict.fromkeys(
                [
                    INDEX.as_posix(),
                    STATE.as_posix(),
                    mundo.WORLD_STATE_PATH.as_posix(),
                    mundo.TIME_PATH.as_posix(),
                    *causal_sources,
                ]
            )
        ),
    }


def status_view(repo: Path) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    canonical, _ = mundo.load_canonical_time(repo)
    due = []
    caches: dict[str, Any] = {}
    for agent_id, meta in index["agentes"].items():
        raw = state["agentes"][agent_id]["proxima_avaliacao"]
        instant = mundo.parse_instant(raw["data"], raw["hora"])
        if meta["estado"] == "ativo" and instant <= canonical:
            due.append(agent_id)
        cache = state["agentes"][agent_id].get("cache_negativo")
        if isinstance(cache, dict):
            caches[agent_id] = {
                "confirmado_em": cache["confirmado_em"],
                "acertos_compactados": cache["acertos_compactados"],
                "ultima_compactacao": cache["ultima_compactacao"],
            }
    return {
        "orcamento": index["orcamento"],
        "vencidos": sorted(due),
        "caches_negativos": caches,
        "proximas_avaliacoes": {
            agent_id: state["agentes"][agent_id]["proxima_avaliacao"]
            for agent_id in sorted(index["agentes"])
        },
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), mundo.TIME_PATH.as_posix()],
    }


def check_world(repo: Path) -> dict[str, Any]:
    errors = list(validate_repo(repo).get("erros") or [])
    try:
        index = load_index(repo)
        known = set(index["agentes"])
        world_state = mundo.load_world_state(repo)
        pending = _light_pending(world_state)
        for item in pending:
            agent_id = item.get("agente_leve")
            if agent_id not in known:
                errors.append(f"pendência referencia agente leve inexistente: {agent_id}")
        if len(pending) > int(index["orcamento"]["max_pendencias_abertas"]):
            errors.append("pendências leves abertas excedem o orçamento configurado")
    except (LightAgentError, mundo.WorldEngineError) as exc:
        errors.append(str(exc))
    return {"ok": not errors, "erros": list(dict.fromkeys(errors))}


def _dump(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("validar")
    show = sub.add_parser("mostrar")
    show.add_argument("agente")
    sub.add_parser("processar")
    noop = sub.add_parser(
        "concluir-noop",
        help="conclui reavaliação leve sem mudança extraordinária e instala cache causal",
    )
    noop.add_argument("id")
    noop.add_argument("--nota")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.command == "status":
            result = status_view(repo)
        elif args.command == "validar":
            result = validate_repo(repo)
        elif args.command == "mostrar":
            result = load_agent(repo, args.agente)
        elif args.command == "concluir-noop":
            result = conclude_noop(repo, args.id, args.nota)
        else:
            result = process_checkpoint(repo)
        print(_dump(result), end="")
        if args.command == "validar":
            return 0 if result["ok"] else 1
        return 0
    except (LightAgentError, mundo.WorldEngineError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
