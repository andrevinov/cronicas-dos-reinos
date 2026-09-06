"""Overlays e CLI reais em diretórios sintéticos; nenhuma escrita no save vivo."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

from test_memoria_relevante import ROOT, cases, make_repo, snapshot, write_yaml
import contexto
import benchmark_sondas


def pending(repo, deltas):
    record = {"versao": 1, "id": "memoria-fixture", "sessao": 1,
              "resumo": "Alterações sintéticas para testar consulta antes do checkpoint.", "deltas": deltas}
    (repo / "runtime/eventos-pendentes.jsonl").write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")


class MemoriaEfetivaIntegrationTest(unittest.TestCase):
    def render(self, data):
        text, _ = contexto.fit_budget(data, 8192, True)
        self.assertLessEqual(len(text.encode("utf-8")), 8192)
        return yaml.safe_load(text)

    def test_alteracao_profunda_e_incremento_chegam_a_consulta_antes_da_selecao(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            case = cases()[2]
            case["relacao"]["conhecimento_sobre_ren"] = {
                "registro": {"origem": {"detalhes": {"tentativas": 2, "confirmado": False}}}}
            make_repo(repo, case)
            pending(repo, [{"alvo": "relacao:luath", "op": "inc", "caminho": "conhecimento_sobre_ren.registro.origem.detalhes.tentativas", "valor": 1}])
            before = snapshot(repo)
            for command in (contexto.command_npc, contexto.command_relation):
                data = command(repo, "luath")
                out = self.render(data)
                rel = out["resultado"]["relacao"]
                rel = rel.get("dados", rel)
                self.assertEqual(rel["conhecimento_sobre_ren"]["registro"]["origem"]["detalhes"], {"tentativas": 3, "confirmado": False})
                self.assertEqual(out["resultado"]["deltas_pendentes_aplicados"], 1)
                self.assertIn("runtime/eventos-pendentes.jsonl", out["fontes"])
            self.assertEqual(before, snapshot(repo))

    def test_append_remove_e_set_usam_listas_inteiras_e_reconsulta_nao_duplica(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            case = cases()[0]
            old = [f"Acordo antigo {i}. " + "Condição integral. " * 80 for i in range(12)]
            case["relacao"]["acordos"] = old
            make_repo(repo, case)
            new = "Ren devolveu o mapa; ficou combinado revisar a ponte amanhã."
            pending(repo, [
                {"alvo": "relacao:silva_elkwood", "op": "remove", "caminho": "acordos", "valor": old[-1]},
                {"alvo": "relacao:silva_elkwood", "op": "append", "caminho": "acordos", "valor": new},
                {"alvo": "relacao:silva_elkwood", "op": "set", "caminho": "confianca", "valor": "alta"}])
            before = snapshot(repo)
            first = contexto.command_npc(repo, "silva")
            second = contexto.command_npc(repo, "silva")
            self.assertEqual(first, second)
            raw = first["resultado"]["relacao"]["dados"]
            self.assertEqual(raw["acordos"], old[:-1] + [new])
            out = self.render(first)["resultado"]["relacao"]["dados"]
            self.assertIn(new, out["acordos"])
            self.assertNotIn(old[-1], out["acordos"])
            self.assertEqual(out["confianca"], "alta")
            self.assertEqual(before, snapshot(repo))

    def test_medidor_completo_sobreposto_alimenta_dialogo_antes_do_orcamento(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            make_repo(repo, cases()[1])
            meter = {"nome": "Nera Vell", "registro": {"origem": {"detalhes": {"tentativas": 7}}}}
            write_yaml(repo, "estado/npcs/index.yaml", {"npcs": {"nera_vell": {"nome": "Nera Vell", "arquivo": "estado/npcs/nera_vell.yaml"}}})
            write_yaml(repo, "estado/npcs/nera_vell.yaml", {"npc": meter})
            pending(repo, [{"alvo": "npc:nera_vell", "op": "inc", "caminho": "registro.origem.detalhes.tentativas", "valor": 1}])
            # O teste isola a entrada do projetor; a semântica do diálogo tem suíte própria.
            with patch.object(contexto.dialogo_relacional, "project", return_value=None) as project:
                data = contexto.command_npc(repo, "nera")
            expected = {"nome": "Nera Vell", "registro": {"origem": {"detalhes": {"tentativas": 8}}}}
            self.assertEqual(project.call_args.args[0], expected)
            self.assertEqual(self.render(data)["resultado"]["medidores"]["dados"], expected)

    def test_delta_reservado_nao_vaza_por_projecao_nem_por_consulta_dirigida(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            make_repo(repo, cases()[0])
            pending(repo, [{"alvo": "relacao:silva_elkwood", "op": "set", "caminho": "conhecimento_sobre_ren", "valor": "SEGREDO_NAO_TRANSMITIDO", "visibilidade": "narrador"}])
            data = contexto.command_npc(repo, "silva")
            out = self.render(data)
            self.assertNotIn("SEGREDO_NAO_TRANSMITIDO", json.dumps(out))
            directed = contexto.memoria_relevante.request(data, campo="/relacao/dados")
            self.assertNotIn("SEGREDO_NAO_TRANSMITIDO", json.dumps(self.render(directed)))

    def test_consultas_reais_preservam_fatos_das_tres_fixtures_sem_historico(self):
        for case in cases():
            with self.subTest(npc=case["id"]), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                make_repo(repo, case)
                before = snapshot(repo)
                with patch.object(contexto, "generic_search", side_effect=AssertionError("busca ampla")), patch.object(contexto.continuidade_autoral, "lookup", side_effect=AssertionError("segredo")):
                    data = contexto.command_npc(repo, case["id"])
                    out = self.render(data)
                self.assertEqual(out["resultado"]["relacao"]["dados"], case["relacao"])
                self.assertFalse(any(p.startswith(("historico/", "sessoes/", "narrador/")) for p in data["fontes"]))
                self.assertEqual(before, snapshot(repo))

    def test_cli_publica_dirige_consulta_sobre_estado_pendente_e_aplica_teto_l2(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            make_repo(repo, cases()[0])
            pending(repo, [{"alvo": "relacao:silva_elkwood", "op": "append", "caminho": "acordos", "valor": "Nova promessa pendente."}])
            before = snapshot(repo)
            cmd = [sys.executable, str(ROOT / "ferramentas/contexto.py"), "--repo", str(repo), "--json", "--max-bytes", "999999", "npc", "silva"]
            proc = subprocess.run(cmd + ["--campo", "/relacao/dados/acordos"], capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertLessEqual(len(proc.stdout.encode("utf-8")), 8192)
            self.assertEqual(json.loads(proc.stdout)["resultado"]["itens"][-1]["valor"], "Nova promessa pendente.")
            bad = subprocess.run(cmd + ["--campo", "/nao_existe"], capture_output=True, text=True)
            self.assertEqual(bad.returncode, 1)
            self.assertNotIn("Traceback", bad.stderr)
            self.assertEqual(before, snapshot(repo))

    def test_sonda_nv02_reencontro_agora_entrega_promessa_e_vinculo(self):
        report = benchmark_sondas.probe()
        reunion = next(e for e in report["episodios"] if e["cenario"] == "reencontro_aliado")
        checks = reunion["amostras"][0]["checagens_estruturais"]
        self.assertTrue(checks["promessa_visivel"])
        self.assertTrue(checks["vinculo_visivel"])
        self.assertTrue(checks["teto_respeitado"])
        self.assertIsNone(report["totais"]["tokens_nativos"])


if __name__ == "__main__":
    unittest.main()
