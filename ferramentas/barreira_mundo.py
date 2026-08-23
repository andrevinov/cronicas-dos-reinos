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

Eventos canônicos datados são a exceção ao no-op: quando uma pendência corresponde
ao catálogo da Parte 1, ela só pode ser concluída depois de uma transação de mundo
materializar seu núcleo. Se a forma preferencial for impossível, a forma muda; se
o núcleo estiver temporariamente impossível, a pendência permanece aberta.

Quando a pendência possui candidato autônomo de pressão em Ravens Bluff, a
conclusão fica causalmente fechada: ou recebe a transação consolidada + linha +
método usados, para aplicar no máximo uma frente de pressão, ou declara
explicitamente ``--sem-mudanca`` com um bloqueio canônico concreto. Ausência de
ação de Ren ou mera ausência de fato novo não são bloqueios válidos para um plano
autônomo já elegível.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import re
import sys
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
import pressao_ravens_bluff

BARRIER_PATH = Path("runtime/mundo-pendencias.yaml")
SCHEMA = 1
NATURE = "runtime_derivado"
RESOLUTION_TAG_PREFIX = "resolver-pendencia-mundo:"
PENDING_ID_RE = re.compile(r"^mundo-[0-9a-f]{16}$")
INVALID_AUTONOMOUS_NOOP_PHRASES = (
    "ren não fez",
    "ren nao fez",
    "sem ação de ren",
    "sem acao de ren",
    "nenhuma iniciativa de ren",
    "nenhum fato novo",
    "sem novo fato",
)


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
    matches = [
        item[len(RESOLUTION_TAG_PREFIX):]
        for item in tags
        if item.startswith(RESOLUTION_TAG_PREFIX)
    ]
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
        return {
            "ok": True,
            "retry": True,
            "pendencia_resolvida": resolution_id,
            "barreira": status,
        }

    if not status.get("configurado") or not status.get("bloqueado"):
        if resolution_id is not None:
            raise WorldPendingBarrierError(
                f"transação declara {resolution_id}, mas não há pendência bloqueante no marcador"
            )
        return {
            "ok": True,
            "retry": False,
            "pendencia_resolvida": None,
            "barreira": status,
        }

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
        "Antes de registrar novo turno de Ren, execute `python3 ferramentas/endpoints.py pendencias`, "
        "avalie somente as pendências indicadas e conclua cada uma pela barreira. "
        "Se uma avaliação produzir mudança canônica, registre antes uma transação sem `jogador`, com `modo: mundo` "
        f"e tag `{RESOLUTION_TAG_PREFIX}<id>`."
    )


def _pending_item(repo: Path, pending_id: str) -> dict[str, Any]:
    state = mundo.load_world_state(repo)
    matches = [item for item in state.get("pendencias") or [] if item.get("id") == pending_id]
    if not matches:
        raise WorldPendingBarrierError(f"pendência não encontrada: {pending_id}")
    return matches[0]


def _validate_autonomous_noop(note: str | None) -> str:
    if not isinstance(note, str) or len(" ".join(note.split())) < 20:
        raise WorldPendingBarrierError(
            "--sem-mudanca em candidato autônomo exige --nota com bloqueio canônico concreto"
        )
    normalized = " ".join(note.lower().split())
    if any(phrase in normalized for phrase in INVALID_AUTONOMOUS_NOOP_PHRASES):
        raise WorldPendingBarrierError(
            "ausência de ação de Ren ou de fato externo novo não bloqueia um plano autônomo; "
            "aponte restrição, falta de recurso, conhecimento, presença ou oportunidade canônica concreta"
        )
    return note.strip()


def _canonical_module(repo: Path):
    catalog = repo / "narrador/arcos/parte_1/eventos-canonicos.yaml"
    if not catalog.is_file():
        return None
    try:
        import eventos_canonicos
        return eventos_canonicos
    except ModuleNotFoundError as exc:
        if exc.name != "eventos_canonicos":
            raise
        module_path = Path(__file__).with_name("eventos_canonicos.py")
        spec = importlib.util.spec_from_file_location("eventos_canonicos", module_path)
        if spec is None or spec.loader is None:
            raise WorldPendingBarrierError("não foi possível carregar ferramentas/eventos_canonicos.py") from exc
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("eventos_canonicos", module)
        spec.loader.exec_module(module)
        return module


def _canonical_event(repo: Path, pending: dict[str, Any]) -> dict[str, Any] | None:
    module = _canonical_module(repo)
    if module is None:
        return None
    try:
        return module.event_for_pending(repo, pending)
    except module.CanonicalEventError as exc:
        raise WorldPendingBarrierError(str(exc)) from exc


