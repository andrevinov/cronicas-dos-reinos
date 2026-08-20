#!/usr/bin/env python3
"""Guardrail compacto de marcos de primeira aparição.

Esta camada não cria chegada, presença, cena, conhecimento ou ação. Ela existe para
responder, antes de uma descoberta contextual ou de uma movimentação controlada:

1. o NPC pertence ao arco corrente?
2. o nível mínimo já foi alcançado?
3. o marco narrativo de primeira aparição está bloqueado, elegível ou consumido?

``elegivel`` significa somente que uma cena concreta pode propor a primeira
aparição. ``consumido`` significa que a primeira aparição já ocorreu e o marco não
deve bloquear reaparições futuras. A fonte longa permanece em
``narrador/juppongatana/marcos-de-aparicao.md``; esta camada guarda apenas índice e
estado operacional mínimos.
"""
from __future__ import annotations

import argparse
import sys
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

import yaml

import arcos

INDEX = Path("narrador/arcos/marcos-aparicao.yaml")
STATE = Path("narrador/arcos/estado-marcos-aparicao.yaml")
RUNTIME = Path("runtime/contexto.yaml")
VALID_STATES = {"bloqueado", "elegivel", "consumido"}
MAX_HISTORY = 24


class AppearanceMilestoneError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise AppearanceMilestoneError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AppearanceMilestoneError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise AppearanceMilestoneError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AppearanceMilestoneError(f"{label} deve ser texto não vazio")
    return value.strip()


def _id(value: Any, label: str) -> str:
    value = _text(value, label)
    if any(ch.isspace() for ch in value):
        raise AppearanceMilestoneError(f"{label} deve ser ID sem espaços")
    return value


def _repo_path(repo: Path, raw: str) -> Path:
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        raise AppearanceMilestoneError(f"caminho fora do repositório: {raw}")
    return repo / rel


def _atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
        handle.flush()
        os.fsync(handle.fileno())
        tmp = Path(handle.name)
    os.replace(tmp, path)


def load_index(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / INDEX), INDEX.as_posix())
    if data.get("schema_marcos_aparicao") != 1:
        raise AppearanceMilestoneError("índice de marcos de aparição deve usar schema 1")
    if data.get("natureza") != "roteador_reservado":
        raise AppearanceMilestoneError("índice de marcos deve ser roteador_reservado")
    source = _text(data.get("fonte_canonica"), "fonte_canonica")
    _repo_path(repo, source)
    rules = _map(data.get("regras"), "regras")
    if rules.get("elegivel_nao_e_aparicao") is not True:
        raise AppearanceMilestoneError("regra elegivel_nao_e_aparicao deve ser true")
    if rules.get("consumido_nao_bloqueia_reaparicao") is not True:
        raise AppearanceMilestoneError(
            "regra consumido_nao_bloqueia_reaparicao deve ser true"
        )
    milestones = _map(data.get("marcos"), "marcos")
    if not milestones:
        raise AppearanceMilestoneError("marcos de aparição não podem ser vazios")
    for agent_id, raw in milestones.items():
        agent_id = _id(agent_id, "id de agente")
        meta = _map(raw, f"marcos.{agent_id}")
        allowed = {"arco", "grupo", "nivel_minimo", "secao_fonte", "condicao_id"}
        extra = set(meta) - allowed
        if extra:
            raise AppearanceMilestoneError(
                f"marcos.{agent_id} contém campos não permitidos: {', '.join(sorted(extra))}"
            )
        _id(meta.get("arco"), f"marcos.{agent_id}.arco")
        if _text(meta.get("grupo"), f"marcos.{agent_id}.grupo") != "antagonistas":
            raise AppearanceMilestoneError(
                f"marcos.{agent_id}.grupo deve ser antagonistas nesta etapa"
            )
        level = meta.get("nivel_minimo")
        if not isinstance(level, int) or isinstance(level, bool) or level < 1:
            raise AppearanceMilestoneError(
                f"marcos.{agent_id}.nivel_minimo deve ser inteiro >= 1"
            )
        _text(meta.get("secao_fonte"), f"marcos.{agent_id}.secao_fonte")
        _id(meta.get("condicao_id"), f"marcos.{agent_id}.condicao_id")
    return data


