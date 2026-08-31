#!/usr/bin/env python3
"""Confere se congelamentos de estado vivo receberam revisão semântica."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
AUDITOR = ROOT / "ferramentas/auditar-testes.py"
REVIEW = Path("tests/live-state-freeze-review.yaml")
ALLOWED_STATUS = {"corrigido", "justificado"}


class LiveStateFreezeReviewError(ValueError):
    pass


def _load_auditor():
    spec = importlib.util.spec_from_file_location("auditar_testes_task1", AUDITOR)
    if spec is None or spec.loader is None:
        raise LiveStateFreezeReviewError("auditor da Task 1 não pôde ser carregado")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_document(repo: Path) -> dict[str, Any]:
    path = repo / REVIEW
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LiveStateFreezeReviewError(f"revisão ausente: {REVIEW.as_posix()}") from exc
    except yaml.YAMLError as exc:
        raise LiveStateFreezeReviewError(f"YAML inválido em {REVIEW.as_posix()}: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema_revisao_congelamento_estado_vivo") != 1:
        raise LiveStateFreezeReviewError("revisão de estado vivo precisa usar schema 1")
    return data


def _validate_section(
    repo: Path,
    files: Any,
    *,
    label: str,
    required: bool,
) -> dict[str, dict[str, str]]:
    if files is None and not required:
        return {}
    if not isinstance(files, dict) or (required and not files):
        raise LiveStateFreezeReviewError(f"revisão precisa declarar {label}")

    clean: dict[str, dict[str, str]] = {}
    for rel, entry in files.items():
        if not isinstance(rel, str) or not rel.startswith("tests/"):
            raise LiveStateFreezeReviewError(f"caminho de teste inválido na revisão: {rel!r}")
        if not (repo / rel).is_file():
            raise LiveStateFreezeReviewError(f"arquivo revisado não existe: {rel}")
        if not isinstance(entry, dict):
            raise LiveStateFreezeReviewError(f"revisão inválida para {rel}")
        status = entry.get("status")
        reason = entry.get("motivo")
        if status not in ALLOWED_STATUS:
            raise LiveStateFreezeReviewError(
                f"{rel}: status precisa ser corrigido ou justificado"
            )
        if not isinstance(reason, str) or len(reason.strip()) < 20:
            raise LiveStateFreezeReviewError(f"{rel}: motivo de revisão é insuficiente")
        clean[rel] = {"status": status, "motivo": reason.strip()}
    return clean


def load_review(repo: Path) -> dict[str, dict[str, str]]:
    data = _load_document(repo)
    return _validate_section(repo, data.get("arquivos"), label="arquivos", required=True)


def load_indirect_review(repo: Path) -> dict[str, dict[str, str]]:
    data = _load_document(repo)
    return _validate_section(
        repo,
        data.get("revisoes_indiretas"),
        label="revisoes_indiretas",
        required=False,
    )


def check(repo: Path = ROOT) -> dict[str, Any]:
    repo = repo.resolve()
    auditor = _load_auditor()
    inventory = auditor.inventory(repo / "tests", repo)
    suspects = set(inventory["candidatos"]["congelamento_suspeito"])
    reviews = load_review(repo)
    indirect = load_indirect_review(repo)
    reviewed = suspects.intersection(reviews)
    unreviewed = sorted(suspects - set(reviews))
    overlap = sorted(set(reviews).intersection(indirect))
    if overlap:
        raise LiveStateFreezeReviewError(
            "arquivo não pode aparecer como revisão direta e indireta: " + ", ".join(overlap)
        )
    return {
        "schema_verificacao_congelamento_estado_vivo": 1,
        "ok": not unreviewed,
        "suspeitos_heuristicos": sorted(suspects),
        "revisados": sorted(reviewed),
        "nao_revisados": unreviewed,
        "decisoes": {rel: reviews[rel] for rel in sorted(reviews)},
        "revisoes_indiretas": {rel: indirect[rel] for rel in sorted(indirect)},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        report = check(args.repo)
    except LiveStateFreezeReviewError as exc:
        print(f"FALHA — revisão de congelamentos de estado vivo: {exc}")
        return 1
    if not report["ok"]:
        print("FALHA — há congelamentos suspeitos sem revisão semântica:")
        for rel in report["nao_revisados"]:
            print(f"- {rel}")
        return 1
    print(
        "OK — congelamentos de estado vivo possuem revisão semântica explícita "
        f"({len(report['revisados'])} heurísticos correntes; "
        f"{len(report['decisoes'])} decisões da Task 1; "
        f"{len(report['revisoes_indiretas'])} revisões indiretas)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
