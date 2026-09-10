from __future__ import annotations

import sys
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
    def payload(self):
        return {
            "schema_cronica_ticket": 1,
            "preparacao_id": "turn-neutral-memory",
            "cena": {
                "scene_id": "convivencia",
                "npcs": [],
                "place": None,
                "action": None,
                "tier": None,
                "danger": None,
                "context_tags": [],
                "now_minute": None,
                "approach": {"preparacao": None, "informacao": None, "adequacao": None},
            },
        }

    def social_doc(self):
        social = iniciativa_social.project(
            {"identidade_relacional": "ren", "medidores": {"risco_percebido": 2}},
            relationship_mode="alta_afinidade_alta_confianca",
        )
        return {"resultado": {"dialogo_relacional": {"iniciativa_social": social}}}

    def test_mesmo_carregamento_produz_memoria_e_decisao_no_mesmo_ticket(self):
        reader = FakeReader()
        state = {
            "campanha": {"sessao_atual": 20, "modo_de_cena_atual": "interacao"},
            "localizacao": {"area": "circo_hooft", "ponto_exato": "acampamento"},
        }
        token, ticket_id = core.encode_ticket(self.payload())
        prepared = {"ticket": token, "ticket_id": ticket_id, "fontes_lidas": [], "contrato_conclusao": {}}
        docs = {"nera_vell": self.social_doc()}
        memory_pack = {"versao": memory.VERSION, "modo": "completa", "itens": {}}
        with (
            layer.interlocutors(["nera_vell"]),
            mock.patch.object(memory, "load_scene", return_value=(reader, state, [], None)),
            mock.patch.object(memory, "documents", return_value=docs) as load_docs,
            mock.patch.object(memory, "project", return_value=memory_pack),
        ):
            out = layer.attach(
                Path("/tmp/repo"),
                prepared,
                decode_ticket=core.decode_ticket,
                encode_ticket=core.encode_ticket,
                participants=["nera_vell"],
                max_output_bytes=8192,
            )
        load_docs.assert_called_once()
        decoded = core.decode_ticket(out["ticket"])
        self.assertIn(memory.TICKET_KEY, decoded)
        self.assertIn(initiative.TICKET_KEY, decoded)
        self.assertEqual(out[initiative.PUBLIC_KEY]["interlocutores"], ["nera_vell"])
        self.assertEqual(out[initiative.PUBLIC_KEY]["metricas"]["consultas_adicionais_por_npc"], 0)

    def test_sem_interlocutor_delega_byte_logicamente(self):
        sentinel = {"sem_nv16": True}
        with mock.patch.object(layer, "_BASE_ATTACH", return_value=sentinel) as base:
            result = layer.attach(
                Path("/tmp/repo"),
                {"ticket": "x"},
                decode_ticket=lambda value: value,
                encode_ticket=lambda value: value,
            )
        self.assertIs(result, sentinel)
        base.assert_called_once()


if __name__ == "__main__":
    unittest.main()
