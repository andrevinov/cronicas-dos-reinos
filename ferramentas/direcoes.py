#!/usr/bin/env python3
"""Camada reservada de direções narrativas canônicas.

Direções são destinos obrigatórios de longo prazo sem roteiro fixo. Esta ferramenta
não inventa cenas nem decide sozinha que um marco ocorreu. Ela mantém consulta
fragmentada, valida proveniência e registra ativações/avanços explicitamente
justificados pelo narrador.
"""
from __future__ import annotations

import argparse
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

INDEX_PATH = Path("narrador/direcoes/index.yaml")
STATE_PATH = Path("narrador/direcoes/estado.yaml")
DIRECTIONS_DIR = Path("narrador/direcoes")
TIME_PATH = Path("estado/tempo.yaml")
VALID_STATES = {"ativa", "latente", "suspensa", "concluida"}
VALID_STATUTES = {"canonica_obrigatoria"}
VALID_CADENCES = {"amanhecer"}
MAX_HISTORY = 32
DATE_RE = re.compile(r"^(?:\d{1,2}\s+[A-Za-zÀ-ÿ'-]+|[A-Za-zÀ-ÿ' -]+),\s*\d+\s*DR$")


class DirectionError(ValueError):
    """Erro de contrato da camada de direções canônicas."""


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DirectionError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise DirectionError(f"YAML inválido em {path}: {exc}") from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DirectionError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise DirectionError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DirectionError(f"{label} deve ser texto não vazio")
    return value.strip()


def _nullable_text(value: Any, label: str) -> str | None:
    if value is None:
        return None
    return _text(value, label)


def _normalize(value: str) -> str:
    raw = unicodedata.normalize("NFKD", str(value))
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return " ".join(raw.split()).lower()


def _repo_path(repo: Path, raw: str, *, prefix: Path | None = None) -> Path:
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        raise DirectionError(f"caminho fora do repositório: {raw}")
    if prefix is not None:
        try:
            rel.relative_to(prefix)
        except ValueError as exc:
            raise DirectionError(f"caminho {raw} deve permanecer sob {prefix.as_posix()}") from exc
    return repo / rel


def load_index(repo: Path) -> dict[str, Any]:
    data = _map(_load_yaml(repo / INDEX_PATH), INDEX_PATH.as_posix())
    if data.get("schema_direcoes") != 1:
        raise DirectionError("índice deve usar schema_direcoes: 1")
    if data.get("natureza") != "reservado":
        raise DirectionError("índice de direções deve ter natureza: reservado")
    directions = _map(data.get("direcoes"), "direcoes")
    if not directions:
        raise DirectionError("índice de direções não pode ser vazio")

    files: set[str] = set()
    for direction_id, meta_raw in directions.items():
        direction_id = _text(direction_id, "id da direção")
        meta = _map(meta_raw, f"direcoes.{direction_id}")
        _text(meta.get("nome"), f"direcoes.{direction_id}.nome")
        raw_path = _text(meta.get("arquivo"), f"direcoes.{direction_id}.arquivo")
        _repo_path(repo, raw_path, prefix=DIRECTIONS_DIR)
        if raw_path in files:
            raise DirectionError(f"arquivo de direção duplicado: {raw_path}")
        files.add(raw_path)

        evaluation = _map(meta.get("avaliacao"), f"direcoes.{direction_id}.avaliacao")
        cadence = _text(evaluation.get("cadencia"), f"direcoes.{direction_id}.avaliacao.cadencia")
        if cadence not in VALID_CADENCES:
            raise DirectionError(f"cadência inválida para {direction_id}: {cadence}")
        interval = evaluation.get("intervalo_dias")
        if not isinstance(interval, int) or interval < 1:
            raise DirectionError(f"direcoes.{direction_id}.avaliacao.intervalo_dias deve ser inteiro >= 1")
        start = _text(evaluation.get("inicio"), f"direcoes.{direction_id}.avaliacao.inicio")
        if not DATE_RE.fullmatch(start):
            raise DirectionError(f"data de início inválida para {direction_id}: {start}")

        activation = meta.get("ativacao")
        if activation is not None:
            activation = _map(activation, f"direcoes.{direction_id}.ativacao")
            dep = _map(activation.get("depende_de"), f"direcoes.{direction_id}.ativacao.depende_de")
            _text(dep.get("direcao"), f"direcoes.{direction_id}.ativacao.depende_de.direcao")
            _text(dep.get("marco"), f"direcoes.{direction_id}.ativacao.depende_de.marco")
    return data


