from __future__ import annotations

from copy import deepcopy
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fronteira_vivacidade as live


class LivenessBoundaryContractTest(unittest.TestCase):
    def window(self):
        return {
            "gatilho": "compressao_longa",
            "inicio": {"data": "21 Eleasis, 1372 DR", "hora": "09:00"},
            "fim": {"data": "21 Eleasis, 1372 DR", "hora": "22:00"},
        }

    def checks(self):
        return [
            {
                "dominio": domain,
                "estado": "consultado",
                "fontes": [f"fixture/{domain}.yaml"],
            }
            for domain in live.REQUIRED_DOMAINS
        ]

    def candidate(
        self,
        candidate_id: str,
        domain: str,
        priority: int,
        *,
        eligible: bool = True,
        reason: str = "Causa vencida e alcançável nesta janela.",
    ):
        return {
            "id": candidate_id,
            "dominio": domain,
            "tipo": "fixture",
            "prioridade": priority,
            "elegivel": eligible,
            "fundamento": reason,
            "origem": f"fixture:{candidate_id}",
        }

    def test_calma_exige_cobertura_de_todos_os_dominios(self):
        checks = self.checks()[:-1]
        with self.assertRaisesRegex(live.LivenessBoundaryError, "cobertura incompleta"):
            live.project(self.window(), [], checks)

    def test_sem_candidata_elegivel_emite_recibo_de_calma_verificavel(self):
        result = live.project(self.window(), [], self.checks())
        self.assertIsNone(result["pressao_primaria"])
        self.assertEqual(result["decisoes"], [])
        self.assertEqual(result["recibo_calma"]["estado"], "calma_justificada")
        self.assertEqual(
            result["recibo_calma"]["motivo"], "nenhuma_pressao_elegivel"
        )
        self.assertEqual(
            [item["dominio"] for item in result["cobertura"]],
            list(live.REQUIRED_DOMAINS),
        )
        self.assertLessEqual(live._size(result), live.MAX_OUTPUT_BYTES)

    def test_escolhe_uma_primaria_e_adia_as_demais_sem_descartar(self):
        candidates = [
            self.candidate("contato-luath", "entregas_contatos", 4),
            self.candidate("compromisso-mapa", "planos_compromissos", 2),
            self.candidate("reacao-sidequest", "operacoes_reacoes", 3),
        ]
        result = live.project(self.window(), candidates, self.checks())
        self.assertEqual(result["pressao_primaria"], "compromisso-mapa")
        decisions = {item["id"]: item["decisao"] for item in result["decisoes"]}
        self.assertEqual(decisions["compromisso-mapa"], "entregue")
        self.assertEqual(decisions["reacao-sidequest"], "adiada")
        self.assertEqual(decisions["contato-luath"], "adiada")
        self.assertEqual(list(decisions.values()).count("entregue"), 1)
        self.assertIsNone(result["recibo_calma"])

    def test_bloqueada_nao_consume_slot_e_preserva_motivo_concreto(self):
        candidates = [
            self.candidate(
                "mensagem-sem-canal",
                "entregas_contatos",
                1,
                eligible=False,
                reason="Não existe canal causal válido para alcançar Ren.",
            ),
            self.candidate("plano-devido", "planos_compromissos", 5),
        ]
        result = live.project(self.window(), candidates, self.checks())
        self.assertEqual(result["pressao_primaria"], "plano-devido")
        blocked = next(
            item for item in result["decisoes"] if item["id"] == "mensagem-sem-canal"
        )
        self.assertEqual(blocked["decisao"], "bloqueada")
        self.assertEqual(
            blocked["motivo"], "Não existe canal causal válido para alcançar Ren."
        )

    def test_candidata_nao_pode_surgir_de_dominio_declarado_nao_configurado(self):
        checks = self.checks()
        checks[0] = {
            "dominio": live.REQUIRED_DOMAINS[0],
            "estado": "nao_configurado",
            "fontes": [],
            "motivo": "Fixture sem esse produtor.",
        }
        candidate = self.candidate("fantasma", live.REQUIRED_DOMAINS[0], 1)
        with self.assertRaisesRegex(live.LivenessBoundaryError, "domínio não configurado"):
            live.project(self.window(), [candidate], checks)

    def test_projecao_e_pura_deterministica_e_nao_muta_entradas(self):
        window = self.window()
        candidates = [
            self.candidate("b", "ecologia_local", 7),
            self.candidate("a", "iniciativas_elenco", 7),
        ]
        checks = self.checks()
        before = deepcopy((window, candidates, checks))
        first = live.project(window, candidates, checks)
        second = live.project(window, list(reversed(candidates)), list(reversed(checks)))
        self.assertEqual(first, second)
        self.assertEqual((window, candidates, checks), before)
        self.assertEqual(
            yaml.safe_dump(first, allow_unicode=True, sort_keys=False),
            yaml.safe_dump(second, allow_unicode=True, sort_keys=False),
        )

    def test_ids_duplicados_e_overflow_falham_fechado(self):
        duplicate = self.candidate("mesma", "ecologia_local", 8)
        with self.assertRaisesRegex(live.LivenessBoundaryError, "IDs de candidatas"):
            live.project(self.window(), [duplicate, deepcopy(duplicate)], self.checks())
        overflow = [
            self.candidate(f"c-{index}", "ecologia_local", 8)
            for index in range(live.MAX_CANDIDATES + 1)
        ]
        with self.assertRaisesRegex(live.LivenessBoundaryError, "até"):
            live.project(self.window(), overflow, self.checks())


if __name__ == "__main__":
    unittest.main()
