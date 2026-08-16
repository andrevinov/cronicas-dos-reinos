#!/usr/bin/env python3
"""Memória compacta de sessões e política de transcrições frias.

A transcrição continua sendo o registro completo e o destino append-only da
narração, mas deixa de ser uma fonte de leitura normal. Este módulo mantém:

- `sessoes/index.yaml`: índice barato de sessões e artefatos compactos;
- `sessoes/NNN/handoff.yaml`: checkpoint pequeno para retomada;
- validações que impedem novas sessões de copiar trechos da anterior.

O módulo não interpreta transcrições para produzir fatos. Handoffs novos são
construídos somente de runtime/cena e dos resumos explícitos do ledger de
consolidação.

Durante uma sessão ativa, o índice pertence ao último checkpoint. A transcrição
pode crescer depois dele sem reindexação enquanto houver transações pendentes
válidas; exigir atualização do índice a cada turno reintroduziria uma terceira
escrita no caminho narrativo normal.
"""
from __future__ import annotations

import argparse
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    import yaml
except ImportError as exc:
    raise SystemExit(
        "PyYAML não encontrado. Instale com: python3 -m pip install -r requirements-dev.txt"
    ) from exc

INDEX_SCHEMA = 1
HANDOFF_SCHEMA = 1
INDEX_PATH = Path("sessoes/index.yaml")
HANDOFF_NAME = "handoff.yaml"
TRANSCRIPT_NAME = "transcricao.md"
PENDING_PATH = Path("runtime/eventos-pendentes.jsonl")
MAX_HANDOFF_BYTES = 8 * 1024
MAX_INDEX_BYTES = 64 * 1024
RECENT_EVENT_LIMIT = 8
LEGACY_TRANSCRIPT_COPY_CUTOFF = 3
COMPACT_ARTIFACTS = (
    "handoff.yaml",
    "resumo.md",
    "alteracoes-de-estado.yaml",
    "alteracoes-transacionais.yaml",
    "consequencias.md",
    "experiencia.md",
    "correcoes-de-continuidade.md",
    "consolidacoes.jsonl",
)
COPY_MARKERS = (
    "último trecho da sessão",
    "ultimo trecho da sessao",
    "foi copiado para cá como ponto de retomada",
    "foi copiado para ca como ponto de retomada",
)


class SessionMemoryError(RuntimeError):
    pass


def load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def dump_yaml(value: Any) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=110)


def dump_yaml_bytes(value: Any) -> bytes:
    return dump_yaml(value).encode("utf-8")


