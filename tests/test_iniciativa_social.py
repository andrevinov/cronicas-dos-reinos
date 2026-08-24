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
import iniciativa_social


class SocialInitiativePureTest(unittest.TestCase):
    def _project(self, affinity, trust, risk=4, identity="ren"):
        payload = {
            "nome": "Teste",
            "identidade_relacional": identity,
            "medidores": {
                "vinculo": affinity,
                "confianca": trust,
                "risco_percebido": risk,
            },
        }
        dialogue = dialogo_relacional.project(payload)
        self.assertIsNotNone(dialogue)
        return dialogue["iniciativa_social"]

    def test_quatro_quadrantes_e_fallback_tem_iniciativas_distintas(self):
        cases = {
            (8, 8): ("espontanea", True, False),
            (8, 3): ("afetiva_cautelosa", True, False),
            (3, 8): ("funcional", True, True),
            (3, 3): ("somente_motivo_concreto", False, True),
            (5, 8): ("situacional", False, True),
        }
        for pair, expected in cases.items():
            with self.subTest(pair=pair):
                social = self._project(*pair)
                self.assertEqual(
                    (social["modo"], social["pode_iniciar"], social["exige_motivo"]),
                    expected,
                )
                iniciativa_social.validate_projection(social)

    def test_null_nao_fabrica_espontaneidade(self):
        social = self._project(None, 8)
        self.assertEqual(social["modo"], "situacional")
        self.assertFalse(social["pode_iniciar"])
        self.assertTrue(social["exige_motivo"])

    def test_risco_alto_nao_promove_relacao_hostil(self):
        social = self._project(2, 2, risk=10)
        self.assertTrue(social["risco_alto"])
        self.assertEqual(social["modo"], "somente_motivo_concreto")
        self.assertFalse(social["pode_iniciar"])

    def test_identidade_relacional_e_preservada(self):
        social = self._project(8, 8, identity="shinta")
        self.assertEqual(social["identidade_relacional"], "shinta")

    def test_sem_medidores_nao_cria_iniciativa(self):
        self.assertIsNone(
            iniciativa_social.project(
                {"nome": "Figurante"},
                relationship_mode="intermediaria_ou_desconhecida",
            )
        )

    def test_limite_proibe_criar_eventos_e_controlar_ren(self):
        social = self._project(8, 8)
        rendered = social["limite"].lower()
        for forbidden in ("encontro", "segredo", "conhecimento", "side quest", "compromisso", "acao de ren"):
            with self.subTest(forbidden=forbidden):
                self.assertIn(forbidden, rendered)
        self.assertIn("task 27", rendered)


