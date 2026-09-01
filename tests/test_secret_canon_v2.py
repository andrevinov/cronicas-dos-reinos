from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import eventos_canonicos
import mundo


class SecretCanonV2RepositoryTest(unittest.TestCase):
    def setUp(self):
        self.catalog = eventos_canonicos.load_catalog(ROOT)
        self.secret = self.catalog["secret_canon_v2"]
        self.frontier = mundo.parse_instant(
            self.secret["fronteira_autoral"]["data"],
            self.secret["fronteira_autoral"]["hora"],
        )
        self.frozen = set(self.secret["passado_congelado"])
        self.future = [
            event_id
            for event_id in self.catalog["eventos"]
            if event_id not in self.frozen
        ]

    def test_fronteira_separa_passado_congelado_e_futuro_editavel(self):
        self.assertEqual(len(self.frozen), 1)
        self.assertEqual(len(self.future), 20)
        for event_id in self.frozen:
            event = eventos_canonicos.load_event(
                ROOT, event_id, catalog=self.catalog
            )
            instant = mundo.parse_instant(
                event["ativacao"]["data"], event["ativacao"]["hora"]
            )
            self.assertLessEqual(instant.minute, self.frontier.minute)
            self.assertEqual(
                eventos_canonicos.event_digest(event),
                self.secret["passado_congelado"][event_id],
            )
        for event_id in self.future:
            event = eventos_canonicos.load_event(
                ROOT, event_id, catalog=self.catalog
            )
            instant = mundo.parse_instant(
                event["ativacao"]["data"], event["ativacao"]["hora"]
            )
            self.assertGreater(instant.minute, self.frontier.minute)

    def test_futuro_tem_cobertura_dramatica_sem_resultado_automatico(self):
        controlled = set(self.secret["categorias_controladas"])
        required = set(self.secret["cobertura_obrigatoria"])
        coverage: set[str] = set()
        forbidden = {
            "resultado_obrigatorio",
            "acao_de_ren_obrigatoria",
            "recompensa_automatica",
            "neutralizacao_automatica",
            "conhecimento_automatico_de_ren",
        }
        for event_id in self.future:
            event = eventos_canonicos.load_event(
                ROOT, event_id, catalog=self.catalog
            )
            categories = set(event["categorias"])
            self.assertTrue(categories)
            self.assertTrue(categories <= controlled)
            self.assertTrue(event["adaptacao"])
            self.assertFalse(forbidden & set(event))
            coverage.update(categories)
        self.assertTrue(required <= coverage)

    def test_datas_futuras_tem_folga_e_nao_formam_rajada_diaria(self):
        instants = sorted(
            (
                mundo.parse_instant(
                    event["ativacao"]["data"], event["ativacao"]["hora"]
                ).minute,
                event_id,
            )
            for event_id in self.future
            for event in [
                eventos_canonicos.load_event(
                    ROOT, event_id, catalog=self.catalog
                )
            ]
        )
        self.assertEqual(len({minute for minute, _ in instants}), len(instants))
        for (left, _), (right, _) in zip(instants, instants[1:]):
            self.assertGreaterEqual(right - left, 24 * 60)
        self.assertGreaterEqual(instants[-1][0] - instants[0][0], 30 * 24 * 60)

    def test_indice_e_fragmentos_respeitam_orcamento(self):
        budget = yaml.safe_load(
            (ROOT / "baseline/secret-canon-v2-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        limits = budget["limites"]
        self.assertLessEqual(
            (ROOT / eventos_canonicos.CATALOG).stat().st_size,
            limits["indice_bytes_max"],
        )
        for event_id, raw in self.catalog["eventos"].items():
            self.assertLessEqual(
                (ROOT / raw["fragmento"]).stat().st_size,
                limits["fragmento_bytes_max"],
                event_id,
            )
        self.assertEqual(limits["eventos_total"], 21)
        self.assertEqual(limits["eventos_passado_congelados"], 1)
        self.assertEqual(limits["eventos_futuros"], 20)
        self.assertEqual(limits["leituras_fragmentos_turno_sem_evento"], 0)
        self.assertEqual(limits["leituras_fragmento_evento_devido_max"], 1)
        self.assertEqual(limits["schedulers_novos"], 0)
        self.assertEqual(limits["estados_novos"], 0)
        self.assertEqual(limits["rng_novo"], 0)
        self.assertTrue(all(budget["invariantes"].values()))

    def test_lookup_de_um_evento_abre_indice_e_um_fragmento(self):
        event_id = self.future[0]
        schedule_id = self.catalog["eventos"][event_id]["agendamento_id"]
        pending = {
            "origem": eventos_canonicos.SCHEDULE_ORIGIN_PREFIX + schedule_id
        }
        original = eventos_canonicos._load
        opened: list[Path] = []

        def tracked(path: Path):
            opened.append(path.relative_to(ROOT))
            return original(path)

        with patch.object(eventos_canonicos, "_load", side_effect=tracked):
            event = eventos_canonicos.event_for_pending(ROOT, pending)

        self.assertEqual(event["id"], event_id)
        self.assertEqual(opened[0], eventos_canonicos.CATALOG)
        self.assertEqual(len(opened), 2)
        self.assertEqual(
            opened[1].as_posix(),
            self.catalog["eventos"][event_id]["fragmento"],
        )

    def test_catalogo_nao_implementa_a_task37(self):
        all_text = "\n".join(
            (ROOT / self.catalog["eventos"][event_id]["fragmento"]).read_text(
                encoding="utf-8"
            )
            for event_id in self.future
        ).casefold()
        self.assertNotIn("torneio clandestino", all_text)
        self.assertNotIn("underground tournament", all_text)

    def test_documentacao_publica_nao_vaza_detalhes_futuros(self):
        public = (
            (ROOT / "docs/task36-secret-canon-v2.md").read_text(encoding="utf-8")
            + "\n"
            + (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        )
        for event_id in self.future:
            event = eventos_canonicos.load_event(
                ROOT, event_id, catalog=self.catalog
            )
            self.assertNotIn(event_id, public)
            self.assertNotIn(event["titulo"], public)
        self.assertLessEqual((ROOT / "AGENTS.md").stat().st_size, 13312)


if __name__ == "__main__":
    unittest.main()
