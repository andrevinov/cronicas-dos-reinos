#!/usr/bin/env python3
"""Integrador temporário da Etapa 9; falha se a base não for a esperada."""
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    if old not in s:
        raise SystemExit(f"Padrão não encontrado em {path}: {old[:140]!r}")
    p.write_text(s.replace(old, new, 1), encoding="utf-8")


def replace_after(path: str, anchor: str, old: str, new: str) -> None:
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    start = s.find(anchor)
    if start < 0:
        raise SystemExit(f"Âncora não encontrada em {path}: {anchor!r}")
    pos = s.find(old, start)
    if pos < 0:
        raise SystemExit(f"Padrão após âncora não encontrado em {path}: {old[:140]!r}")
    s = s[:pos] + new + s[pos + len(old):]
    p.write_text(s, encoding="utf-8")


CORE = "ferramentas/contexto_core.py"
replace_once(CORE, "\n\nDEFAULT_MAX_BYTES = 8 * 1024", "\n\nimport sessoes as memoria_sessoes\n\nDEFAULT_MAX_BYTES = 8 * 1024")
replace_once(
    CORE,
    "def iter_search_files(repo: Path, *, reserved: bool, historical: bool) -> Iterable[Path]:",
    "def iter_search_files(\n    repo: Path, *, reserved: bool, historical: bool, transcripts: bool = False\n) -> Iterable[Path]:",
)
replace_after(
    CORE,
    "sessions = repo / \"sessoes\"",
    '            for name in ("resumo.md", "alteracoes-de-estado.yaml", "consequencias.md", "experiencia.md"): ',
    '            for name in ("handoff.yaml", "resumo.md", "alteracoes-de-estado.yaml", "alteracoes-transacionais.yaml", "consequencias.md", "experiencia.md"): ',
)
