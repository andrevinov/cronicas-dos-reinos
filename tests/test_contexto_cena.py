from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[1]
TOOLS = ROOT / "ferramentas"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import arcos
import contexto_cena
import marcos_aparicao


class ContextoCenaTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        self._write(
            "narrador/mundo/contextos-cena.yaml",
            {
                "schema_contextos_cena": 3,
                "natureza": "roteador_reservado",
                "orcamento": {
                    "max_tags_por_cena": 8,
                    "max_presencas": 2,
                    "max_operacoes": 2,
                    "max_direcoes": 1,
                    "max_entradas": 1,
                    "max_candidatos_total": 4,
                    "ordenacao": "coincidencias_prioridade_tipo_id",
                },
                "candidatos": {
                    "presenca_shizune": {
                        "tipo": "presenca",
                        "alvo": "shizune",
                        "grupo_arco": "antagonistas",
                        "prioridade": 100,
                        "tags": ["documentos", "escrituracao", "registros"],
                    },
                    "presenca_agente_b": {
                        "tipo": "presenca",
                        "alvo": "agente_b",
                        "grupo_arco": "antagonistas",
                        "prioridade": 200,
                        "tags": ["documentos"],
                    },
                    "presenca_agente_c": {
                        "tipo": "presenca",
                        "alvo": "agente_c",
                        "grupo_arco": "antagonistas",
                        "prioridade": 200,
                        "tags": ["documentos"],
                    },
                    "presenca_inativo": {
                        "tipo": "presenca",
                        "alvo": "agente_inativo",
                        "grupo_arco": "antagonistas",
                        "prioridade": 999,
                        "tags": ["documentos", "escrituracao", "registros"],
                    },
                    "operacao_provas": {
                        "tipo": "operacao",
                        "alvo": "impedir_consolidacao_de_provas",
                        "prioridade": 90,
                        "min_coincidencias": 2,
                        "tags": ["documentos", "registros", "provas", "burocracia"],
                    },
                    "operacao_logistica": {
                        "tipo": "operacao",
                        "alvo": "proteger_cadeia_logistica",
                        "prioridade": 80,
                        "min_coincidencias": 2,
                        "tags": ["porto", "carga", "armazem", "logistica"],
                    },
                    "direcao_ponte": {
                        "tipo": "direcao",
                        "alvo": "ponte_de_kozakura",
                        "prioridade": 85,
                        "min_coincidencias": 2,
                        "tags": ["documentos", "registros", "kozakura", "contabilidade"],
                    },
                },
            },
        )
        self._write(
            "narrador/agentes/index.yaml",
            {
                "schema_agentes": 2,
                "natureza": "reservado",
                "agentes": {
                    "shizune": {"nome": "Kajiwara Shizune", "estado": "ativo", "presenca": "indeterminado", "atuacao_local": "exige_presenca_fisica"},
                    "agente_b": {"nome": "Agente B", "estado": "ativo", "presenca": "presente", "atuacao_local": "exige_presenca_fisica"},
                    "agente_c": {"nome": "Agente C", "estado": "ativo", "presenca": "presente_oculto", "atuacao_local": "exige_presenca_fisica"},
                    "agente_inativo": {"nome": "Agente Inativo", "estado": "inativo", "presenca": "presente", "atuacao_local": "exige_presenca_fisica"},
                    "masao": {"nome": "Masao", "estado": "ativo", "presenca": "indeterminado", "atuacao_local": "permite_rede"},
                },
            },
        )
        self._write(
            "narrador/direcoes/index.yaml",
            {
                "schema_direcoes": 1,
                "natureza": "reservado",
                "direcoes": {
                    "ponte_de_kozakura": {"nome": "Ponte de Kozakura", "arquivo": "narrador/direcoes/ponte_de_kozakura.yaml"},
                    "futura": {"nome": "Futura", "arquivo": "narrador/direcoes/futura.yaml"},
                },
            },
        )
        self._write(
            "narrador/direcoes/estado.yaml",
            {
                "schema_estado_direcoes": 1,
                "natureza": "controle_reservado",
                "direcoes": {
                    "ponte_de_kozakura": {"estado": "ativa", "marco_atual": "coisas_plausiveis", "marcos_concluidos": [], "historico_recente": []},
                    "futura": {"estado": "latente", "marco_atual": "inicio", "marcos_concluidos": [], "historico_recente": []},
                },
            },
        )
        self._arc(["shizune", "agente_b", "agente_c", "agente_inativo"])
        self._milestones(["shizune", "agente_b", "agente_c", "agente_inativo"])

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, rel: str, value) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def _arc(self, antagonists: list[str], *, directions: list[str] | None = None) -> None:
        self._write(
            "narrador/arcos/index.yaml",
            {
                "schema_arcos": 1,
                "natureza": "roteador_reservado",
                "arcos": {"parte_1": {"titulo": "Parte 1", "ordem": 1, "arquivo": "narrador/arcos/parte_1.yaml", "proximo": None}},
            },
        )
        self._write(
            "narrador/arcos/estado.yaml",
            {"schema_estado_arcos": 2, "natureza": "controle_reservado", "arco_atual": "parte_1", "estado": "ativo", "historico_transicoes": []},
        )
        self._write(
            "narrador/arcos/parte_1.yaml",
            {
                "schema_arco": 4,
                "natureza": "reservado",
                "estatuto": "contrato_orquestrador_de_arco",
                "id": "parte_1",
                "titulo": "Parte 1",
                "principio": "Fixture de contrato orquestrador.",
                "inicio": {"tipo": "fato_canonico", "marcador": "inicio_parte_1", "fonte": "campanha.yaml"},
                "termino": {"tipo": "marco_explicito", "marcador": "fim_parte_1", "fonte": "campanha.yaml"},
                "orquestracao": {
                    "fontes": {"plano_mestre": {"tipo": "documento_reservado", "arquivo": "narrador/masao/plano.md"}},
                    "plano_mestre": {"agente": "masao", "objetivo": "objetivo_parte_1", "referencia": "plano_mestre"},
                },
                "habilitacoes": {
                    "politica_nao_listados": "bloqueados",
                    "antagonistas": antagonists,
                    "aliados": [],
                    "direcoes": list(directions if directions is not None else ["ponte_de_kozakura"]),
                },
                "linhas_operacionais": {
                    "impedir_consolidacao_de_provas": {"objetivo": "impedir_provas", "executores": ["shizune"], "referencia": "plano_mestre"},
                    "proteger_cadeia_logistica": {"objetivo": "proteger_logistica", "executores": ["agente_b"], "referencia": "plano_mestre"},
                },
            },
        )


    def _milestones(self, antagonists: list[str]) -> None:
        self._write(
            "narrador/arcos/marcos-aparicao.yaml",
            {
                "schema_marcos_aparicao": 1,
                "natureza": "roteador_reservado",
                "fonte_canonica": "narrador/juppongatana/marcos-de-aparicao.md",
                "regras": {
                    "elegivel_nao_e_aparicao": True,
                    "consumido_nao_bloqueia_reaparicao": True,
                },
                "marcos": {
                    agent_id: {
                        "arco": "parte_1",
                        "grupo": "antagonistas",
                        "nivel_minimo": 1,
                        "secao_fonte": f"### {agent_id}",
                        "condicao_id": f"condicao_{agent_id}",
                    }
                    for agent_id in antagonists
                },
            },
        )
        self._write(
            "narrador/arcos/estado-marcos-aparicao.yaml",
            {
                "schema_estado_marcos_aparicao": 1,
                "natureza": "controle_reservado",
                "marcos": {
                    agent_id: {
                        "estado": "elegivel" if agent_id in {"shizune", "agente_inativo"} else "consumido",
                        "origem": "fixture",
                        "nota": "marco preparado para teste",
                        "historico_recente": [],
                    }
                    for agent_id in antagonists
                },
            },
        )
        self._write("runtime/contexto.yaml", {"personagem": {"nivel": 6}})
        source = self.repo / "narrador/juppongatana/marcos-de-aparicao.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            "# Marcos\n" + "\n".join(f"### {agent_id}" for agent_id in antagonists) + "\n",
            encoding="utf-8",
        )

    def test_sem_tags_nao_le_roteador(self):
        empty = Path(self.temp.name) / "repo-vazio"
        empty.mkdir()
        result = contexto_cena.select_candidates(empty, [], scene_id="s1")
        self.assertEqual(result["candidatos"], [])
        self.assertEqual(result["fontes_lidas"], [])

    def test_tags_sem_afinidade_leem_so_o_roteador(self):
        result = contexto_cena.select_candidates(self.repo, ["cozinha", "jardim"], scene_id="sem-afinidade")
        self.assertEqual(result["candidatos"], [])
        self.assertEqual(result["fontes_lidas"], ["narrador/mundo/contextos-cena.yaml"])

    def test_validacao_fria_confere_tres_classes_de_binding(self):
        result = contexto_cena.validate(self.repo)
        self.assertTrue(result["ok"])
        self.assertEqual(result["bindings"], 7)
        self.assertEqual(result["tipos"], {"direcao": 1, "entrada": 0, "operacao": 2, "presenca": 4})
        self.assertEqual(result["arco"]["arco_id"], "parte_1")

    def test_contexto_documental_retorna_presenca_operacao_e_direcao(self):
        result = contexto_cena.select_candidates(
            self.repo, ["documentos", "escrituração", "registros"], scene_id="s009:tomas-escritorio"
        )
        by_type = {kind: [item["id"] for item in result[kind]] for kind in ("presencas", "operacoes", "direcoes")}
        self.assertIn("shizune", by_type["presencas"])
        self.assertEqual(by_type["operacoes"], ["impedir_consolidacao_de_provas"])
        self.assertEqual(by_type["direcoes"], ["ponte_de_kozakura"])
        direction = result["direcoes"][0]
        self.assertEqual(direction["marco_atual"], "coisas_plausiveis")
        self.assertEqual(direction["modo_avaliacao"], "avaliar_sustentacao_do_marco")
        self.assertEqual(direction["papel"], "restricao_destino")
        self.assertFalse(direction["executavel"])
        self.assertEqual(direction["consulta_dirigida"], "python3 ferramentas/direcoes.py avaliar-destino ponte_de_kozakura")
        operation = result["operacoes"][0]
        self.assertEqual(operation["modo_avaliacao"], "avaliar_linha_operacional")
        self.assertEqual(operation["executores"], ["shizune"])

    def test_operacao_nao_abre_indice_de_agentes(self):
        router = yaml.safe_load((self.repo / contexto_cena.ROUTER).read_text())
        router["candidatos"] = {"operacao_provas": router["candidatos"]["operacao_provas"]}
        self._write(contexto_cena.ROUTER.as_posix(), router)
        (self.repo / contexto_cena.STRATEGIC_INDEX).unlink()
        result = contexto_cena.select_candidates(self.repo, ["documentos", "registros"], scene_id="op")
        self.assertEqual([item["id"] for item in result["operacoes"]], ["impedir_consolidacao_de_provas"])
        self.assertNotIn(contexto_cena.STRATEGIC_INDEX.as_posix(), result["fontes_lidas"])

    def test_operacao_nao_escolhe_executor_metodo_ou_acao(self):
        result = contexto_cena.select_candidates(self.repo, ["documentos", "registros"], scene_id="op-sem-acao")
        item = result["operacoes"][0]
        self.assertIn("executores", item)
        for forbidden in ("executor_escolhido", "metodo", "acao", "alvo"):
            self.assertNotIn(forbidden, item)

    def test_linha_fora_do_arco_e_bloqueada_antes_de_fragmento(self):
        arc = yaml.safe_load((self.repo / "narrador/arcos/parte_1.yaml").read_text())
        arc["linhas_operacionais"].pop("impedir_consolidacao_de_provas")
        self._write("narrador/arcos/parte_1.yaml", arc)
        result = contexto_cena.select_candidates(self.repo, ["documentos", "registros"], scene_id="linha-bloq")
        self.assertEqual(result["operacoes"], [])
        self.assertGreaterEqual(result["arco"]["bloqueados_por_tipo"]["operacao"], 1)

    def test_direcao_latente_nao_e_exposta(self):
        state = yaml.safe_load((self.repo / contexto_cena.DIRECTIONS_STATE).read_text())
        state["direcoes"]["ponte_de_kozakura"]["estado"] = "latente"
        self._write(contexto_cena.DIRECTIONS_STATE.as_posix(), state)
        result = contexto_cena.select_candidates(self.repo, ["documentos", "registros"], scene_id="dir-latente")
        self.assertEqual(result["direcoes"], [])

    def test_direcao_fora_do_arco_para_antes_do_estado_de_direcoes(self):
        self._arc(["shizune", "agente_b", "agente_c", "agente_inativo"], directions=[])
        router = yaml.safe_load((self.repo / contexto_cena.ROUTER).read_text())
        router["candidatos"] = {"direcao_ponte": router["candidatos"]["direcao_ponte"]}
        self._write(contexto_cena.ROUTER.as_posix(), router)
        (self.repo / contexto_cena.DIRECTIONS_STATE).unlink()
        result = contexto_cena.select_candidates(self.repo, ["documentos", "registros"], scene_id="dir-bloq")
        self.assertEqual(result["direcoes"], [])
        self.assertNotIn(contexto_cena.DIRECTIONS_STATE.as_posix(), result["fontes_lidas"])

    def test_direcao_nao_avanca_estado(self):
        path = self.repo / contexto_cena.DIRECTIONS_STATE
        before = path.read_bytes()
        contexto_cena.select_candidates(self.repo, ["documentos", "registros"], scene_id="read-only")
        self.assertEqual(path.read_bytes(), before)

    def test_presenca_shizune_continua_sem_canonizar_presenca(self):
        result = contexto_cena.select_candidates(self.repo, ["documentos", "escrituracao", "registros"], scene_id="presenca")
        item = {i["id"]: i for i in result["presencas"]}["shizune"]
        self.assertEqual(item["modo_avaliacao"], "avaliar_estabelecimento_presenca")
        self.assertEqual(item["presenca_resumida"], "indeterminado")
        self.assertEqual(item["marco_aparicao"]["estado"], "elegivel")
        self.assertEqual(item["marco_aparicao"]["modo"], "avaliar_primeira_aparicao")


    def test_marco_bloqueado_impede_presenca_sem_esconder_operacao_ou_direcao(self):
        state = yaml.safe_load((self.repo / marcos_aparicao.STATE).read_text())
        state["marcos"]["shizune"]["estado"] = "bloqueado"
        self._write(marcos_aparicao.STATE.as_posix(), state)
        result = contexto_cena.select_candidates(
            self.repo, ["documentos", "registros", "escrituracao"], scene_id="marco-bloq"
        )
        self.assertNotIn("shizune", {item["id"] for item in result["presencas"]})
        self.assertEqual(result["operacoes"][0]["id"], "impedir_consolidacao_de_provas")
        self.assertEqual(result["direcoes"][0]["id"], "ponte_de_kozakura")

    def test_marco_consumido_permite_reaparicao_contextual(self):
        state = yaml.safe_load((self.repo / marcos_aparicao.STATE).read_text())
        state["marcos"]["shizune"]["estado"] = "consumido"
        self._write(marcos_aparicao.STATE.as_posix(), state)
        result = contexto_cena.select_candidates(
            self.repo, ["documentos", "registros", "escrituracao"], scene_id="reaparicao"
        )
        item = {item["id"]: item for item in result["presencas"]}["shizune"]
        self.assertEqual(item["marco_aparicao"]["modo"], "reaparicao_nao_bloqueada_pelo_marco")

    def test_nivel_do_marco_bloqueia_antes_do_indice_de_agentes(self):
        index = yaml.safe_load((self.repo / marcos_aparicao.INDEX).read_text())
        index["marcos"]["shizune"]["nivel_minimo"] = 7
        self._write(marcos_aparicao.INDEX.as_posix(), index)
        router = yaml.safe_load((self.repo / contexto_cena.ROUTER).read_text())
        router["candidatos"] = {"presenca_shizune": router["candidatos"]["presenca_shizune"]}
        self._write(contexto_cena.ROUTER.as_posix(), router)
        (self.repo / contexto_cena.STRATEGIC_INDEX).unlink()
        result = contexto_cena.select_candidates(
            self.repo, ["documentos", "escrituracao", "registros"], scene_id="nivel-bloq"
        )
        self.assertEqual(result["presencas"], [])
        self.assertNotIn(contexto_cena.STRATEGIC_INDEX.as_posix(), result["fontes_lidas"])

    def test_ranking_de_presenca_preserva_coincidencias_antes_prioridade(self):
        result = contexto_cena.select_candidates(self.repo, ["documentos", "escrituracao"], scene_id="ranking")
        self.assertEqual([i["id"] for i in result["presencas"]], ["shizune", "agente_b"])

    def test_inativo_e_fora_da_area_nao_aparecem(self):
        data = yaml.safe_load((self.repo / contexto_cena.STRATEGIC_INDEX).read_text())
        data["agentes"]["agente_b"]["presenca"] = "fora_da_area"
        self._write(contexto_cena.STRATEGIC_INDEX.as_posix(), data)
        ids = {i["id"] for i in contexto_cena.select_candidates(self.repo, ["documentos"], scene_id="filtro")["presencas"]}
        self.assertNotIn("agente_b", ids)
        self.assertNotIn("agente_inativo", ids)

    def test_npc_ja_no_elenco_e_excluido_sem_afetar_operacao(self):
        result = contexto_cena.select_candidates(
            self.repo, ["documentos", "registros"], scene_id="excluir", exclude_ids={"shizune"}
        )
        self.assertNotIn("shizune", {i["id"] for i in result["presencas"]})
        self.assertEqual(result["operacoes"][0]["id"], "impedir_consolidacao_de_provas")

    def test_repeticao_mesma_cena_e_deterministica(self):
        first = contexto_cena.select_candidates(self.repo, ["documentos", "registros"], scene_id="mesma")
        second = contexto_cena.select_candidates(self.repo, ["documentos", "registros"], scene_id="mesma")
        self.assertEqual(first, second)

    def test_teto_agregado_e_por_classe(self):
        result = contexto_cena.select_candidates(self.repo, ["documentos", "registros", "porto", "carga"], scene_id="tetos")
        self.assertLessEqual(len(result["presencas"]), 2)
        self.assertLessEqual(len(result["operacoes"]), 2)
        self.assertLessEqual(len(result["direcoes"]), 1)
        self.assertLessEqual(len(result["candidatos"]), 4)

    def test_orcamento_contextual_congela_fontes_tetos_e_payload(self):
        contract = yaml.safe_load((ROOT / "baseline/mundo-vivo-integracao-orcamento.yaml").read_text(encoding="utf-8"))
        opening = contract["limites"]["abertura_cena"]
        matched = contract["limites"]["descoberta_contextual_com_match"]
        self.assertEqual(opening["max_tags_contextuais"], contexto_cena.MAX_CONTEXT_TAGS)
        self.assertEqual(opening["max_candidatos_contextuais"], contexto_cena.MAX_CONTEXT_CANDIDATES)
        result = contexto_cena.select_candidates(self.repo, ["documentos", "escrituracao", "registros"], scene_id="budget")
        self.assertLessEqual(len(result["fontes_lidas"]), matched["max_fontes"])
        payload = json.dumps(result, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.assertLessEqual(len(payload), matched["max_payload_bytes"])

    def test_binding_de_linha_inexistente_falha_na_validacao_fria(self):
        router = yaml.safe_load((self.repo / contexto_cena.ROUTER).read_text())
        router["candidatos"]["operacao_fantasma"] = {
            "tipo": "operacao", "alvo": "linha_fantasma", "prioridade": 1, "tags": ["fantasma"]
        }
        self._write(contexto_cena.ROUTER.as_posix(), router)
        with self.assertRaisesRegex(contexto_cena.ContextSceneError, "linha operacional inexistente"):
            contexto_cena.validate(self.repo)

    def test_binding_de_direcao_inexistente_falha_na_validacao_fria(self):
        router = yaml.safe_load((self.repo / contexto_cena.ROUTER).read_text())
        router["candidatos"]["direcao_fantasma"] = {
            "tipo": "direcao", "alvo": "direcao_fantasma", "prioridade": 1, "tags": ["fantasma"]
        }
        self._write(contexto_cena.ROUTER.as_posix(), router)
        with self.assertRaisesRegex(contexto_cena.ContextSceneError, "direção inexistente"):
            contexto_cena.validate(self.repo)

    def test_grupo_livre_de_presenca_nao_precisa_arco(self):
        router = yaml.safe_load((self.repo / contexto_cena.ROUTER).read_text())
        item = router["candidatos"]["presenca_agente_b"]
        item["grupo_arco"] = "livre"
        router["candidatos"] = {"presenca_agente_b": item}
        self._write(contexto_cena.ROUTER.as_posix(), router)
        for rel in ("narrador/arcos/index.yaml", "narrador/arcos/estado.yaml", "narrador/arcos/parte_1.yaml"):
            (self.repo / rel).unlink()
        result = contexto_cena.select_candidates(self.repo, ["documentos"], scene_id="livre")
        self.assertEqual(result["presencas"][0]["id"], "agente_b")
        self.assertFalse(result["arco"]["aplicado"])

    def test_limite_tags_e_duro(self):
        with self.assertRaises(contexto_cena.ContextSceneError):
            contexto_cena.select_candidates(self.repo, [f"tag-{i}" for i in range(contexto_cena.MAX_CONTEXT_TAGS + 1)], scene_id="muitas")


class ContextoCenaBundleTest(unittest.TestCase):
    def test_roteador_real_tem_tres_classes_e_contrato_da_parte_1(self):
        router = contexto_cena.load_router(ROOT)
        types = {meta["tipo"] for meta in router["candidatos"].values()}
        self.assertEqual(types, {"presenca", "entrada", "operacao", "direcao"})
        info = arcos.current(ROOT)
        self.assertIn("kajiwara_shizune", info["habilitacoes"]["antagonistas"])
        self.assertIn("ponte_de_kozakura", info["habilitacoes"]["direcoes"])
        self.assertIn("impedir_consolidacao_de_provas", info["linhas_operacionais"])
        self.assertLessEqual((ROOT / contexto_cena.ROUTER).stat().st_size, 16384)


if __name__ == "__main__":
    unittest.main()
