from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).parents[1] / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import _cronica_turn_core as core
import iniciativa_elenco as initiative
import iniciativa_social
import memoria_cena as memory
import memoria_cena_iniciativa as layer


class FakeReader:
    def __init__(self):
        self.sources = ["estado/estado-atual.yaml"]
        self._indexes = [{"nera_vell": {"arquivo": "estado/npcs/nera_vell.yaml"}}, {}, {}]

    def indexes(self):
        return self._indexes

    def resolve(self, terms, _indexes):
        return sorted(set(terms))


class SceneMemoryInitiativeCompositionTest(unittest.TestCase):
    def payload(self, *, scene_id="convivencia", stay=False):
        result = {
            "schema_cronica_ticket": 1,
            "preparacao_id": "turn-neutral-memory",
            "cena": {
                "scene_id": scene_id,
                "npcs": [],
                "place": "circo_hooft" if stay else None,
                "action": None,
                "tier": None,
                "danger": None,
                "context_tags": [],
                "now_minute": None,
                "approach": {"preparacao": None, "informacao": None, "adequacao": None},
            },
        }
        if stay:
            result["permanencia_espacial"] = {
                "local_id": "circo_hooft", "data": "21 Eleasis, 1372 DR", "periodo": "dia"
            }
        return result

    def social_doc(self):
        social = iniciativa_social.project(
            {"identidade_relacional": "ren", "medidores": {"risco_percebido": 2}},
            relationship_mode="alta_afinidade_alta_confianca",
        )
        return {"resultado": {"dialogo_relacional": {"iniciativa_social": social}}}

    def state(self):
        return {
            "campanha": {"sessao_atual": 20, "modo_de_cena_atual": "interacao"},
            "localizacao": {"area": "circo_hooft", "ponto_exato": "acampamento"},
        }

    def saved(self, scene_id="convivencia"):
        return {
            "versao": memory.VERSION,
            "cena_id": scene_id,
            "local": {"area": "circo_hooft", "ponto_exato": "acampamento"},
            "participantes": ["nera_vell"],
        }

    def prepared(self, payload):
        token, ticket_id = core.encode_ticket(payload)
        return {"ticket": token, "ticket_id": ticket_id, "fontes_lidas": [], "contrato_conclusao": {}}

    def memory_pack(self):
        return {"versao": memory.VERSION, "modo": "completa", "itens": {"nera_vell": {"encontrado": True}}}

    def test_mesmo_carregamento_produz_memoria_e_decisao_no_mesmo_ticket(self):
        reader = FakeReader()
        docs = {"nera_vell": self.social_doc()}
        with tempfile.TemporaryDirectory() as tmp:
            with (
                layer.interlocutors(["nera_vell"]),
                mock.patch.object(memory, "load_scene", return_value=(reader, self.state(), [], self.saved())),
                mock.patch.object(memory, "documents", return_value=docs) as load_docs,
                mock.patch.object(memory, "project", return_value=self.memory_pack()),
            ):
                out = layer.attach(
                    Path(tmp),
                    self.prepared(self.payload()),
                    decode_ticket=core.decode_ticket,
                    encode_ticket=core.encode_ticket,
                    participants=["nera_vell"],
                    max_output_bytes=8192,
                )
        load_docs.assert_called_once()
        decoded = core.decode_ticket(out["ticket"])
        self.assertIn(memory.TICKET_KEY, decoded)
        self.assertIn(initiative.TICKET_KEY, decoded)
        self.assertIn("nera_vell", out[memory.KEY]["itens"])
        self.assertEqual(out[initiative.PUBLIC_KEY]["interlocutores"], ["nera_vell"])
        self.assertEqual(out[initiative.PUBLIC_KEY]["itens"][0]["presenca"], "elenco_cena")
        self.assertEqual(out[initiative.PUBLIC_KEY]["metricas"]["consultas_adicionais_por_npc"], 0)

    def test_novo_participante_carrega_memoria_mas_nao_prova_presenca_retroativa(self):
        reader = FakeReader()
        docs = {"nera_vell": self.social_doc()}
        with tempfile.TemporaryDirectory() as tmp:
            with (
                layer.interlocutors(["nera_vell"]),
                mock.patch.object(memory, "load_scene", return_value=(reader, self.state(), [], None)),
                mock.patch.object(memory, "documents", return_value=docs),
                mock.patch.object(memory, "project", return_value=self.memory_pack()),
            ):
                out = layer.attach(
                    Path(tmp), self.prepared(self.payload()),
                    decode_ticket=core.decode_ticket, encode_ticket=core.encode_ticket,
                    participants=["nera_vell"], max_output_bytes=8192,
                )
        item = out[initiative.PUBLIC_KEY]["itens"][0]
        self.assertIn("nera_vell", out[memory.KEY]["itens"])
        self.assertEqual(item["presenca"], "ausente")
        self.assertEqual(item["resultado_automatico"], "nao_elegivel")
        self.assertIsNone(out[initiative.PUBLIC_KEY]["selecionada"])

    def test_permanencia_mesmo_local_preserva_presenca_apesar_de_novo_scene_id(self):
        reader = FakeReader()
        docs = {"nera_vell": self.social_doc()}
        with tempfile.TemporaryDirectory() as tmp:
            with (
                layer.interlocutors(["nera_vell"]),
                mock.patch.object(memory, "load_scene", return_value=(reader, self.state(), [], self.saved("cena-anterior"))),
                mock.patch.object(memory, "documents", return_value=docs),
                mock.patch.object(memory, "project", return_value=self.memory_pack()),
            ):
                out = layer.attach(
                    Path(tmp), self.prepared(self.payload(scene_id="cena-renomeada", stay=True)),
                    decode_ticket=core.decode_ticket, encode_ticket=core.encode_ticket,
                    max_output_bytes=8192,
                )
        item = out[initiative.PUBLIC_KEY]["itens"][0]
        self.assertEqual(item["presenca"], "elenco_cena")
        self.assertIsNotNone(out[initiative.PUBLIC_KEY]["selecionada"])

    def test_sem_interlocutor_delega_byte_logicamente(self):
        sentinel = {"sem_nv16": True}
        with tempfile.TemporaryDirectory() as tmp:
            with mock.patch.object(layer, "_BASE_ATTACH", return_value=sentinel) as base:
                result = layer.attach(
                    Path(tmp),
                    {"ticket": "x"},
                    decode_ticket=lambda value: value,
                    encode_ticket=lambda value: value,
                )
        self.assertIs(result, sentinel)
        base.assert_called_once()


if __name__ == "__main__":
    unittest.main()
