from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import checkpoint
import direcoes_mundo
import mundo

FIXTURE = ROOT / "tests/fixtures/mundo-vivo/sessao-008.yaml"


class MundoVivoSnapshotRealTest(unittest.TestCase):
    """Regressão integrada sobre um recorte congelado da campanha real."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.snapshot = yaml.safe_load(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(self.snapshot["schema_snapshot_mundo_vivo"], 1)
        for rel, document in self.snapshot["arquivos"].items():
            self._write_yaml(rel, document)

    def tearDown(self):
        self.temp.cleanup()

    def _write_yaml(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=110),
            encoding="utf-8",
        )

    def _read_yaml(self, rel: str):
        return yaml.safe_load((self.repo / rel).read_text(encoding="utf-8"))

    def _advance_time(self, date: str, hour: str) -> None:
        time = self._read_yaml("estado/tempo.yaml")
        time["data_atual"] = date
        time["hora_aproximada"] = hour
        self._write_yaml("estado/tempo.yaml", time)

    def _pending(self):
        return mundo.load_world_state(self.repo)["pendencias"]

    @staticmethod
    def _of_type(items, kind: str):
        return [item for item in items if item.get("tipo") == kind]

    def test_repo_real_completo_continua_validando_todas_as_camadas(self):
        result = direcoes_mundo.check_repo(ROOT)
        self.assertTrue(result["ok"], result["erros"])

    def test_snapshot_sessao_008_atravessa_dois_amanheceres_de_forma_reprodutivel(self):
        origin = self.snapshot["origem"]
        self.assertEqual(origin["sessao"], 8)
        self.assertEqual(origin["tempo"], "10 Eleasis, 1372 DR 17:42")
        self.assertEqual(origin["nivel_ren"], 6)

        # Primeiro amanhecer após o estado real congelado: a cadência de Shen abre
        # uma janela contextual sem criar pendência bloqueante; três
        # instituições/facções vencem na agenda e o baralho tira rotina.
        self._advance_time("11 Eleasis, 1372 DR", "06:05")
        first = checkpoint.sync_world(self.repo)
        self.assertTrue(first["configurado"])
        self.assertEqual(len(first["novas_pendencias"]), 3)

        pending = self._pending()
        self.assertEqual(len(pending), 3)
        self.assertEqual(
            {item["agente"] for item in self._of_type(pending, "reavaliar_agente")},
            {"red_sail", "night_watch", "casa_de_tyr"},
        )
        self.assertEqual(self._of_type(pending, "avaliar_entrada"), [])
        self.assertEqual(self._of_type(pending, "avaliar_direcao"), [])
        self.assertEqual(self._of_type(pending, "evento_mundial"), [])

        event_state = self._read_yaml("narrador/eventos/estado.yaml")
        self.assertEqual(event_state["ocorrencia"]["ciclo"], 1)
        self.assertEqual(len(event_state["ocorrencia"]["restantes"]), 9)
        self.assertEqual(event_state["eventos"]["ciclo"], 0)
        self.assertEqual(event_state["historico_recente"][0]["ficha_ocorrencia"], "rotina_02")
        self.assertEqual(event_state["historico_recente"][0]["resultado"], "rotina")

        entry_state = self._read_yaml("narrador/entradas/estado.yaml")
        shen = entry_state["candidatos"]["shen_meihua"]
        self.assertIsNone(shen["proxima_avaliacao"])
        self.assertTrue(
            any(
                isinstance(item, dict) and item.get("acao") == "abrir_janela_contextual"
                for item in shen["historico_recente"]
            )
        )
        self.assertEqual(
            mundo.load_world_state(self.repo)["processado_ate"],
            {"data": "11 Eleasis, 1372 DR", "hora": "06:05"},
        )

        # Simula a resolução normal das decisões do primeiro dia antes de avançar.
        for pending_id in [item["id"] for item in self._pending()]:
            mundo.conclude(self.repo, pending_id, "resolvido pelo cenário de regressão")
        self.assertEqual(self._pending(), [])

        # Segundo amanhecer: Ponte vence, Kurobane/Masao entram na agenda e a
        # segunda ficha da urna é evento_03, que sorteia procissao_local.
        self._advance_time("12 Eleasis, 1372 DR", "06:05")
        second = checkpoint.sync_world(self.repo)
        self.assertEqual(len(second["novas_pendencias"]), 6)

        pending = self._pending()
        self.assertEqual(len(pending), 6)
        self.assertEqual(
            {item["agente"] for item in self._of_type(pending, "reavaliar_agente")},
            {"red_sail", "night_watch", "kurobane_jinzaburo", "masao_hirasawa"},
        )
        directions = self._of_type(pending, "avaliar_direcao")
        self.assertEqual([item["direcao"] for item in directions], ["ponte_de_kozakura"])
        self.assertEqual(self._of_type(pending, "avaliar_entrada"), [])
        self.assertEqual(self._of_type(pending, "reavaliar_agente_leve"), [])

        events = self._of_type(pending, "evento_mundial")
        self.assertEqual(len(events), 1)
        event = events[0]
        self.assertEqual(event["evento"], "procissao_local")
        self.assertEqual(event["agentes_afetados"], ["night_watch"])
        self.assertEqual(event["agentes_leves_afetados"], ["luath"])

        event_state = self._read_yaml("narrador/eventos/estado.yaml")
        self.assertEqual(event_state["historico_recente"][1]["ficha_ocorrencia"], "evento_03")
        self.assertEqual(event_state["historico_recente"][1]["resultado"], "evento")
        self.assertEqual(event_state["historico_recente"][1]["evento"], "procissao_local")
        self.assertEqual(event_state["eventos"]["ciclo"], 1)
        self.assertEqual(len(event_state["eventos"]["restantes"]), 9)

        direction_state = self._read_yaml("narrador/direcoes/estado.yaml")
        self.assertEqual(direction_state["direcoes"]["ponte_de_kozakura"]["estado"], "ativa")
        self.assertEqual(
            direction_state["direcoes"]["ponte_de_kozakura"]["marco_atual"],
            "coisas_plausiveis",
        )
        self.assertEqual(
            mundo.load_world_state(self.repo)["processado_ate"],
            {"data": "12 Eleasis, 1372 DR", "hora": "06:05"},
        )

        # Retry no mesmo instante não consome outra carta, não duplica pendência
        # e não avança direção/entrada implicitamente.
        stable_paths = [
            "narrador/mundo/estado.yaml",
            "narrador/eventos/estado.yaml",
            "narrador/entradas/estado.yaml",
            "narrador/agentes-leves/estado.yaml",
            "narrador/direcoes/estado.yaml",
        ]
        before = {rel: (self.repo / rel).read_bytes() for rel in stable_paths}
        third = checkpoint.sync_world(self.repo)
        after = {rel: (self.repo / rel).read_bytes() for rel in stable_paths}
        self.assertEqual(third["novas_pendencias"], [])
        self.assertEqual(before, after)
        self.assertEqual(len(self._pending()), 6)


if __name__ == "__main__":
    unittest.main()
