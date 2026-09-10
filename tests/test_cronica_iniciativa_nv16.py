from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).parents[1] / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import cronica
import cronica_iniciativa as layer
import iniciativa_elenco as initiative


class CronicaInitiativeCompositionTest(unittest.TestCase):
    def test_parser_expoe_subconjunto_repetivel_de_interlocutores(self):
        args = cronica.build_parser().parse_args([
            "preparar", "--cena-id", "convivencia",
            "--sem-oportunidade-sidequest",
            "--participante", "nera_vell",
            "--interlocutor", "nera_vell",
            "--interlocutor", "silva_elkwood",
        ])
        self.assertEqual(args.interlocutor, ["nera_vell", "silva_elkwood"])
        self.assertEqual(args.participante, ["nera_vell"])

    def test_sem_interlocutor_delega_preparo_anterior_sem_camada(self):
        sentinel = {"fase": "preparacao"}
        with mock.patch.object(layer, "_BASE_PREPARE", return_value=sentinel) as base:
            result = cronica.prepare(Path("/tmp/repo"), scene_id="cena", sidequest_signal=None)
        self.assertIs(result, sentinel)
        base.assert_called_once()

    def test_modulo_publico_preserva_identidade_para_monkeypatches(self):
        self.assertIs(cronica, layer._base)
        marker = object()
        with mock.patch.object(cronica, "_preflight_registration", marker):
            self.assertIs(layer._base._preflight_registration, marker)

    def _automatic_ticket(self):
        proposal = initiative._digest(["nera_vell", "ausente"])
        decision = "ini-" + initiative._digest(["cena-x", "nera_vell", proposal])[:20]
        meta = {
            "schema": 1,
            "janela_id": "cena-x",
            "janela_tipo": "cena",
            "cena_id": "cena",
            "selecionada": None,
            "itens": [{
                "decisao_id": decision,
                "npc_id": "nera_vell",
                "presenca": "ausente",
                "proposta_digest": proposal,
                "requer_decisao": False,
                "resultado_automatico": "nao_elegivel",
                "motivo_automatico": "ausencia",
                "pressao_superior": None,
                "exige_motivo": False,
                "reutilizado": False,
            }],
        }
        payload = {
            "schema_cronica_ticket": 1,
            "preparacao_id": "turn-neutral-x",
            "cena": {"scene_id": "cena", "npcs": [], "place": None, "action": None,
                     "tier": None, "danger": None, "context_tags": [], "now_minute": None,
                     "approach": {"preparacao": None, "informacao": None, "adequacao": None}},
            initiative.TICKET_KEY: meta,
        }
        return layer._core.encode_ticket(payload)[0]

    def test_concluir_remove_envelope_nv16_antes_do_writer_e_instala_depois(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            token = self._automatic_ticket()
            tx = {"jogador": "Ren observa.", "narracao": "A conversa não se abre.",
                  "resumo": "Sem abertura social.", "modo": "interação", "deltas": []}
            captured = {}

            def base(_repo, base_token, writer_tx):
                captured["payload"] = layer._base.decode_ticket(base_token)
                captured["tx"] = writer_tx
                return {"fase": "concluida", "ticket_id": "base",
                        "transacao": {"id": "tx-nv16"}, "sistemas_narrativos": []}

            with mock.patch.object(layer, "_BASE_CONCLUDE", side_effect=base):
                result = cronica.conclude(repo, token, tx)
            self.assertNotIn(initiative.TICKET_KEY, captured["payload"])
            self.assertNotIn(initiative.TRANSACTION_KEY, captured["tx"])
            self.assertEqual(result[initiative.PUBLIC_KEY]["resultados"][0]["resultado"], "nao_elegivel")
            self.assertIn("present_cast_initiative", result["sistemas_narrativos"])

    def test_confirmar_e_registrar_separados_rejeitam_ticket_nv16(self):
        token = self._automatic_ticket()
        with self.assertRaisesRegex(cronica.CronicaError, "NV16"):
            cronica.confirm(Path("/tmp/repo"), token)
        with self.assertRaisesRegex(cronica.CronicaError, "NV16"):
            cronica.register(Path("/tmp/repo"), token, {})

    def test_bloco_sem_ticket_e_recusado_antes_do_fluxo_base(self):
        token, _ = layer._core.encode_ticket({
            "schema_cronica_ticket": 1,
            "preparacao_id": "turn-neutral-x",
            "cena": {"scene_id": "cena", "npcs": [], "place": None, "action": None,
                     "tier": None, "danger": None, "context_tags": [], "now_minute": None,
                     "approach": {"preparacao": None, "informacao": None, "adequacao": None}},
        })
        with mock.patch.object(layer, "_BASE_CONCLUDE") as base:
            with self.assertRaisesRegex(cronica.CronicaError, "autorização"):
                cronica.conclude(Path("/tmp/repo"), token, {initiative.TRANSACTION_KEY: {}})
        base.assert_not_called()


if __name__ == "__main__":
    unittest.main()
