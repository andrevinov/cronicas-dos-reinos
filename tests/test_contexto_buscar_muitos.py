from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
MODULE_PATH = TOOLS / "contexto-buscar-muitos.py"
spec = importlib.util.spec_from_file_location("contexto_buscar_muitos", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

import politica_acesso as politica


class ContextoBuscarMuitosTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "runtime").mkdir(parents=True)
        (self.repo / "cenario").mkdir(parents=True)
        (self.repo / "historico").mkdir(parents=True)
        (self.repo / "narrador").mkdir(parents=True)
        (self.repo / "sessoes/001").mkdir(parents=True)
        (self.repo / "runtime/eventos-pendentes.jsonl").write_text("", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(MODULE_PATH), "--repo", str(self.repo), *args],
            text=True,
            capture_output=True,
            check=False,
        )

    def test_tres_lacunas_relacionadas_voltam_agrupadas_em_uma_resposta(self):
        (self.repo / "cenario/pistas.md").write_text(
            "O menino foi visto perto da doca.\n"
            "O barril seco ficou junto ao muro.\n"
            "Brass não toca mais em papéis depois do sino.\n",
            encoding="utf-8",
        )
        data = mod.command_search_many(
            self.repo,
            ["menino", "barril seco", "não toca mais em papéis"],
            reserved=False,
            historical=False,
        )
        self.assertEqual(data["consulta"]["comando"], "buscar-muitos")
        self.assertEqual(data["nivel"], "L3")
        self.assertEqual(data["resultado"]["quantidade_termos"], 3)
        self.assertTrue(data["resultado"]["todos_encontrados"])
        self.assertEqual(len(data["resultado"]["resultados"]), 3)
        self.assertEqual(data["fontes"], ["cenario/pistas.md"])

    def test_pendencia_corrente_tem_prioridade_sem_duplicar_fonte(self):
        (self.repo / "cenario/pistas.md").write_text(
            "O menino apareceu antes junto ao cais.\nO barril seco está marcado.\n",
            encoding="utf-8",
        )
        record = {
            "versao": 1,
            "id": "tx-menino",
            "sessao": 3,
            "resumo": "O menino agora está protegido no pátio norte.",
            "deltas": [],
        }
        (self.repo / "runtime/eventos-pendentes.jsonl").write_text(
            json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        data = mod.command_search_many(
            self.repo,
            ["menino", "barril seco"],
            reserved=False,
            historical=False,
        )
        first = data["resultado"]["resultados"][0]["ocorrencias"][0]
        self.assertEqual(first["arquivo"], "runtime/eventos-pendentes.jsonl")
        self.assertEqual(first["transacao"], "tx-menino")
        self.assertEqual(len(data["fontes"]), len(set(data["fontes"])))

    def test_orcamento_e_global_para_o_lote_inteiro(self):
        terms = ["agulha", "bronze", "corda", "lamparina", "ponte"]
        for term in terms:
            lines = [f"{term} " + ("detalhe extenso " * 80) + str(index) for index in range(8)]
            (self.repo / f"cenario/{term}.md").write_text("\n".join(lines), encoding="utf-8")

        data = mod.command_search_many(
            self.repo,
            terms,
            reserved=False,
            historical=False,
        )
        decision = politica.classify("buscar")
        decorated, budget = politica.decorate(
            data,
            decision,
            requested_budget=99999,
            after="L2",
            reason="As cinco lacunas pertencem à mesma decisão de investigação corrente.",
        )
        rendered, truncated = mod.contexto.fit_budget(decorated, budget, False)
        self.assertTrue(truncated)
        self.assertEqual(budget, 8 * 1024)
        self.assertLessEqual(len(rendered.encode("utf-8")), 8 * 1024)

    def test_historico_nao_implica_transcricao(self):
        (self.repo / "historico/pista.md").write_text("arquivo frio menciona selo violeta\n", encoding="utf-8")
        (self.repo / "sessoes/001/transcricao.md").write_text(
            "fala literal menciona sino quebrado\n", encoding="utf-8"
        )
        historical = mod.command_search_many(
            self.repo,
            ["selo violeta", "sino quebrado"],
            reserved=False,
            historical=True,
            transcripts=False,
        )
        groups = {item["termo"]: item for item in historical["resultado"]["resultados"]}
        self.assertTrue(groups["selo violeta"]["encontrado"])
        self.assertFalse(groups["sino quebrado"]["encontrado"])

        transcripts = mod.command_search_many(
            self.repo,
            ["selo violeta", "sino quebrado"],
            reserved=False,
            historical=True,
            transcripts=True,
        )
        groups = {item["termo"]: item for item in transcripts["resultado"]["resultados"]}
        self.assertTrue(groups["sino quebrado"]["encontrado"])
        self.assertIn("sessoes/001/transcricao.md", transcripts["fontes"])

    def test_cli_usa_a_mesma_escada_de_buscar(self):
        (self.repo / "cenario/pistas.md").write_text("menino aqui\nbarril seco aqui\n", encoding="utf-8")

        missing_escalation = self._run("menino", "barril seco")
        self.assertNotEqual(missing_escalation.returncode, 0)
        self.assertIn("--apos L2", missing_escalation.stderr)

        l3 = self._run(
            "menino",
            "barril seco",
            "--apos",
            "L2",
            "--motivo",
            "As duas lacunas pertencem à mesma decisão de investigação.",
        )
        self.assertEqual(l3.returncode, 0, l3.stderr)
        self.assertIn("nivel: L3", l3.stdout)

        wrong_l4 = self._run(
            "menino",
            "barril seco",
            "--historico",
            "--apos",
            "L2",
            "--motivo",
            "A busca corrente não localizou a origem histórica necessária.",
        )
        self.assertNotEqual(wrong_l4.returncode, 0)
        self.assertIn("--apos L3", wrong_l4.stderr)

        l4 = self._run(
            "menino",
            "barril seco",
            "--historico",
            "--apos",
            "L3",
            "--motivo",
            "A busca corrente não localizou a origem histórica necessária.",
        )
        self.assertEqual(l4.returncode, 0, l4.stderr)
        self.assertIn("nivel: L4", l4.stdout)

    def test_transcricoes_exigem_historico_e_l4_previo(self):
        (self.repo / "sessoes/001/transcricao.md").write_text("menino\nbarril seco\n", encoding="utf-8")
        no_history = self._run(
            "menino",
            "barril seco",
            "--transcricoes",
            "--apos",
            "L4",
            "--motivo",
            "A formulação literal é necessária para resolver estas duas lacunas.",
        )
        self.assertNotEqual(no_history.returncode, 0)
        self.assertIn("--historico", no_history.stderr)

        wrong_after = self._run(
            "menino",
            "barril seco",
            "--historico",
            "--transcricoes",
            "--apos",
            "L3",
            "--motivo",
            "O histórico estruturado não contém a formulação literal necessária.",
        )
        self.assertNotEqual(wrong_after.returncode, 0)
        self.assertIn("--apos L4", wrong_after.stderr)

    def test_lote_recusa_uma_lacuna_ou_mais_de_cinco(self):
        with self.assertRaises(ValueError):
            mod.validate_terms(["uma"])
        with self.assertRaises(ValueError):
            mod.validate_terms(["a", "b", "c", "d", "e", "f"])
        with self.assertRaises(ValueError):
            mod.validate_terms(["menino", "Menino"])


if __name__ == "__main__":
    unittest.main()
