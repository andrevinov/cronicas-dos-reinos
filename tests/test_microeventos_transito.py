from __future__ import annotations

import copy
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

import ecologia_local
import microeventos_locais as micro
import microeventos_transito as transit
import pressao_ravens_bluff as pressao


class UrbanTransitRepositoryTest(unittest.TestCase):
    def test_repositorio_real_valida_sem_inicializar_estado(self):
        before = (ROOT / micro.STATE).read_bytes()
        result = transit.validate_repo(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertGreaterEqual(
            result["cartas_basais_elegiveis"], micro.MIN_ELIGIBLE_PER_LOCAL
        )
        self.assertEqual((ROOT / micro.STATE).read_bytes(), before)

    def test_perfil_maximo_permanece_dentro_da_ecologia_existente(self):
        levels = {front_id: 4 for front_id in transit.FRONT_ECOLOGY}
        profile = transit.profile_for_levels(levels)
        self.assertLessEqual(len(profile["tags"]), ecologia_local.MAX_TAGS)
        self.assertLessEqual(
            len(profile["canais_microevento"]), ecologia_local.MAX_CHANNELS
        )
        self.assertEqual(profile["familia"], "transito_urbano")
        self.assertIn("rua_urbana", profile["tags"])
        self.assertIn("transito", profile["canais_microevento"])


class UrbanTransitDeckTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        shutil.copytree(
            ROOT / "narrador/microeventos-locais",
            self.repo / "narrador/microeventos-locais",
        )
        pressure_dir = self.repo / "narrador/arcos/parte_1"
        pressure_dir.mkdir(parents=True)
        shutil.copy2(ROOT / pressao.PROFILE, self.repo / pressao.PROFILE)
        shutil.copy2(ROOT / pressao.STATE, self.repo / pressao.STATE)

    def tearDown(self):
        self.temp.cleanup()

    def _micro_bytes(self) -> bytes:
        return (self.repo / micro.STATE).read_bytes()

    def _pressure_bytes(self) -> bytes:
        return (self.repo / pressao.STATE).read_bytes()

    def _pressure_state(self) -> dict:
        return yaml.safe_load((self.repo / pressao.STATE).read_text(encoding="utf-8"))

    def _write_pressure(self, state: dict) -> None:
        (self.repo / pressao.STATE).write_text(
            yaml.safe_dump(state, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def test_planejamento_e_read_only_e_nao_cria_rua_como_local(self):
        before = self._micro_bytes()
        result = transit.plan(self.repo, scene_id="transit-read-only")
        self.assertEqual(self._micro_bytes(), before)
        self.assertTrue(result["alterou"])
        self.assertFalse(result["confirmado"])
        self.assertEqual(result["publico"]["escopo"], "ravens_bluff")
        state = yaml.safe_load(before.decode("utf-8"))
        self.assertNotIn("transito_ravens_bluff", state["locais"])
        self.assertGreaterEqual(
            result["publico"]["cartas_elegiveis"], micro.MIN_ELIGIBLE_PER_LOCAL
        )

    def test_pressao_muda_pool_sem_mudar_frequencia(self):
        base = transit.plan(self.repo, scene_id="transit-base")["publico"]
        state = self._pressure_state()
        state["frentes"]["custo_de_vida"]["nivel"] = 1
        self._write_pressure(state)
        pressured = transit.plan(self.repo, scene_id="transit-pressure")["publico"]
        self.assertGreater(pressured["cartas_elegiveis"], base["cartas_elegiveis"])
        pressure = pressured["pressao_ravens_bluff"]
        self.assertEqual(pressure["frentes_ativas"], 1)
        self.assertEqual(pressure["max_nivel"], 1)
        self.assertEqual(
            next(item for item in pressure["frentes"] if item["id"] == "custo_de_vida")["nivel"],
            1,
        )
        index = micro.load_index(self.repo)
        results = [item["resultado"] for item in index["ocorrencia"]["fichas"]]
        self.assertEqual(results.count("rotina"), 3)
        self.assertEqual(results.count("microevento"), 1)

    def test_quatro_deslocamentos_confirmados_tem_um_microevento(self):
        pressure_before = self._pressure_bytes()
        original = micro.load_state(self.repo, micro.load_index(self.repo))
        local_state_before = copy.deepcopy(original["locais"])
        local_history_before = copy.deepcopy(original["historico_recente"])
        transit_history_before = copy.deepcopy(original.get(transit.HISTORY_KEY, []))

        results = []
        for i in range(4):
            planned = transit.plan(self.repo, scene_id=f"transit-{i}")
            confirmed = transit.confirm(
                self.repo,
                scene_id=f"transit-{i}",
                expected_fingerprint=planned["fingerprint"],
            )
            results.append(confirmed)

        self.assertEqual(
            sum(item["resultado"] == "avaliar_microevento" for item in results), 1
        )
        after = micro.load_state(self.repo, micro.load_index(self.repo))
        self.assertEqual(after["locais"], local_state_before)
        self.assertEqual(after["historico_recente"], local_history_before)
        self.assertIn(transit.STATE_KEY, after)
        self.assertEqual(
            len(after[transit.HISTORY_KEY]), len(transit_history_before) + 4
        )
        self.assertEqual(self._pressure_bytes(), pressure_before)

    def test_retry_da_mesma_cena_nao_consume_de_novo(self):
        planned = transit.plan(self.repo, scene_id="transit-retry")
        first = transit.confirm(
            self.repo,
            scene_id="transit-retry",
            expected_fingerprint=planned["fingerprint"],
        )
        after_first = self._micro_bytes()
        second = transit.confirm(
            self.repo,
            scene_id="transit-retry",
            expected_fingerprint=planned["fingerprint"],
        )
        self.assertEqual(self._micro_bytes(), after_first)
        self.assertTrue(second["reutilizado"])
        self.assertFalse(second["mutacoes_aplicadas"])
        self.assertEqual(first["resultado"], second["resultado"])
        if "carta" in first:
            self.assertEqual(first["carta"]["id"], second["carta"]["id"])

    def test_mudanca_de_pressao_invalida_preparacao_antes_da_escrita(self):
        planned = transit.plan(self.repo, scene_id="transit-stale")
        micro_before = self._micro_bytes()
        state = self._pressure_state()
        state["frentes"]["crime_e_milicias"]["nivel"] = 1
        self._write_pressure(state)
        with self.assertRaises(transit.TransitMicroeventError):
            transit.revalidate(
                self.repo,
                scene_id="transit-stale",
                expected_fingerprint=planned["fingerprint"],
            )
        self.assertEqual(self._micro_bytes(), micro_before)

    def test_todas_as_frentes_altas_cabem_no_mesmo_catalogo(self):
        index = micro.load_index(self.repo)
        base = transit.profile_for_levels(
            {front_id: 0 for front_id in transit.FRONT_ECOLOGY}
        )
        maxed = transit.profile_for_levels(
            {front_id: 4 for front_id in transit.FRONT_ECOLOGY}
        )
        base_count = len(micro.eligible_cards(index, base))
        maxed_count = len(micro.eligible_cards(index, maxed))
        self.assertGreaterEqual(base_count, micro.MIN_ELIGIBLE_PER_LOCAL)
        self.assertGreaterEqual(maxed_count, base_count)
        self.assertLessEqual(len(maxed["tags"]), ecologia_local.MAX_TAGS)
        self.assertLessEqual(
            len(maxed["canais_microevento"]), ecologia_local.MAX_CHANNELS
        )


if __name__ == "__main__":
    unittest.main()
