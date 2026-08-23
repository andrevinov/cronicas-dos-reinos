from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import progressao_juppongatana as progression


class JuppongatanaMilestoneRepositoryTest(unittest.TestCase):
    def test_repo_real_comeca_em_zero_de_dez_no_nivel_sete(self):
        result = progression.validate_repo(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["membros"], 10)
        self.assertEqual(result["neutralizacoes"], 0)
        self.assertEqual(result["niveis_pendentes"], 0)

        status = progression.status(ROOT)
        self.assertEqual(status["nivel_ficha"], 7)
        self.assertEqual(status["neutralizacoes_duraveis"], 0)
        self.assertEqual(status["nivel_desbloqueado_por_marcos"], 7)
        self.assertEqual(status["proximo_nivel"], 8)
        self.assertEqual(len(status["restantes"]), 10)
        self.assertEqual(
            status["fontes_lidas"],
            [
                "narrador/juppongatana/progressao.yaml",
                "narrador/juppongatana/estado-progressao.yaml",
                "personagens/jogador/ficha.yaml",
            ],
        )

    def test_politica_tem_exatamente_os_dez_membros_sem_masao(self):
        policy = progression.load_policy(ROOT)
        self.assertEqual(set(policy["membros"]), set(progression.EXPECTED_MEMBERS))
        self.assertNotIn("masao_hirasawa", policy["membros"])
        self.assertEqual(policy["faixa_niveis"], list(range(8, 18)))
        self.assertEqual(policy["ordem_dos_membros"], "livre")

    def test_estado_inicial_nao_da_credito_retroativo_a_kurobane(self):
        state = progression.load_state(ROOT)
        self.assertFalse(state["retroatividade_aplicada"])
        self.assertEqual(state["neutralizacoes"], [])
        policy = progression.load_policy(ROOT)
        self.assertTrue(policy["regras"]["kurobane_frustrado_antes_da_task_nao_conta"])


class JuppongatanaMilestoneSyntheticTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        for rel in (progression.POLICY, progression.STATE, progression.SHEET, progression.AGENTS):
            target = self.repo / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / rel, target)
        self.source = self.repo / "sessoes/999/resumo.md"
        self.source.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"milestone confirmado para {member}: neutralização durável estabelecida no cânone."
            for member in progression.EXPECTED_MEMBERS
        ]
        self.source.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def evidence(self, member: str) -> str:
        return f"milestone confirmado para {member}: neutralização durável estabelecida no cânone."

    def prepare(self, member: str, kind: str = "prisao_ou_confinamento_estavel"):
        return progression.prepare(
            self.repo,
            member,
            kind,
            "sessoes/999/resumo.md",
            self.evidence(member),
            session=999,
        )

    def confirm(self, member: str, kind: str = "prisao_ou_confinamento_estavel"):
        preview = self.prepare(member, kind)
        return progression.confirm(
            self.repo,
            preview["preparacao_id"],
            member,
            kind,
            "sessoes/999/resumo.md",
            self.evidence(member),
            session=999,
        )

    def set_level(self, level: int):
        path = self.repo / progression.SHEET
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["identidade"]["nivel"] = level
        path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def test_primeiro_membro_qualquer_desbloqueia_nivel_oito(self):
        preview = self.prepare("fuji", "ruptura_definitiva_com_masao")
        self.assertEqual(preview["fase"], "preparacao")
        self.assertEqual(preview["milestone"]["ordem"], 1)
        self.assertEqual(preview["nivel_desbloqueado"], 8)
        self.assertFalse(preview["mutacoes_aplicadas"])
        self.assertEqual(
            preview["fontes_lidas"],
            [
                progression.POLICY.as_posix(),
                progression.STATE.as_posix(),
                progression.SHEET.as_posix(),
                "sessoes/999/resumo.md",
            ],
        )

    def test_prepare_e_read_only_e_confirmacao_muda_so_o_ledger(self):
        before = {
            path.relative_to(self.repo).as_posix(): path.read_bytes()
            for path in self.repo.rglob("*")
            if path.is_file()
        }
        preview = self.prepare("kurobane_jinzaburo")
        after_preview = {
            path.relative_to(self.repo).as_posix(): path.read_bytes()
            for path in self.repo.rglob("*")
            if path.is_file()
        }
        self.assertEqual(before, after_preview)

        result = progression.confirm(
            self.repo,
            preview["preparacao_id"],
            "kurobane_jinzaburo",
            "prisao_ou_confinamento_estavel",
            "sessoes/999/resumo.md",
            self.evidence("kurobane_jinzaburo"),
            session=999,
        )
        self.assertTrue(result["criado"])
        self.assertEqual(result["arquivos_alterados"], [progression.STATE.as_posix()])
        self.assertEqual(
            (self.repo / progression.SHEET).read_bytes(),
            before[progression.SHEET.as_posix()],
        )
        changed = [
            rel
            for rel, raw in before.items()
            if (self.repo / rel).read_bytes() != raw
        ]
        self.assertEqual(changed, [progression.STATE.as_posix()])

    def test_derrota_temporaria_nao_e_tipo_aceito(self):
        with self.assertRaisesRegex(progression.JuppongatanaProgressionError, "não é neutralização durável"):
            progression.prepare(
                self.repo,
                "kurobane_jinzaburo",
                "derrota_temporaria",
                "sessoes/999/resumo.md",
                self.evidence("kurobane_jinzaburo"),
            )

    def test_fonte_e_evidencia_canonica_sao_obrigatorias(self):
        with self.assertRaisesRegex(progression.JuppongatanaProgressionError, "deve ficar sob"):
            progression.prepare(
                self.repo,
                "pan_chu",
                "incapacitacao_duravel",
                "narrador/juppongatana/progressao.yaml",
                "neutralização",
            )
        with self.assertRaisesRegex(progression.JuppongatanaProgressionError, "evidência literal"):
            progression.prepare(
                self.repo,
                "pan_chu",
                "incapacitacao_duravel",
                "sessoes/999/resumo.md",
                "texto que não existe na fonte",
            )

    def test_mesmo_membro_nao_pode_contar_duas_vezes(self):
        first = self.confirm("wetuji", "incapacitacao_duravel")
        retry = progression.confirm(
            self.repo,
            first["preparacao_id"],
            "wetuji",
            "incapacitacao_duravel",
            "sessoes/999/resumo.md",
            self.evidence("wetuji"),
            session=999,
        )
        self.assertFalse(retry["criado"])
        self.assertEqual(retry["motivo"], "milestone_ja_registrado")
        with self.assertRaisesRegex(progression.JuppongatanaProgressionError, "já consumiu"):
            self.prepare("wetuji", "morte_confirmada")

    def test_preparacao_fica_obsoleta_se_outro_milestone_entrar(self):
        stale = self.prepare("kurobane_jinzaburo")
        self.confirm("pan_chu")
        with self.assertRaisesRegex(progression.JuppongatanaProgressionError, "preparação ficou obsoleta"):
            progression.confirm(
                self.repo,
                stale["preparacao_id"],
                "kurobane_jinzaburo",
                "prisao_ou_confinamento_estavel",
                "sessoes/999/resumo.md",
                self.evidence("kurobane_jinzaburo"),
                session=999,
            )

    def test_dez_membros_unicos_desbloqueiam_exatamente_niveis_oito_a_dezessete(self):
        order = [
            "fuji",
            "kajiwara_shizune",
            "uonuma_usui",
            "pan_chu",
            "kurobane_jinzaburo",
            "amagiri_seishiro",
            "sawagejo_cho",
            "kureha_shiranui",
            "yukyuzan_anji",
            "wetuji",
        ]
        unlocked = []
        for member in order:
            result = self.confirm(member)
            unlocked.append(result["nivel_desbloqueado"])
        self.assertEqual(unlocked, list(range(8, 18)))
        status = progression.status(self.repo)
        self.assertEqual(status["neutralizacoes_duraveis"], 10)
        self.assertEqual(status["nivel_desbloqueado_por_marcos"], 17)
        self.assertIsNone(status["proximo_nivel"])
        self.assertEqual(status["restantes"], [])
        self.assertTrue(status["concluido"])

    def test_ficha_nao_pode_avancar_na_faixa_antes_do_milestone(self):
        self.set_level(8)
        check = progression.validate_repo(self.repo)
        self.assertFalse(check["ok"])
        self.assertTrue(any("excede nível 7" in error for error in check["erros"]))

    def test_milestone_pode_ficar_pendente_ate_aplicacao_mecanica_segura(self):
        self.confirm("kurobane_jinzaburo")
        check = progression.validate_repo(self.repo)
        self.assertTrue(check["ok"], check["erros"])
        self.assertEqual(check["niveis_pendentes"], 1)
        status = progression.status(self.repo)
        self.assertTrue(status["niveis_pendentes_de_aplicacao"])
        self.set_level(8)
        check_after = progression.validate_repo(self.repo)
        self.assertTrue(check_after["ok"], check_after["erros"])
        self.assertEqual(check_after["niveis_pendentes"], 0)


class JuppongatanaMilestoneBudgetTest(unittest.TestCase):
    def test_contrato_de_orcamento_bate_com_codigo(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/juppongatana-milestone-progression-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        limits = contract["limites"]
        self.assertEqual(limits["nivel_base"], progression.BASE_LEVEL)
        self.assertEqual(limits["ultimo_nivel"], progression.FINAL_LEVEL)
        self.assertEqual(limits["neutralizacoes_maximas"], progression.MAX_NEUTRALIZATIONS)
        self.assertEqual(limits["max_bytes_estado"], progression.MAX_STATE_BYTES)
        self.assertEqual(limits["max_evidencia_chars"], progression.MAX_EVIDENCE_CHARS)
        self.assertEqual(limits["max_nota_chars"], progression.MAX_NOTE_CHARS)
        self.assertEqual(limits["max_fontes_status"], 3)
        self.assertEqual(limits["max_fontes_preparacao"], 4)
        self.assertEqual(limits["max_escritas_confirmacao"], 1)
        self.assertEqual(limits["max_scans_repo"], 0)
        self.assertEqual(limits["max_schedulers_novos"], 0)


if __name__ == "__main__":
    unittest.main()