def load_state(repo: Path, index: dict[str, Any] | None = None) -> dict[str, Any]:
    index = index or load_index(repo)
    data = _map(_load_yaml(repo / STATE_PATH), STATE_PATH.as_posix())
    if data.get("schema_estado_direcoes") != 1:
        raise DirectionError("estado deve usar schema_estado_direcoes: 1")
    if data.get("natureza") != "controle_reservado":
        raise DirectionError("estado de direções deve ter natureza: controle_reservado")
    states = _map(data.get("direcoes"), "estado_direcoes.direcoes")
    expected = set(index["direcoes"])
    actual = set(states)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        raise DirectionError(f"estado/índice divergem; ausentes={missing}, extras={extra}")
    for direction_id, raw in states.items():
        item = _map(raw, f"estado_direcoes.{direction_id}")
        state = _text(item.get("estado"), f"estado_direcoes.{direction_id}.estado")
        if state not in VALID_STATES:
            raise DirectionError(f"estado inválido para {direction_id}: {state}")
        current = item.get("marco_atual")
        if state == "concluida":
            if current is not None:
                raise DirectionError(f"direção concluída {direction_id} deve ter marco_atual: null")
        else:
            _text(current, f"estado_direcoes.{direction_id}.marco_atual")
        completed = _list(item.get("marcos_concluidos"), f"estado_direcoes.{direction_id}.marcos_concluidos")
        if any(not isinstance(value, str) or not value.strip() for value in completed):
            raise DirectionError(f"marcos_concluidos inválidos em {direction_id}")
        history = _list(item.get("historico_recente"), f"estado_direcoes.{direction_id}.historico_recente")
        for i, entry in enumerate(history):
            _map(entry, f"estado_direcoes.{direction_id}.historico_recente[{i}]")
    return data


def load_fragment(repo: Path, direction_id: str, meta: dict[str, Any]) -> dict[str, Any]:
    path = _repo_path(repo, _text(meta.get("arquivo"), f"direcoes.{direction_id}.arquivo"), prefix=DIRECTIONS_DIR)
    data = _map(_load_yaml(path), path.relative_to(repo).as_posix())
    if data.get("schema_direcao") != 1:
        raise DirectionError(f"{path.relative_to(repo)} deve usar schema_direcao: 1")
    if data.get("natureza") != "reservado":
        raise DirectionError(f"{direction_id} deve ter natureza: reservado")
    if data.get("id") != direction_id:
        raise DirectionError(f"id do fragmento {data.get('id')!r} não coincide com índice {direction_id!r}")
    if data.get("nome") != meta.get("nome"):
        raise DirectionError(f"nome de {direction_id} diverge entre índice e fragmento")
    statute = _text(data.get("estatuto"), f"{direction_id}.estatuto")
    if statute not in VALID_STATUTES:
        raise DirectionError(f"estatuto inválido para {direction_id}: {statute}")
    _text(data.get("principio"), f"{direction_id}.principio")
    sources = _list(data.get("fontes_canonicas"), f"{direction_id}.fontes_canonicas")
    if not sources or any(not isinstance(value, str) or not value.strip() for value in sources):
        raise DirectionError(f"{direction_id}.fontes_canonicas deve ser lista não vazia")
    milestones = _list(data.get("marcos"), f"{direction_id}.marcos")
    if not milestones:
        raise DirectionError(f"{direction_id} precisa de ao menos um marco")
    seen_ids: set[str] = set()
    orders: list[int] = []
    for i, raw in enumerate(milestones):
        milestone = _map(raw, f"{direction_id}.marcos[{i}]")
        mid = _text(milestone.get("id"), f"{direction_id}.marcos[{i}].id")
        if mid in seen_ids:
            raise DirectionError(f"marco duplicado em {direction_id}: {mid}")
        seen_ids.add(mid)
        order = milestone.get("ordem")
        if not isinstance(order, int) or order < 1:
            raise DirectionError(f"ordem inválida em {direction_id}.{mid}")
        orders.append(order)
        _text(milestone.get("titulo"), f"{direction_id}.{mid}.titulo")
        source = _text(milestone.get("fonte"), f"{direction_id}.{mid}.fonte")
        if source not in sources:
            raise DirectionError(f"marco {direction_id}.{mid} usa fonte não declarada: {source}")
        _text(milestone.get("evidencia"), f"{direction_id}.{mid}.evidencia")
        _text(milestone.get("criterio_para_avancar"), f"{direction_id}.{mid}.criterio_para_avancar")
        guards = _list(milestone.get("guardrails"), f"{direction_id}.{mid}.guardrails")
        if not guards or any(not isinstance(value, str) or not value.strip() for value in guards):
            raise DirectionError(f"guardrails inválidos em {direction_id}.{mid}")
    if sorted(orders) != list(range(1, len(milestones) + 1)) or orders != sorted(orders):
        raise DirectionError(f"ordem dos marcos de {direction_id} deve ser contínua a partir de 1")
    return data


