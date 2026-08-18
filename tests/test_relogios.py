from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

TOOLS = Path(__file__).parents[1] / "ferramentas"
sys.path.insert(0, str(TOOLS))

RELOGIOS_PATH = TOOLS / "relogios.py"
spec = importlib.util.spec_from_file_location("relogios", RELOGIOS_PATH)
relogios = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(relogios)

DIRECOES_MUNDO_PATH = TOOLS / "direcoes_mundo.py"
spec2 = importlib.util.spec_from_file_location("direcoes_mundo_relogios", DIRECOES_MUNDO_PATH)
direcoes_mundo = importlib.util.module_from_spec(spec2)
assert spec2.loader is not None
spec2.loader.exec_module(direcoes_mundo)


ROOT = Path(__file__).parents[1]


class RelogiosRepositoryTest(unittest.TestCase):
    def test_repositorio_real_tem_sete_relogios_todos_vinculados(self):
        result = relogios.validate_repo(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["quantidade"], 7)
        self.assertEqual(result["pressoes_ativas"], 3)
        self.assertEqual(result["consequencias_resolvidas"], 4)

    def test_red_sail_recebe_somente_as_tres_pressoes_ativas_sem_abrir_fragmentos(self):
        result = relogios.by_agent(ROOT, "red_sail")
        self.assertEqual(
            result["pressoes_ativas"],
            [
                "exposicao_do_contato_de_kethra",
                "exposicao_do_contato_de_pell",
                "rastro_fraco_no_pomar",
            ],
        )
        self.assertEqual(
            result["operacoes_com_pressao_ativa"],
            ["red_sail_reconstruir_cadeia_colm"],
        )
        self.assertEqual(result["fontes_lidas"], ["narrador/relogios/vinculos.yaml"])

    def test_consequencias_resolvidas_nao_competem_com_pressoes_ativas(self):
        result = relogios.by_agent(ROOT, "red_sail", include_resolved=True)
        self.assertIn("resposta_red_sail_ao_corpo", result["consequencias_resolvidas"])
        self.assertIn("relatorio_pell_ponto_morto", result["consequencias_resolvidas"])
        self.assertNotIn("resposta_red_sail_ao_corpo", result["pressoes_ativas"])

    def test_consulta_exata_de_um_relogio_abre_so_roteador_indice_e_fragmento(self):
        result = relogios.show(ROOT, "rastro_fraco_no_pomar")
        self.assertEqual(
            result["fontes_lidas"],
            [
                "narrador/relogios/vinculos.yaml",
                "narrador/relogios/index.yaml",
                "narrador/relogios/rastro_fraco_no_pomar.yaml",
            ],
        )
        self.assertEqual(result["vinculo"]["agente_principal"], "red_sail")
        self.assertEqual(result["vinculo"]["estado"], "ativo")


class RelogiosSyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self._make_repo()

    def tearDown(self):
        self.temp.cleanup()

    def _write_yaml(self, rel: str, value):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=110),
            encoding="utf-8",
        )

    def _read_yaml(self, rel: str):
        return yaml.safe_load((self.repo / rel).read_text(encoding="utf-8"))

    def _agent_index(self):
        return {
            "schema_agentes": 2,
            "natureza": "reservado",
            "agentes": {
                "red_sail": {
                    "nome": "Red Sail",
                    "tipo": "faccao",
                    "estado": "ativo",
                    "presenca": "distribuida",
                    "atuacao_local": "estrutura_local",
                    "arquivo": "narrador/agentes/red_sail.yaml",
                }
            },
        }

    def _clock(self, clock_id: str, *, progress: int, limit: int, state: str, kind: str, agent="red_sail", operation="busca"):
        return {
            "schema_relogio": 1,
            "id": clock_id,
            "natureza": "reservado",
            "vinculo_agencial": {
                "tipo": kind,
                "estado": state,
                "operacao": operation,
                "agente_principal": agent,
                "papel_agente": "explorador" if state == "ativo" else "origem",
                "agentes_relacionados": [],
            },
            "relogio": {
                "titulo": clock_id.replace("_", " "),
                "progresso": progress,
                "limite": limit,
                "descricao": "Pressão sintética.",
                "consequencia_no_limite": "A consequência sintética ocorre.",
            },
            "eventos": [],
        }

    def _make_repo(self):
        self._write_yaml("narrador/agentes/index.yaml", self._agent_index())
        self._write_yaml(
            "narrador/relogios/index.yaml",
            {
                "schema_relogios": 1,
                "natureza": "reservado",
                "relogios": {
                    "busca": {
                        "arquivo": "narrador/relogios/busca.yaml",
                        "sessao_ultima_atualizacao": 8,
                    },
                    "feito": {
                        "arquivo": "narrador/relogios/feito.yaml",
                        "sessao_ultima_atualizacao": 8,
                    },
                },
                "quantidade": 2,
            },
        )
        self._write_yaml(
            "narrador/relogios/busca.yaml",
            self._clock("busca", progress=2, limit=4, state="ativo", kind="pressao"),
        )
        done = self._clock(
            "feito",
            progress=4,
            limit=4,
            state="resolvido",
            kind="consequencia",
        )
        self._write_yaml("narrador/relogios/feito.yaml", done)
        relogios.sync(self.repo)

    def test_sincronizacao_e_idempotente(self):
        first = relogios.sync(self.repo)
        second = relogios.sync(self.repo)
        self.assertFalse(first["roteador_alterado"])
        self.assertFalse(second["roteador_alterado"])
        self.assertEqual(second["resolvidos_agora"], [])

    def test_pressao_que_alcanca_limite_vira_consequencia_resolvida(self):
        doc = self._read_yaml("narrador/relogios/busca.yaml")
        doc["relogio"]["progresso"] = 4
        self._write_yaml("narrador/relogios/busca.yaml", doc)

        result = relogios.sync(self.repo)
        self.assertEqual(result["resolvidos_agora"], ["busca"])
        updated = self._read_yaml("narrador/relogios/busca.yaml")
        self.assertEqual(updated["vinculo_agencial"]["estado"], "resolvido")
        self.assertEqual(updated["vinculo_agencial"]["tipo"], "consequencia")
        by_agent = relogios.by_agent(self.repo, "red_sail", include_resolved=True)
        self.assertNotIn("busca", by_agent["pressoes_ativas"])
        self.assertIn("busca", by_agent["consequencias_resolvidas"])

    def test_agente_inexistente_no_vinculo_falha(self):
        doc = self._read_yaml("narrador/relogios/busca.yaml")
        doc["vinculo_agencial"]["agente_principal"] = "ninguem"
        self._write_yaml("narrador/relogios/busca.yaml", doc)
        result = relogios.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("agentes inexistentes", result["erros"][0])

    def test_pressao_ativa_sem_operacao_falha(self):
        doc = self._read_yaml("narrador/relogios/busca.yaml")
        doc["vinculo_agencial"]["operacao"] = None
        self._write_yaml("narrador/relogios/busca.yaml", doc)
        result = relogios.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("pressão ativa exige operação", result["erros"][0])

    def test_roteador_derivado_desatualizado_falha_validacao(self):
        router = self._read_yaml("narrador/relogios/vinculos.yaml")
        router["pressoes_ativas"] = 99
        self._write_yaml("narrador/relogios/vinculos.yaml", router)
        result = relogios.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("roteador de vínculos está desatualizado", result["erros"][0])


class RelogiosWorldIntegrationTest(unittest.TestCase):
    def test_orquestrador_sincroniza_relogios_antes_de_direcoes(self):
        repo = Path("/tmp/repo-sintetico")
        order = []

        def sync_clocks(_repo):
            order.append("relogios")
            return {
                "ok": True,
                "pressoes_ativas": 3,
                "consequencias_resolvidas": 4,
                "resolvidos_agora": [],
                "roteador_alterado": False,
                "fontes_expostas": [],
            }

        def load_directions(_repo):
            order.append("direcoes")
            return {"direcoes": {}}

        world_state = {
            "processado_ate": {"data": "10 Eleasis, 1372 DR", "hora": "17:42"},
            "pendencias": [],
            "concluidas_recentes": [],
        }
        canonical = direcoes_mundo.mundo.parse_instant("10 Eleasis, 1372 DR", "17:42")

        with (
            mock.patch.object(direcoes_mundo.ciclo_npcs, "configured", return_value=False),
            mock.patch.object(direcoes_mundo.relogios, "configured", return_value=True),
            mock.patch.object(direcoes_mundo.relogios, "sync", side_effect=sync_clocks),
            mock.patch.object(direcoes_mundo.direcoes, "load_index", side_effect=load_directions),
            mock.patch.object(
                direcoes_mundo.direcoes,
                "load_state",
                return_value={"direcoes": {}},
            ),
            mock.patch.object(direcoes_mundo.mundo, "load_world_state", return_value=world_state),
            mock.patch.object(
                direcoes_mundo.mundo,
                "load_agenda",
                return_value={"hora_amanhecer": "06:00", "reavaliacoes": {}, "agendamentos": []},
            ),
            mock.patch.object(
                direcoes_mundo.mundo,
                "load_canonical_time",
                return_value=(canonical, {}),
            ),
            mock.patch.object(direcoes_mundo, "_entries_configured", return_value=False),
            mock.patch.object(direcoes_mundo, "_light_agents_configured", return_value=False),
        ):
            result = direcoes_mundo.process_checkpoint(repo)

        self.assertEqual(order[:2], ["relogios", "direcoes"])
        self.assertEqual(result["relogios"]["pressoes_ativas"], 3)


if __name__ == "__main__":
    unittest.main()
