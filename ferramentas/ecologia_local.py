#!/usr/bin/env python3
"""Perfis ecológicos determinísticos de locais canônicos.

Ecologia local é uma restrição operacional de plausibilidade, não uma camada de
cânone. Ela descreve família, acesso, ritmo relativo, tags, papéis comuns e canais
ambientais que futuras microcenas podem usar para filtrar possibilidades.

Nenhuma função deste módulo estabelece presença, sorteia evento ou cria fato.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

import locais

INDEX = Path("cenario/locais/ecologia.yaml")
MAX_PROFILES = 32
MAX_PROFILE_BYTES = 2048
MAX_TAGS = 8
MAX_ACTORS = 6
MAX_CHANNELS = 6
PERIODS = ("amanhecer", "dia", "anoitecer", "noite")
ACCESS = {"publico", "semipublico", "controlado", "privado"}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")
ALLOWED_FIELDS = {
    "familia",
    "acesso",
    "ritmo_baseline",
    "tags",
    "atores_comuns",
    "canais_microevento",
}


class LocalEcologyError(ValueError):
    """Erro de contrato da ecologia local."""


def configured(repo: Path) -> bool:
    return (repo / INDEX).is_file()


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise LocalEcologyError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise LocalEcologyError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise LocalEcologyError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LocalEcologyError(f"{label} deve ser texto não vazio")
    return value.strip()


def _slug(value: Any, label: str) -> str:
    value = _text(value, label)
    if not SLUG_RE.fullmatch(value):
        raise LocalEcologyError(f"{label} deve ser slug ASCII minúsculo")
    return value


def _slugs(value: Any, label: str, *, maximum: int) -> list[str]:
    raw = _list(value, label)
    if not 1 <= len(raw) <= maximum:
        raise LocalEcologyError(f"{label} deve ter entre 1 e {maximum} itens")
    result = [_slug(item, f"{label}[{i}]") for i, item in enumerate(raw)]
    if len(result) != len(set(result)):
        raise LocalEcologyError(f"{label} não pode conter duplicatas")
    return result


def _validate_profile(local_id: str, raw: Any) -> dict[str, Any]:
    profile = _map(raw, f"perfis.{local_id}")
    extra = sorted(set(profile) - ALLOWED_FIELDS)
    missing = sorted(ALLOWED_FIELDS - set(profile))
    if extra or missing:
        raise LocalEcologyError(
            f"{local_id}: campos ecológicos inválidos; ausentes={missing}, extras={extra}"
        )
    _slug(profile.get("familia"), f"{local_id}.familia")
    access = _slug(profile.get("acesso"), f"{local_id}.acesso")
    if access not in ACCESS:
        raise LocalEcologyError(f"{local_id}.acesso inválido: {access}")

    rhythm = _map(profile.get("ritmo_baseline"), f"{local_id}.ritmo_baseline")
    if tuple(rhythm) != PERIODS:
        raise LocalEcologyError(
            f"{local_id}.ritmo_baseline deve declarar {', '.join(PERIODS)} nessa ordem"
        )
    for period in PERIODS:
        value = rhythm[period]
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 3:
            raise LocalEcologyError(f"{local_id}.ritmo_baseline.{period} deve ficar entre 0 e 3")

    _slugs(profile.get("tags"), f"{local_id}.tags", maximum=MAX_TAGS)
    _slugs(profile.get("atores_comuns"), f"{local_id}.atores_comuns", maximum=MAX_ACTORS)
    _slugs(
        profile.get("canais_microevento"),
        f"{local_id}.canais_microevento",
        maximum=MAX_CHANNELS,
    )
    rendered = yaml.safe_dump(profile, allow_unicode=True, sort_keys=False).encode("utf-8")
    if len(rendered) > MAX_PROFILE_BYTES:
        raise LocalEcologyError(
            f"{local_id}: perfil ecológico excede {MAX_PROFILE_BYTES} bytes"
        )
    return profile


def load_index(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / INDEX), INDEX.as_posix())
    if (
        data.get("schema_ecologia_local") != 1
        or data.get("natureza") != "roteador_operacional_nao_canonico"
        or data.get("estatuto") != "restricao_de_plausibilidade"
    ):
        raise LocalEcologyError("índice de ecologia local inválido")
    periods = data.get("periodos")
    if periods != list(PERIODS):
        raise LocalEcologyError("periodos da ecologia local divergem do contrato")
    scale = _map(data.get("escala_ritmo"), "escala_ritmo")
    if set(scale) != {0, 1, 2, 3}:
        raise LocalEcologyError("escala_ritmo deve conter exatamente 0, 1, 2, 3")
    rules = _map(data.get("regras"), "regras")
    required_rules = {
        "exige_local_canonico",
        "cobertura_total_do_registro",
        "atores_sao_papeis_nao_npcs",
        "perfil_nao_estabelece_presenca",
        "perfil_nao_cria_evento",
        "perfil_nao_cria_conhecimento",
        "microevento_futuro_deve_respeitar_tags_e_canais",
        "estado_canonico_prevalece",
    }
    if set(rules) != required_rules or not all(value is True for value in rules.values()):
        raise LocalEcologyError("regras da ecologia local devem permanecer integralmente verdadeiras")

    profiles = _map(data.get("perfis"), "perfis")
    if not 1 <= len(profiles) <= MAX_PROFILES:
        raise LocalEcologyError(f"ecologia local deve ter entre 1 e {MAX_PROFILES} perfis")
    for local_id, raw in profiles.items():
        locais._id(local_id)
        _validate_profile(local_id, raw)
    return data


def validate_coverage(repo: Path, ecology: dict[str, Any] | None = None) -> list[str]:
    """Exige um perfil para cada local canônico e nenhum perfil órfão."""
    ecology = ecology or load_index(repo)
    try:
        registry = locais.load_index(repo)
    except locais.LocationError as exc:
        raise LocalEcologyError(str(exc)) from exc
    canonical = set(registry["locais"])
    profiles = set(ecology["perfis"])
    missing = sorted(canonical - profiles)
    extra = sorted(profiles - canonical)
    errors = []
    if missing:
        errors.append("locais canônicos sem ecologia: " + ", ".join(missing))
    if extra:
        errors.append("perfis ecológicos sem local canônico: " + ", ".join(extra))
    return errors


def lookup_canonical(repo: Path, local_id: str) -> dict[str, Any]:
    """Lookup barato quando o chamador já resolveu o ID pelo registro canônico."""
    local_id = locais._id(local_id)
    index = load_index(repo)
    profile = index["perfis"].get(local_id)
    if not isinstance(profile, dict):
        raise LocalEcologyError(f"local canônico sem perfil ecológico: {local_id}")
    return {
        "local_id": local_id,
        "perfil": profile,
        "fontes_lidas": [INDEX.as_posix()],
    }


def lookup(repo: Path, supplied: Any) -> dict[str, Any]:
    """Resolve alias primeiro e depois abre somente o roteador ecológico."""
    try:
        resolution = locais.resolve(repo, supplied)
    except locais.LocationError as exc:
        raise LocalEcologyError(str(exc)) from exc
    result = lookup_canonical(repo, resolution["local_id"])
    return {
        **result,
        "recebido": resolution["recebido"],
        "resolucao": resolution["resolucao"],
        "nome": resolution["nome"],
        "fontes_lidas": list(
            dict.fromkeys([*resolution["fontes_lidas"], *result["fontes_lidas"]])
        ),
    }


def activity(profile: dict[str, Any], period: str) -> dict[str, Any]:
    """Projeta ritmo relativo de um período já conhecido, sem ler tempo."""
    period = _slug(period, "periodo")
    if period not in PERIODS:
        raise LocalEcologyError("periodo deve ser amanhecer, dia, anoitecer ou noite")
    profile = _validate_profile("perfil", profile)
    return {
        "periodo": period,
        "ritmo": profile["ritmo_baseline"][period],
        "canais_microevento": list(profile["canais_microevento"]),
        "tags": list(profile["tags"]),
    }


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    count = 0
    try:
        index = load_index(repo)
        count = len(index["perfis"])
        errors.extend(validate_coverage(repo, index))
    except LocalEcologyError as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "perfis": count,
        "erros": errors,
        "fontes_lidas": [locais.INDEX.as_posix(), INDEX.as_posix()],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)
    show = sub.add_parser("mostrar", help="resolve local e mostra perfil ecológico")
    show.add_argument("local")
    show.add_argument("--periodo", choices=PERIODS)
    sub.add_parser("check", help="valida schema e cobertura do registro canônico")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "check":
            result = check(repo)
        else:
            result = lookup(repo, args.local)
            if args.periodo:
                result["atividade"] = activity(result["perfil"], args.periodo)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0 if result.get("ok", True) else 1
    except (LocalEcologyError, locais.LocationError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
