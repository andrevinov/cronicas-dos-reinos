#!/usr/bin/env python3
"""Primitivas transacionais para encerrar e iniciar sessões.

O fechamento mantém o número da sessão e muda somente o ciclo de vida para
`entre_sessoes`. A abertura exige esse estado, cria N+1 sem copiar transcrição e
instala estado/runtime/handoff/índice com o mesmo journal + staging usado pela
consolidação canônica. Repetir a operação após queda apenas conclui os bytes já
preparados.
"""
from __future__ import annotations

import copy
import importlib
import json
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

import consolidar
import transacoes

STATE_PATH = Path("estado/estado-atual.yaml")
TIME_PATH = Path("estado/tempo.yaml")
SHEET_PATH = Path("personagens/jogador/ficha.yaml")
KNOW_ACTIVE_PATH = Path("personagens/jogador/conhecimento/ativo.yaml")
CONTEXT_PATH = Path("runtime/contexto.yaml")
SCENE_PATH = Path("runtime/cena.yaml")
PENDING_PATH = transacoes.PENDING_PATH

STATUS_ACTIVE = "em_sessao"
STATUS_BETWEEN = "entre_sessoes"
CLOSE_KIND = "encerramento_sessao"
START_KIND = "inicio_sessao"


class SessionLifecycleError(RuntimeError):
    pass


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SessionLifecycleError(f"{label} não é mapeamento")
    return value


def _journal(repo: Path) -> dict[str, Any] | None:
    path = repo / consolidar.JOURNAL_PATH
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SessionLifecycleError(f"journal de ciclo/consolidação corrompido: {exc}") from exc
    if not isinstance(data, dict):
        raise SessionLifecycleError("journal de ciclo/consolidação não é objeto")
    return data


def _resume_owned(repo: Path, kind: str) -> dict[str, Any] | None:
    journal = _journal(repo)
    if journal is None:
        return None
    actual = journal.get("tipo")
    if actual != kind:
        raise SessionLifecycleError(
            f"há operação pendente do tipo {actual!r}; recupere-a antes de executar {kind!r}"
        )
    result = consolidar.resume_consolidation(repo)
    if result is None:
        raise SessionLifecycleError("journal desapareceu durante recuperação do ciclo de sessão")
    return {"recuperada": True, **result}


