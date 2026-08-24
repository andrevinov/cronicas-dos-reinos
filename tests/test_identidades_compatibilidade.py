from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import consolidar
import identidades


class IdentityCompatibilityTest(unittest.TestCase):
    def test_gate_sem_delta_de_identidade_nao_exige_registro(self):
        records = [
            {
                "id": "tx-legado",
                "deltas": [
                    {"alvo": "estado", "op": "set", "caminho": "modo", "valor": "interacao"}
                ],
            }
        ]
        self.assertFalse(consolidar._has_identity_deltas(records))
        with mock.patch.object(identidades, "load_registry", side_effect=AssertionError("não deve ler")):
            self.assertFalse(consolidar._has_identity_deltas(records))

    def test_validacao_de_outputs_sem_reconhecimento_nao_abre_registro(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            plan = {
                "outputs": {
                    "estado/npcs/exemplo.yaml": b"schema_npc_fragmento: 1\nid: exemplo\nnpc:\n  nome: Exemplo\n"
                }
            }
            with mock.patch.object(identidades, "load_registry", side_effect=AssertionError("não deve ler")):
                consolidar._validate_npc_outputs(repo, plan)


if __name__ == "__main__":
    unittest.main()
