#!/usr/bin/env python3
"""Pressão canônica de Ravens Bluff e ponte determinística com o Mundo Vivo.

O calendário nunca sobe uma frente sozinho. O Mundo Vivo pode, porém, reavaliar
agentes autônomos sem qualquer iniciativa de Ren. Se uma dessas reavaliações
produzir uma ação canônica e o método escolhido estiver roteado neste perfil, a
resolução pode subir no máximo uma frente de pressão em um nível.

A integração é pós-cânone e idempotente: a transação precisa constar no ledger da
sessão. Se o processo cair depois da pressão e antes de concluir a pendência, o
retry reconhece o mesmo ID transacional e não duplica o avanço.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml

import agentes
import metodos_agentes

PROFILE = Path("narrador/arcos/parte_1/pressao-ravens-bluff.yaml")
STATE = Path("narrador/arcos/parte_1/estado-pressao-ravens-bluff.yaml")
MAX_HISTORY = 24
MAX_WORLD_ROUTES = 32
MAX_WORLD_EFFECTS = 4
BANNED_EVIDENCE_PREFIX = Path("narrador/arcos")
TX_SESSION_RE = re.compile(r"^s(\d{3})-[a-z0-9]+$")


class PressureError(ValueError):
    pass


def load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise PressureError(str(exc)) from exc


def mp(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PressureError(f"{label} deve ser mapa")
    return value


def ls(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PressureError(f"{label} deve ser lista")
    return value


def txt(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PressureError(f"{label} deve ser texto não vazio")
    return value.strip()


def norm(value: Any) -> str:
    return " ".join(str(value).split())


def rel(value: Any, label: str) -> Path:
    path = Path(txt(value, label))
    if path.is_absolute() or ".." in path.parts:
        raise PressureError(f"{label} deve ficar no repositório")
    return path


def atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
        handle.flush()
        os.fsync(handle.fileno())
        temp = Path(handle.name)
    os.replace(temp, path)


def configured(repo: Path) -> bool:
    return (repo / PROFILE).is_file() and (repo / STATE).is_file()


def _integration(profile: dict[str, Any]) -> dict[str, Any]:
    raw = profile.get("integracao_mundo_vivo")
    if raw is None:
        return {
            "max_frentes_por_resolucao": 1,
            "ausencia_de_acao_de_ren_bloqueia": False,
            "regra": "integração não configurada",
            "rotas": [],
        }
    cfg = mp(raw, "integracao_mundo_vivo")
    if cfg.get("max_frentes_por_resolucao") != 1:
        raise PressureError("integração do Mundo Vivo deve limitar uma frente por resolução")
    if cfg.get("ausencia_de_acao_de_ren_bloqueia") is not False:
        raise PressureError("ausência de ação de Ren não pode bloquear pressão autônoma")
    txt(cfg.get("regra"), "integracao_mundo_vivo.regra")
    routes = ls(cfg.get("rotas"), "integracao_mundo_vivo.rotas")
    if len(routes) > MAX_WORLD_ROUTES:
        raise PressureError(f"integração excede {MAX_WORLD_ROUTES} rotas")
    return cfg


def _validate_world_routes(profile: dict[str, Any], fronts: dict[str, Any], lo: int, hi: int) -> None:
    cfg = _integration(profile)
    seen: set[tuple[str, str, str]] = set()
    for index, raw in enumerate(cfg.get("rotas") or []):
        label = f"integracao_mundo_vivo.rotas[{index}]"
        route = mp(raw, label)
        extra = set(route) - {"agente", "linha", "metodo", "efeitos"}
        if extra:
            raise PressureError(f"{label} contém campos desconhecidos: {', '.join(sorted(extra))}")
        agent = txt(route.get("agente"), f"{label}.agente")
        line = txt(route.get("linha"), f"{label}.linha")
        method = txt(route.get("metodo"), f"{label}.metodo")
        key = (agent, line, method)
        if key in seen:
            raise PressureError(f"rota do Mundo Vivo duplicada: {agent}/{line}/{method}")
        seen.add(key)
        effects = ls(route.get("efeitos"), f"{label}.efeitos")
        if not effects or len(effects) > MAX_WORLD_EFFECTS:
            raise PressureError(f"{label}.efeitos deve ter entre 1 e {MAX_WORLD_EFFECTS} itens")
        effect_fronts: set[str] = set()
        for eindex, eraw in enumerate(effects):
            elabel = f"{label}.efeitos[{eindex}]"
            effect = mp(eraw, elabel)
            if set(effect) != {"frente", "niveis_destino"}:
                raise PressureError(f"{elabel} deve conter apenas frente e niveis_destino")
            front = txt(effect.get("frente"), f"{elabel}.frente")
            if front not in fronts:
                raise PressureError(f"{elabel}: frente inexistente: {front}")
            if front in effect_fronts:
                raise PressureError(f"{label}: frente repetida: {front}")
            effect_fronts.add(front)
            if line not in fronts[front]["linhas_relacionadas"]:
                raise PressureError(
                    f"{agent}/{line}/{method}: frente {front} não é relacionada à linha"
                )
            targets = ls(effect.get("niveis_destino"), f"{elabel}.niveis_destino")
            if not targets or any(
                not isinstance(item, int) or isinstance(item, bool) or not lo < item <= hi
                for item in targets
            ):
                raise PressureError(f"{elabel}.niveis_destino deve conter níveis entre {lo + 1} e {hi}")
            if targets != sorted(set(targets)):
                raise PressureError(f"{elabel}.niveis_destino deve ser ordenado e sem duplicatas")


def load_profile(repo: Path) -> dict[str, Any]:
    data = mp(load(repo / PROFILE), str(PROFILE))
    if data.get("schema_pressao_ravens_bluff") != 1 or data.get("natureza") != "reservado":
        raise PressureError("perfil de pressão inválido")
    rules = mp(data.get("regras"), "regras")
    lo = rules.get("nivel_minimo")
    hi = rules.get("nivel_maximo")
    if (
        lo != 0
        or hi != 4
        or rules.get("mudanca_maxima_por_registro") != 1
        or rules.get("avanco_automatico") is not False
    ):
        raise PressureError("regras de pressão divergiram do contrato")
    fronts = mp(data.get("frentes"), "frentes")
    if not fronts:
        raise PressureError("frentes ausentes")
    for front_id, raw in fronts.items():
        front = mp(raw, f"frentes.{front_id}")
        txt(front.get("nome"), f"{front_id}.nome")
        lines = ls(front.get("linhas_relacionadas"), f"{front_id}.linhas_relacionadas")
        if not lines:
            raise PressureError(f"{front_id}: precisa de linha relacionada")
        levels = ls(front.get("niveis"), f"{front_id}.niveis")
        if [item.get("nivel") for item in levels] != list(range(lo, hi + 1)):
            raise PressureError(f"{front_id}: níveis devem formar {lo}..{hi}")
        for item in levels:
            txt(item.get("titulo"), f"{front_id}.titulo")
            signals = ls(item.get("sinais"), f"{front_id}.sinais")
            if not signals or any(not isinstance(signal, str) or not signal.strip() for signal in signals):
                raise PressureError(f"{front_id}: sinais inválidos")
    _validate_world_routes(data, fronts, lo, hi)
    return data


def load_state(repo: Path, profile: dict[str, Any] | None = None) -> dict[str, Any]:
    profile = profile or load_profile(repo)
    data = mp(load(repo / STATE), str(STATE))
    if (
        data.get("schema_estado_pressao_ravens_bluff") != 1
        or data.get("natureza") != "controle_reservado"
    ):
        raise PressureError("estado de pressão inválido")
    fronts = mp(data.get("frentes"), "estado.frentes")
    if set(fronts) != set(profile["frentes"]):
        raise PressureError("estado de pressão diverge do perfil")
    for front_id, item in fronts.items():
        item = mp(item, f"estado.{front_id}")
        level = item.get("nivel")
        if not isinstance(level, int) or isinstance(level, bool) or not 0 <= level <= 4:
            raise PressureError(f"{front_id}: nível inválido")
        history = ls(item.get("historico_recente"), f"{front_id}.historico_recente")
        if len(history) > MAX_HISTORY:
            raise PressureError(f"{front_id}: histórico excedeu teto")
    return data


def _routes_for(profile: dict[str, Any], agent_id: str) -> list[dict[str, Any]]:
    return [
        route
        for route in (_integration(profile).get("rotas") or [])
        if route.get("agente") == agent_id
    ]


def _route_for(
    profile: dict[str, Any], agent_id: str, line_id: str, method_id: str
) -> dict[str, Any] | None:
    for route in _routes_for(profile, agent_id):
        if route.get("linha") == line_id and route.get("metodo") == method_id:
            return route
    return None


def _next_effect(
    profile: dict[str, Any], state: dict[str, Any], route: dict[str, Any]
) -> dict[str, Any] | None:
    for effect in route.get("efeitos") or []:
        front_id = effect["frente"]
        current = int(state["frentes"][front_id]["nivel"])
        target = current + 1
        if target not in effect["niveis_destino"]:
            continue
        level_meta = profile["frentes"][front_id]["niveis"][target]
        return {
            "frente": front_id,
            "de": current,
            "para": target,
            "titulo_destino": level_meta["titulo"],
            "sinais_destino": list(level_meta["sinais"]),
        }
    return None


def _candidate_from(
    profile: dict[str, Any], state: dict[str, Any], agent_id: str
) -> dict[str, Any] | None:
    for route in _routes_for(profile, agent_id):
        effect = _next_effect(profile, state, route)
        if effect is None:
            continue
        return {
            "agente": agent_id,
            "linha": route["linha"],
            "metodo": route["metodo"],
            **effect,
            "regra": "candidato autônomo; ausência de ação de Ren não bloqueia, mas restrições canônicas do agente ainda valem",
        }
    return None


def candidate_for_agent(repo: Path, agent_id: str) -> dict[str, Any] | None:
    if not configured(repo):
        return None
    profile = load_profile(repo)
    state = load_state(repo, profile)
    return _candidate_from(profile, state, agent_id)


def candidate_for_pending(repo: Path, pending: dict[str, Any]) -> dict[str, Any] | None:
    if pending.get("tipo") != "reavaliar_agente":
        return None
    agent_id = pending.get("agente")
    if not isinstance(agent_id, str) or not agent_id:
        return None
    candidate = candidate_for_agent(repo, agent_id)
    if candidate is None:
        return None
    return {"pendencia": pending.get("id"), **candidate}


def pending_candidates(repo: Path, pending: list[dict[str, Any]]) -> dict[str, Any]:
    if not configured(repo):
        return {"candidatos": [], "fontes_lidas": []}
    profile = load_profile(repo)
    state = load_state(repo, profile)
    candidates: list[dict[str, Any]] = []
    for item in pending:
        if not isinstance(item, dict) or item.get("tipo") != "reavaliar_agente":
            continue
        agent_id = item.get("agente")
        if not isinstance(agent_id, str):
            continue
        candidate = _candidate_from(profile, state, agent_id)
        if candidate is not None:
            candidates.append({"pendencia": item.get("id"), **candidate})
    return {
        "candidatos": candidates,
        "fontes_lidas": [PROFILE.as_posix(), STATE.as_posix()],
    }


def _agent_method(repo: Path, agent_id: str, line_id: str, method_id: str) -> dict[str, Any]:
    try:
        loaded = agentes.load_agent_complete(repo, agent_id)
        methods = metodos_agentes.for_line(
            loaded["resultado"], line_id, expected_agent_id=agent_id
        )
    except (agentes.AgentValidationError, metodos_agentes.AgentMethodError) as exc:
        raise PressureError(str(exc)) from exc
    for method in methods:
        if method["id"] == method_id:
            return method
    raise PressureError(f"método {agent_id}/{line_id}/{method_id} não existe")


def validate_world_resolution(
    repo: Path,
    pending: dict[str, Any],
    line_id: str,
    method_id: str,
) -> dict[str, Any]:
    if pending.get("tipo") != "reavaliar_agente":
        raise PressureError("integração de pressão exige pendência reavaliar_agente")
    agent_id = txt(pending.get("agente"), "pendencia.agente")
    line_id = txt(line_id, "linha")
    method_id = txt(method_id, "metodo")
    _agent_method(repo, agent_id, line_id, method_id)
    profile = load_profile(repo)
    state = load_state(repo, profile)
    route = _route_for(profile, agent_id, line_id, method_id)
    effect = _next_effect(profile, state, route) if route is not None else None
    return {
        "agente": agent_id,
        "linha": line_id,
        "metodo": method_id,
        "rota_pressao": route is not None,
        "efeito_elegivel": effect,
    }


def _transaction_session(transaction_id: str) -> int:
    match = TX_SESSION_RE.fullmatch(txt(transaction_id, "transacao"))
    if not match:
        raise PressureError(f"id transacional inválido para resolução do mundo: {transaction_id!r}")
    return int(match.group(1))


def _ledger_path(transaction_id: str) -> Path:
    session = _transaction_session(transaction_id)
    return Path("sessoes") / f"{session:03d}" / "consolidacoes.jsonl"


def _transaction_in_ledger(repo: Path, transaction_id: str) -> Path:
    ledger = _ledger_path(transaction_id)
    path = repo / ledger
    if not path.is_file():
        raise PressureError(f"ledger da transação não existe: {ledger}")
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PressureError(f"ledger inválido em {ledger}:{number}: {exc}") from exc
        if transaction_id in (item.get("transacoes") or []):
            return ledger
    raise PressureError(
        f"transação {transaction_id} ainda não foi consolidada; pressione só depois do checkpoint"
    )


def _history_for_transaction(state: dict[str, Any], transaction_id: str) -> tuple[str, dict[str, Any]] | None:
    for front_id, item in state["frentes"].items():
        for entry in item.get("historico_recente") or []:
            if isinstance(entry, dict) and entry.get("transacao") == transaction_id:
                return front_id, entry
    return None


def apply_world_resolution(
    repo: Path,
    pending: dict[str, Any],
    transaction_id: str,
    line_id: str,
    method_id: str,
    note: str,
) -> dict[str, Any]:
    validation = validate_world_resolution(repo, pending, line_id, method_id)
    profile = load_profile(repo)
    state = load_state(repo, profile)
    existing = _history_for_transaction(state, transaction_id)
    if existing is not None:
        front_id, entry = existing
        return {
            "ok": True,
            "alterou": False,
            "ja_aplicada": True,
            "frente": front_id,
            "registro": entry,
            "fontes_lidas": [PROFILE.as_posix(), STATE.as_posix()],
        }

    ledger = _transaction_in_ledger(repo, transaction_id)
    route = _route_for(
        profile,
        validation["agente"],
        validation["linha"],
        validation["metodo"],
    )
    if route is None:
        return {
            "ok": True,
            "alterou": False,
            "ja_aplicada": False,
            "motivo": "método canônico não está roteado para uma frente de pressão",
            "fontes_lidas": [PROFILE.as_posix(), STATE.as_posix(), ledger.as_posix()],
        }
    effect = _next_effect(profile, state, route)
    if effect is None:
        return {
            "ok": True,
            "alterou": False,
            "ja_aplicada": False,
            "motivo": "rota não possui próximo degrau elegível no estado atual",
            "fontes_lidas": [PROFILE.as_posix(), STATE.as_posix(), ledger.as_posix()],
        }

    front_id = effect["frente"]
    record = {
        "de": effect["de"],
        "para": effect["para"],
        "fonte": ledger.as_posix(),
        "evidencia": f"transacao:{transaction_id}",
        "origem": f"mundo:{txt(pending.get('id'), 'pendencia.id')}",
        "nota": txt(note, "nota"),
        "transacao": transaction_id,
        "pendencia_mundo": pending["id"],
        "agente": validation["agente"],
        "linha": validation["linha"],
        "metodo": validation["metodo"],
    }
    state["frentes"][front_id]["nivel"] = effect["para"]
    history = state["frentes"][front_id]["historico_recente"]
    history.append(record)
    state["frentes"][front_id]["historico_recente"] = history[-MAX_HISTORY:]
    atomic(repo / STATE, state)
    return {
        "ok": True,
        "alterou": True,
        "ja_aplicada": False,
        "frente": front_id,
        "de": effect["de"],
        "para": effect["para"],
        "registro": record,
        "regra": "ação autônoma canônica move no máximo uma frente; Ren não recebe a causa automaticamente",
        "fontes_lidas": [PROFILE.as_posix(), STATE.as_posix(), ledger.as_posix()],
    }


def _validate_route_references(repo: Path, profile: dict[str, Any]) -> None:
    cache: dict[str, dict[str, Any]] = {}
    for route in _integration(profile).get("rotas") or []:
        agent_id = route["agente"]
        if agent_id not in cache:
            try:
                cache[agent_id] = agentes.load_agent_complete(repo, agent_id)["resultado"]
            except agentes.AgentValidationError as exc:
                raise PressureError(str(exc)) from exc
        try:
            methods = metodos_agentes.for_line(
                cache[agent_id], route["linha"], expected_agent_id=agent_id
            )
        except metodos_agentes.AgentMethodError as exc:
            raise PressureError(str(exc)) from exc
        if route["metodo"] not in {method["id"] for method in methods}:
            raise PressureError(
                f"rota aponta método inexistente: {agent_id}/{route['linha']}/{route['metodo']}"
            )


def validate(repo: Path) -> dict[str, Any]:
    try:
        profile = load_profile(repo)
        load_state(repo, profile)
        _validate_route_references(repo, profile)
        return {
            "ok": True,
            "frentes": len(profile["frentes"]),
            "rotas_mundo_vivo": len(_integration(profile).get("rotas") or []),
            "erros": [],
            "fontes_lidas": [PROFILE.as_posix(), STATE.as_posix()],
        }
    except PressureError as exc:
        return {"ok": False, "frentes": 0, "rotas_mundo_vivo": 0, "erros": [str(exc)], "fontes_lidas": []}


def status(repo: Path) -> dict[str, Any]:
    profile = load_profile(repo)
    state = load_state(repo, profile)
    rows = []
    for front_id, meta in profile["frentes"].items():
        level = state["frentes"][front_id]["nivel"]
        current = meta["niveis"][level]
        next_level = meta["niveis"][level + 1] if level < 4 else None
        rows.append(
            {
                "id": front_id,
                "nome": meta["nome"],
                "nivel": level,
                "titulo": current["titulo"],
                "sinais_atuais": current["sinais"],
                "proximo_nivel": (
                    {"nivel": next_level["nivel"], "titulo": next_level["titulo"]}
                    if next_level
                    else None
                ),
            }
        )
    cfg = _integration(profile)
    return {
        "arco": profile["arco"],
        "frentes": rows,
        "integracao_mundo_vivo": {
            "rotas": len(cfg.get("rotas") or []),
            "max_frentes_por_resolucao": cfg["max_frentes_por_resolucao"],
            "ausencia_de_acao_de_ren_bloqueia": cfg["ausencia_de_acao_de_ren_bloqueia"],
        },
        "regra": "níveis registram pressão canônica; não concedem descoberta da causa a Ren",
        "fontes_lidas": [PROFILE.as_posix(), STATE.as_posix()],
    }


def adjust(
    repo: Path,
    front: str,
    delta: int,
    source: str,
    evidence: str,
    origin: str,
    note: str,
) -> dict[str, Any]:
    if delta not in {-1, 1}:
        raise PressureError("delta deve ser -1 ou 1")
    profile = load_profile(repo)
    state = load_state(repo, profile)
    if front not in profile["frentes"]:
        raise PressureError(f"frente inexistente: {front}")
    src = rel(source, "fonte")
    if src == BANNED_EVIDENCE_PREFIX or BANNED_EVIDENCE_PREFIX in src.parents:
        raise PressureError("arquivo de planejamento do arco não pode provar sua própria pressão")
    path = repo / src
    if not path.is_file():
        raise PressureError(f"fonte canônica inexistente: {src}")
    ev = txt(evidence, "evidencia")
    if norm(ev) not in norm(path.read_text(encoding="utf-8")):
        raise PressureError("evidência literal não localizada na fonte")
    current = state["frentes"][front]["nivel"]
    target = current + delta
    if not 0 <= target <= 4:
        raise PressureError("mudança sairia do intervalo 0..4")
    item = {
        "de": current,
        "para": target,
        "fonte": src.as_posix(),
        "evidencia": ev,
        "origem": txt(origin, "origem"),
        "nota": txt(note, "nota"),
    }
    state["frentes"][front]["nivel"] = target
    state["frentes"][front]["historico_recente"].append(item)
    state["frentes"][front]["historico_recente"] = state["frentes"][front]["historico_recente"][-MAX_HISTORY:]
    atomic(repo / STATE, state)
    return {
        "ok": True,
        "frente": front,
        "de": current,
        "para": target,
        "registro": item,
        "regra": "mudança de pressão não revela automaticamente causa a Ren",
        "fontes_lidas": [PROFILE.as_posix(), STATE.as_posix(), src.as_posix()],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validar")
    sub.add_parser("status")
    candidate = sub.add_parser("candidato")
    candidate.add_argument("agente")
    change = sub.add_parser("ajustar")
    change.add_argument("frente")
    change.add_argument("--delta", type=int, choices=[-1, 1], required=True)
    change.add_argument("--fonte", required=True)
    change.add_argument("--evidencia", required=True)
    change.add_argument("--origem", required=True)
    change.add_argument("--nota", required=True)
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "validar":
            result = validate(repo)
        elif args.cmd == "status":
            result = status(repo)
        elif args.cmd == "candidato":
            result = {
                "agente": args.agente,
                "candidato": candidate_for_agent(repo, args.agente),
                "fontes_lidas": [PROFILE.as_posix(), STATE.as_posix()],
            }
        else:
            result = adjust(
                repo,
                args.frente,
                args.delta,
                args.fonte,
                args.evidencia,
                args.origem,
                args.nota,
            )
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0 if result.get("ok", True) else 1
    except PressureError as exc:
        print(f"erro: {exc}", file=__import__("sys").stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
