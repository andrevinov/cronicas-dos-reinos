#!/usr/bin/env python3
"""Gate local único antes de push/merge.

Executa, em sequência, contratos read-only/check da campanha. O preflight não
consolida, não avança sessão e não altera cânone.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Check:
    nome: str
    comando: tuple[str, ...]
    grupo: str


@dataclass(frozen=True)
class Result:
    check: Check
    retorno: int
    segundos: float

    @property
    def ok(self) -> bool:
        return self.retorno == 0


def checks(*, incluir_testes: bool = True) -> list[Check]:
    python = sys.executable
    result: list[Check] = []
    if incluir_testes:
        result.append(
            Check(
                "testes unitários",
                (python, "-m", "unittest", "discover", "-s", "tests", "-v"),
                "regressão",
            )
        )
    result.extend(
        [
            Check("turno transacional", (python, "ferramentas/turno.py", "check"), "operação"),
            Check("consolidação", (python, "ferramentas/consolidar.py", "check"), "operação"),
            Check("memória de sessões", (python, "ferramentas/sessoes.py", "check"), "operação"),
            Check("checkpoint", (python, "ferramentas/checkpoint.py", "check"), "operação"),
            Check(
                "recompensas determinísticas",
                (python, "ferramentas/recompensas.py", "check"),
                "mundo vivo",
            ),
            Check(
                "recompensas de sidequest",
                (python, "ferramentas/recompensas_sidequest.py", "check"),
                "mundo vivo",
            ),
            Check(
                "integridade adversarial",
                (python, "ferramentas/integridade_adversarial.py", "check"),
                "mundo vivo",
            ),
            Check(
                "progressão e consequências de sidequest",
                (python, "ferramentas/progressao_sidequests.py", "check"),
                "mundo vivo",
            ),
            Check(
                "integração de sidequests emergentes",
                (python, "ferramentas/sidequests_integracao_check.py"),
                "mundo vivo",
            ),
            Check(
                "oportunidades de sidequest",
                (python, "ferramentas/oportunidades.py", "check"),
                "mundo vivo",
            ),
            Check(
                "canon bridge",
                (python, "ferramentas/canon_bridge_runtime.py", "check"),
                "mundo vivo",
            ),
            Check(
                "integração reativa",
                (python, "ferramentas/interacoes_mundo.py", "check"),
                "mundo vivo",
            ),
            Check(
                "estado atual separado do histórico",
                (python, "ferramentas/migrar-estado-atual.py", "--check"),
                "estrutura",
            ),
            Check(
                "memórias fragmentadas",
                (python, "ferramentas/migrar-memorias-fragmentadas.py", "--check"),
                "estrutura",
            ),
            Check(
                "índice de conhecimento",
                (python, "ferramentas/reindexar-conhecimento.py", "--check"),
                "estrutura",
            ),
            Check("runtime derivado", (python, "ferramentas/gerar-runtime.py", "--check"), "estrutura"),
            Check(
                "consistência ruleset D&D 5.5e",
                (python, "ferramentas/ruleset_5_5e.py", "check"),
                "integridade",
            ),
            Check(
                "gate AD&D para ruleset moderno",
                (python, "ferramentas/gate_adnd.py", "check"),
                "integridade",
            ),
            Check(
                "integridade estrutural e semântica",
                (python, "ferramentas/verificar-integridade.py"),
                "integridade",
            ),
            Check(
                "baseline histórica",
                (python, "ferramentas/verificar-integridade.py", "--verificar-baseline-historica"),
                "integridade",
            ),
            Check(
                "auditoria final e retomada",
                (python, "ferramentas/auditoria-final.py", "--json"),
                "retomada",
            ),
        ]
    )
    return result


def run_check(repo: Path, check: Check) -> Result:
    print(f"\n==> {check.nome}", flush=True)
    started = time.monotonic()
    try:
        proc = subprocess.run(check.comando, cwd=repo, check=False)
        code = proc.returncode
    except OSError as exc:
        print(f"FALHA — não foi possível executar: {exc}", file=sys.stderr)
        code = 127
    elapsed = time.monotonic() - started
    print(f"<== {'OK' if code == 0 else 'FALHA'} — {check.nome} ({elapsed:.2f}s)", flush=True)
    return Result(check, code, elapsed)


def run_preflight(
    repo: Path,
    *,
    incluir_testes: bool = True,
    fail_fast: bool = False,
) -> list[Result]:
    results: list[Result] = []
    for check in checks(incluir_testes=incluir_testes):
        result = run_check(repo, check)
        results.append(result)
        if fail_fast and not result.ok:
            break
    return results


def _summary(results: Sequence[Result]) -> str:
    failures = [item for item in results if not item.ok]
    total = sum(item.segundos for item in results)
    lines = ["", "PREFLIGHT", f"Checks executados: {len(results)} | tempo: {total:.2f}s"]
    if failures:
        lines.append(f"VEREDITO: FALHA ({len(failures)} gate(s))")
        for item in failures:
            lines.append(f"- {item.check.nome}: exit {item.retorno}")
    else:
        lines.append("VEREDITO: OK — pronto para push/merge")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    parser.add_argument(
        "--sem-testes",
        action="store_true",
        help="pula somente unittest; mantém todos os checks de integração",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="para no primeiro gate vermelho em vez de coletar todos os erros",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo = args.repo.resolve()
    results = run_preflight(
        repo,
        incluir_testes=not args.sem_testes,
        fail_fast=args.fail_fast,
    )
    print(_summary(results))
    return 0 if results and all(item.ok for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
