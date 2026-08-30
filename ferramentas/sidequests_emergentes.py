#!/usr/bin/env python3
"""Task 41 — Emergent Sidequest Authoring & Registry v2.

Transforma um pacote read-only da Task 40 em um mini-arco persistente somente
quando uma oferta foi efetivamente narrada.

Fluxo:
    Task40 planejar -> Task41 preparar -> narrar oferta -> Task41 materializar

Preparar nunca escreve. Materializar revalida a preparação e registra:
- um fragmento reservado completo da quest;
- uma missão `oferecida` no lifecycle já existente de `oportunidades.py`.

A Task 41 não executa recompensa, perda, consequência, presença de elenco novo
nem rewrite canônico. Esses contratos ficam congelados para Tasks posteriores.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import tempfile
import unicodedata
from pathlib import Path
from typing import Any

import yaml

import estado_relacional
import locais
import mundo
import oportunidades

QUESTS_DIR = Path("narrador/sidequests-emergentes/quests")
NPC_INDEX = estado_relacional.NPC_INDEX
LOCATION_INDEX = locais.INDEX

SCHEMA = 2
QUEST_PREFIX = "qse-"
MISSION_PREFIX = "sqe-"
PREPARATION_PREFIX = "sqe-prep-"

MAX_FRAGMENT_BYTES = 20 * 1024
MAX_PREP_OUTPUT_BYTES = 8 * 1024
MAX_PHASES = 6
MAX_LOCATIONS = 8
MAX_EXISTING_NPCS = 8
MAX_NEW_NPCS = 6
MAX_ANTAGONISTS = 6
MAX_JUPPONGATANA = 4
MAX_SUCCESS_CONDITIONS = 5
MAX_FAILURE_CONDITIONS = 5
MAX_REWARDS = 6
MAX_SECRETS = 6
MAX_BRANCHES = 6
MAX_RISKS = 8
MAX_LOSSES = 6
MAX_QUEST_DURATION_HOURS = 30 * 24
MAX_TEXT = 520

ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,95}$")
QUEST_RE = re.compile(r"^qse-[0-9a-f]{16}$")
PREPARATION_RE = re.compile(r"^sqe-prep-[0-9a-f]{24}$")

CANON_RELATIONS = {
    "lateral",
    "candidata_ponte",
    "candidata_convergente",
    "candidata_adiamento",
    "candidata_transformacao",
}
QUEST_GIVER_TYPES = {"npc_existente", "npc_novo", "instituicao", "mensagem", "outro"}
LOCATION_TYPES = {"canonico", "proposto"}
ANTAGONIST_TYPES = {
    "ator_task40",
    "npc_existente",
    "npc_novo",
    "faccao",
    "instituicao",
    "circunstancia",
}
JUPPONGATANA_ROLES = {
    "envolvimento_condicionado",
    "revelacao_condicionada",
    "oposicao_possivel",
}
REWARD_TYPES = {
    "dinheiro",
    "item",
    "item_magico",
    "consumivel",
    "pergaminho",
    "tesouro",
    "propriedade",
    "direito_de_uso",
    "servico",
    "informacao",
    "contato",
    "favor",
    "acesso",
    "reputacao",
    "recurso",
}
REWARD_MODES = {"sucesso", "descoberta", "condicional"}
REWARD_VALUES = {"baixo", "moderado", "alto", "especial"}
MATERIAL_REWARDS = {"dinheiro", "item", "item_magico", "consumivel", "pergaminho", "tesouro"}
VALUE_RANK = {"baixo": 1, "moderado": 2, "alto": 3}

FORBIDDEN_AGENCY_KEYS = {
    "acao_ren", "acoes_ren", "decisao_ren", "decisoes_ren", "fala_ren",
    "falas_ren", "intencao_ren", "intencoes_ren", "emocao_ren", "emocoes_ren",
    "crenca_ren", "crencas_ren", "resultado_ren", "rota_ren", "escolha_ren",
    "escolhas_ren",
}
FORBIDDEN_REN_FUTURE = re.compile(
    r"\bren\s+(?:vai(?:\s+a)?|ira|deve|devera|precisa|tera(?:\s+de|\s+que)?|"
    r"decide|decidira|escolhe|escolhera|aceita|aceitara|recusa|recusara|"
    r"investiga|investigara|segue|seguira|ataca|atacara|foge|fugira|"
    r"negocia|negociara|sente|sentira|acredita|acreditara|mata|matara|"
    r"poupa|poupara)\b",
    re.IGNORECASE,
)


class EmergentSidequestAuthoringError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise EmergentSidequestAuthoringError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EmergentSidequestAuthoringError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise EmergentSidequestAuthoringError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str, *, minimum: int = 1, maximum: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise EmergentSidequestAuthoringError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if len(result) < minimum:
        raise EmergentSidequestAuthoringError(f"{label} deve ter ao menos {minimum} caracteres")
    if len(result) > maximum:
        raise EmergentSidequestAuthoringError(f"{label} excede {maximum} caracteres")
    return result


def _id(value: Any, label: str) -> str:
    result = _text(value, label, maximum=128)
    if not ID_RE.fullmatch(result):
        raise EmergentSidequestAuthoringError(f"{label} deve usar id ASCII minúsculo estável")
    return result


def _slug(value: Any, label: str) -> str:
    result = _text(value, label, maximum=96)
    if not SLUG_RE.fullmatch(result):
        raise EmergentSidequestAuthoringError(f"{label} deve usar slug ASCII minúsculo")
    return result


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return " ".join(ascii_text.lower().split())


def _agency_scan(value: Any, path: str = "quest") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = _normalized(str(key)).replace(" ", "_")
            if normalized_key in FORBIDDEN_AGENCY_KEYS:
                raise EmergentSidequestAuthoringError(
                    f"{path}.{key}: Task41 não pode escrever agência de Ren"
                )
            _agency_scan(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for pos, child in enumerate(value):
            _agency_scan(child, f"{path}[{pos}]")
        return
    if isinstance(value, str) and FORBIDDEN_REN_FUTURE.search(_normalized(value)):
        raise EmergentSidequestAuthoringError(
            f"{path}: plano descreve escolha/ação futura de Ren; descreva o mundo e suas condições"
        )


def _yaml_bytes(value: Any) -> bytes:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8")


def _hash_payload(value: Any) -> str:
    rendered = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(rendered).hexdigest()


def _quest_id(package: dict[str, Any], normalized_spec: dict[str, Any]) -> str:
    return QUEST_PREFIX + _hash_payload({"origem": package["origem"], "spec": normalized_spec})[:16]


def mission_id(quest_id: str) -> str:
    if not QUEST_RE.fullmatch(quest_id):
        raise EmergentSidequestAuthoringError("quest_id emergente inválido")
    return MISSION_PREFIX + hashlib.sha256(
        f"emergent-sidequest|{quest_id}".encode("utf-8")
    ).hexdigest()[:16]


def _quest_path(quest_id: str) -> Path:
    if not QUEST_RE.fullmatch(quest_id):
        raise EmergentSidequestAuthoringError("quest_id emergente inválido")
    return QUESTS_DIR / f"{quest_id}.yaml"


def _parse_instant(value: Any, label: str) -> mundo.WorldInstant:
    raw = _map(value, label)
    if set(raw) != {"data", "hora"}:
        raise EmergentSidequestAuthoringError(f"{label} deve conter exatamente data e hora")
    try:
        return mundo.parse_instant(
            _text(raw["data"], label + ".data", maximum=80),
            _text(raw["hora"], label + ".hora", maximum=8),
        )
    except mundo.WorldEngineError as exc:
        raise EmergentSidequestAuthoringError(str(exc)) from exc


def _validate_task40_package(raw: Any) -> dict[str, Any]:
    package = copy.deepcopy(_map(raw, "pacote_task40"))
    if (
        package.get("resultado") != "material_para_planejamento"
        or package.get("read_only") is not True
        or package.get("mutacoes_aplicadas") is not False
    ):
        raise EmergentSidequestAuthoringError(
            "Task41 exige pacote material_para_planejamento read-only da Task40"
        )
    authority = _map(package.get("autoridade"), "pacote_task40.autoridade")
    required_false = (
        "pode_criar_missao", "pode_oferecer_missao", "pode_reescrever_intencao",
        "pode_marcar_intencao_satisfeita",
    )
    if authority.get("pode_planejar") is not True or any(
        authority.get(key) is not False for key in required_false
    ):
        raise EmergentSidequestAuthoringError(
            "autoridade Task40 divergente: pacote deve autorizar somente planejamento"
        )
    origin = _map(package.get("origem"), "pacote_task40.origem")
    for key in ("tipo", "id", "ancora_tipo", "ancora"):
        _text(origin.get(key), f"pacote_task40.origem.{key}", maximum=320)
    quests = _map(package.get("quests"), "pacote_task40.quests")
    for key in ("ativas", "abertas", "max_ativas", "max_abertas"):
        if isinstance(quests.get(key), bool) or not isinstance(quests.get(key), int):
            raise EmergentSidequestAuthoringError(f"pacote_task40.quests.{key} inválido")
    if quests["ativas"] >= quests["max_ativas"] or quests["abertas"] >= quests["max_abertas"]:
        raise EmergentSidequestAuthoringError("pacote Task40 já está sem orçamento para nova sidequest")
    world = _map(package.get("prazo_mundo"), "pacote_task40.prazo_mundo")
    _parse_instant(world.get("agora"), "pacote_task40.prazo_mundo.agora")
    horizon = _map(
        package.get("horizonte_intencoes_canonicas"),
        "pacote_task40.horizonte_intencoes_canonicas",
    )
    compatible = _list(horizon.get("compativeis"), "pacote_task40.intencoes.compativeis")
    if len(compatible) > 3:
        raise EmergentSidequestAuthoringError("pacote Task40 excede três intenções")
    actors = _list(
        package.get("atores_causalmente_disponiveis"),
        "pacote_task40.atores_causalmente_disponiveis",
    )
    jupp = _list(package.get("juppongatana_possiveis"), "pacote_task40.juppongatana_possiveis")
    if len(actors) > 6 or len(jupp) > 4:
        raise EmergentSidequestAuthoringError("pacote Task40 excede orçamento de atores")
    reward = _map(package.get("envelope_recompensa"), "pacote_task40.envelope_recompensa")
    _text(reward.get("regra"), "pacote_task40.envelope_recompensa.regra")
    return package


def _normalize_deadline(raw: Any, *, now: mundo.WorldInstant) -> dict[str, Any]:
    data = _map(raw, "prazo")
    kind = _text(data.get("tipo"), "prazo.tipo", maximum=40)
    if kind == "temporal":
        if set(data) != {"tipo", "expira_em"}:
            raise EmergentSidequestAuthoringError("prazo temporal exige somente tipo e expira_em")
        end = _parse_instant(data["expira_em"], "prazo.expira_em")
        if end.minute <= now.minute:
            raise EmergentSidequestAuthoringError("prazo precisa ficar no futuro")
        hours = (end.minute - now.minute) // 60
        if hours > MAX_QUEST_DURATION_HOURS:
            raise EmergentSidequestAuthoringError(f"prazo excede {MAX_QUEST_DURATION_HOURS} horas")
        return {"tipo": "temporal", "expira_em": mundo.instant_parts(end)}
    if kind == "enquanto_condicao":
        if set(data) != {"tipo", "condicao"}:
            raise EmergentSidequestAuthoringError(
                "prazo enquanto_condicao exige somente tipo e condicao"
            )
        return {"tipo": kind, "condicao": _text(data["condicao"], "prazo.condicao")}
    if kind == "a_qualquer_momento":
        if set(data) != {"tipo"}:
            raise EmergentSidequestAuthoringError(
                "prazo a_qualquer_momento não aceita campos extras"
            )
        return {"tipo": kind}
    raise EmergentSidequestAuthoringError(
        "prazo.tipo deve ser temporal, enquanto_condicao ou a_qualquer_momento"
    )


def _load_reference_indexes(repo: Path) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    npcs = _map(_load(repo / NPC_INDEX), NPC_INDEX.as_posix())
    npc_map = _map(npcs.get("npcs"), "estado/npcs/index.yaml:npcs")
    try:
        locations = locais.load_index(repo)
    except locais.LocationError as exc:
        raise EmergentSidequestAuthoringError(str(exc)) from exc
    location_map = _map(locations.get("locais"), "cenario/locais:index")
    return npc_map, location_map, [NPC_INDEX.as_posix(), LOCATION_INDEX.as_posix()]


def _normalize_new_npcs(raw: Any, *, npc_map: dict[str, Any]) -> list[dict[str, str]]:
    items = _list(raw, "npcs_novos")
    if len(items) > MAX_NEW_NPCS:
        raise EmergentSidequestAuthoringError("npcs_novos excede orçamento")
    result, seen = [], set()
    for pos, item in enumerate(items):
        data = _map(item, f"npcs_novos[{pos}]")
        if set(data) != {"id", "nome", "funcao", "estatuto"}:
            raise EmergentSidequestAuthoringError(
                f"npcs_novos[{pos}] exige id, nome, funcao e estatuto"
            )
        nid = _slug(data["id"], f"npcs_novos[{pos}].id")
        if nid in npc_map:
            raise EmergentSidequestAuthoringError(f"npc_novo colide com NPC existente: {nid}")
        if nid in seen:
            raise EmergentSidequestAuthoringError(f"npc_novo duplicado: {nid}")
        if data.get("estatuto") != "reservado_nao_presente":
            raise EmergentSidequestAuthoringError(
                "npc_novo deve nascer como reservado_nao_presente; Task41 não cria presença"
            )
        seen.add(nid)
        result.append({
            "id": nid,
            "nome": _text(data["nome"], f"npcs_novos[{pos}].nome", maximum=120),
            "funcao": _text(data["funcao"], f"npcs_novos[{pos}].funcao"),
            "estatuto": "reservado_nao_presente",
        })
    return result


def _normalize_existing_npcs(raw: Any, *, npc_map: dict[str, Any]) -> list[dict[str, str]]:
    items = _list(raw, "npcs_existentes")
    if len(items) > MAX_EXISTING_NPCS:
        raise EmergentSidequestAuthoringError("npcs_existentes excede orçamento")
    result, seen = [], set()
    for pos, item in enumerate(items):
        data = _map(item, f"npcs_existentes[{pos}]")
        if set(data) != {"id", "funcao"}:
            raise EmergentSidequestAuthoringError(f"npcs_existentes[{pos}] exige id e funcao")
        nid = _slug(data["id"], f"npcs_existentes[{pos}].id")
        if nid not in npc_map:
            raise EmergentSidequestAuthoringError(f"NPC existente desconhecido: {nid}")
        if nid in seen:
            raise EmergentSidequestAuthoringError(f"NPC duplicado: {nid}")
        seen.add(nid)
        result.append({"id": nid, "funcao": _text(data["funcao"], f"npcs_existentes[{pos}].funcao")})
    return result


def _normalize_quest_giver(
    raw: Any, *, npc_map: dict[str, Any], new_npc_ids: set[str]
) -> dict[str, Any]:
    data = _map(raw, "quest_giver")
    if set(data) != {"tipo", "id", "nome", "legitimidade"}:
        raise EmergentSidequestAuthoringError(
            "quest_giver exige tipo, id, nome e legitimidade"
        )
    kind = _text(data["tipo"], "quest_giver.tipo", maximum=32)
    if kind not in QUEST_GIVER_TYPES:
        raise EmergentSidequestAuthoringError("quest_giver.tipo inválido")
    gid = _id(data["id"], "quest_giver.id")
    if kind == "npc_existente" and gid not in npc_map:
        raise EmergentSidequestAuthoringError(f"quest_giver NPC existente não encontrado: {gid}")
    if kind == "npc_novo" and gid not in new_npc_ids:
        raise EmergentSidequestAuthoringError(
            "quest_giver npc_novo precisa estar declarado em npcs_novos"
        )
    return {
        "tipo": kind,
        "id": gid,
        "nome": _text(data["nome"], "quest_giver.nome", maximum=120),
        "legitimidade": _text(data["legitimidade"], "quest_giver.legitimidade"),
    }


def _normalize_locations(raw: Any, *, location_map: dict[str, Any]) -> list[dict[str, Any]]:
    items = _list(raw, "locais")
    if not 1 <= len(items) <= MAX_LOCATIONS:
        raise EmergentSidequestAuthoringError(
            f"locais deve ter entre 1 e {MAX_LOCATIONS} entradas"
        )
    result, seen = [], set()
    for pos, item in enumerate(items):
        data = _map(item, f"locais[{pos}]")
        if set(data) - {"id", "tipo", "nome", "funcao"}:
            raise EmergentSidequestAuthoringError(f"locais[{pos}] possui campo extra")
        lid = _slug(data.get("id"), f"locais[{pos}].id")
        if lid in seen:
            raise EmergentSidequestAuthoringError(f"local duplicado: {lid}")
        seen.add(lid)
        kind = _text(data.get("tipo"), f"locais[{pos}].tipo", maximum=24)
        if kind not in LOCATION_TYPES:
            raise EmergentSidequestAuthoringError(f"locais[{pos}].tipo inválido")
        if kind == "canonico" and lid not in location_map:
            raise EmergentSidequestAuthoringError(f"local canônico inexistente: {lid}")
        name = data.get("nome")
        if kind == "proposto":
            name = _text(name, f"locais[{pos}].nome", maximum=120)
        elif name is not None:
            name = _text(name, f"locais[{pos}].nome", maximum=120)
        result.append({
            "id": lid,
            "tipo": kind,
            **({"nome": name} if name is not None else {}),
            "funcao": _text(data.get("funcao"), f"locais[{pos}].funcao"),
        })
    return result


def _normalize_phases(raw: Any, *, known_locations: set[str]) -> list[dict[str, Any]]:
    items = _list(raw, "fases")
    if not 1 <= len(items) <= MAX_PHASES:
        raise EmergentSidequestAuthoringError(
            f"fases deve ter entre 1 e {MAX_PHASES} entradas"
        )
    result, seen = [], set()
    for pos, item in enumerate(items):
        data = _map(item, f"fases[{pos}]")
        if set(data) != {"id", "titulo", "situacao", "condicao_avanco", "locais"}:
            raise EmergentSidequestAuthoringError(
                f"fases[{pos}] exige id, titulo, situacao, condicao_avanco e locais"
            )
        fid = _slug(data["id"], f"fases[{pos}].id")
        if fid in seen:
            raise EmergentSidequestAuthoringError(f"fase duplicada: {fid}")
        seen.add(fid)
        places = [_slug(value, f"fases[{pos}].locais") for value in _list(data["locais"], f"fases[{pos}].locais")]
        if not places or set(places) - known_locations:
            raise EmergentSidequestAuthoringError(f"fases[{pos}] referencia local não declarado")
        result.append({
            "id": fid,
            "titulo": _text(data["titulo"], f"fases[{pos}].titulo", maximum=120),
            "situacao": _text(data["situacao"], f"fases[{pos}].situacao"),
            "condicao_avanco": _text(data["condicao_avanco"], f"fases[{pos}].condicao_avanco"),
            "locais": places,
        })
    return result


def _normalize_antagonists(
    raw: Any,
    *,
    package: dict[str, Any],
    npc_map: dict[str, Any],
    new_npc_ids: set[str],
) -> list[dict[str, str]]:
    items = _list(raw, "antagonistas")
    if not 1 <= len(items) <= MAX_ANTAGONISTS:
        raise EmergentSidequestAuthoringError(
            f"antagonistas deve ter entre 1 e {MAX_ANTAGONISTS} entradas"
        )
    actor_ids = {
        str(item.get("id")) for item in package["atores_causalmente_disponiveis"]
        if isinstance(item, dict)
    }
    result, seen = [], set()
    for pos, item in enumerate(items):
        data = _map(item, f"antagonistas[{pos}]")
        if set(data) != {"id", "tipo", "funcao", "objetivo"}:
            raise EmergentSidequestAuthoringError(
                f"antagonistas[{pos}] exige id, tipo, funcao e objetivo"
            )
        aid = _id(data["id"], f"antagonistas[{pos}].id")
        if aid in seen:
            raise EmergentSidequestAuthoringError(f"antagonista duplicado: {aid}")
        seen.add(aid)
        kind = _text(data["tipo"], f"antagonistas[{pos}].tipo", maximum=32)
        if kind not in ANTAGONIST_TYPES:
            raise EmergentSidequestAuthoringError("tipo de antagonista inválido")
        if kind == "ator_task40" and aid not in actor_ids:
            raise EmergentSidequestAuthoringError(
                f"antagonista {aid} não estava causalmente disponível na Task40"
            )
        if kind == "npc_existente" and aid not in npc_map:
            raise EmergentSidequestAuthoringError(f"NPC antagonista inexistente: {aid}")
        if kind == "npc_novo" and aid not in new_npc_ids:
            raise EmergentSidequestAuthoringError(f"antagonista npc_novo não declarado: {aid}")
        result.append({
            "id": aid,
            "tipo": kind,
            "funcao": _text(data["funcao"], f"antagonistas[{pos}].funcao"),
            "objetivo": _text(data["objetivo"], f"antagonistas[{pos}].objetivo"),
        })
    return result


def _normalize_juppongatana(raw: Any, *, package: dict[str, Any]) -> list[dict[str, Any]]:
    items = _list(raw, "juppongatana")
    if len(items) > MAX_JUPPONGATANA:
        raise EmergentSidequestAuthoringError("juppongatana excede orçamento")
    possible = {
        str(item.get("id")): item for item in package["juppongatana_possiveis"]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    result, seen = [], set()
    for pos, item in enumerate(items):
        data = _map(item, f"juppongatana[{pos}]")
        if set(data) != {"id", "funcao", "estatuto"}:
            raise EmergentSidequestAuthoringError(
                f"juppongatana[{pos}] exige id, funcao e estatuto"
            )
        jid = _slug(data["id"], f"juppongatana[{pos}].id")
        if jid not in possible:
            raise EmergentSidequestAuthoringError(
                f"Juppongatana não permitido pelo pacote Task40: {jid}"
            )
        if jid in seen:
            raise EmergentSidequestAuthoringError(f"Juppongatana duplicado: {jid}")
        seen.add(jid)
        status = _text(data["estatuto"], f"juppongatana[{pos}].estatuto", maximum=40)
        if status not in JUPPONGATANA_ROLES:
            raise EmergentSidequestAuthoringError("estatuto Juppongatana inválido")
        result.append({
            "id": jid,
            "funcao": _text(data["funcao"], f"juppongatana[{pos}].funcao"),
            "estatuto": status,
            "causal_agora": bool(possible[jid].get("causal_agora")),
        })
    return result


def _normalize_condition_list(raw: Any, label: str, maximum: int) -> list[str]:
    values = _list(raw, label)
    if not 1 <= len(values) <= maximum:
        raise EmergentSidequestAuthoringError(f"{label} deve ter entre 1 e {maximum} condições")
    return [_text(value, f"{label}[{pos}]") for pos, value in enumerate(values)]


def _normalize_stakes(raw: Any) -> dict[str, Any]:
    data = _map(raw, "stakes")
    if set(data) != {"em_risco", "consequencia_expiracao", "perdas_possiveis"}:
        raise EmergentSidequestAuthoringError(
            "stakes exige em_risco, consequencia_expiracao e perdas_possiveis"
        )
    risks = _list(data["em_risco"], "stakes.em_risco")
    if not 1 <= len(risks) <= MAX_RISKS:
        raise EmergentSidequestAuthoringError("stakes.em_risco fora do orçamento")
    risks = [_text(item, f"stakes.em_risco[{pos}]") for pos, item in enumerate(risks)]
    losses = _list(data["perdas_possiveis"], "stakes.perdas_possiveis")
    if len(losses) > MAX_LOSSES:
        raise EmergentSidequestAuthoringError("perdas_possiveis excede orçamento")
    normalized_losses = []
    for pos, item in enumerate(losses):
        entry = _map(item, f"stakes.perdas_possiveis[{pos}]")
        if set(entry) != {"tipo", "alvo", "condicao", "descricao"}:
            raise EmergentSidequestAuthoringError(
                "perda possível exige tipo, alvo, condicao e descricao"
            )
        normalized_losses.append({
            "tipo": _id(entry["tipo"], f"perdas[{pos}].tipo"),
            "alvo": _id(entry["alvo"], f"perdas[{pos}].alvo"),
            "condicao": _text(entry["condicao"], f"perdas[{pos}].condicao"),
            "descricao": _text(entry["descricao"], f"perdas[{pos}].descricao"),
        })
    return {
        "em_risco": risks,
        "consequencia_expiracao": _text(data["consequencia_expiracao"], "stakes.consequencia_expiracao"),
        "perdas_possiveis": normalized_losses,
    }


def _normalize_rewards(raw: Any, *, package: dict[str, Any]) -> list[dict[str, str]]:
    items = _list(raw, "recompensas")
    if not 1 <= len(items) <= MAX_REWARDS:
        raise EmergentSidequestAuthoringError(
            f"recompensas deve ter entre 1 e {MAX_REWARDS} entradas"
        )
    envelope = package["envelope_recompensa"]
    ceiling_raw = envelope.get("teto_valor")
    ceiling = VALUE_RANK.get(ceiling_raw) if isinstance(ceiling_raw, str) else None
    result, seen = [], set()
    for pos, item in enumerate(items):
        data = _map(item, f"recompensas[{pos}]")
        if set(data) != {
            "id", "tipo", "modo", "descricao", "condicao", "valor_aproximado",
            "autoridade_concedente",
        }:
            raise EmergentSidequestAuthoringError(f"recompensas[{pos}] possui estrutura inválida")
        rid = _slug(data["id"], f"recompensas[{pos}].id")
        if rid in seen:
            raise EmergentSidequestAuthoringError(f"recompensa duplicada: {rid}")
        seen.add(rid)
        kind = _text(data["tipo"], f"recompensas[{pos}].tipo", maximum=32)
        mode = _text(data["modo"], f"recompensas[{pos}].modo", maximum=24)
        value = _text(data["valor_aproximado"], f"recompensas[{pos}].valor_aproximado", maximum=16)
        if kind not in REWARD_TYPES or mode not in REWARD_MODES or value not in REWARD_VALUES:
            raise EmergentSidequestAuthoringError(
                f"recompensas[{pos}] possui tipo/modo/valor inválido"
            )
        if (
            kind in MATERIAL_REWARDS and value in VALUE_RANK and ceiling is not None
            and VALUE_RANK[value] > ceiling
        ):
            raise EmergentSidequestAuthoringError(
                f"recompensa material {rid} excede teto {ceiling_raw} da Task40"
            )
        result.append({
            "id": rid,
            "tipo": kind,
            "modo": mode,
            "descricao": _text(data["descricao"], f"recompensas[{pos}].descricao"),
            "condicao": _text(data["condicao"], f"recompensas[{pos}].condicao"),
            "valor_aproximado": value,
            "autoridade_concedente": _text(
                data["autoridade_concedente"], f"recompensas[{pos}].autoridade_concedente"
            ),
        })
    return result


def _normalize_canon_relation(raw: Any, *, package: dict[str, Any]) -> dict[str, Any]:
    data = _map(raw, "relacao_canone")
    if set(data) != {"modo", "intencoes_candidatas", "justificativa"}:
        raise EmergentSidequestAuthoringError(
            "relacao_canone exige modo, intencoes_candidatas e justificativa"
        )
    mode = _text(data["modo"], "relacao_canone.modo", maximum=40)
    if mode not in CANON_RELATIONS:
        raise EmergentSidequestAuthoringError("relacao_canone.modo inválido")
    ids = [_id(value, "relacao_canone.intencoes_candidatas") for value in _list(
        data["intencoes_candidatas"], "relacao_canone.intencoes_candidatas"
    )]
    if len(ids) != len(set(ids)) or len(ids) > 3:
        raise EmergentSidequestAuthoringError(
            "intencoes_candidatas deve ser única e ter no máximo 3 IDs"
        )
    allowed = {
        str(item.get("evento_id"))
        for item in package["horizonte_intencoes_canonicas"]["compativeis"]
        if isinstance(item, dict)
    }
    if mode == "lateral" and ids:
        raise EmergentSidequestAuthoringError("quest lateral não deve reservar intenção canônica")
    if mode != "lateral" and not ids:
        raise EmergentSidequestAuthoringError(
            "relação canônica não lateral exige intenção candidata"
        )
    if set(ids) - allowed:
        raise EmergentSidequestAuthoringError(
            "Task41 só pode citar intenções que vieram no pacote Task40"
        )
    return {
        "modo": mode,
        "intencoes_candidatas": ids,
        "justificativa": _text(data["justificativa"], "relacao_canone.justificativa"),
        "autoridade": "candidatura_somente_task42_pode_reescrever",
    }


def _normalize_branches(raw: Any) -> list[dict[str, str]]:
    items = _list(raw, "bifurcacoes")
    if len(items) > MAX_BRANCHES:
        raise EmergentSidequestAuthoringError("bifurcacoes excede orçamento")
    result, seen = [], set()
    for pos, item in enumerate(items):
        data = _map(item, f"bifurcacoes[{pos}]")
        if set(data) != {"id", "se", "efeito_no_mundo"}:
            raise EmergentSidequestAuthoringError(
                "bifurcação exige id, se e efeito_no_mundo"
            )
        bid = _slug(data["id"], f"bifurcacoes[{pos}].id")
        if bid in seen:
            raise EmergentSidequestAuthoringError(f"bifurcação duplicada: {bid}")
        seen.add(bid)
        result.append({
            "id": bid,
            "se": _text(data["se"], f"bifurcacoes[{pos}].se"),
            "efeito_no_mundo": _text(data["efeito_no_mundo"], f"bifurcacoes[{pos}].efeito_no_mundo"),
        })
    return result


def normalize_spec(
    repo: Path, package_raw: Any, spec_raw: Any
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Valida autoria. Não escreve e não abre conteúdo narrativo secreto."""
    package = _validate_task40_package(package_raw)
    spec = copy.deepcopy(_map(spec_raw, "quest"))
    expected = {
        "titulo", "tipo", "origem_causal", "quest_giver", "oferta", "premissa",
        "prazo", "objetivo", "fases", "locais", "npcs_existentes", "npcs_novos",
        "antagonistas", "juppongatana", "condicoes_sucesso", "condicoes_falha",
        "stakes", "recompensas", "relacao_canone", "segredos", "bifurcacoes",
    }
    if set(spec) != expected:
        raise EmergentSidequestAuthoringError(
            f"schema autoral Task41 divergente; faltando={sorted(expected-set(spec))}; extras={sorted(set(spec)-expected)}"
        )
    _agency_scan(spec)
    origin = _map(spec["origem_causal"], "origem_causal")
    if set(origin) != {"tipo", "id", "npc_id", "ancora_tipo", "ancora"}:
        raise EmergentSidequestAuthoringError(
            "origem_causal deve espelhar tipo/id/npc_id/ancora_tipo/ancora da Task40"
        )
    normalized_origin = {
        "tipo": _text(origin["tipo"], "origem_causal.tipo", maximum=40),
        "id": _id(origin["id"], "origem_causal.id"),
        "npc_id": _slug(origin["npc_id"], "origem_causal.npc_id") if origin["npc_id"] is not None else None,
        "ancora_tipo": _text(origin["ancora_tipo"], "origem_causal.ancora_tipo", maximum=40),
        "ancora": _text(origin["ancora"], "origem_causal.ancora", maximum=320),
    }
    for key in ("tipo", "id", "npc_id", "ancora_tipo", "ancora"):
        if normalized_origin[key] != package["origem"].get(key):
            raise EmergentSidequestAuthoringError(f"origem_causal.{key} diverge do pacote Task40")

    npc_map, location_map, sources = _load_reference_indexes(repo)
    new_npcs = _normalize_new_npcs(spec["npcs_novos"], npc_map=npc_map)
    new_npc_ids = {item["id"] for item in new_npcs}
    existing_npcs = _normalize_existing_npcs(spec["npcs_existentes"], npc_map=npc_map)
    locations = _normalize_locations(spec["locais"], location_map=location_map)
    now = _parse_instant(package["prazo_mundo"]["agora"], "pacote_task40.prazo_mundo.agora")
    quest_giver = _normalize_quest_giver(
        spec["quest_giver"], npc_map=npc_map, new_npc_ids=new_npc_ids
    )
    offer = _map(spec["oferta"], "oferta")
    if set(offer) != {"premissa", "pedido", "recusa_permitida"} or offer.get("recusa_permitida") is not True:
        raise EmergentSidequestAuthoringError(
            "oferta exige premissa, pedido e recusa_permitida=true"
        )
    normalized = {
        "titulo": _text(spec["titulo"], "titulo", maximum=140),
        "tipo": _text(spec["tipo"], "tipo", maximum=40),
        "origem_causal": normalized_origin,
        "quest_giver": quest_giver,
        "oferta": {
            "premissa": _text(offer["premissa"], "oferta.premissa"),
            "pedido": _text(offer["pedido"], "oferta.pedido"),
            "recusa_permitida": True,
        },
        "premissa": _text(spec["premissa"], "premissa"),
        "prazo": _normalize_deadline(spec["prazo"], now=now),
        "objetivo": _text(spec["objetivo"], "objetivo"),
        "locais": locations,
        "npcs_existentes": existing_npcs,
        "npcs_novos": new_npcs,
    }
    if normalized["tipo"] not in oportunidades.VALID_TYPES:
        raise EmergentSidequestAuthoringError(
            "tipo deve reutilizar um tipo de missão do lifecycle existente"
        )
    normalized["fases"] = _normalize_phases(
        spec["fases"], known_locations={item["id"] for item in locations}
    )
    normalized["antagonistas"] = _normalize_antagonists(
        spec["antagonistas"], package=package, npc_map=npc_map, new_npc_ids=new_npc_ids
    )
    normalized["juppongatana"] = _normalize_juppongatana(spec["juppongatana"], package=package)
    normalized["condicoes_sucesso"] = _normalize_condition_list(
        spec["condicoes_sucesso"], "condicoes_sucesso", MAX_SUCCESS_CONDITIONS
    )
    normalized["condicoes_falha"] = _normalize_condition_list(
        spec["condicoes_falha"], "condicoes_falha", MAX_FAILURE_CONDITIONS
    )
    normalized["stakes"] = _normalize_stakes(spec["stakes"])
    normalized["recompensas"] = _normalize_rewards(spec["recompensas"], package=package)
    normalized["relacao_canone"] = _normalize_canon_relation(spec["relacao_canone"], package=package)
    secrets = _list(spec["segredos"], "segredos")
    if len(secrets) > MAX_SECRETS:
        raise EmergentSidequestAuthoringError("segredos excede orçamento")
    normalized["segredos"] = [_text(item, f"segredos[{pos}]") for pos, item in enumerate(secrets)]
    normalized["bifurcacoes"] = _normalize_branches(spec["bifurcacoes"])
    _agency_scan(normalized)
    return package, normalized, sources


