#!/usr/bin/env python3
"""Baralho determinístico e reativo de microeventos locais.

A camada só é acionada quando uma cena já possui gatilho local canônico. Ela usa
um baralho de ocorrência (rotina/microevento) e um baralho de cartas filtrado pela
ecologia do local. Sorteio é candidato operacional, não fato canônico.

A Task 13 adiciona pressão global de seca derivada do próprio histórico recente:
o baralho-base continua 3:1, mas algumas fichas de rotina podem ser promovidas
quando muitas cenas locais seguidas não produziram sequer candidato de incidente.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

import ecologia_local
import locais
import pressao_aventura

INDEX = Path("narrador/microeventos-locais/index.yaml")
STATE = Path("narrador/microeventos-locais/estado.yaml")
MAX_INDEX_BYTES = 16 * 1024
MAX_STATE_BYTES = 16 * 1024
MAX_CARDS = 24
MAX_CARD_TAGS = 8
MAX_CARD_CHANNELS = 4
MAX_PREMISE_CHARS = 260
MAX_HISTORY = 64
MIN_ELIGIBLE_PER_LOCAL = 2
VALID_RESULTS = {"rotina", "microevento"}
VALID_CATEGORIES = {"fluxo", "servico", "manutencao", "movimento", "ambiente", "trabalho", "controle"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,79}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
CARD_FIELDS = {"nome", "categoria", "canais", "tags", "premissa"}


class LocalMicroeventError(ValueError):
    """Erro de contrato do baralho local."""


def configured(repo: Path) -> bool:
    return (repo / INDEX).is_file() and (repo / STATE).is_file()


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise LocalMicroeventError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LocalMicroeventError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise LocalMicroeventError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LocalMicroeventError(f"{label} deve ser texto não vazio")
    return value.strip()


def _id(value: Any, label: str) -> str:
    value = _text(value, label)
    if not ID_RE.fullmatch(value):
        raise LocalMicroeventError(f"{label} deve ser slug ASCII minúsculo")
    return value


def _strings(value: Any, label: str, *, maximum: int) -> list[str]:
    raw = _list(value, label)
    if not 1 <= len(raw) <= maximum:
        raise LocalMicroeventError(f"{label} deve ter entre 1 e {maximum} itens")
    result = [_id(item, f"{label}[{i}]") for i, item in enumerate(raw)]
    if len(result) != len(set(result)):
        raise LocalMicroeventError(f"{label} não pode conter duplicatas")
    return result


def atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
        handle.flush()
        os.fsync(handle.fileno())
        tmp = Path(handle.name)
    os.replace(tmp, path)


def load_index(repo: Path) -> dict[str, Any]:
    path = repo / INDEX
    if path.is_file() and path.stat().st_size > MAX_INDEX_BYTES:
        raise LocalMicroeventError(
            f"catálogo de microeventos excede {MAX_INDEX_BYTES} bytes"
        )
    data = _map(_load(path), INDEX.as_posix())
    if (
        data.get("schema_microeventos_locais") != 1
        or data.get("natureza") != "reservado"
        or data.get("estatuto") != "moldes_nao_canonicos_ate_narracao"
    ):
        raise LocalMicroeventError("índice de microeventos locais inválido")
    _text(data.get("semente"), "semente")

    occurrence = _map(data.get("ocorrencia"), "ocorrencia")
    tokens = _list(occurrence.get("fichas"), "ocorrencia.fichas")
    seen: set[str] = set()
    results: list[str] = []
    for i, raw in enumerate(tokens):
        item = _map(raw, f"ocorrencia.fichas[{i}]")
        if set(item) != {"id", "resultado"}:
            raise LocalMicroeventError("ficha de ocorrência deve conter somente id e resultado")
        token_id = _id(item.get("id"), f"ocorrencia.fichas[{i}].id")
        result = _id(item.get("resultado"), f"ocorrencia.fichas[{i}].resultado")
        if token_id in seen or result not in VALID_RESULTS:
            raise LocalMicroeventError("ficha de ocorrência inválida ou duplicada")
        seen.add(token_id)
        results.append(result)
    if results.count("rotina") != 3 or results.count("microevento") != 1:
        raise LocalMicroeventError("baralho de ocorrência deve permanecer 3 rotina : 1 microevento")

    rules = _map(data.get("regras"), "regras")
    required_true = {
        "um_sorteio_por_cena_e_local",
        "exige_intersecao_de_canal_e_tag",
        "carta_e_candidata_nao_fato",
        "carta_incompativel_com_canone_pode_ser_descartada_sem_reroll",
    }
    for key in required_true:
        if rules.get(key) is not True:
            raise LocalMicroeventError(f"regras.{key} deve permanecer true")
    if rules.get("scheduler") != "proibido":
        raise LocalMicroeventError("scheduler de microeventos locais deve permanecer proibido")
    for key in (
        "npc_nomeado_automatico",
        "combate_automatico",
        "quest_automatica",
        "recompensa_automatica",
        "segredo_automatico",
    ):
        if rules.get(key) != "proibido":
            raise LocalMicroeventError(f"regras.{key} deve permanecer proibido")

    guardrails = _list(data.get("guardrails_globais"), "guardrails_globais")
    if not 1 <= len(guardrails) <= 4 or any(not isinstance(item, str) or not item.strip() for item in guardrails):
        raise LocalMicroeventError("guardrails_globais deve ter 1–4 textos")

    cards = _map(data.get("cartas"), "cartas")
    if not 1 <= len(cards) <= MAX_CARDS:
        raise LocalMicroeventError(f"catálogo deve ter entre 1 e {MAX_CARDS} cartas")
    for raw_id, raw in cards.items():
        card_id = _id(raw_id, "carta_id")
        card = _map(raw, f"cartas.{card_id}")
        if set(card) != CARD_FIELDS:
            raise LocalMicroeventError(
                f"{card_id}: campos inválidos; esperado={sorted(CARD_FIELDS)}"
            )
        _text(card.get("nome"), f"{card_id}.nome")
        category = _id(card.get("categoria"), f"{card_id}.categoria")
        if category not in VALID_CATEGORIES:
            raise LocalMicroeventError(f"{card_id}: categoria inválida")
        _strings(card.get("canais"), f"{card_id}.canais", maximum=MAX_CARD_CHANNELS)
        _strings(card.get("tags"), f"{card_id}.tags", maximum=MAX_CARD_TAGS)
        premise = _text(card.get("premissa"), f"{card_id}.premissa")
        if len(premise) > MAX_PREMISE_CHARS:
            raise LocalMicroeventError(
                f"{card_id}.premissa excede {MAX_PREMISE_CHARS} caracteres"
            )
    return data


def _validate_deck(deck: Any, label: str, *, allowed: set[str], card_deck: bool) -> dict[str, Any]:
    deck = _map(deck, label)
    expected = {"ciclo", "restantes", "assinatura_pool"} if card_deck else {"ciclo", "restantes"}
    if set(deck) != expected:
        raise LocalMicroeventError(f"{label}: campos de deck inválidos")
    cycle = deck.get("ciclo")
    if not isinstance(cycle, int) or isinstance(cycle, bool) or cycle < 0:
        raise LocalMicroeventError(f"{label}.ciclo deve ser inteiro >= 0")
    remaining = _list(deck.get("restantes"), f"{label}.restantes")
    if len(remaining) != len(set(remaining)) or set(remaining) - allowed:
        raise LocalMicroeventError(f"{label}.restantes contém ficha inválida/duplicada")
    if cycle == 0 and remaining:
        raise LocalMicroeventError(f"{label}: ciclo 0 exige restantes vazio")
    if card_deck:
        signature = deck.get("assinatura_pool")
        if signature is not None and (not isinstance(signature, str) or not SHA_RE.fullmatch(signature)):
            raise LocalMicroeventError(f"{label}.assinatura_pool inválida")
    return deck


def _validate_pressure_history(item: dict[str, Any], label: str) -> None:
    base = item.get("resultado_base")
    pressure = item.get("pressao_aventura")
    if base is None and pressure is None:
        return
    if base not in VALID_RESULTS:
        raise LocalMicroeventError(f"{label}.resultado_base inválido")
    pressure = _map(pressure, f"{label}.pressao_aventura")
    level = pressure.get("nivel")
    dry = pressure.get("cenas_secas_antes")
    promoted = pressure.get("promovido")
    if level not in {0, 1, 2, 3}:
        raise LocalMicroeventError(f"{label}.pressao_aventura.nivel inválido")
    if not isinstance(dry, int) or isinstance(dry, bool) or dry < 0:
        raise LocalMicroeventError(f"{label}.pressao_aventura.cenas_secas_antes inválido")
    if not isinstance(promoted, bool):
        raise LocalMicroeventError(f"{label}.pressao_aventura.promovido deve ser booleano")
    expected = "microevento" if promoted else base
    if item.get("resultado") != expected:
        raise LocalMicroeventError(f"{label}: resultado diverge da pressão registrada")


def load_state(repo: Path, index: dict[str, Any] | None = None) -> dict[str, Any]:
    index = index or load_index(repo)
    path = repo / STATE
    if path.is_file() and path.stat().st_size > MAX_STATE_BYTES:
        raise LocalMicroeventError(f"estado de microeventos excede {MAX_STATE_BYTES} bytes")
    data = _map(_load(path), STATE.as_posix())
    if (
        data.get("schema_estado_microeventos_locais") != 1
        or data.get("natureza") != "controle_reservado"
    ):
        raise LocalMicroeventError("estado de microeventos locais inválido")
    locations = _map(data.get("locais"), "estado.locais")
    token_ids = {item["id"] for item in index["ocorrencia"]["fichas"]}
    card_ids = set(index["cartas"])
    for local_id, raw in locations.items():
        locais._id(local_id)
        item = _map(raw, f"estado.locais.{local_id}")
        if set(item) != {"ocorrencia", "cartas"}:
            raise LocalMicroeventError(f"estado.locais.{local_id}: campos inválidos")
        _validate_deck(item["ocorrencia"], f"{local_id}.ocorrencia", allowed=token_ids, card_deck=False)
        _validate_deck(item["cartas"], f"{local_id}.cartas", allowed=card_ids, card_deck=True)
    history = _list(data.get("historico_recente"), "historico_recente")
    if len(history) > MAX_HISTORY:
        raise LocalMicroeventError(f"historico_recente excede {MAX_HISTORY} entradas")
    for i, raw in enumerate(history):
        item = _map(raw, f"historico_recente[{i}]")
        if not {"cena_id", "local_id", "ficha_ocorrencia", "resultado"} <= set(item):
            raise LocalMicroeventError("histórico de microevento incompleto")
        _text(item.get("cena_id"), f"historico_recente[{i}].cena_id")
        locais._id(item.get("local_id"))
        if item.get("resultado") not in VALID_RESULTS:
            raise LocalMicroeventError("histórico possui resultado inválido")
        card_id = item.get("carta_id")
        if card_id is not None and card_id not in card_ids:
            raise LocalMicroeventError("histórico referencia carta inexistente")
        _validate_pressure_history(item, f"historico_recente[{i}]")
    return data


def eligible_cards(index: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Filtra o catálogo em memória; não abre nenhuma fonte."""
    profile = ecologia_local._validate_profile("perfil", profile)
    channels = set(profile["canais_microevento"])
    tags = set(profile["tags"])
    result: list[dict[str, Any]] = []
    for card_id, card in sorted(index["cartas"].items()):
        channel_hits = sorted(channels & set(card["canais"]))
        tag_hits = sorted(tags & set(card["tags"]))
        if not channel_hits or not tag_hits:
            continue
        result.append(
            {
                "id": card_id,
                "canais": channel_hits,
                "tags": tag_hits,
            }
        )
    return result


