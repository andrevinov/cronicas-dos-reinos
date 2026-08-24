from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import contexto
import dialogo_relacional
import texturas


class RelationshipDialoguePureTest(unittest.TestCase):
    def test_quatro_quadrantes_sao_deterministicos(self):
        cases = {
            (2, 3): "baixa_afinidade_baixa_confianca",
            (8, 3): "alta_afinidade_baixa_confianca",
            (3, 8): "baixa_afinidade_alta_confianca",
            (8, 8): "alta_afinidade_alta_confianca",
        }
        for pair, expected in cases.items():
            with self.subTest(pair=pair):
                self.assertEqual(dialogo_relacional.relationship_mode(*pair), expected)

    def test_cinco_ou_null_nao_fabricam_quadrante_forte(self):
        for pair in ((5, 8), (8, 5), (None, 8), (8, None), (None, None)):
            with self.subTest(pair=pair):
                self.assertEqual(
                    dialogo_relacional.relationship_mode(*pair),
                    "intermediaria_ou_desconhecida",
                )

    def test_conselho_e_gated_e_sermao_automatico_e_proibido(self):
        projection = dialogo_relacional.project(
            {
                "nome": "Teste",
                "medidores": {"vinculo": 8, "confianca": 8, "risco_percebido": 4},
            },
            role="espelho_afetivo",
        )
        self.assertIsNotNone(projection)
        dialogo_relacional.validate_projection(projection)
        self.assertEqual(projection["conselho"]["iniciativa"], "somente_com_gatilho")
        self.assertEqual(len(projection["conselho"]["gatilhos"]), 3)
        self.assertIn("Não converter conversa casual", projection["conselho"]["guardrail"])
        self.assertEqual(projection["papel_base"], "espelho_afetivo")

    def test_risco_alto_endurece_limite_sem_apagar_relacao(self):
        projection = dialogo_relacional.project(
            {
                "nome": "Silva",
                "medidores": {"vinculo": 8, "confianca": 8, "risco_percebido": 10},
            },
            role="guardia_pragmatica",
        )
        self.assertEqual(projection["modo"], "alta_afinidade_alta_confianca")
        self.assertIn("Risco alto", projection["modulador_de_risco"])
        self.assertIn("não apaga afeto/confiança", projection["modulador_de_risco"])


