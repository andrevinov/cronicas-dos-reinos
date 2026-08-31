from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica
import cronica_hotpath
import locais
import retomada_cronica


class NeutralTurnRegressionTest(unittest.TestCase):
    def registered(self):
        return {
            "id": "tx-neutral-1",
            "sessao": 13,
            "deltas": 0,
            "transcricao_escrita": True,
            "evento_escrito": True,
            "reparo_parcial": False,
            "ja_registrada": False,
            "consolidada": False,
            "checkpoint_mundo": None,
            "avisos": [],
        }

    def transaction(self):
        return {
            "jogador": "Ren observa a rua.",
            "narracao": "A rua segue silenciosa.",
            "resumo": "Ren observa a rua sem mudança material.",
            "modo": "exploração",
            "deltas": [],
        }

    def test_turno_comum_nao_inventa_gatilho_nem_chama_endpoint(self):
        with mock.patch.object(cronica.endpoints, "scene") as endpoint:
            result = cronica.prepare(
                ROOT,
                scene_id="s013-turno-comum",
                sidequest_signal=None,
            )
        endpoint.assert_not_called()
        self.assertFalse(result["reativa"])
        self.assertEqual(result["fontes_lidas"], [])
        payload = cronica.decode_ticket(result["ticket"])
        self.assertTrue(payload["preparacao_id"].startswith(cronica_hotpath.NEUTRAL_PREPARATION_PREFIX))
        self.assertEqual(payload["cena"]["context_tags"], [])
        self.assertEqual(payload["cena"]["npcs"], [])

    def test_saida_preparar_ensina_conclusao_sem_help_ou_leitura_de_codigo(self):
        result = cronica.prepare(
            ROOT,
            scene_id="s013-autossuficiente",
            sidequest_signal=None,
        )
        contract = result["contrato_conclusao"]
        self.assertIn("cronica concluir --ticket <ticket>", contract["comando"])
        self.assertEqual(
            set(contract["campos"]),
            {"jogador", "narracao", "resumo", "modo", "deltas"},
        )
        self.assertIn("MECÂNICA —", contract["mecanica"])
        self.assertIn("Não chamar --help", contract["disciplina"])

    def test_turno_neutro_conclui_sem_confirmacao_reativa_falsa(self):
        prepared = cronica.prepare(
            ROOT,
            scene_id="s013-neutral-concluir",
            sidequest_signal=None,
        )
        order = []

        def preflight(_repo, _tx):
            order.append("preflight")
            return {"id": "tx-neutral-1", "checkpoint_previsto": None}

        def register(_repo, _tx):
            order.append("registrar")
            return self.registered()

        with (
            mock.patch.object(cronica, "_preflight_registration", side_effect=preflight),
            mock.patch.object(cronica.cena_mundo, "confirm_scene") as confirm,
            mock.patch.object(cronica.turno, "register_transaction", side_effect=register),
            mock.patch.object(cronica.rodape_turno, "build_safe", return_value="RODAPE_CANONICO — ok"),
        ):
            result = cronica.conclude(ROOT, prepared["ticket"], self.transaction())
        self.assertEqual(order, ["preflight", "registrar"])
        confirm.assert_not_called()
        self.assertFalse(result["reativa"])
        self.assertFalse(result["cena"]["confirmada"])
        self.assertEqual(result["transacao"]["id"], "tx-neutral-1")

    def test_flags_locais_parciais_falham_com_instrucao_de_omissao(self):
        with self.assertRaises(cronica.CronicaError) as caught:
            cronica.prepare(
                ROOT,
                scene_id="s013-local-incompleto",
                danger="baixa",
                sidequest_signal=None,
            )
        text = str(caught.exception)
        self.assertIn("gatilho local incompleto", text)
        self.assertIn("omita os quatro", text)
        self.assertIn("--cena-id", text)


