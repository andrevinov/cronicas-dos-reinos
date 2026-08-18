from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"

spec = importlib.util.spec_from_file_location("agentes_leves", TOOLS / "agentes_leves.py")
light = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(light)

spec2 = importlib.util.spec_from_file_location("direcoes_mundo_light_test", TOOLS / "direcoes_mundo.py")
low = importlib.util.module_from_spec(spec2)
assert spec2.loader is not None
spec2.loader.exec_module(low)


class AgentesLevesRepositoryTest(unittest.TestCase):
    def test_repositorio_real_valida_tres_agentes_leves(self):
        result = light.validate_repo(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["quantidade"], 3)

    def test_status_real_nao_abre_fragmentos(self):
        result = light.status_view(ROOT)
        self.assertEqual(
            result["fontes_lidas"],
            [
                "narrador/agentes-leves/index.yaml",
                "narrador/agentes-leves/estado.yaml",
                "estado/tempo.yaml",
            ],
        )
        self.assertNotIn("narrador/agentes-leves/luath.yaml", result["fontes_lidas"])

    def test_consulta_de_silva_e_fragmentada(self):
        result = light.load_agent(ROOT, "Silva")
        self.assertEqual(result["agente_leve_id"], "silva_elkwood")
        self.assertEqual(
            result["fontes_lidas"],
            [
                "narrador/agentes-leves/index.yaml",
                "narrador/agentes-leves/estado.yaml",
                "narrador/agentes-leves/silva_elkwood.yaml",
            ],
        )


class AgentesLevesSyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "narrador/agentes-leves").mkdir(parents=True)
        (self.repo / "narrador/mundo").mkdir(parents=True)
        (self.repo / "estado").mkdir(parents=True)
        (self.repo / "fontes").mkdir(parents=True)
        (self.repo / "fontes/canone.md").write_text(
            "Rotina comprovada. Objetivo comprovado. Iniciativa comprovada.\n",
            encoding="utf-8",
        )
        self._yaml(
            "estado/tempo.yaml",
            {
                "schema_tempo": 1,
                "natureza": "tempo_atual",
                "data_atual": "12 Eleasis, 1372 DR",
                "hora_aproximada": "08:00 de 12 Eleasis",
            },
        )
        self._yaml(
            "narrador/mundo/estado.yaml",
            {
                "schema_estado_mundo": 1,
                "natureza": "controle_reservado",
                "processado_ate": {"data": "10 Eleasis, 1372 DR", "hora": "17:42"},
                "pendencias": [],
                "concluidas_recentes": [],
            },
        )
        self._yaml(
            "narrador/agentes-leves/index.yaml",
            {
                "schema_agentes_leves": 1,
                "natureza": "reservado",
                "orcamento": {
                    "max_novas_por_checkpoint": 1,
                    "max_pendencias_abertas": 2,
                    "ordenacao": "mais_atrasado_prioridade_id",
                },
                "agentes": {
                    "a": self._meta("A", 1, "10 Eleasis, 1372 DR"),
                    "b": self._meta("B", 3, "11 Eleasis, 1372 DR"),
                    "c": self._meta("C", 2, "11 Eleasis, 1372 DR"),
                },
            },
        )
        self._yaml(
            "narrador/agentes-leves/estado.yaml",
            {
                "schema_estado_agentes_leves": 1,
                "natureza": "controle_reservado",
                "agentes": {
                    "a": self._state("10 Eleasis, 1372 DR"),
                    "b": self._state("11 Eleasis, 1372 DR"),
                    "c": self._state("11 Eleasis, 1372 DR"),
                },
            },
        )
        for agent_id, name in (("a", "A"), ("b", "B"), ("c", "C")):
            self._yaml(
                f"narrador/agentes-leves/{agent_id}.yaml",
                {
                    "schema_agente_leve": 1,
                    "natureza": "reservado",
                    "id": agent_id,
                    "nome": name,
                    "perfil_operacional": "recorrente_leve",
                    "rotina_padrao": self._evidence("Rotina comprovada."),
                    "objetivo_atual": self._evidence("Objetivo comprovado."),
                    "iniciativas_possiveis": [
                        {"descricao": "Pode agir.", **self._evidence_fields("Iniciativa comprovada.")}
                    ],
                    "regra_de_reavaliacao": "Rotina é o padrão.",
                    "fontes_canonicas": ["fontes/canone.md"],
                },
            )
        (self.repo / "estado/estado-atual.yaml").write_text("sentinela: intacta\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def _yaml(self, rel, value):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _meta(self, name, priority, date):
        return {
            "nome": name,
            "perfil_operacional": "recorrente_leve",
            "estado": "ativo",
            "prioridade": priority,
            "intervalo_dias": 3,
            "inicio": {"data": date, "hora": "06:00"},
            "arquivo": f"narrador/agentes-leves/{name.lower()}.yaml",
        }

    def _state(self, date):
        return {
            "estado": "ativo",
            "proxima_avaliacao": {"data": date, "hora": "06:00"},
        }

    def _evidence_fields(self, evidence):
        return {"fonte": "fontes/canone.md", "evidencia": evidence}

    def _evidence(self, evidence):
        return {"descricao": "Texto operacional.", **self._evidence_fields(evidence)}

    def test_orcamento_escolhe_um_e_prioriza_mais_atrasado(self):
        result = light.process_checkpoint(self.repo)
        self.assertEqual(result["agentes_leves_reconsiderar"], ["a"])
        self.assertEqual(result["adiados_por_orcamento"], ["b", "c"])

    def test_mesma_data_usa_prioridade_como_desempate(self):
        state = yaml.safe_load((self.repo / light.STATE).read_text(encoding="utf-8"))
        state["agentes"]["a"]["proxima_avaliacao"] = {"data": "11 Eleasis, 1372 DR", "hora": "06:00"}
        self._yaml(light.STATE.as_posix(), state)
        result = light.process_checkpoint(self.repo)
        self.assertEqual(result["agentes_leves_reconsiderar"], ["b"])

    def test_duas_pendencias_abertas_bloqueiam_novas(self):
        world = yaml.safe_load((self.repo / light.mundo.WORLD_STATE_PATH).read_text(encoding="utf-8"))
        world["pendencias"] = [
            {"id": "x", "tipo": "reavaliar_agente_leve", "agente_leve": "b", "agentes_afetados": [], "disparado_em": {"data": "11 Eleasis, 1372 DR", "hora": "06:00"}},
            {"id": "y", "tipo": "reavaliar_agente_leve", "agente_leve": "c", "agentes_afetados": [], "disparado_em": {"data": "11 Eleasis, 1372 DR", "hora": "06:00"}},
        ]
        self._yaml(light.mundo.WORLD_STATE_PATH.as_posix(), world)
        result = light.process_checkpoint(self.repo)
        self.assertEqual(result["novas_pendencias"], [])
        self.assertIn("a", result["adiados_por_orcamento"])

    def test_intervalos_perdidos_sao_condensados(self):
        result = light.process_checkpoint(self.repo)
        self.assertEqual(result["agentes_leves_reconsiderar"], ["a"])
        state = yaml.safe_load((self.repo / light.STATE).read_text(encoding="utf-8"))
        next_a = state["agentes"]["a"]["proxima_avaliacao"]
        self.assertGreater(
            light.mundo.parse_instant(next_a["data"], next_a["hora"]),
            light.mundo.parse_instant("12 Eleasis, 1372 DR", "08:00"),
        )

    def test_retry_repara_estado_sem_duplicar_pendencia(self):
        due = light.mundo.parse_instant("10 Eleasis, 1372 DR", "06:00")
        pid = light._pending_id("a", due)
        world = yaml.safe_load((self.repo / light.mundo.WORLD_STATE_PATH).read_text(encoding="utf-8"))
        world["pendencias"] = [
            {"id": pid, "tipo": "reavaliar_agente_leve", "agente_leve": "a", "agentes_afetados": [], "disparado_em": {"data": "10 Eleasis, 1372 DR", "hora": "06:00"}}
        ]
        self._yaml(light.mundo.WORLD_STATE_PATH.as_posix(), world)
        result = light.process_checkpoint(self.repo)
        self.assertNotIn("a", result["agentes_leves_reconsiderar"])
        state = yaml.safe_load((self.repo / light.STATE).read_text(encoding="utf-8"))
        self.assertNotEqual(state["agentes"]["a"]["proxima_avaliacao"]["data"], "10 Eleasis, 1372 DR")

    def test_avaliacao_nao_toca_estado_publico(self):
        before = (self.repo / "estado/estado-atual.yaml").read_bytes()
        light.process_checkpoint(self.repo)
        self.assertEqual((self.repo / "estado/estado-atual.yaml").read_bytes(), before)

    def test_validacao_rejeita_evidencia_inventada(self):
        path = self.repo / "narrador/agentes-leves/a.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["objetivo_atual"]["evidencia"] = "Isto não existe."
        self._yaml("narrador/agentes-leves/a.yaml", data)
        result = light.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("evidência não localizada", result["erros"][0])


class GateDeAmanhecerTest(unittest.TestCase):
    def test_checkpoint_diurno_nao_consulta_agentes_leves(self):
        agenda = {"hora_amanhecer": "06:00"}
        start = light.mundo.parse_instant("10 Eleasis, 1372 DR", "08:00")
        end = light.mundo.parse_instant("10 Eleasis, 1372 DR", "12:00")
        self.assertFalse(low._crossed_dawn(agenda, start, end))

    def test_cruzar_amanhecer_habilita_camadas_leves(self):
        agenda = {"hora_amanhecer": "06:00"}
        start = light.mundo.parse_instant("10 Eleasis, 1372 DR", "23:00")
        end = light.mundo.parse_instant("11 Eleasis, 1372 DR", "07:00")
        self.assertTrue(low._crossed_dawn(agenda, start, end))


if __name__ == "__main__":
    unittest.main()