def pool_signature(card_ids: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(card_ids)).encode("utf-8")).hexdigest()


def deck_order(seed: str, label: str, cycle: int, ids: list[str]) -> list[str]:
    return sorted(
        ids,
        key=lambda item: hashlib.sha256(
            f"{seed}|{label}|{cycle}|{item}".encode("utf-8")
        ).hexdigest(),
    )


def _draw_occurrence(deck: dict[str, Any], index: dict[str, Any], local_id: str) -> str:
    ids = [item["id"] for item in index["ocorrencia"]["fichas"]]
    if not deck["restantes"]:
        deck["ciclo"] += 1
        deck["restantes"] = deck_order(
            index["semente"], f"{local_id}:ocorrencia", deck["ciclo"], ids
        )
    return deck["restantes"].pop(0)


def _draw_card(
    deck: dict[str, Any],
    index: dict[str, Any],
    local_id: str,
    eligible: list[dict[str, Any]],
) -> str:
    ids = [item["id"] for item in eligible]
    signature = pool_signature(ids)
    if deck.get("assinatura_pool") != signature:
        deck["assinatura_pool"] = signature
        deck["restantes"] = []
    if not deck["restantes"]:
        deck["ciclo"] += 1
        deck["restantes"] = deck_order(
            index["semente"],
            f"{local_id}:cartas:{signature}",
            deck["ciclo"],
            ids,
        )
    return deck["restantes"].pop(0)


