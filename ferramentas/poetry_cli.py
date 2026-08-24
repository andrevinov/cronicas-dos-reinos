"""Entrypoints curtos instalados pelo Poetry.

Os comandos continuam executando os scripts originais em `ferramentas/`; este
módulo só elimina a necessidade de decorar caminhos. O subprocesso usa o mesmo
Python do virtualenv do Poetry e mantém o diretório do repositório como cwd.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


class RepositoryNotFound(RuntimeError):
    """O comando foi executado fora de um checkout de Crônicas dos Reinos."""


def _repo_root() -> Path:
    """Localiza a raiz mesmo quando o comando é chamado de uma subpasta."""
    cwd = Path.cwd().resolve()
    for candidate in (cwd, *cwd.parents):
        if (candidate / "campanha.yaml").is_file() and (candidate / "ferramentas").is_dir():
            return candidate

    # Em instalação editável, __file__ normalmente aponta para o checkout.
    source_root = Path(__file__).resolve().parents[1]
    if (source_root / "campanha.yaml").is_file():
        return source_root

    raise RepositoryNotFound(
        "Não encontrei a raiz de Crônicas dos Reinos. Execute o comando dentro do repositório."
    )


def _run_script(filename: str) -> int:
    repo = _repo_root()
    script = repo / "ferramentas" / filename
    if not script.is_file():
        raise FileNotFoundError(f"ferramenta ausente: {script}")
    return subprocess.run(
        [sys.executable, str(script), *sys.argv[1:]],
        cwd=repo,
        check=False,
    ).returncode


def entrada() -> int:
    return _run_script("entrada.py")


def contexto() -> int:
    return _run_script("contexto.py")


def cronica() -> int:
    return _run_script("cronica.py")


def turno() -> int:
    return _run_script("turno.py")


def checkpoint() -> int:
    return _run_script("checkpoint.py")


def consolidar() -> int:
    return _run_script("consolidar.py")


def auditoria() -> int:
    return _run_script("auditoria-final.py")


def integridade() -> int:
    return _run_script("verificar-integridade.py")


def runtime() -> int:
    return _run_script("gerar-runtime.py")


def sessoes() -> int:
    return _run_script("sessoes.py")


def dados() -> int:
    return _run_script("rolar-dados.py")


def dados_lote() -> int:
    return _run_script("rolar-lote.py")


def rollout() -> int:
    return _run_script("analisar-rollout.py")


def rollout_comparar() -> int:
    return _run_script("comparar-rollouts.py")


def rollout_benchmark() -> int:
    return _run_script("benchmark-rollouts.py")


def preflight() -> int:
    return _run_script("preflight.py")


def testes() -> int:
    repo = _repo_root()
    return subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=repo,
        check=False,
    ).returncode
