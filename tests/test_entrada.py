from __future__ import annotations

import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import entrada
import turno

ROOT = Path(__file__).parents[1]


class EntradaParserTest(unittest.TestCase):
    def test_texto_normal_e_somente_on_e_registravel(self):
        report = entrada.parse_message("Eu pago os 3 PO.")
        self.assertTrue(report["valido"])
        self.assertEqual(report["tipo"], "somente_on")
        self.assertTrue(report["tem_on"])
        self.assertFalse(report["tem_off"])
        self.assertFalse(report["tem_recall"])
        self.assertTrue(report["pode_registrar"])

    def test_bloco_inteiro_entre_colchetes_e_off(self):
        report = entrada.parse_message("[Quanto dinheiro eu tenho?]")
        self.assertTrue(report["valido"])
        self.assertEqual(report["tipo"], "somente_off")
        self.assertFalse(report["tem_on"])
        self.assertTrue(report["tem_off"])
        self.assertEqual(report["off"], ["Quanto dinheiro eu tenho?"])
        self.assertFalse(report["pode_registrar"])

    def test_mensagem_mista_preserva_ordem_e_separa_canais(self):
        text = "[Quanto dinheiro eu tenho?]\n\nEu pago os 3 PO."
        report = entrada.parse_message(text)
        self.assertEqual(report["tipo"], "misto")
        self.assertTrue(report["tem_on"])
        self.assertTrue(report["tem_off"])
        self.assertEqual(report["on"], "Eu pago os 3 PO.")
        self.assertEqual([item["tipo"] for item in report["blocos"]], ["off", "on"])
        self.assertFalse(report["pode_registrar"])

    def test_recall_e_extraido_apenas_dentro_de_on(self):
        text = (
            "Ren diz a Nera:\n\n"
            "— Quando eu vivia em {cidade onde Ren passou seus anos mais pobres}, a vida era difícil."
        )
        report = entrada.parse_message(text)
        self.assertEqual(report["tipo"], "somente_on")
        self.assertTrue(report["tem_recall"])
        self.assertEqual(
            report["recalls"][0]["pedido"],
            "cidade onde Ren passou seus anos mais pobres",
        )
        self.assertFalse(report["pode_registrar"])

        off = entrada.parse_message("[Posso escrever {qualquer coisa} aqui?]")
        self.assertEqual(off["tipo"], "somente_off")
        self.assertFalse(off["tem_recall"])

    def test_colchetes_inline_nao_viram_off(self):
        report = entrada.parse_message("Ren observa a placa [já bastante desgastada] antes de entrar.")
        self.assertEqual(report["tipo"], "somente_on")
        self.assertTrue(report["pode_registrar"])

    def test_sintaxe_off_ambigua_e_rejeitada(self):
        report = entrada.parse_message("[Quanto tenho?] Eu pago os 3 PO.")
        self.assertFalse(report["valido"])
        self.assertEqual(report["tipo"], "invalido")
        self.assertIn("precisa terminar com ']'", report["erros"][0])

    def test_recall_desbalanceado_aninhado_ou_vazio_e_rejeitado(self):
        for text in (
            "Ren fala {nome sem fechar.",
            "Ren fala nome sem abrir}.",
            "Ren fala {um {outro} nome}.",
            "Ren fala {}.",
        ):
            with self.subTest(text=text):
                report = entrada.parse_message(text)
                self.assertFalse(report["valido"])

    def test_chaves_escapadas_sao_literais(self):
        report = entrada.parse_message(r"Ren escreve \{exemplo\} no papel.")
        self.assertTrue(report["valido"])
        self.assertFalse(report["tem_recall"])
        self.assertTrue(report["pode_registrar"])


class EntradaTransactionalBarrierTest(unittest.TestCase):
    def test_turno_recusa_off_e_recall_cru(self):
        with self.assertRaises(turno.TransactionError):
            turno.validate_player_protocol("[Continue a sessão 3.]")
        with self.assertRaises(turno.TransactionError):
            turno.validate_player_protocol("Ren procura {nome do contato}.")

    def test_turno_aceita_on_resolvido(self):
        self.assertEqual(
            turno.validate_player_protocol("Ren procura Kethra Dunn."),
            "Ren procura Kethra Dunn.",
        )


class EntradaContractTest(unittest.TestCase):
    def test_contrato_documenta_tres_canais_e_limites_de_agencia(self):
        text = (ROOT / "docs/agente/protocolo-de-entrada.md").read_text(encoding="utf-8")
        self.assertIn("texto normal   = ON", text)
        self.assertIn("[texto]        = OFF", text)
        self.assertIn("{texto}        = RECALL", text)
        self.assertIn("não delega a personagem ao narrador", text)
        self.assertIn("não registrar turno", text)


if __name__ == "__main__":
    unittest.main()
