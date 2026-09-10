from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import iniciativa_elenco as initiative
import iniciativa_elenco_conclusao as conclusion
import iniciativa_elenco_estado as receipts
import iniciativa_social


class PresentCastInitiativeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self.people = ["nera_vell", "silva_elkwood", "jack_mooney"]
        self.indexes = [{npc: {"arquivo": f"estado/npcs/{npc}.yaml"} for npc in self.people}, {}, {}]

    def tearDown(self):
        self.temp.cleanup()

    def social(self, *, mode="alta_afinidade_alta_confianca", risk=4):
        payload = {"identidade_relacional": "ren", "medidores": {"risco_percebido": risk}}
        return iniciativa_social.project(payload, relationship_mode=mode)

    def docs(self, modes=None, *, commitment=None):
        modes = modes or {}
        result = {
            npc: {"resultado": {"dialogo_relacional": {"iniciativa_social": self.social(mode=modes.get(npc, "alta_afinidade_alta_confianca"))}}}
            for npc in self.people
        }
        if commitment is not None:
            result["@compromissos"] = commitment
        return result

    def payload(self, scene="convivencia", *, stay=False):
        value = {"cena": {"scene_id": scene, "npcs": [], "place": None, "context_tags": []}}
        if stay:
            value["permanencia_espacial"] = {
                "local_id": "circo_hooft", "data": "21 Eleasis, 1372 DR", "periodo": "dia"
            }
        return value

    def attach(self, interlocutors, *, physical=None, contactable=None, docs=None, payload=None, prepared=None):
        return initiative.attach_loaded(
            self.repo,
            prepared or {"fontes_lidas": [], "contrato_conclusao": {}},
            payload or self.payload(),
            interlocutors=interlocutors,
            physical=self.people if physical is None else physical,
            contactable=[] if contactable is None else contactable,
            docs=self.docs() if docs is None else docs,
            indexes=self.indexes,
            scene_mode="interacao",
        )

    def test_tres_interlocutores_recebem_decisao_e_so_um_abre(self):
        out, meta = self.attach(self.people)
        public = out[initiative.PUBLIC_KEY]
        self.assertEqual(set(public["interlocutores"]), set(self.people))
        self.assertEqual(len(public["itens"]), 3)
        self.assertEqual(sum(item["requer_decisao"] for item in public["itens"]), 1)
        self.assertEqual(public["selecionada"], "ini-" + initiative._digest([
            public["janela_id"], "jack_mooney",
            next(row["proposta_digest"] for row in meta["itens"] if row["npc_id"] == "jack_mooney")
        ])[:20])
        self.assertEqual(sum(item["resultado_automatico"] == "silencio_justificado" for item in public["itens"]), 2)
        self.assertEqual(len(out["pressao_narrativa"]["itens"]), 1)

    def test_participante_sem_interlocutor_nao_acorda_camada(self):
        prepared = {"marcador": "inalterado"}
        out, meta = initiative.attach_loaded(
            self.repo, prepared, self.payload(), interlocutors=None, physical=self.people,
            contactable=[], docs=self.docs(), indexes=self.indexes, scene_mode="interacao"
        )
        self.assertIs(out, prepared)
        self.assertIsNone(meta)
        self.assertNotIn(initiative.PUBLIC_KEY, out)

    def test_interlocutor_ausente_nao_fabrica_encontro(self):
        out, meta = self.attach(["nera_vell"], physical=[])
        item = out[initiative.PUBLIC_KEY]["itens"][0]
        self.assertEqual(item["presenca"], "ausente")
        self.assertEqual(item["resultado_automatico"], "nao_elegivel")
        self.assertEqual(item["motivo_automatico"], "ausencia")
        self.assertIsNone(out[initiative.PUBLIC_KEY]["selecionada"])
        self.assertNotIn("pressao_narrativa", out)
        self.assertNotIn("encontro", yaml.safe_dump(meta, allow_unicode=True))

    def test_interlocutor_nao_cria_sidequest(self):
        out, _ = self.attach(["nera_vell"])
        rendered = yaml.safe_dump(out, allow_unicode=True)
        self.assertNotIn("sidequest_emergente", rendered)
        self.assertNotIn("nova_oportunidade", rendered)

    def test_pressao_superior_adia_sem_apagar(self):
        prepared = {
            "fontes_lidas": [], "contrato_conclusao": {},
            "pressao_narrativa": {"itens": [{"id": "prazo", "tipo": "fronteira_temporal"}]},
        }
        out, meta = self.attach(["nera_vell"], prepared=prepared)
        item = out[initiative.PUBLIC_KEY]["itens"][0]
        self.assertEqual(item["resultado_automatico"], "adiada_por_pressao_superior")
        self.assertEqual(item["pressao_superior"], "prazo")
        self.assertIsNone(out[initiative.PUBLIC_KEY]["selecionada"])
        self.assertEqual(meta["itens"][0]["resultado_automatico"], "adiada_por_pressao_superior")

    def test_motivo_obrigatorio_sem_causa_produz_silencio_auditavel(self):
        docs = self.docs({"nera_vell": "baixa_afinidade_alta_confianca"})
        out, _ = self.attach(["nera_vell"], docs=docs)
        item = out[initiative.PUBLIC_KEY]["itens"][0]
        self.assertEqual(item["resultado_automatico"], "silencio_justificado")
        self.assertEqual(item["motivo_automatico"], "sem_motivo_concreto")

    def test_compromisso_ja_carregado_pode_ser_motivo_sem_nova_leitura(self):
        docs = self.docs(
            {"nera_vell": "baixa_afinidade_alta_confianca"},
            commitment={"acordo": {"envolvidos": ["nera_vell"], "situacao_temporal": "devido"}},
        )
        out, _ = self.attach(["nera_vell"], docs=docs)
        self.assertIsNotNone(out[initiative.PUBLIC_KEY]["selecionada"])
        self.assertEqual(out[initiative.PUBLIC_KEY]["itens"][0]["proposta"]["causa_id"], "compromisso:acordo")
        self.assertEqual(out[initiative.PUBLIC_KEY]["metricas"]["consultas_adicionais_por_npc"], 0)

    def test_contato_validado_conta_como_contactabilidade(self):
        out, _ = self.attach(["nera_vell"], physical=[], contactable=["nera_vell"])
        self.assertEqual(out[initiative.PUBLIC_KEY]["itens"][0]["presenca"], "canal_contato")
        self.assertIsNotNone(out[initiative.PUBLIC_KEY]["selecionada"])

    def test_permanencia_ignora_scene_id_na_identidade_da_janela(self):
        first, meta_a = self.attach(["nera_vell"], payload=self.payload("cena-a", stay=True))
        second, meta_b = self.attach(["nera_vell"], payload=self.payload("cena-b", stay=True))
        self.assertEqual(first[initiative.PUBLIC_KEY]["janela_id"], second[initiative.PUBLIC_KEY]["janela_id"])
        self.assertEqual(meta_a["itens"][0]["decisao_id"], meta_b["itens"][0]["decisao_id"])

    def test_apresentada_exige_evidencia_literal_e_retry_reutiliza(self):
        out, meta = self.attach(["nera_vell"])
        decision_id = out[initiative.PUBLIC_KEY]["selecionada"]
        tx = {"narracao": "Nera pergunta se Ren pretende ficar para o jantar.", "resumo": "Nera inicia conversa."}
        tx[initiative.TRANSACTION_KEY] = {
            "decisao_id": decision_id, "resultado": "apresentada",
            "evidencia_literal": "Nera pergunta se Ren pretende ficar para o jantar."
        }
        plan = conclusion.prepare(self.repo, meta, tx)
        first = conclusion.install(self.repo, meta, plan, ticket_id="ticket-a", transaction_id="tx-a")
        second = conclusion.install(self.repo, meta, plan, ticket_id="ticket-a", transaction_id="tx-a")
        self.assertTrue(first["alterou_estado"])
        self.assertFalse(second["alterou_estado"])
        again, _ = self.attach(["nera_vell"])
        self.assertIsNone(again[initiative.PUBLIC_KEY]["selecionada"])
        self.assertTrue(again[initiative.PUBLIC_KEY]["itens"][0]["reutilizado"])

    def test_evidencia_inventada_falha_antes_de_instalar(self):
        out, meta = self.attach(["nera_vell"])
        tx = {"narracao": "Nera permanece em silêncio.", "resumo": "Nada novo."}
        tx[initiative.TRANSACTION_KEY] = {
            "decisao_id": out[initiative.PUBLIC_KEY]["selecionada"],
            "resultado": "apresentada", "evidencia_literal": "Nera fez uma pergunta concreta"
        }
        with self.assertRaises(initiative.CastInitiativeError):
            conclusion.prepare(self.repo, meta, tx)
        self.assertEqual(receipts.load(self.repo)["decisoes"], {})

    def test_abertura_ja_apresentada_bloqueia_outro_npc_na_mesma_janela(self):
        out, meta = self.attach(["nera_vell"])
        did = out[initiative.PUBLIC_KEY]["selecionada"]
        tx = {"narracao": "Nera chama Ren para conversar agora.", "resumo": "Nera inicia a conversa.",
              initiative.TRANSACTION_KEY: {"decisao_id": did, "resultado": "apresentada",
                                           "evidencia_literal": "Nera chama Ren para conversar agora."}}
        plan = conclusion.prepare(self.repo, meta, tx)
        conclusion.install(self.repo, meta, plan, ticket_id="ticket-a", transaction_id="tx-a")
        later, _ = self.attach(["silva_elkwood"])
        item = later[initiative.PUBLIC_KEY]["itens"][0]
        self.assertIsNone(later[initiative.PUBLIC_KEY]["selecionada"])
        self.assertEqual(item["motivo_automatico"], "janela_ocupada")


