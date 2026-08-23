#!/usr/bin/env python3
"""Guardrail determinístico para a rede central protegida de Ren.

A proteção é estritamente **por origem**: este módulo só governa consequências
procedurais. Ele não concede imunidade narrativa e não bloqueia combate resolvido,
escolhas do jogador nem ações canônicas dirigidas pelo arco.

No hot path, a política cabe em uma única fonte compacta. Validação fria cruza os
membros declarados com o índice canônico de relações.
"""
from __future__ import annotations

import argparse
import copy
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import yaml

INDEX = Path("narrador/mundo/rede-protegida.yaml")
RELATIONS = Path("estado/relacoes/index.yaml")
SCHEMA = 1
MAX_MEMBERS = 8
MAX_TARGETS = 4
MAX_HOT_SOURCES = 1
SEVERITIES = ("leve", "moderada", "grave")
REVERSIBILITY = ("reversivel", "incerta", "irreversivel")
IMPACT_CLASSES = ("social", "material", "logistico", "juridico", "saude", "liberdade", "vida")
SEVERITY_RANK = {name: idx for idx, name in enumerate(SEVERITIES)}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")
REQUIRED_RULES = {
    "protecao_e_por_origem_nao_imortalidade",
    "combate_resolvido_fica_fora_deste_gate",
    "escolha_do_jogador_fica_fora_deste_gate",
    "acao_canonica_do_arco_fica_fora_deste_gate",
    "evento_mundial_pode_gerar_reacao_mas_nao_afetar_diretamente_o_nucleo",
    "sidequest_procedural_exige_gravidade_reversibilidade_e_alvos",
    "consequencia_grave_procedural_no_nucleo_e_bloqueada",
    "consequencia_nao_reversivel_procedural_no_nucleo_e_bloqueada",
    "vida_e_liberdade_nao_sao_alvos_procedurais_diretos_do_nucleo",
    "microevento_local_permanece_candidato_sem_npc_nomeado",
    "presenca_incidental_permanece_candidato_sem_consequencia",
    "sem_scheduler",
    "sem_estado_proprio",
}
MEMBER_FIELDS = {"nome", "grupo", "fonte"}
VALID_GROUPS = {"nucleo_afetivo", "nucleo_apoio"}


class ProtectedNetworkError(ValueError):
    """Erro de contrato da rede central protegida."""


def configured(repo: Path) -> bool:
    return (repo / INDEX).is_file()


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise ProtectedNetworkError(str(exc)) from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProtectedNetworkError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProtectedNetworkError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProtectedNetworkError(f"{label} deve ser texto não vazio")
    return value.strip()


def _slug(value: Any, label: str) -> str:
    text = _text(value, label)
    if not SLUG_RE.fullmatch(text):
        raise ProtectedNetworkError(f"{label} deve ser slug ASCII minúsculo")
    return text


def _strict(data: dict[str, Any], allowed: set[str], label: str) -> None:
    missing = sorted(allowed - set(data))
    extra = sorted(set(data) - allowed)
    if missing or extra:
        raise ProtectedNetworkError(
            f"{label}: campos inválidos; ausentes={missing}, extras={extra}"
        )


