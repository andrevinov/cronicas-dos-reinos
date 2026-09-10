from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import iniciativa_elenco as initiative
import iniciativa_elenco_conclusao as conclusion
import iniciativa_elenco_estado as receipts
import iniciativa_social


class InitiativeDecisionGuardrailTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.npc = "nera_vell"
        self.indexes = [{self.npc: {"arquivo": "estado/npcs/nera_vell.yaml"}}, {}, {}]
        social = iniciativa_social.project(
            {"identidade_relacional": "ren", "medidores": {"risco_percebido": 2}},
            relationship_mode="alta_afinidade_alta_confianca",
        )
        self.docs = {self.npc: {"resultado": {"dialogo_relacional": {"iniciativa_social": social}}}}
        self.payload = {"cena": {"scene_id": "convivencia", "npcs": [], "place": None, "context_tags": []}}

    def tearDown(self):
        self.temp.cleanup()

    def attach(self, *, physical=True):
        return initiative.attach_loaded(
            self.repo,
            {"fontes_lidas": [], "contrato_conclusao": {}},
            self.payload,
            interlocutors=[self.npc],
            physical=[self.npc] if physical else [],
            contactable=[], docs=self.docs, indexes=self.indexes, scene_mode="interacao",
        )

    def test_sem_abertura_selecionada_exige_omitir_bloco_inteiro(self):
        _, meta = self.attach(physical=False)
        with self.assertRaisesRegex(initiative.CastInitiativeError, "sem abertura selecionada"):
            conclusion.prepare(self.repo, meta, {initiative.TRANSACTION_KEY: {}})

    def test_motivos_automaticos_nao_podem_ser_fabricados_no_concluir(self):
        out, meta = self.attach()
        did = out[initiative.PUBLIC_KEY]["selecionada"]
        common = {"narracao": "Nera observa Ren.", "resumo": "A janela social é avaliada."}
        for result, code in (
            ("silencio_justificado", "sem_motivo_concreto"),
            ("silencio_justificado", "janela_ocupada"),
            ("nao_elegivel", "ausencia"),
        ):
            tx = {**common, initiative.TRANSACTION_KEY: {
                "decisao_id": did, "resultado": result, "motivo_codigo": code,
                "motivo": "Motivo manual que não pode substituir um gate automático.",
            }}
            with self.subTest(resultado=result, codigo=code):
                with self.assertRaises(initiative.CastInitiativeError):
                    conclusion.prepare(self.repo, meta, tx)

    def test_ticket_adulterado_na_identidade_da_decisao_falha_fechado(self):
        _, meta = self.attach()
        tampered = copy.deepcopy(meta)
        tampered["itens"][0]["decisao_id"] = "ini-00000000000000000000"
        with self.assertRaisesRegex(initiative.CastInitiativeError, "identidade/digest"):
            conclusion.validate_ticket(tampered)

    def test_ausencia_automatica_persiste_com_justificativa_auditavel(self):
        _, meta = self.attach(physical=False)
        plan = conclusion.prepare(self.repo, meta, {})
        conclusion.install(self.repo, meta, plan, ticket_id="ticket-a", transaction_id="tx-a")
        stored = next(iter(receipts.load(self.repo)["decisoes"].values()))
        self.assertEqual(stored["resultado"], "nao_elegivel")
        self.assertEqual(stored["motivo_codigo"], "ausencia")
        self.assertIn("presença física consolidada", stored["motivo"])

    def test_abertura_apresentada_reaparece_como_silencio_de_repeticao(self):
        out, meta = self.attach()
        did = out[initiative.PUBLIC_KEY]["selecionada"]
        tx = {
            "narracao": "Nera pergunta a Ren se ele pretende jantar com o grupo.",
            "resumo": "Nera abre a conversa sobre o jantar.",
            initiative.TRANSACTION_KEY: {
                "decisao_id": did, "resultado": "apresentada",
                "evidencia_literal": "Nera pergunta a Ren se ele pretende jantar com o grupo.",
            },
        }
        plan = conclusion.prepare(self.repo, meta, tx)
        conclusion.install(self.repo, meta, plan, ticket_id="ticket-a", transaction_id="tx-a")
        repeated, repeated_meta = self.attach()
        item = repeated[initiative.PUBLIC_KEY]["itens"][0]
        self.assertIsNone(repeated[initiative.PUBLIC_KEY]["selecionada"])
        self.assertTrue(item["reutilizado"])
        self.assertEqual(item["resultado_automatico"], "silencio_justificado")
        self.assertEqual(item["motivo_automatico"], "repeticao_sem_causa_nova")
        self.assertEqual(conclusion.prepare(self.repo, repeated_meta, {})["itens"], [])


if __name__ == "__main__":
    unittest.main()
