#!/usr/bin/env python3
"""Registro mecânico fragmentado de adversários competentes.

Esta camada não decide quem está presente nem inicia encontros. Ela valida e
projeta números já preparados, impedindo que uma ficha incompleta ou ajustada
depois da rolagem seja tratada como adversário executável.
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

import yaml


CONTRACT_PATH = Path("narrador/adversarios/contrato.yaml")
INDEX_PATH = Path("narrador/adversarios/index.yaml")
SHEETS_DIR = Path("narrador/adversarios/fichas")
SPECIALTIES_DIR = Path("narrador/adversarios/especialidades")
CAMPAIGN_PATH = Path("campanha.yaml")
SCHEMA = 1
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_:-]{0,95}$")
DICE_RE = re.compile(r"^[1-9][0-9]*d[1-9][0-9]*(?:[+-][0-9]+)?$")


class AdversaryValidationError(ValueError):
    """Erro de contrato da camada mecânica de adversários."""


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise AdversaryValidationError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise AdversaryValidationError(f"YAML inválido em {path}: {exc}") from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AdversaryValidationError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise AdversaryValidationError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str, *, nullable: bool = False) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value.strip():
        raise AdversaryValidationError(f"{label} deve ser texto não vazio")
    return " ".join(value.strip().split())


def _id(value: Any, label: str) -> str:
    result = _text(value, label)
    assert isinstance(result, str)
    if not ID_RE.fullmatch(result):
        raise AdversaryValidationError(f"{label} deve ser id ASCII minúsculo estável")
    return result


def _integer(value: Any, label: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise AdversaryValidationError(f"{label} deve ser inteiro")
    if not minimum <= value <= maximum:
        raise AdversaryValidationError(
            f"{label} deve ficar entre {minimum} e {maximum}"
        )
    return value


def _strings(
    value: Any,
    label: str,
    *,
    allow_empty: bool = True,
) -> list[str]:
    raw = _list(value, label)
    result = [_text(item, f"{label}[{index}]") for index, item in enumerate(raw)]
    if not allow_empty and not result:
        raise AdversaryValidationError(f"{label} não pode ser vazio")
    if len(result) != len(set(result)):
        raise AdversaryValidationError(f"{label} não pode conter duplicatas")
    return [item for item in result if isinstance(item, str)]


def _enum(value: Any, allowed: set[str], label: str) -> str:
    result = _text(value, label)
    assert isinstance(result, str)
    if result not in allowed:
        raise AdversaryValidationError(
            f"{label} inválido: {result}; esperado: {', '.join(sorted(allowed))}"
        )
    return result


def _repo_path(repo: Path, raw: Any, label: str, prefix: Path) -> tuple[str, Path]:
    value = _text(raw, label)
    assert isinstance(value, str)
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts:
        raise AdversaryValidationError(f"{label} deve ficar dentro do repositório")
    try:
        rel.relative_to(prefix)
    except ValueError as exc:
        raise AdversaryValidationError(
            f"{label} deve permanecer sob {prefix.as_posix()}"
        ) from exc
    return rel.as_posix(), repo / rel


def _dump(value: Any) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def _contract_set(contract: dict[str, Any], key: str) -> set[str]:
    return set(_strings(contract.get(key), key, allow_empty=False))


def load_contract(repo: Path) -> dict[str, Any]:
    data = _map(_load_yaml(repo / CONTRACT_PATH), CONTRACT_PATH.as_posix())
    expected = {
        "schema_contrato_adversarios",
        "natureza",
        "ruleset_obrigatorio",
        "orcamento",
        "tipos_adversario",
        "funcoes",
        "escalas",
        "origens_mecanicas",
        "ativacoes",
        "tipos_resolucao",
        "modos_ataque",
        "executores_teste",
        "atributos",
        "tipos_limite",
        "recuperacoes_recurso",
        "posturas_retirada",
        "invariantes",
    }
    if set(data) != expected:
        raise AdversaryValidationError("contrato de adversários possui estrutura inesperada")
    if data["schema_contrato_adversarios"] != SCHEMA:
        raise AdversaryValidationError("schema_contrato_adversarios deve ser 1")
    if data["natureza"] != "contrato_mecanico_reservado":
        raise AdversaryValidationError("natureza do contrato de adversários inválida")
    if data["ruleset_obrigatorio"] != "dnd_5_5e":
        raise AdversaryValidationError("contrato deve permanecer no ruleset dnd_5_5e")

    budget = _map(data["orcamento"], "orcamento")
    budget_keys = {
        "indice_max_bytes",
        "consulta_dirigida_max_bytes",
        "fragmento_base_max_bytes",
        "fragmento_especialidades_max_bytes",
    }
    if set(budget) != budget_keys:
        raise AdversaryValidationError("orcamento possui estrutura inesperada")
    for key, value in budget.items():
        _integer(value, f"orcamento.{key}", minimum=1024, maximum=32 * 1024)
    if budget["consulta_dirigida_max_bytes"] != 8 * 1024:
        raise AdversaryValidationError("consulta dirigida deve respeitar o teto L2 de 8 KiB")

    for key in (
        "tipos_adversario",
        "funcoes",
        "escalas",
        "origens_mecanicas",
        "ativacoes",
        "tipos_resolucao",
        "modos_ataque",
        "executores_teste",
        "atributos",
        "tipos_limite",
        "recuperacoes_recurso",
        "posturas_retirada",
    ):
        _strings(data[key], key, allow_empty=False)
    if set(data["atributos"]) != {"for", "des", "con", "int", "sab", "car"}:
        raise AdversaryValidationError("contrato deve declarar os seis atributos")

    invariants = _map(data["invariantes"], "invariantes")
    required_invariants = {
        "numeros_definidos_antes_da_rolagem",
        "dificuldade_nao_muda_pos_rolagem",
        "toda_acao_tem_resolucao_e_contrajogo",
        "escala_lendaria_exige_acao_lendaria",
        "custo_referencia_recurso_declarado",
        "especialidade_nao_combativa_tem_procedimento",
        "taticas_nao_substituem_decisao_causal",
        "retirada_nao_e_salvamento_automatico",
        "consulta_dirigida_nao_abre_outros_adversarios",
    }
    if set(invariants) != required_invariants or not all(
        value is True for value in invariants.values()
    ):
        raise AdversaryValidationError("invariantes do contrato devem permanecer verdadeiras")
    return data


def load_campaign_ruleset(repo: Path) -> str:
    campaign = _map(_load_yaml(repo / CAMPAIGN_PATH), CAMPAIGN_PATH.as_posix())
    system = _map(campaign.get("sistema"), "campanha.sistema")
    ruleset = _map(system.get("ruleset"), "campanha.sistema.ruleset")
    return _text(ruleset.get("atual"), "campanha.sistema.ruleset.atual") or ""


def load_index(repo: Path, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = contract or load_contract(repo)
    path = repo / INDEX_PATH
    if path.stat().st_size > contract["orcamento"]["indice_max_bytes"]:
        raise AdversaryValidationError("índice de adversários excede o orçamento")
    data = _map(_load_yaml(path), INDEX_PATH.as_posix())
    if set(data) != {"schema_indice_adversarios", "natureza", "contrato", "adversarios"}:
        raise AdversaryValidationError("índice de adversários possui estrutura inesperada")
    if data["schema_indice_adversarios"] != SCHEMA or data["natureza"] != "reservado":
        raise AdversaryValidationError("metadados do índice de adversários inválidos")
    if data["contrato"] != CONTRACT_PATH.as_posix():
        raise AdversaryValidationError("índice deve apontar para o contrato mecânico autoritativo")
    entries = _map(data["adversarios"], "adversarios")
    seen_paths: set[str] = set()
    for adversary_id, raw in entries.items():
        _id(adversary_id, "id do adversário no índice")
        meta = _map(raw, f"adversarios.{adversary_id}")
        if set(meta) != {"nome", "tipo", "funcao", "arquivo", "especialidades_arquivo"}:
            raise AdversaryValidationError(
                f"adversarios.{adversary_id} possui estrutura inesperada"
            )
        _text(meta["nome"], f"adversarios.{adversary_id}.nome")
        _enum(meta["tipo"], _contract_set(contract, "tipos_adversario"), f"{adversary_id}.tipo")
        _enum(meta["funcao"], _contract_set(contract, "funcoes"), f"{adversary_id}.funcao")
        base_rel, _ = _repo_path(repo, meta["arquivo"], f"{adversary_id}.arquivo", SHEETS_DIR)
        detail_rel, _ = _repo_path(
            repo,
            meta["especialidades_arquivo"],
            f"{adversary_id}.especialidades_arquivo",
            SPECIALTIES_DIR,
        )
        for rel in (base_rel, detail_rel):
            if rel in seen_paths:
                raise AdversaryValidationError(f"fragmento duplicado no índice: {rel}")
            seen_paths.add(rel)
    return data


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(
        "".join(char.lower() if char.isalnum() else " " for char in ascii_text).split()
    )


def resolve_adversary(index: dict[str, Any], query: str) -> tuple[str, dict[str, Any]]:
    entries = index["adversarios"]
    if query in entries:
        return query, entries[query]
    wanted = _normalize(query)
    matches = [
        (adversary_id, meta)
        for adversary_id, meta in entries.items()
        if wanted in {_normalize(adversary_id), _normalize(meta["nome"])}
    ]
    if not matches:
        raise AdversaryValidationError(f"adversário não encontrado: {query}")
    if len(matches) > 1:
        raise AdversaryValidationError(
            f"consulta ambígua para {query!r}: {', '.join(item[0] for item in matches)}"
        )
    return matches[0]


def _validate_provenance(raw: Any, contract: dict[str, Any], label: str) -> None:
    data = _map(raw, label)
    if set(data) != {"origem", "referencia", "decisao", "adaptacao"}:
        raise AdversaryValidationError(f"{label} possui estrutura inesperada")
    origin = _enum(data["origem"], _contract_set(contract, "origens_mecanicas"), f"{label}.origem")
    _text(data["referencia"], f"{label}.referencia")
    decision = _text(data["decisao"], f"{label}.decisao", nullable=True)
    adaptation = _text(data["adaptacao"], f"{label}.adaptacao", nullable=True)
    if origin == "adaptado_edicao_anterior" and not adaptation:
        raise AdversaryValidationError(f"{label}: adaptação de edição anterior exige registro")
    if origin == "compatibilidade_2014_aprovada" and not decision:
        raise AdversaryValidationError(f"{label}: compatibilidade 2014 exige decisão explícita")


def _validate_resolution(raw: Any, contract: dict[str, Any], label: str) -> None:
    data = _map(raw, label)
    resolution_type = _enum(
        data.get("tipo"), _contract_set(contract, "tipos_resolucao"), f"{label}.tipo"
    )
    attributes = _contract_set(contract, "atributos")
    if resolution_type == "ataque":
        if set(data) != {"tipo", "bonus", "defesa", "modo"}:
            raise AdversaryValidationError(f"{label}: ataque exige tipo, bonus, defesa e modo")
        _integer(data["bonus"], f"{label}.bonus", minimum=-5, maximum=25)
        if data["defesa"] != "ca":
            raise AdversaryValidationError(f"{label}.defesa deve ser ca")
        _enum(data["modo"], _contract_set(contract, "modos_ataque"), f"{label}.modo")
    elif resolution_type == "salvaguarda":
        if set(data) != {"tipo", "atributo", "cd"}:
            raise AdversaryValidationError(f"{label}: salvaguarda exige tipo, atributo e cd")
        _enum(data["atributo"], attributes, f"{label}.atributo")
        _integer(data["cd"], f"{label}.cd", minimum=5, maximum=35)
    elif resolution_type == "teste":
        if set(data) != {"tipo", "executor", "atributo_ou_pericia", "bonus", "cd"}:
            raise AdversaryValidationError(
                f"{label}: teste exige tipo, executor, atributo_ou_pericia, bonus e cd"
            )
        executor = _enum(
            data["executor"], _contract_set(contract, "executores_teste"), f"{label}.executor"
        )
        _text(data["atributo_ou_pericia"], f"{label}.atributo_ou_pericia")
        if executor == "adversario":
            _integer(data["bonus"], f"{label}.bonus", minimum=-10, maximum=30)
        elif data["bonus"] is not None:
            raise AdversaryValidationError(
                f"{label}.bonus deve ser null quando o opositor usa a própria ficha"
            )
        _integer(data["cd"], f"{label}.cd", minimum=5, maximum=35)
    elif resolution_type == "teste_oposto":
        if set(data) != {"tipo", "atributo_ou_pericia", "bonus", "oposicao"}:
            raise AdversaryValidationError(
                f"{label}: teste_oposto exige tipo, atributo_ou_pericia, bonus e oposicao"
            )
        _text(data["atributo_ou_pericia"], f"{label}.atributo_ou_pericia")
        _integer(data["bonus"], f"{label}.bonus", minimum=-10, maximum=30)
        _text(data["oposicao"], f"{label}.oposicao")
    else:
        if set(data) != {"tipo", "condicao"}:
            raise AdversaryValidationError(f"{label}: automática exige tipo e condicao")
        _text(data["condicao"], f"{label}.condicao")


def _validate_limit(raw: Any, contract: dict[str, Any], label: str) -> None:
    data = _map(raw, label)
    if set(data) != {"tipo", "valor"}:
        raise AdversaryValidationError(f"{label} exige tipo e valor")
    limit_type = _enum(data["tipo"], _contract_set(contract, "tipos_limite"), f"{label}.tipo")
    value = data["valor"]
    if limit_type == "ilimitado":
        if value is not None:
            raise AdversaryValidationError(f"{label}.valor deve ser null para ilimitado")
    elif limit_type == "usos_por_descanso":
        _integer(value, f"{label}.valor", minimum=1, maximum=99)
    else:
        _text(value, f"{label}.valor")


def _validate_cost(raw: Any, resources: set[str], label: str) -> None:
    if raw is None:
        return
    data = _map(raw, label)
    if set(data) != {"recurso", "quantidade"}:
        raise AdversaryValidationError(f"{label} exige recurso e quantidade")
    resource = _id(data["recurso"], f"{label}.recurso")
    if resource not in resources:
        raise AdversaryValidationError(f"{label} referencia recurso não declarado: {resource}")
    _integer(data["quantidade"], f"{label}.quantidade", minimum=1, maximum=99)


def _validate_actions(
    raw: Any,
    contract: dict[str, Any],
    label: str,
    activation: str,
    resources: set[str],
    *,
    required: bool,
) -> set[str]:
    actions = _list(raw, label)
    if required and not actions:
        raise AdversaryValidationError(f"{label} deve conter ao menos uma ação")
    seen: set[str] = set()
    for index, raw_action in enumerate(actions):
        item_label = f"{label}[{index}]"
        action = _map(raw_action, item_label)
        expected = {
            "id", "nome", "ativacao", "gatilho", "alcance", "alvos",
            "resolucao", "efeitos", "custo", "limite", "contrajogo",
        }
        if set(action) != expected:
            raise AdversaryValidationError(f"{item_label} possui estrutura inesperada")
        action_id = _id(action["id"], f"{item_label}.id")
        if action_id in seen:
            raise AdversaryValidationError(f"{label} possui id duplicado: {action_id}")
        seen.add(action_id)
        _text(action["nome"], f"{item_label}.nome")
        if action["ativacao"] != activation:
            raise AdversaryValidationError(f"{item_label}.ativacao deve ser {activation}")
        trigger = _text(action["gatilho"], f"{item_label}.gatilho", nullable=True)
        if activation == "reacao" and not trigger:
            raise AdversaryValidationError(f"{item_label}: reação exige gatilho")
        _text(action["alcance"], f"{item_label}.alcance")
        _text(action["alvos"], f"{item_label}.alvos")
        _validate_resolution(action["resolucao"], contract, f"{item_label}.resolucao")
        effects = _list(action["efeitos"], f"{item_label}.efeitos")
        if not effects:
            raise AdversaryValidationError(f"{item_label}.efeitos não pode ser vazio")
        for effect_index, raw_effect in enumerate(effects):
            effect = _map(raw_effect, f"{item_label}.efeitos[{effect_index}]")
            if set(effect) != {"quando", "regra", "dano"}:
                raise AdversaryValidationError(
                    f"{item_label}.efeitos[{effect_index}] exige quando, regra e dano"
                )
            _text(effect["quando"], f"{item_label}.efeitos[{effect_index}].quando")
            _text(effect["regra"], f"{item_label}.efeitos[{effect_index}].regra")
            damage = effect["dano"]
            if damage is not None:
                damage_map = _map(damage, f"{item_label}.efeitos[{effect_index}].dano")
                if set(damage_map) != {"formula", "tipo"}:
                    raise AdversaryValidationError(
                        f"{item_label}.efeitos[{effect_index}].dano exige formula e tipo"
                    )
                formula = _text(
                    damage_map["formula"], f"{item_label}.efeitos[{effect_index}].dano.formula"
                )
                assert isinstance(formula, str)
                if not DICE_RE.fullmatch(formula):
                    raise AdversaryValidationError(
                        f"{item_label}.efeitos[{effect_index}].dano.formula inválida"
                    )
                _text(damage_map["tipo"], f"{item_label}.efeitos[{effect_index}].dano.tipo")
        _validate_cost(action["custo"], resources, f"{item_label}.custo")
        _validate_limit(action["limite"], contract, f"{item_label}.limite")
        _strings(action["contrajogo"], f"{item_label}.contrajogo", allow_empty=False)
    return seen


def validate_adversary_data(
    repo: Path,
    adversary_id: str,
    meta: dict[str, Any],
    data: Any,
    contract: dict[str, Any],
) -> dict[str, Any]:
    sheet = _map(data, adversary_id)
    expected = {
        "schema_adversario", "natureza", "id", "nome", "tipo", "funcao",
        "ruleset", "proveniencia", "perfil", "escala", "defesas", "movimento",
        "atributos", "bonus_proficiencia", "iniciativa", "salvaguardas", "pericias",
        "vulnerabilidades", "resistencias", "imunidades_dano",
        "imunidades_condicao", "sentidos", "idiomas", "recursos", "tracos",
        "acoes", "acoes_bonus", "reacoes", "acoes_lendarias", "taticas", "retirada",
        "especialidades",
    }
    if set(sheet) != expected:
        raise AdversaryValidationError(f"{adversary_id}: ficha possui estrutura inesperada")
    if sheet["schema_adversario"] != SCHEMA or sheet["natureza"] != "reservado":
        raise AdversaryValidationError(f"{adversary_id}: metadados da ficha inválidos")
    if sheet["id"] != adversary_id or sheet["nome"] != meta["nome"]:
        raise AdversaryValidationError(f"{adversary_id}: identidade diverge do índice")
    if sheet["tipo"] != meta["tipo"] or sheet["funcao"] != meta["funcao"]:
        raise AdversaryValidationError(f"{adversary_id}: classificação diverge do índice")
    active_ruleset = load_campaign_ruleset(repo)
    if sheet["ruleset"] != contract["ruleset_obrigatorio"] or sheet["ruleset"] != active_ruleset:
        raise AdversaryValidationError(
            f"{adversary_id}: ruleset {sheet['ruleset']!r} diverge do ruleset ativo {active_ruleset!r}"
        )
    _validate_provenance(sheet["proveniencia"], contract, f"{adversary_id}.proveniencia")

    profile = _map(sheet["perfil"], f"{adversary_id}.perfil")
    if set(profile) != {"tamanho", "tipo_criatura", "alinhamento"}:
        raise AdversaryValidationError(
            f"{adversary_id}.perfil exige tamanho, tipo_criatura e alinhamento"
        )
    for key in profile:
        _text(profile[key], f"{adversary_id}.perfil.{key}")

    scale = _map(sheet["escala"], f"{adversary_id}.escala")
    if set(scale) != {"categoria", "referencia"}:
        raise AdversaryValidationError(f"{adversary_id}.escala exige categoria e referencia")
    scale_category = _enum(
        scale["categoria"], _contract_set(contract, "escalas"), f"{adversary_id}.escala.categoria"
    )
    _text(scale["referencia"], f"{adversary_id}.escala.referencia")

    defenses = _map(sheet["defesas"], f"{adversary_id}.defesas")
    if set(defenses) != {"ca", "pv", "dados_vida"}:
        raise AdversaryValidationError(f"{adversary_id}.defesas exige ca, pv e dados_vida")
    _integer(defenses["ca"], f"{adversary_id}.defesas.ca", minimum=1, maximum=35)
    _integer(defenses["pv"], f"{adversary_id}.defesas.pv", minimum=1, maximum=9999)
    dice = _text(defenses["dados_vida"], f"{adversary_id}.defesas.dados_vida")
    assert isinstance(dice, str)
    if not DICE_RE.fullmatch(dice):
        raise AdversaryValidationError(f"{adversary_id}.defesas.dados_vida possui fórmula inválida")

    movement = _map(sheet["movimento"], f"{adversary_id}.movimento")
    if not movement:
        raise AdversaryValidationError(f"{adversary_id}.movimento não pode ser vazio")
    movement_values = [
        _integer(value, f"{adversary_id}.movimento.{key}", minimum=0, maximum=1000)
        for key, value in movement.items()
    ]
    if not any(value > 0 for value in movement_values):
        raise AdversaryValidationError(f"{adversary_id}.movimento precisa de ao menos um deslocamento positivo")

    attributes = _map(sheet["atributos"], f"{adversary_id}.atributos")
    if set(attributes) != _contract_set(contract, "atributos"):
        raise AdversaryValidationError(f"{adversary_id}: atributos devem conter os seis valores")
    for key, value in attributes.items():
        _integer(value, f"{adversary_id}.atributos.{key}", minimum=1, maximum=30)
    _integer(sheet["bonus_proficiencia"], f"{adversary_id}.bonus_proficiencia", minimum=2, maximum=9)
    _integer(sheet["iniciativa"], f"{adversary_id}.iniciativa", minimum=-10, maximum=30)
    for group in ("salvaguardas", "pericias"):
        values = _map(sheet[group], f"{adversary_id}.{group}")
        for key, value in values.items():
            _text(key, f"{adversary_id}.{group}.chave")
            _integer(value, f"{adversary_id}.{group}.{key}", minimum=-10, maximum=30)
    for group in ("vulnerabilidades", "resistencias", "imunidades_dano", "imunidades_condicao", "idiomas"):
        _strings(sheet[group], f"{adversary_id}.{group}")
    senses = _map(sheet["sentidos"], f"{adversary_id}.sentidos")
    if set(senses) != {"percepcao_passiva", "especiais"}:
        raise AdversaryValidationError(f"{adversary_id}.sentidos exige percepcao_passiva e especiais")
    _integer(senses["percepcao_passiva"], f"{adversary_id}.sentidos.percepcao_passiva", minimum=1, maximum=40)
    _strings(senses["especiais"], f"{adversary_id}.sentidos.especiais")

    resources: set[str] = set()
    for index, raw_resource in enumerate(_list(sheet["recursos"], f"{adversary_id}.recursos")):
        label = f"{adversary_id}.recursos[{index}]"
        resource = _map(raw_resource, label)
        if set(resource) != {"id", "nome", "maximo", "recuperacao", "condicao_recuperacao"}:
            raise AdversaryValidationError(f"{label} possui estrutura inesperada")
        resource_id = _id(resource["id"], f"{label}.id")
        if resource_id in resources:
            raise AdversaryValidationError(f"{adversary_id}: recurso duplicado {resource_id}")
        resources.add(resource_id)
        _text(resource["nome"], f"{label}.nome")
        _integer(resource["maximo"], f"{label}.maximo", minimum=1, maximum=999)
        recovery = _enum(
            resource["recuperacao"],
            _contract_set(contract, "recuperacoes_recurso"),
            f"{label}.recuperacao",
        )
        condition = _text(resource["condicao_recuperacao"], f"{label}.condicao_recuperacao", nullable=True)
        if recovery == "condicional" and not condition:
            raise AdversaryValidationError(f"{label}: recuperação condicional exige condição")

    traits = _list(sheet["tracos"], f"{adversary_id}.tracos")
    if not traits:
        raise AdversaryValidationError(f"{adversary_id}.tracos não pode ser vazio")
    trait_ids: set[str] = set()
    for index, raw_trait in enumerate(traits):
        label = f"{adversary_id}.tracos[{index}]"
        trait = _map(raw_trait, label)
        if set(trait) != {"id", "nome", "regra", "contrajogo"}:
            raise AdversaryValidationError(f"{label} possui estrutura inesperada")
        trait_id = _id(trait["id"], f"{label}.id")
        if trait_id in trait_ids:
            raise AdversaryValidationError(f"{adversary_id}: traço duplicado {trait_id}")
        trait_ids.add(trait_id)
        _text(trait["nome"], f"{label}.nome")
        _text(trait["regra"], f"{label}.regra")
        _strings(trait["contrajogo"], f"{label}.contrajogo", allow_empty=False)

    all_action_ids: set[str] = set()
    for group, activation, required in (
        ("acoes", "acao", True),
        ("acoes_bonus", "acao_bonus", False),
        ("reacoes", "reacao", False),
        ("acoes_lendarias", "acao_lendaria", False),
    ):
        ids = _validate_actions(
            sheet[group], contract, f"{adversary_id}.{group}", activation, resources, required=required
        )
        overlap = all_action_ids & ids
        if overlap:
            raise AdversaryValidationError(
                f"{adversary_id}: id de ação repetido entre grupos: {', '.join(sorted(overlap))}"
            )
        all_action_ids |= ids
    if scale_category == "lendario" and not sheet["acoes_lendarias"]:
        raise AdversaryValidationError(
            f"{adversary_id}: escala lendária exige ao menos uma ação lendária"
        )

    tactics = _map(sheet["taticas"], f"{adversary_id}.taticas")
    tactic_keys = {"abertura", "prioridades", "adaptacoes", "uso_terreno", "evita"}
    if set(tactics) != tactic_keys:
        raise AdversaryValidationError(f"{adversary_id}.taticas possui estrutura inesperada")
    for key in tactic_keys:
        _strings(tactics[key], f"{adversary_id}.taticas.{key}", allow_empty=False)

    retreat = _map(sheet["retirada"], f"{adversary_id}.retirada")
    retreat_keys = {"postura", "gatilhos", "metodo", "custo_ou_risco", "sinais_observaveis"}
    if set(retreat) != retreat_keys:
        raise AdversaryValidationError(f"{adversary_id}.retirada possui estrutura inesperada")
    posture = _enum(
        retreat["postura"], _contract_set(contract, "posturas_retirada"), f"{adversary_id}.retirada.postura"
    )
    triggers = _strings(
        retreat["gatilhos"],
        f"{adversary_id}.retirada.gatilhos",
        allow_empty=posture == "luta_ate_incapacitado",
    )
    if posture != "luta_ate_incapacitado" and not triggers:
        raise AdversaryValidationError(f"{adversary_id}: retirada deve possuir gatilho definido")
    _text(retreat["metodo"], f"{adversary_id}.retirada.metodo")
    _text(retreat["custo_ou_risco"], f"{adversary_id}.retirada.custo_ou_risco")
    _strings(retreat["sinais_observaveis"], f"{adversary_id}.retirada.sinais_observaveis", allow_empty=False)

    pointer = _map(sheet["especialidades"], f"{adversary_id}.especialidades")
    if set(pointer) != {"arquivo", "ids"}:
        raise AdversaryValidationError(f"{adversary_id}.especialidades exige arquivo e ids")
    detail_rel, _ = _repo_path(
        repo, pointer["arquivo"], f"{adversary_id}.especialidades.arquivo", SPECIALTIES_DIR
    )
    if detail_rel != meta["especialidades_arquivo"]:
        raise AdversaryValidationError(f"{adversary_id}: ponteiro de especialidades diverge do índice")
    specialty_ids = _strings(pointer["ids"], f"{adversary_id}.especialidades.ids", allow_empty=False)
    for specialty_id in specialty_ids:
        _id(specialty_id, f"{adversary_id}.especialidades.ids")
    return sheet


def validate_specialties_data(
    adversary_id: str,
    sheet: dict[str, Any],
    raw: Any,
    contract: dict[str, Any],
    resources: set[str],
) -> dict[str, Any]:
    data = _map(raw, f"especialidades de {adversary_id}")
    if set(data) != {"schema_especialidades_adversario", "natureza", "adversario_id", "especialidades"}:
        raise AdversaryValidationError(f"{adversary_id}: fragmento de especialidades possui estrutura inesperada")
    if data["schema_especialidades_adversario"] != SCHEMA or data["natureza"] != "reservado":
        raise AdversaryValidationError(f"{adversary_id}: metadados das especialidades inválidos")
    if data["adversario_id"] != adversary_id:
        raise AdversaryValidationError(f"{adversary_id}: fragmento de especialidades aponta outro adversário")
    specialties = _map(data["especialidades"], f"{adversary_id}.especialidades")
    declared = set(sheet["especialidades"]["ids"])
    if set(specialties) != declared:
        raise AdversaryValidationError(f"{adversary_id}: ids de especialidade divergem do fragmento-base")
    for specialty_id, raw_specialty in specialties.items():
        label = f"{adversary_id}.especialidades.{specialty_id}"
        specialty = _map(raw_specialty, label)
        if set(specialty) != {"nome", "dominio", "objetivo", "procedimentos", "contrajogo"}:
            raise AdversaryValidationError(f"{label} possui estrutura inesperada")
        _text(specialty["nome"], f"{label}.nome")
        _text(specialty["dominio"], f"{label}.dominio")
        _text(specialty["objetivo"], f"{label}.objetivo")
        procedures = _list(specialty["procedimentos"], f"{label}.procedimentos")
        if not procedures:
            raise AdversaryValidationError(f"{label}.procedimentos não pode ser vazio")
        procedure_ids: set[str] = set()
        for index, raw_procedure in enumerate(procedures):
            item_label = f"{label}.procedimentos[{index}]"
            procedure = _map(raw_procedure, item_label)
            if set(procedure) != {
                "id", "gatilho", "resolucao", "resultado_sucesso",
                "resultado_falha", "custo", "limite",
            }:
                raise AdversaryValidationError(f"{item_label} possui estrutura inesperada")
            procedure_id = _id(procedure["id"], f"{item_label}.id")
            if procedure_id in procedure_ids:
                raise AdversaryValidationError(f"{label}: procedimento duplicado {procedure_id}")
            procedure_ids.add(procedure_id)
            _text(procedure["gatilho"], f"{item_label}.gatilho")
            _validate_resolution(procedure["resolucao"], contract, f"{item_label}.resolucao")
            _text(procedure["resultado_sucesso"], f"{item_label}.resultado_sucesso")
            _text(procedure["resultado_falha"], f"{item_label}.resultado_falha")
            _validate_cost(procedure["custo"], resources, f"{item_label}.custo")
            _validate_limit(procedure["limite"], contract, f"{item_label}.limite")
        _strings(specialty["contrajogo"], f"{label}.contrajogo", allow_empty=False)
    return data


def _load_base(
    repo: Path, query: str
) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    contract = load_contract(repo)
    index = load_index(repo, contract)
    adversary_id, meta = resolve_adversary(index, query)
    base_rel, base_path = _repo_path(repo, meta["arquivo"], f"{adversary_id}.arquivo", SHEETS_DIR)
    if not base_path.is_file():
        raise AdversaryValidationError(f"{adversary_id}: fragmento inexistente: {base_rel}")
    if base_path.stat().st_size > contract["orcamento"]["fragmento_base_max_bytes"]:
        raise AdversaryValidationError(f"{adversary_id}: ficha-base excede o orçamento")
    sheet = validate_adversary_data(repo, adversary_id, meta, _load_yaml(base_path), contract)
    return adversary_id, meta, sheet, contract


def _load_with_specialties(
    repo: Path, query: str
) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    adversary_id, meta, sheet, contract = _load_base(repo, query)
    detail_rel, detail_path = _repo_path(
        repo, meta["especialidades_arquivo"], f"{adversary_id}.especialidades_arquivo", SPECIALTIES_DIR
    )
    if not detail_path.is_file():
        raise AdversaryValidationError(f"{adversary_id}: fragmento inexistente: {detail_rel}")
    if detail_path.stat().st_size > contract["orcamento"]["fragmento_especialidades_max_bytes"]:
        raise AdversaryValidationError(f"{adversary_id}: especialidades excedem o orçamento")
    resources = {item["id"] for item in sheet["recursos"]}
    specialties = validate_specialties_data(
        adversary_id, sheet, _load_yaml(detail_path), contract, resources
    )
    return adversary_id, meta, sheet, specialties, contract


def load_adversary(repo: Path, query: str) -> dict[str, Any]:
    adversary_id, meta, sheet, contract = _load_base(repo, query)
    result = {
        "schema_consulta_adversario": 1,
        "adversario_id": adversary_id,
        "fontes_lidas": [
            CONTRACT_PATH.as_posix(), INDEX_PATH.as_posix(), CAMPAIGN_PATH.as_posix(), meta["arquivo"]
        ],
        "resultado": sheet,
    }
    if len(_dump(result).encode("utf-8")) > contract["orcamento"]["consulta_dirigida_max_bytes"]:
        raise AdversaryValidationError(f"consulta de {adversary_id} excede o teto L2")
    return result


def load_specialty(repo: Path, query: str, specialty_id: str) -> dict[str, Any]:
    adversary_id, meta, _, specialties, contract = _load_with_specialties(repo, query)
    specialty_id = _id(specialty_id, "especialidade-id")
    try:
        specialty = specialties["especialidades"][specialty_id]
    except KeyError as exc:
        raise AdversaryValidationError(
            f"especialidade não encontrada para {adversary_id}: {specialty_id}"
        ) from exc
    result = {
        "schema_consulta_especialidade_adversario": 1,
        "adversario_id": adversary_id,
        "especialidade_id": specialty_id,
        "fontes_lidas": [
            CONTRACT_PATH.as_posix(), INDEX_PATH.as_posix(), CAMPAIGN_PATH.as_posix(),
            meta["arquivo"], meta["especialidades_arquivo"]
        ],
        "resultado": specialty,
    }
    if len(_dump(result).encode("utf-8")) > contract["orcamento"]["consulta_dirigida_max_bytes"]:
        raise AdversaryValidationError(
            f"consulta da especialidade {adversary_id}.{specialty_id} excede o teto L2"
        )
    return result


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    quantity = 0
    try:
        contract = load_contract(repo)
        if load_campaign_ruleset(repo) != contract["ruleset_obrigatorio"]:
            raise AdversaryValidationError("ruleset ativo diverge do contrato de adversários")
        index = load_index(repo, contract)
        quantity = len(index["adversarios"])
        for adversary_id in index["adversarios"]:
            try:
                base = load_adversary(repo, adversary_id)
                for specialty_id in base["resultado"]["especialidades"]["ids"]:
                    load_specialty(repo, adversary_id, specialty_id)
            except AdversaryValidationError as exc:
                errors.append(str(exc))
    except AdversaryValidationError as exc:
        errors.append(str(exc))
    return {"ok": not errors, "quantidade": quantity, "erros": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    subparsers = parser.add_subparsers(dest="comando", required=True)
    show = subparsers.add_parser("mostrar", help="mostra um bloco mecânico dirigido")
    show.add_argument("consulta")
    specialty = subparsers.add_parser("especialidade", help="mostra uma especialidade não combativa")
    specialty.add_argument("consulta")
    specialty.add_argument("especialidade_id")
    subparsers.add_parser("validar", help="valida todo o registro em manutenção/CI")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.comando == "mostrar":
            result = load_adversary(repo, args.consulta)
        elif args.comando == "especialidade":
            result = load_specialty(repo, args.consulta, args.especialidade_id)
        else:
            result = validate_repo(repo)
            if not result["ok"]:
                print(_dump(result), end="")
                return 1
        print(_dump(result), end="")
        return 0
    except AdversaryValidationError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