def _budget_state(
    repo: Path, *, qid: str | None = None
) -> tuple[dict[str, Any], dict[str, Any], list[str], dict[str, Any] | None]:
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise EmergentSidequestAuthoringError(str(exc)) from exc
    existing = state["missoes"].get(mission_id(qid)) if qid is not None else None
    active, opened = oportunidades._mission_counts(state)
    if not isinstance(existing, dict):
        existing = None
        if active >= index["orcamento"]["max_ativas"]:
            raise EmergentSidequestAuthoringError("limite_ativas")
        if opened >= index["orcamento"]["max_em_aberto"]:
            raise EmergentSidequestAuthoringError("limite_abertas")
    return index, state, [oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix()], existing


def _fingerprint_sources(repo: Path, sources: list[str]) -> list[dict[str, Any]]:
    result = []
    for raw in sorted(dict.fromkeys(sources)):
        path = repo / raw
        result.append({
            "fonte": raw,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None,
        })
    return result


def _preparation_id(
    repo: Path, package: dict[str, Any], normalized_spec: dict[str, Any], sources: list[str]
) -> str:
    payload = {
        "package_digest": _hash_payload(package),
        "spec_digest": _hash_payload(normalized_spec),
        "sources": _fingerprint_sources(repo, sources),
    }
    return PREPARATION_PREFIX + _hash_payload(payload)[:24]


