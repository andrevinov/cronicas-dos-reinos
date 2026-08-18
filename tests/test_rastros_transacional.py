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
import rastros
import transacoes
import test_consolidacao


class RastrosTransacionaisTest(unittest.TestCase):
    def setUp(self):
        self.base = test_consolidacao.ConsolidacaoTest("test_cena_aplica_recursos_espelha_ficha_e_limpa_buffer")
        self.base.setUp()
        self.repo = self.base.repo
        tempo = self.base._read_yaml("estado/tempo.yaml")
        tempo["schema_tempo"] = 1
        tempo["natureza"] = "tempo_atual"
        self.base._write_yaml("estado/tempo.yaml", tempo)
        self.base._write_yaml(
            "narrador/rastros/index.yaml",
            {
                "schema_indice_rastros": 1,
                "natureza": "reservado",
                "descricao": "Índice ativo de evidências observáveis.",
                "rastros": {},
            },
        )
        source = self.repo / "sessoes/003/fatos-rastro.yaml"
        source.write_text(
            "fato: Kurobane deixou lama azul junto à porta dos fundos.\n",
            encoding="utf-8",
        )
        self.trace_id = rastros.register(self.repo, self.spec())["rastro_id"]

    def tearDown(self):
        self.base.tearDown()

    def spec(self):
        return {
            "nome": "Lama azul junto à cerca",
            "tipo": "fisico",
            "manifestacao": "Há respingos de lama azul seca junto à cerca.",
            "fato_observavel": "Alguém passou recentemente por ali trazendo lama azul nas botas.",
            "localizacao": {
                "escopo": "ponto",
                "cidade": "Ravens Bluff",
                "area": "estrada",
                "ponto": "cerca",
            },
            "acesso": "automatico",
            "persistencia": {
                "disponivel_de": {"data": "7 Eleasis, 1372 DR", "hora": "06:00"},
                "expira_em": None,
            },
            "tags": ["lama", "passagem"],
            "origem": {
                "estatuto": "fato_canonico",
                "fonte": "sessoes/003/fatos-rastro.yaml",
                "evidencia": "Kurobane deixou lama azul junto à porta dos fundos.",
                "referencia": "kurobane_jinzaburo",
            },
        }

    def read_yaml(self, rel):
        return yaml.safe_load((self.repo / rel).read_text(encoding="utf-8"))

    def prepared(self):
        return rastros.prepare_discovery(self.repo, self.trace_id)

    def test_preparar_descoberta_entrega_par_atomico(self):
        result = self.prepared()
        self.assertEqual(len(result["deltas_transacionais"]), 2)
        knowledge, trace = result["deltas_transacionais"]
        self.assertEqual(knowledge["alvo"], "conhecimento")
        self.assertEqual(trace["alvo"], f"rastro:{self.trace_id}")
        self.assertEqual(trace["visibilidade"], "narrador")
        self.assertEqual(trace["valor"], "descoberto")

    def test_par_incompleto_e_recusado_antes_das_duas_escritas(self):
        prepared = self.prepared()
        before_pending = (self.repo / "runtime/eventos-pendentes.jsonl").read_bytes()
        before_transcript = (self.repo / "sessoes/003/transcricao.md").read_bytes()
        with self.assertRaises(transacoes.TransactionError):
            self.base.register("tx-incompleta", [prepared["deltas_transacionais"][0]])
        self.assertEqual(before_pending, (self.repo / "runtime/eventos-pendentes.jsonl").read_bytes())
        self.assertEqual(before_transcript, (self.repo / "sessoes/003/transcricao.md").read_bytes())

    def test_descobrir_usa_writer_normal_e_ainda_nao_muta_canone(self):
        result = rastros.discover(
            self.repo,
            self.trace_id,
            {
                "id": "tx-wrapper-rastro",
                "jogador": "Ren observa a lama junto à cerca.",
                "narracao": "A marca é recente, mas não identifica quem passou por ali.",
                "resumo": "Ren observa um rastro de lama azul.",
                "modo": "exploração",
            },
        )
        self.assertEqual(result["turno"]["deltas"], 2)
        self.assertTrue(result["turno"]["evento_escrito"])
        self.assertTrue(result["turno"]["transcricao_escrita"])
        self.assertEqual(
            self.read_yaml("narrador/rastros/index.yaml")["rastros"][self.trace_id]["estado"],
            "ativo",
        )
        self.assertFalse((self.repo / "personagens/jogador/conhecimento/incrementais/sessao-003").exists())

    def test_consolidacao_instala_conhecimento_e_estado_do_rastro_no_mesmo_lote(self):
        prepared = self.prepared()
        self.base.register(
            "tx-rastro",
            prepared["deltas_transacionais"],
            summary="Ren descobre um rastro de lama azul.",
            mode="exploração",
        )
        result = consolidar.consolidate(self.repo, "cena")
        self.assertFalse(result["recuperada"])

        index = self.read_yaml("narrador/rastros/index.yaml")
        self.assertEqual(index["rastros"][self.trace_id]["estado"], "descoberto")
        self.assertEqual(rastros.candidates(self.repo)["rastros"], [])

        fragment = self.repo / "personagens/jogador/conhecimento/incrementais/sessao-003/tx-tx-rastro.md"
        text = fragment.read_text(encoding="utf-8")
        self.assertIn("Alguém passou recentemente por ali trazendo lama azul nas botas.", text)
        self.assertNotIn("Kurobane deixou lama azul", text)

        ledger = consolidar.load_ledger(self.repo, 3)
        batch = ledger[-1]
        self.assertEqual(batch["rastros_descobertos"], [self.trace_id])
        self.assertIn("narrador/rastros/index.yaml", batch["arquivos_afetados"])
        self.assertEqual(batch["deltas"], 2)

    def test_queda_no_meio_recupera_conhecimento_e_rastro_do_mesmo_journal(self):
        prepared = self.prepared()
        self.base.register(
            "tx-rastro-crash",
            prepared["deltas_transacionais"],
            summary="Ren descobre o rastro antes de uma queda simulada.",
        )
        with self.assertRaises(consolidar.ConsolidationError):
            consolidar.consolidate(self.repo, "cena", fail_after=1)
        self.assertTrue((self.repo / consolidar.JOURNAL_PATH).is_file())

        recovered = consolidar.consolidate(self.repo, "cena")
        self.assertTrue(recovered["recuperada"])
        self.assertFalse((self.repo / consolidar.JOURNAL_PATH).exists())
        self.assertEqual(
            self.read_yaml("narrador/rastros/index.yaml")["rastros"][self.trace_id]["estado"],
            "descoberto",
        )
        fragment = self.repo / "personagens/jogador/conhecimento/incrementais/sessao-003/tx-tx-rastro-crash.md"
        self.assertTrue(fragment.is_file())
        self.assertIn(
            "Alguém passou recentemente por ali trazendo lama azul nas botas.",
            fragment.read_text(encoding="utf-8"),
        )
        ledger = consolidar.load_ledger(self.repo, 3)
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["rastros_descobertos"], [self.trace_id])

    def test_conhecimento_mais_forte_que_o_rastro_falha_antes_do_stage(self):
        prepared = self.prepared()
        pair = prepared["deltas_transacionais"]
        pair[0] = dict(pair[0])
        pair[0]["valor"] = dict(pair[0]["valor"])
        pair[0]["valor"]["texto"] = "Kurobane esteve aqui e deixou lama azul."
        self.base.register("tx-vazamento", pair, summary="Tentativa de vazamento.")

        before_index = (self.repo / "narrador/rastros/index.yaml").read_bytes()
        before_knowledge = (self.repo / "personagens/jogador/conhecimento/index.yaml").read_bytes()
        with self.assertRaises(consolidar.ConsolidationError):
            consolidar.consolidate(self.repo, "cena")
        self.assertEqual(before_index, (self.repo / "narrador/rastros/index.yaml").read_bytes())
        self.assertEqual(before_knowledge, (self.repo / "personagens/jogador/conhecimento/index.yaml").read_bytes())
        self.assertFalse((self.repo / consolidar.JOURNAL_PATH).exists())

    def test_retry_de_registro_apos_consolidacao_nao_redescobre_rastro(self):
        prepared = self.prepared()
        self.base.register("tx-rastro-retry", prepared["deltas_transacionais"], summary="Descoberta única.")
        consolidar.consolidate(self.repo, "cena")
        self.assertEqual(
            self.read_yaml("narrador/rastros/index.yaml")["rastros"][self.trace_id]["estado"],
            "descoberto",
        )
        again = consolidar.consolidate(self.repo, "cena")
        self.assertTrue(again["sem_pendencias"])
        self.assertEqual(len(consolidar.load_ledger(self.repo, 3)), 1)


if __name__ == "__main__":
    unittest.main()
