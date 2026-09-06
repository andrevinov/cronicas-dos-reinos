#!/usr/bin/env python3
"""Aceitação read-only da experiência integrada e da documentação operacional.

O checker valida o piloto instalado e as rotas públicas. Episódios narrados são
avaliados separadamente: campos estruturados não satisfazem um critério sem um
trecho literal da narração correspondente.
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
from typing import Any

import yaml

import personalidade_decisoria


ROOT = Path(__file__).resolve().parents[1]
CONTRACT = Path("baseline/nv12-experiencia-integrada.yaml")
SCHEMA = 1
EPISODE_SCHEMA = 1
REQUIRED_SYSTEMS = {"memoria", "personalidade", "iniciativa", "consequencia"}


class IntegratedExperienceError(ValueError):
    """O contrato, o piloto ou a evidência narrativa é inconsistente."""


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IntegratedExperienceError(f"{label} deve ser mapa")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise IntegratedExperienceError(f"{label} deve ser lista")
    return value


def _text(value: Any, label: str, *, minimum: int = 1) -> str:
    if not isinstance(value, str) or len(value.strip()) < minimum:
        raise IntegratedExperienceError(f"{label} deve ser texto com ao menos {minimum} caracteres")
    return value.strip()


def _load_yaml(path: Path, label: str) -> dict[str, Any]:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise IntegratedExperienceError(f"não foi possível ler {label}: {exc}") from exc
    return _map(value, label)


def load_contract(repo: Path = ROOT) -> dict[str, Any]:
    contract = _load_yaml(Path(repo) / CONTRACT, CONTRACT.as_posix())
    if contract.get("schema_experiencia_integrada") != SCHEMA:
        raise IntegratedExperienceError("contrato integrado deve usar schema 1")
    comparison = _map(contract.get("comparacao"), "comparacao")
    before = _map(comparison.get("antes"), "comparacao.antes")
    after = _map(comparison.get("depois"), "comparacao.depois")
    if before.get("cobertura") != "componentes_e_pares_isolados":
        raise IntegratedExperienceError("baseline anterior precisa declarar sua cobertura limitada")
    if after.get("cobertura") != "episodio_integrado_multiturno":
        raise IntegratedExperienceError("estado posterior precisa exigir episódio integrado")
    episode = _map(contract.get("episodio"), "episodio")
    if type(episode.get("minimo_turnos")) is not int or episode["minimo_turnos"] < 5:
        raise IntegratedExperienceError("episódio integrado exige ao menos cinco turnos")
    milestones = _list(episode.get("marcos_obrigatorios"), "episodio.marcos_obrigatorios")
    if len(milestones) != len(set(milestones)) or len(milestones) < 6:
        raise IntegratedExperienceError("marcos do episódio devem ser únicos e cobrir o fluxo completo")
    systems = set(_list(episode.get("sistemas_com_evidencia_narrativa"), "episodio.sistemas"))
    if systems != REQUIRED_SYSTEMS:
        raise IntegratedExperienceError("avaliação narrativa deve cobrir memória, personalidade, iniciativa e consequência")
    if episode.get("consultas_manuais_permitidas") != 0:
        raise IntegratedExperienceError("composição do hot path não pode depender de consulta manual")
    if not all(_map(contract.get("invariantes"), "invariantes").values()):
        raise IntegratedExperienceError("todos os invariantes da adoção precisam permanecer ativos")
    return contract


def _indexed_path(index: dict[str, Any], plural: str, identity: str) -> str:
    entries = _map(index.get(plural), plural)
    entry = _map(entries.get(identity), f"{plural}.{identity}")
    return _text(entry.get("arquivo"), f"{plural}.{identity}.arquivo")


def validate_cast(repo: Path, contract: dict[str, Any]) -> list[dict[str, Any]]:
    adoption = _map(contract.get("adocao_controlada"), "adocao_controlada")
    cast = _list(adoption.get("elenco_inicial"), "adocao_controlada.elenco_inicial")
    if not 1 <= len(cast) <= 3:
        raise IntegratedExperienceError("piloto deve permanecer restrito a um, dois ou três personagens")
    npc_index = _load_yaml(repo / "estado/npcs/index.yaml", "índice de NPCs")
    relation_index = _load_yaml(repo / "estado/relacoes/index.yaml", "índice de relações")
    texture_index = _load_yaml(repo / "cenario/texturas/index.yaml", "índice de texturas")
    textures = _map(texture_index.get("npcs"), "texturas.npcs")
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for position, raw in enumerate(cast):
        entry = _map(raw, f"elenco_inicial[{position}]")
        if set(entry) != {"id", "npc", "relacao"}:
            raise IntegratedExperienceError("entrada do piloto exige somente id, npc e relacao")
        identity = _text(entry.get("id"), "elenco.id")
        if identity in seen:
            raise IntegratedExperienceError(f"ID duplicado no piloto: {identity}")
        seen.add(identity)
        npc_path = _indexed_path(npc_index, "npcs", identity)
        relation_path = _indexed_path(relation_index, "relacoes", identity)
        if npc_path != entry["npc"] or relation_path != entry["relacao"]:
            raise IntegratedExperienceError(f"fontes dirigidas divergiram para {identity}")
        if not (repo / npc_path).is_file() or not (repo / relation_path).is_file():
            raise IntegratedExperienceError(f"fontes do piloto ausentes para {identity}")
        texture = _map(textures.get(identity), f"texturas.npcs.{identity}")
        role = _map(texture.get("papel_conversacional"), f"papel_conversacional.{identity}")
        profile = personalidade_decisoria.project(identity, role)
        if profile is None:
            raise IntegratedExperienceError(f"{identity} não possui perfil decisório curado")
        result.append({"id": identity, "npc": npc_path, "relacao": relation_path,
                       "papel": role.get("papel"), "lacunas": sorted(profile["lacunas"])})
    return result


def validate_operational_docs(repo: Path, contract: dict[str, Any]) -> list[str]:
    checked: list[str] = []
    for position, raw in enumerate(_list(contract.get("documentacao_operacional"), "documentacao_operacional")):
        entry = _map(raw, f"documentacao_operacional[{position}]")
        relative = _text(entry.get("arquivo"), "documentacao_operacional.arquivo")
        path = (repo / relative).resolve()
        if not path.is_relative_to(repo.resolve()) or not path.is_file():
            raise IntegratedExperienceError(f"documento operacional ausente: {relative}")
        text = path.read_text(encoding="utf-8")
        for required in _list(entry.get("exige"), f"{relative}.exige"):
            required = _text(required, f"{relative}.exige")
            if required not in text:
                raise IntegratedExperienceError(f"{relative}: instrução vigente ausente: {required}")
        for forbidden in _list(entry.get("proibe"), f"{relative}.proibe"):
            forbidden = _text(forbidden, f"{relative}.proibe").replace("\\n", "\n")
            if forbidden in text:
                raise IntegratedExperienceError(f"{relative}: instrução obsoleta ainda ativa: {forbidden!r}")
        checked.append(relative)
    return checked


def check(repo: Path = ROOT) -> dict[str, Any]:
    repo = Path(repo).resolve()
    try:
        contract = load_contract(repo)
        cast = validate_cast(repo, contract)
        documents = validate_operational_docs(repo, contract)
    except IntegratedExperienceError as exc:
        return {"schema_experiencia_integrada": SCHEMA, "ok": False, "erros": [str(exc)]}
    comparison = copy.deepcopy(contract["comparacao"])
    return {
        "schema_experiencia_integrada": SCHEMA,
        "ok": True,
        "erros": [],
        "comparacao": comparison,
        "adocao_controlada": {"elenco": cast, "quantidade": len(cast), "save_alterado": False},
        "documentos_operacionais": documents,
        "avaliacao": {
            "episodio_multiturno": True,
            "narracao_literal_obrigatoria": True,
            "consulta_manual_obrigatoria": False,
            "retomada_sem_transcricao": True,
        },
    }


def evaluate_episode(value: Any, contract: dict[str, Any]) -> dict[str, Any]:
    """Confere cobertura e evidência literal; não finge interpretar qualidade."""
    episode = copy.deepcopy(_map(value, "episodio narrado"))
    expected = {
        "schema_episodio_integrado", "cenario_id", "elenco", "turnos",
        "evidencias_narrativas", "retomada_fria", "consultas_manuais", "preservacao",
    }
    if set(episode) != expected or episode.get("schema_episodio_integrado") != EPISODE_SCHEMA:
        raise IntegratedExperienceError("episódio narrado possui schema ou campos divergentes")
    _text(episode.get("cenario_id"), "cenario_id")
    allowed = {item["id"] for item in contract["adocao_controlada"]["elenco_inicial"]}
    cast = _list(episode.get("elenco"), "elenco")
    if not cast or len(cast) != len(set(cast)) or not set(cast) <= allowed:
        raise IntegratedExperienceError("episódio usa elenco fora do piloto controlado")
    turns = _list(episode.get("turnos"), "turnos")
    minimum = contract["episodio"]["minimo_turnos"]
    if len(turns) < minimum:
        raise IntegratedExperienceError(f"episódio precisa de ao menos {minimum} turnos")
    by_id: dict[str, dict[str, Any]] = {}
    observed: set[str] = set()
    for position, raw in enumerate(turns):
        turn = _map(raw, f"turnos[{position}]")
        if set(turn) != {"id", "marcos", "jogador", "narracao", "resumo"}:
            raise IntegratedExperienceError("turno exige id, marcos, jogador, narracao e resumo")
        turn_id = _text(turn.get("id"), "turno.id")
        if turn_id in by_id:
            raise IntegratedExperienceError(f"turno duplicado: {turn_id}")
        by_id[turn_id] = turn
        observed.update(_text(item, "turno.marco") for item in _list(turn.get("marcos"), "turno.marcos"))
        _text(turn.get("jogador"), "turno.jogador")
        _text(turn.get("narracao"), "turno.narracao", minimum=30)
        _text(turn.get("resumo"), "turno.resumo", minimum=10)
    required_milestones = set(contract["episodio"]["marcos_obrigatorios"])
    missing_milestones = sorted(required_milestones - observed)
    if missing_milestones:
        raise IntegratedExperienceError(f"marcos não exercitados: {missing_milestones}")
    evidence = _list(episode.get("evidencias_narrativas"), "evidencias_narrativas")
    covered: set[str] = set()
    evidence_ids: set[str] = set()
    for position, raw in enumerate(evidence):
        item = _map(raw, f"evidencias_narrativas[{position}]")
        if set(item) != {"id", "sistema", "turno", "trecho", "avaliador", "justificativa"}:
            raise IntegratedExperienceError("evidência narrativa possui campos divergentes")
        evidence_id = _text(item.get("id"), "evidencia.id")
        if evidence_id in evidence_ids:
            raise IntegratedExperienceError(f"evidência duplicada: {evidence_id}")
        evidence_ids.add(evidence_id)
        system = _text(item.get("sistema"), "evidencia.sistema")
        if system not in REQUIRED_SYSTEMS:
            raise IntegratedExperienceError(f"sistema narrativo desconhecido: {system}")
        turn_id = _text(item.get("turno"), "evidencia.turno")
        if turn_id not in by_id:
            raise IntegratedExperienceError(f"evidência aponta turno ausente: {turn_id}")
        quote = _text(item.get("trecho"), "evidencia.trecho", minimum=12)
        if quote not in by_id[turn_id]["narracao"]:
            raise IntegratedExperienceError(
                f"evidência {evidence_id} não aparece literalmente na narração produzida"
            )
        _text(item.get("avaliador"), "evidencia.avaliador", minimum=5)
        _text(item.get("justificativa"), "evidencia.justificativa", minimum=30)
        covered.add(system)
    missing_systems = sorted(REQUIRED_SYSTEMS - covered)
    if missing_systems:
        raise IntegratedExperienceError(f"sistemas sem evidência narrativa: {missing_systems}")
    resume = _map(episode.get("retomada_fria"), "retomada_fria")
    if set(resume) != {"processo_novo", "contexto_anterior_fornecido", "transcricao_lida"} or resume != {
        "processo_novo": True, "contexto_anterior_fornecido": False, "transcricao_lida": False,
    }:
        raise IntegratedExperienceError("retomada fria exige processo novo, sem chat anterior nem transcrição")
    if _list(episode.get("consultas_manuais"), "consultas_manuais"):
        raise IntegratedExperienceError("episódio integrado não pode depender de consulta manual complementar")
    preservation = _map(episode.get("preservacao"), "preservacao")
    if set(preservation) != {"ids_antes", "ids_depois", "historico_append_only", "save_original_inalterado"}:
        raise IntegratedExperienceError("preservação do episódio possui campos divergentes")
    if preservation["ids_antes"] != preservation["ids_depois"] or not preservation.get("historico_append_only") or not preservation.get("save_original_inalterado"):
        raise IntegratedExperienceError("episódio não preservou IDs, histórico e save original")
    return {
        "schema_avaliacao_experiencia_integrada": 1,
        "ok": True,
        "cenario_id": episode["cenario_id"],
        "turnos": len(turns),
        "marcos": sorted(observed),
        "sistemas_com_evidencia_narrativa": sorted(covered),
        "evidencias": len(evidence),
        "retomada_fria": True,
        "consultas_manuais": 0,
        "preservacao": copy.deepcopy(preservation),
        "limite": (
            "A checagem prova endereço e literalidade da narração anotada; "
            "qualidade semântica de rollout real continua exigindo revisão pós-hoc."
        ),
    }


def _dump(value: dict[str, Any], as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(yaml.safe_dump(value, allow_unicode=True, sort_keys=False).rstrip())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("check", help="valida piloto, comparação e documentos ativos sem alterar o save")
    evaluate = sub.add_parser("avaliar", help="avalia um episódio narrado anotado")
    evaluate.add_argument("arquivo", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo = args.repo.resolve()
    if args.comando == "check":
        report = check(repo)
        _dump(report, args.json)
        return 0 if report["ok"] else 1
    try:
        contract = load_contract(repo)
        episode = _load_yaml(args.arquivo.resolve(), str(args.arquivo))
        report = evaluate_episode(episode, contract)
    except IntegratedExperienceError as exc:
        report = {"schema_avaliacao_experiencia_integrada": 1, "ok": False, "erros": [str(exc)]}
    _dump(report, args.json)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
