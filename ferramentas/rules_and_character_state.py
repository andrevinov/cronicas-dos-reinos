#!/usr/bin/env python3
"""Fachada pública v2 de regras, rolagens e estado de Ren.

A fachada agrega autoridades existentes sem criar outro RNG, writer ou estado.
No hot path ela apenas publica, depois do writer, um recibo compacto do contrato
que já foi validado antes da persistência.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from _module_facade import attach_coverage, combine_checks
import catalogo_regras
import ficha_ren
import mecanica_cronica
import mecanica_dnd_5_5e as dnd
import tempo_transacional

FACADE_SCHEMA = 2
RECEIPT_SCHEMA = 1
MODULE_ID = "rules_and_character_state"
CAPABILITIES = ("rules_resolution", "roll_execution", "character_time_state")
LEGACY_COMPONENTS = (
    "catalogo_regras",
    "mecanica_cronica",
    "mecanica_dnd_5_5e",
    "dados",
    "ficha_ren",
    "tempo_transacional",
    "transacoes",
)
RECEIPT_KEY = "regras_estado_personagem"
MAX_RECEIPT_BYTES = 1024

CHARACTER_STATE_ROOTS = (
    "recursos",
    "personagem",
    "equipamento_em_posse",
    "efeitos_temporarios",
)


class RulesAndCharacterStateError(ValueError):
    """Contrato inválido da fachada mecânica v2."""


class _FixedRng:
    def __init__(self, *values: int):
        self.values = list(values)
        self.calls = 0

    def randint(self, low: int, high: int) -> int:
        if self.calls >= len(self.values):
            raise AssertionError("RNG sintético recebeu chamada inesperada")
        value = self.values[self.calls]
        self.calls += 1
        if not low <= value <= high:
            raise AssertionError(f"valor sintético fora da faixa: {value}")
        return value


class _ForbiddenRng:
    def __init__(self):
        self.calls = 0

    def randint(self, _low: int, _high: int) -> int:
        self.calls += 1
        raise AssertionError("entrada inválida alcançou o RNG")


def _size(value: Any) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    )


def _load_map(repo: Path, relative: str) -> dict[str, Any]:
    path = repo / relative
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise RulesAndCharacterStateError(f"não foi possível ler {relative}: {exc}") from exc
    if not isinstance(value, dict):
        raise RulesAndCharacterStateError(f"{relative} precisa ser mapa YAML")
    return value


def _rule_catalog_check(repo: Path) -> dict[str, Any]:
    return catalogo_regras.check(repo)


def _roll_contract_check(_repo: Path) -> dict[str, Any]:
    errors: list[str] = []

    success_rng = _FixedRng(10)
    success = dnd.perform_check(5, 15, "normal", rng=success_rng)
    if success.success is not True or success.roll.total != 15 or success_rng.calls != 1:
        errors.append("teste d20 não preservou alvo, modificador e resultado")

    failure_rng = _FixedRng(9)
    failure = dnd.perform_check(5, 15, "normal", rng=failure_rng)
    if failure.success is not False or failure.roll.total != 14 or failure_rng.calls != 1:
        errors.append("sucesso e falha não obedecem ao mesmo contrato prévio")

    critical_rng = _FixedRng(20)
    critical = dnd.perform_attack(0, 99, "normal", rng=critical_rng)
    if not critical.hit or not critical.critical or critical.automatic != "critico":
        errors.append("vinte natural deixou de preservar a resolução de ataque")

    forbidden = _ForbiddenRng()
    try:
        dnd.perform_check("5", 15, "normal", rng=forbidden)  # type: ignore[arg-type]
    except dnd.MechanicsInputError:
        pass
    else:
        errors.append("entrada inválida não falhou antes do RNG")
    if forbidden.calls:
        errors.append("entrada inválida consumiu RNG")

    return {
        "ok": not errors,
        "erros": errors,
        "ruleset": dnd.RULESET_ID,
        "rng_novo": 0,
        "resultado_pos_rolagem_mutavel": False,
    }


def state_consistency(repo: Path) -> dict[str, Any]:
    """Confere relações entre fontes vivas, sem congelar seus valores atuais."""

    errors: list[str] = []
    sheet_doc = _load_map(repo, "personagens/jogador/ficha.yaml")
    state = _load_map(repo, "estado/estado-atual.yaml")
    time_state = _load_map(repo, "estado/tempo.yaml")
    runtime = _load_map(repo, "runtime/contexto.yaml")
    try:
        sheet = ficha_ren.load(repo / "personagens/jogador/ficha.yaml")
    except ficha_ren.RenSheetError as exc:
        return {"ok": False, "erros": [str(exc)]}

    sheet_person = sheet_doc.get("personagem") or {}
    identity = sheet_doc.get("identidade") or {}
    state_person = state.get("personagem") or {}
    state_resources = state.get("recursos") or {}
    runtime_person = runtime.get("personagem") or {}
    runtime_resources = runtime.get("recursos") or {}
    state_time = state.get("tempo") or {}
    runtime_time = runtime.get("tempo") or {}

    if not all(
        isinstance(value, dict)
        for value in (
            sheet_person,
            identity,
            state_person,
            state_resources,
            runtime_person,
            runtime_resources,
            state_time,
            runtime_time,
        )
    ):
        return {"ok": False, "erros": ["fontes de ficha/estado/runtime possuem shape inválido"]}

    if state_person.get("nome") != sheet_person.get("nome"):
        errors.append("nome diverge entre ficha e estado")
    if runtime_person.get("nome") != state_person.get("nome"):
        errors.append("nome diverge entre estado e runtime")
    for field, label in (
        ("nivel", "nível"),
        ("classe", "classe"),
        ("subclasse", "subclasse"),
    ):
        if state_person.get(field) != identity.get(field):
            errors.append(f"{label} diverge entre ficha e estado")
        if runtime_person.get(field) != state_person.get(field):
            errors.append(f"{label} diverge entre estado e runtime")

    hp = state_resources.get("pontos_de_vida") or {}
    expected_hp = sheet.resources["pontos_de_vida"]
    if not isinstance(hp, dict) or {
        "atuais": hp.get("atuais"),
        "maximos": hp.get("maximos"),
    } != {
        "atuais": expected_hp["atuais"],
        "maximos": expected_hp["maximos"],
    }:
        errors.append("PV diverge entre ficha e estado")
    if runtime_resources.get("pv") != {
        "atuais": hp.get("atuais") if isinstance(hp, dict) else None,
        "maximos": hp.get("maximos") if isinstance(hp, dict) else None,
    }:
        errors.append("PV diverge entre estado e runtime")

    focus = state_resources.get("focus") or {}
    expected_focus = sheet.resources["focus"]
    if not isinstance(focus, dict) or {
        "atuais": focus.get("atuais"),
        "maximos": focus.get("maximos"),
    } != {
        "atuais": expected_focus["pontos_atuais"],
        "maximos": expected_focus["pontos_maximos"],
    }:
        errors.append("Focus diverge entre ficha e estado")
    if runtime_resources.get("focus") != {
        "atuais": focus.get("atuais") if isinstance(focus, dict) else None,
        "maximos": focus.get("maximos") if isinstance(focus, dict) else None,
    }:
        errors.append("Focus diverge entre estado e runtime")

    if state_resources.get("classe_de_armadura") != sheet.armor_class:
        errors.append("CA diverge entre ficha e estado")
    if runtime_resources.get("ca") != state_resources.get("classe_de_armadura"):
        errors.append("CA diverge entre estado e runtime")
    conditions = state_resources.get("condicoes")
    if not isinstance(conditions, list):
        errors.append("condições de Ren precisam permanecer uma lista no estado")

    canonical_date = time_state.get("data_atual")
    canonical_hour = time_state.get("hora_aproximada")
    if state_time.get("data_exata") != canonical_date:
        errors.append("data diverge entre estado atual e autoridade temporal")
    if state_time.get("hora_aproximada") != canonical_hour:
        errors.append("hora diverge entre estado atual e autoridade temporal")
    if runtime_time.get("data") != canonical_date:
        errors.append("data diverge entre tempo canônico e runtime")
    if runtime_time.get("hora_aproximada") != canonical_hour:
        errors.append("hora diverge entre tempo canônico e runtime")
    try:
        tempo_transacional.validate_atomic_delta(
            {
                "alvo": "tempo",
                "op": "instante",
                "valor": {"data": canonical_date, "hora": canonical_hour},
            }
        )
    except tempo_transacional.AtomicTimeError as exc:
        errors.append(f"instante canônico inválido: {exc}")

    return {
        "ok": not errors,
        "erros": errors,
        "fontes": [
            "personagens/jogador/ficha.yaml",
            "estado/estado-atual.yaml",
            "estado/tempo.yaml",
            "runtime/contexto.yaml",
        ],
        "valores_absolutos_congelados": False,
    }


def _transaction_contract_check(_repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    if mecanica_cronica.PROTECTED_RESOURCES != {"focus"}:
        errors.append("recursos protegidos do contrato mecânico mudaram")
    if mecanica_cronica.D20_TYPES != {"teste", "salvaguarda", "ataque"}:
        errors.append("tipos d20 do contrato mecânico mudaram")
    if mecanica_cronica.MAX_RULES > 8 or mecanica_cronica.MAX_OBLIGATIONS > 8:
        errors.append("orçamento mecânico excedeu oito regras/obrigações")
    try:
        tempo_transacional.validate_record_contract(
            [
                {
                    "alvo": "tempo",
                    "op": "instante",
                    "valor": {"data": "11 Eleasis, 1372 DR", "hora": "05:10"},
                }
            ]
        )
    except tempo_transacional.AtomicTimeError as exc:
        errors.append(f"contrato temporal atômico falhou: {exc}")
    return {
        "ok": not errors,
        "erros": errors,
        "regras_max": mecanica_cronica.MAX_RULES,
        "obrigacoes_max": mecanica_cronica.MAX_OBLIGATIONS,
        "writers_novos": 0,
        "estado_paralelo": False,
    }


def _relevant_delta(delta: Any) -> bool:
    if not isinstance(delta, dict):
        return False
    target = delta.get("alvo")
    if target in {"tempo", "ficha"}:
        return True
    if target != "estado":
        return False
    path = str(delta.get("caminho") or "")
    return any(path == root or path.startswith(root + ".") for root in CHARACTER_STATE_ROOTS)


def _delta_categories(deltas: list[Any]) -> tuple[list[str], int]:
    categories: set[str] = set()
    relevant = 0
    for delta in deltas:
        if not _relevant_delta(delta):
            continue
        relevant += 1
        target = delta.get("alvo")
        path = str(delta.get("caminho") or "")
        if target == "tempo":
            categories.add("tempo_atomico")
        elif target == "ficha":
            categories.add("ficha")
        elif path.startswith("recursos"):
            categories.add("recursos")
        elif path.startswith("efeitos_temporarios"):
            categories.add("condicoes_ou_efeitos")
        elif path.startswith("equipamento_em_posse"):
            categories.add("equipamento")
        else:
            categories.add("personagem")
    return sorted(categories), relevant


def _mechanical_counts(ticket_payload: dict[str, Any], transaction: dict[str, Any]) -> dict[str, int]:
    contract = ticket_payload.get(mecanica_cronica.TICKET_KEY)
    obligations = contract.get("obrigacoes") if isinstance(contract, dict) else []
    if not isinstance(obligations, list):
        obligations = []
    rules = contract.get("regras") if isinstance(contract, dict) else []
    if not isinstance(rules, list):
        rules = []
    resolution_block = transaction.get(mecanica_cronica.TRANSACTION_KEY)
    resolutions = resolution_block.get("resolucoes") if isinstance(resolution_block, dict) else []
    if not isinstance(resolutions, list):
        resolutions = []
    return {
        "regras": len(rules),
        "obrigacoes": len(obligations),
        "obrigacoes_d20": sum(
            isinstance(item, dict) and item.get("tipo") in mecanica_cronica.D20_TYPES
            for item in obligations
        ),
        "obrigacoes_recurso": sum(
            isinstance(item, dict) and item.get("tipo") == "gasto_recurso"
            for item in obligations
        ),
        "resolucoes": len(resolutions),
        "recursos_aplicados": sum(
            isinstance(item, dict)
            and item.get("tipo") == "gasto_recurso"
            and item.get("aplicado") is True
            for item in resolutions
        ),
    }


def _event_id(result: dict[str, Any], counts: dict[str, int], categories: list[str]) -> str:
    persisted = result.get("transacao") if isinstance(result.get("transacao"), dict) else {}
    seed = {
        "ticket_id": result.get("ticket_id"),
        "transacao_id": persisted.get("id"),
        "contagens": counts,
        "categorias": categories,
    }
    digest = hashlib.sha256(
        json.dumps(seed, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:20]
    return f"mechanics-{digest}"


def publish_conclusion(
    result: dict[str, Any],
    transaction: dict[str, Any],
    ticket_payload: dict[str, Any],
) -> dict[str, Any]:
    """Publica observação pós-writer; toda validação mutante já ocorreu antes."""

    if not all(isinstance(value, dict) for value in (result, transaction, ticket_payload)):
        raise RulesAndCharacterStateError("resultado, transação e ticket precisam ser mapas")
    counts = _mechanical_counts(ticket_payload, transaction)
    deltas = transaction.get("deltas") or []
    if not isinstance(deltas, list):
        deltas = []
    categories, relevant_deltas = _delta_categories(deltas)
    if not counts["obrigacoes"] and not relevant_deltas:
        return attach_coverage(
            result,
            module_id=MODULE_ID,
            phase="concluir",
            applicability="nao_aplicavel",
        )

    persisted = result.get("transacao") if isinstance(result.get("transacao"), dict) else {}
    replay = any(
        persisted.get(key) is True
        for key in ("ja_registrada", "reparo_parcial", "consolidada")
    )
    contract_present = counts["obrigacoes"] > 0
    receipt = {
        "schema_rules_and_character_state": RECEIPT_SCHEMA,
        "module_id": MODULE_ID,
        "evento_id": _event_id(result, counts, categories),
        "estado": "replay_sem_novo_efeito" if replay else "commit_validado",
        "correlacao": {
            "ticket_id": result.get("ticket_id"),
            "transacao_id": persisted.get("id"),
            "sessao": persisted.get("sessao"),
        },
        "contrato": {
            **counts,
            "validado_antes_do_writer": True,
        },
        "mutacoes": {
            "categorias": categories,
            "deltas_relevantes": relevant_deltas,
            "tempo_atomico": "tempo_atomico" in categories,
        },
        "commit": {
            "exactly_once": True,
            "efeito_novo": not replay,
        },
        "guardrails": {
            "player_agency": "indeterminado",
            "roll_integrity": "ok" if counts["obrigacoes_d20"] else "nao_aplicavel",
            "canonical_consistency": "ok" if contract_present or relevant_deltas else "nao_aplicavel",
        },
        "guardrails_participam_media": False,
        "escrita_canonica_pelo_modulo": False,
    }
    if _size(receipt) > MAX_RECEIPT_BYTES:
        raise RulesAndCharacterStateError(
            f"recibo mecânico excede {MAX_RECEIPT_BYTES} bytes"
        )

    out = copy.deepcopy(result)
    out[RECEIPT_KEY] = receipt
    systems = out.setdefault("sistemas_narrativos", [])
    if MODULE_ID not in systems:
        systems.append(MODULE_ID)
    return attach_coverage(
        out,
        module_id=MODULE_ID,
        phase="concluir",
        applicability="aplicavel",
    )


def check(repo: Path) -> dict[str, Any]:
    return combine_checks(
        repo,
        module_id=MODULE_ID,
        capabilities=CAPABILITIES,
        legacy_components=LEGACY_COMPONENTS,
        checks=(
            ("rules_resolution", _rule_catalog_check),
            ("roll_execution", _roll_contract_check),
            ("character_time_state", state_consistency),
            ("transactional_contract", _transaction_contract_check),
        ),
        contract={
            "source_ownership": {
                "ruleset": "campanha.yaml:sistema.ruleset",
                "rule_catalog": "regras/catalogo.yaml",
                "character_sheet": "personagens/jogador/ficha.yaml",
                "current_state": "estado/estado-atual.yaml",
                "canonical_time": "estado/tempo.yaml",
                "derived_runtime": "runtime/contexto.yaml + runtime/cena.yaml",
                "turn_writer": "runtime/eventos-pendentes.jsonl via cronica concluir",
            },
            "difficulty_changes_after_roll": False,
            "result_changes_after_roll": False,
            "focus_without_ticket_obligation": False,
            "direct_live_state_write": False,
            "guardrails_are_compensable": False,
            "additional_orchestration_calls": 0,
            "new_rng": False,
            "new_writer": False,
            "parallel_state": False,
            "telemetry_in_hot_path": False,
        },
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("cmd", choices=["check"])
    args = parser.parse_args(argv)
    result = check(args.repo.resolve())
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
