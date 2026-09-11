from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import clima_diario as climate
import condicoes_mundo
import mundo


class ClimateFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        (self.repo / climate.CONFIG).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / climate.CONFIG, self.repo / climate.CONFIG)
        self.write(climate.STATE, {
            "schema_clima_diario": 1,
            "natureza": "estado_climatico_deterministico",
            "regioes": {
                "ravens_bluff": {
                    "avaliado_ate": "1 Hammer, 1372 DR",
                    "ativo": None,
                    "candidato_extremo": None,
                    "historico_recente": [],
                }
            },
        })
        self.write(mundo.AGENDA_PATH, {"hora_amanhecer": "06:00"})
        self.write(mundo.TIME_PATH, {
            "schema_tempo": 1,
            "data_atual": "1 Hammer, 1372 DR",
            "hora_aproximada": "06:00",
        })
        self.write(condicoes_mundo.STATE, {
            "schema_condicoes_mundo": 1,
            "natureza": "controle_reservado",
            "cidade": "ravens_bluff",
            "condicoes": {},
            "historico_recente": [],
        })

    def write(self, relative, value):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def set_time(self, date, hour="06:00"):
        self.write(mundo.TIME_PATH, {
            "schema_tempo": 1,
            "data_atual": date,
            "hora_aproximada": hour,
        })

    def reset_before(self, date):
        previous = climate._date_from_day(climate._date_day(date) - 1)
        self.write(climate.STATE, {
            "schema_clima_diario": 1,
            "natureza": "estado_climatico_deterministico",
            "regioes": {
                "ravens_bluff": {
                    "avaliado_ate": previous,
                    "ativo": None,
                    "candidato_extremo": None,
                    "historico_recente": [],
                }
            },
        })
        self.write(condicoes_mundo.STATE, {
            "schema_condicoes_mundo": 1,
            "natureza": "controle_reservado",
            "cidade": "ravens_bluff",
            "condicoes": {},
            "historico_recente": [],
        })
        self.set_time(date)

    def find(self, predicate):
        start = climate._date_day("1 Hammer, 1372 DR")
        for offset in range(1, 800):
            date = climate._date_from_day(start + offset)
            record = climate.draw_for_date(self.repo, date=date)
            if predicate(record):
                return date, record
        self.fail("nenhuma data sintética satisfez o predicado")


class DeterministicWeatherDeckTest(ClimateFixture):
    def test_mesma_data_regiao_produz_exatamente_o_mesmo_resultado(self):
        first = climate.draw_for_date(self.repo, date="12 Ches, 1372 DR")
        second = climate.draw_for_date(self.repo, date="12 Ches, 1372 DR")
        self.assertEqual(first, second)
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual(len(first["seed_sha256"]), 64)

    def test_decks_mantem_chuva_vento_plausiveis_e_extremos_raros(self):
        config = climate.load_config(self.repo)
        states = config["estados"]
        for season, slots in config["regioes"]["ravens_bluff"]["decks"].items():
            with self.subTest(season=season):
                extremes = [item for item in slots if states[item]["extremo"]]
                ordinary = [
                    item for item in slots
                    if states[item]["familia"] in {"chuva", "vento"} and not states[item]["extremo"]
                ]
                self.assertEqual(len(slots), 32)
                self.assertEqual(extremes.count("vendaval"), 1)
                self.assertEqual(len(extremes), 2)
                self.assertGreaterEqual(len(ordinary), 8)

    def test_chuva_e_vendaval_sao_possiveis_sem_autoria_manual(self):
        rain_date, rain = self.find(lambda row: row["estado"] in {"chuva_leve", "chuva_forte"})
        gale_date, gale = self.find(lambda row: row["estado"] == "vendaval")
        self.assertNotEqual(rain_date, gale_date)
        self.assertFalse(rain["extremo"])
        self.assertTrue(gale["extremo"])


class DawnLifecycleTest(ClimateFixture):
    def test_clima_comum_ativa_uma_vez_e_materializa_condicao_existente(self):
        date, expected = self.find(lambda row: not row["extremo"] and row["estado"] == "chuva_leve")
        self.reset_before(date)
        first = climate.sync_dawn(self.repo)
        self.assertEqual(len(first["avaliacoes"]), 1)
        state = climate.load_state(self.repo)
        self.assertEqual(state["regioes"]["ravens_bluff"]["ativo"]["id"], expected["id"])
        conditions = condicoes_mundo.load_state(self.repo)
        self.assertIn(expected["condicao_id"], conditions["condicoes"])
        self.assertIn("chuva", conditions["condicoes"][expected["condicao_id"]]["marcadores"])

        state_bytes = (self.repo / climate.STATE).read_bytes()
        condition_bytes = (self.repo / condicoes_mundo.STATE).read_bytes()
        second = climate.sync_dawn(self.repo)
        self.assertEqual(second["avaliacoes"], [])
        self.assertEqual((self.repo / climate.STATE).read_bytes(), state_bytes)
        self.assertEqual((self.repo / condicoes_mundo.STATE).read_bytes(), condition_bytes)

    def test_extremo_fica_candidato_estavel_ate_confirmacao(self):
        date, expected = self.find(lambda row: row["estado"] == "vendaval")
        self.reset_before(date)
        first = climate.sync_dawn(self.repo)
        self.assertEqual(first["candidatos_extremos"][0]["id"], expected["id"])
        state = climate.load_state(self.repo)
        self.assertIsNone(state["regioes"]["ravens_bluff"]["ativo"])
        self.assertEqual(state["regioes"]["ravens_bluff"]["candidato_extremo"], expected)
        self.assertNotIn(expected["condicao_id"], condicoes_mundo.load_state(self.repo)["condicoes"])

        before = (self.repo / climate.STATE).read_bytes()
        retry = climate.sync_dawn(self.repo)
        self.assertEqual((self.repo / climate.STATE).read_bytes(), before)
        self.assertEqual(retry["candidatos_extremos"][0]["fingerprint"], expected["fingerprint"])

        confirmed = climate.confirm_extreme(
            self.repo, candidate_id=expected["id"], expected_fingerprint=expected["fingerprint"]
        )
        self.assertEqual(confirmed["resultado"], "confirmado")
        after = climate.load_state(self.repo)["regioes"]["ravens_bluff"]
        self.assertIsNone(after["candidato_extremo"])
        self.assertEqual(after["ativo"]["efeitos"], expected["efeitos"])
        self.assertIn(expected["condicao_id"], condicoes_mundo.load_state(self.repo)["condicoes"])
        again = climate.confirm_extreme(
            self.repo, candidate_id=expected["id"], expected_fingerprint=expected["fingerprint"]
        )
        self.assertTrue(again["reutilizado"])

    def test_cena_so_le_estado_ativo_sem_abrir_deck_ou_escrever(self):
        date, expected = self.find(lambda row: not row["extremo"])
        self.reset_before(date)
        climate.sync_dawn(self.repo)
        before = {path: (self.repo / path).read_bytes() for path in (climate.STATE, climate.CONFIG)}
        now = mundo.parse_instant(date, "06:30")
        first = climate.for_scene(self.repo, "circo_mooney", now=now)
        second = climate.for_scene(self.repo, "circo_mooney", now=now)
        self.assertEqual(first, second)
        self.assertEqual(first["ativo"]["id"], expected["id"])
        self.assertIn("sensorial", first["ativo"])
        self.assertIn("espacos", first["ativo"])
        self.assertEqual(before, {path: (self.repo / path).read_bytes() for path in before})


if __name__ == "__main__":
    unittest.main()