def _prepare_summary(
    *, qid: str, mid: str, preparation_id: str, spec: dict[str, Any],
    sources: list[str], existing: dict[str, Any] | None,
) -> dict[str, Any]:
    result = {
        "ok": True,
        "fase": "preparacao",
        "resultado": "ja_materializada" if existing else "pronta_para_oferta",
        "read_only": True,
        "mutacoes_aplicadas": False,
        "quest_id": qid,
        "mission_id": mid,
        "preparacao_id": preparation_id,
        "titulo": spec["titulo"],
        "tipo": spec["tipo"],
        "quest_giver": spec["quest_giver"],
        "oferta": spec["oferta"],
        "prazo": spec["prazo"],
        "objetivo": spec["objetivo"],
        "resumo_estrutura": {
            "fases": len(spec["fases"]), "locais": len(spec["locais"]),
            "npcs_existentes": len(spec["npcs_existentes"]), "npcs_novos": len(spec["npcs_novos"]),
            "antagonistas": len(spec["antagonistas"]), "juppongatana": len(spec["juppongatana"]),
            "recompensas": len(spec["recompensas"]), "segredos": len(spec["segredos"]),
            "bifurcacoes": len(spec["bifurcacoes"]),
        },
        "relacao_canone": spec["relacao_canone"],
        "recompensas_planejadas": [
            {"id": item["id"], "tipo": item["tipo"], "modo": item["modo"],
             "valor_aproximado": item["valor_aproximado"]}
            for item in spec["recompensas"]
        ],
        "stakes": {
            "em_risco": spec["stakes"]["em_risco"],
            "consequencia_expiracao": spec["stakes"]["consequencia_expiracao"],
        },
        "regra": (
            "narrar a oferta é obrigatório antes de materializar; preparar não cria "
            "quest, NPC, recompensa, presença, consequência nem rewrite canônico"
        ),
        "fontes_lidas": list(dict.fromkeys(sources)),
        "metricas": {"escritas": 0, "fragmentos_task33": 0, "fragmentos_task36": 0,
                     "transcricoes": 0, "scans_globais": 0},
    }
    size = len(_yaml_bytes(result))
    if size > MAX_PREP_OUTPUT_BYTES:
        raise EmergentSidequestAuthoringError(
            f"saída de preparação excede {MAX_PREP_OUTPUT_BYTES} bytes: {size}"
        )
    result["orcamento_saida"] = {"bytes": size, "max_bytes": MAX_PREP_OUTPUT_BYTES}
    return result


