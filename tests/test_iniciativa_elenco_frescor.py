from __future__ import annotations

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


class InitiativeFreshnessTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.npc = "silva_elkwood"
        self.indexes = [{self.npc: {"arquivo": "estado/npcs/silva_elkwood.yaml"}}, {}, {}]
        social = iniciativa_social.project(
            {"identidade_relacional": "ren", "medidores": {"risco_percebido": 2}},
            relationship_mode="alta_afinidade_alta_confianca",
        )
        self.docs = {self.npc: {"resultado": {"dialogo_relacional": {"iniciativa_social": social}}}}
        self.payload = {"cena": {"scene_id": "convivencia", "npcs": [], "place": None, "context_tags": []}}

    def tearDown(self):
        self.temp.cleanup()

    def attach(self, prepared=None):
        return initiative.attach_loaded(
            self.repo,
            prepared or {"fontes_lidas": [], "contrato_conclusao": {}},
            self.payload,
            interlocutors=[self.npc], physical=[self.npc], contactable=[],
            docs=self.docs, indexes=self.indexes, scene_mode="interacao",
        )

    def test_adiamento_por_pressao_superior_pode_ser_reavaliado_quando_ela_some(self):
        blocked = {
            "fontes_lidas": [], "contrato_conclusao": {},
            "pressao_narrativa": {"itens": [{"id": "prazo-urgente", "tipo": "prazo_sidequest"}]},
        }
        out, meta = self.attach(blocked)
        self.assertEqual(out[initiative.PUBLIC_KEY]["itens"][0]["resultado_automatico"], "adiada_por_pressao_superior")
        plan = conclusion.prepare(self.repo, meta, {})
        conclusion.install(self.repo, meta, plan, ticket_id="ticket-1", transaction_id="tx-1")
        state = receipts.load(self.repo)
        self.assertEqual(next(iter(state["decisoes"].values()))["resultado"], "adiada_por_pressao_superior")

        resumed, resumed_meta = self.attach()
        self.assertIsNotNone(resumed[initiative.PUBLIC_KEY]["selecionada"])
        self.assertEqual(resumed_meta["itens"][0]["decisao_id"], meta["itens"][0]["decisao_id"])

    def test_silencio_terminal_nao_reabre_mesma_proposta_na_mesma_janela(self):
        out, meta = self.attach()
        decision = out[initiative.PUBLIC_KEY]["selecionada"]
        tx = {
            "narracao": "Silva observa o movimento e decide não interromper Ren.",
            "resumo": "Silva mantém a conversa em pausa.",
            initiative.TRANSACTION_KEY: {
                "decisao_id": decision,
                "resultado": "silencio_justificado",
                "motivo_codigo": "indisponibilidade",
                "motivo": "Ren está concentrado em outra interação imediata.",
            },
        }
        plan = conclusion.prepare(self.repo, meta, tx)
        conclusion.install(self.repo, meta, plan, ticket_id="ticket-2", transaction_id="tx-2")
        repeated, _ = self.attach()
        item = repeated[initiative.PUBLIC_KEY]["itens"][0]
        self.assertIsNone(repeated[initiative.PUBLIC_KEY]["selecionada"])
        self.assertTrue(item["reutilizado"])
        self.assertEqual(item["resultado_automatico"], "silencio_justificado")


if __name__ == "__main__":
    unittest.main()
