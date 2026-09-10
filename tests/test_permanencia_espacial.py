from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

# Importar a porta instala a política de digest estável usada em produção NV-15.
import cronica  # noqa: F401,E402
import mundo  # noqa: E402
import permanencia_espacial as stay  # noqa: E402


class SpatialPermanenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "estado").mkdir(parents=True)
        (self.repo / "estado/estado-atual.yaml").write_text(
            yaml.safe_dump(
                {
                    "localizacao": {
                        "area": "circo_hooft",
                        "local_id": "circo_hooft",
                    }
                },
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        self.now = mundo.parse_instant("21 Eleasis, 1372 DR", "10:30")
        self.ecology = {
            "perfil": {"dummy": True},
            "fontes_lidas": ["cenario/ecologia-local/index.yaml"],
        }

    def tearDown(self):
        self.temp.cleanup()

    def _patches(self, *, micro_result="rotina", incident_result="rotina"):
        micro_public = {
            "resultado": micro_result,
            "ficha_ocorrencia": "loc-1",
            "fontes_lidas": ["narrador/microeventos-locais/estado.yaml"],
        }
        if micro_result == "avaliar_microevento":
            micro_public["carta"] = {
                "id": "carta_rotina",
                "nome": "Rotina local",
                "categoria": "cotidiano",
                "premissa": "Algo pequeno acontece no espaço compartilhado.",
                "atores_comuns": ["artistas"],
                "guardrails": ["não decidir ação de Ren"],
            }
        incident_public = {
            "resultado": incident_result,
            "origem": None,
            "fontes_lidas": ["narrador/incidentes-v2/estado.yaml"],
        }
        if incident_result == "avaliar_incidente":
            incident_public["incidente"] = {
                "id": "furto_local",
                "nome": "Furto",
                "tipo": "roubo",
                "severidade": "media",
                "intervencao": "opcional",
                "premissa": "Um furto se desenrola no fluxo do local.",
                "rotas_observaveis": ["observar", "intervir", "ignorar"],
                "atores_comuns": ["visitantes"],
                "guardrails": ["candidato não é fato"],
            }
        return [
            mock.patch.object(
                stay.locais,
                "resolve",
                side_effect=lambda _repo, raw: {
                    "local_id": "circo_hooft",
                    "recebido": raw,
                    "resolucao": "id_exato",
                    "nome": "Circo Hooft",
                    "fontes_lidas": ["cenario/locais/index.yaml"],
                },
            ),
            mock.patch.object(stay.mundo, "load_agenda", return_value={"hora_amanhecer": "06:00"}),
            mock.patch.object(stay.ecologia_local, "lookup_canonical", return_value=self.ecology),
            mock.patch.object(
                stay.ecologia_local,
                "activity",
                return_value={
                    "ritmo": "cheio",
                    "tags": ["circo"],
                    "canais_microevento": ["publico"],
                },
            ),
            mock.patch.object(stay.presenca_incidental, "configured", return_value=False),
            mock.patch.object(stay.microeventos_locais, "configured", return_value=True),
            mock.patch.object(
                stay.microeventos_locais,
                "plan",
                return_value={"publico": micro_public, "estado_planejado": {}, "alterou": True},
            ),
            mock.patch.object(stay.microeventos_locais, "commit_plan", return_value=True),
            mock.patch.object(stay.incidentes_mundo, "configured", return_value=True),
            mock.patch.object(
                stay.incidentes_mundo,
                "plan",
                return_value={"publico": incident_public, "estado_planejado": {}, "alterou": True},
            ),
            mock.patch.object(stay.incidentes_mundo, "commit_plan", return_value=None),
        ]

    def _run_with(self, patches, callback):
        entered = []
        try:
            for patcher in patches:
                entered.append(patcher)
                patcher.start()
            return callback()
        finally:
            for patcher in reversed(entered):
                patcher.stop()

    def test_inherits_consolidated_local_and_records_calm(self):
        patches = self._patches()

        def run():
            result = stay.prepare(self.repo, scene_id="circo-a", now=self.now)
            public = result["publico"]
            self.assertEqual(public["local_id"], "circo_hooft")
            self.assertEqual(public["estado"], "calma_espacial")
            self.assertEqual(public["incidente_local"]["resultado"], "rotina")
            self.assertFalse(public["exige_decisao_conclusao"])
            self.assertIsNone(public["pressao_primaria"])

        self._run_with(patches, run)

    def test_scene_id_change_reuses_same_period_without_reroll(self):
        patches = self._patches(micro_result="avaliar_microevento")

        def run():
            first = stay.prepare(self.repo, scene_id="circo-primeira", now=self.now)
            second = stay.prepare(self.repo, scene_id="circo-renomeada", now=self.now)
            self.assertEqual(first["publico"]["avaliacao_id"], second["publico"]["avaliacao_id"])
            self.assertEqual(first["publico"]["pressao_primaria"], second["publico"]["pressao_primaria"])
            self.assertFalse(first["publico"]["reutilizado"])
            self.assertTrue(second["publico"]["reutilizado"])
            self.assertEqual(stay.microeventos_locais.plan.call_count, 1)
            self.assertEqual(stay.incidentes_mundo.plan.call_count, 1)

        self._run_with(patches, run)

    def test_active_candidate_survives_retry_and_conclusion_is_idempotent(self):
        patches = self._patches(incident_result="avaliar_incidente")

        def run():
            prepared = stay.prepare(self.repo, scene_id="circo-1", now=self.now)
            public = prepared["publico"]
            self.assertEqual(public["estado"], "ativa")
            self.assertEqual(public["pressao_primaria"], "incidente:furto_local")
            transaction = {
                "narracao": "Um furto se desenrola no fluxo do local, chamando a atenção ao redor.",
                "resumo": "O furto se desenrola no circo.",
                "permanencia_espacial": {
                    "avaliacao_id": public["avaliacao_id"],
                    "resultado": "resolvida",
                    "evidencia_literal": "Um furto se desenrola no fluxo do local",
                },
            }
            decision = stay.prepare_conclusion(self.repo, prepared["ticket"], transaction)
            applied = stay.install_conclusion(self.repo, prepared["ticket"], decision, now=self.now)
            self.assertEqual(applied["estado"], "resolvida")
            # O mesmo ticket/transação continua reparável depois da instalação.
            retry_decision = stay.prepare_conclusion(self.repo, prepared["ticket"], transaction)
            retried = stay.install_conclusion(self.repo, prepared["ticket"], retry_decision, now=self.now)
            self.assertEqual(retried["resultado"], "ja_aplicada")

        self._run_with(patches, run)

    def test_explicit_local_must_match_consolidated_location(self):
        with mock.patch.object(
            stay.locais,
            "resolve",
            side_effect=[
                {
                    "local_id": "circo_hooft",
                    "fontes_lidas": ["cenario/locais/index.yaml"],
                },
                {
                    "local_id": "porto_ravens_bluff",
                    "fontes_lidas": ["cenario/locais/index.yaml"],
                },
            ],
        ):
            with self.assertRaisesRegex(stay.SpatialPermanenceError, "permanência não move Ren"):
                stay.resolve_location(self.repo, "porto_ravens_bluff")


if __name__ == "__main__":
    unittest.main()