def prepare(repo: Path, *, package: Any, quest: Any) -> dict[str, Any]:
    package_n, spec, reference_sources = normalize_spec(repo, package, quest)
    qid = _quest_id(package_n, spec)
    mid = mission_id(qid)
    _, _, budget_sources, existing = _budget_state(repo, qid=qid)
    sources = [*reference_sources, *budget_sources]
    prep_id = _preparation_id(repo, package_n, spec, sources)
    return _prepare_summary(
        qid=qid, mid=mid, preparation_id=prep_id, spec=spec, sources=sources, existing=existing
    )


def _quest_document(
    *, qid: str, preparation_id: str, package: dict[str, Any], spec: dict[str, Any],
    offer_scene_id: str, offer_summary: str,
) -> dict[str, Any]:
    doc = {
        "schema_sidequest_emergente": SCHEMA,
        "natureza": "reservado",
        "id": qid,
        "origem_engine": "task41_emergent_sidequest_authoring_registry_v2",
        "pacote_task40_digest": _hash_payload(package),
        "spec_digest": _hash_payload(spec),
        "preparacao_id": preparation_id,
        "oferta_materializada": {
            "cena_id": offer_scene_id,
            "quest_giver_id": spec["quest_giver"]["id"],
            "resumo": offer_summary,
        },
        **copy.deepcopy(spec),
        "guardrails_execucao": {
            "agencia_de_ren": "preservada",
            "npcs_novos": "nao_presentes_ate_canonizacao_em_cena",
            "recompensas": "declaradas_nao_concedidas_task43_45",
            "stakes": "declarados_nao_executados_task45",
            "relacao_canone": "candidatura_sem_rewrite_ate_task42",
            "scheduler": "proibido",
        },
    }
    _agency_scan(doc)
    if len(_yaml_bytes(doc)) > MAX_FRAGMENT_BYTES:
        raise EmergentSidequestAuthoringError(
            f"fragmento de sidequest excede {MAX_FRAGMENT_BYTES} bytes"
        )
    return doc


