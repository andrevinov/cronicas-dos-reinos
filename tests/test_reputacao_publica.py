from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import contexto
import politica_acesso
import reputacao_publica as rep
import transacoes


class PublicReputationRegistryTest(unittest.TestCase):
    def test_registro_real_tem_seis_publicos_compactos_e_tres_personas(self):
        audiences = rep.load_audiences(ROOT)
        identities = rep.load_identities(ROOT)
        self.assertEqual(
            set(audiences["publicos"]),
            {
                "populacao_geral",
                "autoridades_civicas",
                "porto_e_comercio",
                "templos_e_comunidade",
                "circo_e_artes",
                "redes_informais",
            },
        )
        self.assertEqual(set(identities["identidades"]), {"ren", "shinta", "kage"})
        self.assertEqual(rep.resolve_public(audiences, "Night Watch"), "autoridades_civicas")
        self.assertEqual(rep.resolve_identity(identities, "Kage"), "kage")
        self.assertEqual(rep.check(ROOT), [])

    def test_bootstrap_real_nao_inventa_reputacao_retroativa(self):
        state = yaml.safe_load((ROOT / rep.STATE_FILE).read_text(encoding="utf-8"))
        self.assertNotIn(rep.STATE_ROOT, state)
        projected = rep.show(ROOT, "ren")
        self.assertEqual(projected["leitura_da_cidade"], "sem_posicao_publica")
        self.assertTrue(
            all(
                item["estado"] == "estrangeiro_desconhecido"
                for item in projected["publicos"].values()
            )
        )

    def test_sucesso_artistico_de_kage_existente_nao_vira_reputacao_civica(self):
        summary = (ROOT / "sessoes/014/resumo.md").read_text(encoding="utf-8")
        self.assertIn("forte entusiasmo pelo público", summary)
        projected = rep.show(ROOT, "kage")
        self.assertEqual(projected["leitura_da_cidade"], "sem_posicao_publica")
        self.assertEqual(projected["publicos"]["circo_e_artes"]["estado"], "estrangeiro_desconhecido")


class PublicReputationRulesTest(unittest.TestCase):
    def test_rotulos_sao_derivados_sem_score(self):
        self.assertEqual(rep.derive_label([]), "estrangeiro_desconhecido")
        self.assertEqual(rep.derive_label([rep.NEGATIVE_MARK]), "pessoa_perigosa")
        self.assertEqual(
            rep.derive_label([rep.NEGATIVE_MARK, "resgate_publico"]),
            "figura_controversa",
        )
        self.assertEqual(rep.derive_label(["derrota_criminosos"]), "vigilante")
        self.assertEqual(rep.derive_label(["colaboracao_institucional"]), "pessoa_util")
        self.assertEqual(rep.derive_label(["consequencia_positiva_visivel"]), "pessoa_util")
        self.assertEqual(rep.derive_label(["resgate_publico"]), "protetor")
        self.assertEqual(rep.derive_label(rep.POSITIVE_MARKS), "heroi_local")

    def test_um_fato_nao_pode_saltar_varios_marcos(self):
        audiences = rep.load_audiences(ROOT)
        identities = rep.load_identities(ROOT)
        proposal = rep.propose_event(
            ROOT,
            identity="ren",
            publics=["populacao_geral"],
            event_type="resgate_publico",
            fact="Ren retirou publicamente moradores de uma carroca em risco diante de testemunhas da rua.",
            source="teste:salto-reputacao",
        )
        delta = copy.deepcopy(proposal["deltas"][0])
        record = delta["valor"]
        for kind in ("derrota_criminosos", "colaboracao_institucional"):
            record["marcos"].append(kind)
            record["evidencias"][kind] = {
                "id": rep.event_id(
                    "populacao_geral", "ren", kind, delta["fonte"], delta["fato_canonico"]
                ),
                "fonte": delta["fonte"],
            }
        record["marcos"] = rep._ordered_marks(record["marcos"])
        record["estado"] = rep.derive_label(record["marcos"])
        with self.assertRaises(rep.PublicReputationError):
            rep.validate_transition(rep.empty_state(), delta, audiences, identities)

    def test_writer_recusa_mutacao_direta_e_atribuicao_nao_publica(self):
        malformed = {
            "alvo": "estado",
            "op": "set",
            "caminho": f"{rep.STATE_ROOT}.registros.populacao_geral.ren.estado",
            "valor": "heroi_local",
        }
        with self.assertRaises(transacoes.TransactionError):
            transacoes.validate_delta(malformed)

        proposal = rep.propose_event(
            ROOT,
            identity="ren",
            publics=["autoridades_civicas"],
            event_type="colaboracao_institucional",
            fact="Ren entregou em publico uma testemunha protegida a uma autoridade que confirmou sua colaboracao.",
            source="teste:atribuicao-publica",
        )
        invalid = copy.deepcopy(proposal["deltas"][0])
        invalid["atribuicao_publica"] = False
        with self.assertRaises(transacoes.TransactionError):
            transacoes.validate_delta(invalid)

    def test_validacao_de_batch_e_lazy_sem_delta(self):
        with mock.patch.object(rep, "load_audiences", side_effect=AssertionError("nao deve ler")):
            self.assertEqual(rep.validate_batch(ROOT, [{"deltas": []}]), 0)

        proposal = rep.propose_event(
            ROOT,
            identity="ren",
            publics=["templos_e_comunidade"],
            event_type="consequencia_positiva_visivel",
            fact="A ajuda de Ren produziu diante do templo uma consequencia comunitaria positiva reconhecida publicamente.",
            source="teste:batch-reputacao",
        )
        self.assertEqual(rep.validate_batch(ROOT, [{"deltas": proposal["deltas"]}]), 1)


