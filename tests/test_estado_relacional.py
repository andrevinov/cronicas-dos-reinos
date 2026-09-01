from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import consolidar
import contexto
import estado_relacional
import transacoes


class RelationshipStateRepositoryTest(unittest.TestCase):
    def test_repositorio_real_cobre_todas_as_relacoes(self):
        self.assertEqual(estado_relacional.check(ROOT), [])
        rel = yaml.safe_load((ROOT / estado_relacional.REL_INDEX).read_text(encoding="utf-8"))
        npc = yaml.safe_load((ROOT / estado_relacional.NPC_INDEX).read_text(encoding="utf-8"))
        relations = rel["relacoes"]
        npcs = npc["npcs"]
        self.assertEqual(rel["quantidade"], len(relations))
        self.assertTrue(set(relations) <= set(npcs))
        self.assertEqual(npc["quantidade"], len(npcs))
        self.assertGreaterEqual(len(npcs), len(relations))

    def test_estado_existente_de_jack_e_reutilizado_sem_migracao_semantica(self):
        state = estado_relacional.lookup(ROOT, "jack_mooney")
        self.assertTrue(state["encontrado"])
        self.assertEqual(state["afinidade"], 5)
        self.assertEqual(state["afinidade_faixa"], "neutra")
        self.assertEqual(state["confianca"], 7)
        self.assertEqual(state["confianca_faixa"], "positiva")
        self.assertEqual(state["risco_percebido"], 7)

    def test_sella_da_galeria_e_relacao_com_shinta_sem_revelar_ren(self):
        state = estado_relacional.lookup(ROOT, "sella_conferente_galeria")
        self.assertEqual(state["afinidade"], 6)
        self.assertEqual(state["confianca"], 6)
        self.assertEqual(state["identidade_relacional"], "shinta")

    def test_desconhecido_permanece_desconhecido(self):
        state = estado_relacional.lookup(ROOT, "rusk_cinza")
        self.assertIsNone(state["afinidade"])
        self.assertEqual(state["afinidade_faixa"], "desconhecida")
        self.assertEqual(state["confianca"], 1)
        self.assertIsNone(state["risco_percebido"])

    def test_contexto_npc_continua_mesma_porta_sem_ler_contrato_extra(self):
        data = contexto.command_npc(ROOT, "sella_conferente_galeria")
        self.assertTrue(data["resultado"]["encontrado"])
        meters = data["resultado"]["medidores"]["dados"]["medidores"]
        self.assertEqual(meters["vinculo"], 6)
        self.assertEqual(meters["confianca"], 6)
        self.assertIn("estado/npcs/sella_conferente_galeria.yaml", data["fontes"])
        self.assertIn("estado/relacoes/sella_conferente_galeria.yaml", data["fontes"])
        self.assertNotIn(estado_relacional.CONTRACT.as_posix(), data["fontes"])


