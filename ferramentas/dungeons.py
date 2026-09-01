#!/usr/bin/env python3
"""Consulta e valida dungeons preparadas sem materializá-las como cânone.

O hot path comum não usa este módulo. ``mostrar`` abre somente o manifesto;
``nivel`` acrescenta exatamente um fragmento e devolve referências mecânicas
opacas, que continuam pertencendo a ``adversarios.py`` e ``ameacas.py``.
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import yaml

try:
    import adversarios
    import ameacas
    import locais
    import recompensas
except ModuleNotFoundError:
    from ferramentas import adversarios, ameacas, locais, recompensas


CONTRACT_PATH = Path("narrador/dungeons/contrato.yaml")
INDEX_PATH = Path("narrador/dungeons/index.yaml")
DUNGEONS_DIR = Path("narrador/dungeons")
PLANNED_REWARDS_PATH = Path("narrador/recompensas/planejadas.yaml")
SCHEMA = 1
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,95}$")
DICE_RE = re.compile(r"^[1-9][0-9]*d[1-9][0-9]*(?:[+-][0-9]+)?$")


class DungeonValidationError(ValueError):
    """Preparação de dungeon inválida ou consulta ambígua."""


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DungeonValidationError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise DungeonValidationError(f"YAML inválido em {path}: {exc}") from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DungeonValidationError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise DungeonValidationError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DungeonValidationError(f"{label} deve ser texto não vazio")
    return " ".join(value.strip().split())


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise DungeonValidationError(f"{label} deve ser inteiro entre {minimum} e {maximum}")
    return value


def _id(value: Any, label: str) -> str:
    value = _text(value, label)
    if not ID_RE.fullmatch(value):
        raise DungeonValidationError(f"{label} deve ser slug ASCII minúsculo")
    return value


def _strings(value: Any, label: str, *, minimum: int = 1, maximum: int = 16) -> list[str]:
    raw = _list(value, label)
    if not minimum <= len(raw) <= maximum:
        raise DungeonValidationError(f"{label} deve ter entre {minimum} e {maximum} itens")
    result = [_text(item, f"{label}[{index}]") for index, item in enumerate(raw)]
    if len(result) != len(set(result)):
        raise DungeonValidationError(f"{label} não aceita duplicatas")
    return result


def _ids(value: Any, label: str, *, minimum: int = 1, maximum: int = 16) -> list[str]:
    raw = _list(value, label)
    if not minimum <= len(raw) <= maximum:
        raise DungeonValidationError(f"{label} deve ter entre {minimum} e {maximum} itens")
    result = [_id(item, f"{label}[{index}]") for index, item in enumerate(raw)]
    if len(result) != len(set(result)):
        raise DungeonValidationError(f"{label} não aceita duplicatas")
    return result


def _dump(value: Any) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def _repo_path(repo: Path, raw: Any, label: str, prefix: Path | None = None) -> tuple[str, Path]:
    text = _text(raw, label)
    rel = Path(text)
    if rel.is_absolute() or ".." in rel.parts:
        raise DungeonValidationError(f"{label} aponta para fora do repositório")
    if prefix is not None:
        try:
            rel.relative_to(prefix)
        except ValueError as exc:
            raise DungeonValidationError(f"{label} deve ficar sob {prefix.as_posix()}") from exc
    return rel.as_posix(), repo / rel


def load_contract(repo: Path) -> dict[str, Any]:
    path = repo / CONTRACT_PATH
    data = _map(_load_yaml(path), CONTRACT_PATH.as_posix())
    expected = {
        "schema_contrato_dungeons", "natureza", "ruleset", "orcamento",
        "estatutos", "tipos_area", "tipos_resolucao_perigo",
        "classificacoes_ameaca", "invariantes",
    }
    if set(data) != expected:
        raise DungeonValidationError("contrato de dungeons possui estrutura inesperada")
    if data["schema_contrato_dungeons"] != SCHEMA:
        raise DungeonValidationError("schema_contrato_dungeons deve ser 1")
    if data["natureza"] != "contrato_preparacao_dungeon_reservado":
        raise DungeonValidationError("natureza do contrato de dungeons inválida")
    if data["ruleset"] != adversarios.load_campaign_ruleset(repo):
        raise DungeonValidationError("ruleset do contrato de dungeons diverge da campanha")

    budget = _map(data["orcamento"], "orcamento")
    expected_budget = {
        "indice_max_bytes", "manifesto_max_bytes", "nivel_max_bytes", "consulta_max_bytes",
        "max_niveis", "max_areas_por_nivel", "max_encontros_por_nivel", "max_perigos_por_nivel",
    }
    if set(budget) != expected_budget:
        raise DungeonValidationError("orçamento de dungeons possui estrutura inesperada")
    for key in ("indice_max_bytes", "manifesto_max_bytes", "nivel_max_bytes", "consulta_max_bytes"):
        _integer(budget[key], f"orcamento.{key}", 1024, 32768)
    if budget["consulta_max_bytes"] != 8192:
        raise DungeonValidationError("consulta de dungeon deve respeitar o teto L2 de 8 KiB")
    for key in ("max_niveis", "max_areas_por_nivel", "max_encontros_por_nivel", "max_perigos_por_nivel"):
        _integer(budget[key], f"orcamento.{key}", 1, 16)

    if _strings(data["estatutos"], "estatutos") != ["preparada_nao_materializada"]:
        raise DungeonValidationError("estatutos de dungeon foram alterados")
    _strings(data["tipos_area"], "tipos_area")
    if set(_strings(data["tipos_resolucao_perigo"], "tipos_resolucao_perigo")) != {"teste", "salvaguarda"}:
        raise DungeonValidationError("tipos de resolução de perigo inválidos")
    if _strings(data["classificacoes_ameaca"], "classificacoes_ameaca") != [
        "baixa", "moderada", "alta", "letal", "esmagadora"
    ]:
        raise DungeonValidationError("classificações de ameaça divergentes")
    invariants = _map(data["invariantes"], "invariantes")
    required = {
        "registro_nao_materializa_dungeon", "layout_preparado_nao_estabelece_descoberta",
        "presenca_planejada_e_candidata_ate_cena", "numeros_e_geografia_anteriores_a_rolagem",
        "dificuldade_nao_muda_pos_rolagem", "todo_perigo_tem_sinalizacao_e_contrajogo",
        "todo_encontro_tem_objetivo_e_retirada", "todo_nivel_tem_recuo_observavel",
        "recompensa_exige_descoberta_e_obtencao", "recompensa_nunca_e_automatica",
        "progresso_usa_writer_canonico_existente", "sem_estado_scheduler_ou_rng_proprio",
        "consulta_dirigida_nao_abre_outros_niveis", "turno_comum_nao_consulta_dungeon",
    }
    if set(invariants) != required or not all(value is True for value in invariants.values()):
        raise DungeonValidationError("invariantes de dungeon devem permanecer verdadeiras")
    return data


def load_index(repo: Path, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = contract or load_contract(repo)
    path = repo / INDEX_PATH
    if path.stat().st_size > contract["orcamento"]["indice_max_bytes"]:
        raise DungeonValidationError("índice de dungeons excede o orçamento")
    data = _map(_load_yaml(path), INDEX_PATH.as_posix())
    if set(data) != {"schema_indice_dungeons", "natureza", "contrato", "dungeons"}:
        raise DungeonValidationError("índice de dungeons possui estrutura inesperada")
    if data["schema_indice_dungeons"] != SCHEMA or data["natureza"] != "reservado":
        raise DungeonValidationError("metadados do índice de dungeons inválidos")
    if data["contrato"] != CONTRACT_PATH.as_posix():
        raise DungeonValidationError("índice de dungeons aponta para contrato incorreto")
    entries = _map(data["dungeons"], "dungeons")
    if not entries:
        raise DungeonValidationError("índice de dungeons não pode ser vazio")
    seen_files: set[str] = set()
    for dungeon_id, raw in entries.items():
        _id(dungeon_id, "id da dungeon")
        meta = _map(raw, f"dungeons.{dungeon_id}")
        if set(meta) != {"nome", "local_id", "estatuto", "arquivo"}:
            raise DungeonValidationError(f"dungeons.{dungeon_id} possui estrutura inesperada")
        _text(meta["nome"], f"dungeons.{dungeon_id}.nome")
        _id(meta["local_id"], f"dungeons.{dungeon_id}.local_id")
        if meta["estatuto"] not in contract["estatutos"]:
            raise DungeonValidationError(f"dungeons.{dungeon_id}.estatuto inválido")
        rel, _ = _repo_path(repo, meta["arquivo"], f"dungeons.{dungeon_id}.arquivo", DUNGEONS_DIR)
        if rel in seen_files:
            raise DungeonValidationError(f"manifesto duplicado no índice: {rel}")
        seen_files.add(rel)
    return data


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    plain = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join("".join(char.lower() if char.isalnum() else " " for char in plain).split())


def resolve_dungeon(index: dict[str, Any], query: str) -> tuple[str, dict[str, Any]]:
    entries = index["dungeons"]
    if query in entries:
        return query, entries[query]
    wanted = _normalize(_text(query, "consulta"))
    matches = [
        (dungeon_id, meta)
        for dungeon_id, meta in entries.items()
        if wanted in {_normalize(dungeon_id), _normalize(meta["nome"])}
    ]
    if not matches:
        raise DungeonValidationError(f"dungeon não encontrada: {query}")
    if len(matches) > 1:
        raise DungeonValidationError(
            f"consulta ambígua para {query!r}: {', '.join(item[0] for item in matches)}"
        )
    return matches[0]


def load_manifest(
    repo: Path,
    dungeon_id: str,
    meta: dict[str, Any],
    contract: dict[str, Any],
    *,
    cross_validate: bool = False,
) -> dict[str, Any]:
    rel, path = _repo_path(repo, meta["arquivo"], f"{dungeon_id}.arquivo", DUNGEONS_DIR)
    if path.stat().st_size > contract["orcamento"]["manifesto_max_bytes"]:
        raise DungeonValidationError(f"{dungeon_id}: manifesto excede o orçamento")
    data = _map(_load_yaml(path), rel)
    expected = {
        "schema_dungeon", "natureza", "id", "nome", "local_id", "contrato", "estatuto",
        "escopo_canonico", "premissa", "ativacao", "estrutura", "recompensa_final", "continuidade",
    }
    if set(data) != expected:
        raise DungeonValidationError(f"{dungeon_id}: manifesto possui estrutura inesperada")
    if data["schema_dungeon"] != SCHEMA or data["natureza"] != "preparacao_reservada_nao_materializada":
        raise DungeonValidationError(f"{dungeon_id}: metadados do manifesto inválidos")
    if data["id"] != dungeon_id or data["nome"] != meta["nome"] or data["local_id"] != meta["local_id"]:
        raise DungeonValidationError(f"{dungeon_id}: manifesto diverge do índice")
    if data["contrato"] != CONTRACT_PATH.as_posix() or data["estatuto"] != meta["estatuto"]:
        raise DungeonValidationError(f"{dungeon_id}: contrato ou estatuto divergente")

    scope = _map(data["escopo_canonico"], f"{dungeon_id}.escopo_canonico")
    if set(scope) != {"ancoras", "fatos_preservados", "nao_estabelece"}:
        raise DungeonValidationError(f"{dungeon_id}: escopo canônico inválido")
    anchors = _strings(scope["ancoras"], f"{dungeon_id}.ancoras", maximum=8)
    _strings(scope["fatos_preservados"], f"{dungeon_id}.fatos_preservados", minimum=2, maximum=12)
    _strings(scope["nao_estabelece"], f"{dungeon_id}.nao_estabelece", minimum=3, maximum=12)
    for index, raw in enumerate(anchors):
        _, anchor = _repo_path(repo, raw, f"{dungeon_id}.ancoras[{index}]")
        if not anchor.is_file():
            raise DungeonValidationError(f"{dungeon_id}: âncora inexistente: {raw}")
    _text(data["premissa"], f"{dungeon_id}.premissa")

    activation = _map(data["ativacao"], f"{dungeon_id}.ativacao")
    if set(activation) != {"exige_gatilho_canonico", "materializacao", "nao_ativa"}:
        raise DungeonValidationError(f"{dungeon_id}: ativação possui estrutura inesperada")
    _strings(activation["exige_gatilho_canonico"], f"{dungeon_id}.exige_gatilho_canonico", minimum=2)
    _text(activation["materializacao"], f"{dungeon_id}.materializacao")
    _strings(activation["nao_ativa"], f"{dungeon_id}.nao_ativa", minimum=4)

    structure = _map(data["estrutura"], f"{dungeon_id}.estrutura")
    if set(structure) != {"nivel_inicial", "niveis"}:
        raise DungeonValidationError(f"{dungeon_id}: estrutura inválida")
    levels = _list(structure["niveis"], f"{dungeon_id}.niveis")
    if not 1 <= len(levels) <= contract["orcamento"]["max_niveis"]:
        raise DungeonValidationError(f"{dungeon_id}: quantidade de níveis inválida")
    level_numbers: list[int] = []
    level_files: set[str] = set()
    for position, raw in enumerate(levels, start=1):
        item = _map(raw, f"{dungeon_id}.niveis[{position - 1}]")
        if set(item) != {"numero", "nome", "arquivo"}:
            raise DungeonValidationError(f"{dungeon_id}: nível roteado possui campos inválidos")
        number = _integer(item["numero"], f"{dungeon_id}.nivel.numero", 1, 99)
        level_numbers.append(number)
        _text(item["nome"], f"{dungeon_id}.nivel.nome")
        level_rel, _ = _repo_path(repo, item["arquivo"], f"{dungeon_id}.nivel.arquivo", Path(rel).parent)
        if level_rel in level_files:
            raise DungeonValidationError(f"{dungeon_id}: fragmento de nível duplicado")
        level_files.add(level_rel)
    if level_numbers != list(range(1, len(levels) + 1)):
        raise DungeonValidationError(f"{dungeon_id}: níveis devem ser contíguos a partir de 1")
    if structure["nivel_inicial"] != 1:
        raise DungeonValidationError(f"{dungeon_id}: nivel_inicial deve ser 1")

    reward = _map(data["recompensa_final"], f"{dungeon_id}.recompensa_final")
    if set(reward) != {"id", "fonte", "condicao", "obtencao_automatica"}:
        raise DungeonValidationError(f"{dungeon_id}: recompensa final possui campos inválidos")
    _id(reward["id"], f"{dungeon_id}.recompensa_final.id")
    if reward["fonte"] != PLANNED_REWARDS_PATH.as_posix():
        raise DungeonValidationError(f"{dungeon_id}: recompensa deve reutilizar catálogo planejado")
    _text(reward["condicao"], f"{dungeon_id}.recompensa_final.condicao")
    if reward["obtencao_automatica"] is not False:
        raise DungeonValidationError(f"{dungeon_id}: recompensa nunca pode ser automática")

    continuity = _map(data["continuidade"], f"{dungeon_id}.continuidade")
    if set(continuity) != {"estado", "writer", "checkpoint"}:
        raise DungeonValidationError(f"{dungeon_id}: continuidade possui estrutura inesperada")
    for key in continuity:
        _text(continuity[key], f"{dungeon_id}.continuidade.{key}")

    if cross_validate:
        if not locais.is_canonical(repo, data["local_id"]):
            raise DungeonValidationError(f"{dungeon_id}: local_id não é canônico")
        planned = recompensas.load_planned(repo)["por_local"].get(data["local_id"], [])
        matching = [item for item in planned if item.get("id") == reward["id"]]
        if len(matching) != 1:
            raise DungeonValidationError(f"{dungeon_id}: recompensa final não possui uma declaração planejada")
        if matching[0]["condicao_de_descoberta"] != reward["condicao"]:
            raise DungeonValidationError(f"{dungeon_id}: condição da recompensa diverge do catálogo")
    return data


def _connected_areas(areas: dict[str, dict[str, Any]], entry: str) -> set[str]:
    seen: set[str] = set()
    pending = [entry]
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        pending.extend(areas[current]["conexoes"])
    return seen


def _validate_level(
    repo: Path,
    dungeon_id: str,
    manifest: dict[str, Any],
    level_meta: dict[str, Any],
    contract: dict[str, Any],
    *,
    cross_validate: bool,
) -> dict[str, Any]:
    rel, path = _repo_path(
        repo, level_meta["arquivo"], f"{dungeon_id}.nivel.arquivo",
        Path(next(item["arquivo"] for item in manifest["estrutura"]["niveis"] if item["numero"] == 1)).parent,
    )
    if path.stat().st_size > contract["orcamento"]["nivel_max_bytes"]:
        raise DungeonValidationError(f"{dungeon_id} nível {level_meta['numero']}: fragmento excede orçamento")
    data = _map(_load_yaml(path), rel)
    expected = {
        "schema_nivel_dungeon", "natureza", "dungeon_id", "numero", "nome", "entrada_area",
        "areas", "encontros", "perigos", "descobertas", "saidas", "descanso",
    }
    if set(data) != expected:
        raise DungeonValidationError(f"{dungeon_id} nível {level_meta['numero']}: estrutura inesperada")
    if data["schema_nivel_dungeon"] != SCHEMA or data["natureza"] != "preparacao_reservada_nao_materializada":
        raise DungeonValidationError(f"{dungeon_id} nível {level_meta['numero']}: metadados inválidos")
    if data["dungeon_id"] != dungeon_id or data["numero"] != level_meta["numero"] or data["nome"] != level_meta["nome"]:
        raise DungeonValidationError(f"{dungeon_id} nível {level_meta['numero']}: diverge do manifesto")

    raw_areas = _list(data["areas"], f"{dungeon_id}.areas")
    if not 3 <= len(raw_areas) <= contract["orcamento"]["max_areas_por_nivel"]:
        raise DungeonValidationError(f"{dungeon_id} nível {data['numero']}: quantidade de áreas inválida")
    areas: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_areas):
        area = _map(raw, f"areas[{index}]")
        if set(area) != {"id", "nome", "tipo", "descricao", "sinais", "conexoes"}:
            raise DungeonValidationError(f"areas[{index}] possui campos inválidos")
        area_id = _id(area["id"], f"areas[{index}].id")
        if area_id in areas:
            raise DungeonValidationError(f"área duplicada: {area_id}")
        _text(area["nome"], f"{area_id}.nome")
        if area["tipo"] not in contract["tipos_area"]:
            raise DungeonValidationError(f"{area_id}.tipo inválido")
        _text(area["descricao"], f"{area_id}.descricao")
        _strings(area["sinais"], f"{area_id}.sinais", minimum=2, maximum=6)
        area["conexoes"] = _ids(area["conexoes"], f"{area_id}.conexoes", maximum=6)
        if area_id in area["conexoes"]:
            raise DungeonValidationError(f"{area_id} não pode conectar a si própria")
        areas[area_id] = area
    entry = _id(data["entrada_area"], "entrada_area")
    if entry not in areas or areas[entry]["tipo"] != "entrada":
        raise DungeonValidationError("entrada_area deve apontar para área do tipo entrada")
    for area_id, area in areas.items():
        unknown = set(area["conexoes"]) - set(areas)
        if unknown:
            raise DungeonValidationError(f"{area_id} conecta áreas inexistentes: {sorted(unknown)}")
        for target in area["conexoes"]:
            if area_id not in areas[target]["conexoes"]:
                raise DungeonValidationError(f"conexão assimétrica: {area_id} -> {target}")
    unreachable = set(areas) - _connected_areas(areas, entry)
    if unreachable:
        raise DungeonValidationError(f"áreas desconectadas da entrada: {sorted(unreachable)}")

    encounters = _list(data["encontros"], "encontros")
    if len(encounters) > contract["orcamento"]["max_encontros_por_nivel"]:
        raise DungeonValidationError("nível excede máximo de encontros")
    adversary_ids: set[str] = set()
    for index, raw in enumerate(encounters):
        encounter = _map(raw, f"encontros[{index}]")
        expected_encounter = {
            "id", "area_id", "condicao_materializacao", "adversarios", "objetivo", "sinalizacao",
            "avaliacao_referencia", "alternativas", "retirada",
        }
        if set(encounter) != expected_encounter:
            raise DungeonValidationError(f"encontros[{index}] possui campos inválidos")
        _id(encounter["id"], f"encontros[{index}].id")
        area_id = _id(encounter["area_id"], f"encontros[{index}].area_id")
        if area_id not in areas:
            raise DungeonValidationError(f"encontro aponta para área inexistente: {area_id}")
        _text(encounter["condicao_materializacao"], f"encontros[{index}].condicao_materializacao")
        _text(encounter["objetivo"], f"encontros[{index}].objetivo")
        _text(encounter["sinalizacao"], f"encontros[{index}].sinalizacao")
        _strings(encounter["alternativas"], f"encontros[{index}].alternativas", minimum=3, maximum=8)
        _text(encounter["retirada"], f"encontros[{index}].retirada")
        opponents = _list(encounter["adversarios"], f"encontros[{index}].adversarios")
        if not 1 <= len(opponents) <= 4:
            raise DungeonValidationError("encontro deve referenciar entre um e quatro blocos")
        encounter_ids: set[str] = set()
        quantity = 0
        for opponent_index, raw_opponent in enumerate(opponents):
            opponent = _map(raw_opponent, f"encontros[{index}].adversarios[{opponent_index}]")
            if set(opponent) != {"id", "quantidade"}:
                raise DungeonValidationError("referência de adversário exige id e quantidade")
            adversary_id = _id(opponent["id"], "adversario.id")
            encounter_ids.add(adversary_id)
            adversary_ids.add(adversary_id)
            quantity += _integer(opponent["quantidade"], "adversario.quantidade", 1, 10)
        if len(encounter_ids) != 1:
            raise DungeonValidationError("avaliação determinística exige um único perfil por encontro")

        snapshot = _map(encounter["avaliacao_referencia"], f"encontros[{index}].avaliacao_referencia")
        if set(snapshot) != {"nivel", "vetor", "recursos", "terreno", "iniciativa", "classificacao"}:
            raise DungeonValidationError("avaliacao_referencia possui campos inválidos")
        level = _integer(snapshot["nivel"], "avaliacao_referencia.nivel", 1, 20)
        if snapshot["vetor"] != "combate":
            raise DungeonValidationError("encontro de dungeon deve avaliar vetor combate")
        if snapshot["classificacao"] not in contract["classificacoes_ameaca"]:
            raise DungeonValidationError("classificação de referência inválida")
        if cross_validate:
            adversary_index = adversarios.load_index(repo)
            if not encounter_ids <= set(adversary_index["adversarios"]):
                raise DungeonValidationError(f"encontro referencia adversário inexistente: {sorted(encounter_ids)}")
            assessment = ameacas.evaluate(
                repo, next(iter(encounter_ids)), vector="combate", level=level, enemies=quantity,
                resources=snapshot["recursos"], terrain=snapshot["terreno"], initiative=snapshot["iniciativa"],
            )
            if assessment["resultado"]["classificacao"] != snapshot["classificacao"]:
                raise DungeonValidationError(
                    f"encontro {encounter['id']}: classificação congelada diverge da avaliação"
                )

    dangers = _list(data["perigos"], "perigos")
    if len(dangers) > contract["orcamento"]["max_perigos_por_nivel"]:
        raise DungeonValidationError("nível excede máximo de perigos")
    for index, raw in enumerate(dangers):
        danger = _map(raw, f"perigos[{index}]")
        expected_danger = {
            "id", "area_id", "gatilho", "sinalizacao", "resolucao", "falha", "sucesso", "contrajogo"
        }
        if set(danger) != expected_danger:
            raise DungeonValidationError(f"perigos[{index}] possui campos inválidos")
        _id(danger["id"], f"perigos[{index}].id")
        if danger["area_id"] not in areas:
            raise DungeonValidationError(f"perigo aponta para área inexistente: {danger['area_id']}")
        _text(danger["gatilho"], f"perigos[{index}].gatilho")
        _text(danger["sinalizacao"], f"perigos[{index}].sinalizacao")
        resolution = _map(danger["resolucao"], f"perigos[{index}].resolucao")
        if set(resolution) != {"tipo", "atributo", "cd"}:
            raise DungeonValidationError("resolução de perigo exige tipo, atributo e cd")
        if resolution["tipo"] not in contract["tipos_resolucao_perigo"]:
            raise DungeonValidationError("tipo de resolução de perigo inválido")
        _text(resolution["atributo"], "resolucao.atributo")
        _integer(resolution["cd"], "resolucao.cd", 5, 30)
        failure = _map(danger["falha"], f"perigos[{index}].falha")
        if set(failure) != {"dano", "consequencia"}:
            raise DungeonValidationError("falha de perigo exige dano e consequência")
        if failure["dano"] is not None:
            damage = _map(failure["dano"], f"perigos[{index}].falha.dano")
            if set(damage) != {"formula", "tipo"} or not DICE_RE.fullmatch(_text(damage["formula"], "dano.formula")):
                raise DungeonValidationError("dano de perigo inválido")
            _text(damage["tipo"], "dano.tipo")
        _text(failure["consequencia"], f"perigos[{index}].falha.consequencia")
        _text(danger["sucesso"], f"perigos[{index}].sucesso")
        _strings(danger["contrajogo"], f"perigos[{index}].contrajogo", minimum=2, maximum=6)

    discoveries = _list(data["descobertas"], "descobertas")
    for index, raw in enumerate(discoveries):
        discovery = _map(raw, f"descobertas[{index}]")
        if set(discovery) != {"id", "area_id", "condicao", "resultado", "estatuto"}:
            raise DungeonValidationError(f"descobertas[{index}] possui campos inválidos")
        _id(discovery["id"], f"descobertas[{index}].id")
        if discovery["area_id"] not in areas:
            raise DungeonValidationError("descoberta aponta para área inexistente")
        _text(discovery["condicao"], f"descobertas[{index}].condicao")
        _text(discovery["resultado"], f"descobertas[{index}].resultado")
        if discovery["estatuto"] != "possibilidade_ate_descoberta":
            raise DungeonValidationError("descoberta preparada não pode nascer como conhecimento")

    exits = _list(data["saidas"], "saidas")
    if len(exits) < 2:
        raise DungeonValidationError("cada nível deve possuir progressão e/ou mais de uma saída")
    retreat_count = 0
    destinations: set[str] = set()
    for index, raw in enumerate(exits):
        exit_spec = _map(raw, f"saidas[{index}]")
        if set(exit_spec) != {"id", "area_id", "destino", "tipo", "condicao", "sinalizacao"}:
            raise DungeonValidationError(f"saidas[{index}] possui campos inválidos")
        _id(exit_spec["id"], f"saidas[{index}].id")
        if exit_spec["area_id"] not in areas:
            raise DungeonValidationError("saída aponta para área inexistente")
        destination = _text(exit_spec["destino"], f"saidas[{index}].destino")
        if destination != "superficie" and not re.fullmatch(r"nivel_[1-9][0-9]*", destination):
            raise DungeonValidationError(f"destino de saída inválido: {destination}")
        destinations.add(destination)
        if exit_spec["tipo"] not in {"recuo", "progressao"}:
            raise DungeonValidationError("tipo de saída inválido")
        retreat_count += int(exit_spec["tipo"] == "recuo")
        _text(exit_spec["condicao"], f"saidas[{index}].condicao")
        _text(exit_spec["sinalizacao"], f"saidas[{index}].sinalizacao")
    if retreat_count < 1:
        raise DungeonValidationError("todo nível exige ao menos um recuo observável")
    total_levels = len(manifest["estrutura"]["niveis"])
    if data["numero"] < total_levels and f"nivel_{data['numero'] + 1}" not in destinations:
        raise DungeonValidationError("nível não final precisa conectar ao próximo")
    if data["numero"] == total_levels and any(
        target.startswith("nivel_") and int(target.split("_")[1]) > total_levels for target in destinations
    ):
        raise DungeonValidationError("nível final aponta para nível inexistente")

    rest = _map(data["descanso"], "descanso")
    if set(rest) != {"seguro", "condicoes"} or rest["seguro"] is not False:
        raise DungeonValidationError("descanso de dungeon não pode ser garantido pela preparação")
    _strings(rest["condicoes"], "descanso.condicoes", minimum=1, maximum=4)
    data["_referencias_adversarios"] = sorted(adversary_ids)
    return data


def show(repo: Path, query: str) -> dict[str, Any]:
    contract = load_contract(repo)
    index = load_index(repo, contract)
    dungeon_id, meta = resolve_dungeon(index, query)
    manifest = load_manifest(repo, dungeon_id, meta, contract)
    result = {
        "schema_consulta_dungeon": 1,
        "dungeon_id": dungeon_id,
        "manifesto": manifest,
        "fontes_lidas": [
            "campanha.yaml", CONTRACT_PATH.as_posix(), INDEX_PATH.as_posix(), meta["arquivo"],
        ],
        "limites": [
            "preparação não materializa acesso, encontro, descoberta ou recompensa",
            "consultar um nível somente quando a exploração o tornar relevante",
        ],
    }
    if len(_dump(result).encode("utf-8")) > contract["orcamento"]["consulta_max_bytes"]:
        raise DungeonValidationError("consulta de manifesto excede o orçamento")
    return result


def show_level(repo: Path, query: str, number: int) -> dict[str, Any]:
    contract = load_contract(repo)
    index = load_index(repo, contract)
    dungeon_id, meta = resolve_dungeon(index, query)
    manifest = load_manifest(repo, dungeon_id, meta, contract)
    matches = [item for item in manifest["estrutura"]["niveis"] if item["numero"] == number]
    if len(matches) != 1:
        raise DungeonValidationError(f"nível inexistente em {dungeon_id}: {number}")
    level = _validate_level(repo, dungeon_id, manifest, matches[0], contract, cross_validate=False)
    references = level.pop("_referencias_adversarios")
    result = {
        "schema_consulta_nivel_dungeon": 1,
        "dungeon_id": dungeon_id,
        "local_id": manifest["local_id"],
        "estatuto": manifest["estatuto"],
        "nivel": level,
        "referencias_adversarios": references,
        "fontes_lidas": [
            "campanha.yaml", CONTRACT_PATH.as_posix(), INDEX_PATH.as_posix(),
            meta["arquivo"], matches[0]["arquivo"],
        ],
        "limites": [
            "referência não materializa presença; confirmar pela cena",
            "abrir ficha e ameaça por consulta própria somente se o encontro materializar",
        ],
    }
    if len(_dump(result).encode("utf-8")) > contract["orcamento"]["consulta_max_bytes"]:
        raise DungeonValidationError(f"consulta do nível {number} excede o orçamento")
    return result


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    count = 0
    levels_count = 0
    try:
        contract = load_contract(repo)
        index = load_index(repo, contract)
        for dungeon_id, meta in index["dungeons"].items():
            manifest = load_manifest(repo, dungeon_id, meta, contract, cross_validate=True)
            for level_meta in manifest["estrutura"]["niveis"]:
                level = _validate_level(
                    repo, dungeon_id, manifest, level_meta, contract, cross_validate=True
                )
                level.pop("_referencias_adversarios", None)
                levels_count += 1
            show(repo, dungeon_id)
            for level_meta in manifest["estrutura"]["niveis"]:
                show_level(repo, dungeon_id, level_meta["numero"])
            count += 1
    except (DungeonValidationError, adversarios.AdversaryValidationError, ameacas.ThreatValidationError, locais.LocationError, recompensas.RewardMapError, OSError) as exc:
        errors.append(str(exc))
    return {"ok": not errors, "dungeons": count, "niveis": levels_count, "erros": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="comando", required=True)
    show_parser = sub.add_parser("mostrar", help="abre somente o manifesto dirigido")
    show_parser.add_argument("dungeon")
    level_parser = sub.add_parser("nivel", help="abre exatamente um nível dirigido")
    level_parser.add_argument("dungeon")
    level_parser.add_argument("numero", type=int)
    sub.add_parser("validar", help="valida todo o domínio em manutenção/CI")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.comando == "mostrar":
            result = show(repo, args.dungeon)
        elif args.comando == "nivel":
            result = show_level(repo, args.dungeon, args.numero)
        else:
            result = validate_repo(repo)
        print(_dump(result), end="")
        return 0 if result.get("ok", True) else 1
    except DungeonValidationError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