class PublicReputationEventTest(unittest.TestCase):
    @staticmethod
    def _record(delta, txid="tx-reputacao", session=None):
        if session is None:
            runtime = yaml.safe_load((ROOT / "runtime/contexto.yaml").read_text(encoding="utf-8"))
            session = runtime["sessao"]["numero"]
        return {
            "versao": transacoes.SCHEMA_VERSION,
            "id": txid,
            "sessao": session,
            "resumo": "Fato publico alterou a reputacao de uma persona em Ravens Bluff.",
            "deltas": [delta],
        }

    def test_repetir_mesmo_tipo_nao_farma_reputacao(self):
        first = rep.propose_event(
            ROOT,
            identity="ren",
            publics=["populacao_geral"],
            event_type="resgate_publico",
            fact="Ren resgatou uma crianca em plena rua e foi identificado pelo nome por varias testemunhas.",
            source="teste:resgate-um",
        )
        pending = [self._record(first["deltas"][0])]
        with mock.patch.object(transacoes, "load_pending", return_value=pending):
            second = rep.propose_event(
                ROOT,
                identity="ren",
                publics=["populacao_geral"],
                event_type="resgate_publico",
                fact="Ren realizou outro resgate publico dias depois diante de moradores do mesmo circuito.",
                source="teste:resgate-dois",
            )
        self.assertEqual(second["resultado"], "sem_delta")
        self.assertIn("nao aumenta reputacao", second["ignorados"][0]["motivo"])

    def test_dois_fatos_antes_do_checkpoint_acumulam(self):
        first = rep.propose_event(
            ROOT,
            identity="ren",
            publics=["autoridades_civicas"],
            event_type="colaboracao_institucional",
            fact="A Night Watch confirmou diante de outros agentes que Ren cooperou numa entrega legalmente sensivel.",
            source="teste:pendente-um",
        )
        pending = [self._record(first["deltas"][0], txid="tx-rep-1")]
        with mock.patch.object(transacoes, "load_pending", return_value=pending):
            second = rep.propose_event(
                ROOT,
                identity="ren",
                publics=["autoridades_civicas"],
                event_type="consequencia_positiva_visivel",
                fact="A cooperacao de Ren resultou publicamente na protecao de civis reconhecida pelos agentes presentes.",
                source="teste:pendente-dois",
            )
        after = second["projecao_depois"]["publicos"]["autoridades_civicas"]
        self.assertEqual(
            after["marcos"],
            ["colaboracao_institucional", "consequencia_positiva_visivel"],
        )
        self.assertEqual(after["estado"], "pessoa_util")
        self.assertEqual(second["deltas_pendentes_preexistentes"], 1)

    def test_kage_nao_transfere_reputacao_para_ren(self):
        kage = rep.propose_event(
            ROOT,
            identity="kage",
            publics=["circo_e_artes"],
            event_type="consequencia_positiva_visivel",
            fact="Uma intervencao publica atribuida a Kage beneficiou diretamente artistas e espectadores presentes.",
            source="teste:kage-isolado",
        )
        pending = [self._record(kage["deltas"][0], txid="tx-kage")]
        with mock.patch.object(transacoes, "load_pending", return_value=pending):
            kage_view = rep.show(ROOT, "kage")
            ren_view = rep.show(ROOT, "ren")
        self.assertEqual(kage_view["publicos"]["circo_e_artes"]["estado"], "pessoa_util")
        self.assertEqual(ren_view["publicos"]["circo_e_artes"]["estado"], "estrangeiro_desconhecido")
        self.assertEqual(ren_view["leitura_da_cidade"], "sem_posicao_publica")

    def test_esclarecimento_remove_so_o_negativo_sem_apagar_evidencia(self):
        negative = rep.propose_event(
            ROOT,
            identity="ren",
            publics=["porto_e_comercio"],
            event_type=rep.NEGATIVE_MARK,
            fact="Uma consequencia publica foi atribuida a Ren no porto e comerciantes passaram a trata-lo como risco.",
            source="teste:negativo-publico",
        )
        pending = [self._record(negative["deltas"][0], txid="tx-negativo")]
        with mock.patch.object(transacoes, "load_pending", return_value=pending):
            cleared = rep.propose_event(
                ROOT,
                identity="ren",
                publics=["porto_e_comercio"],
                event_type=rep.CLARIFICATION,
                fact="A origem do incidente foi esclarecida publicamente e o porto retirou a atribuicao negativa feita a Ren.",
                source="teste:esclarecido",
            )
        record = cleared["deltas"][0]["valor"]
        self.assertEqual(record["marcos"], [])
        self.assertEqual(record["estado"], "estrangeiro_desconhecido")
        self.assertIn(rep.NEGATIVE_MARK, record["evidencias"])
        self.assertIn(rep.CLARIFICATION, record["evidencias"])


