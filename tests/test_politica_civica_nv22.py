from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

import yaml

TOOLS = Path(__file__).resolve().parents[1] / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import politica_civica as civic


class CivicPolicyFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.write("estado/estado-atual.yaml", {})
        self.write("cenario/regioes/ravens-bluff/instituicoes-civicas.yaml", {
            "schema_instituicoes_civicas": 1,
            "jurisdicao": "ravens_bluff",
            "natureza": "fixture",
            "canais_publicos": {
                "arauto": {"nome": "Arauto", "modo": "ativo"},
                "quadro_avisos": {"nome": "Quadro", "modo": "persistente"},
                "guarda": {"nome": "Guarda", "modo": "ativo"},
                "templo": {"nome": "Templo", "modo": "ativo"},
                "mensageiro": {"nome": "Mensageiro", "modo": "ativo"},
                "edital_publico": {"nome": "Edital", "modo": "persistente"},
            },
            "instituicoes": {
                "lord_mayor_gabinete": {
                    "nome": "Lord Mayor", "autorizada": True,
                    "tipos": ["lei", "decreto", "edital", "aviso"],
                    "canais": ["arauto", "quadro_avisos", "guarda", "templo", "mensageiro", "edital_publico"],
                },
                "city_guard": {
                    "nome": "City Guard", "autorizada": True,
                    "tipos": ["edital", "aviso"],
                    "canais": ["arauto", "quadro_avisos", "guarda", "mensageiro", "edital_publico"],
                },
                "advisory_council": {
                    "nome": "Advisory Council", "autorizada": False,
                    "tipos": [], "canais": [],
                },
            },
        })
        self.write("cenario/regioes/ravens-bluff/catalogo-medidas-civicas.yaml", {
            "schema_catalogo_medidas_civicas": 1,
            "jurisdicao": "ravens_bluff",
            "natureza": "fixture",
            "medidas_menores": {
                "aviso_seguranca_local": {
                    "tipo": "aviso",
                    "descricao": "Aviso menor dirigido.",
                    "instituicoes": ["lord_mayor_gabinete"],
                    "canais_sugeridos": ["quadro_avisos", "edital_publico"],
                },
            },
        })

    def write(self, relative: str, value) -> None:
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    @staticmethod
    def when(hour: str) -> dict[str, str]:
        return {"data": "21 Eleasis, 1372 DR", "hora": hour}

    def propose(self, **extra):
        args = {
            "institution": "lord_mayor_gabinete",
            "measure_type": "aviso",
            "title": "Aviso do mercado",
            "motive": "Evitar circulação na área em manutenção.",
            "institutional_cause": "Ordem registrada pelo gabinete após relatório de obras.",
            "scope": {"localidades": ["ravens_bluff"], "descricao": "Âmbito urbano."},
            "when": self.when("09:00"),
        }
        args.update(extra)
        return civic.propose_measure(self.repo, **args)

    def vigente(self):
        proposal = self.propose()
        state = proposal["deltas"][0]["valor"]
        measure_id = proposal["medida"]
        approved = civic.propose_transition(
            self.repo, measure_id=measure_id, target_phase="aprovada",
            when=self.when("10:00"), reason="Aprovação institucional.", state=state,
        )
        state = approved["deltas"][0]["valor"]
        effective = civic.propose_transition(
            self.repo, measure_id=measure_id, target_phase="vigente",
            when=self.when("11:00"), reason="Início de vigência.", state=state,
        )
        return measure_id, effective["deltas"][0]["valor"]

    def publicada(self, *, channel="quadro_avisos", period="persistente"):
        measure_id, state = self.vigente()
        result = civic.propose_publication(
            self.repo, measure_id=measure_id, locality="circo", period=period,
            channel=channel, content="A passagem leste ficará fechada durante as obras.",
            when=self.when("12:00"), state=state,
        )
        return measure_id, result["publicacao"], result["deltas"][0]["valor"]


