from __future__ import annotations

import argparse
import copy
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import checkpoint
import ciclo_cronica
import ciclo_sessoes
import consolidar
import cronica
import progressao_juppongatana
import sessoes


def write_yaml(repo: Path, rel: str | Path, value) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=110),
        encoding="utf-8",
    )


def read_yaml(repo: Path, rel: str | Path):
    return yaml.safe_load((repo / rel).read_text(encoding="utf-8"))


def tree_bytes(repo: Path) -> dict[str, bytes]:
    return {
        path.relative_to(repo).as_posix(): path.read_bytes()
        for path in sorted(repo.rglob("*"))
        if path.is_file()
        and path.relative_to(repo).as_posix()
        not in {
            consolidar.JOURNAL_PATH.as_posix(),
        }
        and not path.relative_to(repo).as_posix().startswith(
            consolidar.STAGE_DIR.as_posix() + "/"
        )
    }


def make_session_repo(repo: Path) -> None:
    (repo / "runtime").mkdir(parents=True, exist_ok=True)
    (repo / "sessoes/003").mkdir(parents=True, exist_ok=True)
    (repo / "personagens/jogador/conhecimento").mkdir(parents=True, exist_ok=True)

    write_yaml(
        repo,
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
                "nivel": 7,
                "classe": "Monge",
                "subclasse": "Guerreiro das Sombras",
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
                "pontos_de_vida": {"atuais": 52, "maximos": 52},
                "focus": {"atuais": 7, "maximos": 7},
                "classe_de_armadura": 17,
                "deslocamento": "55 pés",
                "dinheiro": {"po": 34},
            },
            "efeitos_temporarios": {},
            "ponteiros": {"transcricao_atual": "sessoes/003/transcricao.md"},
        },
    )
    write_yaml(
        repo,
        "estado/tempo.yaml",
        {
            "data_atual": "9 Eleasis, 1372 DR",
            "hora_aproximada": "18:20",
            "periodo_do_dia": "entardecer",
            "clima": "úmido",
            "prazo_relevante": "nenhum",
        },
    )
    write_yaml(
        repo,
        "personagens/jogador/ficha.yaml",
        {
            "personagem": {"nome": "Ren Kagehira"},
            "identidade": {"nivel": 7, "classe": "Monge", "subclasse": "Guerreiro das Sombras"},
            "combate": {
                "classe_de_armadura": {"valor": 17},
                "pontos_de_vida": {"atuais": 52, "maximos": 52, "dados_de_vida": "7d8"},
            },
            "recursos_de_classe": {"focus": {"pontos_atuais": 7, "pontos_maximos": 7}},
            "equipamento": {"dinheiro": {"po": 34}},
            "progressao": {"metodo": "marcos narrativos"},
        },
    )
    (repo / "personagens/jogador/resumo-de-poderes.md").write_text(
        "# Resumo de poderes de Ren\n\nRen é um monge do Guerreiro das Sombras, nível 7.\n",
        encoding="utf-8",
    )
    write_yaml(
        repo,
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
    context, scene = runtime.build_runtime(repo)
    write_yaml(repo, "runtime/contexto.yaml", context)
    write_yaml(repo, "runtime/cena.yaml", scene)
    (repo / "runtime/eventos-pendentes.jsonl").write_text("", encoding="utf-8")
    (repo / "sessoes/003/transcricao.md").write_text(
        "# Sessão 003\n\nSEGREDO_TRANSCRICAO_ANTIGA\n",
        encoding="utf-8",
    )
    (repo / "sessoes/003/consolidacoes.jsonl").write_text("", encoding="utf-8")
    sessoes.bootstrap_current(repo)


def add_task19(repo: Path, *, with_milestone: bool = True, prep: str = "a" * 24) -> None:
    policy = repo / progressao_juppongatana.POLICY
    policy.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / progressao_juppongatana.POLICY, policy)
    roster = repo / progressao_juppongatana.ROSTER
    shutil.copy2(ROOT / progressao_juppongatana.ROSTER, roster)
    entries = []
    if with_milestone:
        entries.append(
            {
                "ordem": 1,
                "membro": "pan_chu",
                "tipo": "expulsao_ou_exilio_operacional",
                "fonte": "estado/estado-atual.yaml",
                "evidencia": "Ren encerra a sessão junto à ponte.",
                "nivel_desbloqueado": 8,
                "preparacao_id": prep,
                "sessao": 3,
            }
        )
    write_yaml(
        repo,
        progressao_juppongatana.STATE,
        {
            "schema_estado_progressao_juppongatana": 1,
            "natureza": "estado_reservado",
            "base_nivel": 7,
            "retroatividade_aplicada": False,
            "neutralizacoes": entries,
        },
    )