def load_policy(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / INDEX), INDEX.as_posix())
    if data.get("schema_rede_protegida") != SCHEMA:
        raise ProtectedNetworkError(f"política deve usar schema_rede_protegida: {SCHEMA}")
    if data.get("natureza") != "guardrail_reservado":
        raise ProtectedNetworkError("natureza da rede protegida inválida")
    if data.get("estatuto") != "protecao_contra_escalada_procedural":
        raise ProtectedNetworkError("estatuto da rede protegida inválido")

    budget = _map(data.get("orcamento"), "orcamento")
    expected_budget = {
        "max_membros",
        "max_alvos_por_consequencia",
        "max_fontes_hot_path",
        "impacto_procedural_maximo",
    }
    _strict(budget, expected_budget, "orcamento")
    if budget["max_membros"] != MAX_MEMBERS:
        raise ProtectedNetworkError(f"orcamento.max_membros deve ser {MAX_MEMBERS}")
    if budget["max_alvos_por_consequencia"] != MAX_TARGETS:
        raise ProtectedNetworkError(
            f"orcamento.max_alvos_por_consequencia deve ser {MAX_TARGETS}"
        )
    if budget["max_fontes_hot_path"] != MAX_HOT_SOURCES:
        raise ProtectedNetworkError(
            f"orcamento.max_fontes_hot_path deve ser {MAX_HOT_SOURCES}"
        )
    maximum = _slug(budget["impacto_procedural_maximo"], "impacto_procedural_maximo")
    if maximum not in SEVERITY_RANK:
        raise ProtectedNetworkError("impacto_procedural_maximo inválido")

    rules = _map(data.get("regras"), "regras")
    if set(rules) != REQUIRED_RULES or not all(value is True for value in rules.values()):
        raise ProtectedNetworkError("regras da rede protegida devem permanecer integralmente verdadeiras")

    if data.get("gravidades") != list(SEVERITIES):
        raise ProtectedNetworkError("gravidades divergem do contrato")
    if data.get("reversibilidades") != list(REVERSIBILITY):
        raise ProtectedNetworkError("reversibilidades divergem do contrato")
    if data.get("classes_impacto") != list(IMPACT_CLASSES):
        raise ProtectedNetworkError("classes_impacto divergem do contrato")
    forbidden = _list(data.get("classes_proibidas_no_nucleo"), "classes_proibidas_no_nucleo")
    if set(forbidden) != {"liberdade", "vida"}:
        raise ProtectedNetworkError("classes_proibidas_no_nucleo devem ser liberdade e vida")

    members = _map(data.get("membros"), "membros")
    if not 1 <= len(members) <= MAX_MEMBERS:
        raise ProtectedNetworkError(f"rede protegida deve ter entre 1 e {MAX_MEMBERS} membros")
    for npc_id, raw in members.items():
        npc_id = _slug(npc_id, "id de membro")
        meta = _map(raw, f"membros.{npc_id}")
        _strict(meta, MEMBER_FIELDS, f"membros.{npc_id}")
        _text(meta["nome"], f"membros.{npc_id}.nome")
        group = _slug(meta["grupo"], f"membros.{npc_id}.grupo")
        if group not in VALID_GROUPS:
            raise ProtectedNetworkError(f"grupo protegido inválido: {group}")
        source = _text(meta["fonte"], f"membros.{npc_id}.fonte")
        if source != f"estado/relacoes/{npc_id}.yaml":
            raise ProtectedNetworkError(
                f"membros.{npc_id}.fonte deve apontar para estado/relacoes/{npc_id}.yaml"
            )
    return data


def protected_ids(policy: dict[str, Any]) -> set[str]:
    return set(_map(policy.get("membros"), "membros"))


def partition_candidates(policy: dict[str, Any], ids: Iterable[str]) -> dict[str, list[str]]:
    """Separa candidatos de evento sem reordenar nem substituir o ranking original."""
    protected = protected_ids(policy)
    affected: list[str] = []
    core: list[str] = []
    seen: set[str] = set()
    for raw in ids:
        npc_id = _slug(raw, "npc_id")
        if npc_id in seen:
            continue
        seen.add(npc_id)
        (core if npc_id in protected else affected).append(npc_id)
    return {"afetados": affected, "nucleo_protegido": core}


def _targets(value: dict[str, Any]) -> list[str]:
    raw = _list(value.get("alvos_npc"), "consequencia.alvos_npc")
    if len(raw) > MAX_TARGETS:
        raise ProtectedNetworkError(
            f"consequência aceita no máximo {MAX_TARGETS} alvos_npc"
        )
    result = [_slug(item, f"consequencia.alvos_npc[{i}]") for i, item in enumerate(raw)]
    if len(result) != len(set(result)):
        raise ProtectedNetworkError("consequencia.alvos_npc não pode conter duplicatas")
    return result


