from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
sys.path.insert(0, str(TOOLS))
MODULE_PATH = TOOLS / "transacoes.py"
spec = importlib.util.spec_from_file_location("transacoes", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


class TransactionSchemaTest(unittest.TestCase):
    def test_stable_id_is_reproducible(self):
        tx = {"jogador": "A", "narracao": "B", "resumo": "C"}
        self.assertEqual(mod.stable_transaction_id(tx, 3), mod.stable_transaction_id(tx, 3))

    def test_invalid_increment_is_rejected(self):
        with self.assertRaises(mod.TransactionError):
            mod.validate_delta(
                {"alvo": "estado", "op": "inc", "caminho": "recursos.ki.atuais", "valor": "-1"}
            )

    def test_pending_loader_rejects_duplicate_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "runtime").mkdir()
            record = {
                "versao": 1,
                "id": "x",
                "sessao": 3,
                "resumo": "teste",
                "deltas": [],
            }
            line = json.dumps(record, ensure_ascii=False)
            (repo / mod.PENDING_PATH).write_text(line + "\n" + line + "\n", encoding="utf-8")
            with self.assertRaises(mod.TransactionError):
                mod.load_pending(repo)


class TransactionOverlayTest(unittest.TestCase):
    def base_runtime(self):
        context = {
            "sessao": {"numero": 3, "modo_de_cena": "exploração"},
            "recursos": {
                "pv": {"atuais": 45, "maximos": 45},
                "ki": {"atuais": 5, "maximos": 6},
                "ca": 17,
                "deslocamento": "55 pés",
                "dinheiro_po": 45,
            },
            "tempo": {"data": "7 Eleasis", "hora_aproximada": "08:03", "periodo": "manhã", "clima": "névoa"},
            "localizacao": {"area": "estrada", "ponto_exato": "cerca"},
        }
        scene = {
            "sessao": 3,
            "modo": "exploração",
            "localizacao": {"area": "estrada", "ponto_exato": "cerca"},
            "tempo": {"data": "7 Eleasis", "hora_aproximada": "08:03"},
            "mecanica_imediata": {"pv": "45/45", "ki": "5/6", "ca": 17, "deslocamento": "55 pés"},
            "resumo_imediato": "antes",
            "prazos_e_alertas": "antes",
        }
        return context, scene

    def test_runtime_overlay_applies_critical_resources_location_time_and_mode(self):
        context, scene = self.base_runtime()
        records = [
            {
                "versao": 1,
                "id": "turno-1",
                "sessao": 3,
                "resumo": "combate avançou",
                "deltas": [
                    {"alvo": "estado", "op": "inc", "caminho": "recursos.ki.atuais", "valor": -2},
                    {"alvo": "estado", "op": "inc", "caminho": "recursos.pontos_de_vida.atuais", "valor": -7},
                    {"alvo": "estado", "op": "set", "caminho": "localizacao.ponto_exato", "valor": "junto ao alvo"},
                    {"alvo": "tempo", "op": "set", "caminho": "hora_aproximada", "valor": "08:04"},
                    {"alvo": "estado", "op": "set", "caminho": "campanha.modo_de_cena_atual", "valor": "combate"},
                    {"alvo": "estado", "op": "set", "caminho": "localizacao.descricao_operacional", "valor": "É o turno de Ren."},
                ],
            }
        ]
        effective, effective_scene, applied = mod.overlay_runtime(context, scene, records)
        self.assertGreaterEqual(applied, 5)
        self.assertEqual(effective["recursos"]["ki"]["atuais"], 3)
        self.assertEqual(effective["recursos"]["pv"]["atuais"], 38)
        self.assertEqual(effective["localizacao"]["ponto_exato"], "junto ao alvo")
        self.assertEqual(effective["tempo"]["hora_aproximada"], "08:04")
        self.assertEqual(effective["sessao"]["modo_de_cena"], "combate")
        self.assertEqual(effective_scene["mecanica_imediata"]["pv"], "38/45")
        self.assertEqual(effective_scene["mecanica_imediata"]["ki"], "3/6")
        self.assertEqual(effective_scene["resumo_imediato"], "É o turno de Ren.")
        self.assertEqual(effective["sobreposicao_transacional"]["ultima_transacao"], "turno-1")

    def test_relation_and_npc_are_overlaid_without_touching_history(self):
        records = [
            {
                "versao": 1,
                "id": "turno-2",
                "sessao": 3,
                "resumo": "Kethra coopera mais",
                "deltas": [
                    {"alvo": "relacao:kethra_dunn", "op": "set", "caminho": "confianca", "valor": "moderada"},
                    {"alvo": "npc:kethra_dunn", "op": "inc", "caminho": "medidores.confianca", "valor": 1},
                ],
            }
        ]
        relation, count = mod.overlay_target({"nome": "Kethra Dunn", "confianca": "baixa"}, records, "relacao:kethra_dunn")
        npc, npc_count = mod.overlay_target({"medidores": {"confianca": 5}}, records, "npc:kethra_dunn")
        self.assertEqual(count, 1)
        self.assertEqual(npc_count, 1)
        self.assertEqual(relation["confianca"], "moderada")
        self.assertEqual(npc["medidores"]["confianca"], 6)

    def test_pending_knowledge_is_searchable_and_hidden_roll_is_not_public(self):
        records = [
            {
                "versao": 1,
                "id": "turno-3",
                "sessao": 3,
                "resumo": "Ren descobriu que a ponte baixa usa uma brasa como sinal.",
                "deltas": [
                    {
                        "alvo": "conhecimento",
                        "op": "registrar",
                        "valor": {"assunto": "ponte baixa", "texto": "brasa protegida e sinal"},
                    }
                ],
                "rolagens_ocultas": ["Percepção secreta do perseguidor: 19"],
            }
        ]
        public = mod.search_pending(records, "brasa", target_prefix="conhecimento")
        self.assertTrue(public)
        self.assertEqual(mod.search_pending(records, "perseguidor", reserved=False), [])
        self.assertTrue(mod.search_pending(records, "perseguidor", reserved=True))


if __name__ == "__main__":
    unittest.main()