class PresentCastInitiativeBudgetTest(unittest.TestCase):
    def test_budget_congela_zero_scan_rng_scheduler_e_ia(self):
        budget = yaml.safe_load((ROOT / "baseline/present-cast-initiative-orcamento.yaml").read_text(encoding="utf-8"))
        limits = budget["limites"]
        self.assertEqual(limits["interlocutores_por_preparo_max"], initiative.MAX_INTERLOCUTORS)
        self.assertEqual(limits["aberturas_por_janela_max"], initiative.MAX_OPENINGS_PER_WINDOW)
        self.assertEqual(limits["projecao_publica_bytes_max"], initiative.MAX_PUBLIC_BYTES)
        self.assertEqual(limits["ticket_bytes_max"], initiative.MAX_TICKET_BYTES)
        self.assertEqual(limits["estado_reservado_bytes_max"], receipts.MAX_STATE_BYTES)
        self.assertEqual(limits["registros_reservados_max"], receipts.MAX_RECORDS)
        for key in ("consultas_adicionais_por_npc", "chamadas_ia_por_npc", "rng_novo", "schedulers_novos", "scans_globais_npc"):
            self.assertEqual(limits[key], 0)
        self.assertTrue(all(budget["invariantes"].values()))


if __name__ == "__main__":
    unittest.main()
