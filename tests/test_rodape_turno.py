from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import rodape_turno
import transacoes


class RodapeTurnoSyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "runtime").mkdir(parents=True)
        (self.repo / "sessoes/003").mkdir(parents=True)
        self._write(
            "runtime/contexto.yaml",
            {
                "versao_runtime": 2,
                "sessao": {"numero": 3, "status": "em_sessao", "modo_de_cena": "interação"},
                "recursos": {
                    "pv": {"atuais": 27, "maximos": 39},
                    "focus": {"atuais": 3, "maximos": 6},
                },
                "tempo": {"data": "11 Eleasis, 1372 DR", "hora_aproximada": "14:37"},
                "localizacao": {"area": "cais", "ponto_exato": "navio no cais"},
                "rodape": {
                    "itens_magicos": {
                        "broche_do_semblante_humilde": {
                            "nome": "Broche do Semblante Humilde",
                            "caminho_disponibilidade": "recursos.disponibilidades.broche_do_semblante_humilde",
                            "efeito_temporario": "broche_do_semblante_humilde",
                            "disponibilidade": "disponível",
                        }
                    }
                },
            },
        )
        self._write(
            "runtime/cena.yaml",
            {
                "versao_runtime": 2,
                "sessao": 3,
                "modo": "interação",
                "localizacao": {"area": "cais", "ponto_exato": "navio no cais"},
                "tempo": {"data": "11 Eleasis, 1372 DR", "hora_aproximada": "14:37"},
                "mecanica_imediata": {"pv": "27/39", "focus": "3/6"},
            },
        )
        (self.repo / "runtime/eventos-pendentes.jsonl").write_text("", encoding="utf-8")
        (self.repo / "sessoes/003/transcricao.md").write_text("# Sessão 003\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _append_pending(self, record: dict) -> None:
        with (self.repo / "runtime/eventos-pendentes.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def test_formato_basico_e_item_disponivel(self):
        footer = rodape_turno.build(self.repo)
        self.assertEqual(
            footer,
            "RODAPE_CANONICO — 11 de Eleasis · 14:37 · navio no cais · PV 27/39 · Focus 3/6 · "
            "Broche do Semblante Humilde disponível",
        )
        self.assertLess(len(footer), 240)

    def test_deltas_pendentes_entram_no_mesmo_rodape_sem_escrita_extra(self):
        record = transacoes.build_pending_record(
            {
                "id": "turno-footer",
                "narracao": "estado muda",
                "resumo": "estado muda",
                "deltas": [
                    {"alvo": "estado", "op": "inc", "caminho": "recursos.pontos_de_vida.atuais", "valor": -5},
                    {"alvo": "estado", "op": "inc", "caminho": "recursos.focus.atuais", "valor": -2},
                    {
                        "alvo": "tempo",
                        "op": "instante",
                        "valor": {"data": "11 Eleasis, 1372 DR", "hora": "14:42"},
                    },
                    {"alvo": "estado", "op": "set", "caminho": "localizacao.ponto_exato", "valor": "convés do navio"},
                    {
                        "alvo": "estado",
                        "op": "set",
                        "caminho": "recursos.disponibilidades.broche_do_semblante_humilde",
                        "valor": "usado; indisponível até o próximo amanhecer",
                    },
                ],
            },
            3,
        )
        self._append_pending(record)
        before = (self.repo / "runtime/contexto.yaml").read_bytes()
        footer = rodape_turno.build(self.repo)
        self.assertIn("14:42", footer)
        self.assertIn("convés do navio", footer)
        self.assertIn("PV 22/39", footer)
        self.assertIn("Focus 1/6", footer)
        self.assertNotIn("Broche do Semblante Humilde", footer)
        self.assertEqual(before, (self.repo / "runtime/contexto.yaml").read_bytes())

    def test_efeito_ativo_aparece_mesmo_quando_item_ja_foi_gasto(self):
        context = yaml.safe_load((self.repo / "runtime/contexto.yaml").read_text(encoding="utf-8"))
        context["rodape"]["itens_magicos"]["broche_do_semblante_humilde"]["disponibilidade"] = (
            "indisponível até amanhã"
        )
        context["efeitos_temporarios"] = {
            "broche_do_semblante_humilde": {"duracao": "até 15:37"}
        }
        self._write("runtime/contexto.yaml", context)
        footer = rodape_turno.build(self.repo)
        self.assertIn("Broche do Semblante Humilde ativo", footer)
        self.assertNotIn("Broche do Semblante Humilde disponível", footer)

    def test_build_safe_nao_transforma_erro_de_exibicao_em_falha_do_turno(self):
        (self.repo / "runtime/contexto.yaml").unlink()
        footer = rodape_turno.build_safe(self.repo)
        self.assertTrue(footer.startswith("RODAPE_CANONICO — indisponível ("))

    def test_cli_turno_emite_rodape_como_ultima_linha(self):
        transaction = {
            "jogador": "Ren observa o cais.",
            "narracao": "Ren permanece atento ao movimento do convés.",
            "resumo": "Ren observa o cais.",
            "modo": "interação",
            "deltas": [],
        }
        process = subprocess.run(
            [sys.executable, str(TOOLS / "turno.py"), "--repo", str(self.repo), "registrar"],
            input=json.dumps(transaction, ensure_ascii=False),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr or process.stdout)
        lines = [line for line in process.stdout.splitlines() if line.strip()]
        self.assertTrue(lines[-1].startswith("RODAPE_CANONICO — "), process.stdout)
        self.assertIn("11 de Eleasis · 14:37 · navio no cais · PV 27/39 · Focus 3/6", lines[-1])


class RodapeTurnoRepositoryTest(unittest.TestCase):
    def test_runtime_real_expoe_registro_magico_sem_scan_de_inventario(self):
        context = yaml.safe_load((ROOT / "runtime/contexto.yaml").read_text(encoding="utf-8"))
        items = ((context.get("rodape") or {}).get("itens_magicos") or {})
        self.assertEqual(set(items), {"broche_do_semblante_humilde"})
        self.assertNotIn("disponibilidades", context.get("recursos") or {})
        self.assertIn("disponibilidade", items["broche_do_semblante_humilde"])

    def test_rodape_real_e_compacto(self):
        context, _ = rodape_turno.effective_runtime(ROOT)
        footer = rodape_turno.build(ROOT)
        raw_date = context["tempo"]["data"].split(",", 1)[0]
        day, month = raw_date.split(maxsplit=1)
        expected_clock = context["tempo"]["hora_aproximada"]
        pv = context["recursos"]["pv"]
        focus = context["recursos"]["focus"]
        self.assertTrue(footer.startswith("RODAPE_CANONICO — "))
        self.assertIn(f"{day} de {month} · {expected_clock} · ", footer)
        self.assertIn(
            f"PV {pv['atuais']}/{pv['maximos']} · Focus {focus['atuais']}/{focus['maximos']}",
            footer,
        )
        item = context["rodape"]["itens_magicos"]["broche_do_semblante_humilde"]
        effects = context.get("efeitos_temporarios") or {}
        if "broche_do_semblante_humilde" in effects:
            self.assertIn("Broche do Semblante Humilde ativo", footer)
        elif rodape_turno._available(item.get("disponibilidade")):
            self.assertIn("Broche do Semblante Humilde disponível", footer)
        else:
            self.assertNotIn("Broche do Semblante Humilde", footer)
        self.assertLess(len(footer.encode("utf-8")), 512)


if __name__ == "__main__":
    unittest.main()
