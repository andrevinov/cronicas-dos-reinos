from __future__ import annotations

import hashlib
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
import npc_stubs


class AutomaticNpcStubTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self._write(
            "narrador/oportunidades/index.yaml",
            {
                "schema_oportunidades": 1,
                "natureza": "reservado",
                "semente": "npc-stub-test",
                "gate": {
                    "modo": "baralho_sem_reposicao_sha256",
                    "fichas": [
                        *[{"id": f"nada_{i:02d}", "resultado": "nada"} for i in range(1, 9)],
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
                    "nera_vell": {
                        "nome": "Nera Vell",
                        "estado": "ativo",
                        "arquivo": "narrador/oportunidades/perfis/nera_vell.yaml",
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
            "narrador/oportunidades/perfis/nera_vell.yaml",
            {
                "schema_perfil_oportunidades": 1,
                "natureza": "reservado",
                "estatuto": "sementes_nao_canonicas_ate_resolucao",
                "npc_id": "nera_vell",
                "nome": "Nera Vell",
                "fonte_npc": "estado/relacoes/nera_vell.yaml",
                "necessidades": [
                    {
                        "id": "favor",
                        "tipo": "favor",
                        "semente": "Uma necessidade coerente pode surgir.",
                        "janela": {"tipo": "a_qualquer_momento"},
                        "pode_reabrir": False,
                        "consequencia_sem_ren": "A vida segue sem Ren.",
                    }
                ],
            },
        )
        self._write("estado/relacoes/nera_vell.yaml", {"schema_relacao": 2, "id": "nera_vell"})
        self._write(
            "estado/relacoes/index.yaml",
            {
                "schema_relacoes": 2,
                "natureza": "indice_relacoes_atuais",
                "quantidade": 3,
                "relacoes": {
                    "nera_vell": {"nome": "Nera Vell"},
                    "sella_rove": {"nome": "Sella Rove"},
                    "velha_sella": {"nome": "Velha Sella"},
                },
            },
        )
        self._write(
            "estado/npcs/index.yaml",
            {
                "schema_npcs": 2,
                "natureza": "indice_medidores_npcs",
                "quantidade": 0,
                "npcs": {},
            },
        )

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def _digest(self) -> str:
        h = hashlib.sha256()
        for path in sorted(p for p in self.repo.rglob("*") if p.is_file()):
            h.update(path.relative_to(self.repo).as_posix().encode("utf-8"))
            h.update(b"\0")
            h.update(path.read_bytes())
        return h.hexdigest()

    def _prepare_tomas(self, scene="galeria-tomas"):
        return cena_mundo.prepare_scene(self.repo, scene_id=scene, npcs=["Tomas"])

    def test_preparar_tomas_propoe_id_estavel_sem_escrever(self):
        before = self._digest()
        result = self._prepare_tomas()
        self.assertEqual(self._digest(), before)
        self.assertEqual(result["npcs_canonicos"], ["tomas"])
        self.assertEqual(result["encontros"][0]["motivo"], "npc_persistente_sem_agenda")
        self.assertEqual(
            result["stubs_npc"],
            [
                {
                    "npc_id": "tomas",
                    "nome": "Tomas",
                    "persistencia": "persistente_sem_agenda",
                    "stub_automatico": True,
                }
            ],
        )
        self.assertFalse((self.repo / "estado/npcs/tomas.yaml").exists())

    def test_confirmar_materializa_stub_sem_sidequest_ou_agenda(self):
        prep = self._prepare_tomas()
        opportunity_before = (self.repo / "narrador/oportunidades/estado.yaml").read_bytes()
        relations_before = (self.repo / "estado/relacoes/index.yaml").read_bytes()
        result = cena_mundo.confirm_scene(
            self.repo,
            preparation_id=prep["preparacao_id"],
            scene_id="galeria-tomas",
            npcs=["Tomas"],
        )

        self.assertTrue(result["stubs_npc_persistidos"][0]["criado"])
        index = yaml.safe_load((self.repo / "estado/npcs/index.yaml").read_text(encoding="utf-8"))
        self.assertEqual(index["quantidade"], 1)
        self.assertEqual(index["npcs"]["tomas"]["persistencia"], "persistente_sem_agenda")
        fragment = yaml.safe_load((self.repo / "estado/npcs/tomas.yaml").read_text(encoding="utf-8"))
        self.assertEqual(fragment["npc"]["nome"], "Tomas")
        self.assertEqual(fragment["npc"]["persistencia"], "persistente_sem_agenda")
        history = yaml.safe_load((self.repo / "historico/npcs/tomas.yaml").read_text(encoding="utf-8"))
        self.assertEqual(history["eventos_pos_migracao"][0]["cena_id"], "galeria-tomas")
        self.assertEqual((self.repo / "narrador/oportunidades/estado.yaml").read_bytes(), opportunity_before)
        self.assertEqual((self.repo / "estado/relacoes/index.yaml").read_bytes(), relations_before)
        self.assertFalse((self.repo / "narrador/agentes/index.yaml").exists())
        self.assertFalse((self.repo / "narrador/agentes-leves/index.yaml").exists())
        self.assertFalse((self.repo / "narrador/mundo/agenda.yaml").exists())
        self.assertTrue(npc_stubs.check_repo(self.repo)["ok"])

    def test_reencontro_resolve_mesmo_stub_sem_criar_outro_id(self):
        prep = self._prepare_tomas()
        cena_mundo.confirm_scene(
            self.repo,
            preparation_id=prep["preparacao_id"],
            scene_id="galeria-tomas",
            npcs=["Tomas"],
        )
        second = cena_mundo.prepare_scene(self.repo, scene_id="galeria-tomas-2", npcs=["Tomas"])
        self.assertEqual(second["npcs_canonicos"], ["tomas"])
        self.assertEqual(second["stubs_npc"][0]["npc_id"], "tomas")
        self.assertEqual(second["encontros"][0]["motivo"], "npc_persistente_sem_agenda")
        self.assertEqual(
            yaml.safe_load((self.repo / "estado/npcs/index.yaml").read_text(encoding="utf-8"))["quantidade"],
            1,
        )

    def test_mesmo_nome_novo_repetido_na_cena_e_colapsado(self):
        result = cena_mundo.prepare_scene(
            self.repo,
            scene_id="tomas-duplicado",
            npcs=["Tomas", "Tomas"],
        )
        self.assertEqual(result["npcs_canonicos"], ["tomas"])
        self.assertEqual(result["duplicatas_colapsadas"], [{"recebido": "Tomas", "npc_id": "tomas"}])
        self.assertEqual(len(result["stubs_npc"]), 1)

    def test_sella_ambiguo_nao_cria_terceira_sella(self):
        before = self._digest()
        with self.assertRaises(cena_mundo.SceneGateError) as ctx:
            cena_mundo.prepare_scene(self.repo, scene_id="sella", npcs=["Sella"])
        self.assertIn("Sella", str(ctx.exception))
        self.assertEqual(self._digest(), before)
        self.assertNotIn(
            "sella",
            yaml.safe_load((self.repo / "estado/npcs/index.yaml").read_text(encoding="utf-8"))["npcs"],
        )

    def test_typo_proximo_nao_vira_npc_novo(self):
        with self.assertRaises(cena_mundo.SceneGateError) as ctx:
            cena_mundo.prepare_scene(self.repo, scene_id="typo", npcs=["Nrea"])
        self.assertIn("nera_vell", str(ctx.exception))
        self.assertFalse((self.repo / "estado/npcs/nrea.yaml").exists())

    def test_figurante_anonimo_nao_recebe_stub(self):
        with self.assertRaises(cena_mundo.SceneGateError) as ctx:
            cena_mundo.prepare_scene(self.repo, scene_id="guarda", npcs=["guarda"])
        self.assertIn("figurantes anônimos", str(ctx.exception))
        self.assertEqual(
            yaml.safe_load((self.repo / "estado/npcs/index.yaml").read_text(encoding="utf-8"))["quantidade"],
            0,
        )


class NpcStubBudgetContractTest(unittest.TestCase):
    def test_contrato_congela_stub_fora_do_scheduler(self):
        contract = yaml.safe_load((ROOT / "baseline/npc-stub-orcamento.yaml").read_text(encoding="utf-8"))
        self.assertEqual(contract["limites"]["max_escritas_preparar"], 0)
        self.assertEqual(contract["limites"]["max_stubs_por_cena"], 6)
        inv = contract["invariantes"]
        self.assertTrue(inv["stub_nao_cria_scheduler"])
        self.assertTrue(inv["stub_nao_cria_perfil_sidequest"])
        self.assertTrue(inv["npc_novo_nao_sorteia_sidequest"])
        self.assertTrue(inv["turno_comum_sem_leitura_adicional"])


if __name__ == "__main__":
    unittest.main()