def load_state(repo: Path, index: dict[str, Any] | None = None) -> dict[str, Any]:
    index = index or load_index(repo)
    data = _map(_load(repo / STATE), STATE.as_posix())
    if data.get("schema_estado_marcos_aparicao") != 1:
        raise AppearanceMilestoneError("estado de marcos de aparição deve usar schema 1")
    if data.get("natureza") != "controle_reservado":
        raise AppearanceMilestoneError("estado de marcos deve ser controle_reservado")
    states = _map(data.get("marcos"), "estado.marcos")
    if set(states) != set(index["marcos"]):
        raise AppearanceMilestoneError("estado de marcos não corresponde ao índice")
    for agent_id, raw in states.items():
        item = _map(raw, f"estado.marcos.{agent_id}")
        state = _text(item.get("estado"), f"estado.marcos.{agent_id}.estado")
        if state not in VALID_STATES:
            raise AppearanceMilestoneError(
                f"estado de marco inválido para {agent_id}: {state}"
            )
        _text(item.get("origem"), f"estado.marcos.{agent_id}.origem")
        _text(item.get("nota"), f"estado.marcos.{agent_id}.nota")
        history = _list(item.get("historico_recente"), f"estado.marcos.{agent_id}.historico_recente")
        if len(history) > MAX_HISTORY:
            raise AppearanceMilestoneError(
                f"histórico de marco grande demais para {agent_id}"
            )
        for i, entry in enumerate(history):
            entry = _map(entry, f"estado.marcos.{agent_id}.historico_recente[{i}]")
            if _text(entry.get("acao"), "acao") not in {"marcar_elegivel", "consumir"}:
                raise AppearanceMilestoneError(
                    f"histórico de {agent_id} contém ação inválida"
                )
            _text(entry.get("origem"), "origem")
            _text(entry.get("nota"), "nota")
    return data


def level(repo: Path) -> tuple[int, list[str]]:
    data = _map(_load(repo / RUNTIME), RUNTIME.as_posix())
    character = _map(data.get("personagem"), "runtime.personagem")
    value = character.get("nivel")
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise AppearanceMilestoneError("runtime.personagem.nivel deve ser inteiro >= 1")
    return value, [RUNTIME.as_posix()]


def context(repo: Path, *, arc_info: dict[str, Any] | None = None, supplied_level: int | None = None) -> dict[str, Any]:
    try:
        arc_info = arc_info or arcos.current(repo)
    except arcos.ArcContractError as exc:
        raise AppearanceMilestoneError(str(exc)) from exc
    index = load_index(repo)
    state = load_state(repo, index)
    if supplied_level is None:
        current_level, level_sources = level(repo)
    else:
        if not isinstance(supplied_level, int) or isinstance(supplied_level, bool) or supplied_level < 1:
            raise AppearanceMilestoneError("nível fornecido deve ser inteiro >= 1")
        current_level = supplied_level
        level_sources = []
    return {
        "arco": arc_info,
        "indice": index,
        "estado": state,
        "nivel": current_level,
        "fontes_lidas": list(
            dict.fromkeys(
                [*arc_info.get("fontes_lidas", []), INDEX.as_posix(), STATE.as_posix(), *level_sources]
            )
        ),
    }


