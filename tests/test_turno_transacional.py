from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
sys.path.insert(0, str(TOOLS))
MODULE_PATH = TOOLS / "turno.py"
spec = importlib.util.spec_from_file_location("turno", MODULE_PATH)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

import transacoes


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TurnoTransactionalTest(unittest.TestCase):
    def make_repo(self) -> Path:
        self.temp = tempfile.TemporaryDirectory()
        repo = Path(self.temp.name)
        (repo / "runtime").mkdir(parents=True)
        (repo / "sessoes/003").mkdir(parents=True)
        (repo / "estado").mkdir(parents=True)
        (repo / "personagens/jogador").mkdir(parents=True)
        (repo / "runtime/contexto.yaml").write_text(
            "sessao:\n  numero: 3\n", encoding="utf-8"
        )
        (repo / "runtime/eventos-pendentes.jsonl").write_text("", encoding="utf-8")
        (repo / "sessoes/003/transcricao.md").write_text(
            "# Sessão 003\n\n---\n", encoding="utf-8"
        )
        (repo / "estado/estado-atual.yaml").write_text("sentinela: estado\n", encoding="utf-8")
        (repo / "estado/tempo.yaml").write_text("sentinela: tempo\n", encoding="utf-8")
        (repo / "personagens/jogador/ficha.yaml").write_text("sentinela: ficha\n", encoding="utf-8")
        return repo

    def tearDown(self):
        if hasattr(self, "temp"):
            self.temp.cleanup()

    def transaction(self, *, mode="combate", delta=None):
        return {
            "jogador": "Ren avança sobre o homem de mãos limpas.",
            "narracao": "Ren fecha a distância. O homem recua um passo e mantém a faca alta.",
            "resumo": "Ren mantém o homem de mãos limpas sob pressão.",
            "modo": mode,
            "deltas": delta or [],
        }

    def test_common_turn_changes_only_transcript_and_pending_buffer(self):
        repo = self.make_repo()
        protected = [
            repo / "estado/estado-atual.yaml",
            repo / "estado/tempo.yaml",
            repo / "personagens/jogador/ficha.yaml",
        ]
        before = {path: sha(path) for path in protected}
        result = mod.register_transaction(
            repo,
            self.transaction(
                delta=[
                    {"alvo": "estado", "op": "inc", "caminho": "recursos.ki.atuais", "valor": -1},
                    {"alvo": "tempo", "op": "set", "caminho": "hora_aproximada", "valor": "08:04"},
                ]
            ),
        )
        self.assertTrue(result["transcricao_escrita"])
        self.assertTrue(result["evento_escrito"])
        for path in protected:
            self.assertEqual(before[path], sha(path), f"arquivo canônico foi alterado: {path}")
        self.assertIn("**Jogador**", (repo / "sessoes/003/transcricao.md").read_text(encoding="utf-8"))
        self.assertEqual(len(transacoes.load_pending(repo)), 1)

    def test_rerun_is_idempotent(self):
        repo = self.make_repo()
        tx = self.transaction()
        first = mod.register_transaction(repo, tx)
        transcript_after_first = (repo / "sessoes/003/transcricao.md").read_text(encoding="utf-8")
        pending_after_first = (repo / "runtime/eventos-pendentes.jsonl").read_text(encoding="utf-8")
        second = mod.register_transaction(repo, tx)
        self.assertTrue(second["ja_registrada"])
        self.assertEqual(transcript_after_first, (repo / "sessoes/003/transcricao.md").read_text(encoding="utf-8"))
        self.assertEqual(pending_after_first, (repo / "runtime/eventos-pendentes.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(first["id"], second["id"])

    def test_interruption_after_event_write_is_repaired(self):
        repo = self.make_repo()
        tx, session = mod.normalize_transaction(repo, self.transaction())
        record = transacoes.build_pending_record(tx, session)
        (repo / "runtime/eventos-pendentes.jsonl").write_text(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        result = mod.register_transaction(repo, tx)
        self.assertTrue(result["reparo_parcial"])
        self.assertTrue(result["transcricao_escrita"])
        self.assertFalse(result["evento_escrito"])
        self.assertEqual(len(transacoes.load_pending(repo)), 1)
        self.assertEqual(
            (repo / "sessoes/003/transcricao.md").read_text(encoding="utf-8").count(transacoes.transaction_marker(result["id"])),
            1,
        )

    def test_interruption_after_transcript_write_is_repaired(self):
        repo = self.make_repo()
        tx, _ = mod.normalize_transaction(repo, self.transaction())
        transcript = (repo / "sessoes/003/transcricao.md").read_text(encoding="utf-8")
        (repo / "sessoes/003/transcricao.md").write_text(
            mod._append_block(transcript, mod.render_transcript_block(tx)), encoding="utf-8"
        )
        result = mod.register_transaction(repo, tx)
        self.assertTrue(result["reparo_parcial"])
        self.assertFalse(result["transcricao_escrita"])
        self.assertTrue(result["evento_escrito"])
        self.assertEqual(len(transacoes.load_pending(repo)), 1)

    def test_modes_cover_interaction_exploration_combat_rest_and_discovery(self):
        repo = self.make_repo()
        cases = [
            (
                "interação",
                [{"alvo": "relacao:luath", "op": "set", "caminho": "confianca", "valor": "moderada"}],
            ),
            (
                "exploração",
                [{"alvo": "estado", "op": "set", "caminho": "localizacao.ponto_exato", "valor": "galpão"}],
            ),
            (
                "combate",
                [{"alvo": "estado", "op": "inc", "caminho": "recursos.pontos_de_vida.atuais", "valor": -4}],
            ),
            (
                "descanso",
                [{"alvo": "estado", "op": "set", "caminho": "recursos.ki.atuais", "valor": 6}],
            ),
            (
                "descoberta",
                [{"alvo": "conhecimento", "op": "registrar", "valor": {"assunto": "ponte", "texto": "nova pista"}}],
            ),
        ]
        for index, (mode, deltas) in enumerate(cases):
            tx = {
                "id": f"modo-{index}",
                "jogador": f"ação {index}",
                "narracao": f"resultado {index}",
                "resumo": f"resumo {index}",
                "modo": mode,
                "deltas": deltas,
            }
            mod.register_transaction(repo, tx)
        records = transacoes.load_pending(repo)
        self.assertEqual(len(records), 5)
        self.assertEqual({record.get("modo") for record in records}, {item[0] for item in cases})
        self.assertEqual(mod.check_transactions(repo), [])

    def test_resume_uses_pending_overlay_without_canonical_write(self):
        repo = self.make_repo()
        mod.register_transaction(
            repo,
            self.transaction(
                delta=[
                    {"alvo": "estado", "op": "inc", "caminho": "recursos.ki.atuais", "valor": -2},
                    {"alvo": "estado", "op": "set", "caminho": "localizacao.ponto_exato", "valor": "junto ao salgueiro"},
                ]
            ),
        )
        base_context = {
            "sessao": {"numero": 3},
            "recursos": {"ki": {"atuais": 5, "maximos": 6}, "pv": {"atuais": 45, "maximos": 45}},
            "localizacao": {"ponto_exato": "estrada"},
        }
        effective, _, _ = transacoes.overlay_runtime(base_context, None, transacoes.load_pending(repo))
        self.assertEqual(effective["recursos"]["ki"]["atuais"], 3)
        self.assertEqual(effective["localizacao"]["ponto_exato"], "junto ao salgueiro")


if __name__ == "__main__":
    unittest.main()
