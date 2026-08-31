from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
AGENTS = ROOT / "AGENTS.md"
POLICY = ROOT / "docs/agente/politica-de-testes.md"


class PermanentTestPolicyContractTest(unittest.TestCase):
    def test_agents_roteia_e_resume_as_seis_regras_permanentes(self):
        text = AGENTS.read_text(encoding="utf-8")
        self.assertIn("docs/agente/politica-de-testes.md", text)
        required = (
            "estado vivo",
            "invariantes",
            "fixtures/snapshots/cenários temporários/histórico imutável",
            "snapshot histórico",
            "nome de domínio",
            "propriedade protegida",
            "TemporaryDirectory",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)

    def test_documento_detalhado_declara_as_seis_regras(self):
        text = POLICY.read_text(encoding="utf-8")
        headings = (
            "## Regra 1 — estado vivo",
            "## Regra 2 — valores absolutos mutáveis",
            "## Regra 3 — snapshots históricos",
            "## Regra 4 — nomes de testes pertencem ao domínio, não à Task",
            "## Regra 5 — remoção e consolidação",
            "## Regra 6 — estado real é exceção, não padrão",
        )
        for heading in headings:
            with self.subTest(heading=heading):
                self.assertIn(heading, text)

    def test_politica_ancora_os_mecanismos_de_revisao_ja_existentes(self):
        text = POLICY.read_text(encoding="utf-8")
        paths = (
            "ferramentas/auditar-testes.py",
            "ferramentas/verificar-congelamentos-estado-vivo.py",
            "tests/live-state-freeze-review.yaml",
            "ferramentas/verificar-testes-historicos.py",
            "tests/historical-test-review.yaml",
            "docs/agente/perfis-de-testes.md",
        )
        for rel in paths:
            with self.subTest(path=rel):
                self.assertTrue((ROOT / rel).is_file(), rel)
                self.assertIn(rel, text)

    def test_auditoria_continua_read_only_e_suspeita_exige_revisao_semantica(self):
        auditor = (ROOT / "ferramentas/auditar-testes.py").read_text(encoding="utf-8")
        policy = POLICY.read_text(encoding="utf-8")
        self.assertIn("somente leitura", auditor)
        self.assertIn('candidates.append("congelamento_suspeito")', auditor)
        self.assertIn("sinal de revisão", policy)
        self.assertIn("não veredito automático de erro", policy)
        self.assertIn("corrigido", policy)
        self.assertIn("justificado", policy)

    def test_snapshot_de_referencia_declara_natureza_momento_e_nao_estado_futuro(self):
        data = yaml.safe_load(
            (ROOT / "tests/fixtures/ren-5-5e-activation-snapshot.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(data["natureza"], "snapshot_historico_isolado")
        self.assertTrue(data["momento"])
        note = data["observacao"].lower()
        self.assertIn("estado vivo futuro", note)
        self.assertIn("não devem ser comparados", note)


if __name__ == "__main__":
    unittest.main()
