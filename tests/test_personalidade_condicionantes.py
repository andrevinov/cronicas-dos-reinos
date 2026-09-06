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