def _existing_history(state: dict[str, Any], local_id: str, scene_id: str) -> dict[str, Any] | None:
    for item in reversed(state.get("historico_recente") or []):
        if item.get("local_id") == local_id and item.get("cena_id") == scene_id:
            return item
    return None


def _public_result(
    index: dict[str, Any],
    profile: dict[str, Any],
    local_id: str,
    scene_id: str,
    history: dict[str, Any],
    eligible: list[dict[str, Any]],
    *,
    reused: bool,
) -> dict[str, Any]:
    result = history["resultado"]
    payload: dict[str, Any] = {
        "ok": True,
        "tipo": "microevento_local",
        "local_id": local_id,
        "cena_id": scene_id,
        "resultado": "avaliar_microevento" if result == "microevento" else "rotina",
        "ficha_ocorrencia": history["ficha_ocorrencia"],
        "reutilizado": reused,
        "cartas_elegiveis": len(eligible),
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix()],
        "regra": (
            "Carta é candidata não canônica. Pressão de seca só pode promover a chance de candidato; "
            "se conflitar com estado, arco, cena ou pendência, descartar a manifestação sem sortear substituta."
        ),
    }
    pressure = history.get("pressao_aventura")
    if isinstance(pressure, dict):
        payload["pressao_aventura"] = {
            "nivel": pressure["nivel"],
            "nome": pressure.get("nome", pressao_aventura.LEVEL_NAMES[pressure["nivel"]]),
            "cenas_secas_antes": pressure["cenas_secas_antes"],
            "promovido": pressure["promovido"],
        }
        payload["resultado_base"] = history.get("resultado_base")
    if result != "microevento":
        return payload

    card_id = history.get("carta_id")
    card = index["cartas"].get(card_id)
    if not isinstance(card, dict):
        raise LocalMicroeventError(f"histórico referencia carta ausente: {card_id}")
    match = next((item for item in eligible if item["id"] == card_id), None)
    if match is None:
        payload["resultado"] = "rotina"
        payload["motivo"] = "carta_historica_nao_compativel_com_ecologia_atual"
        return payload
    payload["carta"] = {
        "id": card_id,
        "nome": card["nome"],
        "categoria": card["categoria"],
        "premissa": card["premissa"],
        "canais_compativeis": match["canais"],
        "tags_compativeis": match["tags"],
        "atores_comuns": list(profile["atores_comuns"]),
        "guardrails": list(index["guardrails_globais"]),
    }
    return payload


