from __future__ import annotations

import copy
import hashlib
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
import ecologia_local
import locais


class LocalEcologyRepositoryTest(unittest.TestCase):
    def test_repositorio_real_cobre_exatamente_os_locais_canonicos(self):
        ecology = ecologia_local.load_index(ROOT)
        registry = locais.load_index(ROOT)
        # A cardinalidade evolui com o registro; a igualdade dos conjuntos é o contrato.
        self.assertEqual(set(ecology["perfis"]), set(registry["locais"]))
        self.assertEqual(ecologia_local.validate_coverage(ROOT, ecology), [])
        self.assertTrue(ecologia_local.check(ROOT)["ok"])

    def test_perfis_reais_respeitam_tetos_e_nao_nomeiam_presenca(self):
        ecology = ecologia_local.load_index(ROOT)
        for local_id, profile in ecology["perfis"].items():
            rendered = yaml.safe_dump(profile, allow_unicode=True, sort_keys=False).encode("utf-8")
            self.assertLessEqual(len(rendered), ecologia_local.MAX_PROFILE_BYTES, local_id)
            self.assertLessEqual(len(profile["tags"]), ecologia_local.MAX_TAGS)
            self.assertLessEqual(len(profile["atores_comuns"]), ecologia_local.MAX_ACTORS)
            self.assertLessEqual(len(profile["canais_microevento"]), ecologia_local.MAX_CHANNELS)
            self.assertNotIn("npc", profile)
            self.assertNotIn("presenca", profile)
            self.assertNotIn("evento", profile)

    def test_galeria_e_narwhal_expoem_ecologias_distintas_e_compactas(self):
        gallery = ecologia_local.lookup(ROOT, "galeria de escribas")
        narwhal = ecologia_local.lookup(ROOT, "mansão Narwhal")
        self.assertEqual(gallery["local_id"], "galeria_dos_escribas")
        self.assertEqual(gallery["perfil"]["familia"], "entreposto_documental")
        self.assertIn("documentos", gallery["perfil"]["tags"])
        self.assertEqual(narwhal["local_id"], "narwhal_manor")
        self.assertEqual(narwhal["perfil"]["familia"], "mansao_privada")
        self.assertIn("estabulo", narwhal["perfil"]["tags"])
        self.assertEqual(
            gallery["fontes_lidas"],
            ["cenario/locais/index.yaml", "cenario/locais/ecologia.yaml"],
        )

    def test_lookup_canonico_nao_reabre_registro(self):
        with mock.patch.object(ecologia_local.locais, "load_index") as registry:
            result = ecologia_local.lookup_canonical(ROOT, "galeria_dos_escribas")
        registry.assert_not_called()
        self.assertEqual(result["fontes_lidas"], ["cenario/locais/ecologia.yaml"])

    def test_atividade_por_periodo_e_pura_e_relativa(self):
        profile = ecologia_local.lookup(ROOT, "casa de Tyr")["perfil"]
        before = copy.deepcopy(profile)
        result = ecologia_local.activity(profile, "dia")
        self.assertEqual(result["periodo"], "dia")
        self.assertEqual(result["ritmo"], 3)
        self.assertEqual(profile, before)


class LocalEcologySyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self._write(
            "cenario/locais/index.yaml",
            {
                "schema_locais": 1,
                "natureza": "roteador_canonico",
                "regra": "alias_nunca_cria_novo_local",
                "locais": {
                    "local_a": {"nome": "Local A", "aliases": ["A"]},
                    "local_b": {"nome": "Local B", "aliases": []},
                },
            },
        )
        self._write_ecology(["local_a", "local_b"])

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

    def _profile(self):
        return {
            "familia": "fixture",
            "acesso": "controlado",
            "ritmo_baseline": {
                "amanhecer": 1,
                "dia": 2,
                "anoitecer": 1,
                "noite": 0,
            },
            "tags": ["trabalho"],
            "atores_comuns": ["trabalhador"],
            "canais_microevento": ["rotina"],
        }

    def _write_ecology(self, ids):
        self._write(
            "cenario/locais/ecologia.yaml",
            {
                "schema_ecologia_local": 1,
                "natureza": "roteador_operacional_nao_canonico",
                "estatuto": "restricao_de_plausibilidade",
                "escala_ritmo": {
                    0: "quase_inativo",
                    1: "baixo",
                    2: "medio",
                    3: "alto",
                },
                "periodos": ["amanhecer", "dia", "anoitecer", "noite"],
                "regras": {
                    "exige_local_canonico": True,
                    "cobertura_total_do_registro": True,
                    "atores_sao_papeis_nao_npcs": True,
                    "perfil_nao_estabelece_presenca": True,
                    "perfil_nao_cria_evento": True,
                    "perfil_nao_cria_conhecimento": True,
                    "microevento_futuro_deve_respeitar_tags_e_canais": True,
                    "estado_canonico_prevalece": True,
                },
                "perfis": {local_id: self._profile() for local_id in ids},
            },
        )

    def test_alias_resolve_antes_da_ecologia(self):
        result = ecologia_local.lookup(self.repo, "A")
        self.assertEqual(result["local_id"], "local_a")
        self.assertEqual(result["resolucao"], "alias_canonico")

    def test_cobertura_incompleta_falha_check(self):
        self._write_ecology(["local_a"])
        result = ecologia_local.check(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("local_b", result["erros"][0])

    def test_perfil_nao_aceita_campo_de_presenca_ou_evento(self):
        data = yaml.safe_load((self.repo / ecologia_local.INDEX).read_text())
        data["perfis"]["local_a"]["presenca"] = "npc_x"
        self._write(ecologia_local.INDEX.as_posix(), data)
        with self.assertRaises(ecologia_local.LocalEcologyError):
            ecologia_local.load_index(self.repo)


class LocalEcologySceneIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        shutil.copytree(ROOT / "narrador/recompensas", self.repo / "narrador/recompensas")
        shutil.copytree(ROOT / "cenario/locais", self.repo / "cenario/locais")
        registry_path = self.repo / "cenario/locais/index.yaml"
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        registry["locais"]["local_ecologico"] = {
            "nome": "Local Ecológico",
            "aliases": ["local eco"],
        }
        registry_path.write_text(
            yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        ecology_path = self.repo / ecologia_local.INDEX
        ecology = yaml.safe_load(ecology_path.read_text(encoding="utf-8"))
        ecology["perfis"]["local_ecologico"] = {
            "familia": "fixture_ecologico",
            "acesso": "controlado",
            "ritmo_baseline": {"amanhecer": 1, "dia": 2, "anoitecer": 1, "noite": 0},
            "tags": ["trabalho", "entrega"],
            "atores_comuns": ["trabalhador"],
            "canais_microevento": ["rotina", "entrega"],
        }
        ecology_path.write_text(
            yaml.safe_dump(ecology, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )

    def tearDown(self):
        self.temp.cleanup()

    def _digest(self):
        return {
            path.relative_to(self.repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(self.repo.rglob("*"))
            if path.is_file()
        }

    def test_preparacao_local_anexa_ecologia_sem_escrever_ou_ler_tempo(self):
        before = self._digest()
        with mock.patch.object(cena_mundo.interacoes_mundo, "_now") as now:
            preview = cena_mundo.prepare_scene(
                self.repo,
                scene_id="eco-scene",
                place="local eco",
                action="entrar",
                tier=1,
                danger="baixa",
            )
        now.assert_not_called()
        self.assertEqual(self._digest(), before)
        self.assertEqual(preview["local"]["local_id"], "local_ecologico")
        self.assertEqual(preview["local"]["ecologia"]["familia"], "fixture_ecologico")
        self.assertIn("cenario/locais/ecologia.yaml", preview["fontes_lidas"])
        self.assertFalse(preview["mutacoes_aplicadas"])

    def test_cena_sem_local_nao_consulta_ecologia(self):
        with mock.patch.object(cena_mundo.ecologia_local, "lookup_canonical") as ecology:
            with self.assertRaises(cena_mundo.SceneGateError):
                cena_mundo.prepare_scene(self.repo, scene_id="sem-gatilho")
        ecology.assert_not_called()

    def test_mudanca_ecologica_invalida_preparacao_antiga(self):
        preview = cena_mundo.prepare_scene(
            self.repo,
            scene_id="eco-stale",
            place="local_ecologico",
            action="entrar",
            tier=1,
            danger="baixa",
        )
        ecology_path = self.repo / ecologia_local.INDEX
        ecology = yaml.safe_load(ecology_path.read_text(encoding="utf-8"))
        ecology["perfis"]["local_ecologico"]["tags"].append("mudanca_operacional")
        ecology_path.write_text(
            yaml.safe_dump(ecology, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        with self.assertRaisesRegex(cena_mundo.SceneGateError, "obsoleta"):
            cena_mundo.confirm_scene(
                self.repo,
                preparation_id=preview["preparacao_id"],
                scene_id="eco-stale",
                place="local_ecologico",
                action="entrar",
                tier=1,
                danger="baixa",
            )


class LocalEcologyBudgetTest(unittest.TestCase):
    def test_contrato_bate_com_codigo(self):
        data = yaml.safe_load(
            (ROOT / "baseline/local-ecology-orcamento.yaml").read_text(encoding="utf-8")
        )
        limits = data["limites"]
        self.assertEqual(data["schema_orcamento_ecologia_local"], 1)
        self.assertEqual(limits["max_perfis"], ecologia_local.MAX_PROFILES)
        self.assertEqual(limits["max_bytes_por_perfil"], ecologia_local.MAX_PROFILE_BYTES)
        self.assertEqual(limits["max_tags_por_perfil"], ecologia_local.MAX_TAGS)
        self.assertEqual(limits["max_atores_comuns"], ecologia_local.MAX_ACTORS)
        self.assertEqual(limits["max_canais_microevento"], ecologia_local.MAX_CHANNELS)
        self.assertEqual(limits["max_fontes_lookup_publico"], 2)
        self.assertEqual(limits["max_fontes_extras_em_cena_local"], 1)
        self.assertEqual(limits["max_fragmentos_narrativos"], 0)
        self.assertEqual(limits["max_leituras_tempo"], 0)
        self.assertEqual(limits["max_escritas"], 0)
        self.assertEqual(limits["max_schedulers_novos"], 0)
        self.assertTrue(data["invariantes"]["nenhum_microevento_e_sorteado_nesta_task"])


if __name__ == "__main__":
    unittest.main()