def _install_fragment(path: Path, doc: dict[str, Any]) -> bool:
    rendered = yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text(encoding="utf-8") != rendered:
            raise EmergentSidequestAuthoringError(f"fragmento órfão/divergente já existe: {path}")
        return False
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
        tmp = Path(handle.name)
    os.replace(tmp, path)
    return True


def _mission_record(
    *, qid: str, spec: dict[str, Any], package: dict[str, Any],
    preparation_id: str, offer_scene_id: str,
) -> dict[str, Any]:
    return {
        "id": mission_id(qid),
        "estado": "oferecida",
        "origem": "sidequest_emergente",
        "quest_id": qid,
        "arquivo": _quest_path(qid).as_posix(),
        "npc_id": spec["quest_giver"]["id"],
        "necessidade_id": qid,
        "tipo": spec["tipo"],
        "titulo": spec["titulo"],
        "objetivo": spec["objetivo"],
        "janela": copy.deepcopy(spec["prazo"]),
        "pode_reabrir": False,
        "consequencia_sem_ren": spec["stakes"]["consequencia_expiracao"],
        "oferecida_em": copy.deepcopy(package["prazo_mundo"]["agora"]),
        "cena_oferta": offer_scene_id,
        "preparacao_id": preparation_id,
        "recompensas_declaradas": [item["id"] for item in spec["recompensas"]],
    }


