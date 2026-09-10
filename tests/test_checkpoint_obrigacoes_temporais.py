from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import agentes_leves
import checkpoint
import obrigacoes_temporais


def condition_record() -> dict:
    return {
        "tipo": "compromisso",
        "resumo": "Silva acompanha a transferência",
        "envolvidos": ["silva_elkwood"],
        "obrigacao_temporal": {
            "schema": 1,
            "estado": "reconciliar",
            "responsavel": "silva_elkwood",
            "destinatario": "ren",
            "local_ou_canal": "retorno genérico",
            "prazo_ou_condicao": {"condicao": "a transferência mudar"},
            "resultado_esperado": "retornar estado geral",
            "modo_retorno": "sem revelar rota",
            "fonte_canonica": {
                "arquivo": "estado/relacoes/colm_dunn.yaml",
                "evidencia_literal": "em trânsito",
            },
        },
    }


class CheckpointTemporalCompositionTest(unittest.TestCase):
    def test_fixture_sem_instalacao_temporal_delega_ao_checkpoint_anterior(self):
        repo = Path("/fixture-sem-nv18")
        with mock.patch.object(obrigacoes_temporais, "configured", return_value=False), \
             mock.patch.object(checkpoint, "_BASE_SYNC_WORLD", return_value={"configurado": False}) as base:
            result = checkpoint.sync_world(repo)
        base.assert_called_once_with(repo)
        self.assertFalse(result["obrigacoes_temporais"]["configurado"])

    def test_checkpoint_temporal_roda_antes_da_sincronizacao_existente(self):
        repo = Path("/fixture-com-nv18")
        order = []

        def temporal(_repo):
            order.append("temporal")
            return {"configurado": True, "alterou": False, "devidas": []}

        def base(_repo):
            order.append("mundo")
            return {"configurado": True}

        with mock.patch.object(obrigacoes_temporais, "sync_checkpoint", side_effect=temporal), \
             mock.patch.object(checkpoint, "_BASE_SYNC_WORLD", side_effect=base):
            result = checkpoint.sync_world(repo)
        self.assertEqual(order, ["temporal", "mundo"])
        self.assertTrue(result["obrigacoes_temporais"]["configurado"])

    def test_check_do_checkpoint_agrega_erros_temporais_sem_novo_preflight(self):
        repo = Path("/fixture")
        with mock.patch.object(checkpoint, "_BASE_CHECK", return_value=[]), \
             mock.patch.object(obrigacoes_temporais, "check", return_value={"ok": False, "erros": ["índice stale"]}):
            self.assertEqual(checkpoint.check(repo), ["obrigações temporais: índice stale"])


class TemporalCausalDispatchTest(unittest.TestCase):
    def test_obrigacao_condicional_usa_fila_existente_e_suspende_rotina(self):
        now = obrigacoes_temporais.mundo.parse_instant("21 Eleasis, 1372 DR", "22:00")
        world = {
            "pendencias": [
                {
                    "id": "mundo-1111111111111111",
                    "tipo": "reavaliar_agente_leve",
                    "agente_leve": "outro_agente",
                    "agentes_afetados": [],
                    "disparado_em": {"data": "21 Eleasis, 1372 DR", "hora": "06:00"},
                    "motivo": "rotina",
                    "origem": "rotina",
                }
            ],
            "concluidas_recentes": [],
        }
        index = {
            "agentes": {
                "silva_elkwood": {"estado": "ativo"},
                "outro_agente": {"estado": "ativo"},
            },
            "orcamento": {"max_pendencias_abertas": 1},
        }
        tracker = {"despachos": {}}
        written = []

        def capture(_path, value):
            written.append(value)

        with mock.patch("acionamentos_leves.configured", return_value=True), \
             mock.patch("agentes_leves.load_index", return_value=index), \
             mock.patch.object(obrigacoes_temporais.mundo, "load_world_state", return_value=world), \
             mock.patch.object(obrigacoes_temporais.mundo, "_atomic_write_yaml", side_effect=capture):
            projection = obrigacoes_temporais._dispatch_nonexact_due(
                Path("/fixture"), {"retorno_colm": condition_record()}, now, tracker
            )

        self.assertEqual(len(written), 1)
        saved = written[0]
        causal = [p for p in saved["pendencias"] if p.get("agente_leve") == "silva_elkwood"]
        self.assertEqual(len(causal), 1)
        self.assertIn("nv18:retorno_colm", causal[0]["acionamento_causal"])
        self.assertIn("mundo-1111111111111111", saved["acionamentos_leves"]["rotinas_suspensas"])
        self.assertEqual(projection[0]["resultado"], "acionamento_causal")


class LightAgentTemporalNoopCompositionTest(unittest.TestCase):
    def test_noop_publico_e_delegado_ao_contrato_temporal(self):
        repo = Path("/fixture")
        expected = {"ok": True, "obrigacoes_temporais": {"adiadas": []}}
        with mock.patch.object(obrigacoes_temporais, "conclude_noop", return_value=expected) as temporal:
            result = agentes_leves.conclude_noop(
                repo,
                "mundo-2222222222222222",
                "bloqueio real",
                retomar_data="22 Eleasis, 1372 DR",
                retomar_hora="06:00",
            )
        self.assertEqual(result, expected)
        self.assertEqual(temporal.call_args.kwargs["retomar_data"], "22 Eleasis, 1372 DR")
        self.assertIs(temporal.call_args.kwargs["base_conclude"], agentes_leves._BASE_CONCLUDE_NOOP)


if __name__ == "__main__":
    unittest.main()
