from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import compromissos
import transacoes

RUNTIME_PATH = TOOLS / "gerar-runtime.py"
spec = importlib.util.spec_from_file_location("gerar_runtime_compromissos", RUNTIME_PATH)
gerar_runtime = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(gerar_runtime)


def appointment(summary: str = "Encontrar Sella no mercador de cal") -> dict:
    return {
        "tipo": "encontro",
        "resumo": summary,
        "envolvidos": ["ren", "sella_rove"],
        "local_id": "mercador_cal_rua_cal",
        "janela": {
            "inicio": {"data": "14 Eleasis, 1372 DR", "hora": "21:20"},
            "fim": {"data": "14 Eleasis, 1372 DR", "hora": "21:50"},
            "descricao": "vinte minutos depois do segundo sino; partir após meia hora",
        },
    }


class CommitmentSchemaTest(unittest.TestCase):
    def test_criacao_usa_um_unico_delta_de_estado(self):
        delta = compromissos.create_delta("resposta_sella", appointment())
        self.assertEqual(delta["alvo"], "estado")
        self.assertEqual(delta["op"], "set")
        self.assertEqual(delta["caminho"], "compromissos.resposta_sella")
        self.assertEqual(delta["valor"]["tipo"], "encontro")
        transacoes.validate_delta(delta)

    def test_subcampo_nao_pode_ser_editado_isoladamente(self):
        with self.assertRaises(transacoes.TransactionError):
            transacoes.validate_delta(
                {
                    "alvo": "estado",
                    "op": "set",
                    "caminho": "compromissos.resposta_sella.resumo",
                    "valor": "texto",
                }
            )

    def test_janela_invertida_falha_antes_de_virar_registro_pendente(self):
        value = appointment()
        value["janela"]["fim"] = {"data": "14 Eleasis, 1372 DR", "hora": "21:00"}
        with self.assertRaises(transacoes.TransactionError):
            transacoes.build_pending_record(
                {
                    "id": "tx-compromisso-invalido",
                    "jogador": "Ren combina o encontro.",
                    "narracao": "O horário fica acertado.",
                    "resumo": "Encontro combinado.",
                    "deltas": [
                        {
                            "alvo": "estado",
                            "op": "set",
                            "caminho": "compromissos.resposta_sella",
                            "valor": value,
                        }
                    ],
                },
                12,
            )

    def test_encontro_exige_janela_mas_compromisso_pode_ser_sem_data(self):
        with self.assertRaises(compromissos.CommitmentError):
            compromissos.validate_record({"tipo": "encontro", "resumo": "Encontrar alguém"})
        result = compromissos.validate_record(
            {"tipo": "compromisso", "resumo": "Avisar Nera quando não puder voltar", "envolvidos": ["ren", "nera_vell"]}
        )
        self.assertNotIn("janela", result)


