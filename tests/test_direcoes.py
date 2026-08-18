from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import checkpoint
import direcoes
import direcoes_mundo
import mundo


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DirectionsRepositoryTest(unittest.TestCase):
    def test_repositorio_real_valida_duas_direcoes(self):
        result = direcoes.validate_repo(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["quantidade"], 2)

    def test_consulta_shin_kozakura_e_fragmentada(self):
        result = direcoes.show(ROOT, "Shin-Kozakura")
        self.assertEqual(result["direcao_id"], "shin_kozakura")
        self.assertEqual(
            result["fontes_lidas"],
            [
                "narrador/direcoes/index.yaml",
                "narrador/direcoes/estado.yaml",
                "narrador/direcoes/shin_kozakura.yaml",
            ],
        )
        self.assertNotIn("narrador/direcoes/ponte_de_kozakura.yaml", result["fontes_lidas"])
        self.assertNotIn("narrador/ponte-de-kozakura/shin-kozakura.md", result["fontes_lidas"])

    def test_estado_inicial_nao_avanca_historia_retroativamente(self):
        status = direcoes.status_view(ROOT)
        by_id = {item["id"]: item for item in status["direcoes"]}
        self.assertEqual(by_id["ponte_de_kozakura"]["estado"], "ativa")
        self.assertEqual(by_id["ponte_de_kozakura"]["marco_atual"], "coisas_plausiveis")
        self.assertEqual(by_id["shin_kozakura"]["estado"], "latente")
        self.assertEqual(by_id["shin_kozakura"]["marco_atual"], "uso_controlado")
        self.assertFalse(by_id["shin_kozakura"]["ativacao_satisfeita"])


class DirectionsSyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "narrador/direcoes").mkdir(parents=True)
        (self.repo / "fontes").mkdir(parents=True)
        (self.repo / "estado").mkdir(parents=True)
        self._yaml(
            "narrador/direcoes/index.yaml",
            {
                "schema_direcoes": 1,
                "natureza": "reservado",
                "direcoes": {
                    "ponte": {
                        "nome": "Ponte",
                        "arquivo": "narrador/direcoes/ponte.yaml",
                        "avaliacao": {"cadencia": "amanhecer", "intervalo_dias": 2, "inicio": "12 Eleasis, 1372 DR"},
                        "ativacao": None,
                    },
                    "bairro": {
                        "nome": "Bairro",
                        "arquivo": "narrador/direcoes/bairro.yaml",
                        "avaliacao": {"cadencia": "amanhecer", "intervalo_dias": 7, "inicio": "11 Eleasis, 1372 DR"},
                        "ativacao": {"depende_de": {"direcao": "ponte", "marco": "controle_perdido"}},
                    },
                },
            },
        )
        self._yaml(
            "narrador/direcoes/estado.yaml",
            {
                "schema_estado_direcoes": 1,
                "natureza": "controle_reservado",
                "direcoes": {
                    "ponte": {"estado": "ativa", "marco_atual": "pistas", "marcos_concluidos": [], "historico_recente": []},
                    "bairro": {"estado": "latente", "marco_atual": "uso", "marcos_concluidos": [], "historico_recente": []},
                },
            },
        )
        (self.repo / "fontes/ponte.md").write_text("## Pistas\n## Controle perdido\n", encoding="utf-8")
        (self.repo / "fontes/bairro.md").write_text("## Uso\n## Cultura\n", encoding="utf-8")
        self._direction(
            "ponte",
            "Ponte",
            "fontes/ponte.md",
            [("pistas", "## Pistas"), ("controle_perdido", "## Controle perdido")],
        )
        self._direction(
            "bairro",
            "Bairro",
            "fontes/bairro.md",
            [("uso", "## Uso"), ("cultura", "## Cultura")],
        )
        self._yaml(
            "estado/tempo.yaml",
            {
                "schema_tempo": 1,
                "natureza": "tempo_atual",
                "data_atual": "10 Eleasis, 1372 DR",
                "hora_aproximada": "17:42 de 10 Eleasis",
            },
        )

    def tearDown(self):
        self.temp.cleanup()

    def _yaml(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def _direction(self, did: str, name: str, source: str, milestones: list[tuple[str, str]]) -> None:
        data = {
            "schema_direcao": 1,
            "natureza": "reservado",
            "id": did,
            "nome": name,
            "estatuto": "canonica_obrigatoria",
            "principio": "Chegar ao destino sem prescrever a cena.",
            "fontes_canonicas": [source],
            "marcos": [
                {
                    "id": mid,
                    "ordem": i,
                    "titulo": mid,
                    "fonte": source,
                    "evidencia": evidence,
                    "criterio_para_avancar": "O mundo sustenta a passagem para a próxima fase.",
                    "guardrails": ["Não avançar por conveniência."],
                }
                for i, (mid, evidence) in enumerate(milestones, start=1)
            ],
        }
        self._yaml(f"narrador/direcoes/{did}.yaml", data)

    def test_evidencia_inventada_faz_validacao_falhar(self):
        path = self.repo / "narrador/direcoes/ponte.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["marcos"][0]["evidencia"] = "texto que não existe"
        self._yaml("narrador/direcoes/ponte.yaml", data)
        result = direcoes.validate_repo(self.repo)
        self.assertFalse(result["ok"])
        self.assertIn("não possui evidência", result["erros"][0])

    def test_avanco_e_sequencial_e_rastreavel(self):
        public = self.repo / "estado/tempo.yaml"
        before = digest(public)
        result = direcoes.advance(self.repo, "ponte", "Sessão teste", "As pistas se acumularam.")
        self.assertEqual(result["marco_concluido"], "pistas")
        self.assertEqual(result["proximo_marco"], "controle_perdido")
        self.assertEqual(before, digest(public))
        state = direcoes.load_state(self.repo)
        self.assertEqual(state["direcoes"]["ponte"]["marcos_concluidos"], ["pistas"])
        self.assertEqual(state["direcoes"]["ponte"]["historico_recente"][-1]["origem"], "Sessão teste")

    def test_bairro_nao_ativa_antes_da_dependencia(self):
        with self.assertRaises(direcoes.DirectionError):
            direcoes.activate(self.repo, "bairro", "teste", "cedo demais")

    def test_bairro_ativa_depois_do_marco_da_ponte(self):
        state = direcoes.load_state(self.repo)
        state["direcoes"]["ponte"] = {
            "estado": "concluida",
            "marco_atual": None,
            "marcos_concluidos": ["pistas", "controle_perdido"],
            "historico_recente": [],
        }
        self._yaml("narrador/direcoes/estado.yaml", state)
        result = direcoes.activate(self.repo, "bairro", "Ponte liberada", "A dependência foi cumprida.")
        self.assertEqual(result["estado"], "ativa")
        self.assertEqual(result["marco_atual"], "uso")


class DirectionsWorldIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.case = DirectionsSyntheticTest(methodName="runTest")
        self.case.setUp()
        self.repo = self.case.repo
        (self.repo / "narrador/mundo").mkdir(parents=True, exist_ok=True)
        self.case._yaml(
            "narrador/mundo/agenda.yaml",
            {
                "schema_agenda_mundo": 1,
                "natureza": "reservado",
                "hora_amanhecer": "06:00",
                "reavaliacoes": {},
                "agendamentos": [],
            },
        )
        self.case._yaml(
            "narrador/mundo/estado.yaml",
            {
                "schema_estado_mundo": 1,
                "natureza": "controle_reservado",
                "processado_ate": {"data": "10 Eleasis, 1372 DR", "hora": "17:42"},
                "pendencias": [],
                "concluidas_recentes": [],
            },
        )

    def tearDown(self):
        self.case.tearDown()

    def test_direcao_ativa_so_dispara_na_cadencia(self):
        self.case._yaml(
            "estado/tempo.yaml",
            {"schema_tempo": 1, "natureza": "tempo_atual", "data_atual": "12 Eleasis, 1372 DR", "hora_aproximada": "06:10 de 12 Eleasis"},
        )
        result = direcoes_mundo.process_checkpoint(self.repo)
        self.assertEqual(result["direcoes_reconsiderar"], ["ponte"])
        self.assertEqual(result["novas_pendencias"][0]["tipo"], "avaliar_direcao")
        self.assertEqual(result["novas_pendencias"][0]["direcao"], "ponte")
        self.assertNotIn("narrador/direcoes/ponte.yaml", result["fontes_lidas"])

    def test_pendencia_aberta_impede_repeticao_da_mesma_direcao(self):
        self.case._yaml(
            "estado/tempo.yaml",
            {"schema_tempo": 1, "natureza": "tempo_atual", "data_atual": "12 Eleasis, 1372 DR", "hora_aproximada": "06:10 de 12 Eleasis"},
        )
        first = direcoes_mundo.process_checkpoint(self.repo)
        second = direcoes_mundo.process_checkpoint(self.repo)
        self.assertEqual(len(first["novas_pendencias"]), 1)
        self.assertEqual(second["novas_pendencias"], [])

    def test_dependencia_satisfeita_gera_pendencia_de_ativacao_sem_autoativar(self):
        state = direcoes.load_state(self.repo)
        state["direcoes"]["ponte"] = {
            "estado": "concluida",
            "marco_atual": None,
            "marcos_concluidos": ["pistas", "controle_perdido"],
            "historico_recente": [],
        }
        self.case._yaml("narrador/direcoes/estado.yaml", state)
        result = direcoes_mundo.process_checkpoint(self.repo)
        records = [item for item in result["novas_pendencias"] if item["tipo"] == "ativar_direcao"]
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["direcao"], "bairro")
        self.assertEqual(direcoes.load_state(self.repo)["direcoes"]["bairro"]["estado"], "latente")

    def test_checkpoint_chama_direcoes_antes_de_mover_cursor_do_mundo(self):
        order = []
        with patch.object(checkpoint, "_world_configured", return_value=True), \
             patch.object(checkpoint, "_directions_configured", return_value=True), \
             patch.object(checkpoint.direcoes_mundo, "process_checkpoint", side_effect=lambda repo: order.append("direcoes") or {"novas_pendencias": [], "direcoes_reconsiderar": []}), \
             patch.object(checkpoint.mundo, "process_to_canonical", side_effect=lambda repo: order.append("mundo") or {"alterou": False, "novas_pendencias": [], "agentes_reconsiderar": []}):
            checkpoint.sync_world(self.repo)
        self.assertEqual(order, ["direcoes", "mundo"])


if __name__ == "__main__":
    unittest.main()
