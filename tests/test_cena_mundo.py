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
import mundo
import oportunidades


class CenaMundoTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.now = mundo.parse_instant("11 Eleasis, 1372 DR", "09:00")
        self._write(
            "narrador/oportunidades/index.yaml",
            {
                "schema_oportunidades": 1,
                "natureza": "reservado",
                "semente": "cena-mundo-teste",
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
                    },
                    "npc_b": {
                        "nome": "NPC B",
                        "estado": "ativo",
                        "arquivo": "narrador/oportunidades/perfis/npc_b.yaml",
                    },
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
        for npc_id, name in (("npc_a", "NPC A"), ("npc_b", "NPC B")):
            self._write(
                f"narrador/oportunidades/perfis/{npc_id}.yaml",
                {
                    "schema_perfil_oportunidades": 1,
                    "natureza": "reservado",
                    "estatuto": "sementes_nao_canonicas_ate_resolucao",
                    "npc_id": npc_id,
                    "nome": name,
                    "fonte_npc": f"estado/relacoes/{npc_id}.yaml",
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
                f"estado/relacoes/{npc_id}.yaml",
                {"schema_relacao": 2, "id": npc_id},
            )
        self._write(
            "estado/relacoes/index.yaml",
            {
                "schema_relacoes": 2,
                "natureza": "indice_relacoes_atuais",
                "quantidade": 3,
                "relacoes": {
                    "npc_a": {"nome": "NPC A"},
                    "npc_b": {"nome": "NPC B"},
                    "npc_c": {"nome": "NPC C"},
                },
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

    def _draws(self) -> int:
        return oportunidades.load_state(
            self.repo,
            oportunidades.load_index(self.repo),
        )["gate"]["sorteios"]

    def test_ordena_encontros_simultaneos_e_deriva_ids_estaveis(self):
        fake = lambda npc_id, **kwargs: {
            "ok": True,
            "resultado": "interacao_normal",
            "motivo": "gate_sem_oportunidade",
            "npc_id": npc_id,
            "encontro_id": kwargs["encounter_id"],
            "fontes_lidas": [],
        }
        with mock.patch.object(
            cena_mundo.interacoes_mundo, "encounter_event", side_effect=fake
        ) as encounter:
            result = cena_mundo.open_scene(
                self.repo,
                scene_id="s009-circo",
                npcs=["npc_b", "npc_a"],
                now=self.now,
            )

        self.assertEqual(result["npcs_canonicos"], ["npc_a", "npc_b"])
        self.assertEqual(
            [call.args[1] for call in encounter.call_args_list],
            ["npc_a", "npc_b"],
        )
        self.assertEqual(
            [call.kwargs["encounter_id"] for call in encounter.call_args_list],
            [
                "scene:s009-circo:npc:npc_a",
                "scene:s009-circo:npc:npc_b",
            ],
        )

    def test_alias_e_id_do_mesmo_npc_sao_colapsados(self):
        with mock.patch.object(
            cena_mundo.interacoes_mundo,
            "encounter_event",
            return_value={
                "ok": True,
                "resultado": "interacao_normal",
                "motivo": "gate_sem_oportunidade",
                "npc_id": "npc_a",
                "fontes_lidas": [],
            },
        ) as encounter:
            result = cena_mundo.open_scene(
                self.repo,
                scene_id="duplicata",
                npcs=["npc_a", "NPC A"],
                now=self.now,
            )
        encounter.assert_called_once()
        self.assertEqual(result["npcs_canonicos"], ["npc_a"])
        self.assertEqual(
            result["duplicatas_colapsadas"],
            [{"recebido": "NPC A", "npc_id": "npc_a"}],
        )

    def test_typo_falha_antes_de_mutar_local(self):
        with mock.patch.object(cena_mundo.interacoes_mundo, "local_event") as local:
            with self.assertRaises(cena_mundo.SceneGateError):
                cena_mundo.open_scene(
                    self.repo,
                    scene_id="falha-antes",
                    npcs=["npc_z"],
                    place="local_teste",
                    action="entrar",
                    tier=1,
                    danger="baixa",
                    now=self.now,
                )
        local.assert_not_called()
        self.assertEqual(self._draws(), 0)

    def test_local_sozinho_nao_le_oportunidades_nem_tempo(self):
        local_result = {
            "ok": True,
            "local_id": "local_teste",
            "mapa_criado": True,
            "fontes_lidas": ["narrador/recompensas/index.yaml"],
        }
        with (
            mock.patch.object(cena_mundo.oportunidades, "load_index") as opp,
            mock.patch.object(cena_mundo.interacoes_mundo, "_now") as now,
            mock.patch.object(
                cena_mundo.interacoes_mundo,
                "local_event",
                return_value=local_result,
            ) as local,
        ):
            result = cena_mundo.open_scene(
                self.repo,
                scene_id="local-only",
                place="local_teste",
                action="explorar",
                tier=2,
                danger="media",
            )
        opp.assert_not_called()
        now.assert_not_called()
        local.assert_called_once()
        self.assertEqual(result["resumo"]["gatilhos_locais"], 1)
        self.assertEqual(result["resumo"]["encontros"], 0)

    def test_npc_sem_perfil_nao_precisa_ler_tempo(self):
        with mock.patch.object(cena_mundo.interacoes_mundo, "_now") as now:
            result = cena_mundo.open_scene(
                self.repo,
                scene_id="sem-perfil",
                npcs=["npc_c"],
            )
        now.assert_not_called()
        self.assertEqual(result["encontros"][0]["motivo"], "npc_sem_perfil_ativo")
        self.assertEqual(result["resumo"]["sem_perfil_ativo"], 1)

    def test_repetir_mesma_cena_nao_consome_gate_de_novo(self):
        first = cena_mundo.open_scene(
            self.repo,
            scene_id="mesma-cena",
            npcs=["npc_a"],
            now=self.now,
        )
        after_first = self._draws()
        second = cena_mundo.open_scene(
            self.repo,
            scene_id="mesma-cena",
            npcs=["npc_a"],
            now=self.now,
        )
        self.assertEqual(after_first, 1)
        self.assertEqual(self._draws(), after_first)
        self.assertEqual(first["encontros"][0]["encontro_id"], second["encontros"][0]["encontro_id"])
        self.assertEqual(second["encontros"][0]["motivo"], "encontro_ja_processado")

    def test_npc_novo_na_mesma_cena_consumira_so_um_gate_novo(self):
        cena_mundo.open_scene(
            self.repo,
            scene_id="elenco-cresce",
            npcs=["npc_a"],
            now=self.now,
        )
        self.assertEqual(self._draws(), 1)
        result = cena_mundo.open_scene(
            self.repo,
            scene_id="elenco-cresce",
            npcs=["npc_a", "npc_b"],
            now=self.now,
        )
        self.assertEqual(self._draws(), 2)
        by_id = {item["npc_id"]: item for item in result["encontros"]}
        self.assertEqual(by_id["npc_a"]["motivo"], "encontro_ja_processado")
        self.assertEqual(by_id["npc_b"]["motivo"], "gate_sem_oportunidade")

    def test_sem_gatilho_e_opcoes_locais_incompletas_falham(self):
        with self.assertRaises(cena_mundo.SceneGateError):
            cena_mundo.open_scene(self.repo, scene_id="vazia")
        with self.assertRaises(cena_mundo.SceneGateError):
            cena_mundo.open_scene(
                self.repo,
                scene_id="local-incompleto",
                place="local_teste",
                action="entrar",
            )

    def test_limite_de_npcs_e_duro(self):
        refs = ["npc_a"] * (cena_mundo.MAX_SCENE_NPCS + 1)
        with self.assertRaises(cena_mundo.SceneGateError):
            cena_mundo.open_scene(
                self.repo,
                scene_id="grande-demais",
                npcs=refs,
                now=self.now,
            )

    def test_parser_aceita_varios_npcs_em_uma_unica_chamada(self):
        args = cena_mundo.build_parser().parse_args(
            [
                "abrir",
                "--cena-id",
                "s009",
                "--npc",
                "npc_a",
                "--npc",
                "npc_b",
            ]
        )
        self.assertEqual(args.npc, ["npc_a", "npc_b"])


if __name__ == "__main__":
    unittest.main()
