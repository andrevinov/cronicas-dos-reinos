from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

SPEC = importlib.util.spec_from_file_location("analisar_rollout_nv14", TOOLS / "analisar-rollout.py")
assert SPEC is not None and SPEC.loader is not None
analyzer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analyzer)


class LivenessRolloutTelemetryTest(unittest.TestCase):
    def test_calma_justificada_nao_e_confundida_com_ausencia_de_consulta(self):
        observed = analyzer._liveness_observation(
            """
schema_fronteira_vivacidade: 1
avaliacoes:
- pressao_primaria: null
  recibo_calma:
    estado: calma_justificada
- pressao_primaria: null
  recibo_calma:
    estado: calma_justificada
"""
        )
        self.assertEqual(observed["avaliacoes"], 2)
        self.assertEqual(observed["calma_justificada"], 2)
        self.assertEqual(observed["pressao"], 0)
        self.assertEqual(observed["modulos_nao_consultados"], 0)

    def test_pressao_e_calma_podem_coexistir_em_janelas_diferentes(self):
        observed = analyzer._liveness_observation(
            """
schema_fronteira_vivacidade: 1
avaliacoes:
- pressao_primaria: compromisso-x
  recibo_calma: null
- pressao_primaria: null
  recibo_calma:
    estado: calma_justificada
"""
        )
        self.assertEqual(observed["avaliacoes"], 2)
        self.assertEqual(observed["pressao"], 1)
        self.assertEqual(observed["calma_justificada"], 1)

    def test_cobertura_incompleta_e_modulos_nao_consultados(self):
        observed = analyzer._liveness_observation(
            "ERRO: cobertura incompleta da fronteira de vivacidade: ambiente_publico"
        )
        self.assertEqual(observed["modulos_nao_consultados"], 1)
        self.assertEqual(observed["calma_justificada"], 0)

    def test_saida_sem_nv14_nao_conta_como_calma(self):
        self.assertIsNone(analyzer._liveness_observation("ok: true\nendpoint: cena.preparar\n"))


if __name__ == "__main__":
    unittest.main()
