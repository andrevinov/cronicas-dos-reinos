from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
sys.path.insert(0, str(TOOLS))

import contexto
import sessoes

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


class MemoriaSessoesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        (self.repo / "runtime").mkdir(parents=True)
        (self.repo / "sessoes/001").mkdir(parents=True)
        (self.repo / "sessoes/003").mkdir(parents=True)
        self._write_yaml(
            "runtime/contexto.yaml",
            {
                "versao_runtime": 1,
                "sessao": {"numero": 3, "status": "em_sessao", "modo_de_cena": "exploracao"},
                "personagem": {"nome": "Ren", "nivel": 6},
                "recursos": {"pv": {"atuais": 40, "maximos": 45}, "ki": {"atuais": 4, "maximos": 6}, "ca": 17},
                "tempo": {"data": "7 Eleasis", "hora_aproximada": "08:10"},
                "localizacao": {"cidade": "Ravens Bluff", "area": "ponte", "ponto_exato": "margem"},
            },
        )
        self._write_yaml(
            "runtime/cena.yaml",
            {
                "versao_runtime": 1,
                "sessao": 3,
                "modo": "exploracao",
                "localizacao": {"area": "ponte", "ponto_exato": "margem"},
                "tempo": {"data": "7 Eleasis", "hora_aproximada": "08:10"},
                "mecanica_imediata": {"pv": "40/45", "ki": "4/6", "ca": 17},
                "resumo_imediato": "Ren alcançou a ponte e precisa decidir se atravessa.",
                "prazos_e_alertas": "Uma patrulha pode chegar em breve.",
            },
        )
        (self.repo / "runtime/eventos-pendentes.jsonl").write_text("", encoding="utf-8")
        (self.repo / "sessoes/001/transcricao.md").write_text(
            "# Sessão 001\n\nA agulha violeta está escondida sob a pedra.\n",
            encoding="utf-8",
        )
        (self.repo / "sessoes/001/resumo.md").write_text(
            "# Resumo\n\nRen investigou o cais sem descobrir o objeto secreto.\n",
            encoding="utf-8",
        )
        (self.repo / "sessoes/003/transcricao.md").write_text("# Sessão 003\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def _write_yaml(self, rel: str, value):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=110),
            encoding="utf-8",
        )

    def test_bootstrap_cria_handoff_pequeno_sem_prosa_de_transcricao(self):
        path, handoff = sessoes.bootstrap_current(self.repo)
        self.assertTrue(path.is_file())
        raw = path.read_text(encoding="utf-8")
        self.assertLessEqual(len(raw.encode("utf-8")), sessoes.MAX_HANDOFF_BYTES)
        self.assertNotIn("**Jogador**", raw)
        self.assertNotIn("**Narrador**", raw)
        self.assertEqual(handoff["sessao"], 3)
        self.assertIn("ponte", handoff["continuidade"]["resumo_imediato"])
        self.assertEqual(sessoes.check(self.repo), [])

    def test_snapshot_historico_nao_abre_transcricao_quando_handoff_ausente(self):
        sessoes.write_index(self.repo)
        result, sources = sessoes.session_snapshot(self.repo, 1)
        serialized = yaml.safe_dump(result, allow_unicode=True)
        self.assertTrue(result["encontrado"])
        self.assertFalse(result["transcricao_lida"])
        self.assertIn("Resumo", serialized)
        self.assertNotIn("agulha violeta", serialized.lower())
        self.assertNotIn("sessoes/001/transcricao.md", sources)

    def test_busca_historica_so_le_transcricao_com_escalada_explicita(self):
        without = contexto.generic_search(
            self.repo,
            "agulha violeta",
            reserved=False,
            historical=True,
            transcripts=False,
        )
        self.assertEqual(without, [])

        with_transcript = contexto.generic_search(
            self.repo,
            "agulha violeta",
            reserved=False,
            historical=True,
            transcripts=True,
        )
        self.assertTrue(with_transcript)
        self.assertEqual(with_transcript[0]["arquivo"], "sessoes/001/transcricao.md")

    def test_copia_de_sessao_anterior_fica_proibida_para_sessoes_novas(self):
        (self.repo / "sessoes/004").mkdir(parents=True)
        (self.repo / "sessoes/004/transcricao.md").write_text(
            "# Sessão 004\n\n## Último trecho da Sessão 003\n\ntexto copiado\n",
            encoding="utf-8",
        )
        runtime = yaml.safe_load((self.repo / "runtime/contexto.yaml").read_text(encoding="utf-8"))
        runtime["sessao"]["numero"] = 4
        self._write_yaml("runtime/contexto.yaml", runtime)
        scene = yaml.safe_load((self.repo / "runtime/cena.yaml").read_text(encoding="utf-8"))
        scene["sessao"] = 4
        self._write_yaml("runtime/cena.yaml", scene)
        sessoes.write_index(self.repo)
        errors = sessoes.check(self.repo)
        self.assertTrue(any("copia trecho de sessão anterior" in error for error in errors))

    def test_marcador_legado_na_sessao_003_e_tolerado(self):
        (self.repo / "sessoes/003/transcricao.md").write_text(
            "# Sessão 003\n\n## Último trecho da Sessão 002\n\nlegado\n",
            encoding="utf-8",
        )
        sessoes.bootstrap_current(self.repo)
        self.assertEqual(sessoes.check(self.repo), [])


if __name__ == "__main__":
    unittest.main()
