"""Alvo explícito e fronteira real, em sandbox, sem avançar a campanha viva."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

import yaml
sys.path[:0] = [str(Path(__file__).parents[1] / "ferramentas")]
import cronica
import endpoints
import fronteira_mundo
import mundo
import transacoes
import consolidar
import test_memoria_duravel_integracao as fixtures


class TemporalWindowIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.DurableMemoryIntegrationTest()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.repo = self.f.repo
        self.date = "11 Eleasis, 1372 DR"
        self.f.write("estado/tempo.yaml", {"schema_tempo": 1, "data_atual": self.date,
                                           "hora_aproximada": "11:35"})
        state = yaml.safe_load((self.repo / "estado/estado-atual.yaml").read_text())
        state["tempo"].update(data_exata=self.date, hora_aproximada="11:35")
        self.f.write("estado/estado-atual.yaml", state)
        self.f.write(mundo.AGENDA_PATH, {"schema_agenda_mundo": 1, "natureza": "reservado",
                     "hora_amanhecer": "06:00", "reavaliacoes": {}, "agendamentos": []})
        self.f.write(mundo.WORLD_STATE_PATH, {"schema_estado_mundo": 1, "natureza": "controle_reservado",
                     "processado_ate": {"data": self.date, "hora": "11:35"},
                     "pendencias": [], "concluidas_recentes": []})

    def cause(self):
        agenda = mundo.load_agenda(self.repo)
        # Expiração controlada, sem NPC/arco nem evento canônico criado no save.
        agenda["agendamentos"] = [{"id": "prazo_fixture", "tipo": "expiracao",
                  "em": {"data": self.date, "hora": "11:50"}, "motivo": "Fim da janela controlada."}]
        self.f.write(mundo.AGENDA_PATH, agenda)

    def query(self, hour):
        return endpoints.boundary(self.repo, date=self.date, hour=hour)

    def tx(self, tid, hour):
        return {"id": tid, "jogador": "Ren espera até 12:14, se nada interromper.",
                "narracao": "O tempo passou durante a espera autorizada.", "resumo": "Esperou.",
                "modo": "descanso", "deltas": [{"alvo": "tempo", "op": "instante",
                          "valor": {"data": self.date, "hora": hour}}]}

    def prepare(self, scene):
        return cronica.prepare(self.repo, scene_id=scene, sidequest_signal=None, memory_participants=[])

    def test_causa_interrompe_39_minutos_no_primeiro_limite_e_consulta_e_read_only(self):
        self.cause()
        before = self.f.hashes()
        out = self.query("12:14")
        self.assertEqual(before, self.f.hashes())
        self.assertEqual(out["disponibilidade"]["inicio"]["hora"], "11:35")
        self.assertEqual(out["disponibilidade"]["janela_consultada"]["duracao_minutos"], 39)
        self.assertEqual(out["proximo_passo"]["fronteira"]["hora"], "11:50")
        self.assertFalse(out["disponibilidade"]["alvo_inteiro_sem_checkpoint"])
        self.assertEqual(out["ids"]["motivos_por_camada"]["agendamentos"], ["prazo_fixture"])

    def test_sem_causa_libera_alvo_e_zero_nao_comprova_espera(self):
        out = self.query("12:14")
        self.assertTrue(out["disponibilidade"]["alvo_inteiro_sem_checkpoint"])
        self.assertEqual(out["disponibilidade"]["janela_consultada"]["limite_narravel"]["hora"], "12:14")
        zero = self.query("11:35")
        self.assertFalse(zero["disponibilidade"]["alvo_inteiro_sem_checkpoint"])
        self.assertEqual(zero["disponibilidade"]["janela_consultada"]["cobertura"], "instante_sem_compressao")
        self.assertEqual(zero["proximo_passo"]["acao"], "informar_alvo_final_da_compressao")
        prepared = self.prepare("espera-sem-causa")
        cronica.conclude(self.repo, prepared["ticket"], self.tx("espera-livre", "12:14"))
        self.assertEqual(fronteira_mundo.effective_time(self.repo)[0], mundo.parse_instant(self.date, "12:14"))

    def test_cli_explica_alvo_e_aliases_legados_preservam_resultado(self):
        self.cause()
        outputs = []
        for date_flag, hour_flag in [("--data-alvo", "--hora-alvo"), ("--data", "--hora")]:
            result = subprocess.run([sys.executable, str(Path(endpoints.__file__)), "--repo", str(self.repo),
                     "fronteira", date_flag, self.date, hour_flag, "12:14"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(yaml.safe_load(result.stdout))
        self.assertEqual(outputs[0], outputs[1])

    def test_inicio_usa_tempo_pendente_e_ignora_outra_sessao(self):
        out = self.prepare("avanco-pendente")
        cronica.conclude(self.repo, out["ticket"], self.tx("avanco", "11:45"))
        self.assertEqual(self.query("12:14")["disponibilidade"]["inicio"]["hora"], "11:45")
        self.assertEqual(self.query("12:14")["disponibilidade"]["janela_consultada"]["duracao_minutos"], 29)
        record = transacoes.load_pending(self.repo)[0]
        record["sessao"] = 99
        with patch.object(transacoes, "load_pending", return_value=[record]):
            self.assertEqual(self.query("12:14")["disponibilidade"]["inicio"]["hora"], "11:35")
        with self.assertRaisesRegex(ValueError, "anterior"):
            self.query("11:40")

    def test_checkpoint_retry_e_continuacao_nao_repetem_causa_instalada(self):
        self.cause()
        limit = self.query("12:14")["disponibilidade"]["janela_consultada"]["limite_narravel"]
        prepared = self.prepare("espera-ate-fronteira")
        tx = self.tx("espera", limit["hora"])
        cronica.conclude(self.repo, prepared["ticket"], tx)
        before = self.f.hashes()
        cronica.conclude(self.repo, prepared["ticket"], tx)
        self.assertEqual(before, self.f.hashes())
        consolidar.consolidate(self.repo, "cena")
        processed = mundo.process_to_canonical(self.repo)
        pending = processed["novas_pendencias"]
        self.assertEqual(len(pending), 1)
        mundo.conclude(self.repo, pending[0]["id"], "Expiração da fixture avaliada explicitamente.")
        self.assertFalse(mundo.process_to_canonical(self.repo)["alterou"])
        remaining = self.query("12:14")
        self.assertEqual(remaining["disponibilidade"]["inicio"]["hora"], "11:50")
        self.assertTrue(remaining["disponibilidade"]["alvo_inteiro_sem_checkpoint"])
        new = self.prepare("continuacao-da-espera")
        cronica.conclude(self.repo, new["ticket"], self.tx("termino", "12:14"))
        self.assertEqual(fronteira_mundo.effective_time(self.repo)[0], mundo.parse_instant(self.date, "12:14"))
        self.assertEqual(len(mundo.load_world_state(self.repo)["concluidas_recentes"]), 1)

    def test_turno_curto_nao_acrescenta_consulta_de_fronteira(self):
        with patch.object(endpoints, "boundary") as public, patch.object(fronteira_mundo, "next_boundary") as inner:
            out = self.prepare("fala-curta")
            tx = self.tx("fala", "11:35")
            tx["deltas"] = []
            cronica.conclude(self.repo, out["ticket"], tx)
        public.assert_not_called()
        inner.assert_not_called()