def guard_consequence(repo: Path, raw: Any, *, origem: str) -> dict[str, Any]:
    """Valida uma consequência procedural e bloqueia escalada grave sobre o núcleo."""
    value = copy.deepcopy(_map(raw, "consequencia"))
    policy = load_policy(repo)
    source = _slug(origem, "origem procedural")
    if source not in {"sidequest", "evento_mundial"}:
        raise ProtectedNetworkError(
            "rede protegida governa somente origens procedurais sidequest ou evento_mundial"
        )

    severity = _slug(value.get("gravidade"), "consequencia.gravidade")
    if severity not in SEVERITY_RANK:
        raise ProtectedNetworkError(
            "consequencia.gravidade deve ser leve, moderada ou grave"
        )
    reversibility = _slug(value.get("reversibilidade"), "consequencia.reversibilidade")
    if reversibility not in REVERSIBILITY:
        raise ProtectedNetworkError(
            "consequencia.reversibilidade deve ser reversivel, incerta ou irreversivel"
        )
    impact_class = _slug(value.get("classe_impacto"), "consequencia.classe_impacto")
    if impact_class not in IMPACT_CLASSES:
        raise ProtectedNetworkError(
            "consequencia.classe_impacto deve pertencer ao vocabulário controlado"
        )
    targets = _targets(value)
    protected = sorted(set(targets) & protected_ids(policy))

    if protected:
        maximum = policy["orcamento"]["impacto_procedural_maximo"]
        if SEVERITY_RANK[severity] > SEVERITY_RANK[maximum]:
            raise ProtectedNetworkError(
                "consequência procedural grave bloqueada para núcleo protegido: "
                + ", ".join(protected)
            )
        if reversibility != "reversivel":
            raise ProtectedNetworkError(
                "consequência procedural não reversível bloqueada para núcleo protegido: "
                + ", ".join(protected)
            )
        if impact_class in set(policy["classes_proibidas_no_nucleo"]):
            raise ProtectedNetworkError(
                f"classe procedural {impact_class} bloqueada para núcleo protegido: "
                + ", ".join(protected)
            )

    value["gravidade"] = severity
    value["reversibilidade"] = reversibility
    value["classe_impacto"] = impact_class
    value["alvos_npc"] = targets
    value["origem_procedural"] = source
    if protected:
        value["rede_protegida"] = {
            "alvos": protected,
            "impacto_maximo": policy["orcamento"]["impacto_procedural_maximo"],
            "reversibilidade_exigida": "reversivel",
        }
    return {
        "valor": value,
        "alvos_protegidos": protected,
        "fontes_lidas": [INDEX.as_posix()],
    }


def event_guard(policy: dict[str, Any], protected: Iterable[str]) -> dict[str, Any] | None:
    ids = list(protected)
    if not ids:
        return None
    return {
        "alvos": ids,
        "papel": "reagir_sem_ser_alvo_direto",
        "impacto_maximo": policy["orcamento"]["impacto_procedural_maximo"],
        "reversibilidade_exigida": "reversivel",
        "regra": (
            "evento procedural pode motivar reação contextual, mas não impor diretamente "
            "consequência grave, irreversível, de vida ou liberdade ao núcleo"
        ),
    }


def validate(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    members = 0
    try:
        policy = load_policy(repo)
        members = len(policy["membros"])
        relations = _map(_load(repo / RELATIONS), RELATIONS.as_posix())
        canonical = _map(relations.get("relacoes"), "relacoes")
        for npc_id, meta in policy["membros"].items():
            relation = canonical.get(npc_id)
            if not isinstance(relation, dict):
                errors.append(f"membro protegido não existe nas relações canônicas: {npc_id}")
                continue
            if relation.get("nome") != meta["nome"]:
                errors.append(f"nome protegido diverge do índice canônico: {npc_id}")
            if relation.get("arquivo") != meta["fonte"]:
                errors.append(f"fonte protegida diverge do índice canônico: {npc_id}")
    except ProtectedNetworkError as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "membros": members,
        "erros": list(dict.fromkeys(errors)),
        "fontes_lidas": [INDEX.as_posix(), RELATIONS.as_posix()],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check")
    show = sub.add_parser("mostrar")
    show.add_argument("npc_id")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "check":
            result = validate(repo)
            status = 0 if result["ok"] else 1
        else:
            policy = load_policy(repo)
            npc_id = _slug(args.npc_id, "npc_id")
            meta = policy["membros"].get(npc_id)
            result = {
                "npc_id": npc_id,
                "protegido": isinstance(meta, dict),
                "politica": copy.deepcopy(meta) if isinstance(meta, dict) else None,
                "fontes_lidas": [INDEX.as_posix()],
            }
            status = 0
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return status
    except ProtectedNetworkError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
