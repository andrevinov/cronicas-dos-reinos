from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

import yaml

TOOLS = Path(__file__).resolve().parents[1] / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import reconhecibilidade_persona as fame
import planos_personagens as plans
import transacoes


class RecognitionFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name)
        self.write("estado/estado-atual.yaml", {"campanha": {"sessao_atual": 1}})
        self.write("personagens/jogador/identidades.yaml", {
            "schema_identidades_ren": 1,
            "natureza": "registro_canonico_de_personas_do_jogador",
            "principal": "ren",
            "observacao": "Fixture: personas permanecem separadas.",
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
        social.write_text("# Estrutura social da fixture\n", encoding="utf-8")
        self.write("cenario/regioes/ravens-bluff/publicos-reputacao.yaml", {
            "schema_publicos_reputacao": 1,
            "cidade": "ravens_bluff",
            "natureza": "registro_canonico_de_publicos_sociais",
            "fonte_estrutura_social": "cenario/regioes/ravens-bluff/faccoes.md",
            "observacao": "Fixture dirigida.",
            "publicos": {
                "circo_e_artes": {"nome": "Circo e artes", "aliases": ["circo"], "descricao": "Público cultural."},
                "redes_informais": {"nome": "Redes informais", "aliases": ["redes"], "descricao": "Redes discretas."},
            },
            "regras": {
                "publico_nao_e_opiniao_individual": True,
                "publico_nao_compartilha_conhecimento_secreto_automaticamente": True,
                "reputacoes_de_personas_nao_se_fundem_automaticamente": True,
            },
        })
        self.fact = "Kage concluiu uma apresentação pública diante do público do circo."

    def write(self, relative, value):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def proposal(self, audiences=None, milestone="kage_estreia"):
        return fame.propose_public_performance(
            self.repo,
            persona="kage",
            audiences=audiences or ["circo_e_artes"],
            locality="ravens_bluff",
            milestone=milestone,
            fact=self.fact,
            source="sessoes/001/transcricao.md#kage-estreia",
            records=[],
        )

    def install(self, proposal):
        state = yaml.safe_load((self.repo / fame.STATE_FILE).read_text(encoding="utf-8"))
        state[fame.STATE_ROOT] = deepcopy(proposal["deltas"][1]["valor"])
        self.write(fame.STATE_FILE.as_posix(), state)


class PublicPerformanceContractTest(RecognitionFixture):
    def test_apresentacao_confirmada_produz_marco_e_fama_no_mesmo_writer(self):
        proposal = self.proposal()
        self.assertEqual(proposal["resultado"], "registrar_no_mesmo_writer")
        self.assertEqual(len(proposal["deltas"]), 2)
        marker, ledger = proposal["deltas"]
        self.assertEqual(marker["alvo"], "consequencia")
        self.assertEqual(marker["valor"]["tipo"], fame.PERFORMANCE_TYPE)
        self.assertEqual(ledger["caminho"], fame.STATE_ROOT)
        fame.validate_transaction_contract(
            proposal["deltas"], fame.load_audiences(self.repo), fame.load_identities(self.repo)
        )

    def test_marker_sem_evento_de_fama_falha_fechado(self):
        marker = self.proposal()["deltas"][0]
        with self.assertRaisesRegex(fame.RecognizabilityError, "mesmo writer"):
            fame.validate_transaction_contract(
                [marker], fame.load_audiences(self.repo), fame.load_identities(self.repo)
            )

    def test_wrapper_transacional_exige_o_mesmo_pareamento(self):
        proposal = self.proposal()
        record = {
            "versao": 1,
            "id": "performance-kage",
            "sessao": 1,
            "resumo": "Kage se apresentou publicamente.",
            "deltas": proposal["deltas"],
        }
        self.assertEqual(transacoes.validate_pending_record(record), record)
        bad = deepcopy(record)
        bad["deltas"] = bad["deltas"][:1]
        with self.assertRaisesRegex(ValueError, "mesmo writer"):
            transacoes.validate_pending_record(bad)

    def test_dedup_por_marco_e_audiencia_nao_farma_fama(self):
        first = self.proposal()
        self.install(first)
        second = self.proposal()
        self.assertEqual(second["resultado"], "ja_registrado")
        self.assertEqual(second["deltas"], [])
        state = yaml.safe_load((self.repo / fame.STATE_FILE).read_text(encoding="utf-8"))[fame.STATE_ROOT]
        self.assertEqual(len(state["eventos"]), 1)

    def test_transicao_e_append_only(self):
        proposal = self.proposal()
        audiences = fame.load_audiences(self.repo)
        identities = fame.load_identities(self.repo)
        after = fame.validate_transition(None, proposal["deltas"][1], audiences, identities)
        altered = deepcopy(proposal["deltas"][1])
        altered["valor"] = fame.empty_state()
        with self.assertRaises(fame.RecognizabilityError):
            fame.validate_transition(after, altered, audiences, identities)


class DirectedRecognitionTest(RecognitionFixture):
    def test_kage_ren_e_shinta_permanecem_separados(self):
        self.install(self.proposal())
        kage = fame.query(self.repo, persona="kage", audience="circo_e_artes", locality="ravens_bluff", records=[])
        ren = fame.query(self.repo, persona="ren", audience="circo_e_artes", locality="ravens_bluff", records=[])
        shinta = fame.query(self.repo, persona="shinta", audience="circo_e_artes", locality="ravens_bluff", records=[])
        self.assertEqual(kage["nivel"], "reconhecivel")
        self.assertEqual(kage["marcos_distintos"], 1)
        self.assertEqual(ren["nivel"], "desconhecida")
        self.assertEqual(shinta["nivel"], "desconhecida")
        self.assertEqual(ren["marcos_distintos"], shinta["marcos_distintos"])

    def test_query_e_dirigida_por_persona_publico_e_localidade(self):
        self.install(self.proposal(["circo_e_artes", "redes_informais"]))
        circus = fame.query(self.repo, persona="kage", audience="circo_e_artes", locality="ravens_bluff", records=[])
        networks = fame.query(self.repo, persona="kage", audience="redes_informais", locality="ravens_bluff", records=[])
        other_place = fame.query(self.repo, persona="kage", audience="circo_e_artes", locality="porto", records=[])
        self.assertEqual(circus["marcos_distintos"], 1)
        self.assertEqual(networks["marcos_distintos"], 1)
        self.assertEqual(other_place["marcos_distintos"], 0)

    def test_evento_de_fama_vira_causa_canonica_sem_fundir_identidade(self):
        proposal = self.proposal()
        event = proposal["eventos"][0]
        ref = fame.event_reference(event)
        self.assertEqual(ref["arquivo"], "estado/estado-atual.yaml")
        self.assertIn(event["id"], ref["caminho"])
        self.assertEqual(plans._ref(ref), ref)
        self.assertEqual(ref["valor"]["persona"], "kage")
        self.assertNotIn("ren", ref["caminho"])


if __name__ == "__main__":
    unittest.main()
