from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import eventos_mundo
import interacoes_mundo
import oportunidades
import rede_protegida


class ProtectedCoreRepositoryTest(unittest.TestCase):
    def test_nucleo_real_tem_exatamente_cinco_membros_canonicos(self):
        result = rede_protegida.validate(ROOT)
        self.assertTrue(result["ok"], result["erros"])
        self.assertEqual(result["membros"], 5)
        policy = rede_protegida.load_policy(ROOT)
        self.assertEqual(
            set(policy["membros"]),
            {"nera_vell", "tavin_vell", "silva_elkwood", "maerra_thandrel", "luath"},
        )
        self.assertNotIn("jack_mooney", policy["membros"])
        self.assertNotIn("kethra_dunn", policy["membros"])
        self.assertNotIn("halessa_vorn", policy["membros"])

    def test_politica_declara_que_protecao_nao_e_imortalidade(self):
        policy = rede_protegida.load_policy(ROOT)
        rules = policy["regras"]
        self.assertTrue(rules["protecao_e_por_origem_nao_imortalidade"])
        self.assertTrue(rules["combate_resolvido_fica_fora_deste_gate"])
        self.assertTrue(rules["escolha_do_jogador_fica_fora_deste_gate"])
        self.assertTrue(rules["acao_canonica_do_arco_fica_fora_deste_gate"])

    def test_evento_real_reclassifica_luath_sem_buscar_substituto(self):
        index = eventos_mundo.load_index(ROOT)
        context = eventos_mundo.routing_context(ROOT)
        routed = eventos_mundo.route_agents(
            index["cartas"]["inspecao_portuaria_reforcada"]["tags"],
            context,
        )
        self.assertEqual(routed["estrategicos"], ["red_sail", "night_watch"])
        self.assertEqual(routed["leves"], [])
        self.assertEqual(routed["nucleo_protegido"], ["luath"])

    def test_evento_real_reclassifica_maerra_sem_afeta_la_diretamente(self):
        index = eventos_mundo.load_index(ROOT)
        routed = eventos_mundo.route_agents(
            index["cartas"]["surto_de_doenca_leve"]["tags"],
            eventos_mundo.routing_context(ROOT),
        )
        self.assertEqual(routed["estrategicos"], [])
        self.assertEqual(routed["leves"], [])
        self.assertEqual(routed["nucleo_protegido"], ["maerra_thandrel"])


class ProtectedCorePureGateTest(unittest.TestCase):
    def test_particao_preserva_ordem_e_nao_escolhe_substituto(self):
        policy = rede_protegida.load_policy(ROOT)
        result = rede_protegida.partition_candidates(policy, ["luath"])
        self.assertEqual(result, {"afetados": [], "nucleo_protegido": ["luath"]})

    def test_consequencia_moderada_reversivel_social_e_permitida(self):
        result = rede_protegida.guard_consequence(
            ROOT,
            {
                "titulo": "Atrito temporário",
                "descricao": "Nera fica contrariada por uma consequência lateral.",
                "gravidade": "moderada",
                "reversibilidade": "reversivel",
                "classe_impacto": "social",
                "alvos_npc": ["nera_vell"],
            },
            origem="sidequest",
        )
        self.assertEqual(result["alvos_protegidos"], ["nera_vell"])
        self.assertEqual(result["valor"]["rede_protegida"]["impacto_maximo"], "moderada")
        self.assertEqual(result["fontes_lidas"], [rede_protegida.INDEX.as_posix()])

    def test_grave_incerta_vida_e_liberdade_sao_bloqueados_no_nucleo(self):
        base = {
            "titulo": "Teste",
            "descricao": "Teste de bloqueio.",
            "gravidade": "moderada",
            "reversibilidade": "reversivel",
            "classe_impacto": "social",
            "alvos_npc": ["tavin_vell"],
        }
        cases = [
            {**base, "gravidade": "grave"},
            {**base, "reversibilidade": "incerta"},
            {**base, "reversibilidade": "irreversivel"},
            {**base, "classe_impacto": "vida"},
            {**base, "classe_impacto": "liberdade"},
        ]
        for value in cases:
            with self.subTest(value=value):
                with self.assertRaises(rede_protegida.ProtectedNetworkError):
                    rede_protegida.guard_consequence(ROOT, value, origem="sidequest")

    def test_npc_fora_do_nucleo_nao_ganha_plot_armor(self):
        result = rede_protegida.guard_consequence(
            ROOT,
            {
                "titulo": "Consequência grave",
                "descricao": "Uma consequência grave pode atingir alguém fora do núcleo.",
                "gravidade": "grave",
                "reversibilidade": "incerta",
                "classe_impacto": "liberdade",
                "alvos_npc": ["kethra_dunn"],
            },
            origem="sidequest",
        )
        self.assertEqual(result["alvos_protegidos"], [])
        self.assertNotIn("rede_protegida", result["valor"])

    def test_consequencia_procedural_exige_metadados_explicitos(self):
        with self.assertRaises(rede_protegida.ProtectedNetworkError):
            rede_protegida.guard_consequence(
                ROOT,
                {"titulo": "Sem classificação", "descricao": "Sem metadados."},
                origem="sidequest",
            )


class ProtectedCoreSidequestIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        shutil.copytree(ROOT / "narrador/oportunidades", self.repo / "narrador/oportunidades")
        shutil.copytree(ROOT / "narrador/relogios", self.repo / "narrador/relogios")
        target = self.repo / rede_protegida.INDEX
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rede_protegida.INDEX, target)
        state = oportunidades.load_state(self.repo, oportunidades.load_index(self.repo))
        state["missoes"]["sq-core"] = {
            "id": "sq-core",
            "estado": "aceita",
            "npc_id": "pell",
            "necessidade_id": "teste",
        }
        oportunidades.atomic(self.repo / oportunidades.STATE, state)

    def tearDown(self):
        self.temp.cleanup()

    def test_sidequest_permite_impacto_reversivel_e_anexa_guardrail(self):
        result = interacoes_mundo.prepare_sidequest_effects(
            self.repo,
            "sq-core",
            [
                {
                    "tipo": "consequencia",
                    "valor": {
                        "titulo": "Custo social",
                        "descricao": "Luath precisa reparar um atrito institucional temporário.",
                        "gravidade": "moderada",
                        "reversibilidade": "reversivel",
                        "classe_impacto": "social",
                        "alvos_npc": ["luath"],
                    },
                }
            ],
        )
        self.assertEqual(len(result["deltas_transacionais"]), 1)
        value = result["deltas_transacionais"][0]["valor"]
        self.assertEqual(value["origem_procedural"], "sidequest")
        self.assertEqual(value["rede_protegida"]["alvos"], ["luath"])
        self.assertIn(rede_protegida.INDEX.as_posix(), result["fontes_lidas"])
        self.assertEqual(result["vinculos"][0]["tipo"], "rede_protegida")

    def test_sidequest_grave_falha_antes_de_gerar_delta(self):
        with self.assertRaisesRegex(interacoes_mundo.IntegrationError, "grave bloqueada"):
            interacoes_mundo.prepare_sidequest_effects(
                self.repo,
                "sq-core",
                [
                    {
                        "tipo": "consequencia",
                        "valor": {
                            "titulo": "Escalada indevida",
                            "descricao": "Procedural tenta atingir Silva gravemente.",
                            "gravidade": "grave",
                            "reversibilidade": "reversivel",
                            "classe_impacto": "saude",
                            "alvos_npc": ["silva_elkwood"],
                        },
                    }
                ],
            )

    def test_fixture_sem_politica_preserva_consequencia_legada(self):
        (self.repo / rede_protegida.INDEX).unlink()
        result = interacoes_mundo.prepare_sidequest_effects(
            self.repo,
            "sq-core",
            [
                {
                    "tipo": "consequencia",
                    "valor": {"titulo": "Legado", "descricao": "Fixture antiga."},
                }
            ],
        )
        self.assertEqual(result["deltas_transacionais"][0]["valor"]["titulo"], "Legado")
        self.assertNotIn(rede_protegida.INDEX.as_posix(), result["fontes_lidas"])


class ProtectedCoreBudgetTest(unittest.TestCase):
    def test_contrato_bate_com_codigo_e_custos(self):
        contract = yaml.safe_load(
            (ROOT / "baseline/protected-core-network-orcamento.yaml").read_text(encoding="utf-8")
        )
        limits = contract["limites"]
        self.assertEqual(limits["max_membros"], rede_protegida.MAX_MEMBERS)
        self.assertEqual(limits["max_alvos_por_consequencia"], rede_protegida.MAX_TARGETS)
        self.assertEqual(limits["max_fontes_hot_path"], rede_protegida.MAX_HOT_SOURCES)
        self.assertEqual(limits["impacto_procedural_maximo_nucleo"], "moderada")
        self.assertEqual(limits["max_fragmentos_narrativos_adicionais"], 0)
        self.assertEqual(limits["max_escritas_adicionais"], 0)
        self.assertEqual(limits["max_estados_novos"], 0)
        self.assertEqual(limits["max_schedulers_novos"], 0)
        self.assertEqual(limits["max_scans_repo"], 0)
        self.assertEqual(contract["custos"]["sidequest_sem_consequencia_fontes_adicionais"], 0)
        self.assertEqual(contract["custos"]["evento_rotina_fontes_adicionais"], 0)


if __name__ == "__main__":
    unittest.main()
