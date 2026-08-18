#!/usr/bin/env python3
"""Checkpoint canônico + memória compacta + sincronização do Mundo Vivo.

`consolidar.py` continua responsável pela transação canônica atômica. Este wrapper
é a porta operacional: depois que a consolidação termina, direções canônicas e o
Mundo Vivo são sincronizados até o novo tempo canônico e só então são derivados
`handoff.yaml` e `sessoes/index.yaml`.

No fechamento de sessão, a consolidação é seguida por uma pequena transação de
ciclo que mantém N como sessão corrente e muda `campanha.status` para
`entre_sessoes`. Só `sessoes.py iniciar` avança para N+1.

Se o processo cair após o cânone e antes do handoff ou da sincronização do mundo,
nenhum delta é reaplicado: basta executar o comando novamente ou
`checkpoint.py recuperar`. O cursor determinístico de `mundo.py` e os IDs das
pendências de direção são idempotentes.

Desde o ajuste de autoridade temporal, `estado/tempo.yaml:prazo_relevante` é a
representação canônica única de prazos/alertas temporais. O campo legado homônimo
aninhado em `estado/estado-atual.yaml` não participa mais da checagem de espelho.
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

import ciclo_sessoes
import consolidar
import direcoes
import direcoes_mundo
import mundo
import sessoes
import transacoes

PRAZO_MIRROR_LEGADO = ("tempo.prazo_relevante", "prazo_relevante")

consolidar.TIME_MIRRORS = tuple(
    pair for pair in consolidar.TIME_MIRRORS if pair != PRAZO_MIRROR_LEGADO
)


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


def _world_configured(repo: Path) -> bool:
    return all(
        (repo / path).is_file()
        for path in (mundo.TIME_PATH, mundo.AGENDA_PATH, mundo.WORLD_STATE_PATH)
    )


def _directions_configured(repo: Path) -> bool:
    return (repo / direcoes.INDEX_PATH).is_file() and (repo / direcoes.STATE_PATH).is_file()


def sync_world(repo: Path) -> dict[str, Any]:
    """Sincroniza depois do cânone; tolera fixtures legadas sem Mundo Vivo."""
    if not _world_configured(repo):
        return {
            "configurado": False,
            "alterou": False,
            "novas_pendencias": [],
            "agentes_reconsiderar": [],
            "direcoes_reconsiderar": [],
        }

    direction_result: dict[str, Any] = {
        "novas_pendencias": [],
        "direcoes_reconsiderar": [],
    }
    if _directions_configured(repo):
        # Direções precisam enxergar o intervalo antigo -> novo antes que
        # mundo.py mova seu cursor até o tempo canônico recém-consolidado.
        direction_result = direcoes_mundo.process_checkpoint(repo)

    result = mundo.process_to_canonical(repo)
    new_pending = [
        *(direction_result.get("novas_pendencias") or []),
        *(result.get("novas_pendencias") or []),
    ]
    return {
        "configurado": True,
        **result,
        "novas_pendencias": new_pending,
        "direcoes_reconsiderar": direction_result.get("direcoes_reconsiderar") or [],
    }


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


def _lifecycle_journal_kind(repo: Path) -> str | None:
    journal = ciclo_sessoes._journal(repo)
    if not journal:
        return None
    kind = journal.get("tipo")
    return str(kind) if kind is not None else None


def checkpoint(repo: Path, kind: str) -> dict[str, Any]:
    journal_kind = _lifecycle_journal_kind(repo)
    if journal_kind == ciclo_sessoes.START_KIND:
        raise ciclo_sessoes.SessionLifecycleError(
            "início de sessão interrompido; repita `sessoes.py iniciar` antes de fazer checkpoint"
        )
    if journal_kind == ciclo_sessoes.CLOSE_KIND and kind != "sessao":
        raise ciclo_sessoes.SessionLifecycleError(
            "encerramento de sessão interrompido; execute checkpoint.py recuperar antes de checkpoint de cena"
        )

    canonical = consolidar.consolidate(repo, kind)
    lifecycle: dict[str, Any] | None = None
    if kind == "sessao":
        lifecycle = ciclo_sessoes.encerrar(repo)
        effective_kind = "sessao"
    else:
        effective_kind = canonical.get("tipo") or kind
        if effective_kind not in {"cena", "sessao"}:
            effective_kind = kind

    # Ordem deliberada: primeiro o tempo vira cânone; então as direções observam
    # o intervalo e o Mundo Vivo move seu cursor. Nenhuma camada usa prosa ou
    # deltas ainda não instalados como se fossem fatos.
    world = sync_world(repo)
    memory = refresh_memory(repo, effective_kind)
    return {"canonico": canonical, "ciclo": lifecycle, "mundo": world, "memoria": memory}


def recover(repo: Path) -> dict[str, Any]:
    journal_kind = _lifecycle_journal_kind(repo)
    canonical = consolidar.resume_consolidation(repo)
    if canonical is None:
        lifecycle = ciclo_sessoes.status(repo)
        kind = "sessao" if lifecycle.get("status") == ciclo_sessoes.STATUS_BETWEEN else "bootstrap"
        world = sync_world(repo)
        memory = refresh_memory(repo, kind)
        return {
            "canonico": {"sem_journal": True},
            "ciclo": lifecycle,
            "mundo": world,
            "memoria": memory,
        }

    kind = canonical.get("tipo") or journal_kind or "cena"
    if kind == ciclo_sessoes.CLOSE_KIND:
        memory_kind = "sessao"
    elif kind == ciclo_sessoes.START_KIND:
        memory_kind = "bootstrap"
    else:
        memory_kind = kind if kind in {"cena", "sessao"} else "cena"
    world = sync_world(repo)
    memory = refresh_memory(repo, memory_kind)
    return {
        "canonico": canonical,
        "ciclo": ciclo_sessoes.status(repo),
        "mundo": world,
        "memoria": memory,
    }


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
    lifecycle = ciclo_sessoes.status(repo)
    if lifecycle.get("status") == ciclo_sessoes.STATUS_BETWEEN and kind != "sessao":
        errors.append(
            f"sessão {session:03d} está entre_sessoes, mas o handoff não é de encerramento"
        )
    return errors


def check(repo: Path) -> list[str]:
    errors = list(consolidar.check(repo))
    errors.extend(sessoes.check(repo))
    errors.extend(ciclo_sessoes.check(repo))
    errors.extend(_current_handoff_errors(repo))
    if _world_configured(repo):
        world = mundo.check_repo(repo)
        errors.extend(f"mundo vivo: {error}" for error in world.get("erros") or [])
    if _directions_configured(repo):
        direction_check = direcoes_mundo.check_repo(repo)
        errors.extend(f"direções: {error}" for error in direction_check.get("erros") or [])
    return list(dict.fromkeys(errors))


def status(repo: Path) -> dict[str, Any]:
    world = (
        {"configurado": True, **mundo.status_view(repo)}
        if _world_configured(repo)
        else {"configurado": False}
    )
    directions = (
        {"configurado": True, **direcoes.status_view(repo)}
        if _directions_configured(repo)
        else {"configurado": False}
    )
    return {
        "consolidacao": consolidar.status(repo),
        "ciclo_sessao": ciclo_sessoes.status(repo),
        "mundo": world,
        "direcoes": directions,
        "memoria_sessoes": sessoes.status(repo),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("cena", help="consolida cena, sincroniza mundo/direções e atualiza handoff/índice")
    sub.add_parser("sessao", help="consolida, sincroniza mundo/direções e encerra N")
    sub.add_parser("recuperar", help="recupera journal, sincroniza mundo/direções e reconstrói memória")
    sub.add_parser("status", help="mostra cânone, ciclo, mundo, direções e memória")
    sub.add_parser("check", help="valida consolidação, ciclo, Mundo Vivo, direções e memória fria")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo = args.repo.resolve()
    try:
        if args.comando in {"cena", "sessao"}:
            result = checkpoint(repo, args.comando)
            canonical = result["canonico"]
            memory = result["memoria"]
            world = result["mundo"]
            if canonical.get("sem_pendencias"):
                prefix = "sem novos deltas; memória compacta atualizada"
            elif canonical.get("recuperada"):
                prefix = "operação interrompida recuperada e memória atualizada"
            else:
                prefix = "consolidação concluída e memória atualizada"
            if args.comando == "sessao":
                prefix += "; sessão encerrada (entre_sessoes)"
            if world.get("configurado") and world.get("novas_pendencias"):
                prefix += f"; Mundo Vivo gerou {len(world['novas_pendencias'])} pendência(s)"
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
            print("OK — consolidação, ciclo, Mundo Vivo, direções e memória fria estão íntegros.")
            return 0
        raise ValueError(f"comando desconhecido: {args.comando}")
    except (
        OSError,
        ValueError,
        yaml.YAMLError,
        transacoes.TransactionError,
        consolidar.ConsolidationError,
        ciclo_sessoes.SessionLifecycleError,
        sessoes.SessionMemoryError,
        mundo.WorldEngineError,
        direcoes.DirectionError,
    ) as exc:
        print(f"FALHA DE CHECKPOINT — {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
