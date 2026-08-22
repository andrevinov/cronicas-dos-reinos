from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import contexto_cena


class TypedContextTagBudgetTest(unittest.TestCase):
    def test_contrato_preserva_tetos_e_zero_custo_extra(self):
        data = yaml.safe_load(
            (ROOT / "baseline/tags-contextuais-tipadas-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(data["schema_orcamento_tags_contextuais_tipadas"], 1)
        limits = data["limites"]
        self.assertEqual(limits["tipos_tags"], 5)
        self.assertEqual(limits["max_tags_por_cena"], contexto_cena.MAX_CONTEXT_TAGS)
        self.assertEqual(limits["max_presencas"], contexto_cena.MAX_PRESENCE_CANDIDATES)
        self.assertEqual(limits["max_entradas"], contexto_cena.MAX_ENTRY_CANDIDATES)
        self.assertEqual(limits["max_operacoes"], contexto_cena.MAX_OPERATION_CANDIDATES)
        self.assertEqual(limits["max_direcoes"], contexto_cena.MAX_DIRECTION_CANDIDATES)
        self.assertEqual(limits["max_candidatos_total"], contexto_cena.MAX_CONTEXT_CANDIDATES)
        self.assertEqual(limits["leituras_extras_sem_match"], 0)
        self.assertEqual(limits["fragmentos_narrativos_adicionais"], 0)
        self.assertEqual(limits["schedulers_adicionais"], 0)

    def test_contrato_congela_semantica_espacial(self):
        inv = yaml.safe_load(
            (ROOT / "baseline/tags-contextuais-tipadas-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )["invariantes"]
        self.assertTrue(inv["namespace_obrigatorio"])
        self.assertEqual(inv["tipos_fechados"], list(contexto_cena.TAG_TYPES))
        self.assertTrue(inv["tag_legada_sem_namespace_e_rejeitada"])
        self.assertTrue(inv["presenca_binding_exige_local"])
        self.assertTrue(inv["presenca_match_exige_local"])
        self.assertTrue(inv["assunto_sem_local_nao_cria_presenca"])
        self.assertTrue(inv["operacao_pode_reagir_sem_local"])
        self.assertEqual(inv["scan_semantico_contextual"], 0)


if __name__ == "__main__":
    unittest.main()
