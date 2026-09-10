#!/usr/bin/env python3
"""Agentes leves até NV-17 + no-op temporal seguro da NV-18."""
from __future__ import annotations

from pathlib import Path
import sys

_LEGACY_SOURCE = Path(__file__).with_name("_agentes_leves_nv17.py")
_saved_name = globals().get("__name__", "agentes_leves")
globals()["__name__"] = "_agentes_leves_nv17_exec"
exec(compile(_LEGACY_SOURCE.read_text(encoding="utf-8"), str(_LEGACY_SOURCE), "exec"), globals(), globals())
globals()["__name__"] = _saved_name

_BASE_CONCLUDE_NOOP = conclude_noop
_BASE_MAIN = main

import obrigacoes_temporais


def conclude_noop(
    repo: Path,
    pending_id: str,
    note: str | None = None,
    *,
    retomar_data: str | None = None,
    retomar_hora: str | None = None,
    retomar_condicao: str | None = None,
) -> dict[str, Any]:
    """No-op legado, exceto quando uma obrigação vencida exige próximo gatilho."""
    return obrigacoes_temporais.conclude_noop(
        repo,
        pending_id,
        note,
        retomar_data=retomar_data,
        retomar_hora=retomar_hora,
        retomar_condicao=retomar_condicao,
        base_conclude=_BASE_CONCLUDE_NOOP,
    )


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if "concluir-noop" not in argv:
        return _BASE_MAIN(argv)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("command", choices=["concluir-noop"])
    parser.add_argument("id")
    parser.add_argument("--nota")
    parser.add_argument("--retomar-data")
    parser.add_argument("--retomar-hora")
    parser.add_argument("--retomar-condicao")
    args = parser.parse_args(argv)
    try:
        result = conclude_noop(
            args.repo.resolve(),
            args.id,
            args.nota,
            retomar_data=args.retomar_data,
            retomar_hora=args.retomar_hora,
            retomar_condicao=args.retomar_condicao,
        )
        print(_dump(result), end="")
        return 0
    except (LightAgentError, mundo.WorldEngineError, obrigacoes_temporais.TemporalObligationError) as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