class CommitmentRuntimeTest(unittest.TestCase):
    def test_situacao_temporal_e_derivada_sem_mutar_registro(self):
        source = {"resposta_sella": appointment()}
        original = copy.deepcopy(source)
        before = compromissos.runtime_bundle(source, "14 Eleasis, 1372 DR", "21:00")
        during = compromissos.runtime_bundle(source, "14 Eleasis, 1372 DR", "21:30")
        after = compromissos.runtime_bundle(source, "14 Eleasis, 1372 DR", "22:00")
        self.assertEqual(before["itens"]["resposta_sella"]["situacao_temporal"], "futuro")
        self.assertEqual(during["itens"]["resposta_sella"]["situacao_temporal"], "em_janela")
        self.assertEqual(after["itens"]["resposta_sella"]["situacao_temporal"], "janela_encerrada")
        self.assertEqual(source, original)

    def test_pacote_quente_expoe_quatro_e_resto_so_por_id(self):
        records = {
            f"encontro_{index}": {
                "tipo": "encontro",
                "resumo": f"Encontro {index}",
                "janela": {"inicio": {"data": f"{15 + index} Eleasis, 1372 DR", "hora": "09:00"}},
            }
            for index in range(6)
        }
        bundle = compromissos.runtime_bundle(records, "14 Eleasis, 1372 DR", "09:00", limit=4)
        self.assertEqual(bundle["quantidade"], 6)
        self.assertEqual(len(bundle["itens"]), 4)
        self.assertEqual(len(bundle["omitidos"]), 2)

    def test_delta_pendente_aparece_no_l1_sem_mudar_cena(self):
        context = {
            "sessao": {"numero": 12},
            "tempo": {"data": "14 Eleasis, 1372 DR", "hora_aproximada": "21:30"},
        }
        scene = {"sessao": 12, "tempo": {"data": "14 Eleasis, 1372 DR", "hora_aproximada": "21:30"}}
        record = transacoes.build_pending_record(
            {
                "id": "tx-compromisso",
                "jogador": "Ren combina o encontro.",
                "narracao": "Sella confirma a janela.",
                "resumo": "Encontro com Sella combinado.",
                "deltas": [compromissos.create_delta("resposta_sella", appointment())],
            },
            12,
        )
        effective, effective_scene, applied = transacoes.overlay_runtime(context, scene, [record])
        self.assertGreaterEqual(applied, 1)
        self.assertEqual(
            effective["compromissos"]["itens"]["resposta_sella"]["situacao_temporal"],
            "em_janela",
        )
        self.assertNotIn("compromissos", effective_scene)
        self.assertNotIn("compromissos", context)

    def test_remove_pendente_fecha_estado_corrente_sem_estado_terminal(self):
        context = {
            "sessao": {"numero": 12},
            "tempo": {"data": "14 Eleasis, 1372 DR", "hora_aproximada": "21:30"},
            "compromissos": compromissos.runtime_bundle(
                {"resposta_sella": appointment()}, "14 Eleasis, 1372 DR", "21:30", limit=4
            ),
        }
        record = transacoes.build_pending_record(
            {
                "id": "tx-cumprido",
                "jogador": "Ren conclui o encontro.",
                "narracao": "A conversa termina.",
                "resumo": "Compromisso encerrado.",
                "deltas": [compromissos.close_delta("resposta_sella")],
            },
            12,
        )
        effective, _, _ = transacoes.overlay_runtime(context, None, [record])
        self.assertNotIn("compromissos", effective)

    def test_tempo_atomico_do_mesmo_turno_reclassifica_compromisso(self):
        context = {
            "sessao": {"numero": 12},
            "tempo": {"data": "14 Eleasis, 1372 DR", "hora_aproximada": "21:00"},
        }
        record = transacoes.build_pending_record(
            {
                "id": "tx-avanco-e-compromisso",
                "jogador": "Ren espera até o horário.",
                "narracao": "O sino marca a hora combinada.",
                "resumo": "Ren chega à janela combinada.",
                "deltas": [
                    compromissos.create_delta("resposta_sella", appointment()),
                    {
                        "alvo": "tempo",
                        "op": "instante",
                        "valor": {"data": "14 Eleasis, 1372 DR", "hora": "21:30"},
                    },
                ],
            },
            12,
        )
        effective, _, _ = transacoes.overlay_runtime(context, None, [record])
        self.assertEqual(effective["tempo"]["hora_aproximada"], "21:30")
        self.assertEqual(
            effective["compromissos"]["itens"]["resposta_sella"]["situacao_temporal"],
            "em_janela",
        )


class CommitmentRuntimeGeneratorTest(unittest.TestCase):
    def _documents(self, commitments=None):
        state = {
            "campanha": {"sessao_atual": 12, "status": "em_sessao", "modo_de_cena_atual": "interacao"},
            "personagem": {"nome": "Ren Kagehira", "nivel": 7, "classe": "Monge", "subclasse": "Caminho da Sombra"},
            "localizacao": {"plano": "Material", "mundo": "Toril", "continente": "Faerûn", "regiao": "The Vast", "cidade": "Ravens Bluff", "area": "Rua da Cal", "ponto_exato": "mercador", "descricao_operacional": "Ren aguarda."},
            "tempo": {"data_exata": "14 Eleasis, 1372 DR", "hora_aproximada": "21:30", "periodo_do_dia": "noite", "clima": "seco"},
            "recursos": {"pontos_de_vida": {"atuais": 52, "maximos": 52}, "ki": {"atuais": 7, "maximos": 7}, "classe_de_armadura": 17, "deslocamento": "55 pés", "dinheiro": {"po": 30.58}, "disponibilidades": {}},
        }
        if commitments is not None:
            state["compromissos"] = commitments
        time = {"data_atual": "14 Eleasis, 1372 DR", "hora_aproximada": "21:30", "periodo_do_dia": "noite", "clima": "seco", "prazo_relevante": "alerta livre"}
        sheet = {"personagem": {"nome": "Ren Kagehira"}, "identidade": {"nivel": 7}}
        return state, time, sheet

    def test_sem_compromisso_runtime_permanece_sem_nova_chave(self):
        context, scene = gerar_runtime.build_runtime_from_documents(*self._documents())
        self.assertNotIn("compromissos", context)
        self.assertNotIn("compromissos", scene)

    def test_compromisso_canonico_entra_uma_vez_no_contexto(self):
        state, time, sheet = self._documents({"resposta_sella": appointment()})
        context, scene = gerar_runtime.build_runtime_from_documents(state, time, sheet)
        self.assertEqual(context["compromissos"]["quantidade"], 1)
        self.assertEqual(
            context["compromissos"]["itens"]["resposta_sella"]["situacao_temporal"],
            "em_janela",
        )
        self.assertNotIn("compromissos", scene)


if __name__ == "__main__":
    unittest.main()
