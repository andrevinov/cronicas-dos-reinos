from __future__ import annotations

import contextlib
import hashlib
import io
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

import cena_mundo
import mundo
import oportunidades
import recompensas


class TransactionalEncounterPreparationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.now = mundo.parse_instant("11 Eleasis, 1372 DR", "09:00")
        self._write(
            "narrador/oportunidades/index.yaml",
            {
                "schema_oportunidades": 1,
                "natureza": "reservado",
                "semente": "scene-transaction-test",
                "gate": {
                    "modo": "baralho_sem_reposicao_sha256",
                    "fichas": [
                        *[
                            {"id": f"nada_{i:02d}", "resultado": "nada"}
                            for i in range(1, 9)
                        ],
                        {"id": "oportunidade_01", "resultado": "oportunidade"},
                        {"id": "oportunidade_02", "resultado": "oportunidade"},
                    ],
                },
                "orcamento": {
                    "max_ativas": 2,
                    "max_em_aberto": 3,
                    "max_pendencias_avaliacao": 1,
                    "cooldown_oferta_dias": [2, 3],
                },
                "regras": {
                    "acionamento": "encontro_com_npc",
                    "scheduler": "proibido",
                    "scan_geral_npcs": "proibido",
                    "necessidade_nao_e_oferta": True,
                    "oferta_nao_e_aceite": True,
                    "consequencia_sem_ren_nao_e_automatica": True,
                },
                "perfis": {
                    "npc_a": {
                        "nome": "NPC A",
                        "estado": "ativo",
                        "arquivo": "narrador/oportunidades/perfis/npc_a.yaml",
                    }
                },
            },
        )
        self._write(
            "narrador/oportunidades/estado.yaml",
            {
                "schema_estado_oportunidades": 1,
                "natureza": "controle_reservado",
                "gate": {"ciclo": 0, "restantes": [], "sorteios": 0},
                "cooldown_ate": None,
                "pendencias_avaliacao": {},
                "missoes": {},
                "sementes_consumidas": [],
                "encontros_recentes": [],
                "historico_recente": [],
            },
        )
        self._write(
            "narrador/oportunidades/perfis/npc_a.yaml",
            {
                "schema_perfil_oportunidades": 1,
                "natureza": "reservado",
                "estatuto": "sementes_nao_canonicas_ate_resolucao",
                "npc_id": "npc_a",
                "nome": "NPC A",
                "fonte_npc": "estado/relacoes/npc_a.yaml",
                "necessidades": [
                    {
                        "id": "favor",
                        "tipo": "favor",
                        "semente": "Uma necessidade coerente pode existir.",
                        "janela": {"tipo": "a_qualquer_momento"},
                        "pode_reabrir": False,
                        "consequencia_sem_ren": "O mundo pode resolver sem Ren.",
                    }
                ],
            },
        )
        self._write(
            "estado/relacoes/index.yaml",
            {
                "schema_relacoes": 2,
                "natureza": "indice_relacoes_atuais",
                "quantidade": 1,
                "relacoes": {"npc_a": {"nome": "NPC A"}},
            },
        )

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _state(self) -> dict:
        return oportunidades.load_state(
            self.repo,
            oportunidades.load_index(self.repo),
        )

    def test_prepare_e_idempotente_e_nao_consome_gate(self):
        state_path = self.repo / oportunidades.STATE
        before = state_path.read_bytes()

        first = cena_mundo.prepare_scene(
            self.repo,
            scene_id="scene-tx",
            npcs=["npc_a"],
            now=self.now,
        )
        second = cena_mundo.prepare_scene(
            self.repo,
            scene_id="scene-tx",
            npcs=["npc_a"],
            now=self.now,
        )

        self.assertEqual(state_path.read_bytes(), before)
        self.assertEqual(self._state()["gate"]["sorteios"], 0)
        self.assertEqual(first["preparacao_id"], second["preparacao_id"])
        self.assertEqual(first["encontros"], second["encontros"])
        self.assertFalse(first["mutacoes_aplicadas"])

    def test_confirmar_materializa_exatamente_uma_vez(self):
        preview = cena_mundo.prepare_scene(
            self.repo,
            scene_id="scene-commit",
            npcs=["npc_a"],
            now=self.now,
        )
        self.assertEqual(self._state()["gate"]["sorteios"], 0)

        committed = cena_mundo.confirm_scene(
            self.repo,
            preparation_id=preview["preparacao_id"],
            scene_id="scene-commit",
            npcs=["npc_a"],
            now=self.now,
        )
        self.assertEqual(self._state()["gate"]["sorteios"], 1)
        self.assertTrue(committed["mutacoes_aplicadas"])
        self.assertTrue(committed["preparacao_revalidada"])
        self.assertEqual(
            committed["encontros"][0].get("ficha"),
            preview["encontros"][0].get("ficha"),
        )
        self.assertEqual(
            committed["encontros"][0]["resultado"],
            preview["encontros"][0]["resultado"],
        )

        with self.assertRaisesRegex(cena_mundo.SceneGateError, "obsoleta"):
            cena_mundo.confirm_scene(
                self.repo,
                preparation_id=preview["preparacao_id"],
                scene_id="scene-commit",
                npcs=["npc_a"],
                now=self.now,
            )
        self.assertEqual(self._state()["gate"]["sorteios"], 1)

    def test_verbo_abrir_do_cli_agora_e_preparacao_sem_escrita(self):
        before = (self.repo / oportunidades.STATE).read_bytes()
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            rc = cena_mundo.main(
                [
                    "--repo",
                    str(self.repo),
                    "abrir",
                    "--cena-id",
                    "scene-legacy-safe",
                    "--npc",
                    "npc_a",
                    "--data",
                    "11 Eleasis, 1372 DR",
                    "--hora",
                    "09:00",
                ]
            )
        self.assertEqual(rc, 0)
        payload = yaml.safe_load(out.getvalue())
        self.assertEqual(payload["alias_cli"], "abrir->preparar")
        self.assertFalse(payload["mutacoes_aplicadas"])
        self.assertEqual((self.repo / oportunidades.STATE).read_bytes(), before)


class TransactionalLocalPreparationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        shutil.copytree(
            ROOT / "narrador/recompensas",
            self.repo / "narrador/recompensas",
        )
        shutil.copytree(
            ROOT / "cenario/locais",
            self.repo / "cenario/locais",
        )
        registry_path = self.repo / "cenario/locais/index.yaml"
        registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
        synthetic_ids = ("local_transacional", "local_descartado", "local_stale")
        registry["locais"]["local_transacional"] = {
            "nome": "Local Transacional",
            "aliases": ["local de teste transacional"],
        }
        registry["locais"]["local_descartado"] = {
            "nome": "Local Descartado",
            "aliases": [],
        }
        registry["locais"]["local_stale"] = {
            "nome": "Local Stale",
            "aliases": [],
        }
        registry_path.write_text(
            yaml.safe_dump(registry, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

        ecology_path = self.repo / "cenario/locais/ecologia.yaml"
        ecology = yaml.safe_load(ecology_path.read_text(encoding="utf-8"))
        for local_id in synthetic_ids:
            ecology["perfis"][local_id] = {
                "familia": "fixture_transacional",
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
        ecology_path.write_text(
            yaml.safe_dump(ecology, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def _tree_digest(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for path in sorted(self.repo.rglob("*")):
            if path.is_file():
                result[path.relative_to(self.repo).as_posix()] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
        return result

    def _reward_index(self) -> dict:
        return recompensas.load_index(self.repo)

    def test_prepare_local_calcula_loot_sem_criar_artefato(self):
        before = self._tree_digest()
        preview = cena_mundo.prepare_scene(
            self.repo,
            scene_id="local-tx",
            place="local de teste transacional",
            action="entrar",
            tier=1,
            danger="baixa",
        )
        self.assertEqual(self._tree_digest(), before)
        self.assertEqual(preview["local"]["ecologia"]["familia"], "fixture_transacional")
        self.assertFalse(preview["local"]["mapa_criado"])
        self.assertTrue(preview["local"]["mapa_seria_criado"])
        self.assertNotIn("local_transacional", self._reward_index()["mapas"])
        self.assertFalse(
            (self.repo / "narrador/recompensas/mapas/local_transacional.yaml").exists()
        )

        committed = cena_mundo.confirm_scene(
            self.repo,
            preparation_id=preview["preparacao_id"],
            scene_id="local-tx",
            place="local de teste transacional",
            action="entrar",
            tier=1,
            danger="baixa",
        )
        self.assertTrue(committed["local"]["mapa_criado"])
        self.assertIn("local_transacional", self._reward_index()["mapas"])
        self.assertTrue(
            (self.repo / "narrador/recompensas/mapas/local_transacional.yaml").is_file()
        )

    def test_preparacao_abandonada_nao_deixa_residuo(self):
        before = self._tree_digest()
        preview = cena_mundo.prepare_scene(
            self.repo,
            scene_id="cena-que-nao-aconteceu",
            place="local_descartado",
            action="explorar",
            tier=2,
            danger="media",
        )
        self.assertTrue(preview["local"]["mapa_seria_criado"])
        self.assertEqual(self._tree_digest(), before)
        self.assertNotIn("local_descartado", self._reward_index()["mapas"])

    def test_confirmacao_recusa_preparacao_se_fonte_mudou(self):
        preview = cena_mundo.prepare_scene(
            self.repo,
            scene_id="stale",
            place="local_stale",
            action="entrar",
            tier=1,
            danger="baixa",
        )
        planned = self.repo / recompensas.PLANNED
        planned.write_text(
            planned.read_text(encoding="utf-8") + "\n# mudança concorrente de regressão\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(cena_mundo.SceneGateError, "obsoleta"):
            cena_mundo.confirm_scene(
                self.repo,
                preparation_id=preview["preparacao_id"],
                scene_id="stale",
                place="local_stale",
                action="entrar",
                tier=1,
                danger="baixa",
            )
        self.assertNotIn("local_stale", self._reward_index()["mapas"])
        self.assertFalse(
            (self.repo / "narrador/recompensas/mapas/local_stale.yaml").exists()
        )


class TransactionalSceneBudgetContractTest(unittest.TestCase):
    def test_contrato_exige_prepare_sem_escrita_e_confirmacao_revalidada(self):
        data = yaml.safe_load(
            (ROOT / "baseline/cena-transacional-orcamento.yaml").read_text(encoding="utf-8")
        )
        self.assertEqual(data["schema_cena_transacional"], 1)
        self.assertEqual(data["preparar"]["max_escritas_repo"], 0)
        self.assertTrue(data["preparar"]["idempotente"])
        self.assertTrue(data["preparar"]["calcula_ecologia_local"])
        self.assertTrue(data["confirmar"]["exige_preparacao_id"])
        self.assertTrue(data["confirmar"]["revalida_fontes"])
        self.assertEqual(data["invariantes"]["arquivo_preparacao_persistido"], 0)
        self.assertEqual(data["invariantes"]["novo_scheduler"], 0)
        self.assertTrue(data["invariantes"]["ecologia_local_e_fonte_do_fingerprint"])
        self.assertTrue(data["invariantes"]["ecologia_local_nao_estabelece_fato"])


if __name__ == "__main__":
    unittest.main()
