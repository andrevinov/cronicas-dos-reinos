#!/usr/bin/env python3
"""Semântica de direções canônicas como restrições de destino.

Direção não é agente, operação, método, ação ou scheduler. Ela descreve um destino
obrigatório de longo prazo e seus marcos; o mundo pode apenas pedir que o narrador
avalie se fatos já canônicos sustentam o marco corrente.

Esta camada é deliberadamente assimétrica:

* consulta contextual barata continua lendo só estado/índices;
* quando uma direção específica merece avaliação, abre exatamente seu fragmento;
* avanço exige proveniência literal em uma fonte canônica já existente;
* nenhuma API daqui escolhe executor, alvo, método, cena ou momento.
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import yaml

import arcos

INDEX = Path("narrador/direcoes/index.yaml")
STATE = Path("narrador/direcoes/estado.yaml")
DIR = Path("narrador/direcoes")
VALID_STATES = {"ativa", "latente", "suspensa", "concluida"}
FORBIDDEN_EVIDENCE_PREFIXES = (
    "narrador/direcoes/",
    "narrador/arcos/",
)
FORBIDDEN_EVIDENCE_FILES = {
    "narrador/masao/plano.md",
    "narrador/juppongatana/marcos-de-aparicao.md",
    "narrador/aliados/marcos-de-aparicao.md",
}
FORBIDDEN_OPERATIONAL_FIELDS = {
    "executor",
    "executores",
    "acao",
    "acoes",
    "metodo",
    "metodos",
    "alvo",
    "alvos",
    "prazo",
    "agente",
    "agentes",
    "operacao",
    "operacoes",
}


class DestinationDirectionError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise DestinationDirectionError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DestinationDirectionError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise DestinationDirectionError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DestinationDirectionError(f"{label} deve ser texto não vazio")
    return value.strip()


def _normalize(value: Any) -> str:
    raw = unicodedata.normalize("NFKD", str(value))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return " ".join(raw.split()).casefold()


def _safe_rel(value: Any, label: str) -> str:
    value = _text(value, label)
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise DestinationDirectionError(f"{label} deve ficar dentro do repositório")
    return path.as_posix()


def _forbid_operational_fields(data: dict[str, Any], label: str) -> None:
    found = sorted(set(data) & FORBIDDEN_OPERATIONAL_FIELDS)
    if found:
        raise DestinationDirectionError(
            f"{label} contém campos operacionais proibidos para uma restrição de destino: "
            + ", ".join(found)
        )


def validate_destination_shape(data: Any, *, direction_id: str | None = None) -> dict[str, Any]:
    """Valida somente a semântica 'destino, nunca ação'.

    Pode ser chamada por ``direcoes.py`` depois de seu próprio schema legado.
    """
    data = _map(data, direction_id or "direcao")
    label = direction_id or str(data.get("id") or "direcao")
    _forbid_operational_fields(data, label)
    milestones = _list(data.get("marcos"), f"{label}.marcos")
    for i, raw in enumerate(milestones):
        milestone = _map(raw, f"{label}.marcos[{i}]")
        _forbid_operational_fields(milestone, f"{label}.marcos[{i}]")
        _text(milestone.get("id"), f"{label}.marcos[{i}].id")
        _text(
            milestone.get("criterio_para_avancar"),
            f"{label}.marcos[{i}].criterio_para_avancar",
        )
        guards = _list(milestone.get("guardrails"), f"{label}.marcos[{i}].guardrails")
        if not guards or any(not isinstance(item, str) or not item.strip() for item in guards):
            raise DestinationDirectionError(f"{label}.marcos[{i}].guardrails inválidos")
    return data


def load_index(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / INDEX), INDEX.as_posix())
    if data.get("schema_direcoes") != 1 or data.get("natureza") != "reservado":
        raise DestinationDirectionError("índice de direções inválido")
    directions = _map(data.get("direcoes"), "direcoes")
    if not directions:
        raise DestinationDirectionError("índice de direções vazio")
    return data


def load_state(repo: Path, index: dict[str, Any] | None = None) -> dict[str, Any]:
    index = index or load_index(repo)
    data = _map(_load(repo / STATE), STATE.as_posix())
    if data.get("schema_estado_direcoes") != 1 or data.get("natureza") != "controle_reservado":
        raise DestinationDirectionError("estado de direções inválido")
    states = _map(data.get("direcoes"), "estado_direcoes.direcoes")
    if set(states) != set(index["direcoes"]):
        raise DestinationDirectionError("estado de direções diverge do índice")
    for direction_id, raw in states.items():
        current = _map(raw, f"estado_direcoes.{direction_id}")
        state = _text(current.get("estado"), f"estado_direcoes.{direction_id}.estado")
        if state not in VALID_STATES:
            raise DestinationDirectionError(f"estado inválido para {direction_id}: {state}")
    return data


def resolve(index: dict[str, Any], query: str) -> tuple[str, dict[str, Any]]:
    directions = index["direcoes"]
    if query in directions:
        return query, directions[query]
    wanted = _normalize(query)
    hits: list[tuple[str, dict[str, Any]]] = []
    for direction_id, meta in directions.items():
        pool = {_normalize(direction_id), _normalize(meta.get("nome"))}
        if wanted in pool or any(wanted and wanted in item for item in pool):
            hits.append((direction_id, meta))
    if len(hits) != 1:
        if not hits:
            raise DestinationDirectionError(f"direção não encontrada: {query}")
        raise DestinationDirectionError(
            f"direção ambígua {query!r}: " + ", ".join(item[0] for item in hits)
        )
    return hits[0]


def load_fragment(repo: Path, direction_id: str, meta: dict[str, Any]) -> dict[str, Any]:
    raw = _safe_rel(meta.get("arquivo"), f"direcoes.{direction_id}.arquivo")
    path = Path(raw)
    try:
        path.relative_to(DIR)
    except ValueError as exc:
        raise DestinationDirectionError(
            f"direções devem permanecer sob {DIR.as_posix()}: {raw}"
        ) from exc
    data = _map(_load(repo / path), raw)
    if data.get("schema_direcao") != 1 or data.get("natureza") != "reservado":
        raise DestinationDirectionError(f"fragmento inválido: {raw}")
    if data.get("id") != direction_id:
        raise DestinationDirectionError(f"id do fragmento diverge do índice: {direction_id}")
    if data.get("estatuto") != "canonica_obrigatoria":
        raise DestinationDirectionError(f"{direction_id}: estatuto deve ser canonica_obrigatoria")
    validate_destination_shape(data, direction_id=direction_id)
    return data


def _current_milestone(fragment: dict[str, Any], milestone_id: str) -> dict[str, Any]:
    hits = [item for item in fragment["marcos"] if item.get("id") == milestone_id]
    if len(hits) != 1:
        raise DestinationDirectionError(
            f"marco atual não existe exatamente uma vez no fragmento: {milestone_id}"
        )
    return hits[0]


def arc_gate(repo: Path, direction_id: str, *, arc_info: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        if arc_info is None:
            return arcos.eligibility(repo, "direcoes", direction_id)
        allowed = direction_id in set(arc_info["habilitacoes"]["direcoes"])
        return {
            "permitido": allowed,
            "grupo": "direcoes",
            "peca": direction_id,
            "arco_id": arc_info["id"],
            "motivo": "habilitada_no_arco" if allowed else "bloqueada_pelo_arco",
            "fontes_lidas": list(arc_info.get("fontes_lidas") or []),
        }
    except arcos.ArcContractError as exc:
        raise DestinationDirectionError(str(exc)) from exc


def ensure_direction_allowed(repo: Path, direction_id: str) -> dict[str, Any]:
    gate = arc_gate(repo, direction_id)
    if not gate["permitido"]:
        raise DestinationDirectionError(
            f"direção {direction_id} está bloqueada pelo Contrato de Arco corrente"
        )
    return gate


def project(
    repo: Path,
    query: str,
    *,
    arc_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Projeta somente o marco corrente que restringe o destino.

    A saída é deliberadamente não executável e não contém executor/ação/método.
    """
    index = load_index(repo)
    direction_id, meta = resolve(index, query)
    gate = arc_gate(repo, direction_id, arc_info=arc_info)
    sources = [INDEX.as_posix(), *(gate.get("fontes_lidas") or [])]
    if not gate["permitido"]:
        return {
            "ok": True,
            "direcao_id": direction_id,
            "papel": "restricao_destino",
            "permitido": False,
            "executavel": False,
            "motivo": "direcao_bloqueada_pelo_arco",
            "fontes_lidas": list(dict.fromkeys(sources)),
        }

    state = load_state(repo, index)
    sources.append(STATE.as_posix())
    current = state["direcoes"][direction_id]
    if current["estado"] != "ativa":
        return {
            "ok": True,
            "direcao_id": direction_id,
            "papel": "restricao_destino",
            "permitido": False,
            "executavel": False,
            "estado": current["estado"],
            "motivo": "direcao_nao_ativa",
            "fontes_lidas": list(dict.fromkeys(sources)),
        }

    milestone_id = _text(current.get("marco_atual"), f"{direction_id}.marco_atual")
    fragment = load_fragment(repo, direction_id, meta)
    raw_path = _safe_rel(meta.get("arquivo"), f"direcoes.{direction_id}.arquivo")
    sources.append(raw_path)
    milestone = _current_milestone(fragment, milestone_id)
    return {
        "ok": True,
        "direcao_id": direction_id,
        "nome": meta.get("nome"),
        "papel": "restricao_destino",
        "permitido": True,
        "executavel": False,
        "estado": current["estado"],
        "marco_atual": {
            "id": milestone_id,
            "titulo": milestone.get("titulo"),
            "criterio_para_avancar": milestone["criterio_para_avancar"],
            "guardrails": list(milestone["guardrails"]),
        },
        "modo_avaliacao": "avaliar_sustentacao_do_marco",
        "avanco_requer_fato_canonico": True,
        "regra": (
            "A direção restringe o destino: avaliar se fatos já canônicos sustentam o marco. "
            "Ela nunca escolhe executor, ação, método, alvo, cena ou momento."
        ),
        "fontes_lidas": list(dict.fromkeys(sources)),
    }


