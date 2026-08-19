from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import interacoes_mundo
import mundo
import oportunidades


class ResolucaoNpcEncontroSyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.now = mundo.parse_instant("11 Eleasis, 1372 DR", "09:00")
        self._write(
            "narrador/oportunidades/index.yaml",
            {
                "schema_oportunidades": 1,
                "natureza": "reservado",
                "semente": "resolver-npc-teste",
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
                    "nera_vell": {
                        "nome": "Nera Vell",
                        "estado": "ativo",
                        "arquivo": "narrador/oportunidades/perfis/nera_vell.yaml",
                    },
                    "kethra_dunn": {
                        "nome": "Kethra Dunn",
                        "estado": "ativo",
                        "arquivo": "narrador/oportunidades/perfis/kethra_dunn.yaml",
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
        for npc_id, name in (("nera_vell", "Nera Vell"), ("kethra_dunn", "Kethra Dunn")):
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
                            "id": "necessidade",
                            "tipo": "favor",
                            "semente": "Uma necessidade coerente pode surgir.",
                            "janela": {"tipo": "a_qualquer_momento"},
                            "pode_reabrir": False,
                            "consequencia_sem_ren": "A vida do NPC continua sem Ren.",
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
                "quantidade": 6,
                "relacoes": {
                    "nera_vell": {"nome": "Nera Vell"},
                    "kethra_dunn": {"nome": "Kethra Dunn"},
                    "colm_dunn": {"nome": "Colm Dunn"},
                    "tavin_vell": {"nome": "Tavin Vell"},
                    "sella_rove": {"nome": "Sella Rove"},
                    "velha_sella": {"nome": "Velha Sella"},
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

    def index(self):
        return oportunidades.load_index(self.repo)

    def test_id_exato_de_perfil_custa_so_indice_de_oportunidades(self):
        result = interacoes_mundo.resolve_encounter_npc(
            self.repo, "nera_vell", self.index()
        )
        self.assertEqual(result["npc_id"], "nera_vell")
        self.assertEqual(result["resolucao"], "id_exato")
        self.assertEqual(
            result["fontes_lidas"],
            [oportunidades.INDEX.as_posix()],
        )

    def test_nome_completo_normalizado_nao_precisa_abrir_relacoes(self):
        result = interacoes_mundo.resolve_encounter_npc(
            self.repo, "NÉRA Vell", self.index()
        )
        self.assertEqual(result["npc_id"], "nera_vell")
        self.assertEqual(result["resolucao"], "nome_ou_id_normalizado")
        self.assertEqual(
            result["fontes_lidas"],
            [oportunidades.INDEX.as_posix()],
        )

    def test_alias_nera_resolve_para_id_canonico(self):
        result = interacoes_mundo.resolve_encounter_npc(
            self.repo, "nera", self.index()
        )
        self.assertEqual(result["npc_id"], "nera_vell")
        self.assertEqual(result["resolucao"], "alias_univoco")
        self.assertEqual(
            result["fontes_lidas"],
            [oportunidades.INDEX.as_posix(), oportunidades.RELATIONS.as_posix()],
        )

    def test_alias_dunn_e_ambiguo_globalmente(self):
        with self.assertRaises(interacoes_mundo.IntegrationError) as ctx:
            interacoes_mundo.resolve_encounter_npc(self.repo, "dunn", self.index())
        message = str(ctx.exception)
        self.assertIn("ambígua", message)
        self.assertIn("colm_dunn", message)
        self.assertIn("kethra_dunn", message)

    def test_alias_sella_nao_escolhe_arbitrariamente(self):
        with self.assertRaises(interacoes_mundo.IntegrationError) as ctx:
            interacoes_mundo.resolve_encounter_npc(self.repo, "sella", self.index())
        message = str(ctx.exception)
        self.assertIn("sella_rove", message)
        self.assertIn("velha_sella", message)

    def test_typo_desconhecido_falha_e_sugere(self):
        with self.assertRaises(interacoes_mundo.IntegrationError) as ctx:
            interacoes_mundo.resolve_encounter_npc(self.repo, "nrea", self.index())
        message = str(ctx.exception)
        self.assertIn("NPC desconhecido", message)
        self.assertIn("nera_vell", message)
        self.assertIn("nunca equivale", message)

    def test_npc_canonico_sem_perfil_continua_interacao_normal(self):
        result = interacoes_mundo.encounter_event(
            self.repo,
            "tavin_vell",
            now=self.now,
            encounter_id="tavin-cena",
        )
        self.assertEqual(result["resultado"], "interacao_normal")
        self.assertEqual(result["motivo"], "npc_sem_perfil_ativo")
        self.assertEqual(result["npc_id"], "tavin_vell")
        self.assertIn(oportunidades.RELATIONS.as_posix(), result["fontes_lidas"])

    def test_npc_canonico_sem_perfil_tambem_aceita_alias_univoco(self):
        result = interacoes_mundo.encounter_event(
            self.repo,
            "tavin",
            now=self.now,
            encounter_id="tavin-alias",
        )
        self.assertEqual(result["motivo"], "npc_sem_perfil_ativo")
        self.assertEqual(result["npc_id"], "tavin_vell")
        self.assertEqual(result["npc_id_recebido"], "tavin")
        self.assertEqual(result["resolucao_id"], "alias_univoco")

    def test_desconhecido_nao_pode_virar_falso_sem_perfil(self):
        with self.assertRaises(interacoes_mundo.IntegrationError):
            interacoes_mundo.encounter_event(
                self.repo,
                "nrea",
                now=self.now,
                encounter_id="typo",
            )

    def test_alias_ativo_usa_id_canonico_no_gate(self):
        result = interacoes_mundo.encounter_event(
            self.repo,
            "nera",
            now=self.now,
            encounter_id="cena-nera",
        )
        self.assertEqual(result["npc_id"], "nera_vell")
        self.assertEqual(result["npc_id_recebido"], "nera")
        self.assertEqual(result["resolucao_id"], "alias_univoco")
        state = oportunidades.load_state(self.repo, self.index())
        for pending in state["pendencias_avaliacao"].values():
            self.assertEqual(pending["npc_id"], "nera_vell")


class ResolucaoNpcEncontroRepositoryTest(unittest.TestCase):
    def test_caso_real_nera_agora_resolve(self):
        index = oportunidades.load_index(ROOT)
        result = interacoes_mundo.resolve_encounter_npc(ROOT, "nera", index)
        self.assertEqual(result["npc_id"], "nera_vell")
        self.assertEqual(result["resolucao"], "alias_univoco")
        self.assertEqual(len(result["fontes_lidas"]), 2)

    def test_caso_real_nrea_agora_falha_em_vez_de_sumir(self):
        index = oportunidades.load_index(ROOT)
        with self.assertRaises(interacoes_mundo.IntegrationError) as ctx:
            interacoes_mundo.resolve_encounter_npc(ROOT, "nrea", index)
        self.assertIn("nera_vell", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
