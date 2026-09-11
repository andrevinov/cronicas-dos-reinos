from __future__ import annotations

from pathlib import Path
import sys
import unittest

import yaml

TOOLS = Path(__file__).resolve().parents[1] / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import consolidar
import reconhecibilidade_persona as fame
import turno
import test_planos_personagens as legacy


class RecognitionWriterIntegrationTest(legacy.PlanFixture):
    FACT = "Kage concluiu uma apresentação pública anunciada diante dos artistas reunidos no circo."

    def setUp(self):
        super().setUp()
        self.write("personagens/jogador/identidades.yaml", {
            "schema_identidades_ren": 1,
            "natureza": "registro_canonico_de_personas_do_jogador",
            "principal": "ren",
            "observacao": "Fixture NV-20.",
            "identidades": {
                "ren": {"nome": "Ren", "tipo": "identidade_principal", "aliases": ["Ren"]},
                "shinta": {"nome": "Shinta", "tipo": "cobertura", "aliases": ["Shinta"]},
                "kage": {"nome": "Kage", "tipo": "persona_publica", "aliases": ["Kage"]},
            },
            "regras": {
                "actor_nao_e_metamorfose": True,
                "suspeita_nao_e_conhecimento_confirmado": True,
                "suspeita_forte_nao_confirma_sozinha": True,
                "confirmacao_exige_fato_canonico_explicito": True,
            },
        })
        social = self.repo / "cenario/regioes/ravens-bluff/faccoes.md"
        social.parent.mkdir(parents=True, exist_ok=True)
        social.write_text("# Fixture social NV-20\n", encoding="utf-8")
        self.write("cenario/regioes/ravens-bluff/publicos-reputacao.yaml", {
            "schema_publicos_reputacao": 1,
            "cidade": "ravens_bluff",
            "natureza": "registro_canonico_de_publicos_sociais",
            "fonte_estrutura_social": "cenario/regioes/ravens-bluff/faccoes.md",
            "observacao": "Fixture dirigida.",
            "publicos": {
                "circo_e_artes": {"nome": "Circo e artes", "aliases": ["circo"], "descricao": "Público cultural."},
            },
            "regras": {
                "publico_nao_e_opiniao_individual": True,
                "publico_nao_compartilha_conhecimento_secreto_automaticamente": True,
                "reputacoes_de_personas_nao_se_fundem_automaticamente": True,
            },
        })

    def transaction(self):
        proposal = fame.propose_public_performance(
            self.repo, persona="kage", audiences=["circo_e_artes"], locality="ravens_bluff",
            milestone="kage_show_fixture", fact=self.FACT, source="fixture:kage_show", records=[]
        )
        return {
            "id": "kage-show-fixture",
            "modo": "mundo",
            "narracao": self.FACT,
            "resumo": self.FACT,
            "deltas": proposal["deltas"],
        }

    def test_marco_e_fama_entram_no_mesmo_plano_de_consolidacao(self):
        tx = self.transaction()
        turno.register_transaction(self.repo, tx)
        plan = consolidar.build_plan(self.repo, "cena")
        self.assertIn("estado/estado-atual.yaml", plan["outputs"])
        staged = yaml.safe_load(plan["outputs"]["estado/estado-atual.yaml"].decode("utf-8"))
        ledger = staged[fame.STATE_ROOT]
        self.assertEqual(len(ledger["eventos"]), 1)
        event = next(iter(ledger["eventos"].values()))
        self.assertEqual(event["persona"], "kage")
        self.assertEqual(event["marco_publico"], "kage_show_fixture")
        ledger_path = f"sessoes/{plan['sessao']:03d}/consolidacoes.jsonl"
        self.assertIn(ledger_path, plan["outputs"])

    def test_install_e_retry_nao_duplicam_o_marco(self):
        tx = self.transaction()
        turno.register_transaction(self.repo, tx)
        plan = consolidar.build_plan(self.repo, "cena")
        consolidar.stage_plan(self.repo, plan)
        consolidar.resume_consolidation(self.repo)
        before = self.hashes()
        result = turno.register_transaction(self.repo, tx)
        self.assertTrue(result["consolidada"] or result["ja_registrada"])
        self.assertEqual(before, self.hashes())
        projection = fame.query(
            self.repo, persona="kage", audience="circo_e_artes", locality="ravens_bluff", records=[]
        )
        self.assertEqual(projection["marcos_distintos"], 1)


if __name__ == "__main__":
    unittest.main()
