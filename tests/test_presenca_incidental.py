from __future__ import annotations

import copy
import shutil
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

import cena_mundo
import contexto_cena
import ecologia_local
import mundo
import presenca_incidental as incidental


class IncidentalPresenceContractTest(unittest.TestCase):
    def test_bundle_real_tem_cinco_perfis_ancorados_e_validos(self):
        result = incidental.validate(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["perfis"], 5)
        index = incidental.load_index(ROOT)
        self.assertEqual(
            set(index["perfis"]),
            {"kethra_dunn", "bram_vask", "silva_elkwood", "jack_mooney", "halessa_vorn"},
        )

    def test_periodos_tem_limites_deterministicos(self):
        base = mundo.parse_instant("14 Eleasis, 1372 DR", "00:00").minute
        cases = {
            "04:59": "noite",
            "05:00": "amanhecer",
            "07:59": "amanhecer",
            "08:00": "dia",
            "16:59": "dia",
            "17:00": "anoitecer",
            "20:59": "anoitecer",
            "21:00": "noite",
        }
        for clock, expected in cases.items():
            hour, minute = map(int, clock.split(":"))
            instant = mundo.WorldInstant(base + hour * 60 + minute)
            self.assertEqual(incidental.period_from_instant(instant), expected, clock)

    def test_configuracao_congela_semantica_de_candidato(self):
        index = incidental.load_index(ROOT)
        self.assertTrue(index["regras"]["candidato_nao_e_presenca"])
        self.assertTrue(index["regras"]["candidato_nao_cria_acao"])
        self.assertTrue(index["regras"]["candidato_nao_cria_dialogo"])
        self.assertTrue(index["regras"]["candidato_nao_cria_conhecimento"])
        self.assertTrue(index["regras"]["candidato_nao_cria_encontro_sidequest"])
        self.assertTrue(index["regras"]["janela_independe_de_scene_id"])
        self.assertTrue(index["regras"]["canon_forte_prevalece"])


class IncidentalPresenceSelectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.narwhal = ecologia_local.lookup_canonical(ROOT, "narwhal_manor")["perfil"]
        cls.circus = ecologia_local.lookup_canonical(ROOT, "jack_mooney_sons_circus")["perfil"]

    def _find_active(self, local_id: str, ecology: dict, *, start_hour: str = "10:00", days: int = 16):
        for day in range(1, days + 1):
            instant = mundo.parse_instant(f"{day} Eleasis, 1372 DR", start_hour)
            result = incidental.select(
                ROOT,
                scene_id="probe",
                local_id=local_id,
                ecology=ecology,
                now=instant,
            )
            if result["candidatos"]:
                return instant, result
        self.fail(f"nenhuma janela ativa encontrada para {local_id}")

    def test_local_sem_perfil_incidental_nao_le_tempo(self):
        ecology = ecologia_local.lookup_canonical(ROOT, "galeria_dos_escribas")["perfil"]
        with mock.patch.object(mundo, "load_canonical_time", side_effect=AssertionError("não deveria ler tempo")):
            result = incidental.select(
                ROOT,
                scene_id="sem-perfil",
                local_id="galeria_dos_escribas",
                ecology=ecology,
            )
        self.assertEqual(result["candidatos"], [])
        self.assertEqual(result["fontes_lidas"], [incidental.INDEX.as_posix()])

    def test_periodo_incompativel_nao_produz_candidato(self):
        result = incidental.select(
            ROOT,
            scene_id="narwhal-noite",
            local_id="narwhal_manor",
            ecology=self.narwhal,
            now=mundo.parse_instant("14 Eleasis, 1372 DR", "22:00"),
        )
        self.assertEqual(result["periodo"], "noite")
        self.assertEqual(result["candidatos"], [])

    def test_janela_e_independente_do_scene_id(self):
        instant, first = self._find_active("narwhal_manor", self.narwhal)
        second = incidental.select(
            ROOT,
            scene_id="outra-cena-completamente",
            local_id="narwhal_manor",
            ecology=self.narwhal,
            now=instant,
        )
        self.assertEqual(
            [(x["id"], x["janela_id"], x["motivo"]) for x in first["candidatos"]],
            [(x["id"], x["janela_id"], x["motivo"]) for x in second["candidatos"]],
        )
        self.assertNotEqual(
            first["candidatos"][0]["avaliacao_id"],
            second["candidatos"][0]["avaliacao_id"],
        )

    def test_exclusao_de_npc_explicito_remove_coincidencia(self):
        instant, first = self._find_active("narwhal_manor", self.narwhal)
        npc_id = first["candidatos"][0]["id"]
        result = incidental.select(
            ROOT,
            scene_id="explicitamente-presente",
            local_id="narwhal_manor",
            ecology=self.narwhal,
            now=instant,
            exclude_ids=[npc_id],
        )
        self.assertEqual(result["candidatos"], [])

    def test_hot_path_com_now_explicito_abre_so_roteador_compacto(self):
        instant, result = self._find_active("narwhal_manor", self.narwhal)
        self.assertIsInstance(instant, mundo.WorldInstant)
        self.assertEqual(result["fontes_lidas"], [incidental.INDEX.as_posix()])
        self.assertFalse(any(source.startswith("estado/relacoes/") for source in result["fontes_lidas"]))
        self.assertFalse(any(source.startswith("narrador/agentes-leves/") for source in result["fontes_lidas"]))

    def test_sem_now_le_apenas_roteador_e_tempo(self):
        with mock.patch.object(
            mundo,
            "load_canonical_time",
            return_value=(mundo.parse_instant("14 Eleasis, 1372 DR", "10:00"), {}),
        ):
            result = incidental.select(
                ROOT,
                scene_id="tempo-canonico",
                local_id="narwhal_manor",
                ecology=self.narwhal,
            )
        self.assertEqual(
            result["fontes_lidas"],
            [incidental.INDEX.as_posix(), mundo.TIME_PATH.as_posix()],
        )

    def test_no_maximo_um_candidato_mesmo_com_dois_perfis_no_circo(self):
        for day in range(1, 25):
            for clock in ("10:00", "18:00"):
                result = incidental.select(
                    ROOT,
                    scene_id=f"circus-{day}-{clock}",
                    local_id="jack_mooney_sons_circus",
                    ecology=self.circus,
                    now=mundo.parse_instant(f"{day} Eleasis, 1372 DR", clock),
                )
                self.assertLessEqual(len(result["candidatos"]), 1)

    def test_candidato_e_avaliacao_sem_fato_automatico(self):
        _, result = self._find_active("narwhal_manor", self.narwhal)
        item = result["candidatos"][0]
        self.assertEqual(item["tipo"], "presenca")
        self.assertEqual(item["subtipo"], "incidental")
        self.assertEqual(item["modo_avaliacao"], "avaliar_presenca_incidental")
        self.assertNotIn("acao", item)
        self.assertNotIn("dialogo", item)
        self.assertNotIn("conhecimento", item)
        self.assertIn("não estabelece presença", item["regra"])


class IncidentalPresenceIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        for rel in (
            "cenario/locais",
            "narrador/recompensas",
            "narrador/microeventos-locais",
        ):
            shutil.copytree(ROOT / rel, self.repo / rel)
        (self.repo / "narrador").mkdir(exist_ok=True)
        shutil.copy2(ROOT / incidental.INDEX, self.repo / incidental.INDEX)

    def tearDown(self):
        self.temp.cleanup()

    def _find_scene_window(self, place: str, local_id: str):
        ecology = ecologia_local.lookup_canonical(ROOT, local_id)["perfil"]
        for day in range(1, 20):
            instant = mundo.parse_instant(f"{day} Eleasis, 1372 DR", "10:00")
            result = incidental.select(
                ROOT,
                scene_id="probe",
                local_id=local_id,
                ecology=ecology,
                now=instant,
            )
            if result["candidatos"]:
                return instant
        self.fail(f"janela incidental não encontrada para {place}")

    def test_prepare_anexa_incidental_sem_criar_encontro_ou_escrita(self):
        instant = self._find_scene_window("Narwhal Manor", "narwhal_manor")
        before = {
            path.relative_to(self.repo).as_posix(): path.read_bytes()
            for path in self.repo.rglob("*")
            if path.is_file()
        }
        result = cena_mundo.prepare_scene(
            self.repo,
            scene_id="incidental-integrado",
            place="Narwhal Manor",
            action="entrar",
            tier=1,
            danger="baixa",
            now=instant,
        )
        selected = result.get("presencas_incidentais") or []
        self.assertEqual(len(selected), 1)
        npc_id = selected[0]["id"]
        self.assertIn(npc_id, [item["id"] for item in result["presencas_contextuais"]])
        self.assertIn(npc_id, [item["id"] for item in result["candidatos_contextuais"]])
        self.assertEqual(result["encontros"], [])
        self.assertEqual(result["resumo"]["presencas_incidentais_para_avaliar"], 1)
        after = {
            path.relative_to(self.repo).as_posix(): path.read_bytes()
            for path in self.repo.rglob("*")
            if path.is_file()
        }
        self.assertEqual(before, after)

    def test_fixture_sem_camada_incidental_permanece_compativel(self):
        (self.repo / incidental.INDEX).unlink()
        result = cena_mundo.prepare_scene(
            self.repo,
            scene_id="sem-incidental",
            place="Galeria dos Escribas",
            action="entrar",
            tier=1,
            danger="baixa",
            now=mundo.parse_instant("14 Eleasis, 1372 DR", "10:00"),
        )
        self.assertNotIn("presencas_incidentais", result)
        self.assertFalse(any("presencas-incidentais" in source for source in result["fontes_lidas"]))

    def test_candidatos_contextuais_anteriores_tem_precedencia(self):
        base = {
            "ok": True,
            "cena_id": "lotada",
            "local": {
                "local_id": "jack_mooney_sons_circus",
                "ecologia": ecologia_local.lookup_canonical(ROOT, "jack_mooney_sons_circus")["perfil"],
            },
            "npcs_canonicos": [],
            "presencas_contextuais": [
                {"id": "estrategico_a", "tipo": "presenca"},
                {"id": "estrategico_b", "tipo": "presenca"},
            ],
            "candidatos_contextuais": [
                {"id": "estrategico_a", "tipo": "presenca"},
                {"id": "estrategico_b", "tipo": "presenca"},
            ],
            "encontros": [],
            "resumo": {"presencas_contextuais": 2, "candidatos_contextuais": 2},
            "regra": "base",
            "fontes_lidas": [],
        }
        import cena_mundo_v5
        with mock.patch.object(cena_mundo_v5, "_base_open_scene", return_value=copy.deepcopy(base)), mock.patch.object(
            incidental, "select", side_effect=AssertionError("não deve consultar incidental sem vaga de presença")
        ):
            result = cena_mundo_v5.open_scene(
                ROOT,
                scene_id="lotada",
                place="Circo de Jack Mooney",
                action="entrar",
                tier=1,
                danger="baixa",
            )
        self.assertEqual(result["presencas_contextuais"], base["presencas_contextuais"])
        self.assertNotIn("presencas_incidentais", result)


class IncidentalPresenceBudgetTest(unittest.TestCase):
    def test_contrato_de_orcamento_bate_com_codigo(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/incidental-presence-orcamento.yaml").read_text(encoding="utf-8")
        )
        limits = contract["limites"]
        self.assertEqual(limits["max_perfis"], incidental.MAX_PROFILES)
        self.assertEqual(limits["max_candidatos_por_cena"], incidental.MAX_CANDIDATES)
        self.assertEqual(limits["max_locais_por_perfil"], incidental.MAX_LOCALS_PER_PROFILE)
        self.assertEqual(limits["max_periodos_por_local"], incidental.MAX_PERIODS_PER_LOCAL)
        self.assertEqual(limits["max_motivos_por_local"], incidental.MAX_MOTIVES_PER_LOCAL)
        self.assertEqual(limits["max_fontes_adicionais_com_now_explicito"], 1)
        self.assertEqual(limits["max_fontes_adicionais_sem_now_explicito"], 2)
        self.assertEqual(limits["max_fragmentos_narrativos_selecao"], 0)
        self.assertEqual(limits["max_escritas_repo"], 0)
        self.assertEqual(limits["max_estados_novos"], 0)
        self.assertEqual(limits["max_schedulers_novos"], 0)
        self.assertEqual(limits["max_scans_repo"], 0)
        self.assertEqual(
            contract["integracao_contextual"]["max_presencas_total_preservado"],
            contexto_cena.MAX_PRESENCE_CANDIDATES,
        )
        self.assertEqual(
            contract["integracao_contextual"]["max_candidatos_total_preservado"],
            contexto_cena.MAX_CONTEXT_CANDIDATES,
        )


if __name__ == "__main__":
    unittest.main()
