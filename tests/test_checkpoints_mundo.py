from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

TURN_PATH = TOOLS / "turno.py"
spec = importlib.util.spec_from_file_location("turno_checkpoint_mundo", TURN_PATH)
turno = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(turno)

import checkpoint
import transacoes


class TemporalCheckpointTurnTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "runtime").mkdir(parents=True)
        (self.repo / "sessoes/003").mkdir(parents=True)
        (self.repo / "estado").mkdir(parents=True)
        (self.repo / "narrador/mundo").mkdir(parents=True)
        (self.repo / "runtime/contexto.yaml").write_text(
            "sessao:\n  numero: 3\n  status: em_sessao\n", encoding="utf-8"
        )
        (self.repo / "runtime/eventos-pendentes.jsonl").write_text("", encoding="utf-8")
        (self.repo / "sessoes/003/transcricao.md").write_text("# Sessão 003\n", encoding="utf-8")
        self._yaml(
            "estado/tempo.yaml",
            {
                "schema_tempo": 1,
                "natureza": "tempo_atual",
                "data_atual": "10 Eleasis, 1372 DR",
                "hora_aproximada": "17:42 de 10 Eleasis",
            },
        )
        self._yaml(
            "narrador/mundo/agenda.yaml",
            {
                "schema_agenda_mundo": 1,
                "natureza": "reservado",
                "hora_amanhecer": "06:00",
                "reavaliacoes": {},
                "agendamentos": [],
            },
        )
        self._yaml(
            "narrador/mundo/estado.yaml",
            {
                "schema_estado_mundo": 1,
                "natureza": "controle_reservado",
                "processado_ate": {"data": "10 Eleasis, 1372 DR", "hora": "17:42"},
                "pendencias": [],
                "concluidas_recentes": [],
            },
        )

    def tearDown(self):
        self.temp.cleanup()

    def _yaml(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def tx(self, hour: str, *, mode: str = "exploração", extra_deltas=None):
        deltas = [
            {"alvo": "tempo", "op": "set", "caminho": "hora_aproximada", "valor": hour}
        ]
        deltas.extend(extra_deltas or [])
        return {
            "jogador": "Ren continua sua ação.",
            "narracao": "O tempo passa enquanto Ren prossegue.",
            "resumo": f"O tempo avança até {hour}.",
            "modo": mode,
            "deltas": deltas,
        }

    def test_cinco_minutos_nao_disparam_checkpoint(self):
        record = transacoes.build_pending_record(self.tx("17:47 de 10 Eleasis"), 3)
        trigger = turno.detect_world_checkpoint(self.repo, [], record)
        self.assertIsNone(trigger)

    def test_duas_horas_acumuladas_disparam_checkpoint(self):
        prior = transacoes.build_pending_record(self.tx("18:42 de 10 Eleasis"), 3)
        current = transacoes.build_pending_record(
            {**self.tx("19:42 de 10 Eleasis"), "id": "segundo-avanco"},
            3,
        )
        trigger = turno.detect_world_checkpoint(self.repo, [prior], current)
        self.assertIsNotNone(trigger)
        self.assertEqual(trigger["motivo"], "passagem_horas")
        self.assertEqual(trigger["minutos_desde_checkpoint"], 120)

    def test_cruzar_amanhecer_dispara_mesmo_com_menos_de_duas_horas(self):
        self._yaml(
            "estado/tempo.yaml",
            {
                "schema_tempo": 1,
                "natureza": "tempo_atual",
                "data_atual": "11 Eleasis, 1372 DR",
                "hora_aproximada": "05:30 de 11 Eleasis",
            },
        )
        self._yaml(
            "narrador/mundo/estado.yaml",
            {
                "schema_estado_mundo": 1,
                "natureza": "controle_reservado",
                "processado_ate": {"data": "11 Eleasis, 1372 DR", "hora": "05:30"},
                "pendencias": [],
                "concluidas_recentes": [],
            },
        )
        record = transacoes.build_pending_record(self.tx("06:10 de 11 Eleasis"), 3)
        trigger = turno.detect_world_checkpoint(self.repo, [], record)
        self.assertIsNotNone(trigger)
        self.assertEqual(trigger["motivo"], "amanhecer")
        self.assertEqual(trigger["minutos_desde_checkpoint"], 40)

    def test_viagem_longa_e_classificada_quando_localizacao_muda(self):
        record = transacoes.build_pending_record(
            self.tx(
                "20:00 de 10 Eleasis",
                extra_deltas=[
                    {
                        "alvo": "estado",
                        "op": "set",
                        "caminho": "localizacao.area",
                        "valor": "Calaunt Road",
                    }
                ],
            ),
            3,
        )
        trigger = turno.detect_world_checkpoint(self.repo, [], record)
        self.assertEqual(trigger["motivo"], "viagem_longa")

    def test_turno_significativo_chama_checkpoint_de_cena(self):
        with patch.object(
            turno,
            "_run_scene_checkpoint",
            return_value={
                "canonico": {"tipo": "cena"},
                "mundo": {"configurado": True, "novas_pendencias": [], "agentes_reconsiderar": []},
            },
        ) as run:
            result = turno.register_transaction(self.repo, self.tx("19:42 de 10 Eleasis"))
        run.assert_called_once_with(self.repo)
        self.assertTrue(result["checkpoint_mundo"]["disparado"])
        self.assertEqual(result["checkpoint_mundo"]["motivo"], "passagem_horas")

    def test_reexecucao_de_turno_ja_consolidado_nao_recoloca_evento(self):
        tx = self.tx("19:42 de 10 Eleasis")
        normalized, session = turno.normalize_transaction(self.repo, tx)
        record = transacoes.build_pending_record(normalized, session)
        marker = transacoes.transaction_marker(record["id"])
        (self.repo / "sessoes/003/transcricao.md").write_text(
            f"# Sessão 003\n\n{marker}\n**Narrador**\n\ntexto\n", encoding="utf-8"
        )
        ledger = {"id": "batch-1", "transacoes": [record["id"]]}
        (self.repo / "sessoes/003/consolidacoes.jsonl").write_text(
            json.dumps(ledger, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        result = turno.register_transaction(self.repo, tx)
        self.assertTrue(result["consolidada"])
        self.assertTrue(result["ja_registrada"])
        self.assertEqual((self.repo / "runtime/eventos-pendentes.jsonl").read_text(encoding="utf-8"), "")


class CheckpointWorldIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "runtime").mkdir(parents=True)
        (self.repo / "sessoes/003").mkdir(parents=True)
        self._yaml(
            "runtime/contexto.yaml",
            {
                "sessao": {"numero": 3, "status": "em_sessao", "modo_de_cena": "exploração"},
                "personagem": {"nome": "Ren", "nivel": 6},
                "recursos": {"pv": {"atuais": 45, "maximos": 45}, "ki": {"atuais": 6, "maximos": 6}, "ca": 17},
                "tempo": {"data": "10 Eleasis, 1372 DR", "hora_aproximada": "17:42"},
                "localizacao": {"cidade": "Ravens Bluff", "area": "circo", "ponto_exato": "depósito"},
            },
        )
        self._yaml("runtime/cena.yaml", {"sessao": 3, "modo": "exploração"})
        (self.repo / "runtime/eventos-pendentes.jsonl").write_text("", encoding="utf-8")
        (self.repo / "sessoes/003/transcricao.md").write_text("# Sessão 003\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def _yaml(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def test_checkpoint_de_cena_sincroniza_mundo_depois_do_canone(self):
        order = []

        def consolidate(repo, kind):
            order.append("canonico")
            return {"sessao": 3, "tipo": kind, "sem_pendencias": True}

        def sync(repo):
            order.append("mundo")
            return {"configurado": True, "alterou": False, "novas_pendencias": []}

        with patch.object(checkpoint.consolidar, "consolidate", side_effect=consolidate), patch.object(
            checkpoint, "sync_world", side_effect=sync
        ):
            result = checkpoint.checkpoint(self.repo, "cena")
        self.assertEqual(order[:2], ["canonico", "mundo"])
        self.assertTrue(result["mundo"]["configurado"])

    def test_checkpoint_de_sessao_tambem_sincroniza_mundo(self):
        fake = {"sessao": 3, "tipo": "sessao", "sem_pendencias": True}
        with patch.object(checkpoint.consolidar, "consolidate", return_value=fake), patch.object(
            checkpoint.ciclo_sessoes,
            "encerrar",
            return_value={"status": "entre_sessoes"},
        ), patch.object(
            checkpoint,
            "sync_world",
            return_value={"configurado": True, "alterou": False, "novas_pendencias": []},
        ) as sync:
            result = checkpoint.checkpoint(self.repo, "sessao")
        sync.assert_called_once_with(self.repo)
        self.assertTrue(result["mundo"]["configurado"])

    def test_checkpoint_sem_motor_configurado_continua_compativel(self):
        result = checkpoint.sync_world(self.repo)
        self.assertFalse(result["configurado"])


if __name__ == "__main__":
    unittest.main()