def materialize(
    repo: Path,
    *,
    package: Any,
    quest: Any,
    preparation_id: str,
    offer_was_narrated: bool,
    offer_scene_id: str | None = None,
    offer_summary: str | None = None,
) -> dict[str, Any]:
    if not isinstance(preparation_id, str) or not PREPARATION_RE.fullmatch(preparation_id):
        raise EmergentSidequestAuthoringError("preparacao_id Task41 inválido")
    if offer_was_narrated is not True:
        return {
            "ok": True, "resultado": "oferta_nao_materializada", "read_only": True,
            "mutacoes_aplicadas": False,
            "regra": "sem oferta efetivamente narrada não nasce quest persistente",
            "fontes_lidas": [],
        }
    scene = _id(offer_scene_id, "oferta.cena_id")
    summary = _text(offer_summary, "oferta.resumo", minimum=20, maximum=320)
    package_n, spec, reference_sources = normalize_spec(repo, package, quest)
    qid = _quest_id(package_n, spec)
    mid = mission_id(qid)
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise EmergentSidequestAuthoringError(str(exc)) from exc
    existing = state["missoes"].get(mid)
    fragment_path = repo / _quest_path(qid)
    if isinstance(existing, dict):
        if existing.get("quest_id") != qid or existing.get("origem") != "sidequest_emergente":
            raise EmergentSidequestAuthoringError(f"colisão de mission_id: {mid}")
        stored = _map(_load(fragment_path), _quest_path(qid).as_posix())
        if stored.get("spec_digest") != _hash_payload(spec):
            raise EmergentSidequestAuthoringError("quest já materializada com conteúdo divergente")
        return {
            "ok": True, "resultado": "ja_materializada", "quest_id": qid,
            "mission_id": mid, "estado": existing.get("estado"),
            "arquivo": _quest_path(qid).as_posix(), "mutacoes_aplicadas": False,
            "fontes_lidas": [oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix(),
                            _quest_path(qid).as_posix()],
        }
    active, opened = oportunidades._mission_counts(state)
    if active >= index["orcamento"]["max_ativas"]:
        raise EmergentSidequestAuthoringError("limite_ativas")
    if opened >= index["orcamento"]["max_em_aberto"]:
        raise EmergentSidequestAuthoringError("limite_abertas")
    sources = [*reference_sources, oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix()]
    fresh_prep = _preparation_id(repo, package_n, spec, sources)
    if fresh_prep != preparation_id:
        raise EmergentSidequestAuthoringError(
            "preparação Task41 ficou obsoleta; refaça preparar antes de materializar"
        )
    doc = _quest_document(
        qid=qid, preparation_id=preparation_id, package=package_n, spec=spec,
        offer_scene_id=scene, offer_summary=summary,
    )
    fragment_created = _install_fragment(fragment_path, doc)
    state["missoes"][mid] = _mission_record(
        qid=qid, spec=spec, package=package_n, preparation_id=preparation_id,
        offer_scene_id=scene,
    )
    state["historico_recente"].append({
        "tipo": "sidequest_emergente_materializada", "id": mid, "quest_id": qid,
        "npc_id": spec["quest_giver"]["id"],
        "em": copy.deepcopy(package_n["prazo_mundo"]["agora"]),
    })
    state["historico_recente"] = state["historico_recente"][-oportunidades.MAX_HISTORY:]
    oportunidades.atomic(repo / oportunidades.STATE, state)
    return {
        "ok": True, "resultado": "materializada", "quest_id": qid,
        "mission_id": mid, "estado": "oferecida", "arquivo": _quest_path(qid).as_posix(),
        "fragmento_criado": fragment_created, "mutacoes_aplicadas": True,
        "arquivos_alterados": [_quest_path(qid).as_posix(), oportunidades.STATE.as_posix()],
        "regra": (
            "quest nasceu porque a oferta foi narrada; aceitar/adiar/recusar continua "
            "no lifecycle existente e nenhum reward/stake/rewrite foi executado"
        ),
        "fontes_lidas": list(dict.fromkeys([*sources, _quest_path(qid).as_posix()])),
    }


