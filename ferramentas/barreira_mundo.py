#!/usr/bin/env python3
"""Barreira barata entre pendências do Mundo Vivo e novos turnos de Ren.

O arquivo ``runtime/mundo-pendencias.yaml`` é somente um marcador derivado. A
fonte de verdade continua sendo ``narrador/mundo/estado.yaml``. Em um turno
normal, o hot path lê apenas esse marcador minúsculo. Se ele aponta bloqueio, a
camada confirma o estado real antes de recusar o avanço e repara marcador stale.

Uma pendência não é um fato. Ela precisa ser avaliada. Se a avaliação não gera
mudança, pode ser concluída diretamente. Se gera mudança canônica, o narrador
pode registrar uma transação sem ação do jogador, com ``modo: mundo`` e uma tag
``resolver-pendencia-mundo:<id>``; ``turno.py`` força checkpoint antes de permitir
que a pendência seja concluída.
"""
from __future__ import annotations

import argparse
import os
import re
import tempfile
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

import mundo

BARRIER_PATH = Path("runtime/mundo-pendencias.yaml")
SCHEMA = 1
NATURE = "runtime_derivado"
RESOLUTION_TAG_PREFIX = "resolver-pendencia-mundo:"
PENDING_ID_RE = re.compile(r"^mundo-[0-9a-f]{16}$")


class WorldPendingBarrierError(ValueError):
    """Contrato inválido ou tentativa de atravessar pendências abertas."""


def _load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorldPendingBarrierError(f"arquivo inexistente: {path}") from exc
    except yaml.YAMLError as exc:
        raise WorldPendingBarrierError(f"YAML inválido em {path}: {exc}") from exc


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        yaml.safe_dump(data, handle, allow_unicode=True, sort_keys=False)
        handle.flush()
        os.fsync(handle.fileno())
        temp = Path(handle.name)
    os.replace(temp, path)


def _instant_of(item: dict[str, Any]) -> mundo.WorldInstant:
    when = item.get("disparado_em") or {}
    return mundo.parse_instant(str(when.get("data")), str(when.get("hora")))


def payload_from_state(state: dict[str, Any]) -> dict[str, Any]:
    pending = list(state.get("pendencias") or [])
    earliest = min((_instant_of(item) for item in pending), default=None)
    return {
        "schema_barreira_mundo": SCHEMA,
        "natureza": NATURE,
        "bloqueado": bool(pending),
        "quantidade": len(pending),
        "disparo_mais_antigo": mundo.instant_parts(earliest) if earliest else None,
    }


def load_status(repo: Path) -> dict[str, Any]:
    path = repo / BARRIER_PATH
    if not path.is_file():
        return {
            "configurado": False,
            "bloqueado": False,
            "quantidade": 0,
            "disparo_mais_antigo": None,
            "fontes_lidas": [],
        }
    data = _load_yaml(path)
    if not isinstance(data, dict):
        raise WorldPendingBarrierError("marcador de pendências deve ser mapa")
    if data.get("schema_barreira_mundo") != SCHEMA:
        raise WorldPendingBarrierError(
            f"runtime/mundo-pendencias.yaml deve usar schema_barreira_mundo: {SCHEMA}"
        )
    if data.get("natureza") != NATURE:
        raise WorldPendingBarrierError("marcador de pendências deve ser runtime_derivado")
    blocked = data.get("bloqueado")
    quantity = data.get("quantidade")
    if not isinstance(blocked, bool):
        raise WorldPendingBarrierError("barreira.bloqueado deve ser booleano")
    if not isinstance(quantity, int) or quantity < 0:
        raise WorldPendingBarrierError("barreira.quantidade deve ser inteiro >= 0")
    if blocked != (quantity > 0):
        raise WorldPendingBarrierError("barreira diverge: bloqueado precisa equivaler a quantidade > 0")
    oldest = data.get("disparo_mais_antigo")
    if quantity == 0:
        if oldest is not None:
            raise WorldPendingBarrierError("barreira livre não pode ter disparo_mais_antigo")
    else:
        if not isinstance(oldest, dict):
            raise WorldPendingBarrierError("barreira bloqueada precisa de disparo_mais_antigo")
        mundo.parse_instant(str(oldest.get("data")), str(oldest.get("hora")))
    return {
        "configurado": True,
        "bloqueado": blocked,
        "quantidade": quantity,
        "disparo_mais_antigo": oldest,
        "fontes_lidas": [BARRIER_PATH.as_posix()],
    }


def sync(repo: Path, state: dict[str, Any] | None = None) -> dict[str, Any]:
    state = state or mundo.load_world_state(repo)
    payload = payload_from_state(state)
    _atomic_write(repo / BARRIER_PATH, payload)
    return {
        "configurado": True,
        **payload,
        "fontes_lidas": [mundo.WORLD_STATE_PATH.as_posix(), BARRIER_PATH.as_posix()],
    }


