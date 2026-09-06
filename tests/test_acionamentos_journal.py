"""O journal bloqueia no-ops mesmo antes da primeira chave causal ser instalada."""
from unittest.mock import patch
import unittest

import test_acionamentos_leves as cases

causal = cases.causal
light = cases.light
consolidar = cases.consolidar


class CausalJournalEntryGuardTest(unittest.TestCase):
    def setUp(self):
        self.f = cases.CausalActivationIntegrationTest()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.repo = self.f.repo

    def test_noop_bloqueia_antes_de_ler_indice_ou_estado_sem_chave_causal(self):
        import _consolidar_core
        self.assertNotIn(causal.KEY, self.f.world())
        journal = self.repo / _consolidar_core.JOURNAL_PATH
        journal.parent.mkdir(parents=True, exist_ok=True)
        journal.write_text('{}', encoding="utf-8")
        before = self.f.f.hashes()
        with patch.object(light, "load_index") as index, \
                patch.object(light, "load_state") as state, \
                patch.object(light.mundo, "load_world_state") as world:
            with self.assertRaisesRegex(light.LightAgentError, "consolidação interrompida"):
                light.conclude_noop(self.repo, "mundo-" + "a" * 16, cases.NOTE)
        index.assert_not_called()
        state.assert_not_called()
        world.assert_not_called()
        self.assertEqual(before, self.f.f.hashes())

    def test_instalacao_parcial_sem_chave_nao_conclui_rotina_nem_instala_cache(self):
        # Persistir o turno sem checkpoint para montar um journal real abaixo.
        with patch.object(cases.turno, "detect_world_checkpoint", return_value=None):
            cases.cronica.conclude(self.repo, self.f.f.token, self.f.mark())
        world = self.f.world()
        routine = cases.CausalQueueTest().routine("silva_fixture", "a")
        world["pendencias"] = [routine]
        self.f.write(causal.WORLD.as_posix(), world)
        self.assertNotIn(causal.KEY, world)
        plan = consolidar.build_plan(self.repo, "cena")
        self.assertIn(causal.WORLD.as_posix(), plan["outputs"])
        journal = consolidar.stage_plan(self.repo, plan)
        with self.assertRaises(consolidar.ConsolidationError):
            consolidar.install_staged(self.repo, journal, fail_after=1)
        self.assertNotIn(causal.KEY, self.f.world())
        before = self.f.f.hashes()
        with self.assertRaisesRegex(light.LightAgentError, "consolidação interrompida"):
            light.conclude_noop(self.repo, routine["id"], cases.NOTE)
        self.assertEqual(before, self.f.f.hashes())
        self.assertIsNone(light.load_state(self.repo)["agentes"]["silva_fixture"]["cache_negativo"])
        consolidar.resume_consolidation(self.repo)
        restored = self.f.world()["pendencias"]
        self.assertEqual(len(restored), 1)
        self.assertEqual(restored[0]["id"], routine["id"])
        self.assertIn(causal.PENDING_KEY, restored[0])
        self.assertEqual((self.repo / causal.WORLD).read_bytes(), plan["outputs"][causal.WORLD.as_posix()])


if __name__ == "__main__":
    unittest.main()
