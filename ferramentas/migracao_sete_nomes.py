#!/usr/bin/env python3
"""Migração histórica da sidequest Sete Nomes Antes do Amanhecer.

A migração é deliberadamente estreita: reconhece fatos consolidados até o fim da
Sessão 017, repara a projeção Task48 e sinaliza que a Task50 deve reavaliar a
repercussão. Ela não conclui a verificação institucional, não materializa reação
e não altera os contratos Task41/43/44 já congelados.

Fluxo obrigatório::

    migracao_sete_nomes.py dry-run <mission_id-ou-quest_id>
    migracao_sete_nomes.py aplicar <id> --preparacao-id <id-do-dry-run>

O journal torna uma aplicação interrompida reparável e o receipt histórico torna
repetições idempotentes mesmo depois de a campanha avançar.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

import oportunidades


SCHEMA = 1
MIGRATION_ID = "seven-names-session-017-v1"
DEFAULT_MISSION_ID = "sqe-47ea56e74d59f1c0"
DEFAULT_QUEST_ID = "qse-c721ace29e628024"
JOURNAL = Path("runtime/migracao-sete-nomes-journal.yaml")
RECEIPT = Path("historico/migracoes/sidequests/sete-nomes-session-017-v1.yaml")
MAX_FACTS_IMPORTED = 3
MAX_PROGRESS_BYTES = 24 * 1024
MAX_JOURNAL_BYTES = 128 * 1024
MAX_RECEIPT_BYTES = 12 * 1024
HEX64 = set("0123456789abcdef")

FACTS: tuple[dict[str, Any], ...] = (
    {
        "id": "confissao_cinza_azul_vincula_masao",
        "descricao": (
            "A mulher Cinza-Azul admitiu servir a Masao, coordenar a célula "
            "documental local e participar da operação destinada a remover as crianças."
        ),
        "prova": {
            "fonte": "sessoes/017/resumo.md",
            "evidencia": (
                "Ela admitiu que M. Harrow é uma identidade documental fabricada, "
                "afirmou trabalhar para Masao Hirasawa coordenando a célula documental local"
            ),
        },
        "fases": {},
        "condicoes_sucesso": {},
        "condicoes_falha": {},
        "atores": ["cinza_azul"],
        "substituicoes": [],
        "visibilidade": "narrador",
        "canonizado_em": {"data": "19 Eleasis, 1372 DR", "hora": "23:38"},
    },
    {
        "id": "luath_assume_custodia_depoimento_e_provas",
        "descricao": (
            "Luath compareceu, examinou as provas e recebeu diretamente a confirmação "
            "da cativa, tornando possível a verificação institucional sem concluí-la."
        ),
        "prova": {
            "fonte": "sessoes/017/resumo.md",
            "evidencia": (
                "Luath examinou as provas, recebeu o relato completo e ouviu a cativa "
                "confirmar seus vínculos e a operação contra as crianças."
            ),
        },
        "fases": {"verificar_autoridade": "possivel"},
        "condicoes_sucesso": {},
        "condicoes_falha": {},
        "atores": ["luath", "cinza_azul"],
        "substituicoes": [],
        "visibilidade": "narrador",
        "canonizado_em": {"data": "20 Eleasis, 1372 DR", "hora": "00:24"},
    },
    {
        "id": "criancas_e_cadeia_protegidas_ate_transferencia_segura",
        "descricao": (
            "As crianças permaneceram no abrigo, a prova e a testemunha ficaram sob "
            "custódia e a transferência segura começou a ser preparada."
        ),
        "prova": {
            "fonte": "sessoes/017/resumo.md",
            "evidencia": (
                "Luath aceitou a escolta de Ren; Maerra aceitou um guarda discreto dentro "
                "da Casa até o amanhecer, e o grupo começou a preparar a transferência "
                "segura da cativa e das provas."
            ),
        },
        "fases": {},
        "condicoes_sucesso": {"sucesso_02": "satisfeita"},
        "condicoes_falha": {},
        "atores": ["maerra_thandrel", "luath", "cinza_azul"],
        "substituicoes": [],
        "visibilidade": "narrador",
        "canonizado_em": {"data": "20 Eleasis, 1372 DR", "hora": "00:31"},
    },
)


class SevenNamesMigrationError(ValueError):
    pass


def _map(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SevenNamesMigrationError(f"{label} deve ser mapa")
    return value


def _text(value: Any, label: str, *, maximum: int = 520) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SevenNamesMigrationError(f"{label} deve ser texto não vazio")
    result = " ".join(value.split())
    if len(result) > maximum:
        raise SevenNamesMigrationError(f"{label} excede {maximum} caracteres")
    return result


def _load(path: Path, label: str) -> dict[str, Any]:
    try:
        return _map(yaml.safe_load(path.read_text(encoding="utf-8")), label)
    except (FileNotFoundError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise SevenNamesMigrationError(str(exc)) from exc


def _render(value: dict[str, Any]) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False)


def _digest(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _sha(raw: bytes | str) -> str:
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _valid_digest(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= HEX64


def _atomic_text(path: Path, content: str, maximum: int | None = None) -> None:
    raw = content.encode("utf-8")
    if maximum is not None and len(raw) > maximum:
        raise SevenNamesMigrationError(
            f"{path.as_posix()} excede orçamento de {maximum} bytes: {len(raw)}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "wb", dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        handle.write(raw)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def _atomic_yaml(path: Path, value: dict[str, Any], maximum: int | None = None) -> None:
    _atomic_text(path, _render(value), maximum)


def _raw_text(value: Any, label: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value:
        raise SevenNamesMigrationError(f"{label} deve ser texto não vazio")
    if len(value.encode("utf-8")) > maximum:
        raise SevenNamesMigrationError(f"{label} excede {maximum} bytes")
    return value


def _locate(repo: Path, reference: str) -> tuple[dict[str, Any], str, dict[str, Any]]:
    try:
        index = oportunidades.load_index(repo)
        state = oportunidades.load_state(repo, index)
    except oportunidades.OpportunityError as exc:
        raise SevenNamesMigrationError(str(exc)) from exc
    matches = [
        (mission_id, mission)
        for mission_id, mission in state.get("missoes", {}).items()
        if isinstance(mission, dict)
        and reference in {mission_id, mission.get("id"), mission.get("quest_id")}
    ]
    if len(matches) != 1:
        raise SevenNamesMigrationError(
            f"sidequest inexistente ou ambígua para migração: {reference}"
        )
    mission_id, mission = matches[0]
    if mission.get("origem") != "sidequest_emergente":
        raise SevenNamesMigrationError("migração exige missão emergente Task41")
    return state, mission_id, mission


def _relative_file(repo: Path, raw: Any, label: str, prefix: str) -> tuple[Path, bytes, dict[str, Any]]:
    source = _text(raw, label, maximum=240)
    rel = Path(source)
    if rel.is_absolute() or ".." in rel.parts or not source.startswith(prefix):
        raise SevenNamesMigrationError(f"{label} possui caminho inválido: {source}")
    path = repo / rel
    try:
        content = path.read_bytes()
        doc = _map(yaml.safe_load(content.decode("utf-8")), source)
    except (FileNotFoundError, UnicodeDecodeError, yaml.YAMLError) as exc:
        raise SevenNamesMigrationError(str(exc)) from exc
    return rel, content, doc


def _proof(repo: Path, raw: Any, label: str) -> dict[str, str]:
    proof = _map(raw, label)
    if set(proof) != {"fonte", "evidencia"}:
        raise SevenNamesMigrationError(f"{label} exige fonte e evidencia")
    source = _text(proof.get("fonte"), f"{label}.fonte", maximum=240)
    rel = Path(source)
    if rel.is_absolute() or ".." in rel.parts or source.startswith("narrador/"):
        raise SevenNamesMigrationError(
            f"{label}: planejamento reservado não prova fato histórico"
        )
    path = repo / rel
    if not path.is_file():
        raise SevenNamesMigrationError(f"fonte canônica inexistente: {source}")
    evidence = _text(proof.get("evidencia"), f"{label}.evidencia", maximum=360)
    canonical = " ".join(path.read_text(encoding="utf-8").split())
    if evidence not in canonical:
        raise SevenNamesMigrationError(
            f"evidência literal não encontrada em {source}: {evidence}"
        )
    return {"fonte": source, "evidencia": evidence}


def _contracts(
    repo: Path, mission_id: str, mission: dict[str, Any]
) -> dict[str, Any]:
    quest_rel, quest_raw, quest = _relative_file(
        repo,
        mission.get("arquivo"),
        "missao.arquivo",
        "narrador/sidequests-emergentes/quests/",
    )
    reward_rel, reward_raw, reward = _relative_file(
        repo,
        mission.get("contrato_recompensa"),
        "missao.contrato_recompensa",
        "narrador/sidequests-emergentes/recompensas/",
    )
    stake_rel, stake_raw, stake = _relative_file(
        repo,
        mission.get("contrato_adversarial"),
        "missao.contrato_adversarial",
        "narrador/sidequests-emergentes/stakes/",
    )
    quest_id = mission.get("quest_id")
    progress_expected = Path(f"narrador/sidequests-emergentes/progresso/{quest_id}.yaml")
    progress_path = repo / progress_expected
    progress_raw = progress_path.read_bytes() if progress_path.is_file() else b""
    progress = _load(progress_path, progress_expected.as_posix())

    if (
        quest.get("schema_sidequest_emergente") != 2
        or quest.get("id") != quest_id
        or not _valid_digest(quest.get("spec_digest"))
        or not _valid_digest(quest.get("pacote_task40_digest"))
    ):
        raise SevenNamesMigrationError("contrato Task41 ou seus digests são inválidos")
    if (
        reward.get("schema_recompensas_sidequest") != 1
        or reward.get("mission_id") != mission_id
        or reward.get("quest_id") != quest_id
        or reward.get("quest_file") != quest_rel.as_posix()
        or reward.get("pacote_task40_digest") != quest.get("pacote_task40_digest")
    ):
        raise SevenNamesMigrationError("contrato Task43 diverge da missão Task41")
    if (
        stake.get("schema_integridade_adversarial") != 1
        or stake.get("mission_id") != mission_id
        or stake.get("quest_id") != quest_id
        or not _valid_digest(stake.get("contrato_digest"))
        or stake.get("contrato_digest") != _digest(stake.get("contrato"))
    ):
        raise SevenNamesMigrationError("contrato Task44 ou seu digest são inválidos")
    if (
        progress.get("schema_progressao_sidequest") != 1
        or progress.get("mission_id") != mission_id
        or progress.get("quest_id") != quest_id
        or progress.get("quest_file") != quest_rel.as_posix()
        or progress.get("contrato_recompensa") != reward_rel.as_posix()
        or progress.get("contrato_adversarial") != stake_rel.as_posix()
        or not isinstance(progress.get("contrato"), dict)
        or not isinstance(progress.get("estado"), dict)
    ):
        raise SevenNamesMigrationError("contrato Task45 diverge de Tasks41/43/44")
    return {
        "quest": quest,
        "reward": reward,
        "stake": stake,
        "progress": progress,
        "paths": {
            "task41": quest_rel,
            "task43": reward_rel,
            "task44": stake_rel,
            "task45": progress_expected,
        },
        "raw": {
            "task41": quest_raw,
            "task43": reward_raw,
            "task44": stake_raw,
            "task45": progress_raw,
        },
        "digests": {
            "task41_spec": quest["spec_digest"],
            "task41_file": _sha(quest_raw),
            "task43_file": _sha(reward_raw),
            "task44_contract": stake["contrato_digest"],
            "task44_file": _sha(stake_raw),
            "task45_file": _sha(progress_raw),
        },
    }


def _validate_fact_targets(progress: dict[str, Any], fact: dict[str, Any]) -> None:
    state = _map(progress.get("estado"), "Task45.estado")
    groups = {
        "fases": state.get("fases"),
        "condicoes_sucesso": state.get("condicoes_sucesso"),
        "condicoes_falha": state.get("condicoes_falha"),
    }
    allowed = {
        "fases": {"indeterminada", "possivel", "impossivel", "resolvida"},
        "condicoes_sucesso": {"pendente", "satisfeita", "inviavel"},
        "condicoes_falha": {"pendente", "satisfeita", "inviavel"},
    }
    for group, values in groups.items():
        target = _map(values, f"Task45.estado.{group}")
        for item_id, wanted in fact[group].items():
            if item_id not in target or wanted not in allowed[group]:
                raise SevenNamesMigrationError(
                    f"fato {fact['id']} possui transição inválida: {group}.{item_id}={wanted}"
                )


def _normalized_fact(repo: Path, progress: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    fact = copy.deepcopy(raw)
    fact["prova"] = _proof(repo, fact["prova"], f"fato {fact['id']}.prova")
    _validate_fact_targets(progress, fact)
    return fact


def _apply_fact(progress: dict[str, Any], fact: dict[str, Any]) -> bool:
    state = progress["estado"]
    facts = _map(state.get("fatos"), "Task45.estado.fatos")
    existing = facts.get(fact["id"])
    if existing is not None:
        if existing != fact:
            raise SevenNamesMigrationError(
                f"fato histórico {fact['id']} já existe com conteúdo divergente"
            )
        return False
    facts[fact["id"]] = copy.deepcopy(fact)
    for phase_id, wanted in fact["fases"].items():
        current = state["fases"][phase_id].get("estado")
        if current == "resolvida" and wanted != "resolvida":
            continue
        state["fases"][phase_id] = {
            "estado": wanted,
            "fato_id": fact["id"],
            "motivo_automatico": None,
        }
    for group in ("condicoes_sucesso", "condicoes_falha"):
        for condition_id, wanted in fact[group].items():
            current = state[group][condition_id].get("estado")
            if current in {"satisfeita", "inviavel"} and current != wanted:
                raise SevenNamesMigrationError(
                    f"migração não pode reverter condição {condition_id}: {current} -> {wanted}"
                )
            state[group][condition_id]["estado"] = wanted
            state[group][condition_id]["fato_id"] = fact["id"]
    history = state.setdefault("historico_recente", [])
    history.append(
        {
            "tipo": "fato_historico_migrado",
            "id": fact["id"],
            "fonte": fact["prova"]["fonte"],
            "migracao_id": MIGRATION_ID,
            "atores": copy.deepcopy(fact["atores"]),
            "substituicoes": copy.deepcopy(fact["substituicoes"]),
        }
    )
    state["historico_recente"] = history[-32:]
    return True


def _target_documents(
    repo: Path,
    state: dict[str, Any],
    mission_id: str,
    mission: dict[str, Any],
    contracts: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    if mission.get("estado") != "aceita":
        raise SevenNamesMigrationError(
            "migração inicial exige Sete Nomes ainda aceita; não reabre missão terminal"
        )
    progress = copy.deepcopy(contracts["progress"])
    target_state = copy.deepcopy(state)
    target_mission = target_state["missoes"][mission_id]
    progress_rel = contracts["paths"]["task45"].as_posix()
    target_mission["progresso_sidequest"] = progress_rel
    imported: list[str] = []
    for raw in FACTS:
        fact = _normalized_fact(repo, progress, raw)
        if _apply_fact(progress, fact):
            imported.append(fact["id"])

    actors = _map(progress["estado"].get("atores"), "Task45.estado.atores")
    if "luath" not in actors:
        actors["luath"] = {
            "estado": "disponivel",
            "vida_estado": None,
            "fonte": "estado/npcs/luath.yaml",
        }
    progress["estado"]["necessita_reavaliacao_reacao"] = {
        "estado": True,
        "gatilho_tipo": "progresso_excepcional",
        "fato_id": "confissao_cinza_azul_vincula_masao",
        "motivo": (
            "Captura de coordenadora, confissão e provas preservadas alteraram a "
            "exposição da rede; Task50 deve avaliar sem presumir conhecimento adversarial."
        ),
    }
    progress["estado"].setdefault("migracoes_aplicadas", {})[MIGRATION_ID] = {
        "instante_representado": {"data": "20 Eleasis, 1372 DR", "hora": "00:31"},
        "terminal_inventado": False,
        "contrato_task44_alterado": False,
    }
    success_states = [
        row.get("estado")
        for row in _map(
            progress["estado"].get("condicoes_sucesso"),
            "Task45.estado.condicoes_sucesso",
        ).values()
        if isinstance(row, dict)
    ]
    failure_states = [
        row.get("estado")
        for row in _map(
            progress["estado"].get("condicoes_falha"),
            "Task45.estado.condicoes_falha",
        ).values()
        if isinstance(row, dict)
    ]
    if all(value == "satisfeita" for value in success_states) or any(
        value == "satisfeita" for value in failure_states
    ):
        raise SevenNamesMigrationError(
            "snapshot histórico produziria terminal; a migração não pode completar fato ausente"
        )
    if progress["estado"].get("terminal") is not None:
        raise SevenNamesMigrationError("migração não pode reescrever terminal existente")
    return target_state, progress, imported


def _receipt(repo: Path) -> dict[str, Any] | None:
    return _load(repo / RECEIPT, RECEIPT.as_posix()) if (repo / RECEIPT).is_file() else None


def _already_applied(repo: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    reference = str(receipt.get("mission_id") or DEFAULT_MISSION_ID)
    state, mission_id, mission = _locate(repo, reference)
    contracts = _contracts(repo, mission_id, mission)
    progress = contracts["progress"]
    migration = (progress.get("estado") or {}).get("migracoes_aplicadas", {}).get(MIGRATION_ID)
    if not isinstance(migration, dict):
        raise SevenNamesMigrationError("receipt existe, mas marcador de migração desapareceu")
    facts = _map(progress["estado"].get("fatos"), "Task45.estado.fatos")
    for raw in FACTS:
        expected = _normalized_fact(repo, progress, raw)
        if facts.get(raw["id"]) != expected:
            raise SevenNamesMigrationError(
                f"receipt existe, mas fato migrado divergiu: {raw['id']}"
            )
    if contracts["digests"]["task44_file"] != receipt.get("task44_sha256"):
        raise SevenNamesMigrationError("contrato Task44 mudou depois da migração")
    return {
        "state": state,
        "mission_id": mission_id,
        "mission": mission,
        "contracts": contracts,
    }


def dry_run(repo: Path, reference: str = DEFAULT_MISSION_ID) -> dict[str, Any]:
    repo = repo.resolve()
    existing_receipt = _receipt(repo)
    if existing_receipt is not None:
        applied = _already_applied(repo, existing_receipt)
        return {
            "schema_migracao_sete_nomes": SCHEMA,
            "ok": True,
            "fase": "dry_run",
            "read_only": True,
            "resultado": "ja_aplicada",
            "migration_id": MIGRATION_ID,
            "preparacao_id": existing_receipt["preparacao_id"],
            "mission_id": applied["mission_id"],
            "quest_id": applied["mission"].get("quest_id"),
            "fatos_a_importar": [],
            "necessita_reavaliacao_reacao": True,
            "terminal": applied["contracts"]["progress"]["estado"].get("terminal"),
            "mutacoes_aplicadas": False,
            "digests": copy.deepcopy(applied["contracts"]["digests"]),
        }

    state, mission_id, mission = _locate(repo, reference)
    if mission.get("quest_id") != DEFAULT_QUEST_ID and reference in {
        DEFAULT_MISSION_ID,
        DEFAULT_QUEST_ID,
    }:
        raise SevenNamesMigrationError("IDs canônicos de Sete Nomes divergiram")
    contracts = _contracts(repo, mission_id, mission)
    target_state, target_progress, imported = _target_documents(
        repo, state, mission_id, mission, contracts
    )
    state_before = (repo / oportunidades.STATE).read_bytes()
    state_after = _render(target_state)
    progress_before = contracts["raw"]["task45"]
    progress_after = _render(target_progress)
    if len(progress_after.encode("utf-8")) > MAX_PROGRESS_BYTES:
        raise SevenNamesMigrationError(
            "progresso Task45 excede orçamento após migração: "
            f"{len(progress_after.encode('utf-8'))} > {MAX_PROGRESS_BYTES} bytes"
        )
    preparation_id = "snm-prep-" + _digest(
        {
            "migration_id": MIGRATION_ID,
            "mission_id": mission_id,
            "quest_id": mission.get("quest_id"),
            "task41": contracts["digests"]["task41_file"],
            "task43": contracts["digests"]["task43_file"],
            "task44": contracts["digests"]["task44_file"],
            "task45_before": _sha(progress_before),
            "state_before": _sha(state_before),
            "task45_after": _sha(progress_after),
            "state_after": _sha(state_after),
        }
    )[:24]
    return {
        "schema_migracao_sete_nomes": SCHEMA,
        "ok": True,
        "fase": "dry_run",
        "read_only": True,
        "resultado": "mudancas_planejadas" if imported or state_after.encode() != state_before else "sem_mudancas",
        "migration_id": MIGRATION_ID,
        "preparacao_id": preparation_id,
        "mission_id": mission_id,
        "quest_id": mission.get("quest_id"),
        "fatos_a_importar": imported,
        "fase_institucional": target_progress["estado"]["fases"]["verificar_autoridade"]["estado"],
        "condicoes_sucesso": {
            key: value.get("estado")
            for key, value in target_progress["estado"]["condicoes_sucesso"].items()
        },
        "necessita_reavaliacao_reacao": True,
        "terminal": target_progress["estado"].get("terminal"),
        "mutacoes_aplicadas": False,
        "digests": copy.deepcopy(contracts["digests"]),
        "_plano": {
            "state_before_sha256": _sha(state_before),
            "state_after": state_after,
            "progress_before_sha256": _sha(progress_before),
            "progress_after": progress_after,
            "task44_sha256": contracts["digests"]["task44_file"],
            "progress_path": contracts["paths"]["task45"].as_posix(),
        },
    }


def _public_plan(plan: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(plan)
    result.pop("_plano", None)
    return result


def _journal_from_plan(plan: dict[str, Any]) -> dict[str, Any]:
    private = plan["_plano"]
    progress_final_sha = _sha(private["progress_after"])
    state_final_sha = _sha(private["state_after"])
    receipt = {
        "schema_migracao_sete_nomes_receipt": SCHEMA,
        "natureza": "registro_migracao_historica",
        "migration_id": MIGRATION_ID,
        "preparacao_id": plan["preparacao_id"],
        "mission_id": plan["mission_id"],
        "quest_id": plan["quest_id"],
        "instante_representado": {"data": "20 Eleasis, 1372 DR", "hora": "00:31"},
        "motivo": (
            "Reconciliar fatos canônicos das Sessões 016–017 que ficaram atrás do "
            "progresso operacional da sidequest aceita."
        ),
        "task44_sha256": private["task44_sha256"],
        "resultado": {
            "task45_sha256": progress_final_sha,
            "estado_oportunidades_sha256": state_final_sha,
            "terminal_inventado": False,
            "reacao_materializada": False,
        },
    }
    return {
        "schema_migracao_sete_nomes_journal": SCHEMA,
        "migration_id": MIGRATION_ID,
        "preparacao_id": plan["preparacao_id"],
        "mission_id": plan["mission_id"],
        "task44_sha256": private["task44_sha256"],
        "instalados": [],
        "targets": [
            {
                "path": private["progress_path"],
                "before_sha256": private["progress_before_sha256"],
                "final_sha256": progress_final_sha,
                "content": private["progress_after"],
            },
            {
                "path": oportunidades.STATE.as_posix(),
                "before_sha256": private["state_before_sha256"],
                "final_sha256": state_final_sha,
                "content": private["state_after"],
            },
            {
                "path": RECEIPT.as_posix(),
                "before_sha256": _sha(b""),
                "final_sha256": _sha(_render(receipt)),
                "content": _render(receipt),
            },
        ],
    }


def _load_journal(repo: Path) -> dict[str, Any] | None:
    return _load(repo / JOURNAL, JOURNAL.as_posix()) if (repo / JOURNAL).is_file() else None


def _install_journal(
    repo: Path, journal: dict[str, Any], *, fail_after: int | None = None
) -> None:
    installed = set(journal.get("instalados") or [])
    writes = 0
    for target in journal.get("targets") or []:
        rel = Path(_text(target.get("path"), "journal.target.path", maximum=240))
        if rel.is_absolute() or ".." in rel.parts:
            raise SevenNamesMigrationError("journal aponta para fora do repositório")
        path = repo / rel
        current = path.read_bytes() if path.is_file() else b""
        current_sha = _sha(current)
        if current_sha == target.get("final_sha256"):
            pass
        elif current_sha == target.get("before_sha256"):
            _atomic_text(
                path,
                _raw_text(
                    target.get("content"),
                    "journal.target.content",
                    maximum=MAX_JOURNAL_BYTES,
                ),
                MAX_RECEIPT_BYTES if rel == RECEIPT else None,
            )
            writes += 1
        else:
            raise SevenNamesMigrationError(
                f"arquivo mudou concorrentemente durante migração: {rel.as_posix()}"
            )
        installed.add(rel.as_posix())
        journal["instalados"] = sorted(installed)
        _atomic_yaml(repo / JOURNAL, journal, MAX_JOURNAL_BYTES)
        if fail_after is not None and writes >= fail_after:
            raise SevenNamesMigrationError("falha simulada durante aplicação da migração")


def apply(
    repo: Path,
    reference: str,
    preparation_id: str,
    *,
    fail_after: int | None = None,
) -> dict[str, Any]:
    repo = repo.resolve()
    if not isinstance(preparation_id, str) or not preparation_id.startswith("snm-prep-"):
        raise SevenNamesMigrationError("aplicar exige preparacao_id produzido pelo dry-run")
    existing_receipt = _receipt(repo)
    if existing_receipt is not None:
        if existing_receipt.get("preparacao_id") != preparation_id:
            raise SevenNamesMigrationError("migração já aplicada com preparação divergente")
        applied = _already_applied(repo, existing_receipt)
        if reference not in {applied["mission_id"], applied["mission"].get("quest_id")}:
            raise SevenNamesMigrationError(
                "referência não corresponde à migração Sete Nomes já aplicada"
            )
        return {
            "ok": True,
            "resultado": "ja_aplicada",
            "migration_id": MIGRATION_ID,
            "preparacao_id": preparation_id,
            "mission_id": applied["mission_id"],
            "quest_id": applied["mission"].get("quest_id"),
            "idempotente": True,
            "contrato_task44_alterado": False,
            "reacao_materializada": False,
        }

    journal = _load_journal(repo)
    recovered = journal is not None
    if journal is not None:
        if (
            journal.get("migration_id") != MIGRATION_ID
            or journal.get("preparacao_id") != preparation_id
        ):
            raise SevenNamesMigrationError(
                "há outra migração interrompida; repita a preparação original"
            )
        if reference not in {journal.get("mission_id"), DEFAULT_QUEST_ID}:
            raise SevenNamesMigrationError(
                "referência não corresponde à migração Sete Nomes interrompida"
            )
    else:
        plan = dry_run(repo, reference)
        if plan["preparacao_id"] != preparation_id:
            raise SevenNamesMigrationError(
                "dry-run ficou obsoleto; execute novamente antes de aplicar"
            )
        journal = _journal_from_plan(plan)
        _atomic_yaml(repo / JOURNAL, journal, MAX_JOURNAL_BYTES)

    _install_journal(repo, journal, fail_after=fail_after)
    receipt = _receipt(repo)
    if receipt is None:
        raise SevenNamesMigrationError("migração terminou sem receipt histórico")
    applied = _already_applied(repo, receipt)
    (repo / JOURNAL).unlink(missing_ok=True)
    return {
        "ok": True,
        "resultado": "recuperada" if recovered else "aplicada",
        "migration_id": MIGRATION_ID,
        "preparacao_id": preparation_id,
        "mission_id": applied["mission_id"],
        "quest_id": applied["mission"].get("quest_id"),
        "fatos_importados": [fact["id"] for fact in FACTS],
        "fase_institucional": applied["contracts"]["progress"]["estado"]["fases"]["verificar_autoridade"]["estado"],
        "terminal": applied["contracts"]["progress"]["estado"].get("terminal"),
        "necessita_reavaliacao_reacao": True,
        "idempotente": True,
        "contrato_task44_alterado": False,
        "reacao_materializada": False,
    }


def check(repo: Path) -> dict[str, Any]:
    errors: list[str] = []
    receipt = None
    try:
        receipt = _receipt(repo.resolve())
        if receipt is None:
            errors.append("migração Sete Nomes ainda não foi aplicada")
        else:
            _already_applied(repo.resolve(), receipt)
        if (repo / JOURNAL).is_file():
            errors.append("há journal aberto da migração Sete Nomes")
    except (SevenNamesMigrationError, OSError, yaml.YAMLError) as exc:
        errors.append(str(exc))
    return {
        "ok": not errors,
        "erros": errors,
        "migration_id": MIGRATION_ID,
        "receipt": RECEIPT.as_posix() if receipt is not None else None,
        "contrato": {
            "dry_run_obrigatorio": True,
            "max_fatos_importados": MAX_FACTS_IMPORTED,
            "max_progresso_bytes": MAX_PROGRESS_BYTES,
            "estado_vivo_usado_como_fixture": False,
            "contrato_task44_preservado_byte_a_byte": True,
            "terminal_inventado": False,
            "reacao_materializada_na_migracao": False,
            "rng_novo": 0,
            "scheduler_novo": 0,
            "scan_global": 0,
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="cmd", required=True)
    dry = sub.add_parser("dry-run")
    dry.add_argument("referencia", nargs="?", default=DEFAULT_MISSION_ID)
    run = sub.add_parser("aplicar")
    run.add_argument("referencia", nargs="?", default=DEFAULT_MISSION_ID)
    run.add_argument("--preparacao-id", required=True)
    sub.add_parser("check")
    args = parser.parse_args(argv)
    repo = args.repo.resolve()
    try:
        if args.cmd == "dry-run":
            result = _public_plan(dry_run(repo, args.referencia))
        elif args.cmd == "aplicar":
            result = apply(repo, args.referencia, args.preparacao_id)
        else:
            result = check(repo)
        print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
        return 0 if result.get("ok") else 1
    except (SevenNamesMigrationError, OSError, yaml.YAMLError) as exc:
        print(f"FALHA — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
