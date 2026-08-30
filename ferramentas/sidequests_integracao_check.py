#!/usr/bin/env python3
"""Check read-only da integração Task46."""
from __future__ import annotations

from pathlib import Path
import sys
import yaml

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import sidequests_integracao_runtime as integration


def main() -> int:
    repo = Path.cwd().resolve()
    result = integration.check(repo)
    print(yaml.safe_dump(result, allow_unicode=True, sort_keys=False), end="")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
