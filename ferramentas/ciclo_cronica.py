#!/usr/bin/env python3
"""Orquestra lifecycle de sessão e level-up para a CLI ``cronica``.

A Task 22 é deliberadamente uma camada de alto nível. Fechamento, checkpoint,
abertura e recovery continuam delegando às autoridades já existentes. A única
escrita nova é a aplicação mecânica de progressão, que usa o MESMO journal e o
MESMO staging da consolidação para instalar de forma atômica ficha, espelhos,
resumo de poderes, experiência e caches derivados.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

import yaml

import checkpoint
import ciclo_sessoes
import consolidar
import progressao_juppongatana
import sessoes
import transacoes

SCHEMA = 1
PROGRESSION_SCHEMA = 1
POWERS_PATH = Path("personagens/jogador/resumo-de-poderes.md")
MAX_PROGRESSION_PLAN_BYTES = 128 * 1024
MAX_SHEET_CHANGES = 32
MAX_POWERS_BYTES = 64 * 1024
MAX_MARK_TEXT = 1200
MAX_PENDING_CHOICES = 12
PROGRESSION_BATCH_PREFIX = "progressao-mecanica"


class UnifiedSessionError(ValueError):
    """Falha de contrato da camada unificada de lifecycle."""


def _text(value: Any, label: str, *, maximum: int | None = None) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnifiedSessionError(f"{label} deve ser texto não vazio")
    result = value.strip()
    if maximum is not None and len(result) > maximum:
        raise UnifiedSessionError(f"{label} excede {maximum} caracteres")
    return result


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise UnifiedSessionError(f"{label} deve ser mapa")
    return value


def _integer(value: Any, label: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise UnifiedSessionError(f"{label} deve ser inteiro >= {minimum}")
    return value


def _append_text(existing: str, block: str) -> str:
    if not existing.strip():
        return block.rstrip() + "\n"
    return existing.rstrip() + "\n\n" + block.rstrip() + "\n"


def _compact_checkpoint_result(result: dict[str, Any], phase: str) -> dict[str, Any]:
    canonical = result.get("canonico") or {}
    cycle = result.get("ciclo") or {}
    world = result.get("mundo") or {}
    memory = result.get("memoria") or {}
    return {
        "schema_cronica_sessao": SCHEMA,
        "fase": phase,
        "sessao": memory.get("sessao") or canonical.get("sessao") or cycle.get("sessao"),
        "canonico": {
            "sem_pendencias": bool(canonical.get("sem_pendencias")),
            "recuperada": bool(canonical.get("recuperada")),
            "batch": canonical.get("batch"),
            "transacoes": len(canonical.get("transacoes") or []),
        },
        "ciclo": {
            "status": cycle.get("status") or cycle.get("tipo"),
            "sem_alteracao": bool(cycle.get("sem_alteracao")),
        },
        "mundo": {
            "configurado": bool(world.get("configurado")),
            "novas_pendencias": len(world.get("novas_pendencias") or []),
            "agentes_reconsiderar": world.get("agentes_reconsiderar") or [],
            "direcoes_reconsiderar": world.get("direcoes_reconsiderar") or [],
            "barreira": world.get("barreira_pendencias") or {},
        },
        "memoria": {
            "handoff": memory.get("handoff"),
            "indice": memory.get("indice"),
            "tipo": memory.get("tipo"),
        },
    }


def _progression_view(repo: Path) -> dict[str, Any]:
    if not all(
        (repo / path).is_file()
        for path in (
            progressao_juppongatana.POLICY,
            progressao_juppongatana.ROSTER,
            progressao_juppongatana.STATE,
            progressao_juppongatana.SHEET,
        )
    ):
        return {"configurada": False}
    status = progressao_juppongatana.status(repo)
    return {
        "configurada": True,
        "nivel_ficha": status["nivel_ficha"],
        "nivel_desbloqueado_por_marcos": status["nivel_desbloqueado_por_marcos"],
        "neutralizacoes_duraveis": status["neutralizacoes_duraveis"],
        "progressao_pendente": status["nivel_ficha"] < status["nivel_desbloqueado_por_marcos"],
        "proximo_nivel": (
            status["nivel_ficha"] + 1
            if status["nivel_ficha"] < status["nivel_desbloqueado_por_marcos"]
            else None
        ),
    }


def _assert_resumable(repo: Path) -> None:
    errors = checkpoint.check(repo)
    if errors:
        raise UnifiedSessionError(
            "lifecycle terminou, mas a campanha não ficou formalmente retomável: "
            + "; ".join(errors)
        )


def session_status(repo: Path) -> dict[str, Any]:
    return {
        "schema_cronica_sessao": SCHEMA,
        "fase": "status",
        "lifecycle": checkpoint.status(repo),
        "progressao": _progression_view(repo),
    }


def session_checkpoint(repo: Path) -> dict[str, Any]:
    result = checkpoint.checkpoint(repo, "cena")
    _assert_resumable(repo)
    compact = _compact_checkpoint_result(result, "checkpoint")
    compact["progressao"] = _progression_view(repo)
    return compact


def session_close(repo: Path) -> dict[str, Any]:
    # Autoridade única: exatamente a mesma operação usada antes da Task 22.
    result = checkpoint.checkpoint(repo, "sessao")
    _assert_resumable(repo)
    compact = _compact_checkpoint_result(result, "encerrada")
    compact["progressao"] = _progression_view(repo)
    compact["proximo_passo"] = (
        {"acao": "aplicar_progressao", "comando": "cronica progressao aplicar"}
        if compact["progressao"].get("progressao_pendente")
        else {"acao": "iniciar_quando_pronto", "comando": "cronica sessao iniciar"}
    )
    return compact


def session_start(repo: Path, *, fail_after: int | None = None) -> dict[str, Any]:
    # Autoridade única: start_next é a mesma porta usada pelo CLI sessoes.py.
    result = sessoes.start_next(repo, fail_after=fail_after)
    _assert_resumable(repo)
    return {
        "schema_cronica_sessao": SCHEMA,
        "fase": "iniciada",
        "sessao_anterior": result.get("sessao_anterior"),
        "sessao": result.get("sessao_iniciada") or result.get("sessao"),
        "recuperada": bool(result.get("recuperada")),
        "transcricao": result.get("transcricao"),
        "handoff": result.get("handoff"),
        "indice": result.get("indice"),
        "progressao": _progression_view(repo),
        "proximo_passo": {"acao": "preparar_turno", "comando": "cronica preparar ..."},
    }


def session_recover(repo: Path) -> dict[str, Any]:
    # Um plano de progressão usa tipo=sessao justamente para permanecer
    # recuperável pela autoridade existente checkpoint.recover.
    result = checkpoint.recover(repo)
    _assert_resumable(repo)
    compact = _compact_checkpoint_result(result, "recuperada")
    compact["progressao"] = _progression_view(repo)
    return compact


def read_progression_plan(path: Path | None) -> dict[str, Any]:
    raw = path.read_bytes() if path is not None else sys.stdin.buffer.read()
    if not raw.strip():
        raise UnifiedSessionError("plano de progressão está vazio")
    if len(raw) > MAX_PROGRESSION_PLAN_BYTES:
        raise UnifiedSessionError(
            f"plano de progressão excede {MAX_PROGRESSION_PLAN_BYTES} bytes"
        )
    try:
        value = yaml.safe_load(raw.decode("utf-8"))
    except (UnicodeDecodeError, yaml.YAMLError) as exc:
        raise UnifiedSessionError(f"plano de progressão inválido: {exc}") from exc
    return validate_progression_plan(value)


def validate_progression_plan(value: Any) -> dict[str, Any]:
    plan = _mapping(value, "plano")
    required = {
        "schema_progressao_mecanica",
        "nivel_novo",
        "milestone_preparacao_id",
        "alteracoes_ficha",
        "resumo_de_poderes",
        "marco",
        "motivo",
        "escolhas_pendentes",
    }
    optional = {"nota"}
    if not required <= set(plan) or set(plan) - required - optional:
        raise UnifiedSessionError(
            "plano possui campos divergentes: " + ", ".join(sorted(set(plan) ^ required))
        )
    if plan.get("schema_progressao_mecanica") != PROGRESSION_SCHEMA:
        raise UnifiedSessionError(
            f"plano deve usar schema_progressao_mecanica: {PROGRESSION_SCHEMA}"
        )
    _integer(plan.get("nivel_novo"), "nivel_novo", 1)
    prep = _text(plan.get("milestone_preparacao_id"), "milestone_preparacao_id")
    if not progressao_juppongatana.PREPARATION_RE.fullmatch(prep):
        raise UnifiedSessionError("milestone_preparacao_id inválido")

    changes = plan.get("alteracoes_ficha")
    if not isinstance(changes, list):
        raise UnifiedSessionError("alteracoes_ficha deve ser lista")
    if len(changes) > MAX_SHEET_CHANGES:
        raise UnifiedSessionError(
            f"alteracoes_ficha excede {MAX_SHEET_CHANGES} entradas"
        )
    seen: set[str] = set()
    normalized_changes: list[dict[str, Any]] = []
    for index, raw in enumerate(changes):
        change = _mapping(raw, f"alteracoes_ficha[{index}]")
        if set(change) != {"caminho", "valor"}:
            raise UnifiedSessionError(
                f"alteracoes_ficha[{index}] deve conter somente caminho e valor"
            )
        path = _text(change.get("caminho"), f"alteracoes_ficha[{index}].caminho")
        if path == "identidade.nivel":
            raise UnifiedSessionError(
                "identidade.nivel é controlado pelo lifecycle e não pode vir no plano"
            )
        if path in seen:
            raise UnifiedSessionError(f"caminho repetido no plano: {path}")
        seen.add(path)
        normalized_changes.append({"caminho": path, "valor": copy.deepcopy(change.get("valor"))})

    powers = _text(plan.get("resumo_de_poderes"), "resumo_de_poderes")
    if len(powers.encode("utf-8")) > MAX_POWERS_BYTES:
        raise UnifiedSessionError(f"resumo_de_poderes excede {MAX_POWERS_BYTES} bytes")
    target = int(plan["nivel_novo"])
    normalized = "".join(
        ch for ch in powers.casefold().replace("í", "i") if ch not in "\r"
    )
    if not re.search(rf"\bnivel\s+{target}\b", normalized):
        raise UnifiedSessionError(
            f"resumo_de_poderes precisa declarar explicitamente nível {target}"
        )

    choices = plan.get("escolhas_pendentes")
    if not isinstance(choices, list) or any(not isinstance(item, str) for item in choices):
        raise UnifiedSessionError("escolhas_pendentes deve ser lista de strings")
    if len(choices) > MAX_PENDING_CHOICES:
        raise UnifiedSessionError(
            f"escolhas_pendentes excede {MAX_PENDING_CHOICES} entradas"
        )
    result = dict(plan)
    result["alteracoes_ficha"] = normalized_changes
    result["resumo_de_poderes"] = powers.rstrip() + "\n"
    result["marco"] = _text(plan.get("marco"), "marco", maximum=MAX_MARK_TEXT)
    result["motivo"] = _text(plan.get("motivo"), "motivo", maximum=MAX_MARK_TEXT)
    result["escolhas_pendentes"] = [
        _text(item, "escolha_pendente", maximum=320) for item in choices
    ]
    if "nota" in plan:
        result["nota"] = _text(plan.get("nota"), "nota", maximum=MAX_MARK_TEXT)
    return result


def _plan_fingerprint(plan: dict[str, Any]) -> str:
    rendered = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()[:24]


def _sheet_level(sheet: dict[str, Any]) -> int:
    identity = _mapping(sheet.get("identidade"), "ficha.identidade")
    return _integer(identity.get("nivel"), "ficha.identidade.nivel", 1)


def _milestone_for_target(
    repo: Path,
    *,
    current_level: int,
    target_level: int,
    preparation_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if target_level != current_level + 1:
        raise UnifiedSessionError(
            f"progressão mecânica só pode aplicar o próximo nível: atual={current_level}, pedido={target_level}"
        )
    if not (
        progressao_juppongatana.BASE_LEVEL < target_level <= progressao_juppongatana.FINAL_LEVEL
    ):
        raise UnifiedSessionError(
            "esta versão do lifecycle aplica automaticamente somente a faixa 8–17 protegida pela Task 19"
        )
    policy = progressao_juppongatana.load_policy(repo)
    state = progressao_juppongatana.load_state(repo)
    milestone = next(
        (
            item
            for item in state["neutralizacoes"]
            if item.get("nivel_desbloqueado") == target_level
        ),
        None,
    )
    if not isinstance(milestone, dict):
        raise UnifiedSessionError(
            f"nível {target_level} não pode alterar a ficha: milestone correspondente ainda não foi registrado"
        )
    if milestone.get("preparacao_id") != preparation_id:
        raise UnifiedSessionError(
            "milestone_preparacao_id não corresponde ao marco que desbloqueia o próximo nível"
        )
    member = str(milestone.get("membro"))
    if member not in policy["membros"]:
        raise UnifiedSessionError("milestone aponta para membro fora da política Juppongatana")
    return milestone, policy["membros"][member]


def _experience_block(
    *,
    session: int,
    old_level: int,
    new_level: int,
    plan: dict[str, Any],
    milestone: dict[str, Any],
    member_meta: dict[str, Any],
    fingerprint: str,
) -> str:
    choices = plan["escolhas_pendentes"]
    choice_text = ", ".join(choices) if choices else "nenhuma"
    lines = [
        f"<!-- cronica-progressao:{fingerprint} -->",
        f"## Progressão para nível {new_level}",
        "",
        f"- Sessão: {session:03d}",
        f"- Nível anterior: {old_level}",
        f"- Novo nível: {new_level}",
        f"- Marco: {plan['marco']}",
        f"- Motivo: {plan['motivo']}",
        (
            "- Milestone Juppongatana: "
            f"{member_meta.get('nome')} (`{milestone.get('membro')}`), "
            f"{milestone.get('tipo')}, preparação `{milestone.get('preparacao_id')}`"
        ),
        f"- Escolhas pendentes: {choice_text}",
        (
            "- Arquivos atualizados: personagens/jogador/ficha.yaml; "
            "personagens/jogador/resumo-de-poderes.md; estado/estado-atual.yaml; "
            "runtime/contexto.yaml; runtime/cena.yaml; handoff/índice da sessão"
        ),
    ]
    if plan.get("nota"):
        lines.append(f"- Nota: {plan['nota']}")
    return "\n".join(lines).rstrip() + "\n"


def progression_status(repo: Path) -> dict[str, Any]:
    cycle = ciclo_sessoes.status(repo)
    return {
        "schema_cronica_progressao": SCHEMA,
        "fase": "status",
        "ciclo": cycle,
        "progressao": _progression_view(repo),
    }


def apply_progression(
    repo: Path,
    plan: dict[str, Any],
    *,
    fail_after: int | None = None,
) -> dict[str, Any]:
    plan = validate_progression_plan(plan)
    if (repo / consolidar.JOURNAL_PATH).exists():
        raise UnifiedSessionError(
            "há journal pendente; execute `cronica sessao recuperar` antes da progressão"
        )
    cycle = ciclo_sessoes.status(repo)
    if cycle.get("status") != ciclo_sessoes.STATUS_BETWEEN:
        raise UnifiedSessionError(
            "level-up unificado exige campanha entre_sessoes; encerre a sessão primeiro"
        )
    pending = transacoes.load_pending(repo)
    if pending:
        raise UnifiedSessionError(
            "level-up exige buffer transacional vazio; encerre/consolide a sessão primeiro"
        )

    state = _mapping(
        consolidar.load_yaml(repo / consolidar.STATE_PATH),
        "estado/estado-atual.yaml",
    )
    time = _mapping(
        consolidar.load_yaml(repo / consolidar.TIME_PATH),
        "estado/tempo.yaml",
    )
    sheet = _mapping(
        consolidar.load_yaml(repo / consolidar.SHEET_PATH),
        "personagens/jogador/ficha.yaml",
    )
    current_level = _sheet_level(sheet)
    target_level = int(plan["nivel_novo"])
    fingerprint = _plan_fingerprint(plan)
    experience_path = Path("sessoes") / f"{int(cycle['sessao']):03d}" / "experiencia.md"
    existing_experience = (
        (repo / experience_path).read_text(encoding="utf-8")
        if (repo / experience_path).is_file()
        else ""
    )
    marker = f"<!-- cronica-progressao:{fingerprint} -->"

    if current_level == target_level:
        powers = (repo / POWERS_PATH).read_text(encoding="utf-8") if (repo / POWERS_PATH).is_file() else ""
        if marker in existing_experience and powers == plan["resumo_de_poderes"]:
            return {
                "schema_cronica_progressao": SCHEMA,
                "fase": "aplicada",
                "nivel_anterior": target_level - 1,
                "nivel_novo": target_level,
                "ja_aplicada": True,
                "fingerprint": fingerprint,
            }
        raise UnifiedSessionError(
            f"ficha já está no nível {target_level}, mas o plano não corresponde a uma aplicação idempotente registrada"
        )
    if current_level > target_level:
        raise UnifiedSessionError("plano tenta aplicar nível inferior ao nível atual")

    milestone, member_meta = _milestone_for_target(
        repo,
        current_level=current_level,
        target_level=target_level,
        preparation_id=plan["milestone_preparacao_id"],
    )

    new_state = copy.deepcopy(state)
    new_sheet = copy.deepcopy(sheet)
    touched_sheet: set[str] = set()
    for change in plan["alteracoes_ficha"]:
        delta = {
            "alvo": "ficha",
            "op": "set",
            "caminho": change["caminho"],
            "valor": copy.deepcopy(change["valor"]),
        }
        try:
            transacoes.validate_delta(delta)
            transacoes.apply_delta(new_sheet, delta)
        except transacoes.TransactionError as exc:
            raise UnifiedSessionError(str(exc)) from exc
        touched_sheet.add(change["caminho"])

    consolidar._set(new_sheet, "identidade.nivel", target_level)
    touched_sheet.add("identidade.nivel")
    consolidar.sync_mirrors(
        new_state,
        time,
        new_sheet,
        set(),
        set(),
        touched_sheet,
    )
    if consolidar._get(new_state, "personagem.nivel") != target_level:
        raise UnifiedSessionError("espelho estado.personagem.nivel não acompanhou a ficha")

    session = int(cycle["sessao"])
    experience_block = _experience_block(
        session=session,
        old_level=current_level,
        new_level=target_level,
        plan=plan,
        milestone=milestone,
        member_meta=member_meta,
        fingerprint=fingerprint,
    )
    new_experience = _append_text(existing_experience, experience_block)

    runtime_mod = consolidar._runtime_module()
    new_context, new_scene = runtime_mod.build_runtime_from_documents(new_state, time, new_sheet)
    outputs: dict[str, bytes] = {
        consolidar.STATE_PATH.as_posix(): consolidar.dump_yaml(new_state),
        consolidar.SHEET_PATH.as_posix(): consolidar.dump_yaml(new_sheet),
        POWERS_PATH.as_posix(): plan["resumo_de_poderes"].encode("utf-8"),
        experience_path.as_posix(): new_experience.encode("utf-8"),
        "runtime/contexto.yaml": runtime_mod.dump_yaml(new_context).encode("utf-8"),
        "runtime/cena.yaml": runtime_mod.dump_yaml(new_scene).encode("utf-8"),
    }

    ledger = sessoes.read_jsonl(
        repo / "sessoes" / f"{session:03d}" / consolidar.LEDGER_NAME
    )
    handoff = sessoes.build_handoff(
        repo,
        session=session,
        kind="sessao",
        context=new_context,
        scene=new_scene,
        ledger=ledger,
    )
    handoff_rel = sessoes.handoff_rel(session)
    outputs[handoff_rel.as_posix()] = sessoes.dump_yaml_bytes(handoff)
    index = sessoes.build_index(
        repo,
        active_session=session,
        virtual_files=outputs,
    )
    outputs[sessoes.INDEX_PATH.as_posix()] = sessoes.dump_yaml_bytes(index)

    plan_record = {
        "versao": consolidar.SCHEMA_VERSION,
        "sessao": session,
        # tipo=sessao mantém qualquer queda recuperável pela rota legada
        # checkpoint.py recuperar, além de cronica sessao recuperar.
        "tipo": "sessao",
        "batch": f"{PROGRESSION_BATCH_PREFIX}-{target_level}-{fingerprint}",
        "transacoes": [],
        "stale": [],
        "outputs": outputs,
    }
    journal = consolidar.stage_plan(repo, plan_record)
    result = consolidar.install_staged(repo, journal, fail_after=fail_after)
    return {
        "schema_cronica_progressao": SCHEMA,
        "fase": "aplicada",
        "sessao": session,
        "nivel_anterior": current_level,
        "nivel_novo": target_level,
        "milestone": {
            "membro": milestone.get("membro"),
            "nome": member_meta.get("nome"),
            "tipo": milestone.get("tipo"),
            "preparacao_id": milestone.get("preparacao_id"),
        },
        "fingerprint": fingerprint,
        "ja_aplicada": False,
        "arquivos": result.get("arquivos"),
        "experiencia": experience_path.as_posix(),
        "handoff": handoff_rel.as_posix(),
        "indice": sessoes.INDEX_PATH.as_posix(),
        "proximo_passo": {"acao": "iniciar_sessao", "comando": "cronica sessao iniciar"},
    }
