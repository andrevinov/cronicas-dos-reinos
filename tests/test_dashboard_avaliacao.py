from __future__ import annotations

import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
DASHBOARD = ROOT / "evaluation" / "dashboard"
SESSIONS = ROOT / "evaluation" / "sessions"


class EvaluationDashboardTest(unittest.TestCase):
    def test_dashboard_estatico_nao_depende_de_recursos_externos(self) -> None:
        html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
        css = (DASHBOARD / "styles.css").read_text(encoding="utf-8")
        javascript = (DASHBOARD / "app.js").read_text(encoding="utf-8")

        self.assertIn('href="styles.css"', html)
        self.assertIn('src="app.js"', html)
        self.assertNotIn("https://", html)
        self.assertNotIn("http://", html)
        self.assertIn("[hidden]", css)
        self.assertIn('const SESSION_INDEX = "../sessions/index.json"', javascript)
        self.assertIn("localStorage", javascript)
        self.assertIn("impacto_menos2a2", javascript)
        self.assertIn("resumo-modulos.json", javascript)

    def test_indice_aponta_para_pacotes_compativeis_com_o_painel(self) -> None:
        index = json.loads((SESSIONS / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["schema_indice_avaliacoes"], 1)
        self.assertTrue(index["sessoes"])

        for entry in index["sessoes"]:
            package = SESSIONS / entry["caminho"]
            scorecard = json.loads((package / "scorecard.json").read_text(encoding="utf-8"))
            summary = json.loads((package / "resumo-modulos.json").read_text(encoding="utf-8"))
            with (package / "feedback-jogador.csv").open(encoding="utf-8-sig", newline="") as stream:
                feedback = list(csv.DictReader(stream))

            self.assertEqual(entry["sessao_id"], scorecard["sessao_id"])
            self.assertTrue(summary["modulos"])
            self.assertTrue(any(row["tipo"] == "global" for row in feedback))
            self.assertTrue(any(row["tipo"] == "modulo" for row in feedback))
            self.assertEqual(
                set(feedback[0]),
                {
                    "tipo",
                    "item",
                    "rotulo",
                    "observado",
                    "nota_1a5",
                    "ativacao_menos2a2",
                    "impacto_menos2a2",
                    "comentario",
                },
            )


if __name__ == "__main__":
    unittest.main()
