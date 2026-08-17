#!/usr/bin/env python3
"""Porta única de contexto com escada executável, orçamento rígido e transcrições frias.

O motor fragmentado da Etapa 6 continua em `contexto_core.py`. Esta porta soma:

- sobreposição de `runtime/eventos-pendentes.jsonl`;
- retomada compacta por `sessoes/NNN/handoff.yaml`;
- consulta de sessão sem abrir transcrição;
- textura narrativa compacta e dirigida para NPCs/locais;
- busca histórica em dois degraus: estruturado primeiro, transcrição só mediante
  `--historico --transcricoes`;
- política mecânica de L1–L4T com teto de bytes e justificativa para escaladas.

L0 não é um comando: significa responder com o contexto já presente, sem ferramenta.
L5 também não é um comando local: significa recorrer a fonte externa/autorizada só
quando a memória interna realmente não resolver a lacuna.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import contexto_core as core
import politica_acesso as politica
import recursos
import sessoes as memoria_sessoes
import texturas
import transacoes

DEFAULT_MAX_BYTES = core.DEFAULT_MAX_BYTES
HARD_MAX_BYTES = core.HARD_MAX_BYTES
QUERY_LOG = core.QUERY_LOG
TEXT_SUFFIXES = core.TEXT_SUFFIXES
SKIP_DIRS = core.SKIP_DIRS

# Reexporta helpers usados por testes/ferramentas existentes.
load_yaml = core.load_yaml
normalize = core.normalize
truncate_text = core.truncate_text
compact_value = core.compact_value
serialize = core.serialize
fit_budget = core.fit_budget
entity_score = core.entity_score
resolve_entity = core.resolve_entity
compact_relation = core.compact_relation
split_markdown_sections = core.split_markdown_sections
section_score = core.section_score
search_markdown_files = core.search_markdown_files
envelope = core.envelope
log_query = core.log_query
command_rule = core.command_rule


def _pending(repo: Path) -> list[dict[str, Any]]:
    return transacoes.load_pending(repo)


def _has_overlay(result: dict[str, Any]) -> bool:
    return isinstance(result, dict) and "sobreposicao_transacional" in result


def _add_pending_source(data: dict[str, Any]) -> None:
    sources = list(data.get("fontes") or [])
    pending = transacoes.PENDING_PATH.as_posix()
    if pending not in sources:
        sources.append(pending)
    data["fontes"] = sources


def _add_sources(data: dict[str, Any], sources: list[str]) -> None:
    current = list(data.get("fontes") or [])
    data["fontes"] = list(dict.fromkeys(current + sources))


def _resume_context_view(context: dict[str, Any]) -> dict[str, Any]:
    """Recorte efetivo necessário para retomar sem estourar o orçamento L2.

    A projeção é feita *depois* de aplicar os eventos pendentes, portanto mantém
    tipos estruturados (PV/Ki continuam mapas, números continuam números) em vez
    de depender da compactação genérica de `fit_budget`.
    """
    keys = (
        "sessao",
        "personagem",
        "recursos",
        "efeitos_temporarios",
        "tempo",
        "localizacao",
        "sobreposicao_transacional",
    )
    return {key: context[key] for key in keys if key in context}


def _resume_scene_view(scene: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in (
        "modo",
        "localizacao",
        "tempo",
        "mecanica_imediata",
        "efeitos_temporarios",
        "sobreposicao_transacional",
    ):
        if key in scene:
            result[key] = scene[key]
    if "resumo_imediato" in scene:
        result["resumo_imediato"] = truncate_text(scene.get("resumo_imediato", ""), 1400)
    if "prazos_e_alertas" in scene:
        result["prazos_e_alertas"] = truncate_text(scene.get("prazos_e_alertas", ""), 900)
    return result


def _resume_memory_view(memory: Any) -> dict[str, Any] | None:
    """Remove do handoff o que runtime/cena já disseram na mesma resposta."""
    if not isinstance(memory, dict):
        return None
    checkpoint = memory.get("checkpoint") or {}
    checkpoint_view = (
        {
            key: checkpoint.get(key)
            for key in ("tipo", "estado", "modo")
            if key in checkpoint
        }
        if isinstance(checkpoint, dict)
        else {}
    )
    recent: list[dict[str, Any]] = []
    for item in list(memory.get("eventos_recentes") or [])[-3:]:
        if not isinstance(item, dict):
            continue
        recent.append(
            {
                "transacao": item.get("transacao"),
                "resumo": truncate_text(item.get("resumo", ""), 260),
            }
        )
    result: dict[str, Any] = {}
    if checkpoint_view:
        result["checkpoint"] = checkpoint_view
    if recent:
        result["eventos_recentes"] = recent
    return result or None


def command_status(repo: Path) -> dict[str, Any]:
    data = core.command_status(repo)
    context = data.get("resultado")
    if not isinstance(context, dict):
        return data
    records = _pending(repo)
    effective, _, _ = transacoes.overlay_runtime(context, None, records)
    recursos.apply_pending_effects(effective, None, records)
    data["resultado"] = effective
    if _has_overlay(effective):
        _add_pending_source(data)
    return data


def command_scene(repo: Path) -> dict[str, Any]:
    data = core.command_scene(repo)
    result = data.get("resultado") or {}
    context = result.get("contexto") if isinstance(result, dict) else None
    scene = result.get("cena") if isinstance(result, dict) else None
    if not isinstance(context, dict) or not isinstance(scene, dict):
        return data
    records = _pending(repo)
    effective_context, effective_scene, _ = transacoes.overlay_runtime(
        context, scene, records
    )
    recursos.apply_pending_effects(effective_context, effective_scene, records)
    data["resultado"] = {"contexto": effective_context, "cena": effective_scene}
    if _has_overlay(effective_context):
        _add_pending_source(data)
    return data


def command_resume(repo: Path) -> dict[str, Any]:
    result, sources = memoria_sessoes.resume_view(repo)
    context = result.get("contexto")
    scene = result.get("cena")
    records = _pending(repo)
    if isinstance(context, dict) and isinstance(scene, dict):
        effective_context, effective_scene, _ = transacoes.overlay_runtime(context, scene, records)
        recursos.apply_pending_effects(effective_context, effective_scene, records)
        result["contexto"] = _resume_context_view(effective_context)
        result["cena"] = _resume_scene_view(effective_scene or {})
    result["memoria_consolidada"] = _resume_memory_view(result.get("memoria_consolidada"))

    session = result.get("sessao")
    recent = (
        transacoes.pending_for_session(records, session)[-4:]
        if isinstance(session, int)
        else records[-4:]
    )
    result["eventos_pendentes_recentes"] = [
        {
            "id": item.get("id"),
            "resumo": core.truncate_text(item.get("resumo", ""), 320),
            "modo": item.get("modo"),
        }
        for item in recent
    ]
    data = envelope("retomada", None, "L2", sources, result)
    if recent:
        _add_pending_source(data)
    return data


def _resolve_session(repo: Path, term: str) -> int:
    normalized = normalize(term)
    if normalized in {"atual", "current"}:
        return memoria_sessoes.current_session(repo)
    try:
        return int(term)
    except ValueError as exc:
        raise ValueError("sessao precisa ser número inteiro ou 'atual'") from exc


def command_session(repo: Path, term: str) -> dict[str, Any]:
    session = _resolve_session(repo, term)
    result, sources = memoria_sessoes.session_snapshot(repo, session)
    return envelope("sessao", term, "L2", sources, result)


def command_relation(repo: Path, term: str) -> dict[str, Any]:
    data = core.command_relation(repo, term)
    result = data.get("resultado") or {}
    if not isinstance(result, dict) or not result.get("encontrado"):
        return data
    relation = result.get("relacao")
    entity_id = result.get("id")
    if not isinstance(relation, dict) or not isinstance(entity_id, str):
        return data
    effective, applied = transacoes.overlay_target(
        relation, _pending(repo), f"relacao:{entity_id}"
    )
    result["relacao"] = effective
    if applied:
        result["deltas_pendentes_aplicados"] = applied
        _add_pending_source(data)
    return data


def command_npc(repo: Path, term: str) -> dict[str, Any]:
    data = core.command_npc(repo, term)
    result = data.get("resultado") or {}
    if not isinstance(result, dict):
        result = {"encontrado": False, "medidores": None, "relacao": None}
        data["resultado"] = result

    # A textura é uma extensão da mesma consulta dirigida; não exige uma segunda
    # inferência nem busca ampla. Também permite que NPCs ainda sem medidor tenham
    # presença narrativa compacta.
    texture, texture_sources, texture_candidates = texturas.lookup(repo, "npcs", term)
    if texture is not None:
        result["textura_narrativa"] = texture
        result["encontrado"] = True
        _add_sources(data, texture_sources)
    elif texture_candidates and not result.get("encontrado"):
        existing = list(result.get("candidatos") or [])
        result["candidatos"] = list(dict.fromkeys(existing + texture_candidates))[:8]

    if not result.get("encontrado"):
        return data

    records = _pending(repo)
    applied_total = 0

    med = result.get("medidores")
    if isinstance(med, dict) and isinstance(med.get("id"), str) and isinstance(med.get("dados"), dict):
        effective, applied = transacoes.overlay_target(
            med["dados"], records, f"npc:{med['id']}"
        )
        med["dados"] = effective
        applied_total += applied

    relation = result.get("relacao")
    if (
        isinstance(relation, dict)
        and isinstance(relation.get("id"), str)
        and isinstance(relation.get("dados"), dict)
    ):
        effective, applied = transacoes.overlay_target(
            relation["dados"], records, f"relacao:{relation['id']}"
        )
        relation["dados"] = effective
        applied_total += applied

    if applied_total:
        result["deltas_pendentes_aplicados"] = applied_total
        _add_pending_source(data)
    return data


def command_local(repo: Path, term: str) -> dict[str, Any]:
    texture, sources, candidates = texturas.lookup(repo, "locais", term)
    result: dict[str, Any] = {
        "encontrado": texture is not None,
        "textura_narrativa": texture,
    }
    if texture is None:
        result["candidatos"] = candidates
    return envelope("local", term, "L2", sources or [texturas.INDEX_PATH.as_posix()], result)


def command_resource(repo: Path, term: str) -> dict[str, Any]:
    return recursos.command_resource(repo, term, _pending(repo))


def command_knowledge(repo: Path, term: str) -> dict[str, Any]:
    data = core.command_knowledge(repo, term)
    result = data.get("resultado") or {}
    if not isinstance(result, dict):
        return data
    pending = [
        item
        for item in transacoes.search_pending(
            _pending(repo), term, reserved=False, target_prefix="conhecimento", limit=4
        )
        if item.get("deltas")
    ]
    if pending:
        result["pendentes"] = pending
        result["encontrado"] = True
        _add_pending_source(data)
    return data


def _iter_text_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def iter_search_files(
    repo: Path,
    *,
    reserved: bool,
    historical: bool,
    transcripts: bool = False,
) -> Iterable[Path]:
    """Escopo público de busca; histórico não implica transcrição."""
    roots = ["estado", "personagens/jogador", "cenario", "regras", "narracao"]
    if reserved:
        roots.append("narrador")
    for root_name in roots:
        yield from _iter_text_files(repo / root_name)

    if historical:
        history = repo / "historico"
        if history.exists():
            for path in history.rglob("*"):
                if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                    yield path

    sessions = repo / "sessoes"
    if sessions.exists():
        for session_dir in sessions.iterdir():
            if not session_dir.is_dir() or not session_dir.name.isdigit():
                continue
            for name in (
                "handoff.yaml",
                "resumo.md",
                "alteracoes-de-estado.yaml",
                "alteracoes-transacionais.yaml",
                "consequencias.md",
                "experiencia.md",
                "correcoes-de-continuidade.md",
            ):
                path = session_dir / name
                if path.is_file():
                    yield path
            if transcripts:
                path = session_dir / "transcricao.md"
                if path.is_file():
                    yield path


def generic_search(
    repo: Path,
    term: str,
    *,
    reserved: bool,
    historical: bool,
    transcripts: bool = False,
    limit: int = 8,
) -> list[dict[str, Any]]:
    query = normalize(term)
    tokens = [token for token in query.split() if token]
    if not tokens:
        return []
    matches: list[tuple[int, str, int, str]] = []
    for path in iter_search_files(
        repo, reserved=reserved, historical=historical, transcripts=transcripts
    ):
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        rel = path.relative_to(repo).as_posix()
        for index, line in enumerate(lines):
            line_n = normalize(line)
            if not all(token in line_n for token in tokens):
                continue
            score = 20 + sum(line_n.count(token) for token in tokens)
            start = max(0, index - 1)
            end = min(len(lines), index + 2)
            snippet = " ".join(part.strip() for part in lines[start:end] if part.strip())
            matches.append((score, rel, index + 1, truncate_text(snippet, 650)))
    matches.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [
        {"arquivo": rel, "linha": line, "trecho": snippet}
        for _, rel, line, snippet in matches[:limit]
    ]


def command_search(
    repo: Path,
    term: str,
    *,
    reserved: bool,
    historical: bool,
    transcripts: bool = False,
) -> dict[str, Any]:
    matches = generic_search(
        repo,
        term,
        reserved=reserved,
        historical=historical,
        transcripts=transcripts,
        limit=8,
    )
    level = "L4T" if transcripts else ("L4" if historical else "L3")
    data = envelope(
        "buscar",
        term,
        level,
        list(dict.fromkeys(item["arquivo"] for item in matches)),
        {
            "escopo": {
                "reservado": reserved,
                "historico_estruturado": historical,
                "transcricoes_frias": transcripts,
            },
            "encontrado": bool(matches),
            "ocorrencias": matches,
        },
    )

    pending = transacoes.search_pending(_pending(repo), term, reserved=reserved, limit=5)
    if pending:
        result = data["resultado"]
        occurrences = [
            {
                "arquivo": transacoes.PENDING_PATH.as_posix(),
                "transacao": item.get("transacao"),
                "sessao": item.get("sessao"),
                "trecho": truncate_text(item.get("resumo", ""), 650),
            }
            for item in pending
        ]
        result["ocorrencias"] = (occurrences + list(result.get("ocorrencias") or []))[:8]
        result["encontrado"] = True
        _add_pending_source(data)
    return data


def _add_escalation_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--apos",
        choices=["L0", "L1", "L2", "L3", "L4"],
        help="declara o último nível que foi insuficiente; não executa consulta extra",
    )
    parser.add_argument(
        "--motivo",
        help="lacuna concreta que justifica a escalada; obrigatório em L3+ e acesso reservado",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="emite JSON em vez de YAML")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help="orçamento solicitado; a política de cada nível pode impor teto menor",
    )
    parser.add_argument(
        "--log-local",
        action="store_true",
        help="opcional: registra metadados locais da consulta; desligado por padrão",
    )
    parser.add_argument(
        "--sem-log",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="L1: somente contexto quente efetivo")
    sub.add_parser("cena", help="L2: contexto quente + cena efetiva")
    sub.add_parser("retomada", help="L2: retoma sessão/cena sem abrir transcrições")

    session = sub.add_parser("sessao", help="L2 atual / L4 histórica: memória compacta de uma sessão")
    session.add_argument("termo", help="número ou 'atual'")
    _add_escalation_arguments(session)

    for name, help_text in (
        ("npc", "L2: medidores, relação atual e textura compacta de um NPC"),
        ("local", "L2: paleta narrativa compacta de um lugar conhecido"),
        ("relacao", "L2: relação atual com uma entidade"),
        ("recurso", "L2: item, habilidade ou recurso da ficha + disponibilidade atual"),
        ("conhecimento", "L2: o que Ren sabe sobre um assunto"),
        ("regra", "L2: trechos das regras internas sobre um assunto"),
    ):
        child = sub.add_parser(name, help=help_text)
        child.add_argument("termo")

    search = sub.add_parser("buscar", help="L3/L4/L4T: busca limitada e escalonada")
    search.add_argument("termo")
    search.add_argument("--reservado", action="store_true", help="inclui narrador/; exige motivo")
    search.add_argument(
        "--historico",
        action="store_true",
        help="L4: inclui histórico estruturado/frio; ainda exclui transcrições",
    )
    search.add_argument(
        "--transcricoes",
        action="store_true",
        help="L4T: inclui transcrições brutas; exige --historico e --apos L4",
    )
    _add_escalation_arguments(search)
    return parser


def _decision_for(repo: Path, args: argparse.Namespace) -> politica.AccessDecision:
    current_session = None
    session_term = None
    historical = False
    transcripts = False
    if args.command == "sessao":
        current_session = memoria_sessoes.current_session(repo)
        session_term = args.termo
    elif args.command == "buscar":
        historical = args.historico
        transcripts = args.transcricoes
    return politica.classify(
        args.command,
        current_session=current_session,
        session_term=session_term,
        historical=historical,
        transcripts=transcripts,
    )


def main() -> int:
    args = build_parser().parse_args()
    repo = args.repo.resolve()
    try:
        if args.command == "buscar" and args.transcricoes and not args.historico:
            raise politica.AccessPolicyError("--transcricoes exige --historico")

        decision = _decision_for(repo, args)
        after = getattr(args, "apos", None)
        reason = getattr(args, "motivo", None)
        reserved = bool(getattr(args, "reservado", False))
        validated_reason = politica.validate_escalation(
            decision,
            after=after,
            reason=reason,
            reserved=reserved,
        )

        if args.command == "status":
            data = command_status(repo)
        elif args.command == "cena":
            data = command_scene(repo)
        elif args.command == "retomada":
            data = command_resume(repo)
        elif args.command == "sessao":
            data = command_session(repo, args.termo)
        elif args.command == "npc":
            data = command_npc(repo, args.termo)
        elif args.command == "local":
            data = command_local(repo, args.termo)
        elif args.command == "relacao":
            data = command_relation(repo, args.termo)
        elif args.command == "recurso":
            data = command_resource(repo, args.termo)
        elif args.command == "conhecimento":
            data = command_knowledge(repo, args.termo)
        elif args.command == "regra":
            data = command_rule(repo, args.termo)
        elif args.command == "buscar":
            data = command_search(
                repo,
                args.termo,
                reserved=args.reservado,
                historical=args.historico,
                transcripts=args.transcricoes,
            )
        else:
            raise politica.AccessPolicyError(f"comando desconhecido: {args.command}")

        data, effective_max = politica.decorate(
            data,
            decision,
            requested_budget=args.max_bytes,
            after=after,
            reason=validated_reason,
        )
    except (
        OSError,
        ValueError,
        yaml.YAMLError,
        memoria_sessoes.SessionMemoryError,
        politica.AccessPolicyError,
    ) as exc:
        print(f"FALHA DE CONSULTA — {exc}", file=sys.stderr)
        return 1

    text, truncated = fit_budget(data, effective_max, args.json)
    output_bytes = len(text.encode("utf-8"))
    if args.log_local and not args.sem_log:
        try:
            log_query(repo, data, output_bytes, truncated)
        except OSError:
            pass
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
