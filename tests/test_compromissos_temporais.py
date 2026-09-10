from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import compromissos
import transacoes


def temporal_record() -> dict:
    return {
        "tipo": "compromisso",
        "resumo": "Jack precisa retornar sobre o próximo passo de Kage",
        "envolvidos": ["jack_mooney"],
        "janela": {
            "inicio": {"data": "18 Eleasis, 1372 DR", "hora": "00:00"},
        },
        "obrigacao_temporal": {
            "schema": 1,
            "estado": "reconciliar",
            "responsavel": "jack_mooney",
            "destinatario": "ren",
            "local_ou_canal": "contato direto no circo",
            "prazo_ou_condicao": {"data": "17 Eleasis, 1372 DR"},
            "resultado_esperado": "registrar novo prazo, retorno ou encerramento explícito",
            "modo_retorno": "conversa direta",
            "fonte_canonica": {
                "arquivo": "estado/relacoes/jack_mooney.yaml",
                "evidencia_literal": "A data de 17 Eleasis já passou.",
            },
            "protecoes": ["não inferir que a apresentação ocorreu"],
        },
    }


class TemporalCommitmentSchemaTest(unittest.TestCase):
    def test_compromisso_legado_permanece_valido(self):
        legacy = {
            "tipo": "compromisso",
            "resumo": "Avisar Nera quando não puder voltar",
            "envolvidos": ["ren", "nera_vell"],
        }
        self.assertEqual(compromissos.validate_record(legacy), legacy)

    def test_obrigacao_temporal_preserva_metadados_causais(self):
        source = temporal_record()
        result = compromissos.validate_record(source)
        self.assertEqual(result["obrigacao_temporal"]["responsavel"], "jack_mooney")
        self.assertEqual(result["obrigacao_temporal"]["destinatario"], "ren")
        self.assertEqual(
            result["obrigacao_temporal"]["prazo_ou_condicao"],
            {"data": "17 Eleasis, 1372 DR"},
        )
        self.assertEqual(source, temporal_record())

    def test_todos_os_campos_temporais_obrigatorios_falham_fechado(self):
        required = {
            "schema",
            "estado",
            "responsavel",
            "destinatario",
            "local_ou_canal",
            "prazo_ou_condicao",
            "resultado_esperado",
            "modo_retorno",
            "fonte_canonica",
        }
        for field in sorted(required):
            with self.subTest(field=field):
                record = temporal_record()
                del record["obrigacao_temporal"][field]
                with self.assertRaises(compromissos.CommitmentError):
                    compromissos.validate_record(record)

    def test_prazo_e_condicao_sao_mutuamente_exclusivos(self):
        record = temporal_record()
        record["obrigacao_temporal"]["prazo_ou_condicao"] = {
            "data": "17 Eleasis, 1372 DR",
            "condicao": "Jack encontrar Ren",
        }
        with self.assertRaises(compromissos.CommitmentError):
            compromissos.validate_record(record)

    def test_fonte_canonica_nao_pode_escapar_do_repo(self):
        record = temporal_record()
        record["obrigacao_temporal"]["fonte_canonica"]["arquivo"] = "../segredo.yaml"
        with self.assertRaises(compromissos.CommitmentError):
            compromissos.validate_record(record)

    def test_delta_temporal_usa_o_mesmo_writer_de_compromissos(self):
        delta = compromissos.create_temporal_delta("retorno_jack", temporal_record())
        self.assertEqual(delta["alvo"], "estado")
        self.assertEqual(delta["caminho"], "compromissos.retorno_jack")
        transacoes.validate_delta(delta)

    def test_runtime_legado_classifica_sem_descartar_metadados(self):
        source = {"retorno_jack": temporal_record()}
        original = copy.deepcopy(source)
        bundle = compromissos.runtime_bundle(source, "21 Eleasis, 1372 DR", "22:00")
        item = bundle["itens"]["retorno_jack"]
        self.assertEqual(item["situacao_temporal"], "devido")
        self.assertEqual(item["obrigacao_temporal"]["estado"], "reconciliar")
        self.assertEqual(source, original)


if __name__ == "__main__":
    unittest.main()
