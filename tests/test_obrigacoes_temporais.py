from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import acionamentos_leves
import obrigacoes_temporais


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")


def record(*, owner="silva_elkwood", state="reconciliar", trigger=None, source="estado/relacoes/silva_elkwood.yaml"):
    return {
        "tipo": "compromisso",
        "resumo": "Retornar estado verificável sem inventar resultado",
        "envolvidos": [owner],
        "obrigacao_temporal": {
            "schema": 1,
            "estado": state,
            "responsavel": owner,
            "destinatario": "ren",
            "local_ou_canal": "canal já estabelecido",
            "prazo_ou_condicao": trigger or {"condicao": "a situação material mudar"},
            "resultado_esperado": "registrar retorno, novo prazo ou encerramento",
            "modo_retorno": "atualização compatível com o canal",
            "fonte_canonica": {"arquivo": source, "evidencia_literal": "situação ainda em trânsito"},
            "protecoes": ["não inventar resultado"],
        },
    }


class TemporalObligationFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        dump(
            self.repo / "estado/tempo.yaml",
            {
                "schema_tempo": 1,
                "natureza": "tempo_atual",
                "data_atual": "21 Eleasis, 1372 DR",
                "hora_aproximada": "22:00",
            },
        )
        dump(self.repo / "estado/relacoes/silva_elkwood.yaml", {"texto": "situação ainda em trânsito"})
        dump(
            self.repo / "narrador/obrigacoes-temporais/evidencias.yaml",
            {"schema_migracao_obrigacoes_temporais": 1, "natureza": "reservado", "candidatos": {}},
        )
        dump(
            self.repo / "narrador/obrigacoes-temporais/estado.yaml",
            {
                "schema_estado_obrigacoes_temporais": 1,
                "natureza": "controle_reservado",
                "migracao": {"executada": True},
                "adiamentos": {},
                "despachos": {},
            },
        )
        dump(
            self.repo / "estado/estado-atual.yaml",
            {"schema_estado": 1, "compromissos": {"retorno_silva": record()}},
        )
        dump(
            self.repo / "narrador/obrigacoes-temporais/indice.yaml",
            obrigacoes_temporais.build_index({"retorno_silva": record()}),
        )

    def tearDown(self):
        self.tmp.cleanup()


class TemporalIndexTest(TemporalObligationFixture):
    def test_indice_e_dirigido_por_data_condicao_e_responsavel(self):
        records = {
            "retorno": record(),
            "prazo": record(
                owner="jack_mooney",
                trigger={"data": "17 Eleasis, 1372 DR"},
                source="estado/relacoes/jack_mooney.yaml",
            ),
        }
        index = obrigacoes_temporais.build_index(records)
        self.assertEqual(index["por_responsavel"]["silva_elkwood"], ["retorno"])
        self.assertEqual(index["por_responsavel"]["jack_mooney"], ["prazo"])
        self.assertEqual(index["por_data"]["17 Eleasis, 1372 DR"], ["prazo"])
        self.assertEqual(len(index["por_condicao"]), 1)

    def test_estado_reconciliar_fica_devido_sem_inventar_evento(self):
        due = obrigacoes_temporais.due_records(self.repo)
        self.assertEqual(set(due), {"retorno_silva"})
        self.assertEqual(due["retorno_silva"]["obrigacao_temporal"]["estado"], "reconciliar")

    def test_data_sem_hora_so_vence_depois_do_dia(self):
        meta = record(state="ativa", trigger={"data": "21 Eleasis, 1372 DR"})["obrigacao_temporal"]
        now = obrigacoes_temporais.mundo.parse_instant("21 Eleasis, 1372 DR", "22:00")
        self.assertFalse(obrigacoes_temporais._trigger_due(meta, now))
        later = obrigacoes_temporais.mundo.parse_instant("22 Eleasis, 1372 DR", "00:00")
        self.assertTrue(obrigacoes_temporais._trigger_due(meta, later))


class TemporalNoopTest(TemporalObligationFixture):
    def test_noop_vencido_exige_nova_data_ou_condicao(self):
        with mock.patch.object(obrigacoes_temporais, "_pending_owner", return_value="silva_elkwood"):
            with self.assertRaises(obrigacoes_temporais.TemporalObligationError):
                obrigacoes_temporais.conclude_noop(
                    self.repo,
                    "mundo-aaaaaaaaaaaaaaaa",
                    "sem mudança material",
                    retomar_data=None,
                    retomar_hora=None,
                    retomar_condicao=None,
                    base_conclude=lambda *_: {"ok": True},
                )

    def test_condicao_e_gravada_antes_de_encerrar_e_retry_e_idempotente(self):
        observed = {}

        def base(_repo, _pending, _note):
            observed["durante_base"] = obrigacoes_temporais.load_tracker(self.repo)["adiamentos"]["retorno_silva"]["estado"]
            return {"ok": True}

        with mock.patch.object(obrigacoes_temporais, "_pending_owner", return_value="silva_elkwood"):
            result = obrigacoes_temporais.conclude_noop(
                self.repo,
                "mundo-bbbbbbbbbbbbbbbb",
                "sem mudança material",
                retomar_data=None,
                retomar_hora=None,
                retomar_condicao="quando a transferência mudar",
                base_conclude=base,
            )
        self.assertEqual(observed["durante_base"], "preparado")
        tracker = obrigacoes_temporais.load_tracker(self.repo)
        self.assertEqual(tracker["adiamentos"]["retorno_silva"]["estado"], "ativo")
        self.assertEqual(result["obrigacoes_temporais"]["adiadas"], ["retorno_silva"])
        self.assertEqual(obrigacoes_temporais.due_records(self.repo), {})

    def test_condicao_adiada_volta_quando_fonte_canonica_muda(self):
        with mock.patch.object(obrigacoes_temporais, "_pending_owner", return_value="silva_elkwood"):
            obrigacoes_temporais.conclude_noop(
                self.repo,
                "mundo-cccccccccccccccc",
                "sem mudança material",
                retomar_data=None,
                retomar_hora=None,
                retomar_condicao="quando a transferência mudar",
                base_conclude=lambda *_: {"ok": True},
            )
        (self.repo / "estado/relacoes/silva_elkwood.yaml").write_text(
            "texto: situação ainda em trânsito, mas a fonte mudou\n", encoding="utf-8"
        )
        self.assertEqual(set(obrigacoes_temporais.due_records(self.repo)), {"retorno_silva"})

    def test_retomada_com_data_precisa_ser_futura(self):
        with mock.patch.object(obrigacoes_temporais, "_pending_owner", return_value="silva_elkwood"):
            with self.assertRaises(obrigacoes_temporais.TemporalObligationError):
                obrigacoes_temporais.conclude_noop(
                    self.repo,
                    "mundo-dddddddddddddddd",
                    "sem mudança material",
                    retomar_data="20 Eleasis, 1372 DR",
                    retomar_hora="06:00",
                    retomar_condicao=None,
                    base_conclude=lambda *_: {"ok": True},
                )


