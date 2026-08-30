#!/usr/bin/env python3
"""Task 43 — Quest Rewards, Discoveries & Losses.

Sidequests emergentes recebem um contrato de recompensas dirigido. O contrato
classifica tudo que a Task41 já declarou, controla descoberta/perda/obtenção e
materializa efeitos reais pelo writer transacional existente. Não há RNG,
scheduler, scan global nem perda/recompensa inventada depois do fato.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

import oportunidades
import recompensas
import sidequests_emergentes as emergent
import transacoes
import turno

CONTRACTS_DIR = Path("narrador/sidequests-emergentes/recompensas")
STATE_PATH = Path("estado/estado-atual.yaml")
SHEET_PATH = Path("personagens/jogador/ficha.yaml")
SCHEMA = 1
MAX_BYTES = 24 * 1024
MAX_HISTORY = 32
MAX_TEXT = 520
MAX_EVIDENCE = 360
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_:-]{0,95}$")

PHYSICAL = {"item", "item_magico", "consumivel", "pergaminho", "tesouro"}
MATERIAL = {"dinheiro", *PHYSICAL}
ASSETS = {"propriedade", "direito_de_uso", "servico", "contato", "favor", "acesso", "reputacao", "recurso"}
REWARD_TYPES = set(emergent.REWARD_TYPES) | {"progressao_canonica"}
LOSS_TYPES = {"dinheiro", *PHYSICAL, *ASSETS, "oportunidade", "posicao_institucional"}
STRONG_AUTHORITY = {"propriedade", "direito_de_uso"}
AUTHORITY_TYPES = {"quest_giver", "npc_existente", "instituicao", "proprietario", "mundo", "outro"}
DISCOVERY_FAILURES = {"permanece_oculta", "perdida_permanentemente"}
DISCOVERY_DELIVERY = {"imediata", "desfecho"}
FORBIDDEN_PROOF = (
    "narrador/sidequests-emergentes/",
    "narrador/arcos/parte_1/intencoes/",
    "narrador/arcos/parte_1/eventos/",
)
GOLD_CAPS = {
    1: {"baixo": 25, "moderado": 100, "alto": 250},
    2: {"baixo": 100, "moderado": 500, "alto": 1500},
    3: {"baixo": 500, "moderado": 2500, "alto": 7500},
    4: {"baixo": 2500, "moderado": 10000, "alto": 30000},
}


class QuestRewardError(ValueError):
    pass


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise QuestRewardError(str(exc)) from exc


def _map(v: Any, label: str) -> dict[str, Any]:
    if not isinstance(v, dict):
        raise QuestRewardError(f"{label} deve ser mapa")
    return v


def _list(v: Any, label: str) -> list[Any]:
    if not isinstance(v, list):
        raise QuestRewardError(f"{label} deve ser lista")
    return v


def _text(v: Any, label: str, minimum: int = 1, maximum: int = MAX_TEXT) -> str:
    if not isinstance(v, str):
        raise QuestRewardError(f"{label} deve ser texto")
    out = " ".join(v.strip().split())
    if len(out) < minimum or len(out) > maximum:
        raise QuestRewardError(f"{label} deve ter {minimum}..{maximum} caracteres")
    return out


def _id(v: Any, label: str) -> str:
    out = _text(v, label, maximum=128)
    if not ID_RE.fullmatch(out):
        raise QuestRewardError(f"{label} deve usar id ASCII minúsculo estável")
    return out


def _slug(v: Any, label: str) -> str:
    out = _text(v, label, maximum=96)
    if not SLUG_RE.fullmatch(out):
        raise QuestRewardError(f"{label} deve usar slug ASCII minúsculo")
    return out


def _bytes(v: Any) -> bytes:
    return yaml.safe_dump(v, allow_unicode=True, sort_keys=False).encode("utf-8")


def _atomic(path: Path, doc: dict[str, Any]) -> None:
    raw = _bytes(doc)
    if len(raw) > MAX_BYTES:
        raise QuestRewardError(f"fragmento Task43 excede {MAX_BYTES} bytes")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=f".{path.name}.", delete=False) as h:
        h.write(raw); h.flush(); os.fsync(h.fileno()); tmp = Path(h.name)
    os.replace(tmp, path)


def _contract_rel(quest_id: str) -> Path:
    qid = _id(quest_id, "quest_id")
    if not qid.startswith("qse-"):
        raise QuestRewardError("quest_id não é emergente Task41")
    return CONTRACTS_DIR / f"{qid}.yaml"


def _mission(repo: Path, ref: str) -> tuple[dict[str, Any], str, dict[str, Any]]:
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise QuestRewardError(str(exc)) from exc
    matches = [
        (mid, m) for mid, m in state.get("missoes", {}).items()
        if isinstance(m, dict) and m.get("origem") == "sidequest_emergente"
        and ref in {mid, m.get("id"), m.get("quest_id")}
    ]
    if len(matches) != 1:
        raise QuestRewardError(f"sidequest emergente inexistente/ambígua: {ref}")
    return state, matches[0][0], matches[0][1]


def _quest(repo: Path, mission: dict[str, Any]) -> dict[str, Any]:
    raw = mission.get("arquivo")
    if not isinstance(raw, str) or not raw.startswith("narrador/sidequests-emergentes/quests/"):
        raise QuestRewardError("missão Task41 sem fragmento reservado válido")
    doc = _map(_load(repo / raw), raw)
    if doc.get("schema_sidequest_emergente") != 2 or doc.get("id") != mission.get("quest_id"):
        raise QuestRewardError("fragmento Task41 inválido/divergente")
    return doc


def _proof(repo: Path, raw: Any, label: str) -> dict[str, str]:
    data = _map(raw, label)
    if set(data) != {"fonte", "evidencia"}:
        raise QuestRewardError(f"{label} exige fonte e evidencia")
    source = _text(data["fonte"], f"{label}.fonte", maximum=240)
    rel = Path(source)
    if rel.is_absolute() or ".." in rel.parts or any(source.startswith(p) for p in FORBIDDEN_PROOF):
        raise QuestRewardError("planejamento reservado não pode servir de prova")
    path = repo / rel
    if not path.is_file():
        raise QuestRewardError(f"fonte inexistente: {source}")
    literal = _text(data["evidencia"], f"{label}.evidencia", 8, MAX_EVIDENCE)
    if literal not in path.read_text(encoding="utf-8"):
        raise QuestRewardError(f"evidência literal não encontrada em {source}")
    return {"fonte": source, "evidencia": literal}


def _authority(repo: Path, raw: Any, reward_type: str, giver: str) -> dict[str, Any]:
    data = _map(raw, "autoridade_concedente")
    if set(data) - {"tipo", "id", "fonte", "evidencia"} or not {"tipo", "id"} <= set(data):
        raise QuestRewardError("autoridade exige tipo/id; fonte/evidencia são opcionais pareadas")
    kind = _text(data["tipo"], "autoridade.tipo", maximum=32)
    aid = _id(data["id"], "autoridade.id")
    if kind not in AUTHORITY_TYPES:
        raise QuestRewardError("autoridade.tipo inválido")
    if kind == "quest_giver" and aid != giver:
        raise QuestRewardError("autoridade quest_giver deve ser o quest-giver real")
    if (data.get("fonte") is None) != (data.get("evidencia") is None):
        raise QuestRewardError("fonte/evidencia da autoridade devem aparecer juntas")
    proof = None
    if data.get("fonte") is not None:
        proof = _proof(repo, {"fonte": data["fonte"], "evidencia": data["evidencia"]}, "autoridade.prova")
    if reward_type in STRONG_AUTHORITY and proof is None:
        raise QuestRewardError(f"{reward_type} exige prova canônica explícita da autoridade")
    return {"tipo": kind, "id": aid, **({"prova": proof} if proof else {})}


def _effect(raw: Any, reward_type: str, value: str, envelope: dict[str, Any], label: str) -> dict[str, Any]:
    data = _map(raw, label); tier = int(envelope["tier"])
    if reward_type == "dinheiro":
        if set(data) != {"po"}:
            raise QuestRewardError("efeito dinheiro exige po")
        po = data["po"]
        if isinstance(po, bool) or not isinstance(po, (int, float)) or po <= 0:
            raise QuestRewardError("po deve ser positivo")
        if value not in GOLD_CAPS[tier] or float(po) > GOLD_CAPS[tier][value]:
            raise QuestRewardError(f"valor em PO excede teto {value} do tier {tier}")
        return {"po": float(po)}
    if reward_type in PHYSICAL:
        allowed = {"nome", "quantidade", "descricao_inventario", "tier", "raridade"}
        if set(data) - allowed or not {"nome", "quantidade", "descricao_inventario"} <= set(data):
            raise QuestRewardError("efeito de item inválido")
        qty = data["quantidade"]
        if isinstance(qty, bool) or not isinstance(qty, int) or not 1 <= qty <= 20:
            raise QuestRewardError("quantidade deve ficar entre 1 e 20")
        out = {
            "nome": _text(data["nome"], f"{label}.nome", maximum=160),
            "quantidade": qty,
            "descricao_inventario": _text(data["descricao_inventario"], f"{label}.descricao_inventario", maximum=320),
        }
        if reward_type == "item_magico":
            item_tier = data.get("tier")
            if isinstance(item_tier, bool) or not isinstance(item_tier, int) or not 1 <= item_tier <= tier:
                raise QuestRewardError(f"item mágico excede tier {tier} do envelope Task40")
            out["tier"] = item_tier
            if data.get("raridade") is not None:
                out["raridade"] = _text(data["raridade"], f"{label}.raridade", maximum=48)
        elif data.get("tier") is not None or data.get("raridade") is not None:
            raise QuestRewardError("tier/raridade só pertencem a item_magico")
        return out
    if reward_type == "informacao":
        if set(data) != {"ativo_id", "texto"}:
            raise QuestRewardError("informação exige ativo_id/texto")
        return {"ativo_id": _slug(data["ativo_id"], f"{label}.ativo_id"), "texto": _text(data["texto"], f"{label}.texto")}
    if reward_type == "progressao_canonica":
        if set(data) != {"ativo_id", "descricao"}:
            raise QuestRewardError("progressao_canonica exige ativo_id/descricao")
        return {"ativo_id": _slug(data["ativo_id"], f"{label}.ativo_id"), "descricao": _text(data["descricao"], f"{label}.descricao")}
    if reward_type in ASSETS:
        if set(data) != {"ativo_id", "nome", "descricao"}:
            raise QuestRewardError("ativo narrativo exige ativo_id/nome/descricao")
        return {
            "ativo_id": _slug(data["ativo_id"], f"{label}.ativo_id"),
            "nome": _text(data["nome"], f"{label}.nome", maximum=160),
            "descricao": _text(data["descricao"], f"{label}.descricao"),
        }
    raise QuestRewardError(f"tipo de recompensa sem efeito: {reward_type}")


def _cost(item: dict[str, Any]) -> int:
    if item["tipo"] not in MATERIAL:
        return 0
    value = item["valor_aproximado"]
    if value not in recompensas.V2_VALUE_COST:
        raise QuestRewardError("recompensa material não pode usar valor especial")
    return int(recompensas.V2_VALUE_COST[value]) + (int(recompensas.V2_IMPORTANCE_COST["especial"]) if item["tipo"] == "item_magico" else 0)


def _declared_rewards(quest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out = {}
    for raw in _list(quest.get("recompensas"), "quest.recompensas"):
        item = _map(raw, "quest.recompensas[]"); rid = _slug(item.get("id"), "reward.id")
        if rid in out:
            raise QuestRewardError(f"recompensa Task41 duplicada: {rid}")
        out[rid] = item
    if not out:
        raise QuestRewardError("Task41 não declarou recompensa")
    return out


def _reward(repo: Path, raw: Any, category: str, declared: dict[str, dict[str, Any]], quest: dict[str, Any], envelope: dict[str, Any]) -> dict[str, Any]:
    data = _map(raw, category); expected = {"id", "tipo", "efeito", "autoridade_concedente"}
    if category == "recompensas_descobríveis": expected.add("descoberta")
    if set(data) != expected:
        raise QuestRewardError(f"{category}: estrutura inválida")
    rid = _slug(data["id"], f"{category}.id"); dec = declared.get(rid)
    if not isinstance(dec, dict):
        raise QuestRewardError(f"{rid}: não declarado pela Task41")
    rtype = _text(data["tipo"], f"{rid}.tipo", maximum=32)
    if rtype not in REWARD_TYPES:
        raise QuestRewardError(f"{rid}: tipo inválido")
    dtype, mode = dec.get("tipo"), dec.get("modo")
    if rtype != dtype and not (rtype == "progressao_canonica" and dtype in {"recurso", "informacao"}):
        raise QuestRewardError(f"{rid}: tipo diverge da Task41")
    required_mode = {
        "recompensa_principal": {"sucesso"}, "recompensas_opcionais": {"sucesso", "condicional"},
        "recompensas_descobríveis": {"descoberta"}, "recompensas_condicionais": {"condicional"},
    }[category]
    if mode not in required_mode:
        raise QuestRewardError(f"{rid}: modo Task41 incompatível com {category}")
    value = _text(dec.get("valor_aproximado"), f"{rid}.valor", maximum=16)
    out = {
        "id": rid, "tipo": rtype, "categoria": category,
        "descricao": _text(dec.get("descricao"), f"{rid}.descricao"),
        "condicao": _text(dec.get("condicao"), f"{rid}.condicao"),
        "valor_aproximado": value,
        "efeito": _effect(data["efeito"], rtype, value, envelope, f"{rid}.efeito"),
        "autoridade_concedente": _authority(repo, data["autoridade_concedente"], rtype, str(quest["quest_giver"]["id"])),
    }
    if category == "recompensas_descobríveis":
        d = _map(data["descoberta"], f"{rid}.descoberta")
        if set(d) != {"condicao", "teste", "falha", "momento_entrega"}:
            raise QuestRewardError("descoberta exige condicao/teste/falha/momento_entrega")
        test = _map(d["teste"], f"{rid}.teste")
        if set(test) - {"requerido", "pericia", "cd"} or not isinstance(test.get("requerido"), bool):
            raise QuestRewardError("teste de descoberta inválido")
        nt = {"requerido": test["requerido"]}
        if test["requerido"]:
            nt["pericia"] = _text(test.get("pericia"), f"{rid}.pericia", maximum=80)
            cd = test.get("cd")
            if isinstance(cd, bool) or not isinstance(cd, int) or not 5 <= cd <= 35:
                raise QuestRewardError("CD de descoberta deve ficar entre 5 e 35")
            nt["cd"] = cd
        elif test.get("pericia") is not None or test.get("cd") is not None:
            raise QuestRewardError("teste não requerido não aceita perícia/CD")
        failure = _text(d["falha"], f"{rid}.falha", maximum=40); delivery = _text(d["momento_entrega"], f"{rid}.entrega", maximum=32)
        if failure not in DISCOVERY_FAILURES or delivery not in DISCOVERY_DELIVERY:
            raise QuestRewardError("falha/momento de descoberta inválido")
        out["descoberta"] = {"condicao": _text(d["condicao"], f"{rid}.condicao_descoberta"), "teste": nt, "falha": failure, "momento_entrega": delivery}
    return out


def _loss_effect(raw: Any, kind: str, label: str) -> dict[str, Any]:
    data = _map(raw, label)
    if kind == "dinheiro":
        if set(data) != {"po"} or isinstance(data["po"], bool) or not isinstance(data["po"], (int, float)) or data["po"] <= 0:
            raise QuestRewardError("perda de dinheiro exige po positivo")
        return {"po": float(data["po"])}
    if kind in PHYSICAL:
        if set(data) != {"descricao_inventario"}: raise QuestRewardError("perda de item exige descrição exata")
        return {"descricao_inventario": _text(data["descricao_inventario"], f"{label}.descricao", maximum=320)}
    if kind in ASSETS | {"oportunidade", "posicao_institucional"}:
        if set(data) != {"ativo_id"}: raise QuestRewardError("perda de ativo exige ativo_id")
        return {"ativo_id": _slug(data["ativo_id"], f"{label}.ativo_id")}
    raise QuestRewardError(f"tipo de perda não suportado: {kind}")


def _losses(raw: Any, quest: dict[str, Any]) -> list[dict[str, Any]]:
    declared = _list(_map(quest.get("stakes"), "quest.stakes").get("perdas_possiveis"), "quest.perdas")
    used, seen, out = set(), set(), []
    for pos, raw_item in enumerate(_list(raw, "perdas_possiveis")):
        data = _map(raw_item, f"perdas[{pos}]")
        if set(data) != {"id", "stake_tipo", "stake_alvo", "efeito"}: raise QuestRewardError("perda contratada exige id/stake_tipo/stake_alvo/efeito")
        lid = _slug(data["id"], f"perdas[{pos}].id"); kind = _id(data["stake_tipo"], f"{lid}.tipo"); target = _id(data["stake_alvo"], f"{lid}.alvo")
        if lid in seen or kind not in LOSS_TYPES: raise QuestRewardError(f"{lid}: perda duplicada/inválida")
        seen.add(lid)
        matches = [(i, x) for i, x in enumerate(declared) if i not in used and isinstance(x, dict) and x.get("tipo") == kind and x.get("alvo") == target]
        if len(matches) != 1: raise QuestRewardError(f"{lid}: perda não corresponde univocamente a stake Task41")
        idx, dec = matches[0]; used.add(idx)
        out.append({"id": lid, "tipo": kind, "alvo": target, "condicao": _text(dec.get("condicao"), f"{lid}.condicao"), "descricao": _text(dec.get("descricao"), f"{lid}.descricao"), "efeito": _loss_effect(data["efeito"], kind, f"{lid}.efeito")})
    if len(used) != len(declared): raise QuestRewardError("contrato deve classificar todas as perdas Task41")
    return out


def _normalize_contract(repo: Path, raw: Any, quest: dict[str, Any], package: dict[str, Any]) -> dict[str, Any]:
    data = _map(raw, "contrato_recompensa"); keys = {"recompensa_principal", "recompensas_opcionais", "recompensas_descobríveis", "recompensas_condicionais", "perdas_possiveis"}
    if set(data) != keys: raise QuestRewardError("contrato_recompensa possui estrutura inesperada")
    declared = _declared_rewards(quest); envelope = _map(package.get("envelope_recompensa"), "envelope_recompensa")
    principal = _reward(repo, data["recompensa_principal"], "recompensa_principal", declared, quest, envelope)
    optional = [_reward(repo, x, "recompensas_opcionais", declared, quest, envelope) for x in _list(data["recompensas_opcionais"], "opcionais")]
    discoverable = [_reward(repo, x, "recompensas_descobríveis", declared, quest, envelope) for x in _list(data["recompensas_descobríveis"], "descobríveis")]
    conditional = [_reward(repo, x, "recompensas_condicionais", declared, quest, envelope) for x in _list(data["recompensas_condicionais"], "condicionais")]
    all_rewards = [principal, *optional, *discoverable, *conditional]; ids = [x["id"] for x in all_rewards]
    if len(ids) != len(set(ids)) or set(ids) != set(declared): raise QuestRewardError("contrato deve classificar exatamente todas as recompensas Task41")
    points = sum(_cost(x) for x in all_rewards); physical = sum(x["tipo"] in PHYSICAL for x in all_rewards)
    if points > int(envelope["pontos"]): raise QuestRewardError(f"custo material {points} excede envelope {envelope['pontos']}")
    if physical > int(envelope["max_itens"]): raise QuestRewardError("quantidade de itens excede envelope Task40")
    ceiling = envelope.get("teto_valor")
    if ceiling in emergent.VALUE_RANK:
        for x in all_rewards:
            if x["tipo"] in MATERIAL and (x["valor_aproximado"] not in emergent.VALUE_RANK or emergent.VALUE_RANK[x["valor_aproximado"]] > emergent.VALUE_RANK[ceiling]):
                raise QuestRewardError(f"{x['id']}: valor material excede teto {ceiling}")
    return {"recompensa_principal": principal, "recompensas_opcionais": optional, "recompensas_descobríveis": discoverable, "recompensas_condicionais": conditional, "perdas_possiveis": _losses(data["perdas_possiveis"], quest), "orcamento": {"tier": int(envelope["tier"]), "periculosidade": envelope["periculosidade"], "pontos_disponiveis": int(envelope["pontos"]), "pontos_material": points, "max_itens": int(envelope["max_itens"]), "itens": physical, "teto_valor": ceiling}}


def _initial_state(contract: dict[str, Any]) -> dict[str, Any]:
    rewards = {}
    for x in [contract["recompensa_principal"], *contract["recompensas_opcionais"], *contract["recompensas_descobríveis"], *contract["recompensas_condicionais"]]:
        rewards[x["id"]] = {"estado": "oculta" if x["categoria"] == "recompensas_descobríveis" else "pendente", "tentativas_descoberta": 0, "transacao": None}
    return {"recompensas": rewards, "perdas": {x["id"]: {"estado": "pendente", "transacao": None} for x in contract["perdas_possiveis"]}, "historico_recente": []}


def register_contract(repo: Path, mission_ref: str, *, package_raw: Any, contract_raw: Any) -> dict[str, Any]:
    opp, mid, mission = _mission(repo, mission_ref); quest = _quest(repo, mission)
    try: package = emergent._validate_task40_package(package_raw)
    except emergent.EmergentSidequestAuthoringError as exc: raise QuestRewardError(str(exc)) from exc
    if emergent._hash_payload(package) != quest.get("pacote_task40_digest"): raise QuestRewardError("pacote Task40 diverge do digest Task41")
    contract = _normalize_contract(repo, contract_raw, quest, package); rel = _contract_rel(str(mission["quest_id"])); path = repo / rel
    doc = {"schema_recompensas_sidequest": SCHEMA, "natureza": "reservado", "mission_id": mid, "quest_id": mission["quest_id"], "quest_file": mission["arquivo"], "pacote_task40_digest": quest["pacote_task40_digest"], "contrato_recompensa": contract, "estado": _initial_state(contract), "guardrails": {"descoberta_nao_e_obtencao": True, "perda_exige_contrato_e_prova": True, "efeito_real_transacional": True, "scheduler": "proibido"}}
    created = False
    if path.is_file():
        old = _map(_load(path), rel.as_posix())
        if old.get("mission_id") != mid or old.get("contrato_recompensa") != contract: raise QuestRewardError("contrato Task43 existente diverge")
    else: _atomic(path, doc); created = True
    changed = mission.get("contrato_recompensa") != rel.as_posix()
    if changed: mission["contrato_recompensa"] = rel.as_posix(); oportunidades.atomic(repo / oportunidades.STATE, opp)
    return {"ok": True, "resultado": "contrato_registrado" if created else "contrato_ja_existia", "mission_id": mid, "quest_id": mission["quest_id"], "arquivo": rel.as_posix(), "mission_pointer_reparado": changed, "orcamento": contract["orcamento"]}


def _load_contract(repo: Path, mission: dict[str, Any], mid: str) -> tuple[dict[str, Any], Path]:
    expected = _contract_rel(str(mission.get("quest_id"))).as_posix()
    if mission.get("contrato_recompensa") != expected: raise QuestRewardError(f"{mid}: sidequest sem contrato_recompensa Task43 obrigatório")
    doc = _map(_load(repo / expected), expected)
    if doc.get("schema_recompensas_sidequest") != SCHEMA or doc.get("mission_id") != mid or doc.get("quest_id") != mission.get("quest_id"): raise QuestRewardError("fragmento Task43 inválido")
    state = _map(doc.get("estado"), "Task43.estado"); _map(state.get("recompensas"), "estado.recompensas"); _map(state.get("perdas"), "estado.perdas")
    if len(_list(state.get("historico_recente"), "historico")) > MAX_HISTORY: raise QuestRewardError("histórico Task43 excede orçamento")
    return doc, Path(expected)


def _rewards(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {x["id"]: x for x in [contract["recompensa_principal"], *contract["recompensas_opcionais"], *contract["recompensas_descobríveis"], *contract["recompensas_condicionais"]]}


def _loss_map(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {x["id"]: x for x in contract["perdas_possiveis"]}


def _history(doc: dict[str, Any], item: dict[str, Any]) -> None:
    h = doc["estado"]["historico_recente"]; h.append(item); doc["estado"]["historico_recente"] = h[-MAX_HISTORY:]


def _effective(repo: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    state = _map(_load(repo / STATE_PATH), STATE_PATH.as_posix()); sheet = _map(_load(repo / SHEET_PATH), SHEET_PATH.as_posix())
    try:
        pending = transacoes.load_pending(repo); state, _ = transacoes.overlay_target(state, pending, "estado"); sheet, _ = transacoes.overlay_target(sheet, pending, "ficha")
    except (transacoes.TransactionError, OSError, ValueError) as exc: raise QuestRewardError(str(exc)) from exc
    return state, sheet


def _inventory_text(r: dict[str, Any]) -> str:
    q = int(r["efeito"].get("quantidade", 1)); text = r["efeito"]["descricao_inventario"]
    return f"{q}× {text}" if q > 1 else text


def _asset(mission: dict[str, Any], r: dict[str, Any]) -> dict[str, Any]:
    e = r["efeito"]
    return {"id": e["ativo_id"], "tipo": r["tipo"], "nome": e.get("nome") or e["ativo_id"], "descricao": e.get("descricao") or e.get("texto") or r["descricao"], "origem": f"sidequest:{mission['quest_id']}:{r['id']}"}


def _reward_deltas(repo: Path, mission: dict[str, Any], r: dict[str, Any]) -> list[dict[str, Any]]:
    kind, e = r["tipo"], r["efeito"]; state, _ = _effective(repo)
    if kind == "dinheiro": return [{"alvo": "estado", "op": "inc", "caminho": "recursos.dinheiro.po", "valor": e["po"]}]
    if kind in PHYSICAL:
        text = _inventory_text(r); return [{"alvo": "ficha", "op": "append", "caminho": "equipamento.itens", "valor": text}, {"alvo": "estado", "op": "append", "caminho": "equipamento_em_posse.itens_importantes", "valor": text}]
    if kind == "informacao": return [{"alvo": "conhecimento", "op": "registrar", "valor": {"tipo": "recompensa_sidequest", "texto": e["texto"], "fonte": f"sidequest:{mission['quest_id']}:{r['id']}"}}]
    if kind == "progressao_canonica": return [{"alvo": "progressao", "op": "registrar", "valor": {"titulo": e["ativo_id"], "descricao": e["descricao"], "fonte": f"sidequest:{mission['quest_id']}:{r['id']}"}}]
    if kind in ASSETS:
        record = _asset(mission, r); collision = next((x for x in (((state.get("ativos_narrativos") or {}).get(kind)) or []) if isinstance(x, dict) and x.get("id") == record["id"]), None)
        if collision and collision.get("origem") != record["origem"]: raise QuestRewardError(f"ativo {record['id']} já existe com outra proveniência")
        return [{"alvo": "estado", "op": "append", "caminho": f"ativos_narrativos.{kind}", "valor": record}]
    raise QuestRewardError(f"tipo sem delta: {kind}")


def _loss_deltas(repo: Path, loss: dict[str, Any]) -> list[dict[str, Any]]:
    kind, e = loss["tipo"], loss["efeito"]; state, sheet = _effective(repo)
    if kind == "dinheiro":
        po = (((state.get("recursos") or {}).get("dinheiro") or {}).get("po"))
        if not isinstance(po, (int, float)) or po < e["po"]: raise QuestRewardError("perda excede PO efetivamente possuídos")
        return [{"alvo": "estado", "op": "inc", "caminho": "recursos.dinheiro.po", "valor": -e["po"]}]
    if kind in PHYSICAL:
        text = e["descricao_inventario"]; a = (((sheet.get("equipamento") or {}).get("itens")) or []); b = (((state.get("equipamento_em_posse") or {}).get("itens_importantes")) or [])
        if text not in a or text not in b: raise QuestRewardError("item contratado para perda não está em posse")
        return [{"alvo": "ficha", "op": "remove", "caminho": "equipamento.itens", "valor": text}, {"alvo": "estado", "op": "remove", "caminho": "equipamento_em_posse.itens_importantes", "valor": text}]
    assets = (((state.get("ativos_narrativos") or {}).get(kind)) or []); record = next((x for x in assets if isinstance(x, dict) and x.get("id") == e["ativo_id"]), None)
    if not record: raise QuestRewardError(f"ativo {e['ativo_id']} não existe; falha não pode inventar perda")
    return [{"alvo": "estado", "op": "remove", "caminho": f"ativos_narrativos.{kind}", "valor": copy.deepcopy(record)}]


def _txid(mid: str, action: str, ids: list[str]) -> str:
    return "task43-" + hashlib.sha256(f"task43|{mid}|{action}|{'|'.join(sorted(ids))}".encode()).hexdigest()[:20]


def _tx_exists(repo: Path, txid: str) -> bool:
    try:
        if any(x.get("id") == txid for x in transacoes.load_pending(repo)): return True
        session = turno.current_session(repo)
    except (transacoes.TransactionError, OSError, ValueError) as exc: raise QuestRewardError(str(exc)) from exc
    ledger = repo / "sessoes" / f"{session:03d}" / turno.LEDGER_NAME
    if not ledger.is_file(): return False
    for n, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip(): continue
        try: item = json.loads(line)
        except json.JSONDecodeError as exc: raise QuestRewardError(f"ledger inválido {ledger}:{n}: {exc}") from exc
        if txid in (item.get("transacoes") or []): return True
    return False


def _write(repo: Path, mid: str, action: str, ids: list[str], narration: str, deltas: list[dict[str, Any]], summary: str) -> dict[str, Any]:
    txid = _txid(mid, action, ids)
    try:
        result = turno.register_transaction(repo, {"id": txid, "narracao": _text(narration, "narracao", 20, 2400), "resumo": _text(summary, "resumo", 12, 500), "modo": "interacao", "tags": ["task43-recompensa-sidequest", f"missao:{mid}"], "deltas": deltas})
    except (transacoes.TransactionError, OSError, yaml.YAMLError) as exc: raise QuestRewardError(str(exc)) from exc
    return {"transacao_id": txid, "writer": result}


def resolve_discovery(repo: Path, mission_ref: str, reward_id: str, *, success: bool, evidence: Any, test_result: Any | None = None, narration: str | None = None) -> dict[str, Any]:
    _, mid, mission = _mission(repo, mission_ref)
    if mission.get("estado") not in {"aceita", "concluida"}: raise QuestRewardError("descoberta exige sidequest aceita/em conclusão")
    doc, rel = _load_contract(repo, mission, mid); rewards = _rewards(doc["contrato_recompensa"]); rid = _slug(reward_id, "reward_id"); r = rewards.get(rid)
    if not r or r.get("categoria") != "recompensas_descobríveis": raise QuestRewardError(f"{rid}: não é descobrível")
    rs = doc["estado"]["recompensas"][rid]
    if rs["estado"] in {"obtida", "perdida"}: return {"ok": True, "resultado": f"ja_{rs['estado']}", "reward_id": rid, "transacao_id": rs.get("transacao")}
    proof = _proof(repo, evidence, f"descoberta.{rid}.evidencia"); test = r["descoberta"]["teste"]; nt = None
    if test["requerido"]:
        tr = _map(test_result, "teste_resultado")
        if set(tr) != {"rotulo", "sucesso"} or not isinstance(tr["sucesso"], bool): raise QuestRewardError("teste_resultado exige rotulo/sucesso")
        nt = {"rotulo": _text(tr["rotulo"], "teste.rotulo", maximum=180), "sucesso": tr["sucesso"]}
        if nt["sucesso"] != success: raise QuestRewardError("resultado diverge do teste")
    elif test_result is not None: raise QuestRewardError("recompensa sem teste não aceita teste_resultado")
    rs["tentativas_descoberta"] = int(rs.get("tentativas_descoberta", 0)) + 1
    if not success:
        rs["estado"] = "perdida" if r["descoberta"]["falha"] == "perdida_permanentemente" else "oculta"; rs["ultima_descoberta"] = {"sucesso": False, "evidencia": proof, "teste": nt}; _history(doc, {"tipo": "descoberta_falhou", "reward_id": rid, "estado": rs["estado"]}); _atomic(repo / rel, doc)
        return {"ok": True, "resultado": "perdida_permanentemente" if rs["estado"] == "perdida" else "permanece_oculta", "reward_id": rid, "transacao_id": None}
    if r["descoberta"]["momento_entrega"] == "desfecho":
        rs["estado"] = "descoberta"; rs["ultima_descoberta"] = {"sucesso": True, "evidencia": proof, "teste": nt}; _history(doc, {"tipo": "recompensa_descoberta", "reward_id": rid}); _atomic(repo / rel, doc)
        return {"ok": True, "resultado": "descoberta", "reward_id": rid, "transacao_id": None}
    if narration is None: raise QuestRewardError("entrega imediata exige narração canônica")
    txid = _txid(mid, "descoberta", [rid])
    if not _tx_exists(repo, txid): tx = _write(repo, mid, "descoberta", [rid], narration, _reward_deltas(repo, mission, r), f"Sidequest {mission['quest_id']} concede recompensa descobrível {rid}.")
    else: tx = {"transacao_id": txid, "writer": {"ja_registrada": True}}
    rs["estado"] = "obtida"; rs["transacao"] = txid; rs["ultima_descoberta"] = {"sucesso": True, "evidencia": proof, "teste": nt}; _history(doc, {"tipo": "recompensa_obtida_descoberta", "reward_id": rid, "transacao": txid}); _atomic(repo / rel, doc)
    return {"ok": True, "resultado": "obtida", "reward_id": rid, "transacao_id": txid, "writer": tx["writer"]}


def apply_success(repo: Path, mission_ref: str, *, optional_ids: Any | None, evidences: Any | None, narration: str) -> dict[str, Any]:
    _, mid, mission = _mission(repo, mission_ref)
    if mission.get("estado") != "concluida": raise QuestRewardError("recompensas de sucesso exigem sidequest concluída")
    doc, rel = _load_contract(repo, mission, mid); c = doc["contrato_recompensa"]; state = doc["estado"]["recompensas"]
    optional = {_slug(x, "opcional") for x in ([] if optional_ids is None else _list(optional_ids, "opcionais"))}; raw_ev = _map(evidences or {}, "evidencias"); ev = {_slug(k, "evidencia.id"): v for k, v in raw_ev.items()}
    eligible = []; p = c["recompensa_principal"]
    if state[p["id"]]["estado"] != "obtida": eligible.append(p)
    ob = {x["id"]: x for x in c["recompensas_opcionais"]}; unknown = optional - set(ob)
    if unknown: raise QuestRewardError("opcionais desconhecidas: " + ", ".join(sorted(unknown)))
    for rid in sorted(optional):
        if state[rid]["estado"] == "obtida": continue
        if rid not in ev: raise QuestRewardError(f"{rid}: opcional exige evidência")
        state[rid]["evidencia_condicao"] = _proof(repo, ev[rid], f"opcional.{rid}"); eligible.append(ob[rid])
    cb = {x["id"]: x for x in c["recompensas_condicionais"]}
    for rid, raw in ev.items():
        if rid in cb and state[rid]["estado"] != "obtida": state[rid]["evidencia_condicao"] = _proof(repo, raw, f"condicional.{rid}"); eligible.append(cb[rid])
    for r in c["recompensas_descobríveis"]:
        if r["descoberta"]["momento_entrega"] == "desfecho" and state[r["id"]]["estado"] == "descoberta": eligible.append(r)
    eligible = list({x["id"]: x for x in eligible}.values()); eligible.sort(key=lambda x: x["id"])
    if not eligible: return {"ok": True, "resultado": "nenhuma_recompensa_nova", "transacao_id": None}
    ids = [x["id"] for x in eligible]; txid = _txid(mid, "sucesso", ids)
    if not _tx_exists(repo, txid):
        deltas = [d for r in eligible for d in _reward_deltas(repo, mission, r)]; tx = _write(repo, mid, "sucesso", ids, narration, deltas, f"Sidequest {mission['quest_id']} concede: {', '.join(ids)}")
    else: tx = {"transacao_id": txid, "writer": {"ja_registrada": True}}
    for r in eligible: state[r["id"]]["estado"] = "obtida"; state[r["id"]]["transacao"] = txid
    _history(doc, {"tipo": "recompensas_sucesso", "ids": ids, "transacao": txid}); _atomic(repo / rel, doc)
    return {"ok": True, "resultado": "recompensas_obtidas", "reward_ids": ids, "transacao_id": txid, "writer": tx["writer"]}


def apply_losses(repo: Path, mission_ref: str, *, evidences: Any, narration: str) -> dict[str, Any]:
    _, mid, mission = _mission(repo, mission_ref)
    if mission.get("estado") not in {"falhada", "expirada"}: raise QuestRewardError("perdas exigem sidequest falhada/expirada")
    doc, rel = _load_contract(repo, mission, mid); losses = _loss_map(doc["contrato_recompensa"]); state = doc["estado"]["perdas"]; raw = _map(evidences, "evidencias_perdas"); ev = {_slug(k, "perda.id"): v for k, v in raw.items()}; selected = []
    for lid, proof_raw in ev.items():
        if lid not in losses: raise QuestRewardError(f"perda não contratada: {lid}")
        if state[lid]["estado"] == "aplicada": continue
        state[lid]["evidencia_causal"] = _proof(repo, proof_raw, f"perda.{lid}"); selected.append(losses[lid])
    if not selected: return {"ok": True, "resultado": "nenhuma_perda_nova", "transacao_id": None}
    ids = sorted(x["id"] for x in selected); txid = _txid(mid, "perdas", ids)
    if not _tx_exists(repo, txid):
        deltas = [d for loss in selected for d in _loss_deltas(repo, loss)]; tx = _write(repo, mid, "perdas", ids, narration, deltas, f"Sidequest {mission['quest_id']} materializa perdas: {', '.join(ids)}")
    else: tx = {"transacao_id": txid, "writer": {"ja_registrada": True}}
    for loss in selected: state[loss["id"]]["estado"] = "aplicada"; state[loss["id"]]["transacao"] = txid
    _history(doc, {"tipo": "perdas_aplicadas", "ids": ids, "transacao": txid}); _atomic(repo / rel, doc)
    return {"ok": True, "resultado": "perdas_aplicadas", "loss_ids": ids, "transacao_id": txid, "writer": tx["writer"]}


def status(repo: Path, mission_ref: str) -> dict[str, Any]:
    _, mid, mission = _mission(repo, mission_ref); doc, rel = _load_contract(repo, mission, mid)
    return {"ok": True, "mission_id": mid, "quest_id": mission["quest_id"], "recompensas": copy.deepcopy(doc["estado"]["recompensas"]), "perdas": copy.deepcopy(doc["estado"]["perdas"]), "fontes_lidas": [oportunidades.INDEX.as_posix(), oportunidades.STATE.as_posix(), rel.as_posix()]}


def check(repo: Path) -> dict[str, Any]:
    errors, missions, contracts, rewards, losses = [], 0, 0, 0, 0
    try:
        index = oportunidades.load_index(repo); state = oportunidades.load_state(repo, index)
        for mid, mission in state.get("missoes", {}).items():
            if not isinstance(mission, dict) or mission.get("origem") != "sidequest_emergente": continue
            missions += 1; doc, _ = _load_contract(repo, mission, mid); contracts += 1; c = doc["contrato_recompensa"]; rm, lm = _rewards(c), _loss_map(c); rewards += len(rm); losses += len(lm)
            if set(doc["estado"]["recompensas"]) != set(rm) or set(doc["estado"]["perdas"]) != set(lm): raise QuestRewardError(f"{mid}: estado Task43 diverge do contrato")
            if len(_bytes(doc)) > MAX_BYTES: raise QuestRewardError(f"{mid}: fragmento Task43 excede orçamento")
    except (QuestRewardError, oportunidades.OpportunityError) as exc: errors.append(str(exc))
    return {"ok": not errors, "erros": errors, "missoes_emergentes": missions, "contratos": contracts, "recompensas": rewards, "perdas": losses, "max_fragment_bytes": MAX_BYTES, "scheduler_novo": 0, "rng_novo": 0, "scans_globais": 0}


def _stdin() -> dict[str, Any]:
    try: return _map(yaml.safe_load(sys.stdin.read()), "stdin")
    except yaml.YAMLError as exc: raise QuestRewardError(str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__); p.add_argument("--repo", type=Path, default=Path.cwd()); sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("registrar-contrato"); r.add_argument("mission_id")
    d = sub.add_parser("descoberta"); d.add_argument("mission_id"); d.add_argument("reward_id"); d.add_argument("resultado", choices=["sucesso", "falha"]); d.add_argument("--narracao")
    s = sub.add_parser("sucesso"); s.add_argument("mission_id"); s.add_argument("--narracao", required=True)
    l = sub.add_parser("perdas"); l.add_argument("mission_id"); l.add_argument("--narracao", required=True)
    st = sub.add_parser("status"); st.add_argument("mission_id"); sub.add_parser("check")
    a = p.parse_args(argv); repo = a.repo.resolve()
    try:
        if a.cmd == "registrar-contrato":
            x = _stdin(); out = register_contract(repo, a.mission_id, package_raw=x.get("pacote_task40"), contract_raw=x.get("contrato_recompensa"))
        elif a.cmd == "descoberta":
            x = _stdin(); out = resolve_discovery(repo, a.mission_id, a.reward_id, success=a.resultado == "sucesso", evidence=x.get("evidencia"), test_result=x.get("teste_resultado"), narration=a.narracao)
        elif a.cmd == "sucesso":
            x = _stdin(); out = apply_success(repo, a.mission_id, optional_ids=x.get("opcionais"), evidences=x.get("evidencias"), narration=a.narracao)
        elif a.cmd == "perdas":
            x = _stdin(); out = apply_losses(repo, a.mission_id, evidences=x.get("evidencias") or {}, narration=a.narracao)
        elif a.cmd == "status": out = status(repo, a.mission_id)
        else: out = check(repo)
        print(yaml.safe_dump(out, allow_unicode=True, sort_keys=False), end=""); return 0 if out.get("ok") else 1
    except (QuestRewardError, transacoes.TransactionError) as exc:
        print(yaml.safe_dump({"ok": False, "erro": str(exc)}, allow_unicode=True, sort_keys=False), end=""); return 2


if __name__ == "__main__": raise SystemExit(main())
