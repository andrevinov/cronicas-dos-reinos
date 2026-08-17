from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
sys.path.insert(0, str(TOOLS))

import checkpoint
import ciclo_sessoes
import consolidar
import sessoes
import transacoes

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None


class CicloSessoesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self._make_repo()

    def tearDown(self):
        self.temp.cleanup()

    def _yaml(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=110),
            encoding="utf-8",
        )

    def _read_yaml(self, rel: str):
        return yaml.safe_load((self.repo / rel).read_text(encoding="utf-8"))

    def _make_repo(self) -> None:
        (self.repo / "runtime").mkdir(parents=True)
        (self.repo / "sessoes/003").mkdir(parents=True)
        (self.repo / "personagens/jogador/conhecimento").mkdir(parents=True)

        self._yaml(
            "estado/estado-atual.yaml",
            {
                "schema_estado": 1,
                "campanha": {
                    "status": "em_sessao",
                    "sessao_atual": 3,
                    "modo_de_cena_atual": "exploracao",
                },
                "personagem": {
                    "nome": "Ren Kagehira",
                    "arquivo_ficha": "personagens/jogador/ficha.yaml",
                    "nivel": 6,
                    "classe": "Monge",
                    "subclasse": "Caminho da Sombra",
                },
                "localizacao": {
                    "plano": "Material",
                    "mundo": "Toril",
                    "continente": "Faerûn",
                    "regiao": "The Vast",
                    "cidade": "Ravens Bluff",
                    "area": "ponte",
                    "ponto_exato": "margem",
                    "descricao_operacional": "Ren encerra a sessão junto à ponte.",
                },
                "tempo": {
                    "data_exata": "9 Eleasis, 1372 DR",
                    "hora_aproximada": "18:20",
                    "periodo_do_dia": "entardecer",
                    "clima": "úmido",
                },
                "recursos": {
                    "pontos_de_vida": {"atuais": 45, "maximos": 45},
                    "ki": {"atuais": 6, "maximos": 6},
                    "classe_de_armadura": 17,
                    "deslocamento": "55 pés",
                    "dinheiro": {"po": 34},
                },
                "efeitos_temporarios": {},
                "ponteiros": {"transcricao_atual": "sessoes/003/transcricao.md"},
            },
        )
        self._yaml(
            "estado/tempo.yaml",
            {
                "data_atual": "9 Eleasis, 1372 DR",
                "hora_aproximada": "18:20",
                "periodo_do_dia": "entardecer",
                "clima": "úmido",
                "prazo_relevante": "nenhum",
            },
        )
        self._yaml(
            "personagens/jogador/ficha.yaml",
            {
                "personagem": {"nome": "Ren Kagehira"},
                "identidade": {"nivel": 6},
                "combate": {
                    "classe_de_armadura": {"valor": 17},
                    "pontos_de_vida": {"atuais": 45, "maximos": 45},
                },
                "recursos_de_classe": {"ki": {"pontos_atuais": 6, "pontos_maximos": 6}},
                "equipamento": {"dinheiro": {"po": 34}},
            },
        )
        self._yaml(
            "personagens/jogador/conhecimento/ativo.yaml",
            {
                "schema_conhecimento_ativo": 2,
                "natureza": "roteador_derivado",
                "sessao_atual_da_campanha": 3,
                "sessao_mais_recente_indexada": 3,
                "topicos_prioritarios": [],
                "descobertas_recentes": [],
                "incrementais_recentes": [],
            },
        )

        runtime = consolidar._runtime_module()
        context, scene = runtime.build_runtime(self.repo)
        self._yaml("runtime/contexto.yaml", context)
        self._yaml("runtime/cena.yaml", scene)
        (self.repo / "runtime/eventos-pendentes.jsonl").write_text("", encoding="utf-8")
        (self.repo / "sessoes/003/transcricao.md").write_text(
            "# Sessão 003\n\nSEGREDO_TRANSCRICAO_ANTIGA\n",
            encoding="utf-8",
        )
        sessoes.bootstrap_current(self.repo)

    def close(self):
        return checkpoint.checkpoint(self.repo, "sessao")

    def test_checkpoint_sessao_deixa_campanha_entre_sessoes(self):
        result = self.close()
        state = self._read_yaml("estado/estado-atual.yaml")
        runtime = self._read_yaml("runtime/contexto.yaml")
        handoff = self._read_yaml("sessoes/003/handoff.yaml")

        self.assertTrue(result["canonico"]["sem_pendencias"])
        self.assertEqual(state["campanha"]["sessao_atual"], 3)
        self.assertEqual(state["campanha"]["status"], "entre_sessoes")
        self.assertEqual(runtime["sessao"]["numero"], 3)
        self.assertEqual(runtime["sessao"]["status"], "entre_sessoes")
        self.assertEqual(handoff["checkpoint"]["tipo"], "sessao")
        self.assertEqual(handoff["checkpoint"]["estado"], "sessao_encerrada")
        self.assertEqual(sessoes.check(self.repo), [])

    def test_iniciar_cria_n_mais_1_sem_copiar_transcricao(self):
        self.close()
        result = sessoes.start_next(self.repo)

        state = self._read_yaml("estado/estado-atual.yaml")
        runtime = self._read_yaml("runtime/contexto.yaml")
        index = self._read_yaml("sessoes/index.yaml")
        handoff = self._read_yaml("sessoes/004/handoff.yaml")
        active_knowledge = self._read_yaml("personagens/jogador/conhecimento/ativo.yaml")
        transcript = (self.repo / "sessoes/004/transcricao.md").read_text(encoding="utf-8")

        self.assertEqual(result["sessao_iniciada"], 4)
        self.assertEqual(state["campanha"]["sessao_atual"], 4)
        self.assertEqual(state["campanha"]["status"], "em_sessao")
        self.assertEqual(state["ponteiros"]["transcricao_atual"], "sessoes/004/transcricao.md")
        self.assertEqual(runtime["sessao"]["numero"], 4)
        self.assertEqual(runtime["sessao"]["status"], "em_sessao")
        self.assertEqual(handoff["checkpoint"]["tipo"], "bootstrap")
        self.assertEqual(index["sessao_atual"], 4)
        self.assertEqual(index["sessoes"]["003"]["natureza"], "historica")
        self.assertEqual(index["sessoes"]["004"]["natureza"], "atual")
        self.assertEqual(active_knowledge["sessao_atual_da_campanha"], 4)
        self.assertEqual(active_knowledge["sessao_mais_recente_indexada"], 3)
        self.assertIn("# Sessão 004", transcript)
        self.assertNotIn("SEGREDO_TRANSCRICAO_ANTIGA", transcript)
        self.assertEqual((self.repo / "runtime/eventos-pendentes.jsonl").read_text(encoding="utf-8"), "")
        self.assertEqual(sessoes.check(self.repo), [])

    def test_iniciar_sem_encerrar_falha_de_forma_explicita(self):
        with self.assertRaises(ciclo_sessoes.SessionLifecycleError) as ctx:
            sessoes.start_next(self.repo)
        self.assertIn("checkpoint.py sessao", str(ctx.exception))
        self.assertFalse((self.repo / "sessoes/004/transcricao.md").exists())

    def test_segundo_iniciar_nao_pula_outra_sessao(self):
        self.close()
        sessoes.start_next(self.repo)
        with self.assertRaises(ciclo_sessoes.SessionLifecycleError):
            sessoes.start_next(self.repo)
        self.assertFalse((self.repo / "sessoes/005/transcricao.md").exists())

    def test_inicio_interrompido_e_retomado_sem_duplicar_artefatos(self):
        self.close()
        with self.assertRaises(consolidar.ConsolidationError):
            sessoes.start_next(self.repo, fail_after=2)
        self.assertTrue((self.repo / consolidar.JOURNAL_PATH).is_file())

        recovered = sessoes.start_next(self.repo)
        self.assertTrue(recovered["recuperada"])
        self.assertEqual(recovered["sessao_iniciada"], 4)
        self.assertFalse((self.repo / consolidar.JOURNAL_PATH).exists())
        transcript = (self.repo / "sessoes/004/transcricao.md").read_text(encoding="utf-8")
        self.assertEqual(transcript.count("# Sessão 004"), 1)
        self.assertNotIn("SEGREDO_TRANSCRICAO_ANTIGA", transcript)
        self.assertEqual(sessoes.check(self.repo), [])

    def test_recuperar_sem_journal_preserva_handoff_de_encerramento(self):
        self.close()
        before = self._read_yaml("sessoes/003/handoff.yaml")
        self.assertEqual(before["checkpoint"]["tipo"], "sessao")
        result = checkpoint.recover(self.repo)
        after = self._read_yaml("sessoes/003/handoff.yaml")
        self.assertTrue(result["canonico"]["sem_journal"])
        self.assertEqual(after["checkpoint"]["tipo"], "sessao")
        self.assertEqual(after["checkpoint"]["estado"], "sessao_encerrada")

    def test_parser_expoe_iniciar_como_porta_unica(self):
        args = sessoes.build_parser().parse_args(["iniciar"])
        self.assertEqual(args.comando, "iniciar")


if __name__ == "__main__":
    unittest.main()
