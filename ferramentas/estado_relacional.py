#!/usr/bin/env python3
"""Estado relacional v1 sobre a camada fragmentada de medidores de NPC.

A Task 26 não cria um segundo armazenamento. O eixo público ``afinidade`` é a
semântica operacional do campo legado ``medidores.vinculo``; ``confianca`` usa o
campo homônimo já existente. A prosa detalhada continua em ``estado/relacoes``.

A ferramenta é principalmente um contrato/check de manutenção. O hot path normal
continua usando ``contexto npc <nome>`` e não ganha chamada adicional.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Iterable

import yaml

import contexto_core

NPC_INDEX = Path("estado/npcs/index.yaml")
REL_INDEX = Path("estado/relacoes/index.yaml")
CONTRACT = Path("estado/npcs/relacionamento-v1.yaml")
MAX_VALUE = 10
MIN_VALUE = 0
MAX_FRAGMENT_BYTES = 12 * 1024
MAX_INDEX_BYTES = 24 * 1024
RELATIONAL_PATHS = {
    "medidores.vinculo": "afinidade",
    "medidores.confianca": "confianca",
}


class RelationshipStateError(ValueError):
    """Estado relacional ausente, incoerente ou fora do contrato."""


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RelationshipStateError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise RelationshipStateError(f"YAML inválido em {path}: {exc}") from exc


def _axis(value: Any, label: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise RelationshipStateError(f"{label} deve ser inteiro 0..10 ou null")
    if not MIN_VALUE <= value <= MAX_VALUE:
        raise RelationshipStateError(f"{label} fora da escala 0..10: {value}")
    return value


def _band(value: int | None) -> str:
    if value is None:
        return "desconhecida"
    if value <= 2:
        return "adversa"
    if value <= 4:
        return "baixa"
    if value == 5:
        return "neutra"
    if value <= 7:
        return "positiva"
    if value <= 9:
        return "forte"
    return "extrema"


def validate_meters(meters: Any, *, entity_id: str) -> dict[str, Any]:
    if not isinstance(meters, dict):
        raise RelationshipStateError(f"{entity_id}: medidores ausentes")
    affinity = _axis(meters.get("vinculo"), f"{entity_id}.afinidade/vinculo")
    trust = _axis(meters.get("confianca"), f"{entity_id}.confianca")
    risk = _axis(meters.get("risco_percebido"), f"{entity_id}.risco_percebido")
    return {"vinculo": affinity, "confianca": trust, "risco_percebido": risk}


def project(meters: Any) -> dict[str, Any]:
    normalized = validate_meters(meters, entity_id="estado_relacional")
    affinity = normalized["vinculo"]
    trust = normalized["confianca"]
    return {
        "schema_estado_relacional": 1,
        "afinidade": affinity,
        "afinidade_faixa": _band(affinity),
        "confianca": trust,
        "confianca_faixa": _band(trust),
        "risco_percebido": normalized["risco_percebido"],
    }


def is_relationship_delta(delta: Any) -> bool:
    return (
        isinstance(delta, dict)
        and isinstance(delta.get("alvo"), str)
        and str(delta["alvo"]).startswith("npc:")
        and delta.get("caminho") in RELATIONAL_PATHS
    )


def _evidence(delta: dict[str, Any], axis: str) -> None:
    fact = delta.get("fato_canonico")
    source = delta.get("fonte")
    if not isinstance(fact, str) or len(fact.strip()) < 20:
        raise RelationshipStateError(
            f"mudança de {axis} exige fato_canonico concreto (mínimo 20 caracteres)"
        )
    if not isinstance(source, str) or not source.strip():
        raise RelationshipStateError(f"mudança de {axis} exige fonte canônica rastreável")


def validate_relationship_delta(delta: Any) -> dict[str, Any]:
    """Congela forma do delta; o estado anterior é conferido no checkpoint."""
    if not is_relationship_delta(delta):
        raise RelationshipStateError("delta não aponta eixo relacional v1")
    axis = RELATIONAL_PATHS[str(delta["caminho"])]
    op = delta.get("op")
    if op == "inc":
        if delta.get("valor") not in {-1, 1}:
            raise RelationshipStateError(
                f"mudança de {axis} deve usar inc +1/-1; não use salto múltiplo"
            )
    elif op == "set":
        if delta.get("inicializacao") is not True:
            raise RelationshipStateError(
                f"set em {axis} só é permitido para eixo null com inicializacao=true"
            )
        value = _axis(delta.get("valor"), f"inicializacao.{axis}")
        if value is None:
            raise RelationshipStateError(f"inicialização de {axis} exige valor conhecido 0..10")
    else:
        raise RelationshipStateError(f"mudança de {axis} aceita somente inc ou inicialização set")
    if delta.get("visibilidade", "operacional") != "operacional":
        raise RelationshipStateError("estado relacional de NPC é operacional, não delta reservado")
    _evidence(delta, axis)
    return delta


def _indices(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    npc = _load_yaml(repo / NPC_INDEX)
    relations = _load_yaml(repo / REL_INDEX)
    if not isinstance(npc, dict) or not isinstance(npc.get("npcs"), dict):
        raise RelationshipStateError("estado/npcs/index.yaml inválido")
    if not isinstance(relations, dict) or not isinstance(relations.get("relacoes"), dict):
        raise RelationshipStateError("estado/relacoes/index.yaml inválido")
    return npc, relations


def _load_meters(repo: Path, npc_index: dict[str, Any], entity_id: str) -> dict[str, Any]:
    entry = npc_index["npcs"].get(entity_id)
    if not isinstance(entry, dict) or not isinstance(entry.get("arquivo"), str):
        raise RelationshipStateError(f"{entity_id}: estado relacional não indexado")
    doc = _load_yaml(repo / entry["arquivo"])
    payload = doc.get("npc") if isinstance(doc, dict) else None
    if not isinstance(payload, dict):
        raise RelationshipStateError(f"{entity_id}: fragmento NPC inválido")
    return validate_meters(payload.get("medidores"), entity_id=entity_id)


def validate_batch(repo: Path, records: Iterable[dict[str, Any]]) -> int:
    """Valida transições contra o estado consolidado antes do stage.

    Só abre índice/fragmentos quando o lote realmente contém afinidade/confiança.
    Vários deltas pendentes para o mesmo NPC são aplicados em memória na ordem do
    ledger, garantindo limites 0..10 e inicialização única de valores ``null``.
    """
    relational: list[dict[str, Any]] = []
    for record in records:
        for delta in record.get("deltas") or []:
            if is_relationship_delta(delta):
                validate_relationship_delta(delta)
                relational.append(delta)
    if not relational:
        return 0

    npc_index = _load_yaml(repo / NPC_INDEX)
    if not isinstance(npc_index, dict) or not isinstance(npc_index.get("npcs"), dict):
        raise RelationshipStateError("estado/npcs/index.yaml inválido")
    working: dict[str, dict[str, Any]] = {}

    for delta in relational:
        entity_id = str(delta["alvo"]).split(":", 1)[1]
        if entity_id not in working:
            working[entity_id] = _load_meters(repo, npc_index, entity_id)
        meters = working[entity_id]
        stored = "vinculo" if delta["caminho"] == "medidores.vinculo" else "confianca"
        axis = RELATIONAL_PATHS[str(delta["caminho"])]
        current = meters[stored]
        if delta["op"] == "inc":
            if current is None:
                raise RelationshipStateError(
                    f"{entity_id}.{axis} está desconhecida; inicialize com set + inicializacao=true antes de incrementar"
                )
            next_value = _axis(current + int(delta["valor"]), f"{entity_id}.{axis}")
        else:
            if current is not None:
                raise RelationshipStateError(
                    f"{entity_id}.{axis} já vale {current}; inicialização não pode sobrescrever eixo conhecido"
                )
            next_value = _axis(delta.get("valor"), f"{entity_id}.{axis}")
            if next_value is None:
                raise RelationshipStateError(f"{entity_id}.{axis}: inicialização não pode permanecer null")
        meters[stored] = next_value
    return len(relational)


def lookup(repo: Path, term: str) -> dict[str, Any]:
    npc_index, _ = _indices(repo)
    entity_id, entry, candidates = contexto_core.resolve_entity(npc_index["npcs"], term)
    if entity_id is None or not isinstance(entry, dict):
        return {"encontrado": False, "candidatos": candidates}
    rel = entry.get("arquivo")
    if not isinstance(rel, str):
        raise RelationshipStateError(f"{entity_id}: fragmento NPC não indexado")
    doc = _load_yaml(repo / rel)
    payload = doc.get("npc") if isinstance(doc, dict) else None
    if not isinstance(payload, dict):
        raise RelationshipStateError(f"{entity_id}: fragmento NPC inválido")
    result = project(payload.get("medidores"))
    result.update(
        {
            "encontrado": True,
            "id": entity_id,
            "nome": payload.get("nome") or entry.get("nome") or entity_id,
            "identidade_relacional": payload.get("identidade_relacional", "ren"),
            "fonte": rel,
        }
    )
    return result


def validate_change(change: Any) -> dict[str, Any]:
    """Valida uma proposta explícita; não aplica nem agenda mudança alguma."""
    if not isinstance(change, dict):
        raise RelationshipStateError("mudança relacional deve ser mapa")
    axis = change.get("eixo")
    if axis not in {"afinidade", "confianca"}:
        raise RelationshipStateError("eixo deve ser afinidade ou confianca")
    before = _axis(change.get("de"), f"mudanca.{axis}.de")
    after = _axis(change.get("para"), f"mudanca.{axis}.para")
    if before is None or after is None:
        raise RelationshipStateError("mudança exige valores conhecidos em de/para")
    if abs(after - before) > 1:
        raise RelationshipStateError("mudança relacional normal não pode saltar mais de 1 ponto por fato")
    if after == before:
        raise RelationshipStateError("mudança relacional precisa alterar o valor")
    fact = change.get("fato_canonico")
    source = change.get("fonte")
    if not isinstance(fact, str) or len(fact.strip()) < 20:
        raise RelationshipStateError("mudança exige fato_canonico concreto (mínimo 20 caracteres)")
    if not isinstance(source, str) or not source.strip():
        raise RelationshipStateError("mudança exige fonte canônica rastreável")
    return {
        "eixo": axis,
        "de": before,
        "para": after,
        "fato_canonico": fact.strip(),
        "fonte": source.strip(),
    }


def check(repo: Path) -> list[str]:
    errors: list[str] = []
    try:
        contract = _load_yaml(repo / CONTRACT)
        npc_index, relation_index = _indices(repo)
    except RelationshipStateError as exc:
        return [str(exc)]
    if not isinstance(contract, dict) or contract.get("schema_estado_relacional") != 1:
        errors.append("contrato relacional deve usar schema_estado_relacional: 1")

    npcs = npc_index["npcs"]
    relations = relation_index["relacoes"]
    if npc_index.get("quantidade") != len(npcs):
        errors.append("estado/npcs/index.yaml.quantidade diverge do número real de entradas")
    missing = sorted(set(relations) - set(npcs))
    if missing:
        errors.append("relações sem estado relacional: " + ", ".join(missing))

    for entity_id in sorted(relations):
        entry = npcs.get(entity_id)
        if not isinstance(entry, dict):
            continue
        rel = entry.get("arquivo")
        if not isinstance(rel, str):
            errors.append(f"{entity_id}: arquivo de medidores ausente no índice")
            continue
        path = repo / rel
        if not path.is_file():
            errors.append(f"{entity_id}: fragmento ausente: {rel}")
            continue
        if path.stat().st_size > MAX_FRAGMENT_BYTES:
            errors.append(f"{entity_id}: fragmento excede {MAX_FRAGMENT_BYTES} bytes")
        try:
            doc = _load_yaml(path)
        except RelationshipStateError as exc:
            errors.append(str(exc))
            continue
        payload = doc.get("npc") if isinstance(doc, dict) else None
        if not isinstance(payload, dict):
            errors.append(f"{entity_id}: payload npc inválido")
            continue
        try:
            meters = validate_meters(payload.get("medidores"), entity_id=entity_id)
        except RelationshipStateError as exc:
            errors.append(str(exc))
            continue
        indexed = entry.get("medidores")
        if indexed != meters:
            errors.append(f"{entity_id}: medidores do índice divergem do fragmento")

    index_path = repo / NPC_INDEX
    if index_path.is_file() and index_path.stat().st_size > MAX_INDEX_BYTES:
        errors.append(f"índice de NPCs excede {MAX_INDEX_BYTES} bytes")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)
    status = sub.add_parser("status", help="projeta afinidade/confiança de um NPC")
    status.add_argument("npc")
    sub.add_parser("check", help="valida cobertura e coerência do estado relacional")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "status":
            result = lookup(repo, args.npc)
            print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
            return 0
        errors = check(repo)
        if errors:
            print("FALHA — estado relacional inválido:")
            for error in errors:
                print(f"- {error}")
            return 1
        print("OK — estado relacional v1 cobre todas as relações atuais.")
        return 0
    except (RelationshipStateError, OSError, yaml.YAMLError) as exc:
        print(f"FALHA — {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