def refresh_if_blocked(repo: Path) -> dict[str, Any]:
    """No caminho raro bloqueado, confirma a fonte real e repara marcador stale."""
    status = load_status(repo)
    if not status.get("configurado") or not status.get("bloqueado"):
        return status
    state = mundo.load_world_state(repo)
    expected = payload_from_state(state)
    actual = {
        "schema_barreira_mundo": SCHEMA,
        "natureza": NATURE,
        "bloqueado": status["bloqueado"],
        "quantidade": status["quantidade"],
        "disparo_mais_antigo": status["disparo_mais_antigo"],
    }
    if actual != expected:
        _atomic_write(repo / BARRIER_PATH, expected)
    return {
        "configurado": True,
        **expected,
        "fontes_lidas": [BARRIER_PATH.as_posix(), mundo.WORLD_STATE_PATH.as_posix()],
    }


def resolution_pending_id(transaction: dict[str, Any]) -> str | None:
    tags = transaction.get("tags") or []
    if not isinstance(tags, list) or any(not isinstance(item, str) for item in tags):
        raise WorldPendingBarrierError("tags de transação devem ser lista de strings")
    matches = [item[len(RESOLUTION_TAG_PREFIX):] for item in tags if item.startswith(RESOLUTION_TAG_PREFIX)]
    if not matches:
        return None
    if len(matches) != 1:
        raise WorldPendingBarrierError("transação pode resolver somente uma pendência do mundo por vez")
    pending_id = matches[0]
    if not PENDING_ID_RE.fullmatch(pending_id):
        raise WorldPendingBarrierError(f"id de pendência do mundo inválido: {pending_id!r}")
    if transaction.get("modo") != "mundo":
        raise WorldPendingBarrierError("resolução de pendência exige modo: mundo")
    player = transaction.get("jogador")
    if isinstance(player, str) and player.strip():
        raise WorldPendingBarrierError(
            "resolução do Mundo Vivo não pode carregar nova ação do jogador; resolva antes do próximo turno de Ren"
        )
    if player is not None and not isinstance(player, str):
        raise WorldPendingBarrierError("jogador precisa ser string quando presente")
    return pending_id


def authorize_registration(
    repo: Path,
    transaction: dict[str, Any],
    *,
    retry: bool,
) -> dict[str, Any]:
    """Autoriza retry ou resolução explícita; bloqueia um turno novo de Ren."""
    resolution_id = resolution_pending_id(transaction)
    status = load_status(repo)
    if status.get("bloqueado"):
        status = refresh_if_blocked(repo)

    if retry:
        return {"ok": True, "retry": True, "pendencia_resolvida": resolution_id, "barreira": status}

    if not status.get("configurado") or not status.get("bloqueado"):
        if resolution_id is not None:
            raise WorldPendingBarrierError(
                f"transação declara {resolution_id}, mas não há pendência bloqueante no marcador"
            )
        return {"ok": True, "retry": False, "pendencia_resolvida": None, "barreira": status}

    if resolution_id is not None:
        state = mundo.load_world_state(repo)
        known = {str(item.get("id")) for item in state.get("pendencias") or []}
        if resolution_id not in known:
            raise WorldPendingBarrierError(f"pendência não está aberta: {resolution_id}")
        return {
            "ok": True,
            "retry": False,
            "pendencia_resolvida": resolution_id,
            "barreira": status,
        }

    quantity = int(status.get("quantidade") or 0)
    raise WorldPendingBarrierError(
        f"Mundo Vivo possui {quantity} pendência(s) não resolvida(s). "
        "Antes de registrar novo turno de Ren, execute `python3 ferramentas/mundo.py pendentes`, "
        "avalie as pendências e conclua cada uma com `python3 ferramentas/barreira_mundo.py concluir <id> --nota ...`. "
        "Se uma avaliação produzir mudança canônica, registre antes uma transação sem `jogador`, com `modo: mundo` "
        f"e tag `{RESOLUTION_TAG_PREFIX}<id>`."
    )


def conclude(repo: Path, pending_id: str, note: str | None = None) -> dict[str, Any]:
    result = mundo.conclude(repo, pending_id, note)
    barrier = sync(repo)
    return {**result, "barreira": barrier}


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        status = load_status(repo)
        if status.get("configurado"):
            state = mundo.load_world_state(repo)
            expected = payload_from_state(state)
            actual = {
                "schema_barreira_mundo": SCHEMA,
                "natureza": NATURE,
                "bloqueado": status["bloqueado"],
                "quantidade": status["quantidade"],
                "disparo_mais_antigo": status["disparo_mais_antigo"],
            }
            if actual != expected:
                errors.append("marcador runtime diverge de narrador/mundo/estado.yaml")
    except (WorldPendingBarrierError, mundo.WorldEngineError) as exc:
        errors.append(str(exc))
    return {"ok": not errors, "erros": errors}


def _dump(value: dict[str, Any]) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("sincronizar")
    sub.add_parser("check")
    done = sub.add_parser("concluir")
    done.add_argument("id")
    done.add_argument("--nota")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.command == "status":
            result = refresh_if_blocked(repo)
        elif args.command == "sincronizar":
            result = sync(repo)
        elif args.command == "concluir":
            result = conclude(repo, args.id, args.nota)
        else:
            result = check(repo)
        print(_dump(result), end="")
        if args.command == "check":
            return 0 if result["ok"] else 1
        return 0
    except (WorldPendingBarrierError, mundo.WorldEngineError) as exc:
        print(f"erro: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
