#!/usr/bin/env python3
"""Adaptador v2 do gate raro de sidequests.

Preserva a orquestração existente de `interacoes_mundo.encounter_event`: bloqueios,
perfil, necessidade, persistência e orçamento continuam em uma única implementação.
Este módulo intercepta somente o sorteio 8:2 já existente e pode promover a ficha
`nada` corrente conforme a Adventure Drought Pressure, sem reroll ou reset.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import yaml

import interacoes_mundo as integration
import oportunidades
import pressao_aventura

GATE_VERSION = 2
PROMOTION_ORDER = "sha256_seed_token"
EXPECTED_PROMOTIONS = {0: 0, 1: 1, 2: 2, 3: 3}
MAX_PROMOTIONS = 3

# Capturado antes de `cena_mundo.py` instalar este adaptador como porta preferencial.
_BASE_ENCOUNTER_EVENT = integration.encounter_event
_PRESSURE_CACHE: dict[tuple[str, tuple[Any, ...]], dict[str, Any]] = {}


class SidequestGateV2Error(ValueError):
    """Erro de contrato do Side Quest Gate v2."""


def _contract(index: dict[str, Any]) -> dict[str, Any]:
    gate = index.get("gate")
    if not isinstance(gate, dict):
        raise SidequestGateV2Error("gate de oportunidades ausente")
    version = gate.get("versao", 1)
    if version == 1:
        return {
            "versao": 1,
            "promocoes_nada_por_nivel": {0: 0, 1: 0, 2: 0, 3: 0},
            "fonte": None,
        }
    if version != GATE_VERSION:
        raise SidequestGateV2Error(f"versão de gate desconhecida: {version}")

    pressure = gate.get("pressao_aventura")
    if not isinstance(pressure, dict):
        raise SidequestGateV2Error("gate v2 exige pressao_aventura")
    if pressure.get("origem") != "adventure_drought_pressure":
        raise SidequestGateV2Error("origem da pressão do gate v2 inválida")
    if pressure.get("fonte") != pressao_aventura.MICROEVENT_STATE.as_posix():
        raise SidequestGateV2Error("fonte da pressão do gate v2 inválida")
    if pressure.get("ordenacao_promovidos") != PROMOTION_ORDER:
        raise SidequestGateV2Error("ordenação de promoção do gate v2 inválida")

    raw = pressure.get("promocoes_nada_por_nivel")
    if not isinstance(raw, dict):
        raise SidequestGateV2Error("promocoes_nada_por_nivel deve ser mapa")
    promotions: dict[int, int] = {}
    for level in range(4):
        value = raw.get(level)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise SidequestGateV2Error(
                f"promocoes_nada_por_nivel.{level} deve ser inteiro >= 0"
            )
        promotions[level] = value
    if promotions != EXPECTED_PROMOTIONS:
        raise SidequestGateV2Error(
            f"promoções do gate v2 divergentes: esperado={EXPECTED_PROMOTIONS}"
        )
    if max(promotions.values()) > MAX_PROMOTIONS:
        raise SidequestGateV2Error("gate v2 promove fichas demais")

    rules = index.get("regras") or {}
    for key in (
        "pressao_aventura_modula_gate",
        "pressao_nao_fura_orcamento",
        "pressao_nao_rerrola",
    ):
        if rules.get(key) is not True:
            raise SidequestGateV2Error(f"regras.{key} deve permanecer true")
    return {
        "versao": GATE_VERSION,
        "promocoes_nada_por_nivel": promotions,
        "fonte": pressure["fonte"],
    }


def promoted_nada_tokens(index: dict[str, Any], level: int) -> list[str]:
    contract = _contract(index)
    if level not in {0, 1, 2, 3}:
        raise SidequestGateV2Error(f"nível de pressão inválido: {level}")
    count = contract["promocoes_nada_por_nivel"][level]
    if not count:
        return []
    nada = sorted(
        item["id"]
        for item in index["gate"]["fichas"]
        if item["resultado"] == "nada"
    )
    ordered = sorted(
        nada,
        key=lambda token: hashlib.sha256(
            f"{index['_seed']}|sidequest-gate-v2-pressure|{token}".encode("utf-8")
        ).hexdigest(),
    )
    return ordered[:count]


def _pressure_signature(repo: Path) -> tuple[Any, ...]:
    path = repo / pressao_aventura.MICROEVENT_STATE
    if not path.parent.exists():
        return ("camada_ausente",)
    if not path.is_file():
        return ("camada_parcial",)
    stat = path.stat()
    return ("arquivo", stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)


def pressure_for_gate(repo: Path) -> dict[str, Any]:
    """Lê no máximo uma vez a mesma versão do estado de pressão por processo."""
    repo = repo.resolve()
    signature = _pressure_signature(repo)
    key = (str(repo), signature)
    cached = _PRESSURE_CACHE.get(key)
    if cached is not None:
        return copy.deepcopy(cached)
    try:
        result = pressao_aventura.status_for_gate(repo)
    except pressao_aventura.AdventurePressureError as exc:
        raise SidequestGateV2Error(str(exc)) from exc
    for old in [item for item in _PRESSURE_CACHE if item[0] == str(repo)]:
        _PRESSURE_CACHE.pop(old, None)
    _PRESSURE_CACHE[key] = copy.deepcopy(result)
    return result


def draw_gate_v2(
    repo: Path,
    state: dict[str, Any],
    index: dict[str, Any],
    *,
    base_draw=None,
) -> dict[str, Any]:
    """Consome exatamente uma ficha-base e opcionalmente promove essa mesma ficha."""
    contract = _contract(index)
    draw = base_draw or oportunidades.draw_gate
    token, base = draw(state, index)
    result = {
        "versao": contract["versao"],
        "ficha": token,
        "resultado_base": base,
        "resultado": base,
        "promovido_por_pressao": False,
        "pressao_consultada": False,
        "fontes_lidas": [],
    }
    if contract["versao"] != GATE_VERSION or base == "oportunidade":
        return result

    pressure_result = pressure_for_gate(repo)
    pressure = pressure_result["pressao_aventura"]
    promoted = token in promoted_nada_tokens(index, int(pressure["nivel"]))
    result.update(
        {
            "resultado": "oportunidade" if promoted else "nada",
            "promovido_por_pressao": promoted,
            "pressao_consultada": True,
            "pressao_aventura": {
                "nivel": pressure["nivel"],
                "nome": pressure["nome"],
                "cenas_secas_consecutivas": pressure["cenas_secas_consecutivas"],
                "configurada": bool(pressure_result.get("configurado")),
            },
            "fontes_lidas": list(pressure_result.get("fontes_lidas") or []),
        }
    )
    return result


def _provenance(gate: dict[str, Any]) -> dict[str, Any]:
    value = {
        "versao": gate["versao"],
        "ficha": gate["ficha"],
        "resultado_base": gate["resultado_base"],
        "resultado": gate["resultado"],
        "promovido_por_pressao": gate["promovido_por_pressao"],
    }
    if isinstance(gate.get("pressao_aventura"), dict):
        value["pressao_aventura"] = copy.deepcopy(gate["pressao_aventura"])
    return value


@contextmanager
def _adapt_draw(repo: Path) -> Iterator[dict[str, Any]]:
    """Adapta só `draw_gate`; toda a orquestração continua em interacoes_mundo."""
    original = oportunidades.draw_gate
    captured: dict[str, Any] = {}

    def draw(state: dict[str, Any], index: dict[str, Any]) -> tuple[str, str]:
        try:
            gate = draw_gate_v2(repo, state, index, base_draw=original)
        except SidequestGateV2Error as exc:
            raise oportunidades.OpportunityError(str(exc)) from exc
        captured.clear()
        captured.update(gate)
        return gate["ficha"], gate["resultado"]

    oportunidades.draw_gate = draw
    try:
        yield captured
    finally:
        oportunidades.draw_gate = original


def encounter_event(
    repo: Path,
    npc_id: str,
    *,
    now=None,
    encounter_id: str | None = None,
) -> dict[str, Any]:
    """Executa o encontro existente com somente o sorteio adaptado para v2."""
    try:
        index = oportunidades.load_index(repo)
        _contract(index)
    except (oportunidades.OpportunityError, SidequestGateV2Error) as exc:
        raise integration.IntegrationError(str(exc)) from exc

    with _adapt_draw(repo) as gate:
        result = _BASE_ENCOUNTER_EVENT(
            repo,
            npc_id,
            now=now,
            encounter_id=encounter_id,
        )

    if not gate:
        return result

    provenance = _provenance(gate)
    result = copy.deepcopy(result)
    result["gate_v2"] = provenance
    result["fontes_lidas"] = list(
        dict.fromkeys([*(result.get("fontes_lidas") or []), *(gate.get("fontes_lidas") or [])])
    )
    if result.get("resultado") == "avaliar_sidequest":
        result["motivo"] = (
            "gate_v2_promovido_por_pressao"
            if gate["promovido_por_pressao"]
            else "gate_oportunidade_base"
        )
        result["instrucao"] = (
            "Avaliar a semente contra o cânone atual. Pressão só pode abrir a avaliação; "
            "só oferecer após decisão explícita. Potencial não é fala nem missão."
        )
    return result


def check(repo: Path) -> dict[str, Any]:
    try:
        index = oportunidades.load_index(repo)
        contract = _contract(index)
        validation = oportunidades.validate_repo(repo)
        pressure = pressao_aventura.status_for_gate(repo)
    except (
        oportunidades.OpportunityError,
        SidequestGateV2Error,
        pressao_aventura.AdventurePressureError,
    ) as exc:
        return {"ok": False, "erros": [str(exc)]}
    errors = list(validation.get("erros") or [])
    base_results = [item["resultado"] for item in index["gate"]["fichas"]]
    if base_results.count("nada") != 8 or base_results.count("oportunidade") != 2:
        errors.append("gate-base deixou de ser 8 nada : 2 oportunidade")
    return {
        "ok": not errors,
        "versao": contract["versao"],
        "gate_base": {
            "nada": base_results.count("nada"),
            "oportunidade": base_results.count("oportunidade"),
        },
        "promocoes_nada_por_nivel": contract["promocoes_nada_por_nivel"],
        "pressao_atual": pressure["pressao_aventura"],
        "erros": errors,
        "fontes_lidas": list(
            dict.fromkeys(
                [
                    oportunidades.INDEX.as_posix(),
                    oportunidades.STATE.as_posix(),
                    *pressure.get("fontes_lidas", []),
                ]
            )
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)
    encounter_parser = sub.add_parser("encontro", help="executa gate v2 para encontro elegível")
    encounter_parser.add_argument("npc")
    encounter_parser.add_argument("--encontro-id")
    sub.add_parser("check", help="valida contrato v2 e estado corrente")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "check":
            result = check(repo)
            code = 0 if result["ok"] else 1
        else:
            result = encounter_event(repo, args.npc, encounter_id=args.encontro_id)
            code = 0
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return code
    except (SidequestGateV2Error, integration.IntegrationError) as exc:
        print(f"ERRO: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