class RelationshipStateDeltaTest(unittest.TestCase):
    def fact(self) -> str:
        return "Jack viu Ren cumprir um compromisso importante sem expor o circo."

    def delta(self, **overrides):
        value = {
            "alvo": "npc:jack_mooney",
            "op": "inc",
            "caminho": "medidores.confianca",
            "valor": 1,
            "fato_canonico": self.fact(),
            "fonte": "sessoes/013/transcricao.md",
        }
        value.update(overrides)
        return value

    def test_delta_incremental_com_evidencia_passa_schema_transacional(self):
        delta = self.delta()
        self.assertIs(transacoes.validate_delta(delta), delta)
        record = transacoes.build_pending_record(
            {"narracao": "Jack reconhece o fato sem transformar a cena em sermão.", "resumo": "Confiança de Jack muda por fato persistente.", "deltas": [delta]},
            13,
        )
        stored = record["deltas"][0]
        self.assertEqual(stored["fato_canonico"], self.fact())
        self.assertEqual(stored["fonte"], "sessoes/013/transcricao.md")

    def test_set_comum_salto_e_falta_de_evidencia_falham(self):
        invalid = [
            self.delta(op="set", valor=8),
            self.delta(valor=2),
            self.delta(fato_canonico="curto"),
            self.delta(fonte=""),
        ]
        for delta in invalid:
            with self.subTest(delta=delta):
                with self.assertRaises(transacoes.TransactionError):
                    transacoes.validate_delta(delta)

    def test_lote_valida_incremento_e_inicializacao_de_null(self):
        jack = {"deltas": [self.delta()]}
        self.assertEqual(estado_relacional.validate_batch(ROOT, [jack]), 1)
        init = {
            "deltas": [
                {
                    "alvo": "npc:rusk_cinza",
                    "op": "set",
                    "caminho": "medidores.vinculo",
                    "valor": 3,
                    "inicializacao": True,
                    "fato_canonico": "Rusk finalmente encontra Ren e demonstra hostilidade cautelosa de forma inequívoca.",
                    "fonte": "sessoes/013/transcricao.md",
                }
            ]
        }
        self.assertEqual(estado_relacional.validate_batch(ROOT, [init]), 1)

    def test_lote_recusa_overflow_incremento_de_null_e_reinicializacao(self):
        overflow = [
            {"deltas": [self.delta(alvo="npc:nera_vell", caminho="medidores.vinculo")]}
            for _ in range(3)
        ]
        with self.assertRaises(estado_relacional.RelationshipStateError):
            estado_relacional.validate_batch(ROOT, overflow)

        null_inc = {
            "deltas": [
                self.delta(alvo="npc:rusk_cinza", caminho="medidores.vinculo")
            ]
        }
        with self.assertRaises(estado_relacional.RelationshipStateError):
            estado_relacional.validate_batch(ROOT, [null_inc])

        reinit = {
            "deltas": [
                self.delta(op="set", valor=8, inicializacao=True)
            ]
        }
        with self.assertRaises(estado_relacional.RelationshipStateError):
            estado_relacional.validate_batch(ROOT, [reinit])

    def test_consolidacao_recusa_fragmento_staged_fora_da_escala(self):
        invalid = {
            "schema_npc": 2,
            "natureza": "medidores_npc_atuais",
            "id": "jack_mooney",
            "npc": {
                "medidores": {"vinculo": 5, "confianca": 11, "risco_percebido": 7}
            },
        }
        plan = {
            "outputs": {
                "estado/npcs/jack_mooney.yaml": yaml.safe_dump(
                    invalid, allow_unicode=True, sort_keys=False
                ).encode("utf-8")
            }
        }
        with self.assertRaises(consolidar.ConsolidationError):
            consolidar._validate_relationship_outputs(plan)


class RelationshipStateBudgetTest(unittest.TestCase):
    def test_contrato_congela_estado_sem_infra_paralela(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/npc-relationship-state-v1-orcamento.yaml").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(contract["schema_orcamento_estado_relacional"], 1)
        limits = contract["limites"]
        self.assertEqual(limits["eixos_relacionais_centrais"], 2)
        self.assertEqual(limits["variacao_normal_maxima_por_fato"], 1)
        self.assertEqual(limits["max_chamadas_extras_por_turno"], 0)
        self.assertEqual(limits["max_schedulers_novos"], 0)
        self.assertEqual(limits["max_estados_relacionais_paralelos"], 0)
        self.assertEqual(limits["max_indice_npcs_bytes"], estado_relacional.MAX_INDEX_BYTES)
        self.assertEqual(limits["max_fragmento_npc_bytes"], estado_relacional.MAX_FRAGMENT_BYTES)
        self.assertTrue(all(contract["invariantes"].values()))
        self.assertLessEqual((ROOT / estado_relacional.NPC_INDEX).stat().st_size, estado_relacional.MAX_INDEX_BYTES)


if __name__ == "__main__":
    unittest.main()
