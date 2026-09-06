"""Memória relevante: cenários sintéticos, não expectativas sobre o save vivo."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ferramentas"))
import contexto_core as core
import memoria_relevante as memory


def cases():
    return json.loads((ROOT / "tests/fixtures/memoria-relevante-v1.json").read_text(encoding="utf-8"))["casos"]


def write_yaml(repo, name, value):
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(core.serialize(value, False), encoding="utf-8")


def make_repo(repo, case, *, noise=True):
    key = case["id"]
    relation = {"nome": case["relacao"]["nome"]}
    if noise:
        relation.update({f"contexto_secundario_{i}": "Rotina antiga da oficina. " * 80 for i in range(30)})
    relation.update(deepcopy(case["relacao"]))
    write_yaml(repo, "estado/relacoes/index.yaml", {"relacoes": {key: {
        "nome": relation["nome"], "arquivo": f"estado/relacoes/{key}.yaml",
        "historico": "historico/nao-deve-ser-lido.yaml"}}})
    write_yaml(repo, f"estado/relacoes/{key}.yaml", {"natureza": "fixture_sintetica", "relacao": relation})
    write_yaml(repo, "estado/npcs/index.yaml", {"npcs": {}})
    write_yaml(repo, "cenario/texturas/index.yaml", {"npcs": {}, "locais": {}})
    (repo / "runtime").mkdir(exist_ok=True)
    (repo / "runtime/eventos-pendentes.jsonl").write_text("", encoding="utf-8")
    return relation


def snapshot(repo):
    return {str(p.relative_to(repo)): p.read_bytes() for p in repo.rglob("*") if p.is_file()}


class MemoriaRelevanteTest(unittest.TestCase):
    def data(self, relation):
        return core.envelope("relacao", "alvo", "L2", ["estado/relacoes/alvo.yaml"],
                             {"encontrado": True, "id": "alvo", "relacao": relation})

    def render(self, data, budget=8192, as_json=False):
        text, truncated = core.fit_budget(data, budget, as_json)
        self.assertLessEqual(len(text.encode("utf-8")), max(1024, min(budget, 16384)))
        self.assertNotIn("conteúdo adicional omitido", text)
        return yaml.safe_load(text), truncated

    def test_silva_nera_luath_preservam_fatos_depois_de_trinta_campos_secundarios(self):
        for case in cases():
            for command in ("npc", "relacao"):
                for as_json in (False, True):
                    with self.subTest(npc=case["id"], comando=command, json=as_json), tempfile.TemporaryDirectory() as tmp:
                        repo = Path(tmp)
                        make_repo(repo, case)
                        before = snapshot(repo)
                        data = getattr(core, "command_npc" if command == "npc" else "command_relation")(repo, case["id"])
                        out, truncated = self.render(data, as_json=as_json)
                        relation = out["resultado"]["relacao"]
                        if command == "npc":
                            relation = relation["dados"]
                        self.assertEqual(relation, case["relacao"])
                        self.assertFalse(truncated)
                        self.assertEqual(out["memoria_relevante"]["campos_secundarios"], 30)
                        self.assertFalse(out["memoria_relevante"]["aprofundamento_necessario"])
                        self.assertEqual(before, snapshot(repo))

    def test_nucleo_nao_compacta_antes_do_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            relation = make_repo(repo, cases()[0])
            raw = core.command_npc(repo, "silva")
            self.assertEqual(raw["resultado"]["relacao"]["dados"], relation)
            self.assertGreater(len(raw["resultado"]["relacao"]["dados"]), 24)

    def test_projecao_e_pura_deterministica_e_independe_da_ordem_dos_campos(self):
        data = self.data(deepcopy(cases()[0]["relacao"]))
        before = deepcopy(data)
        first = self.render(data)
        self.assertEqual(data, before)
        data["resultado"]["relacao"] = dict(reversed(list(data["resultado"]["relacao"].items())))
        self.assertEqual(first, self.render(data))

    def test_nao_corta_fato_nem_perde_limite_de_conhecimento_por_profundidade(self):
        fact = {"relato": {"fonte": {"canal": {"detalhes": {"texto": "Enviado, não confirmado.", "confirmado": False}}}}}
        out, truncated = self.render(self.data({"nome": "Luath", "conhecimento_recebido_por_carta": [fact]}))
        self.assertEqual(out["resultado"]["relacao"]["conhecimento_recebido_por_carta"], [fact])
        self.assertFalse(truncated)

    def test_ultimo_item_de_lista_longa_sobrevive_e_indices_sao_explicitos(self):
        facts = [f"Promessa {i}: " + "çã漢🙂 " * 40 for i in range(50)]
        data = self.data({"nome": "Silva", "acordos": facts, "momentos_de_vinculo": ["Abrigo durante a tempestade."]})
        for as_json in (False, True):
            out, truncated = self.render(data, 4096, as_json)
            self.assertTrue(truncated)
            self.assertIn(facts[-1], out["resultado"]["relacao"]["acordos"])
            self.assertIn("Abrigo durante a tempestade.", out["resultado"]["relacao"]["momentos_de_vinculo"])
            indices = out["memoria_relevante"]["indices_origem"]["/relacao/acordos"]
            self.assertEqual(out["resultado"]["relacao"]["acordos"], [facts[i] for i in indices])
            self.assertTrue(out["memoria_relevante"]["aprofundamento_necessario"])

    def test_fato_indispensavel_grande_gera_necessidade_nao_resumo(self):
        fact = "Limite importante. " * 3000
        for budget in (1024, 2048, 4096, 8192, 16384):
            for as_json in (False, True):
                out, truncated = self.render(self.data({"nome": "Nera", "acordos": [fact]}), budget, as_json)
                self.assertTrue(truncated)
                self.assertTrue(out["memoria_relevante"]["aprofundamento_necessario"])
                self.assertIn({"campo": "/relacao/acordos", "itens": 1}, out["memoria_relevante"]["pendentes"])
                self.assertNotIn("acordos", out["resultado"]["relacao"])

    def test_fontes_ou_termo_gigantes_nao_estouram_teto(self):
        data = self.data({"nome": "Silva", "acordos": ["Acordo."]})
        data["fontes"] = ["fonte" * 2000] * 20
        for as_json in (False, True):
            out, truncated = self.render(data, 1024, as_json)
            self.assertTrue(truncated)
            self.assertTrue(out["resultado"]["aprofundamento_necessario"])

    def test_consulta_dirigida_recupera_secundario_sem_busca_ampla(self):
        data = self.data({"nome": "Luath", "experiencia_previa": {"oficio": "analista", "limite": "alcance desconhecido"}})
        out, _ = self.render(memory.request(data, campo="/relacao/experiencia_previa"))
        self.assertEqual(out["resultado"]["itens"], [
            {"chave": "oficio", "valor": "analista"}, {"chave": "limite", "valor": "alcance desconhecido"}])
        self.assertIsNone(out["resultado"]["proximo_inicio"])

    def test_paginacao_reconstroi_lista_sem_saltar_duplicar_ou_cortar_fatos(self):
        facts = [f"Fato {i}: " + "漢çã " * 40 for i in range(25)]
        data = self.data({"acordos": facts})
        for as_json in (False, True):
            start, collected = 0, []
            while start is not None:
                out, _ = self.render(memory.request(data, campo="/relacao/acordos", inicio=start), 2048, as_json)
                result = out["resultado"]
                self.assertNotIn("item_nao_cabe", result)
                collected.extend(i["valor"] for i in result["itens"])
                next_start = result["proximo_inicio"]
                self.assertTrue(next_start is None or next_start > start)
                start = next_start
            self.assertEqual(collected, facts)

    def test_item_gigante_nao_devolve_cursor_infinito(self):
        out, truncated = self.render(memory.request(self.data({"acordos": ["x" * 20000]}), campo="/relacao/acordos"), 2048)
        self.assertTrue(truncated)
        self.assertEqual(out["resultado"]["item_nao_cabe"], 0)
        self.assertIsNone(out["resultado"]["proximo_inicio"])
        self.assertTrue(out["resultado"]["aprofundamento_necessario"])

    def test_catalogo_dirigido_paginavel_inclui_campos_nao_classificados(self):
        data = self.data({f"secundario_{i}": "não retornar o texto" for i in range(30)})
        start, paths = 0, []
        while start is not None:
            out, _ = self.render(memory.request(data, campos=True, inicio=start), 2048)
            self.assertNotIn("não retornar o texto", core.serialize(out, True))
            paths.extend(i["campo"] for i in out["resultado"]["itens"])
            start = out["resultado"]["proximo_inicio"]
        self.assertEqual(set(paths), {f"/relacao/secundario_{i}" for i in range(30)})
        self.assertEqual(len(paths), 30)

    def test_ponteiros_invalidos_nao_sao_caminhos_de_arquivos(self):
        data = self.data({"acordos": ["Fato"], "chave/~": "ok"})
        out, _ = self.render(memory.request(data, campo="/relacao/chave~1~0"))
        self.assertEqual(out["resultado"]["itens"][0]["valor"], "ok")
        for path in ("../../narrador", "/inexistente", "/relacao/acordos/-1", "/relacao/acordos/01", "/relacao/~2"):
            with self.subTest(campo=path), self.assertRaises(ValueError):
                self.render(memory.request(data, campo=path))
        with self.assertRaises(ValueError):
            memory.request(data, inicio=1)
        with self.assertRaises(ValueError):
            memory.request(data, campo="/relacao", inicio=-1)

    def test_valores_vazios_e_tipos_nao_sao_convertidos_em_prosa(self):
        value = {"nome": "Nera", "confianca": 0, "acordos": [], "divida": None}
        out, truncated = self.render(self.data(value))
        self.assertEqual(out["resultado"]["relacao"], value)
        self.assertFalse(truncated)

    def test_textura_e_limite_de_autoridade_sao_fatos_inteiros(self):
        data = core.envelope("npc", "alvo", "L2", [], {"encontrado": True, "relacao": None,
            "medidores": None, "textura_narrativa": {"voz": "baixa", "papel_conversacional": {
                "papel": "guardia_pragmatica", "limite_de_autoridade": "Não cria conhecimento."}}})
        out, _ = self.render(data)
        self.assertEqual(out["resultado"]["textura_narrativa"], data["resultado"]["textura_narrativa"])

    def test_outras_consultas_preservam_compactacao_anterior(self):
        text, truncated = core.fit_budget(core.envelope("status", None, "L1", [], {"texto": "x" * 30000}), 2048, False)
        self.assertTrue(truncated)
        self.assertLessEqual(len(text.encode("utf-8")), 2048)
        self.assertNotIn("memoria_relevante", text)

    def test_cli_nucleo_consulta_dirigida_e_falha_sem_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            make_repo(repo, cases()[0])
            cmd = [sys.executable, str(ROOT / "ferramentas/contexto_core.py"), "--repo", str(repo), "--sem-log", "--json", "npc", "silva"]
            proc = subprocess.run(cmd + ["--campo", "/relacao/dados/acordos"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(json.loads(proc.stdout)["resultado"]["itens"][0]["valor"], cases()[0]["relacao"]["acordos"][0])
            bad = subprocess.run(cmd + ["--campo", "/nao_existe"], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 1)
            self.assertNotIn("Traceback", bad.stdout + bad.stderr)


if __name__ == "__main__":
    unittest.main()
