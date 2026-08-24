from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import barreira_mundo
import cronica
import cronica_pending_gate
import mundo


PENDING_ID = "mundo-1111111111111111"


class CronicaPendingGateTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "runtime").mkdir(parents=True)
        (self.repo / "narrador/mundo").mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def _write_yaml(self, rel: str, data) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _world(self, pending: list[dict]) -> None:
        self._write_yaml(
            mundo.WORLD_STATE_PATH.as_posix(),
            {
                "schema_estado_mundo": 1,
                "natureza": "controle_reservado",
                "processado_ate": {"data": "17 Eleasis, 1372 DR", "hora": "06:00"},
                "pendencias": pending,
                "concluidas_recentes": [],
            },
        )

    def _pending(self) -> dict:
        return {
            "id": PENDING_ID,
            "tipo": "reavaliar_agente",
            "agente": "red_sail",
            "disparado_em": {"data": "17 Eleasis, 1372 DR", "hora": "06:00"},
            "motivo": "reavaliar plano sem transformar cadência em ação automática",
            "origem": "fixture",
        }

    def _marker(self, *, blocked: bool, quantity: int, oldest=None) -> None:
        self._write_yaml(
            barreira_mundo.BARRIER_PATH.as_posix(),
            {
                "schema_barreira_mundo": 1,
                "natureza": "runtime_derivado",
                "bloqueado": blocked,
                "quantidade": quantity,
                "disparo_mais_antigo": oldest,
            },
        )

    def test_caminho_livre_preserva_saida_byte_logica_da_preparacao(self):
        self._marker(blocked=False, quantity=0, oldest=None)
        expected = cronica._hot.prepare(self.repo, scene_id="s024-livre")
        actual = cronica.prepare(self.repo, scene_id="s024-livre")
        self.assertEqual(actual, expected)
        self.assertIn("ticket", actual)
        self.assertEqual(actual["fontes_lidas"], [])

    def test_bloqueio_vem_antes_do_hotpath_e_nao_emite_ticket(self):
        oldest = {"data": "17 Eleasis, 1372 DR", "hora": "06:00"}
        self._marker(blocked=True, quantity=1, oldest=oldest)
        self._world([self._pending()])
        marker_before = (self.repo / barreira_mundo.BARRIER_PATH).read_bytes()
        world_before = (self.repo / mundo.WORLD_STATE_PATH).read_bytes()

        with mock.patch.object(cronica._hot, "prepare") as hot:
            result = cronica.prepare(
                self.repo,
                scene_id="s024-bloqueada",
                place="incompleto",
                urban_transit="ravens_bluff",
            )

        hot.assert_not_called()
        self.assertEqual(result["fase"], "bloqueada_pendencias_mundo")
        self.assertFalse(result["ticket_emitido"])
        self.assertNotIn("ticket", result)
        self.assertNotIn("contrato_conclusao", result)
        self.assertFalse(result["disponibilidade"]["narracao"])
        self.assertEqual(result["barreira"]["quantidade"], 1)
        self.assertIn("resolver_fronteira.py preparar", result["proximo_passo"]["comando"])
        self.assertEqual(
            result["fontes_lidas"],
            [
                barreira_mundo.BARRIER_PATH.as_posix(),
                mundo.WORLD_STATE_PATH.as_posix(),
            ],
        )
        self.assertEqual((self.repo / barreira_mundo.BARRIER_PATH).read_bytes(), marker_before)
        self.assertEqual((self.repo / mundo.WORLD_STATE_PATH).read_bytes(), world_before)

    def test_marcador_bloqueado_stale_nao_cria_deadlock_nem_escreve(self):
        oldest = {"data": "17 Eleasis, 1372 DR", "hora": "06:00"}
        self._marker(blocked=True, quantity=1, oldest=oldest)
        self._world([])
        marker_path = self.repo / barreira_mundo.BARRIER_PATH
        before = marker_path.read_bytes()

        inspected = cronica_pending_gate.inspect_read_only(self.repo)
        self.assertFalse(inspected["bloqueado"])
        self.assertTrue(inspected["marcador_stale"])
        self.assertTrue(inspected["autoritativo_confirmado"])
        self.assertEqual(marker_path.read_bytes(), before)

        expected = cronica._hot.prepare(self.repo, scene_id="s024-stale")
        actual = cronica.prepare(self.repo, scene_id="s024-stale")
        self.assertEqual(actual, expected)
        self.assertEqual(marker_path.read_bytes(), before)

    def test_marcador_livre_nao_abre_estado_autoritativo(self):
        self._marker(blocked=False, quantity=0, oldest=None)
        with mock.patch.object(cronica_pending_gate.mundo, "load_world_state") as load_state:
            result = cronica_pending_gate.inspect_read_only(self.repo)
        load_state.assert_not_called()
        self.assertFalse(result["bloqueado"])
        self.assertEqual(result["fontes_lidas"], [barreira_mundo.BARRIER_PATH.as_posix()])

    def test_resposta_bloqueada_fica_no_orcamento_compacto(self):
        oldest = {"data": "17 Eleasis, 1372 DR", "hora": "06:00"}
        self._marker(blocked=True, quantity=1, oldest=oldest)
        self._world([self._pending()])
        result = cronica_pending_gate.prepare_gate(self.repo)
        self.assertIsNotNone(result)
        size = len(yaml.safe_dump(result, allow_unicode=True, sort_keys=False).encode("utf-8"))
        self.assertLessEqual(size, cronica_pending_gate.MAX_BLOCKED_OUTPUT_BYTES)
        self.assertLessEqual(size, cronica.MAX_PREP_OUTPUT_BYTES)

    def test_cli_preparar_bloqueado_retorna_gate_com_exit_zero(self):
        oldest = {"data": "17 Eleasis, 1372 DR", "hora": "06:00"}
        self._marker(blocked=True, quantity=1, oldest=oldest)
        self._world([self._pending()])
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = cronica.main(
                ["--repo", str(self.repo), "preparar", "--cena-id", "s024-cli"]
            )
        self.assertEqual(code, 0)
        result = yaml.safe_load(stdout.getvalue())
        self.assertEqual(result["fase"], "bloqueada_pendencias_mundo")
        self.assertFalse(result["ticket_emitido"])


if __name__ == "__main__":
    unittest.main()