class CivicPolicyDomainTest(CivicPolicyFixture):
    def test_medida_exige_instituicao_autorizada_motivo_causa_e_escopo(self):
        with self.assertRaises(civic.CivicPolicyError):
            self.propose(institution="advisory_council")
        with self.assertRaises(civic.CivicPolicyError):
            self.propose(motive="")
        with self.assertRaises(civic.CivicPolicyError):
            self.propose(institutional_cause="")
        with self.assertRaises(civic.CivicPolicyError):
            self.propose(scope={"localidades": [], "descricao": "nada"})

    def test_pipeline_chega_a_publicacao_e_encerramento(self):
        measure_id, publication_id, state = self.publicada()
        self.assertIn(publication_id, state["publicacoes"])
        self.assertEqual(state["medidas"][measure_id]["fase"], "publicada")
        revoked = civic.propose_transition(
            self.repo, measure_id=measure_id, target_phase="revogada",
            when=self.when("13:00"), reason="A causa deixou de existir.", state=state,
        )
        final = revoked["deltas"][0]["valor"]
        self.assertEqual(final["medidas"][measure_id]["fase"], "revogada")
        self.assertEqual(
            [item["estado"] for item in final["medidas"][measure_id]["historico"]],
            ["proposta", "aprovada", "vigente", "publicada", "revogada"],
        )

    def test_avaliacao_e_os_tres_encerramentos_sao_transicoes_legais(self):
        proposal = self.propose(title="Medida avaliada")
        state = proposal["deltas"][0]["valor"]
        measure_id = proposal["medida"]
        evaluated = civic.propose_transition(
            self.repo, measure_id=measure_id, target_phase="em_avaliacao",
            when=self.when("09:30"), reason="Encaminhada à avaliação.", state=state,
        )
        self.assertEqual(evaluated["deltas"][0]["valor"]["medidas"][measure_id]["fase"], "em_avaliacao")
        for terminal in ("expirada", "revogada"):
            mid, _pub, published = self.publicada()
            result = civic.propose_transition(
                self.repo, measure_id=mid, target_phase=terminal,
                when=self.when("13:00"), reason=f"Encerramento {terminal}.", state=published,
            )
            self.assertEqual(result["deltas"][0]["valor"]["medidas"][mid]["fase"], terminal)

        mid, _pub, published = self.publicada()
        replacement = self.propose(title="Medida substituta", when=self.when("12:30"), state=published)
        with_replacement = replacement["deltas"][0]["valor"]
        substituted = civic.propose_transition(
            self.repo, measure_id=mid, target_phase="substituida",
            replacement_id=replacement["medida"], when=self.when("13:00"),
            reason="Substituição expressa.", state=with_replacement,
        )
        self.assertEqual(
            substituted["deltas"][0]["valor"]["medidas"][mid]["substituida_por"],
            replacement["medida"],
        )

    def test_agenda_consulta_somente_planos_vencidos(self):
        self.assertEqual(civic.due_plans(self.repo, now=self.when("12:00")), [])
        proposal = self.propose()
        state = proposal["deltas"][0]["valor"]
        plan = civic.propose_plan(
            self.repo, measure_id=proposal["medida"], action="aprovar",
            due_at=self.when("10:00"), reason="Prazo interno do gabinete.", state=state,
        )
        state = plan["deltas"][0]["valor"]
        self.assertEqual(civic.due_plans(self.repo, now=self.when("09:59"), state=state), [])
        due = civic.due_plans(self.repo, now=self.when("10:00"), state=state)
        self.assertEqual([item["id"] for item in due], [plan["plano"]])
        closed = civic.propose_transition(
            self.repo, measure_id=proposal["medida"], target_phase="aprovada",
            plan_id=plan["plano"], when=self.when("10:05"), reason="Plano processado.", state=state,
        )
        self.assertEqual(closed["deltas"][0]["valor"]["planos"][plan["plano"]]["estado"], "concluido")

    def test_catalogo_menor_e_limitado_e_nao_escolhe_entrada_automaticamente(self):
        result = self.propose(catalog_slug="aviso_seguranca_local")
        measure = result["deltas"][0]["valor"]["medidas"][result["medida"]]
        self.assertEqual(measure["catalogo"], "aviso_seguranca_local")
        with self.assertRaises(civic.CivicPolicyError):
            self.propose(
                institution="city_guard", catalog_slug="aviso_seguranca_local",
                title="Tentativa incompatível",
            )
        self.assertNotIn("random", civic.__dict__)

    def test_publicacao_deduplica_por_medida_local_periodo(self):
        measure_id, publication_id, state = self.publicada()
        retry = civic.propose_publication(
            self.repo, measure_id=measure_id, locality="circo", period="persistente",
            channel="quadro_avisos", content="A passagem leste ficará fechada durante as obras.",
            when=self.when("12:10"), state=state,
        )
        self.assertEqual(retry["resultado"], "ja_publicada")
        self.assertEqual(retry["publicacao"], publication_id)
        self.assertEqual(retry["deltas"], [])

    def test_canal_ativo_nao_pode_simular_persistencia(self):
        measure_id, state = self.vigente()
        with self.assertRaises(civic.CivicPolicyError):
            civic.propose_publication(
                self.repo, measure_id=measure_id, locality="circo", period="persistente",
                channel="arauto", content="Proclamação oral.", when=self.when("12:00"), state=state,
            )