class RolloutLocationRegressionTest(unittest.TestCase):
    def test_circo_resolve_sem_busca_ampla(self):
        result = locais.resolve(ROOT, "circo")
        self.assertEqual(result["local_id"], "jack_mooney_sons_circus")
        self.assertEqual(result["resolucao"], "alias_canonico")
        self.assertEqual(result["fontes_lidas"], ["cenario/locais/index.yaml"])


class ResumeProjectionRegressionTest(unittest.TestCase):
    def test_retomada_prefere_overlay_e_resumo_pendente_a_prosa_stale(self):
        stale_context = {
            "sessao": {"numero": 13, "status": "em_sessao", "modo_de_cena": "antigo"},
            "personagem": {"nome": "Ren Kagehira", "nivel": 7},
            "recursos": {"pv": {"atuais": 52, "maximos": 52}},
            "tempo": {
                "data": "14 Eleasis, 1372 DR",
                "hora_aproximada": "21:20",
                "periodo": "meio da tarde de 11 Eleasis",
            },
            "localizacao": {"area": "Rua da Cal", "ponto_exato": "junto a Sella"},
        }
        stale_scene = {"modo": "antigo", "resumo_imediato": "Resumo de 11 Eleasis"}
        effective = {
            **stale_context,
            "sessao": {"numero": 13, "status": "em_sessao", "modo_de_cena": "circo_apos_retorno"},
            "tempo": {"data": "14 Eleasis, 1372 DR", "hora_aproximada": "22:00", "periodo": "stale"},
            "localizacao": {"area": "Jack Mooney & Sons Circus", "ponto_exato": "fundos do acampamento"},
        }
        pending = [{"id": "tx-real", "sessao": 13, "resumo": "Ren retornou ao circo sem cauda."}]

        def fake_load(path):
            return stale_context if path.name == "contexto.yaml" else stale_scene

        with (
            mock.patch.object(retomada_cronica, "_load_yaml", side_effect=fake_load),
            mock.patch.object(retomada_cronica.transacoes, "load_pending", return_value=pending),
            mock.patch.object(retomada_cronica.transacoes, "pending_for_session", return_value=pending),
            mock.patch.object(
                retomada_cronica.transacoes,
                "overlay_runtime",
                return_value=(effective, {"modo": "circo_apos_retorno"}, 1),
            ),
            mock.patch.object(retomada_cronica.recursos, "apply_pending_effects"),
        ):
            result = retomada_cronica.current_snapshot(ROOT)

        self.assertEqual(result["agora"]["hora"], "22:00")
        self.assertEqual(result["agora"]["local"]["area"], "Jack Mooney & Sons Circus")
        self.assertEqual(result["resumo_imediato"], "Ren retornou ao circo sem cauda.")
        self.assertNotIn("periodo", result["agora"])
        self.assertNotIn("11 Eleasis", str(result))
        self.assertFalse(result["transcricao_lida"])

    def test_inicio_de_sessao_carrega_recap_sem_transcricao(self):
        base = {"fase": "iniciada", "sessao_anterior": 12, "sessao": 13}
        with (
            mock.patch.object(
                retomada_cronica,
                "previous_recap",
                return_value={"sessao": 12, "eventos_recentes": [{"resumo": "fim"}], "transcricao_lida": False},
            ),
            mock.patch.object(
                retomada_cronica,
                "current_snapshot",
                return_value={"sessao": 13, "agora": {"hora": "21:20"}, "transcricao_lida": False},
            ),
        ):
            result = retomada_cronica.decorate_start(ROOT, base)
        self.assertEqual(result["recap_sessao_anterior"]["sessao"], 12)
        self.assertFalse(result["recap_sessao_anterior"]["transcricao_lida"])
        self.assertFalse(result["retomada"]["transcricao_lida"])
        self.assertIn("cronica preparar --cena-id", result["proximo_passo"]["depois"])


if __name__ == "__main__":
    unittest.main()