def verify_advance_evidence(repo: Path, source: str, evidence: str | None) -> dict[str, str]:
    source = _safe_rel(source, "fonte do fato-base")
    evidence = _text(evidence, "evidencia do fato-base")
    if source in FORBIDDEN_EVIDENCE_FILES or any(source.startswith(prefix) for prefix in FORBIDDEN_EVIDENCE_PREFIXES):
        raise DestinationDirectionError(
            f"fonte do fato-base é prescritiva, não factual: {source}"
        )
    path = repo / source
    if not path.is_file():
        raise DestinationDirectionError(f"fonte do fato-base inexistente: {source}")
    haystack = _normalize(path.read_text(encoding="utf-8"))
    needle = _normalize(evidence)
    if needle not in haystack:
        raise DestinationDirectionError(
            f"evidência do fato-base não foi localizada literalmente em {source}"
        )
    return {"fonte": source, "evidencia": evidence}


def prepare_advance(
    repo: Path,
    query: str,
    *,
    source: str,
    evidence: str,
    note: str,
) -> dict[str, Any]:
    """Prepara, sem mutar, a prova necessária para um avanço explícito."""
    projection = project(repo, query)
    if not projection.get("permitido"):
        raise DestinationDirectionError(
            f"direção {projection['direcao_id']} não está elegível para avanço: {projection.get('motivo')}"
        )
    proof = verify_advance_evidence(repo, source, evidence)
    return {
        "ok": True,
        "direcao_id": projection["direcao_id"],
        "papel": "restricao_destino",
        "executavel": False,
        "marco_atual": projection["marco_atual"],
        "fato_base": proof,
        "nota_interpretativa": _text(note, "nota"),
        "mutou_estado": False,
        "regra": (
            "Proveniência literal prova apenas o fato-base; o narrador ainda decide se ele satisfaz "
            "o critério do marco antes de chamar o avanço explícito."
        ),
        "fontes_lidas": list(
            dict.fromkeys([*projection["fontes_lidas"], proof["fonte"]])
        ),
    }


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    quantity = 0
    try:
        index = load_index(repo)
        state = load_state(repo, index)
        for direction_id, meta in index["direcoes"].items():
            fragment = load_fragment(repo, direction_id, meta)
            quantity += 1
            current = state["direcoes"][direction_id]
            if current["estado"] == "ativa":
                milestone_id = _text(
                    current.get("marco_atual"), f"{direction_id}.marco_atual"
                )
                _current_milestone(fragment, milestone_id)
    except DestinationDirectionError as exc:
        errors.append(str(exc))
    return {"ok": not errors, "quantidade": quantity, "erros": errors}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    show = sub.add_parser("mostrar")
    show.add_argument("direcao")
    prep = sub.add_parser("preparar-avanco")
    prep.add_argument("direcao")
    prep.add_argument("--fonte", required=True)
    prep.add_argument("--evidencia", required=True)
    prep.add_argument("--nota", required=True)
    sub.add_parser("validar")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "mostrar":
            result = project(repo, args.direcao)
        elif args.cmd == "preparar-avanco":
            result = prepare_advance(
                repo,
                args.direcao,
                source=args.fonte,
                evidence=args.evidencia,
                note=args.nota,
            )
        else:
            result = validate_repo(repo)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0 if args.cmd != "validar" or result["ok"] else 1
    except (DestinationDirectionError, OSError, yaml.YAMLError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