class PublicNoticeCausalityTest(CivicPolicyFixture):
    def test_edital_persistente_pode_chegar_ao_circo_pela_permanencia_e_nv13(self):
        measure_id, publication_id, state = self.publicada(channel="edital_publico")
        projection = civic.project_for_permanence(
            self.repo, locality="circo", date="21 Eleasis, 1372 DR", period="tarde",
            evaluation_id="perm-fixture", state=state,
        )
        self.assertEqual(projection["resultado"], "avisos_disponiveis")
        self.assertEqual([item["publicacao"] for item in projection["avisos"]], [publication_id])
        self.assertFalse(civic.known_to_ren(self.repo, measure_id, state=state))

        delivered = civic.propose_delivery(
            self.repo, publication_id=publication_id,
            evidence=projection["avisos"][0]["evidencia_entrega"],
            when=self.when("12:30"), state=state,
        )
        self.assertEqual(len(delivered["deltas"]), 2)
        registry = civic.load_registry(self.repo)
        catalog = civic.load_catalog(self.repo, registry)
        civic.validate_transaction_contract(delivered["deltas"], registry, catalog)
        with self.assertRaises(civic.CivicPolicyError):
            civic.validate_transaction_contract(delivered["deltas"][:1], registry, catalog)

        after = delivered["deltas"][0]["valor"]
        self.assertTrue(civic.known_to_ren(self.repo, measure_id, state=after))
        again = civic.project_for_permanence(
            self.repo, locality="circo", date="21 Eleasis, 1372 DR", period="tarde",
            evaluation_id="perm-outra-cena", state=after,
        )
        self.assertEqual(again["avisos"], [])

    def test_arauto_ja_produzido_nao_e_postagem_persistente(self):
        measure_id, state = self.vigente()
        publication = civic.propose_publication(
            self.repo, measure_id=measure_id, locality="circo",
            period="21 Eleasis, 1372 DR|tarde", channel="arauto",
            content="O arauto proclama a medida.", when=self.when("12:00"), state=state,
        )
        current = publication["deltas"][0]["valor"]
        projection = civic.project_for_permanence(
            self.repo, locality="circo", date="21 Eleasis, 1372 DR", period="tarde",
            state=current,
        )
        self.assertEqual(projection["avisos"], [])

    def test_plano_vencido_sem_publicacao_nao_vaza_na_permanencia(self):
        proposal = self.propose()
        state = proposal["deltas"][0]["valor"]
        plan = civic.propose_plan(
            self.repo, measure_id=proposal["medida"], action="aprovar",
            due_at=self.when("10:00"), reason="Avaliar o aviso.", state=state,
        )
        state = plan["deltas"][0]["valor"]
        self.assertEqual(len(civic.due_plans(self.repo, now=self.when("12:00"), state=state)), 1)
        projection = civic.project_for_permanence(
            self.repo, locality="circo", date="21 Eleasis, 1372 DR", period="tarde", state=state,
        )
        self.assertEqual(projection["resultado"], "nenhum_aviso_publico_produzido")
        self.assertEqual(projection["avisos"], [])


if __name__ == "__main__":
    unittest.main()
