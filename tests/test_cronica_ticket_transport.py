from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import _cronica_turn_core as core
import cronica


class CronicaTicketTransportTest(unittest.TestCase):
    def payload(self):
        return {
            "schema_cronica_ticket": 1,
            "preparacao_id": "scene-prep-transport",
            "cena": {
                "scene_id": "s013-transporte-ticket",
                "npcs": ["sella_rove"],
                "place": None,
                "action": None,
                "tier": None,
                "danger": None,
                "context_tags": [],
                "now_minute": None,
                "approach": {
                    "preparacao": None,
                    "informacao": None,
                    "adequacao": None,
                },
            },
        }

    def wrapped(self, token: str) -> str:
        prefix, digest, body = token.split(".", 2)
        cut_a = max(1, len(body) // 4)
        cut_b = max(cut_a + 1, len(body) // 2)
        cut_c = max(cut_b + 1, (3 * len(body)) // 4)
        transported = (
            body[:cut_a]
            + "\n"
            + body[cut_a:cut_b]
            + " \t "
            + body[cut_b:cut_c]
            + "\r\n"
            + body[cut_c:]
        )
        return f"{prefix}.{digest}.{transported}"

    def test_whitespace_acidental_no_corpo_base64_e_ignorado(self):
        payload = self.payload()
        token, _ = cronica.encode_ticket(payload)
        wrapped = self.wrapped(token)

        self.assertEqual(cronica.decode_ticket(wrapped), payload)
        # O hot path compartilha o mesmo módulo core; a correção precisa valer
        # também quando ele chama core.decode_ticket internamente.
        self.assertEqual(core.decode_ticket(wrapped), payload)

    def test_whitespace_nao_altera_ticket_id(self):
        token, digest = cronica.encode_ticket(self.payload())
        self.assertEqual(cronica.ticket_id(self.wrapped(token)), digest)

    def test_corrupcao_real_do_corpo_continua_falhando(self):
        token, _ = cronica.encode_ticket(self.payload())
        prefix, digest, body = token.split(".", 2)
        index = len(body) // 2
        replacement = "A" if body[index] != "A" else "B"
        corrupted = f"{prefix}.{digest}.{body[:index]}{replacement}{body[index + 1:]}"

        with self.assertRaises(cronica.CronicaError):
            cronica.decode_ticket(corrupted)

    def test_prefixo_e_checksum_nao_sao_normalizados(self):
        token, _ = cronica.encode_ticket(self.payload())
        prefix, digest, body = token.split(".", 2)

        with self.assertRaises(cronica.CronicaError):
            cronica.decode_ticket(f"{prefix} \n.{digest}.{body}")
        with self.assertRaises(cronica.CronicaError):
            cronica.decode_ticket(f"{prefix}.{digest[:10]} \n{digest[10:]}.{body}")


if __name__ == "__main__":
    unittest.main()
