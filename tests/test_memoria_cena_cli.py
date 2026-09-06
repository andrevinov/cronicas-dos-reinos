"""Retomada pela CLI real e validação do transporte, em fixtures isoladas."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

import yaml
import test_memoria_cena_integracao as fixtures


class SceneMemoryCliTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SceneMemoryIntegrationTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_cli_retomada_preserva_memoria_em_ambos_formatos(self):
        fixture = self.fixture
        fixtures.checkpoint.refresh_memory(fixture.repo, "cena")
        prepared = fixture.prepare(["silva_fixture"])
        fixtures.cronica.conclude(fixture.repo, prepared["ticket"], fixture.f.promise())
        program = Path(__file__).resolve().parents[1] / "ferramentas" / "contexto.py"
        for persistence in ("pendente", "consolidada"):
            if persistence == "consolidada":
                fixtures.consolidar.consolidate(fixture.repo, "cena")
            before = fixture.f.hashes()
            for options in (["--json"], []):
                with self.subTest(persistencia=persistence, formato=options or "yaml"):
                    process = subprocess.run(
                        [sys.executable, str(program), "--repo", str(fixture.repo), *options, "retomada"],
                        capture_output=True, text=True, encoding="utf-8", check=False,
                    )
                    diagnostics = f"program={program}\nSTDERR:\n{process.stderr}\nSTDOUT:\n{process.stdout}"
                    self.assertEqual(process.returncode, 0, diagnostics)
                    # JSON precisa ser JSON de fato, não apenas YAML compatível.
                    output = json.loads(process.stdout) if options else yaml.safe_load(process.stdout)
                    self.assertIsInstance(output, dict, diagnostics)
                    self.assertIn("memoria_cena", output, diagnostics)
                    pack = output["memoria_cena"]
                    self.assertEqual(pack["modo"], "completa")
                    self.assertIn("silva_fixture", pack["itens"])
                    self.assertIn("@compromissos", pack["itens"])
                    self.assertIn("Entregar o mapa a Silva.", json.dumps(pack, ensure_ascii=False))
                    self.assertLessEqual(len(process.stdout.encode("utf-8")), 8192)
                    self.assertEqual(before, fixture.f.hashes())

    def test_ticket_invalido_continua_recusado_com_estado_canonico(self):
        fixture = self.fixture
        before = fixture.f.hashes()
        prepared = {"ticket": "crn1.fixture", "ticket_id": "fixture"}
        with self.assertRaisesRegex(fixtures.cronica.CronicaError, "ticket"):
            fixtures.memory.attach(
                fixture.repo, prepared,
                decode_ticket=fixtures.cronica.decode_ticket,
                encode_ticket=fixtures.cronica.encode_ticket,
            )
        self.assertEqual(before, fixture.f.hashes())
        self.assertEqual(prepared, {"ticket": "crn1.fixture", "ticket_id": "fixture"})
