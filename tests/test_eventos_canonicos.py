from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import barreira_mundo
import eventos_canonicos
import mundo


class EventosCanonicosRepositoryTest(unittest.TestCase):
    def test_repositorio_real_tem_dezessete_eventos_integrados(self):
        result = eventos_canonicos.validate(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["eventos"], 17)

    def test_datas_chave_e_excecoes_estao_congeladas(self):
        catalog = eventos_canonicos.load_catalog(ROOT)
        events = catalog["eventos"]
        self.assertEqual(
            events["sequestro_de_kethra"]["ativacao"]["data"],
            "1 Eleint, 1372 DR",
        )
        self.assertIn(
            "não ativa o Círculo Interno",
            " ".join(events["descida_a_ponte_e_masao"]["nucleo_obrigatorio"]),
        )
        shizune = " ".join(events["veneno_em_tyr"]["guardrails"])
        self.assertIn("Mundo Vivo", shizune)
        self.assertIn("Não criar compromisso de eliminar", shizune)


class EventosCanonicosSyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "estado").mkdir(parents=True)
        (self.repo / "narrador/mundo").mkdir(parents=True)
        (self.repo / "narrador/arcos/parte_1").mkdir(parents=True)
        (self.repo / "runtime").mkdir(parents=True)
        (self.repo / "sessoes/003").mkdir(parents=True)
        self._yaml(
            "estado/tempo.yaml",
            {
                "schema_tempo": 1,
                "data_atual": "16 Eleasis, 1372 DR",
                "hora_aproximada": "07:00",
            },
        )
        self._yaml(
            "narrador/arcos/parte_1/eventos-canonicos.yaml",
            {
                "schema_eventos_canonicos_parte_1": 1,
                "natureza": "reservado",
                "arco": eventos_canonicos.ARC,
                "eventos": {
                    "teste": {
                        "titulo": "Evento de teste",
                        "agendamento_id": "canon_teste",
                        "ativacao": {"data": "16 Eleasis, 1372 DR", "hora": "06:00"},
                        "nucleo_obrigatorio": ["Algo precisa entrar em jogo."],
                        "guardrails": ["Não escrever decisão de Ren."],
                    }
                },
            },
        )
        self._yaml(
            "narrador/mundo/agenda.yaml",
            {
                "schema_agenda_mundo": 1,
                "natureza": "reservado",
                "hora_amanhecer": "06:00",
                "reavaliacoes": {},
                "agendamentos": [
                    {
                        "id": "canon_teste",
                        "tipo": "expiracao",
                        "evento_canonico": "teste",
                        "em": {"data": "16 Eleasis, 1372 DR", "hora": "06:00"},
                        "motivo": "teste",
                    }
                ],
            },
        )
        self.pending = {
            "id": "mundo-1111111111111111",
            "tipo": "expiracao",
            "agentes_afetados": [],
            "disparado_em": {"data": "16 Eleasis, 1372 DR", "hora": "06:00"},
            "motivo": "teste",
            "origem": "agenda:agendamentos.canon_teste",
        }
        self._yaml(
            "narrador/mundo/estado.yaml",
            {
                "schema_estado_mundo": 1,
                "natureza": "controle_reservado",
                "processado_ate": {"data": "16 Eleasis, 1372 DR", "hora": "07:00"},
                "pendencias": [self.pending],
                "concluidas_recentes": [],
            },
        )
        (self.repo / "sessoes/003/consolidacoes.jsonl").write_text(
            json.dumps({"transacoes": ["s003-canonico"]}) + "\n",
            encoding="utf-8",
        )
        barreira_mundo.sync(self.repo)

    def tearDown(self):
        self.temp.cleanup()

    def _yaml(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def test_catalogo_mapeia_pendencia_pelo_id_do_agendamento(self):
        event = eventos_canonicos.event_for_pending(self.repo, self.pending)
        self.assertIsNotNone(event)
        self.assertEqual(event["id"], "teste")
        projection = eventos_canonicos.pending_projection(self.repo, [self.pending])
        self.assertEqual(projection["eventos"][0]["evento"], "teste")
        self.assertEqual(projection["eventos"][0]["atraso_dias"], 0)

    def test_evento_canonico_nao_pode_ser_concluido_com_noop(self):
        with self.assertRaises(barreira_mundo.WorldPendingBarrierError) as ctx:
            barreira_mundo.conclude(
                self.repo,
                self.pending["id"],
                "não aconteceu nada",
                no_change=True,
            )
        self.assertIn("não aceita --sem-mudanca", str(ctx.exception))
        self.assertEqual(mundo.pending_view(self.repo)["quantidade"], 1)

    def test_evento_canonico_exige_transacao_para_entrar_em_jogo(self):
        with self.assertRaises(barreira_mundo.WorldPendingBarrierError) as ctx:
            barreira_mundo.conclude(self.repo, self.pending["id"], "materializado")
        self.assertIn("informe --transacao", str(ctx.exception))

        result = barreira_mundo.conclude(
            self.repo,
            self.pending["id"],
            "núcleo materializado em cena",
            transaction_id="s003-canonico",
        )
        self.assertEqual(result["evento_canonico"]["id"], "teste")
        self.assertEqual(result["evento_canonico"]["estado"], "materializado_em_jogo")
        self.assertEqual(result["pendencias_restantes"], 0)


if __name__ == "__main__":
    unittest.main()
