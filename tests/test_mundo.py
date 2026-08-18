from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "ferramentas" / "mundo.py"
spec = importlib.util.spec_from_file_location("mundo", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)

REPO = Path(__file__).parents[1]


class MundoRepositoryTest(unittest.TestCase):
    def test_repositorio_real_tem_motor_consistente(self):
        result = mod.check_repo(REPO)
        self.assertTrue(result["ok"], result["erros"])

    def test_status_real_nao_abre_fragmentos_de_agentes(self):
        result = mod.status_view(REPO)
        self.assertIn("estado/tempo.yaml", result["fontes_lidas"])
        self.assertIn("narrador/mundo/agenda.yaml", result["fontes_lidas"])
        self.assertFalse(
            any(
                path.startswith("narrador/agentes/") and path != "narrador/agentes/index.yaml"
                for path in result["fontes_lidas"]
            )
        )


class MundoSyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "estado").mkdir(parents=True)
        (self.repo / "narrador/mundo").mkdir(parents=True)
        (self.repo / "narrador/agentes").mkdir(parents=True)
        (self.repo / "narrador/agentes/index.yaml").write_text(
            """schema_agentes: 2
natureza: reservado
agentes:
  red_sail:
    nome: Red Sail
    tipo: faccao
    estado: ativo
    presenca: distribuida
    atuacao_local: estrutura_local
    arquivo: narrador/agentes/red_sail.yaml
  kurobane_jinzaburo:
    nome: Kurobane Jinzaburō
    tipo: npc
    estado: ativo
    presenca: presente
    atuacao_local: exige_presenca_fisica
    arquivo: narrador/agentes/kurobane_jinzaburo.yaml
""",
            encoding="utf-8",
        )
        self.write_time("10 Eleasis, 1372 DR", "17:42 de 10 Eleasis")
        (self.repo / "narrador/mundo/agenda.yaml").write_text(
            """schema_agenda_mundo: 1
natureza: reservado
hora_amanhecer: '06:00'
reavaliacoes:
  red_sail:
    cadencia: amanhecer
    intervalo_dias: 1
    inicio: '11 Eleasis, 1372 DR'
    motivo: Reavaliar busca ativa.
agendamentos: []
""",
            encoding="utf-8",
        )
        (self.repo / "narrador/mundo/estado.yaml").write_text(
            """schema_estado_mundo: 1
natureza: controle_reservado
processado_ate:
  data: '10 Eleasis, 1372 DR'
  hora: '17:42'
pendencias: []
concluidas_recentes: []
""",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def write_time(self, date: str, hour: str) -> None:
        (self.repo / "estado/tempo.yaml").write_text(
            f"schema_tempo: 1\ndata_atual: '{date}'\nhora_aproximada: '{hour}'\n",
            encoding="utf-8",
        )

    def test_nada_vencido_nao_le_indice_nem_fragmento_de_agente(self):
        result = mod.process_to_canonical(self.repo)
        self.assertFalse(result["alterou"])
        self.assertNotIn("narrador/agentes/index.yaml", result["fontes_lidas"])
        self.assertFalse(any(path.endswith("red_sail.yaml") for path in result["fontes_lidas"]))

    def test_amanhecer_gera_pendencia_sem_abrir_fragmento(self):
        self.write_time("11 Eleasis, 1372 DR", "06:30 de 11 Eleasis")
        result = mod.process_dawn(self.repo)
        self.assertTrue(result["alterou"])
        self.assertEqual(result["agentes_reconsiderar"], ["red_sail"])
        self.assertEqual(len(result["novas_pendencias"]), 1)
        self.assertIn("narrador/agentes/index.yaml", result["fontes_lidas"])
        self.assertFalse(any(path.endswith("red_sail.yaml") for path in result["fontes_lidas"]))

    def test_mesmo_instante_nao_processa_mundo_duas_vezes(self):
        self.write_time("11 Eleasis, 1372 DR", "06:30 de 11 Eleasis")
        first = mod.process_to_canonical(self.repo)
        second = mod.process_to_canonical(self.repo)
        self.assertEqual(len(first["novas_pendencias"]), 1)
        self.assertFalse(second["alterou"])
        self.assertEqual(mod.pending_view(self.repo)["quantidade"], 1)

    def test_avanco_atravessa_dois_amanheceres(self):
        self.write_time("12 Eleasis, 1372 DR", "07:00 de 12 Eleasis")
        result = mod.process_dawn(self.repo)
        self.assertEqual(len(result["novas_pendencias"]), 2)
        dates = [item["disparado_em"]["data"] for item in result["novas_pendencias"]]
        self.assertEqual(dates, ["11 Eleasis, 1372 DR", "12 Eleasis, 1372 DR"])

    def test_amanhecer_nao_processa_agendamento_do_meio_dia(self):
        agenda = mod.load_agenda(self.repo)
        agenda["agendamentos"] = [
            {
                "id": "saida",
                "tipo": "movimento",
                "agente": "kurobane_jinzaburo",
                "em": {"data": "11 Eleasis, 1372 DR", "hora": "12:00"},
                "motivo": "Sair da cidade.",
            }
        ]
        (self.repo / mod.AGENDA_PATH).write_text(mod._dump(agenda), encoding="utf-8")
        self.write_time("11 Eleasis, 1372 DR", "17:00 de 11 Eleasis")

        dawn = mod.process_dawn(self.repo)
        self.assertEqual(
            [item["tipo"] for item in dawn["novas_pendencias"]],
            ["reavaliar_agente"],
        )
        later = mod.process_to_canonical(self.repo)
        self.assertEqual(
            [item["tipo"] for item in later["novas_pendencias"]],
            ["movimento"],
        )

    def test_concluir_remove_pendencia_sem_reexecutar_agente(self):
        self.write_time("11 Eleasis, 1372 DR", "06:30 de 11 Eleasis")
        result = mod.process_to_canonical(self.repo)
        pending_id = result["novas_pendencias"][0]["id"]
        done = mod.conclude(self.repo, pending_id, "avaliado sem mudança")
        self.assertEqual(done["pendencias_restantes"], 0)
        state = mod.load_world_state(self.repo)
        self.assertEqual(state["concluidas_recentes"][-1]["id"], pending_id)

    def test_check_rejeita_agente_inexistente_na_agenda(self):
        agenda = mod.load_agenda(self.repo)
        agenda["reavaliacoes"]["fantasma"] = {
            "cadencia": "amanhecer",
            "intervalo_dias": 1,
            "inicio": "11 Eleasis, 1372 DR",
            "motivo": "teste",
        }
        (self.repo / mod.AGENDA_PATH).write_text(mod._dump(agenda), encoding="utf-8")
        result = mod.check_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertTrue(any("fantasma" in error for error in result["erros"]))

    def test_calendario_atravessa_eleasis_para_eleint(self):
        end = mod.WorldInstant(
            mod.parse_instant("30 Eleasis, 1372 DR", "23:59").minute + 2
        )
        self.assertEqual(
            mod.instant_parts(end),
            {"data": "1 Eleint, 1372 DR", "hora": "00:01"},
        )


if __name__ == "__main__":
    unittest.main()
