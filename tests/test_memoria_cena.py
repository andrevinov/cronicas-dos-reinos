"""Contratos puros de memória de cena; dados inteiramente sintéticos."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "ferramentas"))
import memoria_cena as memory


def document(name="Aliada", **extra):
    return {"consulta": {"comando": "npc"}, "fontes": [], "resultado": {
        "encontrado": True, "relacao": {"id": "aliada", "dados": {
            "nome": name, "vinculo": "Ren resgatou sua família.",
            "acordos": ["Conversar depois do ensaio."],
            "informacoes_recebidas": [{"texto": "Relato não confirmado.", "estatuto": "rumor", "emissor": "ren"}],
            "memorias_importantes": ["A noite em que dividiram a vigília."], **extra}}}}


def cast(people=None):
    return {"versao": 1, "cena_id": "cena_a", "local": {"area": "praça", "ponto_exato": "banco"},
            "participantes": ["aliada"] if people is None else people}


class SceneMemoryProjectionTest(unittest.TestCase):
    def project(self, docs=None, **kwargs):
        return memory.project({"aliada": document()} if docs is None else docs,
                              scope="a" * 24, budget=4096, **kwargs)

    def test_identidade_vinculo_promessa_informacao_e_marco_sobrevivem(self):
        out = self.project()
        rel = out["itens"]["aliada"]["relacao"]["dados"]
        self.assertEqual(rel, document()["resultado"]["relacao"]["dados"])
        self.assertFalse(out["aprofundamento_necessario"])

    def test_ordem_estavel_e_entrada_intacta(self):
        docs = {"b": document("B"), "a": document("A")}
        before = deepcopy(docs)
        out = self.project(docs)
        self.assertEqual(out, self.project(dict(reversed(list(docs.items())))))
        self.assertEqual(docs, before)

    def test_nao_carrega_biografia_secundaria(self):
        out = self.project({"aliada": document(biografia="INUTIL " * 5000)})
        self.assertNotIn("INUTIL", memory.canonical(out))

    def test_fato_indivisivel_exige_aprofundamento_sem_texto_cortado(self):
        out = self.project({"aliada": document(acordos=["INDIVISIVEL " * 2000])})
        self.assertTrue(out["aprofundamento_necessario"])
        self.assertNotIn("INDIVISIVEL", memory.canonical(out))
        self.assertIn("/relacao/dados/acordos", memory.canonical(out))
        self.assertLessEqual(memory.size(out), 4096)

    def test_seis_participantes_compartilham_um_teto(self):
        docs = {f"npc_{n}": document(str(n), memorias_importantes=["memória " * 30] * 20) for n in range(6)}
        out = self.project(docs)
        self.assertEqual(set(out["itens"]), set(docs))
        self.assertLessEqual(memory.size(out), 4096)
        self.assertTrue(out["aprofundamento_necessario"])

    def test_lista_parcial_indica_indices_de_origem(self):
        out = self.project({"aliada": document(memorias_importantes=["memória " * 50] * 30)})
        self.assertIn("indices_origem", memory.canonical(out))

    def test_sem_recibo_sempre_entrega_base_completa(self):
        a = self.project()
        self.assertEqual(a, self.project())
        self.assertEqual(a["modo"], "completa")

    def test_recibo_explicito_reutiliza_base_sem_retransmitir(self):
        a = self.project()
        b = self.project(base=a["recibo"])
        self.assertEqual(b["modo"], "delta")
        self.assertEqual(b["itens"], {})
        self.assertEqual(b["base"], memory.digest(a["recibo"]))
        self.assertLess(memory.size(b), memory.size(a))

    def test_delta_substitui_so_participante_alterado(self):
        docs = {"a": document("A"), "b": document("B")}
        old = self.project(docs)
        docs["a"]["resultado"]["relacao"]["dados"]["vinculo"] = "Vínculo mudou."
        out = self.project(docs, base=old["recibo"])
        self.assertEqual(set(out["itens"]), {"a"})
        self.assertEqual(out["modo"], "delta")

    def test_saida_de_participante_vem_no_delta(self):
        old = self.project({"a": document("A"), "b": document("B")})
        new = self.project({"b": document("B")}, base=old["recibo"])
        self.assertEqual(new["removidos"], ["a"])
        self.assertEqual(new["itens"], {})

    def test_outro_escopo_forca_base_completa(self):
        base = self.project()["recibo"]
        base["escopo"] = "b" * 24
        self.assertEqual(self.project(base=base)["modo"], "completa")

    def test_receipt_invalido_e_boolean_nao_passam(self):
        for bad in ({}, {"versao": True, "escopo": "a" * 24, "itens": {}}, "null", "{", "x" * 2000):
            with self.subTest(bad=str(bad)[:40]), self.assertRaises(memory.SceneMemoryError):
                memory.receipt(bad)

    def test_compromisso_compartilhado_nao_e_duplicado_por_npc(self):
        docs = {"a": document("A"), "b": document("B"),
                "@compromissos": {"encontro": {"resumo": "Encontro único", "envolvidos": ["a", "b"]}}}
        out = self.project(docs)
        self.assertEqual(memory.canonical(out).count("Encontro único"), 1)

    def test_fontes_dirigidas_sao_unificadas(self):
        d = document()
        d["fontes"] = ["estado/relacoes/index.yaml"]
        self.assertEqual(self.project({"a": d, "b": deepcopy(d)})["fontes"], d["fontes"])

    def test_orcamento_nunca_pode_ser_multiplicado_pelo_chamador(self):
        docs = {"a": document(memorias_importantes=["á" * 500] * 40)}
        out = memory.project(docs, scope="a" * 24, budget=100000)
        self.assertLessEqual(memory.size(out), 4096)


class SceneCastContractTest(unittest.TestCase):
    def payload(self, selected=None, previous=None):
        return {"cena": {"scene_id": "cena_a"}, memory.TICKET_KEY: {
            "elenco": cast() if selected is None else selected,
            "anterior": previous, "local": cast()["local"]}}

    def test_elenco_compila_no_delta_existente_sem_mutar_entrada(self):
        tx = {"resumo": "Uma conversa.", "deltas": []}
        original = deepcopy(tx)
        out = memory.compile_cast(self.payload(), tx)
        self.assertEqual(tx, original)
        self.assertEqual(out["deltas"], [{"alvo": "estado", "op": "set", "caminho": memory.CAST_PATH, "valor": cast()}])
        self.assertEqual(out, memory.compile_cast(self.payload(), tx))

    def test_elenco_inalterado_nao_gera_delta_ritual(self):
        tx = {"deltas": []}
        self.assertIs(memory.compile_cast(self.payload(previous=cast()), tx), tx)

    def test_sem_metadados_preserva_payload_legado(self):
        tx = {"deltas": []}
        self.assertIs(memory.compile_cast({}, tx), tx)

    def test_movimento_invalida_elenco_sem_teleporte(self):
        tx = {"deltas": [{"alvo": "estado", "op": "set", "caminho": "localizacao.area", "valor": "porto"}]}
        out = memory.compile_cast(self.payload(previous=cast()), tx)
        self.assertIsNone(out["deltas"][-1]["valor"])

    def test_atualizacao_explicita_pode_fechar_elenco_no_mesmo_turno(self):
        tx = {"deltas": [{"alvo": "estado", "op": "set", "caminho": memory.CAST_PATH, "valor": cast([])}]}
        self.assertIs(memory.compile_cast(self.payload(), tx), tx)

    def test_duplicata_subcampo_e_segredo_nao_corrompem_elenco(self):
        delta = {"alvo": "estado", "op": "set", "caminho": memory.CAST_PATH, "valor": cast()}
        bads = [[delta, delta], [{**delta, "visibilidade": "narrador"}],
                [{**delta, "caminho": memory.CAST_PATH + ".participantes"}],
                [{**delta, "op": "append"}]]
        for deltas in bads:
            with self.subTest(deltas=deltas), self.assertRaises(memory.SceneMemoryError):
                memory.compile_cast(self.payload(), {"deltas": deltas})

    def test_cena_divergente_e_elenco_invalido_falham(self):
        for wrong in (cast(["ren"]), cast(["../segredo"]), {**cast(), "versao": True}, {**cast(), "cena_id": "outra"}):
            with self.subTest(wrong=wrong), self.assertRaises(memory.SceneMemoryError):
                memory.compile_cast(self.payload(selected=wrong), {"deltas": []})

    def test_alias_exato_colapsa_sem_busca_aproximada(self):
        with tempfile.TemporaryDirectory() as tmp:
            reader = memory.Reader(Path(tmp))
            indexes = [{"nera_vell": {"nome": "Nera Vell", "aliases": ["Nera"]}}]
            self.assertEqual(reader.resolve(["Nera", "nera_vell"], indexes), ["nera_vell"])
            for bad in ("Nrea", "ner", "alguem"):
                with self.assertRaises(memory.SceneMemoryError):
                    reader.resolve([bad], indexes)
            self.assertEqual(reader.sources, [])

    def test_alias_ambiguo_nao_escolhe_outro_npc(self):
        with tempfile.TemporaryDirectory() as tmp:
            reader = memory.Reader(Path(tmp))
            index = {"sella_a": {"aliases": ["Sella"]}, "sella_b": {"aliases": ["Sella"]}}
            with self.assertRaises(memory.SceneMemoryError):
                reader.resolve(["Sella"], [index])

    def test_reader_memoiza_apenas_na_chamada_e_rejeita_fuga(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "estado").mkdir()
            path = repo / "estado/dado.yaml"
            path.write_text("valor: antes\n", encoding="utf-8")
            reader = memory.Reader(repo)
            self.assertEqual(reader.read("estado/dado.yaml"), {"valor": "antes"})
            path.write_text("valor: depois\n", encoding="utf-8")
            self.assertEqual(reader.read("estado/dado.yaml"), {"valor": "antes"})
            self.assertEqual(reader.sources, ["estado/dado.yaml"])
            self.assertEqual(memory.Reader(repo).read("estado/dado.yaml"), {"valor": "depois"})
            for path in ("../segredo.yaml", "estado/../narrador/segredo.yaml", "historico/relacoes/a.yaml"):
                with self.assertRaises(memory.SceneMemoryError):
                    reader.read(path)


if __name__ == "__main__":
    unittest.main()
