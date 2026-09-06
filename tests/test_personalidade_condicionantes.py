"""Condições do perfil e estabilidade da paginação em fonte sintética isolada."""
import json
import unittest

import test_personalidade_decisoria as cases
import test_personalidade_memoria as selection


class PersonalityConditionAndPageContractTest(unittest.TestCase):
    def test_condicionantes_da_fonte_nao_sao_perdidos_na_projecao(self):
        for person, entry in cases.roles().items():
            out = cases.personality.project(person, entry["papel_conversacional"])
            for value in out["estavel"].values():
                if value is None:
                    continue
                source = entry["papel_conversacional"]
                for part in value["origem"].strip("/").split("/"):
                    source = source[int(part)] if isinstance(source, list) else source[part]
                self.assertEqual(value["texto"], " ".join(source.split()))
        luath = cases.profile("luath")["estavel"]
        self.assertIn("em operação", luath["metodos_preferidos"]["texto"])
        self.assertIn("fora de assunto operacional", luath["relacionamento"]["texto"])

    def test_consulta_dirigida_preserva_ordem_da_fonte_ao_adicionar_derivado(self):
        doc = cases.document(z_ultimo="primeiro na fonte", a_primeiro="segundo na fonte")
        request = selection.relevant.request(doc, campo="/medidores/dados")
        text, _ = selection.relevant.fit(request, 8192, True, selection.serialize)
        items = json.loads(text)["resultado"]["itens"]
        self.assertEqual([item["chave"] for item in items], ["z_ultimo", "a_primeiro"])
        page = selection.relevant.request(doc, campo="/medidores/dados", inicio=1)
        text, _ = selection.relevant.fit(page, 8192, True, selection.serialize)
        self.assertEqual(json.loads(text)["resultado"]["itens"][0]["chave"], "a_primeiro")

    def test_contrariar_valor_sem_apoio_nao_recomenda_mentir_em_vez_de_calar(self):
        profile = cases.profile()
        choices = [cases.option("calar"),
                   cases.option("mentir", opposes={"verdade_verificavel": "Afirma algo falso."}),
                   cases.option("mentir_com_apoio_inexistente", {"poder_inventado": "Não está no perfil."},
                                {"verdade_verificavel": "Afirma algo falso."})]
        out = cases.personality.evaluate_options(profile, choices)
        self.assertEqual(out["preferiveis"], [])
        self.assertEqual(out["alternativas"][0]["status"], "sem_fundamento_no_perfil")
        self.assertTrue(all(row["status"] == "contraria_sem_apoio" for row in out["alternativas"][1:]))
        self.assertTrue(all(row["justificativas"] for row in out["alternativas"][1:]))

    def test_fatos_ganham_disputa_com_perfil_interpretativo(self):
        doc = cases.document(nome="Silva da fixture")
        bond = "Vínculo canônico da fixture. " * 8
        knowledge = "Informação recebida e limitada à fixture. " * 8
        promise = "Promessa ainda pendente da fixture. " * 8
        doc["resultado"]["relacao"] = {"id": "silva_elkwood", "dados": {
            "vinculo": bond, "informacoes_recebidas": knowledge, "acordos": promise}}
        text, _ = selection.relevant.fit(doc, 2000, False, selection.serialize)
        out = selection.yaml.safe_load(text)
        result = out["resultado"]
        self.assertEqual(result["relacao"]["dados"]["vinculo"], bond)
        self.assertEqual(result["relacao"]["dados"]["informacoes_recebidas"], knowledge)
        self.assertEqual(result["relacao"]["dados"]["acordos"], promise)
        self.assertNotIn(cases.personality.KEY, result)
        self.assertTrue(out["memoria_relevante"]["aprofundamento_necessario"])
        self.assertIn("/personalidade_decisoria", [x["campo"] for x in out["memoria_relevante"]["pendentes"]])
        self.assertLessEqual(len(text.encode()), 2000)