def _emergent_missions(state: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for mid, mission in state.get("missoes", {}).items():
        if isinstance(mission, dict) and mission.get("origem") == "sidequest_emergente":
            result.append({"_mid": mid, **mission})
    return sorted(result, key=lambda item: str(item.get("id")))


def list_quests(repo: Path) -> dict[str, Any]:
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise EmergentSidequestAuthoringError(str(exc)) from exc
    quests = [{
        "mission_id": item["id"], "quest_id": item.get("quest_id"),
        "titulo": item.get("titulo"), "estado": item.get("estado"),
        "quest_giver": item.get("npc_id"), "prazo": copy.deepcopy(item.get("janela")),
        "arquivo": item.get("arquivo"),
    } for item in _emergent_missions(state)]
    return {
        "ok": True, "quantidade": len(quests), "quests": quests,
        "fontes_lidas": [oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix()],
        "regra": "listar não abre fragmentos completos de sidequest",
    }


def show(repo: Path, ref: str) -> dict[str, Any]:
    listing = list_quests(repo)
    matches = [item for item in listing["quests"] if ref in {item["mission_id"], item["quest_id"]}]
    if len(matches) != 1:
        raise EmergentSidequestAuthoringError(f"sidequest emergente não encontrada de forma única: {ref}")
    meta = matches[0]
    rel = Path(str(meta["arquivo"]))
    doc = _map(_load(repo / rel), rel.as_posix())
    if (
        doc.get("schema_sidequest_emergente") != SCHEMA or doc.get("natureza") != "reservado"
        or doc.get("id") != meta["quest_id"]
    ):
        raise EmergentSidequestAuthoringError("fragmento emergente inválido")
    _agency_scan(doc)
    return {
        "ok": True, "mission_id": meta["mission_id"], "estado": meta["estado"],
        "prazo": meta["prazo"], "quest": doc,
        "fontes_lidas": [oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix(), rel.as_posix()],
    }


def check(repo: Path) -> dict[str, Any]:
    errors, count = [], 0
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
        for mission in _emergent_missions(state):
            count += 1
            qid = mission.get("quest_id")
            if not isinstance(qid, str) or not QUEST_RE.fullmatch(qid):
                errors.append(f"{mission.get('id')}: quest_id emergente inválido")
                continue
            if mission.get("id") != mission_id(qid):
                errors.append(f"{qid}: mission_id divergente")
            rel = _quest_path(qid)
            if mission.get("arquivo") != rel.as_posix():
                errors.append(f"{qid}: caminho de fragmento divergente")
                continue
            doc = _map(_load(repo / rel), rel.as_posix())
            if (
                doc.get("schema_sidequest_emergente") != SCHEMA
                or doc.get("natureza") != "reservado" or doc.get("id") != qid
            ):
                errors.append(f"{qid}: fragmento/schema inválido")
                continue
            if len(_yaml_bytes(doc)) > MAX_FRAGMENT_BYTES:
                errors.append(f"{qid}: fragmento excede orçamento")
            _agency_scan(doc)
            guard = doc.get("guardrails_execucao", {})
            if guard.get("recompensas") != "declaradas_nao_concedidas_task43_45":
                errors.append(f"{qid}: guardrail de recompensas divergente")
            if guard.get("stakes") != "declarados_nao_executados_task45":
                errors.append(f"{qid}: guardrail de stakes divergente")
    except (EmergentSidequestAuthoringError, oportunidades.OpportunityError) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors, "erros": errors, "quests_emergentes": count,
        "max_fragment_bytes": MAX_FRAGMENT_BYTES, "max_fases": MAX_PHASES,
        "schedulers_novos": 0, "rng_novo": 0, "scans_globais": 0, "transcricoes_hot": 0,
    }


