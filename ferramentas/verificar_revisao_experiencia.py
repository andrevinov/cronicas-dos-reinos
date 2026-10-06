"""Prepara episódios sem gabarito e mede decisões de revisão contra referência.

Não produz julgamentos narrativos. Medição de replay é separada da execução da
revisão pelo agente; nenhuma resposta esperada é passada ao avaliador.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from ferramentas import revisao_sessao as workflow
from ferramentas import entrada_medicao as frozen

CORPUS = ROOT / "evaluation/aceite-experiencia-v1"


def check_reference():
    manifest = workflow.load(CORPUS / "manifest.json")
    for name, sha in manifest["reference_sha256"].items():
        if hashlib.sha256((CORPUS / name).read_bytes()).hexdigest() != sha:
            raise ValueError("Referência de aceite alterada; preserve a anterior")
    return manifest


def prepare_episodes(output):
    manifest = check_reference()
    results = []
    for episode in workflow.load(CORPUS / manifest["active_corpus"])["episodes"]:
        directory = Path(output) / episode["id"]
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "fonte.jsonl"
        text = "\n".join(json.dumps(record, ensure_ascii=False) for record in episode["records"]) + "\n"
        if path.exists() and path.read_text() != text:
            raise ValueError("Fonte do episódio alterada")
        path.write_text(text)
        bundle = frozen.prepare_input(path, session_id="999")
        request = workflow.prepare(path, bundle, criterion_ids=[episode["criterion_id"]], interaction_refs=[episode["interaction_ref"]])
        workflow.save_once(directory / "entrada.json", bundle, private=True)
        workflow.save_once(directory / "pedido.json", request, private=True)
        workflow.save_once(directory / "origem.json", {"rollout": str(path.resolve())}, private=True)
        results.append({"id": episode["id"], "request_id": request["request_id"], "workdir": str(directory)})
    return results


def measure(workdir, submissions, *, replay=False):
    manifest = check_reference()
    expected = {case["id"]: case for case in workflow.load(CORPUS / "gabarito.json")["cases"]}
    judgments = workflow.load(submissions)
    actual = {case["id"]: case for case in judgments["cases"]}
    if set(actual) != set(expected):
        raise ValueError("Revisão deve abranger todos os episódios congelados")
    results = []
    for identifier, gold in expected.items():
        request = workflow.load(Path(workdir) / identifier / "pedido.json")
        judgment = actual[identifier]
        if judgment["source_sha256"] != request["source_sha256"]:
            raise ValueError("Parecer registrado pertence a outra fonte")
        submission = judgment["submission"]
        if replay:
            submission = {**submission, "request_id": request["request_id"]}
        compiled = workflow.compile_reviews(request, submission)
        decision = submission["decisions"][0]
        item = compiled["quality_assessments"][0]
        checks = {key: item[key] == gold[key] for key in ("eligibility", "activation", "quality")}
        checks["decision_state"] = decision["state"] == gold["state"]
        checks["guardrails"] = item["review"]["guardrails"] == gold["guardrails"]
        checks["stage"] = (item["review"].get("diagnosis") or {}).get("stage") == gold["stage"]
        checks["binding"] = item["review"]["verification"] == "verificada"
        results.append({"id": identifier, "property": gold["property"], "split": gold["split"],
                        "checks": checks, "passed": all(checks.values())})
    return {"schema": 1, "status": "aprovado" if all(row["passed"] for row in results) else "reprovado",
            "mode": "replay_de_pareceres_registrados" if replay else "conferencia_da_revisao_executada",
            "reference_sha256": manifest["reference_sha256"],
            "submissions_sha256": hashlib.sha256(Path(submissions).read_bytes()).hexdigest(),
            "cases": len(results), "checks": sum(len(row["checks"]) for row in results),
            "passed_checks": sum(sum(row["checks"].values()) for row in results),
            "properties": sorted({row["property"] for row in results}), "results": results,
            "limit": "Não é prova de generalização, validação cega por terceiro ou aceite dos módulos jogados."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    start = sub.add_parser("preparar")
    start.add_argument("--trabalho", required=True, type=Path)
    end = sub.add_parser("medir")
    end.add_argument("--trabalho", required=True, type=Path)
    end.add_argument("--pareceres", required=True, type=Path)
    end.add_argument("--replay", action="store_true")
    end.add_argument("--saida", required=True, type=Path)
    args = parser.parse_args()
    try:
        if args.cmd == "preparar":
            print(json.dumps(prepare_episodes(args.trabalho), ensure_ascii=False, indent=2))
            return 0
        result = measure(args.trabalho, args.pareceres, replay=args.replay)
        workflow.save_once(args.saida, result)
        print(json.dumps({key: value for key, value in result.items() if key != "results"}, ensure_ascii=False, indent=2))
        return int(result["status"] != "aprovado")
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "bloqueada", "erro": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
