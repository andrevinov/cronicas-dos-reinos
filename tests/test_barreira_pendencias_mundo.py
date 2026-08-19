from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import barreira_mundo
import mundo
import transacoes

TURN_PATH = TOOLS / "turno.py"
spec = importlib.util.spec_from_file_location("turno_barreira_mundo", TURN_PATH)
turno = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(turno)


PENDING_ID = "mundo-1111111111111111"


class BarreiraPendenciasMundoSyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "runtime").mkdir(parents=True)
        (self.repo / "sessoes/003").mkdir(parents=True)
        (self.repo / "narrador/mundo").mkdir(parents=True)
        self._yaml(
            "runtime/contexto.yaml",
            {"sessao": {"numero": 3, "status": "em_sessao"}},
        )
        (self.repo / "runtime/eventos-pendentes.jsonl").write_text("", encoding="utf-8")
        (self.repo / "sessoes/003/transcricao.md").write_text("# Sessão 003\n", encoding="utf-8")
        self.write_world_state([])

    def tearDown(self):
        self.temp.cleanup()

    def _yaml(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def pending(self, pending_id: str = PENDING_ID) -> dict:
        return {
            "id": pending_id,
            "tipo": "reavaliar_agente",
            "agente": "red_sail",
            "agentes_afetados": ["red_sail"],
            "disparado_em": {"data": "11 Eleasis, 1372 DR", "hora": "06:00"},
            "motivo": "Avaliar uma iniciativa sem fazê-la acontecer automaticamente.",
            "origem": "agenda:reavaliacoes.red_sail",
        }

    def write_world_state(self, pending: list[dict]) -> None:
        self._yaml(
            "narrador/mundo/estado.yaml",
            {
                "schema_estado_mundo": 1,
                "natureza": "controle_reservado",
                "processado_ate": {"data": "11 Eleasis, 1372 DR", "hora": "15:30"},
                "pendencias": pending,
                "concluidas_recentes": [],
            },
        )

    def tx(self, *, player: bool = True, tags=None, mode="interação") -> dict:
        result = {
            "narracao": "O estado do mundo é resolvido de forma rastreável.",
            "resumo": "Uma avaliação é resolvida.",
            "modo": mode,
            "deltas": [],
        }
        if player:
            result["jogador"] = "Ren tenta continuar sua ação."
        if tags is not None:
            result["tags"] = tags
        return result

    def test_sync_bloqueia_com_payload_minimo(self):
        self.write_world_state([self.pending()])
        result = barreira_mundo.sync(self.repo)
        self.assertTrue(result["bloqueado"])
        self.assertEqual(result["quantidade"], 1)
        self.assertEqual(
            result["disparo_mais_antigo"],
            {"data": "11 Eleasis, 1372 DR", "hora": "06:00"},
        )
        marker = self.repo / barreira_mundo.BARRIER_PATH
        self.assertLess(marker.stat().st_size, 512)
        self.assertEqual(
            result["fontes_lidas"],
            [mundo.WORLD_STATE_PATH.as_posix(), barreira_mundo.BARRIER_PATH.as_posix()],
        )

    def test_sync_libera_quando_fila_esta_vazia(self):
        result = barreira_mundo.sync(self.repo)
        self.assertFalse(result["bloqueado"])
        self.assertEqual(result["quantidade"], 0)
        self.assertIsNone(result["disparo_mais_antigo"])

    def test_turno_novo_e_bloqueado_antes_de_qualquer_escrita(self):
        self.write_world_state([self.pending()])
        barreira_mundo.sync(self.repo)
        transcript = self.repo / "sessoes/003/transcricao.md"
        pending = self.repo / "runtime/eventos-pendentes.jsonl"
        before_transcript = transcript.read_bytes()
        before_pending = pending.read_bytes()

        with self.assertRaises(transacoes.TransactionError) as ctx:
            turno.register_transaction(self.repo, self.tx())

        self.assertIn("pendência(s) não resolvida(s)", str(ctx.exception))
        self.assertEqual(transcript.read_bytes(), before_transcript)
        self.assertEqual(pending.read_bytes(), before_pending)

    def test_retry_parcial_continua_permitido_mesmo_bloqueado(self):
        self.write_world_state([self.pending()])
        barreira_mundo.sync(self.repo)
        normalized, session = turno.normalize_transaction(self.repo, self.tx())
        record = transacoes.build_pending_record(normalized, session)
        (self.repo / "runtime/eventos-pendentes.jsonl").write_text(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )

        result = turno.register_transaction(self.repo, normalized)

        self.assertTrue(result["reparo_parcial"])
        self.assertTrue(result["transcricao_escrita"])
        self.assertFalse(result["evento_escrito"])

    def test_resolucao_explicita_sem_jogador_forca_checkpoint(self):
        self.write_world_state([self.pending()])
        barreira_mundo.sync(self.repo)
        tx = self.tx(
            player=False,
            mode="mundo",
            tags=[f"{barreira_mundo.RESOLUTION_TAG_PREFIX}{PENDING_ID}"],
        )
        fake_checkpoint = {
            "canonico": {"tipo": "cena"},
            "mundo": {
                "configurado": True,
                "novas_pendencias": [],
                "agentes_reconsiderar": [],
            },
        }
        with patch.object(turno, "_run_scene_checkpoint", return_value=fake_checkpoint) as run:
            result = turno.register_transaction(self.repo, tx)

        run.assert_called_once_with(self.repo)
        self.assertEqual(result["pendencia_mundo"], PENDING_ID)
        self.assertTrue(result["checkpoint_mundo"]["disparado"])
        self.assertEqual(
            result["checkpoint_mundo"]["motivo"],
            "resolucao_pendencia_mundo",
        )

    def test_resolucao_errada_ou_com_acao_de_ren_e_rejeitada(self):
        self.write_world_state([self.pending()])
        barreira_mundo.sync(self.repo)
        wrong = self.tx(
            player=False,
            mode="mundo",
            tags=[f"{barreira_mundo.RESOLUTION_TAG_PREFIX}mundo-2222222222222222"],
        )
        with self.assertRaises(transacoes.TransactionError):
            turno.register_transaction(self.repo, wrong)

        with_player = self.tx(
            player=True,
            mode="mundo",
            tags=[f"{barreira_mundo.RESOLUTION_TAG_PREFIX}{PENDING_ID}"],
        )
        with self.assertRaises(transacoes.TransactionError) as ctx:
            turno.register_transaction(self.repo, with_player)
        self.assertIn("não pode carregar nova ação do jogador", str(ctx.exception))

    def test_concluir_remove_pendencia_e_libera_barreira(self):
        self.write_world_state([self.pending()])
        barreira_mundo.sync(self.repo)

        result = barreira_mundo.conclude(self.repo, PENDING_ID, "avaliado sem mudança")

        self.assertEqual(result["pendencias_restantes"], 0)
        self.assertFalse(result["barreira"]["bloqueado"])
        self.assertEqual(result["barreira"]["quantidade"], 0)
        self.assertEqual(mundo.load_world_state(self.repo)["pendencias"], [])

    def test_marcador_bloqueado_stale_se_autorrepara(self):
        self.write_world_state([self.pending()])
        barreira_mundo.sync(self.repo)
        self.write_world_state([])

        auth = barreira_mundo.authorize_registration(
            self.repo,
            self.tx(),
            retry=False,
        )

        self.assertTrue(auth["ok"])
        self.assertFalse(auth["barreira"]["bloqueado"])
        self.assertFalse(barreira_mundo.load_status(self.repo)["bloqueado"])

    def test_hot_path_livre_le_somente_marcador(self):
        barreira_mundo.sync(self.repo)
        auth = barreira_mundo.authorize_registration(
            self.repo,
            self.tx(),
            retry=False,
        )
        self.assertEqual(
            auth["barreira"]["fontes_lidas"],
            [barreira_mundo.BARRIER_PATH.as_posix()],
        )


class BarreiraPendenciasMundoRepositoryTest(unittest.TestCase):
    def test_marcador_real_corresponde_a_fila_real_sem_fixar_quantidade(self):
        state = mundo.load_world_state(ROOT)
        status = barreira_mundo.load_status(ROOT)
        self.assertTrue(status["configurado"])
        self.assertEqual(status["quantidade"], len(state["pendencias"]))
        self.assertEqual(status["bloqueado"], bool(state["pendencias"]))
        self.assertTrue(barreira_mundo.check(ROOT)["ok"])


if __name__ == "__main__":
    unittest.main()