def gate(
    repo: Path,
    agent_id: str,
    *,
    ctx: dict[str, Any] | None = None,
    arc_info: dict[str, Any] | None = None,
    supplied_level: int | None = None,
) -> dict[str, Any]:
    """Avalia o marco sem abrir fragmento de agente nem fonte Markdown longa."""
    agent_id = _id(agent_id, "agent_id")

    # A trava de arco vem primeiro e pode encerrar sem pagar runtime/estado de marco.
    try:
        arc_info = arc_info or (ctx or {}).get("arco") or arcos.current(repo)
    except arcos.ArcContractError as exc:
        raise AppearanceMilestoneError(str(exc)) from exc
    arc_allowed = agent_id in set(arc_info["habilitacoes"]["antagonistas"])
    if not arc_allowed:
        return {
            "permitido": False,
            "agente": agent_id,
            "motivo": "agente_bloqueado_pelo_arco_antes_do_marco",
            "arco_id": arc_info["id"],
            "fontes_lidas": arc_info["fontes_lidas"],
        }

    ctx = ctx or context(repo, arc_info=arc_info, supplied_level=supplied_level)
    meta = ctx["indice"]["marcos"].get(agent_id)
    if not isinstance(meta, dict):
        return {
            "permitido": False,
            "agente": agent_id,
            "motivo": "agente_habilitado_sem_marco_de_aparicao",
            "arco_id": arc_info["id"],
            "fontes_lidas": ctx["fontes_lidas"],
        }
    if meta["arco"] != arc_info["id"]:
        return {
            "permitido": False,
            "agente": agent_id,
            "motivo": "marco_de_aparicao_pertence_a_outro_arco",
            "arco_id": arc_info["id"],
            "marco_arco_id": meta["arco"],
            "fontes_lidas": ctx["fontes_lidas"],
        }

    state = ctx["estado"]["marcos"][agent_id]
    current_level = int(ctx["nivel"])
    minimum = int(meta["nivel_minimo"])
    base = {
        "agente": agent_id,
        "arco_id": arc_info["id"],
        "estado_marco": state["estado"],
        "nivel_atual": current_level,
        "nivel_minimo": minimum,
        "condicao_id": meta["condicao_id"],
        "secao_fonte": meta["secao_fonte"],
        "fontes_lidas": ctx["fontes_lidas"],
    }
    if current_level < minimum:
        return {
            **base,
            "permitido": False,
            "motivo": "nivel_minimo_do_marco_nao_alcancado",
        }
    if state["estado"] == "bloqueado":
        return {
            **base,
            "permitido": False,
            "motivo": "condicao_narrativa_do_marco_ainda_bloqueada",
        }
    if state["estado"] == "elegivel":
        return {
            **base,
            "permitido": True,
            "motivo": "primeira_aparicao_pode_ser_avaliada",
            "modo": "avaliar_primeira_aparicao",
        }
    return {
        **base,
        "permitido": True,
        "motivo": "primeira_aparicao_ja_consumida",
        "modo": "reaparicao_nao_bloqueada_pelo_marco",
    }


def gates(
    repo: Path,
    agent_ids: Iterable[str],
    *,
    arc_info: dict[str, Any] | None = None,
    supplied_level: int | None = None,
) -> dict[str, Any]:
    ids = list(dict.fromkeys(_id(value, "agent_id") for value in agent_ids))
    if not ids:
        return {"resultados": {}, "fontes_lidas": []}
    try:
        arc_info = arc_info or arcos.current(repo)
    except arcos.ArcContractError as exc:
        raise AppearanceMilestoneError(str(exc)) from exc
    enabled = set(arc_info["habilitacoes"]["antagonistas"])
    if not any(agent_id in enabled for agent_id in ids):
        results = {
            agent_id: gate(repo, agent_id, arc_info=arc_info, supplied_level=supplied_level)
            for agent_id in ids
        }
        return {
            "resultados": results,
            "fontes_lidas": list(dict.fromkeys(source for result in results.values() for source in result["fontes_lidas"])),
        }
    ctx = context(repo, arc_info=arc_info, supplied_level=supplied_level)
    results = {agent_id: gate(repo, agent_id, ctx=ctx, arc_info=arc_info) for agent_id in ids}
    return {"resultados": results, "fontes_lidas": ctx["fontes_lidas"]}


def mutate(repo: Path, agent_id: str, *, action: str, origin: str, note: str) -> dict[str, Any]:
    agent_id = _id(agent_id, "agent_id")
    origin = _text(origin, "origem")
    note = _text(note, "nota")
    index = load_index(repo)
    state = load_state(repo, index)
    if agent_id not in index["marcos"]:
        raise AppearanceMilestoneError(f"marco de aparição inexistente: {agent_id}")
    item = state["marcos"][agent_id]
    before = item["estado"]
    if action == "marcar_elegivel":
        if before == "consumido":
            return {"ok": True, "alterou": False, "agente": agent_id, "estado": before}
        item["estado"] = "elegivel"
    elif action == "consumir":
        if before == "bloqueado":
            raise AppearanceMilestoneError(
                "marco bloqueado não pode ser consumido antes de se tornar elegível"
            )
        if before == "consumido":
            return {"ok": True, "alterou": False, "agente": agent_id, "estado": before}
        item["estado"] = "consumido"
    else:
        raise AppearanceMilestoneError(f"ação inválida: {action}")
    item["origem"] = origin
    item["nota"] = note
    item["historico_recente"].append({"acao": action, "origem": origin, "nota": note})
    item["historico_recente"] = item["historico_recente"][-MAX_HISTORY:]
    _atomic(repo / STATE, state)
    return {
        "ok": True,
        "alterou": item["estado"] != before,
        "agente": agent_id,
        "de": before,
        "para": item["estado"],
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix()],
    }


