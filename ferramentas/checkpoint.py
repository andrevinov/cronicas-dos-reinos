#!/usr/bin/env python3
"""Checkpoint canônico + atualização reconstruível da memória compacta.

`consolidar.py` continua responsável pela transação canônica atômica. Este wrapper
é a porta operacional da Etapa 9: depois que a consolidação termina, deriva
`handoff.yaml` e `sessoes/index.yaml` do runtime e do ledger já instalados.

Se o processo cair após o cânone e antes do handoff, nenhum delta é reaplicado:
basta executar o comando novamente ou `sessoes.py bootstrap-atual`, pois a memória
de sessão é cache derivado, não fonte de verdade.
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

import consolidar
import sessoes
import transacoes


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
        temp = Path(handle.name)
    os.replace(temp, path)


def refresh_memory(repo: Path, kind: str) -> dict[str, Any]:
    session = sessoes.current_session(repo)
    context = sessoes.load_yaml(repo / "runtime/contexto.yaml") or {}
    scene = sessoes.load_yaml(repo / "runtime/cena.yaml") or {}
    ledger_path = repo / "sessoes" / f"{session:03d}" / consolidar.LEDGER_NAME
    ledger = sessoes.read_jsonl(ledger_path)
    handoff = sessoes.build_handoff(
        repo,
        session=session,
        kind=kind,
        context=context,
        scene=scene,
        ledger=ledger,
    )
    hpath = repo / sessoes.handoff_rel(session)
    _atomic_text(hpath, sessoes.dump_yaml(handoff))
    index = sessoes.build_index(repo, active_session=session)
    _atomic_text(repo / sessoes.INDEX_PATH, sessoes.dump_yaml(index))
    return {
        "sessao": session,
        "tipo": kind,
        "handoff": hpath.relative_to(repo).as_posix(),
        "indice": sessoes.INDEX_PATH.as_posix(),
        "eventos_recentes": len(handoff.get("eventos_recentes") or []),
    }


def checkpoint(repo: Path, kind: str) -> dict[str, Any]:
    canonical = consolidar.consolidate(repo, kind)
    effective_kind = canonical.get("tipo") or kind
    if effective_kind not in {"cena", "sessao"}:
        effective_kind = kind
    memory = refresh_memory(repo, effective_kind)
    return {"canonico": canonical, "memoria": memory}


def recover(repo: Path) -> dict[str, Any]:
    canonical = consolidar.resume_consolidation(repo)
    if canonical is None:
        memory = refresh_memory(repo, "bootstrap")
        return {"canonico": {"sem_journal": True}, "memoria": memory}
    kind = canonical.get("tipo") or "cena"
    memory = refresh_memory(repo, kind if kind in {"cena", "sessao"} else "cena")
    return {"canonico": canonical, "memoria": memory}


def _current_handoff_errors(repo: Path) -> list[str]:
    errors: list[str] = []
    session = sessoes.current_session(repo)
    path = repo / sessoes.handoff_rel(session)
    if not path.is_file():
        return [
            f"handoff da sessão atual ausente: {sessoes.handoff_rel(session)}; "
            "execute ferramentas/checkpoint.py recuperar"
        ]
    actual = sessoes.load_yaml(path) or {}
    if not isinstance(actual, dict):
        return [f"handoff da sessão {session:03d} não é mapeamento"]
    kind = ((actual.get("checkpoint") or {}).get("tipo"))
    if kind not in {"bootstrap", "cena", "sessao"}:
        return [f"handoff da sessão {session:03d} possui tipo de checkpoint inválido: {kind}"]

    context = sessoes.load_yaml(repo / "runtime/contexto.yaml") or {}
    scene = sessoes.load_yaml(repo / "runtime/cena.yaml") or {}
    ledger = sessoes.read_jsonl(
        repo / "sessoes" / f"{session:03d}" / consolidar.LEDGER_NAME
    )
    expected = sessoes.build_handoff(
        repo,
        session=session,
        kind=kind,
        context=context,
        scene=scene,
        ledger=ledger,
    )
    if actual != expected:
        errors.append(
            f"handoff da sessão {session:03d} diverge de runtime/ledger; "
            "execute ferramentas/checkpoint.py recuperar"
        )
    return errors


def check(repo: Path) -> list[str]:
    errors = list(consolidar.check(repo))
    errors.extend(sessoes.check(repo))
    errors.extend(_current_handoff_errors(repo))
    return list(dict.fromkeys(errors))


def status(repo: Path) -> dict[str, Any]:
    return {
        "consolidacao": consolidar.status(repo),
        "memoria_sessoes": sessoes.status(repo),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("cena", help="consolida checkpoint de cena e atualiza handoff/índice")
    sub.add_parser("sessao", help="consolida encerramento e atualiza handoff/índice")
    sub.add_parser("recuperar", help="recupera journal canônico e reconstrói memória compacta")
    sub.add_parser("status", help="mostra estado do cânone e da memória de sessões")
    sub.add_parser("check", help="valida consolidação e memória fria")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo = args.repo.resolve()
    try:
        if args.comando in {"cena", "sessao"}:
            result = checkpoint(repo, args.comando)
            canonical = result["canonico"]
            memory = result["memoria"]
            if canonical.get("sem_pendencias"):
                prefix = "sem novos deltas; memória compacta atualizada"
            elif canonical.get("recuperada"):
                prefix = "consolidação interrompida recuperada e memória atualizada"
            else:
                prefix = "consolidação concluída e memória atualizada"
            print(
                f"OK — {prefix}: sessão {memory['sessao']:03d} | "
                f"handoff={memory['handoff']}"
            )
            return 0
        if args.comando == "recuperar":
            result = recover(repo)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        if args.comando == "status":
            print(json.dumps(status(repo), ensure_ascii=False, indent=2))
            return 0
        if args.comando == "check":
            errors = check(repo)
            if errors:
                print("FALHA DE CHECKPOINT")
                for error in errors:
                    print(f"- {error}")
                return 1
            print("OK — consolidação e memória fria estão íntegras.")
            return 0
        raise ValueError(f"comando desconhecido: {args.comando}")
    except (
        OSError,
        ValueError,
        yaml.YAMLError,
        transacoes.TransactionError,
        consolidar.ConsolidationError,
        sessoes.SessionMemoryError,
    ) as exc:
        print(f"FALHA DE CHECKPOINT — {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