class SocialInitiativeRepositoryTest(unittest.TestCase):
    def test_nera_pode_iniciar_contato_cotidiano_sem_virar_sermao(self):
        result = contexto.command_npc(ROOT, "Nera")["resultado"]
        dialogue = result["dialogo_relacional"]
        social = dialogue["iniciativa_social"]
        self.assertEqual(dialogue["modo"], "alta_afinidade_alta_confianca")
        self.assertEqual(social["modo"], "espontanea")
        self.assertTrue(social["pode_iniciar"])
        self.assertFalse(social["exige_motivo"])
        self.assertTrue(social["risco_alto"])
        self.assertEqual(social["identidade_relacional"], "ren")
        self.assertEqual(dialogue["conselho"]["iniciativa"], "somente_com_gatilho")

    def test_luath_tem_iniciativa_funcional_sem_intimidade(self):
        social = contexto.command_npc(ROOT, "Luath")["resultado"]["dialogo_relacional"]["iniciativa_social"]
        self.assertEqual(social["modo"], "funcional")
        self.assertTrue(social["pode_iniciar"])
        self.assertTrue(social["exige_motivo"])
        self.assertIn("abordagem profissional", social["escopo"])
        self.assertNotIn("pedido pessoal pequeno", social["escopo"])

    def test_sella_inicia_com_shinta_nao_com_ren(self):
        social = contexto.command_npc(ROOT, "Sella Conferente Galeria")["resultado"]["dialogo_relacional"]["iniciativa_social"]
        self.assertEqual(social["modo"], "espontanea")
        self.assertEqual(social["identidade_relacional"], "shinta")

    def test_pell_nao_ganha_sociabilidade_gratuita(self):
        social = contexto.command_npc(ROOT, "Pell")["resultado"]["dialogo_relacional"]["iniciativa_social"]
        self.assertEqual(social["modo"], "somente_motivo_concreto")
        self.assertFalse(social["pode_iniciar"])
        self.assertTrue(social["exige_motivo"])

    def test_delta_pendente_muda_iniciativa_antes_do_checkpoint(self):
        pending = [
            {
                "id": "tx-iniciativa-social",
                "sessao": 1,
                "deltas": [
                    {
                        "alvo": "npc:jack_mooney",
                        "op": "inc",
                        "caminho": "medidores.vinculo",
                        "valor": 1,
                        "fato_canonico": "Jack reconheceu um fato persistente que aproximou sua relacao com Ren.",
                        "fonte": "fixture:task30",
                    }
                ],
            }
        ]
        base = contexto.command_npc(ROOT, "Jack Mooney")["resultado"]["dialogo_relacional"]["iniciativa_social"]
        self.assertEqual(base["modo"], "situacional")
        with mock.patch.object(contexto, "_pending", return_value=pending):
            data = contexto.command_npc(ROOT, "Jack Mooney")
        social = data["resultado"]["dialogo_relacional"]["iniciativa_social"]
        self.assertEqual(social["modo"], "espontanea")
        self.assertTrue(social["pode_iniciar"])
        self.assertIn("runtime/eventos-pendentes.jsonl", data["fontes"])

    def test_status_e_cena_nao_carregam_iniciativa_social(self):
        status = yaml.safe_dump(contexto.command_status(ROOT), allow_unicode=True)
        scene = yaml.safe_dump(contexto.command_scene(ROOT), allow_unicode=True)
        self.assertNotIn("iniciativa_social", status)
        self.assertNotIn("iniciativa_social", scene)

    def test_mesma_consulta_nao_adiciona_fonte_nova(self):
        data = contexto.command_npc(ROOT, "Nera")
        self.assertNotIn("ferramentas/iniciativa_social.py", data["fontes"])
        self.assertNotIn("baseline/npc-social-initiative-orcamento.yaml", data["fontes"])


class SocialInitiativeBudgetTest(unittest.TestCase):
    def test_contrato_congela_zero_infra_e_mesma_consulta(self):
        budget = yaml.safe_load(
            (ROOT / "baseline/npc-social-initiative-orcamento.yaml").read_text(encoding="utf-8")
        )
        limits = budget["limites"]
        self.assertEqual(limits["chamadas_extras_por_consulta_npc"], 0)
        self.assertEqual(limits["fontes_extras_por_consulta_npc"], 0)
        self.assertEqual(limits["leituras_extras_status_cena"], 0)
        self.assertEqual(limits["schedulers_novos"], 0)
        self.assertEqual(limits["rng_novo"], 0)
        self.assertEqual(limits["estados_persistentes_novos"], 0)
        self.assertEqual(limits["max_escopos_por_modo"], iniciativa_social.MAX_OPENINGS)
        self.assertTrue(all(budget["invariantes"].values()))

    def test_pior_caso_real_cabe_no_orcamento_antigo_de_dialogo(self):
        data = contexto.command_npc(ROOT, "Nera")
        dialogue = data["resultado"]["dialogo_relacional"]
        social = dialogue["iniciativa_social"]
        dialogue_bytes = len(
            yaml.safe_dump(dialogue, allow_unicode=True, sort_keys=False).encode("utf-8")
        )
        social_bytes = len(
            yaml.safe_dump(social, allow_unicode=True, sort_keys=False).encode("utf-8")
        )
        limits = yaml.safe_load(
            (ROOT / "baseline/npc-social-initiative-orcamento.yaml").read_text(encoding="utf-8")
        )["limites"]
        old_dialogue_limit = yaml.safe_load(
            (ROOT / "baseline/relationship-aware-dialogue-orcamento.yaml").read_text(encoding="utf-8")
        )["limites"]["max_saida_dialogo_relacional_bytes"]
        self.assertLessEqual(social_bytes, limits["max_saida_iniciativa_social_bytes"])
        self.assertLessEqual(dialogue_bytes, limits["max_saida_dialogo_relacional_com_iniciativa_bytes"])
        self.assertLessEqual(dialogue_bytes, old_dialogue_limit)

        rendered, _ = contexto.fit_budget(data, contexto.DEFAULT_MAX_BYTES, False)
        self.assertLessEqual(len(rendered.encode("utf-8")), contexto.DEFAULT_MAX_BYTES)
        self.assertIn("iniciativa_social", yaml.safe_load(rendered)["resultado"]["dialogo_relacional"])


if __name__ == "__main__":
    unittest.main()