def conclude(
    repo: Path,
    pending_id: str,
    note: str | None = None,
    *,
    transaction_id: str | None = None,
    line_id: str | None = None,
    method_id: str | None = None,
    no_change: bool = False,
) -> dict[str, Any]:
    pending = _pending_item(repo, pending_id)
    canonical_event = _canonical_event(repo, pending)
    try:
        candidate = pressao_ravens_bluff.candidate_for_pending(repo, pending)
    except pressao_ravens_bluff.PressureError as exc:
        raise WorldPendingBarrierError(str(exc)) from exc

    if canonical_event is not None:
        if no_change:
            raise WorldPendingBarrierError(
                "evento canônico datado não aceita --sem-mudanca; adapte a forma ou mantenha a pendência aberta se o núcleo estiver realmente impossível"
            )
        if not isinstance(transaction_id, str) or not transaction_id.strip():
            raise WorldPendingBarrierError(
                "evento canônico datado só pode ser concluído após transação de mundo que materialize seu núcleo; informe --transacao"
            )
        pressure_args = (line_id, method_id)
        if any(value is not None for value in pressure_args) and not all(
            isinstance(value, str) and value.strip() for value in pressure_args
        ):
            raise WorldPendingBarrierError(
                "ao acoplar pressão urbana a evento canônico, informe --linha e --metodo juntos"
            )
        if candidate is not None and line_id and method_id:
            try:
                pressure_result = pressao_ravens_bluff.apply_world_resolution(
                    repo,
                    pending,
                    transaction_id.strip(),
                    line_id.strip(),
                    method_id.strip(),
                    note or "evento canônico materializado e pressão urbana consolidada",
                )
            except pressao_ravens_bluff.PressureError as exc:
                raise WorldPendingBarrierError(str(exc)) from exc
        else:
            pressure_result = {
                "ok": True,
                "alterou": False,
                "candidato": candidate,
                "motivo": "evento canônico materializado; nenhuma frente foi acoplada nesta conclusão",
            }
        result = mundo.conclude(repo, pending_id, note or f"núcleo canônico materializado: {canonical_event['id']}")
        barrier = sync(repo)
        return {
            **result,
            "evento_canonico": {
                "id": canonical_event["id"],
                "titulo": canonical_event["titulo"],
                "estado": "materializado_em_jogo",
            },
            "pressao_ravens_bluff": pressure_result,
            "barreira": barrier,
        }

    action_values = (transaction_id, line_id, method_id)
    has_action = any(value is not None for value in action_values)
    if has_action and not all(isinstance(value, str) and value.strip() for value in action_values):
        raise WorldPendingBarrierError(
            "conclusão com mudança exige --transacao, --linha e --metodo juntos"
        )
    if has_action and no_change:
        raise WorldPendingBarrierError("--sem-mudanca não pode ser combinado com resolução canônica")

    pressure_result: dict[str, Any]
    if candidate is not None:
        if not has_action and not no_change:
            raise WorldPendingBarrierError(
                "pendência possui candidato autônomo de pressão; conclua a mudança com "
                "--transacao <id> --linha <linha> --metodo <metodo> --nota ... ou declare "
                "--sem-mudanca --nota <bloqueio canônico concreto>"
            )
        if no_change:
            note = _validate_autonomous_noop(note)
            pressure_result = {
                "ok": True,
                "alterou": False,
                "candidato": candidate,
                "motivo": "bloqueio canônico explícito informado pelo narrador",
            }
        else:
            try:
                pressure_result = pressao_ravens_bluff.apply_world_resolution(
                    repo,
                    pending,
                    str(transaction_id),
                    str(line_id),
                    str(method_id),
                    note or "ação autônoma consolidada pelo Mundo Vivo",
                )
            except pressao_ravens_bluff.PressureError as exc:
                raise WorldPendingBarrierError(str(exc)) from exc
    else:
        pressure_result = {
            "ok": True,
            "alterou": False,
            "motivo": "pendência sem candidato elegível de pressão",
        }

    result = mundo.conclude(repo, pending_id, note)
    barrier = sync(repo)
    return {**result, "pressao_ravens_bluff": pressure_result, "barreira": barrier}


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
    done.add_argument("--transacao")
    done.add_argument("--linha")
    done.add_argument("--metodo")
    done.add_argument("--sem-mudanca", action="store_true")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.command == "status":
            result = refresh_if_blocked(repo)
        elif args.command == "sincronizar":
            result = sync(repo)
        elif args.command == "concluir":
            result = conclude(
                repo,
                args.id,
                args.nota,
                transaction_id=args.transacao,
                line_id=args.linha,
                method_id=args.metodo,
                no_change=args.sem_mudanca,
            )
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