def progression_plan(prep: str = "a" * 24) -> dict:
    return {
        "schema_progressao_mecanica": 1,
        "nivel_novo": 8,
        "milestone_preparacao_id": prep,
        "alteracoes_ficha": [
            {"caminho": "combate.pontos_de_vida.maximos", "valor": 59},
            {"caminho": "combate.pontos_de_vida.atuais", "valor": 59},
            {"caminho": "combate.pontos_de_vida.dados_de_vida", "valor": "8d8"},
            {"caminho": "recursos_de_classe.focus.pontos_maximos", "valor": 8},
            {"caminho": "recursos_de_classe.focus.pontos_atuais", "valor": 8},
            {
                "caminho": "aumentos_de_atributo.nivel_8",
                "valor": {"escolha": "+2 Sabedoria", "motivo": "plano de teste"},
            },
        ],
        "resumo_de_poderes": (
            "# Resumo de poderes de Ren\n\n"
            "Ren é um monge do Guerreiro das Sombras, nível 8.\n\n"
            "Este texto representa o resumo mecânico completo aprovado para o novo nível.\n"
        ),
        "marco": "Primeiro Juppongatana neutralizado de forma durável.",
        "motivo": "O milestone registrado desbloqueou o nível 8.",
        "escolhas_pendentes": [],
    }


class UnifiedSessionEquivalenceTest(unittest.TestCase):
    def make_pair(self):
        left = tempfile.TemporaryDirectory()
        right = tempfile.TemporaryDirectory()
        legacy = Path(left.name)
        unified = Path(right.name)
        make_session_repo(legacy)
        make_session_repo(unified)
        self.addCleanup(left.cleanup)
        self.addCleanup(right.cleanup)
        return legacy, unified

    def test_encerrar_produz_exatamente_os_mesmos_bytes_do_fluxo_legado(self):
        legacy, unified = self.make_pair()
        expected = checkpoint.checkpoint(legacy, "sessao")
        actual = ciclo_cronica.session_close(unified)
        self.assertEqual(tree_bytes(unified), tree_bytes(legacy))
        self.assertEqual(expected["memoria"]["handoff"], actual["memoria"]["handoff"])
        self.assertEqual(read_yaml(unified, "estado/estado-atual.yaml")["campanha"]["status"], "entre_sessoes")

    def test_fechar_e_abrir_produzem_exatamente_os_mesmos_bytes_e_nao_copiam_transcricao(self):
        legacy, unified = self.make_pair()
        checkpoint.checkpoint(legacy, "sessao")
        ciclo_cronica.session_close(unified)
        sessoes.start_next(legacy)
        ciclo_cronica.session_start(unified)
        self.assertEqual(tree_bytes(unified), tree_bytes(legacy))
        transcript = (unified / "sessoes/004/transcricao.md").read_text(encoding="utf-8")
        self.assertEqual(transcript, "# Sessão 004\n\n---\n")
        self.assertNotIn("SEGREDO_TRANSCRICAO_ANTIGA", transcript)

    def test_checkpoint_delega_a_mesma_autoridade_sem_implementar_segundo_motor(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name)
        fake = {
            "canonico": {"sessao": 3, "tipo": "cena", "sem_pendencias": True},
            "ciclo": None,
            "mundo": {"configurado": False},
            "memoria": {"sessao": 3, "tipo": "cena", "handoff": "x", "indice": "y"},
        }
        with (
            mock.patch.object(ciclo_cronica.checkpoint, "checkpoint", return_value=fake) as call,
            mock.patch.object(ciclo_cronica, "_assert_resumable"),
        ):
            result = ciclo_cronica.session_checkpoint(repo)
        call.assert_called_once_with(repo, "cena")
        self.assertEqual(result["fase"], "checkpoint")

    def test_inicio_interrompido_continua_recuperavel_pelo_mesmo_journal(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name)
        make_session_repo(repo)
        ciclo_cronica.session_close(repo)
        with self.assertRaises(consolidar.ConsolidationError):
            ciclo_cronica.session_start(repo, fail_after=2)
        self.assertTrue((repo / consolidar.JOURNAL_PATH).is_file())
        recovered = ciclo_cronica.session_recover(repo)
        self.assertEqual(recovered["fase"], "recuperada")
        self.assertFalse((repo / consolidar.JOURNAL_PATH).exists())
        self.assertEqual(read_yaml(repo, "estado/estado-atual.yaml")["campanha"]["sessao_atual"], 4)
        transcript = (repo / "sessoes/004/transcricao.md").read_text(encoding="utf-8")
        self.assertEqual(transcript.count("# Sessão 004"), 1)
        self.assertNotIn("SEGREDO_TRANSCRICAO_ANTIGA", transcript)


