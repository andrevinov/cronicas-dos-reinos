"""Repetir o staging não perde o vínculo entre resolução e pendência original.

Estado/índices são fixtures temporárias. O plano ainda não foi instalado: somente
outputs podem mudar; o arquivo de mundo persistido continua sendo a base do lote.
Não depende da ordem de imports da suíte para reproduzir o staging duplicado.
"""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ferramentas"))
import acionamentos_leves as causal

WHEN = {"data": "7 Eleasis, 1372 DR", "hora": "08:03"}
SOURCE = "estado/relacoes/a.yaml"


def rendered(value):
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False).encode("utf-8")


class CausalStagingIdentityTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        self.index = {
            "schema_agentes_leves": 2, "natureza": "reservado",
            "orcamento": {"max_novas_por_checkpoint": 1, "max_pendencias_abertas": 2,
                          "max_checks_cache_negativo_por_checkpoint": 1,
                          "ordenacao": "mais_atrasado_prioridade_id"},
            "agentes": {
                aid: {"nome": aid.upper(), "perfil_operacional": "recorrente_leve", "estado": "ativo",
                      "prioridade": 1, "intervalo_dias": 1, "inicio": deepcopy(WHEN),
                      "arquivo": f"narrador/agentes-leves/{aid}.yaml",
                      "fontes_causais": [SOURCE], "perfil_blob_git": "0" * 40}
                for aid in ("a", "b", "c")
            },
        }
        self.world = {"schema_estado_mundo": 1, "natureza": "controle_reservado",
                      "processado_ate": deepcopy(WHEN), "pendencias": [], "concluidas_recentes": []}
        self.write(causal.INDEX, self.index)
        self.write(causal.LIGHT_STATE, {
            "schema_estado_agentes_leves": 2, "natureza": "controle_reservado",
            "agentes": {aid: {"estado": "ativo", "proxima_avaliacao": deepcopy(WHEN),
                              "cache_negativo": None} for aid in self.index["agentes"]},
        })
        self.write(causal.TIME, {"schema_tempo": 1, "data_atual": WHEN["data"], "hora_aproximada": WHEN["hora"]})
        self.write(causal.STATE, {"compromissos": {}})
        self.write(causal.WORLD, self.world)
        self.write(SOURCE, {"id": "a", "relacao": {"informacoes_recebidas": "Relato anterior."}})

    def write(self, relative, value):
        path = self.repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(rendered(value))

    def files(self):
        return {p.relative_to(self.repo).as_posix(): p.read_bytes()
                for p in self.repo.rglob("*") if p.is_file()}

    def open_deadline(self, involved=("a",)):
        state = {"compromissos": {"mapa": {
            "tipo": "encontro", "resumo": "Examinar o mapa.", "envolvidos": list(involved),
            "janela": {"inicio": deepcopy(WHEN)},
        }}}
        self.write(causal.STATE, state)
        causal._refresh_deadlines(self.world, state, self.index, WHEN)
        causal.dispatch(self.world, self.index)
        self.write(causal.WORLD, self.world)
        return next(p["id"] for p in self.world["pendencias"] if p["agente_leve"] == "a")

    def cancellation(self, pid):
        plan = {"batch": "s003-cena-cancelamento", "sessao": 3,
                "outputs": {causal.STATE.as_posix(): rendered({"compromissos": {}})}}
        record = {"id": "cancelado", "sessao": 3, "modo": "mundo", "resumo": "Acordo cancelado.",
                  "tags": ["resolver-pendencia-mundo:" + pid],
                  "deltas": [{"alvo": "estado", "op": "remove", "caminho": "compromissos.mapa"}]}
        return plan, [record]

    def staged_world(self, plan):
        return yaml.safe_load(plan["outputs"][causal.WORLD.as_posix()])

    def assert_repeated_stage(self, plan, records):
        output = deepcopy(plan["outputs"])
        files = self.files()
        original_records = deepcopy(records)
        for _ in range(3):
            causal.stage(self.repo, plan, records)
            self.assertEqual(plan["outputs"], output)
        self.assertEqual(records, original_records)
        self.assertEqual(self.files(), files)

    def test_cancelamento_repetido_preserva_fila_vazia_e_bytes(self):
        pid = self.open_deadline()
        plan, records = self.cancellation(pid)
        files = self.files()
        causal.stage(self.repo, plan, records)
        staged = self.staged_world(plan)
        self.assertEqual(staged["pendencias"], [])
        self.assertEqual(staged[causal.KEY]["prazos"], {})
        self.assertEqual([(p["id"], p["resultado"]) for p in staged["concluidas_recentes"]],
                         [(pid, "gatilho_revogado")])
        self.assertEqual(self.files(), files)
        self.assert_repeated_stage(plan, records)

    def test_cancelamento_compartilhado_nao_silencia_outro_envolvido(self):
        pid = self.open_deadline(("a", "b"))
        plan, records = self.cancellation(pid)
        causal.stage(self.repo, plan, records)
        staged = self.staged_world(plan)
        self.assertEqual([p["agente_leve"] for p in staged["pendencias"]], ["b"])
        causes = staged["pendencias"][0][causal.PENDING_KEY]
        self.assertEqual(set(causes), {"compromisso:mapa"})
        self.assertEqual(causes["compromisso:mapa"]["tipo"], "mudanca")
        self.assertEqual(staged[causal.KEY]["prazos"], {})
        self.assert_repeated_stage(plan, records)

    def test_fonte_e_cancelamento_no_mesmo_lote_preservam_resolutor(self):
        pid = self.open_deadline()
        plan, records = self.cancellation(pid)
        records[0]["deltas"].append({"alvo": "relacao:a", "op": "set",
                                      "caminho": "informacoes_recebidas", "valor": "Cancelamento confirmado."})
        plan["outputs"][SOURCE] = rendered({"id": "a", "relacao": {"informacoes_recebidas": "Cancelamento confirmado."}})
        causal.stage(self.repo, plan, records)
        staged = self.staged_world(plan)
        self.assertEqual({p["agente_leve"] for p in staged["pendencias"]}, {"b", "c"})
        for pending in staged["pendencias"]:
            self.assertEqual(set(pending[causal.PENDING_KEY]), {SOURCE})
        self.assert_repeated_stage(plan, records)

    def test_mudanca_independente_no_lote_nao_e_suprimida(self):
        pid = self.open_deadline()
        plan, records = self.cancellation(pid)
        # Antes do cancelamento há outro fato sobre o mesmo acordo, sem tag de
        # resolução. A supressão não pode virar um veto global ao agente.
        record = {"id": "alteracao-independente", "sessao": 3, "modo": "interação",
                  "deltas": [{"alvo": "estado", "op": "set", "caminho": "compromissos.mapa",
                              "valor": {"tipo": "compromisso", "resumo": "Revisar o mapa.", "envolvidos": ["a"]}}]}
        records.insert(0, record)
        causal.stage(self.repo, plan, records)
        staged = self.staged_world(plan)
        self.assertEqual([p["agente_leve"] for p in staged["pendencias"]], ["a"])
        self.assertEqual(set(staged["pendencias"][0][causal.PENDING_KEY]), {"compromisso:mapa"})
        self.assert_repeated_stage(plan, records)

    def test_saidas_do_mundo_ja_preparadas_nao_sao_sobrescritas(self):
        pid = self.open_deadline()
        plan, records = self.cancellation(pid)
        previous = deepcopy(self.world)
        strategic = {"id": "mundo-" + "f" * 16, "tipo": "reavaliar_agente", "agente": "outro",
                     "disparado_em": deepcopy(WHEN), "origem": "fixture-outro-produtor"}
        previous["pendencias"].append(strategic)
        plan["outputs"][causal.WORLD.as_posix()] = rendered(previous)
        causal.stage(self.repo, plan, records)
        self.assertEqual(self.staged_world(plan)["pendencias"], [strategic])
        self.assert_repeated_stage(plan, records)

    def test_cancelamento_preserva_rotina_promovida_com_o_mesmo_id(self):
        routine = {"id": "mundo-" + "a" * 16, "tipo": "reavaliar_agente_leve", "agente_leve": "a",
                   "disparado_em": deepcopy(WHEN), "origem": "agentes-leves:a.cadencia"}
        self.world["pendencias"].append(deepcopy(routine))
        pid = self.open_deadline()
        self.assertEqual(pid, routine["id"])
        plan, records = self.cancellation(pid)
        causal.stage(self.repo, plan, records)
        self.assertEqual(self.staged_world(plan)["pendencias"], [routine])
        self.assert_repeated_stage(plan, records)

    def test_sem_mundo_preparado_le_a_base_somente_uma_vez(self):
        pid = self.open_deadline()
        plan, records = self.cancellation(pid)
        with patch.object(causal, "_read", wraps=causal._read) as reads:
            causal.stage(self.repo, plan, records)
        world_reads = [call for call in reads.call_args_list if call.args[1] == causal.WORLD]
        self.assertEqual(len(world_reads), 1)


if __name__ == "__main__":
    unittest.main()
