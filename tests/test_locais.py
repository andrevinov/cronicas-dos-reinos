from __future__ import annotations

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
import locais
import recompensas
import texturas


class LocalRegistryRepositoryTest(unittest.TestCase):
    def test_aliases_observados_nos_rollouts_convergem_para_ids_antigos(self):
        salgueiro = locais.resolve(ROOT, "casa_do_salgueiro_seco")
        circo = locais.resolve(ROOT, "jack_mooney_and_sons_circus")
        self.assertEqual(salgueiro["local_id"], "casa_salgueiro_seco")
        self.assertEqual(circo["local_id"], "jack_mooney_sons_circus")
        self.assertEqual(salgueiro["resolucao"], "alias_canonico")
        self.assertEqual(circo["resolucao"], "alias_canonico")

    def test_consumidores_reais_persistem_somente_ids_canonicos(self):
        result = locais.check(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        rewards = recompensas.load_index(ROOT)["mapas"]
        self.assertIn("casa_salgueiro_seco", rewards)
        self.assertIn("jack_mooney_sons_circus", rewards)
        self.assertNotIn("casa_do_salgueiro_seco", rewards)
        self.assertNotIn("jack_mooney_and_sons_circus", rewards)

    def test_alias_de_textura_local_usa_o_mesmo_id_canonico(self):
        texture, sources, candidates = texturas.lookup(ROOT, "locais", "abrigo de Iria")
        self.assertEqual(candidates, [])
        self.assertIsNotNone(texture)
        self.assertEqual(texture["id"], "casa_iria_doss")
        self.assertEqual(texture["resolucao_local"], "alias_canonico")
        self.assertEqual(
            sources,
            [
                "cenario/locais/index.yaml",
                "cenario/texturas/index.yaml",
                "cenario/texturas/locais/casa_iria_doss.yaml",
            ],
        )


class LocalRegistrySyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _write_registry(self, locations: dict) -> None:
        path = self.repo / "cenario/locais/index.yaml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(
                {
                    "schema_locais": 1,
                    "natureza": "roteador_canonico",
                    "regra": "alias_nunca_cria_novo_local",
                    "locais": locations,
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def test_alias_ambiguo_falha_explicitamente(self):
        self._write_registry(
            {
                "mercado_norte": {"nome": "Mercado Norte", "aliases": ["mercado"]},
                "mercado_sul": {"nome": "Mercado Sul", "aliases": ["mercado"]},
            }
        )
        with self.assertRaisesRegex(locais.LocationError, "ambíguo"):
            locais.load_index(self.repo)

    def test_desconhecido_nao_cria_id_por_aproximacao(self):
        self._write_registry(
            {
                "galeria_dos_escribas": {
                    "nome": "Galeria dos Escribas",
                    "aliases": ["galeria"],
                }
            }
        )
        with self.assertRaisesRegex(locais.LocationError, "local desconhecido"):
            locais.resolve(self.repo, "galeria dos escrivaes")

    def test_cena_resolve_alias_antes_de_qualquer_efeito_local(self):
        self._write_registry(
            {
                "setor_a": {
                    "nome": "Setor A",
                    "aliases": ["setor_antigo", "Setor Antigo"],
                }
            }
        )
        contextual = {
            "tags": [],
            "arco": None,
            "candidatos": [],
            "presencas": [],
            "entradas": [],
            "operacoes": [],
            "direcoes": [],
            "fontes_lidas": [],
        }
        local_result = {
            "ok": True,
            "gatilho": "local:entrar",
            "local_id": "setor_a",
            "mapa_criado": False,
            "mapa": {"local_id": "setor_a"},
            "fontes_lidas": ["narrador/recompensas/index.yaml"],
        }
        with (
            mock.patch.object(
                cena_mundo.contexto_cena,
                "select_candidates",
                return_value=contextual,
            ),
            mock.patch.object(
                cena_mundo.interacoes_mundo,
                "local_event",
                return_value=local_result,
            ) as local_event,
        ):
            result = cena_mundo.open_scene(
                self.repo,
                scene_id="alias-local",
                place="setor_antigo",
                action="entrar",
                tier=1,
                danger="baixa",
            )

        local_event.assert_called_once_with(
            self.repo,
            "setor_a",
            action="entrar",
            tier=1,
            danger="baixa",
        )
        self.assertEqual(result["local"]["local_id"], "setor_a")
        self.assertEqual(result["local"]["local_ref_recebido"], "setor_antigo")
        self.assertEqual(result["local"]["resolucao_local"], "alias_canonico")
        self.assertEqual(
            result["fontes_lidas"],
            ["cenario/locais/index.yaml", "narrador/recompensas/index.yaml"],
        )

    def test_local_desconhecido_falha_antes_de_mutar(self):
        self._write_registry(
            {"setor_a": {"nome": "Setor A", "aliases": []}}
        )
        with mock.patch.object(cena_mundo.interacoes_mundo, "local_event") as local_event:
            with self.assertRaises(cena_mundo.SceneGateError):
                cena_mundo.open_scene(
                    self.repo,
                    scene_id="local-desconhecido",
                    place="setor_b",
                    action="entrar",
                    tier=1,
                    danger="baixa",
                )
        local_event.assert_not_called()

    def test_fixture_sem_camadas_de_local_preserva_id_explicito(self):
        result = locais.resolve(self.repo, "local_teste")
        self.assertEqual(result["local_id"], "local_teste")
        self.assertEqual(result["resolucao"], "fixture_sem_registro")
        self.assertEqual(result["fontes_lidas"], [])


if __name__ == "__main__":
    unittest.main()
