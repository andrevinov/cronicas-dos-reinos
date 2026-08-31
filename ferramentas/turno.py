#!/usr/bin/env python3
"""Registra um avanço narrativo em duas escritas: transcrição + deltas pendentes.

Uso preferencial em uma única chamada de ferramenta:

    python3 ferramentas/turno.py registrar <<'JSON'
    {
      "jogador": "Ren tenta ...",
      "narracao": "...",
      "resumo": "Ren alcança o alvo e gasta 1 Focus.",
      "modo": "combate",
      "deltas": [
        {"alvo": "estado", "op": "inc", "caminho": "recursos.focus.atuais", "valor": -1}
      ]
    }
    JSON

O campo `jogador` aceita somente ON já resolvido. Blocos OFF (`[...]`) e
placeholders RECALL (`{...}`) precisam ser separados/resolvidos antes desta porta;
se vazarem até aqui, a transação é recusada antes de qualquer escrita.

A operação é idempotente. Se houver interrupção entre as duas escritas, repetir a
mesma entrada repara somente o lado ausente sem duplicar o outro. Desde o Mundo
Vivo, a idempotência também reconhece uma transação já instalada no ledger após
checkpoint.

Data+hora são um único fato transacional: mudanças novas chegam ao buffer como
{"alvo":"tempo","op":"instante","valor":{"data":"...","hora":"HH:MM"}}.
O checkpoint temporal lê esse mesmo instante; não existe janela em que a hora
avance sem a data correspondente.

Pendências de avaliação do Mundo Vivo formam uma barreira causal: um novo avanço
de Ren não pode ser registrado enquanto elas estiverem abertas. O hot path lê
somente um marcador derivado minúsculo; o estado reservado completo só é conferido
quando o marcador aponta bloqueio. Retry/recuperação permanece sempre permitido.
Uma avaliação que gere mudança canônica usa uma transação sem ação do jogador,
modo: mundo e tag resolver-pendencia-mundo:<id>; essa transação força
checkpoint antes de a pendência ser concluída.

Passagens pequenas de tempo continuam no hot path comum. Quando o tempo efetivo
acumula pelo menos duas horas desde o último cursor do Mundo Vivo, ou atravessa o
amanhecer configurado, o próprio registro promove uma fronteira de cena: primeiro
persiste transcrição + delta, depois consolida o cânone e só então sincroniza o
motor do mundo. Não há checkpoint extra para uma caminhada de poucos minutos.

Depois de persistir e de qualquer checkpoint automático, o CLI emite por último
`RODAPE_CANONICO — ...`. A linha é derivada do runtime efetivo e deve ser copiada
verbatim pelo narrador; o modelo não recalcula data, local, PV, Focus ou itens mágicos.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

import barreira_mundo
import entrada
import rodape_turno
import tempo_transacional
from transacoes import (
    PENDING_PATH,
    TransactionError,
    build_pending_record,
    load_pending,
    record_fingerprint,
    transaction_marker,
)

MAX_PENDING_BYTES = 512 * 1024
SIGNIFICANT_WORLD_MINUTES = 120
WORLD_AGENDA_PATH = Path("narrador/mundo/agenda.yaml")
WORLD_STATE_PATH = Path("narrador/mundo/estado.yaml")
TIME_PATH = Path("estado/tempo.yaml")
LEDGER_NAME = "consolidacoes.jsonl"

# Aviso heurístico, nunca bloqueio. A meta é impedir que um painel completo de
# estado seja copiado para a transcrição a cada avanço sem necessidade.
_STATUS_PATTERNS = {
    "pv": re.compile(r"(?:\bPV\b|pontos? de vida)", re.IGNORECASE),
    "ca": re.compile(r"(?:\bCA\b|classe de armadura)", re.IGNORECASE),
    "focus": re.compile(r"\bki\b", re.IGNORECASE),
    "dinheiro": re.compile(r"(?:\bPO\b|peças? de ouro|dinheiro)", re.IGNORECASE),
    "hora": re.compile(r"(?:\b\d{1,2}:\d{2}\b|hora aproximada)", re.IGNORECASE),
    "localizacao": re.compile(r"(?:localiza(?:ção|cao)|posição atual|ponto exato)", re.IGNORECASE),
    "municao": re.compile(r"(?:muni(?:ção|cao)|shuriken|flechas?|virotes?)", re.IGNORECASE),
}


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def current_session_info(repo: Path) -> tuple[int, str | None]:
    runtime = load_yaml(repo / "runtime/contexto.yaml") or {}
    session_data = runtime.get("sessao") if isinstance(runtime, dict) else None
    if not isinstance(session_data, dict):
        raise TransactionError("runtime/contexto.yaml não define sessão atual válida")
    session = session_data.get("numero")
    if not isinstance(session, int) or session < 1:
        raise TransactionError("runtime/contexto.yaml não define sessão atual válida")
    status = session_data.get("status")
    return session, status if isinstance(status, str) else None


def current_session(repo: Path) -> int:
    return current_session_info(repo)[0]


def read_transaction(path: Path | None) -> dict[str, Any]:
    if path is None:
        raw = sys.stdin.read()
    else:
        raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        raise TransactionError("entrada JSON da transação está vazia")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise TransactionError(f"JSON da transação inválido: {exc}") from exc
    if not isinstance(value, dict):
        raise TransactionError("transação precisa ser objeto JSON")
    return value


def validate_player_protocol(player: str) -> str:
    """Garante que somente ON resolvido possa chegar à transcrição."""
    try:
        return entrada.assert_registerable(player)
    except entrada.InputProtocolError as exc:
        raise TransactionError(f"protocolo de entrada inválido: {exc}") from exc


def normalize_transaction(repo: Path, transaction: dict[str, Any]) -> tuple[dict[str, Any], int]:
    active, status = current_session_info(repo)
    session = transaction.get("sessao", active)
    if not isinstance(session, int) or session < 1:
        raise TransactionError("sessao precisa ser inteiro positivo")
    if session != active:
        raise TransactionError(f"transação é da sessão {session}, mas runtime está na sessão {active}")
    if status is not None and status != "em_sessao":
        raise TransactionError(
            f"campanha não está em sessão ativa ({status}); execute ferramentas/sessoes.py iniciar "
            "antes de registrar novo turno"
        )

    narration = transaction.get("narracao")
    if not isinstance(narration, str) or not narration.strip():
        raise TransactionError("narracao precisa ser string não vazia")
    player = transaction.get("jogador")
    if player is not None and not isinstance(player, str):
        raise TransactionError("jogador precisa ser string quando presente")

    normalized = dict(transaction)
    if isinstance(player, str) and player.strip():
        normalized["jogador"] = validate_player_protocol(player)
    elif isinstance(player, str):
        normalized.pop("jogador", None)

    record = build_pending_record(normalized, session)
    normalized["id"] = record["id"]
    normalized["sessao"] = session
    normalized["resumo"] = record["resumo"]
    normalized["deltas"] = record.get("deltas", [])
    return normalized, session


def _changed_status_categories(transaction: dict[str, Any]) -> set[str]:
    changed: set[str] = set()
    for delta in transaction.get("deltas") or []:
        if not isinstance(delta, dict):
            continue
        target = str(delta.get("alvo") or "")
        path = str(delta.get("caminho") or "").lower()
        combined = f"{target.lower()} {path}"
        if "pontos_de_vida" in combined or ".pv" in combined:
            changed.add("pv")
        if re.search(r"(?:^|[._])focus(?:$|[._])", path) or "recursos_de_classe.focus" in combined:
            changed.add("focus")
        if "classe_de_armadura" in combined or "combate.ca" in combined:
            changed.add("ca")
        if "dinheiro" in combined or re.search(r"(?:^|[._])po(?:$|[._])", path):
            changed.add("dinheiro")
        if target == "tempo" or "hora_aproximada" in combined:
            changed.add("hora")
        if "localizacao" in combined or "ponto_exato" in combined:
            changed.add("localizacao")
        if any(word in combined for word in ("municao", "shuriken", "flecha", "virote")):
            changed.add("municao")
    return changed


def narration_warnings(transaction: dict[str, Any]) -> list[str]:
    """Detecta provável painel de status repetido sem impedir um uso deliberado."""
    narration = str(transaction.get("narracao") or "")
    mentioned = {
        category for category, pattern in _STATUS_PATTERNS.items() if pattern.search(narration)
    }
    if len(mentioned) < 4:
        return []
    changed = _changed_status_categories(transaction)
    unchanged = mentioned - changed
    if len(unchanged) < 3:
        return []
    fields = ", ".join(sorted(unchanged))
    return [
        "possível painel mecânico repetido sem mudança correspondente "
        f"({fields}); mantenha na narração somente o estado necessário à decisão atual"
    ]


def render_transcript_block(transaction: dict[str, Any]) -> str:
    marker = transaction_marker(str(transaction["id"]))
    parts = [marker]
    player = (transaction.get("jogador") or "").strip()
    if player:
        parts.extend(["**Jogador**", "", player])
    parts.extend(["**Narrador**", "", str(transaction["narracao"]).strip()])
    return "\n".join(parts).rstrip() + "\n"


def _append_block(existing: str, block: str) -> str:
    if not existing:
        return block
    return existing.rstrip() + "\n\n" + block


def _append_jsonl(existing: str, record: dict[str, Any]) -> str:
    line = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if not existing:
        return line + "\n"
    return existing.rstrip("\n") + "\n" + line + "\n"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
        temp_path = Path(handle.name)
    os.replace(temp_path, path)


def _transaction_in_ledger(repo: Path, session: int, transaction_id: str) -> bool:
    """Consulta o ledger só no caminho raro de retry após consolidação."""
    path = repo / "sessoes" / f"{session:03d}" / LEDGER_NAME
    if not path.is_file():
        return False
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TransactionError(f"ledger inválido em {path.relative_to(repo)}:{number}: {exc}") from exc
        if transaction_id in (item.get("transacoes") or []):
            return True
    return False


def _has_time_delta(record: dict[str, Any]) -> bool:
    return tempo_transacional.has_instant_change(record.get("deltas") or [])


def _apply_time_deltas(snapshot: dict[str, Any], records: Iterable[dict[str, Any]]) -> None:
    for record in tempo_transacional.expand_records(records):
        for delta in record.get("deltas") or []:
            if not isinstance(delta, dict) or delta.get("op") != "set":
                continue
            if delta.get("visibilidade", "operacional") == "narrador":
                continue
            target = delta.get("alvo")
            path = delta.get("caminho")
            value = delta.get("valor")
            if target == "tempo":
                if path in {"data_atual", "data"}:
                    snapshot["data_atual"] = value
                elif path == "hora_aproximada":
                    snapshot["hora_aproximada"] = value
            elif target == "estado":
                if path == "tempo.data_exata":
                    snapshot["data_atual"] = value
                elif path == "tempo.hora_aproximada":
                    snapshot["hora_aproximada"] = value


def _location_changed(record: dict[str, Any]) -> bool:
    for delta in record.get("deltas") or []:
        if not isinstance(delta, dict):
            continue
        target = str(delta.get("alvo") or "")
        path = str(delta.get("caminho") or "")
        if target == "estado" and path.startswith("localizacao."):
            return True
    return False


def _crossed_daily_minute(start_minute: int, end_minute: int, minute_of_day: int) -> bool:
    if end_minute <= start_minute:
        return False
    start_day = start_minute // 1440
    end_day = end_minute // 1440
    for day in range(start_day, end_day + 1):
        instant = day * 1440 + minute_of_day
        if start_minute < instant <= end_minute:
            return True
    return False


def detect_world_checkpoint(
    repo: Path,
    prior_records: Iterable[dict[str, Any]],
    current_record: dict[str, Any],
) -> dict[str, Any] | None:
    """Detecta marco temporal sem tool call extra e sem abrir fragmentos de agentes.

    O relógio de referência é o cursor do Mundo Vivo, não apenas a duração deste
    turno. Assim vários avanços pequenos acumulam e o primeiro que completar duas
    horas promove o checkpoint.
    """
    if not _has_time_delta(current_record):
        return None
    required = [repo / TIME_PATH, repo / WORLD_AGENDA_PATH, repo / WORLD_STATE_PATH]
    if not all(path.is_file() for path in required):
        return None

    try:
        import mundo

        time_data = load_yaml(repo / TIME_PATH) or {}
        if not isinstance(time_data, dict):
            raise TransactionError("estado/tempo.yaml inválido para checkpoint temporal")
        effective = dict(time_data)
        _apply_time_deltas(effective, [*prior_records, current_record])
        date_text = effective.get("data_atual") or effective.get("data")
        hour_text = effective.get("hora_aproximada")
        after = mundo.parse_instant(str(date_text), str(hour_text))

        world_state = mundo.load_world_state(repo)
        cursor_data = world_state["processado_ate"]
        cursor = mundo.parse_instant(cursor_data["data"], cursor_data["hora"])
        if after.minute <= cursor.minute:
            return None

        gap = after.minute - cursor.minute
        agenda = mundo.load_agenda(repo)
        dawn_text = str(agenda["hora_amanhecer"])
        match = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", dawn_text)
        if not match:
            raise TransactionError(f"hora_amanhecer inválida: {dawn_text}")
        dawn = int(match.group(1)) * 60 + int(match.group(2))
        crossed_dawn = _crossed_daily_minute(cursor.minute, after.minute, dawn)

        if crossed_dawn:
            reason = "amanhecer"
        elif gap >= SIGNIFICANT_WORLD_MINUTES:
            mode = str(current_record.get("modo") or "")
            if mode == "descanso" and gap >= 360:
                reason = "descanso_longo"
            elif mode == "exploração" and _location_changed(current_record):
                reason = "viagem_longa"
            else:
                reason = "passagem_horas"
        else:
            return None

        return {
            "motivo": reason,
            "minutos_desde_checkpoint": gap,
            "tempo_efetivo": mundo.instant_parts(after),
        }
    except (OSError, ValueError, yaml.YAMLError, tempo_transacional.AtomicTimeError) as exc:
        if isinstance(exc, TransactionError):
            raise
        raise TransactionError(f"não foi possível avaliar checkpoint temporal do mundo: {exc}") from exc


def _run_scene_checkpoint(repo: Path) -> dict[str, Any]:
    try:
        import checkpoint

        return checkpoint.checkpoint(repo, "cena")
    except Exception as exc:  # a transação já pode estar persistida; retry deve reparar
        raise TransactionError(
            "turno registrado, mas checkpoint do mundo falhou; repita a mesma operação "
            "ou execute ferramentas/checkpoint.py recuperar"
        ) from exc


def register_transaction(repo: Path, transaction: dict[str, Any]) -> dict[str, Any]:
    # A validação ON/OFF/RECALL ocorre dentro de normalize_transaction e, portanto,
    # antes de qualquer leitura destinada a preparar uma escrita ou de qualquer
    # mutação do transcript/buffer.
    normalized, session = normalize_transaction(repo, transaction)
    record = build_pending_record(normalized, session)
    transaction_id = record["id"]
    transcript_path = repo / "sessoes" / f"{session:03d}" / "transcricao.md"
    pending_path = repo / PENDING_PATH
    if not transcript_path.is_file():
        raise TransactionError(f"transcrição da sessão não existe: {transcript_path.relative_to(repo)}")
    if not pending_path.exists():
        raise TransactionError(f"arquivo pendente não existe: {PENDING_PATH}")

    transcript = transcript_path.read_text(encoding="utf-8")
    pending_text = pending_path.read_text(encoding="utf-8")
    marker = transaction_marker(transaction_id)
    marker_count = transcript.count(marker)
    if marker_count > 1:
        raise TransactionError(f"marcador transacional duplicado na transcrição: {transaction_id}")

    existing_records = load_pending(repo)
    by_id = {item["id"]: item for item in existing_records}
    existing_record = by_id.get(transaction_id)
    if existing_record is not None and record_fingerprint(existing_record) != record_fingerprint(record):
        raise TransactionError(
            f"id {transaction_id} já existe com conteúdo diferente; não sobrescrever silenciosamente"
        )

    consolidated = False
    if marker_count == 1 and existing_record is None:
        consolidated = _transaction_in_ledger(repo, session, transaction_id)

    need_transcript = marker_count == 0
    need_pending = existing_record is None and not consolidated
    retry = not (need_transcript and need_pending)
    try:
        authorization = barreira_mundo.authorize_registration(
            repo,
            normalized,
            retry=retry,
        )
    except barreira_mundo.WorldPendingBarrierError as exc:
        raise TransactionError(str(exc)) from exc
    resolution_id = authorization.get("pendencia_resolvida")

    prior_records = [item for item in existing_records if item.get("id") != transaction_id]
    temporal_trigger = None if consolidated else detect_world_checkpoint(repo, prior_records, record)

    if need_pending:
        candidate_pending = _append_jsonl(pending_text, record)
        if len(candidate_pending.encode("utf-8")) > MAX_PENDING_BYTES:
            raise TransactionError(
                f"{PENDING_PATH} excederia {MAX_PENDING_BYTES} bytes; consolidar antes de continuar"
            )
    else:
        candidate_pending = pending_text

    candidate_transcript = (
        _append_block(transcript, render_transcript_block(normalized)) if need_transcript else transcript
    )

    # Escrevemos o delta primeiro. Se o processo cair antes da transcrição, a
    # repetição da mesma entrada detecta o ID e repara apenas a transcrição.
    if need_pending:
        _atomic_write(pending_path, candidate_pending)
    if need_transcript:
        _atomic_write(transcript_path, candidate_transcript)

    checkpoint_world: dict[str, Any] | None = None
    force_resolution_checkpoint = resolution_id is not None and not consolidated
    if temporal_trigger is not None or force_resolution_checkpoint:
        checkpoint_result = _run_scene_checkpoint(repo)
        world = checkpoint_result.get("mundo") or {}
        checkpoint_world = {
            "disparado": True,
            "motivo": (
                temporal_trigger["motivo"]
                if temporal_trigger is not None
                else "resolucao_pendencia_mundo"
            ),
            "novas_pendencias": len(world.get("novas_pendencias") or []),
            "agentes_reconsiderar": world.get("agentes_reconsiderar") or [],
        }
        if temporal_trigger is not None:
            checkpoint_world.update(
                {
                    "minutos_desde_checkpoint": temporal_trigger["minutos_desde_checkpoint"],
                    "tempo_efetivo": temporal_trigger["tempo_efetivo"],
                }
            )
        if resolution_id is not None:
            checkpoint_world["pendencia_mundo"] = resolution_id
    elif consolidated:
        checkpoint_world = {
            "disparado": False,
            "ja_consolidado": True,
        }
        if resolution_id is not None:
            checkpoint_world["pendencia_mundo"] = resolution_id

    return {
        "id": transaction_id,
        "sessao": session,
        "transcricao": transcript_path.relative_to(repo).as_posix(),
        "eventos": PENDING_PATH.as_posix(),
        "deltas": len(record.get("deltas", [])),
        "transcricao_escrita": need_transcript,
        "evento_escrito": need_pending,
        "reparo_parcial": need_transcript != need_pending and not consolidated,
        "ja_registrada": not need_transcript and not need_pending,
        "consolidada": consolidated,
        "pendencia_mundo": resolution_id,
        "checkpoint_mundo": checkpoint_world,
        "avisos": narration_warnings(normalized),
    }


def check_transactions(repo: Path) -> list[str]:
    errors: list[str] = []
    try:
        records = load_pending(repo)
    except TransactionError as exc:
        return [str(exc)]

    pending_path = repo / PENDING_PATH
    if pending_path.exists() and pending_path.stat().st_size > MAX_PENDING_BYTES:
        errors.append(
            f"{PENDING_PATH} excede limite operacional: {pending_path.stat().st_size} > {MAX_PENDING_BYTES}"
        )

    for record in records:
        session = record["sessao"]
        transcript_path = repo / "sessoes" / f"{session:03d}" / "transcricao.md"
        if not transcript_path.is_file():
            errors.append(f"transação {record['id']} aponta para sessão sem transcrição: {session:03d}")
            continue
        text = transcript_path.read_text(encoding="utf-8")
        count = text.count(transaction_marker(record["id"]))
        if count != 1:
            errors.append(
                f"transação {record['id']} possui {count} marcador(es) na transcrição; esperado 1"
            )
    return errors


def status(repo: Path) -> dict[str, Any]:
    records = load_pending(repo)
    session, session_status = current_session_info(repo)
    return {
        "eventos_pendentes": len(records),
        "bytes_pendentes": (repo / PENDING_PATH).stat().st_size if (repo / PENDING_PATH).exists() else 0,
        "ultima_transacao": records[-1]["id"] if records else None,
        "sessao_atual": session,
        "status_sessao": session_status,
        "barreira_mundo": barreira_mundo.load_status(repo),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="comando", required=True)

    register = sub.add_parser("registrar", help="registra transcrição + deltas em uma única operação")
    register.add_argument("--arquivo", type=Path, help="JSON da transação; sem opção, lê stdin")

    sub.add_parser("check", help="valida schema e correspondência com marcadores da transcrição")
    sub.add_parser("status", help="mostra somente metadados do buffer transacional")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo = args.repo.resolve()
    try:
        if args.comando == "registrar":
            transaction = read_transaction(args.arquivo)
            result = register_transaction(repo, transaction)
            print(
                "OK — turno transacional registrado: "
                f"{result['id']} | deltas={result['deltas']} | "
                f"transcrição={'sim' if result['transcricao_escrita'] else 'já existia'} | "
                f"evento={'sim' if result['evento_escrito'] else ('consolidado' if result['consolidada'] else 'já existia')}"
            )
            if result["reparo_parcial"]:
                print("OK — inconsistência parcial anterior foi reparada de forma idempotente.")
            world = result.get("checkpoint_mundo") or {}
            if world.get("disparado"):
                agents = ", ".join(world.get("agentes_reconsiderar") or []) or "nenhum"
                if world.get("motivo") == "resolucao_pendencia_mundo":
                    print(
                        "MUNDO — checkpoint de resolução: "
                        f"{world.get('pendencia_mundo')} | "
                        f"novas_pendencias={world.get('novas_pendencias', 0)} | agentes={agents}"
                    )
                else:
                    print(
                        "MUNDO — checkpoint temporal: "
                        f"{world.get('motivo')} | atraso={world.get('minutos_desde_checkpoint')} min | "
                        f"novas_pendencias={world.get('novas_pendencias', 0)} | agentes={agents}"
                    )
            pending_world = result.get("pendencia_mundo")
            if pending_world and world.get("disparado"):
                print(
                    "MUNDO — mudança da avaliação foi canonizada; conclua a pendência com: "
                    f"python3 ferramentas/barreira_mundo.py concluir {pending_world} --nota '<resultado da avaliação>'"
                )
            for warning in result.get("avisos", []):
                print(f"AVISO — {warning}")
            print(rodape_turno.build_safe(repo))
            return 0
        if args.comando == "check":
            errors = check_transactions(repo)
            if errors:
                print("FALHA TRANSACIONAL")
                for error in errors:
                    print(f"- {error}")
                return 1
            print("OK — buffer transacional e marcadores de transcrição estão consistentes.")
            return 0
        if args.comando == "status":
            print(json.dumps(status(repo), ensure_ascii=False, indent=2))
            return 0
        raise TransactionError(f"comando desconhecido: {args.comando}")
    except (
        OSError,
        TransactionError,
        yaml.YAMLError,
        barreira_mundo.WorldPendingBarrierError,
    ) as exc:
        print(f"FALHA DE TURNO — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
