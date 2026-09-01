#!/usr/bin/env python3
"""Avaliação dirigida e determinística de ameaça para adversários preparados.

O resultado é orientação pré-rolagem. Não cria encontro, presença ou aliado e
jamais autoriza alterar uma ficha para obter a classificação desejada.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

try:
    import adversarios
    import ficha_ren
except ModuleNotFoundError:
    from ferramentas import adversarios, ficha_ren


CONTRACT_PATH = Path("narrador/adversarios/contrato-ameacas.yaml")
PROFILES_PATH = Path("narrador/adversarios/ameacas.yaml")
REN_SHEET_PATH = Path("personagens/jogador/ficha.yaml")
SCHEMA = 1


class ThreatValidationError(ValueError):
    """Contrato ou entrada inválida da avaliação de ameaça."""


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ThreatValidationError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise ThreatValidationError(f"YAML inválido em {path}: {exc}") from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ThreatValidationError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ThreatValidationError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ThreatValidationError(f"{label} deve ser texto não vazio")
    return " ".join(value.strip().split())


def _integer(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ThreatValidationError(f"{label} deve ser inteiro")
    if not minimum <= value <= maximum:
        raise ThreatValidationError(f"{label} deve ficar entre {minimum} e {maximum}")
    return value


def _strings(value: Any, label: str) -> list[str]:
    items = [_text(item, f"{label}[{index}]") for index, item in enumerate(_list(value, label))]
    if not items or len(items) != len(set(items)):
        raise ThreatValidationError(f"{label} deve ser lista não vazia sem duplicatas")
    return items


def _dump(value: Any) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def load_contract(repo: Path) -> dict[str, Any]:
    path = repo / CONTRACT_PATH
    data = _map(_load_yaml(path), CONTRACT_PATH.as_posix())
    expected = {
        "schema_contrato_ameacas", "natureza", "ruleset", "orcamento",
        "naturezas_perfil", "vetores", "estados_recursos",
        "vantagens_contextuais", "faixas", "modificadores", "invariantes",
    }
    if set(data) != expected:
        raise ThreatValidationError("contrato de ameaças possui estrutura inesperada")
    if data["schema_contrato_ameacas"] != SCHEMA:
        raise ThreatValidationError("schema_contrato_ameacas deve ser 1")
    if data["natureza"] != "contrato_avaliacao_ameaca_reservado":
        raise ThreatValidationError("natureza do contrato de ameaças inválida")
    if data["ruleset"] != adversarios.load_campaign_ruleset(repo):
        raise ThreatValidationError("ruleset do contrato de ameaças diverge da campanha")

    budget = _map(data["orcamento"], "orcamento")
    if set(budget) != {"registro_max_bytes", "consulta_max_bytes"}:
        raise ThreatValidationError("orcamento de ameaças possui estrutura inesperada")
    _integer(budget["registro_max_bytes"], "orcamento.registro_max_bytes", 1024, 16384)
    if _integer(budget["consulta_max_bytes"], "orcamento.consulta_max_bytes", 1024, 8192) != 4096:
        raise ThreatValidationError("consulta de ameaça deve permanecer em 4 KiB")

    if set(_strings(data["naturezas_perfil"], "naturezas_perfil")) != {
        "ator_canonico", "arquetipo_reutilizavel"
    }:
        raise ThreatValidationError("naturezas_perfil inválidas")
    if _strings(data["vetores"], "vetores") != ["combate", "especialidade"]:
        raise ThreatValidationError("vetores devem ser combate e especialidade")
    resources = _strings(data["estados_recursos"], "estados_recursos")
    contexts = _strings(data["vantagens_contextuais"], "vantagens_contextuais")
    if resources != ["plenos", "gastos", "criticos"]:
        raise ThreatValidationError("estados_recursos inválidos")
    if contexts != ["grupo", "neutra", "adversario"]:
        raise ThreatValidationError("vantagens_contextuais inválidas")

    expected_ranges = [
        ("baixa", None, -3, False),
        ("moderada", -2, -1, False),
        ("alta", 0, 1, False),
        ("letal", 2, 3, True),
        ("esmagadora", 4, None, True),
    ]
    ranges = _list(data["faixas"], "faixas")
    parsed_ranges = []
    for index, raw in enumerate(ranges):
        item = _map(raw, f"faixas[{index}]")
        if set(item) != {"id", "minimo", "maximo", "saida_observavel_obrigatoria"}:
            raise ThreatValidationError(f"faixas[{index}] possui estrutura inesperada")
        parsed_ranges.append(
            (item["id"], item["minimo"], item["maximo"], item["saida_observavel_obrigatoria"])
        )
    if parsed_ranges != expected_ranges:
        raise ThreatValidationError("faixas de ameaça foram alteradas sem nova decisão")

    modifiers = _map(data["modificadores"], "modificadores")
    if set(modifiers) != {
        "inimigo_adicional", "aliado_competente", "recursos", "terreno", "iniciativa"
    }:
        raise ThreatValidationError("modificadores possui estrutura inesperada")
    if modifiers["inimigo_adicional"] != 2 or modifiers["aliado_competente"] != -2:
        raise ThreatValidationError("economia de ações da avaliação foi alterada")
    expected_maps = {
        "recursos": {"plenos": 0, "gastos": 1, "criticos": 2},
        "terreno": {"grupo": -1, "neutra": 0, "adversario": 1},
        "iniciativa": {"grupo": -1, "neutra": 0, "adversario": 1},
    }
    for key, expected_map in expected_maps.items():
        if _map(modifiers[key], f"modificadores.{key}") != expected_map:
            raise ThreatValidationError(f"modificadores.{key} foi alterado")

    invariants = _map(data["invariantes"], "invariantes")
    required = {
        "avaliacao_antes_da_rolagem", "classificacao_nao_altera_ficha",
        "aliado_exige_presenca_capacidade_e_motivo", "aliado_nao_e_injetado_para_balancear",
        "ameaca_letal_exige_saida_observavel", "saida_nao_garante_sucesso",
        "quantidade_e_contexto_sao_explicitos", "consulta_nao_roda_em_turno_comum",
    }
    if set(invariants) != required or not all(value is True for value in invariants.values()):
        raise ThreatValidationError("invariantes de ameaça devem permanecer verdadeiras")
    return data


def load_profiles(repo: Path, contract: dict[str, Any] | None = None) -> dict[str, Any]:
    contract = contract or load_contract(repo)
    path = repo / PROFILES_PATH
    if path.stat().st_size > contract["orcamento"]["registro_max_bytes"]:
        raise ThreatValidationError("registro de ameaças excede o orçamento")
    data = _map(_load_yaml(path), PROFILES_PATH.as_posix())
    if set(data) != {"schema_perfis_ameaca", "natureza", "contrato", "perfis"}:
        raise ThreatValidationError("registro de ameaças possui estrutura inesperada")
    if data["schema_perfis_ameaca"] != SCHEMA or data["natureza"] != "reservado":
        raise ThreatValidationError("metadados do registro de ameaças inválidos")
    if data["contrato"] != CONTRACT_PATH.as_posix():
        raise ThreatValidationError("registro deve apontar para contrato de ameaças")

    index = adversarios.load_index(repo)
    profiles = _map(data["perfis"], "perfis")
    if set(profiles) != set(index["adversarios"]):
        missing = sorted(set(index["adversarios"]) - set(profiles))
        extra = sorted(set(profiles) - set(index["adversarios"]))
        raise ThreatValidationError(f"perfis divergem do índice; ausentes={missing}; extras={extra}")
    allowed_natures = set(contract["naturezas_perfil"])
    for adversary_id, raw in profiles.items():
        label = f"perfis.{adversary_id}"
        profile = _map(raw, label)
        if set(profile) != {"natureza", "patamares", "vetores", "sinalizacao", "saidas_plausiveis"}:
            raise ThreatValidationError(f"{label} possui estrutura inesperada")
        nature = _text(profile["natureza"], f"{label}.natureza")
        if nature not in allowed_natures:
            raise ThreatValidationError(f"{label}.natureza inválida")
        if nature == "arquetipo_reutilizavel" and not adversary_id.startswith("arquetipo_"):
            raise ThreatValidationError(f"{label}: arquétipo exige prefixo arquetipo_")
        tiers = _map(profile["patamares"], f"{label}.patamares")
        if set(tiers) != set(contract["vetores"]):
            raise ThreatValidationError(f"{label}.patamares deve cobrir os dois vetores")
        for vector, value in tiers.items():
            _integer(value, f"{label}.patamares.{vector}", 1, 30)
        _strings(profile["vetores"], f"{label}.vetores")
        _text(profile["sinalizacao"], f"{label}.sinalizacao")
        _strings(profile["saidas_plausiveis"], f"{label}.saidas_plausiveis")
    return data


def _band(contract: dict[str, Any], score: int) -> dict[str, Any]:
    for band in contract["faixas"]:
        lower = band["minimo"]
        upper = band["maximo"]
        if (lower is None or score >= lower) and (upper is None or score <= upper):
            return band
    raise ThreatValidationError("índice não pertence a nenhuma faixa de ameaça")


def _ren_snapshot(repo: Path) -> tuple[int, str]:
    path = repo / REN_SHEET_PATH
    mechanics = ficha_ren.load(path)
    raw = _map(_load_yaml(path), REN_SHEET_PATH.as_posix())
    identity = _map(raw.get("identidade"), "ficha.identidade")
    level = _integer(identity.get("nivel"), "ficha.identidade.nivel", 1, 20)
    hp = mechanics.resources["pontos_de_vida"]
    focus = mechanics.resources["focus"]
    hp_ratio = hp["atuais"] / hp["maximos"]
    focus_max = focus["pontos_maximos"]
    focus_ratio = focus["pontos_atuais"] / focus_max if focus_max else 1.0
    if hp_ratio <= 0.35 or (focus_max and focus["pontos_atuais"] == 0):
        state = "criticos"
    elif hp_ratio < 0.75 or focus_ratio < 0.5:
        state = "gastos"
    else:
        state = "plenos"
    return level, state


def evaluate(
    repo: Path,
    query: str,
    *,
    vector: str,
    level: int,
    enemies: int = 1,
    allies: int = 0,
    resources: str = "plenos",
    terrain: str = "neutra",
    initiative: str = "neutra",
    ren_sheet_read: bool = False,
) -> dict[str, Any]:
    contract = load_contract(repo)
    profiles = load_profiles(repo, contract)
    index = adversarios.load_index(repo)
    adversary_id, _ = adversarios.resolve_adversary(index, query)
    if vector not in contract["vetores"]:
        raise ThreatValidationError("vetor deve ser combate ou especialidade")
    level = _integer(level, "nivel", 1, 20)
    enemies = _integer(enemies, "inimigos", 1, 10)
    allies = _integer(allies, "aliados_competentes", 0, 5)
    if resources not in contract["estados_recursos"]:
        raise ThreatValidationError("estado de recursos inválido")
    if terrain not in contract["vantagens_contextuais"]:
        raise ThreatValidationError("terreno inválido")
    if initiative not in contract["vantagens_contextuais"]:
        raise ThreatValidationError("iniciativa inválida")

    profile = profiles["perfis"][adversary_id]
    tier = profile["patamares"][vector]
    modifiers = contract["modificadores"]
    components = {
        "diferenca_patamar_nivel": tier - level,
        "inimigos_adicionais": (enemies - 1) * modifiers["inimigo_adicional"],
        "aliados_competentes": allies * modifiers["aliado_competente"],
        "recursos": modifiers["recursos"][resources],
        "terreno": modifiers["terreno"][terrain],
        "iniciativa": modifiers["iniciativa"][initiative],
    }
    score = sum(components.values())
    band = _band(contract, score)
    sources = [
        CONTRACT_PATH.as_posix(), PROFILES_PATH.as_posix(),
        adversarios.CONTRACT_PATH.as_posix(), adversarios.INDEX_PATH.as_posix(),
    ]
    if ren_sheet_read:
        sources.append(REN_SHEET_PATH.as_posix())
    result = {
        "schema_avaliacao_ameaca": 1,
        "adversario_id": adversary_id,
        "fontes_lidas": sources,
        "snapshot_pre_rolagem": {
            "vetor": vector,
            "nivel": level,
            "inimigos": enemies,
            "aliados_competentes": allies,
            "recursos": resources,
            "terreno": terrain,
            "iniciativa": initiative,
        },
        "calculo": {"patamar": tier, "componentes": components, "indice": score},
        "resultado": {
            "classificacao": band["id"],
            "saida_observavel_obrigatoria": band["saida_observavel_obrigatoria"],
            "sinalizacao": profile["sinalizacao"],
            "saidas_plausiveis": profile["saidas_plausiveis"],
            "limites": [
                "heurística de preparação, não garantia de vitória ou derrota",
                "não altera ficha, quantidade, terreno ou resultado depois da rolagem",
                "aliado contado precisa já ter presença, capacidade e motivo canônicos",
            ],
        },
    }
    if len(_dump(result).encode("utf-8")) > contract["orcamento"]["consulta_max_bytes"]:
        raise ThreatValidationError("consulta de ameaça excede o orçamento de 4 KiB")
    return result


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    quantity = 0
    try:
        contract = load_contract(repo)
        profiles = load_profiles(repo, contract)
        quantity = len(profiles["perfis"])
        for adversary_id, profile in profiles["perfis"].items():
            for vector in contract["vetores"]:
                evaluate(repo, adversary_id, vector=vector, level=profile["patamares"][vector])
    except (ThreatValidationError, adversarios.AdversaryValidationError, ficha_ren.RenSheetError) as exc:
        errors.append(str(exc))
    return {"ok": not errors, "quantidade": quantity, "erros": errors}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    subparsers = parser.add_subparsers(dest="comando", required=True)
    assess = subparsers.add_parser("avaliar", help="avalia ameaça antes da rolagem")
    assess.add_argument("consulta")
    source = assess.add_mutually_exclusive_group(required=True)
    source.add_argument("--ren", action="store_true")
    source.add_argument("--nivel", type=int)
    assess.add_argument("--vetor", choices=["combate", "especialidade"], default="combate")
    assess.add_argument("--inimigos", type=int, default=1)
    assess.add_argument("--aliados-competentes", type=int, default=0)
    assess.add_argument("--recursos", choices=["plenos", "gastos", "criticos"])
    assess.add_argument("--terreno", choices=["grupo", "neutra", "adversario"], default="neutra")
    assess.add_argument("--iniciativa", choices=["grupo", "neutra", "adversario"], default="neutra")
    subparsers.add_parser("validar", help="valida perfis e contrato em manutenção/CI")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.comando == "validar":
            result = validate_repo(repo)
            if not result["ok"]:
                print(_dump(result), end="")
                return 1
        else:
            if args.ren:
                if args.recursos is not None:
                    raise ThreatValidationError("--ren deriva recursos; não combinar com --recursos")
                level, resources = _ren_snapshot(repo)
            else:
                level, resources = args.nivel, args.recursos or "plenos"
            result = evaluate(
                repo, args.consulta, vector=args.vetor, level=level,
                enemies=args.inimigos, allies=args.aliados_competentes,
                resources=resources, terrain=args.terreno, initiative=args.iniciativa,
                ren_sheet_read=args.ren,
            )
        print(_dump(result), end="")
        return 0
    except (ThreatValidationError, adversarios.AdversaryValidationError, ficha_ren.RenSheetError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
