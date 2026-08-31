#!/usr/bin/env python3
"""Contrato mecânico entre ``cronica preparar`` e ``cronica concluir``.

Esta camada não rola dados e não implementa regras de D&D. Ela congela no ticket
quais regras/obrigações foram preparadas, usa ``mecanica_dnd_5_5e`` para reexecutar
a resolução determinística a partir dos dados já rolados e só então autoriza que o
writer receba deltas mecânicos. O catálogo continua responsável pela identidade das
regras e ``estado/estado-atual.yaml`` pela disponibilidade de recursos.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml

import catalogo_regras
import gate_adnd
import mecanica_dnd_5_5e as dnd

SCHEMA = 1
TICKET_KEY = "mecanica_cronica"
TRANSACTION_KEY = "mecanica"
MAX_RULES = 8
MAX_OBLIGATIONS = 8
D20_TYPES = {"teste", "salvaguarda", "ataque"}
SUPPORTED_TYPES = D20_TYPES | {"gasto_recurso"}
OUTCOMES = {
    "sucesso",
    "falha",
    "acerto",
    "erro",
    "critico",
    "falha_automatica",
    "indeterminado",
    "aplicado",
}
PROTECTED_RESOURCES = {"focus"}


class MechanicalContractError(ValueError):
    """Contrato ou resolução mecânica incompatível com o ticket."""


class MechanicalTicketStaleError(MechanicalContractError):
    """Estado mecânico mudou desde a preparação do ticket."""


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MechanicalContractError(f"{label} precisa ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise MechanicalContractError(f"{label} precisa ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MechanicalContractError(f"{label} precisa ser texto não vazio")
    return value.strip()


def _integer(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MechanicalContractError(f"{label} precisa ser inteiro")
    return value


def _optional_integer(value: Any, label: str) -> int | None:
    if value is None:
        return None
    return _integer(value, label)


def _campaign_ruleset(repo: Path) -> str:
    path = repo / "campanha.yaml"
    try:
        campaign = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return _text(campaign["sistema"]["ruleset"]["atual"], "sistema.ruleset.atual")
    except (OSError, yaml.YAMLError, KeyError, TypeError) as exc:
        raise MechanicalContractError("não foi possível determinar o ruleset atual") from exc


def _resource_state(repo: Path, resource: str) -> dict[str, int]:
    path = repo / "estado/estado-atual.yaml"
    try:
        state = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raw = state["recursos"][resource]
    except (OSError, yaml.YAMLError, KeyError, TypeError) as exc:
        raise MechanicalContractError(
            f"recurso mecânico indisponível no estado atual: {resource}"
        ) from exc
    data = _map(raw, f"recursos.{resource}")
    current = _integer(data.get("atuais"), f"recursos.{resource}.atuais")
    maximum = _integer(data.get("maximos"), f"recursos.{resource}.maximos")
    if maximum < 0 or current < 0 or current > maximum:
        raise MechanicalContractError(f"recurso {resource} possui faixa inválida")
    return {"atuais": current, "maximos": maximum}


def _resolve_catalog_rule(document: dict[str, Any], value: Any, label: str) -> str:
    term = _text(value, label)
    rule, candidates = catalogo_regras.resolve_rule(document, term)
    if rule is None:
        hint = f"; candidatos={candidates}" if candidates else ""
        raise MechanicalContractError(f"regra não catalogada: {term!r}{hint}")
    return str(rule["id"])


def _normalize_effects(value: Any, obligation_id: str) -> dict[str, list[dict[str, Any]]]:
    if value is None:
        return {}
    raw = _map(value, f"obrigacoes.{obligation_id}.efeitos")
    result: dict[str, list[dict[str, Any]]] = {}
    for outcome, deltas in raw.items():
        if outcome not in OUTCOMES:
            raise MechanicalContractError(
                f"obrigação {obligation_id}: resultado de efeito desconhecido: {outcome}"
            )
        items = _list(deltas, f"obrigacoes.{obligation_id}.efeitos.{outcome}")
        normalized: list[dict[str, Any]] = []
        for index, delta in enumerate(items):
            normalized.append(
                copy.deepcopy(_map(delta, f"efeito {obligation_id}/{outcome}[{index}]"))
            )
        result[outcome] = normalized
    return result


def _normalize_d20(obligation: dict[str, Any], obligation_id: str, rule_id: str) -> dict[str, Any]:
    kind = str(obligation["tipo"])
    bonus = _integer(obligation.get("bonus", 0), f"obrigacoes.{obligation_id}.bonus")
    target = _optional_integer(obligation.get("alvo"), f"obrigacoes.{obligation_id}.alvo")
    mode_raw = obligation.get("modo", "normal")
    try:
        mode = dnd.validate_roll_mode(mode_raw)
    except dnd.MechanicsInputError as exc:
        raise MechanicalContractError(str(exc)) from exc
    return {
        "id": obligation_id,
        "tipo": kind,
        "regra": rule_id,
        "bonus": bonus,
        "alvo": target,
        "modo": mode,
        "efeitos": _normalize_effects(obligation.get("efeitos"), obligation_id),
    }


def _normalize_resource(
    repo: Path,
    obligation: dict[str, Any],
    obligation_id: str,
    rule_id: str,
) -> dict[str, Any]:
    resource = _text(obligation.get("recurso"), f"obrigacoes.{obligation_id}.recurso").lower()
    if resource not in PROTECTED_RESOURCES:
        raise MechanicalContractError(
            f"obrigação {obligation_id}: recurso protegido desconhecido: {resource}"
        )
    cost = _integer(obligation.get("custo"), f"obrigacoes.{obligation_id}.custo")
    if cost <= 0:
        raise MechanicalContractError(f"obrigação {obligation_id}: custo precisa ser positivo")
    return {
        "id": obligation_id,
        "tipo": "gasto_recurso",
        "regra": rule_id,
        "recurso": resource,
        "custo": cost,
        "delta_esperado": {
            "alvo": "estado",
            "op": "inc",
            "caminho": f"recursos.{resource}.atuais",
            "valor": -cost,
        },
        "efeitos": _normalize_effects(obligation.get("efeitos"), obligation_id),
        "snapshot": _resource_state(repo, resource),
    }


def normalize_spec(repo: Path, spec: dict[str, Any] | None) -> dict[str, Any] | None:
    """Valida a intenção mecânica e congela catálogo + recursos sem consumir RNG."""
    if spec is None:
        return None
    raw = _map(spec, "mecanica")
    if not raw:
        return None
    extra = set(raw) - {"regras", "obrigacoes", "proveniencia"}
    if extra:
        raise MechanicalContractError(f"campos mecânicos desconhecidos: {sorted(extra)}")

    provenance = None
    if raw.get("proveniencia") is not None:
        try:
            provenance = gate_adnd.validate_runtime_provenance(
                repo, raw["proveniencia"], raw
            )
        except gate_adnd.ADNDGateError as exc:
            raise MechanicalContractError(f"gate AD&D: {exc}") from exc

    try:
        document = catalogo_regras.load_catalog(repo)
    except catalogo_regras.RuleCatalogError as exc:
        raise MechanicalContractError(str(exc)) from exc

    rule_terms = _list(raw.get("regras", []), "mecanica.regras")
    if not rule_terms or len(rule_terms) > MAX_RULES:
        raise MechanicalContractError(f"mecanica.regras precisa ter entre 1 e {MAX_RULES} itens")
    rules: list[str] = []
    for index, term in enumerate(rule_terms):
        rule_id = _resolve_catalog_rule(document, term, f"mecanica.regras[{index}]")
        if rule_id not in rules:
            rules.append(rule_id)
    if len(rules) != len(rule_terms):
        raise MechanicalContractError("mecanica.regras contém regra duplicada após resolução de aliases")

    obligations_raw = _list(raw.get("obrigacoes", []), "mecanica.obrigacoes")
    if not obligations_raw or len(obligations_raw) > MAX_OBLIGATIONS:
        raise MechanicalContractError(
            f"mecanica.obrigacoes precisa ter entre 1 e {MAX_OBLIGATIONS} itens"
        )
    obligations: list[dict[str, Any]] = []
    ids: set[str] = set()
    spend_by_resource: dict[str, int] = {}
    snapshot_by_resource: dict[str, dict[str, int]] = {}

    for index, item in enumerate(obligations_raw):
        obligation = _map(item, f"mecanica.obrigacoes[{index}]")
        obligation_id = _text(obligation.get("id"), f"mecanica.obrigacoes[{index}].id")
        if obligation_id in ids:
            raise MechanicalContractError(f"id de obrigação duplicado: {obligation_id}")
        ids.add(obligation_id)
        kind = _text(obligation.get("tipo"), f"obrigacoes.{obligation_id}.tipo")
        if kind not in SUPPORTED_TYPES:
            raise MechanicalContractError(f"obrigação {obligation_id}: tipo desconhecido: {kind}")
        rule_id = _resolve_catalog_rule(document, obligation.get("regra"), f"obrigacoes.{obligation_id}.regra")
        if rule_id not in rules:
            raise MechanicalContractError(
                f"obrigação {obligation_id}: regra {rule_id} não foi declarada em mecanica.regras"
            )
        if kind in D20_TYPES:
            normalized = _normalize_d20(obligation, obligation_id, rule_id)
        else:
            normalized = _normalize_resource(repo, obligation, obligation_id, rule_id)
            resource = normalized["recurso"]
            spend_by_resource[resource] = spend_by_resource.get(resource, 0) + normalized["custo"]
            snapshot_by_resource[resource] = dict(normalized["snapshot"])
        obligations.append(normalized)

    for resource, spent in spend_by_resource.items():
        available = snapshot_by_resource[resource]["atuais"]
        if spent > available:
            raise MechanicalContractError(
                f"recurso insuficiente: {resource} tem {available}, obrigações exigem {spent}"
            )
        if available - spent < 0:
            raise MechanicalContractError(f"gasto deixaria {resource} negativo")

    contract = {
        "schema_mecanica_cronica": SCHEMA,
        "ruleset": _campaign_ruleset(repo),
        "regras": rules,
        "obrigacoes": obligations,
        "snapshot_recursos": snapshot_by_resource,
    }
    if provenance is not None:
        contract["proveniencia"] = provenance
    return contract


def public_summary(contract: dict[str, Any]) -> dict[str, Any]:
    summary = {
        "ruleset": contract["ruleset"],
        "regras": list(contract["regras"]),
        "obrigacoes": [
            {
                "id": item["id"],
                "tipo": item["tipo"],
                "regra": item["regra"],
                **({"recurso": item["recurso"], "custo": item["custo"]} if item["tipo"] == "gasto_recurso" else {}),
            }
            for item in contract["obrigacoes"]
        ],
        "resolucao": "registrar uma resolução por obrigação em transacao.mecanica.resolucoes",
    }
    provenance = contract.get("proveniencia")
    if isinstance(provenance, dict):
        summary["proveniencia"] = {
            "edicao_origem": provenance.get("edicao_origem"),
            "adaptado_para": provenance.get("adaptado_para"),
            "fonte_mecanica": provenance.get("fonte_mecanica"),
            **({"decisao": provenance["decisao"]} if provenance.get("decisao") else {}),
            **({"fallback_2014": provenance["fallback_2014"]} if provenance.get("fallback_2014") else {}),
        }
    return summary


def attach_to_prepare(
    repo: Path,
    result: dict[str, Any],
    spec: dict[str, Any] | None,
    *,
    decode_ticket,
    encode_ticket,
    max_ticket_chars: int,
    max_output_bytes: int,
) -> dict[str, Any]:
    """Anexa contrato ao ticket; o caminho sem mecânica retorna o mesmo objeto."""
    contract = normalize_spec(repo, spec)
    if contract is None:
        return result
    token = result.get("ticket")
    if not isinstance(token, str):
        raise MechanicalContractError("preparação não retornou ticket para anexar mecânica")
    payload = copy.deepcopy(decode_ticket(token))
    payload[TICKET_KEY] = contract
    new_token, new_id = encode_ticket(payload)
    if len(new_token) > max_ticket_chars:
        raise MechanicalContractError(
            f"ticket mecânico excede orçamento: {len(new_token)} > {max_ticket_chars} caracteres"
        )
    decorated = copy.deepcopy(result)
    decorated["ticket"] = new_token
    decorated["ticket_id"] = new_id
    decorated["mecanica"] = public_summary(contract)
    conclusion = decorated.get("contrato_conclusao")
    if isinstance(conclusion, dict):
        fields = conclusion.setdefault("campos", {})
        if isinstance(fields, dict):
            fields[TRANSACTION_KEY] = {
                "resolucoes": "uma resolução estruturada por obrigação mecânica do ticket"
            }
    size = len(yaml.safe_dump(decorated, allow_unicode=True, sort_keys=False).encode("utf-8"))
    if size > max_output_bytes:
        raise MechanicalContractError(
            f"preparação mecânica excede orçamento: {size} > {max_output_bytes} bytes"
        )
    return decorated


def _ticket_contract(payload: dict[str, Any]) -> dict[str, Any] | None:
    raw = payload.get(TICKET_KEY)
    if raw is None:
        return None
    contract = _map(raw, f"ticket.{TICKET_KEY}")
    if contract.get("schema_mecanica_cronica") != SCHEMA:
        raise MechanicalContractError("schema mecânico do ticket é inválido")
    for key in ("ruleset", "regras", "obrigacoes", "snapshot_recursos"):
        if key not in contract:
            raise MechanicalContractError(f"ticket mecânico sem campo obrigatório: {key}")
    return contract


def revalidate_ticket(repo: Path, payload: dict[str, Any]) -> dict[str, Any] | None:
    contract = _ticket_contract(payload)
    if contract is None:
        return None
    current_ruleset = _campaign_ruleset(repo)
    if contract.get("ruleset") != current_ruleset:
        raise MechanicalTicketStaleError(
            "ticket mecânico obsoleto: o ruleset mudou; execute cronica preparar novamente"
        )
    snapshots = _map(contract.get("snapshot_recursos"), "ticket.snapshot_recursos")
    for resource, expected_raw in snapshots.items():
        expected = _map(expected_raw, f"ticket.snapshot_recursos.{resource}")
        current = _resource_state(repo, str(resource))
        if current != expected:
            raise MechanicalTicketStaleError(
                f"ticket mecânico obsoleto: recurso {resource} mudou desde preparar; execute cronica preparar novamente"
            )
    return contract


class _ReplayRng:
    def __init__(self, values: list[int]):
        self._values = list(values)
        self._index = 0

    def randint(self, low: int, high: int) -> int:
        if self._index >= len(self._values):
            raise MechanicalContractError("resolução não contém dados suficientes")
        value = self._values[self._index]
        self._index += 1
        if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
            raise MechanicalContractError(f"resultado de dado fora da faixa {low}..{high}: {value!r}")
        return value

    def exhausted(self) -> bool:
        return self._index == len(self._values)


def _expected_outcome(kind: str, resolved: Any) -> str:
    if kind in {"teste", "salvaguarda"}:
        if resolved.success is None:
            return "indeterminado"
        return "sucesso" if resolved.success else "falha"
    if resolved.automatic == "falha":
        return "falha_automatica"
    if resolved.critical:
        return "critico"
    if resolved.hit is None:
        return "indeterminado"
    return "acerto" if resolved.hit else "erro"


def _validate_d20_resolution(obligation: dict[str, Any], resolution: dict[str, Any]) -> str:
    rolls = _list(resolution.get("rolagens"), f"resolucao.{obligation['id']}.rolagens")
    values = [_integer(value, f"resolucao.{obligation['id']}.rolagens") for value in rolls]
    replay = _ReplayRng(values)
    kind = obligation["tipo"]
    kwargs = {
        "bonus": obligation["bonus"],
        "target": obligation["alvo"],
        "mode": obligation["modo"],
        "rng": replay,
    }
    try:
        if kind == "teste":
            resolved = dnd.perform_check(**kwargs)
        elif kind == "salvaguarda":
            resolved = dnd.perform_save(**kwargs)
        else:
            resolved = dnd.perform_attack(
                obligation["bonus"], obligation["alvo"], obligation["modo"], rng=replay
            )
    except dnd.MechanicsInputError as exc:
        raise MechanicalContractError(str(exc)) from exc
    if not replay.exhausted():
        raise MechanicalContractError(f"resolução {obligation['id']} contém dados excedentes")
    chosen = _integer(resolution.get("escolhido"), f"resolucao.{obligation['id']}.escolhido")
    total = _integer(resolution.get("total"), f"resolucao.{obligation['id']}.total")
    if resolved.roll.chosen != chosen or resolved.roll.total != total:
        raise MechanicalContractError(
            f"resolução {obligation['id']} diverge da primitiva mecânica do ruleset"
        )
    expected = _expected_outcome(kind, resolved)
    actual = _text(resolution.get("resultado"), f"resolucao.{obligation['id']}.resultado")
    if actual != expected:
        raise MechanicalContractError(
            f"resolução {obligation['id']} incompatível: informado={actual}, esperado={expected}"
        )
    return expected


def _delta_key(delta: dict[str, Any]) -> str:
    return json.dumps(
        {key: delta.get(key) for key in ("alvo", "op", "caminho", "valor")},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _transaction_deltas(transaction: dict[str, Any]) -> list[dict[str, Any]]:
    raw = transaction.get("deltas", [])
    items = _list(raw, "transacao.deltas")
    return [_map(item, f"transacao.deltas[{index}]") for index, item in enumerate(items)]


def _protected_spend(delta: dict[str, Any]) -> tuple[str, int] | None:
    if delta.get("alvo") not in {"estado", "ficha"} or delta.get("op") != "inc":
        return None
    path = str(delta.get("caminho") or "")
    for resource in PROTECTED_RESOURCES:
        if path == f"recursos.{resource}.atuais":
            value = delta.get("valor")
            if isinstance(value, int) and not isinstance(value, bool) and value < 0:
                return resource, -value
    return None


def _validate_effects(obligation: dict[str, Any], outcome: str, deltas: list[dict[str, Any]]) -> None:
    effects = _map(obligation.get("efeitos", {}), f"obrigacao.{obligation['id']}.efeitos")
    if not effects:
        return
    expected = {_delta_key(item) for item in effects.get(outcome, [])}
    declared = {_delta_key(item) for items in effects.values() for item in items}
    actual = {_delta_key(delta) for delta in deltas if _delta_key(delta) in declared}
    if actual != expected:
        raise MechanicalContractError(
            f"consequência mecânica incompatível com resolução {obligation['id']}: esperado={sorted(expected)}, recebido={sorted(actual)}"
        )


def _validate_resource_resolution(
    obligation: dict[str, Any], resolution: dict[str, Any], deltas: list[dict[str, Any]]
) -> str:
    if resolution.get("aplicado") is not True:
        raise MechanicalContractError(f"gasto {obligation['id']} precisa declarar aplicado=true")
    expected_key = _delta_key(_map(obligation["delta_esperado"], "delta_esperado"))
    matches = sum(1 for delta in deltas if _delta_key(delta) == expected_key)
    if matches != 1:
        raise MechanicalContractError(
            f"gasto {obligation['id']} exige exatamente um delta de recurso compatível"
        )
    _validate_effects(obligation, "aplicado", deltas)
    return "aplicado"


def validate_transaction(
    repo: Path,
    payload: dict[str, Any],
    transaction: dict[str, Any],
) -> dict[str, Any]:
    """Valida causa mecânica antes de qualquer escrita e remove envelope reservado."""
    contract = revalidate_ticket(repo, payload)
    deltas = _transaction_deltas(transaction)
    block_raw = transaction.get(TRANSACTION_KEY)

    if contract is None:
        if block_raw not in (None, {}):
            raise MechanicalContractError("transação traz resolução mecânica sem obrigação no ticket")
        for delta in deltas:
            if _protected_spend(delta) is not None:
                raise MechanicalContractError(
                    "gasto de Focus exige obrigação mecânica preparada no ticket"
                )
        return transaction

    block = _map(block_raw, "transacao.mecanica")
    if set(block) != {"resolucoes"}:
        raise MechanicalContractError("transacao.mecanica aceita somente o campo resolucoes")
    resolutions_raw = _list(block.get("resolucoes"), "transacao.mecanica.resolucoes")
    resolutions: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(resolutions_raw):
        resolution = _map(item, f"transacao.mecanica.resolucoes[{index}]")
        obligation_id = _text(resolution.get("obrigacao_id"), "resolucao.obrigacao_id")
        if obligation_id in resolutions:
            raise MechanicalContractError(f"resolução duplicada: {obligation_id}")
        resolutions[obligation_id] = resolution

    obligations = _list(contract.get("obrigacoes"), "ticket.mecanica.obrigacoes")
    expected_ids = {str(item.get("id")) for item in obligations}
    if set(resolutions) != expected_ids:
        raise MechanicalContractError(
            f"ticket/resolução incompatível: esperadas={sorted(expected_ids)}, recebidas={sorted(resolutions)}"
        )

    allowed_spend: dict[str, int] = {}
    for raw_obligation in obligations:
        obligation = _map(raw_obligation, "ticket.obrigacao")
        obligation_id = str(obligation["id"])
        resolution = resolutions[obligation_id]
        kind = str(obligation["tipo"])
        if resolution.get("tipo") != kind:
            raise MechanicalContractError(
                f"resolução {obligation_id} usa tipo {resolution.get('tipo')!r}, esperado {kind!r}"
            )
        if kind in D20_TYPES:
            outcome = _validate_d20_resolution(obligation, resolution)
            _validate_effects(obligation, outcome, deltas)
        else:
            _validate_resource_resolution(obligation, resolution, deltas)
            resource = str(obligation["recurso"])
            allowed_spend[resource] = allowed_spend.get(resource, 0) + int(obligation["custo"])

    actual_spend: dict[str, int] = {}
    for delta in deltas:
        spend = _protected_spend(delta)
        if spend is None:
            continue
        resource, amount = spend
        actual_spend[resource] = actual_spend.get(resource, 0) + amount
    if actual_spend != allowed_spend:
        raise MechanicalContractError(
            f"gasto mecânico diverge das obrigações: autorizado={allowed_spend}, deltas={actual_spend}"
        )
    for resource, amount in allowed_spend.items():
        current = _resource_state(repo, resource)["atuais"]
        if current - amount < 0:
            raise MechanicalContractError(f"gasto deixaria {resource} negativo")

    clean = copy.deepcopy(transaction)
    clean.pop(TRANSACTION_KEY, None)
    return clean