def validate(repo: Path, *, check_source: bool = True) -> dict[str, Any]:
    errors: list[str] = []
    try:
        index = load_index(repo)
        state = load_state(repo, index)
        arc_index = arcos.load_index(repo)
        source = index["fonte_canonica"]
        if check_source:
            source_path = _repo_path(repo, source)
            if not source_path.is_file():
                raise AppearanceMilestoneError(f"fonte canônica inexistente: {source}")
            source_text = source_path.read_text(encoding="utf-8")
            for agent_id, meta in index["marcos"].items():
                if meta["secao_fonte"] not in source_text:
                    errors.append(
                        f"{agent_id}: seção do marco não localizada em {source}: {meta['secao_fonte']}"
                    )
        for agent_id, meta in index["marcos"].items():
            if meta["arco"] not in arc_index["arcos"]:
                errors.append(f"{agent_id}: arco inexistente: {meta['arco']}")

        # Fail-closed: todo antagonista explicitamente habilitado em um contrato
        # precisa possuir marco, evitando que um arco futuro contorne a segunda trava.
        for arc_id in arc_index["arcos"]:
            contract = arcos.load_contract(repo, arc_id, arc_index)
            for agent_id in contract["habilitacoes"]["antagonistas"]:
                if agent_id not in index["marcos"]:
                    errors.append(
                        f"{arc_id}: antagonista habilitado sem marco de aparição: {agent_id}"
                    )
                elif index["marcos"][agent_id]["arco"] != arc_id:
                    errors.append(
                        f"{arc_id}: marco de {agent_id} pertence a {index['marcos'][agent_id]['arco']}"
                    )
        _ = state
    except (AppearanceMilestoneError, arcos.ArcContractError) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "quantidade": len(index["marcos"]) if "index" in locals() else 0,
        "erros": list(dict.fromkeys(errors)),
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), arcos.INDEX.as_posix()],
    }


def status(repo: Path) -> dict[str, Any]:
    ctx = context(repo)
    rows = {}
    for agent_id in ctx["indice"]["marcos"]:
        rows[agent_id] = gate(repo, agent_id, ctx=ctx, arc_info=ctx["arco"])
    return {
        "arco": {"id": ctx["arco"]["id"], "titulo": ctx["arco"]["titulo"]},
        "nivel": ctx["nivel"],
        "marcos": rows,
        "fontes_lidas": ctx["fontes_lidas"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    validate_cmd = sub.add_parser("validar")
    validate_cmd.add_argument(
        "--sem-fonte",
        action="store_true",
        help="valida somente controles; útil no bundle overlay antes de aplicá-lo ao repo completo",
    )
    show = sub.add_parser("mostrar")
    show.add_argument("agente")
    ready = sub.add_parser("marcar-elegivel")
    ready.add_argument("agente")
    ready.add_argument("--origem", required=True)
    ready.add_argument("--nota", required=True)
    consume = sub.add_parser("consumir")
    consume.add_argument("agente")
    consume.add_argument("--origem", required=True)
    consume.add_argument("--nota", required=True)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "status":
            result = status(repo)
        elif args.cmd == "validar":
            result = validate(repo, check_source=not args.sem_fonte)
            print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
            return 0 if result["ok"] else 1
        elif args.cmd == "mostrar":
            result = gate(repo, args.agente)
        elif args.cmd == "marcar-elegivel":
            result = mutate(
                repo, args.agente, action="marcar_elegivel", origin=args.origem, note=args.nota
            )
        else:
            result = mutate(
                repo, args.agente, action="consumir", origin=args.origem, note=args.nota
            )
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0
    except (AppearanceMilestoneError, arcos.ArcContractError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