def _read_stdin_payload() -> dict[str, Any]:
    import sys
    try:
        raw = yaml.safe_load(sys.stdin.read())
    except yaml.YAMLError as exc:
        raise EmergentSidequestAuthoringError(str(exc)) from exc
    return _map(raw, "stdin")


def _dump(value: Any) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("preparar", help="valida pacote Task40 + quest via stdin; zero writes")
    material = sub.add_parser(
        "materializar", help="revalida e registra somente depois de oferta efetivamente narrada"
    )
    material.add_argument("--preparacao-id", required=True)
    material.add_argument("--oferta-narrada", action="store_true")
    material.add_argument("--cena-id")
    material.add_argument("--resumo-oferta")
    sub.add_parser("listar", help="lista registry compacto sem abrir fragmentos")
    show_parser = sub.add_parser("mostrar", help="abre uma quest por mission_id ou quest_id")
    show_parser.add_argument("id")
    sub.add_parser("check", help="valida registry e fragmentos registrados")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "preparar":
            payload = _read_stdin_payload()
            result = prepare(repo, package=payload.get("pacote_task40"), quest=payload.get("quest"))
        elif args.cmd == "materializar":
            payload = _read_stdin_payload()
            result = materialize(
                repo, package=payload.get("pacote_task40"), quest=payload.get("quest"),
                preparation_id=args.preparacao_id, offer_was_narrated=args.oferta_narrada,
                offer_scene_id=args.cena_id, offer_summary=args.resumo_oferta,
            )
        elif args.cmd == "listar":
            result = list_quests(repo)
        elif args.cmd == "mostrar":
            result = show(repo, args.id)
        else:
            result = check(repo)
    except (EmergentSidequestAuthoringError, mundo.WorldEngineError) as exc:
        print(_dump({"ok": False, "erro": str(exc)}), end="")
        return 2
    print(_dump(result), end="")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
