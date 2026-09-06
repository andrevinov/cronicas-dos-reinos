"""Reservas canônicas acompanham o lifecycle no mesmo checkpoint, sem reescrever ficção."""
from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml

import test_canon_bridge_rewriter as cases
import canon_bridge
import canon_bridge_runtime
import checkpoint
import interacoes_mundo
import mundo
import oportunidades


class CheckpointCanonBridgeTest(cases.Task42Fixture):
    def reserve(self):
        package_base = cases.task41_cases.task40_package()
        candidate = cases._candidate(package_base, set())
        package = cases._package_for(candidate)
        base = cases._instant(candidate["ativacao"])
        deadline = mundo.WorldInstant(base.minute - 60)
        spec = cases._spec_for(
            package, candidate, "candidata_ponte",
            deadline=mundo.instant_parts(deadline),
        )
        mission = self.materialize(package, spec, scene_suffix="checkpoint-reserva")
        canon_bridge_runtime.respond(
            self.repo, mission["mission_id"], "aceitar",
            now=cases._instant(package["prazo_mundo"]["agora"]),
        )
        return candidate, mission["mission_id"], deadline, base

    def set_time(self, current):
        parts = mundo.instant_parts(current)
        time_path = self.repo / mundo.TIME_PATH
        time = yaml.safe_load(time_path.read_text(encoding="utf-8"))
        time["data_atual"] = parts["data"]
        time["data"] = parts["data"]
        time["hora_aproximada"] = parts["hora"]
        time_path.write_text(yaml.safe_dump(time, allow_unicode=True), encoding="utf-8")
        world = mundo.load_world_state(self.repo)
        world["processado_ate"] = parts
        world["pendencias"] = []
        world["concluidas_recentes"] = []
        mundo._atomic_write_yaml(self.repo / mundo.WORLD_STATE_PATH, world)

    def sync(self):
        # Só camadas alheias ao caso são isoladas. Prune, ledger e fallback são reais.
        def process_world(repo):
            self.assertEqual(canon_bridge.load_state(repo)["reservas"], {})
            return {
                "ok": True, "alterou": False,
                "novas_pendencias": [], "agentes_reconsiderar": [],
            }

        with ExitStack() as stack:
            for name in ("_directions_configured", "_reactions_configured", "_operations_configured"):
                stack.enter_context(patch.object(checkpoint, name, return_value=False))
            stack.enter_context(patch.object(checkpoint, "_integration_configured", return_value=True))
            stack.enter_context(patch.object(
                interacoes_mundo, "_canonical_dead_for_profiles", return_value=(set(), [])
            ))
            stack.enter_context(patch.object(mundo, "process_to_canonical", side_effect=process_world))
            return checkpoint.sync_world(self.repo)

    def snapshot(self):
        return {
            path.relative_to(self.repo).as_posix(): path.read_bytes()
            for path in self.repo.rglob("*") if path.is_file()
        }

    def test_checkpoint_expira_missao_e_libera_reserva_antes_do_mundo(self):
        candidate, mission_id, deadline, _ = self.reserve()
        self.set_time(mundo.WorldInstant(deadline.minute + 1))
        canon_before = self.canon_bytes(candidate["evento_id"])
        world_before = (self.repo / mundo.WORLD_STATE_PATH).read_bytes()
        result = self.sync()
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        self.assertEqual(state["missoes"][mission_id]["estado"], "falhada")
        bridge = canon_bridge.load_state(self.repo)
        self.assertEqual(bridge["reservas"], {})
        self.assertEqual(bridge["resolucoes"], {})
        self.assertEqual(bridge["historico_recente"][-1]["motivo"], "lifecycle_falhada")
        self.assertTrue(result["integracao_reativa"]["alterou"])
        self.assertEqual(self.canon_bytes(candidate["evento_id"]), canon_before)
        self.assertEqual((self.repo / mundo.WORLD_STATE_PATH).read_bytes(), world_before)
        before_retry = self.snapshot()
        self.sync()
        self.assertEqual(self.snapshot(), before_retry)

    def test_checkpoint_recupera_reserva_terminal_sem_reencerrar_missao(self):
        candidate, mission_id, deadline, _ = self.reserve()
        current = mundo.WorldInstant(deadline.minute + 1)
        self.set_time(current)
        canon_before = self.canon_bytes(candidate["evento_id"])
        # Interrompe o checkpoint real depois do prune e antes da escrita do bridge.
        with patch.object(
            canon_bridge, "reconcile_lifecycle", side_effect=OSError("queda simulada")
        ):
            with self.assertRaisesRegex(OSError, "queda simulada"):
                self.sync()
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        self.assertEqual(state["missoes"][mission_id]["estado"], "falhada")
        mission_before = (self.repo / oportunidades.STATE).read_bytes()
        self.assertTrue(canon_bridge.load_state(self.repo)["reservas"])
        self.assertEqual(self.canon_bytes(candidate["evento_id"]), canon_before)
        result = self.sync()
        self.assertTrue(result["integracao_reativa"]["alterou"])
        self.assertEqual((self.repo / oportunidades.STATE).read_bytes(), mission_before)
        self.assertEqual(self.canon_bytes(candidate["evento_id"]), canon_before)
        self.assertEqual(canon_bridge.load_state(self.repo)["reservas"], {})
        before_retry = self.snapshot()
        self.sync()
        self.assertEqual(self.snapshot(), before_retry)

    def test_reserva_terminal_restaura_fallback_devido_uma_vez_sem_materializar_evento(self):
        candidate, _, _, base = self.reserve()
        self.set_time(mundo.WorldInstant(base.minute + 1))
        canon_before = self.canon_bytes(candidate["evento_id"])
        self.sync()
        pending = mundo.load_world_state(self.repo)["pendencias"]
        self.assertEqual(len(pending), 1)
        catalog = cases.eventos_canonicos.load_catalog(self.repo)
        schedule_id = catalog["eventos"][candidate["evento_id"]]["agendamento_id"]
        self.assertEqual(pending[0]["origem"], f"agenda:agendamentos.{schedule_id}")
        self.assertEqual(pending[0]["disparado_em"], mundo.instant_parts(base))
        self.assertEqual(canon_bridge.load_state(self.repo)["resolucoes"], {})
        self.assertEqual(self.canon_bytes(candidate["evento_id"]), canon_before)
        before_retry = self.snapshot()
        self.sync()
        self.assertEqual(self.snapshot(), before_retry)


