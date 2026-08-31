from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
sys.path.insert(0, str(TOOLS))
MODULE = TOOLS / "politica_acesso.py"
spec = importlib.util.spec_from_file_location("politica_acesso_test", MODULE)
policy = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = policy
spec.loader.exec_module(policy)


class PoliticaAcessoTest(unittest.TestCase):
    def test_classificacao_dos_niveis_operacionais(self):
        self.assertEqual(policy.classify("status").level, "L1")
        for command in ("cena", "retomada", "npc", "relacao", "conhecimento", "regra"):
            self.assertEqual(policy.classify(command).level, "L2")
        self.assertEqual(policy.classify("buscar").level, "L3")
        self.assertEqual(policy.classify("buscar", historical=True).level, "L4")
        self.assertEqual(policy.classify("buscar", historical=True, transcripts=True).level, "L4T")

    def test_sessao_atual_e_historica_tem_politicas_diferentes(self):
        current = policy.classify("sessao", current_session=3, session_term="3")
        self.assertEqual(current.level, "L2")
        self.assertIsNone(current.required_after)

        old = policy.classify("sessao", current_session=3, session_term="2")
        self.assertEqual(old.level, "L4")
        self.assertEqual(old.required_after, "L2")
        self.assertTrue(old.direct_jump)

    def test_busca_l3_exige_declaracao_de_escalada_e_motivo(self):
        decision = policy.classify("buscar")
        with self.assertRaises(policy.AccessPolicyError):
            policy.validate_escalation(decision, after=None, reason=None)
        with self.assertRaises(policy.AccessPolicyError):
            policy.validate_escalation(decision, after="L1", reason="Falta localizar a pista exata.")
        reason = policy.validate_escalation(
            decision,
            after="L2",
            reason="A consulta dirigida não localizou onde a pista foi registrada.",
        )
        self.assertIn("pista", reason)

    def test_historico_e_transcricao_nao_pulam_degrau_amplo(self):
        historical = policy.classify("buscar", historical=True)
        with self.assertRaises(policy.AccessPolicyError):
            policy.validate_escalation(
                historical,
                after="L2",
                reason="A busca corrente não encontrou a origem histórica da informação.",
            )
        policy.validate_escalation(
            historical,
            after="L3",
            reason="A busca corrente não encontrou a origem histórica da informação.",
        )

        transcript = policy.classify("buscar", historical=True, transcripts=True)
        with self.assertRaises(policy.AccessPolicyError):
            policy.validate_escalation(
                transcript,
                after="L3",
                reason="O resumo histórico não contém a fala exata necessária para continuidade.",
            )
        policy.validate_escalation(
            transcript,
            after="L4",
            reason="O resumo histórico não contém a fala exata necessária para continuidade.",
        )

    def test_alvo_historico_conhecido_pode_saltar_busca_ampla(self):
        decision = policy.classify("sessao", current_session=3, session_term="2")
        policy.validate_escalation(
            decision,
            after="L2",
            reason="A pergunta aponta diretamente para a sessão 002 e exige seu resumo consolidado.",
        )

    def test_motivo_generico_e_rejeitado(self):
        decision = policy.classify("buscar")
        with self.assertRaises(policy.AccessPolicyError):
            policy.validate_escalation(decision, after="L2", reason="por precaução")

    def test_acesso_reservado_exige_motivo_mesmo_sem_outro_requisito(self):
        decision = policy.AccessDecision("L2", None)
        with self.assertRaises(policy.AccessPolicyError):
            policy.validate_escalation(decision, after=None, reason=None, reserved=True)

    def test_tetos_de_bytes_nao_podem_ser_aumentados_pelo_chamador(self):
        self.assertEqual(policy.effective_budget("L1", 16000), 4096)
        self.assertEqual(policy.effective_budget("L2", 16000), 8192)
        self.assertEqual(policy.effective_budget("L3", 16000), 8192)
        self.assertEqual(policy.effective_budget("L4", 16000), 12288)
        self.assertEqual(policy.effective_budget("L4T", 99999), 16384)
        self.assertEqual(policy.effective_budget("L4", 2048), 2048)

    def test_saida_de_politica_lembra_condicao_de_parada(self):
        decision = policy.classify("status")
        data, budget = policy.decorate(
            {"consulta": {"comando": "status"}, "resultado": {}},
            decision,
            requested_budget=16000,
            after=None,
            reason=None,
        )
        self.assertEqual(budget, 4096)
        self.assertTrue(data["controle_acesso"]["pare_se_suficiente"])
        self.assertEqual(data["controle_acesso"]["proximo_nivel"], "L2")

    def test_status_l1_compacta_prosa_livre_sem_perder_estado_estruturado(self):
        result = {
            "sessao": {"numero": 13, "status": "em_sessao"},
            "personagem": {"nome": "Ren Kagehira", "nivel": 7},
            "recursos": {"pv": {"atuais": 52, "maximos": 52}, "focus": {"atuais": 7, "maximos": 7}},
            "tempo": {
                "data": "14 Eleasis, 1372 DR",
                "hora_aproximada": "22:00",
                "periodo": "texto livre antigo " * 100,
            },
            "localizacao": {
                "area": "Jack Mooney & Sons Circus, Ravens Bluff",
                "ponto_exato": "fundos do acampamento",
                "descricao_operacional": "prosa longa " * 200,
            },
            "efeitos_temporarios": {
                f"efeito_{i}": {
                    "nome": f"Efeito {i}",
                    "descricao": "descrição longa " * 80,
                    "duracao": "até mudar",
                }
                for i in range(8)
            },
            "sobreposicao_transacional": {"eventos_pendentes": 1, "ultima_transacao": "tx"},
        }
        decision = policy.classify("status")
        data, budget = policy.decorate(
            {"consulta": {"comando": "status"}, "resultado": result},
            decision,
            requested_budget=16000,
            after=None,
            reason=None,
        )
        compact = data["resultado"]
        self.assertEqual(budget, 4096)
        self.assertEqual(compact["personagem"]["nome"], "Ren Kagehira")
        self.assertEqual(compact["tempo"], {"data": "14 Eleasis, 1372 DR", "hora_aproximada": "22:00"})
        self.assertEqual(compact["localizacao"]["area"], "Jack Mooney & Sons Circus, Ravens Bluff")
        self.assertNotIn("descricao_operacional", compact["localizacao"])
        self.assertEqual(compact["efeitos_temporarios"]["efeito_0"]["nome"], "Efeito 0")
        self.assertTrue(data["controle_acesso"]["pare_se_suficiente"])


if __name__ == "__main__":
    unittest.main()
