from __future__ import annotations

from pathlib import Path
import sys
import unittest

import yaml

TOOLS = Path(__file__).resolve().parents[1] / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import consolidar
import politica_civica as civic
import turno
import test_planos_personagens as legacy


class CivicWriterIntegrationTest(legacy.PlanFixture):
    DATE = "7 Eleasis, 1372 DR"

    def setUp(self):
        super().setUp()
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
            },
        })
        self.write("cenario/regioes/ravens-bluff/catalogo-medidas-civicas.yaml", {
            "schema_catalogo_medidas_civicas": 1,
            "jurisdicao": "ravens_bluff",
            "natureza": "fixture",
            "medidas_menores": {
                "aviso_seguranca_local": {
                    "tipo": "aviso", "descricao": "Fixture.",
                    "instituicoes": ["lord_mayor_gabinete"],
                    "canais_sugeridos": ["quadro_avisos"],
                },
            },
        })

    def when(self, hour):
        return {"data": self.DATE, "hora": hour}

    def proposal(self):
        return civic.propose_measure(
            self.repo,
            institution="lord_mayor_gabinete",
            measure_type="aviso",
            title="Aviso cívico de integração",
            motive="A administração precisa sinalizar uma restrição local.",
            institutional_cause="Despacho institucional registrado na fixture.",
            scope={"localidades": ["ravens_bluff"], "descricao": "Cidade."},
            when=self.when("08:03"),
        )

    def published_state(self):
        proposal = self.proposal()
        measure_id = proposal["medida"]
        state = proposal["deltas"][0]["valor"]
        approved = civic.propose_transition(
            self.repo, measure_id=measure_id, target_phase="aprovada",
            when=self.when("08:04"), reason="Aprovada.", state=state,
        )
        state = approved["deltas"][0]["valor"]
        effective = civic.propose_transition(
            self.repo, measure_id=measure_id, target_phase="vigente",
            when=self.when("08:05"), reason="Vigente.", state=state,
        )
        state = effective["deltas"][0]["valor"]
        publication = civic.propose_publication(
            self.repo, measure_id=measure_id, locality="circo", period="persistente",
            channel="quadro_avisos", content="O acesso lateral permanecerá fechado.",
            when=self.when("08:06"), state=state,
        )
        return measure_id, publication["publicacao"], publication["deltas"][0]["valor"]

    def test_proposta_entra_no_writer_existente_sem_writer_paralelo(self):
        proposal = self.proposal()
        tx = {
            "id": "nv22-proposta-fixture",
            "modo": "mundo",
            "narracao": "O gabinete formalizou um aviso cívico.",
            "resumo": "Proposta cívica formalizada.",
            "deltas": proposal["deltas"],
        }
        turno.register_transaction(self.repo, tx)
        plan = consolidar.build_plan(self.repo, "cena")
        self.assertIn("estado/estado-atual.yaml", plan["outputs"])
        staged = yaml.safe_load(plan["outputs"]["estado/estado-atual.yaml"].decode("utf-8"))
        self.assertIn(proposal["medida"], staged[civic.STATE_ROOT]["medidas"])
        ledger_path = f"sessoes/{plan['sessao']:03d}/consolidacoes.jsonl"
        self.assertIn(ledger_path, plan["outputs"])

    def test_entrega_e_recibo_nv13_sao_planejados_atomicamente(self):
        measure_id, publication_id, state = self.published_state()
        state_doc = self.read("estado/estado-atual.yaml")
        state_doc[civic.STATE_ROOT] = state
        self.write("estado/estado-atual.yaml", state_doc)

        delivery = civic.propose_delivery(
            self.repo, publication_id=publication_id,
            evidence="permanencia:perm-fixture", when=self.when("08:07"),
        )
        tx = {
            "id": "nv22-entrega-fixture",
            "modo": "mundo",
            "narracao": "Ren leu o aviso no quadro do circo.",
            "resumo": "Aviso cívico entregue a Ren.",
            "deltas": delivery["deltas"],
        }
        turno.register_transaction(self.repo, tx)
        plan = consolidar.build_plan(self.repo, "cena")
        self.assertIn("estado/estado-atual.yaml", plan["outputs"])
        receipt_target = delivery["deltas"][1]["alvo"].split(":", 1)[1]
        self.assertIn(f"narrador/relogios/{receipt_target}.yaml", plan["outputs"])
        staged = yaml.safe_load(plan["outputs"]["estado/estado-atual.yaml"].decode("utf-8"))
        self.assertTrue(any(
            item["medida"] == measure_id
            for item in staged[civic.STATE_ROOT]["entregas"].values()
        ))


if __name__ == "__main__":
    unittest.main()