def _canonical_documents(repo: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    estado = _mapping(_load_yaml(repo / STATE_PATH), "estado atual")
    tempo = _mapping(_load_yaml(repo / TIME_PATH), "tempo")
    ficha = _mapping(_load_yaml(repo / SHEET_PATH), "ficha")
    return estado, tempo, ficha


def _campaign(estado: dict[str, Any]) -> dict[str, Any]:
    return _mapping(estado.get("campanha"), "estado.campanha")


def _state_session_status(estado: dict[str, Any]) -> tuple[int, str]:
    campanha = _campaign(estado)
    session = campanha.get("sessao_atual")
    status = campanha.get("status")
    if not isinstance(session, int) or session < 1:
        raise SessionLifecycleError("estado.campanha.sessao_atual precisa ser inteiro positivo")
    if not isinstance(status, str):
        raise SessionLifecycleError("estado.campanha.status precisa ser string")
    return session, status


def _runtime_session_status(repo: Path) -> tuple[int, str | None]:
    runtime = _mapping(_load_yaml(repo / CONTEXT_PATH), "runtime/contexto.yaml")
    session_data = _mapping(runtime.get("sessao"), "runtime.sessao")
    session = session_data.get("numero")
    status = session_data.get("status")
    if not isinstance(session, int) or session < 1:
        raise SessionLifecycleError("runtime não define sessão inteira positiva")
    return session, status if isinstance(status, str) else None


def _pending_records(repo: Path) -> list[dict[str, Any]]:
    return transacoes.load_pending(repo)


def _runtime_bytes(
    estado: dict[str, Any], tempo: dict[str, Any], ficha: dict[str, Any]
) -> tuple[bytes, bytes, dict[str, Any], dict[str, Any]]:
    runtime_mod = consolidar._runtime_module()
    context, scene = runtime_mod.build_runtime_from_documents(estado, tempo, ficha)
    return (
        runtime_mod.dump_yaml(context).encode("utf-8"),
        runtime_mod.dump_yaml(scene).encode("utf-8"),
        context,
        scene,
    )


def encerrar(repo: Path, *, fail_after: int | None = None) -> dict[str, Any]:
    """Marca a sessão consolidada como `entre_sessoes` sem avançar seu número."""
    recovered = _resume_owned(repo, CLOSE_KIND)
    if recovered is not None:
        return recovered

    pending = _pending_records(repo)
    if pending:
        raise SessionLifecycleError(
            "não é possível encerrar o ciclo com eventos pendentes; consolide a sessão primeiro"
        )

    estado, tempo, ficha = _canonical_documents(repo)
    session, status = _state_session_status(estado)
    runtime_session, _ = _runtime_session_status(repo)
    if runtime_session != session:
        raise SessionLifecycleError(
            f"estado aponta para sessão {session}, runtime para {runtime_session}; recupere o checkpoint"
        )
    if status == STATUS_BETWEEN:
        return {"sessao": session, "tipo": CLOSE_KIND, "sem_alteracao": True}
    if status != STATUS_ACTIVE:
        raise SessionLifecycleError(
            f"sessão só pode ser encerrada a partir de {STATUS_ACTIVE!r}; status atual={status!r}"
        )

    novo_estado = copy.deepcopy(estado)
    _campaign(novo_estado)["status"] = STATUS_BETWEEN
    context_raw, scene_raw, _, _ = _runtime_bytes(novo_estado, tempo, ficha)
    outputs = {
        STATE_PATH.as_posix(): consolidar.dump_yaml(novo_estado),
        CONTEXT_PATH.as_posix(): context_raw,
        SCENE_PATH.as_posix(): scene_raw,
    }
    plan = {
        "sessao": session,
        "tipo": CLOSE_KIND,
        "outputs": outputs,
        "transacoes": [],
        "stale": [],
    }
    journal = consolidar.stage_plan(repo, plan)
    result = consolidar.install_staged(repo, journal, fail_after=fail_after)
    return {"recuperada": False, **result}


def _closed_handoff(repo: Path, memory: Any, session: int) -> None:
    path = repo / memory.handoff_rel(session)
    if not path.is_file():
        raise SessionLifecycleError(
            f"handoff de encerramento ausente para sessão {session:03d}; execute checkpoint.py sessao"
        )
    data = _mapping(memory.load_yaml(path), f"handoff da sessão {session:03d}")
    checkpoint = _mapping(data.get("checkpoint"), "handoff.checkpoint")
    if checkpoint.get("tipo") != "sessao" or checkpoint.get("estado") != "sessao_encerrada":
        raise SessionLifecycleError(
            f"sessão {session:03d} ainda não possui handoff de encerramento válido"
        )


def _session_dir_is_free(repo: Path, session: int) -> None:
    path = repo / "sessoes" / f"{session:03d}"
    if not path.exists():
        return
    if path.is_dir() and not any(path.iterdir()):
        return
    raise SessionLifecycleError(
        f"destino da sessão {session:03d} já existe; não sobrescrever artefatos existentes"
    )


def iniciar(repo: Path, *, fail_after: int | None = None) -> dict[str, Any]:
    """Abre N+1 somente após encerramento explícito e com buffer vazio."""
    recovered = _resume_owned(repo, START_KIND)
    if recovered is not None:
        estado = _mapping(_load_yaml(repo / STATE_PATH), "estado atual")
        session, status = _state_session_status(estado)
        if status != STATUS_ACTIVE:
            raise SessionLifecycleError("recuperação do início terminou sem restaurar status em_sessao")
        return {**recovered, "sessao_iniciada": session}

    pending = _pending_records(repo)
    if pending:
        raise SessionLifecycleError(
            "não é possível iniciar nova sessão com eventos pendentes; encerre/consolide a sessão atual"
        )

    estado, tempo, ficha = _canonical_documents(repo)
    current, status = _state_session_status(estado)
    runtime_session, runtime_status = _runtime_session_status(repo)
    if status != STATUS_BETWEEN:
        raise SessionLifecycleError(
            f"nova sessão exige status {STATUS_BETWEEN!r}; status atual={status!r}. "
            "Execute checkpoint.py sessao antes de iniciar N+1."
        )
    if runtime_session != current or runtime_status != STATUS_BETWEEN:
        raise SessionLifecycleError(
            "estado/runtime não concordam sobre o encerramento; execute checkpoint.py recuperar"
        )

    memory = importlib.import_module("sessoes")
    _closed_handoff(repo, memory, current)
    next_session = current + 1
    _session_dir_is_free(repo, next_session)

    novo_estado = copy.deepcopy(estado)
    campanha = _campaign(novo_estado)
    campanha["sessao_atual"] = next_session
    campanha["status"] = STATUS_ACTIVE
    pointers = novo_estado.setdefault("ponteiros", {})
    if isinstance(pointers, dict):
        pointers["transcricao_atual"] = f"sessoes/{next_session:03d}/transcricao.md"

    context_raw, scene_raw, new_context, new_scene = _runtime_bytes(novo_estado, tempo, ficha)
    transcript_rel = memory.transcript_rel(next_session)
    handoff_rel = memory.handoff_rel(next_session)
    transcript = f"# Sessão {next_session:03d}\n\n---\n".encode("utf-8")
    handoff = memory.build_handoff(
        repo,
        session=next_session,
        kind="bootstrap",
        context=new_context,
        scene=new_scene,
        ledger=(),
    )

    outputs: dict[str, bytes] = {
        STATE_PATH.as_posix(): consolidar.dump_yaml(novo_estado),
        CONTEXT_PATH.as_posix(): context_raw,
        SCENE_PATH.as_posix(): scene_raw,
        transcript_rel.as_posix(): transcript,
        handoff_rel.as_posix(): memory.dump_yaml_bytes(handoff),
    }

    active_path = repo / KNOW_ACTIVE_PATH
    if active_path.is_file():
        active = _mapping(_load_yaml(active_path), "conhecimento/ativo.yaml")
        active = copy.deepcopy(active)
        active["sessao_atual_da_campanha"] = next_session
        outputs[KNOW_ACTIVE_PATH.as_posix()] = memory.dump_yaml_bytes(active)

    index = memory.build_index(
        repo,
        active_session=next_session,
        virtual_files=outputs,
    )
    outputs[memory.INDEX_PATH.as_posix()] = memory.dump_yaml_bytes(index)

    plan = {
        "sessao": next_session,
        "tipo": START_KIND,
        "outputs": outputs,
        "transacoes": [],
        "stale": [],
    }
    journal = consolidar.stage_plan(repo, plan)
    result = consolidar.install_staged(repo, journal, fail_after=fail_after)
    return {
        "recuperada": False,
        **result,
        "sessao_anterior": current,
        "sessao_iniciada": next_session,
        "transcricao": transcript_rel.as_posix(),
        "handoff": handoff_rel.as_posix(),
        "indice": memory.INDEX_PATH.as_posix(),
    }


def status(repo: Path) -> dict[str, Any]:
    if not (repo / STATE_PATH).is_file() or not (repo / CONTEXT_PATH).is_file():
        return {"disponivel": False}
    estado = _mapping(_load_yaml(repo / STATE_PATH), "estado atual")
    session, state_status = _state_session_status(estado)
    runtime_session, runtime_status = _runtime_session_status(repo)
    journal = _journal(repo)
    return {
        "disponivel": True,
        "sessao": session,
        "status": state_status,
        "runtime_sessao": runtime_session,
        "runtime_status": runtime_status,
        "operacao_em_andamento": (journal or {}).get("tipo") if journal else None,
    }


def check(repo: Path) -> list[str]:
    """Valida somente invariantes do ciclo quando o fixture possui estado canônico."""
    if not (repo / STATE_PATH).is_file() or not (repo / CONTEXT_PATH).is_file():
        return []
    errors: list[str] = []
    try:
        estado = _mapping(_load_yaml(repo / STATE_PATH), "estado atual")
        session, state_status = _state_session_status(estado)
        runtime_session, runtime_status = _runtime_session_status(repo)
        if session != runtime_session:
            errors.append(f"ciclo de sessão diverge: estado={session}, runtime={runtime_session}")
        if state_status != runtime_status:
            errors.append(
                f"ciclo de sessão diverge em status: estado={state_status!r}, runtime={runtime_status!r}"
            )
        if state_status not in {STATUS_ACTIVE, STATUS_BETWEEN}:
            errors.append(f"status de ciclo desconhecido: {state_status!r}")
        pending = read_pending_without_barrier(repo)
        if state_status == STATUS_BETWEEN and pending:
            errors.append("há eventos pendentes enquanto a campanha está entre_sessoes")
        pointer = ((estado.get("ponteiros") or {}).get("transcricao_atual"))
        expected_pointer = f"sessoes/{session:03d}/transcricao.md"
        if isinstance(pointer, str) and pointer != expected_pointer:
            errors.append(
                f"ponteiro de transcrição diverge da sessão atual: {pointer!r} != {expected_pointer!r}"
            )
        if state_status == STATUS_ACTIVE and not (repo / expected_pointer).is_file():
            errors.append(f"transcrição da sessão ativa ausente: {expected_pointer}")
    except (OSError, yaml.YAMLError, SessionLifecycleError) as exc:
        errors.append(f"ciclo de sessão inválido: {exc}")
    return errors


def read_pending_without_barrier(repo: Path) -> list[dict[str, Any]]:
    """Leitura de check: não tenta atravessar journal; apenas examina o arquivo."""
    path = repo / PENDING_PATH
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SessionLifecycleError(f"JSONL pendente inválido na linha {number}: {exc}") from exc
        if isinstance(item, dict):
            records.append(item)
    return records