def plan(
    repo: Path,
    *,
    local_id: str,
    scene_id: str,
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Planeja um sorteio sem persistir; o chamador decide quando comitar."""
    local_id = locais._id(local_id)
    scene_id = _text(scene_id, "cena_id")
    index = load_index(repo)
    state = load_state(repo, index)
    if local_id not in state["locais"]:
        raise LocalMicroeventError(f"estado sem deck para local canônico: {local_id}")
    profile = ecologia_local._validate_profile(local_id, profile)
    eligible = eligible_cards(index, profile)
    if len(eligible) < MIN_ELIGIBLE_PER_LOCAL:
        raise LocalMicroeventError(
            f"{local_id}: somente {len(eligible)} cartas compatíveis; mínimo {MIN_ELIGIBLE_PER_LOCAL}"
        )

    existing = _existing_history(state, local_id, scene_id)
    if existing is not None:
        return {
            "publico": _public_result(
                index, profile, local_id, scene_id, existing, eligible, reused=True
            ),
            "estado_planejado": state,
            "alterou": False,
        }

    planned = copy.deepcopy(state)
    local_state = planned["locais"][local_id]
    token_id = _draw_occurrence(local_state["ocorrencia"], index, local_id)
    token = next(item for item in index["ocorrencia"]["fichas"] if item["id"] == token_id)
    pressure = pressao_aventura.apply(
        list(state.get("historico_recente") or []),
        token_id=token_id,
        base_result=token["resultado"],
    )
    history: dict[str, Any] = {
        "cena_id": scene_id,
        "local_id": local_id,
        "ficha_ocorrencia": token_id,
        "resultado_base": token["resultado"],
        "resultado": pressure["resultado"],
        "pressao_aventura": {
            "nivel": pressure["nivel"],
            "nome": pressure["nome"],
            "cenas_secas_antes": pressure["cenas_secas_consecutivas"],
            "promovido": pressure["promovido"],
        },
    }
    if pressure["resultado"] == "microevento":
        history["carta_id"] = _draw_card(local_state["cartas"], index, local_id, eligible)
    planned["historico_recente"].append(history)
    planned["historico_recente"] = planned["historico_recente"][-MAX_HISTORY:]
    return {
        "publico": _public_result(
            index, profile, local_id, scene_id, history, eligible, reused=False
        ),
        "estado_planejado": planned,
        "alterou": True,
    }


def commit_plan(repo: Path, planned: dict[str, Any]) -> bool:
    """Persiste somente o estado já calculado; não sorteia novamente."""
    if not planned.get("alterou"):
        return False
    state = _map(planned.get("estado_planejado"), "estado_planejado")
    atomic(repo / STATE, state)
    return True


def simulate(repo: Path, local_ref: str, scene_id: str) -> dict[str, Any]:
    try:
        ecology = ecologia_local.lookup(repo, local_ref)
    except ecologia_local.LocalEcologyError as exc:
        raise LocalMicroeventError(str(exc)) from exc
    result = plan(
        repo,
        local_id=ecology["local_id"],
        scene_id=scene_id,
        profile=ecology["perfil"],
    )["publico"]
    result["fontes_lidas"] = list(
        dict.fromkeys([*ecology["fontes_lidas"], *result["fontes_lidas"]])
    )
    return result


def status(repo: Path, local_ref: str | None = None) -> dict[str, Any]:
    index = load_index(repo)
    state = load_state(repo, index)
    pressure = pressao_aventura.status_from_history(list(state.get("historico_recente") or []))
    if local_ref is None:
        return {
            "ok": True,
            "locais": len(state["locais"]),
            "historico_recente": len(state["historico_recente"]),
            "pressao_aventura": pressure,
            "fontes_lidas": [INDEX.as_posix(), STATE.as_posix()],
        }
    try:
        resolution = locais.resolve(repo, local_ref)
    except locais.LocationError as exc:
        raise LocalMicroeventError(str(exc)) from exc
    local_id = resolution["local_id"]
    if local_id not in state["locais"]:
        raise LocalMicroeventError(f"estado sem deck para local: {local_id}")
    item = state["locais"][local_id]
    return {
        "ok": True,
        "local_id": local_id,
        "ocorrencia": {
            "ciclo": item["ocorrencia"]["ciclo"],
            "restantes": len(item["ocorrencia"]["restantes"]),
        },
        "cartas": {
            "ciclo": item["cartas"]["ciclo"],
            "restantes": len(item["cartas"]["restantes"]),
        },
        "pressao_aventura": pressure,
        "fontes_lidas": list(
            dict.fromkeys([*resolution["fontes_lidas"], INDEX.as_posix(), STATE.as_posix()])
        ),
    }


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    card_count = 0
    try:
        index = load_index(repo)
        state = load_state(repo, index)
        ecology = ecologia_local.load_index(repo)
        coverage_errors = ecologia_local.validate_coverage(repo, ecology)
        errors.extend(coverage_errors)
        profiles = ecology["perfis"]
        if set(state["locais"]) != set(profiles):
            missing = sorted(set(profiles) - set(state["locais"]))
            extra = sorted(set(state["locais"]) - set(profiles))
            errors.append(f"estado/local diverge da ecologia: ausentes={missing}, extras={extra}")
        for local_id, profile in profiles.items():
            count = len(eligible_cards(index, profile))
            if count < MIN_ELIGIBLE_PER_LOCAL:
                errors.append(
                    f"{local_id}: somente {count} cartas compatíveis; mínimo {MIN_ELIGIBLE_PER_LOCAL}"
                )
        pressure = pressao_aventura.status_from_history(list(state.get("historico_recente") or []))
        if pressure["nivel"] not in {0, 1, 2, 3}:
            errors.append("pressão de aventura inválida")
        card_count = len(index["cartas"])
    except (
        LocalMicroeventError,
        ecologia_local.LocalEcologyError,
        locais.LocationError,
        pressao_aventura.AdventurePressureError,
    ) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "cartas": card_count,
        "erros": list(dict.fromkeys(errors)),
        "fontes_lidas": [
            locais.INDEX.as_posix(),
            ecologia_local.INDEX.as_posix(),
            INDEX.as_posix(),
            STATE.as_posix(),
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sim = sub.add_parser("simular", help="simula sem consumir uma cena local")
    sim.add_argument("local")
    sim.add_argument("--cena-id", required=True)
    stat = sub.add_parser("status", help="mostra estado compacto sem abrir cartas adicionais")
    stat.add_argument("local", nargs="?")
    sub.add_parser("check", help="valida catálogo, estado, ecologia e pressão de seca")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "simular":
            result = simulate(repo, args.local, args.cena_id)
        elif args.cmd == "status":
            result = status(repo, args.local)
        else:
            result = validate_repo(repo)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0 if result.get("ok", True) else 1
    except LocalMicroeventError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
