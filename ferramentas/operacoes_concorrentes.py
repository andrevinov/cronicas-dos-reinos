#!/usr/bin/env python3
"""Operações adversariais concorrentes derivadas de reações Task50.

O grupo é preparado antes da escolha de Ren. A fronteira compromete em lote as
operações ainda causais, reserva recursos exclusivos e materializa encontros
imutáveis. Cada frente continua com pendência própria; conhecimento remoto só é
projetado depois de uma entrega por canal declarado.
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

import adversarios
import ameacas
import barreira_mundo
import integridade_adversarial as adversarial
import mundo
import reacoes_sidequest as reactions

SCHEMA = 1
ROOT = reactions.ROOT / "operacoes-concorrentes"
INDEX = ROOT / "index.yaml"
STATE = ROOT / "estado.yaml"
GROUPS = ROOT / "grupos"
ENCOUNTERS = ROOT / "encontros"
JOURNAL = Path("runtime/operacoes-concorrentes-journal.yaml")

MAX_GROUPS = 8
MAX_OPERATIONS = 4
MAX_CHANNELS = 8
MAX_GROUP_BYTES = 48 * 1024
MAX_ENCOUNTER_BYTES = 16 * 1024
MAX_PREP_BYTES = 16 * 1024
MAX_HISTORY = 48
MAX_DELIVERIES = 32
GROUP_STATES = {"planejado", "elegivel", "comprometido", "parcial", "resolvido", "cancelado"}
OPERATION_STATES = {"planejada", "comprometida", "bloqueada", "resolvida", "cancelada"}
CHANNEL_TYPES = {"percepcao_direta", "mensageiro", "sinal_magico", "testemunha"}
MECHANICAL_MODES = {"nenhuma", "combate", "especialidade", "combate_com_especialista"}
ROLES = {"combatente", "especialista", "apoio"}
PERCEPTIBILITY = {"perceptivel", "investigavel"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,127}$")
GROUP_RE = re.compile(r"^gop-[0-9a-f]{20}$")


class ConcurrentOperationError(ValueError):
    pass


def configured(repo: Path) -> bool:
    return (repo / INDEX).is_file() or (repo / STATE).is_file()


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ConcurrentOperationError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ConcurrentOperationError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str, *, minimum: int = 1, maximum: int = 520) -> str:
    if not isinstance(value, str):
        raise ConcurrentOperationError(f"{label} deve ser texto")
    result = " ".join(value.strip().split())
    if not minimum <= len(result) <= maximum:
        raise ConcurrentOperationError(f"{label} deve ter {minimum}..{maximum} caracteres")
    return result


def _id(value: Any, label: str) -> str:
    result = _text(value, label, maximum=128)
    if not ID_RE.fullmatch(result):
        raise ConcurrentOperationError(f"{label} deve ser ID ASCII minúsculo estável")
    return result


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ConcurrentOperationError(f"{label} deve ser inteiro entre {minimum} e {maximum}")
    return value


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sha_bytes(raw: bytes | None) -> str | None:
    return hashlib.sha256(raw).hexdigest() if raw is not None else None


def _yaml(value: Any) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        return _map(yaml.safe_load(path.read_text(encoding="utf-8")), label)
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise ConcurrentOperationError(str(exc)) from exc


def _atomic_text(path: Path, rendered: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _atomic(path: Path, value: dict[str, Any], maximum: int | None = None) -> None:
    rendered = _yaml(value)
    if maximum is not None and len(rendered.encode("utf-8")) > maximum:
        raise ConcurrentOperationError(f"{path.as_posix()} excede {maximum} bytes")
    _atomic_text(path, rendered)


def _empty_index() -> dict[str, Any]:
    return {"schema_operacoes_concorrentes": SCHEMA, "natureza": "reservado", "grupos": {}}


def _empty_state() -> dict[str, Any]:
    return {
        "schema_estado_operacoes_concorrentes": SCHEMA,
        "natureza": "controle_reservado",
        "grupos": {},
        "operacao_para_grupo": {},
        "reservas_exclusivas": {},
        "entregas_informacao": [],
        "historico_recente": [],
    }


def _load_index(repo: Path, allow_missing: bool = False) -> dict[str, Any]:
    if allow_missing and not (repo / INDEX).is_file():
        return _empty_index()
    value = _load(repo / INDEX, INDEX.as_posix())
    if value.get("schema_operacoes_concorrentes") != SCHEMA or value.get("natureza") != "reservado":
        raise ConcurrentOperationError("índice de operações concorrentes inválido")
    _map(value.get("grupos"), "indice.grupos")
    return value


def _load_state(repo: Path, allow_missing: bool = False) -> dict[str, Any]:
    if allow_missing and not (repo / STATE).is_file():
        return _empty_state()
    value = _load(repo / STATE, STATE.as_posix())
    if (
        value.get("schema_estado_operacoes_concorrentes") != SCHEMA
        or value.get("natureza") != "controle_reservado"
    ):
        raise ConcurrentOperationError("estado de operações concorrentes inválido")
    for key in ("grupos", "operacao_para_grupo", "reservas_exclusivas"):
        _map(value.get(key), f"estado.{key}")
    for key in ("entregas_informacao", "historico_recente"):
        _list(value.get(key), f"estado.{key}")
    return value


def _group_rel(group_id: str) -> Path:
    if not GROUP_RE.fullmatch(group_id):
        raise ConcurrentOperationError("grupo_operacoes_id inválido")
    return GROUPS / f"{group_id}.yaml"


def _encounter_rel(operation_id: str) -> Path:
    return ENCOUNTERS / f"{_id(operation_id, 'operation_id')}.yaml"


def _load_group(repo: Path, group_id: str) -> tuple[dict[str, Any], str]:
    index = _load_index(repo)
    meta = _map(index["grupos"].get(group_id), f"indice.{group_id}")
    source = _text(meta.get("arquivo"), f"indice.{group_id}.arquivo", maximum=240)
    if source != _group_rel(group_id).as_posix():
        raise ConcurrentOperationError("índice aponta grupo divergente")
    doc = _load(repo / source, source)
    contract = _map(doc.get("grupo_operacoes"), f"{group_id}.grupo_operacoes")
    if (
        doc.get("schema_grupo_operacoes") != SCHEMA
        or doc.get("natureza") != "reservado"
        or doc.get("grupo_operacoes_id") != group_id
        or doc.get("contrato_digest") != _digest(contract)
    ):
        raise ConcurrentOperationError(f"contrato de grupo divergente: {group_id}")
    return doc, source


def _instant(raw: Any, label: str) -> tuple[dict[str, str], mundo.WorldInstant]:
    value = _map(raw, label)
    if set(value) != {"data", "hora"}:
        raise ConcurrentOperationError(f"{label} exige data e hora")
    parts = {
        "data": _text(value["data"], f"{label}.data", maximum=80),
        "hora": _text(value["hora"], f"{label}.hora", maximum=12),
    }
    try:
        return parts, mundo.parse_instant(parts["data"], parts["hora"])
    except mundo.WorldEngineError as exc:
        raise ConcurrentOperationError(str(exc)) from exc


def _proof(repo: Path, raw: Any, label: str) -> dict[str, str]:
    try:
        return reactions._safe_proof(repo, raw, label)
    except reactions.SidequestReactionError as exc:
        raise ConcurrentOperationError(str(exc)) from exc


def _mechanics(repo: Path, raw: Any, operation_id: str) -> tuple[dict[str, Any], list[str]]:
    value = _map(raw, f"{operation_id}.mecanica")
    expected = {
        "modo", "alvo", "nivel_alvo", "recursos_alvo", "prova_alvo",
        "adversario_referencia", "composicao", "aliados_presentes", "terreno",
        "iniciativa", "surpresa", "objetivo_tatico", "rotas_retirada",
        "capacidade_exclusiva",
    }
    if set(value) != expected:
        raise ConcurrentOperationError(
            f"{operation_id}.mecanica possui campos divergentes: {sorted(set(value) ^ expected)}"
        )
    mode = _text(value["modo"], f"{operation_id}.mecanica.modo", maximum=32)
    if mode not in MECHANICAL_MODES:
        raise ConcurrentOperationError("modo mecânico inválido")
    target = _id(value["alvo"], f"{operation_id}.mecanica.alvo")
    level = _integer(value["nivel_alvo"], f"{operation_id}.nivel_alvo", 1, 20)
    resources = _text(value["recursos_alvo"], f"{operation_id}.recursos_alvo", maximum=16)
    if resources not in {"plenos", "gastos", "criticos"}:
        raise ConcurrentOperationError("recursos_alvo inválido")
    target_proof = _proof(repo, value["prova_alvo"], f"{operation_id}.prova_alvo")
    terrain = _text(value["terreno"], f"{operation_id}.terreno", maximum=16)
    initiative = _text(value["iniciativa"], f"{operation_id}.iniciativa", maximum=16)
    if terrain not in {"grupo", "neutra", "adversario"} or initiative not in {
        "grupo", "neutra", "adversario"
    }:
        raise ConcurrentOperationError("terreno/iniciativa inválidos")
    if not isinstance(value["surpresa"], bool) or not isinstance(value["capacidade_exclusiva"], bool):
        raise ConcurrentOperationError("surpresa e capacidade_exclusiva devem ser bool")

    composition: list[dict[str, Any]] = []
    total_enemies = 0
    sources = [target_proof["fonte"]]
    for position, raw_member in enumerate(_list(value["composicao"], f"{operation_id}.composicao")):
        member = _map(raw_member, f"{operation_id}.composicao[{position}]")
        if set(member) != {"adversario", "quantidade", "papel", "especialidade_id"}:
            raise ConcurrentOperationError("membro mecânico possui estrutura inválida")
        try:
            sheet = adversarios.load_adversary(repo, _text(member["adversario"], "adversario"))
        except adversarios.AdversaryValidationError as exc:
            raise ConcurrentOperationError(str(exc)) from exc
        adversary_id = sheet["adversario_id"]
        quantity = _integer(member["quantidade"], "quantidade", 1, 10)
        role = _text(member["papel"], "papel", maximum=20)
        if role not in ROLES:
            raise ConcurrentOperationError("papel mecânico inválido")
        specialty_raw = member["especialidade_id"]
        specialty = None if specialty_raw is None else _id(specialty_raw, "especialidade_id")
        if role == "especialista" and specialty is None:
            raise ConcurrentOperationError("especialista exige especialidade_id")
        if specialty is not None:
            try:
                detail = adversarios.load_specialty(repo, adversary_id, specialty)
            except adversarios.AdversaryValidationError as exc:
                raise ConcurrentOperationError(str(exc)) from exc
            sources.extend(detail.get("fontes_lidas") or [])
        sources.extend(sheet.get("fontes_lidas") or [])
        total_enemies += quantity
        composition.append(
            {
                "adversario_id": adversary_id,
                "quantidade": quantity,
                "papel": role,
                "especialidade_id": specialty,
            }
        )
    if mode != "nenhuma" and not composition:
        raise ConcurrentOperationError("operação mecânica exige composição")
    if mode == "nenhuma" and composition:
        raise ConcurrentOperationError("mecânica nenhuma não aceita composição")
    composition.sort(
        key=lambda item: (
            item["adversario_id"], item["papel"], item["especialidade_id"] or ""
        )
    )

    allies: list[dict[str, Any]] = []
    for position, raw_ally in enumerate(_list(value["aliados_presentes"], "aliados_presentes")):
        ally = _map(raw_ally, f"aliados_presentes[{position}]")
        if set(ally) != {"id", "prova_presenca", "prova_capacidade", "prova_motivo"}:
            raise ConcurrentOperationError("aliado exige id e três provas causais")
        proofs = {
            key: _proof(repo, ally[key], f"aliado.{key}")
            for key in ("prova_presenca", "prova_capacidade", "prova_motivo")
        }
        sources.extend(proof["fonte"] for proof in proofs.values())
        allies.append({"id": _id(ally["id"], "aliado.id"), **proofs})
    if len({item["id"] for item in allies}) != len(allies):
        raise ConcurrentOperationError("aliado duplicado")
    allies.sort(key=lambda item: item["id"])

    routes: list[dict[str, str]] = []
    for position, raw_route in enumerate(_list(value["rotas_retirada"], "rotas_retirada")):
        route = _map(raw_route, f"rotas_retirada[{position}]")
        if set(route) != {"descricao", "perceptibilidade", "condicao"}:
            raise ConcurrentOperationError("rota de retirada possui estrutura inválida")
        perceptibility = _text(route["perceptibilidade"], "perceptibilidade", maximum=20)
        if perceptibility not in PERCEPTIBILITY:
            raise ConcurrentOperationError("perceptibilidade de rota inválida")
        routes.append(
            {
                "descricao": _text(route["descricao"], "rota.descricao"),
                "perceptibilidade": perceptibility,
                "condicao": _text(route["condicao"], "rota.condicao"),
            }
        )

    reference_raw = value["adversario_referencia"]
    if mode == "nenhuma":
        if reference_raw is not None:
            raise ConcurrentOperationError("mecânica nenhuma não aceita adversário de referência")
        reference_id = None
    else:
        reference = _text(reference_raw, "adversario_referencia")
        try:
            reference_id = adversarios.resolve_adversary(adversarios.load_index(repo), reference)[0]
        except adversarios.AdversaryValidationError as exc:
            raise ConcurrentOperationError(str(exc)) from exc
    if reference_id not in {item["adversario_id"] for item in composition} and mode != "nenhuma":
        raise ConcurrentOperationError("adversário de referência não está na composição")
    threats = None
    if mode != "nenhuma":
        vector = "especialidade" if mode == "especialidade" else "combate"
        try:
            solo = ameacas.evaluate(
                repo, reference_id, vector=vector, level=level, enemies=total_enemies,
                allies=0, resources=resources, terrain=terrain, initiative=initiative,
            )
            with_allies = ameacas.evaluate(
                repo, reference_id, vector=vector, level=level, enemies=total_enemies,
                allies=len(allies), resources=resources, terrain=terrain, initiative=initiative,
            )
        except (ameacas.ThreatValidationError, adversarios.AdversaryValidationError) as exc:
            raise ConcurrentOperationError(str(exc)) from exc
        sources.extend(solo.get("fontes_lidas") or [])
        sources.extend(with_allies.get("fontes_lidas") or [])
        classifications = {
            solo["resultado"]["classificacao"], with_allies["resultado"]["classificacao"]
        }
        if classifications & {"letal", "esmagadora"} and not routes:
            raise ConcurrentOperationError(
                "ameaça letal/esmagadora exige saída plausível perceptível ou investigável"
            )
        threats = {"ren_solo": solo, "com_aliados_presentes": with_allies}
    return {
        "modo": mode,
        "alvo": target,
        "nivel_alvo": level,
        "recursos_alvo": resources,
        "prova_alvo": target_proof,
        "adversario_referencia": reference_id,
        "composicao": composition,
        "aliados_presentes": allies,
        "terreno": terrain,
        "iniciativa": initiative,
        "surpresa": value["surpresa"],
        "objetivo_tatico": _text(value["objetivo_tatico"], "objetivo_tatico"),
        "rotas_retirada": routes,
        "capacidade_exclusiva": value["capacidade_exclusiva"],
        "avaliacoes_ameaca": threats,
    }, list(dict.fromkeys(sources))


def _operation(repo: Path, raw: Any, position: int) -> tuple[dict[str, Any], list[str]]:
    value = _map(raw, f"operacoes[{position}]")
    expected = {
        "id", "reaction_id", "alternative_id", "alvo", "local", "objetivo",
        "celula_id", "atores", "recursos", "dependencias", "bloqueios_causais",
        "sinais_perceptiveis", "mecanica",
    }
    if set(value) != expected:
        raise ConcurrentOperationError(
            f"operação possui campos divergentes: {sorted(set(value) ^ expected)}"
        )
    operation_id = _id(value["id"], f"operacoes[{position}].id")
    reaction_id = _text(value["reaction_id"], f"{operation_id}.reaction_id", maximum=32)
    try:
        reaction, reaction_source = reactions._load_contract(repo, reaction_id)
        reaction_state = reactions._load_state(repo)
    except reactions.SidequestReactionError as exc:
        raise ConcurrentOperationError(str(exc)) from exc
    row = _map(reaction_state["reacoes"].get(reaction_id), f"reacao.{reaction_id}")
    if row.get("estado") not in {"planejada", "elegivel"}:
        raise ConcurrentOperationError(f"reação não está disponível para grupo: {reaction_id}")
    alternative_id = _id(value["alternative_id"], f"{operation_id}.alternative_id")
    alternatives = {
        item["id"]: item for item in reaction["contrato"]["alternativas"]
        if isinstance(item, dict) and item.get("id")
    }
    alternative = alternatives.get(alternative_id)
    if not isinstance(alternative, dict) or alternative.get("estado") != "elegivel":
        raise ConcurrentOperationError(f"alternativa não elegível: {alternative_id}")
    target = _map(value["alvo"], f"{operation_id}.alvo")
    if set(target) != {"id", "tipo"}:
        raise ConcurrentOperationError("alvo de operação exige id e tipo")
    normalized_target = {"id": _id(target["id"], "alvo.id"), "tipo": _text(target["tipo"], "alvo.tipo", maximum=24)}
    if normalized_target not in alternative["alvos"]:
        raise ConcurrentOperationError("alvo da operação não pertence à alternativa Task50")
    actors = sorted(_id(item, f"{operation_id}.atores") for item in _list(value["atores"], "atores"))
    antagonist_id = reaction["contrato"]["antagonista"]["id"]
    if not actors or antagonist_id not in actors or len(actors) != len(set(actors)):
        raise ConcurrentOperationError("atores devem incluir o antagonista sem duplicatas")
    resources = sorted(_text(item, f"{operation_id}.recursos", maximum=240) for item in _list(value["recursos"], "recursos"))
    if set(resources) != set(alternative["recursos_exigidos"]) or len(resources) != len(set(resources)):
        raise ConcurrentOperationError("recursos da operação devem coincidir com a alternativa")
    cell = None if value["celula_id"] is None else _id(value["celula_id"], "celula_id")
    try:
        actor = reactions._agent(repo, antagonist_id)
    except reactions.SidequestReactionError as exc:
        raise ConcurrentOperationError(str(exc)) from exc
    mechanics, mechanical_sources = _mechanics(repo, value["mecanica"], operation_id)
    physical = mechanics["modo"] in {"combate", "combate_com_especialista"} or alternative["exige_presenca_fisica"]
    if physical and (
        actor["presenca"].get("estado") not in {"presente", "presente_oculto", "distribuida", "ancorada"}
        or actor["elegibilidade_local"] != "sim"
    ):
        raise ConcurrentOperationError(f"{operation_id}: ator sem presença física/local compatível")
    if cell is not None and actor.get("tipo") not in {"faccao", "instituicao"}:
        raise ConcurrentOperationError("somente facção/instituição pode dividir células físicas")
    strings = {}
    for key in ("dependencias", "bloqueios_causais", "sinais_perceptiveis"):
        strings[key] = [
            _text(item, f"{operation_id}.{key}", minimum=8)
            for item in _list(value[key], f"{operation_id}.{key}")
        ]
        if len(strings[key]) != len(set(strings[key])):
            raise ConcurrentOperationError(f"{operation_id}.{key} possui duplicatas")
    return {
        "id": operation_id,
        "reaction_id": reaction_id,
        "alternative_id": alternative_id,
        "alvo": normalized_target,
        "local": _id(value["local"], f"{operation_id}.local"),
        "objetivo": _text(value["objetivo"], f"{operation_id}.objetivo"),
        "celula_id": cell,
        "atores": actors,
        "recursos": resources,
        **strings,
        "capacidade_id": alternative["capacidade_id"],
        "exige_presenca_fisica": physical,
        "antagonista_id": antagonist_id,
        "mecanica": mechanics,
    }, [reaction_source, *mechanical_sources, *actor["fontes_lidas"]]


def _channels(repo: Path, raw: Any, operation_ids: set[str]) -> tuple[list[dict[str, Any]], list[str]]:
    result = []
    sources: list[str] = []
    for position, raw_channel in enumerate(_list(raw, "canais")):
        channel = _map(raw_channel, f"canais[{position}]")
        expected = {
            "id", "tipo", "operacao_origem", "destinatario", "atraso_minutos",
            "conhecimentos_permitidos", "prova_disponibilidade",
        }
        if set(channel) != expected:
            raise ConcurrentOperationError("canal possui estrutura inválida")
        channel_id = _id(channel["id"], "canal.id")
        kind = _text(channel["tipo"], "canal.tipo", maximum=24)
        if kind not in CHANNEL_TYPES:
            raise ConcurrentOperationError("tipo de canal inválido")
        origin = _id(channel["operacao_origem"], "canal.operacao_origem")
        if origin not in operation_ids:
            raise ConcurrentOperationError("canal referencia operação inexistente")
        delay = _integer(channel["atraso_minutos"], "canal.atraso_minutos", 0, 7 * 1440)
        if kind == "percepcao_direta" and delay != 0:
            raise ConcurrentOperationError("percepção direta não possui atraso artificial")
        knowledge = [_text(item, "canal.conhecimento", minimum=8) for item in _list(channel["conhecimentos_permitidos"], "conhecimentos_permitidos")]
        if not knowledge or len(knowledge) != len(set(knowledge)):
            raise ConcurrentOperationError("canal exige conhecimentos únicos")
        proof = _proof(repo, channel["prova_disponibilidade"], f"canal {channel_id}")
        sources.append(proof["fonte"])
        result.append(
            {
                "id": channel_id,
                "tipo": kind,
                "operacao_origem": origin,
                "destinatario": _id(channel["destinatario"], "canal.destinatario"),
                "atraso_minutos": delay,
                "conhecimentos_permitidos": knowledge,
                "prova_disponibilidade": proof,
            }
        )
    if len(result) > MAX_CHANNELS or len({item["id"] for item in result}) != len(result):
        raise ConcurrentOperationError("canais excedem orçamento ou possuem IDs duplicados")
    return sorted(result, key=lambda item: item["id"]), sources


def _reservation_keys(operation: dict[str, Any]) -> list[str]:
    actor = operation["antagonista_id"]
    keys = []
    if operation["exige_presenca_fisica"]:
        keys.append(
            f"celula:{actor}:{operation['celula_id']}"
            if operation["celula_id"] else f"ator:{actor}"
        )
    keys.extend(f"recurso:{actor}:{hashlib.sha256(item.encode('utf-8')).hexdigest()[:16]}" for item in operation["recursos"])
    if operation["mecanica"]["capacidade_exclusiva"]:
        keys.append(f"capacidade:{actor}:{operation['capacidade_id']}")
    return sorted(keys)


def _contract(repo: Path, proposal_raw: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    proposal = _map(proposal_raw, "grupo_operacoes")
    expected = {"janela", "simultaneidade", "operacoes", "canais", "motivo"}
    if set(proposal) != expected:
        raise ConcurrentOperationError(f"grupo possui campos divergentes: {sorted(set(proposal) ^ expected)}")
    window = _map(proposal["janela"], "janela")
    if set(window) != {"minimo", "maximo", "condicao"}:
        raise ConcurrentOperationError("janela exige minimo, maximo e condicao")
    minimum_parts, minimum = _instant(window["minimo"], "janela.minimo")
    maximum_parts, maximum = _instant(window["maximo"], "janela.maximo")
    if maximum.minute < minimum.minute:
        raise ConcurrentOperationError("janela máxima antecede a mínima")
    raw_operations = _list(proposal["operacoes"], "operacoes")
    if not 2 <= len(raw_operations) <= MAX_OPERATIONS:
        raise ConcurrentOperationError(f"grupo exige 2..{MAX_OPERATIONS} operações")
    operations = []
    sources: list[str] = []
    for position, raw_operation in enumerate(raw_operations):
        operation, operation_sources = _operation(repo, raw_operation, position)
        operations.append(operation)
        sources.extend(operation_sources)
    operations.sort(key=lambda item: item["id"])
    if len({item["id"] for item in operations}) != len(operations):
        raise ConcurrentOperationError("IDs de operação duplicados")
    if len({item["reaction_id"] for item in operations}) != len(operations):
        raise ConcurrentOperationError("cada operação deve possuir reação Task50 distinta")
    for operation in operations:
        reaction, _ = reactions._load_contract(repo, operation["reaction_id"])
        reaction_window = reaction["contrato"]["janela"]
        _, reaction_min = _instant(reaction_window["minimo"], "reacao.janela.minimo")
        _, reaction_max = _instant(reaction_window["maximo"], "reacao.janela.maximo")
        if minimum.minute < reaction_min.minute or maximum.minute > reaction_max.minute:
            raise ConcurrentOperationError("janela compartilhada deve caber nas janelas das reações")
    reservations: dict[str, str] = {}
    for operation in operations:
        for key in _reservation_keys(operation):
            owner = reservations.get(key)
            if owner is not None and owner != operation["id"]:
                raise ConcurrentOperationError(
                    f"recurso/ator/célula/capacidade exclusiva duplicada: {key}"
                )
            reservations[key] = operation["id"]
    channels, channel_sources = _channels(repo, proposal["canais"], {item["id"] for item in operations})
    core = {
        "janela": {
            "minimo": minimum_parts,
            "maximo": maximum_parts,
            "condicao": _text(window["condicao"], "janela.condicao"),
        },
        "simultaneidade": _text(proposal["simultaneidade"], "simultaneidade", minimum=12),
        "operacoes": operations,
        "ordem_processamento": [item["id"] for item in operations],
        "canais": channels,
        "reservas_planejadas": [
            {"chave": key, "operacao_id": owner} for key, owner in sorted(reservations.items())
        ],
        "motivo": _text(proposal["motivo"], "motivo", minimum=12),
        "guardrails": {
            "compromisso_antes_da_escolha_de_ren": True,
            "escolha_de_ren_nao_cancela_frente_remota": True,
            "conhecimento_remoto_exige_canal_e_atraso": True,
            "ordem_tecnica_nao_define_prioridade_ficcional": True,
            "mecanica_congelada_antes_da_primeira_rolagem": True,
            "sem_scheduler_novo": True,
            "sem_rng": True,
        },
    }
    group_id = "gop-" + _digest(core)[:20]
    contract = {
        "schema_grupo_operacoes": SCHEMA,
        "natureza": "reservado",
        "grupo_operacoes_id": group_id,
        "contrato_digest": _digest(core),
        "grupo_operacoes": core,
    }
    sources = list(dict.fromkeys([reactions.INDEX.as_posix(), reactions.STATE.as_posix(), *sources, *channel_sources]))
    return contract, {"group_id": group_id, "sources": sources}


def _fingerprints(repo: Path, sources: list[str]) -> list[dict[str, Any]]:
    return [
        {"fonte": source, "sha256": _sha_bytes((repo / source).read_bytes()) if (repo / source).is_file() else None}
        for source in sorted(dict.fromkeys(sources))
    ]


def prepare(repo: Path, proposal: Any) -> dict[str, Any]:
    contract, meta = _contract(repo, proposal)
    preparation_id = "gop-prep-" + _digest(
        {"contrato": contract, "fontes": _fingerprints(repo, meta["sources"])}
    )[:24]
    result = {
        "schema_preparacao_grupo_operacoes": SCHEMA,
        "ok": True,
        "read_only": True,
        "grupo_operacoes_id": meta["group_id"],
        "preparacao_id": preparation_id,
        "operacoes": contract["grupo_operacoes"]["ordem_processamento"],
        "mutacoes_aplicadas": False,
        "fontes_lidas": meta["sources"],
    }
    if len(_yaml(result).encode("utf-8")) > MAX_PREP_BYTES:
        raise ConcurrentOperationError("preparação do grupo excede orçamento")
    return result


def _group_pending(contract: dict[str, Any]) -> dict[str, Any]:
    group_id = contract["grupo_operacoes_id"]
    parts, instant = _instant(contract["grupo_operacoes"]["janela"]["minimo"], "janela.minimo")
    agents = sorted({item["antagonista_id"] for item in contract["grupo_operacoes"]["operacoes"]})
    return {
        "id": mundo._pending_id("resolver_grupo_operacoes", f"operacoes_concorrentes.{group_id}", instant),
        "tipo": "resolver_grupo_operacoes",
        "grupo_operacoes_id": group_id,
        "agente": agents[0],
        "agentes_afetados": agents,
        "disparado_em": parts,
        "motivo": "Grupo adversarial simultâneo exige compromisso em lote antes da narração.",
        "origem": f"grupo-operacoes:{group_id}",
    }


def _operation_pending(contract: dict[str, Any], operation: dict[str, Any]) -> dict[str, Any]:
    parts, instant = _instant(contract["grupo_operacoes"]["janela"]["minimo"], "janela.minimo")
    return {
        "id": mundo._pending_id("resolver_operacao_adversarial", f"operacao.{operation['id']}", instant),
        "tipo": "resolver_operacao_adversarial",
        "grupo_operacoes_id": contract["grupo_operacoes_id"],
        "operacao_id": operation["id"],
        "reaction_id": operation["reaction_id"],
        "agente": operation["antagonista_id"],
        "agentes_afetados": operation["atores"],
        "local": operation["local"],
        "disparado_em": parts,
        "motivo": "Operação comprometida continua até resultado factual próprio.",
        "origem": f"operacao-adversarial:{operation['id']}",
    }


def materialize(repo: Path, proposal: Any, preparation_id: str) -> dict[str, Any]:
    prepared = prepare(repo, proposal)
    if prepared["preparacao_id"] != preparation_id:
        raise ConcurrentOperationError("preparação do grupo obsoleta/divergente")
    contract, meta = _contract(repo, proposal)
    group_id = meta["group_id"]
    index = _load_index(repo, allow_missing=True)
    state = _load_state(repo, allow_missing=True)
    if group_id not in index["grupos"] and len(index["grupos"]) >= MAX_GROUPS:
        raise ConcurrentOperationError(f"índice excede {MAX_GROUPS} grupos")
    reactions_state = reactions._load_state(repo)
    member_reactions = [item["reaction_id"] for item in contract["grupo_operacoes"]["operacoes"]]
    for operation in contract["grupo_operacoes"]["operacoes"]:
        owner = state["operacao_para_grupo"].get(operation["id"])
        if owner is not None and owner != group_id:
            raise ConcurrentOperationError(
                f"ID de operação já pertence a outro grupo: {operation['id']}"
            )
    causal_key = _digest(sorted(member_reactions))
    divergent = [
        gid for gid, row in index["grupos"].items()
        if isinstance(row, dict) and row.get("chave_causal") == causal_key and gid != group_id
    ]
    if divergent:
        raise ConcurrentOperationError("as mesmas reações já pertencem a grupo divergente")
    for reaction_id in member_reactions:
        row = _map(reactions_state["reacoes"].get(reaction_id), f"reacao.{reaction_id}")
        owner = row.get("grupo_operacoes_id")
        if owner not in {None, group_id}:
            raise ConcurrentOperationError(f"reação já pertence ao grupo {owner}")
        if row.get("estado") not in {"planejada", "elegivel"}:
            raise ConcurrentOperationError("grupo só reivindica reações ainda não comprometidas")
    rel = _group_rel(group_id)
    rendered = _yaml(contract)
    if (repo / rel).is_file() and (repo / rel).read_text(encoding="utf-8") != rendered:
        raise ConcurrentOperationError("contrato de grupo existente diverge")
    if not (repo / rel).is_file():
        _atomic(repo / rel, contract, MAX_GROUP_BYTES)
    meta_row = {
        "grupo_operacoes_id": group_id,
        "chave_causal": causal_key,
        "arquivo": rel.as_posix(),
        "operacoes": contract["grupo_operacoes"]["ordem_processamento"],
    }
    existing_meta = index["grupos"].get(group_id)
    if existing_meta is not None and existing_meta != meta_row:
        raise ConcurrentOperationError("metadado do grupo diverge")
    created = group_id not in index["grupos"]
    index["grupos"][group_id] = meta_row
    _atomic(repo / INDEX, index)
    pending = _group_pending(contract)
    if group_id not in state["grupos"]:
        state["grupos"][group_id] = {
            "estado": "planejado",
            "pendencia_id": None,
            "operacoes": {
                item["id"]: {
                    "estado": "planejada", "pendencia_id": None,
                    "primeira_rolagem": None, "resolucao": None, "bloqueio": None,
                }
                for item in contract["grupo_operacoes"]["operacoes"]
            },
        }
        for operation in contract["grupo_operacoes"]["operacoes"]:
            state["operacao_para_grupo"][operation["id"]] = group_id
        state["historico_recente"].append({"tipo": "grupo_materializado", "grupo_operacoes_id": group_id})
        state["historico_recente"] = state["historico_recente"][-MAX_HISTORY:]
    _atomic(repo / STATE, state)

    world = mundo.load_world_state(repo)
    old_pending_ids = {
        reactions_state["reacoes"][rid].get("pendencia_id") for rid in member_reactions
    } - {None}
    world["pendencias"] = [item for item in world["pendencias"] if item.get("id") not in old_pending_ids]
    for reaction_id in member_reactions:
        row = reactions_state["reacoes"][reaction_id]
        row["estado"] = "planejada"
        row["pendencia_id"] = None
        row["grupo_operacoes_id"] = group_id
    reactions._atomic(repo / reactions.STATE, reactions_state)
    now, _ = mundo.load_canonical_time(repo)
    _, minimum = _instant(contract["grupo_operacoes"]["janela"]["minimo"], "janela.minimo")
    added = []
    if now.minute >= minimum.minute:
        added = mundo._merge_pending(world, [pending])
        state = _load_state(repo)
        state["grupos"][group_id]["estado"] = "elegivel"
        state["grupos"][group_id]["pendencia_id"] = pending["id"]
        _atomic(repo / STATE, state)
    mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, world)
    barreira_mundo.sync(repo, world)
    return {
        "ok": True,
        "resultado": "materializado" if created else "ja_materializado",
        "grupo_operacoes_id": group_id,
        "estado": _load_state(repo)["grupos"][group_id]["estado"],
        "pendencia": pending if added else None,
        "reacoes_reivindicadas": member_reactions,
    }


def reconcile(repo: Path, now: mundo.WorldInstant | None = None) -> dict[str, Any]:
    if not configured(repo):
        return {"ok": True, "configurado": False, "alterou": False, "novas_pendencias": []}
    index = _load_index(repo)
    state = _load_state(repo)
    current = now or mundo.load_canonical_time(repo)[0]
    world = mundo.load_world_state(repo)
    emitted = []
    changed = False
    for group_id in sorted(index["grupos"]):
        contract, _ = _load_group(repo, group_id)
        row = state["grupos"][group_id]
        _, minimum = _instant(contract["grupo_operacoes"]["janela"]["minimo"], "janela.minimo")
        if row["estado"] == "planejado" and current.minute >= minimum.minute:
            pending = _group_pending(contract)
            row["estado"] = "elegivel"
            row["pendencia_id"] = pending["id"]
            emitted.append(pending)
            changed = True
        elif row["estado"] == "elegivel":
            emitted.append(_group_pending(contract))
    added = mundo._merge_pending(world, emitted)
    if changed:
        _atomic(repo / STATE, state)
    if added:
        mundo._atomic_write_yaml(repo / mundo.WORLD_STATE_PATH, world)
    barreira_mundo.sync(repo, world)
    return {"ok": True, "configurado": True, "alterou": changed or bool(added), "novas_pendencias": added}


def project_group_pending(repo: Path, pending: dict[str, Any]) -> dict[str, Any]:
    group_id = _text(pending.get("grupo_operacoes_id"), "pendencia.grupo_operacoes_id", maximum=32)
    contract, source = _load_group(repo, group_id)
    state = _load_state(repo)
    row = _map(state["grupos"].get(group_id), f"estado.{group_id}")
    if pending.get("id") != row.get("pendencia_id") or row.get("estado") != "elegivel":
        raise ConcurrentOperationError("pendência não corresponde a grupo elegível")
    return {
        "grupo_operacoes_id": group_id,
        "estado": row["estado"],
        "janela": contract["grupo_operacoes"]["janela"],
        "simultaneidade": contract["grupo_operacoes"]["simultaneidade"],
        "operacoes": [
            {
                key: operation[key]
                for key in (
                    "id", "reaction_id", "alvo", "local", "objetivo", "celula_id",
                    "atores", "recursos", "dependencias", "bloqueios_causais",
                    "sinais_perceptiveis", "mecanica",
                )
            }
            for operation in contract["grupo_operacoes"]["operacoes"]
        ],
        "canais": contract["grupo_operacoes"]["canais"],
        "ordem_processamento": contract["grupo_operacoes"]["ordem_processamento"],
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), source],
    }


def _normalized_blockers(repo: Path, raw: Any, operation_ids: set[str]) -> dict[str, dict[str, Any]]:
    if raw is None:
        return {}
    value = _map(raw, "bloqueios")
    result = {}
    for operation_id, raw_blocker in value.items():
        operation_id = _id(operation_id, "bloqueios.operation_id")
        if operation_id not in operation_ids:
            raise ConcurrentOperationError("bloqueio referencia operação inexistente")
        blocker = _map(raw_blocker, f"bloqueio.{operation_id}")
        if set(blocker) != {"motivo", "prova"}:
            raise ConcurrentOperationError("bloqueio exige motivo e prova")
        result[operation_id] = {
            "motivo": _text(blocker["motivo"], "bloqueio.motivo", minimum=12),
            "prova": _proof(repo, blocker["prova"], f"bloqueio.{operation_id}.prova"),
        }
    return result


def _completed(world: dict[str, Any], pending: dict[str, Any], note: str) -> None:
    world["pendencias"] = [item for item in world["pendencias"] if item.get("id") != pending["id"]]
    if pending["id"] not in {item.get("id") for item in world["concluidas_recentes"]}:
        world["concluidas_recentes"].append(
            {"id": pending["id"], "tipo": pending["tipo"], "disparado_em": pending["disparado_em"], "agente": pending.get("agente"), "nota": note}
        )
        world["concluidas_recentes"] = world["concluidas_recentes"][-mundo.MAX_RECENT_COMPLETED:]


def _encounter_doc(group_id: str, operation: dict[str, Any]) -> dict[str, Any]:
    core = {
        "grupo_operacoes_id": group_id,
        "operacao_id": operation["id"],
        "reaction_id": operation["reaction_id"],
        "local": operation["local"],
        "objetivo_tatico": operation["mecanica"]["objetivo_tatico"],
        "mecanica": operation["mecanica"],
        "guardrails": {
            "composicao_imutavel_apos_primeira_rolagem": True,
            "especialista_pode_operar_durante_distracao": True,
            "protected_core_nao_remove_risco_de_combate": True,
            "consequencia_automatica_continua_sob_task44": True,
        },
    }
    return {
        "schema_encontro_operacao": SCHEMA,
        "natureza": "reservado",
        "operacao_id": operation["id"],
        "encontro_digest": _digest(core),
        "encontro": core,
    }


def _stage(path: Path, current: bytes | None, after: dict[str, Any]) -> dict[str, Any]:
    rendered = _yaml(after)
    return {
        "arquivo": path.as_posix(),
        "sha_antes": _sha_bytes(current),
        "sha_depois": _sha_bytes(rendered.encode("utf-8")),
        "conteudo_depois": rendered,
    }


def _install_journal(repo: Path, journal: dict[str, Any], fail_after: int | None = None) -> None:
    installed = 0
    for entry in journal["staged"]:
        path = repo / entry["arquivo"]
        current = path.read_bytes() if path.is_file() else None
        current_sha = _sha_bytes(current)
        if current_sha == entry["sha_depois"]:
            continue
        if current_sha != entry["sha_antes"]:
            raise ConcurrentOperationError(f"recovery encontrou mudança concorrente em {entry['arquivo']}")
        _atomic_text(path, entry["conteudo_depois"])
        installed += 1
        if fail_after is not None and installed >= fail_after:
            raise ConcurrentOperationError("falha simulada durante materialização do grupo")


def _recover_open(repo: Path, group_id: str, fail_after: int | None = None) -> dict[str, Any] | None:
    path = repo / JOURNAL
    if not path.is_file():
        return None
    journal = _load(path, JOURNAL.as_posix())
    if journal.get("grupo_operacoes_id") != group_id:
        raise ConcurrentOperationError(
            f"journal aberto pertence a {journal.get('grupo_operacoes_id')}; recupere-o primeiro"
        )
    _install_journal(repo, journal, fail_after)
    barreira_mundo.sync(repo)
    path.unlink()
    return journal["resultado"]


def commit_group(
    repo: Path,
    group_id: str,
    blockers: Any = None,
    *,
    fail_after: int | None = None,
) -> dict[str, Any]:
    recovered = _recover_open(repo, group_id, fail_after)
    if recovered is not None:
        return {**recovered, "resultado": "recuperado"}
    contract, source = _load_group(repo, group_id)
    state = _load_state(repo)
    group_row = _map(state["grupos"].get(group_id), f"estado.{group_id}")
    if group_row["estado"] in {"comprometido", "parcial", "resolvido"}:
        return {"ok": True, "resultado": "ja_comprometido", "grupo_operacoes_id": group_id}
    if group_row["estado"] != "elegivel":
        raise ConcurrentOperationError("somente grupo elegível pode ser comprometido")
    operations = contract["grupo_operacoes"]["operacoes"]
    blocked = _normalized_blockers(repo, blockers, {item["id"] for item in operations})
    reactions_state = reactions._load_state(repo)
    planned_reservations: dict[str, str] = {}
    for operation in operations:
        if operation["id"] in blocked:
            continue
        reaction_id = operation["reaction_id"]
        reaction, _ = reactions._load_contract(repo, reaction_id)
        reaction_row = reactions_state["reacoes"][reaction_id]
        if reaction_row.get("grupo_operacoes_id") != group_id or reaction_row["estado"] != "planejada":
            raise ConcurrentOperationError("reação deixou de estar reservada ao grupo")
        task44 = reaction["contrato"]["origem_task44"]
        if reactions._sha(repo / task44["arquivo"]) != task44["sha256"]:
            raise ConcurrentOperationError("contrato Task44 original mudou")
        actor = reactions._agent(repo, operation["antagonista_id"])
        option = next(
            item for item in reaction["contrato"]["alternativas"]
            if item["id"] == operation["alternative_id"]
        )
        if operation["capacidade_id"] not in actor["capacidades"]:
            raise ConcurrentOperationError(f"capacidade indisponível em {operation['id']}")
        if set(option["conhecimentos_requeridos"]) - set(actor["conhecimento"]):
            raise ConcurrentOperationError(f"conhecimento deixou de existir em {operation['id']}")
        if operation["exige_presenca_fisica"] and (
            actor["presenca"].get("estado") not in {"presente", "presente_oculto", "distribuida", "ancorada"}
            or actor["elegibilidade_local"] != "sim"
        ):
            raise ConcurrentOperationError(f"presença incompatível em {operation['id']}")
        consequence = {
            "titulo": option["titulo"],
            "descricao": option["resultado_possivel"],
            "gravidade": option["gravidade"],
            "reversibilidade": option["reversibilidade"],
            "classe_impacto": option["classe_impacto"],
            "alvos_npc": [
                target["id"] for target in option["alvos"] if target["tipo"] == "npc"
            ],
        }
        try:
            adversarial.authorize_external_consequence(
                repo, consequence, authority="procedural"
            )
        except adversarial.AdversarialIntegrityError as exc:
            raise ConcurrentOperationError(str(exc)) from exc
        for key in _reservation_keys(operation):
            if key in planned_reservations and planned_reservations[key] != operation["id"]:
                raise ConcurrentOperationError(f"reserva exclusiva duplicada: {key}")
            existing = state["reservas_exclusivas"].get(key)
            if existing is not None and existing.get("grupo_operacoes_id") != group_id:
                raise ConcurrentOperationError(f"reserva já comprometida: {key}")
            planned_reservations[key] = operation["id"]
        for resource in operation["recursos"]:
            if resource not in actor["recursos"]:
                raise ConcurrentOperationError(f"recurso indisponível: {resource}")
            task50_key = reactions._resource_key(actor["id"], resource)
            existing = reactions_state["recursos_comprometidos"].get(task50_key)
            if existing is not None and existing.get("reaction_id") != reaction_id:
                raise ConcurrentOperationError(f"recurso Task50 já comprometido: {resource}")

    next_reactions = copy.deepcopy(reactions_state)
    next_state = copy.deepcopy(state)
    next_world = copy.deepcopy(mundo.load_world_state(repo))
    group_pending = _group_pending(contract)
    if group_pending["id"] != group_row.get("pendencia_id"):
        raise ConcurrentOperationError("pendência do grupo divergiu")
    committed_ids = []
    encounter_docs: list[tuple[Path, dict[str, Any]]] = []
    operation_pendings = []
    for operation in operations:
        op_id = operation["id"]
        op_row = next_state["grupos"][group_id]["operacoes"][op_id]
        reaction_row = next_reactions["reacoes"][operation["reaction_id"]]
        if op_id in blocked:
            op_row["estado"] = "bloqueada"
            op_row["bloqueio"] = blocked[op_id]
            reaction_row["estado"] = "cancelada"
            reaction_row["resolucao"] = {"tipo": "bloqueio_causal", **blocked[op_id]}
            continue
        pending = _operation_pending(contract, operation)
        operation_pendings.append(pending)
        op_row["estado"] = "comprometida"
        op_row["pendencia_id"] = pending["id"]
        reaction_row["estado"] = "comprometida"
        reaction_row["pendencia_id"] = pending["id"]
        reaction_row["alternativas_comprometidas"] = [operation["alternative_id"]]
        reaction_row["comprometida_em"] = contract["grupo_operacoes"]["janela"]["minimo"]
        for resource in operation["recursos"]:
            key = reactions._resource_key(operation["antagonista_id"], resource)
            next_reactions["recursos_comprometidos"][key] = {
                "reaction_id": operation["reaction_id"],
                "alternative_id": operation["alternative_id"],
                "antagonista_id": operation["antagonista_id"],
                "recurso": resource,
                "grupo_operacoes_id": group_id,
                "operacao_id": op_id,
            }
        for key in _reservation_keys(operation):
            next_state["reservas_exclusivas"][key] = {
                "grupo_operacoes_id": group_id, "operacao_id": op_id
            }
        encounter_docs.append((_encounter_rel(op_id), _encounter_doc(group_id, operation)))
        committed_ids.append(op_id)
    next_state["grupos"][group_id]["estado"] = (
        "parcial" if blocked and committed_ids else "comprometido" if committed_ids else "resolvido"
    )
    next_state["grupos"][group_id]["pendencia_id"] = None
    next_state["historico_recente"].append(
        {"tipo": "grupo_comprometido", "grupo_operacoes_id": group_id, "operacoes": committed_ids, "bloqueadas": sorted(blocked)}
    )
    next_state["historico_recente"] = next_state["historico_recente"][-MAX_HISTORY:]
    _completed(next_world, group_pending, "operações válidas comprometidas em lote")
    mundo._merge_pending(next_world, operation_pendings)
    result = {
        "ok": True,
        "resultado": "comprometido_em_lote",
        "grupo_operacoes_id": group_id,
        "operacoes_comprometidas": committed_ids,
        "operacoes_bloqueadas": sorted(blocked),
        "encontros_materializados": [path.as_posix() for path, _ in encounter_docs],
        "regra": "compromisso e composição antecedem escolha de Ren, narração e rolagem",
        "fontes_lidas": [source],
    }
    staged = [
        _stage(reactions.STATE, (repo / reactions.STATE).read_bytes(), next_reactions),
        _stage(STATE, (repo / STATE).read_bytes(), next_state),
        *[
            _stage(path, (repo / path).read_bytes() if (repo / path).is_file() else None, doc)
            for path, doc in encounter_docs
        ],
        _stage(mundo.WORLD_STATE_PATH, (repo / mundo.WORLD_STATE_PATH).read_bytes(), next_world),
    ]
    journal = {
        "schema_journal_operacoes_concorrentes": SCHEMA,
        "natureza": "journal_recuperacao",
        "grupo_operacoes_id": group_id,
        "staged": staged,
        "resultado": result,
    }
    _atomic(repo / JOURNAL, journal)
    _install_journal(repo, journal, fail_after)
    barreira_mundo.sync(repo)
    (repo / JOURNAL).unlink()
    return result


def _operation_context(repo: Path, operation_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str]:
    state = _load_state(repo)
    group_id = _text(state["operacao_para_grupo"].get(operation_id), "grupo da operação", maximum=32)
    contract, source = _load_group(repo, group_id)
    operation = next(
        (item for item in contract["grupo_operacoes"]["operacoes"] if item["id"] == operation_id),
        None,
    )
    if not isinstance(operation, dict):
        raise ConcurrentOperationError("operação não existe no contrato do grupo")
    row = state["grupos"][group_id]["operacoes"][operation_id]
    return contract, operation, row, source


def project_operation_pending(repo: Path, pending: dict[str, Any]) -> dict[str, Any]:
    operation_id = _id(pending.get("operacao_id"), "pendencia.operacao_id")
    contract, operation, row, source = _operation_context(repo, operation_id)
    if row.get("pendencia_id") != pending.get("id") or row.get("estado") != "comprometida":
        raise ConcurrentOperationError("pendência não corresponde a operação comprometida")
    encounter_source = _encounter_rel(operation_id).as_posix()
    encounter = _load(repo / encounter_source, encounter_source)
    if (
        encounter.get("schema_encontro_operacao") != SCHEMA
        or encounter.get("natureza") != "reservado"
        or encounter.get("operacao_id") != operation_id
        or encounter.get("encontro_digest") != _digest(encounter.get("encontro"))
    ):
        raise ConcurrentOperationError("encontro congelado divergente")
    return {
        "grupo_operacoes_id": contract["grupo_operacoes_id"],
        "operacao_id": operation_id,
        "estado": row["estado"],
        "local": operation["local"],
        "alvo": operation["alvo"],
        "objetivo": operation["objetivo"],
        "bloqueios_causais": operation["bloqueios_causais"],
        "sinais_perceptiveis": operation["sinais_perceptiveis"],
        "encontro": encounter["encontro"],
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), source, encounter_source],
    }


def register_roll(repo: Path, operation_id: str, roll_id: str) -> dict[str, Any]:
    contract, _, row, _ = _operation_context(repo, operation_id)
    if row["estado"] != "comprometida":
        raise ConcurrentOperationError("rolagem exige operação comprometida")
    encounter_path = repo / _encounter_rel(operation_id)
    encounter = _load(encounter_path, encounter_path.as_posix())
    if (
        encounter.get("schema_encontro_operacao") != SCHEMA
        or encounter.get("natureza") != "reservado"
        or encounter.get("operacao_id") != operation_id
        or encounter.get("encontro_digest") != _digest(encounter.get("encontro"))
    ):
        raise ConcurrentOperationError("encontro congelado divergente antes da rolagem")
    encounter_sha = _sha_bytes(encounter_path.read_bytes())
    roll = _id(roll_id, "roll_id")
    state = _load_state(repo)
    mutable = state["grupos"][contract["grupo_operacoes_id"]]["operacoes"][operation_id]
    existing = mutable.get("primeira_rolagem")
    expected = {"roll_id": roll, "encontro_sha256": encounter_sha}
    if existing is not None:
        if existing != expected:
            raise ConcurrentOperationError("primeira rolagem já congelou outro encontro/ID")
        return {"ok": True, "resultado": "ja_registrada", "operacao_id": operation_id, **expected}
    mutable["primeira_rolagem"] = expected
    _atomic(repo / STATE, state)
    return {"ok": True, "resultado": "registrada", "operacao_id": operation_id, **expected}


def resolve_operation(repo: Path, operation_id: str, proof: Any, result: str) -> dict[str, Any]:
    contract, operation, row, _ = _operation_context(repo, operation_id)
    normalized_result = _text(result, "resultado", minimum=12)
    causal = _proof(repo, proof, "prova_resultado")
    if row["estado"] == "resolvida":
        if row["resolucao"] != {"resultado": normalized_result, "prova": causal}:
            raise ConcurrentOperationError("operação já resolvida com resultado divergente")
        return {"ok": True, "resultado": "ja_resolvida", "operacao_id": operation_id}
    if row["estado"] != "comprometida":
        raise ConcurrentOperationError("resultado exige operação comprometida")
    try:
        reactions.resolve(
            repo, operation["reaction_id"], proof=causal, result=normalized_result
        )
    except reactions.SidequestReactionError as exc:
        raise ConcurrentOperationError(str(exc)) from exc
    state = _load_state(repo)
    group_id = contract["grupo_operacoes_id"]
    mutable = state["grupos"][group_id]["operacoes"][operation_id]
    mutable["estado"] = "resolvida"
    mutable["resolucao"] = {"resultado": normalized_result, "prova": causal}
    for key, reservation in list(state["reservas_exclusivas"].items()):
        if reservation.get("operacao_id") == operation_id:
            del state["reservas_exclusivas"][key]
    if all(
        item["estado"] in {"resolvida", "bloqueada", "cancelada"}
        for item in state["grupos"][group_id]["operacoes"].values()
    ):
        state["grupos"][group_id]["estado"] = "resolvido"
    state["historico_recente"].append(
        {"tipo": "operacao_resolvida", "grupo_operacoes_id": group_id, "operacao_id": operation_id}
    )
    state["historico_recente"] = state["historico_recente"][-MAX_HISTORY:]
    _atomic(repo / STATE, state)
    return {"ok": True, "resultado": "resolvida", "operacao_id": operation_id, "grupo_operacoes_id": group_id}


def deliver_information(
    repo: Path,
    operation_id: str,
    channel_id: str,
    facts: list[str],
    proof: Any,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    contract, operation, row, _ = _operation_context(repo, operation_id)
    if row["estado"] not in {"comprometida", "resolvida"}:
        raise ConcurrentOperationError("informação exige operação materializada")
    channel = next(
        (item for item in contract["grupo_operacoes"]["canais"] if item["id"] == channel_id and item["operacao_origem"] == operation_id),
        None,
    )
    if not isinstance(channel, dict) or channel["tipo"] == "percepcao_direta":
        raise ConcurrentOperationError("entrega remota exige canal indireto declarado")
    current = now or mundo.load_canonical_time(repo)[0]
    _, start = _instant(contract["grupo_operacoes"]["janela"]["minimo"], "janela.minimo")
    available = mundo.WorldInstant(start.minute + channel["atraso_minutos"])
    if current.minute < available.minute:
        raise ConcurrentOperationError("canal ainda não cumpriu seu atraso mínimo")
    normalized = [_text(item, "fato entregue", minimum=8) for item in facts]
    if not normalized or len(normalized) != len(set(normalized)):
        raise ConcurrentOperationError("entrega exige fatos únicos")
    if set(normalized) - set(channel["conhecimentos_permitidos"]):
        raise ConcurrentOperationError("canal tenta entregar conhecimento além de seu escopo")
    causal = _proof(repo, proof, "prova_entrega")
    delivery_id = "inf-" + _digest(
        {"grupo": contract["grupo_operacoes_id"], "operacao": operation_id, "canal": channel_id, "fatos": normalized, "prova": causal}
    )[:20]
    state = _load_state(repo)
    existing = next((item for item in state["entregas_informacao"] if item["id"] == delivery_id), None)
    if existing is None:
        state["entregas_informacao"].append(
            {
                "id": delivery_id,
                "grupo_operacoes_id": contract["grupo_operacoes_id"],
                "operacao_id": operation_id,
                "canal_id": channel_id,
                "destinatario": channel["destinatario"],
                "entregue_em": mundo.instant_parts(current),
                "fatos": normalized,
                "prova": causal,
            }
        )
        state["entregas_informacao"] = state["entregas_informacao"][-MAX_DELIVERIES:]
        _atomic(repo / STATE, state)
    return {"ok": True, "resultado": "ja_entregue" if existing else "entregue", "entrega_id": delivery_id, "fatos": normalized}


def project_for_ren(
    repo: Path,
    group_id: str,
    *,
    local: str | None,
    now: mundo.WorldInstant | None = None,
) -> dict[str, Any]:
    contract, source = _load_group(repo, group_id)
    state = _load_state(repo)
    current = now or mundo.load_canonical_time(repo)[0]
    local_id = None if local is None else _id(local, "local")
    direct = [
        {"operacao_id": item["id"], "local": item["local"], "sinais": item["sinais_perceptiveis"]}
        for item in contract["grupo_operacoes"]["operacoes"]
        if local_id is not None
        and item["local"] == local_id
        and state["grupos"][group_id]["operacoes"][item["id"]]["estado"] in {"comprometida", "resolvida"}
    ]
    delivered = []
    for item in state["entregas_informacao"]:
        if item.get("grupo_operacoes_id") != group_id or item.get("destinatario") != "ren":
            continue
        _, delivered_at = _instant(item["entregue_em"], "entrega.entregue_em")
        if delivered_at.minute <= current.minute:
            delivered.append(
                {key: item[key] for key in ("id", "operacao_id", "canal_id", "entregue_em", "fatos")}
            )
    return {
        "ok": True,
        "grupo_operacoes_id": group_id,
        "percepcao_direta": direct,
        "informacao_remota_entregue": sorted(delivered, key=lambda item: item["id"]),
        "operacoes_remotas_ocultas": len(contract["grupo_operacoes"]["operacoes"]) - len(direct),
        "regra": "presença em uma frente não concede conhecimento instantâneo das demais",
        "fontes_lidas": [INDEX.as_posix(), STATE.as_posix(), source],
    }


def check(repo: Path) -> dict[str, Any]:
    errors = []
    count = 0
    if (repo / JOURNAL).is_file():
        errors.append("journal de operações concorrentes interrompido")
    if configured(repo):
        try:
            if not (repo / INDEX).is_file() or not (repo / STATE).is_file():
                raise ConcurrentOperationError("índice e estado devem existir juntos")
            index = _load_index(repo)
            state = _load_state(repo)
            if set(index["grupos"]) != set(state["grupos"]):
                raise ConcurrentOperationError("índice e estado possuem grupos divergentes")
            world = mundo.load_world_state(repo)
            pending_ids = {item.get("id") for item in world["pendencias"]}
            seen_operations: set[str] = set()
            for group_id in sorted(index["grupos"]):
                contract, source = _load_group(repo, group_id)
                if len((repo / source).read_bytes()) > MAX_GROUP_BYTES:
                    raise ConcurrentOperationError("grupo excede orçamento")
                group_row = state["grupos"][group_id]
                if group_row["estado"] not in GROUP_STATES:
                    raise ConcurrentOperationError("estado de grupo inválido")
                if group_row["estado"] == "elegivel" and group_row.get("pendencia_id") not in pending_ids:
                    raise ConcurrentOperationError("grupo elegível sem pendência")
                operation_ids = {
                    operation["id"] for operation in contract["grupo_operacoes"]["operacoes"]
                }
                if set(group_row["operacoes"]) != operation_ids:
                    raise ConcurrentOperationError("estado e contrato possuem operações divergentes")
                for operation in contract["grupo_operacoes"]["operacoes"]:
                    if operation["id"] in seen_operations:
                        raise ConcurrentOperationError("ID de operação aparece em mais de um grupo")
                    seen_operations.add(operation["id"])
                    if state["operacao_para_grupo"].get(operation["id"]) != group_id:
                        raise ConcurrentOperationError("roteador de operação aponta grupo divergente")
                    op_row = group_row["operacoes"][operation["id"]]
                    if op_row["estado"] not in OPERATION_STATES:
                        raise ConcurrentOperationError("estado de operação inválido")
                    if op_row["estado"] == "comprometida":
                        if op_row.get("pendencia_id") not in pending_ids:
                            raise ConcurrentOperationError("operação comprometida sem pendência")
                        encounter = repo / _encounter_rel(operation["id"])
                        if not encounter.is_file() or encounter.stat().st_size > MAX_ENCOUNTER_BYTES:
                            raise ConcurrentOperationError("encontro ausente ou acima do orçamento")
                        frozen = _load(encounter, encounter.as_posix())
                        if frozen.get("encontro_digest") != _digest(frozen.get("encontro")):
                            raise ConcurrentOperationError("encontro comprometido foi alterado")
                        first_roll = op_row.get("primeira_rolagem")
                        if first_roll is not None and first_roll.get("encontro_sha256") != _sha_bytes(encounter.read_bytes()):
                            raise ConcurrentOperationError("encontro mudou depois da primeira rolagem")
            for key, reservation in state["reservas_exclusivas"].items():
                group = state["grupos"].get(reservation.get("grupo_operacoes_id"))
                operation = group.get("operacoes", {}).get(reservation.get("operacao_id")) if isinstance(group, dict) else None
                if not isinstance(operation, dict) or operation.get("estado") != "comprometida":
                    raise ConcurrentOperationError(f"reserva exclusiva órfã: {key}")
            count = len(index["grupos"])
        except (ConcurrentOperationError, mundo.WorldEngineError, OSError, yaml.YAMLError) as exc:
            errors.append(str(exc))
    return {
        "ok": not errors,
        "configurado": configured(repo),
        "erros": errors,
        "grupos": count,
        "contrato": {
            "max_grupos": MAX_GROUPS,
            "max_operacoes": MAX_OPERATIONS,
            "max_canais": MAX_CHANNELS,
            "grupo_bytes_max": MAX_GROUP_BYTES,
            "encontro_bytes_max": MAX_ENCOUNTER_BYTES,
            "scheduler_novo": 0,
            "rng_novo": 0,
            "scan_global": 0,
        },
    }


def _stdin() -> Any:
    try:
        return yaml.safe_load(sys.stdin.read())
    except yaml.YAMLError as exc:
        raise ConcurrentOperationError(str(exc)) from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("preparar")
    material = sub.add_parser("materializar")
    material.add_argument("--preparacao-id", required=True)
    commit = sub.add_parser("comprometer")
    commit.add_argument("grupo_operacoes_id")
    roll = sub.add_parser("registrar-rolagem")
    roll.add_argument("operacao_id")
    roll.add_argument("roll_id")
    resolve = sub.add_parser("resolver")
    resolve.add_argument("operacao_id")
    resolve.add_argument("--resultado", required=True)
    deliver = sub.add_parser("entregar-informacao")
    deliver.add_argument("operacao_id")
    deliver.add_argument("canal_id")
    deliver.add_argument("fatos", nargs="+")
    show = sub.add_parser("percepcao-ren")
    show.add_argument("grupo_operacoes_id")
    show.add_argument("--local")
    sub.add_parser("reconciliar")
    sub.add_parser("check")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "preparar":
            result = prepare(repo, _stdin())
        elif args.cmd == "materializar":
            result = materialize(repo, _stdin(), args.preparacao_id)
        elif args.cmd == "comprometer":
            result = commit_group(repo, args.grupo_operacoes_id, _stdin())
        elif args.cmd == "registrar-rolagem":
            result = register_roll(repo, args.operacao_id, args.roll_id)
        elif args.cmd == "resolver":
            result = resolve_operation(repo, args.operacao_id, _stdin(), args.resultado)
        elif args.cmd == "entregar-informacao":
            result = deliver_information(repo, args.operacao_id, args.canal_id, args.fatos, _stdin())
        elif args.cmd == "percepcao-ren":
            result = project_for_ren(repo, args.grupo_operacoes_id, local=args.local)
        elif args.cmd == "reconciliar":
            result = reconcile(repo)
        else:
            result = check(repo)
        print(_yaml(result), end="")
        return 0 if result.get("ok", True) else 1
    except (ConcurrentOperationError, reactions.SidequestReactionError, mundo.WorldEngineError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
