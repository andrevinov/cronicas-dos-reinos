from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

TOOLS = Path(__file__).parents[1] / "ferramentas"
sys.path.insert(0, str(TOOLS))

import checkpoint

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


class CheckpointMemoryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "runtime").mkdir(parents=True)
        (self.repo / "sessoes/003").mkdir(parents=True)
        self._yaml(
            "runtime/contexto.yaml",
            {
                "sessao": {"numero": 3, "status": "em_sessao", "modo_de_cena": "combate"},
                "personagem": {"nome": "Ren", "nivel": 6},
                "recursos": {"pv": {"atuais": 40, "maximos": 45}, "ki": {"atuais": 3, "maximos": 6}, "ca": 17},
                "tempo": {"data": "7 Eleasis", "hora_aproximada": "08:20"},
                "localizacao": {"cidade": "Ravens Bluff", "area": "estrada", "ponto_exato": "ponte"},
            },
        )
        self._yaml(
            "runtime/cena.yaml",
            {
                "sessao": 3,
                "modo": "combate",
                "resumo_imediato": "Ren está adjacente ao adversário.",
                "prazos_e_alertas": "Há testemunhas.",
            },
        )
        (self.repo / "runtime/eventos-pendentes.jsonl").write_text("", encoding="utf-8")
        (self.repo / "sessoes/003/transcricao.md").write_text("# Sessão 003\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def _yaml(self, rel: str, value):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def test_checkpoint_atualiza_handoff_e_indice_depois_do_canone(self):
        fake = {"sessao": 3, "tipo": "cena", "sem_pendencias": True}
        with patch.object(checkpoint.consolidar, "consolidate", return_value=fake):
            result = checkpoint.checkpoint(self.repo, "cena")

        self.assertEqual(result["canonico"], fake)
        self.assertTrue((self.repo / "sessoes/003/handoff.yaml").is_file())
        self.assertTrue((self.repo / "sessoes/index.yaml").is_file())
        handoff = yaml.safe_load((self.repo / "sessoes/003/handoff.yaml").read_text(encoding="utf-8"))
        self.assertEqual(handoff["checkpoint"]["tipo"], "cena")
        self.assertEqual(handoff["checkpoint"]["recursos"]["ki"]["atuais"], 3)

    def test_refresh_e_idempotente_com_mesmo_runtime(self):
        first = checkpoint.refresh_memory(self.repo, "cena")
        before = (self.repo / "sessoes/003/handoff.yaml").read_bytes()
        second = checkpoint.refresh_memory(self.repo, "cena")
        after = (self.repo / "sessoes/003/handoff.yaml").read_bytes()
        self.assertEqual(first["handoff"], second["handoff"])
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
