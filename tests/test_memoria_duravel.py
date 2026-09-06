"""Contrato puro; fatos sintéticos não representam acontecimentos da campanha."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ferramentas"))
import memoria_duravel as memory


def transaction(kind="marco"):
    text = "Silva recebeu a carta e guardou o selo azul."
    fact = {"id": "carta", "tipo": kind, "participantes": ["ren", "silva_fixture"],
            "evidencia": {"campo": "narracao", "trecho": text}, "texto": text}
    if kind == "informacao":
        fact.update(emissor="ren", destinatario="silva_fixture", canal="presencial", estatuto="rumor")
    return {"jogador": "Ren entrega a carta.", "narracao": text, "resumo": "Carta entregue.",
            "modo": "interação", "deltas": [], "memoria": {"versao": 1, "fatos": [fact]}}


class DurableMemoryContractTest(unittest.TestCase):
    def compile(self, tx):
        return memory.compile_transaction(tx, "teste-duravel", 3)[0]

    def test_ausencia_de_bloco_e_identidade_sem_leituras(self):
        tx = transaction()
        tx.pop("memoria")
        with patch.object(Path, "read_text", side_effect=AssertionError("leitura extra")), \
             patch.object(Path, "open", side_effect=AssertionError("leitura extra")):
            self.assertIs(memory.prepare_transaction(Path("/inexistente"), tx), tx)

    def test_compilacao_pura_deterministica_sem_mutar_entrada(self):
        tx = transaction()
        original = deepcopy(tx)
        first = self.compile(tx)
        self.assertEqual(first, self.compile(tx))
        self.assertEqual(tx, original)
        self.assertNotIn("memoria", first)
        self.assertEqual(first["deltas"][0]["alvo"], "relacao:silva_fixture")
        self.assertEqual(first["deltas"][0]["valor"]["fonte"], "transacao:teste-duravel")

    def test_ids_independem_de_estado_e_mudam_por_fato_ou_transacao(self):
        self.assertEqual(memory.event_id("a", "b"), memory.event_id("a", "b"))
        self.assertNotEqual(memory.event_id("a", "b"), memory.event_id("b", "a"))
        self.assertLessEqual(len(memory.event_id("a", "b")), 64)

    def test_schema_rejeita_bloco_vazio_nulo_versao_boolean_e_campos_extras(self):
        for block in (None, {}, {"versao": True, "fatos": []},
                      {"versao": 1, "fatos": []}, {"versao": 2, "fatos": [1]},
                      {"versao": 1, "fatos": [1], "segredo": "x"}):
            with self.subTest(block=block), self.assertRaises(memory.DurableMemoryError):
                tx = transaction()
                tx["memoria"] = block
                self.compile(tx)

    def test_evidencia_nao_pode_vir_so_do_resumo_ou_de_arquivo_secreto(self):
        for field in ("resumo", "narrador/segredo.yaml", None):
            with self.subTest(field=field), self.assertRaises(memory.DurableMemoryError):
                tx = transaction()
                tx["memoria"]["fatos"][0]["evidencia"]["campo"] = field
                self.compile(tx)

    def test_evidencia_inventada_e_texto_mais_forte_sao_recusados(self):
        for key in ("evidencia", "texto"):
            tx = transaction()
            fact = tx["memoria"]["fatos"][0]
            if key == "evidencia":
                fact[key]["trecho"] = "Silva descobriu o verdadeiro autor do atentado."
            else:
                fact[key] = "Silva descobriu o verdadeiro autor do atentado."
            with self.subTest(key=key), self.assertRaises(memory.DurableMemoryError):
                self.compile(tx)

    def test_segredo_ou_campo_desconhecido_falha_fechado(self):
        for key in ("visibilidade", "destinatarios", "arquivo"):
            tx = transaction()
            tx["memoria"]["fatos"][0][key] = "narrador"
            with self.subTest(key=key), self.assertRaises(memory.DurableMemoryError):
                self.compile(tx)

    def test_participantes_exigem_ids_distintos_e_ren(self):
        for people in (["silva_fixture", "nera_fixture"], ["ren", "ren"], ["ren"],
                       ["ren", "../silva"], ["ren", {}], ["ren"] + ["npc_" + str(i) for i in range(6)]):
            tx = transaction()
            tx["memoria"]["fatos"][0]["participantes"] = people
            with self.subTest(people=people), self.assertRaises(memory.DurableMemoryError):
                self.compile(tx)

    def test_id_de_fato_duplicado_ou_invalido_falha(self):
        tx = transaction()
        tx["memoria"]["fatos"] *= 2
        with self.assertRaises(memory.DurableMemoryError):
            self.compile(tx)
        tx = transaction()
        tx["memoria"]["fatos"][0]["id"] = "a.b"
        with self.assertRaises(memory.DurableMemoryError):
            self.compile(tx)

    def test_informacao_so_vai_ao_destinatario_explicito(self):
        tx = transaction("informacao")
        tx["memoria"]["fatos"][0]["participantes"].append("nera_fixture")
        deltas = self.compile(tx)["deltas"]
        self.assertEqual([d["alvo"] for d in deltas], ["relacao:silva_fixture"])
        self.assertEqual(deltas[0]["caminho"], "informacoes_recebidas")
        self.assertEqual(deltas[0]["valor"]["estatuto"], "rumor")

    def test_relato_recebido_por_ren_preserva_emissor_canal_e_incerteza(self):
        tx = transaction("informacao")
        fact = tx["memoria"]["fatos"][0]
        fact.update(emissor="silva_fixture", destinatario="ren")
        deltas = self.compile(tx)["deltas"]
        knowledge = next(d["valor"] for d in deltas if d["alvo"] == "conhecimento")
        self.assertIn("rumor recebido de silva_fixture", knowledge["texto"])
        self.assertEqual(knowledge["estatuto"], "rumor")

    def test_envio_futuro_ou_verdade_automatica_sao_recusados(self):
        for key, value in (("canal", "mensagem_a_enviar"), ("estatuto", "fato_confirmado"),
                           ("emissor", "ausente"), ("destinatario", "ren")):
            tx = transaction("informacao")
            tx["memoria"]["fatos"][0][key] = value
            with self.subTest(key=key), self.assertRaises(memory.DurableMemoryError):
                self.compile(tx)

    def test_troca_exclusiva_entre_npcs_nao_confere_conhecimento_a_ren(self):
        tx = transaction("informacao")
        fact = tx["memoria"]["fatos"][0]
        fact["participantes"].append("nera_fixture")
        fact.update(emissor="nera_fixture", destinatario="silva_fixture")
        with self.assertRaises(memory.DurableMemoryError):
            self.compile(tx)

    def relationship(self):
        tx = transaction()
        fact = tx["memoria"]["fatos"][0]
        fact.pop("texto")
        fact.update(tipo="relacao", npc="silva_fixture", eixo="confianca", anterior=5, variacao=1)
        return tx

    def test_relacao_reutiliza_inc_e_fato_canonico(self):
        tx = self.relationship()
        delta = self.compile(tx)["deltas"][0]
        self.assertEqual((delta["op"], delta["caminho"], delta["valor"]), ("inc", "medidores.confianca", 1))
        self.assertEqual(delta["fato_canonico"], tx["narracao"])

    def test_relacao_nao_aceita_salto_boolean_null_ou_overflow(self):
        for key, value in (("variacao", True), ("variacao", 2), ("anterior", None),
                           ("anterior", 10), ("anterior", -1), ("eixo", "obediencia")):
            tx = self.relationship()
            tx["memoria"]["fatos"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(memory.DurableMemoryError):
                self.compile(tx)

    def test_dois_fatos_nao_podem_saltar_dois_pontos_no_mesmo_eixo(self):
        tx = self.relationship()
        second = deepcopy(tx["memoria"]["fatos"][0])
        second["id"] = "outro"
        tx["memoria"]["fatos"].append(second)
        with self.assertRaises(memory.DurableMemoryError):
            self.compile(tx)

    def test_delta_manual_nao_pode_sobrescrever_memoria_ou_medidor(self):
        for path in ("medidores", "medidores.confianca", "medidores.confianca.valor"):
            tx = self.relationship()
            tx["deltas"] = [{"alvo": "npc:silva_fixture", "op": "set", "caminho": path, "valor": {}}]
            with self.subTest(path=path), self.assertRaises(memory.DurableMemoryError):
                self.compile(tx)
        tx = transaction()
        tx["deltas"] = [{"alvo": "relacao:silva_fixture", "op": "set", "caminho": "memorias_importantes", "valor": []}]
        with self.assertRaises(memory.DurableMemoryError):
            self.compile(tx)

    def test_delta_independente_e_preservado(self):
        tx = transaction()
        raw = {"alvo": "estado", "op": "set", "caminho": "localizacao.ponto_exato", "valor": "mesa"}
        tx["deltas"] = [raw]
        self.assertEqual(self.compile(tx)["deltas"][0], raw)

    def test_assinatura_muda_quando_conclusao_e_adulterada(self):
        tx = transaction()
        first = self.compile(tx)["deltas"][0]["valor"]["registro_sha256"]
        tx["resumo"] += " Outra conclusão."
        self.assertNotEqual(first, self.compile(tx)["deltas"][0]["valor"]["registro_sha256"])

    def test_orcamento_de_entrada_e_numero_de_fatos_sao_limitados(self):
        tx = transaction()
        tx["memoria"]["fatos"] *= 9
        with self.assertRaises(memory.DurableMemoryError):
            self.compile(tx)
        tx = transaction()
        tx["memoria"]["fatos"][0]["texto"] = "x" * 9000
        with self.assertRaises(memory.DurableMemoryError):
            self.compile(tx)

    def test_ponteiros_nao_escapam_do_dominio(self):
        for relative in ("/etc/a.yaml", "estado/relacoes/../../x.yaml", "estado/npcs/a.yaml", "estado/relacoes/a.py"):
            with self.subTest(relative=relative), self.assertRaises(memory.DurableMemoryError):
                memory._path(Path("/tmp/fixture"), relative, "estado/relacoes")


if __name__ == "__main__":
    unittest.main()