class TemporalMigrationTest(unittest.TestCase):
    def test_migracao_e_one_shot_e_so_converte_evidencia_literal(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            dump(repo / "estado/estado-atual.yaml", {"schema_estado": 1})
            dump(
                repo / "narrador/obrigacoes-temporais/estado.yaml",
                {
                    "schema_estado_obrigacoes_temporais": 1,
                    "natureza": "controle_reservado",
                    "migracao": {"executada": False},
                    "adiamentos": {},
                    "despachos": {},
                },
            )
            dump(
                repo / "narrador/obrigacoes-temporais/indice.yaml",
                obrigacoes_temporais.build_index({}),
            )
            dump(repo / "historico/prova.yaml", {"texto": "promessa literal comprovada"})
            dump(repo / "estado/relacoes/silva_elkwood.yaml", {"texto": "situação ainda em trânsito"})
            candidate = record()
            dump(
                repo / "narrador/obrigacoes-temporais/evidencias.yaml",
                {
                    "schema_migracao_obrigacoes_temporais": 1,
                    "natureza": "reservado",
                    "candidatos": {
                        "retorno_silva": {
                            "evidencia_historica": {
                                "arquivo": "historico/prova.yaml",
                                "evidencia_literal": "promessa literal comprovada",
                            },
                            "registro": candidate,
                        }
                    },
                },
            )
            first = obrigacoes_temporais.migrate(repo)
            self.assertEqual(first["convertidos"], ["retorno_silva"])
            state = yaml.safe_load((repo / "estado/estado-atual.yaml").read_text(encoding="utf-8"))
            self.assertIn("retorno_silva", state["compromissos"])

            shutil.rmtree(repo / "historico")
            (repo / "narrador/obrigacoes-temporais/evidencias.yaml").unlink()
            second = obrigacoes_temporais.migrate(repo)
            self.assertTrue(second["ja_executada"])
            self.assertEqual(second["fontes_lidas"], [obrigacoes_temporais.TRACKER_PATH.as_posix()])

    def test_evidencia_historica_ausente_falha_sem_criar_obrigacao(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            dump(repo / "estado/estado-atual.yaml", {"schema_estado": 1})
            dump(
                repo / "narrador/obrigacoes-temporais/estado.yaml",
                {
                    "schema_estado_obrigacoes_temporais": 1,
                    "natureza": "controle_reservado",
                    "migracao": {"executada": False},
                    "adiamentos": {},
                    "despachos": {},
                },
            )
            dump(repo / "narrador/obrigacoes-temporais/indice.yaml", obrigacoes_temporais.build_index({}))
            dump(repo / "historico/prova.yaml", {"texto": "outra coisa"})
            dump(repo / "estado/relacoes/silva_elkwood.yaml", {"texto": "situação ainda em trânsito"})
            dump(
                repo / "narrador/obrigacoes-temporais/evidencias.yaml",
                {
                    "schema_migracao_obrigacoes_temporais": 1,
                    "natureza": "reservado",
                    "candidatos": {
                        "retorno_silva": {
                            "evidencia_historica": {
                                "arquivo": "historico/prova.yaml",
                                "evidencia_literal": "promessa que não existe",
                            },
                            "registro": record(),
                        }
                    },
                },
            )
            with self.assertRaises(obrigacoes_temporais.TemporalObligationError):
                obrigacoes_temporais.migrate(repo)
            state = yaml.safe_load((repo / "estado/estado-atual.yaml").read_text(encoding="utf-8"))
            self.assertNotIn("compromissos", state)


class ExistingCausalPriorityTest(unittest.TestCase):
    def test_prazo_causal_tem_precedencia_sobre_mudanca_ordinaria(self):
        when = {"data": "21 Eleasis, 1372 DR", "hora": "06:00"}
        deadline = {"prazo:x": {"tipo": "prazo", "em": when}}
        ordinary = {"mudanca:x": {"tipo": "mudanca", "em": when}}
        self.assertLess(acionamentos_leves._rank(deadline), acionamentos_leves._rank(ordinary))


if __name__ == "__main__":
    unittest.main()
