#!/usr/bin/env python3
"""Task 35 — incidentes sérios globais/locais, determinísticos e reativos.

A camada possui dois baralhos de ocorrência: um municipal e outro por local.
Incidente sorteado é somente candidato até entrar na narração aceita. Condições
persistentes da Task 34 podem habilitar cartas contextuais, mas nunca aumentam a
frequência dos baralhos. Não existe scheduler, scan global ou criação de sidequest.
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

INDEX = Path("narrador/incidentes-v2/index.yaml")
STATE = Path("narrador/incidentes-v2/estado.yaml")
SCHEMA = 1
MAX_INDEX_BYTES = 24 * 1024
MAX_STATE_BYTES = 16 * 1024
MAX_HISTORY = 48
MAX_CARDS = 32
MAX_ROUTES = 6
MAX_TEXT = 300
MIN_LOCAL_ELIGIBLE = 2
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,79}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
VALID_RESULTS = {"rotina", "incidente"}
VALID_SCOPES = {"global", "local"}
VALID_ACCESS = {"publico", "semipublico", "controlado", "privado"}
VALID_SEVERITY = {"baixa", "moderada", "alta"}
VALID_INTERVENTION = {"imediata"}
CARD_FIELDS = {
    "nome",
    "tipo",
    "escopos",
    "acessos",
    "canais",
    "tags",
    "condicoes_necessarias",
    "severidade",
    "intervencao",
    "premissa",
    "rotas",
}


class IncidentError(ValueError):
    pass


def configured(repo: Path) -> bool:
    return (repo / INDEX).is_file() and (repo / STATE).is_file()


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise IncidentError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IncidentError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise IncidentError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str, *, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IncidentError(f"{label} deve ser texto não vazio")
    text = value.strip()
    if len(text) > maximum:
        raise IncidentError(f"{label} excede {maximum} caracteres")
    return text


def _id(value: Any, label: str) -> str:
    value = _text(value, label, maximum=80)
    if not ID_RE.fullmatch(value):
        raise IncidentError(f"{label} deve ser slug ASCII minúsculo")
    return value


def _ids(value: Any, label: str, *, maximum: int, allow_empty: bool = True) -> list[str]:
    raw = _list(value, label)
    if len(raw) > maximum or (not allow_empty and not raw):
        raise IncidentError(f"{label} possui quantidade inválida")
    result = [_id(item, f"{label}[{i}]") for i, item in enumerate(raw)]
    if len(result) != len(set(result)):
        raise IncidentError(f"{label} não pode conter duplicatas")
    return result


def atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
        handle.flush()
        os.fsync(handle.fileno())
        temp = Path(handle.name)
    os.replace(temp, path)


def _validate_occurrence(raw: Any, label: str, *, expected_routine: int) -> list[dict[str, str]]:
    block = _map(raw, label)
    tokens = _list(block.get("fichas"), f"{label}.fichas")
    result: list[dict[str, str]] = []
    seen: set[str] = set()
    for i, item_raw in enumerate(tokens):
        item = _map(item_raw, f"{label}.fichas[{i}]")
        if set(item) != {"id", "resultado"}:
            raise IncidentError(f"{label}: ficha deve conter id e resultado")
        token_id = _id(item.get("id"), f"{label}.fichas[{i}].id")
        outcome = _id(item.get("resultado"), f"{label}.fichas[{i}].resultado")
        if token_id in seen or outcome not in VALID_RESULTS:
            raise IncidentError(f"{label}: ficha duplicada/inválida")
        seen.add(token_id)
        result.append({"id": token_id, "resultado": outcome})
    outcomes = [item["resultado"] for item in result]
    if outcomes.count("incidente") != 1 or outcomes.count("rotina") != expected_routine:
        raise IncidentError(
            f"{label} deve permanecer {expected_routine} rotina : 1 incidente"
        )
    return result


def load_index(repo: Path) -> dict[str, Any]:
    path = repo / INDEX
    if path.stat().st_size > MAX_INDEX_BYTES:
        raise IncidentError(f"índice de incidentes excede {MAX_INDEX_BYTES} bytes")
    data = _map(_load(path), INDEX.as_posix())
    if (
        data.get("schema_incidentes_mundo") != SCHEMA
        or data.get("natureza") != "reservado"
        or data.get("estatuto") != "candidatos_serios_nao_canonicos_ate_narracao"
        or data.get("cidade") != "ravens_bluff"
    ):
        raise IncidentError("índice de incidentes inválido")
    _text(data.get("semente"), "semente", maximum=100)
    frequency = _map(data.get("frequencia"), "frequencia")
    if set(frequency) != VALID_SCOPES:
        raise IncidentError("frequencia deve declarar global e local")
    _validate_occurrence(frequency["global"], "frequencia.global", expected_routine=11)
    _validate_occurrence(frequency["local"], "frequencia.local", expected_routine=7)

    rules = _map(data.get("regras"), "regras")
    required_true = {
        "incidente_e_candidato_ate_narracao",
        "condicao_persistente_muda_pool_nao_frequencia",
        "sem_npc_nomeado_automatico",
        "sem_sidequest_automatica",
        "sem_recompensa_automatica",
        "sem_segredo_automatico",
        "sem_conhecimento_automatico",
        "ren_pode_nao_intervir",
        "combate_nao_e_obrigatorio",
        "ameaca_desproporcional_exige_saida_observavel",
    }
    if any(rules.get(key) is not True for key in required_true):
        raise IncidentError("guardrails booleanos de incidentes foram relaxados")
    if rules.get("max_incidentes_por_cena") != 1:
        raise IncidentError("max_incidentes_por_cena deve permanecer 1")
    if rules.get("scheduler") != "proibido" or rules.get("reroll_por_incompatibilidade") != "proibido":
        raise IncidentError("scheduler/reroll de incidentes devem permanecer proibidos")

    guardrails = _list(data.get("guardrails_globais"), "guardrails_globais")
    if not 1 <= len(guardrails) <= 6 or any(not isinstance(item, str) or not item.strip() for item in guardrails):
        raise IncidentError("guardrails_globais inválidos")

    cards = _map(data.get("cartas"), "cartas")
    if not 8 <= len(cards) <= MAX_CARDS:
        raise IncidentError("catálogo de incidentes deve ter cobertura séria suficiente")
    for card_id, raw in cards.items():
        _id(card_id, "carta_id")
        card = _map(raw, f"cartas.{card_id}")
        if set(card) != CARD_FIELDS:
            raise IncidentError(f"{card_id}: campos inválidos")
        _text(card.get("nome"), f"{card_id}.nome", maximum=100)
        _id(card.get("tipo"), f"{card_id}.tipo")
        scopes = _ids(card.get("escopos"), f"{card_id}.escopos", maximum=2, allow_empty=False)
        if set(scopes) - VALID_SCOPES:
            raise IncidentError(f"{card_id}: escopo inválido")
        accesses = _ids(card.get("acessos"), f"{card_id}.acessos", maximum=4, allow_empty=False)
        if set(accesses) - VALID_ACCESS:
            raise IncidentError(f"{card_id}: acesso inválido")
        _ids(card.get("canais"), f"{card_id}.canais", maximum=8)
        _ids(card.get("tags"), f"{card_id}.tags", maximum=8)
        _ids(card.get("condicoes_necessarias"), f"{card_id}.condicoes_necessarias", maximum=4)
        if card.get("severidade") not in VALID_SEVERITY:
            raise IncidentError(f"{card_id}: severidade inválida")
        if card.get("intervencao") not in VALID_INTERVENTION:
            raise IncidentError(f"{card_id}: intervenção inválida")
        _text(card.get("premissa"), f"{card_id}.premissa")
        routes = _ids(card.get("rotas"), f"{card_id}.rotas", maximum=MAX_ROUTES, allow_empty=False)
        if not routes:
            raise IncidentError(f"{card_id}: precisa oferecer rotas observáveis")
    return data


def _validate_deck(deck: Any, label: str, *, allowed: set[str], cards: bool) -> dict[str, Any]:
    deck = _map(deck, label)
    expected = {"ciclo", "restantes", "assinatura_pool"} if cards else {"ciclo", "restantes"}
    if set(deck) != expected:
        raise IncidentError(f"{label}: campos inválidos")
    cycle = deck.get("ciclo")
    if not isinstance(cycle, int) or isinstance(cycle, bool) or cycle < 0:
        raise IncidentError(f"{label}.ciclo inválido")
    remaining = _list(deck.get("restantes"), f"{label}.restantes")
    if len(remaining) != len(set(remaining)) or set(remaining) - allowed:
        raise IncidentError(f"{label}.restantes inválido")
    if cycle == 0 and remaining:
        raise IncidentError(f"{label}: ciclo 0 exige restantes vazio")
    if cards:
        signature = deck.get("assinatura_pool")
        if signature is not None and (not isinstance(signature, str) or not SHA_RE.fullmatch(signature)):
            raise IncidentError(f"{label}.assinatura_pool inválida")
    return deck


def _empty_scope() -> dict[str, Any]:
    return {
        "ocorrencia": {"ciclo": 0, "restantes": []},
        "cartas": {"ciclo": 0, "assinatura_pool": None, "restantes": []},
    }


def load_state(repo: Path, index: dict[str, Any] | None = None) -> dict[str, Any]:
    index = index or load_index(repo)
    path = repo / STATE
    if path.stat().st_size > MAX_STATE_BYTES:
        raise IncidentError(f"estado de incidentes excede {MAX_STATE_BYTES} bytes")
    data = _map(_load(path), STATE.as_posix())
    if (
        data.get("schema_estado_incidentes_mundo") != SCHEMA
        or data.get("natureza") != "controle_reservado"
        or data.get("cidade") != "ravens_bluff"
        or set(data) != {"schema_estado_incidentes_mundo", "natureza", "cidade", "global", "locais", "historico_recente"}
    ):
        raise IncidentError("estado de incidentes inválido")
    cards = set(index["cartas"])
    global_tokens = {item["id"] for item in index["frequencia"]["global"]["fichas"]}
    local_tokens = {item["id"] for item in index["frequencia"]["local"]["fichas"]}
    global_state = _map(data.get("global"), "global")
    if set(global_state) != {"ocorrencia", "cartas"}:
        raise IncidentError("estado global inválido")
    _validate_deck(global_state["ocorrencia"], "global.ocorrencia", allowed=global_tokens, cards=False)
    _validate_deck(global_state["cartas"], "global.cartas", allowed=cards, cards=True)
    locations = _map(data.get("locais"), "locais")
    for local_id, scope in locations.items():
        locais._id(local_id)
        scope = _map(scope, f"locais.{local_id}")
        if set(scope) != {"ocorrencia", "cartas"}:
            raise IncidentError(f"locais.{local_id}: estado inválido")
        _validate_deck(scope["ocorrencia"], f"{local_id}.ocorrencia", allowed=local_tokens, cards=False)
        _validate_deck(scope["cartas"], f"{local_id}.cartas", allowed=cards, cards=True)
    history = _list(data.get("historico_recente"), "historico_recente")
    if len(history) > MAX_HISTORY:
        raise IncidentError(f"historico_recente excede {MAX_HISTORY}")
    for i, item in enumerate(history):
        item = _map(item, f"historico_recente[{i}]")
        if not {"cena_id", "local_id", "resultado", "ficha_global"} <= set(item):
            raise IncidentError("histórico de incidentes incompleto")
        _text(item.get("cena_id"), "cena_id", maximum=160)
        locais._id(item.get("local_id"))
        if item.get("resultado") not in {"rotina", "avaliar_incidente"}:
            raise IncidentError("histórico possui resultado inválido")
        if item.get("carta_id") is not None and item["carta_id"] not in cards:
            raise IncidentError("histórico referencia carta inexistente")
    return data


def condition_tokens(active: list[dict[str, Any]] | None) -> set[str]:
    tokens: set[str] = set()
    for raw in list(active or []):
        if not isinstance(raw, dict):
            continue
        kind = raw.get("tipo")
        intensity = raw.get("intensidade")
        if isinstance(kind, str) and kind:
            tokens.add(kind)
            tokens.add(f"tipo_{kind}")
        if isinstance(intensity, str) and intensity:
            tokens.add(f"intensidade_{intensity}")
        for marker in raw.get("marcadores") or []:
            if isinstance(marker, str) and ID_RE.fullmatch(marker):
                tokens.add(marker)
    return tokens


def eligible_cards(
    index: dict[str, Any],
    profile: dict[str, Any],
    *,
    scope: str,
    conditions: list[dict[str, Any]] | None = None,
) -> list[str]:
    if scope not in VALID_SCOPES:
        raise IncidentError("scope deve ser global ou local")
    profile = ecologia_local._validate_profile("incidente", profile)
    channels = set(profile["canais_microevento"])
    tags = set(profile["tags"])
    access = profile["acesso"]
    cond = condition_tokens(conditions)
    result: list[str] = []
    for card_id, card in sorted(index["cartas"].items()):
        if scope not in card["escopos"] or access not in card["acessos"]:
            continue
        required_channels = set(card["canais"])
        required_tags = set(card["tags"])
        required_conditions = set(card["condicoes_necessarias"])
        if required_channels and not (channels & required_channels):
            continue
        if required_tags and not (tags & required_tags):
            continue
        if required_conditions and not required_conditions <= cond:
            continue
        result.append(card_id)
    return result


def _order(seed: str, label: str, cycle: int, ids: list[str]) -> list[str]:
    return sorted(
        ids,
        key=lambda item: hashlib.sha256(f"{seed}|{label}|{cycle}|{item}".encode()).hexdigest(),
    )


def _draw_occurrence(deck: dict[str, Any], *, index: dict[str, Any], scope: str) -> tuple[str, str]:
    tokens = index["frequencia"][scope]["fichas"]
    ids = [item["id"] for item in tokens]
    if not deck["restantes"]:
        deck["ciclo"] += 1
        deck["restantes"] = _order(index["semente"], f"{scope}:ocorrencia", deck["ciclo"], ids)
    token_id = deck["restantes"].pop(0)
    result = next(item["resultado"] for item in tokens if item["id"] == token_id)
    return token_id, result


def _signature(ids: list[str]) -> str:
    return hashlib.sha256("\n".join(sorted(ids)).encode()).hexdigest()


def _draw_card(deck: dict[str, Any], *, index: dict[str, Any], label: str, eligible: list[str]) -> str | None:
    if not eligible:
        return None
    signature = _signature(eligible)
    if deck["assinatura_pool"] != signature:
        deck["ciclo"] += 1
        deck["assinatura_pool"] = signature
        deck["restantes"] = _order(index["semente"], label, deck["ciclo"], eligible)
    elif not deck["restantes"]:
        deck["ciclo"] += 1
        deck["restantes"] = _order(index["semente"], label, deck["ciclo"], eligible)
    deck["restantes"] = [item for item in deck["restantes"] if item in eligible]
    if not deck["restantes"]:
        deck["ciclo"] += 1
        deck["restantes"] = _order(index["semente"], label, deck["ciclo"], eligible)
    return deck["restantes"].pop(0)


def _existing(history: list[dict[str, Any]], scene_id: str, local_id: str) -> dict[str, Any] | None:
    return next(
        (item for item in reversed(history) if item.get("cena_id") == scene_id and item.get("local_id") == local_id),
        None,
    )


def _public(index: dict[str, Any], record: dict[str, Any], profile: dict[str, Any], *, reused: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": True,
        "tipo": "incidentes_mundo_v2",
        "resultado": record["resultado"],
        "origem": record.get("origem"),
        "cena_id": record["cena_id"],
        "local_id": record["local_id"],
        "reutilizado": reused,
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix()],
        "regra": (
            "Incidente é candidato até ser narrado. Pode ser resolvido ou ignorado na própria cena; "
            "não cria sidequest, recompensa, segredo, conhecimento ou NPC nomeado automaticamente."
        ),
    }
    card_id = record.get("carta_id")
    if record["resultado"] != "avaliar_incidente" or not card_id:
        return payload
    card = index["cartas"][card_id]
    payload["incidente"] = {
        "id": card_id,
        "nome": card["nome"],
        "tipo": card["tipo"],
        "severidade": card["severidade"],
        "intervencao": card["intervencao"],
        "premissa": card["premissa"],
        "rotas_observaveis": list(card["rotas"]),
        "atores_comuns": list(profile["atores_comuns"]),
        "guardrails": list(index["guardrails_globais"]),
    }
    return payload


def plan(
    repo: Path,
    *,
    scene_id: str,
    local_id: str,
    profile: dict[str, Any],
    conditions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    scene_id = _text(scene_id, "cena_id", maximum=160)
    local_id = locais._id(local_id)
    profile = ecologia_local._validate_profile(local_id, profile)
    index = load_index(repo)
    state = load_state(repo, index)
    existing = _existing(state["historico_recente"], scene_id, local_id)
    if existing is not None:
        return {
            "publico": _public(index, existing, profile, reused=True),
            "estado_planejado": state,
            "alterou": False,
        }

    planned = copy.deepcopy(state)
    global_eligible = eligible_cards(index, profile, scope="global", conditions=conditions)
    local_eligible = eligible_cards(index, profile, scope="local", conditions=conditions)
    if len(local_eligible) < MIN_LOCAL_ELIGIBLE:
        raise IncidentError(
            f"{local_id}: somente {len(local_eligible)} incidentes locais elegíveis; mínimo {MIN_LOCAL_ELIGIBLE}"
        )

    global_token, global_result = _draw_occurrence(planned["global"]["ocorrencia"], index=index, scope="global")
    card_id: str | None = None
    origin: str | None = None
    local_token: str | None = None

    if global_result == "incidente":
        card_id = _draw_card(
            planned["global"]["cartas"],
            index=index,
            label="global:cartas",
            eligible=global_eligible,
        )
        if card_id is not None:
            origin = "global"

    if card_id is None:
        local_state = planned["locais"].setdefault(local_id, _empty_scope())
        local_token, local_result = _draw_occurrence(local_state["ocorrencia"], index=index, scope="local")
        if local_result == "incidente":
            card_id = _draw_card(
                local_state["cartas"],
                index=index,
                label=f"local:{local_id}:cartas",
                eligible=local_eligible,
            )
            if card_id is not None:
                origin = "local"

    record: dict[str, Any] = {
        "cena_id": scene_id,
        "local_id": local_id,
        "resultado": "avaliar_incidente" if card_id else "rotina",
        "origem": origin,
        "ficha_global": global_token,
    }
    if local_token is not None:
        record["ficha_local"] = local_token
    if card_id is not None:
        record["carta_id"] = card_id
    planned["historico_recente"].append(record)
    planned["historico_recente"] = planned["historico_recente"][-MAX_HISTORY:]
    rendered = yaml.safe_dump(planned, allow_unicode=True, sort_keys=False).encode()
    if len(rendered) > MAX_STATE_BYTES:
        raise IncidentError(f"estado planejado excede {MAX_STATE_BYTES} bytes")
    return {
        "publico": _public(index, record, profile, reused=False),
        "estado_planejado": planned,
        "alterou": True,
    }


def commit_plan(repo: Path, plan_result: dict[str, Any]) -> None:
    if plan_result.get("alterou") is not True:
        return
    state = plan_result.get("estado_planejado")
    if not isinstance(state, dict):
        raise IncidentError("plano de incidente sem estado_planejado")
    atomic(repo / STATE, state)


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    cards = 0
    try:
        index = load_index(repo)
        load_state(repo, index)
        ecology = ecologia_local.load_index(repo)
        cards = len(index["cartas"])
        for local_id, profile in ecology["perfis"].items():
            eligible = eligible_cards(index, profile, scope="local", conditions=[])
            if len(eligible) < MIN_LOCAL_ELIGIBLE:
                errors.append(f"{local_id}: cobertura local insuficiente ({len(eligible)})")
        required_types = {
            "briga", "roubo", "perseguicao", "acidente", "incendio", "desabamento",
            "crianca_em_perigo", "extorsao", "guarda", "tumulto", "ferimento",
        }
        actual = {card["tipo"] for card in index["cartas"].values()}
        missing = sorted(required_types - actual)
        if missing:
            errors.append("tipos sérios ausentes: " + ", ".join(missing))
    except (IncidentError, ecologia_local.LocalEcologyError) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "cartas": cards,
        "erros": errors,
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), ecologia_local.INDEX.as_posix()],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    args = parser.parse_args(argv)
    result = check(args.repo.resolve())
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