class PublicReputationContextTest(unittest.TestCase):
    def test_contexto_expoe_reputacao_como_l2_sem_inchar_status(self):
        decision = politica_acesso.classify("reputacao")
        self.assertEqual(decision.level, "L2")
        data = contexto.command_reputation(ROOT, "ren")
        self.assertEqual(data["consulta"]["comando"], "reputacao")
        self.assertEqual(data["resultado"]["leitura_da_cidade"], "sem_posicao_publica")
        self.assertIn(rep.AUDIENCE_REGISTRY.as_posix(), data["fontes"])
        status = contexto.command_status(ROOT)["resultado"]
        self.assertNotIn(rep.STATE_ROOT, status)

    def test_contexto_ve_reputacao_pendente_antes_do_checkpoint(self):
        proposal = rep.propose_event(
            ROOT,
            identity="shinta",
            publics=["porto_e_comercio"],
            event_type="colaboracao_institucional",
            fact="Shinta foi publicamente creditado por uma colaboracao profissional que evitou um problema comercial.",
            source="teste:overlay-contexto",
        )
        pending = [PublicReputationEventTest._record(proposal["deltas"][0], txid="tx-shinta")]
        with mock.patch.object(transacoes, "load_pending", return_value=pending):
            data = contexto.command_reputation(ROOT, "shinta", "porto")
        result = data["resultado"]
        self.assertEqual(result["publicos"]["porto_e_comercio"]["estado"], "pessoa_util")
        self.assertEqual(result["deltas_pendentes_aplicados"], 1)
        self.assertIn(transacoes.PENDING_PATH.as_posix(), data["fontes"])


class PublicReputationBudgetTest(unittest.TestCase):
    def test_contrato_congela_custo_e_invariantes(self):
        data = yaml.safe_load(
            (ROOT / "baseline/public-reputation-ren-orcamento.yaml").read_text(encoding="utf-8")
        )
        limits = data["limites"]
        self.assertEqual(limits["chamadas_extras_turno_comum"], 0)
        self.assertEqual(limits["max_publicos_por_evento"], rep.MAX_PUBLICS_PER_EVENT)
        self.assertEqual(limits["max_registros_ativos"], rep.MAX_ACTIVE_RECORDS)
        self.assertEqual(limits["max_estado_reputacao_bytes"], rep.MAX_STATE_BYTES)
        self.assertEqual(limits["max_fonte_chars"], rep.MAX_SOURCE_CHARS)
        self.assertEqual(limits["schedulers_novos"], 0)
        self.assertEqual(limits["rng_novo"], 0)
        self.assertEqual(limits["arquivos_estado_paralelo_novos"], 0)
        self.assertTrue(all(data["invariantes"].values()))


if __name__ == "__main__":
    unittest.main()