class CheckpointReservationBudgetTest(unittest.TestCase):
    def test_sem_bridge_nao_le_oportunidades_nem_tempo(self):
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(canon_bridge, "load_state") as bridge_load, \
             patch.object(oportunidades, "load_index") as index_load, \
             patch.object(mundo, "load_canonical_time") as time_load:
            self.assertFalse(checkpoint._sync_canonical_reservations(Path(tmp)))
            bridge_load.assert_not_called()
            index_load.assert_not_called()
            time_load.assert_not_called()

    def test_sem_reservas_nao_le_oportunidades_nem_tempo_e_nao_escreve(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            canon_bridge._atomic(repo / canon_bridge.STATE, {
                "schema_canon_bridge": 1, "natureza": "controle_reservado",
                "reservas": {}, "resolucoes": {}, "historico_recente": [],
            })
            before = (repo / canon_bridge.STATE).read_bytes()
            with patch.object(oportunidades, "load_index") as index_load, \
                 patch.object(mundo, "load_canonical_time") as time_load, \
                 patch.object(canon_bridge, "reconcile_lifecycle") as reconcile:
                self.assertFalse(checkpoint._sync_canonical_reservations(repo))
                index_load.assert_not_called()
                time_load.assert_not_called()
                reconcile.assert_not_called()
            self.assertEqual((repo / canon_bridge.STATE).read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
