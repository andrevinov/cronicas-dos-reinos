from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica
import cronica_hotpath as hot


class CronicaUrbanTransitTest(unittest.TestCase):
    def _planned(self, *, result: str = "rotina") -> dict:
        public = {
            "ok": True,
            "tipo": "microevento_transito_urbano",
            "escopo": "ravens_bluff",
            "cena_id": "transit-test",
            "resultado": result,
            "ficha_ocorrencia": "rotina_01",
            "reutilizado": False,
            "cartas_elegiveis": 2,
            "pressao_ravens_bluff": {
                "max_nivel": 0,
                "frentes_ativas": 0,
                "frentes": [],
                "regra": "teste",
            },
            "fontes_lidas": [
                "narrador/microeventos-locais/index.yaml",
                "narrador/microeventos-locais/estado.yaml",
                "narrador/arcos/parte_1/pressao-ravens-bluff.yaml",
                "narrador/arcos/parte_1/estado-pressao-ravens-bluff.yaml",
            ],
            "regra": "teste",
        }
        return {
            "publico": public,
            "fingerprint": "a" * 64,
            "estado_planejado": {},
            "alterou": True,
            "confirmado": False,
        }

    def _ticket(self) -> str:
        with mock.patch.object(hot.microeventos_transito, "plan", return_value=self._planned()):
            return hot.prepare(
                ROOT,
                scene_id="transit-test",
                urban_transit="ravens_bluff",
            )["ticket"]

    def test_parser_publico_expoe_flag_na_mesma_porta_preparar(self):
        args = cronica.build_parser().parse_args(
            [
                "preparar",
                "--cena-id",
                "move-1",
                "--transito-urbano",
                "ravens_bluff",
                "--sem-oportunidade-sidequest",
            ]
        )
        self.assertEqual(args.cmd, "preparar")
        self.assertEqual(args.transito_urbano, "ravens_bluff")

    def test_preparar_transito_nao_chama_endpoint_de_cena(self):
        planned = self._planned()
        with mock.patch.object(hot.microeventos_transito, "plan", return_value=planned) as plan, mock.patch.object(
            hot.core, "prepare"
        ) as scene_prepare:
            result = hot.prepare(
                ROOT,
                scene_id="transit-test",
                urban_transit="ravens_bluff",
            )
        plan.assert_called_once_with(ROOT, scene_id="transit-test")
        scene_prepare.assert_not_called()
        self.assertFalse(result["reativa"])
        self.assertEqual(result["ids"]["transito_urbano"], "ravens_bluff")
        self.assertEqual(result["gates"][0]["tipo"], "transito_urbano")
        payload = hot.core.decode_ticket(result["ticket"])
        self.assertTrue(hot._is_transit_payload(payload))
        self.assertEqual(payload["transito_urbano"]["fingerprint"], "a" * 64)

    def test_transito_recusa_gatilho_reativo_no_mesmo_ticket(self):
        with mock.patch.object(hot.microeventos_transito, "plan") as plan:
            with self.assertRaises(hot.core.CronicaError):
                hot.prepare(
                    ROOT,
                    scene_id="move-and-enter",
                    place="Galeria dos Escribas",
                    action="entrar",
                    tier=1,
                    danger="baixa",
                    urban_transit="ravens_bluff",
                )
        plan.assert_not_called()

    def test_preparacao_real_fica_dentro_do_teto_da_task21(self):
        result = hot.prepare(
            ROOT,
            scene_id="transit-budget-real",
            urban_transit="ravens_bluff",
        )
        rendered = yaml.safe_dump(result, allow_unicode=True, sort_keys=False).encode("utf-8")
        self.assertLessEqual(len(rendered), hot.core.MAX_PREP_OUTPUT_BYTES)
        self.assertLessEqual(len(result["fontes_lidas"]), 4)

    def test_concluir_ordena_preflight_confirmacao_e_registro(self):
        token = self._ticket()
        order: list[str] = []
        preview = {"id": "s013-transit", "checkpoint_previsto": None}
        confirmed = {**self._planned()["publico"], "mutacoes_aplicadas": True}
        registered = {
            "id": "s013-transit",
            "sessao": 13,
            "deltas": [],
            "transcricao_escrita": True,
            "evento_escrito": True,
            "reparo_parcial": False,
            "ja_registrada": False,
            "consolidada": False,
            "checkpoint_mundo": None,
            "avisos": [],
        }

        def preflight(_repo, _transaction):
            order.append("preflight")
            return preview

        def confirm(_repo, _payload):
            order.append("confirmar_transito")
            return confirmed

        def register(_repo, _transaction):
            order.append("registrar")
            return registered

        with mock.patch.object(hot, "_confirm_transit", side_effect=confirm), mock.patch.object(
            hot.turno, "register_transaction", side_effect=register
        ), mock.patch.object(hot.rodape_turno, "build_safe", return_value="rodape"):
            result = hot.conclude(
                ROOT,
                token,
                {"jogador": "x", "narracao": "y", "resumo": "z", "modo": "exploração", "deltas": []},
                preflight=preflight,
            )
        self.assertEqual(order, ["preflight", "confirmar_transito", "registrar"])
        self.assertEqual(result["fase"], "concluida")
        self.assertEqual(result["transito_urbano"]["escopo"], "ravens_bluff")

    def test_reparo_pos_confirmacao_nao_revalida_nem_reconsome_transito(self):
        token = self._ticket()
        registered = {
            "id": "s013-repair",
            "sessao": 13,
            "deltas": [],
            "transcricao_escrita": True,
            "evento_escrito": True,
            "reparo_parcial": True,
            "ja_registrada": False,
            "consolidada": False,
            "checkpoint_mundo": None,
            "avisos": [],
        }
        with mock.patch.object(hot, "_revalidate_transit") as revalidate, mock.patch.object(
            hot, "_confirm_transit"
        ) as confirm, mock.patch.object(
            hot.turno, "register_transaction", return_value=registered
        ), mock.patch.object(hot.rodape_turno, "build_safe", return_value="rodape"):
            result = hot.register(
                ROOT,
                token,
                {"qualquer": "payload já validado pelo fluxo real"},
                revalidate_ticket=False,
            )
        revalidate.assert_not_called()
        confirm.assert_not_called()
        self.assertEqual(result["transacao"]["id"], "s013-repair")

    def test_fluxos_sem_flag_permanecem_neutro_ou_reativo(self):
        neutral = hot.prepare(ROOT, scene_id="plain-neutral")
        self.assertFalse(neutral["reativa"])
        self.assertNotIn("transito_urbano", neutral)
        with mock.patch.object(hot.core, "prepare", return_value={
            "schema_cronica_turno": 1,
            "fase": "preparacao",
            "ticket_id": "x",
            "ticket": "crn1.x.fake",
            "ids": {},
            "filtros": [],
            "disponibilidade": {},
            "gates": [],
            "modificadores": [],
            "proximo_passo": {},
            "fontes_lidas": [],
        }) as prepare:
            reactive = hot.prepare(
                ROOT,
                scene_id="plain-reactive",
                context_tags=["assunto:documentos"],
            )
        prepare.assert_called_once()
        self.assertTrue(reactive["reativa"])


if __name__ == "__main__":
    unittest.main()
