"""Interrupção após o commit da conclusão: a próxima causa continua bloqueante."""
from contextlib import redirect_stdout
import io
import unittest
from unittest.mock import patch

import test_acionamentos_leves_recuperacao as fixtures

causal = fixtures.causal
light = fixtures.light
barrier = fixtures.barrier
cronica = fixtures.cronica


class CausalMarkerRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CausalBoundaryRecoveryTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.f = self.fixture.f
        self.repo = self.fixture.repo

    def test_queda_no_marcador_preserva_proxima_causa_no_estado_e_na_barreira(self):
        index = light.load_index(self.repo)
        index["orcamento"]["max_pendencias_abertas"] = 1
        self.f.write(causal.INDEX.as_posix(), index)
        first = self.fixture.enqueue(self.f.people)[0]["id"]
        with patch.object(barrier, "sync", side_effect=OSError("interrupção simulada do marcador")):
            with self.assertRaises(light.LightAgentError):
                light.conclude_noop(self.repo, first, fixtures.cases.NOTE)
        world = self.f.world()
        self.assertEqual(len(world["pendencias"]), 1)
        self.assertNotEqual(world["pendencias"][0]["id"], first)
        self.assertEqual(len(world[causal.KEY]["aguardando"]), 1)
        before = self.f.f.hashes()
        prepared = cronica.prepare(self.repo, scene_id="bloqueio-recuperavel", sidequest_signal=None)
        self.assertEqual(prepared["fase"], "bloqueada_pendencias_mundo")
        self.assertEqual(before, self.f.f.hashes())
        light.conclude_noop(self.repo, first, fixtures.cases.NOTE)
        self.assertEqual(self.f.world(), world)
        self.assertTrue(barrier.load_status(self.repo)["bloqueado"])

    def test_cli_barreira_preserva_argv_programatico_e_somente_leitura(self):
        before = self.f.f.hashes()
        output = io.StringIO()
        with redirect_stdout(output):
            result = barrier.main(["--repo", str(self.repo), "check"])
        self.assertEqual(result, 0, output.getvalue())
        self.assertEqual(before, self.f.f.hashes())


if __name__ == "__main__":
    unittest.main()