def truncate(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def compact(value: Any, *, depth: int = 3, list_limit: int = 6, string_limit: int = 700) -> Any:
    if depth <= 0:
        if isinstance(value, (dict, list)):
            return "[… omitido …]"
        return truncate(value, string_limit)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 20:
                out["_omitidos"] = len(value) - index
                break
            out[str(key)] = compact(
                item,
                depth=depth - 1,
                list_limit=list_limit,
                string_limit=string_limit,
            )
        return out
    if isinstance(value, list):
        items = [
            compact(item, depth=depth - 1, list_limit=list_limit, string_limit=string_limit)
            for item in value[:list_limit]
        ]
        if len(value) > list_limit:
            items.append(f"… {len(value) - list_limit} item(ns) omitido(s)")
        return items
    if isinstance(value, str):
        return truncate(value, string_limit)
    return value


def current_session(repo: Path) -> int:
    runtime = load_yaml(repo / "runtime/contexto.yaml") or {}
    session = ((runtime.get("sessao") or {}).get("numero")) if isinstance(runtime, dict) else None
    if not isinstance(session, int) or session < 1:
        raise SessionMemoryError("runtime/contexto.yaml não define sessão atual válida")
    return session


def handoff_rel(session: int) -> Path:
    return Path("sessoes") / f"{session:03d}" / HANDOFF_NAME


def transcript_rel(session: int) -> Path:
    return Path("sessoes") / f"{session:03d}" / TRANSCRIPT_NAME


def _session_numbers(repo: Path) -> list[int]:
    root = repo / "sessoes"
    if not root.exists():
        return []
    result: list[int] = []
    for path in root.iterdir():
        if path.is_dir() and path.name.isdigit():
            result.append(int(path.name))
    return sorted(result)


def _virtual_data(
    repo: Path,
    rel: Path,
    virtual_files: Mapping[str, bytes] | None,
) -> bytes | None:
    key = rel.as_posix()
    if virtual_files and key in virtual_files:
        return virtual_files[key]
    path = repo / rel
    if path.is_file():
        return path.read_bytes()
    return None


def _artifact_entry(
    repo: Path,
    rel: Path,
    virtual_files: Mapping[str, bytes] | None,
) -> dict[str, Any] | None:
    data = _virtual_data(repo, rel, virtual_files)
    if data is None:
        return None
    return {"arquivo": rel.as_posix(), "bytes": len(data)}


def build_index(
    repo: Path,
    *,
    active_session: int | None = None,
    virtual_files: Mapping[str, bytes] | None = None,
) -> dict[str, Any]:
    active = active_session if active_session is not None else current_session(repo)
    numbers = _session_numbers(repo)
    if active not in numbers:
        numbers.append(active)
        numbers.sort()

    sessions: dict[str, Any] = {}
    total_transcript_bytes = 0
    for number in numbers:
        base = Path("sessoes") / f"{number:03d}"
        compactos: list[dict[str, Any]] = []
        for name in COMPACT_ARTIFACTS:
            item = _artifact_entry(repo, base / name, virtual_files)
            if item is not None:
                compactos.append(item)

        transcript = _artifact_entry(repo, base / TRANSCRIPT_NAME, virtual_files)
        transcript_bytes = int((transcript or {}).get("bytes") or 0)
        total_transcript_bytes += transcript_bytes
        hrel = handoff_rel(number)
        handoff_exists = _virtual_data(repo, hrel, virtual_files) is not None

        preferred: list[str] = []
        if handoff_exists:
            preferred.append(hrel.as_posix())
        for name in (
            "resumo.md",
            "alteracoes-de-estado.yaml",
            "alteracoes-transacionais.yaml",
            "consequencias.md",
            "experiencia.md",
        ):
            rel = base / name
            if _virtual_data(repo, rel, virtual_files) is not None:
                preferred.append(rel.as_posix())

        sessions[f"{number:03d}"] = {
            "natureza": "atual" if number == active else "historica",
            "handoff": hrel.as_posix() if handoff_exists else None,
            "compactos": compactos,
            "ordem_de_leitura": preferred,
            "transcricao": {
                "arquivo": (base / TRANSCRIPT_NAME).as_posix(),
                "bytes": transcript_bytes,
                "classe": "append_only_frio_para_leitura" if number == active else "arquivo_frio",
                "escalada": "somente busca histórica explícita com transcrições",
            },
        }

    result = {
        "schema_sessoes": INDEX_SCHEMA,
        "natureza": "indice_de_memoria_compacta",
        "sessao_atual": active,
        "politica": {
            "retomada": "handoff + runtime + eventos pendentes",
            "historico": "handoff/resumo/alteracoes antes de transcricao",
            "transcricoes": "frias para leitura; nunca copiar para sessão nova",
        },
        "totais": {
            "sessoes": len(sessions),
            "bytes_transcricoes": total_transcript_bytes,
        },
        "sessoes": sessions,
    }
    raw = dump_yaml_bytes(result)
    if len(raw) > MAX_INDEX_BYTES:
        raise SessionMemoryError(
            f"índice de sessões excedeu {MAX_INDEX_BYTES} bytes; precisa ser paginado/fragmentado"
        )
    return result


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SessionMemoryError(f"JSONL inválido em {path}:{number}: {exc}") from exc
        if isinstance(value, dict):
            records.append(value)
    return records


def _live_transcript_drift_allowed(repo: Path, actual: Any, expected: Any) -> bool:
    """Aceita só a defasagem de bytes causada por turnos após o checkpoint.

    O índice continua representando o último checkpoint. Enquanto a sessão atual
    tiver eventos pendentes, a única divergência tolerável é a transcrição ativa ter
    crescido por append (e, consequentemente, o total de bytes de transcrições).
    Qualquer outro campo divergente continua falhando.
    """
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    active = current_session(repo)
    pending = [
        record
        for record in read_jsonl(repo / PENDING_PATH)
        if record.get("sessao") == active
    ]
    if not pending:
        return False

    key = f"{active:03d}"
    actual_entry = ((actual.get("sessoes") or {}).get(key) or {})
    expected_entry = ((expected.get("sessoes") or {}).get(key) or {})
    actual_bytes = (((actual_entry.get("transcricao") or {}).get("bytes")))
    expected_bytes = (((expected_entry.get("transcricao") or {}).get("bytes")))
    actual_total = ((actual.get("totais") or {}).get("bytes_transcricoes"))
    expected_total = ((expected.get("totais") or {}).get("bytes_transcricoes"))
    if not all(isinstance(value, int) for value in (actual_bytes, expected_bytes, actual_total, expected_total)):
        return False
    if expected_bytes < actual_bytes:
        return False
    if expected_total - actual_total != expected_bytes - actual_bytes:
        return False

    normalized = deepcopy(expected)
    normalized["sessoes"][key]["transcricao"]["bytes"] = actual_bytes
    normalized["totais"]["bytes_transcricoes"] = actual_total
    return normalized == actual


def recent_ledger_events(ledger: Iterable[dict[str, Any]], limit: int = RECENT_EVENT_LIMIT) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for batch in ledger:
        txids = list(batch.get("transacoes") or [])
        summaries = list(batch.get("resumos") or [])
        for index, summary in enumerate(summaries):
            events.append(
                {
                    "batch": batch.get("id"),
                    "transacao": txids[index] if index < len(txids) else None,
                    "resumo": truncate(summary, 420),
                }
            )
    return events[-limit:]


def build_handoff(
    repo: Path,
    *,
    session: int,
    kind: str,
    context: dict[str, Any],
    scene: dict[str, Any],
    ledger: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    context_session = ((context.get("sessao") or {}).get("numero")) if isinstance(context, dict) else None
    if context_session != session:
        raise SessionMemoryError(
            f"runtime usado no handoff aponta para sessão {context_session}, esperado {session}"
        )
    if kind not in {"bootstrap", "cena", "sessao"}:
        raise SessionMemoryError(f"tipo de handoff inválido: {kind}")

    result = {
        "schema_handoff": HANDOFF_SCHEMA,
        "natureza": "memoria_compacta_de_retomada",
        "sessao": session,
        "checkpoint": {
            "tipo": kind,
            "estado": "sessao_encerrada" if kind == "sessao" else "retomavel",
            "modo": ((context.get("sessao") or {}).get("modo_de_cena")),
            "personagem": compact(context.get("personagem") or {}, depth=3, list_limit=5, string_limit=300),
            "recursos": compact(context.get("recursos") or {}, depth=3, list_limit=6, string_limit=300),
            "tempo": compact(context.get("tempo") or {}, depth=3, list_limit=6, string_limit=500),
            "localizacao": compact(context.get("localizacao") or {}, depth=3, list_limit=8, string_limit=500),
        },
        "continuidade": {
            "resumo_imediato": truncate(scene.get("resumo_imediato"), 1800),
            "prazos_e_alertas": truncate(scene.get("prazos_e_alertas"), 1400),
        },
        "eventos_recentes": recent_ledger_events(ledger),
        "fontes": {
            "estado": "estado/estado-atual.yaml",
            "tempo": "estado/tempo.yaml",
            "ficha": "personagens/jogador/ficha.yaml",
            "transcricao_fria": transcript_rel(session).as_posix(),
        },
        "politica": {
            "retomada_normal": "usar este handoff, runtime e eventos pendentes",
            "transcricao": "somente se memória compacta e busca histórica forem insuficientes",
        },
    }

    raw = dump_yaml_bytes(result)
    if len(raw) > MAX_HANDOFF_BYTES:
        result["eventos_recentes"] = result["eventos_recentes"][-4:]
        result["continuidade"]["resumo_imediato"] = truncate(
            result["continuidade"]["resumo_imediato"], 1100
        )
        result["continuidade"]["prazos_e_alertas"] = truncate(
            result["continuidade"]["prazos_e_alertas"], 850
        )
        raw = dump_yaml_bytes(result)
    if len(raw) > MAX_HANDOFF_BYTES:
        raise SessionMemoryError(
            f"handoff da sessão {session:03d} excedeu {MAX_HANDOFF_BYTES} bytes"
        )
    return result


def validate_handoff(data: Any, *, expected_session: int | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["handoff não é mapeamento"]
    if data.get("schema_handoff") != HANDOFF_SCHEMA:
        errors.append(f"schema_handoff inesperado: {data.get('schema_handoff')}")
    session = data.get("sessao")
    if not isinstance(session, int) or session < 1:
        errors.append("handoff não define sessão inteira positiva")
    if expected_session is not None and session != expected_session:
        errors.append(f"handoff aponta para sessão {session}, esperado {expected_session}")
    text = dump_yaml(data)
    if "**Jogador**" in text or "**Narrador**" in text:
        errors.append("handoff contém bloco de transcrição; deve guardar apenas memória compacta")
    if len(text.encode("utf-8")) > MAX_HANDOFF_BYTES:
        errors.append(f"handoff excede {MAX_HANDOFF_BYTES} bytes")
    return errors


def bootstrap_current(repo: Path) -> tuple[Path, dict[str, Any]]:
    session = current_session(repo)
    context = load_yaml(repo / "runtime/contexto.yaml") or {}
    scene = load_yaml(repo / "runtime/cena.yaml") or {}
    ledger = read_jsonl(repo / "sessoes" / f"{session:03d}" / "consolidacoes.jsonl")
    handoff = build_handoff(
        repo,
        session=session,
        kind="bootstrap",
        context=context,
        scene=scene,
        ledger=ledger,
    )
    path = repo / handoff_rel(session)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml(handoff), encoding="utf-8")
    write_index(repo)
    return path, handoff


def write_index(repo: Path) -> dict[str, Any]:
    data = build_index(repo)
    path = repo / INDEX_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_yaml(data), encoding="utf-8")
    return data


def _safe_read_text(path: Path, limit: int) -> str | None:
    if not path.is_file():
        return None
    return truncate(path.read_text(encoding="utf-8"), limit)


def session_snapshot(repo: Path, session: int) -> tuple[dict[str, Any], list[str]]:
    if session < 1:
        raise SessionMemoryError("sessão precisa ser positiva")
    index = load_yaml(repo / INDEX_PATH) if (repo / INDEX_PATH).is_file() else build_index(repo)
    entry = ((index.get("sessoes") or {}).get(f"{session:03d}")) if isinstance(index, dict) else None
    if not isinstance(entry, dict):
        return {"encontrado": False, "sessao": session}, [INDEX_PATH.as_posix()]

    sources = [INDEX_PATH.as_posix()]
    hrel = entry.get("handoff")
    if isinstance(hrel, str) and (repo / hrel).is_file():
        handoff = load_yaml(repo / hrel) or {}
        sources.append(hrel)
        return {
            "encontrado": True,
            "sessao": session,
            "indice": entry,
            "handoff": handoff,
            "transcricao_lida": False,
        }, sources

    base = repo / "sessoes" / f"{session:03d}"
    fallback: dict[str, Any] = {}
    summary = _safe_read_text(base / "resumo.md", 4200)
    if summary:
        fallback["resumo"] = summary
        sources.append((Path("sessoes") / f"{session:03d}" / "resumo.md").as_posix())
    for name in ("alteracoes-de-estado.yaml", "alteracoes-transacionais.yaml"):
        path = base / name
        if path.is_file():
            fallback["alteracoes"] = compact(load_yaml(path), depth=3, list_limit=6, string_limit=500)
            sources.append((Path("sessoes") / f"{session:03d}" / name).as_posix())
            break
    return {
        "encontrado": True,
        "sessao": session,
        "indice": entry,
        "fallback_compacto": fallback,
        "aviso": "handoff ausente; transcrição permaneceu fria e não foi aberta",
        "transcricao_lida": False,
    }, sources


def resume_view(repo: Path) -> tuple[dict[str, Any], list[str]]:
    context = load_yaml(repo / "runtime/contexto.yaml") or {}
    scene = load_yaml(repo / "runtime/cena.yaml") or {}
    session = ((context.get("sessao") or {}).get("numero")) if isinstance(context, dict) else None
    if not isinstance(session, int):
        raise SessionMemoryError("runtime sem sessão válida")

    sources = ["runtime/contexto.yaml", "runtime/cena.yaml"]
    handoff: dict[str, Any] | None = None
    hrel = handoff_rel(session)
    if (repo / hrel).is_file():
        raw = load_yaml(repo / hrel) or {}
        if isinstance(raw, dict):
            handoff = {
                "checkpoint": raw.get("checkpoint"),
                "continuidade": raw.get("continuidade"),
                "eventos_recentes": raw.get("eventos_recentes", []),
            }
            sources.append(hrel.as_posix())
    if (repo / INDEX_PATH).is_file():
        sources.append(INDEX_PATH.as_posix())

    return {
        "sessao": session,
        "contexto": context,
        "cena": scene,
        "memoria_consolidada": handoff,
        "transcricao": {
            "arquivo": transcript_rel(session).as_posix(),
            "classe": "fria_para_leitura",
            "orientacao": "não abrir para retomada normal",
        },
    }, sources


def check(repo: Path) -> list[str]:
    errors: list[str] = []
    path = repo / INDEX_PATH
    if not path.is_file():
        errors.append(f"índice de sessões ausente: {INDEX_PATH}")
    else:
        try:
            actual = load_yaml(path)
            expected = build_index(repo)
            if actual != expected and not _live_transcript_drift_allowed(repo, actual, expected):
                errors.append("sessoes/index.yaml está desatualizado fora da defasagem transacional permitida")
            if path.stat().st_size > MAX_INDEX_BYTES:
                errors.append(f"sessoes/index.yaml excede {MAX_INDEX_BYTES} bytes")
        except (OSError, yaml.YAMLError, SessionMemoryError) as exc:
            errors.append(f"índice de sessões inválido: {exc}")

    for session in _session_numbers(repo):
        hpath = repo / handoff_rel(session)
        if hpath.is_file():
            try:
                errors.extend(
                    f"sessão {session:03d}: {error}"
                    for error in validate_handoff(load_yaml(hpath), expected_session=session)
                )
            except (OSError, yaml.YAMLError) as exc:
                errors.append(f"handoff inválido da sessão {session:03d}: {exc}")

        # Sessões antigas já contêm decisões de arquivo que não devem ser reescritas.
        # O gate vale para toda sessão criada depois da implantação da Etapa 9.
        if session <= LEGACY_TRANSCRIPT_COPY_CUTOFF:
            continue
        transcript = repo / transcript_rel(session)
        if transcript.is_file():
            prefix = transcript.read_text(encoding="utf-8")[:24000].lower()
            for marker in COPY_MARKERS:
                if marker in prefix:
                    errors.append(
                        f"sessão {session:03d} copia trecho de sessão anterior; usar handoff/contexto.py retomada"
                    )
                    break
    return errors


def status(repo: Path) -> dict[str, Any]:
    index = build_index(repo)
    active = current_session(repo)
    entry = (index.get("sessoes") or {}).get(f"{active:03d}") or {}
    return {
        "sessao_atual": active,
        "sessoes": (index.get("totais") or {}).get("sessoes"),
        "bytes_transcricoes_frias": (index.get("totais") or {}).get("bytes_transcricoes"),
        "handoff_atual": entry.get("handoff"),
        "transcricao_atual": (entry.get("transcricao") or {}).get("arquivo"),
        "politica": "transcrições são append-only, mas frias para leitura",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    sub = parser.add_subparsers(dest="comando", required=True)
    sub.add_parser("bootstrap-atual", help="cria handoff derivado da sessão corrente e reindexa")
    sub.add_parser("reindexar", help="regenera sessoes/index.yaml sem ler transcrições")
    sub.add_parser("check", help="valida índice, handoffs e política de arquivos frios")
    sub.add_parser("status", help="mostra metadados da memória de sessões")
    show = sub.add_parser("sessao", help="mostra memória compacta de uma sessão sem abrir a transcrição")
    show.add_argument("numero", type=int)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo = args.repo.resolve()
    try:
        if args.comando == "bootstrap-atual":
            path, _ = bootstrap_current(repo)
            print(f"OK — handoff atual criado em {path.relative_to(repo)} e índice regenerado.")
            return 0
        if args.comando == "reindexar":
            data = write_index(repo)
            print(
                f"OK — índice de sessões regenerado: {data['totais']['sessoes']} sessão(ões), "
                f"{data['totais']['bytes_transcricoes']} bytes de transcrições frias."
            )
            return 0
        if args.comando == "check":
            errors = check(repo)
            if errors:
                print("FALHA NA MEMÓRIA DE SESSÕES")
                for error in errors:
                    print(f"- {error}")
                return 1
            print("OK — índice, handoffs e política de transcrições frias estão íntegros.")
            return 0
        if args.comando == "status":
            print(json.dumps(status(repo), ensure_ascii=False, indent=2))
            return 0
        if args.comando == "sessao":
            data, sources = session_snapshot(repo, args.numero)
            print(dump_yaml({"fontes": sources, "resultado": data}), end="")
            return 0
        raise SessionMemoryError(f"comando desconhecido: {args.comando}")
    except (OSError, yaml.YAMLError, SessionMemoryError, ValueError) as exc:
        print(f"FALHA NA MEMÓRIA DE SESSÕES — {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
