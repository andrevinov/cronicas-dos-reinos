#!/usr/bin/env python3
"""Publica uma revisão do mesmo recorte, sem substituir a avaliação histórica."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rollout", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--entrada-medicao", type=Path, required=True)
    parser.add_argument("--revisao", required=True)
    parser.add_argument("--data-revisao", required=True)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("generator_revision", ROOT / "ferramentas/gerar-avaliacao-sessao.py")
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    result = generator.generate_derived_evaluation(
        args.rollout, original_dir=args.original,
        output_dir=args.original / "revisoes" / args.revisao,
        revision_id=args.revisao, revision_date=args.data_revisao,
        measurement_input=json.loads(args.entrada_medicao.read_text(encoding="utf-8")))
    print(json.dumps({"output_dir": result["output_dir"], "revisao": result["manifest"]["revisao"],
                      "apresentacao": result["scorecard"]["apresentacao"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
