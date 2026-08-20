#!/usr/bin/env python3
"""Gate contextual de entrada de aliados futuros.

Esta camada não cria uma segunda fila de aliados. Ela lê somente o índice/estado
já canônicos de ``narrador/entradas`` e o Contrato de Arco para responder se um
aliado futuro pode ser proposto por uma cena concreta.

A ordem é deliberada:

arco permite -> candidato está em foco -> janela temporal está aberta -> nível
permite -> contexto da cena pode propor avaliação.

``permitido`` nunca significa que o aliado apareceu. A confirmação continua sendo
responsabilidade da camada ``entradas`` somente depois de uma entrada realmente
narrada/canonizada.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml

import arcos

INDEX = Path("narrador/entradas/index.yaml")
STATE = Path("narrador/entradas/estado.yaml")
RUNTIME = Path("runtime/contexto.yaml")
VALID_STATES = {"latente", "presente", "inviavel"}


class AllyContextError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise AllyContextError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AllyContextError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise AllyContextError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AllyContextError(f"{label} deve ser texto não vazio")
    return value.strip()


def load_index(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / INDEX), INDEX.as_posix())
    if data.get("schema_entradas") != 1 or data.get("natureza") != "reservado":
        raise AllyContextError("índice de entradas inválido")
    candidates = _map(data.get("candidatos"), "entradas.candidatos")
    if not candidates:
        raise AllyContextError("índice de entradas não pode ser vazio")
    seen_orders: set[int] = set()
    for entry_id, raw in candidates.items():
        _text(entry_id, "id de entrada")
        meta = _map(raw, f"candidatos.{entry_id}")
        _text(meta.get("nome"), f"candidatos.{entry_id}.nome")
        order = meta.get("ordem")
        level = meta.get("nivel_minimo_normal")
        if not isinstance(order, int) or isinstance(order, bool) or order < 1:
            raise AllyContextError(f"candidatos.{entry_id}.ordem inválida")
        if order in seen_orders:
            raise AllyContextError(f"ordem de entrada duplicada: {order}")
        seen_orders.add(order)
        if not isinstance(level, int) or isinstance(level, bool) or level < 1:
            raise AllyContextError(f"candidatos.{entry_id}.nivel_minimo_normal inválido")
        _text(meta.get("arquivo"), f"candidatos.{entry_id}.arquivo")
    if sorted(seen_orders) != list(range(1, len(seen_orders) + 1)):
        raise AllyContextError("ordens de entrada devem formar 1..N")
    return data


def load_state(repo: Path, index: dict[str, Any] | None = None) -> dict[str, Any]:
    index = index or load_index(repo)
    data = _map(_load(repo / STATE), STATE.as_posix())
    if data.get("schema_estado_entradas") != 1 or data.get("natureza") != "controle_reservado":
        raise AllyContextError("estado de entradas inválido")
    states = _map(data.get("candidatos"), "estado_entradas.candidatos")
    if set(states) != set(index["candidatos"]):
        raise AllyContextError("estado de entradas não corresponde ao índice")
    anticipated: list[str] = []
    for entry_id, raw in states.items():
        item = _map(raw, f"estado_entradas.{entry_id}")
        if item.get("estado") not in VALID_STATES:
            raise AllyContextError(f"estado inválido para {entry_id}: {item.get('estado')}")
        if not isinstance(item.get("antecipado"), bool):
            raise AllyContextError(f"{entry_id}.antecipado deve ser booleano")
        if item["antecipado"] and item["estado"] == "latente":
            anticipated.append(entry_id)
        due = item.get("proxima_avaliacao")
        if due is not None:
            due = _map(due, f"{entry_id}.proxima_avaliacao")
            _text(due.get("data"), f"{entry_id}.proxima_avaliacao.data")
            _text(due.get("hora"), f"{entry_id}.proxima_avaliacao.hora")
        _list(item.get("historico_recente"), f"{entry_id}.historico_recente")
    if len(anticipated) > 1:
        raise AllyContextError("somente um aliado pode estar antecipado por vez")
    return data


def level(repo: Path) -> tuple[int, list[str]]:
    data = _map(_load(repo / RUNTIME), RUNTIME.as_posix())
    character = _map(data.get("personagem"), "runtime.personagem")
    value = character.get("nivel")
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise AllyContextError("runtime.personagem.nivel deve ser inteiro >= 1")
    return value, [RUNTIME.as_posix()]


def ordered(index: dict[str, Any]) -> list[str]:
    return [
        entry_id
        for entry_id, _ in sorted(
            index["candidatos"].items(), key=lambda pair: pair[1]["ordem"]
        )
    ]


def normal(index: dict[str, Any], state: dict[str, Any]) -> str | None:
    return next(
        (
            entry_id
            for entry_id in ordered(index)
            if state["candidatos"][entry_id]["estado"] == "latente"
        ),
        None,
    )


def anticipated(state: dict[str, Any]) -> str | None:
    return next(
        (
            entry_id
            for entry_id, item in state["candidatos"].items()
            if item["estado"] == "latente" and item["antecipado"]
        ),
        None,
    )


def focus(index: dict[str, Any], state: dict[str, Any]) -> str | None:
    return anticipated(state) or normal(index, state)


def context(
    repo: Path,
    *,
    arc_info: dict[str, Any] | None = None,
    supplied_level: int | None = None,
) -> dict[str, Any]:
    try:
        arc_info = arc_info or arcos.current(repo)
    except arcos.ArcContractError as exc:
        raise AllyContextError(str(exc)) from exc
    index = load_index(repo)
    state = load_state(repo, index)
    if supplied_level is None:
        current_level, level_sources = level(repo)
    else:
        if not isinstance(supplied_level, int) or isinstance(supplied_level, bool) or supplied_level < 1:
            raise AllyContextError("nível fornecido deve ser inteiro >= 1")
        current_level = supplied_level
        level_sources = []
    return {
        "arco": arc_info,
        "indice": index,
        "estado": state,
        "nivel": current_level,
        "foco": focus(index, state),
        "fontes_lidas": list(
            dict.fromkeys(
                [
                    *arc_info.get("fontes_lidas", []),
                    INDEX.as_posix(),
                    STATE.as_posix(),
                    *level_sources,
                ]
            )
        ),
    }


def _window_open(item: dict[str, Any]) -> bool:
    if item.get("proxima_avaliacao") is not None:
        return False
    history = item.get("historico_recente") or []
    return any(
        isinstance(entry, dict) and entry.get("acao") == "abrir_janela_contextual"
        for entry in reversed(history)
    )


def gate(
    repo: Path,
    entry_id: str,
    *,
    ctx: dict[str, Any] | None = None,
    arc_info: dict[str, Any] | None = None,
    supplied_level: int | None = None,
) -> dict[str, Any]:
    entry_id = _text(entry_id, "entry_id")
    try:
        arc_info = arc_info or (ctx or {}).get("arco") or arcos.current(repo)
    except arcos.ArcContractError as exc:
        raise AllyContextError(str(exc)) from exc

    if entry_id not in set(arc_info["habilitacoes"]["aliados"]):
        return {
            "permitido": False,
            "entrada": entry_id,
            "motivo": "aliado_bloqueado_pelo_arco",
            "arco_id": arc_info["id"],
            "fontes_lidas": arc_info["fontes_lidas"],
        }

    ctx = ctx or context(repo, arc_info=arc_info, supplied_level=supplied_level)
    meta = ctx["indice"]["candidatos"].get(entry_id)
    if not isinstance(meta, dict):
        raise AllyContextError(f"aliado habilitado no arco não existe em entradas: {entry_id}")
    state = ctx["estado"]["candidatos"][entry_id]
    base = {
        "entrada": entry_id,
        "nome": meta["nome"],
        "arco_id": arc_info["id"],
        "estado": state["estado"],
        "antecipado": state["antecipado"],
        "ordem": meta["ordem"],
        "nivel_atual": int(ctx["nivel"]),
        "nivel_minimo": int(meta["nivel_minimo_normal"]),
        "candidato_em_foco": ctx["foco"],
        "fontes_lidas": ctx["fontes_lidas"],
    }

    if state["estado"] == "presente":
        return {**base, "permitido": False, "motivo": "aliado_ja_presente"}
    if state["estado"] == "inviavel":
        return {**base, "permitido": False, "motivo": "aliado_inviavel"}
    if ctx["foco"] != entry_id:
        return {**base, "permitido": False, "motivo": "aguarda_ordem_preferencial"}
    if state.get("proxima_avaliacao") is not None:
        return {
            **base,
            "permitido": False,
            "motivo": "janela_contextual_ainda_fechada",
            "proxima_avaliacao": state["proxima_avaliacao"],
        }
    if not _window_open(state):
        return {**base, "permitido": False, "motivo": "janela_contextual_nao_aberta"}
    if not state["antecipado"] and int(ctx["nivel"]) < int(meta["nivel_minimo_normal"]):
        return {**base, "permitido": False, "motivo": "nivel_minimo_nao_alcancado"}

    return {
        **base,
        "permitido": True,
        "motivo": "janela_contextual_aberta",
        "modo": "avaliar_entrada_organica",
        "regra": "janela aberta permite somente avaliação contextual; não confirma aparição",
    }


def gates(
    repo: Path,
    entry_ids: Iterable[str],
    *,
    arc_info: dict[str, Any] | None = None,
    supplied_level: int | None = None,
) -> dict[str, Any]:
    ids = list(dict.fromkeys(_text(item, "entry_id") for item in entry_ids))
    if not ids:
        return {"resultados": {}, "fontes_lidas": []}
    try:
        arc_info = arc_info or arcos.current(repo)
    except arcos.ArcContractError as exc:
        raise AllyContextError(str(exc)) from exc

    # O arco pode eliminar todos os candidatos antes de ler a camada de entradas.
    allowed = set(arc_info["habilitacoes"]["aliados"])
    results: dict[str, dict[str, Any]] = {}
    remaining: list[str] = []
    for entry_id in ids:
        if entry_id not in allowed:
            results[entry_id] = {
                "permitido": False,
                "entrada": entry_id,
                "motivo": "aliado_bloqueado_pelo_arco",
                "arco_id": arc_info["id"],
                "fontes_lidas": arc_info["fontes_lidas"],
            }
        else:
            remaining.append(entry_id)
    if not remaining:
        return {"resultados": results, "fontes_lidas": arc_info["fontes_lidas"]}

    ctx = context(repo, arc_info=arc_info, supplied_level=supplied_level)
    for entry_id in remaining:
        results[entry_id] = gate(repo, entry_id, ctx=ctx, arc_info=arc_info)
    return {"resultados": results, "fontes_lidas": ctx["fontes_lidas"]}


def status(repo: Path) -> dict[str, Any]:
    ctx = context(repo)
    current = ctx["foco"]
    gate_result = gate(repo, current, ctx=ctx, arc_info=ctx["arco"]) if current else None
    return {
        "arco_id": ctx["arco"]["id"],
        "candidato_em_foco": current,
        "janela_contextual_aberta": bool(gate_result and gate_result.get("permitido")),
        "gate": gate_result,
        "fontes_lidas": ctx["fontes_lidas"],
    }


def validate(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        arc_info = arcos.current(repo)
        index = load_index(repo)
        load_state(repo, index)
        level(repo)
        missing = sorted(set(arc_info["habilitacoes"]["aliados"]) - set(index["candidatos"]))
        if missing:
            errors.append("aliados habilitados ausentes do índice de entradas: " + ", ".join(missing))
    except (AllyContextError, arcos.ArcContractError) as exc:
        errors.append(str(exc))
    return {"ok": not errors, "erros": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validar")
    sub.add_parser("status")
    gate_parser = sub.add_parser("gate")
    gate_parser.add_argument("entrada")
    args = parser.parse_args(argv)
    try:
        if args.cmd == "validar":
            result = validate(args.repo.resolve())
            print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
            return 0 if result["ok"] else 1
        if args.cmd == "status":
            result = status(args.repo.resolve())
            print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
            return 0
        result = gate(args.repo.resolve(), args.entrada)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0
    except (AllyContextError, arcos.ArcContractError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