def _milestone_map(fragment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in fragment["marcos"]}


def _ordered_ids(fragment: dict[str, Any]) -> list[str]:
    return [item["id"] for item in sorted(fragment["marcos"], key=lambda item: item["ordem"])]


def _validate_evidence(repo: Path, direction_id: str, fragment: dict[str, Any]) -> None:
    cache: dict[str, str] = {}
    for source in fragment["fontes_canonicas"]:
        path = _repo_path(repo, source)
        if not path.is_file():
            raise DirectionError(f"fonte canônica inexistente para {direction_id}: {source}")
        cache[source] = _normalize(path.read_text(encoding="utf-8"))
    for milestone in fragment["marcos"]:
        source = milestone["fonte"]
        evidence = _normalize(milestone["evidencia"])
        if evidence not in cache[source]:
            raise DirectionError(
                f"fonte {source} não possui evidência declarada para {direction_id}.{milestone['id']}"
            )


def dependency_satisfied(index: dict[str, Any], state: dict[str, Any], direction_id: str) -> bool:
    meta = index["direcoes"][direction_id]
    activation = meta.get("ativacao")
    if activation is None:
        return True
    dep = activation["depende_de"]
    other = state["direcoes"].get(dep["direcao"])
    if not isinstance(other, dict):
        return False
    return dep["marco"] in (other.get("marcos_concluidos") or [])


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    quantity = 0
    try:
        index = load_index(repo)
        state = load_state(repo, index)
        fragments: dict[str, dict[str, Any]] = {}
        for direction_id, meta in index["direcoes"].items():
            fragment = load_fragment(repo, direction_id, meta)
            fragments[direction_id] = fragment
            quantity += 1
            _validate_evidence(repo, direction_id, fragment)

        for direction_id, meta in index["direcoes"].items():
            activation = meta.get("ativacao")
            if activation is not None:
                dep = activation["depende_de"]
                if dep["direcao"] not in fragments:
                    errors.append(f"{direction_id} depende de direção inexistente: {dep['direcao']}")
                elif dep["marco"] not in _milestone_map(fragments[dep["direcao"]]):
                    errors.append(f"{direction_id} depende de marco inexistente: {dep['direcao']}.{dep['marco']}")

            fragment = fragments[direction_id]
            ordered = _ordered_ids(fragment)
            current_state = state["direcoes"][direction_id]
            completed = current_state["marcos_concluidos"]
            if completed != ordered[: len(completed)]:
                errors.append(f"marcos concluídos de {direction_id} não formam prefixo ordenado")
            if current_state["estado"] == "concluida":
                if completed != ordered:
                    errors.append(f"direção concluída {direction_id} não concluiu todos os marcos")
            else:
                expected_current = ordered[len(completed)] if len(completed) < len(ordered) else None
                if current_state.get("marco_atual") != expected_current:
                    errors.append(
                        f"marco_atual de {direction_id} deveria ser {expected_current!r}, "
                        f"mas é {current_state.get('marco_atual')!r}"
                    )
                if current_state["estado"] == "ativa" and meta.get("ativacao") and not dependency_satisfied(index, state, direction_id):
                    errors.append(f"direção {direction_id} está ativa sem dependência satisfeita")
    except DirectionError as exc:
        errors.append(str(exc))
    return {"ok": not errors, "quantidade": quantity, "erros": errors}


def resolve(index: dict[str, Any], query: str) -> tuple[str, dict[str, Any]]:
    if query in index["direcoes"]:
        return query, index["direcoes"][query]
    wanted = _normalize(query)
    matches = []
    for direction_id, meta in index["direcoes"].items():
        candidates = {_normalize(direction_id), _normalize(meta["nome"])}
        if wanted in candidates or any(wanted and wanted in candidate for candidate in candidates):
            matches.append((direction_id, meta))
    if not matches:
        raise DirectionError(f"direção não encontrada: {query}")
    if len(matches) > 1:
        raise DirectionError("consulta ambígua: " + ", ".join(item[0] for item in matches))
    return matches[0]


def show(repo: Path, query: str) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    direction_id, meta = resolve(index, query)
    fragment = load_fragment(repo, direction_id, meta)
    return {
        "direcao_id": direction_id,
        "nome": meta["nome"],
        "estado": state["direcoes"][direction_id],
        "ativacao_satisfeita": dependency_satisfied(index, state, direction_id),
        "direcao": fragment,
        "fontes_lidas": [
            INDEX_PATH.as_posix(),
            STATE_PATH.as_posix(),
            meta["arquivo"],
        ],
    }


