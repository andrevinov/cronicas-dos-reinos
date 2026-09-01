#!/usr/bin/env python3
"""Progressão de Ren por neutralizações duráveis da Juppongatana.

A faixa 8–17 usa dez milestones: cada membro único neutralizado de forma
canônica e durável desbloqueia exatamente um nível. A ordem dos membros é livre.

Este módulo NÃO aplica a progressão mecânica da ficha. Ele registra o milestone e
expõe o nível devido; PV, focus, habilidades e escolhas continuam passando por
``regras/progressao.md``.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml

POLICY = Path("narrador/juppongatana/progressao.yaml")
STATE = Path("narrador/juppongatana/estado-progressao.yaml")
ROSTER = Path("narrador/juppongatana/index.yaml")
SHEET = Path("personagens/jogador/ficha.yaml")
AGENTS = Path("narrador/agentes/index.yaml")

SCHEMA_POLICY = 1
SCHEMA_STATE = 1
BASE_LEVEL = 7
FINAL_LEVEL = 17
MAX_NEUTRALIZATIONS = 10
MAX_EVIDENCE_CHARS = 320
MAX_NOTE_CHARS = 320
MAX_STATE_BYTES = 16384
SOURCE_PREFIXES = ("sessoes/", "estado/", "historico/")
DURABLE_TYPES = (
    "morte_confirmada",
    "prisao_ou_confinamento_estavel",
    "incapacitacao_duravel",
    "ruptura_definitiva_com_masao",
    "expulsao_ou_exilio_operacional",
)
VALID_CIRCLES = {"externo", "meio", "interno"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_]{0,63}$")
PREPARATION_RE = re.compile(r"^[0-9a-f]{24}$")


class JuppongatanaProgressionError(ValueError):
    """Violação do contrato de milestones da Juppongatana."""


def _load(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise JuppongatanaProgressionError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise JuppongatanaProgressionError(f"YAML inválido em {path}: {exc}") from exc


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise JuppongatanaProgressionError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise JuppongatanaProgressionError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str, *, maximum: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise JuppongatanaProgressionError(f"{label} deve ser texto não vazio")
    result = value.strip()
    if maximum is not None and len(result) > maximum:
        raise JuppongatanaProgressionError(f"{label} excede {maximum} caracteres")
    return result


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise JuppongatanaProgressionError(f"{label} deve ser inteiro >= {minimum}")
    return value


def _member_id(value: Any) -> str:
    result = _text(value, "membro")
    if not ID_RE.fullmatch(result):
        raise JuppongatanaProgressionError("membro deve ser um ID estável ASCII")
    return result


def _atomic(path: Path, payload: dict[str, Any]) -> None:
    rendered = yaml.safe_dump(payload, allow_unicode=True, sort_keys=False)
    if len(rendered.encode("utf-8")) > MAX_STATE_BYTES:
        raise JuppongatanaProgressionError(
            f"estado de progressão excederia {MAX_STATE_BYTES} bytes"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        handle.write(rendered)
        handle.flush()
        os.fsync(handle.fileno())
        tmp = Path(handle.name)
    os.replace(tmp, path)


def load_policy(repo: Path) -> dict[str, Any]:
    data = _map(_load(repo / POLICY), POLICY.as_posix())
    if data.get("schema_progressao_juppongatana") != SCHEMA_POLICY:
        raise JuppongatanaProgressionError(
            f"política deve usar schema_progressao_juppongatana: {SCHEMA_POLICY}"
        )
    if data.get("natureza") != "reservado":
        raise JuppongatanaProgressionError("política deve ter natureza: reservado")
    if data.get("estatuto") != "espinha_de_marcos_niveis_8_a_17":
        raise JuppongatanaProgressionError("estatuto de progressão inesperado")
    if data.get("base_nivel") != BASE_LEVEL or data.get("ultimo_nivel") != FINAL_LEVEL:
        raise JuppongatanaProgressionError("faixa de níveis da Juppongatana diverge do contrato")
    if data.get("neutralizacoes_necessarias") != MAX_NEUTRALIZATIONS:
        raise JuppongatanaProgressionError("quantidade de milestones deve continuar em 10")
    if data.get("ordem_dos_membros") != "livre":
        raise JuppongatanaProgressionError("ordem dos membros deve permanecer livre")
    if data.get("faixa_niveis") != list(range(BASE_LEVEL + 1, FINAL_LEVEL + 1)):
        raise JuppongatanaProgressionError("faixa_niveis deve ser exatamente 8..17")
    if tuple(data.get("tipos_duraveis") or ()) != DURABLE_TYPES:
        raise JuppongatanaProgressionError("tipos_duraveis divergem do contrato")

    rules = _map(data.get("regras"), "regras")
    required_true = {
        "um_membro_so_conta_uma_vez",
        "neutralizacao_nao_exige_morte",
        "resultado_precisa_ser_canonico_e_duravel",
        "fonte_e_evidencia_literal_obrigatorias",
        "simples_vitoria_em_cena_nao_conta",
        "ordem_de_neutralizacao_nao_e_trilho",
        "aparicao_nao_define_ordem_de_progressao",
        "nenhuma_neutralizacao_retroativa_na_instalacao",
        "kurobane_frustrado_antes_da_task_nao_conta",
        "retorno_futuro_nao_revoga_nivel_ja_conquistado",
        "retorno_futuro_nao_permite_contar_o_mesmo_membro_de_novo",
        "niveis_8_a_17_usam_esta_espinha",
        "outros_marcos_na_faixa_nao_substituem_neutralizacao",
        "nivel_mecanico_nao_e_aplicado_automaticamente",
        "aplicacao_mecanica_segue_regras_progressao",
        "depois_do_nivel_17_progressao_geral_reassume",
    }
    if set(rules) != required_true or not all(value is True for value in rules.values()):
        raise JuppongatanaProgressionError("guardrails da progressão devem permanecer verdadeiros")

    roster_ref = _map(data.get("elenco"), "elenco")
    if set(roster_ref) != {"autoridade", "arquivo"}:
        raise JuppongatanaProgressionError("elenco deve declarar autoridade e arquivo")
    if roster_ref.get("autoridade") != "elenco_juppongatana":
        raise JuppongatanaProgressionError("política deve usar a autoridade elenco_juppongatana")
    if roster_ref.get("arquivo") != ROSTER.as_posix():
        raise JuppongatanaProgressionError("política aponta para autoridade de elenco inesperada")
    # Compatibilidade de API: consumidores recebem uma visão derivada, nunca uma
    # segunda cópia persistida no arquivo de política.
    data["membros"] = load_roster(repo)
    return data


def load_roster(
    repo: Path,
    *,
    check_routes: bool = False,
) -> dict[str, dict[str, Any]]:
    data = _map(_load(repo / ROSTER), ROSTER.as_posix())
    if data.get("schema_elenco_juppongatana") != 1:
        raise JuppongatanaProgressionError("elenco deve usar schema_elenco_juppongatana: 1")
    if data.get("natureza") != "autoridade_reservada_de_elenco":
        raise JuppongatanaProgressionError("natureza da autoridade de elenco inválida")
    if data.get("id") != "juppongatana" or data.get("quantidade_canônica") != MAX_NEUTRALIZATIONS:
        raise JuppongatanaProgressionError("elenco deve representar exatamente as Dez Espadas")
    members = _map(data.get("membros"), "elenco.membros")
    if len(members) != MAX_NEUTRALIZATIONS:
        raise JuppongatanaProgressionError("elenco deve conter exatamente dez membros")
    required = {"nome", "alcunha", "circulo", "perfil", "agente", "imagem"}
    for member_id, raw in members.items():
        _member_id(member_id)
        meta = _map(raw, f"elenco.membros.{member_id}")
        if set(meta) != required:
            raise JuppongatanaProgressionError(
                f"elenco.membros.{member_id} deve conter somente {', '.join(sorted(required))}"
            )
        _text(meta.get("nome"), f"elenco.membros.{member_id}.nome")
        _text(meta.get("alcunha"), f"elenco.membros.{member_id}.alcunha")
        if meta.get("circulo") not in VALID_CIRCLES:
            raise JuppongatanaProgressionError(f"círculo inválido para {member_id}")
        for field in ("perfil", "agente", "imagem"):
            raw_path = _text(meta.get(field), f"elenco.membros.{member_id}.{field}")
            path_text = raw_path.split("#", 1)[0]
            path = Path(path_text)
            if path.is_absolute() or ".." in path.parts or (
                check_routes and not (repo / path).is_file()
            ):
                raise JuppongatanaProgressionError(
                    f"rota inválida ou inexistente em elenco.membros.{member_id}.{field}: {raw_path}"
                )
    return members


def load_state(
    repo: Path,
    roster: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    roster = roster if roster is not None else load_roster(repo)
    data = _map(_load(repo / STATE), STATE.as_posix())
    if data.get("schema_estado_progressao_juppongatana") != SCHEMA_STATE:
        raise JuppongatanaProgressionError(
            f"estado deve usar schema_estado_progressao_juppongatana: {SCHEMA_STATE}"
        )
    if data.get("natureza") != "estado_reservado" or data.get("base_nivel") != BASE_LEVEL:
        raise JuppongatanaProgressionError("metadados do estado de progressão inválidos")
    if data.get("retroatividade_aplicada") is not False:
        raise JuppongatanaProgressionError("estado não pode conceder neutralização retroativa")

    entries = _list(data.get("neutralizacoes"), "neutralizacoes")
    if len(entries) > MAX_NEUTRALIZATIONS:
        raise JuppongatanaProgressionError("estado excede dez neutralizações")
    seen: set[str] = set()
    for index, raw in enumerate(entries, start=1):
        item = _map(raw, f"neutralizacoes[{index - 1}]")
        expected_fields = {
            "ordem",
            "membro",
            "tipo",
            "fonte",
            "evidencia",
            "nivel_desbloqueado",
            "preparacao_id",
        }
        optional = {"sessao", "nota"}
        if not expected_fields <= set(item) or set(item) - expected_fields - optional:
            raise JuppongatanaProgressionError(
                f"neutralizacoes[{index - 1}] possui campos inválidos"
            )
        if item.get("ordem") != index:
            raise JuppongatanaProgressionError("ordem das neutralizações deve ser sequencial")
        member = _member_id(item.get("membro"))
        if member not in roster:
            raise JuppongatanaProgressionError(f"membro fora da Juppongatana: {member}")
        if member in seen:
            raise JuppongatanaProgressionError(f"membro contado duas vezes: {member}")
        seen.add(member)
        if item.get("tipo") not in DURABLE_TYPES:
            raise JuppongatanaProgressionError(f"neutralização não durável: {item.get('tipo')!r}")
        _validate_source_rel(item.get("fonte"))
        _text(item.get("evidencia"), "evidencia", maximum=MAX_EVIDENCE_CHARS)
        if item.get("nivel_desbloqueado") != BASE_LEVEL + index:
            raise JuppongatanaProgressionError("nível desbloqueado diverge da ordem do milestone")
        prep = _text(item.get("preparacao_id"), "preparacao_id")
        if not PREPARATION_RE.fullmatch(prep):
            raise JuppongatanaProgressionError("preparacao_id inválido no ledger")
        if "sessao" in item:
            _integer(item["sessao"], "sessao", 1)
        if "nota" in item:
            _text(item["nota"], "nota", maximum=MAX_NOTE_CHARS)
    return data


def _sheet_level(repo: Path) -> int:
    sheet = _map(_load(repo / SHEET), SHEET.as_posix())
    identity = _map(sheet.get("identidade"), "ficha.identidade")
    return _integer(identity.get("nivel"), "ficha.identidade.nivel", 1)


def _validate_source_rel(value: Any) -> str:
    raw = _text(value, "fonte")
    rel = Path(raw)
    if rel.is_absolute() or ".." in rel.parts:
        raise JuppongatanaProgressionError("fonte deve ser caminho relativo dentro do repositório")
    normalized = rel.as_posix()
    if not normalized.startswith(SOURCE_PREFIXES):
        raise JuppongatanaProgressionError(
            "fonte do milestone deve ficar sob sessoes/, estado/ ou historico/"
        )
    return normalized


def _source_evidence(repo: Path, source: Any, evidence: Any) -> tuple[str, str, bytes]:
    rel = _validate_source_rel(source)
    evidence_text = _text(evidence, "evidencia", maximum=MAX_EVIDENCE_CHARS)
    path = repo / rel
    if not path.is_file():
        raise JuppongatanaProgressionError(f"fonte canônica inexistente: {rel}")
    raw = path.read_bytes()
    try:
        body = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise JuppongatanaProgressionError("fonte de milestone precisa ser texto UTF-8") from exc
    compact_body = " ".join(body.split())
    compact_evidence = " ".join(evidence_text.split())
    if compact_evidence not in compact_body:
        raise JuppongatanaProgressionError(
            "evidência literal não encontrada na fonte canônica informada"
        )
    return rel, evidence_text, raw


def _preparation_id(
    policy_bytes: bytes,
    roster_bytes: bytes,
    state_bytes: bytes,
    sheet_bytes: bytes,
    source_bytes: bytes,
    *,
    member: str,
    kind: str,
    source: str,
    evidence: str,
    session: int | None,
    note: str | None,
) -> str:
    digest = hashlib.sha256()
    for raw in (policy_bytes, roster_bytes, state_bytes, sheet_bytes, source_bytes):
        digest.update(raw)
        digest.update(b"\0")
    for value in (member, kind, source, evidence, session or "", note or ""):
        digest.update(str(value).encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()[:24]


def _existing(state: dict[str, Any], member: str) -> dict[str, Any] | None:
    return next(
        (item for item in state["neutralizacoes"] if item.get("membro") == member),
        None,
    )


def status(repo: Path) -> dict[str, Any]:
    policy = load_policy(repo)
    roster = load_roster(repo)
    state = load_state(repo, roster)
    current = _sheet_level(repo)
    count = len(state["neutralizacoes"])
    unlocked = BASE_LEVEL + count
    remaining = [member for member in roster if _existing(state, member) is None]
    return {
        "ok": True,
        "nivel_ficha": current,
        "neutralizacoes_duraveis": count,
        "nivel_desbloqueado_por_marcos": unlocked,
        "niveis_pendentes_de_aplicacao": max(0, unlocked - current),
        "proximo_nivel": unlocked + 1 if count < MAX_NEUTRALIZATIONS else None,
        "restantes": remaining,
        "concluido": count == MAX_NEUTRALIZATIONS,
        "regra": (
            "cada membro único neutralizado de forma canônica e durável desbloqueia um nível; "
            "a aplicação mecânica da ficha continua separada"
        ),
        "fontes_lidas": [POLICY.as_posix(), ROSTER.as_posix(), STATE.as_posix(), SHEET.as_posix()],
    }


def prepare(
    repo: Path,
    member: str,
    kind: str,
    source: str,
    evidence: str,
    *,
    session: int | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    member = _member_id(member)
    if session is not None:
        _integer(session, "sessao", 1)
    if note is not None:
        note = _text(note, "nota", maximum=MAX_NOTE_CHARS)

    policy = load_policy(repo)
    roster = load_roster(repo)
    state = load_state(repo, roster)
    current = _sheet_level(repo)
    if member not in roster:
        raise JuppongatanaProgressionError(f"membro não pertence à Juppongatana: {member}")
    if kind not in DURABLE_TYPES:
        raise JuppongatanaProgressionError(
            "tipo não é neutralização durável; derrotas, fugas e objetivos frustrados não contam"
        )
    if _existing(state, member) is not None:
        raise JuppongatanaProgressionError(f"{member} já consumiu seu único milestone")
    count = len(state["neutralizacoes"])
    if count >= MAX_NEUTRALIZATIONS:
        raise JuppongatanaProgressionError("todos os dez milestones já foram consumidos")
    if BASE_LEVEL < current <= FINAL_LEVEL and current > BASE_LEVEL + count:
        raise JuppongatanaProgressionError(
            "ficha avançou além dos milestones registrados na faixa 8–17; corrija a divergência antes de continuar"
        )

    source_rel, evidence_text, source_bytes = _source_evidence(repo, source, evidence)
    policy_bytes = (repo / POLICY).read_bytes()
    roster_bytes = (repo / ROSTER).read_bytes()
    state_bytes = (repo / STATE).read_bytes()
    sheet_bytes = (repo / SHEET).read_bytes()
    prep = _preparation_id(
        policy_bytes,
        roster_bytes,
        state_bytes,
        sheet_bytes,
        source_bytes,
        member=member,
        kind=kind,
        source=source_rel,
        evidence=evidence_text,
        session=session,
        note=note,
    )
    order = count + 1
    target = BASE_LEVEL + order
    record: dict[str, Any] = {
        "ordem": order,
        "membro": member,
        "tipo": kind,
        "fonte": source_rel,
        "evidencia": evidence_text,
        "nivel_desbloqueado": target,
        "preparacao_id": prep,
    }
    if session is not None:
        record["sessao"] = session
    if note is not None:
        record["nota"] = note
    return {
        "ok": True,
        "fase": "preparacao",
        "preparacao_id": prep,
        "milestone": record,
        "nivel_ficha": current,
        "nivel_desbloqueado": target,
        "aplicacao_mecanica_pendente": current < target,
        "mutacoes_aplicadas": False,
        "regra": "confirmar registra somente o milestone; não altera automaticamente a ficha",
        "fontes_lidas": [POLICY.as_posix(), ROSTER.as_posix(), STATE.as_posix(), SHEET.as_posix(), source_rel],
    }


def confirm(
    repo: Path,
    preparation_id: str,
    member: str,
    kind: str,
    source: str,
    evidence: str,
    *,
    session: int | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    expected = _text(preparation_id, "preparacao_id")
    if not PREPARATION_RE.fullmatch(expected):
        raise JuppongatanaProgressionError("preparacao_id deve ter 24 caracteres hexadecimais")
    member = _member_id(member)
    roster = load_roster(repo)
    state = load_state(repo, roster)
    existing = _existing(state, member)
    if existing is not None:
        if existing.get("preparacao_id") == expected:
            current = _sheet_level(repo)
            return {
                "ok": True,
                "fase": "confirmacao",
                "criado": False,
                "motivo": "milestone_ja_registrado",
                "milestone": existing,
                "nivel_ficha": current,
                "nivel_desbloqueado": existing["nivel_desbloqueado"],
                "aplicacao_mecanica_pendente": current < existing["nivel_desbloqueado"],
                "fontes_lidas": [ROSTER.as_posix(), STATE.as_posix(), SHEET.as_posix()],
            }
        raise JuppongatanaProgressionError(f"{member} já consumiu seu único milestone")

    fresh = prepare(
        repo,
        member,
        kind,
        source,
        evidence,
        session=session,
        note=note,
    )
    if fresh["preparacao_id"] != expected:
        raise JuppongatanaProgressionError(
            "preparação ficou obsoleta; refaça `preparar` antes de confirmar"
        )

    state = load_state(repo, roster)
    state["neutralizacoes"].append(fresh["milestone"])
    _atomic(repo / STATE, state)
    return {
        **fresh,
        "fase": "confirmacao",
        "criado": True,
        "mutacoes_aplicadas": True,
        "arquivos_alterados": [STATE.as_posix()],
    }


def validate_repo(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    members = 0
    neutralizations = 0
    pending = 0
    try:
        policy = load_policy(repo)
        roster = load_roster(repo)
        state = load_state(repo, roster)
        current = _sheet_level(repo)
        members = len(roster)
        neutralizations = len(state["neutralizacoes"])
        unlocked = BASE_LEVEL + neutralizations
        pending = max(0, unlocked - current)

        agents = _map(_load(repo / AGENTS), AGENTS.as_posix())
        strategic = _map(agents.get("agentes"), "agentes.agentes")
        for member_id, meta in roster.items():
            agent = strategic.get(member_id)
            if not isinstance(agent, dict) or agent.get("tipo") != "npc":
                errors.append(f"membro sem agente estratégico NPC: {member_id}")
                continue
            if agent.get("nome") != meta["nome"]:
                errors.append(f"nome do agente diverge da política: {member_id}")

        if current < BASE_LEVEL:
            errors.append(f"Ren está abaixo do nível-base {BASE_LEVEL}")
        if BASE_LEVEL < current <= FINAL_LEVEL and current > unlocked:
            errors.append(
                f"ficha nível {current} excede nível {unlocked} desbloqueado pelos milestones Juppongatana"
            )

        for item in state["neutralizacoes"]:
            try:
                _source_evidence(repo, item["fonte"], item["evidencia"])
            except JuppongatanaProgressionError as exc:
                errors.append(f"milestone {item['membro']}: {exc}")
    except JuppongatanaProgressionError as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "membros": members,
        "neutralizacoes": neutralizations,
        "niveis_pendentes": pending,
        "erros": list(dict.fromkeys(errors)),
        "fontes_lidas": [POLICY.as_posix(), ROSTER.as_posix(), STATE.as_posix(), SHEET.as_posix(), AGENTS.as_posix()],
    }


def _dump(value: Any) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("status")
    sub.add_parser("check")

    prepare_parser = sub.add_parser("preparar")
    confirm_parser = sub.add_parser("confirmar")
    for command in (prepare_parser, confirm_parser):
        command.add_argument("membro")
        command.add_argument("--tipo", choices=DURABLE_TYPES, required=True)
        command.add_argument("--fonte", required=True)
        command.add_argument("--evidencia", required=True)
        command.add_argument("--sessao", type=int)
        command.add_argument("--nota")
    confirm_parser.add_argument("--preparacao-id", required=True)

    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.comando == "status":
            result = status(repo)
        elif args.comando == "check":
            result = validate_repo(repo)
        elif args.comando == "preparar":
            result = prepare(
                repo,
                args.membro,
                args.tipo,
                args.fonte,
                args.evidencia,
                session=args.sessao,
                note=args.nota,
            )
        else:
            result = confirm(
                repo,
                args.preparacao_id,
                args.membro,
                args.tipo,
                args.fonte,
                args.evidencia,
                session=args.sessao,
                note=args.nota,
            )
        print(_dump(result), end="")
        return 0 if result.get("ok") else 1
    except JuppongatanaProgressionError as exc:
        print(_dump({"ok": False, "erro": str(exc)}), end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