class UnifiedProgressionTest(unittest.TestCase):
    def make_repo(self, *, milestone: bool = True, prep: str = "a" * 24) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name)
        make_session_repo(repo)
        checkpoint.checkpoint(repo, "sessao")
        add_task19(repo, with_milestone=milestone, prep=prep)
        return repo

    def test_sem_milestone_level_up_falha_antes_de_qualquer_escrita(self):
        repo = self.make_repo(milestone=False)
        before = tree_bytes(repo)
        with self.assertRaisesRegex(ciclo_cronica.UnifiedSessionError, "milestone"):
            ciclo_cronica.apply_progression(repo, progression_plan())
        self.assertEqual(tree_bytes(repo), before)
        self.assertFalse((repo / consolidar.JOURNAL_PATH).exists())

    def test_preparacao_id_errado_nao_pode_alterar_ficha(self):
        repo = self.make_repo(prep="b" * 24)
        before_sheet = (repo / "personagens/jogador/ficha.yaml").read_bytes()
        with self.assertRaisesRegex(ciclo_cronica.UnifiedSessionError, "milestone_preparacao_id"):
            ciclo_cronica.apply_progression(repo, progression_plan(prep="a" * 24))
        self.assertEqual((repo / "personagens/jogador/ficha.yaml").read_bytes(), before_sheet)

    def test_plano_nao_pode_controlar_identidade_nivel(self):
        plan = progression_plan()
        plan["alteracoes_ficha"].append({"caminho": "identidade.nivel", "valor": 99})
        with self.assertRaisesRegex(ciclo_cronica.UnifiedSessionError, "controlado pelo lifecycle"):
            ciclo_cronica.validate_progression_plan(plan)

    def test_level_up_instala_ficha_espelhos_resumo_experiencia_e_derivados_em_um_journal(self):
        repo = self.make_repo()
        result = ciclo_cronica.apply_progression(repo, progression_plan())
        self.assertEqual(result["nivel_anterior"], 7)
        self.assertEqual(result["nivel_novo"], 8)
        self.assertFalse(result["ja_aplicada"])
        sheet = read_yaml(repo, "personagens/jogador/ficha.yaml")
        state = read_yaml(repo, "estado/estado-atual.yaml")
        runtime = read_yaml(repo, "runtime/contexto.yaml")
        self.assertEqual(sheet["identidade"]["nivel"], 8)
        self.assertEqual(state["personagem"]["nivel"], 8)
        self.assertEqual(sheet["combate"]["pontos_de_vida"]["maximos"], 59)
        self.assertEqual(state["recursos"]["pontos_de_vida"]["maximos"], 59)
        self.assertEqual(sheet["recursos_de_classe"]["focus"]["pontos_maximos"], 8)
        self.assertEqual(state["recursos"]["focus"]["maximos"], 8)
        self.assertEqual(runtime["personagem"]["nivel"], 8)
        self.assertEqual(
            (repo / "personagens/jogador/resumo-de-poderes.md").read_text(encoding="utf-8"),
            progression_plan()["resumo_de_poderes"],
        )
        experience = (repo / "sessoes/003/experiencia.md").read_text(encoding="utf-8")
        self.assertIn("Novo nível: 8", experience)
        self.assertIn("Pan Chu", experience)
        self.assertIn("cronica-progressao:", experience)
        handoff = read_yaml(repo, "sessoes/003/handoff.yaml")
        index = read_yaml(repo, "sessoes/index.yaml")
        self.assertEqual(handoff["checkpoint"]["personagem"]["nivel"], 8)
        self.assertEqual(index["sessao_atual"], 3)
        self.assertFalse((repo / consolidar.JOURNAL_PATH).exists())

    def test_level_up_e_idempotente_com_o_mesmo_plano(self):
        repo = self.make_repo()
        first = ciclo_cronica.apply_progression(repo, progression_plan())
        before = tree_bytes(repo)
        second = ciclo_cronica.apply_progression(repo, progression_plan())
        self.assertFalse(first["ja_aplicada"])
        self.assertTrue(second["ja_aplicada"])
        self.assertEqual(tree_bytes(repo), before)

    def test_falha_intermediaria_do_level_up_e_recuperada_pelo_checkpoint_legado(self):
        clean = self.make_repo()
        interrupted = self.make_repo()
        ciclo_cronica.apply_progression(clean, progression_plan())
        with self.assertRaises(consolidar.ConsolidationError):
            ciclo_cronica.apply_progression(interrupted, progression_plan(), fail_after=2)
        self.assertTrue((interrupted / consolidar.JOURNAL_PATH).is_file())
        checkpoint.recover(interrupted)
        self.assertFalse((interrupted / consolidar.JOURNAL_PATH).exists())
        self.assertEqual(tree_bytes(interrupted), tree_bytes(clean))

    def test_progressao_so_e_aplicada_entre_sessoes(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name)
        make_session_repo(repo)
        add_task19(repo)
        with self.assertRaisesRegex(ciclo_cronica.UnifiedSessionError, "entre_sessoes"):
            ciclo_cronica.apply_progression(repo, progression_plan())