class RelationshipDialogueRepositoryTest(unittest.TestCase):
    def test_nera_combina_papel_e_relacao_alta_alta_na_mesma_consulta(self):
        data = contexto.command_npc(ROOT, "Nera")
        result = data["resultado"]
        self.assertEqual(
            result["textura_narrativa"]["papel_conversacional"]["papel"],
            "espelho_afetivo",
        )
        dialogue = result["dialogo_relacional"]
        self.assertEqual(dialogue["modo"], "alta_afinidade_alta_confianca")
        self.assertEqual(dialogue["papel_base"], "espelho_afetivo")
        self.assertEqual(dialogue["afinidade"], 8)
        self.assertEqual(dialogue["confianca"], 8)
        self.assertNotIn("ferramentas/dialogo_relacional.py", data["fontes"])
        self.assertNotIn("estado/npcs/relacionamento-v1.yaml", data["fontes"])

    def test_luath_mostra_respeito_profissional_sem_intimidade(self):
        dialogue = contexto.command_npc(ROOT, "Luath")["resultado"]["dialogo_relacional"]
        self.assertEqual(dialogue["modo"], "baixa_afinidade_alta_confianca")
        self.assertIn("respeito profissional", dialogue["tom"])
        self.assertIn("sem intimidade", dialogue["tom"])

    def test_pell_sem_papel_opt_in_ainda_recebe_calibracao_relacional(self):
        data = contexto.command_npc(ROOT, "Pell")
        result = data["resultado"]
        self.assertIsNone(result.get("textura_narrativa"))
        dialogue = result["dialogo_relacional"]
        self.assertEqual(dialogue["modo"], "baixa_afinidade_baixa_confianca")
        self.assertNotIn("papel_base", dialogue)

    def test_delta_pendente_da_task26_muda_quadrante_antes_do_checkpoint(self):
        pending = [
            {
                "id": "tx-relacao-pendente",
                "sessao": 1,
                "deltas": [
                    {
                        "alvo": "npc:jack_mooney",
                        "op": "inc",
                        "caminho": "medidores.vinculo",
                        "valor": 1,
                        "fato_canonico": "Jack reconheceu uma ação persistente que melhorou o vínculo com Ren.",
                        "fonte": "fixture:task27",
                    }
                ],
            }
        ]
        with mock.patch.object(contexto, "_pending", return_value=pending):
            data = contexto.command_npc(ROOT, "Jack Mooney")
        dialogue = data["resultado"]["dialogo_relacional"]
        self.assertEqual(dialogue["afinidade"], 6)
        self.assertEqual(dialogue["confianca"], 7)
        self.assertEqual(dialogue["modo"], "alta_afinidade_alta_confianca")
        self.assertIn("runtime/eventos-pendentes.jsonl", data["fontes"])

    def test_status_e_cena_continuam_sem_dialogo_relacional(self):
        status = contexto.command_status(ROOT)
        scene = contexto.command_scene(ROOT)
        self.assertNotIn("dialogo_relacional", yaml.safe_dump(status, allow_unicode=True))
        self.assertNotIn("dialogo_relacional", yaml.safe_dump(scene, allow_unicode=True))

    def test_saida_l2_preserva_dialogo_dentro_do_orcamento(self):
        data = contexto.command_npc(ROOT, "Nera")
        rendered, _ = contexto.fit_budget(data, contexto.DEFAULT_MAX_BYTES, False)
        self.assertLessEqual(len(rendered.encode("utf-8")), contexto.DEFAULT_MAX_BYTES)
        delivered = yaml.safe_load(rendered)
        self.assertIn("dialogo_relacional", delivered["resultado"])
        dialog_bytes = len(
            yaml.safe_dump(
                data["resultado"]["dialogo_relacional"],
                allow_unicode=True,
                sort_keys=False,
            ).encode("utf-8")
        )
        budget = yaml.safe_load(
            (ROOT / "baseline/relationship-aware-dialogue-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )["limites"]["max_saida_dialogo_relacional_bytes"]
        self.assertLessEqual(dialog_bytes, budget)

    def test_perfis_revisados_nao_induzem_sermao_por_padrao(self):
        index = texturas.load_yaml(ROOT / texturas.INDEX_PATH)
        profiles = [
            entry["papel_conversacional"]
            for entry in index["npcs"].values()
            if isinstance(entry, dict) and "papel_conversacional" in entry
        ]
        rendered = yaml.safe_dump(profiles, allow_unicode=True).lower()
        self.assertNotIn("reenquadrar a premissa antes de dar uma resposta pronta", rendered)
        self.assertNotIn("combinar cuidado concreto com censura", rendered)
        self.assertIn("sermão automático", rendered)


class RelationshipDialogueBudgetTest(unittest.TestCase):
    def test_contrato_congela_zero_infra_e_zero_leitura_extra(self):
        data = yaml.safe_load(
            (ROOT / "baseline/relationship-aware-dialogue-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        limits = data["limites"]
        self.assertEqual(limits["chamadas_extras_por_consulta_npc"], 0)
        self.assertEqual(limits["fontes_extras_por_consulta_npc"], 0)
        self.assertEqual(limits["leituras_extras_status_cena"], 0)
        self.assertEqual(limits["schedulers_novos"], 0)
        self.assertEqual(limits["rng_novo"], 0)
        self.assertEqual(limits["estados_persistentes_novos"], 0)
        self.assertEqual(limits["modos_relacionais_principais"], 4)
        self.assertEqual(limits["modos_fallback"], 1)
        inv = data["invariantes"]
        self.assertTrue(inv["aplica_deltas_pendentes_antes_da_calibracao"])
        self.assertTrue(inv["sermao_automatico_e_proibido"])
        self.assertTrue(inv["nenhuma_fala_e_scriptada"])


if __name__ == "__main__":
    unittest.main()
