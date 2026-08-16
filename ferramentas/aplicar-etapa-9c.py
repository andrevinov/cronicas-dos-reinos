#!/usr/bin/env python3
"""Patch temporário e determinístico da integração estrutural da Etapa 9."""
from pathlib import Path


def edit(path: str, edits: list[tuple[str, str]]) -> None:
    p = Path(path)
    s = p.read_text(encoding="utf-8")
    for old, new in edits:
        if old not in s:
            raise SystemExit(f"Padrão não encontrado em {path}: {old[:120]!r}")
        s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8")


edit("ferramentas/contexto_core.py", [
    ("\n\nDEFAULT_MAX_BYTES = 8 * 1024", "\n\nimport sessoes as memoria_sessoes\n\nDEFAULT_MAX_BYTES = 8 * 1024"),
    (
        "def iter_search_files(repo: Path, *, reserved: bool, historical: bool) -> Iterable[Path]:",
        "def iter_search_files(\n    repo: Path, *, reserved: bool, historical: bool, transcripts: bool = False\n) -> Iterable[Path]:",
    ),
    (
        '            for name in ("resumo.md", "alteracoes-de-estado.yaml", "consequencias.md", "experiencia.md"): ',
        '            for name in ("handoff.yaml", "resumo.md", "alteracoes-de-estado.yaml", "alteracoes-transacionais.yaml", "consequencias.md", "experiencia.md"): ',
    ),
])
