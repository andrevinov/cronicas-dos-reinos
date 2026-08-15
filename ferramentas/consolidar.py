#!/usr/bin/env python3
"""Consolida deltas de narração em cânone, em lote, com recuperação idempotente.

A Etapa 7 mantém cada avanço narrativo em dois lugares: transcrição e
`runtime/eventos-pendentes.jsonl`. Esta ferramenta fecha o circuito sem voltar à
write amplification por turno.

Comandos principais:

    python3 ferramentas/consolidar.py cena
    python3 ferramentas/consolidar.py sessao
    python3 ferramentas/consolidar.py recuperar
    python3 ferramentas/consolidar.py status
    python3 ferramentas/consolidar.py check

`cena` e `sessao` aplicam todos os eventos pendentes da sessão atual. A diferença
é documental: `sessao` marca os artefatos de fechamento como encerrados. Nenhum
dos dois avança automaticamente o número da sessão nem inventa fatos ausentes dos
deltas.

A escrita multiarquivo usa um journal + staging. Enquanto o journal existe,
`contexto.py` e `turno.py` recusam operação normal. Em caso de interrupção, basta
executar `recuperar` (ou repetir `cena`/`sessao`) para instalar exatamente os
mesmos bytes preparados, sem reaplicar deltas.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
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

import transacoes
import turno

SCHEMA_VERSION = 1
JOURNAL_PATH = Path("runtime/consolidacao-em-andamento.json")
STAGE_DIR = Path("runtime/.consolidacao-stage")
LEDGER_NAME = "consolidacoes.jsonl"
AUTO_START = "<!-- consolidacao-automatica:inicio -->"
AUTO_END = "<!-- consolidacao-automatica:fim -->"
MAX_ENTITY_FRAGMENT = 12 * 1024
MAX_INDEX_BYTES = 48 * 1024

PUBLIC_TARGETS = {"estado", "tempo", "ficha", "progressao", "conhecimento", "consequencia"}
PUBLIC_PREFIXES = ("relacao:", "npc:")
RESERVED_PREFIXES = ("relogio:",)

STATE_PATH = Path("estado/estado-atual.yaml")
TIME_PATH = Path("estado/tempo.yaml")
SHEET_PATH = Path("personagens/jogador/ficha.yaml")
REL_INDEX_PATH = Path("estado/relacoes/index.yaml")
NPC_INDEX_PATH = Path("estado/npcs/index.yaml")
KNOW_INDEX_PATH = Path("personagens/jogador/conhecimento/index.yaml")
KNOW_ACTIVE_PATH = Path("personagens/jogador/conhecimento/ativo.yaml")


class ConsolidationError(RuntimeError):
    pass


def _runtime_module():
    path = Path(__file__).with_name("gerar-runtime.py")
    spec = importlib.util.spec_from_file_location("gerar_runtime_consolidacao", path)
    if spec is None or spec.loader is None:
        raise ConsolidationError("não foi possível carregar gerar-runtime.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def dump_yaml(value: Any) -> bytes:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=110).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path: Path) -> str | None:
    if not path.is_file():
        return None
    return sha256_bytes(path.read_bytes())


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def safe_id(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value).strip("-.")
    if cleaned and len(cleaned) <= 80:
        return cleaned
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def jsonl_text(records: Iterable[dict[str, Any]]) -> bytes:
    lines = [canonical_json(record) for record in records]
    return (("\n".join(lines) + "\n") if lines else "").encode("utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    result: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ConsolidationError(f"JSONL inválido em {path}:{number}: {exc}") from exc
        if not isinstance(item, dict):
            raise ConsolidationError(f"registro não-objeto em {path}:{number}")
        result.append(item)
    return result


def _get(document: dict[str, Any], dotted: str) -> Any:
    current: Any = document
    for part in dotted.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _set(document: dict[str, Any], dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    current = document
    for part in parts[:-1]:
        child = current.get(part)
        if child is None:
            child = {}
            current[part] = child
        if not isinstance(child, dict):
            raise ConsolidationError(f"não é possível espelhar valor em {dotted}: {part} não é mapa")
        current = child
    current[parts[-1]] = copy.deepcopy(value)


def _atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
        tmp = Path(handle.name)
    os.replace(tmp, path)


def _atomic_write_json(path: Path, value: Any) -> None:
    data = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _atomic_write_bytes(path, data)


def current_session(repo: Path) -> int:
    return turno.current_session(repo)


def ledger_path(repo: Path, session: int) -> Path:
    return repo / "sessoes" / f"{session:03d}" / LEDGER_NAME


def load_ledger(repo: Path, session: int) -> list[dict[str, Any]]:
    records = read_jsonl(ledger_path(repo, session))
    batches: set[str] = set()
    txids: set[str] = set()
    for item in records:
        batch = item.get("id")
        if not isinstance(batch, str) or not batch:
            raise ConsolidationError(f"ledger da sessão {session:03d} possui batch sem id")
        if batch in batches:
            raise ConsolidationError(f"batch duplicado no ledger: {batch}")
        batches.add(batch)
        for txid in item.get("transacoes", []):
            if txid in txids:
                raise ConsolidationError(f"transação consolidada duas vezes no ledger: {txid}")
            txids.add(txid)
    return records


def consolidated_ids(ledger: Iterable[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for item in ledger:
        result.update(str(txid) for txid in item.get("transacoes", []))
    return result


def batch_id(session: int, kind: str, records: list[dict[str, Any]]) -> str:
    seed = {"sessao": session, "tipo": kind, "transacoes": [item["id"] for item in records]}
    digest = hashlib.sha256(canonical_json(seed).encode("utf-8")).hexdigest()[:16]
    return f"s{session:03d}-{kind}-{digest}"


def public_target(target: str) -> bool:
    return target in PUBLIC_TARGETS or target.startswith(PUBLIC_PREFIXES)


def validate_visibility(delta: dict[str, Any]) -> None:
    target = str(delta.get("alvo") or "")
    visibility = delta.get("visibilidade", "operacional")
    if visibility == "narrador" and public_target(target):
        raise ConsolidationError(
            f"delta reservado não pode ser consolidado em domínio público: {target}. "
            "Use alvo reservado (por exemplo relogio:<id>) ou registre apenas em rolagens_ocultas."
        )
    if visibility != "narrador" and target.startswith(RESERVED_PREFIXES):
        # Um relógio pode ser percebido pelo jogador, mas seu estado mecânico continua reservado.
        return


def _copy_delta(delta: dict[str, Any], *, path: str | None = None) -> dict[str, Any]:
    value = copy.deepcopy(delta)
    if path is not None:
        value["caminho"] = path
    return value


def _apply(document: dict[str, Any], delta: dict[str, Any], *, path: str | None = None) -> None:
    mapped = _copy_delta(delta, path=path)
    try:
        transacoes.apply_delta(document, mapped)
    except transacoes.TransactionError as exc:
        raise ConsolidationError(str(exc)) from exc


def snapshot(estado: dict[str, Any], tempo: dict[str, Any], ficha: dict[str, Any]) -> dict[str, Any]:
    recursos = estado.get("recursos") or {}
    pv = recursos.get("pontos_de_vida") or {}
    ki = recursos.get("ki") or {}
    dinheiro = recursos.get("dinheiro") or {}
    personagem = estado.get("personagem") or {}
    campanha = estado.get("campanha") or {}
    local = estado.get("localizacao") or {}
    tempo_estado = estado.get("tempo") or {}
    return {
        "sessao": campanha.get("sessao_atual"),
        "modo": campanha.get("modo_de_cena_atual"),
        "personagem": personagem.get("nome"),
        "nivel": personagem.get("nivel"),
        "pv": f"{pv.get('atuais')}/{pv.get('maximos')}",
        "ki": f"{ki.get('atuais')}/{ki.get('maximos')}",
        "ca": recursos.get("classe_de_armadura"),
        "dinheiro_po": dinheiro.get("po"),
        "data": tempo_estado.get("data_exata") or ((tempo.get("data_atual") or {}).get("valor")),
        "hora": tempo_estado.get("hora_aproximada") or tempo.get("hora_aproximada"),
        "area": local.get("area"),
        "ponto_exato": local.get("ponto_exato"),
        "nivel_ficha": ((ficha.get("identidade") or {}).get("nivel")),
    }


TIME_MIRRORS = (
    ("tempo.data_exata", "data_atual.valor"),
    ("tempo.hora_aproximada", "hora_aproximada"),
    ("tempo.periodo_do_dia", "periodo_do_dia"),
    ("tempo.clima", "clima"),
    ("tempo.prazo_relevante", "prazo_relevante"),
)
SHEET_MIRRORS = (
    ("personagem.nivel", "identidade.nivel"),
    ("recursos.pontos_de_vida.atuais", "combate.pontos_de_vida.atuais"),
    ("recursos.pontos_de_vida.maximos", "combate.pontos_de_vida.maximos"),
    ("recursos.ki.atuais", "recursos_de_classe.ki.pontos_atuais"),
    ("recursos.ki.maximos", "recursos_de_classe.ki.pontos_maximos"),
    ("recursos.classe_de_armadura", "combate.classe_de_armadura.valor"),
    ("recursos.dinheiro.po", "equipamento.dinheiro.po"),
)


def sync_mirrors(
    estado: dict[str, Any],
    tempo: dict[str, Any],
    ficha: dict[str, Any],
    touched_state: set[str],
    touched_time: set[str],
    touched_sheet: set[str],
) -> None:
    for state_path, time_path in TIME_MIRRORS:
        left = state_path in touched_state
        right = time_path in touched_time
        state_value = _get(estado, state_path)
        time_value = _get(tempo, time_path)
        if left and right and state_value != time_value:
            raise ConsolidationError(
                f"deltas conflitantes para o mesmo fato temporal: estado.{state_path}={state_value!r}, "
                f"tempo.{time_path}={time_value!r}"
            )
        if left:
            _set(tempo, time_path, state_value)
        elif right:
            _set(estado, state_path, time_value)
        elif state_value != time_value and state_value is not None and time_value is not None:
            raise ConsolidationError(
                f"estado e tempo já estavam divergentes antes da consolidação: {state_path} != {time_path}"
            )

    for state_path, sheet_path in SHEET_MIRRORS:
        left = state_path in touched_state
        right = sheet_path in touched_sheet
        state_value = _get(estado, state_path)
        sheet_value = _get(ficha, sheet_path)
        if left and right and state_value != sheet_value:
            raise ConsolidationError(
                f"deltas conflitantes entre estado e ficha: {state_path}={state_value!r}, "
                f"{sheet_path}={sheet_value!r}"
            )
        if left:
            _set(ficha, sheet_path, state_value)
        elif right:
            _set(estado, state_path, sheet_value)
        elif state_value != sheet_value and state_value is not None and sheet_value is not None:
            raise ConsolidationError(
                f"estado e ficha já estavam divergentes antes da consolidação: {state_path} != {sheet_path}"
            )


def _entity_doc(
    repo: Path,
    index: dict[str, Any],
    mapping_key: str,
    entity_id: str,
    kind: str,
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    mapping = index.setdefault(mapping_key, {})
    if not isinstance(mapping, dict):
        raise ConsolidationError(f"índice inválido: {mapping_key}")
    entry = mapping.get(entity_id)
    if isinstance(entry, dict) and isinstance(entry.get("arquivo"), str):
        rel = Path(entry["arquivo"])
        path = repo / rel
        if not path.is_file():
            raise ConsolidationError(f"fragmento indexado ausente: {rel}")
        doc = load_yaml(path) or {}
        if not isinstance(doc, dict):
            raise ConsolidationError(f"fragmento inválido: {rel}")
        return doc, entry, rel

    if kind == "relacao":
        rel = Path("estado/relacoes") / f"{entity_id}.yaml"
        history = Path("historico/relacoes") / f"{entity_id}.yaml"
        doc = {
            "schema_relacao": 2,
            "natureza": "estado_relacao_atual",
            "id": entity_id,
            "historico": history.as_posix(),
            "relacao": {},
        }
        entry = {"arquivo": rel.as_posix(), "historico": history.as_posix()}
    else:
        rel = Path("estado/npcs") / f"{entity_id}.yaml"
        doc = {
            "schema_npc": 2,
            "natureza": "medidores_npc_atuais",
            "id": entity_id,
            "npc": {},
        }
        entry = {"arquivo": rel.as_posix()}
    mapping[entity_id] = entry
    return doc, entry, rel


def _history_event(record: dict[str, Any], deltas: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "transacao": record["id"],
        "sessao": record["sessao"],
        "resumo": record.get("resumo", ""),
        "deltas": copy.deepcopy(deltas),
    }


def _append_history(
    repo: Path,
    path: Path,
    entity_id: str,
    kind: str,
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    absolute = repo / path
    if absolute.is_file():
        history = load_yaml(absolute) or {}
        if not isinstance(history, dict):
            raise ConsolidationError(f"histórico inválido: {path}")
    else:
        history = {
            "schema_historico_relacao" if kind == "relacao" else "schema_historico_npc": 2,
            "id": entity_id,
            "origem": "transacoes-pos-etapa-8",
        }
    existing = history.setdefault("eventos_pos_migracao", [])
    if not isinstance(existing, list):
        raise ConsolidationError(f"eventos_pos_migracao não é lista: {path}")
    seen = {item.get("transacao") for item in existing if isinstance(item, dict)}
    for event in events:
        if event.get("transacao") not in seen:
            existing.append(copy.deepcopy(event))
            seen.add(event.get("transacao"))
    return history


def _update_relation_entry(entry: dict[str, Any], payload: dict[str, Any], rel: Path, history: Path, size: int) -> None:
    for key in ("nome", "tipo", "status", "atitude_para_ren", "confianca", "respeito"):
        if key in payload:
            entry[key] = copy.deepcopy(payload[key])
    entry["arquivo"] = rel.as_posix()
    entry["historico"] = history.as_posix()
    entry["bytes_fragmento"] = size
    entry["campos_atuais"] = len(payload)


def _update_npc_entry(entry: dict[str, Any], payload: dict[str, Any], rel: Path, history: Path, size: int) -> None:
    for key in ("nome", "grupo", "medidores", "natureza_do_vinculo", "subtexto_romantico"):
        if key in payload:
            entry[key] = copy.deepcopy(payload[key])
    entry["arquivo"] = rel.as_posix()
    entry["historico"] = history.as_posix()
    entry["bytes_fragmento"] = size


def _knowledge_text(record: dict[str, Any], values: list[Any]) -> str:
    lines = [f"### Sessão {record['sessao']:03d}: {record.get('resumo') or record['id']}", "", f"<!-- origem-transacao:{record['id']} -->", ""]
    for value in values:
        if isinstance(value, str):
            lines.append(f"- {value}")
        elif isinstance(value, dict):
            assunto = value.get("assunto")
            texto = value.get("texto")
            if assunto is not None and texto is not None:
                lines.append(f"- **{assunto}:** {texto}")
            elif texto is not None:
                lines.append(f"- {texto}")
            else:
                rendered = yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=100).rstrip()
                lines.extend(["- Registro estruturado:", "", "```yaml", rendered, "```"])
        else:
            lines.append(f"- {json.dumps(value, ensure_ascii=False, sort_keys=True)}")
    return "\n".join(lines).rstrip() + "\n"


def _build_incremental_knowledge(
    repo: Path,
    session: int,
    records: list[dict[str, Any]],
    knowledge_by_tx: dict[str, list[Any]],
    outputs: dict[str, bytes],
) -> None:
    if not knowledge_by_tx:
        return
    index = load_yaml(repo / KNOW_INDEX_PATH) or {}
    active = load_yaml(repo / KNOW_ACTIVE_PATH) or {}
    if not isinstance(index, dict) or not isinstance(active, dict):
        raise ConsolidationError("índices de conhecimento inválidos")

    session_dir = Path("personagens/jogador/conhecimento/incrementais") / f"sessao-{session:03d}"
    session_index_rel = session_dir / "index.yaml"
    session_index_abs = repo / session_index_rel
    session_index = load_yaml(session_index_abs) if session_index_abs.is_file() else {
        "schema_conhecimento_incremental": 1,
        "sessao": session,
        "fragmentos": [],
    }
    fragments = session_index.setdefault("fragmentos", [])
    if not isinstance(fragments, list):
        raise ConsolidationError("índice incremental de conhecimento inválido")
    known = {item.get("transacao") for item in fragments if isinstance(item, dict)}
    record_map = {record["id"]: record for record in records}

    for txid, values in knowledge_by_tx.items():
        if txid in known:
            continue
        record = record_map[txid]
        filename = f"tx-{safe_id(txid)}.md"
        rel = session_dir / filename
        text = _knowledge_text(record, values)
        outputs[rel.as_posix()] = text.encode("utf-8")
        fragments.append({
            "transacao": txid,
            "titulo": record.get("resumo") or txid,
            "arquivo": rel.as_posix(),
            "bytes": len(text.encode("utf-8")),
        })
        known.add(txid)

    session_index["quantidade"] = len(fragments)
    outputs[session_index_rel.as_posix()] = dump_yaml(session_index)

    incrementals = index.setdefault("incrementais", {})
    if not isinstance(incrementals, dict):
        raise ConsolidationError("conhecimento/index.yaml.incrementais precisa ser mapa")
    incrementals[str(session)] = {
        "index": session_index_rel.as_posix(),
        "quantidade": len(fragments),
    }
    outputs[KNOW_INDEX_PATH.as_posix()] = dump_yaml(index)

    recent = fragments[-8:]
    active["sessao_atual_da_campanha"] = session
    active["sessao_mais_recente_indexada"] = session
    active["incrementais_recentes"] = [
        {
            "titulo": item.get("titulo"),
            "arquivos": [item.get("arquivo")],
            "bytes": item.get("bytes"),
            "transacao": item.get("transacao"),
        }
        for item in recent
    ]
    outputs[KNOW_ACTIVE_PATH.as_posix()] = dump_yaml(active)


def _replace_auto_section(existing: str, heading: str, body: str) -> str:
    section = f"{heading}\n\n{AUTO_START}\n{body.rstrip()}\n{AUTO_END}\n"
    if AUTO_START in existing and AUTO_END in existing:
        start = existing.index(AUTO_START)
        end = existing.index(AUTO_END, start) + len(AUTO_END)
        prefix = existing[:start].rstrip()
        suffix = existing[end:].lstrip("\n")
        replacement = f"{AUTO_START}\n{body.rstrip()}\n{AUTO_END}"
        combined = prefix + "\n" + replacement
        if suffix:
            combined += "\n\n" + suffix.rstrip()
        return combined.rstrip() + "\n"
    if existing.strip():
        return existing.rstrip() + "\n\n" + section
    return section


def _render_summary(session: int, ledger: list[dict[str, Any]], closed: bool) -> str:
    lines = [
        f"* Status transacional: {'encerrada' if closed else 'em andamento'}.",
        "* Esta seção é gerada apenas a partir dos resumos registrados por `turno.py`; não inventa fatos ausentes dos deltas.",
        "",
        "### Linha consolidada",
    ]
    if not ledger:
        lines.append("- Nenhuma transação consolidada.")
    for batch in ledger:
        lines.append(f"- **{batch['id']}** ({batch.get('tipo', 'cena')}):")
        for summary in batch.get("resumos", []):
            lines.append(f"  - {summary}")
    return "\n".join(lines)


def _format_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if value.get("titulo") and value.get("descricao"):
            return f"**{value['titulo']}** — {value['descricao']}"
        if value.get("descricao"):
            return str(value["descricao"])
        if value.get("texto"):
            return str(value["texto"])
    return f"`{json.dumps(value, ensure_ascii=False, sort_keys=True)}`"


def _render_consequences(ledger: list[dict[str, Any]]) -> str:
    values: list[Any] = []
    for batch in ledger:
        values.extend(batch.get("consequencias", []))
    if not values:
        return "Nenhuma consequência foi registrada explicitamente como delta `consequencia` no período transacional."
    lines = ["Consequências explicitamente registradas:"]
    lines.extend(f"- {_format_value(value)}" for value in values)
    return "\n".join(lines)


def _render_progression(ledger: list[dict[str, Any]]) -> str:
    values: list[Any] = []
    for batch in ledger:
        values.extend(batch.get("progressao", []))
    if not values:
        return "Nenhuma alteração explícita de progressão foi registrada nesta consolidação."
    lines = ["Registros explícitos de progressão:"]
    lines.extend(f"- {_format_value(value)}" for value in values)
    return "\n".join(lines)


def _session_artifacts(
    repo: Path,
    session: int,
    ledger: list[dict[str, Any]],
    before: dict[str, Any],
    after: dict[str, Any],
    kind: str,
    outputs: dict[str, bytes],
) -> None:
    session_dir = repo / "sessoes" / f"{session:03d}"
    closed = kind == "sessao"

    alterations_path = session_dir / "alteracoes-de-estado.yaml"
    if alterations_path.is_file():
        existing = load_yaml(alterations_path) or {}
        if isinstance(existing, dict) and existing.get("schema_alteracoes_transacionais") == 1:
            initial = existing.get("checkpoint_inicial") or before
            alteration_rel = alterations_path.relative_to(repo)
        else:
            initial = before
            alteration_rel = Path("sessoes") / f"{session:03d}" / "alteracoes-transacionais.yaml"
    else:
        initial = before
        alteration_rel = Path("sessoes") / f"{session:03d}" / "alteracoes-de-estado.yaml"

    alteration_doc = {
        "schema_alteracoes_transacionais": 1,
        "sessao": session,
        "status": "encerrada" if closed else "em_andamento",
        "fonte": f"sessoes/{session:03d}/{LEDGER_NAME}",
        "checkpoint_inicial": initial,
        "checkpoint_atual": after,
        "consolidacoes": [
            {
                "id": item.get("id"),
                "tipo": item.get("tipo"),
                "transacoes": item.get("transacoes", []),
                "deltas": item.get("deltas", 0),
                "arquivos_afetados": item.get("arquivos_afetados", []),
            }
            for item in ledger
        ],
    }
    outputs[alteration_rel.as_posix()] = dump_yaml(alteration_doc)

    summary_path = session_dir / "resumo.md"
    summary_existing = summary_path.read_text(encoding="utf-8") if summary_path.is_file() else f"# Resumo - Sessão {session:03d}\n"
    summary = _replace_auto_section(
        summary_existing,
        "## Consolidação transacional automática",
        _render_summary(session, ledger, closed),
    )
    outputs[summary_path.relative_to(repo).as_posix()] = summary.encode("utf-8")

    consequences_path = session_dir / "consequencias.md"
    consequences_existing = consequences_path.read_text(encoding="utf-8") if consequences_path.is_file() else f"# Consequências - Sessão {session:03d}\n"
    consequences = _replace_auto_section(
        consequences_existing,
        "## Consolidação transacional automática",
        _render_consequences(ledger),
    )
    outputs[consequences_path.relative_to(repo).as_posix()] = consequences.encode("utf-8")

    if any(item.get("progressao") for item in ledger):
        experience_path = session_dir / "experiencia.md"
        experience_existing = experience_path.read_text(encoding="utf-8") if experience_path.is_file() else f"# Experiência - Sessão {session:03d}\n"
        experience = _replace_auto_section(
            experience_existing,
            "## Consolidação transacional automática",
            _render_progression(ledger),
        )
        outputs[experience_path.relative_to(repo).as_posix()] = experience.encode("utf-8")


def _hidden_rolls_output(repo: Path, session: int, batch: str, records: list[dict[str, Any]]) -> tuple[str, bytes] | None:
    entries = [(record["id"], roll) for record in records for roll in record.get("rolagens_ocultas", [])]
    if not entries:
        return None
    rel = Path("narrador/sessoes") / f"{session:03d}" / "rolagens-ocultas.md"
    path = repo / rel
    existing = path.read_text(encoding="utf-8") if path.is_file() else f"# Rolagens ocultas — Sessão {session:03d}\n"
    marker = f"<!-- consolidacao:{batch} -->"
    if marker in existing:
        return rel.as_posix(), existing.encode("utf-8")
    lines = [marker, f"## Consolidação {batch}", ""]
    for txid, roll in entries:
        lines.append(f"- `{txid}` — {roll}")
    text = existing.rstrip() + "\n\n" + "\n".join(lines).rstrip() + "\n"
    return rel.as_posix(), text.encode("utf-8")


def _clock_documents(
    repo: Path,
    clock_deltas: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]],
    outputs: dict[str, bytes],
) -> None:
    if not clock_deltas:
        return
    index_rel = Path("narrador/relogios/index.yaml")
    index_abs = repo / index_rel
    index = load_yaml(index_abs) if index_abs.is_file() else {
        "schema_relogios": 1,
        "natureza": "reservado",
        "relogios": {},
    }
    mapping = index.setdefault("relogios", {})
    if not isinstance(mapping, dict):
        raise ConsolidationError("índice de relógios inválido")

    for clock_id, pairs in clock_deltas.items():
        rel = Path("narrador/relogios") / f"{clock_id}.yaml"
        absolute = repo / rel
        doc = load_yaml(absolute) if absolute.is_file() else {
            "schema_relogio": 1,
            "id": clock_id,
            "natureza": "reservado",
            "relogio": {},
            "eventos": [],
        }
        payload = doc.setdefault("relogio", {})
        events = doc.setdefault("eventos", [])
        if not isinstance(payload, dict) or not isinstance(events, list):
            raise ConsolidationError(f"relógio inválido: {clock_id}")
        for record, delta in pairs:
            if delta.get("op") == "registrar":
                events.append({"transacao": record["id"], "sessao": record["sessao"], "valor": copy.deepcopy(delta.get("valor"))})
            else:
                _apply(payload, delta)
        outputs[rel.as_posix()] = dump_yaml(doc)
        mapping[clock_id] = {"arquivo": rel.as_posix(), "sessao_ultima_atualizacao": pairs[-1][0]["sessao"]}
    index["quantidade"] = len(mapping)
    outputs[index_rel.as_posix()] = dump_yaml(index)


def build_plan(repo: Path, kind: str) -> dict[str, Any] | None:
    if kind not in {"cena", "sessao"}:
        raise ConsolidationError(f"tipo de consolidação inválido: {kind}")
    if (repo / JOURNAL_PATH).exists():
        raise ConsolidationError("há consolidação interrompida; execute recuperar antes de criar outro lote")

    transaction_errors = turno.check_transactions(repo)
    if transaction_errors:
        raise ConsolidationError("buffer transacional inconsistente: " + "; ".join(transaction_errors))

    session = current_session(repo)
    pending_all = transacoes.load_pending(repo)
    pending_session = transacoes.pending_for_session(pending_all, session)
    ledger = load_ledger(repo, session)
    done = consolidated_ids(ledger)
    stale = [record for record in pending_session if record["id"] in done]
    records = [record for record in pending_session if record["id"] not in done]
    if not records and not stale:
        return None

    estado = load_yaml(repo / STATE_PATH) or {}
    tempo = load_yaml(repo / TIME_PATH) or {}
    ficha = load_yaml(repo / SHEET_PATH) or {}
    rel_index = load_yaml(repo / REL_INDEX_PATH) or {}
    npc_index = load_yaml(repo / NPC_INDEX_PATH) or {}
    for name, value in (("estado", estado), ("tempo", tempo), ("ficha", ficha), ("índice de relações", rel_index), ("índice de NPCs", npc_index)):
        if not isinstance(value, dict):
            raise ConsolidationError(f"{name} inválido")

    before = snapshot(estado, tempo, ficha)
    touched_state: set[str] = set()
    touched_time: set[str] = set()
    touched_sheet: set[str] = set()
    changed_state = changed_time = changed_sheet = False

    relation_docs: dict[str, tuple[dict[str, Any], dict[str, Any], Path]] = {}
    npc_docs: dict[str, tuple[dict[str, Any], dict[str, Any], Path]] = {}
    relation_events: dict[str, list[dict[str, Any]]] = {}
    npc_events: dict[str, list[dict[str, Any]]] = {}
    knowledge_by_tx: dict[str, list[Any]] = {}
    consequences: list[Any] = []
    progression: list[Any] = []
    clock_deltas: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}

    for record in records:
        per_rel: dict[str, list[dict[str, Any]]] = {}
        per_npc: dict[str, list[dict[str, Any]]] = {}
        for delta in record.get("deltas", []):
            transacoes.validate_delta(delta)
            validate_visibility(delta)
            target = str(delta["alvo"])
            op = delta["op"]
            path = delta.get("caminho")

            if target == "estado":
                if op == "registrar":
                    raise ConsolidationError("alvo estado não aceita operação registrar")
                _apply(estado, delta)
                touched_state.add(str(path))
                changed_state = True
                continue
            if target == "tempo":
                if op == "registrar":
                    raise ConsolidationError("alvo tempo não aceita operação registrar")
                _apply(tempo, delta)
                touched_time.add(str(path))
                changed_time = True
                continue
            if target == "ficha":
                if op == "registrar":
                    raise ConsolidationError("alvo ficha não aceita operação registrar")
                _apply(ficha, delta)
                touched_sheet.add(str(path))
                changed_sheet = True
                continue
            if target == "progressao":
                if op == "registrar":
                    progression.append(copy.deepcopy(delta.get("valor")))
                else:
                    mapped_path = f"progressao.{path}"
                    _apply(ficha, delta, path=mapped_path)
                    touched_sheet.add(mapped_path)
                    changed_sheet = True
                continue
            if target.startswith("relacao:"):
                entity_id = target.split(":", 1)[1]
                if entity_id not in relation_docs:
                    relation_docs[entity_id] = _entity_doc(repo, rel_index, "relacoes", entity_id, "relacao")
                doc, _, _ = relation_docs[entity_id]
                payload = doc.setdefault("relacao", {})
                if not isinstance(payload, dict):
                    raise ConsolidationError(f"payload de relação inválido: {entity_id}")
                if op == "registrar":
                    raise ConsolidationError("relações devem usar set/inc/append/remove; histórico é gerado automaticamente")
                _apply(payload, delta)
                per_rel.setdefault(entity_id, []).append(copy.deepcopy(delta))
                continue
            if target.startswith("npc:"):
                entity_id = target.split(":", 1)[1]
                if entity_id not in npc_docs:
                    npc_docs[entity_id] = _entity_doc(repo, npc_index, "npcs", entity_id, "npc")
                doc, _, _ = npc_docs[entity_id]
                payload = doc.setdefault("npc", {})
                if not isinstance(payload, dict):
                    raise ConsolidationError(f"payload de NPC inválido: {entity_id}")
                if op == "registrar":
                    raise ConsolidationError("NPC deve usar set/inc/append/remove; histórico é gerado automaticamente")
                _apply(payload, delta)
                per_npc.setdefault(entity_id, []).append(copy.deepcopy(delta))
                continue
            if target == "conhecimento":
                if op != "registrar":
                    raise ConsolidationError("conhecimento aceita somente operação registrar")
                knowledge_by_tx.setdefault(record["id"], []).append(copy.deepcopy(delta.get("valor")))
                continue
            if target == "consequencia":
                if op != "registrar":
                    raise ConsolidationError("consequencia aceita somente operação registrar")
                consequences.append(copy.deepcopy(delta.get("valor")))
                continue
            if target.startswith("relogio:"):
                clock_id = target.split(":", 1)[1]
                clock_deltas.setdefault(clock_id, []).append((record, copy.deepcopy(delta)))
                continue
            raise ConsolidationError(f"alvo ainda não suportado pela consolidação: {target}")

        for entity_id, deltas in per_rel.items():
            relation_events.setdefault(entity_id, []).append(_history_event(record, deltas))
        for entity_id, deltas in per_npc.items():
            npc_events.setdefault(entity_id, []).append(_history_event(record, deltas))

    sync_mirrors(estado, tempo, ficha, touched_state, touched_time, touched_sheet)
    if touched_state or touched_time or touched_sheet:
        changed_state = changed_state or bool(touched_time & {pair[1] for pair in TIME_MIRRORS}) or bool(touched_sheet & {pair[1] for pair in SHEET_MIRRORS})
        changed_time = changed_time or bool(touched_state & {pair[0] for pair in TIME_MIRRORS})
        changed_sheet = changed_sheet or bool(touched_state & {pair[0] for pair in SHEET_MIRRORS})

    after = snapshot(estado, tempo, ficha)
    outputs: dict[str, bytes] = {}
    affected: set[str] = set()

    if changed_state:
        outputs[STATE_PATH.as_posix()] = dump_yaml(estado)
        affected.add(STATE_PATH.as_posix())
    if changed_time:
        outputs[TIME_PATH.as_posix()] = dump_yaml(tempo)
        affected.add(TIME_PATH.as_posix())
    if changed_sheet:
        outputs[SHEET_PATH.as_posix()] = dump_yaml(ficha)
        affected.add(SHEET_PATH.as_posix())

    for entity_id, (doc, entry, rel) in relation_docs.items():
        payload = doc.get("relacao") or {}
        raw = dump_yaml(doc)
        if len(raw) > MAX_ENTITY_FRAGMENT:
            raise ConsolidationError(f"fragmento de relação excederia {MAX_ENTITY_FRAGMENT} bytes: {rel}")
        history_rel = Path(entry.get("historico") or f"historico/relacoes/{entity_id}.yaml")
        history = _append_history(repo, history_rel, entity_id, "relacao", relation_events.get(entity_id, []))
        outputs[rel.as_posix()] = raw
        outputs[history_rel.as_posix()] = dump_yaml(history)
        _update_relation_entry(entry, payload, rel, history_rel, len(raw))
        affected.update({rel.as_posix(), history_rel.as_posix()})
    if relation_docs:
        mapping = rel_index.get("relacoes") or {}
        rel_index["quantidade"] = len(mapping)
        raw = dump_yaml(rel_index)
        if len(raw) > MAX_INDEX_BYTES:
            raise ConsolidationError("índice de relações cresceu além do limite operacional")
        outputs[REL_INDEX_PATH.as_posix()] = raw
        affected.add(REL_INDEX_PATH.as_posix())

    for entity_id, (doc, entry, rel) in npc_docs.items():
        payload = doc.get("npc") or {}
        raw = dump_yaml(doc)
        if len(raw) > MAX_ENTITY_FRAGMENT:
            raise ConsolidationError(f"fragmento de NPC excederia {MAX_ENTITY_FRAGMENT} bytes: {rel}")
        history_rel = Path(entry.get("historico") or f"historico/npcs/{entity_id}.yaml")
        history = _append_history(repo, history_rel, entity_id, "npc", npc_events.get(entity_id, []))
        outputs[rel.as_posix()] = raw
        outputs[history_rel.as_posix()] = dump_yaml(history)
        _update_npc_entry(entry, payload, rel, history_rel, len(raw))
        affected.update({rel.as_posix(), history_rel.as_posix()})
    if npc_docs:
        mapping = npc_index.get("npcs") or {}
        npc_index["quantidade"] = len(mapping)
        raw = dump_yaml(npc_index)
        if len(raw) > MAX_INDEX_BYTES:
            raise ConsolidationError("índice de NPCs cresceu além do limite operacional")
        outputs[NPC_INDEX_PATH.as_posix()] = raw
        affected.add(NPC_INDEX_PATH.as_posix())

    _build_incremental_knowledge(repo, session, records, knowledge_by_tx, outputs)
    if knowledge_by_tx:
        affected.update(path for path in outputs if path.startswith("personagens/jogador/conhecimento/"))

    _clock_documents(repo, clock_deltas, outputs)
    if clock_deltas:
        affected.update(path for path in outputs if path.startswith("narrador/relogios/"))

    new_batch: dict[str, Any] | None = None
    combined_ledger = list(ledger)
    if records:
        batch = batch_id(session, kind, records)
        new_batch = {
            "versao": SCHEMA_VERSION,
            "id": batch,
            "sessao": session,
            "tipo": kind,
            "transacoes": [record["id"] for record in records],
            "quantidade": len(records),
            "deltas": sum(len(record.get("deltas", [])) for record in records),
            "resumos": [record.get("resumo", "") for record in records],
            "consequencias": consequences,
            "progressao": progression,
            "rolagens_ocultas": sum(len(record.get("rolagens_ocultas", [])) for record in records),
            "checkpoint_antes": before,
            "checkpoint_depois": after,
            "arquivos_afetados": sorted(affected),
        }
        combined_ledger.append(new_batch)
        ledger_rel = Path("sessoes") / f"{session:03d}" / LEDGER_NAME
        outputs[ledger_rel.as_posix()] = jsonl_text(combined_ledger)
        affected.add(ledger_rel.as_posix())

        hidden = _hidden_rolls_output(repo, session, batch, records)
        if hidden:
            outputs[hidden[0]] = hidden[1]
            affected.add(hidden[0])

    _session_artifacts(repo, session, combined_ledger, before, after, kind, outputs)
    affected.update(path for path in outputs if path.startswith(f"sessoes/{session:03d}/"))

    # Runtime novo é calculado sobre os documentos em memória antes de qualquer escrita.
    runtime_mod = _runtime_module()
    new_context, new_scene = runtime_mod.build_runtime_from_documents(estado, tempo, ficha)
    outputs["runtime/contexto.yaml"] = runtime_mod.dump_yaml(new_context).encode("utf-8")
    outputs["runtime/cena.yaml"] = runtime_mod.dump_yaml(new_scene).encode("utf-8")

    processed_ids = {record["id"] for record in records + stale}
    remaining = [record for record in pending_all if record["id"] not in processed_ids]
    outputs[transacoes.PENDING_PATH.as_posix()] = jsonl_text(remaining)

    if new_batch is not None:
        # Atualiza a lista depois que todos os caminhos do lote são conhecidos.
        new_batch["arquivos_afetados"] = sorted(affected)
        ledger_rel = Path("sessoes") / f"{session:03d}" / LEDGER_NAME
        outputs[ledger_rel.as_posix()] = jsonl_text(combined_ledger)
        _session_artifacts(repo, session, combined_ledger, before, after, kind, outputs)

    return {
        "versao": SCHEMA_VERSION,
        "sessao": session,
        "tipo": kind,
        "batch": new_batch["id"] if new_batch else None,
        "transacoes": [record["id"] for record in records],
        "stale": [record["id"] for record in stale],
        "outputs": outputs,
        "checkpoint_antes": before,
        "checkpoint_depois": after,
    }


def stage_plan(repo: Path, plan: dict[str, Any]) -> dict[str, Any]:
    stage_root = repo / STAGE_DIR
    if stage_root.exists():
        shutil.rmtree(stage_root)
    stage_root.mkdir(parents=True, exist_ok=True)

    files: list[dict[str, Any]] = []
    outputs: dict[str, bytes] = plan["outputs"]
    # Pending é instalado por último; até lá o journal bloqueia leituras e novos turnos.
    ordered = sorted(outputs, key=lambda rel: (rel == transacoes.PENDING_PATH.as_posix(), rel))
    for rel in ordered:
        data = outputs[rel]
        stage_path = stage_root / rel
        _atomic_write_bytes(stage_path, data)
        destination = repo / rel
        files.append({
            "caminho": rel,
            "stage": (STAGE_DIR / rel).as_posix(),
            "sha_antes": sha256_path(destination),
            "sha_depois": sha256_bytes(data),
        })

    journal = {
        "versao": SCHEMA_VERSION,
        "sessao": plan["sessao"],
        "tipo": plan["tipo"],
        "batch": plan.get("batch"),
        "transacoes": plan.get("transacoes", []),
        "stale": plan.get("stale", []),
        "arquivos": files,
    }
    _atomic_write_json(repo / JOURNAL_PATH, journal)
    return journal


def install_staged(repo: Path, journal: dict[str, Any], *, fail_after: int | None = None) -> dict[str, Any]:
    installed = 0
    for item in journal.get("arquivos", []):
        rel = str(item["caminho"])
        stage = repo / str(item["stage"])
        destination = repo / rel
        if not stage.is_file():
            raise ConsolidationError(f"arquivo staged desapareceu: {item['stage']}")
        staged_data = stage.read_bytes()
        if sha256_bytes(staged_data) != item.get("sha_depois"):
            raise ConsolidationError(f"hash do staging divergiu: {item['stage']}")
        current = sha256_path(destination)
        allowed = {item.get("sha_antes"), item.get("sha_depois")}
        if current not in allowed:
            raise ConsolidationError(
                f"{rel} mudou externamente durante a consolidação; recusando sobrescrever (hash {current})"
            )
        if current != item.get("sha_depois"):
            _atomic_write_bytes(destination, staged_data)
        installed += 1
        if fail_after is not None and installed >= fail_after:
            raise ConsolidationError("falha simulada após escrita staged")

    for item in journal.get("arquivos", []):
        destination = repo / str(item["caminho"])
        if sha256_path(destination) != item.get("sha_depois"):
            raise ConsolidationError(f"verificação pós-instalação falhou: {item['caminho']}")

    (repo / JOURNAL_PATH).unlink(missing_ok=True)
    shutil.rmtree(repo / STAGE_DIR, ignore_errors=True)
    return {
        "sessao": journal.get("sessao"),
        "tipo": journal.get("tipo"),
        "batch": journal.get("batch"),
        "transacoes": journal.get("transacoes", []),
        "stale": journal.get("stale", []),
        "arquivos": len(journal.get("arquivos", [])),
    }


def resume_consolidation(repo: Path, *, fail_after: int | None = None) -> dict[str, Any] | None:
    journal_path = repo / JOURNAL_PATH
    if not journal_path.is_file():
        return None
    try:
        journal = json.loads(journal_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConsolidationError(f"journal de consolidação corrompido: {exc}") from exc
    if not isinstance(journal, dict) or journal.get("versao") != SCHEMA_VERSION:
        raise ConsolidationError("journal de consolidação possui schema inesperado")
    return install_staged(repo, journal, fail_after=fail_after)


def consolidate(repo: Path, kind: str, *, fail_after: int | None = None) -> dict[str, Any]:
    recovered = resume_consolidation(repo)
    if recovered is not None:
        # A operação interrompida já consolidou exatamente o lote preparado.
        return {"recuperada": True, **recovered}
    plan = build_plan(repo, kind)
    if plan is None:
        return {"sessao": current_session(repo), "tipo": kind, "sem_pendencias": True}
    journal = stage_plan(repo, plan)
    result = install_staged(repo, journal, fail_after=fail_after)
    return {"recuperada": False, **result}


def check(repo: Path) -> list[str]:
    errors: list[str] = []
    if (repo / JOURNAL_PATH).exists():
        errors.append(f"consolidação interrompida: {JOURNAL_PATH}; execute ferramentas/consolidar.py recuperar")
    errors.extend(turno.check_transactions(repo))

    pending_ids: set[str] = set()
    try:
        for record in transacoes.load_pending(repo):
            if record["id"] in pending_ids:
                errors.append(f"id pendente duplicado: {record['id']}")
            pending_ids.add(record["id"])
    except transacoes.TransactionError as exc:
        errors.append(str(exc))

    consolidated: set[str] = set()
    batches: set[str] = set()
    sessions = repo / "sessoes"
    if sessions.exists():
        for session_dir in sessions.iterdir():
            if not session_dir.is_dir() or not session_dir.name.isdigit():
                continue
            path = session_dir / LEDGER_NAME
            if not path.is_file():
                continue
            try:
                ledger = read_jsonl(path)
            except ConsolidationError as exc:
                errors.append(str(exc))
                continue
            for batch in ledger:
                bid = batch.get("id")
                if bid in batches:
                    errors.append(f"batch de consolidação duplicado: {bid}")
                batches.add(str(bid))
                for txid in batch.get("transacoes", []):
                    if txid in consolidated:
                        errors.append(f"transação aparece em mais de uma consolidação: {txid}")
                    consolidated.add(str(txid))
    overlap = pending_ids & consolidated
    for txid in sorted(overlap):
        errors.append(f"transação está simultaneamente pendente e consolidada: {txid}")

    # Índices incrementais, quando existirem, precisam apontar para arquivos reais.
    if (repo / KNOW_INDEX_PATH).is_file():
        index = load_yaml(repo / KNOW_INDEX_PATH) or {}
        incrementals = index.get("incrementais", {}) if isinstance(index, dict) else {}
        if isinstance(incrementals, dict):
            for session, entry in incrementals.items():
                rel = entry.get("index") if isinstance(entry, dict) else None
                if not isinstance(rel, str) or not (repo / rel).is_file():
                    errors.append(f"índice incremental de conhecimento ausente para sessão {session}: {rel}")
    return errors


def status(repo: Path) -> dict[str, Any]:
    session = current_session(repo)
    pending = transacoes.pending_for_session(transacoes.load_pending(repo), session)
    ledger = load_ledger(repo, session)
    journal = None
    if (repo / JOURNAL_PATH).is_file():
        try:
            journal = json.loads((repo / JOURNAL_PATH).read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            journal = {"corrompido": True}
    return {
        "sessao": session,
        "eventos_pendentes": len(pending),
        "batches_consolidados": len(ledger),
        "transacoes_consolidadas": len(consolidated_ids(ledger)),
        "consolidacao_em_andamento": journal,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("cena", help="consolida o buffer atual como checkpoint de cena")
    sub.add_parser("sessao", help="consolida o buffer e marca artefatos da sessão como encerrados")
    sub.add_parser("recuperar", help="retoma uma instalação interrompida a partir do staging")
    sub.add_parser("status", help="mostra metadados de pendências e consolidações")
    sub.add_parser("check", help="valida journal, ledgers, buffer e índices incrementais")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo = args.repo.resolve()
    try:
        if args.comando in {"cena", "sessao"}:
            result = consolidate(repo, args.comando)
            if result.get("sem_pendencias"):
                print(f"OK — sessão {result['sessao']:03d} sem eventos pendentes para consolidar.")
            elif result.get("recuperada"):
                print(
                    f"OK — consolidação interrompida recuperada: {result.get('batch')} | "
                    f"transações={len(result.get('transacoes', []))} | arquivos={result.get('arquivos')}"
                )
            else:
                print(
                    f"OK — consolidação {result.get('batch')} concluída | "
                    f"transações={len(result.get('transacoes', []))} | arquivos={result.get('arquivos')}"
                )
            return 0
        if args.comando == "recuperar":
            result = resume_consolidation(repo)
            if result is None:
                print("OK — não há consolidação interrompida.")
            else:
                print(f"OK — consolidação recuperada: {result.get('batch')}.")
            return 0
        if args.comando == "status":
            print(json.dumps(status(repo), ensure_ascii=False, indent=2))
            return 0
        if args.comando == "check":
            errors = check(repo)
            if errors:
                print("FALHA DE CONSOLIDAÇÃO")
                for error in errors:
                    print(f"- {error}")
                return 1
            print("OK — consolidação, ledgers e buffer transacional estão íntegros.")
            return 0
        raise ConsolidationError(f"comando desconhecido: {args.comando}")
    except (OSError, yaml.YAMLError, transacoes.TransactionError, ConsolidationError, ValueError) as exc:
        print(f"FALHA DE CONSOLIDAÇÃO — {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
