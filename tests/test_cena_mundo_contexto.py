from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock
import types
import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

# Bundle overlay: stubs apenas para dependências que não fazem parte desta fase.
interacoes = types.ModuleType("interacoes_mundo")
interacoes.VALID_LOCAL_ACTIONS = {"entrar", "explorar"}
class IntegrationError(ValueError): pass
interacoes.IntegrationError = IntegrationError
interacoes.resolve_encounter_npc = lambda *a, **k: (_ for _ in ()).throw(AssertionError("não deveria resolver NPC"))
interacoes.local_event = lambda *a, **k: (_ for _ in ()).throw(AssertionError("não deveria tocar local"))
interacoes.encounter_event = lambda *a, **k: (_ for _ in ()).throw(AssertionError("não deveria tocar encontro"))
interacoes._now = lambda *a, **k: (_ for _ in ()).throw(AssertionError("não deveria ler tempo"))
sys.modules.setdefault("interacoes_mundo", interacoes)

mundo_stub = types.ModuleType("mundo")
class WorldEngineError(ValueError): pass
class WorldInstant: pass
mundo_stub.WorldEngineError = WorldEngineError
mundo_stub.WorldInstant = WorldInstant
mundo_stub.parse_instant = lambda d, h: (d, h)
sys.modules.setdefault("mundo", mundo_stub)

opps = types.ModuleType("oportunidades")
opps.INDEX = Path("narrador/oportunidades/index.yaml")
class OpportunityError(ValueError): pass
opps.OpportunityError = OpportunityError
opps.load_index = lambda *a, **k: (_ for _ in ()).throw(AssertionError("não deveria ler oportunidades"))
sys.modules.setdefault("oportunidades", opps)

rewards = types.ModuleType("recompensas")
rewards.VALID_DANGER = {"baixa", "media", "alta"}
class RewardMapError(ValueError): pass
rewards.RewardMapError = RewardMapError
rewards.local_id = lambda value: value
sys.modules.setdefault("recompensas", rewards)

import cena_mundo


class CenaMundoContextoTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self._base()

    def tearDown(self): self.temp.cleanup()

    def _write(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def _base(self) -> None:
        self._write("narrador/mundo/contextos-cena.yaml", {
            "schema_contextos_cena": 3,
            "natureza": "roteador_reservado",
            "orcamento": {"max_tags_por_cena": 8, "max_presencas": 2, "max_operacoes": 2, "max_direcoes": 1, "max_entradas": 1, "max_candidatos_total": 4, "ordenacao": "coincidencias_prioridade_tipo_id"},
            "candidatos": {
                "presenca_shizune": {"tipo": "presenca", "alvo": "shizune", "grupo_arco": "antagonistas", "prioridade": 100, "min_coincidencias": 2, "tags": ["documentos", "escrituracao", "registros"]},
                "operacao_provas": {"tipo": "operacao", "alvo": "impedir_consolidacao_de_provas", "prioridade": 90, "min_coincidencias": 2, "tags": ["documentos", "registros", "provas"]},
                "direcao_ponte": {"tipo": "direcao", "alvo": "ponte_de_kozakura", "prioridade": 85, "min_coincidencias": 2, "tags": ["documentos", "registros", "kozakura"]},
            },
        })
        self._write("narrador/agentes/index.yaml", {"schema_agentes": 2, "natureza": "reservado", "agentes": {
            "shizune": {"nome": "Kajiwara Shizune", "estado": "ativo", "presenca": "indeterminado", "atuacao_local": "exige_presenca_fisica"},
            "masao": {"nome": "Masao", "estado": "ativo", "presenca": "indeterminado", "atuacao_local": "permite_rede"},
        }})
        self._write("narrador/arcos/index.yaml", {"schema_arcos": 1, "natureza": "roteador_reservado", "arcos": {"parte_1": {"titulo": "Parte 1", "ordem": 1, "arquivo": "narrador/arcos/parte_1.yaml", "proximo": None}}})
        self._write("narrador/arcos/estado.yaml", {"schema_estado_arcos": 2, "natureza": "controle_reservado", "arco_atual": "parte_1", "estado": "ativo", "historico_transicoes": []})
        self._write("narrador/arcos/parte_1.yaml", {
            "schema_arco": 4, "natureza": "reservado", "estatuto": "contrato_orquestrador_de_arco", "id": "parte_1", "titulo": "Parte 1", "principio": "fixture",
            "inicio": {"tipo": "fato_canonico", "marcador": "inicio", "fonte": "campanha.yaml"},
            "termino": {"tipo": "marco_explicito", "marcador": "fim", "fonte": "campanha.yaml"},
            "orquestracao": {"fontes": {"plano": {"tipo": "documento_reservado", "arquivo": "narrador/masao/plano.md"}}, "plano_mestre": {"agente": "masao", "objetivo": "objetivo", "referencia": "plano"}},
            "habilitacoes": {"politica_nao_listados": "bloqueados", "antagonistas": ["shizune"], "aliados": [], "direcoes": ["ponte_de_kozakura"]},
            "linhas_operacionais": {"impedir_consolidacao_de_provas": {"objetivo": "impedir_provas", "executores": ["shizune"], "referencia": "plano"}},
        })
        self._write("narrador/direcoes/estado.yaml", {"schema_estado_direcoes": 1, "natureza": "controle_reservado", "direcoes": {"ponte_de_kozakura": {"estado": "ativa", "marco_atual": "coisas_plausiveis", "marcos_concluidos": [], "historico_recente": []}}})
        self._write("narrador/arcos/marcos-aparicao.yaml", {
            "schema_marcos_aparicao": 1, "natureza": "roteador_reservado",
            "fonte_canonica": "narrador/juppongatana/marcos-de-aparicao.md",
            "regras": {"elegivel_nao_e_aparicao": True, "consumido_nao_bloqueia_reaparicao": True},
            "marcos": {"shizune": {"arco": "parte_1", "grupo": "antagonistas", "nivel_minimo": 6, "secao_fonte": "### Shizune", "condicao_id": "institucional"}},
        })
        self._write("narrador/arcos/estado-marcos-aparicao.yaml", {
            "schema_estado_marcos_aparicao": 1, "natureza": "controle_reservado",
            "marcos": {"shizune": {"estado": "elegivel", "origem": "fixture", "nota": "ok", "historico_recente": []}},
        })
        self._write("runtime/contexto.yaml", {"personagem": {"nivel": 6}})

    def test_contexto_sozinho_retorna_tres_classes_sem_oportunidades_ou_tempo(self):
        with (
            mock.patch.object(cena_mundo.oportunidades, "load_index") as opportunities,
            mock.patch.object(cena_mundo.interacoes_mundo, "_now") as now,
        ):
            result = cena_mundo.open_scene(self.repo, scene_id="s009:tomas-escritorio", context_tags=["documentos", "escrituração", "registros"])
        opportunities.assert_not_called(); now.assert_not_called()
        self.assertEqual(result["npcs_canonicos"], [])
        self.assertEqual([x["id"] for x in result["presencas_contextuais"]], ["shizune"])
        self.assertEqual(result["presencas_contextuais"][0]["marco_aparicao"]["estado"], "elegivel")
        self.assertEqual([x["id"] for x in result["operacoes_contextuais"]], ["impedir_consolidacao_de_provas"])
        self.assertEqual([x["id"] for x in result["direcoes_contextuais"]], ["ponte_de_kozakura"])
        self.assertEqual(result["resumo"]["presencas_contextuais"], 1)
        self.assertEqual(result["resumo"]["operacoes_contextuais"], 1)
        self.assertEqual(result["resumo"]["direcoes_contextuais"], 1)

    def test_tags_sem_match_nao_exigem_controles_adicionais(self):
        result = cena_mundo.open_scene(self.repo, scene_id="s009:cozinha", context_tags=["cozinha", "comida"])
        self.assertEqual(result["candidatos_contextuais"], [])
        self.assertEqual(result["fontes_lidas"], ["narrador/mundo/contextos-cena.yaml"])

    def test_operacao_contextual_nao_vira_encontro(self):
        result = cena_mundo.open_scene(self.repo, scene_id="op", context_tags=["documentos", "registros"])
        self.assertEqual(result["encontros"], [])
        self.assertTrue(result["operacoes_contextuais"])

    def test_direcao_contextual_nao_muta_estado(self):
        path = self.repo / "narrador/direcoes/estado.yaml"
        before = path.read_bytes()
        cena_mundo.open_scene(self.repo, scene_id="dir", context_tags=["documentos", "registros"])
        self.assertEqual(path.read_bytes(), before)

    def test_configuracao_de_arco_quebrada_falha_antes_de_mutar_local(self):
        state = yaml.safe_load((self.repo / "narrador/arcos/estado.yaml").read_text())
        state["arco_atual"] = "parte_inexistente"
        self._write("narrador/arcos/estado.yaml", state)
        with mock.patch.object(cena_mundo.interacoes_mundo, "local_event") as local:
            with self.assertRaises(cena_mundo.SceneGateError):
                cena_mundo.open_scene(self.repo, scene_id="arco-quebrado", context_tags=["documentos", "registros"], place="local", action="entrar", tier=1, danger="baixa")
        local.assert_not_called()

    def test_parser_aceita_tags_contextuais_repetidas(self):
        args = cena_mundo.build_parser().parse_args(["abrir", "--cena-id", "s009", "--contexto-tag", "documentos", "--contexto-tag", "registros"])
        self.assertEqual(args.contexto_tag, ["documentos", "registros"])


if __name__ == "__main__": unittest.main()