class UnifiedLifecycleParserBudgetTest(unittest.TestCase):
    def test_parser_publico_preserva_task21_e_adiciona_sessao_e_progressao(self):
        parser = cronica.build_parser()
        root = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        self.assertEqual(
            set(root.choices),
            {"preparar", "concluir", "registrar", "confirmar", "sessao", "progressao"},
        )
        legacy = cronica._ORIGINAL_BUILD_PARSER()
        legacy_root = next(
            action
            for action in legacy._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        self.assertEqual(
            set(legacy_root.choices),
            {"preparar", "concluir", "registrar", "confirmar"},
        )
        session_root = next(
            action
            for action in root.choices["sessao"]._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        self.assertEqual(
            set(session_root.choices),
            {"status", "checkpoint", "encerrar", "iniciar", "recuperar"},
        )

    def test_orcamento_bate_com_codigo(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/unified-session-lifecycle-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        limits = contract["limites"]
        self.assertEqual(limits["max_alteracoes_ficha"], ciclo_cronica.MAX_SHEET_CHANGES)
        self.assertEqual(limits["max_plano_progressao_bytes"], ciclo_cronica.MAX_PROGRESSION_PLAN_BYTES)
        self.assertEqual(limits["max_resumo_poderes_bytes"], ciclo_cronica.MAX_POWERS_BYTES)
        self.assertEqual(limits["max_escolhas_pendentes"], ciclo_cronica.MAX_PENDING_CHOICES)
        self.assertEqual(limits["max_outputs_progressao"], 8)
        self.assertTrue(contract["invariantes"]["recovery_reutiliza_journal_existente"])
        self.assertTrue(contract["meta_rollout"]["proibido_inventar_reducao_sem_rollout_real"])


if __name__ == "__main__":
    unittest.main()