def status_view(repo: Path) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    items = []
    for direction_id, meta in index["direcoes"].items():
        current = state["direcoes"][direction_id]
        items.append(
            {
                "id": direction_id,
                "nome": meta["nome"],
                "estado": current["estado"],
                "marco_atual": current.get("marco_atual"),
                "ativacao_satisfeita": dependency_satisfied(index, state, direction_id),
            }
        )
    return {"direcoes": items, "fontes_lidas": [INDEX_PATH.as_posix(), STATE_PATH.as_posix()]}


def _canonical_time(repo: Path) -> dict[str, Any]:
    path = repo / TIME_PATH
    if not path.is_file():
        return {"data": None, "hora": None}
    raw = _load_yaml(path) or {}
    if not isinstance(raw, dict):
        return {"data": None, "hora": None}
    return {
        "data": raw.get("data_atual") or raw.get("data"),
        "hora": raw.get("hora_aproximada"),
    }


def _atomic_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        temp = Path(handle.name)
    os.replace(temp, path)


def _history(repo: Path, action: str, origin: str, note: str, **extra: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "acao": action,
        "em": _canonical_time(repo),
        "origem": _text(origin, "origem"),
        "nota": _text(note, "nota"),
    }
    entry.update(extra)
    return entry


def activate(repo: Path, query: str, origin: str, note: str) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    direction_id, _ = resolve(index, query)
    current = state["direcoes"][direction_id]
    if current["estado"] != "latente":
        raise DirectionError(f"direção {direction_id} não está latente: {current['estado']}")
    if not dependency_satisfied(index, state, direction_id):
        raise DirectionError(f"dependência de ativação ainda não satisfeita para {direction_id}")
    current["estado"] = "ativa"
    current["historico_recente"].append(_history(repo, "ativar", origin, note))
    current["historico_recente"] = current["historico_recente"][-MAX_HISTORY:]
    _atomic_yaml(repo / STATE_PATH, state)
    return {"ok": True, "direcao": direction_id, "estado": "ativa", "marco_atual": current["marco_atual"]}


def advance(repo: Path, query: str, origin: str, note: str) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    direction_id, meta = resolve(index, query)
    current = state["direcoes"][direction_id]
    if current["estado"] != "ativa":
        raise DirectionError(f"direção {direction_id} não está ativa: {current['estado']}")
    fragment = load_fragment(repo, direction_id, meta)
    ordered = _ordered_ids(fragment)
    milestone = current.get("marco_atual")
    if milestone not in ordered:
        raise DirectionError(f"marco atual inválido para {direction_id}: {milestone!r}")
    index_current = ordered.index(milestone)
    if current["marcos_concluidos"] != ordered[:index_current]:
        raise DirectionError(f"progresso inconsistente antes de avançar {direction_id}")

    current["marcos_concluidos"].append(milestone)
    if index_current + 1 < len(ordered):
        next_milestone = ordered[index_current + 1]
        current["marco_atual"] = next_milestone
        new_state = "ativa"
    else:
        next_milestone = None
        current["marco_atual"] = None
        current["estado"] = "concluida"
        new_state = "concluida"
    current["historico_recente"].append(
        _history(repo, "avancar", origin, note, marco_concluido=milestone, proximo_marco=next_milestone)
    )
    current["historico_recente"] = current["historico_recente"][-MAX_HISTORY:]
    _atomic_yaml(repo / STATE_PATH, state)
    return {
        "ok": True,
        "direcao": direction_id,
        "marco_concluido": milestone,
        "proximo_marco": next_milestone,
        "estado": new_state,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("status")
    show_parser = sub.add_parser("mostrar")
    show_parser.add_argument("direcao")
    sub.add_parser("validar")
    activate_parser = sub.add_parser("ativar")
    activate_parser.add_argument("direcao")
    activate_parser.add_argument("--origem", required=True)
    activate_parser.add_argument("--nota", required=True)
    advance_parser = sub.add_parser("avancar")
    advance_parser.add_argument("direcao")
    advance_parser.add_argument("--origem", required=True)
    advance_parser.add_argument("--nota", required=True)
    return parser


def _dump(value: Any) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.comando == "status":
            result = status_view(repo)
        elif args.comando == "mostrar":
            result = show(repo, args.direcao)
        elif args.comando == "ativar":
            result = activate(repo, args.direcao, args.origem, args.nota)
        elif args.comando == "avancar":
            result = advance(repo, args.direcao, args.origem, args.nota)
        else:
            result = validate_repo(repo)
        print(_dump(result), end="")
        return 0 if args.comando != "validar" or result["ok"] else 1
    except (DirectionError, OSError, yaml.YAMLError) as exc:
        print(f"erro: {exc}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
