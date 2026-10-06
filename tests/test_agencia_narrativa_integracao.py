"""Contrato público e replay da revisão semântica de respostas novas isoladas.

O agente escreveu e revisou as respostas da fixture na entrega documentada.
Estes testes verificam integração/persistência dos pareceres, não são um juiz
semântico automático nem uma nova execução de geração a cada teste.
"""
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "ferramentas"), str(ROOT / "tests")]
import cronica
import narrative_delivery as delivery
import test_memoria_duravel_integracao as fixtures
from ferramentas import entrada_medicao as frozen
from ferramentas import revisao_sessao as workflow

PROOF = workflow.load(ROOT / "tests/fixtures/agencia-narrativa.json")


def publish_review(root, cases, *, replay=True):
    """Replay das decisões explícitas com fontes nativas e publicação real."""
    records = [{"type": "session_meta", "payload": {
        "id": "agencia-isolada", "cwd": "/campanha-isolada"}}]
    for number, case in enumerate(cases, 1):
        turn = f"t{number}"
        ref = f"S999-I{number:04d}"
        records.extend([
            {"type": "event_msg", "payload": {"type": "task_started", "turn_id": turn}},
            {"type": "response_item", "payload": {"type": "message", "role": "user",
                "content": [{"type": "input_text", "text": case["jogador"]}]}},
            {"type": "response_item", "payload": {"type": "function_call", "name": "exec_command",
                "call_id": "fonte", "arguments": json.dumps({"cmd":
                    "poetry run cronica preparar --cena-id fixture --sem-oportunidade-sidequest"}),
                "internal_chat_message_metadata_passthrough": {"turn_id": turn}}},
            {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "fonte",
                "output": "Process exited with code 0\nfase: pronta\n" + case["contexto"] +
                    "\ncontrato_conclusao.campos.narracao: " + delivery.narration_instruction(),
                "internal_chat_message_metadata_passthrough": {"turn_id": turn}}},
            {"type": "response_item", "payload": {"type": "message", "role": "assistant",
                "content": [{"type": "output_text", "text": case["narracao"] +
                    f"\nRODAPE_CANONICO — Interação {ref}"}]}},
        ])
    path = root / "respostas.jsonl"
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n")
    bundle = frozen.prepare_input(path, session_id="999")
    request = workflow.prepare(path, bundle, criterion_ids=[PROOF["criterion_id"]])
    frames = workflow.cases(request)["cases"]
    decisions = []
    for case, frame in zip(cases, frames, strict=True):
        violated = case["player_agency"] == "violado"
        decisions.append({
            "interaction_ref": frame["evaluation_ref"], "criterion_id": PROOF["criterion_id"],
            "state": "avaliada", "eligibility": "sim", "activation": "presente",
            "quality": case["quality"], "reason": case["parecer"],
            "evidence": [{"locator": s["locator"], "quote": s["text"]}
                         for s in frame["sources"] if s["kind"] in {"input", "response", "output"}],
            "guardrails": {"player_agency": case["player_agency"]},
            "diagnosis": {"category": "comportamento_modulo", "stage": "narracao",
                "cause_status": "hipotese", "finding": case["parecer"],
                "correction": "Executar o retorno sem espera voluntária ou intenção nova; devolver a próxima decisão ao jogador.",
                "test": "Comparar retorno livre, espera ordenada e impedimento externo estabelecido."} if violated else None,
        })
    submission = {"request_id": request["request_id"], "reviewer": {
        "identity": "Codex/agencia-narrativa-2026-10-06", "role": "revisor_poshoc",
        "configuration": {"executor": "agente_ativo", "mode":
                          "replay_pareceres_documentados" if replay else "leitura_semantica_das_fontes",
                          "autoria_e_revisao_mesmo_agente": True}}, "decisions": decisions}
    before = path.read_bytes()
    compiled = workflow.compile_reviews(request, submission)
    workflow.publish(path, bundle, request, submission, root / "pacote")
    assert path.read_bytes() == before
    return request, compiled


class NarrativeAgencyIntegrationTest(unittest.TestCase):
    def test_public_prepare_delivers_instruction_and_writer_keeps_review_indeterminate(self):
        for case in PROOF["cases"][:3]:
            with self.subTest(case=case["id"]):
                fixture = fixtures.DurableMemoryIntegrationTest()
                fixture.setUp()
                try:
                    prepared = cronica.prepare(fixture.repo, scene_id=case["id"], sidequest_signal=None)
                    self.assertEqual(prepared["contrato_conclusao"]["campos"]["narracao"],
                                     delivery.narration_instruction())
                    tx = {"id": case["id"], "jogador": case["jogador"], "narracao": case["narracao"],
                          "resumo": "Prosa contrastada em sandbox.", "modo": "exploração", "deltas": []}
                    result = cronica.conclude(fixture.repo, prepared["ticket"], tx)
                    transcript = (fixture.repo / "sessoes/003/transcricao.md").read_text()
                    self.assertIn(case["narracao"], transcript)
                    receipt = result[delivery.RECEIPT_KEY]
                    self.assertEqual(receipt["avaliacao_semantica"], "nao_realizada")
                    self.assertEqual(receipt["guardrails"]["player_agency"], "indeterminado")
                    self.assertFalse(receipt["guardrails_participam_media"])
                finally:
                    fixture.doCleanups()

    def test_semantic_review_validates_contrasted_sources_and_publishes_each_case(self):
        for case in PROOF["cases"]:
            with self.subTest(case=case["id"]), TemporaryDirectory() as temp:
                request, compiled = publish_review(Path(temp), [case])
                self.assertEqual(len(request["required_units"]), 1)
                review = compiled["quality_assessments"][0]
                self.assertEqual(review["review"]["verification"], "verificada")
                self.assertEqual(review["review"]["guardrails"]["player_agency"], case["player_agency"])
                self.assertEqual(len(review["evidence"]), 3)
                self.assertNotIn("parecer", request)

    def test_three_positive_responses_cannot_compensate_critical_voluntary_wait(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            _, compiled = publish_review(root, PROOF["cases"])
            self.assertEqual(len(compiled["quality_assessments"]), 4)
            rows = workflow.load(root / "pacote/resumo-modulos.json")["modulos"]
            row = next(r for r in rows if r["modulo"] == "narrative_delivery")
            self.assertTrue(row["violacoes_guardrail_experiencia"])
            self.assertEqual(row["estado_experiencia"], "violacao_guardrail")
            self.assertEqual(row["leitura_experiencia"]["estado"], "violacao_critica")
            self.assertEqual(row["fila_experiencia_violacoes_criticas"], 1)
            metric = next(c["metricas"] for c in row["experiencia_por_criterio"]
                          if c["criterio_id"] == PROOF["criterion_id"])
            self.assertEqual(metric["nota_qualidade_0a100"], 75.0)
            self.assertIsNone(metric["nota_experiencia_0a100"])
            self.assertIsNone(row["nota_experiencia_interacao_0a100"])
            self.assertEqual(row["fila_experiencia_rank"], 1)


if __name__ == "__main__":
    unittest.main()
