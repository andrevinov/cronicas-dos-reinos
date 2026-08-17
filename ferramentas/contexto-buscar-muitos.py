#!/usr/bin/env python3
"""Busca várias lacunas relacionadas em uma única chamada e um único orçamento.

Esta porta é o equivalente em lote de `contexto.py buscar`: usa a mesma escada
L3/L4/L4T, o mesmo escopo público/reservado/histórico e aplica o teto de bytes ao
resultado completo, não a cada termo isoladamente.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import contexto
import politica_acesso as politica
import transacoes

MIN_TERMS = 2
MAX_TERMS = 5
PER_TERM_LIMIT = 4


def validate_terms(terms: list[str]) -> list[str]:
    cleaned = [" ".join(str(term).split()) for term in terms if str(term).strip()]
    if len(cleaned) < MIN_TERMS:
        raise ValueError(
            f"buscar em lote exige pelo menos {MIN_TERMS} termos relacionados; para uma lacuna use contexto.py buscar"
        )
    if len(cleaned) > MAX_TERMS:
        raise ValueError(f"buscar em lote aceita no máximo {MAX_TERMS} termos por chamada")
    normalized = [contexto.normalize(term) for term in cleaned]
    if len(set(normalized)) != len(normalized):
        raise ValueError("buscar em lote recebeu termos duplicados")
    return cleaned


def _level(*, historical: bool, transcripts: bool) -> str:
    return "L4T" if transcripts else ("L4" if historical else "L3")


def _pending_occurrences(
    records: list[dict[str, Any]], term: str, *, reserved: bool
) -> list[dict[str, Any]]:
    pending = transacoes.search_pending(
        records,
        term,
        reserved=reserved,
        limit=PER_TERM_LIMIT,
    )
    return [
        {
            "arquivo": transacoes.PENDING_PATH.as_posix(),
            "transacao": item.get("transacao"),
            "sessao": item.get("sessao"),
            "trecho": contexto.truncate_text(item.get("resumo", ""), 650),
        }
        for item in pending
    ]


def command_search_many(
    repo: Path,
    terms: list[str],
    *,
    reserved: bool,
    historical: bool,
    transcripts: bool = False,
) -> dict[str, Any]:
    terms = validate_terms(terms)
    records = transacoes.load_pending(repo)
    groups: list[dict[str, Any]] = []
    sources: list[str] = []

    for term in terms:
        current = contexto.generic_search(
            repo,
            term,
            reserved=reserved,
            historical=historical,
            transcripts=transcripts,
            limit=PER_TERM_LIMIT,
        )
        pending = _pending_occurrences(records, term, reserved=reserved)
        occurrences = (pending + current)[:PER_TERM_LIMIT]
        for item in occurrences:
            source = item.get("arquivo")
            if isinstance(source, str) and source not in sources:
                sources.append(source)
        groups.append(
            {
                "termo": term,
                "encontrado": bool(occurrences),
                "ocorrencias": occurrences,
            }
        )

    missing = [group["termo"] for group in groups if not group["encontrado"]]
    return {
        "consulta": {"comando": "buscar-muitos", "termos": terms},
        "nivel": _level(historical=historical, transcripts=transcripts),
        "fontes": sources,
        "resultado": {
            "escopo": {
                "reservado": reserved,
                "historico_estruturado": historical,
                "transcricoes_frias": transcripts,
            },
            "quantidade_termos": len(terms),
            "encontrado": any(group["encontrado"] for group in groups),
            "todos_encontrados": not missing,
            "termos_nao_encontrados": missing,
            "resultados": groups,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true", help="emite JSON em vez de YAML")
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=contexto.DEFAULT_MAX_BYTES,
        help="orçamento solicitado para o lote inteiro; a política pode impor teto menor",
    )
    parser.add_argument(
        "--log-local",
        action="store_true",
        help="opcional: registra metadados locais da consulta; desligado por padrão",
    )
    parser.add_argument("--sem-log", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("termos", nargs="+", help="de 2 a 5 lacunas concretas da mesma decisão")
    parser.add_argument("--reservado", action="store_true", help="inclui narrador/; exige motivo")
    parser.add_argument(
        "--historico",
        action="store_true",
        help="L4: inclui histórico estruturado/frio; ainda exclui transcrições",
    )
    parser.add_argument(
        "--transcricoes",
        action="store_true",
        help="L4T: inclui transcrições brutas; exige --historico e --apos L4",
    )
    parser.add_argument(
        "--apos",
        choices=["L0", "L1", "L2", "L3", "L4"],
        help="declara o último nível insuficiente para o lote",
    )
    parser.add_argument(
        "--motivo",
        help="lacuna/decisão concreta que justifica a escalada do lote",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo = args.repo.resolve()
    try:
        terms = validate_terms(args.termos)
        if args.transcricoes and not args.historico:
            raise politica.AccessPolicyError("--transcricoes exige --historico")

        decision = politica.classify(
            "buscar",
            historical=args.historico,
            transcripts=args.transcricoes,
        )
        validated_reason = politica.validate_escalation(
            decision,
            after=args.apos,
            reason=args.motivo,
            reserved=args.reservado,
        )
        data = command_search_many(
            repo,
            terms,
            reserved=args.reservado,
            historical=args.historico,
            transcripts=args.transcricoes,
        )
        data, effective_max = politica.decorate(
            data,
            decision,
            requested_budget=args.max_bytes,
            after=args.apos,
            reason=validated_reason,
        )
    except (OSError, ValueError, transacoes.TransactionError, politica.AccessPolicyError) as exc:
        print(f"FALHA DE CONSULTA — {exc}", file=sys.stderr)
        return 1

    text, truncated = contexto.fit_budget(data, effective_max, args.json)
    output_bytes = len(text.encode("utf-8"))
    if args.log_local and not args.sem_log:
        try:
            contexto.log_query(repo, data, output_bytes, truncated)
        except OSError:
            pass
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
