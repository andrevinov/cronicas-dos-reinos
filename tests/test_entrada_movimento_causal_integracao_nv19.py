from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest import mock

TOOLS = Path(__file__).resolve().parents[1] / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import contatos_sociais
import cronica_entradas_causais
import permanencia_espacial
import planos_personagens as plans


class EntryLocalPermanenceCompositionTest(unittest.TestCase):
    def test_sem_plano_de_entrada_preserva_preparo_nv15_sem_consulta_dirigida(self):
        repo = Path("/fixture-sem-nv19")
        base = {
            "publico": {"local_id": "Circo", "fontes_lidas": ["narrador/permanencia-espacial/estado.yaml"]},
            "ticket": {"avaliacao_id": "janela-x"},
        }
        with mock.patch.object(permanencia_espacial, "_BASE_PREPARE_NV15", return_value=deepcopy(base)), \
             mock.patch.object(permanencia_espacial, "_has_entry_plans", return_value=False), \
             mock.patch.object(plans, "project_local_entry") as projection:
            result = permanencia_espacial.prepare(repo, scene_id="cena")
        projection.assert_not_called()
        self.assertEqual(result, base)

    def test_com_plano_dirigido_anexa_uma_unica_entrada_sem_materializar(self):
        repo = Path("/fixture-nv19")
        base = {
            "publico": {"local_id": "Circo", "fontes_lidas": ["fonte-base.yaml"]},
            "ticket": {"avaliacao_id": "janela-x"},
        }
        entry = {
            "tipo": plans.ENTRY_TYPE,
            "plano_id": "visita",
            "pendencia_id": "mundo-aaaaaaaaaaaaaaaa",
            "agente": {"tipo": "leve", "id": "visitante"},
            "fase": "partida_devida",
            "origem": "Porto",
            "destino": "Circo",
            "janela": {},
            "duracao_esperada_minutos": 60,
            "motivo_presenca": "entregar notícia",
            "bloqueios": [],
            "fontes_lidas": ["estado/npcs/visitante.yaml"],
            "regra": "uma entrada",
        }
        with mock.patch.object(permanencia_espacial, "_BASE_PREPARE_NV15", return_value=deepcopy(base)), \
             mock.patch.object(permanencia_espacial, "_has_entry_plans", return_value=True), \
             mock.patch.object(plans, "project_local_entry", return_value=deepcopy(entry)) as projection:
            result = permanencia_espacial.prepare(repo, scene_id="cena")
        projection.assert_called_once_with(repo, "Circo")
        self.assertEqual(result["publico"]["entrada_causal"]["plano_id"], "visita")
        self.assertEqual(result["publico"]["fontes_lidas"], ["fonte-base.yaml", "estado/npcs/visitante.yaml"])


class EntryLocalCronicaCompositionTest(unittest.TestCase):
    def test_cronica_expoe_candidato_sem_converter_em_elenco_ou_fato(self):
        prepared = {
            "fase": "preparacao",
            "ids": {"entradas_contextuais": [], "npcs": []},
            "gates": [],
            "permanencia_espacial": {
                "entrada_causal": {
                    "plano_id": "visita",
                    "pendencia_id": "mundo-aaaaaaaaaaaaaaaa",
                    "agente": {"tipo": "leve", "id": "visitante"},
                    "fase": "chegada_devida",
                    "bloqueios": [],
                }
            },
            "proximo_passo": {},
        }
        with mock.patch.object(cronica_entradas_causais, "_BASE_PREPARE", return_value=deepcopy(prepared)):
            result = cronica_entradas_causais.prepare(Path("/fixture"), scene_id="cena")
        self.assertEqual(result["ids"]["entradas_contextuais"], ["visitante"])
        self.assertEqual(result["ids"]["npcs"], [])
        self.assertEqual(result["entrada_local"]["fase"], "chegada_devida")
        self.assertIn("causal_character_entry", result["sistemas_narrativos"])
        gate = next(g for g in result["gates"] if g["tipo"] == "entrada_local")
        self.assertEqual(gate["plano_id"], "visita")
        self.assertEqual(prepared["ids"]["entradas_contextuais"], [])


class EntryLocalMessengerCompositionTest(unittest.TestCase):
    def test_emissario_reutiliza_presence_at_sem_subsistema_paralelo(self):
        view = object()
        with mock.patch.object(plans, "presence_at", return_value=True) as present:
            self.assertTrue(contatos_sociais._present(view, "mensageiro", "Circo"))
        present.assert_called_once_with(view, "mensageiro", "Circo")

    def test_presenca_expirada_bloqueia_emissario(self):
        view = object()
        with mock.patch.object(plans, "presence_at", return_value=False):
            self.assertFalse(contatos_sociais._present(view, "mensageiro", "Circo"))


class EntryLocalBudgetContractTest(unittest.TestCase):
    def test_reusa_teto_de_planos_e_projeta_so_um_ator(self):
        self.assertEqual(plans.MAX_PLANS, 8)
        self.assertEqual(plans.MAX_ENTRY_PROJECTION_BYTES, 3072)

    def test_modulo_nv19_nao_importa_rng_scheduler_ou_catalogo_de_populacao(self):
        source = Path(plans.__file__).read_text(encoding="utf-8")
        self.assertNotIn("import random", source)
        self.assertNotIn("import sched", source)
        self.assertNotIn("apscheduler", source.lower())
        body = source[source.index("def project_local_entry"):]
        self.assertNotIn("estado/npcs/index.yaml", body)
        self.assertNotIn("narrador/agentes/index.yaml", body)


if __name__ == "__main__":
    unittest.main()
